"""A professional component does not impose written judgment on every requirement."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import ReviewStage
from app.services import judgment_search_job_service as service


@pytest.mark.parametrize(
    "source_types,stage,node,expected",
    [
        ([], ReviewStage.SCREENING, "screen", []),
        (["screening_record"], ReviewStage.SCREENING, "screen", []),
        ([" investigator_assessment "], ReviewStage.SCREENING, "screen", ["req"]),
        (["investigator_assessment"], ReviewStage.BASELINE, "baseline", []),
        (["investigator_assessment"], ReviewStage.SCREENING, "other-screen", []),
    ],
)
def test_structured_judgment_is_selected_without_crossing_nodes(
    monkeypatch, source_types, stage, node, expected,
):
    authority = SimpleNamespace(review_episode_id="episode", rule_set_id="rules", rule_set_revision=3)
    episode = SimpleNamespace(stage=ReviewStage.SCREENING, workflow_stage_id="screen")
    template = SimpleNamespace(
        requirement_id="req", due_stage=stage, workflow_stage_id=node,
        required_source_types=source_types,
    )
    monkeypatch.setattr(service, "EpisodeRepository", lambda session: SimpleNamespace(get=lambda key: episode))
    monkeypatch.setattr(service, "list_expectation_templates", lambda *args: [template])
    assert service.select_judgment_search_requirements(None, authority) == expected
