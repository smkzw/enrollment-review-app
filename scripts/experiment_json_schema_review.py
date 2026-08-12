#!/usr/bin/env python3
"""Experimental JSON-output review comparison for D001.

This does not modify the production review flow or overwrite existing reports.
It asks the review backend for strict JSON on a few already-reviewed subjects
and compares parsing stability against the current Markdown-table route.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm.client import review_chat
from app.phases import load_review_workflow, phase_by_id
from app.pipeline.reviewer import (
    _SYSTEM_PROMPT,
    build_review_messages,
    extract_rule_ids,
    parse_review_response,
)
from app.subject_dates import subject_anchor_dates


PROJECT_CODE = "D001-02-II"
PHASE = "screening_run_in"
STUDY_STAGE = "Ⅱ期"
DEFAULT_SUBJECTS = ["SA11004", "SA09002", "SA07009", "SA10002"]


JSON_SCHEMA_INSTRUCTIONS = """\
本次为结构化输出实验。你必须只输出一个合法 JSON 对象，不要输出 Markdown、代码块或解释性前后缀。

JSON 顶层结构：
{
  "overall_verdict": "pass | fail | insufficient | investigator",
  "summary": "一段中文总结",
  "rule_results": [
    {
      "rule_id": "IN-01 或 EX-01 等，必须来自规则ID清单",
      "rule_name": "规则名称",
      "rule_type": "inclusion | exclusion | procedure | unknown",
      "verdict": "pass | pass_verify | fail | insufficient | investigator | na",
      "trigger_status": "met | triggered | not_triggered | not_applicable | source_traceability_verify | future_phase_verify | needs_evidence | needs_investigator",
      "evidence_quotes": [
        {"source": "证据类别/文件名", "page": "pN", "quote": "原文关键句"}
      ],
      "reasoning": "1-2句中文依据，必须说明触发/符合判断",
      "logic_note": "如涉及AND/OR、研究者判断、精确检验项目匹配，则简述；否则为空字符串"
    }
  ]
}

要求：
1. rule_results 必须逐项覆盖规则ID清单，每个父级规则只输出一项。
2. 不得新增 schema 以外的顶层字段。
3. verdict 只能使用枚举值；不要使用中文或 emoji。
4. 排除标准只有完整触发方案条件才可 fail；研究者判断、AND 条件、实验室精确项目匹配规则按系统要求执行。
5. 如果没有证据引用，evidence_quotes 设为空数组，并把 verdict 判为 insufficient 或 investigator，不得臆造。
"""


def compact_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def extract_json_object(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def normalize_rule_results(data: dict) -> list[dict]:
    rows = data.get("rule_results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def validate_json_review(data: dict, expected_rule_ids: list[str]) -> dict:
    valid_overall = {"pass", "fail", "insufficient", "investigator"}
    valid_rule_verdicts = {"pass", "pass_verify", "fail", "insufficient", "investigator", "na"}
    rows = normalize_rule_results(data)
    ids = [str(row.get("rule_id") or "").strip() for row in rows]
    missing = [rid for rid in expected_rule_ids if rid not in ids]
    extra = [rid for rid in ids if rid and rid not in set(expected_rule_ids)]
    duplicate = sorted({rid for rid in ids if ids.count(rid) > 1 and rid})
    invalid_rule_verdicts = [
        {"rule_id": row.get("rule_id", ""), "verdict": row.get("verdict", "")}
        for row in rows
        if row.get("verdict") not in valid_rule_verdicts
    ]
    quote_count = 0
    for row in rows:
        quotes = row.get("evidence_quotes")
        if isinstance(quotes, list):
            quote_count += len([q for q in quotes if isinstance(q, dict) and q.get("quote")])
    return {
        "overall_valid": data.get("overall_verdict") in valid_overall,
        "rule_count": len(rows),
        "missing_rule_ids": missing,
        "extra_rule_ids": extra,
        "duplicate_rule_ids": duplicate,
        "invalid_rule_verdicts": invalid_rule_verdicts,
        "evidence_quote_count": quote_count,
    }


async def run_subject(subject_id: str, output_dir: Path) -> dict:
    project_dir = ROOT / "projects" / PROJECT_CODE
    subject_dir = project_dir / "subjects" / subject_id
    rules_path = project_dir / "criteria_rules.md"
    bundle_path = subject_dir / f"evidence_bundle_{PHASE}.md"
    report_path = subject_dir / "llm" / PHASE / "review_report.md"
    criteria_rules = rules_path.read_text(encoding="utf-8")
    evidence_bundle = bundle_path.read_text(encoding="utf-8")
    workflow = load_review_workflow(project_dir, criteria_rules)
    phase_info = phase_by_id(workflow, PHASE)
    expected_rule_ids = extract_rule_ids(criteria_rules)

    current_report = parse_review_response(report_path.read_text(encoding="utf-8"))
    messages = build_review_messages(
        project_code=PROJECT_CODE,
        anchor_dates=subject_anchor_dates(subject_dir),
        criteria_rules=criteria_rules,
        evidence_bundle=evidence_bundle,
        review_phase=phase_info,
        study_stage=STUDY_STAGE,
    )
    messages[0]["content"] = _SYSTEM_PROMPT + "\n\n" + JSON_SCHEMA_INSTRUCTIONS
    messages[1]["content"] = messages[1]["content"] + "\n\n请按上述 JSON schema 输出。"

    raw = await review_chat(messages, temperature=0.1, max_tokens=16000)
    raw_path = output_dir / f"{subject_id}_json_raw.txt"
    raw_path.write_text(raw, encoding="utf-8")
    parse_error = ""
    data = {}
    try:
        data = extract_json_object(raw)
    except Exception as exc:
        parse_error = str(exc)
    if data:
        (output_dir / f"{subject_id}_parsed.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    validation = validate_json_review(data, expected_rule_ids) if data else {
        "overall_valid": False,
        "rule_count": 0,
        "missing_rule_ids": expected_rule_ids,
        "extra_rule_ids": [],
        "duplicate_rule_ids": [],
        "invalid_rule_verdicts": [],
        "evidence_quote_count": 0,
    }
    return {
        "subject_id": subject_id,
        "current_overall": current_report.get("overall_verdict", ""),
        "json_overall": data.get("overall_verdict", "") if data else "",
        "overall_matches_current": bool(data) and data.get("overall_verdict") == current_report.get("overall_verdict", ""),
        "current_rule_count": len(current_report.get("rule_results", [])),
        "parse_error": parse_error,
        "validation": validation,
        "raw_path": str(raw_path),
    }


def render_markdown(results: list[dict], output_dir: Path) -> str:
    lines = [
        "# JSON Schema Review Experiment",
        "",
        f"- Project: {PROJECT_CODE}",
        f"- Phase: {PHASE}",
        f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        "| Subject | Current | JSON | Match | JSON parse | Rules JSON/current | Missing | Invalid verdicts | Raw |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        v = row["validation"]
        parsed = "yes" if not row.get("parse_error") else "no"
        lines.append(
            "| "
            + " | ".join([
                row["subject_id"],
                row["current_overall"],
                row["json_overall"] or "-",
                "yes" if row["overall_matches_current"] else "no",
                parsed,
                f"{v['rule_count']}/{row['current_rule_count']}",
                str(len(v["missing_rule_ids"])),
                str(len(v["invalid_rule_verdicts"])),
                Path(row["raw_path"]).name,
            ])
            + " |"
        )
    lines.extend([
        "",
        "## Initial Assessment",
        "",
        "- This experiment is prompt-only JSON, not API-enforced structured output.",
        "- A route is advantageous only if it parses reliably, preserves full rule coverage, and reduces semantic contradictions without making reports harder to read.",
        "- Review the per-subject parsed JSON files before promoting this route to production.",
    ])
    return "\n".join(lines) + "\n"


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", nargs="*", default=DEFAULT_SUBJECTS)
    args = parser.parse_args()
    output_dir = ROOT / "projects" / PROJECT_CODE / "reports" / f"json_schema_experiment_{compact_ts()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for subject_id in args.subjects:
        print(f"Running JSON experiment: {subject_id}", flush=True)
        results.append(await run_subject(subject_id, output_dir))
    summary_path = output_dir / "summary.md"
    summary_path.write_text(render_markdown(results, output_dir), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary_path)
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
