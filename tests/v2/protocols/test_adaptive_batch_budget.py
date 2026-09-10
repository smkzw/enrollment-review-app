"""Adaptive token-budget packing and anti-overfit checks."""

from __future__ import annotations

import re
from pathlib import Path

from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
)
from app.protocols.adaptive_batch_budget import (
    AdaptiveBatchBudget,
    estimate_text_tokens,
    pack_structure_units_by_budget,
)
from app.protocols.protocol_control_planning import plan_protocol_control_discovery


ROOT = Path(__file__).resolve().parents[3]

_WORD_BOUNDED_MARKERS = (
    "D001",
    "MG-K10-SAR",
    "CMS-D001",
    "SAR-001",
    "PASI",
    "EASI",
    "IGA",
    "SCORAD",
    "DLQI",
    "PGA",
    "BSA",
)
_SUBSTRING_MARKERS = (
    "银屑病",
    "特应性皮炎",
    "度普利尤",
    "达必妥",
)


def _unit(number: int, *, excerpt: str | None = None, heading: str = "通用章节") -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=f"unit-{number:03d}",
        source_ref=f"body.p{number}",
        member_source_refs=[f"body.p{number}"],
        source_span_ids=[f"span:{number:03d}"],
        unit_kind="paragraph",
        heading_path=[heading],
        source_order=number,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt or f"第{number}项通用原文，必须记录对象状态并保留溯源。",
    )


def _manifest(count: int = 40, *, long: bool = False) -> ProtocolSectionCoverageManifest:
    excerpt = ("通用长原文。" * 80) if long else None
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:adaptive-neutral",
        protocol_version_id="protocol:adaptive-neutral",
        protocol_document_sha256="b" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:adaptive-neutral",
        units=[_unit(number, excerpt=excerpt) for number in range(count)],
    )


def test_token_estimate_is_monotonic_and_project_neutral() -> None:
    short = estimate_text_tokens("短")
    long = estimate_text_tokens("短" * 100)
    assert short >= 1
    assert long > short


def test_adaptive_packing_respects_input_and_output_budgets_without_dropping_coverage() -> None:
    units = _manifest(30, long=True).units
    budget = AdaptiveBatchBudget(
        max_input_tokens=6000,
        max_output_tokens=2000,
        output_tokens_per_unit=280,
        template_overhead_tokens=1200,
        chars_per_token=1.2,
        max_units_hard_cap=24,
    )
    packs = pack_structure_units_by_budget(
        units,
        budget=budget,
        context_radius=1,
        group_by_heading=False,
    )
    covered = [unit.structure_unit_id for pack in packs for unit in pack.owned_units]
    assert covered == [unit.structure_unit_id for unit in units]
    assert len(packs) > 1
    assert all(len(pack.owned_units) <= budget.max_units_hard_cap for pack in packs)
    for pack in packs:
        if pack.over_budget:
            assert len(pack.owned_units) == 1
        else:
            assert pack.estimated_input_tokens <= budget.max_input_tokens
            assert pack.estimated_output_tokens <= budget.max_output_tokens


def test_adaptive_discovery_plan_is_smaller_than_fixed_48_for_long_units() -> None:
    manifest = _manifest(60, long=True)
    fixed = plan_protocol_control_discovery(manifest, max_units_per_batch=48)
    adaptive = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=48,
        batch_budget=AdaptiveBatchBudget(
            max_input_tokens=8000,
            max_output_tokens=3000,
            output_tokens_per_unit=280,
            template_overhead_tokens=2000,
            max_units_hard_cap=24,
        ),
    )
    assert len(fixed.batches) == 2
    assert len(adaptive.batches) > len(fixed.batches)
    assert [
        unit_id
        for batch in adaptive.batches
        for unit_id in batch.target_structure_unit_ids
    ] == [f"unit-{number:03d}" for number in range(60)]
    assert all(len(batch.target_units) <= 24 for batch in adaptive.batches)


def test_adaptive_modules_have_no_project_specific_markers() -> None:
    files = (
        ROOT / "app/protocols/adaptive_batch_budget.py",
        ROOT / "app/protocols/protocol_control_planning.py",
        ROOT / "app/services/protocol_control_execution.py",
        ROOT / "app/config.py",
        ROOT / ".env.example",
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        hits = []
        for marker in _SUBSTRING_MARKERS:
            if marker in text:
                hits.append(marker)
        for marker in _WORD_BOUNDED_MARKERS:
            if re.search(rf"\b{re.escape(marker)}\b", text):
                hits.append(marker)
        assert not hits, f"{path} contains project markers: {hits}"
