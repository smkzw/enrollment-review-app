"""Literal intraday durations, without interpreting their clinical scope."""

from __future__ import annotations

import re
import unicodedata


_QUANTITY = (
    r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万半]+"
    r"(?:点[零〇一二三四五六七八九]+)?|one|two|three|four|five|six|seven|"
    r"eight|nine|ten|half|an?)"
)
_INTRADAY_DURATION = re.compile(
    rf"(?<![A-Za-z]){_QUANTITY}\s*[-－]?\s*"
    r"(?:小时|钟头|分钟|hours?|hrs?|h|minutes?|mins?)(?![A-Za-z])",
    re.IGNORECASE,
)


def intraday_time_fragments(text: str) -> list[str]:
    """Return normalized literal fragments; absence is not proof of completeness."""

    source = unicodedata.normalize("NFKC", text)
    titles = list(re.finditer(r"《[^》]*》", source))
    return sorted({
        re.sub(r"\s+", "", match.group())
        for match in _INTRADAY_DURATION.finditer(source)
        if not any(title.start() <= match.start() < title.end() for title in titles)
    })
