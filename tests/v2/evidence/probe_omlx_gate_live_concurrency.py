"""Run concurrent PHI-free GLM-OCR requests through the shared oMLX gate."""
from __future__ import annotations

import argparse
import base64
import json
import multiprocessing
import os
import queue
import tempfile
import time
from pathlib import Path
from typing import Any

from app.services.omlx_gate import OmlxGateClient, omlx_http_inference
from tests.v2.evidence.goldgen import build_gold_set


def _normalize(text: str) -> str:
    return "".join(text.split())


def _worker(
    *,
    server_url: str,
    image_path: str,
    expected_text: str,
    ready: Any,
    start: Any,
    results: Any,
) -> None:
    client = OmlxGateClient(
        owner=f"phase4-live-concurrency-{os.getpid()}",
        acquire_timeout=600,
    )
    inference = omlx_http_inference(server_url, gate=client)
    image_bytes = Path(image_path).read_bytes()
    payload = {
        "prompt": "请逐字识别图片中的全部文字，保留原有行序和否定词。只返回识别文字。",
        "image": {
            "mime": "image/jpeg",
            "data_base64": base64.b64encode(image_bytes).decode("ascii"),
        },
    }
    ready.put(os.getpid())
    if not start.wait(timeout=120):
        results.put({"ok": False, "error": "并发起始信号超时"})
        return
    started = time.monotonic()
    try:
        response, lease = client.run_under_lease(
            inference,
            request_payload=payload,
            image_bytes=image_bytes,
        )
        results.put(
            {
                "ok": True,
                "model": lease.get("model"),
                "exact_text": response.recognized_text == expected_text,
                "normalized_exact": (
                    _normalize(response.recognized_text) == _normalize(expected_text)
                ),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
    except Exception as exc:  # noqa: BLE001 - probe must retain terminal class only
        results.put(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )


def run_probe(*, server_url: str, workers: int, output: Path) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    start = context.Event()
    results = context.Queue()
    client = OmlxGateClient(owner="phase4-live-concurrency-controller")

    before = client.status()
    if before["active"]["ocr"] != 0:
        raise RuntimeError("共享 OCR 门禁当前已有任务，无法得到独立并发测量")

    with tempfile.TemporaryDirectory(prefix="phase4-live-gate-") as tmp:
        root = Path(tmp) / "gold"
        gold = build_gold_set(root)
        page = next(item for item in gold.pages if item.gold_page_id == "photo-01-p1")
        processes = [
            context.Process(
                target=_worker,
                kwargs={
                    "server_url": server_url,
                    "image_path": str(root / "photo-01.jpg"),
                    "expected_text": page.expected_text or "",
                    "ready": ready,
                    "start": start,
                    "results": results,
                },
            )
            for _ in range(workers)
        ]
        for process in processes:
            process.start()
        for _ in processes:
            ready.get(timeout=120)

        start.set()
        peak = 0
        while any(process.is_alive() for process in processes):
            peak = max(peak, int(client.status()["active"]["ocr"]))
            time.sleep(0.01)
        for process in processes:
            process.join(timeout=10)

        rows: list[dict[str, Any]] = []
        while len(rows) < workers:
            try:
                rows.append(results.get(timeout=5))
            except queue.Empty:
                break

    after = client.status()
    summary = {
        "schema": "phase4_live_omlx_gate_concurrency_v1",
        "server": server_url,
        "synthetic_no_phi": True,
        "requested_workers": workers,
        "returned_results": len(rows),
        "successful_requests": sum(bool(row.get("ok")) for row in rows),
        "exact_text_requests": sum(bool(row.get("exact_text")) for row in rows),
        "normalized_exact_requests": sum(
            bool(row.get("normalized_exact")) for row in rows
        ),
        "observed_gate_peak": peak,
        "configured_ocr_limit": int(after["limits"]["ocr"]),
        "leases_remaining": int(after["active"]["ocr"]),
        "results": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run_probe(
        server_url=args.url,
        workers=args.workers,
        output=args.output,
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if (
        summary["returned_results"] == args.workers
        and summary["successful_requests"] == args.workers
        and summary["normalized_exact_requests"] == args.workers
        and 1 <= summary["observed_gate_peak"] <= summary["configured_ocr_limit"]
        and summary["leases_remaining"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
