#!/usr/bin/env python3
"""Model-free Package 110 data publication/commercial-secret regressions.

The tests freeze Package 110 ownership for body.p1281-p1290, keep the 37
context units read-only, preserve Package 109/111 boundaries, and prove that
clinical-study-report recording, sponsor data ownership/disclosure,
public dissemination, multicentre publication preference, centre publication
timing limits, manuscript sponsor review, authorship arrangements, and
commercial-secret/patent cooperation wording are not inverted into subject
eligibility while any real pre-participation control would still be retained
if present in source.

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
    "representative_group_package110_data_publication_commercial_secret_governance_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cw-package110-data-publication-commercial-secret-governance-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package110-data-publication-commercial-secret-governance-boundary"
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
PACKAGE_ORDINAL = 110
PACKAGE_ID = "pap-7358ad349433c3c08aacc5f1"
PACKAGE109_ID = "pap-2101c87c43a5499476169b81"
PACKAGE111_ID = "pap-214ce50fd89fb1998521c4c3"

OWNED = [
    "body.p1281",
    "body.p1282",
    "body.p1283",
    "body.p1284",
    "body.p1285",
    "body.p1286",
    "body.p1287",
    "body.p1288",
    "body.p1289",
    "body.p1290",
]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = [
    "body.p1281",
]
GOVERNANCE = [
    "body.p1282",
    "body.p1283",
    "body.p1284",
    "body.p1285",
    "body.p1286",
    "body.p1287",
    "body.p1288",
    "body.p1289",
    "body.p1290",
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
    "body.p1281": "数据发布和商业秘密的保护",
    "body.p1282": (
        "应按照现行的法规要求将临床研究得出的结果都记录在完整的临床研究报告中。"
    ),
    "body.p1283": (
        "本研究的所有资料，所有权属于申办者，除国家药品监督管理局要求外，未经申办者书面同意，"
        "研究者不得以任何方式提供给第三者。申办者可自由地将研究中收集到的数据用于药品注册、"
        "世界范围内的科学产品记录以及出版物的发表。"
    ),
    "body.p1284": (
        "无论研究结果如何，申办者致力于通过科学大会和同行评审期刊向医疗专业人员和公众公开"
        "研究相关信息。申办者将遵守所有研究结果出版的要求。"
    ),
    "body.p1285": (
        "根据常规编辑和道德规范，申办者通常仅支持基于完整研究的多中心研究结果的发表，而不是"
        "单个中心的数据发表。在这种情况下，经相互同意，将可能指定一名协调研究者。"
    ),
    "body.p1286": (
        "按照惯例，申办者与研究者一致同意，参与本研究的中心在完成本研究、数据解读以及发布"
        "最终报告之前，不得发表、介绍或讨论与本研究得到的数据和/或结果相关的文章。"
    ),
    "body.p1287": (
        "申办者通常不反对研究者公开本研究得出的结果。但是，在公开或提交出版社发表之前，"
        "研究者必须向申办者提供原稿（纸质件或电子档）以供审核（同时附上一封信，在信中要告知"
        "申办者打算公开研究结果这一意愿），之所以采取这一程序是为防止提前泄露商业秘密或其他"
        "受专利保护的材料，而不是将其作为限制公开研究结果或表达研究者观点的措施。申办者审查"
        "完论文原稿后，将向研究者提供所有评论以及申办者关于研究结果发表的意见。"
    ),
    "body.p1288": (
        "申办者有权将本公司对本项目理论或研究工作做出实质性贡献的所有人员加入文章作者之列，"
        "而且还有权决定作者姓名先后顺序。文章发表费用可通过双方签订的书面协议进行规定。"
    ),
    "body.p1289": (
        "如果研究结果（部分或全部）文章是由申办者撰写的，则会以书面形式询问研究者是否同意"
        "将其列为文章作者之一，研究者在合理时限[例如30个日历日]内将书面形式的答复发送到申办者。"
    ),
    "body.p1290": (
        "任何出版物或手稿均不得包含申办者的任何商业秘密信息或申办者的任何专有或机密信息，"
        "且仅限于新发现和科学事实解释。如果申办者认为任何提交审查的出版物或手稿中包含可申请"
        "专利的主题，则申办者应立即向研究者确定该主题。如果申办者要求且申办者承担费用，研究者"
        "应尽最大努力协助申办者在任何发表前向专利和商标机构或通过专利合作条约提交涵盖此类主题"
        "的专利申请。"
    ),
}
SOURCE_ORDERS = [
    31440,
    31450,
    31460,
    31470,
    31480,
    31490,
    31500,
    31510,
    31520,
    31530,
]
HEADING_PATHS = {
    ref: ["研究文件、监查和管理", "数据发布和商业秘密的保护"] for ref in OWNED
}
EXPECTED_OWNER_MAP = {
    "body.p1280": 109,
    "body.p1281": 110,
    "body.p1282": 110,
    "body.p1283": 110,
    "body.p1284": 110,
    "body.p1285": 110,
    "body.p1286": 110,
    "body.p1287": 110,
    "body.p1288": 110,
    "body.p1289": 110,
    "body.p1290": 110,
    "body.p1291": 111,
    "body.p515": 45,
    "body.p575": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1281": "data_publication_commercial_secret_subsection_heading",
    "body.p1282": "complete_clinical_study_report_recording_governance",
    "body.p1283": (
        "sponsor_data_ownership_third_party_disclosure_restriction_and_registration_use_governance"
    ),
    "body.p1284": "study_result_public_dissemination_and_publication_requirement_governance",
    "body.p1285": "multicentre_publication_preference_and_coordinating_investigator_governance",
    "body.p1286": "participating_centre_pre_final_report_publication_restriction_governance",
    "body.p1287": (
        "investigator_manuscript_sponsor_review_for_commercial_secret_patent_governance"
    ),
    "body.p1288": "authorship_order_and_publication_cost_arrangement_governance",
    "body.p1289": "sponsor_written_publication_authorship_invitation_response_governance",
    "body.p1290": (
        "publication_confidential_info_exclusion_and_pre_publication_patent_cooperation_governance"
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


def test_config_contract_keeps_publication_governance_out_of_subject_candidates(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package110-data-publication-commercial-secret-governance-boundary"
    )
    assert config["task_id"] == "phase5-slice61cw-20260830"
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
            "manifest:slice61cw-package110-data-publication-commercial-secret-governance-boundary"
        ),
        "catalog_id": (
            "catalog:slice61cw-package110-data-publication-commercial-secret-governance-boundary"
        ),
    }


def test_config_preserves_two_layer_publication_governance_semantics(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "完整的临床研究报告",
        "所有权属于申办者",
        "国家药品监督管理局",
        "无论研究结果如何",
        "多中心研究结果的发表",
        "发布最终报告之前",
        "提供原稿",
        "商业秘密",
        "作者姓名先后顺序",
        "30个日历日",
        "专利合作条约",
        "Package 109",
        "Package 111",
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

    p1286 = semantics["body.p1286"]
    assert "出版治理" in p1286["exception_rule"]
    assert "参加研究前" in p1286["exception_rule"]
    assert "发布最终报告之前" in p1286["preserve_keywords"]

    p1287 = semantics["body.p1287"]
    assert "原稿审核" in p1287["exception_rule"]
    assert "商业秘密" in "；".join(p1287["preserve_keywords"])
    assert "不是单例入排资格" in p1287["exception_rule"]

    p1290 = semantics["body.p1290"]
    assert "专利合作" in p1290["exception_rule"]
    assert "参加研究前控制" in p1290["exception_rule"]
    assert "专利合作条约" in p1290["preserve_keywords"]


def test_source_identity_blocks_eligibility_inversion(config: dict) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(FORBIDDEN_CANDIDATES)
    for ref in FORBIDDEN_CANDIDATES:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert {
        "数据发布标题决定受试者资格",
        "商业秘密标题决定入排控制",
    } <= set(forbidden["body.p1281"])
    assert {
        "临床研究报告决定单例资格",
        "研究结果未记入CSR不得入组",
    } <= set(forbidden["body.p1282"])
    assert {
        "数据归属决定单例资格",
        "资料所有权误作受试者资格",
    } <= set(forbidden["body.p1283"])
    assert {
        "研究结果公开决定单例资格",
        "出版要求误作入排控制",
    } <= set(forbidden["body.p1284"])
    assert {
        "多中心发表偏好决定单例资格",
        "单中心数据发表限制误作入排排除",
    } <= set(forbidden["body.p1285"])
    assert {
        "中心发表限制决定单例资格",
        "最终报告前发表限制误作入排排除",
        "研究者发表禁令倒置为参加研究前控制",
    } <= set(forbidden["body.p1286"])
    assert {
        "原稿审核决定单例资格",
        "未提交原稿不得入组",
        "商业秘密审核误作入排控制",
    } <= set(forbidden["body.p1287"])
    assert {
        "作者署名决定单例资格",
        "发表费用安排误作入排控制",
    } <= set(forbidden["body.p1288"])
    assert {
        "作者邀请答复决定单例资格",
        "30日未答复不得入组",
    } <= set(forbidden["body.p1289"])
    assert {
        "商业秘密排除决定单例资格",
        "专利申请协助缺失不得入组",
        "发表前专利合作倒置为参加研究前控制",
    } <= set(forbidden["body.p1290"])

    checks = config["clinical_qc_checks_by_source_ref"]
    assert "临床研究报告" in "；".join(checks["body.p1282"])
    assert "所有权属于申办者" in "；".join(checks["body.p1283"])
    assert "无论研究结果如何" in "；".join(checks["body.p1284"])
    assert "多中心" in "；".join(checks["body.p1285"])
    assert "最终报告之前" in "；".join(checks["body.p1286"])
    assert "原稿" in "；".join(checks["body.p1287"])
    assert "作者" in "；".join(checks["body.p1288"])
    assert "30个日历日" in "；".join(checks["body.p1289"])
    assert "专利申请" in "；".join(checks["body.p1290"])


def test_phase_applicability_explains_governance_not_subject_scope(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "数据发布和商业秘密的保护",
        "临床研究报告",
        "原稿审核",
        "专利合作",
        "不是单例受试者",
        "Package 109",
        "Package 111",
        "p1280",
        "p1291",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得以other_control_candidate强挂" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_frozen_plan_owns_exact_package110_units(plan: dict, config: dict) -> None:
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
    assert owner_by_ref["body.p1280"] == 109
    assert owner_by_ref["body.p1291"] == 111
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_context_units_remain_read_only_and_unowned_partition(
    plan: dict,
    config: dict,
) -> None:
    package110 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package110["context_units"]]
    assert len(context_refs) == 37
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1280" not in context_refs
    assert "body.p1291" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1280"] == [109]
    assert owners["body.p1281"] == [110]
    assert owners["body.p1290"] == [110]
    assert owners["body.p1291"] == [111]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package110["context_units"]
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


def test_resolver_keeps_package110_owned_roles_only(config: dict) -> None:
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
        "body.p1280",
        "body.p1291",
        "body.p1270",
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
    attack["owned_source_refs"] = ["body.p1287"]
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
        "完整的临床研究报告",
        "所有权属于申办者",
        "国家药品监督管理局",
        "无论研究结果如何",
        "多中心研究结果的发表",
        "发布最终报告之前",
        "提供原稿",
        "商业秘密或其他受专利保护的材料",
        "作者姓名先后顺序",
        "30个日历日",
        "专利合作条约",
    ):
        assert marker in prompt
    for ref in (
        "body.p1270",
        "body.p1280",
        "body.p1291",
        "body.p1292",
        PACKAGE109_ID,
        PACKAGE111_ID,
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
        ("body.p1281", "数据发布标题决定受试者资格"),
        ("body.p1282", "临床研究报告决定单例资格"),
        ("body.p1283", "数据归属决定单例资格"),
        ("body.p1283", "资料所有权误作受试者资格"),
        ("body.p1284", "研究结果公开决定单例资格"),
        ("body.p1285", "多中心发表偏好决定单例资格"),
        ("body.p1286", "中心发表限制决定单例资格"),
        ("body.p1286", "最终报告前发表限制误作入排排除"),
        ("body.p1286", "研究者发表禁令倒置为参加研究前控制"),
        ("body.p1287", "原稿审核决定单例资格"),
        ("body.p1287", "未提交原稿不得入组"),
        ("body.p1287", "商业秘密审核误作入排控制"),
        ("body.p1288", "作者署名决定单例资格"),
        ("body.p1289", "作者邀请答复决定单例资格"),
        ("body.p1289", "30日未答复不得入组"),
        ("body.p1290", "商业秘密排除决定单例资格"),
        ("body.p1290", "专利申请协助缺失不得入组"),
        ("body.p1290", "发表前专利合作倒置为参加研究前控制"),
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
        "pap-7358ad349433c3c08aacc5f1",
        "body.p1281",
        "body.p1283",
        "body.p1286",
        "body.p1287",
        "body.p1290",
        "body.p1280",
        "body.p1291",
        "required_candidate_source_refs=[]",
        "non_enrollment_execution",
        "完整的临床研究报告",
        "发布最终报告之前",
        "原稿",
        "商业秘密",
        "专利",
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
