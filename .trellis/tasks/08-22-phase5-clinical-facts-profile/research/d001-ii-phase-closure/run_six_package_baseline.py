#!/usr/bin/env python3
"""Run an explicit subset of the six frozen D001 phase-semantics packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.agents.phase_applicability import (  # noqa: E402
    PhaseApplicabilityAgentInput,
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentRunner,
    build_phase_applicability_agent_prompt,
)
from app.agents.phase_applicability_transport import (  # noqa: E402
    OpenAICompatiblePhaseApplicabilityAgentTransport,
)


ORDINALS = (59, 63, 69, 70, 73, 79)
DEFAULT_INPUT = (
    REPO
    / "artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826"
    / "controlled-input.json"
)
DEFAULT_OUTPUT = DEFAULT_INPUT.parent / "qwen38-baseline-host-real-run-20260826"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class TimedTransport:
    def __init__(
        self,
        transport: OpenAICompatiblePhaseApplicabilityAgentTransport,
        progress_dir: Path,
    ):
        self.transport = transport
        self.progress_dir = progress_dir
        self.calls: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []

    def _checkpoint(self) -> None:
        _write_json(
            self.progress_dir / "transport-calls.in-progress.json",
            self.calls,
        )
        _write_json(
            self.progress_dir / "raw-responses.in-progress.json",
            self.responses,
        )

    def _call(self, kind: str, prompt: str, session_id: str | None = None):
        started = perf_counter()
        try:
            response = (
                self.transport.start(prompt=prompt)
                if session_id is None
                else self.transport.continue_session(
                    session_id=session_id,
                    prompt=prompt,
                )
            )
        except Exception as exc:
            self.calls.append(
                {
                    "kind": kind,
                    "status": "error",
                    "elapsed_seconds": round(perf_counter() - started, 6),
                    "prompt_char_count": len(prompt),
                    "prompt_sha256": _sha256(prompt),
                    "session_id": getattr(exc, "session_id", session_id),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            self._checkpoint()
            raise
        elapsed = round(perf_counter() - started, 6)
        self.calls.append(
            {
                "kind": kind,
                "status": "ok",
                "elapsed_seconds": elapsed,
                "prompt_char_count": len(prompt),
                "prompt_sha256": _sha256(prompt),
                "session_id": response.session_id,
                "output_char_count": len(response.text),
                "output_sha256": _sha256(response.text),
            }
        )
        self.responses.append(
            {
                "kind": kind,
                "session_id": response.session_id,
                "text": response.text,
            }
        )
        self._checkpoint()
        return response

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        return self._call("start", prompt)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        return self._call("repair", prompt, session_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controlled-input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--ordinals",
        type=int,
        nargs="+",
        choices=ORDINALS,
        default=list(ORDINALS),
    )
    args = parser.parse_args()
    ordinals = tuple(dict.fromkeys(args.ordinals))

    controlled = json.loads(args.controlled_input.read_text(encoding="utf-8"))
    contract = controlled["execution_contract"]
    selection = controlled["selection"]
    if contract["ready_for_model_execution"] is not True:
        raise RuntimeError("六包冻结输入尚未通过提示词合同门禁")
    if tuple(selection["selected_package_ordinals"]) != ORDINALS:
        raise RuntimeError("代表包序号与冻结六包不一致")
    if selection["selected_package_count"] != 6:
        raise RuntimeError("受控输入必须保留六个冻结代表包")

    package_records = {
        item["package_ordinal"]: item for item in controlled["packages"]
    }
    output_dir = args.output_dir.resolve()
    run_started = datetime.now(UTC)
    results: list[dict[str, Any]] = []

    for ordinal in ordinals:
        record = package_records[ordinal]
        package_dir = output_dir / f"package-{ordinal:04d}"
        input_path = args.controlled_input.parent / (
            f"package-{ordinal:04d}-agent-input.json"
        )
        agent_input = PhaseApplicabilityAgentInput.model_validate_json(
            input_path.read_text(encoding="utf-8")
        )
        prompt = build_phase_applicability_agent_prompt(agent_input)
        if len(prompt) != record["prompt_char_count"]:
            raise RuntimeError(f"包 {ordinal} prompt 字符数漂移")
        if _sha256(prompt) != record["prompt_sha256"]:
            raise RuntimeError(f"包 {ordinal} prompt 哈希漂移")

        transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
            backend="omlx",
            base_url="http://127.0.0.1:8001",
            model="Qwen3.8-27B-oQ8e-fp16-mtp",
            reasoning_effort="default",
            max_tokens=60000,
            temperature=0.0,
            timeout=600.0,
            max_retries=0,
        )
        timed = TimedTransport(transport, package_dir)
        started = perf_counter()
        result = PhaseApplicabilityAgentRunner(
            max_transport_retries=1,
            max_schema_repairs=2,
        ).run(agent_input, timed)
        elapsed = round(perf_counter() - started, 6)
        package_result = {
            "package_id": result.package_id,
            "package_ordinal": ordinal,
            "selection_strata": record["selection_strata"],
            "prompt_char_count": len(prompt),
            "owned_unit_count": len(agent_input.target_units),
            "context_unit_count": len(agent_input.frozen_package.context_units),
            "elapsed_seconds": elapsed,
            "status": result.status,
            "session_id": result.session_id,
            "attempt_count": len(result.attempts),
            "attempt_outcomes": [item.outcome for item in result.attempts],
            "issue_count": sum(len(item.issues) for item in result.attempts),
            "calls": timed.calls,
            "response_count": len(timed.responses),
            "final_disposition_counts": {},
        }
        if result.final_output is not None:
            counts: dict[str, int] = {}
            for item in result.final_output.results:
                key = item.final_disposition.value
                counts[key] = counts.get(key, 0) + 1
            package_result["final_disposition_counts"] = counts
        _write_json(package_dir / "runner-result.json", result.model_dump(mode="json"))
        _write_json(package_dir / "transport-calls.json", timed.calls)
        _write_json(package_dir / "raw-responses.json", timed.responses)
        if timed.responses:
            _write_json(
                package_dir / "conversation-history.json",
                list(transport.history(result.session_id)),
            )
        _write_json(package_dir / "metrics.json", package_result)
        (package_dir / "transport-calls.in-progress.json").unlink(missing_ok=True)
        (package_dir / "raw-responses.in-progress.json").unlink(missing_ok=True)
        results.append(package_result)
        _write_json(
            output_dir / "progress.json",
            {
                "completed_package_ordinals": [
                    item["package_ordinal"] for item in results
                ],
                "results": results,
            },
        )

    summary = {
        "schema_version": "phase5/d001-ii-six-package-host-baseline/v1",
        "started_at": run_started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "model": "Qwen3.8-27B-oQ8e-fp16-mtp",
        "reasoning_effort": "default",
        "temperature": 0.0,
        "configured_max_tokens": 60000,
        "selected_package_ordinals": list(ordinals),
        "excluded_frozen_package_count": 137 - len(ordinals),
        "results": results,
        "accepted_package_count": sum(
            item["status"] == "已解析" for item in results
        ),
        "needs_review_package_count": sum(
            item["status"] == "需要核对" for item in results
        ),
        "total_elapsed_seconds": round(
            sum(item["elapsed_seconds"] for item in results), 6
        ),
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["needs_review_package_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
