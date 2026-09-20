#!/usr/bin/env python3
"""Slice61bt model-free source-closure regressions.

Locks the D001 II package 82 Table 7 secondary-event recording boundary
(frozen plan package 82: 表 7 应记录的继发于其它事件的不良事件四行规则,
body.t12.r0-r4) to its authoritative sources before any semantic replay
decision:

- config contract and role partition
- owned refs == frozen plan package 82 (table header + 4 conditional rows);
  attached refs stay read-only
- table header (t12.r0) stays structural only; four semantic rows keep
  post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- four row rules are parallel conditional branches, never compressed into
  "一律独立" or "一律合并":
  * r1 类型、示例与结果保持列关系；示例细节不提升为额外通用条件 -> 仅报告事件A,
    not extrapolated to all secondary events
  * r2 (重度或严重继发性事件) -> 分别单独报告事件A、事件B; examples are
    illustrations, not new universal disease-severity thresholds
  * r3 (在时间上分离 且 具有重要医学意义) keeps the conjunction; mere
    temporal succession never splits events
  * r4 (无法确定事件关联) -> 单独记录所有不良事件; never rewritten as
    evidence gap or enrollment pending-evidence
- t7/t12 anti-conflation: 表题 p1032 uniquely identifies 表 7 as body.t12;
  unrelated body.t7 and its lead-in p507 stay outside the prompt entirely
- column relation: 序列/继发事件的类型/示例/应记录的AE preserved, no
  serial mismatch between type/example/recorded-AE columns
- later packages are not absorbed: package 81 lead-in/caption (p1030-p1032)
  and package 83 A/B note plus adjacent rules (p1033-p1042) enter as
  direct-reference or anti-conflation read-only context without changing
  ownership; package 84 and later stay outside the attached closure
- official matrix keeps zero rows anchored in t12/t7/p985-p1100 and zero
  不良事件 / TEAE / SAE rows; procedure catalog has no AE node and no
  t12/t7 source spans
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
    CONFIG_DIR / "representative_group_package82_table7_secondary_event_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bt-package82-table7-secondary-event-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package82-table7-secondary-event-boundary"
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
PACKAGE_82_ORDINAL = 82
PACKAGE_82_ID = "pap-2979ce0b01f057b9f4f0de11"

OWNED_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]

# 结构表头单元：仅提供表格列结构，不独立形成控制点
STRUCTURAL_REFS = ["body.t12.r0"]
# 语义行单元：保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = ["body.t12.r1", "body.t12.r2", "body.t12.r3", "body.t12.r4"]

# 只读闭包：第81包引导语与表题（3）、第83包A/B记法与持续/复发/实验室异常相邻规则（10）、
# AE/TEAE/SAE定义与严重性总纲（4）、AE收集期/全量记录义务/单一事件项一术语（3）、
# 流程/监测/D1给药前锚点（3）；无关 t7 表头与引导语明确排除
PKG81_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1030, 1033)]
PKG83_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1033, 1043)]
AE_DEF_ATTACHED_REFS = ["body.p986", "body.p994"]
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1024", "body.p1026"]
FLOW_ANCHOR_REFS = ["body.p340", "body.p835", "body.p885"]
T7_EXCLUDED_REFS = ["body.t7.r0", "body.p507"]
UNOWNED_CONTEXT_REFS = ["body.p340", "body.p885"]
ATTACHED_REFS = (
    PKG81_ATTACHED_REFS
    + PKG83_ATTACHED_REFS
    + AE_DEF_ATTACHED_REFS
    + SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
)

# 后续包所有权：第83包只读进入，第84包只保留所有权元数据
LATER_PKG83_REFS = PKG83_ATTACHED_REFS
LATER_PKG84_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]

# 各语义行的合取/例外/限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.t12.r1": {
        "base_rule": "轻度/中度/非严重/无需干预治疗的继发事件，如果示例中的事件B（如健康成人轻度脱水）无需额外治疗，在eCRF上应仅报告事件A（呕吐）",
        "exception_rule": "r1必须按表格三列保持类型、示例和结果的对应关系；示例中的'无需额外治疗'不得被提升为整行新增合取条件，也不得把该示例外推为所有继发事件的一般规则",
        "preserve_keywords": ["轻度/中度/非严重/无需干预治疗", "无需额外治疗", "仅报告呕吐", "事件A"],
    },
    "body.t12.r2": {
        "base_rule": "重度或严重继发性事件分别单独报告：呕吐导致严重脱水、重度胃肠道出血导致肾衰竭时，两个事件均应在eCRF上分别单独报告（事件A、事件B）",
        "exception_rule": "r2覆盖'重度或严重继发性事件'，事件A与事件B分别单独报告；示例（严重脱水、肾衰竭）是重度/严重继发事件的举例，不是新增的通用病种门槛，不得把示例病种扩写为新的报告义务",
        "preserve_keywords": ["重度或严重继发性事件", "分别单独报告", "严重脱水", "肾衰竭", "事件A、事件B"],
    },
    "body.t12.r3": {
        "base_rule": "在时间上从与初始事件中分离出来的具有重要医学意义的次级不良事件分别单独报告：头晕导致跌倒和继发性骨折、中性粒细胞减少伴发感染时，所有事件均应在eCRF上单独报告",
        "exception_rule": "r3必须保留'在时间上分离'与'具有重要医学意义'的合取限定；仅凭先后发生不得拆分事件；示例（跌倒/继发性骨折、中性粒细胞减少伴发感染）用于说明合取判定，不得改写为'时间上分离即分别记录'",
        "preserve_keywords": ["时间上", "分离", "重要医学意义", "单独报告", "跌倒", "骨折", "中性粒细胞减少"],
    },
    "body.t12.r4": {
        "base_rule": "无法确定的：如果不清楚事件之间是否有关联，应在eCRF上单独记录所有不良事件（事件A、事件B）",
        "exception_rule": "r4仅在'不清楚事件之间是否有关联'时全部单独记录；不得改写为'证据不足'或'入排待补证'，不构成筛选/基线待补证门槛",
        "preserve_keywords": ["无法确定", "不清楚事件之间是否有关联", "单独记录所有不良事件"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"  # 接受试验用药品之后出现的所有不良医学事件
TEAE_DEFINITION_REF = "body.p994"  # 给药后出现的任何不利的医学事件
SAE_DEFINITION_REF = "body.p996"  # 相邻严重不良事件定义，仅用于防止术语混同
RECORDING_OBLIGATION_REF = "body.p1024"  # 首次服药至末次访视期间所有AE记录在eCRF
COLLECTION_WINDOW_REF = "body.p1022"  # AE收集期窗口
SINGLE_EVENT_TERM_REF = "body.p1026"  # 单一事件项一术语
AE_RECORD_START_REF = "body.p340"  # AE于D1启动给药后开始记录
SECONDARY_EVENT_GUIDE_REF = "body.p1031"  # 根据主要原因判断，示例见表7
TABLE7_CAPTION_REF = "body.p1032"  # 表 7 应记录的继发于其它事件的不良事件
AB_NOTATION_REF = "body.p1033"  # 注：以上示例将初始事件记为事件A，继发事件记为事件B


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_82_ORDINAL
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
    assert config["group_id"] == "d001-ii-package82-table7-secondary-event-boundary"
    assert config["task_id"] == "phase5-slice61bt-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 5

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "表头单元必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第82包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第82包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义行保持治疗期处置；表头不进入处置映射
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
    pkg82 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_82_ORDINAL
    )
    owned_82 = {u["source_ref"] for u in pkg82["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_82), "attached refs must not be owned by package 82"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 23


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PKG81_ATTACHED_REFS:
        assert owners.get(ref) == [81], f"{ref} 必须保持归第81包"
    for ref in PKG83_ATTACHED_REFS:
        assert owners.get(ref) == [83], f"{ref} 必须保持归第83包"
    for ref in AE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [77], f"{ref} 必须保持归第77包"
    for ref in SAE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in RECORDING_ATTACHED_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记/疗效表上下文来源"
    for ref in LATER_PKG84_REFS:
        assert owners.get(ref) == [84], f"{ref} 必须保持归第84包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第82包拥有t12.r0-r4（5），第83包拥有p1033-p1042（10），
    第84包拥有p1043-p1054（12）；第81包拥有p1027-p1032（6）。"""
    pkg81 = next(p for p in plan["packages"] if p["package_ordinal"] == 81)
    pkg82 = next(p for p in plan["packages"] if p["package_ordinal"] == 82)
    pkg83 = next(p for p in plan["packages"] if p["package_ordinal"] == 83)
    pkg84 = next(p for p in plan["packages"] if p["package_ordinal"] == 84)
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    owned_82 = {u["source_ref"] for u in pkg82["owned_units"]}
    owned_83 = {u["source_ref"] for u in pkg83["owned_units"]}
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    assert "body.p1027" in owned_81 and "body.p1032" in owned_81 and len(owned_81) == 6
    assert set(OWNED_REFS) <= owned_82 and len(owned_82) == 5
    assert set(LATER_PKG83_REFS) <= owned_83 and len(owned_83) == 10
    assert set(LATER_PKG84_REFS) <= owned_84 and len(owned_84) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_82(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_82_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_82_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.t12.r0"] == "序列 | 继发事件的类型 | 示例 | 应记录的AE"
    assert excerpts["body.t12.r1"] == (
        "1 | 轻度/中度/非严重/无需干预治疗的 | 如果呕吐（事件A）导致健康成人轻度脱水"
        "（事件B），无需额外治疗，在eCRF上应仅报告呕吐。 | 事件A"
    )
    assert excerpts["body.t12.r2"] == (
        "2 | 重度或严重继发性事件 | 如果呕吐（事件A）导致严重脱水（事件B），则应"
        "在eCRF上分别单独报告这两个事件。 | 如果重度胃肠道出血（事件A）导致肾衰竭"
        "（事件B），两个事件均应在eCRF上单独报告。 | 事件A、事件B"
    )
    assert excerpts["body.t12.r3"] == (
        "3 | 在时间上从与初始事件中分离出来的具有重要医学意义的次级不良事件 | 如果"
        "头晕（事件A）导致跌倒（事件B1）和继发性骨折（事件B2），所有三个事件均应在"
        "eCRF上单独报告。 | 如果中性粒细胞减少（事件A）伴发感染（事件B），两个事件均"
        "应在eCRF上单独报告。 | 事件A、事件B"
    )
    assert excerpts["body.t12.r4"] == (
        "4 | 无法确定的 | 如果不清楚事件之间是否有关联，应在eCRF上单独记录所有不良"
        "事件。 | 事件A、事件B"
    )


# ---------------------------------------------------------------------------
# structural-only header and semantic rows
# ---------------------------------------------------------------------------


def test_table_header_is_structural_only(config: dict, plan: dict) -> None:
    """表头r0摘录必须与表头一致，不形成控制点；四个语义行保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert "body.t12.r0" in config["structural_only_source_refs"]
    assert excerpts["body.t12.r0"] == "序列 | 继发事件的类型 | 示例 | 应记录的AE"
    assert "body.t12.r0" in config["forbidden_candidate_source_refs"]
    assert "body.t12.r0" not in config["expected_disposition_by_source_ref"]
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


def test_table_column_relation_preserved(config: dict, plan: dict) -> None:
    """表7列结构（序列/继发事件的类型/示例/应记录的AE）逐行保持，类型-示例-应记录顺序不得串行错配。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    header = excerpts["body.t12.r0"]
    for column in ("序列", "继发事件的类型", "示例", "应记录的AE"):
        assert column in header, f"表头丢失列名: {column}"
    # 行内顺序：序号 | 类型 | 示例 | 应记录，逐段验证
    assert excerpts["body.t12.r1"].startswith("1 | 轻度/中度/非严重/无需干预治疗的 | ")
    assert "在eCRF上应仅报告呕吐" in excerpts["body.t12.r1"]
    assert excerpts["body.t12.r1"].endswith("| 事件A")
    assert excerpts["body.t12.r2"].startswith("2 | 重度或严重继发性事件 | ")
    assert "分别单独报告" in excerpts["body.t12.r2"]
    assert excerpts["body.t12.r2"].endswith("| 事件A、事件B")
    assert excerpts["body.t12.r3"].startswith("3 | 在时间上从与初始事件中分离出来的具有重要医学意义的次级不良事件 | ")
    assert excerpts["body.t12.r3"].endswith("| 事件A、事件B")
    assert excerpts["body.t12.r4"].startswith("4 | 无法确定的 | ")
    assert "单独记录所有不良事件" in excerpts["body.t12.r4"]
    assert excerpts["body.t12.r4"].endswith("| 事件A、事件B")


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1033-p1042 -> 83, p1043-p1054 -> 84
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """后续包来源可只读进入闭包，但不得改变所有权或由第82包发射。"""
    boundary = config["later_package_boundary"]
    expected_later = set(LATER_PKG83_REFS + LATER_PKG84_REFS)
    assert set(boundary["expected_owners_by_span"]) == expected_later | set(OWNED_REFS)
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 82
    for ref in LATER_PKG83_REFS:
        assert boundary["expected_owners_by_span"][ref] == 83
    for ref in LATER_PKG84_REFS:
        assert boundary["expected_owners_by_span"][ref] == 84
    assert expected_later.isdisjoint(set(config["owned_source_refs"])), (
        "第83-84包细则不得被第82包拥有"
    )
    attached = set(config["attached_source_refs"])
    assert set(LATER_PKG83_REFS) <= attached
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
        assert expected_ordinal != PACKAGE_82_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第82包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第81包", "第83包", "第84包", "吞并", "第85", "第90", "第92", "24小时报告"):
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
        assert by_ref[ref].table_context is not None, f"{ref} 缺少表格行列上下文"

    # 拥有单元关键语义片段
    assert "轻度/中度/非严重/无需干预治疗" in by_ref["body.t12.r1"].excerpt
    assert "仅报告呕吐" in by_ref["body.t12.r1"].excerpt
    assert "重度或严重继发性事件" in by_ref["body.t12.r2"].excerpt
    assert "严重脱水" in by_ref["body.t12.r2"].excerpt
    assert "肾衰竭" in by_ref["body.t12.r2"].excerpt
    assert "重要医学意义" in by_ref["body.t12.r3"].excerpt
    assert "跌倒" in by_ref["body.t12.r3"].excerpt
    assert "中性粒细胞减少" in by_ref["body.t12.r3"].excerpt
    assert "不清楚事件之间是否有关联" in by_ref["body.t12.r4"].excerpt

    # 只读闭包关键片段
    assert "接受试验用药品之后出现的所有不良医学事件" in by_ref[AE_DEFINITION_REF].excerpt
    assert "给药后出现" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_EVENT_TERM_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt
    assert "具体示例见表7" in by_ref[SECONDARY_EVENT_GUIDE_REF].excerpt
    assert by_ref[TABLE7_CAPTION_REF].excerpt == "表 7 应记录的继发于其它事件的不良事件"
    assert "初始事件记为事件A，继发事件记为事件B" in by_ref[AB_NOTATION_REF].excerpt
    # 无关t7不进入本包提示，避免以“反例教学”扩大混同面
    for ref in T7_EXCLUDED_REFS:
        assert ref not in by_ref
    # 持续/复发/实验室异常相邻规则
    assert "仅记录一次" in by_ref["body.p1035"].excerpt
    assert "每次复发" in by_ref["body.p1036"].excerpt
    assert "必须报告为不良事件" in by_ref["body.p1039"].excerpt


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
    assert summary["owned_count"] == 5
    assert summary["attached_count"] == 23
    assert summary["unit_count"] == 28
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

    # 越界候选（把表7记录细则升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.t12.r2"]],
                "title": "筛选时评估继发事件记录能力，证据不足者入排不通过",
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
    """确定性门禁必须拒绝把表7记录细则改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.t12.r1": [
            "筛选时核对继发事件仅报告事件A的记录能力，不合格者视为证据缺口",
            "基线期完成继发事件记录确认，未完成者不得入组",
        ],
        "body.t12.r2": [
            "筛选时评估重度或严重继发事件分别报告能力，不合格者按排除标准判定入排不通过",
            "继发事件分别报告记录安排未完成者不得入组",
        ],
        "body.t12.r3": [
            "筛选时核对时间分离重要医学意义事件的记录路径，未安排者证据缺口不得入组",
            "基线期完成时间分离事件记录确认，未确认者入排不通过",
        ],
        "body.t12.r4": [
            "筛选时评估无法确定关联事件的记录能力，证据不足者按排除标准判定不通过",
            "无法确定关联事件的单独记录安排未完成者不得入组",
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
# deterministic exception/conjunction semantics gate (四行条件分支)
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """四行条件分支的关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或记录路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.t12.r1": "轻度或中度继发事件仅报告事件A。",
        "body.t12.r2": "重度或严重继发性事件单独报告。",
        "body.t12.r3": "时间上分离的次级不良事件应分别单独报告。",
        "body.t12.r4": "无法确定的事件关联应单独记录。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# row 1: mild/moderate/non-serious/no-intervention -> event A only
# ---------------------------------------------------------------------------


def test_row1_columns_stay_bound_without_invented_conjunction(config: dict, plan: dict) -> None:
    """r1类型、示例、结果保持绑定；示例细节不提升为整行新增合取条件。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.t12.r1"]
    assert "轻度/中度/非严重/无需干预治疗" in excerpt
    assert "无需额外治疗" in excerpt
    assert "仅报告呕吐" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.t12.r1"]
    assert "表格三列" in entry["exception_rule"]
    assert "不得被提升为整行新增合取条件" in entry["exception_rule"]
    assert "外推为所有继发事件" in entry["exception_rule"]

    extrapolated = [
        "所有继发事件一律仅报告事件A。",
        "任何继发事件都只记录初始事件。",
        "继发事件发生时仅报告初始事件A。",
    ]
    for text in extrapolated:
        assert _missing_exception_keywords(text, entry), f"r1外推反例未被拦截: {text}"


# ---------------------------------------------------------------------------
# row 2: severe/serious -> report A and B separately; examples not thresholds
# ---------------------------------------------------------------------------


def test_row2_examples_are_not_universal_thresholds(config: dict, plan: dict) -> None:
    """r2 示例（严重脱水、肾衰竭）是举例，不是新增的通用病种门槛。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.t12.r2"]
    for fragment in ("重度或严重继发性事件", "分别单独报告", "严重脱水", "肾衰竭"):
        assert fragment in excerpt, f"r2 丢失片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.t12.r2"]
    assert "不是新增的通用病种门槛" in entry["exception_rule"]
    assert "不得把示例病种扩写为新的报告义务" in entry["exception_rule"]

    threshold_invented = [
        "重度胃肠道出血导致肾衰竭时必须分别单独报告。",
        "呕吐导致严重脱水的事件一律分别报告。",
        "出现肾衰竭的继发事件都必须单独报告。",
    ]
    for text in threshold_invented:
        assert _missing_exception_keywords(text, entry), f"r2门槛扩写反例未被拦截: {text}"


def test_row2_severity_and_seriousness_dimensions(config: dict) -> None:
    """r2 的“重度/严重”不得混同，也不得无交叉引用地自动等同于 SAE。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    row2 = by_ref["body.t12.r2"].excerpt
    assert "重度或严重继发性事件" in row2
    sae = by_ref[SAE_DEFINITION_REF].excerpt
    assert "死亡、危及生命" in sae
    # 配置QC检查必须同时锁定术语区分、无交叉引用不得等同及示例非门槛。
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t12.r2"])
    assert "不得把表7中的'严重'自动等同于SAE定义" in checks
    assert "表7未明示交叉引用" in checks
    assert "沿用SAE定义" not in checks
    assert "不是新增的通用病种门槛" in checks


def test_adjacent_recording_norms_are_not_table7_premises(config: dict) -> None:
    """相邻记录规范只用于防混同，不能反推表7未写明的判定前提。"""
    p1024 = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1024"])
    p1026 = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1026"])
    assert "不得从p1024反推出额外的拆分、合并条件" in p1024
    assert "不得把p1026当作表7各行判定的逻辑前提" in p1026
    assert "以单一事件项一术语为前提" not in p1026


# ---------------------------------------------------------------------------
# row 3: temporally separated AND medically significant conjunction
# ---------------------------------------------------------------------------


def test_row3_conjunction_preserved(config: dict, plan: dict) -> None:
    """r3 保留'在时间上分离'与'具有重要医学意义'合取；仅凭先后发生不得拆分。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.t12.r3"]
    for fragment in ("时间上", "分离", "重要医学意义"):
        assert fragment in excerpt, f"r3 丢失合取片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.t12.r3"]
    assert "合取限定" in entry["exception_rule"]
    assert "仅凭先后发生不得拆分事件" in entry["exception_rule"]

    conjunction_dropped = [
        "时间上分离的次级事件一律分别单独报告。",
        "先后发生的继发事件应分别单独报告。",
        "事件发生时间不同即分别记录。",
    ]
    for text in conjunction_dropped:
        assert _missing_exception_keywords(text, entry), f"r3合取丢失反例未被拦截: {text}"


# ---------------------------------------------------------------------------
# row 4: relationship undetermined -> record all; never evidence gap
# ---------------------------------------------------------------------------


def test_row4_not_rewritten_as_evidence_gap(config: dict, plan: dict) -> None:
    """r4 仅在无法确定关联时全部单独记录，不得改写为证据不足或入排待补证。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.t12.r4"]
    for fragment in ("无法确定", "不清楚事件之间是否有关联", "单独记录所有不良事件"):
        assert fragment in excerpt, f"r4 丢失片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.t12.r4"]
    assert "不得改写为'证据不足'或'入排待补证'" in entry["exception_rule"]
    assert "不构成筛选/基线待补证门槛" in entry["exception_rule"]

    evidence_gap = [
        "事件关联证据不足时应单独记录所有不良事件。",
        "无法确定关联的继发事件在证据补齐前不得记录。",
        "关联不确定的事件按入排待补证处理。",
    ]
    for text in evidence_gap:
        assert _missing_exception_keywords(text, entry), f"r4证据缺口反例未被拦截: {text}"


def test_rows_never_compressed_to_uniform_rule(config: dict) -> None:
    """四行条件分支不得被压成一律独立或一律合并。"""
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        forbidden = entry["forbidden_inversion"]
        if ref == "body.t12.r1":
            assert "一律仅报告事件A" in forbidden
        if ref == "body.t12.r4":
            assert "一律单独记录" in forbidden
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得压成一律独立或一律合并" in checks_blob
    assert "筛选/基线必做" in checks_blob
    assert "入排不通过门槛" in checks_blob


# ---------------------------------------------------------------------------
# t7/t12 anti-conflation
# ---------------------------------------------------------------------------


def test_t7_is_not_injected_to_explain_table7(config: dict) -> None:
    """表7由p1032与相邻结构绑定；无关t7不得为“防混同”反向注入提示。"""
    caption_checks = "\n".join(
        config["clinical_qc_checks_by_source_ref"][TABLE7_CAPTION_REF]
    )
    assert "相邻结构关系" in caption_checks
    for ref in T7_EXCLUDED_REFS:
        assert ref not in config["attached_source_refs"]
        assert ref not in config["clinical_qc_checks_by_source_ref"]


def test_prompt_excludes_unrelated_t7_table(config: dict) -> None:
    """防混同依赖准确来源选择，不向提示注入无关Ⅲ期疗效表。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "表 7 应记录的继发于其它事件的不良事件" in prompt_text
    for leaked in ("伴发事件 | 处理策略 | 备注", "伴发事件及处理策略：", "PASI75", "未应答", "禁止的合并用药", "复合策略", "补救治疗"):
        assert leaked not in prompt_text, f"t7行内容泄漏进表7提示: {leaked}"


def test_table7_rows_verbatim_in_prompt(config: dict) -> None:
    """表7四行规则全文必须逐字进入提示（拥有来源）。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"
    # A/B记法说明必须进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert "初始事件记为事件A，继发事件记为事件B" in by_ref[AB_NOTATION_REF]["excerpt"]


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in t12/t7/p985-p1100, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_table7_or_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg82 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_82_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg82["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第82包拥有来源为锚点"
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
            if ref.startswith("body.t12") or ref.startswith("body.t7"):
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在表7或Ⅲ期疗效表内"
                )
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package82_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg82 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_82_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg82["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第82包拥有来源为锚点"
            )


# ---------------------------------------------------------------------------
# frozen procedure catalog: no AE/TEAE/SAE node, no t12/t7 spans
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


def test_no_procedure_node_sourced_from_table7_or_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            if ref.startswith("body.t12") or ref.startswith("body.t7"):
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以表7/Ⅲ期疗效表来源 {ref} 为来源"
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
    assert PACKAGE_82_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "轻度/中度/非严重/无需干预治疗" in text
    assert "重度或严重继发性事件" in text
    assert "重要医学意义" in text and "时间上分离" in text
    assert "无法确定" in text and "证据不足" in text
    assert "PASI75" in text
    assert "body.t12.r0" in text and "body.t12.r4" in text
    assert "第81包" in text and "第83包" in text and "第84包" in text
    assert "第85" in text and "第90" in text and "第92" in text
