"""Product-owned page vision transport for configured independent providers.

This module is a shared page-vision verification plane for raw DOCX/PDF page
inputs. The connection uses the explicit product environment and cannot
silently borrow an external agent harness or another provider's credential.
It fails closed on remote balance/auth/quota failures.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import httpx
from openai import APIStatusError, AsyncOpenAI, AuthenticationError

from app.config import (
    INDEPENDENT_VLM_API_KEY,
    INDEPENDENT_VLM_BASE_URL,
    INDEPENDENT_VLM_MAX_TOKENS,
    INDEPENDENT_VLM_MODEL,
    INDEPENDENT_VLM_PROVIDER,
    INDEPENDENT_VLM_REASONING_EFFORT,
    INDEPENDENT_VLM_TIMEOUT_SECONDS,
)
from app.llm.provider_profiles import (
    provider_default_headers,
    resolve_openai_connection,
)

logger = logging.getLogger(__name__)

SUPPORTED_INDEPENDENT_VLM_PROVIDERS = frozenset(
    {"zhipu-coding-plan", "bigmodel", "cms-router", "cms-smk", "opencode-go"}
)
# Product-owned `zhipu-coding-plan` / glm-5.3-flash Coding Plan base URL.
CODING_PLAN_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
# GLM-5.3 / GLM-5.3-Flash coding/paas v4 only accept these effort values.
SUPPORTED_GLM53_REASONING_EFFORTS = frozenset({"low", "high", "max"})

_BALANCE_CODE_MARKERS = frozenset({"1113"})
_BALANCE_TEXT_MARKERS = (
    "余额不足",
    "账户余额不足",
    "insufficient balance",
    "insufficient fund",
    "insufficient funds",
    "account balance is insufficient",
    "billing hard limit",
)
_AUTH_TEXT_MARKERS = (
    "unauthorized",
    "invalid api key",
    "authentication",
    "鉴权失败",
    "身份验证失败",
    "api key",
)
_QUOTA_TEXT_MARKERS = (
    "quota",
    "rate limit",
    "too many requests",
    "额度",
    "限流",
)

_SOURCE_REF_TOKEN_RE = re.compile(
    r"source_ref(?:\*\*|__|`)?\s*[:=：＝]\s*[`\"'“‘]?"
    r"([^\s,，;；（(\]}\"'”’`>]+)",
    re.IGNORECASE,
)


class IndependentVlmError(RuntimeError):
    """Base error for Independent VLM transport failures."""


class IndependentVlmConfigError(IndependentVlmError):
    """Configuration is missing or unsupported; route stays disabled."""


class IndependentVlmRemoteError(IndependentVlmError):
    """Remote provider failure with an explicit fail-closed classification."""

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str,
        disabled: bool,
        provider_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.disabled = disabled
        self.provider_code = provider_code
        self.status_code = status_code


class IndependentVlmBalanceError(IndependentVlmRemoteError):
    """Remote balance insufficient — Independent VLM must stay disabled."""

    def __init__(
        self,
        message: str,
        *,
        provider_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message,
            failure_kind="balance_insufficient",
            disabled=True,
            provider_code=provider_code,
            status_code=status_code,
        )


class IndependentVlmSourceFidelityError(IndependentVlmError):
    """Response invented or omitted required source locator identity."""


@dataclass(frozen=True)
class PageVisionInput:
    """One raw page image with stable source identity for fidelity checks."""

    source_ref: str
    page_ordinal: int
    media_type: str = "image/png"
    image_bytes: bytes | None = None
    data_url: str | None = None
    image_path: str | Path | None = None
    locator_hint: str | None = None

    def __post_init__(self) -> None:
        if not str(self.source_ref).strip():
            raise ValueError("PageVisionInput.source_ref must be non-empty")
        if int(self.page_ordinal) < 1:
            raise ValueError("PageVisionInput.page_ordinal must be >= 1")
        if not any((self.image_bytes, self.data_url, self.image_path)):
            raise ValueError(
                "PageVisionInput requires image_bytes, data_url, or image_path"
            )


@dataclass(frozen=True)
class IndependentVlmChatResult:
    """Text response plus transport diagnostics; never a clinical verdict."""

    text: str
    model: str
    finish_reason: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    reasoning_content: str | None = None
    raw_message: Mapping[str, Any] = field(default_factory=dict)
    allowed_source_refs: tuple[str, ...] = ()


_client: Optional[AsyncOpenAI] = None
_client_connection_identity: str | None = None


def reset_independent_vlm_client() -> None:
    """Drop the cached client (tests / config reload)."""
    global _client, _client_connection_identity
    _client = None
    _client_connection_identity = None


def normalize_independent_vlm_base_url(base_url: str) -> str:
    """Normalize BigModel paas/coding base URL without appending OpenAI /v1."""
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise IndependentVlmConfigError("INDEPENDENT_VLM_BASE_URL is empty")
    # Historical misconfig: some helpers append /v1; strip a trailing accidental
    # /v1 when the path already contains /paas/v4 or /coding/paas/v4.
    if normalized.endswith("/v1") and "/paas/v4" in normalized:
        normalized = normalized[: -len("/v1")].rstrip("/")
    return normalized


def map_reasoning_effort_to_thinking(
    effort: str | None = None,
) -> dict[str, Any]:
    """Map configured reasoning effort to BigModel thinking kwargs.

    Contract for GLM-5.3-Flash Coding Plan (matches OMP zai thinkingFormat):
    - ``high`` → ``thinking.type=enabled`` with ``reasoning_effort=high``
    - ``low`` / ``max`` are also accepted (provider vocabulary)
    - unsupported values fail closed (no invented project-specific mapping)
    - thinking cannot be disabled for this model family when effort is set
    """
    selected = effort if effort is not None else INDEPENDENT_VLM_REASONING_EFFORT
    selected = str(selected or "").strip().lower()
    if selected in {"", "default", "auto"}:
        selected = "high"
    if selected not in SUPPORTED_GLM53_REASONING_EFFORTS:
        raise IndependentVlmConfigError(
            "Unsupported INDEPENDENT_VLM_REASONING_EFFORT="
            f"{selected!r}; GLM-5.3-Flash accepts only "
            f"{sorted(SUPPORTED_GLM53_REASONING_EFFORTS)}"
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


def require_independent_vlm_config() -> dict[str, str]:
    """Validate provider/model/key; fail closed when vision route is selected."""
    provider = os.getenv(
        "INDEPENDENT_VLM_PROVIDER", INDEPENDENT_VLM_PROVIDER
    ).strip().lower()
    if provider not in SUPPORTED_INDEPENDENT_VLM_PROVIDERS:
        raise IndependentVlmConfigError(
            f"Unsupported INDEPENDENT_VLM_PROVIDER={provider!r}; "
            f"allowed={sorted(SUPPORTED_INDEPENDENT_VLM_PROVIDERS)}"
        )
    model = os.getenv("INDEPENDENT_VLM_MODEL", INDEPENDENT_VLM_MODEL).strip()
    if not model:
        raise IndependentVlmConfigError("INDEPENDENT_VLM_MODEL is empty")
    explicit_base_url = os.getenv("INDEPENDENT_VLM_BASE_URL", "").strip()
    explicit_api_key = os.getenv("INDEPENDENT_VLM_API_KEY", "").strip()
    if provider == "bigmodel":
        provider = "zhipu-coding-plan"
    try:
        base_url, api_key = resolve_openai_connection(
            provider,
            base_url=explicit_base_url,
            api_key=explicit_api_key,
            role_base_url_env="INDEPENDENT_VLM_BASE_URL",
            role_api_key_env="INDEPENDENT_VLM_API_KEY",
        )
    except ValueError as exc:
        raise IndependentVlmConfigError(str(exc)) from exc
    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
    }


def get_independent_vlm_client() -> AsyncOpenAI:
    """Return the configured client; connection changes require a process restart."""
    global _client, _client_connection_identity
    cfg = require_independent_vlm_config()
    timeout = float(
        os.getenv("INDEPENDENT_VLM_TIMEOUT_SECONDS", str(INDEPENDENT_VLM_TIMEOUT_SECONDS))
    )
    connection_identity = hashlib.sha256(json.dumps(
        (cfg["provider"], cfg["base_url"], cfg["api_key"], timeout),
        ensure_ascii=True,
    ).encode("utf-8")).hexdigest()
    if _client is not None and _client_connection_identity != connection_identity:
        raise IndependentVlmConfigError(
            "视觉模型连接配置已变化，请重启当前服务后继续核验。"
        )
    if _client is None:
        http_client = httpx.AsyncClient(
            trust_env=False,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        _client = AsyncOpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            http_client=http_client,
            max_retries=0,
            default_headers=provider_default_headers(
                cfg["provider"],
                session_id="enrollment-review-independent-vlm",
            ),
        )
        _client_connection_identity = connection_identity
    return _client


def page_to_data_url(page: PageVisionInput) -> str:
    """Encode a page image as a data URL without dropping source identity."""
    if page.data_url:
        return page.data_url
    if page.image_bytes is not None:
        b64 = base64.b64encode(page.image_bytes).decode("ascii")
        return f"data:{page.media_type};base64,{b64}"
    path = Path(page.image_path)  # type: ignore[arg-type]
    data = path.read_bytes()
    suffix = path.suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(suffix, page.media_type or "image/png")
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_page_anchor(page: PageVisionInput) -> str:
    """Stable textual side-car that round-trips source_ref / page ordinal."""
    parts = [
        (
            f"[PAGE_ANCHOR source_ref={page.source_ref} "
            f"page_ordinal={page.page_ordinal} media_type={page.media_type}]"
        ),
    ]
    if page.locator_hint:
        parts.append(f"[LOCATOR_HINT {page.locator_hint}]")
    return "\n".join(parts)


def build_page_vision_messages(
    prompt: str,
    pages: Sequence[PageVisionInput],
    *,
    system_prompt: str | None = None,
) -> list[dict[str, Any]]:
    """Build multimodal messages that preserve raw page + source identity."""
    if not pages:
        raise ValueError("build_page_vision_messages requires at least one page")

    allowed = [page.source_ref for page in pages]
    fidelity_rules = (
        "SOURCE LOCATOR FIDELITY CONTRACT:\n"
        "- Only cite source_ref / page_ordinal values listed in PAGE_ANCHOR blocks.\n"
        "- Do not invent, rename, or relocate source_ref values.\n"
        f"- Allowed source_ref values: {', '.join(allowed)}\n"
        "- If a claim cannot be grounded to an allowed source_ref, say so explicitly."
    )
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt.strip()},
        {"type": "text", "text": fidelity_rules},
    ]
    for page in pages:
        user_content.append({"type": "text", "text": build_page_anchor(page)})
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": page_to_data_url(page)},
            }
        )

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    return messages


def independent_vlm_completion_kwargs(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> dict[str, Any]:
    """Build request kwargs while preserving provider-default sampling."""
    cfg_model = model or os.getenv("INDEPENDENT_VLM_MODEL", INDEPENDENT_VLM_MODEL)
    provider = os.getenv("INDEPENDENT_VLM_PROVIDER", INDEPENDENT_VLM_PROVIDER).strip().lower()
    selected_effort = str(
        reasoning_effort
        if reasoning_effort is not None
        else os.getenv("INDEPENDENT_VLM_REASONING_EFFORT", INDEPENDENT_VLM_REASONING_EFFORT)
    ).strip().lower()
    if selected_effort in {"", "default", "auto"}:
        selected_effort = "high"
    kwargs: dict[str, Any] = {
        "model": cfg_model,
        "messages": messages,
        "max_tokens": int(
            max_tokens
            if max_tokens is not None
            else os.getenv(
                "INDEPENDENT_VLM_MAX_TOKENS", str(INDEPENDENT_VLM_MAX_TOKENS)
            )
        ),
        "reasoning_effort": selected_effort,
    }
    if provider in {"zhipu-coding-plan", "bigmodel"}:
        thinking = map_reasoning_effort_to_thinking(selected_effort)
        kwargs["reasoning_effort"] = thinking["reasoning_effort"]
        kwargs["extra_body"] = thinking["extra_body"]
    if temperature is not None:
        kwargs["temperature"] = temperature
    if top_p is not None:
        kwargs["top_p"] = top_p
    return kwargs


def _extract_error_payload(exc: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": str(exc)}
    body = getattr(exc, "body", None)
    if isinstance(body, Mapping):
        payload["body"] = dict(body)
        error = body.get("error")
        if isinstance(error, Mapping):
            payload["error"] = dict(error)
            for key in ("code", "error_code", "type"):
                if error.get(key) is not None:
                    payload["code"] = str(error.get(key))
                    break
            if error.get("message"):
                payload["message"] = str(error.get("message"))
        elif body.get("code") is not None:
            payload["code"] = str(body.get("code"))
        if body.get("msg") and payload.get("message") == str(exc):
            payload["message"] = str(body.get("msg"))
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status is not None:
            payload["status_code"] = int(status)
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, Mapping):
            payload.setdefault("body", dict(data))
            error = data.get("error") if isinstance(data.get("error"), Mapping) else data
            if isinstance(error, Mapping):
                for key in ("code", "error_code", "type"):
                    if error.get(key) is not None:
                        payload["code"] = str(error.get(key))
                        break
                if error.get("message"):
                    payload["message"] = str(error.get("message"))
                elif error.get("msg"):
                    payload["message"] = str(error.get("msg"))
    code = getattr(exc, "code", None)
    if code is not None and "code" not in payload:
        payload["code"] = str(code)
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        payload["status_code"] = int(status_code)
    return payload


def _message_blob(payload: Mapping[str, Any]) -> str:
    parts = [
        str(payload.get("message") or ""),
        str(payload.get("code") or ""),
        str(payload),
    ]
    return " ".join(parts).lower()


def classify_remote_failure(exc: BaseException) -> IndependentVlmRemoteError:
    """Classify remote failures; balance insufficient forces disabled=True."""
    payload = _extract_error_payload(exc)
    code = str(payload.get("code") or "").strip()
    status_code = payload.get("status_code")
    blob = _message_blob(payload)
    message = str(payload.get("message") or exc)

    if code in _BALANCE_CODE_MARKERS or any(
        marker.lower() in blob for marker in _BALANCE_TEXT_MARKERS
    ):
        return IndependentVlmBalanceError(
            f"Independent VLM disabled: remote balance insufficient ({message})",
            provider_code=code or "1113",
            status_code=int(status_code) if status_code is not None else None,
        )

    if isinstance(exc, AuthenticationError) or any(
        marker in blob for marker in _AUTH_TEXT_MARKERS
    ):
        return IndependentVlmRemoteError(
            f"Independent VLM disabled: authentication failure ({message})",
            failure_kind="auth",
            disabled=True,
            provider_code=code or None,
            status_code=int(status_code) if status_code is not None else None,
        )

    if any(marker in blob for marker in _QUOTA_TEXT_MARKERS) or status_code == 429:
        if code in _BALANCE_CODE_MARKERS or any(
            marker.lower() in blob for marker in _BALANCE_TEXT_MARKERS
        ):
            return IndependentVlmBalanceError(
                f"Independent VLM disabled: remote balance insufficient ({message})",
                provider_code=code or "1113",
                status_code=int(status_code) if status_code is not None else None,
            )
        return IndependentVlmRemoteError(
            f"Independent VLM unavailable: quota/rate-limit ({message})",
            failure_kind="quota",
            disabled=True,
            provider_code=code or None,
            status_code=int(status_code) if status_code is not None else None,
        )

    return IndependentVlmRemoteError(
        f"Independent VLM unavailable: {message}",
        failure_kind="remote_error",
        disabled=True,
        provider_code=code or None,
        status_code=int(status_code) if status_code is not None else None,
    )


def extract_claimed_source_refs(text: str) -> set[str]:
    """Collect source_ref tokens claimed in model text (best-effort)."""
    return {match.group(1) for match in _SOURCE_REF_TOKEN_RE.finditer(text or "")}


def assert_source_locator_fidelity(
    text: str,
    allowed_source_refs: Sequence[str],
    *,
    require_claim: bool = False,
) -> None:
    """Reject responses that invent source_ref values outside the page set."""
    allowed = {str(ref).strip() for ref in allowed_source_refs if str(ref).strip()}
    if not allowed:
        raise IndependentVlmSourceFidelityError(
            "No allowed source_ref values were provided for fidelity checks"
        )
    claimed = extract_claimed_source_refs(text)
    invented = sorted(ref for ref in claimed if ref not in allowed)
    if invented:
        raise IndependentVlmSourceFidelityError(
            "Independent VLM response invented source_ref values: "
            + ", ".join(invented)
        )
    if require_claim and not claimed:
        raise IndependentVlmSourceFidelityError(
            "Independent VLM response omitted required source_ref claims"
        )


async def independent_vlm_chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    allowed_source_refs: Sequence[str] | None = None,
    enforce_source_fidelity: bool = True,
    require_source_claim: bool = False,
) -> IndependentVlmChatResult:
    """Call BigModel vision chat and fail closed on balance/auth/quota errors."""
    client = get_independent_vlm_client()
    kwargs = independent_vlm_completion_kwargs(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        top_p=top_p,
    )
    try:
        resp = await client.chat.completions.create(**kwargs)
    except IndependentVlmError:
        raise
    except (APIStatusError, AuthenticationError) as exc:
        raise classify_remote_failure(exc) from exc
    except Exception as exc:  # noqa: BLE001 - classify remote transport failures
        classified = classify_remote_failure(exc)
        if classified.failure_kind == "balance_insufficient":
            raise classified from exc
        raise IndependentVlmRemoteError(
            f"Independent VLM unavailable: {exc}",
            failure_kind="remote_error",
            disabled=True,
        ) from exc

    choice = resp.choices[0] if resp.choices else None
    message = choice.message if choice is not None else None
    text = (getattr(message, "content", None) or "") if message is not None else ""
    reasoning = (
        getattr(message, "reasoning_content", None) if message is not None else None
    )
    usage_obj = getattr(resp, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        if hasattr(usage_obj, "model_dump"):
            dumped = usage_obj.model_dump()
            if isinstance(dumped, Mapping):
                usage = dict(dumped)
        if not usage:
            for key in ("completion_tokens", "prompt_tokens", "total_tokens"):
                value = getattr(usage_obj, key, None)
                if value is not None:
                    usage[key] = value

    allowed = tuple(allowed_source_refs or ())
    if enforce_source_fidelity and allowed:
        assert_source_locator_fidelity(
            text,
            allowed,
            require_claim=require_source_claim,
        )

    raw_message: dict[str, Any] = {}
    if message is not None:
        raw_message = {
            "role": getattr(message, "role", None),
            "content": text,
            "reasoning_content": reasoning,
        }

    return IndependentVlmChatResult(
        text=text,
        model=str(getattr(resp, "model", None) or kwargs["model"]),
        finish_reason=getattr(choice, "finish_reason", None) if choice else None,
        usage=usage,
        reasoning_content=reasoning,
        raw_message=raw_message,
        allowed_source_refs=allowed,
    )


async def independent_vlm_page_chat(
    prompt: str,
    pages: Sequence[PageVisionInput],
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> IndependentVlmChatResult:
    """Convenience wrapper: build raw-page messages then call Independent VLM."""
    messages = build_page_vision_messages(
        prompt,
        pages,
        system_prompt=system_prompt,
    )
    return await independent_vlm_chat(
        messages,
        model=model,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        allowed_source_refs=[page.source_ref for page in pages],
        enforce_source_fidelity=True,
        require_source_claim=True,
    )


async def check_independent_vlm() -> bool:
    """Return True only when provider config is present and key is set.

    Does not probe the remote network by default: missing credentials must keep
    the Independent VLM route explicitly disabled.
    """
    try:
        require_independent_vlm_config()
        map_reasoning_effort_to_thinking()
    except IndependentVlmConfigError:
        return False
    return True
