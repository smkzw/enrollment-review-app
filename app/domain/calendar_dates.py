"""Calendar operations shared by event conditions and source validity."""
from calendar import monthrange
from datetime import date, timedelta

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision
from app.domain.contracts.rules import TimeQuantity, TimeUnit


def shift_date(value: date, quantity: TimeQuantity, *, sign: int = 1) -> date:
    amount = sign * quantity.value
    if quantity.unit == TimeUnit.DAY:
        return value + timedelta(days=amount)
    if quantity.unit == TimeUnit.WEEK:
        return value + timedelta(days=amount * 7)
    if quantity.unit == TimeUnit.MONTH:
        year, month_index = divmod(value.year * 12 + value.month - 1 + amount, 12)
        month = month_index + 1
        return date(year, month, min(value.day, monthrange(year, month)[1]))
    if quantity.unit == TimeUnit.YEAR:
        year = value.year + amount
        return date(year, value.month, min(value.day, monthrange(year, value.month)[1]))
    raise ValueError(f"不支持的时间单位: {quantity.unit}")


def date_bounds(value: DateValue, *, allow_partial: bool) -> tuple[date, date] | None:
    if value.value is None:
        return None
    if value.precision == DatePrecision.DAY:
        return value.value, value.value
    if not allow_partial or value.precision == DatePrecision.UNKNOWN:
        return None
    if value.precision == DatePrecision.MONTH:
        return value.value.replace(day=1), value.value.replace(
            day=monthrange(value.value.year, value.value.month)[1]
        )
    if value.precision == DatePrecision.YEAR:
        return date(value.value.year, 1, 1), date(value.value.year, 12, 31)
    return None
