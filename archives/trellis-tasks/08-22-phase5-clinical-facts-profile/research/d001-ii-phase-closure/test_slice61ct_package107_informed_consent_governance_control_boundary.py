#!/usr/bin/env python3
"""Model-free Package 107 informed-consent governance regressions.

The tests freeze Package 107 ownership for body.p1251-p1259, keep the 41
context units read-only, preserve Package 67 screening-before explanation /
voluntary ICF signature as non-duplicated authority, and prove ethics approval,
ICF template content, and ongoing disclosure are not inverted into subject
eligibility while signature/date/understanding/re-consent semantics are retained.

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
    "representative_group_package107_informed_consent_governance_control_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61ct-package107-informed-consent-governance-control-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package107-informed-consent-governance-control-boundary"
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
PACKAGE_ORDINAL = 107
PACKAGE_ID = "pap-b119517783facd407b628e1e"
PACKAGE67_ID = "pap-94f383363b62f9768daa21a7"
PACKAGE106_ID = "pap-2bfe896140d41556d48a5132"
PACKAGE108_ID = "pap-f3fa399755a65a5a57ba306c"

OWNED = [
    "body.p1251",
    "body.p1252",
    "body.p1253",
    "body.p1254",
    "body.p1255",
    "body.p1256",
    "body.p1257",
    "body.p1258",
    "body.p1259",
]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
REQUIRED_CANDIDATES = ["body.p1257", "body.p1259"]
FORBIDDEN_CANDIDATES = [
    "body.p1251",
    "body.p1252",
    "body.p1253",
    "body.p1254",
    "body.p1255",
    "body.p1256",
    "body.p1258",
]
STRUCTURAL_ONLY = ["body.p1251", "body.p1252", "body.p1255"]
GOVERNANCE = [
    "body.p1253",
    "body.p1254",
    "body.p1256",
    "body.p1258",
]
EXPECTED_DISPOSITIONS = {
    **{ref: "non_enrollment_execution" for ref in GOVERNANCE},
    "body.p1257": "other_control_candidate",
    "body.p1259": "other_control_candidate",
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
PACKAGE67_DEDUP_MARKERS = [
    "筛选前解释所有研究程序",
    "获得参与者自愿签署的ICF",
    "筛选前签署知情同意书",
]
EXPECTED_EXCERPTS = {
    "body.p1251": "伦理考虑",
    "body.p1252": "遵守法律法规",
    "body.p1253": (
        "本研究将完全按照ICH E6和我国GCP指导原则、赫尔辛基宣言、相关法律法规及伦理委员会审核意见进行，"
        "以提供并加强对个人的保护。"
    ),
    "body.p1254": (
        "在研究开始之前，研究者应将研究方案、知情同意书以及其他必需的材料交于伦理委员会供其审阅及批准。"
        "申办者只有在接到伦理委员会的批准件后才能提供研究药物。同时必须告知伦理委员会可能会影响参与者安全和"
        "继续参加研究的后续方案增补件和在试验过程中发生的严重不良事件。研究者有责任向伦理委员会报告有关研究的进展情况。"
        "此外，研究者必须及时将与伦理委员会之间的所有的通讯副本交于申办者。伦理委员会在审阅及批准研究方案时，"
        "必须确认方案/研究标题，方案/研究编号，并注明已评审的方案文件及评审日期。在研究进行期间，如果研究方案、"
        "知情同意书等有任何新增修订，都应根据法规再次获得相关管理单位的书面核准意见。"
    ),
    "body.p1255": "知情同意",
    "body.p1256": "ICF（和研究方案一起）必须经伦理委员会审查及批准。",
    "body.p1257": (
        "研究者必须以口头和书面两种方式告知有关本研究的信息。若参与者或者其监护人无阅读能力，公正见证人须阅读"
        "ICF和其他书面资料（如有），并见证知情同意。研究者或其指定人员有责任用参与者可以理解的方式和措词就ICF的"
        "内容向参与者（或其监护人、见证人）解释，使参与者或者其监护人、见证人易于理解。研究者获得可能影响参与者"
        "继续参加研究的新信息时，应及时告知参与者（或其监护人），并做相应记录。"
    ),
    "body.p1258": (
        "最终的ICF文本和提供给参与者的其他资料应包含以下内容：研究概况、研究目的、研究的过程与期限、参与者需要遵守"
        "的研究步骤、参与者的义务、参与者预期可能的受益（包括不获益的可能性）和风险，告知参与者可能被分配到研究的"
        "不同组别及分配至各组的可能性；如发生与研究相关的损害时，参与者可以获得的治疗和相应的补偿；参与者参加临床"
        "研究可能获得的补偿；参与者自愿参加本研究；参与者个人资料的保密原则等。"
    ),
    "body.p1259": (
        "签署ICF之前，研究者或其指定研究人员应当给予参与者（或其监护人）充分的时间和机会了解临床研究的详细情况。"
        "参与者（或其监护人）以及执行知情同意的研究者应当在ICF上分别签名并注明日期（若非参与者本人签署，应当注明关系）。"
        "ICF应由研究者和参与者各保留1份。如发现涉及研究药物的重要新资料，则必须将ICF作书面修改送伦理委员会批准后，"
        "再次取得参与者（或其监护人）同意。"
    ),
}
SOURCE_ORDERS = [31140, 31150, 31160, 31170, 31180, 31190, 31200, 31210, 31220]
HEADING_PATHS = {
    "body.p1251": ["伦理考虑"],
    "body.p1252": ["伦理考虑", "遵守法律法规"],
    "body.p1253": ["伦理考虑", "遵守法律法规"],
    "body.p1254": ["伦理考虑", "遵守法律法规"],
    "body.p1255": ["伦理考虑", "知情同意"],
    "body.p1256": ["伦理考虑", "知情同意"],
    "body.p1257": ["伦理考虑", "知情同意"],
    "body.p1258": ["伦理考虑", "知情同意"],
    "body.p1259": ["伦理考虑", "知情同意"],
}
EXPECTED_OWNER_MAP = {
    "body.p768": 67,
    "body.p1248": 106,
    "body.p1249": 106,
    "body.p1250": 106,
    "body.p1251": 107,
    "body.p1252": 107,
    "body.p1253": 107,
    "body.p1254": 107,
    "body.p1255": 107,
    "body.p1256": 107,
    "body.p1257": 107,
    "body.p1258": 107,
    "body.p1259": 107,
    "body.p1260": 108,
}
SEMANTIC_ROLES = {
    "body.p1251": "ethics_considerations_section_heading",
    "body.p1252": "regulatory_compliance_subsection_heading",
    "body.p1253": "study_level_ethics_legal_compliance_governance",
    "body.p1254": "pre_study_and_ongoing_ethics_committee_governance",
    "body.p1255": "informed_consent_subsection_heading",
    "body.p1256": "icf_file_ethics_review_governance",
    "body.p1257": "informed_consent_process_and_ongoing_disclosure",
    "body.p1258": "icf_template_required_content_governance",
    "body.p1259": "pre_participation_signature_date_understanding_and_reconsent_controls",
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


def test_config_contract_separates_governance_from_pre_participation_controls(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package107-informed-consent-governance-control-boundary"
    )
    assert config["task_id"] == "phase5-slice61ct-20260830"
    assert config["worker"] == "codex-parent"
    assert config["study_phase"] == "phase_ii"
    assert config["expected_package_ordinal"] == PACKAGE_ORDINAL
    assert config["expected_package_id"] == PACKAGE_ID
    assert config["expected_protocol_sha256"] == EXPECTED_PROTOCOL_SHA256
    assert config["batching"]["mode"] == "single_batch_with_known_targets"

    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == REQUIRED_CANDIDATES
    assert config["forbidden_candidate_source_refs"] == FORBIDDEN_CANDIDATES
    assert config["pre_enrollment_source_refs"] == REQUIRED_CANDIDATES
    assert config["structural_only_source_refs"] == STRUCTURAL_ONLY
    assert config["attached_structural_only_source_refs"] == []
    assert config["expected_disposition_by_source_ref"] == EXPECTED_DISPOSITIONS
    assert config["expected_workflow_stage_ids_by_source_ref"] == {
        ref: ["flow-screening"] for ref in REQUIRED_CANDIDATES
    }
    assert config["owned_procedure_semantic_families_by_source_ref"] == {
        ref: ["informed_consent"] for ref in REQUIRED_CANDIDATES
    }
    assert config["owned_required_action_kinds_by_source_ref"] == {
        "body.p1257": [
            "communicate_with_participant",
            "explain_information",
            "witness_consent",
        ],
        "body.p1259": [
            "allow_informed_decision_time",
            "obtain_signature",
            "record_signature_date",
            "record_signer_relationship",
        ],
    }
    assert config["candidate_required_markers_by_source_ref"] == {
        "body.p1257": ["口头和书面", "公正见证人", "可以理解"],
        "body.p1259": ["充分的时间和机会", "分别签名并注明日期", "注明关系"],
    }
    assert config["known_targets"]["official_rules"] == []
    assert [
        item["catalog_item_id"]
        for item in config["known_targets"]["required_procedures"]
    ] == ["procedure:d001-icf-screening"]
    assert config["known_targets"]["required_procedures"][0][
        "covered_action_kinds"
    ] == ["obtain_signature"]
    assert config["phase_applicability"]["disposition"] == (
        "selected_phase_applicable"
    )
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["ids"] == {
        "manifest_id": (
            "manifest:slice61ct-package107-informed-consent-governance-control-boundary"
        ),
        "catalog_id": (
            "catalog:slice61ct-package107-informed-consent-governance-control-boundary"
        ),
    }


def test_config_preserves_four_layer_semantics_and_package67_dedup(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "研究级伦理治理",
        "ICF文件治理",
        "知情过程",
        "签署与重新同意控制",
        "筛选前解释所有研究程序",
        "自愿签署",
        "充分的时间和机会",
        "分别签名并注明日期",
        "注明关系",
        "各保留1份",
        "再次取得参与者",
        "公正见证人",
        "口头和书面",
        "Package 108",
        "claims_complete=false",
        "不调用临床语义模型",
        "Patient Profile",
    ):
        assert phrase in combined

    semantics = config["exception_semantics_by_source_ref"]
    for ref, role in SEMANTIC_ROLES.items():
        assert semantics[ref]["semantic_role"] == role
        assert semantics[ref]["base_rule"] == EXPECTED_EXCERPTS[ref]

    p1259 = semantics["body.p1259"]
    assert p1259["preserve_keywords"] == [
        "签署ICF之前",
        "充分的时间和机会",
        "了解临床研究的详细情况",
        "分别签名并注明日期",
        "若非参与者本人签署，应当注明关系",
        "研究者和参与者各保留1份",
        "重要新资料",
        "书面修改送伦理委员会批准后",
        "再次取得参与者（或其监护人）同意",
    ]
    assert "不得丢失" in p1259["exception_rule"]
    assert "第67包" in p1259["exception_rule"]

    p1257 = semantics["body.p1257"]
    assert "公正见证人" in p1257["preserve_keywords"]
    assert "不得重复第67包" in p1257["exception_rule"] or "不得重复" in p1257["exception_rule"]


def test_source_identity_blocks_eligibility_inversion_and_package67_duplicates(
    config: dict,
) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(OWNED)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])
    for ref in REQUIRED_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) - {"发布控制点"} <= set(forbidden[ref])

    assert {
        "伦理未批准不得入组",
        "伦理报批决定单例资格",
        "书面核准意见缺失即入排不通过",
    } <= set(forbidden["body.p1254"])
    assert {
        "ICF未经伦理批准不得入组",
        "ICF文件治理决定单例资格",
    } <= set(forbidden["body.p1256"])
    assert set(PACKAGE67_DEDUP_MARKERS) <= set(forbidden["body.p1257"])
    assert {
        "持续告知缺失不得入组",
        "持续告知决定单例资格",
    } <= set(forbidden["body.p1257"])
    assert {
        "ICF模板缺项不得入组",
        "ICF模板内容误作单例资格",
    } <= set(forbidden["body.p1258"])
    assert set(PACKAGE67_DEDUP_MARKERS) <= set(forbidden["body.p1259"])
    assert {
        "签署即可无需注明日期",
        "充分时间可省略",
        "非本人签署无需注明关系",
        "ICF只需一方留存",
        "重要新资料后无需再次同意",
        "通用ICF签署控制重复发布",
    } <= set(forbidden["body.p1259"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "充分的时间和机会" in "；".join(checks["body.p1259"])
    assert "分别签名并注明日期" in "；".join(checks["body.p1259"])
    assert "各保留1份" in "；".join(checks["body.p1259"])
    assert "再次取得参与者或其监护人同意" in "；".join(checks["body.p1259"])
    assert "不得重复发布第67包" in "；".join(checks["body.p1257"])
    assert "Package 108" in "；".join(checks["body.p1254"])


def test_phase_applicability_explains_ethics_not_subject_scope(config: dict) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "研究级伦理治理",
        "ICF文件/模板治理",
        "知情过程",
        "签署/重新同意",
        "不是单例资格",
        "适用于筛选期",
        "研究进行期治理",
        "第67包",
        "Package 106",
        "Package 108",
        "p1260",
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


def test_frozen_plan_owns_exact_package107_units(plan: dict, config: dict) -> None:
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
    assert len(package["context_units"]) == 41
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert owner_by_ref["body.p1250"] == 106
    assert owner_by_ref["body.p1260"] == 108
    assert owner_by_ref["body.p768"] == 67
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_context_units_remain_read_only_and_disjoint(plan: dict, config: dict) -> None:
    package107 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = {unit["source_ref"] for unit in package107["context_units"]}
    assert len(context_refs) == 41
    assert context_refs.isdisjoint(config["owned_source_refs"])
    assert context_refs.isdisjoint(config["attached_source_refs"])
    assert "body.p1260" not in context_refs
    assert "body.p768" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1250"] == [106]
    assert owners["body.p1251"] == [107]
    assert owners["body.p1259"] == [107]
    assert owners["body.p1260"] == [108]
    assert owners["body.p768"] == [67]
    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package107["context_units"]
        if unit["source_ref"] not in owners
    ]
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


def test_resolver_keeps_package107_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 9
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 9
    for row in rows:
        assert row.package_ordinal == PACKAGE_ORDINAL
        assert row.package_id == PACKAGE_ID
        assert row.source_span_ids == (row.source_ref,)
        assert row.member_source_refs == (row.source_ref,)
    assert [row.excerpt for row in rows] == [EXPECTED_EXCERPTS[ref] for ref in ORDERED]


@pytest.mark.parametrize(
    "source_ref",
    [
        "body.p1250",
        "body.p1260",
        "body.p768",
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
    attack["owned_source_refs"] = ["body.p1259"]
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
    assert summary["owned_count"] == 9
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 9
    assert summary["lookup_counts"] == {"frozen_plan_owned": 9}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 9
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 9
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 9
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 9
    assert [row["excerpt"] for row in rows] == [
        EXPECTED_EXCERPTS[ref] for ref in ORDERED
    ]

    owned_ids = [row["structure_unit_id"] for row in rows]
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}
    structural_ids = [
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] in STRUCTURAL_ONLY
    ]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == OWNED
    assert batch["context_source_span_ids"] == []
    assert batch["structural_only_structure_unit_ids"] == structural_ids
    required_ids = [unit_by_ref[ref] for ref in REQUIRED_CANDIDATES]
    assert batch["pre_enrollment_structure_unit_ids"] == required_ids
    assert batch["owned_visit_instance_by_structure_unit_id"] == {
        unit_id: "筛选访视" for unit_id in required_ids
    }
    assert batch["owned_procedure_semantic_families_by_structure_unit_id"] == {
        unit_id: ["informed_consent"] for unit_id in required_ids
    }
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {
        unit_by_ref["body.p1257"]: [
            "communicate_with_participant",
            "explain_information",
            "witness_consent",
        ],
        unit_by_ref["body.p1259"]: [
            "allow_informed_decision_time",
            "obtain_signature",
            "record_signature_date",
            "record_signer_relationship",
        ],
    }
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {
        unit_id: ["procedure:d001-icf-screening"] for unit_id in required_ids
    }
    assert batch["known_official_targets"] == []
    assert [
        item["catalog_item_id"] for item in batch["known_procedure_targets"]
    ] == ["procedure:d001-icf-screening"]
    assert [
        stage["workflow_stage_id"] for stage in batch["known_workflow_stage_targets"]
    ] == ["flow-screening", "flow-baseline", "flow-d1-pre-dose"]

    assert prompt_meta["owned_count"] == 9
    assert prompt_meta["attached_count"] == 0
    assert prompt_meta["context_structure_unit_ids"] == []
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
        "在研究开始之前",
        "口头和书面两种方式",
        "公正见证人",
        "充分的时间和机会",
        "分别签名并注明日期",
        "各保留1份",
        "书面修改送伦理委员会批准后",
    ):
        assert marker in prompt
    for ref in (
        "body.p1260",
        "body.p1248",
        "body.p1249",
        "body.p1250",
        "body.p768",
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


def _valid_candidates(unit_by_ref: dict[str, str]) -> list[dict]:
    return [
        {
            "frozen_structure_unit_ids": [unit_by_ref["body.p1257"]],
            "title": (
                "知情同意过程补充：口头和书面告知、公正见证人及可以理解的解释"
            ),
            "semantics": {
                "review_node_bindings": [
                    {"workflow_stage_id": "flow-screening"}
                ]
            },
        },
        {
            "frozen_structure_unit_ids": [unit_by_ref["body.p1259"]],
            "title": (
                "知情同意签署过程补充：充分的时间和机会、分别签名并注明日期，"
                "非本人签署注明关系"
            ),
            "semantics": {
                "review_node_bindings": [
                    {"workflow_stage_id": "flow-screening"}
                ]
            },
        },
    ]


def _gate_kwargs(config: dict, rows: list[dict], unit_by_ref: dict[str, str]) -> dict:
    return {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "allowed_structure_unit_ids": [unit_by_ref[ref] for ref in OWNED],
        "required_candidate_source_refs": REQUIRED_CANDIDATES,
        "forbidden_candidate_source_refs": FORBIDDEN_CANDIDATES,
        "expected_disposition_by_source_ref": EXPECTED_DISPOSITIONS,
        "expected_workflow_stage_ids_by_source_ref": {
            ref: ["flow-screening"] for ref in REQUIRED_CANDIDATES
        },
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": config[
            "candidate_required_markers_by_source_ref"
        ],
    }


def test_deterministic_gate_rejects_zero_candidate_semantic_loss(
    config: dict,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    issues = evaluate_hydrated_agent_output(
        hydrated={"candidates": [], "dispositions": dispositions},
        **_gate_kwargs(config, rows, unit_by_ref),
    )
    assert {
        issue.source_refs[0]
        for issue in issues
        if issue.code == "CONTROL_DELTA_DROPPED"
    } == set(REQUIRED_CANDIDATES)


def test_deterministic_gate_accepts_governance_and_incremental_controls(
    config: dict,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    issues = evaluate_hydrated_agent_output(
        hydrated={
            "candidates": _valid_candidates(unit_by_ref),
            "dispositions": dispositions,
        },
        **_gate_kwargs(config, rows, unit_by_ref),
    )
    assert issues == []


@pytest.mark.parametrize(
    ("source_ref", "title"),
    [
        ("body.p1253", "未按ICH E6执行不得入组"),
        ("body.p1254", "伦理未批准不得入组"),
        ("body.p1254", "伦理报批决定单例资格"),
        ("body.p1256", "ICF未经伦理批准不得入组"),
        ("body.p1258", "ICF模板缺项不得入组"),
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
        **_gate_kwargs(config, rows, unit_by_ref),
        hydrated={
            "candidates": _valid_candidates(unit_by_ref) + [
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


@pytest.mark.parametrize(
    ("source_ref", "title"),
    [
        ("body.p1257", "筛选前解释所有研究程序"),
        ("body.p1257", "持续告知缺失不得入组"),
        ("body.p1259", "获得参与者自愿签署的ICF"),
        ("body.p1259", "重要新资料后无需再次同意"),
    ],
)
def test_hydrated_gate_rejects_duplicate_or_ongoing_branch_in_candidate(
    config: dict,
    source_ref: str,
    title: str,
) -> None:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, dispositions = _gate_inputs(config)
    candidates = _valid_candidates(unit_by_ref)
    target = next(
        item
        for item in candidates
        if item["frozen_structure_unit_ids"] == [unit_by_ref[source_ref]]
    )
    target["title"] += f"；{title}"
    issues = evaluate_hydrated_agent_output(
        hydrated={"candidates": candidates, "dispositions": dispositions},
        **_gate_kwargs(config, rows, unit_by_ref),
    )
    assert any(
        issue.code == "COVERED_BRANCH_DUPLICATED"
        and issue.source_refs == (source_ref,)
        for issue in issues
    )


def test_action_detector_preserves_generic_informed_consent_process() -> None:
    from app.protocols.protocol_control_planning import detect_required_action_kinds

    assert {
        "communicate_with_participant",
        "explain_information",
        "witness_consent",
    } <= set(detect_required_action_kinds(EXPECTED_EXCERPTS["body.p1257"]))
    assert {
        "allow_informed_decision_time",
        "obtain_signature",
        "record_signature_date",
        "record_signer_relationship",
    } <= set(detect_required_action_kinds(EXPECTED_EXCERPTS["body.p1259"]))


def test_checklist_records_scope_dedup_and_stop_conditions() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    for phrase in (
        "papl-e17d498106b6f71f440ff2be",
        "pap-b119517783facd407b628e1e",
        "body.p1251",
        "body.p1259",
        "body.p1260",
        "body.p768",
        "研究级伦理治理",
        "ICF 文件治理",
        "知情过程",
        "签署与重新同意控制",
        "required_candidate_source_refs=[body.p1257, body.p1259]",
        "procedure:d001-icf-screening",
        "other_control_candidate",
        "non_enrollment_execution",
        "充分的时间和机会",
        "分别签名并注明日期",
        "公正见证人",
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
