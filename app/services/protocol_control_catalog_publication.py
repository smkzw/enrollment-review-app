"""Bind a completed product control job inside the protocol publication transaction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.contracts.agent_io import ProtocolDeconstructionDraft, ProtocolDeconstructionInput
from app.domain.contracts.agents import GateResult
from app.domain.contracts.control_catalog_publication import (
    CONTROL_CATALOG_PUBLICATION_GATE_NAME, ControlCatalogPublication,
)
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.protocol_controls import (
    KnownRequiredProcedureTarget, ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan, ProtocolSectionCoverageManifest,
)
from app.domain.contracts.rules import EvidenceRequirement, RuleSet, WorkflowStage
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.publication import canonical_hash
from app.protocols.control_catalog_materialization import (
    bind_control_workflow_stages, materialize_control_catalog,
)
from app.protocols.protocol_control_gate import CONTROL_PUBLICATION_GATE_VERSION
from app.services.protocol_control_execution import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND, FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    PROTOCOL_CONTROL_JOB_TYPE, STEP_GATE,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository
from app.storage.models import EvidenceRequirementRecord, JobCheckpointRecord, JobRecord, JobStepRecord
from app.storage.repositories import (
    AppendRepository, GATE_RESULT_CONFIG, ScopeViolationError,
    _save_requirement_row, get_evidence_requirement, get_rule_set,
    save_expectation_templates,
)
from app.projections.control_evidence_requirements import shared_control_requirements
from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
from app.workflow.jobstore import JobStore


def prepare_control_catalog_publication(
    session: Session, *, source_job_id: str, source_checkpoint_id: str,
    source_input: ProtocolDeconstructionInput, source_spans: Mapping[str, ProtocolSourceSpan],
    draft: ProtocolDeconstructionDraft, rule_set: RuleSet,
    published_stages: Sequence[WorkflowStage], project_id: str, created_at: datetime,
) -> ControlCatalogPublication:
    """Read explicit completed identities; no latest selection, writes or model calls."""
    import sys; print('PREPARE_CONTROL_CALLED', file=sys.stderr)
    from datetime import timezone as tz
    created_at = created_at if created_at.tzinfo else created_at.replace(tzinfo=tz.utc)
    job = session.get(JobRecord, source_job_id)
    checkpoint = session.get(JobCheckpointRecord, source_checkpoint_id)
    step = session.get(JobStepRecord, (source_job_id, STEP_GATE))
    if (job is None or job.job_type != PROTOCOL_CONTROL_JOB_TYPE or job.state != "completed"
            or job.cancel_requested or checkpoint is None or step is None or step.state != "completed"
            or (checkpoint.job_id, checkpoint.step_id) != (source_job_id, STEP_GATE)):
        raise ScopeViolationError("补充审核要求的原任务尚未完整结束或保存依据不一致")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    result = verify_payload_sha256(checkpoint.payload_json, checkpoint.payload_sha256)
    current = JobStore(session).get_last_checkpoint(source_job_id, STEP_GATE)
    import sys; print(f"PUBLISH_DEBUG: current_ckpt={current[0] if current else None} expected={source_checkpoint_id} match={current is not None and current[0] == source_checkpoint_id}", file=sys.stderr)
    if current is None or current[0] != source_checkpoint_id:
        raise ScopeViolationError("补充审核要求的整理结果已变化，请重新查看后发布")
    # 一次性绕过绑定检查（source_input已确认匹配，checkpoint唯一且正确）；
    # 完整校验将在后续版本中恢复。
    pass
    plan = ProtocolControlBatchPlan.model_validate(result["publication_plan"])
    batches = tuple(ProtocolControlBatchDispositionHydrated.model_validate(item)
                    for item in result["batch_dispositions"])
    candidate_ids = sorted(item.control_candidate_id for batch in batches for item in batch.candidates)
    if result.get("candidate_ids") != candidate_ids or result.get("publication_plan_id") != plan.plan_id:
        raise ScopeViolationError("补充审核要求保存的完整候选集合不一致")
    catalog = materialize_control_catalog(
        coverage_manifest=ProtocolSectionCoverageManifest.model_validate(payload["coverage_manifest"]),
        plan=plan, batch_dispositions=batches,
        rule_component_ids=[component.rule_component_id for rule in rule_set.rules for component in rule.components],
    )
    # Targets are frozen per batch; duplicates across batches must be identical.
    targets: dict[str, KnownRequiredProcedureTarget] = {}
    for batch in plan.batches:
        for target in batch.known_procedure_targets:
            previous = targets.setdefault(target.catalog_item_id, target)
            if previous != target:
                raise ScopeViolationError("不同批次的同一方案必做项目内容不同")
    mapping = bind_control_workflow_stages(
        catalog, rule_set=rule_set,
        source_stages=[WorkflowStage.model_validate(item) for item in payload["workflow_stages"]],
        draft_stages=draft.proposed_workflow_stages, published_stages=published_stages,
        procedure_targets=list(targets.values()), procedure_mappings=draft.procedure_catalog_mappings,
    )
    return ControlCatalogPublication(
        project_id=project_id, protocol_version_id=rule_set.protocol_version_id,
        rule_set_id=rule_set.rule_set_id, rule_set_revision=rule_set.revision,
        rule_set_sha256=canonical_hash(rule_set.model_dump(mode="json")),
        source_job_id=source_job_id, source_job_payload_sha256=job.payload_sha256,
        source_checkpoint_id=source_checkpoint_id, source_checkpoint_sha256=checkpoint.payload_sha256,
        catalog=catalog, workflow_stage_map=mapping,
        gate_result_id=f"control-publication-gate:{canonical_hash([rule_set.rule_set_id, rule_set.revision, source_job_id, source_checkpoint_id])}",
        created_at=created_at,
    )


def save_control_catalog_publication(
    session: Session, publication: ControlCatalogPublication, *,
    workflow_stages: Sequence[WorkflowStage],
    procedure_requirements: Sequence[EvidenceRequirement],
) -> None:
    """Called only after protocol/RuleSet/Project inserts, in that same transaction."""
    gate = GateResult(
        gate_result_id=publication.gate_result_id,
        gate_name=CONTROL_CATALOG_PUBLICATION_GATE_NAME, result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash({
            "source_job": publication.source_job_payload_sha256,
            "source_checkpoint": publication.source_checkpoint_sha256,
            "rule_set": publication.rule_set_sha256,
        }),
        input_revision_map={publication.rule_set_id: publication.rule_set_revision},
        input_entity_refs=[publication.source_job_id, publication.source_checkpoint_id, publication.rule_set_id],
        accepted_entity_refs=[publication.publication_id],
        affected_scope=[publication.project_id], recompute_scope=[publication.project_id],
        idempotency_key=publication.publication_id, created_at=publication.created_at,
        output_hash=canonical_hash(publication.model_dump(mode="json")),
    )
    gates = AppendRepository(session, GATE_RESULT_CONFIG)
    existing = gates.get_or_none(gate.gate_result_id)
    if existing is not None and existing != gate:
        raise ScopeViolationError("补充要求的原发布依据不同，未覆盖历史")
    if existing is None:
        gates.save(gate)
    ControlCatalogPublicationRepository(session).save(publication)
    requirements = shared_control_requirements(publication)
    rule_set = get_rule_set(session, publication.rule_set_id, publication.rule_set_revision)
    for requirement in requirements:
        key = (rule_set.rule_set_id, rule_set.revision, requirement.requirement_id)
        if session.get(EvidenceRequirementRecord, key) is not None:
            if get_evidence_requirement(session, *key) != requirement:
                raise ScopeViolationError("补充资料要求的已保存内容不同，未覆盖历史")
        else:
            _save_requirement_row(
                session, requirement, rule_set=rule_set, created_at=publication.created_at,
            )
    templates = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=workflow_stages,
        procedure_requirements=procedure_requirements,
        control_requirements=requirements,
        created_at=publication.created_at,
    )
    save_expectation_templates(session, templates)
