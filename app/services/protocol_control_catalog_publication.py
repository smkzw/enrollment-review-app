"""Bind a completed product control job inside the protocol publication transaction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunResult
from app.agents.protocol_control_source_interpretation import (
    is_post_eligibility_calculation, normalize_source_excerpt, source_definition_statement_indexes,
)
from app.domain.contracts.agent_io import ProtocolDeconstructionDraft, ProtocolDeconstructionInput
from app.domain.contracts.agents import GateResult
from app.domain.contracts.control_catalog_publication import (
    CONTROL_CATALOG_PUBLICATION_GATE_NAME, ControlCatalogPublication,
)
from app.domain.contracts.enums import GateOutcome
from app.domain.contracts.protocol_controls import (
    KnownRequiredProcedureTarget, ProtocolControlBatchDispositionHydrated,
    ProtocolControlDefinitionConsumerRecord,
    ProtocolControlSourceUnitRelation,
    ProtocolControlBatchPlan, ProtocolControlDiscoveryToDeepPlan,
    ProtocolSectionCoverageManifest,
)
from app.domain.contracts.rules import (
    EvidenceRequirement, RuleSet, WorkflowStage, iter_atomic_predicates,
)
from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
from app.domain.publication import canonical_hash
from app.protocols.control_catalog_materialization import (
    bind_control_workflow_stages, materialize_control_catalog,
)
from app.protocols.protocol_control_gate import CONTROL_PUBLICATION_GATE_VERSION
from app.services.protocol_control_execution import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND, FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    PROTOCOL_CONTROL_JOB_TYPE, STEP_CLOSURE, STEP_GATE,
    PROTOCOL_CONTROL_EXECUTION_VERSION, STEP_SCOPE, ProtocolControlExecutorConfig,
    _verified_definition_scope,
    _definition_consumer_atom,
    _validate_saved_source_review,
)
from app.storage.codecs import verify_payload_sha256
from app.storage.config import DB_FILENAME, resolve_data_paths
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
from app.workflow.runner import StepContext
from app.workflow.errors import StepFailure


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
    batch_id: str = ""


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
        definition_indexes = set(source_definition_statement_indexes(interpretation))
        for index, statement in enumerate(interpretation.statements):
            if index not in definition_indexes:
                continue
            review = reviews.get(index)
            if review is not None and review.decision == "not_current_control":
                try:
                    _validate_saved_source_review(batch, run)
                except ValueError as exc:
                    raise ScopeViolationError("非当前审核计算的来源核对记录无效") from exc
                if is_post_eligibility_calculation(statement, review):
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
                batch_id=batch.batch_id,
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


def _definition_consumer_official_predicate(
    rule_set: RuleSet, consumer,
) -> list[str]:
    """Prove a declared official consumer against the frozen RuleSet.

    The declared ``(rule_component_id, predicate_id)`` must resolve to one
    frozen ``AtomicPredicate`` of the current RuleSet, and the consumer excerpt
    must occur in that predicate's own exact source clauses. A parent IN/EX code
    is never accepted as the consumer identity, and wording similarity is never
    used as proof.
    """

    for rule in rule_set.rules:
        for component in rule.components:
            if component.rule_component_id != consumer.rule_component_id:
                continue
            predicates = [
                predicate
                for expression in (component.expression, component.exception_expression,
                                   *(item.expression for item in component.repeat_trigger_conditions))
                if expression is not None
                for predicate in iter_atomic_predicates(expression)
            ]
            for predicate in predicates:
                if predicate.predicate_id == consumer.predicate_id:
                    return list(predicate.exact_source_clauses)
    raise ValueError("官方条件消费未绑定当前冻结规则条件")


def _require_valid_source_definition_consumers(
    result: Mapping[str, object],
    plan: ProtocolControlBatchPlan,
    batches: Sequence[ProtocolControlBatchDispositionHydrated],
    coverage_manifest: ProtocolSectionCoverageManifest,
    rule_set: RuleSet,
) -> list[ProtocolControlDefinitionConsumerRecord]:
    """Re-verify saved definition→consumer records against the frozen inputs.

    A stored record is never trusted by itself. The definition anchor (quote and
    span set) is re-checked against the frozen coverage manifest, and each
    consumer anchor is re-checked against that consumer's own declared excerpts
    in the frozen input: a hydrated control candidate atom by position, an
    official predicate by its content-derived identity in the frozen RuleSet.
    The two anchors are independent: a definition in a calculation/method
    chapter links to a consumer excerpted elsewhere without either side
    containing the other. Any mismatch rejects publication. The records are
    identity-bound evidence for the definition block; they release it only per
    definition whose consumer scope is proven complete, and the same records
    must then mark those consumers unresolved in the working draft.
    """

    raw = result.get("source_definition_consumers", [])
    if not isinstance(raw, list):
        raise ScopeViolationError("来源定义消费关系保存格式无效")
    records = [ProtocolControlDefinitionConsumerRecord.model_validate(item) for item in raw]
    if len({(item.batch_id, item.source_statement_index) for item in records}) != len(records):
        raise ScopeViolationError("来源定义消费关系重复")
    units = {unit.structure_unit_id: unit for unit in coverage_manifest.units}
    batch_ids = {batch.batch_id for batch in plan.batches}
    candidate_by_id = {
        candidate.control_candidate_id: candidate
        for batch in batches for candidate in batch.candidates
    }
    for record in records:
        unit = units.get(record.source_structure_unit_id)
        quote = normalize_source_excerpt(record.source_quote)
        if (record.batch_id not in batch_ids or unit is None
                or sorted(unit.source_span_ids) != sorted(record.source_span_ids)
                or not quote
                or not any(quote in normalize_source_excerpt(part)
                           for part in [unit.excerpt, *unit.heading_path])):
            raise ScopeViolationError("来源定义消费关系未绑定当前冻结定义与原文")
        for consumer in record.consumers:
            if consumer.consumer_kind == "official_predicate":
                try:
                    excerpts = _definition_consumer_official_predicate(rule_set, consumer)
                except ValueError as exc:
                    raise ScopeViolationError("来源定义消费条件未绑定冻结规则条件") from exc
            else:
                candidate = candidate_by_id.get(consumer.control_candidate_id)
                if candidate is None:
                    raise ScopeViolationError("来源定义消费原子引用了非冻结候选")
                try:
                    _, excerpts = _definition_consumer_atom(candidate, consumer)
                except ValueError as exc:
                    raise ScopeViolationError("来源定义消费原子未绑定冻结候选原子") from exc
            consumer_excerpt = normalize_source_excerpt(consumer.consumer_excerpt)
            if not consumer_excerpt or not any(
                consumer_excerpt in normalize_source_excerpt(value) for value in excerpts
            ):
                raise ScopeViolationError("消费来源摘录不在该消费者自身声明的冻结原文中")
    return records


def _released_definition_keys(
    records: Sequence[ProtocolControlDefinitionConsumerRecord],
    plan: ProtocolControlBatchPlan,
) -> frozenset[tuple[int, int]]:
    """Definitions whose saved relation may release the calculation block.

    Release is per definition and requires a stored, nonempty, completely
    scoped consumer set without untyped unresolved reasons. An old job has no
    records and releases nothing.
    """

    number_by_batch = {batch.batch_id: batch.batch_number for batch in plan.batches}
    return frozenset(
        (number_by_batch[record.batch_id], record.source_statement_index)
        for record in records
        if record.scope_complete and record.consumers and not record.unresolved_reasons
        and record.batch_id in number_by_batch
    )


def _verified_calculation_release(
    result: Mapping[str, object], plan: ProtocolControlBatchPlan,
    batches: Sequence[ProtocolControlBatchDispositionHydrated],
    coverage_manifest: ProtocolSectionCoverageManifest, rule_set: RuleSet,
    gaps: Sequence[SourceCalculationGap],
) -> frozenset[tuple[int, int]]:
    """Use the same frozen anchors to preview and to publish a release."""
    records = _require_valid_source_definition_consumers(
        result, plan, batches, coverage_manifest, rule_set,
    )
    return _calculation_release_for_records(records, plan, gaps)


def _calculation_release_for_records(
    records: Sequence[ProtocolControlDefinitionConsumerRecord],
    plan: ProtocolControlBatchPlan,
    gaps: Sequence[SourceCalculationGap],
) -> frozenset[tuple[int, int]]:
    """Match already source-verified records to their exact calculation gaps."""
    number_by_batch = {batch.batch_id: batch.batch_number for batch in plan.batches}
    gap_keys = {(gap.batch_number, gap.statement_index) for gap in gaps}
    if len(gap_keys) != len(gaps):
        raise ScopeViolationError("计算定义来源清单存在重复")
    released: set[tuple[int, int]] = set()
    for record in records:
        if not (record.scope_complete and record.consumers and not record.unresolved_reasons):
            continue
        matches = [gap for gap in gaps
                   if gap.statement_index == record.source_statement_index
                   and (gap.batch_id == record.batch_id if gap.batch_id
                        else gap.batch_number == number_by_batch[record.batch_id])]
        if len(matches) != 1:
            raise ScopeViolationError("计算定义消费关系与逐批原文缺口不一致")
        gap = matches[0]
        if (record.source_structure_unit_id != gap.structure_unit_id
                or set(record.source_span_ids) != set(gap.source_span_ids)
                or normalize_source_excerpt(record.source_quote)
                not in normalize_source_excerpt(gap.source_quote)):
            raise ScopeViolationError("计算定义消费关系与逐批原文缺口不一致")
        released.add((gap.batch_number, gap.statement_index))
    return frozenset(released)


def _require_source_calculations_consumable(
    store: JobStore, source_job_id: str, *,
    released: frozenset[tuple[int, int]] = frozenset(),
) -> None:
    """A source-defined calculation still needs its own proven consumer relation.

    The block is narrowed per definition only after its saved affected scope
    is verified and all affected consumers are carried into the working-draft
    unknown set. No record, empty consumers, unproven cross-batch scope, or a
    pre-contract job keeps the original hard block.
    """
    gaps = source_calculation_gaps(store, source_job_id)
    blocking = [
        gap for gap in gaps
        if (gap.batch_number, gap.statement_index) not in released
    ]
    if blocking:
        first = blocking[0]
        raise ScopeViolationError(
            "方案定义尚未核清影响范围与对应要求，不能仅凭条款文字对应发布"
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


def require_saved_definition_scope(
    session: Session, *, source_job_id: str,
    payload: Mapping[str, object], result: Mapping[str, object],
) -> None:
    """Read the original scope proof again in the caller's transaction; never run a model."""
    found = JobStore(session).get_last_checkpoint(source_job_id, STEP_SCOPE)
    records = result.get("source_definition_consumers", [])
    if found is None:
        if records:
            raise ScopeViolationError("定义对应的核对记录缺失，不能仅凭整理后的关系用于发布")
        # Legacy packages without records cannot release a calculation gap.
        return
    step = session.get(JobStepRecord, (source_job_id, STEP_SCOPE))
    checkpoint_id, checkpoint = found
    if (step is None or step.state != "completed"
            or checkpoint.get("stage") != STEP_SCOPE
            or checkpoint.get("attempt") != step.attempt
            or checkpoint.get("source_definition_consumers") != records):
        raise ScopeViolationError("定义对应关系与本次已完成核对记录不一致")
    database = session.get_bind().engine.url.database
    if not database or Path(database).name != DB_FILENAME:
        raise ScopeViolationError("定义原始核对资料未绑定当前数据目录")

    @contextmanager
    def current_session():
        yield session

    config = ProtocolControlExecutorConfig(
        data_paths=resolve_data_paths(str(Path(database).resolve().parent)),
        session_factory=current_session,
    )
    context = StepContext(
        job_id=source_job_id, job_type=PROTOCOL_CONTROL_JOB_TYPE,
        job_payload=dict(payload), step_id=STEP_SCOPE, name="核对定义来源",
        attempt=step.attempt, last_checkpoint_id=checkpoint_id, last_checkpoint=checkpoint,
    )
    try:
        _verified_definition_scope(context, config, checkpoint=checkpoint)
    except (StepFailure, ValueError, TypeError, KeyError) as exc:
        raise ScopeViolationError("定义作用范围的原始核对依据未通过保存内容复核") from exc


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
    if payload.get("execution_version") != PROTOCOL_CONTROL_EXECUTION_VERSION:
        raise ScopeViolationError("补充审核要求使用较早的整理版本，不能作为当前发布依据")
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
    require_saved_definition_scope(session, source_job_id=source_job_id, payload=payload, result=result)
    definition_consumers = _require_valid_source_definition_consumers(
        result, plan, batches, coverage_manifest, rule_set,
    )
    released = _calculation_release_for_records(
        definition_consumers, plan,
        source_calculation_gaps(JobStore(session), source_job_id),
    )
    # The block is narrowed per definition only after that definition's saved
    # relation has been re-verified above; an old job carries no records and
    # therefore keeps the unconditional block.
    _require_source_calculations_consumable(
        JobStore(session), source_job_id,
        released=released,
    )
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
        schema_version=(
            "control-catalog/v3" if catalog.restricted_statements else
            "control-catalog/v2" if definition_consumers else "control-catalog/v1"
        ),
        project_id=project_id, protocol_version_id=rule_set.protocol_version_id,
        rule_set_id=rule_set.rule_set_id, rule_set_revision=rule_set.revision,
        rule_set_sha256=canonical_hash(rule_set.model_dump(mode="json")),
        source_job_id=source_job_id, source_job_payload_sha256=job.payload_sha256,
        source_checkpoint_id=source_checkpoint_id, source_checkpoint_sha256=checkpoint.payload_sha256,
        catalog=catalog, workflow_stage_map=mapping,
        definition_consumer_records=definition_consumers,
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
