#!/usr/bin/env python3
"""Slice61ca model-free source-closure regressions.

Locks the D001 II package 89 table 8 severity grading boundary (frozen plan
package 89: 表8不良事件严重程度分级, body.t13.r0-r5) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 89 (table 8 header + grade 1-5 rows);
  attached refs (p1084-p1086 / p997-p1001 / p1014) stay read-only with
  ownership preserved to packages 88 / 78 / 79
- r0 keeps the three-column header 分级｜类型｜定义（满足列举的任一情况）;
  r1-r5 keep row-bound grade/type/definition (no column misalignment, no
  type-as-definition, no fabricated type cell for r4/r5)
- OR semantics: 定义（满足列举的任一情况） keeps every semicolon branch
  within each grade definition as an alternative (never strengthened to
  all-satisfied AND)
- branch qualifier containment: 并未卧床不起 in grade 3 modifies only the
  自理性日常生活活动受限 branch, never the whole grade
- grade text never tampered: grade 4 keeps 危及生命 and 需要紧急治疗;
  grade 5 keeps 与不良事件相关 (death related to the AE)
- severity grading never conflated with SAE seriousness: table 8 grades
  must not be mechanically equated with package 78-79 SAE judgment
  (p997 OR lead, p998 death, p999 actual life-threatening, p1000 disability,
  p1001 hospitalization, p1014 other significant medical events)
- zero candidates: required_candidate_source_refs explicitly empty; every
  owned and attached ref is forbidden to emit a candidate
- no absorption: package 88 owned refs stay attached only (CTCAE 6.0 fallback
  method and 表8 entry heading never re-owned); package 87 (p1074-p1083),
  packages 90 (p1087-p1097) / 91 (t14.r0-r7) / 92 (p1098-p1101) / 93
  (p1102-p1112) and the non-attached rest of 78/79 never enter this closure
- official matrix keeps zero rows anchored in body.t13 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no t13 spans
- immutable source fingerprints and checklist freeze

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

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
    / "representative_group_package89_table8_severity_grading_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61ca-package89-table8-severity-grading-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package89-table8-severity-grading-boundary"
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
PACKAGE_89_ORDINAL = 89
PACKAGE_89_ID = "pap-2a23364a794edb74a0db5e2b"
PACKAGE_88_ORDINAL = 88
PACKAGE_88_ID = "pap-c83571533332e92881f82dd1"
PACKAGE_90_ORDINAL = 90
PACKAGE_90_ID = "pap-969cb2554a2487b656fbbb20"
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_87_ORDINAL = 87
PACKAGE_91_ORDINAL = 91
PACKAGE_92_ORDINAL = 92
PACKAGE_93_ORDINAL = 93

OWNED_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]

# 只读闭包（9）：第88包p1084-p1086（严重程度评估标题/CTCAE 6.0参考与回退方法/
# 表8入口标题，闭合表格用途和适用路径）、第78包p997-p1001（SAE OR总纲、死亡、
# 实际危及生命、永久或严重残疾或功能丧失、需要住院治疗或延长住院时间）、
# 第79包p1014（其他有重要意义的医学事件）。全部只读，不改变所有权。
PKG88_ATTACHED_REFS = ["body.p1084", "body.p1085", "body.p1086"]
SAE_SERIOUSNESS_ATTACHED_REFS = [
    "body.p997",
    "body.p998",
    "body.p999",
    "body.p1000",
    "body.p1001",
]
SAE_OTHER_SIGNIFICANT_ATTACHED_REFS = ["body.p1014"]
ATTACHED_REFS = (
    PKG88_ATTACHED_REFS + SAE_SERIOUSNESS_ATTACHED_REFS + SAE_OTHER_SIGNIFICANT_ATTACHED_REFS
)

# 相邻包所有权元数据（不进入本包拥有/不进入提示）：
# 第78包（p995-p1006，仅p997/p998/p999/p1000/p1001只读进入）、第79包
# （p1007-p1014，仅p1014只读进入）、第87包（p1074-p1083，全部防吞并不进入）、
# 第90包（p1087-p1097）、第91包（body.t14.r0-r7）、第92包（p1098-p1101）、
# 第93包（p1102-p1112）。第88包（p1084-p1086）仅以只读附加角色进入。
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG78_NON_ATTACHED_REFS = [
    ref for ref in PKG78_SPAN_REFS if ref not in set(SAE_SERIOUSNESS_ATTACHED_REFS)
]
PKG79_NON_ATTACHED_REFS = [
    ref for ref in PKG79_SPAN_REFS if ref not in set(SAE_OTHER_SIGNIFICANT_ATTACHED_REFS)
]

# 表8单元元数据：unit_kind、member_source_refs（r0-r3三格、r4-r5两格，c1类型
# 单元格在源文档中为空且不进入成员）与源结构块中逐格文本。
TABLE8_HEADER_REF = "body.t13.r0"
TABLE8_GRADE_REFS = [f"body.t13.r{ordinal}" for ordinal in range(1, 6)]
TABLE8_GRADE1_REF = "body.t13.r1"
TABLE8_GRADE2_REF = "body.t13.r2"
TABLE8_GRADE3_REF = "body.t13.r3"
TABLE8_GRADE4_REF = "body.t13.r4"
TABLE8_GRADE5_REF = "body.t13.r5"

EXPECTED_UNIT_KIND_BY_REF = {
    "body.t13.r0": "table_header",
    **{f"body.t13.r{ordinal}": "table_row" for ordinal in range(1, 6)},
}
EXPECTED_MEMBER_CELL_COUNT_BY_REF = {
    "body.t13.r0": 3,
    "body.t13.r1": 3,
    "body.t13.r2": 3,
    "body.t13.r3": 3,
    "body.t13.r4": 2,
    "body.t13.r5": 2,
}
# 源结构块逐格文本（c0=分级、c1=类型、c2=定义）
CELL_TEXT_BY_REF = {
    "body.t13.r0": ("分级", "类型", "定义（满足列举的任一情况）"),
    "body.t13.r1": ("1级", "轻度", "无症状或轻微；仅为临床或诊断所见；无需治疗。"),
    "body.t13.r2": (
        "2级",
        "中度",
        "需要较小、局部或非侵入性治疗；与年龄相当的工具性日常生活活动受限（指做饭、购买衣物、使用电话、理财等。）",
    ),
    "body.t13.r3": (
        "3级",
        "重度",
        "严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；致残；自理性日常生活活动受限（指洗澡、穿脱衣、吃饭、盥洗、服药等，并未卧床不起。）",
    ),
    "body.t13.r4": ("4级", "", "危及生命；需要紧急治疗。"),
    "body.t13.r5": ("5级", "", "与不良事件相关的死亡。"),
}

# 每行三列绑定：行必须以分级格开头、以定义格结尾；r1-r3 类型格必须位于第二列。
COLUMN_ALIGNMENT_PREFIX_BY_REF = {
    "body.t13.r1": "1级 | 轻度 |",
    "body.t13.r2": "2级 | 中度 |",
    "body.t13.r3": "3级 | 重度 |",
    "body.t13.r4": "4级 |",
    "body.t13.r5": "5级 |",
}
COLUMN_ALIGNMENT_SUFFIX_BY_REF = {
    "body.t13.r1": "无需治疗。",
    "body.t13.r2": "理财等。）",
    "body.t13.r3": "并未卧床不起。）",
    "body.t13.r4": "需要紧急治疗。",
    "body.t13.r5": "与不良事件相关的死亡。",
}

# 表头OR语义与各级定义的关键逐字片段（改写反例必须破坏至少一个）
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.t13.r0": ["分级", "类型", "定义（满足列举的任一情况）"],
    "body.t13.r1": ["无症状或轻微", "仅为临床或诊断所见", "无需治疗"],
    "body.t13.r2": ["需要较小、局部或非侵入性治疗", "与年龄相当的工具性日常生活活动受限", "做饭", "使用电话"],
    "body.t13.r3": [
        "严重或者具有重要医学意义但不会立即危及生命",
        "导致住院或者延长住院时间",
        "致残",
        "自理性日常生活活动受限",
        "服药等，并未卧床不起",
    ],
    "body.t13.r4": ["危及生命", "需要紧急治疗"],
    "body.t13.r5": ["与不良事件相关的死亡"],
}

# OR 反转为 AND 的确定性措辞门禁：命中任一即判定反例
OR_AND_CONVERSION_PHRASES = [
    "必须同时满足",
    "需同时满足",
    "全部同时满足",
    "均需满足",
    "全部满足",
    "且必须",
    "无症状且轻微",
    "需要治疗且工具性日常生活活动受限",
    "危及生命且需要紧急治疗",
    "严重且导致住院",
]

# 列错位/类型当定义/虚构类型格的确定性措辞门禁
COLUMN_MISALIGNMENT_PHRASES = [
    "轻度定义为",
    "中度定义为",
    "重度定义为",
    "类型为定义",
    "1级 | 无症状或轻微",
    "2级 | 需要较小、局部或非侵入性治疗",
    "3级 | 严重或者具有重要医学意义",
    "轻度 | 1级",
    "中度 | 2级",
    "重度 | 3级",
    "4级 | 危及生命 |",
    "5级 | 死亡 |",
    "4级 | 需要紧急治疗 |",
    "5级 | 与不良事件相关的死亡 |",
]

# 分支限定外溢门禁：'并未卧床不起' 必须紧跟在 3 级自理性ADL分支链内
BRANCH_QUALIFIER_CHAIN = "服药等，并未卧床不起"
BRANCH_QUALIFIER_SPILL_PHRASES = [
    "3级：并未卧床不起",
    "3级必须并未卧床不起",
    "3级均未卧床不起",
    "并未卧床不起者方可评为3级",
    "达到3级须并未卧床不起",
    "导致住院且不会立即危及生命",
    "致残且不会立即危及生命",
    "自理性日常生活活动受限且不会立即危及生命",
]

# 第88包 CTCAE 方法不可被本包反向改写
CTCAE_REABSORPTION_PHRASES = [
    "CTCAE 5.0",
    "必须一律采用CTCAE",
    "仅按表8",
    "无论方案有无定义均使用表8",
]

# 等级文本删改的确定性措辞门禁
GRADE_TEXT_TAMPERING_PHRASES = [
    "5级 | 死亡。",
    "5级 | 死亡",
    "4级 | 危及生命。",
    "4级 | 需要紧急治疗。",
    "1级 | 轻度 | 无症状或轻微；仅为临床或诊断所见；无需治疗",
    "3级 | 重度 | 严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；致残；",
]

# 严重程度分级与SAE严重性混同的确定性措辞门禁
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
    "3级即SAE",
    "4级即SAE",
    "5级即SAE",
    "达到3级及以上即SAE",
    "作为SAE死亡结果",
    "作为SAE危及生命",
    "作为SAE上报",
]

# 3级分支限定外溢检查的逐字引用（完整合法3级定义）
GRADE3_FULL_TEXT = (
    "3级 | 重度 | 严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；"
    "致残；自理性日常生活活动受限（指洗澡、穿脱衣、吃饭、盥洗、服药等，并未卧床不起。）"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _or_and_conversion_hits(text: str) -> list[str]:
    return [phrase for phrase in OR_AND_CONVERSION_PHRASES if phrase in text]


def _column_misalignment_hits(text: str) -> list[str]:
    return [phrase for phrase in COLUMN_MISALIGNMENT_PHRASES if phrase in text]


def _branch_qualifier_spill_hits(text: str) -> list[str]:
    hits = [phrase for phrase in BRANCH_QUALIFIER_SPILL_PHRASES if phrase in text]
    # 只要"并未卧床不起"脱离自理性ADL分支链即视为外溢
    if "并未卧床不起" in text and BRANCH_QUALIFIER_CHAIN not in text:
        hits.append("并未卧床不起 脱离分支限定链")
    return hits


def _ctcae_reabsorption_hits(text: str) -> list[str]:
    return [phrase for phrase in CTCAE_REABSORPTION_PHRASES if phrase in text]


def _grade_text_tampering_hits(text: str) -> list[str]:
    return [phrase for phrase in GRADE_TEXT_TAMPERING_PHRASES if phrase in text]


def _sae_conflation_hits(text: str) -> list[str]:
    return [phrase for phrase in SAE_CONFLATION_PHRASES if phrase in text]


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码术语边界/限定/回退顺序的逐字片段。"""
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _frozen_unit_by_ref(plan: dict) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            units.setdefault(u["source_ref"], u)
    return units


def _structure_blob_cell_text(blob: list[dict], cell_ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == cell_ref:
            return str(block.get("text") or "")
    raise AssertionError(f"cell {cell_ref} missing from structure blob")


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


# ---------------------------------------------------------------------------
# config contract
# ---------------------------------------------------------------------------


def test_config_contract(config: dict) -> None:
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["group_id"] == "d001-ii-package89-table8-severity-grading-boundary"
    assert config["task_id"] == "phase5-slice61ca-20260830"
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
    assert structural == {TABLE8_HEADER_REF}, "第89包表头仅作结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS + ATTACHED_REFS), (
        "第89包拥有单元与只读附加单元均禁止发射候选"
    )
    assert pre_enrollment == set()
    assert required == set(), "第89包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 零候选不等于无语义处置：表头仅作结构，五个等级行归治疗后执行语义
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in TABLE8_GRADE_REFS
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

    # 表8 OR语义/行绑定/分支限定语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref
        assert entry["forbidden_inversion"], ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg89 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL
    )
    owned_89 = {u["source_ref"] for u in pkg89["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_89), "attached refs must not be owned by package 89"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 9


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PKG88_ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_88_ORDINAL], f"{ref} 必须保持归第88包"
    for ref in SAE_SERIOUSNESS_ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_78_ORDINAL], f"{ref} 必须保持归第78包"
    assert owners.get("body.p1014") == [PACKAGE_79_ORDINAL], "p1014 必须保持归第79包"
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_89_ORDINAL], f"{ref} 必须保持归第89包"


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包拥有p995-p1006（12）、第79包拥有p1007-p1014（8）、
    第87包拥有p1074-p1083（10）、第88包拥有p1084-p1086（3）、第89包拥有
    body.t13.r0-r5（6）、第90包拥有p1087-p1097（11）、第91包拥有body.t14.r0-r7（8）、
    第92包拥有p1098-p1101（4）、第93包拥有p1102-p1112（11）。"""
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    owned_78 = counts[PACKAGE_78_ORDINAL]
    owned_79 = counts[PACKAGE_79_ORDINAL]
    owned_87 = counts[PACKAGE_87_ORDINAL]
    owned_88 = counts[PACKAGE_88_ORDINAL]
    owned_89 = counts[PACKAGE_89_ORDINAL]
    owned_90 = counts[PACKAGE_90_ORDINAL]
    owned_91 = counts[PACKAGE_91_ORDINAL]
    owned_92 = counts[PACKAGE_92_ORDINAL]
    owned_93 = counts[PACKAGE_93_ORDINAL]
    assert set(PKG78_SPAN_REFS) <= owned_78 and len(owned_78) == 12
    assert set(PKG79_SPAN_REFS) <= owned_79 and len(owned_79) == 8
    assert set(PKG87_SPAN_REFS) <= owned_87 and len(owned_87) == 10
    assert set(PKG88_ATTACHED_REFS) <= owned_88 and len(owned_88) == 3
    assert set(OWNED_REFS) <= owned_89 and len(owned_89) == 6
    assert set(PKG90_SPAN_REFS) <= owned_90 and len(owned_90) == 11
    assert set(PKG91_SPAN_REFS) <= owned_91 and len(owned_91) == 8
    assert set(PKG92_SPAN_REFS) <= owned_92 and len(owned_92) == 4
    assert set(PKG93_SPAN_REFS) <= owned_93 and len(owned_93) == 11


# ---------------------------------------------------------------------------
# frozen plan ownership and table identity
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_89(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_89_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.t13.r0"] == "分级 | 类型 | 定义（满足列举的任一情况）"
    assert excerpts["body.t13.r1"] == (
        "1级 | 轻度 | 无症状或轻微；仅为临床或诊断所见；无需治疗。"
    )
    assert excerpts["body.t13.r2"] == (
        "2级 | 中度 | 需要较小、局部或非侵入性治疗；与年龄相当的工具性日常"
        "生活活动受限（指做饭、购买衣物、使用电话、理财等。）"
    )
    assert excerpts["body.t13.r3"] == (
        "3级 | 重度 | 严重或者具有重要医学意义但不会立即危及生命；导致住院或"
        "者延长住院时间；致残；自理性日常生活活动受限（指洗澡、穿脱衣、吃饭、"
        "盥洗、服药等，并未卧床不起。）"
    )
    assert excerpts["body.t13.r4"] == "4级 | 危及生命；需要紧急治疗。"
    assert excerpts["body.t13.r5"] == "5级 | 与不良事件相关的死亡。"


def test_table8_heading_hierarchy(config: dict, plan: dict) -> None:
    """表8全部拥有单元位于'表 8 不良事件严重程度分级'标题之下，且位于
    '不良事件的严重程度评估'层级。"""
    package = next(
        item for item in plan["packages"] if item["package_id"] == PACKAGE_89_ID
    )
    units = {item["source_ref"]: item for item in package["owned_units"]}
    for ref in OWNED_REFS:
        assert units[ref]["heading_path"][-1] == "表 8 不良事件严重程度分级"
        assert "不良事件的严重程度评估" in units[ref]["heading_path"]
        assert "不良事件的评估" in units[ref]["heading_path"]


def test_table8_unit_kinds_and_member_cells(plan: dict) -> None:
    """r0是table_header；r1-r5是table_row；r0-r3含三格成员，r4/r5因c1
    类型单元格为空仅含c0分级与c2定义两个有值成员。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[ref], ref
        assert len(unit["member_source_refs"]) == EXPECTED_MEMBER_CELL_COUNT_BY_REF[ref], ref
        assert len(unit["source_span_ids"]) == EXPECTED_MEMBER_CELL_COUNT_BY_REF[ref], ref


def test_table8_cell_text_matches_structure_blob(plan: dict, structure_blob: list[dict]) -> None:
    """行摘录必须与源结构块逐格文本按'分级 | 类型 | 定义'顺序拼接一致，
    证明无列错位、无类型/定义互换、无虚构类型内容。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        # r4/r5 的c1类型单元格在源文档为空，成员格跳过该空单元格
        expected_cells = tuple(
            cell for cell in CELL_TEXT_BY_REF[ref] if cell != ""
        )
        assert len(expected_cells) == len(unit["member_source_refs"]), ref
        for index, cell_ref in enumerate(unit["member_source_refs"]):
            cell_text = _structure_blob_cell_text(structure_blob, cell_ref)
            assert cell_text == expected_cells[index], (
                f"{ref} 第{index + 1}格与源结构块不一致: {cell_text!r} != {expected_cells[index]!r}"
            )
        # 行摘录必须与源结构块逐格文本按'分级 | 类型 | 定义'顺序拼接一致，
        # 证明无列错位、无类型/定义互换、无虚构类型内容。
        joined = " | ".join(expected_cells)
        assert unit["excerpt"] == joined, f"{ref} 摘录与逐格拼接不一致"


def test_table8_r4_r5_type_cell_empty_not_fabricated(
    plan: dict, structure_blob: list[dict]
) -> None:
    """r4/r5的c1类型单元格在源文档为空，成员格不包含该空单元格，
    且不得虚构类型内容。"""
    units = _frozen_unit_by_ref(plan)
    for ref in ("body.t13.r4", "body.t13.r5"):
        unit = units[ref]
        cell_refs = unit["member_source_refs"]
        assert len(cell_refs) == 2
        assert f"{ref}.c1.p0" not in cell_refs, f"{ref} 不应包含空类型格成员"
        # 源结构块中 c1 类型格确实为空
        assert _structure_blob_cell_text(structure_blob, f"{ref}.c1.p0") == ""
        assert "轻度" not in unit["excerpt"]
        assert "中度" not in unit["excerpt"]
        assert "重度" not in unit["excerpt"]


# ---------------------------------------------------------------------------
# row binding / column alignment deterministic gates
# ---------------------------------------------------------------------------


def test_owned_sources_keep_row_binding_columns(config: dict, plan: dict) -> None:
    """r1-r3保持'分级 | 类型 | 定义'三个有值单元格绑定；r4/r5保留空c1
    的源结构事实，摘录以c0开头、c2结尾。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in TABLE8_GRADE_REFS:
        text = excerpts[ref]
        assert text.startswith(COLUMN_ALIGNMENT_PREFIX_BY_REF[ref]), ref
        assert text.endswith(COLUMN_ALIGNMENT_SUFFIX_BY_REF[ref]), ref


def test_column_misalignment_counterexamples_detected(config: dict) -> None:
    """列错位/类型当定义反例必须被确定性门禁拦截。"""
    counterexamples = {
        "body.t13.r1": [
            "轻度 | 1级 | 无症状或轻微；仅为临床或诊断所见；无需治疗。",
            "1级 | 无症状或轻微；仅为临床或诊断所见；无需治疗。 | 轻度",
            "1级 | 轻度定义为无症状或轻微；仅为临床或诊断所见；无需治疗。",
            "1级 | 无症状或轻微；仅为临床或诊断所见；无需治疗。",
        ],
        "body.t13.r2": [
            "中度 | 2级 | 需要较小、局部或非侵入性治疗；与年龄相当的工具性日常生活活动受限（指做饭、购买衣物、使用电话、理财等。）",
            "2级 | 需要较小、局部或非侵入性治疗；与年龄相当的工具性日常生活活动受限（指做饭、购买衣物、使用电话、理财等。） | 中度",
            "2级 | 中度定义为需要较小、局部或非侵入性治疗。",
        ],
        "body.t13.r3": [
            "重度 | 3级 | 严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；致残；自理性日常生活活动受限（指洗澡、穿脱衣、吃饭、盥洗、服药等，并未卧床不起。）",
            "3级 | 严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；致残；自理性日常生活活动受限（指洗澡、穿脱衣、吃饭、盥洗、服药等，并未卧床不起。） | 重度",
        ],
        "body.t13.r4": [
            "危及生命 | 4级 | 需要紧急治疗。",
            "4级 | 危及生命；需要紧急治疗。 | 危及生命",
        ],
        "body.t13.r5": [
            "与不良事件相关的死亡 | 5级",
            "5级 | 死亡 | 与不良事件相关的死亡。",
        ],
    }
    for ref, texts in counterexamples.items():
        for text in texts:
            missing = _missing_structural_fragments(text, ref)
            misaligned = _column_misalignment_hits(text)
            prefix_ok = text.startswith(COLUMN_ALIGNMENT_PREFIX_BY_REF[ref])
            suffix_ok = text.endswith(COLUMN_ALIGNMENT_SUFFIX_BY_REF[ref])
            assert missing or misaligned or not prefix_ok or not suffix_ok, (
                f"{ref} 列错位反例未被门禁拦截: {text}"
            )

    # 合法来源文本不得被误拦截
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        hits = _column_misalignment_hits(excerpts[ref])
        assert hits == [], f"误拦截合法行 {ref}: {hits}"


# ---------------------------------------------------------------------------
# deterministic OR-not-AND gate
# ---------------------------------------------------------------------------


def test_owned_sources_preserve_or_semantics(config: dict, plan: dict) -> None:
    """表头'定义（满足列举的任一情况）'与各级分支必须保持OR；来源本身不得含
    AND强化措辞。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert "定义（满足列举的任一情况）" in excerpts["body.t13.r0"]
    for ref in OWNED_REFS:
        hits = _or_and_conversion_hits(excerpts[ref])
        assert hits == [], f"{ref} 来源已含OR反转措辞: {hits}"


def test_or_and_conversion_counterexamples_detected(config: dict) -> None:
    """OR 反转为 AND（全部同时满足）反例必须被确定性拦截。"""
    counterexamples = {
        "body.t13.r1": [
            "1级 | 轻度 | 必须同时满足无症状或轻微、仅为临床或诊断所见、无需治疗。",
            "1级 | 轻度 | 无症状且轻微；仅为临床或诊断所见；无需治疗。",
            "1级 | 轻度 | 无症状或轻微、仅为临床或诊断所见、无需治疗全部满足。",
        ],
        "body.t13.r2": [
            "2级 | 中度 | 需要较小、局部或非侵入性治疗且与年龄相当的工具性日常生活活动受限。",
            "2级 | 中度 | 必须同时满足治疗要求与工具性日常生活活动受限。",
        ],
        "body.t13.r3": [
            "3级 | 重度 | 必须同时满足严重、住院、致残与自理性日常生活活动受限。",
            "3级 | 重度 | 严重且导致住院且致残且自理性日常生活活动受限。",
        ],
        "body.t13.r4": [
            "4级 | 危及生命且需要紧急治疗。",
            "4级 | 必须同时满足危及生命与需要紧急治疗。",
        ],
    }
    for ref, texts in counterexamples.items():
        for text in texts:
            missing = _missing_structural_fragments(text, ref)
            and_hits = _or_and_conversion_hits(text)
            assert missing or and_hits, f"{ref} OR反转反例未被门禁拦截: {text}"

    # 合法来源文本不得被误拦截
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        hits = _or_and_conversion_hits(excerpts[ref])
        assert hits == [], f"误拦截合法定义 {ref}: {hits}"


# ---------------------------------------------------------------------------
# branch qualifier containment (并未卧床不起)
# ---------------------------------------------------------------------------


def test_grade3_branch_qualifier_contained(config: dict, plan: dict) -> None:
    """'并未卧床不起'仅修饰自理性日常生活活动受限分支，且必须在分支链内。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    text = excerpts["body.t13.r3"]
    assert BRANCH_QUALIFIER_CHAIN in text
    assert text.endswith("并未卧床不起。）")
    assert "并未卧床不起" not in text[: text.index("自理性日常生活活动受限")]


def test_branch_qualifier_spill_counterexamples_detected(config: dict) -> None:
    """两个局部限定语外溢到其他分支或整级时必须被确定性拦截。"""
    spill = [
        "3级 | 重度 | 并未卧床不起。严重或者具有重要医学意义但不会立即危及生命；导致住院或者延长住院时间；致残；自理性日常生活活动受限。",
        "3级 | 重度 | 达到3级须并未卧床不起。",
        "3级 | 重度 | 严重或者具有重要医学意义但不会立即危及生命且并未卧床不起；导致住院或者延长住院时间；致残；自理性日常生活活动受限。",
        "3级：并未卧床不起者方可评为3级。",
        "3级 | 重度 | 严重或者具有重要医学意义；导致住院且不会立即危及生命；致残；自理性日常生活活动受限。",
        "3级 | 重度 | 严重或者具有重要医学意义；导致住院；致残且不会立即危及生命；自理性日常生活活动受限。",
        "3级 | 重度 | 严重或者具有重要医学意义；导致住院；致残；自理性日常生活活动受限且不会立即危及生命。",
    ]
    for text in spill:
        missing = _missing_structural_fragments(text, "body.t13.r3")
        spill_hits = _branch_qualifier_spill_hits(text)
        assert missing or spill_hits, f"分支限定外溢反例未被门禁拦截: {text}"
    # 合法3级定义不得误拦截
    assert _branch_qualifier_spill_hits(GRADE3_FULL_TEXT) == []


# ---------------------------------------------------------------------------
# grade text verbatim gates
# ---------------------------------------------------------------------------


def test_grade_text_tampering_counterexamples_detected(config: dict) -> None:
    """等级文本删改（删去分支、删去'与不良事件相关'限定）必须被确定性拦截。"""
    tampered = [
        "5级 | 死亡。",
        "5级 | 死亡",
        "5级 | 与不良事件相关的死亡。作为SAE死亡结果上报。",
        "4级 | 危及生命。",
        "4级 | 需要紧急治疗。",
        "4级 | 危及生命；需要紧急治疗。且必须同时满足。",
    ]
    for text in tampered:
        missing = _missing_structural_fragments(text, "body.t13.r4" if "4级" in text else "body.t13.r5")
        tamper_hits = _grade_text_tampering_hits(text)
        conflation_hits = _sae_conflation_hits(text)
        and_hits = _or_and_conversion_hits(text)
        assert missing or tamper_hits or conflation_hits or and_hits, (
            f"等级文本删改反例未被门禁拦截: {text}"
        )
    # 合法等级定义不得被误拦截
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in ("body.t13.r4", "body.t13.r5"):
        hits = _grade_text_tampering_hits(excerpts[ref])
        assert hits == [], f"误拦截合法等级定义 {ref}: {hits}"


def test_grade5_keeps_ae_related_qualifier(config: dict) -> None:
    """5级必须保留'与不良事件相关'限定；配置语义结构必须声明不得删去。"""
    semantics = config["exception_semantics_by_source_ref"]["body.t13.r5"]
    assert "与不良事件相关的死亡" in semantics["base_rule"]
    assert "必须保留'与不良事件相关'限定" in semantics["exception_rule"]
    assert "不得删去'与不良事件相关'" in semantics["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t13.r5"])
    assert "必须保留'与不良事件相关'限定" in checks


# ---------------------------------------------------------------------------
# severity grading vs SAE seriousness separation
# ---------------------------------------------------------------------------


def test_severity_vs_sae_seriousness_never_conflated(config: dict) -> None:
    """严重程度分级（3级严重/住院/重要医学意义、4级危及生命、5级死亡）不得与
    SAE严重性混同。"""
    for ref in ("body.t13.r3", "body.t13.r4", "body.t13.r5"):
        semantics = config["exception_semantics_by_source_ref"][ref]
        assert ("不等同" in semantics["exception_rule"]) or (
            "不得机械等同" in semantics["exception_rule"]
        ), ref
        assert "SAE" in semantics["forbidden_inversion"], ref
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得机械等同第78-79包SAE严重性标准" in checks_blob
    assert "不等同第78包SAE'危及生命'判定标准（body.p999）" in checks_blob
    assert "不等同第78包SAE死亡结果判定（body.p998）" in checks_blob
    for ref in SAE_SERIOUSNESS_ATTACHED_REFS + SAE_OTHER_SIGNIFICANT_ATTACHED_REFS:
        assert config["clinical_qc_checks_by_source_ref"][ref], ref
    assert "严重程度等级不得机械等同SAE OR标准" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p997"]
    )
    assert "已经处于死亡危险中" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p999"]
    )
    assert "表8 3级'致残'措辞不得机械等同该标准" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1000"]
    )
    assert "表8 3级'导致住院或者延长住院时间'措辞不得机械等同该标准" in "\n".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1001"]
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
        "表8 3级具有重要医学意义即SAE其他重要医学事件。",
        "表8 5级与不良事件相关的死亡即按SAE上报。",
        "3级及以上严重不良事件均属于SAE。",
    ]
    for text in conflated:
        hits = _sae_conflation_hits(text)
        assert hits, f"严重程度/SAE严重性混同反例未被门禁拦截: {text}"
    # 合法来源文本（含t13分级定义与SAE锚点）不得误拦截
    plan = _load_json(PLAN_PATH)
    for pkg in plan["packages"]:
        for u in pkg["owned_units"]:
            hits = _sae_conflation_hits(u["excerpt"])
            assert hits == [], f"误拦截合法来源 {u['source_ref']}: {hits}"


# ---------------------------------------------------------------------------
# resolution and zero-candidate hydrated gate
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
    assert "定义（满足列举的任一情况）" in by_ref[TABLE8_HEADER_REF].excerpt
    assert "无症状或轻微" in by_ref[TABLE8_GRADE1_REF].excerpt
    assert "与年龄相当的工具性日常生活活动受限" in by_ref[TABLE8_GRADE2_REF].excerpt
    assert "并未卧床不起" in by_ref[TABLE8_GRADE3_REF].excerpt
    assert "危及生命；需要紧急治疗。" in by_ref[TABLE8_GRADE4_REF].excerpt
    assert "与不良事件相关的死亡" in by_ref[TABLE8_GRADE5_REF].excerpt

    # 只读闭包关键片段
    assert by_ref["body.p1084"].excerpt == "不良事件的严重程度评估"
    assert "CTCAE，版本6.0" in by_ref["body.p1085"].excerpt
    assert "使用下列准则对严重程度进行评估：" in by_ref["body.p1085"].excerpt
    assert by_ref["body.p1086"].excerpt == "表 8 不良事件严重程度分级"
    assert "符合下列标准任何一项的不良事件" in by_ref["body.p997"].excerpt
    assert "导致死亡" in by_ref["body.p998"].excerpt
    assert "已经处于死亡的危险中" in by_ref["body.p999"].excerpt
    assert "并不是指假设该不良事件如果更严重可能导致死亡" in by_ref["body.p999"].excerpt
    assert "永久或者严重的残疾或者功能丧失" in by_ref["body.p1000"].excerpt
    assert "需要住院治疗或延长住院时间" in by_ref["body.p1001"].excerpt
    assert "其他有重要意义的医学事件" in by_ref["body.p1014"].excerpt

    # r0-r3 三格成员、r4-r5 两格成员
    for ref, count in EXPECTED_MEMBER_CELL_COUNT_BY_REF.items():
        assert len(by_ref[ref].source_span_ids) == count, f"{ref} 成员格数漂移"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含表8闭包与防吞并边界，不能只在配置元数据里声明。"""
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
    for ref in (
        PKG78_NON_ATTACHED_REFS
        + PKG79_NON_ATTACHED_REFS
        + PKG87_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 6
    assert summary["attached_count"] == 9
    assert summary["unit_count"] == 15
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

    # 越界候选（把表8分级定义升格为筛选/基线控制候选）必须被拒绝
    for ref in ("body.t13.r1", "body.t13.r3", "body.t13.r5"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对表8严重程度分级掌握情况，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 只读附加来源也只是上下文，任何候选发射都必须拒绝
    for ref in ("body.p1085", "body.p997", "body.p999", "body.p1014"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "只读背景来源不得转移所有权或发布控制点",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 越界引用组外单元必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": ["su-not-in-group"],
                "title": "越界候选",
                "semantics": {},
            }
        ],
        "dispositions": [],
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


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
    """确定性门禁必须拒绝把表8分级定义改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.t13.r0": [
            "筛选时核对表8三列表头，未确认者不得入组",
        ],
        "body.t13.r1": [
            "筛选时核对1级轻度定义掌握情况，未确认者证据缺口不得入组",
        ],
        "body.t13.r2": [
            "基线时核对2级中度定义掌握情况，未确认者入排不通过",
        ],
        "body.t13.r3": [
            "筛选时核对3级重度定义掌握情况，未确认者排除标准",
        ],
        "body.t13.r4": [
            "基线时核对4级定义掌握情况，未确认者不得入组",
        ],
        "body.t13.r5": [
            "筛选时核对5级定义掌握情况，未确认者入组前必查",
        ],
    }
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref, counterexamples in counterexamples_by_ref.items():
        for text in counterexamples:
            assert _forbidden_marker_hits(text, markers_by_ref[ref]), (
                f"门禁未拦截 {ref} 升格反例: {text}"
            )


# ---------------------------------------------------------------------------
# anti-absorption: package 78/79/87/88/90/91/92/93
# ---------------------------------------------------------------------------


def test_package78_79_sae_seriousness_attached_read_only(config: dict) -> None:
    """第78-79包SAE锚点仅p997-p1001/p1014只读进入；其余不进入。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(SAE_SERIOUSNESS_ATTACHED_REFS) <= attached
    assert set(SAE_OTHER_SIGNIFICANT_ATTACHED_REFS) <= attached
    assert set(SAE_SERIOUSNESS_ATTACHED_REFS + SAE_OTHER_SIGNIFICANT_ATTACHED_REFS).isdisjoint(
        owned
    )
    assert set(PKG78_NON_ATTACHED_REFS).isdisjoint(attached)
    assert set(PKG79_NON_ATTACHED_REFS).isdisjoint(attached)
    note = config["later_package_boundary"]["note"]
    assert "仅用于阻断表8等级和SAE严重性机械等同" in note
    assert "不得进入本包候选或重新拥有SAE规则" in note


def test_package88_not_re_owned(config: dict) -> None:
    """第88包p1084-p1086仅以只读附加角色进入，所有权不转移。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    assert set(PKG88_ATTACHED_REFS).isdisjoint(owned)
    assert set(PKG88_ATTACHED_REFS) <= attached
    boundary = config["later_package_boundary"]
    for ref in PKG88_ATTACHED_REFS:
        assert boundary["expected_owners_by_span"][ref] == PACKAGE_88_ORDINAL
    note = boundary["note"]
    assert "所有权不转移" in note
    assert "不重新拥有CTCAE 6.0参考与回退方法（p1085）" in note
    semantics = config["exception_semantics_by_source_ref"]["body.t13.r0"]
    assert "不得把类型列内容与定义列内容互换" in semantics["forbidden_inversion"]


def test_package88_ctcae_method_not_reverse_absorbed(config: dict) -> None:
    """本包不得改写第88包CTCAE版本、强度或回退层级。"""
    note = config["later_package_boundary"]["note"]
    assert "不得改变版本" in note
    assert "把'可参考'强化为'必须一律采用'" in note
    assert "跳过方案定义而把表8作为唯一回退" in note
    counterexamples = [
        "研究者必须一律采用CTCAE 5.0。",
        "未收录事件仅按表8，不再核对方案定义。",
        "无论方案有无定义均使用表8。",
    ]
    for text in counterexamples:
        assert _ctcae_reabsorption_hits(text), f"CTCAE反向改写未被拦截: {text}"


def test_package87_predecessor_not_absorbed(config: dict) -> None:
    """第87包死亡/过量/给药错误逻辑不得进入本包闭包或提示。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG87_SPAN_REFS).isdisjoint(attached)
    assert set(PKG87_SPAN_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "第87包死亡、药物过量与给药错误记录规则（body.p1074-p1083）" in note
    assert "防吞并边界" in note
    assert "p1083不附加" in note
    assert "标题路径已经完整闭合层级" in note


def test_package90_and_later_not_absorbed(config: dict) -> None:
    """第90包因果关系及更后包流程不得进入本包闭包或提示。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    for span in (PKG90_SPAN_REFS, PKG91_SPAN_REFS, PKG92_SPAN_REFS, PKG93_SPAN_REFS):
        assert set(span).isdisjoint(attached)
        assert set(span).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "第90包因果关系共同判断（body.p1087-p1097）" in note
    assert "第91包因果判定表（body.t14.r0-r7）" in note
    assert "第92包预期性评估（body.p1098-p1101）" in note
    assert "第93包应报告事件类型与随访流程（body.p1102-p1112）" in note
    assert "本包不提前吞并或处置" in note


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
    # 本包拥有单元只允许 t13 六行
    for ref in boundary["expected_owners_by_span"]:
        if ref in OWNED_REFS:
            assert boundary["expected_owners_by_span"][ref] == PACKAGE_89_ORDINAL


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第78包",
        "第79包",
        "第87包",
        "第88包",
        "第89包",
        "第90包",
        "第91包",
        "第92包",
        "第93包",
        "吞并",
        "所有权不转移",
        "body.t13.r0-r5",
        "p997",
        "p998",
        "p999",
        "p1000",
        "p1001",
        "p1014",
        "SAE严重性",
        "严重程度",
        "CTCAE",
    ):
        assert fragment in note, f"边界注记缺少防吞并/防混同声明: {fragment}"


def test_prompt_excludes_neighbor_content() -> None:
    """第78-79包非附加内容、第87包、第90/91/92/93包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第87包死亡/过量/给药错误内容（禁止泄漏）
    for leaked in (
        "药物过量",
        "给药错误",
        "不明原因死亡",
        "猝死",
        "eCRF研究药物给药表",
    ):
        assert leaked not in prompt_text, f"第87包内容泄漏进第89包提示: {leaked}"
    # 第90/91/92/93包内容（禁止泄漏）
    for leaked in (
        "因果关系",
        "预期性",
        "研究者手册",
        "妊娠事件",
        "应报告",
        "血细胞减少",
        "暂停治疗",
        "24小时",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第89包提示: {leaked}"
    # 相邻包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in (
        PKG78_NON_ATTACHED_REFS
        + PKG79_NON_ATTACHED_REFS
        + PKG87_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入第89包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第89包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_table8_closure_and_attached_sources() -> None:
    """提示必须包含表8表头/1-5级定义与全部只读附加来源，且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "分级 | 类型 | 定义（满足列举的任一情况）" in prompt_text
    assert "1级 | 轻度 | 无症状或轻微；仅为临床或诊断所见；无需治疗。" in prompt_text
    assert "5级 | 与不良事件相关的死亡。" in prompt_text
    assert "并未卧床不起" in prompt_text
    assert "研究者可参考" in prompt_text
    assert "CTCAE，版本6.0" in prompt_text
    assert "表 8 不良事件严重程度分级" in prompt_text
    assert "符合下列标准任何一项的不良事件" in prompt_text
    assert "导致死亡" in prompt_text
    assert "已经处于死亡的危险中" in prompt_text
    assert "永久或者严重的残疾或者功能丧失" in prompt_text
    assert "需要住院治疗或延长住院时间" in prompt_text
    assert "其他有重要意义的医学事件" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned", ref
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached", ref


def test_prompt_separates_severity_and_sae_seriousness() -> None:
    """提示含SAE严重性只读锚点且无混同措辞。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 提示中不得出现严重程度/SAE严重性混同措辞
    hits = _sae_conflation_hits(prompt_text)
    assert hits == [], f"提示含严重程度/SAE严重性混同措辞: {hits}"
    hits = _or_and_conversion_hits(prompt_text)
    assert hits == [], f"提示含OR反转措辞: {hits}"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package89(matrix: dict, plan: dict) -> None:
    pkg89 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg89["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第89包拥有来源为锚点"
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


def test_no_official_rule_anchors_package89_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg89 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_89_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg89["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第89包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package89_or_definition_spans(
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
# known targets build empty / workflow stages
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
    assert PACKAGE_89_ID in text
    assert PACKAGE_90_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "定义（满足列举的任一情况）" in text
    assert "并未卧床不起" in text
    assert "与不良事件相关的死亡" in text
    assert "body.t13" in text
    assert "SAE严重性" in text
    assert "body.p1084" in text and "body.p1086" in text
    assert "body.p997" in text and "body.p1001" in text and "body.p1014" in text
    assert "第78包" in text and "第79包" in text and "第87包" in text
    assert "第88包" in text and "第89包" in text and "第90包" in text
    assert "第91包" in text and "第92包" in text and "第93包" in text
    assert "claims_complete" in text
