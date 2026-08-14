"""Migration 0005 upgrade/downgrade coverage for slice 2."""
from __future__ import annotations

from sqlalchemy import inspect

from app.storage.db import Base, build_engine
from app.storage.migrate import MigrationManager, verify_schema_matches_metadata


SLICE2_TABLES = {
    "protocol_metadata_candidates",
    "protocol_metadata_conflicts",
    "protocol_identity_decisions",
    "study_phase_candidates",
    "study_phase_selections",
    "protocol_phase_applicability_graphs",
    "protocol_phase_projections",
    "interpretation_sources",
    "interpretation_conflicts",
}


def test_0005_upgrade_downgrade_upgrade_roundtrip(data_paths) -> None:
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert SLICE2_TABLES <= set(inspect(engine).get_table_names())
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()

    manager.downgrade("0004")
    engine = build_engine(data_paths.db_path)
    try:
        assert SLICE2_TABLES.isdisjoint(set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()

    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert SLICE2_TABLES <= set(inspect(engine).get_table_names())
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()
