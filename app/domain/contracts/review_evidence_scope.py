"""Explicit snapshot lineage for the existing formal review chain."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .common import VersionedModel


class ReviewEvidenceScope(VersionedModel):
    schema_version: Literal["fixture/v1", "review/v2"] = "fixture/v1"
    evidence_snapshot_id: str | None = Field(default=None, min_length=1)
    evidence_snapshot_v2_id: str | None = Field(default=None, min_length=1)
    complete_processing_revision_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_evidence_lineage(self) -> "ReviewEvidenceScope":
        if self.schema_version == "fixture/v1":
            if self.evidence_snapshot_id is None or any((
                self.evidence_snapshot_v2_id,
                self.complete_processing_revision_id,
            )):
                raise ValueError("旧版审核必须且只能绑定旧版资料快照")
        elif (
            self.evidence_snapshot_id is not None
            or self.evidence_snapshot_v2_id is None
            or self.complete_processing_revision_id is None
        ):
            raise ValueError("新版审核必须同时绑定资料快照和完整处理修订，不得混用旧版资料")
        return self

    @model_serializer(mode="wrap")
    def serialize_evidence_lineage(self, handler):
        payload = handler(self)
        # Omit only the newly introduced absent fields; old null fields are signed.
        if self.schema_version == "fixture/v1":
            payload.pop("evidence_snapshot_v2_id", None)
            payload.pop("complete_processing_revision_id", None)
        return payload


class ReviewLocatedEvidenceScope(ReviewEvidenceScope):
    locator_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_locator_lineage(self) -> "ReviewLocatedEvidenceScope":
        if self.schema_version == "fixture/v1":
            if self.locator_ids is not None:
                raise ValueError("旧版审核不得携带新版原件定位")
        else:
            if self.locator_ids is None:
                raise ValueError("新版审核必须明确给出原件定位集合，可为空但不可省略")
            if any(not item.strip() for item in self.locator_ids) or len(
                set(self.locator_ids)
            ) != len(self.locator_ids):
                raise ValueError("审核原件定位不得为空或重复")
            if getattr(self, "evidence_span_ids", ()):
                raise ValueError("新版审核不得混入旧版证据片段")
        return self

    @model_serializer(mode="wrap")
    def serialize_located_evidence(self, handler):
        payload = super().serialize_evidence_lineage(handler)
        if self.schema_version == "fixture/v1":
            payload.pop("locator_ids", None)
        return payload
