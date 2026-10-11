#!/usr/bin/env python3
"""Slice61bz model-free source-closure regressions.

Locks the D001 II package 88 AE severity assessment boundary (frozen plan
package 88: AE严重程度评估与表8分级入口, body.p1084-p1086) to its
authoritative sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 88 (2 structural headings + 1 semantic
  unit); attached refs stay read-only
- structural units (p1084/p1086) stay structural only; p1085 keeps
  post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- p1085 keeps the CTCAE 6.0 reference obligation: 研究者可参考 CTCAE 6.0
  (never reworded to 必须一律采用, never weakened to 任选任意标准, version
  never changed or dropped); keeps the fallback hierarchy and order:
  CTCAE-covered AE -> specific 1-5 descriptions; uncovered AE -> protocol
  specific definition if any; no protocol definition -> table 8 generic
  criteria (read-only closure from package 89 body.t13.r0-r5)
- table 8 level definitions stay owned by package 89; package 88 carries
  only the read-only closure and the table entry heading (p1086), never
  publishes grade rules itself
- severity grading never conflated with SAE seriousness: table 8 grade 3
  (严重/住院), grade 4 (危及生命), grade 5 (死亡) must not be mechanically
  equated with package 78-79 SAE judgment (p997 OR lead, p999 actual
  life-threatening definition, p1000 disability criterion, p1014 other
  significant medical events)
- package 87 (p1074-p1082) enters only as read-only ownership metadata;
  p1083 (不良事件的评估 heading) enters read-only for hierarchy closure;
  packages 90/91/92/93 and the rest of 78/79 are never absorbed
- official matrix keeps zero rows anchored in p1084-p1086 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no p1084-p1086 spans
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
    / "representative_group_package88_ae_severity_assessment_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bz-package88-ae-severity-assessment-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package88-ae-severity-assessment-boundary"
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
PACKAGE_88_ORDINAL = 88
PACKAGE_88_ID = "pap-c83571533332e92881f82dd1"
PACKAGE_87_ORDINAL = 87
PACKAGE_87_ID = "pap-2479acb2cc6c17a411ff2a3e"
PACKAGE_89_ORDINAL = 89
PACKAGE_89_ID = "pap-2a23364a794edb74a0db5e2b"
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_90_ORDINAL = 90
PACKAGE_92_ORDINAL = 92
PACKAGE_93_ORDINAL = 93

OWNED_REFS = ["body.p1084", "body.p1085", "body.p1086"]

# 结构单元：不良事件的严重程度评估标题 / 表 8 标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1084", "body.p1086"]
# 语义单元：研究者可参考CTCAE 6.0评估AE严重程度（含回退层级），保持
# post_treatment_execution 处置
SEMANTIC_OWNED_REFS = ["body.p1085"]

# 只读闭包（11）：第87包层级闭合p1083（1）、第89包表8表头与1-5级定义
# body.t13.r0-r5（6）、第78包SAE OR总纲、实际危及生命定义与永久或严重
# 残疾标准p997/p999/p1000（3）、第79包其他有重要意义的医学事件判断
# p1014（1）。全部只读，不改变所有权。
HIERARCHY_CLOSURE_REFS = ["body.p1083"]
TABLE8_ATTACHED_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
SAE_SERIOUSNESS_ATTACHED_REFS = [
    "body.p997",
    "body.p999",
    "body.p1000",
    "body.p1014",
]
ATTACHED_REFS = (
    HIERARCHY_CLOSURE_REFS + TABLE8_ATTACHED_REFS + SAE_SERIOUSNESS_ATTACHED_REFS
)

# 相邻包所有权元数据（不进入本包拥有/不进入提示，除合同指定只读进入项）：
# 第87包（p1074-p1083，仅p1083层级闭合只读进入）、第89包（body.t13.r0-r5，
# 全部只读进入）、第90包（p1087-p1097）、第92包（p1098-p1101）、第93包
# （p1102-p1112）；第78包（p995-p1006，仅p997/p1000只读进入）、第79包
# （p1007-p1014，仅p1014只读进入）
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG87_NON_ATTACHED_REFS = [
    ref for ref in PKG87_SPAN_REFS if ref not in HIERARCHY_CLOSURE_REFS
]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
SAE_PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
SAE_PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
SAE_NON_ATTACHED_REFS = (
    [
        ref
        for ref in SAE_PKG78_SPAN_REFS
        if ref not in {"body.p997", "body.p999", "body.p1000"}
    ]
    + [ref for ref in SAE_PKG79_SPAN_REFS if ref not in {"body.p1014"}]
)

# 语义单元的语义结构、版本锚点与回退层级要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1085": {
        "base_rule": "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本6.0）评估AE严重程度。CTCAE基于以下基本准则对每个收录的不良事件的严重程度从1级至5级作了特定的描述。对于未收录至CTCAE中的不良事件，如果方案有具体定义，则按相关定义进行评估；如果方案没有具体定义，则使用下列准则对严重程度进行评估：",
        "exception_rule": "研究者可参考美国国家癌症研究所发布的CTCAE 6.0评估AE严重程度；CTCAE对已收录AE给出1-5级特定描述；未收录AE若方案有具体定义则按方案定义评估，无方案定义时才使用表8通用准则（由第89包body.t13.r0-r5只读闭包承接）；'可参考'是允许性参考义务，不得改写成'必须一律采用'，也不得弱化为任选任意标准；严重程度分级（3级严重/住院、4级危及生命、5级死亡）不等同SAE严重性判定（第78-79包）",
        "preserve_keywords": [
            "研究者可参考美国国家癌症研究所发布的",
            "CTCAE，版本6.0",
            "1级至5级",
            "如果方案有具体定义，则按相关定义进行评估",
            "如果方案没有具体定义，则使用下列准则",
        ],
    },
}

# 交叉验证锚点（只读闭包）
PKG88_HEADING_REF = "body.p1084"
PKG88_CTCAE_SEMANTIC_REF = "body.p1085"
PKG88_TABLE8_HEADING_REF = "body.p1086"
ASSESSMENT_HEADING_REF = "body.p1083"
TABLE8_HEADER_REF = "body.t13.r0"
TABLE8_GRADE1_REF = "body.t13.r1"
TABLE8_GRADE3_REF = "body.t13.r3"
TABLE8_GRADE4_REF = "body.t13.r4"
TABLE8_GRADE5_REF = "body.t13.r5"
SAE_OR_LEAD_REF = "body.p997"
SAE_LIFE_THREATENING_REF = "body.p999"
SAE_DISABILITY_REF = "body.p1000"
SAE_OTHER_SIGNIFICANT_REF = "body.p1014"

# 结构级关键片段：编码CTCAE 6.0版本锚点、可参考义务与回退层级顺序的逐字片段，
# 反例改写必须破坏至少一个
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1085": [
        "研究者可参考美国国家癌症研究所发布的",
        "CTCAE，版本6.0",
        "对每个收录的不良事件的严重程度从1级至5级作了特定的描述",
        "如果方案有具体定义，则按相关定义进行评估",
        "如果方案没有具体定义，则使用下列准则",
    ],
}

# 结构片段门禁可发现删词或改词，但无法发现"保留原句后追加必要条件"。
# 这组标记只覆盖来源明确没有、且会改变真值范围的附加条件（版本漂移、
# 义务强化、严重程度/SAE严重性混同）。
FORBIDDEN_SEMANTIC_ADDITIONS_BY_REF = {
    "body.p1085": [
        "必须一律采用CTCAE",
        "必须采用CTCAE",
        "一律按CTCAE分级",
        "版本5.0",
        "版本4.03",
        "版本4.0",
        "版本6.1",
        "任意标准",
        "等同于SAE",
        "即SAE",
        "作为SAE判定",
    ],
}

# 严重程度分级与SAE严重性混同的确定性措辞门禁：命中任一即判定混同反例
SAE_CONFLATION_PHRASES = [
    "即SAE",
    "等同于SAE",
    "视为SAE",
    "即满足SAE",
    "满足SAE",
    "满足严重不良事件",
    "作为SAE判定",
    "直接作为SAE判定",
    "机械等同SAE",
    "即按SAE上报",
    "均属于SAE",
]

# CTCAE 版本漂移确定性标记：命中任一即判定版本漂移反例
CTCae_WRONG_VERSION_PHRASES = [
    "版本5.0",
    "版本4.03",
    "版本4.0",
    "版本6.1",
    "CTCAE 5.0",
    "CTCAE 4.0",
]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden_semantic_addition_hits(text: str, source_ref: str) -> list[str]:
    return [
        marker
        for marker in FORBIDDEN_SEMANTIC_ADDITIONS_BY_REF.get(source_ref, [])
        if marker in text
    ]


def _sae_conflation_hits(text: str) -> list[str]:
    return [phrase for phrase in SAE_CONFLATION_PHRASES if phrase in text]


def _ctcae_wrong_version_hits(text: str) -> list[str]:
    return [phrase for phrase in CTCae_WRONG_VERSION_PHRASES if phrase in text]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _missing_exception_keywords(text: str, entry: dict) -> list[str]:
    """确定性合取/例外门禁：来源文本必须同时保留基础规则与例外条款关键词。"""
    return [kw for kw in entry["preserve_keywords"] if kw not in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码术语边界/限定/回退顺序的逐字片段。"""
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
    assert config["group_id"] == "d001-ii-package88-ae-severity-assessment-boundary"
    assert config["task_id"] == "phase5-slice61bz-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 3

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "p1084/p1086 两个标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS + ATTACHED_REFS), (
        "第88包拥有单元与只读附加单元均禁止发射候选"
    )
    assert pre_enrollment == set()
    assert required == set(), "第88包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗后评估方法处置；结构单元不进入处置映射
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
    assert set(config["candidate_forbidden_markers_by_source_ref"]) == forbidden

    # 版本锚点/回退层级/可参考义务语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(EXCEPTION_SEMANTICS_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg88 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL
    )
    owned_88 = {u["source_ref"] for u in pkg88["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_88), "attached refs must not be owned by package 88"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 11


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    assert owners.get("body.p1083") == [PACKAGE_87_ORDINAL], (
        "p1083 必须保持归第87包"
    )
    for ref in TABLE8_ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_89_ORDINAL], f"{ref} 必须保持归第89包"
    assert owners.get("body.p997") == [PACKAGE_78_ORDINAL], "p997 必须保持归第78包"
    assert owners.get("body.p1000") == [PACKAGE_78_ORDINAL], "p1000 必须保持归第78包"
    assert owners.get("body.p1014") == [PACKAGE_79_ORDINAL], "p1014 必须保持归第79包"


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第87包拥有p1074-p1083（10），第88包拥有p1084-p1086（3），
    第89包拥有body.t13.r0-r5（6），第90包拥有p1087-p1097（11），第92包拥有
    p1098-p1101（4），第93包拥有p1102-p1112（11）。"""
    pkg87 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_87_ORDINAL)
    pkg88 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL)
    pkg89 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL)
    pkg90 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL)
    pkg92 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL)
    pkg93 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL)
    owned_87 = {u["source_ref"] for u in pkg87["owned_units"]}
    owned_88 = {u["source_ref"] for u in pkg88["owned_units"]}
    owned_89 = {u["source_ref"] for u in pkg89["owned_units"]}
    owned_90 = {u["source_ref"] for u in pkg90["owned_units"]}
    owned_92 = {u["source_ref"] for u in pkg92["owned_units"]}
    owned_93 = {u["source_ref"] for u in pkg93["owned_units"]}
    assert set(PKG87_SPAN_REFS) <= owned_87 and len(owned_87) == 10
    assert set(OWNED_REFS) <= owned_88 and len(owned_88) == 3
    assert set(TABLE8_ATTACHED_REFS) <= owned_89 and len(owned_89) == 6
    assert set(PKG90_SPAN_REFS) <= owned_90 and len(owned_90) == 11
    assert set(PKG92_SPAN_REFS) <= owned_92 and len(owned_92) == 4
    assert set(PKG93_SPAN_REFS) <= owned_93 and len(owned_93) == 11


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_88(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_88_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1084"] == "不良事件的严重程度评估"
    assert excerpts["body.p1085"] == (
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，"
        "版本6.0）评估AE严重程度。CTCAE基于以下基本准则对每个收录的不良事件的"
        "严重程度从1级至5级作了特定的描述。对于未收录至CTCAE中的不良事件，如果"
        "方案有具体定义，则按相关定义进行评估；如果方案没有具体定义，则使用下列"
        "准则对严重程度进行评估："
    )
    assert excerpts["body.p1086"] == "表 8 不良事件严重程度分级"


def test_heading_hierarchy_keeps_distinct(config: dict, plan: dict) -> None:
    """p1083停在'不良事件的评估'；p1084-p1086全部位于'不良事件的严重程度评估'下。"""
    package = next(
        item for item in plan["packages"] if item["package_id"] == PACKAGE_88_ID
    )
    units = {item["source_ref"]: item for item in package["owned_units"]}
    assert units["body.p1084"]["heading_path"][-1] == "不良事件的严重程度评估"
    assert units["body.p1085"]["heading_path"][-1] == "不良事件的严重程度评估"
    assert units["body.p1086"]["heading_path"][-1] == "不良事件的严重程度评估"
    assert "不良事件的评估" in units["body.p1085"]["heading_path"], (
        "p1085 必须位于'不良事件的评估'层级之下"
    )
    assert units["body.p1085"]["heading_path"][-2] == "不良事件的评估"
    pkg87 = next(
        item for item in plan["packages"] if item["package_id"] == PACKAGE_87_ID
    )
    unit1083 = next(
        u for u in pkg87["owned_units"] if u["source_ref"] == "body.p1083"
    )
    assert unit1083["heading_path"][-1] == "不良事件的评估"
    assert "不良事件的严重程度评估" not in unit1083["heading_path"]


# ---------------------------------------------------------------------------
# structural-only units and semantic rows
# ---------------------------------------------------------------------------


def test_structural_units_do_not_form_control_points(config: dict, plan: dict) -> None:
    """两个标题（p1084/p1086）不形成控制点；p1085保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1084"] == "不良事件的严重程度评估"
    assert excerpts["body.p1086"] == "表 8 不良事件严重程度分级"
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1074-p1083 -> 87, p1084-p1086 -> 88,
# body.t13.r0-r5 -> 89, p1087-p1097 -> 90, p1098-p1101 -> 92
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """第87/89/90/92包来源可保留所有权元数据，但不得进入本包拥有或由本包发射。"""
    boundary = config["later_package_boundary"]
    expected_boundary = set(
        PKG87_SPAN_REFS + OWNED_REFS + TABLE8_ATTACHED_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS
    )
    assert set(boundary["expected_owners_by_span"]) == expected_boundary
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 88
    for ref in PKG87_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 87
    for ref in TABLE8_ATTACHED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 89
    for ref in PKG90_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 90
    for ref in PKG92_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 92
    neighbor = set(
        PKG87_SPAN_REFS + TABLE8_ATTACHED_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS
    )
    assert neighbor.isdisjoint(set(config["owned_source_refs"])), (
        "第87/89/90/92包来源不得被第88包拥有"
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
        assert expected_ordinal != PACKAGE_88_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第88包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第87包",
        "第88包",
        "第89包",
        "第90包",
        "第91包",
        "第92包",
        "第93包",
        "吞并",
        "所有权不得转移",
        "body.t13.r0-r5",
        "p997",
        "p1000",
        "p1014",
        "CTCAE 6.0",
        "严重程度",
        "SAE严重性",
    ):
        assert fragment in note, f"边界注记缺少防吞并/防混同声明: {fragment}"


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

    # 拥有单元关键语义片段（版本锚点与回退层级）
    assert "研究者可参考" in by_ref[PKG88_CTCAE_SEMANTIC_REF].excerpt
    assert "CTCAE，版本6.0" in by_ref[PKG88_CTCAE_SEMANTIC_REF].excerpt
    assert "1级至5级" in by_ref[PKG88_CTCAE_SEMANTIC_REF].excerpt
    assert "如果方案有具体定义，则按相关定义进行评估" in by_ref[PKG88_CTCAE_SEMANTIC_REF].excerpt
    assert "如果方案没有具体定义，则使用下列准则" in by_ref[PKG88_CTCAE_SEMANTIC_REF].excerpt
    assert by_ref[PKG88_HEADING_REF].excerpt == "不良事件的严重程度评估"
    assert by_ref[PKG88_TABLE8_HEADING_REF].excerpt == "表 8 不良事件严重程度分级"

    # 只读闭包关键片段（层级闭合/表8分级/SAE严重性防混同）
    assert by_ref[ASSESSMENT_HEADING_REF].excerpt == "不良事件的评估"
    assert "1级 | 轻度" in by_ref[TABLE8_GRADE1_REF].excerpt
    assert "严重或者具有重要医学意义但不会立即危及生命" in by_ref[TABLE8_GRADE3_REF].excerpt
    assert "4级 | 危及生命；需要紧急治疗。" in by_ref[TABLE8_GRADE4_REF].excerpt
    assert "5级 | 与不良事件相关的死亡。" in by_ref[TABLE8_GRADE5_REF].excerpt
    assert "符合下列标准任何一项的不良事件" in by_ref[SAE_OR_LEAD_REF].excerpt
    assert "已经处于死亡的危险中" in by_ref[SAE_LIFE_THREATENING_REF].excerpt
    assert "并不是指假设该不良事件如果更严重可能导致死亡" in by_ref[SAE_LIFE_THREATENING_REF].excerpt
    assert "永久或者严重的残疾或者功能丧失" in by_ref[SAE_DISABILITY_REF].excerpt
    assert "其他有重要意义的医学事件" in by_ref[SAE_OTHER_SIGNIFICANT_REF].excerpt


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含版本锚点/回退层级/表8闭包与防吞并边界，
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
    # 相邻包仅合同指定项只读进入；其余不得进入
    for ref in PKG87_NON_ATTACHED_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS + PKG93_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"
    for ref in SAE_NON_ATTACHED_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 3
    assert summary["attached_count"] == 11
    assert summary["unit_count"] == 14
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

    # 越界候选（把AE严重程度评估方法升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1085"]],
                "title": "筛选时核对AE严重程度评估安排，未确认者按证据缺口判定入排不通过",
                "semantics": {},
            }
        ],
        "dispositions": dispositions,
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues)

    # 只读表8/SAE来源也只是上下文，任何候选发射都必须拒绝。
    for ref in ("body.t13.r5", "body.p997", "body.p999"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "只读背景来源不得转移所有权或发布控制点",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

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
    """确定性门禁必须拒绝把严重程度评估方法改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1084": [
            "筛选时核对严重程度评估安排，未完成者不得入组",
        ],
        "body.p1085": [
            "筛选时核对CTCAE 6.0参考掌握情况，未确认者证据缺口不得入组",
        ],
        "body.p1086": [
            "筛选时核对表8分级安排，未确认者入排不通过",
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
    """版本锚点、可参考义务与回退层级关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失版本、层级或回退顺序的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1085": [
            "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE）评估AE严重程度。",
            "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本6.0）评估AE严重程度。CTCAE对每个收录的不良事件从1级至5级作了特定的描述。",
            "对于未收录至CTCAE中的不良事件，如果方案没有具体定义，则使用下列准则对严重程度进行评估。",
            "对于未收录至CTCAE中的不良事件，如果方案有具体定义，则按相关定义进行评估。",
            "研究者可参考CTCAE 6.0评估AE严重程度。",
        ],
    }
    for ref, texts in dropped.items():
        for text in texts:
            assert _missing_exception_keywords(text, semantics[ref]), (
                f"{ref} 限定丢失反例未被门禁拦截: {text}"
            )


# ---------------------------------------------------------------------------
# CTCAE version, reference obligation, fallback order and table-8 gates
# ---------------------------------------------------------------------------


def test_structural_fragments_present_in_owned_sources(plan: dict, config: dict) -> None:
    """编码版本锚点/可参考义务/回退顺序的逐字片段必须完整保留在来源摘录中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref, fragments in STRUCTURAL_FRAGMENTS_BY_REF.items():
        for fragment in fragments:
            assert fragment in excerpts[ref], f"{ref} 丢失结构级片段: {fragment}"


def test_ctcae_version_drift_counterexamples_detected(config: dict) -> None:
    """CTCAE 版本漂移（替换版本或省略版本）必须被确定性拦截。"""
    drifted = [
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本5.0）评估AE严重程度。",
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本4.03）评估AE严重程度。",
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本6.1）评估AE严重程度。",
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE）评估AE严重程度。",
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE 4.0）评估AE严重程度。",
    ]
    for text in drifted:
        missing = _missing_structural_fragments(text, PKG88_CTCAE_SEMANTIC_REF)
        wrong = _ctcae_wrong_version_hits(text)
        version_omitted = "版本6.0" not in text and not wrong
        assert missing or wrong or version_omitted, (
            f"CTCAE版本漂移反例未被门禁拦截: {text}"
        )
    # 合法版本文本不得被误拦截
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    correct = excerpts[PKG88_CTCAE_SEMANTIC_REF]
    assert _ctcae_wrong_version_hits(correct) == []
    assert "版本6.0" in correct


def test_fallback_order_inversion_counterexamples_detected(config: dict) -> None:
    """未收录AE回退顺序反转（方案定义优先丢失、表8提前、顺序颠倒）必须被拦截。"""
    inverted = [
        "对于未收录至CTCAE中的不良事件，一律使用下列准则对严重程度进行评估。",
        "对于未收录至CTCAE中的不良事件，如果方案没有具体定义，则按相关定义进行评估；如果方案有具体定义，则使用下列准则对严重程度进行评估。",
        "对于未收录至CTCAE中的不良事件，先使用下列准则，再考虑方案定义。",
        "CTCAE对每个收录的不良事件的严重程度从1级至5级作了特定的描述；未收录事件无需分级。",
    ]
    for text in inverted:
        missing = _missing_structural_fragments(text, PKG88_CTCAE_SEMANTIC_REF)
        assert missing, f"回退顺序反转反例未被门禁拦截: {text}"


def test_reference_obligation_strength_inversion_detected(config: dict) -> None:
    """'可参考'义务强弱反转（强化为必须一律采用 / 弱化为任选任意标准）必须被拦截。"""
    inverted = [
        "研究者必须一律采用美国国家癌症研究所发布的“不良事件通用术语标准”（CTCAE，版本6.0）评估AE严重程度。",
        "研究者必须采用CTCAE，版本6.0评估AE严重程度。",
        "研究者可参考任意标准评估AE严重程度。",
        "研究者可参考美国国家癌症研究所发布的“不良事件通用术语标准”评估AE严重程度，版本可自选。",
        "研究者可参考CTCAE 6.0或研究者自行选择的其他分级标准评估AE严重程度。",
    ]
    for text in inverted:
        missing = _missing_structural_fragments(text, PKG88_CTCAE_SEMANTIC_REF)
        additions = _forbidden_semantic_addition_hits(text, PKG88_CTCAE_SEMANTIC_REF)
        assert missing or additions, (
            f"可参考义务强弱反转反例未被门禁拦截: {text}"
        )


def test_table8_not_pre_owned_by_package88(config: dict, plan: dict) -> None:
    """表8具体等级由第89包拥有；第88包只携带只读闭包并指向表格入口。"""
    owned = set(config["owned_source_refs"])
    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    assert set(TABLE8_ATTACHED_REFS).isdisjoint(owned)
    assert set(TABLE8_ATTACHED_REFS).isdisjoint(structural)
    assert set(TABLE8_ATTACHED_REFS) <= forbidden
    # p1086 只保留表格入口标题，不含任何等级定义
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1086"] == "表 8 不良事件严重程度分级"
    assert "1级" not in excerpts["body.p1086"]
    assert "轻度" not in excerpts["body.p1086"]
    # 配置显式声明表8定义由第89包承接，本包不生成等级规则
    semantics = config["exception_semantics_by_source_ref"]["body.p1085"]
    assert "由第89包body.t13.r0-r5只读闭包承接" in semantics["exception_rule"]
    assert "不得由本包自行生成表8等级规则" in semantics["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1086"])
    assert "表8具体1-5级定义由第89包拥有（body.t13.r0-r5）" in checks
    # 准备证据中表8行为 attached 角色
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in TABLE8_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached", f"{ref} 必须以只读角色进入"
    # 第89包表8内容不得转移所有权元数据
    boundary = config["later_package_boundary"]
    for ref in TABLE8_ATTACHED_REFS:
        assert boundary["expected_owners_by_span"][ref] == PACKAGE_89_ORDINAL


def test_severity_vs_sae_seriousness_never_conflated(config: dict) -> None:
    """严重程度分级（3级严重/住院、4级危及生命、5级死亡）不得与SAE严重性混同。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1085"]
    assert "不等同SAE严重性判定（第78-79包）" in semantics["exception_rule"]
    assert "不得把表8 3级严重/住院、4级危及生命、5级死亡机械等同第78-79包SAE严重性判定" in (
        semantics["forbidden_inversion"]
    )
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得机械等同第78-79包SAE严重性标准" in checks_blob
    assert "不等同第78包SAE'危及生命'判定标准" in checks_blob
    assert "不等同第78包SAE死亡结果判定（p998）" in checks_blob
    # 只读SAE锚点检查文本存在
    assert "严重程度等级不得机械等同SAE OR标准" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p997"]
    )
    assert "已经处于死亡危险中" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p999"]
    )
    assert "表8 3级'致残'措辞不得机械等同该标准" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1000"]
    )
    assert "与表8 3级'具有重要医学意义'措辞是不同层级规则，不得混同" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1014"]
    )


def test_sae_conflation_counterexamples_detected(config: dict) -> None:
    """严重程度/SAE严重性混同反例必须被确定性措辞门禁拦截。"""
    conflated = [
        "表8 3级（重度）即SAE，需按SAE流程上报。",
        "表8 3级重度不良事件等同于SAE。",
        "表8 4级危及生命即满足SAE危及生命标准。",
        "表8 5级死亡即SAE死亡结果。",
        "达到3级及以上即SAE。",
        "表8 3级包含住院措辞，住院即SAE。",
        "AE严重程度分级可直接作为SAE判定。",
        "表8分级结果直接作为SAE判定依据。",
        "3级及以上严重不良事件均属于SAE。",
        "表8 4级危及生命视为SAE危及生命。",
        "表8 4级危及生命满足SAE危及生命标准。",
        "表8 5级死亡满足严重不良事件标准。",
    ]
    for text in conflated:
        hits = _sae_conflation_hits(text)
        assert hits, f"严重程度/SAE严重性混同反例未被门禁拦截: {text}"
    # 合法来源文本（含t13 3级/4级/5级定义与SAE锚点）不得误拦截
    plan = _load_json(PLAN_PATH)
    for pkg in plan["packages"]:
        for u in pkg["owned_units"]:
            hits = _sae_conflation_hits(u["excerpt"])
            assert hits == [], f"误拦截合法来源 {u['source_ref']}: {hits}"


# ---------------------------------------------------------------------------
# anti-absorption: package 87 / package 90+ / package 78-79
# ---------------------------------------------------------------------------


def test_package87_predecessor_not_absorbed(config: dict) -> None:
    """第87包死亡/过量/给药错误逻辑不得进入本包闭包；仅p1083层级闭合只读进入。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG87_NON_ATTACHED_REFS).isdisjoint(attached)
    assert set(PKG87_NON_ATTACHED_REFS).isdisjoint(owned)
    assert "body.p1083" in attached
    note = config["later_package_boundary"]["note"]
    assert "第87包死亡、药物过量与给药错误记录规则（body.p1074-p1083）仅作为防吞并边界保留所有权元数据" in note
    assert "p1083（不良事件的评估标题）按合同作为层级闭合只读进入" in note


def test_package90_and_later_not_absorbed(config: dict) -> None:
    """第90包因果关系及更后包流程不得进入本包闭包。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    for span in (PKG90_SPAN_REFS, PKG92_SPAN_REFS, PKG93_SPAN_REFS):
        assert set(span).isdisjoint(attached)
        assert set(span).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "第90包因果关系共同判断" in note
    assert "第91包因果判定表（body.t14）" in note
    assert "第92包预期性评估" in note
    assert "第93包应报告事件类型与随访流程（body.p1102-p1112）" in note
    assert "本包不提前吞并或处置" in note


def test_package78_79_sae_seriousness_attached_read_only(config: dict) -> None:
    """第78-79包SAE锚点仅p997/p999/p1000/p1014只读进入。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(SAE_SERIOUSNESS_ATTACHED_REFS) <= attached
    assert set(SAE_SERIOUSNESS_ATTACHED_REFS).isdisjoint(owned)
    assert set(SAE_NON_ATTACHED_REFS).isdisjoint(attached)
    note = config["later_package_boundary"]["note"]
    assert "仅用于防止严重程度等级与SAE严重性混同" in note
    assert "不得进入本包候选或重新拥有SAE规则" in note


def test_prompt_excludes_neighbor_content() -> None:
    """第87包（除p1083）、第90/91/92/93包与第78-79包非附加内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第87包死亡/过量/给药错误内容（禁止泄漏）
    for leaked in (
        "药物过量",
        "给药错误",
        "不明原因死亡",
        "猝死",
        "eCRF研究药物给药表",
    ):
        assert leaked not in prompt_text, f"第87包内容泄漏进第88包提示: {leaked}"
    # 第86包DILI内容（禁止泄漏）
    for leaked in (
        "药物性肝损伤",
        "Hy",
        "总胆红素",
    ):
        assert leaked not in prompt_text, f"第86包DILI内容泄漏进第88包提示: {leaked}"
    # 第90/91/92/93包内容（禁止泄漏）
    for leaked in (
        "因果关系",
        "预期性",
        "研究者手册",
        "妊娠事件",
        "24小时",
        "应报告",
        "血细胞减少",
        "暂停治疗",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第88包提示: {leaked}"
    # 相邻包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in (
        PKG87_NON_ATTACHED_REFS + PKG90_SPAN_REFS + PKG92_SPAN_REFS + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入第88包准备证据"
    for ref in SAE_NON_ATTACHED_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第88包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第88包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_ctcae6_and_table8_closure() -> None:
    """提示必须包含CTCAE 6.0版本锚点、回退层级与表8只读闭包，且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "CTCAE，版本6.0" in prompt_text
    assert "研究者可参考" in prompt_text
    assert "1级至5级" in prompt_text
    assert "如果方案有具体定义，则按相关定义进行评估" in prompt_text
    assert "如果方案没有具体定义，则使用下列准则" in prompt_text
    assert "表 8 不良事件严重程度分级" in prompt_text
    assert "1级 | 轻度" in prompt_text
    assert "5级 | 与不良事件相关的死亡。" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert by_ref[TABLE8_HEADER_REF]["role"] == "attached"
    assert by_ref[TABLE8_GRADE5_REF]["role"] == "attached"
    assert by_ref[ASSESSMENT_HEADING_REF]["role"] == "attached"
    assert by_ref[PKG88_CTCAE_SEMANTIC_REF]["role"] == "owned"


def test_prompt_separates_severity_and_sae_seriousness() -> None:
    """提示含SAE严重性只读锚点且无混同措辞。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "符合下列标准任何一项的不良事件" in prompt_text
    assert "已经处于死亡的危险中" in prompt_text
    assert "并不是指假设该不良事件如果更严重可能导致死亡" in prompt_text
    assert "永久或者严重的残疾或者功能丧失" in prompt_text
    assert "其他有重要意义的医学事件" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert by_ref[SAE_OR_LEAD_REF]["role"] == "attached"
    assert by_ref[SAE_LIFE_THREATENING_REF]["role"] == "attached"
    assert by_ref[SAE_DISABILITY_REF]["role"] == "attached"
    assert by_ref[SAE_OTHER_SIGNIFICANT_REF]["role"] == "attached"
    # 提示中不得出现严重程度/SAE严重性混同措辞
    hits = _sae_conflation_hits(prompt_text)
    assert hits == [], f"提示含严重程度/SAE严重性混同措辞: {hits}"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package88(matrix: dict, plan: dict) -> None:
    pkg88 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg88["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第88包拥有来源为锚点"
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


def test_no_official_rule_anchors_package88_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg88 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_88_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg88["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第88包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package88_or_definition_spans(
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
    assert PACKAGE_88_ID in text
    assert PACKAGE_87_ID in text
    assert PACKAGE_89_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "CTCAE，版本6.0" in text
    assert "研究者可参考" in text
    assert "1级至5级" in text
    assert "方案有具体定义" in text
    assert "表 8 不良事件严重程度分级" in text
    assert "body.t13" in text
    assert "SAE严重性" in text
    assert "body.p1084" in text and "body.p1086" in text
    assert "第87包" in text and "第88包" in text and "第89包" in text
    assert "第90包" in text and "第92包" in text and "第93包" in text
    assert "claims_complete" in text
