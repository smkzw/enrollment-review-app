#!/usr/bin/env python3
"""Slice61cg model-free source-closure regressions.

Locks the D001 II package 95 sponsor scientific assessment / SUSAR expedited
reporting boundary (frozen plan package 95: 申办者的报告要求,
body.p1124-p1135) to its authoritative sources before any semantic replay
decision:

- config contract and role partition: 12 owned refs body.p1124-p1135
  (p1124 structural only; p1125 any-source scientific assessment dimensions;
  p1126 recipient set; p1127 (definite-or-suspected) AND unexpected AND
  serious conjunction; p1128/p1129 separated 7+8 / 15 day clocks; p1130 two
  starts one end; p1131 post-study SAE-to-sponsor with SUSAR-only expedited
  and new-info 15-day update; p1132 either-party cannot-exclude-related;
  p1133-p1135 usually-not-expedited list lead-in and first two items);
  attached refs stay body.p1018/p1019 (pkg80), body.p1096 (pkg90),
  body.p1136/p1137 (pkg96) read-only
- real config-field mutation detection for assessment dimension loss,
  recipient omission, AND/OR weakening, 7/8/15 clock swap, post-study all-SAE
  expedited, disagreement strengthen/weaken, cross-package list truncation,
  and non-absolute intensity absoluteization (no self-proving phrase-only
  matching)
- package 94/96/97 prevention of absorption; zero candidates for owned+attached
- official matrix keeps zero rows anchored in owned or attached spans
- immutable source fingerprints and checklist freeze (claims_complete=false)

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

import copy
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
    / "representative_group_package95_sponsor_susar_expedited_reporting_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61cg-package95-sponsor-susar-expedited-reporting-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package95-sponsor-susar-expedited-reporting-boundary"
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
PACKAGE_95_ORDINAL = 95
PACKAGE_95_ID = "pap-d6a9d76caa3d4d5bd85c672e"
PACKAGE_94_ORDINAL = 94
PACKAGE_94_ID = "pap-205e346371315fa509f03126"
PACKAGE_96_ORDINAL = 96
PACKAGE_96_ID = "pap-8dd6a669bdee4e77cc1f0b63"
PACKAGE_97_ORDINAL = 97
PACKAGE_97_ID = "pap-6e961f674f48ee5003dcc014"
PACKAGE_80_ORDINAL = 80
PACKAGE_90_ORDINAL = 90
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_91_ORDINAL = 91
PACKAGE_92_ORDINAL = 92
PACKAGE_93_ORDINAL = 93

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1124, 1136)]
ATTACHED_REFS = [
    "body.p1018",
    "body.p1019",
    "body.p1096",
    "body.p1136",
    "body.p1137",
]
STRUCTURAL_REFS = ["body.p1124"]
SEMANTIC_OWNED_REFS = [ref for ref in OWNED_REFS if ref not in STRUCTURAL_REFS]

PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG80_OWNED_ALL = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG80_NON_ATTACHED = [ref for ref in PKG80_OWNED_ALL if ref not in ATTACHED_REFS]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_OWNED_ALL = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG90_NON_ATTACHED = [ref for ref in PKG90_OWNED_ALL if ref not in ATTACHED_REFS]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG94_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1113, 1124)]
PKG96_SPAN_REFS = ["body.p1136", "body.p1137"]
PKG97_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1138, 1150)]

EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1124": "paragraph",
    "body.p1125": "paragraph",
    "body.p1126": "paragraph",
    "body.p1127": "paragraph",
    "body.p1128": "list_item",
    "body.p1129": "list_item",
    "body.p1130": "paragraph",
    "body.p1131": "paragraph",
    "body.p1132": "paragraph",
    "body.p1133": "paragraph",
    "body.p1134": "list_item",
    "body.p1135": "list_item",
}

OWNED_EXCERPT_BY_REF = {
    "body.p1124": "申办者的报告要求",
    "body.p1125": (
        "申办者收到任何来源的安全性相关信息后，均应当科学全面地分析评估，包括严重性、与试验用药品的相关性、预期性以及评估风险-获益比等。"
    ),
    "body.p1126": (
        "申办者应当将SUSAR快速报告给所有参加临床试验的研究者、临床试验机构及伦理委员会；申办者应当向药品监督管理部门和卫生健康主管部门报告SUSAR。"
    ),
    "body.p1127": (
        "对于研究期间发生的所有与试验用药品肯定相关或可疑的非预期且严重的不良反应，申办者都应按照下述规定时限向国家药品监督管理总局药品审评中心进行快速报告："
    ),
    "body.p1128": (
        "对于致死或危及生命的SUSAR，应在首次获知后7天内（含7天）尽快报告，并在随后的8天内报告、完善随访信息（首次获知当天为第0天）；"
    ),
    "body.p1129": (
        "对于非致死或危及生命的SUSAR，应在首次获知后15天内（含15天）尽快报告。"
    ),
    "body.p1130": (
        "快速报告开始时间为临床试验批准日期或国家药品审评机构默示许可开始日期；结束时间为国内最后一例参与者随访结束日期。"
    ),
    "body.p1131": (
        "在临床试验结束或随访结束后，研究者获知的任何严重不良事件研究者应报告申办者。若属于SUSAR，还应进行快速报告。申办者在首次报告后，应继续跟踪严重不良反应，以随访报告的形式及时报送有关更新的信息或对前次报告的更改信息等，报告时限为获得新信息起15天内。"
    ),
    "body.p1132": (
        "对于临床试验期间发生的所有与试验用药品肯定相关或可疑非预期的严重不良反应，即使申办者和研究者在不良事件与研究药物因果关系判断中不能达成一致时，只要其中任何一方判断不能排除与研究药物相关的，申办者也应向国家药品审评机构进行快速报告。"
    ),
    "body.p1133": "以下情况一般不作为快速报告内容：",
    "body.p1134": "非严重不良事件；",
    "body.p1135": "严重不良事件与试验用药品无关；",
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1018": (
        "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）指临床表现的性质和严重程度超出了试验药物《研究者手册》、已上市药品的说明书或者产品特性摘要等已有资料信息的可疑并且非预期的严重不良反应。"
    ),
    "body.p1019": (
        "非预期不良反应指不良反应的性质、严重程度、后果或频率，不同于试验药物当前相关资料（如《研究者手册》等文件）所描述的预期风险。《研究者手册》作为主要文件提供用以判断某不良反应是否预期或非预期的安全性参考信息。"
    ),
    "body.p1096": (
        "严重不良事件（SAE）与试验用药品的因果关系由研究者和申办者双方共同判断。当双方意见不一致时，对研究者或/和申办者任意一方判断与试验用药品相关的严重不良事件，均属报告范围。"
    ),
    "body.p1136": "严重但属预期的不良反应；",
    "body.p1137": (
        "当以严重不良事件为主要疗效终点时，不建议申请人以个例安全性报告形式向国家药品审评机构报告。"
    ),
}

STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1124": ["申办者的报告要求"],
    "body.p1125": [
        "任何来源",
        "安全性相关信息",
        "科学全面地分析评估",
        "严重性",
        "相关性",
        "预期性",
        "风险-获益比",
    ],
    "body.p1126": [
        "所有参加临床试验的研究者",
        "临床试验机构",
        "伦理委员会",
        "药品监督管理部门",
        "卫生健康主管部门",
    ],
    "body.p1127": [
        "肯定相关或可疑",
        "非预期",
        "严重的不良反应",
        "国家药品监督管理总局药品审评中心",
    ],
    "body.p1128": [
        "致死或危及生命",
        "首次获知后7天内（含7天）",
        "随后的8天内",
        "首次获知当天为第0天",
    ],
    "body.p1129": [
        "非致死或危及生命",
        "首次获知后15天内（含15天）",
    ],
    "body.p1130": [
        "临床试验批准日期",
        "默示许可开始日期",
        "国内最后一例参与者随访结束日期",
    ],
    "body.p1131": [
        "临床试验结束或随访结束后",
        "任何严重不良事件",
        "报告申办者",
        "若属于SUSAR",
        "获得新信息起15天内",
    ],
    "body.p1132": [
        "不能达成一致",
        "任何一方",
        "不能排除与研究药物相关",
    ],
    "body.p1133": ["以下情况", "一般", "不作为快速报告内容"],
    "body.p1134": ["非严重不良事件"],
    "body.p1135": ["严重不良事件", "与试验用药品无关"],
}

# Parent-spec counterexample probes for prompt/checklist scanning only.
# Mutation detection uses real config-field validators below, not these phrases.

HEADING_OBLIGATION_PHRASES = [
    "申办者的报告要求标题本身构成科学评估义务",
    "结构标题独立形成SUSAR接收方集合",
    "标题直接设定7天或15天快速报告时限",
    "结构标题升格为独立控制点或入排门槛",
]

ASSESSMENT_LOSS_PHRASES = [
    "科学评估可省略严重性维度",
    "科学评估可省略相关性维度",
    "科学评估可省略预期性维度",
    "科学评估可省略风险-获益比",
    "任何来源安全信息均直接认定为SUSAR",
]

RECIPIENT_ERROR_PHRASES = [
    "SUSAR仅向研究者快速报告，可省略伦理委员会",
    "漏掉卫生健康主管部门接收方",
    "把所有参加临床试验的修饰语扩到药品监督管理部门",
    "把药品监督管理部门改写成当前机构别名",
]

CONJUNCTION_WEAKEN_PHRASES = [
    "仅非预期且严重即可快速报告，无需相关维度",
    "相关或非预期或严重任一满足即快速报告",
    "可疑等同于已证实相关",
    "把AND合取弱化为单维满足",
]

CLOCK_ERROR_PHRASES = [
    "致死SUSAR改用15天时钟",
    "非致死SUSAR改用7天加8天随访",
    "把7天与8天相加改写为15天统一时限",
    "按工作日口径计算7天或15天",
    "删除含第7天或第0天要求",
]

POST_STUDY_ERROR_PHRASES = [
    "研究结束后获知的全部SAE均须快速报告",
    "研究结束后SAE无需再报告申办者",
    "更新更改15天沿用首次获知时钟",
]

DISAGREEMENT_ERROR_PHRASES = [
    "必须双方一致确认相关才快速报告",
    "必须最终确认相关才快速报告",
    "任一方不能排除相关不足以触发快速报告",
]

LIST_TRUNCATE_OR_ABSOLUTE_PHRASES = [
    "只保留非严重不良事件与无关SAE两项，截断第96包后项",
    "一般不作为快速报告内容改成绝对禁止报告",
    "不建议改成一律不得以个例安全性报告",
    "提前夺取第96包p1136/p1137所有权",
]

CANDIDATE_UPGRADE_PHRASES = [
    "未完成SUSAR快速报告培训的受试者筛选失败",
    "未确认7天时钟视为基线不通过",
    "入组前必须完成申办者科学评估流程否则不得入组",
    "发布SUSAR快速报告控制点",
    "筛选期必做：接收方集合核对",
    "基线期必做：通常不快速报告列表签署作为入组条件",
]

ALL_DETERMINISTIC_PHRASES = (
    HEADING_OBLIGATION_PHRASES
    + ASSESSMENT_LOSS_PHRASES
    + RECIPIENT_ERROR_PHRASES
    + CONJUNCTION_WEAKEN_PHRASES
    + CLOCK_ERROR_PHRASES
    + POST_STUDY_ERROR_PHRASES
    + DISAGREEMENT_ERROR_PHRASES
    + LIST_TRUNCATE_OR_ABSOLUTE_PHRASES
    + CANDIDATE_UPGRADE_PHRASES
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


def _interpretation_blob(entry: dict) -> str:
    return " ".join([entry.get("exception_rule", ""), *entry.get("preserve_keywords", [])])


def _qc_blob(config: dict, ref: str) -> str:
    return " ".join(config["clinical_qc_checks_by_source_ref"].get(ref) or [])


def _package95_contract_issues(config: dict) -> set[str]:
    """Validate the local Package 95 specification via real config fields."""
    issues: set[str] = set()
    semantics = config["exception_semantics_by_source_ref"]

    for ref in SEMANTIC_OWNED_REFS:
        if semantics[ref]["base_rule"] != OWNED_EXCERPT_BY_REF[ref]:
            issues.add(f"{ref}:SOURCE_TEXT")

    p1125_entry = semantics["body.p1125"]
    p1125 = p1125_entry["exception_rule"]
    if not all(
        fragment in p1125
        for fragment in (
            "任何来源",
            "严重性",
            "相关性",
            "预期性",
            "风险-获益比",
            "不等于任何信息均为SUSAR",
        )
    ):
        issues.add("body.p1125:ASSESSMENT_DIMS")

    p1126_entry = semantics["body.p1126"]
    p1126 = p1126_entry["exception_rule"] + " " + " ".join(p1126_entry["preserve_keywords"])
    recipients = (
        "所有参加临床试验的研究者",
        "临床试验机构",
        "伦理委员会",
        "药品监督管理部门",
        "卫生健康主管部门",
    )
    if not all(fragment in p1126 for fragment in recipients):
        issues.add("body.p1126:RECIPIENTS")
    if not all(fragment in p1126_entry["exception_rule"] for fragment in recipients):
        issues.add("body.p1126:RECIPIENTS")
    if "所有参加临床试验的" not in p1126 or "监管部门" not in p1126_entry["forbidden_inversion"]:
        issues.add("body.p1126:RECIPIENTS")
    recipient_narrative = " ".join(
        [config["batching"]["reason"], _qc_blob(config, "body.p1126")]
    )
    if not all(fragment in recipient_narrative for fragment in recipients):
        issues.add("body.p1126:RECIPIENT_NARRATIVE")

    p1127_entry = semantics["body.p1127"]
    p1127 = p1127_entry["exception_rule"] + " " + p1127_entry["forbidden_inversion"]
    if not all(
        fragment in p1127
        for fragment in (
            "肯定相关 OR 可疑",
            "非预期",
            "严重",
            "AND",
            "不得把AND弱化",
            "可疑",
        )
    ):
        issues.add("body.p1127:CONJUNCTION")
    if "已证实相关" not in p1127:
        issues.add("body.p1127:CONJUNCTION")
    if "国家药品监督管理总局药品审评中心" not in p1127_entry["preserve_keywords"]:
        issues.add("body.p1127:AGENCY")
    if "国家药品监督管理总局药品审评中心" not in p1127_entry["forbidden_inversion"]:
        issues.add("body.p1127:AGENCY")

    p1128_entry = semantics["body.p1128"]
    p1128 = p1128_entry["exception_rule"]
    if not all(
        fragment in p1128
        for fragment in (
            "致死或危及生命",
            "7天内（含7天）",
            "8天内",
            "第0天",
        )
    ):
        issues.add("body.p1128:CLOCK_7_8")
    if "不得与非致死15天时钟互换" not in p1128_entry["forbidden_inversion"]:
        issues.add("body.p1128:CLOCK_7_8")

    p1129_entry = semantics["body.p1129"]
    p1129 = p1129_entry["exception_rule"]
    if not all(
        fragment in p1129
        for fragment in (
            "非（致死或危及生命）的SUSAR",
            "15天内（含15天）",
        )
    ):
        issues.add("body.p1129:CLOCK_15")
    if "不得与致死7/8天时钟互换" not in p1129_entry["forbidden_inversion"]:
        issues.add("body.p1129:CLOCK_15")
    if "不得解析为（非致死）OR（危及生命）" not in p1129_entry["exception_rule"]:
        issues.add("body.p1129:GROUPING")

    # Real clock-separation check: neither clock entry may absorb the other.
    if "15天内（含15天）" in p1128 and "7天内（含7天）" not in p1128:
        issues.add("CLOCK_SWAP")
    if "7天内（含7天）" in p1129 and "15天内（含15天）" not in p1129:
        issues.add("CLOCK_SWAP")

    p1130_entry = semantics["body.p1130"]
    p1130 = p1130_entry["exception_rule"] + " " + p1130_entry["forbidden_inversion"]
    if not all(
        fragment in p1130
        for fragment in (
            "临床试验批准日期",
            "默示许可开始日期",
            "国内最后一例参与者随访结束日期",
            "方案签署",
            "首例入组",
            "数据库锁定",
        )
    ):
        issues.add("body.p1130:WINDOW")

    p1131_entry = semantics["body.p1131"]
    p1131 = p1131_entry["exception_rule"]
    if not all(
        fragment in p1131
        for fragment in (
            "报告申办者",
            "属于SUSAR",
            "获得新信息起15天内",
        )
    ):
        issues.add("body.p1131:POST_STUDY")
    if "不得把研究结束后全部SAE改成快速报告" not in p1131_entry["forbidden_inversion"]:
        issues.add("body.p1131:POST_STUDY")

    p1132_entry = semantics["body.p1132"]
    p1132 = p1132_entry["exception_rule"]
    if not all(
        fragment in p1132
        for fragment in (
            "任一方",
            "不能排除相关",
            "不得要求双方一致",
            "最终确认相关",
        )
    ):
        issues.add("body.p1132:DISAGREEMENT")
    if not all(
        fragment in p1132
        for fragment in (
            "(肯定相关 OR 可疑) AND 非预期 AND 严重",
            "国家药品审评机构",
        )
    ):
        issues.add("body.p1132:OBJECT")
    p1132_forbid = p1132_entry["forbidden_inversion"]
    if not all(
        fragment in p1132_forbid
        for fragment in (
            "不得把任意因果关系分歧直接升级为快速报告",
            "不得删除(肯定相关 OR 可疑) AND 非预期 AND 严重的对象约束",
            "不得要求双方一致才报告",
            "不得改成最终确认相关才报告",
        )
    ):
        issues.add("body.p1132:FORBIDDEN_INVERSION")

    p1133_entry = semantics["body.p1133"]
    p1134_entry = semantics["body.p1134"]
    p1135_entry = semantics["body.p1135"]
    p1133 = _interpretation_blob(p1133_entry) + " " + p1133_entry["forbidden_inversion"]
    p1134 = _interpretation_blob(p1134_entry) + " " + p1134_entry["forbidden_inversion"]
    p1135 = _interpretation_blob(p1135_entry) + " " + p1135_entry["forbidden_inversion"]
    if "一般" not in p1133_entry["exception_rule"] or any(
        phrase in p1133_entry["exception_rule"]
        for phrase in ("以下情况绝对禁止", "绝对禁止作为", "一律不得快速报告")
    ):
        issues.add("body.p1133:INTENSITY")
    for ref, entry in (("body.p1134", p1134_entry), ("body.p1135", p1135_entry)):
        if "一般" not in entry["exception_rule"] or any(
            phrase in entry["exception_rule"]
            for phrase in ("以下情况绝对禁止", "绝对禁止作为", "一律不得快速报告")
        ):
            issues.add(f"{ref}:INTENSITY")
    qc_1136 = _qc_blob(config, "body.p1136")
    qc_1137 = _qc_blob(config, "body.p1137")
    list_blob = " ".join(
        [
            p1133,
            p1134,
            p1135,
            qc_1136,
            qc_1137,
            " ".join(config.get("notes") or []),
            config["later_package_boundary"].get("note", ""),
        ]
    )
    if not all(
        fragment in list_blob
        for fragment in (
            "非严重不良事件",
            "与试验用药品无关",
            "p1136",
            "p1137",
            "不建议",
            "申请人",
            "个例安全性报告形式",
            "国家药品审评机构",
        )
    ):
        issues.add("CROSS_PACKAGE_LIST")
    if not all(
        fragment in list_blob
        for fragment in (
            "绝对禁止",
            "不得截断",
        )
    ):
        issues.add("INTENSITY_NON_ABSOLUTE")
    if set(config.get("attached_source_refs") or []) & set(PKG96_SPAN_REFS) != set(
        PKG96_SPAN_REFS
    ):
        issues.add("CROSS_PACKAGE_LIST")

    owned_and_attached = set(config["owned_source_refs"] + config["attached_source_refs"])
    if owned_and_attached & set(PKG94_SPAN_REFS):
        issues.add("PACKAGE94_OWNERSHIP")
    if set(config["owned_source_refs"]) & set(PKG96_SPAN_REFS):
        issues.add("PACKAGE96_OWNERSHIP")
    if owned_and_attached & set(PKG97_SPAN_REFS):
        issues.add("PACKAGE97_OWNERSHIP")
    if config.get("required_candidate_source_refs"):
        issues.add("REQUIRED_CANDIDATE_NONEMPTY")
    return issues


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_95_ORDINAL
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
            return str(block.get("text") or "")
    raise AssertionError(f"block {ref} missing from structure blob")


@pytest.fixture(scope="module")
def config() -> dict:
    from slice59n_representative_group_control_replay import _load_config

    return _load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def plan() -> dict:
    return _load_json(PLAN_PATH)


@pytest.fixture(scope="module")
def matrix() -> dict:
    return _load_json(MATRIX_PATH)


@pytest.fixture(scope="module")
def procedure_catalog() -> dict:
    return _load_json(CATALOG_DIR / "required_procedures.json")


@pytest.fixture(scope="module")
def structure_blob() -> list[dict]:
    return _load_json(STRUCTURE_BLOB_PATH)


def test_config_contract(config: dict) -> None:
    assert (
        config["schema_version"]
        == "phase5/representative-group-control-replay-config/v1"
    )
    assert (
        config["group_id"]
        == "d001-ii-package95-sponsor-susar-expedited-reporting-boundary"
    )
    assert config["task_id"] == "phase5-slice61cg-20260830"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert len(config["owned_source_refs"]) == 12
    assert len(config["attached_source_refs"]) == 5
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(
        OWNED_REFS + ATTACHED_REFS
    )
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL_REFS

    dispositions = config["expected_disposition_by_source_ref"]
    assert set(dispositions) == set(SEMANTIC_OWNED_REFS)
    for ref in SEMANTIC_OWNED_REFS:
        assert dispositions[ref] == "post_treatment_execution", ref
    for ref in STRUCTURAL_REFS:
        assert ref not in dispositions

    for ref in OWNED_REFS + ATTACHED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {
            "筛选必做",
            "基线必做",
            "证据缺口",
            "不得入组",
            "排除标准",
            "入排不通过",
        } <= set(markers), ref
        assert ref in config["clinical_qc_checks_by_source_ref"]
        assert len(config["clinical_qc_checks_by_source_ref"][ref]) >= 2

    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert entry["preserve_keywords"]
        assert entry["forbidden_inversion"]


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg95 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_95_ORDINAL
    )
    owned_95 = {u["source_ref"] for u in pkg95["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached == ATTACHED_REFS
    assert not (set(attached) & owned_95)


def test_attached_refs_ownership_documented(plan: dict) -> None:
    owners: dict[str, list[int]] = {}
    for pkg in plan["packages"]:
        for unit in pkg["owned_units"]:
            owners.setdefault(unit["source_ref"], []).append(pkg["package_ordinal"])
    assert owners.get("body.p1018") == [PACKAGE_80_ORDINAL]
    assert owners.get("body.p1019") == [PACKAGE_80_ORDINAL]
    assert owners.get("body.p1096") == [PACKAGE_90_ORDINAL]
    assert owners.get("body.p1136") == [PACKAGE_96_ORDINAL]
    assert owners.get("body.p1137") == [PACKAGE_96_ORDINAL]
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_95_ORDINAL], ref


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    assert set(PKG78_SPAN_REFS) <= counts[PACKAGE_78_ORDINAL] and len(
        counts[PACKAGE_78_ORDINAL]
    ) == 12
    assert set(PKG79_SPAN_REFS) <= counts[PACKAGE_79_ORDINAL] and len(
        counts[PACKAGE_79_ORDINAL]
    ) == 8
    assert set(PKG80_OWNED_ALL) <= counts[PACKAGE_80_ORDINAL] and len(
        counts[PACKAGE_80_ORDINAL]
    ) == 12
    assert set(PKG82_SPAN_REFS) <= counts[PACKAGE_82_ORDINAL] and len(
        counts[PACKAGE_82_ORDINAL]
    ) == 5
    assert set(PKG87_SPAN_REFS) <= counts[PACKAGE_87_ORDINAL] and len(
        counts[PACKAGE_87_ORDINAL]
    ) == 10
    assert set(PKG88_SPAN_REFS) <= counts[PACKAGE_88_ORDINAL] and len(
        counts[PACKAGE_88_ORDINAL]
    ) == 3
    assert set(PKG89_SPAN_REFS) <= counts[PACKAGE_89_ORDINAL] and len(
        counts[PACKAGE_89_ORDINAL]
    ) == 6
    assert set(PKG90_OWNED_ALL) <= counts[PACKAGE_90_ORDINAL] and len(
        counts[PACKAGE_90_ORDINAL]
    ) == 11
    assert set(PKG91_SPAN_REFS) <= counts[PACKAGE_91_ORDINAL] and len(
        counts[PACKAGE_91_ORDINAL]
    ) == 8
    assert set(PKG92_SPAN_REFS) <= counts[PACKAGE_92_ORDINAL] and len(
        counts[PACKAGE_92_ORDINAL]
    ) == 4
    assert set(PKG93_SPAN_REFS) <= counts[PACKAGE_93_ORDINAL] and len(
        counts[PACKAGE_93_ORDINAL]
    ) == 11
    assert set(PKG94_SPAN_REFS) <= counts[PACKAGE_94_ORDINAL] and len(
        counts[PACKAGE_94_ORDINAL]
    ) == 11
    assert set(OWNED_REFS) <= counts[PACKAGE_95_ORDINAL] and len(
        counts[PACKAGE_95_ORDINAL]
    ) == 12
    assert set(PKG96_SPAN_REFS) <= counts[PACKAGE_96_ORDINAL] and len(
        counts[PACKAGE_96_ORDINAL]
    ) == 2
    assert set(PKG97_SPAN_REFS) <= counts[PACKAGE_97_ORDINAL] and len(
        counts[PACKAGE_97_ORDINAL]
    ) == 12


def test_owned_refs_match_frozen_package_95(config: dict, plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_95_ORDINAL
    )
    assert pkg["package_id"] == PACKAGE_95_ID
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    assert excerpts == OWNED_EXCERPT_BY_REF


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    assert excerpts == ATTACHED_EXCERPT_BY_REF


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_95_ORDINAL
    )
    for unit in pkg["owned_units"]:
        ref = unit["source_ref"]
        assert unit.get("unit_kind") == EXPECTED_UNIT_KIND_BY_REF[ref], ref


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        assert excerpt == _structure_blob_text(structure_blob, ref)


def test_structural_heading_never_converted_to_obligations(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]
    for ref in STRUCTURAL_REFS:
        text = (
            semantics[ref]["exception_rule"]
            + " "
            + semantics[ref]["forbidden_inversion"]
        )
        assert "仅作结构" in text or "仅作结构" in semantics[ref]["exception_rule"]
        assert "不得" in semantics[ref]["forbidden_inversion"]


def test_specification_probe_catalog_is_unique_and_source_clean() -> None:
    assert ALL_DETERMINISTIC_PHRASES
    assert len(ALL_DETERMINISTIC_PHRASES) == len(set(ALL_DETERMINISTIC_PHRASES))
    for excerpt in OWNED_EXCERPT_BY_REF.values():
        assert _deterministic_hits(excerpt) == []
    for excerpt in ATTACHED_EXCERPT_BY_REF.values():
        assert _deterministic_hits(excerpt) == []


def test_p1125_assessment_dimensions_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1125"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1125")
    assert missing == []
    blob = _semantic_blob(semantics)
    assert "不等于任何信息均为SUSAR" in blob
    assert "严重性" in blob and "相关性" in blob and "预期性" in blob
    assert "风险-获益比" in blob


def test_assessment_dimension_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1125"]
    semantic["exception_rule"] = "任何来源安全信息均可直接按SUSAR处理；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["任何来源", "安全性相关信息"]
    assert "body.p1125:ASSESSMENT_DIMS" in _package95_contract_issues(mutated)


def test_p1126_recipients_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1126"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1126")
    assert missing == []
    inversion = semantics["forbidden_inversion"]
    assert "不得漏项或互相替代接收方" in inversion
    assert "监管部门" in inversion
    narrative = " ".join([config["batching"]["reason"], _qc_blob(config, "body.p1126")])
    assert all(
        recipient in narrative
        for recipient in (
            "所有参加临床试验的研究者",
            "临床试验机构",
            "伦理委员会",
            "药品监督管理部门",
            "卫生健康主管部门",
        )
    )


def test_recipient_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1126"]
    semantic["exception_rule"] = "SUSAR仅向研究者快速报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["SUSAR", "快速报告", "研究者"]
    assert "body.p1126:RECIPIENTS" in _package95_contract_issues(mutated)


def test_recipient_exception_only_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1126"]
    semantic["exception_rule"] = "SUSAR仅向研究者快速报告；零候选"
    assert "body.p1126:RECIPIENTS" in _package95_contract_issues(mutated)


def test_recipient_narrative_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["batching"]["reason"] = "SUSAR向研究者、机构和药监报告"
    mutated["clinical_qc_checks_by_source_ref"]["body.p1126"] = [
        "SUSAR向研究者、机构和药监报告",
        "保持治疗后执行职责，零候选",
    ]
    issues = _package95_contract_issues(mutated)
    assert "body.p1126:RECIPIENT_NARRATIVE" in issues


def test_p1127_conjunction_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1127"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1127")
    assert missing == []
    blob = _semantic_blob(semantics)
    assert "(肯定相关 OR 可疑) AND 非预期 AND 严重" in blob
    assert "不得把AND弱化" in blob
    assert "已证实相关" in blob


def test_conjunction_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1127"]
    semantic["exception_rule"] = "相关或非预期或严重任一满足即可快速报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["快速报告", "严重的不良反应"]
    assert "body.p1127:CONJUNCTION" in _package95_contract_issues(mutated)


def test_p1128_p1129_clocks_preserved(config: dict) -> None:
    p1128 = config["exception_semantics_by_source_ref"]["body.p1128"]
    p1129 = config["exception_semantics_by_source_ref"]["body.p1129"]
    assert _missing_structural_fragments(p1128["base_rule"], "body.p1128") == []
    assert _missing_structural_fragments(p1129["base_rule"], "body.p1129") == []
    assert "不得与非致死15天时钟互换" in p1128["forbidden_inversion"]
    assert "不得与致死7/8天时钟互换" in p1129["forbidden_inversion"]
    assert "工作日" in p1128["forbidden_inversion"]
    assert "工作日" in p1129["forbidden_inversion"]
    assert "非（致死或危及生命）的SUSAR" in _semantic_blob(p1129)
    assert "不得解析为（非致死）OR（危及生命）" in _semantic_blob(p1129)


def test_clock_contract_mutations_are_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1128"]
    semantic["exception_rule"] = "致死SUSAR首次获知后15天内尽快报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["致死或危及生命", "SUSAR"]
    assert "body.p1128:CLOCK_7_8" in _package95_contract_issues(mutated)

    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1129"]
    semantic["exception_rule"] = "非致死SUSAR首次获知后7天内并随后8天随访；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["非致死或危及生命", "SUSAR"]
    assert "body.p1129:CLOCK_15" in _package95_contract_issues(mutated)


def test_p1128_exception_only_clock_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1128"]
    semantic["exception_rule"] = "致死或危及生命SUSAR首次获知后15天内报告"
    assert "body.p1128:CLOCK_7_8" in _package95_contract_issues(mutated)


def test_p1129_grouping_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1129"]
    semantic["exception_rule"] = (
        "（非致死）OR（危及生命）的SUSAR首次获知后15天内（含15天）报告"
    )
    semantic["forbidden_inversion"] = (
        "不得与致死7/8天时钟互换；不得改成工作日；不得删除含第15天"
    )
    semantic["preserve_keywords"] = [
        "SUSAR",
        "首次获知后15天内（含15天）",
        "尽快报告",
    ]
    issues = _package95_contract_issues(mutated)
    assert "body.p1129:GROUPING" in issues


def test_p1130_reporting_window_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1130"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1130") == []
    blob = _semantic_blob(semantics)
    assert "两个可能起点" in blob or (
        "临床试验批准日期" in blob and "默示许可开始日期" in blob
    )
    assert "方案签署" in blob and "首例入组" in blob and "数据库锁定" in blob


def test_reporting_window_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1130"]
    semantic["exception_rule"] = "快速报告起于方案签署，止于数据库锁定；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["快速报告"]
    assert "body.p1130:WINDOW" in _package95_contract_issues(mutated)


def test_p1131_post_study_split_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1131"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1131") == []
    blob = _semantic_blob(semantics)
    assert "若属于SUSAR" in blob
    assert "获得新信息起15天内" in blob
    assert "不得把研究结束后全部SAE改成快速报告" in blob


def test_post_study_all_sae_expedited_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1131"]
    semantic["exception_rule"] = "研究结束后获知的全部SAE均快速报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["任何严重不良事件", "快速报告"]
    assert "body.p1131:POST_STUDY" in _package95_contract_issues(mutated)


def test_post_study_exception_only_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1131"]
    semantic["exception_rule"] = "研究结束后获知的全部SAE均快速报告"
    assert "body.p1131:POST_STUDY" in _package95_contract_issues(mutated)


def test_p1132_disagreement_rule_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1132"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1132") == []
    blob = _semantic_blob(semantics)
    assert "任一方" in blob or "任何一方" in blob
    assert "不能排除相关" in blob
    assert "不得要求双方一致" in blob
    assert "最终确认相关" in blob
    assert "(肯定相关 OR 可疑) AND 非预期 AND 严重" in blob
    assert "不得把任意因果关系分歧直接升级为快速报告" in blob
    assert "国家药品审评机构" in blob


def test_disagreement_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1132"]
    semantic["exception_rule"] = "必须双方一致且最终确认相关才快速报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["快速报告", "国家药品审评机构"]
    assert "body.p1132:DISAGREEMENT" in _package95_contract_issues(mutated)


def test_p1132_object_conjunction_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1132"]
    semantic["exception_rule"] = (
        "因果关系存在分歧时，任一方判断不能排除相关即向国家药品审评机构快速报告"
    )
    semantic["forbidden_inversion"] = (
        "不得要求双方一致才报告；不得改成最终确认相关才报告"
    )
    semantic["preserve_keywords"] = [
        "不能达成一致",
        "任何一方",
        "不能排除与研究药物相关",
        "快速报告",
        "国家药品审评机构",
    ]
    issues = _package95_contract_issues(mutated)
    assert "body.p1132:OBJECT" in issues


def test_p1132_object_exception_only_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1132"]
    semantic["exception_rule"] = (
        "因果关系存在分歧时，任一方判断不能排除相关即向国家药品审评机构快速报告"
    )
    assert "body.p1132:OBJECT" in _package95_contract_issues(mutated)


def test_p1132_disagreement_exception_only_contradiction_is_detected(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1132"]
    semantic["exception_rule"] = "必须双方一致且最终确认相关才快速报告；零候选"
    assert "body.p1132:DISAGREEMENT" in _package95_contract_issues(mutated)


def test_cross_package_usually_not_expedited_list_preserved(config: dict) -> None:
    assert config["attached_source_refs"][-2:] == PKG96_SPAN_REFS
    p1133 = config["exception_semantics_by_source_ref"]["body.p1133"]
    assert "一般" in " ".join(p1133["preserve_keywords"])
    assert "绝对禁止" in p1133["forbidden_inversion"]
    assert "截断" in p1133["forbidden_inversion"]
    qc_1136 = _qc_blob(config, "body.p1136")
    qc_1137 = _qc_blob(config, "body.p1137")
    assert "严重但属预期" in qc_1136
    assert "不建议" in qc_1137
    assert "申请人" in qc_1137
    assert "个例安全性报告形式" in qc_1137
    assert "国家药品审评机构" in qc_1137
    assert "绝对禁止" in qc_1136 and "绝对禁止" in qc_1137
    note = config["later_package_boundary"]["note"]
    assert "第96包" in note
    assert "不得提前夺取第96包所有权" in note or "不得夺取第96包所有权" in note


def test_cross_package_list_truncation_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = [
        ref for ref in mutated["attached_source_refs"] if ref not in PKG96_SPAN_REFS
    ]
    for ref in PKG96_SPAN_REFS:
        mutated["clinical_qc_checks_by_source_ref"].pop(ref, None)
    mutated["notes"] = ["截断跨包列表，仅保留本包前两项"]
    mutated["later_package_boundary"]["note"] = "不提及第96包连续后项"
    p1133 = mutated["exception_semantics_by_source_ref"]["body.p1133"]
    p1133["exception_rule"] = "仅本包两项；零候选"
    p1133["forbidden_inversion"] = "不得升格为入排控制点"
    p1133["preserve_keywords"] = ["以下情况"]
    issues = _package95_contract_issues(mutated)
    assert "CROSS_PACKAGE_LIST" in issues or "body.p1133:INTENSITY" in issues


def test_cross_package_p1137_paraphrase_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["clinical_qc_checks_by_source_ref"]["body.p1137"] = [
        "第96包拥有：主要疗效终点时不建议报告，只读",
        "保留非绝对强度",
    ]
    assert "CROSS_PACKAGE_LIST" in _package95_contract_issues(mutated)


def test_non_absolute_intensity_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    p1133 = mutated["exception_semantics_by_source_ref"]["body.p1133"]
    p1133["exception_rule"] = "以下情况绝对禁止作为快速报告内容；零候选"
    p1133["forbidden_inversion"] = "不得升格为入排控制点"
    p1133["preserve_keywords"] = ["以下情况", "绝对禁止", "不作为快速报告内容"]
    for ref in ("body.p1134", "body.p1135"):
        entry = mutated["exception_semantics_by_source_ref"][ref]
        entry["exception_rule"] = "一律不得快速报告；零候选"
        entry["forbidden_inversion"] = "不得升格为入排控制点"
    for ref in PKG96_SPAN_REFS:
        mutated["clinical_qc_checks_by_source_ref"][ref] = [
            "第96包拥有列表后项，只读",
            "强化为绝对禁止报告",
        ]
    mutated["notes"] = ["列表强度改为绝对禁止"]
    mutated["later_package_boundary"]["note"] = "跨包列表后项绝对禁止，夺取第96包"
    issues = _package95_contract_issues(mutated)
    assert (
        "body.p1133:INTENSITY" in issues
        or "INTENSITY_NON_ABSOLUTE" in issues
        or "CROSS_PACKAGE_LIST" in issues
    )


def test_intensity_exception_only_contradiction_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1133"]
    semantic["exception_rule"] = "以下情况绝对禁止作为快速报告内容"
    assert "body.p1133:INTENSITY" in _package95_contract_issues(mutated)


def test_required_candidate_upgrade_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["required_candidate_source_refs"] = ["body.p1127"]
    assert "REQUIRED_CANDIDATE_NONEMPTY" in _package95_contract_issues(mutated)


def test_package94_content_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG94_SPAN_REFS:
        assert ref not in owned
        assert ref not in attached
    boundary = config["later_package_boundary"]["expected_owners_by_span"]
    for ref in PKG94_SPAN_REFS:
        assert boundary[ref] == PACKAGE_94_ORDINAL


def test_package96_ownership_not_taken(config: dict) -> None:
    assert set(config["owned_source_refs"]) & set(PKG96_SPAN_REFS) == set()
    assert set(PKG96_SPAN_REFS) <= set(config["attached_source_refs"])
    boundary = config["later_package_boundary"]["expected_owners_by_span"]
    for ref in PKG96_SPAN_REFS:
        assert boundary[ref] == PACKAGE_96_ORDINAL


def test_package96_ownership_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"].append("body.p1136")
    assert "PACKAGE96_OWNERSHIP" in _package95_contract_issues(mutated)


def test_package97_content_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG97_SPAN_REFS:
        assert ref not in owned
        assert ref not in attached
    boundary = config["later_package_boundary"]["expected_owners_by_span"]
    for ref in PKG97_SPAN_REFS:
        assert boundary[ref] == PACKAGE_97_ORDINAL


def test_package95_contract_is_currently_closed(config: dict) -> None:
    assert _package95_contract_issues(config) == set()


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
        + PKG90_NON_ATTACHED
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG94_SPAN_REFS
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
    assert "第95包拥有申办者科学评估与SUSAR快速报告" in note
    assert "第94包" in note
    assert "第96包" in note
    assert "第97包" in note
    assert "零候选" in note


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(ATTACHED_REFS)
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"

    assert by_ref["body.p1124"].excerpt == OWNED_EXCERPT_BY_REF["body.p1124"]
    assert "任何来源的安全性相关信息" in by_ref["body.p1125"].excerpt
    assert "风险-获益比" in by_ref["body.p1125"].excerpt
    assert "药品监督管理部门和卫生健康主管部门" in by_ref["body.p1126"].excerpt
    assert "肯定相关或可疑的非预期且严重" in by_ref["body.p1127"].excerpt
    assert "首次获知后7天内（含7天）" in by_ref["body.p1128"].excerpt
    assert "首次获知当天为第0天" in by_ref["body.p1128"].excerpt
    assert "首次获知后15天内（含15天）" in by_ref["body.p1129"].excerpt
    assert "默示许可开始日期" in by_ref["body.p1130"].excerpt
    assert "若属于SUSAR，还应进行快速报告" in by_ref["body.p1131"].excerpt
    assert "获得新信息起15天内" in by_ref["body.p1131"].excerpt
    assert "任何一方判断不能排除与研究药物相关" in by_ref["body.p1132"].excerpt
    assert by_ref["body.p1133"].excerpt == OWNED_EXCERPT_BY_REF["body.p1133"]
    assert "不建议申请人以个例安全性报告形式" in by_ref["body.p1137"].excerpt


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
        + PKG90_NON_ATTACHED
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG94_SPAN_REFS
        + PKG97_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 5
    assert summary["unit_count"] == 17
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
                    "title": "筛选时核对SUSAR快速报告时限，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    paraphrased_candidates = {
        "body.p1124": "申办者报告要求章节作为入组前药物警戒培训门槛",
        "body.p1125": "科学评估维度核对作为机构启动考核指标",
        "body.p1126": "SUSAR接收方集合作为中心启动检查项",
        "body.p1127": "合取对象判定流程作为受试者随访执行前置条件",
        "body.p1128": "7天时钟签署作为伦理委员会资格条件",
        "body.p1131": "研究结束后报告分流作为合同签署前置要求",
        "body.p1133": "通常不快速报告列表确认作为医学监查准入准则",
        "body.p1018": "SUSAR定义复述作为研究者资质审核条件",
        "body.p1136": "跨包列表后项签署作为中心质量评分项",
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
    for ref in OWNED_REFS:
        hits = _deterministic_hits(excerpts[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"
    attached = _attached_excerpt_by_ref(plan)
    for ref in ATTACHED_REFS:
        hits = _deterministic_hits(attached[ref])
        assert hits == [], f"{ref} 只读附加来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    counterexamples_by_ref = {
        "body.p1124": [
            "筛选必做：申办者的报告要求核对",
            "基线必做：申办者报告要求章节确认",
            "申办者报告要求未明确作为证据缺口，不得入组",
            "发布控制点：申办者的报告要求",
        ],
        "body.p1125": [
            "筛选期必做：科学评估维度培训",
            "基线必做：风险-获益比评估承诺",
            "评估维度缺失视为证据缺口，判定入排不通过",
            "转移所有权至第95包发布控制点",
        ],
        "body.p1126": [
            "筛选必做：SUSAR接收方集合签署",
            "基线期必做：伦理委员会报送核对",
            "接收方漏项视为入排不通过",
            "SUSAR接收方流程发布控制点",
        ],
        "body.p1127": [
            "筛选必做：合取对象判定确认",
            "基线必做：肯定相关或可疑核对",
            "合取弱化视为证据缺口，不得入组",
        ],
        "body.p1128": [
            "筛选必做：7天时钟培训",
            "基线必做：第0天定义签署",
            "7天时限缺失视为入排不通过",
        ],
        "body.p1131": [
            "筛选必做：研究结束后报告分流告知",
            "基线必做：新信息15天更新确认",
            "研究结束后分流未签署视为入排不通过",
        ],
        "body.p1133": [
            "筛选期必做：通常不快速报告列表确认",
            "基线必做：一般不作为快速报告内容签署",
            "列表截断视为证据缺口，不符合入选标准",
        ],
        "body.p1018": [
            "筛选必做：SUSAR定义复述",
            "基线必做：三维关系培训",
            "SUSAR定义缺失视为入排不通过",
        ],
        "body.p1137": [
            "筛选必做：不建议个例安全性报告确认",
            "基线期必做：主要疗效终点SAE报告边界签署",
            "跨包列表后项缺失视为证据缺口，不得入组",
        ],
    }
    for ref, counterexamples in counterexamples_by_ref.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        for text in counterexamples:
            hits = _forbidden_marker_hits(text, markers)
            assert hits, f"{ref} 升格反例未被 forbidden_markers 拦截: {text}"


def test_prompt_excludes_neighbor_package94_and_97_content() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")

    package94_fragments = [
        "应提供的安全信息资料及要求",
        "研究者将负责确保所有关于事件和相关随访的正确信息均被记录在可溯源的参与者病历及对应的事件报告表上。",
        "研究期间发生的所有SAE，无论其与试验药物是否相关",
        "本研究的报告联系方式见附录7。",
    ]
    package97_fragments = [
        "不良事件的随访",
    ]
    for fragment in package94_fragments + package97_fragments:
        assert fragment not in prompt_text, fragment


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


def test_matrix_has_no_rows_anchored_in_package95_or_attached(
    matrix: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for rule in matrix.get("official_rules") or []:
        anchors = set(rule.get("source_refs") or []) | set(
            rule.get("frozen_structure_unit_ids") or []
        )
        assert not (anchors & forbidden), rule


def test_matrix_has_no_ae_teae_sae_susar_rows(matrix: dict) -> None:
    banned_tokens = ("不良事件", "TEAE", "SAE", "SUSAR", "快速报告")
    for rule in matrix.get("official_rules") or []:
        blob = json.dumps(rule, ensure_ascii=False)
        assert not any(token in blob for token in banned_tokens), rule


def test_no_official_rule_anchors_package95_owned_or_attached_spans(
    matrix: dict,
) -> None:
    assert matrix.get("official_rules") in ([], None) or all(
        not (
            set(rule.get("source_refs") or [])
            & set(OWNED_REFS + ATTACHED_REFS)
        )
        for rule in matrix.get("official_rules") or []
    )


def test_procedure_catalog_has_no_susar_or_expedited_node(
    procedure_catalog: dict,
) -> None:
    banned = ("SUSAR", "快速报告", "申办者的报告要求", "7天内", "15天内")
    for item in procedure_catalog.get("items") or []:
        blob = json.dumps(item, ensure_ascii=False)
        assert not any(token in blob for token in banned), item


def test_no_procedure_node_sourced_from_package95_or_attached(
    procedure_catalog: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for item in procedure_catalog.get("items") or []:
        refs = set(item.get("source_refs") or [])
        assert not (refs & forbidden), item


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
    rationale = config["phase_applicability"]["rationale"]
    assert "不构成入排门槛" in rationale
    assert "全部禁止发射候选" in rationale


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(COVERAGE_PATH)
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_95_ID in text
    assert PACKAGE_94_ID in text
    assert PACKAGE_96_ID in text
    assert "body.p1124" in text
    assert "body.p1135" in text
    assert "body.p1018" in text
    assert "body.p1137" in text
    assert "claims_complete=false" in text
    assert "合取" in text
    assert "7" in text and "15" in text
    assert "通常" in text or "一般" in text
    assert "不建议" in text
    assert "第96包" in text
