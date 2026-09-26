from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import TruthValue
from app.domain.proposition_observations import combine_observations


def _item(fact_id, truth):
    return SimpleNamespace(fact_id=fact_id, truth=truth, reason_codes=[])


@pytest.mark.parametrize(
    ("truths", "scope_verified", "expected"),
    [
        ([TruthValue.TRUE], True, TruthValue.TRUE),
        ([TruthValue.FALSE], True, TruthValue.FALSE),
        ([TruthValue.TRUE, TruthValue.FALSE], True, TruthValue.UNKNOWN),
        ([TruthValue.TRUE, TruthValue.UNKNOWN], True, TruthValue.UNKNOWN),
        ([TruthValue.TRUE], False, TruthValue.UNKNOWN),
    ],
)
def test_action_completion_keeps_explicit_negative_conflict_and_unknown_separate(
    truths, scope_verified, expected,
):
    policy = SimpleNamespace(mode="action_completion")
    observations = [_item(str(index), truth) for index, truth in enumerate(truths)]
    result, _ = combine_observations(policy, observations, scope_verified=scope_verified)
    assert result == expected


def test_action_completion_missing_record_is_unknown():
    result, reasons = combine_observations(
        SimpleNamespace(mode="action_completion"), [], scope_verified=True,
    )
    assert result == TruthValue.UNKNOWN
    assert "selected_observation_missing" in reasons
