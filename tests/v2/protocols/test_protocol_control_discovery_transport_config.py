"""Config regressions for the protocol-control discovery transport route.

Covers the GLM Coding Plan connection profile (paas/v4 preserved, no system
proxy, credential required), explicit budget caps that fail closed instead of
silently shrinking, and sampling defaults that keep provider behavior unless
explicitly configured. No live model calls.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents import protocol_control_discovery_transport as discovery_module
from app.agents.protocol_control_deconstructor import (
    CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME,
)


_BIGMODEL_CODING_PLAN_URL = "https://open.bigmodel.cn/api/coding/paas/v4"


class _RecordingOpenAI:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)
        # Identity gate probe capability, mirroring a real OpenAI client.
        self.models = SimpleNamespace(list=lambda: SimpleNamespace(data=[]))


class _RecordingHTTPClient:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.calls.append(kwargs)


def test_discovery_glm_backend_resolves_coding_plan_connection(monkeypatch) -> None:
    _RecordingOpenAI.calls.clear()
    _RecordingHTTPClient.calls.clear()
    monkeypatch.setattr(discovery_module, "OpenAI", _RecordingOpenAI)
    monkeypatch.setattr(discovery_module.httpx, "Client", _RecordingHTTPClient)
    monkeypatch.setattr(
        discovery_module,
        "PROTOCOL_CONTROL_DISCOVERY_BACKEND",
        "zhipu-coding-plan",
    )
    monkeypatch.setattr(
        discovery_module, "PROTOCOL_CONTROL_DISCOVERY_MODEL", "glm-5.3-flash"
    )
    monkeypatch.setattr(
        discovery_module, "PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT", "high"
    )
    monkeypatch.setattr(
        discovery_module, "PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS", 65536
    )
    monkeypatch.setattr(
        discovery_module,
        "PROTOCOL_CONTROL_GLM_BASE_URL",
        f"{_BIGMODEL_CODING_PLAN_URL}/",
    )
    monkeypatch.setattr(discovery_module, "PROTOCOL_CONTROL_GLM_API_KEY", "glm-key")

    transport = discovery_module.protocol_control_discovery_transport_from_environment()

    # Coding Plan .../paas/v4 路径原样保留，不追加 /v1；直连不走系统代理。
    assert _RecordingOpenAI.calls[0]["base_url"] == _BIGMODEL_CODING_PLAN_URL
    assert _RecordingOpenAI.calls[0]["api_key"] == "glm-key"
    assert _RecordingHTTPClient.calls == [{"trust_env": False}]
    assert transport.backend == "zhipu-coding-plan"
    assert transport.model == "glm-5.3-flash"
    assert transport.reasoning_effort == "high"
    assert transport.max_tokens == 65536


def test_discovery_uses_discovery_schema_and_provider_sampling_defaults() -> None:
    transport = discovery_module.OpenAICompatibleProtocolControlDiscoveryAgentTransport(
        client=object(),
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        api_key="glm-key",
        max_tokens=65536,
    )

    assert transport.uses_discovery_response_format is True
    assert transport.uses_control_response_format is False
    kwargs = transport._completion_kwargs([{"role": "user", "content": "发现"}])
    assert kwargs["response_format"]["json_schema"]["name"] == (
        CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME
    )
    assert "temperature" not in kwargs
    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled", "clear_thinking": False}
    }


def test_discovery_explicit_budget_above_cap_fails_without_silent_shrink(
    monkeypatch,
) -> None:
    monkeypatch.setattr(discovery_module, "MTPLX_PROTOCOL_BATCH_MAX_TOKENS", 16384)

    with pytest.raises(ValueError, match="不会静默压缩显式请求"):
        discovery_module.OpenAICompatibleProtocolControlDiscoveryAgentTransport(
            client=object(),
            backend="mtplx",
            model="mtplx-flash-next-optimized-speed",
            max_tokens=32768,
        )
