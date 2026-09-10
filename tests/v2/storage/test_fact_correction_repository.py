"""Phase 5 Slice 5.7 人工事实修订仓储确定性测试（worker_01 重制）。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.domain.contracts.enums import (
    DatePrecision,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    ProfileLane,
    SourceStrength,
)
from app.domain.contracts.fact_corrections import (
    FactCorrectionImpactScope,
    FactCorrectionV2,
    canonical_json,
    event_semantic_snapshot,
    exposure_semantic_snapshot,
    fact_correction_idempotency_key,
    fact_semantic_snapshot,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    PartialDateRange,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    fact_run_idempotency_key,
    medication_exposure_stable_identity,
)
from app.storage.fact_authority import FactAuthorityError, FactLocatorReferenceError
from app.storage.fact_correction_repository import (
    FactCorrectionRepository,
    FactCorrectionRevisionError,
)
from app.storage.fact_repositories import (
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationCallRepository,
    FactNormalizationRunRepository,
    MedicationExposureV2Repository,
)
from app.storage.facts_models import (
    FactCorrectionRecord,
    PatientProfileRevisionV2Record,
)
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.storage.repositories import InvalidReferenceError, RepositoryError
from tests.v2.storage.test_fact_repositories import (
    _event as _seed_event,
    _exposure as _seed_exposure,
    _fact as _seed_fact,
    _seed_chain as _seed_storage_chain,
)
from tests.v2.storage.test_patient_profile_repository import _revision as _profile_revision

UTC_NOW = datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC)
NOW = UTC_NOW


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_valid_chain(session, prefix: str, fixture_index: int = 0) -> dict:
    return _seed_storage_chain(session, prefix, fixture_index=fixture_index)


def _create_fact_with_candidate(session, seed: dict, fact_id: str, run_id: str, call_id: str, gate_id: str, cand_id: str, *, value: str = "120/80", asserted_object: str = "血压", assertion_text: str | None = None, revision: int = 1) -> ClinicalFactV2:
    authority = seed["authority"]
    # The storage seed already owns one run/call/fact candidate/gate for the
    # same prefix; publish corrections need a second real upstream chain.
    if run_id == seed["run_id"]:
        run_id = f"{run_id}-publish"
    if call_id == seed["call_id"]:
        call_id = f"{call_id}-publish"
    if gate_id in {seed["gate_id"], seed["event_gate_id"], seed["exposure_gate_id"]}:
        gate_id = f"{gate_id}-publish"
    if cand_id == seed["fact_candidate_id"]:
        cand_id = f"{cand_id}-publish"
    # 创建运行/调用/候选/门禁，要求候选语义与事实语义完全一致
    run = FactNormalizationRun(run_id=run_id, authority=authority, idempotency_key=fact_run_idempotency_key(authority=authority, prompt_version_id=seed["prompt_version_id"], model_config_id=seed["model_config_id"], input_scope_sha256=_sha(f"{run_id}-input-scope")), prompt_version_id=seed["prompt_version_id"], model_config_id=seed["model_config_id"], input_scope_sha256=_sha(f"{run_id}-input-scope"), status=FactNormalizationRunStatus.SUCCEEDED, created_at=NOW, created_by="tester")
    FactNormalizationRunRepository(session).create_or_reuse(run)
    FactNormalizationCallRepository(session).create(FactNormalizationCall(call_id=call_id, run_id=run_id, logical_document_id=seed["logical_document_id"], page_numbers=[1], status=FactCallStatus.SUCCEEDED, input_sha256=_sha(f"{call_id}-input"), created_at=NOW))
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from app.storage.codecs import decode_contract
    from app.domain.contracts.evidence_locator import EvidenceLocatorArtifact
    loc_rec = session.get(EvidenceLocatorArtifactRecord, seed["locator_id"])
    loc_contract = decode_contract(EvidenceLocatorArtifact, loc_rec.payload_json, loc_rec.payload_sha256)
    basis = AssertionBasis(asserted_object=asserted_object, assertion_text=assertion_text or loc_contract.excerpt, locator_id=seed["locator_id"], source_text_sha256=loc_contract.source_text_sha256)
    date_range = PartialDateRange(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound="2026-03-01", upper_bound="2026-03-01")
    FactNormalizationCandidateRepository(session).create(call_id, ClinicalFactCandidateV2(candidate_id=cand_id, run_id=run_id, call_id=call_id, fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object=asserted_object, raw_value=value, canonical_value=value, unit="unitless", date_range=date_range, record_time=NOW, locator_ids=[seed["locator_id"]], candidate_source_semantics="objective_result", assertion_basis=basis, model_uncertainty=0.01, created_at=NOW))
    FactGateResultRepository(session).create(FactGateResult(gate_result_id=gate_id, run_id=run_id, call_id=call_id, candidate_id=cand_id, gate=FactGate.TRANSACTIONAL_PUBLISH, outcome=GateOutcome.ACCEPTED, reasons=[], created_at=NOW))
    # 创建事实，语义与候选完全一致
    stable = clinical_fact_stable_identity(authority=authority, fact_type="vital_sign", asserted_object=asserted_object, polarity=FactPolarity.AFFIRMED, value=value, unit="unitless", date_range=date_range, profile_lane=ProfileLane.EVIDENCE_QUALITY)
    fact = ClinicalFactV2(fact_id=fact_id, run_id=run_id, gate_id=gate_id, source_candidate_ids=[], gate_ids=[gate_id], authority=authority, fact_type="vital_sign", profile_lane=ProfileLane.EVIDENCE_QUALITY, supported_requirement_ids=[], polarity=FactPolarity.AFFIRMED, asserted_object=asserted_object, value=value, unit="unitless", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE, date_range=date_range, record_time=NOW, locator_ids=[seed["locator_id"]], assertion_basis=basis, stable_identity=stable, revision=revision, created_at=UTC_NOW)
    ClinicalFactV2Repository(session).create(fact)
    return fact


def _correction_for_facts(
    old_fact: ClinicalFactV2,
    new_fact: ClinicalFactV2,
    locator_ids: list[str],
    *,
    correction_id: str = "corr-1",
    reason: str = "核对原文第3页，旧值录入错误",
    operator_id: str = "op-1",
    impact_scope: FactCorrectionImpactScope | None = None,
) -> FactCorrectionV2:
    old_snap = fact_semantic_snapshot(old_fact)
    new_snap = fact_semantic_snapshot(new_fact)
    old_json = canonical_json(old_snap)
    new_json = canonical_json(new_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    new_sha = hashlib.sha256(new_json.encode()).hexdigest()
    id_key = fact_correction_idempotency_key(authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_stable_identity=new_fact.stable_identity, new_revision=new_fact.revision, old_snapshot_sha256=old_sha, new_snapshot_sha256=new_sha, reason=reason, locator_ids=locator_ids, operator_id=operator_id)
    return FactCorrectionV2(correction_id=correction_id, authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, new_stable_identity=new_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_revision=new_fact.revision, old_snapshot_json=old_json, old_snapshot_sha256=old_sha, new_snapshot_json=new_json, new_snapshot_sha256=new_sha, reason=reason, locator_ids=locator_ids, operator_id=operator_id, corrected_at=UTC_NOW, created_at=UTC_NOW, impact_scope=impact_scope or FactCorrectionImpactScope(scope_kind="local", affected_locator_ids=sorted(locator_ids), affected_fact_ids=[old_fact.fact_id]), idempotency_key=id_key)


def _correction_for_entities(
    old_entity,
    new_entity,
    target_kind: str,
    snapshotter,
    locator_ids: list[str],
    *,
    correction_id: str,
    reason: str,
    operator_id: str = "op-1",
) -> FactCorrectionV2:
    id_field = {"fact": "fact_id", "event": "event_id", "exposure": "exposure_id"}[target_kind]
    old_id = getattr(old_entity, id_field)
    new_id = getattr(new_entity, id_field)
    old_json = canonical_json(snapshotter(old_entity))
    new_json = canonical_json(snapshotter(new_entity))
    old_sha = _sha(old_json)
    new_sha = _sha(new_json)
    locator_ids = sorted(locator_ids)
    id_key = fact_correction_idempotency_key(
        authority=old_entity.authority,
        target_kind=target_kind,
        target_id=old_id,
        target_stable_identity=old_entity.stable_identity,
        target_revision=old_entity.revision,
        new_entity_id=new_id,
        new_stable_identity=new_entity.stable_identity,
        new_revision=new_entity.revision,
        old_snapshot_sha256=old_sha,
        new_snapshot_sha256=new_sha,
        reason=reason,
        locator_ids=locator_ids,
        operator_id=operator_id,
    )
    affected_field = {
        "fact": "affected_fact_ids",
        "event": "affected_event_ids",
        "exposure": "affected_exposure_ids",
    }[target_kind]
    impact_values = {
        "scope_kind": "local",
        "affected_locator_ids": locator_ids,
        affected_field: [old_id],
    }
    return FactCorrectionV2(
        correction_id=correction_id,
        authority=old_entity.authority,
        target_kind=target_kind,
        target_id=old_id,
        target_stable_identity=old_entity.stable_identity,
        target_revision=old_entity.revision,
        new_entity_id=new_id,
        new_stable_identity=new_entity.stable_identity,
        new_revision=new_entity.revision,
        old_snapshot_json=old_json,
        old_snapshot_sha256=old_sha,
        new_snapshot_json=new_json,
        new_snapshot_sha256=new_sha,
        reason=reason,
        locator_ids=locator_ids,
        operator_id=operator_id,
        corrected_at=UTC_NOW,
        created_at=UTC_NOW,
        impact_scope=FactCorrectionImpactScope(**impact_values),
        idempotency_key=id_key,
    )


def _add_candidate_and_gate(session, seed: dict, candidate, gate_id: str) -> None:
    FactNormalizationCandidateRepository(session).create(seed["call_id"], candidate)
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=seed["run_id"],
            call_id=seed["call_id"],
            candidate_id=candidate.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )


def test_fact_correction_create_and_get_roundtrip_with_both_entities(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57a")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-1", "s57a-run", "s57a-call", "s57a-gate", "s57a-cand", value="120/80", revision=1)
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-1", "s57a-run2", "s57a-call2", "s57a-gate2", "s57a-cand2", value="无", revision=1)
    session.commit()
    corr = _correction_for_facts(old_fact, new_fact, [seed["locator_id"]])
    repo = FactCorrectionRepository(session)
    created = repo.create(corr)
    assert created.correction_id == "corr-1"
    fetched = repo.get("corr-1")
    assert fetched == created
    assert ClinicalFactV2Repository(session).get("fact-old-1").revision == 1
    assert ClinicalFactV2Repository(session).get("fact-new-1").revision == 1
    assert fetched.old_snapshot_json == canonical_json(fact_semantic_snapshot(old_fact))
    assert fetched.new_snapshot_json == canonical_json(fact_semantic_snapshot(new_fact))
    assert "supported_requirement_ids" in json.loads(fetched.old_snapshot_json)
    row = session.execute(select(FactCorrectionRecord).where(FactCorrectionRecord.correction_id == "corr-1")).scalar_one()
    assert row.payload_sha256 == hashlib.sha256(row.payload_json.encode()).hexdigest()
    session.close()


def test_correction_rejects_snapshot_omitting_supported_requirement_ids(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57req")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-req", "s57req-run", "s57req-call", "s57req-gate", "s57req-cand", value="120/80", revision=1)
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-req", "s57req-run2", "s57req-call2", "s57req-gate2", "s57req-cand2", value="无", revision=1)
    session.commit()
    corr = _correction_for_facts(old_fact, new_fact, [seed["locator_id"]], correction_id="corr-req")
    stripped = json.loads(corr.new_snapshot_json)
    stripped.pop("supported_requirement_ids")
    stripped_json = canonical_json(stripped)
    stripped_sha = hashlib.sha256(stripped_json.encode()).hexdigest()
    id_key = fact_correction_idempotency_key(
        authority=corr.authority,
        target_kind=corr.target_kind,
        target_id=corr.target_id,
        target_stable_identity=corr.target_stable_identity,
        target_revision=corr.target_revision,
        new_entity_id=corr.new_entity_id,
        new_stable_identity=corr.new_stable_identity,
        new_revision=corr.new_revision,
        old_snapshot_sha256=corr.old_snapshot_sha256,
        new_snapshot_sha256=stripped_sha,
        reason=corr.reason,
        locator_ids=corr.locator_ids,
        operator_id=corr.operator_id,
    )
    tampered = corr.model_copy(
        update={
            "new_snapshot_json": stripped_json,
            "new_snapshot_sha256": stripped_sha,
            "idempotency_key": id_key,
        }
    )
    with pytest.raises(RepositoryError, match="新快照 JSON 与实际持久化合约语义不一致"):
        FactCorrectionRepository(session).create(tampered)
    session.close()


def test_fact_correction_locator_outside_authority_rejected(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57b")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-2", "s57b-run", "s57b-call", "s57b-gate", "s57b-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-2", "s57b-run2", "s57b-call2", "s57b-gate2", "s57b-cand2", value="无")
    session.commit()
    foreign_locator = "nonexistent-loc-xyz"
    corr = _correction_for_facts(old_fact, new_fact, [foreign_locator])
    with pytest.raises(FactLocatorReferenceError):
        FactCorrectionRepository(session).create(corr)
    session.close()


def test_fact_correction_idempotency_and_branching(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57c")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-3", "s57c-run", "s57c-call", "s57c-gate", "s57c-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-3", "s57c-run2", "s57c-call2", "s57c-gate2", "s57c-cand2", value="无")
    session.commit()
    corr = _correction_for_facts(old_fact, new_fact, [seed["locator_id"]])
    repo = FactCorrectionRepository(session)
    first = repo.create(corr)
    second = repo.create(corr)
    assert first == second
    assert len(session.execute(select(FactCorrectionRecord)).scalars().all()) == 1
    dup = corr.model_copy(update={"correction_id": "corr-dup"})
    third = repo.create(dup)
    assert third.correction_id == first.correction_id
    changed_payload_same_id = corr.model_copy(
        update={
            "impact_scope": FactCorrectionImpactScope(
                scope_kind="local",
                affected_locator_ids=[seed["locator_id"]],
                affected_fact_ids=[old_fact.fact_id],
                affected_document_ids=[seed["logical_document_id"]],
            )
        }
    )
    assert changed_payload_same_id.idempotency_key == corr.idempotency_key
    with pytest.raises(FactCorrectionRevisionError, match="内容不一致"):
        repo.create(changed_payload_same_id)
    # 分支：同一 target 再次修订应拒绝
    new_fact2 = _create_fact_with_candidate(session, seed, "fact-new-3b", "s57c-run3", "s57c-call3", "s57c-gate3", "s57c-cand3", value="90/60")
    session.commit()
    corr2 = _correction_for_facts(old_fact, new_fact2, [seed["locator_id"]], correction_id="corr-branch")
    with pytest.raises(FactCorrectionRevisionError, match="已有修订"):
        repo.create(corr2)
    # 入边分支：同一新实体再次被指向应拒绝
    old_fact2 = _create_fact_with_candidate(session, seed, "fact-old-3b", "s57c-run4", "s57c-call4", "s57c-gate4", "s57c-cand4", value="100/70")
    session.commit()
    corr3 = _correction_for_facts(old_fact2, new_fact, [seed["locator_id"]], correction_id="corr-incoming-branch")
    with pytest.raises(FactCorrectionRevisionError, match="已被.*指向"):
        repo.create(corr3)
    session.close()


def test_fact_correction_dangling_new_entity_rejected(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57d")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-4", "s57d-run", "s57d-call", "s57d-gate", "s57d-cand")
    session.commit()
    old_snap = fact_semantic_snapshot(old_fact)
    old_json = canonical_json(old_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    fake_new_snap = {**old_snap, "value": "无"}
    fake_new_json = canonical_json(fake_new_snap)
    fake_new_sha = hashlib.sha256(fake_new_json.encode()).hexdigest()
    id_key = fact_correction_idempotency_key(authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, target_revision=old_fact.revision, new_entity_id="nonexistent-new", new_stable_identity="b"*64, new_revision=1, old_snapshot_sha256=old_sha, new_snapshot_sha256=fake_new_sha, reason="悬挂新实体", locator_ids=[seed["locator_id"]], operator_id="op-1")
    corr = FactCorrectionV2(correction_id="corr-dangle", authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, new_stable_identity="b"*64, target_revision=old_fact.revision, new_entity_id="nonexistent-new", new_revision=1, old_snapshot_json=old_json, old_snapshot_sha256=old_sha, new_snapshot_json=fake_new_json, new_snapshot_sha256=fake_new_sha, reason="悬挂新实体", locator_ids=[seed["locator_id"]], operator_id="op-1", corrected_at=UTC_NOW, created_at=UTC_NOW, impact_scope=FactCorrectionImpactScope(scope_kind="local", affected_locator_ids=[seed["locator_id"]], affected_fact_ids=[old_fact.fact_id]), idempotency_key=id_key)
    with pytest.raises(InvalidReferenceError, match="不存在"):
        FactCorrectionRepository(session).create(corr)
    session.close()


def test_fact_correction_cross_authority_rejected(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57e")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-5", "s57e-run", "s57e-call", "s57e-gate", "s57e-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-5", "s57e-run2", "s57e-call2", "s57e-gate2", "s57e-cand2", value="无")
    session.commit()
    # 构造跨权威修订：篡改 authority 的快照，使其与实体权威不一致
    from app.domain.contracts.facts import FactAuthority
    bad_authority = FactAuthority(**{**old_fact.authority.model_dump(), "evidence_snapshot_v2_id": "nonexistent-snapshot"})
    old_snap = fact_semantic_snapshot(old_fact)
    new_snap = fact_semantic_snapshot(new_fact)
    old_json = canonical_json(old_snap)
    new_json = canonical_json(new_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    new_sha = hashlib.sha256(new_json.encode()).hexdigest()
    id_key = fact_correction_idempotency_key(authority=bad_authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_stable_identity=new_fact.stable_identity, new_revision=new_fact.revision, old_snapshot_sha256=old_sha, new_snapshot_sha256=new_sha, reason="跨权威", locator_ids=[seed["locator_id"]], operator_id="op-1")
    corr = FactCorrectionV2(correction_id="corr-cross", authority=bad_authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, new_stable_identity=new_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_revision=new_fact.revision, old_snapshot_json=old_json, old_snapshot_sha256=old_sha, new_snapshot_json=new_json, new_snapshot_sha256=new_sha, reason="跨权威", locator_ids=[seed["locator_id"]], operator_id="op-1", corrected_at=UTC_NOW, created_at=UTC_NOW, impact_scope=FactCorrectionImpactScope(scope_kind="local", affected_locator_ids=[seed["locator_id"]], affected_fact_ids=[old_fact.fact_id]), idempotency_key=id_key)
    with pytest.raises(FactAuthorityError):
        FactCorrectionRepository(session).create(corr)
    session.close()


def test_fact_correction_wrong_kind_rejected(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57f")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-6", "s57f-run", "s57f-call", "s57f-gate", "s57f-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-6", "s57f-run2", "s57f-call2", "s57f-gate2", "s57f-cand2", value="无")
    session.commit()
    corr = _correction_for_facts(old_fact, new_fact, [seed["locator_id"]])
    corr_wrong = corr.model_copy(update={"target_kind": "event", "idempotency_key": fact_correction_idempotency_key(authority=corr.authority, target_kind="event", target_id=corr.target_id, target_stable_identity=corr.target_stable_identity, target_revision=corr.target_revision, new_entity_id=corr.new_entity_id, new_stable_identity=corr.new_stable_identity, new_revision=corr.new_revision, old_snapshot_sha256=corr.old_snapshot_sha256, new_snapshot_sha256=corr.new_snapshot_sha256, reason=corr.reason, locator_ids=corr.locator_ids, operator_id=corr.operator_id)})
    with pytest.raises(InvalidReferenceError, match="不存在"):
        FactCorrectionRepository(session).create(corr_wrong)
    session.close()


def test_fact_correction_wrong_snapshot_rejected(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57g")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-7", "s57g-run", "s57g-call", "s57g-gate", "s57g-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-7", "s57g-run2", "s57g-call2", "s57g-gate2", "s57g-cand2", value="无")
    session.commit()
    corr = _correction_for_facts(old_fact, new_fact, [seed["locator_id"]])
    bad_old = canonical_json({"kind": "fact", "fact_type": "vital_sign", "value": "tampered"})
    bad_sha = hashlib.sha256(bad_old.encode()).hexdigest()
    corr_bad = corr.model_copy(update={"old_snapshot_json": bad_old, "old_snapshot_sha256": bad_sha, "idempotency_key": fact_correction_idempotency_key(authority=corr.authority, target_kind=corr.target_kind, target_id=corr.target_id, target_stable_identity=corr.target_stable_identity, target_revision=corr.target_revision, new_entity_id=corr.new_entity_id, new_stable_identity=corr.new_stable_identity, new_revision=corr.new_revision, old_snapshot_sha256=bad_sha, new_snapshot_sha256=corr.new_snapshot_sha256, reason=corr.reason, locator_ids=corr.locator_ids, operator_id=corr.operator_id)})
    with pytest.raises(RepositoryError, match="旧快照.*不一致"):
        FactCorrectionRepository(session).create(corr_bad)
    session.close()


def test_fact_correction_beijing_and_profile_replay(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57h")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-8", "s57h-run", "s57h-call", "s57h-gate", "s57h-cand")
    session.commit()
    profile_repo = PatientProfileRevisionRepository(session)
    profile_before = profile_repo.create(_profile_revision(seed, revision=1))
    profile_before = profile_repo.get(profile_before.patient_profile_revision_id)
    profile_row_before = session.get(
        PatientProfileRevisionV2Record, profile_before.patient_profile_revision_id
    )
    assert profile_row_before is not None
    profile_payload_before = profile_row_before.payload_json.encode("utf-8")
    profile_hash_before = profile_row_before.payload_sha256
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-8", "s57h-run2", "s57h-call2", "s57h-gate2", "s57h-cand2", value="无")
    session.commit()
    corr = _correction_for_facts(
        old_fact,
        new_fact,
        [seed["locator_id"]],
        impact_scope=FactCorrectionImpactScope(
            scope_kind="local",
            affected_locator_ids=[seed["locator_id"]],
            affected_fact_ids=[old_fact.fact_id],
            affected_profile_revision_ids=[profile_before.patient_profile_revision_id],
        ),
    )
    FactCorrectionRepository(session).create(corr)
    session.commit()
    utc_midnight = datetime(2026, 8, 23, 0, 0, 0, tzinfo=UTC)
    assert FactCorrectionRepository.to_beijing_naive(utc_midnight).hour == 8
    assert ClinicalFactV2Repository(session).get("fact-old-8").revision == 1
    assert ClinicalFactV2Repository(session).get("fact-new-8").revision == 1
    profile_after = profile_repo.get(profile_before.patient_profile_revision_id)
    profile_row_after = session.get(
        PatientProfileRevisionV2Record, profile_before.patient_profile_revision_id
    )
    assert profile_after == profile_before
    assert profile_row_after is not None
    assert profile_row_after.payload_json.encode("utf-8") == profile_payload_before
    assert profile_row_after.payload_sha256 == profile_hash_before
    assert profile_repo.list_by_episode(seed["review_episode_id"]) == [profile_before]
    assert corr.impact_scope.affected_profile_revision_ids == [
        profile_before.patient_profile_revision_id
    ]
    session.close()


def test_fact_correction_impact_node_fallback(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57i")
    old_fact = _create_fact_with_candidate(session, seed, "fact-old-9", "s57i-run", "s57i-call", "s57i-gate", "s57i-cand")
    session.commit()
    new_fact = _create_fact_with_candidate(session, seed, "fact-new-9", "s57i-run2", "s57i-call2", "s57i-gate2", "s57i-cand2", value="无")
    session.commit()
    old_snap = fact_semantic_snapshot(old_fact)
    new_snap = fact_semantic_snapshot(new_fact)
    old_json = canonical_json(old_snap)
    new_json = canonical_json(new_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    new_sha = hashlib.sha256(new_json.encode()).hexdigest()
    id_key = fact_correction_idempotency_key(authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_stable_identity=new_fact.stable_identity, new_revision=new_fact.revision, old_snapshot_sha256=old_sha, new_snapshot_sha256=new_sha, reason="缺少索引", locator_ids=[seed["locator_id"]], operator_id="op-1")
    corr = FactCorrectionV2(correction_id="corr-node", authority=old_fact.authority, target_kind="fact", target_id=old_fact.fact_id, target_stable_identity=old_fact.stable_identity, new_stable_identity=new_fact.stable_identity, target_revision=old_fact.revision, new_entity_id=new_fact.fact_id, new_revision=new_fact.revision, old_snapshot_json=old_json, old_snapshot_sha256=old_sha, new_snapshot_json=new_json, new_snapshot_sha256=new_sha, reason="缺少索引", locator_ids=[seed["locator_id"]], operator_id="op-1", corrected_at=UTC_NOW, created_at=UTC_NOW, impact_scope=FactCorrectionImpactScope(scope_kind="node", fallback_reason="缺少 FactRuleLink 反向索引，无法证明局部闭包"), idempotency_key=id_key)
    created = FactCorrectionRepository(session).create(corr)
    assert created.impact_scope.scope_kind == "node"
    session.close()


def test_event_correction_roundtrip_uses_persisted_candidates_and_typed_links(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57j")
    ClinicalFactV2Repository(session).create(_seed_fact(seed))
    event_repo = ClinicalEventV2Repository(session)
    old_event_gate = FactGateResultRepository(session).get(seed["event_gate_id"])
    old_event = event_repo.create(
        _seed_event(seed).model_copy(
            update={
                "source_candidate_ids": [old_event_gate.candidate_id],
                "gate_ids": [seed["event_gate_id"]],
            }
        )
    )
    new_event_candidate_id = "s57j-event-cand-new"
    new_event_gate_id = "s57j-event-gate-new"
    _add_candidate_and_gate(
        session,
        seed,
        ClinicalEventCandidateV2(
            candidate_id=new_event_candidate_id,
            run_id=seed["run_id"],
            call_id=seed["call_id"],
            event_type="treatment",
            start_range=old_event.start_range,
            end_range=old_event.end_range,
            duration_status=old_event.duration_status,
            record_time=old_event.record_time,
            fact_candidate_ids=[seed["fact_candidate_id"]],
            locator_ids=[seed["locator_id"]],
            candidate_source_semantics="historical_primary",
            model_uncertainty=0.02,
            created_at=NOW,
        ),
        new_event_gate_id,
    )
    new_event_stable = clinical_event_stable_identity(
        authority=old_event.authority,
        event_type="treatment",
        profile_lane=old_event.profile_lane,
        referenced_fact_objects=old_event.referenced_fact_objects,
        start_range=old_event.start_range,
        end_range=old_event.end_range,
        duration_status=old_event.duration_status,
    )
    new_event = event_repo.create(
        old_event.model_copy(
            update={
                "event_id": "s57j-event-new",
                "gate_id": new_event_gate_id,
                "event_type": "treatment",
                "source_candidate_ids": [new_event_candidate_id],
                "gate_ids": [new_event_gate_id],
                "stable_identity": new_event_stable,
            }
        )
    )
    session.commit()

    correction = _correction_for_entities(
        old_event,
        new_event,
        "event",
        event_semantic_snapshot,
        [seed["locator_id"]],
        correction_id="corr-event",
        reason="人工核对事件类型",
    )
    created = FactCorrectionRepository(session).create(correction)
    session.commit()
    row = session.get(FactCorrectionRecord, correction.correction_id)
    assert row is not None
    assert row.target_event_id == old_event.event_id
    assert row.new_event_id == new_event.event_id
    assert row.target_fact_id is None and row.new_fact_id is None
    assert row.target_exposure_id is None and row.new_exposure_id is None
    assert created.authority == old_event.authority == new_event.authority
    assert created.old_snapshot_json == canonical_json(event_semantic_snapshot(old_event))
    assert created.new_snapshot_json == canonical_json(event_semantic_snapshot(new_event))
    assert event_repo.get(old_event.event_id) == old_event
    assert event_repo.get(new_event.event_id) == new_event
    session.close()


def test_exposure_correction_roundtrip_uses_persisted_candidates_and_typed_links(session_factory):
    session = session_factory()
    seed = _seed_valid_chain(session, "s57k")
    ClinicalFactV2Repository(session).create(_seed_fact(seed))
    exposure_repo = MedicationExposureV2Repository(session)
    old_exposure_gate = FactGateResultRepository(session).get(seed["exposure_gate_id"])
    old_exposure = exposure_repo.create(
        _seed_exposure(seed).model_copy(
            update={
                "source_candidate_ids": [old_exposure_gate.candidate_id],
                "gate_ids": [seed["exposure_gate_id"]],
            }
        )
    )
    new_exposure_candidate_id = "s57k-exposure-cand-new"
    new_exposure_gate_id = "s57k-exposure-gate-new"
    _add_candidate_and_gate(
        session,
        seed,
        MedicationExposureCandidateV2(
            candidate_id=new_exposure_candidate_id,
            run_id=seed["run_id"],
            call_id=seed["call_id"],
            medication_name="阿司匹林",
            category=old_exposure.category,
            indication=old_exposure.indication,
            dose=old_exposure.dose,
            unit=old_exposure.unit,
            frequency=old_exposure.frequency,
            route=old_exposure.route,
            start_range=old_exposure.start_range,
            end_range=old_exposure.end_range,
            duration_status=old_exposure.duration_status,
            record_time=old_exposure.record_time,
            fact_candidate_ids=[seed["fact_candidate_id"]],
            locator_ids=[seed["locator_id"]],
            candidate_source_semantics="current_chart",
            model_uncertainty=0.03,
            created_at=NOW,
        ),
        new_exposure_gate_id,
    )
    new_exposure_stable = medication_exposure_stable_identity(
        authority=old_exposure.authority,
        medication_name="阿司匹林",
        category=old_exposure.category,
        indication=old_exposure.indication,
        dose=old_exposure.dose,
        unit=old_exposure.unit,
        frequency=old_exposure.frequency,
        route=old_exposure.route,
        start_range=old_exposure.start_range,
        end_range=old_exposure.end_range,
        duration_status=old_exposure.duration_status,
    )
    new_exposure = exposure_repo.create(
        old_exposure.model_copy(
            update={
                "exposure_id": "s57k-exposure-new",
                "gate_id": new_exposure_gate_id,
                "medication_name": "阿司匹林",
                "source_candidate_ids": [new_exposure_candidate_id],
                "gate_ids": [new_exposure_gate_id],
                "stable_identity": new_exposure_stable,
            }
        )
    )
    session.commit()

    correction = _correction_for_entities(
        old_exposure,
        new_exposure,
        "exposure",
        exposure_semantic_snapshot,
        [seed["locator_id"]],
        correction_id="corr-exposure",
        reason="人工核对用药名称",
    )
    created = FactCorrectionRepository(session).create(correction)
    session.commit()
    row = session.get(FactCorrectionRecord, correction.correction_id)
    assert row is not None
    assert row.target_exposure_id == old_exposure.exposure_id
    assert row.new_exposure_id == new_exposure.exposure_id
    assert row.target_fact_id is None and row.new_fact_id is None
    assert row.target_event_id is None and row.new_event_id is None
    assert created.authority == old_exposure.authority == new_exposure.authority
    assert created.old_snapshot_json == canonical_json(exposure_semantic_snapshot(old_exposure))
    assert created.new_snapshot_json == canonical_json(exposure_semantic_snapshot(new_exposure))
    assert exposure_repo.get(old_exposure.exposure_id) == old_exposure
    assert exposure_repo.get(new_exposure.exposure_id) == new_exposure
    session.close()
