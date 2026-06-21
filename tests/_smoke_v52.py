"""Smoke v52: SemanticStore/RelationStore unification via mirror (v1.30).

store_summary now mirrors each LLM relation into SemanticStore so internal
graph algorithms (activation/profile/graph retrieval) and the WebUI share
the SAME LLM-derived facts, with entity type taken from the LLM. This fixes
the rule-classified ??=unknown problem at the SemanticStore layer too.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_SH = "\u4e0a\u6d77"   # place
_XM = "\u5c0f\u660e"   # ?? person


def main():
    from hippocampus import MemoryService, MemoryConfig

    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    cfg = MemoryConfig(sqlite_path=db, embedding_name="hash", llm_name="rule")
    svc = MemoryService(cfg)
    try:
        summary = {
            "summary": "s", "key_facts": [], "topics": [],
            "participants": ["Alice"],
            "relations": [
                {"subject": "Alice", "relation": "resides_in",
                 "object": _SH, "confidence": 0.9,
                 "subject_type": "person", "object_type": "place"},
                {"subject": "Alice", "relation": "knows",
                 "object": _XM, "confidence": 0.7,
                 "subject_type": "person", "object_type": "person"},
            ],
            "participant_names": {},
        }
        identity = {"chat_type": "group", "actor_id": "conversation",
                    "channel_id": "g1", "memory_type": "episodic"}
        svc.store_summary(summary, identity)

        # RelationStore (UI source) has the 2 LLM relations
        assert svc.relation_store.count_active() == 2, svc.relation_store.count_active()

        # SemanticStore now mirrors the same facts
        ents = {ent.name: ent for ent in svc.semantic.all_entities(limit=100)}
        assert "Alice" in ents and ents["Alice"].type == "person", ents
        assert _SH in ents and ents[_SH].type == "place", {k: v.type for k, v in ents.items()}
        # ?? typed as person at the SemanticStore layer too (was unknown)
        assert _XM in ents and ents[_XM].type == "person", {k: v.type for k, v in ents.items()}

        # mirrored relations link real entity ids with confidence
        alice = ents["Alice"]
        rels = svc.semantic.relations_of(alice.id)
        preds = sorted(r.predicate for r in rels)
        assert preds == ["knows", "resides_in"], preds
        assert any(abs(r.confidence - 0.9) < 1e-9 for r in rels), [r.confidence for r in rels]

        # internal graph algorithm can now traverse LLM facts: activation
        # resolves Alice and finds neighbors via SemanticStore.
        if svc.activation is not None:
            hit = svc.semantic.find_entity_by_name("Alice")
            assert hit is not None and hit.type == "person"
        print("v52 OK")
    finally:
        svc.close()
        try: os.unlink(db)
        except OSError: pass


if __name__ == "__main__":
    main()
