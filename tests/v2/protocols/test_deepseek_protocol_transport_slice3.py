from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.deepseek_protocol_transport import DeepSeekProtocolAgentTransport
from app.llm import client as llm_client


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = next(self.outputs)
        if isinstance(output, tuple):
            content, finish_reason, reasoning_content = output
        else:
            content, finish_reason, reasoning_content = output, "stop", ""
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(
                        content=content,
                        reasoning_content=reasoning_content,
                    ),
                )
            ]
        )


def _client(outputs):
    completions = FakeCompletions(outputs)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    ), completions


def test_transport_retains_full_same_session_history_and_max_reasoning():
    client, completions = _client(['{"draft":1}', '{"draft":2}'])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    first = transport.start(prompt="首轮完整输入")
    second = transport.continue_session(
        session_id=first.session_id, prompt="仅修正时间锚点"
    )

    assert second.session_id == first.session_id
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert completions.calls[1]["messages"][1]["content"] == '{"draft":1}'
    assert completions.calls[1]["reasoning_effort"] == "max"
    assert completions.calls[1]["extra_body"] == {"thinking": {"type": "enabled"}}
    assert completions.calls[1]["response_format"] == {"type": "json_object"}
    assert len(transport.history(first.session_id)) == 4


def test_unknown_session_is_rejected_instead_of_starting_fresh():
    client, _completions = _client([])
    transport = DeepSeekProtocolAgentTransport(client=client)
    with pytest.raises(ValueError, match="找不到原方案解构会话"):
        transport.continue_session(session_id="missing", prompt="修正")


def test_persisted_complete_history_can_resume_without_starting_fresh():
    client, completions = _client(['{"repair":1}'])
    transport = DeepSeekProtocolAgentTransport(client=client)
    history = [
        {"role": "user", "content": "首轮完整输入"},
        {"role": "assistant", "content": '{"draft":1}'},
    ]

    transport.restore_history(session_id="persisted-session", messages=history)
    response = transport.continue_session(
        session_id="persisted-session", prompt="仅修正EX-04"
    )

    assert response.session_id == "persisted-session"
    assert completions.calls[0]["messages"][:2] == history
    assert completions.calls[0]["messages"][2]["content"] == "仅修正EX-04"


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "assistant", "content": "无首轮请求"}],
        [
            {"role": "user", "content": "请求"},
            {"role": "user", "content": "角色顺序错误"},
        ],
        [{"role": "user", "content": "尚无模型响应"}],
    ],
)
def test_invalid_persisted_history_is_rejected(messages):
    client, _completions = _client([])
    transport = DeepSeekProtocolAgentTransport(client=client)
    with pytest.raises(ValueError, match="持久方案解构会话|只能从"):
        transport.restore_history(session_id="persisted-session", messages=messages)


def test_empty_body_is_retried_once_without_changing_logical_session():
    client, completions = _client(
        [(None, "length", "内部推理"), ('{"draft":1}', "stop", "")]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    response = transport.start(prompt="首轮完整输入")

    assert response.text == '{"draft":1}'
    assert len(completions.calls) == 2
    assert completions.calls[1]["messages"][:-1] == completions.calls[0]["messages"]
    assert "不要重复分析" in completions.calls[1]["messages"][-1]["content"]
    assert len(transport.history(response.session_id)) == 2


def test_two_empty_bodies_report_finish_reason_without_exposing_reasoning():
    client, _completions = _client(
        [
            (None, "length", "不应出现在异常中的内部推理"),
            (None, "length", "仍不应暴露"),
        ]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    with pytest.raises(RuntimeError, match="连续2次.*结束原因=length") as exc:
        transport.start(prompt="首轮完整输入")

    assert "内部推理" not in str(exc.value)
    assert len(transport.history(exc.value.session_id)) == 1
    assert transport.history(exc.value.session_id)[0]["content"] == "首轮完整输入"


def test_deconstruct_completion_kwargs_use_independent_reasoning_setting(monkeypatch):
    monkeypatch.setattr(llm_client, "DECONSTRUCT_BACKEND", "deepseek")
    monkeypatch.setattr(llm_client, "DECONSTRUCT_REASONING_EFFORT", "max")
    kwargs = llm_client._deconstruct_completion_kwargs(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": "方案"}],
        temperature=0.9,
        max_tokens=60000,
    )
    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "temperature" not in kwargs
