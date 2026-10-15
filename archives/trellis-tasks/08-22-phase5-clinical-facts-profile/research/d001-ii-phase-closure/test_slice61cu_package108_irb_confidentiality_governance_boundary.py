#!/usr/bin/env python3
"""Model-free Package 108 IRB/EC and confidentiality governance regressions.

The tests freeze Package 108 ownership for body.p1260-p1269, keep the 37
context units read-only, preserve Package 107/109 boundaries, and prove that
study-startup IRB/EC approval, recruitment-material approval, ongoing progress
reporting, SAE/safety communications, coding/confidentiality, PHI disclosure
authorization, monitor/audit access, private-physician disclosure, exploratory
result non-return, and regulatory inspection are not inverted into subject
eligibility while any real pre-participation control would still be retained if
present in source.

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
    "representative_group_package108_irb_confidentiality_governance_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cu-package108-irb-confidentiality-governance-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package108-irb-confidentiality-governance-boundary"
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
PACKAGE_ORDINAL = 108
PACKAGE_ID = "pap-f3fa399755a65a5a57ba306c"
PACKAGE107_ID = "pap-b119517783facd407b628e1e"
PACKAGE109_ID = "pap-2101c87c43a5499476169b81"

OWNED = [
    "body.p1260",
    "body.p1261",
    "body.p1262",
    "body.p1263",
    "body.p1264",
    "body.p1265",
    "body.p1266",
    "body.p1267",
    "body.p1268",
    "body.p1269",
]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = ["body.p1260", "body.p1264"]
GOVERNANCE = [
    "body.p1261",
    "body.p1262",
    "body.p1263",
    "body.p1265",
    "body.p1266",
    "body.p1267",
    "body.p1268",
    "body.p1269",
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
    "body.p1260": "机构审查委员会或伦理委员会",
    "body.p1261": (
        "在研究启动前，本方案、知情同意书、提供给参与者的任何信息，以及相关支持信息"
        "必须提交给IRB/EC审查和批准。此外，任何参与者招募材料也必须经IRB/EC批准。"
    ),
    "body.p1262": (
        "根据IRB/EC要求或既定程序，主要研究者负责每年或更频繁地向IRB/EC提交书面的"
        "研究进展报告。研究者也负责及时通知IRB/EC任何方案修正案。"
    ),
    "body.p1263": (
        "除向申办者报告SAE之外，适用时研究者还必须按要求向卫生主管部门和IRB/EC报告SAE。"
        "研究者可能会收到来自申办者的相关安全性报告或通信，研究者负责确保此类报告的审查"
        "和处理符合卫生主管部门要求及IRB/EC既定的政策和程序，并存档在研究中心的研究文件中。"
    ),
    "body.p1264": "保密",
    "body.p1265": (
        "研究中心将会对本次研究采集到的信息进行保密。参与者通过分配的唯一识别号参与研究，"
        "这意味着参与者姓名不会出现在传输至任何地方的数据集中。"
    ),
    "body.p1266": (
        "本研究获得的参与者医疗信息是保密的。除非法律允许或要求，否则，仅在参与者签署的"
        "知情同意书允许（或单独授权使用和披露个人健康信息）的情况下，可能会向第三方披露。"
    ),
    "body.p1267": (
        "研究期间向参与者收集的信息，将会得到妥善保管，只有研究者或授权的人员可以查看。"
        "参与者所有信息都会用数字、字母进行编号，而不使用参与者的姓名。只有研究者知道参与者"
        "对应的编号。在不违反保密原则和相关法规的情况下，研究者、申办者的相关人员（或代表）"
        "及法规机构和EC可能在研究相关的监查、稽查、EC/IRB审核过程中审查参与者的个人医疗记录。"
        "研究中心将会在法律允许范围内，全力保护参与者的隐私和健康信息。"
    ),
    "body.p1268": (
        "医疗信息可能向参与者的私人医生或负责参与者卫生福利或治疗目的的其他医疗人员提供。"
        "鉴于样品分析的复杂性和探究性，除非法律要求，否则通常不会向研究者或参与者提供来源于"
        "探究性生物标志物样本的数据。"
    ),
    "body.p1269": (
        "本研究生成的数据必须接受国家和地方卫生监管机构的代表、申办者监查员、各研究中心的"
        "代表、合作者和IRB/EC（如适用）的检查。"
    ),
}
SOURCE_ORDERS = [
    31230,
    31240,
    31250,
    31260,
    31270,
    31280,
    31290,
    31300,
    31310,
    31320,
]
HEADING_PATHS = {
    "body.p1260": ["伦理考虑", "机构审查委员会或伦理委员会"],
    "body.p1261": ["伦理考虑", "机构审查委员会或伦理委员会"],
    "body.p1262": ["伦理考虑", "机构审查委员会或伦理委员会"],
    "body.p1263": ["伦理考虑", "机构审查委员会或伦理委员会"],
    "body.p1264": ["伦理考虑", "保密"],
    "body.p1265": ["伦理考虑", "保密"],
    "body.p1266": ["伦理考虑", "保密"],
    "body.p1267": ["伦理考虑", "保密"],
    "body.p1268": ["伦理考虑", "保密"],
    "body.p1269": ["伦理考虑", "保密"],
}
EXPECTED_OWNER_MAP = {
    "body.p1251": 107,
    "body.p1259": 107,
    "body.p1260": 108,
    "body.p1261": 108,
    "body.p1262": 108,
    "body.p1263": 108,
    "body.p1264": 108,
    "body.p1265": 108,
    "body.p1266": 108,
    "body.p1267": 108,
    "body.p1268": 108,
    "body.p1269": 108,
    "body.p1270": 109,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1260": "irb_ec_subsection_heading",
    "body.p1261": "study_startup_irb_ec_and_recruitment_material_approval_governance",
    "body.p1262": "ongoing_irb_ec_progress_and_amendment_reporting_governance",
    "body.p1263": "sae_and_safety_communication_irb_ec_governance",
    "body.p1264": "confidentiality_subsection_heading",
    "body.p1265": "participant_coding_and_dataset_confidentiality_governance",
    "body.p1266": "phi_disclosure_authorization_and_third_party_access_governance",
    "body.p1267": "coded_restricted_access_and_monitor_audit_review_governance",
    "body.p1268": "private_physician_disclosure_and_exploratory_result_nonreturn_governance",
    "body.p1269": "regulatory_and_irb_ec_inspection_access_governance",
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


def test_config_contract_keeps_irb_confidentiality_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package108-irb-confidentiality-governance-boundary"
    )
    assert config["task_id"] == "phase5-slice61cu-20260830"
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
            "manifest:slice61cu-package108-irb-confidentiality-governance-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cu-package108-irb-confidentiality-governance-boundary"
        ),
    }


def test_config_preserves_five_layer_governance_semantics(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "研究启动前",
        "参与者招募材料",
        "书面的研究进展报告",
        "方案修正案",
        "向卫生主管部门和IRB/EC报告SAE",
        "安全性报告或通信",
        "唯一识别号",
        "签署的知情同意书允许",
        "单独授权使用和披露个人健康信息",
        "监查、稽查、EC/IRB审核",
        "私人医生",
        "探究性生物标志物样本",
        "国家和地方卫生监管机构的代表",
        "Package 107",
        "Package 109",
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

    p1261 = semantics["body.p1261"]
    assert "研究级启动门槛" in p1261["exception_rule"]
    assert "参与者招募材料" in "；".join(p1261["preserve_keywords"])
    assert "参加研究前资格" in p1261["exception_rule"]

    p1266 = semantics["body.p1266"]
    assert "隐私授权与信息访问治理" in p1266["exception_rule"]
    assert "重复Package 67/107" in p1266["exception_rule"]
    assert "签署的知情同意书允许" in p1266["preserve_keywords"]


def test_source_identity_blocks_eligibility_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "研究启动前未获IRB/EC批准不得入组",
        "招募材料未批准不得入组",
        "研究启动前误作筛选前资格",
        "伦理报批决定单例资格",
    } <= set(forbidden["body.p1261"])
    assert {
        "年度进展报告缺失不得入组",
        "方案修正案未通知IRB/EC不得入组",
    } <= set(forbidden["body.p1262"])
    assert {
        "SAE未报IRB/EC不得入组",
        "安全性通信未存档不得入组",
        "SAE上报决定单例资格",
    } <= set(forbidden["body.p1263"])
    assert {
        "资料保密决定单例资格",
        "未分配唯一识别号不得入组",
    } <= set(forbidden["body.p1265"])
    assert {
        "隐私授权决定单例资格",
        "ICF允许披露误作筛选资格",
        "单独授权缺失不得入组",
    } <= set(forbidden["body.p1266"])
    assert {
        "编码化与受限访问决定单例资格",
        "监查访问缺失不得入组",
    } <= set(forbidden["body.p1267"])
    assert {
        "结果不返还决定单例资格",
        "私人医生披露决定单例资格",
    } <= set(forbidden["body.p1268"])
    assert {
        "监管检查决定单例资格",
        "监管检查未完成不得入组",
    } <= set(forbidden["body.p1269"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "参与者招募材料" in "；".join(checks["body.p1261"])
    assert "研究启动前" in "；".join(checks["body.p1261"])
    assert "SAE" in "；".join(checks["body.p1263"])
    assert "签署的知情同意书允许" in "；".join(checks["body.p1266"])
    assert "探究性生物标志物" in "；".join(checks["body.p1268"])
    assert "监管" in "；".join(checks["body.p1269"])


def test_phase_applicability_explains_governance_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "IRB/EC",
        "保密",
        "研究启动",
        "SAE",
        "隐私",
        "监管检查",
        "不是单例受试者",
        "Package 107",
        "Package 109",
        "p1259",
        "p1270",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得以other_control_candidate强挂" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_frozen_plan_owns_exact_package108_units(plan: dict, config: dict) -> None:
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
    assert owner_by_ref["body.p1259"] == 107
    assert owner_by_ref["body.p1270"] == 109
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_context_units_remain_read_only_and_unowned_partition(
    plan: dict,
    config: dict,
) -> None:
    package108 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package108["context_units"]]
    assert len(context_refs) == 37
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1259" not in context_refs
    assert "body.p1270" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1259"] == [107]
    assert owners["body.p1260"] == [108]
    assert owners["body.p1269"] == [108]
    assert owners["body.p1270"] == [109]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package108["context_units"]
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


def test_resolver_keeps_package108_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 10
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 10
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
        "body.p1259",
        "body.p1270",
        "body.p1251",
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
    attack["owned_source_refs"] = ["body.p1261"]
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
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 10
    assert summary["lookup_counts"] == {"frozen_plan_owned": 10}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 10
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 10
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 10
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 10
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == OWNED
    assert batch["context_source_span_ids"] == []
    assert batch["structural_only_structure_unit_ids"] == [
        owned_ids[0],
        owned_ids[4],
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

    assert prompt_meta["owned_count"] == 10
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
        "在研究启动前",
        "参与者招募材料",
        "书面的研究进展报告",
        "向卫生主管部门和IRB/EC报告SAE",
        "唯一识别号",
        "签署的知情同意书允许",
        "单独授权使用和披露个人健康信息",
        "监查、稽查、EC/IRB审核",
        "私人医生",
        "探究性生物标志物样本",
        "国家和地方卫生监管机构的代表",
    ):
        assert marker in prompt
    for ref in (
        "body.p1251",
        "body.p1259",
        "body.p1270",
        "body.p768",
        PACKAGE107_ID,
        PACKAGE109_ID,
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
        ("body.p1260", "IRB/EC标题决定受试者资格"),
        ("body.p1261", "研究启动前未获IRB/EC批准不得入组"),
        ("body.p1261", "招募材料未批准不得入组"),
        ("body.p1261", "研究启动前误作筛选前资格"),
        ("body.p1262", "年度进展报告缺失不得入组"),
        ("body.p1263", "SAE未报IRB/EC不得入组"),
        ("body.p1263", "安全性通信未存档不得入组"),
        ("body.p1264", "保密标题决定受试者资格"),
        ("body.p1265", "资料保密决定单例资格"),
        ("body.p1266", "隐私授权决定单例资格"),
        ("body.p1266", "ICF允许披露误作筛选资格"),
        ("body.p1267", "编码化与受限访问决定单例资格"),
        ("body.p1268", "结果不返还决定单例资格"),
        ("body.p1269", "监管检查决定单例资格"),
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
        "pap-f3fa399755a65a5a57ba306c",
        "body.p1260",
        "body.p1261",
        "body.p1269",
        "body.p1259",
        "body.p1270",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "参与者招募材料",
        "年度",
        "SAE",
        "签署的知情同意书允许",
        "探究性生物标志物",
        "监管",
        "不得调用临床语义模型",
        "不得发布 control point",
        "Patient Profile",
        "parent clinical acceptance",
        "claims_complete=false",
        "零候选不是预设",
    ):
        assert phrase in text


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256(STRUCTURE_PATH) == EXPECTED_STRUCTURE_SHA256
    assert CONFIG_PATH.exists()
    assert CHECKLIST_PATH.exists()
