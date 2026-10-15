#!/usr/bin/env python3
"""Slice61bo model-free source-closure regressions.

Locks the D001 II package 77 AE/TEAE definition and pre-dose history boundary
(frozen plan package 77: AE 定义 / 五类不作为AE记录的除外情形 / TEAE 定义,
body.p985-p994) to its authoritative sources before any semantic replay
decision:

- config contract and role partition
- owned refs == frozen plan package 77; attached refs stay read-only
- no control candidate may be emitted from any owned span
- AE definition, the five AE-recording exceptions and the TEAE definition must
  never be upgraded into screening/baseline mandatory duties, evidence gaps, or
  enrollment-fail conditions (deterministic forbidden-marker gate)
- conjunctive/exception semantics preserved per ref: 计划住院/手术 (除非…加重),
  侵入性检查 (但…疾病可能为AE), 疾病预期进展 (除非…高于预期), 既存波动
  (预期周期性波动但并未恶化), plus the TEAE post-dose anchor and the
  ICH E9 治疗前并未出现/恶化 anchor; 知情同意前已存在与给药前事件
  记录为病史/伴随疾病, 不作为AE (p988/p1023)
- later-package read-only boundary: body.p995-p1026 stays owned by packages
  78-80 (78: p995-p1006, 79: p1007-p1014, 80: p1015-p1026), never absorbed by
  package 77; boundary extends to p1026 per the real frozen plan
- official matrix keeps zero rows anchored in p985-p1026 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE/TEAE/SAE node and already covers
  既往和现病史 at screening + baseline stages
- workflow stages keep D1 pre-dose distinct from the baseline visit
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package77_ae_teae_history_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bo-package77-ae-teae-history-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package77-ae-teae-history-boundary"
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
PACKAGE_77_ORDINAL = 77
PACKAGE_77_ID = "pap-11233226bef34c28a4a2e05c"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(985, 995)]
TITLE_REFS = ["body.p985", "body.p993"]
DEFINITION_REFS = ["body.p986", "body.p987", "body.p988", "body.p989",
                   "body.p990", "body.p991", "body.p992", "body.p994"]

# 只读闭包：前接第76包（5）、流程/访视/监测锚点（4）、后续第78-80包（32）
PRECEDING_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(980, 985)]
ANCHOR_ATTACHED_REFS = ["body.p318", "body.p340", "body.p835", "body.p885"]
UNOWNED_CONTEXT_REFS = ["body.p318", "body.p340", "body.p885"]
LATER_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1027)]
ATTACHED_REFS = (
    PRECEDING_ATTACHED_REFS + ANCHOR_ATTACHED_REFS + LATER_ATTACHED_REFS
)

# 后续包只读边界：body.p995-p1026 归第78-80包所有（按冻结计划实际所有权）
LATER_BOUNDARY_FIRST = "body.p995"
LATER_BOUNDARY_LAST = "body.p1026"
LATER_OWNER_RANGES = {
    78: (995, 1006),  # SAE定义、严重性标准及住院除外列表
    79: (1007, 1014),  # 住院除外列表续及严重性标准
    80: (1015, 1026),  # ADR、SUSAR定义及AE收集与记录边界（含p1025-p1026）
}

# 五类AE记录除外情形 + TEAE定义的合取/例外语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p988": {
        "base_rule": "筛选时发现的已存在的情况不作为AE记录",
        "exception_rule": "经研究者判断该异常在参与者知情同意前已存在时记录为病史/伴随疾病",
        "preserve_keywords": ["病史/伴随疾病", "知情同意前已存在", "研究者判断"],
    },
    "body.p989": {
        "base_rule": "计划的住院/手术不作为AE记录",
        "exception_rule": "除非计划住院/手术的情况较原有情况加重",
        "preserve_keywords": ["计划的住院/手术", "加重"],
    },
    "body.p990": {
        "base_rule": "内科和外科侵入性检查不作为AE记录",
        "exception_rule": "但导致需实施这些检查的疾病可能为不良事件",
        "preserve_keywords": ["侵入性检查", "肝脏活检", "疾病可能为不良事件"],
    },
    "body.p991": {
        "base_rule": "研究的疾病预期进展不作为AE记录",
        "exception_rule": "除非严重程度或发生频率高于预期",
        "preserve_keywords": ["预期进展", "高于预期"],
    },
    "body.p992": {
        "base_rule": "既存伴随疾病或原有症状体征预期周期性波动不作为AE记录",
        "exception_rule": "合取限定：且并未恶化",
        "preserve_keywords": ["预期", "周期性波动", "并未恶化"],
    },
    "body.p994": {
        "base_rule": "TEAE指给药后出现的任何不利的医学事件",
        "exception_rule": "ICH E9：治疗前并未出现或相对于治疗前发生恶化",
        "preserve_keywords": ["给药后", "治疗前并未出现", "恶化"],
    },
}

# 给药前后锚点交叉验证（只读闭包）
HISTORY_BOUNDARY_REF = "body.p988"  # 知情同意前已存在 → 病史/伴随疾病
PRE_DOSE_HISTORY_REF = "body.p1023"  # 知情同意后至首次给药前 → 病史/伴随疾病
AE_WINDOW_REF = "body.p1022"  # 首次服药后至末次安全性随访
AE_RECORD_START_REF = "body.p340"  # 不良事件于D1启动给药后开始记录


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL
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


@pytest.fixture(scope="module")
def structure_by_ref() -> dict:
    blocks = _load_json(STRUCTURE_BLOB_PATH)
    return {block["source_ref"]: block for block in blocks}


# ---------------------------------------------------------------------------
# config contract
# ---------------------------------------------------------------------------


def test_config_contract(config: dict) -> None:
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["group_id"] == "d001-ii-package77-ae-teae-history-boundary"
    assert config["task_id"] == "phase5-slice61bo-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 10

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(TITLE_REFS), "仅两个定义标题为结构性单元"
    assert forbidden == set(OWNED_REFS), "第77包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第77包不发射任何候选"
    assert structural <= owned
    assert required.isdisjoint(forbidden)

    # 两个结构标题不需要伪装成语义处置；其余拥有单元落入治疗期记录范围语义。
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in OWNED_REFS if ref not in TITLE_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：AE/TEAE定义及五类除外情形的禁止升格措辞必须已写入配置
    for ref in OWNED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {"筛选必做", "基线必做", "证据缺口", "不得入组", "排除标准", "入排不通过"} <= set(
            markers
        ), ref
    assert config["candidate_required_markers_by_source_ref"] == {}

    # 合取/例外语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(EXCEPTION_SEMANTICS_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 2, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg77 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL
    )
    owned_77 = {u["source_ref"] for u in pkg77["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_77), "attached refs must not be owned by package 77"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 41


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，p995-p1026 保持归第78-80包。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PRECEDING_ATTACHED_REFS:
        assert owners.get(ref) == [76], f"{ref} 必须保持归第76包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        for paragraph in range(start, end + 1):
            ref = f"body.p{paragraph}"
            assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"


def test_later_boundary_covers_p1025_p1026_against_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第80包拥有 p1015-p1026（含p1025-p1026）。

    该断言只冻结本包所需的完整后续定义边界，不反推其他包必须装入同一范围。
    """
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == 80
    )
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    assert "body.p1025" in owned_80
    assert "body.p1026" in owned_80
    assert len(owned_80) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_77(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_77_ID
    assert plan["plan_id"] == PLAN_ID
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p985"] == "不良事件（AE）"
    assert excerpts["body.p986"] == (
        "不良事件（AE）指临床试验参与者在接受试验用药品之后出现的所有不良医学"
        "事件，可以表现为症状体征、疾病和/或有临床意义的实验室检查异常，但不一"
        "定与试验用药品有因果关系。"
    )
    assert excerpts["body.p987"] == "但下列情况不应作为AE记录："
    assert excerpts["body.p988"] == (
        "筛选时发现的已存在的情况（例如筛选时实验室检查、心电图检查、生命体征、"
        "体格检查等结果显示具有临床意义的异常，但经由研究者判断该异常在参与者知"
        "情同意前已存在）；该种情况应作为病史/伴随疾病进行记录。"
    )
    assert excerpts["body.p989"] == "计划的住院/手术；除非计划住院/手术的情况较原有情况加重。"
    assert excerpts["body.p990"] == (
        "内科和外科侵入性检查（如肝脏活检、内镜检查等）；但导致需实施这些检查的"
        "疾病可能为不良事件。"
    )
    assert excerpts["body.p991"] == (
        "研究的疾病预期进展和/或研究疾病的症状与体征出现预期进展；除非严重程度或"
        "发生频率高于预期。"
    )
    assert excerpts["body.p992"] == (
        "筛选时已存在的伴随疾病或原有症状、体征等出现预期的周期性波动，但并未恶化。"
    )
    assert excerpts["body.p993"] == "治疗期出现的不良事件（TEAE）"
    assert excerpts["body.p994"] == (
        "治疗期出现的不良事件（TEAE）是指在给药后出现的任何不利的医学事件。ICH E9"
        " 指南“临床试验统计原则”将“治疗期不良事件”定义为：“在治疗过程中出现的事件，"
        "在治疗前并未出现或相对于治疗前发生恶化”。"
    )


# ---------------------------------------------------------------------------
# later-package read-only boundary: p995-p1026 stays with packages 78-80
# ---------------------------------------------------------------------------


def test_later_package_boundary_contiguous(config: dict) -> None:
    boundary = config["later_package_boundary"]
    spans = set(boundary["expected_owners_by_span"])
    expected = {
        f"body.p{ordinal}"
        for ordinal in range(995, 1027)
    }
    assert spans == expected, "后续包边界必须精确覆盖 body.p995-p1026"
    assert spans <= set(config["attached_source_refs"]), (
        "只读所有权元数据不等于来源闭包；后续定义必须实际进入提示上下文"
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
        assert expected_ordinal != PACKAGE_77_ORDINAL, f"{ref} 不得归第77包"


def test_later_package_boundary_ranges_match_semantics(config: dict) -> None:
    boundary = config["later_package_boundary"]
    by_ordinal: dict[int, set[str]] = {}
    for ref, ordinal in boundary["expected_owners_by_span"].items():
        by_ordinal.setdefault(ordinal, set()).add(ref)
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        expected = {f"body.p{i}" for i in range(start, end + 1)}
        assert by_ordinal.get(ordinal) == expected, (
            f"第{ordinal}包边界与配置语义区间不一致"
        )
    assert set(by_ordinal) == {78, 79, 80}


def test_later_package_definition_heads_stay_out_of_package_77(plan: dict) -> None:
    """SAE定义起于 body.p995，不得被第77包提前吞并。"""
    pkg77 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL
    )
    owned_77 = {u["source_ref"] for u in pkg77["owned_units"]}
    assert "body.p995" not in owned_77
    assert "body.p1002" not in owned_77
    assert "body.p1022" not in owned_77
    assert "body.p1026" not in owned_77


def test_later_boundary_note_documents_current_package_scope(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "body.p1026" in note
    assert "不反推" not in note


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
    assert "接受试验用药品之后" in by_ref["body.p986"].excerpt
    assert "不应作为AE记录" in by_ref["body.p987"].excerpt
    assert "病史/伴随疾病" in by_ref["body.p988"].excerpt
    assert "计划的住院/手术" in by_ref["body.p989"].excerpt
    assert "加重" in by_ref["body.p989"].excerpt
    assert "侵入性检查" in by_ref["body.p990"].excerpt
    assert "疾病可能为不良事件" in by_ref["body.p990"].excerpt
    assert "预期进展" in by_ref["body.p991"].excerpt
    assert "高于预期" in by_ref["body.p991"].excerpt
    assert "并未恶化" in by_ref["body.p992"].excerpt
    assert "给药后" in by_ref["body.p994"].excerpt
    assert "治疗前并未出现" in by_ref["body.p994"].excerpt

    for ref in PRECEDING_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip()
    assert "既往和现病史收集" in by_ref["body.p318"].excerpt
    assert "不良事件于D1启动给药后开始记录" in by_ref["body.p340"].excerpt
    assert "整个研究过程要严密监测" in by_ref["body.p835"].excerpt
    assert "D1给药前结果作为基线值" in by_ref["body.p885"].excerpt
    assert "同时需要记录合并用药及不良事件" in by_ref["body.p885"].excerpt
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip(), f"{ref} 只读闭包来源为空"
    assert "严重不良事件" in by_ref["body.p996"].excerpt
    assert "不作为SAE" in by_ref["body.p1002"].excerpt
    assert "首次服用试验用药品后" in by_ref["body.p1022"].excerpt
    assert "首次服用试验用药品之前" in by_ref["body.p1023"].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt
    assert "所有AE均需记录" in by_ref["body.p1024"].excerpt


def test_pre_post_dose_anchor_chain_consistent(config: dict) -> None:
    """给药前后锚点链：AE(服药后)-TEAE(给药后)-收集窗口(首次服药后)-给药前病史。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    assert "接受试验用药品之后" in by_ref["body.p986"]
    assert "给药后" in by_ref["body.p994"]
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF]
    assert "首次服用试验用药品后" in by_ref[AE_WINDOW_REF]
    assert "首次服用试验用药品之前" in by_ref[PRE_DOSE_HISTORY_REF]
    assert "不作为AE记录" in by_ref[PRE_DOSE_HISTORY_REF]
    assert "病史/伴随疾病" in by_ref[HISTORY_BOUNDARY_REF]


def test_d1_pre_dose_eligibility_review_does_not_move_ae_record_start(
    config: dict,
) -> None:
    """D1给药前入排复核与给药后AE记录是相邻但独立的控制。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    pre_dose = by_ref["body.p885"]
    record_start = by_ref[AE_RECORD_START_REF]

    assert "D1给药前结果作为基线值" in pre_dose
    assert "基线需再次审查入选和排除标准" in pre_dose
    assert "D1启动给药后开始记录" in record_start
    assert "给药前开始记录" not in record_start

    # 第77包只负责AE/TEAE记录范围，不得因附带的给药前复核来源而发射入排候选。
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(OWNED_REFS)
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}


def test_prepare_evidence_contains_real_later_package_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含后续定义，不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in ANCHOR_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 41
    assert summary["unit_count"] == 51
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

    # 越界候选（把AE定义升格为控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p986"]],
                "title": "筛选时异常作为AE判定",
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
    """确定性门禁必须拒绝把AE/TEAE定义或记录除外改写为筛选/基线门槛的反例。"""
    markers = config["candidate_forbidden_markers_by_source_ref"]["body.p986"]

    counterexamples = [
        "筛选时发现的临床意义异常应在筛选期作为必做检查完成，否则视为证据缺口",
        "知情同意前已存在的异常属于证据缺口，入排不通过",
        "计划住院情况未加重者不符合入选标准",
        "疾病预期进展未超预期者按排除标准判定不通过",
        "给药前发生的事件按TEAE记录并作为基线期必做判定",
        "筛选发现的异常不得入组，须按AE登记",
    ]
    for text in counterexamples:
        assert _forbidden_marker_hits(text, markers), f"门禁未拦截: {text}"

    legitimate = [
        "不良事件（AE）指临床试验参与者在接受试验用药品之后出现的所有不良医学"
        "事件，可以表现为症状体征、疾病和/或有临床意义的实验室检查异常，但不一"
        "定与试验用药品有因果关系。",
        "但下列情况不应作为AE记录：",
        "筛选时发现的已存在的情况（例如筛选时实验室检查、心电图检查、生命体征、"
        "体格检查等结果显示具有临床意义的异常，但经由研究者判断该异常在参与者知"
        "情同意前已存在）；该种情况应作为病史/伴随疾病进行记录。",
        "计划的住院/手术；除非计划住院/手术的情况较原有情况加重。",
        "内科和外科侵入性检查（如肝脏活检、内镜检查等）；但导致需实施这些检查的"
        "疾病可能为不良事件。",
        "研究的疾病预期进展和/或研究疾病的症状与体征出现预期进展；除非严重程度或"
        "发生频率高于预期。",
        "筛选时已存在的伴随疾病或原有症状、体征等出现预期的周期性波动，但并未恶化。",
        "治疗期出现的不良事件（TEAE）是指在给药后出现的任何不利的医学事件。",
        "在签署知情同意书后到首次服用试验用药品之前，发生的临床不良医学事件作为"
        "病史/伴随疾病记录在原始病历中，不作为AE记录。",
    ]
    for text in legitimate:
        assert _forbidden_marker_hits(text, markers) == [], f"误拦截合法定义: {text}"


# ---------------------------------------------------------------------------
# deterministic exception/conjunction semantics gate (合取/例外语义)
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """五类除外情形与TEAE定义的合取/例外关键词必须逐条保留在冻结来源中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失例外条款/合取限定的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p988": "筛选时发现的已存在的情况应作为病史进行记录。",
        "body.p989": "计划的住院/手术不作为AE记录。",
        "body.p990": "内科和外科侵入性检查不作为AE记录。",
        "body.p991": "研究的疾病预期进展不作为AE记录。",
        "body.p992": "筛选时已存在的伴随疾病或原有症状、体征等出现预期的周期性波动。",
        "body.p994": "治疗期出现的不良事件是指在给药后出现的任何不利的医学事件。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 例外丢失反例未被门禁拦截"
        )


def test_conjunctive_guard_requires_both_expected_and_not_worsened(
    config: dict, plan: dict
) -> None:
    """p992 的合取语义：'预期周期性波动' 与 '并未恶化' 必须同时成立。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p992"]
    assert "预期" in excerpt and "并未恶化" in excerpt
    # 任一限定丢失即不构成完整合取
    assert "恶化" in excerpt and "预期" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p992"]
    for keyword in ("预期", "周期性波动", "并未恶化"):
        assert keyword in entry["preserve_keywords"]


def test_teae_anchor_fragments_preserved(config: dict, plan: dict) -> None:
    """TEAE 定义必须同时保留给药后锚点与 ICH E9 恶化锚点。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p994"]
    for fragment in ("给药后", "治疗前并未出现", "恶化"):
        assert fragment in excerpt, f"TEAE 定义丢失锚点片段: {fragment}"


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p985-p1026, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg77 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg77["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第77包拥有来源为锚点"
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
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1026:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package77_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg77 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg77["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第77包拥有来源为锚点"
            )


# ---------------------------------------------------------------------------
# frozen procedure catalog: no AE/TEAE/SAE node; history collection covered
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


def test_procedure_catalog_covers_history_collection_stages(
    procedure_catalog: dict,
) -> None:
    """p988/p992'记录为病史/伴随疾病'的收集义务已由流程目录在筛选与基线发布。"""
    nodes = _catalog_nodes(procedure_catalog, "既往和现病史")
    assert len(nodes) == 3
    stages = sorted(n["review_stage"] for n in nodes)
    assert stages == ["baseline", "baseline", "screening"], stages


def test_no_procedure_node_sourced_from_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1026:
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
    assert PACKAGE_77_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "病史/伴随疾病" in text
    assert "给药后" in text
    assert "除非" in text
    assert "并未恶化" in text
    assert "body.p995" in text and "body.p1026" in text
    assert "78-80" in text
    assert "父级盲态检查清单" in text
