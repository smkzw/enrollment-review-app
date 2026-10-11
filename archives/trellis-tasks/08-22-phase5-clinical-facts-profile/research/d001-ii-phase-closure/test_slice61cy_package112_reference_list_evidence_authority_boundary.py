#!/usr/bin/env python3
"""Model-free Package 112 reference-list / protocol-body authority regressions.

The tests freeze Package 112 ownership for body.p1295-p1306, keep the 38
context units read-only, preserve Package 111/113 boundaries, and prove that
bibliographic citation titles are not inverted into subject thresholds, scale
algorithms, or execution procedures while any real pre-participation control
would still be retained if present in source. Protocol body remains the
execution authority; no new domain disposition enum is introduced.

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
    "representative_group_package112_reference_list_evidence_authority_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cy-package112-reference-list-evidence-authority-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package112-reference-list-evidence-authority-boundary"
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
PACKAGE_ORDINAL = 112
PACKAGE_ID = "pap-fa6b2b871b90b62bbfe81775"
PACKAGE111_ID = "pap-214ce50fd89fb1998521c4c3"
PACKAGE113_ID = "pap-d042355fa4845796808fa256"

OWNED = ["body.p1295", "body.p1296", "body.p1297", "body.p1298", "body.p1299", "body.p1300", "body.p1301", "body.p1302", "body.p1303", "body.p1304", "body.p1305", "body.p1306"]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = ["body.p1295"]
BIBLIOGRAPHIC = [
    ref for ref in OWNED if ref != "body.p1295"
]
EXPECTED_DISPOSITIONS = {
    ref: "non_enrollment_execution" for ref in BIBLIOGRAPHIC
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
    "body.p1295": "参考文献",
    "body.p1296": "中华医学会皮肤性病学分会银屑病专业委员会. 中国银屑病诊疗指南（2023版）[J]. 中华皮肤科杂志, 2023,56(7):573-625.",
    "body.p1297": "黄丹,陈崑.银屑病相关流行病学调查进展[J].诊断学理论与实践,2021,20(01):48-52.",
    "body.p1298": "李慧贤,胡丽,郑焱,等.基于全球疾病负担(GBD)大数据的中国银屑病流行病学负担分析[J].中国皮肤性病学杂志,2021,35(04):386-392.",
    "body.p1299": "Griffiths CEM, Armstrong AW, Gudjonsson JE, et al. Psoriasis. The Lancet. 2021;397:1301–15.",
    "body.p1300": "Armstrong AW, Read C. Pathophysiology, Clinical Presentation, and Treatment of Psoriasis: A Review. JAMA. 2020;323:1945–60.",
    "body.p1301": "Xin P, Xu X, Deng C, et al. The role of JAK/STAT signaling pathway and its inhibitors in diseases. Int Immunopharmacol. 2020 Mar;80:106210.",
    "body.p1302": "Krueger JG, McInnes IB, Blauvelt A. Tyrosine kinase 2 and Janus kinase‒signal transducer and activator of transcription signaling and inhibition in plaque psoriasis. J Am Acad Dermatol. 2022;86:148–57.",
    "body.p1303": "Deucravacitinib. FDA Multi-Discipline Review. 2022.",
    "body.p1304": "Feldman SR, Krueger GG. Psoriasis assessment tools in clinical trials. Ann Rheum Dis. 2005;64 Suppl 2:ii65-8; discussion ii69-73.",
    "body.p1305": "Bożek A, Reich A. The reliability of three psoriasis assessment tools: Psoriasis area and severity index, body surface area and physician global assessment. Adv Clin Exp Med. 2017;26:851–6.",
    "body.p1306": "Thomas CL, Finlay AY. The “handprint” approximates to 1% of the total body surface area whereas the “palm minus the fingers” does not. Br J Dermatol. 2007;157:1080–1."
}
EXPECTED_UNIT_KINDS = {
    "body.p1295": "paragraph",
    "body.p1296": "list_item",
    "body.p1297": "list_item",
    "body.p1298": "list_item",
    "body.p1299": "list_item",
    "body.p1300": "list_item",
    "body.p1301": "list_item",
    "body.p1302": "list_item",
    "body.p1303": "list_item",
    "body.p1304": "list_item",
    "body.p1305": "list_item",
    "body.p1306": "list_item"
}
EXPECTED_SPANS = {
    "body.p1295": ["body.p1295"],
    "body.p1296": ["body.p1296"],
    "body.p1297": ["body.p1297"],
    "body.p1298": ["body.p1298"],
    "body.p1299": ["body.p1299"],
    "body.p1300": ["body.p1300"],
    "body.p1301": ["body.p1301"],
    "body.p1302": ["body.p1302"],
    "body.p1303": ["body.p1303"],
    "body.p1304": ["body.p1304"],
    "body.p1305": ["body.p1305"],
    "body.p1306": ["body.p1306"]
}
SOURCE_ORDERS = [31910, 31920, 31930, 31940, 31950, 31960, 31970, 31980, 31990, 32000, 32010, 32020]
HEADING_PATHS = {
    ref: ["参考文献"] for ref in OWNED
}
EXPECTED_OWNER_MAP = {
    "body.t15.r1": 111,
    "body.p1291": 111,
    "body.p1292": 111,
    "body.p1295": 112,
    "body.p1306": 112,
    "body.p1307": 113,
    "body.p1308": 113,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1295": "reference_list_section_heading_structural_only",
    "body.p1296": "bibliographic_citation_guideline_not_protocol_clause",
    "body.p1297": "bibliographic_citation_epidemiology_not_protocol_clause",
    "body.p1298": "bibliographic_citation_gbd_burden_not_protocol_clause",
    "body.p1299": "bibliographic_citation_lancet_review_not_protocol_clause",
    "body.p1300": "bibliographic_citation_jama_review_not_protocol_clause",
    "body.p1301": "bibliographic_citation_jak_stat_not_protocol_clause",
    "body.p1302": "bibliographic_citation_tyk2_jak_not_protocol_clause",
    "body.p1303": "bibliographic_citation_fda_review_not_protocol_clause",
    "body.p1304": "bibliographic_citation_assessment_tools_not_protocol_clause",
    "body.p1305": "bibliographic_citation_pasi_bsa_pga_not_protocol_clause",
    "body.p1306": "bibliographic_citation_handprint_bsa_not_protocol_clause"
}
EXPECTED_OWNED_SOURCE_SPAN_IDS = sorted(
    {span for spans in EXPECTED_SPANS.values() for span in spans}
)
EXCLUDED_UNOWNED_STRUCTURE_REFS = [
    "body.p1293",
    "body.p1294",
    "body.p1309",
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
        "d001-ii-package112-reference-list-evidence-authority-boundary"
    )
    assert config["task_id"] == "phase5-slice61cy-20260830"
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
            "manifest:slice61cy-package112-reference-list-evidence-authority-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cy-package112-reference-list-evidence-authority-boundary"
        ),
    }


def test_config_preserves_reference_list_vs_protocol_body_authority(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "参考文献题录",
        "非方案执行条款",
        "方案正文仍是执行权威",
        "non_enrollment_execution",
        "不新增领域枚举",
        "PASI",
        "BSA",
        "PGA",
        "handprint",
        "1%",
        "JAK/STAT",
        "TYK2",
        "Deucravacitinib",
        "中国银屑病诊疗指南",
        "Package 111",
        "Package 113",
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

    heading = semantics["body.p1295"]
    assert "章节标题" in heading["exception_rule"]
    assert "参考文献" in heading["preserve_keywords"]

    pasi = semantics["body.p1305"]
    assert "PASI" in pasi["exception_rule"] or "Psoriasis area and severity index" in pasi["base_rule"]
    assert "非方案执行条款" in pasi["exception_rule"] or "不是方案执行条款" in pasi["exception_rule"]
    assert "方案正文仍是执行权威" in pasi["exception_rule"]

    handprint = semantics["body.p1306"]
    assert "handprint" in handprint["exception_rule"] or "handprint" in handprint["base_rule"]
    assert "1%" in handprint["exception_rule"] or "1%" in handprint["base_rule"]
    assert "方案正文仍是执行权威" in handprint["exception_rule"]


def test_source_identity_blocks_citation_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "参考文献标题决定受试者资格",
        "参考文献章节误作入排控制",
    } <= set(forbidden["body.p1295"])
    assert {
        "中国银屑病诊疗指南反向生成诊断标准",
        "指南题录误作入排阈值",
    } <= set(forbidden["body.p1296"])
    assert {
        "JAK/STAT题录反向生成抑制剂算法",
    } <= set(forbidden["body.p1301"])
    assert {
        "Deucravacitinib FDA审评题录误作受试者资格",
    } <= set(forbidden["body.p1303"])
    assert {
        "PASI题录反向生成评分阈值",
        "BSA题录反向生成体表面积阈值",
        "PGA题录反向生成医师总体评估阈值",
    } <= set(forbidden["body.p1305"])
    assert {
        "handprint题录反向生成1%BSA规则",
        "1%体表面积题录误作入排阈值",
    } <= set(forbidden["body.p1306"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "参考文献" in "；".join(checks["body.p1295"])
    assert "非方案执行条款" in "；".join(checks["body.p1296"])
    assert "PASI" in "；".join(checks["body.p1305"]) or "PGA" in "；".join(checks["body.p1305"])
    assert "handprint" in "；".join(checks["body.p1306"]) or "1%" in "；".join(checks["body.p1306"])


def test_phase_applicability_explains_citations_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "参考文献",
        "方案正文仍是执行权威",
        "PASI",
        "不是单例受试者",
        "Package 111",
        "Package 113",
        "p1307",
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


def test_frozen_plan_owns_exact_package112_units(plan: dict, config: dict) -> None:
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
    assert owner_by_ref["body.p1291"] == 111
    assert owner_by_ref["body.p1292"] == 111
    assert owner_by_ref["body.t15.r1"] == 111
    assert owner_by_ref["body.p1307"] == 113
    assert owner_by_ref["body.p1308"] == 113
    assert "body.p1293" not in owner_by_ref
    assert "body.p1294" not in owner_by_ref
    assert "body.p1309" not in owner_by_ref
    assert set(EXCLUDED_UNOWNED_STRUCTURE_REFS).isdisjoint(owner_by_ref)
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_blank_separators_are_explicitly_excluded(
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
    package112 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package112["context_units"]]
    assert len(context_refs) == 38
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1291" not in context_refs
    assert "body.p1292" not in context_refs
    assert "body.p1308" not in context_refs
    assert "body.p1307" in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1291"] == [111]
    assert owners["body.p1295"] == [112]
    assert owners["body.p1306"] == [112]
    assert owners["body.p1307"] == [113]
    assert owners["body.p1308"] == [113]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package112["context_units"]
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


def test_resolver_keeps_package112_owned_roles_only(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    assert [row.source_ref for row in rows] == ORDERED
    assert [row.role for row in rows] == ["owned"] * 12
    assert [row.lookup for row in rows] == ["frozen_plan_owned"] * 12
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
        "body.p1291",
        "body.p1307",
        "body.p1308",
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
    attack["owned_source_refs"] = ["body.p1305"]
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
    assert summary["attached_count"] == 0
    assert summary["unit_count"] == 12
    assert summary["lookup_counts"] == {"frozen_plan_owned": 12}
    assert summary["claims_complete"] is False
    assert summary["group_id"] == config["group_id"]

    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == ["owned"] * 12
    assert [row["lookup"] for row in rows] == ["frozen_plan_owned"] * 12
    assert [row["package_ordinal"] for row in rows] == [PACKAGE_ORDINAL] * 12
    assert [row["package_id"] for row in rows] == [PACKAGE_ID] * 12
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

    assert prompt_meta["owned_count"] == 12
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
        "参考文献",
        "中国银屑病诊疗指南（2023版）",
        "JAK/STAT",
        "Deucravacitinib",
        "Psoriasis area and severity index",
        "handprint",
        "1%",
    ):
        assert marker in prompt
    for ref in (
        "body.p1291",
        "body.p1292",
        "body.t15.r0",
        "body.p1307",
        "body.p1308",
        PACKAGE111_ID,
        PACKAGE113_ID,
    ):
        assert ref not in prompt
    for ref in EXCLUDED_UNOWNED_STRUCTURE_REFS:
        assert f'"source_ref":"{ref}"' not in prompt
    assert "PASI评分阈值" not in prompt
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
        ("body.p1295", "参考文献标题决定受试者资格"),
        ("body.p1295", "参考文献章节误作入排控制"),
        ("body.p1296", "中国银屑病诊疗指南反向生成诊断标准"),
        ("body.p1296", "指南题录误作入排阈值"),
        ("body.p1301", "JAK/STAT题录反向生成抑制剂算法"),
        ("body.p1303", "Deucravacitinib FDA审评题录误作受试者资格"),
        ("body.p1305", "PASI题录反向生成评分阈值"),
        ("body.p1305", "BSA题录反向生成体表面积阈值"),
        ("body.p1305", "PGA题录反向生成医师总体评估阈值"),
        ("body.p1306", "handprint题录反向生成1%BSA规则"),
        ("body.p1306", "1%体表面积题录误作入排阈值"),
        ("body.p1304", "评估工具题录反向生成量表算法")
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
        "pap-fa6b2b871b90b62bbfe81775",
        "body.p1295",
        "body.p1306",
        "body.p1291",
        "body.p1307",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "参考文献题录",
        "非方案执行条款",
        "方案正文仍是执行权威",
        "PASI",
        "handprint",
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
