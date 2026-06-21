"""Smoke v56: relation confidence time-decay (v1.34).

A relation not re-observed loses confidence exponentially by updated_at age;
once below relation_decay_floor it is soft-forgotten (forgotten_at set, row
kept, dropped from active queries). Re-observed (fresh) relations stay sharp.
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main():
    from hippocampus.relation_store import RelationStore, Relation

    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    rs = RelationStore(db)
    try:
        now = time.time()
        old_ts = now - 90 * 24 * 3600   # 90 days stale
        mid_ts = now - 20 * 24 * 3600   # 20 days
        # stale high-conf relation
        r_old = Relation(subject="A", predicate="knows", object="B",
                         confidence=0.9)
        r_old.created_at = old_ts; r_old.updated_at = old_ts
        rs._insert(r_old)
        # mid-age relation
        r_mid = Relation(subject="C", predicate="likes", object="D",
                         confidence=0.9)
        r_mid.created_at = mid_ts; r_mid.updated_at = mid_ts
        rs._insert(r_mid)
        # fresh relation
        r_new = Relation(subject="E", predicate="met", object="F",
                         confidence=0.9)
        rs._insert(r_new)

        assert rs.count_active() == 3, rs.count_active()

        tau = 30 * 24 * 3600.0   # 30d
        floor = 0.1
        rep = rs.decay_pass(tau, floor)
        print("  decay report: " + repr(rep))

        active = {r.subject: r for r in rs.all_active(limit=10)}
        # 90d stale: 0.9*exp(-90/30)=0.9*0.0498=0.0448 < floor -> forgotten
        assert "A" not in active, "stale relation should be soft-forgotten"
        # 20d: 0.9*exp(-20/30)=0.9*0.513=0.462 -> decayed but alive
        assert "C" in active, "mid-age relation should survive"
        assert active["C"].confidence < 0.9, active["C"].confidence
        assert active["C"].confidence > floor, active["C"].confidence
        # fresh: ~unchanged (dt~0)
        assert "E" in active and active["E"].confidence > 0.89, active["E"].confidence
        assert rs.count_active() == 2, "one forgotten -> 2 active"
        # soft-forget keeps the row (audit): get_by_id still returns it
        assert rs.get_by_id(r_old.id) is not None, "forgotten row must be kept"
        print("  stale forgotten, mid decayed to %.3f, fresh kept %.3f"
              % (active["C"].confidence, active["E"].confidence))

        # idempotent-ish: re-running decays mid further, never below 0
        rep2 = rs.decay_pass(tau, floor)
        print("  second pass: " + repr(rep2))

        print(chr(10) + "v56 relation decay smoke: ALL PASS")
    finally:
        try: rs.close()
        except Exception: pass
        try: os.remove(db)
        except Exception: pass


if __name__ == "__main__":
    main()
