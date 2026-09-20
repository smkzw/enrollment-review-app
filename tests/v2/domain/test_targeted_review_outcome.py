import pytest
from pydantic import ValidationError

from app.domain.contracts.targeted_review_outcome import TargetedReviewOutcome


def agreement():
    return dict(outcome_kind="candidate_agreement_unaccepted", round_number=1,
                cue_kind="blind", agreed_candidate_targets=["检查项目"], requires_user_review=False)


@pytest.mark.parametrize("patch", [
    {"candidate_auto_accept": True}, {"clinical_findings_allowed": True},
    {"professional_judgment": "missing"}, {"exclusion_triggered": True},
    {"outcome_kind": "accepted"}, {"round_number": 3},
    {"agreed_candidate_targets": []}, {"requires_user_review": True},
    {"read_failures": [{"lane": "main-B", "failure_kind": "schema"}]},
    {"agreed_candidate_rounds": {"检查项目": 2}},
    {"agreed_candidate_rounds": {"另一个项目": 1}},
    {"agreed_candidate_targets": ["检查项目", "检查项目"]},
    {"pending_targets": ["检查项目"]},
])
def test_auxiliary_outcome_rejects_acceptance_and_clinical_findings(patch):
    with pytest.raises(ValidationError):
        TargetedReviewOutcome(**{**agreement(), **patch})


def test_candidate_agreement_is_explicitly_not_accepted():
    result = TargetedReviewOutcome(**agreement())
    assert not result.candidate_auto_accept
    assert not result.clinical_findings_allowed
