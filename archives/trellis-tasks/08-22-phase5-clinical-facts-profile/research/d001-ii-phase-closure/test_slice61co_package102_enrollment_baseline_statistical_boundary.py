#!/usr/bin/env python3
"""Package 102 model-free statistical-domain boundary regressions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package102_enrollment_baseline_statistical_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61co-package102-enrollment-baseline-statistical-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package102-enrollment-baseline-statistical-boundary"
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
PACKAGE_ID = "pap-ad0c757625a628fce5c7ed7c"
OWNED = [
    "body.p1197",
    "body.p1200",
    "body.p1201",
    "body.p1202",
    "body.p1203",
    "body.p1204",
    "body.p1205",
]
ATTACHED = [
    "body.p1198",
    "body.p1199",
    "body.p1206",
    "body.p1207",
    "body.p1208",
    "body.p1209",
]
ORDERED = [f"body.p{n}" for n in range(1197, 1210)]
STRUCTURAL = [
    "body.p1197",
    "body.p1200",
    "body.p1202",
    "body.p1205",
]
ATTACHED_STRUCTURAL = ["body.p1206", "body.p1207"]
SEMANTIC = ["body.p1201", "body.p1203", "body.p1204"]
PHASE_III = ["body.p1199"]
PHASE_II_ATTACHED = [
    "body.p1198",
    "body.p1206",
    "body.p1207",
    "body.p1208",
    "body.p1209",
]
EXCLUDED_NEIGHBORS = [
    *[f"body.p{n}" for n in range(1186, 1197)],
    *[f"body.p{n}" for n in range(1210, 1238)],
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
    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == []
    assert config["forbidden_candidate_source_refs"] == ORDERED
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL
    assert config["attached_structural_only_source_refs"] == ATTACHED_STRUCTURAL
    assert config["expected_disposition_by_source_ref"] == {
        ref: "administrative_statistical_background" for ref in SEMANTIC
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert set(config["candidate_forbidden_markers_by_source_ref"]) == set(ORDERED)
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []
    assert config["phase_applicability"]["scope"] == "phase_ii"
    assert config["notes"][-1].startswith("claims_complete=false")


def test_frozen_plan_owns_exact_package102_units(plan: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    package = next(p for p in plan["packages"] if p["package_ordinal"] == 102)
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
    assert all(owner_by_ref[ref] == 102 for ref in OWNED)
    assert all(ref not in owner_by_ref for ref in ATTACHED)
    assert not (set(EXCLUDED_NEIGHBORS) & set(OWNED))


def test_phase_graph_keeps_ii_and_iii_enrollment_context_separate(
    manifest: dict, plan: dict
) -> None:
    units = {u["source_ref"]: u for u in manifest["units"]}
    assert units["body.p1198"]["phase_scopes"] == ["phase_ii"]
    for ref in PHASE_III:
        assert units[ref]["phase_scopes"] == ["phase_iii"]
    for ref in PHASE_II_ATTACHED:
        assert units[ref]["phase_scopes"] == ["phase_ii"]
    package102 = next(p for p in plan["packages"] if p["package_ordinal"] == 102)
    target_refs = {
        unit["source_ref"]
        for unit in package102["owned_units"]
    }
    assert not (set(PHASE_III) & target_refs)
    assert "body.p1199" in {
        unit["source_ref"] for unit in package102["context_units"]
    }


def test_source_excerpts_preserve_statistical_meaning(manifest: dict) -> None:
    units = {u["source_ref"]: u["excerpt"] for u in manifest["units"]}
    assert units["body.p1197"] == "参与者入组分析"
    assert "总体入选及完成参与者例数" in units["body.p1198"]
    assert "Ⅱ期临床阶段" in units["body.p1198"]
    assert "Ⅲ期临床阶段" in units["body.p1199"]
    assert "完成16周基础期治疗" in units["body.p1199"]
    assert units["body.p1200"] == "人口统计学和基线特征分析"
    for marker in ("ITT集", "描述性统计", "按组别及总体", "基线特性"):
        assert marker in units["body.p1201"]
    assert units["body.p1202"] == "药物治疗与非药物治疗分析"
    assert "WHO Drug" in units["body.p1203"]
    assert "例数和百分比" in units["body.p1203"]
    for marker in ("MedDRA", "系统器官分类", "SOC", "PT", "例数与百分比"):
        assert marker in units["body.p1204"]
    assert units["body.p1205"] == "疗效分析"
    assert units["body.p1206"] == "Ⅱ期临床研究阶段"
    assert units["body.p1207"] == "主要疗效指标分析"
    for marker in ("第12周", "PASI-75", "CMH检验", "95%的置信区间", "多重填补"):
        assert marker in units["body.p1208"]
    for marker in ("缺失", "LOCF", "NRI", "敏感性分析"):
        assert marker in units["body.p1209"]


def test_neighbor_ownership_and_context_only_refs(plan: dict) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert all(owner_by_ref[ref] == 102 for ref in OWNED)
    assert owner_by_ref["body.p1179"] == 101
    assert all(owner_by_ref[f"body.p{n}"] == 101 for n in range(1186, 1197))
    assert owner_by_ref["body.p1224"] == 103
    assert all(f"body.p{n}" not in owner_by_ref for n in range(1210, 1224))
    for ref in ATTACHED:
        assert ref not in owner_by_ref
    for ref in EXCLUDED_NEIGHBORS:
        assert ref not in {
            unit["source_ref"]
            for package in plan["packages"]
            if package["package_ordinal"] == 102
            for unit in package["owned_units"]
        }


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
    assert summary["attached_count"] == 6
    assert summary["owned_count"] == 7
    assert summary["unit_count"] == 13
    assert summary["claims_complete"] is False
    assert [row["source_ref"] for row in rows] == ORDERED
    assert [row["role"] for row in rows] == [
        "owned" if ref in OWNED else "attached" for ref in ORDERED
    ]
    assert [row["source_ref"] for row in clinical_qc["rows"]] == ORDERED
    assert all(row["agent_candidates"] == [] for row in clinical_qc["rows"])
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


def test_config_resists_statistical_to_eligibility_inversion(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    for phrase in (
        "事后统计总结",
        "不是新的入组标准、筛选动作或入组决策入口",
        "基线是ITT统计描述域",
        "WHO Drug是统计编码和汇总维度",
        "MedDRA SOC/PT仅是合并治疗的统计分类",
        "疗效终点及缺失处理属于随机后分析方法",
        "不构成入排资格、流程必做或证据缺口",
    ):
        assert phrase in combined
    for marker in (
        "基线资料缺失不得入组",
        "合并用药编码缺失不得入组",
        "WHO Drug缺失不得入组",
        "MedDRA编码缺失不得入组",
        "PASI-75未应答不得入组",
        "LOCF失败不得入组",
        "统计分析集不足不得入组",
    ):
        assert marker not in combined


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == (
        "92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4"
    )
    assert _sha256(STRUCTURE_PATH) == (
        "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
    )
    assert CHECKLIST_PATH.exists()
