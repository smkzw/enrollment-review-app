#!/usr/bin/env python3
"""Slice61bm model-free source-closure regressions.

Locks the D001 II package 75 clinical semantic boundary (frozen plan package
75: PK/IL-17A blood sampling, AE recording, concomitant-treatment recording)
to its authoritative sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 75; attached refs stay read-only
- no official IN/EX rule may be derived from package-75 owned spans
- flow-table cell-level markers: PK has no D1/pre-dose marker, IL-17A has D1,
  AE starts at treatment D1, concomitant treatment at screening
- frozen procedure catalog: IL-17A D1 node and screening concomitant node only;
  no PK or AE enrollment node exists
- the frozen official matrix keeps 合并治疗 as a must_record collection row
- workflow stages keep D1 pre-dose distinct from the baseline visit
- immutable source fingerprints

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

from collections import Counter
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
CONFIG_PATH = CONFIG_DIR / "representative_group_package75_semantic_boundary.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bm-package75-semantic-boundary-parent-checklist.md"
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
PACKAGE_75_ORDINAL = 75
PACKAGE_75_ID = "pap-9519680f4eac0c124ea342b6"

OWNED_REFS = [
    "body.p828",
    "body.p831",
    "body.p832",
    "body.p833",
    "body.p834",
    "body.p835",
    "body.p836",
    "body.p837",
    "body.p838",
]
TITLE_REFS = ["body.p828", "body.p834", "body.p836", "body.p838"]
# 中心实验室手册说明：申办者对研究中心的操作层指引，不发射受试者级候选
LAB_OPERATIONS_REFS = ["body.p833"]
ACTION_REFS = ["body.p837"]

ATTACHED_REFS = [
    "body.p829",
    "body.p830",
    "body.p749",
    "body.t5.r29",
    "body.t5.r30",
    "body.t5.r37",
    "body.t5.r38",
    "body.p855",
    "body.p866",
    "body.p875",
    "body.p883",
    "body.p884",
    "body.p885",
    "body.p931",
    "body.p932",
    "body.p933",
    "body.p934",
]

# Ⅱ期流程表列：c1=筛选、c2=基线、c3=治疗期W0(D1)、c4-c7=W2/W4/W8/W12、
# c8=W16安全性随访、c9=提前退出
FLOW_COLUMN_SCREENING = "c1"
FLOW_COLUMN_BASELINE = "c2"
FLOW_COLUMN_D1 = "c3"

CONCOMITANT_MATRIX_ROW_ID = "pcm-row-ac740aed1f7fb0e761095c20"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    assert config["group_id"] == "d001-ii-package75-semantic-boundary"
    assert config["task_id"] == "phase5-slice61bm-20260829"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 9

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == set(TITLE_REFS)
    assert forbidden == set(TITLE_REFS + LAB_OPERATIONS_REFS)
    assert pre_enrollment == set()
    assert required == set(ACTION_REFS)
    assert structural <= owned and required <= owned
    assert required.isdisjoint(forbidden)
    assert config["expected_disposition_by_source_ref"] == {
        "body.p831": "post_treatment_execution",
        "body.p832": "post_treatment_execution",
        "body.p833": "non_enrollment_execution",
        "body.p835": "post_treatment_execution",
        "body.p837": "other_control_candidate",
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {
        "body.p837": ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]
    }
    assert set(config["candidate_required_markers_by_source_ref"]["body.p837"]) == {
        "开始",
        "结束",
        "剂量",
        "频率",
        "给药途径",
        "治疗方法",
        "适应症",
    }


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg75 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_75_ORDINAL)
    owned_75 = {u["source_ref"] for u in pkg75["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_75), "attached refs must not be owned by package 75"
    assert set(attached) == set(ATTACHED_REFS)


def test_known_targets_contain_no_official_rules(config: dict) -> None:
    rules = config["known_targets"]["official_rules"]
    assert rules == [], "第75包拥有来源不含任何官方入排规则"


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_75(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_75_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_75_ID
    assert plan["plan_id"] == PLAN_ID
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_attached_refs_ownership(config: dict, plan: dict) -> None:
    """p829/p830/流程表行/访视安排节点均为context-only；p749归第63包所有。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    never_owned = {
        "body.p829",
        "body.p830",
        "body.t5.r29",
        "body.t5.r30",
        "body.t5.r37",
        "body.t5.r38",
        "body.p855",
        "body.p866",
        "body.p875",
        "body.p883",
        "body.p884",
        "body.p885",
        "body.p931",
        "body.p932",
        "body.p933",
        "body.p934",
    }
    for ref in never_owned:
        assert ref not in owners, f"{ref} must stay context-only"
    assert owners.get("body.p749") == [63], "合并治疗定义由第63包拥有"


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
    assert "精确到分秒" in by_ref["body.p831"].excerpt
    assert "计划外PK样本" in by_ref["body.p832"].excerpt
    assert "中心实验室手册" in by_ref["body.p833"].excerpt
    assert "严密监测" in by_ref["body.p835"].excerpt
    assert "自签署ICF开始至研究结束" in by_ref["body.p837"].excerpt
    for ref in ("body.p829", "body.p830", "body.p885"):
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"


# ---------------------------------------------------------------------------
# flow table node separation
# ---------------------------------------------------------------------------


def test_flow_rows_cell_level_markers(structure_by_ref: dict) -> None:
    # PK采血行：筛选/基线/D1（W0）均无标记，治疗期W2起有X
    for col in (FLOW_COLUMN_SCREENING, FLOW_COLUMN_BASELINE, FLOW_COLUMN_D1):
        assert structure_by_ref[f"body.t5.r29.{col}.p0"]["text"] == "", col
    for col in ("c4", "c5", "c6", "c7", "c9"):
        assert structure_by_ref[f"body.t5.r29.{col}.p0"]["text"] == "X", col
    # IL-17A采血行：D1（W0）有X
    assert structure_by_ref["body.t5.r30.c1.p0"]["text"] == ""
    assert structure_by_ref["body.t5.r30.c2.p0"]["text"] == ""
    assert structure_by_ref["body.t5.r30.c3.p0"]["text"] == "X"
    # 合并治疗行：仅筛选列X
    assert structure_by_ref["body.t5.r37.c1.p0"]["text"] == "X"
    # 不良事件行：筛选/基线无标记，首个X在治疗期D1
    assert structure_by_ref["body.t5.r38.c1.p0"]["text"] == ""
    assert structure_by_ref["body.t5.r38.c2.p0"]["text"] == ""
    assert structure_by_ref["body.t5.r38.c3.p0"]["text"] == "X"


def test_flow_row_excerpts_in_coverage() -> None:
    coverage = _load_json(COVERAGE_PATH)
    by_ref = {u["source_ref"]: u for u in coverage["units"]}
    assert by_ref["body.t5.r29"]["excerpt"].startswith("PK采血^20")
    assert by_ref["body.t5.r30"]["excerpt"].startswith("IL-17A采血^21")
    assert by_ref["body.t5.r37"]["excerpt"].startswith("合并治疗^25")
    assert by_ref["body.t5.r38"]["excerpt"].startswith("不良事件^26")


# ---------------------------------------------------------------------------
# frozen procedure catalog: no PK / AE enrollment node
# ---------------------------------------------------------------------------


def _catalog_nodes(catalog: dict, label: str) -> list[dict]:
    return [item for item in catalog["items"] if item["label"] == label]


def test_procedure_catalog_nodes(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"

    il17 = _catalog_nodes(procedure_catalog, "IL-17A采血")
    assert len(il17) == 1
    assert il17[0]["review_stage"] == "baseline"
    assert il17[0]["visit_instance"] == "治疗期 / W0 / D1 / -"

    concomitant = _catalog_nodes(procedure_catalog, "合并治疗")
    assert len(concomitant) == 1
    assert concomitant[0]["review_stage"] == "screening"

    # PK采血与不良事件在入排及基线以前流程目录中没有任何节点
    assert _catalog_nodes(procedure_catalog, "PK采血") == []
    assert _catalog_nodes(procedure_catalog, "不良事件") == []
    assert all("PK" not in str(item["label"]) for item in procedure_catalog["items"])
    assert all("不良事件" not in str(item["label"]) for item in procedure_catalog["items"])


def test_catalog_has_no_enrollment_duty_for_sampling_or_monitoring(
    procedure_catalog: dict,
) -> None:
    labels = {str(item["label"]) for item in procedure_catalog["items"]}
    assert "PK采血" not in labels
    assert "不良事件" not in labels


# ---------------------------------------------------------------------------
# official matrix: 合并治疗 stays a must_record collection row, not eligibility
# ---------------------------------------------------------------------------


def test_concomitant_matrix_row_is_must_record_collection(matrix: dict) -> None:
    row = next(
        r for r in matrix["rows"] if r["matrix_row_id"] == CONCOMITANT_MATRIX_ROW_ID
    )
    obligations = row["obligations"]
    assert obligations and all(o.get("kind") == "must_record" for o in obligations)
    attainment = str(row.get("attainment_criteria_zh") or "")
    assert "合并治疗记录" in attainment
    assert "复核" in attainment
    # 资料收集义务不得表述为资格不通过条件
    for forbidden_phrase in ("不得入组", "不通过", "不符合", "不合格", "排除"):
        assert forbidden_phrase not in attainment, forbidden_phrase
    assert not row.get("condition_atoms"), "合并治疗行不应有条件原子"
    assert not (row.get("official_parent_code") or row.get("official_code")), (
        "合并治疗行不是IN/EX官方规则"
    )


def test_no_official_rule_anchors_package75_owned_spans(matrix: dict, plan: dict) -> None:
    pkg75 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_75_ORDINAL)
    owned_refs = {u["source_ref"] for u in pkg75["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第75包拥有来源为锚点"
            )


def test_known_targets_build_with_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert official == []
    assert len(procedures) == 1
    assert Counter(p.label for p in procedures) == {"合并治疗": 1}
    for proc in procedures:
        assert proc.source_excerpts and proc.source_excerpts[0]
    concomitant = [p for p in procedures if p.catalog_item_id == CONCOMITANT_MATRIX_ROW_ID]
    assert len(concomitant) == 1
    assert concomitant[0].review_stage.value == "screening"
    assert any("ICF" in (e or "") for e in concomitant[0].source_excerpts)


def test_unrelated_frozen_procedures_stay_in_read_only_closure(config: dict) -> None:
    assert "body.t5.r30" in config["attached_source_refs"]
    assert "body.t5.r37" in config["attached_source_refs"]
    target_ids = {
        item["catalog_item_id"]
        for item in config["known_targets"]["required_procedures"]
    }
    assert "procedure:6a29fdf2c85847fbe189e603656b214a" not in target_ids
    assert "procedure:de629323fe71cc5a52b15793aa06fc8a" not in target_ids


# ---------------------------------------------------------------------------
# workflow stages and D1 pre-dose distinction
# ---------------------------------------------------------------------------


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
    assert PACKAGE_75_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "中心实验室手册" in text
    assert "全程AE监测" in text
    assert "ICF后合并治疗收集" in text
    assert "计划外PK样本" in text
    assert "D1给药前" in text
    assert "父级盲态检查清单" in text
