"""Connected software fixture: qualification receipts -> work-draft -> frozen calc.

This is simulated producer / software evidence only:

- ephemeral pytest tmp SQLite via ``session_factory`` / ``data_paths``;
- synthetic dual-lane answers enter through the existing JobExecutor ``completion``
  transport (same pattern as ``test_predicate_binding_job`` /
  ``test_binding_qualification_policy_preflight``);
- no production model names, usage, authorization, clinical materials, or network.

It does **not** hand-build ``_SEAL``, forge route receipts, fill verified/adoption,
or monkeypatch qualification verification / ``calculate_frozen_review``.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from hashlib import sha256
from types import SimpleNamespace
import pytest
from pydantic import ValidationError

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    ComponentDecision,
    DatePrecision,
    ExpectationStatus,
    FactPolarity,
    GapType,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    LogicalOperator,
    ProfileLane,
    ReviewStage,
    RuleKind,
    SourceStrength,
    StudyPhase,
    TruthValue,
)
from app.domain.contracts.evidence_expectations_v2 import CoverageObservation
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactV2,
    PartialDateRange,
    clinical_fact_stable_identity,
)
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput, control_binding_input_hash
from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
from app.domain.contracts.protocol_controls import (
    ControlObligationAtom, ControlObligationDnf, ControlObligationGroup,
    ProtocolReviewControl, PublishedProtocolControlCatalog,
)
from app.domain.contracts.predicate_binding import (
    FrozenLocatorIdentity,
    PredicateBindingFrozenInput,
    predicate_binding_frozen_input_sha256,
)
from app.domain.contracts.review import ProtocolDocumentVersion, ReviewEpisode, Subject
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    EvidenceRequirement,
    LogicalExpression,
    RestrictedRuleComponent,
    Rule,
    RuleComponent,
    RuleSet,
    WorkflowStage,
)
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.llm.medication_history_guidance import MEDICATION_HISTORY_GUIDANCE
from app.projections.clause_pack import project_clause_pack, verify_clause_pack
from app.projections.control_evidence_requirements import shared_control_requirements
from app.projections.evidence_expectation_templates import (
    project_evidence_expectation_templates,
)
from app.projections.evidence_expectations import project_expectation
from app.services.binding_qualification import (
    JOB_TYPE as QUALIFICATION_TYPE,
    BindingQualificationJobExecutor,
    enqueue_binding_qualification,
)
from app.services.binding_qualification_support import verify_completed_binding_qualification
from app.services.binding_evaluation import (
    GOLD_SPLIT_VERSION, _selected_fact_ids_by_identity, build_binding_evaluation_manifest,
)
from app.services.review_method_evidence import read_binding_evaluation, read_method_evaluation
from app.storage.repositories import ScopeViolationError
from app.storage.codecs import encode_value
from app.storage.models import JobRecord
from app.workflow.errors import InvalidJobDefinitionError
from app.services.frozen_review_calculation import (
    EVALUATOR_VERSION,
    calculate_frozen_review,
)
from app.services.predicate_binding_input import _frozen_component, _frozen_fact
from app.services.predicate_binding_job import (
    JOB_TYPE as CANDIDATE_TYPE,
    PredicateBindingJobExecutor,
    enqueue_predicate_candidates,
)
from app.services.qualified_binding_selection import (
    ReceiptVerifiedWorkDraftSelections,
    _select_control_semantic_evidence,
    build_receipt_verified_work_draft_selections,
)
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.llm.test_predicate_binding_candidates import _route, _v2_accounting
from tests.v2.services.test_predicate_binding_input import _COMPONENT_FIELDS, _authority

STAGE_ID = "workflow-stage-screening"
REQUIREMENT_ID = "synthetic-source-policy"
NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
NATIVE_EXCERPT = "静息心率 72 bpm"
NATIVE_TEXT_SHA256 = sha256(NATIVE_EXCERPT.encode("utf-8")).hexdigest()
POSITIVE_PREDICATE_ID = "predicate-resting-heart-rate-eq-72"
COUNTER_PREDICATE_ID = "predicate-systolic-bp-eq-140"
FACT_ID = "fact-hr"
LOCATOR_ID = "loc-hr"


def _positive_predicate(*, computation=False) -> AtomicPredicate:
    calculation = {}
    if computation:
        single = computation == "single"
        input_quote = "一次静息心率记录" if single else "最近两次静息心率记录"
        clause = input_quote + "的均值等于72 bpm"
        calculation = {
            "source_clause": clause,
            "source_computation": {
                "operator": "mean", "operator_ref": {"statement_index": 0, "quote": "均值"},
                "input_refs": [{"statement_index": 0, "quote": input_quote}],
                "missing_policy": "not_specified",
                "declared_input_count": {
                    "value": 1 if single else 2, "number_text": "一" if single else "两",
                    "source": {"statement_index": 0, "quote": input_quote},
                },
                **({"input_selection": {"mode": "single", "source": {"statement_index": 0, "quote": input_quote}}}
                   if single else {}),
            },
        }
    return AtomicPredicate(**(dict(
        predicate_id=POSITIVE_PREDICATE_ID,
        subject="vital_sign",
        attribute="resting_heart_rate",
        comparator="eq",
        value=72,
        unit="bpm",
        source_clause="静息心率等于72 bpm",
        requires_professional_judgment=False,
    ) | calculation))


def _counterexample_predicate() -> AtomicPredicate:
    """Honest unresolved branch: no matching fact is proposed for this atom."""
    return AtomicPredicate(
        predicate_id=COUNTER_PREDICATE_ID,
        subject="vital_sign",
        attribute="systolic_blood_pressure",
        comparator="eq",
        value=140,
        unit="mmHg",
        source_clause="收缩压等于140 mmHg",
        requires_professional_judgment=False,
    )


def _synthetic_material(*, computation=False, positive=None, record=None):
    """One executable ANY-component (usable + unresolved) plus restricted sibling."""
    authority = _authority()
    positive = positive or _positive_predicate(computation=computation)
    excerpt = record or NATIVE_EXCERPT
    excerpt_sha256 = sha256(excerpt.encode("utf-8")).hexdigest()
    counter = _counterexample_predicate()
    expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            AtomicExpression(predicate=positive),
            AtomicExpression(predicate=counter),
        ],
    )
    requirement = EvidenceRequirement(
        requirement_id=REQUIREMENT_ID,
        rule_component_id="component-a",
        fact_type="medication_history" if record is not None else "vital_sign",
        due_stage=ReviewStage.SCREENING,
        description="核对本条件的原始记录",
        allows_screening_record_transcription=True,
        requires_contemporaneous_objective_source=False,
        predicate_ids=[POSITIVE_PREDICATE_ID, COUNTER_PREDICATE_ID],
    )
    rule_component = RuleComponent(
        rule_component_id="component-a",
        parent_rule_id=_COMPONENT_FIELDS["parent_rule_id"],
        display_code=_COMPONENT_FIELDS["display_code"],
        title=_COMPONENT_FIELDS["title"],
        expression=expression,
        evidence_requirements=[requirement],
    )
    rule = Rule(
        rule_id=_COMPONENT_FIELDS["parent_rule_id"],
        official_code=_COMPONENT_FIELDS["official_code"],
        kind=RuleKind.EXCLUSION,
        source_text=f"以下任一项：{positive.source_clause}；收缩压等于140 mmHg。另有同源受限兄弟要求原文。",
        study_phase=StudyPhase.PHASE_III,
        components=[rule_component],
        restricted_components=[
            RestrictedRuleComponent(
                rule_component_id="component-restricted-sibling",
                display_code="EX-01-b",
                title="同源受限兄弟要求",
                source_span_ids=["span-restricted-sibling"],
                source_excerpts=["同源受限兄弟要求原文"],
                limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["适用对象尚未核清"],
            )
        ],
    )
    rule_set = RuleSet(
        rule_set_id=authority.rule_set_id,
        revision=authority.rule_set_revision,
        protocol_version_id=authority.protocol_version_id,
        study_phase=StudyPhase.PHASE_III,
        rules=[rule],
    )
    frozen_component = _frozen_component(rule_component, rule)
    positive_identity = next(
        item.predicate_identity_sha256
        for item in frozen_component.trigger_predicates
        if item.predicate_id == POSITIVE_PREDICATE_ID
    )
    counter_identity = next(
        item.predicate_identity_sha256
        for item in frozen_component.trigger_predicates
        if item.predicate_id == COUNTER_PREDICATE_ID
    )

    basis = AssertionBasis(
        asserted_object=record or "静息心率",
        assertion_text=excerpt,
        locator_id=LOCATOR_ID,
        source_text_sha256=excerpt_sha256,
    )
    fact_kwargs = dict(
        authority=authority,
        fact_type="medication_history" if record is not None else "vital_sign",
        profile_lane=ProfileLane.MEDICATION if record is not None else ProfileLane.EVIDENCE_QUALITY,
        asserted_object=record or "静息心率",
        polarity=FactPolarity.AFFIRMED,
        value=record or 72,
        unit=None if record is not None else "bpm",
        date_range=(PartialDateRange(precision=DatePrecision.DAY, lower_bound=date(2025, 4, 12),
                                    upper_bound=date(2025, 4, 12)) if record is not None else None),
    )
    clinical_fact = ClinicalFactV2(
        fact_id=FACT_ID,
        run_id="run-synthetic",
        gate_id="gate-synthetic",
        source_strength=(SourceStrength.HISTORICAL_PRIMARY if record is not None
                         else SourceStrength.CONTEMPORANEOUS_OBJECTIVE),
        locator_ids=[LOCATOR_ID],
        assertion_basis=basis,
        supported_requirement_ids=[REQUIREMENT_ID],
        source_candidate_ids=[],
        source_observation_refs=[],
        gate_ids=["gate-synthetic"],
        revision=1,
        created_at=NOW,
        stable_identity=clinical_fact_stable_identity(**fact_kwargs),
        **fact_kwargs,
    )
    frozen_fact = _frozen_fact(clinical_fact)
    locators = [
        FrozenLocatorIdentity(
            locator_id=LOCATOR_ID,
            page_artifact_id=f"{LOCATOR_ID}-pa",
            source_document_version_id=f"{LOCATOR_ID}-doc",
            page_number=1,
            source_layer=LocatorSourceLayer.NATIVE_TEXT,
            source_text_sha256=excerpt_sha256,
            precision=LocatorPrecision.TEXT_RANGE,
            authenticity=LocatorAuthenticity.DEGRADED,
            target_id=f"{LOCATOR_ID}-target",
            text_start=0,
            text_end=len(excerpt),
            excerpt=excerpt,
            degradation_reason="native_text_range_without_bbox",
        )
    ]
    episode = ReviewEpisode(
        project_id=authority.project_id,
        subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        protocol_version_id=authority.protocol_version_id,
        study_phase=StudyPhase.PHASE_III,
        stage=ReviewStage.SCREENING,
        revision=authority.episode_revision,
        workflow_stage_id=STAGE_ID,
        anchor_dates={},
        active_evidence_snapshot_id=authority.evidence_snapshot_v2_id,
        active_evidence_processing_revision_id=authority.complete_processing_revision_id,
    )
    frozen = PredicateBindingFrozenInput(
        authority=authority,
        episode=episode,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        protocol_version_id=authority.protocol_version_id,
        study_phase=StudyPhase.PHASE_III,
        components=[frozen_component],
        facts=[frozen_fact],
        locators=locators,
        frozen_input_sha256=predicate_binding_frozen_input_sha256(
            authority=authority,
            episode=episode,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            protocol_version_id=authority.protocol_version_id,
            study_phase=StudyPhase.PHASE_III,
            components=[frozen_component],
            facts=[frozen_fact],
            locators=locators,
        ),
    )
    candidate_response = {
        "results": [
            {
                "predicate_identity_sha256": positive_identity,
                "status": "candidates",
                "candidates": [
                    {
                        "fact_id": FACT_ID,
                        "fact_attribute": "value",
                        "locator_id": LOCATOR_ID,
                        "object_correspondence": "supported",
                        "attribute_correspondence": "direct",
                        "correspondence_explanation": (
                            record or "native-text excerpt states resting heart rate 72 bpm"
                        ),
                    }
                ],
                "fact_accounting": _v2_accounting(
                    candidate_fact_ids=(FACT_ID,), universe=(FACT_ID,),
                ),
            },
            {
                "predicate_identity_sha256": counter_identity,
                "status": "unresolved",
                "candidates": [],
                "uncertainty": "本批未见与收缩压条件对应的事实",
                "fact_accounting": _v2_accounting(
                    candidate_fact_ids=(),
                    universe=(FACT_ID,),
                    disposition="uncertain",
                    reason_code="category_match_only",
                ),
            },
        ]
    }
    return authority, rule_set, frozen, clinical_fact, episode, candidate_response


def _aligned_review_context(*, authority, rule_set, clinical_fact, episode, control_publication=None,
                            clinical_facts=None):
    facts = tuple(sorted(clinical_facts, key=lambda item: item.fact_id)) if clinical_facts is not None else (clinical_fact,)
    pack = project_clause_pack(rule_set, control_publication=control_publication)
    verify_clause_pack(pack)
    assert len(pack.clauses) == 1
    assert len(pack.restricted_clauses) == 1
    stage = WorkflowStage(
        workflow_stage_id=STAGE_ID,
        stage=ReviewStage.SCREENING,
        display_name="筛选期",
        due_requirement_ids=[REQUIREMENT_ID],
    )
    stages = [stage]
    if control_publication is not None:
        stages.extend(WorkflowStage(workflow_stage_id=key, stage=ReviewStage.SCREENING,
                                    display_name="筛选期补充要求", due_requirement_ids=[])
                      for key in sorted(set(control_publication.workflow_stage_map.values()) - {STAGE_ID}))
    templates = tuple(
        project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=stages,
            control_requirements=(shared_control_requirements(control_publication)
                                  if control_publication is not None else ()),
            created_at=NOW,
        )
    )
    assert len(templates) == (2 if control_publication is not None else 1)
    expectation = project_expectation(
        template=next(item for item in templates if item.requirement_id == REQUIREMENT_ID),
        authority=authority,
        current_stage=ReviewStage.SCREENING,
        observations=[CoverageObservation(fact=fact, source_types=["vital_sign"]) for fact in facts],
        created_at=NOW,
    )
    assert expectation.status == ExpectationStatus.OBSERVED
    assert expectation.gap_type is None
    protocol = ProtocolDocumentVersion(
        protocol_version_id=authority.protocol_version_id,
        protocol_code="SYN-PROTO",
        official_version="v0-synthetic",
        official_date=DateValue(value=date(2026, 1, 1), precision=DatePrecision.DAY),
        sha256="a" * 64,
        integrity_manifest_sha256="b" * 64,
        authority_record_sha256="c" * 64,
        authority_confirmation_id="auth-confirm-synthetic",
        authority_gate_result_id="auth-gate-synthetic",
        integrity_gate_result_id="integrity-gate-synthetic",
    )
    subject = Subject(
        subject_id=authority.subject_id,
        subject_code="S-SYN",
        project_id=authority.project_id,
        revision=1,
    )
    data = dict(
        context_id="review-context-v2:synthetic-work-draft-consumer",
        review_run_id="review-run-synthetic",
        authority=authority,
        review_episode=episode,
        subject=subject,
        project_name="synthetic-project",
        project_revision=1,
        protocol_document=protocol,
        rule_set_sha256=canonical_hash(rule_set.model_dump(mode="json")),
        clause_pack_sha256=pack.clause_pack_sha256,
        clause_pack=pack,
        protocol_integrity_gate_result_id=protocol.integrity_gate_result_id,
        evaluator_version=EVALUATOR_VERSION,
        requirements_scope_version="review-requirements-scope/v1",
        workflow_stages=tuple(stages),
        facts=facts,
        expectation_templates=tuple(sorted(templates, key=lambda item: item.template_id)),
        expectations=(expectation,),
        created_at=NOW,
    )
    draft = ReviewContextSnapshotV2.model_construct(**data, context_sha256="0" * 64)
    return ReviewContextSnapshotV2(
        **data,
        context_sha256=canonical_hash(
            draft.model_dump(mode="json", exclude={"context_sha256"})
        ),
    )


def _qualification_payload_for_messages(messages):
    """Synthetic clear success body; v6 must preserve empty reasons verbatim."""
    pair_ids = json.loads(messages[1]["content"][0]["text"])["required_pair_ids"]
    return {
        "results": [
            {
                "pair_id": pair_id,
                "source_admissibility": "admissible",
                "object_match": "supported",
                "attribute_match": "direct",
                "denial_scope": "compatible",
                "temporal_role": "not_applicable",
                "direct_operand_usable": "usable",
                "unresolved_reasons": [],
                "explanation": (
                    "native-text resting heart rate 72 bpm is a direct usable operand"
                ),
            }
            for pair_id in pair_ids
        ]
    }


def _synthetic_control_input(*, computation=True):
    from app.domain.contracts.protocol_controls import stable_protocol_control_obligation_group_id
    authority, rules, evidence, _, _, response = _synthetic_material(computation=computation)
    predicate = _positive_predicate(computation=computation)
    clause, span = predicate.source_clause, "synthetic-computation-span"
    spec = ControlAtomEvaluationSpec(
        determination_mode="deterministic", operation="value_comparison",
        proposition=clause, predicate=predicate, operand_attribute="value",
        time_purpose="not_applicable", observation_policy={"mode": "single" if computation == "single" else "unresolved", "scope": clause,
            "source_span_ids": [span], "source_excerpts": [clause]},
        source_span_ids=[span], source_excerpts=[clause],
    )
    atom = ControlObligationAtom(
        obligation_id="synthetic-computation-obligation", kind="reach_condition",
        statement=clause, evaluation=spec, source_span_ids=[span], source_excerpts=[clause],
    )
    control = ProtocolReviewControl(
        protocol_control_id="synthetic-computation-control", display_ordinal=1,
        protocol_version_id=authority.protocol_version_id, study_phase=StudyPhase.PHASE_III,
        title="合成计算要求", applicable_population="本节点受试者",
        obligation_expression=ControlObligationDnf(groups=[ControlObligationGroup(atoms=[atom],
            obligation_group_id=stable_protocol_control_obligation_group_id("synthetic-computation-candidate", 0))]),
        review_node_bindings=[dict(workflow_stage_id=STAGE_ID, review_stage="screening", role="decide_at_node")],
        minimum_evidence=[dict(
            evidence_key="synthetic-computation-evidence", fact_type="vital_sign",
            description="核对原始心率记录", due_stage="screening", workflow_stage_ids=[STAGE_ID],
            atom_refs=[dict(layer="obligation", group_index=0, atom_index=0)],
            source_policy=dict(requires_contemporaneous_objective_source=False,
                allows_screening_record_transcription=True, result_validity_status="not_specified",
                result_validity_constraint=None, source_span_ids=[span], source_excerpts=[clause]),
        )], source_span_ids=[span], source_structure_unit_ids=["synthetic-unit"],
    )
    publication = ControlCatalogPublication(
        project_id=authority.project_id, protocol_version_id=authority.protocol_version_id,
        rule_set_id=authority.rule_set_id, rule_set_revision=authority.rule_set_revision,
        rule_set_sha256=canonical_hash(rules.model_dump(mode="json")),
        source_job_id="synthetic-publication-job", source_job_payload_sha256="a" * 64,
        source_checkpoint_id="synthetic-checkpoint", source_checkpoint_sha256="b" * 64,
        gate_result_id="synthetic-publication-gate", created_at=NOW,
        workflow_stage_map={STAGE_ID: f"{authority.rule_set_id}:{authority.rule_set_revision}:{STAGE_ID}"},
        catalog=PublishedProtocolControlCatalog(
            catalog_id="synthetic-catalog", protocol_version_id=authority.protocol_version_id,
            protocol_document_sha256="c" * 64, study_phase=StudyPhase.PHASE_III,
            coverage_manifest_id="synthetic-coverage", allowed_source_span_ids=[span], controls=[control],
        ),
    )
    frozen = ControlBindingFrozenInput(publication=publication, evidence_input=evidence,
        frozen_input_sha256=control_binding_input_hash(publication, evidence))
    from app.projections.control_atom_binding_input import project_control_atom_identities
    identity, = project_control_atom_identities(publication)
    candidate = response["results"][0]
    return frozen, identity.identity_sha256, {"results": [dict(
        atom_identity_sha256=identity.identity_sha256, candidates=candidate["candidates"],
        fact_accounting=candidate["fact_accounting"],
    )]}


@pytest.mark.parametrize("old_contract,missing_request,source_check,qualified", [
    (False, False, False, False), (True, False, False, False), (False, True, False, False),
    (False, False, True, False), (False, False, True, True)])
def test_control_computation_raw_value_survives_receipts_but_not_direct_selection(
    session_factory, data_paths, monkeypatch, old_contract, missing_request, source_check, qualified,
):
    from app.services.control_binding_job import (
        JOB_TYPE as CONTROL_TYPE, ControlBindingJobExecutor, enqueue_control_candidates,
    )
    from app.llm.control_binding_candidates import build_control_binding_messages
    from app.llm.predicate_binding_candidates import SOURCE_COMPUTATION_BINDING_GUIDANCE

    computation = "single" if qualified else True
    frozen, identity, response = _synthetic_control_input(computation=computation)
    source_review = None
    if source_check:
        authority, rules, _, fact, episode, _ = _synthetic_material(computation=computation)
        source_review = _aligned_review_context(authority=authority, rule_set=rules,
            clinical_fact=fact, episode=episode, control_publication=frozen.publication)
        monkeypatch.setattr("app.storage.review_context_repository.ReviewContextV2Repository.get",
                            lambda _self, _context_id: source_review)
        monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_: rules)
    assert SOURCE_COMPUTATION_BINDING_GUIDANCE in build_control_binding_messages(frozen)[0]["content"]
    for path in ("app.services.control_binding_job", "app.services.binding_qualification"):
        monkeypatch.setattr(f"{path}.build_control_binding_frozen_input", lambda *args, **kwargs: frozen)
    routes = {lane: _route(lane=lane, **({"model": f"synthetic-{lane.value}"} if source_check else {}))
              for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    artifacts = ArtifactStore(data_paths)

    async def candidate_completion(*args):
        return PageCompletion(json.dumps(response, ensure_ascii=False), "stop", {})

    async def qualification_completion(route, messages, budget):
        # Deliberately overconfident identical answers must not bypass the host.
        assert SOURCE_COMPUTATION_BINDING_GUIDANCE in messages[0]["content"]
        return PageCompletion(json.dumps(_qualification_payload_for_messages(messages)), "stop", {})

    candidate = enqueue_control_candidates(session_factory,
        review_episode_id=frozen.evidence_input.authority.review_episode_id, routes=routes,
        **({"review_context_id": source_review.context_id} if source_review is not None else {}))
    assert JobRunner(session_factory, {CONTROL_TYPE: ControlBindingJobExecutor(
        session_factory, artifacts, routes, completion=candidate_completion)}).run_job(candidate.job_id)
    if missing_request:
        from app.services.binding_qualification_support import verify_completed_candidate_comparison
        from app.workflow.errors import StepFailure
        with session_factory() as session, session.begin():
            row = session.get(JobRecord, candidate.job_id)
            body = json.loads(row.payload_json)
            assert body.pop("request_messages_sha256s")
            row.payload_json, row.payload_sha256 = encode_value(body)
            with pytest.raises(InvalidJobDefinitionError, match="不能复用旧结果"):
                verify_completed_candidate_comparison(session, artifacts, candidate.job_id)
        executor = ControlBindingJobExecutor(session_factory, artifacts, routes, completion=candidate_completion)
        with pytest.raises(StepFailure) as failure:
            executor(SimpleNamespace(job_type=CONTROL_TYPE, job_payload=body))
        assert failure.value.error_code == "CONTROL_BINDING_REQUEST_CHANGED"
        return
    with session_factory() as session, session.begin():
        row = session.get(JobRecord, candidate.job_id)
        if old_contract:
            # Fault injection into the temporary fixture only. Old terminal outputs
            # cannot acquire a repaired identity just because the consumer changed.
            body = json.loads(row.payload_json)
            body["contract"] = "control-binding-candidate-job/v6"
            row.payload_json, row.payload_sha256 = encode_value(body)
    if old_contract:
        with pytest.raises(InvalidJobDefinitionError, match="官方谓词或控制候选"):
            enqueue_binding_qualification(session_factory, candidate_job_id=candidate.job_id,
                routes=routes, artifact_store=artifacts)
        return
    qualification = enqueue_binding_qualification(session_factory,
        candidate_job_id=candidate.job_id, routes=routes, artifact_store=artifacts)
    assert JobRunner(session_factory, {QUALIFICATION_TYPE: BindingQualificationJobExecutor(
        session_factory, artifacts, routes, completion=qualification_completion)}).run_job(qualification.job_id)
    source_job_id = None
    if source_check:
        from app.services.computation_input_job import (
            ComputationInputJobExecutor, enqueue_computation_input, verify_completed_computation_input,
        )
        async def source_completion(_route, messages, _budget):
            groups = json.loads(messages[1]["content"][0]["text"])["groups"]
            return PageCompletion(json.dumps({"results": [{"pair_id": group["group_id"],
                "descriptions": [{"pair_id": key, "token_kind": "unresolved", "date_role": "unresolved",
                                  **({"input_role": "raw_input", "input_excerpt": NATIVE_EXCERPT,
                                      "input_ref": group["computation"]["input_refs"][0]} if qualified else {}),
                                  "explanation": "本条只有一次读数，未写采集标识及日期。"}
                                 for key in group["sources"]["required_pair_ids"]],
                "relations": [], "unresolved_notes": [] if qualified else ["不能把单值当均值。"]}
                for group in groups]}), "stop", {})
        source = enqueue_computation_input(session_factory, candidate_job_id=candidate.job_id,
            context_id=source_review.context_id, routes=routes, artifact_store=artifacts)
        executor = ComputationInputJobExecutor(session_factory, artifacts, routes, completion=source_completion)
        assert JobRunner(session_factory, {executor.job_type: executor}).run_job(source.job_id)
        with session_factory() as session:
            evidence = verify_completed_computation_input(session, artifacts, source.job_id)
        assert evidence["summary"]["input_set_qualified"] is False
        assert len(evidence["summary"]["comparisons"]) == 1
        source_job_id = source.job_id
    with session_factory() as session:
        verified = verify_completed_binding_qualification(session, artifacts, qualification.job_id)
        record, = verified["summary"].pair_records
        assert record.fact_id == FACT_ID and record.locator_id == LOCATOR_ID
        assert record.structural.referenced_value == frozen.facts[0].value
        assert record.structural.operand_shape == "source_computation_input"
        assert "source_computation_input_set_unverified" in record.remaining_unverified
        assert record.dual_agreement and not record.authorized_clinical_adoption
        selections = build_receipt_verified_work_draft_selections(
            session, artifacts, qualification_job_id=qualification.job_id,
            computation_input_job_id=source_job_id)
    if source_check:
        assert selections.computation_input == source_job_id
        assert selections.computation_sources[0]["identity_sha256"] == identity
        selections.require_unchanged()
    outcome, = selections.identity_outcomes
    if qualified:
        assert selections.control_selections == {identity: [FACT_ID]}
        assert outcome.status == "usable"
        # Both official and cross-chapter consumers use the same sealed proof.
        from app.services.computation_atom_calculation import calculate_computation_atoms, computation_result_note
        from app.domain.expression import EvaluationContext
        from app.services.eligibility_review_projection import adapt_clinical_facts_v2
        from app.projections.control_calculation_experiment import evaluate_control_layers_experiment
        context = EvaluationContext(project_id=authority.project_id, subject_id=authority.subject_id,
            review_episode_id=authority.review_episode_id, evidence_snapshot_id=authority.evidence_snapshot_v2_id,
            anchor_dates=dict(frozen.evidence_input.episode.anchor_dates),
            accepted_fact_ids=[FACT_ID], facts=adapt_clinical_facts_v2(source_review.facts))
        evaluated = calculate_computation_atoms(selections, context)
        value = evaluated[identity]
        assert value.result.truth == TruthValue.TRUE
        assert value.resolution["exact_value"] == {"numerator": "72", "denominator": "1"}
        assert "1次采集" in computation_result_note(value)
        calculation = evaluate_control_layers_experiment(frozen,
            frozen_input_sha256=frozen.frozen_input_sha256, selections=selections.control_selections,
            computation_evaluations=evaluated)
        assert calculation.version == "control-calculation-experiment/v19"
        assert calculation.computation_evaluations[identity].result.truth == TruthValue.TRUE
        return
    assert selections.control_selections == {identity: []}
    assert outcome.status == "unresolved" and outcome.fact_ids == []
    assert any("source_computation_input_set_unverified" in reason
               for reason in outcome.unresolved_reasons)


def test_control_schema_forbids_semantic_computation_bypass():
    frozen, _, _ = _synthetic_control_input()
    spec = frozen.publication.catalog.controls[0].obligation_expression.groups[0].atoms[0].evaluation
    body = spec.model_dump(mode="json")
    body.update(determination_mode="semantic", operation=None)
    with pytest.raises(ValidationError, match="值比较"):
        ControlAtomEvaluationSpec.model_validate(body)


@pytest.mark.parametrize("computation", [False, True])
def test_request_identity_separates_changed_recipe_without_recreating_ordinary_job(
    session_factory, monkeypatch, computation,
):
    authority, _, frozen, *_ = _synthetic_material(computation=computation)
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    arguments = dict(review_episode_id=authority.review_episode_id,
                     component_ids=["component-a"], routes=routes)
    # Queue-identity fixture only: emulate the former missing fingerprint.
    # Its completed flag is not a read receipt or clinical acceptance proof.
    with monkeypatch.context() as legacy:
        legacy.setattr("app.services.predicate_binding_job.computation_request_hashes", lambda _: {})
        previous = enqueue_predicate_candidates(session_factory, **arguments)
    with session_factory() as session, session.begin():
        row = session.get(JobRecord, previous.job_id)
        row.state = "completed"
        previous_bytes = row.payload_json
    current = enqueue_predicate_candidates(session_factory, **arguments)
    repeated = enqueue_predicate_candidates(session_factory, **arguments)
    assert repeated.job_id == current.job_id and not repeated.created
    assert (current.job_id != previous.job_id) is computation
    with session_factory() as session:
        assert session.get(JobRecord, previous.job_id).payload_json == previous_bytes
        body = json.loads(session.get(JobRecord, current.job_id).payload_json)
        assert bool(body.get("request_messages_sha256s")) is computation


@pytest.mark.parametrize("extra_pair", [False, True])
def test_shared_control_semantic_selection_checks_all_source_pairs(extra_pair):
    meta = SimpleNamespace(atom=SimpleNamespace(time_constraint=None, evaluation=SimpleNamespace(
        observation_policy=SimpleNamespace(mode="single", selection=None))))
    records = [SimpleNamespace(pair_id="p1", identity_sha256="i", fact_id="f1", fact_attribute="value")]
    if extra_pair:
        records.append(SimpleNamespace(pair_id="p2", identity_sha256="i", fact_id="f2", fact_attribute="value"))
    result = _select_control_semantic_evidence(frozen=None, identity="i", meta=meta,
        proposition_relations=[dict(identity_sha256="i", pair_id="p1", fact_id="f1")],
        records=records, usable=records[:1], accounting=[], review_context=None)
    assert result[:2] == (["f1"], ["p1"])
    assert result[2] == (["single_observation_relations_incomplete"] if extra_pair else [])


def test_shared_control_ordering_preserves_selected_ids(monkeypatch):
    # Wiring seam only: the real ordering algorithm is tested separately.
    from app.services.semantic_observation_selection import SemanticObservationSelection
    monkeypatch.setattr("app.services.qualified_binding_selection._semantic_ordering",
        lambda **kwargs: SemanticObservationSelection(fact_ids=("selected",), pair_ids=("selected-pair",),
            reasons=(), ordering={"selected_fact_ids": ["selected"]}))
    meta = SimpleNamespace(atom=SimpleNamespace(time_constraint=None, evaluation=SimpleNamespace(
        time_purpose="not_applicable", observation_policy=SimpleNamespace(mode="single", selection=object()))))
    result = _select_control_semantic_evidence(frozen=None, identity="i", meta=meta,
        proposition_relations=[], records=[], usable=[], accounting=[], review_context=object())
    assert result == (["selected"], ["selected-pair"], [], {"selected_fact_ids": ["selected"]})


def test_real_semantic_ordering_never_accepts_empty_relations():
    from app.services.semantic_observation_selection import select_semantic_ordered_observation
    policy = SimpleNamespace(mode="single", selection=SimpleNamespace(
        criterion="latest", ordering_attribute="date_range"))
    result = select_semantic_ordered_observation(policy=policy, facts={}, relations=[],
        usable_records=[], source_records=[], accounting=[], time_constraint=None,
        anchor_dates={}, time_purpose="not_applicable", review_context=object())
    assert result.fact_ids == result.pair_ids == ()
    assert result.reasons == ("semantic_evidence_unverified",)


@pytest.mark.parametrize("version", ["v31", "v32", "v33"])
def test_consumer_upgrade_reads_history_without_relabeling_its_authority(version):
    from app.domain.contracts.qualified_binding_selection import QualificationAdoptionAuthorization
    reference = dict(job_id="synthetic-evidence", summary_logical_sha256="a" * 64,
        summary_artifact_sha256="b" * 64, evaluation_sha256="c" * 64)
    authorization = QualificationAdoptionAuthorization(
        authorization_id="synthetic-authorization", authorizing_service="synthetic-service",
        qualification_job_id="synthetic-qualification", candidate_family="control",
        consumer_algorithm_version=f"qualified-binding-selection-consumer/{version}",
        frozen_input_sha256="a" * 64, comparison_sha256="b" * 64,
        summary_logical_sha256="c" * 64, summary_artifact_sha256="d" * 64,
        approved_evaluation_evidence_sha256="e" * 64,
        route_identities={lane: dict(provider="synthetic", base_url="http://synthetic.invalid",
            model=lane, reasoning_effort="high", max_tokens=65536) for lane in ("main-A", "main-B")},
        frequency_evidence=reference, observation_relation=reference,
    )
    restored = QualificationAdoptionAuthorization.model_validate(authorization.model_dump(mode="json"))
    assert restored == authorization
    assert restored.consumer_algorithm_version.endswith(f"/{version}")


@pytest.mark.parametrize("case", ["normal", "normal_sources", "rejected", "old_version", "computation", "computation_input",
    "computation_candidate_identity_missing", "computation_qualification_identity_missing",
    "computation_qualification_identity_changed", "computation_sources", "computation_sources_length",
    "computation_sources_changed", "computation_sources_request_changed", "computation_sources_missing_field",
    "computation_sources_qualified", "prescription_history", "purchase_history",
    "prescription_duration", "purchase_duration", "prescription_last_use", "purchase_last_use"])
def test_receipt_verified_work_draft_consumes_normal_clause_and_keeps_restricted_sibling(
    session_factory, data_paths, monkeypatch, case,
):
    is_computation = case.startswith("computation")
    is_medication = case.startswith(("prescription_", "purchase_"))
    history_supported = is_medication and case.endswith("_history")
    is_withheld = (case == "rejected" or is_computation and case != "computation_sources_qualified"
                   or is_medication and not history_supported)
    medication = {}
    if is_medication:
        record = "2025-04-12" + ("处方：示例药物，每日一次" if case.startswith("prescription_")
                                 else "购药记录：示例药物一盒")
        clause = ("曾有示例药物用药史" if history_supported else
                  "示例药物连续实际使用至少30天" if case.endswith("_duration") else
                  "示例药物末次实际服药日期为2025-04-12")
        medication = dict(record=record, positive=AtomicPredicate(
            predicate_id=POSITIVE_PREDICATE_ID, subject="medication_history", attribute="source_statement",
            comparator="exists", source_clause=clause, semantic_proposition=clause,
            observation_policy={"mode": "any", "scope": "本项用药史记录",
                                "source_span_ids": ["synthetic-history-clause"], "source_excerpts": [clause]},
        ))
    authority, rule_set, frozen, clinical_fact, episode, candidate_response = (
        _synthetic_material(computation="single" if case == "computation_sources_qualified" else is_computation,
                            **medication)
    )
    if case == "computation_input":
        candidate_response["results"][0]["candidates"][0]["attribute_correspondence"] = "derivation_operand"
    source_review = None
    if case.startswith("computation_sources") or case == "normal_sources" or is_medication:
        source_review = _aligned_review_context(authority=authority, rule_set=rule_set,
                                               clinical_fact=clinical_fact, episode=episode)
        monkeypatch.setattr("app.storage.review_context_repository.ReviewContextV2Repository.get",
                            lambda _self, _context_id: source_review)
        monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_: rule_set)
    # Existing producer jobs rebuild frozen input from the DB; this fixture keeps
    # the synthetic authored material stable through that existing seam.
    monkeypatch.setattr(
        "app.services.predicate_binding_job.build_predicate_binding_frozen_input",
        lambda *args, **kwargs: frozen,
    )
    monkeypatch.setattr(
        "app.services.binding_qualification.build_predicate_binding_frozen_input",
        lambda *args, **kwargs: frozen,
    )

    routes = {
        lane: _route(lane=lane, **({"model": f"synthetic-{lane.value}"}
                                 if source_review is not None else {}))
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    }
    artifacts = ArtifactStore(data_paths)

    async def candidate_completion(*_args):
        return PageCompletion(
            json.dumps(candidate_response, ensure_ascii=False), "stop", {},
        )

    async def qualification_completion(route, messages, budget):
        del route, budget
        payload = _qualification_payload_for_messages(messages)
        if case == "rejected":
            for judgment in payload["results"]:
                judgment["attribute_match"] = "rejected"
                judgment["unresolved_reasons"] = ["This operand is not the requested attribute."]
        if case == "computation_input":
            for judgment in payload["results"]:
                judgment.update(attribute_match="derivation_operand", direct_operand_usable="not_usable",
                    unresolved_reasons=["Selected input set and arithmetic have not been qualified."],
                    explanation="The original individual measurement remains a computation input.")
        if is_medication:
            for judgment in payload["results"]:
                judgment["explanation"] = "原文仅记载处方或购药，保留该记录日期，不推测实际给药。"
                if not history_supported:
                    judgment.update(attribute_match="uncertain", direct_operand_usable="not_usable",
                                    unresolved_reasons=["本记录不能证明连续疗程或末次实际服药日期。"])
        return PageCompletion(
            json.dumps(payload, ensure_ascii=False),
            "stop",
            {},
        )

    candidate = enqueue_predicate_candidates(
        session_factory,
        review_episode_id=authority.review_episode_id,
        component_ids=["component-a"],
        routes=routes,
        **({"review_context_id": source_review.context_id} if source_review is not None else {}),
    )
    assert JobRunner(
        session_factory,
        {
            CANDIDATE_TYPE: PredicateBindingJobExecutor(
                session_factory, artifacts, routes, completion=candidate_completion,
            )
        },
    ).run_job(candidate.job_id)

    if case == "computation_candidate_identity_missing":
        from app.services.binding_qualification_support import verify_completed_candidate_comparison
        from app.workflow.errors import StepFailure
        with session_factory() as session, session.begin():
            row = session.get(JobRecord, candidate.job_id)
            body = json.loads(row.payload_json)
            assert body.pop("request_messages_sha256s")
            row.payload_json, row.payload_sha256 = encode_value(body)
            with pytest.raises(InvalidJobDefinitionError, match="不能复用旧结果"):
                verify_completed_candidate_comparison(session, artifacts, candidate.job_id)
        executor = PredicateBindingJobExecutor(session_factory, artifacts, routes,
                                              completion=candidate_completion)
        with pytest.raises(StepFailure) as failure:
            executor(SimpleNamespace(job_type=CANDIDATE_TYPE, job_payload=body))
        assert failure.value.error_code == "PREDICATE_REQUEST_CHANGED"
        return

    legacy_qualification = None
    if case == "computation":
        # Isolated queue regression: old completed state alone cannot substitute
        # for the changed request, and its payload is never rewritten.
        with monkeypatch.context() as legacy:
            legacy.setattr("app.services.binding_qualification.qualification_request_hashes", lambda *_: {})
            legacy_qualification = enqueue_binding_qualification(session_factory,
                candidate_job_id=candidate.job_id, routes=routes, artifact_store=artifacts)
        with session_factory() as session, session.begin():
            row = session.get(JobRecord, legacy_qualification.job_id)
            row.state = "completed"
            legacy_bytes = row.payload_json

    qualification = enqueue_binding_qualification(
        session_factory,
        candidate_job_id=candidate.job_id,
        routes=routes,
        artifact_store=artifacts,
    )
    if legacy_qualification is not None:
        assert qualification.job_id != legacy_qualification.job_id
        repeated = enqueue_binding_qualification(session_factory, candidate_job_id=candidate.job_id,
            routes=routes, artifact_store=artifacts)
        assert repeated.job_id == qualification.job_id and not repeated.created
        with session_factory() as session:
            assert session.get(JobRecord, legacy_qualification.job_id).payload_json == legacy_bytes
    assert JobRunner(
        session_factory,
        {
            QUALIFICATION_TYPE: BindingQualificationJobExecutor(
                session_factory,
                artifacts,
                routes,
                completion=qualification_completion,
            )
        },
    ).run_job(qualification.job_id)

    proposition_job_id = None
    if is_medication:
        from app.services.proposition_evidence_job import (
            JOB_TYPE as PROPOSITION_TYPE, PropositionEvidenceJobExecutor, enqueue_proposition_evidence,
        )

        async def proposition_completion(route, messages, budget):
            request = json.loads(messages[1]["content"][0]["text"])
            assert MEDICATION_HISTORY_GUIDANCE in messages[0]["content"]
            results = []
            for pair in request["pairs"]:
                condition = request["conditions"][pair["identity_sha256"]]["condition"]
                results.append(dict(pair_id=pair["pair_id"], proposition_sha256=condition["proposition_sha256"],
                    scope="pair_local", scope_correspondence="supported", scope_quote=record,
                    assertion_extent="individual", scope_population="unresolved", population_quote=None,
                    prospective_evidence=None, target_correspondence="supported", node_correspondence="supported",
                    investigator_attribution="not_applicable", relation="entails" if history_supported else "undetermined",
                    basis="explicit_statement" if history_supported else "insufficient", quoted_evidence=record,
                    explanation="按处方或购药原文核对用药史，记录日期不等同于实际给药日期。",
                    unresolved_reasons=[] if history_supported else ["实际服药的日期或持续时间未记载。"]))
            return PageCompletion(json.dumps({"results": results}, ensure_ascii=False), "stop", {})

        proposition = enqueue_proposition_evidence(session_factory, candidate_job_id=candidate.job_id,
            context_id=source_review.context_id, routes=routes, artifact_store=artifacts)
        assert JobRunner(session_factory, {PROPOSITION_TYPE: PropositionEvidenceJobExecutor(
            session_factory, artifacts, routes, completion=proposition_completion)}).run_job(proposition.job_id)
        proposition_job_id = proposition.job_id

    if case in {"computation_qualification_identity_missing", "computation_qualification_identity_changed"}:
        from app.workflow.errors import StepFailure
        with session_factory() as session, session.begin():
            row = session.get(JobRecord, qualification.job_id)
            body = json.loads(row.payload_json)
            if case.endswith("missing"):
                assert body.pop("request_messages_sha256s")
            else:
                key = next(iter(body["request_messages_sha256s"]))
                body["request_messages_sha256s"][key] = "f" * 64
            row.payload_json, row.payload_sha256 = encode_value(body)
            with pytest.raises(InvalidJobDefinitionError, match="不能复用旧结果"):
                verify_completed_binding_qualification(session, artifacts, qualification.job_id)
        executor = BindingQualificationJobExecutor(session_factory, artifacts, routes,
                                                   completion=qualification_completion)
        with pytest.raises(StepFailure) as failure:
            executor(SimpleNamespace(job_type=QUALIFICATION_TYPE, job_payload=body))
        assert failure.value.error_code == "BINDING_QUALIFICATION_REQUEST_CHANGED"
        return

    computation_job_id = None
    if case.startswith("computation_sources") or case == "normal_sources":
        from app.services.computation_input_job import (
            ComputationInputJobExecutor, enqueue_computation_input, verify_completed_computation_input,
        )
        from app.workflow.errors import StepFailure
        calls = []
        async def source_completion(route, messages, budget):
            request = json.loads(messages[1]["content"][0]["text"])
            calls.append((route.lane.value, budget))
            if case == "computation_sources_length" and budget == 65536:
                return PageCompletion("", "length", {})
            return PageCompletion(json.dumps({"results": [{
                "pair_id": group["group_id"], "descriptions": [{
                    "pair_id": pair_id, "collection_token": None, "token_kind": "unresolved",
                    **({"input_role": "raw_input", "input_excerpt": NATIVE_EXCERPT,
                        "input_ref": group["computation"]["input_refs"][0]}
                       if case == "computation_sources_qualified" else {}),
                    "collection_excerpt": None, "date_role": "unresolved", "date_text": None,
                    "date_excerpt": None, "explanation": "原文仅有读数，没有明确采集标识或日期角色。",
                } for pair_id in group["sources"]["required_pair_ids"]],
                "relations": [], "unresolved_notes": ([] if case == "computation_sources_qualified"
                                                       else ["不能凭单个读数替代两次均值。"]),
            } for group in request["groups"]]}, ensure_ascii=False), "stop", {})
        source_job = enqueue_computation_input(session_factory, candidate_job_id=candidate.job_id,
            context_id=source_review.context_id, routes=routes, artifact_store=artifacts)
        repeated = enqueue_computation_input(session_factory, candidate_job_id=candidate.job_id,
            context_id=source_review.context_id, routes=routes, artifact_store=artifacts)
        assert repeated.job_id == source_job.job_id and not repeated.created
        executor = ComputationInputJobExecutor(session_factory, artifacts, routes, completion=source_completion)
        assert JobRunner(session_factory, {executor.job_type: executor}).run_job(source_job.job_id)
        with session_factory() as session:
            source_evidence = verify_completed_computation_input(session, artifacts, source_job.job_id)
        assert source_evidence["summary"]["accepted"] is False
        assert source_evidence["summary"]["input_set_qualified"] is False
        if case == "normal_sources":
            assert source_evidence["summary"]["comparisons"] == []
            assert source_evidence["payload"]["identity_coverage"] == []
            assert calls == []
        else:
            comparison, = source_evidence["summary"]["comparisons"]
        if case != "normal_sources":
            assert comparison["agreed_source_descriptions"][0]["token_kind"] == "unresolved"
            assert comparison["agreed_relationships"] == []
        if case == "computation_sources_request_changed":
            with session_factory() as session, session.begin():
                row = session.get(JobRecord, source_job.job_id)
                body = json.loads(row.payload_json)
                assert body.pop("request_messages_sha256s")
                row.payload_json, row.payload_sha256 = encode_value(body)
                with pytest.raises(InvalidJobDefinitionError, match="实际请求已变化"):
                    verify_completed_computation_input(session, artifacts, source_job.job_id)
            with pytest.raises(StepFailure) as failure:
                executor(SimpleNamespace(job_type=executor.job_type, job_payload=body))
            assert failure.value.error_code == "COMPUTATION_INPUT_REQUEST_CHANGED"
            assert len(calls) == 2
            return
        if case == "computation_sources_missing_field":
            with session_factory() as session, session.begin():
                row = session.get(JobRecord, source_job.job_id)
                body = json.loads(row.payload_json)
                assert body.pop("identity_coverage")
                row.payload_json, row.payload_sha256 = encode_value(body)
                with pytest.raises(InvalidJobDefinitionError, match="缺少原文或版本字段"):
                    verify_completed_computation_input(session, artifacts, source_job.job_id)
            with pytest.raises(StepFailure) as failure:
                executor(SimpleNamespace(job_type=executor.job_type, job_payload=body))
            assert failure.value.error_code == "COMPUTATION_INPUT_INPUT_CHANGED"
            assert len(calls) == 2
            return
        if case == "computation_sources_length":
            assert sorted(calls) == [("main-A", 65536), ("main-A", 131072),
                                    ("main-B", 65536), ("main-B", 131072)]
            assert all(len(ids) == 2 for ids in comparison["lane_receipt_sha256s"].values())
        elif case != "normal_sources":
            assert len(calls) == 2
        if case == "computation_sources_changed":
            changed = rule_set.model_copy(deep=True)
            changed.rules[0].source_text += "来源已更新"
            monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_: changed)
            with session_factory() as session, pytest.raises(InvalidJobDefinitionError, match="方案内容不一致"):
                verify_completed_computation_input(session, artifacts, source_job.job_id)
            with pytest.raises(StepFailure) as failure:
                executor(SimpleNamespace(job_type=executor.job_type, job_payload=source_evidence["payload"]))
            assert failure.value.error_code == "COMPUTATION_INPUT_INPUT_CHANGED"
            assert len(calls) == 2
            return
        computation_job_id = source_job.job_id

    observation_job_id = None
    if case == "computation_sources_qualified":
        from app.services.observation_relation_job import (
            ObservationRelationJobExecutor, enqueue_observation_relation, verify_completed_observation_relation,
        )
        async def unexpected_observation_read(*_args):
            raise AssertionError("普通计算不得伪造复查角色再读取一次")
        observation_job = enqueue_observation_relation(session_factory,
            candidate_job_id=candidate.job_id, context_id=source_review.context_id,
            routes=routes, artifact_store=artifacts)
        observation_executor = ObservationRelationJobExecutor(session_factory, artifacts, routes,
                                                              completion=unexpected_observation_read)
        assert JobRunner(session_factory, {observation_executor.job_type: observation_executor}).run_job(
            observation_job.job_id)
        with session_factory() as session:
            observation = verify_completed_observation_relation(session, artifacts, observation_job.job_id)
        assert observation["pairs"] == [] and observation["summary"]["comparisons"] == []
        observation_job_id = observation_job.job_id

    with session_factory() as session:
        assert JobStore(session).get_job(candidate.job_id).state == "completed"
        assert JobStore(session).get_job(qualification.job_id).state == "completed"
        if case == "old_version":
            # Fault injection only into this ephemeral test DB, never real history.
            row = session.get(JobRecord, qualification.job_id)
            payload = json.loads(row.payload_json)
            payload["prompt_version"] = "binding-qualification/v5"
            row.payload_json, row.payload_sha256 = encode_value(payload)
            session.flush()
            with pytest.raises(InvalidJobDefinitionError, match="当前官方版本"):
                build_receipt_verified_work_draft_selections(
                    session, artifacts, qualification_job_id=qualification.job_id,
                )
            return
        selections = build_receipt_verified_work_draft_selections(
            session,
            artifacts,
            qualification_job_id=qualification.job_id,
            proposition_evidence_job_id=proposition_job_id,
            computation_input_job_id=computation_job_id,
            observation_relation_job_id=observation_job_id,
        )
        if computation_job_id is not None:
            assert selections.computation_input == computation_job_id
            assert len(selections.computation_sources) == (0 if case == "normal_sources" else 1)
            selections.require_unchanged()
            if selections.computation_sources:
                selections.computation_sources[0]["input_set_qualified"] = True
                with pytest.raises(ValueError, match="已变化"):
                    selections.require_unchanged()
                selections.computation_sources[0]["input_set_qualified"] = False
                selections.require_unchanged()
        if is_computation:
            verified = verify_completed_binding_qualification(session, artifacts, qualification.job_id)
            record, = verified["summary"].pair_records
            assert record.fact_id == FACT_ID and record.locator_id == LOCATOR_ID
            assert record.structural.referenced_value == clinical_fact.value
            assert record.structural.operand_shape == "source_computation_input"
            assert "source_computation_input_set_unverified" in record.remaining_unverified
            assert record.authorized_clinical_adoption is False
            if case == "computation_input":
                assert all(item.attribute_match == "derivation_operand" for item in record.lane_judgments.values())
            else:
                # Even identical overconfident answers cannot turn a reading into a mean.
                assert record.dual_agreement
                assert all(item.direct_operand_usable == "usable" for item in record.lane_judgments.values())

    assert isinstance(selections, ReceiptVerifiedWorkDraftSelections)
    assert selections.candidate_family == "predicate"
    assert selections.qualification_job_id == qualification.job_id
    assert set(selections.predicate_fact_ids_by_component) == {"component-a"}
    assert selections.predicate_fact_ids_by_component["component-a"] == {
        POSITIVE_PREDICATE_ID: [] if is_withheld else [FACT_ID],
        COUNTER_PREDICATE_ID: [],
    }
    outcomes = {item.identity_sha256: item for item in selections.identity_outcomes}
    assert len(outcomes) == 2
    usable = [
        item for item in selections.identity_outcomes if item.status == "usable"
    ]
    unresolved = [
        item for item in selections.identity_outcomes if item.status == "unresolved"
    ]
    assert len(usable) == (0 if is_withheld else 1)
    if usable:
        assert usable[0].fact_ids == [FACT_ID]
        assert usable[0].unresolved_reasons == []
    assert len(unresolved) == (2 if is_withheld else 1)
    assert unresolved[0].fact_ids == []
    assert unresolved[0].unresolved_reasons
    assert _selected_fact_ids_by_identity(selections) == (
        {} if is_withheld else {
            usable[0].identity_sha256: {FACT_ID},
        }
    )
    # Expectations come from the authored synthetic fixture, not model output.
    gold = {
        "version": GOLD_SPLIT_VERSION, "qualification_job_id": qualification.job_id,
        "annotated_by": "synthetic fixture author, not clinical gold",
        "entries": [{
            "predicate_id": POSITIVE_PREDICATE_ID,
            "predicate_identity_sha256": (
                frozen.components[0].trigger_predicates[0].predicate_identity_sha256
            ),
            "expected_fact_ids": [FACT_ID],
        }],
    }
    with session_factory() as session:
        evaluation = build_binding_evaluation_manifest(
            session, artifacts, qualification_job_id=qualification.job_id,
            gold_split=gold, scoring_version="synthetic-fixture/v1",
        )
    # This evaluation has neither computation inputs nor proposition companion
    # receipts; it must not borrow the richer work-draft's evidence authority.
    assert evaluation["aggregate"]["selected_total"] == (0 if is_withheld or is_computation or is_medication else 1)
    manifest = read_binding_evaluation(artifacts, evaluation["manifest_sha256"])
    report = json.loads(artifacts.read_by_sha("raw_response", manifest.scoring_report_sha256))
    report["version"] = "binding-evaluation-scoring-report/v1"
    old_report = artifacts.put("raw_response", json.dumps(report).encode())
    old_manifest = manifest.model_copy(update={"scoring_report_sha256": old_report.sha256})
    old_artifact = artifacts.put("evaluation_manifest", old_manifest.model_dump_json().encode())
    # History is readable, but it cannot authorize new use of current scoring.
    assert read_method_evaluation(artifacts, old_artifact.sha256) == old_manifest
    with pytest.raises(ScopeViolationError, match="计分版本"):
        read_binding_evaluation(artifacts, old_artifact.sha256)

    review = _aligned_review_context(
        authority=authority,
        rule_set=rule_set,
        clinical_fact=clinical_fact,
        episode=episode,
    )
    assert review.clause_pack.projection_version == "clause-pack/v4"
    restricted = review.clause_pack.restricted_clauses
    assert [item.clause_id for item in restricted] == ["component-restricted-sibling"]
    before_restricted = [item.model_dump(mode="json") for item in restricted]

    calculation = calculate_frozen_review(
        review,
        rule_set,
        work_draft_selections=selections,
    )
    assert [item.rule_component_id for item in calculation.components] == ["component-a"]
    assert {item.rule_component_id for item in calculation.components}.isdisjoint(
        {item.clause_id for item in review.clause_pack.restricted_clauses}
    )
    assert [
        item.model_dump(mode="json") for item in review.clause_pack.restricted_clauses
    ] == before_restricted
    if case in {"normal", "normal_sources", "computation_sources_qualified"} or history_supported:
        assert calculation.components[0].result.decision == ComponentDecision.EXCLUSION_TRIGGERED
        assert calculation.components[0].result.gaps == frozenset()
        if is_computation:
            value, = calculation.computation_atom_evaluations["predicate"].values()
            assert value.resolution["exact_value"] == {"numerator": "72", "denominator": "1"}
            assert value.result.used_fact_ids == [FACT_ID]
            assert value.resolution["input_qualification"]["input_set_qualified"] is True
            # A later caller still cannot supply the individual raw value as an aggregate.
            from app.domain.expression import evaluate_calculated_numeric_value
            from fractions import Fraction
            assert evaluate_calculated_numeric_value(
                _positive_predicate(computation="single"), value=Fraction(72), unit="bpm").truth == TruthValue.UNKNOWN
    else:
        assert calculation.components[0].result.decision != ComponentDecision.EXCLUSION_TRIGGERED
        assert calculation.components[0].result.gaps
        if is_computation:
            assert GapType.CALCULATION_CAPABILITY_UNAVAILABLE in calculation.components[0].result.gaps
            assert GapType.PROFESSIONAL_JUDGMENT not in calculation.components[0].result.gaps
            # A qualified individual reading is not a qualified selected mean.
            assert review.clause_pack.clauses[0].expression.children[0].predicate.source_computation is not None
