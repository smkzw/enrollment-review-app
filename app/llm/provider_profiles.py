"""Connection profiles for product-owned OpenAI-compatible model routes.

Clinical roles keep their own model, effort and output budget. This module
only resolves provider connections and never borrows another provider's key.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal


REMOTE_OPENAI_PROVIDERS = frozenset(
    {
        "cms-router",
        "cms-smk",
        "opencode-go",
        "ollama-cloud",
        "deepseek",
        "deepseek-api",
        "zhipu-coding-plan",
        "glm",
    }
)

_PROVIDER_ENV = {
    "cms-router": ("CMS_ROUTER_BASE_URL", "CMS_ROUTER_API_KEY", "http://127.0.0.1:20128/v1"),
    "cms-smk": ("CMS_SMK_BASE_URL", "CMS_SMK_API_KEY", "https://new-api.mediportal.com.cn/v1"),
    "opencode-go": ("OPENCODE_BASE_URL", "OPENCODE_API_KEY", "https://opencode.ai/zen/go/v1"),
    "ollama-cloud": ("OLLAMA_BASE_URL", "OLLAMA_API_KEY", "https://ollama.com/v1"),
    "deepseek": ("DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
    "deepseek-api": ("DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
    "zhipu-coding-plan": (
        "DECONSTRUCT_GLM_BASE_URL",
        "DECONSTRUCT_GLM_API_KEY",
        "https://open.bigmodel.cn/api/coding/paas/v4",
    ),
    "glm": (
        "DECONSTRUCT_GLM_BASE_URL",
        "DECONSTRUCT_GLM_API_KEY",
        "https://open.bigmodel.cn/api/coding/paas/v4",
    ),
}

StructuredResponseMode = Literal["json_schema", "json_object", "text"]

# Provider transports do not expose one uniform structured-output contract.
# This is a connection capability only: downstream Pydantic validation remains
# identical regardless of the wire mode selected here.
_PROVIDER_STRUCTURED_RESPONSE_MODE: dict[str, StructuredResponseMode] = {
    "opencode-go": "json_object",
    "ollama-cloud": "text",
    "deepseek": "json_object",
    "deepseek-api": "json_object",
}


def _value(environ: Mapping[str, str], name: str) -> str:
    return str(environ.get(name, "") or "").strip()


def normalize_openai_base_url(provider: str, base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("模型服务地址不能为空")
    if provider in {"zhipu-coding-plan", "glm"} and "/paas/v4" in normalized:
        return normalized[: -len("/v1")] if normalized.endswith("/v1") else normalized
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def resolve_openai_connection(
    provider: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    role_base_url_env: str | None = None,
    role_api_key_env: str | None = None,
    environ: Mapping[str, str] | None = None,
    require_api_key: bool = True,
) -> tuple[str, str]:
    """Resolve one explicit provider without cross-provider credential fallback."""

    env = os.environ if environ is None else environ
    selected = provider.strip().lower()
    if selected not in _PROVIDER_ENV:
        raise ValueError(f"模型供应商 {selected or '空值'} 没有远程连接配置")
    provider_base_env, provider_key_env, default_base = _PROVIDER_ENV[selected]
    resolved_base = (
        str(base_url or "").strip()
        or (_value(env, role_base_url_env) if role_base_url_env else "")
        or _value(env, provider_base_env)
        or default_base
    )
    resolved_key = (
        str(api_key or "").strip()
        or (_value(env, role_api_key_env) if role_api_key_env else "")
        or _value(env, provider_key_env)
    )
    if require_api_key and not resolved_key:
        expected = role_api_key_env or provider_key_env
        raise ValueError(f"模型服务尚未配置凭据（缺少 {expected} 或 {provider_key_env}）")
    return normalize_openai_base_url(selected, resolved_base), resolved_key


def provider_default_headers(provider: str, *, session_id: str) -> dict[str, str] | None:
    if provider.strip().lower() != "opencode-go":
        return None
    return {
        "x-opencode-session": session_id,
        "User-Agent": "enrollment-review-app/1",
    }


def resolve_structured_response_mode(
    provider: str,
    *,
    explicit: str | None = None,
    env_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> StructuredResponseMode:
    """Resolve provider wire capability without weakening product validation."""

    env = os.environ if environ is None else environ
    configured = str(explicit or "").strip().lower()
    if not configured and env_name:
        configured = _value(env, env_name).lower()
    selected = provider.strip().lower()
    mode = configured or _PROVIDER_STRUCTURED_RESPONSE_MODE.get(
        selected, "json_schema"
    )
    if mode not in {"json_schema", "json_object", "text"}:
        raise ValueError(
            f"{env_name or '模型'} 返回方式仅支持 "
            "json_schema/json_object/text"
        )
    return mode  # type: ignore[return-value]
