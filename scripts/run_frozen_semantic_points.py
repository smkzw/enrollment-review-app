#!/usr/bin/env python3
"""Compare a small semantic reading against a frozen, read-only control batch."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from time import monotonic
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_control_agent_transport import protocol_control_transport_from_environment
from app.agents.protocol_control_semantic_point import (
    SEMANTIC_BINDER_VERSION,
    SEMANTIC_POINT_VERSION,
    SourceSemanticPacket,
    bind_semantic_packet_partially,
    build_semantic_point_prompt,
)
from app.agents.protocol_control_semantic_repair import (
    apply_semantic_point_replacement,
    build_semantic_point_repair_prompt,
    semantic_point_precondition,
)
from app.agents.protocol_control_source_interpretation import SourceInterpretation
from app.domain.contracts.protocol_controls import ProtocolControlDiscoveryToDeepPlan


def reuse_raw_response(previous_bytes: bytes, expected_identity: dict) -> dict:
    previous = json.loads(previous_bytes)
    if any(previous.get(key) != expected_identity[key] for key in (
        "source_job_id", "batch_id", "source_probe_sha256", "prompt_sha256", "indexes", "context_indexes"
    )) or not isinstance(previous.get("raw_response"), str):
        raise ValueError("原始回答的来源或提示身份不一致，不能重核")
    model = previous.get("model_identity")
    if not isinstance(model, dict) or not model.get("requested") or model.get("requested") != model.get("reported"):
        raise ValueError("原始回答没有已核实的模型身份，不能重核")
    return {
        "model_identity": model,
        "reused_response_sha256": sha256(previous_bytes).hexdigest(),
        "raw_response": previous["raw_response"],
    }


def parse_reused_packet(raw_response: str) -> tuple[SourceSemanticPacket, str | None]:
    """Inspect an old envelope without promoting absent point dependencies to evidence."""

    payload = json.loads(raw_response)
    if not isinstance(payload, dict):
        raise ValueError("原始语义回答不是对象")
    version = payload.get("version")
    legacy_versions = {f"phase5/control-semantic-point/v{number}" for number in range(7, 12)}
    if version in legacy_versions:
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("旧版语义回答缺少可核对的语义点")
        migrated = []
        for original in items:
            if not isinstance(original, dict):
                raise ValueError("旧版语义点不是对象")
            point = dict(original)
            ambiguous = bool(point.get("dependency_statement_indexes") or point.get("dependency_point_keys"))
            point["dependency_statement_indexes"] = []
            point["dependency_point_keys"] = []
            if ambiguous:
                point["unresolved_dimensions"] = [
                    *point.get("unresolved_dimensions", []),
                    "旧版依赖缺少可验证的完整语义点身份",
                ]
                if isinstance(point.get("computation"), dict):
                    point["computation"] = {
                        **point["computation"], "missing_policy": "unresolved",
                        "missing_ref": None, "max_missing_count": None,
                    }
            migrated.append(point)
        payload = {**payload, "version": SEMANTIC_POINT_VERSION, "items": migrated}
        return SourceSemanticPacket.model_validate(payload), version
    return SourceSemanticPacket.model_validate(payload), None


def select_repair_issue(parent: dict, statement_index: int, point_key: str) -> dict:
    issue = next((item for item in parent.get("binding_issues", []) if (
        item.get("statement_index"), item.get("point_key")
    ) == (statement_index, point_key)), None)
    if issue is None:
        raise ValueError("原答未列出此语义点的核验问题")
    if issue.get("code") != "point_invalid":
        raise ValueError("此点仅受依赖组影响或问题尚未定位，请先核实真正出错的来源点")
    return issue


def main() -> int:
    parser = argparse.ArgumentParser(description="只读对照冻结批次的局部来源语义")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--batch-number", type=int, required=True)
    parser.add_argument("--source-probe", type=Path, required=True)
    parser.add_argument("--indexes", type=int, nargs="+", required=True)
    parser.add_argument("--context-indexes", type=int, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="确认发起一次真实产品模型请求")
    parser.add_argument("--reuse-raw-response", type=Path,
                        help="同一来源和提示下仅重核已保存的原始回答，不再调用模型")
    parser.add_argument("--repair-from", type=Path,
                        help="从已有失败回执仅修订一个有源语义点")
    parser.add_argument("--repair-statement-index", type=int)
    parser.add_argument("--repair-point-key")
    args = parser.parse_args()
    if (args.run and args.reuse_raw_response is not None) or (
        args.repair_from is not None and (not args.run or args.reuse_raw_response is not None
                                      or args.repair_statement_index is None or not args.repair_point_key)
    ):
        parser.error("真实调用与原答重核不能同时启用")
    if args.batch_number < 1 or args.output.exists():
        parser.error("批次序号须从1开始，不能覆盖旧对照回执")

    probe_bytes = args.source_probe.read_bytes()
    probe = json.loads(probe_bytes)
    if probe.get("source_job_id") != args.job_id or probe.get("batch_number") != args.batch_number:
        raise ValueError("来源解释回执与冻结作业批次不一致")
    interpretation = SourceInterpretation.model_validate(
        probe["result"]["source_interpretation"]
    )
    connection = sqlite3.connect(f"file:{args.database.resolve(strict=True)}?mode=ro", uri=True)
    try:
        job = connection.execute("SELECT state FROM jobs WHERE job_id=?", (args.job_id,)).fetchone()
        closure = connection.execute(
            "SELECT payload_json FROM job_checkpoints "
            "WHERE job_id=? AND step_id='deterministic_closure' ORDER BY created_at DESC LIMIT 1",
            (args.job_id,),
        ).fetchone()
    finally:
        connection.close()
    if job is None or closure is None or job[0] not in {"failed_final", "cancelled", "completed"}:
        raise ValueError("仅接受含冻结来源的终态作业")
    plan = ProtocolControlDiscoveryToDeepPlan.model_validate(json.loads(closure[0])["deep_plan"])
    batch = next((item for item in plan.batches if item.batch_number == args.batch_number), None)
    if batch is None or batch.batch_id != probe.get("batch_id"):
        raise ValueError("来源解释回执与冻结分包身份不一致")
    prompt = build_semantic_point_prompt(
        batch, interpretation, args.indexes, context_indexes=args.context_indexes,
    )
    record = {
        "source_job_id": args.job_id,
        "batch_id": batch.batch_id,
        "source_probe_sha256": sha256(probe_bytes).hexdigest(),
        "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "indexes": args.indexes,
        "context_indexes": args.context_indexes,
        "selected_statements": [{
            "statement_index": index,
            "structure_unit_id": interpretation.statements[index].structure_unit_id,
            "decision_functions": interpretation.statements[index].decision_functions,
            "quote_sha256": sha256(
                interpretation.statements[index].quoted_text.encode("utf-8")
            ).hexdigest(),
        } for index in args.indexes],
        "binder_version": SEMANTIC_BINDER_VERSION,
        "claims_complete": False,
    }
    if args.repair_from is not None:
        parent_bytes = args.repair_from.read_bytes()
        parent = json.loads(parent_bytes)
        if any(parent.get(key) != record[key] for key in (
            "source_job_id", "batch_id", "source_probe_sha256", "prompt_sha256",
            "indexes", "context_indexes",
        )) or not isinstance(parent.get("raw_response"), str):
            raise ValueError("原答的来源或基础提示身份已变化，不能局部修订")
        issue = select_repair_issue(parent, args.repair_statement_index, args.repair_point_key)
        prior_packet = SourceSemanticPacket.model_validate_json(parent["raw_response"])
        target = next((point for point in prior_packet.items if (
            point.statement_index, point.point_key
        ) == (args.repair_statement_index, args.repair_point_key)), None)
        if target is None:
            raise ValueError("原答中没有指定的语义点")
        repair_prompt = build_semantic_point_repair_prompt(
            batch, interpretation, prior_packet,
            statement_index=args.repair_statement_index,
            point_key=args.repair_point_key,
            issue=issue["reason"],
            visible_indexes=[*args.indexes, *args.context_indexes],
        )
        transport = protocol_control_transport_from_environment()
        model_identity = {
            "requested": transport.model, "reported": transport.verify_model_identity(),
            "backend": transport.backend, "effort": transport.reasoning_effort,
        }
        if parent.get("model_identity") != model_identity:
            raise ValueError("修订模型线路与原答不一致，不能混用结果")
        record.update({
            "repair_from_sha256": sha256(parent_bytes).hexdigest(),
            "repair_prompt_sha256": sha256(repair_prompt.encode("utf-8")).hexdigest(),
            "repair_target": {"statement_index": args.repair_statement_index,
                              "point_key": args.repair_point_key},
            "precondition_sha256": semantic_point_precondition(target),
            "repair_reason": issue["reason"],
            "model_identity": model_identity,
        })
        started = monotonic()
        response = transport.read_semantic_points(prompt=repair_prompt)
        record["elapsed_seconds"] = round(monotonic() - started, 3)
        record["transport_receipt"] = response.transport_receipt
        record["raw_response"] = response.text
        try:
            replacement = SourceSemanticPacket.model_validate_json(response.text)
            packet = apply_semantic_point_replacement(
                prior_packet, replacement,
                statement_index=args.repair_statement_index,
                point_key=args.repair_point_key,
                precondition_sha256=record["precondition_sha256"],
            )
            bound, remaining = bind_semantic_packet_partially(
                batch, interpretation, args.indexes, packet,
                context_indexes=args.context_indexes,
            )
        except (ValueError, TypeError) as exc:
            record["status"] = "source_check_failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
        else:
            record["status"] = (
                "source_quotes_verified" if not remaining else
                "partial_source_check" if bound else "source_check_failed"
            )
            record["packet_after_repair"] = packet.model_dump(mode="json")
            record["bound_points"] = [point.model_dump(mode="json") for point in bound]
            record["binding_issues"] = [item.model_dump(mode="json") for item in remaining]
            record["capability_gaps"] = [
                {"statement_index": point.statement_index, "point_key": point.point_key}
                for point in bound if point.capability == "capability_gap"
            ]
            record["unresolved_points"] = [
                {"statement_index": point.statement_index, "point_key": point.point_key}
                for point in bound if point.capability == "unresolved"
            ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        print(json.dumps({
            "status": record["status"], "source_point_count": len(record.get("bound_points", [])),
            "rejected_point_count": len(record.get("binding_issues", [])),
            "output": str(args.output.resolve()),
        }, ensure_ascii=False))
        return 0 if record["status"] == "source_quotes_verified" else 2
    if not args.run and args.reuse_raw_response is None:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return 0
    if args.reuse_raw_response is not None:
        previous_bytes = args.reuse_raw_response.read_bytes()
        record.update(reuse_raw_response(previous_bytes, record))
    else:
        transport = protocol_control_transport_from_environment()
        record["model_identity"] = {
            "requested": transport.model,
            "reported": transport.verify_model_identity(),
            "backend": transport.backend,
            "effort": transport.reasoning_effort,
        }
        started = monotonic()
        response = transport.read_semantic_points(prompt=prompt)
        record["elapsed_seconds"] = round(monotonic() - started, 3)
        record["transport_receipt"] = response.transport_receipt
        record["raw_response"] = response.text
    try:
        if args.reuse_raw_response is not None:
            packet, migrated_from = parse_reused_packet(record["raw_response"])
            if migrated_from is not None:
                record["validation_envelope_migrated_from"] = migrated_from
                record["raw_response_sha256"] = sha256(record["raw_response"].encode("utf-8")).hexdigest()
        else:
            packet = SourceSemanticPacket.model_validate_json(record["raw_response"])
        bound, issues = bind_semantic_packet_partially(
            batch, interpretation, args.indexes, packet,
            context_indexes=args.context_indexes,
        )
    except (ValueError, TypeError) as exc:
        record["status"] = "source_check_failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    else:
        record["status"] = (
            "source_quotes_verified" if not issues else
            "partial_source_check" if bound else "source_check_failed"
        )
        if record.get("validation_envelope_migrated_from") is not None:
            record["status"] = "legacy_dependency_unverified"
        record["bound_points"] = [point.model_dump(mode="json") for point in bound]
        record["binding_issues"] = [issue.model_dump(mode="json") for issue in issues]
        record["capability_gaps"] = [
            {"statement_index": point.statement_index, "point_key": point.point_key}
            for point in bound if point.capability == "capability_gap"
        ]
        record["unresolved_points"] = [
            {"statement_index": point.statement_index, "point_key": point.point_key}
            for point in bound if point.capability == "unresolved"
        ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "status": record["status"],
        "source_point_count": len(record.get("bound_points", [])),
        "rejected_point_count": len(record.get("binding_issues", [])),
        "capability_gaps": record.get("capability_gaps", []),
        "unresolved_points": record.get("unresolved_points", []),
        "output": str(args.output.resolve()),
    }, ensure_ascii=False))
    return 0 if record["status"] == "source_quotes_verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
