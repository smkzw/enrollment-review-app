"""人工事实修订的确定性应用：预览影响范围并追加新实体/修订/Profile。

修订只追加，不覆盖原 OCR、候选、旧实体或历史 Profile。新实体必须通过正式发布
仓储（候选语义一致、已接受最终门禁、权威/定位闭包）。成功提交时新实体、修订
记录与新 Profile 由调用方放在同一租约写栅栏事务中。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.domain.contracts.enums import (
    DurationStatus,
    FactCallStatus,
    FactGate,
    FactNormalizationRunStatus,
    FactPolarity,
    GateOutcome,
    ProfileLane,
    SourceStrength,
)
from app.domain.contracts.fact_corrections import (
    ConflictCorrectionOutcome,
    FactCorrectionCommitV2,
    FactCorrectionImpactScope,
    FactCorrectionV2,
    canonical_json,
    fact_correction_idempotency_key,
    snapshot_for_kind,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalEventV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    FactNormalizationCall,
    FactNormalizationRun,
    MedicationExposureCandidateV2,
    MedicationExposureV2,
    PartialDateRange,
    _date_range_identity,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    fact_run_idempotency_key,
    medication_exposure_stable_identity,
)
from app.domain.gates.fact_evidence_closure import derive_source_strength_for_candidate
from app.domain.planning.fact_correction_impact import (
    NODE_RECOMPUTE_MESSAGE,
    FactCorrectionImpactSeed,
    FactReplacementSignature,
    plan_fact_correction_impact,
)
from app.domain.publication import canonical_hash
from app.projections.evidence_expectations import (
    ProjectionInputError as ExpectationProjectionInputError,
)
from app.projections.patient_profile import (
    ProjectionInputError as ProfileProjectionInputError,
)
from app.services.evidence_expectation_projection_service import (
    EvidenceExpectationProjectionError,
    EvidenceExpectationProjectionService,
)
from app.services.fact_expectation_gaps import (
    ReprojectionLineageError,
    reconstruct_reprojection_gap_signals,
)
from app.services.patient_profile_service import (
    PatientProfileProjectionError,
    PatientProfileService,
)
from app.workflow.errors import StepFailure
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.domain.contracts.patient_profile_v2 import profile_items
from app.storage.evidence_models import SourceDocumentVersionV2Record
from app.storage.ocr_models import PageArtifactRecord
from app.storage.fact_authority import (
    FactAuthorityError,
    FactAuthorityValidator,
    FactLocatorReferenceError,
)
from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
from app.storage.fact_correction_impact_queries import load_fact_correction_impact_graph
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactCrossEntityError,
    FactGateResultRepository,
    FactNormalizationCallRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    MedicationExposureV2Repository,
    Phase5RepositoryError,
)
from app.storage.fact_rule_link_repository import (
    FactRuleIndexError,
    FactRuleLinkV2Repository,
)
from app.storage.repositories import (
    EpisodeRepository,
    InvalidReferenceError,
    NotFoundError,
    RepositoryError,
)

__all__ = [
    "FACT_CORRECTION_CONTRACT_VERSION",
    "FactCorrectionApplyResult",
    "FactCorrectionError",
    "FactCorrectionPreview",
    "FactCorrectionStaleError",
    "FactCorrectionValidationError",
    "PreparedFactCorrection",
    "active_entity_ids_after_corrections",
    "apply_prepared_fact_correction",
    "authority_from_episode",
    "list_fact_correction_history",
    "plan_correction_impact",
    "prepare_fact_correction",
    "prepared_from_payload",
    "prepared_to_payload",
    "preview_fact_correction",
    "superseded_entity_ids",
]

FACT_CORRECTION_CONTRACT_VERSION = "phase5/fact_correction/v1"
_CANDIDATE_SEMANTICS = "clinical_review_correction"
_SOURCE_STRENGTH_SEMANTICS = {
    SourceStrength.CONTEMPORANEOUS_OBJECTIVE: "objective_result",
    SourceStrength.HISTORICAL_PRIMARY: "historical_primary",
    SourceStrength.CURRENT_STUDY_CHART: "current_chart",
    SourceStrength.SCREENING_RECORD_TRANSCRIPTION: "screening_transcript",
    SourceStrength.UNVERIFIABLE: "unverifiable_source",
}


class FactCorrectionError(RuntimeError):
    """人工事实修订失败。"""


class FactCorrectionValidationError(FactCorrectionError):
    """请求内容无法形成可发布修订。"""


class FactCorrectionStaleError(FactCorrectionError):
    """活动权威指针已变化，拒绝陈旧修订。"""


@dataclass(frozen=True)
class FactCorrectionPreview:
    target_kind: Literal["fact", "event", "exposure"]
    target_id: str
    old_snapshot: dict[str, Any]
    new_snapshot: dict[str, Any]
    impact_scope: FactCorrectionImpactScope
    locator_ids: list[str]
    # F04：同源兄弟事实（同一原件观察经其他发布通道派生）。更正一条通道
    # 后其余通道仍持旧值，预览必须让医学经理一眼看到全部需要同步的通道。
    sibling_facts: list[dict[str, Any]]


@dataclass(frozen=True)
class PreparedFactCorrection:
    authority: FactAuthority
    target_kind: Literal["fact", "event", "exposure"]
    target_id: str
    locator_ids: list[str]
    reason: str
    operator_id: str
    created_at: datetime
    run_id: str
    call_id: str
    candidate_id: str
    gate_id: str
    new_entity_id: str
    new_revision: int
    new_stable_identity: str
    old_snapshot_json: str
    old_snapshot_sha256: str
    new_snapshot_json: str
    new_snapshot_sha256: str
    correction_id: str
    idempotency_key: str
    proposed_entity: dict[str, Any]
    candidate_payload: dict[str, Any]
    logical_document_id: str
    page_numbers: list[int]
    prompt_version_id: str
    model_config_id: str
    input_scope_sha256: str
    replacement: dict[str, Any] | None


@dataclass(frozen=True)
class FactCorrectionApplyResult:
    correction: FactCorrectionV2
    new_entity_id: str
    profile_revision_id: str
    impact_scope: FactCorrectionImpactScope
    is_replay: bool = False


def superseded_entity_ids(session: Session, authority: FactAuthority) -> set[str]:
    """已被修订指向的旧实体，不得再进入新 Profile 链头。"""
    return {
        item.target_id
        for item in FactCorrectionRepository(session).list_by_authority(authority)
    }


def active_entity_ids_after_corrections(
    session: Session, authority: FactAuthority
) -> dict[str, set[str]]:
    """当前权威下应进入新投影的实体 ID（排除修订目标后的链头，并要求引用闭合）。"""
    superseded = superseded_entity_ids(session, authority)
    from app.storage.active_facts import current_fact_heads

    fact_heads = current_fact_heads(session, authority)
    fact_ids = {item.fact_id for item in fact_heads}
    events = [
        item
        for item in ClinicalEventV2Repository(session).list_for_authority(authority)
        if item.event_id not in superseded and set(item.fact_ids) <= fact_ids
    ]
    event_heads = _chain_heads(events, "stable_identity", "event_id")
    event_ids = {item.event_id for item in event_heads}
    exposures = [
        item
        for item in MedicationExposureV2Repository(session).list_for_authority(
            authority
        )
        if item.exposure_id not in superseded and set(item.fact_ids) <= fact_ids
    ]
    exposure_heads = _chain_heads(exposures, "stable_identity", "exposure_id")
    exposure_ids = {item.exposure_id for item in exposure_heads}
    from app.storage.active_conflicts import current_conflict_heads
    conflicts = [
        item
        for item in current_conflict_heads(session, authority)
        if item.conflict_group_id not in superseded
        and (
            (item.member_kind == "fact" and set(item.fact_ids) <= fact_ids)
            or (item.member_kind == "event" and set(item.event_ids) <= event_ids)
            or (
                item.member_kind == "exposure"
                and set(item.exposure_ids) <= exposure_ids
            )
        )
    ]
    expectations = [
        item
        for item in EvidenceExpectationV2Repository(session).list_for_authority(
            authority
        )
        if item.expectation_id not in superseded
        and set(item.coverage_fact_ids) <= fact_ids
    ]
    return {
        "fact": fact_ids,
        "event": event_ids,
        "exposure": exposure_ids,
        "conflict": {item.conflict_group_id for item in conflicts},
        "expectation": {item.expectation_id for item in expectations},
    }


def _chain_heads(entities: list[Any], identity_attr: str, id_attr: str) -> list[Any]:
    heads: dict[Any, Any] = {}
    for entity in entities:
        key = getattr(entity, identity_attr)
        current = heads.get(key)
        if current is None or entity.revision > current.revision:
            heads[key] = entity
    return sorted(
        heads.values(),
        key=lambda item: (item.revision, getattr(item, id_attr)),
    )


def authority_from_episode(session: Session, review_episode_id: str) -> FactAuthority:
    episode = EpisodeRepository(session).get(review_episode_id)
    if (
        episode.active_evidence_snapshot_id is None
        or episode.active_evidence_processing_revision_id is None
    ):
        raise FactCorrectionValidationError(
            "该审核节点还没有启用完整处理修订，无法修订事实记录。"
        )
    return FactAuthority(
        project_id=episode.project_id,
        subject_id=episode.subject_id,
        review_episode_id=episode.review_episode_id,
        episode_revision=episode.revision,
        protocol_version_id=episode.protocol_version_id,
        rule_set_id=episode.rule_set_id,
        rule_set_revision=episode.rule_set_revision,
        evidence_snapshot_v2_id=episode.active_evidence_snapshot_id,
        complete_processing_revision_id=episode.active_evidence_processing_revision_id,
    )


def _require_authority(session: Session, authority: FactAuthority) -> None:
    try:
        FactAuthorityValidator(session).validate(authority)
    except FactAuthorityError as exc:
        raise FactCorrectionStaleError(
            "审核节点的活动证据已变化，本次修订没有写入。"
        ) from exc


def _load_target(session: Session, kind: str, target_id: str):
    try:
        if kind == "fact":
            return ClinicalFactV2Repository(session).get(target_id)
        if kind == "event":
            return ClinicalEventV2Repository(session).get(target_id)
        if kind == "exposure":
            return MedicationExposureV2Repository(session).get(target_id)
    except (NotFoundError, InvalidReferenceError) as exc:
        raise FactCorrectionValidationError("找不到要修订的事实记录。") from exc
    raise FactCorrectionValidationError(f"不支持的修订目标类型 {kind}")


def _next_revision(entities: list[Any], stable_identity: str) -> int:
    chain = [item.revision for item in entities if item.stable_identity == stable_identity]
    return max(chain, default=0) + 1


def _stable_id(kind: str, material: dict[str, Any]) -> str:
    return kind + ":" + canonical_hash(material)[:32]


def _date_range_from(value: Any) -> PartialDateRange | None:
    if value is None:
        return None
    if isinstance(value, PartialDateRange):
        return value
    if isinstance(value, dict):
        return PartialDateRange.model_validate(value)
    raise FactCorrectionValidationError("日期范围格式不正确")


def _enum(value: Any, enum_cls, label: str):
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise FactCorrectionValidationError(f"{label}无法识别") from exc


def _seed_kind(target_kind: str) -> Literal["fact", "event", "exposure"]:
    if target_kind == "fact":
        return "fact"
    if target_kind == "event":
        return "event"
    if target_kind == "exposure":
        return "exposure"
    raise FactCorrectionValidationError(f"不支持的修订目标类型 {target_kind}")


def plan_correction_impact(
    session: Session,
    *,
    authority: FactAuthority,
    target_kind: str,
    target_id: str,
    replacement: FactReplacementSignature | None,
) -> FactCorrectionImpactScope:
    graph = load_fact_correction_impact_graph(session, authority)
    seed = FactCorrectionImpactSeed(
        kind=_seed_kind(target_kind),
        ids=(target_id,),
        replacement=replacement,
    )
    return plan_fact_correction_impact(seed, graph)


@dataclass(frozen=True)
class FactCorrectionHistoryItem:
    correction: FactCorrectionV2
    patient_profile_revision_id: str
    patient_profile_revision: int


def list_fact_correction_history(
    session: Session, review_episode_id: str
) -> list[FactCorrectionHistoryItem]:
    corrections = FactCorrectionRepository(session).list_by_review_episode(
        review_episode_id
    )
    commits = {
        item.correction_id: item
        for item in FactCorrectionCommitRepository(session).list_by_review_episode(
            review_episode_id
        )
    }
    history: list[FactCorrectionHistoryItem] = []
    profiles = PatientProfileService()
    for correction in corrections:
        commit = commits.get(correction.correction_id)
        if commit is None:
            raise FactCorrectionError(
                f"修订记录 {correction.correction_id} 缺少提交栅栏，拒绝返回不完整历史。"
            )
        profile = profiles.get(session, commit.patient_profile_revision_id)
        history.append(
            FactCorrectionHistoryItem(
                correction=correction,
                patient_profile_revision_id=commit.patient_profile_revision_id,
                patient_profile_revision=profile.revision,
            )
        )
    return history


def preview_fact_correction(
    session: Session,
    *,
    authority: FactAuthority,
    target_kind: Literal["fact", "event", "exposure"],
    target_id: str,
    locator_ids: list[str],
    updates: dict[str, Any],
) -> FactCorrectionPreview:
    _require_authority(session, authority)
    prepared = prepare_fact_correction(
        session,
        authority=authority,
        target_kind=target_kind,
        target_id=target_id,
        locator_ids=locator_ids,
        reason="预览",
        operator_id="preview",
        updates=updates,
        created_at=datetime.now(UTC),
    )
    replacement = None
    if prepared.replacement is not None:
        replacement = FactReplacementSignature(
            fact_type=prepared.replacement["fact_type"],
            supported_requirement_ids=tuple(
                prepared.replacement["supported_requirement_ids"]
            ),
        )
    scope = plan_correction_impact(
        session,
        authority=authority,
        target_kind=target_kind,
        target_id=target_id,
        replacement=replacement,
    )
    if (
        scope.scope_kind == "local"
        and not set(prepared.locator_ids) <= set(scope.affected_locator_ids)
    ):
        scope = FactCorrectionImpactScope(
            scope_kind="node",
            fallback_reason=f"{NODE_RECOMPUTE_MESSAGE}：局部影响范围未包含提交引用的全部定位",
        )
    siblings = _same_observation_siblings(
        session, authority=authority, target_kind=target_kind, target_id=target_id,
    )
    return FactCorrectionPreview(
        target_kind=target_kind,
        target_id=target_id,
        old_snapshot=dict(json.loads(prepared.old_snapshot_json)),
        new_snapshot=dict(json.loads(prepared.new_snapshot_json)),
        impact_scope=scope,
        locator_ids=list(prepared.locator_ids),
        sibling_facts=siblings,
    )


def _same_observation_siblings(
    session: Session, *, authority: FactAuthority,
    target_kind: str, target_id: str,
) -> list[dict[str, Any]]:
    """F04：同一原件观察经其他发布通道派生的活动事实（不含目标自身）。

    同源判定用当前权威 + 断言对象 + 原件定位重叠，不同 fact_type 的通道
    互为兄弟；更正一条通道后其余通道仍持旧值，预览必须可见，避免医学
    经理逐通道试错。不做跨来源的值匹配合并。
    """
    from sqlalchemy import select
    from app.storage.fact_repositories import ClinicalFactV2Repository
    from app.storage.active_facts import current_fact_heads

    facts = ClinicalFactV2Repository(session).list_by_episode(
        authority.review_episode_id
    )
    target = next((f for f in facts if f.fact_id == target_id), None)
    if target is None or target_kind != "fact":
        return []
    target_locators = set(target.locator_ids)
    siblings = []
    for fact in current_fact_heads(session, authority):
        if fact.fact_id == target.fact_id:
            continue
        if fact.asserted_object != target.asserted_object:
            continue
        if not set(fact.locator_ids) & target_locators:
            continue
        siblings.append({
            "fact_id": fact.fact_id,
            "fact_type": fact.fact_type,
            "polarity": fact.polarity.value,
            "value": fact.value,
            "unit": fact.unit,
        })
    return siblings


def prepare_fact_correction(
    session: Session,
    *,
    authority: FactAuthority,
    target_kind: Literal["fact", "event", "exposure"],
    target_id: str,
    locator_ids: list[str],
    reason: str,
    operator_id: str,
    updates: dict[str, Any],
    created_at: datetime,
) -> PreparedFactCorrection:
    if not reason or not reason.strip():
        raise FactCorrectionValidationError("修订理由不能为空。")
    if not operator_id or not operator_id.strip():
        raise FactCorrectionValidationError("操作者不能为空。")
    locators = sorted({item for item in locator_ids if item and str(item).strip()})
    if not locators:
        raise FactCorrectionValidationError("修订必须引用至少一处原文定位。")
    try:
        FactAuthorityValidator(session).validate_locators(authority, locators)
    except (FactAuthorityError, FactLocatorReferenceError, NotFoundError, InvalidReferenceError) as exc:
        raise FactCorrectionValidationError("修订引用的原文定位不属于当前冻结资料。") from exc
    _require_locator_page_artifact_consistency(session, locators)

    try:
        target = _load_target(session, target_kind, target_id)
    except (NotFoundError, InvalidReferenceError) as exc:
        raise FactCorrectionValidationError("找不到要修订的事实记录。") from exc
    if target.authority != authority:
        raise FactCorrectionValidationError("修订目标不属于当前审核节点的活动证据。")
    if FactCorrectionRepository(session).outgoing(target_id) is not None:
        raise FactCorrectionValidationError("该记录已被修订，不能再从同一原记录分叉。")

    new_entity, candidate_payload, replacement = _build_new_entity(
        session,
        target_kind=target_kind,
        target=target,
        locator_ids=locators,
        updates=updates,
        created_at=created_at,
    )
    old_snapshot = snapshot_for_kind(target_kind, target)
    new_snapshot = snapshot_for_kind(target_kind, new_entity)
    old_json = canonical_json(old_snapshot)
    new_json = canonical_json(new_snapshot)
    if old_json == new_json:
        raise FactCorrectionValidationError("拟修改内容与原记录相同，没有可提交的修订。")
    old_sha = hashlib.sha256(old_json.encode("utf-8")).hexdigest()
    new_sha = hashlib.sha256(new_json.encode("utf-8")).hexdigest()

    if target_kind == "fact":
        new_entity_id = new_entity.fact_id
    elif target_kind == "event":
        new_entity_id = new_entity.event_id
    else:
        new_entity_id = new_entity.exposure_id
    material = {
        "contract": FACT_CORRECTION_CONTRACT_VERSION,
        "authority": authority.model_dump(mode="json"),
        "target_kind": target_kind,
        "target_id": target_id,
        "new_entity_id": new_entity_id,
        "reason": reason.strip(),
        "operator_id": operator_id,
        "locator_ids": locators,
        "new_snapshot_sha256": new_sha,
    }
    correction_id = "fcorr-" + canonical_hash(material)[:24]
    run_id = "fcorr-run-" + canonical_hash({**material, "part": "run"})[:24]
    call_id = "fcorr-call-" + canonical_hash({**material, "part": "call"})[:24]
    candidate_id = candidate_payload["candidate_id"]
    gate_id = "fcorr-gate-" + canonical_hash({**material, "part": "gate"})[:24]
    source_run = FactNormalizationRunRepository(session).get(target.run_id)
    input_scope = canonical_hash(
        {
            "fact_correction_input/v1": True,
            "correction_id": correction_id,
            "new_snapshot_sha256": new_sha,
        }
    )
    locator_repo = EvidenceLocatorRepository(session)
    first_locator = locator_repo.get(locators[0])
    document = session.get(
        SourceDocumentVersionV2Record, first_locator.source_document_version_id
    )
    if document is None:
        raise FactCorrectionValidationError("修订定位所属资料版本不存在。")
    page_numbers = sorted(
        {
            locator_repo.get(locator_id).page_number
            for locator_id in locators
            if locator_repo.get(locator_id).source_document_version_id
            == document.source_document_version_id
        }
    )
    if not page_numbers:
        page_numbers = [first_locator.page_number]
    idempotency_key = fact_correction_idempotency_key(
        authority=authority,
        target_kind=target_kind,
        target_id=target_id,
        target_stable_identity=target.stable_identity,
        target_revision=target.revision,
        new_entity_id=new_entity_id,
        new_stable_identity=new_entity.stable_identity,
        new_revision=new_entity.revision,
        old_snapshot_sha256=old_sha,
        new_snapshot_sha256=new_sha,
        reason=reason.strip(),
        locator_ids=locators,
        operator_id=operator_id,
    )
    candidate_payload = dict(candidate_payload)
    candidate_payload["run_id"] = run_id
    candidate_payload["call_id"] = call_id
    proposed_entity = new_entity.model_dump(mode="json")
    proposed_entity["run_id"] = run_id
    proposed_entity["gate_id"] = gate_id
    proposed_entity["gate_ids"] = [gate_id]
    proposed_entity["source_candidate_ids"] = [candidate_id]
    return PreparedFactCorrection(
        authority=authority,
        target_kind=target_kind,
        target_id=target_id,
        locator_ids=locators,
        reason=reason.strip(),
        operator_id=operator_id,
        created_at=created_at,
        run_id=run_id,
        call_id=call_id,
        candidate_id=candidate_id,
        gate_id=gate_id,
        new_entity_id=new_entity_id,
        new_revision=new_entity.revision,
        new_stable_identity=new_entity.stable_identity,
        old_snapshot_json=old_json,
        old_snapshot_sha256=old_sha,
        new_snapshot_json=new_json,
        new_snapshot_sha256=new_sha,
        correction_id=correction_id,
        idempotency_key=idempotency_key,
        proposed_entity=proposed_entity,
        candidate_payload=candidate_payload,
        logical_document_id=document.logical_document_id,
        page_numbers=page_numbers,
        prompt_version_id=source_run.prompt_version_id,
        model_config_id=source_run.model_config_id,
        input_scope_sha256=input_scope,
        replacement=(
            None
            if replacement is None
            else {
                "fact_type": replacement.fact_type,
                "supported_requirement_ids": list(replacement.supported_requirement_ids),
            }
        ),
    )


def _build_new_entity(
    session: Session,
    *,
    target_kind: str,
    target,
    locator_ids: list[str],
    updates: dict[str, Any],
    created_at: datetime,
):
    if target_kind == "fact":
        return _build_new_fact(session, target, locator_ids, updates, created_at)
    if target_kind == "event":
        return _build_new_event(session, target, locator_ids, updates, created_at)
    return _build_new_exposure(session, target, locator_ids, updates, created_at)


def _build_new_fact(session, target: ClinicalFactV2, locator_ids, updates, created_at):
    fact_type = str(updates.get("fact_type") or target.fact_type)
    polarity = _enum(updates.get("polarity"), FactPolarity, "极性") or target.polarity
    asserted_object = str(updates.get("asserted_object") or target.asserted_object)
    value = target.value if "value" not in updates else updates["value"]
    unit = target.unit if "unit" not in updates else updates["unit"]
    date_range = (
        target.date_range
        if "date_range" not in updates
        else _date_range_from(updates["date_range"])
    )
    profile_lane = (
        _enum(updates.get("profile_lane"), ProfileLane, "主题泳道") or target.profile_lane
    )
    supported = updates.get("supported_requirement_ids")
    if supported is None:
        supported_requirement_ids = list(target.supported_requirement_ids)
    else:
        supported_requirement_ids = sorted(set(str(item) for item in supported))
    locator_repo = EvidenceLocatorRepository(session)
    assertion_locator_id = locator_ids[0]
    if target.assertion_basis is not None and target.assertion_basis.locator_id in locator_ids:
        assertion_locator_id = target.assertion_basis.locator_id
    locator = locator_repo.get(assertion_locator_id)
    preserves_assertion_basis = (
        target.assertion_basis is not None
        and assertion_locator_id == target.assertion_basis.locator_id
        and asserted_object == target.asserted_object
    )
    assertion_text = (
        target.assertion_basis.assertion_text
        if preserves_assertion_basis
        else locator.excerpt or asserted_object
    )
    assertion_basis = None
    if polarity != FactPolarity.UNKNOWN:
        assertion_basis = AssertionBasis(
            asserted_object=asserted_object,
            assertion_text=assertion_text,
            locator_id=assertion_locator_id,
            source_text_sha256=locator.source_text_sha256,
        )
    stable = clinical_fact_stable_identity(
        authority=target.authority,
        fact_type=fact_type,
        profile_lane=profile_lane,
        asserted_object=asserted_object,
        polarity=polarity,
        value=value,
        unit=unit,
        date_range=date_range,
    )
    existing = ClinicalFactV2Repository(session).list_for_authority(target.authority)
    revision = (
        target.revision + 1
        if stable == target.stable_identity
        else _next_revision(existing, stable)
    )
    new_id = _stable_id(
        "fact",
        {
            "target_id": target.fact_id,
            "stable_identity": stable,
            "revision": revision,
        },
    )
    candidate_id = "fcorr-cand-" + canonical_hash({"entity": new_id, "kind": "fact"})[:24]
    candidate_payload = {
        "candidate_id": candidate_id,
        "fact_type": fact_type,
        "profile_lane": profile_lane.value,
        "supported_requirement_ids": supported_requirement_ids,
        "polarity": polarity.value,
        "asserted_object": asserted_object,
        "raw_value": value,
        "canonical_value": value,
        "unit": unit,
        "date_range": None if date_range is None else date_range.model_dump(mode="json"),
        "record_time": None if target.record_time is None else target.record_time.isoformat(),
        "locator_ids": locator_ids,
        "candidate_source_semantics": (
            _SOURCE_STRENGTH_SEMANTICS[target.source_strength]
            if set(locator_ids) == set(target.locator_ids)
            else _CANDIDATE_SEMANTICS
        ),
        "assertion_basis": None
        if assertion_basis is None
        else assertion_basis.model_dump(mode="json"),
        "model_uncertainty": 0.0,
        "created_at": created_at.isoformat(),
    }
    placeholder_gate = "pending-gate"
    fact = ClinicalFactV2(
        fact_id=new_id,
        run_id=target.run_id,
        gate_id=placeholder_gate,
        source_candidate_ids=[],
        gate_ids=[],
        authority=target.authority,
        fact_type=fact_type,
        profile_lane=profile_lane,
        supported_requirement_ids=supported_requirement_ids,
        polarity=polarity,
        asserted_object=asserted_object,
        value=value,
        unit=unit,
        source_strength=(
            target.source_strength
            if locator_ids == list(target.locator_ids)
            else _strength_for_locators(session, target.authority, locator_ids, created_at)
        ),
        date_range=date_range,
        record_time=target.record_time,
        locator_ids=locator_ids,
        assertion_basis=assertion_basis,
        stable_identity=stable,
        revision=revision,
        created_at=created_at,
    )
    replacement = FactReplacementSignature(
        fact_type=fact_type,
        supported_requirement_ids=tuple(supported_requirement_ids),
    )
    return fact, candidate_payload, replacement


def _build_new_event(session, target: ClinicalEventV2, locator_ids, updates, created_at):
    event_type = str(updates.get("event_type") or target.event_type)
    profile_lane = (
        _enum(updates.get("profile_lane"), ProfileLane, "主题泳道") or target.profile_lane
    )
    start_range = (
        target.start_range
        if "start_range" not in updates
        else _date_range_from(updates["start_range"])
    )
    end_range = (
        target.end_range
        if "end_range" not in updates
        else _date_range_from(updates["end_range"])
    )
    duration_status = (
        _enum(updates.get("duration_status"), DurationStatus, "持续状态")
        or target.duration_status
    )
    fact_ids = list(target.fact_ids)
    if "fact_ids" in updates:
        fact_ids = sorted(set(str(item) for item in updates["fact_ids"]))
    referenced = ClinicalFactV2Repository(session)._fact_semantic_objects(fact_ids)
    stable = clinical_event_stable_identity(
        authority=target.authority,
        event_type=event_type,
        profile_lane=profile_lane,
        referenced_fact_objects=referenced,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
    )
    existing = ClinicalEventV2Repository(session).list_for_authority(target.authority)
    revision = (
        target.revision + 1
        if stable == target.stable_identity
        else _next_revision(existing, stable)
    )
    new_id = _stable_id(
        "event",
        {
            "target_id": target.event_id,
            "stable_identity": stable,
            "revision": revision,
        },
    )
    candidate_id = "fcorr-cand-" + canonical_hash({"entity": new_id, "kind": "event"})[:24]
    fact_candidate_ids = ClinicalFactV2Repository(session)._fact_candidate_ids(fact_ids)
    candidate_payload = {
        "candidate_id": candidate_id,
        "event_type": event_type,
        "profile_lane": profile_lane.value,
        "start_range": None if start_range is None else start_range.model_dump(mode="json"),
        "end_range": None if end_range is None else end_range.model_dump(mode="json"),
        "duration_status": duration_status.value,
        "record_time": None if target.record_time is None else target.record_time.isoformat(),
        "fact_candidate_ids": fact_candidate_ids,
        "locator_ids": locator_ids,
        "candidate_source_semantics": _CANDIDATE_SEMANTICS,
        "model_uncertainty": 0.0,
        "created_at": created_at.isoformat(),
        "fact_ids": fact_ids,
        "referenced_fact_objects": referenced,
    }
    event = ClinicalEventV2(
        event_id=new_id,
        run_id=target.run_id,
        gate_id="pending-gate",
        source_candidate_ids=[],
        gate_ids=[],
        authority=target.authority,
        event_type=event_type,
        profile_lane=profile_lane,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
        record_time=target.record_time,
        fact_ids=fact_ids,
        referenced_fact_objects=referenced,
        locator_ids=locator_ids,
        source_strength=_strength_for_locators(
            session, target.authority, locator_ids, created_at
        ),
        stable_identity=stable,
        revision=revision,
        created_at=created_at,
    )
    return event, candidate_payload, None


def _build_new_exposure(session, target: MedicationExposureV2, locator_ids, updates, created_at):
    medication_name = str(updates.get("medication_name") or target.medication_name)
    category = target.category if "category" not in updates else updates["category"]
    indication = target.indication if "indication" not in updates else updates["indication"]
    dose = target.dose if "dose" not in updates else updates["dose"]
    unit = target.unit if "unit" not in updates else updates["unit"]
    frequency = target.frequency if "frequency" not in updates else updates["frequency"]
    route = target.route if "route" not in updates else updates["route"]
    start_range = (
        target.start_range
        if "start_range" not in updates
        else _date_range_from(updates["start_range"])
    )
    end_range = (
        target.end_range
        if "end_range" not in updates
        else _date_range_from(updates["end_range"])
    )
    duration_status = (
        _enum(updates.get("duration_status"), DurationStatus, "持续状态")
        or target.duration_status
    )
    fact_ids = list(target.fact_ids)
    if "fact_ids" in updates:
        fact_ids = sorted(set(str(item) for item in updates["fact_ids"]))
    stable = medication_exposure_stable_identity(
        authority=target.authority,
        medication_name=medication_name,
        category=category,
        indication=indication,
        dose=dose,
        unit=unit,
        frequency=frequency,
        route=route,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
    )
    existing = MedicationExposureV2Repository(session).list_for_authority(target.authority)
    revision = (
        target.revision + 1
        if stable == target.stable_identity
        else _next_revision(existing, stable)
    )
    new_id = _stable_id(
        "exposure",
        {
            "target_id": target.exposure_id,
            "stable_identity": stable,
            "revision": revision,
        },
    )
    candidate_id = "fcorr-cand-" + canonical_hash({"entity": new_id, "kind": "exposure"})[:24]
    fact_candidate_ids = ClinicalFactV2Repository(session)._fact_candidate_ids(fact_ids)
    candidate_payload = {
        "candidate_id": candidate_id,
        "medication_name": medication_name,
        "category": category,
        "indication": indication,
        "dose": dose,
        "unit": unit,
        "frequency": frequency,
        "route": route,
        "start_range": None if start_range is None else start_range.model_dump(mode="json"),
        "end_range": None if end_range is None else end_range.model_dump(mode="json"),
        "duration_status": duration_status.value,
        "record_time": None if target.record_time is None else target.record_time.isoformat(),
        "fact_candidate_ids": fact_candidate_ids,
        "locator_ids": locator_ids,
        "candidate_source_semantics": _CANDIDATE_SEMANTICS,
        "model_uncertainty": 0.0,
        "created_at": created_at.isoformat(),
        "fact_ids": fact_ids,
    }
    exposure = MedicationExposureV2(
        exposure_id=new_id,
        run_id=target.run_id,
        gate_id="pending-gate",
        source_candidate_ids=[],
        gate_ids=[],
        authority=target.authority,
        medication_name=medication_name,
        category=category,
        indication=indication,
        dose=dose,
        unit=unit,
        frequency=frequency,
        route=route,
        start_range=start_range,
        end_range=end_range,
        duration_status=duration_status,
        record_time=target.record_time,
        fact_ids=fact_ids,
        locator_ids=locator_ids,
        source_strength=_strength_for_locators(
            session, target.authority, locator_ids, created_at
        ),
        stable_identity=stable,
        revision=revision,
        created_at=created_at,
    )
    return exposure, candidate_payload, None


def prepared_from_payload(prepared: dict[str, Any]) -> PreparedFactCorrection:
    return PreparedFactCorrection(
        authority=FactAuthority.model_validate(prepared["authority"]),
        target_kind=prepared["target_kind"],
        target_id=prepared["target_id"],
        locator_ids=list(prepared["locator_ids"]),
        reason=prepared["reason"],
        operator_id=prepared["operator_id"],
        created_at=datetime.fromisoformat(prepared["created_at"]),
        run_id=prepared["run_id"],
        call_id=prepared["call_id"],
        candidate_id=prepared["candidate_id"],
        gate_id=prepared["gate_id"],
        new_entity_id=prepared["new_entity_id"],
        new_revision=prepared["new_revision"],
        new_stable_identity=prepared["new_stable_identity"],
        old_snapshot_json=prepared["old_snapshot_json"],
        old_snapshot_sha256=prepared["old_snapshot_sha256"],
        new_snapshot_json=prepared["new_snapshot_json"],
        new_snapshot_sha256=prepared["new_snapshot_sha256"],
        correction_id=prepared["correction_id"],
        idempotency_key=prepared["idempotency_key"],
        proposed_entity=dict(prepared["proposed_entity"]),
        candidate_payload=dict(prepared["candidate_payload"]),
        logical_document_id=prepared["logical_document_id"],
        page_numbers=list(prepared["page_numbers"]),
        prompt_version_id=prepared["prompt_version_id"],
        model_config_id=prepared["model_config_id"],
        input_scope_sha256=prepared["input_scope_sha256"],
        replacement=prepared.get("replacement"),
    )


def prepared_to_payload(prepared: PreparedFactCorrection) -> dict[str, Any]:
    return {
        "authority": prepared.authority.model_dump(mode="json"),
        "target_kind": prepared.target_kind,
        "target_id": prepared.target_id,
        "locator_ids": prepared.locator_ids,
        "reason": prepared.reason,
        "operator_id": prepared.operator_id,
        "created_at": prepared.created_at.isoformat(),
        "run_id": prepared.run_id,
        "call_id": prepared.call_id,
        "candidate_id": prepared.candidate_id,
        "gate_id": prepared.gate_id,
        "new_entity_id": prepared.new_entity_id,
        "new_revision": prepared.new_revision,
        "new_stable_identity": prepared.new_stable_identity,
        "old_snapshot_json": prepared.old_snapshot_json,
        "old_snapshot_sha256": prepared.old_snapshot_sha256,
        "new_snapshot_json": prepared.new_snapshot_json,
        "new_snapshot_sha256": prepared.new_snapshot_sha256,
        "correction_id": prepared.correction_id,
        "idempotency_key": prepared.idempotency_key,
        "proposed_entity": prepared.proposed_entity,
        "candidate_payload": prepared.candidate_payload,
        "logical_document_id": prepared.logical_document_id,
        "page_numbers": prepared.page_numbers,
        "prompt_version_id": prepared.prompt_version_id,
        "model_config_id": prepared.model_config_id,
        "input_scope_sha256": prepared.input_scope_sha256,
        "replacement": prepared.replacement,
    }


def apply_prepared_fact_correction(
    session: Session,
    prepared: PreparedFactCorrection,
    *,
    impact_scope: FactCorrectionImpactScope | None = None,
) -> FactCorrectionApplyResult:
    """在调用方事务内追加新实体、修订记录和新 Profile；不得 commit。"""
    commits = FactCorrectionCommitRepository(session)
    existing_commit = commits.get_optional(prepared.correction_id)
    if existing_commit is not None:
        existing = FactCorrectionRepository(session).get(prepared.correction_id)
        return FactCorrectionApplyResult(
            correction=existing,
            new_entity_id=existing.new_entity_id,
            profile_revision_id=existing_commit.patient_profile_revision_id,
            impact_scope=existing_commit.impact_scope,
            is_replay=True,
        )
    existing = FactCorrectionRepository(session).get_by_idempotency_key(
        prepared.idempotency_key
    )
    if existing is not None:
        raise FactCorrectionError(
            "修订记录已存在但缺少提交栅栏，拒绝把后续病历档案当作本次结果。"
        )

    try:
        _require_authority(session, prepared.authority)
        target = _require_active_correction_head(session, prepared)
        replacement = _replacement_from_prepared(prepared)
        fresh_scope = plan_correction_impact(
            session,
            authority=prepared.authority,
            target_kind=prepared.target_kind,
            target_id=prepared.target_id,
            replacement=replacement,
        )
        scope = _conservative_scope(impact_scope, fresh_scope)
        if (
            scope.scope_kind == "local"
            and not set(prepared.locator_ids) <= set(scope.affected_locator_ids)
        ):
            scope = FactCorrectionImpactScope(
                scope_kind="node",
                fallback_reason=f"{NODE_RECOMPUTE_MESSAGE}：局部影响范围未包含提交引用的全部定位",
            )

        _ensure_correction_run(session, prepared)
        replacement_map = {prepared.target_id: prepared.new_entity_id}
        _publish_primary_entity(session, prepared)
        if prepared.target_kind == "fact":
            replacement_map.update(
                _rewrite_referencing_events_and_exposures(
                    session, prepared, replacement_map
                )
            )
        new_entity = _load_target(session, prepared.target_kind, prepared.new_entity_id)
        published_new_json = canonical_json(
            snapshot_for_kind(prepared.target_kind, new_entity)
        )
        if published_new_json != prepared.new_snapshot_json:
            raise FactCorrectionError(
                "已发布新实体与修订新快照不一致，本次修订没有写入。"
            )
        outcomes = _recompute_conflict_groups(
            session, prepared, scope, replacement_map
        )
        correction = FactCorrectionV2(
            correction_id=prepared.correction_id,
            authority=prepared.authority,
            target_kind=prepared.target_kind,
            target_id=prepared.target_id,
            target_stable_identity=target.stable_identity,
            new_stable_identity=new_entity.stable_identity,
            target_revision=target.revision,
            new_entity_id=prepared.new_entity_id,
            new_revision=new_entity.revision,
            old_snapshot_json=prepared.old_snapshot_json,
            old_snapshot_sha256=prepared.old_snapshot_sha256,
            new_snapshot_json=prepared.new_snapshot_json,
            new_snapshot_sha256=prepared.new_snapshot_sha256,
            reason=prepared.reason,
            locator_ids=prepared.locator_ids,
            operator_id=prepared.operator_id,
            corrected_at=prepared.created_at,
            created_at=prepared.created_at,
            impact_scope=scope,
            idempotency_key=prepared.idempotency_key,
        )
        persisted = FactCorrectionRepository(session).create(correction)
        _rebuild_rule_index(session, prepared, scope)
        _reproject_expectations(session, prepared, scope)
        active_ids = active_entity_ids_after_corrections(session, prepared.authority)
        active_conflict_ids = active_ids["conflict"]
        historical_conflict_ids = {
            item.conflict_group_id
            for item in ClinicalConflictGroupV2Repository(session).list_for_authority(
                prepared.authority
            )
            if item.conflict_group_id not in active_conflict_ids
        }
        historical_expectation_ids = {
            item.expectation_id
            for item in EvidenceExpectationV2Repository(session).list_for_authority(
                prepared.authority
            )
            if item.expectation_id not in active_ids["expectation"]
        }
        profile = PatientProfileService().generate(
            session,
            authority=prepared.authority,
            created_at=prepared.created_at,
            generated_at=prepared.created_at,
            exclude_conflict_group_ids=historical_conflict_ids
            | {item.superseded_conflict_group_id for item in outcomes},
            exclude_expectation_ids=historical_expectation_ids,
        )
        _require_generated_profile_binds_correction(
            profile,
            target_kind=prepared.target_kind,
            new_entity_id=prepared.new_entity_id,
            locator_ids=prepared.locator_ids,
        )
        commits.create(
            FactCorrectionCommitV2(
                correction_id=prepared.correction_id,
                authority=prepared.authority,
                patient_profile_revision_id=profile.patient_profile_revision_id,
                impact_scope=scope,
                conflict_outcomes=outcomes,
                created_at=prepared.created_at,
            )
        )
        return FactCorrectionApplyResult(
            correction=persisted,
            new_entity_id=prepared.new_entity_id,
            profile_revision_id=profile.patient_profile_revision_id,
            impact_scope=scope,
            is_replay=False,
        )
    except FactCorrectionError:
        raise
    except (
        FactRuleIndexError,
        PatientProfileProjectionError,
        EvidenceExpectationProjectionError,
        ExpectationProjectionInputError,
        ProfileProjectionInputError,
        FactCrossEntityError,
        Phase5RepositoryError,
        PersistedContractInvalid,
        ValidationError,
        RepositoryError,
    ) as exc:
        raise FactCorrectionError("本次修订没有写入，已回退全部中间结果。") from exc


def _replacement_from_prepared(
    prepared: PreparedFactCorrection,
) -> FactReplacementSignature | None:
    if prepared.replacement is None:
        return None
    return FactReplacementSignature(
        fact_type=prepared.replacement["fact_type"],
        supported_requirement_ids=tuple(
            prepared.replacement["supported_requirement_ids"]
        ),
    )


def _union_ids(*groups: list[str]) -> list[str]:
    values: set[str] = set()
    for group in groups:
        values.update(group)
    return sorted(values)


def _conservative_scope(
    planned: FactCorrectionImpactScope | None,
    fresh: FactCorrectionImpactScope,
) -> FactCorrectionImpactScope:
    if planned is None:
        return fresh
    if planned.scope_kind == "node" or fresh.scope_kind == "node":
        reason = fresh.fallback_reason or planned.fallback_reason
        if reason is None or reason.strip() == "":
            reason = f"{NODE_RECOMPUTE_MESSAGE}：提交时影响范围无法继续证明局部闭包"
        return FactCorrectionImpactScope(scope_kind="node", fallback_reason=reason)
    return FactCorrectionImpactScope(
        scope_kind="local",
        affected_locator_ids=_union_ids(
            planned.affected_locator_ids, fresh.affected_locator_ids
        ),
        affected_document_ids=_union_ids(
            planned.affected_document_ids, fresh.affected_document_ids
        ),
        affected_fact_ids=_union_ids(planned.affected_fact_ids, fresh.affected_fact_ids),
        affected_event_ids=_union_ids(
            planned.affected_event_ids, fresh.affected_event_ids
        ),
        affected_exposure_ids=_union_ids(
            planned.affected_exposure_ids, fresh.affected_exposure_ids
        ),
        affected_conflict_group_ids=_union_ids(
            planned.affected_conflict_group_ids, fresh.affected_conflict_group_ids
        ),
        affected_rule_link_ids=_union_ids(
            planned.affected_rule_link_ids, fresh.affected_rule_link_ids
        ),
        affected_expectation_ids=_union_ids(
            planned.affected_expectation_ids, fresh.affected_expectation_ids
        ),
        affected_profile_revision_ids=_union_ids(
            planned.affected_profile_revision_ids, fresh.affected_profile_revision_ids
        ),
    )


def _entity_pk(kind: str, entity) -> str:
    if kind == "fact":
        return entity.fact_id
    if kind == "event":
        return entity.event_id
    if kind == "exposure":
        return entity.exposure_id
    raise FactCorrectionValidationError(f"不支持的修订目标类型 {kind}")


def _rebuild_rule_index(
    session: Session,
    prepared: PreparedFactCorrection,
    scope: FactCorrectionImpactScope,
) -> None:
    try:
        FactRuleLinkV2Repository(session).rebuild_for_authority(prepared.authority)
    except FactRuleIndexError:
        if scope.scope_kind == "node" or scope.affected_rule_link_ids:
            raise


def _reproject_expectations(
    session: Session,
    prepared: PreparedFactCorrection,
    scope: FactCorrectionImpactScope,
) -> None:
    template_ids = None
    if scope.scope_kind == "local":
        expectations = EvidenceExpectationV2Repository(session).list_for_authority(
            prepared.authority
        )
        template_ids = {
            item.template_id
            for item in expectations
            if item.expectation_id in set(scope.affected_expectation_ids)
        }
        if not template_ids and scope.affected_expectation_ids:
            raise FactCorrectionError(
                "局部影响范围声明了资料期望，但当前权威下找不到对应模板，拒绝提交。"
            )
    # 与原始终结共用同一信号推导：从所选源运行的持久化未解决项/事务门禁重建
    # 结构化缺口，按到期模板补 fallback 兜底，并保守保留无法按源记录复核的
    # 先期显式风险。绝不静默以空信号重投影。
    try:
        gap_signals = reconstruct_reprojection_gap_signals(
            session,
            authority=prepared.authority,
            target_kind=prepared.target_kind,
            target_id=prepared.target_id,
        )
    except ReprojectionLineageError as exc:
        raise FactCorrectionError(
            f"修订谱系无法按不可变记录追溯，拒绝重投影资料期望：{exc}"
        ) from exc
    except StepFailure as exc:
        raise FactCorrectionError(
            f"修订重投影无法从源记录重建结构化缺口信号：{exc}"
        ) from exc
    EvidenceExpectationProjectionService().project(
        session,
        authority=prepared.authority,
        gap_signals=gap_signals,
        created_at=prepared.created_at,
        template_ids=template_ids,
        exclude_fact_ids=superseded_entity_ids(session, prepared.authority),
    )


def _require_locator_page_artifact_consistency(
    session: Session, locator_ids: list[str]
) -> None:
    """Phase 4 locator 身份不可变：页码必须与页工件一致，否则拒绝引用。"""
    from app.storage.evidence_locator_repositories import LocatorIdentityError

    locator_repo = EvidenceLocatorRepository(session)
    for locator_id in locator_ids:
        try:
            locator = locator_repo.get(locator_id)
        except LocatorIdentityError as exc:
            raise FactCorrectionValidationError(
                "修订引用的原文定位页码与页工件不一致，拒绝提交。"
            ) from exc
        page = session.get(PageArtifactRecord, locator.page_artifact_id)
        if page is None:
            raise FactCorrectionValidationError(
                "修订引用的原文定位缺少页工件，无法安全回源。"
            )
        if page.page_number != locator.page_number:
            raise FactCorrectionValidationError(
                "修订引用的原文定位页码与页工件不一致，拒绝提交。"
            )
        if page.source_document_version_id != locator.source_document_version_id:
            raise FactCorrectionValidationError(
                "修订引用的原文定位资料版本与页工件不一致，拒绝提交。"
            )


def _require_generated_profile_binds_correction(
    profile,
    *,
    target_kind: str,
    new_entity_id: str,
    locator_ids: list[str],
) -> None:
    """提交栅栏只能绑定本次修订生成的档案：必须含新实体及其提交定位。"""
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind

    kind_map = {
        "fact": ProfileItemKind.FACT,
        "event": ProfileItemKind.EVENT,
        "exposure": ProfileItemKind.EXPOSURE,
    }
    expected_kind = kind_map[target_kind]
    matches = [
        item
        for item in profile_items(profile)
        if item.kind == expected_kind and item.source_id == new_entity_id
    ]
    if not matches:
        raise FactCorrectionError(
            "本次修订生成的病历档案未包含新实体，拒绝写入提交栅栏。"
        )
    item = matches[0]
    missing = sorted(set(locator_ids) - set(item.locator_ids))
    if missing:
        raise FactCorrectionError(
            "本次修订生成的病历档案未绑定提交引用的全部定位，拒绝写入提交栅栏。"
        )


def _require_active_correction_head(session: Session, prepared: PreparedFactCorrection):
    corrections = FactCorrectionRepository(session)
    outgoing = corrections.outgoing(prepared.target_id)
    if outgoing is not None:
        raise FactCorrectionValidationError("该记录已被修订，不能再从同一原记录分叉。")
    target = _load_target(session, prepared.target_kind, prepared.target_id)
    old_json = canonical_json(snapshot_for_kind(prepared.target_kind, target))
    if old_json != prepared.old_snapshot_json:
        raise FactCorrectionStaleError("原记录内容已变化，本次修订没有写入。")
    if prepared.target_kind == "fact":
        repo = ClinicalFactV2Repository(session)
    elif prepared.target_kind == "event":
        repo = ClinicalEventV2Repository(session)
    else:
        repo = MedicationExposureV2Repository(session)
    bound = [
        item
        for item in repo.list_for_authority(prepared.authority)
        if item.stable_identity == target.stable_identity
    ]
    head = max(bound, key=lambda item: item.revision)
    if _entity_pk(prepared.target_kind, head) != prepared.target_id:
        raise FactCorrectionValidationError("修订目标已不是当前活动链头，不能提交陈旧修订。")
    return target


def _follow_entity_id(session: Session, entity_id: str, overlay: dict[str, str]) -> str:
    current = overlay.get(entity_id, entity_id)
    seen: set[str] = set()
    corrections = FactCorrectionRepository(session)
    while current not in seen:
        seen.add(current)
        outgoing = corrections.outgoing(current)
        if outgoing is None:
            return overlay.get(current, current)
        current = overlay.get(outgoing.new_entity_id, outgoing.new_entity_id)
    raise FactCorrectionError("修订链出现循环，拒绝提交。")


def _scalar(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _conflict_signature(item: Any) -> tuple[Any, ...]:
    """冲突显著性签名：临床身份/值/极性/日期/持续状态，不含定位/门禁/强度/时间戳。"""
    if isinstance(item, ClinicalFactV2):
        return (
            "fact",
            item.fact_type,
            item.asserted_object,
            _scalar(item.polarity),
            item.value,
            item.unit,
            _scalar(item.profile_lane),
            canonical_json(_date_range_identity(item.date_range) or {}),
        )
    if isinstance(item, ClinicalEventV2):
        return (
            "event",
            item.event_type,
            tuple(item.referenced_fact_objects),
            _scalar(item.profile_lane),
            canonical_json(_date_range_identity(item.start_range) or {}),
            canonical_json(_date_range_identity(item.end_range) or {}),
            _scalar(item.duration_status),
        )
    if isinstance(item, MedicationExposureV2):
        return (
            "exposure",
            item.medication_name,
            item.category,
            item.indication,
            item.dose,
            item.unit,
            item.frequency,
            item.route,
            canonical_json(_date_range_identity(item.start_range) or {}),
            canonical_json(_date_range_identity(item.end_range) or {}),
            _scalar(item.duration_status),
        )
    raise FactCorrectionError("冲突成员类型无法形成可比对的临床签名。")


def _published_still_conflict(members: list[Any]) -> bool:
    if len(members) < 2:
        return False
    kinds = {type(item) for item in members}
    if len(kinds) != 1:
        return True
    return len({_conflict_signature(item) for item in members}) > 1


def _recompute_conflict_groups(
    session: Session,
    prepared: PreparedFactCorrection,
    scope: FactCorrectionImpactScope,
    replacement_map: dict[str, str],
) -> list[ConflictCorrectionOutcome]:
    from app.storage.active_conflicts import current_conflict_heads
    groups = current_conflict_heads(session, prepared.authority)
    already_superseded = FactCorrectionCommitRepository(session).superseded_conflict_ids(
        prepared.authority
    )
    if scope.scope_kind == "node":
        selected = [
            group
            for group in groups
            if group.conflict_group_id not in already_superseded
        ]
    else:
        wanted = set(scope.affected_conflict_group_ids)
        selected = [
            group
            for group in groups
            if group.conflict_group_id not in already_superseded
            and (
                group.conflict_group_id in wanted
                or prepared.target_id in group.fact_ids
                or prepared.target_id in group.event_ids
                or prepared.target_id in group.exposure_ids
            )
        ]
    outcomes: list[ConflictCorrectionOutcome] = []
    for group in selected:
        member_ids = {
            "fact": group.fact_ids,
            "event": group.event_ids,
            "exposure": group.exposure_ids,
        }[group.member_kind]
        remapped = sorted(
            {
                _follow_entity_id(session, member_id, replacement_map)
                for member_id in member_ids
            }
        )
        members = [
            _load_target(session, group.member_kind, member_id) for member_id in remapped
        ]
        lineage_changed = remapped != list(member_ids)
        still_conflict = _published_still_conflict(members)
        if not lineage_changed:
            continue
        successor_id = None
        if still_conflict:
            successor_id = _append_successor_conflict(
                session, prepared, group, remapped
            )
        outcomes.append(
            ConflictCorrectionOutcome(
                superseded_conflict_group_id=group.conflict_group_id,
                successor_conflict_group_id=successor_id,
            )
        )
    return sorted(outcomes, key=lambda item: item.superseded_conflict_group_id)


def _append_successor_conflict(
    session: Session,
    prepared: PreparedFactCorrection,
    group: ClinicalConflictGroupV2,
    member_ids: list[str],
) -> str:
    locators = sorted(
        {
            locator_id
            for member_id in member_ids
            for locator_id in _load_target(
                session, group.member_kind, member_id
            ).locator_ids
        }
    )
    successor_id = "conflict:" + canonical_hash(
        {
            "correction_id": prepared.correction_id,
            "superseded": group.conflict_group_id,
            "member_ids": member_ids,
        }
    )[:32]
    try:
        ClinicalConflictGroupV2Repository(session).get(successor_id)
        return successor_id
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        pass
    current_members = [
        _load_target(session, group.member_kind, member_id) for member_id in member_ids
    ]
    chosen = min(
        current_members,
        key=lambda item: (_entity_pk(group.member_kind, item), item.gate_id),
    )
    successor = ClinicalConflictGroupV2(
        conflict_group_id=successor_id,
        run_id=chosen.run_id,
        gate_id=chosen.gate_id,
        authority=prepared.authority,
        member_kind=group.member_kind,
        fact_ids=member_ids if group.member_kind == "fact" else [],
        event_ids=member_ids if group.member_kind == "event" else [],
        exposure_ids=member_ids if group.member_kind == "exposure" else [],
        locator_ids=locators,
        created_at=prepared.created_at,
    )
    ClinicalConflictGroupV2Repository(session).create(successor)
    return successor_id


def _ensure_correction_run(session: Session, prepared: PreparedFactCorrection) -> None:
    run = FactNormalizationRun(
        run_id=prepared.run_id,
        authority=prepared.authority,
        idempotency_key=fact_run_idempotency_key(
            authority=prepared.authority,
            prompt_version_id=prepared.prompt_version_id,
            model_config_id=prepared.model_config_id,
            input_scope_sha256=prepared.input_scope_sha256,
        ),
        prompt_version_id=prepared.prompt_version_id,
        model_config_id=prepared.model_config_id,
        input_scope_sha256=prepared.input_scope_sha256,
        status=FactNormalizationRunStatus.SUCCEEDED,
        created_at=prepared.created_at,
        created_by=prepared.operator_id,
    )
    FactNormalizationRunRepository(session).create_or_reuse(run)
    try:
        FactNormalizationCallRepository(session).get(prepared.call_id)
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        FactNormalizationCallRepository(session).create(
            FactNormalizationCall(
                call_id=prepared.call_id,
                run_id=prepared.run_id,
                logical_document_id=prepared.logical_document_id,
                page_numbers=prepared.page_numbers,
                status=FactCallStatus.SUCCEEDED,
                input_sha256=prepared.input_scope_sha256,
                created_at=prepared.created_at,
            )
        )


def _publish_primary_entity(session: Session, prepared: PreparedFactCorrection) -> None:
    try:
        if prepared.target_kind == "fact":
            ClinicalFactV2Repository(session).get(prepared.new_entity_id)
        elif prepared.target_kind == "event":
            ClinicalEventV2Repository(session).get(prepared.new_entity_id)
        else:
            MedicationExposureV2Repository(session).get(prepared.new_entity_id)
        return
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        pass
    candidate = _candidate_from_payload(prepared)
    try:
        FactNormalizationCandidateRepository(session).get(prepared.candidate_id)
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        FactNormalizationCandidateRepository(session).create(prepared.call_id, candidate)
    try:
        FactGateResultRepository(session).get(prepared.gate_id)
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        FactGateResultRepository(session).create(
            FactGateResult(
                gate_result_id=prepared.gate_id,
                run_id=prepared.run_id,
                call_id=prepared.call_id,
                candidate_id=prepared.candidate_id,
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                created_at=prepared.created_at,
            )
        )
    entity_payload = dict(prepared.proposed_entity)
    target = _load_target(session, prepared.target_kind, prepared.target_id)
    if set(candidate.locator_ids) == set(target.locator_ids):
        source_strength = target.source_strength
    else:
        try:
            source_strength = _derive_strength(session, prepared.authority, candidate)
        except (
            ValueError,
            RepositoryError,
            InvalidReferenceError,
            NotFoundError,
            PersistedContractInvalid,
            ValidationError,
        ) as exc:
            raise FactCorrectionValidationError(
                "修订引用的原文定位缺少完整处理修订中的资料类型，无法确认来源强度。"
            ) from exc
    entity_payload["source_strength"] = source_strength.value
    if prepared.target_kind == "fact":
        ClinicalFactV2Repository(session).create(ClinicalFactV2.model_validate(entity_payload))
    elif prepared.target_kind == "event":
        ClinicalEventV2Repository(session).create(
            ClinicalEventV2.model_validate(entity_payload)
        )
    else:
        MedicationExposureV2Repository(session).create(
            MedicationExposureV2.model_validate(entity_payload)
        )


def _candidate_from_payload(prepared: PreparedFactCorrection):
    payload = dict(prepared.candidate_payload)
    payload["run_id"] = prepared.run_id
    payload["call_id"] = prepared.call_id
    payload["created_at"] = prepared.created_at
    if prepared.target_kind == "fact":
        payload["record_time"] = (
            None
            if payload.get("record_time") is None
            else datetime.fromisoformat(str(payload["record_time"]).replace("Z", "+00:00"))
        )
        if isinstance(payload.get("date_range"), dict):
            payload["date_range"] = PartialDateRange.model_validate(payload["date_range"])
        if isinstance(payload.get("assertion_basis"), dict):
            payload["assertion_basis"] = AssertionBasis.model_validate(
                payload["assertion_basis"]
            )
        payload["polarity"] = FactPolarity(payload["polarity"])
        payload["profile_lane"] = ProfileLane(payload["profile_lane"])
        return ClinicalFactCandidateV2.model_validate(
            {key: value for key, value in payload.items() if key not in {"fact_ids", "referenced_fact_objects"}}
        )
    payload["record_time"] = (
        None
        if payload.get("record_time") is None
        else datetime.fromisoformat(str(payload["record_time"]).replace("Z", "+00:00"))
    )
    for field in ("start_range", "end_range"):
        if isinstance(payload.get(field), dict):
            payload[field] = PartialDateRange.model_validate(payload[field])
    payload["duration_status"] = DurationStatus(payload["duration_status"])
    if "profile_lane" in payload:
        payload["profile_lane"] = ProfileLane(payload["profile_lane"])
    if prepared.target_kind == "event":
        return ClinicalEventCandidateV2.model_validate(
            {
                key: value
                for key, value in payload.items()
                if key not in {"fact_ids", "referenced_fact_objects"}
            }
        )
    return MedicationExposureCandidateV2.model_validate(
        {key: value for key, value in payload.items() if key not in {"fact_ids"}}
    )


def _derive_strength(session: Session, authority: FactAuthority, candidate) -> SourceStrength:
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(
        authority.complete_processing_revision_id
    )
    return derive_source_strength_for_candidate(session, candidate, revision)


def _strength_for_locators(
    session: Session,
    authority: FactAuthority,
    locator_ids: list[str],
    created_at: datetime,
) -> SourceStrength:
    candidate = ClinicalFactCandidateV2(
        candidate_id="strength-probe",
        run_id="strength-probe-run",
        call_id="strength-probe-call",
        fact_type="probe",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="probe",
        raw_value="1",
        canonical_value="1",
        unit="unitless",
        locator_ids=locator_ids,
        candidate_source_semantics=_CANDIDATE_SEMANTICS,
        assertion_basis=AssertionBasis(
            asserted_object="probe",
            assertion_text="probe",
            locator_id=locator_ids[0],
            source_text_sha256=EvidenceLocatorRepository(session).get(
                locator_ids[0]
            ).source_text_sha256,
        ),
        model_uncertainty=0.0,
        created_at=created_at,
    )
    try:
        return _derive_strength(session, authority, candidate)
    except (
        ValueError,
        RepositoryError,
        InvalidReferenceError,
        NotFoundError,
        PersistedContractInvalid,
        ValidationError,
    ) as exc:
        raise FactCorrectionValidationError(
            "修订引用的原文定位缺少完整处理修订中的资料类型，无法确认来源强度。"
        ) from exc


def _rewrite_referencing_events_and_exposures(
    session: Session,
    prepared: PreparedFactCorrection,
    replacement_map: dict[str, str],
) -> dict[str, str]:
    """事实修订后，为仍引用旧事实 ID 的事件/暴露追加新 revision，保证 Profile 引用闭合。"""
    extra: dict[str, str] = {}
    new_fact = ClinicalFactV2Repository(session).get(prepared.new_entity_id)
    events = ClinicalEventV2Repository(session).list_for_authority(prepared.authority)
    for event in events:
        if prepared.target_id not in event.fact_ids:
            continue
        if event.event_id in superseded_entity_ids(session, prepared.authority):
            continue
        new_fact_ids = sorted(
            {replacement_map.get(fact_id, fact_id) for fact_id in event.fact_ids}
        )
        if new_fact_ids == list(event.fact_ids):
            continue
        rewritten = _rewrite_event(session, prepared, event, new_fact_ids, new_fact)
        extra[event.event_id] = rewritten
    exposures = MedicationExposureV2Repository(session).list_for_authority(
        prepared.authority
    )
    for exposure in exposures:
        if prepared.target_id not in exposure.fact_ids:
            continue
        if exposure.exposure_id in superseded_entity_ids(session, prepared.authority):
            continue
        new_fact_ids = sorted(
            {replacement_map.get(fact_id, fact_id) for fact_id in exposure.fact_ids}
        )
        if new_fact_ids == list(exposure.fact_ids):
            continue
        rewritten = _rewrite_exposure(session, prepared, exposure, new_fact_ids, new_fact)
        extra[exposure.exposure_id] = rewritten
    return extra


def _rewrite_event(session, prepared, event: ClinicalEventV2, fact_ids, new_fact):
    referenced = ClinicalFactV2Repository(session)._fact_semantic_objects(fact_ids)
    fact_locators = set().union(
        *(
            set(ClinicalFactV2Repository(session).get(fid).locator_ids)
            for fid in fact_ids
        )
    )
    locators = sorted(set(event.locator_ids) & fact_locators)
    if not locators:
        locators = list(new_fact.locator_ids)
    stable = clinical_event_stable_identity(
        authority=event.authority,
        event_type=event.event_type,
        profile_lane=event.profile_lane,
        referenced_fact_objects=referenced,
        start_range=event.start_range,
        end_range=event.end_range,
        duration_status=event.duration_status,
    )
    existing = ClinicalEventV2Repository(session).list_for_authority(event.authority)
    revision = (
        event.revision + 1
        if stable == event.stable_identity
        else _next_revision(existing, stable)
    )
    new_id = _stable_id(
        "event",
        {
            "cascade_of": prepared.correction_id,
            "target_id": event.event_id,
            "stable_identity": stable,
            "revision": revision,
        },
    )
    try:
        ClinicalEventV2Repository(session).get(new_id)
        return new_id
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        pass
    cascade = _cascade_ids(prepared, "event", event.event_id)
    fact_candidate_ids = ClinicalFactV2Repository(session)._fact_candidate_ids(fact_ids)
    candidate = ClinicalEventCandidateV2(
        candidate_id=cascade["candidate_id"],
        run_id=prepared.run_id,
        call_id=prepared.call_id,
        event_type=event.event_type,
        profile_lane=event.profile_lane,
        start_range=event.start_range,
        end_range=event.end_range,
        duration_status=event.duration_status,
        record_time=event.record_time,
        fact_candidate_ids=fact_candidate_ids,
        locator_ids=locators,
        candidate_source_semantics=_CANDIDATE_SEMANTICS,
        model_uncertainty=0.0,
        created_at=prepared.created_at,
    )
    _persist_candidate_and_gate(session, prepared, cascade, candidate)
    source_strength = _derive_strength(session, prepared.authority, candidate)
    ClinicalEventV2Repository(session).create(
        ClinicalEventV2(
            event_id=new_id,
            run_id=prepared.run_id,
            gate_id=cascade["gate_id"],
            source_candidate_ids=[cascade["candidate_id"]],
            gate_ids=[cascade["gate_id"]],
            authority=event.authority,
            event_type=event.event_type,
            profile_lane=event.profile_lane,
            start_range=event.start_range,
            end_range=event.end_range,
            duration_status=event.duration_status,
            record_time=event.record_time,
            fact_ids=fact_ids,
            referenced_fact_objects=referenced,
            locator_ids=locators,
            source_strength=source_strength,
            stable_identity=stable,
            revision=revision,
            created_at=prepared.created_at,
        )
    )
    return new_id


def _rewrite_exposure(session, prepared, exposure: MedicationExposureV2, fact_ids, new_fact):
    locators = sorted(
        set(exposure.locator_ids)
        & set().union(
            *(
                set(ClinicalFactV2Repository(session).get(fid).locator_ids)
                for fid in fact_ids
            )
        )
    )
    if not locators:
        locators = list(new_fact.locator_ids)
    stable = medication_exposure_stable_identity(
        authority=exposure.authority,
        medication_name=exposure.medication_name,
        category=exposure.category,
        indication=exposure.indication,
        dose=exposure.dose,
        unit=exposure.unit,
        frequency=exposure.frequency,
        route=exposure.route,
        start_range=exposure.start_range,
        end_range=exposure.end_range,
        duration_status=exposure.duration_status,
    )
    existing = MedicationExposureV2Repository(session).list_for_authority(exposure.authority)
    revision = (
        exposure.revision + 1
        if stable == exposure.stable_identity
        else _next_revision(existing, stable)
    )
    new_id = _stable_id(
        "exposure",
        {
            "cascade_of": prepared.correction_id,
            "target_id": exposure.exposure_id,
            "stable_identity": stable,
            "revision": revision,
        },
    )
    try:
        MedicationExposureV2Repository(session).get(new_id)
        return new_id
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        pass
    cascade = _cascade_ids(prepared, "exposure", exposure.exposure_id)
    fact_candidate_ids = ClinicalFactV2Repository(session)._fact_candidate_ids(fact_ids)
    candidate = MedicationExposureCandidateV2(
        candidate_id=cascade["candidate_id"],
        run_id=prepared.run_id,
        call_id=prepared.call_id,
        medication_name=exposure.medication_name,
        category=exposure.category,
        indication=exposure.indication,
        dose=exposure.dose,
        unit=exposure.unit,
        frequency=exposure.frequency,
        route=exposure.route,
        start_range=exposure.start_range,
        end_range=exposure.end_range,
        duration_status=exposure.duration_status,
        record_time=exposure.record_time,
        fact_candidate_ids=fact_candidate_ids,
        locator_ids=locators,
        candidate_source_semantics=_CANDIDATE_SEMANTICS,
        model_uncertainty=0.0,
        created_at=prepared.created_at,
    )
    _persist_candidate_and_gate(session, prepared, cascade, candidate)
    source_strength = _derive_strength(session, prepared.authority, candidate)
    MedicationExposureV2Repository(session).create(
        MedicationExposureV2(
            exposure_id=new_id,
            run_id=prepared.run_id,
            gate_id=cascade["gate_id"],
            source_candidate_ids=[cascade["candidate_id"]],
            gate_ids=[cascade["gate_id"]],
            authority=exposure.authority,
            medication_name=exposure.medication_name,
            category=exposure.category,
            indication=exposure.indication,
            dose=exposure.dose,
            unit=exposure.unit,
            frequency=exposure.frequency,
            route=exposure.route,
            start_range=exposure.start_range,
            end_range=exposure.end_range,
            duration_status=exposure.duration_status,
            record_time=exposure.record_time,
            fact_ids=fact_ids,
            locator_ids=locators,
            source_strength=source_strength,
            stable_identity=stable,
            revision=revision,
            created_at=prepared.created_at,
        )
    )
    return new_id


def _cascade_ids(prepared: PreparedFactCorrection, kind: str, source_id: str) -> dict[str, str]:
    material = {
        "correction_id": prepared.correction_id,
        "kind": kind,
        "source_id": source_id,
    }
    return {
        "candidate_id": "fcorr-cand-" + canonical_hash({**material, "part": "cand"})[:24],
        "gate_id": "fcorr-gate-" + canonical_hash({**material, "part": "gate"})[:24],
    }


def _persist_candidate_and_gate(session, prepared, cascade, candidate) -> None:
    try:
        FactNormalizationCandidateRepository(session).get(cascade["candidate_id"])
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        FactNormalizationCandidateRepository(session).create(prepared.call_id, candidate)
    try:
        FactGateResultRepository(session).get(cascade["gate_id"])
    except (NotFoundError, InvalidReferenceError, Phase5RepositoryError):
        FactGateResultRepository(session).create(
            FactGateResult(
                gate_result_id=cascade["gate_id"],
                run_id=prepared.run_id,
                call_id=prepared.call_id,
                candidate_id=cascade["candidate_id"],
                gate=FactGate.TRANSACTIONAL_PUBLISH,
                outcome=GateOutcome.ACCEPTED,
                reasons=[],
                created_at=prepared.created_at,
            )
        )
