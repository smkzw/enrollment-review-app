import httpx
import pytest
from types import SimpleNamespace
from openai import RateLimitError

from app.agents.protocol_deconstructor import ProtocolAgentCallError
from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from tests.v2.protocols.test_deepseek_protocol_transport_slice3 import _client


@pytest.mark.parametrize("code", ["1308", "1310"])
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("continuation", [False, True])
def test_exhausted_quota_is_not_retried_or_relabelled_as_format_error(monkeypatch, code, nested, continuation):
    body = {"code": code, "message": "quota exhausted"}
    if nested:
        body = {"error": body}
    error = RateLimitError(
        "quota exhausted", response=httpx.Response(
            429, request=httpx.Request("POST", "https://example.invalid/completions")
        ), body=body,
    )
    client, calls = _client([error])
    waits = []
    monkeypatch.setattr("app.agents.protocol_semantic_transport.time.sleep", waits.append)
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="zhipu-coding-plan", model="glm-5.3-flash",
        reasoning_effort="high", max_tokens=65536,
    )
    if continuation:
        transport.restore_history(session_id="same-session", messages=[
            {"role": "user", "content": "source"},
            {"role": "assistant", "content": '{"result": "prior"}'},
        ])
    with pytest.raises(ProtocolAgentCallError) as raised:
        if continuation:
            transport.continue_session(session_id="same-session", prompt="repair")
        else:
            transport.start(prompt="source")
    assert raised.value.error_code == "QUOTA_EXHAUSTED"
    assert len(calls.calls) == 1
    assert waits == []
    if continuation:
        assert raised.value.session_id == "same-session"


@pytest.mark.parametrize("backend,code", [("zhipu-coding-plan", "1302"), ("deepseek", "1310")])
def test_transient_throttling_and_other_provider_codes_keep_existing_policy(monkeypatch, backend, code):
    error = RateLimitError(
        "rate limit", response=httpx.Response(
            429, request=httpx.Request("POST", "https://example.invalid/completions")
        ), body={"code": code},
    )
    client, calls = _client([error, '{"result": "ok"}'])
    waits = []
    monkeypatch.setattr("app.agents.protocol_semantic_transport.time.sleep", waits.append)
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend=backend, model="test-model", reasoning_effort="high",
    )
    assert transport.start(prompt="source").text == '{"result": "ok"}'
    assert len(calls.calls) == 2
    assert waits == [2.0]


def test_segment_quota_failure_does_not_fall_back_to_another_whole_parent_call(monkeypatch):
    from app.agents import protocol_deconstructor as module
    from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture

    source, _, _ = _fixture()
    code = source.parent_rule_catalog.items[0].official_code
    plan = SimpleNamespace(segments=[SimpleNamespace(segment_id="segment-a")])
    monkeypatch.setattr(module, "plan_parent_rule_segments", lambda *args, **kwargs: plan)
    original = ProtocolAgentCallError("preserved-session", "quota", error_code="QUOTA_EXHAUSTED")

    def collect(*args, **kwargs):
        raise module.ProtocolParentSegmentError("segment-a", "QUOTA_EXHAUSTED", "quota") from original

    monkeypatch.setattr(module, "_collect_parent_segment", collect)
    with pytest.raises(ProtocolAgentCallError) as raised:
        module._try_collect_parent_segments(
            source, prompt_template="source", parent_prompt="source", rule_codes=[code],
            transport_factory=lambda: None, batch_cache=None, candidate_id=None, agent_call_id=None,
        )
    assert raised.value is original
