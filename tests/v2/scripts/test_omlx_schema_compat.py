from copy import deepcopy

import pytest

from app.llm.omlx_schema_compat import decoding_response_format
from app.llm.generation_repetition import repetitive_closing_tag_tail


def test_projection_preserves_original_and_other_constraints():
    value = {"type": "json_schema", "json_schema": {"schema": {
        "type": "object", "additionalProperties": False, "properties": {
            "label": {"type": "string", "minLength": 1, "pattern": r"\S"},
            "code": {"type": "string", "pattern": "^[A-Z]+$"}}}}}
    original = deepcopy(value)
    projected = decoding_response_format(value)
    assert value == original
    props = projected["json_schema"]["schema"]["properties"]
    assert props["label"] == {"type": "string", "minLength": 1}
    assert props["code"]["pattern"] == "^[A-Z]+$"
    assert projected["json_schema"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize("text,expected", [
    (("</function_results>\n" * 6 + "</null>\n") * 100, True),
    ("</function_results>\n" * 10, False),
    ('{"result":"正常","value":1}\n' * 1000, False),
    ("重复临床资料内容\n" * 2000, False),
    (("</alpha>\n</beta>\n</gamma>\n</delta>\n</epsilon>\n") * 300, False),
    (("</function_results>\n临床检查已记录但仍需核实来源\n") * 500, False),
])
def test_only_sustained_closing_tags_fail(text, expected):
    assert repetitive_closing_tag_tail(text) is expected
