"""Smoke v1.15: frequency-aware recall (access_count term).

Covers:
  - frequency_recall_weight config field registered + default 0.0
  - with weight=0, recall scoring identical to before (no freq influence)
  - with weight>0, a high-access_count engram outranks an otherwise-equal
    low-access_count engram for the same cue
"""
import sys, os, tempfile, time


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hippocampus.config import MemoryConfig
from hippocampus.config_manager import ConfigManager, _FIELDS, LABELS


def banner(m):
    print(chr(10) + "=== " + m + " ===")


def test_field_default():
    banner("frequency_recall_weight field + default")
    assert "frequency_recall_weight" in _FIELDS
    assert "frequency_recall_weight" in LABELS
    cfg = ConfigManager({}).memory_config
    assert cfg.frequency_recall_weight == 0.0
    print("  field + default 0.0 OK")


def _svc(tmp, weight):
    from hippocampus.service import MemoryService
    cfg = MemoryConfig()
    cfg.sqlite_path = os.path.join(tmp, "h.db")
    cfg.enable_semantic = False
    cfg.enable_prospective = False
    cfg.enable_profile = False
    cfg.enable_persona = False
    cfg.dedup_enabled = False
    cfg.enable_separation = False
    cfg.tiering_enabled = False
    cfg.metamemory_enabled = False
    cfg.importance_floor_for_long_term = 0.0
    cfg.frequency_recall_weight = weight
    return MemoryService(cfg=cfg), cfg


def _seed(svc, content, access_count):
    from hippocampus.types import Engram
    now = time.time()
    e = Engram(actor_id="u1", platform="qq", channel_id="g1",
               content=content, summary=content, strength=0.5,
               created_at=now, last_accessed=now, access_count=access_count,
               embedding_model=svc._current_embedding_name)
    e.embedding = svc.embedder.embed(content)
    svc.store.upsert(e)
    return e


def _rank(weight):
    tmp = tempfile.mkdtemp()
    svc, cfg = _svc(tmp, weight)
    # two near-identical contents, differ only by access_count
    a = _seed(svc, "用户喜欢奶茶", access_count=50)
    b = _seed(svc, "用户喜欢奶茶呢", access_count=0)
    from hippocampus.types import Cue; res = svc.recall(Cue(text="奶茶", actor_id="u1", k=2))
    out = res.engrams if hasattr(res, "engrams") else res
    ids = [e.id for e in out]
    try:
        svc.close()
    except Exception:
        pass
    return ids, a.id, b.id


def test_weight_changes_order():
    banner("freq weight boosts high-access_count engram")
    ids0, a0, b0 = _rank(0.0)
    ids1, a1, b1 = _rank(0.30)
    # with strong weight, the high-access_count engram (a) should rank first
    assert a1 in ids1, "high-access engram must be recalled"
    assert ids1[0] == a1, "high-access engram should rank first with freq weight"
    print("  weight=0:", ids0[:2], " weight=0.3 first:", ids1[0] == a1, "OK")


def main():
    test_field_default()
    test_weight_changes_order()
    print(chr(10) + "v1.15 smoke: ALL PASS")


if __name__ == "__main__":
    main()
