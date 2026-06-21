"""Smoke v54: WebUI graph per-pair relation cap (v1.31).

graph_data caps relations shown between a single entity pair to the top-N by
confidence (graph_max_relations_per_pair, default 4) so multiple-relation
labels don't pile on the same edge midpoint. Edges also carry confidence.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main():
    from hippocampus import MemoryService, MemoryConfig
    from page_api_modules.graph import GraphHandler

    class _Utils:
        def ok(self, d): return {"status": "ok", "data": d}
        def error(self, m): return {"status": "error", "message": m}

    fd, db = tempfile.mkstemp(suffix=".db"); os.close(fd)
    cfg = MemoryConfig(sqlite_path=db, embedding_name="hash", llm_name="rule")
    cfg.graph_max_relations_per_pair = 2  # cap to 2 for the test
    svc = MemoryService(cfg)
    gh = GraphHandler(_Utils())
    try:
        # 5 relations between the SAME pair (A<->B), differing confidence
        rels = []
        confs = [0.5, 0.9, 0.7, 0.3, 0.95]
        for i, cf in enumerate(confs):
            rels.append({"subject": "A", "relation": "rel_" + str(i),
                         "object": "B", "confidence": cf,
                         "subject_type": "person", "object_type": "person"})
        summary = {"summary": "s", "key_facts": [], "topics": [],
                   "participants": ["A"], "relations": rels,
                   "participant_names": {}}
        identity = {"chat_type": "group", "actor_id": "conversation",
                    "channel_id": "g1", "memory_type": "episodic"}
        svc.store_summary(summary, identity)

        assert svc.relation_store.count_active() == 5, svc.relation_store.count_active()

        gd = gh.graph_data(svc)["data"]
        edges = gd["edges"]
        # capped to 2 between the single pair
        assert len(edges) == 2, "per-pair cap=2, got " + str(len(edges))
        # the kept ones are the top-2 by confidence: 0.95 (rel_4) + 0.9 (rel_1)
        preds = sorted(e["predicate"] for e in edges)
        assert preds == ["rel_1", "rel_4"], preds
        # confidence is included in edge payload
        assert all("confidence" in e for e in edges), edges
        print("  per-pair cap keeps top-2 by confidence: " + str(preds))

        # raising the cap shows all 5
        svc.cfg.graph_max_relations_per_pair = 10
        gd2 = gh.graph_data(svc)["data"]
        assert len(gd2["edges"]) == 5, "cap=10 -> all 5, got " + str(len(gd2["edges"]))
        print("  cap=10 shows all 5 OK")

        print(chr(10) + "v54 graph per-pair cap smoke: ALL PASS")
    finally:
        try: svc.close()
        except Exception: pass
        try: os.remove(db)
        except Exception: pass


if __name__ == "__main__":
    main()
