from __future__ import annotations

import json
from itertools import product

import pytest

from app.agents.protocol_deconstructor import (
    ProtocolDeconstructionAttempt,
    ProtocolDeconstructionRunResult,
    ProtocolAgentResponse,
    ProtocolDeconstructorRunner,
    _parse_semantic_candidate,
    _plan_semantic_rule_batches,
    _merge_semantic_batches,
    _repair_batch_id,
    _validate_semantic_batch,
    _validate_semantic_repair,
    _collect_initial_semantic_response,
    _apply_semantic_repair,
    _hydrate_semantic_candidate,
    _parse_protocol_draft,
    _recover_exact_fragments,
    _wire_atom,
    _wire_time_constraint,
    _wire_time_quantity,
    build_protocol_deconstruction_prompt,
    regressing_rule_codes,
    _select_repair_rule_codes,
    protocol_prompt_template_sha256,
    protocol_output_response_format,
    revise_protocol_draft_from_feedback,
    semantic_candidate_from_draft,
)
from app.domain.contracts.agents import PromptVersion
from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate,
    ProtocolSemanticRuleRepair,
    SemanticEvidenceRequirement,
    SemanticRule,
    SemanticRuleComponent,
)
from app.domain.contracts.enums import (
    AgentNode,
    AnchorResolutionMode,
    InterpretationSourceType,
    LogicalOperator,
    ReviewStage,
)
from app.domain.contracts.normalization import UnresolvedItem
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationSource,
)
from app.domain.contracts.rules import iter_atomic_predicates
from app.protocols.deconstruction_gate import ProtocolGateIssue
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.start_prompts = []
        self.repair_prompts = []
        self.start_output_kinds = []
        self.repair_output_kinds = []

    def start(self, *, prompt, output_kind="semantic_candidate"):
        self.start_prompts.append(prompt)
        self.start_output_kinds.append(output_kind)
        return self.responses.pop(0)

    def continue_session(
        self, *, session_id, prompt, output_kind="semantic_candidate"
    ):
        self.repair_prompts.append((session_id, prompt))
        self.repair_output_kinds.append(output_kind)
        return self.responses.pop(0)


class CompactFakeTransport(FakeTransport):
    uses_compact_wire_contract = True

    def __init__(self, responses):
        super().__init__(responses)
        self.compact_contexts = []
        self.histories = {}
        self.request_histories = []
        self.output_scopes = []

    def configure_output_scope(self, **scope):
        self.output_scopes.append(scope)

    def semantic_cache_identity(self, *, output_kind):
        return f"compact-fake:{output_kind}:{self.output_scopes[-1]}"

    def start(self, *, prompt, output_kind="semantic_candidate"):
        response = super().start(prompt=prompt, output_kind=output_kind)
        history = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.text},
        ]
        self.histories[response.session_id] = history
        self.request_histories.append([dict(item) for item in history])
        return response

    def continue_session(
        self, *, session_id, prompt, output_kind="semantic_candidate"
    ):
        request = [
            *self.histories[session_id],
            {"role": "user", "content": prompt},
        ]
        self.request_histories.append([dict(item) for item in request])
        response = super().continue_session(
            session_id=session_id,
            prompt=prompt,
            output_kind=output_kind,
        )
        self.histories[session_id] = [
            *request,
            {"role": "assistant", "content": response.text},
        ]
        return response

    def compact_session_history(self, *, session_id, context):
        self.compact_contexts.append((session_id, context))
        self.histories[session_id] = [
            {"role": "user", "content": context},
            {"role": "assistant", "content": "已保留冻结上下文和批次身份。"},
        ]


class FailingStartTransport:
    def start(self, *, prompt, output_kind="semantic_candidate"):
        raise RuntimeError("上游连续返回空正文")


class FailingRepairTransport(FakeTransport):
    def continue_session(
        self, *, session_id, prompt, output_kind="semantic_candidate"
    ):
        self.repair_prompts.append((session_id, prompt))
        self.repair_output_kinds.append(output_kind)
        raise RuntimeError("修订请求未完成")


class MemoryBatchCache:
    def __init__(self):
        self.items = {}

    def load(self, cache_key):
        return self.items.get(cache_key)

    def store(
        self,
        cache_key,
        response_text,
        *,
        cache_contract="protocol-semantic-batch/v1",
    ):
        del cache_contract
        self.items[cache_key] = response_text


def _prompt_version(template):
    return PromptVersion(
        prompt_version_id="protocol-deconstructor/v1",
        node=AgentNode.PROTOCOL_DECONSTRUCTOR,
        template_sha256=protocol_prompt_template_sha256(template),
        schema_version_id="protocol-deconstruction-draft/fixture-v1",
    )


def _semantic_candidate(source_input, draft):
    source_text = {
        material.source_span_id: material.text
        for material in source_input.source_materials
    }
    return ProtocolSemanticDeconstructionCandidate(
        candidate_id="candidate-1",
        proposed_rules=[
            SemanticRule(
                official_code=rule.official_code,
                components=[
                    SemanticRuleComponent(
                        title=component.title,
                        expression=component.expression,
                        exception_expression=component.exception_expression,
                        evidence_requirements=[
                            SemanticEvidenceRequirement(
                                fact_type=requirement.fact_type,
                                required_source_types=requirement.required_source_types,
                                allows_screening_record_transcription=(
                                    requirement.allows_screening_record_transcription
                                ),
                                requires_contemporaneous_objective_source=(
                                    requirement.requires_contemporaneous_objective_source
                                ),
                                due_stage=requirement.due_stage,
                                description=requirement.description,
                            )
                            for requirement in component.evidence_requirements
                        ],
                        source_span_ids=next(
                            item.source_refs
                            for item in draft.component_drafts
                            if item.proposed_component.rule_component_id
                            == component.rule_component_id
                        ),
                        source_excerpts=[
                            source_text[
                                next(
                                    item.source_refs[0]
                                    for item in draft.component_drafts
                                    if item.proposed_component.rule_component_id
                                    == component.rule_component_id
                                )
                            ]
                        ],
                    )
                    for component in rule.components
                ],
            )
            for rule in draft.proposed_rules
        ],
        created_by_agent_call_id="agent-call-1",
    )


def _wire_candidate(candidate, *, batch_id="1/1"):
    def atom_wire(expression, *, negated=False):
        if expression.kind != "predicate":
            raise AssertionError("DNF test encoder expects an atomic expression")
        predicate = expression.predicate.model_dump(mode="json")
        predicate_id = predicate.pop("predicate_id")
        del predicate_id
        source_clause = predicate.pop("source_clause")
        source_clauses = predicate.pop("source_clauses")
        predicate["source_locator"] = (
            {"source_clause": source_clause}
            if source_clause is not None
            else {"source_clauses": source_clauses}
        )
        comparator = predicate.pop("comparator")
        value = predicate.pop("value")
        predicate.pop("unit_match_policy", None)
        predicate["time_constraint"] = (
            expression.time_constraint.model_dump(mode="json")
            if expression.time_constraint is not None
            else None
        )
        predicate["negated"] = negated
        if comparator == "exists":
            predicate.pop("unit", None)
            predicate.pop("value", None)
            return "existence", predicate
        if comparator in {"in", "not_in"}:
            predicate["comparator"] = comparator
            predicate["values"] = value
            return "set", predicate
        predicate["comparator"] = comparator
        predicate["value"] = value
        return "scalar", predicate

    def dnf(expression, *, negated=False):
        if expression.kind == "predicate":
            return [[(expression, negated)]]
        if expression.operator == LogicalOperator.NOT:
            return dnf(expression.children[0], negated=not negated)
        if negated:
            raise AssertionError("test encoder does not distribute NOT over compound DNF")
        child_groups = [dnf(child) for child in expression.children]
        if expression.operator == LogicalOperator.ANY:
            return [group for groups in child_groups for group in groups]
        if expression.operator == LogicalOperator.ALL:
            groups = [[]]
            for alternatives in child_groups:
                groups = [left + right for left, right in product(groups, alternatives)]
            return groups
        raise AssertionError(f"unsupported operator: {expression.operator}")

    def wire_expression(expression):
        groups = []
        for group in dnf(expression):
            shaped = {"existence_atoms": [], "scalar_atoms": [], "set_atoms": []}
            for atomic, negated in group:
                shape, atom = atom_wire(atomic, negated=negated)
                shaped[f"{shape}_atoms"].append(atom)
            groups.append(shaped)
        return groups

    rules = []
    for rule in candidate.proposed_rules:
        components = []
        for component in rule.components:
            components.append(
                {
                    "title": component.title,
                    "expression": wire_expression(component.expression),
                    "exception_expression": (
                        wire_expression(component.exception_expression)
                        if component.exception_expression is not None
                        else None
                    ),
                    "evidence_requirements": [
                        requirement.model_dump(mode="json")
                        for requirement in component.evidence_requirements
                    ],
                    "source_span_ids": list(component.source_span_ids),
                    "source_excerpts": list(component.source_excerpts),
                }
            )
        rules.append({"official_code": rule.official_code, "components": components})
    return {
        "wire_version": "dnf-v1",
        "candidate_id": candidate.candidate_id,
        "batch_id": batch_id,
        "proposed_rules": rules,
        "structural_warnings": [
            item.model_dump(mode="json") for item in candidate.structural_warnings
        ],
        "unresolved_items": [
            item.model_dump(mode="json") for item in candidate.unresolved_items
        ],
        "created_by_agent_call_id": candidate.created_by_agent_call_id,
    }


def test_hydrated_draft_can_recover_semantic_candidate_for_persisted_repair():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    hydrated = _parse_protocol_draft(candidate.model_dump_json(), source_input)

    recovered = semantic_candidate_from_draft(hydrated)

    assert recovered.candidate_id == candidate.candidate_id
    assert recovered.proposed_rules == candidate.proposed_rules
    assert recovered.created_by_agent_call_id == candidate.created_by_agent_call_id


def test_compact_wire_candidate_hydrates_logic_exception_timing_and_unresolved_items():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    payload = _wire_candidate(candidate)
    component = payload["proposed_rules"][1]["components"][0]
    predicate_atom = component["expression"][0]["scalar_atoms"][0]
    predicate_atom["negated"] = True
    predicate_atom["source_locator"] = {
        "source_clause": "不符合ALT或AST≥1.5×ULN"
    }
    predicate_atom["time_constraint"] = {
        "anchor_type": "screening_date",
        "direction": "before",
        "lower_bound_days": None,
        "upper_bound_days": None,
        "lower_bound": None,
        "upper_bound": {"value": 4, "unit": "week"},
        "half_life_multiplier": None,
        "allow_partial_date": False,
    }
    component["exception_expression"] = [
        {
            "existence_atoms": [],
            "scalar_atoms": [json.loads(json.dumps(predicate_atom))],
            "set_atoms": [],
        }
    ]
    payload["unresolved_items"] = [
        {
            "code": "TIME_ANCHOR_UNRESOLVED",
            "affected_scope": ["EX-01"],
            "source_refs": ["span-ex"],
        }
    ]

    parsed = _parse_semantic_candidate(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )

    expression = parsed.proposed_rules[1].components[0].expression
    assert expression.kind == "logical"
    assert expression.operator == LogicalOperator.ANY
    assert expression.children[0].operator == LogicalOperator.NOT
    assert expression.children[0].children[0].predicate.comparator.value == "gte"
    assert (
        expression.children[0].children[0].predicate.source_clause
        == "不符合ALT或AST≥1.5×ULN"
    )
    assert (
        expression.children[0].children[0].time_constraint.upper_bound.unit.value
        == "week"
    )
    exception = parsed.proposed_rules[1].components[0].exception_expression
    assert exception is not None
    assert exception.kind == "logical"
    assert exception.operator == LogicalOperator.NOT
    exception_predicate = exception.children[0].predicate
    assert exception_predicate.predicate_id != (
        expression.children[0].children[0].predicate.predicate_id
    )
    assert parsed.unresolved_items[0].code == "TIME_ANCHOR_UNRESOLVED"


def test_wire_optional_objects_normalize_only_when_semantically_empty():
    assert _wire_time_quantity({"value": None, "unit": None}) is None
    assert _wire_time_constraint(
        {
            "anchor_type": None,
            "direction": None,
            "lower_bound_days": None,
            "upper_bound_days": None,
            "lower_bound": {"value": None, "unit": None},
            "upper_bound": {"value": None, "unit": None},
            "half_life_multiplier": None,
            "combined_window_selection": None,
            "allow_partial_date": False,
        }
    ) is None

    longer = _wire_time_constraint(
        {
            "anchor_type": "first_dose_date",
            "direction": "before",
            "lower_bound_days": None,
            "upper_bound_days": None,
            "lower_bound": {"value": 3, "unit": "month"},
            "upper_bound": None,
            "half_life_multiplier": 5,
            "combined_window_selection": "longer_of_calendar_and_half_life",
            "allow_partial_date": False,
        }
    )
    assert longer is not None
    assert longer["combined_window_selection"] == "longer_of_calendar_and_half_life"
    assert longer["half_life_multiplier"] == 5
    with pytest.raises(ValueError, match="combined_window_selection"):
        _wire_time_constraint(
            {
                "anchor_type": "first_dose_date",
                "direction": "before",
                "lower_bound_days": None,
                "upper_bound_days": None,
                "lower_bound": {"value": 3, "unit": "month"},
                "upper_bound": None,
                "half_life_multiplier": 5,
                "combined_window_selection": "guessed_from_or",
                "allow_partial_date": False,
            }
        )

    predicate = _wire_atom(
        {
            "subject": "受试者",
            "attribute": "既往病史",
            "source_locator": {"source_clause": "既往病史"},
            "requires_professional_judgment": False,
            "negated": False,
            "occurrence_window": {
                "duration": {"value": None, "unit": None},
                "minimum_count": None,
            },
            "prospective_window": {
                "anchor_type": None,
                "upper_bound": {"value": None, "unit": None},
            },
            "prospective_period": {"period": None},
        },
        shape="existence",
    )
    assert predicate["occurrence_window"] is None
    assert predicate["prospective_window"] is None
    assert predicate["prospective_period"] is None
    assert predicate["requires_professional_judgment"] is False
    assert predicate["unit_match_policy"] == "exact_canonical_label"


def test_wire_partial_semantic_objects_are_rejected_precisely():
    with pytest.raises(ValueError, match="时间数量的 value 和 unit"):
        _wire_time_quantity({"value": 1, "unit": None})
    with pytest.raises(ValueError, match="时间约束的 direction"):
        _wire_time_constraint(
            {
                "anchor_type": "screening_date",
                "direction": None,
                "allow_partial_date": False,
            }
        )
    with pytest.raises(ValueError, match="occurrence_window 的 duration"):
        _wire_atom(
            {
                "subject": "受试者",
                "attribute": "病史",
                "source_locator": {"source_clause": "病史"},
                "requires_professional_judgment": False,
                "negated": False,
                "occurrence_window": {"duration": None, "minimum_count": 1},
            },
            shape="existence",
        )
    with pytest.raises(ValueError, match="prospective_window 的 upper_bound"):
        _wire_atom(
            {
                "subject": "受试者",
                "attribute": "计划",
                "source_locator": {"source_clause": "计划"},
                "requires_professional_judgment": False,
                "negated": False,
                "prospective_window": {
                    "anchor_type": "last_dose_date",
                    "upper_bound": None,
                },
            },
            shape="existence",
        )


def test_wire_candidate_round_trips_exact_domain_semantics_without_policy_field():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    payload = _wire_candidate(candidate)

    assert all(
        "unit_match_policy" not in atom
        for rule in payload["proposed_rules"]
        for component in rule["components"]
        for expression in (component["expression"], component["exception_expression"])
        if expression is not None
        for group in expression
        for atom_group in (
            group["existence_atoms"],
            group["scalar_atoms"],
            group["set_atoms"],
        )
        for atom in atom_group
    )
    parsed = _parse_semantic_candidate(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )

    def without_internal_identity(value):
        if isinstance(value, dict):
            return {
                key: without_internal_identity(item)
                for key, item in value.items()
                if key not in {"predicate_id", "unit_match_policy"}
            }
        if isinstance(value, list):
            return [without_internal_identity(item) for item in value]
        return value

    assert without_internal_identity(parsed.model_dump(mode="json")) == (
        without_internal_identity(candidate.model_dump(mode="json"))
    )
    assert all(
        predicate.unit_match_policy == "exact_canonical_label"
        for rule in parsed.proposed_rules
        for component in rule.components
        for expression in (
            component.expression,
            component.exception_expression,
        )
        if expression is not None
        for predicate in iter_atomic_predicates(expression)
    )


def test_compact_wire_round_trips_each_comparator_shape_and_categorical_dnf():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    payload = _wire_candidate(candidate)
    component = payload["proposed_rules"][1]["components"][0]
    first_scalar = component["expression"][0]["scalar_atoms"][0]
    second_scalar = component["expression"][1]["scalar_atoms"][0]
    first_scalar["comparator"] = "gte"
    first_scalar["value"] = 1.5
    first_scalar["unit"] = "ULN"
    second_scalar["comparator"] = "eq"
    second_scalar["value"] = 2
    second_scalar["unit"] = "unitless"
    existence_atom = {
        **json.loads(json.dumps(first_scalar)),
        "subject": "受试者",
        "attribute": "肝功能记录",
        "source_locator": {"source_clause": "肝功能记录"},
        "negated": False,
    }
    existence_atom.pop("comparator")
    existence_atom.pop("value")
    existence_atom.pop("unit")
    component["expression"][0]["existence_atoms"] = [existence_atom]
    first_scalar["time_constraint"] = {
        "anchor_type": "screening_date",
        "direction": "before",
        "lower_bound_days": None,
        "upper_bound_days": None,
        "lower_bound": None,
        "upper_bound": {"value": 4, "unit": "week"},
        "half_life_multiplier": None,
        "allow_partial_date": False,
    }
    component["expression"][0]["scalar_atoms"] = [first_scalar]
    set_atom = json.loads(json.dumps(second_scalar))
    set_atom.pop("value")
    set_atom.update({"comparator": "in", "values": ["ALT", "AST"]})
    component["expression"][0]["set_atoms"] = [set_atom]
    component["exception_expression"] = [
        {
            "existence_atoms": [existence_atom],
            "scalar_atoms": [],
            "set_atoms": [],
        }
    ]

    parsed = _parse_semantic_candidate(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )
    parsed_component = parsed.proposed_rules[1].components[0]
    predicates = list(iter_atomic_predicates(parsed_component.expression))
    assert parsed_component.expression.operator == LogicalOperator.ANY
    assert parsed_component.expression.children[0].operator == LogicalOperator.ALL
    assert parsed_component.exception_expression.kind == "predicate"
    assert {predicate.comparator.value for predicate in predicates} == {
        "exists",
        "gte",
        "eq",
        "in",
    }
    by_attribute_and_comparator = {
        (predicate.attribute, predicate.comparator.value): predicate
        for predicate in predicates
    }
    assert by_attribute_and_comparator[("ALT", "gte")].value == 1.5
    assert by_attribute_and_comparator[("ALT", "gte")].unit == "ULN"
    assert by_attribute_and_comparator[("AST", "in")].value == ["ALT", "AST"]
    assert by_attribute_and_comparator[("AST", "in")].unit == "unitless"
    assert by_attribute_and_comparator[("肝功能记录", "exists")].value is None
    assert by_attribute_and_comparator[("肝功能记录", "exists")].predicate_id != (
        parsed_component.exception_expression.predicate.predicate_id
    )
    assert (
        parsed_component.expression.children[0].children[1].time_constraint.upper_bound.unit.value
        == "week"
    )


def test_compact_wire_rejects_obsolete_mixed_comparator_shape():
    source_input, draft, _spans = _fixture()
    payload = _wire_candidate(_semantic_candidate(source_input, draft))
    component = payload["proposed_rules"][1]["components"][0]
    scalar_atom = component["expression"][0]["scalar_atoms"][0]
    scalar_atom["comparator"] = "exists"

    with pytest.raises(ValueError, match="wire scalar atom 的 comparator 无效"):
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )


def test_compact_wire_requires_exact_source_term_for_numeric_atom():
    source_input, draft, _spans = _fixture()
    payload = _wire_candidate(_semantic_candidate(source_input, draft))
    scalar_atom = payload["proposed_rules"][1]["components"][0]["expression"][0][
        "scalar_atoms"
    ][0]
    scalar_atom.pop("source_term")

    with pytest.raises(ValueError, match="source_term"):
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )


def test_compact_wire_schema_requires_numeric_source_term_but_not_set_source_term():
    schema = protocol_output_response_format(
        "semantic_candidate",
        compact=True,
    )["json_schema"]["schema"]
    group = schema["$defs"]["wire_dnf_group"]

    assert "source_term" in group["properties"]["scalar_atoms"]["items"]["required"]
    assert "source_term" not in group["properties"]["set_atoms"]["items"]["required"]


def test_compact_wire_schema_is_bounded_to_frozen_batch_scope():
    schema = protocol_output_response_format(
        "semantic_candidate",
        compact=True,
        official_codes=["IN-04", "IN-05", "IN-06"],
        allowed_source_span_ids=["span-4a", "span-4b", "span-5", "span-6"],
        component_limit=8,
        group_limit=4,
        atom_limit=8,
        requirement_limit=8,
    )["json_schema"]["schema"]
    rules = schema["properties"]["proposed_rules"]
    rule = rules["items"]
    component = rule["properties"]["components"]

    assert rules["minItems"] == rules["maxItems"] == 3
    assert rule["properties"]["official_code"]["enum"] == [
        "IN-04",
        "IN-05",
        "IN-06",
    ]
    assert component["maxItems"] == 8
    assert component["items"]["properties"]["expression"]["maxItems"] == 4
    assert schema["$defs"]["wire_dnf_group"]["properties"]["scalar_atoms"][
        "maxItems"
    ] == 8
    assert component["items"]["properties"]["source_span_ids"]["maxItems"] == 4

def test_compact_batch_prompt_omits_unrequested_source_and_full_schema_prose():
    source_input, _draft, _spans = _fixture()
    compact = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="按方案原文解构。",
        requested_rule_codes=["IN-01"],
        batch_number=1,
        batch_total=2,
        batch_id="1/2",
        compact=True,
    )
    full = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="按方案原文解构。",
        requested_rule_codes=["IN-01"],
    )

    assert len(compact) < len(full)
    assert "wire_version='dnf-v1'" in compact
    assert "ALT或AST≥1.5×ULN" not in compact
    assert "年龄≥18岁" in compact
    assert "span-proc-screen" not in compact
    assert '"batch_id": "1/2"' in compact


def test_remote_batch_prompt_scopes_source_without_changing_full_output_contract():
    source_input, _draft, _spans = _fixture()
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="按方案原文解构。",
        requested_rule_codes=["IN-01"],
        batch_number=1,
        batch_total=2,
        scoped_source=True,
    )

    assert "wire_version='dnf-v1'" not in prompt
    assert "输出结构：" in prompt
    assert "年龄≥18岁" in prompt
    assert "ALT或AST≥1.5×ULN" not in prompt
    assert "span-proc-screen" not in prompt
    assert '"batch_rule_codes": ["IN-01"]' in prompt


def test_compact_batch_rejects_foreign_unresolved_rule_scope():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft).model_copy(
        update={
            "proposed_rules": [
                _semantic_candidate(source_input, draft).proposed_rules[0]
            ],
            "structural_warnings": [
                UnresolvedItem(
                    code="CROSS_BATCH",
                    affected_scope=["EX-01"],
                    source_refs=["span-in"],
                )
            ],
        },
        deep=True,
    )

    with pytest.raises(ValueError, match="污染了其他父规则"):
        _validate_semantic_batch(
            candidate,
            expected_codes=["IN-01"],
            expected_candidate_id=None,
            source_input=source_input,
        )


@pytest.mark.parametrize("bad_source_span", ["span-ex", "span-proc-screen"])
def test_compact_batch_rejects_cross_batch_or_ownerless_component_sources(
    bad_source_span,
):
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    rule = candidate.proposed_rules[0].model_copy(deep=True)
    rule.components[0].source_span_ids = [bad_source_span]
    candidate = candidate.model_copy(
        update={"proposed_rules": [rule]},
        deep=True,
    )

    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _validate_semantic_batch(
            candidate,
            expected_codes=["IN-01"],
            expected_candidate_id=None,
            source_input=source_input,
        )


@pytest.mark.parametrize("issue_field", ["structural_warnings", "unresolved_items"])
def test_compact_batch_rejects_warning_or_unresolved_source_refs_outside_parent_closure(
    issue_field,
):
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft).model_copy(
        update={
            "proposed_rules": [
                _semantic_candidate(source_input, draft).proposed_rules[0]
            ],
            issue_field: [
                UnresolvedItem(
                    code="OWNERLESS_SOURCE",
                    affected_scope=["IN-01"],
                    source_refs=["span-proc-screen"],
                )
            ],
        },
        deep=True,
    )

    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _validate_semantic_batch(
            candidate,
            expected_codes=["IN-01"],
            expected_candidate_id=None,
            source_input=source_input,
        )


def test_hydration_stably_disambiguates_repeated_predicate_ids():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    first_predicate = next(
        iter_atomic_predicates(candidate.proposed_rules[0].components[0].expression)
    )
    second_predicate = next(
        iter_atomic_predicates(candidate.proposed_rules[1].components[0].expression)
    )
    second_predicate.predicate_id = first_predicate.predicate_id

    hydrated = _hydrate_semantic_candidate(source_input, candidate)
    predicate_ids = [
        predicate.predicate_id
        for rule in hydrated.proposed_rules
        for component in rule.components
        for expression in (component.expression, component.exception_expression)
        if expression is not None
        for predicate in iter_atomic_predicates(expression)
    ]

    assert len(predicate_ids) == len(set(predicate_ids))
    assert predicate_ids[0] == first_predicate.predicate_id
    assert any(
        predicate_id.startswith(
            f"{first_predicate.predicate_id}:component:EX-01:01:"
        )
        for predicate_id in predicate_ids[1:]
    )


def test_hydration_neutralizes_evidence_description_that_prejudges_result():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    requirement = candidate.proposed_rules[1].components[0].evidence_requirements[0]
    requirement.fact_type = "既往病史记录"
    requirement.description = "确认参与者不存在相关既往病史"

    hydrated = _hydrate_semantic_candidate(source_input, candidate)
    actual = hydrated.proposed_rules[1].components[0].evidence_requirements[0]

    assert actual.description == "筛选期审核：核对既往病史记录"


def test_feedback_revision_replaces_only_selected_parent_rule():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "按方案原文修正后的排除条件"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="EX-01 的原文条件被理解错了，请按原文重新拆分。",
        transport=transport,
    )

    original = semantic_candidate_from_draft(draft)
    actual = semantic_candidate_from_draft(revised)
    assert actual.proposed_rules[0] == original.proposed_rules[0]
    assert actual.proposed_rules[1].components[0].title == "按方案原文修正后的排除条件"
    assert revised.draft_id == draft.draft_id
    assert transport.start_output_kinds == ["semantic_rule_repair"]
    assert "replacement_rules 必须且只能包含 EX-01" in transport.start_prompts[0]


def test_noncompact_feedback_keeps_interpretation_in_dedicated_section():
    source_input, draft, _spans = _fixture()
    source_ref = next(
        item.source_refs[0]
        for item in draft.component_drafts
        if item.parent_official_code == "EX-01"
    )
    interpretation = InterpretationSource(
        interpretation_source_id="interpretation-feedback",
        protocol_version_id=source_input.protocol_version_id,
        source_type=InterpretationSourceType.MEDICAL_INTERPRETATION,
        file_sha256="b" * 64,
        source_ref="medical-note:feedback",
        excerpt="原文未写明回溯锚点。",
        explanation="按当前审核节点日期分别核对。",
        applies_to_rule_refs=["EX-01"],
        clarifies_ambiguity=True,
        anchor_resolutions=[
            AnchorResolutionStatement(
                resolution_id="resolution-feedback",
                affected_rule_refs=["EX-01"],
                ambiguous_source_refs=[source_ref],
                target_review_stages=[ReviewStage.SCREENING, ReviewStage.BASELINE],
                resolution_mode=AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
            )
        ],
    )
    source_input = source_input.model_copy(
        update={
            "interpretation_source_ids": [interpretation.interpretation_source_id],
            "interpretation_sources": [interpretation],
        }
    )
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())]
    )

    revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="结合解释材料核对。",
        transport=transport,
    )

    frozen_input = transport.start_prompts[0].split("冻结的方案输入：", 1)[1].split(
        "\n\n输出结构：", 1
    )[0]
    payload = json.loads(frozen_input)
    assert "interpretation_sources" not in payload
    assert "interpretation_source_ids" not in payload
    assert payload["interpretation_clarifications"][0]["explanation"] == (
        "按当前审核节点日期分别核对。"
    )


def test_compact_feedback_revision_sends_only_target_rule_source_context():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    repair_payload = _wire_candidate(
        candidate.model_copy(
            update={"proposed_rules": [candidate.proposed_rules[1]]},
            deep=True,
        ),
        batch_id="repair:EX-01",
    )
    repair_payload["replacement_rules"] = repair_payload.pop("proposed_rules")
    repair_payload["replacement_structural_warnings"] = repair_payload.pop(
        "structural_warnings"
    )
    repair_payload["replacement_unresolved_items"] = repair_payload.pop(
        "unresolved_items"
    )
    repair_payload.pop("created_by_agent_call_id")
    wrong_batch_payload = json.loads(json.dumps(repair_payload))
    wrong_batch_payload["batch_id"] = "repair:IN-01"
    transport = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="feedback-session",
                text=json.dumps(wrong_batch_payload, ensure_ascii=False),
            ),
            ProtocolAgentResponse(
                session_id="feedback-session",
                text=json.dumps(repair_payload, ensure_ascii=False),
            ),
        ]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="只核对 EX-01。",
        transport=transport,
    )

    assert revised.draft_id == draft.draft_id
    assert "ALT或AST≥1.5×ULN" in transport.start_prompts[0]
    assert "年龄≥18岁" not in transport.start_prompts[0]
    assert "span-proc-screen" not in transport.start_prompts[0]
    assert "parent_rule_catalog_total" not in transport.start_prompts[0]
    assert "required_procedure_catalog_total" not in transport.start_prompts[0]
    assert len(transport.repair_prompts) == 1
    assert "batch_id 必须为 repair:EX-01" in transport.repair_prompts[0][1]


def test_feedback_replaces_only_selected_rule_unresolved_items():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft).model_copy(
        update={
            "unresolved_items": [
                UnresolvedItem(code="KEEP_IN", affected_scope=["IN-01"]),
                UnresolvedItem(code="DROP_EX", affected_scope=["EX-01"]),
            ]
        }
    )
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
        replacement_unresolved_items=[
            UnresolvedItem(code="CURRENT_EX", affected_scope=["EX-01"])
        ],
    )

    revised = _apply_semantic_repair(
        candidate,
        repair,
        expected_codes=["EX-01"],
    )

    assert [item.code for item in revised.unresolved_items] == [
        "KEEP_IN",
        "CURRENT_EX",
    ]


def test_feedback_accepts_target_component_scope_and_rejects_foreign_rule_scope():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft).model_copy(
        update={
            "unresolved_items": [
                UnresolvedItem(
                    code="OLD_COMPONENT",
                    affected_scope=["component:EX-01:07"],
                )
            ]
        }
    )
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    accepted = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
        replacement_unresolved_items=[
            UnresolvedItem(
                code="CURRENT_COMPONENT",
                affected_scope=["component:EX-01:08"],
            )
        ],
    )

    revised = _apply_semantic_repair(
        candidate,
        accepted,
        expected_codes=["EX-01"],
    )

    assert [item.code for item in revised.unresolved_items] == ["CURRENT_COMPONENT"]

    foreign = accepted.model_copy(
        update={
            "replacement_unresolved_items": [
                UnresolvedItem(
                    code="FOREIGN_COMPONENT",
                    affected_scope=["component:IN-01:01"],
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="指定父规则之外"):
        _apply_semantic_repair(candidate, foreign, expected_codes=["EX-01"])

    unscoped = accepted.model_copy(
        update={
            "replacement_unresolved_items": [
                UnresolvedItem(code="NO_OWNER", affected_scope=["component:08"])
            ]
        }
    )
    with pytest.raises(ValueError, match="指定父规则之外"):
        _apply_semantic_repair(candidate, unscoped, expected_codes=["EX-01"])


def test_feedback_namespaced_draft_id_round_trips_without_creating_new_chain():
    """正式版本反馈草稿的命名空间不得在语义水合后重复套 draft 前缀。"""

    source_input, draft, _spans = _fixture()
    draft = draft.model_copy(update={"draft_id": "draft:feedback:stable-id"})
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="核对反馈草稿身份。",
        transport=transport,
    )

    assert candidate.candidate_id == "feedback:stable-id"
    assert revised.draft_id == "draft:feedback:stable-id"


def test_feedback_revision_rejects_wrong_rule_then_repairs_in_same_session():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    wrong = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[0]],
    )
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "修正后的目标规则"
    correct = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[replacement],
    )
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="feedback-session", text=wrong.model_dump_json()),
            ProtocolAgentResponse(session_id="feedback-session", text=correct.model_dump_json()),
        ]
    )

    revised = revise_protocol_draft_from_feedback(
        source_input,
        draft,
        target_rule_code="EX-01",
        feedback_note="只核对 EX-01。",
        transport=transport,
    )

    assert semantic_candidate_from_draft(revised).proposed_rules[1].components[0].title == "修正后的目标规则"
    assert transport.repair_prompts[0][0] == "feedback-session"
    assert "指定父规则的局部修订" in transport.repair_prompts[0][1]


def test_valid_json_passes_without_repair():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="session-1", text=draft.model_dump_json())]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert len(result.attempts) == 1
    assert transport.repair_prompts == []
    assert transport.start_output_kinds == ["semantic_candidate"]
    assert "不得增加、删除、合并或调换成员" in transport.start_prompts[0]
    assert "不能拆成任一条件单独触发" in transport.start_prompts[0]
    assert "顿号、逗号和普通并列列举只表示原文术语清单" in transport.start_prompts[0]
    assert "不得自行补写‘或’" in transport.start_prompts[0]
    assert "exception_expression" in transport.start_prompts[0]
    assert "first_dose_date" in transport.start_prompts[0]
    assert "不得为表示审核阶段而复制原子条件" in transport.start_prompts[0]
    assert "不得为了‘再次确认’" in transport.start_prompts[0]
    assert "同时引用父级引导段和当前子项" in transport.start_prompts[0]


def _gate_issue(code, refs, *, level="阻止发布"):
    return ProtocolGateIssue(
        issue_code=code,
        check_name="temporal_semantics",
        level=level,
        problem="需要修正",
        impact="当前不能发布",
        next_action="核对原文",
        affected_refs=refs,
        repair_scope=refs,
    )


def test_repair_selection_rotates_to_less_repaired_parent_rules():
    _source_input, draft, _spans = _fixture()
    issues = [
        _gate_issue("IN_ISSUE", ["predicate-age"]),
        _gate_issue("EX_ISSUE", ["predicate-alt"]),
    ]

    selected = _select_repair_rule_codes(
        draft,
        issues,
        {"IN-01": 2, "EX-01": 0},
        limit=1,
    )

    assert selected == ["EX-01"]


def test_rule_repair_that_adds_blocking_issues_is_detected_as_regression():
    _source_input, draft, _spans = _fixture()
    previous = [_gate_issue("OLD", ["predicate-alt"])]
    revised = [
        _gate_issue("OLD", ["predicate-alt"]),
        _gate_issue("NEW", ["predicate-ast"]),
    ]

    assert regressing_rule_codes(
        draft,
        previous,
        draft,
        revised,
        ["EX-01"],
    ) == {"EX-01"}


def test_equal_count_issue_moved_to_another_predicate_is_regression():
    _source_input, draft, _spans = _fixture()
    previous = [_gate_issue("TIME_ANCHOR_MISSING", ["predicate-alt"])]
    revised = [_gate_issue("TIME_ANCHOR_MISSING", ["predicate-ast"])]

    assert regressing_rule_codes(
        draft,
        previous,
        draft,
        revised,
        ["EX-01"],
    ) == {"EX-01"}


def test_fewer_issues_cannot_replace_old_issues_with_new_failures():
    _source_input, draft, _spans = _fixture()
    previous = [
        _gate_issue(f"OLD-{index}", ["predicate-alt"])
        for index in range(5)
    ]
    revised = [
        _gate_issue("NEW-A", ["predicate-ast"]),
        _gate_issue("NEW-B", ["predicate-ast"]),
    ]

    assert regressing_rule_codes(
        draft,
        previous,
        draft,
        revised,
        ["EX-01"],
    ) == {"EX-01"}


def test_lean_semantic_candidate_is_hydrated_from_frozen_catalogs():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="session-1", text=candidate.model_dump_json())]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert result.final_draft is not None
    assert len(result.final_draft.parent_catalog_mappings) == 2
    assert len(result.final_draft.procedure_catalog_mappings) == 2
    assert len(result.final_draft.component_drafts) == 2
    assert {
        item.proposed_requirement.procedure_catalog_item_id
        for item in result.final_draft.evidence_requirement_drafts
        if item.procedure_catalog_item_id is not None
    } == {"procedure:screening:lab", "procedure:baseline:lab"}


def test_hydration_preserves_rule_only_stage_and_procedure_catalog_order():
    source_input, draft, _spans = _fixture()
    first, second = source_input.required_procedure_catalog.items
    first = first.model_copy(
        update={
            "review_stage": ReviewStage.RUN_IN,
            "visit_instance": "筛选/导入期 D-7~D-1",
        }
    )
    third = first.model_copy(
        update={
            "item_id": "procedure:run-in:repeat-lab",
            "position": 2,
        }
    )
    source_input.required_procedure_catalog = (
        source_input.required_procedure_catalog.model_copy(
            update={"items": [first, second, third]}
        )
    )
    candidate = _semantic_candidate(source_input, draft)

    hydrated = _parse_protocol_draft(candidate.model_dump_json(), source_input)

    assert [
        item.catalog_item_id for item in hydrated.procedure_catalog_mappings
    ] == [first.item_id, second.item_id, third.item_id]
    stages = {stage.stage: stage for stage in hydrated.proposed_workflow_stages}
    assert set(stages) == {
        ReviewStage.SCREENING,
        ReviewStage.RUN_IN,
        ReviewStage.BASELINE,
    }
    screening_requirement_ids = {
        item.proposed_requirement.requirement_id
        for item in hydrated.evidence_requirement_drafts
        if item.proposed_requirement.due_stage == ReviewStage.SCREENING
    }
    assert screening_requirement_ids <= set(
        stages[ReviewStage.SCREENING].due_requirement_ids
    )


def test_large_official_catalog_is_collected_in_ordered_same_session_batches():
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    codes = ["IN-01", "IN-02", "IN-03", "EX-01", "EX-02", "EX-03"]
    items = []
    for index, code in enumerate(codes):
        template = source_input.parent_rule_catalog.items[index % 2]
        items.append(
            template.model_copy(
                update={
                    "item_id": f"catalog:{code}",
                    "official_code": code,
                    "position": index + 1,
                }
            )
        )
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": tuple(items)}
            )
        }
    )

    def batch(rule_codes):
        rules = []
        for index, code in enumerate(rule_codes):
            rule = base_candidate.proposed_rules[index % 2].model_copy(deep=True)
            rule.official_code = code
            rules.append(rule)
        return base_candidate.model_copy(update={"proposed_rules": rules}, deep=True)

    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[:3]).model_dump_json()
            ),
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[3:]).model_dump_json()
            ),
        ]
    )

    response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        batch_size=3,
    )
    merged = _parse_semantic_candidate(response.text)

    assert error is None
    assert [rule.official_code for rule in merged.proposed_rules] == codes
    assert "必须且只能返回这些官方父规则" in transport.start_prompts[0]
    assert transport.repair_prompts[0][0] == "session-1"
    assert "第 2/2 批" in transport.repair_prompts[0][1]


def test_compact_semantic_batches_isolate_one_oversized_parent_without_splitting_it():
    source_input, _draft, _spans = _fixture()
    original_items = source_input.parent_rule_catalog.items
    materials = list(source_input.source_materials)
    long_span_id = original_items[1].source_span_ids[0]
    materials = [
        material.model_copy(
            update={"text": "中性方案原文。" * 4_000}
        )
        if material.source_span_id == long_span_id
        else material
        for material in materials
    ]
    codes = ["IN-01", "EX-01", "IN-02"]
    items = tuple(
        original_items[index % 2].model_copy(
            update={
                "item_id": f"catalog:{code}",
                "official_code": code,
                "position": index + 1,
            }
        )
        for index, code in enumerate(codes)
    )
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": items}
            ),
            "source_materials": tuple(materials),
        }
    )

    batches = _plan_semantic_rule_batches(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        batch_size=3,
        compact=True,
    )

    assert batches == [["IN-01"], ["EX-01"], ["IN-02"]]
    assert [code for batch in batches for code in batch] == codes

    remote_batches = _plan_semantic_rule_batches(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        batch_size=3,
        compact=False,
    )

    assert remote_batches == [["IN-01"], ["EX-01"], ["IN-02"]]


def test_compact_batch_with_missing_rule_is_not_silently_merged():
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    original_items = source_input.parent_rule_catalog.items
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={
                    "items": (
                        original_items[0],
                        original_items[1],
                        original_items[0].model_copy(
                            update={
                                "item_id": "catalog:in02",
                                "official_code": "IN-02",
                                "position": 2,
                            }
                        ),
                    )
                }
            )
        }
    )
    missing_rule = base_candidate.model_copy(
        update={"proposed_rules": [base_candidate.proposed_rules[0]]},
        deep=True,
    )
    missing_payload = json.dumps(
        _wire_candidate(missing_rule, batch_id="1/2"),
        ensure_ascii=False,
    )
    transport = CompactFakeTransport(
        [
            ProtocolAgentResponse(session_id="compact-session", text=missing_payload),
            ProtocolAgentResponse(session_id="compact-session", text=missing_payload),
        ]
    )

    response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        batch_size=2,
    )

    assert response.session_id == "compact-session"
    assert error is not None
    assert "第 1/2 批" in error
    assert "本批官方父规则" in error
    assert "['IN-01', 'EX-01']" in transport.repair_prompts[0][1]


def test_merge_rejects_mismatched_logical_call_provenance():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    first = candidate.model_copy(
        update={
            "proposed_rules": [candidate.proposed_rules[0]],
            "created_by_agent_call_id": "call-1",
        },
        deep=True,
    )
    second = candidate.model_copy(
        update={
            "proposed_rules": [candidate.proposed_rules[1]],
            "created_by_agent_call_id": "call-2",
        },
        deep=True,
    )

    with pytest.raises(ValueError, match="不得更换 created_by_agent_call_id"):
        _merge_semantic_batches([first, second], expected_codes=["IN-01", "EX-01"])


def test_final_merge_rejects_cross_batch_source_provenance():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    first = candidate.model_copy(
        update={"proposed_rules": [candidate.proposed_rules[0]]},
        deep=True,
    )
    second_rule = candidate.proposed_rules[1].model_copy(deep=True)
    second_rule.components[0].source_span_ids = ["span-in"]
    second = candidate.model_copy(
        update={"proposed_rules": [second_rule]},
        deep=True,
    )

    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _merge_semantic_batches(
            [first, second],
            expected_codes=["IN-01", "EX-01"],
            source_input=source_input,
        )


def test_repair_validation_requires_canonical_expected_batch_id():
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )

    with pytest.raises(ValueError, match="规范身份"):
        _validate_semantic_repair(
            repair,
            expected_codes=["EX-01"],
            expected_candidate_id=candidate.candidate_id,
            expected_batch_id="repair:IN-01",
            source_input=source_input,
        )


def test_compact_batches_close_exactly_and_drop_previous_batch_source_material():
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    codes = ["IN-01", "EX-01", "IN-02", "EX-02"]
    items = []
    for index, code in enumerate(codes):
        template = source_input.parent_rule_catalog.items[index % 2]
        items.append(
            template.model_copy(
                update={
                    "item_id": f"catalog:{code}",
                    "official_code": code,
                    "position": index + 1,
                }
            )
        )
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": tuple(items)}
            )
        }
    )

    def wire_batch(rule_codes, batch_id):
        rules = []
        for code in rule_codes:
            source_rule = (
                base_candidate.proposed_rules[0]
                if code.startswith("IN-")
                else base_candidate.proposed_rules[1]
            )
            rules.append(source_rule.model_copy(update={"official_code": code}))
        candidate = base_candidate.model_copy(
            update={"proposed_rules": rules},
            deep=True,
        )
        return json.dumps(
            _wire_candidate(candidate, batch_id=batch_id),
            ensure_ascii=False,
        )

    transport = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="compact-session",
                text=wire_batch(codes[:3], "1/2"),
            ),
            ProtocolAgentResponse(
                session_id="compact-session",
                text=wire_batch(codes[3:], "2/2"),
            ),
        ]
    )

    response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        batch_size=3,
    )
    merged = _parse_semantic_candidate(response.text)

    assert error is None
    assert [rule.official_code for rule in merged.proposed_rules] == codes
    assert len(transport.compact_contexts) == 1
    assert len(transport.request_histories[1]) == 3
    assert transport.request_histories[1][0]["content"] == (
        "已完成方案解构批次 1/2；candidate_id='candidate-1'。"
        "只保留冻结上下文和下一批明确身份，不要复述上一批原文或输出。"
    )
    assert "年龄≥18岁" not in transport.request_histories[1][0]["content"]
    next_prompt = transport.repair_prompts[0][1]
    assert "第 2/2 批" in next_prompt
    assert "ALT或AST≥1.5×ULN" in next_prompt
    assert "年龄≥18岁" not in next_prompt
    assert [scope["official_codes"] for scope in transport.output_scopes] == [
        ("IN-01", "EX-01", "IN-02"),
        ("EX-02",),
    ]
    assert set(transport.output_scopes[1]["allowed_source_span_ids"]) == {
        span_id
        for item in expanded_input.parent_rule_catalog.items
        if item.official_code == "EX-02"
        for span_id in item.source_span_ids
    }


def test_compact_semantic_batches_resume_after_completed_batch_without_repeating_it():
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    codes = ["IN-01", "EX-01", "IN-02", "EX-02"]
    items = tuple(
        source_input.parent_rule_catalog.items[index % 2].model_copy(
            update={
                "item_id": f"catalog:{code}",
                "official_code": code,
                "position": index + 1,
            }
        )
        for index, code in enumerate(codes)
    )
    expanded_input = source_input.model_copy(
        update={
            "parent_rule_catalog": source_input.parent_rule_catalog.model_copy(
                update={"items": items}
            )
        }
    )

    def wire_batch(rule_codes, batch_id):
        rules = [
            (
                base_candidate.proposed_rules[0]
                if code.startswith("IN-")
                else base_candidate.proposed_rules[1]
            ).model_copy(update={"official_code": code}, deep=True)
            for code in rule_codes
        ]
        return json.dumps(
            _wire_candidate(
                base_candidate.model_copy(
                    update={"proposed_rules": rules},
                    deep=True,
                ),
                batch_id=batch_id,
            ),
            ensure_ascii=False,
        )

    cache = MemoryBatchCache()
    interrupted = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="first-session",
                text=wire_batch(codes[:3], "1/2"),
            )
        ]
    )
    _response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=interrupted,
        batch_size=3,
        batch_cache=cache,
    )

    assert error is not None
    assert "第 2/2 批调用未完成" in error
    assert len(cache.items) == 1

    resumed = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="resumed-session",
                text=wire_batch(codes[3:], "2/2"),
            )
        ]
    )
    response, error = _collect_initial_semantic_response(
        expanded_input,
        prompt_template="按正式方案原文进行结构化解构。",
        transport=resumed,
        batch_size=3,
        batch_cache=cache,
    )
    merged = _parse_semantic_candidate(response.text)

    assert error is None
    assert [rule.official_code for rule in merged.proposed_rules] == codes
    assert len(resumed.start_prompts) == 1
    assert "第 2/2 批" in resumed.start_prompts[0]
    assert "年龄≥18岁" not in resumed.start_prompts[0]
    assert len(cache.items) == 2


def test_invalid_output_is_repaired_in_same_session():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="不是 JSON"),
            ProtocolAgentResponse(
                session_id="session-1", text=draft.model_dump_json()
            ),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "输出格式无效",
        "通过完整性检查",
    ]
    assert transport.repair_prompts[0][0] == "session-1"
    assert "前一响应从未成功解析为完整草稿" in transport.repair_prompts[0][1]
    assert "严禁输出空列表" in transport.repair_prompts[0][1]


def test_valid_candidate_repairs_only_affected_parent_rule():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            ProtocolAgentResponse(session_id="session-1", text=repair.model_dump_json()),
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "需要定向修正",
        "通过完整性检查",
    ]
    assert transport.start_output_kinds == ["semantic_candidate"]
    assert transport.repair_output_kinds == ["semantic_rule_repair"]
    assert "['EX-01']" in transport.repair_prompts[0][1]
    assert "不要返回整份草稿" in transport.repair_prompts[0][1]
    assert result.final_draft is not None
    assert (
        result.final_draft.proposed_rules[0].components[0].expression
        == candidate.proposed_rules[0].components[0].expression
    )


def test_checkpoint_candidate_starts_targeted_repair_session(monkeypatch):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.candidate_id = "parent-segment-candidate:test"
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    repair = ProtocolSemanticRuleRepair(
        candidate_id="model-invented-candidate-id",
        replacement_rules=[candidate.proposed_rules[1]],
    )
    monkeypatch.setattr(
        "app.agents.protocol_deconstructor._collect_initial_semantic_response",
        lambda *_args, **_kwargs: (
            ProtocolAgentResponse(
                session_id="protocol-parent-segments-checkpoint",
                text=bad_candidate.model_dump_json(),
            ),
            None,
        ),
    )
    transport = FakeTransport(
        [ProtocolAgentResponse(session_id="repair-session", text=repair.model_dump_json())]
    )
    template = "按正式方案原文进行结构化解构。"

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert transport.start_output_kinds == ["semantic_rule_repair"]
    assert transport.repair_output_kinds == []
    assert result.same_session_id == "repair-session"


def test_compact_wire_candidate_and_local_repair_keep_domain_gate_path():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    repair_payload = _wire_candidate(
        candidate.model_copy(update={"proposed_rules": [candidate.proposed_rules[1]]}, deep=True),
        batch_id="repair:EX-01",
    )
    repair_payload["replacement_rules"] = repair_payload.pop("proposed_rules")
    repair_payload["replacement_structural_warnings"] = repair_payload.pop(
        "structural_warnings"
    )
    repair_payload["replacement_unresolved_items"] = repair_payload.pop(
        "unresolved_items"
    )
    repair_payload.pop("created_by_agent_call_id")
    wrong_repair_payload = json.loads(json.dumps(repair_payload))
    wrong_repair_payload["batch_id"] = "repair:IN-01"
    transport = CompactFakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1",
                text=json.dumps(_wire_candidate(bad_candidate), ensure_ascii=False),
            ),
            ProtocolAgentResponse(
                session_id="session-1",
                text=json.dumps(wrong_repair_payload, ensure_ascii=False),
            ),
            ProtocolAgentResponse(
                session_id="session-1",
                text=json.dumps(repair_payload, ensure_ascii=False),
            ),
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version("按正式方案原文进行结构化解构。"),
        prompt_template="按正式方案原文进行结构化解构。",
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert transport.start_output_kinds == ["semantic_candidate"]
    assert transport.repair_output_kinds == [
        "semantic_rule_repair",
        "semantic_rule_repair",
    ]
    assert "batch_id 必须为 repair:EX-01" in transport.repair_prompts[0][1]
    assert transport.compact_contexts


def test_empty_schema_defs_and_singleton_identity_logic_are_normalized():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    payload["$defs"] = {}
    original = payload["proposed_rules"][0]["components"][0]["expression"]
    payload["proposed_rules"][0]["components"][0]["expression"] = {
        "kind": "logical",
        "operator": "all",
        "children": [original],
    }

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert parsed.proposed_rules[0].components[0].expression.kind == "predicate"


def test_shared_time_prefix_is_split_only_into_unique_exact_fragments():
    source = (
        "随机前12周（大分子药物）/4周（小分子药物）或5个药物半衰期"
        "（以较长时间为准）内参加过其他药物临床试验且使用过研究药物"
    )
    assert _recover_exact_fragments(
        "随机前4周（小分子药物）", [source]
    ) == ["随机前", "4周（小分子药物）"]


def test_nonempty_schema_definition_is_not_silently_discarded():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    payload["$defs"] = {"unexpected": {"type": "object"}}

    with pytest.raises(Exception, match="Extra inputs"):
        _parse_protocol_draft(__import__("json").dumps(payload))


def test_unambiguous_nested_exception_is_moved_to_component_level():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    component = payload["proposed_rules"][0]["components"][0]
    component["expression"]["exception_expression"] = component["expression"].copy()

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert parsed.proposed_rules[0].components[0].exception_expression is not None


def test_missing_numeric_unit_survives_as_gate_repair_marker():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    predicate = payload["proposed_rules"][0]["components"][0]["expression"][
        "predicate"
    ]
    predicate.pop("unit")

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))

    assert (
        parsed.proposed_rules[0].components[0].expression.predicate.unit
        == "__missing_from_agent__"
    )


def test_duplicate_single_source_clause_is_removed_when_list_contains_it():
    _source_input, draft, _spans = _fixture()
    payload = draft.model_dump(mode="json")
    predicate = payload["proposed_rules"][0]["components"][0]["expression"][
        "predicate"
    ]
    predicate["source_clause"] = "年龄≥18岁"
    predicate["source_clauses"] = ["年龄≥18岁", "包括边界值"]

    parsed = _parse_protocol_draft(__import__("json").dumps(payload))
    parsed_predicate = parsed.proposed_rules[0].components[0].expression.predicate

    assert parsed_predicate.source_clause is None
    assert parsed_predicate.source_clauses == ["年龄≥18岁", "包括边界值"]


def test_only_two_targeted_repairs_are_allowed():
    source_input, _draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="无效一"),
            ProtocolAgentResponse(session_id="session-1", text="无效二"),
            ProtocolAgentResponse(session_id="session-1", text="无效三"),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert len(result.attempts) == 3
    assert len(transport.repair_prompts) == 2


def test_semantic_repairs_have_separate_bounded_budget():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    bad_repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[bad_candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            *[
                ProtocolAgentResponse(
                    session_id="session-1", text=bad_repair.model_dump_json()
                )
                for _ in range(16)
            ],
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 17
    assert len(transport.repair_prompts) == 16
    assert all("['EX-01']" in prompt for _, prompt in transport.repair_prompts)


def test_invalid_local_repair_gets_one_schema_retry_without_empty_issue_list():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    good_repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            ProtocolAgentResponse(
                session_id="session-1",
                text=(
                    '{"candidate_id":"candidate-1",'
                    '"final_output":"repair"}'
                ),
            ),
            ProtocolAgentResponse(
                session_id="session-1", text=good_repair.model_dump_json()
            ),
        ]
    )

    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )

    assert result.status == "可以进入审阅"
    assert [item.outcome for item in result.attempts] == [
        "需要定向修正",
        "输出格式无效",
        "通过完整性检查",
    ]
    assert "AGENT_OUTPUT_SCHEMA_INVALID" in transport.repair_prompts[1][1]
    assert "重新输出完整 JSON 对象，不要附加说明：[]" not in (
        transport.repair_prompts[1][1]
    )


def test_repair_cannot_silently_switch_session():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(session_id="session-1", text="无效"),
            ProtocolAgentResponse(
                session_id="session-2", text=draft.model_dump_json()
            ),
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert result.attempts[-1].outcome == "会话异常"
    assert result.same_session_id == "session-1"


def test_initial_transport_failure_returns_auditable_review_result():
    source_input, _draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=FailingStartTransport(),
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert result.attempts[0].outcome == "会话异常"
    assert "上游连续返回空正文" in result.attempts[0].issues[0].problem


def test_repair_transport_failure_preserves_prior_draft_and_stops_cleanly():
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    template = "按正式方案原文进行结构化解构。"
    transport = FailingRepairTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            )
        ]
    )
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=transport,
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert [attempt.outcome for attempt in result.attempts] == [
        "需要定向修正",
        "会话异常",
    ]
    assert result.same_session_id == "session-1"
    assert result.final_draft is not None
    assert result.final_gate_result is not None
    assert result.final_draft.draft_id == result.attempts[0].draft_id
    assert result.final_gate_result.publishable is False


def test_audit_history_accepts_dynamic_parent_rule_repair_budget():
    attempts = [
        ProtocolDeconstructionAttempt(
            attempt=index,
            session_id="session-large-protocol",
            raw_output_sha256="a" * 64,
            outcome="需要定向修正",
        )
        for index in range(1, 37)
    ]

    result = ProtocolDeconstructionRunResult(
        status="需要核对",
        same_session_id="session-large-protocol",
        attempts=attempts,
    )

    assert len(result.attempts) == 36
    assert result.attempts[-1].attempt == 36
