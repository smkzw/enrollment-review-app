from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.storage.boundaries import ProtectedPathError, snapshot_tree
from app.storage.migrate import MigrationManager

from .conftest import REPO_ROOT

LEGACY_PROJECTS_ROOT = REPO_ROOT / "projects"


def test_legacy_tree_unchanged_after_storage_lifecycle(data_paths):
    """完整迁移/备份/降级/恢复周期不得改动 legacy projects/ 树。"""
    before = snapshot_tree(LEGACY_PROJECTS_ROOT)

    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    manager.downgrade("base")
    second = manager.upgrade("head")
    assert second.backup is not None
    manager.restore(second.backup.path)

    assert before == snapshot_tree(LEGACY_PROJECTS_ROOT)


def test_backup_and_manifest_confined_to_data_root(data_paths):
    raw = sqlite3.connect(str(data_paths.db_path))
    raw.close()
    manager = MigrationManager(data_paths)
    record = manager.create_backup()
    assert record is not None
    assert data_paths.boundary.require_v2_target(record.path) == record.path.resolve()
    assert (
        data_paths.boundary.require_v2_target(record.manifest_path)
        == record.manifest_path.resolve()
    )


def test_storage_boundary_rejects_legacy_and_unscoped_targets(data_paths):
    boundary = data_paths.boundary
    with pytest.raises(ProtectedPathError):
        boundary.require_v2_target(REPO_ROOT / "projects" / "probe.sqlite3")
    with pytest.raises(ProtectedPathError):
        boundary.require_v2_target(REPO_ROOT / "unscoped.sqlite3")


def test_storage_cycle_writes_only_inside_data_root(data_paths, tmp_path):
    """迁移周期产生的所有文件都必须落在 data_v2 根内。"""
    allowed_root = data_paths.root
    before = {path for path in tmp_path.rglob("*")}
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    manager.create_backup()
    manager.downgrade("base")
    manager.upgrade("head")
    after = {path for path in tmp_path.rglob("*")}
    new_paths = after - before
    assert new_paths, "迁移周期应产生新文件"
    for path in new_paths:
        assert path.is_relative_to(allowed_root), f"越界写入：{path}"
