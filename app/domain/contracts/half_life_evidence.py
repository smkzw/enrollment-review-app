"""An exact protocol-sourced duration, scoped to one declared time constraint."""
from decimal import Decimal
import re
from typing import Literal
from unicodedata import normalize

from pydantic import Field, model_validator

from .common import ContractModel


class HalfLifeEvidence(ContractModel):
    value: Decimal = Field(gt=0, allow_inf_nan=False)
    unit: Literal["minute", "hour", "day", "week"]
    source_span_id: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=1)
    applies_to_quote: str = Field(min_length=1)
    duration_quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_quoted_scope(self):
        if (not self.source_span_id.strip() or not self.source_excerpt.strip()
                or not self.applies_to_quote.strip() or self.applies_to_quote not in self.source_excerpt):
            raise ValueError("半衰期数值须保留原文及其中明确的适用对象，不从药名推测")
        if self.duration_quote not in self.source_excerpt:
            raise ValueError("半衰期数值与单位须逐字保留在所引原文中")
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*(分钟|小时|天|日|周|minutes?|mins?|hours?|hrs?|days?|weeks?|min|h|d|wk)\s*",
            normalize("NFKC", self.duration_quote), re.IGNORECASE,
        )
        units = {"分钟": "minute", "minute": "minute", "minutes": "minute", "min": "minute", "mins": "minute",
                 "小时": "hour", "hour": "hour", "hours": "hour", "hr": "hour", "hrs": "hour", "h": "hour",
                 "天": "day", "日": "day", "day": "day", "days": "day", "d": "day",
                 "周": "week", "week": "week", "weeks": "week", "wk": "week"}
        if (match is None or Decimal(match[1]) != self.value
                or units[match[2].lower()] != self.unit):
            raise ValueError("半衰期必须是原文明确的单一数值与单位，不能用范围端点或推测值代替")
        normalized_source = normalize("NFKC", self.source_excerpt)
        quoted = re.escape(normalize("NFKC", self.duration_quote).strip())
        claims = [part.strip() for part in re.split(r"[。！？；;\n]", normalized_source) if part.strip()]
        if (len(claims) != 1
                or len(re.findall(r"半衰期|half[ -]?life", normalized_source, re.IGNORECASE)) != 1
                or re.search(r"分别|各自|respectively", normalized_source, re.IGNORECASE)
                or self.applies_to_quote.strip() in self.duration_quote
                or re.fullmatch(r"半衰期|half[ -]?life", self.applies_to_quote.strip(), re.IGNORECASE)):
            raise ValueError("半衰期数值与适用对象须保留在同一明确陈述中，多对象或多段陈述暂不用于自动计算")
        cue = re.search(r"半衰期|half[ -]?life", normalized_source, re.IGNORECASE)
        subject_prefix = normalized_source[:cue.start()].strip()
        applies_to = normalize("NFKC", self.applies_to_quote).strip()
        if (not subject_prefix.startswith(applies_to)
                or subject_prefix[len(applies_to):].strip() not in {"", "的", "'s", "’s"}
                or re.search(r"和|与|及|以及|、|,|，|或|相比|对照|\b(?:and|or|compared|versus)\b",
                             subject_prefix[len(applies_to):], re.IGNORECASE)):
            raise ValueError("半衰期适用对象不明确，不能用同句中的对照或其他药物代替")
        occurrences = list(re.finditer(r"(?<![\d.])" + quoted + r"(?![\d.A-Za-z])", normalized_source))
        if (not re.search(r"半衰期|half[ -]?life", normalized_source, re.IGNORECASE)
                or len(occurrences) != 1):
            raise ValueError("半衰期时长须在摘录中唯一完整出现，不得截取数值")
        occurrence = occurrences[0]
        prefix, suffix = normalized_source[:occurrence.start()], normalized_source[occurrence.end():]
        if (normalized_source[cue.end():occurrence.start()].strip().lower() not in {"", "为", "是", "is", "=", ":", "为:", "是:"}
                or suffix.strip().strip("。.!！") != ""):
            raise ValueError("半衰期陈述含尚未结构化的限定内容，不能忽略适用人群、条件或范围后直接计算")
        if (re.search(r"(?:[<>≤≥~～—–-]|至|到|约|大于|小于|至少|最多|about|approximately|between|to)\s*$", prefix, re.IGNORECASE)
                or re.match(r"\s*(?:[~～—–-]|至|到|或(?:者|为)?|to\b|and\b)\s*\d", suffix, re.IGNORECASE)
                or re.match(r"\s*(?:左右|上下|以上|以下)", suffix)
                or re.search(r"平均|中位|\b(?:median|mean|typically|approximately|about)\b", normalized_source, re.IGNORECASE)):
            raise ValueError("范围或近似半衰期不能截取为精确时长，请保留原文并待核实")
        return self

    def mask_duration(self) -> str:
        """Hide only the duration token, not equal suffixes of other quantities."""
        matches = list(re.finditer(
            r"(?<![\d.．])" + re.escape(self.duration_quote.strip()) + r"(?![\d.A-Za-z．])",
            self.source_excerpt,
        ))
        if len(matches) != 1:
            raise ValueError("半衰期时长无法在原文中唯一定位")
        start, end = matches[0].span()
        return self.source_excerpt[:start] + " " * (end - start) + self.source_excerpt[end:]

    def in_days(self, multiplier: Decimal = Decimal(1)) -> Decimal:
        numerator, denominator = {"minute": (1, 1440), "hour": (1, 24),
                                  "day": (1, 1), "week": (7, 1)}[self.unit]
        return self.value * multiplier * Decimal(numerator) / Decimal(denominator)
