#!/usr/bin/env python3
"""Run one bounded MTPLX call for the D001 II laboratory representative group."""

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
    build_protocol_control_agent_prompt,
    hydrate_protocol_control_agent_output,
    parse_protocol_control_agent_wire,
)
from app.domain.contracts.protocol_controls import (
    ProtocolControlDispositionBatch,
    stable_protocol_control_batch_id,
)
from app.protocols.protocol_control_planning import detect_required_action_kinds


ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / "artifacts/phase5-slice60zs-laboratory-cross-chapter-closure-20260828"
OUTPUT = ROOT / "artifacts/phase5-slice60zt-laboratory-single-mtplx-20260828"
MODEL = "mtplx-qwen38-27b-optimized-quality"
EXPECTED_DOCX_SHA256 = (
    "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
)
EXPECTED_PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
EXPECTED_OWNED_REFS = (
    "body.p798",
    "body.p799",
    "body.p800",
    "body.t11.r0",
    "body.t11.r1",
    "body.t11.r2",
    "body.t11.r3",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_batch(ordinal: int) -> ProtocolControlDispositionBatch:
    path = SOURCE / f"package-{ordinal}/execution/batch.json"
    return ProtocolControlDispositionBatch.model_validate_json(path.read_text())


def _combined_batch() -> ProtocolControlDispositionBatch:
    left = _load_batch(70)
    right = _load_batch(71)
    assert left.coverage_manifest_id == right.coverage_manifest_id
    assert left.protocol_version_id == right.protocol_version_id
    assert left.study_phase == right.study_phase
    assert left.known_official_targets == right.known_official_targets
    assert left.known_procedure_targets == right.known_procedure_targets

    owned = [*left.owned_units, *right.owned_units]
    assert tuple(unit.source_ref for unit in owned) == EXPECTED_OWNED_REFS
    owned_ids = [unit.structure_unit_id for unit in owned]
    owned_id_set = set(owned_ids)
    context_by_id = {
        unit.structure_unit_id: unit
        for unit in sorted(
            [*left.context_units, *right.context_units],
            key=lambda unit: (unit.source_order, unit.structure_unit_id),
        )
        if unit.structure_unit_id not in owned_id_set
    }
    context = list(context_by_id.values())
    return ProtocolControlDispositionBatch(
        batch_id=stable_protocol_control_batch_id(
            left.coverage_manifest_id,
            1,
            owned_ids,
        ),
        coverage_manifest_id=left.coverage_manifest_id,
        protocol_version_id=left.protocol_version_id,
        study_phase=left.study_phase,
        batch_number=1,
        batch_total=1,
        priority_rank=max(unit.priority_rank for unit in owned),
        owned_units=owned,
        context_units=context,
        owned_structure_unit_ids=owned_ids,
        context_structure_unit_ids=[unit.structure_unit_id for unit in context],
        owned_source_span_ids=sorted(
            {span_id for unit in owned for span_id in unit.source_span_ids}
        ),
        context_source_span_ids=sorted(
            {span_id for unit in context for span_id in unit.source_span_ids}
        ),
        owned_required_action_kinds_by_structure_unit_id={
            unit.structure_unit_id: list(action_kinds)
            for unit in owned
            if (action_kinds := detect_required_action_kinds(unit.excerpt))
        },
        known_official_targets=left.known_official_targets,
        known_procedure_targets=left.known_procedure_targets,
        known_workflow_stage_targets=[],
    )


def main() -> int:
    provenance = json.loads((SOURCE / "freeze_provenance.json").read_text())
    review = json.loads((SOURCE / "dryrun-review.json").read_text())
    assert provenance["docx_sha256"] == EXPECTED_DOCX_SHA256
    assert provenance["plan_id"] == EXPECTED_PLAN_ID
    assert (
        review["parent_checklist_prompt_evidence"]["go_stop_prompt_layer"]["issues"]
        == []
    )
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite immutable output: {OUTPUT}")
    execution = OUTPUT / "execution"
    execution.mkdir(parents=True)

    batch = _combined_batch()
    agent_input = ProtocolControlAgentInput.from_batch(batch)
    prompt = build_protocol_control_agent_prompt(agent_input)
    required_text = (
        "筛选和基线访视可合并",
        "本检查应空腹采样",
        "根据新出现的安全性数据",
        "经研究者评估如果参与研究将可能对参与者构成不可接受的风险",
    )
    assert all(text in prompt for text in required_text)

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
    _write_json(
        OUTPUT / "replay-summary.json",
        {
            "schema_version": "phase5/laboratory-single-mtplx-replay/v1",
            "claims_complete": False,
            "control_points_published": False,
            "source_artifact": str(SOURCE.relative_to(ROOT)),
            "docx_sha256": EXPECTED_DOCX_SHA256,
            "plan_id": EXPECTED_PLAN_ID,
            "batch_id": batch.batch_id,
            "owned_source_refs": list(EXPECTED_OWNED_REFS),
            "context_source_refs": [unit.source_ref for unit in batch.context_units],
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
        },
    )
    print((OUTPUT / "replay-summary.json").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
