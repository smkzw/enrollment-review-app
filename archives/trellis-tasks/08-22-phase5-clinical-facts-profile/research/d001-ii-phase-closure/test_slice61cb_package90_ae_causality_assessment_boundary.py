#!/usr/bin/env python3
"""Slice61cb model-free source-closure regressions.

Locks the D001 II package 90 AE causality assessment boundary (frozen plan
package 90: 不良事件因果关系判断, body.p1087-p1097) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 90 (p1087 causality title, p1088 five-level
  correlation conclusion, p1089 five-point comprehensive judgment total
  provision, p1090-p1094 the five evaluation points, p1095 table reference and
  statistical grouping, p1096 SAE joint judgment and report scope, p1097
  table 9 entry title); p1087/p1097 are structural only; p1088-p1096 stay
  post_treatment_execution; zero candidates
- attached refs (package 91 table 9 body.t14.r0-r7, including the +/-/±/++/-?
  annotation note) stay read-only with ownership preserved to package 91
- five evaluation points are comprehensive-judgment inputs: never all-satisfied
  AND, never fixed scoring, never a single-sufficient condition, never a
  mechanical decision tree
- table number inconsistency preserved: p1095 keeps 可参照表7进行 verbatim while
  p1097 and the table 9 heading say 表 9; the inconsistency stays marked as
  需要核对 and is never silently corrected to 表9; package 82 table 7 secondary
  event rules (body.t12) are never absorbed
- statistical grouping keeps exactly 肯定有关/很可能有关/可能有关 as related;
  never expanded to 可能无关/无关; individual-case reporting rules are never
  reverse-inferred from the statistical grouping
- p1096 joint judgment is OR not AND: any one side judging related falls into
  report scope; 报告范围 is never upgraded to 最终确认相关
- dimension separation: causality vs severity grading vs SAE seriousness vs
  expectedness vs reporting timeline are distinct and never substituted
- no absorption: package 78 (p995-p1006), 79 (p1007-p1014), 82 (t12.r0-r4),
  87 (p1074-p1083), 88 (p1084-p1086), 89 (t13.r0-r5), 92 (p1098-p1101), 93
  (p1102-p1112) and non-attached package 91 units never enter this closure
- official matrix keeps zero rows anchored in body.p1087-p1097 or body.t14 and
  zero 不良事件 / TEAE / SAE rows; procedure catalog has no AE node and no
  p1087-p1097 / t14 spans
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
    / "representative_group_package90_ae_causality_assessment_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61cb-package90-ae-causality-assessment-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package90-ae-causality-assessment-boundary"
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
PACKAGE_90_ORDINAL = 90
PACKAGE_90_ID = "pap-969cb2554a2487b656fbbb20"
PACKAGE_89_ORDINAL = 89
PACKAGE_89_ID = "pap-2a23364a794edb74a0db5e2b"
PACKAGE_91_ORDINAL = 91
PACKAGE_91_ID = "pap-87e89271165354d285b2faa1"
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_92_ORDINAL = 92
PACKAGE_93_ORDINAL = 93

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]

# 只读闭包（8）：第91包表9判定依据表 body.t14.r0-r7（表头、五级结论行、
# 五个评价要点对应行与+/-/±/++/-?注记），用于闭合p1095/p1097指向的实际因果
# 关系评价表及去激发/再激发未进行或不适用（-/?)含义。全部只读，所有权归第91包。
TABLE9_ATTACHED_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
ATTACHED_REFS = list(TABLE9_ATTACHED_REFS)

# 相邻包所有权元数据（不进入本包拥有/不进入提示）：
# 第78包（p995-p1006）、第79包（p1007-p1014）、第82包表7（body.t12.r0-r4）、
# 第87包（p1074-p1083）、第88包（p1084-p1086）、第89包（body.t13.r0-r5）、
# 第92包（p1098-p1101）、第93包（p1102-p1112）全部防吞并不进入；
# 第91包（body.t14.r0-r7）仅以只读附加角色进入。
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG91_NON_ATTACHED_REFS = [
    ref for ref in PKG91_SPAN_REFS if ref not in set(TABLE9_ATTACHED_REFS)
]

# 结构标题（仅作结构）：p1087因果关系判断标题、p1097表9入口标题
STRUCTURAL_REFS = ["body.p1087", "body.p1097"]
# 治疗后处置行：p1088-p1096
DISPOSITION_REFS = [f"body.p{ordinal}" for ordinal in range(1088, 1097)]
# 五个评价要点
FIVE_POINT_REFS = [f"body.p{ordinal}" for ordinal in range(1090, 1095)]

# 单元元数据：unit_kind（p1087-p1089/p1095-p1097为paragraph，p1090-p1094为
# list_item）与源结构块逐段文本。
EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1087": "paragraph",
    "body.p1088": "paragraph",
    "body.p1089": "paragraph",
    **{f"body.p{ordinal}": "list_item" for ordinal in range(1090, 1095)},
    "body.p1095": "paragraph",
    "body.p1096": "paragraph",
    "body.p1097": "paragraph",
}

# 冻结计划拥有单元逐字摘录（权威文本，任何改写反例必须破坏至少一个片段）
OWNED_EXCERPT_BY_REF = {
    "body.p1087": "不良事件因果关系判断",
    "body.p1088": "根据药物与不良事件相关性判断标准，按照五分法将不良事件与试验用药品相关性判定结果分为：肯定有关、很可能有关、可能有关、可能无关、无关。",
    "body.p1089": "研究者需根据五个评价要点进行临床试验个例不良事件与试验用药品相关性综合评价，并提供相关性判定依据。五个评价要点概括如下：",
    "body.p1090": "时间相关性：试验用药品和不良事件出现的有无合理的时间关系；",
    "body.p1091": "是否已知：不良事件是否符合该药物已知的作用机制、特性或已知的不良反应；",
    "body.p1092": "去激发结果：参与者在停药或减量后，可疑的不良事件是否减轻、好转或消失；",
    "body.p1093": "再激发结果：参与者在再次给药后，已经消除的同样、同性质的不良事件再次出现；",
    "body.p1094": "其他合理解释：不良事件是否可用参与者疾病进展（包括伴随疾病）、合并用药的作用、其他治疗措施或干扰因素等的影响来解释。",
    "body.p1095": "不良事件与试验用药品相关性判定结果分类及判定依据可参照表7进行。统计分析时，将“肯定有关”、“很可能有关”、“可能有关”视为与试验用药品相关。",
    "body.p1096": "严重不良事件（SAE）与试验用药品的因果关系由研究者和申办者双方共同判断。当双方意见不一致时，对研究者或/和申办者任意一方判断与试验用药品相关的严重不良事件，均属报告范围。",
    "body.p1097": "表 9 不良事件与试验用药品因果关系评价",
}

# 关键逐字片段门禁：改写文本必须保留的编码术语边界
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1087": ["不良事件因果关系判断"],
    "body.p1088": ["五分法", "肯定有关", "很可能有关", "可能有关", "可能无关", "无关"],
    "body.p1089": ["五个评价要点", "综合评价", "相关性判定依据"],
    "body.p1090": ["时间相关性", "合理的时间关系"],
    "body.p1091": ["是否已知", "已知的作用机制", "已知的不良反应"],
    "body.p1092": ["去激发结果", "停药或减量", "减轻、好转或消失"],
    "body.p1093": ["再激发结果", "再次给药", "同样、同性质的不良事件再次出现"],
    "body.p1094": ["其他合理解释", "疾病进展", "合并用药", "干扰因素"],
    "body.p1095": ["可参照表7进行", "肯定有关", "很可能有关", "可能有关", "视为与试验用药品相关"],
    "body.p1096": ["共同判断", "意见不一致", "任意一方判断与试验用药品相关", "均属报告范围"],
    "body.p1097": ["表 9 不良事件与试验用药品因果关系评价"],
}

# 以下短语用于父级规格反例探针，不是运行时文本分类器。运行时的零候选边界由
# forbidden_candidate_source_refs 按来源身份确定性拒绝，不能依赖有限关键词覆盖同义改写。
# 五要点AND化/计分化/单项充分/机械决策树的规格反例
FIVE_POINTS_AND_PHRASES = [
    "五个要点均需满足",
    "五个要点必须全部满足",
    "五个要点缺一不可",
    "全部评价要点同时满足",
    "五个要点全部满足",
    "五个要点需同时满足",
    "评价要点需同时满足",
    "必须全部满足",
    "均需满足",
]
FIVE_POINTS_SCORING_PHRASES = [
    "按要点计分",
    "要点加权",
    "得分达到",
    "计分达到",
    "固定计分",
    "按评分",
    "加权评分",
    "要点打分",
    "计分规则",
]
FIVE_POINTS_SINGLE_SUFFICIENT_PHRASES = [
    "任一要点满足即",
    "单项满足即可",
    "只要一个要点",
    "任一要点即可判定",
    "单项充分",
    "任一要点即判定相关",
    "单一要点即",
]
FIVE_POINTS_DECISION_TREE_PHRASES = [
    "决策树",
    "机械决策",
    "自动判定相关",
    "算法判定",
    "机械判定",
]

# 表号静默纠正的确定性措辞门禁（p1095'可参照表7'不得改为表9）
TABLE_NUMBER_SILENT_CORRECTION_PHRASES = [
    "可参照表9进行",
    "参照表9进行",
    "将表7更正为表9",
    "表7即表9",
    "表7实为表9",
    "表7应为表9",
    "表7系笔误",
    "表7（即表9）",
    "表7就是表9",
]

# 统计分组扩大的确定性措辞门禁（相关分组只含前三类）
STAT_GROUP_EXPANSION_PHRASES = [
    "统计分组包含可能无关",
    "可能无关也视为相关",
    "无关也视为相关",
    "将可能无关纳入相关组",
    "将无关纳入相关组",
    "扩大为五类",
    "统计时纳入可能无关",
    "可能无关计入相关",
]

# 由统计分组反推个例报告规则的确定性措辞门禁
REVERSE_INFERENCE_PHRASES = [
    "统计相关即个例报告",
    "统计相关即需报告",
    "相关分组即报告范围",
    "统计相关即确认",
    "按统计分组反推个例",
    "统计相关即上报",
]

# p1096双方判断AND化（共同判断=双方一致）的确定性措辞门禁
JOINT_JUDGMENT_AND_PHRASES = [
    "双方一致才",
    "双方均判断相关才",
    "只有双方一致",
    "双方一致判断",
    "双方意见一致时",
    "必须双方一致",
    "双方都判断相关",
    "待双方一致",
]

# '报告范围'升级为'最终确认相关'的确定性措辞门禁
REPORT_SCOPE_UPGRADE_PHRASES = [
    "即最终确认相关",
    "即确认相关",
    "确认为最终相关",
    "即因果结论成立",
    "等同于确认因果关系",
    "即确认因果关系",
    "作为最终因果结论",
    "确认因果关系成立",
]

# 跨维度混同（因果关系/严重程度/SAE严重性/预期性/报告时限互相替代）门禁
DIMENSION_CONFLATION_PHRASES = [
    "因果关系即严重程度",
    "严重程度即因果关系",
    "因果判断即SAE判定",
    "按SAE严重性判断因果",
    "因果关系即预期性",
    "预期性即因果关系",
    "因果判断即报告时限",
    "按报告时限判断因果",
    "因果相关即SAE",
    "以严重程度判定因果",
    "以预期性判定因果",
    "以SAE严重性替代因果",
    "因果判断即预期性判断",
    "因果关系即报告时限",
]

ALL_DETERMINISTIC_PHRASES = (
    FIVE_POINTS_AND_PHRASES
    + FIVE_POINTS_SCORING_PHRASES
    + FIVE_POINTS_SINGLE_SUFFICIENT_PHRASES
    + FIVE_POINTS_DECISION_TREE_PHRASES
    + TABLE_NUMBER_SILENT_CORRECTION_PHRASES
    + STAT_GROUP_EXPANSION_PHRASES
    + REVERSE_INFERENCE_PHRASES
    + JOINT_JUDGMENT_AND_PHRASES
    + REPORT_SCOPE_UPGRADE_PHRASES
    + DIMENSION_CONFLATION_PHRASES
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _deterministic_hits(text: str) -> list[str]:
    return [phrase for phrase in ALL_DETERMINISTIC_PHRASES if phrase in text]


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码术语边界/限定/顺序的逐字片段。"""
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _frozen_unit_by_ref(plan: dict) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            units.setdefault(u["source_ref"], u)
    return units


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


# ---------------------------------------------------------------------------
# config contract
# ---------------------------------------------------------------------------


def test_config_contract(config: dict) -> None:
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["group_id"] == "d001-ii-package90-ae-causality-assessment-boundary"
    assert config["task_id"] == "phase5-slice61cb-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 11

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "第90包标题与表9入口仅作结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS + ATTACHED_REFS), (
        "第90包拥有单元与只读附加单元均禁止发射候选"
    )
    assert pre_enrollment == set()
    assert required == set(), "第90包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 零候选不等于无语义处置：p1088-p1096归治疗后执行语义；p1087/p1097仅作结构
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in DISPOSITION_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：全部拥有与只读附加单元的禁止升格措辞必须已写入配置
    for ref in OWNED_REFS + ATTACHED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {"筛选必做", "基线必做", "证据缺口", "不得入组", "排除标准", "入排不通过"} <= set(
            markers
        ), ref
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert set(config["candidate_forbidden_markers_by_source_ref"]) == forbidden

    # 五要点综合评价/表号不一致/统计分组/共同判断/跨维度分离语义必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref
        assert entry["forbidden_inversion"], ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg90 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL
    )
    owned_90 = {u["source_ref"] for u in pkg90["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_90), "attached refs must not be owned by package 90"
    assert set(attached) == set(TABLE9_ATTACHED_REFS)
    assert len(attached) == 8


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in TABLE9_ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_91_ORDINAL], f"{ref} 必须保持归第91包"
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_90_ORDINAL], f"{ref} 必须保持归第90包"


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包p995-p1006（12）、第79包p1007-p1014（8）、
    第82包body.t12.r0-r4（5）、第87包p1074-p1083（10）、第88包p1084-p1086（3）、
    第89包body.t13.r0-r5（6）、第90包p1087-p1097（11）、第91包body.t14.r0-r7（8）、
    第92包p1098-p1101（4）、第93包p1102-p1112（11）。"""
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    owned_78 = counts[PACKAGE_78_ORDINAL]
    owned_79 = counts[PACKAGE_79_ORDINAL]
    owned_82 = counts[PACKAGE_82_ORDINAL]
    owned_87 = counts[PACKAGE_87_ORDINAL]
    owned_88 = counts[PACKAGE_88_ORDINAL]
    owned_89 = counts[PACKAGE_89_ORDINAL]
    owned_90 = counts[PACKAGE_90_ORDINAL]
    owned_91 = counts[PACKAGE_91_ORDINAL]
    owned_92 = counts[PACKAGE_92_ORDINAL]
    owned_93 = counts[PACKAGE_93_ORDINAL]
    assert set(PKG78_SPAN_REFS) <= owned_78 and len(owned_78) == 12
    assert set(PKG79_SPAN_REFS) <= owned_79 and len(owned_79) == 8
    assert set(PKG82_SPAN_REFS) <= owned_82 and len(owned_82) == 5
    assert set(PKG87_SPAN_REFS) <= owned_87 and len(owned_87) == 10
    assert set(PKG88_SPAN_REFS) <= owned_88 and len(owned_88) == 3
    assert set(PKG89_SPAN_REFS) <= owned_89 and len(owned_89) == 6
    assert set(PKG90_SPAN_REFS) <= owned_90 and len(owned_90) == 11
    assert set(PKG91_SPAN_REFS) <= owned_91 and len(owned_91) == 8
    assert set(PKG92_SPAN_REFS) <= owned_92 and len(owned_92) == 4
    assert set(PKG93_SPAN_REFS) <= owned_93 and len(owned_93) == 11


# ---------------------------------------------------------------------------
# frozen plan ownership and source identity
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_90(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_90_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, expected in OWNED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == expected, f"{ref} 摘录与冻结计划不一致"


def test_owned_unit_kinds_and_heading_paths(config: dict, plan: dict) -> None:
    """p1087-p1089/p1095-p1097为paragraph；p1090-p1094为list_item；全部拥有
    单元位于'不良事件因果关系判断'标题之下。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[ref], ref
        assert unit["heading_path"][-1] == "不良事件因果关系判断", ref
        assert "不良事件的评估" in unit["heading_path"], ref
        assert "安全性评估" in unit["heading_path"], ref


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    """段落/列表项摘录必须与源结构块逐段文本一致，证明无改写、无拼接错位。"""
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        assert _structure_blob_text(structure_blob, ref) == excerpts[ref], ref


def test_attached_table9_excerpts_contain_symbol_annotations(
    plan: dict,
) -> None:
    """表9只读闭包必须包含五级结论行、五个要点对应行与+/-/±/++/-?注记。"""
    units = _frozen_unit_by_ref(plan)
    excerpts = {ref: units[ref]["excerpt"] for ref in TABLE9_ATTACHED_REFS}
    assert excerpts["body.t14.r0"] == "判定依据 | 相关 | 不相关"
    assert "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关" in excerpts["body.t14.r1"]
    assert excerpts["body.t14.r2"].startswith("是否有合理的时间关系")
    assert excerpts["body.t14.r3"].startswith("是否符合已知的作用机制")
    assert excerpts["body.t14.r4"].startswith("去激发结果")
    assert excerpts["body.t14.r5"].startswith("再激发结果")
    assert excerpts["body.t14.r6"].startswith("是否可用其他合理的原因解释")
    assert "“+/”" in excerpts["body.t14.r7"] or "-/?" in excerpts["body.t14.r7"]
    assert "尚未进行去激发" in excerpts["body.t14.r7"]
    assert "不适用去激发" in excerpts["body.t14.r7"]
    assert "时间关系不能排除" in excerpts["body.t14.r7"]
    for ref in TABLE9_ATTACHED_REFS:
        assert units[ref]["heading_path"][-1] == "表 9 不良事件与试验用药品因果关系评价", ref


# ---------------------------------------------------------------------------
# five evaluation points: comprehensive-judgment inputs
# ---------------------------------------------------------------------------


def test_five_points_are_comprehensive_judgment_inputs(config: dict) -> None:
    """五个评价要点是综合评价输入：p1089总纲必须显式声明四种禁止变形。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1089"]
    assert "五个评价要点" in semantics["base_rule"]
    for fragment in (
        "不是全部满足条件",
        "不是固定计分规则",
        "不是任一单项充分条件",
        "也不是机械决策树",
        "综合评价",
        "提供相关性判定依据",
    ):
        assert fragment in semantics["exception_rule"], fragment
    for ref in FIVE_POINT_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert entry["semantic_role"].startswith("five_points_input_"), ref
        assert "综合评价输入之一" in entry["exception_rule"], ref
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得改为全部满足（AND化）、固定计分、任一单项充分条件或机械决策树" in checks_blob


def test_five_points_and_ification_counterexamples_detected() -> None:
    """五要点AND化（全部同时满足/缺一不可）反例必须被确定性拦截。"""
    counterexamples = [
        "研究者需根据五个评价要点进行综合评价，五个要点均需满足方可判定相关。",
        "五个评价要点必须全部满足，否则不判定相关。",
        "五个要点缺一不可，全部评价要点同时满足才可判定相关性。",
        "评价相关性时五个要点全部满足、均需满足。",
        "五个评价要点需同时满足，缺一即判定无关。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"五要点AND化反例未被门禁拦截: {text}"


def test_five_points_scoring_counterexamples_detected() -> None:
    """固定计分化反例必须被确定性拦截。"""
    counterexamples = [
        "按要点计分，五个要点按权重评分后加总判定。",
        "采用固定计分：每个评价要点计分达到3分即相关。",
        "要点加权后得分达到阈值即判定相关。",
        "按评分规则对五个要点打分，按计分规则判定相关级别。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"五要点计分化反例未被门禁拦截: {text}"


def test_five_points_single_sufficient_counterexamples_detected() -> None:
    """单项充分条件化反例必须被确定性拦截。"""
    counterexamples = [
        "任一要点满足即判定与试验用药品相关。",
        "五个要点中单项满足即可判定相关。",
        "只要一个要点符合即判定相关，单项充分条件成立。",
        "任一要点即可判定相关，单一要点即达到判定标准。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"五要点单项充分化反例未被门禁拦截: {text}"


def test_five_points_decision_tree_counterexamples_detected() -> None:
    """机械决策树化反例必须被确定性拦截。"""
    counterexamples = [
        "按决策树依次核对五个要点后自动判定相关。",
        "建立机械决策流程，机械判定相关性。",
        "由系统按算法判定相关，无需研究者综合评价。",
        "机械决策：时间相关且已知即自动判定相关。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"五要点决策树化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# table number inconsistency (表7 vs 表9) preserved
# ---------------------------------------------------------------------------


def test_table_number_inconsistency_preserved(config: dict, plan: dict) -> None:
    """p1095'可参照表7进行'与p1097'表 9'必须同时逐字保留，方案内部不一致
    标为需要核对，不得静默纠正。"""
    excerpts = _owned_excerpt_by_ref(plan)
    assert "可参照表7进行" in excerpts["body.p1095"]
    assert "表 9 不良事件与试验用药品因果关系评价" == excerpts["body.p1097"]
    note = config["later_package_boundary"]["note"]
    assert "表7" in note and "表9" in note
    assert "不一致必须保留" in note
    assert "需要核对" in note
    semantics = config["exception_semantics_by_source_ref"]["body.p1095"]
    assert "可参照表7进行" in semantics["preserve_keywords"]
    assert "不得把'可参照表7进行'静默改成'可参照表9进行'" in semantics["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1095"])
    assert "必须保留并标为需要核对" in checks


def test_table_number_silent_correction_counterexamples_detected() -> None:
    """表号静默纠正反例必须被确定性拦截。"""
    counterexamples = [
        "相关性判定结果分类及判定依据可参照表9进行。",
        "判定依据参照表9进行，不再使用表7。",
        "将表7更正为表9后执行。",
        "方案中的表7即表9，表7实为表9。",
        "表7应为表9，表7系笔误。",
        "判定依据参照表7（即表9）进行。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"表号静默纠正反例未被门禁拦截: {text}"
    # 合法来源文本不得误拦截
    plan = _load_json(PLAN_PATH)
    for ref in OWNED_REFS:
        hits = _deterministic_hits(_owned_excerpt_by_ref(plan)[ref])
        assert hits == [], f"误拦截合法来源 {ref}: {hits}"


def test_table7_secondary_event_rules_not_absorbed(config: dict) -> None:
    """第82包表7继发事件规则（body.t12.r0-r4）不得进入本包拥有、附加或提示。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    assert set(PKG82_SPAN_REFS).isdisjoint(owned)
    assert set(PKG82_SPAN_REFS).isdisjoint(attached)
    note = config["later_package_boundary"]["note"]
    assert "第82包表7继发事件规则（body.t12.r0-r4）不得吸入本包" in note
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for leaked in ("继发事件", "body.t12"):
        assert leaked not in prompt_text, f"表7继发事件规则泄漏进第90包提示: {leaked}"


# ---------------------------------------------------------------------------
# statistical grouping boundary
# ---------------------------------------------------------------------------


def test_statistical_grouping_keeps_three_classes(config: dict, plan: dict) -> None:
    """统计分析相关分组只含肯定有关/很可能有关/可能有关三类。"""
    excerpts = _owned_excerpt_by_ref(plan)
    text = excerpts["body.p1095"]
    assert "将“肯定有关”、“很可能有关”、“可能有关”视为与试验用药品相关" in text
    semantics = config["exception_semantics_by_source_ref"]["body.p1095"]
    assert "只含'肯定有关、很可能有关、可能有关'三类" in semantics["exception_rule"]
    assert "不得把统计分组扩大到'可能无关'或'无关'" in semantics["forbidden_inversion"]
    assert "不得从统计分组反推个例报告规则" in semantics["forbidden_inversion"]


def test_stat_group_expansion_counterexamples_detected() -> None:
    """统计分组扩大（纳入可能无关/无关）反例必须被确定性拦截。"""
    counterexamples = [
        "统计分析时，统计分组包含可能无关。",
        "将'可能无关'也视为相关，可能无关也视为相关。",
        "无关也视为相关，纳入统计相关组。",
        "统计分组扩大为五类。",
        "统计时纳入可能无关与无关。",
        "将可能无关纳入相关组统计。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"统计分组扩大反例未被门禁拦截: {text}"
    # 合法p1095不得误拦截
    plan = _load_json(PLAN_PATH)
    assert _deterministic_hits(_owned_excerpt_by_ref(plan)["body.p1095"]) == []


def test_reverse_inference_counterexamples_detected() -> None:
    """由统计相关分组反推个例报告规则的反例必须被确定性拦截。"""
    counterexamples = [
        "统计相关即个例报告，必须上报。",
        "统计相关即需报告，统计相关即确认相关。",
        "相关分组即报告范围，统计相关的个例必须上报。",
        "按统计分组反推个例报告规则。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"统计分组反推个例报告反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# p1096 SAE joint judgment: OR not AND, report scope not confirmation
# ---------------------------------------------------------------------------


def test_p1096_joint_judgment_or_report_scope(config: dict) -> None:
    """共同判断不等于双方一致；任一方判断相关即进入报告范围（OR）。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1096"]
    assert "共同判断不等于双方意见一致" in semantics["exception_rule"]
    assert "任意一方判断相关即进入报告范围（OR）" in semantics["exception_rule"]
    assert "不得把OR改为AND" in semantics["forbidden_inversion"]
    assert "不得把'报告范围'升级为'最终确认相关'" in semantics["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1096"])
    assert "任一方判断相关即进入报告范围（OR）" in checks
    assert "不得升级为'最终确认相关'或'因果结论成立'" in checks


def test_joint_judgment_and_ification_counterexamples_detected() -> None:
    """把共同判断改写成双方一致（AND）的反例必须被确定性拦截。"""
    counterexamples = [
        "双方一致才判定相关并报告。",
        "研究者与申办者双方均判断相关才进入报告范围。",
        "只有双方一致判断相关时方可报告。",
        "必须双方一致，双方一致判断为报告前提。",
        "双方意见一致时才属报告范围。",
        "双方都判断相关方进入报告范围。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"双方判断AND化反例未被门禁拦截: {text}"


def test_report_scope_upgrade_counterexamples_detected() -> None:
    """把'报告范围'升级为'最终确认相关'的反例必须被确定性拦截。"""
    counterexamples = [
        "任意一方判断相关即最终确认相关。",
        "任一方判断相关即确认相关成立。",
        "任意一方判断相关即确认为最终相关。",
        "任一方判断相关即因果结论成立。",
        "共同判断后即确认因果关系成立。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"报告范围升级反例未被门禁拦截: {text}"
    # 合法p1096不得误拦截
    plan = _load_json(PLAN_PATH)
    assert _deterministic_hits(_owned_excerpt_by_ref(plan)["body.p1096"]) == []


# ---------------------------------------------------------------------------
# cross-dimension separation
# ---------------------------------------------------------------------------


def test_dimension_separation_never_conflated(config: dict) -> None:
    """因果关系、严重程度、SAE严重性、预期性和报告时限是不同维度。"""
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "因果关系、严重程度、SAE严重性和预期性、报告时限是不同维度，不得相互替代" in checks_blob
    # p1088五级结论与p1091已知性必须显式声明不与其他维度互相替代
    for ref in ("body.p1088", "body.p1091"):
        semantics = config["exception_semantics_by_source_ref"][ref]
        assert "不得" in semantics["forbidden_inversion"], ref
        assert any(
            token in semantics["forbidden_inversion"]
            for token in ("严重程度", "SAE", "预期性", "报告时限")
        ), ref
    note = config["later_package_boundary"]["note"]
    assert "严重程度、SAE严重性、预期性、报告时限与因果关系是不同维度" in note


def test_dimension_conflation_counterexamples_detected() -> None:
    """跨维度混同反例必须被确定性措辞门禁拦截。"""
    conflated = [
        "因果关系即严重程度，按严重程度判定相关。",
        "严重程度即因果关系，达到3级即相关。",
        "因果判断即SAE判定，相关即SAE。",
        "按SAE严重性判断因果，SAE即相关。",
        "因果关系即预期性，预期性即因果关系。",
        "因果判断即报告时限，按报告时限判断因果。",
        "因果相关即SAE，直接上报。",
        "以严重程度判定因果，以预期性判定因果。",
    ]
    for text in conflated:
        hits = _deterministic_hits(text)
        assert hits, f"跨维度混同反例未被门禁拦截: {text}"
    # 合法来源文本不得误拦截
    plan = _load_json(PLAN_PATH)
    for pkg in plan["packages"]:
        for u in pkg["owned_units"]:
            hits = _deterministic_hits(u["excerpt"])
            assert hits == [], f"误拦截合法来源 {u['source_ref']}: {hits}"
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert _deterministic_hits(prompt_text) == [], "提示含确定性反例措辞"


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
    assert "五分法" in by_ref["body.p1088"].excerpt
    assert "五个评价要点" in by_ref["body.p1089"].excerpt
    assert "时间相关性" in by_ref["body.p1090"].excerpt
    assert "是否已知" in by_ref["body.p1091"].excerpt
    assert "去激发结果" in by_ref["body.p1092"].excerpt
    assert "再激发结果" in by_ref["body.p1093"].excerpt
    assert "其他合理解释" in by_ref["body.p1094"].excerpt
    assert "可参照表7进行" in by_ref["body.p1095"].excerpt
    assert "均属报告范围" in by_ref["body.p1096"].excerpt

    # 只读闭包关键片段
    assert by_ref["body.t14.r0"].excerpt == "判定依据 | 相关 | 不相关"
    assert "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关" in by_ref["body.t14.r1"].excerpt
    assert "是否有合理的时间关系" in by_ref["body.t14.r2"].excerpt
    assert "-/?" in by_ref["body.t14.r4"].excerpt
    assert "-/?" in by_ref["body.t14.r5"].excerpt
    assert "++" in by_ref["body.t14.r6"].excerpt
    assert "尚未进行去激发" in by_ref["body.t14.r7"].excerpt
    assert "不适用去激发" in by_ref["body.t14.r7"].excerpt


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含本包闭包与防吞并边界，不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    # 相邻包仅第91包表9按合同只读进入；其余不得进入
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG91_NON_ATTACHED_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 11
    assert summary["attached_count"] == 8
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

    # 越界候选（把因果判断内容升格为筛选/基线控制候选）必须被拒绝
    for ref in ("body.p1089", "body.p1095", "body.p1096"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对因果关系综合判断掌握情况，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 即使标题使用短语探针未覆盖的同义改写，来源身份门禁仍必须拒绝候选。
    paraphrased_candidates = {
        "body.p1089": "五项依据齐备后由系统自动归因为相关",
        "body.p1095": "依后续因果评价表执行并扩大相关统计口径",
        "body.p1096": "仅在双方达成同一判断后形成最终因果结论",
    }
    for ref, title in paraphrased_candidates.items():
        assert _deterministic_hits(title) == [], "本测试必须证明无需短语命中也能拒绝"
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": title,
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 只读附加来源也只是上下文，任何候选发射都必须拒绝
    for ref in ("body.t14.r2", "body.t14.r7"):
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
    excerpts = _owned_excerpt_by_ref(plan)
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref in OWNED_REFS:
        hits = _forbidden_marker_hits(excerpts[ref], markers_by_ref[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把因果判断内容改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1087": [
            "筛选时核对因果关系判断标题掌握情况，未确认者不得入组",
        ],
        "body.p1088": [
            "筛选时核对五级相关性结论，未确认者证据缺口不得入组",
        ],
        "body.p1089": [
            "基线时核对五个评价要点掌握情况，未确认者入排不通过",
        ],
        "body.p1090": [
            "筛选时核对时间相关性要点，未确认者排除标准",
        ],
        "body.p1095": [
            "基线时核对统计分析分组，未确认者不得入组",
        ],
        "body.p1096": [
            "筛选时核对SAE共同判断规则，未确认者入组前必查",
        ],
        "body.p1097": [
            "筛选时核对表9入口标题，未确认者不得入组",
        ],
    }
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref, counterexamples in counterexamples_by_ref.items():
        for text in counterexamples:
            assert _forbidden_marker_hits(text, markers_by_ref[ref]), (
                f"门禁未拦截 {ref} 升格反例: {text}"
            )


# ---------------------------------------------------------------------------
# anti-absorption: package 78/79/82/87/88/89/91/92/93
# ---------------------------------------------------------------------------


def test_neighbor_spans_not_absorbed(config: dict) -> None:
    """第78/79/82/87/88/89/92/93包内容与第91包非附加内容均不得进入本包闭包。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for span in (
        PKG78_SPAN_REFS,
        PKG79_SPAN_REFS,
        PKG82_SPAN_REFS,
        PKG87_SPAN_REFS,
        PKG88_SPAN_REFS,
        PKG89_SPAN_REFS,
        PKG92_SPAN_REFS,
        PKG93_SPAN_REFS,
        PKG91_NON_ATTACHED_REFS,
    ):
        assert set(span).isdisjoint(owned), span[0]
        assert set(span).isdisjoint(attached), span[0]


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
    # 本包拥有单元只允许 p1087-p1097
    for ref in boundary["expected_owners_by_span"]:
        if ref in OWNED_REFS:
            assert boundary["expected_owners_by_span"][ref] == PACKAGE_90_ORDINAL


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第78包",
        "第79包",
        "第82包",
        "第87包",
        "第88包",
        "第89包",
        "第90包",
        "第91包",
        "第92包",
        "第93包",
        "吞并",
        "所有权",
        "body.t14.r0-r7",
        "body.t12.r0-r4",
        "需要核对",
        "表7",
        "表9",
        "预期性",
        "报告时限",
        "严重程度",
        "SAE严重性",
        "不得相互替代",
    ):
        assert fragment in note, f"边界注记缺少防吞并/防混同声明: {fragment}"


def test_prompt_excludes_neighbor_content() -> None:
    """第78/79/82/87/88/89/92/93包内容与第91包非附加内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for leaked in (
        "CTCAE",
        "严重程度分级",
        "预期性",
        "药物过量",
        "给药错误",
        "继发事件",
        "不明原因死亡",
        "body.t12",
        "body.t13",
        "body.p997",
        "body.p1098",
        "body.p1102",
    ):
        assert leaked not in prompt_text, f"相邻包内容泄漏进第90包提示: {leaked}"
    # 第91包仅表9行进入提示；其余第91包来源不得进入
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
        + PKG91_NON_ATTACHED_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入第90包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第90包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_table9_closure_and_attached_sources() -> None:
    """提示必须包含五要点/表号不一致/统计分组/共同判断语义与全部只读表9行。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "不良事件因果关系判断" in prompt_text
    assert "五分法" in prompt_text
    assert "肯定有关、很可能有关、可能有关、可能无关、无关" in prompt_text
    assert "五个评价要点" in prompt_text
    assert "综合评价" in prompt_text
    assert "时间相关性" in prompt_text
    assert "是否已知" in prompt_text
    assert "去激发结果" in prompt_text
    assert "再激发结果" in prompt_text
    assert "其他合理解释" in prompt_text
    assert "可参照表7进行" in prompt_text
    assert "视为与试验用药品相关" in prompt_text
    assert "均属报告范围" in prompt_text
    assert "表 9 不良事件与试验用药品因果关系评价" in prompt_text
    assert "判定依据 | 相关 | 不相关" in prompt_text
    assert "是否有合理的时间关系" in prompt_text
    assert "尚未进行去激发" in prompt_text
    assert "不适用去激发" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned", ref
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached", ref


def test_prompt_keeps_deterministic_semantics_clean() -> None:
    """提示不得出现五要点AND/计分/单项充分/决策树、表号纠正、统计分组扩大、
    反推、双方AND、范围升级或跨维度混同措辞。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    hits = _deterministic_hits(prompt_text)
    assert hits == [], f"提示含确定性反例措辞: {hits}"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package90(matrix: dict, plan: dict) -> None:
    pkg90 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg90["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第90包拥有来源为锚点"
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


def test_no_official_rule_anchors_package90_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg90 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_90_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg90["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第90包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package90_or_definition_spans(
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
    assert PACKAGE_89_ID in text
    assert PACKAGE_90_ID in text
    assert PACKAGE_91_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "五个评价要点" in text
    assert "可参照表7进行" in text
    assert "表 9 不良事件与试验用药品因果关系评价" in text
    assert "需要核对" in text
    assert "均属报告范围" in text
    assert "body.t14" in text
    assert "body.t12" in text
    assert "第78包" in text and "第79包" in text and "第82包" in text
    assert "第87包" in text and "第88包" in text and "第89包" in text
    assert "第90包" in text and "第91包" in text and "第92包" in text
    assert "第93包" in text
    assert "claims_complete" in text
