#!/usr/bin/env python3
"""Run one immutable MTPLX call for the action-bearing laboratory package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter

from app.agents.protocol_control_agent_transport import (
    OpenAICompatibleProtocolControlAgentTransport,
)
from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentInput,
    hydrate_protocol_control_agent_output,
    parse_protocol_control_agent_wire,
)
from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_hydrated_result_links,
)


ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / "artifacts/phase5-slice60zu-laboratory-action-preservation-rerun-20260828"
OUTPUT = ROOT / "artifacts/phase5-slice60zv-laboratory-action-gate-call-20260828"
MODEL = "mtplx-qwen38-27b-optimized-quality"
EXPECTED_DOCX_SHA256 = (
    "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
)
EXPECTED_PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
EXPECTED_BATCH_ID = "pcb-00bbc4e9f4de2f418ceb7ad1"
EXPECTED_PROMPT_SHA256 = (
    "3f7d2fe7e3d405201150e1e7942c2294487c8e608803e843a5ec096c78bc7612"
)
P799_UNIT_ID = "su-ebd9aa3df8c86a8ab785ba14"
P799_ACTIONS = ["collect_biospecimen", "follow_specified_procedure"]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    provenance = json.loads((SOURCE / "freeze_provenance.json").read_text())
    review = json.loads((SOURCE / "dryrun-review.json").read_text())
    execution_source = SOURCE / "package-70/execution"
    batch = ProtocolControlDispositionBatch.model_validate_json(
        (execution_source / "batch.json").read_text()
    )
    agent_input = ProtocolControlAgentInput.model_validate_json(
        (execution_source / "agent_input.json").read_text()
    )
    prompt = (execution_source / "prompt.txt").read_text()

    assert provenance["docx_sha256"] == EXPECTED_DOCX_SHA256
    assert provenance["plan_id"] == EXPECTED_PLAN_ID
    assert (
        review["parent_checklist_prompt_evidence"]["go_stop_prompt_layer"]["issues"]
        == []
    )
    assert batch.batch_id == EXPECTED_BATCH_ID
    assert _sha256(prompt) == EXPECTED_PROMPT_SHA256
    assert ProtocolControlAgentInput.from_batch(batch) == agent_input
    assert batch.owned_required_action_kinds_by_structure_unit_id == {
        P799_UNIT_ID: P799_ACTIONS
    }
    assert all(token not in prompt for token in (*P799_ACTIONS, "REQUIRED_ACTION"))
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite immutable output: {OUTPUT}")

    execution = OUTPUT / "execution"
    execution.mkdir(parents=True)
    (execution / "prompt.txt").write_text(prompt, encoding="utf-8")
    _write_json(execution / "batch.json", batch.model_dump(mode="json"))
    _write_json(execution / "agent-input.json", agent_input.model_dump(mode="json"))

    transport = OpenAICompatibleProtocolControlAgentTransport(
        backend="mtplx",
        provider="mtplx",
        base_url="http://127.0.0.1:8002",
        model=MODEL,
        reasoning_effort="medium",
        max_tokens=16384,
        temperature=0,
        timeout=7200,
        max_retries=0,
    )
    started = perf_counter()
    response = transport.start(prompt=prompt)
    elapsed = round(perf_counter() - started, 6)
    (execution / "raw-response.json").write_text(response.text, encoding="utf-8")

    wire = parse_protocol_control_agent_wire(response.text)
    hydrated = hydrate_protocol_control_agent_output(wire, batch)
    _write_json(execution / "hydrated-output.json", hydrated.model_dump(mode="json"))

    gate_report: dict[str, object] = {"accepted": True, "issues": []}
    try:
        _check_hydrated_result_links(
            hydrated,
            known_procedure_targets=batch.known_procedure_targets,
            unit_by_id={unit.structure_unit_id: unit for unit in batch.owned_units},
            study_phase=batch.study_phase,
            owned_required_action_kinds_by_structure_unit_id=(
                batch.owned_required_action_kinds_by_structure_unit_id
            ),
        )
    except ProtocolControlGateError as exc:
        gate_report = {
            "accepted": False,
            "issues": [
                {
                    "code": exc.code,
                    "message": str(exc),
                    "structure_unit_ids": list(exc.structure_unit_ids),
                }
            ],
        }
    _write_json(OUTPUT / "batch-gate-report.json", gate_report)

    summary = {
        "schema_version": "phase5/laboratory-action-gate-call/v1",
        "claims_complete": False,
        "control_points_published": False,
        "source_artifact": str(SOURCE.relative_to(ROOT)),
        "docx_sha256": EXPECTED_DOCX_SHA256,
        "plan_id": EXPECTED_PLAN_ID,
        "batch_id": batch.batch_id,
        "owned_source_refs": [unit.source_ref for unit in batch.owned_units],
        "prompt_char_count": len(prompt),
        "prompt_sha256": _sha256(prompt),
        "raw_response_char_count": len(response.text),
        "raw_response_sha256": _sha256(response.text),
        "session_id": response.session_id,
        "elapsed_seconds": elapsed,
        "transport_call_count": 1,
        "transport": {
            "provider": transport.provider,
            "base_url": transport.base_url,
            "model": transport.model,
            "reasoning_effort": transport.reasoning_effort,
            "max_tokens": transport.max_tokens,
            "temperature": transport.temperature,
            "max_retries": transport.max_retries,
            "strict_control_schema": transport.uses_control_response_format,
        },
        "candidate_count": len(hydrated.candidates),
        "disposition_count": len(hydrated.dispositions),
        "batch_gate_accepted": gate_report["accepted"],
    }
    _write_json(OUTPUT / "replay-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
