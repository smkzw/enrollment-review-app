#!/usr/bin/env python3
"""Slice61bq model-free source-closure regressions.

Locks the D001 II package 79 SAE tail-boundary (frozen plan package 79:
SAE 住院不作为SAE除外列表续、先天性异常或者出生缺陷、其他有重要意义的
医学事件及其医学和科学判断, body.p1007-p1014) to its authoritative
sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 79; attached refs stay read-only
- no control candidate may be emitted from any owned span
- hospitalization exceptions (p1007-p1012), congenital anomaly / birth
  defect (p1013) and other medically important events (p1014) must never
  be upgraded into screening/baseline mandatory duties, evidence gaps, or
  enrollment-fail conditions (deterministic forbidden-marker gate)
- continuous hospitalization-exception list: head body.p1002 (package 78)
  + list items p1003-p1006 (package 78) + p1007-p1012 (package 79) must
  not be truncated at body.p1006; each item stays an investigator-judgment
  candidate, never an automatic waiver nor a mandatory gate
- body.p1011 and body.p1012 stay two independent source units and adjacent
  alternatives ("或" connector), never merged into one atomic condition;
  "非不良事件导致" (p1011) mirrors the p1001 "由于不良事件所致" causal
  qualification
- body.p1013 stays a seriousness criterion judged on the participant's
  offspring ("参与者的后代"); never inverted into reproductive
  inclusion/exclusion criteria
- body.p1014 keeps the medical and scientific judgment ("必须运用医学和
  科学的判断决定是否对其他的情况加速报告") and the prevention-of-serious-
  consequences conditional ("如需要采取医学措施来预防如上情形之一的
  发生，也通常被视为是严重的"); never simplified to "any abnormality",
  never stripped of the judgment, never weakened; "加速报告" stays this
  package's judgment outcome and is not absorbed into package 80's
  ADR/SUSAR or reporting obligations
- OR semantics of "符合下列标准任何一项" (body.p997, attached) preserved:
  p1013/p1014 are tail items where any single criterion suffices
- official matrix keeps zero rows anchored in p996-p1026 and zero 不良事件 /
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package79_sae_tail_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bq-package79-sae-tail-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package79-sae-tail-boundary"
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
PACKAGE_79_ORDINAL = 79
PACKAGE_79_ID = "pap-5fbec1c2327b345382aa22d6"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]

# 只读闭包：前接第78包SAE定义/严重性标准/住院除外引导句（11）、流程/访视/监测锚点（3）、
# 同词异域锚点（6）、后续第80包ADR/SUSAR与AE收集记录（12）
PRECEDING_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(996, 1007)]
ANCHOR_ATTACHED_REFS = ["body.p340", "body.p835", "body.p885"]
DOMAIN_SEPARATION_ATTACHED_REFS = [
    "body.p327",
    "body.p638",
    "body.p645",
    "body.p661",
    "body.p696",
    "body.p816",
]
UNOWNED_CONTEXT_REFS = ["body.p327", "body.p340", "body.p885"]
LATER_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
ATTACHED_REFS = (
    PRECEDING_ATTACHED_REFS
    + ANCHOR_ATTACHED_REFS
    + DOMAIN_SEPARATION_ATTACHED_REFS
    + LATER_ATTACHED_REFS
)

# 后续包只读边界：body.p1015-p1026 归第80包所有（按冻结计划实际所有权）
LATER_BOUNDARY_FIRST = "body.p1015"
LATER_BOUNDARY_LAST = "body.p1026"
LATER_OWNER_RANGES = {
    80: (1015, 1026),  # ADR、SUSAR定义及AE收集与记录边界
}

# 连续住院除外列表：p1002引导句（第78包）承接 p1003-p1006（第78包）
# 与 p1007-p1012（第79包），跨包连续，不得在 p1006 截断
LIST_HEAD_REF = "body.p1002"
LIST_FIRST_PKG78_REF = "body.p1003"
LIST_LAST_PKG78_REF = "body.p1006"
LIST_FIRST_PKG79_REF = "body.p1007"
LIST_LAST_PKG79_REF = "body.p1012"
LIST_ITEMS_PKG79_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1013)]

# 各拥有单元的合取/例外/限定语义要求
EXCEPTION_SEMANTICS_REFS = {
    "body.p1007": {
        "base_rule": "因对现存疾病进行诊断或择期手术治疗而住院或延长住院，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "析取关系：现存疾病诊断或择期手术治疗是两个备选原因，不得改为同时满足",
        "preserve_keywords": ["现存疾病", "诊断", "择期手术"],
    },
    "body.p1008": {
        "base_rule": "因研究需要做疗效评价而住院或延长住院，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "限定：研究需要且疗效评价；不是疗效评价执行义务或入排程序",
        "preserve_keywords": ["研究需要", "疗效评价"],
    },
    "body.p1009": {
        "base_rule": "因研究的目标疾病的规定疗程而住院或延长住院，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "双重限定：目标疾病且规定疗程；不是治疗执行义务",
        "preserve_keywords": ["目标疾病", "规定疗程"],
    },
    "body.p1010": {
        "base_rule": "方案规定的计划住院，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "限定：方案规定；与AE记录除外（第77包p989计划住院）语义层次不同",
        "preserve_keywords": ["方案规定", "计划住院"],
    },
    "body.p1011": {
        "base_rule": "研究前计划的住院或非不良事件导致的择期手术，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "因果镜像：非不良事件导致与p1001'由于不良事件所致'互为镜像；与p1012是相邻独立备选项",
        "preserve_keywords": ["研究前计划的住院", "非不良事件导致", "择期手术"],
    },
    "body.p1012": {
        "base_rule": "或全面体格检查而导致的入院，可作为研究者综合判断下的不作为SAE候选项",
        "exception_rule": "'或'连接相邻备选项：p1011与p1012是两个独立来源单元，不得合并成一个条件",
        "preserve_keywords": ["全面体格检查", "入院"],
    },
    "body.p1013": {
        "base_rule": "先天性异常或者出生缺陷：指参与者的后代出现畸形或先天的功能缺陷等，是SAE严重性标准之一",
        "exception_rule": "判据对象是参与者的后代，是治疗期SAE判定标准，不是筛选/基线入排条件，不得倒灌为生殖/生育入排标准",
        "preserve_keywords": ["先天性异常或者出生缺陷", "后代", "畸形", "先天的功能缺陷"],
    },
    "body.p1014": {
        "base_rule": "其他有重要意义的医学事件：必须运用医学和科学的判断决定是否对其他的情况加速报告",
        "exception_rule": "预防严重后果的条件逻辑：如需要采取医学措施来预防立即危及生命/死亡/住院情形之一的发生，也通常被视为是严重的",
        "preserve_keywords": ["医学和科学的判断", "加速报告", "采取医学措施", "预防", "通常被视为是严重的"],
    },
}

# SAE锚点交叉验证（只读闭包）
SAE_ANCHOR_REF = "body.p996"  # 接受试验用药品后
AE_RECORD_START_REF = "body.p340"  # 不良事件于D1启动给药后开始记录
AE_WINDOW_REF = "body.p1022"  # 首次服药后至末次安全性随访
OR_HEAD_REF = "body.p997"  # 符合下列标准任何一项
HOSPITALIZATION_CAUSAL_REF = "body.p1001"  # 由于不良事件所致，而非择期手术、非医疗原因
INVESTIGATOR_JUDGMENT_HEAD_REF = "body.p1002"  # 可根据研究者综合判断不作为SAE


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
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
    assert config["group_id"] == "d001-ii-package79-sae-tail-boundary"
    assert config["task_id"] == "phase5-slice61bq-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 8

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(), "第79包八个拥有单元均为语义单元，无结构性标题单元"
    assert forbidden == set(OWNED_REFS), "第79包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第79包不发射任何候选"
    assert structural <= owned
    assert required.isdisjoint(forbidden)

    # 全部拥有单元落入治疗期SAE分类语义（住院除外列表续与严重性标准尾项）。
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in OWNED_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：住院除外/先天异常/重要医学事件的禁止升格措辞必须已写入配置
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
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_79), "attached refs must not be owned by package 79"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 32


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，同词锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PRECEDING_ATTACHED_REFS:
        assert owners.get(ref) == [78], f"{ref} 必须保持归第78包"
    assert owners.get("body.p835") == [75], "body.p835 必须保持归第75包"
    expected_domain_owners = {
        "body.p638": 51,
        "body.p645": 52,
        "body.p661": 53,
        "body.p696": 56,
        "body.p816": 73,
    }
    for ref, ordinal in expected_domain_owners.items():
        assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"
    for ref in UNOWNED_CONTEXT_REFS:
        assert ref not in owners, f"{ref} 必须保持流程注记上下文来源"
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        for paragraph in range(start, end + 1):
            ref = f"body.p{paragraph}"
            assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"


def test_later_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包拥有p996-p1006（11），第79包拥有p1007-p1014（8），
    第80包拥有p1015-p1026（12）。"""
    pkg78 = next(p for p in plan["packages"] if p["package_ordinal"] == 78)
    pkg79 = next(p for p in plan["packages"] if p["package_ordinal"] == 79)
    pkg80 = next(p for p in plan["packages"] if p["package_ordinal"] == 80)
    owned_78 = {u["source_ref"] for u in pkg78["owned_units"]}
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    owned_80 = {u["source_ref"] for u in pkg80["owned_units"]}
    assert set(PRECEDING_ATTACHED_REFS) <= owned_78
    assert len(owned_78) == 12
    assert "body.p1007" in owned_79 and "body.p1012" in owned_79
    assert "body.p1014" in owned_79 and len(owned_79) == 8
    assert "body.p1015" in owned_80 and "body.p1026" in owned_80
    assert len(owned_80) == 12


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_79(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_79_ID
    assert plan["plan_id"] == PLAN_ID
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p1007"] == "因对现存疾病进行诊断或择期手术治疗而住院或延长住院；"
    assert excerpts["body.p1008"] == "因研究需要做疗效评价而住院或延长住院；"
    assert excerpts["body.p1009"] == "因研究的目标疾病的规定疗程而住院或延长住院；"
    assert excerpts["body.p1010"] == "方案规定的计划住院；"
    assert excerpts["body.p1011"] == "研究前计划的住院或非不良事件导致的择期手术；"
    assert excerpts["body.p1012"] == "或全面体格检查而导致的入院。"
    assert excerpts["body.p1013"] == (
        "先天性异常或者出生缺陷：指参与者的后代出现畸形或先天的功能缺陷等。"
    )
    assert excerpts["body.p1014"] == (
        "其他有重要意义的医学事件：必须运用医学和科学的判断决定是否对其他的情况"
        "加速报告，如重要医学事件可能不会立即危及生命、死亡或住院，但如需要采取"
        "医学措施来预防如上情形之一的发生，也通常被视为是严重的。"
    )


# ---------------------------------------------------------------------------
# later-package read-only boundary: p1015-p1026 stays with package 80
# ---------------------------------------------------------------------------


def test_later_package_boundary_contiguous(config: dict) -> None:
    boundary = config["later_package_boundary"]
    spans = set(boundary["expected_owners_by_span"])
    expected = {
        f"body.p{ordinal}" for ordinal in range(1015, 1027)
    }
    assert spans == expected, "后续包边界必须精确覆盖 body.p1015-p1026"
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
        assert expected_ordinal != PACKAGE_79_ORDINAL, f"{ref} 不得归第79包"


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
    assert set(by_ordinal) == {80}


def test_later_package_definition_heads_stay_out_of_package_79(plan: dict) -> None:
    """ADR/SUSAR与AE收集记录边界起于 body.p1015，不得被第79包提前吞并。"""
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    assert "body.p1015" not in owned_79
    assert "body.p1022" not in owned_79
    assert "body.p1026" not in owned_79


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "body.p1026" in note
    assert "第80包" in note
    assert "吞并" in note, "边界注记必须声明后续包不得被本包提前吞并"


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
    assert "现存疾病" in by_ref["body.p1007"].excerpt
    assert "疗效评价" in by_ref["body.p1008"].excerpt
    assert "规定疗程" in by_ref["body.p1009"].excerpt
    assert "方案规定的计划住院" in by_ref["body.p1010"].excerpt
    assert "非不良事件导致" in by_ref["body.p1011"].excerpt
    assert "全面体格检查" in by_ref["body.p1012"].excerpt
    assert "后代" in by_ref["body.p1013"].excerpt
    assert "医学和科学的判断" in by_ref["body.p1014"].excerpt
    assert "预防" in by_ref["body.p1014"].excerpt

    domain_fragments = {
        "body.p327": "妊娠试验或卵泡刺激素",
        "body.p638": "无怀孕或捐精计划",
        "body.p645": "需住院或静脉抗感染治疗",
        "body.p661": "先天性或获得性免疫缺陷",
        "body.p696": "妊娠或哺乳期女性",
        "body.p816": "不具有生育能力",
    }
    for ref, fragment in domain_fragments.items():
        assert by_ref[ref].role == "attached"
        assert fragment in by_ref[ref].excerpt

    for ref in PRECEDING_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip()
    assert "接受试验用药品后" in by_ref["body.p996"].excerpt
    assert "任何一项" in by_ref["body.p997"].excerpt
    assert "结果" in by_ref["body.p998"].excerpt and "死亡" in by_ref["body.p998"].excerpt
    assert "已经处于死亡的危险中" in by_ref["body.p999"].excerpt
    assert "不构成重大干扰" in by_ref["body.p1000"].excerpt
    assert "由于不良事件所致" in by_ref["body.p1001"].excerpt
    assert "研究者综合判断" in by_ref["body.p1002"].excerpt
    assert "留院观察" in by_ref["body.p1003"].excerpt
    assert "少于24小时" in by_ref["body.p1004"].excerpt
    assert "社会原因" in by_ref["body.p1005"].excerpt
    assert "康复机构" in by_ref["body.p1006"].excerpt
    assert "不良事件于D1启动给药后开始记录" in by_ref["body.p340"].excerpt
    assert "整个研究过程要严密监测" in by_ref["body.p835"].excerpt
    assert "D1给药前结果作为基线值" in by_ref["body.p885"].excerpt
    assert "同时需要记录合并用药及不良事件" in by_ref["body.p885"].excerpt
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip(), f"{ref} 只读闭包来源为空"
    assert "药物不良反应（ADR）" in by_ref["body.p1015"].excerpt
    assert "可能有关的对人体有害或者非期望的反应" in by_ref["body.p1016"].excerpt
    assert "SUSAR" in by_ref["body.p1017"].excerpt
    assert "可疑并且非预期的严重不良反应" in by_ref["body.p1018"].excerpt
    assert "非预期不良反应" in by_ref["body.p1019"].excerpt
    assert "不良事件的收集和记录" in by_ref["body.p1020"].excerpt
    assert "不良事件的收集" in by_ref["body.p1021"].excerpt
    assert "首次服用试验用药品后" in by_ref["body.p1022"].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt
    assert "记录在eCRF中" in by_ref["body.p1024"].excerpt
    assert "不良事件的记录与规定" in by_ref["body.p1025"].excerpt
    assert "单一事件项中应只记录一个不良事件术语" in by_ref["body.p1026"].excerpt


def test_sae_anchor_chain_consistent(config: dict) -> None:
    """SAE锚点链：SAE(接受试验用药品后)-记录起点(D1给药后)-收集窗口(首次服药后)。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    assert "接受试验用药品后" in by_ref[SAE_ANCHOR_REF]
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

    # 第79包只负责SAE判定分类，不得因附带的给药前复核来源而发射入排候选。
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
    for ref in PRECEDING_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in ANCHOR_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in DOMAIN_SEPARATION_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 8
    assert summary["attached_count"] == 32
    assert summary["unit_count"] == 40
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

    # 越界候选（把重要医学事件升格为筛选/基线控制候选）必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p1014"]],
                "title": "重要医学事件史纳入筛选必查，证据不足者入排不通过",
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
    """确定性门禁必须拒绝把住院除外/先天异常/重要医学事件改写为筛选/基线门槛的反例。"""
    # 先天异常（p1013）倒灌筛选/基线或生殖入排门槛
    markers_1013 = config["candidate_forbidden_markers_by_source_ref"]["body.p1013"]
    congenital_counterexamples = [
        "筛选时评估受试者后代有无先天异常，无畸形证据者视为证据缺口",
        "后代存在出生缺陷风险者按排除标准判定入排不通过",
        "基线期完成先天异常评估，未完成者不得入组",
        "筛选发现的先天性异常或出生缺陷属于证据不足，禁止入组",
    ]
    for text in congenital_counterexamples:
        assert _forbidden_marker_hits(text, markers_1013), f"门禁未拦截: {text}"

    # 住院除外（p1007）改写为筛选/基线必做门槛
    markers_1007 = config["candidate_forbidden_markers_by_source_ref"]["body.p1007"]
    hospitalization_counterexamples = [
        "筛选时评估既往住院情况，现存疾病择期手术住院者证据不足不得入组",
        "因现存疾病择期手术住院者按排除标准判定不通过",
        "基线期完成住院情况必做核验，不符合者不得入组",
    ]
    for text in hospitalization_counterexamples:
        assert _forbidden_marker_hits(text, markers_1007), f"门禁未拦截: {text}"

    # 重要医学事件（p1014）改写为筛选/基线必做
    markers_1014 = config["candidate_forbidden_markers_by_source_ref"]["body.p1014"]
    important_event_counterexamples = [
        "筛选时评估重要医学事件史，否则视为证据缺口",
        "重要医学事件史不符合者按排除标准判定入排不通过",
    ]
    for text in important_event_counterexamples:
        assert _forbidden_marker_hits(text, markers_1014), f"门禁未拦截: {text}"

    legitimate = [
        "因对现存疾病进行诊断或择期手术治疗而住院或延长住院；",
        "因研究需要做疗效评价而住院或延长住院；",
        "因研究的目标疾病的规定疗程而住院或延长住院；",
        "方案规定的计划住院；",
        "研究前计划的住院或非不良事件导致的择期手术；",
        "或全面体格检查而导致的入院。",
        "先天性异常或者出生缺陷：指参与者的后代出现畸形或先天的功能缺陷等。",
        "其他有重要意义的医学事件：必须运用医学和科学的判断决定是否对其他的情况"
        "加速报告，如重要医学事件可能不会立即危及生命、死亡或住院，但如需要采取"
        "医学措施来预防如上情形之一的发生，也通常被视为是严重的。",
    ]
    for text in legitimate:
        assert _forbidden_marker_hits(text, markers_1013) == [], f"误拦截合法定义: {text}"


# ---------------------------------------------------------------------------
# deterministic exception/conjunction semantics gate (合取/例外/限定语义)
# ---------------------------------------------------------------------------


def test_exception_semantics_preserved_in_owned_sources(
    config: dict, plan: dict
) -> None:
    """住院除外/先天异常/重要医学事件的合取、例外与限定关键词必须逐条保留在冻结来源中。"""
    excerpts = _owned_excerpt_by_ref(plan, config)
    semantics = config["exception_semantics_by_source_ref"]
    for ref, entry in semantics.items():
        missing = _missing_exception_keywords(excerpts[ref], entry)
        assert missing == [], f"{ref} 丢失例外语义关键词: {missing}"


def test_exception_drop_regressions_are_detected(config: dict) -> None:
    """确定性门禁必须拦截丢失限定、判断权或条件逻辑的改写。"""
    semantics = config["exception_semantics_by_source_ref"]
    dropped = {
        "body.p1007": "因现存疾病住院不作为SAE。",
        "body.p1008": "研究相关住院不作为SAE。",
        "body.p1009": "因规定疗程住院不作为SAE。",
        "body.p1010": "计划住院不作为SAE。",
        "body.p1011": "研究前计划的住院或择期手术不作为SAE。",
        "body.p1012": "体格检查导致的入院不作为SAE。",
        "body.p1013": "出生缺陷者需在筛选时评估。",
        "body.p1014": "其他异常情况均需加速报告。",
    }
    for ref, text in dropped.items():
        assert _missing_exception_keywords(text, semantics[ref]), (
            f"{ref} 例外/限定丢失反例未被门禁拦截"
        )


def test_p1007_preserves_or_instead_of_rewriting_as_and(
    config: dict, plan: dict
) -> None:
    """现存疾病诊断与择期手术治疗是备选原因，不得由“或”反转为“且”。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1007"]
    assert "现存疾病进行诊断或择期手术治疗" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1007"]
    assert "析取关系" in entry["exception_rule"]
    assert "不得改成同时满足" in entry["exception_rule"]
    assert "且'择期手术治疗'" not in entry["exception_rule"]


def test_same_term_eligibility_anchors_stay_distinct_from_sae_tail(
    config: dict,
) -> None:
    """同词不得跨语义域合并：住院、先天性、生育和妊娠各守原规则职责。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    assert "需住院或静脉抗感染治疗" in by_ref["body.p645"].excerpt
    assert "严重细菌、真菌或病毒感染史" in by_ref["body.p645"].excerpt
    assert "研究者综合判断不作为SAE" in by_ref[LIST_HEAD_REF].excerpt
    assert "先天性或获得性免疫缺陷" in by_ref["body.p661"].excerpt
    assert "参与者的后代" in by_ref["body.p1013"].excerpt
    assert "无怀孕或捐精计划" in by_ref["body.p638"].excerpt
    assert "妊娠或哺乳期女性" in by_ref["body.p696"].excerpt
    assert not (set(DOMAIN_SEPARATION_ATTACHED_REFS) & set(OWNED_REFS))
    assert not (
        set(DOMAIN_SEPARATION_ATTACHED_REFS)
        & set(config["required_candidate_source_refs"])
    )


def test_any_criterion_or_semantics_preserved(config: dict) -> None:
    """p997 的OR语义：'符合下列标准任何一项'必须保留；p1013/p1014是任一满足即SAE的尾项。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    head = by_ref[OR_HEAD_REF].excerpt
    assert "任何一项" in head and "符合下列标准" in head
    assert "全部标准" not in head
    # 尾项不得声称需要全部标准同时满足
    for ref in ("body.p1013", "body.p1014"):
        assert "全部标准" not in by_ref[ref].excerpt
        assert "任何一项" in head  # 总纲在只读闭包内，尾项语义由其统辖


def test_hospitalization_causal_qualification_mirror_preserved(config: dict) -> None:
    """p1001（只读）与p1011（拥有）的因果限定互为镜像，必须同时保留。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row for row in _resolve_units(config)}
    assert "由于不良事件所致" in by_ref[HOSPITALIZATION_CAUSAL_REF].excerpt
    assert "非不良事件导致" in by_ref["body.p1011"].excerpt
    assert "择期手术" in by_ref[HOSPITALIZATION_CAUSAL_REF].excerpt
    assert "择期手术" in by_ref["body.p1011"].excerpt


def test_investigator_judgment_head_attached_not_automatic_waiver(config: dict) -> None:
    """p1002 的研究者综合判断：列表各项是判断候选项，不是自动豁免。"""
    from slice59n_representative_group_control_replay import _resolve_units

    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    head = by_ref[LIST_HEAD_REF]
    assert "研究者综合判断" in head and "不作为SAE" in head
    for ref in LIST_ITEMS_PKG79_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert "自动豁免" in entry["forbidden_inversion"], ref


def test_congenital_anomaly_not_inverted_into_reproductive_ie(
    config: dict, plan: dict
) -> None:
    """p1013 保持为SAE严重性标准（判据对象为参与者的后代），不倒灌生殖入排标准。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1013"]
    assert "先天性异常或者出生缺陷" in excerpt
    assert "后代" in excerpt
    assert "畸形" in excerpt and "先天的功能缺陷" in excerpt
    entry = config["exception_semantics_by_source_ref"]["body.p1013"]
    for keyword in ("后代", "畸形", "先天的功能缺陷"):
        assert keyword in entry["preserve_keywords"]
    assert "倒灌" in entry["forbidden_inversion"]

    inverted = [
        "受试者后代存在先天异常者不得入组",
        "筛选时评估后代先天异常风险，无畸形证据者视为证据缺口",
    ]
    for text in inverted:
        assert _missing_exception_keywords(text, entry), f"倒灌反例未被拦截: {text}"
        markers = config["candidate_forbidden_markers_by_source_ref"]["body.p1013"]
        assert _forbidden_marker_hits(text, markers), f"升格门禁未拦截: {text}"


def test_important_medical_event_judgment_and_prevention_conditional(
    config: dict, plan: dict
) -> None:
    """p1014 保留医学和科学判断及预防严重后果的条件逻辑，不简化为'任何异常'。"""
    excerpt = _owned_excerpt_by_ref(plan, config)["body.p1014"]
    for fragment in (
        "医学和科学的判断",
        "加速报告",
        "不会立即危及生命、死亡或住院",
        "采取医学措施来预防如上情形之一的发生",
        "通常被视为是严重的",
    ):
        assert fragment in excerpt, f"p1014 丢失条件逻辑片段: {fragment}"
    entry = config["exception_semantics_by_source_ref"]["body.p1014"]
    for keyword in ("医学和科学的判断", "加速报告", "采取医学措施", "预防", "通常被视为是严重的"):
        assert keyword in entry["preserve_keywords"]

    weakened = [
        "其他有重要意义的医学事件均需加速报告。",
        "重要医学事件如无立即危险即不作为严重事件。",
        "任何异常发现均按重要医学事件加速报告。",
        "重要医学事件按研究者判断处置。",
    ]
    for text in weakened:
        assert _missing_exception_keywords(text, entry), f"弱化反例未被拦截: {text}"


def test_p1014_reporting_obligation_not_absorbed_into_package80(
    config: dict, plan: dict
) -> None:
    """第79包只保留严重性判断，不替代第80包定义或后续报告时限与流程。"""
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}
    assert "body.p1014" in owned_79
    assert not ({f"body.p{ordinal}" for ordinal in range(1015, 1027)} & owned_79)
    entry = config["exception_semantics_by_source_ref"]["body.p1014"]
    assert "第80包" in entry["forbidden_inversion"]
    note = config["later_package_boundary"]["note"]
    assert "报告时限与流程" in note


# ---------------------------------------------------------------------------
# continuous hospitalization-exception list across packages 78-79
# ---------------------------------------------------------------------------


def test_hospitalization_exception_list_continuous_across_packages(
    config: dict, plan: dict
) -> None:
    """p1002引导句承接的住院除外列表跨第78-79包连续，不得在p1006截断。"""
    from slice59n_representative_group_control_replay import _resolve_units

    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_79 = {u["source_ref"] for u in pkg79["owned_units"]}

    # 列表头与第78包前四项必须进入只读闭包（跨包连续性依赖实际提示内容）
    attached = set(config["attached_source_refs"])
    assert LIST_HEAD_REF in attached
    for ordinal in range(1003, 1007):
        ref = f"body.p{ordinal}"
        assert ref in attached, f"{ref} 必须进入只读闭包以保持连续列表"

    # 第79包拥有列表延续项 p1007-p1012
    assert LIST_FIRST_PKG79_REF in owned_79 and LIST_LAST_PKG79_REF in owned_79
    assert LIST_ITEMS_PKG79_REFS == [f"body.p{ordinal}" for ordinal in range(1007, 1013)]

    # 第78包拥有项以分号结尾表示延续，第79包收尾项以句号结束
    by_ref = {row.source_ref: row.excerpt for row in _resolve_units(config)}
    assert by_ref[LIST_LAST_PKG78_REF].rstrip().endswith("；")
    assert by_ref[LIST_LAST_PKG79_REF].rstrip().endswith("。")
    assert by_ref[LIST_HEAD_REF] == "*以下住院情况可根据研究者综合判断不作为SAE："
    assert LIST_LAST_PKG78_REF != LIST_HEAD_REF


def test_p1011_and_p1012_remain_separate_alternatives_in_one_list(
    config: dict,
) -> None:
    """跨段的'或'连接相邻备选项，不得把两个来源单元合并成一个条件。"""
    from slice59n_representative_group_control_replay import _resolve_units

    rows = {row.source_ref: row for row in _resolve_units(config)}
    assert rows["body.p1011"].structure_unit_id != rows["body.p1012"].structure_unit_id
    assert rows["body.p1011"].excerpt.rstrip().endswith("；")
    assert rows["body.p1012"].excerpt.lstrip().startswith("或")
    assert rows["body.p1011"].source_span_ids == ("body.p1011",)
    assert rows["body.p1012"].source_span_ids == ("body.p1012",)


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p996-p1026, zero AE/TEAE/SAE rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_definition_section(
    matrix: dict, plan: dict
) -> None:
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg79["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第79包拥有来源为锚点"
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
            if ordinal.isdigit() and 996 <= int(ordinal) <= 1026:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package79_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg79 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_79_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg79["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第79包拥有来源为锚点"
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
            if ordinal.isdigit() and 996 <= int(ordinal) <= 1026:
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
    assert PACKAGE_79_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "研究者综合判断" in text
    assert "医学和科学的判断" in text
    assert "预防" in text and "后代" in text
    assert "截断" in text
    assert "body.p1015" in text and "body.p1026" in text
    assert "body.p327" in text and "body.p816" in text
    assert "同词" in text and "析取" in text
    assert "第80包" in text
    assert "父级盲态检查清单" in text
