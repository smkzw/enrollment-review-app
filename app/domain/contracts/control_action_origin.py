"""A second source kind for the existing action lifecycle, not a second workflow."""
from pydantic import Field, model_validator

from .common import ContractModel
from .protocol_controls import ControlObligationModality


class ControlActionOrigin(ContractModel):
    review_run_id: str = Field(min_length=1)
    protocol_control_id: str = Field(min_length=1)
    obligation_id: str | None = Field(default=None, min_length=1)
    obligation_group_id: str | None = Field(default=None, min_length=1)
    modality: ControlObligationModality

    @model_validator(mode="after")
    def validate_target(self):
        if (self.obligation_id is None) == (self.obligation_group_id is None):
            raise ValueError("办理事项须明确对应一项要求或一组适用条件")
        return self

    @property
    def target_id(self) -> str:
        return self.obligation_id or self.obligation_group_id
