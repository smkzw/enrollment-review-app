"""Phase 5 事实事务发布。

本服务只组装已通过最终事务门禁的候选，所有写入仍经正式仓储复核
权威元组、来源强度、定位并集和事实引用闭包。事务边界由持久任务执行器拥有；
本服务不 commit、rollback，也不直接写 ORM 表。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy.orm import Session

from app.domain.contracts.enums import FactGate, GateOutcome, ProfileLane, SourceStrength
from app.domain.contracts.facts import (
    ClinicalConflictGroupV2,
    ClinicalEventCandidateV2,
    ClinicalEventV2,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    MedicationExposureCandidateV2,
    MedicationExposureV2,
    clinical_event_stable_identity,
    clinical_fact_stable_identity,
    medication_exposure_stable_identity,
)
from app.domain.gates.fact_evidence_closure import resolve_source_strength_for_candidate
from app.domain.gates.fact_batch_orchestration import detect_semantic_conflicts
from app.domain.publication import canonical_hash
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
)
from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    MedicationExposureV2Repository,
)


class FactPublicationError(RuntimeError):
    """发布输入不完整或跨实体引用无法闭合。"""


class FactPublicationStaleAuthorityError(FactPublicationError):
    """活动权威指针已变化，拒绝陈旧发布。"""


@dataclass(frozen=True)
class FactPublicationResult:
    run_id: str
    authority: FactAuthority
    fact_ids: list[str]
    event_ids: list[str]
    exposure_ids: list[str]
    conflict_group_ids: list[str]
    is_replay: bool = False


CandidateT = TypeVar(
    "CandidateT",
    ClinicalFactCandidateV2,
    ClinicalEventCandidateV2,
    MedicationExposureCandidateV2,
)


def _group_by_identity(candidates: list[CandidateT], identity_for):
    grouped: dict[str, list[CandidateT]] = {}
    for candidate in candidates:
        grouped.setdefault(identity_for(candidate), []).append(candidate)
    return {
        identity: sorted(group, key=lambda item: item.candidate_id)
        for identity, group in sorted(grouped.items())
    }


def _reject_profile_lane_conflicts(
    candidates,
    existing,
    authority,
    semantic_identity_for,
    existing_semantic_identity_for,
    label: str,
) -> None:
    """Reject duplicate clinical semantics assigned to different Profile lanes.

    ``profile_lane`` participates in the published stable identity so that a lane change is
    revision-significant. It must not, however, turn one semantic candidate into duplicate
    published entities. Existing entities under the same frozen authority are included, so a
    later run cannot duplicate a fact/event merely by moving it. Ambiguous classification is
    an explicit normalization defect, not a second clinical fact/event.
    """
    lanes_by_semantic_identity: dict[str, set[ProfileLane]] = {}
    for entity in existing:
        if entity.authority == authority:
            lanes_by_semantic_identity.setdefault(
                existing_semantic_identity_for(entity), set()
            ).add(entity.profile_lane)
    for candidate in candidates:
        lanes_by_semantic_identity.setdefault(
            semantic_identity_for(candidate), set()
        ).add(candidate.profile_lane)
    conflicts = [
        sorted(lane.value for lane in lanes)
        for lanes in lanes_by_semantic_identity.values()
        if len(lanes) > 1
    ]
    if conflicts:
        rendered = ", ".join("/".join(lanes) for lanes in sorted(conflicts))
        raise FactPublicationError(
            f"同一{label}候选的 Patient Profile 主题归属冲突：{rendered}"
        )


def _locator_union(candidates) -> list[str]:
    return sorted(
        {locator_id for candidate in candidates for locator_id in candidate.locator_ids}
    )


def _requirement_union(candidates: list[ClinicalFactCandidateV2]) -> list[str]:
    return sorted(
        {
            requirement_id
            for candidate in candidates
            for requirement_id in candidate.supported_requirement_ids
        }
    )


def _common_record_time(candidates):
    values = {candidate.record_time for candidate in candidates}
    return next(iter(values)) if len(values) == 1 else None


def _source_strength(session, revision, candidates) -> SourceStrength:
    rank = {
        SourceStrength.UNVERIFIABLE: 0,
        SourceStrength.SCREENING_RECORD_TRANSCRIPTION: 1,
        SourceStrength.CURRENT_STUDY_CHART: 2,
        SourceStrength.HISTORICAL_PRIMARY: 3,
        SourceStrength.CONTEMPORANEOUS_OBJECTIVE: 4,
    }
    return max(
        (
            resolve_source_strength_for_candidate(session, candidate, revision)
            for candidate in candidates
        ),
        key=rank.__getitem__,
    )


def _next_revision(entities, stable_identity: str) -> int:
    chain = [item.revision for item in entities if item.stable_identity == stable_identity]
    return max(chain, default=0) + 1


def _entity_id(run_id: str, kind: str, stable_identity: str, revision: int) -> str:
    return f"{kind}:" + canonical_hash(
        {"run_id": run_id, "stable_identity": stable_identity, "revision": revision}
    )[:32]


class FactPublicationService:
    """将最终门禁已接受的候选发布为不可变实体。"""

    def publish(self, session: Session, run_id: str) -> FactPublicationResult:
        run = FactNormalizationRunRepository(session).get(run_id)
        authority = run.authority
        validator = FactAuthorityValidator(session)
        try:
            validator.validate(authority)
        except FactAuthorityError as exc:
            raise FactPublicationStaleAuthorityError(str(exc)) from exc
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(
            authority.complete_processing_revision_id
        )

        repository_options = {
            "authority_validator": validator,
            "complete_revision": revision,
        }
        fact_repository = ClinicalFactV2Repository(session, **repository_options)
        event_repository = ClinicalEventV2Repository(session, **repository_options)
        exposure_repository = MedicationExposureV2Repository(session, **repository_options)
        conflict_repository = ClinicalConflictGroupV2Repository(
            session, **repository_options
        )
        existing_facts = fact_repository.list_by_episode(authority.review_episode_id)
        existing_events = event_repository.list_by_episode(authority.review_episode_id)
        existing_exposures = exposure_repository.list_by_episode(authority.review_episode_id)
        existing_conflicts = conflict_repository.list_by_episode(authority.review_episode_id)
        superseded_entity_ids = {
            item.target_id
            for item in FactCorrectionRepository(session).list_by_authority(authority)
        }
        existing_facts = [
            item for item in existing_facts if item.fact_id not in superseded_entity_ids
        ]
        existing_events = [
            item for item in existing_events if item.event_id not in superseded_entity_ids
        ]
        existing_exposures = [
            item
            for item in existing_exposures
            if item.exposure_id not in superseded_entity_ids
        ]
        candidates = FactNormalizationCandidateRepository(session).list_by_run(run_id)
        gate_results = FactGateResultRepository(session).list_by_run(run_id)
        final_gates = [
            result for result in gate_results if result.gate == FactGate.TRANSACTIONAL_PUBLISH
        ]
        gate_by_candidate = {result.candidate_id: result for result in final_gates}
        if len(gate_by_candidate) != len(final_gates) or set(gate_by_candidate) != {
            candidate.candidate_id for candidate in candidates
        }:
            raise FactPublicationError(
                "最终事务发布门禁必须不重不漏覆盖当前运行全部候选"
            )
        accepted = [
            candidate
            for candidate in candidates
            if gate_by_candidate[candidate.candidate_id].outcome == GateOutcome.ACCEPTED
        ]
        replay = self._replay_if_published(
            run_id,
            authority,
            accepted,
            existing_facts,
            existing_events,
            existing_exposures,
            existing_conflicts,
        )
        if replay is not None:
            validator.validate(authority)
            return replay
        fact_candidates = [
            item for item in accepted if isinstance(item, ClinicalFactCandidateV2)
        ]
        event_candidates = [
            item for item in accepted if isinstance(item, ClinicalEventCandidateV2)
        ]
        exposure_candidates = [
            item for item in accepted if isinstance(item, MedicationExposureCandidateV2)
        ]
        created_at = datetime.now(UTC)

        published_facts, candidate_to_fact = self._publish_facts(
            session=session,
            authority=authority,
            run_id=run_id,
            revision=revision,
            candidates=fact_candidates,
            gates=gate_by_candidate,
            existing=existing_facts,
            created_at=created_at,
            repository=fact_repository,
        )
        published_events, candidate_to_event = self._publish_events(
            session=session,
            authority=authority,
            run_id=run_id,
            revision=revision,
            candidates=event_candidates,
            gates=gate_by_candidate,
            facts=published_facts,
            candidate_to_fact=candidate_to_fact,
            existing=existing_events,
            created_at=created_at,
            repository=event_repository,
        )
        published_exposures, candidate_to_exposure = self._publish_exposures(
            session=session,
            authority=authority,
            run_id=run_id,
            revision=revision,
            candidates=exposure_candidates,
            gates=gate_by_candidate,
            candidate_to_fact=candidate_to_fact,
            existing=existing_exposures,
            created_at=created_at,
            repository=exposure_repository,
        )
        published_conflicts = self._publish_conflicts(
            authority=authority,
            run_id=run_id,
            fact_candidates=fact_candidates,
            event_candidates=event_candidates,
            exposure_candidates=exposure_candidates,
            candidate_to_fact=candidate_to_fact,
            candidate_to_event=candidate_to_event,
            candidate_to_exposure=candidate_to_exposure,
            facts=published_facts,
            events=published_events,
            exposures=published_exposures,
            gate_by_candidate=gate_by_candidate,
            created_at=created_at,
            repository=conflict_repository,
        )
        validator.validate(authority)
        return FactPublicationResult(
            run_id=run_id,
            authority=authority,
            fact_ids=sorted(fact.fact_id for fact in published_facts),
            event_ids=sorted(event.event_id for event in published_events),
            exposure_ids=sorted(item.exposure_id for item in published_exposures),
            conflict_group_ids=sorted(
                group.conflict_group_id for group in published_conflicts
            ),
        )

    @staticmethod
    def _replay_if_published(
        run_id, authority, accepted_candidates, facts, events, exposures, conflicts
    ):
        run_facts = [item for item in facts if item.run_id == run_id]
        run_events = [item for item in events if item.run_id == run_id]
        run_exposures = [item for item in exposures if item.run_id == run_id]
        run_conflicts = [item for item in conflicts if item.run_id == run_id]
        if not any((run_facts, run_events, run_exposures, run_conflicts)):
            return None
        published_candidate_ids = {
            candidate_id
            for entity in (*run_facts, *run_events, *run_exposures)
            for candidate_id in entity.source_candidate_ids
        }
        accepted_candidate_ids = {
            candidate.candidate_id for candidate in accepted_candidates
        }
        if published_candidate_ids != accepted_candidate_ids:
            raise FactPublicationError(
                f"运行 {run_id} 已发布后候选集发生变化，拒绝将新候选"
                "静默忽略或并入旧结果"
            )
        return FactPublicationResult(
            run_id=run_id,
            authority=authority,
            fact_ids=sorted(item.fact_id for item in run_facts),
            event_ids=sorted(item.event_id for item in run_events),
            exposure_ids=sorted(item.exposure_id for item in run_exposures),
            conflict_group_ids=sorted(item.conflict_group_id for item in run_conflicts),
            is_replay=True,
        )

    @staticmethod
    def _publication_ids(candidates, gates):
        candidate_ids = sorted(candidate.candidate_id for candidate in candidates)
        gate_ids = sorted(gates[item].gate_result_id for item in candidate_ids)
        return candidate_ids, gate_ids

    def _publish_facts(
        self, *, session, authority, run_id, revision, candidates, gates, existing,
        created_at, repository
    ):
        def semantic_identity(candidate):
            return clinical_fact_stable_identity(
                authority=authority,
                fact_type=candidate.fact_type,
                profile_lane=ProfileLane.EVIDENCE_QUALITY,
                asserted_object=candidate.asserted_object,
                polarity=candidate.polarity,
                value=candidate.canonical_value,
                unit=candidate.unit,
                date_range=candidate.date_range,
            )
        _reject_profile_lane_conflicts(
            candidates,
            existing,
            authority,
            semantic_identity,
            lambda fact: clinical_fact_stable_identity(
                authority=authority,
                fact_type=fact.fact_type,
                profile_lane=ProfileLane.EVIDENCE_QUALITY,
                asserted_object=fact.asserted_object,
                polarity=fact.polarity,
                value=fact.value,
                unit=fact.unit,
                date_range=fact.date_range,
            ),
            "事实",
        )
        groups = _group_by_identity(
            candidates,
            lambda candidate: clinical_fact_stable_identity(
                authority=authority,
                fact_type=candidate.fact_type,
                profile_lane=candidate.profile_lane,
                asserted_object=candidate.asserted_object,
                polarity=candidate.polarity,
                value=candidate.canonical_value,
                unit=candidate.unit,
                date_range=candidate.date_range,
            ),
        )
        published: list[ClinicalFactV2] = []
        candidate_to_fact: dict[str, str] = {}
        for stable_identity, group in groups.items():
            representative = group[0]
            candidate_ids, gate_ids = self._publication_ids(group, gates)
            fact_revision = _next_revision(existing, stable_identity)
            fact = ClinicalFactV2(
                fact_id=_entity_id(run_id, "fact", stable_identity, fact_revision),
                run_id=run_id,
                gate_id=gate_ids[0],
                source_candidate_ids=candidate_ids,
                gate_ids=gate_ids,
                authority=authority,
                fact_type=representative.fact_type,
                profile_lane=representative.profile_lane,
                supported_requirement_ids=_requirement_union(group),
                polarity=representative.polarity,
                asserted_object=representative.asserted_object,
                value=representative.canonical_value,
                unit=representative.unit,
                source_strength=_source_strength(session, revision, group),
                date_range=representative.date_range,
                record_time=_common_record_time(group),
                locator_ids=_locator_union(group),
                assertion_basis=representative.assertion_basis,
                stable_identity=stable_identity,
                revision=fact_revision,
                created_at=created_at,
            )
            repository.create(fact)
            published.append(fact)
            candidate_to_fact.update({item: fact.fact_id for item in candidate_ids})
        return published, candidate_to_fact

    def _publish_events(
        self, *, session, authority, run_id, revision, candidates, gates, facts,
        candidate_to_fact, existing, created_at, repository
    ):
        facts_by_id = {fact.fact_id: fact for fact in facts}

        def identity(candidate):
            fact_ids = self._resolved_fact_ids(candidate, candidate_to_fact)
            objects = sorted(
                {f"{facts_by_id[item].fact_type}:{facts_by_id[item].asserted_object}" for item in fact_ids}
            )
            return clinical_event_stable_identity(
                authority=authority,
                event_type=candidate.event_type,
                profile_lane=candidate.profile_lane,
                referenced_fact_objects=objects,
                start_range=candidate.start_range,
                end_range=candidate.end_range,
                duration_status=candidate.duration_status,
            )

        def semantic_identity(candidate):
            fact_ids = self._resolved_fact_ids(candidate, candidate_to_fact)
            objects = sorted(
                {
                    f"{facts_by_id[item].fact_type}:{facts_by_id[item].asserted_object}"
                    for item in fact_ids
                }
            )
            return clinical_event_stable_identity(
                authority=authority,
                event_type=candidate.event_type,
                profile_lane=ProfileLane.EVIDENCE_QUALITY,
                referenced_fact_objects=objects,
                start_range=candidate.start_range,
                end_range=candidate.end_range,
                duration_status=candidate.duration_status,
            )

        _reject_profile_lane_conflicts(
            candidates,
            existing,
            authority,
            semantic_identity,
            lambda event: clinical_event_stable_identity(
                authority=authority,
                event_type=event.event_type,
                profile_lane=ProfileLane.EVIDENCE_QUALITY,
                referenced_fact_objects=event.referenced_fact_objects,
                start_range=event.start_range,
                end_range=event.end_range,
                duration_status=event.duration_status,
            ),
            "事件",
        )
        groups = _group_by_identity(candidates, identity)
        published = []
        candidate_to_event: dict[str, str] = {}
        for stable_identity, group in groups.items():
            representative = group[0]
            candidate_ids, gate_ids = self._publication_ids(group, gates)
            fact_ids = sorted(
                {
                    item
                    for candidate in group
                    for item in self._resolved_fact_ids(candidate, candidate_to_fact)
                }
            )
            objects = sorted(
                {f"{facts_by_id[item].fact_type}:{facts_by_id[item].asserted_object}" for item in fact_ids}
            )
            entity_revision = _next_revision(existing, stable_identity)
            event = ClinicalEventV2(
                event_id=_entity_id(run_id, "event", stable_identity, entity_revision),
                run_id=run_id,
                gate_id=gate_ids[0],
                source_candidate_ids=candidate_ids,
                gate_ids=gate_ids,
                authority=authority,
                event_type=representative.event_type,
                profile_lane=representative.profile_lane,
                start_range=representative.start_range,
                end_range=representative.end_range,
                duration_status=representative.duration_status,
                record_time=_common_record_time(group),
                fact_ids=fact_ids,
                referenced_fact_objects=objects,
                locator_ids=_locator_union(group),
                source_strength=_source_strength(session, revision, group),
                stable_identity=stable_identity,
                revision=entity_revision,
                created_at=created_at,
            )
            repository.create(event)
            published.append(event)
            candidate_to_event.update({item: event.event_id for item in candidate_ids})
        return published, candidate_to_event

    def _publish_exposures(
        self, *, session, authority, run_id, revision, candidates, gates,
        candidate_to_fact, existing, created_at, repository
    ):
        groups = _group_by_identity(
            candidates,
            lambda candidate: medication_exposure_stable_identity(
                authority=authority,
                medication_name=candidate.medication_name,
                category=candidate.category,
                indication=candidate.indication,
                dose=candidate.dose,
                unit=candidate.unit,
                frequency=candidate.frequency,
                route=candidate.route,
                start_range=candidate.start_range,
                end_range=candidate.end_range,
                duration_status=candidate.duration_status,
            ),
        )
        published = []
        candidate_to_exposure: dict[str, str] = {}
        for stable_identity, group in groups.items():
            representative = group[0]
            candidate_ids, gate_ids = self._publication_ids(group, gates)
            fact_ids = sorted(
                {
                    item
                    for candidate in group
                    for item in self._resolved_fact_ids(candidate, candidate_to_fact)
                }
            )
            entity_revision = _next_revision(existing, stable_identity)
            exposure = MedicationExposureV2(
                exposure_id=_entity_id(run_id, "exposure", stable_identity, entity_revision),
                run_id=run_id,
                gate_id=gate_ids[0],
                source_candidate_ids=candidate_ids,
                gate_ids=gate_ids,
                authority=authority,
                medication_name=representative.medication_name,
                category=representative.category,
                indication=representative.indication,
                dose=representative.dose,
                unit=representative.unit,
                frequency=representative.frequency,
                route=representative.route,
                start_range=representative.start_range,
                end_range=representative.end_range,
                duration_status=representative.duration_status,
                record_time=_common_record_time(group),
                fact_ids=fact_ids,
                locator_ids=_locator_union(group),
                source_strength=_source_strength(session, revision, group),
                stable_identity=stable_identity,
                revision=entity_revision,
                created_at=created_at,
            )
            repository.create(exposure)
            published.append(exposure)
            candidate_to_exposure.update(
                {item: exposure.exposure_id for item in candidate_ids}
            )
        return published, candidate_to_exposure

    @staticmethod
    def _resolved_fact_ids(candidate, candidate_to_fact):
        missing = sorted(set(candidate.fact_candidate_ids) - set(candidate_to_fact))
        if missing:
            raise FactPublicationError(
                f"候选 {candidate.candidate_id} 引用的事实候选未通过最终发布门禁：{missing}"
            )
        return sorted({candidate_to_fact[item] for item in candidate.fact_candidate_ids})

    @staticmethod
    def _publish_conflicts(
        *, authority, run_id, fact_candidates, event_candidates, exposure_candidates,
        candidate_to_fact, candidate_to_event, candidate_to_exposure,
        facts, events, exposures, gate_by_candidate, created_at, repository
    ):
        semantic_conflicts = detect_semantic_conflicts(
            authority=authority,
            fact_candidates=fact_candidates,
            event_candidates=event_candidates,
            exposure_candidates=exposure_candidates,
        )
        mappings = {
            "fact": candidate_to_fact,
            "event": candidate_to_event,
            "exposure": candidate_to_exposure,
        }
        entities = {
            "fact": {item.fact_id: item for item in facts},
            "event": {item.event_id: item for item in events},
            "exposure": {item.exposure_id: item for item in exposures},
        }
        published = []
        for conflict in semantic_conflicts:
            member_ids = sorted(
                {mappings[conflict.semantic_type][candidate_id]
                 for candidate_id in conflict.candidate_ids}
            )
            if len(member_ids) < 2:
                raise FactPublicationError(
                    f"冲突 {conflict.semantic_key} 发布后不足两个不同成员"
                )
            locator_ids = sorted(
                {
                    locator_id
                    for member_id in member_ids
                    for locator_id in entities[conflict.semantic_type][member_id].locator_ids
                }
            )
            group = ClinicalConflictGroupV2(
                conflict_group_id="conflict:" + canonical_hash(
                    {
                        "run_id": run_id,
                        "semantic_type": conflict.semantic_type,
                        "semantic_key": conflict.semantic_key,
                        "member_ids": member_ids,
                    }
                )[:32],
                run_id=run_id,
                gate_id=min(
                    gate_by_candidate[item].gate_result_id
                    for item in conflict.candidate_ids
                ),
                authority=authority,
                member_kind=conflict.semantic_type,
                fact_ids=member_ids if conflict.semantic_type == "fact" else [],
                event_ids=member_ids if conflict.semantic_type == "event" else [],
                exposure_ids=member_ids if conflict.semantic_type == "exposure" else [],
                locator_ids=locator_ids,
                created_at=created_at,
            )
            repository.create(group)
            published.append(group)
        return published
