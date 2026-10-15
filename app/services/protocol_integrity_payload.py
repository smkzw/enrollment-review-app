"""The exact input fingerprint shared by protocol publication and review."""
from app.domain.contracts.agents import GateResult
from app.domain.contracts.rules import (
    ProtocolAuthorityConfirmation, ProtocolAuthorityRecord,
    ProtocolIntegrityManifest, RuleSet, WorkflowStage,
)


def protocol_integrity_payload(
    rule_set: RuleSet, *, workflow_stages: list[WorkflowStage],
    manifest: ProtocolIntegrityManifest, authority_record: ProtocolAuthorityRecord,
    authority_confirmation: ProtocolAuthorityConfirmation,
    authority_gate_result: GateResult,
) -> dict:
    return {
        "rule_set": rule_set.model_dump(mode="json"),
        "workflow_stages": [item.model_dump(mode="json") for item in workflow_stages],
        "protocol_version": {
            "protocol_version_id": rule_set.protocol_version_id,
            "rule_set_revision": rule_set.revision,
        },
        "manifest": manifest.model_dump(mode="json"),
        "authority_record": authority_record.model_dump(mode="json"),
        "authority_confirmation": authority_confirmation.model_dump(mode="json"),
        "authority_gate_result": authority_gate_result.model_dump(mode="json"),
    }
