#!/usr/bin/env python3
"""Model-free Package 104 interim-analysis governance boundary regressions.

This module freezes the D001 II package 104 source closure before any semantic
replay decision.  It distinguishes study-level cumulative-data governance,
IDMC recommendation, sponsor study decision, and an independent interim SAP
from subject-level eligibility, visits, procedures, and published controls.

No model, transport, subject/OCR/Profile surface, or publication is involved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package104_interim_analysis_governance_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cq-package104-interim-analysis-governance-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package104-interim-analysis-governance-boundary"
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
PACKAGE_ORDINAL = 104
PACKAGE_ID = "pap-03856594c8db16e170f5a4db"

OWNED = [
    "body.p1236",
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-160-208",
]
ATTACHED = ["body.p537", "body.p1237#atom-100-160"]
SEMANTIC = [
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-160-208",
]
REQUIRED_CANDIDATES: list[str] = []
FORBIDDEN_CANDIDATES = [
    "body.p537",
    "body.p1236",
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-100-160",
    "body.p1237#atom-160-208",
]
STRUCTURAL_ONLY = ["body.p1236"]
ORDERED = [
    "body.p537",
    "body.p1236",
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-100-160",
    "body.p1237#atom-160-208",
]

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
    "body.p1236": "期中分析",
    "body.p1237#atom-0-15": "本研究包含一个预设的期中分析。",
    "body.p1237#atom-15-100": (
        "该分析的主要目的是基于累积的II期研究的有效性和安全性数据，"
        "由独立数据监查委员会（IDMC）向申办方提供正式建议：包括能否继续进行Ⅲ期临床研究，"
        "以及推荐Ⅲ期研究的剂量等。"
    ),
    "body.p1237#atom-100-160": (
        "期中分析将在II期的50%参与者完成第12周访视的主要疗效评估后启动，"
        "将由独立的统计团队进行分析并将结果提交给IDMC。"
    ),
    "body.p1237#atom-160-208": (
        "IDMC将综合评估所有疗效和安全性证据来形成建议。"
        "期中分析的具体细节可见独立的期中统计分析计划。"
    ),
    "body.p537": (
        "期中分析将在Ⅱ期约50%参与者完成第12周访视后进行，在有效性和安全性评估的基础上，"
        "对Ⅱ期研究数据进行评估。数据将由独立统计科学组（Statistical Sciences Group，SSG）分析。"
        "分析结果将由独立数据监查委员会（Independent Data Monitoring Committee，IDMC）进行审查。"
        "IDMC基于期中分析结果（包括主要疗效终点、关键安全性事件等），建议Ⅲ期研究的剂量；"
        "可能基于安全性和或有效性原因而建议某剂量组不再入选新的参与者。最终决定将取决于申办方。"
    ),
}
PHASE_SCOPES = {
    "body.p537": ["phase_ii"],
    "body.p1236": ["unknown"],
    "body.p1237#atom-0-15": ["unknown"],
    "body.p1237#atom-15-100": ["mixed"],
    "body.p1237#atom-100-160": ["phase_ii"],
    "body.p1237#atom-160-208": ["unknown"],
}


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


# ---------------------------------------------------------------------------
# configuration and semantic boundary
# ---------------------------------------------------------------------------


def test_config_contract_keeps_study_governance_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package104-interim-analysis-governance-boundary"
    )
    assert config["task_id"] == "phase5-slice61cq-20260830"
    assert config["worker"] == "codex-parent"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_PROTOCOL_SHA256

    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    required = config["required_candidate_source_refs"]
    assert required == REQUIRED_CANDIDATES
    assert required == []
    assert config["forbidden_candidate_source_refs"] == FORBIDDEN_CANDIDATES
    assert config["structural_only_source_refs"] == STRUCTURAL_ONLY
    assert config["attached_structural_only_source_refs"] == []

    assert config["expected_disposition_by_source_ref"] == {
        ref: "administrative_statistical_background" for ref in SEMANTIC
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["pre_enrollment_source_refs"] == []
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["phase_applicability"]["disposition"] == "selected_phase_applicable"
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": "manifest:slice61cq-package104-interim-analysis-governance-boundary",
        "catalog_id": "catalog:slice61cq-package104-interim-analysis-governance-boundary",
    }


def test_source_identity_blocks_all_candidate_and_subject_inversion_paths(
    config: dict,
) -> None:
    required_markers = config["candidate_required_markers_by_source_ref"]
    assert required_markers == {}

    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])
    assert {
        "IDMC决定受试者资格",
        "IDMC决定单例入排",
    } <= set(forbidden["body.p1237#atom-15-100"])
    assert {
        "独立统计分析计划决定受试者资格",
        "独立统计分析计划决定单例入排",
    } <= set(forbidden["body.p1237#atom-160-208"])
    assert "单个受试者必须完成第12周访视" in forbidden["body.p537"]
    assert "第12周访视决定受试者资格" in forbidden[
        "body.p1237#atom-100-160"
    ]

    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "研究级统计治理",
        "累积Ⅱ期数据",
        "申办方最终研究决策",
        "全部零候选",
        "不能承载无受试者节点的研究治理事实",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
    ):
        assert phrase in combined


def test_frozen_plan_owns_exact_package104_units(plan: dict, config: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    packages = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_ORDINAL]
    assert len(packages) == 1
    package = packages[0]
    assert package["package_id"] == PACKAGE_ID
    assert package["selected_phase"] == "phase_ii"
    assert [unit["source_ref"] for unit in package["owned_units"]] == OWNED
    assert set(ATTACHED) <= {u["source_ref"] for u in package["context_units"]}
    assert set(config["owned_source_refs"]) == {
        u["source_ref"] for u in package["owned_units"]
    }


def test_read_only_context_has_no_frozen_owner(plan: dict, config: dict) -> None:
    owners: dict[str, list[int]] = {}
    for package in plan["packages"]:
        for unit in package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                package["package_ordinal"]
            )

    assert all(owners.get(ref) == [PACKAGE_ORDINAL] for ref in OWNED)
    assert all(ref not in owners for ref in ATTACHED)
    assert owners.get("body.p1224") == [103]
    assert owners.get("body.p1235") == [103]
    assert owners.get("body.p1238") == [105]
    assert "body.p1210" not in owners
    assert "body.p1223" not in owners
    assert config["later_package_boundary"]["unowned_context_source_refs"] == [
        "body.p537",
        "body.p1210",
        "body.p1223",
        "body.p1237#atom-100-160",
    ]
    assert config["later_package_boundary"]["expected_owners_by_span"] == {
        "body.p1224": 103,
        "body.p1235": 103,
        "body.p1236": 104,
        "body.p1237#atom-0-15": 104,
        "body.p1237#atom-15-100": 104,
        "body.p1237#atom-160-208": 104,
        "body.p1238": 105,
    }


# ---------------------------------------------------------------------------
# immutable source and phase closure
# ---------------------------------------------------------------------------


def test_coverage_preserves_exact_excerpts_and_phase_scopes(coverage: dict) -> None:
    units = {unit["source_ref"]: unit for unit in coverage["units"]}
    for ref, excerpt in EXPECTED_EXCERPTS.items():
        assert units[ref]["excerpt"] == excerpt
        assert units[ref]["phase_scopes"] == PHASE_SCOPES[ref]
        assert units[ref]["study_phase"] == "phase_ii"
        assert units[ref]["unit_kind"] == "paragraph"
    assert [units[ref]["source_order"] for ref in ORDERED] == [
        22240,
        30990,
        31000,
        31001,
        31002,
        31003,
    ]
    assert all(units[ref]["source_span_ids"] == [
        "body.p537" if ref == "body.p537" else (
            "body.p1236" if ref == "body.p1236" else "body.p1237"
        )
    ] for ref in ORDERED)


def test_phase_applicability_explains_study_level_not_subject_level(config: dict) -> None:
    phase = config["phase_applicability"]
    for phrase in (
        "研究级数据触发",
        "独立分析",
        "IDMC建议",
        "申办方研究决策",
        "不是单例受试者入排资格",
        "不是单例受试者入排",
        "D1给药前义务",
    ):
        assert phrase in phase["rationale"]
    assert config["workflow_stages"] == [
        {
            "workflow_stage_id": "flow-screening",
            "review_stage": "screening",
            "display_name": "筛选访视",
            "visit_instance": "筛选访视",
        },
        {
            "workflow_stage_id": "flow-baseline",
            "review_stage": "baseline",
            "display_name": "基线访视",
            "visit_instance": "基线访视",
        },
        {
            "workflow_stage_id": "flow-d1-pre-dose",
            "review_stage": "baseline",
            "display_name": "D1给药前",
            "visit_instance": "D1给药前",
        },
    ]


# ---------------------------------------------------------------------------
# resolver and deterministic model-free prepare evidence
# ---------------------------------------------------------------------------


def test_resolver_keeps_owned_and_attached_roles_distinct(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == [
        "attached",
        "owned",
        "owned",
        "owned",
        "attached",
        "owned",
    ]
    by_ref = {row.source_ref: row for row in rows}
    for ref in OWNED:
        assert by_ref[ref].role == "owned"
        assert by_ref[ref].lookup == "frozen_plan_owned"
        assert by_ref[ref].package_ordinal == PACKAGE_ORDINAL
        assert by_ref[ref].package_id == PACKAGE_ID
    for ref in ATTACHED:
        assert by_ref[ref].role == "attached"
        assert by_ref[ref].lookup == "frozen_plan_context"
        assert by_ref[ref].package_ordinal != PACKAGE_ORDINAL
        assert by_ref[ref].package_id != PACKAGE_ID
    for ref, excerpt in EXPECTED_EXCERPTS.items():
        assert by_ref[ref].excerpt == excerpt


def test_model_free_prepare_has_declared_six_source_rows_only(
    config: dict,
) -> None:
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
    assert summary["attached_count"] == 2
    assert summary["unit_count"] == 6
    assert summary["lookup_counts"] == {
        "frozen_plan_context": 2,
        "frozen_plan_owned": 4,
    }
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == [
        "attached",
        "owned",
        "owned",
        "owned",
        "attached",
        "owned",
    ]
    assert [row["lookup"] for row in rows] == [
        "frozen_plan_context",
        "frozen_plan_owned",
        "frozen_plan_owned",
        "frozen_plan_owned",
        "frozen_plan_context",
        "frozen_plan_owned",
    ]
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows if row["role"] == "owned"]
    context_ids = [row["structure_unit_id"] for row in rows if row["role"] == "attached"]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == context_ids
    assert batch["structural_only_structure_unit_ids"] == [owned_ids[0]]
    assert batch["pre_enrollment_structure_unit_ids"] == []
    assert batch["owned_visit_instance_by_structure_unit_id"] == {}
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {}
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {}
    assert batch["known_official_targets"] == []
    assert batch["known_procedure_targets"] == []
    assert [
        stage["workflow_stage_id"] for stage in batch["known_workflow_stage_targets"]
    ] == ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]

    assert prompt_meta["owned_count"] == 4
    assert prompt_meta["attached_count"] == 2
    assert prompt_meta["context_structure_unit_ids"] == context_ids
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
        "预设的期中分析",
        "累积的II期研究的有效性和安全性数据",
        "向申办方提供正式建议",
        "独立的期中统计分析计划",
        "约50%参与者完成第12周访视",
        "最终决定将取决于申办方",
    ):
        assert marker in prompt
    for ref in (
        *(f"body.p{number}" for number in range(1210, 1224)),
        "body.p1238",
    ):
        assert ref not in prompt


def test_hydrated_gate_rejects_paraphrased_subject_controls_by_source_identity(
    config: dict,
) -> None:
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
        "allowed_structure_unit_ids": list(unit_by_ref.values()),
        "required_candidate_source_refs": [],
        "forbidden_candidate_source_refs": FORBIDDEN_CANDIDATES,
        "expected_disposition_by_source_ref": config[
            "expected_disposition_by_source_ref"
        ],
        "expected_workflow_stage_ids_by_source_ref": {},
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": {},
    }
    assert not evaluate_hydrated_agent_output(
        **kwargs,
        hydrated={"candidates": [], "dispositions": dispositions},
    )

    attacks = {
        "body.p537": "累计样本达到约一半后，单例必须完成第12周评估才可继续研究。",
        "body.p1236": "期中分析是每名受试者进入后续阶段的必要审核。",
        "body.p1237#atom-0-15": "预设分析用于判断该受试者是否符合继续参加研究的条件。",
        "body.p1237#atom-15-100": "委员会结合累积结果裁定当前受试者能否纳入研究。",
        "body.p1237#atom-100-160": "该受试者完成第12周访视后方具备继续入组资格。",
        "body.p1237#atom-160-208": "独立统计分析计划决定每名受试者是否满足入排要求。",
    }
    for ref, title in attacks.items():
        issues = evaluate_hydrated_agent_output(
            **kwargs,
            hydrated={
                "candidates": [
                    {
                        "frozen_structure_unit_ids": [unit_by_ref[ref]],
                        "title": title,
                        "semantics": {},
                    }
                ],
                "dispositions": dispositions,
            },
        )
        assert any(
            issue.code == "CONTROL_DUPLICATE_RETAINED"
            and issue.source_refs == (ref,)
            for issue in issues
        ), f"来源身份门禁未拦截 {ref} 的候选化改写"



# ---------------------------------------------------------------------------
# deliverable and immutable fingerprints
# ---------------------------------------------------------------------------


def test_checklist_records_scope_and_stop_conditions() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    for phrase in (
        "papl-e17d498106b6f71f440ff2be",
        "pap-03856594c8db16e170f5a4db",
        "body.p1237#atom-100-160",
        "body.p537",
        "administrative_statistical_background",
        "全部禁止候选",
        "claims_complete=false",
        "不得调用临床语义模型",
        "不得发布 control point",
        "Patient Profile",
        "parent clinical acceptance",
    ):
        assert phrase in text


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256(STRUCTURE_PATH) == EXPECTED_STRUCTURE_SHA256
    assert CONFIG_PATH.exists()
    assert CHECKLIST_PATH.exists()
