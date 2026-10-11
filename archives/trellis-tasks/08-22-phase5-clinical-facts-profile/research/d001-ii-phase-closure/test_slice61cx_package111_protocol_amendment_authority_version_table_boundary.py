#!/usr/bin/env python3
"""Model-free Package 111 protocol amendment/version-table regressions.

The tests freeze Package 111 ownership for body.p1291, body.p1292,
body.t15.r0 and body.t15.r1, keep the 37 context units read-only, preserve
Package 110/112 boundaries, and prove that protocol-amendment authority plus
the V1.0 initial version table are not inverted into subject eligibility while
any real pre-participation control would still be retained if present in
source.

No model, transport, subject/OCR/Profile surface, or publication is involved.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PHASE_CLOSURE) not in sys.path:
    sys.path.insert(0, str(PHASE_CLOSURE))

CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package111_protocol_amendment_authority_version_table_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cx-package111-protocol-amendment-authority-version-table-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package111-protocol-amendment-authority-version-table-boundary"
)
FREEZE_DIR = (
    ROOT
    / "artifacts"
    / "phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830"
)
PLAN_PATH = FREEZE_DIR / "frozen_phase_plan.json"
COVERAGE_PATH = FREEZE_DIR / "coverage_manifest.json"
STRUCTURE_PATH = (
    FREEZE_DIR
    / "structure"
    / "blobs"
    / "protocol_blocks"
    / "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json"
)

EXPECTED_PROTOCOL_SHA256 = (
    "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
)
EXPECTED_PLAN_SHA256 = (
    "92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4"
)
EXPECTED_STRUCTURE_SHA256 = (
    "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
)
PLAN_ID = "papl-e17d498106b6f71f440ff2be"
PACKAGE_ORDINAL = 111
PACKAGE_ID = "pap-214ce50fd89fb1998521c4c3"
PACKAGE110_ID = "pap-7358ad349433c3c08aacc5f1"
PACKAGE112_ID = "pap-fa6b2b871b90b62bbfe81775"

OWNED = [
    "body.p1291",
    "body.p1292",
    "body.t15.r0",
    "body.t15.r1",
]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = [
    "body.p1291",
    "body.t15.r0",
]
GOVERNANCE = [
    "body.p1292",
    "body.t15.r1",
]
EXPECTED_DISPOSITIONS = {
    ref: "non_enrollment_execution" for ref in GOVERNANCE
}
BASE_FORBIDDEN_MARKERS = [
    "筛选必做",
    "基线必做",
    "入组前必查",
    "不得入组",
    "排除标准",
    "入排不通过",
    "发布控制点",
]
EXPECTED_EXCERPTS = {
    "body.p1291": "方案修订",
    "body.p1292": (
        "方案任何的必须的改变，都需以方案修订形式进行，并需在获得申办者、主要研究者签字同意后"
        "提交伦理委员会审批或备案。"
    ),
    "body.t15.r0": "版本 | 日期 | 变更说明 | 简要理由",
    "body.t15.r1": "V1.0 | 2025年12月10日 | NA | NA",
}
EXPECTED_UNIT_KINDS = {
    "body.p1291": "paragraph",
    "body.p1292": "paragraph",
    "body.t15.r0": "table_header",
    "body.t15.r1": "table_row",
}
EXPECTED_SPANS = {
    "body.p1291": ["body.p1291"],
    "body.p1292": ["body.p1292"],
    "body.t15.r0": [
        "body.t15.r0.c0.p0",
        "body.t15.r0.c1.p0",
        "body.t15.r0.c2.p0",
        "body.t15.r0.c3.p0",
    ],
    "body.t15.r1": [
        "body.t15.r1.c0.p0",
        "body.t15.r1.c1.p0",
        "body.t15.r1.c2.p0",
        "body.t15.r1.c3.p0",
    ],
}
SOURCE_ORDERS = [
    31540,
    31550,
    31571,
    31611,
]
HEADING_PATHS = {
    ref: ["方案修订"] for ref in OWNED
}
EXPECTED_OWNER_MAP = {
    "body.p1290": 110,
    "body.p1291": 111,
    "body.p1292": 111,
    "body.t15.r0": 111,
    "body.t15.r1": 111,
    "body.p1295": 112,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1291": "protocol_amendment_section_heading",
    "body.p1292": "protocol_amendment_authority_sponsor_pi_ethics_governance",
    "body.t15.r0": "protocol_version_table_header_structural_only",
    "body.t15.r1": "protocol_initial_version_v1_record_not_historical_amendment",
}
EXPECTED_OWNED_SOURCE_SPAN_IDS = sorted(
    {span for spans in EXPECTED_SPANS.values() for span in spans}
)
EXCLUDED_UNOWNED_STRUCTURE_REFS = [
    "body.t15",
    *[
        f"body.t15.r{row}.c{column}.p0"
        for row in range(2, 8)
        for column in range(4)
    ],
    "body.p1293",
    "body.p1294",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def config() -> dict:
    return _load(CONFIG_PATH)


@pytest.fixture(scope="module")
def plan() -> dict:
    return _load(PLAN_PATH)


@pytest.fixture(scope="module")
def coverage() -> dict:
    return _load(COVERAGE_PATH)


def test_config_contract_keeps_amendment_governance_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package111-protocol-amendment-authority-version-table-boundary"
    )
    assert config["task_id"] == "phase5-slice61cx-20260830"
    assert config["worker"] == "codex-parent"
    assert config["study_phase"] == "phase_ii"
    assert config["expected_package_ordinal"] == PACKAGE_ORDINAL
    assert config["expected_package_id"] == PACKAGE_ID
    assert config["expected_protocol_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert config["batching"]["mode"] == "single_batch_with_known_targets"

    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == []
    assert config["forbidden_candidate_source_refs"] == FORBIDDEN_CANDIDATES
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL_ONLY
    assert config["attached_structural_only_source_refs"] == []
    assert config["expected_disposition_by_source_ref"] == EXPECTED_DISPOSITIONS
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["owned_visit_instances_by_source_ref"] == {}
    assert config["owned_procedure_semantic_families_by_source_ref"] == {}
    assert config["owned_required_action_kinds_by_source_ref"] == {}
    assert config["owned_required_procedure_target_ids_by_source_ref"] == {}
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["phase_applicability"]["disposition"] == (
        "selected_phase_applicable"
    )
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": (
            "manifest:slice61cx-package111-protocol-amendment-authority-version-table-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cx-package111-protocol-amendment-authority-version-table-boundary"
        ),
    }


def test_config_preserves_four_layer_amendment_version_semantics(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "方案修订形式",
        "申办者",
        "主要研究者",
        "伦理委员会",
        "审批或备案",
        "版本",
        "日期",
        "变更说明",
        "简要理由",
        "V1.0",
        "2025年12月10日",
        "NA",
        "唯一授权标准变更形式",
        "不得把V1.0/NA臆造为既往修订",
        "Package 110",
        "Package 112",
        "required_candidate_source_refs为空",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
    ):
        assert phrase in combined

    semantics = config["exception_semantics_by_source_ref"]
    for ref, role in SEMANTIC_ROLES.items():
        assert semantics[ref]["semantic_role"] == role
        assert semantics[ref]["base_rule"] == EXPECTED_EXCERPTS[ref]

    p1292 = semantics["body.p1292"]
    assert "唯一授权标准变更机制" in p1292["exception_rule"]
    assert "受试者级入排条件" in p1292["exception_rule"]
    assert "方案修订形式" in p1292["preserve_keywords"]

    t15r1 = semantics["body.t15.r1"]
    assert "初始版本" in t15r1["exception_rule"]
    assert "既往修订" in t15r1["exception_rule"]
    assert "V1.0" in t15r1["preserve_keywords"]
    assert "NA" in t15r1["preserve_keywords"]


def test_source_identity_blocks_eligibility_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "方案修订标题决定受试者资格",
        "方案修订章节误作入排控制",
    } <= set(forbidden["body.p1291"])
    assert {
        "申办者签字同意决定单例资格",
        "主要研究者签字决定入排",
        "伦理委员会审批误作受试者资格",
        "方案修订签字义务候选化为入排条件",
    } <= set(forbidden["body.p1292"])
    assert {
        "版本表头决定受试者资格",
        "变更说明列误作入排控制",
        "表头与数据行混淆为既往修订",
    } <= set(forbidden["body.t15.r0"])
    assert {
        "V1.0误读为既往修订",
        "NA臆造变更说明",
        "NA臆造简要理由",
        "初始版本记录误作修订历史",
    } <= set(forbidden["body.t15.r1"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "方案修订" in "；".join(checks["body.p1291"])
    assert "方案修订形式" in "；".join(checks["body.p1292"])
    assert "伦理委员会" in "；".join(checks["body.p1292"])
    assert "版本" in "；".join(checks["body.t15.r0"])
    assert "V1.0" in "；".join(checks["body.t15.r1"])
    assert "既往修订" in "；".join(checks["body.t15.r1"])


def test_phase_applicability_explains_governance_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "方案修订",
        "申办者",
        "主要研究者",
        "伦理委员会",
        "V1.0",
        "不是单例受试者",
        "Package 110",
        "Package 112",
        "p1290",
        "p1295",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得以other_control_candidate强挂" in batch_reason
    assert "V1.0/NA臆造为既往修订" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )
    assert config["later_package_boundary"]["excluded_unowned_structure_refs"] == (
        EXCLUDED_UNOWNED_STRUCTURE_REFS
    )


def test_frozen_plan_owns_exact_package111_units(plan: dict, config: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    packages = [
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    ]
    assert len(packages) == 1
    package = packages[0]
    assert package["package_id"] == PACKAGE_ID
    assert package["selected_phase"] == "phase_ii"
    assert [unit["source_ref"] for unit in package["owned_units"]] == OWNED
    assert len(package["context_units"]) == 37

    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert owner_by_ref["body.p1290"] == 110
    assert owner_by_ref["body.p1295"] == 112
    assert "body.p1293" not in owner_by_ref
    assert "body.p1294" not in owner_by_ref
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(owner_by_ref)
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_empty_version_rows_and_blank_separators_are_explicitly_excluded(
    plan: dict,
    coverage: dict,
    config: dict,
) -> None:
    structure = json.loads(STRUCTURE_PATH.read_text(encoding="utf-8"))
    structure_by_ref = {row["source_ref"]: row for row in structure}
    coverage_refs = {unit["source_ref"] for unit in coverage["units"]}
    owned_refs = {
        unit["source_ref"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }

    assert config["later_package_boundary"]["excluded_unowned_structure_refs"] == (
        EXCLUDED_UNOWNED_STRUCTURE_REFS
    )
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).issubset(structure_by_ref)
    assert all(
        not structure_by_ref[ref].get("text", "").strip()
        for ref in EXCLUDED_UNOWNED_STRUCTURE_REFS
    )
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(coverage_refs)
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(owned_refs)
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(
        config["owned_source_refs"] + config["attached_source_refs"]
    )


def test_context_units_remain_read_only_and_unowned_partition(
    plan: dict,
    config: dict,
) -> None:
    package111 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package111["context_units"]]
    assert len(context_refs) == 37
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1290" not in context_refs
    assert "body.p1295" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1290"] == [110]
    assert owners["body.p1291"] == [111]
    assert owners["body.p1292"] == [111]
    assert owners["body.t15.r0"] == [111]
    assert owners["body.t15.r1"] == [111]
    assert owners["body.p1295"] == [112]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package111["context_units"]
        if unit["source_ref"] not in owners
    ]
    assert len(expected_unowned_context_refs) == 26
    assert config["later_package_boundary"]["unowned_context_source_refs"] == (
        expected_unowned_context_refs
    )


def test_coverage_preserves_exact_excerpts_order_kinds_and_spans(
    coverage: dict,
) -> None:
    units = {unit["source_ref"]: unit for unit in coverage["units"]}
    assert [units[ref]["source_order"] for ref in ORDERED] == SOURCE_ORDERS
    for ref in ORDERED:
        unit = units[ref]
        assert unit["excerpt"] == EXPECTED_EXCERPTS[ref]
        assert unit["phase_scopes"] == ["unknown"]
        assert unit["study_phase"] == "phase_ii"
        assert unit["unit_kind"] == EXPECTED_UNIT_KINDS[ref]
        assert unit["source_span_ids"] == EXPECTED_SPANS[ref]
        assert unit["member_source_refs"] == EXPECTED_SPANS[ref]
        assert unit["heading_path"] == HEADING_PATHS[ref]


def test_resolver_keeps_package111_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 4
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 4
    for row in rows:
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert list(row.source_span_ids) == EXPECTED_SPANS[row.source_ref]
        assert list(row.member_source_refs) == EXPECTED_SPANS[row.source_ref]
    assert [row.excerpt for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1290",
        "body.p1295",
        "body.p1281",
    ],
)
def test_resolver_rejects_cross_package_owned_identity_bypasses(
    config: dict,
    source_ref: str,
) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    attack = deepcopy(config)
    attack["owned_source_refs"] = [source_ref]
    with pytest.raises(SystemExit):
        _resolve_units(attack)


def test_resolver_rejects_coverage_lookup_bypass(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    attack = deepcopy(config)
    attack["owned_source_refs"] = ["body.p1292"]
    attack["unit_lookup"] = ["coverage_manifest"]
    with pytest.raises(SystemExit):
        _resolve_units(attack)


def test_model_free_prepare_has_owned_rows_only(config: dict) -> None:
    command = [
        str(ROOT / ".venv" / "bin" / "python"),
        str(PHASE_CLOSURE / "slice59n_representative_group_control_replay.py"),
        "--config",
        str(CONFIG_PATH),
        "--dry-run",
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)

    summary = _load(PREPARE_DIR / "replay-summary.json")
    rows = _load(PREPARE_DIR / "source_rows.json")
    qc = _load(PREPARE_DIR / "clinical-qc.json")
    batch = _load(PREPARE_DIR / "execution" / "batch.json")
    prompt_meta = _load(PREPARE_DIR / "execution" / "prompt-meta.json")
    provenance = _load(PREPARE_DIR / "freeze_provenance.json")
    prompt = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")

    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 4
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 4
    assert summary["lookup_counts"] == {"frozen_plan_owned": 4}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 4
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 4
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 4
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 4
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == EXPECTED_OWNED_SOURCE_SPAN_IDS
    assert batch["context_source_span_ids"] == []
    structural_indexes = [ORDERED.index(ref) for ref in STRUCTURAL_ONLY]
    assert batch["structural_only_structure_unit_ids"] == [
        owned_ids[index] for index in structural_indexes
    ]
    assert batch["pre_enrollment_structure_unit_ids"] == []
    assert batch["owned_visit_instance_by_structure_unit_id"] == {}
    assert batch["owned_procedure_semantic_families_by_structure_unit_id"] == {}
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {}
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {}
    assert batch["known_official_targets"] == []
    assert batch["known_procedure_targets"] == []
    assert [
        stage["workflow_stage_id"] for stage in batch["known_workflow_stage_targets"]
    ] == ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]

    assert prompt_meta["owned_count"] == 4
    assert prompt_meta["attached_count"] == 0
    assert prompt_meta["batching_mode"] == "single_batch_with_known_targets"
    assert provenance["config_sha256"] == _sha256(CONFIG_PATH)
    assert provenance["frozen_plan_sha256"] == EXPECTED_PLAN_SHA256
    assert provenance["protocol_document_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert provenance["claims_complete"] is False

    assert [row["source_ref"] for row in qc["rows"]] == ORDERED
    assert all(row["agent_candidates"] == [] for row in qc["rows"])
    assert all(row["codex_accepted"] is None for row in qc["rows"])
    assert qc["runner_status"] == "dry_run"
    assert qc["claims_complete"] is False
    assert qc["gate"] == {
        "accepted": False,
        "skipped": True,
        "reason": "dry-run prepare only; publication gate requires hydrated Agent output",
    }
    assert qc["reject_gates"]["prepare_accepted"] is True
    assert qc["reject_gates"]["hydrated_skipped"] is True

    for ref in ORDERED:
        assert ref in prompt
    for marker in (
        "方案修订",
        "方案修订形式",
        "申办者",
        "主要研究者",
        "伦理委员会",
        "审批或备案",
        "版本",
        "日期",
        "变更说明",
        "简要理由",
        "V1.0",
        "2025年12月10日",
        "NA",
    ):
        assert marker in prompt
    for ref in (
        "body.p1290",
        "body.p1295",
        PACKAGE110_ID,
        PACKAGE112_ID,
    ):
        assert ref not in prompt
    for ref in EXCLUDED_UNOWNED_STRUCTURE_REFS:
        assert f'"source_ref":"{ref}"' not in prompt
    assert "既往修订历史" not in prompt


def _gate_inputs(config: dict) -> tuple[list[dict], dict[str, str], list[dict]]:
    from slice59n_representative_group_control_replay import _resolve_units

    resolved = _resolve_units(config)
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
        for row in resolved
    ]
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}
    dispositions = [
        {
            "structure_unit_id": unit_by_ref[ref],
            "disposition": disposition,
        }
        for ref, disposition in EXPECTED_DISPOSITIONS.items()
    ]
    return rows, unit_by_ref, dispositions


def test_deterministic_gate_accepts_non_enrollment_dispositions(
    config: dict,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": [], "dispositions": dispositions},
        allowed_structure_unit_ids=[unit_by_ref[ref] for ref in OWNED],
        required_candidate_source_refs=[],
        forbidden_candidate_source_refs=FORBIDDEN_CANDIDATES,
        expected_disposition_by_source_ref=EXPECTED_DISPOSITIONS,
        expected_workflow_stage_ids_by_source_ref={},
        candidate_forbidden_markers_by_source_ref=config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        candidate_required_markers_by_source_ref={},
    )
    assert issues == []


@pytest.mark.parametrize(
    ("source_ref", "title"),
    [
        ("body.p1291", "方案修订标题决定受试者资格"),
        ("body.p1292", "申办者签字同意决定单例资格"),
        ("body.p1292", "主要研究者签字决定入排"),
        ("body.p1292", "伦理委员会审批误作受试者资格"),
        ("body.p1292", "方案修订签字义务候选化为入排条件"),
        ("body.t15.r0", "版本表头决定受试者资格"),
        ("body.t15.r0", "变更说明列误作入排控制"),
        ("body.t15.r0", "表头与数据行混淆为既往修订"),
        ("body.t15.r1", "V1.0误读为既往修订"),
        ("body.t15.r1", "NA臆造变更说明"),
        ("body.t15.r1", "NA臆造简要理由"),
        ("body.t15.r1", "初始版本记录误作修订历史"),
    ],
)
def test_hydrated_gate_rejects_governance_as_subject_control(
    config: dict,
    source_ref: str,
    title: str,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[source_ref]],
                    "title": title,
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        },
        allowed_structure_unit_ids=[unit_by_ref[ref] for ref in OWNED],
        required_candidate_source_refs=[],
        forbidden_candidate_source_refs=FORBIDDEN_CANDIDATES,
        expected_disposition_by_source_ref=EXPECTED_DISPOSITIONS,
        expected_workflow_stage_ids_by_source_ref={},
        candidate_forbidden_markers_by_source_ref=config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        candidate_required_markers_by_source_ref={},
    )
    assert any(
        issue.code == "CONTROL_DUPLICATE_RETAINED"
        and issue.source_refs == (source_ref,)
        for issue in issues
    ), f"来源身份门禁未拦截 {source_ref} 的候选化改写"


def test_checklist_records_scope_zero_candidate_and_stop_conditions() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    for phrase in (
        "papl-e17d498106b6f71f440ff2be",
        "pap-214ce50fd89fb1998521c4c3",
        "body.p1291",
        "body.p1292",
        "body.t15.r0",
        "body.t15.r1",
        "body.p1290",
        "body.p1295",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "方案修订形式",
        "伦理委员会",
        "V1.0",
        "不得把 V1.0/NA 臆造为既往修订",
        "不得调用临床语义模型",
        "不得发布 control point",
        "Patient Profile",
        "parent clinical acceptance",
        "claims_complete=false",
        "零候选不是预设",
        "也不得丢失任何真实前置控制",
    ):
        assert phrase in text


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256(STRUCTURE_PATH) == EXPECTED_STRUCTURE_SHA256
    assert CONFIG_PATH.exists()
    assert CHECKLIST_PATH.exists()
