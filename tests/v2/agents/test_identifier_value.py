import pytest

from app.domain.contracts.identifier_value import validate_identifier_value


@pytest.mark.parametrize("raw,source", [
    ("120", "收缩压 120 mmHg。"),
    ("6.1", "血糖 6.1 mmol/L"),
    ("1.2e3", "结果 1.2e3"),
    ("98", "饱和度 98%"),
    ("１２０", "收缩压 １２０ mmHg"),
])
def test_measurement_cannot_bypass_units_as_identifier(raw, source):
    with pytest.raises(ValueError, match="标识编号"):
        validate_identifier_value(raw, raw, None, source)


@pytest.mark.parametrize("raw", ["0047", "A-0003", "84721"])
def test_identifier_is_preserved(raw):
    validate_identifier_value(raw, raw, None, "标识 " + raw)
