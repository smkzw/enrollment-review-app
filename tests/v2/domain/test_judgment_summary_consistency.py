"""A persisted summary must not contradict its retained findings or gaps."""
import pytest
from pydantic import ValidationError

from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus as Status,
    JudgmentSearchCoverageSummary,
    JudgmentSearchLane,
)
from app.domain.judgment_search_coverage import summarize_judgment_search_coverage
from tests.v2.domain.test_judgment_search_coverage import (
    _measurement_scope, _lane, _page_result, _found, _ambiguous, _unreadable,
)


@pytest.mark.parametrize("case,retained_field", [
    ("missing", "missing_lanes"),
    ("page", "pages_without_lane_result"),
    ("found", "found_candidates"),
    ("ambiguous", "ambiguous_channels"),
    ("unreadable", "unreadable_channels"),
])
def test_incomplete_or_found_result_cannot_be_relabeled_without_candidate(case, retained_field):
    scope = _measurement_scope()
    channel = {"found": _found("合成判断摘录"), "ambiguous": _ambiguous(),
               "unreadable": _unreadable()}.get(case)
    lanes = [] if case == "missing" else [
        _lane(scope, JudgmentSearchLane.MAIN_A, [
            _page_result(page, handwritten=channel) for page in scope.pages
            if case != "page" or page == scope.pages[0]
        ])
    ]
    summary = summarize_judgment_search_coverage(scope, lanes)
    payload = summary.model_dump(mode="json")
    assert payload[retained_field]
    for field in ("missing_lanes", "pages_without_lane_result", "found_candidates",
                  "ambiguous_channels", "unreadable_channels"):
        if field != retained_field:
            payload[field] = []
    payload["status"] = Status.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE.value
    with pytest.raises(ValidationError, match="未见候选.*不一致"):
        JudgmentSearchCoverageSummary.model_validate(payload)
