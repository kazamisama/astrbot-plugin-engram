"""Smoke v57: hard-delete soft-forgotten relations after retention, and
profile-fact decay wired into the maintenance sweep (v1.34/v1.35).
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_purge_forgotten():
    from hippocampus.relation_store import RelationStore, Relation
    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    rs = RelationStore(db)
    try:
        now = time.time()
        # soft-forgotten 20 days ago
        r1 = Relation(subject="A", predicate="p", object="B", confidence=0.05)
        r1.forgotten_at = now - 20 * 86400.0
        rs._insert(r1)
        # soft-forgotten only 3 days ago (within 14d retention)
        r2 = Relation(subject="C", predicate="p", object="D", confidence=0.05)
        r2.forgotten_at = now - 3 * 86400.0
        rs._insert(r2)
        # active relation, never forgotten
        r3 = Relation(subject="E", predicate="p", object="F", confidence=0.9)
        rs._insert(r3)

        deleted = rs.purge_forgotten(14 * 86400.0)
        assert deleted == 1, "only the 20d-old forgotten row deleted, got " + str(deleted)
        # r1 physically gone, r2 kept (still within retention), r3 active
        assert rs.get_by_id(r1.id) is None, "r1 must be hard-deleted"
        assert rs.get_by_id(r2.id) is not None, "r2 within retention must remain"
        assert rs.get_by_id(r3.id) is not None, "active r3 must remain"
        assert rs.count_active() == 1, "only E active"
        print("  purge: 20d forgotten deleted; 3d kept; active kept")
    finally:
        try: rs.close()
        except Exception: pass
        try: os.remove(db)
        except Exception: pass


def test_profile_decay_in_sweep():
    from hippocampus import MemoryService, MemoryConfig
    from hippocampus.profile import ProfileFact
    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    cfg = MemoryConfig(sqlite_path=db, embedding_name="hash", llm_name="rule")
    cfg.enable_profile = True
    cfg.memory_decay_enabled = False  # drive sweep manually
    cfg.profile_decay_enabled = True
    cfg.profile_fact_decay_days = 180.0
    svc = MemoryService(cfg)
    try:
        if svc.profile is None:
            print("  profile disabled in build; skip")
            return
        now = time.time()
        stale = ProfileFact(actor_id="u1", predicate="likes", value="cats",
                            confidence=0.8, evidence_count=1)
        # last evidence 1 year ago -> should decay
        stale.last_evidence_at = now - 365 * 86400.0
        svc.profile.upsert_fact(stale)
        # force last_evidence_at old (upsert may reset it)
        conn = svc.profile._ensure_conn()
        conn.execute("UPDATE profile_facts SET last_evidence_at=? WHERE actor_id='u1'",
                     (now - 365 * 86400.0,))
        conn.commit()

        before = svc.profile.facts_for("u1")
        conf_before = before[0].confidence if before else None

        rep = svc.run_memory_decay()
        assert "profile_facts" in rep, "sweep should report profile_facts: " + repr(rep)

        after = svc.profile.facts_for("u1")
        conf_after = after[0].confidence if after else 0.0
        assert conf_after < conf_before, "stale fact confidence should drop (%.3f -> %.3f)" % (
            conf_before, conf_after)
        print("  profile fact decayed in sweep: %.3f -> %.3f (report=%r)" % (
            conf_before, conf_after, rep.get("profile_facts")))
    finally:
        try: svc.close()
        except Exception: pass
        try: os.remove(db)
        except Exception: pass


def main():
    test_purge_forgotten()
    test_profile_decay_in_sweep()
    print(chr(10) + "v57 purge + profile-decay smoke: ALL PASS")


if __name__ == "__main__":
    main()
