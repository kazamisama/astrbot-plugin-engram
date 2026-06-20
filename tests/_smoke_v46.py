"""Smoke v46: legacy relations table (no rkey column) auto-migrates.

Regression for the production bug:
    [hippocampus] recall_relations error: OperationalError('no such column: rkey')
caused by CREATE TABLE IF NOT EXISTS skipping rkey on a pre-existing
legacy table. _init_schema now does a PRAGMA + ALTER TABLE migration.
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_LEGACY = (
    "CREATE TABLE relations ("
    " id TEXT PRIMARY KEY,"
    " subject TEXT, predicate TEXT, object TEXT,"
    " confidence REAL, actor_id TEXT, channel_id TEXT,"
    " source_engram_id TEXT,"
    " created_at REAL, updated_at REAL,"
    " superseded_by TEXT, forgotten_at REAL)"
)


def _cols(db):
    c = sqlite3.connect(db)
    try:
        return [r[1] for r in c.execute("PRAGMA table_info(relations)").fetchall()]
    finally:
        c.close()


def main():
    from hippocampus.relation_store import RelationStore
    td = tempfile.mkdtemp()

    # 1) legacy table without rkey -> opening + first use migrates it
    legacy = os.path.join(td, "legacy.db")
    c = sqlite3.connect(legacy)
    c.execute(_LEGACY)
    c.commit()
    c.close()
    assert "rkey" not in _cols(legacy)
    rs = RelationStore(legacy)
    rs._ensure_conn()
    assert "rkey" in _cols(legacy), _cols(legacy)
    print("  legacy table migrated: rkey added OK")

    # 2) fresh db has rkey from the start
    fresh = os.path.join(td, "fresh.db")
    rs2 = RelationStore(fresh)
    rs2._ensure_conn()
    assert "rkey" in _cols(fresh), _cols(fresh)
    print("  fresh table has rkey OK")

    print("v46 OK")


if __name__ == "__main__":
    main()
