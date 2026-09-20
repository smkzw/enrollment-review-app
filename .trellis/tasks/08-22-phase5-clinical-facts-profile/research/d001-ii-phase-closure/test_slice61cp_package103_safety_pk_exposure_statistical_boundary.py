#!/usr/bin/env python3
"""Package 103 model-free safety, PK, PopPK, and exposure-effect regressions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package103_safety_pk_exposure_statistical_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cp-package103-safety-pk-exposure-statistical-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package103-safety-pk-exposure-statistical-boundary"
)
ARTIFACT_DIR = ROOT / "artifacts" / (
    "phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830"
)
PLAN_PATH = ARTIFACT_DIR / "frozen_phase_plan.json"
COVERAGE_PATH = ARTIFACT_DIR / "coverage_manifest.json"
STRUCTURE_PATH = ARTIFACT_DIR / "structure" / "blobs" / "protocol_blocks" / (
    "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json"
)

PLAN_ID = "papl-e17d498106b6f71f440ff2be"
PACKAGE_ID = "pap-e965d4d93dad672cc906240d"
OWNED = [
    "body.p1224",
    *[f"body.p{n}" for n in range(1226, 1236)],
]
ATTACHED = ["body.p1225"]
ORDERED = ["body.p1224", "body.p1225", *[f"body.p{n}" for n in range(1226, 1236)]]
STRUCTURAL = ["body.p1224", "body.p1230", "body.p1232", "body.p1234"]
SEMANTIC = [
    "body.p1226",
    "body.p1227",
    "body.p1228",
    "body.p1229",
    "body.p1231",
    "body.p1233",
    "body.p1235",
]
PHASE_III = ["body.p1225"]
EXCLUDED_NEIGHBORS = [
    *[f"body.p{n}" for n in range(1197, 1224)],
    "body.p1236",
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-100-160",
    "body.p1237#atom-160-208",
]
PACKAGE104_OWNED = [
    "body.p1236",
    "body.p1237#atom-0-15",
    "body.p1237#atom-15-100",
    "body.p1237#atom-160-208",
]
PACKAGE102_OWNED = [
    "body.p1197",
    *[f"body.p{n}" for n in range(1200, 1206)],
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
def manifest() -> dict:
    return _load(COVERAGE_PATH)


def test_config_freezes_minimal_zero_candidate_closure(config: dict) -> None:
    assert config["worker"] == "codex-parent"
    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == []
    assert config["forbidden_candidate_source_refs"] == ORDERED
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL
    assert config["attached_structural_only_source_refs"] == []
    assert config["expected_disposition_by_source_ref"] == {
        ref: "administrative_statistical_background" for ref in SEMANTIC
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert set(config["candidate_forbidden_markers_by_source_ref"]) == set(ORDERED)
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["phase_applicability"]["scope"] == "phase_ii"
    boundary = config["later_package_boundary"]
    assert boundary["expected_owners_by_span"] == {
        "body.p1197": 102,
        "body.p1209": 102,
        "body.p1224": 103,
        "body.p1235": 103,
        **{ref: 104 for ref in PACKAGE104_OWNED},
    }
    assert boundary["unowned_context_source_refs"] == [
        "body.p1237#atom-100-160"
    ]
    assert config["notes"][-1].startswith("claims_complete=false")


def test_frozen_plan_owns_exact_package103_units(plan: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    package = next(p for p in plan["packages"] if p["package_ordinal"] == 103)
    assert package["package_id"] == PACKAGE_ID
    assert package["selected_phase"] == "phase_ii"
    assert [u["source_ref"] for u in package["owned_units"]] == OWNED
    context = {u["source_ref"] for u in package["context_units"]}
    assert set(ATTACHED) <= context
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert all(owner_by_ref[ref] == 103 for ref in OWNED)
    assert all(ref not in owner_by_ref for ref in ATTACHED)
    assert not (set(EXCLUDED_NEIGHBORS) & set(OWNED))


def test_phase_graph_keeps_phase_iii_safety_context_separate(
    manifest: dict, plan: dict
) -> None:
    units = {u["source_ref"]: u for u in manifest["units"]}
    assert units["body.p1225"]["phase_scopes"] == ["phase_iii"]
    for ref in OWNED:
        assert units[ref]["phase_scopes"] == ["unknown"]
    package103 = next(p for p in plan["packages"] if p["package_ordinal"] == 103)
    target_refs = {unit["source_ref"] for unit in package103["owned_units"]}
    assert not (set(PHASE_III) & target_refs)
    assert set(ATTACHED) <= {
        unit["source_ref"] for unit in package103["context_units"]
    }


def test_source_excerpts_preserve_safety_pk_statistical_meaning(
    manifest: dict,
) -> None:
    units = {u["source_ref"]: u["excerpt"] for u in manifest["units"]}
    assert units["body.p1224"] == "安全性分析"
    for marker in (
        "Ⅲ期临床阶段",
        "MedDRA",
        "SOC",
        "PT",
        "TEAE",
        "治疗前",
        "严重不良事件",
        "死亡事件",
    ):
        assert marker in units["body.p1225"]
    for marker in ("血常规", "血生化", "生命体征", "治疗后异常", "交叉表", "例数和百分比"):
        assert marker in units["body.p1226"]
    for marker in ("体格检查", "列表", "交叉表", "例数和百分比", "异常结果"):
        assert marker in units["body.p1227"]
    assert units["body.p1228"] == "列出所有具有生育能力的女性的血妊娠检查结果。"
    for marker in ("合并用药", "汇总", "列表"):
        assert marker in units["body.p1229"]
    assert units["body.p1230"] == "药代动力学分析"
    for marker in (
        "PKCS",
        "计划PK采样时间",
        "实际PK采样时间",
        "CMS-D001",
        "C_trough",
        "C_max",
        "描述性统计",
        "浓度-时间曲线图",
    ):
        assert marker in units["body.p1231"]
    assert units["body.p1232"] == "群体药代动力学分析"
    for marker in (
        "前期已完成研究",
        "血药浓度数据",
        "数据合并",
        "PopPK分析",
        "NONMEM",
        "定量药理分析计划及报告",
    ):
        assert marker in units["body.p1233"]

    assert units["body.p1234"] == "暴露-效应分析"
    for marker in (
        "如数据允许",
        "最终PopPK模型参数估计值",
        "个体暴露参数",
        "暴露/疗效",
        "暴露/安全性",
        "相关性探索",
    ):
        assert marker in units["body.p1235"]


def test_neighbor_ownership_and_context_only_refs(plan: dict) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert all(owner_by_ref[ref] == 103 for ref in OWNED)
    assert all(owner_by_ref[ref] == 102 for ref in PACKAGE102_OWNED)
    assert all(
        f"body.p{n}" not in owner_by_ref
        for n in (*range(1198, 1200), *range(1206, 1224))
    )

    assert all(owner_by_ref[ref] == 104 for ref in PACKAGE104_OWNED)
    assert "body.p1237#atom-100-160" not in owner_by_ref
    assert all(ref not in owner_by_ref for ref in ATTACHED)
    package103_owned = {
        unit["source_ref"]
        for package in plan["packages"]
        if package["package_ordinal"] == 103
        for unit in package["owned_units"]
    }
    assert not (set(EXCLUDED_NEIGHBORS) & package103_owned)


def test_model_free_prepare_has_only_declared_sources() -> None:
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
    clinical_qc = _load(PREPARE_DIR / "clinical-qc.json")
    batch = _load(PREPARE_DIR / "execution" / "batch.json")
    prompt = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert summary["attached_count"] == 1
    assert summary["owned_count"] == 11
    assert summary["unit_count"] == 12
    assert summary["claims_complete"] is False
    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == [
        "owned" if ref in OWNED else "attached" for ref in ORDERED
    ]
    assert [row["source_ref"] for row in clinical_qc["rows"]] == ORDERED
    assert all(row["agent_candidates"] == [] for row in clinical_qc["rows"])
    assert clinical_qc["runner_status"] == "dry_run"
    assert clinical_qc["gate"]["skipped"] is True
    assert batch["known_official_targets"] == []
    assert batch["known_procedure_targets"] == []
    assert batch["owned_required_action_kinds_by_structure_unit_id"] == {}
    assert batch["owned_required_procedure_target_ids_by_structure_unit_id"] == {}
    assert batch["owned_visit_instance_by_structure_unit_id"] == {}
    assert batch["pre_enrollment_structure_unit_ids"] == []
    for ref in ORDERED:
        assert ref in prompt
    for ref in EXCLUDED_NEIGHBORS:
        assert ref not in prompt


def test_config_resists_safety_pk_to_eligibility_inversion(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "治疗后安全性汇总",
        "不形成筛选、基线、随机或D1给药前控制点",
        "仅作为安全性统计列表",
        "PK采样时间、血药浓度和曲线是PK分析数据与统计展示的时间/结果维度",
        "PopPK是研究数据与前期数据的模型分析",
        "如数据允许",
        "相关性探索",
        "不得把暴露参数、暴露-疗效/安全性相关性或分析结果改写为入排标准",
    ):
        assert phrase in combined
    forbidden = config["candidate_forbidden_markers_by_source_ref"]
    for source_ref, marker in (
        ("body.p1226", "实验室异常不得入组"),
        ("body.p1228", "妊娠检查阳性不得入组"),
        ("body.p1229", "合并治疗不符合入排"),
        ("body.p1231", "PK缺失不得入组"),
        ("body.p1233", "NONMEM模型失败不得入组"),
        ("body.p1235", "暴露-效应结果不得入组"),
        ("body.p1235", "暴露/安全性相关性作为入选标准"),
    ):
        assert marker in forbidden[source_ref]


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == (
        "92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4"
    )
    assert _sha256(STRUCTURE_PATH) == (
        "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
    )
    assert CHECKLIST_PATH.exists()
