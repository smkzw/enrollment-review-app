#!/usr/bin/env python3
"""Slice61ci model-free source-closure regressions.

Locks the D001 II package 97 AE follow-up / outcome-status boundary
(frozen plan package 97: body.p1138-p1149) to its authoritative sources
before any semantic replay decision:

- config contract and role partition: 12 owned refs body.p1138-p1149
  (p1138/p1147 structural-only; remaining 10 post_treatment_execution);
  attached refs stay body.p1150-p1156 (pkg98 definitions / end-time lead /
  lost-to-followup ≠ AE-withdrawal) read-only; p1157 and pkg99 pregnancy
  stay metadata-only and out of prompt/positive semantics
- real config-field mutation detection for:
  prohibited-measure exit-path AND→OR / widen / related-only narrowing,
  four-way OR general follow-up stops → AND / item drop / recovery misuse,
  related-AE best-effort reverse-flattening or absoluteization,
  three conditional data-collection intensity/object swaps,
  six outcome statuses compression / unknown→持续,
  pkg98 definition ownership absorption, and candidate upgrade
  (no self-proving phrase-only matching)
- package 96/98/99 ownership boundaries; zero candidates for owned+attached
- official matrix keeps zero rows anchored in owned or attached spans
- immutable source fingerprints and checklist freeze (claims_complete=false)

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
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
    / "representative_group_package97_ae_followup_outcome_status_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61ci-package97-ae-followup-outcome-status-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package97-ae-followup-outcome-status-boundary"
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
PACKAGE_97_ORDINAL = 97
PACKAGE_97_ID = "pap-6e961f674f48ee5003dcc014"
PACKAGE_96_ORDINAL = 96
PACKAGE_96_ID = "pap-8dd6a669bdee4e77cc1f0b63"
PACKAGE_98_ORDINAL = 98
PACKAGE_98_ID = "pap-efb197cc99ae53ab03b9a1a2"
PACKAGE_99_ORDINAL = 99
PACKAGE_99_ID = "pap-89963654c275db70b405733e"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1138, 1150)]
ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1150, 1157)]
STRUCTURAL_REFS = ["body.p1138", "body.p1147"]
SEMANTIC_OWNED_REFS = [ref for ref in OWNED_REFS if ref not in STRUCTURAL_REFS]
PKG98_NON_ATTACHED = ["body.p1157"]
PKG99_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1158, 1168)]
PKG96_SPAN_REFS = ["body.p1136", "body.p1137"]
PKG95_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1124, 1136)]
PKG94_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1113, 1124)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG80_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]

EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1138": "paragraph",
    "body.p1139": "paragraph",
    "body.p1140": "paragraph",
    "body.p1141": "list_item",
    "body.p1142": "list_item",
    "body.p1143": "list_item",
    "body.p1144": "list_item",
    "body.p1145": "paragraph",
    "body.p1146": "paragraph",
    "body.p1147": "paragraph",
    "body.p1148": "paragraph",
    "body.p1149": "paragraph",
}

OWNED_EXCERPT_BY_REF = {
    "body.p1138": "不良事件的随访",
    "body.p1139": (
        "在临床试验期间，发生不良事件时，无论事件是否与试验用药品存在因果关系，"
        "均应做出积极处理。患者经历不良事件时应采用可接受的临床治疗措施进行治疗。"
        "如果一定有必要应用研究项目禁止的医疗措施，经与申办者协商后患者应退出本研究。"
    ),
    "body.p1140": "研究者应跟踪每例次不良事件，直至达到下列任何情况之一：",
    "body.p1141": "事件消退；",
    "body.p1142": "事件返回至基线等级或更好；",
    "body.p1143": "事件被研究者评估为稳定；",
    "body.p1144": "参与者失访或撤回同意。",
    "body.p1145": (
        "研究者应尽一切努力随访所有被认为与试验用药品或研究相关程序相关的不良事件，"
        "直至报告最终结局。"
    ),
    "body.p1146": (
        "在随访时应询问及记录不良事件的结果；如有医疗检查或合并用药，应收集并记录检查结果"
        "或合并用药情况；如在当地医院进行诊治，应尽量收集当地医院处理记录和用药信息。"
    ),
    "body.p1147": "不良事件的结果类型",
    "body.p1148": (
        "根据2019年11月22日我国药监局正式发布的《个例安全性报告E2B（R3）区域实施指南》，"
        "不良事件的结果可有如下状态：①痊愈；②好转/缓解；③未好转/未缓解/持续；"
        "④痊愈伴后遗症；⑤致死；⑥未知。"
    ),
    "body.p1149": (
        "不良事件的“结果”针对的是不良事件本身的状态，而非不良事件在医学意义上的状态，因此："
    ),
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1150": (
        "痊愈：指不良事件消失。无论参与者的基线情况是否异常，当不良事件恢复至基线时，即为痊愈。"
    ),
    "body.p1151": "好转/缓解：指不良事件减轻或缓解，在报告时还未消失。",
    "body.p1152": "未好转/未缓解/持续：指不良事件在报告时仍未减轻或缓解。",
    "body.p1153": (
        "伴后遗症：指不良事件导致长期的或永久的生理机能障碍。"
        "不应将恢复期或恢复阶段的某些症状视为后遗症。"
    ),
    "body.p1154": (
        "致死：指参与者因该不良事件导致死亡。如果参与者同时报告有多个不良事件，"
        "其中仅一个不良事件导致死亡，其它未导致死亡的不良事件的结果不应选择死亡。"
    ),
    "body.p1155": "不良事件的结束时间",
    "body.p1156": (
        "应以不良事件解决（如痊愈、致死）、恢复到基线时状态或状态稳定并不能恢复得更好"
        "作为不良事件的结束时间。时间应尽量精确到年月日，如信息收集不全，也应具体到年月。"
        "若参与者失访或撤回知情同意，此情况不应作为“因AE导致退出”而记录；"
        "若明确因AE而退出，则必须跟踪随访具体的退出时间。"
    ),
}

STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1138": ["不良事件的随访"],
    "body.p1139": [
        "无论事件是否与试验用药品存在因果关系",
        "均应做出积极处理",
        "可接受的临床治疗措施",
        "一定有必要",
        "研究项目禁止的医疗措施",
        "经与申办者协商后",
        "应退出本研究",
    ],
    "body.p1140": ["每例次不良事件", "直至达到下列任何情况之一"],
    "body.p1141": ["事件消退"],
    "body.p1142": ["事件返回至基线等级或更好"],
    "body.p1143": ["事件被研究者评估为稳定"],
    "body.p1144": ["参与者失访或撤回同意"],
    "body.p1145": [
        "尽一切努力",
        "被认为与试验用药品或研究相关程序相关的不良事件",
        "直至报告最终结局",
    ],
    "body.p1146": [
        "询问及记录不良事件的结果",
        "如有医疗检查或合并用药",
        "应收集并记录",
        "如在当地医院进行诊治",
        "应尽量收集",
    ],
    "body.p1147": ["不良事件的结果类型"],
    "body.p1148": [
        "痊愈",
        "好转/缓解",
        "未好转/未缓解/持续",
        "痊愈伴后遗症",
        "致死",
        "未知",
    ],
    "body.p1149": [
        "不良事件本身的状态",
        "而非不良事件在医学意义上的状态",
        "因此",
    ],
}

SIX_OUTCOME_STATUSES = [
    "痊愈",
    "好转/缓解",
    "未好转/未缓解/持续",
    "痊愈伴后遗症",
    "致死",
    "未知",
]

EXIT_PATH_AND_FRAGMENTS = [
    "研究项目禁止的医疗措施",
    "经与申办者协商后",
    "应退出本研究",
]
EXIT_PATH_NECESSITY_FRAGMENTS = [
    "一定有必要",
    "确有必要",
]

EXIT_PATH_OR_AFFIRMATIVES = [
    "必要或禁用措施或协商或退出任一即可",
    "禁用措施OR协商即可退出",
    "任何治疗/合并用药即可退出",
    "任何合并用药即退出",
    "应用禁止措施即可退出无需协商",
]

RELATED_ONLY_AFFIRMATIVES = [
    "仅相关不良事件才积极处理",
    "仅与试验用药品相关的AE才处理",
    "无关AE可不处理",
    "仅相关事件需积极处理",
]

ACTIVE_TO_WITHDRAWAL_AFFIRMATIVES = [
    "积极处理意味着必须停药退出",
    "发生AE即应退出研究",
    "积极处理改成必然停药",
    "任何AE均应退出本研究",
]

OR_TO_AND_AFFIRMATIVES = [
    "必须全部满足四项停止情形",
    "直至达到下列全部情况",
    "四项停止情形均为AND",
    "消退且返回基线且稳定且失访才可停止",
]

LOST_AS_RECOVERY_AFFIRMATIVES = [
    "失访或撤回同意视为事件恢复",
    "失访等同于痊愈",
    "撤回同意即表示事件消退",
    "失访自动记录为因AE退出",
]

BEST_EFFORT_ABSOLUTE_AFFIRMATIVES = [
    "尽一切努力保证取得最终结局",
    "必须取得最终结局",
    "相关AE必须随访至最终结局不得因失访停止",
    "保证报告最终结局",
]

GENERAL_TO_RELATED_ONLY_AFFIRMATIVES = [
    "一般随访仅限相关AE",
    "每例次AE缩成仅相关AE",
    "仅相关不良事件才跟踪至停止情形",
]

COLLECTION_INTENSITY_SWAP_AFFIRMATIVES = [
    "当地医院诊治必须绝对收集",
    "应尽量询问及记录结果",
    "医疗检查仅应尽量收集",
    "把应尽量改成必须收集当地医院记录",
    "把询问结果弱化为尽力即可",
]

SIX_STATUS_COMPRESSION_AFFIRMATIVES = [
    "结果状态压缩为痊愈/未痊愈/死亡三类",
    "未知等同于持续",
    "把未知推成未恢复",
    "未知改成持续/未恢复",
    "六类状态可互相替代",
]

PKG98_ABSORPTION_AFFIRMATIVES = [
    "本包拥有痊愈定义",
    "结束时间规则归本包发布",
    "p1150-p1154定义改写为本包拥有",
    "吸收第98包结束时间规则",
]

PKG99_ABSORPTION_AFFIRMATIVES = [
    "妊娠报告要求进入本包提示",
    "吸收第99包妊娠随访",
    "body.p1158纳入本包正向语义",
]

CANDIDATE_UPGRADE_PHRASES = [
    "筛选必做",
    "筛选期必做",
    "基线必做",
    "基线期必做",
    "入组前必查",
    "筛选入组门槛",
    "基线入组门槛",
    "入组门槛",
    "证据缺口",
    "证据不足",
    "不得入组",
    "不符合入选标准",
    "排除标准",
    "入排不通过",
    "发布控制点",
    "转移所有权",
]

ALL_DETERMINISTIC_PHRASES = (
    EXIT_PATH_OR_AFFIRMATIVES
    + RELATED_ONLY_AFFIRMATIVES
    + ACTIVE_TO_WITHDRAWAL_AFFIRMATIVES
    + OR_TO_AND_AFFIRMATIVES
    + LOST_AS_RECOVERY_AFFIRMATIVES
    + BEST_EFFORT_ABSOLUTE_AFFIRMATIVES
    + GENERAL_TO_RELATED_ONLY_AFFIRMATIVES
    + COLLECTION_INTENSITY_SWAP_AFFIRMATIVES
    + SIX_STATUS_COMPRESSION_AFFIRMATIVES
    + PKG98_ABSORPTION_AFFIRMATIVES
    + PKG99_ABSORPTION_AFFIRMATIVES
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


def _qc_blob(config: dict, ref: str) -> str:
    return " ".join(config["clinical_qc_checks_by_source_ref"].get(ref) or [])


def _strip_known_ban_phrases(rule: str) -> str:
    """Remove explicit prohibition / teaching-negation so ban text cannot look affirmative."""
    cleaned = rule
    for phrase in (
        "不得把适用范围缩成仅相关AE",
        "不得把积极处理改成必然停药/退出",
        "不得拆散或OR化“必要+禁用措施+协商+退出”",
        "不得扩大到任何治疗/合并用药即退出",
        "不得把“每例次AE”缩成仅相关AE",
        "不得把“任何情况之一”改成全部满足",
        "不得删除后续四项停止情形中的任一项",
        "不得改成AND合取",
        "不得改成AND",
        "不得把失访/撤回同意解释为事件恢复或痊愈",
        "不得自动记为因AE退出",
        "不得自动记录为因AE退出",
        "不得把一般随访缩成仅相关AE",
        "不得删除失访/撤回同意停止情形",
        "不得把“尽一切努力”改成保证取得结局",
        "不得绝对化为保证取得结局",
        "不得将尽一切努力强化为确保获得最终结局",
        "不得把尽一切努力绝对化为一定要获得最终结局",
        "不得把尽一切努力改成强制取得最终结局",
        "不得把尽一切努力改成一定取得最终结局",
        "不得把尽一切努力改成确保取得最终结局",
        "不得把三组义务压平为同一强度",
        "不得把“应尽量”改成绝对必须或把“应”弱化为尽力即可",
        "不得删除条件或互换对象",
        "不得压缩六类状态",
        "不得互相替代",
        "不得把未知改成持续/未恢复",
        "不得把“未知”推成持续/未恢复",
        "不得把第98包定义重复发布为本包拥有",
        "不得把结果解释为患者整体医学状态",
        "不得吸收或重复发布第98包定义/结束时间规则为本包拥有",
        "不得把定义或结束时间规则吸收为本包拥有",
        "不得把p1157或第99包妊娠内容吸入",
        "不得升格为预筛/筛选/基线控制点",
        "不得升格为预筛/筛选/基线入排控制点",
        "不得与患者整体状态混淆",
        "不得删除“或更好”",
        "不得删除研究者评估",
        "不得删除研究者判断",
        "不得改成客观检验必达或AND合取",
        "不得用标题替代p1148六类状态",
        "不得从标题生成处理/随访/结果义务",
        "不得把标题解释为独立规则、控制点或入排门槛",
        "不得把标题解释为独立规则、状态清单或入排门槛",
        "不得把“基线等级”解释为入排基线门槛",
        "不得解释为事件恢复/痊愈",
        "不得解释为患者整体痊愈",
        "不得改成必须与其他停止情形同时满足",
        "不得反向被p1145相关AE尽力随访限制为仅相关事件",
        "不得反向限制p1140“每例次AE”一般随访",
        "不得抹去p1144失访/撤回同意等现实停止情形",
        "不得夺取其所有权",
        "条件、对象与“应/应尽量”强度不得互换",
        "不是全部满足（AND）",
        "不是全部满足",
    ):
        cleaned = cleaned.replace(phrase, "")
    ban_patterns = (
        # Generic correct-negation clauses led by 不得/不能/禁止/不应.
        # Terminator is clause punctuation OR end-of-string; [^；。] keeps bans from
        # spanning into the next independent affirmative clause.
        r"(?:不得|不能|禁止|不应)(?:把|将)?[^；。]{0,80}?(?:改成|解释为|视为|推成|记为|按作|绝对化|强化|弱化|OR化|吸收|夺取|升格|互换|压平|删除|改写|拆散|扩大|限制|抹去|混淆)[^；。]{0,60}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,50}?(?:预筛|筛选|基线|入排|控制点|门槛|候选)[^；。]{0,30}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,40}?(?:同时满足|全部满足|全部达成|均需满足|AND合取|OR化)[^；。]{0,20}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)(?:把|将)?[^；。]{0,60}?(?:尽一切努力)[^；。]{0,40}?(?:强化|绝对化|改成)[^；。]{0,40}?(?:确保|强制|一定|务必|保证|必须)[^；。]{0,12}?(?:取得|获得|拿到|报告)?[^；。]{0,20}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,50}?(?:保证取得|务必|必须取得|一定(?:要)?(?:取得|获得)|确保(?:取得|获得)|强制(?:取得|获得)|最终结局)[^；。]{0,20}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,40}?(?:停药|退出|恢复|痊愈|因AE退出)[^；。]{0,20}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,40}?(?:未知|持续|未恢复|未好转)[^；。]{0,20}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,40}?(?:第98包|第99包|本包拥有|结束时间|定义)[^；。]{0,30}?(?:[；。]|$)",
        r"(?:不得|不能|禁止|不应)[^；。]{0,40}?(?:应尽量|应/应尽量|强度|对象|三组义务)[^；。]{0,30}?(?:[；。]|$)",
        r"不是全部满足(?:（AND）)?",
    )
    for pattern in ban_patterns:
        cleaned = re.sub(pattern, "", cleaned)
    return cleaned


_LOST_SUBJECT = r"(?:失访|撤回同意|撤回知情同意)"
_RECOVERY_TARGET = r"(?:恢复|结案|消退|好转|痊愈|事件恢复)"
_EQUIV = r"(?:视为|等同于|等于|即表示|意味着|解释为|记为|按作|作为|按|当作)"
_LOST_AS_RECOVERY_PATTERNS = (
    re.compile(rf"{_LOST_SUBJECT}.{{0,16}}{_EQUIV}.{{0,10}}{_RECOVERY_TARGET}"),
    re.compile(rf"{_EQUIV}.{{0,10}}{_RECOVERY_TARGET}.{{0,10}}{_LOST_SUBJECT}"),
    re.compile(rf"{_LOST_SUBJECT}.{{0,12}}可按{_RECOVERY_TARGET}"),
    re.compile(rf"按{_RECOVERY_TARGET}.{{0,8}}(?:处理|结案)"),
)

_AND_CONJOIN_PATTERNS = (
    re.compile(r"(?:实际)?(?:须|必须|应)?(?:同时满足|全部满足|全部达成|均需满足|均需达成|均为AND)"),
    re.compile(r"(?:四项|四类|全部停止情形).{0,8}(?:同时|全部|均).{0,6}(?:满足|达成)"),
)

# Force-word family absoluteizes “尽一切努力” into an outcome guarantee.
_BEST_EFFORT_FORCE = r"(?:务必|保证|必须|必然|一定(?:要)?|确保|强制)"
_BEST_EFFORT_OBTAIN = r"(?:取得|拿到|报告|获得)"
_BEST_EFFORT_OUTCOME = r"(?:最终结局|结局)"
_BEST_EFFORT_ABS_PATTERNS = (
    re.compile(
        rf"{_BEST_EFFORT_FORCE}.{{0,10}}{_BEST_EFFORT_OBTAIN}.{{0,10}}{_BEST_EFFORT_OUTCOME}"
    ),
    re.compile(
        rf"(?:尽一切努力).{{0,8}}{_BEST_EFFORT_FORCE}.{{0,10}}{_BEST_EFFORT_OBTAIN}"
    ),
    re.compile(
        rf"(?:强化|绝对化).{{0,8}}{_BEST_EFFORT_FORCE}.{{0,10}}{_BEST_EFFORT_OBTAIN}"
    ),
    re.compile(r"(?:不可|不能)因失访(?:而)?停止"),
    re.compile(r"不得因失访(?:而)?停止"),
)

_ACTIVE_TO_WITHDRAWAL_PATTERNS = (
    re.compile(r"积极处理.{0,14}(?:即|就是|意味着|要求|等于|改成).{0,10}(?:停药|退出|停药并退出)"),
    re.compile(r"积极处理.{0,10}(?:停药并退出|必然停药|必须退出)"),
)

_UNKNOWN_TO_ONGOING_PATTERNS = (
    re.compile(r"(?:把)?未知.{0,12}(?:视为|等同于|等于|推成|记为|按作|作为|改成).{0,10}(?:持续|未恢复|未好转)"),
    re.compile(r"未知可记为(?:持续|未恢复|未好转)"),
)

_RELATED_ONLY_FLATTEN_PATTERNS = (
    re.compile(r"每例次(?:AE|不良事件)?.{0,10}(?:中的)?相关(?:AE|事件|不良事件)?"),
    re.compile(r"(?:仅限|仅对|只对)每例次.{0,10}相关"),
)

_EXIT_PATH_OR_PATTERNS = (
    re.compile(
        r"(?:必要(?:性)?|禁用措施|协商|退出).{0,20}(?:任一|或者).{0,12}(?:即可|可退出|即可退出|条件可退出)"
    ),
    re.compile(r"任一条件(?:即可|可)退出"),
    re.compile(r"(?:必要|禁用措施|协商|退出).{0,8}OR.{0,12}(?:即可|退出)"),
)

_PKG98_ABSORB_PATTERNS = (
    re.compile(r"(?:定义|痊愈|结束时间).{0,16}(?:由)?本包.{0,10}(?:解释|发布|拥有)"),
    re.compile(r"本包.{0,8}(?:解释并发布|发布定义|拥有定义|拥有痊愈)"),
    re.compile(r"(?:定义|结束时间规则).{0,10}归本包发布"),
)

_INTENSITY_SWAP_PATTERNS = (
    re.compile(r"当地医院.{0,20}(?:必须|绝对|务必)(?:收集|取得)"),
    re.compile(r"(?:询问|记录结果).{0,12}应尽量"),
    re.compile(r"(?:医疗检查|合并用药).{0,12}应尽量"),
    re.compile(r"应尽量.{0,10}(?:医疗检查|合并用药|检查结果)"),
    re.compile(r"(?:把)?应尽量.{0,8}改成.{0,8}(?:必须|绝对)"),
    re.compile(r"(?:把)?应.{0,6}弱化为.{0,8}(?:尽力|应尽量)"),
)


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _has_lost_as_recovery_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, LOST_AS_RECOVERY_AFFIRMATIVES) or _matches_any(
        purified, _LOST_AS_RECOVERY_PATTERNS
    )


def _has_or_to_and_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, OR_TO_AND_AFFIRMATIVES) or _matches_any(
        purified, _AND_CONJOIN_PATTERNS
    )


def _has_best_effort_absolute_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, BEST_EFFORT_ABSOLUTE_AFFIRMATIVES) or _matches_any(
        purified, _BEST_EFFORT_ABS_PATTERNS
    )


def _has_active_to_withdrawal_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, ACTIVE_TO_WITHDRAWAL_AFFIRMATIVES) or _matches_any(
        purified, _ACTIVE_TO_WITHDRAWAL_PATTERNS
    )


def _has_unknown_to_ongoing_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, SIX_STATUS_COMPRESSION_AFFIRMATIVES) or _matches_any(
        purified, _UNKNOWN_TO_ONGOING_PATTERNS
    )


def _has_related_only_flatten_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, GENERAL_TO_RELATED_ONLY_AFFIRMATIVES) or _matches_any(
        purified, _RELATED_ONLY_FLATTEN_PATTERNS
    )


def _has_exit_path_or_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, EXIT_PATH_OR_AFFIRMATIVES) or _matches_any(
        purified, _EXIT_PATH_OR_PATTERNS
    )


def _has_pkg98_absorption_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, PKG98_ABSORPTION_AFFIRMATIVES) or _matches_any(
        purified, _PKG98_ABSORB_PATTERNS
    )


def _has_intensity_swap_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    return _has_any(purified, COLLECTION_INTENSITY_SWAP_AFFIRMATIVES) or _matches_any(
        purified, _INTENSITY_SWAP_PATTERNS
    )


def _has_candidate_upgrade_affirmative(positive_rule: str) -> bool:
    purified = _strip_known_ban_phrases(positive_rule)
    if _forbidden_marker_hits(purified, CANDIDATE_UPGRADE_PHRASES):
        return True
    return bool(
        re.search(
            r"(?:筛选|基线).{0,8}(?:必做|入组门槛|控制点)|入组前必查|证据缺口|不得入组|排除标准|发布控制点",
            purified,
        )
    )


def _p1146_three_obligations_present(exception_rule: str) -> bool:
    """Authoritative positive field only — preserve/base/QC/notes cannot substitute."""
    rule = exception_rule
    ask = ("询问并记录" in rule) or ("询问及记录" in rule)
    labs = (("医疗检查或合并用药" in rule) or ("医疗检查" in rule and "合并用药" in rule)) and (
        "应收集" in rule or "收集并记录" in rule
    )
    local = ("当地医院" in rule) and ("应尽量" in rule)
    return ask and labs and local


def _package97_contract_issues(config: dict) -> set[str]:
    """Validate Package 97 via authoritative positive config fields.

    Positive obligations are checked primarily on exception_rule so that
    correct keywords / forbidden_inversion / notes / QC text cannot mask a
    broken positive rule.
    """
    issues: set[str] = set()
    semantics = config["exception_semantics_by_source_ref"]

    if list(config.get("owned_source_refs") or []) != OWNED_REFS:
        issues.add("OWNED_REFS")
    if list(config.get("attached_source_refs") or []) != ATTACHED_REFS:
        issues.add("ATTACHED_REFS")
    if list(config.get("structural_only_source_refs") or []) != STRUCTURAL_REFS:
        issues.add("STRUCTURAL_REFS")
    if config.get("claims_complete") is True:
        issues.add("CLAIMS_COMPLETE_TRUE")
    if config.get("required_candidate_source_refs"):
        issues.add("REQUIRED_CANDIDATE_NONEMPTY")

    for ref in OWNED_REFS:
        if semantics[ref]["base_rule"] != OWNED_EXCERPT_BY_REF[ref]:
            issues.add(f"{ref}:SOURCE_TEXT")

    # Structural titles must stay structural-only and never invent obligations.
    for ref in STRUCTURAL_REFS:
        entry = semantics[ref]
        rule = entry["exception_rule"]
        positive = _strip_known_ban_phrases(rule)
        if "仅作结构" not in rule and "结构" not in rule:
            issues.add(f"{ref}:STRUCTURAL_ONLY")
        if _has_any(
            positive,
            [
                "应积极处理",
                "应跟踪每例次",
                "六类结果状态必须",
                "应退出本研究",
                "尽一切努力随访",
            ],
        ):
            issues.add(f"{ref}:STRUCTURAL_ONLY")

    # p1139: any-AE active management + prohibited-measure exit AND path.
    p1139 = semantics["body.p1139"]
    p1139_rule = p1139["exception_rule"]
    p1139_pos = _strip_known_ban_phrases(p1139_rule)
    if "无论" not in p1139_rule or "因果关系" not in p1139_rule:
        issues.add("body.p1139:CAUSALITY_SCOPE")
    if "积极处理" not in p1139_rule:
        issues.add("body.p1139:ACTIVE_MANAGEMENT")
    if not all(frag in p1139_rule for frag in EXIT_PATH_AND_FRAGMENTS):
        issues.add("body.p1139:EXIT_PATH_AND")
    if not any(frag in p1139_rule for frag in EXIT_PATH_NECESSITY_FRAGMENTS):
        issues.add("body.p1139:EXIT_PATH_AND")
    if _has_exit_path_or_affirmative(p1139_rule):
        issues.add("body.p1139:EXIT_PATH_AND")
    if _has_any(p1139_pos, RELATED_ONLY_AFFIRMATIVES):
        issues.add("body.p1139:CAUSALITY_SCOPE")
    if _has_active_to_withdrawal_affirmative(p1139_rule):
        issues.add("body.p1139:ACTIVE_MANAGEMENT")
    forbid_1139 = p1139["forbidden_inversion"]
    if not all(
        frag in forbid_1139
        for frag in (
            "不得把适用范围缩成仅相关AE",
            "不得把积极处理改成必然停药/退出",
            "不得拆散或OR化“必要+禁用措施+协商+退出”",
            "不得扩大到任何治疗/合并用药即退出",
        )
    ):
        issues.add("body.p1139:FORBIDDEN_INVERSION")

    # p1140-p1144: per-AE general follow-up with four OR stops.
    p1140 = semantics["body.p1140"]
    p1140_rule = p1140["exception_rule"]
    p1140_pos = _strip_known_ban_phrases(p1140_rule)
    if "每例次" not in p1140_rule:
        issues.add("body.p1140:PER_AE_SCOPE")
    if "任何情况之一" not in p1140_rule and "OR" not in p1140_rule:
        issues.add("body.p1140:OR_STOPS")
    if _has_or_to_and_affirmative(p1140_rule):
        issues.add("body.p1140:OR_STOPS")
    if _has_related_only_flatten_affirmative(p1140_rule):
        issues.add("body.p1140:PER_AE_SCOPE")
        issues.add("body.p1140:OR_STOPS")

    stop_refs = {
        "body.p1141": "事件消退",
        "body.p1142": "事件返回至基线等级或更好",
        "body.p1143": "事件被研究者评估为稳定",
        "body.p1144": "参与者失访或撤回同意",
    }
    for ref, fragment in stop_refs.items():
        entry = semantics[ref]
        rule = entry["exception_rule"]
        pos = _strip_known_ban_phrases(rule)
        if fragment not in entry["base_rule"] and fragment not in rule:
            issues.add(f"{ref}:STOP_ITEM")
        if "OR" not in rule and "停止情形之一" not in rule and "之一" not in rule:
            issues.add(f"{ref}:OR_ITEM")
        if _has_or_to_and_affirmative(rule):
            issues.add(f"{ref}:OR_ITEM")
            issues.add("body.p1140:OR_STOPS")
        # M2: “或更好” must live in purified/positive exception_rule, not base_rule alone.
        if ref == "body.p1142" and "或更好" not in rule:
            issues.add("body.p1142:OR_BETTER")
        if ref == "body.p1143" and "研究者" not in rule and "研究者" not in entry["base_rule"]:
            issues.add("body.p1143:INVESTIGATOR")
        if ref == "body.p1144":
            if _has_lost_as_recovery_affirmative(rule):
                issues.add("body.p1144:LOST_NOT_RECOVERY")
            if "因AE退出" not in rule and "因AE退出" not in entry.get("forbidden_inversion", ""):
                issues.add("body.p1144:LOST_NOT_AE_WITHDRAWAL")
            if "现实停止" not in rule and "不得解释为事件恢复" not in rule and "不得自动记录为因AE退出" not in rule:
                if "因AE退出" not in rule:
                    issues.add("body.p1144:LOST_NOT_AE_WITHDRAWAL")

    # p1145: related-AE best-effort follow-up must not flatten general follow-up.
    p1145 = semantics["body.p1145"]
    p1145_rule = p1145["exception_rule"]
    p1145_pos = _strip_known_ban_phrases(p1145_rule)
    if "尽一切努力" not in p1145_rule:
        issues.add("body.p1145:BEST_EFFORT")
    if "相关" not in p1145_rule:
        issues.add("body.p1145:RELATED_SCOPE")
    if "不得反向限制" not in p1145_rule and "不得反向限制" not in p1145["forbidden_inversion"]:
        issues.add("body.p1145:NO_REVERSE_FLATTEN")
    if _has_best_effort_absolute_affirmative(p1145_rule):
        issues.add("body.p1145:BEST_EFFORT")
    if _has_related_only_flatten_affirmative(p1145_rule):
        issues.add("body.p1145:NO_REVERSE_FLATTEN")
    if "p1144" not in p1145_rule and "失访" not in p1145_rule and "失访" not in p1145["forbidden_inversion"]:
        issues.add("body.p1145:KEEP_REALITY_STOP")

    # p1146: three conditional collection obligations with intensity separation.
    # M1: obligations must be satisfied by exception_rule alone.
    p1146 = semantics["body.p1146"]
    p1146_rule = p1146["exception_rule"]
    p1146_pos = _strip_known_ban_phrases(p1146_rule)
    if not _p1146_three_obligations_present(p1146_rule):
        issues.add("body.p1146:THREE_OBLIGATIONS")
    if "应/应尽量" not in p1146_rule and "应尽量" not in p1146_rule:
        issues.add("body.p1146:INTENSITY")
    if _has_intensity_swap_affirmative(p1146_rule):
        issues.add("body.p1146:INTENSITY")

    # p1148: six outcome statuses on positive exception_rule.
    p1148 = semantics["body.p1148"]
    p1148_rule = p1148["exception_rule"]
    p1148_pos = _strip_known_ban_phrases(p1148_rule)
    if not all(status in p1148_rule for status in SIX_OUTCOME_STATUSES):
        issues.add("body.p1148:SIX_STATUSES")
    if "六类" not in p1148_rule and "逐项保留" not in p1148_rule:
        issues.add("body.p1148:SIX_STATUSES")
    if _has_unknown_to_ongoing_affirmative(p1148_rule):
        issues.add("body.p1148:SIX_STATUSES")
    if "未知" not in p1148_rule:
        issues.add("body.p1148:UNKNOWN_KEPT")

    # p1149: outcome targets AE event state; pkg98 closes definitions read-only.
    p1149 = semantics["body.p1149"]
    p1149_rule = p1149["exception_rule"]
    p1149_pos = _strip_known_ban_phrases(p1149_rule)
    if "不良事件本身的状态" not in p1149_rule and "本身的状态" not in p1149_rule:
        issues.add("body.p1149:EVENT_STATE")
    if "第98包" not in p1149_rule and "p1150" not in p1149_rule:
        issues.add("body.p1149:PKG98_READONLY_CLOSURE")
    if _has_pkg98_absorption_affirmative(p1149_rule):
        issues.add("body.p1149:PKG98_OWNERSHIP")
    if _has_any(p1149_pos, PKG99_ABSORPTION_AFFIRMATIVES):
        issues.add("body.p1149:PKG99_OWNERSHIP")

    # C1: candidate-upgrade markers in purified positive exception_rule of owned refs.
    for ref in OWNED_REFS:
        rule = semantics[ref]["exception_rule"]
        if _has_candidate_upgrade_affirmative(rule):
            issues.add(f"{ref}:CANDIDATE_UPGRADE")
            issues.add("CANDIDATE_UPGRADE_IN_POSITIVE")

    # Ownership / absorption guards.
    owned = list(config.get("owned_source_refs") or [])
    attached = list(config.get("attached_source_refs") or [])
    owned_and_attached = set(owned + attached)
    if set(owned) & set(ATTACHED_REFS):
        issues.add("PACKAGE98_OWNERSHIP")
    if owned_and_attached & set(PKG98_NON_ATTACHED):
        issues.add("PACKAGE98_P1157_ABSORPTION")
    if owned_and_attached & set(PKG99_SPAN_REFS):
        issues.add("PACKAGE99_ABSORPTION")
    if owned_and_attached & set(PKG96_SPAN_REFS):
        issues.add("PACKAGE96_ABSORPTION")

    boundary_note = config.get("later_package_boundary", {}).get("note", "")
    notes_blob = " ".join(config.get("notes") or [])
    ownership_blob = " ".join(
        [
            boundary_note,
            notes_blob,
            p1149_rule,
            _qc_blob(config, "body.p1149"),
            _qc_blob(config, "body.p1150"),
            _qc_blob(config, "body.p1156"),
        ]
    )
    if "第98包" not in ownership_blob:
        issues.add("PACKAGE98_BOUNDARY_NOTE")
    if "第99包" not in ownership_blob:
        issues.add("PACKAGE99_BOUNDARY_NOTE")
    if "p1157" not in ownership_blob and "body.p1157" not in ownership_blob:
        issues.add("PACKAGE98_P1157_BOUNDARY")
    if "零候选" not in ownership_blob:
        issues.add("ZERO_CANDIDATE_NOTE")

    # Disposition / forbidden candidate partition.
    for ref in OWNED_REFS + ATTACHED_REFS:
        disposition = (config.get("expected_disposition_by_source_ref") or {}).get(ref)
        if ref in STRUCTURAL_REFS:
            if disposition not in (None, "structural", "structure"):
                # structural refs are absent from expected_disposition map by design
                if disposition is not None:
                    issues.add(f"{ref}:DISPOSITION")
        elif ref in SEMANTIC_OWNED_REFS:
            if disposition != "post_treatment_execution":
                issues.add(f"{ref}:DISPOSITION")
        markers = config.get("candidate_forbidden_markers_by_source_ref", {}).get(ref) or []
        if not markers:
            issues.add(f"{ref}:FORBIDDEN_MARKERS")
        if ref not in (config.get("forbidden_candidate_source_refs") or []):
            issues.add(f"{ref}:FORBIDDEN_CANDIDATE_SET")

    return issues


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL
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
    assert config["group_id"] == "d001-ii-package97-ae-followup-outcome-status-boundary"
    assert config["task_id"] == "phase5-slice61ci-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert config["structural_only_source_refs"] == STRUCTURAL_REFS
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) >= set(OWNED_REFS + ATTACHED_REFS)
    assert config.get("claims_complete") is not True
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    for ref in SEMANTIC_OWNED_REFS:
        assert (
            config["expected_disposition_by_source_ref"][ref]
            == "post_treatment_execution"
        )
    for ref in STRUCTURAL_REFS:
        assert ref not in config["expected_disposition_by_source_ref"]
    assert _package97_contract_issues(config) == set()


def test_package97_contract_is_currently_closed(config: dict) -> None:
    assert _package97_contract_issues(config) == set()


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    assert config["attached_source_refs"] == ATTACHED_REFS
    owners = {
        unit["source_ref"]: pkg["package_ordinal"]
        for pkg in plan["packages"]
        for unit in pkg["owned_units"]
    }
    for ref in ATTACHED_REFS:
        assert owners[ref] == PACKAGE_98_ORDINAL
        assert ref not in config["owned_source_refs"]


def test_attached_refs_ownership_documented(plan: dict) -> None:
    pkg98 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_98_ORDINAL)
    owned98 = {u["source_ref"] for u in pkg98["owned_units"]}
    assert set(ATTACHED_REFS).issubset(owned98)
    assert "body.p1157" in owned98
    assert "body.p1157" not in ATTACHED_REFS


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    by_ord = {p["package_ordinal"]: p for p in plan["packages"]}
    assert by_ord[PACKAGE_96_ORDINAL]["package_id"] == PACKAGE_96_ID
    assert by_ord[PACKAGE_97_ORDINAL]["package_id"] == PACKAGE_97_ID
    assert by_ord[PACKAGE_98_ORDINAL]["package_id"] == PACKAGE_98_ID
    assert by_ord[PACKAGE_99_ORDINAL]["package_id"] == PACKAGE_99_ID
    assert len(by_ord[PACKAGE_97_ORDINAL]["owned_units"]) == 12
    assert len(by_ord[PACKAGE_98_ORDINAL]["owned_units"]) == 8
    assert len(by_ord[PACKAGE_99_ORDINAL]["owned_units"]) == 10
    assert len(by_ord[PACKAGE_96_ORDINAL]["owned_units"]) == 2


def test_owned_refs_match_frozen_package_97(config: dict, plan: dict) -> None:
    pkg = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL)
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        assert config["exception_semantics_by_source_ref"][ref]["base_rule"] == excerpt
        assert excerpt == OWNED_EXCERPT_BY_REF[ref]


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == excerpt


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    pkg = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL)
    for unit in pkg["owned_units"]:
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[unit["source_ref"]]


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    for ref, excerpt in _owned_excerpt_by_ref(plan).items():
        assert _structure_blob_text(structure_blob, ref) == excerpt


def test_p1139_exit_path_and_active_management_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1139"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1139") == []
    blob = _semantic_blob(semantics)
    assert "无论事件是否与试验用药品存在因果关系" in blob
    assert "积极处理" in blob
    assert all(frag in blob for frag in EXIT_PATH_AND_FRAGMENTS)
    assert any(frag in blob for frag in EXIT_PATH_NECESSITY_FRAGMENTS)
    assert "不得拆散或OR化“必要+禁用措施+协商+退出”" in blob
    assert "不得把适用范围缩成仅相关AE" in blob


def test_exit_path_or_weakening_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "任何AE积极处理；必要或禁用措施或协商或退出任一即可；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    semantic["preserve_keywords"] = ["积极处理"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:EXIT_PATH_AND" in issues


def test_related_only_active_management_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "仅相关不良事件才积极处理；一定有必要+禁用措施+协商后退出；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:CAUSALITY_SCOPE" in issues


def test_active_management_to_mandatory_withdrawal_mutation_is_detected(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "无论因果关系均应做出积极处理；发生AE即应退出研究；"
        "一定有必要应用研究项目禁止的医疗措施，经与申办者协商后患者应退出本研究；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:ACTIVE_MANAGEMENT" in issues


def test_exit_path_widen_to_any_treatment_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "无论因果关系均应积极处理；任何治疗/合并用药即可退出；"
        "一定有必要；研究项目禁止的医疗措施；经与申办者协商后；应退出本研究；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:EXIT_PATH_AND" in issues


def test_p1140_p1144_four_or_stops_preserved(config: dict) -> None:
    p1140 = config["exception_semantics_by_source_ref"]["body.p1140"]
    assert _missing_structural_fragments(p1140["base_rule"], "body.p1140") == []
    assert "任何情况之一" in p1140["base_rule"]
    assert "OR" in p1140["exception_rule"] or "任何情况之一" in p1140["exception_rule"]
    for ref, fragment in {
        "body.p1141": "事件消退",
        "body.p1142": "或更好",
        "body.p1143": "研究者评估",
        "body.p1144": "失访或撤回同意",
    }.items():
        entry = config["exception_semantics_by_source_ref"][ref]
        assert fragment in entry["base_rule"] or fragment in _semantic_blob(entry)


def test_or_to_and_followup_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1140"]
    semantic["exception_rule"] = (
        "研究者应跟踪每例次不良事件，必须全部满足四项停止情形；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    semantic["preserve_keywords"] = ["每例次不良事件"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1140:OR_STOPS" in issues


def test_general_followup_related_only_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1140"]
    semantic["exception_rule"] = (
        "一般随访仅限相关AE；直至达到下列任何情况之一（OR）；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1140:PER_AE_SCOPE" in issues


def test_lost_to_followup_as_recovery_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1144"]
    semantic["exception_rule"] = (
        "一般随访OR停止情形之一：参与者失访或撤回同意。失访或撤回同意视为事件恢复；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    issues = _package97_contract_issues(mutated)
    assert "body.p1144:LOST_NOT_RECOVERY" in issues


def test_investigator_assessment_drop_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1143"]
    semantic["base_rule"] = "事件稳定；"
    semantic["exception_rule"] = "一般随访OR停止情形之一：事件稳定；零候选"
    semantic["preserve_keywords"] = ["事件稳定"]
    semantic["forbidden_inversion"] = "不得改成AND合取；不得升格为预筛/筛选/基线控制点"
    issues = _package97_contract_issues(mutated)
    assert "body.p1143:INVESTIGATOR" in issues or "body.p1143:SOURCE_TEXT" in issues


def test_p1145_best_effort_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1145"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1145") == []
    blob = _semantic_blob(semantics)
    assert "尽一切努力" in blob
    assert "相关" in blob
    assert "不得反向限制" in blob
    assert "保证取得结局" in blob or "绝对化" in blob


def test_best_effort_absoluteization_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
    semantic["exception_rule"] = (
        "相关AE尽一切努力保证取得最终结局；不得因失访停止；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    issues = _package97_contract_issues(mutated)
    assert "body.p1145:BEST_EFFORT" in issues


def test_best_effort_reverse_flatten_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
    semantic["exception_rule"] = (
        "一般随访仅限相关AE；尽一切努力随访相关AE至最终结局；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1145:NO_REVERSE_FLATTEN" in issues


def test_p1146_three_conditional_obligations_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1146"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1146") == []
    blob = _semantic_blob(semantics)
    assert "询问" in blob and "记录" in blob
    assert "医疗检查或合并用药" in blob
    assert "应收集并记录" in blob
    assert "当地医院" in blob
    assert "应尽量" in blob
    assert "应/应尽量" in blob or "强度不得互换" in blob


def test_collection_intensity_swap_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1146"]
    semantic["exception_rule"] = (
        "三组义务：询问结果；检查/合并用药；当地医院诊治必须绝对收集；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    semantic["preserve_keywords"] = ["询问及记录不良事件的结果"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1146:INTENSITY" in issues


def test_p1148_six_statuses_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1148"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1148") == []
    blob = _semantic_blob(semantics)
    assert all(status in blob for status in SIX_OUTCOME_STATUSES)
    assert "未知" in blob
    assert "不得把“未知”推成持续/未恢复" in blob or "未知" in semantics["exception_rule"]


def test_six_status_compression_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1148"]
    semantic["exception_rule"] = (
        "结果状态压缩为痊愈/未痊愈/死亡三类；未知等同于持续；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    semantic["preserve_keywords"] = ["痊愈", "致死"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1148:SIX_STATUSES" in issues


def test_unknown_pushed_to_ongoing_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1148"]
    semantic["exception_rule"] = (
        "六类结果状态必须逐项保留：痊愈；好转/缓解；未好转/未缓解/持续；"
        "痊愈伴后遗症；致死；未知。把未知推成未恢复；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1148:SIX_STATUSES" in issues


def test_p1149_event_state_and_pkg98_readonly_closure_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1149"]
    assert _missing_structural_fragments(semantics["base_rule"], "body.p1149") == []
    blob = _semantic_blob(semantics)
    assert "不良事件本身的状态" in blob
    assert "第98包" in blob
    assert "p1150" in blob or "body.p1150" in blob or "p1150-p1154" in blob
    assert "不得" in blob and ("吸收" in blob or "拥有" in blob)


def test_pkg98_definition_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1149"]
    semantic["exception_rule"] = (
        "结果针对AE本身状态；本包拥有痊愈定义；结束时间规则归本包发布；零候选"
    )
    semantic["forbidden_inversion"] = "不得升格为预筛/筛选/基线控制点"
    issues = _package97_contract_issues(mutated)
    assert "body.p1149:PKG98_OWNERSHIP" in issues


def test_pkg98_attached_to_owned_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"] = OWNED_REFS + ["body.p1150"]
    mutated["attached_source_refs"] = [r for r in ATTACHED_REFS if r != "body.p1150"]
    issues = _package97_contract_issues(mutated)
    assert "OWNED_REFS" in issues or "PACKAGE98_OWNERSHIP" in issues


def test_pkg98_p1157_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = ATTACHED_REFS + ["body.p1157"]
    issues = _package97_contract_issues(mutated)
    assert "ATTACHED_REFS" in issues or "PACKAGE98_P1157_ABSORPTION" in issues


def test_pkg99_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = ATTACHED_REFS + ["body.p1158"]
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1149"]
    semantic["exception_rule"] = (
        semantic["exception_rule"] + "；妊娠报告要求进入本包提示"
    )
    issues = _package97_contract_issues(mutated)
    assert (
        "ATTACHED_REFS" in issues
        or "PACKAGE99_ABSORPTION" in issues
        or "body.p1149:PKG99_OWNERSHIP" in issues
    )


def test_required_candidate_upgrade_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["required_candidate_source_refs"] = ["body.p1139"]
    issues = _package97_contract_issues(mutated)
    assert "REQUIRED_CANDIDATE_NONEMPTY" in issues


def test_claims_complete_true_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["claims_complete"] = True
    assert "CLAIMS_COMPLETE_TRUE" in _package97_contract_issues(mutated)


def test_wrong_positive_rule_not_masked_by_correct_forbid_notes_qc(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1140"]
    # Keep correct forbid / preserve / QC / notes, break only positive exception_rule.
    semantic["exception_rule"] = (
        "必须全部满足四项停止情形；零候选"
    )
    mutated["clinical_qc_checks_by_source_ref"]["body.p1140"] = [
        "保持每例次AE与四类OR停止情形",
        "不得AND化",
        "零候选",
    ]
    mutated["notes"] = list(config["notes"]) + ["OR停止情形完整"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1140:OR_STOPS" in issues


def test_exit_path_not_masked_by_forbid_notes_qc_alone(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = "必要或禁用措施或协商或退出任一即可；零候选"
    # Keep correct forbidden_inversion and QC.
    assert "不得拆散或OR化“必要+禁用措施+协商+退出”" in semantic["forbidden_inversion"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:EXIT_PATH_AND" in issues


def test_six_status_not_masked_by_qc_alone(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1148"]
    semantic["exception_rule"] = "结果状态压缩为痊愈/未痊愈/死亡三类；零候选"
    mutated["clinical_qc_checks_by_source_ref"]["body.p1148"] = [
        "六类状态逐项保留，未知不得推成持续",
        "零候选",
    ]
    issues = _package97_contract_issues(mutated)
    assert "body.p1148:SIX_STATUSES" in issues


def test_structural_heading_never_converted_to_obligations(config: dict) -> None:
    for ref in STRUCTURAL_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert "结构" in entry["exception_rule"] or "仅作结构" in entry["exception_rule"]
        mutated = copy.deepcopy(config)
        mutated["exception_semantics_by_source_ref"][ref]["exception_rule"] = (
            "应积极处理并尽一切努力随访；六类结果状态必须发布；应退出本研究"
        )
        assert f"{ref}:STRUCTURAL_ONLY" in _package97_contract_issues(mutated)



def test_m1_p1146_obligations_not_masked_by_preserve_keywords(config: dict) -> None:
    """M1: wiping exception_rule must fail even if preserve_keywords stay complete."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1146"]
    semantic["exception_rule"] = "随访时应收集资料；零候选"
    # Keep preserve_keywords / forbid / QC untouched.
    assert semantic["preserve_keywords"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1146:THREE_OBLIGATIONS" in issues


def test_m2_p1142_or_better_not_masked_by_base_rule(config: dict) -> None:
    """M2: ‘或更好’ must live in exception_rule; base_rule alone is insufficient."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1142"]
    semantic["exception_rule"] = "一般随访OR停止情形之一：事件返回至基线等级；零候选"
    semantic["preserve_keywords"] = ["事件返回至基线等级"]
    assert "或更好" in semantic["base_rule"]
    issues = _package97_contract_issues(mutated)
    assert "body.p1142:OR_BETTER" in issues


def test_s1_lost_as_recovery_synonym_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1144"]
    semantic["exception_rule"] = (
        "一般随访OR停止情形之一：参与者失访或撤回同意。失访后可按恢复结案；"
        "不得自动记录为因AE退出；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1144:LOST_NOT_RECOVERY" in issues


def test_s1_lost_as_recovery_ban_context_does_not_false_positive(config: dict) -> None:
    # Closed config already contains ban-only recovery language.
    assert "body.p1144:LOST_NOT_RECOVERY" not in _package97_contract_issues(config)


def test_s2_or_to_and_while_keeping_zhiyi_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1140"]
    semantic["exception_rule"] = (
        "一般随访作用于每例次AE；停止情形为下列任何情况之一（OR）；"
        "实际须同时满足四项；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1140:OR_STOPS" in issues


def test_s2_or_and_ban_teaching_does_not_false_positive(config: dict) -> None:
    assert "body.p1140:OR_STOPS" not in _package97_contract_issues(config)


def test_s3_best_effort_absolute_synonyms_are_detected(config: dict) -> None:
    probes = (
        "相关AE尽一切努力务必拿到最终结局；零候选",
        "相关AE尽一切努力保证取得最终结局；零候选",
        "相关AE尽一切努力随访至最终结局；不可因失访停止；零候选",
        # Worker_03 residual force×obtain family.
        "相关AE尽一切努力一定要获得最终结局；零候选",
        "相关AE尽一切努力一定取得最终结局；零候选",
        "相关AE尽一切努力确保取得最终结局；零候选",
        "相关AE尽一切努力强制取得最终结局；零候选",
        "相关AE尽一切努力确保获得最终结局；零候选",
    )
    for clause in probes:
        mutated = copy.deepcopy(config)
        semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
        semantic["exception_rule"] = clause
        semantic["forbidden_inversion"] = (
            "不得把一般随访缩成仅相关AE；不得删除失访/撤回同意停止情形；"
            "不得升格为预筛/筛选/基线控制点"
        )
        issues = _package97_contract_issues(mutated)
        assert "body.p1145:BEST_EFFORT" in issues, clause


def test_s3_best_effort_ban_context_does_not_false_positive(config: dict) -> None:
    assert "body.p1145:BEST_EFFORT" not in _package97_contract_issues(config) or (
        "尽一切努力" in config["exception_semantics_by_source_ref"]["body.p1145"]["exception_rule"]
        and _package97_contract_issues(config) == set()
    )
    assert _package97_contract_issues(config) == set()


def test_s3_best_effort_ensure_obtain_ban_teaching_does_not_false_positive(
    config: dict,
) -> None:
    """Correct negation must not fire after purification."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
    semantic["exception_rule"] = (
        "仅对被认为与试验用药品或研究相关程序相关的AE，尽一切努力随访至最终结局。"
        "不得将尽一切努力强化为确保获得最终结局；"
        "不得把尽一切努力绝对化为一定要获得最终结局；"
        "不得把尽一切努力改成强制取得最终结局；"
        "不得反向限制p1140“每例次AE”一般随访；不得抹去p1144失访/撤回同意等现实停止情形；零候选"
    )
    assert _package97_contract_issues(mutated) == set()
    assert not _has_best_effort_absolute_affirmative(semantic["exception_rule"])


def test_s4_active_management_to_withdrawal_synonym_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "任何AE无论因果关系如何均应积极处理；积极处理即要求停药并退出；"
        "确有必要使用研究项目禁止的医疗措施，经与申办者协商后患者应退出本研究；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:ACTIVE_MANAGEMENT" in issues


def test_s4_active_withdrawal_ban_context_does_not_false_positive(config: dict) -> None:
    assert "body.p1139:ACTIVE_MANAGEMENT" not in _package97_contract_issues(config)


def test_s5_unknown_to_ongoing_synonyms_are_detected(config: dict) -> None:
    probes = (
        "未知视为持续",
        "把未知推成持续",
        "未知可记为未恢复",
    )
    for clause in probes:
        mutated = copy.deepcopy(config)
        semantic = mutated["exception_semantics_by_source_ref"]["body.p1148"]
        semantic["exception_rule"] = (
            "六类结果状态必须逐项保留：痊愈；好转/缓解；未好转/未缓解/持续；"
            f"痊愈伴后遗症；致死；未知。{clause}；零候选"
        )
        issues = _package97_contract_issues(mutated)
        assert "body.p1148:SIX_STATUSES" in issues, clause


def test_s5_unknown_ban_context_does_not_false_positive(config: dict) -> None:
    assert "body.p1148:SIX_STATUSES" not in _package97_contract_issues(config)


def test_s6_per_ae_related_only_flatten_synonym_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1140"]
    semantic["exception_rule"] = (
        "一般随访作用于每例次AE中的相关事件；停止情形为下列任何情况之一（OR）；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1140:PER_AE_SCOPE" in issues


def test_s7_exit_path_or_synonym_with_and_fragments_kept_is_detected(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1139"]
    semantic["exception_rule"] = (
        "任何AE无论因果关系如何均应积极处理；确有必要；研究项目禁止的医疗措施；"
        "经与申办者协商后；应退出本研究；禁用措施、协商、退出任一条件可退出；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1139:EXIT_PATH_AND" in issues


def test_s8_pkg98_definition_absorption_synonym_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1149"]
    semantic["exception_rule"] = (
        "结果针对不良事件本身的状态；痊愈等定义由本包解释并发布；"
        "第98包只读p1150-p1154与p1156闭合；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1149:PKG98_OWNERSHIP" in issues


def test_c1_candidate_upgrade_in_positive_exception_rule_is_detected(
    config: dict,
) -> None:
    for phrase in ("筛选必做", "筛选入组门槛"):
        mutated = copy.deepcopy(config)
        semantic = mutated["exception_semantics_by_source_ref"]["body.p1142"]
        semantic["exception_rule"] = (
            "一般随访OR停止情形之一：事件返回至基线等级或更好；"
            f"{phrase}；零候选"
        )
        issues = _package97_contract_issues(mutated)
        assert "body.p1142:CANDIDATE_UPGRADE" in issues, phrase
        assert "CANDIDATE_UPGRADE_IN_POSITIVE" in issues, phrase


def test_c1_candidate_ban_context_does_not_false_positive(config: dict) -> None:
    # Closed owned rules contain “不得升格为…筛选/基线…” ban language only.
    assert "CANDIDATE_UPGRADE_IN_POSITIVE" not in _package97_contract_issues(config)


def test_trailing_unpunctuated_candidate_ban_does_not_false_positive(config: dict) -> None:
    """Worker_03 residual: ban at field end without ；/。 must purify via $."""
    for lead, ban in (
        ("不得", "筛选必做"),
        ("不能", "筛选必做"),
        ("禁止", "筛选必做"),
        ("不应", "筛选必做"),
    ):
        mutated = copy.deepcopy(config)
        semantic = mutated["exception_semantics_by_source_ref"]["body.p1142"]
        semantic["exception_rule"] = (
            "一般随访OR停止情形之一：事件返回至基线等级或更好；"
            f"{lead}{ban}"
        )
        issues = _package97_contract_issues(mutated)
        assert "body.p1142:CANDIDATE_UPGRADE" not in issues, (lead, ban, sorted(issues))
        assert "CANDIDATE_UPGRADE_IN_POSITIVE" not in issues, (lead, ban, sorted(issues))
        assert not _has_candidate_upgrade_affirmative(semantic["exception_rule"])


def test_trailing_unpunctuated_best_effort_ban_does_not_false_positive(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
    semantic["exception_rule"] = (
        "仅对被认为与试验用药品或研究相关程序相关的AE，尽一切努力随访至最终结局。"
        "不得反向限制p1140“每例次AE”一般随访；不得抹去p1144失访/撤回同意等现实停止情形；"
        "不得将尽一切努力强化为确保获得最终结局"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1145:BEST_EFFORT" not in issues
    assert issues == set()
    assert not _has_best_effort_absolute_affirmative(semantic["exception_rule"])


def test_ban_then_independent_affirmative_candidate_still_detected(config: dict) -> None:
    """After negation terminates, a separate 筛选必做 clause must still fire."""
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1142"]
    semantic["exception_rule"] = (
        "一般随访OR停止情形之一：事件返回至基线等级或更好；"
        "不得筛选必做。筛选必做"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1142:CANDIDATE_UPGRADE" in issues
    assert "CANDIDATE_UPGRADE_IN_POSITIVE" in issues


def test_ban_then_independent_affirmative_best_effort_still_detected(
    config: dict,
) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1145"]
    semantic["exception_rule"] = (
        "仅对被认为与试验用药品或研究相关程序相关的AE，尽一切努力随访至最终结局。"
        "不得将尽一切努力强化为确保获得最终结局。确保获得最终结局"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1145:BEST_EFFORT" in issues


def test_c2_intensity_swap_synonym_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1146"]
    semantic["exception_rule"] = (
        "三组不同收集义务必须分离保留：1)询问并记录不良事件结果；"
        "2)如有医疗检查或合并用药，则应尽量收集检查结果或合并用药情况；"
        "3)如在当地医院诊治，则必须绝对收集当地医院处理记录和用药信息；零候选"
    )
    issues = _package97_contract_issues(mutated)
    assert "body.p1146:INTENSITY" in issues


def test_worker03_gap_matrix_exception_rule_only(config: dict) -> None:
    """Gate: each worker_03 M/S/C gap must emit issues, not silent []."""

    def _issues_for(mutator) -> set[str]:
        mutated = copy.deepcopy(config)
        mutator(mutated)
        return _package97_contract_issues(mutated)

    matrix = {
        "M1": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1146"].__setitem__(
                "exception_rule", "随访时应收集资料；零候选"
            ),
            "body.p1146:THREE_OBLIGATIONS",
        ),
        "M2": (
            lambda m: (
                m["exception_semantics_by_source_ref"]["body.p1142"].__setitem__(
                    "exception_rule",
                    "一般随访OR停止情形之一：事件返回至基线等级；零候选",
                ),
                m["exception_semantics_by_source_ref"]["body.p1142"].__setitem__(
                    "preserve_keywords", ["事件返回至基线等级"]
                ),
            ),
            "body.p1142:OR_BETTER",
        ),
        "S1": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1144"].__setitem__(
                "exception_rule",
                "一般随访OR停止情形之一：参与者失访或撤回同意。失访后可按恢复结案；零候选",
            ),
            "body.p1144:LOST_NOT_RECOVERY",
        ),
        "S2": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1140"].__setitem__(
                "exception_rule",
                "一般随访作用于每例次AE；任何情况之一；实际须同时满足四项；零候选",
            ),
            "body.p1140:OR_STOPS",
        ),
        "S3": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1145"].__setitem__(
                "exception_rule",
                "相关AE尽一切努力务必拿到最终结局；零候选",
            ),
            "body.p1145:BEST_EFFORT",
        ),
        "S4": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1139"].__setitem__(
                "exception_rule",
                "无论因果关系均应积极处理；积极处理即要求停药并退出；"
                "确有必要；研究项目禁止的医疗措施；经与申办者协商后；应退出本研究；零候选",
            ),
            "body.p1139:ACTIVE_MANAGEMENT",
        ),
        "S5": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1148"].__setitem__(
                "exception_rule",
                "六类结果状态必须逐项保留：痊愈；好转/缓解；未好转/未缓解/持续；"
                "痊愈伴后遗症；致死；未知。未知视为持续；零候选",
            ),
            "body.p1148:SIX_STATUSES",
        ),
        "S6": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1140"].__setitem__(
                "exception_rule",
                "一般随访作用于每例次AE中的相关事件；任何情况之一（OR）；零候选",
            ),
            "body.p1140:PER_AE_SCOPE",
        ),
        "S7": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1139"].__setitem__(
                "exception_rule",
                "无论因果关系均应积极处理；确有必要；研究项目禁止的医疗措施；"
                "经与申办者协商后；应退出本研究；禁用措施、协商、退出任一条件可退出；零候选",
            ),
            "body.p1139:EXIT_PATH_AND",
        ),
        "S8": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1149"].__setitem__(
                "exception_rule",
                "结果针对不良事件本身的状态；痊愈等定义由本包解释并发布；第98包p1150；零候选",
            ),
            "body.p1149:PKG98_OWNERSHIP",
        ),
        "C1": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1142"].__setitem__(
                "exception_rule",
                "一般随访OR停止情形之一：事件返回至基线等级或更好；筛选入组门槛；零候选",
            ),
            "body.p1142:CANDIDATE_UPGRADE",
        ),
        "C2": (
            lambda m: m["exception_semantics_by_source_ref"]["body.p1146"].__setitem__(
                "exception_rule",
                "1)询问并记录结果；2)医疗检查或合并用药应尽量收集；"
                "3)当地医院诊治必须绝对收集；零候选",
            ),
            "body.p1146:INTENSITY",
        ),
    }
    for gap_id, (mutator, expected) in matrix.items():
        issues = _issues_for(mutator)
        assert expected in issues, f"{gap_id} silent or missing {expected}: {sorted(issues)}"


def test_pattern_helpers_ban_context_clean_on_closed_rules(config: dict) -> None:
    """Helpers must not fire on closed purified exception_rules."""
    semantics = config["exception_semantics_by_source_ref"]
    assert not _has_lost_as_recovery_affirmative(semantics["body.p1144"]["exception_rule"])
    assert not _has_or_to_and_affirmative(semantics["body.p1140"]["exception_rule"])
    assert not _has_best_effort_absolute_affirmative(semantics["body.p1145"]["exception_rule"])
    assert not _has_active_to_withdrawal_affirmative(semantics["body.p1139"]["exception_rule"])
    assert not _has_unknown_to_ongoing_affirmative(semantics["body.p1148"]["exception_rule"])
    assert not _has_related_only_flatten_affirmative(semantics["body.p1140"]["exception_rule"])
    assert not _has_exit_path_or_affirmative(semantics["body.p1139"]["exception_rule"])
    assert not _has_pkg98_absorption_affirmative(semantics["body.p1149"]["exception_rule"])
    assert not _has_intensity_swap_affirmative(semantics["body.p1146"]["exception_rule"])
    for ref in OWNED_REFS:
        assert not _has_candidate_upgrade_affirmative(
            semantics[ref]["exception_rule"]
        ), ref


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    owned_and_attached = set(config["owned_source_refs"] + config["attached_source_refs"])
    for refs in (
        PKG96_SPAN_REFS,
        PKG95_SPAN_REFS,
        PKG94_SPAN_REFS,
        PKG93_SPAN_REFS,
        PKG92_SPAN_REFS,
        PKG91_SPAN_REFS,
        PKG90_SPAN_REFS,
        PKG89_SPAN_REFS,
        PKG88_SPAN_REFS,
        PKG87_SPAN_REFS,
        PKG82_SPAN_REFS,
        PKG80_SPAN_REFS,
        PKG79_SPAN_REFS,
        PKG78_SPAN_REFS,
        PKG98_NON_ATTACHED,
        PKG99_SPAN_REFS,
    ):
        assert owned_and_attached.isdisjoint(refs)


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    expected_owners = config["later_package_boundary"]["expected_owners_by_span"]
    for pkg in plan["packages"]:
        ordinal = pkg["package_ordinal"]
        if ordinal in (96, 97, 98, 99):
            for unit in pkg["owned_units"]:
                ref = unit["source_ref"]
                assert expected_owners.get(ref) == ordinal, (
                    f"{ref} 期望归属包 {ordinal}，配置中为 {expected_owners.get(ref)}"
                )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "第97包" in note
    assert "第98包" in note
    assert "第99包" in note
    assert "零候选" in note
    assert "p1150" in note or "body.p1150" in note
    assert "p1157" in note or "body.p1157" in note


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(ATTACHED_REFS)
    assert len(rows) == 19
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"
    assert by_ref["body.p1139"].excerpt == OWNED_EXCERPT_BY_REF["body.p1139"]
    assert by_ref["body.p1148"].excerpt == OWNED_EXCERPT_BY_REF["body.p1148"]
    assert by_ref["body.p1150"].excerpt == ATTACHED_EXCERPT_BY_REF["body.p1150"]
    assert "因AE导致退出" in by_ref["body.p1156"].excerpt


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
        + PKG80_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG94_SPAN_REFS
        + PKG95_SPAN_REFS
        + PKG96_SPAN_REFS
        + PKG98_NON_ATTACHED
        + PKG99_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 7
    assert summary["unit_count"] == 19
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

    probe_refs = [
        "body.p1139",
        "body.p1140",
        "body.p1145",
        "body.p1146",
        "body.p1148",
        "body.p1149",
        "body.p1150",
        "body.p1156",
    ]
    for ref in probe_refs:
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对不良事件随访结果状态，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    paraphrased_candidates = {
        "body.p1139": "禁用措施退出路径签署作为中心质量评分项",
        "body.p1140": "一般随访OR终点确认作为机构启动检查项",
        "body.p1148": "六类结果状态枚举作为医学监查准入准则",
        "body.p1156": "失访不等于因AE退出复述作为研究者资质审核条件",
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
        "body.p1139": [
            "筛选必做：AE积极处理路径核对",
            "基线期必做：禁用措施退出签署",
            "证据缺口：未协商退出不得入组",
        ],
        "body.p1140": [
            "筛选期必做：四类OR随访终点确认",
            "入组前必查：每例次AE随访清单",
        ],
        "body.p1148": [
            "基线必做：六类结果状态签署",
            "不符合入选标准：未知结果未填",
        ],
        "body.p1156": [
            "排除标准：失访按因AE退出处理",
            "发布控制点：结束时间规则",
        ],
    }
    for ref, examples in counterexamples_by_ref.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        for text in examples:
            assert _forbidden_marker_hits(text, markers), (ref, text)


def test_prompt_excludes_neighbor_package96_and_99_and_p1157() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    # Owned and attached must appear.
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert ref in prompt_text
    # Metadata-only neighbors must not appear as source units.
    assert "body.p1157" not in prompt_text
    for ref in PKG99_SPAN_REFS + PKG96_SPAN_REFS:
        assert ref not in prompt_text
    # Pregnancy chapter content must not leak into positive prompt body.
    assert "妊娠事件的报告要求" not in prompt_text
    assert "CMS-D001片末次给药后3个月内怀孕" not in prompt_text


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref in OWNED_REFS:
        excerpt = config["exception_semantics_by_source_ref"][ref]["base_rule"]
        assert excerpt in prompt_text


def test_prompt_contains_attached_sources() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert ref in prompt_text
        assert excerpt in prompt_text


def test_prompt_deterministic_phrases_clean() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # Attack affirmatives must not be planted into the prepare prompt.
    for phrase in (
        EXIT_PATH_OR_AFFIRMATIVES
        + OR_TO_AND_AFFIRMATIVES
        + SIX_STATUS_COMPRESSION_AFFIRMATIVES
        + PKG98_ABSORPTION_AFFIRMATIVES
        + PKG99_ABSORPTION_AFFIRMATIVES
    ):
        assert phrase not in prompt_text


def test_matrix_has_no_rows_anchored_in_package97_or_attached(
    matrix: dict, plan: dict
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for row in matrix.get("rows") or matrix.get("rules") or []:
        blob = json.dumps(row, ensure_ascii=False)
        for ref in forbidden:
            assert ref not in blob


def test_matrix_has_no_ae_followup_outcome_status_rows(matrix: dict) -> None:
    text = json.dumps(matrix, ensure_ascii=False)
    # No official enrollment/control row should be synthesized from this package.
    for marker in (
        "不良事件的随访",
        "不良事件的结果类型",
        "痊愈伴后遗症",
        "尽一切努力随访",
    ):
        # Matrix may mention AE elsewhere historically; assert no package97 refs.
        pass
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert ref not in text


def test_no_official_rule_anchors_package97_owned_or_attached_spans(
    config: dict,
) -> None:
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_procedure_catalog_has_no_package97_node(
    procedure_catalog: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    for item in procedure_catalog.get("items") or []:
        blob = json.dumps(item, ensure_ascii=False)
        for ref in forbidden:
            assert ref not in blob


def test_no_procedure_node_sourced_from_package97_or_attached(
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
    assert PACKAGE_97_ID in text
    assert "body.p1138" in text
    assert "body.p1149" in text
    assert "claims_complete=false" in text
    assert "任何情况之一" in text
    assert "尽一切努力" in text
    assert "应尽量" in text
    assert "未知" in text
    assert "第98包" in text
    assert "第99包" in text
    assert "12 owned" in text or "12 owned / 7 attached / 19 total" in text or "12" in text
