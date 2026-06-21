"""v1.36 smoke: persona-scoped memory isolation.

Engrams written under different persona ids must not leak across recall;
passing persona_id=None disables scoping.
"""
import os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hippocampus import MemoryService, MemoryConfig, Cue


def _mk(db):
    cfg = MemoryConfig(sqlite_path=db, embedding_name="hash", llm_name="rule")
    cfg.memory_decay_enabled = False
    return MemoryService(cfg)


def main():
    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    svc = _mk(db)
    try:
        assert MemoryConfig().persona_isolation_enabled is True
        print("[OK] persona_isolation_enabled defaults True")

        common = dict(session_id="s1", actor_id="u1", platform="qq", channel_id="g100")
        e_cat = svc.observe(content="cat persona note alpha", persona_id="cat", **common)
        e_dog = svc.observe(content="dog persona note beta", persona_id="dog", **common)

        assert svc.store.get(e_cat.id).persona_id == "cat"
        assert svc.store.get(e_dog.id).persona_id == "dog"
        print("[OK] persona_id persisted on engram")

        r_cat = svc.recall(Cue(text="note", actor_id="u1", channel_id="g100",
                               persona_id="cat", k=10, mode="hybrid"))
        pids = {getattr(e, "persona_id", "") for e in r_cat.engrams}
        assert pids <= {"cat"}, ("leak in cat recall", pids)

        r_dog = svc.recall(Cue(text="note", actor_id="u1", channel_id="g100",
                               persona_id="dog", k=10, mode="hybrid"))
        pids2 = {getattr(e, "persona_id", "") for e in r_dog.engrams}
        assert pids2 <= {"dog"}, ("leak in dog recall", pids2)
        print("[OK] cross-persona recall isolated")

        r_all = svc.recall(Cue(text="note", actor_id="u1", channel_id="g100",
                               persona_id=None, k=10, mode="hybrid"))
        pids3 = {getattr(e, "persona_id", "") for e in r_all.engrams}
        assert {"cat", "dog"} <= pids3, ("None scope must not filter persona", pids3)
        print("[OK] persona_id=None disables scoping")
        print("ALL PASS")
    finally:
        try:
            svc.close()
        except Exception:
            pass
        try:
            os.remove(db)
        except Exception:
            pass


if __name__ == "__main__":
    main()
