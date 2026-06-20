"""Smoke v47: entity classification + QQ-nickname alias linking (v1.25).

Covers:
  A) _classify("123456789") -> "person" (pure-digit 5-11 -> account/user),
     no longer "unknown".
  B) store_summary with participant_names map links a QQ号 (actor_id) to its
     昵称: the stored entity name == 昵称, aliases include the QQ号,
     and type == "person".
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_classify_digit():
    from hippocampus.semantic import _classify
    assert _classify("123456789") == "person", _classify("123456789")
    assert _classify("12345") == "person"
    assert _classify("1234") == "unknown"          # too short
    assert _classify("123456789012") == "unknown"  # too long
    print("  A classify digit rule: OK")


def test_alias_linking():
    from hippocampus.config import MemoryConfig
    from hippocampus.service import MemoryService

    td = tempfile.mkdtemp()
    cfg = MemoryConfig()
    cfg.sqlite_path = os.path.join(td, "engram.db")
    cfg.enable_semantic = True
    svc = MemoryService(cfg=cfg)

    summary = {
        "summary": "1001 said hello to the group.",
        "key_facts": [],
        "topics": [],
        "participants": ["1001"],
        "participant_names": {"1001": "Alice"},
        "relations": [],
    }
    identity = {
        "chat_type": "group", "actor_id": "1001",
        "session_id": "s", "platform": "qq",
        "channel_id": "c", "group_id": "g1", "group_name": "Test",
        "memory_type": "episodic",
    }
    e = svc.store_summary(summary, identity)
    assert e is not None, "store_summary returned None"

    ent = svc.semantic.find_entity_by_name("Alice")
    assert ent is not None, "entity Alice not found"
    assert ent.type == "person", ent.type
    assert "1001" in ent.aliases, ent.aliases
    # the raw QQ号 should resolve back to the same entity via alias search
    by_alias = svc.semantic.search_entities("1001")
    assert any(x.id == ent.id for x in by_alias), "alias search miss"
    print("  B QQ->nickname alias linking: OK")


def main():
    test_classify_digit()
    test_alias_linking()
    print("v47 PASS")


if __name__ == "__main__":
    main()
