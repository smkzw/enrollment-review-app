#!/usr/bin/env python3
"""Model-free Package 115 contraception method authority boundary regressions.

Locks appendix ownership body.p1322-p1333, the menopause clinical diagnosis
definition, the screening-negative vs ICF-date time anchors, high-efficiency
method OR choices (p1328/p1329/p1330), condom mutual exclusion and
recommendation modality (p1332), unacceptable-method isolation (p1333),
abstinence reliability assessment (p1331), anti-duplication of the accepted
slice60m p1325/p1326 controls and of IN-06, plus Package114/116 isolation.
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
    "representative_group_package115_contraception_method_authority_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61db-package115-contraception-method-authority-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package115-contraception-method-authority-boundary"
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
PACKAGE_ORDINAL = 115
PACKAGE_ID = "pap-9fb70d121e089bc533c21255"
PACKAGE114_ID = "pap-cd76207b0f3d157c2eaa66d6"
PACKAGE116_ID = "pap-1a482edf71b15f7aba00234a"

OWNED = [f"body.p{i}" for i in range(1322, 1334)]
ATTACHED: list[str] = []
ORDERED = list(OWNED)
FORBIDDEN_CANDIDATES = list(OWNED)
STRUCTURAL_ONLY = ["body.p1323"]
SUPPORTING_REFS = [ref for ref in OWNED if ref not in STRUCTURAL_ONLY]
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
    "body.p1322": "女性连续停经12个月，并排除妊娠及其他可能导致闭经的医疗原因后，即可临床诊断为绝经。",
    "body.p1323": "2.有生育能力女性参与者的避孕规定与方法",
    "body.p1324": "在筛选时血妊娠试验阴性后，必须开始采取适当的避孕措施。",
    "body.p1325": "从签署知情同意书之日开始至研究药物末次给药后3个月为止，期间参与者必须同意持续和正确地使用一种高效或可接受的避孕方法进行避孕（禁止使用激素类避孕）。研究者或指定人员应与参与者讨论，确认参与者已从允许的避孕方法中选择了最适合其避孕的方法（下述），并确认参与者已知晓研究期间需持续并正确地使用该方法。",
    "body.p1326": "在研究流程中计划的访视点，研究者或指定人员将告知参与者需要持续使用高效或可接受的避孕方法，并在参与者病历中记录与之的对话和参与者的同意（参与者需要确认她同意将持续并正确使用至少1种选定的避孕方法）。此外，还应告知参与者，如果她已停用所选的避孕方法，或，已知或怀疑怀孕，需立即打电话给研究者或指定人员。",
    "body.p1327": "高效的避孕方法是指持续和正确地使用时，年失败率低于1%的避孕方法。包括：",
    "body.p1328": "正确放置含铜的宫内节育器（Intrauterine-device，IUD）",
    "body.p1329": "男性伴侣绝育",
    "body.p1330": "双侧输卵管结扎/双侧输卵管切除术/双侧输卵管闭塞术",
    "body.p1331": "禁欲。禁欲定义为完全和持续地避免所有的异性性交。禁欲的可靠性需要根据研究的持续时间以及参与者的首选和平常的生活方式进行评估",
    "body.p1332": "可接受的避孕方法：含杀精剂的男用避孕套或女用避孕套。男用避孕套和女用避孕套不能同时使用（存在因摩擦失效的风险）。采用可接受的避孕方法时，建议参与者在末次给药结束后每隔一个月经周期进行妊娠检查。对于月经延迟者，强烈建议进行妊娠检查以确认是否怀孕，此建议也适用于月经周期较长或不规律的参与者。",
    "body.p1333": "不可接受的避孕方法：评价参与者的避孕首选，以及跟日常生活方式相关的禁欲的可靠性。定期禁欲（如推算日历法、排卵期法、症状体温避孕法或排卵后安全期避孕法）、男性或女性用避孕套（无杀精剂）、杀精海绵等，以及性交中断（或体外射精）都是本研究不可接受的避孕方法。",
}
EXPECTED_UNIT_KINDS = {
    "body.p1322": "list_item",
    "body.p1323": "paragraph",
    "body.p1324": "paragraph",
    "body.p1325": "paragraph",
    "body.p1326": "paragraph",
    "body.p1327": "paragraph",
    "body.p1328": "list_item",
    "body.p1329": "list_item",
    "body.p1330": "list_item",
    "body.p1331": "list_item",
    "body.p1332": "paragraph",
    "body.p1333": "paragraph",
}
EXPECTED_SPANS = {ref: [ref] for ref in ORDERED}
SOURCE_ORDERS = list(range(32180, 32300, 10))
HEADING_PATHS = {ref: ["附录"] for ref in ORDERED}
EXPECTED_OWNER_MAP = {
    "body.p1307": 113,
    "body.p1308": 113,
    "body.p1321": 114,
    **{ref: 115 for ref in OWNED},
    "body.p1334": 116,
    "body.p1335": 116,
    "body.p515": 45,
    "body.p516": 45,
    "body.p567": 45,
    "body.p575": 46,
    "body.p581": 46,
    "body.p583": 46,
    "body.p584": 47,
    "body.p594": 48,
    "body.p618": 50,
    "body.p623": 50,
    "body.p838": 75,
}
SEMANTIC_ROLES = {
    "body.p1322": "menopause_clinical_diagnosis_definition",
    "body.p1323": "appendix_contraception_section_heading_2",
    "body.p1324": "screening_negative_contraception_start_trigger",
    "body.p1325": "icf_start_duration_prohibition_discussion_increments",
    "body.p1326": "planned_visit_counselling_record_conditional_contact_increments",
    "body.p1327": "high_efficiency_method_definition",
    "body.p1328": "high_efficiency_method_or_branch_copper_iud",
    "body.p1329": "high_efficiency_method_or_branch_male_sterilization",
    "body.p1330": "high_efficiency_method_or_branch_bilateral_tubal",
    "body.p1331": "abstinence_definition_and_reliability_professional_assessment",
    "body.p1332": "acceptable_methods_condoms_or_exclusive_and_pregnancy_check_recommendation",
    "body.p1333": "unacceptable_methods_list",
}
EXPECTED_OWNED_SOURCE_SPAN_IDS = sorted(
    {span for ref in OWNED for span in EXPECTED_SPANS[ref]}
)
PACKAGE114_REFS = [f"body.p{i}" for i in range(1310, 1322)]
PACKAGE116_REFS = [
    f"body.p{i}" for i in list(range(1334, 1342)) + list(range(1343, 1347))
]
HIGH_EFFICIENCY_OR_CHILDREN = ["body.p1328", "body.p1329", "body.p1330"]


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


def test_config_contract_keeps_package115_owned_and_forbidden_boundary(
    config: dict,
) -> None:
    assert config["schema_version"] == (
        "phase5/representative-group-control-replay-config/v1"
    )
    assert config["group_id"] == (
        "d001-ii-package115-contraception-method-authority-boundary"
    )
    assert config["task_id"] == "phase5-slice61db-20260830"
    assert config["worker"] == "worker_02"
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
    assert config["expected_disposition_by_source_ref"] == {
        ref: "supporting_or_supplement" for ref in SUPPORTING_REFS
    }
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
            "manifest:slice61db-package115-contraception-method-authority-boundary"
        ),
        "catalog_id": (
            "catalog:slice61db-package115-contraception-method-authority-boundary"
        ),
    }


def test_config_preserves_anchors_methods_modality_and_duplication_boundary(
    config: dict,
) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "连续停经12个月",
        "排除妊娠",
        "可能导致闭经的医疗原因",
        "筛选时血妊娠试验阴性",
        "签署知情同意书之日开始",
        "末次给药后3个月",
        "禁止使用激素类避孕",
        "并列OR",
        "不能同时使用",
        "建议",
        "强烈建议",
        "可靠性",
        "研究的持续时间",
        "首选和平常的生活方式",
        "双侧",
        "年失败率低于1%",
        "Package114",
        "Package116",
        "body.p1334",
        "slice60m",
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

    high = semantics["body.p1327"]["logic_tree"]
    assert high["operator"] == "OR"
    assert high["children"] == HIGH_EFFICIENCY_OR_CHILDREN
    condom = semantics["body.p1332"]["logic_tree"]
    assert condom["operator"] == "OR"
    assert condom["children_choices"] == ["含杀精剂的男用避孕套", "女用避孕套"]
    assert "不能同时使用" in condom["mutual_exclusion"]
    assert "双侧" in semantics["body.p1330"]["base_rule"]
    assert "小节标题" in semantics["body.p1323"]["exception_rule"]
    assert "body.p1334" in config["later_package_boundary"]["note"]
    assert config["later_package_boundary"]["forbidden_next_package_refs"] == (
        PACKAGE116_REFS
    )


def test_source_identity_blocks_anchor_method_modality_attacks(
    config: dict,
) -> None:
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    assert set(forbidden) == set(OWNED)
    for ref in OWNED:
        assert set(BASE_FORBIDDEN_MARKERS) <= set(forbidden[ref])

    assert "筛选阴性锚点与ICF锚点混淆" in forbidden["body.p1324"]
    assert "必须开始改为建议" in forbidden["body.p1324"]
    assert "高效方法列表压平为AND" in forbidden["body.p1327"]
    assert "高效方法OR分支压平为AND" in forbidden["body.p1328"]
    assert "双侧条件丢失" in forbidden["body.p1330"]
    assert "定期禁欲或性交中断视为与持续禁欲等效" in forbidden["body.p1331"]
    assert "禁欲可靠性评估丢失" in forbidden["body.p1331"]
    assert "男用避孕套和女用避孕套可同时使用" in forbidden["body.p1332"]
    assert "建议改为必须" in forbidden["body.p1332"]
    assert "妊娠检查升级为必做程序" in forbidden["body.p1332"]
    assert "不可接受方法误作可接受方法" in forbidden["body.p1333"]
    assert "持续和正确地使用一种高效或可接受的避孕方法" in forbidden["body.p1325"]
    assert "禁止使用激素类避孕增量重复发布" in forbidden["body.p1325"]
    assert "计划访视量词压缩为单一筛选节点" in forbidden["body.p1326"]
    assert "未来条件伪造成当前触发" in forbidden["body.p1326"]


def test_phase_applicability_explains_support_and_no_publication(
    config: dict,
) -> None:
    rationale = config["phase_applicability"]["rationale"]
    for phrase in (
        "有生育能力女性参与者的避孕规定与方法",
        "筛选时血妊娠试验阴性",
        "知情同意书日期起点",
        "slice60m",
        "末次给药后至少3个月",
        "Package116",
        "不是新的独立筛选",
        "claims_complete=false",
    ):
        assert phrase in rationale

    batch_reason = config["batching"]["reason"]
    assert "required candidates为空" in batch_reason
    assert "不得重复发布" in batch_reason
    assert "不得压平为AND" in batch_reason
    assert "不得混淆" in batch_reason
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )
    assert config["later_package_boundary"]["excluded_unowned_structure_refs"] == []
    assert config["later_package_boundary"]["forbidden_next_package_refs"] == (
        PACKAGE116_REFS
    )


def test_frozen_plan_owns_exact_package115_units(plan: dict, config: dict) -> None:
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
    assert len(package["context_units"]) == 39

    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    assert all(owner_by_ref[ref] == PACKAGE_ORDINAL for ref in OWNED)
    assert owner_by_ref["body.p1321"] == 114
    assert owner_by_ref["body.p1334"] == 116
    assert config["later_package_boundary"]["expected_owners_by_span"] == (
        EXPECTED_OWNER_MAP
    )


def test_package114_and_package116_stay_outside_owned_inputs(
    plan: dict,
    config: dict,
) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package.get("owned_units") or []
    }
    package114 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == 114
    )
    package116 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == 116
    )
    assert package114["package_id"] == PACKAGE114_ID
    assert package116["package_id"] == PACKAGE116_ID
    package114_refs = {unit["source_ref"] for unit in package114["owned_units"]}
    package116_refs = {unit["source_ref"] for unit in package116["owned_units"]}
    assert package114_refs == set(PACKAGE114_REFS)
    assert package116_refs == set(PACKAGE116_REFS)

    package115_inputs = set(config["owned_source_refs"])
    package115_inputs.update(config["attached_source_refs"])
    assert package114_refs.isdisjoint(package115_inputs)
    assert package116_refs.isdisjoint(package115_inputs)
    assert set(FORBIDDEN_CANDIDATES) <= set(OWNED)
    assert set(PACKAGE116_REFS).isdisjoint(config["forbidden_candidate_source_refs"])
    assert owner_by_ref["body.p1321"] == 114
    assert owner_by_ref["body.p1334"] == 116


def test_package116_context_only_p1334_never_absorbed(
    plan: dict,
    config: dict,
) -> None:
    package115 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package115["context_units"]]
    assert "body.p1334" in context_refs
    assert "body.p1334" not in config["owned_source_refs"]
    assert "body.p1334" not in config["attached_source_refs"]
    assert "body.p1334" not in config["forbidden_candidate_source_refs"]
    assert "body.p1334" not in config["required_candidate_source_refs"]
    assert "body.p1334" not in config["structural_only_source_refs"]
    assert "body.p1334" not in (
        config["candidate_forbidden_markers_by_source_ref"]
    )
    assert "body.p1334" not in (
        config["candidate_required_markers_by_source_ref"]
    )
    assert "body.p1334" not in config["exception_semantics_by_source_ref"]
    assert config["later_package_boundary"]["read_only"] is True


def test_context_units_remain_read_only_and_unowned_partition(
    plan: dict,
    config: dict,
) -> None:
    package115 = next(
        package
        for package in plan["packages"]
        if package["package_ordinal"] == PACKAGE_ORDINAL
    )
    context_refs = [unit["source_ref"] for unit in package115["context_units"]]
    assert len(context_refs) == 39
    assert set(context_refs).isdisjoint(config["owned_source_refs"])
    assert set(context_refs).isdisjoint(config["attached_source_refs"])
    assert "body.p1321" in context_refs
    assert "body.p1334" in context_refs
    assert "body.p1323" not in context_refs

    owners: dict[str, list[int]] = {}
    for candidate_package in plan["packages"]:
        for unit in candidate_package.get("owned_units") or []:
            owners.setdefault(unit["source_ref"], []).append(
                candidate_package["package_ordinal"]
            )
    assert owners["body.p1321"] == [114]
    assert owners["body.p1322"] == [115]
    assert owners["body.p1333"] == [115]
    assert owners["body.p1334"] == [116]
    assert owners["body.p515"] == [45]
    assert owners["body.p575"] == [46]
    assert owners["body.p584"] == [47]
    assert owners["body.p594"] == [48]
    assert owners["body.p618"] == [50]
    assert owners["body.p838"] == [75]

    expected_unowned_context_refs = [
        unit["source_ref"]
        for unit in package115["context_units"]
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


def test_resolver_keeps_package115_owned_roles(config: dict) -> None:
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
        "body.p1321",
        "body.p1334",
        "body.p1335",
        "body.p1346",
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
    attack["owned_source_refs"] = ["body.p1322"]
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

    owned_ids = [row["structure_unit_id"] for row in rows if row["role"] == "owned"]
    structural_ids = [
        row["structure_unit_id"]
        for row in rows
        if row["source_ref"] in STRUCTURAL_ONLY
    ]
    assert batch["owned_structure_unit_ids"] == owned_ids
    assert batch["context_structure_unit_ids"] == []
    assert batch["owned_source_span_ids"] == EXPECTED_OWNED_SOURCE_SPAN_IDS
    assert batch["context_source_span_ids"] == []
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
        "连续停经12个月",
        "筛选时血妊娠试验阴性",
        "签署知情同意书之日开始",
        "末次给药后3个月",
        "禁止使用激素类避孕",
        "年失败率低于1%",
        "双侧输卵管结扎",
        "完全和持续地避免所有的异性性交",
        "含杀精剂的男用避孕套",
        "不能同时使用",
        "每隔一个月经周期",
        "强烈建议",
        "定期禁欲",
        "体外射精",
    ):
        assert marker in prompt
    for ref in (
        "body.p1321",
        "body.p1334",
        "body.p1335",
        "body.p1346",
        PACKAGE114_ID,
        PACKAGE116_ID,
    ):
        assert ref not in prompt


def _candidate(
    unit_id: str,
    title: str,
    statements: list[str],
    study_phase: str = "phase_ii",
) -> dict:
    return {
        "control_candidate_id": f"cand-{unit_id}-{abs(hash(title)) % 100000}",
        "title": title,
        "study_phase": study_phase,
        "frozen_structure_unit_ids": [unit_id],
        "source_span_ids": [],
        "semantics": {
            "obligation_expression": {
                "groups": [
                    {
                        "atoms": [
                            {
                                "kind": "reach_condition",
                                "statement": statement,
                                "source_span_ids": ["span-attack"],
                            }
                            for statement in statements
                        ]
                    }
                ]
            }
        },
    }


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
    return rows, unit_by_ref, []


def _evaluate(config: dict, candidates: list[dict]) -> list[object]:
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows, unit_by_ref, _ = _gate_inputs(config)
    return evaluate_hydrated_agent_output(
        group_id=config["group_id"],
        study_phase=config["study_phase"],
        rows=rows,
        hydrated={"candidates": candidates, "dispositions": []},
        allowed_structure_unit_ids=[unit_by_ref[ref] for ref in OWNED],
        required_candidate_source_refs=[],
        forbidden_candidate_source_refs=FORBIDDEN_CANDIDATES,
        expected_disposition_by_source_ref={},
        expected_workflow_stage_ids_by_source_ref={},
        candidate_forbidden_markers_by_source_ref=config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        candidate_required_markers_by_source_ref=config[
            "candidate_required_markers_by_source_ref"
        ],
    )


def test_deterministic_gate_accepts_clean_hydrated(config: dict) -> None:
    issues = _evaluate(config, candidates=[])
    assert issues == []


@pytest.mark.parametrize("source_ref", OWNED)
def test_hydrated_gate_rejects_duplicate_candidate_for_disposed_source(
    config: dict,
    source_ref: str,
) -> None:
    _, unit_by_ref, _ = _gate_inputs(config)
    issues = _evaluate(
        config,
        candidates=[
            _candidate(
                unit_by_ref[source_ref],
                f"{source_ref} 增量重复发布",
                ["禁止使用激素类避孕增量重复发布"],
            )
        ],
    )
    assert issues
    assert any(
        issue.code in {"CONTROL_DUPLICATE_RETAINED", "COVERED_BRANCH_DUPLICATED"}
        for issue in issues
    )


@pytest.mark.parametrize(
    ("source_ref", "marker"),
    [
        ("body.p1324", "筛选阴性锚点与ICF锚点混淆"),
        ("body.p1324", "必须开始改为建议"),
        ("body.p1327", "高效方法列表压平为AND"),
        ("body.p1328", "高效方法OR分支压平为AND"),
        ("body.p1330", "双侧条件丢失"),
        ("body.p1331", "定期禁欲或性交中断视为与持续禁欲等效"),
        ("body.p1331", "禁欲可靠性评估丢失"),
        ("body.p1332", "男用避孕套和女用避孕套可同时使用"),
        ("body.p1332", "建议改为必须"),
        ("body.p1332", "妊娠检查升级为必做程序"),
        ("body.p1333", "不可接受方法误作可接受方法"),
        ("body.p1325", "持续和正确地使用一种高效或可接受的避孕方法"),
        ("body.p1326", "计划访视量词压缩为单一筛选节点"),
    ],
)
def test_hydrated_gate_rejects_forbidden_marker_attacks(
    config: dict,
    source_ref: str,
    marker: str,
) -> None:
    _, unit_by_ref, _ = _gate_inputs(config)
    issues = _evaluate(
        config,
        candidates=[
            _candidate(unit_by_ref[source_ref], f"{source_ref} 攻击候选", [marker])
        ],
    )
    assert issues
    assert any(
        issue.code in {"COVERED_BRANCH_DUPLICATED", "CONTROL_DUPLICATE_RETAINED"}
        or source_ref in issue.source_refs
        for issue in issues
    )


def test_hydrated_gate_rejects_scope_creep_to_package116(
    config: dict,
    plan: dict,
) -> None:
    package116 = next(
        package for package in plan["packages"] if package["package_ordinal"] == 116
    )
    p1334 = next(
        unit for unit in package116["owned_units"] if unit["source_ref"] == "body.p1334"
    )
    issues = _evaluate(
        config,
        candidates=[
            _candidate(p1334["structure_unit_id"], "吸收Package116", ["病史月经史询问"])
        ],
    )
    assert issues
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


def test_hydrated_gate_rejects_phase_mismatch(config: dict) -> None:
    _, unit_by_ref, _ = _gate_inputs(config)
    issues = _evaluate(
        config,
        candidates=[
            _candidate(
                unit_by_ref["body.p1322"],
                "phase_iii 候选",
                ["连续停经12个月"],
                study_phase="phase_iii",
            )
        ],
    )
    assert issues
    assert any(issue.code == "PHASE_MISMATCH" for issue in issues)
