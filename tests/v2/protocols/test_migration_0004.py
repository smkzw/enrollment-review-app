"""迁移 0004 方案提取表：升级/降级/重升级往返与 schema-metadata 一致性。"""
from __future__ import annotations

from sqlalchemy import inspect

from app.storage.db import Base, build_engine
from app.storage.migrate import MigrationManager, verify_schema_matches_metadata

PROTOCOL_TABLES = {
    "protocol_source_artifacts",
    "protocol_render_artifacts",
    "protocol_extraction_snapshots",
    "protocol_source_spans",
    "frozen_protocol_catalogs",
}


def _table_names(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_0004_upgrade_downgrade_upgrade_roundtrip(data_paths):
    manager = MigrationManager(data_paths)

    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert PROTOCOL_TABLES <= _table_names(engine)
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()

    manager.downgrade("0003")
    engine = build_engine(data_paths.db_path)
    try:
        assert PROTOCOL_TABLES.isdisjoint(_table_names(engine))
    finally:
        engine.dispose()

    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert PROTOCOL_TABLES <= _table_names(engine)
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()
