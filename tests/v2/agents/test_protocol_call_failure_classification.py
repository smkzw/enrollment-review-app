"""Transport failures must not request a JSON repair."""

import pytest

from app.agents.protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    ProtocolDeconstructorRunner,
)
from app.agents.protocol_semantic_model_router import summarize_run_result_for_route
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture
from tests.v2.protocols.test_protocol_deconstructor_adapter_slice3 import _prompt_version


@pytest.mark.parametrize("during_repair", [False, True])
@pytest.mark.parametrize("code", ["TRANSPORT_TIMEOUT", "SEMANTIC_CALL_FAILED", "QUOTA_EXHAUSTED"])
def test_typed_call_failure_retains_classification_without_another_repair(code, during_repair):
    class Transport:
        calls = 0

        def start(self, **kwargs):
            self.calls += 1
            if during_repair:
                return ProtocolAgentResponse(session_id="failure-session", text="{}")
            raise ProtocolAgentCallError("failure-session", "provider detail", error_code=code)

        def continue_session(self, **kwargs):
            self.calls += 1
            raise ProtocolAgentCallError("failure-session", "provider detail", error_code=code)

    source, _, spans = _fixture()
    transport = Transport()
    result = ProtocolDeconstructorRunner().run(
        source,
        prompt_version=_prompt_version("Read source"),
        prompt_template="Read source",
        transport=transport,
        source_spans=spans,
    )
    assert summarize_run_result_for_route(result)[1] == code
    assert result.final_draft is None
    assert result.same_session_id == "failure-session"
    assert transport.calls == (2 if during_repair else 1)
    assert result.attempts[0].issues[0].repair_scope == ["model_service"]
    assert "AGENT_OUTPUT_SCHEMA_INVALID" != result.attempts[0].issues[0].issue_code
