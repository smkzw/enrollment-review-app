#!/usr/bin/env python3
"""Slice61cd model-free source-closure regressions.

Locks the D001 II package 92 AE expectedness reference and report section
heading boundary (frozen plan package 92: 不良事件预期性评估与报告章节入口,
body.p1098-p1101) to its authoritative sources before any semantic replay
decision:

- config contract and role partition: 4 owned refs body.p1098-p1101
  (p1098 expectedness title structural only, p1099 Investigator's Brochure
  reference post_treatment_execution, p1100 reporting title structural only,
  p1101 investigator reporting requirements title structural only);
  attached refs (package 80 body.p1018 SUSAR definition and body.p1019
  unexpected adverse reaction definition / Investigator's Brochure reference)
  stay read-only with ownership preserved to package 80
- Investigator's Brochure version/content fabrication prevented: p1099 only
  establishes that expectedness assessment refers to CMS-D001 Investigator's
  Brochure; no version number, date, risk items, or individual conclusions
  are provided; no version is fabricated, no "latest version" is defaulted,
  and no risk item is invented
- missing brochure content never turned into definite conclusion or evidence gap:
  absence of brochure text in protocol cannot be reinterpreted as expected,
  unexpected, evidence gap, or screening failure
- known mechanism != expectedness: package 90/91 causality input ("conforms
  to known mechanism of action, characteristics, or known adverse reactions")
  never substitutes for expectedness assessment
- three-dimensional separation: causality, severity, and expectedness are
  independent dimensions and must never be mutually derived or conflated
- SUSAR three-dimensional AND conjunction preserved: p1018 SUSAR is suspected
  (causality) + unexpected (information reference) + serious (SAE); never
  weakened to any single dimension
- report headings never converted to obligations: p1100/p1101 only close the
  reporting chapter hierarchy and do not generate reporting targets,
  timelines, forms, pathways, or follow-up duties
- package 93 prevention of absorption: package 93 (body.p1102-p1112, specific
  reportable events, 24-hour clock, new information follow-up) stays outside
  owned and attached closure; only ownership metadata is retained
- zero candidates: required_candidate_source_refs explicitly empty; every
  owned and attached ref is forbidden to emit a candidate
- official matrix keeps zero rows anchored in body.p1098-p1101 or body.p1018-p1019
  and zero 不良事件 / TEAE / SAE rows; procedure catalog has no AE node and no
  p1098-p1101 / p1018-p1019 spans
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
    / "representative_group_package92_ae_expectedness_report_heading_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61cd-package92-ae-expectedness-report-heading-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package92-ae-expectedness-report-heading-boundary"
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
PACKAGE_92_ORDINAL = 92
PACKAGE_92_ID = "pap-c6c57a2734d51175bf06d031"
PACKAGE_91_ORDINAL = 91
PACKAGE_91_ID = "pap-87e89271165354d285b2faa1"
PACKAGE_93_ORDINAL = 93
PACKAGE_93_ID = "pap-2815c9e5b343ac6d7663ae21"
PACKAGE_80_ORDINAL = 80
PACKAGE_80_ID = "pap-bb9bf95c9cd13f15e3b737f3"
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_90_ORDINAL = 90

OWNED_REFS = ["body.p1098", "body.p1099", "body.p1100", "body.p1101"]

# 只读闭包（2）：第80包 body.p1019（非预期不良反应定义及《研究者手册》主要文件参考地位）
# 与 body.p1018（SUSAR定义）。全部只读进入提示，所有权仍归第80包。
ATTACHED_REFS = ["body.p1018", "body.p1019"]

# 相邻包所有权元数据（不进入本包拥有/不进入提示）：
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG80_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG80_UNATTACHED_REFS = [
    ref for ref in PKG80_SPAN_REFS if ref not in set(ATTACHED_REFS)
]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = ["body.p1098", "body.p1099", "body.p1100", "body.p1101"]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]

# 结构标题（仅作结构）：p1098不良事件预期性评估、p1100不良事件的报告、
# p1101研究者向申办者报告不良事件等信息的要求与途径
STRUCTURAL_REFS = ["body.p1098", "body.p1100", "body.p1101"]
# 治疗后处置行：p1099
SEMANTIC_OWNED_REFS = ["body.p1099"]
DISPOSITION_REFS = ["body.p1099"]

# 单元元数据：unit_kind（全部为paragraph）与源结构块逐段文本。
EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1098": "paragraph",
    "body.p1099": "paragraph",
    "body.p1100": "paragraph",
    "body.p1101": "paragraph",
}

# 冻结计划拥有单元逐字摘录（权威文本，任何改写反例必须破坏至少一个片段）
OWNED_EXCERPT_BY_REF = {
    "body.p1098": "不良事件预期性评估",
    "body.p1099": "本研究中，评估CMS-D001片不良事件预期性见CMS-D001片的《研究者手册》。",
    "body.p1100": "不良事件的报告",
    "body.p1101": "研究者向申办者报告不良事件等信息的要求与途径",
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1018": "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）指临床表现的性质和严重程度超出了试验药物《研究者手册》、已上市药品的说明书或者产品特性摘要等已有资料信息的可疑并且非预期的严重不良反应。",
    "body.p1019": "非预期不良反应指不良反应的性质、严重程度、后果或频率，不同于试验药物当前相关资料（如《研究者手册》等文件）所描述的预期风险。《研究者手册》作为主要文件提供用以判断某不良反应是否预期或非预期的安全性参考信息。",
}

# 关键逐字片段门禁：改写文本必须保留的编码术语边界
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1098": ["不良事件预期性评估"],
    "body.p1099": [
        "本研究中",
        "评估CMS-D001片不良事件预期性",
        "CMS-D001片",
        "《研究者手册》",
    ],
    "body.p1100": ["不良事件的报告"],
    "body.p1101": ["研究者向申办者报告不良事件等信息的要求与途径"],
    "body.p1018": [
        "可疑且非预期严重不良反应",
        "SUSAR",
        "性质和严重程度",
        "超出了",
        "《研究者手册》",
        "可疑并且非预期的严重不良反应",
    ],
    "body.p1019": [
        "非预期不良反应",
        "性质、严重程度、后果或频率",
        "《研究者手册》",
        "主要文件",
        "安全性参考信息",
    ],
}

# 以下短语用于父级规格反例探针，不是运行时文本分类器。运行时的零候选边界由
# forbidden_candidate_source_refs 按来源身份确定性拒绝，不能依赖有限关键词覆盖同义改写。

# 1. 研究者手册版本或内容虚构反例
BROCHURE_VERSION_FABRICATION_PHRASES = [
    "《研究者手册》第3.0版",
    "《研究者手册》第2.0版",
    "2023年版研究者手册",
    "2024年版研究者手册",
    "2025年版研究者手册",
    "最新版本研究者手册",
    "当前有效版本研究者手册",
    "手册v2.1",
    "按2025版研究者手册",
    "研究者手册第1.0版",
    "默认最新版本",
    "默认按最新版《研究者手册》",
    "自动采用最新版本手册",
]
BROCHURE_RISK_ITEM_FABRICATION_PHRASES = [
    "《研究者手册》中明确列出皮疹为预期风险",
    "手册未列入肝损",
    "手册第4章安全信息",
    "手册中列明的预期毒性",
    "手册中已记录的不良事件",
    "手册中明确预期的事件",
    "手册列明的不良反应",
]

# 2. 无手册结论化 / 缺少手册内容改成确定结论或证据缺口反例
MISSING_BROCHURE_CONCLUSION_PHRASES = [
    "未提供研究者手册，判定为非预期不良事件",
    "因缺少研究者手册，直接认定为预期不良反应",
    "手册内容未知，判定为证据缺口",
    "手册信息不足，判定为研究药物非预期风险",
    "缺少手册判定不通过",
    "未见手册内容判定为非预期",
    "缺少手册判定为非预期",
    "因手册未知直接认定非预期",
    "缺少研究者手册直接判定",
]

# 3. 已知性（第90/91包因果输入）替代预期性反例
KNOWN_MECHANISM_EXPECTEDNESS_PHRASES = [
    "符合已知作用机制即为预期不良反应",
    "已知不良反应等同于预期不良事件",
    "已知特性直接判定为预期风险",
    "已知作用机制替代预期性评估",
    "已知不良反应即预期",
    "符合已知机制即视为预期",
    "符合已知作用机制即预期",
    "已知特性即为预期",
]

# 4. 因果性/严重性/预期性互推与跨维度混同反例
DIMENSION_CONFLATION_PHRASES = [
    "因果关系为肯定有关，故判定为预期不良事件",
    "判定为无关的不良事件即为非预期",
    "因果相关即预期",
    "很可能有关即预期不良事件",
    "因果不相关即非预期",
    "严重不良事件即为非预期不良反应",
    "3级严重程度不良事件自动判定为非预期",
    "非预期不良事件判定为肯定有关",
    "轻度不良事件即为预期",
    "重度不良事件即非预期",
    "SAE即非预期",
    "预期性即因果关系",
    "因果关系即预期性",
    "严重程度即预期性",
    "预期性即严重程度",
]

# 5. SUSAR 三维合取弱化反例（单独非预期/单独严重/单独相关即SUSAR）
SUSAR_CONJUNCTION_WEAKENING_PHRASES = [
    "非预期不良事件即构成SUSAR",
    "只要是严重不良事件即为SUSAR",
    "因果关系相关的不良事件即为SUSAR",
    "非预期或严重即为SUSAR",
    "严重不良反应即SUSAR",
    "非预期即可报告为SUSAR",
    "只要相关且严重即为SUSAR",
    "非预期不良反应即SUSAR",
    "单独非预期即为SUSAR",
    "单独严重即为SUSAR",
]

# 6. 报告标题义务化反例
HEADING_OBLIGATION_PHRASES = [
    "不良事件预期性评估标题要求研究者必须在入组前完成预期性评估",
    "不良事件的报告标题规定研究者必须填写报告表",
    "研究者向申办者报告不良事件等信息的要求与途径规定必须通过邮件报告",
    "标题要求报告不良事件",
    "标题规定报告途径为电子系统",
    "不良事件预期性评估标题要求进行评价",
    "不良事件的报告标题规定报告时限",
    "标题规定研究者报告途径",
]

# 7. 第93包 24 小时流程与应报告事件提前吞并反例
PACKAGE93_ABSORPTION_PHRASES = [
    "研究者获知不良事件后24小时内向申办者报告",
    "24小时内报告SAE",
    "随访新信息需在24小时内补充报告",
    "填写严重不良事件报告表",
    "24小时报告时钟",
    "24小时内书面报告",
    "新信息24小时内随访",
    "24小时内报告申办者",
    "24小时内填写报告表",
]

# 8. 候选升级与筛选/基线门槛反例
CANDIDATE_UPGRADE_PHRASES = [
    "筛选期必做不良事件预期性评估",
    "基线期检查研究者手册预期性",
    "证据缺口不得入组",
    "不符合入选标准",
    "排除标准：未进行预期性评估",
    "基线前必查研究者手册",
    "入组前必查预期性",
    "筛选期必查预期性",
]

ALL_DETERMINISTIC_PHRASES = (
    BROCHURE_VERSION_FABRICATION_PHRASES
    + BROCHURE_RISK_ITEM_FABRICATION_PHRASES
    + MISSING_BROCHURE_CONCLUSION_PHRASES
    + KNOWN_MECHANISM_EXPECTEDNESS_PHRASES
    + DIMENSION_CONFLATION_PHRASES
    + SUSAR_CONJUNCTION_WEAKENING_PHRASES
    + HEADING_OBLIGATION_PHRASES
    + PACKAGE93_ABSORPTION_PHRASES
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
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL
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
    assert config["group_id"] == "d001-ii-package92-ae-expectedness-report-heading-boundary"
    assert config["task_id"] == "phase5-slice61cd-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 4

    attached = set(config["attached_source_refs"])
    assert attached == set(ATTACHED_REFS)
    assert len(config["attached_source_refs"]) == 2

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])

    assert structural == set(STRUCTURAL_REFS), "第92包三个标题仅作结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS + ATTACHED_REFS), (
        "第92包拥有单元与只读附加单元均禁止发射候选"
    )
    assert pre_enrollment == set()
    assert required == set(), "第92包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 零候选不等于无语义处置：p1099归治疗后执行语义；p1098/p1100/p1101仅作结构
    assert config["expected_disposition_by_source_ref"] == {
        "body.p1099": "post_treatment_execution"
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

    # 语义结构：拥有单元必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref
        assert entry["forbidden_inversion"], ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg92 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL
    )
    owned_92 = {u["source_ref"] for u in pkg92["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_92), "attached refs must not be owned by package 92"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 2


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_80_ORDINAL], f"{ref} 必须保持归第80包"
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_92_ORDINAL], f"{ref} 必须保持归第92包"


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包p995-p1006（12）、第79包p1007-p1014（8）、
    第80包p1015-p1026（12）、第82包body.t12.r0-r4（5）、第87包p1074-p1083（10）、
    第88包p1084-p1086（3）、第89包body.t13.r0-r5（6）、第90包p1087-p1097（11）、
    第91包body.t14.r0-r7（8）、第92包p1098-p1101（4）、第93包p1102-p1112（11）。"""
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    owned_78 = counts[PACKAGE_78_ORDINAL]
    owned_79 = counts[PACKAGE_79_ORDINAL]
    owned_80 = counts[PACKAGE_80_ORDINAL]
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
    assert set(PKG80_SPAN_REFS) <= owned_80 and len(owned_80) == 12
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


def test_owned_refs_match_frozen_package_92(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_92_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, expected in OWNED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == expected, f"{ref} 摘录与冻结计划不一致"


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    units = _frozen_unit_by_ref(plan)
    for ref, expected in ATTACHED_EXCERPT_BY_REF.items():
        assert units[ref]["excerpt"] == expected, f"{ref} 摘录与冻结计划不一致"


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    """p1098-p1101全部为paragraph；p1098/p1099位于'不良事件预期性评估'标题下；
    p1100位于'不良事件的报告'标题下；p1101位于'研究者向申办者报告不良事件等信息的
    要求与途径'标题下。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[ref], ref
        assert "安全性评估" in unit["heading_path"], ref
        assert "研究评估和程序" in unit["heading_path"], ref

    assert units["body.p1098"]["heading_path"][-1] == "不良事件预期性评估"
    assert units["body.p1099"]["heading_path"][-1] == "不良事件预期性评估"
    assert units["body.p1100"]["heading_path"][-1] == "不良事件的报告"
    assert (
        units["body.p1101"]["heading_path"][-1]
        == "研究者向申办者报告不良事件等信息的要求与途径"
    )


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    """段落摘录必须与源结构块逐段文本一致，证明无改写、无拼接错位。"""
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        assert _structure_blob_text(structure_blob, ref) == excerpts[ref], ref


# ---------------------------------------------------------------------------
# Investigator's Brochure reference & version fabrication prevention
# ---------------------------------------------------------------------------


def test_p1099_investigator_brochure_reference_preserved(config: dict) -> None:
    """p1099必须保留《研究者手册》主要参考地位，且配置显式声明不得虚构版本或条目。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1099"]
    assert "《研究者手册》" in semantics["base_rule"]
    assert "CMS-D001片" in semantics["base_rule"]
    assert "预期性" in semantics["base_rule"]

    for fragment in (
        "只确定预期性判断需参见CMS-D001片《研究者手册》",
        "不得补写版本",
        "默认最新版本",
        "凭常识判定预期/非预期",
        "把缺少手册内容改成确定结论",
    ):
        assert any(
            fragment in part
            for part in (semantics["exception_rule"], semantics["forbidden_inversion"])
        ), fragment


def test_brochure_version_fabrication_counterexamples_detected(config: dict) -> None:
    """研究者手册版本/日期/条目虚构反例必须被确定性拦截。"""
    counterexamples = [
        "评估CMS-D001片不良事件预期性见《研究者手册》第3.0版。",
        "按2023年版研究者手册评估预期性。",
        "不良事件预期性按最新版本研究者手册执行。",
        "默认当前有效版本研究者手册进行预期性判定。",
        "依据手册v2.1判定皮疹为预期不良事件。",
        "按2025版研究者手册，未列明者为非预期。",
        "默认按最新版《研究者手册》评估预期性。",
        "《研究者手册》中明确列出皮疹为预期风险，故判定为预期。",
        "手册未列入肝损，属于非预期不良反应。",
        "参照手册第4章安全信息判定预期性。",
        "对手册中列明的预期毒性判定为预期。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"手册版本/内容虚构反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# missing brochure content never turned into definite conclusion or evidence gap
# ---------------------------------------------------------------------------


def test_missing_brochure_not_turned_into_conclusion_or_evidence_gap(
    config: dict,
) -> None:
    """缺少手册内容不得改成确定预期/非预期结论或证据缺口。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1099"]
    assert "证据缺口" in semantics["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得把缺少手册内容改写成证据缺口、确定预期/非预期结论或入排门槛" in checks_blob


def test_missing_brochure_conclusion_counterexamples_detected(config: dict) -> None:
    """无手册结论化/证据缺口反例必须被确定性拦截。"""
    counterexamples = [
        "方案未提供研究者手册，判定为非预期不良事件。",
        "因缺少研究者手册，直接认定为预期不良反应。",
        "研究者手册内容未知，判定为证据缺口，不符合入选条件。",
        "由于手册信息不足，判定为研究药物非预期风险。",
        "缺少手册判定不通过筛选。",
        "方案未见手册内容判定为非预期不良事件。",
        "因缺少手册判定为非预期，需紧急上报。",
        "因手册未知直接认定非预期不良反应。",
        "缺少研究者手册直接判定为非预期风险。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"无手册结论化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# known mechanism != expectedness
# ---------------------------------------------------------------------------


def test_known_mechanism_never_substitutes_expectedness(config: dict) -> None:
    """已知性（第90/91包因果评价输入）不能替代预期性评估。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1099"]
    assert "已知作用机制" in semantics["forbidden_inversion"]
    assert "替代预期性" in semantics["forbidden_inversion"]
    note = config["later_package_boundary"]["note"]
    assert "已知性（第90/91包因果关系综合评价输入）不等于预期性" in note


def test_known_mechanism_expectedness_counterexamples_detected() -> None:
    """已知性替代预期性反例必须被确定性拦截。"""
    counterexamples = [
        "符合已知作用机制即为预期不良反应。",
        "已知不良反应等同于预期不良事件，无需查阅手册。",
        "根据已知特性直接判定为预期风险。",
        "已知作用机制替代预期性评估，判定为预期。",
        "符合已知不良反应即预期不良事件。",
        "符合已知机制即视为预期事件。",
        "符合已知作用机制即预期不良反应。",
        "符合药物已知特性即为预期不良事件。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"已知性替代预期性反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# three-dimensional separation (causality vs severity vs expectedness)
# ---------------------------------------------------------------------------


def test_three_dimensions_separation_preserved(config: dict) -> None:
    """因果关系、严重性、预期性是独立维度，不得互相推出。"""
    semantics = config["exception_semantics_by_source_ref"]["body.p1099"]
    assert "不得从因果关系或严重程度推导预期性" in semantics["forbidden_inversion"]
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "预期性、因果关系、严重性为不同维度，不得互相推出" in checks_blob


def test_dimension_conflation_counterexamples_detected() -> None:
    """因果性/严重性/预期性互推与跨维度混同反例必须被确定性拦截。"""
    conflated = [
        "因果关系为肯定有关，故判定为预期不良事件。",
        "判定为无关的不良事件即为非预期。",
        "因果相关即预期，肯定有关即预期。",
        "很可能有关即预期不良事件。",
        "因果不相关即非预期不良反应。",
        "严重不良事件即为非预期不良反应。",
        "3级严重程度不良事件自动判定为非预期。",
        "非预期不良事件判定为肯定有关。",
        "轻度不良事件即为预期。",
        "重度不良事件即非预期不良反应。",
        "发生SAE即非预期，必须立即报告。",
        "预期性即因果关系，预期即可判定相关。",
        "因果关系即预期性，不相关即非预期。",
        "严重程度即预期性，1级即预期。",
        "预期性即严重程度，非预期即严重。",
    ]
    for text in conflated:
        hits = _deterministic_hits(text)
        assert hits, f"跨维度混同反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# SUSAR three-dimensional AND conjunction
# ---------------------------------------------------------------------------


def test_susar_three_dimensional_and_conjunction_preserved(config: dict) -> None:
    """SUSAR 必须保持可疑+非预期+严重三维合取，任一单独满足均不构成 SUSAR。"""
    checks_p1018 = config["clinical_qc_checks_by_source_ref"]["body.p1018"]
    checks_blob = "\n".join(checks_p1018)
    assert "三维合取必须保持" in checks_blob
    assert "可疑（独立因果维度）+非预期+严重" in checks_blob
    assert "任一维度单独满足均不构成SUSAR" in checks_blob


def test_susar_conjunction_weakening_counterexamples_detected() -> None:
    """SUSAR 合取弱化（单独非预期/单独严重/单独相关即 SUSAR）反例必须被拦截。"""
    counterexamples = [
        "非预期不良事件即构成SUSAR，需按SUSAR上报。",
        "只要是严重不良事件即为SUSAR。",
        "因果关系相关的不良事件即为SUSAR。",
        "非预期或严重即为SUSAR，满足其一即可。",
        "严重不良反应即SUSAR，无需核对手册。",
        "非预期即可报告为SUSAR。",
        "只要相关且严重即为SUSAR，不考虑预期性。",
        "非预期不良反应即SUSAR。",
        "单独非预期即为SUSAR，直接报告。",
        "单独严重即为SUSAR，立即启动流程。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"SUSAR合取弱化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# structural headings never converted to obligations
# ---------------------------------------------------------------------------


def test_structural_headings_never_converted_to_obligations(config: dict) -> None:
    """p1098/p1100/p1101 仅作结构，不生成独立评价规则、判定门槛或报告义务。"""
    for ref in STRUCTURAL_REFS:
        semantics = config["exception_semantics_by_source_ref"][ref]
        assert "structural_only" in semantics["semantic_role"], ref
        assert "仅作结构" in semantics["exception_rule"], ref
        assert "不得" in semantics["forbidden_inversion"], ref


def test_heading_obligation_counterexamples_detected() -> None:
    """报告标题义务化反例必须被确定性拦截。"""
    counterexamples = [
        "不良事件预期性评估标题要求研究者必须在入组前完成预期性评估。",
        "不良事件的报告标题规定研究者必须填写报告表。",
        "研究者向申办者报告不良事件等信息的要求与途径规定必须通过邮件报告。",
        "不良事件预期性评估标题要求进行评价并形成正式记录。",
        "不良事件的报告标题规定报告时限为获知后立即报告。",
        "标题规定研究者报告途径为电话通知申办者。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"标题义务化反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# package 93 prevention of absorption
# ---------------------------------------------------------------------------


def test_package93_content_not_absorbed(config: dict) -> None:
    """第93包（body.p1102-p1112）具体应报告事件与24小时时限不得进入本包拥有或附加。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG93_SPAN_REFS:
        assert ref not in owned, f"{ref} 不得归入第92包拥有"
        assert ref not in attached, f"{ref} 不得归入第92包附加"


def test_package93_absorption_counterexamples_detected() -> None:
    """第93包 24 小时流程与应报告事件提前吞并反例必须被确定性拦截。"""
    counterexamples = [
        "研究者获知不良事件后24小时内向申办者报告。",
        "24小时内报告SAE给申办者和伦理委员会。",
        "随访新信息需在24小时内补充报告。",
        "填写严重不良事件报告表并于24小时内传真申办者。",
        "获知事件后启动24小时报告时钟。",
        "24小时内书面报告全部安全性信息。",
        "新信息24小时内随访并完成记录。",
        "发生不良事件后24小时内报告申办者。",
        "24小时内填写报告表并提交。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"第93包24小时流程吞并反例未被门禁拦截: {text}"


# ---------------------------------------------------------------------------
# package 80 and other neighbor prevention of absorption
# ---------------------------------------------------------------------------


def test_package80_unattached_sources_not_absorbed(config: dict) -> None:
    """第80包除 body.p1018 与 body.p1019 外的来源不得进入本包拥有或附加。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG80_UNATTACHED_REFS:
        assert ref not in owned, f"{ref} 不得进入第92包拥有"
        assert ref not in attached, f"{ref} 不得进入第92包附加"


def test_other_neighbors_not_absorbed(config: dict) -> None:
    """第78/79/82/87/88/89/90/91包仅保留所有权元数据，不进入本包拥有或附加。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
    ):
        assert ref not in owned, f"{ref} 不得进入第92包拥有"
        assert ref not in attached, f"{ref} 不得进入第92包附加"


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    expected_owners = boundary["expected_owners_by_span"]
    plan_owners: dict[str, int] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            plan_owners[u["source_ref"]] = p["package_ordinal"]

    for span_ref, expected_ordinal in expected_owners.items():
        actual_ordinal = plan_owners.get(span_ref)
        assert actual_ordinal == expected_ordinal, (
            f"span {span_ref} expected package {expected_ordinal}, got {actual_ordinal}"
        )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "第92包拥有预期性参照与报告章节入口" in note
    assert "全部零候选" in note
    assert "第80包body.p1019" in note
    assert "body.p1018" in note
    assert "已知性（第90/91包因果关系综合评价输入）不等于预期性" in note
    assert "第93包具体应报告事件类型、24小时时限与新信息随访流程" in note
    assert "不提前吞并" in note


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
    assert by_ref["body.p1098"].excerpt == "不良事件预期性评估"
    assert "CMS-D001片" in by_ref["body.p1099"].excerpt
    assert "《研究者手册》" in by_ref["body.p1099"].excerpt
    assert by_ref["body.p1100"].excerpt == "不良事件的报告"
    assert by_ref["body.p1101"].excerpt == "研究者向申办者报告不良事件等信息的要求与途径"

    # 只读闭包关键片段
    assert "SUSAR" in by_ref["body.p1018"].excerpt
    assert "可疑并且非预期的严重不良反应" in by_ref["body.p1018"].excerpt
    assert "非预期不良反应" in by_ref["body.p1019"].excerpt
    assert "性质、严重程度、后果或频率" in by_ref["body.p1019"].excerpt
    assert "主要文件" in by_ref["body.p1019"].excerpt


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

    # 相邻包除第80包p1018/p1019只读附加外，其余不得进入
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_UNATTACHED_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 4
    assert summary["attached_count"] == 2
    assert summary["unit_count"] == 6
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

    # 越界候选（把预期性参照或报告标题升格为筛选/基线控制候选）必须被拒绝
    for ref in ("body.p1098", "body.p1099", "body.p1100", "body.p1101"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对研究者手册预期性，未核对者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 即使标题使用短语探针未覆盖的同义改写，来源身份门禁仍必须拒绝候选
    paraphrased_candidates = {
        "body.p1098": "预期性章节入口作为入组前安全性掌握门槛",
        "body.p1099": "依研究者手册最新内容在基线前逐项审核不良事件风险",
        "body.p1100": "不良事件报告总要求作为受试者随访执行前置条件",
        "body.p1101": "研究者报告途径作为机构准入门槛",
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

    # 只读附加来源也是上下文，任何候选发射都必须拒绝
    for ref in ("body.p1018", "body.p1019"):
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
    for ref in OWNED_REFS:
        hits = _deterministic_hits(excerpts[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把第92包内容改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1098": [
            "筛选必做：不良事件预期性评估",
            "基线期必做：评估不良事件预期性",
            "不良事件预期性评估作为证据缺口，不得入组",
            "未完成预期性评估视为入排不通过",
        ],
        "body.p1099": [
            "筛选期必做：核对CMS-D001片《研究者手册》",
            "基线必做：依《研究者手册》完成预期性审核",
            "手册内容未知构成证据缺口，排除标准判定不通过",
            "转移所有权至第92包发布控制点",
        ],
        "body.p1100": [
            "筛选必做：不良事件报告培训",
            "基线必做：确认报告流程",
            "未建立报告途径属于证据缺口，不得入组",
            "不良事件的报告发布控制点",
        ],
        "body.p1101": [
            "筛选期必做：研究者向申办者报告不良事件途径核对",
            "基线必做：报告途径确认",
            "报告要求与途径未落实者入排不通过",
            "发布控制点：研究者报告途径",
        ],
        "body.p1018": [
            "筛选必做：SUSAR判定流程核对",
            "基线期必做：SUSAR标准确认",
            "SUSAR定义作为证据缺口，不得入组",
        ],
        "body.p1019": [
            "筛选必做：非预期不良反应定义学习",
            "基线必做：非预期定义确认",
            "非预期风险证据不足，不符合入选标准",
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


def test_prompt_excludes_neighbor_content() -> None:
    """第78/79/82/87/88/89/90/91/93包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")

    # 第82包表7继发事件规则 / 第88包严重程度 / 第89包表8 / 第87包记录规则 / 第90包因果判断 / 第91包表9
    for fragment in (
        "表 7 不良事件/反应继发事件判定原则",
        "按轻度、中度、重度三分法",
        "表 8 不良事件严重程度分级标准",
        "由于同一原因导致了受试者死亡",
        "任何因用药过量导致的不良事件",
        "按五分法将不良事件与试验用药品相关性判定结果分为",
        "表 9 不良事件与试验用药品因果关系评价",
    ):
        assert fragment not in prompt_text, f"提示不当吸入邻包内容: {fragment}"

    # 第93包24小时时钟与应报告事件
    for fragment in (
        "24小时",
        "24 小时",
        "严重不良事件报告表",
        "随访新信息",
    ):
        assert fragment not in prompt_text, f"提示不当吸入第93包报告流程: {fragment}"


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第92包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 摘录未逐字进入提示"


def test_prompt_contains_attached_sources() -> None:
    """提示必须包含只读附加来源（body.p1018 与 body.p1019）。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert excerpt in prompt_text, f"{ref} 只读附加来源未进入提示"


def test_prompt_deterministic_phrases_clean() -> None:
    """提示本身不得包含任何确定性反例措辞。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    hits = _deterministic_hits(prompt_text)
    assert hits == [], f"提示含确定性反例措辞: {hits}"


# ---------------------------------------------------------------------------
# official flow matrix & procedure catalog isolation
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package92(matrix: dict, plan: dict) -> None:
    pkg92 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL
    )
    owned_92 = {u["source_ref"] for u in pkg92["owned_units"]}
    all_refs = owned_92 | set(ATTACHED_REFS)
    for row in matrix["rows"]:
        anchor = row.get("anchor_source_ref") or ""
        assert anchor not in all_refs, f"matrix row {row.get('rule_id')} anchored in {anchor}"


def test_matrix_has_no_ae_teae_sae_rows(matrix: dict) -> None:
    for row in matrix["rows"]:
        text = " ".join(
            str(row.get(key) or "")
            for key in (
                "rule_id",
                "item_name",
                "content_expression",
                "standard_term",
                "procedure_name",
            )
        )
        assert "不良事件" not in text, f"matrix contains AE row: {row.get('rule_id')}"
        assert "TEAE" not in text, f"matrix contains TEAE row: {row.get('rule_id')}"
        assert "SAE" not in text, f"matrix contains SAE row: {row.get('rule_id')}"
        assert "预期性" not in text, f"matrix contains expectedness row: {row.get('rule_id')}"


def test_no_official_rule_anchors_package92_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg92 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_92_ORDINAL
    )
    owned_spans = {
        span_id for u in pkg92["owned_units"] for span_id in u["source_span_ids"]
    }
    for row in matrix["rows"]:
        for span_id in row.get("source_span_ids") or []:
            assert span_id not in owned_spans, (
                f"matrix rule {row.get('rule_id')} references span {span_id}"
            )


def test_procedure_catalog_has_no_ae_or_expectedness_node(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = str(item["label"])
        assert "不良事件" not in label
        assert "TEAE" not in label
        assert "SAE" not in label
        assert "预期性" not in label


def test_no_procedure_node_sourced_from_package92_or_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_spans") or []:
            span_id = span.get("span_id") or ""
            assert not span_id.startswith("body.p1098"), span_id
            assert not span_id.startswith("body.p1099"), span_id
            assert not span_id.startswith("body.p1100"), span_id
            assert not span_id.startswith("body.p1101"), span_id
            assert not span_id.startswith("body.p1018"), span_id
            assert not span_id.startswith("body.p1019"), span_id


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
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    coverage = _load_json(COVERAGE_PATH)
    assert coverage["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256

def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_91_ID in text
    assert PACKAGE_92_ID in text
    assert PACKAGE_93_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "claims_complete=false" in text
