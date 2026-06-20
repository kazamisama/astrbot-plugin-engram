"""Smoke v49: graph entity hard-delete + relation confidence/delete (v1.28).

Backend-level coverage of the new SemanticStore + GraphHandler ops:
  - delete_entity removes the entity AND every relation touching it.
  - set_relation_confidence clamps to [0,1] and persists.
  - delete_relation removes a single edge.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main():
    from hippocampus.semantic import SemanticStore
    from hippocampus.types import Entity, Relation

    td = tempfile.mkdtemp()
    sem = SemanticStore(os.path.join(td, "sem.db"))

    a = sem.upsert_entity(Entity(name="Alice", type="person"))
    b = sem.upsert_entity(Entity(name="Shanghai", type="place"))
    c = sem.upsert_entity(Entity(name="Bob", type="person"))
    r1 = Relation(subject_id=a.id, predicate="resides_in", object_id=b.id,
                  confidence=0.8)
    r2 = Relation(subject_id=c.id, predicate="knows", object_id=a.id,
                  confidence=0.5)
    sem.add_relation(r1)
    sem.add_relation(r2)

    # set_relation_confidence clamps and persists
    assert sem.set_relation_confidence(r1.id, 1.7) is True
    got = [x for x in sem.relations_of(a.id) if x.id == r1.id][0]
    assert got.confidence == 1.0, got.confidence
    assert sem.set_relation_confidence(r1.id, -0.3) is True
    got = [x for x in sem.relations_of(a.id) if x.id == r1.id][0]
    assert got.confidence == 0.0, got.confidence
    assert sem.set_relation_confidence("nope", 0.5) is False
    print("  set_relation_confidence clamp+persist: OK")

    # delete a single relation
    assert sem.delete_relation(r2.id) is True
    assert sem.delete_relation(r2.id) is False
    assert all(x.id != r2.id for x in sem.relations_of(a.id))
    print("  delete_relation: OK")

    # delete entity cascades to its remaining relations (r1)
    n = sem.delete_entity(a.id)
    assert n == 1, n
    assert sem.get_entity(a.id) is None
    assert sem.relations_of(b.id) == []
    print("  delete_entity cascade: OK")

    # GraphHandler wrappers (ok/error shape)
    from page_api_modules.graph import GraphHandler
    class _Utils:
        def ok(self, d): return {"status": "ok", "data": d}
        def error(self, m): return {"status": "error", "message": m}
    class _Svc:
        semantic = sem
        store = None
    gh = GraphHandler(_Utils())
    assert gh.update_relation(_Svc(), "nope", 0.5)["status"] == "error"
    assert gh.delete_relation(_Svc(), "nope")["status"] == "error"
    assert gh.delete_entity(_Svc(), b.id)["status"] == "ok"
    assert sem.get_entity(b.id) is None
    print("  GraphHandler wrappers: OK")

    print("v49 PASS")


if __name__ == "__main__":
    main()
