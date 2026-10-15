#!/usr/bin/env python3
"""Slice61bu model-free source-closure regressions.

Locks the D001 II package 83 persistent/recurrent AE and laboratory
abnormality recording boundary (frozen plan package 83: 持续性或复发性不良
事件与实验室检查值异常记录规则, body.p1033-p1042) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 83 (A/B notation note + 2 structural
  headings + 7 semantic rules); attached refs stay read-only
- structural units (p1033/p1034/p1037) stay structural only; seven semantic
  units keep post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- persistent/recurrent boundary: p1035 持续不消失仅记录一次, never
  extrapolated to merging all repeated manifestations; p1036 消失后再次发生
  每次复发单独记录, never treating un-resolved fluctuation as recurrence
- professional judgment (p1038) vs OR mandatory reporting (p1039-p1042)
  stay layered: judgment never becomes "只要异常即为AE" or "只要研究者未
  明确否定即为AE"; mandatory reporting never weakened by judgment, never
  expanded to all abnormalities
- OR structure never inverted to AND: p1039 "任一标准" keeps OR; the three
  alternatives p1040/p1041/p1042 stay parallel and non-interchangeable
- lab abnormality rules never escalate to screening/baseline enrollment
  thresholds
- table 7 (body.t12.r0-r4) enters only as p1033's direct read-only table
  context owned by package 82; package 83 never re-publishes the four-row
  rules
- package 84 vital-sign parallel rules (p1043-p1048) enter only as
  anti-conflation read-only context; package 84 remaining sources
  (p1049-p1054) and packages 85-99 stay out of the prompt
- official matrix keeps zero rows anchored in p1033-p1042/p985-p1100 and
  zero 不良事件 / TEAE / SAE rows; procedure catalog has no AE node and no
  p1033-p1042 source spans
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
    / "representative_group_package83_persistent_recurrent_lab_ae_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61bu-package83-persistent-recurrent-lab-ae-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package83-persistent-recurrent-lab-ae-boundary"
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
PACKAGE_83_ORDINAL = 83
PACKAGE_83_ID = "pap-2090ba6d6c3314d6edeb957f"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1033, 1043)]

# 结构单元：A/B记号说明与两个章节标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1033", "body.p1034", "body.p1037"]
# 语义单元：持续/复发边界、专业判断与OR强制报告结构，保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = [
    "body.p1035",
    "body.p1036",
    "body.p1038",
    "body.p1039",
    "body.p1040",
    "body.p1041",
    "body.p1042",
]

# 只读闭包：第81包诊断/命名与前接记录规范（6）、第82包表7（5）、
# AE/TEAE/SAE定义与严重性总纲（4）、AE收集期/全量记录义务/单一事件项一术语（3）、
# 流程/监测/D1给药前锚点（3）、第84包生命体征异常防混同语境（6）
PKG81_PRECEDING_REFS = [f"body.p{ordinal}" for ordinal in range(1027, 1033)]
PKG82_TABLE7_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
AE_DEF_ATTACHED_REFS = ["body.p986", "body.p994"]
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1024", "body.p1026"]
FLOW_ANCHOR_REFS = ["body.p340", "body.p835", "body.p885"]
PKG84_ANTI_CONFLATION_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1049)]
UNOWNED_CONTEXT_REFS = ["body.p340", "body.p885"]
ATTACHED_REFS = (
    PKG81_PRECEDING_REFS
    + PKG82_TABLE7_REFS
    + AE_DEF_ATTACHED_REFS
    + SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
    + PKG84_ANTI_CONFLATION_REFS
)

# 后续包所有权：第82包表7与第84包生命体征防混同只读进入，所有权不变；
# 第84包既存疾病及第85-99包只保留所有权元数据
LATER_PKG82_REFS = PKG82_TABLE7_REFS
LATER_PKG84_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]
PKG84_META_ONLY_REFS = [f"body.p{ordinal}" for ordinal in range(1049, 1055)]

# 各语义单元的持续/复发、判断/强制报告、OR结构语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1035": {
        "base_rule": "持续性不良事件是指在评估时点之间持续延伸而不消失的不良事件，此类事件在eCRF不良事件页中应仅记录一次",
        "exception_rule": "持续性边界：仅在评估时点间持续而不消失时记录一次；不得外推为所有重复出现的表现合并记录，也不得把未消失的持续波动误判为复发",
        "preserve_keywords": ["持续延伸而不消失", "仅记录一次"],
    },
    "body.p1036": {
        "base_rule": "复发性不良事件是指在评估时点之间消失的事件随后复发。不良事件的每次复发应在eCRF不良事件页上记录成单独的事件",
        "exception_rule": "复发性边界：仅在事件消失后再次发生时，每次复发单独记录；不得把未消失的持续波动误判为复发，也不得与表7（body.t12）分别单独报告混同",
        "preserve_keywords": ["消失的事件随后复发", "每次复发", "单独的事件"],
    },
    "body.p1038": {
        "base_rule": "研究者负责审查所有实验室检查结果，通过医学和科学判断一个孤立的实验室检查值异常是否应归类为不良事件",
        "exception_rule": "专业判断层：研究者的医学和科学判断用于判断孤立实验室异常是否应归类为AE；不得改写为'只要异常即为AE'或'只要研究者未明确否定即为AE'；判断层不得与p1039-p1042强制报告层混同",
        "preserve_keywords": ["医学和科学判断", "孤立的实验室检查值异常", "是否应归类为不良事件"],
    },
    "body.p1039": {
        "base_rule": "当实验室检查值异常符合以下任一标准时，则必须报告为不良事件",
        "exception_rule": "OR强制报告总纲：p1040/p1041/p1042任一标准满足即必须报告为AE；不得改成AND，不得把'必须报告'弱化为'可报告'",
        "preserve_keywords": ["任一标准", "必须报告为不良事件"],
    },
    "body.p1040": {
        "base_rule": "伴有临床症状或体征",
        "exception_rule": "OR备选一：实验室异常伴有临床症状或体征即满足强制报告标准；与p1041/p1042并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["伴有临床症状或体征"],
    },
    "body.p1041": {
        "base_rule": "导致研究治疗发生变化（例如治疗暂停或治疗终止）",
        "exception_rule": "OR备选二：实验室异常导致研究治疗发生变化（如治疗暂停或终止）即满足强制报告标准；与p1040/p1042并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["导致研究治疗发生变化", "治疗暂停", "治疗终止"],
    },
    "body.p1042": {
        "base_rule": "导致医学干预或合并用药/治疗改变",
        "exception_rule": "OR备选三：实验室异常导致医学干预或合并用药/治疗改变即满足强制报告标准；与p1040/p1041并列备选，任一满足即可，不得互相替代",
        "preserve_keywords": ["导致医学干预", "合并用药/治疗改变"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"
TEAE_DEFINITION_REF = "body.p994"
SAE_DEFINITION_REF = "body.p996"
SAE_OR_LEAD_REF = "body.p997"
RECORDING_OBLIGATION_REF = "body.p1024"
COLLECTION_WINDOW_REF = "body.p1022"
SINGLE_EVENT_TERM_REF = "body.p1026"
AE_RECORD_START_REF = "body.p340"
LAB_VALUE_RECORDING_REF = "body.p1029"  # 无法明确诊断时记录实验室异常值本身
TABLE7_CAPTION_REF = "body.p1032"
AB_NOTATION_REF = "body.p1033"
VITAL_SIGN_JUDGMENT_REF = "body.p1044"  # 第84包生命体征判断（防混同）
VITAL_SIGN_OR_LEAD_REF = "body.p1045"  # 第84包生命体征OR总纲（防混同）


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_83_ORDINAL
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
    assert config["group_id"] == "d001-ii-package83-persistent-recurrent-lab-ae-boundary"
    assert config["task_id"] == "phase5-slice61bu-20260830"
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
    assert structural == set(STRUCTURAL_REFS), "A/B记号说明与结构标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第83包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第83包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗期处置；结构单元不进入处置映射
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
        assert len(entry["preserve_keywords"]) >= 2, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg83 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_83_ORDINAL
    )
    owned_83 = {u["source_ref"] for u in pkg83["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_83), "attached refs must not be owned by package 83"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 27


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PKG81_PRECEDING_REFS:
        assert owners.get(ref) == [81], f"{ref} 必须保持归第81包"
    for ref in PKG82_TABLE7_REFS:
        assert owners.get(ref) == [82], f"{ref} 必须保持归第82包"
    for ref in AE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [77], f"{ref} 必须保持归第77包"
    for ref in SAE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in RECORDING_ATTACHED_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ref in PKG84_ANTI_CONFLATION_REFS:
        assert owners.get(ref) == [84], f"{ref} 必须保持归第84包"
    for ref in PKG84_META_ONLY_REFS:
        assert owners.get(ref) == [84], f"{ref} 必须保持归第84包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第81包拥有p1027-p1032（6），第82包拥有t12.r0-r4（5），
    第83包拥有p1033-p1042（10），第84包拥有p1043-p1054（12）。"""
    pkg81 = next(p for p in plan["packages"] if p["package_ordinal"] == 81)
    pkg82 = next(p for p in plan["packages"] if p["package_ordinal"] == 82)
    pkg83 = next(p for p in plan["packages"] if p["package_ordinal"] == 83)
    pkg84 = next(p for p in plan["packages"] if p["package_ordinal"] == 84)
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    owned_82 = {u["source_ref"] for u in pkg82["owned_units"]}
    owned_83 = {u["source_ref"] for u in pkg83["owned_units"]}
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    assert set(PKG81_PRECEDING_REFS) <= owned_81 and len(owned_81) == 6
    assert set(LATER_PKG82_REFS) <= owned_82 and len(owned_82) == 5
    assert set(OWNED_REFS) <= owned_83 and len(owned_83) == 10
    assert set(LATER_PKG84_REFS) <= owned_84 and len(owned_84) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_83(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_83_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_83_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1033"] == "注：以上示例将初始事件记为事件A，继发事件记为事件B。"
    assert excerpts["body.p1034"] == "持续性或复发性不良事件"
    assert excerpts["body.p1035"] == (
        "持续性不良事件是指在评估时点之间持续延伸而不消失的不良事件，此类事件在eCRF"
        "不良事件页中应仅记录一次。"
    )
    assert excerpts["body.p1036"] == (
        "复发性不良事件是指在评估时点之间消失的事件随后复发。不良事件的每次复发应在"
        "eCRF不良事件页上记录成单独的事件。"
    )
    assert excerpts["body.p1037"] == "实验室检查值异常"
    assert excerpts["body.p1038"] == (
        "研究者负责审查所有实验室检查结果，通过医学和科学判断一个孤立的实验室检查值"
        "异常是否应归类为不良事件。"
    )
    assert excerpts["body.p1039"] == "当实验室检查值异常符合以下任一标准时，则必须报告为不良事件："
    assert excerpts["body.p1040"] == "伴有临床症状或体征"
    assert excerpts["body.p1041"] == "导致研究治疗发生变化（例如治疗暂停或治疗终止）"
    assert excerpts["body.p1042"] == "导致医学干预或合并用药/治疗改变"


# ---------------------------------------------------------------------------
# structural-only units and semantic rows
# ---------------------------------------------------------------------------


def test_structural_units_do_not_form_control_points(config: dict, plan: dict) -> None:
    """A/B注记（p1033）与两个结构标题（p1034/p1037）不形成控制点；
    七个语义单元保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1033"].startswith("注：以上示例")
    assert "记号说明" in "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1033"])
    assert excerpts["body.p1034"] == "持续性或复发性不良事件"
    assert excerpts["body.p1037"] == "实验室检查值异常"
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: t12.r0-r4 -> 82, p1043-p1054 -> 84
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """后续包来源可只读进入闭包，但不得改变所有权或由第83包发射。"""
    boundary = config["later_package_boundary"]
    expected_later = set(LATER_PKG82_REFS + LATER_PKG84_REFS)
    assert set(boundary["expected_owners_by_span"]) == expected_later | set(OWNED_REFS)
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 83
    for ref in LATER_PKG82_REFS:
        assert boundary["expected_owners_by_span"][ref] == 82
    for ref in LATER_PKG84_REFS:
        assert boundary["expected_owners_by_span"][ref] == 84
    assert expected_later.isdisjoint(set(config["owned_source_refs"])), (
        "第82包表7与第84包细则不得被第83包拥有"
    )
    attached = set(config["attached_source_refs"])
    assert set(LATER_PKG82_REFS) <= attached
    assert set(PKG84_ANTI_CONFLATION_REFS) <= attached
    assert set(PKG84_META_ONLY_REFS).isdisjoint(attached), (
        "第84包既存（合并）疾病规则不得进入第83包提示"
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
        assert expected_ordinal != PACKAGE_83_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第83包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第81包", "第82包", "第83包", "第84包", "吞并", "第85", "第90", "第92", "24小时报告"):
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
    assert "持续延伸而不消失" in by_ref["body.p1035"].excerpt
    assert "仅记录一次" in by_ref["body.p1035"].excerpt
    assert "消失的事件随后复发" in by_ref["body.p1036"].excerpt
    assert "每次复发" in by_ref["body.p1036"].excerpt
    assert "医学和科学判断" in by_ref["body.p1038"].excerpt
    assert "任一标准" in by_ref["body.p1039"].excerpt
    assert "必须报告为不良事件" in by_ref["body.p1039"].excerpt
    assert "伴有临床症状或体征" in by_ref["body.p1040"].excerpt
    assert "治疗暂停" in by_ref["body.p1041"].excerpt
    assert "合并用药/治疗改变" in by_ref["body.p1042"].excerpt

    # 只读闭包关键片段
    assert "有临床意义的实验室检查异常" in by_ref[AE_DEFINITION_REF].excerpt
    assert "给药后出现" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_EVENT_TERM_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt
    assert "记录实验室异常值本身" in by_ref[LAB_VALUE_RECORDING_REF].excerpt
    assert by_ref[TABLE7_CAPTION_REF].excerpt == "表 7 应记录的继发于其它事件的不良事件"
    assert "初始事件记为事件A，继发事件记为事件B" in by_ref[AB_NOTATION_REF].excerpt
    # 表7四行规则全文只读进入（第82包所有权）
    for row in LATER_PKG82_REFS:
        assert by_ref[row].excerpt.strip(), f"{row} 未进入表7只读语境"
    # 第84包生命体征防混同语境
    assert "医学和科学判断一项孤立的生命体征值异常" in by_ref[VITAL_SIGN_JUDGMENT_REF].excerpt
    assert "生命体征异常符合以下任一标准" in by_ref[VITAL_SIGN_OR_LEAD_REF].excerpt
    # 第84包既存疾病不得进入
    for ref in PKG84_META_ONLY_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第83包闭包"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含表7只读语境、前接规范与防混同语境，
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
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 27
    assert summary["unit_count"] == 37
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

    # 越界候选（把实验室异常强制报告升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1039"]],
                "title": "筛选时评估实验室异常报告能力，证据不足者入排不通过",
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
    """确定性门禁必须拒绝把实验室异常强制报告改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1035": [
            "筛选时核对持续性AE记录次数，不合格者视为证据缺口",
            "基线期完成持续AE单次记录确认，未完成者不得入组",
        ],
        "body.p1036": [
            "筛选时评估复发性AE单独记录能力，不合格者按排除标准判定入排不通过",
            "复发单独记录安排未完成者不得入组",
        ],
        "body.p1038": [
            "筛选时核对实验室异常归类判断能力，证据不足者不得入组",
            "基线期完成实验室异常判断确认，未确认者入排不通过",
        ],
        "body.p1039": [
            "筛选时评估实验室异常报告能力，证据不足者按排除标准判定不通过",
            "实验室异常报告安排未完成者不得入组",
        ],
        "body.p1040": [
            "筛选时核对实验室异常伴临床症状报告安排，未安排者证据缺口不得入组",
        ],
        "body.p1041": [
            "筛选时核对实验室异常导致治疗变化报告安排，未确认者入排不通过",
        ],
        "body.p1042": [
            "实验室异常导致医学干预报告安排未完成者不得入组",
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
    """持续/复发、判断/强制报告、OR结构的关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或记录路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1035": "重复出现的不良事件合并记录一次。",
        "body.p1036": "反复出现的不良事件单独记录。",
        "body.p1038": "实验室异常只要出现即归类为不良事件。",
        "body.p1039": "实验室检查值异常符合所有标准时报告为不良事件。",
        "body.p1040": "实验室异常应报告为不良事件。",
        "body.p1041": "实验室异常导致治疗变化。",
        "body.p1042": "实验室异常导致干预或治疗改变。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# persistent / recurrent boundary
# ---------------------------------------------------------------------------


def test_persistent_boundary_not_extrapolated(config: dict, plan: dict) -> None:
    """p1035 仅描述持续不消失时记录一次；不得外推为所有重复表现合并记录。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1035"]
    assert "持续延伸而不消失" in excerpt
    assert "仅记录一次" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1035"]
    assert "不得外推为所有重复出现的表现合并记录" in entry["exception_rule"]
    assert "不得把未消失的持续波动误判为复发" in entry["exception_rule"]

    extrapolated = [
        "重复出现的表现一律合并记录。",
        "所有反复出现的不良事件只记录一次。",
        "持续波动的表现按复发每次单独记录。",
    ]
    for text in extrapolated:
        assert _missing_exception_keywords(text, entry), f"p1035外推反例未被拦截: {text}"


def test_recurrent_boundary_requires_disappearance(config: dict, plan: dict) -> None:
    """p1036 仅在事件消失后再次发生时每次复发单独记录。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1036"]
    assert "消失的事件随后复发" in excerpt
    assert "每次复发" in excerpt
    assert "单独的事件" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1036"]
    assert "不得把未消失的持续波动误判为复发" in entry["exception_rule"]

    fluctuation_as_recurrence = [
        "未消失的持续波动按复发每次单独记录。",
        "评估时点间持续存在的波动分别记录。",
        "任何重复出现的事件都单独记录。",
    ]
    for text in fluctuation_as_recurrence:
        assert _missing_exception_keywords(text, entry), f"p1036复发误判反例未被拦截: {text}"


def test_persistent_recurrent_never_collapsed(config: dict) -> None:
    """持续与复发边界不得互相合并，也不得与表7分别单独报告混同。"""
    p1035 = config["exception_semantics_by_source_ref"]["body.p1035"]
    p1036 = config["exception_semantics_by_source_ref"]["body.p1036"]
    assert "仅记录一次" in p1035["forbidden_inversion"]
    assert "误判为复发" in p1035["forbidden_inversion"]
    assert "误判为复发" in p1036["forbidden_inversion"]
    assert "消失后再次发生" in p1036["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得把未消失的持续波动误判为复发" in checks_blob
    assert "不得把'每次复发单独记录'与表7" in checks_blob


# ---------------------------------------------------------------------------
# professional judgment vs OR mandatory reporting layering
# ---------------------------------------------------------------------------


def test_judgment_never_becomes_automatic_classification(config: dict, plan: dict) -> None:
    """p1038 是研究者医学和科学判断；不得改写为只要异常即为AE或未否定即为AE。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1038"]
    for fragment in ("医学和科学判断", "孤立的实验室检查值异常", "是否应归类为不良事件"):
        assert fragment in excerpt, f"p1038 丢失片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1038"]
    assert "不得改写为'只要异常即为AE'或'只要研究者未明确否定即为AE'" in entry["exception_rule"]

    judgment_collapsed = [
        "实验室异常只要出现即为不良事件。",
        "实验室异常若研究者未明确否定即归为不良事件。",
        "所有实验室异常一律归类为不良事件。",
    ]
    for text in judgment_collapsed:
        assert _missing_exception_keywords(text, entry), f"p1038判断崩塌反例未被拦截: {text}"


def test_mandatory_report_not_weakened_by_judgment(config: dict) -> None:
    """专业判断层不得弱化强制报告层；强制报告层不得扩成任何异常一律报告。"""
    p1038 = config["exception_semantics_by_source_ref"]["body.p1038"]
    p1039 = config["exception_semantics_by_source_ref"]["body.p1039"]
    assert "判断层不得与p1039-p1042强制报告层混同" in p1038["exception_rule"]
    assert "不得用专业判断弱化p1039-p1042'满足任一标准必须报告'" in p1038["forbidden_inversion"]
    assert "不得把'必须报告'弱化为'可报告'" in p1039["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "前者不能弱化后者，后者也不能扩成任何异常一律报告" in checks_blob


# ---------------------------------------------------------------------------
# OR structure: never inverted to AND, alternatives non-interchangeable
# ---------------------------------------------------------------------------


def test_or_lead_never_inverted_to_and(config: dict, plan: dict) -> None:
    """p1039 '任一标准' 保持OR；不得反转为AND。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1039"]
    assert "任一标准" in excerpt
    assert "必须报告为不良事件" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1039"]
    assert "不得改成AND" in entry["exception_rule"]
    assert "不得把'必须报告'弱化为'可报告'" in entry["exception_rule"]

    and_inverted = [
        "实验室检查值异常同时满足以下所有标准时，则必须报告为不良事件。",
        "实验室检查值异常需全部符合下列标准才报告为不良事件。",
        "实验室异常须同时伴有症状且导致治疗变化且导致干预才报告。",
    ]
    for text in and_inverted:
        assert _missing_exception_keywords(text, entry), f"OR反AND反例未被拦截: {text}"


def test_or_alternatives_stay_parallel_and_distinct(config: dict, plan: dict) -> None:
    """p1040/p1041/p1042 三个OR备选保持并列，任一满足即可，不得互相替代。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1040"] == "伴有临床症状或体征"
    assert excerpts["body.p1041"] == "导致研究治疗发生变化（例如治疗暂停或治疗终止）"
    assert excerpts["body.p1042"] == "导致医学干预或合并用药/治疗改变"
    for ref in ("body.p1040", "body.p1041", "body.p1042"):
        entry = config["exception_semantics_by_source_ref"][ref]
        assert "不得互相替代" in entry["exception_rule"]
        assert "并列备选" in entry["exception_rule"]

    # 备选互替反例必须被门禁拦截（任一备选文案被另一备选替换后丢失本备选关键词）
    substituted = {
        "body.p1040": "导致研究治疗发生变化。",
        "body.p1041": "导致医学干预或合并用药/治疗改变。",
        "body.p1042": "伴有临床症状或体征。",
    }
    semantics = config["exception_semantics_by_source_ref"]
    for ref, text in substituted.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 备选互替反例未被拦截: {text}"
        )


def test_nested_or_and_examples_preserve_their_source_logic(config: dict) -> None:
    """三个备选内部的OR与示例边界也必须保留，不能只锁定外层OR。"""
    semantics = config["exception_semantics_by_source_ref"]
    p1040 = semantics["body.p1040"]
    p1041 = semantics["body.p1041"]
    p1042 = semantics["body.p1042"]

    assert "临床症状与体征为本备选内的OR" in p1040["exception_rule"]
    assert "临床症状且体征" in p1040["forbidden_inversion"]
    assert "仅为研究治疗变化的并列示例" in p1041["exception_rule"]
    assert "不是穷尽范围" in p1041["exception_rule"]
    assert "必须同时满足" in p1041["forbidden_inversion"]
    assert "医学干预与合并用药/治疗改变为本备选内的OR" in p1042["exception_rule"]
    assert "两者同时发生" in p1042["forbidden_inversion"]

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "任一出现即可" in "\n".join(checks["body.p1040"])
    assert "不是穷尽范围" in "\n".join(checks["body.p1041"])
    assert "任一出现即可" in "\n".join(checks["body.p1042"])


def test_adjacent_definition_and_recording_obligation_are_not_new_premises(config: dict) -> None:
    """相邻定义与全量记录义务只提供语境，不得反推本包未写明的前提。"""
    checks = config["clinical_qc_checks_by_source_ref"]
    p986 = "\n".join(checks[AE_DEFINITION_REF])
    p1024 = "\n".join(checks[RECORDING_OBLIGATION_REF])

    assert "仅提供AE定义中的相邻语境" in p986
    assert "不得把'有临床意义'补成p1039-p1042未写明的额外前提" in p986
    assert "不得从p1024反推出额外计数条件或改写本包规则" in p1024
    assert "上位语境" not in p986
    assert "具体计数细则" not in p1024


def test_or_alternatives_never_compressed_to_and(config: dict) -> None:
    """三备选不得压成AND合取；OR结构的总纲与备选关系必须逐项保留。"""
    semantics = config["exception_semantics_by_source_ref"]
    for ref in ("body.p1040", "body.p1041", "body.p1042"):
        assert "不得把OR备选改写为AND合取" in semantics[ref]["forbidden_inversion"]
        assert "筛选/基线必做" in semantics[ref]["forbidden_inversion"]
        assert "入排不通过门槛" in semantics[ref]["forbidden_inversion"]


# ---------------------------------------------------------------------------
# table 7 stays package 82 read-only context
# ---------------------------------------------------------------------------


def test_table7_enters_only_as_read_only_context(config: dict) -> None:
    """表7（body.t12.r0-r4）只以只读附加角色进入，所有权归第82包。"""
    attached = set(config["attached_source_refs"])
    assert set(LATER_PKG82_REFS) <= attached
    assert set(LATER_PKG82_REFS).isdisjoint(set(config["owned_source_refs"]))
    assert config["later_package_boundary"]["expected_owners_by_span"]["body.t12.r1"] == 82
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "所有权归第82包" in checks_blob
    assert "本包不重新发布表7四行规则" in checks_blob


def test_recurrence_not_confused_with_table7_separate_reporting(config: dict) -> None:
    """p1036 '每次复发单独记录' 与表7 '分别单独报告' 是不同规则，不得混同。"""
    p1036 = config["exception_semantics_by_source_ref"]["body.p1036"]
    assert "不得与表7（body.t12）分别单独报告混同" in p1036["exception_rule"]
    t12_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t12.r1"])
    assert "与p1035'持续仅记录一次'是不同规则" in t12_checks
    t12_r2_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t12.r2"])
    assert "与p1036'每次复发单独记录'是不同规则" in t12_r2_checks


# ---------------------------------------------------------------------------
# package 84 anti-conflation: vital signs stay read-only, never absorbed
# ---------------------------------------------------------------------------


def test_package84_vital_signs_anti_conflation_read_only(config: dict) -> None:
    """第84包生命体征异常平行规则只以防混同进入；与实验室规则不得互换。"""
    attached = set(config["attached_source_refs"])
    assert set(PKG84_ANTI_CONFLATION_REFS) <= attached
    assert set(PKG84_ANTI_CONFLATION_REFS).isdisjoint(set(config["owned_source_refs"]))
    for ref in PKG84_ANTI_CONFLATION_REFS:
        checks = "\n".join(config["clinical_qc_checks_by_source_ref"][ref])
        assert "归第84包" in checks, f"{ref} 缺少第84包所有权声明"
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "结构平行" in checks_blob
    assert "不得与p1040实验室OR备选互换" in checks_blob
    assert "不得与p1042实验室OR备选互换" in checks_blob


def test_package84_pre_existing_disease_not_attached(config: dict) -> None:
    """第84包既存（合并）疾病（p1049-p1054）不得进入第83包提示。"""
    attached = set(config["attached_source_refs"])
    assert set(PKG84_META_ONLY_REFS).isdisjoint(attached)
    assert set(PKG84_META_ONLY_REFS).isdisjoint(set(config["owned_source_refs"]))
    note = config["later_package_boundary"]["note"]
    assert "既存（合并）疾病" in note
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref in PKG84_META_ONLY_REFS:
        assert ref not in prompt_text, f"第84包既存疾病来源 {ref} 泄漏进第83包提示"
    for leaked in ("既存疾病", "偏头痛频次增加", "病史和基线状况"):
        assert leaked not in prompt_text, f"第84包既存疾病内容泄漏: {leaked}"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第83包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_table7_and_package84_context(config: dict) -> None:
    """提示必须包含表7只读语境与第84包生命体征防混同语境。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "表 7 应记录的继发于其它事件的不良事件" in prompt_text
    assert "序列 | 继发事件的类型 | 示例 | 应记录的AE" in prompt_text
    assert "生命体征异常" in prompt_text
    assert "医学和科学判断一项孤立的生命体征值异常" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert "初始事件记为事件A，继发事件记为事件B" in by_ref[AB_NOTATION_REF]["excerpt"]
    assert by_ref["body.t12.r1"]["role"] == "attached"
    assert by_ref["body.p1044"]["role"] == "attached"


def test_prompt_excludes_later_package_sources() -> None:
    """第84包既存疾病与第85-99包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for leaked in (
        "既存疾病",
        "偏头痛",
        "Hy",
        "ALT或AST",
        "海氏定律",
        "24小时",
        "共同判断",
        "PASI75",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第83包提示: {leaked}"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package83_or_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg83 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_83_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg83["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第83包拥有来源为锚点"
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


def test_no_official_rule_anchors_package83_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg83 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_83_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg83["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第83包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package83_or_definition_spans(
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
    assert PACKAGE_83_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "持续延伸而不消失" in text and "仅记录一次" in text
    assert "消失的事件随后复发" in text and "每次复发" in text
    assert "医学和科学判断" in text
    assert "只要异常即为AE" in text and "只要研究者未明确否定即为AE" in text
    assert "任一标准" in text and "必须报告为不良事件" in text
    assert "不得改成AND" in text
    assert "body.p1033" in text and "body.p1042" in text
    assert "body.t12.r0" in text and "body.t12.r4" in text
    assert "第81包" in text and "第82包" in text and "第83包" in text and "第84包" in text
    assert "第85" in text and "第90" in text and "第92" in text
