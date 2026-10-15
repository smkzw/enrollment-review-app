import json

import pytest

from app.llm.json_container_recovery import recover_single_container_close, strict_json_loads

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["rows", "notes"],
    "properties": {"rows": {"type": "array", "items": {"type": "object",
        "required": ["quote", "value"], "additionalProperties": False,
        "properties": {"quote": {"type": "string"}, "value": {"type": "number"}}}},
        "notes": {"type": "array", "items": {"type": "string"}}},
}


def test_unique_closing_container_preserves_every_original_byte_and_value():
    raw = '{"rows":[{"quote":"原文中的逗号,括号]}及\\\"引号","value":1.25},"notes":[]}'
    recovered = recover_single_container_close(raw, SCHEMA)
    assert recovered is not None and recovered.token == "]"
    assert recovered.text[:recovered.position] + recovered.text[recovered.position + 1:] == raw
    assert json.loads(recovered.text) == {"rows": [{"quote": '原文中的逗号,括号]}及"引号', "value": 1.25}], "notes": []}
    assert recovered.receipt(raw)["clinical_validation_complete"] is False
    assert recovered.receipt(raw)["original_sha256"] != recovered.receipt(raw)["recovered_sha256"]


@pytest.mark.parametrize("raw", [
    '{"rows":[],"notes":[]}',
    '{"rows":[{"quote":"完整文字","value":1}',
    '{"rows":[{"quote":"未闭合文字,"value":1},"notes":[]}',
    '{"rows":[{"quote":"文字","value":1,"value":2},"notes":[]}',
    '{"rows":[{"quote":"文字","value":NaN},"notes":[]}',
    '{"rows":[{"quote":"文字","value":1},"notes":[],"unknown":true}',
    '{"rows":[{"quote":"文字"},"notes":[]}',
])
def test_invalid_or_complete_json_never_gets_guessed_values(raw):
    assert recover_single_container_close(raw, SCHEMA) is None


def test_ambiguous_structure_and_large_scope_do_not_recover():
    raw = '{"rows":[[1,2,3]}'
    assert recover_single_container_close(raw, {"type": "object"}) is None
    assert recover_single_container_close('{"rows":[' + ','.join('1' for _ in range(130)) + ',"notes":[]}', SCHEMA) is None


def test_same_recovered_text_from_adjacent_positions_is_not_two_interpretations():
    raw = '{"rows":[[{"quote":"文字","value":1}],"notes":[]}'
    result = recover_single_container_close(raw, {"type": "object"})
    assert result is not None
    assert json.loads(result.text) == {"rows": [[{"quote": "文字", "value": 1}]], "notes": []}


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_normal_json_cannot_silently_select_duplicate_or_nonstandard_values(raw):
    with pytest.raises(json.JSONDecodeError):
        strict_json_loads(raw)
