import re

import jsonschema
import pytest

from app.agents.protocol_deconstructor import (
    _wire_categorical_value_schema,
    _wire_value_atom_schema,
)


@pytest.mark.parametrize("value,valid", [
    ("严重感染", True), ("mg/dL", True), ("a\nb", True),
    ("单", True), ("", False), (" \t\n", False), ("\u3000", False),
])
def test_nonblank_pattern_agrees_for_search_and_full_match(value, valid):
    scalar = _wire_value_atom_schema("scalar")["properties"]
    for schema in (_wire_categorical_value_schema(), scalar["source_term"], scalar["unit"]):
        assert jsonschema.Draft202012Validator(schema).is_valid(value) is valid
        assert bool(re.fullmatch(schema["pattern"], value)) is valid
