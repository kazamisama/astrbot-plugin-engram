"""tiering: hot / warm / cold memory tiers (v1.13, memori-inspired).

memori marks each atom ACTIVE / DORMANT / ARCHIVED and only retrieves
ACTIVE rows; decay + TTL drive the transitions. We bring the same idea to
Engram, but keep it non-destructive and derived from data engram already
tracks (strength / last_accessed / created_at), so no engram is ever lost:

  - hot : recently accessed AND still strong -> always recalled first.
  - warm: not hot but not stale -> recalled normally.
  - cold: stale / weak -> excluded from normal recall, kept in the DB and
          only pulled in as a fallback when hot+warm under-deliver.

`classify()` is a pure function of an engram + config + now, so the tier
can be recomputed any time (recall, ingest, background sweep) without
trusting a possibly-stale stored value. The stored `tier` field is just a
cache/index for fast filtering and observability.
"""
from __future__ import annotations
import time

HOT = "hot"
WARM = "warm"
COLD = "cold"
TIERS = (HOT, WARM, COLD)

_DAY = 86400.0


def classify(e, cfg, now: float | None = None) -> str:
    """Return the tier for engram `e` under `cfg`. Pure / side-effect free.

    A soft-forgotten engram (forgotten_at > 0) is always cold. Otherwise:
    recent + strong -> hot; within the warm age window -> warm; else cold.
    Age is measured from last_accessed when available, else created_at, so
    a freshly created (never-recalled) engram still counts as recent.
    """
    n = time.time() if now is None else now
    if getattr(e, "forgotten_at", 0.0):
        return COLD
    last = float(getattr(e, "last_accessed", 0.0) or 0.0)
    created = float(getattr(e, "created_at", 0.0) or 0.0)
    ref = last if last > 0 else created
    # No usable timestamp -> treat as fresh (age 0). Otherwise measure from
    # ref, clamped to >= 0 so future/skewed timestamps just read as fresh.
    age_days = 0.0 if ref <= 0 else max(0.0, (n - ref) / _DAY)
    strength = float(getattr(e, "strength", 0.0) or 0.0)

    hot_age = float(getattr(cfg, "tier_hot_max_age_days", 3.0))
    hot_str = float(getattr(cfg, "tier_hot_min_strength", 0.5))
    warm_age = float(getattr(cfg, "tier_warm_max_age_days", 30.0))
    cold_floor = float(getattr(cfg, "tier_cold_strength_floor", 0.1))

    if strength < cold_floor:
        return COLD
    if age_days <= hot_age and strength >= hot_str:
        return HOT
    if age_days <= warm_age:
        return WARM
    return COLD


class TieringEngine:
    """Recall-side tier routing + background reclassification over the store."""

    def __init__(self, store, cfg) -> None:
        self._store = store
        self._cfg = cfg

    # ---- recall-side routing ----
    def split_candidates(self, scored, now: float | None = None):
        """Split [(engram, score), ...] into (hot_warm, cold) by live tier."""
        n = time.time() if now is None else now
        hot_warm = []
        cold = []
        for e, sc in scored:
            t = classify(e, self._cfg, n)
            (cold if t == COLD else hot_warm).append((e, sc))
        return hot_warm, cold

    # ---- background sweep ----
    def reclassify_all(self, limit: int = 1_000_000) -> dict:
        """Recompute + persist the cached tier for every engram. Returns a
        {hot, warm, cold, changed} count dict. Never deletes anything."""
        now = time.time()
        counts = {HOT: 0, WARM: 0, COLD: 0, "changed": 0}
        rows = self._store.all(limit=limit)
        for e in rows:
            new_tier = classify(e, self._cfg, now)
            counts[new_tier] += 1
            if getattr(e, "tier", "") != new_tier:
                e.tier = new_tier
                counts["changed"] += 1
                try:
                    self._store.upsert(e)
                except Exception as ex:
                    print("[hippocampus] tier reclassify upsert error: " + repr(ex))
        return counts
