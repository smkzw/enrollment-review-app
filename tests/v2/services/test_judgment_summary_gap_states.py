"""Not yet searched is not a finding that written judgment is missing."""
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import GapType, ReviewStage
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus as Status,
    JudgmentSearchCoverageSummary,
)
from app.services.eligibility_review_projection import _summary_gaps


@pytest.mark.parametrize(("status", "expected"), [
    (None, GapType.OBSERVATION_UNVERIFIED),
    (Status.COVERAGE_INCOMPLETE, GapType.OBSERVATION_UNVERIFIED),
    (Status.CANDIDATES_PRESENT, GapType.OBSERVATION_UNVERIFIED),
    (Status.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE, GapType.PROFESSIONAL_JUDGMENT),
])
def test_search_states_do_not_collapse_into_absence(status, expected):
    requirement = SimpleNamespace(
        requirement_id="judgment", due_stage=ReviewStage.SCREENING,
        required_source_types=["investigator_assessment"],
    )
    component = SimpleNamespace(
        determination_mode=SimpleNamespace(value="investigator_judgment"),
        evidence_requirements=[requirement],
    )
    summaries = {} if status is None else {
        "judgment": JudgmentSearchCoverageSummary(
            scope_sha256="a" * 64, requirement_id="judgment", status=status,
        ),
    }
    assert _summary_gaps(
        component, episode_stage=ReviewStage.SCREENING,
        summaries=summaries, templates_by_requirement={},
    ) == {expected}


@pytest.mark.parametrize("other_requirement", [False, True])
def test_live_summary_does_not_override_missing_file_for_same_requirement(other_requirement):
    from app.domain.contracts.enums import ExpectationStatus
    from app.domain.gates.assessment import RequirementGapState

    requirement = SimpleNamespace(
        requirement_id="judgment", due_stage=ReviewStage.SCREENING,
        required_source_types=["investigator_assessment"],
    )
    component = SimpleNamespace(
        determination_mode=SimpleNamespace(value="investigator_judgment"),
        evidence_requirements=[requirement],
    )
    summary = JudgmentSearchCoverageSummary(
        scope_sha256="a" * 64, requirement_id="judgment",
        status=Status.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE,
    )
    states = [RequirementGapState(
        "unrelated" if other_requirement else "judgment",
        ExpectationStatus.ABSENT, GapType.REFERENCED_FILE_MISSING,
    )]
    assert _summary_gaps(
        component, episode_stage=ReviewStage.SCREENING,
        summaries={"judgment": summary}, templates_by_requirement={},
        expectations=states,
    ) == ({GapType.PROFESSIONAL_JUDGMENT} if other_requirement else set())


@pytest.mark.parametrize("status,expected,fallback", [
    (None, GapType.OBSERVATION_UNVERIFIED, True),
    (Status.COVERAGE_INCOMPLETE, GapType.OBSERVATION_UNVERIFIED, True),
    (Status.CANDIDATES_PRESENT, GapType.OBSERVATION_UNVERIFIED, True),
    (Status.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE, GapType.PROFESSIONAL_JUDGMENT, False),
])
def test_expectation_producer_preserves_completed_search_gap(status, expected, fallback):
    from app.services.fact_expectation_gaps import expectation_gap_signals

    template = SimpleNamespace(template_id="template", requirement_id="judgment",
        due_stage=ReviewStage.SCREENING, workflow_stage_id="screening",
        required_source_types=["investigator_assessment"], description="合成书面判断要求")
    episode = SimpleNamespace(stage=ReviewStage.SCREENING, workflow_stage_id="screening")
    authority = SimpleNamespace(rule_set_id="rules", rule_set_revision=1, review_episode_id="episode")
    summaries = {} if status is None else {"judgment": JudgmentSearchCoverageSummary(
        scope_sha256="a" * 64, requirement_id="judgment", status=status)}
    signals = expectation_gap_signals(None, authority, [],
        judgment_search_summaries=summaries,
        _templates_lookup=lambda *_: [template],
        _episode_lookup=lambda _: SimpleNamespace(get=lambda _: episode))
    assert len(signals) == 1
    assert signals[0].kind == expected
    assert signals[0].fallback_only is fallback
    assert signals[0].applies_to_template_id == "template"
    if not fallback:
        assert "本次提交的资料中" in signals[0].detail


@pytest.mark.parametrize("missing_file", [False, True])
def test_complete_supplied_search_does_not_override_missing_file(missing_file):
    from app.domain.judgment_search_coverage import summarize_judgment_search_coverage
    from app.services.fact_expectation_gaps import expectation_gap_signals
    from tests.v2.domain.test_judgment_search_coverage import _measurement_scope, _both_lanes_all_not_found

    scope = _measurement_scope()
    summary = summarize_judgment_search_coverage(scope, _both_lanes_all_not_found(scope))
    template = SimpleNamespace(template_id="template", requirement_id=scope.requirement_id,
        due_stage=ReviewStage.SCREENING, workflow_stage_id="screening",
        required_source_types=["investigator_assessment"], description="合成书面判断要求")
    episode = SimpleNamespace(stage=ReviewStage.SCREENING, workflow_stage_id="screening")
    unresolved = [] if not missing_file else [SimpleNamespace(item=SimpleNamespace(
        gap_type=GapType.REFERENCED_FILE_MISSING, affected_requirement_ids=[scope.requirement_id],
        reason="所引用的病历尚未提供", referenced_file_id="missing-document"))]
    signals = expectation_gap_signals(None, scope.authority, unresolved,
        judgment_search_summaries={scope.requirement_id: summary},
        _templates_lookup=lambda *_: [template],
        _episode_lookup=lambda _: SimpleNamespace(get=lambda _: episode))
    assert [signal.kind for signal in signals] == [
        GapType.REFERENCED_FILE_MISSING if missing_file else GapType.PROFESSIONAL_JUDGMENT]
    assert all(not signal.fallback_only for signal in signals)


@pytest.mark.parametrize("gap", [GapType.PROFESSIONAL_JUDGMENT, GapType.OBSERVATION_UNVERIFIED])
def test_v2_gap_projection_does_not_bypass_legacy_contract(gap, monkeypatch):
    from datetime import datetime, timezone
    from app.domain.contracts.enums import ExpectationStatus
    from app.domain.contracts.evidence import EvidenceExpectation
    from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
    from app.domain.gates.assessment import RequirementGapState
    from app.services.eligibility_review_projection import _expectation_views, EligibilityReviewProjectionError
    from tests.v2.llm.test_predicate_binding_candidates import _case

    expectation = EvidenceExpectationV2(
        expectation_id="expectation", authority=_case()[0].authority,
        template_id="template", status=ExpectationStatus.ABSENT,
        gap_type=gap, revision=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(EvidenceExpectation, "model_construct",
                        lambda **_: pytest.fail("不得绕过旧合同伪装v2状态"))
    views = _expectation_views([expectation], {"template": SimpleNamespace(requirement_id="requirement")})
    assert views == [RequirementGapState("requirement", ExpectationStatus.ABSENT, gap)]
    with pytest.raises(EligibilityReviewProjectionError, match="来源模板不存在"):
        _expectation_views([expectation], {})
