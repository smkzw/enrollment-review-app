#!/usr/bin/env python3
"""Slice61bk model-free source-closure regressions.

Locks the D001 II efficacy scoring representative group (frozen plan package
74) to its authoritative sources before any semantic replay decision:

- config contract and role partition
- owned refs == frozen plan package 74; attached refs stay read-only
- IN-04 known target matches the frozen control matrix (no DLQI rule)
- flow-table cell-level markers (screening / baseline / D1 separation)
- frozen procedure catalog nodes (DLQI only has a D1 pre-dose node)
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
CONFIG_PATH = CONFIG_DIR / "representative_group_efficacy_scoring.v1.json"
CHECKLIST_PATH = (
    PHASE_CLOSURE / "slice61bk-efficacy-baseline-source-closure-parent-checklist.md"
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
PACKAGE_74_ORDINAL = 74
PACKAGE_74_ID = "pap-ddea6dc1bab6691aaace01bc"

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(819, 828)]
TITLE_REFS = ["body.p819", "body.p820", "body.p822", "body.p824", "body.p826"]
METHOD_REFS = ["body.p821", "body.p823", "body.p825", "body.p827"]


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
    assert config["group_id"] == "d001-ii-efficacy-scoring"
    assert config["task_id"] == "phase5-slice61bk-20260829"
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
    assert structural == forbidden == set(TITLE_REFS)
    assert pre_enrollment == required == set(METHOD_REFS)
    assert pre_enrollment <= owned and structural <= owned
    assert required.isdisjoint(forbidden)


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg74 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_74_ORDINAL)
    owned_74 = {u["source_ref"] for u in pkg74["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_74), "attached refs must not be owned by package 74"
    expected_read_only = {
        "body.t5.r22",
        "body.t5.r23",
        "body.t5.r24",
        "body.t5.r25",
        "body.p316",
        "body.p633",
        "body.p634",
        "body.p635",
        "body.p636",
        "body.p885",
    }
    assert set(attached) == expected_read_only


# ---------------------------------------------------------------------------
# frozen plan ownership
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_74(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_74_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_74_ID
    assert plan["plan_id"] == "papl-40b1237a22e538a278b4fd5e"
    assert pkg["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_in04_owned_by_package_51(plan: dict) -> None:
    for ref in ("body.p633", "body.p634", "body.p635", "body.p636"):
        owners = [
            p["package_ordinal"]
            for p in plan["packages"]
            if any(u["source_ref"] == ref for u in p["owned_units"])
        ]
        assert owners == [51], f"{ref} ownership drifted"


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------


def test_resolve_units_roles_and_method_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(
        config["attached_source_refs"]
    )
    for ref in OWNED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"
    assert "附录4" in by_ref["body.p821"].excerpt
    assert "附录5" in by_ref["body.p823"].excerpt
    assert "疗效评价SOP" in by_ref["body.p825"].excerpt
    assert "附录6" in by_ref["body.p827"].excerpt
    for ref in ("body.p633", "body.p634", "body.p635", "body.p636"):
        assert by_ref[ref].package_ordinal == 51


# ---------------------------------------------------------------------------
# IN-04 known target vs frozen matrix
# ---------------------------------------------------------------------------


def test_in04_known_target_matches_matrix(config: dict, matrix: dict) -> None:
    rules = config["known_targets"]["official_rules"]
    assert len(rules) == 1
    target = rules[0]
    assert target["catalog_item_id"] == "pcm-row-60a9e564dea57508635a69e8"
    assert target["official_code"] == "IN-04"
    spans = target["source_span_ids"]
    assert spans == sorted(set(spans))

    row = next(
        r for r in matrix["rows"] if r["matrix_row_id"] == "pcm-row-60a9e564dea57508635a69e8"
    )
    assert row["official_parent_code"] == "IN-04"
    anchors = {a["source_ref"]: a for a in row["source_anchors"]}
    assert set(anchors) == {"body.p633", "body.p634", "body.p635", "body.p636"}
    matrix_spans = sorted(
        span for a in row["source_anchors"] for span in a["source_span_ids"]
    )
    assert spans == matrix_spans

    excerpts = [str(a["verbatim_excerpt"]) for a in row["source_anchors"]]
    joined = "\n".join(excerpts)
    assert "≥12分" in joined
    assert "≥3分" in joined
    assert "≥10%" in joined
    assert "DLQI" not in joined


def test_matrix_has_no_dlqi_official_rule(matrix: dict) -> None:
    titles = [str(r.get("title_zh") or "") for r in matrix["rows"]]
    assert all("DLQI" not in title for title in titles)
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            if str(anchor.get("source_ref")) in {"body.p633", "body.p634", "body.p635", "body.p636"}:
                assert row["matrix_row_id"] == "pcm-row-60a9e564dea57508635a69e8"


# ---------------------------------------------------------------------------
# flow table node separation
# ---------------------------------------------------------------------------


def test_flow_rows_cell_level_markers(structure_by_ref: dict) -> None:
    for ref in ("body.t5.r22", "body.t5.r23", "body.t5.r24"):
        assert structure_by_ref[f"{ref}.c1.p0"]["text"] == "X"
        assert structure_by_ref[f"{ref}.c2.p0"]["text"] == "（X）"
    dlqi = structure_by_ref
    assert dlqi["body.t5.r25.c1.p0"]["text"] == ""
    assert dlqi["body.t5.r25.c2.p0"]["text"] == ""
    assert dlqi["body.t5.r25.c3.p0"]["text"] == "X"


def test_flow_row_aggregates_in_coverage() -> None:
    coverage = _load_json(COVERAGE_PATH)
    by_ref = {u["source_ref"]: u for u in coverage["units"]}
    for ref in ("body.t5.r22", "body.t5.r23", "body.t5.r24"):
        assert "（X）" in by_ref[ref]["excerpt"]
    dlqi = by_ref["body.t5.r25"]["excerpt"]
    assert dlqi.startswith("DLQI评分")
    assert "（X）" not in dlqi


# ---------------------------------------------------------------------------
# frozen procedure catalog nodes
# ---------------------------------------------------------------------------


def _catalog_nodes(catalog: dict, label: str) -> list[dict]:
    return [item for item in catalog["items"] if item["label"] == label]


def test_procedure_catalog_nodes(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for label in ("PASI评分", "PGA评分", "BSA评分"):
        nodes = _catalog_nodes(procedure_catalog, label)
        stages = sorted((n["review_stage"], n["visit_instance"]) for n in nodes)
        assert len(nodes) == 3, (label, stages)
        assert stages == [
            ("baseline", "治疗期 / W0 / D1 / -"),
            ("baseline", "筛选期(D-28~D-1) / 基线 / D≤-7 / -"),
            ("screening", "筛选期(D-28~D-1) / 筛选 / W-4~W-1 / D-28~D-1 / -"),
        ], (label, stages)

    dlqi = _catalog_nodes(procedure_catalog, "DLQI评分")
    assert len(dlqi) == 1
    assert dlqi[0]["review_stage"] == "baseline"
    assert dlqi[0]["visit_instance"] == "治疗期 / W0 / D1 / -"

    review = _catalog_nodes(procedure_catalog, "入排标准审核")
    assert sorted(n["review_stage"] for n in review) == ["baseline", "baseline", "screening"]


# ---------------------------------------------------------------------------
# workflow stages and known targets build
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


def test_known_targets_build_with_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert len(official) == 1
    assert official[0].official_code == "IN-04"
    assert len(official[0].source_excerpts) == len(official[0].source_span_ids) == 4
    assert any("≥12分" in (e or "") for e in official[0].source_excerpts)

    assert len(procedures) == 11
    assert Counter(p.label for p in procedures) == {
        "PASI评分": 3,
        "PGA评分": 3,
        "BSA评分": 3,
        "DLQI评分": 1,
        "入排标准审核": 1,
    }
    for proc in procedures:
        assert proc.source_excerpts and proc.source_excerpts[0]
    for label in ("PASI评分", "PGA评分", "BSA评分"):
        assert {
            (p.review_stage.value, p.visit_instance)
            for p in procedures
            if p.label == label
        } == {
            ("screening", "筛选访视"),
            ("baseline", "基线访视"),
            ("baseline", "D1给药前"),
        }
    dlqi = [p for p in procedures if p.label == "DLQI评分"]
    assert len(dlqi) == 1
    assert dlqi[0].visit_instance == "D1给药前"
    assert dlqi[0].review_stage.value == "baseline"
    assert dlqi[0].source_excerpts == ["DLQI评分"]


# ---------------------------------------------------------------------------
# fingerprints and checklist freeze
# ---------------------------------------------------------------------------


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    coverage = _load_json(COVERAGE_PATH)
    assert coverage["protocol_document_sha256"] == EXPECTED_DOCX_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "papl-40b1237a22e538a278b4fd5e" in text
    assert PACKAGE_74_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "IN-04" in text and "DLQI" in text
    assert "D1给药前" in text
    assert "父级盲态检查清单" in text
