"""Fault-injection tests for the provider-neutral transient retry boundary.

Proves the contract required for SAR controlled recovery:
- transient 5xx/429/connection failures are retried a finite number of times
  against the byte-identical request payload (same session, same model route);
- the retry budget is finite and the final error keeps the session recoverable;
- non-transient 4xx failures and timeouts are never retried;
- neither the raised error nor the retry warnings leak credentials;
- user-facing recovery semantics stay in Chinese.
"""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.agents.protocol_deconstructor import ProtocolAgentCallError

SECRET_API_KEY = "sk-secret-glm-key-0123456789abcdef"


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=output, reasoning_content=""),
                )
            ]
        )


def _client(outputs):
    completions = FakeCompletions(outputs)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def _authed_request() -> httpx.Request:
    """Mimic a real provider call: the request object carries the credential."""
    return httpx.Request(
        "POST",
        "https://provider.example/v1/chat/completions",
        headers={"Authorization": f"Bearer {SECRET_API_KEY}"},
    )


def _status_error(exc_type, status_code: int, message: str):
    request = _authed_request()
    return exc_type(
        message,
        response=httpx.Response(status_code, request=request),
        body=None,
    )


def _glm_transport(outputs, monkeypatch=None, sleeps=None):
    if monkeypatch is not None and sleeps is not None:
        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    client, completions = _client(outputs)
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        api_key=SECRET_API_KEY,
    )
    return transport, completions


def test_transient_5xx_is_retried_finitely_then_succeeds_with_identical_payload(
    monkeypatch,
):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [
            _status_error(InternalServerError, 500, "Error code: 500 - internal error"),
            _status_error(InternalServerError, 500, "Error code: 500 - still down"),
            '{"draft":1}',
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    response = transport.start(prompt="首轮完整输入")

    assert response.text == '{"draft":1}'
    assert len(completions.calls) == 3
    # Every retry resends the byte-identical request payload: the retry can
    # never mutate the logical session or switch the model route.
    assert completions.calls[0] == completions.calls[1] == completions.calls[2]
    assert completions.calls[0]["model"] == "glm-5.3-flash"
    assert sleeps == [2.0, 4.0]
    # Retries never touch session history: only user + assistant survive.
    assert len(transport.history(response.session_id)) == 2


@pytest.mark.parametrize(
    "transient_error",
    [
        _status_error(RateLimitError, 429, "Error code: 429 - rate limited"),
        APIConnectionError(request=_authed_request()),
        httpx.ConnectError("connection refused"),
    ],
    ids=["429-rate-limit", "connection-error", "httpx-transport-error"],
)
def test_transient_429_and_connection_errors_are_retried_then_succeed(
    transient_error, monkeypatch
):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [transient_error, '{"draft":2}'],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    response = transport.start(prompt="首轮完整输入")

    assert response.text == '{"draft":2}'
    assert len(completions.calls) == 2
    assert completions.calls[0] == completions.calls[1]
    assert sleeps == [2.0]


def test_mid_session_transient_retry_keeps_repair_history_unchanged(monkeypatch):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [
            '{"draft":1}',
            _status_error(InternalServerError, 502, "Error code: 502 - bad gateway"),
            '{"draft":2}',
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )
    first = transport.start(prompt="首轮完整输入")

    second = transport.continue_session(
        session_id=first.session_id, prompt="仅修正EX-04"
    )

    assert second.session_id == first.session_id
    assert len(completions.calls) == 3
    # The retried repair attempt replays the full u/a/u history unchanged.
    assert completions.calls[2]["messages"] == completions.calls[1]["messages"]
    assert [item["role"] for item in completions.calls[2]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert [item["role"] for item in transport.history(first.session_id)] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_retry_budget_is_finite_and_final_error_keeps_session_recoverable(
    monkeypatch, caplog
):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [
            _status_error(InternalServerError, 500, "Error code: 500 - down 1"),
            _status_error(InternalServerError, 500, "Error code: 500 - down 2"),
            _status_error(InternalServerError, 500, "Error code: 500 - down 3"),
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    with caplog.at_level(
        logging.WARNING, logger="app.agents.protocol_semantic_transport"
    ):
        with pytest.raises(ProtocolAgentCallError) as caught:
            transport.start(prompt="首轮完整输入")

    # Exactly the finite budget: 3 attempts, 2 backoff waits, no 4th attempt.
    assert len(completions.calls) == 3
    assert sleeps == [2.0, 4.0]
    assert caught.value.session_id
    # The failed session is retained in full for SAR recovery.
    assert transport.history(caught.value.session_id) == (
        {"role": "user", "content": "首轮完整输入"},
    )
    # Recovery continues the same logical session instead of starting fresh.
    recovered_client, recovered_completions = _client(['{"draft":"recovered"}'])
    transport._client = recovered_client
    recovered = transport.continue_session(
        session_id=caught.value.session_id, prompt="服务已恢复，继续当前会话"
    )
    assert recovered.session_id == caught.value.session_id
    assert recovered_completions.calls[0]["messages"] == [
        {"role": "user", "content": "首轮完整输入"},
        {"role": "user", "content": "服务已恢复，继续当前会话"},
    ]


@pytest.mark.parametrize(
    "exc_type,status_code",
    [
        (BadRequestError, 400),
        (AuthenticationError, 401),
        (PermissionDeniedError, 403),
        (NotFoundError, 404),
        (UnprocessableEntityError, 422),
    ],
)
def test_non_transient_4xx_is_never_retried(exc_type, status_code, monkeypatch):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [
            _status_error(
                exc_type,
                status_code,
                f"Error code: {status_code} - request rejected",
            ),
            '{"draft":must-not-run}',
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    with pytest.raises(ProtocolAgentCallError) as caught:
        transport.start(prompt="首轮完整输入")

    assert len(completions.calls) == 1
    assert sleeps == []
    assert caught.value.error_code == "SEMANTIC_CALL_FAILED"
    assert transport.history(caught.value.session_id) == (
        {"role": "user", "content": "首轮完整输入"},
    )


def test_timeout_is_never_retried_and_surfaces_transport_timeout(monkeypatch):
    sleeps: list[float] = []
    transport, completions = _glm_transport(
        [APITimeoutError(_authed_request()), '{"draft":must-not-run}'],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    with pytest.raises(ProtocolAgentCallError) as caught:
        transport.start(prompt="一个冻结分段")

    assert len(completions.calls) == 1
    assert sleeps == []
    assert caught.value.error_code == "TRANSPORT_TIMEOUT"


def test_retry_warnings_preserve_chinese_recovery_semantics(monkeypatch, caplog):
    sleeps: list[float] = []
    transport, _completions = _glm_transport(
        [
            _status_error(InternalServerError, 500, "Error code: 500 - internal error"),
            '{"draft":1}',
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    with caplog.at_level(
        logging.WARNING, logger="app.agents.protocol_semantic_transport"
    ):
        transport.start(prompt="首轮完整输入")

    assert "方案解构模型服务出现暂态传输错误" in caplog.text
    assert "第1/3次尝试" in caplog.text
    assert "重试" in caplog.text


def test_final_error_and_retry_logs_do_not_leak_credentials(monkeypatch, caplog):
    sleeps: list[float] = []
    # Every injected failure carries a request object whose Authorization
    # header holds the real credential, exactly like a live provider client.
    transport, completions = _glm_transport(
        [
            _status_error(InternalServerError, 500, "Error code: 500 - internal error"),
            _status_error(RateLimitError, 429, "Error code: 429 - rate limited"),
            APIConnectionError(request=_authed_request()),
        ],
        monkeypatch=monkeypatch,
        sleeps=sleeps,
    )

    with caplog.at_level(
        logging.WARNING, logger="app.agents.protocol_semantic_transport"
    ):
        with pytest.raises(ProtocolAgentCallError) as caught:
            transport.start(prompt="首轮完整输入")

    assert len(completions.calls) == 3
    assert SECRET_API_KEY not in str(caught.value)
    assert SECRET_API_KEY not in repr(caught.value)
    assert SECRET_API_KEY not in caplog.text
