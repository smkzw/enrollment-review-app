#!/usr/bin/env python3
"""Model-free Package 109 study records/deviation/monitoring regressions.

The tests freeze Package 109 ownership for body.p1270-p1280, keep the 37
context units read-only, preserve Package 108/110 boundaries, and prove that
study-recordkeeping, archive retention, protocol-deviation recording,
serious-deviation in-study withdrawal disposition, onsite monitoring access,
and IWRS/sample/EDC management-infrastructure wording are not inverted into
subject eligibility while any real pre-participation control would still be
retained if present in source.

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
    "representative_group_package109_study_records_deviation_monitoring_management_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cv-package109-study-records-deviation-monitoring-management-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package109-study-records-deviation-monitoring-management-boundary"
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
PACKAGE_ORDINAL = 109
PACKAGE_ID = "pap-2101c87c43a5499476169b81"
PACKAGE108_ID = "pap-f3fa399755a65a5a57ba306c"
PACKAGE110_ID = "pap-7358ad349433c3c08aacc5f1"

OWNED = [
    "body.p1270",
    "body.p1271",
    "body.p1272",
    "body.p1273",
    "body.p1274",
    "body.p1275",
    "body.p1276",
    "body.p1277",
    "body.p1278",
    "body.p1279",
    "body.p1280",
]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = [
    "body.p1270",
    "body.p1271",
    "body.p1274",
    "body.p1277",
    "body.p1279",
]
GOVERNANCE = [
    "body.p1272",
    "body.p1273",
    "body.p1275",
    "body.p1276",
    "body.p1278",
    "body.p1280",
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
    "body.p1270": "研究文件、监查和管理",
    "body.p1271": "研究文件",
    "body.p1272": (
        "研究者必须保存足够且准确的记录，以便完整记录研究的执行过程，包括但不限于方案、"
        "方案修正案、知情同意书和IRB/EC与政府批准文件。此外，在研究结束时，研究者可以获得"
        "该中心的参与者数据，包括含有所有数据变更完整记录的稽查跟踪数据。"
    ),
    "body.p1273": (
        "研究开始时，研究中心、分析检测单位、申办者三方均应各自建立研究文件的档案管理。"
        "研究结束时，监查员必须审核确认各研究中心、分析检测单位、申办者各自的文件，这些文件"
        "必须被妥善的保存在各自的临床研究档案卷宗内。"
    ),
    "body.p1274": "方案偏离",
    "body.p1275": (
        "研究方案中规定的所有要求，必须严格执行。任何有意或无意偏离试验方案和GCP原则的行为，"
        "均可归类为偏离方案。临床监查员在监查过程中，如果发现偏离方案时应填写偏离方案记录，"
        "详细记录事件发生的时间、过程、原因、相应的处理措施等适用项，由研究者签字，并通报"
        "伦理委员会及申办者。在数据统计和总结报告中，研究者对发生的方案偏离对最终数据和结论"
        "的影响进行分析和报告。"
    ),
    "body.p1276": (
        "所有方案偏离情况必须记录在源文件中。所有方案偏离必须按照伦理委员会规定递交以供审查。"
        "研究者有责任知悉并遵行伦理委员会相关规定。当发生严重方案偏离时，应进行评估。必要时，"
        "参与者需退出研究。"
    ),
    "body.p1277": "现场监查/检查",
    "body.p1278": (
        "研究中心访视将由申办者或授权的代表进行研究数据、参与者病历和eCRFs的监查。研究者将"
        "允许国家和地方卫生当局、申办者监查员、代表和合作者，以及IRB/EC检查与本研究相关的"
        "设施和记录。"
    ),
    "body.p1279": "管理结构",
    "body.p1280": (
        "申办者或其代理人将执行项目管理、研究管理、监查、供应商管理和统计编程。可使用IWRS"
        "进行参与者筛查和随机分组，以及研究药物申请和运输的管理。研究中心将负责生物样品在"
        "运输至申办者或其指定分析单位之前的保存。数据将使用eCRFs通过EDC系统记录，或以电子"
        "方式转发给申办者（例如，药代动力学数据）。"
    ),
}
SOURCE_ORDERS = [
    31330,
    31340,
    31350,
    31360,
    31370,
    31380,
    31390,
    31400,
    31410,
    31420,
    31430,
]
HEADING_PATHS = {
    "body.p1270": ["研究文件、监查和管理"],
    "body.p1271": ["研究文件、监查和管理", "研究文件"],
    "body.p1272": ["研究文件、监查和管理", "研究文件"],
    "body.p1273": ["研究文件、监查和管理", "研究文件"],
    "body.p1274": ["研究文件、监查和管理", "方案偏离"],
    "body.p1275": ["研究文件、监查和管理", "方案偏离"],
    "body.p1276": ["研究文件、监查和管理", "方案偏离"],
    "body.p1277": ["研究文件、监查和管理", "现场监查/检查"],
    "body.p1278": ["研究文件、监查和管理", "现场监查/检查"],
    "body.p1279": ["研究文件、监查和管理", "管理结构"],
    "body.p1280": ["研究文件、监查和管理", "管理结构"],
}
EXPECTED_OWNER_MAP = {
    "body.p1269": 108,
    "body.p1270": 109,
    "body.p1271": 109,
    "body.p1272": 109,
    "body.p1273": 109,
    "body.p1274": 109,
    "body.p1275": 109,
    "body.p1276": 109,
    "body.p1277": 109,
    "body.p1278": 109,
    "body.p1279": 109,
    "body.p1280": 109,
    "body.p1281": 110,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1270": "study_records_monitoring_management_chapter_heading",
    "body.p1271": "study_records_subsection_heading",
    "body.p1272": "study_recordkeeping_and_audit_trail_governance",
    "body.p1273": "study_archive_establishment_review_and_retention_governance",
    "body.p1274": "protocol_deviation_subsection_heading",
    "body.p1275": (
        "protocol_deviation_identification_recording_notification_and_summary_governance"
    ),
    "body.p1276": (
        "serious_protocol_deviation_assessment_and_in_study_withdrawal_disposition"
    ),
    "body.p1277": "onsite_monitoring_inspection_subsection_heading",
    "body.p1278": (
        "onsite_monitoring_inspection_and_facility_record_access_governance"
    ),
    "body.p1279": "management_structure_subsection_heading",
    "body.p1280": (
        "sponsor_management_iwrs_sample_storage_and_edc_infrastructure_capability"
    ),
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


def test_config_contract_keeps_study_governance_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package109-study-records-deviation-monitoring-management-boundary"
    )
    assert config["task_id"] == "phase5-slice61cv-20260830"
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
            "manifest:slice61cv-package109-study-records-deviation-monitoring-management-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cv-package109-study-records-deviation-monitoring-management-boundary"
        ),
    }


def test_config_preserves_four_layer_governance_semantics(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "稽查跟踪数据",
        "建立研究文件的档案管理",
        "所有要求，必须严格执行",
        "通报伦理委员会及申办者",
        "必要时，参与者需退出研究",
        "严重方案偏离",
        "检查与本研究相关的设施和记录",
        "可使用IWRS进行参与者筛查和随机分组",
        "eCRFs通过EDC系统记录",
        "Package 108",
        "Package 110",
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

    p1275 = semantics["body.p1275"]
    assert "不得脱离具体要求生成一个泛化的单例入排控制" in p1275["exception_rule"]
    assert "所有要求，必须严格执行" in "；".join(p1275["preserve_keywords"])

    p1276 = semantics["body.p1276"]
    assert "在研处置" in p1276["exception_rule"]
    assert "参加研究前控制" in p1276["exception_rule"]
    assert "必要时，参与者需退出研究" in p1276["preserve_keywords"]

    p1280 = semantics["body.p1280"]
    assert "基础设施用途" in p1280["exception_rule"]
    assert "不等于该段新建筛选" in p1280["exception_rule"]
    assert "可使用IWRS进行参与者筛查和随机分组" in p1280["preserve_keywords"]


def test_source_identity_blocks_eligibility_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "研究文件记录决定单例资格",
        "稽查跟踪缺失不得入组",
    } <= set(forbidden["body.p1272"])
    assert {
        "档案管理决定单例资格",
        "研究开始档案未建立不得入组",
    } <= set(forbidden["body.p1273"])
    assert {
        "所有要求必须严格执行决定单例资格",
        "泛化方案遵从改写为入排控制",
        "偏离方案记录缺失不得入组",
    } <= set(forbidden["body.p1275"])
    assert {
        "严重方案偏离决定筛选排除",
        "必要时退出研究误作入排排除",
        "偏离后在研退出倒置为参加研究前控制",
    } <= set(forbidden["body.p1276"])
    assert {
        "监查检查决定单例资格",
        "设施访问缺失不得入组",
    } <= set(forbidden["body.p1278"])
    assert {
        "IWRS筛查能力决定单例资格",
        "IWRS随机能力决定入排控制",
        "基础设施用途候选化为入排动作",
    } <= set(forbidden["body.p1280"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "稽查跟踪" in "；".join(checks["body.p1272"])
    assert "档案" in "；".join(checks["body.p1273"])
    assert "所有要求必须严格执行" in "；".join(checks["body.p1275"])
    assert "必要时，参与者需退出研究" in "；".join(checks["body.p1276"])
    assert "设施和记录" in "；".join(checks["body.p1278"])
    assert "IWRS" in "；".join(checks["body.p1280"])


def test_phase_applicability_explains_governance_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "研究文件",
        "方案偏离",
        "现场监查",
        "IWRS",
        "不是单例受试者",
        "Package 108",
        "Package 110",
        "p1269",
        "p1281",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得以other_control_candidate强挂" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_frozen_plan_owns_exact_package109_units(plan: dict, config: dict) -> None:
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
    assert owner_by_ref["body.p1269"] == 108
    assert owner_by_ref["body.p1281"] == 110
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_context_units_remain_read_only_and_unowned_partition(
    plan: dict,
    config: dict,
) -> None:
    package109 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package109["context_units"]]
    assert len(context_refs) == 37
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1269" not in context_refs
    assert "body.p1281" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1269"] == [108]
    assert owners["body.p1270"] == [109]
    assert owners["body.p1280"] == [109]
    assert owners["body.p1281"] == [110]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package109["context_units"]
        if unit["source_ref"] not in owners
    ]
    assert len(expected_unowned_context_refs) == 26
    assert config["later_package_boundary"]["unowned_context_source_refs"] == (
        expected_unowned_context_refs
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


def test_resolver_keeps_package109_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 11
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 11
    for row in rows:
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert row.source_span_ids == (row.source_ref,)
        assert row.member_source_refs == (row.source_ref,)
    assert [row.excerpt for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1269",
        "body.p1281",
        "body.p1260",
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
    attack["owned_source_refs"] = ["body.p1275"]
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
    assert summary["owned_count"] == 11
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 11
    assert summary["lookup_counts"] == {"frozen_plan_owned": 11}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 11
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 11
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 11
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 11
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == OWNED
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

    assert prompt_meta["owned_count"] == 11
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
        "保存足够且准确的记录",
        "稽查跟踪数据",
        "建立研究文件的档案管理",
        "所有要求，必须严格执行",
        "通报伦理委员会及申办者",
        "必要时，参与者需退出研究",
        "检查与本研究相关的设施和记录",
        "可使用IWRS进行参与者筛查和随机分组",
        "eCRFs通过EDC系统记录",
    ):
        assert marker in prompt
    for ref in (
        "body.p1260",
        "body.p1269",
        "body.p1281",
        "body.p1290",
        PACKAGE108_ID,
        PACKAGE110_ID,
    ):
        assert ref not in prompt


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
        ("body.p1270", "研究文件监查管理标题决定受试者资格"),
        ("body.p1271", "研究文件标题决定受试者资格"),
        ("body.p1272", "研究文件记录决定单例资格"),
        ("body.p1273", "档案管理决定单例资格"),
        ("body.p1274", "方案偏离标题决定受试者资格"),
        ("body.p1275", "所有要求必须严格执行决定单例资格"),
        ("body.p1275", "泛化方案遵从改写为入排控制"),
        ("body.p1276", "严重方案偏离决定筛选排除"),
        ("body.p1276", "必要时退出研究误作入排排除"),
        ("body.p1276", "偏离后在研退出倒置为参加研究前控制"),
        ("body.p1277", "现场监查检查标题决定受试者资格"),
        ("body.p1278", "监查检查决定单例资格"),
        ("body.p1279", "管理结构标题决定受试者资格"),
        ("body.p1280", "IWRS筛查能力决定单例资格"),
        ("body.p1280", "基础设施用途候选化为入排动作"),
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
        "pap-2101c87c43a5499476169b81",
        "body.p1270",
        "body.p1275",
        "body.p1276",
        "body.p1280",
        "body.p1269",
        "body.p1281",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "所有要求必须严格执行",
        "必要时，参与者需退出研究",
        "IWRS",
        "稽查跟踪",
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
