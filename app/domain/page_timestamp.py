"""Normalize explicit timestamps without inventing precision or time zones."""

import re
import unicodedata
from datetime import datetime

_TIMESTAMP = re.compile(
    r"^(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})日?[Tt\s]+"
    r"(\d{1,2}):(\d{2})(?::(\d{2})(\.\d{1,6})?)?"
    r"([Zz]|[+-]\d{2}:\d{2})?$"
)


def normalize_timestamp(value: object) -> str | None:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    match = _TIMESTAMP.fullmatch(text)
    if match is None:
        return None
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    canonical = f"{int(year):04d}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}"
    if second is not None:
        canonical += ":" + second + (fraction or "")
    if zone:
        canonical += "+00:00" if zone.upper() == "Z" else zone
    datetime.fromisoformat(canonical)
    return canonical
