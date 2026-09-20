"""Content fidelity checks for existing written-judgment facts, not IE decisions."""
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel

JUDGMENT_CONTENT_VERSION = "judgment-content/v1"
Check = Literal["supported", "rejected", "unresolved"]


class JudgmentContentCheck(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    explicit_written_judgment: Check
    investigator_attribution: Check
    target_correspondence: Check
    node_correspondence: Check
    encoded_value_fidelity: Check
    quoted_evidence: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    unresolved_reasons: list[str]

    def agreement_key(self) -> tuple[str, ...]:
        return (self.explicit_written_judgment, self.investigator_attribution,
                self.target_correspondence, self.node_correspondence, self.encoded_value_fidelity)

    @model_validator(mode="after")
    def validate_explanation(self):
        if not self.quoted_evidence.strip() or not self.explanation.strip():
            raise ValueError("书面判断核实须保留原文与具体说明")
        if any(not item.strip() for item in self.unresolved_reasons):
            raise ValueError("未核实原因不能为空")
        if any(value != "supported" for value in self.agreement_key()) and not self.unresolved_reasons:
            raise ValueError("判断内容未确认时须说明具体原因")
        if all(value == "supported" for value in self.agreement_key()) and self.unresolved_reasons:
            raise ValueError("仍有未核实原因时不得将全部项目标为已支持")
        return self


class JudgmentContentPayload(ContractModel):
    results: list[JudgmentContentCheck]

    @model_validator(mode="after")
    def unique_pairs(self):
        ids = [item.pair_id for item in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("同一书面判断配对不得重复核实")
        return self
