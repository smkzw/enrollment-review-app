from __future__ import annotations

import pytest

from app.agents.protocol_deconstructor import (
    DNF_WIRE_VERSION,
    _hydrate_semantic_candidate,
    _omlx_wire_schema,
    _validate_semantic_batch,
    _wire_semantic_rule,
)
from app.domain.contracts.agent_io import (
    ProtocolSemanticDeconstructionCandidate,
    SemanticRestrictedComponent,
    SemanticRule,
)
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


def _source_bound_rule() -> SemanticRule:
    return SemanticRule(
        official_code="IN-01",
        components=[],
        restricted_components=[SemanticRestrictedComponent(
            title="原文独立要求",
            source_span_ids=["span-in"],
            source_excerpts=["年龄≥18岁"],
            limitation_kind="interpretation_unresolved",
            unresolved_dimensions=["该年龄要求的适用范围尚未核清"],
        )],
    )


def test_restricted_rule_wire_requires_source_and_explicit_limitation() -> None:
    rule = _source_bound_rule()
    schema = _omlx_wire_schema(
        "semantic_candidate", official_codes=("IN-01",),
        allowed_source_span_ids=("span-in",),
    )
    rule_schema = schema["properties"]["proposed_rules"]["items"]
    assert "restricted_components" in rule_schema["required"]
    assert schema["properties"]["wire_version"]["const"] == DNF_WIRE_VERSION
    hydrated = _wire_semantic_rule(rule.model_dump(mode="json"))
    assert hydrated["components"] == []
    assert hydrated["restricted_components"][0]["source_span_ids"] == ["span-in"]

    assert rule_schema["properties"]["restricted_components"]["items"]["properties"][
        "limitation_kind"
    ]["enum"] == ["interpretation_unresolved", "consumer_unavailable"]
    unverified = _wire_semantic_rule({
        **rule.model_dump(mode="json"),
        "restricted_components": [{
            **rule.restricted_components[0].model_dump(mode="json"),
            "limitation_kind": "consumer_unavailable",
        }],
    })
    assert unverified["restricted_components"][0]["limitation_kind"] == "consumer_unavailable"


def test_restricted_rule_hydrates_only_frozen_source_and_keeps_sibling_rule() -> None:
    source, draft, _ = _fixture()
    from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import _semantic_candidate

    original = _semantic_candidate(source, draft)
    candidate = ProtocolSemanticDeconstructionCandidate(
        candidate_id="restricted-slice",
        proposed_rules=[_source_bound_rule(), original.proposed_rules[1]],
        created_by_agent_call_id="agent-call-1",
    )
    hydrated = _hydrate_semantic_candidate(source, candidate)
    assert hydrated.proposed_rules[0].components == []
    assert hydrated.proposed_rules[0].restricted_components[0].source_excerpts == ["年龄≥18岁"]
    assert hydrated.proposed_rules[1].components[0].expression == draft.proposed_rules[1].components[0].expression
    assert hydrated.proposed_rules[1].components[0].evidence_requirements[0].fact_type == draft.proposed_rules[1].components[0].evidence_requirements[0].fact_type


def test_restricted_rule_must_stay_in_selected_parent_source_closure() -> None:
    source, draft, _ = _fixture()
    from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import _semantic_candidate

    candidate = _semantic_candidate(source, draft).model_copy(update={
        "proposed_rules": [_source_bound_rule()],
    })
    _validate_semantic_batch(
        candidate, expected_codes=["IN-01"], expected_candidate_id=None,
        source_input=source,
    )
    candidate.proposed_rules[0].restricted_components[0].source_span_ids = ["span-ex"]
    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _validate_semantic_batch(
            candidate, expected_codes=["IN-01"], expected_candidate_id=None,
            source_input=source,
        )

    candidate = _semantic_candidate(source, draft)
    candidate.proposed_rules[0].restricted_components = [
        _source_bound_rule().restricted_components[0].model_copy(update={
            "source_span_ids": ["span-ex"],
        })
    ]
    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _validate_semantic_batch(
            candidate, expected_codes=["IN-01", "EX-01"],
            expected_candidate_id=None, source_input=source,
        )

    candidate.proposed_rules[0].restricted_components = []
    candidate.proposed_rules[0].components[0].source_span_ids = ["span-ex"]
    with pytest.raises(ValueError, match="来源片段不属于选定父规则来源闭包"):
        _validate_semantic_batch(
            candidate, expected_codes=["IN-01", "EX-01"],
            expected_candidate_id=None, source_input=source,
        )
