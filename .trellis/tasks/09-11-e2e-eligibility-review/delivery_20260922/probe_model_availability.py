"""Bounded diagnostic using product transport; no production jobs or env writes."""
from __future__ import annotations

import asyncio
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import time
import uuid
from functools import partial
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.config import parse_env_file_values
from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageReaderRoute, direct_completion


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-header", action="store_true")
    args = parser.parse_args()
    env = parse_env_file_values(Path(".env"))
    key = env.get("OPENCODE_API_KEY", "")
    if not key:
        raise SystemExit("Product OpenCode credential is absent; no call made.")
    folder = Path(__file__).parent / ("model_diagnostic_header" if args.session_header else "model_diagnostic")
    if folder.exists():
        raise SystemExit("Diagnostic receipts already exist; do not overwrite or repeat this run.")
    folder.mkdir()
    im = Image.new("RGB", (1024, 768), "white")
    ImageDraw.Draw(im).text((80, 100), "CONTROL 4729", fill="black", font_size=64)
    buffer = io.BytesIO()
    im.save(buffer, format="PNG")
    payload = buffer.getvalue()
    results = []
    from app.llm import page_review_harness
    native_client = page_review_harness.AsyncOpenAI
    for model in ("muse-spark-1.3-contributor", "mimo-v2.6-flash", "deepseek-v4.1-flash"):
        route = PageReaderRoute(
            lane=PageReviewLane.MAIN_A, provider="opencode-go",
            base_url="https://opencode.ai/zen/go/v1", api_key=key,
            model=model, reasoning_effort="high", max_tokens=65536, max_concurrency=2,
        )
        for mode in ("text", "image"):
            headers = {
                "x-opencode-session": "enrollment-diagnostic-" + str(uuid.uuid5(uuid.NAMESPACE_URL, model)),
                "User-Agent": "enrollment-review-connectivity-diagnostic/20260922",
            } if args.session_header else {}
            content = "Reply with exactly OK."
            if mode == "image":
                content = [
                    {"type": "text", "text": "Transcribe the visible text only."},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(payload).decode()
                    }},
                ]
            started = time.monotonic()
            entry = {"model": model, "provider": route.provider, "mode": mode,
                     "max_tokens": 65536, "reasoning_effort": "high",
                     "transport": "app.llm.page_review_harness.direct_completion",
                     "image_sha256": hashlib.sha256(payload).hexdigest() if mode == "image" else None,
                     "synthetic_control_not_clinical_acceptance": True}
            entry["isolated_header_override"] = headers
            try:
                # Process-local adapter experiment; product source and .env stay unchanged.
                with patch.object(page_review_harness, "AsyncOpenAI",
                                  partial(native_client, default_headers=headers)):
                    response = await asyncio.wait_for(
                        direct_completion(route, [{"role": "user", "content": content}], 65536),
                        timeout=180,
                    )
                entry.update(status="response", finish_reason=response.finish_reason,
                             response_model=response.response_model, response_id=response.response_id,
                             usage=response.usage, output=response.text,
                             output_lengths=response.output_lengths)
            except Exception as exc:
                message = str(exc).replace(key, "[REDACTED]")
                entry.update(status="error", error_type=type(exc).__name__,
                             http_status=getattr(exc, "status_code", None), message=message[:3000])
            entry["elapsed_seconds"] = round(time.monotonic() - started, 3)
            results.append(entry)
            (folder / "receipts.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            # A text authentication/availability failure cannot be diagnosed by adding an image.
            if mode == "text" and entry.get("http_status") in (401, 402, 403, 404, 429, 502, 503):
                break


if __name__ == "__main__":
    asyncio.run(main())
