#!/usr/bin/env python3
"""Package 100 model-free statistical and phase-boundary regressions."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_PATH = PHASE_CLOSURE / "configs" / (
    "representative_group_package100_statistical_hypothesis_phase_boundary.v1.json"
)
CHECKLIST_PATH = PHASE_CLOSURE / (
    "slice61cm-package100-statistical-hypothesis-phase-boundary-parent-checklist.md"
)
PREPARE_DIR = PHASE_CLOSURE / "slice59n-prepare" / (
    "d001-ii-package100-statistical-hypothesis-phase-boundary"
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
PACKAGE_ID = "pap-fb5d1edc8f1ed99baf4a4a8a"
OWNED = ["body.p1168", "body.p1169", "body.p1170"]
ATTACHED = [f"body.p{n}" for n in range(1171, 1180)]
PHASE_III = [f"body.p{n}" for n in range(1172, 1179)]
EXCLUDED_NEIGHBORS = [
    *[f"body.p{n}" for n in range(1158, 1168)],
    *[f"body.p{n}" for n in range(1180, 1197)],
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
    assert config["owned_source_refs"] == OWNED
    assert config["attached_source_refs"] == ATTACHED
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(OWNED + ATTACHED)
    assert config["structural_only_source_refs"] == ["body.p1168", "body.p1170"]
    assert config["expected_disposition_by_source_ref"] == {
        "body.p1169": "administrative_statistical_background"
    }
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_frozen_plan_owns_only_three_package100_units(plan: dict) -> None:
    assert plan["plan_id"] == PLAN_ID
    package = next(p for p in plan["packages"] if p["package_ordinal"] == 100)
    assert package["package_id"] == PACKAGE_ID
    assert [u["source_ref"] for u in package["owned_units"]] == OWNED
    context = {u["source_ref"] for u in package["context_units"]}
    assert set(ATTACHED) <= context
    assert not (set(EXCLUDED_NEIGHBORS) & set(OWNED))


def test_phase_graph_keeps_ii_and_iii_branches_separate(
    manifest: dict, plan: dict
) -> None:
    units = {u["source_ref"]: u for u in manifest["units"]}
    assert units["body.p1171"]["phase_scopes"] == ["phase_ii"]
    for ref in PHASE_III:
        assert units[ref]["phase_scopes"] == ["phase_iii"]
    assert units["body.p1179"]["phase_scopes"] == ["unknown"]
    target_refs = {
        unit["source_ref"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert not (set(PHASE_III) & target_refs)
    assert "body.p1179" in target_refs


def test_source_excerpts_preserve_statistical_meaning(manifest: dict) -> None:
    units = {u["source_ref"]: u["excerpt"] for u in manifest["units"]}
    assert units["body.p1168"] == "统计学考虑"
    assert "Ⅱ期和Ⅲ期研究" in units["body.p1169"]
    assert "数据库锁定前由申办者批准并定稿" in units["body.p1169"]
    assert units["body.p1170"] == "统计假设"
    assert units["body.p1171"] == "Ⅱ期为探索性研究，不做检验假设。"
    assert "Ⅲ期研究主要目的" in units["body.p1172"]
    assert units["body.p1174"].startswith("H_0")
    assert units["body.p1176"] == "Alpha = 0.025（单侧）"
    assert units["body.p1179"] == "样本量计算"


def test_package101_retains_closing_heading_ownership(plan: dict) -> None:
    owner_by_ref = {
        unit["source_ref"]: package["package_ordinal"]
        for package in plan["packages"]
        for unit in package["owned_units"]
    }
    assert owner_by_ref["body.p1179"] == 101
    assert all(owner_by_ref[ref] == 100 for ref in OWNED)
    assert all(ref not in owner_by_ref for ref in PHASE_III)


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
    assert summary["attached_count"] == 9
    assert summary["owned_count"] == 3
    assert summary["unit_count"] == 12
    assert summary["claims_complete"] is False
    assert [row["source_ref"] for row in rows] == OWNED + ATTACHED
    for ref in OWNED + ATTACHED:
        assert ref in prompt
    for ref in EXCLUDED_NEIGHBORS:
        assert ref not in prompt


def test_config_resists_statistical_to_eligibility_inversion(config: dict) -> None:
    combined = json.dumps(config, ensure_ascii=False)
    assert "数据库锁定前是统计文件定稿时限" in combined
    assert "不构成入排资格、流程必做或证据缺口" in combined
    assert "p1179只作为关闭边界" in combined
    for marker in ("随机前完成SAP", "入组前批准SAP", "缺少SAP不得入组"):
        assert marker not in combined


def test_immutable_source_fingerprints() -> None:
    assert _sha256(PLAN_PATH) == (
        "92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4"
    )
    assert _sha256(STRUCTURE_PATH) == (
        "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
    )
    assert CHECKLIST_PATH.exists()
