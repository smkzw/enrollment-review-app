#!/usr/bin/env python3
"""Model-free Package 113 reference-tail / protocol-body authority regressions.

Locks the bibliographic-citation vs protocol-body authority boundary for
body.p1307 (DLQI citation) and body.p1308 (NMPA Drug Registration Regulation
citation) without inventing DLQI scoring, cutoffs, subject eligibility, or
drug-registration procedures from titles alone.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PHASE_CLOSURE) not in sys.path:
    sys.path.insert(0, str(PHASE_CLOSURE))

CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package113_reference_tail_evidence_authority_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cz-package113-reference-tail-evidence-authority-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package113-reference-tail-evidence-authority-boundary"
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
PACKAGE_ORDINAL = 113
PACKAGE_ID = "pap-d042355fa4845796808fa256"
PACKAGE112_ID = "pap-fa6b2b871b90b62bbfe81775"
PACKAGE114_ID = "pap-cd76207b0f3d157c2eaa66d6"

OWNED = ["body.p1307", "body.p1308"]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY: list[str] = []
EXPECTED_DISPOSITIONS = {
    "body.p1307": "non_enrollment_execution",
    "body.p1308": "non_enrollment_execution",
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
    "body.p1307": (
        "Finlay AY, Khan GK. Dermatology Life Quality Index (DLQI)--a simple "
        "practical measure for routine clinical use. Clin Exp Dermatol. "
        "1994;19:210–6."
    ),
    "body.p1308": "国家药品监督管理局.药品注册管理办法.2020.",
}
EXPECTED_UNIT_KINDS = {
    "body.p1307": "list_item",
    "body.p1308": "list_item",
}
EXPECTED_SPANS = {
    "body.p1307": ["body.p1307"],
    "body.p1308": ["body.p1308"],
}
SOURCE_ORDERS = [32030, 32040]
HEADING_PATHS = {ref: ["参考文献"] for ref in OWNED}
EXPECTED_OWNER_MAP = {
    "body.p1306": 112,
    "body.p1307": 113,
    "body.p1308": 113,
    "body.p1310": 114,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1307": "bibliographic_citation_dlqi_not_protocol_clause",
    "body.p1308": (
        "bibliographic_citation_drug_registration_regulation_not_protocol_clause"
    ),
}
EXPECTED_OWNED_SOURCE_SPAN_IDS = sorted(
    {span for spans in EXPECTED_SPANS.values() for span in spans}
)
EXCLUDED_UNOWNED_STRUCTURE_REFS = ["body.p1309"]
DLQI_PROTOCOL_AUTHORITY_REFS = [
    "body.p826",
    "body.p827",
    "body.p1386",
    "body.p1417",
    "body.p1418",
    "body.p1419",
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


def test_config_contract_keeps_citations_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package113-reference-tail-evidence-authority-boundary"
    )
    assert config["task_id"] == "phase5-slice61cz-20260830"
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
            "manifest:slice61cz-package113-reference-tail-evidence-authority-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cz-package113-reference-tail-evidence-authority-boundary"
        ),
    }


def test_config_preserves_reference_tail_vs_protocol_body_authority(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "参考文献题录",
        "非方案执行条款",
        "方案正文仍是执行权威",
        "non_enrollment_execution",
        "不新增领域枚举",
        "DLQI",
        "Dermatology Life Quality Index",
        "药品注册管理办法",
        "Package 112",
        "Package 114",
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

    dlqi = semantics["body.p1307"]
    assert "DLQI" in dlqi["exception_rule"] or "DLQI" in dlqi["base_rule"]
    assert "非方案执行条款" in dlqi["exception_rule"] or "不是方案执行条款" in dlqi[
        "exception_rule"
    ]
    assert "方案正文仍是执行权威" in dlqi["exception_rule"]
    assert "评分算法" in dlqi["exception_rule"] or "切点" in dlqi["exception_rule"]

    regulation = semantics["body.p1308"]
    assert "药品注册管理办法" in regulation["exception_rule"] or (
        "药品注册管理办法" in regulation["base_rule"]
    )
    assert "方案正文仍是执行权威" in regulation["exception_rule"]
    assert "注册程序" in regulation["exception_rule"] or "执行流程" in regulation[
        "exception_rule"
    ]


def test_source_identity_blocks_citation_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "DLQI题录反向生成评分算法",
        "DLQI题录反向生成切点阈值",
        "Dermatology Life Quality Index题录误作受试者资格",
    } <= set(forbidden["body.p1307"])
    assert {
        "药品注册管理办法题录反向生成注册程序",
        "药品注册管理办法题录误作受试者资格",
        "NMPA注册办法题录误作申办方执行流程",
    } <= set(forbidden["body.p1308"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "DLQI" in "；".join(checks["body.p1307"])
    assert "非方案执行条款" in "；".join(checks["body.p1307"])
    assert "药品注册管理办法" in "；".join(checks["body.p1308"])
    assert "非方案执行条款" in "；".join(checks["body.p1308"])


def test_phase_applicability_explains_citations_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "参考文献",
        "方案正文仍是执行权威",
        "DLQI",
        "药品注册管理办法",
        "不是单例受试者",
        "Package 112",
        "Package 114",
        "p1306",
        "p1310",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得以other_control_candidate强挂" in batch_reason
    assert "非方案执行条款" in batch_reason
    assert "不新增领域枚举" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )
    assert config["later_package_boundary"]["excluded_unowned_structure_refs"] == (
        EXCLUDED_UNOWNED_STRUCTURE_REFS
    )


def test_frozen_plan_owns_exact_package113_units(plan: dict, config: dict) -> None:
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
    assert len(package["context_units"]) == 38

    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert owner_by_ref["body.p1306"] == 112
    assert owner_by_ref["body.p1310"] == 114
    assert "body.p1309" not in owner_by_ref
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(owner_by_ref)
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_real_dlqi_authority_and_package114_stay_outside_reference_tail(
    plan: dict,
    config: dict,
) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert [owner_by_ref[ref] for ref in DLQI_PROTOCOL_AUTHORITY_REFS] == [
        74,
        74,
        125,
        128,
        128,
        128,
    ]

    package114 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == 114
    )
    package114_refs = {unit["source_ref"] for unit in package114["owned_units"]}
    assert package114["package_id"] == PACKAGE114_ID
    assert "body.p1310" in package114_refs

    package113_inputs = set(config["owned_source_refs"])
    package113_inputs.update(config["attached_source_refs"])
    assert set(DLQI_PROTOCOL_AUTHORITY_REFS).isdisjoint(package113_inputs)
    assert package114_refs.isdisjoint(package113_inputs)


def test_blank_separator_p1309_is_explicitly_excluded(
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
    package113 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package113["context_units"]]
    assert len(context_refs) == 38
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1307" not in context_refs
    assert "body.p1308" not in context_refs
    assert "body.p1310" not in context_refs
    assert "body.p1309" not in context_refs
    assert "body.p1306" in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1306"] == [112]
    assert owners["body.p1307"] == [113]
    assert owners["body.p1308"] == [113]
    assert owners["body.p1310"] == [114]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package113["context_units"]
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


def test_resolver_keeps_package113_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 2
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 2
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
        "body.p1306",
        "body.p1310",
        "body.p1295",
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
    attack["owned_source_refs"] = ["body.p1307"]
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
    assert summary["owned_count"] == 2
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 2
    assert summary["lookup_counts"] == {"frozen_plan_owned": 2}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 2
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 2
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 2
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 2
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == EXPECTED_OWNED_SOURCE_SPAN_IDS
    assert batch["context_source_span_ids"] == []
    assert batch["structural_only_structure_unit_ids"] == []
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

    assert prompt_meta["owned_count"] == 2
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
        "Dermatology Life Quality Index",
        "DLQI",
        "Finlay AY",
        "药品注册管理办法",
        "国家药品监督管理局",
    ):
        assert marker in prompt
    for ref in (
        "body.p1306",
        "body.p1310",
        "body.p1295",
        *DLQI_PROTOCOL_AUTHORITY_REFS,
        PACKAGE112_ID,
        PACKAGE114_ID,
    ):
        assert ref not in prompt
    for ref in EXCLUDED_UNOWNED_STRUCTURE_REFS:
        assert f'"source_ref":"{ref}"' not in prompt
    assert "DLQI评分算法" not in prompt
    assert "注册程序" not in prompt or "药品注册管理办法.2020" in prompt
    assert "方案执行阈值" not in prompt


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
        ("body.p1307", "DLQI题录反向生成评分算法"),
        ("body.p1307", "DLQI题录反向生成切点阈值"),
        ("body.p1307", "Dermatology Life Quality Index题录误作受试者资格"),
        ("body.p1307", "DLQI评分在0-30分之间"),
        ("body.p1307", "DLQI总分至少4分视为具有临床重要性"),
        ("body.p1307", "DLQI评分细则见附录6"),
        ("body.p1308", "药品注册管理办法题录反向生成注册程序"),
        ("body.p1308", "药品注册管理办法题录误作受试者资格"),
        ("body.p1308", "NMPA注册办法题录误作申办方执行流程"),
        ("body.p1308", "依据药品注册管理办法提交临床试验申请"),
        ("body.p1308", "准备药品注册申报资料"),
    ],
)
def test_hydrated_gate_rejects_citation_as_subject_control(
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
        "pap-d042355fa4845796808fa256",
        "body.p1307",
        "body.p1308",
        "body.p1306",
        "body.p1309",
        "body.p1310",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "参考文献题录",
        "非方案执行条款",
        "方案正文仍是执行权威",
        "DLQI",
        "药品注册管理办法",
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
