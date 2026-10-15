"""Deterministic verification for MTPLX whole-candidate EX-06 acceptance.

No live MTPLX calls. Validates frozen contract, GLM negative evidence,
gate classification semantics, and isolation rules via the shared verifier.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERIFIER_PATH = (
    ROOT
    / "artifacts/phase5-acceptance/20260901/mtplx-whole-candidate-ex06-20260901/deterministic_verifier.py"
)
CONTRACT_PATH = VERIFIER_PATH.parent / "frozen-contract.json"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("mtplx_ex06_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier():
    return _load_verifier()


@pytest.fixture(scope="module")
def contract(verifier):
    return verifier.load_contract(CONTRACT_PATH)


def test_frozen_contract_hashes_match_disk(verifier, contract):
    package_path = verifier.WORKTREE / contract["frozen_source_package_path"]
    assert verifier.sha256_file(package_path) == contract["frozen_source_package_sha256"]
    source_input, _ = verifier.load_frozen_package(contract)
    assert source_input.protocol_file_sha256 == contract["protocol_file_sha256"]


def test_glm_negative_evidence_is_classified_not_accepted(verifier, contract):
    report = verifier.VerificationReport()
    verifier.verify_glm_negative_evidence(contract, report)
    report.finalize()
    assert all(item.passed for item in report.checks)


def test_api_success_without_publishable_gate_is_rejected(verifier, contract):
    run_dir = verifier.WORKTREE / contract["glm_negative_evidence_dir"]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    gate_payload = json.loads((run_dir / "full-gate-result.json").read_text(encoding="utf-8"))
    assert summary["attempt_count"] >= 1
    assert summary["status"] == "rejected"
    assert gate_payload["publishable"] is False


def test_candidate_isolation_detects_glm_contamination(verifier, contract, tmp_path):
    contaminated = tmp_path / "run-live"
    contaminated.mkdir()
    (contaminated / "summary.json").write_text(
        json.dumps(
            {
                "status": "accepted",
                "model": "mtplx-qwen38-27b-optimized-quality",
                "backend": "mtplx",
                "session_id": contract["glm_negative_session_id"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = verifier.VerificationReport()
    verifier.verify_candidate_isolation(contract, report, contaminated)
    report.finalize()
    assert report.checks[0].passed is False
    assert report.checks[0].evidence["cross_model_hits"]


def test_d001_pause_boundary_passes_without_mtplx_run(verifier, contract):
    report = verifier.VerificationReport()
    verifier.verify_d001_pause_boundary(contract, report, None)
    report.finalize()
    assert report.checks[0].passed


def test_pre_mtplx_verification_partial_pass(verifier):
    report = verifier.run_verification(run_dir=None)
    outcomes = {item.check_id: item.passed for item in report.checks}
    assert outcomes["frozen_package_sha256"]
    assert outcomes["glm_negative_runner_rejected"]
    assert outcomes["d001_pause_boundary"]
    assert not outcomes["mtplx_candidate_isolation"]
    assert not outcomes["mtplx_semantic_acceptance"]
