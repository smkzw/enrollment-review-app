import pytest

from app.domain.page_normalization import normalize_scalar


@pytest.mark.parametrize("raw", ["NCS", "years", "未知年", "未知kg", "正常", "未检查ml"])
def test_text_is_not_split_as_numeric_unit(raw):
    assert normalize_scalar(raw) == (raw.lower(), None)


@pytest.mark.parametrize("raw", ["2026-02-30", "2026年13月", "2025/2/29"])
def test_invalid_calendar_dates_are_rejected(raw):
    with pytest.raises(ValueError):
        normalize_scalar(raw)


@pytest.mark.parametrize("raw,expected", [
    ("2024年2月29日", ("2024-02-29", None)),
    ("2026年9月", ("2026-09", None)),
    ("< 0.010 mmol/L", ("<0.01", "mmol/l")),
    ("4.20 x10^9/L", ("4.2", "×10^9/l")),
])
def test_scalar_grammar_preserves_precision_and_comparator(raw, expected):
    assert normalize_scalar(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("0 /μL", ("0", "/μl")),
    ("< 0.010 /µL", ("<0.01", "/μl")),
    ("4.20↑ /uL", ("4.2", "/μl")),
    ("4.20 /μL↓", ("4.2", "/μl")),
    ("1↑2 /μL", ("1↑2/μl", None)),
    ("未测 /μL", ("未测/μl", None)),
    ("4 /mL", ("4/ml", None)),
])
def test_per_microliter_requires_complete_number(raw, expected):
    assert normalize_scalar(raw) == expected


def test_v5_microliter_remains_frozen():
    from app.domain.page_normalization import normalize_scalar_v5
    assert normalize_scalar_v5("0 /μL") == ("0/μl", None)
