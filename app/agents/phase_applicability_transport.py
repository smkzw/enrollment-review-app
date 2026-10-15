"""Real OpenAI-compatible transport for phase-applicability semantics.

The phase-applicability Agent contract is deliberately provider-neutral.  This
module is the runtime adapter at that boundary: it sends the already rendered
prompt to an OpenAI-compatible chat endpoint, keeps one logical conversation
for bounded repairs, and exposes enough history for a durable caller to
restore a stateless transport after a process restart.

No domain identity is accepted from the model here.  Parsing, source
hydration, and the publication gate remain in :mod:`app.agents.phase_applicability`
and :mod:`app.protocols.phase_applicability`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

import httpx
from openai import OpenAI

from app.agents.phase_applicability import (
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentTransport,
    phase_applicability_agent_response_format,
)
from app.config import (
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_GLM_API_KEY,
    DECONSTRUCT_GLM_BASE_URL,
    DECONSTRUCT_MAX_TOKENS,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    MTPLX_API_KEY,
    MTPLX_BASE_URL,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
    OMLX_API_KEY,
    OMLX_BASE_URL,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
)
from app.llm.provider_profiles import (
    REMOTE_OPENAI_PROVIDERS,
    provider_default_headers,
    resolve_openai_connection,
)


__all__ = [
    "ConfiguredPhaseApplicabilityAgentTransport",
    "OpenAICompatiblePhaseApplicabilityAgentTransport",
    "OpenAICompatiblePhaseApplicabilityTransport",
    "PHASE_APPLICABILITY_BACKEND",
    "PHASE_APPLICABILITY_MAX_TOKENS",
    "PHASE_APPLICABILITY_MODEL",
    "PHASE_APPLICABILITY_REASONING_EFFORT",
    "PhaseApplicabilityAgentResponse",
    "PhaseApplicabilityAgentTransport",
    "PhaseApplicabilityAgentModelTransport",
    "PhaseApplicabilityAgentCallError",
    "PhaseApplicabilityModelTransport",
    "phase_applicability_agent_transport_from_environment",
    "phase_applicability_agent_transport_from_model_config",
    "phase_applicability_transport_from_config",
    "phase_applicability_transport_from_environment",
    "phase_applicability_transport_from_model_config",
]


_LOCAL_BACKENDS = frozenset(
    {"omlx", "local-omlx", "mtplx", "mtplx-api"}
)
_DEFAULT_TIMEOUT_SECONDS = 600.0
_DEFAULT_MAX_TOKENS = 8192
_SUPPORTED_REASONING_EFFORTS = frozenset(
    {"", "default", "auto", "low", "medium", "high", "xhigh", "max"}
)
PHASE_APPLICABILITY_BACKEND = os.getenv(
    "PHASE_APPLICABILITY_BACKEND", DECONSTRUCT_BACKEND
).strip().lower()
PHASE_APPLICABILITY_MODEL = os.getenv(
    "PHASE_APPLICABILITY_MODEL", DECONSTRUCT_MODEL
).strip()
PHASE_APPLICABILITY_REASONING_EFFORT = os.getenv(
    "PHASE_APPLICABILITY_REASONING_EFFORT", DECONSTRUCT_REASONING_EFFORT
).strip().lower()
PHASE_APPLICABILITY_MAX_TOKENS = int(
    os.getenv("PHASE_APPLICABILITY_MAX_TOKENS", str(DECONSTRUCT_MAX_TOKENS))
)


def _with_v1_suffix(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("模型服务 base_url 不能为空")
    return normalized if normalized.endswith(("/v1", "/paas/v4")) else normalized + "/v1"


def _configured_value(name: str, fallback: str) -> str:
    value = os.getenv(name)
    return fallback if value is None else value


class PhaseApplicabilityAgentCallError(RuntimeError):
    """A transport failure retaining the logical session identity."""

    def __init__(self, session_id: str, message: str) -> None:
        self.session_id = session_id
        super().__init__(message)


class OpenAICompatiblePhaseApplicabilityAgentTransport:
    """Provider-neutral synchronous transport for the phase Agent.

    ``backend`` is only a connection profile label.  It does not select a
    clinical rule set or change the wire contract.  Callers may pass any
    OpenAI-compatible client directly through ``client``; when no client is
    supplied, ``omlx``/``local-omlx`` use the configured local endpoint and
    all other labels use the configured remote-compatible endpoint.
    """

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
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 0,
    ) -> None:
        selected_backend = (
            backend or provider or PHASE_APPLICABILITY_BACKEND
        ).strip().lower()
        if not selected_backend:
            raise ValueError("模型服务 backend/provider 不能为空")
        selected_model = (
            model if model is not None else PHASE_APPLICABILITY_MODEL
        ).strip()
        if not selected_model:
            raise ValueError("期别语义模型不能为空")
        selected_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else PHASE_APPLICABILITY_REASONING_EFFORT
        ).strip().lower()
        if selected_effort not in _SUPPORTED_REASONING_EFFORTS:
            raise ValueError("reasoning_effort 不是受支持的推理强度")
        if (
            selected_backend in {"glm", "zhipu-coding-plan"}
            or selected_model.lower().startswith("glm-")
        ) and selected_effort not in {"low", "high", "max"}:
            raise ValueError("GLM 连接不支持指定的推理强度")
        selected_max_tokens = (
            max_tokens if max_tokens is not None else PHASE_APPLICABILITY_MAX_TOKENS
        )
        if isinstance(selected_max_tokens, bool) or selected_max_tokens < _DEFAULT_MAX_TOKENS:
            raise ValueError("期别语义模型输出上限不能低于 8192 tokens")
        if selected_backend in _LOCAL_BACKENDS:
            local_cap = (
                MTPLX_PROTOCOL_BATCH_MAX_TOKENS
                if selected_backend in {"mtplx", "mtplx-api"}
                else OMLX_PROTOCOL_BATCH_MAX_TOKENS
            )
            if selected_max_tokens > local_cap:
                raise ValueError("期别语义输出额度超过本地服务配置上限，不能静默降低")
            if selected_max_tokens < _DEFAULT_MAX_TOKENS:
                raise ValueError("本地期别语义批次输出上限不能低于 8192 tokens")
        if timeout <= 0:
            raise ValueError("模型服务 timeout 必须为正数")
        if max_retries < 0:
            raise ValueError("模型服务 max_retries 不能为负数")
        if temperature is not None and not 0 <= temperature <= 2:
            raise ValueError("模型服务 temperature 必须在 0 到 2 之间")

        self._backend = selected_backend
        self._provider = (provider or selected_backend).strip()
        self._model = selected_model
        self._reasoning_effort = selected_effort
        self._max_tokens = selected_max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._response_format = (
            dict(response_format) if response_format is not None else None
        )
        self._histories: dict[str, list[dict[str, str]]] = {}

        if client is not None:
            self._base_url = _with_v1_suffix(base_url) if base_url else "injected"
            self._client = client
            return

        is_local = selected_backend in _LOCAL_BACKENDS
        selected_base_url = base_url
        if selected_base_url is None:
            if is_local:
                if selected_backend in {"mtplx", "mtplx-api"}:
                    selected_base_url = _configured_value(
                        "MTPLX_BASE_URL", MTPLX_BASE_URL
                    )
                else:
                    selected_base_url = _configured_value(
                        "OMLX_BASE_URL", OMLX_BASE_URL
                    )
            elif selected_backend in {"deepseek", "deepseek-api"}:
                selected_base_url = _configured_value(
                    "DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL
                )
            elif selected_backend in {"glm", "zhipu-coding-plan"}:
                selected_base_url = _configured_value("DECONSTRUCT_GLM_BASE_URL", DECONSTRUCT_GLM_BASE_URL)
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                selected_base_url, _ = resolve_openai_connection(
                    selected_backend,
                    base_url=base_url,
                    api_key=api_key,
                    role_base_url_env="PHASE_APPLICABILITY_BASE_URL",
                    role_api_key_env="PHASE_APPLICABILITY_API_KEY",
                )
            else:
                selected_base_url = os.getenv("PHASE_APPLICABILITY_BASE_URL", "")
        selected_api_key = api_key
        if selected_api_key is None:
            if is_local:
                if selected_backend in {"mtplx", "mtplx-api"}:
                    selected_api_key = _configured_value(
                        "MTPLX_API_KEY", MTPLX_API_KEY
                    )
                else:
                    selected_api_key = _configured_value(
                        "OMLX_API_KEY", OMLX_API_KEY
                    )
            elif selected_backend in {"deepseek", "deepseek-api"}:
                selected_api_key = _configured_value(
                    "DEEPSEEK_API_KEY", DEEPSEEK_API_KEY
                )
            elif selected_backend in {"glm", "zhipu-coding-plan"}:
                selected_api_key = _configured_value("DECONSTRUCT_GLM_API_KEY", DECONSTRUCT_GLM_API_KEY)
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                _, selected_api_key = resolve_openai_connection(
                    selected_backend,
                    base_url=selected_base_url,
                    api_key=api_key,
                    role_base_url_env="PHASE_APPLICABILITY_BASE_URL",
                    role_api_key_env="PHASE_APPLICABILITY_API_KEY",
                )
            else:
                selected_api_key = os.getenv("PHASE_APPLICABILITY_API_KEY", "")
        if is_local:
            selected_api_key = selected_api_key or (
                "local-mtplx"
                if selected_backend in {"mtplx", "mtplx-api"}
                else "local-omlx"
            )
        elif not selected_api_key:
            raise ValueError("远程模型服务尚未配置 api_key")

        client_options: dict[str, Any] = {
            "base_url": _with_v1_suffix(selected_base_url),
            "api_key": selected_api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        default_headers = provider_default_headers(
            selected_backend,
            session_id=f"enrollment-review-phase:{uuid4().hex}",
        )
        if default_headers is not None:
            client_options["default_headers"] = default_headers
        if is_local:
            # A local inference server must not inherit a system proxy.  The
            # caller can still inject a test or custom client explicitly.
            client_options["http_client"] = httpx.Client(trust_env=False)
        self._base_url = str(client_options["base_url"])
        self._client = OpenAI(**client_options)

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def reasoning_effort(self) -> str:
        return self._reasoning_effort

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def temperature(self) -> float | None:
        return self._effective_temperature()

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def response_format_sha256(self) -> str:
        payload = json.dumps(
            self._effective_response_format(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def uses_structured_response_format(self) -> bool:
        return self._response_format is not None or self._backend in _LOCAL_BACKENDS

    def _effective_response_format(self) -> Mapping[str, Any]:
        if self._response_format is not None:
            return self._response_format
        if self._backend in _LOCAL_BACKENDS:
            return phase_applicability_agent_response_format()
        return {"type": "json_object"}

    def _effective_temperature(self) -> float | None:
        return self._temperature

    def _completion_kwargs(
        self,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "response_format": self._effective_response_format(),
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._reasoning_effort not in {"", "default", "auto"}:
            kwargs["reasoning_effort"] = self._reasoning_effort
        if self._backend in {"mtplx", "mtplx-api"}:
            kwargs["extra_body"] = {"generation_mode": "ar"}
        return kwargs

    @staticmethod
    def _message_text(completion: Any) -> str:
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ValueError("模型响应缺少 choices")
        message = getattr(choices[0], "message", None)
        text = getattr(message, "content", None) if message is not None else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("模型响应缺少可读取的 JSON 正文")
        return text.strip()

    def _complete(self, messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        request_messages = [dict(message) for message in messages]
        diagnostics: list[str] = []
        request_budget = self._max_tokens
        for attempt in range(2):
            try:
                kwargs = self._completion_kwargs(request_messages)
                kwargs["max_tokens"] = request_budget
                from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

                with sync_mtplx_model_session(
                    self._backend, str(getattr(self._client, "base_url", "")),
                    self._model, self._reasoning_effort,
                ):
                    completion = self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 - external adapter boundary
                raise RuntimeError(f"模型请求失败：{type(exc).__name__}: {exc}") from exc
            choices = getattr(completion, "choices", None) or []
            finish_reason = getattr(choices[0], "finish_reason", None) if choices else None
            if finish_reason == "length":
                diagnostics.append(f"第{attempt + 1}次输出达到长度上限")
                if attempt == 0:
                    retry_budget = min(request_budget * 2, 131072)
                    if self._backend in _LOCAL_BACKENDS:
                        local_cap = MTPLX_PROTOCOL_BATCH_MAX_TOKENS if self._backend in {"mtplx", "mtplx-api"} else OMLX_PROTOCOL_BATCH_MAX_TOKENS
                        retry_budget = min(retry_budget, local_cap)
                    if retry_budget <= request_budget:
                        break
                    request_budget = retry_budget
                    partial = ""
                    message = getattr(choices[0], "message", None) if choices else None
                    content = getattr(message, "content", None)
                    if isinstance(content, str) and content:
                        partial = content
                    request_messages = [
                        *request_messages,
                        *([{"role": "assistant", "content": partial}] if partial else []),
                        {
                            "role": "user",
                            "content": (
                                "上一请求的 JSON 输出达到长度上限，正文不可用。"
                                "请不要重复分析，立即按原冻结输入和指定 Schema 输出完整 JSON；"
                                "不要附加解释。"
                            ),
                        },
                    ]
                    continue
                continue
            try:
                return self._message_text(completion), request_messages
            except ValueError as exc:
                diagnostics.append(
                    f"第{attempt + 1}次结束原因={finish_reason or '未提供'}：{exc}"
                )
                if attempt == 0:
                    request_messages = [
                        *request_messages,
                        {
                            "role": "user",
                            "content": (
                                "上一请求未返回可读取的完整 JSON 对象。请不要重复分析，"
                                "立即按原冻结输入和指定 Schema 输出完整 JSON；不要附加解释。"
                            ),
                        },
                    ]
                    continue
        raise RuntimeError("模型连续两次未返回可读取的 JSON 正文：" + "；".join(diagnostics))

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        if not prompt.strip():
            raise ValueError("期别语义 Agent prompt 不能为空")
        session_id = f"phase-applicability-chat-{uuid4().hex}"
        history = [{"role": "user", "content": prompt}]
        try:
            text, request_history = self._complete(history)
        except Exception as exc:  # noqa: BLE001 - external adapter boundary
            raise PhaseApplicabilityAgentCallError(session_id, str(exc)) from exc
        self._histories[session_id] = [
            *request_history,
            {"role": "assistant", "content": text},
        ]
        return PhaseApplicabilityAgentResponse(session_id=session_id, text=text)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        if not prompt.strip():
            raise ValueError("期别语义 Agent 修复 prompt 不能为空")
        history = self._histories.get(session_id)
        if history is None:
            raise PhaseApplicabilityAgentCallError(
                session_id,
                "找不到原期别语义 Agent 会话，不能脱离上下文继续修复",
            )
        request_history = [*history, {"role": "user", "content": prompt}]
        try:
            text, used_history = self._complete(request_history)
        except Exception as exc:  # noqa: BLE001 - external adapter boundary
            raise PhaseApplicabilityAgentCallError(session_id, str(exc)) from exc
        self._histories[session_id] = [
            *used_history,
            {"role": "assistant", "content": text},
        ]
        return PhaseApplicabilityAgentResponse(session_id=session_id, text=text)

    def restore_history(
        self,
        *,
        session_id: str,
        messages: Sequence[Mapping[str, str]],
    ) -> None:
        """Restore an alternating user/assistant history after restart."""

        if not session_id.strip():
            raise ValueError("恢复期别语义 Agent 会话必须有 session_id")
        if session_id in self._histories:
            raise ValueError("期别语义 Agent 会话已存在，不能覆盖")
        history = [dict(message) for message in messages]
        if not history or history[0].get("role") != "user":
            raise ValueError("持久会话必须从 user 消息开始")
        expected_role = "user"
        for message in history:
            if set(message) != {"role", "content"}:
                raise ValueError("持久会话消息必须仅包含 role 与 content")
            if message["role"] != expected_role or not message["content"].strip():
                raise ValueError("持久会话角色顺序或正文无效")
            expected_role = "assistant" if expected_role == "user" else "user"
        if history[-1]["role"] != "assistant":
            raise ValueError("只能从已有模型响应的完整会话恢复")
        self._histories[session_id] = history

    def history(self, session_id: str) -> tuple[Mapping[str, str], ...]:
        if session_id not in self._histories:
            raise PhaseApplicabilityAgentCallError(
                session_id,
                "找不到期别语义 Agent 会话",
            )
        return tuple(dict(message) for message in self._histories[session_id])


# Descriptive aliases keep the adapter discoverable without making callers
# depend on a provider-specific class name.
OpenAICompatiblePhaseApplicabilityTransport = (
    OpenAICompatiblePhaseApplicabilityAgentTransport
)
ConfiguredPhaseApplicabilityAgentTransport = (
    OpenAICompatiblePhaseApplicabilityAgentTransport
)
PhaseApplicabilityModelTransport = OpenAICompatiblePhaseApplicabilityAgentTransport


def phase_applicability_transport_from_environment(
    **overrides: Any,
) -> OpenAICompatiblePhaseApplicabilityAgentTransport:
    """Build the configured real transport without selecting a hidden fallback."""

    return OpenAICompatiblePhaseApplicabilityAgentTransport(**overrides)


def phase_applicability_transport_from_model_config(
    model_config: Mapping[str, Any] | Any,
    **overrides: Any,
) -> OpenAICompatiblePhaseApplicabilityAgentTransport:
    """Build from a frozen provider/model config while preserving its identity.

    The helper accepts the project's ``ModelConfigContract`` as well as a
    plain mapping so the execution service does not need to own persistence or
    a provider registry.  Explicit call-site overrides are useful for an
    isolated acceptance endpoint and never silently replace the configured
    model unless the caller supplies the replacement.
    """

    def read(name: str, default: Any = None) -> Any:
        if isinstance(model_config, Mapping):
            return model_config.get(name, default)
        return getattr(model_config, name, default)

    parameters = read("parameters", {}) or {}
    if not isinstance(parameters, Mapping):
        raise ValueError("期别语义模型 parameters 必须为对象")
    selected_provider = read("provider") or read("backend")
    if not isinstance(selected_provider, str) or not selected_provider.strip():
        raise ValueError("期别语义模型 provider/backend 不能为空")
    selected_model = read("model")
    if not isinstance(selected_model, str) or not selected_model.strip():
        raise ValueError("期别语义模型 model 不能为空")
    values: dict[str, Any] = {
        "backend": selected_provider,
        "provider": selected_provider,
        "model": selected_model,
        "reasoning_effort": read("reasoning_effort"),
        "max_tokens": parameters.get("max_tokens"),
        "temperature": parameters.get("temperature"),
        "base_url": parameters.get("base_url"),
    }
    values.update({key: value for key, value in overrides.items() if value is not None})
    return OpenAICompatiblePhaseApplicabilityAgentTransport(
        **{key: value for key, value in values.items() if value is not None}
    )


PhaseApplicabilityAgentModelTransport = OpenAICompatiblePhaseApplicabilityAgentTransport
phase_applicability_transport_from_config = phase_applicability_transport_from_model_config
phase_applicability_agent_transport_from_model_config = (
    phase_applicability_transport_from_model_config
)
phase_applicability_agent_transport_from_environment = (
    phase_applicability_transport_from_environment
)
