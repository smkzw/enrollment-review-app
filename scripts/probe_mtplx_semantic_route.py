#!/usr/bin/env python3
"""Probe the real MTPLX OpenAI-compatible semantic endpoint.

The probe is deliberately fail-closed: it requires the exact served model id,
requests a strict JSON Schema response, and rejects a response that identifies a
different model.  It never tries another endpoint or provider and never reads
or writes clinical/project data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler


# Keep the probe aligned with the application launcher.  A one-off isolated
# MTPLX process can still be checked with ``--base-url`` when another local
# service already owns the default port.
DEFAULT_BASE_URL = "http://127.0.0.1:8002"
DEFAULT_MODEL = "mtplx-flash-next-optimized-speed"
DEFAULT_REASONING_EFFORT = "medium"


class ProbeError(RuntimeError):
    """A bounded, non-secret probe failure."""

    def __init__(self, phase: str, message: str) -> None:
        self.phase = phase
        super().__init__(message)


def _api_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ProbeError("configuration", "MTPLX base URL is empty")
    return normalized if normalized.endswith("/v1") else normalized + "/v1"


def _request(
    *,
    url: str,
    method: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
    api_key: str = "",
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method=method)
    # A local model endpoint must not be tested through an inherited system
    # proxy: a proxy response is not evidence about the local provider.
    opener = build_opener(ProxyHandler({}))
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read(4096)
        digest = hashlib.sha256(raw).hexdigest()
        raise ProbeError(
            "http",
            f"HTTP {exc.code}; body_sha256={digest}; body_bytes={len(raw)}",
        ) from exc
    except URLError as exc:
        raise ProbeError("connectivity", f"{type(exc.reason).__name__}: local endpoint unavailable") from exc
    except TimeoutError as exc:
        raise ProbeError("connectivity", "request timed out") from exc
    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError("protocol", f"response is not JSON; bytes={len(raw)}") from exc
    if not isinstance(value, dict):
        raise ProbeError("protocol", "response JSON top level is not an object")
    value["_probe_elapsed_ms"] = elapsed_ms
    return value


def _strict_probe_schema(model: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ok": {"type": "boolean", "enum": [True]},
            "route": {"type": "string", "enum": [model]},
        },
        "required": ["ok", "route"],
    }


def _strict_completion_payload(model: str, reasoning_effort: str) -> dict[str, Any]:
    """Build the bounded probe request sent to the configured MTPLX endpoint."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "只返回符合 Schema 的 JSON 对象，不要附加解释。"},
            {
                "role": "user",
                "content": f"返回 ok=true，并将 route 原样设置为：{model}",
            },
        ],
        "temperature": 0,
        "max_tokens": 512,
        "reasoning_effort": reasoning_effort,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "mtplx_semantic_route_probe",
                "strict": True,
                "schema": _strict_probe_schema(model),
            },
        },
    }


def _check_model_advertisement(models: dict[str, Any], model: str) -> int:
    entries = models.get("data")
    if not isinstance(entries, list):
        raise ProbeError("model_identity", "/v1/models data is not a list")
    ids = {
        str(entry.get("id"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }
    if model not in ids:
        raise ProbeError(
            "model_identity",
            f"exact model id is not advertised; requested={model!r}; advertised_count={len(ids)}",
        )
    return len(ids)


def _extract_strict_content(completion: dict[str, Any], model: str) -> tuple[str, str]:
    response_model = completion.get("model")
    if response_model != model:
        raise ProbeError(
            "model_identity",
            f"completion model identity mismatch; requested={model!r}; returned={response_model!r}",
        )
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProbeError("structured_output", "completion has no readable choice")
    choice = choices[0]
    message = choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ProbeError("structured_output", "completion has no readable message content")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProbeError("structured_output", f"message content is not JSON at column {exc.colno}") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"ok", "route"}:
        raise ProbeError("structured_output", "response does not match the strict two-field probe shape")
    if parsed.get("ok") is not True or parsed.get("route") != model:
        raise ProbeError("structured_output", "response JSON does not echo the requested route")
    return content, str(choice.get("finish_reason") or "unknown")


def run_probe(*, base_url: str, model: str, reasoning_effort: str, timeout: float) -> dict[str, Any]:
    api_base = _api_base_url(base_url)
    api_key = os.getenv("MTPLX_API_KEY", "")
    models = _request(
        url=f"{api_base}/models",
        method="GET",
        timeout=timeout,
        api_key=api_key,
    )
    advertised_count = _check_model_advertisement(models, model)
    completion = _request(
        url=f"{api_base}/chat/completions",
        method="POST",
        timeout=timeout,
        api_key=api_key,
        payload=_strict_completion_payload(model, reasoning_effort),
    )
    content, finish_reason = _extract_strict_content(completion, model)
    return {
        "ok": True,
        "base_url": api_base,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "advertised_model_count": advertised_count,
        "response_model": completion["model"],
        "finish_reason": finish_reason,
        "strict_json_schema": True,
        "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "models_elapsed_ms": models.get("_probe_elapsed_ms", 0),
        "completion_elapsed_ms": completion.get("_probe_elapsed_ms", 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("MTPLX_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.getenv("MTPLX_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--reasoning-effort",
        default=os.getenv("MTPLX_REASONING_EFFORT", DEFAULT_REASONING_EFFORT),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        result = run_probe(
            base_url=args.base_url,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout=args.timeout,
        )
    except ProbeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "phase": exc.phase,
                    "error": str(exc),
                    "base_url": _api_base_url(args.base_url),
                    "model": args.model,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
