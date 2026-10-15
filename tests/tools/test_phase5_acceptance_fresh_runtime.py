"""Deterministic tests for Phase 5 fresh runtime identity gate.

Uses temporary synthetic trees and sqlite fixtures only. Does not read or
modify external clinical sources.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools.phase5_acceptance.fresh_runtime import (
    CONTRACT_SCHEMA_VERSION,
    DB_FILENAME,
    FRESH_MARKER_NAME,
    FreshRuntimeContract,
    FreshRuntimeError,
    inspect_runtime_database,
    main,
    prepare_fresh_runtime,
    validate_runtime_identity,
    verify_manifest_inputs,
)


def _write(path: Path, content: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _build_verified_manifest(tmp_path: Path, label: str = "iso-a") -> Path:
    source = tmp_path / "source" / label
    destination_root = tmp_path / "isolated" / label
    payload = b"%PDF-fixture-" + label.encode()
    relative = "docs/note.pdf"
    source_file = _write(source / relative, payload)
    destination_file = _write(destination_root / relative, payload)
    digest = _sha(payload)
    manifest = {
        "schema_version": "phase5.input_manifest.v1",
        "mode": "copy",
        "label": label,
        "source_immutability": {"verified": True, "checks": []},
        "copy_verification": {"verified": True, "results": []},
        "summary": {
            "copy_plan_entries": 1,
            "included_files": 1,
            "excluded_files": 0,
            "run_artifact_files": 0,
            "total_files": 1,
        },
        "copy_plan": [
            {
                "relative_path": relative,
                "source_path": str(source_file),
                "destination_path": str(destination_file),
                "sha256": digest,
            }
        ],
        "entries": [],
    }
    path = tmp_path / f"{label}-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _write_contract(
    path: Path,
    *,
    manifests: list[Path],
    forbidden_job_ids: list[str] | None = None,
    forbidden_model_identities: list[dict[str, str]] | None = None,
) -> Path:
    payload = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "forbidden_job_ids": forbidden_job_ids or [],
        "forbidden_model_identities": forbidden_model_identities or [],
        "required_manifests": [str(item) for item in manifests],
        "notes": ["synthetic test contract"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _create_polluted_db(
    db_path: Path,
    *,
    job_id: str = "old-job-1",
    state: str = "failed_final",
    provider: str = "mtplx",
    model: str = "mtplx-qwen38-27b-optimized-quality",
    effort: str = "medium",
) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT,
                state TEXT,
                error_code TEXT
            );
            CREATE TABLE model_configs (
                model_config_id TEXT PRIMARY KEY,
                provider TEXT,
                model TEXT,
                reasoning_effort TEXT
            );
            CREATE TABLE job_steps (
                job_id TEXT,
                step_id TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO jobs(job_id, job_type, state, error_code) VALUES (?,?,?,?)",
            (job_id, "protocol_deconstruction", state, "SEMANTIC_DRAFT_MISSING"),
        )
        connection.execute(
            "INSERT INTO model_configs(model_config_id, provider, model, reasoning_effort) "
            "VALUES (?,?,?,?)",
            ("mc-1", provider, model, effort),
        )
        connection.execute(
            "INSERT INTO job_steps(job_id, step_id) VALUES (?,?)",
            (job_id, "generate_draft"),
        )
        connection.commit()
    finally:
        connection.close()
    return db_path


def _create_configured_empty_db(db_path: Path) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                state TEXT,
                error_code TEXT
            );
            CREATE TABLE model_configs (
                model_config_id TEXT PRIMARY KEY,
                provider TEXT,
                model TEXT,
                reasoning_effort TEXT
            );
            CREATE TABLE prompt_versions (
                prompt_version_id TEXT PRIMARY KEY
            );
            """
        )
        connection.execute(
            "INSERT INTO model_configs(model_config_id, provider, model, reasoning_effort) "
            "VALUES (?,?,?,?)",
            ("mc-new", "zhipu-coding-plan", "glm-5.3-flash", "high"),
        )
        connection.execute(
            "INSERT INTO prompt_versions(prompt_version_id) VALUES (?)",
            ("prompt-new",),
        )
        connection.commit()
    finally:
        connection.close()
    return db_path


def test_verify_manifest_inputs_rejects_hash_drift(tmp_path: Path) -> None:
    manifest_path = _build_verified_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination = Path(payload["copy_plan"][0]["destination_path"])
    destination.write_bytes(b"%PDF-tampered")
    with pytest.raises(FreshRuntimeError, match="隔离输入哈希复验失败"):
        verify_manifest_inputs([manifest_path])


def test_prepare_fresh_runtime_writes_marker_and_refuses_existing_db(
    tmp_path: Path,
) -> None:
    manifest = _build_verified_manifest(tmp_path)
    contract = FreshRuntimeContract.load(
        _write_contract(
            tmp_path / "contract.json",
            manifests=[manifest],
            forbidden_job_ids=["old-job-1"],
            forbidden_model_identities=[
                {
                    "provider": "mtplx",
                    "model": "mtplx-qwen38-27b-optimized-quality",
                    "reasoning_effort": "medium",
                }
            ],
        )
    )
    runtime_root = tmp_path / "runtime-fresh"
    result = prepare_fresh_runtime(runtime_root, contract=contract)
    assert result["ok"] is True
    assert (runtime_root / FRESH_MARKER_NAME).exists()
    assert not (runtime_root / DB_FILENAME).exists()
    assert result["validation"]["ok"] is True

    polluted = tmp_path / "runtime-polluted"
    _create_polluted_db(polluted / DB_FILENAME)
    with pytest.raises(FreshRuntimeError, match="禁止就地复用或迁移"):
        prepare_fresh_runtime(polluted, contract=contract)


def test_validate_rejects_old_job_model_and_business_state(tmp_path: Path) -> None:
    manifest = _build_verified_manifest(tmp_path)
    contract = FreshRuntimeContract.load(
        _write_contract(
            tmp_path / "contract.json",
            manifests=[manifest],
            forbidden_job_ids=["1653540a54c747e4bc60d94ae65b0b18"],
            forbidden_model_identities=[
                {
                    "provider": "mtplx",
                    "model": "mtplx-qwen38-27b-optimized-quality",
                    "reasoning_effort": "medium",
                }
            ],
        )
    )
    runtime_root = tmp_path / "runtime-old"
    _write(runtime_root / FRESH_MARKER_NAME, "marker\n")
    _create_polluted_db(
        runtime_root / DB_FILENAME,
        job_id="1653540a54c747e4bc60d94ae65b0b18",
    )
    with pytest.raises(FreshRuntimeError, match="身份门禁拒绝"):
        validate_runtime_identity(runtime_root, contract=contract)
    inspection = inspect_runtime_database(runtime_root / DB_FILENAME)
    assert "1653540a54c747e4bc60d94ae65b0b18" in inspection["job_ids"]
    assert inspection["business_state_counts"]["jobs"] == 1
    assert inspection["model_identities"][0]["provider"] == "mtplx"


def test_validate_accepts_empty_marked_runtime_with_verified_manifests(
    tmp_path: Path,
) -> None:
    manifest = _build_verified_manifest(tmp_path, label="iso-b")
    runtime_root = tmp_path / "runtime-ok"
    prepare_fresh_runtime(
        runtime_root,
        contract=FreshRuntimeContract.load(
            _write_contract(tmp_path / "contract.json", manifests=[manifest])
        ),
    )
    report = validate_runtime_identity(
        runtime_root,
        contract=FreshRuntimeContract.load(
            _write_contract(tmp_path / "contract.json", manifests=[manifest])
        ),
    )
    assert report["ok"] is True
    assert report["database"]["exists"] is False
    assert report["manifests"]["verified"] is True


def test_validate_accepts_newly_migrated_config_before_first_job(tmp_path: Path) -> None:
    manifest = _build_verified_manifest(tmp_path, label="iso-configured")
    contract = FreshRuntimeContract.load(
        _write_contract(tmp_path / "contract.json", manifests=[manifest])
    )
    runtime_root = tmp_path / "runtime-configured"
    _write(runtime_root / FRESH_MARKER_NAME, "marker\n")
    _create_configured_empty_db(runtime_root / DB_FILENAME)

    report = validate_runtime_identity(runtime_root, contract=contract)

    assert report["ok"] is True
    assert report["database"]["job_ids"] == []
    assert report["database"]["configuration_state_counts"] == {
        "model_configs": 1,
        "prompt_versions": 1,
    }
    assert report["database"]["pollution_reasons"] == []


def test_cli_inspect_and_validate_polluted_db(tmp_path: Path, capsys) -> None:
    manifest = _build_verified_manifest(tmp_path)
    contract_path = _write_contract(
        tmp_path / "contract.json",
        manifests=[manifest],
        forbidden_job_ids=["old-job-1"],
    )
    polluted_root = tmp_path / "polluted"
    _write(polluted_root / FRESH_MARKER_NAME, "marker\n")
    db_path = _create_polluted_db(polluted_root / DB_FILENAME)

    assert main(["inspect-db", "--db", str(db_path)]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["ok"] is True
    assert inspect_payload["database"]["job_ids"] == ["old-job-1"]

    assert (
        main(
            [
                "validate",
                "--runtime-root",
                str(polluted_root),
                "--contract",
                str(contract_path),
            ]
        )
        == 2
    )
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is False
    assert "身份门禁拒绝" in validate_payload["error"]
