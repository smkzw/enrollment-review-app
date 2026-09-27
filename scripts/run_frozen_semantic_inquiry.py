#!/usr/bin/env python3
"""One bounded, read-only source inquiry for a frozen unresolved point set."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from hashlib import sha256
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_control_agent_transport import protocol_control_transport_from_environment
from app.agents.protocol_control_semantic_inquiry import (
    SourceInquiryPlan, SourceInquiryResult, build_inquiry_plan_prompt,
    build_inquiry_result_prompt, materialize_inquiry_sources, verify_inquiry_result,
)
from app.agents.protocol_control_semantic_point import BoundSemanticPoint
from app.domain.contracts.protocol_controls import ProtocolSectionCoverageManifest


def _hash_json(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _result_status(result: SourceInquiryResult) -> str:
    statuses = {item.status for item in result.point_results}
    if statuses == {"source_cited_proposal"}:
        return "source_cited_proposal"
    if statuses == {"remains_unknown"}:
        return "still_unresolved"
    return "mixed_unresolved"


def main() -> int:
    parser = argparse.ArgumentParser(description="只读核对冻结方案中的未决来源点")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--from-semantic-points", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="确认发起受限产品模型查阅")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("不得覆盖已有查阅回执")
    parent_bytes = args.from_semantic_points.read_bytes()
    parent = json.loads(parent_bytes)
    if (parent.get("source_job_id") != args.job_id
            or parent.get("status") not in {"source_quotes_verified", "partial_source_check"}):
        raise ValueError("来源语义回执不属于所选冻结任务或尚未通过来源定位")
    parent_model = parent.get("model_identity")
    if (not isinstance(parent_model, dict) or not parent_model.get("requested")
            or parent_model.get("requested") != parent_model.get("reported")):
        raise ValueError("来源语义回执缺少已核实的模型身份")
    points = [BoundSemanticPoint.model_validate(item) for item in parent.get("bound_points", [])
              if item.get("capability") == "unresolved"]
    if not points:
        raise ValueError("没有可执行局部查阅的未决语义点")
    connection = sqlite3.connect(f"file:{args.database.resolve(strict=True)}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT state,payload_json FROM jobs WHERE job_id=?", (args.job_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or row[0] not in {"failed_final", "cancelled", "completed"}:
        raise ValueError("仅接受含冻结来源的终态任务")
    manifest = ProtocolSectionCoverageManifest.model_validate(
        json.loads(row[1])["coverage_manifest"]
    )
    units_by_id = {unit.structure_unit_id: unit for unit in manifest.units}
    if any(
        (unit := units_by_id.get(point.structure_unit_id)) is None
        or unit.source_ref != point.source_ref
        or _hash_json(unit.model_dump(mode="json")) != point.source_unit_sha256
        for point in points
    ):
        raise ValueError("待核语义点的原文身份与冻结方案不一致")
    prompt = build_inquiry_plan_prompt(points)
    record = {
        "source_job_id": args.job_id,
        "parent_response_sha256": sha256(parent_bytes).hexdigest(),
        "protocol_manifest_id": manifest.manifest_id,
        "point_semantic_ids": sorted(point.semantic_id for point in points),
        "plan_prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "claims_complete": False,
        "clinical_semantics_verified": False,
    }
    if not args.run:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return 0
    transport = protocol_control_transport_from_environment()
    record["model_identity"] = {
        "requested": transport.model,
        "reported": transport.verify_model_identity(),
        "backend": transport.backend,
        "effort": transport.reasoning_effort,
    }
    if any(record["model_identity"].get(key) != parent_model.get(key)
           for key in ("requested", "reported", "backend", "effort")):
        raise ValueError("本次查证与原语义读取的模型路线不一致")
    started = monotonic()
    try:
        plan_response = transport.read_semantic_inquiry(prompt=prompt, step="plan")
        record["plan_transport_receipt"] = plan_response.transport_receipt
        record["plan_raw_response"] = plan_response.text
        plan = SourceInquiryPlan.model_validate_json(plan_response.text)
        sources = materialize_inquiry_sources(plan, manifest.units)
        record["inquiry_plan"] = plan.model_dump(mode="json")
        record["sources"] = [source.model_dump(mode="json") for source in sources]
        result_prompt = build_inquiry_result_prompt(points, sources)
        record["result_prompt_sha256"] = sha256(result_prompt.encode("utf-8")).hexdigest()
        result_response = transport.read_semantic_inquiry(prompt=result_prompt, step="result")
        record["result_transport_receipt"] = result_response.transport_receipt
        record["result_raw_response"] = result_response.text
        result = verify_inquiry_result(
            SourceInquiryResult.model_validate_json(result_response.text), points, sources,
        )
        record["result"] = result.model_dump(mode="json")
        record["status"] = _result_status(result)
    except Exception as exc:  # noqa: BLE001 - preserve the isolated failure receipt
        record["status"] = "inquiry_failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["elapsed_seconds"] = round(monotonic() - started, 3)
    record["record_sha256"] = _hash_json({
        key: value for key, value in record.items() if key != "record_sha256"
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({
        "status": record["status"],
        "source_count": len(record.get("sources", [])),
        "source_cited_proposals": sum(
            item["status"] == "source_cited_proposal" for item in record.get("result", {}).get("point_results", [])
        ),
        "elapsed_seconds": record["elapsed_seconds"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False))
    return 0 if record["status"] != "inquiry_failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
