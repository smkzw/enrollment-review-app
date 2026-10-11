#!/usr/bin/env python3
"""Slice61bp model-free source-closure regressions.

Locks the D001 II package 78 SAE definition / seriousness-standard / 
hospitalization-exception boundary (frozen plan package 78: SAE 定义、任一
严重性标准、住院不作为SAE的除外列表及研究者综合判断引导句,
body.p995-p1006) to its authoritative sources before any semantic replay
decision:

- config contract and role partition
- owned refs == frozen plan package 78; attached refs stay read-only
- no control candidate may be emitted from any owned span
- SAE definition, each seriousness standard and the hospitalization
  exceptions must never be upgraded into screening/baseline mandatory
  duties, evidence gaps, or enrollment-fail conditions (deterministic
  forbidden-marker gate)
- OR semantics of "符合下列标准任何一项" (body.p997) preserved: any single
  seriousness criterion suffices; never rewritten as "all criteria met"
- per-standard guards preserved: 死亡以事件结果为判据 (p998, 不得与死亡原因
  混淆), 危及生命反事实限定 (p999, 并不是指"如果更严重可能导致死亡"),
  轻微功能干扰"不构成重大干扰" (p1000), 住院因果限定"由于不良事件所致，
  而非因择期手术、非医疗原因" (p1001)
- investigator comprehensive judgment (p1002 "可根据研究者综合判断不作为
  SAE") is a judgment right, never an automatic waiver nor a mandatory gate
- continuous hospitalization-exception list: p1003-p1006 (package 78) +
  p1007-p1012 (package 79) must not be truncated at body.p1006; later
  boundary body.p1007-p1026 stays owned by packages 79-80 (79: p1007-p1014,
  80: p1015-p1026), never absorbed by package 78
- official matrix keeps zero rows anchored in p985-p1026 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE/TEAE/SAE node
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package78_sae_seriousness_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bp-package78-sae-seriousness-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package78-sae-seriousness-boundary"
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
PACKAGE_78_ORDINAL = 78
PACKAGE_78_ID = "pap-d01122f016611fda097bbad0"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
TITLE_REFS = ["body.p995"]
DEFINITION_REFS = [f"body.p{ordinal}" for ordinal in range(996, 1007)]

# 只读闭包：前接第77包（10）、流程/访视/监测锚点（3）、后续第79-80包（20）
PRECEDING_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(985, 995)]
ANCHOR_ATTACHED_REFS = ["body.p340", "body.p835", "body.p885"]
UNOWNED_CONTEXT_REFS = ["body.p340", "body.p885"]
LATER_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1027)]
ATTACHED_REFS = (
    PRECEDING_ATTACHED_REFS + ANCHOR_ATTACHED_REFS + LATER_ATTACHED_REFS
)

# 后续包只读边界：body.p1007-p1026 归第79-80包所有（按冻结计划实际所有权）
LATER_BOUNDARY_FIRST = "body.p1007"
LATER_BOUNDARY_LAST = "body.p1026"
LATER_OWNER_RANGES = {
    79: (1007, 1014),  # 住院除外列表续及严重性标准尾项（先天异常/出生缺陷、重要医学事件）
    80: (1015, 1026),  # ADR、SUSAR定义及AE收集与记录边界
}

# 连续住院除外列表：p1002引导句（研究者综合判断）承接 p1003-p1006（第78包）
# 与 p1007-p1012（第79包），跨包连续，不得在 p1006 截断
LIST_HEAD_REF = "body.p1002"
LIST_FIRST_PKG78_REF = "body.p1003"
LIST_LAST_PKG78_REF = "body.p1006"
LIST_FIRST_PKG79_REF = "body.p1007"
LIST_LAST_PKG79_REF = "body.p1012"

# SAE判定总纲与各项严重性标准的合取/例外/限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p996": {
        "base_rule": "严重不良事件指参与者接受试验用药品后出现的死亡、危及生命、永久或者严重的残疾或者功能丧失、需要住院治疗或者延长住院时间、先天性异常或者出生缺陷等不良医学事件",
        "exception_rule": "五项后果为概括性列举，具体判据由p997-p1014逐条展开",
        "preserve_keywords": ["接受试验用药品后", "危及生命", "永久或者严重的残疾或者功能丧失", "需要住院治疗或者延长住院时间", "先天性异常或者出生缺陷"],
    },
    "body.p997": {
        "base_rule": "严重不良事件是指符合下列标准任何一项的不良事件",
        "exception_rule": "OR语义：任一严重性标准满足即构成SAE",
        "preserve_keywords": ["任何一项", "符合下列标准"],
    },
    "body.p998": {
        "base_rule": "导致死亡：当一个事件的结果为死亡",
        "exception_rule": "以事件结果为判据，不得与死亡原因混淆",
        "preserve_keywords": ["结果", "死亡", "明确地"],
    },
    "body.p999": {
        "base_rule": "危及生命：发生不良事件时参与者已经处于死亡的危险中",
        "exception_rule": "反事实限定：并不是指假设该不良事件如果更严重可能导致死亡",
        "preserve_keywords": ["已经处于死亡的危险中", "并不是指", "如果更严重"],
    },
    "body.p1000": {
        "base_rule": "永久或者严重的残疾或者功能丧失：对正常生活和活动造成严重不便或干扰",
        "exception_rule": "相对较小医学意义的经历不构成重大干扰",
        "preserve_keywords": ["严重不便或干扰", "不构成重大干扰", "相对较小医学意义"],
    },
    "body.p1001": {
        "base_rule": "需要住院治疗或延长住院时间：不良事件导致住院或延长住院",
        "exception_rule": "因果限定：由于不良事件所致，而非因择期手术、非医疗原因等导致入院",
        "preserve_keywords": ["由于不良事件所致", "择期手术", "非医疗原因"],
    },
    "body.p1002": {
        "base_rule": "以下住院情况可根据研究者综合判断不作为SAE",
        "exception_rule": "研究者综合判断是判定权，不是自动豁免；列表延续至第79包p1007-p1012",
        "preserve_keywords": ["研究者综合判断", "不作为SAE"],
    },
    "body.p1003": {
        "base_rule": "24小时内出院的留院观察",
        "exception_rule": "时限限定：24小时内出院",
        "preserve_keywords": ["24小时内", "留院观察"],
    },
    "body.p1004": {
        "base_rule": "住院进行门诊常规检查（住院时间少于24小时）",
        "exception_rule": "双重限定：门诊常规检查且住院时间少于24小时",
        "preserve_keywords": ["门诊常规检查", "少于24小时"],
    },
    "body.p1005": {
        "base_rule": "社会原因住院：如患者因无人照料或医保报销等",
        "exception_rule": "非医疗原因住院，与p1001因果限定互为镜像",
        "preserve_keywords": ["社会原因", "无人照料", "医保报销"],
    },
    "body.p1006": {
        "base_rule": "在康复机构、疗养院住院",
        "exception_rule": "场所限定；列表以分号结尾并延续至第79包",
        "preserve_keywords": ["康复机构", "疗养院"],
    },
}

# SAE锚点交叉验证（只读闭包）
SAE_ANCHOR_REF = "body.p996"  # 接受试验用药品后
AE_DEFINITION_REF = "body.p986"  # 接受试验用药品之后（第77包）
AE_RECORD_START_REF = "body.p340"  # 不良事件于D1启动给药后开始记录
AE_WINDOW_REF = "body.p1022"  # 首次服药后至末次安全性随访
PLANNED_HOSPITALIZATION_AE_EXCEPTION_REF = "body.p989"  # 第77包：计划住院/手术AE记录除外


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL
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
    assert config["group_id"] == "d001-ii-package78-sae-seriousness-boundary"
    assert config["task_id"] == "phase5-slice61bp-20260830"
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
    assert structural == set(TITLE_REFS), "仅SAE定义标题为结构性单元"
    assert forbidden == set(OWNED_REFS), "第78包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第78包不发射任何候选"
    assert structural <= owned
    assert required.isdisjoint(forbidden)

    # 仅结构标题不需要伪装成语义处置；其余拥有单元落入治疗期SAE分类语义。
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in OWNED_REFS if ref not in TITLE_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：SAE定义/严重性标准/住院除外的禁止升格措辞必须已写入配置
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
        assert len(entry["preserve_keywords"]) >= 2, ref


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg78 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL
    )
    owned_78 = {u["source_ref"] for u in pkg78["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_78), "attached refs must not be owned by package 78"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 33


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，p1007-p1026 保持归第79-80包。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PRECEDING_ATTACHED_REFS:
        assert owners.get(ref) == [77], f"{ref} 必须保持归第77包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        for paragraph in range(start, end + 1):
            ref = f"body.p{paragraph}"
            assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第79包拥有p1007-p1014（8），第80包拥有p1015-p1026（12）。"""
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == 79
    )
    pkg80 = next(
        p for p in plan["packages"] if p["package_ordinal"] == 80
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    assert "body.p1007" in owned_79 and "body.p1012" in owned_79
    assert "body.p1014" in owned_79 and len(owned_79) == 8
    assert "body.p1025" in owned_80 and "body.p1026" in owned_80
    assert len(owned_80) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_78(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_78_ID
    assert plan["plan_id"] == PLAN_ID
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p995"] == "严重不良事件（SAE）"
    assert excerpts["body.p996"] == (
        "严重不良事件，指参与者接受试验用药品后出现死亡、危及生命、永久或者严重"
        "的残疾或者功能丧失、参与者需要住院治疗或者延长住院时间，以及先天性异常"
        "或者出生缺陷等不良医学事件。"
    )
    assert excerpts["body.p997"] == (
        "严重不良事件（Serious Adverse Event，SAE）是指符合下列标准任何一项的"
        "不良事件："
    )
    assert excerpts["body.p998"] == (
        "导致死亡：当一个事件的结果为“死亡”，则可明确地作为严重不良事件进行记录"
        "和报告。"
    )
    assert excerpts["body.p999"] == (
        "危及生命：在此是指在发生不良事件时参与者已经处于死亡的危险中，并不是指"
        "假设该不良事件如果更严重可能导致死亡。"
    )
    assert excerpts["body.p1000"] == (
        "永久或者严重的残疾或者功能丧失：指不良事件结果可能对参与者正常生活和活动"
        "造成严重不便或干扰。相对较小医学意义的经历，如单纯的头痛、恶心、呕吐、"
        "腹泻、流感和意外创伤（如脚踝扭伤），这些经历可能干扰或阻碍日常生活功能，"
        "但不构成重大干扰。"
    )
    assert excerpts["body.p1001"] == (
        "需要住院治疗或延长住院时间^*：不良事件导致参与者不得不住院接受治疗或本"
        "来已经准备出院但由于发生了不良事件而导致住院时间延长；需明确导致该状况的"
        "原因是由于不良事件所致，而非因择期手术、非医疗原因等导致入院。"
    )
    assert excerpts["body.p1002"] == "*以下住院情况可根据研究者综合判断不作为SAE："
    assert excerpts["body.p1003"] == "24小时内出院的留院观察；"
    assert excerpts["body.p1004"] == "住院进行门诊常规检查（住院时间少于24小时）；"
    assert excerpts["body.p1005"] == "社会原因住院：如患者因无人照料或医保报销等；"
    assert excerpts["body.p1006"] == "在康复机构、疗养院住院；"


# ---------------------------------------------------------------------------
# later-package read-only boundary: p1007-p1026 stays with packages 79-80
# ---------------------------------------------------------------------------


def test_later_package_boundary_contiguous(config: dict) -> None:
    boundary = config["later_package_boundary"]
    spans = set(boundary["expected_owners_by_span"])
    expected = {
        f"body.p{ordinal}"
        for ordinal in range(1007, 1027)
    }
    assert spans == expected, "后续包边界必须精确覆盖 body.p1007-p1026"
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
        assert expected_ordinal != PACKAGE_78_ORDINAL, f"{ref} 不得归第78包"


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
    assert set(by_ordinal) == {79, 80}


def test_later_package_definition_heads_stay_out_of_package_78(plan: dict) -> None:
    """住院除外列表续起于 body.p1007，不得被第78包提前吞并。"""
    pkg78 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL
    )
    owned_78 = {u["source_ref"] for u in pkg78["owned_units"]}
    assert "body.p1007" not in owned_78
    assert "body.p1013" not in owned_78
    assert "body.p1015" not in owned_78
    assert "body.p1026" not in owned_78


def test_later_boundary_note_documents_continuous_list(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "body.p1026" in note
    assert "截断" in note, "边界注记必须声明连续列表不得在p1006截断"


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
    assert "接受试验用药品后" in by_ref["body.p996"].excerpt
    assert "任何一项" in by_ref["body.p997"].excerpt
    assert "结果" in by_ref["body.p998"].excerpt and "死亡" in by_ref["body.p998"].excerpt
    assert "已经处于死亡的危险中" in by_ref["body.p999"].excerpt
    assert "并不是指" in by_ref["body.p999"].excerpt
    assert "不构成重大干扰" in by_ref["body.p1000"].excerpt
    assert "由于不良事件所致" in by_ref["body.p1001"].excerpt
    assert "研究者综合判断" in by_ref["body.p1002"].excerpt
    assert "留院观察" in by_ref["body.p1003"].excerpt
    assert "少于24小时" in by_ref["body.p1004"].excerpt
    assert "社会原因" in by_ref["body.p1005"].excerpt
    assert "康复机构" in by_ref["body.p1006"].excerpt

    for ref in PRECEDING_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip()
    assert "不良事件于D1启动给药后开始记录" in by_ref["body.p340"].excerpt
    assert "整个研究过程要严密监测" in by_ref["body.p835"].excerpt
    assert "D1给药前结果作为基线值" in by_ref["body.p885"].excerpt
    assert "同时需要记录合并用药及不良事件" in by_ref["body.p885"].excerpt
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip(), f"{ref} 只读闭包来源为空"
    assert "择期手术治疗" in by_ref["body.p1007"].excerpt
    assert "疗效评价" in by_ref["body.p1008"].excerpt
    assert "规定疗程" in by_ref["body.p1009"].excerpt
    assert "方案规定的计划住院" in by_ref["body.p1010"].excerpt
    assert "非不良事件导致的择期手术" in by_ref["body.p1011"].excerpt
    assert "全面体格检查" in by_ref["body.p1012"].excerpt
    assert "先天性异常或者出生缺陷" in by_ref["body.p1013"].excerpt
    assert "医学和科学的判断" in by_ref["body.p1014"].excerpt
    assert "首次服用试验用药品后" in by_ref["body.p1022"].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt


def test_sae_anchor_chain_consistent(config: dict) -> None:
    """SAE锚点链：SAE(接受试验用药品后)-AE(服药后)-记录起点(D1给药后)-收集窗口(首次服药后)。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    assert "接受试验用药品后" in by_ref[SAE_ANCHOR_REF]
    assert "接受试验用药品之后" in by_ref[AE_DEFINITION_REF]
    assert "D1启动给药后开始记录" in by_ref[AE_RECORD_START_REF]
    assert "首次服用试验用药品后" in by_ref[AE_WINDOW_REF]


def test_d1_pre_dose_eligibility_review_does_not_move_ae_record_start(
    config: dict,
) -> None:
    """D1给药前入排复核与给药后AE/SAE记录是相邻但独立的控制。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    pre_dose = by_ref["body.p885"]
    record_start = by_ref[AE_RECORD_START_REF]

    assert "D1给药前结果作为基线值" in pre_dose
    assert "基线需再次审查入选和排除标准" in pre_dose
    assert "D1启动给药后开始记录" in record_start
    assert "给药前开始记录" not in record_start

    # 第78包只负责SAE判定分类，不得因附带的给药前复核来源而发射入排候选。
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
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 33
    assert summary["unit_count"] == 45
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

    # 越界候选（把SAE严重性标准升格为控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1001"]],
                "title": "住院史与SAE判定合并为筛选必查",
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
    """确定性门禁必须拒绝把SAE定义/严重性标准/住院除外改写为筛选/基线门槛的反例。"""
    markers = config["candidate_forbidden_markers_by_source_ref"]["body.p1001"]

    counterexamples = [
        "筛选时评估既往住院史作为SAE风险证据，否则视为证据缺口",
        "筛选期住院情况须完成必做核验，不符合者不得入组",
        "受试者曾因非医疗原因住院者按排除标准判定不通过",
        "基线期存在危及生命风险史者入排不通过",
        "筛选发现的残疾或功能丧失属于证据不足，禁止入组",
        "SAE判定标准作为基线期必做检查项目执行",
    ]
    for text in counterexamples:
        assert _forbidden_marker_hits(text, markers), f"门禁未拦截: {text}"

    legitimate = [
        "严重不良事件，指参与者接受试验用药品后出现死亡、危及生命、永久或者严重的"
        "残疾或者功能丧失、参与者需要住院治疗或者延长住院时间，以及先天性异常或者"
        "出生缺陷等不良医学事件。",
        "严重不良事件（Serious Adverse Event，SAE）是指符合下列标准任何一项的"
        "不良事件：",
        "导致死亡：当一个事件的结果为“死亡”，则可明确地作为严重不良事件进行记录"
        "和报告。",
        "危及生命：在此是指在发生不良事件时参与者已经处于死亡的危险中，并不是指"
        "假设该不良事件如果更严重可能导致死亡。",
        "相对较小医学意义的经历，如单纯的头痛、恶心、呕吐、腹泻、流感和意外创伤"
        "（如脚踝扭伤），这些经历可能干扰或阻碍日常生活功能，但不构成重大干扰。",
        "需明确导致该状况的原因是由于不良事件所致，而非因择期手术、非医疗原因等"
        "导致入院。",
        "*以下住院情况可根据研究者综合判断不作为SAE：",
        "24小时内出院的留院观察；",
        "住院进行门诊常规检查（住院时间少于24小时）；",
        "社会原因住院：如患者因无人照料或医保报销等；",
        "在康复机构、疗养院住院；",
    ]
    for text in legitimate:
        assert _forbidden_marker_hits(text, markers) == [], f"误拦截合法定义: {text}"


# ---------------------------------------------------------------------------
# deterministic exception/conjunction semantics gate (合取/例外/限定语义)
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """SAE定义/严重性标准/住院除外的合取、例外与限定关键词必须逐条保留在冻结来源中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失OR语义、反事实/因果限定、研究者综合判断的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p996": "严重不良事件指参与者接受试验用药品后出现的所有不良医学事件。",
        "body.p997": "严重不良事件是指符合下列全部标准的不良事件。",
        "body.p998": "导致死亡：死亡原因已确认者作为严重不良事件记录。",
        "body.p999": "危及生命：指该不良事件如果更严重可能导致死亡。",
        "body.p1000": "永久或者严重的残疾或者功能丧失：指不良事件结果可能对参与者正常生活造成干扰。",
        "body.p1001": "需要住院治疗或延长住院时间：参与者住院治疗即可作为SAE判定。",
        "body.p1002": "以下住院情况一律不作为SAE：",
        "body.p1003": "留院观察不作为SAE。",
        "body.p1004": "住院进行常规检查不作为SAE。",
        "body.p1005": "住院情况不作为SAE。",
        "body.p1006": "在康复机构住院不作为SAE。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 例外/限定丢失反例未被门禁拦截"
        )


def test_any_criterion_or_semantics_preserved(config: dict, plan: dict) -> None:
    """p997 的OR语义：'符合下列标准任何一项'必须保留，不得改为全部标准同时满足。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p997"]
    assert "任何一项" in excerpt and "符合下列标准" in excerpt
    assert "全部标准" not in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p997"]
    for keyword in ("任何一项", "符合下列标准"):
        assert keyword in entry["preserve_keywords"]


def test_hospitalization_causal_qualification_preserved(config: dict, plan: dict) -> None:
    """p1001 的因果限定：住院必须由不良事件所致，而非择期手术/非医疗原因。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1001"]
    for fragment in ("由于不良事件所致", "择期手术", "非医疗原因"):
        assert fragment in excerpt, f"p1001 丢失因果限定片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1001"]
    for keyword in ("由于不良事件所致", "择期手术", "非医疗原因"):
        assert keyword in entry["preserve_keywords"]


def test_investigator_judgment_not_automatic_waiver(config: dict, plan: dict) -> None:
    """p1002 的研究者综合判断：列表各项是判断候选项，不是自动豁免。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1002"]
    assert "研究者综合判断" in excerpt and "不作为SAE" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1002"]
    assert "研究者综合判断" in entry["preserve_keywords"]
    assert "自动豁免" in entry["forbidden_inversion"]
    assert "截断" in entry["forbidden_inversion"]


def test_seriousness_standard_guards_preserved(config: dict, plan: dict) -> None:
    """p998/p999/p1000 标准内限定：死亡以结果判据、危及生命反事实限定、轻微干扰不构成重大干扰。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert "结果" in excerpts["body.p998"] and "死亡" in excerpts["body.p998"]
    assert "已经处于死亡的危险中" in excerpts["body.p999"]
    assert "并不是指" in excerpts["body.p999"] and "如果更严重" in excerpts["body.p999"]
    assert "严重不便或干扰" in excerpts["body.p1000"]
    assert "不构成重大干扰" in excerpts["body.p1000"]
    assert "脚踝扭伤" in excerpts["body.p1000"]


# ---------------------------------------------------------------------------
# continuous hospitalization-exception list across packages 78-79
# ---------------------------------------------------------------------------


def test_hospitalization_exception_list_continuous_across_packages(
    config: dict, plan: dict
) -> None:
    """p1002引导句承接的住院除外列表跨第78-79包连续，不得在p1006截断。"""
    excerpts = _owned_excerpt_by_ref(plan, config)

    # 第78包拥有的列表项以分号结尾，表示列表延续（p1006 不是列表终点）
    assert excerpts[LIST_LAST_PKG78_REF].rstrip().endswith("；")
    assert excerpts[LIST_HEAD_REF] == "*以下住院情况可根据研究者综合判断不作为SAE："

    # 第79包拥有列表延续项必须实际进入只读闭包
    attached = set(config["attached_source_refs"])
    for ordinal in range(1007, 1013):
        ref = f"body.p{ordinal}"
        assert ref in attached, f"{ref} 必须进入只读闭包以保持连续列表"
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == 79
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    assert LIST_FIRST_PKG79_REF in owned_79 and LIST_LAST_PKG79_REF in owned_79

    # 连续列表在p1012以句号收尾；跨包完整，语义上是一个整体
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    assert by_ref[LIST_LAST_PKG79_REF].rstrip().endswith("。")
    # 引导句（p1002）不得被当作独立完整列表
    assert LIST_LAST_PKG78_REF != LIST_HEAD_REF


def test_p1011_and_p1012_remain_separate_alternatives_in_one_list(
    config: dict,
) -> None:
    """跨段的“或”连接相邻备选项，不得把两个来源单元合并成一个条件。"""
    from slice59n_representative_group_control_replay import _resolve_units

    rows = {row.source_ref: row for row in _resolve_units(config)}
    assert rows["body.p1011"].structure_unit_id != rows["body.p1012"].structure_unit_id
    assert rows["body.p1011"].excerpt.rstrip().endswith("；")
    assert rows["body.p1012"].excerpt.lstrip().startswith("或")


def test_planned_hospitalization_ae_exception_not_confused_with_sae_list(
    config: dict, plan: dict
) -> None:
    """第77包AE记录除外（p989计划住院）与SAE住院除外（p1001-p1012）语义层次不同。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    ae_exception = by_ref[PLANNED_HOSPITALIZATION_AE_EXCEPTION_REF]
    assert "计划的住院/手术" in ae_exception
    assert "加重" in ae_exception
    # SAE住院除外以研究者综合判断为引导，两者不得互相替换
    sae_list_head = by_ref[LIST_HEAD_REF]
    assert "研究者综合判断" in sae_list_head
    assert "计划的住院" not in sae_list_head


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p985-p1026, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg78 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg78["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第78包拥有来源为锚点"
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


def test_no_official_rule_anchors_package78_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg78 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg78["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第78包拥有来源为锚点"
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
    assert PACKAGE_78_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "研究者综合判断" in text
    assert "任何一项" in text
    assert "由于不良事件所致" in text
    assert "不构成重大干扰" in text
    assert "截断" in text
    assert "body.p1007" in text and "body.p1026" in text
    assert "79-80" in text
    assert "父级盲态检查清单" in text
