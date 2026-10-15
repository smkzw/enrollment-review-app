"""Tests for Phase 5 acceptance ledger and case structural verifier."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jsonschema
import pytest

from tools.phase5_acceptance.ledger import (
    ACCEPTANCE_CRITERIA,
    CRITERION_IDS,
    EVIDENCE_CLASSES,
    SCHEMA_VERSION,
    CaseIdentity,
    CaseStructuralVerifier,
    EvidenceItem,
    LedgerValidationError,
    build_empty_ledger,
    evaluate_ledger,
    iter_required_manual_or_tester_gaps,
    ledger_schema_path,
    overall_pass_allowed,
    record_evidence,
    validate_ledger_document,
)

STAMP = "2026-08-23T15:00:00+00:00"


def _item(
    evidence_class: str,
    *,
    disposition: str = "pass",
    locator: str = "artifact://test",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_class=evidence_class,
        source_locator=locator,
        artifact="tests/tools/test_phase5_acceptance_ledger.py",
        observed_result=f"{evidence_class}:{disposition}",
        verifier="pytest",
        timestamp=STAMP,
        disposition=disposition,
    )


def _fill_all_required(
    ledger: dict,
    *,
    include_clinical: bool = True,
    include_tester: bool = True,
    include_advisory: bool = True,
    include_deterministic: bool = True,
) -> dict:
    updated = ledger
    for criterion_id, meta in ACCEPTANCE_CRITERIA.items():
        for cls in meta["required_evidence_classes"]:
            if cls == "deterministic" and not include_deterministic:
                continue
            if cls == "clinical_manual" and not include_clinical:
                continue
            if cls == "browser_tester" and not include_tester:
                continue
            if cls == "conference_advisory" and not include_advisory:
                continue
            updated = record_evidence(
                updated,
                criterion_id,
                _item(cls),
                evaluated_at=STAMP,
            )
    return updated


def test_empty_ledger_enumerates_all_thirteen_criteria() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="case-skeleton"), evaluated_at=STAMP)
    assert ledger["schema_version"] == SCHEMA_VERSION
    assert [row["criterion_id"] for row in ledger["criteria"]] == list(CRITERION_IDS)
    assert len(ledger["criteria"]) == 13
    for row in ledger["criteria"]:
        assert row["evidence"] == []
        assert row["criterion_disposition"] == "not_run"
        assert row["required_evidence_classes"] == list(
            ACCEPTANCE_CRITERIA[row["criterion_id"]]["required_evidence_classes"]
        )
    assert ledger["overall"]["disposition"] == "not_run"
    assert ledger["overall"]["deterministic_all_green"] is False
    assert ledger["case"]["fabricated"] is False


def test_schema_validates_empty_ledger() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="case-schema"), evaluated_at=STAMP)
    schema = json.loads(ledger_schema_path().read_text(encoding="utf-8"))
    jsonschema.validate(instance=ledger, schema=schema)


def test_evidence_classes_are_exactly_the_four_required() -> None:
    assert EVIDENCE_CLASSES == (
        "deterministic",
        "clinical_manual",
        "browser_tester",
        "conference_advisory",
    )


def test_fabricated_case_identity_rejected() -> None:
    with pytest.raises(LedgerValidationError, match="fabricated"):
        CaseIdentity(case_id="x", fabricated=True).to_dict()
    with pytest.raises(LedgerValidationError, match="fabricated"):
        build_empty_ledger(CaseIdentity(case_id="x", fabricated=True))


def test_deterministic_green_alone_cannot_overall_pass() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="auto-only"), evaluated_at=STAMP)
    ledger = _fill_all_required(
        ledger,
        include_clinical=False,
        include_tester=False,
        include_advisory=False,
        include_deterministic=True,
    )
    assert ledger["overall"]["deterministic_all_green"] is True
    assert ledger["overall"]["clinical_manual_complete"] is False
    assert ledger["overall"]["browser_tester_complete"] is False
    assert ledger["overall"]["disposition"] != "pass"
    reasons = " ".join(ledger["overall"]["blocking_reasons"])
    assert "clinical_manual" in reasons
    assert "browser_tester" in reasons
    assert overall_pass_allowed(ledger) is False
    gaps = list(iter_required_manual_or_tester_gaps(ledger))
    assert ("P5-AC12", "clinical_manual") in gaps
    assert ("P5-AC13", "browser_tester") in gaps


def test_conference_advisory_cannot_substitute_for_tester_or_clinical() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="advisory-trap"), evaluated_at=STAMP)
    for criterion_id, meta in ACCEPTANCE_CRITERIA.items():
        for cls in meta["required_evidence_classes"]:
            if cls == "deterministic":
                ledger = record_evidence(
                    ledger, criterion_id, _item("deterministic"), evaluated_at=STAMP
                )
        ledger = record_evidence(
            ledger,
            criterion_id,
            _item("conference_advisory", disposition="advisory"),
            evaluated_at=STAMP,
        )
    assert ledger["overall"]["disposition"] != "pass"
    assert ledger["overall"]["clinical_manual_complete"] is False
    assert ledger["overall"]["browser_tester_complete"] is False
    ac13 = next(row for row in ledger["criteria"] if row["criterion_id"] == "P5-AC13")
    assert ac13["criterion_disposition"] != "pass"
    assert any("browser_tester" in reason for reason in ac13["blocking_reasons"])


def test_observed_only_does_not_count_as_clinical_pass() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="observed"), evaluated_at=STAMP)
    ledger = record_evidence(
        ledger,
        "P5-AC12",
        _item("clinical_manual", disposition="observed_only"),
        evaluated_at=STAMP,
    )
    ac12 = next(row for row in ledger["criteria"] if row["criterion_id"] == "P5-AC12")
    assert ac12["criterion_disposition"] != "pass"
    assert "missing required evidence_class=clinical_manual" in ac12["blocking_reasons"]


def test_full_required_evidence_allows_overall_pass() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="complete"), evaluated_at=STAMP)
    ledger = _fill_all_required(ledger)
    assert ledger["overall"]["disposition"] == "pass"
    assert ledger["overall"]["deterministic_all_green"] is True
    assert ledger["overall"]["clinical_manual_complete"] is True
    assert ledger["overall"]["browser_tester_complete"] is True
    assert ledger["overall"]["conference_advisory_present"] is True
    assert ledger["overall"]["blocking_reasons"] == []
    assert overall_pass_allowed(ledger) is True
    schema = json.loads(ledger_schema_path().read_text(encoding="utf-8"))
    jsonschema.validate(instance=ledger, schema=schema)


def test_fail_evidence_fails_criterion_and_overall() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="fail-case"), evaluated_at=STAMP)
    ledger = _fill_all_required(ledger)
    ledger = record_evidence(
        ledger,
        "P5-AC05",
        _item("deterministic", disposition="fail", locator="pytest://ac05"),
        evaluated_at=STAMP,
    )
    ac05 = next(row for row in ledger["criteria"] if row["criterion_id"] == "P5-AC05")
    assert ac05["criterion_disposition"] == "fail"
    assert ledger["overall"]["disposition"] == "fail"


def test_missing_criterion_rejected() -> None:
    ledger = build_empty_ledger(CaseIdentity(case_id="truncate"), evaluated_at=STAMP)
    ledger["criteria"] = ledger["criteria"][:12]
    errors = validate_ledger_document(ledger)
    assert any("missing criteria" in err or "13" in err for err in errors)
    with pytest.raises(LedgerValidationError):
        evaluate_ledger(ledger)


def test_advisory_disposition_only_for_conference_class() -> None:
    with pytest.raises(LedgerValidationError, match="advisory"):
        EvidenceItem(
            evidence_class="deterministic",
            source_locator="x",
            artifact="y",
            observed_result="z",
            verifier="t",
            timestamp=STAMP,
            disposition="advisory",
        )


def test_evidence_requires_locator_artifact_result_verifier_timestamp() -> None:
    with pytest.raises(LedgerValidationError, match="source_locator"):
        EvidenceItem(
            evidence_class="deterministic",
            source_locator=" ",
            artifact="a",
            observed_result="r",
            verifier="v",
            timestamp=STAMP,
            disposition="pass",
        )


def _build_minimal_case_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE clinical_facts_v2 (
              fact_id TEXT PRIMARY KEY,
              project_id TEXT,
              subject_id TEXT,
              review_episode_id TEXT,
              evidence_snapshot_v2_id TEXT,
              complete_processing_revision_id TEXT
            );
            CREATE TABLE fact_evidence_locator_links (
              entity_kind TEXT,
              entity_id TEXT,
              locator_id TEXT
            );
            CREATE TABLE evidence_locator_artifacts (
              locator_id TEXT PRIMARY KEY,
              relative_path TEXT
            );
            CREATE TABLE evidence_snapshots_v2 (
              evidence_snapshot_id TEXT PRIMARY KEY
            );
            CREATE TABLE evidence_processing_revisions (
              revision_id TEXT PRIMARY KEY
            );
            CREATE TABLE clinical_facts (
              fact_id TEXT PRIMARY KEY
            );
            INSERT INTO clinical_facts_v2 VALUES
              ('f1', 'proj', 'subj', 'ep1', 'snap1', 'cpr1');
            INSERT INTO evidence_locator_artifacts VALUES
              ('loc1', 'docs/a.pdf');
            INSERT INTO fact_evidence_locator_links VALUES
              ('fact', 'f1', 'loc1');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_case_structural_verifier_db_file_locator_checks(tmp_path: Path) -> None:
    db_path = tmp_path / "case.sqlite3"
    file_root = tmp_path / "files"
    file_root.mkdir()
    (file_root / "docs").mkdir()
    (file_root / "docs" / "a.pdf").write_bytes(b"%PDF-fake")
    _build_minimal_case_db(db_path)

    verifier = CaseStructuralVerifier(
        database_path=db_path,
        file_root=file_root,
        project_id="proj",
        subject_id="subj",
    )
    observations = verifier.verify()
    by_id = {obs.check_id: obs for obs in observations}
    assert by_id["db_present"].disposition == "pass"
    assert by_id["fact_authority_complete"].disposition == "pass"
    assert by_id["locator_link_closure"].disposition == "pass"
    assert by_id["source_file_paths"].disposition == "pass"
    assert by_id["legacy_clinical_facts_present"].disposition == "observed_only"
    assert "clinical correctness" in by_id["fact_authority_complete"].as_evidence(
        verifier="test"
    ).notes

    ledger = build_empty_ledger(CaseIdentity(case_id="struct"), evaluated_at=STAMP)
    ledger = verifier.attach_to_ledger(ledger, timestamp=STAMP)
    ac01 = next(row for row in ledger["criteria"] if row["criterion_id"] == "P5-AC01")
    assert any(item["evidence_class"] == "deterministic" for item in ac01["evidence"])
    # Structural attach must not satisfy clinical_manual.
    assert ac01["criterion_disposition"] != "pass"
    assert ledger["overall"]["disposition"] != "pass"


def test_case_structural_verifier_missing_db_is_blocked(tmp_path: Path) -> None:
    verifier = CaseStructuralVerifier(database_path=tmp_path / "missing.sqlite3")
    observations = verifier.verify()
    assert observations[0].check_id == "db_present"
    assert observations[0].disposition == "blocked"


def test_case_structural_verifier_does_not_fabricate_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-scope.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE clinical_facts_v2 (
              fact_id TEXT PRIMARY KEY,
              project_id TEXT,
              subject_id TEXT,
              review_episode_id TEXT,
              evidence_snapshot_v2_id TEXT,
              complete_processing_revision_id TEXT
            );
            CREATE TABLE fact_evidence_locator_links (
              entity_kind TEXT, entity_id TEXT, locator_id TEXT
            );
            CREATE TABLE evidence_locator_artifacts (
              locator_id TEXT PRIMARY KEY
            );
            CREATE TABLE evidence_snapshots_v2 (evidence_snapshot_id TEXT PRIMARY KEY);
            CREATE TABLE evidence_processing_revisions (revision_id TEXT PRIMARY KEY);
            """
        )
        conn.commit()
    finally:
        conn.close()
    verifier = CaseStructuralVerifier(
        database_path=db_path, project_id="proj", subject_id="missing-subject"
    )
    observations = verifier.verify()
    authority = next(obs for obs in observations if obs.check_id == "fact_authority_rows")
    assert authority.disposition == "blocked"
    assert "not fabricating" in authority.observed_result
