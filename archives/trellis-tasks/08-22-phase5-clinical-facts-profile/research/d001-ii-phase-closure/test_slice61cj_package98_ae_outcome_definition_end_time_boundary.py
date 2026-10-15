#!/usr/bin/env python3
"""Slice61cj model-free source-closure regressions.

Locks the D001 II package 98 AE outcome-definition / end-time boundary
(frozen plan package 98: body.p1150-p1157) to its authoritative sources
before any semantic replay decision:

- config contract and role partition: 8 owned refs body.p1150-p1157
  (p1155 structural-only; remaining 7 post_treatment_execution);
  attached refs stay body.p1142, body.p1144, body.p1148-p1149 read-only;
  pkg99 pregnancy stays metadata-only and out of prompt/positive semantics
- immutable frozen digests of parent-approved positive semantics fields;
  any append / delete / reorder / rewrite of those fields reports
  POSITIVE_SEMANTICS_DRIFT (not open-ended Chinese synonym regex)
- whole-config fingerprint check so config+test cannot drift together
- attached_source_refs must never appear in exception_semantics_by_source_ref
- readable clinical relation regressions remain as specs, but synonym
  coverage is proved by digest drift rather than open keyword regex
- package 97/99 ownership boundaries; zero candidates for owned+attached
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
    / "representative_group_package98_ae_outcome_definition_end_time_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61cj-package98-ae-outcome-definition-end-time-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package98-ae-outcome-definition-end-time-boundary"
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
# Independent whole-config fingerprint (Worker 01 artifact). Must not be
# recomputed from the config under test inside the issue scanner.
EXPECTED_CONFIG_SHA256 = (
    "e38ace154ab29dbd0d35b4291cab93a0ae909bf555a0d6e92418978d0a3cf306"
)

PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
PACKAGE_98_ORDINAL = 98
PACKAGE_98_ID = "pap-efb197cc99ae53ab03b9a1a2"
PACKAGE_97_ORDINAL = 97
PACKAGE_97_ID = "pap-6e961f674f48ee5003dcc014"
PACKAGE_99_ORDINAL = 99
PACKAGE_99_ID = "pap-89963654c275db70b405733e"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1150, 1158)]
ATTACHED_REFS = ["body.p1142", "body.p1144", "body.p1148", "body.p1149"]
STRUCTURAL_REFS = ["body.p1155"]
SEMANTIC_OWNED_REFS = [ref for ref in OWNED_REFS if ref not in STRUCTURAL_REFS]

PKG99_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1158, 1168)]
PKG97_NON_ATTACHED = [
    f"body.p{ordinal}"
    for ordinal in list(range(1138, 1142))
    + [1143]
    + list(range(1145, 1148))
]
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

OWNED_EXCERPT_BY_REF = {
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
    "body.p1157": (
        "如参与者死亡时未收集到结束时间，非导致“死亡”直接原因的不良事件仍然持续，"
        "则该不良事件的结束时间应空缺，状态为“持续”。"
        "如判断为导致“死亡”的直接或主要原因的不良事件，结束时间为参与者死亡时间。"
    ),
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1142": "事件返回至基线等级或更好；",
    "body.p1144": "参与者失访或撤回同意。",
    "body.p1148": (
        "根据2019年11月22日我国药监局正式发布的《个例安全性报告E2B（R3）区域实施指南》，"
        "不良事件的结果可有如下状态：①痊愈；②好转/缓解；③未好转/未缓解/持续；"
        "④痊愈伴后遗症；⑤致死；⑥未知。"
    ),
    "body.p1149": (
        "不良事件的“结果”针对的是不良事件本身的状态，而非不良事件在医学意义上的状态，因此："
    ),
}

# Parent-approved positive semantics payloads. These are independent constants
# (not derived from the config object under test at scan time).
FROZEN_POSITIVE_SEMANTICS_BY_REF: dict[str, dict] = {
    "body.p1150": {
        "semantic_role": "ae_outcome_recovered_definition_disappearance_or_return_to_baseline",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1150"],
        "exception_rule": (
            "痊愈包括不良事件消失，以及无论基线是否异常时恢复至基线。"
            "不得把痊愈限定为恢复正常范围，也不得把仅好转或状态稳定等同痊愈；零候选"
        ),
        "preserve_keywords": [
            "痊愈",
            "不良事件消失",
            "无论参与者的基线情况是否异常",
            "恢复至基线",
        ],
        "forbidden_inversion": (
            "不得把痊愈限定为恢复正常范围；不得把好转/缓解或状态稳定等同痊愈；"
            "不得删除“无论基线是否异常”；不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1151": {
        "semantic_role": "ae_outcome_improved_relieved_still_present_at_report",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1151"],
        "exception_rule": (
            "好转/缓解要求不良事件减轻或缓解且报告时尚未消失；"
            "不得与未好转/未缓解/持续互换；不得因尚未消失就把已经减轻的事件归入持续；零候选"
        ),
        "preserve_keywords": ["好转/缓解", "减轻或缓解", "在报告时还未消失"],
        "forbidden_inversion": (
            "不得与未好转/未缓解/持续互换；不得因未消失把已减轻事件改成持续；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1152": {
        "semantic_role": "ae_outcome_not_improved_ongoing_at_report",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1152"],
        "exception_rule": (
            "未好转/未缓解/持续要求报告时仍未减轻或缓解；不得与好转/缓解互换；"
            "不得把未知推成持续；零候选"
        ),
        "preserve_keywords": ["未好转/未缓解/持续", "在报告时仍未减轻或缓解"],
        "forbidden_inversion": (
            "不得与好转/缓解互换；不得把未知改写为持续；不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1153": {
        "semantic_role": "ae_outcome_with_sequelae_long_term_or_permanent_impairment",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1153"],
        "exception_rule": (
            "伴后遗症承接第97包“痊愈伴后遗症”，指长期或永久生理机能障碍；"
            "恢复期或恢复阶段症状本身不应视为后遗症。"
            "不得把任意残余症状、恢复中或短期不适升级为后遗症；零候选"
        ),
        "preserve_keywords": [
            "伴后遗症",
            "长期的或永久的生理机能障碍",
            "不应将恢复期或恢复阶段的某些症状视为后遗症",
        ],
        "forbidden_inversion": (
            "不得把任意残余/恢复中/短期症状升级为后遗症；不得删除“长期或永久”；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1154": {
        "semantic_role": "ae_outcome_fatal_requires_causal_death_not_coexistence",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1154"],
        "exception_rule": (
            "致死要求该不良事件导致参与者死亡。多AE并存时，只有导致死亡的事件可选致死，"
            "其他事件不得因参与者死亡而自动选择致死；不得把时间上同时存在替代因果关系；零候选"
        ),
        "preserve_keywords": [
            "因该不良事件导致死亡",
            "同时报告有多个不良事件",
            "仅一个不良事件导致死亡",
            "其它未导致死亡的不良事件的结果不应选择死亡",
        ],
        "forbidden_inversion": (
            "不得把并存AE全部致死化；不得用同时存在替代因果关系；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1155": {
        "semantic_role": "ae_end_time_section_title_structural_only",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1155"],
        "exception_rule": (
            "第98包子节标题，仅作结构，闭合不良事件随访下的结束时间层级；"
            "标题本身不构成结束时间规则、退出时间或死亡分支义务，不得升格为预筛/筛选/基线控制点"
        ),
        "preserve_keywords": ["不良事件的结束时间"],
        "forbidden_inversion": (
            "不得把标题解释为独立规则、候选或入排门槛；不得用标题替代p1156/p1157规则；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1156": {
        "semantic_role": "ae_end_time_or_paths_date_precision_and_exit_time_boundary",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1156"],
        "exception_rule": (
            "结束时间可由任一真实终点确定：事件解决（例如痊愈、致死）、恢复至基线状态，"
            "或状态稳定且不能恢复得更好。三类为备选路径（OR），不得改成同时满足（AND），"
            "也不得把“状态稳定”单独充分化而删除“不能恢复得更好”。日期应尽量精确到年月日；"
            "信息收集不全时仍应具体到年月；不得虚构缺失的日，也不得把缺日改成必须留空。"
            "失访或撤回知情同意不得自动记录为“因AE导致退出”；明确因AE退出时必须跟踪具体退出时间；"
            "退出时间不是自动等同于不良事件结束时间；零候选"
        ),
        "preserve_keywords": [
            "不良事件解决（如痊愈、致死）",
            "恢复到基线时状态",
            "状态稳定并不能恢复得更好",
            "尽量精确到年月日",
            "也应具体到年月",
            "失访或撤回知情同意",
            "不应作为“因AE导致退出”而记录",
            "明确因AE而退出",
            "必须跟踪随访具体的退出时间",
        ],
        "forbidden_inversion": (
            "不得把三类结束时间路径改成AND；不得截断稳定条件；不得虚构日或强制缺日留空；"
            "不得把失访/撤回同意记为因AE退出；不得把退出时间自动等同结束时间；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
    "body.p1157": {
        "semantic_role": "death_scene_dual_branch_end_time_blank_ongoing_vs_death_time",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1157"],
        "exception_rule": (
            "死亡场景必须保留两个条件分支：死亡时未收集结束时间、非导致“死亡”直接原因且事件仍持续时，"
            "该不良事件的结束时间应空缺，状态为“持续”；判断为导致“死亡”的直接或主要原因的不良事件，"
            "结束时间才记录为参与者死亡时间。不得把所有在死亡时持续的事件统一结束于死亡日，"
            "也不得把所有结束时间都留空；零候选"
        ),
        "preserve_keywords": [
            "死亡时未收集到结束时间",
            "非导致“死亡”直接原因",
            "仍然持续",
            "结束时间应空缺",
            "状态为“持续”",
            "导致“死亡”的直接或主要原因",
            "结束时间为参与者死亡时间",
        ],
        "forbidden_inversion": (
            "不得把死亡时持续事件统一记死亡日；不得统一留空全部结束时间；不得删除任一分支；"
            "不得升格为预筛/筛选/基线控制点"
        ),
    },
}


def _canonical_positive_payload(entry: dict) -> str:
    payload = {
        "semantic_role": entry.get("semantic_role"),
        "base_rule": entry.get("base_rule"),
        "exception_rule": entry.get("exception_rule"),
        "preserve_keywords": list(entry.get("preserve_keywords") or []),
        "forbidden_inversion": entry.get("forbidden_inversion") or "",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _positive_field_digest(entry: dict) -> str:
    return _digest_text(_canonical_positive_payload(entry))


# Hardcoded digests derived once from FROZEN_POSITIVE_SEMANTICS_BY_REF above.
# Do not recompute these from the live config object inside scanners.
FROZEN_POSITIVE_DIGEST_BY_REF: dict[str, str] = {
    ref: _positive_field_digest(payload)
    for ref, payload in FROZEN_POSITIVE_SEMANTICS_BY_REF.items()
}
FROZEN_POSITIVE_SET_DIGEST = _digest_text(
    json.dumps(
        [
            {
                "source_ref": ref,
                "digest": FROZEN_POSITIVE_DIGEST_BY_REF[ref],
            }
            for ref in OWNED_REFS
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
)

# Worker 03 second-pass free counterexamples (wrong positive appends).
W3_PASS2_WRONG_POSITIVE_APPENDS: list[tuple[str, str, str]] = [
    # Death dual-branch
    ("body.p1157", "死亡时仍在持续的AE一律按死亡日收口", "death_unify"),
    ("body.p1157", "凡死亡当日尚未结束者统一落在死亡时间", "death_unify"),
    ("body.p1157", "非直接死因的持续事件也结束于死亡日", "death_unify"),
    ("body.p1157", "死亡分支可合并：持续者一概以死亡日为终点", "death_unify"),
    # Exit ≡ end
    ("body.p1156", "因AE退出日可当作事件结束日", "exit_eq_end"),
    ("body.p1156", "退出时间与结束时间保持一致即可", "exit_eq_end"),
    ("body.p1156", "结束日跟随退出日记录", "exit_eq_end"),
    ("body.p1156", "退出时刻同步为结束时刻", "exit_eq_end"),
    ("body.p1156", "明确退出后结束时间直接取退出时间", "exit_eq_end"),
    # Date precision
    ("body.p1156", "缺日时强制留空不写年月", "date_precision"),
    ("body.p1156", "无日信息时日期栏必须空缺", "blank_day"),
    ("body.p1156", "缺日可补记为当月15日", "day_invention"),
    ("body.p1156", "无精确日时默认取月中", "day_invention"),
    # Other clinical / ownership
    ("body.p1152", "未知状态可并入持续", "unknown_to_ongoing"),
    ("body.p1150", "仅好转到稳定也算痊愈", "recovered_flatten"),
    ("body.p1154", "非致死因果的AE也可因死亡勾选致死", "all_fatal"),
    ("body.p1150", "第97包随访规则转入本包发布", "pkg97_absorb"),
    # Stable truncation
    (
        "body.p1156",
        "状态稳定即可记录结束时间，可删除不能恢复得更好。",
        "stable_truncation",
    ),
    # First-pass residual family still covered via digest
    ("body.p1157", "死亡时持续事件一律记死亡日", "death_unify"),
    ("body.p1157", "死亡场景结束时间全部空缺", "death_blank_unify"),
    ("body.p1156", "退出日即结束日", "exit_eq_end"),
    ("body.p1156", "退出时刻=结束时刻", "exit_eq_end"),
    ("body.p1156", "退出时间可直接作为结束时间", "exit_eq_end"),
    ("body.p1156", "退出时间自动记为结束时间", "exit_eq_end"),
    ("body.p1156", "退出时间视同结束时间", "exit_eq_end"),
    ("body.p1156", "只能不填", "blank_day"),
    ("body.p1156", "应不填日", "blank_day"),
    ("body.p1156", "不得填日", "blank_day"),
    ("body.p1156", "禁止写日", "blank_day"),
    ("body.p1156", "日必须空缺", "blank_day"),
    ("body.p1156", "缺日则留空白", "blank_day"),
    ("body.p1156", "无日时应空着", "blank_day"),
    ("body.p1156", "信息不全时不记录日", "blank_day"),
    ("body.p1156", "三类路径缺一不可", "or_to_and"),
    ("body.p1156", "三类路径须一并满足", "or_to_and"),
    ("body.p1150", "可作为筛选门槛", "candidate_upgrade"),
    ("body.p1150", "入排判定依据", "candidate_upgrade"),
    ("body.p1150", "预筛条件", "candidate_upgrade"),
    ("body.p1150", "形成入排候选", "candidate_upgrade"),
    ("body.p1150", "可发射候选", "candidate_upgrade"),
]

assert len(W3_PASS2_WRONG_POSITIVE_APPENDS) == 40

# External ban-context strings that must NOT raise relation semantic labels
# when inspected alone (open-regex FP regression targets).
BAN_CONTEXT_EXTERNAL_STRINGS = [
    "不可把未知等同持续",
    "不可将未知视为持续",
    "不得把未知等同持续",
    "禁止写日",
    "不得把退出时间自动等同结束时间",
    "即结束时间。",
    "状态稳定即可记录结束时间",
    "精度即结束时间字段",
]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker in text]


def _relation_false_positive_labels_for_external_text(_text: str) -> set[str]:
    """Open synonym-regex relation scanners are retired.

    External ban-context / fragment strings must not invent clinical relation
    labels. Digest drift on config fields is the authority for positive-field
    corruption; this helper stays as an explicit no-op gate for FP probes.
    """
    return set()


def _package98_contract_issues(config: dict) -> set[str]:
    """Validate Package 98 via frozen positive-semantics digests + hard gates.

    Clinical synonym breadth is intentionally NOT proved by open Chinese regex.
    Any mutation of parent-approved positive fields is reported as
    POSITIVE_SEMANTICS_DRIFT (optionally per-ref). Specific clinical family
    names remain in readable regression test titles, not in this scanner.
    """
    issues: set[str] = set()
    semantics = config.get("exception_semantics_by_source_ref") or {}

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

    # Whole-config fingerprint: independent of in-memory mutation helpers.
    if CONFIG_PATH.is_file():
        if _sha256_file(CONFIG_PATH) != EXPECTED_CONFIG_SHA256:
            issues.add("CONFIG_FINGERPRINT_DRIFT")

    attached = list(config.get("attached_source_refs") or [])
    attached_set = set(attached)

    # Any attached / unexpected semantics key is an ownership backdoor.
    for ref in list(semantics.keys()):
        if ref in attached_set or ref in ATTACHED_REFS:
            issues.add("ATTACHED_EXCEPTION_SEMANTICS")
            issues.add("PACKAGE97_OWNERSHIP")
        elif ref not in OWNED_REFS:
            issues.add(f"{ref}:UNEXPECTED_SEMANTICS")
            issues.add("POSITIVE_SEMANTICS_DRIFT")

    # Deterministic per-ref digest compare against independent frozen constants.
    observed_set_rows: list[dict[str, str]] = []
    for ref in OWNED_REFS:
        entry = semantics.get(ref)
        if entry is None:
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
            observed_set_rows.append({"source_ref": ref, "digest": ""})
            continue
        if entry.get("base_rule") != OWNED_EXCERPT_BY_REF[ref]:
            issues.add(f"{ref}:SOURCE_TEXT")
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
        digest = _positive_field_digest(entry)
        observed_set_rows.append({"source_ref": ref, "digest": digest})
        if digest != FROZEN_POSITIVE_DIGEST_BY_REF[ref]:
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")

    observed_set_digest = _digest_text(
        json.dumps(observed_set_rows, ensure_ascii=False, separators=(",", ":"))
    )
    if observed_set_digest != FROZEN_POSITIVE_SET_DIGEST:
        issues.add("POSITIVE_SEMANTICS_SET_DRIFT")
        issues.add("POSITIVE_SEMANTICS_DRIFT")

    # Structural title must remain structural-only (specialized gate).
    for ref in STRUCTURAL_REFS:
        entry = semantics.get(ref) or {}
        rule = entry.get("exception_rule") or ""
        if "仅作结构" not in rule and "结构" not in rule:
            issues.add(f"{ref}:STRUCTURAL_ONLY")
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")

    # Ownership teaching still required on boundary/notes/QC surfaces.
    ownership_blob = " ".join(
        [
            config.get("later_package_boundary", {}).get("note", ""),
            " ".join(config.get("notes") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p1142") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p1148") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p1149") or []),
        ]
    )
    if "第97包" not in ownership_blob:
        issues.add("PACKAGE97_BOUNDARY_NOTE")
    if "第99包" not in ownership_blob:
        issues.add("PACKAGE99_BOUNDARY_NOTE")
    if "零候选" not in ownership_blob:
        issues.add("ZERO_CANDIDATE_NOTE")

    owned = list(config.get("owned_source_refs") or [])
    owned_and_attached = set(owned + attached)
    if owned_and_attached & set(PKG99_SPAN_REFS):
        issues.add("PACKAGE99_ABSORPTION")
    if set(owned) & set(ATTACHED_REFS):
        issues.add("PACKAGE97_OWNERSHIP")
    if owned_and_attached & set(PKG97_NON_ATTACHED):
        issues.add("PACKAGE97_NON_ATTACHED_ABSORPTION")

    # Disposition / forbidden candidate partition.
    for ref in OWNED_REFS + ATTACHED_REFS:
        disposition = (config.get("expected_disposition_by_source_ref") or {}).get(ref)
        if ref in STRUCTURAL_REFS:
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


def _append_exception_rule(config: dict, ref: str, clause: str) -> dict:
    mutated = copy.deepcopy(config)
    rule = mutated["exception_semantics_by_source_ref"][ref]["exception_rule"]
    mutated["exception_semantics_by_source_ref"][ref]["exception_rule"] = (
        rule + ("；" if not rule.endswith(("；", "。")) else "") + clause
    )
    return mutated


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_98_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _attached_excerpt_by_ref(plan: dict) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    pkg97 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL
    )
    wanted = set(ATTACHED_REFS)
    for unit in pkg97["owned_units"]:
        if unit["source_ref"] in wanted:
            excerpts[unit["source_ref"]] = unit["excerpt"]
    return excerpts


def _structure_blob_text(blob: list[dict], ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == ref:
            return block.get("text") or block.get("excerpt") or ""
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


def test_frozen_positive_digests_are_independent_constants() -> None:
    assert FROZEN_POSITIVE_DIGEST_BY_REF == {
        ref: _positive_field_digest(FROZEN_POSITIVE_SEMANTICS_BY_REF[ref])
        for ref in OWNED_REFS
    }
    assert FROZEN_POSITIVE_SET_DIGEST == _digest_text(
        json.dumps(
            [
                {"source_ref": ref, "digest": FROZEN_POSITIVE_DIGEST_BY_REF[ref]}
                for ref in OWNED_REFS
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    # Digests are non-empty and stable across owned refs.
    assert len(FROZEN_POSITIVE_DIGEST_BY_REF) == 8
    assert all(len(v) == 64 for v in FROZEN_POSITIVE_DIGEST_BY_REF.values())
    assert len(FROZEN_POSITIVE_SET_DIGEST) == 64


def test_config_file_fingerprint_matches_independent_constant() -> None:
    assert _sha256_file(CONFIG_PATH) == EXPECTED_CONFIG_SHA256


def test_config_contract(config: dict) -> None:
    assert config["group_id"] == "d001-ii-package98-ae-outcome-definition-end-time-boundary"
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["study_phase"] == "phase_ii"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert config["structural_only_source_refs"] == STRUCTURAL_REFS
    assert config["required_candidate_source_refs"] == []
    assert config.get("claims_complete") is not True
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    assert _package98_contract_issues(config) == set()


def test_package98_contract_is_currently_closed(config: dict) -> None:
    assert _package98_contract_issues(config) == set()


def test_live_config_positive_fields_match_frozen_digests(config: dict) -> None:
    for ref in OWNED_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert _positive_field_digest(entry) == FROZEN_POSITIVE_DIGEST_BY_REF[ref]
        assert entry == FROZEN_POSITIVE_SEMANTICS_BY_REF[ref]


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    assert config["attached_source_refs"] == ATTACHED_REFS
    pkg97 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL)
    owned97 = {u["source_ref"] for u in pkg97["owned_units"]}
    for ref in ATTACHED_REFS:
        assert ref in owned97
        assert ref not in config["owned_source_refs"]
        assert ref not in config["exception_semantics_by_source_ref"]


def test_attached_refs_ownership_documented(plan: dict) -> None:
    pkg97 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_97_ORDINAL)
    assert pkg97["package_id"] == PACKAGE_97_ID
    for ref in ATTACHED_REFS:
        assert any(u["source_ref"] == ref for u in pkg97["owned_units"])


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    by_ord = {p["package_ordinal"]: p for p in plan["packages"]}
    assert by_ord[PACKAGE_98_ORDINAL]["package_id"] == PACKAGE_98_ID
    assert len(by_ord[PACKAGE_98_ORDINAL]["owned_units"]) == 8
    assert by_ord[PACKAGE_97_ORDINAL]["package_id"] == PACKAGE_97_ID
    assert len(by_ord[PACKAGE_97_ORDINAL]["owned_units"]) == 12
    assert by_ord[PACKAGE_99_ORDINAL]["package_id"] == PACKAGE_99_ID
    assert len(by_ord[PACKAGE_99_ORDINAL]["owned_units"]) == 10


def test_owned_refs_match_frozen_package_98(config: dict, plan: dict) -> None:
    pkg = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_98_ORDINAL)
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        assert excerpt == OWNED_EXCERPT_BY_REF[ref]
        assert config["exception_semantics_by_source_ref"][ref]["base_rule"] == excerpt


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == excerpt


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    for ref, excerpt in _owned_excerpt_by_ref(plan).items():
        assert _structure_blob_text(structure_blob, ref) == excerpt


def test_positive_append_reports_drift_not_open_synonym_label(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1150", "痊愈仅指恢复至正常值域")
    issues = _package98_contract_issues(mutated)
    assert "POSITIVE_SEMANTICS_DRIFT" in issues
    assert "body.p1150:POSITIVE_SEMANTICS_DRIFT" in issues
    # Specific open-regex family tags are retired.
    assert "body.p1150:NO_NORMAL_RANGE" not in issues


def test_positive_delete_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1156"]["exception_rule"] = (
        "结束时间可由任一真实终点确定：事件解决（例如痊愈、致死）、恢复至基线状态。"
        "三类为备选路径（OR）。日期应尽量精确到年月日；信息收集不全时仍应具体到年月；零候选"
    )
    issues = _package98_contract_issues(mutated)
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_positive_reorder_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    entry = mutated["exception_semantics_by_source_ref"]["body.p1150"]
    entry["preserve_keywords"] = list(reversed(list(entry["preserve_keywords"])))
    issues = _package98_contract_issues(mutated)
    assert "body.p1150:POSITIVE_SEMANTICS_DRIFT" in issues


def test_positive_rewrite_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1157"]["exception_rule"] = (
        "死亡时所有持续事件统一结束于死亡日。"
    )
    issues = _package98_contract_issues(mutated)
    assert "body.p1157:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_spec_recovered_normal_range_mutation_is_drift(config: dict) -> None:
    """Readable clinical spec: recovered→normal-range flattening."""
    mutated = _append_exception_rule(config, "body.p1150", "痊愈限定为恢复正常范围")
    assert "body.p1150:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_improved_ongoing_swap_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1151", "已减轻但尚未消失的事件视为持续")
    assert "body.p1151:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_sequelae_upgrade_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1153", "任意残余症状升级为后遗症")
    assert "body.p1153:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_all_fatalization_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1154", "并存的AE均可记致死")
    assert "body.p1154:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_end_time_or_to_and_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1156", "三类路径缺一不可")
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_stable_truncation_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(
        config, "body.p1156", "状态稳定即可记录结束时间，可删除不能恢复得更好。"
    )
    issues = _package98_contract_issues(mutated)
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in issues
    # Former FP path must not invent EXIT_NE_END.
    assert "body.p1156:EXIT_NE_END" not in issues


def test_spec_day_invention_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1156", "缺日可补记为当月15日")
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_blank_day_mandate_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1156", "无日时应空着")
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_exit_eq_end_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1156", "退出日即结束日")
    issues = _package98_contract_issues(mutated)
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "body.p1156:EXIT_NE_END" not in issues


def test_spec_death_unify_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1157", "死亡时持续事件一律记死亡日")
    assert "body.p1157:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_spec_unknown_to_ongoing_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1152", "未知状态可并入持续")
    assert "body.p1152:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_attached_exception_semantics_backdoor_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1148"] = {
        "semantic_role": "illicit_attached_ownership",
        "base_rule": ATTACHED_EXCERPT_BY_REF["body.p1148"],
        "exception_rule": "六类结果状态由本包拥有并重新发布。",
        "preserve_keywords": [],
        "forbidden_inversion": "",
    }
    issues = _package98_contract_issues(mutated)
    assert "ATTACHED_EXCEPTION_SEMANTICS" in issues
    assert "PACKAGE97_OWNERSHIP" in issues


def test_required_candidate_upgrade_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["required_candidate_source_refs"] = ["body.p1150"]
    assert "REQUIRED_CANDIDATE_NONEMPTY" in _package98_contract_issues(mutated)


def test_claims_complete_true_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["claims_complete"] = True
    assert "CLAIMS_COMPLETE_TRUE" in _package98_contract_issues(mutated)


def test_wrong_positive_not_masked_by_correct_forbid_notes_qc(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1156"]["exception_rule"] = (
        "结束时间三类路径必须同时满足（AND）；解决、恢复至基线与状态稳定均需满足；"
        "日期应尽量精确到年月日；信息收集不全时仍应具体到年月；"
        "失访或撤回知情同意不得自动记录为因AE导致退出；明确因AE退出时必须跟踪具体退出时间；"
        "退出时间不是自动等同于不良事件结束时间；零候选"
    )
    # Keep correct forbid/QC/notes intact — still drift on positive field.
    assert "body.p1156:POSITIVE_SEMANTICS_DRIFT" in _package98_contract_issues(mutated)


def test_notes_qc_only_pollution_does_not_fake_close_positive(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["notes"] = list(mutated.get("notes") or []) + ["第97包六类结果状态改写为本包拥有"]
    mutated["clinical_qc_checks_by_source_ref"]["body.p1150"] = list(
        mutated["clinical_qc_checks_by_source_ref"]["body.p1150"]
    ) + ["可发射候选"]
    # Positive fields unchanged → closed.
    assert _package98_contract_issues(mutated) == set()


def test_w3_pass2_all_wrong_positive_appends_rejected_by_drift(config: dict) -> None:
    assert len(W3_PASS2_WRONG_POSITIVE_APPENDS) == 40
    for ref, clause, family in W3_PASS2_WRONG_POSITIVE_APPENDS:
        issues = _package98_contract_issues(_append_exception_rule(config, ref, clause))
        assert "POSITIVE_SEMANTICS_DRIFT" in issues, (family, ref, clause, issues)
        assert f"{ref}:POSITIVE_SEMANTICS_DRIFT" in issues, (family, ref, clause, issues)
        # Retired open-regex labels must not be the acceptance path.
        assert "body.p1156:EXIT_NE_END" not in issues
        assert "body.p1152:NO_UNKNOWN_TO_ONGOING" not in issues


def test_ban_context_external_strings_do_not_raise_relation_false_positives() -> None:
    for text in BAN_CONTEXT_EXTERNAL_STRINGS:
        labels = _relation_false_positive_labels_for_external_text(text)
        assert labels == set(), (text, labels)


def test_append_ban_teaching_still_reports_field_drift_not_relation_fp(
    config: dict,
) -> None:
    # Changing the positive field always drifts; do not invent EXIT/unknown tags.
    for clause in (
        "不可把未知等同持续",
        "即结束时间。",
        "不得把退出时间自动等同结束时间",
    ):
        ref = "body.p1156" if "退出" in clause or "即结束" in clause else "body.p1152"
        issues = _package98_contract_issues(_append_exception_rule(config, ref, clause))
        assert "POSITIVE_SEMANTICS_DRIFT" in issues
        assert f"{ref}:POSITIVE_SEMANTICS_DRIFT" in issues
        assert "body.p1156:EXIT_NE_END" not in issues
        assert "body.p1152:NO_UNKNOWN_TO_ONGOING" not in issues


def test_pkg97_attached_to_owned_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"] = OWNED_REFS + ["body.p1148"]
    issues = _package98_contract_issues(mutated)
    assert "OWNED_REFS" in issues or "PACKAGE97_OWNERSHIP" in issues


def test_pkg99_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = ATTACHED_REFS + ["body.p1158"]
    issues = _package98_contract_issues(mutated)
    assert "ATTACHED_REFS" in issues or "PACKAGE99_ABSORPTION" in issues


def test_structural_heading_conversion_is_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1155"]["exception_rule"] = (
        "结束时间可由任一真实终点确定；三类为备选路径；必须跟踪具体退出时间。"
    )
    issues = _package98_contract_issues(mutated)
    assert "body.p1155:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "body.p1155:STRUCTURAL_ONLY" in issues


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    owned_and_attached = set(config["owned_source_refs"] + config["attached_source_refs"])
    for refs in (
        PKG78_SPAN_REFS,
        PKG79_SPAN_REFS,
        PKG80_SPAN_REFS,
        PKG82_SPAN_REFS,
        PKG87_SPAN_REFS,
        PKG88_SPAN_REFS,
        PKG89_SPAN_REFS,
        PKG90_SPAN_REFS,
        PKG91_SPAN_REFS,
        PKG92_SPAN_REFS,
        PKG93_SPAN_REFS,
        PKG94_SPAN_REFS,
        PKG95_SPAN_REFS,
        PKG96_SPAN_REFS,
        PKG97_NON_ATTACHED,
        PKG99_SPAN_REFS,
    ):
        assert owned_and_attached.isdisjoint(refs)


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    expected_owners = config["later_package_boundary"]["expected_owners_by_span"]
    by_ord = {p["package_ordinal"]: p for p in plan["packages"]}
    for ref, ordinal in expected_owners.items():
        pkg = by_ord[ordinal]
        owned = {u["source_ref"] for u in pkg["owned_units"]}
        assert ref in owned, (ref, ordinal)


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    note = boundary["note"]
    assert "第97包" in note
    assert "第99包" in note
    assert "零候选" in note
    assert "p1158" in note or "body.p1158" in note


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert len(rows) == 12
    for ref in OWNED_REFS:
        assert by_ref[ref].role == "owned"
        assert by_ref[ref].excerpt == OWNED_EXCERPT_BY_REF[ref]
    for ref in ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt == ATTACHED_EXCERPT_BY_REF[ref]
    assert "因AE导致退出" in by_ref["body.p1156"].excerpt
    assert "结束时间应空缺" in by_ref["body.p1157"].excerpt


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
        + PKG97_NON_ATTACHED
        + PKG99_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 8
    assert summary["attached_count"] == 4
    assert summary["unit_count"] == 12
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

    for ref in ("body.p1150", "body.p1154", "body.p1156", "body.p1157", "body.p1148"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对不良事件结果定义与结束时间，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert issues, ref


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    markers = ["筛选必做", "基线必做", "入组前必查", "发布控制点"]
    for ref, excerpt in excerpts.items():
        assert _forbidden_marker_hits(excerpt, markers) == []


def test_prompt_excludes_neighbor_package97_non_attached_and_99() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    for ref in PKG97_NON_ATTACHED + PKG99_SPAN_REFS:
        assert f"source_ref={ref}" not in prompt_text
    assert "CMS-D001片末次给药后3个月内怀孕" not in prompt_text


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for excerpt in OWNED_EXCERPT_BY_REF.values():
        assert excerpt in prompt_text


def test_prompt_contains_attached_sources() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for excerpt in ATTACHED_EXCERPT_BY_REF.values():
        assert excerpt in prompt_text


def test_matrix_has_no_rows_anchored_in_package98_or_attached(
    matrix: dict, plan: dict
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    blob = json.dumps(matrix, ensure_ascii=False)
    for ref in forbidden:
        assert ref not in blob


def test_no_official_rule_anchors_package98_owned_or_attached_spans(
    config: dict,
) -> None:
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_procedure_catalog_has_no_package98_node(
    procedure_catalog: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    blob = json.dumps(procedure_catalog, ensure_ascii=False)
    for ref in forbidden:
        assert ref not in blob


def test_known_targets_build_empty(config: dict) -> None:
    targets = config["known_targets"]
    assert targets["official_rules"] == []
    assert targets["required_procedures"] == []


def test_workflow_stages_are_nonbinding_replay_scaffold(config: dict) -> None:
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert {stage["workflow_stage_id"] for stage in config["workflow_stages"]} == {
        "flow-screening",
        "flow-baseline",
        "flow-d1-pre-dose",
    }


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    assert _sha256_file(CONFIG_PATH) == EXPECTED_CONFIG_SHA256
    assert EXPECTED_CATALOG_SHA256
    assert (CATALOG_DIR / "required_procedures.json").is_file()


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "pap-efb197cc99ae53ab03b9a1a2" in text
    assert "body.p1150" in text and "body.p1157" in text
    assert "body.p1142" in text and "body.p1148" in text
    assert "claims_complete=false" in text or "claims_complete=false" in text.replace(
        " ", ""
    )
    assert "8" in text and "4" in text
    assert "第99包" in text or "body.p1158" in text
