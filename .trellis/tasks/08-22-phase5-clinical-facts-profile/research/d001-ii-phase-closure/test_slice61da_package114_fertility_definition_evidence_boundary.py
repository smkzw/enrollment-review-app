#!/usr/bin/env python3
"""Model-free Package 114 fertility-definition / evidence-boundary regressions.

Locks appendix structure, childbearing-potential definition, non-childbearing
parent/child OR logic, bilateral surgery terms, parallel confirmation methods,
and Package 113/115 isolation for body.p1310-p1321 without absorbing Package115
menopause diagnosis or contraception clauses.
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
    "representative_group_package114_fertility_definition_evidence_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61da-package114-fertility-definition-evidence-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package114-fertility-definition-evidence-boundary"
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
PACKAGE_ORDINAL = 114
PACKAGE_ID = "pap-cd76207b0f3d157c2eaa66d6"
PACKAGE113_ID = "pap-d042355fa4845796808fa256"
PACKAGE115_ID = "pap-9fb70d121e089bc533c21255"

OWNED = [f"body.p{i}" for i in range(1310, 1322)]
ATTACHED = ["body.p1322"]
ORDERED = [*OWNED, *ATTACHED]
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = ["body.p1310", "body.p1311", "body.p1312"]
EXPECTED_DISPOSITIONS = {
    ref: "supporting_or_supplement" for ref in OWNED if ref not in STRUCTURAL_ONLY
}
KNOWN_OFFICIAL_CODE = "IN-06"
KNOWN_PROCEDURE_ID = "pcm-row-18127a0dc9921364671ebb8c"
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
    "body.p1310": "附录",
    "body.p1311": "附录1 避孕的规定与方法",
    "body.p1312": "有生育能力女性的定义",
    "body.p1313": "女性在月经初潮后至绝经前被认为是有生育能力的。",
    "body.p1314": "具有以下情况的女性不被视为有生育能力：",
    "body.p1315": "尚未经历月经初潮",
    "body.p1316": "满足以下任一项的绝经前女性：",
    "body.p1317": "子宫切除术史",
    "body.p1318": "双侧输卵管切除术史",
    "body.p1319": "双侧卵巢切除术史",
    "body.p1320": "注：通过参与者病历核查或医学检查或病史询问进行确认。",
    "body.p1321": "绝经后女性",
    "body.p1322": "女性连续停经12个月，并排除妊娠及其他可能导致闭经的医疗原因后，即可临床诊断为绝经。",
}
EXPECTED_UNIT_KINDS = {
    "body.p1310": "paragraph",
    "body.p1311": "paragraph",
    "body.p1312": "list_item",
    "body.p1313": "paragraph",
    "body.p1314": "paragraph",
    "body.p1315": "list_item",
    "body.p1316": "list_item",
    "body.p1317": "list_item",
    "body.p1318": "list_item",
    "body.p1319": "list_item",
    "body.p1320": "footnote_or_annotation",
    "body.p1321": "list_item",
    "body.p1322": "list_item",
}
EXPECTED_SPANS = {ref: [ref] for ref in ORDERED}
SOURCE_ORDERS = list(range(32060, 32190, 10))
HEADING_PATHS = {ref: ["附录"] for ref in ORDERED}
EXPECTED_OWNER_MAP = {
    "body.p1308": 113,
    **{ref: 114 for ref in OWNED},
    "body.p1322": 115,
    "body.p1323": 115,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1310": "appendix_structure_heading",
    "body.p1311": "appendix_contraception_section_heading",
    "body.p1312": "fertility_definition_section_heading",
    "body.p1313": "childbearing_potential_time_window_definition",
    "body.p1314": "non_childbearing_parent_condition_or_root",
    "body.p1315": "non_childbearing_or_branch_premenarche",
    "body.p1316": "non_childbearing_or_branch_premenopausal_any_surgery_parent",
    "body.p1317": "surgery_history_or_branch_hysterectomy",
    "body.p1318": "surgery_history_or_branch_bilateral_salpingectomy",
    "body.p1319": "surgery_history_or_branch_bilateral_oophorectomy",
    "body.p1320": "parallel_confirmation_methods_note",
    "body.p1321": "non_childbearing_or_branch_postmenopausal_incomplete_without_p1322",
}
EXPECTED_OWNED_SOURCE_SPAN_IDS = sorted(
    {span for ref in OWNED for span in EXPECTED_SPANS[ref]}
)
EXCLUDED_UNOWNED_STRUCTURE_REFS = ["body.p1309"]
PACKAGE115_REFS = [f"body.p{i}" for i in range(1322, 1334)]
PARENT_OR_CHILDREN = ["body.p1315", "body.p1316", "body.p1321"]
SURGERY_OR_CHILDREN = ["body.p1317", "body.p1318", "body.p1319"]


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


def test_freeze_identity_hashes() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256(STRUCTURE_PATH) == EXPECTED_STRUCTURE_SHA256
    assert CHECKLIST_PATH.is_file()


def test_config_contract_keeps_definition_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package114-fertility-definition-evidence-boundary"
    )
    assert config["task_id"] == "phase5-slice61da-20260830"
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
    assert [
        item["official_code"]
        for item in config["known_targets"]["official_rules"]
    ] == [KNOWN_OFFICIAL_CODE]
    assert [
        item["catalog_item_id"]
        for item in config["known_targets"]["required_procedures"]
    ] == [KNOWN_PROCEDURE_ID]
    assert config["phase_applicability"]["disposition"] == (
        "selected_phase_applicable"
    )
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": (
            "manifest:slice61da-package114-fertility-definition-evidence-boundary"
        ),
        "catalog_id": (
            "catalog:slice61da-package114-fertility-definition-evidence-boundary"
        ),
    }


def test_config_preserves_parent_child_or_and_package115_boundary(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "并列OR",
        "任一项",
        "双侧",
        "病历核查",
        "医学检查",
        "病史询问",
        "不得压平为AND",
        "Package 113",
        "Package 115",
        "body.p1322",
        "required candidates为空",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
        "supporting_or_supplement",
    ):
        assert phrase in combined

    semantics = config["exception_semantics_by_source_ref"]
    for ref, role in SEMANTIC_ROLES.items():
        assert semantics[ref]["semantic_role"] == role
        assert semantics[ref]["base_rule"] == EXPECTED_EXCERPTS[ref]

    parent = semantics["body.p1314"]["logic_tree"]
    assert parent["operator"] == "OR"
    assert parent["children"] == PARENT_OR_CHILDREN
    surgery = semantics["body.p1316"]["logic_tree"]
    assert surgery["operator"] == "OR"
    assert surgery["children"] == SURGERY_OR_CHILDREN
    confirm = semantics["body.p1320"]["logic_tree"]
    assert confirm["operator"] == "OR"
    assert confirm["children_methods"] == ["病历核查", "医学检查", "病史询问"]
    assert "双侧" in semantics["body.p1318"]["base_rule"]
    assert "双侧" in semantics["body.p1319"]["base_rule"]
    assert "Package115" in semantics["body.p1321"]["exception_rule"]
    assert "body.p1322" in semantics["body.p1321"]["exception_rule"]


def test_source_identity_blocks_or_and_package115_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert "不视为有生育能力父条件压平为AND" in forbidden["body.p1314"]
    assert "任一项手术史压平为全部同时满足" in forbidden["body.p1316"]
    assert "双侧条件丢失" in forbidden["body.p1318"]
    assert "双侧条件丢失" in forbidden["body.p1319"]
    assert "三种确认方式压平为AND" in forbidden["body.p1320"]
    assert "核查方式丢失" in forbidden["body.p1320"]
    assert "吸收body.p1322绝经诊断条款并发布候选" in forbidden["body.p1321"]
    assert "吸收Package115避孕起始时点" in forbidden["body.p1311"]


def test_phase_applicability_explains_definition_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "有生育能力女性的定义",
        "并列OR",
        "Package 113",
        "Package 115",
        "p1322",
        "不是新的独立筛选",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得复制既有控制点" in batch_reason
    assert "不得把父子OR压平为AND" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )
    assert config["later_package_boundary"]["excluded_unowned_structure_refs"] == (
        EXCLUDED_UNOWNED_STRUCTURE_REFS
    )
    assert config["later_package_boundary"]["forbidden_next_package_refs"] == (
        PACKAGE115_REFS
    )


def test_frozen_plan_owns_exact_package114_units(plan: dict, config: dict) -> None:
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
    assert owner_by_ref["body.p1308"] == 113
    assert owner_by_ref["body.p1322"] == 115
    assert owner_by_ref["body.p1323"] == 115
    assert "body.p1309" not in owner_by_ref
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(owner_by_ref)
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_package113_and_package115_stay_outside_owned_inputs(
    plan: dict,
    config: dict,
) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    package113 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == 113
    )
    package115 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == 115
    )
    assert package113["package_id"] == PACKAGE113_ID
    assert package115["package_id"] == PACKAGE115_ID
    package113_refs = {unit["source_ref"] for unit in package113["owned_units"]}
    package115_refs = {unit["source_ref"] for unit in package115["owned_units"]}
    assert package113_refs == {"body.p1307", "body.p1308"}
    assert package115_refs == set(PACKAGE115_REFS)

    package114_inputs = set(config["owned_source_refs"])
    package114_inputs.update(config["attached_source_refs"])
    assert package113_refs.isdisjoint(package114_inputs)
    assert package115_refs & package114_inputs == {"body.p1322"}
    assert set(PACKAGE115_REFS[1:]).isdisjoint(package114_inputs)
    assert owner_by_ref["body.p1322"] == 115


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
    package114 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package114["context_units"]]
    assert len(context_refs) == 38
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs) & set(config["attached_source_refs"]) == {
        "body.p1322"
    }
    assert "body.p1322" in context_refs
    assert "body.p1322" in config["attached_source_refs"]
    assert "body.p1323" not in context_refs
    assert "body.p1308" not in context_refs
    assert "body.p1309" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1308"] == [113]
    assert owners["body.p1310"] == [114]
    assert owners["body.p1321"] == [114]
    assert owners["body.p1322"] == [115]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package114["context_units"]
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


def test_resolver_keeps_package114_owned_and_read_only_attached_roles(
    config: dict,
) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 12 + ["attached"]
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 13
    for row in rows[:12]:
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert list(row.source_span_ids) == EXPECTED_SPANS[row.source_ref]
        assert list(row.member_source_refs) == EXPECTED_SPANS[row.source_ref]
    attached = rows[-1]
    assert attached.source_ref == "body.p1322"
    assert attached.role == "attached"
    assert attached.lookup == "frozen_plan_owned"
    assert attached.package_ordinal == 115
    assert attached.package_id == PACKAGE115_ID
    assert list(attached.source_span_ids) == ["body.p1322"]
    assert [row.excerpt for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1308",
        "body.p1322",
        "body.p1323",
        "body.p1307",
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
    attack["owned_source_refs"] = ["body.p1313"]
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
    assert summary["owned_count"] == 12
    assert summary["attached_count"] == 1
    assert summary["unit_count"] == 13
    assert summary["lookup_counts"] == {"frozen_plan_owned": 13}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 12 + ["attached"]
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 13
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 12 + [
        115
    ]
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 12 + [
        PACKAGE115_ID
    ]
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows if row["role"] == "owned"]
    structural_ids = [
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] in STRUCTURAL_ONLY
    ]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == [
        rows[-1]["structure_unit_id"]
    ]
    assert batch["owned_source_span_ids"] == EXPECTED_OWNED_SOURCE_SPAN_IDS
    assert batch["context_source_span_ids"] == ["body.p1322"]
    assert batch["structural_only_structure_unit_ids"] == structural_ids
    assert batch["pre_enrollment_structure_unit_ids"] == []
    assert batch["owned_visit_instance_by_structure_unit_id"] == {}
    assert batch["owned_procedure_semantic_families_by_structure_unit_id"] == {}
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {}
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {}
    assert [
        item["official_code"] for item in batch["known_official_targets"]
    ] == [KNOWN_OFFICIAL_CODE]
    assert [
        item["catalog_item_id"] for item in batch["known_procedure_targets"]
    ] == [KNOWN_PROCEDURE_ID]
    assert [
        stage["workflow_stage_id"] for stage in batch["known_workflow_stage_targets"]
    ] == ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]

    assert prompt_meta["owned_count"] == 12
    assert prompt_meta["attached_count"] == 1
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
        "月经初潮后至绝经前",
        "不被视为有生育能力",
        "任一项",
        "双侧输卵管切除术史",
        "双侧卵巢切除术史",
        "病历核查",
        "医学检查",
        "病史询问",
        "绝经后女性",
    ):
        assert marker in prompt
    for ref in (
        "body.p1308",
        "body.p1307",
        *PACKAGE115_REFS[1:],
        PACKAGE113_ID,
        PACKAGE115_ID,
    ):
        assert ref not in prompt
    for ref in EXCLUDED_UNOWNED_STRUCTURE_REFS:
        assert f'"source_ref":"{ref}"' not in prompt
    assert "三种都必须执行" not in prompt
    assert "连续停经12个月" in prompt
    assert "禁止使用激素类避孕" not in prompt


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


def test_deterministic_gate_accepts_supporting_dispositions(
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
        ("body.p1314", "不视为有生育能力父条件压平为AND"),
        ("body.p1316", "任一项手术史压平为全部同时满足"),
        ("body.p1318", "双侧条件丢失"),
        ("body.p1318", "单侧输卵管切除即可"),
        ("body.p1319", "双侧条件丢失"),
        ("body.p1320", "病历核查且医学检查且病史询问都必须执行"),
        ("body.p1320", "三种确认方式压平为AND"),
        ("body.p1320", "核查方式丢失"),
        ("body.p1321", "吸收body.p1322绝经诊断条款并发布候选"),
        ("body.p1313", "月经初潮与绝经定义倒置"),
        ("body.p1311", "吸收Package115避孕起始时点"),
    ],
)
def test_hydrated_gate_rejects_or_flatten_and_package115_absorption(
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
    assert issues
    assert any(
        issue.code in {"FORBIDDEN_CANDIDATE_SOURCE", "FORBIDDEN_MARKER"}
        or "forbidden" in issue.message.lower()
        or source_ref in issue.source_refs
        for issue in issues
    )
