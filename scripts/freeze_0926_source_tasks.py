#!/usr/bin/env python3
"""Freeze source-only evaluation tasks; this is not a clinical answer key."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from app.domain.contracts.protocol_controls import ProtocolControlDiscoveryToDeepPlan
from scripts.run_phase3_deconstruction_acceptance import PROTOCOLS, _build_package


SOURCE_JOB_ID = "9c651df26b6c4f5496c95294dde846c8"
SOURCE_DATABASE = Path(
    "/Users/smkzw/tmp/enrollment-review-w6-v142-relation-isolated-data/"
    "enrollment-review-v2.sqlite3"
)
DEFAULT_OUTPUT = Path(
    ".trellis/tasks/09-11-e2e-eligibility-review/evaluation/"
    "0926v1-source-tasks-24.json"
)

# Selection is evaluation-only. No score, drug, disease or source ID here enters product logic.
SAR_CASES = (
    ("mixed_background", 1, "su-770b933958b607fa22dfc557"),
    ("definition_and_condition", 3, "su-231c8eb966dc996ef213dca6"),
    ("multi_stage_threshold", 4, "su-cc4f8ad4ea30bde506ddca43"),
    ("operational_definition", 6, "su-d666c4378fe375ebab0d1540"),
    ("current_and_future", 7, "su-f771045b40cb8748ae2f5632"),
    ("longer_of_windows", 8, "su-02584361e9e9536ea84590b2"),
    ("exception_scope", 11, "su-237284b17c804b438be7586a"),
    ("series_and_missingness", 30, "su-f653a4e69dab58d2bd3e5892"),
    ("procedure_validity", 35, "su-2d96881749cb31499d441cc8"),
    ("shared_calculation_definition", 42, "su-206412f1fa9a87330e61b7d3"),
    ("result_with_exception", 55, "su-1357c621b904043818acc780"),
    ("study_procedure_scope", 85, "su-6a37c9ffc8089a84d9b687f4"),
)
D001_CASES = (
    ("history_and_judgment", "IN-03"),
    ("multi_stage_threshold", "IN-04"),
    ("current_and_future", "IN-06"),
    ("lookback_anchor", "EX-01"),
    ("investigator_judgment", "EX-02"),
    ("nested_history_exception", "EX-04"),
    ("future_restriction", "EX-10"),
    ("treatment_washout_list", "EX-18"),
    ("longer_of_windows", "EX-19"),
    ("lab_result_and_threshold", "EX-20"),
    ("source_validity_and_judgment", "EX-21"),
    ("procedure_schedule", "body.t5.r27.c0.p0"),
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sar_tasks() -> tuple[dict, list[dict]]:
    connection = sqlite3.connect(
        f"file:{SOURCE_DATABASE.resolve(strict=True)}?mode=ro", uri=True
    )
    try:
        job = connection.execute(
            "SELECT state, payload_json FROM jobs WHERE job_id=?", (SOURCE_JOB_ID,)
        ).fetchone()
        closure = connection.execute(
            "SELECT payload_json FROM job_checkpoints WHERE job_id=? AND "
            "step_id='deterministic_closure' ORDER BY created_at DESC LIMIT 1",
            (SOURCE_JOB_ID,),
        ).fetchone()
    finally:
        connection.close()
    if job is None or closure is None or job[0] not in {"failed_final", "cancelled", "completed"}:
        raise ValueError("冻结方案来源不是可核验的终态作业")
    payload = json.loads(job[1])
    docx_sha256 = _sha(PROTOCOLS["mg-iii"]["path"].read_bytes())
    if payload["source_input"]["protocol_file_sha256"] != docx_sha256:
        raise ValueError("当前方案文件与旧终态作业的原件不是同一版本")
    plan = ProtocolControlDiscoveryToDeepPlan.model_validate(
        json.loads(closure[0])["deep_plan"]
    )
    by_number = {batch.batch_number: batch for batch in plan.batches}
    tasks = []
    for index, (dimension, number, unit_id) in enumerate(SAR_CASES, 1):
        batch = by_number[number]
        unit = next(
            (item for item in batch.owned_units if item.structure_unit_id == unit_id), None
        )
        if unit is None:
            raise ValueError(f"冻结第{number}批缺少选定原文单元")
        tasks.append({
            "task_id": f"SAR-{index:02d}", "dimension": dimension,
            "batch_id": batch.batch_id, "batch_number": number,
            "structure_unit_id": unit_id, "source_ref": unit.source_ref,
            "source_span_ids": list(unit.source_span_ids),
            "source_excerpt_sha256": _sha(unit.excerpt.encode("utf-8")),
        })
    return ({
        "source_kind": "terminal_control_job", "source_job_id": SOURCE_JOB_ID,
        "source_content_sha256": payload["source_content_sha256"],
        "frozen_closure_sha256": _sha(closure[0].encode("utf-8")),
        "docx_sha256": docx_sha256,
    }, tasks)


def _d001_tasks() -> tuple[dict, list[dict]]:
    with tempfile.TemporaryDirectory(prefix="ie-source-tasks-") as temp:
        package = _build_package("d001-ii", Path(temp))
        docx_sha256 = _sha(PROTOCOLS["d001-ii"]["path"].read_bytes())
        if package.source_input.protocol_file_sha256 != docx_sha256:
            raise ValueError("第二方案结构输入与当前原件不是同一版本")
        materials = {item.source_span_id: item for item in package.source_input.source_materials}
        if len(materials) != len(package.source_input.source_materials):
            raise ValueError("第二方案来源片段身份重复")
        by_code = {item.official_code: item for item in package.parent_rule_catalog.items}
        tasks = []
        for index, (dimension, selector) in enumerate(D001_CASES, 1):
            if selector.startswith("body."):
                sources = [item for item in materials.values() if item.source_ref == selector]
                if len(sources) != 1:
                    raise ValueError("操作日程来源未唯一定位")
                span_ids = [sources[0].source_span_id]
                catalog_code = None
            else:
                item = by_code[selector]
                span_ids = list(item.source_span_ids)
                catalog_code = selector
            if not span_ids or any(span not in materials for span in span_ids):
                raise ValueError("第二方案任务有来源片段不在冻结输入中")
            tasks.append({
                "task_id": f"D001-{index:02d}", "dimension": dimension,
                "catalog_code": catalog_code,
                "source_span_ids": span_ids,
                "source_refs": [materials[span].source_ref for span in span_ids],
                "source_text_sha256": [
                    _sha(materials[span].text.encode("utf-8")) for span in span_ids
                ],
            })
    return ({
        "source_kind": "docx_structural_input", "study_phase": "II",
        "docx_sha256": docx_sha256,
    }, tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="冻结两份真实方案的24项来源任务")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true", help="只读比对既有冻结文件")
    args = parser.parse_args()
    if args.output.exists() and not args.verify:
        parser.error("冻结任务已存在；不得覆盖或把新版本写成旧身份")
    if args.verify and not args.output.is_file():
        parser.error("没有可只读核验的冻结任务")
    sar_source, sar = _sar_tasks()
    d001_source, d001 = _d001_tasks()
    if len(sar) != 12 or len(d001) != 12 or len({
        item["task_id"] for item in [*sar, *d001]
    }) != 24:
        raise ValueError("冻结任务不是两方案各12项且编号唯一")
    document = {
        "version": "0926v1/source-tasks/v1",
        "purpose": "同源A/B/C对照的来源题，不含医学金标或正式发布许可",
        "variant_policy": "每题再冻结原文、同义、布局、改变医学含义四种输入；变体未构建",
        "sources": {"sar_iii": sar_source, "d001_ii": d001_source},
        "tasks": [*sar, *d001], "claims_complete": False,
    }
    if args.verify:
        if json.loads(args.output.read_text(encoding="utf-8")) != document:
            raise ValueError("冻结来源、原件或任务选择已变化；不得混作同一评测")
        print(json.dumps({"verified": True, "tasks": 24,
                          "sha256": _sha(args.output.read_bytes())}, ensure_ascii=False))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "sar": len(sar),
                      "d001": len(d001), "sha256": _sha(args.output.read_bytes())},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
