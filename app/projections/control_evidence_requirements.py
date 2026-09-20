"""Node-specific evidence requirements from one immutable control publication.

These describe evidence to look for, not applicability or eligibility findings.
Do not coerce them into legacy unconditional absence checks or derive examination
validity from an obligation's historical lookback window.

Legacy empty atom references stay explicit as unknown dependencies; a missing
source policy is still rejected because projecting it would invent restrictions.
"""
from __future__ import annotations

from pydantic import ConfigDict, Field, model_serializer

from app.domain.contracts.common import ContractModel
from app.domain.contracts.control_evidence_policy import ControlEvidenceSourcePolicy
from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.control_evidence_origin import ControlEvidenceOrigin
from app.domain.contracts.control_evidence_dependency import (
    ControlEvidenceAtomReference, validate_control_evidence_dependencies,
)
from app.domain.contracts.rules import EvidenceRequirement


class ControlEvidenceRequirement(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    publication_id: str = Field(min_length=1)
    protocol_control_id: str = Field(min_length=1)
    evidence_key: str = Field(min_length=1)
    source_workflow_stage_id: str = Field(min_length=1)
    workflow_stage_id: str = Field(min_length=1)
    due_stage: ReviewStage
    fact_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required_source_types: tuple[str, ...]
    source_span_ids: tuple[str, ...]
    source_policy: ControlEvidenceSourcePolicy
    atom_refs: tuple[ControlEvidenceAtomReference, ...] = ()

    @model_serializer(mode="wrap")
    def serialize_requirement(self, handler):
        data = handler(self)
        if not self.atom_refs:
            data.pop("atom_refs", None)
        return data


def project_control_evidence_requirements(
    publication: ControlCatalogPublication,
) -> tuple[ControlEvidenceRequirement, ...]:
    """Preserve every evidence origin and expand only explicit node bindings."""
    publication = ControlCatalogPublication.model_validate(
        publication.model_dump(mode="json"),
    )
    result = []
    identities: set[str] = set()
    for control in publication.catalog.controls:
        validate_control_evidence_dependencies(control, require_explicit=False)
        nodes = {node.workflow_stage_id: node for node in control.review_node_bindings}
        for evidence in control.minimum_evidence:
            if not evidence.workflow_stage_ids:
                raise ValueError("跨章资料要求尚未明确具体访视，不能生成当前核对要求")
            if evidence.source_policy is None:
                raise ValueError("跨章资料的来源要求尚未整理，不能套用默认来源要求")
            for source_node_id in evidence.workflow_stage_ids:
                node = nodes.get(source_node_id)
                target_id = publication.workflow_stage_map.get(source_node_id)
                if node is None or node.review_stage != evidence.due_stage or target_id is None:
                    raise ValueError("跨章资料要求与已发布控制的具体访视不一致")
                identity = ControlEvidenceOrigin(
                    publication_id=publication.publication_id,
                    protocol_control_id=control.protocol_control_id,
                    evidence_key=evidence.evidence_key,
                    workflow_stage_id=target_id,
                ).requirement_identity()
                if identity in identities:
                    raise ValueError("跨章资料要求的来源与访视身份重复")
                identities.add(identity)
                result.append(ControlEvidenceRequirement(
                    requirement_id=identity,
                    publication_id=publication.publication_id,
                    protocol_control_id=control.protocol_control_id,
                    evidence_key=evidence.evidence_key,
                    source_workflow_stage_id=source_node_id,
                    workflow_stage_id=target_id,
                    due_stage=evidence.due_stage,
                    fact_type=evidence.fact_type,
                    description=evidence.description,
                    required_source_types=tuple(evidence.required_source_types),
                    source_span_ids=tuple(evidence.source_policy.source_span_ids),
                    source_policy=evidence.source_policy,
                    atom_refs=tuple(evidence.atom_refs),
                ))
    return tuple(result)


def shared_control_requirements(
    publication: ControlCatalogPublication,
) -> tuple[EvidenceRequirement, ...]:
    """Project source restrictions without replacing unknowns with legacy defaults."""
    return tuple(
        EvidenceRequirement(
            requirement_id=item.requirement_id,
            control_origin=ControlEvidenceOrigin(
                publication_id=item.publication_id,
                protocol_control_id=item.protocol_control_id,
                evidence_key=item.evidence_key,
                workflow_stage_id=item.workflow_stage_id,
            ),
            fact_type=item.fact_type,
            required_source_types=list(item.required_source_types),
            allows_screening_record_transcription=(
                item.source_policy.allows_screening_record_transcription
            ),
            requires_contemporaneous_objective_source=(
                item.source_policy.requires_contemporaneous_objective_source
            ),
            due_stage=item.due_stage,
            description=item.description,
            control_validity_status=item.source_policy.result_validity_status,
            control_validity_constraint=item.source_policy.result_validity_constraint,
        )
        for item in project_control_evidence_requirements(publication)
    )
