"""Markdown export for subject, center, and project eligibility reports."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.centers import center_label
from app.phases import load_review_workflow, phase_llm_dir
from app.pipeline.reviewer import (
    is_future_phase_verify_reasoning,
    is_source_traceability_verify_reasoning,
    parse_review_response,
    pass_verify_label,
)


VERDICT_LABELS = {
    "pass": "通过",
    "pass_verify": "通过（需验证）",
    "fail": "不符合",
    "needs_evidence": "需处理（旧结论）",
    "insufficient": "证据不足",
    "investigator": "需研究者判定",
    "na": "不适用",
    "": "未审核",
}

ISSUE_VERDICTS = {"fail", "needs_evidence", "insufficient", "investigator"}


def default_report_phase(project_path: Path) -> str:
    rules_path = project_path / "criteria_rules.md"
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    workflow = load_review_workflow(project_path, rules_text)
    for phase in workflow.get("review_phases") or []:
        phase_id = phase.get("phase_id")
        if phase_id and phase_id != "full":
            return phase_id
    phases = workflow.get("review_phases") or []
    return phases[0].get("phase_id", "full") if phases else "full"


def generate_markdown_report(
    *,
    project_path: Path,
    project: dict,
    scope: str,
    phase: str = "full",
    center_code: str = "",
    subject_id: str = "",
) -> str:
    phase = phase or "full"
    if phase == "full":
        phase = default_report_phase(project_path)
    subjects = _collect_subjects(project_path, center_code=center_code, subject_id=subject_id)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title = {
        "project": "项目入排审核汇总报告",
        "center": "中心入排审核汇总报告",
        "subject": "受试者入排审核报告",
    }.get(scope, "入排审核报告")
    lines = [
        f"# {title}",
        "",
        f"- 项目编号：{project.get('project_code') or '-'}",
        f"- 项目名称：{project.get('name') or project.get('project_code') or '-'}",
        f"- 方案编号：{project.get('protocol_id') or '-'}",
        f"- 方案版本/日期：{_join_nonempty(project.get('protocol_version'), project.get('protocol_date')) or '-'}",
        f"- 项目期别：{project.get('study_stage') or '-'}",
        f"- 审核阶段：{phase}",
    ]
    if center_code:
        lines.append(f"- 导出中心：{center_code}")
    if subject_id:
        lines.append(f"- 导出受试者：{subject_id}")
    lines.extend([f"- 导出时间：{generated_at}", ""])

    parsed_subjects = [_subject_report(project_path, item, phase) for item in subjects]
    summary_counts: dict[str, int] = {}
    for item in parsed_subjects:
        summary_counts[item["overall"]] = summary_counts.get(item["overall"], 0) + 1
    lines.extend([
        "## 汇总",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 受试者数 | {len(parsed_subjects)} |",
        f"| 可入组/通过 | {summary_counts.get('pass', 0)} |",
        f"| 溯源提醒 | {sum(1 for item in parsed_subjects for r in item.get('rules', []) if r.verdict == 'pass_verify' and is_source_traceability_verify_reasoning(r.reasoning))} |",
        f"| 后续阶段复核提醒 | {sum(1 for item in parsed_subjects for r in item.get('rules', []) if r.verdict == 'pass_verify' and is_future_phase_verify_reasoning(r.reasoning))} |",
        f"| 不符合 | {summary_counts.get('fail', 0)} |",
        f"| 证据不足 | {summary_counts.get('insufficient', 0)} |",
        f"| 需研究者判定 | {summary_counts.get('investigator', 0)} |",
        f"| 需处理（旧结论） | {summary_counts.get('needs_evidence', 0)} |",
        f"| 未生成报告 | {summary_counts.get('', 0)} |",
        "",
        "## 受试者结论",
        "",
        "| 中心 | 受试者 | 状态 | 总结论 | 摘要 |",
        "|---|---|---|---|---|",
    ])
    for item in parsed_subjects:
        info = item["info"]
        lines.append(
            f"| {_md_cell(center_label(info) or '-')} | {_md_cell(info.get('subject_id') or '-')} | "
            f"{_md_cell(info.get('status') or '-')} | {_md_cell(VERDICT_LABELS.get(item['overall'], item['overall'] or '未审核'))} | "
            f"{_md_cell(item.get('summary') or item.get('missing_reason') or '-')} |"
        )
    lines.append("")

    if scope == "subject":
        lines.extend(_render_subject_full_sections(parsed_subjects))
    else:
        lines.extend(_render_issue_sections(parsed_subjects))

    lines.extend([
        "",
        "---",
        "",
        "说明：本 Markdown 报告由系统根据已保存的审核结果生成。中心/项目级报告仅展示不符合、证据不足、需研究者判定或未生成报告的处理项；通过（溯源提醒）和通过（后续阶段复核）同属提醒项，仅在个人完整报告和规则明细中展示，不单独拉低整体结论。",
    ])
    return "\n".join(lines).rstrip() + "\n"


def _collect_subjects(project_path: Path, *, center_code: str = "", subject_id: str = "") -> list[dict]:
    subjects_dir = project_path / "subjects"
    result: list[dict] = []
    if not subjects_dir.exists():
        return result
    for info_path in sorted(subjects_dir.glob("*/info.json")):
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if subject_id and info.get("subject_id") != subject_id:
            continue
        if center_code and str(info.get("center_code") or "").strip() != center_code:
            continue
        result.append(info)
    return sorted(result, key=lambda x: (str(x.get("center_code") or "~~~~"), str(x.get("subject_id") or "")))


def _subject_report(project_path: Path, info: dict, phase: str) -> dict:
    sid = str(info.get("subject_id") or "")
    sd = project_path / "subjects" / sid
    report_dir = phase_llm_dir(sd, phase)
    raw_path = report_dir / "review_raw.md"
    report_path = report_dir / "review_report.md"
    raw_text = ""
    if report_path.exists():
        raw_text = report_path.read_text(encoding="utf-8")
    elif raw_path.exists():
        raw_text = raw_path.read_text(encoding="utf-8")
    if not raw_text:
        return {
            "info": info,
            "overall": info.get("overall_verdict") or "",
            "summary": "",
            "rules": [],
            "groups": [],
            "missing_reason": "未找到该审核阶段的 Markdown 审核报告",
        }
    parsed = parse_review_response(raw_text)
    return {
        "info": info,
        "overall": parsed.get("overall_verdict") or info.get("overall_verdict") or "",
        "summary": _clean_text(parsed.get("summary") or ""),
        "rules": parsed.get("rule_results") or [],
        "groups": parsed.get("group_results") or [],
        "missing_reason": "",
    }


def _render_subject_full_sections(items: list[dict]) -> list[str]:
    lines: list[str] = ["## 逐条审核明细", ""]
    for item in items:
        info = item["info"]
        lines.extend([f"### 受试者 {info.get('subject_id') or '-'}", ""])
        if item.get("missing_reason"):
            lines.extend([f"- {item['missing_reason']}", ""])
            continue
        lines.extend(["| 规则ID | 规则名称 | 类型 | 结论 | 依据 |", "|---|---|---|---|---|"])
        for rule in item.get("rules") or []:
            verdict_label = pass_verify_label(rule.reasoning) if rule.verdict == "pass_verify" else VERDICT_LABELS.get(rule.verdict, rule.verdict)
            lines.append(
                f"| {_md_cell(rule.rule_id)} | {_md_cell(rule.rule_name)} | {_md_cell(_rule_type_label(rule.rule_type))} | "
                f"{_md_cell(verdict_label)} | {_md_cell(_clean_text(rule.reasoning))} |"
            )
        lines.append("")
    return lines


def _render_issue_sections(items: list[dict]) -> list[str]:
    lines: list[str] = ["## 待处理明细", ""]
    has_issue = False
    for item in items:
        info = item["info"]
        issues = [r for r in item.get("rules") or [] if r.verdict in ISSUE_VERDICTS]
        if item.get("missing_reason"):
            has_issue = True
            lines.extend([
                f"### {center_label(info) or '-'} / 受试者 {info.get('subject_id') or '-'}",
                "",
                f"- 未完成：{item['missing_reason']}",
                "",
            ])
            continue
        if not issues:
            continue
        has_issue = True
        lines.extend([
            f"### {center_label(info) or '-'} / 受试者 {info.get('subject_id') or '-'}",
            "",
            "| 规则ID | 规则名称 | 结论 | 需处理事项 |",
            "|---|---|---|---|",
        ])
        for rule in issues:
            lines.append(
                f"| {_md_cell(rule.rule_id)} | {_md_cell(rule.rule_name)} | "
                f"{_md_cell(VERDICT_LABELS.get(rule.verdict, rule.verdict))} | {_md_cell(_clean_text(rule.reasoning))} |"
            )
        lines.append("")
    if not has_issue:
        lines.append("当前范围内未发现不符合、证据不足或需研究者判定条目。")
    return lines


def _join_nonempty(*parts: object) -> str:
    return " / ".join(str(p).strip() for p in parts if str(p or "").strip())


def _rule_type_label(value: str) -> str:
    if value == "inclusion":
        return "入选"
    if value == "exclusion":
        return "排除"
    return value or "-"


def _clean_text(text: str) -> str:
    text = re.sub(r"\b(?:RAW|EDC)-[A-Za-z0-9_.:-]+\b", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _md_cell(text: object) -> str:
    value = _clean_text(str(text or ""))
    return value.replace("|", "\\|").replace("\n", "<br>")
