"""Independent adversarial identity coverage against the live fresh-runtime gate.

Seeds a generic JobStore ``failed_final`` job in a temporary migrated V2 schema.
Never names a real study, protocol, disease, drug, or prior production job_id
as a contiguous literal. Structural pollution must still be rejected when the
contract deny-list is empty.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.agents import protocol_semantic_model_router as router
from app.storage.codecs import encode_value, utc_now
from app.storage.config import resolve_data_paths
from app.storage.db import build_engine, build_session_factory
from app.storage.migrate import MigrationManager
from app.storage.models import ModelConfigRecord
from app.workflow.jobstore import DEFAULT_LEASE_TTL, JobStore
from tests.v2.workflow.conftest import FakeClock, create_job_with_steps
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
)

ROOT = Path(__file__).resolve().parents[2]

_PRODUCTION_SOURCES = (
    ROOT / "app" / "agents" / "protocol_semantic_model_router.py",
    ROOT / "app" / "services" / "protocol_deconstruction_executor.py",
    ROOT / "app" / "config.py",
    ROOT / "tools" / "phase5_acceptance" / "fresh_runtime.py",
    ROOT / "tools" / "phase5_acceptance" / "input_manifest.py",
    ROOT / "tools" / "phase5_acceptance" / "run_packet.py",
)

# Assembled so a naive copy of this list into production still needs joining.
_BANNED_PRODUCTION_TOKENS = (
    "D" + "001",
    "SA" + "R",
    "31" + "001",
    "SA" + "01025",
    "MG-" + "K10",
    "IL-" + "17",
    "EX-" + "06",
    "IN-" + "01",
    "package" + "20",
    "第" + "20包",
    "阿帕" + "替尼",
    "卡瑞" + "利珠",
    "Nivo" + "lumab",
    "Pembro" + "lizumab",
    "重症肌" + "无力",
    "银屑" + "病",
    "FEV" + "1",
    "EC" + "OG",
    "RECI" + "ST",
    "1653" + "540a" + "54c7" + "47e4" + "bc60" + "d94a" + "e65b" + "0b18",
    "3259" + "ab5f" + "0704" + "47c3" + "938f" + "f2de" + "5f45" + "c9cd",
)

_SYNTHETIC_FAILED_JOB_ID = "job-synthetic-failed-final-01"


@pytest.fixture
def v2_identity_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(tmp_path / "data_v2"))
    paths = resolve_data_paths()
    paths.ensure_directories()
    MigrationManager(paths).upgrade("head")
    engine = build_engine(paths.db_path)
    factory = build_session_factory(engine)
    try:
        yield paths, factory, FakeClock()
    finally:
        engine.dispose()


def _store(session_factory, clock):
    class _T:
        def __enter__(self):
            session = session_factory()
            self.session = session
            self.tx = session.begin()
            return JobStore(session, now=clock.now, lease_ttl=DEFAULT_LEASE_TTL)

        def __exit__(self, *exc):
            if exc[0] is None:
                self.tx.commit()
            else:
                self.tx.rollback()
            self.session.close()
            return False

    return _T()


def _seed_model_config(session_factory, *, provider: str, model: str, effort: str) -> None:
    payload_json, payload_sha = encode_value(
        {"provider": provider, "model": model, "reasoning_effort": effort}
    )
    with session_factory() as session:
        with session.begin():
            session.add(
                ModelConfigRecord(
                    model_config_id="mc-synthetic-old-run",
                    provider=provider,
                    model=model,
                    reasoning_effort=effort,
                    payload_json=payload_json,
                    payload_sha256=payload_sha,
                    created_at=utc_now(),
                )
            )


def _seed_failed_final_job(session_factory, clock, job_id: str) -> None:
    create_job_with_steps(
        session_factory,
        clock,
        job_id=job_id,
        job_type="synthetic_acceptance",
        steps=[{"step_id": "generate", "name": "generate", "retryable": False}],
    )
    with _store(session_factory, clock) as store:
        lease = store.claim_job(job_id, "identity-adv-worker")
        assert lease is not None
        store.start_step(lease, "generate")
    with _store(session_factory, clock) as store:
        store.fail_step(
            lease,
            "generate",
            error_code="SYNTHETIC_FATAL",
            retryable=False,
        )


def _write(path: Path, content: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _verified_manifest(tmp_path: Path, label: str = "iso-adv") -> Path:
    payload = b"%PDF-synthetic-isolation"
    relative = "docs/note.pdf"
    destination = tmp_path / "isolated" / label / relative
    _write(destination, payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": "phase5.input_manifest.v1",
        "mode": "copy",
        "label": label,
        "source_immutability": {"verified": True},
        "copy_verification": {"verified": True},
        "summary": {
            "copy_plan_entries": 1,
            "included_files": 1,
            "run_artifact_files": 0,
        },
        "copy_plan": [
            {
                "relative_path": relative,
                "destination_path": str(destination),
                "sha256": digest,
            }
        ],
        "entries": [
            {
                "relative_path": relative,
                "sha256": digest,
                "run_artifact": False,
            }
        ],
    }
    path = tmp_path / f"{label}-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _empty_contract(tmp_path: Path, manifests: list[Path]) -> FreshRuntimeContract:
    payload = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "forbidden_job_ids": [],
        "forbidden_model_identities": [],
        "required_manifests": [str(item) for item in manifests],
        "notes": ["adversarial empty deny-list"],
    }
    path = tmp_path / "empty-deny-contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return FreshRuntimeContract.load(path)


def test_empty_migrated_schema_has_no_pollution_signal(v2_identity_env) -> None:
    paths, _factory, _clock = v2_identity_env
    inspection = inspect_runtime_database(paths.db_path)
    assert inspection["exists"] is True
    assert inspection["job_ids"] == []
    assert inspection["pollution_reasons"] == []
    assert inspection["business_state_counts"] == {}


def test_jobstore_failed_final_is_structural_pollution_without_deny_list(
    v2_identity_env, tmp_path: Path
) -> None:
    paths, factory, clock = v2_identity_env
    _seed_model_config(
        factory,
        provider="mtplx",
        model="old-polluted-model",
        effort="low",
    )
    _seed_failed_final_job(factory, clock, _SYNTHETIC_FAILED_JOB_ID)

    inspection = inspect_runtime_database(paths.db_path)
    assert _SYNTHETIC_FAILED_JOB_ID in inspection["job_ids"]
    reasons = " ".join(inspection["pollution_reasons"])
    assert "database_has_terminal_job" in reasons
    assert "failed_final" in reasons
    assert "database_has_business_state" in reasons
    assert "database_has_model_configs" in reasons

    marker = paths.root / FRESH_MARKER_NAME
    marker.write_text("synthetic-fresh-marker\n", encoding="utf-8")
    contract = _empty_contract(tmp_path, [_verified_manifest(tmp_path)])
    with pytest.raises(FreshRuntimeError, match="身份门禁拒绝") as exc_info:
        validate_runtime_identity(paths.root, contract=contract)
    message = str(exc_info.value)
    assert "failed_final" in message
    assert _SYNTHETIC_FAILED_JOB_ID in message
    # Empty deny-list still blocks: pollution is structural, not named.
    assert contract.forbidden_job_ids == frozenset()


def test_retry_failed_does_not_create_a_new_acceptance_identity(
    v2_identity_env, tmp_path: Path
) -> None:
    paths, factory, clock = v2_identity_env
    _seed_failed_final_job(factory, clock, _SYNTHETIC_FAILED_JOB_ID)
    with _store(factory, clock) as store:
        outcome = store.retry_failed(_SYNTHETIC_FAILED_JOB_ID)
        assert outcome.state == "queued"

    inspection = inspect_runtime_database(paths.db_path)
    assert inspection["job_ids"] == [_SYNTHETIC_FAILED_JOB_ID]
    assert any(
        row["state"] == "queued" for row in inspection["job_states"]
    )
    assert inspection["business_state_counts"].get("jobs") == 1

    (paths.root / FRESH_MARKER_NAME).write_text("marker\n", encoding="utf-8")
    contract = _empty_contract(tmp_path, [_verified_manifest(tmp_path)])
    with pytest.raises(FreshRuntimeError, match="身份门禁拒绝"):
        validate_runtime_identity(paths.root, contract=contract)


def test_model_configs_without_jobs_are_not_old_run_identity(v2_identity_env) -> None:
    paths, factory, _clock = v2_identity_env
    _seed_model_config(
        factory,
        provider="zhipu-coding-plan",
        model="glm-5.3-flash",
        effort="high",
    )
    inspection = inspect_runtime_database(paths.db_path)
    assert inspection["job_ids"] == []
    assert inspection["pollution_reasons"] == []
    identities = inspection["model_identities"]
    assert identities
    assert identities[0]["provider"] == "zhipu-coding-plan"
    assert identities[0]["model"] == "glm-5.3-flash"


def test_prepare_refuses_polluted_root_and_sibling_empty_root_is_accepted(
    v2_identity_env, tmp_path: Path
) -> None:
    paths, factory, clock = v2_identity_env
    _seed_failed_final_job(factory, clock, _SYNTHETIC_FAILED_JOB_ID)
    manifest = _verified_manifest(tmp_path)
    contract = _empty_contract(tmp_path, [manifest])

    with pytest.raises(FreshRuntimeError, match="禁止就地复用或迁移"):
        prepare_fresh_runtime(paths.root, contract=contract)

    sibling = tmp_path / "fresh-sibling"
    result = prepare_fresh_runtime(sibling, contract=contract)
    assert result["ok"] is True
    assert (sibling / FRESH_MARKER_NAME).exists()
    assert not (sibling / DB_FILENAME).exists()
    still_polluted = inspect_runtime_database(paths.db_path)
    assert _SYNTHETIC_FAILED_JOB_ID in still_polluted["job_ids"]


def test_unverified_manifest_and_run_artifact_inputs_are_blocked(tmp_path: Path) -> None:
    destination = tmp_path / "isolated" / "bad" / "docs" / "note.pdf"
    _write(destination, b"%PDF-synthetic")
    unverified = {
        "schema_version": "phase5.input_manifest.v1",
        "mode": "copy",
        "source_immutability": {"verified": False},
        "copy_verification": {"verified": False},
        "summary": {"run_artifact_files": 0},
        "copy_plan": [
            {
                "relative_path": "docs/note.pdf",
                "destination_path": str(destination),
                "sha256": hashlib.sha256(b"%PDF-synthetic").hexdigest(),
            }
        ],
    }
    path = tmp_path / "unverified.json"
    path.write_text(json.dumps(unverified), encoding="utf-8")
    from tools.phase5_acceptance.fresh_runtime import verify_manifest_inputs

    with pytest.raises(FreshRuntimeError, match="源不可变复验"):
        verify_manifest_inputs([path])

    artifact = dict(unverified)
    artifact["source_immutability"] = {"verified": True}
    artifact["copy_verification"] = {"verified": True}
    artifact["summary"] = {"run_artifact_files": 1}
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(FreshRuntimeError, match="运行产物指纹"):
        verify_manifest_inputs([artifact_path])


def test_untrusted_sqlite_missing_jobs_table_does_not_look_fresh(tmp_path: Path) -> None:
    root = tmp_path / "untrusted-root"
    root.mkdir()
    db_path = root / DB_FILENAME
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE notes (id INTEGER)")
        connection.commit()
    finally:
        connection.close()
    inspection = inspect_runtime_database(db_path)
    assert inspection["exists"] is True
    assert inspection["job_ids"] == []
    # Untrusted layout is not a V2 job store; absence of jobs is not acceptance.
    # The prepare gate still refuses any existing sqlite file.
    manifest = _verified_manifest(tmp_path, label="untrusted")
    contract = _empty_contract(tmp_path, [manifest])
    with pytest.raises(FreshRuntimeError, match="已存在"):
        prepare_fresh_runtime(root, contract=contract)


def test_cli_inspect_json_reports_failed_final_and_prepare_creates_empty_sibling(
    v2_identity_env, tmp_path: Path, capsys
) -> None:
    paths, factory, clock = v2_identity_env
    _seed_failed_final_job(factory, clock, _SYNTHETIC_FAILED_JOB_ID)
    manifest = _verified_manifest(tmp_path, label="cli")
    contract = _empty_contract(tmp_path, [manifest])

    inspect_rc = main(["inspect-db", "--db", str(paths.db_path)])
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_rc == 0
    assert inspect_payload["ok"] is True
    assert _SYNTHETIC_FAILED_JOB_ID in inspect_payload["database"]["job_ids"]
    reasons = " ".join(inspect_payload["database"]["pollution_reasons"])
    assert "failed_final" in reasons

    (paths.root / FRESH_MARKER_NAME).write_text("marker\n", encoding="utf-8")
    validate_rc = main(
        [
            "validate",
            "--runtime-root",
            str(paths.root),
            "--contract",
            str(contract.path),
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_rc == 2
    assert validate_payload["ok"] is False
    assert "身份门禁拒绝" in validate_payload["error"]

    sibling = tmp_path / "cli-fresh"
    prepare_rc = main(
        [
            "prepare",
            "--runtime-root",
            str(sibling),
            "--contract",
            str(contract.path),
        ]
    )
    prepare_payload = json.loads(capsys.readouterr().out)
    assert prepare_rc == 0
    assert prepare_payload["ok"] is True
    assert not (sibling / DB_FILENAME).exists()
    assert inspect_runtime_database(paths.db_path)["job_ids"] == [
        _SYNTHETIC_FAILED_JOB_ID
    ]


def test_live_graded_identities_follow_glm_then_mtplx_then_deepseek(monkeypatch) -> None:
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_MODE", "graded")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_COMPLEX", "")
    monkeypatch.setattr(router, "DECONSTRUCT_ROUTE_SHORT", "")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_MODEL", "glm-5.3-flash")
    monkeypatch.setattr(router, "DECONSTRUCT_GLM_REASONING_EFFORT", "high")
    monkeypatch.setattr(router, "MTPLX_MODEL", "mtplx-qwen38-27b-optimized-quality")
    monkeypatch.setattr(router, "MTPLX_REASONING_EFFORT", "medium")
    monkeypatch.setattr(router, "DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setattr(
        router, "DECONSTRUCT_FALLBACK_DEEPSEEK_REASONING_EFFORT", "high"
    )
    from app.agents.protocol_semantic_model_router import (
        GRADE_COMPLEX,
        GRADE_SHORT,
        select_protocol_semantic_route_candidates,
    )

    complex_ids = [
        item.identity for item in select_protocol_semantic_route_candidates(GRADE_COMPLEX)
    ]
    short_ids = [
        item.identity for item in select_protocol_semantic_route_candidates(GRADE_SHORT)
    ]
    assert complex_ids == [
        "zhipu-coding-plan:glm-5.3-flash:high",
        "mtplx:mtplx-qwen38-27b-optimized-quality:medium",
        "deepseek:deepseek-v4-flash:high",
    ]
    assert short_ids == complex_ids[1:]


def test_identity_and_routing_production_sources_have_no_project_literals() -> None:
    for path in _PRODUCTION_SOURCES:
        text = path.read_text(encoding="utf-8")
        for token in _BANNED_PRODUCTION_TOKENS:
            assert token not in text, f"{path} contains banned token {token!r}"
    source = (ROOT / "tools" / "phase5_acceptance" / "fresh_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "failed_final" in source
    assert "job_id" in source
    assert "model_configs" in source
    assert ("Show" + "ing lines") not in source
