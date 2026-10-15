import copy

import pytest
from jsonschema import ValidationError

from app.llm.json_missing_fields_repair import completion_messages, merge_completion, missing_fields_schema

SCHEMA = {"type": "object", "properties": {"facts": {"type": "array"}, "unresolved": {"type": "array"}},
          "required": ["facts", "unresolved"], "additionalProperties": False}


def test_preserves_original_and_never_defaults_missing_judgment():
    value = {"facts": [{"raw": "original"}]}
    before = copy.deepcopy(value)
    assert missing_fields_schema(value, SCHEMA)["required"] == ["unresolved"]
    with pytest.raises(ValidationError):
        merge_completion(value, {}, SCHEMA)
    result = merge_completion(value, {"unresolved": ["researcher judgment missing"]}, SCHEMA)
    assert result["facts"] == value["facts"]
    assert value == before
    assert completion_messages([], value, SCHEMA)[-1]["role"] == "user"


def test_rejects_overwrite_and_nested_or_other_errors():
    with pytest.raises(ValidationError):
        merge_completion({"facts": [1]}, {"facts": [], "unresolved": []}, SCHEMA)
    with pytest.raises(ValueError):
        missing_fields_schema({"facts": "bad"}, SCHEMA)
    with pytest.raises(ValueError):
        missing_fields_schema({"facts": [], "unresolved": []}, SCHEMA)


def test_nested_missing_field_is_not_a_top_level_completion():
    schema = copy.deepcopy(SCHEMA)
    schema["properties"]["facts"]["items"] = {
        "type": "object", "properties": {"raw": {"type": "string"}},
        "required": ["raw"], "additionalProperties": False,
    }
    with pytest.raises(ValueError):
        missing_fields_schema({"facts": [{}]}, schema)


def test_messages_and_merged_values_do_not_alias_originals():
    messages = [{"role": "user", "content": "original source"}]
    value = {"facts": [{"raw": "source"}]}
    patch = {"unresolved": ["missing judgment"]}
    result = merge_completion(value, patch, SCHEMA)
    result["facts"][0]["raw"] = "changed"
    result["unresolved"].clear()
    built = completion_messages(messages, value, SCHEMA)
    built[0]["content"] = "changed"
    assert messages[0]["content"] == "original source"
    assert value["facts"][0]["raw"] == "source"
    assert patch["unresolved"] == ["missing judgment"]
