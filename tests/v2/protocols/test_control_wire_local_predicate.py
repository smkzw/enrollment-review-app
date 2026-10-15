"""Only a comparison-local label may come from the control wire provider."""

import json

import pytest

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentWireValidationError,
    _find_forbidden_provider_key,
    parse_protocol_control_agent_wire,
)
from tests.v2.protocols.test_slice58c_control_deconstructor import _candidate, _wire


def test_deterministic_candidate_round_trips_without_rejecting_local_label():
    wire = _wire(candidate=_candidate())
    parsed = parse_protocol_control_agent_wire(wire.model_dump_json())
    assert parsed == wire


@pytest.mark.parametrize("field", ["evaluation", "repeat_trigger_conditions"])
def test_current_required_fields_cannot_be_omitted(field):
    payload = _wire(candidate=_candidate()).model_dump(mode="json")
    candidate = payload["candidate_drafts"][0]
    target = (candidate["obligation_expression"]["groups"][0]["atoms"][0]
              if field == "evaluation" else candidate)
    del target[field]
    with pytest.raises(ProtocolControlAgentWireValidationError, match="WIRE_SCHEMA_INVALID"):
        parse_protocol_control_agent_wire(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize("layer", ["applicability", "trigger", "obligation", "exception"])
def test_local_label_is_allowed_only_in_expression_evaluation(layer):
    path = f"candidate_drafts[0].{layer}_expression.groups[1].atoms[2].evaluation.predicate"
    assert _find_forbidden_provider_key({"predicate_id": "local"}, path) is None
    assert _find_forbidden_provider_key({"atom_id": "not-local"}, path) is not None


def test_repeat_condition_local_label_is_allowed():
    path = "candidate_drafts[0].repeat_trigger_conditions[1].expression.groups[0].atoms[2].evaluation.predicate"
    assert _find_forbidden_provider_key({"predicate_id": "local"}, path) is None


@pytest.mark.parametrize("placement", ["root", "candidate", "atom"])
def test_local_label_does_not_authorize_provider_owned_ids(placement):
    payload = _wire(candidate=_candidate()).model_dump(mode="json")
    target = payload
    if placement != "root":
        target = payload["candidate_drafts"][0]
    if placement == "atom":
        target = target["obligation_expression"]["groups"][0]["atoms"][0]
    target["predicate_id"] = "not-local"
    with pytest.raises(ProtocolControlAgentWireValidationError, match="PROVIDER_ID_FORBIDDEN"):
        parse_protocol_control_agent_wire(json.dumps(payload, ensure_ascii=False))
