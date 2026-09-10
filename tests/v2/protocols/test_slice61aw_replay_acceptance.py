"""Representative replay must not present a partial green gate as acceptance."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / ".trellis/tasks/08-22-phase5-clinical-facts-profile/research/"
    "d001-ii-phase-closure/slice59n_representative_group_control_replay.py"
)


def _load_replay_module():
    spec = importlib.util.spec_from_file_location("slice61aw_replay", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_overall_replay_rejects_publication_green_with_clinical_gap() -> None:
    replay = _load_replay_module()

    assert not replay._technical_replay_accepted(
        hydrated=object(),
        publication_gate_accepted=True,
        clinical_issues=[object()],
    )


def test_overall_replay_requires_hydration_and_both_gates() -> None:
    replay = _load_replay_module()

    assert replay._technical_replay_accepted(
        hydrated=object(),
        publication_gate_accepted=True,
        clinical_issues=[],
    )
    assert not replay._technical_replay_accepted(
        hydrated=None,
        publication_gate_accepted=True,
        clinical_issues=[],
    )
