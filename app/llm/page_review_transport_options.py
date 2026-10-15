"""Native page-output constraints without changing the clinical prompt."""

import json

from app.llm.omlx_schema_compat import decoding_response_format
from app.llm.mtplx_schema_compat import decoding_response_format as mtplx_decoding_response_format

PAGE_REVIEW_TRANSPORT_VERSION = "page-decoding/v3"


def page_transport_contract(provider: str, *, generation_mode: str = "mtp") -> str | None:
    if provider == "mtplx":
        return f"mtplx-schema-{generation_mode}-conditional-validation-v3"
    if provider == "omlx":
        return "omlx-schema-request-v1"
    return None


def page_completion_options(provider: str, messages: list[dict], budget: int) -> dict:
    if provider not in {"omlx", "mtplx"}:
        return {}
    has_images = any(
        isinstance(message.get("content"), list)
        and any(isinstance(part, dict) and part.get("type") == "image_url" for part in message["content"])
        for message in messages
    )
    for message in messages:
        content = message.get("content")
        if message.get("role") != "user" or not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") != "text":
                continue
            try:
                payload = json.loads(part["text"])
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(payload, dict) and "output_schema" in payload:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {"name": "page_review", "strict": True,
                                    "schema": payload["output_schema"]},
                }
                if provider == "mtplx":
                    # Current MTPLX rejects image+AR; retain AR for text-only requests.
                    return {"response_format": mtplx_decoding_response_format(response_format),
                            "extra_body": {"generation_mode": "mtp" if has_images else "ar"}}
                return {
                    "response_format": decoding_response_format(response_format),
                    "extra_body": {"thinking_budget": budget},
                }
    return {}
