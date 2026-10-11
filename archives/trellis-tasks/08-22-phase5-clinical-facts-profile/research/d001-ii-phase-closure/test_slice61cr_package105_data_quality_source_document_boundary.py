#!/usr/bin/env python3
"""Model-free Package 105 data-quality and source-document regressions.

The tests freeze source identity and prove that data-management execution and
source-evidence governance are not silently promoted to subject eligibility.
The candidate decision is source-text-driven: source excerpts are checked
before the expected non-candidate dispositions and dry-run closure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from copy import deepcopy

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package105_data_quality_source_document_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cr-package105-data-quality-source-document-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package105-data-quality-source-document-boundary"
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
PACKAGE_ORDINAL = 105
PACKAGE_ID = "pap-b8d5cdfbc6ac4c373c6576b3"

OWNED = [f"body.p{number}" for number in range(1238, 1248)]
ATTACHED: list[str] = []
STRUCTURAL_ONLY = ["body.p1238", "body.p1239", "body.p1241", "body.p1243"]
EXPECTED_DISPOSITIONS = {
    "body.p1240": "non_enrollment_execution",
    "body.p1242": "non_enrollment_execution",
    "body.p1244": "supporting_or_supplement",
    "body.p1245": "non_enrollment_execution",
    "body.p1246": "non_enrollment_execution",
    "body.p1247": "non_enrollment_execution",
}
EXPECTED_ACTIONS: dict[str, list[str]] = {}
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
    "body.p1238": "数据采集与管理",
    "body.p1239": "数据质量保证",
    "body.p1240": (
        "申办者将负责本研究的数据管理，包括数据的质量检查。将通过使用eCRFs，由研究中心负责将数据手动输入电子数据采集系统（Electronic data capture，EDC）。如果数据不一致，申办者将要求研究中心澄清数据，研究中心将在 EDC 系统中解决数据质疑。研究实施方案所需的EDC系统之外的其他数据，如中心实验室的数据将直接发送给申办者，根据申办者的标准程序处理和加工这些数据的电子传输。"
    ),
    "body.p1241": "电子病例报告表（eCRF）",
    "body.p1242": (
        "数据管理将在经验证的EDC系统中进行。通过使用申办者指定的EDC系统完成eCRFs。研究中心将接受培训并获得相应的eCRF填写手册。eCRFs将以电子方式提交给申办者，并按申办者的指示处理。所有eCRFs应由研究中心经过培训的指定工作人员完成。eCRFs应由研究者或指定人员审查并以电子方式签名和注明日期。"
    ),
    "body.p1243": "源数据/源文件",
    "body.p1244": (
        "源文件是指临床试验中产生的原始医学记录、医疗文件和数据，例如医院病历、医学图像、实验室记录、仪器自动记录的数据、临床试验的相关备忘录、发药记录、药房保存的处方、参与者临床试验日记等，可包括复制或抄录的核证副本。源数据是指临床试验中的原始记录或其复印件（核证副本）上记载的所有信息。"
    ),
    "body.p1245": (
        "在研究开始前，将在研究监查计划中明确定义研究生成的源文件类型，这包括任何直接输入 eCRFs 的按方案要求采集的数据（即，之前没有此数据的书面或电子记录），此类数据应视为源数据。"
    ),
    "body.p1246": (
        "无论数据为书面手写还是以电子方式录入，研究者负责确保源数据准确、清晰、具有同期性、为原始数据且可归因溯源。在常规临床试验活动中，如果通过计算机系统（和/或任何其他类型的电子设备）创建（第一次录入）、修改、维护、归档、检索或通过电子方式传输源数据，此类系统必须符合所有适用的管辖电子记录和/或电子签名的使用的法律和法规。此类系统可能包括但不限于：电子医疗/健康档案、不良事件跟踪/报告、方案要求的评价，和/或药物计数记录。采用通过此类系统获得的书面记录来取代电子格式进行规定的活动时，此类书面记录应有经核证的副本。经核证的副本由已验证的原始信息的副本组成，有研究人员的签字及签字日期，具有和原件相同的所有属性。如果修改了计算机系统中的原始数据，在系统上应保留可查看的审核跟踪，显示原始数据及变更原因、进行更改的人员姓名，以及更改的日期。"
    ),
    "body.p1247": (
        "用于验证eCRFs输入数据正确性和完整性的源文件不得被清除或销毁，且必须按照第9.4节中描述的记录保存要求保存。为方便于源数据验证，研究者和机构必须允许申办者因为研究相关的监查、申办者稽查和 机构审查委员会/伦理委员会（Institutional Review Board/Ethics Committee，IRB/EC）审查而直接访问源文件和报告（如得到法律允许，也可以复制）。研究中心还必须允许监管当局对源数据/源文件进行检查。"
    ),
}
SOURCE_ORDERS = [31010, 31020, 31030, 31040, 31050, 31060, 31070, 31080, 31090, 31100]
HEADING_PATHS = {
    "body.p1238": ["数据采集与管理"],
    "body.p1239": ["数据采集与管理", "数据质量保证"],
    "body.p1240": ["数据采集与管理", "数据质量保证"],
    "body.p1241": ["数据采集与管理", "电子病例报告表（eCRF）"],
    "body.p1242": ["数据采集与管理", "电子病例报告表（eCRF）"],
    "body.p1243": ["数据采集与管理", "源数据/源文件"],
    "body.p1244": ["数据采集与管理", "源数据/源文件"],
    "body.p1245": ["数据采集与管理", "源数据/源文件"],
    "body.p1246": ["数据采集与管理", "源数据/源文件"],
    "body.p1247": ["数据采集与管理", "源数据/源文件"],
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
# source-text-driven disposition and ownership boundary
# ---------------------------------------------------------------------------


def test_config_reads_source_before_confirming_zero_candidates(config: dict) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package105-data-quality-source-document-boundary"
    )
    assert config["task_id"] == "phase5-slice61cr-20260830"
    assert config["worker"] == "codex-parent"
    assert config["study_phase"] == "phase_ii"
    assert config["expected_package_ordinal"] == PACKAGE_ORDINAL
    assert config["expected_package_id"] == PACKAGE_ID
    assert config["expected_protocol_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == []
    assert config["forbidden_candidate_source_refs"] == OWNED
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL_ONLY
    assert config["attached_structural_only_source_refs"] == []
    assert config["expected_disposition_by_source_ref"] == EXPECTED_DISPOSITIONS
    assert set(EXPECTED_DISPOSITIONS).isdisjoint(STRUCTURAL_ONLY)
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert config["owned_required_action_kinds_by_source_ref"] == EXPECTED_ACTIONS
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": "manifest:slice61cr-package105-data-quality-source-document-boundary",
        "catalog_id": "catalog:slice61cr-package105-data-quality-source-document-boundary",
    }

    reason = config["batching"]["reason"]
    for phrase in (
        "先逐条读取并判断",
        "申办方、研究中心及研究者",
        "证据来源/QC治理义务",
        "不表达受试者人群、入排条件、阈值",
        "源文审阅后确认",
        "不得以other_control_candidate强挂到受试者工作流",
    ):
        assert phrase in reason

    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "研究执行",
        "证据接受边界",
        "资料可接受性缺口",
        "核证副本",
        "审核跟踪",
        "不得自动变成受试者资料缺口",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
        "Package 106",
    ):
        assert phrase in combined


def test_source_identity_blocks_data_governance_to_eligibility_inversion(
    config: dict,
) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(OWNED)
    for ref in OWNED:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])
    for ref, marker in (
        ("body.p1239", "数据质量不合格不得入组"),
        ("body.p1240", "数据质疑未解决不得入组"),
        ("body.p1240", "中心实验室数据未传输不得入组"),
        ("body.p1242", "研究者未电子签名不得入组"),
        ("body.p1242", "培训未完成不得入组"),
        ("body.p1244", "核证副本不合格不得入组"),
        ("body.p1245", "源数据认定决定受试者资格"),
        ("body.p1246", "审核跟踪缺失不得入组"),
        ("body.p1247", "不能直接访问源文件不得入组"),
    ):
        assert marker in forbidden[ref]

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "研究级数据管理执行" in "；".join(checks["body.p1240"])
    assert "记录流程义务" in "；".join(checks["body.p1242"])
    assert "证据来源词汇" in "；".join(checks["body.p1244"])
    assert "来源分类规则" in "；".join(checks["body.p1245"])
    assert "数据完整性与证据QC义务" in "；".join(checks["body.p1246"])
    assert "证据保存和访问治理" in "；".join(checks["body.p1247"])


def test_frozen_plan_owns_exact_package105_units(plan: dict, config: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    packages = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_ORDINAL]
    assert len(packages) == 1
    package = packages[0]
    assert package["package_id"] == PACKAGE_ID
    assert package["selected_phase"] == "phase_ii"
    assert [unit["source_ref"] for unit in package["owned_units"]] == OWNED
    assert not ATTACHED
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert all(ref not in owner_by_ref for ref in config["later_package_boundary"]["unowned_context_source_refs"])


def test_neighbor_ownership_keeps_packages104_and106_separate(plan: dict, config: dict) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    package103 = {f"body.p{number}" for number in (1224, *range(1226, 1236))}
    package104 = {
        "body.p1236",
        "body.p1237#atom-0-15",
        "body.p1237#atom-15-100",
        "body.p1237#atom-160-208",
    }
    package106 = {f"body.p{number}" for number in range(1248, 1251)}
    assert all(owner_by_ref[ref] == 103 for ref in package103)
    assert all(owner_by_ref[ref] == 104 for ref in package104)
    assert all(owner_by_ref[ref] == 105 for ref in OWNED)
    assert all(owner_by_ref[ref] == 106 for ref in package106)
    assert all(
        ref not in owner_by_ref
        for ref in (
            "body.p537",
            "body.p1210",
            "body.p1223",
            "body.p1237#atom-100-160",
        )
    )
    assert config["later_package_boundary"]["expected_owners_by_span"] == {
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
    }


# ---------------------------------------------------------------------------
# immutable coverage and resolver closure
# ---------------------------------------------------------------------------


def test_coverage_preserves_exact_excerpts_and_source_order(coverage: dict) -> None:
    units = {unit["source_ref"]: unit for unit in coverage["units"]}
    assert [units[ref]["source_order"] for ref in OWNED] == SOURCE_ORDERS
    for ref in OWNED:
        unit = units[ref]
        assert unit["excerpt"] == EXPECTED_EXCERPTS[ref]
        assert unit["phase_scopes"] == ["unknown"]
        assert unit["study_phase"] == "phase_ii"
        assert unit["unit_kind"] == "paragraph"
        assert unit["source_span_ids"] == [ref]
        assert unit["member_source_refs"] == [ref]
        assert unit["heading_path"] == HEADING_PATHS[ref]


def test_resolver_keeps_package105_rows_owned_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == OWNED
    assert [row.role for row in rows] == ["owned"] * len(OWNED)
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * len(OWNED)
    for row in rows:
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert row.excerpt == EXPECTED_EXCERPTS[row.source_ref]
        assert row.source_span_ids == (row.source_ref,)


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1236",
        "body.p1248",
        "body.p1210",
    ],
)
def test_resolver_rejects_owned_source_identity_bypasses(
    config: dict,
    source_ref: str,
) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    attack = deepcopy(config)
    attack["owned_source_refs"] = [source_ref]
    with pytest.raises(SystemExit):
        _resolve_units(attack)


def test_owned_source_cannot_be_forced_through_coverage_lookup(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    attack = deepcopy(config)
    attack["owned_source_refs"] = ["body.p1238"]
    attack["unit_lookup"] = ["coverage_manifest"]
    with pytest.raises(SystemExit):
        _resolve_units(attack)


def test_all_frozen_context_units_remain_read_only(plan: dict, config: dict) -> None:
    package = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = {unit["source_ref"] for unit in package["context_units"]}
    assert len(context_refs) == 37
    assert context_refs.isdisjoint(config["owned_source_refs"])
    assert context_refs.isdisjoint(config["attached_source_refs"])


# ---------------------------------------------------------------------------
# deterministic model-free prepare evidence
# ---------------------------------------------------------------------------


def test_model_free_prepare_has_only_declared_sources(config: dict) -> None:
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
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 10
    assert summary["lookup_counts"] == {"frozen_plan_owned": 10}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]
    assert [row["source_ref"] for row in rows] == OWNED
    assert all(row["role"] == "owned" for row in rows)
    assert all(row["lookup"] == "frozen_plan_owned" for row in rows)
    assert [row["excerpt"] for row in rows] == [EXPECTED_EXCERPTS[ref] for ref in OWNED]

    owned_ids = [row["structure_unit_id"] for row in rows]
    structural_ids = [
        row["structure_unit_id"] for row in rows if row["source_ref"] in STRUCTURAL_ONLY
    ]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["structural_only_structure_unit_ids"] == structural_ids
    assert batch["pre_enrollment_structure_unit_ids"] == []
    assert batch["owned_visit_instance_by_structure_unit_id"] == {}
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {}
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {}
    assert batch["known_official_targets"] == []
    assert batch["known_procedure_targets"] == []
    assert [
        stage["workflow_stage_id"] for stage in batch["known_workflow_stage_targets"]
    ] == ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]

    assert prompt_meta["owned_count"] == 10
    assert prompt_meta["attached_count"] == 0
    assert prompt_meta["context_structure_unit_ids"] == []
    assert prompt_meta["batching_mode"] == "single_batch_with_known_targets"
    assert provenance["config_sha256"] == _sha256(CONFIG_PATH)
    assert provenance["frozen_plan_sha256"] == EXPECTED_PLAN_SHA256
    assert provenance["protocol_document_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert provenance["claims_complete"] is False

    assert [row["source_ref"] for row in qc["rows"]] == OWNED
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

    for ref in OWNED:
        assert ref in prompt
    for marker in (
        "数据质疑",
        "经验证的EDC系统",
        "电子方式签名和注明日期",
        "核证副本",
        "审核跟踪",
        "源文件是指",
        "第9.4节",
    ):
        assert marker in prompt
    for ref in (
        "body.p537",
        "body.p1210",
        "body.p1223",
        "body.p1236",
        "body.p1237",
        "body.p1248",
        "body.p1249",
        "body.p1250",
    ):
        assert ref not in prompt


def test_deterministic_gate_accepts_non_enrollment_dispositions(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units
    from slice59n_representative_group_reject_gates import evaluate_hydrated_agent_output

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
    issues = evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": [], "dispositions": dispositions},
        allowed_structure_unit_ids=list(unit_by_ref.values()),
        required_candidate_source_refs=[],
        forbidden_candidate_source_refs=OWNED,
        expected_disposition_by_source_ref=EXPECTED_DISPOSITIONS,
        expected_workflow_stage_ids_by_source_ref={},
        candidate_forbidden_markers_by_source_ref=config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        candidate_required_markers_by_source_ref={},
    )
    assert issues == []


def test_hydrated_gate_rejects_subject_control_attacks_by_source_identity(
    config: dict,
) -> None:
    from slice59n_representative_group_control_replay import _resolve_units
    from slice59n_representative_group_reject_gates import evaluate_hydrated_agent_output

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
    common = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "allowed_structure_unit_ids": list(unit_by_ref.values()),
        "required_candidate_source_refs": [],
        "forbidden_candidate_source_refs": OWNED,
        "expected_disposition_by_source_ref": EXPECTED_DISPOSITIONS,
        "expected_workflow_stage_ids_by_source_ref": {},
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": {},
    }
    attacks = {
        "body.p1238": "数据采集与管理决定受试者资格。",
        "body.p1239": "数据质量不合格不得入组。",
        "body.p1240": "数据质疑未解决不得入组。",
        "body.p1241": "eCRF决定受试者资格。",
        "body.p1242": "研究者未电子签名不得入组。",
        "body.p1243": "源数据定义决定受试者资格。",
        "body.p1244": "核证副本不合格不得入组。",
        "body.p1245": "源数据认定决定受试者资格。",
        "body.p1246": "审核跟踪缺失不得入组。",
        "body.p1247": "不能直接访问源文件不得入组。",
    }
    for ref, title in attacks.items():
        issues = evaluate_hydrated_agent_output(
            **common,
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


def test_checklist_records_source_driven_boundary() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    for phrase in (
        "papl-e17d498106b6f71f440ff2be",
        "pap-b8d5cdfbc6ac4c373c6576b3",
        "body.p1238",
        "body.p1247",
        "body.p1248",
        "先读源文，再决定候选处置",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "supporting_or_supplement",
        "证据接受边界",
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
