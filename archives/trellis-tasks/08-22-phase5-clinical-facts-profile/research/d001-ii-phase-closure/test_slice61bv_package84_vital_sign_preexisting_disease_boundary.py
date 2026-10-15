#!/usr/bin/env python3
"""Slice61bv model-free source-closure regressions.

Locks the D001 II package 84 vital-sign abnormality and pre-existing
(concomitant) disease recording boundary (frozen plan package 84: 生命体征异常
与既存（合并）疾病记录规则, body.p1043-p1054) to its authoritative sources
before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 84 (2 structural headings + 10 semantic
  recording rules); attached refs stay read-only
- structural units (p1043/p1049) stay structural only; ten semantic units keep
  post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- vital-sign abnormality rules (p1044-p1048) and pre-existing disease
  recording rules (p1049-p1054) stay separated: OR mandatory reporting never
  leaks into the AND conjunction recording of pre-existing disease, and vice
  versa
- professional judgment (p1044) vs OR mandatory reporting (p1045-p1048) stay
  layered: judgment never becomes "只要异常即为AE" or "只要研究者未明确否定
  即为AE"; mandatory reporting never weakened by judgment
- OR structure never inverted to AND for vital signs: p1045 "任一标准" keeps
  OR; the three alternatives p1046/p1047/p1048 stay parallel and
  non-interchangeable; verbatim text differences vs package 83 lab rules
  preserved (p1046 伴有临床症状 without 或体征; p1048 伴随治疗改变 vs
  p1042 合并用药/治疗改变)
- pre-existing disease recording stays AND conjunction: p1051 "才应" requires
  p1052 (恶化或改变) AND p1053 (非预期进展) to be satisfied together; the two
  adjacent list items must never be flipped into OR
- p1050 stays a documentation boundary (record in eCRF 病史和基线状况), never
  escalated to an enrollment standard or 缺失即不通过
- p1054 "偏头痛频次增加" stays an example, never escalated to the only
  expression or a universal disease condition
- package 83 lab parallel rules (p1037-p1042) enter only as read-only
  anti-conflation context owned by package 83; package 85 hepatic-function SAE
  (p1055 heading only) enters only as anti-absorption boundary
- official matrix keeps zero rows anchored in p1043-p1054 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no p1043-p1054 source
  spans
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
    / "representative_group_package84_vital_sign_preexisting_disease_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61bv-package84-vital-sign-preexisting-disease-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package84-vital-sign-preexisting-disease-boundary"
)
FREEZE_DIR = (
    ROOT
    / "artifacts"
    / "phase5-slice59i-d001-phase-table-caption-rebaseline-20260827"
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
CATALOG_DIR = (
    ROOT
    / "artifacts"
    / "phase5-slice61bl-procedure-footnote-scope-20260829"
)
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
PACKAGE_84_ORDINAL = 84
PACKAGE_84_ID = "pap-ab31cb1fdc0643d57a0a41a2"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]

# 结构单元：两个章节标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1043", "body.p1049"]
# 语义单元：生命体征异常判断/OR强制报告结构与既存疾病记录规则，
# 保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = [
    "body.p1044",
    "body.p1045",
    "body.p1046",
    "body.p1047",
    "body.p1048",
    "body.p1050",
    "body.p1051",
    "body.p1052",
    "body.p1053",
    "body.p1054",
]

# 只读闭包：AE/TEAE/SAE定义、筛选时既存情况与严重性总纲（5）、
# AE收集期/给药前事件记录/全量记录义务/单一事件项一术语（4）、
# 流程/监测/D1给药前后锚点（3）、第83包实验室异常平行结构（6）、第85包防吞并边界标题（1）
AE_DEF_ATTACHED_REFS = ["body.p986", "body.p988", "body.p994"]
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1023", "body.p1024", "body.p1026"]
FLOW_ANCHOR_REFS = ["body.p340", "body.p835", "body.p885"]
PKG83_LAB_PARALLEL_REFS = [f"body.p{ordinal}" for ordinal in range(1037, 1043)]
PKG85_BOUNDARY_REF = "body.p1055"
UNOWNED_CONTEXT_REFS = ["body.p340", "body.p885"]
ATTACHED_REFS = (
    AE_DEF_ATTACHED_REFS
    + SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
    + PKG83_LAB_PARALLEL_REFS
    + [PKG85_BOUNDARY_REF]
)

# 后续包所有权：第83包实验室异常平行结构（p1037-p1042）只读进入，所有权不变；
# 第85包特殊肝功能SAE（p1055起）只保留防吞并边界标题
LATER_PKG83_REFS = PKG83_LAB_PARALLEL_REFS
PKG85_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1055, 1067)]

# 各语义单元的判断/强制报告、OR结构、合取结构与记录边界语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1044": {
        "base_rule": "研究者负责审查所有生命体征结果，通过医学和科学判断一项孤立的生命体征值异常是否应归类为不良事件",
        "exception_rule": "专业判断层：研究者的医学和科学判断用于判断孤立生命体征值异常是否应归类为AE；不得改写为'只要异常即为AE'或'只要研究者未明确否定即为AE'；判断层不得与p1045-p1048强制报告层混同",
        "preserve_keywords": ["医学和科学判断", "孤立的生命体征值异常", "是否应归类为不良事件"],
    },
    "body.p1045": {
        "base_rule": "当生命体征异常符合以下任一标准时，则必须报告为不良事件",
        "exception_rule": "OR强制报告总纲：p1046/p1047/p1048任一标准满足即必须报告为AE；不得改成AND，不得把'必须报告'弱化为'可报告'",
        "preserve_keywords": ["任一标准", "必须报告为不良事件"],
    },
    "body.p1046": {
        "base_rule": "伴有临床症状",
        "exception_rule": "OR备选一：生命体征异常伴有临床症状即满足强制报告标准；原文为'伴有临床症状'（无'或体征'），不得补入实验室版'或体征'；与p1047/p1048并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["伴有临床症状"],
    },
    "body.p1047": {
        "base_rule": "导致研究治疗发生变化（例如治疗暂停或治疗终止）",
        "exception_rule": "OR备选二：生命体征异常导致研究治疗发生变化（如治疗暂停或终止）即满足强制报告标准；与p1046/p1048并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["导致研究治疗发生变化", "治疗暂停", "治疗终止"],
    },
    "body.p1048": {
        "base_rule": "导致医学干预或伴随治疗改变",
        "exception_rule": "OR备选三：生命体征异常导致医学干预或伴随治疗改变即满足强制报告标准；原文为'伴随治疗改变'，不得替换为实验室版'合并用药/治疗改变'；与p1046/p1047并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["导致医学干预", "伴随治疗改变"],
    },
    "body.p1050": {
        "base_rule": "既存疾病（事先存在的疾病）是指在本研究的筛选访视时或首次给药前即已存在的疾病，此类状况应记录在eCRF的病史和基线状况中",
        "exception_rule": "资料记录边界：定义筛选访视时或首次给药前既已存在的疾病并要求记录于病史和基线状况；不得升格为入排标准或缺失即不通过",
        "preserve_keywords": ["筛选访视时或首次给药前", "记录在eCRF的病史和基线状况中"],
    },
    "body.p1051": {
        "base_rule": "当符合以下标准时，既存疾病才应记录为不良事件",
        "exception_rule": "合取总纲：p1052与p1053两个列表项必须同时满足（AND）才将既存疾病记录为AE；不得把相邻两个列表项错误改成OR",
        "preserve_keywords": ["才应记录为不良事件"],
    },
    "body.p1052": {
        "base_rule": "发病的频次、严重程度或特征在研究期间恶化或改变",
        "exception_rule": "合取标准一：既存疾病在研究期间发病的频次、严重程度或特征恶化或改变；与p1053必须同时满足（AND）才记录为AE",
        "preserve_keywords": ["频次、严重程度或特征", "恶化或改变"],
    },
    "body.p1053": {
        "base_rule": "恶化或改变不是疾病的预期进展",
        "exception_rule": "合取标准二：恶化或改变不是疾病的预期进展时才记录为AE；与p1052必须同时满足（AND），不得把相邻两个列表项错误改成OR",
        "preserve_keywords": ["不是疾病的预期进展"],
    },
    "body.p1054": {
        "base_rule": "当在eCRF不良事件上记录此类事件时，重要的是要通过采用适当的描述语来体现既存疾病的变化，例如'偏头痛频次增加'",
        "exception_rule": "记录描述要求：记录既存疾病变化为AE时须采用适当描述语体现变化；'偏头痛频次增加'仅为示例，不得升格为唯一表达或通用病种条件",
        "preserve_keywords": ["适当的描述语", "体现既存疾病的变化"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"
SCREENING_PRE_EXISTING_RECORD_REF = "body.p988"
TEAE_DEFINITION_REF = "body.p994"
SAE_DEFINITION_REF = "body.p996"
SAE_OR_LEAD_REF = "body.p997"
RECORDING_OBLIGATION_REF = "body.p1024"
COLLECTION_WINDOW_REF = "body.p1022"
PRE_DOSE_EVENT_RECORD_REF = "body.p1023"
SINGLE_EVENT_TERM_REF = "body.p1026"
AE_RECORD_START_REF = "body.p340"
D1_PRE_DOSE_BASELINE_REF = "body.p885"
LAB_HEADING_REF = "body.p1037"
LAB_JUDGMENT_REF = "body.p1038"
LAB_OR_LEAD_REF = "body.p1039"
LAB_OR_ALT_CLINICAL_REF = "body.p1040"
LAB_OR_ALT_TREATMENT_REF = "body.p1041"
LAB_OR_ALT_MEDICAL_REF = "body.p1042"
PKG85_HEADING_REF = "body.p1055"
VITAL_SIGN_HEADING_REF = "body.p1043"
VITAL_SIGN_JUDGMENT_REF = "body.p1044"
VITAL_SIGN_OR_LEAD_REF = "body.p1045"
VITAL_SIGN_OR_ALT_CLINICAL_REF = "body.p1046"
VITAL_SIGN_OR_ALT_TREATMENT_REF = "body.p1047"
VITAL_SIGN_OR_ALT_MEDICAL_REF = "body.p1048"
PRE_EXISTING_HEADING_REF = "body.p1049"
PRE_EXISTING_DEFINITION_REF = "body.p1050"
PRE_EXISTING_AE_LEAD_REF = "body.p1051"
PRE_EXISTING_CRITERION_WORSENING_REF = "body.p1052"
PRE_EXISTING_CRITERION_NOT_EXPECTED_REF = "body.p1053"
PRE_EXISTING_DESCRIPTION_REF = "body.p1054"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_84_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _missing_exception_keywords(text: str, entry: dict) -> list[str]:
    """确定性合取/例外门禁：来源文本必须同时保留基础规则与例外条款关键词。"""
    return [kw for kw in entry["preserve_keywords"] if kw not in text]


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
    assert config["group_id"] == "d001-ii-package84-vital-sign-preexisting-disease-boundary"
    assert config["task_id"] == "phase5-slice61bv-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 12

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "两个章节标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第84包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第84包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持记录规则处置；结构单元不进入处置映射
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

    # 合取/例外/限定语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(EXCEPTION_SEMANTICS_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg84 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_84_ORDINAL
    )
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_84), "attached refs must not be owned by package 84"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 19


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in AE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [77], f"{ref} 必须保持归第77包"
    for ref in SAE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in RECORDING_ATTACHED_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ref in PKG83_LAB_PARALLEL_REFS:
        assert owners.get(ref) == [83], f"{ref} 必须保持归第83包"
    assert owners.get(PKG85_BOUNDARY_REF) == [85], "p1055 必须保持归第85包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第83包拥有p1033-p1042（10），第84包拥有p1043-p1054（12），
    第85包拥有p1055-p1066（12）。"""
    pkg83 = next(p for p in plan["packages"] if p["package_ordinal"] == 83)
    pkg84 = next(p for p in plan["packages"] if p["package_ordinal"] == 84)
    pkg85 = next(p for p in plan["packages"] if p["package_ordinal"] == 85)
    owned_83 = {u["source_ref"] for u in pkg83["owned_units"]}
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    owned_85 = {u["source_ref"] for u in pkg85["owned_units"]}
    assert set(PKG83_LAB_PARALLEL_REFS) <= owned_83 and len(owned_83) == 10
    assert set(OWNED_REFS) <= owned_84 and len(owned_84) == 12
    assert set(PKG85_SPAN_REFS) <= owned_85 and len(owned_85) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_84(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_84_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_84_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1043"] == "生命体征异常"
    assert excerpts["body.p1044"] == (
        "研究者负责审查所有生命体征结果，通过医学和科学判断一项孤立的生命体征值"
        "异常是否应归类为不良事件。"
    )
    assert excerpts["body.p1045"] == "当生命体征异常符合以下任一标准时，则必须报告为不良事件："
    assert excerpts["body.p1046"] == "伴有临床症状"
    assert excerpts["body.p1047"] == "导致研究治疗发生变化（例如治疗暂停或治疗终止）"
    assert excerpts["body.p1048"] == "导致医学干预或伴随治疗改变"
    assert excerpts["body.p1049"] == "既存（合并）疾病"
    assert excerpts["body.p1050"] == (
        "既存疾病（事先存在的疾病）是指在本研究的筛选访视时或首次给药前即已存在的"
        "疾病，此类状况应记录在eCRF的病史和基线状况中。"
    )
    assert excerpts["body.p1051"] == "当符合以下标准时，既存疾病才应记录为不良事件："
    assert excerpts["body.p1052"] == "发病的频次、严重程度或特征在研究期间恶化或改变；"
    assert excerpts["body.p1053"] == "恶化或改变不是疾病的预期进展。"
    assert excerpts["body.p1054"] == (
        "当在eCRF不良事件上记录此类事件时，重要的是要通过采用适当的描述语来体现"
        "既存疾病的变化，例如“偏头痛频次增加”。"
    )


# ---------------------------------------------------------------------------
# structural-only units and semantic rows
# ---------------------------------------------------------------------------


def test_structural_units_do_not_form_control_points(config: dict, plan: dict) -> None:
    """两个章节标题（p1043/p1049）不形成控制点；十个语义单元保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1043"] == "生命体征异常"
    assert excerpts["body.p1049"] == "既存（合并）疾病"
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1037-p1042 -> 83, p1055 -> 85
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """后续包来源可只读进入闭包，但不得改变所有权或由第84包发射。"""
    boundary = config["later_package_boundary"]
    expected_later = set(LATER_PKG83_REFS + [PKG85_BOUNDARY_REF])
    assert set(boundary["expected_owners_by_span"]) == expected_later | set(OWNED_REFS)
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 84
    for ref in LATER_PKG83_REFS:
        assert boundary["expected_owners_by_span"][ref] == 83
    assert boundary["expected_owners_by_span"][PKG85_BOUNDARY_REF] == 85
    assert expected_later.isdisjoint(set(config["owned_source_refs"])), (
        "第83包实验室规则与第85包标题不得被第84包拥有"
    )
    attached = set(config["attached_source_refs"])
    assert set(LATER_PKG83_REFS) <= attached
    assert PKG85_BOUNDARY_REF in attached
    assert set(PKG85_SPAN_REFS[1:]).isdisjoint(attached), (
        "第85包p1056及以后不得进入第84包提示"
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
        assert expected_ordinal != PACKAGE_84_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第84包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第83包", "第84包", "第85包", "吞并", "第90", "第92", "24小时报告"):
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
    assert "医学和科学判断" in by_ref["body.p1044"].excerpt
    assert "任一标准" in by_ref["body.p1045"].excerpt
    assert "必须报告为不良事件" in by_ref["body.p1045"].excerpt
    assert "伴有临床症状" in by_ref["body.p1046"].excerpt
    assert "治疗暂停" in by_ref["body.p1047"].excerpt
    assert "伴随治疗改变" in by_ref["body.p1048"].excerpt
    assert "病史和基线状况" in by_ref["body.p1050"].excerpt
    assert "才应记录为不良事件" in by_ref["body.p1051"].excerpt
    assert "恶化或改变" in by_ref["body.p1052"].excerpt
    assert "不是疾病的预期进展" in by_ref["body.p1053"].excerpt
    assert "偏头痛频次增加" in by_ref["body.p1054"].excerpt

    # 只读闭包关键片段
    assert "有临床意义的实验室检查异常" in by_ref[AE_DEFINITION_REF].excerpt
    assert "作为病史/伴随疾病进行记录" in by_ref[SCREENING_PRE_EXISTING_RECORD_REF].excerpt
    assert "给药后出现" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "不作为AE记录" in by_ref[PRE_DOSE_EVENT_RECORD_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_EVENT_TERM_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt
    assert "D1给药前结果作为基线值" in by_ref[D1_PRE_DOSE_BASELINE_REF].excerpt
    # 第83包实验室异常平行结构（防混同语境）
    assert by_ref[LAB_HEADING_REF].excerpt == "实验室检查值异常"
    assert "孤立的实验室检查值异常" in by_ref[LAB_JUDGMENT_REF].excerpt
    assert "任一标准" in by_ref[LAB_OR_LEAD_REF].excerpt
    assert by_ref[LAB_OR_ALT_CLINICAL_REF].excerpt == "伴有临床症状或体征"
    assert "治疗暂停" in by_ref[LAB_OR_ALT_TREATMENT_REF].excerpt
    assert "合并用药/治疗改变" in by_ref[LAB_OR_ALT_MEDICAL_REF].excerpt
    # 第85包防吞并边界标题
    assert by_ref[PKG85_HEADING_REF].excerpt == "严重肝损伤与肝功能检查异常"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含第83包实验室平行结构、前接规范与防吞并边界，
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

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 19
    assert summary["unit_count"] == 31
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

    # 越界候选（把既存疾病记录升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1050"]],
                "title": "筛选时核对既存疾病记录，未记录者按证据缺口判定入排不通过",
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
    """确定性门禁必须拒绝把记录规则改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1044": [
            "筛选时核对生命体征判断能力，证据不足者不得入组",
            "基线期完成生命体征异常判断确认，未确认者入排不通过",
        ],
        "body.p1045": [
            "筛选时评估生命体征异常报告能力，证据不足者按排除标准判定不通过",
            "生命体征异常报告安排未完成者不得入组",
        ],
        "body.p1046": [
            "筛选时核对生命体征伴临床症状报告安排，未安排者证据缺口不得入组",
        ],
        "body.p1047": [
            "筛选时核对生命体征导致治疗变化报告安排，未确认者入排不通过",
        ],
        "body.p1048": [
            "生命体征导致医学干预报告安排未完成者不得入组",
        ],
        "body.p1050": [
            "筛选时核对既存疾病记录，未记录者证据缺口不得入组",
            "既存疾病未记录于基线状况者按排除标准判定入排不通过",
        ],
        "body.p1051": [
            "筛选时核对既存疾病AE记录能力，证据不足者不得入组",
        ],
        "body.p1052": [
            "基线期核对既存疾病恶化记录安排，未确认者入排不通过",
        ],
        "body.p1053": [
            "筛选时核对预期进展判定能力，证据不足者不得入组",
        ],
        "body.p1054": [
            "筛选时核对既存疾病描述语记录安排，未完成者不得入组",
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
    """判断/强制报告、OR结构、合取结构与记录边界关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或记录路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1044": "生命体征异常只要出现即归类为不良事件。",
        "body.p1045": "生命体征异常符合所有标准时报告为不良事件。",
        "body.p1046": "生命体征异常应报告为不良事件。",
        "body.p1047": "生命体征异常导致治疗变化。",
        "body.p1048": "生命体征异常导致干预或治疗改变。",
        "body.p1050": "既存疾病应记录于受试者入组条件中。",
        "body.p1051": "既存疾病符合任一标准即记录为不良事件。",
        "body.p1052": "既存疾病在研究期间出现变化。",
        "body.p1053": "既存疾病恶化即记录为不良事件。",
        "body.p1054": "记录既存疾病变化为不良事件。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# vital-sign judgment vs OR mandatory reporting layering
# ---------------------------------------------------------------------------


def test_judgment_never_becomes_automatic_classification(config: dict, plan: dict) -> None:
    """p1044 是研究者医学和科学判断；不得改写为只要异常即为AE或未否定即为AE。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1044"]
    for fragment in ("医学和科学判断", "孤立的生命体征值异常", "是否应归类为不良事件"):
        assert fragment in excerpt, f"p1044 丢失片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1044"]
    assert "不得改写为'只要异常即为AE'或'只要研究者未明确否定即为AE'" in entry["exception_rule"]

    judgment_collapsed = [
        "生命体征异常只要出现即为不良事件。",
        "生命体征异常若研究者未明确否定即归为不良事件。",
        "所有生命体征异常一律归类为不良事件。",
    ]
    for text in judgment_collapsed:
        assert _missing_exception_keywords(text, entry), f"p1044判断崩塌反例未被拦截: {text}"


def test_mandatory_report_not_weakened_by_judgment(config: dict) -> None:
    """专业判断层不得弱化强制报告层；强制报告层不得扩成任何异常一律报告。"""
    p1044 = config["exception_semantics_by_source_ref"]["body.p1044"]
    p1045 = config["exception_semantics_by_source_ref"]["body.p1045"]
    assert "判断层不得与p1045-p1048强制报告层混同" in p1044["exception_rule"]
    assert "不得用专业判断弱化p1045-p1048'满足任一标准必须报告'" in p1044["forbidden_inversion"]
    assert "不得把'必须报告'弱化为'可报告'" in p1045["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "判断层不得与p1045-p1048强制报告层混同" in checks_blob


# ---------------------------------------------------------------------------
# OR structure for vital signs: never inverted to AND, alternatives distinct
# ---------------------------------------------------------------------------


def test_vital_sign_or_lead_never_inverted_to_and(config: dict, plan: dict) -> None:
    """p1045 '任一标准' 保持OR；不得反转为AND。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1045"]
    assert "任一标准" in excerpt
    assert "必须报告为不良事件" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1045"]
    assert "不得改成AND" in entry["exception_rule"]
    assert "不得把'必须报告'弱化为'可报告'" in entry["exception_rule"]

    and_inverted = [
        "生命体征异常同时满足以下所有标准时，则必须报告为不良事件。",
        "生命体征异常需全部符合下列标准才报告为不良事件。",
        "生命体征异常须同时伴有症状且导致治疗变化且导致干预才报告。",
    ]
    for text in and_inverted:
        assert _missing_exception_keywords(text, entry), f"OR反AND反例未被拦截: {text}"


def test_vital_sign_or_alternatives_stay_parallel_and_distinct(config: dict, plan: dict) -> None:
    """p1046/p1047/p1048 三个OR备选保持并列，任一满足即可，不得互相替代。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1046"] == "伴有临床症状"
    assert excerpts["body.p1047"] == "导致研究治疗发生变化（例如治疗暂停或治疗终止）"
    assert excerpts["body.p1048"] == "导致医学干预或伴随治疗改变"
    for ref in ("body.p1046", "body.p1047", "body.p1048"):
        entry = config["exception_semantics_by_source_ref"][ref]
        assert "不得互相替代" in entry["exception_rule"]
        assert "并列备选" in entry["exception_rule"]

    # 备选互替反例必须被门禁拦截（任一备选文案被另一备选替换后丢失本备选关键词）
    substituted = {
        "body.p1046": "导致研究治疗发生变化。",
        "body.p1047": "导致医学干预或伴随治疗改变。",
        "body.p1048": "伴有临床症状。",
    }
    semantics = config["exception_semantics_by_source_ref"]
    for ref, text in substituted.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 备选互替反例未被拦截: {text}"
        )


def test_vital_sign_nested_or_and_examples_preserve_source_logic(config: dict) -> None:
    """三个备选内部的OR与示例边界也必须保留，不能只锁定外层OR。"""
    semantics = config["exception_semantics_by_source_ref"]
    p1047 = semantics["body.p1047"]
    p1048 = semantics["body.p1048"]
    assert "仅为研究治疗变化的并列示例" in p1047["exception_rule"]
    assert "不是穷尽范围" in p1047["exception_rule"]
    assert "医学干预与伴随治疗改变为本备选内的OR" in p1048["exception_rule"]
    assert "两者同时发生" in p1048["forbidden_inversion"]

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "不是穷尽范围" in "\n".join(checks["body.p1047"])
    assert "任一出现即可" in "\n".join(checks["body.p1048"])


def test_vital_sign_lab_verbatim_differences_preserved(config: dict, plan: dict) -> None:
    """p1046 无'或体征'、p1048 '伴随治疗改变' 与实验室版文字差异必须保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1046"] == "伴有临床症状"
    assert excerpts["body.p1048"] == "导致医学干预或伴随治疗改变"
    entry1046 = config["exception_semantics_by_source_ref"]["body.p1046"]
    entry1048 = config["exception_semantics_by_source_ref"]["body.p1048"]
    assert "无'或体征'" in entry1046["exception_rule"]
    assert "不得把'伴有临床症状'改写为'伴有临床症状或体征'" in entry1046["forbidden_inversion"]
    assert "不得替换为实验室版p1042'合并用药/治疗改变'" in entry1048["exception_rule"]
    assert "不得把'伴随治疗改变'改写为'合并用药/治疗改变'" in entry1048["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "文字不同" in checks_blob
    assert "与第83包p1042'合并用药/治疗改变'文字不同" in checks_blob


# ---------------------------------------------------------------------------
# pre-existing disease: AND conjunction, never OR, never enrollment escalation
# ---------------------------------------------------------------------------


def test_pre_existing_ae_conjunction_never_inverted_to_or(
    config: dict, plan: dict
) -> None:
    """p1051-p1053 必须解析为同时满足的条件：恶化/改变 且 非预期进展。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1051"] == "当符合以下标准时，既存疾病才应记录为不良事件："
    assert excerpts["body.p1052"] == "发病的频次、严重程度或特征在研究期间恶化或改变；"
    assert excerpts["body.p1053"] == "恶化或改变不是疾病的预期进展。"
    p1051 = config["exception_semantics_by_source_ref"]["body.p1051"]
    p1052 = config["exception_semantics_by_source_ref"]["body.p1052"]
    p1053 = config["exception_semantics_by_source_ref"]["body.p1053"]
    assert "必须同时满足" in p1051["exception_rule"]
    assert "不得把相邻两个列表项错误改成OR" in p1051["exception_rule"]
    assert "不得把p1052与p1053拆成独立可触发记录的条件（OR）" in p1052["forbidden_inversion"]
    assert "必须与p1052同时满足（AND）" in p1053["exception_rule"]
    assert "不得把p1053与p1052改写成OR" in p1053["forbidden_inversion"]

    or_inverted = [
        "既存疾病符合任一标准即记录为不良事件。",
        "既存疾病恶化或属于非预期进展任一情形即记录为不良事件。",
        "既存疾病在研究期间恶化时记录为不良事件；或变化不属于预期进展时记录为不良事件。",
    ]
    for text in or_inverted:
        assert _missing_exception_keywords(text, p1051), f"合取反OR反例未被拦截: {text}"
    dropped_not_expected = "既存疾病恶化或改变即记录为不良事件。"
    assert _missing_exception_keywords(dropped_not_expected, p1053), (
        "p1053 非预期进展限定丢失反例未被拦截"
    )
    # 两个条件缺一不可：预期进展不能记录为AE；仅声明“非预期”但没有恶化/改变也不能记录为AE。
    expected_progression = "既存疾病在研究期间恶化，但属于疾病的预期进展。"
    assert _missing_exception_keywords(expected_progression, p1053)
    assert "不得把明确未发生恶化或改变解释为满足p1052" in p1052["forbidden_inversion"]


def test_adjacent_pre_existing_recording_context_never_becomes_new_premise(config: dict) -> None:
    """p988/p1023 只解释给药前记录路径，不给p1051-p1053增加临床意义或入排前提。"""
    checks = config["clinical_qc_checks_by_source_ref"]
    p988 = "\n".join(checks[SCREENING_PRE_EXISTING_RECORD_REF])
    p1023 = "\n".join(checks[PRE_DOSE_EVENT_RECORD_REF])
    assert "仅说明筛选时发现的既存情况如何归档" in p988
    assert "不得把筛选时的临床意义判断补成p1050-p1053未写明的额外前提" in p988
    assert "给药前事件的记录路径" in p1023
    assert "不成为p1051-p1053的逻辑前提" in p1023
    assert "不形成筛选/基线入排门槛" in p1023


def test_pre_existing_conjunction_not_collapsed_into_vital_sign_or(config: dict) -> None:
    """生命体征OR结构不得套用到既存疾病记录；合取结构不得扩成OR强制报告。"""
    p1045 = config["exception_semantics_by_source_ref"]["body.p1045"]
    p1051 = config["exception_semantics_by_source_ref"]["body.p1051"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "与p1045-p1048生命体征'任一标准必须报告'OR结构相反" in checks_blob
    assert "不得把生命体征OR结构套用到既存疾病记录" in checks_blob
    assert "不得把生命体征OR结构（p1045-p1048）套用到既存疾病记录" in p1051["forbidden_inversion"]
    assert "conjunction" in p1051["semantic_role"]


def test_pre_existing_definition_stays_documentation_boundary(
    config: dict, plan: dict
) -> None:
    """p1050 是资料记录边界：记录于病史和基线状况，不得升格为入排标准。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1050"]
    assert "筛选访视时或首次给药前" in excerpt
    assert "记录在eCRF的病史和基线状况中" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1050"]
    assert "资料记录边界" in entry["exception_rule"]
    assert "不得升格为入排标准" in entry["exception_rule"]
    assert "缺失即不通过" in entry["exception_rule"]
    assert "不得把'筛选访视时或首次给药前'改成其他时点" in entry["forbidden_inversion"]

    escalated = [
        "筛选时核对既存疾病是否已记录于基线状况，未记录者不得入组。",
        "既存疾病记录缺失视为证据缺口，入排不通过。",
    ]
    for text in escalated:
        assert _forbidden_marker_hits(
            text, config["candidate_forbidden_markers_by_source_ref"]["body.p1050"]
        ), f"p1050 升格反例未被拦截: {text}"


def test_pre_existing_description_example_not_escalated(config: dict, plan: dict) -> None:
    """p1054 '偏头痛频次增加'是示例，不得升格为唯一表达或通用病种条件。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1054"]
    assert "适当的描述语" in excerpt
    assert "体现既存疾病的变化" in excerpt
    assert "偏头痛频次增加" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1054"]
    assert "仅为示例" in entry["exception_rule"]
    assert "不得升格为唯一表达或通用病种条件" in entry["exception_rule"]
    assert "不得把“偏头痛频次增加”升格为唯一表达或通用病种条件" in entry["forbidden_inversion"]


# ---------------------------------------------------------------------------
# package 83 lab parallel structure stays read-only; package 85 boundary
# ---------------------------------------------------------------------------


def test_package83_lab_parallel_structure_read_only(config: dict) -> None:
    """第83包实验室异常平行结构只以防混同进入；与生命体征规则不得互换。"""
    attached = set(config["attached_source_refs"])
    assert set(LATER_PKG83_REFS) <= attached
    assert set(LATER_PKG83_REFS).isdisjoint(set(config["owned_source_refs"]))
    for ref in LATER_PKG83_REFS:
        checks = "\n".join(config["clinical_qc_checks_by_source_ref"][ref])
        assert "归第83包" in checks, f"{ref} 缺少第83包所有权声明"
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "结构平行" in checks_blob
    assert "不得与p1044生命体征判断规则互换" in checks_blob
    assert "不得与p1045生命体征OR总纲互换" in checks_blob
    assert "与p1046'伴有临床症状'不同" in checks_blob
    assert "与p1048'伴随治疗改变'不同" in checks_blob


def test_package85_hepatic_sae_not_absorbed(config: dict) -> None:
    """第85包特殊肝功能SAE（p1055起）仅标题防吞并只读进入，p1056及以后不进入。"""
    attached = set(config["attached_source_refs"])
    assert PKG85_BOUNDARY_REF in attached
    assert set(PKG85_SPAN_REFS[1:]).isdisjoint(attached)
    assert set(PKG85_SPAN_REFS).isdisjoint(set(config["owned_source_refs"]))
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"][PKG85_BOUNDARY_REF])
    assert "归第85包" in checks
    assert "本包不提前吞并或处置" in checks
    note = config["later_package_boundary"]["note"]
    assert "特殊肝功能SAE" in note


def test_prompt_excludes_later_package_sources() -> None:
    """第85包p1056及以后内容不得进入提示；p1055仅标题进入。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "严重肝损伤与肝功能检查异常" in prompt_text
    for leaked in (
        "海氏定律",
        "ALT或AST",
        "Hy’s law",
        "24小时",
        "共同判断",
        "PASI75",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第84包提示: {leaked}"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第84包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_lab_parallel_and_package85_boundary() -> None:
    """提示必须包含第83包实验室平行结构、定义锚点与第85包防吞并标题。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "实验室检查值异常" in prompt_text
    assert "孤立的实验室检查值异常" in prompt_text
    assert "严重肝损伤与肝功能检查异常" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert "伴有临床症状或体征" in by_ref[LAB_OR_ALT_CLINICAL_REF]["excerpt"]
    assert by_ref["body.p1038"]["role"] == "attached"
    assert by_ref[PKG85_BOUNDARY_REF]["role"] == "attached"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package84(matrix: dict, plan: dict) -> None:
    pkg84 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_84_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg84["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第84包拥有来源为锚点"
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
            if ref.startswith("body.t12"):
                raise AssertionError(f"{row['matrix_row_id']} 锚点 {ref} 落在表7内")
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package84_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg84 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_84_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg84["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第84包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package84_or_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            if ref.startswith("body.t12"):
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以表7来源 {ref} 为来源"
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
    assert PACKAGE_84_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "医学和科学判断" in text
    assert "只要异常即为AE" in text and "只要研究者未明确否定即为AE" in text
    assert "任一标准" in text and "必须报告为不良事件" in text
    assert "不得改成AND" in text
    assert "才应记录为不良事件" in text
    assert "不是疾病的预期进展" in text
    assert "不得把相邻两个列表项错误改成OR" in text
    assert "偏头痛频次增加" in text and "仅为示例" in text
    assert "病史和基线状况" in text
    assert "body.p1043" in text and "body.p1054" in text
    assert "body.p1037" in text and "body.p1042" in text
    assert "body.p1055" in text
    assert "第83包" in text and "第84包" in text and "第85包" in text
    assert "第90" in text and "第92" in text
