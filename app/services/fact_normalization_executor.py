"""证据规范化持久任务执行器。

模型调用只在事务外形成结构化候选；候选、门禁、运行状态与任务检查点由
``PreparedStepResult`` 在同一租约写栅栏事务中提交。步骤检查点缺失而已有
同身份成功调用时，从持久记录重建并复核检查点直接复用，不重复调用模型。
执行器不得制造替代文本，不得把读取失败转成成功，也不得在失租结果被丢弃
前先提交临床领域副作用。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
import logging
from app.evidence.artifacts import ArtifactStore
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    EvidenceNormalizerInput,
    EvidenceNormalizerOutput,
    EvidenceNormalizerRunner,
    EvidenceNormalizerTransport,
    evidence_normalizer_prompt_template_sha256,
    validate_evidence_normalizer_model_config,
    validate_evidence_normalizer_output,
)
from app.agents.deepseek_evidence_normalizer_transport import (
    evidence_normalizer_transport_from_model_config,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.evidence_normalizer import (
    PersistedEvidenceNormalizerUnresolvedItem,
)
from app.domain.contracts.evidence_expectations_v2 import CoverageGapSignal
from app.domain.contracts.enums import (
    AgentNode,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    GateOutcome,
    ProfileLane,
)
from app.domain.contracts.facts import (
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    MedicationExposureCandidateV2,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
)
from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationAttachment,
)
from app.domain.gates.fact_batch_orchestration import (
    orchestrate_run_gates,
    run_gate_results_to_fact_gate_results,
)
from app.domain.gates.fact_evidence_closure import validate_page_coverage
from app.projections.evidence_expectations import ProjectionInputError
from app.domain.publication import canonical_hash
from app.services.fact_expectation_gaps import (
    EXPECTATION_INPUT_INCOMPLETE_CODE as _EXPECTATION_INPUT_INCOMPLETE_CODE,
)
from app.services.fact_expectation_gaps import expectation_gap_signals
from app.services.fact_normalization_source_adapter import (
    FactPlanningSourceError,
    build_doc_version_to_logical_map,
    build_evidence_normalizer_input,
    collect_visual_observation_attachments,
    select_call_visual_observation_attachments,
    visual_observation_run_scope,
)
from app.services.fact_publication_service import (
    FactPublicationError,
    FactPublicationService,
)
from app.services.evidence_expectation_projection_service import (
    EvidenceExpectationProjectionError,
    EvidenceExpectationProjectionService,
)
from app.services.patient_profile_service import (
    PatientProfileProjectionError,
    PatientProfileService,
)
from app.domain.contracts.patient_profile_v2 import ProfileStatus
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.fact_repositories import (
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCallRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    FactNormalizationUnresolvedItemRepository,
)
from app.storage.fact_rule_link_repository import (
    FactRuleIndexError,
    FactRuleLinkV2Repository,
)
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.facts_models import (
    FactNormalizationCallRecord,
    FactNormalizationCandidateRecord,
    FactNormalizationUnresolvedItemRecord,
)
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
    EpisodeRepository,
    list_expectation_templates,
)
from app.workflow.errors import StepFailure
from app.workflow.runner import PreparedStepResult, StepContext, StepExecutor

from .fact_normalization_job_service import (
    EMPTY_OUTPUT_CODE,
    FACT_NORMALIZATION_FINALIZE_STEP_ID,
    PARTIAL_OUTPUT_CODE,
    STALE_AUTHORITY_CODE,
)

TransportFn = Callable[[EvidenceNormalizerInput], EvidenceNormalizerOutput]
TransportFactory = Callable[[ModelConfigContract], EvidenceNormalizerTransport]
_FACT_NORMALIZATION_CONTRACT_VERSION = "phase5/facts/v1"


def _expectation_gap_signals(
    session: Session,
    authority: FactAuthority,
    unresolved_items: list[PersistedEvidenceNormalizerUnresolvedItem],
    *,
    fact_candidates: list[ClinicalFactCandidateV2] | None = None,
    gate_results: list[FactGateResult] | None = None,
) -> list[CoverageGapSignal]:
    """兼容别名：信号推导唯一实现在 ``fact_expectation_gaps.expectation_gap_signals``。

    模板清单与审核节点依赖经由本模块全局注入，保持既有针对本模块
    monkeypatch 这两个名字的单测语义不变。书面判断检索摘要按当前权威只读加载：
    未检索/覆盖不完整维持原兜底，双读完整未见候选才升级专业判断缺口。
    """
    return expectation_gap_signals(
        session,
        authority,
        unresolved_items,
        fact_candidates=fact_candidates,
        gate_results=gate_results,
        judgment_search_summaries=JudgmentSearchSummaryRepository(
            session
        ).latest_for_authority(authority),
        _templates_lookup=list_expectation_templates,
        _episode_lookup=EpisodeRepository,
    )


def _profile_lane_conflict_reasons(
    session: Session,
    authority: FactAuthority,
    fact_candidates: list[ClinicalFactCandidateV2],
    event_candidates: list[ClinicalEventCandidateV2] | None = None,
) -> dict[str, list[str]]:
    """Reject rerun lane drift per candidate instead of rolling back the batch."""

    def identity(item, *, value):
        return clinical_fact_stable_identity(
            authority=authority,
            fact_type=item.fact_type,
            profile_lane=ProfileLane.EVIDENCE_QUALITY,
            asserted_object=item.asserted_object,
            polarity=item.polarity,
            value=value,
            unit=item.unit,
            date_range=item.date_range,
        )

    superseded = {
        item.target_id
        for item in FactCorrectionRepository(session).list_by_authority(authority)
    }
    lanes_by_identity: dict[str, set[ProfileLane]] = {}
    for fact in ClinicalFactV2Repository(session).list_by_episode(
        authority.review_episode_id
    ):
        if fact.authority != authority or fact.fact_id in superseded:
            continue
        lanes_by_identity.setdefault(identity(fact, value=fact.value), set()).add(
            fact.profile_lane
        )
    for candidate in fact_candidates:
        lanes_by_identity.setdefault(
            identity(candidate, value=candidate.canonical_value), set()
        ).add(candidate.profile_lane)

    fact_reason = (
        "同一临床事实在当前审核节点已有不同主题归属，当前候选未发布；"
        "请核对主题归属。"
    )
    reasons = {
        candidate.candidate_id: [fact_reason]
        for candidate in fact_candidates
        if len(
            lanes_by_identity[identity(candidate, value=candidate.canonical_value)]
        )
        > 1
    }
    events = event_candidates or []
    if not events:
        return reasons

    facts_by_id = {candidate.candidate_id: candidate for candidate in fact_candidates}

    def event_identity(item, referenced_fact_objects):
        return clinical_event_stable_identity(
            authority=authority,
            event_type=item.event_type,
            profile_lane=ProfileLane.EVIDENCE_QUALITY,
            referenced_fact_objects=referenced_fact_objects,
            start_range=item.start_range,
            end_range=item.end_range,
            duration_status=item.duration_status,
        )

    event_lanes_by_identity: dict[str, set[ProfileLane]] = {}
    for event in ClinicalEventV2Repository(session).list_by_episode(
        authority.review_episode_id
    ):
        if event.authority != authority or event.event_id in superseded:
            continue
        event_lanes_by_identity.setdefault(
            event_identity(event, event.referenced_fact_objects), set()
        ).add(event.profile_lane)
    candidate_event_identities: dict[str, str] = {}
    for event in events:
        referenced_objects = sorted(
            {
                f"{facts_by_id[fact_id].fact_type}:"
                f"{facts_by_id[fact_id].asserted_object}"
                for fact_id in event.fact_candidate_ids
            }
        )
        semantic_identity = event_identity(event, referenced_objects)
        candidate_event_identities[event.candidate_id] = semantic_identity
        event_lanes_by_identity.setdefault(semantic_identity, set()).add(
            event.profile_lane
        )

    event_reason = (
        "同一临床事件在当前审核节点已有不同主题归属，当前候选未发布；"
        "请核对主题归属。"
    )
    reasons.update(
        {
            event.candidate_id: [event_reason]
            for event in events
            if len(event_lanes_by_identity[candidate_event_identities[event.candidate_id]])
            > 1
        }
    )
    return reasons


def _transactional_gate_results(
    run_result,
    candidates,
    created_at,
    *,
    profile_lane_conflicts: dict[str, list[str]] | None = None,
):
    """以全部先行门禁与事实引用闭包生成最终发布门禁。"""
    verdicts_by_candidate = {}
    for verdict in run_result.gate_results:
        verdicts_by_candidate.setdefault(verdict.candidate_id, []).append(verdict)
    outcome_by_candidate = {}
    reasons_by_candidate = {}
    for candidate in candidates:
        verdicts = verdicts_by_candidate.get(candidate.candidate_id, [])
        failures = [item for item in verdicts if item.outcome != GateOutcome.ACCEPTED]
        outcome = GateOutcome.ACCEPTED
        if any(item.outcome == GateOutcome.BLOCKED for item in failures):
            outcome = GateOutcome.BLOCKED
        elif failures:
            outcome = GateOutcome.REJECTED
        outcome_by_candidate[candidate.candidate_id] = outcome
        reasons_by_candidate[candidate.candidate_id] = sorted(
            {reason for item in failures for reason in item.reasons}
        )

    for candidate_id, reasons in (profile_lane_conflicts or {}).items():
        if outcome_by_candidate.get(candidate_id) == GateOutcome.ACCEPTED:
            outcome_by_candidate[candidate_id] = GateOutcome.REJECTED
            reasons_by_candidate[candidate_id] = list(reasons)

    linked = [
        candidate
        for candidate in candidates
        if isinstance(candidate, (ClinicalEventCandidateV2, MedicationExposureCandidateV2))
    ]
    for candidate in linked:
        unavailable = sorted(
            fact_id
            for fact_id in candidate.fact_candidate_ids
            if outcome_by_candidate.get(fact_id) != GateOutcome.ACCEPTED
        )
        if unavailable and outcome_by_candidate[candidate.candidate_id] == GateOutcome.ACCEPTED:
            outcome_by_candidate[candidate.candidate_id] = GateOutcome.REJECTED
            reasons_by_candidate[candidate.candidate_id] = [
                "引用的事实候选未通过最终发布门禁："
                + "、".join(unavailable)
            ]

    return [
        FactGateResult(
            gate_result_id=(
                f"fact-gate-{run_result.run_id}-{candidate.candidate_id}-"
                f"{FactGate.TRANSACTIONAL_PUBLISH.value}"
            ),
            run_id=run_result.run_id,
            call_id=run_result.candidate_call_ids[candidate.candidate_id],
            candidate_id=candidate.candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=outcome_by_candidate[candidate.candidate_id],
            reasons=reasons_by_candidate[candidate.candidate_id],
            created_at=created_at,
        )
        for candidate in sorted(candidates, key=lambda item: item.candidate_id)
    ]


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FactNormalizationExecutorConfig:
    session_factory: sessionmaker[Session]
    transport: EvidenceNormalizerTransport | None = None
    transport_fn: TransportFn | None = None
    transport_factory: TransportFactory | None = None
    prompt_template: str = DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
    # A page call is already a retryable persisted job step. Retrying again
    # inside the model runner hides failures and multiplies the per-page wait.
    max_transport_retries: int = 0
    max_schema_repairs: int = 2
    artifact_store: ArtifactStore | None = None


def _get_call_for_step(payload: dict[str, Any], step_id: str) -> dict[str, Any]:
    if step_id == FACT_NORMALIZATION_FINALIZE_STEP_ID:
        raise StepFailure(retryable=False, error_code="INVALID_STEP", detail="汇总步骤不对应单次模型调用。")
    try:
        index = int(step_id.split("_")[1])
    except (IndexError, ValueError) as exc:
        raise StepFailure(retryable=False, error_code="INVALID_STEP", detail=f"无法识别任务步骤 {step_id}。") from exc
    calls = sorted(
        list(payload.get("calls") or []),
        key=lambda item: (item["logical_document_id"], item["page_numbers"]),
    )
    if index < 0 or index >= len(calls):
        raise StepFailure(retryable=False, error_code="INVALID_STEP", detail=f"任务步骤 {step_id} 超出调用范围。")
    return calls[index]


def _load_authority(payload: dict[str, Any]) -> FactAuthority:
    try:
        return FactAuthority.model_validate(payload["authority"])
    except Exception as exc:
        raise StepFailure(retryable=False, error_code="INVALID_AUTHORITY", detail="任务缺少可验证的证据权威范围。") from exc


def _validate_authority(session: Session, authority: FactAuthority) -> None:
    try:
        FactAuthorityValidator(session).validate(authority)
    except FactAuthorityError as exc:
        raise StepFailure(retryable=False, error_code=STALE_AUTHORITY_CODE, detail=str(exc)) from exc


def _load_frozen_agent_config(
    session: Session,
    *,
    payload: dict[str, Any],
    run_id: str,
    authority: FactAuthority,
    prompt_template: str,
) -> ModelConfigContract:
    """确保审计记录中的冻结配置就是本次实际执行配置。"""
    run = FactNormalizationRunRepository(session).get(run_id)
    if run.authority != authority:
        raise StepFailure(
            retryable=False,
            error_code=STALE_AUTHORITY_CODE,
            detail="规范化运行与当前证据权威范围不一致。",
        )
    prompt_version_id = str(payload.get("prompt_version_id") or "")
    model_config_id = str(payload.get("model_config_id") or "")
    if (
        prompt_version_id != run.prompt_version_id
        or model_config_id != run.model_config_id
    ):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="任务载荷与规范化运行冻结的模型配置不一致。",
        )
    try:
        prompt = AppendRepository(session, PROMPT_VERSION_CONFIG).get(
            prompt_version_id
        )
        model_config = AppendRepository(session, MODEL_CONFIG_CONFIG).get(
            model_config_id
        )
    except Exception as exc:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail=f"无法读取冻结的证据规范化配置：{exc}",
        ) from exc
    if not isinstance(prompt, PromptVersion) or not isinstance(
        model_config, ModelConfigContract
    ):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="冻结的证据规范化配置类型不正确。",
        )
    if prompt.node is not AgentNode.EVIDENCE_NORMALIZER:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="冻结提示词不属于证据规范化任务。",
        )
    if prompt.schema_version_id != _FACT_NORMALIZATION_CONTRACT_VERSION:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="冻结提示词与当前证据规范化输出结构版本不一致。",
        )
    if prompt.template_sha256 != evidence_normalizer_prompt_template_sha256(
        prompt_template
    ):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="冻结提示词内容与当前证据规范化模板不一致。",
        )
    try:
        validate_evidence_normalizer_model_config(model_config)
    except ValueError as exc:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail=f"冻结的个例档案整理模型设置无效：{exc}",
        ) from exc
    return model_config


def _build_input(
    session: Session,
    authority: FactAuthority,
    run_id: str,
    call: dict[str, Any],
    *,
    max_pages_per_call: int,
    created_at: datetime,
    page_review_coverage_id: str | None = None,
    include_visual_sources: bool = False,
) -> EvidenceNormalizerInput:
    try:
        return build_evidence_normalizer_input(
            session,
            authority=authority,
            run_id=run_id,
            call_id=str(call["call_id"]),
            logical_document_id=str(call["logical_document_id"]),
            page_numbers=list(call["page_numbers"]),
            expected_input_sha256=str(call["input_sha256"]),
            max_pages_per_call=max_pages_per_call,
            created_at=created_at,
            page_review_coverage_id=page_review_coverage_id,
            include_visual_sources=include_visual_sources,
        )
    except FactPlanningSourceError as exc:
        raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, detail=str(exc)) from exc
    except Exception as exc:
        raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, detail=f"无法从活动证据修订重建本次调用输入：{exc}") from exc


def _build_frozen_visual_observations(
    session: Session,
    *,
    authority: FactAuthority,
    call: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[SelectiveVisionObservationAttachment, ...]:
    """按任务冻结的视觉观察范围重建本次调用的观察附件（失效关闭）。

    - 任务载荷没有 ``visual_observation_scope_sha256``：任务冻结于视觉通道
      之前，观察永不进入本次输入（不静默追加新观察）；
    - 载荷携带冻结范围：重建时全修订重新收集并复核范围哈希，任一漂移
      （新增/丢失/OCR 漂移/篡改）即硬失败，不允许冻结后静默丢弃或追加。
    """
    frozen_scope = payload.get("visual_observation_scope_sha256")
    if frozen_scope is None:
        return ()
    try:
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(
            authority.complete_processing_revision_id
        )
        doc_version_to_logical, _ = build_doc_version_to_logical_map(session, revision)
        attachments = collect_visual_observation_attachments(
            session,
            revision=revision,
            doc_version_to_logical=doc_version_to_logical,
        )
    except Exception as exc:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail=f"无法按冻结范围重建视觉观察清单：{exc}",
        ) from exc
    run_scope = visual_observation_run_scope(attachments)
    if run_scope != str(frozen_scope):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="当前视觉观察清单与任务冻结范围不一致，拒绝在冻结后追加或丢弃观察。",
        )
    selected = select_call_visual_observation_attachments(
        attachments,
        doc_version_to_logical=doc_version_to_logical,
        logical_document_id=str(call["logical_document_id"]),
        page_numbers=list(call["page_numbers"]),
    )
    return selected


def _candidate_identity(kind: str, call_id: str, index: int, payload: dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("candidate_id", None)
    material.pop("created_at", None)
    digest = canonical_hash({"kind": kind, "call_id": call_id, "position": index, "candidate": material})
    return f"{kind}_{digest[:40]}"


def _hydrate_candidate_ids(output: EvidenceNormalizerOutput, created_at: datetime):
    """候选主键由系统派生，模型 ID 只在本次响应内用于建立引用。"""
    fact_id_map: dict[str, str] = {}
    facts: list[ClinicalFactCandidateV2] = []
    for index, candidate in enumerate(output.fact_candidates):
        payload = candidate.model_dump(mode="json")
        candidate_id = _candidate_identity("fact", output.call_id, index, payload)
        fact_id_map[candidate.candidate_id] = candidate_id
        payload.update(candidate_id=candidate_id, created_at=created_at)
        facts.append(ClinicalFactCandidateV2.model_validate(payload))
    events: list[ClinicalEventCandidateV2] = []
    for index, candidate in enumerate(output.event_candidates):
        payload = candidate.model_dump(mode="json")
        payload["fact_candidate_ids"] = sorted(fact_id_map[item] for item in candidate.fact_candidate_ids)
        payload["candidate_id"] = _candidate_identity("event", output.call_id, index, payload)
        payload["created_at"] = created_at
        events.append(ClinicalEventCandidateV2.model_validate(payload))
    exposures: list[MedicationExposureCandidateV2] = []
    for index, candidate in enumerate(output.exposure_candidates):
        payload = candidate.model_dump(mode="json")
        payload["fact_candidate_ids"] = sorted(fact_id_map[item] for item in candidate.fact_candidate_ids)
        payload["candidate_id"] = _candidate_identity("exposure", output.call_id, index, payload)
        payload["created_at"] = created_at
        exposures.append(MedicationExposureCandidateV2.model_validate(payload))
    return facts, events, exposures


def _unresolved_payload(output: EvidenceNormalizerOutput) -> tuple[list[dict[str, Any]], str]:
    items = [item.model_dump(mode="json") for item in output.unresolved_items]
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return items, _sha256(canonical)


def _persisted_unresolved_items(
    output: EvidenceNormalizerOutput,
    *,
    created_at: datetime,
) -> list[PersistedEvidenceNormalizerUnresolvedItem]:
    persisted: list[PersistedEvidenceNormalizerUnresolvedItem] = []
    for position, item in enumerate(output.unresolved_items):
        identity = canonical_hash(
            {
                "call_id": output.call_id,
                "logical_document_id": output.logical_document_id,
                "position": position,
                "item": item.model_dump(mode="json"),
            }
        )
        persisted.append(
            PersistedEvidenceNormalizerUnresolvedItem(
                unresolved_item_id=f"unresolved_{identity[:40]}",
                run_id=output.run_id,
                call_id=output.call_id,
                logical_document_id=output.logical_document_id,
                position=position,
                item=item,
                created_at=created_at,
            )
        )
    return persisted


def _validate_persisted_page_closure(
    session: Session,
    *,
    calls: list[FactNormalizationCall],
    candidates: list[
        ClinicalFactCandidateV2
        | ClinicalEventCandidateV2
        | MedicationExposureCandidateV2
    ],
    unresolved_items: list[PersistedEvidenceNormalizerUnresolvedItem],
) -> None:
    locator_ids = {
        locator_id
        for candidate in candidates
        for locator_id in candidate.locator_ids
    } | {
        locator_id
        for unresolved in unresolved_items
        for locator_id in unresolved.item.affected_locator_ids
    }
    locator_pages: dict[str, int] = {}
    if locator_ids:
        rows = session.execute(
            select(EvidenceLocatorArtifactRecord).where(
                EvidenceLocatorArtifactRecord.locator_id.in_(sorted(locator_ids))
            )
        ).scalars().all()
        locator_pages = {row.locator_id: row.page_number for row in rows}

    missing_by_call: dict[str, list[int]] = {}
    for call in calls:
        covered: set[int] = set()
        for candidate in candidates:
            if candidate.call_id == call.call_id:
                covered.update(
                    locator_pages[locator_id]
                    for locator_id in candidate.locator_ids
                    if locator_id in locator_pages
                )
        for unresolved in unresolved_items:
            if unresolved.call_id != call.call_id:
                continue
            covered.update(unresolved.item.affected_pages)
            covered.update(
                locator_pages[locator_id]
                for locator_id in unresolved.item.affected_locator_ids
                if locator_id in locator_pages
            )
        missing = sorted(set(call.page_numbers) - covered)
        if missing:
            missing_by_call[call.call_id] = missing
    if missing_by_call:
        detail = "；".join(
            f"调用 {call_id} 缺少逐页候选或未解决说明：{pages}"
            for call_id, pages in sorted(missing_by_call.items())
        )
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail=detail,
        )


def _load_run_candidates(session: Session, run_id: str):
    rows = session.execute(
        select(FactNormalizationCandidateRecord).where(FactNormalizationCandidateRecord.run_id == run_id)
    ).scalars().all()
    repository = FactNormalizationCandidateRepository(session)
    facts: list[ClinicalFactCandidateV2] = []
    events: list[ClinicalEventCandidateV2] = []
    exposures: list[MedicationExposureCandidateV2] = []
    for row in rows:
        candidate = repository.get(row.candidate_id)
        if isinstance(candidate, ClinicalFactCandidateV2):
            facts.append(candidate)
        elif isinstance(candidate, ClinicalEventCandidateV2):
            events.append(candidate)
        else:
            exposures.append(candidate)
    return facts, events, exposures


def _validate_call_checkpoint_replay(
    session: Session,
    *,
    authority: FactAuthority,
    run_id: str,
    call: dict[str, Any],
    checkpoint: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    """检查点只能复用已由同一租约事务提交且仍处于活动权威下的结果。"""
    _validate_authority(session, authority)
    run = FactNormalizationRunRepository(session).get(run_id)
    if run.authority != authority:
        raise StepFailure(
            retryable=False,
            error_code=STALE_AUTHORITY_CODE,
            detail="规范化运行与当前证据权威范围不一致。",
        )
    persisted_call = FactNormalizationCallRepository(session).get(str(call["call_id"]))
    expected_call = (
        run_id,
        str(call["logical_document_id"]),
        list(call["page_numbers"]),
        str(call["input_sha256"]),
    )
    actual_call = (
        persisted_call.run_id,
        persisted_call.logical_document_id,
        persisted_call.page_numbers,
        persisted_call.input_sha256,
    )
    if actual_call != expected_call:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="任务检查点与已持久化的规范化调用不一致。",
        )
    persisted_candidate_ids = sorted(
        session.execute(
            select(FactNormalizationCandidateRecord.candidate_id).where(
                FactNormalizationCandidateRecord.call_id == str(call["call_id"])
            )
        ).scalars().all()
    )
    persisted_unresolved_ids = sorted(
        session.execute(
            select(FactNormalizationUnresolvedItemRecord.unresolved_item_id).where(
                FactNormalizationUnresolvedItemRecord.call_id == str(call["call_id"])
            )
        ).scalars().all()
    )
    if persisted_candidate_ids != sorted(checkpoint.get("candidate_ids") or []):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="任务检查点中的候选清单与持久记录不一致。",
        )
    if persisted_unresolved_ids != sorted(
        checkpoint.get("unresolved_item_ids") or []
    ):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="任务检查点中的未解决项清单与持久记录不一致。",
        )
    from app.services.fact_normalization_replay_sources import validate_replayed_sources
    try:
        validate_replayed_sources(session, payload=payload, authority=authority, run=run,
                                  call=call, candidate_ids=persisted_candidate_ids)
    except Exception as exc:
        raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE,
                          detail=f"已保存候选的来源未通过复验：{exc}") from exc



def _rebuild_call_checkpoint_from_persisted(
    session: Session,
    *,
    run_id: str,
    call: dict[str, Any],
) -> dict[str, Any] | None:
    """步骤检查点缺失但成功调用结果已持久化时，从持久记录重建检查点。

    中断、修复或历史写入可能让 ``fact_normalization_calls``/候选先于步骤
    检查点存在。持久化的成功调用是唯一事实：不得为同一调用再次消耗模型，
    也不得让重放落入 ``CALL_IDENTITY_CONFLICT``。身份不一致、非成功状态或
    内容不完整的持久调用一律失效关闭，交由人工核对。
    """
    call_id = str(call["call_id"])
    call_row = session.execute(
        select(FactNormalizationCallRecord).where(
            FactNormalizationCallRecord.call_id == call_id
        )
    ).scalars().first()
    if call_row is None:
        return None
    persisted_call = FactNormalizationCallRepository(session).get(call_id)
    expected_call = (
        run_id,
        str(call["logical_document_id"]),
        list(call["page_numbers"]),
        str(call["input_sha256"]),
    )
    actual_call = (
        persisted_call.run_id,
        persisted_call.logical_document_id,
        persisted_call.page_numbers,
        persisted_call.input_sha256,
    )
    if actual_call != expected_call:
        raise StepFailure(
            retryable=False,
            error_code="CALL_IDENTITY_CONFLICT",
            detail="已持久化的规范化调用与任务步骤身份不一致，拒绝复用或重放。",
        )
    if persisted_call.status != FactCallStatus.SUCCEEDED:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="已持久化的规范化调用不是成功状态，不能作为步骤结果复用。",
        )
    candidate_ids = sorted(
        session.execute(
            select(FactNormalizationCandidateRecord.candidate_id).where(
                FactNormalizationCandidateRecord.call_id == call_id
            )
        ).scalars().all()
    )
    unresolved_rows = session.execute(
        select(FactNormalizationUnresolvedItemRecord)
        .where(FactNormalizationUnresolvedItemRecord.call_id == call_id)
        .order_by(FactNormalizationUnresolvedItemRecord.position)
    ).scalars().all()
    if not candidate_ids and not unresolved_rows:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="已持久化的成功调用缺少候选与未解决项记录，无法重建可验证检查点。",
        )
    unresolved_repository = FactNormalizationUnresolvedItemRepository(session)
    unresolved_items = [
        unresolved_repository.get(row.unresolved_item_id).item.model_dump(mode="json")
        for row in unresolved_rows
    ]
    canonical = json.dumps(
        unresolved_items, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "call_id": call_id,
        "logical_document_id": str(call["logical_document_id"]),
        "page_numbers": list(call["page_numbers"]),
        "candidate_ids": candidate_ids,
        "unresolved_items": unresolved_items,
        "unresolved_item_ids": [row.unresolved_item_id for row in unresolved_rows],
        "unresolved_items_sha256": _sha256(canonical),
        "input_sha256": str(call["input_sha256"]),
        "raw_output_sha256": persisted_call.raw_output_sha256,
        "completed_at": persisted_call.created_at.isoformat(),
    }


def _verify_finalize_checkpoint_profile(
    session: Session,
    *,
    authority: FactAuthority,
    checkpoint: dict[str, Any],
) -> None:
    """重放汇总检查点时，核对已持久化个例档案身份与内容，不得返回未证实检查点。"""
    profile_id = checkpoint.get("patient_profile_revision_id")
    published_counts = (
        int(checkpoint.get("published_fact_count") or 0)
        + int(checkpoint.get("published_event_count") or 0)
        + int(checkpoint.get("published_exposure_count") or 0)
        + int(checkpoint.get("fact_rule_link_count") or 0)
        + int(checkpoint.get("evidence_expectation_count") or 0)
    )
    if profile_id is None:
        if published_counts > 0 or "patient_profile_revision" in checkpoint:
            raise StepFailure(
                retryable=False,
                error_code=PARTIAL_OUTPUT_CODE,
                detail="汇总检查点声称已发布派生结果，但缺少可验证的个例档案身份。",
            )
        return
    profile = PatientProfileService().get(session, str(profile_id))
    if profile.authority != authority:
        raise StepFailure(
            retryable=False,
            error_code=STALE_AUTHORITY_CODE,
            detail="汇总检查点中的个例档案权威范围与当前证据权威不一致。",
        )
    if profile.status != ProfileStatus.SUCCEEDED:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="汇总检查点引用的个例档案不是成功状态。",
        )
    expected_revision = checkpoint.get("patient_profile_revision")
    if expected_revision is not None and profile.revision != expected_revision:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="汇总检查点中的个例档案版本与持久记录不一致。",
        )
    expected_pending = checkpoint.get("patient_profile_pending_review_count")
    if (
        expected_pending is not None
        and profile.pending_review_count != expected_pending
    ):
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="汇总检查点中的个例档案待核对数与持久记录不一致。",
        )
    expected_status = checkpoint.get("patient_profile_status")
    if expected_status is not None and profile.status.value != expected_status:
        raise StepFailure(
            retryable=False,
            error_code=PARTIAL_OUTPUT_CODE,
            detail="汇总检查点中的个例档案状态与持久记录不一致。",
        )


def create_fact_normalization_executor(config: FactNormalizationExecutorConfig) -> StepExecutor:
    model_runner = EvidenceNormalizerRunner(
        max_transport_retries=config.max_transport_retries,
        max_schema_repairs=config.max_schema_repairs,
    )

    def execute_call(context: StepContext):
        payload = dict(context.job_payload or {})
        strategy = payload.get("verified_evidence_strategy")
        call = _get_call_for_step(payload, context.step_id)
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            raise StepFailure(retryable=False, error_code="MISSING_RUN", detail="任务缺少规范化运行编号。")
        authority = _load_authority(payload)
        if context.last_checkpoint is not None:
            if (
                context.last_checkpoint.get("call_id") != call.get("call_id")
                or context.last_checkpoint.get("input_sha256")
                != call.get("input_sha256")
            ):
                raise StepFailure(
                    retryable=False,
                    error_code=PARTIAL_OUTPUT_CODE,
                    detail="任务检查点与当前规范化调用不一致。",
                )
            with config.session_factory() as session:
                _load_frozen_agent_config(
                    session,
                    payload=payload,
                    run_id=run_id,
                    authority=authority,
                    prompt_template=config.prompt_template,
                )
                _validate_call_checkpoint_replay(
                    session,
                    authority=authority,
                    run_id=run_id,
                    call=call,
                    checkpoint=context.last_checkpoint,
                    payload=payload,
                )
            return dict(context.last_checkpoint)
        recovered_checkpoint = None
        with config.session_factory() as session:
            recovered_checkpoint = _rebuild_call_checkpoint_from_persisted(
                session, run_id=run_id, call=call
            )
            if recovered_checkpoint is not None:
                _load_frozen_agent_config(
                    session,
                    payload=payload,
                    run_id=run_id,
                    authority=authority,
                    prompt_template=config.prompt_template,
                )
                _validate_call_checkpoint_replay(
                    session,
                    authority=authority,
                    run_id=run_id,
                    call=call,
                    checkpoint=recovered_checkpoint,
                    payload=payload,
                )
        if recovered_checkpoint is not None:
            return dict(recovered_checkpoint)
        with config.session_factory() as session:
            _validate_authority(session, authority)
            model_config = _load_frozen_agent_config(
                session,
                payload=payload,
                run_id=run_id,
                authority=authority,
                prompt_template=config.prompt_template,
            )
            run_created_at = FactNormalizationRunRepository(session).get(run_id).created_at
            from app.services.page_review_visual_sources import VISUAL_SOURCE_POLICY
            if payload.get("visual_source_policy") not in (None, VISUAL_SOURCE_POLICY):
                raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE,
                                  detail="视觉来源处理版本不受支持")
            evidence_input = _build_input(
                session,
                authority,
                run_id,
                call,
                max_pages_per_call=int(payload.get("max_pages_per_call", 20)),
                created_at=run_created_at,
                page_review_coverage_id=payload.get("page_review_coverage_id"),
                include_visual_sources=payload.get("visual_source_policy") == VISUAL_SOURCE_POLICY,
            )
            visual_observations = _build_frozen_visual_observations(
                session,
                authority=authority,
                call=call,
                payload=payload,
            )

        receipt_hashes = []

        def record_completion(receipt):
            if config.artifact_store is None:
                return
            envelope = {"job_id": context.job_id, "step_id": context.step_id,
                        "call_id": call["call_id"], "run_id": run_id, **receipt}
            artifact = config.artifact_store.put("raw_response", json.dumps(
                envelope, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            receipt_hashes.append(artifact.sha256)
            logging.getLogger(__name__).info("Normalizer receipt job=%s call=%s sha256=%s",
                context.job_id, call["call_id"], artifact.sha256)

        from app.projections.page_review_pending_normalization import (
            LEGACY_PENDING_NORMALIZATION_POLICY, PENDING_NORMALIZATION_POLICY, pending_only_output,
        )
        policy = payload.get("pending_normalization_policy")
        if policy not in (None, LEGACY_PENDING_NORMALIZATION_POLICY, PENDING_NORMALIZATION_POLICY):
            raise StepFailure(retryable=False, error_code="NORMALIZATION_POLICY_INVALID",
                              detail="本次资料整理方式无法识别，请保留作业并检查版本。")
        pending_output = pending_only_output(evidence_input) if policy is not None else None
        if pending_output is not None:
            output = validate_evidence_normalizer_output(pending_output, evidence_input)
            raw_sha = _sha256(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
        elif config.transport_fn is not None:
            try:
                raw_output = config.transport_fn(evidence_input)
                if not (
                    raw_output.fact_candidates
                    or raw_output.event_candidates
                    or raw_output.exposure_candidates
                    or raw_output.unresolved_items
                ):
                    raise StepFailure(
                        retryable=False,
                        error_code=EMPTY_OUTPUT_CODE,
                        detail="模型未返回候选，也未逐页说明无可提取内容。",
                    )
                output = validate_evidence_normalizer_output(raw_output, evidence_input)
                raw_sha = _sha256(json.dumps(raw_output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
            except StepFailure:
                raise
            except (ValueError, TypeError) as exc:
                raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, detail=f"模型输出未通过完整性校验：{exc}") from exc
            except Exception as exc:
                raise StepFailure(retryable=True, error_code="TRANSPORT_FAILED", detail=f"模型调用失败：{exc}") from exc
        else:
            transport = config.transport
            if transport is None:
                transport_factory = (
                    config.transport_factory
                    or evidence_normalizer_transport_from_model_config
                )
                try:
                    transport = (transport_factory(model_config)
                                 if config.transport_factory is not None
                                 else transport_factory(model_config, receipt_callback=record_completion))
                except Exception as exc:
                    raise StepFailure(
                        retryable=True,
                        error_code="TRANSPORT_FAILED",
                        detail=f"无法按冻结配置启动证据规范化模型：{exc}",
                    ) from exc
            result = model_runner.run(
                evidence_input,
                transport,
                prompt_template=config.prompt_template,
                visual_observations=visual_observations or None,
                **({"pending_details_retained": True, "compact_references": True,
                    "verified_scope_prompt": True} if strategy is not None else {}),
            )
            if result.final_output is None:
                last_attempt = result.attempts[-1] if result.attempts else None
                issues = last_attempt.issues if last_attempt is not None else ["未返回结果"]
                error_code = (
                    last_attempt.error_code
                    if last_attempt is not None and last_attempt.error_code is not None
                    else PARTIAL_OUTPUT_CODE
                )
                raise StepFailure(
                    retryable=error_code == "TRANSPORT_FAILED",
                    error_code=error_code,
                    detail="；".join(issues),
                )
            output = result.final_output
            raw_sha = result.attempts[-1].raw_output_sha256

        if policy == PENDING_NORMALIZATION_POLICY:
            from app.projections.pending_observations_report import pending_retention_items
            retained = pending_retention_items(evidence_input)
            if retained:
                output = output.model_copy(update={
                    "unresolved_items": [*output.unresolved_items, *retained],
                })
                output = validate_evidence_normalizer_output(output, evidence_input)

        candidate_count = len(output.fact_candidates) + len(output.event_candidates) + len(output.exposure_candidates)
        if candidate_count == 0 and not output.unresolved_items:
            raise StepFailure(retryable=False, error_code=EMPTY_OUTPUT_CODE, detail="模型未返回候选，也未逐页说明无可提取内容。")
        completed_at = run_created_at
        facts, events, exposures = _hydrate_candidate_ids(output, completed_at)
        candidates = [*facts, *events, *exposures]
        unresolved_items, unresolved_sha256 = _unresolved_payload(output)
        persisted_unresolved = _persisted_unresolved_items(
            output, created_at=completed_at
        )
        checkpoint = {
            "call_id": call["call_id"],
            "logical_document_id": call["logical_document_id"],
            "page_numbers": list(call["page_numbers"]),
            "candidate_ids": sorted(candidate.candidate_id for candidate in candidates),
            "unresolved_items": unresolved_items,
            "unresolved_item_ids": [
                item.unresolved_item_id for item in persisted_unresolved
            ],
            "unresolved_items_sha256": unresolved_sha256,
            "input_sha256": call["input_sha256"],
            "raw_output_sha256": raw_sha,
            "completed_at": completed_at.isoformat(),
        }
        if receipt_hashes:
            checkpoint["transport_receipt_sha256"] = receipt_hashes
        if pending_output is not None:
            checkpoint["normalization_method"] = policy
            checkpoint["model_called"] = False

        def apply(session: Session) -> None:
            _validate_authority(session, authority)
            call_contract = FactNormalizationCall(
                call_id=str(call["call_id"]), run_id=run_id,
                logical_document_id=str(call["logical_document_id"]),
                page_numbers=list(call["page_numbers"]), status=FactCallStatus.SUCCEEDED,
                input_sha256=str(call["input_sha256"]), raw_output_sha256=raw_sha,
                created_at=completed_at,
            )
            call_repository = FactNormalizationCallRepository(session)
            call_row = session.get(FactNormalizationCallRecord, call_contract.call_id)
            if call_row is None:
                call_repository.create(call_contract)
            elif call_repository.get(call_contract.call_id) != call_contract:
                raise StepFailure(retryable=False, error_code="CALL_IDENTITY_CONFLICT", detail="同一调用编号对应不同规范化结果。")
            candidate_repository = FactNormalizationCandidateRepository(session)
            for candidate in candidates:
                row = session.get(FactNormalizationCandidateRecord, candidate.candidate_id)
                if row is None:
                    candidate_repository.create(call_contract.call_id, candidate)
                elif candidate_repository.get(candidate.candidate_id) != candidate:
                    raise StepFailure(retryable=False, error_code="CANDIDATE_IDENTITY_CONFLICT", detail="同一候选编号对应不同临床内容。")
            unresolved_repository = FactNormalizationUnresolvedItemRepository(session)
            for unresolved in persisted_unresolved:
                row = session.get(
                    FactNormalizationUnresolvedItemRecord,
                    unresolved.unresolved_item_id,
                )
                if row is None:
                    unresolved_repository.create(unresolved)
                elif unresolved_repository.get(unresolved.unresolved_item_id) != unresolved:
                    raise StepFailure(
                        retryable=False,
                        error_code="UNRESOLVED_IDENTITY_CONFLICT",
                        detail="同一未解决项编号对应不同逐页内容。",
                    )

        return PreparedStepResult(checkpoint=checkpoint, apply=apply)

    def execute_finalize(context: StepContext):
        payload = dict(context.job_payload or {})
        run_id = str(payload.get("run_id") or "")
        authority = _load_authority(payload)
        if context.last_checkpoint is not None:
            with config.session_factory() as session:
                _validate_authority(session, authority)
                _load_frozen_agent_config(
                    session,
                    payload=payload,
                    run_id=run_id,
                    authority=authority,
                    prompt_template=config.prompt_template,
                )
                run = FactNormalizationRunRepository(session).get(run_id)
                if (
                    run.authority != authority
                    or run.status.value != context.last_checkpoint.get("status")
                ):
                    raise StepFailure(
                        retryable=False,
                        error_code=PARTIAL_OUTPUT_CODE,
                        detail="汇总检查点与已持久化运行状态不一致。",
                    )
                _verify_finalize_checkpoint_profile(
                    session,
                    authority=authority,
                    checkpoint=context.last_checkpoint,
                )
            return dict(context.last_checkpoint)
        expected_calls = list(payload.get("calls") or [])
        finalized_at = _now_utc()
        checkpoint = {"run_id": run_id, "call_count": len(expected_calls), "status": "running", "finalized_at": finalized_at.isoformat()}

        def apply(session: Session) -> None:
            _validate_authority(session, authority)
            _load_frozen_agent_config(
                session,
                payload=payload,
                run_id=run_id,
                authority=authority,
                prompt_template=config.prompt_template,
            )
            revision = CompleteEvidenceProcessingRevisionRepository(session).get(authority.complete_processing_revision_id)
            calls = FactNormalizationCallRepository(session).list_by_run(run_id)
            if {call.call_id for call in calls} != {str(call["call_id"]) for call in expected_calls}:
                raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, detail="规范化调用未全部形成可验证结果。")
            outcome, reasons, _ = validate_page_coverage(revision, calls, session=session)
            if outcome.value != "accepted":
                raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, detail="；".join(reasons))
            facts, events, exposures = _load_run_candidates(session, run_id)
            unresolved_items = FactNormalizationUnresolvedItemRepository(
                session
            ).list_by_run(run_id)
            all_candidates = [*facts, *events, *exposures]
            _validate_persisted_page_closure(
                session,
                calls=calls,
                candidates=all_candidates,
                unresolved_items=unresolved_items,
            )
            final_status = FactNormalizationRunStatus.SUCCEEDED
            if facts or events or exposures:
                run_result = orchestrate_run_gates(
                    authority=authority, run_id=run_id, calls=calls,
                    fact_candidates=facts, event_candidates=events,
                    exposure_candidates=exposures, revision=revision, session=session,
                )
                gate_repository = FactGateResultRepository(session)
                gate_results = run_gate_results_to_fact_gate_results(run_result, created_at=finalized_at, id_prefix="fact-gate")
                transactional_results = _transactional_gate_results(
                    run_result,
                    all_candidates,
                    finalized_at,
                    profile_lane_conflicts=_profile_lane_conflict_reasons(
                        session, authority, facts, events
                    ),
                )
                gate_repository.create_many([*gate_results, *transactional_results])
                try:
                    publication = FactPublicationService().publish(session, run_id)
                except FactPublicationError as exc:
                    raise StepFailure(
                        retryable=False,
                        error_code=PARTIAL_OUTPUT_CODE,
                        detail=f"事实发布未能完整提交：{exc}",
                    ) from exc
                try:
                    FactAuthorityValidator(session).validate(publication.authority)
                    rule_links = []
                    if publication.fact_ids:
                        rule_links = FactRuleLinkV2Repository(
                            session
                        ).rebuild_for_authority(
                            publication.authority, run_id=publication.run_id
                        )
                    gap_signals = _expectation_gap_signals(
                        session,
                        publication.authority,
                        unresolved_items,
                        fact_candidates=facts,
                        gate_results=transactional_results,
                    )
                    expectations = EvidenceExpectationProjectionService().project(
                        session,
                        authority=publication.authority,
                        gap_signals=gap_signals,
                        created_at=finalized_at,
                        run_id=publication.run_id,
                    )
                    FactAuthorityValidator(session).validate(publication.authority)
                    profile = PatientProfileService().generate(
                        session,
                        authority=publication.authority,
                        created_at=finalized_at,
                        generated_at=finalized_at,
                        run_id=publication.run_id,
                    )
                    if profile.status != ProfileStatus.SUCCEEDED:
                        raise StepFailure(
                            retryable=False,
                            error_code=PARTIAL_OUTPUT_CODE,
                            detail="个例档案未能生成成功状态的不可变版本。",
                        )
                    checkpoint["patient_profile_revision_id"] = (
                        profile.patient_profile_revision_id
                    )
                    checkpoint["patient_profile_revision"] = profile.revision
                    checkpoint["patient_profile_pending_review_count"] = (
                        profile.pending_review_count
                    )
                    checkpoint["patient_profile_status"] = profile.status.value
                except ProjectionInputError as exc:
                    raise StepFailure(
                        retryable=False,
                        error_code=_EXPECTATION_INPUT_INCOMPLETE_CODE,
                        detail=f"资料期望缺少可验证的结构化缺口输入：{exc}",
                    ) from exc
                except (
                    EvidenceExpectationProjectionError,
                    FactRuleIndexError,
                    FactAuthorityError,
                    PatientProfileProjectionError,
                ) as exc:
                    raise StepFailure(
                        retryable=False,
                        error_code=PARTIAL_OUTPUT_CODE,
                        detail=f"规则索引、资料期望或个例档案未能完整生成：{exc}",
                    ) from exc
                checkpoint["gate_result_count"] = len(gate_results) + len(
                    transactional_results
                )
                checkpoint["conflict_group_count"] = len(run_result.conflict_groups)
                checkpoint["published_fact_count"] = len(publication.fact_ids)
                checkpoint["published_event_count"] = len(publication.event_ids)
                checkpoint["published_exposure_count"] = len(publication.exposure_ids)
                checkpoint["fact_rule_link_count"] = len(rule_links)
                checkpoint["evidence_expectation_count"] = len(expectations)
                checkpoint["rejected_candidate_count"] = len(
                    {
                        result.candidate_id
                        for result in transactional_results
                        if result.outcome != GateOutcome.ACCEPTED
                    }
                )
                if any(
                    result.outcome != GateOutcome.ACCEPTED
                    for result in transactional_results
                ):
                    final_status = FactNormalizationRunStatus.PARTIAL
            else:
                checkpoint.update(gate_result_count=0, conflict_group_count=0, rejected_candidate_count=0)
                final_status = FactNormalizationRunStatus.PARTIAL
            checkpoint["unresolved_item_count"] = len(unresolved_items)
            checkpoint["status"] = final_status.value
            FactNormalizationRunRepository(session).set_status(run_id, final_status)

        return PreparedStepResult(checkpoint=checkpoint, apply=apply)

    def execute(context: StepContext):
        payload = dict(context.job_payload or {})
        if payload.get("verified_evidence_strategy") is not None:
            from app.agents.verified_evidence_prompt import verified_evidence_strategy
            from app.projections.page_review_pending_normalization import PENDING_NORMALIZATION_POLICY
            from app.services.page_review_visual_sources import VISUAL_SOURCE_POLICY
            if (payload["verified_evidence_strategy"] != verified_evidence_strategy()
                or payload.get("pending_normalization_policy") != PENDING_NORMALIZATION_POLICY
                or payload.get("visual_source_policy") != VISUAL_SOURCE_POLICY):
                raise StepFailure(retryable=False, error_code="NORMALIZATION_POLICY_INVALID",
                                  detail="本次整理提示与冻结版本不一致，请保留已有记录。")
        return execute_finalize(context) if context.step_id == FACT_NORMALIZATION_FINALIZE_STEP_ID else execute_call(context)

    return execute
