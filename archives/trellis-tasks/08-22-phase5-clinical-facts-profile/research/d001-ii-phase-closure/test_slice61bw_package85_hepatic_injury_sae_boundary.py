#!/usr/bin/env python3
"""Slice61bw model-free source-closure regressions.

Locks the D001 II package 85 severe hepatic injury indicators and abnormal
hepatic-function SAE recording/reporting boundary (frozen plan package 85:
严重肝损伤与肝功能检查异常, body.p1055-p1066) to its authoritative sources
before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 85 (1 structural heading + 11 semantic
  SAE recording/reporting rules); attached refs stay read-only
- structural unit (p1055) stays structural only; eleven semantic units keep
  post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- p1057 keeps the conjunction "ALT或AST>3×ULN 合并 (总胆红素>2×ULN 或 黄疸)"
  with the "无胆汁淤积或其他高胆红素血症的病因" qualifier; the inner OR
  (总胆红素>2×ULN 或 黄疸) and the outer conjunction are never inverted
- p1058 stays an independent alternative ratio indicator; the ratio on
  p1058/p1062/p1066 is always ALT或AST高值/ALP高值 — GGT, total bilirubin or
  other indicators never mix in
- p1059 keeps the outer OR ("以下任一"), the diagnosis-first recording
  priority (最恰当的诊断, lab abnormality only when 无法确定诊断), and the
  immediate sponsor report within no more than 24 hours of becoming aware;
  none of these may be dropped or weakened
- baseline stratification stays separated: p1060-p1062 only for AST/ALT and
  total bilirubin baseline-in-normal participants with two OR branches;
  p1063-p1066 only for baseline-above-ULN participants with three OR branches
- p1064 keeps "(ALT或AST> 2×基线值 且 > 3×ULN) 或 > 8×ULN（以较小者为准）":
  the inner conjunction never becomes OR, and 以较小者为准 never becomes
  以较大者为准 or 须全部满足
- p1065 keeps "总胆红素较基线升高至少1×ULN 或 总胆红素> 3×ULN（以较小者为准）"
  with the branch OR and 以较小者为准 intact
- package 84 (p1043-p1054) enters only as ownership metadata; package 86 DILI
  review/investigation/potential-confirmed Hy's law flow (p1067-p1073) is
  never absorbed, never attached, and never appears in the prompt
- official matrix keeps zero rows anchored in p1055-p1066 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no p1055-p1066 spans
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
    / "representative_group_package85_hepatic_injury_sae_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61bw-package85-hepatic-injury-sae-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package85-hepatic-injury-sae-boundary"
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
PACKAGE_85_ORDINAL = 85
PACKAGE_85_ID = "pap-be8085a9fd5705e64525e8e8"
PACKAGE_86_ORDINAL = 86
PACKAGE_86_ID = "pap-d27cb33cf06d737190efa6c7"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1055, 1067)]

# 结构单元：一个章节标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1055"]
# 语义单元：严重肝损伤指征与肝功能异常SAE记录/报告规则，保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1056, 1067)]

# 只读闭包：AE/TEAE定义（2）、SAE定义与严重性总纲（2）、
# AE收集期/给药前事件记录/全量记录义务/单一事件项一术语（4）、
# 流程/监测/D1给药前后锚点（3）
AE_DEF_ATTACHED_REFS = ["body.p986", "body.p994"]
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1023", "body.p1024", "body.p1026"]
FLOW_ANCHOR_REFS = ["body.p340", "body.p835", "body.p885"]
UNOWNED_CONTEXT_REFS = ["body.p340", "body.p885"]
ATTACHED_REFS = (
    AE_DEF_ATTACHED_REFS
    + SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
)

# 相邻包所有权元数据：第84包（前接，p1043-p1054）与第86包（防吞并，p1067-p1073）
# 均不进入附加闭包，也不得被本包拥有或处置
PKG84_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]
PKG86_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1067, 1074)]

# 各语义单元的合取/OR结构、基线分层、诊断优先级、24小时与比值语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1056": {
        "base_rule": "参考海氏定律（Hy's law）中的定义，严重肝损伤的指征包括：",
        "exception_rule": "严重肝损伤指征总引：p1057/p1058为两个并列指征（外层OR）；引用海氏定律定义仅为指征来源说明，不引入第86包复查/调查/确诊流程",
        "preserve_keywords": ["海氏定律", "严重肝损伤的指征包括"],
    },
    "body.p1057": {
        "base_rule": "ALT或AST升高（> 3×ULN）合并总胆红素升高（> 2×ULN）或合并黄疸（无胆汁淤积或其他高胆红素血症的病因）；",
        "exception_rule": "严重肝损伤指征一（合取+内层OR）：ALT或AST>3×ULN与（总胆红素>2×ULN或黄疸）必须同时满足；'无胆汁淤积或其他高胆红素血症的病因'限定必须保留",
        "preserve_keywords": ["3×ULN", "2×ULN", "合并", "黄疸", "无胆汁淤积或其他高胆红素血症的病因"],
    },
    "body.p1058": {
        "base_rule": "ALT或AST高值与ALP高值的比值≥5。",
        "exception_rule": "严重肝损伤指征二（独立替代指征）：ALT或AST高值与ALP高值的比值≥5，与p1057为并列指征（外层OR）",
        "preserve_keywords": ["ALT或AST高值", "ALP高值", "比值≥5"],
    },
    "body.p1059": {
        "base_rule": "研究者必须将以下任一肝功能检查异常的情况的发生作为SAE在eCRF不良事件上记录为最恰当的诊断或（如果无法确定诊断）实验室检查值异常，并立即报告给申办者（即，在获知事件后不超过24小时）：",
        "exception_rule": "SAE记录与立即报告总纲：'以下任一'必须与人群分层一起理解，即（符合p1060基线人群且满足p1061或p1062）或（符合p1063基线人群且满足p1064、p1065或p1066之一）时触发；记录优先级为最恰当的诊断，无法确定诊断时才记录实验室检查值异常；24小时从获知事件起算并限定报告义务",
        "preserve_keywords": ["以下任一", "作为SAE", "最恰当的诊断", "无法确定诊断", "实验室检查值异常", "立即报告给申办者", "24小时"],
    },
    "body.p1060": {
        "base_rule": "（1）对于AST/ALT和总胆红素基线值在正常范围的参与者，在研究治疗后出现以下情况之一：",
        "exception_rule": "基线正常人群限定：仅适用于AST/ALT和总胆红素基线值均在正常范围的参与者；'以下情况之一'表明p1061/p1062两个分支为OR",
        "preserve_keywords": ["基线值在正常范围", "以下情况之一"],
    },
    "body.p1061": {
        "base_rule": "ALT或AST> 3×ULN合并总胆红素> 2×ULN",
        "exception_rule": "基线正常分支一（合取）：ALT或AST>3×ULN与总胆红素>2×ULN必须同时满足；与p1062为OR并列分支",
        "preserve_keywords": ["3×ULN", "2×ULN", "合并"],
    },
    "body.p1062": {
        "base_rule": "ALT或AST高值与ALP高值的比值≥5",
        "exception_rule": "基线正常分支二：ALT或AST高值与ALP高值的比值≥5；与p1061为OR并列分支",
        "preserve_keywords": ["ALT或AST高值", "ALP高值", "比值≥5"],
    },
    "body.p1063": {
        "base_rule": "（2）对于AST/ALT和总胆红素基线值> ULN的参与者，在研究治疗后出现以下情况之一：",
        "exception_rule": "基线异常人群限定：仅适用于AST/ALT和总胆红素基线值高于ULN的参与者；'以下情况之一'表明p1064/p1065/p1066三个分支为OR",
        "preserve_keywords": ["基线值> ULN", "以下情况之一"],
    },
    "body.p1064": {
        "base_rule": "AST/ALT基线值超出正常范围：研究治疗后出现ALT或AST> 2×基线值且> 3×ULN，或> 8×ULN（以较小者为准）",
        "exception_rule": "AST/ALT基线异常分支：'ALT或AST> 2×基线值 且 > 3×ULN'为内层合取，与'> 8×ULN'为OR；'以较小者为准'必须保留；与p1065/p1066为OR并列分支",
        "preserve_keywords": ["2×基线值", "3×ULN", "8×ULN", "且", "以较小者为准"],
    },
    "body.p1065": {
        "base_rule": "总胆红素基线值超出正常范围：研究治疗后出现总胆红素较基线升高至少1×ULN或总胆红素> 3×ULN（以较小者为准）",
        "exception_rule": "总胆红素基线异常分支：'总胆红素较基线升高至少1×ULN'与'总胆红素> 3×ULN'为本分支内OR；'以较小者为准'必须保留；与p1064/p1066为OR并列分支",
        "preserve_keywords": ["较基线升高至少1×ULN", "3×ULN", "以较小者为准"],
    },
    "body.p1066": {
        "base_rule": "ALT或AST高值与ALP高值的比值≥5",
        "exception_rule": "基线异常分支三：ALT或AST高值与ALP高值的比值≥5；与p1064/p1065为OR并列分支",
        "preserve_keywords": ["ALT或AST高值", "ALP高值", "比值≥5"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"
TEAE_DEFINITION_REF = "body.p994"
SAE_DEFINITION_REF = "body.p996"
SAE_OR_LEAD_REF = "body.p997"
RECORDING_OBLIGATION_REF = "body.p1024"
COLLECTION_WINDOW_REF = "body.p1022"
PRE_DOSE_EVENT_RECORD_REF = "body.p1023"
SINGLE_EVENT_TERM_REF = "body.p1026"
AE_RECORD_START_REF = "body.p340"
D1_PRE_DOSE_BASELINE_REF = "body.p885"
MONITORING_REF = "body.p835"
PKG85_HEADING_REF = "body.p1055"
PKG85_INDICATOR_LEAD_REF = "body.p1056"
PKG85_INDICATOR_CONJUNCTION_REF = "body.p1057"
PKG85_INDICATOR_RATIO_REF = "body.p1058"
PKG85_SAE_RECORD_REPORT_REF = "body.p1059"
PKG85_NORMAL_BASELINE_LEAD_REF = "body.p1060"
PKG85_NORMAL_BASELINE_TBIL_REF = "body.p1061"
PKG85_NORMAL_BASELINE_RATIO_REF = "body.p1062"
PKG85_ABNORMAL_BASELINE_LEAD_REF = "body.p1063"
PKG85_ABNORMAL_BASELINE_ALT_REF = "body.p1064"
PKG85_ABNORMAL_BASELINE_TBIL_REF = "body.p1065"
PKG85_ABNORMAL_BASELINE_RATIO_REF = "body.p1066"

# 结构级关键片段：编码AND/OR结构与限定条件的逐字片段，反例改写必须破坏至少一个
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1056": ["严重肝损伤的指征包括"],
    "body.p1057": [
        "合并总胆红素升高（> 2×ULN）或合并黄疸",
        "无胆汁淤积或其他高胆红素血症的病因",
    ],
    "body.p1058": ["ALT或AST高值与ALP高值的比值≥5"],
    "body.p1059": [
        "以下任一肝功能检查异常",
        "记录为最恰当的诊断或（如果无法确定诊断）实验室检查值异常",
        "立即报告给申办者",
        "获知事件后不超过24小时",
    ],
    "body.p1060": ["基线值在正常范围的参与者", "以下情况之一"],
    "body.p1061": ["ALT或AST> 3×ULN合并总胆红素> 2×ULN"],
    "body.p1062": ["ALT或AST高值与ALP高值的比值≥5"],
    "body.p1063": ["基线值> ULN的参与者", "以下情况之一"],
    "body.p1064": [
        "ALT或AST> 2×基线值且> 3×ULN，或> 8×ULN（以较小者为准）",
    ],
    "body.p1065": [
        "总胆红素较基线升高至少1×ULN或总胆红素> 3×ULN（以较小者为准）",
    ],
    "body.p1066": ["ALT或AST高值与ALP高值的比值≥5"],
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _missing_exception_keywords(text: str, entry: dict) -> list[str]:
    """确定性合取/例外门禁：来源文本必须同时保留基础规则与例外条款关键词。"""
    return [kw for kw in entry["preserve_keywords"] if kw not in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码AND/OR结构与限定的逐字片段。"""
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
    assert config["group_id"] == "d001-ii-package85-hepatic-injury-sae-boundary"
    assert config["task_id"] == "phase5-slice61bw-20260830"
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
    assert structural == set(STRUCTURAL_REFS), "章节标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第85包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第85包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗后SAE记录/报告处置；结构单元不进入处置映射
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
    pkg85 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL
    )
    owned_85 = {u["source_ref"] for u in pkg85["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_85), "attached refs must not be owned by package 85"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 11


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


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第84包拥有p1043-p1054（12），第85包拥有p1055-p1066（12），
    第86包拥有p1067-p1073（7）。"""
    pkg84 = next(p for p in plan["packages"] if p["package_ordinal"] == 84)
    pkg85 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL)
    pkg86 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL)
    owned_84 = {u["source_ref"] for u in pkg84["owned_units"]}
    owned_85 = {u["source_ref"] for u in pkg85["owned_units"]}
    owned_86 = {u["source_ref"] for u in pkg86["owned_units"]}
    assert set(PKG84_SPAN_REFS) <= owned_84 and len(owned_84) == 12
    assert set(OWNED_REFS) <= owned_85 and len(owned_85) == 12
    assert set(PKG86_SPAN_REFS) <= owned_86 and len(owned_86) == 7


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_85(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_85_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1055"] == "严重肝损伤与肝功能检查异常"
    assert excerpts["body.p1056"] == (
        "参考海氏定律（Hy’s law）中的定义，严重肝损伤的指征包括："
    )
    assert excerpts["body.p1057"] == (
        "ALT或AST升高（> 3×ULN）合并总胆红素升高（> 2×ULN）或合并黄疸"
        "（无胆汁淤积或其他高胆红素血症的病因）；"
    )
    assert excerpts["body.p1058"] == "ALT或AST高值与ALP高值的比值≥5。"
    assert excerpts["body.p1059"] == (
        "研究者必须将以下任一肝功能检查异常的情况的发生作为SAE在eCRF不良事件上"
        "记录为最恰当的诊断或（如果无法确定诊断）实验室检查值异常，并立即报告给"
        "申办者（即，在获知事件后不超过24小时）："
    )
    assert excerpts["body.p1060"] == (
        "（1）对于AST/ALT和总胆红素基线值在正常范围的参与者，在研究治疗后出现"
        "以下情况之一："
    )
    assert excerpts["body.p1061"] == "ALT或AST> 3×ULN合并总胆红素> 2×ULN"
    assert excerpts["body.p1062"] == "ALT或AST高值与ALP高值的比值≥5"
    assert excerpts["body.p1063"] == (
        "（2）对于AST/ALT和总胆红素基线值> ULN的参与者，在研究治疗后出现以下"
        "情况之一："
    )
    assert excerpts["body.p1064"] == (
        "AST/ALT基线值超出正常范围：研究治疗后出现ALT或AST> 2×基线值且> 3×ULN，"
        "或> 8×ULN（以较小者为准）"
    )
    assert excerpts["body.p1065"] == (
        "总胆红素基线值超出正常范围：研究治疗后出现总胆红素较基线升高至少1×ULN"
        "或总胆红素> 3×ULN（以较小者为准）"
    )
    assert excerpts["body.p1066"] == "ALT或AST高值与ALP高值的比值≥5"


# ---------------------------------------------------------------------------
# structural-only unit and semantic rows
# ---------------------------------------------------------------------------


def test_structural_unit_does_not_form_control_point(config: dict, plan: dict) -> None:
    """章节标题（p1055）不形成控制点；十一个语义单元保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1055"] == "严重肝损伤与肝功能检查异常"
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1043-p1054 -> 84, p1067-p1073 -> 86
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """第84包与第86包来源可保留所有权元数据，但不得进入本包闭包或由本包发射。"""
    boundary = config["later_package_boundary"]
    expected_boundary = set(PKG84_SPAN_REFS + OWNED_REFS + PKG86_SPAN_REFS)
    assert set(boundary["expected_owners_by_span"]) == expected_boundary
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 85
    for ref in PKG84_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 84
    for ref in PKG86_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 86
    neighbor = set(PKG84_SPAN_REFS + PKG86_SPAN_REFS)
    assert neighbor.isdisjoint(set(config["owned_source_refs"])), (
        "第84包/第86包来源不得被第85包拥有"
    )
    attached = set(config["attached_source_refs"])
    assert neighbor.isdisjoint(attached), (
        "第84包/第86包来源不得进入第85包附加闭包"
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
        assert expected_ordinal != PACKAGE_85_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第85包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第84包", "第85包", "第86包", "吞并", "所有权不得转移", "第90", "第92", "24小时"):
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
    assert "海氏定律" in by_ref[PKG85_INDICATOR_LEAD_REF].excerpt
    assert "合并总胆红素升高" in by_ref[PKG85_INDICATOR_CONJUNCTION_REF].excerpt
    assert "无胆汁淤积或其他高胆红素血症的病因" in by_ref[PKG85_INDICATOR_CONJUNCTION_REF].excerpt
    assert "ALP高值" in by_ref[PKG85_INDICATOR_RATIO_REF].excerpt
    assert "最恰当的诊断" in by_ref[PKG85_SAE_RECORD_REPORT_REF].excerpt
    assert "获知事件后不超过24小时" in by_ref[PKG85_SAE_RECORD_REPORT_REF].excerpt
    assert "基线值在正常范围" in by_ref[PKG85_NORMAL_BASELINE_LEAD_REF].excerpt
    assert "合并总胆红素> 2×ULN" in by_ref[PKG85_NORMAL_BASELINE_TBIL_REF].excerpt
    assert "ALP高值" in by_ref[PKG85_NORMAL_BASELINE_RATIO_REF].excerpt
    assert "基线值> ULN" in by_ref[PKG85_ABNORMAL_BASELINE_LEAD_REF].excerpt
    assert "以较小者为准" in by_ref[PKG85_ABNORMAL_BASELINE_ALT_REF].excerpt
    assert "以较小者为准" in by_ref[PKG85_ABNORMAL_BASELINE_TBIL_REF].excerpt
    assert "ALP高值" in by_ref[PKG85_ABNORMAL_BASELINE_RATIO_REF].excerpt

    # 只读闭包关键片段
    assert "有临床意义的实验室检查异常" in by_ref[AE_DEFINITION_REF].excerpt
    assert "给药后出现的任何不利的医学事件" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "符合下列标准任何一项的不良事件" in by_ref[SAE_OR_LEAD_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "不作为AE记录" in by_ref[PRE_DOSE_EVENT_RECORD_REF].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref[SINGLE_EVENT_TERM_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt
    assert "D1给药前结果作为基线值" in by_ref[D1_PRE_DOSE_BASELINE_REF].excerpt
    assert "严密监测" in by_ref[MONITORING_REF].excerpt


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
    for ref in PKG84_SPAN_REFS + PKG86_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 11
    assert summary["unit_count"] == 23
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

    # 越界候选（把肝功能异常SAE记录/报告升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1059"]],
                "title": "筛选时核对肝功能检查异常SAE报告安排，未确认者按证据缺口判定入排不通过",
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
    """确定性门禁必须拒绝把SAE记录/报告规范改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1055": [
            "筛选时核对严重肝损伤记录安排，未完成者不得入组",
        ],
        "body.p1056": [
            "筛选时评估严重肝损伤指征判断能力，证据不足者按排除标准判定不通过",
        ],
        "body.p1057": [
            "筛选时核对ALT或AST与总胆红素合取判断安排，未确认者入排不通过",
        ],
        "body.p1058": [
            "筛选时核对ALT或AST/ALP比值计算安排，未完成者证据缺口不得入组",
        ],
        "body.p1059": [
            "筛选时核对肝功能异常SAE报告能力，证据不足者不得入组",
        ],
        "body.p1060": [
            "筛选时核对基线肝功能正常人群判断，未确认者入排不通过",
        ],
        "body.p1061": [
            "筛选时核对ALT或AST>3×ULN合并总胆红素>2×ULN记录安排，未完成者不得入组",
        ],
        "body.p1062": [
            "筛选时核对比值≥5记录安排，未确认者证据缺口入排不通过",
        ],
        "body.p1063": [
            "筛选时核对基线肝功能异常人群判断，未确认者不得入组",
        ],
        "body.p1064": [
            "筛选时核对2×基线且3×ULN判定安排，未完成者入排不通过",
        ],
        "body.p1065": [
            "筛选时核对总胆红素基线异常判定安排，未完成者不得入组",
        ],
        "body.p1066": [
            "筛选时核对比值≥5记录安排，未确认者证据缺口不得入组",
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
    """合取/OR结构、基线分层、诊断优先级、24小时与比值关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或记录路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1056": "严重肝损伤的指征如下。",
        "body.p1057": "ALT或AST升高或总胆红素升高。",
        "body.p1058": "ALT或AST高值与GGT高值的比值≥5。",
        "body.p1059": "研究者将肝功能检查异常记录为实验室检查值异常并尽快报告。",
        "body.p1060": "在研究治疗后出现以下情况之一：",
        "body.p1061": "ALT或AST> 3×ULN或总胆红素> 2×ULN",
        "body.p1062": "ALT或AST高值与GGT高值的比值≥5",
        "body.p1063": "在研究治疗后出现以下情况之一：",
        "body.p1064": "研究治疗后出现ALT或AST> 2×基线值或> 3×ULN，或> 8×ULN。",
        "body.p1065": "研究治疗后出现总胆红素较基线升高至少1×ULN且总胆红素> 3×ULN。",
        "body.p1066": "ALT或AST高值与GGT高值的比值≥5",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# AND/OR structure gates
# ---------------------------------------------------------------------------


def test_structural_fragments_present_in_owned_sources(plan: dict, config: dict) -> None:
    """编码AND/OR结构与限定的逐字片段必须完整保留在来源摘录中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref, fragments in STRUCTURAL_FRAGMENTS_BY_REF.items():
        for fragment in fragments:
            assert fragment in excerpts[ref], f"{ref} 丢失结构级片段: {fragment}"


def test_and_or_inversion_counterexamples_detected(config: dict) -> None:
    """AND/OR反转、阈值错配、较小者丢失、24小时弱化反例必须被确定性拦截。"""
    inverted = {
        "body.p1057": [
            "ALT或AST升高（> 3×ULN）或总胆红素升高（> 2×ULN）或合并黄疸。",
            "ALT或AST升高（> 3×ULN）合并总胆红素升高（> 2×ULN）或合并黄疸。",
            "ALT或AST升高（> 3×ULN）合并总胆红素升高（> 2×ULN）。",
        ],
        "body.p1058": [
            "ALT或AST高值与GGT高值的比值≥5。",
            "ALT或AST高值与总胆红素高值的比值≥5。",
            "ALT或AST高值与ALP高值的比值≥3。",
            "ALT或AST高值与ALP高值均高于5。",
        ],
        "body.p1059": [
            "研究者必须将以下全部肝功能检查异常的情况的发生作为SAE在eCRF不良事件上记录。",
            "研究者将肝功能检查异常作为SAE在eCRF不良事件上记录为实验室检查值异常，并报告给申办者。",
            "研究者必须将以下任一肝功能检查异常的情况的发生作为SAE在eCRF不良事件上记录为最恰当的诊断或（如果无法确定诊断）实验室检查值异常，并尽快报告给申办者。",
            "研究者必须将以下任一肝功能检查异常的情况的发生作为SAE在eCRF不良事件上记录为最恰当的诊断或（如果无法确定诊断）实验室检查值异常，并立即报告给申办者（即，在获知事件后不超过48小时）。",
        ],
        "body.p1060": [
            "在研究治疗后出现以下情况之一：",
            "对于AST/ALT和总胆红素基线值高于ULN的参与者，在研究治疗后出现以下情况之一：",
            "对于AST/ALT和总胆红素基线值在正常范围的参与者，在研究治疗后出现以下全部情况：",
        ],
        "body.p1061": [
            "ALT或AST> 3×ULN或总胆红素> 2×ULN",
            "ALT或AST> 4×ULN合并总胆红素> 2×ULN",
        ],
        "body.p1062": [
            "ALT或AST高值与GGT高值的比值≥5",
            "ALT或AST高值与ALP高值的比值≥4",
        ],
        "body.p1063": [
            "在研究治疗后出现以下情况之一：",
            "对于AST/ALT和总胆红素基线值在正常范围的参与者，在研究治疗后出现以下情况之一：",
            "对于AST/ALT和总胆红素基线值> ULN的参与者，在研究治疗后出现以下全部情况：",
        ],
        "body.p1064": [
            "研究治疗后出现ALT或AST> 2×基线值或> 3×ULN，或> 8×ULN（以较小者为准）",
            "研究治疗后出现ALT或AST> 2×基线值且> 3×ULN，且> 8×ULN（以较小者为准）",
            "研究治疗后出现ALT或AST> 2×基线值且> 3×ULN，或> 8×ULN（以较大者为准）",
            "研究治疗后出现ALT或AST> 2×基线值且> 3×ULN，或> 8×ULN（须全部满足）",
        ],
        "body.p1065": [
            "研究治疗后出现总胆红素较基线升高至少1×ULN且总胆红素> 3×ULN（以较小者为准）",
            "研究治疗后出现总胆红素较基线升高至少1×ULN或总胆红素> 3×ULN（以较大者为准）",
            "研究治疗后出现总胆红素较基线升高至少2×ULN或总胆红素> 3×ULN（以较小者为准）",
        ],
        "body.p1066": [
            "ALT或AST高值与GGT高值的比值≥5",
            "ALT或AST高值与ALP高值的比值≥6",
        ],
    }
    for ref, counterexamples in inverted.items():
        for text in counterexamples:
            missing = _missing_structural_fragments(text, ref)
            assert missing, f"{ref} AND/OR反转反例未被结构片段门禁拦截: {text}"


def test_p1059_reporting_priority_and_24h_never_weakened(config: dict) -> None:
    """诊断优先级、立即报告与24小时边界必须完整保留。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1059"]
    assert "记录优先级为最恰当的诊断" in entry["exception_rule"]
    assert "无法确定诊断时才记录实验室检查值异常" in entry["exception_rule"]
    assert "24小时时钟从获知事件起算并只限定报告义务" in entry["exception_rule"]
    assert "改用采血/出结果时间起算" in entry["forbidden_inversion"]
    assert "把24小时错绑到eCRF记录完成时间" in entry["forbidden_inversion"]
    assert "不得把立即报告弱化为'尽快报告'" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1059"])
    assert "诊断优先级" in checks
    assert "24小时" in checks
    assert "第92包通用SAE报告流程" in checks


def test_p1059_keeps_population_gates_around_child_or_branches(config: dict) -> None:
    """p1059 不得把两个基线人群前提与各自的 OR 子分支扁平化。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1059"]
    assert "符合p1060基线人群且满足p1061或p1062" in entry["exception_rule"]
    assert "符合p1063基线人群且满足p1064、p1065或p1066之一" in entry["exception_rule"]
    assert "p1061-p1066任一满足即触发" not in entry["exception_rule"]
    assert "脱离p1060/p1063人群前提扁平化" in entry["forbidden_inversion"]


def test_source_qualifiers_are_not_promoted_or_retyped(config: dict) -> None:
    """黄疸病因限定与p1065基线增量必须保持原文的附着关系和值类型。"""
    p1057 = config["exception_semantics_by_source_ref"]["body.p1057"]
    assert "按原文位置随黄疸分支保留" in p1057["exception_rule"]
    assert "拆成独立OR分支" in p1057["forbidden_inversion"]
    p1065 = config["exception_semantics_by_source_ref"]["body.p1065"]
    assert "治疗后值相对基线值的增量阈值" in p1065["exception_rule"]
    assert "绝对值至少为1×ULN" in p1065["forbidden_inversion"]


def test_baseline_strata_never_conflated(config: dict) -> None:
    """基线正常（p1060-p1062）与基线异常（p1063-p1066）人群不得混同。"""
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "基线正常人群与p1063-p1066基线异常人群不得混同" in checks_blob
    assert "基线异常人群与p1060-p1062基线正常人群不得混同" in checks_blob
    p1060 = config["exception_semantics_by_source_ref"]["body.p1060"]
    p1063 = config["exception_semantics_by_source_ref"]["body.p1063"]
    assert "基线正常人群与p1063-p1066基线异常人群不得混同" in p1060["exception_rule"]
    assert "基线异常人群与p1060-p1062基线正常人群不得混同" in p1063["exception_rule"]
    assert "不得把基线正常分支套用p1064-p1066基线异常分支标准" in p1060["forbidden_inversion"]
    assert "不得把基线异常分支套用p1061/p1062基线正常分支标准" in p1063["forbidden_inversion"]


def test_lesser_of_two_never_lost(config: dict) -> None:
    """p1064/p1065 的'以较小者为准'必须保留，不得改为较大者或全部满足。"""
    p1064 = config["exception_semantics_by_source_ref"]["body.p1064"]
    p1065 = config["exception_semantics_by_source_ref"]["body.p1065"]
    assert "以较小者为准" in p1064["base_rule"]
    assert "以较小者为准" in p1065["base_rule"]
    for entry in (p1064, p1065):
        assert "不得把'以较小者为准'改为'以较大者为准'或'须全部满足'" in entry[
            "forbidden_inversion"
        ]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "以较小者为准" in checks_blob


def test_ratio_indicators_never_misattributed(config: dict) -> None:
    """p1058/p1062/p1066 的比值均为ALT或AST高值与ALP高值的比值。"""
    for ref in (
        "body.p1058",
        "body.p1062",
        "body.p1066",
    ):
            entry = config["exception_semantics_by_source_ref"][ref]
            assert "ALT或AST高值" in entry["preserve_keywords"]
            assert "ALP高值" in entry["preserve_keywords"]
            assert "GGT、总胆红素或其他指标" in entry["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "p1058/p1062/p1066的比值均为ALT或AST高值与ALP高值的比值" in checks_blob


def test_p1064_inner_conjunction_never_weakened(config: dict) -> None:
    """p1064 内层合取'且'不得弱化为OR，>8×ULN 与内层合取保持OR。"""
    excerpt = _owned_excerpt_by_ref(
        config=config, plan=_load_json(PLAN_PATH)
    )["body.p1064"]
    assert "ALT或AST> 2×基线值且> 3×ULN，或> 8×ULN（以较小者为准）" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1064"]
    assert "不得把内层合取'且'弱化为'或'" in entry["forbidden_inversion"]
    assert "不得把>8×ULN与内层合取改成AND" in entry["forbidden_inversion"]
    assert "且" in entry["preserve_keywords"]


# ---------------------------------------------------------------------------
# package 86 anti-absorption boundary
# ---------------------------------------------------------------------------


def test_package86_dili_flow_not_absorbed(config: dict) -> None:
    """第86包DILI复查、调查、潜在/确诊流程不得进入本包闭包。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG86_SPAN_REFS).isdisjoint(attached)
    assert set(PKG86_SPAN_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "DILI简要介绍、复查、调查、潜在/确诊Hy's law流程" in note
    assert "所有权不得转移" in note
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不引入第86包" in checks_blob


def test_prompt_excludes_package86_and_later_content() -> None:
    """第86包DILI复查/调查/确诊及更后包内容不得进入提示；第85包自身内容必须进入。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第85包自身内容（合法）
    assert "严重肝损伤与肝功能检查异常" in prompt_text
    assert "海氏定律" in prompt_text
    assert "以较小者为准" in prompt_text
    assert "获知事件后不超过24小时" in prompt_text
    # 第86包及更后包内容（禁止泄漏；"48 h"/"药物性肝损伤"/"DILI"/调查指标等）
    for leaked in (
        "药物性肝损伤",
        "DILI",
        "48 h",
        "白蛋白",
        "肌酸激酶",
        "谷氨酰转移酶",
        "GGT",
        "凝血酶原",
        "对乙酰氨基酚",
        "病因调查",
        "潜在",
        "确诊",
        "复查",
        "共同判断",
        "报告说明",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第85包提示: {leaked}"
    # 第84包与第86包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in PKG84_SPAN_REFS + PKG86_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第85包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第85包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_definition_anchors() -> None:
    """提示必须包含SAE/AE定义锚点与基线锚点，且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "严重不良事件" in prompt_text
    assert "符合下列标准任何一项的不良事件" in prompt_text
    assert "所有AE均需记录在eCRF中" in prompt_text
    assert "D1给药前结果作为基线值" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert by_ref[SAE_DEFINITION_REF]["role"] == "attached"
    assert by_ref[D1_PRE_DOSE_BASELINE_REF]["role"] == "attached"
    assert by_ref[PKG85_SAE_RECORD_REPORT_REF]["role"] == "owned"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package85(matrix: dict, plan: dict) -> None:
    pkg85 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg85["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第85包拥有来源为锚点"
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


def test_no_official_rule_anchors_package85_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg85 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_85_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg85["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第85包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package85_or_definition_spans(
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
    assert PACKAGE_85_ID in text
    assert PACKAGE_86_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "严重肝损伤与肝功能检查异常" in text
    assert "海氏定律" in text
    assert "无胆汁淤积或其他高胆红素血症的病因" in text
    assert "以较小者为准" in text
    assert "最恰当的诊断" in text
    assert "获知事件后不超过24小时" in text
    assert "基线值在正常范围" in text and "基线值> ULN" in text
    assert "8×ULN" in text
    assert "body.p1055" in text and "body.p1066" in text
    assert "body.p1067" in text and "body.p1073" in text
    assert "第84包" in text and "第85包" in text and "第86包" in text
    assert "第90" in text and "第92" in text
    assert "不得提前吞并" in text or "防吞并" in text
