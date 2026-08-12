from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import DatePrecision, ErrorCode


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionedModel(ContractModel):
    schema_version: Literal["fixture/v1"] = "fixture/v1"


class RevisionedModel(VersionedModel):
    revision: int = Field(default=1, ge=1)


class DateValue(ContractModel):
    value: date | None = None
    precision: DatePrecision
    source_text: str | None = None

    @model_validator(mode="after")
    def validate_precision(self) -> "DateValue":
        if self.precision != DatePrecision.UNKNOWN and self.value is None:
            raise ValueError("已知日期精度必须提供规范化日期值")
        return self


class AuditStamp(ContractModel):
    created_at: datetime
    created_by: str = Field(min_length=1)


class ErrorDetail(ContractModel):
    code: ErrorCode
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    recovery_action: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class ErrorEnvelope(VersionedModel):
    error: ErrorDetail


ScalarValue = str | int | float | bool
