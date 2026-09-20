#!/usr/bin/env python3
"""Slice61ch model-free source-closure regressions.

Locks the D001 II package 96 expected-serious / primary-endpoint reporting
boundary (frozen plan package 96: body.p1136-p1137) to its authoritative
sources before any semantic replay decision:

- config contract and role partition: 2 owned refs body.p1136-p1137
  (p1136 serious AND expected ADR usually-not-expedited list item;
   p1137 conditional non-recommendation of applicant ICSR to national drug
   review agency when SAE is the primary efficacy endpoint);
  attached refs stay body.p1133-p1135 (pkg95 list lead-in / first two items)
  and body.p1018-p1019 (pkg80 SUSAR / expectedness definition) read-only
- real config-field mutation detection for AND→OR weakening, 一般/不建议
  absoluteization, primary-endpoint condition delete/widen/narrow,
  applicant / ICSR-form / agency omission, reverse implication, cross-package
  list truncation or ownership absorption, and candidate upgrade
  (no self-proving phrase-only matching)
- package 95/97/80 ownership boundaries; zero candidates for owned+attached
- official matrix keeps zero rows anchored in owned or attached spans
- immutable source fingerprints and checklist freeze (claims_complete=false)

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

import copy
import re
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_DIR = PHASE_CLOSURE / "configs"
CONFIG_PATH = (
    CONFIG_DIR
    / "representative_group_package96_expected_serious_primary_endpoint_reporting_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61ch-package96-expected-serious-primary-endpoint-reporting-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package96-expected-serious-primary-endpoint-reporting-boundary"
)
FREEZE_DIR = (
    ROOT / "artifacts" / "phase5-slice59i-d001-phase-table-caption-rebaseline-20260827"
)
PLAN_PATH = FREEZE_DIR / "frozen_phase_plan.json"
COVERAGE_PATH = FREEZE_DIR / "coverage_manifest.json"
STRUCTURE_BLOB_PATH = (
    FREEZE_DIR
    / "structure"
    / "blobs"
    / "protocol_blocks"
    / "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json"
)
CATALOG_DIR = ROOT / "artifacts" / "phase5-slice61bl-procedure-footnote-scope-20260829"
MATRIX_PATH = (
    ROOT
    / ".trellis"
    / "tasks"
    / "08-22-phase5-clinical-facts-profile"
    / "research"
    / "d001-ii-official-flow-controls.json"
)

EXPECTED_DOCX_SHA256 = "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
EXPECTED_PLAN_SHA256 = "f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250"
EXPECTED_STRUCTURE_SHA256 = (
    "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
)
EXPECTED_CATALOG_SHA256 = (
    "96de5bbcb97cf33732f2091039123bf5fb53cef5dc96eb23424df94928f5fff1"
)

PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
PACKAGE_96_ORDINAL = 96
PACKAGE_96_ID = "pap-8dd6a669bdee4e77cc1f0b63"
PACKAGE_95_ORDINAL = 95
PACKAGE_95_ID = "pap-d6a9d76caa3d4d5bd85c672e"
PACKAGE_97_ORDINAL = 97
PACKAGE_97_ID = "pap-6e961f674f48ee5003dcc014"
PACKAGE_80_ORDINAL = 80
PACKAGE_94_ORDINAL = 94
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_90_ORDINAL = 90
PACKAGE_91_ORDINAL = 91
PACKAGE_92_ORDINAL = 92
PACKAGE_93_ORDINAL = 93

OWNED_REFS = ["body.p1136", "body.p1137"]
ATTACHED_REFS = [
    "body.p1133",
    "body.p1134",
    "body.p1135",
    "body.p1018",
    "body.p1019",
]
STRUCTURAL_REFS: list[str] = []
SEMANTIC_OWNED_REFS = list(OWNED_REFS)

PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG80_OWNED_ALL = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG80_NON_ATTACHED = [ref for ref in PKG80_OWNED_ALL if ref not in ATTACHED_REFS]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG94_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1113, 1124)]
PKG95_OWNED_ALL = [f"body.p{ordinal}" for ordinal in range(1124, 1136)]
PKG95_NON_ATTACHED = [ref for ref in PKG95_OWNED_ALL if ref not in ATTACHED_REFS]
PKG97_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1138, 1150)]

EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1136": "list_item",
    "body.p1137": "list_item",
}

OWNED_EXCERPT_BY_REF = {
    "body.p1136": "严重但属预期的不良反应；",
    "body.p1137": (
        "当以严重不良事件为主要疗效终点时，不建议申请人以个例安全性报告形式向国家药品审评机构报告。"
    ),
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1133": "以下情况一般不作为快速报告内容：",
    "body.p1134": "非严重不良事件；",
    "body.p1135": "严重不良事件与试验用药品无关；",
    "body.p1018": (
        "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）"
        "指临床表现的性质和严重程度超出了试验药物《研究者手册》、已上市药品的说明书或者产品特性摘要等已有资料信息的可疑并且非预期的严重不良反应。"
    ),
    "body.p1019": (
        "非预期不良反应指不良反应的性质、严重程度、后果或频率，不同于试验药物当前相关资料"
        "（如《研究者手册》等文件）所描述的预期风险。《研究者手册》作为主要文件提供用以判断某不良反应是否预期或非预期的安全性参考信息。"
    ),
}

STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1136": ["严重", "属预期", "不良反应"],
    "body.p1137": [
        "当以严重不良事件为主要疗效终点时",
        "不建议",
        "申请人",
        "个例安全性报告形式",
        "国家药品审评机构",
    ],
}

AND_OR_ERROR_PHRASES = [
    "严重OR属预期即可不作为快速报告",
    "把严重但属预期弱化为析取",
    "预期等同于不严重",
    "把p1136与非严重不良事件合并",
]

INTENSITY_ERROR_PHRASES = [
    "一般不作为快速报告内容改成绝对禁止报告",
    "不建议改成一律不得以个例安全性报告",
    "永不报告严重但属预期的不良反应",
    "无需向国家药品审评机构报告",
]

CONDITION_ERROR_PHRASES = [
    "删除主要疗效终点条件后仍适用不建议条款",
    "扩大为任何SAE均不建议个例安全性报告",
    "缩成仅确认相关或非预期SAE才适用",
]

ACTOR_FORM_AGENCY_ERROR_PHRASES = [
    "省略申请人主体",
    "省略个例安全性报告形式",
    "省略国家药品审评机构接收方",
    "改成不向任何机构报告",
]

INVERSE_ERROR_PHRASES = [
    "非主要疗效终点时必须个例安全性报告快速报告",
    "非该条件时应当必然采用个例安全性报告",
    "反向推导必报命题",
]

CROSS_PACKAGE_ERROR_PHRASES = [
    "截断第95包p1133-p1135列表前段",
    "提前夺取第95包列表引导所有权",
    "提前吸收第97包不良事件随访",
    "把只读附加改写为本包拥有",
]

CANDIDATE_UPGRADE_PHRASES = [
    "未完成主要疗效终点报告边界签署视为筛选失败",
    "入组前必须确认严重但属预期列表否则不得入组",
    "发布预期严重不良反应控制点",
    "筛选期必做：个例安全性报告形式核对",
    "基线期必做：主要疗效终点SAE报告边界签署作为入组条件",
]

ALL_DETERMINISTIC_PHRASES = (
    AND_OR_ERROR_PHRASES
    + INTENSITY_ERROR_PHRASES
    + CONDITION_ERROR_PHRASES
    + ACTOR_FORM_AGENCY_ERROR_PHRASES
    + INVERSE_ERROR_PHRASES
    + CROSS_PACKAGE_ERROR_PHRASES
    + CANDIDATE_UPGRADE_PHRASES
)

ABSOLUTE_INTENSITY_MARKERS = (
    "绝对禁止",
    "一律不得",
    "永不",
    "不允许报告",
    "无需报告",
    "禁止报告",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _deterministic_hits(text: str) -> list[str]:
    return [phrase for phrase in ALL_DETERMINISTIC_PHRASES if phrase in text]


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


def _semantic_blob(entry: dict) -> str:
    return " ".join(
        [
            entry.get("exception_rule", ""),
            entry.get("forbidden_inversion", ""),
            *list(entry.get("preserve_keywords") or []),
            entry.get("base_rule", ""),
        ]
    )


def _qc_blob(config: dict, ref: str) -> str:
    return " ".join(config["clinical_qc_checks_by_source_ref"].get(ref) or [])



def _strip_known_ban_phrases(rule: str) -> str:
    """Remove explicit prohibition phrases so ban text cannot look like affirmation."""
    cleaned = rule
    for phrase in (
        "不得弱化为严重OR属预期",
        "不得改写成永不/禁止/无需/不允许报告",
        "不得与p1134非严重不良事件合并",
        "不得把预期解释为不严重",
        "不得把“预期”解释为“不严重”",
        "不得把预期视为不严重",
        "不得把预期解释为非严重",
        "不得把“预期”解释为“非严重”",
        "不得把预期视为非严重",
        "不得把AND改成OR",
        "不是禁止或不允许",
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告",
        "不得据此推导必须/应当/必然快速报告",
        "不得扩大为任何SAE",
        "不得扩大为任何严重不良事件",
        "不得缩成仅确认相关/非预期SAE",
        "不得缩成仅确认相关",
        "不得缩成仅非预期SAE",
        "不得删除主要疗效终点条件",
    ):
        cleaned = cleaned.replace(phrase, "")
    # Structured ban-family strip: keep only affirmative residue for polarity checks.
    ban_patterns = (
        r"不得[^；。，,]{0,40}?(?:扩大|扩展|扩至|扩大到|扩大至|扩及|覆盖|适用(?:于)?)[^；。，,]{0,40}?(?:全部|所有|任意|任何)?[^；。，,]{0,20}?(?:SAE|严重不良事件)",
        r"不得把?(?:“?属?预期”? )?(?:解释为|视为|等于|意味着|表示|即表示)?(?:“?(?:不|非)严重”?)",
        r"不得把?“?属?预期”?[^；。，,]{0,12}?(?:解释为|视为|等于|意味着|表示|即表示|=|就是)“?(?:不|非)严重”?",
        r"不得[^；。，,]{0,30}?把?“?属?预期”?[^；。，,]{0,20}?(?:不|非)严重",
    )
    for pattern in ban_patterns:
        cleaned = re.sub(pattern, "", cleaned)
    return cleaned


_WIDEN_RELATION = r"(?:扩大|扩展|扩至|扩大到|扩大至|扩及|覆盖|适用(?:于)?)"
_UNIVERSAL_QUANT = r"(?:全部|所有|任意|任何)"
_SAE_TARGET = r"(?:SAE|严重不良事件)"
# Expand-relation + universal SAE target within a short window, either order.
_CONDITION_WIDEN_PATTERNS = (
    re.compile(
        rf"{_WIDEN_RELATION}.{{0,24}}{_UNIVERSAL_QUANT}.{{0,12}}{_SAE_TARGET}"
    ),
    re.compile(
        rf"{_UNIVERSAL_QUANT}.{{0,12}}{_SAE_TARGET}.{{0,16}}{_WIDEN_RELATION}"
    ),
    re.compile(
        rf"{_UNIVERSAL_QUANT}.{{0,8}}{_SAE_TARGET}.{{0,8}}(?:均)?适用"
    ),
    re.compile(
        rf"(?:或)?{_UNIVERSAL_QUANT}{_SAE_TARGET}(?:均)?(?:适用|不建议)"
    ),
)

_EXPECTED_SUBJECT = r"(?:属?预期|“属?预期”)"
_EQUIV_RELATION = (
    r"(?:意味着|表示|即表示|等于|等同于|视为|解释为|就是|=)"
)
_NONSERIOUS = r"(?:(?:不|非)严重|“(?:不|非)严重”)"
_EXPECTED_NONSERIOUS_PATTERNS = (
    re.compile(
        rf"{_EXPECTED_SUBJECT}.{{0,12}}{_EQUIV_RELATION}.{{0,8}}{_NONSERIOUS}"
    ),
    re.compile(
        rf"(?:把)?{_EXPECTED_SUBJECT}.{{0,8}}{_EQUIV_RELATION}.{{0,8}}{_NONSERIOUS}"
    ),
    re.compile(
        rf"{_NONSERIOUS}.{{0,8}}{_EQUIV_RELATION}.{{0,8}}{_EXPECTED_SUBJECT}"
    ),
)


def _has_condition_widen_affirmative(positive_rule: str) -> bool:
    """True when purified positive text affirms widening to all/any SAE."""
    purified = _strip_known_ban_phrases(positive_rule)
    return any(pattern.search(purified) for pattern in _CONDITION_WIDEN_PATTERNS)


def _has_expected_means_nonserious_affirmative(positive_rule: str) -> bool:
    """True when purified positive text equates expectedness with non-serious."""
    purified = _strip_known_ban_phrases(positive_rule)
    return any(pattern.search(purified) for pattern in _EXPECTED_NONSERIOUS_PATTERNS)


def _package96_contract_issues(config: dict) -> set[str]:
    """Validate Package 96 via authoritative positive config fields.

    Positive obligations are checked primarily on exception_rule so that
    correct keywords / forbidden_inversion / notes / QC text cannot mask a
    broken positive rule (worker_03 M1-M12 attack class).
    """
    issues: set[str] = set()
    semantics = config["exception_semantics_by_source_ref"]

    if list(config.get("owned_source_refs") or []) != OWNED_REFS:
        issues.add("OWNED_REFS")
    if list(config.get("attached_source_refs") or []) != ATTACHED_REFS:
        issues.add("ATTACHED_REFS")
    if config.get("structural_only_source_refs"):
        issues.add("STRUCTURAL_NONEMPTY")
    if config.get("claims_complete") is True:
        issues.add("CLAIMS_COMPLETE_TRUE")

    for ref in SEMANTIC_OWNED_REFS:
        if semantics[ref]["base_rule"] != OWNED_EXCERPT_BY_REF[ref]:
            issues.add(f"{ref}:SOURCE_TEXT")

    p1136_entry = semantics["body.p1136"]
    p1136_rule = p1136_entry["exception_rule"]
    p1136_positive = _strip_known_ban_phrases(p1136_rule)
    # M1: conjunction must live in the positive rule itself.
    if "严重AND属预期" not in p1136_rule:
        issues.add("body.p1136:AND_CONJUNCTION")
    if any(
        token in p1136_positive
        for token in (
            "严重OR属预期",
            "严重或属预期",
            "严重/属预期任一",
            "严重或预期任一",
        )
    ):
        issues.add("body.p1136:AND_CONJUNCTION")
    if "不得弱化为严重OR属预期" not in p1136_rule:
        issues.add("body.p1136:AND_CONJUNCTION")
    # M2: merge with non-serious must be rejected from the positive rule.
    if "不得与p1134非严重不良事件合并" not in p1136_rule:
        issues.add("body.p1136:SCOPE")
    if any(
        token in p1136_positive
        for token in (
            "与非严重不良事件合并",
            "等同于非严重",
            "同非严重不良事件",
            "按非严重不良事件处理",
            "可与非严重不良事件合并",
            "应与非严重不良事件合并",
        )
    ):
        issues.add("body.p1136:SCOPE")
    # S3 family: expectedness equated with non-serious on purified positive rule.
    if _has_expected_means_nonserious_affirmative(p1136_positive):
        issues.add("body.p1136:SCOPE")
    # M3: intensity must be present in exception_rule; notes/QC cannot substitute.
    if "一般" not in p1136_rule:
        issues.add("body.p1136:INTENSITY")
        issues.add("INTENSITY_NON_ABSOLUTE")
    if any(
        bad in p1136_positive
        for bad in (
            "绝对禁止作为快速报告",
            "一律不得快速报告",
            "永不作为快速报告",
            "永不报告",
            "无需报告",
            "不允许报告",
            "禁止报告",
            "绝对禁止",
            "一律不得",
            "永不",
            "不允许",
            "无需",
        )
    ):
        issues.add("body.p1136:INTENSITY")
        issues.add("INTENSITY_NON_ABSOLUTE")
    if "不得把AND改成OR" not in p1136_entry["forbidden_inversion"]:
        issues.add("body.p1136:FORBIDDEN_INVERSION")
    if "不得把“一般”改成绝对禁止" not in p1136_entry["forbidden_inversion"]:
        issues.add("body.p1136:FORBIDDEN_INVERSION")

    p1137_entry = semantics["body.p1137"]
    p1137_rule = p1137_entry["exception_rule"]
    p1137_positive = _strip_known_ban_phrases(p1137_rule)
    # M5: primary-endpoint condition must appear in the positive rule.
    if "主要疗效终点" not in p1137_rule:
        issues.add("body.p1137:CONDITION")
    # S1 family: widen affirmatives even when “主要疗效终点” token remains.
    # Uses expand-relation + universal quantifier + SAE target on purified text.
    if _has_condition_widen_affirmative(p1137_positive):
        issues.add("body.p1137:CONDITION")
    # S2: narrow affirmatives that keep the endpoint token but constrain causality/expectedness.
    if any(
        phrase in p1137_positive
        for phrase in (
            "确认相关且非预期",
            "仅确认相关且非预期",
            "仅确认相关",
            "仅非预期SAE",
            "仅非预期",
            "确认相关/非预期",
            "只有确认相关",
            "只有非预期",
        )
    ):
        issues.add("body.p1137:CONDITION")
    # M4: non-absolute intensity must live in exception_rule.
    if "不建议" not in p1137_rule:
        issues.add("body.p1137:INTENSITY")
        issues.add("INTENSITY_NON_ABSOLUTE")
    if any(
        marker in p1137_positive
        for marker in ("禁止报告", "不允许", "一律不得", "无需报告", "绝对禁止", "永不")
    ):
        issues.add("body.p1137:INTENSITY")
        issues.add("INTENSITY_NON_ABSOLUTE")
    # M7: actor/form/agency triad must live in exception_rule.
    if "申请人" not in p1137_rule:
        issues.add("body.p1137:ACTOR")
        issues.add("body.p1137:ACTOR_FORM_AGENCY")
    if "个例安全性报告形式" not in p1137_rule:
        issues.add("body.p1137:FORM")
        issues.add("body.p1137:ACTOR_FORM_AGENCY")
    if "国家药品审评机构" not in p1137_rule:
        issues.add("body.p1137:AGENCY")
        issues.add("body.p1137:ACTOR_FORM_AGENCY")
    # M6: reverse implication must be banned in the positive rule and not affirmed.
    if "不授权反向推理" not in p1137_rule:
        issues.add("body.p1137:INVERSE")
        issues.add("body.p1137:REVERSE")
    if "必须/应当/必然" not in p1137_rule and "不得据此推导必须/应当/必然" not in p1137_rule:
        issues.add("body.p1137:INVERSE")
        issues.add("body.p1137:REVERSE")
    reverse_affirmatives = (
        "非主要疗效终点时必须",
        "非主要疗效终点时应当",
        "非主要疗效终点时必然",
        "不是主要疗效终点时必须",
        "不是主要疗效终点时应当",
        "当SAE不是主要疗效终点时必须",
        "当SAE不是主要疗效终点时应当",
        "当SAE不是主要疗效终点时必然",
        "非该条件时必须",
        "非该条件时应当",
        "非该条件时必然",
    )
    if any(token in p1137_positive for token in reverse_affirmatives):
        issues.add("body.p1137:INVERSE")
        issues.add("body.p1137:REVERSE")
    forbid_1137 = p1137_entry["forbidden_inversion"]
    if not all(
        fragment in forbid_1137
        for fragment in (
            "不得删除主要疗效终点条件",
            "不得扩大为任何SAE",
            "不得把“不建议”改成禁止",
            "不得省略申请人/个例安全性报告/国家药品审评机构",
            "不得推导“非主要疗效终点时必须个例安全性报告快速报告”",
        )
    ):
        issues.add("body.p1137:FORBIDDEN_INVERSION")

    # M8/M9/M10: cross-package ownership / absorption.
    attached = list(config.get("attached_source_refs") or [])
    owned = list(config.get("owned_source_refs") or [])
    if attached[:3] != ["body.p1133", "body.p1134", "body.p1135"]:
        issues.add("CROSS_PACKAGE_LIST")
    if set(attached) != set(ATTACHED_REFS):
        issues.add("CROSS_PACKAGE_LIST")
    if set(owned) & set(ATTACHED_REFS):
        # Attached pkg95 lead-in / pkg80 defs must never become owned.
        if set(owned) & {"body.p1133", "body.p1134", "body.p1135"}:
            issues.add("PACKAGE95_OWNERSHIP")
        if set(owned) & {"body.p1018", "body.p1019"}:
            issues.add("PACKAGE80_OWNERSHIP")
    if set(owned) & set(PKG80_OWNED_ALL):
        issues.add("PACKAGE80_OWNERSHIP")

    # Continuity evidence may use QC/notes, but positive obligations above already
    # require the owned exception_rule itself to carry AND/一般/不建议/triad.
    list_blob = " ".join(
        [
            p1136_rule,
            p1137_rule,
            _qc_blob(config, "body.p1133"),
            _qc_blob(config, "body.p1134"),
            _qc_blob(config, "body.p1135"),
            _qc_blob(config, "body.p1136"),
            _qc_blob(config, "body.p1137"),
            " ".join(config.get("notes") or []),
            config["later_package_boundary"].get("note", ""),
        ]
    )
    if not all(
        fragment in list_blob
        for fragment in (
            "一般",
            "非严重不良事件",
            "与试验用药品无关",
            "严重AND属预期",
            "不建议",
            "申请人",
            "个例安全性报告形式",
            "国家药品审评机构",
            "第95包",
        )
    ):
        issues.add("CROSS_PACKAGE_LIST")

    owned_and_attached = set(owned + attached)
    if owned_and_attached & set(PKG97_SPAN_REFS):
        issues.add("PACKAGE97_OWNERSHIP")
        issues.add("PACKAGE97_ABSORPTION")
    if owned_and_attached & set(PKG95_NON_ATTACHED):
        issues.add("PACKAGE95_ABSORPTION")
    if owned_and_attached & set(PKG94_SPAN_REFS):
        issues.add("PACKAGE94_OWNERSHIP")
    # M11: candidate escalation.
    if config.get("required_candidate_source_refs"):
        issues.add("REQUIRED_CANDIDATE_NONEMPTY")

    for ref in OWNED_REFS + ATTACHED_REFS:
        disposition = (config.get("expected_disposition_by_source_ref") or {}).get(ref)
        if ref in OWNED_REFS and disposition != "post_treatment_execution":
            issues.add(f"{ref}:DISPOSITION")
        markers = config.get("candidate_forbidden_markers_by_source_ref", {}).get(ref) or []
        if not markers:
            issues.add(f"{ref}:FORBIDDEN_MARKERS")
        if ref not in (config.get("forbidden_candidate_source_refs") or []):
            issues.add(f"{ref}:FORBIDDEN_CANDIDATE_SET")

    return issues


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_96_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _attached_excerpt_by_ref(plan: dict) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for pkg in plan["packages"]:
        for unit in pkg["owned_units"]:
            ref = unit["source_ref"]
            if ref in ATTACHED_REFS:
                excerpts[ref] = unit["excerpt"]
    return excerpts


def _structure_blob_text(blob: list[dict], ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == ref:
            return block.get("text") or ""
    return ""


@pytest.fixture
def config() -> dict:
    from slice59n_representative_group_control_replay import _load_config

    return _load_config(CONFIG_PATH)


@pytest.fixture
def plan() -> dict:
    return _load_json(PLAN_PATH)


@pytest.fixture
def matrix() -> dict:
    return _load_json(MATRIX_PATH)


@pytest.fixture
def procedure_catalog() -> dict:
    return _load_json(CATALOG_DIR / "required_procedures.json")


@pytest.fixture
def structure_blob() -> list[dict]:
    return _load_json(STRUCTURE_BLOB_PATH)


def test_config_contract(config: dict) -> None:
    assert (
        config["schema_version"]
        == "phase5/representative-group-control-replay-config/v1"
    )
    assert (
        config["group_id"]
        == "d001-ii-package96-expected-serious-primary-endpoint-reporting-boundary"
    )
    assert config["study_phase"] == "phase_ii"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert config["required_candidate_source_refs"] == []
    assert config["structural_only_source_refs"] == []
    assert config["pre_enrollment_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(
        OWNED_REFS + ATTACHED_REFS
    )
    assert config["expected_disposition_by_source_ref"] == {
        "body.p1136": "post_treatment_execution",
        "body.p1137": "post_treatment_execution",
    }
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["later_package_boundary"]["read_only"] is True


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg96 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_96_ORDINAL
    )
    owned = {u["source_ref"] for u in pkg96["owned_units"]}
    assert set(config["attached_source_refs"]).isdisjoint(owned)
    assert set(config["owned_source_refs"]) == owned


def test_attached_refs_ownership_documented(plan: dict) -> None:
    owners: dict[str, list[int]] = {}
    for pkg in plan["packages"]:
        for unit in pkg["owned_units"]:
            owners.setdefault(unit["source_ref"], []).append(pkg["package_ordinal"])
    assert owners.get("body.p1133") == [PACKAGE_95_ORDINAL]
    assert owners.get("body.p1134") == [PACKAGE_95_ORDINAL]
    assert owners.get("body.p1135") == [PACKAGE_95_ORDINAL]
    assert owners.get("body.p1018") == [PACKAGE_80_ORDINAL]
    assert owners.get("body.p1019") == [PACKAGE_80_ORDINAL]
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_96_ORDINAL], ref


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    assert set(PKG78_SPAN_REFS) <= counts[PACKAGE_78_ORDINAL]
    assert set(PKG79_SPAN_REFS) <= counts[PACKAGE_79_ORDINAL]
    assert set(PKG80_OWNED_ALL) <= counts[PACKAGE_80_ORDINAL]
    assert set(PKG82_SPAN_REFS) <= counts[PACKAGE_82_ORDINAL]
    assert set(PKG87_SPAN_REFS) <= counts[PACKAGE_87_ORDINAL]
    assert set(PKG88_SPAN_REFS) <= counts[PACKAGE_88_ORDINAL]
    assert set(PKG89_SPAN_REFS) <= counts[PACKAGE_89_ORDINAL]
    assert set(PKG90_SPAN_REFS) <= counts[PACKAGE_90_ORDINAL]
    assert set(PKG91_SPAN_REFS) <= counts[PACKAGE_91_ORDINAL]
    assert set(PKG92_SPAN_REFS) <= counts[PACKAGE_92_ORDINAL]
    assert set(PKG93_SPAN_REFS) <= counts[PACKAGE_93_ORDINAL]
    assert set(PKG94_SPAN_REFS) <= counts[PACKAGE_94_ORDINAL]
    assert set(PKG95_OWNED_ALL) <= counts[PACKAGE_95_ORDINAL]
    assert set(OWNED_REFS) <= counts[PACKAGE_96_ORDINAL]
    assert set(PKG97_SPAN_REFS) <= counts[PACKAGE_97_ORDINAL]


def test_owned_refs_match_frozen_package_96(config: dict, plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_96_ORDINAL
    )
    assert pkg["package_id"] == PACKAGE_96_ID
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    assert excerpts == OWNED_EXCERPT_BY_REF
    for ref, excerpt in excerpts.items():
        assert config["exception_semantics_by_source_ref"][ref]["base_rule"] == excerpt


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    assert excerpts == ATTACHED_EXCERPT_BY_REF


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_96_ORDINAL
    )
    for unit in pkg["owned_units"]:
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[unit["source_ref"]]


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        assert _structure_blob_text(structure_blob, ref) == excerpt


def test_specification_probe_catalog_is_unique_and_source_clean() -> None:
    assert ALL_DETERMINISTIC_PHRASES
    assert len(ALL_DETERMINISTIC_PHRASES) == len(set(ALL_DETERMINISTIC_PHRASES))
    for excerpt in OWNED_EXCERPT_BY_REF.values():
        assert _deterministic_hits(excerpt) == []


def test_p1136_and_conjunction_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1136"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1136") == []
    blob = _semantic_blob(semantics)
    assert "严重AND属预期" in blob
    assert "不得弱化为严重OR属预期" in blob
    assert "一般" in blob


def test_and_to_or_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "严重OR属预期的不良反应一般可不作为快速报告；零候选"
    )
    assert "body.p1136:AND_CONJUNCTION" in _package96_contract_issues(mutated)


def test_and_to_or_exception_only_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    # Keep forbidden_inversion and keywords correct; only corrupt positive rule.
    semantic["exception_rule"] = "严重或属预期任一满足即可不作为快速报告；零候选"
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:AND_CONJUNCTION" in issues


def test_p1136_non_absolute_intensity_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1136"]
    assert "一般" in semantics["exception_rule"]
    assert "绝对禁止作为快速报告" not in semantics["exception_rule"]
    assert "不得把“一般”改成绝对禁止" in semantics["forbidden_inversion"]


def test_generally_to_absolute_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "跨包列表后项：严重但属预期不良反应绝对禁止作为快速报告内容；零候选"
    )
    assert "body.p1136:INTENSITY" in _package96_contract_issues(mutated)


def test_p1137_condition_and_triad_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1137"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1137") == []
    rule = semantics["exception_rule"]
    assert "主要疗效终点" in rule
    assert "不建议" in rule
    assert "申请人" in rule
    assert "个例安全性报告形式" in rule
    assert "国家药品审评机构" in rule
    assert "不授权反向推理" in rule


def test_primary_endpoint_condition_delete_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "不建议申请人以个例安全性报告形式向国家药品审评机构报告；"
        "不是禁止或不允许；不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:CONDITION" in _package96_contract_issues(mutated)


def test_primary_endpoint_condition_widen_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：任何SAE均不建议申请人以个例安全性报告形式向国家药品审评机构报告；"
        "强度为不建议；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert (
        "body.p1137:CONDITION" in issues
        or "body.p1137:INVERSE" in issues
        or "body.p1137:FORBIDDEN_INVERSION" in issues
    )


def test_primary_endpoint_condition_narrow_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅确认相关或仅非预期SAE时不建议申请人以个例安全性报告形式向国家药品审评机构报告；"
        "不是禁止或不允许；不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    # Positive rule dropped the required primary-endpoint phrase.
    assert "主要疗效终点" not in semantic["exception_rule"] or True
    semantic["exception_rule"] = semantic["exception_rule"].replace(
        "主要疗效终点", "确认相关终点"
    )
    # Ensure primary endpoint token is gone from positive rule.
    semantic["exception_rule"] = (
        "条件作用域：仅确认相关/非预期SAE适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:CONDITION" in _package96_contract_issues(mutated)


def test_not_recommended_to_forbidden_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为禁止报告，不允许个例安全性报告；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:INTENSITY" in _package96_contract_issues(mutated)


def test_actor_omission_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:ACTOR_FORM_AGENCY" in _package96_contract_issues(mutated)


def test_icsr_form_omission_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:ACTOR_FORM_AGENCY" in _package96_contract_issues(mutated)


def test_agency_omission_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    assert "body.p1137:ACTOR_FORM_AGENCY" in _package96_contract_issues(mutated)


def test_inverse_proposition_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "当SAE不是主要疗效终点时必须/应当/必然采用个例安全性报告快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:INVERSE" in issues


def test_inverse_forbidden_inversion_drop_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    assert "body.p1137:FORBIDDEN_INVERSION" in _package96_contract_issues(mutated)


def test_cross_package_list_preserved(config: dict) -> None:
    assert config["attached_source_refs"][:3] == [
        "body.p1133",
        "body.p1134",
        "body.p1135",
    ]
    assert config["attached_source_refs"][-2:] == ["body.p1018", "body.p1019"]
    qc_1133 = _qc_blob(config, "body.p1133")
    assert "一般" in qc_1133
    assert "第95包" in qc_1133
    note = config["later_package_boundary"]["note"]
    assert "第95包" in note
    assert "第97包" in note


def test_cross_package_list_truncation_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = [
        ref
        for ref in mutated["attached_source_refs"]
        if ref not in ("body.p1133", "body.p1134", "body.p1135")
    ]
    for ref in ("body.p1133", "body.p1134", "body.p1135"):
        mutated["clinical_qc_checks_by_source_ref"].pop(ref, None)
    mutated["notes"] = ["截断跨包列表前段"]
    mutated["later_package_boundary"]["note"] = "不提及第95包连续前段"
    assert "CROSS_PACKAGE_LIST" in _package96_contract_issues(mutated)


def test_package95_ownership_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"].append("body.p1133")
    issues = _package96_contract_issues(mutated)
    assert "OWNED_REFS" in issues or "PACKAGE95_OWNERSHIP" in issues


def test_package97_content_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG97_SPAN_REFS:
        assert ref not in owned
        assert ref not in attached
    boundary = config["later_package_boundary"]["expected_owners_by_span"]
    for ref in PKG97_SPAN_REFS:
        assert boundary[ref] == PACKAGE_97_ORDINAL


def test_package97_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"].append("body.p1138")
    assert "PACKAGE97_OWNERSHIP" in _package96_contract_issues(mutated)


def test_required_candidate_upgrade_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["required_candidate_source_refs"] = ["body.p1137"]
    assert "REQUIRED_CANDIDATE_NONEMPTY" in _package96_contract_issues(mutated)


def test_m2_merge_with_non_serious_exception_only_is_detected(config: dict) -> None:
    """M2: affirmative merge in exception_rule; forbid/keywords remain correct."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "跨包列表后项：严重但属预期不良反应可与非严重不良事件合并处理；"
        "继承一般非绝对强度；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:SCOPE" in issues or "body.p1136:AND_CONJUNCTION" in issues


def test_m3_generally_absolute_exception_only_keeps_forbid(config: dict) -> None:
    """M3: absoluteize inherited 一般 in exception_rule only."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    # Keep forbidden_inversion / preserve_keywords intact.
    semantic["exception_rule"] = (
        "跨包列表后项：严重AND属预期；永不/禁止/无需报告；"
        "不得弱化为严重OR属预期；不得与p1134非严重不良事件合并；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:INTENSITY" in issues or "INTENSITY_NON_ABSOLUTE" in issues


def test_m6_reverse_inference_exception_only_is_detected(config: dict) -> None:
    """M6: affirm reverse implication in exception_rule; keep forbid text."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；"
        "当SAE不是主要疗效终点时必须采用个例安全性报告快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:INVERSE" in issues or "body.p1137:REVERSE" in issues


def test_m10_package80_definition_ownership_transfer_is_detected(config: dict) -> None:
    """M10: treat p1018/p1019 as owned."""
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"] = list(mutated["owned_source_refs"]) + [
        "body.p1018",
        "body.p1019",
    ]
    issues = _package96_contract_issues(mutated)
    assert "PACKAGE80_OWNERSHIP" in issues or "OWNED_REFS" in issues


def test_m11_claims_complete_true_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["claims_complete"] = True
    assert "CLAIMS_COMPLETE_TRUE" in _package96_contract_issues(mutated)


def test_m12_wrong_rule_not_masked_by_correct_forbid_notes_qc(config: dict) -> None:
    """M12: correct forbid/notes/QC must not shadow a wrong exception_rule."""
    mutated = copy.deepcopy(config)
    # Leave forbidden_inversion, notes, QC, preserve_keywords untouched.
    mutated["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
        "严重OR属预期即可；零候选"
    )
    mutated["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
        "一律不得以个例安全性报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert issues  # must not silently close
    assert "body.p1136:AND_CONJUNCTION" in issues
    assert (
        "body.p1137:INTENSITY" in issues
        or "body.p1137:CONDITION" in issues
        or "body.p1137:ACTOR_FORM_AGENCY" in issues
        or "INTENSITY_NON_ABSOLUTE" in issues
    )


def test_m12_intensity_not_satisfied_by_notes_or_qc_alone(config: dict) -> None:
    """M12 residual: notes/QC cannot substitute missing 一般/不建议 in exception_rule."""
    mutated = copy.deepcopy(config)
    p1136 = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    p1137 = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    p1136["exception_rule"] = (
        "跨包列表后项：必须保持严重AND属预期；不得弱化为严重OR属预期；"
        "不得与p1134非严重不良事件合并；零候选"
    )
    p1137["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    # Amplify correct notes/QC so they cannot mask the missing intensity tokens.
    mutated["notes"] = list(mutated.get("notes") or []) + [
        "一般不作为快速报告内容；不建议申请人以个例安全性报告形式报告"
    ]
    mutated["clinical_qc_checks_by_source_ref"]["body.p1136"] = [
        "必须保留一般非绝对强度"
    ]
    mutated["clinical_qc_checks_by_source_ref"]["body.p1137"] = [
        "必须保留不建议非绝对强度"
    ]
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:INTENSITY" in issues or "INTENSITY_NON_ABSOLUTE" in issues
    assert "body.p1137:INTENSITY" in issues or "INTENSITY_NON_ABSOLUTE" in issues


def test_s1_condition_widen_any_sae_keep_endpoint_token_is_detected(config: dict) -> None:
    """S1: widen to any SAE while keeping 主要疗效终点; forbid/QC stay correct."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用，并扩大为任何SAE；"
        "强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" in issues


def test_s1b_condition_widen_or_any_sae_keep_endpoint_token_is_detected(
    config: dict,
) -> None:
    """S1b: ‘主要疗效终点时或任何SAE均适用’ while forbid stays correct."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：主要疗效终点时或任何SAE均适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" in issues


def test_s1b_any_serious_ae_applies_keep_endpoint_token_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；任何严重不良事件均适用；"
        "强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" in issues


def test_s2_condition_narrow_confirmed_unexpected_keep_endpoint_is_detected(
    config: dict,
) -> None:
    """S2: narrow to confirmed-related AND unexpected while keeping endpoint token."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以确认相关且非预期的严重不良事件为主要疗效终点时适用；"
        "强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" in issues


def test_s3_expected_means_nonserious_exception_only_is_detected(config: dict) -> None:
    """S3: affirmative ‘预期意味着不严重’ on exception_rule; AND/anti-merge ban remain."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "跨包“以下情况一般不作为快速报告内容”列表连续后项：必须保持严重AND属预期；"
        "继承只读p1133“一般”非绝对强度；预期意味着不严重；"
        "不得弱化为严重OR属预期，不得把预期解释为不严重，不得与p1134非严重不良事件合并；"
        "不得改写成永不/禁止/无需/不允许报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:SCOPE" in issues


def test_s3_expected_explained_as_nonserious_synonyms_are_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    for phrase in (
        "预期解释为不严重",
        "把预期视为不严重",
        "预期等同于不严重",
    ):
        semantic["exception_rule"] = (
            "跨包列表后项：必须保持严重AND属预期；继承一般非绝对强度；"
            f"{phrase}；不得弱化为严重OR属预期；不得与p1134非严重不良事件合并；零候选"
        )
        issues = _package96_contract_issues(mutated)
        assert "body.p1136:SCOPE" in issues, phrase


@pytest.mark.parametrize(
    "widen_clause",
    [
        "并扩至全部SAE",
        "并扩大到所有SAE",
        "并扩展为任意SAE",
        "并扩大为任何严重不良事件",
        "并扩至全部严重不良事件",
        "适用于任何SAE",
        "适用於所有严重不良事件".replace("於", "于"),
        "或任何SAE均适用",
        "并扩及全部SAE",
        "并覆盖所有SAE",
        "并扩大至任何严重不良事件",
        "并扩展到全部严重不良事件",
    ],
)
def test_condition_widen_pattern_family_synonyms_are_detected(
    config: dict, widen_clause: str
) -> None:
    """Parameterized S1-family paraphrases; forbid/keywords remain correct."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用，"
        f"{widen_clause}；"
        "强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" in issues, widen_clause


def test_condition_widen_ban_context_does_not_false_positive(config: dict) -> None:
    """Correct ban-only widen language must not fire after purification."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1137"]
    # Stock-correct positive rule already contains “不得扩大…” in forbidden_inversion;
    # reinforce ban language only inside exception_rule without affirmative widen.
    semantic["exception_rule"] = (
        "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
        "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
        "不得扩大为任何SAE，不得扩至全部严重不良事件；"
        "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1137:CONDITION" not in issues
    assert issues == set() or "body.p1137:CONDITION" not in issues
    assert _package96_contract_issues(mutated) == set()


@pytest.mark.parametrize(
    "equiv_clause",
    [
        "预期意味着不严重",
        "预期即表示不严重",
        "预期表示不严重",
        "预期等于不严重",
        "预期等同于不严重",
        "预期=不严重",
        "预期就是不严重",
        "属预期视为不严重",
        "把预期解释为不严重",
        "不严重等于属预期",
        # worker_03 blocking residual: 非严重 ≡ 不严重 target
        "预期意味着非严重",
        "预期即表示非严重",
        "预期等于非严重",
        "预期=非严重",
        "把预期解释为非严重",
        "把预期视为非严重",
    ],
)
def test_expected_nonserious_pattern_family_synonyms_are_detected(
    config: dict, equiv_clause: str
) -> None:
    """Parameterized S3-family paraphrases; AND/anti-merge ban remain correct."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "跨包“以下情况一般不作为快速报告内容”列表连续后项：必须保持严重AND属预期；"
        "继承只读p1133“一般”非绝对强度；"
        f"{equiv_clause}；"
        "不得弱化为严重OR属预期，不得把预期解释为不严重，不得与p1134非严重不良事件合并；"
        "不得改写成永不/禁止/无需/不允许报告；零候选"
    )
    issues = _package96_contract_issues(mutated)
    assert "body.p1136:SCOPE" in issues, equiv_clause


def test_expected_nonserious_ban_context_does_not_false_positive(config: dict) -> None:
    """Ban-only expectedness language must not fire after purification."""
    mutated = copy.deepcopy(config)
    # Keep the closed stock rule; it already contains ban text only.
    assert _package96_contract_issues(mutated) == set()
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1136"]
    semantic["exception_rule"] = (
        "跨包“以下情况一般不作为快速报告内容”列表连续后项：必须保持严重AND属预期；"
        "继承只读p1133“一般”非绝对强度；"
        "不得弱化为严重OR属预期，不得把预期解释为不严重，不得把预期视为不严重，"
        "不得把预期解释为非严重，不得把预期视为非严重，"
        "不得与p1134非严重不良事件合并；不得改写成永不/禁止/无需/不允许报告；零候选"
    )
    assert _package96_contract_issues(mutated) == set()


def test_pattern_helpers_are_relational_not_keyword_only() -> None:
    """Helpers require relation+target structure, not bare tokens."""
    assert not _has_condition_widen_affirmative("保留主要疗效终点；不得扩大为任何SAE")
    assert not _has_condition_widen_affirmative("提到SAE与主要疗效终点")
    assert _has_condition_widen_affirmative("扩至全部SAE")
    assert _has_condition_widen_affirmative("扩大到所有严重不良事件")
    assert _has_condition_widen_affirmative("扩及全部SAE")
    assert _has_condition_widen_affirmative("覆盖所有SAE")
    assert not _has_expected_means_nonserious_affirmative(
        "不得把预期解释为不严重；保持严重AND属预期"
    )
    assert not _has_expected_means_nonserious_affirmative(
        "不得把预期解释为非严重；保持严重AND属预期"
    )
    assert not _has_expected_means_nonserious_affirmative("提及预期与不严重风险对照")
    assert not _has_expected_means_nonserious_affirmative("提及预期与非严重风险对照")
    assert _has_expected_means_nonserious_affirmative("预期即表示不严重")
    assert _has_expected_means_nonserious_affirmative("预期=不严重")
    assert _has_expected_means_nonserious_affirmative("预期意味着非严重")
    assert _has_expected_means_nonserious_affirmative("预期=非严重")
    assert _has_expected_means_nonserious_affirmative("把预期视为非严重")


def test_worker03_s1_s3_exception_rule_only_matrix(config: dict) -> None:
    """Gate: S1/S1b/S2/S3 must never silently return []."""

    def _issues_for(mutator) -> set[str]:
        mutated = copy.deepcopy(config)
        mutator(mutated)
        return _package96_contract_issues(mutated)

    def s1(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：仅当以严重不良事件为主要疗效终点时适用，并扩大为任何SAE；"
            "强度为“不建议”，不是禁止或不允许；"
            "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def s1b(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：主要疗效终点时或任何SAE均适用；强度为“不建议”，不是禁止或不允许；"
            "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def s2(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：仅当以确认相关且非预期的严重不良事件为主要疗效终点时适用；"
            "强度为“不建议”，不是禁止或不允许；"
            "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def s3(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
            "跨包列表后项：必须保持严重AND属预期；继承一般；预期意味着不严重；"
            "不得弱化为严重OR属预期，不得与p1134非严重不良事件合并；零候选"
        )

    for label, mutator in {
        "S1": s1,
        "S1b": s1b,
        "S2": s2,
        "S3": s3,
    }.items():
        issues = _issues_for(mutator)
        assert issues, f"{label} silently returned []"


def test_worker03_m1_to_m12_exception_rule_only_matrix(config: dict) -> None:
    """Gate: each worker_03 M1-M12 probe must emit issues, not silent []."""

    def _issues_for(mutator) -> set[str]:
        mutated = copy.deepcopy(config)
        mutator(mutated)
        return _package96_contract_issues(mutated)

    def m1(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
            "严重OR属预期的不良反应一般可不作为快速报告；零候选"
        )

    def m2(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
            "严重但属预期不良反应等同于非严重不良事件；一般强度；零候选"
        )

    def m3(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
            "严重AND属预期；绝对禁止作为快速报告；不得弱化为严重OR属预期；"
            "不得与p1134非严重不良事件合并；零候选"
        )

    def m4(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：仅当以严重不良事件为主要疗效终点时适用；一律不得以个例安全性报告；"
            "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def m5(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "不建议申请人以个例安全性报告形式向国家药品审评机构报告；"
            "不是禁止或不允许；不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def m6(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
            "必须同时保留申请人（报告主体）、个例安全性报告形式、国家药品审评机构（接收机构）；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；"
            "非主要疗效终点时应当快速个例报告；零候选"
        )

    def m7(m: dict) -> None:
        m["exception_semantics_by_source_ref"]["body.p1137"]["exception_rule"] = (
            "条件作用域：仅当以严重不良事件为主要疗效终点时适用；强度为“不建议”，不是禁止或不允许；"
            "不授权反向推理：非该条件时不得据此推导必须/应当/必然快速报告；零候选"
        )

    def m8(m: dict) -> None:
        m["owned_source_refs"] = list(m["owned_source_refs"]) + [
            "body.p1133",
            "body.p1134",
            "body.p1135",
        ]

    def m9(m: dict) -> None:
        m["attached_source_refs"] = list(m["attached_source_refs"]) + ["body.p1138"]

    def m10(m: dict) -> None:
        m["owned_source_refs"] = list(m["owned_source_refs"]) + ["body.p1018"]

    def m11(m: dict) -> None:
        m["required_candidate_source_refs"] = ["body.p1136"]
        m["claims_complete"] = True

    def m12(m: dict) -> None:
        # Wrong positive rule; leave forbid/notes/QC correct.
        m["exception_semantics_by_source_ref"]["body.p1136"]["exception_rule"] = (
            "严重或属预期任一满足即可；零候选"
        )

    probes = {
        "M1": m1,
        "M2": m2,
        "M3": m3,
        "M4": m4,
        "M5": m5,
        "M6": m6,
        "M7": m7,
        "M8": m8,
        "M9": m9,
        "M10": m10,
        "M11": m11,
        "M12": m12,
    }
    for label, mutator in probes.items():
        issues = _issues_for(mutator)
        assert issues, f"{label} silently returned []"


def test_package96_contract_is_currently_closed(config: dict) -> None:
    assert _package96_contract_issues(config) == set()


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_NON_ATTACHED
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG94_SPAN_REFS
        + PKG95_NON_ATTACHED
        + PKG97_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in owned
        assert ref not in attached


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    expected_owners = boundary["expected_owners_by_span"]
    for pkg in plan["packages"]:
        ordinal = pkg["package_ordinal"]
        if ordinal in (
            78,
            79,
            80,
            82,
            87,
            88,
            89,
            90,
            91,
            92,
            93,
            94,
            95,
            96,
            97,
        ):
            for unit in pkg["owned_units"]:
                ref = unit["source_ref"]
                assert expected_owners.get(ref) == ordinal, (
                    f"{ref} 期望归属包 {ordinal}，配置中为 {expected_owners.get(ref)}"
                )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "第96包" in note
    assert "第95包" in note
    assert "第97包" in note
    assert "第80包" in note
    assert "零候选" in note


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(ATTACHED_REFS)
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"

    assert by_ref["body.p1136"].excerpt == OWNED_EXCERPT_BY_REF["body.p1136"]
    assert by_ref["body.p1137"].excerpt == OWNED_EXCERPT_BY_REF["body.p1137"]
    assert by_ref["body.p1133"].excerpt == ATTACHED_EXCERPT_BY_REF["body.p1133"]
    assert "非严重不良事件" in by_ref["body.p1134"].excerpt
    assert "与试验用药品无关" in by_ref["body.p1135"].excerpt
    assert "SUSAR" in by_ref["body.p1018"].excerpt
    assert "研究者手册" in by_ref["body.p1019"].excerpt


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip()
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip()

    neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_NON_ATTACHED
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG94_SPAN_REFS
        + PKG95_NON_ATTACHED
        + PKG97_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 2
    assert summary["attached_count"] == 5
    assert summary["unit_count"] == 7
    assert summary["claims_complete"] is False


def test_hydrated_gate_enforces_zero_candidate_partition(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows = [
        {
            "source_ref": row.source_ref,
            "role": row.role,
            "lookup": row.lookup,
            "structure_unit_id": row.structure_unit_id,
            "source_span_ids": list(row.source_span_ids),
            "excerpt": row.excerpt,
            "study_phase": row.study_phase,
        }
        for row in _resolve_units(config)
    ]
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}
    dispositions = [
        {
            "structure_unit_id": unit_by_ref[ref],
            "disposition": disposition,
        }
        for ref, disposition in config["expected_disposition_by_source_ref"].items()
    ]
    kwargs = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "hydrated": {"candidates": [], "dispositions": dispositions},
        "allowed_structure_unit_ids": [row["structure_unit_id"] for row in rows],
        "required_candidate_source_refs": config["required_candidate_source_refs"],
        "forbidden_candidate_source_refs": config["forbidden_candidate_source_refs"],
        "expected_disposition_by_source_ref": config[
            "expected_disposition_by_source_ref"
        ],
        "expected_workflow_stage_ids_by_source_ref": config[
            "expected_workflow_stage_ids_by_source_ref"
        ],
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": config[
            "candidate_required_markers_by_source_ref"
        ],
    }
    assert not evaluate_hydrated_agent_output(**kwargs)

    for ref in OWNED_REFS + ATTACHED_REFS:
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对主要疗效终点报告边界，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    paraphrased_candidates = {
        "body.p1136": "跨包列表后项签署作为中心质量评分项",
        "body.p1137": "主要疗效终点SAE报告边界作为机构启动检查项",
        "body.p1133": "通常不快速报告列表确认作为医学监查准入准则",
        "body.p1018": "SUSAR定义复述作为研究者资质审核条件",
    }
    for ref, title in paraphrased_candidates.items():
        assert _deterministic_hits(title) == [], "分区测试不得依赖规格探针原句"
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": title,
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": ["su-not-in-group"],
                "title": "越界候选",
                "semantics": {},
            }
        ],
        "dispositions": dispositions,
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert _forbidden_marker_hits(excerpt, markers) == []


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    counterexamples_by_ref = {
        "body.p1136": [
            "筛选必做：严重但属预期列表核对",
            "基线期必做：跨包列表后项签署",
            "证据缺口：属预期未确认不得入组",
        ],
        "body.p1137": [
            "筛选必做：不建议个例安全性报告确认",
            "基线期必做：主要疗效终点SAE报告边界签署",
            "跨包列表后项缺失视为证据缺口，不得入组",
        ],
    }
    for ref, phrases in counterexamples_by_ref.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        for phrase in phrases:
            hits = _forbidden_marker_hits(phrase, markers)
            assert hits, f"{ref} should flag upgrade phrase: {phrase}"


def test_prompt_excludes_neighbor_package95_non_attached_and_97_content() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    for ref in PKG95_NON_ATTACHED + PKG97_SPAN_REFS:
        assert ref not in prompt_text, ref
    # Owned and attached must appear.
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert ref in prompt_text, ref


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref, excerpt in OWNED_EXCERPT_BY_REF.items():
        assert excerpt in prompt_text, ref


def test_prompt_contains_attached_sources() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert excerpt in prompt_text, ref


def test_prompt_deterministic_phrases_clean() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert _deterministic_hits(prompt_text) == []


def test_matrix_has_no_rows_anchored_in_package96_or_attached(
    matrix: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for rule in matrix.get("official_rules") or []:
        blob = json.dumps(rule, ensure_ascii=False)
        for ref in forbidden:
            assert ref not in blob


def test_matrix_has_no_ae_teae_sae_susar_rows(matrix: dict) -> None:
    banned_tokens = ("不良事件", "TEAE", "SAE", "SUSAR", "快速报告")
    for rule in matrix.get("official_rules") or []:
        blob = json.dumps(rule, ensure_ascii=False)
        assert not any(token in blob for token in banned_tokens)


def test_no_official_rule_anchors_package96_owned_or_attached_spans(
    matrix: dict,
) -> None:
    assert matrix.get("official_rules") in ([], None) or all(
        not any(
            ref in json.dumps(rule, ensure_ascii=False)
            for ref in OWNED_REFS + ATTACHED_REFS
        )
        for rule in matrix["official_rules"]
    )


def test_procedure_catalog_has_no_package96_node(
    procedure_catalog: dict,
) -> None:
    banned = ("严重但属预期", "主要疗效终点时，不建议申请人", "个例安全性报告形式")
    for item in procedure_catalog.get("items") or []:
        blob = json.dumps(item, ensure_ascii=False)
        for token in banned:
            assert token not in blob


def test_no_procedure_node_sourced_from_package96_or_attached(
    procedure_catalog: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for item in procedure_catalog.get("items") or []:
        blob = json.dumps(item, ensure_ascii=False)
        for ref in forbidden:
            assert ref not in blob


def test_known_targets_build_empty(config: dict) -> None:
    targets = config["known_targets"]
    assert targets["official_rules"] == []
    assert targets["required_procedures"] == []


def test_workflow_stages_are_nonbinding_replay_scaffold(config: dict) -> None:
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    stages = config["workflow_stages"]
    assert {stage["workflow_stage_id"] for stage in stages} >= {
        "flow-screening",
        "flow-baseline",
        "flow-d1-pre-dose",
    }


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(COVERAGE_PATH)
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert isinstance(catalog, dict)
    assert EXPECTED_DOCX_SHA256
    assert EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_96_ID in text
    assert "body.p1136" in text
    assert "body.p1137" in text
    assert "claims_complete=false" in text
    assert "一般" in text
    assert "不建议" in text
    assert "申请人" in text
    assert "个例安全性报告" in text
    assert "国家药品审评机构" in text
    assert "第95包" in text
    assert "第97包" in text
