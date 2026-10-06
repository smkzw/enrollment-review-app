"""OpenAI-compatible transport retaining one protocol-deconstruction conversation."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

import httpx
from app.llm.generation_completion import local_early_length
from app.llm.json_container_recovery import recover_single_container_close, strict_json_loads
from app.llm.omlx_schema_compat import decoding_response_format
from openai import (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.config import (
    DECONSTRUCT_BACKEND,
    DECONSTRUCT_API_KEY,
    DECONSTRUCT_BASE_URL,
    DECONSTRUCT_GLM_API_KEY,
    DECONSTRUCT_GLM_BASE_URL,
    DECONSTRUCT_GLM_MODEL,
    DECONSTRUCT_GLM_REASONING_EFFORT,
    DECONSTRUCT_MAX_TOKENS,
    DECONSTRUCT_MODEL,
    DECONSTRUCT_REASONING_EFFORT,
    DECONSTRUCT_WIRE_CONTRACT,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    OMLX_API_KEY,
    OMLX_BASE_URL,
    MTPLX_API_KEY,
    MTPLX_BASE_URL,
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
)
from app.llm.provider_profiles import (
    REMOTE_OPENAI_PROVIDERS,
    provider_default_headers,
    resolve_openai_connection,
)
from app.llm.logical_call_budget import LogicalCallBudget, LogicalCallBudgetExhausted

from .protocol_deconstructor import (
    ProtocolAgentCallError,
    ProtocolAgentResponse,
    ProtocolOutputKind,
    protocol_output_response_format,
)


SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS = frozenset(
    {
        "deepseek",
        "omlx",
        "mtplx",
        "mtplx-api",
        "mlx-serve",
        "zhipu-coding-plan",
        "glm",
        "cms-router",
        "cms-smk",
        "opencode-go",
        "ollama-cloud",
    }
)
_DEEPSEEK_BACKENDS = frozenset({"deepseek"})
_MTPLX_BACKENDS = frozenset({"mtplx", "mtplx-api"})
_ZHIPU_BACKENDS = frozenset({"zhipu-coding-plan", "glm"})
_MLX_SERVE_BACKENDS = frozenset({"mlx-serve"})
# 现场实测（2026-09-18，Flash-Next/xgrammar）：MTPLX 的语法引擎无法编译方案
# wire 合同——number/深层嵌套 items 会被判 unsatisfiable 或生成含 look-ahead
# 的正则后被自身拒绝。对这类后端改为“合同入提示词”，响应仍走宿主严格校验。
_GRAMMAR_INCOMPATIBLE_BACKENDS = frozenset({"mtplx"})
_LOCAL_STRUCTURED_BACKENDS = frozenset(
    {"omlx", *_MTPLX_BACKENDS, *_MLX_SERVE_BACKENDS}
)
_SUPPORTED_GLM53_REASONING_EFFORTS = frozenset({"low", "high", "max"})

# mlx-serve local OpenAI-compatible server keeps an independent connection
# profile: it is never relabeled as omlx and never inherits the oMLX or MTPLX
# endpoint or model identity.  The model must be configured explicitly; there
# is no silent cross-provider default.  (Connection constants live here because
# this backend is transport-owned; app/config.py keeps the existing profiles.)
MLX_SERVE_BASE_URL = os.getenv("MLX_SERVE_BASE_URL", "http://127.0.0.1:11234").strip()
MLX_SERVE_API_KEY = os.getenv("MLX_SERVE_API_KEY", "")
MLX_SERVE_MODEL = os.getenv("MLX_SERVE_MODEL", "").strip()


def _unwrap_complete_json_fence(text: str) -> str:
    """Remove only a complete Markdown fence around one JSON response.

    Provider/model changes must not require prompt-specific parsers.  This
    compatibility step changes no JSON bytes inside the fence and deliberately
    rejects prose prefixes, suffixes, partial fences, and guessed repairs.
    """

    stripped = text.strip()
    lines = stripped.splitlines()
    if (
        len(lines) >= 3
        and lines[0].strip().lower() in {"```json", "```"}
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return stripped
MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS = int(
    os.getenv("MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", "8192")
)

logger = logging.getLogger(__name__)

# Transient failures before a response are retried against the same request.
# A started stream is never replayed: its upstream completion is uncertain.
# Timeouts surface as TRANSPORT_TIMEOUT for bounded segment recovery.
TRANSPORT_TRANSIENT_MAX_ATTEMPTS = 3
TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS = 2.0
# One length-finish retry may raise the output budget once, but the shared
# reasoning+content budget never exceeds this ceiling (R3 design §6.1).
PROTOCOL_LENGTH_RETRY_MAX_TOKENS = 131072
_TRANSPORT_TIMEOUT_ERRORS: tuple[type[Exception], ...] = (
    APITimeoutError,
    httpx.TimeoutException,
    TimeoutError,
)
_TRANSIENT_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    InternalServerError,
    RateLimitError,
    APIConnectionError,
    httpx.TransportError,
)


class ProtocolSemanticStreamInterrupted(RuntimeError):
    """The server started a response; its completion is unknown, so do not resend."""

    def __init__(self, cause: Exception, metadata: Mapping[str, object]):
        super().__init__(f"方案解构流式回包中断：{type(cause).__name__}")
        self.metadata = dict(metadata)


def _quota_exhausted(error: Exception, backend: str) -> bool:
    if backend not in _ZHIPU_BACKENDS or not isinstance(error, RateLimitError):
        return False
    body = error.body
    if not isinstance(body, Mapping):
        return False
    detail = body.get("error", body)
    # https://docs.bigmodel.cn/cn/api/api-code: quota windows, not rate throttling.
    return isinstance(detail, Mapping) and str(detail.get("code")) in {"1308", "1310"}


def _with_v1_suffix(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def _normalize_zhipu_coding_plan_base_url(base_url: str) -> str:
    """Keep Coding Plan ``.../paas/v4`` paths; do not append a stray ``/v1``."""

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("GLM 方案解构服务地址不能为空")
    if normalized.endswith("/v1") and "/paas/v4" in normalized:
        normalized = normalized[: -len("/v1")].rstrip("/")
    return normalized


def _map_glm_reasoning_effort(effort: str) -> dict[str, Any]:
    selected = str(effort or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = DECONSTRUCT_GLM_REASONING_EFFORT or "high"
    if selected not in _SUPPORTED_GLM53_REASONING_EFFORTS:
        raise ValueError(
            "GLM 方案解构推理强度仅支持 low/high/max，"
            f"当前值={selected or '空值'}"
        )
    return {
        "reasoning_effort": selected,
        "extra_body": {
            "thinking": {
                "type": "enabled",
                "clear_thinking": False,
            }
        },
    }


class DeepSeekProtocolAgentTransport:
    """Keep repair calls in the same logical chat history.

    All supported providers expose a stateless OpenAI-compatible endpoint.
    The local session ID therefore identifies an immutable message history held
    by this transport; every repair sends the complete prior user/assistant
    exchange.  A repair can never silently become a fresh prompt.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        backend: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        provider_defaults: bool = True,
        compact_wire: bool | None = None,
        bounded_batch_context: bool | None = None,
    ) -> None:
        # Preserve the historical class behavior for direct callers that pass a
        # DeepSeek model but omit the newly introduced backend selector.  The
        # The application path passes backend explicitly; direct callers can
        # still select a historical DeepSeek model by name.
        inferred_backend = (
            "deepseek"
            if model is not None and model.strip().lower().startswith("deepseek")
            else "mtplx"
            if model is not None and model.strip().lower().startswith("mtplx-")
            else "zhipu-coding-plan"
            if model is not None and model.strip().lower().startswith("glm-")
            else None
        )
        selected_backend = (
            backend or inferred_backend or DECONSTRUCT_BACKEND
        ).strip().lower()
        if selected_backend not in SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS:
            raise ValueError(
                f"当前方案解构不支持模型供应商 {selected_backend or '空值'}"
            )
        selected_model = model if model is not None else (
            DECONSTRUCT_GLM_MODEL
            if selected_backend in _ZHIPU_BACKENDS
            else MLX_SERVE_MODEL
            if selected_backend in _MLX_SERVE_BACKENDS
            else DECONSTRUCT_MODEL
        )
        if selected_backend in _MLX_SERVE_BACKENDS and not selected_model.strip():
            raise ValueError(
                "mlx-serve 方案解构模型必须显式配置："
                "请设置 MLX_SERVE_MODEL 或显式传入 model，"
                "不会回退到 oMLX/MTPLX 的默认模型。"
            )
        # ``provider_defaults`` only removes the product-side sampling overrides
        # (temperature) so the platform's own default
        # sampling applies.  Prompts and the strict output schema are never
        # changed by this flag.  New direct calls default to the provider
        # sampling defaults (R3 design §6.1: 不传 temperature); an explicit
        # ``provider_defaults=False`` keeps the historical product-side
        # overrides for frozen legacy identities.
        self._provider_defaults = bool(provider_defaults)
        if compact_wire is not None and type(compact_wire) is not bool:
            raise ValueError("输出合同选择必须为布尔值")
        if compact_wire is None:
            contract = DECONSTRUCT_WIRE_CONTRACT
            if contract not in {"auto", "formal", "compact"}:
                raise ValueError("DECONSTRUCT_WIRE_CONTRACT 仅支持 auto/formal/compact")
            compact_wire = {"auto": None, "formal": False, "compact": True}[contract]
        self._compact_wire = compact_wire
        selected_reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else (
                DECONSTRUCT_GLM_REASONING_EFFORT
                if selected_backend in _ZHIPU_BACKENDS
                else DECONSTRUCT_REASONING_EFFORT
            )
        )
        selected_max_tokens = (
            max_tokens if max_tokens is not None else DECONSTRUCT_MAX_TOKENS
        )
        if selected_backend in _ZHIPU_BACKENDS or selected_model.lower().startswith("glm-"):
            # Validate against GLM vocabulary before storing.
            _map_glm_reasoning_effort(selected_reasoning_effort)
        elif selected_reasoning_effort not in {
            "",
            "default",
            "auto",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise ValueError("方案解构推理强度不是受支持的值")
        if selected_max_tokens < 8192:
            raise ValueError("方案解构输出上限不能低于 8192 tokens")
        self._backend = selected_backend
        self._model = selected_model
        self._reasoning_effort = selected_reasoning_effort
        # Only an explicitly requested effort is forwarded on the oMLX /
        # mlx-serve wire (including xhigh); an env-inherited default must not
        # silently change the legacy request shape of existing product runs.
        self._reasoning_effort_requested = (
            selected_reasoning_effort
            if reasoning_effort is not None
            and selected_reasoning_effort not in {"", "default", "auto"}
            else None
        )
        local_cap = (
            MTPLX_PROTOCOL_BATCH_MAX_TOKENS
            if selected_backend in _MTPLX_BACKENDS
            else MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS
            if selected_backend in _MLX_SERVE_BACKENDS
            else OMLX_PROTOCOL_BATCH_MAX_TOKENS
        )
        if (
            selected_backend in _LOCAL_STRUCTURED_BACKENDS
            and selected_max_tokens > local_cap
        ):
            # An explicitly requested budget above the configured platform cap
            # must fail before any request; never silently min() shrink it.
            cap_env = (
                "MTPLX_PROTOCOL_BATCH_MAX_TOKENS"
                if selected_backend in _MTPLX_BACKENDS
                else "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS"
                if selected_backend in _MLX_SERVE_BACKENDS
                else "OMLX_PROTOCOL_BATCH_MAX_TOKENS"
            )
            raise ValueError(
                f"显式请求的方案解构输出预算 {selected_max_tokens} tokens 超过"
                f"平台批次上限 {cap_env}={local_cap}；请调高上限或降低请求，"
                "不会静默压缩显式请求。"
            )
        self._max_tokens = selected_max_tokens
        self._output_budget_limit = (
            min(local_cap, PROTOCOL_LENGTH_RETRY_MAX_TOKENS)
            if selected_backend in _LOCAL_STRUCTURED_BACKENDS
            else PROTOCOL_LENGTH_RETRY_MAX_TOKENS
        )
        if self._max_tokens < 8192:
            raise ValueError("方案解构批次输出上限不能低于 8192 tokens")
        if client is not None:
            self._client = client
        else:
            if selected_backend in _DEEPSEEK_BACKENDS:
                selected_api_key = DEEPSEEK_API_KEY if api_key is None else api_key
                selected_base_url = DEEPSEEK_BASE_URL if base_url is None else base_url
                if not selected_api_key:
                    raise ValueError("DeepSeek 方案解构服务尚未配置")
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _MTPLX_BACKENDS:
                selected_api_key = MTPLX_API_KEY if api_key is None else api_key
                selected_base_url = MTPLX_BASE_URL if base_url is None else base_url
                selected_api_key = selected_api_key or "local-mtplx"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _MLX_SERVE_BACKENDS:
                selected_api_key = MLX_SERVE_API_KEY if api_key is None else api_key
                selected_base_url = MLX_SERVE_BASE_URL if base_url is None else base_url
                # mlx-serve is local and does not require a secret, but the
                # OpenAI client still needs a non-empty placeholder key.
                selected_api_key = selected_api_key or "local-mlx-serve"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            elif selected_backend in _ZHIPU_BACKENDS:
                selected_api_key = (
                    DECONSTRUCT_GLM_API_KEY if api_key is None else api_key
                )
                selected_base_url = (
                    DECONSTRUCT_GLM_BASE_URL if base_url is None else base_url
                )
                if not selected_api_key:
                    raise ValueError("GLM 方案解构服务尚未配置")
                resolved_base_url = _normalize_zhipu_coding_plan_base_url(
                    selected_base_url
                )
            elif selected_backend in REMOTE_OPENAI_PROVIDERS:
                provider_only = selected_backend == "ollama-cloud"
                resolved_base_url, selected_api_key = resolve_openai_connection(
                    selected_backend,
                    base_url=None if provider_only else base_url or DECONSTRUCT_BASE_URL,
                    api_key=None if provider_only else api_key or DECONSTRUCT_API_KEY,
                    role_base_url_env=None if provider_only else "DECONSTRUCT_BASE_URL",
                    role_api_key_env=None if provider_only else "DECONSTRUCT_API_KEY",
                )
            else:
                selected_api_key = OMLX_API_KEY if api_key is None else api_key
                selected_base_url = OMLX_BASE_URL if base_url is None else base_url
                # oMLX is local and does not require a secret, but the OpenAI
                # client still needs a non-empty placeholder key.
                selected_api_key = selected_api_key or "local-omlx"
                resolved_base_url = _with_v1_suffix(selected_base_url)
            client_options: dict[str, Any] = {}
            if selected_backend in _LOCAL_STRUCTURED_BACKENDS:
                # Local inference must never be routed through a system HTTP
                # proxy. A proxy can return an early 502 while oMLX continues
                # generating, leaving the product with a false transport
                # failure and an orphaned expensive request.
                client_options["http_client"] = httpx.Client(trust_env=False)
            elif selected_backend in _ZHIPU_BACKENDS:
                # Match Independent VLM: do not inherit ambient HTTP_PROXY for
                # BigModel Coding Plan calls.
                client_options["http_client"] = httpx.Client(trust_env=False)
            default_headers = provider_default_headers(
                selected_backend,
                session_id=f"enrollment-review-protocol:{uuid4().hex}",
            )
            if default_headers is not None:
                client_options["default_headers"] = default_headers
            self._client = OpenAI(
                base_url=resolved_base_url,
                api_key=selected_api_key,
                timeout=600.0,
                max_retries=0,
                **client_options,
            )
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._output_scope: dict[str, Any] = {}
        self._bounded_batch_context = bounded_batch_context
        self._call_budgets: dict[str, LogicalCallBudget] = {}
        self.logical_call_budget: LogicalCallBudget | None = None
        self._call_budget_store: Any = None
        self.logical_run_budget: LogicalCallBudget | None = None
        self._last_budget_request_sha256: str | None = None
        self._scope_continuations: dict[str, dict[str, Any]] = {}
        self._active_scope_continuation: dict[str, Any] | None = None

    def bind_call_budget_store(self, store: Any) -> None:
        self._call_budget_store = store

    def configure_logical_run(self, *, logical_task_id: str, max_requests: int,
                              contract_sha256: str) -> None:
        self.logical_run_budget = self._restore_budget(
            logical_task_id, max_requests=max_requests,
            max_output_tokens=max_requests * self._output_budget_limit,
            contract_sha256=contract_sha256,
        )

    def share_run_budget(self, budget: LogicalCallBudget) -> None:
        self.logical_run_budget = budget

    def verify_recovery_budgets(self, metadata: Mapping[str, Any]) -> None:
        """Saved answers never authorize resetting either latest persisted ledger."""
        load = getattr(self._call_budget_store, "load_call_budget", None)
        if not callable(load):
            raise ValueError("恢复核对缺少原始持久预算记录")
        continuation = self._call_budget_metadata().get("authorized_scope_continuation")
        if metadata.get("authorized_scope_continuation") != continuation:
            raise ValueError("恢复核对的追加授权关联不一致")
        if self._active_scope_continuation is not None:
            self._verify_scope_continuation(self._active_scope_continuation)
        for key, budget in (("logical_call_budget", self.logical_call_budget),
                            ("logical_run_budget", self.logical_run_budget)):
            saved = metadata.get(key)
            if saved is None and budget is None and key == "logical_run_budget":
                continue
            if saved is None or budget is None:
                raise ValueError("恢复核对缺少原始范围或总作业额度")
            current = budget.snapshot()
            if load(current["logical_task_id"]) != current:
                raise ValueError("当前额度不是最新持久记录，不能恢复调用")
            if any(saved.get(field) != current.get(field) for field in (
                    "policy", "logical_task_id", "max_requests", "max_output_tokens", "contract_sha256")):
                raise ValueError("恢复额度的身份或上限发生变化")
            # Validate the historical snapshot itself, then prove it is a prefix.
            LogicalCallBudget(saved["logical_task_id"], max_requests=saved["max_requests"],
                              max_output_tokens=saved["max_output_tokens"],
                              contract_sha256=saved.get("contract_sha256"), saved=saved)
            if current["requests"][:saved["requests_used"]] != saved["requests"]:
                raise ValueError("恢复额度没有保留原调用历史")

    def _restore_budget(self, logical_task_id: str, *, max_requests: int,
                        max_output_tokens: int, contract_sha256: str | None = None) -> LogicalCallBudget:
        load = getattr(self._call_budget_store, "load_call_budget", None)
        persist = getattr(self._call_budget_store, "store_call_budget", None)
        try:
            return LogicalCallBudget(
                logical_task_id, max_requests=max_requests, max_output_tokens=max_output_tokens,
                saved=load(logical_task_id) if callable(load) else None,
                persist=persist if callable(persist) else None, contract_sha256=contract_sha256,
            )
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ProtocolAgentCallError(
                "protocol-budget-recovery", "方案读取预算记录无法核实，未重新调用模型",
                error_code="BUDGET_RECORD_INVALID", error_metadata={"logical_task_id": logical_task_id},
            ) from exc

    def configure_logical_task(self, *, logical_task_id: str, max_requests: int = 2) -> None:
        """Initial output and one repair share all nested HTTP attempts."""
        continuation = self._scope_continuations.get(logical_task_id)
        self._active_scope_continuation = continuation
        if continuation is not None:
            self._verify_scope_continuation(continuation)
            self.logical_call_budget = continuation["budget"]
            return
        budget = self._call_budgets.get(logical_task_id)
        if budget is None:
            budget = self._restore_budget(
                logical_task_id, max_requests=max_requests,
                max_output_tokens=(max_requests - 1) * self._max_tokens
                + min(self._max_tokens * 2, self._output_budget_limit),
            )
            self._call_budgets[logical_task_id] = budget
        self.logical_call_budget = budget

    def bind_authorized_scope_continuation(
        self, *, authorization_ref: str, artifact_reader: Callable[[str], bytes],
    ) -> None:
        """Bind a host-authorized additional allowance, never an automatic retry.

        The caller owns authority. The immutable receipt binds the spent scope,
        current run and finite allowance; old ledgers remain unchanged.
        """
        raw = artifact_reader(authorization_ref)
        grant = strict_json_loads(raw.decode("utf-8"))
        required = {"policy", "scope_task_id", "prior_scope_budget_sha256", "run_task_id",
                    "run_budget", "authorization_basis", "purpose", "max_requests",
                    "max_output_tokens"}
        if (not isinstance(grant, dict) or set(grant) != required
                or grant["policy"] != "authorized-scope-continuation/v1"
                or any(not isinstance(grant[key], str) or not grant[key].strip()
                       for key in required - {"max_requests", "max_output_tokens", "run_budget"})
                or any(type(grant[key]) is not int or grant[key] < 1
                       for key in ("max_requests", "max_output_tokens"))):
            raise ValueError("追加核查授权必须绑定原记录、总作业和明确的有限额度")
        if not authorization_ref or grant["scope_task_id"] in self._scope_continuations:
            raise ValueError("追加核查授权不可重复绑定或替换")
        load = getattr(self._call_budget_store, "load_call_budget", None)
        if not callable(load) or self.logical_run_budget is None:
            raise ValueError("追加核查必须沿用持久原任务及总作业额度")
        previous = load(grant["scope_task_id"])
        if previous is None:
            raise ValueError("追加核查的原任务额度记录不存在")
        LogicalCallBudget(previous["logical_task_id"], max_requests=previous["max_requests"],
                          max_output_tokens=previous["max_output_tokens"], saved=previous,
                          contract_sha256=previous.get("contract_sha256"))
        run = self.logical_run_budget.snapshot()
        authorized_run = grant["run_budget"]
        if not isinstance(authorized_run, dict):
            raise ValueError("追加核查缺少授权时的总作业记录")
        LogicalCallBudget(authorized_run["logical_task_id"], max_requests=authorized_run["max_requests"],
                          max_output_tokens=authorized_run["max_output_tokens"], saved=authorized_run,
                          contract_sha256=authorized_run.get("contract_sha256"))
        digest = lambda value: hashlib.sha256(json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if (digest(previous) != grant["prior_scope_budget_sha256"]
                or run["logical_task_id"] != grant["run_task_id"]
                or any(run[key] != authorized_run[key] for key in (
                    "policy", "logical_task_id", "max_requests", "max_output_tokens", "contract_sha256"))
                or run["requests"][:authorized_run["requests_used"]] != authorized_run["requests"]
                or load(run["logical_task_id"]) != run):
            raise ValueError("追加核查授权与实际原记录或总作业不一致")
        if (previous["requests_used"] < previous["max_requests"]
                and previous["reserved_output_tokens"] < previous["max_output_tokens"]):
            raise ValueError("原任务尚有额度，不能另开追加核查")
        authorization_hash = hashlib.sha256(raw).hexdigest()
        if load(authorization_hash) is None and run["requests_used"] != authorized_run["requests_used"]:
            raise ValueError("总作业已前移但追加额度记录缺失，不能当作未使用重新核查")
        budget = self._restore_budget(
            authorization_hash, max_requests=grant["max_requests"],
            max_output_tokens=grant["max_output_tokens"], contract_sha256=authorization_hash,
        )
        self._scope_continuations[grant["scope_task_id"]] = {
            "authorization_ref": authorization_ref, "authorization_sha256": authorization_hash,
            "prior_scope_budget": previous, "budget": budget,
            "run_task_id": run["logical_task_id"], "authorized_run_budget": authorized_run,
        }

    def _verify_scope_continuation(self, continuation: Mapping[str, Any]) -> None:
        load = getattr(self._call_budget_store, "load_call_budget", None)
        previous = continuation["prior_scope_budget"]
        if (not callable(load) or load(previous["logical_task_id"]) != previous
                or self.logical_run_budget is None
                or self.logical_run_budget.logical_task_id != continuation["run_task_id"]
                or load(continuation["run_task_id"]) != self.logical_run_budget.snapshot()):
            raise ValueError("追加核查的原额度或总作业发生变化，未发送请求")
        budget = continuation["budget"].snapshot()
        saved = load(budget["logical_task_id"])
        if saved is None and self.logical_run_budget.snapshot()["requests_used"] != continuation["authorized_run_budget"]["requests_used"]:
            raise ValueError("总作业已前移但追加额度记录缺失，不能重置核查")
        if saved != budget and not (saved is None and budget["requests_used"] == 0):
            raise ValueError("追加核查额度不是最新持久记录，未发送请求")

    def share_call_budget(self, budget: LogicalCallBudget) -> None:
        if self._active_scope_continuation is not None:
            if budget is not self._active_scope_continuation["budget"]:
                raise ValueError("追加核查期间不能用其他额度替换授权范围")
            self._verify_scope_continuation(self._active_scope_continuation)
        self._call_budgets[budget.logical_task_id] = budget
        self.logical_call_budget = budget

    def _call_budget_metadata(self) -> dict[str, object]:
        return {
            **({"logical_call_budget": self.logical_call_budget.snapshot()} if self.logical_call_budget else {}),
            **({"logical_run_budget": self.logical_run_budget.snapshot()} if self.logical_run_budget else {}),
            **({"authorized_scope_continuation": {
                key: value for key, value in self._active_scope_continuation.items() if key != "budget"
            }} if self._active_scope_continuation else {}),
        }

    def _reserve_completion(self, kwargs: Mapping[str, Any]) -> None:
        request_hash = hashlib.sha256(json.dumps(
            dict(kwargs), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        self._last_budget_request_sha256 = request_hash
        try:
            if self._active_scope_continuation is not None:
                self._verify_scope_continuation(self._active_scope_continuation)
            for budget in (self.logical_call_budget, self.logical_run_budget):
                if budget is not None:
                    budget.reserve(request_sha256=request_hash, max_tokens=int(kwargs["max_tokens"]))
        except LogicalCallBudgetExhausted as exc:
            raise ProtocolAgentCallError(
                "protocol-call-budget", str(exc), error_code="LOGICAL_BUDGET_EXHAUSTED",
                error_metadata=self._call_budget_metadata(),
            ) from exc
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ProtocolAgentCallError(
                "protocol-call-budget", "调用预算记录未保存，未发送模型请求",
                error_code="BUDGET_RECORD_INVALID", error_metadata=self._call_budget_metadata(),
            ) from exc

    def configure_output_scope(
        self,
        *,
        official_codes: Sequence[str],
        allowed_source_span_ids: Sequence[str],
        component_limit: int,
        group_limit: int,
        atom_limit: int,
        requirement_limit: int,
    ) -> None:
        """Constrain strict output to the current frozen semantic batch."""
        self._output_scope = {
            "official_codes": tuple(official_codes),
            "allowed_source_span_ids": tuple(allowed_source_span_ids),
            "component_limit": component_limit,
            "group_limit": group_limit,
            "atom_limit": atom_limit,
            "requirement_limit": requirement_limit,
        }

    def semantic_cache_identity(
        self,
        *,
        output_kind: ProtocolOutputKind,
        frozen_run: bool = False,
    ) -> str:
        """Hash the provider/model/schema contract without credentials."""

        kwargs = self._completion_kwargs([], output_kind=output_kind)
        kwargs.pop("messages", None)
        if frozen_run and "response_format" in kwargs:
            # Target subsets may change during repairs, not the run identity.
            kwargs["response_format"] = protocol_output_response_format(
                output_kind, compact=self.uses_compact_wire_contract,
            )
        payload = {
            "backend": self._backend,
            "model": self._model,
            "reasoning_effort": self._reasoning_effort,
            "response_gate_version": "reported-model-and-stop/v1",
            "request": kwargs,
        }
        if frozen_run:
            payload["endpoint"] = str(getattr(self._client, "base_url", ""))
        if self._backend in _GRAMMAR_INCOMPATIBLE_BACKENDS:
            payload["text_contract_mode"] = (
                "compact_schema_prompt" if self.uses_compact_wire_contract
                else "no_embedded_schema"
            )
        elif self.uses_compact_wire_contract and self._backend not in _LOCAL_STRUCTURED_BACKENDS:
            # Text/JSON-object endpoints do not put the output schema in kwargs;
            # its explicit selection must still isolate the saved response.
            payload["text_contract_mode"] = "compact_schema_prompt"
        from app.llm.mtplx_model_lifecycle import mtplx_deployment_identity

        deployment = mtplx_deployment_identity(
            self._backend, str(getattr(self._client, "base_url", "")),
            self._model, self._reasoning_effort,
        )
        if deployment:
            payload["deployment"] = deployment
        if self._bounded_batch_context is not None:
            payload["batch_context_policy"] = {
                "version": "explicit-batch-context/v1",
                "bounded": self._bounded_batch_context,
            }
        elif self._backend not in _LOCAL_STRUCTURED_BACKENDS:
            payload["batch_context_policy"] = {
                "version": "remote-default-bounded/v1",
                "bounded": True,
            }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @property
    def uses_compact_wire_contract(self) -> bool:
        return (self._backend in _LOCAL_STRUCTURED_BACKENDS
                if self._compact_wire is None else self._compact_wire)

    @property
    def supports_bounded_batch_context(self) -> bool:
        if self._bounded_batch_context is not None:
            return self._bounded_batch_context
        return True

    @property
    def supports_parent_rule_segmentation(self) -> bool:
        """Declare semantic segmentation separately from the wire format."""

        return self._backend in {
            *_LOCAL_STRUCTURED_BACKENDS,
            *_ZHIPU_BACKENDS,
            "cms-router",
            "cms-smk",
            "opencode-go",
            "deepseek",
        }

    def _completion_kwargs(
        self,
        messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind = "semantic_candidate",
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if output_kind not in {"semantic_candidate", "semantic_rule_repair", "official_source_scope_review", "semantic_source_fields", "semantic_period_sources"}:
            raise ValueError(f"未知的方案解构输出类型：{output_kind}")
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._backend == "ollama-cloud":
            kwargs.pop("response_format")
        if (
            self._backend in _LOCAL_STRUCTURED_BACKENDS
            and self._backend not in _GRAMMAR_INCOMPATIBLE_BACKENDS
        ):
            kwargs["response_format"] = protocol_output_response_format(
                output_kind,
                compact=self.uses_compact_wire_contract,
                **self._output_scope,
            )
            if self._backend == "omlx":
                kwargs["response_format"] = decoding_response_format(kwargs["response_format"])
        if (
            self._backend in _DEEPSEEK_BACKENDS
            and self._model.startswith("deepseek-v4")
        ):
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        elif self._backend in {"opencode-go", "ollama-cloud"}:
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
        elif self._backend in {"cms-router", "cms-smk"}:
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
        elif self._backend in _MTPLX_BACKENDS:
            if self._reasoning_effort not in {"", "default", "auto"}:
                kwargs["reasoning_effort"] = self._reasoning_effort
            if not self._provider_defaults:
                kwargs["temperature"] = 0.0
            # Strict-schema compatibility is independent of sampling defaults.
            # Speculative decoding can advance ahead of the grammar state.
            kwargs["extra_body"] = {"generation_mode": "ar"}
        elif self._backend in _ZHIPU_BACKENDS:
            glm_thinking = _map_glm_reasoning_effort(self._reasoning_effort)
            kwargs["reasoning_effort"] = glm_thinking["reasoning_effort"]
            kwargs["extra_body"] = glm_thinking["extra_body"]
            if not self._provider_defaults:
                kwargs["temperature"] = 0.1
        elif self._backend in {*_MLX_SERVE_BACKENDS, "omlx"}:
            # oMLX and mlx-serve send the requested reasoning effort verbatim
            # (including xhigh) instead of silently dropping it; an effort that
            # merely came from ambient env defaults is not sent.
            if self._reasoning_effort_requested is not None:
                kwargs["reasoning_effort"] = self._reasoning_effort_requested
            if not self._provider_defaults:
                kwargs["temperature"] = 0.0
        elif not self._provider_defaults:
            kwargs["temperature"] = 0.1
        return kwargs

    def _accumulate_stream(self, stream: Any) -> Any:
        """把流式响应重组为下游已知的非流式对象（content/finish_reason/usage）。

        全模型统一 streaming（2026-09-18 用户指令）：本地/远端路由器对长生成
        的 per-request 空闲超时不再掐断深度思考；usage 依赖
        stream_options.include_usage，不支持的服务端自动降级重试。
        """
        from types import SimpleNamespace

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason: str | None = None
        usage: Any = None
        request_id: str | None = None
        reported_model: str | None = None
        def partial_metadata() -> dict[str, object]:
            content = "".join(content_parts)
            reasoning = "".join(reasoning_parts)
            return {
                "request_id": request_id,
                "reported_model": reported_model,
                "finish_reason": finish_reason,
                "usage": (usage.model_dump(mode="json") if hasattr(usage, "model_dump")
                          else dict(usage) if isinstance(usage, Mapping) else None),
                "content_characters": len(content),
                "reasoning_characters": len(reasoning),
                "partial_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }

        try:
            for chunk in stream:
                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                delta = getattr(choice, "delta", None)
                piece = getattr(delta, "content", None) if delta is not None else None
                reasoning = getattr(delta, "reasoning_content", None) if delta is not None else None
                terminal = getattr(choice, "finish_reason", None)
                if piece or reasoning or terminal:
                    chunk_model = getattr(chunk, "model", None)
                    if chunk_model:
                        if reported_model and chunk_model.casefold() != reported_model.casefold():
                            raise ProtocolAgentCallError(
                                "protocol-stream-identity", "模型流在有效内容之间变更了模型身份",
                                error_code="MODEL_IDENTITY_MISMATCH",
                                error_metadata={**partial_metadata(), "conflicting_model": chunk_model,
                                                **self._call_budget_metadata()},
                            )
                        reported_model = chunk_model
                    request_id = request_id or getattr(chunk, "id", None)
                if terminal:
                    finish_reason = terminal
                if piece:
                    content_parts.append(piece)
                if reasoning:
                    reasoning_parts.append(reasoning)
        except ProtocolAgentCallError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider iterator may fail after dispatch
            raise ProtocolSemanticStreamInterrupted(exc, partial_metadata()) from exc
        if finish_reason is None:
            raise ProtocolSemanticStreamInterrupted(
                RuntimeError("服务未返回完成状态"), partial_metadata(),
            )
        message = SimpleNamespace(
            content="".join(content_parts),
            reasoning_content="".join(reasoning_parts),
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=finish_reason or "未提供")],
            id=request_id, model=reported_model, usage=usage,
        )

    def _send_completion(
        self,
        request_messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind,
        max_tokens: int | None = None,
    ) -> Any:
        """Send one HTTP completion with bounded transient-error retries.

        Before-response transient failures may retry the identical request.
        A stream that started but did not finish is never replayed because its
        upstream completion is unknown. Timeouts surface through the caller.
        """
        kwargs = self._completion_kwargs(
            request_messages,
            output_kind=output_kind,
            max_tokens=max_tokens,
        )
        last_exc: Exception | None = None
        for attempt in range(1, TRANSPORT_TRANSIENT_MAX_ATTEMPTS + 1):
            try:
                from app.llm.mtplx_model_lifecycle import sync_mtplx_model_session

                with sync_mtplx_model_session(
                    self._backend, str(getattr(self._client, "base_url", "")),
                    self._model, self._reasoning_effort,
                ):
                    kwargs["stream"] = True
                    kwargs.setdefault("stream_options", {"include_usage": True})
                    try:
                        self._reserve_completion(kwargs)
                        stream = self._client.chat.completions.create(**kwargs)
                    except Exception as stream_opt_exc:
                        if "stream_options" not in str(stream_opt_exc):
                            raise
                        kwargs.pop("stream_options", None)
                        self._reserve_completion(kwargs)
                        stream = self._client.chat.completions.create(**kwargs)
                    try:
                        return self._accumulate_stream(stream)
                    finally:
                        close = getattr(stream, "close", None)
                        if callable(close):
                            close()
            except ProtocolSemanticStreamInterrupted:
                raise
            except _TRANSPORT_TIMEOUT_ERRORS:
                raise
            except _TRANSIENT_RETRYABLE_ERRORS as exc:
                if _quota_exhausted(exc, self._backend):
                    raise
                last_exc = exc
                if attempt >= TRANSPORT_TRANSIENT_MAX_ATTEMPTS:
                    break
                wait = TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    "方案解构模型服务出现暂态传输错误（第%d/%d次尝试），%.1f秒后重试：%s",
                    attempt,
                    TRANSPORT_TRANSIENT_MAX_ATTEMPTS,
                    wait,
                    exc,
                )
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        output_kind: ProtocolOutputKind,
        with_receipt: bool = False,
    ) -> str | tuple[str, dict[str, object]]:
        request_messages = [dict(message) for message in messages]
        diagnostics: list[str] = []
        receipts: list[dict[str, object]] = []
        length_attempts = 0
        malformed_attempts = 0
        recovery_trigger: dict[str, object] | None = None
        # One logical request carries one shared reasoning+content budget; a
        # single length-finish retry may raise it once, capped, never silently.
        request_budget = self._max_tokens
        for attempt in range(2):
            request_hash = hashlib.sha256(json.dumps(
                request_messages, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            try:
                response = self._send_completion(
                    request_messages,
                    output_kind=output_kind,
                    max_tokens=request_budget,
                )
            except ProtocolAgentCallError as exc:
                exc.error_metadata = {**exc.error_metadata, "attempts": receipts,
                                      **self._call_budget_metadata()}
                if recovery_trigger is not None:
                    exc.error_metadata["first_completion_failure"] = recovery_trigger
                    exc.error_metadata["recovery_blocked_by"] = exc.error_code
                raise
            except ProtocolSemanticStreamInterrupted as exc:
                if receipts:
                    exc.metadata = {**exc.metadata, "attempts": receipts}
                raise
            except Exception as exc:
                code = ("TRANSPORT_TIMEOUT" if isinstance(exc, _TRANSPORT_TIMEOUT_ERRORS)
                        else "QUOTA_EXHAUSTED" if _quota_exhausted(exc, self._backend)
                        else "SEMANTIC_CALL_FAILED")
                raise ProtocolAgentCallError(
                    "protocol-completion", str(exc), error_code=code,
                    error_metadata={"attempts": receipts, **self._call_budget_metadata()},
                ) from exc
            choice = response.choices[0]
            message = choice.message
            text = message.content or ""
            reasoning_chars = len(getattr(message, "reasoning_content", "") or "")
            finish_reason = getattr(choice, "finish_reason", None) or "未提供"
            reported_model = getattr(response, "model", None)
            raw_usage = getattr(response, "usage", None)
            receipts.append({
                "request_sha256": request_hash,
                "budget_request_sha256": self._last_budget_request_sha256,
                "requested_model": self._model,
                "reported_model": reported_model,
                "request_id": getattr(response, "id", None),
                "requested_max_tokens": request_budget,
                "finish_reason": finish_reason,
                "usage": (raw_usage.model_dump(mode="json") if hasattr(raw_usage, "model_dump")
                          else dict(raw_usage) if isinstance(raw_usage, Mapping) else None),
                "content_characters": len(text) if isinstance(text, str) else 0,
                "reasoning_characters": reasoning_chars,
            })
            if (isinstance(reported_model, str) and reported_model.strip()
                    and reported_model.strip().casefold() != self._model.casefold()):
                raise ProtocolAgentCallError(
                    "protocol-response-identity",
                    "方案解构模型实际回报身份与本次配置不一致，结果未采用："
                    f"配置={self._model}，回报={reported_model.strip()}",
                    error_code="MODEL_IDENTITY_MISMATCH",
                    error_metadata={"attempts": receipts, **self._call_budget_metadata()},
                )
            if finish_reason == "length":
                if local_early_length(self._backend, getattr(response, "usage", None), request_budget):
                    raise ProtocolAgentCallError(
                        "protocol-length", "方案解构模型在额度用尽前停止，结果不完整；不扩大额度或重复原请求，需核查运行原因",
                        error_code="OUTPUT_TRUNCATED",
                        error_metadata={"attempts": receipts, **self._call_budget_metadata()},
                    )
                length_attempts += 1
                recovery_trigger = recovery_trigger or {"error_code": "OUTPUT_TRUNCATED", "attempt": attempt + 1}
                diagnostics.append(
                    f"第{attempt + 1}次结束原因=length（请求预算{request_budget} tokens），"
                    f"输出已被长度上限截断，"
                    f"正文长度={len(text) if isinstance(text, str) else 0}"
                )
                if attempt == 0:
                    retry_budget = min(
                        request_budget * 2,
                        PROTOCOL_LENGTH_RETRY_MAX_TOKENS,
                    )
                    if retry_budget <= request_budget:
                        break
                    if retry_budget > self._output_budget_limit:
                        diagnostics.append("扩大后的输出额度超过本地服务上限，未发送重试")
                        break
                    if retry_budget > request_budget:
                        diagnostics.append(
                            f"第2次请求预算提升至{retry_budget} tokens"
                            "（思考与正文共享额度，最多一次）"
                        )
                    request_budget = retry_budget
                    request_messages = [
                        *request_messages,
                        {
                            "role": "user",
                            "content": (
                                "上一请求的输出达到长度上限，正文不可作为完整JSON使用。"
                                "请不要重复分析，立即按上一请求指定的结构重新输出完整JSON对象，"
                                "不要附加解释。"
                                + ("只返回原请求的来源字段提案，不返回整规则或任何其他字段。"
                                   if output_kind in {"semantic_source_fields", "semantic_period_sources"} else
                                   "只处理原请求指定的1-3个父规则，返回最小完整图；"
                                   "不要重复节点、组件、source_excerpts或其他批次内容。")
                            ),
                        },
                    ]
                    continue
                continue
            if finish_reason != "stop":
                raise ProtocolAgentCallError(
                    "protocol-finish", f"方案解构模型未正常完成，结果未采用：{finish_reason}",
                    error_code="CONTENT_FILTERED" if finish_reason == "content_filter" else "COMPLETION_INCOMPLETE",
                    error_metadata={"attempts": receipts, **self._call_budget_metadata()},
                )
            if text.strip():
                json_text = _unwrap_complete_json_fence(text)
                try:
                    parsed = strict_json_loads(json_text)
                except json.JSONDecodeError as exc:
                    schema = protocol_output_response_format(
                        output_kind, compact=self.uses_compact_wire_contract,
                        **(self._output_scope or {}),
                    )["json_schema"]["schema"]
                    save_recovery = getattr(self._call_budget_store, "store_response_recovery", None)
                    recovered = (recover_single_container_close(json_text, schema)
                                 if output_kind != "official_source_scope_review" and callable(save_recovery) else None)
                    if recovered is not None:
                        proof = {
                            **recovered.receipt(json_text),
                            "provider_content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "schema_sha256": hashlib.sha256(json.dumps(schema, sort_keys=True,
                                ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
                        }
                        refs = save_recovery(raw_text=text, original_text=json_text,
                                             recovered_text=recovered.text, proof=proof)
                        receipts[-1]["syntax_recovery"] = {**proof, **refs}
                        return (recovered.text, {"attempts": receipts,
                                "raw_response_text": text, **self._call_budget_metadata()}) if with_receipt else recovered.text
                    malformed_attempts += 1
                    recovery_trigger = recovery_trigger or {
                        "error_code": "SCHEMA_INVALID", "attempt": attempt + 1,
                        "line": exc.lineno, "column": exc.colno,
                    }
                    diagnostics.append(
                        f"第{attempt + 1}次结束原因={finish_reason}，JSON无法解析，"
                        f"错误位置=第{exc.lineno}行第{exc.colno}列"
                    )
                    if attempt == 0:
                        request_messages = [
                            *request_messages,
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": (
                                    "上一回包的JSON语法不完整，无法解析。"
                                    f"解析错误在第{exc.lineno}行第{exc.colno}列。"
                                    "请不要重复分析，只按原结构输出语法完整的JSON对象；"
                                    "不要附加解释，不要省略逗号、引号、括号或必填字段。"
                                ),
                            },
                        ]
                        continue
                    continue
                if not isinstance(parsed, dict):
                    malformed_attempts += 1
                    recovery_trigger = recovery_trigger or {"error_code": "SCHEMA_INVALID", "attempt": attempt + 1}
                    diagnostics.append(
                        f"第{attempt + 1}次结束原因={finish_reason}，JSON顶层不是对象"
                    )
                    if attempt == 0:
                        request_messages = [
                            *request_messages,
                            {"role": "assistant", "content": text},
                            {
                                "role": "user",
                                "content": (
                                    "上一回包顶层不是JSON对象。请不要重复分析，"
                                    "只按原请求的结构输出一个完整JSON对象，不要附加解释。"
                                ),
                            },
                        ]
                        continue
                    continue
                return (json_text, {"attempts": receipts, **self._call_budget_metadata()}) if with_receipt else json_text
            recovery_trigger = recovery_trigger or {"error_code": "EMPTY_OUTPUT", "attempt": attempt + 1}
            diagnostics.append(
                f"第{attempt + 1}次结束原因={finish_reason}，推理内容长度={reasoning_chars}"
            )
            if attempt == 0:
                request_messages = [
                    *request_messages,
                    {
                        "role": "user",
                        "content": (
                            "上一请求只产生了内部推理，没有返回可读取的JSON正文。"
                            "请不要重复分析，立即严格按上一请求指定的结构输出完整JSON对象，"
                            "不要附加解释。"
                        ),
                    },
                ]
        if length_attempts:
            raise ProtocolAgentCallError(
                "protocol-length",
                "方案解构模型连续2次未返回完整JSON，输出被长度上限截断（"
                + "；".join(diagnostics)
                + "）", error_code="OUTPUT_TRUNCATED",
                error_metadata={"attempts": receipts, **self._call_budget_metadata()},
            )
        if malformed_attempts:
            raise ProtocolAgentCallError(
                "protocol-schema",
                "方案解构模型连续2次未返回可解析的JSON对象（"
                + "；".join(diagnostics)
                + "）", error_code="SCHEMA_INVALID",
                error_metadata={"attempts": receipts, **self._call_budget_metadata()},
            )
        raise ProtocolAgentCallError(
            "protocol-empty", "方案解构模型连续2次返回空正文（" + "；".join(diagnostics) + "）",
            error_code="EMPTY_OUTPUT", error_metadata={"attempts": receipts, **self._call_budget_metadata()},
        )

    def _wire_contract_prompt(self, prompt: str, output_kind: ProtocolOutputKind) -> str:
        """为无服务端 Schema 的简化合同请求加入形状提示。

        嵌入版做瘦身（去 $defs、两三层后只留类型形状）：完整合同会显著改变
        prefill 长度形态，实测触发 Flash-Next qsa_prefill Metal kernel 的
        JIT 编译缺陷（服务端 500）；字段级约束由提示词散文合同与宿主严格
        校验共同保证。
        """

        if output_kind in {"official_source_scope_review", "semantic_source_fields", "semantic_period_sources"}:
            # This role already carries its complete, small schema in the frozen
            # prompt; exact replay cannot depend on a second opaque wrapper.
            return prompt
        if (
            (self._backend not in _GRAMMAR_INCOMPATIBLE_BACKENDS
             and self._backend in _LOCAL_STRUCTURED_BACKENDS)
            or not self.uses_compact_wire_contract
        ):
            return prompt
        schema = protocol_output_response_format(
            output_kind,
            compact=True,
            **self._output_scope,
        )["json_schema"]["schema"]

        def slim(node: Any, depth: int) -> Any:
            if isinstance(node, list):
                return [slim(item, depth) for item in node]
            if not isinstance(node, dict):
                return node
            if "$ref" in node:
                return {"type": "object"}
            if depth >= 3:
                shallow: dict[str, Any] = {}
                if "type" in node:
                    shallow["type"] = node["type"]
                if "enum" in node:
                    shallow["enum"] = node["enum"]
                return shallow
            out: dict[str, Any] = {}
            for key, value in node.items():
                if key in {"title", "default", "$defs"}:
                    continue
                out[key] = slim(value, depth + 1)
            return out

        contract_json = json.dumps(slim(schema, 0), ensure_ascii=False)
        heading = (
            "【输出 JSON 合同（本服务语法约束不可用，以下合同取代服务端携带）】"
            if self._backend in _GRAMMAR_INCOMPATIBLE_BACKENDS
            else "【简化输出结构（字段形状摘要，完整约束仍由宿主校验）】"
        )
        return (
            prompt
            + "\n\n" + heading
            + "你的整段响应必须是一个符合该 JSON Schema 的 JSON 对象；"
            + "宿主会按完整合同逐字段严格校验，任何多余或缺失字段都会被拒绝：\n"
            + contract_json
        )

    def start(
        self,
        *,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        session_id = f"protocol-chat-{uuid4().hex}"
        history = [{"role": "user", "content": self._wire_contract_prompt(prompt, output_kind)}]
        self._histories[session_id] = history
        try:
            text, metadata = self._complete(history, output_kind=output_kind, with_receipt=True)
        except ProtocolAgentCallError as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc), error_code=exc.error_code, error_metadata=exc.error_metadata,
            ) from exc
        except ProtocolSemanticStreamInterrupted as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc), error_code="STREAM_INTERRUPTED",
                error_metadata={**exc.metadata, **self._call_budget_metadata()},
            ) from exc
        except (APITimeoutError, httpx.TimeoutException, TimeoutError) as exc:
            raise ProtocolAgentCallError(
                session_id,
                str(exc),
                error_code="TRANSPORT_TIMEOUT",
                error_metadata=self._call_budget_metadata(),
            ) from exc
        except Exception as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc),
                error_code="QUOTA_EXHAUSTED" if _quota_exhausted(exc, self._backend)
                else "SEMANTIC_CALL_FAILED",
                error_metadata=self._call_budget_metadata(),
            ) from exc
        raw_text = metadata.pop("raw_response_text", None)
        history.append({"role": "assistant", "content": text if raw_text is None else raw_text})
        self._histories[session_id] = history
        return ProtocolAgentResponse(session_id=session_id, text=text, raw_text=raw_text, call_metadata=metadata)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
        output_kind: ProtocolOutputKind = "semantic_candidate",
    ) -> ProtocolAgentResponse:
        if session_id not in self._histories:
            raise ValueError("找不到原方案解构会话，不能脱离上下文继续修正")
        history = [
            *self._histories[session_id],
            {"role": "user", "content": self._wire_contract_prompt(prompt, output_kind)},
        ]
        self._histories[session_id] = history
        try:
            text, metadata = self._complete(history, output_kind=output_kind, with_receipt=True)
        except ProtocolAgentCallError as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc), error_code=exc.error_code, error_metadata=exc.error_metadata,
            ) from exc
        except ProtocolSemanticStreamInterrupted as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc), error_code="STREAM_INTERRUPTED",
                error_metadata={**exc.metadata, **self._call_budget_metadata()},
            ) from exc
        except (APITimeoutError, httpx.TimeoutException, TimeoutError) as exc:
            raise ProtocolAgentCallError(
                session_id,
                str(exc),
                error_code="TRANSPORT_TIMEOUT",
                error_metadata=self._call_budget_metadata(),
            ) from exc
        except Exception as exc:
            raise ProtocolAgentCallError(
                session_id, str(exc),
                error_code="QUOTA_EXHAUSTED" if _quota_exhausted(exc, self._backend)
                else "SEMANTIC_CALL_FAILED",
                error_metadata=self._call_budget_metadata(),
            ) from exc
        raw_text = metadata.pop("raw_response_text", None)
        history.append({"role": "assistant", "content": text if raw_text is None else raw_text})
        self._histories[session_id] = history
        return ProtocolAgentResponse(session_id=session_id, text=text, raw_text=raw_text, call_metadata=metadata)

    def restore_history(
        self, *, session_id: str, messages: Sequence[Mapping[str, str]]
    ) -> None:
        """Restore one persisted stateless conversation without changing it."""

        if session_id in self._histories:
            raise ValueError("方案解构会话已存在，不能用持久记录覆盖")
        history = [dict(message) for message in messages]
        if not history or history[0].get("role") != "user":
            raise ValueError("持久方案解构会话必须从用户请求开始")
        expected_role = "user"
        for message in history:
            if message.get("role") != expected_role or not message.get("content", "").strip():
                raise ValueError("持久方案解构会话角色顺序或正文无效")
            expected_role = "assistant" if expected_role == "user" else "user"
        if history[-1]["role"] != "assistant":
            raise ValueError("只能从已有模型响应的完整方案解构会话恢复")
        self._histories[session_id] = history

    def compact_session_history(self, *, session_id: str, context: str) -> None:
        """Replace accumulated batch history with a bounded audit anchor."""

        if session_id not in self._histories:
            raise ValueError("找不到方案解构会话，不能压缩历史")
        if not context.strip():
            raise ValueError("方案解构会话压缩锚点不能为空")
        if len(context) > 12000:
            raise ValueError("方案解构会话压缩锚点超过 12000 字符操作上限")
        self._histories[session_id] = [
            {"role": "user", "content": context},
            {"role": "assistant", "content": "已保留冻结上下文和批次身份。"},
        ]

    def history(self, session_id: str) -> tuple[Mapping[str, str], ...]:
        """Expose a read-only copy for audit persistence and tests."""
        if session_id not in self._histories:
            raise ValueError("找不到方案解构会话")
        return tuple(dict(message) for message in self._histories[session_id])


# Keep the old import path stable while exposing the provider-neutral name to
# new callers.
OpenAICompatibleProtocolAgentTransport = DeepSeekProtocolAgentTransport
