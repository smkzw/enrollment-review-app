#!/usr/bin/env python3
"""Slice61bx model-free source-closure regressions.

Locks the D001 II package 86 DILI evaluation / potential-confirmed
stratification boundary (frozen plan package 86: 药物性肝损伤评估、
调查、潜在/确诊分层与报告流程, body.p1067-p1073) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 86 (1 structural heading + 6 semantic
  evaluation/investigation/reporting units); attached refs stay read-only
- structural unit (p1067) stays structural only; six semantic units keep
  post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- p1068 keeps the medical background and risk stratification: AST和/或ALT
  elevation usually precedes total bilirubin elevation, both elevated in the
  same sample, rare AST/ALT decline still counts as potential DILI, and
  potential cases are important medical events even before exclusion of
  other causes; 多数/通常/极少数 frequency strata never collapse to 全部
- p1069 keeps separate clinical judgment assessment of AST和/或ALT and
  total bilirubin elevations plus joint review with the sponsor whenever
  potential Hy's law is uncertain; joint review is not a diagnosis and not
  a system-only decision
- p1070 keeps the 48-hour return-to-site example boundary (尽快, 如...48 h内)
  for assessment including laboratory tests, detailed history and physical
  assessment; 48 h is never converted into a sponsor reporting deadline and
  the three-part assessment is never weakened to an optional single item
- p1071 keeps the investigation hierarchy: repeat AST/ALT/total bilirubin
  for suspected cases; other laboratory tests 应包括 the listed items;
  separate coagulation/anticoagulation samples, viral hepatitis, imaging and
  acetaminophen-related testing stay under 需要时/必要时 qualifiers (never
  upgraded to unconditional for all cases); detailed information collection
  is never reduced to alcohol history alone; GGT stays an investigation
  analyte and is never mixed into the previous package ALT/AST-vs-ALP ratio
- p1072 keeps the potential-case conjunction trigger chain: 尚未发现其他原因
  且 重复检查证实符合上述两个AST/ALT和总胆红素升高标准 才视为潜在DILI
  (Hy's law) 并报告为SAE; immediate sponsor report within no more than
  24 hours of becoming aware plus a written report explanation; a single
  abnormality, a single test, full exclusion of other causes, or the 48-hour
  return alone never substitutes the complete trigger chain
- p1073 keeps the potential-to-confirmed transition: only after receiving
  all reasonable investigation results and excluding other causes; exclusion
  of other causes is the condition for 潜在转确诊, never a prerequisite for
  the earlier p1068-p1072 assessment, repeat testing, or potential-case
  reporting
- 48-hour return assessment (p1070) and 24-hour sponsor reporting (p1072)
  stay strictly separated; potential DILI (p1072) and confirmed DILI (p1073)
  stay strictly separated
- package 85 (p1055-p1066) enters only as read-only ownership metadata for
  the p1072 cross-referenced "上述两个AST/ALT和总胆红素升高标准"
  (p1060-p1066 attached read-only; p1055-p1059 never attached and never in
  the prompt); package 87+ (p1074+ death/overdose/administration error,
  p1084+ severity, p1087+ causality, p1098+ SAE reporting timelines) is
  never absorbed
- official matrix keeps zero rows anchored in p1067-p1073 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no p1067-p1073 spans
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
    CONFIG_DIR / "representative_group_package86_dili_evaluation_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bx-package86-dili-evaluation-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE / "slice59n-prepare" / "d001-ii-package86-dili-evaluation-boundary"
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
PACKAGE_86_ORDINAL = 86
PACKAGE_86_ID = "pap-d27cb33cf06d737190efa6c7"
PACKAGE_85_ORDINAL = 85
PACKAGE_85_ID = "pap-be8085a9fd5705e64525e8e8"
PACKAGE_87_ORDINAL = 87

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1067, 1074)]

# 结构单元：DILI简要介绍标题，仅提供归属不独立形成控制点
STRUCTURAL_REFS = ["body.p1067"]
# 语义单元：DILI评估、调查、潜在/确诊分层与报告流程，保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1068, 1074)]

# 只读闭包：第85包"上述两个AST/ALT和总胆红素升高标准"（p1060-p1066，7）、
# SAE定义与严重性总纲（2）、AE收集期与全量记录义务（2）、流程锚点（1）
PKG85_STANDARDS_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1060, 1067)]
SAE_DEF_ATTACHED_REFS = ["body.p996", "body.p997"]
RECORDING_ATTACHED_REFS = ["body.p1022", "body.p1024"]
FLOW_ANCHOR_REFS = ["body.p340"]
ATTACHED_REFS = (
    PKG85_STANDARDS_ATTACHED_REFS
    + SAE_DEF_ATTACHED_REFS
    + RECORDING_ATTACHED_REFS
    + FLOW_ANCHOR_REFS
)

# 相邻包所有权元数据：第84包（p1043-p1054）、第85包（p1055-p1066）、
# 第87包（p1074-p1083）、第88包（p1084-p1086）均不得被本包拥有或处置
PKG84_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1043, 1055)]
PKG85_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1055, 1067)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]

# 各语义单元的合取/OR结构、时间边界、潜在/确诊分层、调查层次与限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1068": {
        "base_rule": "在大多数药物性肝损伤病例中，AST和/或ALT的升高会早于总胆红素升高（> 2×ULN）几天或几周，后者升高通常发生在AST和/或ALT仍然高于3×ULN时（即，在同一样本中AST和/或ALT与总胆红素值均表现升高）。在极少数情况下，当检测到总胆红素升高时，AST/ALT值可能已经下降。这种事件仍然被认为是潜在的药物性肝损伤。潜在的药物性肝损伤病例（甚至在所有其他可能的肝损伤原因被排除之前），应该始终被视为重要的医学事件。",
        "exception_rule": "DILI医学背景与风险分层：多数病例中AST和/或ALT升高可早于总胆红素升高；总胆红素升高时AST和/或ALT通常仍高于3×ULN且两类数值在同一样本中；少数情况下AST/ALT已下降仍可视为潜在DILI；潜在病例在排除其他病因前仍是重要医学事件；不得把'尚未排除其他原因'误作不采取行动的理由",
        "preserve_keywords": ["AST和/或ALT", "3×ULN", "同一样本", "极少数情况下", "潜在的药物性肝损伤", "重要的医学事件"],
    },
    "body.p1069": {
        "base_rule": "AST和/或ALT和总胆红素的上升应根据临床判断单独评估，任何不确定是否为潜在的Hy's定律病例，均应与申办者一起审查。",
        "exception_rule": "AST和/或ALT与总胆红素上升按临床判断单独评估；不确定是否为潜在Hy's定律病例时与申办者共同审查；共同审查不是已确诊，也不是仅由系统自行判定",
        "preserve_keywords": ["临床判断", "单独评估", "潜在的Hy's定律", "与申办者一起审查"],
    },
    "body.p1070": {
        "base_rule": "参与者应尽快（如，获知异常结果后的48 h内）返回研究中心进行评估，评估应包括实验室检查、详细的病史和身体评估。",
        "exception_rule": "48小时是获知异常结果后尽快返院评估的示例时间边界；返院评估同时包括实验室检查、详细病史和身体评估三部分；48小时是返院评估时限，不是申办者报告期限",
        "preserve_keywords": ["尽快", "48 h内", "返回研究中心进行评估", "实验室检查", "详细的病史", "身体评估"],
    },
    "body.p1071": {
        "base_rule": "除了对疑似Hy's定律病例重复检测AST、ALT和总胆红素外，其他实验室检查应包括白蛋白、肌酸激酶（CK）、直接和间接胆红素、谷氨酰转移酶（GGT）、凝血酶原时间（PT）/国际标准化比值（INR）、总胆汁酸和碱性磷酸酶。需要时，还应考虑各抽取一管单独的凝血和抗凝血样本用于进一步的检查以确定病因。",
        "exception_rule": "调查层次：疑似病例重复检测AST、ALT和总胆红素；其他实验室检查'应包括'原文列举项目；单独凝血/抗凝血样本、病毒性肝炎、影像及对乙酰氨基酚相关检测受'需要时/必要时'限定，不能升格为所有病例无条件必做；详细相关信息收集不得缩成单一饮酒史；GGT是调查指标，不得混入第85包ALT/AST与ALP的比值判断",
        "preserve_keywords": ["重复检测AST、ALT和总胆红素", "应包括", "白蛋白", "肌酸激酶", "GGT", "凝血酶原时间", "需要时", "必要时", "详细的相关信息", "对乙酰氨基酚"],
    },
    "body.p1072": {
        "base_rule": "如果尚未发现导致肝功能检查异常的其他原因，重复检查证实符合上述两个AST/ALT和总胆红素升高标准的病例，应视为潜在的药物性肝损伤（Hy's定律）病例，并报告为SAE。应立即将此病例报告给申办者（即，在获知事件后不超过24小时），同时提交给申办者了解事件的报告说明。",
        "exception_rule": "潜在病例触发是合取链：尚未发现其他原因 且 重复检查证实符合上述两个AST/ALT和总胆红素升高标准 才视为潜在DILI（Hy's law）并报告为SAE；随后立即报告申办者，获知事件后不超过24小时，同时提交报告说明",
        "preserve_keywords": ["尚未发现", "其他原因", "重复检查证实", "上述两个AST/ALT和总胆红素升高标准", "潜在的药物性肝损伤", "Hy's定律", "报告为SAE", "不超过24小时", "报告说明"],
    },
    "body.p1073": {
        "base_rule": "一个潜在的药物性肝损伤（Hy's定律）病例只有在收到所有合理的调查结果并排除了其他病因后才会成为确诊病例。",
        "exception_rule": "潜在转确诊条件：收到所有合理调查结果并排除其他病因；排除其他病因是'潜在转确诊'的条件，不是p1068-p1072早期评估、复查或潜在病例报告的前置条件",
        "preserve_keywords": ["所有合理的调查结果", "排除了其他病因", "确诊病例"],
    },
}

# 交叉验证锚点（只读闭包）
PKG86_HEADING_REF = "body.p1067"
PKG86_BACKGROUND_REF = "body.p1068"
PKG86_ASSESSMENT_REF = "body.p1069"
PKG86_48H_RETURN_REF = "body.p1070"
PKG86_INVESTIGATION_REF = "body.p1071"
PKG86_POTENTIAL_TRIGGER_REF = "body.p1072"
PKG86_CONFIRMED_REF = "body.p1073"
PKG85_CRITERION_LEAD_NORMAL_REF = "body.p1060"
PKG85_CRITERION_LEAD_ABNORMAL_REF = "body.p1063"
SAE_DEFINITION_REF = "body.p996"
SAE_OR_LEAD_REF = "body.p997"
RECORDING_OBLIGATION_REF = "body.p1024"
COLLECTION_WINDOW_REF = "body.p1022"
AE_RECORD_START_REF = "body.p340"

# 结构级关键片段：编码时间边界、合取触发链、潜在/确诊分层与限定条件的逐字片段，
# 反例改写必须破坏至少一个
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1068": [
        "AST和/或ALT的升高会早于总胆红素升高",
        "同一样本中AST和/或ALT与总胆红素值均表现升高",
        "极少数情况下，当检测到总胆红素升高时，AST/ALT值可能已经下降",
        "甚至在所有其他可能的肝损伤原因被排除之前",
        "被视为重要的医学事件",
    ],
    "body.p1069": [
        "根据临床判断单独评估",
        "任何不确定是否为潜在的Hy's定律病例",
        "均应与申办者一起审查",
    ],
    "body.p1070": [
        "参与者应尽快（如，获知异常结果后的48 h内）返回研究中心进行评估",
        "评估应包括实验室检查、详细的病史和身体评估",
    ],
    "body.p1071": [
        "除了对疑似Hy's定律病例重复检测AST、ALT和总胆红素外",
        "其他实验室检查应包括白蛋白、肌酸激酶（CK）、直接和间接胆红素、谷氨酰转移酶（GGT）、凝血酶原时间（PT）/国际标准化比值（INR）、总胆汁酸和碱性磷酸酶",
        "需要时，还应考虑各抽取一管单独的凝血和抗凝血样本",
        "必要时，进一步检查急性甲型、乙型、丙型、丁型和戊型肝炎感染和肝脏影像（如，胆道）",
    ],
    "body.p1072": [
        "如果尚未发现导致肝功能检查异常的其他原因",
        "重复检查证实符合上述两个AST/ALT和总胆红素升高标准",
        "应视为潜在的药物性肝损伤（Hy's定律）病例，并报告为SAE",
        "在获知事件后不超过24小时",
        "同时提交给申办者了解事件的报告说明",
    ],
    "body.p1073": [
        "只有在收到所有合理的调查结果并排除了其他病因后才会成为确诊病例",
    ],
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
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _missing_exception_keywords(text: str, entry: dict) -> list[str]:
    """确定性合取/例外门禁：来源文本必须同时保留基础规则与例外条款关键词。"""
    return [kw for kw in entry["preserve_keywords"] if kw not in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码时间边界/触发链/分层与限定的逐字片段。"""
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
    assert config["group_id"] == "d001-ii-package86-dili-evaluation-boundary"
    assert config["task_id"] == "phase5-slice61bx-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 7

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(STRUCTURAL_REFS), "DILI简要介绍标题必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第86包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第86包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 语义单元保持治疗后DILI评估/调查/报告处置；结构单元不进入处置映射
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

    # 时间边界/触发链/分层语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(EXCEPTION_SEMANTICS_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg86 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL
    )
    owned_86 = {u["source_ref"] for u in pkg86["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_86), "attached refs must not be owned by package 86"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 12


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PKG85_STANDARDS_ATTACHED_REFS:
        assert owners.get(ref) == [85], f"{ref} 必须保持归第85包"
    for ref in SAE_DEF_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    for ref in RECORDING_ATTACHED_REFS:
        assert owners.get(ref) == [80], f"{ref} 必须保持归第80包"
    assert owners.get("body.p340") is None or "body.p340" not in owners, (
        "body.p340 必须保持流程注记上下文来源"
    )


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第85包拥有p1055-p1066（12），第86包拥有p1067-p1073（7），
    第87包拥有p1074-p1083（10），第88包拥有p1084-p1086（3）。"""
    pkg85 = next(p for p in plan["packages"] if p["package_ordinal"] == 85)
    pkg86 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL)
    pkg87 = next(p for p in plan["packages"] if p["package_ordinal"] == 87)
    pkg88 = next(p for p in plan["packages"] if p["package_ordinal"] == 88)
    owned_85 = {u["source_ref"] for u in pkg85["owned_units"]}
    owned_86 = {u["source_ref"] for u in pkg86["owned_units"]}
    owned_87 = {u["source_ref"] for u in pkg87["owned_units"]}
    owned_88 = {u["source_ref"] for u in pkg88["owned_units"]}
    assert set(PKG85_SPAN_REFS) <= owned_85 and len(owned_85) == 12
    assert set(OWNED_REFS) <= owned_86 and len(owned_86) == 7
    assert set(PKG87_SPAN_REFS) <= owned_87 and len(owned_87) == 10
    assert set(PKG88_SPAN_REFS) <= owned_88 and len(owned_88) == 3


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_86(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_86_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1067"] == (
        "药物性肝损伤（Drug-Induced Liver Injury，DILI）的简要介绍"
    )
    assert excerpts["body.p1068"] == (
        "药物性肝损伤是指由各类化学药品、生物制品、传统中药及其代谢产物乃至辅料"
        "等所诱发的肝脏损伤。在大多数药物性肝损伤病例中，AST和/或ALT的升高会早于"
        "总胆红素升高（> 2×ULN）几天或几周，后者升高通常发生在AST和/或ALT仍然高于"
        "3×ULN时（即，在同一样本中AST和/或ALT与总胆红素值均表现升高）。在极少数情况"
        "下，当检测到总胆红素升高时，AST/ALT值可能已经下降。这种事件仍然被认为是潜在"
        "的药物性肝损伤。潜在的药物性肝损伤病例（甚至在所有其他可能的肝损伤原因被排除"
        "之前），应该始终被视为重要的医学事件。"
    )
    assert excerpts["body.p1069"] == (
        "AST和/或ALT和总胆红素的上升应根据临床判断单独评估，任何不确定是否为潜在的"
        "Hy's定律病例，均应与申办者一起审查。"
    )
    assert excerpts["body.p1070"] == (
        "参与者应尽快（如，获知异常结果后的48 h内）返回研究中心进行评估，评估应包括"
        "实验室检查、详细的病史和身体评估。"
    )
    assert excerpts["body.p1071"] == (
        "除了对疑似Hy's定律病例重复检测AST、ALT和总胆红素外，其他实验室检查应包括"
        "白蛋白、肌酸激酶（CK）、直接和间接胆红素、谷氨酰转移酶（GGT）、凝血酶原时间"
        "（PT）/国际标准化比值（INR）、总胆汁酸和碱性磷酸酶。需要时，还应考虑各抽取"
        "一管单独的凝血和抗凝血样本用于进一步的检查以确定病因。此外，应收集详细的相关"
        "信息，如酒精、对乙酰氨基酚/扑热息痛（单方或复方产品）、娱乐性毒品、补充剂（草"
        "药）的使用和消费，家族史、性史、旅行史、与黄疸患者接触史、手术、输血、肝脏或"
        "过敏性疾病史以及可能的化学物质职业暴露。必要时，进一步检查急性甲型、乙型、丙"
        "型、丁型和戊型肝炎感染和肝脏影像（如，胆道），或收集血清样本以检测对乙酰氨基酚"
        "/扑热息痛和/或蛋白加合物的水平。"
    )
    assert excerpts["body.p1072"] == (
        "如果尚未发现导致肝功能检查异常的其他原因，重复检查证实符合上述两个AST/ALT"
        "和总胆红素升高标准的病例，应视为潜在的药物性肝损伤（Hy's定律）病例，并报告"
        "为SAE。应立即将此病例报告给申办者（即，在获知事件后不超过24小时），同时提交"
        "给申办者了解事件的报告说明。"
    )
    assert excerpts["body.p1073"] == (
        "一个潜在的药物性肝损伤（Hy's定律）病例只有在收到所有合理的调查结果并排除了"
        "其他病因后才会成为确诊病例。"
    )


# ---------------------------------------------------------------------------
# structural-only unit and semantic rows
# ---------------------------------------------------------------------------


def test_structural_unit_does_not_form_control_point(config: dict, plan: dict) -> None:
    """DILI简要介绍标题（p1067）不形成控制点；六个语义单元保持处置。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref in STRUCTURAL_REFS:
        assert ref in config["structural_only_source_refs"]
        assert ref in config["forbidden_candidate_source_refs"]
        assert ref not in config["expected_disposition_by_source_ref"]
    assert excerpts["body.p1067"] == (
        "药物性肝损伤（Drug-Induced Liver Injury，DILI）的简要介绍"
    )
    for ref in SEMANTIC_OWNED_REFS:
        assert ref not in config["structural_only_source_refs"]
        assert config["expected_disposition_by_source_ref"][ref] == "post_treatment_execution"
    assert set(config["expected_disposition_by_source_ref"]) == set(SEMANTIC_OWNED_REFS)


# ---------------------------------------------------------------------------
# later-package read-only ownership metadata: p1043-p1054 -> 84, p1055-p1066 -> 85,
# p1067-p1073 -> 86, p1074-p1083 -> 87, p1084-p1086 -> 88
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """第84/85/87/88包来源可保留所有权元数据，但不得进入本包闭包或由本包发射。"""
    boundary = config["later_package_boundary"]
    expected_boundary = set(
        PKG84_SPAN_REFS + PKG85_SPAN_REFS + OWNED_REFS + PKG87_SPAN_REFS + PKG88_SPAN_REFS
    )
    assert set(boundary["expected_owners_by_span"]) == expected_boundary
    for ref in OWNED_REFS:
        assert boundary["expected_owners_by_span"][ref] == 86
    for ref in PKG84_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 84
    for ref in PKG85_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 85
    for ref in PKG87_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 87
    for ref in PKG88_SPAN_REFS:
        assert boundary["expected_owners_by_span"][ref] == 88
    neighbor = set(PKG84_SPAN_REFS + PKG85_SPAN_REFS + PKG87_SPAN_REFS + PKG88_SPAN_REFS)
    assert neighbor.isdisjoint(set(config["owned_source_refs"])), (
        "第84/85/87/88包来源不得被第86包拥有"
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
        assert expected_ordinal != PACKAGE_86_ORDINAL or ref in OWNED_REFS, (
            f"{ref} 不得归第86包之外"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第85包",
        "第86包",
        "第87包",
        "第88包",
        "吞并",
        "所有权不得转移",
        "第90",
        "第92",
        "24小时",
        "p1072",
        "上述两个AST/ALT和总胆红素升高标准",
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
    assert "同一样本" in by_ref[PKG86_BACKGROUND_REF].excerpt
    assert "极少数情况下" in by_ref[PKG86_BACKGROUND_REF].excerpt
    assert "与申办者一起审查" in by_ref[PKG86_ASSESSMENT_REF].excerpt
    assert "48 h内" in by_ref[PKG86_48H_RETURN_REF].excerpt
    assert "详细的病史" in by_ref[PKG86_48H_RETURN_REF].excerpt
    assert "重复检测AST、ALT和总胆红素" in by_ref[PKG86_INVESTIGATION_REF].excerpt
    assert "需要时" in by_ref[PKG86_INVESTIGATION_REF].excerpt
    assert "必要时" in by_ref[PKG86_INVESTIGATION_REF].excerpt
    assert "上述两个AST/ALT和总胆红素升高标准" in by_ref[PKG86_POTENTIAL_TRIGGER_REF].excerpt
    assert "不超过24小时" in by_ref[PKG86_POTENTIAL_TRIGGER_REF].excerpt
    assert "报告说明" in by_ref[PKG86_POTENTIAL_TRIGGER_REF].excerpt
    assert "排除了其他病因" in by_ref[PKG86_CONFIRMED_REF].excerpt

    # 只读闭包关键片段（第85包两个标准 + SAE定义/记录锚点）
    assert "基线值在正常范围的参与者" in by_ref[PKG85_CRITERION_LEAD_NORMAL_REF].excerpt
    assert "基线值> ULN的参与者" in by_ref[PKG85_CRITERION_LEAD_ABNORMAL_REF].excerpt
    assert "以较小者为准" in by_ref["body.p1064"].excerpt
    assert "死亡、危及生命" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "符合下列标准任何一项的不良事件" in by_ref[SAE_OR_LEAD_REF].excerpt
    assert "首次服用试验用药品后至最后一次安全性随访" in by_ref[COLLECTION_WINDOW_REF].excerpt
    assert "所有AE均需记录在eCRF中" in by_ref[RECORDING_OBLIGATION_REF].excerpt
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF].excerpt


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
    for ref in PKG84_SPAN_REFS + PKG87_SPAN_REFS + PKG88_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"
    # p85 前接标准（p1060-p1066）是合法只读附加，但 p1055-p1059 不得进入
    for ref in [f"body.p{ordinal}" for ordinal in range(1055, 1060)]:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 7
    assert summary["attached_count"] == 12
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

    # 越界候选（把DILI评估/调查升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1071"]],
                "title": "筛选时核对DILI调查安排，未确认者按证据缺口判定入排不通过",
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
    """确定性门禁必须拒绝把DILI评估/调查/报告改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1067": [
            "筛选时核对DILI简要介绍安排，未完成者不得入组",
        ],
        "body.p1068": [
            "筛选时评估DILI医学背景掌握情况，证据不足者按排除标准判定不通过",
        ],
        "body.p1069": [
            "筛选时核对与申办者共同审查安排，未确认者入排不通过",
        ],
        "body.p1070": [
            "筛选时核对48小时返院评估安排，未完成者证据缺口不得入组",
        ],
        "body.p1071": [
            "筛选时核对DILI调查项目安排，未完成者不得入组",
        ],
        "body.p1072": [
            "筛选时核对DILI潜在病例报告安排，未确认者入排不通过",
        ],
        "body.p1073": [
            "筛选时核对DILI确诊判定安排，未确认者证据缺口不得入组",
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
    """时间边界、触发链、分层与调查限定关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、条件或报告路径的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1068": "药物性肝损伤病例中AST和/或ALT的升高会早于总胆红素升高。",
        "body.p1069": "AST和/或ALT和总胆红素的上升应根据临床判断评估。",
        "body.p1070": "参与者应尽快返回研究中心进行评估。",
        "body.p1071": "疑似病例重复检测AST、ALT和总胆红素，其他实验室检查应包括部分检查项目。",
        "body.p1072": "重复检查证实符合上述两个AST/ALT和总胆红素升高标准的病例应视为潜在DILI并报告为SAE。",
        "body.p1073": "潜在DILI病例在排除其他病因后成为确诊。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# AND/OR, time-boundary, stratification structure gates
# ---------------------------------------------------------------------------


def test_structural_fragments_present_in_owned_sources(plan: dict, config: dict) -> None:
    """编码时间边界/触发链/分层与限定的逐字片段必须完整保留在来源摘录中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    for ref, fragments in STRUCTURAL_FRAGMENTS_BY_REF.items():
        for fragment in fragments:
            assert fragment in excerpts[ref], f"{ref} 丢失结构级片段: {fragment}"


def test_and_or_inversion_counterexamples_detected(config: dict) -> None:
    """时间边界反转、触发链弱化、分层混同、调查必做/按需错位反例必须被确定性拦截。"""
    inverted = {
        "body.p1068": [
            "在全部药物性肝损伤病例中，AST和/或ALT的升高会早于总胆红素升高。",
            "总胆红素升高时AST和/或ALT总是仍高于3×ULN。",
            "当检测到总胆红素升高时，AST/ALT值可能已经下降，但不再视为潜在DILI。",
            "潜在的药物性肝损伤病例在所有其他可能的肝损伤原因被排除之后才被视为重要的医学事件。",
        ],
        "body.p1069": [
            "AST和/或ALT和总胆红素的上升应根据临床判断合并评估。",
            "任何不确定是否为潜在的Hy's定律病例，均应由系统自行判定。",
            "任何不确定是否为潜在的Hy's定律病例，均按已确诊处理。",
        ],
        "body.p1070": [
            "参与者应在获知异常结果后的48 h内向申办者提交报告。",
            "参与者应尽快（如，获知异常结果后的48 h内）返回研究中心进行评估，评估应包括实验室检查。",
            "参与者应在获知异常结果后的48 h内返回研究中心完成全部评估和报告。",
        ],
        "body.p1071": [
            "所有病例均应重复检测AST、ALT和总胆红素，其他实验室检查应包括全部列举项目，并各抽取一管单独的凝血和抗凝血样本。",
            "疑似病例重复检测AST、ALT和总胆红素，其他实验室检查应包括白蛋白。",
            "应收集饮酒史。",
            "ALT或AST高值与GGT高值的比值≥5。",
            "必要时，应检查急性病毒性肝炎感染和肝脏影像。",
        ],
        "body.p1072": [
            "重复检查证实符合上述两个AST/ALT和总胆红素升高标准的病例，应视为潜在DILI并报告为SAE。",
            "尚未发现导致肝功能检查异常的其他原因，或重复检查证实符合上述两个AST/ALT和总胆红素升高标准的病例，应视为潜在DILI并报告为SAE。",
            "已排除所有其他可能病因的病例，应视为潜在的药物性肝损伤（Hy's定律）病例，并报告为SAE。",
            "参与者返院完成48小时评估后，应视为潜在的药物性肝损伤（Hy's定律）病例，并报告为SAE。",
            "应立即将此病例报告给申办者（即，在获知事件后不超过48小时），同时提交给申办者了解事件的报告说明。",
            "应尽快将此病例报告给申办者，同时提交给申办者了解事件的报告说明。",
            "应立即将此病例报告给申办者（即，在获知事件后不超过24小时）。",
        ],
        "body.p1073": [
            "潜在DILI病例只有排除其他病因后才成为确诊，无需收到所有合理的调查结果。",
            "潜在DILI病例在收到部分合理的调查结果并排除其他病因后即成为确诊。",
            "在排除其他病因之前，潜在DILI病例不得进行复查或报告。",
        ],
    }
    for ref, counterexamples in inverted.items():
        for text in counterexamples:
            missing = _missing_structural_fragments(text, ref)
            assert missing, f"{ref} 时间边界/触发链/分层反例未被结构片段门禁拦截: {text}"


def test_48h_return_and_24h_report_never_conflated(config: dict) -> None:
    """48小时返院评估（p1070）与24小时申办者报告（p1072）必须严格区分。"""
    p1070 = config["exception_semantics_by_source_ref"]["body.p1070"]
    p1072 = config["exception_semantics_by_source_ref"]["body.p1072"]
    assert "48小时是获知异常结果后尽快返院评估的示例时间边界" in p1070["exception_rule"]
    assert "不是申办者报告期限" in p1070["exception_rule"]
    assert "不得把48小时改成申办者报告期限或24小时报告时限" in p1070["forbidden_inversion"]
    assert "获知事件后不超过24小时" in p1072["exception_rule"]
    assert "不得把24小时改为48小时或其他时限或'尽快报告'" in p1072["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "48小时是获知异常结果后尽快返院评估的示例时间边界" in checks_blob
    assert "24小时是潜在DILI（Hy's law）病例获知事件后立即报告申办者的时限" in checks_blob


def test_potential_and_confirmed_never_conflated(config: dict) -> None:
    """潜在DILI（p1072）与确诊DILI（p1073）必须严格区分；病因排除错绑必须拦截。"""
    p1072 = config["exception_semantics_by_source_ref"]["body.p1072"]
    p1073 = config["exception_semantics_by_source_ref"]["body.p1073"]
    assert "才视为潜在DILI（Hy's law）并报告为SAE" in p1072["exception_rule"]
    assert "不得把潜在病例直接写成确诊" in p1072["forbidden_inversion"]
    assert "排除其他病因是'潜在转确诊'的条件" in p1073["exception_rule"]
    assert "不是p1068-p1072早期评估、复查或潜在病例报告的前置条件" in p1073[
        "exception_rule"
    ]
    assert "不得把排除其他病因前置于p1068-p1072早期评估、复查或潜在病例报告" in p1073[
        "forbidden_inversion"
    ]
    assert "不得把'所有合理的调查结果'删成部分调查或'任一调查'" in p1073[
        "forbidden_inversion"
    ]


def test_single_abnormality_or_single_test_never_substitutes_trigger_chain(
    config: dict,
) -> None:
    """单次异常或一次检查不得直接定性为潜在DILI。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1072"]
    assert "任一单独异常、一次检查、完成全部病因排除或48小时返院任一项替代完整触发链" in entry[
        "forbidden_inversion"
    ]
    assert "合取链弱化为任一条件即触发" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1072"])
    assert "不得把任一单独异常、一次检查、完成全部病因排除或48小时返院任一项替代完整触发链" in checks


def test_investigation_hierarchy_qualifiers_preserved(config: dict) -> None:
    """调查必做/按需层次：'应包括'列举项目与'需要时/必要时'限定不得错位。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1071"]
    assert "其他实验室检查'应包括'原文列举项目" in entry["exception_rule"]
    assert "受'需要时/必要时'限定，不能升格为所有病例无条件必做" in entry["exception_rule"]
    assert "不得把'应包括'列举项目删减或缩水" in entry["forbidden_inversion"]
    assert "不得把'需要时/必要时'限定项目升格为所有病例无条件必做" in entry["forbidden_inversion"]
    assert "不得把详细相关信息收集缩成单一饮酒史" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1071"])
    assert "详细相关信息收集不得缩成单一饮酒史" in checks


def test_ggt_never_mixed_into_previous_package_ratio(config: dict) -> None:
    """GGT是第86包调查指标，不得混入第85包ALT/AST与ALP的比值判断。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1071"]
    assert "GGT是调查指标，不得混入第85包ALT/AST与ALP的比值判断" in entry["exception_rule"]
    assert "不得把GGT混入第85包ALT/AST与ALP的比值判断" in entry["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "GGT是调查指标，不得混入第85包ALT/AST与ALP的比值判断" in checks_blob


def test_p1072_keeps_report_as_sae_and_report_explanation(config: dict) -> None:
    """'报告为SAE'、24小时立即报告与'同时提交报告说明'必须完整保留。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1072"]
    assert "并报告为SAE" in entry["exception_rule"]
    assert "同时提交报告说明" in entry["exception_rule"]
    assert "不得把'报告为SAE'删除" in entry["forbidden_inversion"]
    assert "不得删除'同时提交报告说明'" in entry["forbidden_inversion"]


def test_sponsor_joint_review_is_not_diagnosis(config: dict) -> None:
    """p1069共同审查不得改写为已确诊或仅由系统自行判定。"""
    entry = config["exception_semantics_by_source_ref"]["body.p1069"]
    assert "共同审查不是已确诊，也不是仅由系统自行判定" in entry["exception_rule"]
    assert "不得把共同审查改写成已确诊或仅由系统自行判定" in entry["forbidden_inversion"]
    assert "不得把'与申办者一起审查'删去或弱化为可选" in entry["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1069"])
    assert "共同审查不是已确诊" in checks


# ---------------------------------------------------------------------------
# package 85 read-only cross-reference and package 87+ anti-absorption
# ---------------------------------------------------------------------------


def test_package85_criteria_attached_read_only_not_reowned(config: dict) -> None:
    """第85包'上述两个AST/ALT和总胆红素升高标准'只读附加，不得被本包重新拥有。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG85_STANDARDS_ATTACHED_REFS) <= attached
    assert set(PKG85_SPAN_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "仅按p1072'上述两个AST/ALT和总胆红素升高标准'明确交叉引用提供p1060-p1066必要前接标准" in note
    assert "所有权不得转移" in note
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "所有权仍归第85包" in checks_blob


def test_p1072_cross_reference_context_is_not_a_unique_binding(config: dict) -> None:
    """完整装入前接分层只为保留语境，不能臆定原文已唯一绑定两个子条款。"""
    attached = set(config["attached_source_refs"])
    assert set(PKG85_STANDARDS_ATTACHED_REFS) <= attached
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1072"])
    assert "没有唯一指向两个具体source_ref" in checks
    assert "不代表已经确定唯一绑定" in checks
    inversion = config["exception_semantics_by_source_ref"]["body.p1072"][
        "forbidden_inversion"
    ]
    assert "不得擅自把'上述两个标准'绑定到任意两个具体子条款" in inversion
    assert "不得把p1060-p1066扁平化为任一满足" in inversion


def test_package85_lead_not_absorbed(config: dict) -> None:
    """p1055-p1059（严重肝损伤指征与SAE记录/立即报告总纲）不得进入本包闭包。"""
    p85_lead = [f"body.p{ordinal}" for ordinal in range(1055, 1060)]
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(p85_lead).isdisjoint(attached)
    assert set(p85_lead).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "本包不重新拥有严重肝损伤阈值或通用SAE记录义务" in note
    assert "p1055-p1059不进入本包提示" in note


def test_package87_and_later_not_absorbed(config: dict) -> None:
    """第87包死亡/药物过量/给药错误及更后包流程不得进入本包闭包。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    assert set(PKG87_SPAN_REFS).isdisjoint(attached)
    assert set(PKG87_SPAN_REFS).isdisjoint(owned)
    assert set(PKG88_SPAN_REFS).isdisjoint(attached)
    assert set(PKG88_SPAN_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "第87包死亡/药物过量/给药错误记录规则" in note
    assert "本包不提前吞并或处置" in note


def test_prompt_excludes_package85_lead_and_package87_plus_content() -> None:
    """第85包p1055-p1059与第87包及更后包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第85包前接标准（合法只读附加）
    assert "ALT或AST> 3×ULN合并总胆红素> 2×ULN" in prompt_text
    assert "以较小者为准" in prompt_text
    assert "基线值在正常范围的参与者" in prompt_text
    assert "基线值> ULN的参与者" in prompt_text
    # 第85包p1055-p1059内容（禁止泄漏；"严重肝损伤与肝功能检查异常"是共享章节
    # 标题路径，随拥有/附加行进入提示属合法元数据；p1062/p1066 的比值文本是
    # 只读附加的p85标准本身，属合法前接语境）
    for leaked in (
        "海氏定律",
        "无胆汁淤积或其他高胆红素血症的病因",
        "最恰当的诊断",
        "作为SAE在eCRF不良事件上记录",
        "研究者必须将以下任一肝功能检查异常",
    ):
        assert leaked not in prompt_text, f"第85包p1055-p1059内容泄漏进第86包提示: {leaked}"
    # 第87包及更后包内容（禁止泄漏；p1071自身拥有的调查指标文本属合法）
    for leaked in (
        "死亡应被视为事件的结果",
        "药物过量",
        "给药错误",
        "CTCAE",
        "严重程度评估",
        "因果关系",
        "表 8 不良事件严重程度分级",
    ):
        assert leaked not in prompt_text, f"第87包及更后包内容泄漏进第86包提示: {leaked}"
    # 第84/85/87/88包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in PKG84_SPAN_REFS + PKG87_SPAN_REFS + PKG88_SPAN_REFS:
        assert ref not in by_ref, f"{ref} 不得进入第86包准备证据"
    for ref in [f"body.p{ordinal}" for ordinal in range(1055, 1060)]:
        assert ref not in by_ref, f"{ref} 不得进入第86包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第86包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(config=config, plan=_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_definition_anchors_and_p85_standards() -> None:
    """提示必须包含SAE定义锚点与第85包前接标准，且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "严重不良事件" in prompt_text
    assert "符合下列标准任何一项的不良事件" in prompt_text
    assert "D1启动给药后开始记录" in prompt_text
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert by_ref[SAE_DEFINITION_REF]["role"] == "attached"
    assert by_ref[PKG85_CRITERION_LEAD_NORMAL_REF]["role"] == "attached"
    assert by_ref[PKG85_CRITERION_LEAD_ABNORMAL_REF]["role"] == "attached"
    assert by_ref[PKG86_POTENTIAL_TRIGGER_REF]["role"] == "owned"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package86(matrix: dict, plan: dict) -> None:
    pkg86 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg86["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第86包拥有来源为锚点"
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


def test_no_official_rule_anchors_package86_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg86 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_86_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg86["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第86包拥有来源为锚点"
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


def test_no_procedure_node_sourced_from_package86_or_definition_spans(
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
    assert PACKAGE_86_ID in text
    assert PACKAGE_85_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "药物性肝损伤" in text
    assert "48 h内" in text
    assert "24小时" in text
    assert "上述两个AST/ALT和总胆红素升高标准" in text
    assert "排除了其他病因" in text
    assert "以较小者为准" in text
    assert "body.p1067" in text and "body.p1073" in text
    assert "body.p1074" in text and "body.p1083" in text
    assert "第85包" in text and "第86包" in text and "第87包" in text
    assert "第90" in text and "第92" in text
    assert "不得提前吞并" in text or "防吞并" in text
