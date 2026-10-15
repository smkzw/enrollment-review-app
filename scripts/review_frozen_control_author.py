#!/usr/bin/env python3
"""Reassemble a frozen failed author response; optionally review, never publish."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentResponse, ProtocolControlAgentRunner, ProtocolControlAgentRunResult,
)
from app.agents.protocol_control_fixed_flow import FIXED_FLOW, pending_front_wire
from app.agents.protocol_control_source_interpretation import (
    SourceInterpretation, SourceTargetReview, validate_source_interpretation,
    validate_source_target_review,
)
from app.agents.protocol_control_stage_compiler import assemble_source_requirement_inserts
from app.agents.protocol_control_agent_transport import protocol_control_transport_from_environment
from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch
from app.llm.logical_call_budget import LogicalCallBudget
from app.services.protocol_control_execution import (
    _transport_identity, _validate_deep_batch_output, _validate_saved_source_review,
)
from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
from app.storage.config import resolve_data_paths
from scripts.run_frozen_control_slice import frozen_code_identity


def load_frozen_author(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("receipt_format_version") != "frozen-control-slice/v2"
            or data.get("workflow_executed") != FIXED_FLOW
            or data.get("consumer_validated") is not False
            or len(data.get("call_receipts", [])) != 3
            or any(item.get("finish_reason") != "stop" for item in data["call_receipts"])):
        raise ValueError("只接受明确失败且保留三次完整原答的固定流程材料")
    result = ProtocolControlAgentRunResult.model_validate(data["result"])
    if (result.final_output is not None or len(result.attempts) != 4
            or result.attempts[-1].outcome != "publication_invalid"
            or result.attempts[-1].error_classes != ["FABRICATED_EXCERPT"]):
        raise ValueError("本诊断仅复查有完整作者的摘录装配失败，不能重用其他失败或成功结果")
    raw_outputs = data["attempt_raw_outputs"]
    if len(raw_outputs) != 4:
        raise ValueError("作者原答清单不完整，不能截取其他调用冒充三次读取")
    originals = raw_outputs[:3]
    for index, item in enumerate(originals):
        saved = result.attempts[index]
        if (not isinstance(item.get("text"), str) or not item["text"].strip()
                or hashlib.sha256(item["text"].encode("utf-8")).hexdigest() != item["sha256"]
                or item.get("characters") != len(item["text"])
                or item.get("attempt") != index + 1 or item.get("outcome") != "parsed"
                or item.get("error_classes") != [] or not item.get("session_id")
                or saved.raw_output_sha256 != item["sha256"]
                or saved.raw_output_chars != len(item["text"])
                or saved.session_id != item["session_id"]):
            raise ValueError("原答不完整或哈希不一致")
    old = data["logical_call_budget"]
    checked_budget = LogicalCallBudget(old["logical_task_id"], max_requests=old["max_requests"],
        max_output_tokens=old["max_output_tokens"], saved=old, contract_sha256=old["contract_sha256"])
    if (old["logical_task_id"] != data["logical_task_id"]
            or old["contract_sha256"] != data["execution_contract_sha256"]
            or checked_budget.snapshot()["requests_used"] != 3
            or any(receipt.get("budget_request_sha256") != reservation["request_sha256"]
                   or receipt.get("requested_max_tokens") != reservation["requested_max_tokens"]
                   or receipt.get("request_reserved") is not True
                   for receipt, reservation in zip(data["call_receipts"], old["requests"], strict=True))):
        raise ValueError("原答调用回执与预算不一致，不能重置已使用额度")
    batch = ProtocolControlDispositionBatch.model_validate(data["frozen_batch"])
    interpretation = SourceInterpretation.model_validate_json(originals[0]["text"])
    review = SourceTargetReview.model_validate_json(originals[1]["text"])
    author = ProtocolControlAgentResponse(session_id=originals[2]["session_id"], text=originals[2]["text"])
    validate_source_interpretation(batch, interpretation)
    from app.agents.protocol_control_deconstructor import source_statement_coverage
    validate_source_target_review(batch, interpretation,
        source_statement_coverage(batch, interpretation, pending_front_wire(batch)), review)
    if len(review.items) != 1 or review.items[0].decision != "additional_requirement":
        raise ValueError("本诊断仅处理已经保存的单项增量作者，不扩大修订范围")
    return data, batch, interpretation, review, author


class _SavedAuthorTransport:
    """Only final alignment is live. Reused answers retain their original sessions."""

    def __init__(self, live, originals, author):
        self.live, self.originals, self.author = live, originals, author

    def start_source_target_review(self, *, prompt):
        return ProtocolControlAgentResponse(
            session_id=self.originals[1]["session_id"], text=self.originals[1]["text"],
        )

    def read_stage_bound_requirement(self, *, prompt):
        return self.author

    def start_source_candidate_alignment(self, *, prompt):
        return self.live.start_source_candidate_alignment(prompt=prompt)

    def start(self, **kwargs):
        raise ValueError("装配复查不允许退回完整作者调用")

    def continue_session(self, **kwargs):
        raise ValueError("装配复查不允许重新解释或改写旧作者答案")


def main():
    parser = argparse.ArgumentParser(description="复查已保存作者的装配及候选含义，不发布规则")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger-dir", type=Path, required=True)
    parser.add_argument("--run-review", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("已有复查产物不覆盖")
    source_bytes = args.source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    data, batch, interpretation, review, author = load_frozen_author(args.source)
    wire, output, coverage = assemble_source_requirement_inserts(
        batch, interpretation, review.items, pending_front_wire(batch), [author],
        lambda out: _validate_deep_batch_output(batch, out),
    )
    identity = {**frozen_code_identity(), __file__: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    record = {"source_artifact_sha256": source_sha, "code_identity": identity,
              "scope": "saved_author_reassembly_and_alignment_only", "claims_complete": False,
              "published": False, "assembly_validated": True, "consumer_validated": False,
              "reused_responses": [{"session_id": item["session_id"], "sha256": item["sha256"]}
                                   for item in data["attempt_raw_outputs"][:3]],
              "new_call_receipts": [], "failure": None}
    if args.run_review:
        live = protocol_control_transport_from_environment()
        route = _transport_identity(live, stage="deep")
        # Compiler/schema changed, but model, authorization endpoint and effort must not.
        fields = ("backend", "provider", "base_url", "model", "reasoning_effort",
                  "max_tokens", "max_retries", "response_format_mode", "temperature")
        if any(route[field] != data["route_identity"][field] for field in fields):
            raise ValueError("装配复查不能偷偷换模型、端点或采样/额度")
        old = data["logical_call_budget"]
        logical_id = hashlib.sha256((source_sha + ":saved-author-reassembly/v1").encode()).hexdigest()
        cache = _ProtocolSemanticBatchFileCache(resolve_data_paths(str(args.ledger_dir)), logical_id)
        if cache.load_call_budget(logical_id) is not None:
            raise ValueError("本原答已有复查预算；不能换输出文件名重新发起")
        contract = hashlib.sha256(json.dumps({"code": identity, "route": route,
            "source": source_sha}, sort_keys=True).encode()).hexdigest()
        inherited = {**old, "logical_task_id": logical_id, "contract_sha256": contract}
        budget = LogicalCallBudget(logical_id, max_requests=old["max_requests"],
            max_output_tokens=old["max_output_tokens"], saved=inherited,
            contract_sha256=contract, persist=cache.store_call_budget)
        cache.store_call_budget(budget.snapshot())
        record.update(route_identity=route, inherited_request_count=old["requests_used"],
                      logical_task_id=logical_id, execution_contract_sha256=contract)
        started = time.monotonic()
        try:
            live.bind_logical_call_budget(budget)
            reported = live.verify_model_identity()
            record["reported_model"] = reported
            result = ProtocolControlAgentRunner(max_schema_repairs=0).run(
                batch, _SavedAuthorTransport(live, data["attempt_raw_outputs"], author),
                resume_source_interpretation=interpretation, workflow_variant=FIXED_FLOW,
                output_validator=lambda out: _validate_deep_batch_output(batch, out),
            )
            record["result"] = result.model_dump(mode="json")
            if result.final_output is not None:
                restored = type(result).model_validate_json(result.model_dump_json())
                _validate_deep_batch_output(batch, restored.final_output)
                _validate_saved_source_review(batch, restored)
                record["consumer_validated"] = True
        except Exception as exc:
            record["failure"] = {"type": type(exc).__name__, "code": getattr(exc, "code", None), "detail": str(exc)}
        finally:
            record["new_call_receipts"] = live.take_call_receipts()
            record["logical_call_budget"] = budget.snapshot()
            live.bind_logical_call_budget(None)
            record["review_duration_seconds"] = time.monotonic() - started
    else:
        record["assembled_wire"] = wire.model_dump(mode="json")
        record["source_coverage"] = [entry.model_dump(mode="json") for entry in coverage]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != source_sha:
        raise ValueError("复查期间原答发生变化")
    print(json.dumps({"assembly_validated": True, "consumer_validated": record["consumer_validated"],
                      "new_calls": len(record["new_call_receipts"]), "published": False,
                      "output": str(args.output)}, ensure_ascii=False))
    return 0 if not args.run_review or record["consumer_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
