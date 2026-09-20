"""Atomic V2 review publication, gated by an explicitly approved method.

This module does not issue method approval, discover credentials or run models.
No HTTP route enables it before isolated evaluation and user authorization.
"""
from datetime import UTC, datetime
from collections.abc import Sequence

from app.domain.contracts.agents import GateResult
from app.domain.contracts.control_review_outcome import ReviewControlSnapshot
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.qualified_binding_selection import QualificationAdoptionAuthorization
from app.domain.contracts.review import FinalAssessment, PredicateObservation, ReviewRun
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.services.control_action_publication import publish_control_actions
from app.services.frozen_review_calculation import EVALUATOR_VERSION, calculate_frozen_review
from app.services.qualified_binding_selection import build_receipt_verified_qualified_binding_selections
from app.services.review_action_publication import publish_review_actions
from app.services.review_history_service import get_run
from app.services.review_method_evidence import read_review_method_approval
from app.services.review_judgment_provenance import verify_frozen_judgment_search_result
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.idempotency import IdempotencyConflict, IdempotencyRepository
from app.storage.repositories import (
    AppendRepository, FINAL_ASSESSMENT_CONFIG, GATE_RESULT_CONFIG, REVIEW_RUN_CONFIG,
    DuplicateRecordError, ScopeViolationError, get_rule_set,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.review_control_repository import REVIEW_CONTROL_GATE_NAME, ReviewControlRepository

PUBLICATION_VERSION = "frozen-review-publication/v17"


def publish_frozen_review(
    session, artifact_store, *, context_id: str,
    authorizations: Sequence[QualificationAdoptionAuthorization],
    method_approval_gate_id: str, idempotency_key: str,
) -> str:
    """Save all results/actions or none; the outer command owns commit.

    A persisted method approval is separate from pair qualification. Its exact
    scope binds this evaluator, publisher and approved evaluation artifacts.
    Merely presenting model agreement or a source calculation is insufficient.
    """
    if not authorizations or not idempotency_key.strip():
        raise ScopeViolationError("正式保存需提供完整采用依据和本次操作编号")
    context = ReviewContextV2Repository(session).get(context_id)
    auths = sorted((QualificationAdoptionAuthorization.model_validate(item.model_dump(mode="json"))
                    for item in authorizations), key=lambda item: item.candidate_family)
    request_hash = canonical_hash({"version": PUBLICATION_VERSION, "context": context.context_sha256,
        "authorizations": [item.model_dump(mode="json") for item in auths], "method": method_approval_gate_id})
    scope = f"formal-review:{context_id}"
    receipts = IdempotencyRepository(session)
    def prior_result():
        receipt = receipts.get(scope, idempotency_key)
        if receipt is None:
            return None
        if receipt.request_sha256 != request_hash:
            raise IdempotencyConflict(scope=scope, idempotency_key=idempotency_key,
                existing_sha256=receipt.request_sha256, submitted_sha256=request_hash)
        if receipt.result_type != "review_run" or receipt.result_id != context.review_run_id:
            raise ScopeViolationError("原保存回执不完整，未重复写入")
        detail = get_run(session, context.authority.subject_id, context.authority.review_episode_id, receipt.result_id)
        if detail.status != "completed":
            raise ScopeViolationError("原保存回执对应的审核尚未完整结束")
        return receipt.result_id
    prior = prior_result()
    if prior is not None:
        return prior
    authority = context.authority
    FactAuthorityValidator(session).validate(authority)
    for search in context.judgment_search_results:
        verify_frozen_judgment_search_result(
            session, artifact_store, authority=authority, frozen=search,
        )
    gates = AppendRepository(session, GATE_RESULT_CONFIG)
    evaluations = sorted({item.approved_evaluation_evidence_sha256 for item in auths})
    evaluations = sorted(set(evaluations) | {item.judgment_content.evaluation_sha256
                                           for item in auths if item.judgment_content is not None})
    evaluations = sorted(set(evaluations) | {item.proposition_evidence.evaluation_sha256
                                           for item in auths if item.proposition_evidence is not None})
    evaluations = sorted(set(evaluations) | {item.observation_relation.evaluation_sha256
                                           for item in auths if item.observation_relation is not None})
    evaluations = sorted(set(evaluations) | {item.frequency_evidence.evaluation_sha256
                                           for item in auths if item.frequency_evidence is not None})
    _, manifests = read_review_method_approval(session, artifact_store, method_approval_gate_id)
    if not set(evaluations) <= set(manifests):
        raise ScopeViolationError("本次核对所用评测记录尚未获得采用确认")
    for auth in auths:
        manifest = manifests[auth.approved_evaluation_evidence_sha256]
        if manifest.evaluation_kind != "binding_semantic_correspondence":
            raise ScopeViolationError("来源核实授权不能引用其他类型的评测记录")
        if auth.judgment_content is not None and manifests[auth.judgment_content.evaluation_sha256].evaluation_kind != "written_judgment_content_fidelity":
            raise ScopeViolationError("书面判断授权必须引用对应的内容核实评测")
        if auth.proposition_evidence is not None and manifests[auth.proposition_evidence.evaluation_sha256].evaluation_kind != "pair_local_proposition_relation":
            raise ScopeViolationError("原文含义授权必须引用对应的来源关系评测")
        if auth.observation_relation is not None and manifests[auth.observation_relation.evaluation_sha256].evaluation_kind != "observation_relationship_fidelity":
            raise ScopeViolationError("复查对应授权必须引用对应的原文关系评测")
        if auth.frequency_evidence is not None and manifests[auth.frequency_evidence.evaluation_sha256].evaluation_kind != "frequency_statement_fidelity":
            raise ScopeViolationError("频次授权必须引用对应的原文计数评测")
        methods = [item for item in manifest.methods
                   if item.candidate_family == auth.candidate_family]
        if (len(methods) != 1 or methods[0].publication_version != PUBLICATION_VERSION
                or methods[0].evaluator_version != EVALUATOR_VERSION
                or methods[0].consumer_algorithm_version != auth.consumer_algorithm_version):
            raise ScopeViolationError("当前审核计算版本与已确认的方法不一致")
    selections = [build_receipt_verified_qualified_binding_selections(
        session, artifact_store, qualification_job_id=item.qualification_job_id, authorization=item,
    ) for item in auths]
    rules = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
    calculation = calculate_frozen_review(context, rules, qualified_binding_selections=selections)
    completed_at = datetime.now(UTC)
    run_id = context.review_run_id
    runs = AppendRepository(session, REVIEW_RUN_CONFIG)
    if runs.get_or_none(run_id) is not None:
        prior = prior_result()
        if prior is not None:
            return prior
        raise ScopeViolationError("本次审核已有保存记录但缺少对应回执，未覆盖历史")
    run = ReviewRun(
        schema_version="review/v2", review_run_id=run_id, review_episode_id=authority.review_episode_id,
        protocol_version_id=authority.protocol_version_id, rule_set_revision=authority.rule_set_revision,
        episode_revision=authority.episode_revision, context_id=context_id,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id,
        started_at=context.created_at, completed_at=completed_at,
    )
    common = {key: getattr(authority, key) for key in (
        "project_id", "subject_id", "protocol_version_id", "rule_set_id", "rule_set_revision",
        "review_episode_id", "evidence_snapshot_v2_id", "complete_processing_revision_id",
    )}
    facts = {item.fact_id: item for item in context.facts}
    predicate_outcomes = {}
    predicate_gaps = {}
    predicate_repeats = {}
    predicate_frequencies = {}
    for selection in selections:
        if selection.candidate_family != "predicate":
            continue
        outcomes = {item.identity_sha256: item for item in selection.material.identity_outcomes}
        for component in selection.predicate_frozen_input.components:
            for predicate in (*component.trigger_predicates, *component.exception_predicates):
                predicate_outcomes[(component.rule_component_id, predicate.predicate_id)] = outcomes[
                    predicate.predicate_identity_sha256
                ]
                predicate_gaps[(component.rule_component_id, predicate.predicate_id)] = [
                    item for item in selection.material.unresolved_proposition_pairs
                    if item["identity_sha256"] == predicate.predicate_identity_sha256
                ]
                repeat = calculation.repeat_atom_evaluations.get("predicate", {}).get(predicate.predicate_identity_sha256)
                frequency = calculation.frequency_atom_evaluations.get("predicate", {}).get(predicate.predicate_identity_sha256)
                if frequency is not None:
                    key = component.rule_component_id, predicate.predicate_id
                    predicate_frequencies[key] = frequency
                    predicate_gaps[key] = []
                if repeat is not None:
                    key = component.rule_component_id, predicate.predicate_id
                    predicate_repeats[key] = repeat
                    source = next(item for item in selection.material.observation_relations
                                  if item["identity_sha256"] == predicate.predicate_identity_sha256)
                    predicate_gaps[key] = source["result_sources"]["proposition_pair_gaps"]
    input_refs = [context_id, method_approval_gate_id, *(item.authorization_id for item in auths)]
    def persist():
        runs.save(run)
        assessments = AppendRepository(session, FINAL_ASSESSMENT_CONFIG)
        for component in calculation.components:
            assessment_id = "assessment:" + canonical_hash([run_id, component.rule_component_id])[:32]
            gate_id = f"gate:{assessment_id}"
            observations = [PredicateObservation(
                schema_version="review/v2", predicate_id=key, truth=value.truth,
                observed_value=value.observed_value, observed_unit=value.observed_unit,
                fact_ids=list(value.used_fact_ids),
                locator_ids=sorted({locator for fact_id in value.used_fact_ids for locator in facts[fact_id].locator_ids}),
                reason_codes=list(dict.fromkeys([
                    *value.reason_codes,
                    *(predicate_outcomes[(component.rule_component_id, key)].unresolved_reasons
                      if (component.rule_component_id, key) not in predicate_repeats
                      and (component.rule_component_id, key) not in predicate_frequencies else []),
                ])),
                observation_ordering=predicate_outcomes[(component.rule_component_id, key)].observation_ordering,
                proposition_pair_gaps=predicate_gaps[(component.rule_component_id, key)],
                repeat_evaluation=predicate_repeats.get((component.rule_component_id, key)),
                frequency_evaluation=predicate_frequencies.get((component.rule_component_id, key)),
            ) for key, value in component.result.evaluation.predicate_evaluations.items()]
            data = dict(common, schema_version="review/v2", assessment_id=assessment_id, review_run_id=run_id,
                rule_component_id=component.rule_component_id, decision=component.result.decision,
                gap_types=sorted(component.result.gaps, key=lambda value: value.value),
                blocking_level=component.result.blocking_level,
                used_fact_ids=sorted({fact_id for item in observations for fact_id in item.fact_ids}),
                locator_ids=sorted({locator for item in observations for locator in item.locator_ids}),
                predicate_observations=observations)
            assessment = _build_gate_owned_model(FinalAssessment, entity_type="final_assessment", gate_result_id=gate_id, data=data)
            gate = GateResult(
                gate_result_id=gate_id, gate_name="assessment-publication-gate", result=GateOutcome.ACCEPTED,
                input_scope_hash=canonical_hash({"context": context.context_sha256,
                    "selections": calculation.selections_sha256, "component": component.rule_component_id}),
                input_revision_map={authority.review_episode_id: authority.episode_revision},
                input_entity_refs=input_refs, accepted_entity_refs=[assessment_id],
                affected_scope=[component.rule_component_id], recompute_scope=[component.rule_component_id],
                idempotency_key=assessment_id, created_at=completed_at,
                output_hash=canonical_hash(assessment.model_dump(mode="json")),
            )
            gates.save(gate)
            assessments.save(assessment)
            publish_review_actions(session, assessment_id=assessment_id)
        if calculation.controls is not None:
            gate_id = f"gate:controls:{run_id}"
            snapshot = ReviewControlSnapshot(
                review_run_id=run_id, context_id=context_id, context_sha256=context.context_sha256,
                selections_sha256=calculation.selections_sha256, gate_result_id=gate_id,
                outcomes=list(calculation.control_outcomes), created_at=completed_at,
            )
            gate = GateResult(
                gate_result_id=gate_id, gate_name=REVIEW_CONTROL_GATE_NAME, result=GateOutcome.ACCEPTED,
                input_scope_hash=canonical_hash({"context": context.context_sha256,
                    "review_selections": calculation.selections_sha256,
                    "control_selections": calculation.controls.selections_sha256,
                    "control_input": calculation.controls.frozen_input_sha256}),
                input_revision_map={authority.review_episode_id: authority.episode_revision},
                input_entity_refs=input_refs, accepted_entity_refs=[run_id],
                affected_scope=[item.protocol_control_id for item in snapshot.outcomes],
                recompute_scope=[item.protocol_control_id for item in snapshot.outcomes],
                idempotency_key=f"controls:{run_id}", created_at=completed_at,
                output_hash=canonical_hash(snapshot.model_dump(mode="json")),
            )
            gates.save(gate)
            ReviewControlRepository(session).save(snapshot)
            publish_control_actions(session, review_run_id=run_id)
        get_run(session, authority.subject_id, authority.review_episode_id, run_id)
        receipts.resolve(scope=scope, idempotency_key=idempotency_key, submitted_hash=request_hash,
                         result_type="review_run", result_id=run_id)
    try:
        with session.begin_nested():
            persist()
    except DuplicateRecordError:
        # The savepoint has exited before reading a concurrent winner's receipt.
        # A duplicate alone never proves that this exact request completed.
        prior = prior_result()
        if prior is not None:
            return prior
        raise
    return run_id
