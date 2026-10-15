#!/usr/bin/env python3
"""Slice61br model-free source-closure regressions.

Locks the D001 II package 80 ADR/SUSAR and AE collection/recording boundary
(frozen plan package 80: ADR 定义、SUSAR 三维组合、非预期性权威参照、
AE 收集期与记录义务、单一事件术语记录, body.p1015-p1026) to its
authoritative sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 80; attached refs stay read-only
- structural heading units (p1015/p1017/p1020/p1021/p1025) stay structural
  only; seven semantic units keep post_treatment_execution disposition
- no control candidate may be emitted from any owned span
- ADR causality threshold (p1016): 至少有一个合理的可能性，即不能排除
  相关性; never hardened to "必须证实因果关系" nor loosened to "任何 AE
  均与研究药物有关"; causality dimension stays separate from the SAE
  seriousness dimension (p996-p1014)
- SUSAR (p1018) is a three-dimension AND combination: 可疑 (causality) +
  非预期 (beyond existing information) + 严重 (SAE standard); never
  weakened to any single dimension
- unexpectedness (p1019) anchors on authoritative references: 《研究者
  手册》 as the primary document plus 已上市药品说明书/产品特性摘要
  (p1018); 性质、严重程度、后果或频率 comparison attributes preserved
- pre-first-dose events (p1023): ICF 后至首次服药前的临床不良医学事件
  记录为病史/伴随疾病（原始病历），不作为 AE 记录; cross-checked against
  p988/p318/p315; never recorded as AE nor upgraded to a screening gate
- AE collection window (p1022): 首次服用试验用药品后 to 最后一次安全性
  随访或者退出研究（以先发生时间为准）, consistent with p340; p1024
  separately uses 末次访视, so both source phrases stay intact without an
  unsupported equivalence, difference, or ordering inference
- single event term recording (p1026): 单一事件项中应只记录一个不良
  事件术语; this package does not invent clinical split/merge/update rules
- official matrix keeps zero rows anchored in p985-p1026 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE/TEAE/SAE node
- later packages are not absorbed: package 81 AE 记录规则 (p1027-p1032),
  packages 85-86 特殊肝功能SAE, package 90 因果关系共同判断, packages
  92-99 SAE 报告时限与流程 stay outside owned and attached closure
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package80_adr_susar_ae_collection_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61br-package80-adr-susar-ae-collection-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package80-adr-susar-ae-collection-boundary"
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
PACKAGE_80_ORDINAL = 80
PACKAGE_80_ID = "pap-bb9bf95c9cd13f15e3b737f3"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]

# 结构标题单元：仅提供章节归属，不独立形成控制点
STRUCTURAL_REFS = ["body.p1015", "body.p1017", "body.p1020", "body.p1021", "body.p1025"]
# 语义单元：保持 post_treatment_execution 处置
SEMANTIC_OWNED_REFS = ["body.p1016", "body.p1018", "body.p1019", "body.p1022", "body.p1023", "body.p1024", "body.p1026"]

# 只读闭包：前接第77包AE/TEAE定义（10）、第78包SAE定义与严重性标准（12）、
# 第79包住院除外列表续与严重性标准尾项（8）、流程/访视/监测锚点（3）、
# ICF签署锚点（1）、病史/伴随疾病收集锚点（1）
PRECEDING_PKG77_REFS = [f"body.p{ordinal}" for ordinal in range(985, 995)]
PRECEDING_PKG78_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PRECEDING_PKG79_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
ANCHOR_ATTACHED_REFS = ["body.p340", "body.p835", "body.p885"]
ICF_ANCHOR_REFS = ["body.p315"]
HISTORY_ANCHOR_REFS = ["body.p318"]
UNOWNED_CONTEXT_REFS = ["body.p315", "body.p318", "body.p340", "body.p885"]
ATTACHED_REFS = (
    PRECEDING_PKG77_REFS
    + PRECEDING_PKG78_REFS
    + PRECEDING_PKG79_REFS
    + ANCHOR_ATTACHED_REFS
    + ICF_ANCHOR_REFS
    + HISTORY_ANCHOR_REFS
)

# 后续包只读所有权元数据：body.p1027-p1032 归第81包（AE记录规则），不进提示上下文
LATER_OWNER_RANGES = {
    81: (1027, 1032),  # AE记录规则：诊断与症状、体征和检查值；医学术语优先；继发于其它事件的不良事件
}

# 各语义单元的合取/例外/限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1016": {
        "base_rule": "ADR：临床试验中发生的任何与研究药物可能有关的对人体有害或者非期望的反应；因果关系至少有一个合理的可能性，即不能排除相关性",
        "exception_rule": "因果阈值：至少有一个合理的可能性（不能排除相关性）即满足ADR的因果要求；不得把阈值改严为'必须证实因果关系'，也不得放宽为'任何AE均与研究药物有关'",
        "preserve_keywords": ["与研究药物可能有关", "对人体有害或者非期望的反应", "至少有一个合理的可能性", "不能排除相关性"],
    },
    "body.p1018": {
        "base_rule": "SUSAR指临床表现的性质和严重程度超出了试验药物《研究者手册》、已上市药品的说明书或者产品特性摘要等已有资料信息的可疑并且非预期的严重不良反应",
        "exception_rule": "三维组合必须同时满足（AND）：可疑（独立因果维度）+非预期（超出已有资料信息）+严重（符合SAE标准）；任一维度缺失即不构成SUSAR；p1018未重述可疑维度具体阈值",
        "preserve_keywords": ["可疑", "非预期", "严重", "《研究者手册》", "说明书", "产品特性摘要", "超出"],
    },
    "body.p1019": {
        "base_rule": "非预期不良反应指不良反应的性质、严重程度、后果或频率，不同于试验药物当前相关资料（如《研究者手册》等文件）所描述的预期风险；《研究者手册》作为主要文件",
        "exception_rule": "预期性参照必须锚定权威资料：《研究者手册》作为主要文件；四个比较属性（性质、严重程度、后果或频率）必须保留",
        "preserve_keywords": ["《研究者手册》", "主要文件", "性质", "严重程度", "后果", "频率", "预期风险"],
    },
    "body.p1022": {
        "base_rule": "不良事件收集期应从参与者首次服用试验用药品后至最后一次安全性随访或者退出研究为止（以先发生时间为准）",
        "exception_rule": "收集期起点=首次服用试验用药品后；终点=最后一次安全性随访或者退出研究（以先发生时间为准）；与p340一致；p1024另用末次访视表述，分别保留且不无据推断关系",
        "preserve_keywords": ["首次服用试验用药品后", "最后一次安全性随访", "退出研究", "以先发生时间为准"],
    },
    "body.p1023": {
        "base_rule": "在签署知情同意书后到首次服用试验用药品之前发生的临床不良医学事件作为病史/伴随疾病记录在原始病历中，不作为AE记录",
        "exception_rule": "给药前事件路由：ICF后至首次服药前的临床不良医学事件记录为病史/伴随疾病（原始病历），不作为AE记录；与p988/p318/p315共同界定给药前记录边界",
        "preserve_keywords": ["签署知情同意书后", "首次服用试验用药品之前", "病史/伴随疾病", "原始病历", "不作为AE记录"],
    },
    "body.p1024": {
        "base_rule": "从首次服用试验用药品至末次访视期间发生的所有AE均需记录在eCRF中",
        "exception_rule": "记录义务：'所有AE'均需记录在eCRF中，原文上界为末次访视；与p1022表述分别保留且不无据推断关系",
        "preserve_keywords": ["首次服用试验用药品", "末次访视", "所有AE", "eCRF"],
    },
    "body.p1026": {
        "base_rule": "研究者在记录不良事件时应使用正确的医学术语/概念，避免使用口语和缩略语，在eCRF不良事件页的单一事件项中应只记录一个不良事件术语",
        "exception_rule": "单一事件项只记录一个AE术语；本条不定义临床事件拆分、合并或诊断更新规则",
        "preserve_keywords": ["正确的医学术语", "避免使用口语和缩略语", "单一事件项中应只记录一个不良事件术语"],
    },
}

# 交叉验证锚点（只读闭包）
AE_DEFINITION_REF = "body.p986"  # 接受试验用药品之后出现…但不一定与试验用药品有因果关系
TEAE_DEFINITION_REF = "body.p994"  # 给药后出现…治疗前并未出现或相对治疗前恶化
SAE_DEFINITION_REF = "body.p996"  # 接受试验用药品后…严重不良事件
SAE_OR_HEAD_REF = "body.p997"  # 符合下列标准任何一项
IMPORTANT_EVENT_REF = "body.p1014"  # 医学和科学的判断
AE_RECORD_START_REF = "body.p340"  # 不良事件于D1启动给药后开始记录，直至末次安全性随访或者退出研究为止
PRE_ICF_HISTORY_REF = "body.p988"  # 知情同意前已存在→病史/伴随疾病
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
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL
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
    assert config["group_id"] == "d001-ii-package80-adr-susar-ae-collection-boundary"
    assert config["task_id"] == "phase5-slice61br-20260830"
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
    assert structural == set(STRUCTURAL_REFS), "结构标题单元必须标注为仅结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS), "第80包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第80包不发射任何候选"
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
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL
    )
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_80), "attached refs must not be owned by package 80"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 35


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
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        for paragraph in range(start, end + 1):
            ref = f"body.p{paragraph}"
            assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第77包拥有p985-p994（10），第78包拥有p995-p1006（12），
    第79包拥有p1007-p1014（8），第80包拥有p1015-p1026（12），第81包拥有p1027-p1032（6）。"""
    pkg77 = next(p for p in plan["packages"] if p["package_ordinal"] == 77)
    pkg78 = next(p for p in plan["packages"] if p["package_ordinal"] == 78)
    pkg79 = next(p for p in plan["packages"] if p["package_ordinal"] == 79)
    pkg80 = next(p for p in plan["packages"] if p["package_ordinal"] == 80)
    pkg81 = next(p for p in plan["packages"] if p["package_ordinal"] == 81)
    owned_77 = {u["source_ref"] for u in pkg77["owned_units"]}
    owned_78 = {u["source_ref"] for u in pkg78["owned_units"]}
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    owned_81 = {u["source_ref"] for u in pkg81["owned_units"]}
    assert set(PRECEDING_PKG77_REFS) <= owned_77 and len(owned_77) == 10
    assert set(PRECEDING_PKG78_REFS) <= owned_78 and len(owned_78) == 12
    assert set(PRECEDING_PKG79_REFS) <= owned_79 and len(owned_79) == 8
    assert "body.p1015" in owned_80 and "body.p1026" in owned_80 and len(owned_80) == 12
    assert "body.p1027" in owned_81 and "body.p1032" in owned_81 and len(owned_81) == 6


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_80(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_80_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1015"] == "药物不良反应（ADR）"
    assert excerpts["body.p1016"] == (
        "药物不良反应（Adverse Drug Reaction，ADR）：指临床试验中发生的任何与研究药物"
        "可能有关的对人体有害或者非期望的反应。研究药物与AE之间的因果关系至少有一个"
        "合理的可能性，即不能排除相关性。"
    )
    assert excerpts["body.p1017"] == "可疑且非预期严重不良反应（SUSAR）"
    assert excerpts["body.p1018"] == (
        "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，"
        "SUSAR）指临床表现的性质和严重程度超出了试验药物《研究者手册》、已上市药品的"
        "说明书或者产品特性摘要等已有资料信息的可疑并且非预期的严重不良反应。"
    )
    assert excerpts["body.p1019"] == (
        "非预期不良反应指不良反应的性质、严重程度、后果或频率，不同于试验药物当前"
        "相关资料（如《研究者手册》等文件）所描述的预期风险。《研究者手册》作为主要"
        "文件提供用以判断某不良反应是否预期或非预期的安全性参考信息。"
    )
    assert excerpts["body.p1020"] == "不良事件的收集和记录"
    assert excerpts["body.p1021"] == "不良事件的收集"
    assert excerpts["body.p1022"] == (
        "本试验中，不良事件收集期应从参与者首次服用试验用药品后至最后一次安全性随访"
        "或者退出研究为止（以先发生时间为准）。"
    )
    assert excerpts["body.p1023"] == (
        "在签署知情同意书后到首次服用试验用药品之前，发生的临床不良医学事件作为"
        "病史/伴随疾病记录在原始病历中，不作为AE记录。"
    )
    assert excerpts["body.p1024"] == (
        "从首次服用试验用药品至末次访视期间发生的所有AE均需记录在eCRF中。"
    )
    assert excerpts["body.p1025"] == "不良事件的记录与规定"
    assert excerpts["body.p1026"] == (
        "研究者在记录不良事件时应使用正确的医学术语/概念，避免使用口语和缩略语，"
        "在eCRF不良事件页的单一事件项中应只记录一个不良事件术语。"
    )


# ---------------------------------------------------------------------------
# structural-only heading units
# ---------------------------------------------------------------------------


def test_structural_headings_are_title_only(config: dict, plan: dict) -> None:
    """结构标题单元的摘录必须与其章节标题一致，不含可形成控制点的正文。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    structural_excerpts = {
        "body.p1015": "药物不良反应（ADR）",
        "body.p1017": "可疑且非预期严重不良反应（SUSAR）",
        "body.p1020": "不良事件的收集和记录",
        "body.p1021": "不良事件的收集",
        "body.p1025": "不良事件的记录与规定",
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
# later-package read-only ownership metadata: p1027-p1032 stays with package 81
# ---------------------------------------------------------------------------


def test_later_package_boundary_spans_not_absorbed(config: dict) -> None:
    """第81包AE记录规则（p1027-p1032）不得进入本包拥有或只读闭包。"""
    boundary = config["later_package_boundary"]
    expected_later = {
        f"body.p{ordinal}" for ordinal in range(1027, 1033)
    }
    assert set(boundary["expected_owners_by_span"]) == expected_later
    assert boundary["expected_owners_by_span"] == {
        f"body.p{ordinal}": 81 for ordinal in range(1027, 1033)
    }
    assert expected_later.isdisjoint(set(config["owned_source_refs"])), (
        "第81包AE记录规则不得被第80包拥有"
    )
    assert expected_later.isdisjoint(set(config["attached_source_refs"])), (
        "第81包AE记录规则不得进入本包只读闭包（最小闭包，无文本依赖）"
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
        assert expected_ordinal != PACKAGE_80_ORDINAL, f"{ref} 不得归第80包"


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in ("第81包", "body.p1027", "p1032", "吞并", "第85", "第90", "第92", "24小时报告"):
        assert fragment in note, f"边界注记缺少不得提前吞并声明: {fragment}"


def test_package81_record_rules_stay_out_of_package80(plan: dict) -> None:
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL
    )
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    assert "body.p1027" not in owned_80
    assert "body.p1030" not in owned_80
    assert "body.p1032" not in owned_80


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
    assert "至少有一个合理的可能性" in by_ref["body.p1016"].excerpt
    assert "不能排除相关性" in by_ref["body.p1016"].excerpt
    assert "可疑并且非预期的严重不良反应" in by_ref["body.p1018"].excerpt
    assert "《研究者手册》" in by_ref["body.p1018"].excerpt
    assert "主要文件" in by_ref["body.p1019"].excerpt
    assert "最后一次安全性随访" in by_ref["body.p1022"].excerpt
    assert "退出研究" in by_ref["body.p1022"].excerpt
    assert "病史/伴随疾病" in by_ref["body.p1023"].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt
    assert "末次访视" in by_ref["body.p1024"].excerpt
    assert "所有AE" in by_ref["body.p1024"].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref["body.p1026"].excerpt

    # 只读闭包关键片段
    assert "但不一定与试验用药品有因果关系" in by_ref[AE_DEFINITION_REF].excerpt
    assert "给药后" in by_ref[TEAE_DEFINITION_REF].excerpt
    assert "接受试验用药品后" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "任何一项" in by_ref[SAE_OR_HEAD_REF].excerpt
    assert "医学和科学的判断" in by_ref[IMPORTANT_EVENT_REF].excerpt
    assert "末次安全性随访或者退出研究" in by_ref[AE_RECORD_START_REF].excerpt
    assert "病史/伴随疾病" in by_ref[PRE_ICF_HISTORY_REF].excerpt
    assert "开始任何试验流程之前签署知情同意书" in by_ref[ICF_SIGNING_REF].excerpt
    assert "既往和现病史收集" in by_ref[HISTORY_COLLECTION_REF].excerpt
    assert "病史/伴随疾病" in by_ref[HISTORY_COLLECTION_REF].excerpt
    assert "D1给药前结果作为基线值" in by_ref["body.p885"].excerpt
    assert "记录合并用药及不良事件" in by_ref["body.p885"].excerpt
    assert "整个研究过程要严密监测" in by_ref["body.p835"].excerpt


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
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 35
    assert summary["unit_count"] == 47
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

    # 越界候选（把ADR定义升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1016"]],
                "title": "既往药物反应史纳入筛选必查，证据不足者入排不通过",
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
    """确定性门禁必须拒绝把ADR/SUSAR/AE收集记录改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.p1016": [
            "筛选时评估既往药物反应史，无反应证据者视为证据缺口",
            "基线期完成药物不良反应评估，未完成者不得入组",
            "药物反应史不符合者按排除标准判定入排不通过",
        ],
        "body.p1018": [
            "筛选时评估SUSAR风险史，否则视为证据不足",
            "SUSAR相关评估未完成者不得入组",
        ],
        "body.p1022": [
            "筛选时核对AE收集期安排，未安排者证据缺口不得入组",
            "基线期完成AE收集期确认，未确认者入排不通过",
        ],
        "body.p1023": [
            "筛选时收集首次服药前不良医学事件史，遗漏者视为证据缺口",
            "给药前事件记录不完整者按排除标准判定不通过",
            "基线期完成给药前事件核验，未完成者不得入组",
        ],
        "body.p1024": [
            "筛选时确认eCRF记录安排，未确认者不得入组",
        ],
        "body.p1026": [
            "筛选时考核医学术语记录能力，不合格者按排除标准判定不通过",
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
    """ADR阈值/SUSAR三维/预期性参照/收集窗口/病史路由/术语记录的限定关键词必须逐条保留。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、参照或路由的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1016": "ADR指与研究药物有关的对人体有害的反应。",
        "body.p1018": "性质或严重程度超出已有资料的可疑且非预期的严重不良反应。",
        "body.p1019": "非预期不良反应指不良反应不同于当前资料所描述的预期风险。",
        "body.p1022": "AE收集期自首次服药后至末次访视为止。",
        "body.p1023": "首次服药前发生的临床不良医学事件按AE记录。",
        "body.p1024": "首次服药后发生的AE需记录在eCRF中。",
        "body.p1026": "记录AE时使用医学术语。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 限定丢失反例未被门禁拦截"
        )


# ---------------------------------------------------------------------------
# ADR causality threshold (p1016)
# ---------------------------------------------------------------------------


def test_adr_causality_reasonable_possibility_threshold(
    config: dict, plan: dict
) -> None:
    """ADR因果阈值：至少一个合理的可能性（不能排除相关性），不得改严或放宽。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1016"]
    for fragment in ("与研究药物可能有关", "对人体有害或者非期望的反应", "至少有一个合理的可能性", "不能排除相关性"):
        assert fragment in excerpt, f"p1016 丢失因果阈值片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1016"]
    assert "至少有一个合理的可能性" in entry["preserve_keywords"]
    assert "不能排除相关性" in entry["preserve_keywords"]

    hardened = [
        "ADR指已证实与研究药物有因果关系的反应。",
        "ADR仅指被证实由研究药物引起的反应。",
    ]
    loosened = [
        "ADR指与研究药物可能有关或无关的任何反应。",
        "任何AE均与研究药物有关，均记录为ADR。",
    ]
    for text in hardened + loosened:
        assert _missing_exception_keywords(text, entry), f"因果阈值反例未被拦截: {text}"


def test_causality_dimension_stays_separate_from_seriousness(
    config: dict,
) -> None:
    """因果维度（p1016）与严重性维度（p996-p1014）是不同分类轴。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    adr = by_ref["body.p1016"].excerpt
    sae_def = by_ref[SAE_DEFINITION_REF].excerpt
    sae_head = by_ref[SAE_OR_HEAD_REF].excerpt

    # 严重性定义不携带因果性判断；ADR定义不携带严重性判定
    assert "因果关系" in adr
    assert "因果关系" not in sae_def and "因果关系" not in sae_head
    assert "严重不良事件" not in adr
    assert "接受试验用药品后" in sae_def
    # AE 定义明确与因果关系无关
    assert "但不一定与试验用药品有因果关系" in by_ref[AE_DEFINITION_REF].excerpt


def test_adr_non_desired_wording_is_not_regulatory_unexpectedness(
    config: dict,
) -> None:
    """p1016一般含义的“非期望”不得替代p1019基于权威资料的“非预期”判定。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    assert "有害或者非期望的反应" in by_ref["body.p1016"].excerpt
    assert "非预期不良反应" in by_ref["body.p1019"].excerpt
    assert "《研究者手册》作为主要文件" in by_ref["body.p1019"].excerpt
    inversion = config["exception_semantics_by_source_ref"]["body.p1016"][
        "forbidden_inversion"
    ]
    assert "非期望" in inversion and "非预期" in inversion
    assert "直接等同" in inversion


# ---------------------------------------------------------------------------
# SUSAR three-dimension AND (p1018)
# ---------------------------------------------------------------------------


def test_susar_three_dimension_and_combination(config: dict, plan: dict) -> None:
    """SUSAR必须是可疑+非预期+严重三维同时满足，不得弱化为任一维度。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1018"]
    for fragment in ("可疑", "非预期", "严重", "《研究者手册》", "说明书", "产品特性摘要", "超出"):
        assert fragment in excerpt, f"p1018 丢失三维组合片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1018"]
    assert "AND" in entry["exception_rule"]
    assert "任一维度缺失即不构成SUSAR" in entry["exception_rule"]
    assert "未重述可疑维度的具体因果阈值" in entry["exception_rule"]

    weakened = [
        "非预期且严重的反应即SUSAR。",  # 丢失可疑维度
        "可疑且严重的反应即SUSAR。",  # 丢失非预期维度
        "可疑且非预期的反应即SUSAR。",  # 丢失严重维度
        "性质或严重程度超出现有资料的严重反应按SUSAR报告。",  # 丢失可疑+非预期完整限定
        "任何严重不良反应均按SUSAR处理。",  # 丢失可疑+非预期
    ]
    for text in weakened:
        assert _missing_exception_keywords(text, entry), f"SUSAR弱化反例未被拦截: {text}"


def test_susar_serious_dimension_anchors_sae_standard(config: dict) -> None:
    """SUSAR的'严重'维度承接SAE标准（p996-p1014），严重性与因果维度分离。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    assert "严重不良反应" in by_ref["body.p1018"].excerpt
    assert "接受试验用药品后" in by_ref[SAE_DEFINITION_REF].excerpt
    assert "任何一项" in by_ref[SAE_OR_HEAD_REF].excerpt
    # 严重性标准尾项（p1014）只保留医学和科学判断，不提前等同于SUSAR定义
    assert "医学和科学的判断" in by_ref[IMPORTANT_EVENT_REF].excerpt


# ---------------------------------------------------------------------------
# unexpectedness authority reference (p1019)
# ---------------------------------------------------------------------------


def test_unexpectedness_anchors_authoritative_reference(config: dict, plan: dict) -> None:
    """非预期性必须锚定《研究者手册》主要文件及四个比较属性。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1019"]
    for fragment in ("《研究者手册》", "主要文件", "性质", "严重程度", "后果", "频率", "预期风险"):
        assert fragment in excerpt, f"p1019 丢失预期性参照片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1019"]
    assert "主要文件" in entry["preserve_keywords"]

    reference_free = [
        "非预期不良反应指不良反应的性质或频率不同于预期。",
        "研究者判断不良反应为非预期的即可报告。",
        "非预期不良反应指任何罕见的不良反应。",
    ]
    for text in reference_free:
        assert _missing_exception_keywords(text, entry), f"无参照反例未被拦截: {text}"


def test_unexpectedness_reference_sources_cross_check(config: dict) -> None:
    """p1018与p1019共同给出非预期性参照：研究者手册+说明书+产品特性摘要。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    susar = by_ref["body.p1018"].excerpt
    unexpected = by_ref["body.p1019"].excerpt
    assert "《研究者手册》" in susar and "《研究者手册》" in unexpected
    assert "说明书" in susar and "产品特性摘要" in susar
    assert "主要文件" in unexpected
    # 非预期性不等于严重性：p1019不包含严重性判定用语
    assert "严重不良反应" not in unexpected


# ---------------------------------------------------------------------------
# pre-first-dose history routing (p1023)
# ---------------------------------------------------------------------------


def test_pre_first_dose_events_route_to_history_not_ae(
    config: dict, plan: dict
) -> None:
    """ICF后至首次服药前的临床不良医学事件记录为病史/伴随疾病，不作为AE。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1023"]
    for fragment in ("签署知情同意书后", "首次服用试验用药品之前", "病史/伴随疾病", "原始病历", "不作为AE记录"):
        assert fragment in excerpt, f"p1023 丢失给药前事件路由片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1023"]

    recorded_as_ae = [
        "签署知情同意书后至首次服药前发生的临床不良医学事件按AE记录。",
        "首次服药前发生的任何不良医学事件均记录为AE。",
        "ICF后至首次服药前的临床事件在eCRF中按不良事件收集。",
    ]
    for text in recorded_as_ae:
        assert _missing_exception_keywords(text, entry), f"给药前事件记为AE反例未被拦截: {text}"


def test_pre_dose_history_chain_consistent(config: dict) -> None:
    """给药前记录边界链：ICF签署（p315）→知情同意前已存在（p988）→ICF后至首次服药前（p1023）→病史/伴随疾病收集（p318）。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    assert "开始任何试验流程之前签署知情同意书" in by_ref[ICF_SIGNING_REF].excerpt
    assert "病史/伴随疾病" in by_ref[PRE_ICF_HISTORY_REF].excerpt
    assert "知情同意前已存在" in by_ref[PRE_ICF_HISTORY_REF].excerpt
    assert "病史/伴随疾病" in by_ref[HISTORY_COLLECTION_REF].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt
    # 给药前事件路由不得改写为AE收集义务或筛选/基线门槛
    assert config["required_candidate_source_refs"] == []
    assert "body.p1023" in config["forbidden_candidate_source_refs"]


# ---------------------------------------------------------------------------
# AE collection window (p1022) vs eCRF recording upper bound (p1024)
# ---------------------------------------------------------------------------


def test_ae_collection_window_anchors(config: dict, plan: dict) -> None:
    """AE收集期：首次服药后至最后一次安全性随访或退出研究（以先发生为准）。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1022"]
    for fragment in ("首次服用试验用药品后", "最后一次安全性随访", "退出研究", "以先发生时间为准"):
        assert fragment in excerpt, f"p1022 丢失收集期锚点片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1022"]

    window_drift = [
        "AE收集期自签署知情同意书起至最后一次安全性随访为止。",
        "AE收集期自筛选起至末次访视为止。",
        "AE收集期自首次服药后至末次访视为止。",
        "AE收集期终点为退出研究后30天。",
    ]
    for text in window_drift:
        assert _missing_exception_keywords(text, entry), f"收集期漂移反例未被拦截: {text}"


def test_collection_window_consistent_with_flow_note(config: dict) -> None:
    """p1022收集期与p340流程表注记交叉验证：终点均为最后一次安全性随访或退出研究。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    window = by_ref["body.p1022"].excerpt
    flow_note = by_ref[AE_RECORD_START_REF].excerpt
    # p1022 使用"最后一次安全性随访"，p340 使用"末次安全性随访"（同一锚点的两种措辞）
    assert "最后一次安全性随访" in window
    assert "末次安全性随访" in flow_note
    assert "退出研究" in window and "退出研究" in flow_note
    assert "以先发生时间为准" in window and "以先发生时间为准" in flow_note


def test_collection_and_recording_phrases_stay_separate_without_inference(
    config: dict, plan: dict
) -> None:
    """分别保留p1022与p1024原文，不擅自判定两种表述等同、不同或先后。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    collection = excerpts["body.p1022"]
    recording = excerpts["body.p1024"]

    assert "最后一次安全性随访" in collection
    assert "末次访视" in recording
    assert "末次访视" not in collection, "p1022必须保留自身终点表述"
    assert "最后一次安全性随访" not in recording, "p1024必须保留自身上界表述"

    entry_collection = config["exception_semantics_by_source_ref"]["body.p1022"]
    entry_recording = config["exception_semantics_by_source_ref"]["body.p1024"]
    assert "不得在缺少定义证据时擅自判定二者等同、不同或先后关系" in entry_collection[
        "exception_rule"
    ]
    assert "不得在缺少定义证据时擅自合并或推断二者关系" in entry_recording[
        "exception_rule"
    ]

    conflated = [
        "AE收集期自首次服药后至末次访视为止。",
        "从首次服用试验用药品至最后一次安全性随访期间的所有AE记录在eCRF中。",
        "末次安全随访即末次访视，收集与记录窗口相同。",
    ]
    for text in conflated:
        assert _missing_exception_keywords(text, entry_collection) or _missing_exception_keywords(
            text, entry_recording
        ), f"窗口混同反例未被拦截: {text}"


def test_post_dose_all_ae_ecrf_recording_preserved(config: dict, plan: dict) -> None:
    """p1024：首次服药至末次访视期间'所有AE'记录在eCRF，全量义务不得丢失。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1024"]
    for fragment in ("首次服用试验用药品", "末次访视", "所有AE", "eCRF"):
        assert fragment in excerpt, f"p1024 丢失记录义务片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1024"]
    dropped = [
        "首次服药后发生的AE需记录在eCRF中。",
        "末次访视期间发生的严重AE记录在eCRF中。",
    ]
    for text in dropped:
        assert _missing_exception_keywords(text, entry), f"记录义务丢失反例未被拦截: {text}"


# ---------------------------------------------------------------------------
# single event term recording (p1026)
# ---------------------------------------------------------------------------


def test_single_event_term_recording(config: dict, plan: dict) -> None:
    """只锁定单个eCRF事件项一术语，不越权定义临床事件拆分、合并或更新。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1026"]
    for fragment in ("正确的医学术语", "避免使用口语和缩略语", "单一事件项中应只记录一个不良事件术语"):
        assert fragment in excerpt, f"p1026 丢失术语记录片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1026"]

    assert "单一事件项只记录一个AE术语" in entry["exception_rule"]
    assert "不定义临床事件应如何拆分、合并或在诊断明确后更新" in entry[
        "exception_rule"
    ]
    assert "不得把本条扩写为临床事件拆分、合并或诊断更新规则" in entry[
        "forbidden_inversion"
    ]
    invalid_item = "一个事件项中记录多个不良事件术语。"
    assert _missing_exception_keywords(invalid_item, entry), "单个事件项多术语反例未被拦截"


def test_single_event_term_does_not_emit_any_candidate(config: dict) -> None:
    """术语记录规范是记录质量规则，不构成筛选/基线控制候选。"""
    assert "body.p1026" in config["forbidden_candidate_source_refs"]
    assert config["required_candidate_source_refs"] == []
    assert config["expected_disposition_by_source_ref"]["body.p1026"] == "post_treatment_execution"


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p985-p1026, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg80["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第80包拥有来源为锚点"
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
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1032:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package80_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_80_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg80["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第80包拥有来源为锚点"
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
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1032:
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
    assert PACKAGE_80_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "至少有一个合理的可能性" in text
    assert "不能排除相关性" in text
    assert "三维" in text and "AND" in text
    assert "《研究者手册》" in text and "主要文件" in text
    assert "病史/伴随疾病" in text
    assert "最后一次安全性随访" in text and "末次访视" in text
    assert "单一事件项" in text and "只记录一个" in text
    assert "body.p1027" in text and "body.p1032" in text
    assert "第81包" in text and "第85" in text and "第90" in text and "第92" in text
    assert "24小时报告" in text
    assert "父级盲态检查清单" in text
