"""Read the product's published protocol chain for a new formal review."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.rules import RuleSet, WorkflowStage
from app.domain.contracts.review import ProtocolDocumentVersion
from app.domain.gates.integrity import assert_protocol_integrity
from app.domain.publication import canonical_hash
from app.domain.registry import _issue_trusted_registry
from app.services.protocol_integrity_payload import protocol_integrity_payload
from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
from app.projections.control_evidence_requirements import shared_control_requirements
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository
from app.storage.repositories import (
    AppendRepository, AUTHORITY_CONFIRMATION_CONFIG, AUTHORITY_RECORD_CONFIG,
    COMMAND_EVENT_CONFIG, GATE_RESULT_CONFIG, INTEGRITY_MANIFEST_CONFIG,
    InvalidReferenceError, PROTOCOL_DOC_CONFIG, SOURCE_RECORD_CONFIG,
    WORKFLOW_STAGE_CONFIG, get_rule_set, list_expectation_templates,
)


@dataclass(frozen=True)
class ReviewProtocolSource:
    rule_set: RuleSet
    workflow_stages: tuple[WorkflowStage, ...]
    integrity_gate: GateResult
    expectation_templates: tuple[EvidenceExpectationTemplate, ...]
    protocol_document: ProtocolDocumentVersion


def load_review_protocol_source(session: Session, authority: FactAuthority) -> ReviewProtocolSource:
    rule_set = get_rule_set(session, authority.rule_set_id, authority.rule_set_revision)
    protocol = AppendRepository(session, PROTOCOL_DOC_CONFIG).get(authority.protocol_version_id)
    gate_repository = AppendRepository(session, GATE_RESULT_CONFIG)
    gate = gate_repository.get(protocol.integrity_gate_result_id)
    if gate.gate_name != "protocol-integrity-gate" or gate.result != GateOutcome.ACCEPTED:
        raise InvalidReferenceError("方案修订未通过完整性核对，不能生成正式审核")
    manifest_repository = AppendRepository(session, INTEGRITY_MANIFEST_CONFIG)
    manifests = [
        item for ref in gate.input_entity_refs
        if (item := manifest_repository.get_or_none(ref)) is not None
    ]
    if len(manifests) != 1:
        raise InvalidReferenceError("方案发布记录没有绑定唯一的原始完整性清单")
    manifest = manifests[0]
    record = AppendRepository(session, AUTHORITY_RECORD_CONFIG).get(manifest.authority_record_id)
    confirmation = AppendRepository(session, AUTHORITY_CONFIRMATION_CONFIG).get(
        protocol.authority_confirmation_id
    )
    command = AppendRepository(session, COMMAND_EVENT_CONFIG).get(confirmation.command_id)
    authority_gate = gate_repository.get(protocol.authority_gate_result_id)
    stages_repository = AppendRepository(session, WORKFLOW_STAGE_CONFIG)
    stages = [stages_repository.get(item.workflow_stage_id)
              for item in record.official_workflow_stages]
    sources_repository = AppendRepository(session, SOURCE_RECORD_CONFIG)
    sources = [sources_repository.get(ref) for ref in manifest.source_refs]
    registry = _issue_trusted_registry(
        rule_sets=[rule_set], protocol_document_versions=[protocol],
        protocol_integrity_manifests=[manifest], protocol_authority_records=[record],
        protocol_authority_confirmations=[confirmation], service_command_events=[command],
        protocol_source_records=sources, workflow_stages=stages,
        gate_results=[authority_gate, gate],
    )
    assert_protocol_integrity(
        rule_set, workflow_stages=stages, protocol_version=protocol,
        manifest=manifest, authority_record=record, authority_confirmation=confirmation,
        authority_gate_result=authority_gate, registry=registry,
    )
    payload = protocol_integrity_payload(
        rule_set, workflow_stages=stages, manifest=manifest,
        authority_record=record, authority_confirmation=confirmation,
        authority_gate_result=authority_gate,
    )
    expected_refs = [
        protocol.protocol_version_id, record.authority_record_id,
        confirmation.confirmation_id, authority_gate.gate_result_id,
        manifest.manifest_id, rule_set.rule_set_id,
    ]
    if (
        gate.input_scope_hash != canonical_hash(payload)
        or gate.output_hash != canonical_hash(payload)
        or gate.input_entity_refs != expected_refs
        or gate.accepted_entity_refs != [manifest.manifest_id, rule_set.rule_set_id]
        or gate.input_revision_map != {rule_set.protocol_version_id: rule_set.revision}
    ):
        raise InvalidReferenceError("方案发布凭据与本次所用完整规则修订不一致")
    templates = list_expectation_templates(session, rule_set.rule_set_id, rule_set.revision)
    control_publication = ControlCatalogPublicationRepository(session).get_for_rule_set(
        rule_set.rule_set_id, rule_set.revision,
    )
    if control_publication is not None and (
        control_publication.project_id != authority.project_id
        or control_publication.protocol_version_id != authority.protocol_version_id
    ):
        raise InvalidReferenceError("补充要求不属于当前项目的方案修订")
    projected = project_evidence_expectation_templates(
        rule_set=rule_set, workflow_stages=stages,
        procedure_requirements=record.procedure_evidence_requirements,
        control_requirements=(
            shared_control_requirements(control_publication)
            if control_publication is not None else ()
        ),
        created_at=gate.created_at,
    )
    if sorted((item.template_id, item.projection_sha256) for item in templates) != sorted(
        (item.template_id, item.projection_sha256) for item in projected
    ):
        raise InvalidReferenceError("已保存的资料要求不完整或与发布方案不一致")
    return ReviewProtocolSource(rule_set, tuple(stages), gate, tuple(templates), protocol)
