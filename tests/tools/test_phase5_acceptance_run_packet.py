"""Representative-subject acceptance run packet tests (Phase 5.8 harness).

Builds one real isolated case through the actual V2 services — seeded Phase 4
evidence chain (blob → document version → snapshot → locators → complete
processing revision), fact normalization run/candidate/gate, transactional
publication, and PatientProfileService projection — then exports the run
packet with ``tools.phase5_acceptance.run_packet`` and checks the five
acceptance anchors plus the failure modes the packet must catch.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    DatePrecision,
    FactGate,
    FactPolarity,
    GateOutcome,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    FactGateResult,
    PartialDateRange,
)
from app.services.fact_publication_service import FactPublicationService
from app.services.patient_profile_service import PatientProfileService
from app.storage.config import DataPaths, resolve_data_paths
from app.storage.db import build_engine, build_session_factory
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.fact_repositories import (
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
)
from app.storage.migrate import MigrationManager
from tests.v2.helpers.phase5_fact_chain import seed_valid_fact_chain
from tools.phase5_acceptance.input_manifest import build_manifest, run_inventory
from tools.phase5_acceptance.run_packet import (
    RUN_PACKET_SCHEMA_VERSION,
    RunPacketError,
    _project_effective_text,
    build_run_packet,
    main as run_packet_main,
    write_run_packet,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def case(tmp_path: Path, monkeypatch) -> dict:
    """One isolated representative-subject case built with real services."""
    isolation_root = tmp_path / "isolation"
    isolation_root.mkdir()
    monkeypatch.setenv("ENROLLMENT_V2_DATA_DIR", str(isolation_root))
    paths: DataPaths = resolve_data_paths()
    paths.ensure_directories()
    MigrationManager(paths).upgrade("head")
    engine = build_engine(paths.db_path)
    try:
        factory = build_session_factory(engine)
        with factory() as session:
            chain = seed_valid_fact_chain(session, prefix="packet")
            locator_row = session.execute(
                select(EvidenceLocatorArtifactRecord).where(
                    EvidenceLocatorArtifactRecord.locator_id == chain["locator_id"]
                )
            ).scalar_one()
            basis = AssertionBasis(
                asserted_object="血压",
                assertion_text="血压 120/80 mmHg",
                locator_id=chain["locator_id"],
                source_text_sha256=locator_row.source_text_sha256,
            )
            FactNormalizationCandidateRepository(session).create(
                "packet-call",
                ClinicalFactCandidateV2(
                    candidate_id="packet-cand",
                    run_id=chain["run_id"],
                    call_id=chain["call_id"],
                    fact_type="vital_sign",
                    polarity=FactPolarity.AFFIRMED,
                    asserted_object="血压",
                    raw_value="120/80",
                    canonical_value="120/80",
                    unit="unitless",
                    date_range=PartialDateRange(
                        precision=DatePrecision.DAY,
                        lower_bound=date(2026, 8, 1),
                        upper_bound=date(2026, 8, 1),
                    ),
                    record_time=NOW,
                    locator_ids=[chain["locator_id"]],
                    candidate_source_semantics="objective_result",
                    assertion_basis=basis,
                    model_uncertainty=0.01,
                    created_at=NOW,
                ),
            )
            FactGateResultRepository(session).create(
                FactGateResult(
                    gate_result_id="packet-gate",
                    run_id=chain["run_id"],
                    call_id=chain["call_id"],
                    candidate_id="packet-cand",
                    gate=FactGate.TRANSACTIONAL_PUBLISH,
                    outcome=GateOutcome.ACCEPTED,
                    reasons=[],
                    created_at=NOW,
                )
            )
            session.commit()
            publication = FactPublicationService().publish(session, chain["run_id"])
            session.commit()
            profile = PatientProfileService().generate(
                session, authority=chain["authority"], generated_at=NOW
            )
            FactGateResultRepository(session).create(
                FactGateResult(
                    gate_result_id="packet-gate-rejected",
                    run_id=chain["run_id"],
                    call_id=chain["call_id"],
                    candidate_id="packet-cand",
                    gate=FactGate.LOCATOR_AND_TEXT_HASH,
                    outcome=GateOutcome.REJECTED,
                    reasons=["引用位置与原文不一致"],
                    created_at=NOW,
                )
            )
            session.commit()
    finally:
        engine.dispose()

    raw_root = tmp_path / "raw_sources" / "PK1"
    raw_root.mkdir(parents=True)
    blob_content = "packet-pdf".encode("utf-8")
    (raw_root / "visit-note.pdf").write_bytes(blob_content)

    manifest = run_inventory(
        [raw_root],
        mode="copy",
        destination=isolation_root / "isolated_sources",
        output=tmp_path / "manifest.json",
        label="representative-subject-packet-test",
        perform_copy=True,
    )
    return {
        "isolation_root": isolation_root,
        "manifest": manifest,
        "manifest_path": tmp_path / "manifest.json",
        "chain": chain,
        "blob_sha256": _sha("packet-pdf"),
        "publication": publication,
        "profile": profile,
        "tmp_path": tmp_path,
    }


def test_packet_records_all_five_acceptance_anchors(case) -> None:
    packet = build_run_packet(
        case["isolation_root"],
        case["manifest"],
        case_labels={"case_id": "opaque-case-label"},
    )
    assert packet["schema_version"] == RUN_PACKET_SCHEMA_VERSION
    assert packet["clinical_acceptance"]["claimed"] is False
    assert packet["packet_disposition"] == "verifiable"
    assert packet["blocking_gaps"] == []

    isolation = packet["isolation"]
    assert isolation["isolation_root"] == str(case["isolation_root"])
    assert isolation["database_opened_read_only"] is True

    fingerprints = packet["source_fingerprints"]
    assert fingerprints["included_files"] == [
        {
            "relative_path": "visit-note.pdf",
            "source_root": fingerprints["included_files"][0]["source_root"],
            "sha256": case["blob_sha256"],
            "size_bytes": len("packet-pdf"),
            "file_type": "pdf",
            "run_artifact": False,
            "run_artifact_reason": None,
        }
    ]
    assert fingerprints["run_artifact_entries"] == []
    assert fingerprints["manifest_source_immutability_verified"] is True
    assert fingerprints["manifest_copy_verification"]["verified"] is True
    assert fingerprints["isolated_copy_recheck"]["verified_ok"] == 1
    assert fingerprints["unused_manifest_files"] == []

    authority = packet["run_authority"]
    chain = case["chain"]
    assert authority["authority_source"] == "patient_profile_revision"
    assert authority["frozen"]["review_episode_id"] == chain["episode_id"]
    assert authority["frozen"]["evidence_snapshot_v2_id"] == chain["snapshot_id"]
    assert (
        authority["frozen"]["complete_processing_revision_id"]
        == chain["complete_revision_id"]
    )
    assert authority["authority_matches_active_pointers"] is True
    assert authority["snapshot"]["collection_sha256"]
    assert authority["complete_processing_revision"]["revision_kind"] == "complete"
    (run_info,) = authority["normalization_runs"]
    assert run_info["run_id"] == chain["run_id"]
    assert run_info["matches_frozen_authority"] is True
    assert run_info["model_name"] == "deterministic-test-transport"

    stats = packet["statistics"]
    assert stats["candidates"]["by_kind"] == {"fact": 1}
    assert stats["gate_results"]["by_outcome"] == {
        "accepted": 1,
        "rejected": 1,
    }
    assert stats["gate_results"]["rejected_or_blocked_reasons_sample"] == [
        "引用位置与原文不一致"
    ]
    assert stats["published"]["facts"] == 1
    assert stats["published"]["events"] == 0
    assert stats["profile"]["latest"]["status"] == "succeeded"
    assert sum(stats["profile"]["lane_item_counts"].values()) >= 1

    checks = packet["per_event_source_checks"]
    fact_checks = [item for item in checks if item["kind"] == "fact"]
    assert len(fact_checks) == 1
    check = fact_checks[0]
    assert check["published_row_present"] is True
    assert check["entity_links_match"] is True
    assert check["clinical_fields"]["polarity"] == "affirmed"
    assert check["verification_instructions"]
    (locator,) = check["locators"]
    assert locator["locator_id"] == chain["locator_id"]
    assert locator["page_number"] == 1
    assert locator["manifest_relative_paths"] == ["visit-note.pdf"]
    assert locator["source_text_sha256"]

    (document,) = packet["documents"]
    assert document["blob_sha256"] == case["blob_sha256"]
    assert document["manifest_matches"][0]["relative_path"] == "visit-note.pdf"


def test_packet_blocks_when_blob_is_not_fingerprinted(case) -> None:
    wrong_root = case["tmp_path"] / "other_sources" / "PK2"
    wrong_root.mkdir(parents=True)
    (wrong_root / "unrelated.pdf").write_bytes(b"other bytes entirely")
    manifest = run_inventory([wrong_root], output=case["tmp_path"] / "wrong.json")

    packet = build_run_packet(case["isolation_root"], manifest)
    codes = {gap["code"] for gap in packet["blocking_gaps"]}
    assert "source_not_fingerprinted" in codes
    assert packet["packet_disposition"] == "blocked"


def test_packet_blocks_when_isolated_copy_drifts(case) -> None:
    drifted = (
        case["isolation_root"]
        / "isolated_sources"
        / "PK1"
        / "visit-note.pdf"
    )
    drifted.write_bytes(b"mutated after copy")
    packet = build_run_packet(case["isolation_root"], case["manifest"])
    codes = {gap["code"] for gap in packet["blocking_gaps"]}
    assert "isolated_copy_hash_mismatch" in codes
    assert packet["packet_disposition"] == "blocked"


def test_packet_detects_tampered_payload(case) -> None:
    db_path = case["isolation_root"] / "enrollment-review-v2.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE clinical_facts_v2 SET payload_json = '{\"tampered\": true}'"
        )
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    codes = {gap["code"] for gap in packet["verification_gaps"]}
    assert "payload_hash_mismatch" in codes
    assert packet["packet_disposition"] == "blocked"


def test_packet_without_profile_reports_gap_but_keeps_authority(case) -> None:
    db_path = case["isolation_root"] / "enrollment-review-v2.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM patient_profile_revisions_v2")
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    codes = {gap["code"] for gap in packet["blocking_gaps"]}
    assert "no_succeeded_profile" in codes
    assert packet["packet_disposition"] == "blocked"
    assert packet["per_event_source_checks"] == []
    # Authority falls back to published entities and statistics stay usable.
    assert packet["run_authority"]["authority_source"] == "published_entities"
    assert packet["statistics"]["published"]["facts"] == 1


def test_empty_run_is_not_a_verifiable_acceptance(case) -> None:
    db_path = case["isolation_root"] / "enrollment-review-v2.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        for table in (
            "patient_profile_revisions_v2",
            "fact_evidence_locator_links",
            "clinical_facts_v2",
            "clinical_events_v2",
            "medication_exposures_v2",
            "clinical_conflict_groups_v2",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    codes = {gap["code"] for gap in packet["blocking_gaps"]}
    assert "no_published_entities" in codes
    assert "no_run_authority" in codes or "no_succeeded_profile" in codes
    assert packet["packet_disposition"] == "blocked"
    assert packet["per_event_source_checks"] == []


def test_manifest_without_entries_is_rejected(case) -> None:
    with pytest.raises(RunPacketError, match="raw file"):
        build_run_packet(case["isolation_root"], {"schema_version": "x"})


def test_missing_database_fails_loudly(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    with pytest.raises(RunPacketError, match="isolated database not found"):
        build_run_packet(empty_root, {"entries": [{"sha256": "0" * 64}]})


def test_multiple_episodes_require_explicit_selection(case) -> None:
    from app.domain.contracts.review import ReviewEpisode
    from app.storage.codecs import encode_contract
    from app.storage.models import ReviewEpisodeRecord

    engine = build_engine(case["isolation_root"] / "enrollment-review-v2.sqlite3")
    try:
        factory = build_session_factory(engine)
        with factory() as session:
            chain = case["chain"]
            second = ReviewEpisode(
                review_episode_id="packet-second-episode",
                subject_id=chain["subject_id"],
                project_id=chain["project_id"],
                rule_set_id=chain["authority"].rule_set_id,
                study_phase="phase_iii",
                stage="screening",
                protocol_version_id=chain["authority"].protocol_version_id,
                rule_set_revision=chain["authority"].rule_set_revision,
            )
            payload_json, payload_sha256 = encode_contract(second)
            session.add(
                ReviewEpisodeRecord(
                    review_episode_id=second.review_episode_id,
                    subject_id=second.subject_id,
                    project_id=second.project_id,
                    rule_set_id=second.rule_set_id,
                    rule_set_revision=second.rule_set_revision,
                    study_phase=second.study_phase,
                    stage=second.stage,
                    protocol_version_id=second.protocol_version_id,
                    evidence_snapshot_id=None,
                    active_evidence_snapshot_id=None,
                    active_evidence_processing_revision_id=None,
                    anchor_dates_json={},
                    due_at=None,
                    payload_json=payload_json,
                    payload_sha256=payload_sha256,
                    revision=1,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.commit()
    finally:
        engine.dispose()

    with pytest.raises(RunPacketError, match="select one explicitly"):
        build_run_packet(case["isolation_root"], case["manifest"])
    packet = build_run_packet(
        case["isolation_root"],
        case["manifest"],
        review_episode_id=case["chain"]["episode_id"],
    )
    assert packet["packet_disposition"] == "verifiable"


def test_cli_writes_packet_json(case, capsys) -> None:
    output = case["tmp_path"] / "packet.json"
    code = run_packet_main(
        [
            "--isolation-root",
            str(case["isolation_root"]),
            "--manifest",
            str(case["manifest_path"]),
            "--case-label",
            "case_id=opaque-1",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["case_labels"] == {"case_id": "opaque-1"}
    assert packet["packet_disposition"] == "verifiable"
    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True
    assert printed["per_event_source_checks"] == 1


# --------------------------------------------------------------------------- repairs
# Worker 03 blocking regressions (T1/T2/T3/T5/T6/T7) plus run-artifact and
# effective-text coherence coverage.


def _db(case) -> sqlite3.Connection:
    return sqlite3.connect(case["isolation_root"] / "enrollment-review-v2.sqlite3")


def _blocking_codes(packet) -> set[str]:
    return {gap["code"] for gap in packet["blocking_gaps"]}


def test_t1_published_row_under_foreign_authority_blocks(case) -> None:
    conn = _db(case)
    try:
        conn.execute(
            "UPDATE clinical_facts_v2 SET evidence_snapshot_v2_id = 'stale-snapshot'"
        )
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert "profile_item_authority_mismatch" in _blocking_codes(packet)
    (check,) = packet["per_event_source_checks"]
    assert check["published_row_present"] is False
    assert packet["packet_disposition"] == "blocked"


def test_t2_deleted_entity_locator_links_block(case) -> None:
    conn = _db(case)
    try:
        conn.execute("DELETE FROM fact_evidence_locator_links")
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert "entity_links_absent" in _blocking_codes(packet)
    (check,) = packet["per_event_source_checks"]
    assert check["entity_links_match"] is False
    assert packet["packet_disposition"] == "blocked"


def test_t3_tampered_excerpt_blocks(case) -> None:
    tampered = "从未出现的原文"
    conn = _db(case)
    try:
        row = conn.execute(
            "SELECT payload_json FROM evidence_locator_artifacts"
            " WHERE locator_id = ?",
            (case["chain"]["locator_id"],),
        ).fetchone()
        payload = json.loads(row[0])
        payload["excerpt"] = tampered
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "UPDATE evidence_locator_artifacts SET excerpt = ?, payload_json = ?,"
            " payload_sha256 = ? WHERE locator_id = ?",
            (
                tampered,
                text,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                case["chain"]["locator_id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    codes = _blocking_codes(packet)
    assert "locator_excerpt_not_in_page_text" in codes
    assert "payload_hash_mismatch" not in codes  # the tamper kept hashes consistent
    assert packet["packet_disposition"] == "blocked"


def test_t5_manifest_mode_manifest_blocks(case) -> None:
    manifest = build_manifest(
        [case["tmp_path"] / "raw_sources" / "PK1"],
        label="manifest-mode-probe",
    )

    packet = build_run_packet(case["isolation_root"], manifest)
    codes = _blocking_codes(packet)
    assert "manifest_not_verified" in codes
    assert "isolated_copies_absent" in codes
    assert packet["packet_disposition"] == "blocked"


def test_t6_copy_destination_outside_isolation_root_blocks(case) -> None:
    outside = case["tmp_path"] / "outside_copies"
    manifest = run_inventory(
        [case["tmp_path"] / "raw_sources" / "PK1"],
        mode="copy",
        destination=outside,
        output=case["tmp_path"] / "outside-manifest.json",
        perform_copy=True,
    )

    packet = build_run_packet(case["isolation_root"], manifest)
    assert "isolated_copy_outside_root" in _blocking_codes(packet)
    recheck = packet["source_fingerprints"]["isolated_copy_recheck"]
    assert recheck["results"][0]["status"] == "outside_isolation_root"
    assert packet["packet_disposition"] == "blocked"


def test_t7_no_matching_normalization_run_blocks(case) -> None:
    conn = _db(case)
    try:
        conn.execute(
            "UPDATE fact_normalization_runs SET episode_revision = episode_revision + 1"
        )
        conn.commit()
    finally:
        conn.close()

    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert "no_normalization_run_matching_authority" in _blocking_codes(packet)
    (run_info,) = packet["run_authority"]["normalization_runs"]
    assert run_info["matches_frozen_authority"] is False
    assert packet["packet_disposition"] == "blocked"


def test_manifest_run_artifacts_are_flagged_and_rejected(case) -> None:
    raw_root = case["tmp_path"] / "polluted_sources" / "PK3"
    raw_root.mkdir(parents=True)
    (raw_root / "visit-note.pdf").write_bytes(b"packet-pdf")
    (raw_root / "prev-run.sqlite3").write_bytes(b"stale database bytes")
    (raw_root / "chat.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
    (raw_root / "old-packet.json").write_text(
        json.dumps({"schema_version": "phase5.run_packet/v1", "case_labels": {}}),
        encoding="utf-8",
    )
    manifest = run_inventory(
        [raw_root],
        mode="copy",
        destination=case["isolation_root"] / "isolated_sources_pk3",
        output=case["tmp_path"] / "polluted-manifest.json",
        perform_copy=True,
    )

    assert manifest["summary"]["run_artifact_files"] == 3
    flagged = {
        entry["relative_path"]: entry["run_artifact_reason"]
        for entry in manifest["entries"]
        if entry["run_artifact"]
    }
    assert set(flagged) == {"prev-run.sqlite3", "chat.jsonl", "old-packet.json"}
    assert "database" in flagged["prev-run.sqlite3"]
    assert "transcript" in flagged["chat.jsonl"]
    assert "prior-run pipeline export" in flagged["old-packet.json"]

    packet = build_run_packet(case["isolation_root"], manifest)
    assert "manifest_contains_run_artifacts" in _blocking_codes(packet)
    rejected = packet["source_fingerprints"]["run_artifact_entries"]
    assert {item["relative_path"] for item in rejected} == set(flagged)
    assert packet["packet_disposition"] == "blocked"


def test_legacy_manifest_without_run_artifact_flags_still_rejects_artifacts(
    case,
) -> None:
    # Manifests produced before run-artifact recording carry no flags; the
    # name-based fallback in the packet must still reject obvious artifacts.
    legacy = {
        "schema_version": "phase5.input_manifest.v1",
        "entries": [
            {
                "relative_path": "visit-note.pdf",
                "source_root": str(case["tmp_path"] / "raw_sources" / "PK1"),
                "sha256": case["blob_sha256"],
                "size_bytes": 10,
                "file_type": "pdf",
                "decision": "include",
                "reason": "included clinical/source document candidate",
            },
            {
                "relative_path": "old/prev-run.sqlite3",
                "source_root": str(case["tmp_path"] / "raw_sources" / "PK1"),
                "sha256": "a" * 64,
                "size_bytes": 9,
                "file_type": "sqlite3",
                "decision": "include",
                "reason": "included clinical/source document candidate",
            },
        ],
        "copy_plan": [],
        "source_immutability": {"verified": True},
    }

    packet = build_run_packet(case["isolation_root"], legacy)
    codes = _blocking_codes(packet)
    assert "manifest_contains_run_artifacts" in codes
    assert "isolated_copies_absent" in codes
    rejected = packet["source_fingerprints"]["run_artifact_entries"]
    assert [item["relative_path"] for item in rejected] == ["old/prev-run.sqlite3"]
    assert packet["packet_disposition"] == "blocked"


def test_effective_text_locator_verified_against_rebuilt_projection(case) -> None:
    db_path = case["isolation_root"] / "enrollment-review-v2.sqlite3"
    locator_id = case["chain"]["locator_id"]

    # A frozen revision with no corrections projects effective text == raw text,
    # so an effective_text locator with the raw hash must stay verifiable.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE evidence_locator_artifacts SET source_layer = 'effective_text',"
            " effective_text_sha256 = source_text_sha256 WHERE locator_id = ?",
            (locator_id,),
        )
        conn.commit()
    finally:
        conn.close()
    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert packet["packet_disposition"] == "verifiable", packet["blocking_gaps"]

    # A wrong projection hash must block.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE evidence_locator_artifacts SET effective_text_sha256 = ?"
            " WHERE locator_id = ?",
            ("f" * 64, locator_id),
        )
        conn.commit()
    finally:
        conn.close()
    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert "locator_source_text_hash_mismatch" in _blocking_codes(packet)
    assert packet["packet_disposition"] == "blocked"


def test_effective_text_projection_with_correction_splice(case) -> None:
    db_path = case["isolation_root"] / "enrollment-review-v2.sqlite3"
    locator_id = case["chain"]["locator_id"]
    frozen_revision = case["chain"]["complete_revision_id"]
    base_revision = case["chain"]["base_revision_id"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ocr_page_id = conn.execute(
            "SELECT ocr_page_id FROM evidence_locator_artifacts WHERE locator_id = ?",
            (locator_id,),
        ).fetchone()["ocr_page_id"]
        raw_text = conn.execute(
            "SELECT raw_text FROM ocr_pages WHERE ocr_page_id = ?", (ocr_page_id,)
        ).fetchone()["raw_text"]
        start, end = 0, 5
        original = raw_text[start:end]
        corrected = original.replace("5", "9")
        assert corrected != original
        correction = {
            "correction_id": "packet-correction-1",
            "ocr_page_id": ocr_page_id,
            "raw_text_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "text_start": start,
            "text_end": end,
            "original_text": original,
            "corrected_text": corrected,
        }
        payload_text = "{}"
        conn.execute(
            "INSERT INTO correction_records (correction_id, ocr_page_id,"
            " raw_text_sha256, text_start, text_end, original_text, corrected_text,"
            " change_kind, requires_confirmation, reason, actor,"
            " base_processing_revision_id, supersedes_correction_id,"
            " affected_scope_json, payload_json, payload_sha256, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'numeric', 0, 'test splice', 'tester',"
            " ?, NULL, '[]', ?, ?, '2026-08-22 12:00:00')",
            (
                correction["correction_id"],
                ocr_page_id,
                correction["raw_text_sha256"],
                start,
                end,
                original,
                corrected,
                base_revision,
                payload_text,
                hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
            ),
        )
        conn.execute(
            "INSERT INTO processing_revision_corrections (revision_id, position,"
            " correction_id) VALUES (?, 1, ?)",
            (frozen_revision, correction["correction_id"]),
        )
        effective, effective_sha = _project_effective_text(raw_text, [correction])
        assert effective == raw_text[:start] + corrected + raw_text[end:]
        conn.execute(
            "UPDATE evidence_locator_artifacts SET source_layer = 'effective_text',"
            " source_text_sha256 = ?, effective_text_sha256 = ? WHERE locator_id = ?",
            (effective_sha, effective_sha, locator_id),
        )
        conn.commit()
    finally:
        conn.close()

    # The excerpt slice no longer matches the corrected projection range, so the
    # packet must block on the excerpt replay; with the excerpt cleared the
    # coherent locator stays verifiable.
    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert "locator_excerpt_not_in_page_text" in _blocking_codes(packet)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE evidence_locator_artifacts SET excerpt = NULL, text_start = NULL,"
            " text_end = NULL WHERE locator_id = ?",
            (locator_id,),
        )
        conn.commit()
    finally:
        conn.close()
    packet = build_run_packet(case["isolation_root"], case["manifest"])
    assert packet["packet_disposition"] == "verifiable", packet["blocking_gaps"]
