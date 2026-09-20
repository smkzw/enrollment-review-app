"""来源政策合同：表达证据来源类型、核实状态和覆盖范围。

WP02核心：将"已核实"从"必须两个主读一致"中解耦。每种来源类型
（native/ocr/single_visual/targeted_verification/manual）有明确的
可信度和核实要求，不再是隐式的双道一致性检查。
"""
from __future__ import annotations

from enum import Enum
from typing import Sequence

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel


class SourcePolicyKind(str, Enum):
    """证据来源类型：决定可信度等级和核实要求。"""

    NATIVE_TEXT = "native_text"
    OCR_PRIMARY = "ocr_primary"
    SINGLE_VISUAL = "single_visual"
    TARGETED_VERIFICATION = "targeted_verification"
    MANUAL_CORRECTION = "manual_correction"


class VerificationStatus(str, Enum):
    """单条观察的核实状态。"""

    UNVERIFIED = "unverified"
    SELF_CONSISTENT = "self_consistent"
    CROSS_VERIFIED = "cross_verified"
    TARGETED_VERIFIED = "targeted_verified"
    MANUAL_CONFIRMED = "manual_confirmed"
    UNREADABLE = "unreadable"


class SourcePolicy(ContractModel):
    """单条观察的来源政策：来源类型+核实状态+覆盖声明。

    ``source_policy_version`` 追踪合同版本，允许旧记录保持旧语义。
    """

    source_policy_version: str = Field(default="source-policy/v1")
    kind: SourcePolicyKind
    verification: VerificationStatus
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    locator_ids: list[str] = Field(default_factory=list)
    coverage_declared: bool = Field(
        default=False,
        description="True=该页/区域已做覆盖检查（非仅OCR产出了文本）",
    )
    readable: bool = Field(default=True)
    unreadable_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_policy(self) -> "SourcePolicy":
        if self.verification == VerificationStatus.UNREADABLE and self.readable:
            raise ValueError("UNREADABLE来源不可声明为readable")
        if self.verification in (
            VerificationStatus.CROSS_VERIFIED,
            VerificationStatus.TARGETED_VERIFIED,
        ) and not self.locator_ids:
            raise ValueError("交叉/定向核实必须引用来源定位")
        return self

    @property
    def is_verified(self) -> bool:
        """是否经过独立核实（不限于双道一致）。"""
        return self.verification in (
            VerificationStatus.CROSS_VERIFIED,
            VerificationStatus.TARGETED_VERIFIED,
            VerificationStatus.MANUAL_CONFIRMED,
        )

    @property
    def trust_level(self) -> int:
        """可信度排序：manual > cross > targeted > self > unverified。"""
        _ORDER = {
            VerificationStatus.MANUAL_CONFIRMED: 5,
            VerificationStatus.CROSS_VERIFIED: 4,
            VerificationStatus.TARGETED_VERIFIED: 3,
            VerificationStatus.SELF_CONSISTENT: 2,
            VerificationStatus.UNVERIFIED: 1,
            VerificationStatus.UNREADABLE: 0,
        }
        return _ORDER.get(self.verification, 0)


class ObservationRecord(ContractModel):
    """单条原件观察：原文字面值和上下文，独立于后续核实或规范化。"""

    observation_id: str = Field(min_length=1)
    label_raw: str = Field(min_length=1)
    value_raw: str
    unit_raw: str | None = None
    reference_range_raw: str | None = None
    polarity: str = Field(default="affirmed")
    modality: str = Field(default="printed")
    object_raw: str | None = None
    date_raw: str | None = None
    date_kind: str = Field(default="unknown")
    locator_id: str = Field(min_length=1)
    readable: bool = Field(default=True)
    unreadable_fields: list[str] = Field(default_factory=list)


class VerificationRecord(ContractModel):
    """核实记录：谁核对了什么、怎么核对的、结果如何。"""

    observation_id: str = Field(min_length=1)
    method: SourcePolicyKind
    verification: VerificationStatus
    reader_model: str | None = None
    reader_lane: str | None = None
    agreed_with: str | None = Field(
        default=None,
        description="另一道的observation_id（仅交叉核实时填写）",
    )
    source_locator_id: str = Field(min_length=1)
    result: str = Field(min_length=1)
