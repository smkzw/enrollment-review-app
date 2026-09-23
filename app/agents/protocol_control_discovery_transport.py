"""Strict OpenAI-compatible transport for protocol-control discovery.

Discovery is a separate model contract from deep protocol-control semantic
analysis.  The adapter reuses the connection implementation only; it always
replaces the response format with the discovery-only Schema and never falls
back to the deep-control or official IN/EX contracts.  It also inherits the
shared actual-model identity gate: the first semantic request is refused with
a Chinese diagnostic unless the configured discovery model positively matches
the model ids the service reports via ``/v1/models``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx
from openai import OpenAI

from app.agents.protocol_control_agent_transport import (
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlAgentCallError,
    ProtocolControlModelIdentityError,
    PROTOCOL_CONTROL_GLM_API_KEY,
    PROTOCOL_CONTROL_GLM_BASE_URL,
)
from app.llm.provider_profiles import REMOTE_OPENAI_PROVIDERS, resolve_openai_connection
from app.agents.protocol_control_deconstructor import (
    CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME,
    ProtocolControlDiscoveryAgentResponse,
    ProtocolControlDiscoveryAgentTransport,
    protocol_control_discovery_agent_json_schema,
    protocol_control_discovery_agent_response_format,
)
from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    MTPLX_API_KEY,
    MTPLX_BASE_URL,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
    OMLX_API_KEY,
    OMLX_BASE_URL,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
    PROTOCOL_CONTROL_BACKEND,
    PROTOCOL_CONTROL_MAX_TOKENS,
    PROTOCOL_CONTROL_MODEL,
    PROTOCOL_CONTROL_REASONING_EFFORT,
)


__all__ = [
    "CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME",
    "ConfiguredProtocolControlDiscoveryAgentTransport",
    "OpenAICompatibleProtocolControlDiscoveryAgentTransport",
    "OpenAICompatibleProtocolControlDiscoveryTransport",
    "PROTOCOL_CONTROL_DISCOVERY_BACKEND",
    "PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS",
    "PROTOCOL_CONTROL_DISCOVERY_MODEL",
    "PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT",
    "ProtocolControlDiscoveryAgentCallError",
    "ProtocolControlDiscoveryAgentModelTransport",
    "ProtocolControlDiscoveryAgentResponse",
    "ProtocolControlDiscoveryAgentTransport",
    "ProtocolControlDiscoveryModelIdentityError",
    "ProtocolControlDiscoveryModelTransport",
    "protocol_control_discovery_agent_json_schema",
    "protocol_control_discovery_agent_response_format",
    "protocol_control_discovery_agent_transport_from_environment",
    "protocol_control_discovery_agent_transport_from_model_config",
    "protocol_control_discovery_transport_from_config",
    "protocol_control_discovery_transport_from_environment",
    "protocol_control_discovery_transport_from_model_config",
]


# Dedicated overrides preserve a deliberately independent discovery route while
# remaining compatible with deployments that only configure the control route.
PROTOCOL_CONTROL_DISCOVERY_BACKEND = os.getenv(
    "PROTOCOL_CONTROL_DISCOVERY_BACKEND", PROTOCOL_CONTROL_BACKEND
).strip().lower()
PROTOCOL_CONTROL_DISCOVERY_MODEL = os.getenv(
    "PROTOCOL_CONTROL_DISCOVERY_MODEL", PROTOCOL_CONTROL_MODEL
).strip()
PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT = os.getenv(
    "PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT",
    PROTOCOL_CONTROL_REASONING_EFFORT,
).strip().lower()
PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS = int(
    os.getenv(
        "PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS",
        str(PROTOCOL_CONTROL_MAX_TOKENS),
    )
)


_LOCAL_BACKENDS = frozenset({"omlx", "local-omlx", "mtplx", "mtplx-api"})
_MTPLX_BACKENDS = frozenset({"mtplx", "mtplx-api"})
_ZHIPU_BACKENDS = frozenset({"zhipu-coding-plan", "glm"})


def _connection_defaults(
    backend: str,
    *,
    base_url: str | None,
    api_key: str | None,
) -> tuple[str | None, str | None]:
    """Resolve discovery connection constants before shared setup."""

    if base_url is None:
        if backend in _MTPLX_BACKENDS:
            base_url = os.getenv("MTPLX_BASE_URL", MTPLX_BASE_URL)
        elif backend in {"omlx", "local-omlx"}:
            base_url = os.getenv("OMLX_BASE_URL", OMLX_BASE_URL)
        elif backend in {"deepseek", "deepseek-api"}:
            base_url = os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
        elif backend in _ZHIPU_BACKENDS:
            base_url = os.getenv(
                "PROTOCOL_CONTROL_DISCOVERY_GLM_BASE_URL",
                PROTOCOL_CONTROL_GLM_BASE_URL,
            )
        elif backend in REMOTE_OPENAI_PROVIDERS:
            base_url, _ = resolve_openai_connection(
                backend,
                base_url=base_url,
                api_key=api_key,
                role_base_url_env="PROTOCOL_CONTROL_DISCOVERY_BASE_URL",
                role_api_key_env="PROTOCOL_CONTROL_DISCOVERY_API_KEY",
            )
        else:
            base_url = os.getenv("PROTOCOL_CONTROL_DISCOVERY_BASE_URL", "")
    if api_key is None:
        if backend in _MTPLX_BACKENDS:
            api_key = os.getenv("MTPLX_API_KEY", MTPLX_API_KEY)
        elif backend in {"omlx", "local-omlx"}:
            api_key = os.getenv("OMLX_API_KEY", OMLX_API_KEY)
        elif backend in {"deepseek", "deepseek-api"}:
            api_key = os.getenv("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
        elif backend in _ZHIPU_BACKENDS:
            api_key = os.getenv(
                "PROTOCOL_CONTROL_DISCOVERY_GLM_API_KEY",
                PROTOCOL_CONTROL_GLM_API_KEY,
            )
        elif backend in REMOTE_OPENAI_PROVIDERS:
            _, api_key = resolve_openai_connection(
                backend,
                base_url=base_url,
                api_key=api_key,
                role_base_url_env="PROTOCOL_CONTROL_DISCOVERY_BASE_URL",
                role_api_key_env="PROTOCOL_CONTROL_DISCOVERY_API_KEY",
            )
        else:
            api_key = os.getenv("PROTOCOL_CONTROL_DISCOVERY_API_KEY", "")
    return base_url, api_key

def _assert_discovery_response_format(
    response_format: Mapping[str, Any],
) -> None:
    if response_format.get("type") != "json_schema":
        raise ValueError("协议控制发现传输必须使用严格 json_schema 响应格式")
    wrapper = response_format.get("json_schema")
    if not isinstance(wrapper, Mapping):
        raise ValueError("协议控制发现传输缺少 json_schema 包装")
    name = wrapper.get("name")
    if name != CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME:
        raise ValueError(
            "协议控制发现传输不得使用非发现 Schema："
            f"{name or '空值'}"
        )
    if wrapper.get("strict") is not True:
        raise ValueError("协议控制发现传输必须启用 strict Schema")
    schema = wrapper.get("schema")
    if not isinstance(schema, Mapping) or not schema:
        raise ValueError("协议控制发现传输缺少严格 Schema 正文")


class OpenAICompatibleProtocolControlDiscoveryAgentTransport(
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlDiscoveryAgentTransport,
):
    """Synchronous discovery transport with a discovery-only response Schema."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        backend: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: Mapping[str, Any] | None = None,
        response_format_mode: str | None = None,
        timeout: float = float(__import__("os").getenv("PROTOCOL_CONTROL_REQUEST_TIMEOUT", "1800")),
        max_retries: int = 0,
    ) -> None:
        selected_response_format = (
            dict(response_format)
            if response_format is not None
            else protocol_control_discovery_agent_response_format()
        )
        _assert_discovery_response_format(selected_response_format)
        selected_backend = (
            backend or provider or PROTOCOL_CONTROL_DISCOVERY_BACKEND
        ).strip().lower()
        selected_base_url = base_url
        selected_api_key = api_key
        if client is None:
            selected_base_url, selected_api_key = _connection_defaults(
                selected_backend,
                base_url=selected_base_url,
                api_key=selected_api_key,
            )
        selected_max_tokens = (
            max_tokens
            if max_tokens is not None
            else PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS
        )
        if (
            selected_backend in _LOCAL_BACKENDS
            and not isinstance(selected_max_tokens, bool)
        ):
            local_cap = (
                MTPLX_PROTOCOL_BATCH_MAX_TOKENS
                if selected_backend in _MTPLX_BACKENDS
                else OMLX_PROTOCOL_BATCH_MAX_TOKENS
            )
            if selected_max_tokens > local_cap:
                # Explicit requests above the platform cap fail closed; the
                # transport never silently shrinks an explicit budget.
                raise ValueError(
                    f"显式请求的发现输出预算 {selected_max_tokens} tokens 超过"
                    f"平台批次上限 {local_cap}；请调高上限或降低请求，"
                    "不会静默压缩显式请求。"
                )

        # The shared implementation owns only connection setup, history and
        # bounded transport retries.  This call supplies the discovery Schema
        # directly; the deep-control Schema is never sent or installed.
        super().__init__(
            client=client,
            backend=selected_backend,
            provider=provider,
            api_key=selected_api_key,
            base_url=selected_base_url,
            model=(
                model
                if model is not None
                else PROTOCOL_CONTROL_DISCOVERY_MODEL
            ),
            reasoning_effort=(
                reasoning_effort
                if reasoning_effort is not None
                else PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT
            ),
            max_tokens=selected_max_tokens,
            temperature=temperature,
            response_format=selected_response_format,
            response_format_mode=response_format_mode,
            timeout=timeout,
            max_retries=max_retries,
            _response_format_name=CONTROL_DISCOVERY_RESPONSE_FORMAT_NAME,
            _transport_label="协议控制发现传输",
            _schema_label="发现",
            _response_format_mode_env=(
                "PROTOCOL_CONTROL_DISCOVERY_RESPONSE_FORMAT_MODE"
            ),
            _client_factory=OpenAI,
            _http_client_factory=httpx.Client,
        )

    @property
    def uses_control_response_format(self) -> bool:
        """Discovery must never be reported as the deep-control contract."""

        return False

    @property
    def uses_discovery_response_format(self) -> bool:
        return True

    def start(self, *, prompt: str) -> ProtocolControlDiscoveryAgentResponse:
        response = super().start(prompt=prompt)
        return ProtocolControlDiscoveryAgentResponse.model_validate(
            response.model_dump(mode="json")
        )

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlDiscoveryAgentResponse:
        response = super().continue_session(
            session_id=session_id,
            prompt=prompt,
        )
        return ProtocolControlDiscoveryAgentResponse.model_validate(
            response.model_dump(mode="json")
        )


# Discoverable aliases avoid provider-specific call sites.
OpenAICompatibleProtocolControlDiscoveryTransport = (
    OpenAICompatibleProtocolControlDiscoveryAgentTransport
)
ConfiguredProtocolControlDiscoveryAgentTransport = (
    OpenAICompatibleProtocolControlDiscoveryAgentTransport
)
ProtocolControlDiscoveryModelTransport = (
    OpenAICompatibleProtocolControlDiscoveryAgentTransport
)
ProtocolControlDiscoveryAgentModelTransport = (
    OpenAICompatibleProtocolControlDiscoveryAgentTransport
)
ProtocolControlDiscoveryAgentCallError = ProtocolControlAgentCallError
ProtocolControlDiscoveryModelIdentityError = ProtocolControlModelIdentityError


def protocol_control_discovery_transport_from_environment(
    **overrides: Any,
) -> OpenAICompatibleProtocolControlDiscoveryAgentTransport:
    """Build the configured discovery transport without a hidden fallback."""

    return OpenAICompatibleProtocolControlDiscoveryAgentTransport(**overrides)


def protocol_control_discovery_transport_from_model_config(
    model_config: Mapping[str, Any] | Any,
    **overrides: Any,
) -> OpenAICompatibleProtocolControlDiscoveryAgentTransport:
    """Build from a frozen discovery provider/model configuration."""

    def read(name: str, default: Any = None) -> Any:
        if isinstance(model_config, Mapping):
            return model_config.get(name, default)
        return getattr(model_config, name, default)

    parameters = read("parameters", {}) or {}
    if not isinstance(parameters, Mapping):
        raise ValueError("协议控制发现模型 parameters 必须为对象")
    selected_provider = read("provider") or read("backend")
    if not isinstance(selected_provider, str) or not selected_provider.strip():
        raise ValueError("协议控制发现模型 provider/backend 不能为空")
    selected_model = read("model")
    if not isinstance(selected_model, str) or not selected_model.strip():
        raise ValueError("协议控制发现模型 model 不能为空")
    values: dict[str, Any] = {
        "backend": selected_provider,
        "provider": selected_provider,
        "model": selected_model,
        "reasoning_effort": read("reasoning_effort"),
        "max_tokens": parameters.get("max_tokens"),
        "temperature": parameters.get("temperature"),
        "response_format_mode": parameters.get("response_format_mode"),
        "base_url": parameters.get("base_url"),
    }
    values.update(
        {key: value for key, value in overrides.items() if value is not None}
    )
    return OpenAICompatibleProtocolControlDiscoveryAgentTransport(
        **{key: value for key, value in values.items() if value is not None}
    )


protocol_control_discovery_transport_from_config = (
    protocol_control_discovery_transport_from_model_config
)
protocol_control_discovery_agent_transport_from_model_config = (
    protocol_control_discovery_transport_from_model_config
)
protocol_control_discovery_agent_transport_from_environment = (
    protocol_control_discovery_transport_from_environment
)
