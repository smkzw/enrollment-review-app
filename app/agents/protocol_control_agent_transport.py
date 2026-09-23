"""OpenAI-compatible transport for other-protocol control Agent calls.

This adapter is deliberately separate from
:mod:`app.agents.protocol_semantic_transport`.  Official IN/EX deconstruction
uses a different strict response Schema and must never be silently reused for
protocol-control candidate drafts.

The product path follows the configured control route (currently the GLM
Coding Plan profile) with the configured reasoning effort, the provider's own
sampling defaults (no ``temperature`` is sent unless an explicit value is
configured), the configured control output budget, and
:func:`protocol_control_agent_response_format`.  Repair calls keep one
immutable local message history keyed by session_id; there is no provider-side
session and no silent semantic-model fallback.  In-call length/empty-body
retries stay ephemeral: ``history()`` exposes only logical user prompts and
final complete JSON so ``restore_history()`` can resume the same session.  A
length finish may raise the shared reasoning+content budget once, capped at
``PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS``.

Before the first semantic request the transport positively matches the
configured model against the model ids the service actually reports via
``/v1/models``. A CMS gateway that hides its catalog from a scoped key may
instead prove its identity with one non-clinical, minimal chat response whose
reported model must match exactly. Missing, ambiguous, or mismatched identity
still fails closed with a Chinese diagnostic; a
verified identity is cached per transport and can be re-checked with
:meth:`OpenAICompatibleProtocolControlAgentTransport.verify_model_identity`.
A ``model`` field inside an OpenAI request is never treated as proof that the
service loaded that model.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

import httpx
from openai import APITimeoutError, OpenAI

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentResponse,
    ProtocolControlAgentTransport,
    protocol_control_agent_response_format,
)
from app.config import (
    DECONSTRUCT_GLM_API_KEY,
    DECONSTRUCT_GLM_BASE_URL,
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
from app.llm.provider_profiles import (
    REMOTE_OPENAI_PROVIDERS,
    provider_default_headers,
    resolve_openai_connection,
    resolve_structured_response_mode,
)


__all__ = [
    "CONTROL_RESPONSE_FORMAT_NAME",
    "ConfiguredProtocolControlAgentTransport",
    "OpenAICompatibleProtocolControlAgentTransport",
    "OpenAICompatibleProtocolControlTransport",
    "PROTOCOL_CONTROL_BACKEND",
    "PROTOCOL_CONTROL_GLM_API_KEY",
    "PROTOCOL_CONTROL_GLM_BASE_URL",
    "PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS",
    "PROTOCOL_CONTROL_MAX_TOKENS",
    "PROTOCOL_CONTROL_MODEL",
    "PROTOCOL_CONTROL_REASONING_EFFORT",
    "ProtocolControlAgentCallError",
    "ProtocolControlAgentModelTransport",
    "ProtocolControlAgentResponse",
    "ProtocolControlAgentTransport",
    "ProtocolControlModelIdentityError",
    "ProtocolControlModelTransport",
    "protocol_control_agent_transport_from_environment",
    "protocol_control_agent_transport_from_model_config",
    "protocol_control_transport_from_config",
    "protocol_control_transport_from_environment",
    "protocol_control_transport_from_model_config",
]


CONTROL_RESPONSE_FORMAT_NAME = "protocol_control_agent_wire_v1"
_LOCAL_BACKENDS = frozenset({"omlx", "local-omlx", "mtplx", "mtplx-api"})
_MTPLX_BACKENDS = frozenset({"mtplx", "mtplx-api"})
_ZHIPU_BACKENDS = frozenset({"zhipu-coding-plan", "glm"})
_SUPPORTED_BACKENDS = frozenset(
    {
        "mtplx",
        "mtplx-api",
        "omlx",
        "local-omlx",
        "deepseek",
        "deepseek-api",
        "cms-router",
        "cms-smk",
        "opencode-go",
        *_ZHIPU_BACKENDS,
    }
)
_DEFAULT_TIMEOUT_SECONDS = 600.0
_DEFAULT_MAX_TOKENS = 8192
# A single length-finish retry may raise the shared reasoning+content budget
# once, up to this ceiling (R3 design §6.1); it is never raised silently twice.
PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS = 131072
_SUPPORTED_REASONING_EFFORTS = frozenset(
    {"", "default", "auto", "low", "medium", "high", "xhigh", "max"}
)
_SUPPORTED_GLM_CONTROL_REASONING_EFFORTS = frozenset({"low", "high", "max"})

# The GLM control route reuses the approved Coding Plan endpoint and the same
# BigModel credential chain as protocol-semantic deconstruction; a dedicated
# PROTOCOL_CONTROL_GLM_* override stays available and wins when configured.
PROTOCOL_CONTROL_GLM_BASE_URL = os.getenv(
    "PROTOCOL_CONTROL_GLM_BASE_URL", DECONSTRUCT_GLM_BASE_URL
).strip()
PROTOCOL_CONTROL_GLM_API_KEY = (
    os.getenv("PROTOCOL_CONTROL_GLM_API_KEY", "").strip() or DECONSTRUCT_GLM_API_KEY
)


def _with_v1_suffix(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("协议控制模型服务 base_url 不能为空")
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def _normalize_zhipu_coding_plan_base_url(base_url: str) -> str:
    """Keep Coding Plan ``.../paas/v4`` paths; do not append a stray ``/v1``."""

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("GLM 协议控制模型服务地址不能为空")
    if normalized.endswith("/v1") and "/paas/v4" in normalized:
        normalized = normalized[: -len("/v1")].rstrip("/")
    return normalized


def _map_glm_control_reasoning_effort(effort: str) -> str:
    """Resolve the control effort onto GLM's low/high/max vocabulary.

    An unsupported configured effort fails here instead of silently mapping
    down; an unset value resolves to the configured control default.
    """

    selected = str(effort or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = str(PROTOCOL_CONTROL_REASONING_EFFORT or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = "high"
    if selected not in _SUPPORTED_GLM_CONTROL_REASONING_EFFORTS:
        raise ValueError(
            "GLM 协议控制推理强度仅支持 low/high/max，"
            f"当前值={selected or '空值'}"
        )
    return selected


def _configured_value(name: str, fallback: str) -> str:
    value = os.getenv(name)
    return fallback if value is None else value


def _assert_control_response_format(
    response_format: Mapping[str, Any],
    *,
    expected_name: str = CONTROL_RESPONSE_FORMAT_NAME,
    transport_label: str = "协议控制传输",
    schema_label: str = "控制",
) -> None:
    """Reject a response Schema belonging to another semantic route."""

    if response_format.get("type") != "json_schema":
        raise ValueError(f"{transport_label}必须使用严格 json_schema 响应格式")
    wrapper = response_format.get("json_schema")
    if not isinstance(wrapper, Mapping):
        raise ValueError(f"{transport_label}缺少 json_schema 包装")
    name = wrapper.get("name")
    if name != expected_name:
        raise ValueError(
            f"{transport_label}不得使用非{schema_label} Schema：{name or '空值'}"
        )
    if wrapper.get("strict") is not True:
        raise ValueError(f"{transport_label}必须启用 strict Schema")
    schema = wrapper.get("schema")
    if not isinstance(schema, Mapping) or not schema:
        raise ValueError(f"{transport_label}缺少严格 Schema 正文")


class ProtocolControlModelIdentityError(RuntimeError):
    """配置模型与服务实际加载模型身份无法正向匹配时，拒绝执行语义请求。

    ``reason`` 固定取值：``disabled``（传输未启用身份校验）、``probe_failed``
    （无法从服务取得模型清单）、``missing``（服务未报告任何已加载模型）、
    ``mismatch``（服务报告的模型与配置模型不一致）、``ambiguous``（别名归一后
    匹配到多个不同模型）。
    """

    def __init__(
        self,
        message: str,
        *,
        configured_model: str,
        served_model_ids: Sequence[str] = (),
        reason: str,
    ) -> None:
        super().__init__(message)
        self.configured_model = configured_model
        self.served_model_ids = tuple(served_model_ids)
        self.reason = reason


def _client_supports_model_listing(client: Any) -> bool:
    return callable(getattr(getattr(client, "models", None), "list", None))


def _match_configured_control_model(
    configured_model: str,
    served_model_ids: Sequence[str],
) -> str:
    """Return the positively matched served model id, or fail closed.

    Exact equality wins.  Without an exact match, a single case-insensitive
    alias is tolerated; zero usable ids, more than one distinct alias, or no
    match at all must fail closed instead of silently calling another model.
    """

    ordered: list[str] = []
    for served_id in served_model_ids:
        if isinstance(served_id, str) and served_id.strip():
            normalized = served_id.strip()
            if normalized not in ordered:
                ordered.append(normalized)
    if not ordered:
        raise ProtocolControlModelIdentityError(
            "协议控制模型身份缺证，已拒绝执行语义请求："
            "服务未通过 /v1/models 报告任何已加载模型。",
            configured_model=configured_model,
            served_model_ids=served_model_ids,
            reason="missing",
        )
    exact = [served_id for served_id in ordered if served_id == configured_model]
    if len(exact) == 1:
        return exact[0]
    aliases = sorted(
        {served_id for served_id in ordered if served_id.lower() == configured_model.lower()}
    )
    if len(aliases) > 1:
        raise ProtocolControlModelIdentityError(
            "协议控制模型身份歧义，已拒绝执行语义请求：配置模型 "
            f"{configured_model} 与服务报告的多个不同别名 "
            f"{'、'.join(aliases)} 模糊匹配。",
            configured_model=configured_model,
            served_model_ids=ordered,
            reason="ambiguous",
        )
    if len(aliases) == 1:
        return aliases[0]
    raise ProtocolControlModelIdentityError(
        "协议控制模型身份不一致，已拒绝执行语义请求："
        f"配置模型为 {configured_model}，服务实际报告的模型为 "
        f"{'、'.join(ordered)}。请更正本地模型服务实际加载的模型或配置后再试，"
        "不得静默替换语义模型。",
        configured_model=configured_model,
        served_model_ids=ordered,
        reason="mismatch",
    )


class ProtocolControlAgentCallError(RuntimeError):
    """A transport failure retaining the logical session identity."""

    def __init__(
        self,
        session_id: str,
        message: str,
        *,
        uncertain_completion: bool = False,
    ) -> None:
        self.session_id = session_id
        self.uncertain_completion = uncertain_completion
        super().__init__(message)


class _ProtocolControlRequestTimeout(RuntimeError):
    """The client timed out while the serial local service may still be working."""


class OpenAICompatibleProtocolControlAgentTransport:
    """Synchronous OpenAI-compatible transport for protocol-control Agent runs.

    ``backend`` selects only the connection profile.  It never changes the
    control wire contract and never silently substitutes another semantic model
    when the selected backend fails.
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
        response_format_mode: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 0,
        model_identity_check: bool | None = None,
        model_identity_probe: Callable[[], Sequence[str]] | None = None,
        _response_format_name: str = CONTROL_RESPONSE_FORMAT_NAME,
        _response_format_factory: Callable[[], Mapping[str, Any]] | None = None,
        _transport_label: str = "协议控制传输",
        _schema_label: str = "控制",
        _response_format_mode_env: str = "PROTOCOL_CONTROL_RESPONSE_FORMAT_MODE",
        _client_factory: Callable[..., Any] | None = None,
        _http_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        selected_backend = (
            backend or provider or PROTOCOL_CONTROL_BACKEND
        ).strip().lower()
        if not selected_backend:
            raise ValueError("协议控制模型 backend/provider 不能为空")
        if selected_backend not in _SUPPORTED_BACKENDS:
            raise ValueError(
                f"当前其他方案控制任务不支持模型供应商 {selected_backend}"
            )
        selected_model = (
            model if model is not None else PROTOCOL_CONTROL_MODEL
        ).strip()
        if not selected_model:
            raise ValueError("协议控制模型不能为空")
        selected_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else PROTOCOL_CONTROL_REASONING_EFFORT
        ).strip().lower()
        if selected_effort not in _SUPPORTED_REASONING_EFFORTS:
            raise ValueError("reasoning_effort 不是受支持的推理强度")
        if selected_backend in _ZHIPU_BACKENDS or selected_model.lower().startswith("glm-"):
            # Fail before any request on an effort GLM does not support
            # (e.g. xhigh); never silently map it down.
            selected_effort = _map_glm_control_reasoning_effort(selected_effort)
        selected_max_tokens = (
            max_tokens if max_tokens is not None else PROTOCOL_CONTROL_MAX_TOKENS
        )
        if isinstance(selected_max_tokens, bool) or selected_max_tokens < _DEFAULT_MAX_TOKENS:
            raise ValueError("协议控制模型输出上限不能低于 8192 tokens")
        if selected_backend in _LOCAL_BACKENDS:
            local_cap = (
                MTPLX_PROTOCOL_BATCH_MAX_TOKENS
                if selected_backend in _MTPLX_BACKENDS
                else OMLX_PROTOCOL_BATCH_MAX_TOKENS
            )
            if selected_max_tokens > local_cap:
                # An explicitly requested budget above the configured platform
                # cap fails before any request; never silently min() shrink it.
                raise ValueError(
                    f"显式请求的协议控制输出预算 {selected_max_tokens} tokens 超过"
                    f"平台批次上限 {local_cap}；请调高上限或降低请求，"
                    "不会静默压缩显式请求。"
                )
            if selected_max_tokens < _DEFAULT_MAX_TOKENS:
                raise ValueError("本地协议控制批次输出上限不能低于 8192 tokens")
        if timeout <= 0:
            raise ValueError("模型服务 timeout 必须为正数")
        if max_retries < 0:
            raise ValueError("模型服务 max_retries 不能为负数")
        if temperature is not None and not 0 <= temperature <= 2:
            raise ValueError("模型服务 temperature 必须在 0 到 2 之间")

        if model_identity_check is None:
            # Auto policy: a transport that builds its own client must verify
            # the actually loaded model identity before any semantic request;
            # injected deterministic test clients stay opt-in.
            selected_identity_check = client is None
        else:
            selected_identity_check = bool(model_identity_check)
        if model_identity_probe is not None and not callable(model_identity_probe):
            raise ValueError("协议控制模型身份探测器必须是可调用对象")

        if response_format is None:
            selected_response_format = (
                _response_format_factory()
                if _response_format_factory is not None
                else protocol_control_agent_response_format()
            )
        else:
            selected_response_format = dict(response_format)
        _assert_control_response_format(
            selected_response_format,
            expected_name=_response_format_name,
            transport_label=_transport_label,
            schema_label=_schema_label,
        )

        self._backend = selected_backend
        self._output_budget_limit = (
            min(local_cap, PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS)
            if selected_backend in _LOCAL_BACKENDS
            else PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS
        )
        self._provider = (provider or selected_backend).strip()
        self._model = selected_model
        self._reasoning_effort = selected_effort
        self._max_tokens = selected_max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._response_format_name = _response_format_name
        self._response_format = selected_response_format
        self._response_format_mode = resolve_structured_response_mode(
            selected_backend,
            explicit=response_format_mode,
            env_name=_response_format_mode_env,
        )
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._model_identity_check = selected_identity_check
        self._model_identity_probe = model_identity_probe
        self._model_identity_verified: str | None = None

        if client is not None:
            self._base_url = _with_v1_suffix(base_url) if base_url else "injected"
            self._client = client
            self._assert_identity_probe_availability()
            return

        is_local = selected_backend in _LOCAL_BACKENDS
        selected_base_url = base_url
        if selected_base_url is None:
            if selected_backend in _MTPLX_BACKENDS:
                selected_base_url = _configured_value(
                    "MTPLX_BASE_URL", MTPLX_BASE_URL
                )
            elif selected_backend in {"omlx", "local-omlx"}:
                selected_base_url = _configured_value(
                    "OMLX_BASE_URL", OMLX_BASE_URL
                )
            elif selected_backend in {"deepseek", "deepseek-api"}:
                selected_base_url = _configured_value(
                    "DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL
                )
            elif selected_backend in _ZHIPU_BACKENDS:
                selected_base_url = _configured_value(
                    "PROTOCOL_CONTROL_GLM_BASE_URL", PROTOCOL_CONTROL_GLM_BASE_URL
                )
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                selected_base_url, _ = resolve_openai_connection(
                    selected_backend,
                    base_url=base_url,
                    api_key=api_key,
                    role_base_url_env="PROTOCOL_CONTROL_BASE_URL",
                    role_api_key_env="PROTOCOL_CONTROL_API_KEY",
                )
            else:
                selected_base_url = os.getenv("PROTOCOL_CONTROL_BASE_URL", "")
        selected_api_key = api_key
        if selected_api_key is None:
            if selected_backend in _MTPLX_BACKENDS:
                selected_api_key = _configured_value(
                    "MTPLX_API_KEY", MTPLX_API_KEY
                )
            elif selected_backend in {"omlx", "local-omlx"}:
                selected_api_key = _configured_value(
                    "OMLX_API_KEY", OMLX_API_KEY
                )
            elif selected_backend in {"deepseek", "deepseek-api"}:
                selected_api_key = _configured_value(
                    "DEEPSEEK_API_KEY", DEEPSEEK_API_KEY
                )
            elif selected_backend in _ZHIPU_BACKENDS:
                selected_api_key = _configured_value(
                    "PROTOCOL_CONTROL_GLM_API_KEY", PROTOCOL_CONTROL_GLM_API_KEY
                )
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                _, selected_api_key = resolve_openai_connection(
                    selected_backend,
                    base_url=selected_base_url,
                    api_key=api_key,
                    role_base_url_env="PROTOCOL_CONTROL_BASE_URL",
                    role_api_key_env="PROTOCOL_CONTROL_API_KEY",
                )
            else:
                selected_api_key = os.getenv("PROTOCOL_CONTROL_API_KEY", "")
        if is_local:
            selected_api_key = selected_api_key or (
                "local-mtplx"
                if selected_backend in _MTPLX_BACKENDS
                else "local-omlx"
            )
        elif not selected_api_key:
            raise ValueError("远程协议控制模型服务尚未配置 api_key")

        client_options: dict[str, Any] = {
            "base_url": (
                _normalize_zhipu_coding_plan_base_url(selected_base_url)
                if selected_backend in _ZHIPU_BACKENDS
                else _with_v1_suffix(selected_base_url)
            ),
            "api_key": selected_api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        default_headers = provider_default_headers(
            selected_backend,
            session_id=f"enrollment-review-protocol-control:{uuid4().hex}",
        )
        if default_headers is not None:
            client_options["default_headers"] = default_headers
        if is_local or selected_backend in _ZHIPU_BACKENDS:
            # Local inference and BigModel Coding Plan calls must never inherit
            # a system HTTP proxy (same rule as Independent VLM / semantic GLM).
            client_options["http_client"] = (
                _http_client_factory or httpx.Client
            )(trust_env=False)
        self._base_url = str(client_options["base_url"])
        self._client = (_client_factory or OpenAI)(**client_options)
        self._assert_identity_probe_availability()

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
    def model_identity_verification_enabled(self) -> bool:
        return self._model_identity_check

    @property
    def verified_model_identity(self) -> str | None:
        return self._model_identity_verified

    @property
    def model_identity_policy(self) -> str:
        return "list_then_chat_on_empty" if self._backend == "cms-router" else "list_only"

    @property
    def response_format_sha256(self) -> str:
        payload = json.dumps(
            self._response_format,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def uses_structured_response_format(self) -> bool:
        return True

    @property
    def response_format_mode(self) -> str:
        return self._response_format_mode

    @property
    def uses_control_response_format(self) -> bool:
        return True

    def _effective_temperature(self) -> float | None:
        # Provider sampling defaults apply unless an explicit temperature is
        # configured; an explicit 0.0 is honored as a real request value.
        return self._temperature

    def _assert_identity_probe_availability(self) -> None:
        if (
            self._model_identity_check
            and self._model_identity_probe is None
            and not _client_supports_model_listing(self._client)
        ):
            raise ValueError(
                "协议控制模型客户端不支持 /v1/models 模型清单探测，"
                "无法启用实际模型身份校验"
            )

    def _default_model_identity_probe(self) -> Sequence[str]:
        """Ask the OpenAI-compatible service which models it actually serves."""

        if not _client_supports_model_listing(self._client):
            raise ProtocolControlModelIdentityError(
                "协议控制模型客户端不支持 /v1/models 模型清单探测，"
                "无法核实实际模型身份。",
                configured_model=self._model,
                reason="probe_failed",
            )
        page = self._client.models.list()
        data = getattr(page, "data", None)
        if data is None and isinstance(page, (list, tuple)):
            data = page
        if data is None:
            raise ProtocolControlModelIdentityError(
                "模型清单响应缺少 data 字段，无法核实实际模型身份。",
                configured_model=self._model,
                reason="probe_failed",
            )
        ids: list[str] = []
        for item in data:
            if isinstance(item, Mapping):
                item_id = item.get("id")
            else:
                item_id = getattr(item, "id", None)
            if isinstance(item_id, str) and item_id.strip():
                ids.append(item_id.strip())
        if not ids and self._backend == "cms-router":
            # Scoped gateway keys can serve a model while exposing an empty
            # catalog. This probe contains no protocol or subject material.
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "只回答：好"}],
                max_tokens=32,
                stream=False,
            )
            reported = getattr(response, "model", None)
            if isinstance(reported, str) and reported.strip():
                ids.append(reported.strip())
        return ids

    def verify_model_identity(self, *, force: bool = False) -> str:
        from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

        with sync_mtplx_model_session(
            self._backend, str(getattr(self._client, "base_url", "")),
            self._model, self._reasoning_effort,
        ):
            return self._verify_model_identity(force=force)

    def _verify_model_identity(self, *, force: bool = False) -> str:
        """Positively match the configured model against the served models.

        The matched served id is cached per transport; ``force=True`` re-probes
        the service (used by smoke runners before a live run).  Mismatched,
        missing, or ambiguous identity raises
        :class:`ProtocolControlModelIdentityError` instead of continuing.
        """

        if self._model_identity_verified is not None and not force:
            return self._model_identity_verified
        if not self._model_identity_check:
            raise ProtocolControlModelIdentityError(
                "此传输未启用实际模型身份校验，不能声明已核实模型；"
                "仅确定性测试注入客户端时允许显式关闭。",
                configured_model=self._model,
                reason="disabled",
            )
        probe = self._model_identity_probe or self._default_model_identity_probe
        try:
            served_ids = list(probe())
        except ProtocolControlModelIdentityError:
            raise
        except Exception as exc:  # noqa: BLE001 - external service boundary
            raise ProtocolControlModelIdentityError(
                "无法核实协议控制模型身份，已拒绝执行语义请求："
                f"{type(exc).__name__}: {exc}",
                configured_model=self._model,
                reason="probe_failed",
            ) from exc
        matched = _match_configured_control_model(self._model, served_ids)
        self._model_identity_verified = matched
        return matched

    def _ensure_model_identity_verified(self) -> None:
        if not self._model_identity_check or self._model_identity_verified is not None:
            return
        self._verify_model_identity(force=True)

    def _completion_kwargs(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
        }
        if self._response_format_mode == "json_schema":
            kwargs["response_format"] = self._response_format
        elif self._response_format_mode == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._reasoning_effort not in {"", "default", "auto"}:
            kwargs["reasoning_effort"] = self._reasoning_effort
        if self._backend in _MTPLX_BACKENDS:
            kwargs["extra_body"] = {"generation_mode": "ar"}
        elif self._backend in _ZHIPU_BACKENDS:
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled", "clear_thinking": False}
            }
        return kwargs

    @staticmethod
    @staticmethod
    def _stream_completion(client: Any, kwargs: dict[str, Any]) -> Any:
        """全模型统一 streaming（2026-09-19 用户指令）：云路由器对非流式长生成
        有队列等待上限（OmniRoute 504）；流式按块保活即不受限。重组为下游
        已知的非流式响应对象；stream_options 不被支持时自动降级重试。"""
        from types import SimpleNamespace

        kwargs = dict(kwargs)
        kwargs["stream"] = True
        kwargs.setdefault("stream_options", {"include_usage": True})
        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as exc:
            if "stream_options" not in str(exc):
                raise
            kwargs.pop("stream_options", None)
            stream = client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        finish_reason: str | None = None
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
            delta = getattr(choice, "delta", None)
            piece = getattr(delta, "content", None) if delta is not None else None
            if piece:
                content_parts.append(piece)
        message = SimpleNamespace(content="".join(content_parts))
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=finish_reason or "未提供")]
        )

    @staticmethod
    def _message_text(completion: Any) -> str:
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ValueError("模型响应缺少 choices")
        message = getattr(choices[0], "message", None)
        text = getattr(message, "content", None) if message is not None else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("模型响应缺少可读取的 JSON 正文")
        stripped = text.strip()
        lines = stripped.splitlines()
        if (
            len(lines) >= 3
            and lines[0].strip().lower() in {"```json", "```"}
            and lines[-1].strip() == "```"
        ):
            return "\n".join(lines[1:-1]).strip()
        return stripped

    def _complete(self, messages: list[dict[str, str]]) -> str:
        from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

        with sync_mtplx_model_session(
            self._backend, str(getattr(self._client, "base_url", "")),
            self._model, self._reasoning_effort,
        ):
            return self._complete_owned(messages)

    def _complete_owned(self, messages: list[dict[str, str]]) -> str:
        """Run one logical completion, with ephemeral in-call retries.

        Length/empty-body repair turns are used only for the live request and
        must not be persisted into the externally restorable session history.
        Callers persist only the logical user prompt and the final JSON body.

        The actually loaded model identity must be positively matched before
        any semantic request leaves this transport.
        """

        self._ensure_model_identity_verified()
        request_messages = [dict(message) for message in messages]
        diagnostics: list[str] = []
        # One shared reasoning+content budget per logical request; a length
        # finish may raise it once, capped, and never a second time.
        request_budget = self._max_tokens
        for attempt in range(2):
            try:
                completion = self._stream_completion(
                    self._client,
                    self._completion_kwargs(request_messages, max_tokens=request_budget),
                )
            except (APITimeoutError, httpx.TimeoutException, TimeoutError) as exc:
                raise _ProtocolControlRequestTimeout(
                    f"协议控制模型请求超时：{type(exc).__name__}: {exc}"
                ) from exc
            except Exception as exc:  # noqa: BLE001 - external adapter boundary
                raise RuntimeError(
                    f"协议控制模型请求失败：{type(exc).__name__}: {exc}"
                ) from exc
            choices = getattr(completion, "choices", None) or []
            finish_reason = (
                getattr(choices[0], "finish_reason", None) if choices else None
            )
            if finish_reason == "length":
                diagnostics.append(
                    f"第{attempt + 1}次输出达到长度上限（请求预算{request_budget} tokens）"
                )
                if attempt == 0:
                    retry_budget = min(
                        request_budget * 2,
                        PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS,
                    )
                    if retry_budget <= request_budget:
                        break
                    if retry_budget > self._output_budget_limit:
                        diagnostics.append("扩大后的输出额度超过本地服务上限，未发送重试")
                        break
                    if retry_budget > request_budget:
                        diagnostics.append(
                            f"第2次请求预算提升至{retry_budget} tokens（最多一次）"
                        )
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
                                "请不要重复分析，立即按原冻结输入和协议控制 Schema "
                                f"{self._response_format_name} 输出完整 JSON；"
                                "不要附加解释。"
                            ),
                        },
                    ]
                    continue
                continue
            try:
                return self._message_text(completion)
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
                                "立即按原冻结输入和协议控制 Schema "
                                f"{self._response_format_name} 输出完整 JSON；"
                                "不要附加解释。"
                            ),
                        },
                    ]
                    continue
        raise RuntimeError(
            "协议控制模型连续两次未返回可读取的 JSON 正文："
            + "；".join(diagnostics)
        )

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        if not prompt.strip():
            raise ValueError("协议控制 Agent prompt 不能为空")
        session_id = f"protocol-control-chat-{uuid4().hex}"
        history = [{"role": "user", "content": prompt}]
        try:
            text = self._complete(history)
        except Exception as exc:  # noqa: BLE001 - external adapter boundary
            raise ProtocolControlAgentCallError(
                session_id,
                str(exc),
                uncertain_completion=isinstance(exc, _ProtocolControlRequestTimeout),
            ) from exc
        self._histories[session_id] = [
            *history,
            {"role": "assistant", "content": text},
        ]
        return ProtocolControlAgentResponse(session_id=session_id, text=text)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        if not prompt.strip():
            raise ValueError("协议控制 Agent 修复 prompt 不能为空")
        history = self._histories.get(session_id)
        if history is None:
            raise ProtocolControlAgentCallError(
                session_id,
                "找不到原协议控制 Agent 会话，不能脱离上下文继续修复",
            )
        # Persist only the logical repair turn; in-call length/empty retries stay
        # inside ``_complete`` and must not break user/assistant alternation.
        logical_history = [*history, {"role": "user", "content": prompt}]
        try:
            text = self._complete(logical_history)
        except Exception as exc:  # noqa: BLE001 - external adapter boundary
            raise ProtocolControlAgentCallError(
                session_id,
                str(exc),
                uncertain_completion=isinstance(exc, _ProtocolControlRequestTimeout),
            ) from exc
        self._histories[session_id] = [
            *logical_history,
            {"role": "assistant", "content": text},
        ]
        return ProtocolControlAgentResponse(session_id=session_id, text=text)

    def restore_history(
        self,
        *,
        session_id: str,
        messages: Sequence[Mapping[str, str]],
    ) -> None:
        """Restore an alternating user/assistant history after restart."""

        if not session_id.strip():
            raise ValueError("恢复协议控制 Agent 会话必须有 session_id")
        if session_id in self._histories:
            raise ValueError("协议控制 Agent 会话已存在，不能覆盖")
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
            raise ProtocolControlAgentCallError(
                session_id,
                "找不到协议控制 Agent 会话",
            )
        return tuple(dict(message) for message in self._histories[session_id])


# Discoverable aliases; callers should not depend on a provider-specific name.
OpenAICompatibleProtocolControlTransport = (
    OpenAICompatibleProtocolControlAgentTransport
)
ConfiguredProtocolControlAgentTransport = (
    OpenAICompatibleProtocolControlAgentTransport
)
ProtocolControlModelTransport = OpenAICompatibleProtocolControlAgentTransport
ProtocolControlAgentModelTransport = OpenAICompatibleProtocolControlAgentTransport


def protocol_control_transport_from_environment(
    **overrides: Any,
) -> OpenAICompatibleProtocolControlAgentTransport:
    """Build the configured real transport without selecting a hidden fallback."""

    return OpenAICompatibleProtocolControlAgentTransport(**overrides)


def protocol_control_transport_from_model_config(
    model_config: Mapping[str, Any] | Any,
    **overrides: Any,
) -> OpenAICompatibleProtocolControlAgentTransport:
    """Build from a frozen provider/model config while preserving its identity."""

    def read(name: str, default: Any = None) -> Any:
        if isinstance(model_config, Mapping):
            return model_config.get(name, default)
        return getattr(model_config, name, default)

    parameters = read("parameters", {}) or {}
    if not isinstance(parameters, Mapping):
        raise ValueError("协议控制模型 parameters 必须为对象")
    selected_provider = read("provider") or read("backend")
    if not isinstance(selected_provider, str) or not selected_provider.strip():
        raise ValueError("协议控制模型 provider/backend 不能为空")
    selected_model = read("model")
    if not isinstance(selected_model, str) or not selected_model.strip():
        raise ValueError("协议控制模型 model 不能为空")
    values: dict[str, Any] = {
        "backend": selected_provider,
        "provider": selected_provider,
        "model": selected_model,
        "reasoning_effort": read("reasoning_effort"),
        "max_tokens": parameters.get("max_tokens"),
        "temperature": parameters.get("temperature"),
        "base_url": parameters.get("base_url"),
    }
    values.update(
        {key: value for key, value in overrides.items() if value is not None}
    )
    normalized_provider = selected_provider.strip().lower()
    if (
        normalized_provider in REMOTE_OPENAI_PROVIDERS
        and normalized_provider != PROTOCOL_CONTROL_BACKEND
    ):
        # A frozen alternate provider must not inherit the active role's
        # endpoint or credential, even when that role has explicit overrides.
        values["base_url"], values["api_key"] = resolve_openai_connection(
            normalized_provider,
            base_url=values.get("base_url"),
            api_key=values.get("api_key"),
        )
    return OpenAICompatibleProtocolControlAgentTransport(
        **{key: value for key, value in values.items() if value is not None}
    )


protocol_control_transport_from_config = protocol_control_transport_from_model_config
protocol_control_agent_transport_from_model_config = (
    protocol_control_transport_from_model_config
)
protocol_control_agent_transport_from_environment = (
    protocol_control_transport_from_environment
)
