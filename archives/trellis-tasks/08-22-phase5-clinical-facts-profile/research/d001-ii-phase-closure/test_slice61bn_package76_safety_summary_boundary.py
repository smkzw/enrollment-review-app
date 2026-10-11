#!/usr/bin/env python3
"""Slice61bn model-free source-closure regressions.

Locks the D001 II package 76 safety summary clinical semantic boundary (frozen
plan package 76: 安全性评估 / 安全性指标 / AE-TEAE-SAE incidence / routine
safety parameters / 术语定义 heading) to its authoritative sources before any
semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 76; attached refs stay read-only
- no control candidate may be emitted from any owned span
- AE/TEAE/SAE incidence and routine safety parameter summaries must never be
  upgraded into screening/baseline mandatory duties, evidence gaps, or
  enrollment-fail conditions (deterministic forbidden-marker gate)
- later-package read-only boundary: body.p985-p1024 stays owned by packages
  77-80, never absorbed by package 76
- official matrix keeps zero rows anchored in p980-p1024 and zero 不良事件 /
  发生率 rows; procedure catalog has no AE/incidence node and already covers
  the routine safety parameter classes at flow-table stages
- workflow stages keep D1 pre-dose distinct from the baseline visit
- immutable source fingerprints

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
CONFIG_PATH = CONFIG_DIR / "representative_group_package76_safety_summary_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bn-package76-safety-summary-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package76-safety-summary-boundary"
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
PACKAGE_76_ORDINAL = 76
PACKAGE_76_ID = "pap-02ff890bf007aae9a89887a8"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(980, 985)]
TITLE_REFS = ["body.p980", "body.p981", "body.p984"]
SUMMARY_REFS = ["body.p982", "body.p983"]

CONTEXT_ATTACHED_REFS = [
    "body.p475",
    "body.p494",
    "body.p531",
    "body.p560",
    "body.t5.r0",
    "body.p765",
    "body.p838",
]
LATER_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(985, 1025)]
ATTACHED_REFS = CONTEXT_ATTACHED_REFS + LATER_ATTACHED_REFS

# 后续包只读边界：body.p985-p1024 归第77-80包所有
LATER_BOUNDARY_FIRST = "body.p985"
LATER_BOUNDARY_LAST = "body.p1024"
LATER_OWNER_RANGES = {
    77: (985, 994),  # AE定义及除外、TEAE定义
    78: (995, 1006),  # SAE定义、严重性标准及住院除外列表
    79: (1007, 1014),  # 住院除外列表续及严重性标准
    80: (1015, 1024),  # ADR、SUSAR定义及AE收集与记录边界
}

# 常规安全性参数类别（body.p983 摘要列举），必须已由流程目录单独发布
ROUTINE_PARAMETER_LABELS = (
    "生命体征",
    "体格检查",
    "12-导联心电图",
    "血常规",
    "血生化",
    "尿常规",
    "凝血功能",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _owned_excerpt_by_ref(plan: dict, config: dict) -> dict[str, str]:
    pkg = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL)
    return {
        u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]
    }


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
    assert config["group_id"] == "d001-ii-package76-safety-summary-boundary"
    assert config["task_id"] == "phase5-slice61bn-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 5

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(TITLE_REFS)
    assert forbidden == set(OWNED_REFS), "第76包所有拥有单元均禁止发射候选"
    assert pre_enrollment == set()
    assert required == set(), "第76包不发射任何候选"
    assert structural <= owned
    assert required.isdisjoint(forbidden)

    assert config["expected_disposition_by_source_ref"] == {
        "body.p982": "administrative_statistical_background",
        "body.p983": "administrative_statistical_background",
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 通用门禁建议：发生率/常规参数摘要的禁止升格措辞必须已写入配置
    for ref in SUMMARY_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {"筛选必做", "基线必做", "证据缺口", "不得入组", "排除标准", "入排不通过"} <= set(
            markers
        ), ref
    assert config["candidate_required_markers_by_source_ref"] == {}


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg76 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL)
    owned_76 = {u["source_ref"] for u in pkg76["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_76), "attached refs must not be owned by package 76"
    assert set(attached) == set(ATTACHED_REFS)


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，p985-p1024 保持归第77-80包。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in (
        "body.p475",
        "body.p494",
        "body.p531",
        "body.p560",
        "body.t5.r0",
        "body.p765",
    ):
        assert ref not in owners, f"{ref} must stay context-only"
    assert owners.get("body.p838") == [75], "访视安排章节标题由第75包拥有"
    for ordinal, (start, end) in LATER_OWNER_RANGES.items():
        for paragraph in range(start, end + 1):
            ref = f"body.p{paragraph}"
            assert owners.get(ref) == [ordinal], f"{ref} 必须保持归第{ordinal}包"


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_76(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_76_ID
    assert plan["plan_id"] == PLAN_ID
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan, config)
    assert excerpts["body.p980"] == "安全性评估"
    assert excerpts["body.p981"] == "安全性指标"
    assert excerpts["body.p982"] == "不良事件、治疗期出现的不良事件和严重不良事件的发生率；"
    assert excerpts["body.p983"] == (
        "常规安全性参数，包括实验室检查、生命体征测量、12导联心电图（ECG）和体格检查等。"
    )
    assert excerpts["body.p984"] == "术语定义"


# ---------------------------------------------------------------------------
# later-package read-only boundary: p985-p1024 stays with packages 77-80
# ---------------------------------------------------------------------------


def test_later_package_boundary_contiguous(config: dict) -> None:
    boundary = config["later_package_boundary"]
    spans = set(boundary["expected_owners_by_span"])
    expected = {
        f"body.p{ordinal}"
        for ordinal in range(985, 1025)
    }
    assert spans == expected, "后续包边界必须精确覆盖 body.p985-p1024"
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
        assert expected_ordinal != PACKAGE_76_ORDINAL, f"{ref} 不得归第76包"


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
    assert set(by_ordinal) == {77, 78, 79, 80}


def test_later_package_definition_heads_stay_out_of_package_76(plan: dict) -> None:
    """术语定义正文（AE定义起于 body.p985）不得被第76包提前吞并。"""
    pkg76 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL)
    owned_76 = {u["source_ref"] for u in pkg76["owned_units"]}
    assert "body.p985" not in owned_76
    assert "body.p986" not in owned_76
    assert "body.p1024" not in owned_76


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
    assert "发生率" in by_ref["body.p982"].excerpt
    assert "常规安全性参数" in by_ref["body.p983"].excerpt
    assert "12导联心电图" in by_ref["body.p983"].excerpt
    assert "术语定义" in by_ref["body.p984"].excerpt
    for ref in ("body.p475", "body.p494"):
        assert by_ref[ref].excerpt.strip() == "安全性指标"
    for ref in ("body.p531", "body.p560"):
        assert "安全性评估内容包括" in by_ref[ref].excerpt
    assert "筛选期(D-28~D-1)" in by_ref["body.t5.r0"].excerpt
    assert by_ref["body.p838"].package_ordinal == 75
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].excerpt.strip(), f"{ref} 只读闭包来源为空"
    assert "病史/伴随疾病" in by_ref["body.p988"].excerpt
    assert "严重不良事件" in by_ref["body.p996"].excerpt
    assert "首次服用试验用药品之前" in by_ref["body.p1023"].excerpt
    assert "不作为AE记录" in by_ref["body.p1023"].excerpt
    assert "首次服用试验用药品" in by_ref["body.p1024"].excerpt
    assert "所有AE均需记录" in by_ref["body.p1024"].excerpt


def test_prepare_evidence_contains_real_later_package_closure(config: dict) -> None:
    """生成后的提示证据必须实际包含后续定义，不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in LATER_ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 5
    assert summary["attached_count"] == 47
    assert summary["unit_count"] == 52
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

    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": [unit_by_ref["body.p982"]],
                "title": "不良事件发生率",
                "semantics": {},
            }
        ],
        "dispositions": dispositions,
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues)

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
    for ref in SUMMARY_REFS:
        hits = _forbidden_marker_hits(excerpts[ref], markers_by_ref[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把发生率/常规参数摘要升格为筛选/基线义务的反例。"""
    markers = config["candidate_forbidden_markers_by_source_ref"]["body.p982"]

    counterexamples = [
        "不良事件发生率应在筛选期作为必做检查完成，否则视为证据缺口",
        "筛选前必须收集完整的常规安全性参数，基线期未达标者入排不通过",
        "治疗期出现的不良事件发生率缺失，不符合入选标准",
        "常规安全性参数不足者不得入组",
        "基线期必做12导联心电图且不得缺失",
    ]
    for text in counterexamples:
        assert _forbidden_marker_hits(text, markers), f"门禁未拦截: {text}"

    legitimate = [
        "不良事件、治疗期出现的不良事件和严重不良事件的发生率",
        "常规安全性参数，包括实验室检查、生命体征测量、12导联心电图（ECG）和体格检查等",
        "安全性评估内容包括收集不良事件、记录生命体征、进行体格检查和评估临床实验室检查和心电图检查结果",
    ]
    for text in legitimate:
        assert _forbidden_marker_hits(text, markers) == [], f"误拦截合法摘要: {text}"


# ---------------------------------------------------------------------------
# official matrix: zero rows anchored in p980-p1024, zero AE/incidence rows
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_safety_summary_section(
    matrix: dict, plan: dict
) -> None:
    pkg76 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL)
    owned_refs = {u["source_ref"] for u in pkg76["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第76包拥有来源为锚点"
            )


def test_matrix_has_no_safety_endpoint_or_incidence_rows(matrix: dict) -> None:
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
        assert "发生率" not in text, row["matrix_row_id"]
        for anchor in row.get("source_anchors") or []:
            ref = str(anchor.get("source_ref") or "")
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 980 <= int(ordinal) <= 1024:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在安全性摘要或后续定义边界内"
                )


def test_no_official_rule_anchors_package76_owned_spans(matrix: dict, plan: dict) -> None:
    pkg76 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_76_ORDINAL)
    owned_refs = {u["source_ref"] for u in pkg76["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第76包拥有来源为锚点"
            )


# ---------------------------------------------------------------------------
# frozen procedure catalog: no AE/incidence node; routine parameters covered
# ---------------------------------------------------------------------------


def _catalog_nodes(catalog: dict, label: str) -> list[dict]:
    return [item for item in catalog["items"] if item["label"] == label]


def test_procedure_catalog_has_no_ae_or_incidence_node(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = str(item["label"])
        assert "不良事件" not in label
        assert "发生率" not in label
        assert label not in {"AE", "TEAE", "SAE"}
    assert _catalog_nodes(procedure_catalog, "不良事件") == []
    assert _catalog_nodes(procedure_catalog, "发生率") == []


def test_procedure_catalog_covers_routine_safety_parameter_classes(
    procedure_catalog: dict,
) -> None:
    """body.p983 摘要的常规参数类别必须已由流程目录在正确时点单独发布。"""
    labels = {str(item["label"]) for item in procedure_catalog["items"]}
    for label in ROUTINE_PARAMETER_LABELS:
        assert label in labels, f"流程目录缺少 {label}"
    # 生命体征/体格检查在筛选、基线与D1均有节点（治疗期W0也执行）
    for label in ("生命体征", "体格检查"):
        stages = sorted(n["review_stage"] for n in _catalog_nodes(procedure_catalog, label))
        assert stages == ["baseline", "baseline", "screening"], (label, stages)
    # 实验室面板与12-导联心电图在筛选及基线均有节点，无D1节点
    for label in ("血常规", "血生化", "尿常规", "凝血功能"):
        stages = sorted(n["review_stage"] for n in _catalog_nodes(procedure_catalog, label))
        assert stages == ["baseline", "screening"], (label, stages)
    ecg = sorted(n["review_stage"] for n in _catalog_nodes(procedure_catalog, "12-导联心电图"))
    assert ecg == ["baseline", "screening"]


def test_no_procedure_node_sourced_from_package76_owned_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            if str(span).endswith(("body.p980", "body.p981", "body.p982", "body.p983", "body.p984")):
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以第76包拥有来源为来源"
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
    assert PACKAGE_76_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "发生率" in text
    assert "常规安全性参数" in text
    assert "术语定义" in text
    assert "body.p985" in text and "body.p1024" in text
    assert "77-80" in text
    assert "父级盲态检查清单" in text
