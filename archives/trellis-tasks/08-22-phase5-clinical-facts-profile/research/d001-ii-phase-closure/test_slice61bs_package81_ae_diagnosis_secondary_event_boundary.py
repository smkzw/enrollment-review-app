#!/usr/bin/env python3
"""Slice61bs model-free source-closure regressions.

Locks the D001 II package 81 AE diagnosis and secondary-event boundary
(frozen plan package 81: 诊断与症状、体征和检查值、暂无法诊断的记录路径与
后续诊断更新、继发事件主要原因判断, body.p1027-p1032) to its
authoritative sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 81; attached refs stay read-only
- structural heading/caption units (p1027/p1030/p1032) stay structural
  only; three semantic units keep post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- diagnosis term priority (p1028): 优先使用医学诊断术语，而不是单个的
  症状和体征 — a recording preference, never hardened to "必须立即确诊"
  nor "无诊断不得记录"; the merge qualifier 可称为或归属于一种疾病或者
  损害的表现 stays intact
- undiagnosed recording path (p1029): 症状和/或体征 或 实验室异常值本身
  stay parallel options; later-diagnosis replacement keeps all three
  elements: 基于单一诊断的 1 例次不良事件、取代之前的症状/体征/实验室
  异常值、起始日期为首次症状出现的日期
- secondary-event judgment (p1031): only 根据主要原因确定是否应记录为
  独立不良事件 plus the 表7 reference; never weakened to 一律独立记录 or
  一律合并记录; the four table-7 rule rows (body.t12.r0-r4) belong to
  package 82 and must not be absorbed or drafted into this package
- later packages are not absorbed: package 82 table 7 (t12.r0-r4) and
  package 83 p1033-p1042 enter as direct-reference or anti-conflation
  read-only context without changing ownership; package 84 and later stay
  outside the attached closure
- official matrix keeps zero rows anchored in p985-p1032 and zero 不良
  事件 / TEAE / SAE rows; procedure catalog has no AE/TEAE/SAE node
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package81_ae_diagnosis_secondary_event_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bs-package81-ae-diagnosis-secondary-event-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package81-ae-diagnosis-secondary-event-boundary"
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
PACKAGE_81_ORDINAL = 81
PACKAGE_81_ID = "pap-d284831618aa0dcf855c35d7"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1027, 1033)]

# 结构标题/表题单元：仅提供章节归属或表题引用，不独立形成控制点
STRUCTURAL_REFS = ["body.p1027", "body.p1030", "body.p1032"]
# 语义单元：保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = ["body.p1028", "body.p1029", "body.p1031"]

# 只读闭包：前接第77包AE/TEAE定义与AE记录除外（10）、第78包SAE定义与严重性标准（12）、
# 第79包住院除外列表续与严重性标准尾项（8）、第80包ADR/SUSAR定义与AE收集记录边界（12）、
# 流程/访视/监测锚点（3）、ICF签署锚点（1）、病史/伴随疾病收集锚点（1）
PRECEDING_PKG77_REFS = [f"body.p{ordinal}" for ordinal in range(985, 995)]
PRECEDING_PKG78_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PRECEDING_PKG79_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PRECEDING_PKG80_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
ANCHOR_ATTACHED_REFS = ["body.p340", "body.p835", "body.p885"]
ICF_ANCHOR_REFS = ["body.p315"]
HISTORY_ANCHOR_REFS = ["body.p318"]
UNOWNED_CONTEXT_REFS = ["body.p315", "body.p318", "body.p340", "body.p885"]
TABLE7_ATTACHED_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG83_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1033, 1043)]
ATTACHED_REFS = (
    PRECEDING_PKG77_REFS
    + PRECEDING_PKG78_REFS
    + PRECEDING_PKG79_REFS
    + PRECEDING_PKG80_REFS
    + ANCHOR_ATTACHED_REFS
    + ICF_ANCHOR_REFS
    + HISTORY_ANCHOR_REFS
    + TABLE7_ATTACHED_REFS
    + PKG83_ATTACHED_REFS
)

# 后续包所有权：第82/83包作为只读上下文，第84包只保留所有权元数据
LATER_OWNER_TABLE7_REFS = TABLE7_ATTACHED_REFS
LATER_PKG83_REFS = PKG83_ATTACHED_REFS
LATER_PKG84_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]

# 各语义单元的合取/例外/限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1028": {
        "base_rule": "不良事件的名称应该是医学术语，应优先使用医学诊断术语，而不是单个的症状和体征；如果多项症状、体征和实验室异常值可称为或归属于一种疾病或者损害的表现，则将此作为一个不良事件",
        "exception_rule": "诊断优先是记录偏好而非强制确诊义务：'优先使用医学诊断术语，而不是单个的症状和体征'必须保留；合并限定'可称为或归属于一种疾病或者损害的表现'必须保留，不得扩写为强制拆并规则",
        "preserve_keywords": ["医学术语", "优先使用医学诊断术语", "单个的症状和体征", "一种疾病或者损害", "作为一个不良事件"],
    },
    "body.p1029": {
        "base_rule": "无法明确诊断时在eCRF不良事件页中使用症状和/或体征，或记录实验室异常值本身；后期诊断明确时更新替换为基于单一诊断的1例次不良事件，以取代之前的症状/体征、实验室异常值；该1例次不良事件的起始日期为首次症状出现的日期",
        "exception_rule": "暂无法诊断的并列记录路径必须保留（症状和/或体征，或实验室异常值本身）；后续诊断更新三要素必须全部保留：基于单一诊断的1例次不良事件、取代之前的症状/体征/实验室异常值、起始日期为首次症状出现的日期",
        "preserve_keywords": ["无法明确诊断", "症状和/或体征", "实验室异常值", "后期诊断明确", "单一诊断", "1例次", "首次症状出现的日期"],
    },
    "body.p1031": {
        "base_rule": "继发于其他事件的不良事件（例如，级联事件或临床后遗症）应根据其主要原因确定是否应记录为独立不良事件，具体示例见表7",
        "exception_rule": "本包只保留'根据主要原因判断是否记录为独立不良事件'及表7引用；表7四类具体规则（body.t12.r0-r4）由第82包拥有，本包不得凭引导语补写；'根据主要原因判断'不得弱化为'一律独立记录'或'一律合并记录'",
        "preserve_keywords": ["继发于其他事件的不良事件", "级联事件", "临床后遗症", "主要原因", "独立不良事件", "表7"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"  # 接受试验用药品之后出现的所有不良医学事件，可以表现为症状体征、疾病和/或有临床意义的实验室检查异常
TEAE_DEFINITION_REF = "body.p994"  # 给药后出现…治疗前并未出现或相对治疗前恶化
SINGLE_EVENT_TERM_REF = "body.p1026"  # 单一事件项中应只记录一个不良事件术语（第80包）
AE_RECORD_START_REF = "body.p340"  # 不良事件于D1启动给药后开始记录，直至末次安全性随访或者退出研究为止
COLLECTION_WINDOW_REF = "body.p1022"  # 首次服用试验用药品后至最后一次安全性随访或者退出研究（以先发生时间为准）
RECORDING_OBLIGATION_REF = "body.p1024"  # 首次服药至末次访视期间所有AE记录在eCRF
ICF_SIGNING_REF = "body.p315"  # 开始任何试验流程之前签署知情同意书
HISTORY_COLLECTION_REF = "body.p318"  # 既往和现病史收集（病史/伴随疾病）


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL
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
    assert config["group_id"] == "d001-ii-package81-ae-diagnosis-secondary-event-boundary"
    assert config["task_id"] == "phase5-slice61bs-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 6

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "结构标题/表题单元必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第81包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第81包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗期处置；结构标题不进入处置映射
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
        assert len(entry["preserve_keywords"]) >= 3, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg81 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL
    )
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_81), "attached refs must not be owned by package 81"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 62


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PRECEDING_PKG77_REFS:
        assert owners.get(ref) == [77], f"{ref} 必须保持归第77包"
    for ref in PRECEDING_PKG78_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in PRECEDING_PKG79_REFS:
        assert owners.get(ref) == [79], f"{ref} 必须保持归第79包"
    for ref in PRECEDING_PKG80_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ref in LATER_OWNER_TABLE7_REFS:
        assert owners.get(ref) == [82], f"{ref} 必须保持归第82包"
    for ref in LATER_PKG83_REFS:
        assert owners.get(ref) == [83], f"{ref} 必须保持归第83包"
    for ref in LATER_PKG84_REFS:
        assert owners.get(ref) == [84], f"{ref} 必须保持归第84包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第77包拥有p985-p994（10），第78包拥有p995-p1006（12），
    第79包拥有p1007-p1014（8），第80包拥有p1015-p1026（12），第81包拥有p1027-p1032（6），
    第82包拥有t12.r0-r4（5），第83包拥有p1033-p1042（10），第84包拥有p1043-p1054（12）。"""
    pkg77 = next(p for p in plan["packages"] if p["package_ordinal"] == 77)
    pkg78 = next(p for p in plan["packages"] if p["package_ordinal"] == 78)
    pkg79 = next(p for p in plan["packages"] if p["package_ordinal"] == 79)
    pkg80 = next(p for p in plan["packages"] if p["package_ordinal"] == 80)
    pkg81 = next(p for p in plan["packages"] if p["package_ordinal"] == 81)
    pkg82 = next(p for p in plan["packages"] if p["package_ordinal"] == 82)
    pkg83 = next(p for p in plan["packages"] if p["package_ordinal"] == 83)
    pkg84 = next(p for p in plan["packages"] if p["package_ordinal"] == 84)
    owned_77 = {u["source_ref"] for u in pkg77["owned_units"]}
    owned_78 = {u["source_ref"] for u in pkg78["owned_units"]}
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    owned_82 = {u["source_ref"] for u in pkg82["owned_units"]}
    owned_83 = {u["source_ref"] for u in pkg83["owned_units"]}
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    assert set(PRECEDING_PKG77_REFS) <= owned_77 and len(owned_77) == 10
    assert set(PRECEDING_PKG78_REFS) <= owned_78 and len(owned_78) == 12
    assert set(PRECEDING_PKG79_REFS) <= owned_79 and len(owned_79) == 8
    assert set(PRECEDING_PKG80_REFS) <= owned_80 and len(owned_80) == 12
    assert "body.p1027" in owned_81 and "body.p1032" in owned_81 and len(owned_81) == 6
    assert set(LATER_OWNER_TABLE7_REFS) <= owned_82 and len(owned_82) == 5
    assert set(LATER_PKG83_REFS) <= owned_83 and len(owned_83) == 10
    assert set(LATER_PKG84_REFS) <= owned_84 and len(owned_84) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_81(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_81_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1027"] == "诊断与症状、体征和检查值"
    assert excerpts["body.p1028"] == (
        "不良事件的名称应该是医学术语，应优先使用医学诊断术语，而不是单个的症状和体征。"
        "如果多项症状、体征和实验室异常值可称为或归属于一种疾病或者损害的表现，则将此"
        "作为一个不良事件。"
    )
    assert excerpts["body.p1029"] == (
        "如果无法明确诊断时，则在eCRF不良事件页中使用症状和/或体征，或记录实验室异常值"
        "本身。当后期诊断明确时，应对记录进行更新，替换为基于单一诊断的1例次不良事件，"
        "以取代之前的症状/体征、实验室异常值。此时，该1例次不良事件的起始日期为首次症状"
        "出现的日期。"
    )
    assert excerpts["body.p1030"] == "继发于其它事件的不良事件事件"
    assert excerpts["body.p1031"] == (
        "继发于其他事件的不良事件（例如，级联事件或临床后遗症）应根据其主要原因确定是否"
        "应记录为独立不良事件，具体示例见表7。"
    )
    assert excerpts["body.p1032"] == "表 7 应记录的继发于其它事件的不良事件"


# ---------------------------------------------------------------------------
# structural-only heading/caption units
# ---------------------------------------------------------------------------


def test_structural_headings_are_title_only(config: dict, plan: dict) -> None:
    """结构标题/表题单元的摘录必须与其章节标题/表题一致，不含可形成控制点的正文。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    structural_excerpts = {
        "body.p1027": "诊断与症状、体征和检查值",
        "body.p1030": "继发于其它事件的不良事件事件",
        "body.p1032": "表 7 应记录的继发于其它事件的不良事件",
    }
    for ref, expected in structural_excerpts.items():
        assert ref in config["structural_only_source_refs"]
        assert excerpts[ref] == expected
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]


def test_semantic_owned_refs_keep_disposition(config: dict) -> None:
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: t12.r0-r4 -> 82, p1033-p1054 -> 83/84
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """后续包来源可只读进入闭包，但不得改变所有权或由第81包发射。"""
    boundary = config["later_package_boundary"]
    expected_later = set(LATER_OWNER_TABLE7_REFS + LATER_PKG83_REFS + LATER_PKG84_REFS)
    assert set(boundary["expected_owners_by_span"]) == expected_later
    assert boundary["expected_owners_by_span"] == {
        **{ref: 82 for ref in LATER_OWNER_TABLE7_REFS},
        **{ref: 83 for ref in LATER_PKG83_REFS},
        **{ref: 84 for ref in LATER_PKG84_REFS},
    }
    assert expected_later.isdisjoint(set(config["owned_source_refs"])), (
        "第82包表7行与第83-84包细则不得被第81包拥有"
    )
    attached = set(config["attached_source_refs"])
    assert set(LATER_OWNER_TABLE7_REFS + LATER_PKG83_REFS) <= attached
    assert set(LATER_PKG84_REFS).isdisjoint(attached)


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
        assert expected_ordinal != PACKAGE_81_ORDINAL, f"{ref} 不得归第81包"


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第82包", "body.t12.r0", "第83包", "第84包", "吞并", "第85", "第90", "第92", "24小时报告"):
        assert fragment in note, f"边界注记缺少不得提前吞并声明: {fragment}"


def test_package82_table7_rows_stay_out_of_package81(
    config: dict, plan: dict
) -> None:
    pkg81 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL
    )
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    assert "body.t12.r0" not in owned_81
    assert "body.t12.r4" not in owned_81
    assert set(LATER_OWNER_TABLE7_REFS) <= set(config["attached_source_refs"]), (
        "p1031明确引用的表7必须作为第82包只读来源进入闭包"
    )


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
    assert "优先使用医学诊断术语" in by_ref["body.p1028"].excerpt
    assert "而不是单个的症状和体征" in by_ref["body.p1028"].excerpt
    assert "可称为或归属于一种疾病或者损害的表现" in by_ref["body.p1028"].excerpt
    assert "无法明确诊断" in by_ref["body.p1029"].excerpt
    assert "症状和/或体征" in by_ref["body.p1029"].excerpt
    assert "实验室异常值" in by_ref["body.p1029"].excerpt
    assert "单一诊断" in by_ref["body.p1029"].excerpt
    assert "1例次" in by_ref["body.p1029"].excerpt
    assert "首次症状出现的日期" in by_ref["body.p1029"].excerpt
    assert "主要原因" in by_ref["body.p1031"].excerpt
    assert "独立不良事件" in by_ref["body.p1031"].excerpt
    assert "表7" in by_ref["body.p1031"].excerpt

    # 只读闭包关键片段
    assert "可以表现为症状体征、疾病和/或有临床意义的实验室检查异常" in by_ref[AE_DEFINITION_REF].excerpt
    assert "给药后" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_EVENT_TERM_REF].excerpt
    assert "末次安全性随访或者退出研究" in by_ref[AE_RECORD_START_REF].excerpt
    assert "最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "所有AE" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "开始任何试验流程之前签署知情同意书" in by_ref[ICF_SIGNING_REF].excerpt
    assert "既往和现病史收集" in by_ref[HISTORY_COLLECTION_REF].excerpt
    assert "D1给药前结果作为基线值" in by_ref["body.p885"].excerpt
    assert "记录合并用药及不良事件" in by_ref["body.p885"].excerpt
    assert "整个研究过程要严密监测" in by_ref["body.p835"].excerpt
    assert "至少有一个合理的可能性" in by_ref["body.p1016"].excerpt


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含前接定义与流程锚点，不能只在配置元数据里声明。"""
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
    assert summary["owned_count"] == 6
    assert summary["attached_count"] == 62
    assert summary["unit_count"] == 68
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

    # 越界候选（把AE记录细则升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1028"]],
                "title": "筛选时评估诊断术语记录能力，证据不足者入排不通过",
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
# deterministic forbidden-upgrade gate (通用门禁建议)
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
    """确定性门禁必须拒绝把AE记录细则改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1028": [
            "筛选时考核诊断术语记录能力，不合格者视为证据缺口",
            "基线期完成医学术语记录评估，未完成者不得入组",
            "诊断术语记录不符合者按排除标准判定入排不通过",
        ],
        "body.p1029": [
            "筛选时核对暂无法诊断事件的记录路径，未安排者证据缺口不得入组",
            "基线期完成症状体征记录确认，未确认者入排不通过",
        ],
        "body.p1031": [
            "筛选时评估继发事件判断能力，不合格者按排除标准判定不通过",
            "继发事件记录安排未完成者不得入组",
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
# deterministic exception/conjunction semantics gate (合取/例外/限定语义)
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """诊断术语优先/暂无法诊断记录路径/后续诊断更新/主要原因判断的限定关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、路径或更新要素的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1028": "记录不良事件时应优先使用诊断术语。",
        "body.p1029": "无法明确诊断时在eCRF中记录症状和体征。",
        "body.p1031": "继发于其他事件的不良事件应记录为独立不良事件。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# diagnosis term priority (p1028)
# ---------------------------------------------------------------------------


def test_diagnosis_term_priority_is_preference_not_mandate(
    config: dict, plan: dict
) -> None:
    """p1028 诊断术语优先是记录偏好，不得改写成'必须立即确诊'或'无诊断不得记录'。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1028"]
    for fragment in ("医学术语", "优先使用医学诊断术语", "而不是单个的症状和体征"):
        assert fragment in excerpt, f"p1028 丢失诊断优先片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1028"]
    assert "偏好" in entry["exception_rule"]
    assert "必须立即确诊" in entry["forbidden_inversion"]

    hardened = [
        "不良事件必须立即确诊后才能记录。",
        "未明确诊断的不良事件不得记录。",
        "无医学诊断术语时禁止记录不良事件。",
    ]
    for text in hardened:
        assert _missing_exception_keywords(text, entry), f"诊断强制化反例未被拦截: {text}"


def test_merge_qualifier_stays_intact(config: dict, plan: dict) -> None:
    """多项症状/体征/实验室异常值只有在'可称为或归属于一种疾病或者损害的表现'时才合并为一个AE。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1028"]
    assert "可称为或归属于一种疾病或者损害的表现" in excerpt
    assert "作为一个不良事件" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1028"]
    assert "不得扩写为强制拆并规则" in entry["exception_rule"]

    split_merge_invented = [
        "多项症状和体征必须合并为一个不良事件。",
        "所有实验室异常值必须分别记录为独立不良事件。",
        "每项症状、体征和实验室值都必须单独记录。",
    ]
    for text in split_merge_invented:
        assert _missing_exception_keywords(text, entry), f"拆并扩写反例未被拦截: {text}"


def test_term_preference_distinct_from_single_event_term(config: dict) -> None:
    """p1028 术语偏好与 p1026 单一事件项一术语（第80包）是相邻但独立的记录规范。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    term_norm = by_ref[SINGLE_EVENT_TERM_REF].excerpt
    preference = by_ref["body.p1028"].excerpt
    # p1026 约束事件项术语数量；p1028 给出术语选择偏好，二者不得互相替换
    assert "单一事件项中应只记录一个不良事件术语" in term_norm
    assert "优先使用医学诊断术语" in preference
    assert "单一事件项" not in preference, "p1028 不得吞并 p1026 的单一事件项规范"


# ---------------------------------------------------------------------------
# undiagnosed recording path and later-diagnosis replacement (p1029)
# ---------------------------------------------------------------------------


def test_undiagnosed_parallel_recording_paths(config: dict, plan: dict) -> None:
    """p1029 暂无法诊断时症状/体征、实验室异常值是并列记录选项。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1029"]
    for fragment in ("无法明确诊断", "症状和/或体征", "实验室异常值本身"):
        assert fragment in excerpt, f"p1029 丢失记录路径片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1029"]
    assert "并列" in entry["exception_rule"]

    narrowed = [
        "无法明确诊断时在eCRF中仅记录症状。",
        "无法明确诊断时仅记录实验室异常值。",
        "无法明确诊断的事件推迟到诊断明确后再记录。",
    ]
    for text in narrowed:
        assert _missing_exception_keywords(text, entry), f"记录路径收窄反例未被拦截: {text}"


def test_later_diagnosis_replacement_keeps_first_symptom_date(
    config: dict, plan: dict
) -> None:
    """p1029 后续诊断更新三要素必须全部保留，首次症状日期不得丢失。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1029"]
    for fragment in (
        "后期诊断明确",
        "基于单一诊断的1例次不良事件",
        "以取代之前的症状/体征、实验室异常值",
        "起始日期为首次症状出现的日期",
    ):
        assert fragment in excerpt, f"p1029 丢失后续诊断更新片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1029"]
    assert "首次症状出现的日期" in entry["preserve_keywords"]

    date_dropped = [
        "后期诊断明确时更新记录，替换为基于单一诊断的1例次不良事件。",
        "诊断明确后按新诊断记录不良事件。",
        "后续诊断更新以诊断确认日期作为事件起始日期。",
    ]
    for text in date_dropped:
        assert _missing_exception_keywords(text, entry), f"首次症状日期丢失反例未被拦截: {text}"


# ---------------------------------------------------------------------------
# secondary-event primary-cause judgment (p1031)
# ---------------------------------------------------------------------------


def test_primary_cause_judgment_not_weakened(config: dict, plan: dict) -> None:
    """p1031 继发事件按主要原因判断是否独立记录，不得弱化为一律独立或一律合并。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1031"]
    for fragment in ("继发于其他事件的不良事件", "级联事件", "临床后遗症", "主要原因", "独立不良事件"):
        assert fragment in excerpt, f"p1031 丢失主要原因判断片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1031"]
    assert "根据主要原因" in entry["exception_rule"]

    weakened = [
        "继发事件一律记录为独立不良事件。",
        "所有继发事件一律合并到初始事件记录。",
        "继发事件无需判断，直接按严重程度记录。",
    ]
    for text in weakened:
        assert _missing_exception_keywords(text, entry), f"主要原因弱化反例未被拦截: {text}"


def test_table7_rules_are_read_only_context_not_package81_owned(config: dict, plan: dict) -> None:
    """p1031明确引用的表7必须可读，但仍归第82包且不得发射第81包候选。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1031"]
    assert "具体示例见表7" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1031"]
    assert "body.t12.r0-r4" in entry["exception_rule"]
    assert "不得凭引导语补写" in entry["exception_rule"]

    assert set(LATER_OWNER_TABLE7_REFS) <= set(config["attached_source_refs"])
    assert set(LATER_OWNER_TABLE7_REFS).isdisjoint(config["owned_source_refs"])
    assert set(LATER_OWNER_TABLE7_REFS).isdisjoint(config["forbidden_candidate_source_refs"])

    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in LATER_OWNER_TABLE7_REFS:
        assert by_ref[ref]["role"] == "attached"

    # 直接引用的表7原文必须进入提示，防止模型在缺少被引正文时自行补写；
    # 所有权与零候选边界由上面的结构断言保护。
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for required in ("轻度/中度/非严重/无需干预", "重度或严重继发性事件", "事件B1", "健康成人轻度脱水"):
        assert required in prompt_text, f"表7直接引用原文未进入只读提示: {required}"


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p985-p1032, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg81 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg81["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第81包拥有来源为锚点"
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
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1054:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package81_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg81 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_81_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg81["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第81包拥有来源为锚点"
            )


# ---------------------------------------------------------------------------
# frozen procedure catalog: no AE/TEAE/SAE node
# ---------------------------------------------------------------------------


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


def test_no_procedure_node_sourced_from_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1054:
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
    assert PACKAGE_81_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "优先使用医学诊断术语" in text
    assert "无法明确诊断" in text and "首次症状出现的日期" in text
    assert "主要原因" in text and "独立不良事件" in text
    assert "表7" in text
    assert "body.t12.r0" in text and "body.t12.r4" in text
    assert "第82包" in text and "第83包" in text and "第84包" in text
    assert "第85" in text and "第90" in text and "第92" in text
