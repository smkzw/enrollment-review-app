import pytest

from app.domain.page_normalization import fact_normalization_key, normalize_scalar


@pytest.mark.parametrize("raw", ["2025-08-15 9:46", "2025/8/15T09:46", "２０２５年８月１５日 ９：４６"])
def test_same_explicit_minute_timestamp_normalizes(raw):
    assert normalize_scalar(raw) == ("2025-08-15T09:46", None)


@pytest.mark.parametrize("raw", ["2025-02-30 09:46", "2025-08-15 25:00", "2025-08-15 09:60"])
def test_invalid_timestamp_is_not_accepted(raw):
    with pytest.raises(ValueError):
        normalize_scalar(raw)


def test_precision_timezone_and_observation_identity_are_not_collapsed():
    values = ["2025-08-15", "2025-08-15 09:46", "2025-08-15 09:46:00",
              "2025-08-15 09:46:00.0", "2025-08-15 09:46+08:00", "2025-08-15 09:47"]
    assert len({normalize_scalar(value)[0] for value in values}) == len(values)
    assert normalize_scalar("2025-08-15T09:46Z") == normalize_scalar("2025-08-15T09:46+00:00")
    a = {"target_text": "采样时间", "time_text": "2025-08-15 9:46"}
    b = {**a, "time_text": "2025/8/15T09:46"}
    assert fact_normalization_key("结果", "0", context=a) == fact_normalization_key("结果", "0", context=b)
    assert fact_normalization_key("结果", "0", context=a) != fact_normalization_key("结果", "0", context={**b, "target_text": "报告时间"})
