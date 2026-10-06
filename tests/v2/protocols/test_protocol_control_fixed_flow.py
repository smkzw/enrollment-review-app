"""Connected front-author checks; no model or clinical material is used."""
from __future__ import annotations

import json

import pytest

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentResponse, ProtocolControlAgentRunner,
)
from app.agents.protocol_control_fixed_flow import (
    BASELINE, FIXED_FLOW, prepare_front_stage_flow, supports_front_stage_flow,
    workflow_template,
)
from app.agents.protocol_control_source_interpretation import (
    SourceTargetReview, SOURCE_TARGET_REVIEW_VERSION,
    SourceTargetReviewValidationError, SourceInterpretationValidationError,
    validate_source_interpretation, validate_source_target_review,
)
from app.domain.contracts.protocol_controls import KnownOfficialRuleTarget, KnownRequiredProcedureTarget
from app.services.protocol_control_execution import _validate_saved_source_review
from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _stage_bound_example, _synthetic_policy_checks_from_prompt,
)


def _example():
    batch, inventory, review, selection = _stage_bound_example()
    batch.owned_units = batch.owned_units[:1]
    batch.owned_structure_unit_ids = [batch.owned_units[0].structure_unit_id]
    inventory.units_without_statement = []
    inventory.statements[0].decision_functions = ["action"]
    selection.result_requirement = "action_only"
    return batch, inventory, review, selection


def _separate_heading_example():
    batch, inventory, review, selection = _example()
    unit = batch.owned_units[0]
    scope = inventory.statements[0].scope_quote
    unit.excerpt = inventory.statements[0].quoted_text
    unit.heading_path = ["研究流程", scope]
    unit.source_order = 20
    heading = unit.model_copy(deep=True)
    heading.structure_unit_id = "scope-heading"
    heading.source_ref = "generic.body.p18"
    heading.member_source_refs = [heading.source_ref]
    heading.source_span_ids = ["span:heading"]
    heading.source_order = 18
    heading.excerpt = scope
    batch.context_units = [heading]
    batch.context_structure_unit_ids = [heading.structure_unit_id]
    batch.context_source_span_ids = heading.source_span_ids
    inventory.statements[0].decision_functions = ["action", "time_validity"]
    return batch, inventory, review, selection


def test_separate_heading_is_preserved_through_hydration_and_saved_consumer():
    batch, inventory, review, selection = _separate_heading_example()
    transport = _Transport(review, selection)
    assert supports_front_stage_flow(batch, inventory)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    candidate = restored.final_output.candidates[0].semantics
    citation = candidate.review_node_bindings[0].scope_citation
    assert citation.structure_unit_id == "scope-heading"
    assert citation.source_span_ids == ["span:heading"]
    atom = candidate.obligation_expression.groups[0].atoms[0]
    assert atom.source_excerpts == [inventory.statements[0].quoted_text]
    assert atom.source_span_ids == batch.owned_units[0].source_span_ids
    assert candidate.source_structure_unit_ids == [batch.owned_units[0].structure_unit_id]
    assert "span:heading" not in candidate.source_span_ids


@pytest.mark.parametrize("defect", ["missing", "other_section", "later", "ambiguous", "context_action", "unlocated_heading"])
def test_unproven_heading_fails_front_preflight_without_model_calls(defect):
    batch, inventory, review, selection = _separate_heading_example()
    heading = batch.context_units[0]
    if defect == "missing":
        batch.context_units = []
    elif defect == "other_section":
        heading.heading_path = ["其他章节", heading.excerpt]
    elif defect == "later":
        heading.source_order = 21
    elif defect == "unlocated_heading":
        heading.heading_path = []
    elif defect == "ambiguous":
        another = heading.model_copy(deep=True)
        another.structure_unit_id = "another-heading"
        another.source_span_ids = ["span:another"]
        batch.context_units.append(another)
    else:
        heading.excerpt += "：另须完成检查。"
    assert not supports_front_stage_flow(batch, inventory)
    transport = _Transport(review, selection)
    result = prepare_front_stage_flow(batch, inventory, transport, lambda output: None)
    assert result.error is not None and transport.calls == []


@pytest.mark.parametrize("mutation", ["excerpt", "path", "order", "span", "deleted_citation", "body_identity"])
def test_saved_heading_dependency_changes_are_rejected(mutation):
    batch, inventory, review, selection = _separate_heading_example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    if mutation == "deleted_citation":
        result.final_output.candidates[0].semantics.review_node_bindings[0].scope_citation = None
    elif mutation == "body_identity":
        result.final_output.candidates[0].semantics.review_node_bindings[0].scope_citation.structure_unit_id = batch.owned_units[0].structure_unit_id
    else:
        heading = batch.context_units[0]
        if mutation == "excerpt":
            heading.excerpt += "（修订）"
        elif mutation == "path":
            heading.heading_path[0] = "另一章节"
        elif mutation == "order":
            heading.source_order = 17
        else:
            heading.source_span_ids = ["span:changed-heading"]
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, result)


def test_historical_inline_binding_dump_does_not_gain_null_citation():
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentWireNode
    from app.domain.contracts.protocol_controls import ReviewNodeBinding

    node = {"workflow_stage_id": "stage:screening:one", "review_stage": "screening",
            "role": "decide_at_node", "guidance": None}
    assert ProtocolControlAgentWireNode.model_validate(node).model_dump(mode="json") == node
    assert "scope_citation" not in ReviewNodeBinding.model_validate(node).model_dump(mode="json")


@pytest.mark.parametrize("policy_known", [False, True])
def test_separate_heading_survives_real_catalog_materialization(policy_known):
    from datetime import datetime, timezone
    from app.domain.contracts.control_evidence_policy import ControlEvidenceSourcePolicy
    from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
    from app.projections.control_atom_binding_input import project_control_atom_identities
    from app.services.binding_qualification_support import _source_policies_for_control
    from app.domain.contracts.rules import WorkflowStage
    from app.agents.protocol_control_deconstructor import hydrate_protocol_control_agent_output
    from app.agents.protocol_control_fixed_flow import pending_front_wire
    from app.protocols.protocol_control_planning import plan_protocol_control_batches
    from app.protocols.control_catalog_materialization import materialize_control_catalog
    from tests.v2.protocols.test_slice58c_protocol_control_gate import _manifest

    previous, inventory, review, selection = _separate_heading_example()
    if policy_known:
        original = inventory.statements[0].quoted_text
        quote = original + "；采用同期原始知情同意记录，不另设结果有效期。"
        previous.owned_units[0].excerpt = quote
        inventory.statements[0].quoted_text = quote
        review.source_action_excerpt = quote
        selection.action_excerpt = selection.obligation_statement = quote
        selection.source_policy = ControlEvidenceSourcePolicy(
            requires_contemporaneous_objective_source=True,
            allows_screening_record_transcription=False,
            result_validity_status="not_specified", result_validity_constraint=None,
            source_span_ids=previous.owned_units[0].source_span_ids, source_excerpts=[quote],
        )
    manifest = _manifest(units=[*previous.context_units, *previous.owned_units],
                         dispositions=[], claims_full_coverage=False)
    plan = plan_protocol_control_batches(
        manifest, max_owned_units_per_batch=1,
        workflow_stages=[WorkflowStage(
            workflow_stage_id=item.workflow_stage_id, stage=item.review_stage,
            display_name=item.display_name, visit_instance=item.visit_instance,
            visit_window=item.visit_window,
        ) for item in previous.known_workflow_stage_targets],
    )
    results = []
    for batch in plan.batches:
        if inventory.statements[0].structure_unit_id in batch.owned_structure_unit_ids:
            result = ProtocolControlAgentRunner().run(
                batch, _Transport(review, selection), resume_source_interpretation=inventory,
                workflow_variant=FIXED_FLOW,
                output_validator=lambda out: validate_protocol_control_batch_candidates(batch, out),
            )
            assert result.final_output is not None
            _validate_saved_source_review(batch, result)
            results.append(result.final_output)
        else:
            wire = pending_front_wire(batch)
            for disposition in wire.dispositions:
                disposition.disposition = "supporting_or_supplement"
                disposition.notes = "本段为审核时期标题，不含独立动作要求。"
            results.append(hydrate_protocol_control_agent_output(wire, batch))
    catalog = materialize_control_catalog(
        coverage_manifest=manifest, plan=plan, batch_dispositions=results,
        rule_component_ids=[],
    )
    assert len(catalog.controls) == 1
    citation = catalog.controls[0].review_node_bindings[0].scope_citation
    assert citation.structure_unit_id == "scope-heading"
    assert catalog.controls[0].source_structure_unit_ids == [inventory.statements[0].structure_unit_id]
    publication = ControlCatalogPublication(
        project_id="synthetic-source-policy", protocol_version_id=catalog.protocol_version_id,
        rule_set_id="synthetic-rules", rule_set_revision=1, rule_set_sha256="a" * 64,
        source_job_id="synthetic-job", source_job_payload_sha256="b" * 64,
        source_checkpoint_id="synthetic-checkpoint", source_checkpoint_sha256="c" * 64,
        catalog=catalog,
        workflow_stage_map={selection.workflow_stage_id: "synthetic-rules:1:stage:screening:one"},
        gate_result_id="synthetic-gate",
        created_at=datetime.now(timezone.utc),
    )
    restored = ControlCatalogPublication.model_validate_json(publication.model_dump_json())
    identity = project_control_atom_identities(restored)[0]
    status, policies, _ = _source_policies_for_control(restored, identity.identity_sha256)
    assert status == ("present" if policy_known else "ambiguous")
    assert policies[0]["source_policy"] == catalog.controls[0].minimum_evidence[0].source_policy.model_dump(mode="json")
    assert policies[0]["source_policy"]["allows_screening_record_transcription"] is (False if policy_known else None)


class _Transport:
    def __init__(self, review, selection):
        self.review = review
        self.selection = selection
        self.calls = []

    def start_source_target_review(self, *, prompt):
        self.calls.append("review")
        return ProtocolControlAgentResponse(session_id="source-review", text=SourceTargetReview(
            version=SOURCE_TARGET_REVIEW_VERSION, items=[self.review],
        ).model_dump_json())

    def read_stage_bound_requirement(self, *, prompt):
        self.calls.append("author")
        return ProtocolControlAgentResponse(session_id="author", text=self.selection.model_dump_json())

    def start_source_candidate_alignment(self, *, prompt):
        from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
        self.calls.append("alignment")
        return ProtocolControlAgentResponse(session_id="independent-alignment", text=json.dumps({
            "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
            "items": [{"statement_index": self.review.statement_index, "candidate_index": 0,
                       "decision": "fully_expressed", "source_excerpt": self.selection.action_excerpt,
                       "candidate_atom_quotes": [self.selection.action_excerpt],
                       "unresolved_dimensions": [],
                       "evidence_policy_checks": _synthetic_policy_checks_from_prompt(prompt)}],
        }, ensure_ascii=False))

    def start(self, *, prompt):
        raise AssertionError("front flow must not read the whole wire")

    def continue_session(self, **kwargs):
        raise AssertionError("a failed front flow must not reread the whole wire")


def test_front_author_reaches_existing_hydration_and_publication_consumer():
    batch, inventory, review, selection = _example()
    transport = _Transport(review, selection)
    outputs = []

    def consumer(output):
        validate_protocol_control_batch_candidates(batch, output)
        outputs.append(output)

    result = prepare_front_stage_flow(batch, inventory, transport, consumer)
    assert result.error is None
    assert transport.calls == ["review", "author", "alignment"]
    assert len(outputs) == 1 and len(outputs[0].candidates) == 1
    assert result.wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].statement == inventory.statements[0].quoted_text
    assert result.review.items[0] == review


@pytest.mark.parametrize("defect", [None, "raw_hash", "raw_text", "no_receipt", "partial_wire"])
def test_source_only_front_review_recovery_requires_actual_witness(defect):
    from app.services.protocol_control_execution import _resumable_saved_source_review
    from app.agents.protocol_control_fixed_flow import pending_front_wire
    import hashlib

    batch, inventory, review, selection = _example()

    class Broken(_Transport):
        def read_stage_bound_requirement(self, *, prompt):
            self.calls.append("author")
            return ProtocolControlAgentResponse(session_id="bad-author", text="[]")

    failed = ProtocolControlAgentRunner().run(
        batch, Broken(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert failed.final_output is None and failed.partial_wire is None
    saved = failed.model_dump(mode="json")
    # The public result intentionally excludes raw text. The actual failure
    # checkpoint saves it explicitly for source-bound recovery.
    saved["attempts"] = [{**attempt.model_dump(mode="json"),
                          "raw_output_text": attempt.raw_output_text}
                         for attempt in failed.attempts]
    if defect == "raw_hash":
        saved["attempts"][0]["raw_output_sha256"] = "0" * 64
    elif defect == "raw_text":
        changed = review.model_copy(update={"source_action_excerpt": "与已存原答不同的内容"})
        raw = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[changed]).model_dump_json()
        saved["attempts"][0]["raw_output_text"] = raw
        saved["attempts"][0]["raw_output_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    elif defect == "no_receipt":
        saved["attempts"][0]["error_detail"] = None
    elif defect == "partial_wire":
        saved["partial_wire"] = pending_front_wire(batch).model_dump(mode="json")
    if defect in {"raw_hash", "raw_text"}:
        with pytest.raises(ValueError):
            _resumable_saved_source_review(batch, inventory, saved)
        return
    seed = _resumable_saved_source_review(batch, inventory, saved)
    if defect is not None:
        assert seed.review is None
        return
    assert seed.state == "reused" and seed.reason == "verified_pending_front_review"
    transport = _Transport(review, selection)
    restored = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        resume_source_target_review=seed.review, resume_source_statement_coverage=seed.coverage,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert transport.calls == ["author", "alignment"]
    assert restored.final_output is not None
    _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("functions", [["action", "time_validity"], ["time_validity", "action"]])
@pytest.mark.parametrize("source_types", [[], ["知情同意记录"]])
def test_same_visit_action_and_time_reach_saved_consumer_without_inventing_source_limits(
    functions, source_types,
):
    batch, inventory, review, selection = _example()
    inventory.statements[0].decision_functions = functions
    selection.required_source_types = source_types
    transport = _Transport(review, selection)
    assert supports_front_stage_flow(batch, inventory)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None and result.workflow_path_executed == "front_stage_flow"
    assert transport.calls == ["review", "author", "alignment"]
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    evidence = restored.final_output.candidates[0].semantics.minimum_evidence
    assert len(evidence) == 1 and evidence[0].required_source_types == source_types
    assert evidence[0].source_policy.requires_contemporaneous_objective_source is None
    assert evidence[0].source_policy.allows_screening_record_transcription is None
    assert evidence[0].atom_refs and evidence[0].workflow_stage_ids


@pytest.mark.parametrize("functions", [
    ["time_validity"], ["action", "definition"], ["action", "calculation_input"],
])
def test_visit_time_capability_does_not_expand_to_other_source_functions(functions):
    batch, inventory, _, _ = _example()
    inventory.statements[0].decision_functions = functions
    assert not supports_front_stage_flow(batch, inventory)


@pytest.mark.parametrize("defect", [None, "unknown", "wrong_span", "invented_excerpt"])
def test_short_author_preserves_source_policy_through_saved_consumer(defect):
    from app.domain.contracts.control_evidence_policy import ControlEvidenceSourcePolicy
    batch, inventory, review, selection = _example()
    original = inventory.statements[0].quoted_text
    quote = original + "；资料来源仅采用同期原始记录，不另设结果有效期。"
    batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace(original, quote)
    inventory.statements[0].quoted_text = quote
    review.source_action_excerpt = quote
    selection.action_excerpt = selection.obligation_statement = quote
    selection.source_policy = ControlEvidenceSourcePolicy(
        requires_contemporaneous_objective_source=True,
        allows_screening_record_transcription=False,
        result_validity_status="not_specified", result_validity_constraint=None,
        source_span_ids=[batch.owned_units[0].source_span_ids[0]],
        source_excerpts=[quote],
    )
    if defect == "unknown":
        selection.source_policy.allows_screening_record_transcription = None
    elif defect == "wrong_span":
        selection.source_policy.source_span_ids = ["span:unrelated"]
    elif defect == "invented_excerpt":
        selection.source_policy.source_excerpts = ["允许转述筛选记录。"]
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    if defect in {"wrong_span", "invented_excerpt"}:
        assert result.final_output is None
        return
    assert result.final_output is not None
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    policy = restored.final_output.candidates[0].semantics.minimum_evidence[0].source_policy
    assert policy == selection.source_policy
    from app.services.binding_qualification_support import _policy_unknown
    assert _policy_unknown(policy.model_dump(mode="json")) is (defect == "unknown")


@pytest.mark.parametrize("change", ["duration", "wrong_visit", "exception", "unresolved"])
def test_action_time_functions_still_require_complete_source_and_frozen_visit(change):
    batch, inventory, _, _ = _example()
    inventory.statements[0].decision_functions = ["action", "time_validity"]
    if change == "duration":
        inventory.statements[0].time_words.append("连续7天")
        original_quote = inventory.statements[0].quoted_text
        inventory.statements[0].quoted_text += "，连续7天"
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace(
            original_quote, inventory.statements[0].quoted_text,
        )
    elif change == "wrong_visit":
        inventory.statements[0].scope_quote = "基线期"
        inventory.statements[0].time_words = ["基线期"]
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace("筛选期（D-7~D-1）", "基线期")
    elif change == "exception":
        inventory.statements[0].exception_words = "经研究者判断除外"
    else:
        inventory.statements[0].unresolved = ["访视未确定"]
    assert not supports_front_stage_flow(batch, inventory)


@pytest.mark.parametrize("kind,mode", [
    ("must_record", "semantic"), ("must_professional_assessment", "investigator_judgment"),
    ("complete_or_verify", "investigator_judgment"),
])
def test_inconsistent_action_only_response_is_rejected_without_more_reads(kind, mode):
    batch, inventory, review, selection = _example()
    selection.kind = kind
    selection.determination_mode = mode
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and transport.calls == ["review", "author"]
    assert result.attempts[-1].error_classes == ["FLOW_ASSEMBLY_INVALID"]
    assert result.source_front_target_review is not None


def test_short_author_contract_allows_empty_source_limits_but_requires_explicit_field():
    from pydantic import ValidationError
    from app.agents.protocol_control_stage_compiler import (
        StageBoundRequirement, build_stage_bound_requirement_prompt,
        stage_bound_requirement_response_format,
    )
    batch, inventory, review, selection = _example()
    payload = selection.model_dump(mode="json")
    payload["required_source_types"] = []
    assert StageBoundRequirement.model_validate(payload).required_source_types == []
    del payload["required_source_types"]
    with pytest.raises(ValidationError):
        StageBoundRequirement.model_validate(payload)
    schema = stage_bound_requirement_response_format()["json_schema"]["schema"]
    assert "required_source_types" in schema["required"]
    assert "minItems" not in schema["properties"]["required_source_types"]
    prompt = build_stage_bound_requirement_prompt(batch, inventory, review)
    assert "未限定时必须填写空列表 []" in prompt
    assert "kind=complete_or_verify" in prompt


@pytest.mark.parametrize("shape", ["inline", "split"])
def test_unsupported_visit_anchor_shape_is_rejected_before_front_calls(shape):
    batch, inventory, review, selection = _example()
    statement = inventory.statements[0]
    statement.decision_functions = ["action", "time_validity"]
    if shape == "inline":
        statement.quoted_text = "拟参加者须在筛选期内完成知情同意记录"
        statement.scope_quote = None
        statement.time_words = ["筛选期内"]
        batch.owned_units[0].excerpt = statement.quoted_text
    else:
        statement.time_words = ["筛选期", "D-7~D-1"]
    transport = _Transport(review, selection)
    assert not supports_front_stage_flow(batch, inventory)
    assert not transport.calls


@pytest.mark.parametrize("scope, frozen, expected", [
    ("D-1", "筛选期 / D-7~D-1", False),
    ("筛选期（D-1）", "筛选期 / D-7~D-1", False),
    ("D-7", "筛选期 / D-7~D-1", False),
    ("D1", "基线期 / D10", False),
    ("W2", "随访期 / W1~W2", False),
    ("筛选期（D-7~D-1）", "筛选期 / D-7~D-1", True),
    ("D-1", "基线期 / D-1", True),
    ("筛选期内", "筛选期 / D-7~D-1", True),
])
def test_visit_scope_does_not_expand_a_day_into_a_window(scope, frozen, expected):
    from app.agents.protocol_control_source_interpretation import source_visit_scope_matches
    assert source_visit_scope_matches(scope, frozen) is expected


def test_specific_day_within_a_wider_visit_never_enters_front_author():
    batch, inventory, review, selection = _example()
    statement = inventory.statements[0]
    statement.scope_quote = "D-1"
    statement.time_words = ["D-1"]
    batch.owned_units[0].excerpt = "D-1：" + statement.quoted_text
    transport = _Transport(review, selection)
    assert not supports_front_stage_flow(batch, inventory)
    assert not transport.calls


@pytest.mark.parametrize("uncertain, code", [
    (False, "FLOW_TRANSPORT_FAILED"), (True, "FLOW_COMPLETION_UNCERTAIN"),
])
def test_front_transport_failure_retains_completion_uncertainty_without_inline_retry(uncertain, code):
    from app.agents.protocol_control_agent_transport import ProtocolControlAgentCallError
    batch, inventory, review, selection = _example()

    class Failed(_Transport):
        def read_stage_bound_requirement(self, *, prompt):
            self.calls.append("author")
            raise ProtocolControlAgentCallError("failed-author", "isolated transport failure", uncertain_completion=uncertain)

    transport = Failed(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None
    assert transport.calls == ["review", "author"]
    assert result.attempts[-1].outcome == "transport_failed"
    assert result.attempts[-1].error_classes == [code]
    assert result.source_front_target_review.items == [review]


@pytest.mark.parametrize("phase", ["author", "alignment", "baseline_wire"])
@pytest.mark.parametrize("failure_kind", ["identity", "budget", "interrupted"])
def test_adapter_wrapped_terminal_failure_retains_cause_and_never_replays(phase, failure_kind):
    from app.agents.protocol_control_agent_transport import ProtocolControlAgentCallError, ProtocolControlModelIdentityError
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted
    batch, inventory, review, selection = _example()
    cause = {
        "identity": ProtocolControlModelIdentityError("synthetic wrong model", configured_model="expected", reason="mismatch"),
        "budget": LogicalCallBudgetExhausted("synthetic exhausted budget"),
        "interrupted": ProtocolControlAgentCallError("unfinished-call", "synthetic unfinished", uncertain_completion=True),
    }[failure_kind]
    transport = _Transport(review, selection)

    def failed(**kwargs):
        transport.calls.append(phase)
        raise ProtocolControlAgentCallError("wrapped-call", "synthetic adapter error") from cause

    setattr(transport, {"author": "read_stage_bound_requirement", "alignment": "start_source_candidate_alignment",
                        "baseline_wire": "start"}[phase], failed)
    variant = BASELINE if phase == "baseline_wire" else FIXED_FLOW
    result = ProtocolControlAgentRunner(max_transport_retries=3).run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=variant,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    expected = {"identity": "MODEL_IDENTITY_INVALID", "budget": "LOGICAL_BUDGET_EXHAUSTED",
                "interrupted": "FLOW_COMPLETION_UNCERTAIN"}[failure_kind]
    assert result.final_output is None
    assert result.attempts[-1].error_classes == [expected]
    assert transport.calls.count(phase) == 1
    if phase == "alignment":
        assert result.partial_wire is not None
        assert result.source_statement_coverage
    else:
        assert result.partial_wire is None


@pytest.mark.parametrize("decision", ["incomplete", "uncertain"])
def test_result_condition_disagreement_preserves_answer_without_adoption_or_reread(decision):
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
    batch, inventory, review, selection = _example()
    source = "完成规定检查且结果符合方案要求"
    batch.owned_units[0].excerpt = "筛选期（D-7~D-1）：" + source
    inventory.statements[0].quoted_text = source
    review.source_action_excerpt = source
    selection.action_excerpt = selection.obligation_statement = source

    class Disagreement(_Transport):
        def start_source_candidate_alignment(self, *, prompt):
            self.calls.append("alignment")
            assert "证据政策" in prompt and "action_completion" in prompt
            assert "仅证明操作已经完成，不证明检查结果正常或达到入排阈值" in prompt
            assert "不得新增结果正常要求" in prompt
            return ProtocolControlAgentResponse(session_id="independent-condition-review", text=json.dumps({
                "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
                "items": [{"statement_index": 0, "candidate_index": 0, "decision": decision,
                           "source_excerpt": source, "candidate_atom_quotes": [source],
                           "unresolved_dimensions": ["结果条件不能仅以操作完成替代"]}],
            }, ensure_ascii=False))

    transport = Disagreement(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and transport.calls == ["review", "author", "alignment"]
    assert result.attempts[-1].error_classes == ["FLOW_CANDIDATE_SEMANTICS_UNVERIFIED"]
    assert result.source_candidate_alignment.items[0].unresolved_dimensions == ["结果条件不能仅以操作完成替代"]
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored.final_output is None and restored.source_candidate_alignment == result.source_candidate_alignment
    # The host-assembled proposal remains recoverable, never adopted merely
    # because assembly succeeded before an independent semantic disagreement.
    assert restored.partial_wire is not None
    assert restored.partial_wire == result.partial_wire
    assert restored.source_statement_coverage
    assert restored.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].statement == source
    with pytest.raises(ValueError, match="最终候选与装配结果"):
        _validate_saved_source_review(batch, restored)
    assert any(json.loads(attempt.raw_output_text).get("result_requirement") == "action_only"
               for attempt in result.attempts if attempt.raw_output_text)


@pytest.mark.parametrize("change", ["missing", "missing_proof", "changed_candidate", "detached_front"])
def test_saved_front_result_requires_actual_unchanged_semantic_review(change):
    batch, inventory, review, selection = _example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    _validate_saved_source_review(batch, result)
    if change == "missing":
        result.source_candidate_alignment = None
    elif change == "missing_proof":
        result.source_candidate_alignment.proofs = []
    elif change == "detached_front":
        result.source_front_target_review = None
        result.workflow_path_executed = "baseline"
    else:
        result.partial_wire.candidate_drafts[0].minimum_evidence[0].required_source_types = []
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, result)


def test_shared_prohibition_empty_source_limits_reach_existing_gate():
    from app.agents.protocol_control_stage_compiler import (
        SHARED_PROHIBITION_REQUIREMENT_VERSION, SharedProhibitionRequirement,
        compile_shared_prohibition_requirement,
    )
    from app.agents.protocol_control_deconstructor import (
        hydrate_protocol_control_agent_output, _merge_source_candidate_insert,
    )
    from app.agents.protocol_control_fixed_flow import pending_front_wire
    batch, inventory, review, _ = _example()
    source = "筛选期、治疗期不得调整既定治疗。"
    batch.owned_units[0].excerpt = source
    inventory.statements[0].quoted_text = source
    inventory.statements[0].scope_quote = "筛选期、治疗期"
    inventory.statements[0].force = "prohibited"
    inventory.statements[0].time_words = ["筛选期", "治疗期"]
    review.source_action_excerpt = "不得调整既定治疗"
    selection = SharedProhibitionRequirement.model_validate({
        "version": SHARED_PROHIBITION_REQUIREMENT_VERSION, "statement_index": 0,
        "current_statement": "筛选期不得调整既定治疗", "future_statement": "治疗期不得调整既定治疗",
        "workflow_stage_id": "stage:screening:one", "prospective_period": "treatment_period",
        "kind": "prohibit_medication_or_treatment_exposure", "title": "既定治疗调整限制",
        "applicable_population": "拟参加者", "observation_scope": "筛选期既定治疗调整记录",
        "fact_type": "treatment_change", "evidence_description": "筛选期既定治疗记录",
        "required_source_types": [], "unresolved_aspects": [],
    })
    candidate = compile_shared_prohibition_requirement(batch, inventory, review, selection)
    merged = _merge_source_candidate_insert(json.dumps({"candidate_drafts": [candidate.model_dump(mode="json")]}),
        pending_front_wire(batch), authorized_unit_ids={inventory.statements[0].structure_unit_id})
    output = hydrate_protocol_control_agent_output(merged, batch)
    validate_protocol_control_batch_candidates(batch, output)
    assert output.candidates[0].semantics.minimum_evidence[0].required_source_types == []


@pytest.mark.parametrize("change", ["exception", "unresolved", "definition", "empty", "duration"])
def test_preflight_preserves_unsupported_sources_instead_of_dropping_them(change):
    batch, inventory, _, _ = _example()
    if change == "exception":
        inventory.statements[0].exception_words = "经研究者判断除外"
    elif change == "unresolved":
        inventory.statements[0].unresolved = ["适用对象尚未明确"]
    elif change == "definition":
        inventory.statements[0].decision_functions = ["definition"]
    elif change == "empty":
        inventory.statements = []
        inventory.units_without_statement = batch.owned_structure_unit_ids
    else:
        inventory.statements[0].time_words = ["筛选期（D-7~D-1）", "连续7天"]
        inventory.statements[0].quoted_text += "，连续7天"
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.rstrip("。") + "，连续7天。"
    assert not supports_front_stage_flow(batch, inventory)


def test_bad_target_review_never_calls_author_or_falls_back():
    batch, inventory, review, selection = _example()
    review.source_action_excerpt = "无来源的另一操作"
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None
    assert transport.calls == ["review"]
    assert result.attempts[-1].error_classes == ["SOURCE_ACTION_MISMATCH"]
    assert result.attempts[0].raw_output_text is not None


def test_known_meaning_missing_stage_does_not_trigger_parent_reread():
    batch, inventory, review, selection = _example()
    selection.workflow_stage_id = "invented-stage"
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and result.status == "需要核对"
    assert transport.calls == ["review", "author"]
    assert result.attempts[-1].error_classes == ["FLOW_ASSEMBLY_INVALID"]
    assert result.source_front_target_review.items == [review]
    assert json.loads(result.attempts[1].raw_output_text)["workflow_stage_id"] == "invented-stage"


def test_baseline_identity_unchanged_candidate_identity_explicit():
    assert workflow_template("source prompt", BASELINE) == "source prompt"
    assert workflow_template("source prompt", FIXED_FLOW) != "source prompt"
    with pytest.raises(ValueError):
        workflow_template("source prompt", "unknown")


def test_front_author_reaches_the_same_runner_consumer_without_whole_wire_author():
    batch, inventory, review, selection = _example()
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.status == "已解析" and result.final_output is not None
    assert transport.calls == ["review", "author", "alignment"]
    assert result.source_candidate_alignment.proofs
    assert result.source_statement_coverage[0].status == "expressed"
    assert result.source_front_target_review.items == [review]
    assert result.source_target_review is None
    _validate_saved_source_review(batch, result)
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    restored.source_front_target_review.items[0].source_action_excerpt = "另一无来源操作"
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)
    assert result.final_output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].evaluation.observation_policy.mode == "action_completion"
    assert any("宿主装配，非模型原答" in issue for attempt in result.attempts for issue in attempt.issues)


@pytest.mark.parametrize("target_kind", ["official", "procedure"])
def test_existing_exact_target_routes_to_baseline_before_front_calls(target_kind):
    batch, inventory, _, _ = _example()
    unit = batch.owned_units[0]
    common = dict(catalog_item_id="existing-action", label="已有核查", position=0,
                  source_span_ids=unit.source_span_ids,
                  source_excerpts=[unit.excerpt])
    if target_kind == "official":
        batch.known_official_targets = [KnownOfficialRuleTarget(**common, official_code="IN-01")]
    else:
        batch.known_procedure_targets = [KnownRequiredProcedureTarget(
            **common, visit_instance="筛选", review_stage="screening")]
    assert not supports_front_stage_flow(batch, inventory)
    class BaselineReached(Exception):
        pass
    class ExistingPath(_Transport):
        def start(self, *, prompt):
            self.calls.append("baseline")
            raise BaselineReached("正常转入既有比较路径，未丢来源")
    transport = ExistingPath(None, None)
    result = ProtocolControlAgentRunner(max_transport_retries=0).run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert transport.calls == ["baseline"] and result.final_output is None


def test_target_review_scope_exclusion_is_checked_before_paid_calls(monkeypatch):
    batch, inventory, _, _ = _example()
    monkeypatch.setattr("app.agents.protocol_control_fixed_flow.target_review_indexes",
                        lambda *args: [])
    assert not supports_front_stage_flow(batch, inventory)


def test_shared_budget_exhaustion_is_technical_and_does_not_reread_parent():
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted
    batch, inventory, review, selection = _example()
    class Exhausted(_Transport):
        def read_stage_bound_requirement(self, *, prompt):
            self.calls.append("author-budget-blocked")
            raise LogicalCallBudgetExhausted("累计预算耗尽")
    transport = Exhausted(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert transport.calls == ["review", "author-budget-blocked"]
    assert result.attempts[-1].outcome == "transport_failed"
    assert result.attempts[-1].error_classes == ["LOGICAL_BUDGET_EXHAUSTED"]
    assert result.source_front_target_review is not None and result.final_output is None


def test_frozen_slice_uses_budget_and_saved_result_consumer_then_clears_binding():
    from scripts.run_frozen_control_slice import execute_frozen_slice
    from app.llm.logical_call_budget import LogicalCallBudget

    batch, inventory, review, selection = _example()

    class Measured(_Transport):
        def bind_logical_call_budget(self, budget):
            self.budget = budget

        def take_call_receipts(self):
            return []

        def start_source_interpretation(self, *, prompt):
            self.budget.reserve(request_sha256="a" * 64, max_tokens=100)
            return ProtocolControlAgentResponse(session_id="reader", text=inventory.model_dump_json())

        def start_source_target_review(self, *, prompt):
            self.budget.reserve(request_sha256="b" * 64, max_tokens=100)
            return super().start_source_target_review(prompt=prompt)

        def read_stage_bound_requirement(self, *, prompt):
            self.budget.reserve(request_sha256="c" * 64, max_tokens=100)
            return super().read_stage_bound_requirement(prompt=prompt)

        def start_source_candidate_alignment(self, *, prompt):
            self.budget.reserve(request_sha256="d" * 64, max_tokens=100)
            return super().start_source_candidate_alignment(prompt=prompt)

    transport = Measured(review, selection)
    budget = LogicalCallBudget("isolated-source", max_requests=4, max_output_tokens=400)
    record = execute_frozen_slice(batch, transport, budget, workflow_variant=FIXED_FLOW,
                                   max_schema_repairs=0)
    assert record["consumer_validated"] and record["workflow_executed"] == FIXED_FLOW
    assert record["logical_call_budget"]["requests_used"] == 4
    assert not record["claims_complete"] and record["failure"] is None
    assert transport.budget is None
    assert record["receipt_format_version"] == "frozen-control-slice/v2"
    actual = record["attempt_raw_outputs"][0]
    assert actual["session_id"] == "reader"
    assert actual["sha256"] == record["result"]["attempts"][0]["raw_output_sha256"]
    assert json.loads(actual["text"])["statements"]

    # The same source envelope cannot acquire a new budget in a nested path.
    exhausted = execute_frozen_slice(batch, transport, budget, workflow_variant=FIXED_FLOW,
                                      max_schema_repairs=0)
    assert not exhausted["consumer_validated"]
    assert exhausted["logical_call_budget"]["requests_used"] == 4
    assert transport.budget is None


def test_frozen_slice_gate_failure_and_empty_result_are_not_success(monkeypatch):
    import scripts.run_frozen_control_slice as module
    from app.llm.logical_call_budget import LogicalCallBudget
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunResult

    batch, inventory, review, selection = _example()
    good = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )

    class Measured(_Transport):
        def bind_logical_call_budget(self, budget):
            self.budget = budget

        def take_call_receipts(self):
            return [{"status": "diagnostic_fixture", "usage": None}]

    transport = Measured(review, selection)
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *a, **kw: good)
    monkeypatch.setattr(module, "_validate_saved_source_review", lambda *a: (_ for _ in ()).throw(
        ValueError("保存的来源被更换")))
    record = module.execute_frozen_slice(batch, transport,
        LogicalCallBudget("source-check", max_requests=3, max_output_tokens=300),
        workflow_variant=FIXED_FLOW, max_schema_repairs=0)
    assert not record["consumer_validated"] and record["failure"]["type"] == "ValueError"
    assert record["result"]["final_output"] is not None
    assert record["call_receipts"][0]["usage"] is None and transport.budget is None

    pending = ProtocolControlAgentRunResult(status="需要核对", batch_id=batch.batch_id,
        session_id="no-final-result", attempts=[good.attempts[0].model_copy(update={"issues": []})])
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *a, **kw: pending)
    record = module.execute_frozen_slice(batch, transport,
        LogicalCallBudget("empty-check", max_requests=3, max_output_tokens=300),
        workflow_variant=FIXED_FLOW, max_schema_repairs=0)
    assert not record["consumer_validated"] and record["workflow_executed"] is None
    assert not record["candidate_path_used"] and transport.budget is None


def test_front_request_blocked_before_response_keeps_actual_path():
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted

    batch, inventory, review, selection = _example()

    class Blocked(_Transport):
        def start_source_target_review(self, *, prompt):
            raise LogicalCallBudgetExhausted("来源核对额度已用完")

    result = ProtocolControlAgentRunner().run(
        batch, Blocked(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.workflow_path_executed == "front_stage_flow"
    assert result.final_output is None and result.source_front_target_review is None
    assert result.workflow_variant_requested == FIXED_FLOW


def test_slice_freezes_real_consumer_modules_before_provider_preflight():
    from scripts.run_frozen_control_slice import frozen_code_identity

    identity = frozen_code_identity()
    assert identity["app/agents/protocol_control_stage_compiler.py"]
    assert identity["app/protocols/protocol_control_gate.py"]
    assert identity["app/domain/contracts/control_evidence_policy.py"]
    assert all(len(value) == 64 for value in identity.values())


def test_front_resume_without_recovery_proof_is_refused_before_calls():
    batch, inventory, review, selection = _example()
    good = prepare_front_stage_flow(batch, inventory, _Transport(review, selection),
        lambda output: validate_protocol_control_batch_candidates(batch, output))
    transport = _Transport(review, selection)
    with pytest.raises(ValueError, match="FLOW_RESUME_PROOF_REQUIRED"):
        ProtocolControlAgentRunner().run(
            batch, transport, resume_source_interpretation=inventory,
            resume_wire=good.wire, resume_session_id="saved", workflow_variant=FIXED_FLOW,
            output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
        )
    assert not transport.calls


def _covered_procedure_example():
    batch, inventory, review, selection = _example()
    unit = batch.owned_units[0]
    old_quote = inventory.statements[0].quoted_text
    quote = "受试者须完成知情同意签署"
    unit.excerpt = unit.excerpt.replace(old_quote, quote)
    inventory.statements[0].quoted_text = quote
    review.source_action_excerpt = quote
    selection.action_excerpt = selection.obligation_statement = quote
    batch.known_procedure_targets = [KnownRequiredProcedureTarget(
        catalog_item_id="existing-consent", label="知情同意记录", position=0,
        source_span_ids=unit.source_span_ids, source_excerpts=["由受试者完成知情同意签署"],
        visit_instance="筛选期 / V1 / D-7~D-1", review_stage="screening",
        covered_action_kinds=["obtain_signature"],
    )]
    batch.owned_required_action_kinds_by_structure_unit_id = {unit.structure_unit_id: ["obtain_signature"]}
    review.decision = "covered_by_procedure"
    review.target_id = "existing-consent"
    review.target_action_excerpt = "由受试者完成知情同意签署"
    review.source_time_excerpt = "D-7~D-1"
    review.target_time_excerpt = "D-7~D-1"
    review.unresolved_aspects = []
    return batch, inventory, review, selection


def test_front_covered_requirement_reaches_saved_consumer_without_duplicate_author():
    batch, inventory, review, selection = _covered_procedure_example()
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None and result.status == "已解析"
    assert transport.calls == ["review"]
    assert result.final_output.candidates == []
    assert result.source_statement_coverage[0].status == "linked_only"
    assert result.source_target_review.items == [review]
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    restored.partial_wire.dispositions[0].linked_procedure_catalog_item_ids = ["not-frozen"]
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)
    restored = type(result).model_validate_json(result.model_dump_json())
    batch.known_procedure_targets.append(batch.known_procedure_targets[0].model_copy(update={
        "catalog_item_id": "another-frozen-target",
    }))
    restored.partial_wire.dispositions[0].linked_procedure_catalog_item_ids.append("another-frozen-target")
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


def test_front_covered_requirement_does_not_hide_missing_time_scope():
    batch, inventory, review, selection = _covered_procedure_example()
    review.target_time_excerpt = "D100"
    transport = _Transport(review, selection)
    result = prepare_front_stage_flow(batch, inventory, transport,
        lambda output: validate_protocol_control_batch_candidates(batch, output))
    assert result.wire is None and result.error is not None
    assert result.error_code == result.error.code
    assert transport.calls == ["review"]


def _independent_mixed_example():
    batch, inventory, covered, selection = _covered_procedure_example()
    unit = batch.owned_units[0].model_copy(deep=True)
    unit.structure_unit_id = "independent-action"
    unit.source_span_ids = ["span:independent-action"]
    unit.source_ref = "generic.body.p30"
    unit.member_source_refs = [unit.source_ref]
    unit.source_order += 1
    quote = "拟参加者须完成既往用药核查"
    unit.excerpt = "筛选期（D-7~D-1）：" + quote + "。"
    batch.owned_units.append(unit)
    batch.owned_structure_unit_ids.append(unit.structure_unit_id)
    batch.owned_source_span_ids.extend(unit.source_span_ids)
    statement = inventory.statements[0].model_copy(deep=True)
    statement.structure_unit_id = unit.structure_unit_id
    statement.quoted_text = quote
    inventory.statements.append(statement)
    _, _, additional, _ = _example()
    additional.statement_index = 1
    additional.source_action_excerpt = quote
    selection.statement_index = 1
    selection.action_excerpt = selection.obligation_statement = quote
    selection.title = selection.evidence_description = "既往用药核查"
    selection.observation_scope = "筛选期拟参加者的既往用药核查记录"
    selection.fact_type = "medication_history"
    selection.required_source_types = ["病历记录"]
    review = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[covered, additional])
    return batch, inventory, review, selection


class _MixedTransport(_Transport):
    def __init__(self, review, selection):
        super().__init__(review, selection)
        self.selections = selection if isinstance(selection, list) else [selection]
        self.author_index = 0

    def start_source_target_review(self, *, prompt):
        self.calls.append("review")
        return ProtocolControlAgentResponse(session_id="source-review", text=self.review.model_dump_json())

    def start_source_candidate_alignment(self, *, prompt):
        from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
        self.calls.append("alignment")
        return ProtocolControlAgentResponse(session_id="independent-alignment", text=json.dumps({
            "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
            "items": [{"statement_index": selection.statement_index, "candidate_index": index,
                       "decision": "fully_expressed", "source_excerpt": selection.action_excerpt,
                       "candidate_atom_quotes": [selection.action_excerpt],
                       "unresolved_dimensions": [],
                       "evidence_policy_checks": _synthetic_policy_checks_from_prompt(prompt, index)}
                      for index, selection in enumerate(self.selections)],
        }, ensure_ascii=False))

    def read_stage_bound_requirement(self, *, prompt):
        self.calls.append("author")
        selection = self.selections[self.author_index]
        self.author_index += 1
        return ProtocolControlAgentResponse(session_id=f"author-{selection.statement_index}",
                                            text=selection.model_dump_json())


@pytest.mark.parametrize("failure_index", [None, 0, 1])
@pytest.mark.parametrize("failure", ["scope", "version", "nonobject"])
def test_each_short_answer_is_checked_before_the_next_author(failure_index, failure):
    batch, inventory, review, second = _independent_mixed_example()
    first = second.model_copy(deep=True)
    first.statement_index = 0
    first.action_excerpt = first.obligation_statement = inventory.statements[0].quoted_text
    first.title = first.evidence_description = "知情同意签署"
    first.fact_type = "informed_consent"
    first.required_source_types = ["知情同意记录"]
    first.observation_scope = "筛选期知情同意签署记录"
    review.items[0] = review.items[0].model_copy(update={
        "decision": "additional_requirement", "target_id": None,
        "target_action_excerpt": None, "source_time_excerpt": None,
        "target_time_excerpt": None, "unresolved_aspects": ["保留独立的签署要求"],
    })

    class Checked(_MixedTransport):
        def read_stage_bound_requirement(self, *, prompt):
            index = self.author_index
            response = super().read_stage_bound_requirement(prompt=prompt)
            if index != failure_index:
                return response
            payload = json.loads(response.text)
            if failure == "scope":
                payload["statement_index"] = 100
            elif failure == "version":
                payload["version"] = "unsupported/v1"
            else:
                payload = []
            return response.model_copy(update={"text": json.dumps(payload, ensure_ascii=False)})

    transport = Checked(review, [first, second])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    if failure_index is None:
        assert result.final_output is not None
        assert transport.calls == ["review", "author", "author", "alignment"]
        assert len(result.final_output.candidates) == 2
        _validate_saved_source_review(batch, type(result).model_validate_json(result.model_dump_json()))
    else:
        assert result.final_output is None
        if failure_index == 0:
            assert result.partial_wire is None
        else:
            assert len(result.partial_wire.candidate_drafts) == 1
            assert result.partial_wire.candidate_drafts[0].source_structure_unit_ids == [inventory.statements[0].structure_unit_id]
        assert transport.calls == ["review", *(["author"] * (failure_index + 1))]
        assert result.attempts[-1].error_classes == ["FLOW_ASSEMBLY_INVALID"]
        retained = [attempt for attempt in result.attempts if attempt.raw_output_text is not None]
        assert len(retained) == failure_index + 2  # review and every actual author answer
        if failure_index == 1:
            assert json.loads(retained[1].raw_output_text) == first.model_dump(mode="json")
        with pytest.raises(ValueError):
            _validate_saved_source_review(batch, result)


@pytest.mark.parametrize("review_order", ["source", "reversed"])
@pytest.mark.parametrize("unsupported", ["definition", "duration", "unknown_scope"])
def test_mixed_capability_preserves_simple_point_without_completing_batch(unsupported, review_order):
    from app.agents.protocol_control_fixed_flow import front_stage_supported_indexes
    batch, inventory, review, selection = _independent_mixed_example()
    # Retain the first statement's actual source rather than using a whole-unit
    # target link as proof that an unsupported dependency has been consumed.
    first = inventory.statements[0]
    review.items[0] = review.items[0].model_copy(update={
        "decision": "additional_requirement", "target_id": None,
        "target_action_excerpt": None, "source_time_excerpt": None,
        "target_time_excerpt": None, "unresolved_aspects": ["保留独立要求"],
    })
    if unsupported == "definition":
        first.decision_functions = ["action", "definition"]
    elif unsupported == "unknown_scope":
        first.unresolved = ["适用节点仍不明确"]
    else:
        quote = first.quoted_text
        first.quoted_text += "，连续7天"
        first.time_words.append("连续7天")
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace(quote, first.quoted_text)
        review.items[0].source_action_excerpt = first.quoted_text
    if review_order == "reversed":
        review.items.reverse()
    frozen = inventory.model_dump(mode="json")
    assert front_stage_supported_indexes(batch, inventory) == {1}
    assert supports_front_stage_flow(batch, inventory)
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert transport.calls == ["review", "author", "alignment"]
    assert inventory.model_dump(mode="json") == frozen
    assert result.final_output is None and result.status == "需要核对"
    assert len(result.partial_wire.candidate_drafts) == 1
    assert result.partial_wire.candidate_drafts[0].source_structure_unit_ids == ["independent-action"]
    assert result.source_front_target_review == review
    detail = result.attempts[-1].error_detail
    assert result.attempts[-1].error_classes == [
        "FLOW_SOURCE_SCOPE_UNRESOLVED" if unsupported == "unknown_scope" else "FLOW_COMPILER_CAPABILITY_GAP"
    ]
    assert detail["completed_author_indexes"] == [1]
    retained = detail["retained_statements"]
    assert len(retained) == 1 and retained[0]["statement_index"] == 0
    assert retained[0]["reason"] == (
        "source_review_unresolved" if unsupported == "unknown_scope" else "compiler_capability_gap"
    )
    assert retained[0]["source_refs"] == [batch.owned_units[0].source_ref]
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored.partial_wire == result.partial_wire
    assert restored.attempts[-1].error_detail == detail
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("order", ["source", "reversed"])
def test_independent_covered_and_new_units_reach_saved_consumer(order):
    batch, inventory, review, selection = _independent_mixed_example()
    if order == "reversed":
        review.items.reverse()
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    assert transport.calls == ["review", "author", "alignment"]
    assert len(result.final_output.candidates) == 1
    assert result.final_output.candidates[0].semantics.source_structure_unit_ids == ["independent-action"]
    assert [entry.status for entry in result.source_statement_coverage] == ["linked_only", "expressed"]
    assert [item.statement_index for item in result.source_target_review.items] == [0]
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    # A different frozen target is not interchangeable with the one reviewed.
    batch.known_procedure_targets.append(batch.known_procedure_targets[0].model_copy(update={
        "catalog_item_id": "another-frozen-target",
    }))
    restored.partial_wire.dispositions[0].linked_procedure_catalog_item_ids = ["another-frozen-target"]
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


def _same_unit_mixed_example():
    batch, inventory, review, selection = _independent_mixed_example()
    unit = batch.owned_units[0]
    unit.excerpt += inventory.statements[1].quoted_text + "。"
    batch.owned_units = [unit]
    batch.owned_structure_unit_ids = [unit.structure_unit_id]
    batch.owned_source_span_ids = list(unit.source_span_ids)
    inventory.statements[1].structure_unit_id = unit.structure_unit_id
    return batch, inventory, review, selection


def _background_example(*, same_unit=False, covered=False, background_only=False):
    from app.agents.protocol_control_source_interpretation import SourceTargetReviewItem

    if covered:
        batch, inventory, action_review, selection = _covered_procedure_example()
    else:
        batch, inventory, action_review, selection = _example()
    quote = "样本量估计用于研究总体精度说明"
    unit = batch.owned_units[0]
    background = inventory.statements[0].model_copy(deep=True)
    background.quoted_text = quote
    background.force = "descriptive"
    background.decision_functions = ["background"]
    background.scope_quote = None
    background.time_words = []
    background.exception_words = None
    background.unresolved = []
    if background_only:
        unit.excerpt = quote + "。"
        inventory.statements = [background]
        items = []
        index = 0
    else:
        index = 1
        items = [action_review]
        if same_unit:
            unit.excerpt += quote + "。"
        else:
            unit = unit.model_copy(deep=True)
            unit.structure_unit_id = "independent-background"
            unit.source_span_ids = ["span:independent-background"]
            unit.source_ref = "generic.body.p40"
            unit.member_source_refs = [unit.source_ref]
            unit.source_order += 1
            unit.excerpt = quote + "。"
            batch.owned_units.append(unit)
            batch.owned_structure_unit_ids.append(unit.structure_unit_id)
            batch.owned_source_span_ids.extend(unit.source_span_ids)
            background.structure_unit_id = unit.structure_unit_id
        inventory.statements.append(background)
    items.append(SourceTargetReviewItem(
        statement_index=index, decision="background_context",
        source_action_excerpt=quote, non_control_basis_excerpt=quote,
    ))
    return batch, inventory, SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=items), selection


@pytest.mark.parametrize("same_unit", [False, True])
@pytest.mark.parametrize("covered", [False, True])
def test_background_and_action_reach_saved_consumer_without_background_author(same_unit, covered):
    batch, inventory, review, selection = _background_example(same_unit=same_unit, covered=covered)
    transport = _MixedTransport(review, selection)
    assert supports_front_stage_flow(batch, inventory)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    assert transport.calls == (["review"] if covered else ["review", "author", "alignment"])
    assert len(result.final_output.candidates) == (0 if covered else 1)
    assert result.source_front_target_review.items[1].decision == "background_context"
    assert result.source_statement_coverage[1].candidate_indexes == []
    assert result.source_statement_coverage[1].action_candidate_indexes == []
    if not same_unit:
        assert result.partial_wire.dispositions[1].disposition.value == "administrative_statistical_background"
        assert result.source_statement_coverage[1].status == "not_located"
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    restored.source_front_target_review.items[1].non_control_basis_excerpt = "无源背景"
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


def test_pure_background_requires_saved_source_proof_but_no_patient_obligation():
    batch, inventory, review, selection = _background_example(background_only=True)
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None and result.final_output.candidates == []
    assert transport.calls == ["review"]
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    restored.source_front_target_review = None
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


def test_saved_background_rechecks_unresolved_source_after_restore():
    batch, inventory, review, selection = _background_example(background_only=True)
    result = ProtocolControlAgentRunner().run(
        batch, _MixedTransport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    restored = type(result).model_validate_json(result.model_dump_json())
    restored.source_interpretation.statements[0].unresolved = ["用途仍待核清"]
    with pytest.raises(SourceTargetReviewValidationError) as error:
        _validate_saved_source_review(batch, restored)
    assert error.value.code == "BACKGROUND_CONTEXT_UNPROVEN"


def test_pure_background_cannot_hide_frozen_independent_action():
    batch, inventory, review, selection = _background_example(background_only=True)
    unit = batch.owned_units[0]
    unit.excerpt += "筛选期应完成知情同意核查。"
    batch.owned_required_action_kinds_by_structure_unit_id = {
        unit.structure_unit_id: ["verify_informed_consent"],
    }
    transport = _MixedTransport(review, selection)
    result = prepare_front_stage_flow(batch, inventory, transport,
        lambda output: validate_protocol_control_batch_candidates(batch, output))
    assert result.error is not None and result.wire is None
    assert result.error.code == "REQUIRED_ACTION_DISCARDED"
    assert transport.calls == ["review"]


def test_definition_identified_by_review_is_not_automatically_discarded():
    batch, inventory, review, selection = _background_example(background_only=True)
    quote = "本次审核值为最近两次测量的均值"
    batch.owned_units[0].excerpt = quote + "。"
    inventory.statements[0].quoted_text = quote
    review.items[0].source_action_excerpt = quote
    review.items[0].decision = "unresolved"
    review.items[0].non_control_basis_excerpt = None
    review.items[0].unresolved_aspects = ["该句可能是判定依赖，需核用途"]
    result = prepare_front_stage_flow(batch, inventory, _MixedTransport(review, selection),
        lambda output: validate_protocol_control_batch_candidates(batch, output))
    assert result.error_code == "FLOW_SOURCE_SCOPE_UNRESOLVED"
    assert result.wire is None
    assert result.review.items[0].decision == "unresolved"


@pytest.mark.parametrize("defect", ["required", "definition", "threshold", "unknown", "basis", "changed_source"])
def test_background_cannot_discard_decisive_or_unproven_source(defect):
    batch, inventory, review, selection = _background_example(same_unit=True)
    if defect == "required":
        inventory.statements[1].force = "required"
    elif defect in {"definition", "threshold"}:
        inventory.statements[1].decision_functions = [defect]
    elif defect == "unknown":
        inventory.statements[1].unresolved = ["用途未核清"]
    elif defect == "basis":
        review.items[1].non_control_basis_excerpt = "其他来源"
    else:
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace(
            inventory.statements[1].quoted_text, "受试者必须达到既定条件")
    transport = _MixedTransport(review, selection)
    with_error = None
    try:
        with_error = prepare_front_stage_flow(batch, inventory, transport,
            lambda output: validate_protocol_control_batch_candidates(batch, output))
    except ValueError:
        pass
    assert with_error is None or with_error.error is not None
    assert "author" not in transport.calls and "alignment" not in transport.calls


@pytest.mark.parametrize("layout", ["sentences", "semicolon", "linebreak"])
@pytest.mark.parametrize("review_order", ["source", "reversed"])
def test_same_unit_covered_and_new_points_reach_saved_consumer(layout, review_order):
    batch, inventory, review, selection = _same_unit_mixed_example()
    if layout == "semicolon":
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace("。", "；")
    elif layout == "linebreak":
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace("。", "。\n")
    if review_order == "reversed":
        review.items.reverse()
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    assert transport.calls == ["review", "author", "alignment"]
    assert len(result.final_output.candidates) == 1
    assert [entry.status for entry in result.source_statement_coverage] == ["candidate_linked", "expressed"]
    disposition = result.partial_wire.dispositions[0]
    assert disposition.disposition.value == "other_control_candidate"
    assert disposition.linked_official_code is None
    assert disposition.linked_procedure_catalog_item_ids == []
    assert result.source_target_review.items[0].target_id == next(
        item.target_id for item in review.items if item.statement_index == 0)
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("defect", ["covered_action", "unresolved", "time", "new_action"])
def test_mixed_units_do_not_reclassify_unknown_or_rewrite_shared_scope(defect):
    batch, inventory, review, selection = _same_unit_mixed_example()
    if defect == "covered_action":
        batch.known_procedure_targets[0].covered_action_kinds = []
        batch.known_procedure_targets[0].source_excerpts = ["知情同意记录"]
        review.items[0].target_action_excerpt = "知情同意记录"
    elif defect == "unresolved":
        review.items[1].decision = "unresolved"
    elif defect == "time":
        review.items[0].target_time_excerpt = "D100"
    else:
        selection.action_excerpt = selection.obligation_statement = "另一无来源动作"
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None
    assert transport.calls == (["review", "author"] if defect == "new_action" else ["review"])
    assert result.source_front_target_review is not None or defect in {"time", "covered_action"}
    assert result.attempts[-1].error_classes == [{
        "covered_action": "TARGET_ACTION_LABEL_ONLY_UNPROVEN",
        "unresolved": "FLOW_SOURCE_SCOPE_UNRESOLVED",
        "time": "TARGET_TIME_UNGROUNDED",
        "new_action": "FLOW_ASSEMBLY_INVALID",
    }[defect]]


@pytest.mark.parametrize("change", ["unit_link", "coverage", "front_review", "review_target", "alignment", "source"])
def test_saved_mixed_unit_requires_both_independent_point_proofs(change):
    batch, inventory, review, selection = _same_unit_mixed_example()
    result = ProtocolControlAgentRunner().run(
        batch, _MixedTransport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    restored = type(result).model_validate_json(result.model_dump_json())
    if change == "unit_link":
        restored.partial_wire.dispositions[0].linked_procedure_catalog_item_ids = [review.items[0].target_id]
    elif change == "coverage":
        restored.source_statement_coverage[0].status = "expressed"
    elif change == "front_review":
        restored.source_front_target_review.items = restored.source_front_target_review.items[1:]
    elif change == "review_target":
        restored.source_target_review.items[0].target_id = "unfrozen-target"
    elif change == "alignment":
        restored.source_candidate_alignment.proofs = []
    else:
        batch.owned_units[0].excerpt = batch.owned_units[0].excerpt.replace(selection.action_excerpt, "另一无来源操作")
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


def test_same_unit_action_metadata_cannot_prove_a_neighbours_label():
    from app.agents.protocol_control_fixed_flow import pending_front_wire
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    batch, inventory, review, _ = _same_unit_mixed_example()
    target = batch.known_procedure_targets[0]
    target.source_excerpts = [target.label]
    review.items[0].target_action_excerpt = target.label
    review.items[1] = review.items[0].model_copy(deep=True)
    review.items[1].statement_index = 1
    review.items[1].source_action_excerpt = inventory.statements[1].quoted_text
    coverage = source_statement_coverage(batch, inventory, pending_front_wire(batch))
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, review)
    assert error.value.code == "TARGET_ACTION_LABEL_ONLY_UNPROVEN"
    assert error.value.statement_index == 1


def test_front_postassembly_scope_failure_is_saved_without_parent_reread(monkeypatch):
    import app.agents.protocol_control_source_interpretation as source_module
    import app.agents.protocol_control_deconstructor as runner_module

    batch, inventory, review, selection = _same_unit_mixed_example()
    original = source_module.validate_source_target_review

    def reject_covered_neighbour(batch, interpretation, coverage, actual_review):
        if len(actual_review.items) == 1 and actual_review.items[0].statement_index == 0:
            raise SourceTargetReviewValidationError(
                "装配候选错误表达了邻近已有要求", code="REVIEW_SCOPE_INVALID",
                statement_index=0, json_path="/items", source_refs=tuple(batch.owned_source_span_ids),
            )
        return original(batch, interpretation, coverage, actual_review)

    monkeypatch.setattr(runner_module, "validate_source_target_review", reject_covered_neighbour)
    transport = _MixedTransport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and result.status == "需要核对"
    assert transport.calls == ["review", "author", "alignment"]
    assert result.partial_wire is not None
    assert result.source_front_target_review is not None
    assert result.source_candidate_alignment is not None
    assert result.attempts[-1].error_classes == ["REVIEW_SCOPE_INVALID"]
    assert result.attempts[-1].error_detail["statement_id"] == 0
    restored = type(result).model_validate_json(result.model_dump_json())
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("change", ["candidate", "proof", "missing_candidate", "covered_action"])
def test_mixed_saved_result_does_not_borrow_other_units_proof(change):
    batch, inventory, review, selection = _independent_mixed_example()
    result = ProtocolControlAgentRunner().run(
        batch, _MixedTransport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    restored = type(result).model_validate_json(result.model_dump_json())
    if change == "candidate":
        restored.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].statement = "另一无来源操作"
    elif change == "proof":
        restored.source_candidate_alignment.items[0].source_excerpt = "另一无来源操作"
    elif change == "missing_candidate":
        restored.partial_wire.candidate_drafts = []
    else:
        batch.known_procedure_targets[0].covered_action_kinds = []
        batch.known_procedure_targets[0].source_excerpts = ["知情同意记录"]
        restored.source_front_target_review.items[0].target_action_excerpt = "知情同意记录"
        restored.source_target_review.items[0].target_action_excerpt = "知情同意记录"
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("covered_last", [False, True])
def test_multiple_new_units_preserve_covered_link_and_distinct_alignment(covered_last):
    batch, inventory, review, selection = _independent_mixed_example()
    second_unit = batch.owned_units[1].model_copy(deep=True)
    second_unit.structure_unit_id = "another-independent-action"
    second_unit.source_span_ids = ["span:another-independent-action"]
    second_unit.source_ref = "generic.body.p31"
    second_unit.member_source_refs = [second_unit.source_ref]
    second_unit.source_order += 1
    quote = "拟参加者须完成既往病史核查"
    second_unit.excerpt = "筛选期（D-7~D-1）：" + quote + "。"
    batch.owned_units.append(second_unit)
    batch.owned_structure_unit_ids.append(second_unit.structure_unit_id)
    batch.owned_source_span_ids.extend(second_unit.source_span_ids)
    batch.owned_source_span_ids.sort()
    second_statement = inventory.statements[1].model_copy(deep=True)
    second_statement.structure_unit_id = second_unit.structure_unit_id
    second_statement.quoted_text = quote
    inventory.statements.append(second_statement)
    second_review = review.items[1].model_copy(deep=True)
    second_review.statement_index = 2
    second_review.source_action_excerpt = quote
    review.items.append(second_review)
    second_selection = selection.model_copy(deep=True)
    second_selection.statement_index = 2
    second_selection.action_excerpt = second_selection.obligation_statement = quote
    second_selection.title = second_selection.evidence_description = "既往病史核查"
    second_selection.observation_scope = "筛选期拟参加者的既往病史核查记录"
    second_selection.fact_type = "medical_history"
    if covered_last:
        batch.owned_units = [*batch.owned_units[1:], batch.owned_units[0]]
        batch.owned_structure_unit_ids = [unit.structure_unit_id for unit in batch.owned_units]
        inventory.statements = [*inventory.statements[1:], inventory.statements[0]]
        for item in review.items:
            item.statement_index = (item.statement_index - 1) % 3
        selection.statement_index, second_selection.statement_index = 0, 1
    transport = _MixedTransport(review, [selection, second_selection])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    assert transport.calls == ["review", "author", "author", "alignment"]
    assert len(result.final_output.candidates) == 2
    assert [entry.status for entry in result.source_statement_coverage] == (
        ["expressed", "expressed", "linked_only"] if covered_last else ["linked_only", "expressed", "expressed"])
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    # An added candidate cannot claim expression of a different owned unit,
    # even when its atom points at that unit's span and quote.
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    candidate = restored.partial_wire.candidate_drafts[0]
    covered_statement = inventory.statements[-1 if covered_last else 0]
    covered_unit = next(unit for unit in batch.owned_units
                        if unit.structure_unit_id == covered_statement.structure_unit_id)
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.source_span_ids = covered_unit.source_span_ids
    atom.source_excerpts = [covered_statement.quoted_text]
    atom.statement = covered_statement.quoted_text
    raw_coverage = source_statement_coverage(batch, inventory, restored.partial_wire)
    assert next(entry for entry in raw_coverage
                if entry.structure_unit_id == covered_unit.structure_unit_id).status == "linked_only"
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("metadata", ["empty", "both_empty", "different_action"])
def test_front_grounded_label_cannot_replace_unestablished_action(metadata):
    batch, inventory, review, selection = _covered_procedure_example()
    target = batch.known_procedure_targets[0]
    target.source_excerpts = ["知情同意记录"]
    target.covered_action_kinds = ["collect_biospecimen"] if metadata == "different_action" else []
    if metadata == "both_empty":
        batch.owned_required_action_kinds_by_structure_unit_id = {}
    review.target_action_excerpt = "知情同意记录"
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and result.partial_wire is None
    assert result.source_front_target_review is None  # Invalid evidence is not a validated front proof.
    assert result.session_id == "source-review"
    assert result.attempts[-1].error_classes == ["TARGET_ACTION_LABEL_ONLY_UNPROVEN"]
    assert transport.calls == ["review"]


def test_front_saved_link_cannot_lose_its_action_proof():
    batch, inventory, review, selection = _covered_procedure_example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    _validate_saved_source_review(batch, result)
    batch.known_procedure_targets[0].covered_action_kinds = []
    with pytest.raises(ValueError, match="尚未证明"):
        _validate_saved_source_review(batch, result)


@pytest.mark.parametrize("kind", ["procedure", "official"])
@pytest.mark.parametrize("proof", ["empty", "different_action", "exact", "typed", "different_prose", "clue"])
def test_shared_target_review_requires_action_proof_only_for_complete_label_links(kind, proof):
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    from app.agents.protocol_control_fixed_flow import pending_front_wire

    batch, inventory, review, _ = _covered_procedure_example()
    target = batch.known_procedure_targets[0]
    target.source_excerpts = [target.label + "^a"]
    target.covered_action_kinds = []
    review.target_action_excerpt = target.label
    if proof == "different_action":
        target.covered_action_kinds = ["collect_biospecimen"]
    elif proof == "exact":
        target.source_excerpts.append(inventory.statements[0].quoted_text.rstrip("。"))
    elif proof == "typed":
        target.covered_action_kinds = ["obtain_signature"]
    elif proof == "different_prose":
        target.source_excerpts = ["由受试者完成知情同意签署"]
        review.target_action_excerpt = target.source_excerpts[0]
    elif proof == "clue":
        review.decision = "additional_requirement"
        review.unresolved_aspects = ["目录未载明具体操作要求"]
    if kind == "official":
        batch.known_official_targets = [KnownOfficialRuleTarget(
            catalog_item_id="official-consent", official_code="IN-01", label=target.label, position=0,
            source_span_ids=[f"official-span-{i}" for i in range(len(target.source_excerpts) + 1)],
            source_excerpts=[*target.source_excerpts, "筛选期（D-7~D-1）"],
        )]
        if proof != "clue":
            review.decision = "covered_by_official"
        review.target_id = "IN-01"
        batch.known_procedure_targets = []
    wire = pending_front_wire(batch)
    coverage = source_statement_coverage(batch, inventory, wire)
    result = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[review])
    rejected = proof in {"empty", "different_action"} or (kind == "official" and proof == "typed")
    if rejected:
        with pytest.raises(SourceTargetReviewValidationError) as error:
            validate_source_target_review(batch, inventory, coverage, result)
        assert error.value.code == "TARGET_ACTION_LABEL_ONLY_UNPROVEN"
    else:
        validate_source_target_review(batch, inventory, coverage, result)


def test_baseline_saved_readback_cannot_adopt_a_catalog_name_as_a_complete_action():
    batch, inventory, review, selection = _covered_procedure_example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    result.workflow_variant_requested = BASELINE
    result.workflow_path_executed = "baseline_wire"
    result.source_front_target_review = None
    _validate_saved_source_review(batch, result)
    target = batch.known_procedure_targets[0]
    target.source_excerpts = [target.label + "^a"]
    target.covered_action_kinds = []
    result.source_target_review.items[0].target_action_excerpt = target.label
    with pytest.raises(SourceTargetReviewValidationError) as error:
        _validate_saved_source_review(batch, result)
    assert error.value.code == "TARGET_ACTION_LABEL_ONLY_UNPROVEN"


@pytest.mark.parametrize("marker", ["^26", "^2^6"])
def test_display_footnotes_do_not_turn_a_catalog_label_into_an_action(marker):
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    from app.agents.protocol_control_fixed_flow import pending_front_wire

    batch, inventory, review, _ = _covered_procedure_example()
    target = batch.known_procedure_targets[0]
    target.covered_action_kinds = []
    target.source_excerpts = [target.label + marker]
    review.target_action_excerpt = target.source_excerpts[0]
    coverage = source_statement_coverage(batch, inventory, pending_front_wire(batch))
    result = SourceTargetReview(version=SOURCE_TARGET_REVIEW_VERSION, items=[review])
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_target_review(batch, inventory, coverage, result)
    assert error.value.code == "TARGET_ACTION_LABEL_ONLY_UNPROVEN"
    assert review.target_action_excerpt == target.label + marker


def test_identical_scope_and_body_still_require_the_body_time_fragment():
    from app.agents.protocol_control_source_interpretation import _unreported_time_fragments

    _, inventory, _, _ = _separate_heading_example()
    statement = inventory.statements[0]
    statement.quoted_text = statement.scope_quote = statement.affected_stage = "筛选期"
    statement.time_words = []
    assert _unreported_time_fragments(statement) == ["筛选期"]


def _baseline_policy_example(source_types):
    batch, inventory, review, selection = _example()
    selection.required_source_types = []
    seed = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert seed.final_output is not None
    wire = seed.partial_wire.model_copy(deep=True)
    wire.candidate_drafts[0].minimum_evidence[0].required_source_types = source_types

    class Baseline(_Transport):
        def start(self, *, prompt):
            self.calls.append("wire")
            assert "原文未限定时必须为空列表 []" in prompt
            return ProtocolControlAgentResponse(session_id="baseline-author", text=wire.model_dump_json())

    return batch, inventory, Baseline(review, selection)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "wrong_row", "wrong_span", "other_quote",
                                   "boolean_flip", "unknown_as_false", "validity", "source_types"])
def test_explicit_policy_dimensions_reject_incomplete_or_inconsistent_positive(defect):
    from app.agents.protocol_control_candidate_alignment import (
        EvidencePolicyCheckError, SourceCandidateAlignmentItem, _validate_evidence_policy_checks,
    )
    batch, inventory, review, selection = _example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    candidate = result.partial_wire.candidate_drafts[0]
    payload = result.source_candidate_alignment.items[0].model_dump(mode="json")
    checks = payload["evidence_policy_checks"]
    assert len(checks) == 4
    if defect == "missing":
        checks.pop()
    elif defect == "duplicate":
        checks.append(checks[0].copy())
    elif defect == "wrong_row":
        checks[0]["evidence_index"] = 1
    elif defect == "wrong_span":
        checks[0]["source_span_id"] = "another-source"
    elif defect == "other_quote":
        checks[0]["source_excerpt"] = "另一项资料要求"
    elif defect == "boolean_flip":
        candidate.minimum_evidence[0].source_policy.requires_contemporaneous_objective_source = True
        checks[0]["boolean_value"] = False
    elif defect == "unknown_as_false":
        assert candidate.minimum_evidence[0].source_policy.requires_contemporaneous_objective_source is None
        checks[0]["boolean_value"] = False
    elif defect == "validity":
        checks[2]["validity_status"] = "not_specified"
    else:
        checks[3]["source_types"] = ["无源附加记录"]
    with pytest.raises(EvidencePolicyCheckError) as caught:
        _validate_evidence_policy_checks(candidate, SourceCandidateAlignmentItem.model_validate(payload))
    detail = caught.value.error_detail
    assert detail["statement_ids"] == [0] and detail["candidate_indexes"] == [0]
    assert detail["reason"] == {
        "missing": "missing_dimension", "duplicate": "duplicate", "wrong_row": "out_of_scope",
        "wrong_span": "source_mismatch", "other_quote": "source_mismatch",
    }.get(defect, "value_mismatch")
    assert detail["json_path"].startswith("/candidate_drafts/0/minimum_evidence")
    assert detail["source_refs"] == ([] if defect == "wrong_row" else
                                   candidate.minimum_evidence[0].source_policy.source_span_ids)


@pytest.mark.parametrize("variant", [BASELINE, FIXED_FLOW])
def test_policy_dimension_failure_reaches_saved_runner_without_rereading(variant):
    if variant == BASELINE:
        batch, inventory, transport = _baseline_policy_example(["知情同意记录"])
    else:
        batch, inventory, review, selection = _example()
        transport = _Transport(review, selection)
    original_reader = transport.start_source_candidate_alignment
    rejected_text = []

    def missing_dimension(*, prompt):
        response = original_reader(prompt=prompt)
        payload = json.loads(response.text)
        assert payload["items"][0]["evidence_policy_checks"].pop()["dimension"] == "required_source_types"
        text = json.dumps(payload, ensure_ascii=False)
        rejected_text.append(text)
        return ProtocolControlAgentResponse(session_id=response.session_id, text=text)

    transport.start_source_candidate_alignment = missing_dimension
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=variant,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None
    assert transport.calls == (["wire", "alignment"] if variant == BASELINE else
                               ["review", "author", "alignment"])
    restored = type(result).model_validate_json(result.model_dump_json())
    failure = restored.attempts[-1]
    assert failure.error_classes == ["EVIDENCE_POLICY_UNJUSTIFIED"]
    assert failure.error_detail["reason"] == "missing_dimension"
    assert failure.error_detail["dimension"] == "required_source_types"
    assert failure.error_detail["json_path"] == "/candidate_drafts/0/minimum_evidence/0/required_source_types"
    assert failure.error_detail["retry_class"] == "source_semantic_review"
    actual = next(attempt for attempt in result.attempts if attempt.raw_output_text == rejected_text[0])
    saved = next(attempt for attempt in restored.attempts if attempt.attempt == actual.attempt)
    assert saved.raw_output_sha256 == actual.raw_output_sha256
    assert saved.raw_output_text is None  # Raw clinical answers use the private artifact, not this DTO.
    from app.services.protocol_control_execution import _deep_attempt_raw_outputs
    private_answers = _deep_attempt_raw_outputs(result)
    assert next(row for row in private_answers if row["attempt"] == actual.attempt)["raw_output_text"] == rejected_text[0]


def test_policy_check_preserves_full_time_constraint_and_partial_disagreement():
    from app.agents.protocol_control_candidate_alignment import (
        SourceCandidateAlignmentItem, _validate_evidence_policy_checks,
    )
    from app.domain.contracts.rules import TimeConstraint
    batch, inventory, review, selection = _example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW, output_validator=lambda output: None,
    )
    candidate = result.partial_wire.candidate_drafts[0]
    policy = candidate.minimum_evidence[0].source_policy
    policy.result_validity_status = "specified"
    policy.result_validity_constraint = TimeConstraint(
        anchor_type="screening_date", direction="before", upper_bound_days=14,
    )
    payload = result.source_candidate_alignment.items[0].model_dump(mode="json")
    payload["evidence_policy_checks"][2].update(
        validity_status="specified", validity_constraint=policy.result_validity_constraint.model_dump(mode="json"),
    )
    _validate_evidence_policy_checks(candidate, SourceCandidateAlignmentItem.model_validate(payload))
    payload["evidence_policy_checks"][2]["validity_constraint"]["upper_bound_days"] = 30
    with pytest.raises(ValueError, match="不一致"):
        _validate_evidence_policy_checks(candidate, SourceCandidateAlignmentItem.model_validate(payload))
    payload.update(decision="uncertain", unresolved_dimensions=["有效期限原文尚未判清"])
    payload["evidence_policy_checks"] = payload["evidence_policy_checks"][2:3]
    _validate_evidence_policy_checks(candidate, SourceCandidateAlignmentItem.model_validate(payload))
    assert candidate.minimum_evidence[0].source_policy.result_validity_constraint.upper_bound_days == 14


def test_policy_source_type_order_is_not_a_semantic_difference():
    from app.agents.protocol_control_candidate_alignment import (
        SourceCandidateAlignmentItem, _validate_evidence_policy_checks,
    )
    batch, inventory, review, selection = _example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW, output_validator=lambda output: None,
    )
    candidate = result.partial_wire.candidate_drafts[0]
    candidate.minimum_evidence[0].required_source_types = ["原始病历", "原始报告"]
    payload = result.source_candidate_alignment.items[0].model_dump(mode="json")
    payload["evidence_policy_checks"][3]["source_types"] = ["原始报告", "原始病历"]
    _validate_evidence_policy_checks(candidate, SourceCandidateAlignmentItem.model_validate(payload))


@pytest.mark.parametrize("source", ["source_span_id", "source_excerpt"])
def test_policy_check_rejects_blank_provenance(source):
    from app.agents.protocol_control_candidate_alignment import EvidencePolicyCheck
    payload = dict(evidence_index=0, dimension="contemporaneous_objective_source",
                   boolean_value=None, source_span_id="span:1", source_excerpt="原文")
    payload[source] = " "
    with pytest.raises(ValueError):
        EvidencePolicyCheck.model_validate(payload)


def test_ordinary_alignment_dump_does_not_change_legacy_identity():
    from app.agents.protocol_control_candidate_alignment import SourceCandidateAlignmentItem
    payload = dict(statement_index=0, candidate_index=0, decision="fully_expressed",
                   source_excerpt="完成规定核查", candidate_atom_quotes=["完成规定核查"],
                   unresolved_dimensions=[])
    assert SourceCandidateAlignmentItem.model_validate(payload).model_dump(mode="json") == payload


def test_saved_policy_dimension_mutation_rejects_actual_response_proof():
    batch, inventory, review, selection = _example()
    result = ProtocolControlAgentRunner().run(
        batch, _Transport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    restored = type(result).model_validate_json(result.model_dump_json())
    _validate_saved_source_review(batch, restored)
    restored.source_candidate_alignment.items[0].evidence_policy_checks.pop()
    with pytest.raises(ValueError):
        _validate_saved_source_review(batch, restored)


@pytest.mark.parametrize("source_types", [[], ["知情同意记录"]])
def test_baseline_policy_review_uses_existing_runner_proof_and_saved_consumer(source_types):
    batch, inventory, transport = _baseline_policy_example(source_types)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=BASELINE,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is not None
    assert transport.calls == (["wire", "alignment"] if source_types else ["wire"])
    _validate_saved_source_review(batch, result)
    assert result.partial_wire.candidate_drafts[0].minimum_evidence[0].required_source_types == source_types
    if source_types:
        assert result.source_candidate_alignment.proofs
        result.source_candidate_alignment.proofs = []
        with pytest.raises(ValueError, match="核对证明"):
            _validate_saved_source_review(batch, result)


@pytest.mark.parametrize("failure", ["incomplete", "uncertain", "transport", "budget", "identity", "interrupted"])
def test_baseline_policy_disagreement_does_not_adopt_or_reread(failure):
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
    from app.llm.logical_call_budget import LogicalCallBudgetExhausted

    batch, inventory, transport = _baseline_policy_example(["病历记录", "检查记录"])

    def failed_review(*, prompt):
        transport.calls.append("alignment")
        assert "无源新增限制选 incomplete" in prompt
        if failure == "transport":
            raise RuntimeError("synthetic transport failure")
        if failure == "budget":
            raise LogicalCallBudgetExhausted("synthetic budget exhausted")
        if failure == "identity":
            from app.agents.protocol_control_agent_transport import ProtocolControlModelIdentityError
            raise ProtocolControlModelIdentityError("synthetic wrong model", configured_model="expected", reason="mismatch")
        if failure == "interrupted":
            from app.agents.protocol_control_agent_transport import ProtocolControlAgentCallError
            raise ProtocolControlAgentCallError("policy-review", "synthetic interrupted response", uncertain_completion=True)
        return ProtocolControlAgentResponse(session_id="policy-review", text=json.dumps({
            "version": SOURCE_CANDIDATE_ALIGNMENT_VERSION,
            "items": [{"statement_index": 0, "candidate_index": 0, "decision": failure,
                       "source_excerpt": inventory.statements[0].quoted_text,
                       "candidate_atom_quotes": [inventory.statements[0].quoted_text],
                       "unresolved_dimensions": ["原文未限定必须使用该类记录"]}],
        }, ensure_ascii=False))

    transport.start_source_candidate_alignment = failed_review
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=BASELINE,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and result.partial_wire is not None
    assert transport.calls == ["wire", "alignment"]
    expected = {"transport": "SOURCE_CANDIDATE_ALIGNMENT_TRANSPORT_FAILED",
                "budget": "LOGICAL_BUDGET_EXHAUSTED", "identity": "MODEL_IDENTITY_INVALID",
                "interrupted": "FLOW_COMPLETION_UNCERTAIN"}.get(failure, "EVIDENCE_POLICY_UNJUSTIFIED")
    assert result.attempts[-1].error_classes == [expected]
    if failure in {"incomplete", "uncertain"}:
        assert result.source_candidate_alignment.items[0].decision == failure
    assert result.partial_wire.candidate_drafts[0].minimum_evidence[0].required_source_types == ["病历记录", "检查记录"]


def test_scope_stage_and_separate_window_reach_author_and_saved_alignment():
    batch, inventory, review, selection = _separate_heading_example()
    statement = inventory.statements[0]
    statement.affected_stage = statement.scope_quote
    statement.time_words = ["D-7~D-1"]
    validate_source_interpretation(batch, inventory)
    assert supports_front_stage_flow(batch, inventory)
    transport = _Transport(review, selection)
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_source_interpretation=inventory, workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.status == "已解析" and result.final_output is not None
    assert transport.calls == ["review", "author", "alignment"]
    _validate_saved_source_review(batch, result)
    assert result.final_output.candidates[0].semantics.review_node_bindings[0].scope_citation.source_excerpt == statement.scope_quote


@pytest.mark.parametrize("loss", ["empty_window", "partial_window", "wrong_stage", "duration", "intraday"])
def test_scope_stage_does_not_excuse_missing_window_or_another_timing_dimension(loss):
    batch, inventory, _, _ = _separate_heading_example()
    statement = inventory.statements[0]
    statement.affected_stage = statement.scope_quote
    statement.time_words = ["D-7~D-1"]
    if loss == "empty_window":
        statement.time_words = []
    elif loss == "partial_window":
        statement.time_words = ["D-7"]
    elif loss == "wrong_stage":
        statement.affected_stage = "基线期"
    else:
        suffix = "连续7天" if loss == "duration" else "给药前90分钟"
        batch.owned_units[0].excerpt += suffix
        statement.quoted_text += suffix
    with pytest.raises(SourceInterpretationValidationError):
        validate_source_interpretation(batch, inventory)


@pytest.mark.parametrize("support", ["label_only", "action_metadata", "exact_source"])
def test_front_review_exposes_the_same_action_boundary_as_the_saved_consumer(support):
    from app.agents.protocol_control_fixed_flow import build_front_target_review_prompt, pending_front_wire
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    batch, inventory, review, selection = _covered_procedure_example()
    target = batch.known_procedure_targets[0]
    if support == "label_only":
        target.source_excerpts = [target.label]
        target.covered_action_kinds = []
    elif support == "exact_source":
        target.source_excerpts = [inventory.statements[0].quoted_text]
        target.covered_action_kinds = []
    prompt = build_front_target_review_prompt(batch, inventory,
        source_statement_coverage(batch, inventory, pending_front_wire(batch)))
    proofs = json.loads(prompt.rsplit("当前动作依据范围：", 1)[1])
    assert proofs == [{"statement_index": 0, "action_supported_target_ids": (
        [] if support == "label_only" else [target.catalog_item_id])}]
    assert target.catalog_item_id in prompt  # Unsupported target remains visible as a source clue.
    assert "这不是完整语义或时间核对的结论" in prompt
    assert "选 additional_requirement" in prompt
