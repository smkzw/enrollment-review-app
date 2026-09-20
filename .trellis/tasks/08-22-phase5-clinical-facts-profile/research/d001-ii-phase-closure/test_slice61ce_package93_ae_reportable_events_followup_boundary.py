#!/usr/bin/env python3
"""Slice61ce model-free source-closure regressions.

Locks the D001 II package 93 AE reportable events and new important information
follow-up boundary (frozen plan package 93: 应报告的事件类型与新重要信息随访流程,
body.p1102-p1112) to its authoritative sources before any semantic replay
decision:

- config contract and role partition: 11 owned refs body.p1102-p1112
  (p1102 reportable events title structural only, p1103 first event lead paragraph
  post_treatment_execution, p1104 death event list_item, p1105 SAE list_item,
  p1106 pregnancy event list_item, p1107 new important info lead paragraph
  post_treatment_execution, p1108 sign/symptom/diagnosis change list_item,
  p1109 new diagnostic exam result list_item, p1110 causality change list_item,
  p1111 outcome change including recovery list_item, p1112 other clinical course
  description list_item); attached refs stay strictly empty (0)
- two structural lead relationships: p1103 -> p1104-p1106 (first event report
  obligation: investigator to sponsor within 24h inclusive, regardless of
  relationship to investigational drug); p1107 -> p1108-p1112 (new important info
  follow-up obligation: immediate and within 24h after awareness of new info)
- two reporting obligations separated: trigger objects, awareness clock anchors,
  and lists are distinct; never compressed into a single vague rule
- three reportable events parallel & independent: death (p1104), SAE (p1105),
  pregnancy (p1106) are three parallel event types; never omitted, merged to SAE,
  or conditioned
- pregnancy unconditioned: pregnancy event itself is an independent reportable
  event type; no requirement that it must be an AE, SAE, or drug-related
- causality independence: "regardless of relationship to investigational drug"
  covers all three event types (p1104-p1106)
- 24-hour limit strictly bounded: never generalized to all AE, TEAE, laboratory
  abnormalities, or general safety information
- "Immediately" and "within 24h (inclusive)" dual attributes preserved: never
  deleted, never weakened to unordered follow-up, never distorted to 0-second
  instant completion denying 24h buffer, never stripping "(含)" inclusive boundary
- five new important information types complete: sign/symptom/diagnosis change
  (p1108), new diagnostic exam results (p1109), causality change based on new info
  (p1110), event outcome change including recovery (p1111), other clinical course
  description (p1112)
- "Including recovery" explicitly preserved: never converted to worsening-only
  or recovery-exempt
- "Including" and "other description" open-ended: never closed into exhaustive
  list, never adding unstated items
- package 94 prevention of absorption: SAE report form, written report, sponsor
  contact, IRB/ethics/regulatory reporting, treatment measures, autopsy/final
  medical report, Appendix 7 contact info belong to package 94 and are never
  absorbed
- zero candidates: required_candidate_source_refs explicitly empty; every
  owned ref is forbidden to emit a candidate
- official matrix keeps zero rows anchored in body.p1102-p1112 and zero 不良事件 /
  TEAE / SAE / 应报告事件 rows; procedure catalog has no AE node and no
  p1102-p1112 spans
- immutable source fingerprints and checklist freeze (claims_complete=false)

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
    / "representative_group_package93_ae_reportable_events_followup_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61ce-package93-ae-reportable-events-followup-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package93-ae-reportable-events-followup-boundary"
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
PACKAGE_93_ORDINAL = 93
PACKAGE_93_ID = "pap-2815c9e5b343ac6d7663ae21"
PACKAGE_92_ORDINAL = 92
PACKAGE_92_ID = "pap-c6c57a2734d51175bf06d031"
PACKAGE_94_ORDINAL = 94
PACKAGE_94_ID = "pap-205e346371315fa509f03126"
PACKAGE_80_ORDINAL = 80
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_90_ORDINAL = 90
PACKAGE_91_ORDINAL = 91

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]

# 只读闭包（0）：本包拥有单元自包含，保持零附加来源
ATTACHED_REFS: list[str] = []

# 相邻包所有权元数据（不进入本包拥有/不进入提示）：
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG80_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]
PKG94_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1113, 1124)]

# 结构标题（仅作结构）：p1102应报告的事件类型
STRUCTURAL_REFS = ["body.p1102"]
# 治疗后处置行：p1103-p1112
SEMANTIC_OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1103, 1113)]
DISPOSITION_REFS = [f"body.p{ordinal}" for ordinal in range(1103, 1113)]

# 三类并列应报告事件类型
THREE_EVENT_REFS = ["body.p1104", "body.p1105", "body.p1106"]
# 五类新重要信息类型
FIVE_FOLLOWUP_INFO_REFS = [f"body.p{ordinal}" for ordinal in range(1108, 1113)]

# 单元元数据：unit_kind与源结构块逐段文本。
EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1102": "paragraph",
    "body.p1103": "paragraph",
    "body.p1104": "list_item",
    "body.p1105": "list_item",
    "body.p1106": "list_item",
    "body.p1107": "paragraph",
    "body.p1108": "list_item",
    "body.p1109": "list_item",
    "body.p1110": "list_item",
    "body.p1111": "list_item",
    "body.p1112": "list_item",
}

# 冻结计划拥有单元逐字摘录（权威文本，任何改写反例必须破坏至少一个片段）
OWNED_EXCERPT_BY_REF = {
    "body.p1102": "应报告的事件类型",
    "body.p1103": "以下是研究者必须在获知后24小时（含）内向申办者报告的事件类型，无论事件与试验用药品的关系如何：",
    "body.p1104": "死亡事件",
    "body.p1105": "严重不良事件",
    "body.p1106": "妊娠事件",
    "body.p1107": "研究者必须立即向申办者报告这些事件的新的重要信息（在获知信息后24小时内），包括：",
    "body.p1108": "新的体征或症状，或诊断改变",
    "body.p1109": "重要的新诊断检查结果",
    "body.p1110": "基于新信息的因果关系变化",
    "body.p1111": "事件结果的变化，包括恢复",
    "body.p1112": "关于事件临床过程的其他描述信息",
}

# 关键逐字片段门禁：改写文本必须保留的编码术语边界
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1102": ["应报告的事件类型"],
    "body.p1103": [
        "研究者必须",
        "获知后24小时（含）内",
        "向申办者报告",
        "无论事件与试验用药品的关系如何",
    ],
    "body.p1104": ["死亡事件"],
    "body.p1105": ["严重不良事件"],
    "body.p1106": ["妊娠事件"],
    "body.p1107": [
        "研究者必须立即",
        "向申办者报告",
        "这些事件的新的重要信息",
        "在获知信息后24小时内",
        "包括",
    ],
    "body.p1108": ["新的体征或症状", "诊断改变"],
    "body.p1109": ["重要的新诊断检查结果"],
    "body.p1110": ["基于新信息的因果关系变化"],
    "body.p1111": ["事件结果的变化", "包括恢复"],
    "body.p1112": ["关于事件临床过程的其他描述信息"],
}

# 以下短语用于父级规格反例探针，不是运行时文本分类器。运行时的零候选边界由
# forbidden_candidate_source_refs 按来源身份确定性拒绝，不能依赖有限关键词覆盖同义改写。

# 1. 三类事件漏并反例 (Three event types omission / merging)
THREE_EVENT_TYPES_OMISSION_MERGING_PHRASES = [
    "仅需报告严重不良事件，死亡与妊娠并入SAE处理",
    "死亡事件不单独作为应报告事件类型",
    "妊娠不是独立应报告事件类型",
    "漏掉死亡事件仅报告SAE",
    "漏掉妊娠事件仅报告严重不良事件",
    "应报告事件仅包含严重不良事件一种类型",
    "死亡并入SAE无需单独作为事件类型",
    "妊娠合并入一般不良事件无需专门报告",
    "将死亡、SAE、妊娠三类合并为单一SAE类别",
    "三类事件压缩为仅报告SAE",
]

# 2. 妊娠前提化反例 (Pregnancy conditioned on AE / SAE / drug-related)
PREGNANCY_PREREQUISITE_PHRASES = [
    "妊娠必须构成严重不良事件才需报告",
    "妊娠事件仅在伴随不良反应时报告",
    "妊娠伴有母体并发症或胎儿异常才向申办者报告",
    "妊娠事件须判定与试验用药品相关后24小时内报告",
    "无不良后果的妊娠无需24小时内报告",
    "妊娠事件必须构成AE后才适用24小时报告",
    "妊娠仅在导致住院或致畸时才报告",
    "未发生药物不良反应的妊娠不属于应报告事件",
    "妊娠事件须为药物相关不良事件",
    "妊娠须构成SAE方触发24小时报告",
]

# 3. 因果无关性弱化反例 (Causality independence weakened)
CAUSALITY_INDEPENDENCE_WEAKENING_PHRASES = [
    "仅与试验药物相关的死亡、SAE或妊娠才需24小时报告",
    "可能有关或肯定有关的事件才需在获知后24小时内报告",
    "无关事件无需在24小时内报告",
    "判定为肯定无关的死亡事件不适用24小时时限",
    "因果关系无关的妊娠事件无需向申办者报告",
    "仅药物相关的严重不良事件适用24小时报告",
    "排除药物无关事件的24小时报告要求",
    "关系无关的事件放宽至定期报告",
]

# 4. 24小时全域泛化反例 (24h limit generalized to all AEs / lab / general safety info)
DOMAIN_GENERALIZATION_PHRASES = [
    "所有不良事件均须在获知后24小时内报告",
    "所有TEAE必须在24小时内向申办者报告",
    "任何实验室检查异常必须在24小时内向申办者报告",
    "日常安全性随访信息一律24小时内报送",
    "一般不良事件均须获知后24小时（含）内报告",
    "全部安全性数据均适用24小时报告时限",
    "非严重不良事件亦须在24小时内报告申办者",
    "所有常规检验结果均须在获知后24小时内报告",
]

# 5. 首次/新信息获知锚点混同反例 (First event vs new info awareness anchor conflation)
AWARENESS_ANCHOR_CONFLATION_PHRASES = [
    "新重要信息报告时限仍以受试者最初发生事件的时间起算24小时",
    "随访新信息必须在最初获知死亡/SAE/妊娠事件后24小时内全部提交",
    "新重要信息以首次获知事件的时间为计时起点",
    "新信息报告时限锚定于首次事件获知时刻",
    "后续随访资料提交时钟不以获知新信息起算",
    "新重要信息与首次事件使用同一个获知计时锚点",
    "新诊断结果随访报告以初次发生SAE起算24小时",
]

# 6. 立即或含边界弱化反例 (Immediate / inclusive 24h boundary weakened / distorted)
IMMEDIATE_AND_INCLUSIVE_WEAKENING_PHRASES = [
    "新重要信息无需立即报告，仅按常规随访期末汇总即可",
    "删除立即报告要求，新信息随访无时限约束",
    "必须立即（0秒）完成报告，不存在24小时缓冲期",
    "获知后24小时不包含第24小时整点",
    "24小时仅为开区间不含24小时整点",
    "新重要信息随访无立即要求",
    "将立即报告篡改为实时无延迟提交并否定24小时法定缓冲",
    "删除24小时（含）中的含字要求",
]

# 7. 五类新重要信息漏并反例 (Five new important information types omitted / merged)
FIVE_FOLLOWUP_INFO_OMISSION_PHRASES = [
    "新重要信息仅包括诊断检查结果，体征症状改变无需报告",
    "因果关系变化不属于新重要信息随访范围",
    "临床过程其他描述信息无需随访报告",
    "诊断改变不属于需要随访报告的新信息",
    "新重要信息仅需报告因果关系变化一项",
    "漏掉体征症状或诊断改变",
    "漏掉重要的新诊断检查结果",
    "漏掉临床过程的其他描述信息",
]

# 8. 恢复遗漏 / 仅恶化才报告反例 (Recovery omitted / only worsening reported)
RECOVERY_OMISSION_PHRASES = [
    "事件结果仅在病情恶化或进展时才需报告",
    "事件恢复不属于结果变化，无需随访报告",
    "剔除恢复项，仅报告不良结果加重",
    "事件结果变化不包括恢复",
    "转归向好或恢复无需向申办者随访报告",
    "仅结果恶化属于新重要信息",
    "恢复正常无需作为事件结果变化报告",
    "事件恢复排除在新信息随访之外",
]

# 9. 两类报告义务压缩反例 (Two reporting obligations compressed into one)
TWO_OBLIGATIONS_COMPRESSION_PHRASES = [
    "所有事件及后续资料统一为24小时报送规则，不区分首次报告与新信息随访",
    "事件报告与新信息随访为同一义务，无需区分触发对象与列表",
    "首次报告与随访报告压缩为单一规则",
    "合并首次获知事件与新重要信息为统一报告流程",
    "不区分首次报告义务与新重要信息随访义务",
]

# 10. 第94包流程提前吞并反例 (Package 94 workflow absorption)
PACKAGE94_ABSORPTION_PHRASES = [
    "填写《SAE报告表》所有使用部分并签名",
    "向申办者指定联系人提供书面报告",
    "向伦理委员会及监管机构报告",
    "采取及时适当的治疗措施",
    "提供尸检报告和最终医学报告",
    "报告联系方式见附录7",
    "附录7将根据实际情况进行单独变更",
    "使用一份新的《SAE报告表》并标明随访信息",
    "在可溯源的参与者病历及对应的事件报告表上记录",
    "签署SAE报告表日期并于24小时内书面报告",
]

# 11. 候选升级与筛选/基线门槛反例 (Candidate upgrade phrases)
CANDIDATE_UPGRADE_PHRASES = [
    "发生死亡、SAE或妊娠事件的受试者筛选失败",
    "未在24小时内报告SAE的受试者排除出组",
    "入组前必须签署24小时报告知情同意书",
    "发布应报告事件类型控制点",
    "建立死亡/SAE/妊娠事件入排排除规则",
    "筛选期必须核对应报告事件清单",
    "基线期确认24小时报告流程作为入组条件",
    "未提供新重要信息的受试者基线不通过",
]

ALL_DETERMINISTIC_PHRASES = (
    THREE_EVENT_TYPES_OMISSION_MERGING_PHRASES
    + PREGNANCY_PREREQUISITE_PHRASES
    + CAUSALITY_INDEPENDENCE_WEAKENING_PHRASES
    + DOMAIN_GENERALIZATION_PHRASES
    + AWARENESS_ANCHOR_CONFLATION_PHRASES
    + IMMEDIATE_AND_INCLUSIVE_WEAKENING_PHRASES
    + FIVE_FOLLOWUP_INFO_OMISSION_PHRASES
    + RECOVERY_OMISSION_PHRASES
    + TWO_OBLIGATIONS_COMPRESSION_PHRASES
    + PACKAGE94_ABSORPTION_PHRASES
    + CANDIDATE_UPGRADE_PHRASES
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
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _frozen_unit_by_ref(plan: dict) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for pkg in plan["packages"]:
        for u in pkg["owned_units"]:
            units[u["source_ref"]] = u
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
    assert (
        config["schema_version"]
        == "phase5/representative-group-control-replay-config/v1"
    )
    assert (
        config["group_id"]
        == "d001-ii-package93-ae-reportable-events-followup-boundary"
    )
    assert config["task_id"] == "phase5-slice61ce-20260830"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    assert config["study_phase"] == "phase_ii"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(OWNED_REFS)
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL_REFS

    # 处置分配：p1102为结构，p1103-p1112为治疗后执行
    dispositions = config["expected_disposition_by_source_ref"]
    for ref in SEMANTIC_OWNED_REFS:
        assert dispositions[ref] == "post_treatment_execution", ref

    # 11个单元全部配置了禁止标记和质检语义
    for ref in OWNED_REFS:
        assert ref in config["candidate_forbidden_markers_by_source_ref"]
        assert len(config["candidate_forbidden_markers_by_source_ref"][ref]) >= 4
        assert ref in config["clinical_qc_checks_by_source_ref"]
        assert len(config["clinical_qc_checks_by_source_ref"][ref]) >= 2
        assert ref in config["exception_semantics_by_source_ref"]

    # 异常语义结构
    for ref, entry in config["exception_semantics_by_source_ref"].items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref
        assert entry["forbidden_inversion"], ref


def test_zero_attached_refs(config: dict, plan: dict) -> None:
    """第93包拥有单元已自包含两组引导句及其列表，保持零附加来源。"""
    assert config["attached_source_refs"] == []
    pkg93 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    assert len(pkg93["owned_units"]) == 11


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包p995-p1006（12）、第79包p1007-p1014（8）、
    第80包p1015-p1026（12）、第82包表7 t12.r0-r4（5）、第87包p1074-p1083（10）、
    第88包p1084-p1086（3）、第89包表8 t13.r0-r5（6）、第90包p1087-p1097（11）、
    第91包表9 t14.r0-r7（8）、第92包p1098-p1101（4）、第93包p1102-p1112（11）、
    第94包p1113-p1123（11）。"""
    pkgs = {p["package_ordinal"]: p for p in plan["packages"]}
    assert len(pkgs[78]["owned_units"]) == 12
    assert len(pkgs[79]["owned_units"]) == 8
    assert len(pkgs[80]["owned_units"]) == 12
    assert len(pkgs[82]["owned_units"]) == 5
    assert len(pkgs[87]["owned_units"]) == 10
    assert len(pkgs[88]["owned_units"]) == 3
    assert len(pkgs[89]["owned_units"]) == 6
    assert len(pkgs[90]["owned_units"]) == 11
    assert len(pkgs[91]["owned_units"]) == 8
    assert len(pkgs[92]["owned_units"]) == 4
    assert len(pkgs[93]["owned_units"]) == 11
    assert len(pkgs[94]["owned_units"]) == 11

    owned_93 = {u["source_ref"] for u in pkgs[93]["owned_units"]}
    assert set(PKG93_SPAN_REFS) == owned_93


# ---------------------------------------------------------------------------
# frozen plan ownership and source identity
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_93(config: dict, plan: dict) -> None:
    matches = [
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    ]
    assert len(matches) == 1
    pkg93 = matches[0]
    assert pkg93["package_id"] == PACKAGE_93_ID
    owned = {u["source_ref"] for u in pkg93["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, expected in OWNED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == expected, f"{ref} 摘录与冻结计划不一致"


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    """p1102/p1103/p1107为paragraph，其余为list_item；全部位于'应报告的事件类型'标题下。"""
    pkg93 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    for unit in pkg93["owned_units"]:
        ref = unit["source_ref"]
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[ref], ref
        expected_path = [
            "研究评估和程序",
            "安全性评估",
            "不良事件的报告",
            "研究者向申办者报告不良事件等信息的要求与途径",
            "应报告的事件类型",
        ]
        assert unit.get("heading_path") == expected_path, ref


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    """段落摘录必须与源结构块逐段文本一致，证明无改写、无拼接错位。"""
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        assert _structure_blob_text(structure_blob, ref) == excerpts[ref], ref


# ---------------------------------------------------------------------------
# p1103 lead structure & scope
# ---------------------------------------------------------------------------


def test_p1103_lead_structure_and_scope_preserved(config: dict) -> None:
    """p1103作为p1104-p1106的共同引导句：研究者向申办者在获知后24小时（含）内报告，无论与药物关系如何。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1103"]
    assert "研究者" in semantics["base_rule"]
    assert "申办者" in semantics["base_rule"]
    assert "24小时（含）内" in semantics["base_rule"]
    assert "无论事件与试验用药品的关系如何" in semantics["base_rule"]
    assert "共同引导句" in semantics["exception_rule"]

    checks = config["clinical_qc_checks_by_source_ref"]["body.p1103"]
    checks_blob = " ".join(checks)
    assert "24小时（含）内" in checks_blob
    assert "无论与试验用药品关系如何" in checks_blob
    assert "不得泛化" in checks_blob

    # 关键片段
    for fragment in STRUCTURAL_FRAGMENTS_BY_REF["body.p1103"]:
        assert fragment in OWNED_EXCERPT_BY_REF["body.p1103"], fragment


# ---------------------------------------------------------------------------
# three reportable events parallel & independent
# ---------------------------------------------------------------------------


def test_p1104_p1106_three_events_parallel_independent(config: dict) -> None:
    """死亡事件（p1104）、严重不良事件（p1105）、妊娠事件（p1106）三类并列独立，不能漏项或合并。"""
    for ref in THREE_EVENT_REFS:
        semantics = config["exception_semantics_by_source_ref"][ref]
        assert "并列" in semantics["exception_rule"]
        assert (
            "不得漏掉" in semantics["forbidden_inversion"]
            or "不得合并" in semantics["forbidden_inversion"]
            or "不得把死亡事件并入SAE" in semantics["forbidden_inversion"]
        )

    checks_1104 = " ".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1104"]
    )
    assert "死亡事件" in checks_1104
    assert "并列" in checks_1104

    checks_1105 = " ".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1105"]
    )
    assert "严重不良事件" in checks_1105
    assert "并列" in checks_1105

    checks_1106 = " ".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1106"]
    )
    assert "妊娠事件" in checks_1106
    assert "并列" in checks_1106


def test_three_event_types_omission_merging_counterexamples_detected() -> None:
    """三类事件漏并反例必须被确定性拦截。"""
    for text in THREE_EVENT_TYPES_OMISSION_MERGING_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"三类事件漏并反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# pregnancy unconditioned
# ---------------------------------------------------------------------------


def test_pregnancy_event_unconditioned_preserved(config: dict) -> None:
    """妊娠事件本身即为应报告事件，不得附加必须构成AE/SAE或必须与药物相关的先决条件。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1106"]
    assert "不得附加妊娠事件必须为严重不良事件、必须发生AE或必须与药物相关" in semantics["forbidden_inversion"]

    checks = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1106"])
    assert "不得附加必须发生AE" in checks and "必须构成SAE" in checks


def test_pregnancy_prerequisite_counterexamples_detected() -> None:
    """妊娠前提化反例必须被确定性拦截。"""
    for text in PREGNANCY_PREREQUISITE_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"妊娠前提化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# causality independence (regardless of relationship)
# ---------------------------------------------------------------------------


def test_causality_independence_regardless_of_relationship_preserved(
    config: dict,
) -> None:
    """无论事件与试验用药品的关系如何同时覆盖死亡、SAE、妊娠三类事件。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1103"]
    assert "无论事件与试验用药品的关系如何" in semantics["base_rule"]
    assert "无论与试验用药品关系如何" in semantics["exception_rule"]

    checks = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1103"])
    assert "无论与试验用药品关系如何" in checks


def test_causality_independence_weakening_counterexamples_detected() -> None:
    """因果无关性弱化反例必须被确定性拦截。"""
    for text in CAUSALITY_INDEPENDENCE_WEAKENING_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"因果无关性弱化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# 24-hour limit strictly bounded (not generalized to all AEs)
# ---------------------------------------------------------------------------


def test_24h_timeline_not_generalized_to_all_aes(config: dict) -> None:
    """24小时时限仅适用于死亡、SAE、妊娠三类事件及新重要信息，不得泛化至所有AE。"""
    checks_1103 = " ".join(
        config["clinical_qc_checks_by_source_ref"]["body.p1103"]
    )
    assert (
        "不得泛化为所有AE、TEAE、实验室异常或任何常规安全性信息均须24小时报告"
        in checks_1103
    )

    note = " ".join(config.get("notes", []))
    assert "不得泛化为所有AE、TEAE、实验室异常或全域常规资料均须24小时报告" in note


def test_24h_domain_generalization_counterexamples_detected() -> None:
    """24小时全域泛化反例必须被确定性拦截。"""
    for text in DOMAIN_GENERALIZATION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"24小时全域泛化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# p1107 lead structure & awareness anchor separation
# ---------------------------------------------------------------------------


def test_p1107_lead_structure_and_anchor_separation_preserved(
    config: dict,
) -> None:
    """p1107'这些事件'回指p1104-p1106，计时锚点为获知新信息，与首次事件获知分离。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1107"]
    assert "这些事件" in semantics["base_rule"]
    assert "立即" in semantics["base_rule"]
    assert "获知信息后24小时内" in semantics["base_rule"]
    assert "回指" in semantics["exception_rule"]
    assert "不得将计时锚点混同为首次获知事件的时间" in semantics["forbidden_inversion"]

    checks = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1107"])
    assert "计时锚点为获知新信息" in checks
    assert "独立的报告义务" in checks


def test_awareness_anchor_conflation_counterexamples_detected() -> None:
    """首次/新信息获知锚点混同反例必须被确定性拦截。"""
    for text in AWARENESS_ANCHOR_CONFLATION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"首次/新信息计时锚点混同反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# "Immediately" and "within 24h (inclusive)" dual attributes
# ---------------------------------------------------------------------------


def test_immediate_and_inclusive_24h_boundary_preserved(config: dict) -> None:
    """立即与24小时内关系正确：不得删除立即，不得篡改为瞬时完成否定24小时缓冲，保留（含）字边界。"""
    semantics_1103 = config["exception_semantics_by_source_ref"]["body.p1103"]
    assert "24小时（含）内" in semantics_1103["base_rule"]
    assert "24小时（含）" in semantics_1103["forbidden_inversion"]

    semantics_1107 = config["exception_semantics_by_source_ref"]["body.p1107"]
    assert "不得删除'立即'或将'立即'解释为无序随访" in semantics_1107["forbidden_inversion"]
    assert "不得将'立即'篡改为瞬时完成而否定24小时缓冲" in semantics_1107["forbidden_inversion"]


def test_immediate_and_inclusive_weakening_counterexamples_detected() -> None:
    """立即或含边界弱化反例必须被确定性拦截。"""
    for text in IMMEDIATE_AND_INCLUSIVE_WEAKENING_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"立即或含边界弱化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# five new important information types complete
# ---------------------------------------------------------------------------


def test_five_followup_info_types_complete_preserved(config: dict) -> None:
    """p1108-p1112五类新重要信息完整保留，不得漏并。"""
    for ref in FIVE_FOLLOWUP_INFO_REFS:
        semantics = config["exception_semantics_by_source_ref"][ref]
        assert (
            "不得漏项" in semantics["forbidden_inversion"]
            or "不得删除" in semantics["forbidden_inversion"]
            or "不得将" in semantics["forbidden_inversion"]
        )

    assert (
        "新的体征或症状" in OWNED_EXCERPT_BY_REF["body.p1108"]
        and "诊断改变" in OWNED_EXCERPT_BY_REF["body.p1108"]
    )
    assert (
        "重要的新诊断检查结果" in OWNED_EXCERPT_BY_REF["body.p1109"]
    )
    assert (
        "基于新信息的因果关系变化" in OWNED_EXCERPT_BY_REF["body.p1110"]
    )
    assert (
        "事件结果的变化，包括恢复" in OWNED_EXCERPT_BY_REF["body.p1111"]
    )
    assert (
        "关于事件临床过程的其他描述信息"
        in OWNED_EXCERPT_BY_REF["body.p1112"]
    )


def test_five_followup_info_omission_counterexamples_detected() -> None:
    """五类新重要信息漏并反例必须被确定性拦截。"""
    for text in FIVE_FOLLOWUP_INFO_OMISSION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"五类新重要信息漏并反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# p1111 "including recovery" explicitly preserved
# ---------------------------------------------------------------------------


def test_p1111_including_recovery_explicitly_preserved(config: dict) -> None:
    """p1111'包括恢复'必须显式保留，不得改写为只有恶化才报告或恢复无需报告。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1111"]
    assert "包括恢复" in semantics["base_rule"]
    assert "包括恢复" in semantics["exception_rule"]
    assert (
        "不得删除'包括恢复'" in semantics["forbidden_inversion"]
        or "只有恶化才需随访" in semantics["forbidden_inversion"]
    )

    checks = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1111"])
    assert "包括恢复" in checks
    assert "不得改写为只有恶化才报告" in checks


def test_recovery_omission_counterexamples_detected() -> None:
    """恢复遗漏反例必须被确定性拦截。"""
    for text in RECOVERY_OMISSION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"恢复遗漏反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# two reporting obligations separated
# ---------------------------------------------------------------------------


def test_two_reporting_obligations_separation_preserved(config: dict) -> None:
    """首次事件报告与新重要信息随访两类义务分离，触发对象、获知锚点和列表不同。"""
    note = " ".join(config.get("notes", []))
    assert (
        "建立两组核心结构关系：p1103→p1104-p1106（首次事件报告义务）与p1107→p1108-p1112（新重要信息随访义务）"
        in note
    )
    assert (
        "两类义务触发条件、计时锚点和列表严格分离，不得压缩为一个笼统规则"
        in note
    )


def test_two_obligations_compression_counterexamples_detected() -> None:
    """两类义务压缩反例必须被确定性拦截。"""
    for text in TWO_OBLIGATIONS_COMPRESSION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"两类义务压缩反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# structural headings never converted to obligations
# ---------------------------------------------------------------------------


def test_structural_heading_never_converted_to_obligations(config: dict) -> None:
    """p1102仅作结构，不生成独立报告义务、控制点或入排门槛。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1102"]
    assert "仅作结构" in semantics["exception_rule"]
    assert "不得把标题解释为独立规则" in semantics["forbidden_inversion"]
    assert "body.p1102" in config["structural_only_source_refs"]


# ---------------------------------------------------------------------------
# package 94 prevention of absorption
# ---------------------------------------------------------------------------


def test_package94_content_not_absorbed(config: dict) -> None:
    """第94包（body.p1113-p1123）SAE报告表、书面报告、联系人、伦理监管、治疗措施等不得进入本包。"""
    attached = set(config["attached_source_refs"])
    for ref in PKG94_SPAN_REFS:
        assert ref not in attached, f"{ref} 不得归入第93包附加"
        assert ref not in config["owned_source_refs"], f"{ref} 不得归入第93包拥有"


def test_package94_absorption_counterexamples_detected() -> None:
    """第94包流程提前吞并反例必须被确定性拦截。"""
    for text in PACKAGE94_ABSORPTION_PHRASES:
        hits = _deterministic_hits(text)
        assert hits, f"第94包流程吞并反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# neighbor prevention of absorption
# ---------------------------------------------------------------------------


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    """第78/79/80/82/87/88/89/90/91/92/94包仅保留所有权元数据，不进入本包拥有或附加。"""
    attached = set(config["attached_source_refs"])
    owned = set(config["owned_source_refs"])
    all_neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG94_SPAN_REFS
    )
    for ref in all_neighbors:
        assert ref not in attached, f"{ref} 不得进入第93包附加"
        assert ref not in owned, f"{ref} 不得进入第93包拥有"


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    expected_owners = boundary["expected_owners_by_span"]
    for pkg in plan["packages"]:
        ordinal = pkg["package_ordinal"]
        if ordinal in (78, 79, 80, 82, 87, 88, 89, 90, 91, 92, 94):
            for unit in pkg["owned_units"]:
                ref = unit["source_ref"]
                assert expected_owners.get(ref) == ordinal, (
                    f"{ref} 期望归属包 {ordinal}，配置中为 {expected_owners.get(ref)}"
                )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "第93包拥有应报告事件类型、24小时时限及新重要信息随访流程" in note
    assert "以防吞并" in note or "防吞并" in note


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
    assert by_ref["body.p1102"].excerpt == "应报告的事件类型"
    assert "获知后24小时（含）内" in by_ref["body.p1103"].excerpt
    assert "无论事件与试验用药品的关系如何" in by_ref["body.p1103"].excerpt
    assert by_ref["body.p1104"].excerpt == "死亡事件"
    assert by_ref["body.p1105"].excerpt == "严重不良事件"
    assert by_ref["body.p1106"].excerpt == "妊娠事件"
    assert "研究者必须立即" in by_ref["body.p1107"].excerpt
    assert "在获知信息后24小时内" in by_ref["body.p1107"].excerpt
    assert "新的体征或症状" in by_ref["body.p1108"].excerpt
    assert by_ref["body.p1109"].excerpt == "重要的新诊断检查结果"
    assert by_ref["body.p1110"].excerpt == "基于新信息的因果关系变化"
    assert by_ref["body.p1111"].excerpt == "事件结果的变化，包括恢复"
    assert by_ref["body.p1112"].excerpt == "关于事件临床过程的其他描述信息"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含本包闭包与防吞并边界，不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS)
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"

    # 相邻包不得进入
    all_neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG94_SPAN_REFS
    )
    for ref in all_neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 11
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 11
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

    # 越界候选（把应报告事件或随访流程升格为筛选/基线控制候选）必须被拒绝
    for ref in OWNED_REFS:
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对应报告事件与24小时报告流程，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 即使标题使用短语探针未覆盖的同义改写，来源身份门禁仍必须拒绝候选
    paraphrased_candidates = {
        "body.p1102": "应报告事件类型章节作为入组前安全性培训门槛",
        "body.p1103": "获知后24小时报告义务作为受试者随访执行前置条件",
        "body.p1104": "死亡事件报告流程作为机构伦理准入门槛",
        "body.p1105": "严重不良事件报告规范作为研究者资质审核条件",
        "body.p1106": "妊娠事件通报要求作为女性受试者入选先决标准",
        "body.p1107": "新重要信息随访时限作为中心启动考核指标",
        "body.p1108": "体征症状与诊断改变随访作为不良事件监测门槛",
        "body.p1109": "新诊断检查结果报送作为实验室质控前置要求",
        "body.p1110": "因果关系变化随访作为医学评估入选准则",
        "body.p1111": "转归与恢复随访作为受试者结束研究标准",
        "body.p1112": "临床过程描述作为个案病例报告完整性指标",
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
    for ref in OWNED_REFS:
        hits = _deterministic_hits(excerpts[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把第93包内容改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1102": [
            "筛选必做：应报告的事件类型核对",
            "基线期必做：确认应报告事件类型",
            "应报告事件类型未明确作为证据缺口，不得入组",
            "应报告事件类型发布控制点",
        ],
        "body.p1103": [
            "筛选期必做：获知后24小时报告流程培训",
            "基线必做：24小时报告签署承诺",
            "未承诺24小时报告视为证据缺口，判定入排不通过",
            "转移所有权至第93包发布控制点",
        ],
        "body.p1104": [
            "筛选必做：死亡事件通报途径核实",
            "基线必做：死亡事件流程确认",
            "死亡事件报告机制缺失视为入排不通过",
            "发布控制点：死亡事件报告",
        ],
        "body.p1105": [
            "筛选必做：严重不良事件24小时报告核对",
            "基线必做：SAE报告流程签署",
            "SAE报告未达标构成证据缺口，不符合入选标准",
            "严重不良事件发布控制点",
        ],
        "body.p1106": [
            "筛选必做：妊娠事件报告流程告知",
            "基线期必做：妊娠24小时通报承诺",
            "妊娠事件报告未签署视为入排不通过",
            "妊娠事件发布控制点",
        ],
        "body.p1107": [
            "筛选必做：新重要信息立即报告培训",
            "基线必做：新信息24小时内报送确认",
            "新重要信息随访机制缺失视为证据缺口，不得入组",
            "发布控制点：新重要信息随访",
        ],
        "body.p1108": [
            "筛选期必做：新体征症状与诊断改变随访核对",
            "基线必做：诊断改变报告承诺",
            "体征症状改变未随访视为入排不通过",
        ],
        "body.p1109": [
            "筛选必做：新诊断检查结果随访流程确认",
            "基线期必做：重要新结果报送培训",
            "诊断检查结果随访缺失视为入排不通过",
        ],
        "body.p1110": [
            "筛选必做：因果关系变化随访机制审核",
            "基线必做：因果变化报告确认",
            "因果关系变化未及时报告视为证据缺口，不得入组",
        ],
        "body.p1111": [
            "筛选期必做：事件转归包括恢复随访确认",
            "基线必做：恢复报告流程培训",
            "转归及恢复随访不全视为入排不通过",
        ],
        "body.p1112": [
            "筛选必做：临床过程其他描述信息记录审核",
            "基线期必做：临床过程随访承诺",
            "临床过程描述缺失视为证据缺口，不得入组",
        ],
    }
    for ref, counterexamples in counterexamples_by_ref.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        for text in counterexamples:
            hits = _forbidden_marker_hits(text, markers)
            assert hits, f"{ref} 升格反例未被 forbidden_markers 拦截: {text}"


# ---------------------------------------------------------------------------
# prompt contents & exclusion
# ---------------------------------------------------------------------------


def test_prompt_excludes_neighbor_and_package94_content() -> None:
    """第78/79/80/82/87/88/89/90/91/92/94包内容不得进入提示。"""
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")

    # 第94包具体流程不得进入提示
    package94_fragments = [
        "应提供的安全信息资料及要求",
        "填写《SAE报告表》的所有使用部分",
        "书面报告至申办者和其指定联系人",
        "尸检报告和最终医学报告",
        "本研究的报告联系方式见附录7",
        "附录7将根据实际情况进行单独变更",
    ]
    for fragment in package94_fragments:
        assert fragment not in prompt_text, f"提示不当吸入第94包报告流程: {fragment}"

    # 第92包预期性评估与第80包SUSAR定义等不得进入提示
    for fragment in [
        "评估CMS-D001片不良事件预期性见CMS-D001片的《研究者手册》",
        "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）",
    ]:
        assert fragment not in prompt_text, f"提示不当吸入相邻包内容: {fragment}"


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第93包全部拥有来源必须逐字进入提示。"""
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    for ref in OWNED_REFS:
        assert OWNED_EXCERPT_BY_REF[ref] in prompt_text, f"{ref} 摘录未逐字进入提示"


def test_prompt_deterministic_phrases_clean() -> None:
    """提示本身不得包含任何确定性反例措辞。"""
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    hits = _deterministic_hits(prompt_text)
    assert hits == [], f"提示含确定性反例措辞: {hits}"


# ---------------------------------------------------------------------------
# official flow matrix & procedure catalog isolation
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package93(
    matrix: dict, plan: dict
) -> None:
    pkg93 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    all_refs = {u["source_ref"] for u in pkg93["owned_units"]}
    for row in matrix["rows"]:
        anchor = row.get("protocol_source_span_id") or row.get(
            "source_span_id"
        )
        assert anchor not in all_refs, (
            f"matrix row {row.get('rule_id')} anchored in {anchor}"
        )


def test_matrix_has_no_ae_teae_sae_reportable_event_rows(matrix: dict) -> None:
    for row in matrix["rows"]:
        text = " ".join(
            str(row.get(k, ""))
            for k in ("rule_id", "canonical_name", "description", "category")
        )
        assert "不良事件" not in text, (
            f"matrix contains AE row: {row.get('rule_id')}"
        )
        assert "TEAE" not in text, (
            f"matrix contains TEAE row: {row.get('rule_id')}"
        )
        assert "严重不良事件" not in text, (
            f"matrix contains SAE row: {row.get('rule_id')}"
        )
        assert "应报告的事件类型" not in text, (
            f"matrix contains reportable event row: {row.get('rule_id')}"
        )
        assert "新重要信息" not in text, (
            f"matrix contains new important info row: {row.get('rule_id')}"
        )


def test_no_official_rule_anchors_package93_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg93 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    owned_spans = {
        span for u in pkg93["owned_units"] for span in u.get("source_span_ids", [])
    }
    for row in matrix["rows"]:
        for span_id in row.get("source_span_ids", []):
            assert span_id not in owned_spans, (
                f"official matrix rule {row.get('rule_id')} anchors package 93 span {span_id}"
            )


def test_procedure_catalog_has_no_ae_or_reportable_event_node(
    procedure_catalog: dict,
) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = item.get("label", "")
        assert "不良事件" not in label
        assert "TEAE" not in label
        assert "严重不良事件" not in label
        assert "应报告" not in label
        assert "新重要信息" not in label


def test_no_procedure_node_sourced_from_package93(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span_id in item.get("source_span_ids", []):
            for ordinal in range(1102, 1113):
                assert not span_id.startswith(f"body.p{ordinal}"), span_id


def test_known_targets_build_empty(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert official == []
    assert procedures == []


def test_workflow_stages_keep_d1_pre_dose_distinct(config: dict) -> None:
    from slice59n_representative_group_control_replay import _workflow

    stages = {s.workflow_stage_id: s for s in _workflow(config)}
    assert set(stages) == {"flow-screening", "flow-baseline", "flow-d1-pre-dose"}
    assert stages["flow-screening"].review_stage.value == "screening"
    assert stages["flow-baseline"].review_stage.value == "baseline"
    assert stages["flow-d1-pre-dose"].review_stage.value == "baseline"
    assert (
        stages["flow-baseline"].workflow_stage_id
        != stages["flow-d1-pre-dose"].workflow_stage_id
    )


# ---------------------------------------------------------------------------
# fingerprints & checklist freeze
# ---------------------------------------------------------------------------


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(COVERAGE_PATH)
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "papl-40b1237a22e538a278b4fd5e" in text
    assert PACKAGE_93_ID in text
    assert "body.p1102" in text
    assert "body.p1112" in text
    assert "claims_complete=false" in text
