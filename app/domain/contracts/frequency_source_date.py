"""Source-written calendar components shared by counting scopes and evidence."""
from datetime import date

from pydantic import Field, StrictInt, model_validator

from .common import ContractModel


class FrequencySourceDate(ContractModel):
    year: StrictInt = Field(ge=1, le=9999)
    month: StrictInt | None = Field(default=None, ge=1, le=12)
    day: StrictInt | None = Field(default=None, ge=1, le=31)
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_date(self):
        if self.day is not None and self.month is None:
            raise ValueError("原文未记月份时不能补入日期")
        date(self.year, self.month or 1, self.day or 1)
        if not self.excerpt.strip():
            raise ValueError("计数期间日期须有逐字依据")
        return self
