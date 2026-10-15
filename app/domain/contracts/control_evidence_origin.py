"""Exact published origin of a node-specific supplementary evidence requirement."""
from pydantic import Field

from .common import ContractModel


class ControlEvidenceOrigin(ContractModel):
    publication_id: str = Field(min_length=1)
    protocol_control_id: str = Field(min_length=1)
    evidence_key: str = Field(min_length=1)
    workflow_stage_id: str = Field(min_length=1)

    def requirement_identity(self) -> str:
        from app.domain.publication import canonical_hash

        return "control-evidence:" + canonical_hash({
            "version": "control-evidence/v1", **self.model_dump(mode="json"),
        })

    def resolve(self, publication):
        """Resolve an exact published source, not clinical applicability."""
        if publication is None or publication.publication_id != self.publication_id:
            raise ValueError("补充资料要求缺少对应的冻结发布来源")
        control = next((item for item in publication.catalog.controls
                        if item.protocol_control_id == self.protocol_control_id), None)
        evidence = next((item for item in control.minimum_evidence
                         if item.evidence_key == self.evidence_key), None) if control else None
        if evidence is None or evidence.source_policy is None:
            raise ValueError("补充资料要求不在冻结目录中或缺少来源政策")
        nodes = {item.workflow_stage_id: item for item in control.review_node_bindings}
        if not any(
            publication.workflow_stage_map.get(source_id) == self.workflow_stage_id
            and source_id in nodes and nodes[source_id].review_stage == evidence.due_stage
            for source_id in evidence.workflow_stage_ids
        ):
            raise ValueError("补充资料要求不属于指定的冻结访视")
        return evidence
