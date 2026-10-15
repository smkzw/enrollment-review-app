#!/usr/bin/env python3
"""Read-only single-batch probe through the product protocol-control harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_control_agent_transport import (
    PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS,
    protocol_control_transport_from_environment,
)
from app.agents.protocol_control_fixed_flow import BASELINE, FIXED_FLOW, workflow_template
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
from app.storage.config import resolve_data_paths
from app.llm.logical_call_budget import LogicalCallBudget
from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
from app.services.protocol_control_execution import (
    _transport_identity, _validate_deep_batch_output, _validate_saved_source_review,
)


def frozen_code_identity():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
        "scripts/run_frozen_control_slice.py",
        "app/agents/protocol_control_deconstructor.py",
        "app/agents/protocol_control_fixed_flow.py",
        "app/agents/protocol_control_agent_transport.py",
        "app/services/protocol_control_execution.py",
        "app/agents/protocol_control_stage_compiler.py",
        "app/llm/logical_call_budget.py",
        "app/protocols/protocol_control_gate.py",
        "app/protocols/protocol_control_planning.py",
        "app/agents/protocol_control_source_interpretation.py",
        "app/agents/protocol_control_candidate_alignment.py",
        "app/domain/contracts/protocol_controls.py",
        "app/domain/contracts/control_evidence_policy.py",
        "app/protocols/control_scope_sources.py",
        "app/protocols/protocol_control_repair_errors.py",
    )}


def execute_frozen_slice(batch, transport, budget, *, workflow_variant, max_schema_repairs):
    """Exercise the product runner and saved-result gate, not a short-answer probe."""
    template = workflow_template(DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE, workflow_variant)
    started = time.monotonic()
    result = None
    failure = None
    consumer_validated = False
    receipts = []
    try:
        transport.bind_logical_call_budget(budget)
        result = ProtocolControlAgentRunner(max_schema_repairs=max_schema_repairs).run(
            batch, transport, prompt_template=template, workflow_variant=workflow_variant,
            output_validator=lambda output: _validate_deep_batch_output(batch, output),
        )
        if result.final_output is not None:
            # Use the same read-back contract as a persisted product batch.
            restored = type(result).model_validate_json(result.model_dump_json())
            _validate_deep_batch_output(batch, restored.final_output)
            _validate_saved_source_review(batch, restored)
            consumer_validated = True
    except Exception as exc:
        failure = {"type": type(exc).__name__, "code": getattr(exc, "code", None),
                   "detail": str(exc)}
    finally:
        try:
            receipts = transport.take_call_receipts()
        finally:
            transport.bind_logical_call_budget(None)
    path_executed = result.workflow_path_executed if result else "not_started"
    front_executed = path_executed == "front_stage_flow"
    return {
        "workflow_requested": workflow_variant,
        "workflow_executed": (FIXED_FLOW if front_executed else BASELINE
                              if path_executed == "baseline_wire" else None),
        "workflow_path_executed": path_executed,
        "consumer_scope": "saved_result_gate_only",
        "candidate_path_used": front_executed,
        "consumer_validated": consumer_validated,
        "duration_seconds": time.monotonic() - started,
        "result": result.model_dump(mode="json") if result else None,
        "failure": failure,
        "call_receipts": receipts,
        "logical_call_budget": budget.snapshot(),
        "receipt_format_version": "frozen-control-slice/v2",
        "attempt_raw_outputs": [{
            "attempt": attempt.attempt, "session_id": attempt.session_id,
            "sha256": attempt.raw_output_sha256, "characters": attempt.raw_output_chars,
            "outcome": attempt.outcome, "error_classes": attempt.error_classes,
            "text": attempt.raw_output_text,
        } for attempt in result.attempts] if result else [],
        "claims_complete": False,
    }


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
    parser.add_argument("--workflow-variant", choices=[BASELINE, FIXED_FLOW], default=BASELINE)
    parser.add_argument("--max-requests", type=int,
                        help="真实试跑必须冻结累计物理请求上限，包含重试/格式修复/来源复核")
    parser.add_argument("--replan-max-owned-units", type=int,
                        help="仅在内存中用现有规划器重新分包；批次序号指新计划，不改旧作业")
    parser.add_argument("--run", action="store_true", help="确认发起真实产品模型请求")
    args = parser.parse_args()
    if args.batch_number < 1 or args.max_schema_repairs < 0:
        parser.error("批次序号须从1开始，修订预算不得为负")
    if args.replan_max_owned_units is not None and args.replan_max_owned_units < 1:
        parser.error("重新分包的单元上限须为正整数")
    if (args.max_requests is not None and args.max_requests < 1) or (args.run and args.max_requests is None):
        parser.error("真实试跑须显式指定正整数 --max-requests，不自动扩大预算")
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
        "workflow_requested": args.workflow_variant,
        "request_limit": args.max_requests,
        "code_identity": frozen_code_identity(),
    }
    if not args.run:
        print(json.dumps(identity, ensure_ascii=False, sort_keys=True))
        return 0
    if args.output.exists():
        raise FileExistsError("诊断输出已存在，不覆盖既有回执")
    transport = protocol_control_transport_from_environment()
    route = _transport_identity(transport, stage="deep")
    code_identity = identity["code_identity"]
    common_envelope = {
        "batch": batch.model_dump(mode="json"), "route": route,
        "code_identity": code_identity,
        "request_limit": args.max_requests, "max_schema_repairs": args.max_schema_repairs,
        "baseline_prompt": identity["prompt_template_sha256"],
    }
    envelope_sha = hashlib.sha256(json.dumps(common_envelope, ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    contract_sha = hashlib.sha256((envelope_sha + workflow_template(
        DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE, args.workflow_variant
    )).encode("utf-8")).hexdigest()
    logical_id = hashlib.sha256((envelope_sha + args.workflow_variant).encode("utf-8")).hexdigest()
    cache = _ProtocolSemanticBatchFileCache(
        resolve_data_paths(str(database.parent / "rv1001-isolated-call-ledger")), logical_id,
    )
    saved = cache.load_call_budget(logical_id)
    if saved is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump({**identity, "comparison_envelope_sha256": envelope_sha,
                       "logical_task_id": logical_id, "consumer_validated": False,
                       "failure": {"code": "BUDGET_LEDGER_EXISTS"},
                       "logical_call_budget": saved}, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"failure": "BUDGET_LEDGER_EXISTS", "output": str(args.output)}))
        return 2
    budget = LogicalCallBudget(logical_id, max_requests=args.max_requests,
        max_output_tokens=args.max_requests * max(transport.max_tokens, PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS),
        contract_sha256=contract_sha, persist=cache.store_call_budget)
    identity.update(route_identity=route, code_identity=code_identity, comparison_envelope_sha256=envelope_sha,
                    execution_contract_sha256=contract_sha, logical_task_id=logical_id,
                    budget_scope="all_generation_requests_including_identity_probe;catalog_reads_excluded",
                    source_job_frozen_routes=payload.get("frozen_model_routes"),
                    route_scope="new_isolated_comparison;source_only_not_reusing_old_model_answers")
    # Identity checking is an adapter preflight, not a successful clinical read.
    try:
        transport.bind_logical_call_budget(budget)
        reported = transport.verify_model_identity()
    except Exception as exc:
        record = {"failure": {"type": type(exc).__name__, "code": getattr(exc, "code", None),
                              "detail": str(exc)}, "consumer_validated": False,
                  "call_receipts": transport.take_call_receipts(),
                  "logical_call_budget": budget.snapshot()}
    else:
        identity["model_identity"] = {"requested": transport.model, "reported": reported,
                                      "backend": transport.backend, "effort": transport.reasoning_effort}
        record = execute_frozen_slice(batch, transport, budget, workflow_variant=args.workflow_variant,
                                      max_schema_repairs=args.max_schema_repairs)
    finally:
        transport.bind_logical_call_budget(None)
    record = {**identity, "frozen_batch": batch.model_dump(mode="json"), **record}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "batch_id": batch.batch_id,
        "status": (record.get("result") or {}).get("status", "技术失败"),
        "consumer_validated": record["consumer_validated"],
        "workflow_executed": record.get("workflow_executed"),
        "request_count": record["logical_call_budget"]["requests_used"],
        "result_path": str(args.output.resolve()),
    }, ensure_ascii=False))
    return 0 if record["consumer_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
