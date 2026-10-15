#!/usr/bin/env python3
"""Package 101 model-free sample-size and analysis-set regressions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package101_analysis_set_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cn-package101-analysis-set-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package101-analysis-set-boundary"
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
PACKAGE_ID = "pap-b0e90038f781b39606b42df9"
OWNED = ["body.p1179", *[f"body.p{n}" for n in range(1186, 1197)]]
ATTACHED = [f"body.p{n}" for n in range(1180, 1186)]
ORDERED = [f"body.p{n}" for n in range(1179, 1197)]
STRUCTURAL = [
    "body.p1179",
    "body.p1186",
    "body.p1187",
    "body.p1193",
    "body.p1194",
]
SEMANTIC = [f"body.p{n}" for n in range(1188, 1193)] + [
    "body.p1195",
    "body.p1196",
]
EXCLUDED_NEIGHBORS = [
    *[f"body.p{n}" for n in range(1168, 1179)],
    *[f"body.p{n}" for n in range(1197, 1206)],
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
    assert set(config["forbidden_candidate_source_refs"]) == set(ORDERED)
    assert config["structural_only_source_refs"] == STRUCTURAL
    assert config["expected_disposition_by_source_ref"] == {
        ref: "administrative_statistical_background" for ref in SEMANTIC
    }
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_frozen_plan_owns_exact_package101_units(plan: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    package = next(p for p in plan["packages"] if p["package_ordinal"] == 101)
    assert package["package_id"] == PACKAGE_ID
    assert [u["source_ref"] for u in package["owned_units"]] == OWNED
    context = {u["source_ref"] for u in package["context_units"]}
    assert set(ATTACHED) <= context
    assert not (set(EXCLUDED_NEIGHBORS) & set(OWNED))


def test_phase_graph_keeps_sample_size_branches_separate(manifest: dict) -> None:
    units = {u["source_ref"]: u for u in manifest["units"]}
    for ref in ("body.p1180", "body.p1181"):
        assert units[ref]["phase_scopes"] == ["phase_ii"]
    for ref in ("body.p1182", "body.p1183", "body.p1184", "body.p1185"):
        assert units[ref]["phase_scopes"] == ["phase_iii"]
    assert units["body.p1192"]["phase_scopes"] == ["mixed"]


def test_source_excerpts_preserve_statistical_meaning(manifest: dict) -> None:
    units = {u["source_ref"]: u["excerpt"] for u in manifest["units"]}
    assert units["body.p1179"] == "样本量计算"
    for marker in ("剂量探索", "不做正式的假设检验", "1:1:1", "合计约120例"):
        assert marker in units["body.p1181"]
    for marker in ("Ⅲ期", "2:1", "201例", "99%"):
        assert marker in units["body.p1183"]
    for marker in ("43.2%", "47.4%"):
        assert marker in units["body.p1184"]
    for marker in ("20%", "最多入组420例", "2:2:1", "168例", "84例"):
        assert marker in units["body.p1185"]
    assert "随机化分组后的参与者" in units["body.p1188"]
    assert "实际治疗" in units["body.p1189"]
    assert "给药后" in units["body.p1190"]
    assert "给药后" in units["body.p1191"]
    assert "盲态数据审核后" in units["body.p1192"]
    assert "数据库锁库和揭盲之前" in units["body.p1192"]
    assert "SAS9.4" in units["body.p1195"]
    assert "WinNonlin" in units["body.p1195"]
    assert "MedDRA" in units["body.p1196"]
    assert "WHO Drug" in units["body.p1196"]


def test_neighbor_ownership_and_context_only_refs(plan: dict) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert all(owner_by_ref[ref] == 101 for ref in OWNED)
    assert owner_by_ref["body.p1197"] == 102
    assert all(owner_by_ref[f"body.p{n}"] == 102 for n in range(1200, 1206))
    assert "body.p1198" not in owner_by_ref
    assert "body.p1199" not in owner_by_ref


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
    prompt = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert summary["attached_count"] == 6
    assert summary["owned_count"] == 12
    assert summary["unit_count"] == 18
    assert summary["claims_complete"] is False
    assert [row["source_ref"] for row in rows] == ORDERED
    for ref in ORDERED:
        assert ref in prompt
    for ref in EXCLUDED_NEIGHBORS:
        assert ref not in prompt


def test_config_resists_analysis_set_to_eligibility_inversion(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    assert "基线在此表示分析内容" in combined
    assert "剔除指统计分析集剔除" in combined
    assert "不形成受试者级入排控制" in combined
    for marker in (
        "无安全性评价不得随机",
        "无PK数据不得入组",
        "盲态审核必须在随机前完成",
        "编码缺失不得入组",
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
