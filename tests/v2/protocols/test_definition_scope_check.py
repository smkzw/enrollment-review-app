import pytest

from app.protocols.definition_scope_check import crosses_example_scope, example_ranges


@pytest.mark.parametrize("brackets", [("（", "）"), ("(", ")")])
def test_explicit_example_frequency_is_not_parent_requirement(brackets):
    left, right = brackets
    child = f"类别丙{left}一个周期内多次{right}"
    source = f"上位条件{left}包括但不限于类别甲、{child}{right}或当前条件"
    assert crosses_example_scope(source, child, "上位条件")
    assert not crosses_example_scope(source, child, "类别甲")


def test_actual_conjunction_is_not_an_example():
    source = "上位条件（同时满足次数要求）"
    assert not crosses_example_scope(source, "次数要求", "上位条件")


def test_ambiguous_or_malformed_spans_do_not_claim_scope_proof():
    assert example_ranges("条件（包括示例]") == []
    assert not crosses_example_scope("条件（包括示例）及示例", "示例", "条件")
    assert not crosses_example_scope("条件（包括示例）", "", "条件")
