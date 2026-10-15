"""Explicit opt-in synthetic image probe through the product R3 harness."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

import fitz

from app.domain.contracts.enums import Comparator, RuleKind, StudyPhase
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, Rule, RuleComponent, RuleSet
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    PageReviewInput, direct_openai_completion, preflight_page_reader_routes,
    require_page_reader_routes,
    read_page,
)
from app.projections.clause_pack import project_clause_pack
from app.services.page_review_execution import review_page
from app.llm.page_review_transport_options import page_completion_options


async def run(output: Path, lane: str | None = None) -> None:
    output.mkdir(parents=True, exist_ok=False)
    with fitz.open() as document:
        page = document.new_page(width=800, height=600)
        for index, text in enumerate([
            "合成检查单：仅用于系统连接测试，不是真实病例",
            "测试编号：SYNTHETIC-001",
            "检查日期：2026-09-05",
            "检查项目甲：1.234567 mmol/L",
            "检查项目乙：0 mmol/L",
            "本页无手写批注。",
        ]):
            page.insert_text((40, 60 + index * 65), text, fontname="china-s", fontsize=20)
        image = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
    (output / "synthetic.png").write_bytes(image)
    predicate = AtomicPredicate(predicate_id="synthetic-predicate", subject="受试者",
                                attribute="检查项目甲及乙", comparator=Comparator.EXISTS)
    component = RuleComponent(rule_component_id="synthetic-component", parent_rule_id="synthetic-rule",
                              display_code="IN-01", title="记录检查结果",
                              expression=AtomicExpression(predicate=predicate))
    pack = project_clause_pack(RuleSet(rule_set_id="synthetic-rules", protocol_version_id="synthetic-protocol",
        study_phase=StudyPhase.PHASE_III, rules=[Rule(rule_id="synthetic-rule", official_code="IN-01",
        kind=RuleKind.INCLUSION, source_text="记录检查项目甲及乙的检查结果。此为合成技术验证，非临床标准。",
        study_phase=StudyPhase.PHASE_III, components=[component])]))
    routes = await preflight_page_reader_routes(require_page_reader_routes())
    receipts = []

    async def completion(route, messages, budget):
        if route.provider in {"mtplx", "omlx", "mlx-serve"}:
            from scripts.run_frozen_product_reader import require_idle_local_reader

            require_idle_local_reader(route.provider)
        start = time.monotonic()
        receipt = {"lane": route.lane.value, "provider": route.provider,
                   "model": route.model, "reasoning_effort": route.reasoning_effort,
                   "budget": budget, "messages_sha256": hashlib.sha256(
                       json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        request = {
            "model": route.model, "reasoning_effort": route.reasoning_effort,
            "max_tokens": budget, "messages": messages,
            **page_completion_options(route.provider, messages, budget),
        }
        serialized_request = json.dumps(request, ensure_ascii=False, sort_keys=True)
        receipt["request_sha256"] = hashlib.sha256(serialized_request.encode()).hexdigest()
        (output / f"request-{route.lane.value}-{len(receipts)}.json").write_text(serialized_request, encoding="utf-8")
        try:
            response = await direct_openai_completion(route, messages, budget)
            receipt.update(finish_reason=response.finish_reason, usage=response.usage,
                           response_model=response.response_model,
                           transport_contract=response.transport_contract)
            (output / f"response-{route.lane.value}-{len(receipts)}.json").write_text(
                json.dumps({"text": response.text}, ensure_ascii=False, indent=2), encoding="utf-8")
            return response
        except Exception as exc:
            receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
            raise
        finally:
            receipt["elapsed_seconds"] = round(time.monotonic() - start, 3)
            receipts.append(receipt)
            (output / "receipts.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")

    page_input = PageReviewInput(page_artifact_id="synthetic-page", source_document_version_id="synthetic-document",
        page_number=1, page_image_sha256=hashlib.sha256(image).hexdigest(),
        page=PageVisionInput(source_ref="synthetic-page", page_ordinal=1, image_bytes=image))
    if lane is not None:
        record = await read_page(routes[PageReviewLane(lane)], page_input, pack, completion=completion)
        report = {"synthetic_only": True, "single_lane_only": True,
                  "clinical_acceptance": False, "records": [record.model_dump(mode="json")]}
        (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output": str(output), "records": 1, "receipts": receipts}, ensure_ascii=False))
        return
    result = await review_page(routes, page_input, pack, completion=completion)
    report = {"synthetic_only": True, "coverage": result.coverage_entry.model_dump(mode="json"),
              "records": [r.model_dump(mode="json") for r in result.records],
              "reconciliation": result.reconciliation.model_dump(mode="json") if result.reconciliation else None}
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "disposition": result.coverage_entry.disposition.value,
                      "records": len(result.records), "receipts": receipts}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lane", choices=["main-A", "main-B"])
    args = parser.parse_args()
    asyncio.run(run(args.output, args.lane))
