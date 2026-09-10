import json

import pytest
from pydantic import ValidationError

from scripts.evaluate_conflict_reread import Reread, messages_for


def test_blind_prompt_contains_targets_not_candidate_values(monkeypatch):
    monkeypatch.setattr("scripts.evaluate_conflict_reread.page_to_data_url", lambda _: "data:image/png;base64,test")
    messages = messages_for(b"image", ["target-alpha"])
    text = json.loads(messages[1]["content"][1]["text"])
    assert text == {"targets": ["target-alpha"]}
    assert len(messages) == 2


def test_reread_rejects_verdicts_and_requires_explicit_unreadable_list():
    with pytest.raises(ValidationError):
        Reread.model_validate({"observations": [], "unreadable_targets": [], "exclusion_triggered": False})
    with pytest.raises(ValidationError):
        Reread.model_validate({"observations": []})


def test_reread_preserves_zero_units_and_arrows():
    value = Reread.model_validate({"observations": [
        {"field": "target", "value_with_unit": "0↓ /μL", "excerpt": "target 0↓ /μL"}
    ], "unreadable_targets": []})
    assert value.observations[0].value_with_unit == "0↓ /μL"
