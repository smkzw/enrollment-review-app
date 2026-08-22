"""Run a real, PHI-free GLM-OCR probe against an isolated oMLX server.

This is a Slice 4.0 capability probe, not an application adapter. It preserves
the provider response bytes as base64 plus SHA-256 in the decision artifact and
makes no layout claim unless the response itself contains explicit numeric
coordinate structures.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import fitz

from app.domain.contracts.enums import ExtractionRoute
from tests.v2.evidence.goldgen import build_gold_set


def _normalize(text: str) -> str:
    return "".join(text.split())


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _render_pdf_page(path: Path, page_index: int = 0) -> bytes:
    doc = fitz.open(path)
    try:
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return pix.tobytes("jpeg")
    finally:
        doc.close()


def _request(
    url: str, model: str, image_bytes: bytes, mime: str
) -> tuple[bytes, bytes, float, int]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请逐字识别图片中的全部文字，保留原有行序和否定词。"
                            "如果模型原生支持文字区域坐标，请同时返回模型真实生成的坐标；"
                            "不支持时只返回识别文字，不要估算或编造坐标。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{mime};base64,"
                                + base64.b64encode(image_bytes).decode("ascii")
                            )
                        },
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0,
    }
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/chat/completions",
        data=request_body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=600) as response:
        body = response.read()
        status = int(response.status)
    return request_body, body, time.monotonic() - started, status


def _content(parsed: dict[str, Any]) -> str:
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TypeError("OCR 响应缺少 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise TypeError("OCR 响应 choices[0] 不是对象")
    message = first.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise TypeError("OCR 响应缺少字符串 message.content")
    return message["content"]


_COORDINATE_KEYS = {
    "bbox",
    "boundingbox",
    "bounding_box",
    "box",
    "boxes",
    "bboxes",
    "coordinates",
    "coordinate",
    "layout",
}


def _contains_numeric_coordinate(value: Any) -> bool:
    """Return true only for an explicit numeric bbox/coordinate payload."""
    if isinstance(value, list):
        if len(value) >= 4 and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in value[:4]
        ):
            return True
        return any(_contains_numeric_coordinate(item) for item in value)
    if isinstance(value, dict):
        keys = {str(key).lower().replace("-", "_") for key in value}
        for coordinate_keys in (("x0", "y0", "x1", "y1"), ("left", "top", "right", "bottom")):
            if set(coordinate_keys) <= keys and all(
                isinstance(value[key], (int, float)) and not isinstance(value[key], bool)
                for key in coordinate_keys
            ):
                return True
        return any(_contains_numeric_coordinate(item) for item in value.values())
    return False


def _has_machine_coordinates(parsed: dict[str, Any], content: str) -> bool:
    """Accept only explicit numeric coordinate structures.

    LOC markers alone are not sufficient evidence for a page-image bbox: the
    provider may emit opaque token IDs without exposing a coordinate mapping.
    """
    number = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    if re.search(
        rf'(?i)["\']?(?:bbox|bounding[_ ]?box|coordinates?)["\']?\s*[:=]\s*'
        rf'\[\s*{number}\s*,\s*{number}\s*,\s*{number}\s*,\s*{number}(?:\s*,|\s*\])',
        content,
    ):
        return True

    def visit(value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = str(key).lower().replace("-", "_").replace(" ", "")
                if normalized_key in _COORDINATE_KEYS and _contains_numeric_coordinate(child):
                    return True
                if visit(child):
                    return True
        elif isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    return visit(parsed)


def _probe_succeeded(summary: dict[str, Any]) -> bool:
    """Require a usable response before accepting a probe artifact."""
    total_pages = summary.get("total_pages", 0)
    return (
        isinstance(total_pages, int)
        and total_pages > 0
        and summary.get("all_responses_successful") is True
        and summary.get("all_response_models_match") is True
        and summary.get("all_expected_fragments_found") is True
        and summary.get("raw_exact_pages") == total_pages
    )


def run_probe(url: str, model: str, output: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="phase4-glm-ocr-") as tmp:
        root = Path(tmp) / "gold"
        gold = build_gold_set(root)
        wanted = {
            "scanned-01-p1": ("scanned-01.pdf", "image/jpeg"),
            "photo-01-p1": ("photo-01.jpg", "image/jpeg"),
        }
        pages = {page.gold_page_id: page for page in gold.pages}
        results: list[dict[str, Any]] = []
        for page_id, (filename, mime) in wanted.items():
            page = pages[page_id]
            source = root / filename
            image = _render_pdf_page(source) if source.suffix.lower() == ".pdf" else source.read_bytes()
            request_body, raw, elapsed, response_status = _request(url, model, image, mime)
            raw_utf8 = raw.decode("utf-8")
            parsed = json.loads(raw_utf8)
            content = _content(parsed)
            expected = page.expected_text or ""
            response_model = parsed.get("model")
            results.append(
                {
                    "gold_page_id": page_id,
                    "file_ref": filename,
                    "route": ExtractionRoute.VISION_OCR.value,
                    "expected_text": expected,
                    "recognized_text": content,
                    "exact_text": content == expected,
                    "normalized_exact": _normalize(content) == _normalize(expected),
                    "expected_fragments_found": [
                        target.text for target in page.targets if _normalize(target.text) in _normalize(content)
                    ],
                    "expected_fragment_count": len(page.targets),
                    "machine_coordinates_present": _has_machine_coordinates(parsed, content),
                    "request_image_sha256": _sha256(image),
                    "request_sha256": _sha256(request_body),
                    "response_status": response_status,
                    "response_model": response_model,
                    "model_matches_request": response_model == model,
                    "finish_reason": parsed["choices"][0].get("finish_reason"),
                    "elapsed_seconds": round(elapsed, 3),
                    "response_sha256": _sha256(raw),
                    "raw_response_base64": base64.b64encode(raw).decode("ascii"),
                    "raw_response_utf8": raw_utf8,
                }
            )

    summary = {
        "schema": "phase4_real_omlx_probe_v1",
        "server": url,
        "model": model,
        "synthetic_no_phi": True,
        "pages": results,
        "text_exact_pages": sum(item["normalized_exact"] for item in results),
        "raw_exact_pages": sum(item["exact_text"] for item in results),
        "total_pages": len(results),
        "all_responses_successful": all(item["response_status"] == 200 for item in results),
        "all_response_models_match": all(item["model_matches_request"] for item in results),
        "all_expected_fragments_found": all(
            len(item["expected_fragments_found"]) == item["expected_fragment_count"]
            for item in results
        ),
        "layout_coordinates_observed": any(item["machine_coordinates_present"] for item in results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8002")
    parser.add_argument("--model", default="GLM-OCR-bf16")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run_probe(args.url, args.model, args.output)
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "pages"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if _probe_succeeded(summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
