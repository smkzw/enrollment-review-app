"""Deterministic regressions for the protocol-control actual-model identity gate.

These tests inject fake OpenAI-compatible clients/factories and never call a
live model.  They prove that mismatched, missing, ambiguous, or unprovable
service model identity fails closed with a Chinese diagnostic BEFORE any
semantic request is sent, and that a positively matched identity is accepted
and cached.  The mismatch fixture reuses the actually observed incident:
the service reported a Speed variant while the configured route is Quality.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents import protocol_control_discovery_transport as discovery_module
from app.agents.protocol_control_agent_transport import (
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlAgentCallError,
    ProtocolControlModelIdentityError,
    protocol_control_transport_from_model_config,
)
from app.agents.protocol_control_deconstructor import (
    CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME,
)
from app.agents.protocol_control_discovery_transport import (
    OpenAICompatibleProtocolControlDiscoveryAgentTransport,
)


QUALITY_MODEL = "mtplx-qwen38-27b-optimized-quality"
# Observed runtime evidence: /health reported this Speed variant while the
# configured protocol-control model is the Quality one.  Used only as a
# vocabulary-neutral two-distinct-names fixture; no clinical semantics here.
SPEED_MODEL = "pocketaihub-qwen3.8-27b-abliterated-mtplx-optimized-speed"


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='{"ok":true}'),
                )
            ]
        )


class _FakeModels:
    def __init__(
        self,
        model_ids: tuple[str, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.model_ids = list(model_ids)
        self.error = error
        self.list_calls = 0

    def list(self):
        self.list_calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            data=[SimpleNamespace(id=model_id) for model_id in self.model_ids]
        )


class _FakeServiceClient:
    """Fake OpenAI client exposing both /v1/models and chat completions."""

    def __init__(
        self,
        *,
        model_ids: tuple[str, ...] = (),
        models_error: Exception | None = None,
    ) -> None:
        self.models = _FakeModels(model_ids, error=models_error)
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def _factory_transport(
    model_ids: tuple[str, ...],
    *,
    model: str = QUALITY_MODEL,
    models_error: Exception | None = None,
):
    client = _FakeServiceClient(model_ids=model_ids, models_error=models_error)
    transport = OpenAICompatibleProtocolControlAgentTransport(
        backend="mtplx",
        model=model,
        max_tokens=16384,
        _client_factory=lambda **kwargs: client,
    )
    return transport, client


def test_mismatched_loaded_model_fails_closed_before_semantic_request() -> None:
    transport, client = _factory_transport((SPEED_MODEL,))

    with pytest.raises(ProtocolControlAgentCallError) as exc:
        transport.start(prompt="冻结控制输入")

    message = str(exc.value)
    assert "身份不一致" in message
    assert QUALITY_MODEL in message
    assert SPEED_MODEL in message
    # The semantic request must never leave the transport.
    assert client.chat.completions.calls == []
    assert client.models.list_calls == 1
    assert transport.verified_model_identity is None


def test_verified_identity_accepts_semantic_request_and_caches_probe() -> None:
    transport, client = _factory_transport((SPEED_MODEL, QUALITY_MODEL))

    first = transport.start(prompt="冻结控制输入")

    assert first.text == '{"ok":true}'
    assert first.session_id.startswith("protocol-control-chat-")
    assert transport.verified_model_identity == QUALITY_MODEL
    assert client.models.list_calls == 1
    assert len(client.chat.completions.calls) == 1

    transport.continue_session(session_id=first.session_id, prompt="同会话修复")
    # Verification is cached per transport; later calls do not re-probe.
    assert client.models.list_calls == 1
    assert len(client.chat.completions.calls) == 2


def test_missing_model_list_fails_closed() -> None:
    transport, client = _factory_transport(())

    with pytest.raises(ProtocolControlAgentCallError, match="身份缺证"):
        transport.start(prompt="冻结控制输入")

    assert client.chat.completions.calls == []


def test_probe_failure_fails_closed_without_semantic_request() -> None:
    transport, client = _factory_transport(
        (), models_error=ConnectionError("refused")
    )

    with pytest.raises(
        ProtocolControlAgentCallError, match="无法核实协议控制模型身份"
    ):
        transport.start(prompt="冻结控制输入")

    assert client.chat.completions.calls == []


def test_ambiguous_case_aliases_fail_closed() -> None:
    transport, client = _factory_transport(
        (
            "MTPLX-QWEN38-27B-OPTIMIZED-QUALITY",
            "Mtplx-Qwen38-27B-Optimized-Quality",
        )
    )

    with pytest.raises(ProtocolControlAgentCallError, match="身份歧义"):
        transport.start(prompt="冻结控制输入")

    assert client.chat.completions.calls == []


def test_exact_match_wins_over_case_alias_variants() -> None:
    transport, _client = _factory_transport(
        (QUALITY_MODEL, QUALITY_MODEL.upper())
    )

    assert transport.verify_model_identity() == QUALITY_MODEL


def test_typed_identity_error_carries_structured_evidence() -> None:
    transport, _client = _factory_transport((SPEED_MODEL,))

    with pytest.raises(ProtocolControlModelIdentityError) as exc:
        transport.verify_model_identity(force=True)

    assert exc.value.reason == "mismatch"
    assert exc.value.configured_model == QUALITY_MODEL
    assert exc.value.served_model_ids == (SPEED_MODEL,)


def test_verify_preflight_and_force_reprobe_after_service_swap() -> None:
    transport, client = _factory_transport((QUALITY_MODEL,))

    assert transport.verify_model_identity() == QUALITY_MODEL

    client.models.model_ids = [SPEED_MODEL]
    with pytest.raises(ProtocolControlModelIdentityError, match="身份不一致"):
        transport.verify_model_identity(force=True)
    # A failed forced re-probe must not corrupt the cached verified identity.
    assert transport.verified_model_identity == QUALITY_MODEL


def test_injected_client_forcing_identity_check_requires_probe_support() -> None:
    completions = _FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    with pytest.raises(ValueError, match="不支持 /v1/models"):
        OpenAICompatibleProtocolControlAgentTransport(
            client=fake_client,
            backend="mtplx",
            model=QUALITY_MODEL,
            model_identity_check=True,
        )
    assert completions.calls == []


def test_injected_client_defaults_to_opt_in_gate_for_deterministic_tests() -> None:
    completions = _FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=fake_client,
        backend="mtplx",
        model=QUALITY_MODEL,
        max_tokens=16384,
    )

    assert transport.model_identity_verification_enabled is False
    response = transport.start(prompt="冻结控制输入")
    assert response.text == '{"ok":true}'
    assert len(completions.calls) == 1


def test_injected_client_with_probe_callable_enforces_identity_gate() -> None:
    completions = _FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=fake_client,
        backend="mtplx",
        model=QUALITY_MODEL,
        model_identity_check=True,
        model_identity_probe=lambda: [SPEED_MODEL],
    )

    with pytest.raises(ProtocolControlAgentCallError, match="身份不一致"):
        transport.start(prompt="冻结控制输入")
    assert completions.calls == []


def test_model_config_factory_keeps_auto_identity_gate() -> None:
    client = _FakeServiceClient(model_ids=(QUALITY_MODEL,))

    transport = protocol_control_transport_from_model_config(
        {
            "provider": "mtplx",
            "model": QUALITY_MODEL,
            "reasoning_effort": "medium",
            "parameters": {
                "max_tokens": 60000,
                "temperature": 0.0,
                "base_url": "http://127.0.0.1:8002",
            },
        },
        _client_factory=lambda **kwargs: client,
    )

    assert transport.model_identity_verification_enabled is True
    assert transport.verify_model_identity() == QUALITY_MODEL
    assert len(client.chat.completions.calls) == 0


def test_discovery_transport_inherits_identity_gate(monkeypatch) -> None:
    service = _FakeServiceClient(model_ids=(SPEED_MODEL,))

    class _FactoryOpenAI:
        def __init__(self, **kwargs):
            self.models = service.models
            self.chat = service.chat

    monkeypatch.setattr(discovery_module, "OpenAI", _FactoryOpenAI)
    transport = OpenAICompatibleProtocolControlDiscoveryAgentTransport(
        backend="mtplx",
        model=QUALITY_MODEL,
    )

    assert transport.model_identity_verification_enabled is True
    with pytest.raises(ProtocolControlAgentCallError, match="身份不一致"):
        transport.start(prompt="冻结发现输入")
    assert service.chat.completions.calls == []


def test_discovery_transport_accepts_verified_identity(monkeypatch) -> None:
    service = _FakeServiceClient(model_ids=(QUALITY_MODEL,))

    class _FactoryOpenAI:
        def __init__(self, **kwargs):
            self.models = service.models
            self.chat = service.chat

    monkeypatch.setattr(discovery_module, "OpenAI", _FactoryOpenAI)
    transport = OpenAICompatibleProtocolControlDiscoveryAgentTransport(
        backend="mtplx",
        model=QUALITY_MODEL,
    )

    response = transport.start(prompt="冻结发现输入")

    assert response.session_id.startswith("protocol-control-chat-")
    assert transport.verified_model_identity == QUALITY_MODEL
    assert (
        service.chat.completions.calls[0]["response_format"]["json_schema"]["name"]
        == CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME
    )
