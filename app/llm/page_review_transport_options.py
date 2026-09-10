"""Native page-output constraints without changing the clinical prompt."""

import json

from app.llm.omlx_schema_compat import decoding_response_format


def page_completion_options(provider: str, messages: list[dict], budget: int) -> dict:
    if provider != "omlx":
        return {}
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
                return {
                    "response_format": decoding_response_format({
                        "type": "json_schema",
                        "json_schema": {"name": "page_review", "strict": True,
                                        "schema": payload["output_schema"]},
                    }),
                    "extra_body": {"thinking_budget": budget},
                }
    return {}
