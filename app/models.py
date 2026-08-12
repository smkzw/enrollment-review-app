"""Data models for the enrollment review system."""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
import json
from pathlib import Path


class SubjectStatus(str, Enum):
    PENDING = "pending"           # files uploaded, not yet processed
    PROCESSING = "processing"     # pipeline running
    REVIEWED = "reviewed"         # LLM review complete
    ERROR = "error"


class ReviewVerdict(str, Enum):
    PASS = "pass"
    PASS_VERIFY = "pass_verify"  # passed only with source verification warning
    FAIL = "fail"
    INSUFFICIENT = "insufficient"  # evidence insufficient
    INVESTIGATOR = "investigator"  # needs investigator judgment
    NA = "na"                      # not applicable


@dataclass
class RuleItem:
    rule_id: str          # IN-01, EX-01, etc.
    name: str             # short name
    rule_type: str        # "inclusion" | "exclusion"
    judgment_point: str   # what to check
    pass_criteria: str
    fail_criteria: str
    insufficient_criteria: str = ""
    group_id: str = ""    # e.g. "IN-04-GROUP"


@dataclass
class ReviewResult:
    rule_id: str
    rule_name: str
    rule_type: str
    verdict: str          # ReviewVerdict value
    reasoning: str        # LLM reasoning with chunk references


@dataclass
class GroupResult:
    group_id: str
    verdict: str
    satisfied_members: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class ReviewReport:
    subject_id: str
    project_code: str
    overall_verdict: str          # "pass" | "fail" | "insufficient" | "investigator"
    summary: str                  # one-paragraph conclusion
    rule_results: List[ReviewResult] = field(default_factory=list)
    group_results: List[GroupResult] = field(default_factory=list)
    anchor_dates: Dict[str, str] = field(default_factory=dict)
    model_used: str = ""
    generated_at: str = ""

    def to_markdown(self) -> str:
        lines = ["## 审核结论\n"]
        verdict_map = {
            "pass": "**✅ 可入组**",
            "fail": "**❌ 不可入组**",
            "insufficient": "**⚠️ 证据不足**",
            "investigator": "**🟡 需研究者判定**",
            "needs_evidence": "**⚠️ 需处理（旧结论）**",
            "pass_verify": "**✅ 通过（需验证）**",
        }
        lines.append(f"{verdict_map.get(self.overall_verdict, self.overall_verdict)}  ")
        lines.append(self.summary)
        lines.append("\n---\n")
        lines.append("## 逐条审核结果\n")
        lines.append("| 规则ID | 规则名称 | 类型 | 判定结果 | 推理依据 |")
        lines.append("|--------|----------|------|----------|----------|")
        icon = {"pass": "✅ 通过", "pass_verify": "✅ 通过（需验证）", "fail": "❌ 不通过", "insufficient": "⚠️ 证据不足",
                "investigator": "🟡 需研究者判定", "na": "— 不适用"}
        for r in self.rule_results:
            v = icon.get(r.verdict, r.verdict)
            t = "入选" if r.rule_type == "inclusion" else "排除"
            reasoning = r.reasoning.replace("|", "\|")
            lines.append(f"| {r.rule_id} | {r.rule_name} | {t} | {v} | {reasoning} |")
        if self.group_results:
            lines.append("\n---\n")
            lines.append("## 情形组结论\n")
            lines.append("| 组ID | 组判定 | 满足成员 | 说明 |")
            lines.append("|------|--------|----------|------|")
            for g in self.group_results:
                gv = icon.get(g.verdict, g.verdict)
                members = ", ".join(g.satisfied_members) if g.satisfied_members else "无"
                lines.append(f"| {g.group_id} | {gv} | {members} | {g.explanation} |")
        lines.append("\n---\n")
        lines.append(f"- 项目：`{self.project_code}`")
        lines.append(f"- 生成时间：{self.generated_at}")
        lines.append(f"- 模型通道：`{self.model_used}`")
        for k, v in self.anchor_dates.items():
            lines.append(f"- {k}：{v}")
        lines.append("\n*本报告由 AI 辅助生成，须医学监查/研究者最终确认。*")
        return "\n".join(lines)


@dataclass
class ProjectConfig:
    project_code: str             # e.g. "CMS-D001"
    protocol_id: str              # e.g. "D001-02-002"
    name: str = ""
    protocol_version: str = ""
    protocol_date: str = ""
    protocol_source_filename: str = ""
    study_stage: str = ""
    criteria_rules_path: str = "" # relative to project dir
    created_at: str = ""
    owner_username: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SubjectInfo:
    subject_id: str
    project_code: str
    owner_username: str = ""
    center_code: str = ""
    center_name: str = ""
    screening_date: str = ""
    status: str = SubjectStatus.PENDING.value
    doc_count: int = 0
    last_updated: str = ""
    overall_verdict: str = ""
    icf_date: str = ""
    icf_date_manual: bool = False
    first_dosing_date: str = ""
    birth_date: str = ""
    phase_anchor_dates: Dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
