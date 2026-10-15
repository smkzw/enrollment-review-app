#!/usr/bin/env python3
"""Model-free Package 106 record-retention governance regressions.

The tests freeze Package 106 ownership, preserve Package 105 p1247 only as a
read-only cross-reference, and prove that retention governance does not become
an individual subject eligibility or workflow control.

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
    "representative_group_package106_record_retention_governance_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cs-package106-record-retention-governance-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package106-record-retention-governance-boundary"
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
PACKAGE_ORDINAL = 106
PACKAGE_ID = "pap-2bfe896140d41556d48a5132"
PACKAGE105_ID = "pap-b8d5cdfbc6ac4c373c6576b3"
PACKAGE107_ID = "pap-b119517783facd407b628e1e"

OWNED = ["body.p1248", "body.p1249", "body.p1250"]
ATTACHED = ["body.p1247"]
ORDERED = [*ATTACHED, *OWNED]
FORBIDDEN_CANDIDATES = ORDERED
STRUCTURAL_ONLY = ["body.p1248"]
SEMANTIC = ["body.p1249", "body.p1250"]
EXPECTED_DISPOSITIONS = {
    "body.p1249": "non_enrollment_execution",
    "body.p1250": "non_enrollment_execution",
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
    "body.p1247": (
        "用于验证eCRFs输入数据正确性和完整性的源文件不得被清除或销毁，"
        "且必须按照第9.4节中描述的记录保存要求保存。为方便于源数据验证，"
        "研究者和机构必须允许申办者因为研究相关的监查、申办者稽查和 "
        "机构审查委员会/伦理委员会（Institutional Review Board/Ethics Committee，"
        "IRB/EC）审查而直接访问源文件和报告（如得到法律允许，也可以复制）。"
        "研究中心还必须允许监管当局对源数据/源文件进行检查。"
    ),
    "body.p1248": "记录/文件的保存",
    "body.p1249": (
        "临床研究文件需按照GCP等相关法律法规的要求进行保存和管理。"
        "研究中心和申办者应保存研究必备文件至试验药物被批准上市后至少5年或至临床试验结束后至少5年"
        "（以较长时间为准）。研究文件应合理保存，以便日后访问或数据溯源。"
        "申办者、研究者和临床试验机构应当确认均有保存临床试验必备文件的场所和条件。"
    ),
    "body.p1250": "研究文件的转移、保管人的变更、研究文件的销毁等，必须得到申办者的书面许可。",
}
SOURCE_ORDERS = [31100, 31110, 31120, 31130]
HEADING_PATHS = {
    ref: ["数据采集与管理", "源数据/源文件"] for ref in ATTACHED
}
HEADING_PATHS.update(
    {
        ref: ["数据采集与管理", "记录/文件的保存"]
        for ref in OWNED
    }
)
EXPECTED_OWNER_MAP = {
    "body.p1224": 103,
    "body.p1235": 103,
    "body.p1236": 104,
    "body.p1237#atom-0-15": 104,
    "body.p1237#atom-15-100": 104,
    "body.p1237#atom-160-208": 104,
    "body.p1238": 105,
    "body.p1247": 105,
    "body.p1248": 106,
    "body.p1249": 106,
    "body.p1250": 106,
    "body.p1251": 107,
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
# configuration and source-driven semantic boundary
# ---------------------------------------------------------------------------


def test_config_contract_keeps_retention_governance_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package106-record-retention-governance-boundary"
    )
    assert config["task_id"] == "phase5-slice61cs-20260830"
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
    assert config["owned_procedure_semantic_families_by_source_ref"] == {}
    assert config["owned_required_action_kinds_by_source_ref"] == {}
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["phase_applicability"]["disposition"] == (
        "selected_phase_applicable"
    )
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": "manifest:slice61cs-package106-record-retention-governance-boundary",
        "catalog_id": "catalog:slice61cs-package106-record-retention-governance-boundary",
    }


def test_config_preserves_retention_maximum_responsibilities_and_permission(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "两个独立事件锚点各至少5年",
        "以较长时间为准",
        "试验药物被批准上市后至少5年",
        "临床试验结束后至少5年",
        "max(试验药物获批上市日期+至少5年, 临床试验结束日期+至少5年)",
        "任一锚点未知时不得凭另一个较早锚点",
        "研究中心和申办者",
        "申办者、研究者和临床试验机构",
        "保存场所和条件",
        "研究文件的转移",
        "保管人的变更",
        "研究文件的销毁",
        "申办者的书面许可",
        "Package 105",
        "只读",
        "Package 107",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
    ):
        assert phrase in combined

    semantics = config["exception_semantics_by_source_ref"]
    assert semantics["body.p1247"]["base_rule"] == EXPECTED_EXCERPTS["body.p1247"]

    p1249 = semantics["body.p1249"]
    assert p1249["base_rule"] == EXPECTED_EXCERPTS["body.p1249"]
    assert p1249["preserve_keywords"] == [
        "GCP等相关法律法规",
        "研究中心和申办者",
        "研究必备文件",
        "试验药物被批准上市后至少5年",
        "临床试验结束后至少5年",
        "（以较长时间为准）",
        "日后访问或数据溯源",
        "申办者、研究者和临床试验机构",
        "保存场所和条件",
    ]
    assert p1249["exception_rule"] == (
        "保存截止是两个独立锚点各加至少五年的最大值："
        "max(试验药物获批上市日期+至少5年, 临床试验结束日期+至少5年)。"
        "任一锚点未知时不得凭另一个较早锚点声称保存义务已经结束；"
        "研究文件保存、访问/溯源、场所与责任主体均是研究治理，不是单例受试者资格。"
    )

    p1250 = semantics["body.p1250"]
    assert p1250["base_rule"] == EXPECTED_EXCERPTS["body.p1250"]
    assert p1250["preserve_keywords"] == [
        "研究文件的转移",
        "保管人的变更",
        "研究文件的销毁",
        "申办者的书面许可",
    ]
    assert p1250["exception_rule"] == (
        "研究文件转移、保管人变更和销毁每一项都要求申办者书面许可；"
        "不得弱化为口头同意、一般知会，或替换为研究者、伦理委员会或监管机构许可；"
        "该许可治理不构成受试者资格或入排条件。"
    )


def test_source_identity_blocks_subject_eligibility_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "两个期限任选其一",
        "使用较早期限结束保存义务",
        "任一锚点未知仍可结束保存",
        "保存场所和条件不足不得入组",
        "研究中心或申办者未保存不得入组",
    } <= set(forbidden["body.p1249"])
    assert {
        "未经申办者书面许可不得入组",
        "研究文件转移未获书面许可不得入组",
        "保管人变更未获书面许可不得入组",
        "研究文件销毁未获书面许可不得入组",
        "口头同意即可转移文件",
        "一般知会即可销毁研究文件",
        "研究者书面许可即可销毁研究文件",
    } <= set(forbidden["body.p1250"])
    assert "源文件未保存不得入组" in forbidden["body.p1247"]
    assert "记录/文件的保存决定受试者资格" in forbidden["body.p1248"]

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "只读交叉来源" in "；".join(checks["body.p1247"])
    assert "两个独立事件锚点" in "；".join(checks["body.p1249"])
    assert "研究中心和申办者负责保存" in "；".join(checks["body.p1249"])
    assert "申办者、研究者和临床试验机构" in "；".join(
        checks["body.p1249"]
    )
    assert "每一项都必须得到申办者的书面许可" in "；".join(
        checks["body.p1250"]
    )
    assert "单例受试者" in "；".join(checks["body.p1250"])


def test_phase_applicability_explains_research_file_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "保存期限",
        "访问/溯源",
        "场所条件",
        "责任主体",
        "申办者书面许可",
        "研究文件治理",
        "不是单例受试者入排资格",
        "筛选/基线/D1给药前义务",
        "p1247",
        "Package 107",
    ):
        assert phrase in rationale
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
# frozen ownership and immutable source closure
# ---------------------------------------------------------------------------


def test_frozen_plan_owns_exact_package106_units(plan: dict, config: dict) -> None:
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
    assert set(ATTACHED).isdisjoint(
        {unit["source_ref"] for unit in package["owned_units"]}
    )
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert owner_by_ref["body.p1247"] == 105
    assert owner_by_ref["body.p1251"] == 107
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_context_units_and_unowned_refs_remain_read_only(
    plan: dict,
    config: dict,
) -> None:
    package = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = {unit["source_ref"] for unit in package["context_units"]}
    assert len(context_refs) == 37
    assert context_refs.isdisjoint(config["owned_source_refs"])
    assert context_refs.isdisjoint(config["attached_source_refs"])

    owners: dict[str, list[int]] = {}
    for package in plan["packages"]:
        for unit in package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                package["package_ordinal"]
            )
    assert owners["body.p1247"] == [105]
    assert owners["body.p1248"] == [106]
    assert owners["body.p1249"] == [106]
    assert owners["body.p1250"] == [106]
    assert owners["body.p1251"] == [107]
    assert all(
        ref not in owners
        for ref in config["later_package_boundary"]["unowned_context_source_refs"]
    )


def test_coverage_preserves_exact_excerpts_order_and_heading_paths(
    coverage: dict,
) -> None:
    units = {unit["source_ref"]: unit for unit in coverage["units"]}
    assert [units[ref]["source_order"] for ref in ORDERED] == SOURCE_ORDERS
    for ref in ORDERED:
        unit = units[ref]
        assert unit["excerpt"] == EXPECTED_EXCERPTS[ref]
        assert unit["phase_scopes"] == ["unknown"]
        assert unit["study_phase"] == "phase_ii"
        assert unit["unit_kind"] == "paragraph"
        assert unit["source_span_ids"] == [ref]
        assert unit["member_source_refs"] == [ref]
        assert unit["heading_path"] == HEADING_PATHS[ref]


# ---------------------------------------------------------------------------
# resolver ownership and model-free prepare closure
# ---------------------------------------------------------------------------


def test_resolver_keeps_package105_attachment_and_package106_owned_roles(
    config: dict,
) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["attached", "owned", "owned", "owned"]
    assert [row.lookup for row in rows] == [
        "frozen_plan_owned",
        "frozen_plan_owned",
        "frozen_plan_owned",
        "frozen_plan_owned",
    ]

    by_ref = {row.source_ref: row for row in rows}
    attachment = by_ref["body.p1247"]
    assert attachment.package_ordinal == 105
    assert attachment.package_id == PACKAGE105_ID
    assert attachment.role == "attached"
    for ref in OWNED:
        row = by_ref[ref]
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert row.role == "owned"
        assert row.lookup == "frozen_plan_owned"
        assert row.source_span_ids == (ref,)
        assert row.member_source_refs == (ref,)
    assert [row.excerpt for row in rows] == [EXPECTED_EXCERPTS[ref] for ref in ORDERED]


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1247",
        "body.p1251",
        "body.p1237#atom-100-160",
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
    attack["owned_source_refs"] = ["body.p1248"]
    attack["unit_lookup"] = ["coverage_manifest"]
    with pytest.raises(SystemExit):
        _resolve_units(attack)


def test_model_free_prepare_has_declared_attachment_and_owned_rows_only(
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
    assert summary["owned_count"] == 3
    assert summary["attached_count"] == 1
    assert summary["unit_count"] == 4
    assert summary["lookup_counts"] == {"frozen_plan_owned": 4}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == [
        "attached",
        "owned",
        "owned",
        "owned",
    ]
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 4
    assert [row["package_ordinal"] for row in rows] == [105, 106, 106, 106]
    assert [row["package_id"] for row in rows] == [
        PACKAGE105_ID,
        PACKAGE_ID,
        PACKAGE_ID,
        PACKAGE_ID,
    ]
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows if row["role"] == "owned"]
    context_ids = [
        row["structure_unit_id"] for row in rows if row["role"] == "attached"
    ]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == context_ids
    assert batch["owned_source_span_ids"] == OWNED
    assert batch["context_source_span_ids"] == ATTACHED
    assert batch["structural_only_structure_unit_ids"] == [owned_ids[0]]
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

    assert prompt_meta["owned_count"] == 3
    assert prompt_meta["attached_count"] == 1
    assert prompt_meta["context_structure_unit_ids"] == context_ids
    assert prompt_meta["batching_mode"] == "single_batch_with_known_targets"
    assert provenance["config_sha256"] == _sha256(CONFIG_PATH)
    assert provenance["frozen_plan_sha256"] == EXPECTED_PLAN_SHA256
    assert provenance["protocol_document_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert provenance["claims_complete"] is False

    assert [row["source_ref"] for row in qc["rows"]] == ORDERED
    assert [row["role"] for row in qc["rows"]] == [
        "attached",
        "owned",
        "owned",
        "owned",
    ]
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
        "第9.4节",
        "试验药物被批准上市后至少5年",
        "临床试验结束后至少5年",
        "（以较长时间为准）",
        "申办者、研究者和临床试验机构",
        "场所和条件",
        "研究文件的转移",
        "保管人的变更",
        "研究文件的销毁",
        "申办者的书面许可",
    ):
        assert marker in prompt
    for ref in (
        "body.p1236",
        "body.p1237",
        "body.p1251",
        "body.p537",
        "body.p1210",
        "body.p1223",
    ):
        assert ref not in prompt


# ---------------------------------------------------------------------------
# deterministic hydrated-gate attacks without a model
# ---------------------------------------------------------------------------


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
        ("body.p1247", "源文件未保存不得入组"),
        ("body.p1248", "记录/文件的保存决定受试者资格"),
        ("body.p1249", "保存期限不足不得入组"),
        ("body.p1249", "两个期限任选其一"),
        ("body.p1249", "任一锚点未知仍可结束保存"),
        ("body.p1250", "未经申办者书面许可不得入组"),
        ("body.p1250", "研究文件转移未获书面许可不得入组"),
        ("body.p1250", "保管人变更未获书面许可不得入组"),
        ("body.p1250", "研究文件销毁未获书面许可不得入组"),
        ("body.p1250", "口头同意即可转移文件"),
        ("body.p1250", "一般知会即可销毁研究文件"),
    ],
)
def test_hydrated_gate_rejects_retention_as_subject_control(
    config: dict,
    source_ref: str,
    title: str,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    common = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "allowed_structure_unit_ids":[unit_by_ref[ref] for ref in OWNED],
        "required_candidate_source_refs": [],
        "forbidden_candidate_source_refs": FORBIDDEN_CANDIDATES,
        "expected_disposition_by_source_ref": EXPECTED_DISPOSITIONS,
        "expected_workflow_stage_ids_by_source_ref": {},
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": {},
    }
    issues = evaluate_hydrated_agent_output(
        **common,
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
    )
    assert any(
        issue.code == "CONTROL_DUPLICATE_RETAINED"
        and issue.source_refs == (source_ref,)
        for issue in issues
    ), f"来源身份门禁未拦截 {source_ref} 的候选化改写"
    if source_ref == "body.p1247":
        assert any(issue.code == "SCOPE_CREEP" for issue in issues)


# ---------------------------------------------------------------------------
# deliverable and immutable fingerprints
# ---------------------------------------------------------------------------


def test_checklist_records_retention_scope_and_stop_conditions() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    for phrase in (
        "papl-e17d498106b6f71f440ff2be",
        "pap-2bfe896140d41556d48a5132",
        "body.p1247",
        "body.p1248",
        "body.p1249",
        "body.p1250",
        "body.p1251",
        "只读交叉引用",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "两个独立事件锚点",
        "以较长时间为准",
        "研究中心和申办者",
        "申办者、研究者和临床试验机构",
        "申办者的书面许可",
        "不得调用临床语义模型",
        "不得发布 control point",
        "Patient Profile",
        "parent clinical acceptance",
        "claims_complete=false",
    ):
        assert phrase in text


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256(STRUCTURE_PATH) == EXPECTED_STRUCTURE_SHA256
    assert CONFIG_PATH.exists()
    assert CHECKLIST_PATH.exists()
