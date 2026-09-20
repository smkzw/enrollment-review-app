"""Source-bound identity for a lossless, explicitly selected reading view."""
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel


class ReadingViewBinding(ContractModel):
    version: Literal["reading-view/quarter-turn/v1"]
    coordinate_space: Literal["page_image_pixels"]
    source_page_artifact_id: str = Field(min_length=1)
    source_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_width: int = Field(gt=0, strict=True)
    source_height: int = Field(gt=0, strict=True)
    clockwise_degrees: Literal[90, 180, 270]
    view_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    view_width: int = Field(gt=0, strict=True)
    view_height: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def check_dimensions(self):
        expected = ((self.source_height, self.source_width)
                    if self.clockwise_degrees in (90, 270)
                    else (self.source_width, self.source_height))
        if (self.view_width, self.view_height) != expected:
            raise ValueError("阅读视图尺寸与原页及方向不一致")
        return self
