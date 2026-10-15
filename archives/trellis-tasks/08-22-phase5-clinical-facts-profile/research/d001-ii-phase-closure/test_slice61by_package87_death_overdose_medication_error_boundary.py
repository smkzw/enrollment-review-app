#!/usr/bin/env python3
"""Slice61by model-free source-closure regressions.

Locks the D001 II package 87 death / drug overdose / administration
error recording-and-reporting boundary (frozen plan package 87:
死亡、药物过量与给药错误记录规则, body.p1074-p1083) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 87 (4 structural headings + 6 semantic
  units); attached refs stay read-only
- structural units (p1074/p1077/p1080/p1083) stay structural only; six
  semantic units keep post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- p1075 keeps: all death events in the protocol AE collection period are
  recorded on the eCRF adverse event page and immediately reported to the
  sponsor regardless of relationship to study drug; the 24-hour refinement
  comes read-only from package 93 p1103-p1104 and never becomes re-ownership
  of the generic reporting process
- p1076 keeps the death-outcome semantics: death is the OUTCOME of an event,
  never an independent event; the event/circumstance causing or contributing
  to the fatal outcome is recorded as a single medical concept; "通常，只报告
  1个" stays a default, never an absolute "only one in any case"; unknown
  cause is recorded as "不明原因死亡" and replaced by the determined cause
  when later available (semantic replacement, not physical deletion of
  history); "猝死" is only usable combined with a presumed cause (e.g.
  "心源性猝死"), never rewritten as blanket ban or blanket allowance
- p1078 keeps the overdose definition covering BOTH accidental and
  intentional use with the core judgment CMS-D001片用量高于指定研究剂量;
  never rewritten to only-accidental, only-intentional, an unwritten
  multiple threshold, or any deviation from plan
- p1079 keeps the administration-error definition (any unintended medication
  situation in drug dispensing or administration) with the explicit
  exclusion that participant missed or off-plan use is NOT an administration
  error; the exclusion is never re-included and never extrapolated to
  automatically being an AE, protocol deviation, or enrollment failure
- p1081-p1082 keep the PARALLEL dual-table recording logic: any study-drug
  overdose or study-treatment administration error is noted on the eCRF
  study-drug administration log; the "药物过量/给药错误" label itself is not
  an AE and all related AEs are recorded on the eCRF AE page; log-only
  recording is retained when no related AE exists, AE pages are never
  dropped when related AEs exist, and the label itself is never used as an
  AE term; the two tables are never rewritten as mutually exclusive
- package 86 (p1067-p1073 DILI logic) enters only as read-only ownership
  metadata, never into semantics or prompt; package 88+ (severity
  grading/CTCAE/table 8, causality, expectancy) and the rest of package 93
  (p1105/p1106 and the generic reporting/follow-up flow) are never absorbed
- official matrix keeps zero rows anchored in p1074-p1083 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no p1074-p1083 spans
- immutable source fingerprints and checklist freeze

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

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
    / "representative_group_package87_death_overdose_medication_error_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61by-package87-death-overdose-medication-error-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package87-death-overdose-medication-error-boundary"
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
PACKAGE_87_ORDINAL = 87
PACKAGE_87_ID = "pap-2479acb2cc6c17a411ff2a3e"
PACKAGE_86_ORDINAL = 86
PACKAGE_86_ID = "pap-d27cb33cf06d737190efa6c7"
PACKAGE_88_ORDINAL = 88
PACKAGE_93_ORDINAL = 93
PACKAGE_93_ID = "pap-2815c9e5b343ac6d7663ae21"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]

# 结构单元：死亡/与药物过量或给药错误相关的不良事件/记录要求/不良事件的评估
# 标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1074", "body.p1077", "body.p1080", "body.p1083"]
# 语义单元：死亡记录与报告、死亡结果与事件术语、过量定义、给药错误定义、
# 双表并行记录逻辑，保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = [
    "body.p1075",
    "body.p1076",
    "body.p1078",
    "body.p1079",
    "body.p1081",
    "body.p1082",
]

# 只读闭包（9）：第78包SAE定义与死亡作为SAE结果（3）、第80包AE收集期/
# 全量记录/单一事件项一术语（3）、流程锚点（1）、第93包死亡事件报告时限
# 细化（2，仅p1103-p1104，不得吸收第93包通用报告流程）
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997", "body.p998"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1024", "body.p1026"]
FLOW_ANCHOR_REFS = ["body.p340"]
DEATH_REPORT_REFINEMENT_REFS = ["body.p1103", "body.p1104"]
ATTACHED_REFS = (
    SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
    + DEATH_REPORT_REFINEMENT_REFS
)

# 相邻包所有权元数据：第86包（p1067-p1073）、第88包（p1084-p1086）、
# 第90包（p1087-p1097）、第92包（p1098-p1101）、第93包（p1102-p1112）
# 均不得被本包拥有或处置；第89/91包为表8分级表（t13）与因果判定表（t14）
PKG86_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1067, 1074)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG93_NON_ATTACHED_REFS = [ref for ref in PKG93_SPAN_REFS if ref not in DEATH_REPORT_REFINEMENT_REFS]

# 各语义单元的语义结构、时间边界与限定要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1075": {
        "base_rule": "在方案规定的不良事件收集期内发生的所有死亡事件，无论与研究药物的关系如何，必须记录在eCRF不良事件上，并立即报告给申办者。",
        "exception_rule": "方案规定的AE收集期内发生的所有死亡事件均须记录在eCRF不良事件页并立即报告申办者，与研究药物关系无关；'立即报告'由第93包p1103-p1104'获知后24小时（含）内'只读细化，本包不重新拥有通用报告流程",
        "preserve_keywords": ["所有死亡事件", "无论与研究药物的关系如何", "必须记录在eCRF不良事件上", "立即报告给申办者"],
    },
    "body.p1076": {
        "base_rule": "死亡应被视为事件的结果，而非单独的事件。导致或促成致死性结果的事件或情况应在eCRF不良事件上记录为单一医学概念。通常，只报告1个这样的事件或情况。如果死因不明且不能在报告当时查明，则应在eCRF不良事件上记录“不明原因死亡”。如果死因稍后可获得，应将“不明原因死亡”替换为确定的死因。不应使用术语“猝死”，除非与推测的死因（如“心源性猝死”）结合使用。",
        "exception_rule": "死亡是事件的结果，不是独立事件；导致或促成致死性结果的事件或情况以单一医学概念记录在eCRF不良事件页；'通常只报告1个'是默认情形，不是任何情况下只能记录一个；死因不明且无法查明时记录'不明原因死亡'，后来获得死因时替换为确定死因，不是物理删除历史记录；'猝死'只有与推测死因（如'心源性猝死'）结合使用",
        "preserve_keywords": ["事件的结果", "而非单独的事件", "单一医学概念", "通常，只报告1个", "不明原因死亡", "替换为确定的死因", "猝死", "推测的死因", "心源性猝死"],
    },
    "body.p1078": {
        "base_rule": "药物过量是指意外或故意使用的CMS-D001片用量高于指定的研究剂量。",
        "exception_rule": "药物过量定义同时覆盖意外和故意使用，判断核心是CMS-D001片用量高于指定研究剂量；不得改写为只有意外、只有故意、达到某个未写明倍数或只要偏离计划即过量",
        "preserve_keywords": ["意外或故意", "CMS-D001片用量高于指定的研究剂量"],
    },
    "body.p1079": {
        "base_rule": "给药错误指药物分发或给药中的任何非预期用药情况，参与者漏用或未按计划使用不被视为给药错误。",
        "exception_rule": "给药错误是药物分发或给药中的任何非预期用药情况；参与者漏用或未按计划使用明确排除在给药错误之外，不得重新纳入",
        "preserve_keywords": ["药物分发或给药中的任何非预期用药情况", "漏用或未按计划使用", "不被视为给药错误"],
    },
    "body.p1081": {
        "base_rule": "应在eCRF研究药物给药表上注明任何研究药物过量或研究治疗给药错误的事件。",
        "exception_rule": "任何研究药物过量或研究治疗给药错误都应在eCRF研究药物给药表注明；这是双表并行记录逻辑的给药表一侧，没有关联AE时仍保留给药表记录",
        "preserve_keywords": ["eCRF研究药物给药表上注明", "任何研究药物过量", "研究治疗给药错误"],
    },
    "body.p1082": {
        "base_rule": "“药物过量/给药错误”本身不属于不良事件，但与药物过量或给药错误相关的所有不良事件应记录在eCRF不良事件上。",
        "exception_rule": "双表并行逻辑：'药物过量/给药错误'标签本身不是AE；与其相关的所有AE另行记录在eCRF不良事件页；没有关联AE时仍保留给药表记录；有关联AE时不能只记给药表而漏记AE，也不能把过量/错误标签本身当成AE术语",
        "preserve_keywords": ["本身不属于不良事件", "与药物过量或给药错误相关的所有不良事件", "记录在eCRF不良事件上"],
    },
}

# 交叉验证锚点（只读闭包）
PKG87_DEATH_HEADING_REF = "body.p1074"
PKG87_DEATH_RECORDING_REF = "body.p1075"
PKG87_DEATH_OUTCOME_REF = "body.p1076"
PKG87_OVERDOSE_ERROR_HEADING_REF = "body.p1077"
PKG87_OVERDOSE_DEF_REF = "body.p1078"
PKG87_ADMIN_ERROR_DEF_REF = "body.p1079"
PKG87_RECORDING_HEADING_REF = "body.p1080"
PKG87_ADMIN_LOG_REF = "body.p1081"
PKG87_AE_PAGE_REF = "body.p1082"
PKG87_ASSESSMENT_HEADING_REF = "body.p1083"
SAE_DEFINITION_REF = "body.p996"
SAE_OR_LEAD_REF = "body.p997"
DEATH_AS_SAE_OUTCOME_REF = "body.p998"
COLLECTION_WINDOW_REF = "body.p1022"
RECORDING_OBLIGATION_REF = "body.p1024"
SINGLE_MEDICAL_CONCEPT_REF = "body.p1026"
AE_RECORD_START_REF = "body.p340"
REPORT_TIMELINE_REFINEMENT_REF = "body.p1103"
DEATH_EVENT_LIST_REF = "body.p1104"

# 结构级关键片段：编码死亡结果/事件术语、通常一项限定、不明死因替换、猝死
# 限定、过量/给药错误定义、漏服排除与双表并行逻辑的逐字片段，反例改写必须
# 破坏至少一个
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1075": [
        "所有死亡事件",
        "无论与研究药物的关系如何",
        "必须记录在eCRF不良事件上",
        "立即报告给申办者",
    ],
    "body.p1076": [
        "死亡应被视为事件的结果，而非单独的事件",
        "记录为单一医学概念",
        "通常，只报告1个",
        "不明原因死亡",
        "替换为确定的死因",
        "不应使用术语“猝死”",
        "推测的死因",
    ],
    "body.p1078": [
        "意外或故意使用的CMS-D001片用量高于指定的研究剂量",
    ],
    "body.p1079": [
        "药物分发或给药中的任何非预期用药情况",
        "漏用或未按计划使用不被视为给药错误",
    ],
    "body.p1081": [
        "应在eCRF研究药物给药表上注明",
        "任何研究药物过量或研究治疗给药错误",
    ],
    "body.p1082": [
        "“药物过量/给药错误”本身不属于不良事件",
        "与药物过量或给药错误相关的所有不良事件应记录在eCRF不良事件上",
    ],
}

# 结构片段门禁可发现删词或改词，但无法发现“保留原句后追加必要条件”。
# 这组标记只覆盖来源明确没有、且会改变定义真值范围的附加条件。
FORBIDDEN_SEMANTIC_ADDITIONS_BY_REF = {
    "body.p1078": ["并导致临床伤害", "并发生毒性", "并需要治疗"],
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_semantic_addition_hits(text: str, source_ref: str) -> list[str]:
    return [
        marker
        for marker in FORBIDDEN_SEMANTIC_ADDITIONS_BY_REF.get(source_ref, [])
        if marker in text
    ]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _missing_exception_keywords(text: str, entry: dict) -> list[str]:
    """确定性合取/例外门禁：来源文本必须同时保留基础规则与例外条款关键词。"""
    return [kw for kw in entry["preserve_keywords"] if kw not in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码术语边界/限定/双表逻辑的逐字片段。"""
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


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


# ---------------------------------------------------------------------------
# config contract
# ---------------------------------------------------------------------------


def test_config_contract(config: dict) -> None:
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["group_id"] == "d001-ii-package87-death-overdose-medication-error-boundary"
    assert config["task_id"] == "phase5-slice61by-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 10

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "四个标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第87包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第87包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗后记录与报告处置；结构单元不进入处置映射
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in SEMANTIC_OWNED_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：全部拥有单元的禁止升格措辞必须已写入配置
    for ref in OWNED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {"筛选必做", "基线必做", "证据缺口", "不得入组", "排除标准", "入排不通过"} <= set(
            markers
        ), ref
    assert config["candidate_required_markers_by_source_ref"] == {}

    # 术语边界/限定/双表逻辑语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(EXCEPTION_SEMANTICS_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg87 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL
    )
    owned_87 = {u["source_ref"] for u in pkg87["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_87), "attached refs must not be owned by package 87"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 9


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in SAE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in RECORDING_ATTACHED_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    for ref in DEATH_REPORT_REFINEMENT_REFS:
        assert owners.get(ref) == [PACKAGE_93_ORDINAL], f"{ref} 必须保持归第93包"
    assert owners.get("body.p340") is None, (
        "body.p340 必须保持流程注记上下文来源"
    )


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第86包拥有p1067-p1073（7），第87包拥有p1074-p1083（10），
    第88包拥有p1084-p1086（3），第90包拥有p1087-p1097（11），第93包拥有p1102-p1112（11）。"""
    pkg86 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL)
    pkg87 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL)
    pkg88 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL)
    pkg90 = next(p for p in plan["packages"] if p["package_ordinal"] == 90)
    pkg93 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL)
    owned_86 = {u["source_ref"] for u in pkg86["owned_units"]}
    owned_87 = {u["source_ref"] for u in pkg87["owned_units"]}
    owned_88 = {u["source_ref"] for u in pkg88["owned_units"]}
    owned_90 = {u["source_ref"] for u in pkg90["owned_units"]}
    owned_93 = {u["source_ref"] for u in pkg93["owned_units"]}
    assert set(PKG86_SPAN_REFS) <= owned_86 and len(owned_86) == 7
    assert set(OWNED_REFS) <= owned_87 and len(owned_87) == 10
    assert set(PKG88_SPAN_REFS) <= owned_88 and len(owned_88) == 3
    assert set(PKG90_SPAN_REFS) <= owned_90 and len(owned_90) == 11
    assert set(PKG93_SPAN_REFS) <= owned_93 and len(owned_93) == 11


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_87(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_87_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1074"] == "死亡"
    assert excerpts["body.p1075"] == (
        "在方案规定的不良事件收集期内发生的所有死亡事件，无论与研究药物的关系如何，"
        "必须记录在eCRF不良事件上，并立即报告给申办者。"
    )
    assert excerpts["body.p1076"] == (
        "死亡应被视为事件的结果，而非单独的事件。导致或促成致死性结果的事件或情况"
        "应在eCRF不良事件上记录为单一医学概念。通常，只报告1个这样的事件或情况。"
        "如果死因不明且不能在报告当时查明，则应在eCRF不良事件上记录“不明原因死亡”。"
        "如果死因稍后可获得，应将“不明原因死亡”替换为确定的死因。不应使用术语"
        "“猝死”，除非与推测的死因（如“心源性猝死”）结合使用。"
    )
    assert excerpts["body.p1077"] == "与药物过量或给药错误相关的不良事件"
    assert excerpts["body.p1078"] == (
        "药物过量是指意外或故意使用的CMS-D001片用量高于指定的研究剂量。"
    )
    assert excerpts["body.p1079"] == (
        "给药错误指药物分发或给药中的任何非预期用药情况，参与者漏用或未按计划使用"
        "不被视为给药错误。"
    )
    assert excerpts["body.p1080"] == "记录要求"
    assert excerpts["body.p1081"] == (
        "应在eCRF研究药物给药表上注明任何研究药物过量或研究治疗给药错误的事件。"
    )
    assert excerpts["body.p1082"] == (
        "“药物过量/给药错误”本身不属于不良事件，但与药物过量或给药错误相关的所有"
        "不良事件应记录在eCRF不良事件上。"
    )
    assert excerpts["body.p1083"] == "不良事件的评估"


def test_recording_label_and_next_section_heading_keep_distinct_hierarchy(
    config: dict, plan: dict
) -> None:
    """p1080留在过量/给药错误小节内；p1083才开启后续评估章节。"""
    package = next(
        item for item in plan["packages"] if item["package_id"] == PACKAGE_87_ID
    )
    units = {item["source_ref"]: item for item in package["owned_units"]}
    assert units["body.p1080"]["heading_path"][-1] == "与药物过量或给药错误相关的不良事件"
    assert "记录要求" not in units["body.p1080"]["heading_path"]
    assert units["body.p1083"]["heading_path"][-1] == "不良事件的评估"
    assert "与药物过量或给药错误相关的不良事件" not in units["body.p1083"]["heading_path"]


# ---------------------------------------------------------------------------
# structural-only units and semantic rows
# ---------------------------------------------------------------------------


def test_structural_units_do_not_form_control_points(config: dict, plan: dict) -> None:
    """四个标题（p1074/p1077/p1080/p1083）不形成控制点；六个语义单元保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1074"] == "死亡"
    assert excerpts["body.p1077"] == "与药物过量或给药错误相关的不良事件"
    assert excerpts["body.p1080"] == "记录要求"
    assert excerpts["body.p1083"] == "不良事件的评估"
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1067-p1073 -> 86, p1074-p1083 -> 87,
# p1084-p1086 -> 88
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """第86/88包来源可保留所有权元数据，但不得进入本包闭包或由本包发射。"""
    boundary = config["later_package_boundary"]
    expected_boundary = set(PKG86_SPAN_REFS + OWNED_REFS + PKG88_SPAN_REFS)
    assert set(boundary["expected_owners_by_span"]) == expected_boundary
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 87
    for ref in PKG86_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 86
    for ref in PKG88_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 88
    neighbor = set(PKG86_SPAN_REFS + PKG88_SPAN_REFS)
    assert neighbor.isdisjoint(set(config["owned_source_refs"])), (
        "第86/88包来源不得被第87包拥有"
    )


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref, expected_ordinal in boundary["expected_owners_by_span"].items():
        assert owners.get(ref) == [expected_ordinal], (
            f"{ref} 所有权漂移：期望第{expected_ordinal}包，实际{owners.get(ref)}"
        )
        assert expected_ordinal != PACKAGE_87_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第87包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第86包",
        "第87包",
        "第88包",
        "第89包",
        "第90包",
        "第92包",
        "第93包",
        "吞并",
        "所有权不得转移",
        "p1103",
        "p1104",
        "24小时",
        "死亡事件",
    ):
        assert fragment in note, f"边界注记缺少不得提前吞并声明: {fragment}"


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(
        config["attached_source_refs"]
    )
    for ref in OWNED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"

    # 拥有单元关键语义片段
    assert "所有死亡事件" in by_ref[PKG87_DEATH_RECORDING_REF].excerpt
    assert "无论与研究药物的关系如何" in by_ref[PKG87_DEATH_RECORDING_REF].excerpt
    assert "事件的结果" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "而非单独的事件" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "单一医学概念" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "通常，只报告1个" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "不明原因死亡" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "替换为确定的死因" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "心源性猝死" in by_ref[PKG87_DEATH_OUTCOME_REF].excerpt
    assert "意外或故意" in by_ref[PKG87_OVERDOSE_DEF_REF].excerpt
    assert "高于指定的研究剂量" in by_ref[PKG87_OVERDOSE_DEF_REF].excerpt
    assert "不被视为给药错误" in by_ref[PKG87_ADMIN_ERROR_DEF_REF].excerpt
    assert "eCRF研究药物给药表上注明" in by_ref[PKG87_ADMIN_LOG_REF].excerpt
    assert "本身不属于不良事件" in by_ref[PKG87_AE_PAGE_REF].excerpt

    # 只读闭包关键片段（SAE定义/记录锚点/24小时细化）
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "符合下列标准任何一项的不良事件" in by_ref[SAE_OR_LEAD_REF].excerpt
    assert "当一个事件的结果为“死亡”" in by_ref[DEATH_AS_SAE_OUTCOME_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_MEDICAL_CONCEPT_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt
    assert "获知后24小时（含）内" in by_ref[REPORT_TIMELINE_REFINEMENT_REF].excerpt
    assert by_ref[DEATH_EVENT_LIST_REF].excerpt == "死亡事件"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含定义/记录锚点与防吞并边界，
    不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in PKG86_SPAN_REFS + PKG88_SPAN_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"
    # 第93包仅p1103-p1104只读进入；p1105/p1106及后续通用流程不得进入
    for ref in PKG93_NON_ATTACHED_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 9
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

    # 越界候选（把死亡/过量/给药错误记录规范升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1076"]],
                "title": "筛选时核对死亡事件记录安排，未确认者按证据缺口判定入排不通过",
                "semantics": {},
            }
        ],
        "dispositions": dispositions,
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues)

    # 处置漂移必须被拒绝
    dispositions[0]["disposition"] = "other_control_candidate"
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "DISPOSITION_MISMATCH" for issue in issues)


# ---------------------------------------------------------------------------
# deterministic forbidden-upgrade gate
# ---------------------------------------------------------------------------


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    """冻结来源本身不得包含升格措辞；来源干净是重放门禁的前提。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref in OWNED_REFS:
        hits = _forbidden_marker_hits(excerpts[ref], markers_by_ref[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把死亡/过量/给药错误记录规范改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1074": [
            "筛选时核对死亡记录安排，未完成者不得入组",
        ],
        "body.p1075": [
            "筛选时核对死亡事件立即报告安排，未确认者证据缺口不得入组",
        ],
        "body.p1076": [
            "筛选时核对死亡事件单一医学概念记录安排，未确认者入排不通过",
        ],
        "body.p1077": [
            "筛选时核对药物过量或给药错误相关AE记录安排，未完成者不得入组",
        ],
        "body.p1078": [
            "筛选时核对药物过量定义掌握情况，证据不足者按排除标准判定不通过",
        ],
        "body.p1079": [
            "筛选时核对给药错误定义掌握情况，未确认者入排不通过",
        ],
        "body.p1080": [
            "筛选时核对记录要求安排，未完成者证据缺口不得入组",
        ],
        "body.p1081": [
            "筛选时核对给药表注记安排，未确认者不得入组",
        ],
        "body.p1082": [
            "筛选时核对双表记录安排，未确认者入排不通过",
        ],
        "body.p1083": [
            "筛选时核对AE评估安排，未完成者证据缺口不得入组",
        ],
    }
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref, counterexamples in counterexamples_by_ref.items():
        for text in counterexamples:
            assert _forbidden_marker_hits(text, markers_by_ref[ref]), (
                f"门禁未拦截 {ref} 升格反例: {text}"
            )

    # 合法定义文本不得误拦截
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        hits = _forbidden_marker_hits(
            excerpts[ref], config["candidate_forbidden_markers_by_source_ref"][ref]
        )
        assert hits == [], f"误拦截合法定义 {ref}: {hits}"


# ---------------------------------------------------------------------------
# deterministic exception/conjunction semantics gate
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """术语边界、限定与双表逻辑关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或记录路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1075": "在方案规定的不良事件收集期内发生的死亡事件，必须记录在eCRF不良事件上，并立即报告给申办者。",
        "body.p1076": "死亡应被视为事件的结果，而非单独的事件。",
        "body.p1078": "药物过量是指意外或故意使用的CMS-D001片用量高于研究剂量。",
        "body.p1079": "给药错误指药物分发或给药中的任何非预期用药情况。",
        "body.p1081": "研究药物过量或研究治疗给药错误的事件应在eCRF研究药物给药表上注明。",
        "body.p1082": "与药物过量或给药错误相关的所有不良事件应记录在eCRF不良事件上。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# AND/OR, terminology, and dual-table structure gates
# ---------------------------------------------------------------------------


def test_structural_fragments_present_in_owned_sources(plan: dict, config: dict) -> None:
    """编码术语边界/限定/双表逻辑的逐字片段必须完整保留在来源摘录中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref, fragments in STRUCTURAL_FRAGMENTS_BY_REF.items():
        for fragment in fragments:
            assert fragment in excerpts[ref], f"{ref} 丢失结构级片段: {fragment}"


def test_and_or_inversion_counterexamples_detected(config: dict) -> None:
    """术语边界反转、限定绝对化、定义增删条件、双表互斥反例必须被确定性拦截。"""
    inverted = {
        "body.p1075": [
            "在方案规定的不良事件收集期内发生的死亡事件（与研究药物相关），必须记录在eCRF不良事件上，并立即报告给申办者。",
            "在方案规定的不良事件收集期内发生的所有死亡事件，无论与研究药物的关系如何，必须记录在eCRF不良事件上，并尽快报告给申办者。",
            "在方案规定的不良事件收集期内发生的所有死亡事件，无论与研究药物的关系如何，必须记录在eCRF研究药物给药表上，并立即报告给申办者。",
        ],
        "body.p1076": [
            "死亡应被视为独立的事件，而非事件的结果。",
            "导致或促成致死性结果的事件或情况应在eCRF不良事件上记录为多个医学概念。",
            "任何情况下只能报告1个导致或促成致死性结果的事件或情况。",
            "如果死因稍后可获得，应删除“不明原因死亡”记录并记录确定的死因。",
            "不应使用术语“猝死”。",
            "任何情况下都不得使用“猝死”术语。",
        ],
        "body.p1078": [
            "药物过量是指意外使用的CMS-D001片用量高于指定的研究剂量。",
            "药物过量是指故意使用的CMS-D001片用量高于指定的研究剂量。",
            "药物过量是指意外或故意使用的CMS-D001片用量高于或等于指定的研究剂量。",
            "药物过量是指意外或故意使用的CMS-D001片用量达到指定的研究剂量。",
            "药物过量是指意外或故意使用的CMS-D001片用量达到指定研究剂量的2倍及以上。",
            "药物过量是指意外或故意使用的CMS-D001片用量偏离指定的研究计划。",
            "药物过量是指意外或故意使用的CMS-D001片用量高于指定的研究剂量，并导致临床伤害。",
            "药物过量是指任何药物的用量高于指定的研究剂量。",
        ],
        "body.p1079": [
            "给药错误指药物分发或给药中的任何非预期用药情况，参与者漏用或未按计划使用也视为给药错误。",
            "给药错误指药物分发或给药中的任何非预期用药情况。",
            "参与者漏用或未按计划使用属于给药错误，应记录在给药表。",
        ],
        "body.p1081": [
            "当与研究药物过量或给药错误相关的AE存在时，应在eCRF研究药物给药表上注明这些事件。",
            "研究药物过量或研究治疗给药错误的事件无需在eCRF研究药物给药表上注明。",
        ],
        "body.p1082": [
            "“药物过量/给药错误”本身不属于不良事件，但与药物过量或给药错误相关的所有不良事件应记录在eCRF研究药物给药表上。",
            "“药物过量/给药错误”本身属于不良事件，与药物过量或给药错误相关的所有不良事件应记录在eCRF不良事件上。",
            "存在与药物过量或给药错误相关的AE时，在eCRF研究药物给药表上注明即可，无需再记录不良事件。",
            "无关联AE时无需在给药表记录，有关联AE时才在给药表注明。",
        ],
    }
    for ref, counterexamples in inverted.items():
        for text in counterexamples:
            missing = _missing_structural_fragments(text, ref)
            additions = _forbidden_semantic_addition_hits(text, ref)
            assert missing or additions, (
                f"{ref} 术语边界/限定/额外条件/双表逻辑反例未被门禁拦截: {text}"
            )


def test_death_outcome_and_event_terminology_never_conflated(config: dict) -> None:
    """p1076死亡是事件的结果不是独立事件；死亡结果与事件术语必须严格区分。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1076"]
    assert "死亡是事件的结果，不是独立事件" in entry["exception_rule"]
    assert "以单一医学概念记录在eCRF不良事件页" in entry["exception_rule"]
    assert "不得把死亡结果改写为独立事件" in entry["forbidden_inversion"]
    assert "不得把导致死亡的事件当作独立事件重复计数" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1076"])
    assert "死亡是事件的结果，不是独立事件" in checks
    # p998 只读锚点与 p1076 互相印证但归各自包
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "与p1076'死亡是事件的结果而非单独的事件'互相印证" in checks_blob
    assert "均归各自包" in checks_blob


def test_usually_one_is_not_absolute(config: dict) -> None:
    """'通常只报告1个'不得绝对化为任何情况下只能记录一个。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1076"]
    assert "'通常只报告1个'是默认情形，不是任何情况下只能记录一个" in entry["exception_rule"]
    assert "不得把'通常只报告1个'绝对化为任何情况下只能记录一个" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1076"])
    assert "'通常只报告1个'不是任何情况下只能记录一个" in checks
    # 单一事件项一术语（p1026）与'通常只报告1个'不得互相改写
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得把'只记录一个不良事件术语'与'通常只报告1个事件或情况'互相改写" in checks_blob


def test_unknown_cause_replacement_is_not_history_deletion(config: dict) -> None:
    """不明死因记录'不明原因死亡'，后来获得死因时替换为确定死因，不是删除历史。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1076"]
    assert "死因不明且无法查明时记录'不明原因死亡'" in entry["exception_rule"]
    assert "替换为确定死因，不是物理删除历史记录" in entry["exception_rule"]
    assert "不得把'不明原因死亡'的替换误读为删除/作废历史记录" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1076"])
    assert "后来获得死因时替换为确定死因，不是物理删除历史记录" in checks


def test_sudden_death_qualified_not_blanket(config: dict) -> None:
    """'猝死'只有与推测死因结合才可使用，不得改写为一律禁用或一律允许。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1076"]
    assert "'猝死'只有与推测死因（如'心源性猝死'）结合使用" in entry["exception_rule"]
    assert "不得把'猝死'限定改写为一律禁用或一律允许" in entry["forbidden_inversion"]
    assert "不得删除'与推测的死因结合使用'限定" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1076"])
    assert "只有与推测死因（如'心源性猝死'）结合才可使用" in checks


def test_overdose_definition_covers_accidental_and_intentional(config: dict) -> None:
    """p1078保留用药对象、严格高于阈值及完整并集，不增添临床后果前提。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1078"]
    assert "同时覆盖意外和故意使用" in entry["exception_rule"]
    assert "判断核心是CMS-D001片用量严格高于指定研究剂量" in entry["exception_rule"]
    assert "等于指定研究剂量不满足该定义" in entry["exception_rule"]
    assert "不得把'意外或故意'删成只有意外或只有故意" in entry["forbidden_inversion"]
    assert "不得把'高于'弱化为'高于或等于'或'达到'" in entry["forbidden_inversion"]
    assert "不得增加'至少达到X倍剂量'等原文未写明的阈值条件" in entry["forbidden_inversion"]
    assert "不得把任何偏离计划用药都定义为过量" in entry["forbidden_inversion"]
    assert "不得追加发生伤害、毒性、临床后果或需要治疗等原文没有的必要条件" in entry[
        "forbidden_inversion"
    ]
    assert "不得把CMS-D001片的定义泛化为所有药物" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1078"])
    assert "判断核心是CMS-D001片用量严格高于指定研究剂量" in checks
    assert "等于指定研究剂量不满足该定义" in checks
    assert "达到某个未写明倍数" in checks
    assert "不得追加发生伤害、毒性、临床后果或需要治疗等原文没有的必要条件" in checks
    assert "不得把CMS-D001片的定义泛化为所有药物" in checks


def test_missed_dose_never_reclassified_as_administration_error(config: dict) -> None:
    """p1079漏用或未按计划使用明确排除在给药错误之外，不得重新纳入。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1079"]
    assert "参与者漏用或未按计划使用明确排除在给药错误之外，不得重新纳入" in entry["exception_rule"]
    assert "不得把'漏用或未按计划使用'重新纳入给药错误" in entry["forbidden_inversion"]
    assert "不得从本条外推漏用一定属于AE、方案偏离或入排失败" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1079"])
    assert "参与者漏用或未按计划使用明确排除在给药错误之外" in checks
    assert "不得从本条外推漏用一定属于AE、方案偏离或入排失败" in checks


def test_dual_table_parallel_not_mutually_exclusive(config: dict) -> None:
    """p1081给药表与p1082不良事件页是并行双表记录，不得改写为互斥。"""
    p1081 = config["exception_semantics_by_source_ref"]["body.p1081"]
    p1082 = config["exception_semantics_by_source_ref"]["body.p1082"]
    assert "双表并行记录逻辑的给药表一侧" in p1081["exception_rule"]
    assert "没有关联AE时仍保留给药表记录" in p1081["exception_rule"]
    assert "不得把双表逻辑改写为互斥" in p1081["forbidden_inversion"]
    assert "双表并行逻辑" in p1082["exception_rule"]
    assert "'药物过量/给药错误'标签本身不是AE" in p1082["exception_rule"]
    assert "有关联AE时不能只记给药表而漏记AE" in p1082["exception_rule"]
    assert "也不能把过量/错误标签本身当成AE术语" in p1082["exception_rule"]
    assert "不得把双表逻辑改写为互斥（有AE就删给药表、无AE才记给药表、或只记一张表）" in p1082[
        "forbidden_inversion"
    ]
    assert "不得把'药物过量/给药错误'标签本身当成AE术语" in p1082["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "双表是并行关系不是互斥关系" in checks_blob
    assert "没有关联AE时仍保留给药表记录" in checks_blob
    assert "有关联AE时不能只记给药表而漏记AE" in checks_blob


def test_p1075_keeps_immediate_report_and_all_deaths(config: dict) -> None:
    """'所有死亡事件'、'无论与研究药物的关系如何'与'立即报告'必须完整保留。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1075"]
    assert "所有死亡事件均须记录在eCRF不良事件页" in entry["exception_rule"]
    assert "与研究药物关系无关" in entry["exception_rule"]
    assert "不得把'所有死亡事件'缩小为与研究药物相关死亡" in entry["forbidden_inversion"]
    assert "不得把'立即报告'改为'尽快报告'或删除立即报告义务" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1075"])
    assert "所有死亡事件均需记录并立即报告" in checks
    assert "与研究药物关系无关" in checks


# ---------------------------------------------------------------------------
# package 93 24-hour refinement and package 86/88+ anti-absorption
# ---------------------------------------------------------------------------


def test_p93_24h_refinement_attached_read_only_not_reowned(config: dict) -> None:
    """第93包p1103-p1104死亡事件报告时限细化只读附加，不得被本包重新拥有。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(DEATH_REPORT_REFINEMENT_REFS) <= attached
    assert set(DEATH_REPORT_REFINEMENT_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "p1103-p1104'获知后24小时（含）内'" in note
    assert "只读携带该细化不得变成第87包重新拥有通用报告流程" in note
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1103"])
    assert "仅按合同为p1075'立即报告'提供死亡事件报告时限的细化" in checks
    assert "不得变成第87包重新拥有通用报告流程" in checks


def test_p93_generic_reporting_and_p1105_p1106_not_absorbed(config: dict) -> None:
    """第93包p1105/p1106（严重不良事件、妊娠事件）及通用流程不得进入本包闭包。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG93_NON_ATTACHED_REFS).isdisjoint(attached)
    assert set(PKG93_NON_ATTACHED_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "p1105/p1106（严重不良事件、妊娠事件）与第93包其余通用报告和随访流程" in note
    assert "均不进入本包提示" in note
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得把p1105/p1106（严重不良事件、妊娠事件）并入本包" in checks_blob


def test_package86_not_absorbed(config: dict) -> None:
    """第86包DILI逻辑不得进入本包闭包或提示。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG86_SPAN_REFS).isdisjoint(attached)
    assert set(PKG86_SPAN_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "前接第86包DILI评估、调查、潜在/确诊分层与报告流程" in note
    assert "不进入本包语义，本包不重新拥有DILI逻辑" in note


def test_package88_and_later_not_absorbed(config: dict) -> None:
    """第88包严重程度评估及更后包流程不得进入本包闭包。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    for span in (PKG88_SPAN_REFS, PKG90_SPAN_REFS, PKG92_SPAN_REFS):
        assert set(span).isdisjoint(attached)
        assert set(span).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "第88包AE严重程度评估与表8分级" in note
    assert "第90包因果关系共同判断" in note
    assert "第92包预期性评估" in note
    assert "本包不提前吞并或处置" in note


def test_prompt_excludes_package86_and_later_content() -> None:
    """第86包DILI内容与第88包及更后包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第86包DILI逻辑（禁止泄漏）
    for leaked in (
        "药物性肝损伤",
        "Hy",
        "48 h内",
        "总胆红素升高标准",
        "与申办者一起审查",
    ):
        assert leaked not in prompt_text, f"第86包DILI内容泄漏进第87包提示: {leaked}"
    # 第88/89/90/91/92包内容（禁止泄漏；"不良事件的评估"是p1083本包标题）
    for leaked in (
        "严重程度评估",
        "CTCAE",
        "表 8",
        "因果关系",
        "预期性",
        "研究者手册",
    ):
        assert leaked not in prompt_text, f"第88包及更后包内容泄漏进第87包提示: {leaked}"
    # 第93包通用流程内容（禁止泄漏；"严重不良事件"经p996/p997只读附加合法存在；
    # "应报告的事件类型"是p1103/p1104附加行的共享章节标题路径，属合法元数据）
    assert "妊娠事件" not in prompt_text, "第93包通用报告流程泄漏进第87包提示: 妊娠事件"
    # 相邻包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in PKG86_SPAN_REFS + PKG88_SPAN_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第87包准备证据"
    for ref in PKG93_NON_ATTACHED_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第87包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第87包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_definition_anchors_and_24h_refinement() -> None:
    """提示必须包含SAE定义/记录锚点与第93包24小时细化，且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "严重不良事件" in prompt_text
    assert "符合下列标准任何一项的不良事件" in prompt_text
    assert "当一个事件的结果为“死亡”" in prompt_text
    assert "D1启动给药后开始记录" in prompt_text
    assert "单一事件项中应只记录一个不良事件术语" in prompt_text
    assert "获知后24小时（含）内" in prompt_text
    assert "死亡事件" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert by_ref[DEATH_AS_SAE_OUTCOME_REF]["role"] == "attached"
    assert by_ref[SINGLE_MEDICAL_CONCEPT_REF]["role"] == "attached"
    assert by_ref[REPORT_TIMELINE_REFINEMENT_REF]["role"] == "attached"
    assert by_ref[DEATH_EVENT_LIST_REF]["role"] == "attached"
    assert by_ref[PKG87_DEATH_OUTCOME_REF]["role"] == "owned"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package87(matrix: dict, plan: dict) -> None:
    pkg87 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg87["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第87包拥有来源为锚点"
            )


def test_matrix_has_no_ae_teae_sae_rows(matrix: dict) -> None:
    for row in matrix["rows"]:
        text = " ".join(
            str(row.get(key) or "")
            for key in (
                "title_zh",
                "required_action_zh",
                "attainment_criteria_zh",
                "minimum_evidence",
            )
        )
        assert "不良事件" not in text, row["matrix_row_id"]
        assert "TEAE" not in text and "SAE" not in text, row["matrix_row_id"]
        assert "发生率" not in text, row["matrix_row_id"]
        for anchor in row.get("source_anchors") or []:
            ref = str(anchor.get("source_ref") or "")
            if ref.startswith(("body.t12", "body.t13", "body.t14")):
                raise AssertionError(f"{row['matrix_row_id']} 锚点 {ref} 落在表7/表8/因果判定表内")
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package87_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg87 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg87["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第87包拥有来源为锚点"
            )


def _catalog_nodes(catalog: dict, label: str) -> list[dict]:
    return [item for item in catalog["items"] if item["label"] == label]


def test_procedure_catalog_has_no_ae_or_teae_node(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = str(item["label"])
        assert "不良事件" not in label
        assert label not in {"AE", "TEAE", "SAE", "发生率"}
    assert _catalog_nodes(procedure_catalog, "不良事件") == []
    assert _catalog_nodes(procedure_catalog, "TEAE") == []
    assert _catalog_nodes(procedure_catalog, "SAE") == []


def test_no_procedure_node_sourced_from_package87_or_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            if ref.startswith(("body.t12", "body.t13", "body.t14")):
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以表7/表8/因果判定表来源 {ref} 为来源"
                )
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以定义章节来源 {ref} 为来源"
                )


# ---------------------------------------------------------------------------
# known targets build empty
# ---------------------------------------------------------------------------


def test_known_targets_build_empty(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert official == []
    assert procedures == []
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_workflow_stages_keep_d1_pre_dose_distinct(config: dict) -> None:
    from slice59n_representative_group_control_replay import _workflow

    stages = {s.workflow_stage_id: s for s in _workflow(config)}
    assert set(stages) == {"flow-screening", "flow-baseline", "flow-d1-pre-dose"}
    assert stages["flow-screening"].review_stage.value == "screening"
    assert stages["flow-baseline"].review_stage.value == "baseline"
    assert stages["flow-d1-pre-dose"].review_stage.value == "baseline"
    assert (
        stages["flow-d1-pre-dose"].visit_instance == "D1给药前"
        and stages["flow-d1-pre-dose"].visit_instance
        != stages["flow-baseline"].visit_instance
    )


# ---------------------------------------------------------------------------
# fingerprints and checklist freeze
# ---------------------------------------------------------------------------


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    coverage = _load_json(COVERAGE_PATH)
    assert coverage["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_87_ID in text
    assert PACKAGE_86_ID in text
    assert PACKAGE_93_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "死亡应被视为事件的结果" in text
    assert "不明原因死亡" in text
    assert "猝死" in text
    assert "药物过量" in text
    assert "给药错误" in text
    assert "漏用或未按计划使用" in text
    assert "eCRF研究药物给药表" in text
    assert "24小时" in text
    assert "body.p1074" in text and "body.p1083" in text
    assert "第86包" in text and "第87包" in text and "第88包" in text
    assert "第93包" in text
    assert "不得提前吞并" in text or "防吞并" in text
