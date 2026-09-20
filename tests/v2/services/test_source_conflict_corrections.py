"""Source-only conflict lineage remains distinct from explicit clinical correction."""

import hashlib

from app.domain.contracts.facts import fact_run_idempotency_key
from app.services.fact_publication_service import FactPublicationService
from app.services.patient_profile_service import PatientProfileService
from app.storage.active_conflicts import current_conflict_heads
from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import (
    ClinicalFactV2Repository, ClinicalConflictGroupV2Repository,
    FactNormalizationRunRepository, FactNormalizationCallRepository,
    FactNormalizationCandidateRepository, FactGateResultRepository,
)
from tests.v2.services.test_fact_publication_service import _seed_chain, _authority
from tests.v2.services.test_fact_correction_job import _service, _run, NOW


def _append_source(session, fact, suffix, *, extra_value=None):
    runs = FactNormalizationRunRepository(session)
    calls = FactNormalizationCallRepository(session)
    candidates = FactNormalizationCandidateRepository(session)
    gates = FactGateResultRepository(session)
    original_gate = gates.get(fact.gate_id)
    candidate = candidates.get(original_gate.candidate_id)
    # Clone a valid product request/response fixture; no model or invented clinical answer.
    original_call = calls.get(candidate.call_id)
    original_run = runs.get(candidate.run_id)
    run_id, call_id = f"source-{suffix}", f"source-call-{suffix}"
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    runs.create_or_reuse(original_run.model_copy(update={
        "run_id": run_id, "input_scope_sha256": digest,
        "idempotency_key": fact_run_idempotency_key(
            authority=fact.authority, prompt_version_id=original_run.prompt_version_id,
            model_config_id=original_run.model_config_id, input_scope_sha256=digest,
        ),
    }))
    calls.create(original_call.model_copy(update={
        "call_id": call_id, "run_id": run_id, "input_sha256": digest,
    }))
    copied = candidate.model_copy(update={
        "candidate_id": f"source-candidate-{suffix}", "call_id": call_id, "run_id": run_id,
    })
    candidates.create(call_id, copied)
    gates.create(original_gate.model_copy(update={
        "gate_result_id": f"source-gate-{suffix}", "candidate_id": copied.candidate_id,
        "run_id": run_id, "call_id": call_id,
    }))
    if extra_value is not None:
        extra = copied.model_copy(update={
            "candidate_id": f"source-extra-{suffix}", "raw_value": extra_value, "canonical_value": extra_value,
        })
        candidates.create(call_id, extra)
        gates.create(original_gate.model_copy(update={
            "gate_result_id": f"source-extra-gate-{suffix}", "candidate_id": extra.candidate_id,
            "run_id": run_id, "call_id": call_id,
        }))
    published = FactPublicationService().publish(session, run_id)
    repository = ClinicalFactV2Repository(session)
    inherited = next(repository.get(item) for item in published.fact_ids if repository.get(item).inherited_from_fact_id == fact.fact_id)
    return inherited, published


def test_source_growth_then_correction_then_source_growth(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, "source-correction-sequence")
        authority = _authority(chain)
        candidates = FactNormalizationCandidateRepository(session)
        gates = FactGateResultRepository(session)
        other = candidates.get(chain["fact_candidate_id"]).model_copy(update={
            "candidate_id": "source-correction-other", "raw_value": "130/80", "canonical_value": "130/80",
        })
        candidates.create(chain["call_id"], other)
        gates.create(gates.get(chain["gate_id"]).model_copy(update={
            "gate_result_id": "source-correction-other-gate", "candidate_id": other.candidate_id,
        }))
        first = FactPublicationService().publish(session, chain["run_id"])
        repository = ClinicalFactV2Repository(session)
        original = next(repository.get(item) for item in first.fact_ids if repository.get(item).value == "120/80")
        updated, source_run = _append_source(session, original, "before-correction")
        source_group = current_conflict_heads(session, authority)[0]
        assert source_group.source_revision_of == first.conflict_group_ids[0]
        PatientProfileService().generate(session, authority=authority)
    created = _service(session_factory).create_or_reuse_job(
        authority=authority, target_kind="fact", target_id=updated.fact_id,
        locator_ids=updated.locator_ids, reason="合成测试：核对后更正血压记录",
        operator_id="reviewer-1", updates={"value": "125/80"},
        created_by="reviewer-1", created_at=NOW,
    )
    assert _run(session_factory)
    with session_factory() as session, session.begin():
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        outcome = next(item for item in commit.conflict_outcomes if item.superseded_conflict_group_id == source_group.conflict_group_id)
        correction_group = ClinicalConflictGroupV2Repository(session).get(outcome.successor_conflict_group_id)
        assert correction_group.source_revision_of is None
        assert current_conflict_heads(session, authority) == [correction_group]
        correction = FactCorrectionRepository(session).get(created.correction_id)
        corrected = ClinicalFactV2Repository(session).get(correction.new_entity_id)
        assert FactPublicationService().publish(session, source_run.run_id).is_replay
        assert current_conflict_heads(session, authority) == [correction_group]
        _, after = _append_source(session, corrected, "after-correction")
        final_group = current_conflict_heads(session, authority)[0]
        assert final_group.source_revision_of == correction_group.conflict_group_id
        assert final_group.gate_id == correction_group.gate_id
        assert final_group.resolution_revision == 0
        assert final_group.conflict_group_id in after.conflict_group_ids
        assert first.conflict_group_ids[0] not in {item.conflict_group_id for item in current_conflict_heads(session, authority)}
        assert PatientProfileService().generate(session, authority=authority).status.value == "succeeded"


def test_new_third_value_preserves_original_dispute(session):
    chain = _seed_chain(session, "source-third-value")
    authority = _authority(chain)
    candidates, gates = FactNormalizationCandidateRepository(session), FactGateResultRepository(session)
    other = candidates.get(chain["fact_candidate_id"]).model_copy(update={
        "candidate_id": "third-value-other", "raw_value": "130/80", "canonical_value": "130/80",
    })
    candidates.create(chain["call_id"], other)
    gates.create(gates.get(chain["gate_id"]).model_copy(update={
        "gate_result_id": "third-value-other-gate", "candidate_id": other.candidate_id,
    }))
    first = FactPublicationService().publish(session, chain["run_id"])
    facts = ClinicalFactV2Repository(session)
    original = next(facts.get(item) for item in first.fact_ids if facts.get(item).value == "120/80")
    inherited, published = _append_source(session, original, "third-value", extra_value="140/80")
    groups = current_conflict_heads(session, authority)
    assert len(groups) == 2
    source_group = next(group for group in groups if group.source_revision_of is not None)
    new_group = next(group for group in groups if group.source_revision_of is None)
    assert source_group.source_revision_of == first.conflict_group_ids[0]
    assert {facts.get(item).value for item in source_group.fact_ids} == {"120/80", "130/80"}
    assert {facts.get(item).value for item in new_group.fact_ids} == {"120/80", "140/80"}
    assert inherited.fact_id in source_group.fact_ids and inherited.fact_id in new_group.fact_ids
    assert all(group.resolution_revision == 0 for group in groups)
    assert set(published.conflict_group_ids) == {group.conflict_group_id for group in groups}
    assert PatientProfileService().generate(session, authority=authority).status.value == "succeeded"
