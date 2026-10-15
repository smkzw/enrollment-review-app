"""Stable, credential-free identity of the product's selective page-reader route."""

from __future__ import annotations

import json
import os
from hashlib import sha256

from app.config import (
    INDEPENDENT_VLM_MAX_TOKENS,
    INDEPENDENT_VLM_MODEL,
    INDEPENDENT_VLM_PROVIDER,
    INDEPENDENT_VLM_REASONING_EFFORT,
)
from app.llm.provider_profiles import resolve_openai_connection


def selective_vision_route_sha256(*, model_id: str | None = None) -> str:
    provider = os.getenv("INDEPENDENT_VLM_PROVIDER", INDEPENDENT_VLM_PROVIDER).strip().lower()
    if provider == "bigmodel":
        provider = "zhipu-coding-plan"
    try:
        base_url, _ = resolve_openai_connection(
            provider,
            base_url=os.getenv("INDEPENDENT_VLM_BASE_URL", ""),
            role_base_url_env="INDEPENDENT_VLM_BASE_URL",
            role_api_key_env="INDEPENDENT_VLM_API_KEY",
            require_api_key=False,
        )
    except ValueError:
        # Preserve the intake/job record even when a selected vision route is invalid.
        base_url = os.getenv("INDEPENDENT_VLM_BASE_URL", "").strip() or "unresolved"
    effort = os.getenv(
        "INDEPENDENT_VLM_REASONING_EFFORT", INDEPENDENT_VLM_REASONING_EFFORT
    ).strip().lower()
    if effort in {"", "default", "auto"}:
        effort = "high"
    identity = {
        "provider": provider,
        "base_url": base_url,
        "model": (model_id or os.getenv("INDEPENDENT_VLM_MODEL", INDEPENDENT_VLM_MODEL)).strip(),
        "reasoning_effort": effort,
        "max_tokens": int(os.getenv("INDEPENDENT_VLM_MAX_TOKENS", str(INDEPENDENT_VLM_MAX_TOKENS))),
    }
    return sha256(json.dumps(identity, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()


def selective_vision_observation_plan_identity(
    plan_version: str, *, model_id: str, ocr_raw_text_sha256: str | None
) -> str:
    """Keep the route and read-layer identity in the existing immutable plan field."""
    ocr_identity = ocr_raw_text_sha256 or "no-ocr-text"
    return f"{plan_version}@{selective_vision_route_sha256(model_id=model_id)}:{ocr_identity}"
