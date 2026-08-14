from __future__ import annotations

import pytest

from app.storage.config import (
    DEFAULT_DATA_ROOT,
    MIN_SQLITE_VERSION,
    DataDirError,
    SQLiteRuntimeTooOld,
    resolve_data_paths,
    resolve_data_root,
    runtime_sqlite_version,
    verify_sqlite_runtime,
)

from .conftest import REPO_ROOT


def test_default_data_root_is_repo_data_v2(monkeypatch):
    monkeypatch.delenv("ENROLLMENT_V2_DATA_DIR", raising=False)
    assert resolve_data_root() == (REPO_ROOT / "data_v2").resolve()


def test_env_override_resolves(tmp_path, monkeypatch):
    target = tmp_path / "custom-v2"
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(target))
    assert resolve_data_root() == target.resolve()


def test_relative_override_resolves_against_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", "relative-data")
    assert resolve_data_root() == (REPO_ROOT / "relative-data").resolve()


def test_data_root_inside_legacy_root_rejected(tmp_path):
    legacy = tmp_path / "projects"
    with pytest.raises(DataDirError):
        resolve_data_root(str(legacy / "data_v2"), legacy_roots=(legacy,))


def test_legacy_root_inside_data_root_rejected(tmp_path):
    data_root = tmp_path / "v2-data"
    with pytest.raises(DataDirError):
        resolve_data_root(str(data_root), legacy_roots=(data_root / "projects",))


def test_default_data_root_does_not_overlap_repo_legacy_roots():
    # 默认布局必须始终合法
    assert resolve_data_root() == DEFAULT_DATA_ROOT.resolve()


def test_data_paths_layout(data_paths, tmp_path):
    root = (tmp_path / "data_v2").resolve()
    assert data_paths.root == root
    assert data_paths.db_path == root / "enrollment-review-v2.sqlite3"
    assert data_paths.backups_dir == root / "backups"
    assert data_paths.blobs_dir == root / "blobs"
    assert data_paths.migration_lock_path == root / ".migration.lock"


def test_data_paths_ensure_directories(data_paths):
    for directory in (data_paths.root, data_paths.backups_dir, data_paths.blobs_dir):
        assert directory.is_dir()


def test_runtime_version_gate_passes_by_default():
    assert runtime_sqlite_version() >= MIN_SQLITE_VERSION
    verify_sqlite_runtime()


def test_runtime_version_gate_rejects_old_version(monkeypatch):
    monkeypatch.setattr("app.storage.config.sqlite3.sqlite_version_info", (3, 50, 0))
    with pytest.raises(SQLiteRuntimeTooOld) as exc_info:
        verify_sqlite_runtime()
    assert "3.51.3" in str(exc_info.value)


def test_runtime_version_gate_accepts_boundary(monkeypatch):
    verify_sqlite_runtime((3, 51, 3))
    verify_sqlite_runtime((3, 53, 1))
