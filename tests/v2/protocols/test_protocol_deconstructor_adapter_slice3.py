from __future__ import annotations

import json
import hashlib
from itertools import product
from types import SimpleNamespace

import pytest

from app.agents.protocol_deconstructor import (
    DNF_WIRE_VERSION,
    ProtocolDeconstructionAttempt,
    ProtocolDeconstructionRunResult,
    ProtocolAgentResponse,
    ProtocolAgentCallError,
    ProtocolRequirementIdentityError,
    ProtocolWireError,
    ProtocolDeconstructorRunner,
    _parse_semantic_candidate,
    _plan_semantic_rule_batches,
    _merge_semantic_batches,
    _merge_component_only_repair,
    _repair_batch_id,
    _repair_prompt,
    _validate_semantic_batch,
    _validate_semantic_repair,
    _collect_initial_semantic_response,
    _apply_semantic_repair,
    _affected_rule_codes,
    _repair_issues_for_rules,
    _hydrate_semantic_candidate,
    _parse_protocol_draft,
    _recover_exact_fragments,
    _wire_atom,
    _wire_dnf_expression,
    _wire_time_constraint,
    _wire_time_quantity,
    build_protocol_deconstruction_prompt,
    regressing_rule_codes,
    _select_repair_rule_codes,
    _repair_stagnation_signature,
    _restore_candidate_rules,
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
    SemanticRestrictedComponent,
    SemanticRule,
    SemanticRuleComponent,
)
from app.domain.contracts.enums import (
    AgentNode,
    AnchorResolutionMode,
    CatalogKind,
    InterpretationSourceType,
    LogicalOperator,
    ReviewStage,
)
from app.domain.contracts.normalization import UnresolvedItem
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationSource,
)
from app.domain.contracts.rules import RestrictedRuleComponent, RepeatTriggerCondition, iter_atomic_predicates
from app.domain.contracts.repeat_scheme import RepeatScheme
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate, ProtocolGateIssue
from tests.v2.protocols.test_deconstruction_gate_slice3 import _catalog, _fixture


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


@pytest.fixture
def whole_draft_fixture_budget(monkeypatch):
    # These replay fixtures return both parents in one answer. Adaptive packing
    # is exercised separately with its production limit, not by these fixtures.
    monkeypatch.setattr("app.agents.protocol_deconstructor.SEMANTIC_BATCH_MAX_INPUT_TOKENS", 1_000_000)


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
        predicate.setdefault("semantic_proposition", None)
        predicate.setdefault("repeat_scheme", None)
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
        rules.append({"official_code": rule.official_code, "components": components,
                      "restricted_components": [item.model_dump(mode="json")
                                                for item in rule.restricted_components]})
    return {
        "wire_version": DNF_WIRE_VERSION,
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
            "semantic_proposition": None,
            "observation_policy": {
                "mode": "unresolved", "scope": "既往病史",
                "source_span_ids": ["history-source"],
                "source_excerpts": ["既往病史"],
            },
            "repeat_scheme": None,
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


def test_wire_accepts_explicit_null_observation_policy_without_inventing_selection():
    from jsonschema import validate
    from app.agents.protocol_deconstructor import _wire_observation_policy_schema

    validate(None, _wire_observation_policy_schema())
    predicate = _wire_atom(
        {
            "subject": "参与者",
            "attribute": "既往手术史",
            "source_locator": {"source_clause": "既往手术史"},
            "semantic_proposition": None,
            "observation_policy": None,
            "repeat_scheme": None,
            "requires_professional_judgment": False,
            "negated": False,
        },
        shape="existence",
    )
    assert predicate["observation_policy"] is None


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
                "semantic_proposition": None,
                "observation_policy": {
                    "mode": "unresolved", "scope": "病史",
                    "source_span_ids": ["history-source"],
                    "source_excerpts": ["病史"],
                },
                "repeat_scheme": None,
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
                "semantic_proposition": None,
                "observation_policy": {
                    "mode": "unresolved", "scope": "计划",
                    "source_span_ids": ["plan-source"],
                    "source_excerpts": ["计划"],
                },
                "repeat_scheme": None,
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
        "attribute": "ALT或AST",
        "source_locator": {"source_clause": "ALT或AST≥1.5×ULN"},
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
    assert by_attribute_and_comparator[("ALT或AST", "exists")].value is None
    assert by_attribute_and_comparator[("ALT或AST", "exists")].predicate_id != (
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
    assert f"wire_version={DNF_WIRE_VERSION!r}" in compact
    assert "ALT或AST≥1.5×ULN" not in compact
    assert "年龄≥18岁" in compact
    payload, _ = json.JSONDecoder().raw_decode(compact.split("输入：", 1)[1])
    assert payload["required_procedure_catalog"] == [
        item.model_dump(mode="json")
        for item in sorted(source_input.required_procedure_catalog.items, key=lambda item: item.position)
    ]
    assert payload["allowed_source_span_ids"] == ["span-in"]
    assert [item["source_span_id"] for item in payload["source_materials"]] == ["span-in"]
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

    assert f"wire_version={DNF_WIRE_VERSION!r}" not in prompt
    assert "输出结构：" in prompt
    assert "年龄≥18岁" in prompt
    assert "ALT或AST≥1.5×ULN" not in prompt
    payload, _ = json.JSONDecoder().raw_decode(prompt.split("输入：", 1)[1])
    assert payload["required_procedure_catalog"] == [
        item.model_dump(mode="json")
        for item in sorted(source_input.required_procedure_catalog.items, key=lambda item: item.position)
    ]
    assert payload["allowed_source_span_ids"] == ["span-in"]
    assert [item["source_span_id"] for item in payload["source_materials"]] == ["span-in"]
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


@pytest.mark.parametrize("compact", [False, True])
def test_initial_prompt_allows_exact_branch_objects_without_requiring_every_term(compact):
    source_input, _draft, _spans = _fixture()
    prompt = build_protocol_deconstruction_prompt(
        source_input, prompt_template="按完整来源理解条件。", compact=compact,
    )
    assert "非数值谓词的 source_term 可省略" in prompt
    assert "逐字填写该分支对象名称" in prompt
    assert "不能为取得不同定位而删除共同限定" in prompt
    assert "非数值谓词省略 source_term" not in prompt


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
    assert "每项 affected_scope 必须明确包含 EX-01" in transport.start_prompts[0]
    assert "可以仅把本子项谓词的来源片段缩窄" in transport.start_prompts[0]
    assert "不能通过截掉本子项真正适用的限定词" in transport.start_prompts[0]
    assert "非数值谓词也可用 source_term" in transport.start_prompts[0]
    assert "定位修订不授权改变 ALL/ANY/NOT" in transport.start_prompts[0]


def test_feedback_prospective_guidance_survives_format_recovery_without_changing_initial_identity():
    import app.agents.protocol_deconstructor as author
    source, draft, _spans = _fixture()
    initial_identity = protocol_prompt_template_sha256("fixture")
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]])
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="future-repair", text="{}"),
        ProtocolAgentResponse(session_id="future-repair", text=repair.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(source, draft, target_rule_code="EX-01",
        feedback_note="核对本子项遗漏的原文未来范围，其余内容不改。", transport=transport,
        preserve_review_items=True)
    for prompt in (transport.start_prompts[0], transport.repair_prompts[0][1]):
        assert author._PROSPECTIVE_FEEDBACK_CONTRACT in prompt
        assert "当前同意或计划仍是当前声明" in prompt
        assert "未指明首次或末次时用 study_drug_administration_date" in prompt
        assert "不因出现两个时间字段机械改成且或或" in prompt
    assert author._PROSPECTIVE_FEEDBACK_CONTRACT not in author._SYSTEM_CONTRACT
    assert author._PROSPECTIVE_FEEDBACK_CONTRACT not in author._COMPACT_WIRE_COMPONENT_CONTRACT
    assert protocol_prompt_template_sha256("fixture") == initial_identity
    assert semantic_candidate_from_draft(revised) == candidate
    assert transport.repair_output_kinds == ["semantic_rule_repair"]


@pytest.mark.parametrize("preserve_review_items", [False, True])
@pytest.mark.parametrize("component_only", [False, True])
@pytest.mark.parametrize("joint_source_repair", [False, True])
def test_feedback_review_item_permissions_are_separate_from_rule_revision(
    preserve_review_items, component_only, joint_source_repair,
):
    source_input, draft, _spans = _fixture()
    original = UnresolvedItem(code="DEPENDENCY_UNREAD", affected_scope=["EX-01"])
    warning = UnresolvedItem(code="SOURCE_UNCERTAIN", affected_scope=["EX-01"])
    other = UnresolvedItem(code="OTHER_UNREAD", affected_scope=["IN-01"])
    shared = UnresolvedItem(code="SHARED_UNREAD", affected_scope=["IN-01", "EX-01"])
    draft.unresolved_items = [other, original, shared]
    draft.structural_warnings = [warning]
    candidate = semantic_candidate_from_draft(draft)
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "仅修订条款描述"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[replacement],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="bounded-feedback", text=repair.model_dump_json())
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", feedback_note="只改描述，不解除来源疑问。",
        transport=transport, preserve_review_items=preserve_review_items,
        target_component_id=(draft.proposed_rules[1].components[0].rule_component_id if component_only else None),
        joint_source_repair=joint_source_repair,
    )
    assert revised.proposed_rules[1].components[0].title == "仅修订条款描述"
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert revised.unresolved_items == ([other, original, shared] if preserve_review_items else [other, shared])
    assert revised.structural_warnings == ([warning] if preserve_review_items else [])
    assert draft.unresolved_items == [other, original, shared]
    if preserve_review_items:
        assert "程序原样保留全部已有事项" in transport.start_prompts[0]


def test_feedback_readonly_review_items_survive_structural_recovery():
    source_input, draft, _spans = _fixture()
    original = UnresolvedItem(code="DEPENDENCY_UNREAD", affected_scope=["EX-01"])
    draft.unresolved_items = [original]
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[candidate.proposed_rules[1]],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="bounded-feedback", text="{}"),
        ProtocolAgentResponse(session_id="bounded-feedback", text=repair.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", feedback_note="只改描述。",
        transport=transport, preserve_review_items=True,
    )
    assert revised.unresolved_items == [original]
    assert len(transport.repair_prompts) == 1
    assert "本次待核事项只读" in transport.repair_prompts[0][1]


@pytest.mark.parametrize("replacement_field", ["replacement_unresolved_items", "replacement_structural_warnings"])
def test_feedback_readonly_review_items_reject_replacement_items(replacement_field):
    source_input, draft, _spans = _fixture()
    original = UnresolvedItem(code="DEPENDENCY_UNREAD", affected_scope=["EX-01"])
    draft.unresolved_items = [original]
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[candidate.proposed_rules[1]],
        **{replacement_field: [UnresolvedItem(code="REPLACEMENT", affected_scope=["EX-01"])]},
    )
    response = ProtocolAgentResponse(session_id="bounded-feedback", text=repair.model_dump_json())
    transport = FakeTransport([response, response])
    with pytest.raises(ProtocolAgentCallError, match="无待核事项处置权限"):
        revise_protocol_draft_from_feedback(
            source_input, draft, target_rule_code="EX-01", feedback_note="只改描述。",
            transport=transport, preserve_review_items=True,
        )
    assert draft.unresolved_items == [original]
    assert len(transport.repair_prompts) == 1


def test_feedback_keeps_unselected_draft_structure_byte_equivalent():
    source_input, draft, _spans = _fixture()
    untouched = draft.proposed_rules[0].components[0]
    untouched.display_code = "IN-01-original"
    draft.component_drafts[0].proposed_component = untouched
    candidate = semantic_candidate_from_draft(draft)
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "仅修订目标规则"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[replacement],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())
    ])

    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        feedback_note="仅修订本条来源含义。", transport=transport,
    )
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert revised.component_drafts[0] == draft.component_drafts[0]
    original_stages = {stage.workflow_stage_id: stage for stage in draft.proposed_workflow_stages}
    revised_stages = {stage.workflow_stage_id: stage for stage in revised.proposed_workflow_stages}
    for stage_id, stage in original_stages.items():
        assert stage_id in revised_stages
        assert [
            rid for rid in revised_stages[stage_id].due_requirement_ids
            if rid != "req-ex" and not rid.startswith("requirement:component:EX-01:")
        ] == [rid for rid in stage.due_requirement_ids if rid != "req-ex"]
    for stage_id, stage in revised_stages.items():
        if stage_id not in original_stages:
            assert all(
                rid.startswith("requirement:component:EX-01:")
                for rid in stage.due_requirement_ids
            )
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01",
    )
    assert revised.proposed_rules[1].components[0].title == "仅修订目标规则"


def test_component_feedback_removes_one_requirement_without_orphaning_workflow():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    component = candidate.proposed_rules[1].components[0]
    extra = component.evidence_requirements[0].model_copy(deep=True)
    extra.due_stage = ReviewStage.BASELINE
    extra.description = "隔离夹具中的误添节点要求"
    component.evidence_requirements.append(extra)
    draft = _hydrate_semantic_candidate(source_input, candidate)
    before = draft.model_dump(mode="json")
    target = draft.proposed_rules[1].components[0]
    removed_id = target.evidence_requirements[-1].requirement_id
    retained_id = target.evidence_requirements[0].requirement_id
    assert any(removed_id in stage.due_requirement_ids for stage in draft.proposed_workflow_stages)
    selected = semantic_candidate_from_draft(draft).proposed_rules[1].components[0]
    selected.evidence_requirements.pop()
    repair = ProtocolSemanticRuleRepair(
        candidate_id=semantic_candidate_from_draft(draft).candidate_id,
        replacement_rules=[SemanticRule(official_code="EX-01", components=[selected])],
    )
    transport = FakeTransport([ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=target.rule_component_id,
        feedback_note=f"仅核对误添的资料要求 {removed_id}；来源不支持时删除，其他字段不改。",
        transport=transport,
    )
    actual = revised.proposed_rules[1].components[0]
    assert actual.expression == target.expression
    assert actual.evidence_requirements == target.evidence_requirements[:-1]
    assert actual.evidence_requirements[0].requirement_id == retained_id
    assert all(removed_id not in stage.due_requirement_ids for stage in revised.proposed_workflow_stages)
    assert all(item.proposed_requirement.requirement_id != removed_id
               for item in revised.evidence_requirement_drafts)
    assert sum(retained_id in stage.due_requirement_ids for stage in revised.proposed_workflow_stages) == 1
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert revised.component_drafts[0] == draft.component_drafts[0]
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(draft, revised, target_rule_code="EX-01")
    assert draft.model_dump(mode="json") == before


@pytest.mark.parametrize("removed_index", [0, 1, 2])
@pytest.mark.parametrize("legacy_draft_ids", [False, True])
def test_component_requirement_deletion_retains_each_surviving_identity(removed_index, legacy_draft_ids):
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    component = candidate.proposed_rules[1].components[0]
    original_requirement = component.evidence_requirements[0]
    component.evidence_requirements = [
        original_requirement.model_copy(update={
            "description": f"核对来源明确的第{index + 1}项资料",
            "due_stage": stage,
        }, deep=True)
        for index, stage in enumerate((ReviewStage.SCREENING, ReviewStage.BASELINE, ReviewStage.SCREENING))
    ]
    draft = _hydrate_semantic_candidate(source_input, candidate)
    if legacy_draft_ids:
        draft.component_drafts[1].draft_component_id = "legacy-component-draft"
        for item in draft.evidence_requirement_drafts:
            if item.proposed_requirement.rule_component_id == draft.proposed_rules[1].components[0].rule_component_id:
                item.draft_component_id = "legacy-component-draft"
                item.draft_requirement_id = "legacy-" + item.proposed_requirement.requirement_id
    before = draft.model_dump(mode="json")
    target = draft.proposed_rules[1].components[0]
    expected = [item for index, item in enumerate(target.evidence_requirements) if index != removed_index]
    removed_id = target.evidence_requirements[removed_index].requirement_id
    selected = semantic_candidate_from_draft(draft).proposed_rules[1].components[0]
    selected.evidence_requirements.pop(removed_index)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(official_code="EX-01", components=[selected])],
    )
    transport = FakeTransport([ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", target_component_id=target.rule_component_id,
        feedback_note="仅删除有源核对后确认多添的指定资料要求，剩余内容不改。", transport=transport,
    )
    actual = revised.proposed_rules[1].components[0]
    assert actual.evidence_requirements == expected
    assert actual.expression == target.expression
    assert all(removed_id not in stage.due_requirement_ids for stage in revised.proposed_workflow_stages)
    mapped = {item.proposed_requirement.requirement_id: item for item in revised.evidence_requirement_drafts}
    original_mapped = {item.proposed_requirement.requirement_id: item for item in draft.evidence_requirement_drafts}
    for requirement in expected:
        assert mapped[requirement.requirement_id].proposed_requirement == requirement
        assert mapped[requirement.requirement_id].draft_requirement_id == original_mapped[requirement.requirement_id].draft_requirement_id
        assert mapped[requirement.requirement_id].draft_component_id == original_mapped[requirement.requirement_id].draft_component_id
        old_stage = next(stage.workflow_stage_id for stage in draft.proposed_workflow_stages
                         if requirement.requirement_id in stage.due_requirement_ids)
        new_stage = next(stage.workflow_stage_id for stage in revised.proposed_workflow_stages
                         if requirement.requirement_id in stage.due_requirement_ids)
        assert old_stage == new_stage
    assert revised.component_drafts[1].proposed_component == actual
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(draft, revised, target_rule_code="EX-01")
    assert not transport.repair_prompts
    assert draft.model_dump(mode="json") == before


def test_parent_feedback_does_not_assume_positional_component_correspondence(monkeypatch):
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    component = candidate.proposed_rules[1].components[0]
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(deep=True))
    draft = _hydrate_semantic_candidate(source_input, candidate)
    selected = semantic_candidate_from_draft(draft).proposed_rules[1].model_copy(deep=True)
    selected.components[0].evidence_requirements.pop()
    repair = ProtocolSemanticRuleRepair(candidate_id=candidate.candidate_id, replacement_rules=[selected])
    transport = FakeTransport([ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())])
    def forbidden_match(*_args):
        raise AssertionError("整父修订没有宿主固定的子项对应关系，不能进入删减身份核对")
    monkeypatch.setattr("app.agents.protocol_deconstructor._preserve_deleted_requirement_identities", forbidden_match)
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", feedback_note="整父范围修订的旧路径，仅核不误称子项身份已经对应。",
        transport=transport,
    )
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert not transport.repair_prompts


@pytest.mark.parametrize("ambiguous_duplicate", [False, True])
def test_requirement_deletion_with_unproven_identity_is_not_a_format_retry(ambiguous_duplicate):
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    component = candidate.proposed_rules[1].components[0]
    component.evidence_requirements.append(component.evidence_requirements[0].model_copy(deep=True))
    if not ambiguous_duplicate:
        component.evidence_requirements[1].description = "第二项不同资料要求"
    draft = _hydrate_semantic_candidate(source_input, candidate)
    before = draft.model_dump(mode="json")
    target = draft.proposed_rules[1].components[0]
    selected = semantic_candidate_from_draft(draft).proposed_rules[1].components[0]
    selected.evidence_requirements.pop()
    if not ambiguous_duplicate:
        selected.evidence_requirements[0].due_stage = ReviewStage.BASELINE
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(official_code="EX-01", components=[selected])],
    )
    transport = FakeTransport([ProtocolAgentResponse(session_id="feedback-session", text=repair.model_dump_json())])
    with pytest.raises(ProtocolRequirementIdentityError) as failure:
        revise_protocol_draft_from_feedback(
            source_input, draft, target_rule_code="EX-01", target_component_id=target.rule_component_id,
            feedback_note="删除一个指定要求，不能借删除重写剩余要求。", transport=transport,
        )
    assert failure.value.error_code == "REQUIREMENT_IDENTITY_AMBIGUOUS"
    assert failure.value.component_id == target.rule_component_id
    assert failure.value.affected_requirement_ids == tuple(item.requirement_id for item in target.evidence_requirements)
    assert not transport.repair_prompts
    assert draft.model_dump(mode="json") == before


def test_component_feedback_returns_one_component_and_preserves_siblings():
    source_input, draft, _spans = _fixture()
    original = semantic_candidate_from_draft(draft).proposed_rules[1]
    sibling = original.components[0].model_copy(deep=True)
    selected = original.components[0].model_copy(deep=True)
    selected.title = "仅修改选中的子项"
    parent = SemanticRule(
        official_code="EX-01", components=[sibling, original.components[0]],
    )
    single = ProtocolSemanticRuleRepair(
        candidate_id="candidate-1",
        replacement_rules=[SemanticRule(official_code="EX-01", components=[selected])],
    )
    merged = _merge_component_only_repair(single, parent, 1, "component-ex-second")
    assert merged.replacement_rules[0].components[0] == sibling
    assert merged.replacement_rules[0].components[1].title == "仅修改选中的子项"
    split = _merge_component_only_repair(
        single.model_copy(update={"replacement_rules": [parent]}),
        parent, 1, "component-ex-second",
    )
    assert len(split.replacement_rules[0].components) == 3
    mixed = _merge_component_only_repair(
        single.model_copy(update={"replacement_rules": [SemanticRule(
            official_code="EX-01", components=[selected],
            restricted_components=[SemanticRestrictedComponent(
                title="独立待核要求", source_span_ids=["span-ex"],
                source_excerpts=["ALT或AST≥1.5×ULN"],
                limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["独立要求的适用范围未明确"],
            )],
        )]}),
        parent, 1, "component-ex-second",
    )
    assert mixed.replacement_rules[0].components == [sibling, selected]
    assert len(mixed.replacement_rules[0].restricted_components) == 1
    with pytest.raises(ValueError, match="可执行分支或单个受限子项"):
        _merge_component_only_repair(
            single.model_copy(update={"replacement_rules": [
                single.replacement_rules[0].model_copy(update={"components": []})
            ]}),
            parent, 1, "component-ex-second",
        )


    unsupported = single.model_copy(update={"replacement_rules": [SemanticRule(
        official_code="EX-01", components=[],
        restricted_components=[SemanticRestrictedComponent(
            title="未核清的子项", source_span_ids=["span-ex"],
            source_excerpts=["ALT或AST≥1.5×ULN"],
            limitation_kind="consumer_unavailable",
            unresolved_dimensions=["原文判断关系尚未核清"],
        )],
    )]})
    converted = _merge_component_only_repair(unsupported, parent, 1, "component-ex-second")
    assert converted.replacement_rules[0].components == [sibling]
    assert converted.replacement_rules[0].restricted_components[0].title == "未核清的子项"
    ambiguous = unsupported.model_copy(deep=True)
    ambiguous.replacement_rules[0].restricted_components[0].limitation_kind = "interpretation_unresolved"
    with pytest.raises(ValueError, match="不能把可执行子项改为含义待核"):
        _merge_component_only_repair(ambiguous, parent, 1, "component-ex-second")
    unscoped = single.model_copy(update={
        "replacement_unresolved_items": [UnresolvedItem(
            code="scope_unresolved", affected_scope=["component-ex-other"],
            source_refs=["span-ex"],
        )],
    })
    with pytest.raises(ValueError, match="必须指向选中的子项"):
        _merge_component_only_repair(unscoped, parent, 1, "component-ex-second")
    parent_scoped = single.model_copy(update={
        "replacement_unresolved_items": [UnresolvedItem(
            code="source_question", affected_scope=["EX-01"], source_refs=["span-ex"],
        )],
    })
    singleton = SemanticRule(official_code="EX-01", components=[original.components[0]])
    narrowed = _merge_component_only_repair(parent_scoped, singleton, 0, "component-ex")
    assert narrowed.replacement_unresolved_items[0].affected_scope == ["component-ex"]
    with pytest.raises(ValueError, match="必须指向选中的子项"):
        _merge_component_only_repair(parent_scoped, parent, 1, "component-ex-second")
    borrowed = parent_scoped.model_copy(deep=True)
    borrowed.replacement_unresolved_items[0].source_refs = ["span-in"]
    with pytest.raises(ValueError, match="必须指向选中的子项"):
        _merge_component_only_repair(borrowed, singleton, 0, "component-ex")


@pytest.mark.parametrize("ref_kind", ["identity", "display"])
def test_restricted_issue_selects_only_its_parent_and_reaches_repair_consumer(ref_kind):
    _, draft, _ = _fixture()
    restricted = RestrictedRuleComponent(
        rule_component_id="restricted-component-ex", display_code="EX-01b",
        title="独立要求待核", source_span_ids=["span-ex"], source_excerpts=["有源要求"],
        limitation_kind="interpretation_unresolved", unresolved_dimensions=["适用范围"],
    )
    draft.proposed_rules[1].restricted_components = [restricted]
    ref = restricted.rule_component_id if ref_kind == "identity" else restricted.display_code
    issue = ProtocolGateIssue(
        issue_code="RESTRICTED_COMPONENT_SOURCE_INVALID", check_name="source_coverage",
        level="阻止发布", problem="摘录未对应", impact="不可采用", next_action="核对摘录",
        affected_refs=[ref], repair_scope=[ref],
    )
    before = draft.model_dump(mode="json")
    assert _affected_rule_codes(draft, [issue]) == ["EX-01"]
    assert _select_repair_rule_codes(draft, [issue], {}, limit=1) == ["EX-01"]
    assert _repair_issues_for_rules(draft, [issue], ["EX-01"]) == [issue]
    assert _repair_issues_for_rules(draft, [issue], ["IN-01"]) == []
    assert _affected_rule_codes(draft, [issue.model_copy(update={
        "affected_refs": ["unrelated-component"],
    })], fallback_all=False) == []
    assert regressing_rule_codes(draft, [], draft, [issue], ["EX-01"]) == {"EX-01"}
    assert draft.model_dump(mode="json") == before


@pytest.mark.parametrize("ref_kind", ["requirement", "draft_requirement", "draft_component", "catalog",
                                         "repeat_condition", "repeat_predicate"])
def test_saved_requirement_and_repeat_issues_have_exact_repair_owner(ref_kind):
    _, draft, _ = _fixture()
    rule = draft.proposed_rules[1]
    component = rule.components[0]
    if ref_kind.startswith("repeat_"):
        condition_expression = component.expression.children[0].model_copy(deep=True)
        condition_expression.predicate.predicate_id = "repeat-observation-ex"
        condition = RepeatTriggerCondition(condition_id="repeat-condition-ex", expression=condition_expression)
        component.expression.children[0].predicate.repeat_scheme = RepeatScheme(
            scope="当前原文要求", source_span_ids=["span-ex"], source_excerpts=["ALT或AST≥1.5×ULN"],
            permission="optional", trigger="source_condition", trigger_excerpt="ALT或AST≥1.5×ULN",
            trigger_condition_id=condition.condition_id, count_status="not_specified",
            time_status="not_specified", result_use="not_specified",
        )
        component.repeat_trigger_conditions = [condition]
        # Validate the real rule contract, not a bare extra attribute.
        type(component).model_validate(component.model_dump(mode="json"))
        ref = condition.condition_id if ref_kind == "repeat_condition" else condition_expression.predicate.predicate_id
    elif ref_kind == "requirement":
        ref = component.evidence_requirements[0].requirement_id
    elif ref_kind == "catalog":
        ref = next(item.catalog_item_id for item in draft.parent_catalog_mappings
                   if item.proposed_rule_id == rule.rule_id)
    else:
        mapped = next(item for item in draft.component_drafts
                      if item.proposed_component.rule_component_id == component.rule_component_id)
        ref = (mapped.draft_component_id if ref_kind == "draft_component" else
               next(item.draft_requirement_id for item in draft.evidence_requirement_drafts
                    if item.draft_component_id == mapped.draft_component_id))
    issue = ProtocolGateIssue(
        issue_code="SYNTHETIC_SOURCE_FAILURE", check_name="source_coverage", level="阻止发布",
        problem="对应要求尚未核清", impact="不能采用", next_action="核对当前要求",
        affected_refs=[ref], repair_scope=[ref],
    )
    before = draft.model_dump(mode="json")
    assert _affected_rule_codes(draft, [issue], fallback_all=False) == [rule.official_code]
    assert _select_repair_rule_codes(draft, [issue], {}, limit=3) == [rule.official_code]
    assert _repair_issues_for_rules(draft, [issue], [rule.official_code]) == [issue]
    assert _repair_issues_for_rules(draft, [issue], [draft.proposed_rules[0].official_code]) == []
    assert regressing_rule_codes(draft, [], draft, [issue], [rule.official_code]) == {rule.official_code}
    assert draft.model_dump(mode="json") == before


def test_procedure_and_unknown_labels_are_not_owned_by_an_official_rule():
    _, draft, _ = _fixture()
    procedure = next(item for item in draft.evidence_requirement_drafts
                     if item.procedure_catalog_item_id is not None)
    for ref in (procedure.draft_requirement_id, procedure.proposed_requirement.requirement_id,
                "error mentions EX-01 but is not an identity", "span-ex"):
        issue = ProtocolGateIssue(
            issue_code="SYNTHETIC_SOURCE_FAILURE", check_name="source_coverage", level="阻止发布",
            problem="非官方条件身份", impact="不能交给错误父项", next_action="核对来源",
            affected_refs=[ref], repair_scope=[ref],
        )
        assert _affected_rule_codes(draft, [issue], fallback_all=False) == []
        assert _select_repair_rule_codes(draft, [issue], {}, limit=3) == []
        assert _repair_issues_for_rules(draft, [issue], ["IN-01", "EX-01"]) == []


def test_component_feedback_only_sends_selected_component_gate_issues():
    from app.services.protocol_workbench_service import ProtocolWorkbenchService

    _, draft, _ = _fixture()
    selected = draft.proposed_rules[1].components[0]
    sibling = selected.model_copy(update={
        "rule_component_id": "component-ex-sibling",
        "display_code": "EX-01b",
    })
    rule = SimpleNamespace(components=[selected, sibling], restricted_components=[])
    predicate_id = next(iter_atomic_predicates(selected.expression)).predicate_id

    def issue(ref: str) -> ProtocolGateIssue:
        return ProtocolGateIssue(
            issue_code="SOURCE_CHECK", check_name="来源核对", level="阻止发布",
            problem="原文未对应", impact="不能采用", next_action="核对原文",
            affected_refs=[ref], repair_scope=[ref],
        )

    selected_issue = issue(selected.rule_component_id)
    predicate_issue = issue(predicate_id)
    sibling_issue = issue(sibling.rule_component_id)
    parent_issue = issue("EX-01")
    issues = [selected_issue, predicate_issue, sibling_issue, parent_issue]
    assert ProtocolWorkbenchService._feedback_issues_for_component(
        rule, selected.rule_component_id, issues,
    ) == [selected_issue, predicate_issue]
    assert ProtocolWorkbenchService._feedback_issues_for_component(
        SimpleNamespace(components=[selected], restricted_components=[]),
        selected.rule_component_id, issues,
    ) == issues


def test_component_feedback_split_preserves_siblings_and_source_scope():
    from app.services.protocol_workbench_service import ProtocolWorkbenchService

    source_input, draft, _ = _fixture()
    initial = semantic_candidate_from_draft(draft)
    sibling_semantic = initial.proposed_rules[1].components[0].model_copy(deep=True)
    sibling_semantic.title = "不参与本次修订的另一子项"
    initial.proposed_rules[1].components.append(sibling_semantic)
    draft = _hydrate_semantic_candidate(source_input, initial)
    candidate = semantic_candidate_from_draft(draft)
    target = draft.proposed_rules[1].components[0]
    untouched_sibling = draft.proposed_rules[1].components[1]
    original = candidate.proposed_rules[1].components[0]
    second = original.model_copy(deep=True)
    second.title = "第二个完整触发分支"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[original, second],
        )],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="split-feedback", text=repair.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=target.rule_component_id,
        feedback_note="逐字核对两个完整分支", transport=transport,
    )
    components = revised.proposed_rules[1].components
    assert [item.rule_component_id for item in components] == [
        target.rule_component_id, f"{target.rule_component_id}:split:02",
        untouched_sibling.rule_component_id,
    ]
    assert components[2] == untouched_sibling
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01",
        target_component_id=target.rule_component_id,
    )
    borrowed = revised.model_copy(deep=True)
    extra = next(item for item in borrowed.component_drafts
                 if item.proposed_component.rule_component_id == components[1].rule_component_id)
    extra.source_refs = ["span-in"]
    with pytest.raises(ValueError, match="所选子项以外的原文"):
        ProtocolWorkbenchService._validate_source_error_scope(
            draft, borrowed, target_rule_code="EX-01",
            target_component_id=target.rule_component_id,
        )


def test_component_feedback_uses_compact_target_input():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    selected = candidate.proposed_rules[1].components[0].model_copy(deep=True)
    selected.title = "按目标原文修订"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(official_code="EX-01", components=[selected])],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="component-feedback", text=repair.model_dump_json())
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", target_component_id="component-ex",
        feedback_note="只纠正本子项。", transport=transport,
    )
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert revised.proposed_rules[1].components[0].title == "按目标原文修订"
    assert "只返回子项 component-ex" in transport.start_prompts[0]


def test_component_feedback_restricted_conversion_preserves_identity_and_rejects_clear_bound():
    source_input, draft, spans = _fixture()
    draft = _hydrate_semantic_candidate(source_input, semantic_candidate_from_draft(draft))
    candidate = semantic_candidate_from_draft(draft)
    target_id = draft.proposed_rules[1].components[0].rule_component_id
    target_display = draft.proposed_rules[1].components[0].display_code
    replacement = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[],
            restricted_components=[SemanticRestrictedComponent(
                title="需核清的要求", source_span_ids=["span-ex"],
                source_excerpts=["ALT或AST≥1.5×ULN"],
                limitation_kind="consumer_unavailable",
                unresolved_dimensions=["原文范围尚待核清"],
            )],
        )],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="restricted-feedback", text=replacement.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=target_id, feedback_note="请核对来源范围", transport=transport,
    )
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert not revised.proposed_rules[1].components
    assert revised.proposed_rules[1].restricted_components[0].rule_component_id == target_id
    assert revised.proposed_rules[1].restricted_components[0].display_code == target_display
    assert all(item.draft_component_id != f"draft-component:{target_id}"
               for item in revised.component_drafts)
    assert all(item.proposed_requirement.rule_component_id != target_id
               for item in revised.evidence_requirement_drafts)
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01", target_component_id=target_id,
    )
    result = ProtocolDeconstructionGate().evaluate(source_input, revised, source_spans=spans)
    assert "RESTRICTED_COMPONENT_CAPABILITY_UNPROVEN" in {
        issue.issue_code for check in result.checks for issue in check.issues
    }


def test_component_feedback_mixed_branch_is_source_bound_and_not_auto_accepted():
    source_input, draft, spans = _fixture()
    draft = _hydrate_semantic_candidate(source_input, semantic_candidate_from_draft(draft))
    candidate = semantic_candidate_from_draft(draft)
    selected = draft.proposed_rules[1].components[0]
    selected_semantic = candidate.proposed_rules[1].components[0]
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[selected_semantic],
            restricted_components=[SemanticRestrictedComponent(
                title="待核的独立要求", source_span_ids=["span-ex"],
                source_excerpts=["ALT或AST≥1.5×ULN"],
                limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["独立要求的适用范围未明确"],
            )],
        )],
    )
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=selected.rule_component_id,
        feedback_note="核对独立要求", transport=FakeTransport([
            ProtocolAgentResponse(session_id="mixed-feedback", text=repair.model_dump_json()),
        ]),
    )
    rule = revised.proposed_rules[1]
    assert rule.components[0].rule_component_id == selected.rule_component_id
    assert rule.restricted_components[0].rule_component_id.startswith(
        selected.rule_component_id + ":split:"
    )
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01",
        target_component_id=selected.rule_component_id,
    )
    issues = {
        issue.issue_code
        for check in ProtocolDeconstructionGate().evaluate(
            source_input, revised, source_spans=spans,
        ).checks for issue in check.issues
    }
    assert "RESTRICTED_COMPONENT_SCOPE_INVALID" in issues or "RESTRICTED_COMPONENT_SWALLOWS_NUMERIC_BOUND" in issues

    borrowed = revised.model_copy(deep=True)
    borrowed.proposed_rules[1].restricted_components[0].source_span_ids = ["span-in"]
    with pytest.raises(ValueError, match="不得借用所选子项以外的原文"):
        ProtocolWorkbenchService._validate_source_error_scope(
            draft, borrowed, target_rule_code="EX-01",
            target_component_id=selected.rule_component_id,
        )


def test_component_feedback_mixed_branch_publishes_independent_unresolved_requirement(slice4_env):
    source_input, draft, spans = _fixture()
    source_text = "年龄≥18岁；必要时另须完成专项评估"
    source_input.source_materials[0].text = source_text
    parent_items = list(source_input.parent_rule_catalog.items)
    parent_items[0] = parent_items[0].model_copy(update={"label": source_text})
    source_input.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items)
    candidate = semantic_candidate_from_draft(draft)
    candidate.proposed_rules[0].components[0].source_excerpts = [source_text]
    draft = _hydrate_semantic_candidate(source_input, candidate)
    selected = draft.proposed_rules[0].components[0]
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(
            official_code="IN-01", components=[candidate.proposed_rules[0].components[0]],
            restricted_components=[SemanticRestrictedComponent(
                title="独立专项评估", source_span_ids=["span-in"],
                source_excerpts=["必要时另须完成专项评估"],
                limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["必要时的适用条件未在原文明确"],
            )],
        )],
    )
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="IN-01",
        target_component_id=selected.rule_component_id,
        feedback_note="将独立专项评估单列待核", transport=FakeTransport([
            ProtocolAgentResponse(session_id="mixed-positive", text=repair.model_dump_json()),
        ]),
    )
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="IN-01",
        target_component_id=selected.rule_component_id,
    )
    gate = ProtocolDeconstructionGate().evaluate(source_input, revised, source_spans=spans)
    assert gate.publishable, [issue.issue_code for check in gate.checks for issue in check.issues]

    from app.domain.contracts.protocol_drafts import DraftFeedbackKind
    from app.projections.clause_pack import project_clause_pack
    from app.services.eligibility_review_projection import _restricted_clause_projection
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.services.protocol_publication_service import (
        ProtocolPublicationRequest, ProtocolPublicationService,
    )
    from app.storage.repositories import get_rule_set
    from tests.v2.protocols.slice4_helpers import NOW
    factory, _now = slice4_env
    with factory() as session:
        with session.begin():
            service = ProtocolDraftService(session)
            initial = service.save_initial_draft(draft, actor="医学监查员", created_at=NOW)
            saved = service.apply_feedback(
                revised, expected_revision_id=initial.revision_id,
                feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
                feedback_note="将独立专项评估单列待核", actor="医学监查员", created_at=NOW,
            )
    published = ProtocolPublicationService(factory, now=lambda: NOW).publish(
        ProtocolPublicationRequest(
            idempotency_key="mixed-feedback-publication", draft_revision_id=saved.revision_id,
            source_input=source_input, source_spans=spans, actor="医学监查员", published_at=NOW,
        ),
    )
    with factory() as session:
        rule_set = get_rule_set(session, published.rule_set_id, published.rule_set_revision)
        pack = project_clause_pack(rule_set)
    assert any(item.clause_id == selected.rule_component_id for item in pack.clauses)
    restricted = next(item for item in pack.restricted_clauses
                      if item.clause_id.startswith(selected.rule_component_id + ":split:"))
    assert _restricted_clause_projection(restricted).decision_label == "无法判定"


def test_component_feedback_restricted_conversion_accepts_source_bound_separate_obligation(slice4_env):
    source_input, draft, spans = _fixture()
    nested = "有严重感染既往史（包括反复细菌感染（2年内发生2次或以上））"
    source_input.source_materials[1].text = nested
    parent_items = list(source_input.parent_rule_catalog.items)
    parent_items[1] = parent_items[1].model_copy(update={"label": nested})
    source_input.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items)
    draft.proposed_rules[1].source_text = nested
    draft = _hydrate_semantic_candidate(source_input, semantic_candidate_from_draft(draft))
    candidate = semantic_candidate_from_draft(draft)
    target_id = draft.proposed_rules[1].components[0].rule_component_id
    replacement = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[],
            restricted_components=[SemanticRestrictedComponent(
                title="既往感染史", source_span_ids=["span-ex"],
                source_excerpts=[nested],
                limitation_kind="consumer_unavailable",
                unresolved_dimensions=["上位开放既往史与列举项专属频次尚不能同时可靠表达"],
            )],
        )],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="restricted-feedback", text=replacement.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=target_id, feedback_note="请核对列举项专属频次", transport=transport,
    )
    result = ProtocolDeconstructionGate().evaluate(source_input, revised, source_spans=spans)
    assert result.publishable, {issue.issue_code for check in result.checks for issue in check.issues}
    from app.domain.contracts.protocol_drafts import DraftFeedbackKind
    from app.projections.clause_pack import project_clause_pack
    from app.services.eligibility_review_projection import _restricted_clause_projection
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.services.protocol_publication_service import (
        ProtocolPublicationRequest, ProtocolPublicationService,
    )
    from app.storage.repositories import get_rule_set
    from tests.v2.protocols.slice4_helpers import NOW
    factory, _now = slice4_env
    with factory() as session:
        with session.begin():
            initial = ProtocolDraftService(session).save_initial_draft(
                draft, actor="医学监查员", created_at=NOW,
            )
            saved = ProtocolDraftService(session).apply_feedback(
                revised, expected_revision_id=initial.revision_id,
                feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
                feedback_note="EX-01：核对专项评估原文", actor="医学监查员", created_at=NOW,
            )
    published = ProtocolPublicationService(factory, now=lambda: NOW).publish(
        ProtocolPublicationRequest(
            idempotency_key="restricted-feedback-publication",
            draft_revision_id=saved.revision_id, source_input=source_input,
            source_spans=spans, actor="医学监查员", published_at=NOW,
        ),
    )
    with factory() as session:
        rule_set = get_rule_set(session, published.rule_set_id, published.rule_set_revision)
        pack = project_clause_pack(rule_set)
    restricted = next(item for item in pack.restricted_clauses if item.clause_id == target_id)
    projection = _restricted_clause_projection(restricted)
    assert projection.decision_label == "无法判定"
    assert projection.fact_refs == ()


def test_component_feedback_restricted_conversion_keeps_later_sibling_identity():
    source_input, draft, spans = _fixture()
    nested = "有严重感染既往史（包括反复细菌感染（2年内发生2次或以上））"
    source_input.source_materials[1].text = f"ALT或AST≥1.5×ULN；{nested}"
    parent_items = list(source_input.parent_rule_catalog.items)
    parent_items[1] = parent_items[1].model_copy(update={"label": source_input.source_materials[1].text})
    source_input.parent_rule_catalog = _catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items)
    original = semantic_candidate_from_draft(draft)
    parent = original.proposed_rules[1]
    sibling = parent.components[0].model_copy(deep=True)
    target = sibling.model_copy(update={
        "title": "既往感染史", "source_excerpts": [nested],
    }, deep=True)
    original.proposed_rules[1] = parent.model_copy(update={
        "components": [sibling, target],
    })
    draft = _hydrate_semantic_candidate(source_input, original)
    before = draft.proposed_rules[1]
    target_id = before.components[1].rule_component_id
    repair = ProtocolSemanticRuleRepair(
        candidate_id=semantic_candidate_from_draft(draft).candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[],
            restricted_components=[SemanticRestrictedComponent(
                title="既往感染史", source_span_ids=["span-ex"],
                source_excerpts=[nested],
                limitation_kind="consumer_unavailable",
                unresolved_dimensions=["上位开放既往史与列举项专属频次尚不能同时可靠表达"],
            )],
        )],
    )
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01", target_component_id=target_id,
        feedback_note="只核对列举项专属频次", transport=FakeTransport([
            ProtocolAgentResponse(session_id="restricted-sibling", text=repair.model_dump_json()),
        ]),
    )
    after = revised.proposed_rules[1]
    assert after.components == [before.components[0]]
    assert after.restricted_components[0].rule_component_id == target_id
    assert after.restricted_components[0].display_code == before.components[1].display_code
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01", target_component_id=target_id,
    )
    result = ProtocolDeconstructionGate().evaluate(source_input, revised, source_spans=spans)
    assert result.publishable, {issue.issue_code for check in result.checks for issue in check.issues}
    next_candidate = semantic_candidate_from_draft(revised)
    next_sibling = next_candidate.proposed_rules[1].components[0].model_copy(
        update={"title": "肝功能界限"}, deep=True,
    )
    next_repair = ProtocolSemanticRuleRepair(
        candidate_id=next_candidate.candidate_id,
        replacement_rules=[SemanticRule(official_code="EX-01", components=[next_sibling])],
    )
    second = revise_protocol_draft_from_feedback(
        source_input, revised, target_rule_code="EX-01",
        target_component_id=before.components[0].rule_component_id,
        feedback_note="仅修订肝功能子项标题", transport=FakeTransport([
            ProtocolAgentResponse(session_id="second-feedback", text=next_repair.model_dump_json()),
        ]),
    )
    assert second.proposed_rules[1].restricted_components == after.restricted_components
    assert second.proposed_rules[1].components[0].rule_component_id == before.components[0].rule_component_id


def test_restricted_child_feedback_can_restore_one_executable_with_same_identity(slice4_env):
    source_input, draft, spans = _fixture()
    original = semantic_candidate_from_draft(draft)
    executable = original.proposed_rules[0].components[0]
    original.proposed_rules[0] = SemanticRule(
        official_code="IN-01", components=[],
        restricted_components=[SemanticRestrictedComponent(
            title="年龄要求待核", source_span_ids=["span-in"],
            source_excerpts=["年龄≥18岁"],
            limitation_kind="interpretation_unresolved",
            unresolved_dimensions=["适用范围待核"],
        )],
    )
    draft = _hydrate_semantic_candidate(source_input, original)
    before = draft.proposed_rules[0].restricted_components[0]
    repair = ProtocolSemanticRuleRepair(
        candidate_id=semantic_candidate_from_draft(draft).candidate_id,
        replacement_rules=[SemanticRule(official_code="IN-01", components=[executable])],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="restricted-to-executable", text=repair.model_dump_json()),
    ])
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="IN-01",
        target_component_id=before.rule_component_id,
        feedback_note="按原文核实年龄要求", transport=transport,
    )
    after = revised.proposed_rules[0]
    assert after.restricted_components == []
    assert after.components[0].rule_component_id == before.rule_component_id
    assert after.components[0].display_code == before.display_code
    assert revised.proposed_rules[1] == draft.proposed_rules[1]
    assert "本次只返回待核子项" in transport.start_prompts[0]
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="IN-01",
        target_component_id=before.rule_component_id,
    )
    result = ProtocolDeconstructionGate().evaluate(source_input, revised, source_spans=spans)
    assert result.publishable, {issue.issue_code for check in result.checks for issue in check.issues}
    from app.domain.contracts.protocol_drafts import DraftFeedbackKind
    from app.projections.clause_pack import project_clause_pack
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.services.protocol_publication_service import (
        ProtocolPublicationRequest, ProtocolPublicationService,
    )
    from app.storage.repositories import get_rule_set
    from tests.v2.protocols.slice4_helpers import NOW
    factory, _ = slice4_env
    with factory() as session:
        with session.begin():
            service = ProtocolDraftService(session)
            initial = service.save_initial_draft(draft, actor="医学监查员", created_at=NOW)
            saved = service.apply_feedback(
                revised, expected_revision_id=initial.revision_id,
                feedback_kind=DraftFeedbackKind.SOURCE_ERROR,
                feedback_note="IN-01：核对年龄要求", actor="医学监查员", created_at=NOW,
            )
    published = ProtocolPublicationService(factory, now=lambda: NOW).publish(
        ProtocolPublicationRequest(
            idempotency_key="restricted-restored-publication",
            draft_revision_id=saved.revision_id, source_input=source_input,
            source_spans=spans, actor="医学监查员", published_at=NOW,
        ),
    )
    with factory() as session:
        rule_set = get_rule_set(session, published.rule_set_id, published.rule_set_revision)
        pack = project_clause_pack(rule_set)
    assert any(item.clause_id == before.rule_component_id for item in pack.clauses)
    assert all(item.clause_id != before.rule_component_id for item in pack.restricted_clauses)


def test_restricted_child_feedback_keeps_executable_sibling_and_rejects_multiple_replacements():
    source_input, draft, _ = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    candidate.proposed_rules[1].restricted_components = [SemanticRestrictedComponent(
        title="独立待核要求", source_span_ids=["span-ex"],
        source_excerpts=["ALT或AST≥1.5×ULN"],
        limitation_kind="interpretation_unresolved",
        unresolved_dimensions=["适用条件待核"],
    )]
    draft = _hydrate_semantic_candidate(source_input, candidate)
    before = draft.proposed_rules[1]
    restricted_id = before.restricted_components[0].rule_component_id
    revised_restricted = candidate.proposed_rules[1].restricted_components[0].model_copy(
        update={"unresolved_dimensions": ["仍需核对条件范围"]}, deep=True,
    )
    repair = ProtocolSemanticRuleRepair(
        candidate_id=semantic_candidate_from_draft(draft).candidate_id,
        replacement_rules=[SemanticRule(
            official_code="EX-01", components=[],
            restricted_components=[revised_restricted],
        )],
    )
    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        target_component_id=restricted_id,
        feedback_note="仅核对待核子项", transport=FakeTransport([
            ProtocolAgentResponse(session_id="restricted-only", text=repair.model_dump_json()),
        ]),
    )
    assert revised.proposed_rules[1].components[0] == before.components[0]
    assert revised.proposed_rules[1].restricted_components[0].rule_component_id == restricted_id
    from app.services.protocol_workbench_service import ProtocolWorkbenchService
    ProtocolWorkbenchService._validate_source_error_scope(
        draft, revised, target_rule_code="EX-01", target_component_id=restricted_id,
    )
    duplicated = repair.model_copy(update={"replacement_rules": [SemanticRule(
        official_code="EX-01", components=[
            candidate.proposed_rules[1].components[0],
            candidate.proposed_rules[1].components[0].model_copy(deep=True),
        ],
    )]})
    with pytest.raises(ValueError, match="一次只能转为一个"):
        _merge_component_only_repair(
            duplicated, semantic_candidate_from_draft(draft).proposed_rules[1],
            None, restricted_id, restricted_index=0,
        )


@pytest.mark.parametrize(
    ("invalid_atom", "expected_code"),
    [
        ({"comparator": "gte"}, "DNF_WIRE_UNKNOWN_FIELD"),
        ({"semantic_proposition": None}, "DNF_WIRE_MISSING_FIELD"),
    ],
)
def test_wire_atom_errors_identify_group_and_atom(invalid_atom, expected_code):
    group = {"existence_atoms": [invalid_atom], "scalar_atoms": [], "set_atoms": []}
    with pytest.raises(ProtocolWireError) as exc_info:
        _wire_dnf_expression(
            [group], identity_prefix="test", label="expression", source_text="原文",
        )
    assert exc_info.value.code == expected_code
    assert "第 1 组 existence_atoms[1]" in str(exc_info.value)


def test_compact_feedback_repair_prompt_names_rejected_atom_location():
    source_input, draft, _ = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    payload = _wire_candidate(candidate.model_copy(
        update={"proposed_rules": [candidate.proposed_rules[1]]}, deep=True,
    ), batch_id="repair:EX-01")
    payload["replacement_rules"] = payload.pop("proposed_rules")
    payload["replacement_structural_warnings"] = payload.pop("structural_warnings")
    payload["replacement_unresolved_items"] = payload.pop("unresolved_items")
    payload.pop("created_by_agent_call_id")
    invalid = json.loads(json.dumps(payload))
    invalid["replacement_rules"][0]["components"][0]["expression"][0]["scalar_atoms"][0]["unexpected"] = True
    transport = CompactFakeTransport([
        ProtocolAgentResponse(session_id="located-repair", text=json.dumps(invalid, ensure_ascii=False)),
        ProtocolAgentResponse(session_id="located-repair", text=json.dumps(payload, ensure_ascii=False)),
    ])
    revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        feedback_note="按原文核对", transport=transport,
    )
    assert len(transport.repair_prompts) == 1
    assert "DNF_WIRE_UNKNOWN_FIELD" in transport.repair_prompts[0][1]
    assert "第 1 组 scalar_atoms[1]" in transport.repair_prompts[0][1]


def test_feedback_projection_preserves_existing_restricted_limitation_kind():
    _, draft, _spans = _fixture()
    draft.proposed_rules[0].restricted_components.append(RestrictedRuleComponent(
        rule_component_id="component:IN-01:02", display_code="IN-01b",
        title="有源但暂不能自动计算的要求", source_span_ids=["span-in"],
        source_excerpts=["年龄≥18岁"], limitation_kind="consumer_unavailable",
        unresolved_dimensions=["当前结构不能表达源中的限定关系"],
    ))
    projected = semantic_candidate_from_draft(draft)
    assert projected.proposed_rules[0].restricted_components[0].limitation_kind == "consumer_unavailable"


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
    assert "筛选期血生化检查" not in transport.start_prompts[0]
    assert "基线血生化检查" not in transport.start_prompts[0]
    assert "parent_rule_catalog_total" not in transport.start_prompts[0]
    assert "required_procedure_catalog_total" not in transport.start_prompts[0]
    assert len(transport.repair_prompts) == 1
    assert "batch_id 必须为 repair:EX-01" in transport.repair_prompts[0][1]


def test_feedback_source_context_keeps_only_procedures_sharing_selected_source():
    source_input, draft, _spans = _fixture()
    first, second = source_input.required_procedure_catalog.items
    related = first.model_copy(update={"source_span_ids": ("span-ex",)})
    source_input.required_procedure_catalog = source_input.required_procedure_catalog.model_copy(
        update={"items": (related, second)}
    )
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="feedback-scope", text=repair.model_dump_json())
    ])

    revised = revise_protocol_draft_from_feedback(
        source_input, draft, target_rule_code="EX-01",
        feedback_note="核对原文", transport=transport,
    )

    payload = json.loads(
        transport.start_prompts[0].split("冻结的方案输入：", 1)[1].split(
            "\n\n输出结构：", 1
        )[0]
    )
    assert revised.proposed_rules[0] == draft.proposed_rules[0]
    assert [item["item_id"] for item in payload["required_procedure_catalog"]] == [
        related.item_id
    ]
    assert payload["allowed_source_span_ids"] == ["span-ex"]
    assert [item["source_span_id"] for item in payload["source_materials"]] == ["span-ex"]


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


@pytest.mark.parametrize("field", ["structural_warnings", "unresolved_items"])
def test_partial_repair_preserves_shared_pending_state_and_hydrated_history(field):
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    before = [
        UnresolvedItem(code="SHARED", affected_scope=["IN-01", "component:EX-01:01"]),
        UnresolvedItem(code="OTHER", affected_scope=["IN-01"]),
        UnresolvedItem(code="TARGET", affected_scope=["component:EX-01:01"]),
        UnresolvedItem(code="UNATTRIBUTED", affected_scope=["unattributed"]),
    ]
    setattr(candidate, field, before)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[candidate.proposed_rules[1]],
    )
    setattr(repair, "replacement_" + field, [UnresolvedItem(code="NEW_TARGET", affected_scope=["EX-01"])])
    merged = _apply_semantic_repair(candidate, repair, expected_codes=["EX-01"])
    assert [item.code for item in getattr(merged, field)] == ["SHARED", "OTHER", "UNATTRIBUTED", "NEW_TARGET"]
    assert getattr(candidate, field) == before
    assert getattr(_hydrate_semantic_candidate(source_input, merged), field) == getattr(merged, field)
    # A complete jointly scoped repair can replace a shared item; a one-parent
    # response cannot claim that authority.
    joint = ProtocolSemanticRuleRepair(candidate_id=candidate.candidate_id, replacement_rules=candidate.proposed_rules)
    assert [item.code for item in getattr(_apply_semantic_repair(candidate, joint, expected_codes=["IN-01", "EX-01"]), field)] == ["UNATTRIBUTED"]
    foreign = repair.model_copy(deep=True)
    setattr(foreign, "replacement_" + field, [before[0]])
    with pytest.raises(ValueError, match="指定父规则之外"):
        _apply_semantic_repair(candidate, foreign, expected_codes=["EX-01"])


@pytest.mark.parametrize("field", ["structural_warnings", "unresolved_items"])
def test_regression_restores_pending_state_with_restored_rules_not_other_changes(field):
    source_input, draft, _spans = _fixture()
    previous = _semantic_candidate(source_input, draft)
    old_items = [
        UnresolvedItem(code="OLD_EX", affected_scope=["EX-01"]),
        UnresolvedItem(code="SHARED", affected_scope=["IN-01", "EX-01"]),
    ]
    setattr(previous, field, old_items)
    revised = previous.model_copy(deep=True)
    revised.proposed_rules[0].components[0].title = "保留的新入选标题"
    revised.proposed_rules[1].components[0].title = "退回的排除修订"
    setattr(revised, field, [
        UnresolvedItem(code="NEW_IN", affected_scope=["IN-01"]),
        UnresolvedItem(code="DISCARDED_EX", affected_scope=["EX-01"]),
        UnresolvedItem(code="DISCARDED_SHARED", affected_scope=["IN-01", "EX-01"]),
    ])
    restored = _restore_candidate_rules(revised, previous, {"EX-01"})
    assert restored.proposed_rules[0] == revised.proposed_rules[0]
    assert restored.proposed_rules[1] == previous.proposed_rules[1]
    assert [item.code for item in getattr(restored, field)] == ["NEW_IN", "OLD_EX", "SHARED"]
    assert getattr(_hydrate_semantic_candidate(source_input, restored), field) == getattr(restored, field)
    assert getattr(previous, field) == old_items
    assert getattr(revised, field)[1].code == "DISCARDED_EX"


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


def test_joint_source_feedback_explains_whole_source_restriction_without_changing_default():
    source_input, draft, _spans = _fixture()
    candidate = semantic_candidate_from_draft(draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id,
        replacement_rules=[candidate.proposed_rules[1]],
    )
    transports = [
        FakeTransport([ProtocolAgentResponse(session_id="joint", text=repair.model_dump_json())]),
        FakeTransport([ProtocolAgentResponse(session_id="ordinary", text=repair.model_dump_json())]),
    ]
    for joint, transport in zip((True, False), transports):
        revise_protocol_draft_from_feedback(
            source_input, draft, target_rule_code="EX-01",
            feedback_note="核对同一来源段的条件关系。", transport=transport,
            joint_source_repair=joint,
        )
    joint_prompt, ordinary_prompt = (item.start_prompts[0] for item in transports)
    assert "不要同时保留与其来源重叠的可执行子项" in joint_prompt
    assert "本次是最小范围纠错，不是重写整条规则" not in joint_prompt
    assert "本次是最小范围纠错，不是重写整条规则" in ordinary_prompt
    for prompt in (joint_prompt, ordinary_prompt):
        assert "source_clauses 必须按原文出现顺序排列" in prompt
        assert "不必为来源绑定额外重复摘录括号" in prompt
        assert "不得为迎合摘录格式改变适用对象" in prompt
    assert "不要同时保留与其来源重叠的可执行子项" not in ordinary_prompt


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
    assert "无该条事项时两个数组均为空" in transport.repair_prompts[0][1]


def test_valid_json_passes_without_repair(whole_draft_fixture_budget):
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


def test_runner_keeps_successful_transport_receipt_on_existing_attempt():
    source_input, draft, spans = _fixture()
    template = "按正式方案原文进行结构化解构。"
    metadata = {"attempts": [{
        "request_id": "receipt-1", "usage": {"total_tokens": 31},
        "reasoning_characters": 12,
    }]}
    transport = FakeTransport([ProtocolAgentResponse(
        session_id="receipt-session", text=draft.model_dump_json(),
        call_metadata=metadata,
    )])

    result = ProtocolDeconstructorRunner().run(
        source_input, prompt_version=_prompt_version(template),
        prompt_template=template, transport=transport, source_spans=spans,
    )

    assert result.attempts[0].call_metadata == metadata
    assert result.model_dump(mode="json")["attempts"][0]["call_metadata"] == metadata


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


def test_reminders_do_not_steal_repair_slots_from_blocking_unknown_scope():
    _source_input, draft, _spans = _fixture()
    issues = [
        _gate_issue("CAPABILITY_REMINDER", ["predicate-age"], level="提醒"),
        _gate_issue("SOURCE_IDENTITY_UNKNOWN", ["unmapped-source"]),
    ]
    assert _select_repair_rule_codes(draft, issues, {}, limit=1) == []
    issues.append(_gate_issue("EX_ISSUE", ["req-ex"]))
    assert _select_repair_rule_codes(draft, issues, {}, limit=1) == ["EX-01"]
    reminder = _gate_issue("EX_REMINDER", ["req-ex"], level="提醒")
    assert _repair_issues_for_rules(draft, [*issues, reminder], ["EX-01"]) == [issues[-1]]


def test_stagnation_signature_preserves_meaning_source_and_error_level():
    _source_input, draft, _spans = _fixture()
    issue = _gate_issue("SOURCE_SCOPE", ["component-in"])
    original = _repair_stagnation_signature(draft, [issue], "IN-01")
    renamed = draft.model_copy(deep=True)
    renamed.proposed_rules[0].components[0].title = "换一种标题写法"
    wording = issue.model_copy(update={"problem": "另一个显示说明"})
    assert _repair_stagnation_signature(renamed, [wording], "IN-01") == original
    assert _repair_stagnation_signature(draft, [issue.model_copy(
        update={"level": "需要核对"}
    )], "IN-01") != original
    changed = draft.model_copy(deep=True)
    changed.proposed_rules[0].components[0].expression.predicate.value = 21
    assert _repair_stagnation_signature(changed, [issue], "IN-01") != original
    rebound = draft.model_copy(deep=True)
    rebound.component_drafts[0].source_excerpts.append("新的共同限定")
    assert _repair_stagnation_signature(rebound, [issue], "IN-01") != original


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


def test_lean_semantic_candidate_is_hydrated_from_frozen_catalogs(whole_draft_fixture_budget):
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


def test_large_official_catalog_is_collected_in_ordered_same_session_batches(monkeypatch):
    source_input, draft, _spans = _fixture()
    base_candidate = _semantic_candidate(source_input, draft)
    codes = ["IN-01", "IN-02", "IN-03", "EX-01", "EX-02", "EX-03"]
    items = []
    for index, code in enumerate(codes):
        template = source_input.parent_rule_catalog.items[0 if code.startswith("IN-") else 1]
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
        for code in rule_codes:
            rule = base_candidate.proposed_rules[0 if code.startswith("IN-") else 1].model_copy(deep=True)
            rule.official_code = code
            rules.append(rule)
        return base_candidate.model_copy(update={"proposed_rules": rules}, deep=True)

    # This test covers ordered collection and receipts; planner budget boundaries
    # are exercised separately with the real planner.
    monkeypatch.setattr(
        "app.agents.protocol_deconstructor._plan_semantic_rule_batches",
        lambda *_args, **_kwargs: [codes[:3], codes[3:]],
    )

    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[:3]).model_dump_json(),
                call_metadata={"attempts": [{"request_id": "batch-1", "usage": None}]},
            ),
            ProtocolAgentResponse(
                session_id="session-1", text=batch(codes[3:]).model_dump_json(),
                call_metadata={"attempts": [{"request_id": "batch-2", "usage": None}]},
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
    assert [item["attempts"][0]["request_id"] for item in response.call_metadata["batches"]] == [
        "batch-1", "batch-2",
    ]
    assert response.call_metadata["reused_without_call"] == []
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


def test_invalid_output_is_repaired_in_same_session(whole_draft_fixture_budget):
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


def test_valid_candidate_repairs_only_affected_parent_rule(whole_draft_fixture_budget):
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


@pytest.mark.parametrize("compact", [False, True])
def test_bounded_repair_prompt_keeps_exact_current_target_and_not_other_rules(compact):
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    target = candidate.proposed_rules[1]
    target.restricted_components.append(SemanticRestrictedComponent(
        title="有源但尚未支持的部分", source_span_ids=target.components[0].source_span_ids,
        source_excerpts=target.components[0].source_excerpts,
        limitation_kind="consumer_unavailable", unresolved_dimensions=["计算方式"],
    ))
    candidate.unresolved_items = [
        UnresolvedItem(code="TARGET", affected_scope=["component:EX-01:01"]),
        UnresolvedItem(code="SHARED", affected_scope=["IN-01", "EX-01"]),
        UnresolvedItem(code="OTHER", affected_scope=["IN-01"]),
    ]
    candidate.structural_warnings = [UnresolvedItem(code="WARNING", affected_scope=["EX-01"])]
    before = candidate.model_dump(mode="json")
    prompt = _repair_prompt(
        [], attempt=1, parsed_draft_available=True, replacement_rule_codes=["EX-01"],
        compact=compact, include_frozen_context=True, candidate=candidate, source_input=source_input,
    )
    context = json.JSONDecoder().raw_decode(prompt.split("只返回 replacement_rules：", 1)[1])[0]
    assert context["repair_context_version"] == "official-target-repair-context/v1"
    assert context["current_target_rules"] == [target.model_dump(mode="json")]
    assert context["current_target_rule_codes"] == ["EX-01"]
    assert [item["code"] for item in context["current_target_unresolved_items"]] == ["TARGET", "SHARED"]
    assert context["current_target_structural_warnings"] == [candidate.structural_warnings[0].model_dump(mode="json")]
    assert context["candidate_id"] == candidate.candidate_id
    assert context["frozen_batch_input"]["batch_rule_codes"] == ["EX-01"]
    assert candidate.model_dump(mode="json") == before


@pytest.mark.parametrize("codes", [["EX-99"], ["EX-01", "EX-01"]])
def test_bounded_repair_refuses_missing_or_duplicate_current_targets(codes):
    source_input, draft, _spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    with pytest.raises(ValueError, match="唯一对应当前保存"):
        _repair_prompt(
            [], attempt=1, parsed_draft_available=True, replacement_rule_codes=codes,
            include_frozen_context=True, candidate=candidate, source_input=source_input,
        )


def test_actual_bounded_formal_runner_supplies_target_after_history_compaction(whole_draft_fixture_budget):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = LogicalOperator.ALL
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[candidate.proposed_rules[1]],
    )

    class BoundedFormalTransport(CompactFakeTransport):
        uses_compact_wire_contract = False
        supports_bounded_batch_context = True

        def continue_session(self, *, session_id, prompt, output_kind="semantic_candidate"):
            assert len(self.histories[session_id]) == 2
            assert "proposed_rules" not in self.histories[session_id][0]["content"]
            context = json.JSONDecoder().raw_decode(prompt.split("只返回 replacement_rules：", 1)[1])[0]
            assert context["current_target_rules"] == [bad_candidate.proposed_rules[1].model_dump(mode="json")]
            return super().continue_session(session_id=session_id, prompt=prompt, output_kind=output_kind)

    transport = BoundedFormalTransport([
        ProtocolAgentResponse(session_id="bounded-session", text=bad_candidate.model_dump_json()),
        ProtocolAgentResponse(session_id="bounded-session", text=repair.model_dump_json()),
    ])
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner().run(
        source_input, prompt_version=_prompt_version(template), prompt_template=template,
        transport=transport, source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    assert transport.compact_contexts
    assert result.attempts[1].call_metadata["repair_context_version"] == "official-target-repair-context/v1"
    assert result.attempts[1].call_metadata["repair_prompt_sha256"] == hashlib.sha256(transport.repair_prompts[0][1].encode()).hexdigest()
    assert result.final_draft.proposed_rules[0].components[0].expression == candidate.proposed_rules[0].components[0].expression


def test_requirement_failure_reaches_actual_runner_without_repairing_other_parent(whole_draft_fixture_budget):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[candidate.proposed_rules[1]],
    )

    class RequirementFailureGate(ProtocolDeconstructionGate):
        calls = 0

        def evaluate(self, *args, **kwargs):
            result = super().evaluate(*args, **kwargs)
            self.calls += 1
            if self.calls != 1:
                return result
            # Inject one typed requirement failure; all other gate logic is real.
            evaluated = args[1]
            requirement = evaluated.proposed_rules[1].components[0].evidence_requirements[0]
            result = result.model_copy(deep=True)
            check = next(item for item in result.checks if item.check_name == "source_coverage")
            check.issues.append(ProtocolGateIssue(
                issue_code="SYNTHETIC_REQUIREMENT_FAILURE", check_name=check.check_name,
                level="阻止发布", problem="核对指定资料要求", impact="尚不能采用",
                next_action="核对该要求", affected_refs=[requirement.requirement_id],
                repair_scope=[requirement.requirement_id],
            ))
            check.passed = False
            result.publishable = False
            return result

    transport = FakeTransport([
        ProtocolAgentResponse(session_id="requirement-session", text=candidate.model_dump_json()),
        ProtocolAgentResponse(session_id="requirement-session", text=repair.model_dump_json()),
    ])
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner(gate=RequirementFailureGate(), max_semantic_repairs=1).run(
        source_input, prompt_version=_prompt_version(template), prompt_template=template,
        transport=transport, source_spans=spans,
    )
    assert result.status == "可以进入审阅"
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1
    assert transport.repair_output_kinds == ["semantic_rule_repair"]
    assert "['EX-01']" in transport.repair_prompts[0][1]
    requirement_ref = result.attempts[0].issues[0].affected_refs[0]
    assert requirement_ref in transport.repair_prompts[0][1]
    assert "SYNTHETIC_REQUIREMENT_FAILURE" in transport.repair_prompts[0][1]
    assert result.final_draft.proposed_rules[0].components[0].expression == candidate.proposed_rules[0].components[0].expression
    assert candidate == _semantic_candidate(source_input, draft)


def test_actual_runner_regression_keeps_previous_rule_and_pending_state(whole_draft_fixture_budget):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    candidate.unresolved_items = [UnresolvedItem(code="OLD_EX", affected_scope=["EX-01"])]
    candidate.structural_warnings = [UnresolvedItem(code="SHARED", affected_scope=["IN-01", "EX-01"])]
    replacement = candidate.proposed_rules[1].model_copy(deep=True)
    replacement.components[0].title = "被拒修订"
    repair = ProtocolSemanticRuleRepair(
        candidate_id=candidate.candidate_id, replacement_rules=[replacement],
        replacement_unresolved_items=[UnresolvedItem(code="DISCARDED", affected_scope=["EX-01"])],
    )

    class RegressionGate(ProtocolDeconstructionGate):
        calls = 0

        def evaluate(self, *args, **kwargs):
            result = super().evaluate(*args, **kwargs).model_copy(deep=True)
            self.calls += 1
            requirement = args[1].proposed_rules[1].components[0].evidence_requirements[0]
            check = next(item for item in result.checks if item.check_name == "source_coverage")
            check.issues.append(ProtocolGateIssue(
                issue_code="NEW_ERROR" if self.calls == 2 else "OLD_ERROR",
                check_name=check.check_name, level="阻止发布", problem="合成定向恢复反例",
                impact="尚不能采用", next_action="保留原稿", affected_refs=[requirement.requirement_id],
                repair_scope=[requirement.requirement_id],
            ))
            check.passed = False
            result.publishable = False
            return result

    transport = FakeTransport([
        ProtocolAgentResponse(session_id="regression-session", text=candidate.model_dump_json()),
        ProtocolAgentResponse(session_id="regression-session", text=repair.model_dump_json()),
    ])
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner(gate=RegressionGate(), max_semantic_repairs=1).run(
        source_input, prompt_version=_prompt_version(template), prompt_template=template,
        transport=transport, source_spans=spans,
    )
    expected = _hydrate_semantic_candidate(source_input, candidate)
    assert result.status == "需要核对"
    assert not result.final_gate_result.publishable
    assert result.final_draft.proposed_rules == expected.proposed_rules
    assert result.final_draft.unresolved_items == candidate.unresolved_items
    assert result.final_draft.structural_warnings == candidate.structural_warnings
    assert result.attempts[-1].raw_output_sha256 == hashlib.sha256(repair.model_dump_json().encode()).hexdigest()
    assert len(transport.start_prompts) == len(transport.repair_prompts) == 1


@pytest.mark.parametrize("checkpoint_session", ["protocol-parent-segments-checkpoint", "protocol-semantic-cache-abc123"])
@pytest.mark.parametrize("bounded", [False, True])
def test_checkpoint_candidate_starts_targeted_repair_session(monkeypatch, checkpoint_session, bounded):
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
                session_id=checkpoint_session,
                text=bad_candidate.model_dump_json(),
            ),
            None,
        ),
    )
    class CheckpointTransport(FakeTransport):
        supports_bounded_batch_context = bounded

        def compact_session_history(self, *, session_id, context):
            raise AssertionError("恢复检查点没有可供压缩的真实旧会话")

    transport = CheckpointTransport(
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
    context = json.JSONDecoder().raw_decode(transport.start_prompts[0].split("只返回 replacement_rules：", 1)[1])[0]
    assert context["current_target_rules"] == [bad_candidate.proposed_rules[1].model_dump(mode="json")]
    assert context["frozen_batch_input"]["batch_rule_codes"] == ["EX-01"]


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


def test_only_two_targeted_repairs_are_allowed(whole_draft_fixture_budget):
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


@pytest.mark.parametrize("rename_title", [False, True])
def test_unchanged_semantic_repairs_stop_without_spending_all_budget(
    whole_draft_fixture_budget, rename_title,
):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad_candidate = candidate.model_copy(deep=True)
    bad_candidate.proposed_rules[1].components[0].expression.operator = (
        LogicalOperator.ALL
    )
    repairs = []
    for index in range(16):
        replacement = bad_candidate.proposed_rules[1].model_copy(deep=True)
        if rename_title:
            replacement.components[0].title = f"检查说明{index}"
        repairs.append(ProtocolSemanticRuleRepair(
            candidate_id=candidate.candidate_id, replacement_rules=[replacement],
        ))
    template = "按正式方案原文进行结构化解构。"
    transport = FakeTransport(
        [
            ProtocolAgentResponse(
                session_id="session-1", text=bad_candidate.model_dump_json()
            ),
            *[
                ProtocolAgentResponse(
                    session_id="session-1", text=repair.model_dump_json()
                )
                for repair in repairs
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
    assert len(result.attempts) == 3
    assert len(transport.repair_prompts) == 2
    assert len(transport.responses) == 14
    assert all("['EX-01']" in prompt for _, prompt in transport.repair_prompts)
    assert result.final_gate_result.publishable is False
    expected = _hydrate_semantic_candidate(source_input, candidate)
    assert result.final_draft.proposed_rules[0] == expected.proposed_rules[0]
    metadata = result.model_dump(mode="json")["attempts"][-1]["call_metadata"]
    assert metadata["repair_recovery"] == {
        "policy": ProtocolDeconstructorRunner.RECOVERY_POLICY,
        "unchanged_repair_limit": 2,
        "unchanged_repairs": {"EX-01": 2},
        "stopped_rule_codes": ["EX-01"],
    }


def test_stalled_parent_does_not_stop_another_parent_repair(
    whole_draft_fixture_budget, monkeypatch,
):
    monkeypatch.setattr(ProtocolDeconstructorRunner, "MAX_RULES_PER_REPAIR", 1)
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)
    bad = candidate.model_copy(deep=True)
    bad.proposed_rules[0].components[0].expression.predicate.value = 17
    bad.proposed_rules[1].components[0].expression.operator = LogicalOperator.ALL
    repair_rules = [bad.proposed_rules[0], bad.proposed_rules[1],
                    bad.proposed_rules[0], candidate.proposed_rules[1]]
    transport = FakeTransport([
        ProtocolAgentResponse(session_id="session-1", text=bad.model_dump_json()),
        *[ProtocolAgentResponse(session_id="session-1", text=ProtocolSemanticRuleRepair(
            candidate_id=candidate.candidate_id, replacement_rules=[rule],
        ).model_dump_json()) for rule in repair_rules],
    ])
    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner().run(
        source_input, prompt_version=_prompt_version(template),
        prompt_template=template, transport=transport, source_spans=spans,
    )
    assert result.status == "需要核对"
    assert len(transport.repair_prompts) == 4
    for (_, prompt), rule in zip(transport.repair_prompts, repair_rules):
        assert repr([rule.official_code]) in prompt
    expected = _hydrate_semantic_candidate(source_input, candidate)
    assert result.final_draft.proposed_rules[1] == expected.proposed_rules[1]
    assert result.final_draft.proposed_rules[0].components[0].expression.predicate.value == 17
    assert result.final_gate_result.publishable is False
    assert result.attempts[-1].call_metadata["repair_recovery"]["stopped_rule_codes"] == ["IN-01"]


def test_stall_guard_preserves_frozen_request_budget_identity(whole_draft_fixture_budget):
    source_input, draft, spans = _fixture()
    candidate = _semantic_candidate(source_input, draft)

    class RecordingTransport(FakeTransport):
        def semantic_cache_identity(self, *, output_kind, frozen_run):
            assert output_kind == "semantic_candidate" and frozen_run is True
            return "frozen-fixture-identity"

        def configure_logical_run(self, **kwargs):
            self.run_budget = kwargs

    template = "按正式方案原文进行结构化解构。"
    transport = RecordingTransport([
        ProtocolAgentResponse(session_id="session-1", text=candidate.model_dump_json()),
    ])
    result = ProtocolDeconstructorRunner().run(
        source_input, prompt_version=_prompt_version(template),
        prompt_template=template, transport=transport, source_spans=spans,
    )
    legacy_contract = {
        "prompt": _prompt_version(template).template_sha256,
        "transport": "frozen-fixture-identity",
        "initial_units": 1, "semantic_repair_limit": 16,
        "recovery_policy": "bounded-recovery/v1",
    }
    expected_hash = hashlib.sha256(json.dumps(legacy_contract, sort_keys=True).encode()).hexdigest()
    assert transport.run_budget["contract_sha256"] == expected_hash
    assert transport.run_budget["max_requests"] == 41
    assert result.status == "可以进入审阅"


def test_invalid_local_repair_gets_one_schema_retry_without_empty_issue_list(whole_draft_fixture_budget):
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


def test_repair_cannot_silently_switch_session(whole_draft_fixture_budget):
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


def test_interrupted_stream_metadata_survives_in_failed_run_receipt():
    source_input, _draft, spans = _fixture()

    class InterruptedTransport:
        def start(self, *, prompt, output_kind="semantic_candidate"):
            raise ProtocolAgentCallError(
                "stream-session", "方案解构流式回包中断：ReadError",
                error_code="STREAM_INTERRUPTED",
                error_metadata={"request_id": "request-1", "content_characters": 8},
            )

    template = "按正式方案原文进行结构化解构。"
    result = ProtocolDeconstructorRunner().run(
        source_input,
        prompt_version=_prompt_version(template),
        prompt_template=template,
        transport=InterruptedTransport(),
        source_spans=spans,
    )
    assert result.status == "需要核对"
    assert result.attempts[0].call_metadata == {
        "error_code": "STREAM_INTERRUPTED",
        "request_id": "request-1", "content_characters": 8,
    }
    assert result.model_dump(mode="json")["attempts"][0]["call_metadata"]["request_id"] == "request-1"


def test_repair_transport_failure_preserves_prior_draft_and_stops_cleanly(whole_draft_fixture_budget):
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
