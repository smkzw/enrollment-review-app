"""Bind a completed product control job inside the protocol publication transaction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunResult
from app.agents.protocol_control_source_interpretation import normalize_source_excerpt
from app.domain.contracts.agent_io import ProtocolDeconstructionDraft, ProtocolDeconstructionInput
from app.domain.contracts.agents import GateResult
from app.domain.contracts.control_catalog_publication import (
    CONTROL_CATALOG_PUBLICATION_GATE_NAME, ControlCatalogPublication,
)
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.protocol_controls import (
    KnownRequiredProcedureTarget, ProtocolControlBatchDispositionHydrated,
    ProtocolControlSourceUnitRelation,
    ProtocolControlBatchPlan, ProtocolControlDiscoveryToDeepPlan,
    ProtocolSectionCoverageManifest,
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
    PROTOCOL_CONTROL_JOB_TYPE, STEP_CLOSURE, STEP_GATE,
    _validate_saved_source_review,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.control_catalog_repository import ControlCatalogPublicationRepository
from app.storage.models import EvidenceRequirementRecord, JobCheckpointRecord, JobRecord, JobStepRecord
from app.storage.repositories import (
    AppendRepository, GATE_RESULT_CONFIG, ScopeViolationError,
    ProtocolDraftRevisionRepository,
    _save_requirement_row, get_evidence_requirement, get_rule_set,
    save_expectation_templates,
)
from app.projections.control_evidence_requirements import shared_control_requirements
from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
from app.workflow.jobstore import JobStore


@dataclass(frozen=True)
class SourceCalculationGap:
    batch_number: int
    statement_index: int
    structure_unit_id: str
    source_span_ids: tuple[str, ...]
    source_quote: str
    linked_official_code: str | None
    review_decision: str | None
    unresolved_aspects: tuple[str, ...]


def source_calculation_gaps(
    store: JobStore, source_job_id: str,
) -> tuple[SourceCalculationGap, ...]:
    """Read source-bound calculation gaps from the frozen deep-review steps."""
    closure = store.get_last_checkpoint(source_job_id, STEP_CLOSURE)
    if closure is None:
        raise ScopeViolationError("补充审核要求缺少已冻结的来源分包")
    plan = ProtocolControlDiscoveryToDeepPlan.model_validate(closure[1]["deep_plan"])
    steps = closure[1].get("deep_step_ids")
    if not isinstance(steps, list) or len(steps) != len(plan.batches):
        raise ScopeViolationError("补充审核要求的逐批来源核对身份不完整")
    gaps = []
    for batch, entry in zip(plan.batches, steps, strict=True):
        if not isinstance(entry, Mapping) or entry.get("batch_id") != batch.batch_id:
            raise ScopeViolationError("补充审核要求的逐批来源核对身份不一致")
        step_id = entry.get("step_id")
        if not isinstance(step_id, str):
            raise ScopeViolationError("补充审核要求的逐批来源核对步骤缺失")
        checkpoint = store.get_last_checkpoint(source_job_id, step_id)
        if checkpoint is None:
            raise ScopeViolationError("补充审核要求的逐批来源核对尚未完成")
        run = ProtocolControlAgentRunResult.model_validate(checkpoint[1].get("run_result"))
        interpretation = run.source_interpretation
        if run.batch_id != batch.batch_id or interpretation is None:
            raise ScopeViolationError("补充审核要求的逐批来源解释与冻结分包不一致")
        units = {unit.structure_unit_id: unit for unit in batch.owned_units}
        reviews = ({item.statement_index: item for item in run.source_target_review.items}
                   if run.source_target_review is not None else {})
        official_codes = {item.official_code for item in batch.known_official_targets}
        for index, statement in enumerate(interpretation.statements):
            if "calculation_input" not in statement.decision_functions:
                continue
            review = reviews.get(index)
            if review is not None and review.decision == "not_current_control":
                try:
                    _validate_saved_source_review(batch, run)
                except ValueError as exc:
                    raise ScopeViolationError("非当前审核计算的来源核对记录无效") from exc
                if (set(statement.decision_functions) <= {"action", "calculation_input"}
                        and statement.eligibility_sequence == "after_eligibility_decision"
                        and not statement.unresolved and not review.unresolved_aspects):
                    continue
            unit = units.get(statement.structure_unit_id)
            source_parts = ([unit.excerpt, *unit.heading_path] if unit is not None else [])
            normalized = normalize_source_excerpt(statement.quoted_text)
            source_part = next((part for part in source_parts
                                if normalized and normalized in normalize_source_excerpt(part)), None)
            if source_part is None:
                raise ScopeViolationError("计算定义的原文摘录与冻结来源单元不一致")
            linked_code = (review.target_id if review is not None
                           and review.decision == "covered_by_official"
                           and review.target_id in official_codes else None)
            gaps.append(SourceCalculationGap(
                batch_number=batch.batch_number, statement_index=index,
                structure_unit_id=unit.structure_unit_id,
                source_span_ids=tuple(unit.source_span_ids),
                source_quote=(statement.quoted_text if statement.quoted_text in source_part
                              else source_part),
                linked_official_code=linked_code,
                review_decision=review.decision if review is not None else None,
                unresolved_aspects=tuple(sorted(set([
                    *statement.unresolved,
                    *(review.unresolved_aspects if review is not None else []),
                ]))),
            ))
    return tuple(gaps)


def _require_source_calculations_consumable(
    store: JobStore, source_job_id: str,
) -> None:
    """Textual rule coverage cannot certify a source-defined calculation."""
    gaps = source_calculation_gaps(store, source_job_id)
    if gaps:
        first = gaps[0]
        raise ScopeViolationError(
            "方案中的计算定义尚无可核验的正式求值方式，不能仅凭条款文字对应发布"
            f"（批次 {first.batch_number}，陈述 {first.statement_index}）"
        )


def _require_frozen_draft_revision(
    session: Session, payload: Mapping[str, object], draft: ProtocolDeconstructionDraft,
) -> None:
    revision_id = payload.get("draft_revision_id")
    content_sha256 = payload.get("draft_content_sha256")
    if not isinstance(revision_id, str) or not isinstance(content_sha256, str):
        raise ScopeViolationError("补充审核要求尚未绑定当前方案草稿修订")
    revision = ProtocolDraftRevisionRepository(session).get(revision_id)
    if (revision.content_sha256 != content_sha256
            or revision.content != draft
            or revision.content.draft_id != draft.draft_id
            or revision.content.draft_revision != draft.draft_revision):
        raise ScopeViolationError("补充审核要求对应旧版方案草稿，请重新整理后发布")


def prepare_control_catalog_publication(
    session: Session, *, source_job_id: str, source_checkpoint_id: str,
    source_input: ProtocolDeconstructionInput, source_spans: Mapping[str, ProtocolSourceSpan],
    draft: ProtocolDeconstructionDraft, rule_set: RuleSet,
    published_stages: Sequence[WorkflowStage], project_id: str, created_at: datetime,
) -> ControlCatalogPublication:
    """Read explicit completed identities; no latest selection, writes or model calls."""
    created_at = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
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
    if current is None or current[0] != source_checkpoint_id:
        raise ScopeViolationError("补充审核要求的整理结果已变化，请重新查看后发布")

    expected_source_input = source_input.model_dump(mode="json")
    expected_source_spans = {
        span_id: span.model_dump(mode="json")
        for span_id, span in source_spans.items()
    }
    if payload.get("source_input") != expected_source_input:
        raise ScopeViolationError("补充审核要求与当前方案解构输入不一致")
    if payload.get("source_spans") != expected_source_spans:
        raise ScopeViolationError("补充审核要求与当前方案原文定位不一致")
    if (
        draft.project_id != source_input.project_id
        or draft.protocol_version_id != source_input.protocol_version_id
        or draft.selected_phase != source_input.selected_phase
        or rule_set.protocol_version_id != source_input.protocol_version_id
        or rule_set.study_phase != source_input.selected_phase
    ):
        raise ScopeViolationError("补充审核要求与当前草稿、规则版本或研究期别不一致")
    _require_frozen_draft_revision(session, payload, draft)

    coverage_manifest = ProtocolSectionCoverageManifest.model_validate(
        payload["coverage_manifest"]
    )
    if (
        coverage_manifest.protocol_version_id != source_input.protocol_version_id
        or coverage_manifest.protocol_document_sha256
        != source_input.protocol_file_sha256
        or coverage_manifest.study_phase != source_input.selected_phase
        or coverage_manifest.snapshot_id != source_input.extraction_snapshot_id
        or payload.get("source_snapshot_id") != source_input.extraction_snapshot_id
    ):
        raise ScopeViolationError("补充审核要求的全文覆盖清单不属于当前方案版本")
    if (
        result.get("stage") != "gate"
        or result.get("gate_version") != CONTROL_PUBLICATION_GATE_VERSION
        or result.get("accepted") is not True
        or result.get("result_kind") != CANDIDATE_CONTROL_PACKAGE_RESULT_KIND
        or result.get("formal_catalog_status")
        != FORMAL_CATALOG_STATUS_NOT_MATERIALIZED
        or result.get("coverage_manifest_id") != coverage_manifest.manifest_id
    ):
        raise ScopeViolationError("补充审核要求的最终核对记录不完整或版本不一致")

    _require_source_calculations_consumable(JobStore(session), source_job_id)

    plan = ProtocolControlBatchPlan.model_validate(result["publication_plan"])
    batches = tuple(ProtocolControlBatchDispositionHydrated.model_validate(item)
                    for item in result["batch_dispositions"])
    expected_unit_ids = [unit.structure_unit_id for unit in coverage_manifest.units]
    if (
        plan.coverage_manifest_id != coverage_manifest.manifest_id
        or plan.protocol_version_id != source_input.protocol_version_id
        or plan.study_phase != source_input.selected_phase
        or set(plan.expected_structure_unit_ids) != set(expected_unit_ids)
    ):
        raise ScopeViolationError("补充审核要求的处置计划未覆盖当前方案全部结构单元")
    planned_batches = {batch.batch_id: batch for batch in plan.batches}
    hydrated_batches = {batch.batch_id: batch for batch in batches}
    if set(planned_batches) != set(hydrated_batches):
        raise ScopeViolationError("补充审核要求的已核对批次与处置计划不一致")
    for batch_id, hydrated in hydrated_batches.items():
        planned = planned_batches[batch_id]
        if (
            hydrated.coverage_manifest_id != coverage_manifest.manifest_id
            or hydrated.owned_structure_unit_ids
            != planned.owned_structure_unit_ids
            or hydrated.owned_source_span_ids != planned.owned_source_span_ids
        ):
            raise ScopeViolationError("补充审核要求的批次来源范围与处置计划不一致")
    candidate_ids = sorted(item.control_candidate_id for batch in batches for item in batch.candidates)
    if result.get("candidate_ids") != candidate_ids or result.get("publication_plan_id") != plan.plan_id:
        raise ScopeViolationError("补充审核要求保存的完整候选集合不一致")
    relations = [ProtocolControlSourceUnitRelation.model_validate(item)
                 for item in result.get("source_unit_relations", [])]
    units = {unit.structure_unit_id: unit for unit in coverage_manifest.units}
    if len({(item.source_structure_unit_id, item.source_statement_index) for item in relations}) != len(relations):
        raise ScopeViolationError("跨章节来源对应重复")
    for relation in relations:
        source = units.get(relation.source_structure_unit_id)
        target = units.get(relation.target_structure_unit_id)
        if (source is None or target is None
                or sorted(source.source_span_ids) != relation.source_span_ids
                or sorted(target.source_span_ids) != relation.target_span_ids
                or relation.target_candidate_id not in candidate_ids):
            raise ScopeViolationError("跨章节来源对应未绑定当前方案原文和候选")
    catalog = materialize_control_catalog(
        coverage_manifest=coverage_manifest,
        plan=plan, batch_dispositions=batches,
        rule_component_ids=[component.rule_component_id for rule in rule_set.rules for component in rule.components],
        source_unit_relations=relations,
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
