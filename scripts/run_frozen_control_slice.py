#!/usr/bin/env python3
"""Read-only single-batch probe through the product protocol-control harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_control_agent_transport import protocol_control_transport_from_environment
from app.agents.protocol_control_deconstructor import (
    DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE,
    ProtocolControlAgentRunner,
)
from app.domain.contracts.agent_io import ProtocolDeconstructionInput
from app.domain.contracts.protocol_controls import (
    ProtocolControlDiscoveryPlan, ProtocolControlDiscoveryToDeepPlan,
    ProtocolSectionCoverageManifest,
)
from app.domain.contracts.rules import WorkflowStage
from app.protocols.protocol_control_planning import plan_protocol_control_deep_batches_from_discovery
from app.storage.codecs import verify_payload_sha256
from app.services.protocol_control_execution import _validate_deep_batch_output


def replan_frozen_slice(payload: dict, previous: ProtocolControlDiscoveryToDeepPlan,
                        max_owned_units: int) -> ProtocolControlDiscoveryToDeepPlan:
    """Repartition the complete frozen ledger; never select or drop source units."""
    discovery = ProtocolControlDiscoveryPlan.model_validate(payload["discovery_plan"])
    source = ProtocolDeconstructionInput.model_validate(payload["source_input"])
    decisions = {item.structure_unit_id: item for item in previous.discovery_decisions}
    return plan_protocol_control_deep_batches_from_discovery(
        ProtocolSectionCoverageManifest.model_validate(payload["coverage_manifest"]),
        discovery,
        [[decisions[unit_id] for unit_id in batch.target_structure_unit_ids]
         for batch in discovery.batches],
        source.parent_rule_catalog, source.required_procedure_catalog,
        max_owned_units_per_batch=max_owned_units,
        workflow_stages=[WorkflowStage.model_validate(item)
                         for item in payload.get("workflow_stages", [])],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="只读复核冻结方案控制批次")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--batch-number", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-schema-repairs", type=int, default=2)
    parser.add_argument("--replan-max-owned-units", type=int,
                        help="仅在内存中用现有规划器重新分包；批次序号指新计划，不改旧作业")
    parser.add_argument("--run", action="store_true", help="确认发起真实产品模型请求")
    args = parser.parse_args()
    if args.batch_number < 1 or args.max_schema_repairs < 0:
        parser.error("批次序号须从1开始，修订预算不得为负")
    if args.replan_max_owned_units is not None and args.replan_max_owned_units < 1:
        parser.error("重新分包的单元上限须为正整数")
    database = args.database.resolve(strict=True)
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        job = connection.execute(
            "SELECT state, payload_json, payload_sha256 FROM jobs WHERE job_id=?", (args.job_id,)
        ).fetchone()
        closure = connection.execute(
            "SELECT payload_json, payload_sha256 FROM job_checkpoints "
            "WHERE job_id=? AND step_id='deterministic_closure' ORDER BY created_at DESC LIMIT 1",
            (args.job_id,),
        ).fetchone()
    finally:
        connection.close()
    if job is None or closure is None or job[0] not in {"failed_final", "cancelled", "completed"}:
        raise ValueError("只接受已有终态且具有冻结深审计划的作业")
    payload = verify_payload_sha256(job[1], job[2])
    saved_closure = verify_payload_sha256(closure[0], closure[1])
    previous = ProtocolControlDiscoveryToDeepPlan.model_validate(saved_closure["deep_plan"])
    plan = (replan_frozen_slice(payload, previous, args.replan_max_owned_units)
            if args.replan_max_owned_units is not None else previous)
    batch = next((item for item in plan.batches
                  if item.batch_number == args.batch_number), None)
    if batch is None:
        raise ValueError("冻结计划不存在该批次")
    identity = {
        "source_job_id": args.job_id,
        "source_job_state": job[0],
        "source_job_payload_sha256": job[2],
        "source_closure_sha256": closure[1],
        "source_plan_id": previous.plan_id,
        "diagnostic_plan_id": plan.plan_id,
        "replan_max_owned_units": args.replan_max_owned_units,
        "batch_number": args.batch_number,
        "batch_id": batch.batch_id,
        "protocol_document_sha256": plan.protocol_document_sha256,
        "owned_unit_count": len(batch.owned_units),
        "context_unit_count": len(batch.context_units),
        "prompt_template_sha256": hashlib.sha256(
            DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE.encode("utf-8")
        ).hexdigest(),
        "claims_complete": False,
    }
    if not args.run:
        print(json.dumps(identity, ensure_ascii=False, sort_keys=True))
        return 0
    if args.output.exists():
        raise FileExistsError("诊断输出已存在，不覆盖既有回执")
    transport = protocol_control_transport_from_environment()
    identity["model_identity"] = {
        "requested": transport.model,
        "reported": transport.verify_model_identity(),
        "backend": transport.backend,
        "effort": transport.reasoning_effort,
    }
    result = ProtocolControlAgentRunner(
        max_schema_repairs=args.max_schema_repairs,
    ).run(
        batch, transport,
        output_validator=lambda output: _validate_deep_batch_output(batch, output),
    )
    record = {**identity, "frozen_batch": batch.model_dump(mode="json"),
              "result": result.model_dump(mode="json")}
    record["call_receipts"] = transport.take_call_receipts()
    record["attempt_raw_outputs"] = [attempt.raw_output_text for attempt in result.attempts]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "batch_id": batch.batch_id,
        "status": result.status,
        "attempt_count": len(result.attempts),
        "source_statement_count": len(result.source_interpretation.statements)
        if result.source_interpretation else None,
        "source_review_count": len(result.source_target_review.items)
        if result.source_target_review else None,
        "result_path": str(args.output.resolve()),
    }, ensure_ascii=False))
    return 0 if result.final_output is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
