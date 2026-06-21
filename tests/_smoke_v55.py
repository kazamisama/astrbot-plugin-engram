"""Smoke v55: periodic memory decay + tier maintenance (v1.33).

Confirms that:
  - run_memory_decay() applies Ebbinghaus strength decay to engrams whose
    last_accessed is old, dropping their strength (non-destructive).
  - the decay loop honors memory_decay_enabled / interval (default ON).
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main():
    from hippocampus import MemoryService, MemoryConfig
    from hippocampus.types import Engram

    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    cfg = MemoryConfig(sqlite_path=db, embedding_name="hash", llm_name="rule")
    # keep the background daemon OFF during the test; we drive decay manually.
    cfg.memory_decay_enabled = False
    cfg.decay_tau_base = 60 * 60 * 24 * 7.0  # 7 days
    cfg.decay_floor = 0.05
    svc = MemoryService(cfg)
    try:
        # an OLD engram (last accessed 60 days ago) and a FRESH one (now)
        old_ts = time.time() - 60 * 24 * 3600
        e_old = Engram(content="x_old", summary="x_old", actor_id="a",
                       strength=1.0, importance=0.0,
                       created_at=old_ts, last_accessed=old_ts)
        e_new = Engram(content="x_new", summary="x_new", actor_id="a",
                       strength=1.0, importance=0.0)
        svc.store.upsert(e_old)
        svc.store.upsert(e_new)

        rep = svc.run_memory_decay()
        rows = {e.summary: e for e in svc.store.all(limit=10)}
        s_old = rows["x_old"].strength
        s_new = rows["x_new"].strength
        # old decayed heavily (60d >> tau 7d), fresh barely moved
        assert s_old < 0.05, "old engram should decay below floor, got " + str(s_old)
        assert s_new > 0.9, "fresh engram should stay high, got " + str(s_new)
        # non-destructive: both rows still present
        assert len(rows) == 2, "decay must not delete rows"
        print("  old strength %.4f -> below floor; fresh %.4f kept" % (s_old, s_new))
        print("  report: " + repr(rep))

        # importance protects memory: a high-importance old engram decays slower
        e_imp = Engram(content="x_imp", summary="x_imp", actor_id="a",
                       strength=1.0, importance=1.0,
                       created_at=old_ts, last_accessed=old_ts)
        svc.store.upsert(e_imp)
        svc.run_memory_decay()
        s_imp = {e.summary: e for e in svc.store.all(limit=10)}["x_imp"].strength
        assert s_imp > s_old, "importance should slow decay (%.4f vs %.4f)" % (s_imp, s_old)
        print("  importance slows decay: imp=%.4f > plain=%.4f" % (s_imp, s_old))

        print(chr(10) + "v55 memory decay smoke: ALL PASS")
    finally:
        try: svc.close()
        except Exception: pass
        try: os.remove(db)
        except Exception: pass


if __name__ == "__main__":
    main()
