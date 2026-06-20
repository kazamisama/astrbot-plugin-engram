"""Smoke v1.13: hot/warm/cold memory tiering.

Covers:
  - tiering.classify boundaries (hot/warm/cold by age + strength + forgotten)
  - config fields registered with defaults
  - TieringEngine.split_candidates routes cold out of normal recall
  - service recall: cold engram excluded normally, included on fallback
  - reclassify_tiers persists tiers and never deletes
"""
import sys, os, tempfile, time


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hippocampus.tiering import classify, TieringEngine, HOT, WARM, COLD
from hippocampus.config import MemoryConfig
from hippocampus.config_manager import ConfigManager, _FIELDS, LABELS


def banner(m):
    print(chr(10) + "=== " + m + " ===")


DAY = 86400.0


class _E:
    def __init__(self, strength=1.0, last=0.0, created=0.0, forgotten=0.0):
        self.strength = strength
        self.last_accessed = last
        self.created_at = created
        self.forgotten_at = forgotten
        self.tier = ""


def test_classify():
    banner("classify boundaries")
    cfg = MemoryConfig()
    now = 1_700_000_000.0
    # fresh + strong -> hot
    assert classify(_E(strength=1.0, created=now - 1 * DAY), cfg, now) == HOT
    # strong but old (10 days) -> warm
    assert classify(_E(strength=0.8, created=now - 10 * DAY), cfg, now) == WARM
    # very old (60 days) -> cold
    assert classify(_E(strength=0.8, created=now - 60 * DAY), cfg, now) == COLD
    # weak below floor -> cold regardless of age
    assert classify(_E(strength=0.05, created=now), cfg, now) == COLD
    # soft-forgotten -> cold
    assert classify(_E(strength=1.0, created=now, forgotten=now), cfg, now) == COLD
    # recent access overrides old creation
    assert classify(_E(strength=0.9, created=now - 100 * DAY, last=now - 1 * DAY), cfg, now) == HOT
    print("  hot/warm/cold boundaries OK")


def test_config_fields():
    banner("tiering config fields")
    for f in ("tiering_enabled", "tier_hot_max_age_days", "tier_hot_min_strength",
              "tier_warm_max_age_days", "tier_cold_strength_floor",
              "tier_recall_include_cold", "tier_cold_fallback_min_hits",
              "tier_maintenance_interval_seconds"):
        assert f in _FIELDS, f
        assert f in LABELS, f
    cfg = ConfigManager({}).memory_config
    assert cfg.tiering_enabled is True
    assert cfg.tier_hot_max_age_days == 3.0
    assert cfg.tier_warm_max_age_days == 30.0
    print("  fields + defaults OK")


def test_split_candidates():
    banner("split_candidates routes cold out")
    cfg = MemoryConfig()
    now = 1_700_000_000.0
    hot = _E(strength=1.0, created=now)
    cold = _E(strength=0.05, created=now)
    eng = TieringEngine(store=None, cfg=cfg)
    hw, cd = eng.split_candidates([(hot, 1.0), (cold, 0.9)], now=now)
    assert [e for e, _ in hw] == [hot]
    assert [e for e, _ in cd] == [cold]
    print("  routing OK")


def _build_service(tmp):
    from hippocampus.service import MemoryService
    cfg = MemoryConfig()
    cfg.sqlite_path = os.path.join(tmp, "hippo.db")
    cfg.enable_semantic = False
    cfg.enable_prospective = False
    cfg.enable_profile = False
    cfg.enable_persona = False
    cfg.dedup_enabled = False
    cfg.tiering_enabled = True
    cfg.importance_floor_for_long_term = 0.0
    svc = MemoryService(cfg=cfg)
    return svc, cfg


def test_recall_excludes_cold_then_fallback():
    banner("recall excludes cold; fallback includes it")
    from hippocampus.types import Engram, Cue
    tmp = tempfile.mkdtemp()
    svc, cfg = _build_service(tmp)
    now = time.time()
    # one cold engram (weak) matching the query
    cold = Engram(actor_id="u1", platform="qq", channel_id="g1",
                  content="\u8c1c\u9898\u5f88\u6709\u8da3",
                  summary="\u8c1c\u9898\u5f88\u6709\u8da3",
                  strength=0.02, created_at=now - 90 * DAY,
                  embedding_model=svc._current_embedding_name)
    cold.embedding = svc.embedder.embed(cold.content)
    svc.store.upsert(cold)
    # default: cold excluded, fallback min_hits=1 so it still surfaces when
    # nothing else matches -> with no hot/warm hits, fallback brings cold in.
    res = svc.recall(Cue(text="\u8c1c\u9898", actor_id="u1", k=5))
    got = [e.id for e in (res.engrams or [])]
    assert cold.id in got, "fallback should surface the only (cold) match"
    print("  cold fallback surfaced the match: OK")
    # now disable fallback (min_hits=0) -> cold must NOT appear
    cfg.tier_cold_fallback_min_hits = 0
    res2 = svc.recall(Cue(text="\u8c1c\u9898", actor_id="u1", k=5))
    got2 = [e.id for e in (res2.engrams or [])]
    assert cold.id not in got2, "with fallback off, cold must be excluded"
    print("  cold excluded when fallback off: OK")
    try:
        svc.close()
    except Exception:
        pass


def test_reclassify_persists_no_delete():
    banner("reclassify_tiers persists + never deletes")
    from hippocampus.types import Engram
    tmp = tempfile.mkdtemp()
    svc, cfg = _build_service(tmp)
    now = time.time()
    a = Engram(actor_id="u1", content="a", summary="a", strength=1.0,
               created_at=now, embedding_model=svc._current_embedding_name)
    b = Engram(actor_id="u1", content="b", summary="b", strength=0.02,
               created_at=now - 90 * DAY,
               embedding_model=svc._current_embedding_name)
    for e in (a, b):
        e.embedding = svc.embedder.embed(e.content)
        svc.store.upsert(e)
    counts = svc.reclassify_tiers()
    assert counts.get(HOT, 0) >= 1 and counts.get(COLD, 0) >= 1, counts
    # nothing deleted
    assert len(svc.store.all(limit=100)) == 2
    # persisted tier readable
    assert svc.store.get(b.id).tier == COLD
    print("  reclassified " + str(counts) + ": OK")
    try:
        svc.close()
    except Exception:
        pass


def main():
    test_classify()
    test_config_fields()
    test_split_candidates()
    test_recall_excludes_cold_then_fallback()
    test_reclassify_persists_no_delete()
    print(chr(10) + "v1.13 smoke: ALL PASS")


if __name__ == "__main__":
    main()
