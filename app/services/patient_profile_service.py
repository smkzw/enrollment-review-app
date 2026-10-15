"""Phase 5 Patient Profile 投影服务（Slice 5.5，worker_02）。

从已发布 v2 合同（当前权威元组绑定的事实/事件/暴露/冲突/期望）确定性生成并持久化
不可变 Patient Profile revision：

- 只读同一冻结权威元组的已发布 v2 实体（其他审核节点/旧权威元组一律排除，不读
  fixture/旧事实）；审核阶段取自权威审核节点的 ``stage``；
- 泳道归属完全来自已发布 ``ClinicalFactV2.profile_lane`` / ``ClinicalEventV2.profile_lane``，
  每 fact/event 恰好一个 :class:`ProfileLaneAssignment`；不做额外分类器、词汇表、
  自由文本推断、调用方覆盖或默认归属；exposure 固定 MEDICATION、conflict/expectation
  固定 EVIDENCE_QUALITY 由纯投影保证；
- 事实/事件/暴露按稳定身份取链头（同内容多来源合并为一条事实并保留全部定位，旧
  revision 只用于回放），期望按模板取最新 revision；
- 链头折叠后校验引用闭包：事件/暴露引用的事实、冲突引用的成员、期望覆盖的事实
  必须都在本 Profile 已选链头集合内，任何悬挂引用一律
  :class:`PatientProfileProjectionError` 拒绝，绝不静默并入任意历史实体或改写 ID；
- 经 worker_01 纯投影 ``project_patient_profile`` 生成 ``succeeded`` 完整投影，再由
  :class:`~app.storage.patient_profile_repository.PatientProfileRevisionRepository`
  写一条不可变 revision（同内容幂等复用，内容/权威变化只追加链头 +1）；
- ``generating`` / ``failed`` 是显式状态记录（无投影，绝不冒充空成功 Profile）；
  ``stale`` 读取时对照当前审核节点活动指针派生，不改写历史行；缺失/损坏的审核
  节点上下文不是当前成功的证明，读取派生一律大声失败。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.contracts.facts import ClinicalFactCandidateV2, FactAuthority
from app.domain.contracts.enums import ProfileLane
from app.domain.contracts.patient_profile_v2 import (
    PatientProfileRevisionV2,
    ProfileItemKind,
    ProfileLaneAssignment,
    ProfileStatus,
    profile_revision_identity,
)
from app.domain.contracts.review import ReviewEpisode
from app.domain.risk_flags import reference_abnormality
from app.projections.patient_profile import project_patient_profile
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.active_facts import current_fact_heads
from app.storage.fact_repositories import (
    ClinicalConflictGroupV2Repository,
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    FactNormalizationCandidateRepository,
    FactNormalizationRunRepository,
    MedicationExposureV2Repository,
)
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.storage.repositories import (
    EpisodeRepository,
    InvalidReferenceError,
    NotFoundError,
)

__all__ = [
    "PatientProfileProjectionError",
    "PatientProfileService",
]


def _superseded_ids(session: Session, authority: FactAuthority) -> set[str]:
    from app.storage.fact_correction_repository import FactCorrectionRepository

    return {
        item.target_id
        for item in FactCorrectionRepository(session).list_by_authority(authority)
    }


class PatientProfileProjectionError(RuntimeError):
    """Profile 投影输入不满足确定性前提（审核节点与权威元组不一致 / 非法状态记录）。"""


def _chain_heads(entities: list[Any], identity_attr: str) -> list[Any]:
    """按稳定身份取链头（同身份取最高 revision），输出按 (revision, id) 确定排序。"""
    heads: dict[Any, Any] = {}
    for entity in entities:
        key = getattr(entity, identity_attr)
        current = heads.get(key)
        if current is None or entity.revision > current.revision:
            heads[key] = entity
        elif entity.revision == current.revision and entity != current:
            raise PatientProfileProjectionError("同一记录出现不同的同号修订，请先核对来源。")
    return sorted(
        heads.values(),
        key=lambda item: (item.revision, getattr(item, identity_attr)),
    )


class PatientProfileService:
    """Project current records and verified retained sources without copying facts."""

    def fact_display_metadata(self, session: Session, revision: PatientProfileRevisionV2) -> dict[str, dict]:
        """Read exact saved-source metadata; never adopt facts or infer clinical significance."""
        from app.storage.read_retention import retain_read_records

        with retain_read_records(session):
            items = [item for lane in revision.lanes for item in lane.items if item.kind == ProfileItemKind.FACT]
            facts = ClinicalFactV2Repository(session).get_many([item.source_id for item in items])
            # Retain original source IDs, never today's chain heads or a cached validation verdict.
            display_scope = revision.authority.model_dump(exclude={"episode_revision", "protocol_version_id", "rule_set_revision"})
            from app.storage.fact_authority import FactAuthorityValidator
            validator = FactAuthorityValidator(session)
            metadata = {}
            for item in items:
                fact = facts[item.source_id]
                if ((fact.authority.model_dump(exclude={"episode_revision", "protocol_version_id", "rule_set_revision"}) != display_scope
                        and not validator.retained_fact_source_is_reusable(fact, revision.authority))
                        or fact.revision != item.source_revision or fact.date_range != item.start_range
                        or fact.value != item.value or type(fact.value) is not type(item.value)
                        or fact.polarity != item.polarity or fact.unit != item.unit
                        or fact.asserted_object != item.asserted_object
                        or sorted(fact.locator_ids) != sorted(item.locator_ids)):
                    raise PatientProfileProjectionError("时间线记录与原事实不一致")
                metadata[item.source_id] = {"date_role": fact.date_role,
                    "reference_abnormality": reference_abnormality(fact),
                    "record_label": (fact.fact_type if not fact.fact_type.isascii() else "用药记录")
                        if fact.profile_lane == ProfileLane.MEDICATION else None}
            return metadata

    def fact_source_readings(
        self, session: Session, revision: PatientProfileRevisionV2, fact_id: str,
    ) -> list[ClinicalFactCandidateV2]:
        """Return saved source readings for one fact visible in this frozen profile."""
        if not any(
            item.kind == ProfileItemKind.FACT and item.source_id == fact_id
            for lane in revision.lanes for item in lane.items
        ):
            raise InvalidReferenceError("该病历档案中没有对应事实")
        fact = ClinicalFactV2Repository(session).get(fact_id)
        from app.storage.fact_authority import FactAuthorityValidator
        validator = FactAuthorityValidator(session)
        if not validator.retained_fact_source_is_reusable(fact, revision.authority):
            raise PatientProfileProjectionError("事实与病历档案的资料版本不一致")
        validator.validate_locators(revision.authority, fact.locator_ids)
        candidates = FactNormalizationCandidateRepository(session)
        runs = FactNormalizationRunRepository(session)
        readings = []
        for candidate_id in fact.source_candidate_ids:
            candidate = candidates.get(candidate_id)
            if (
                not isinstance(candidate, ClinicalFactCandidateV2)
                or runs.get(candidate.run_id).authority != fact.authority
                or not set(candidate.locator_ids) <= set(fact.locator_ids)
                or not set(candidate.source_observation_refs) <= set(fact.source_observation_refs)
            ):
                raise PatientProfileProjectionError("事实的来源读数与已发布原件不一致")
            readings.append(candidate)
        return readings

    def validate_published_references(self, session: Session, authority: FactAuthority, *, include_rule_revision_sources=False) -> None:
        """Check the existing source graph before starting a new normalization run."""
        options = {"include_rule_revision_sources": True} if include_rule_revision_sources else {}
        self._validate_referential_closure(
            facts=self._published_facts(session, authority, **options),
            events=self._published_events(session, authority, **options),
            exposures=self._published_exposures(session, authority, **options),
            conflicts=self._published_conflicts(session, authority, **options),
            expectations=self._latest_expectations(session, authority),
        )

    # ------------------------------------------------------------------ 生成

    def generate(
        self,
        session: Session,
        *,
        authority: FactAuthority,
        created_at: datetime | None = None,
        generated_at: datetime | None = None,
        exclude_conflict_group_ids: set[str] | None = None,
        exclude_expectation_ids: set[str] | None = None,
        run_id: str | None = None,
        include_rule_revision_sources: bool = False,
    ) -> PatientProfileRevisionV2:
        """生成并持久化当前权威元组的完整确定性 Profile（``succeeded``）。

        - 默认只读同一权威元组；定向抽取可保留真实版本链中未变原件的记录；
        - 泳道归属只来自已发布 ``profile_lane`` 字段，绝不另行分类；
        - 同内容重生成幂等返回最新行；内容/权威变化追加链头 +1。
        - run_id仅兼容触发批次信息，不能缩小当前档案的已发布内容范围。
        """
        episode = EpisodeRepository(session).get(authority.review_episode_id)
        self._require_episode_scope(authority, episode)

        options = {"include_rule_revision_sources": True} if include_rule_revision_sources else {}
        facts = self._published_facts(session, authority, **options)
        events = self._published_events(session, authority, **options)
        exposures = self._published_exposures(session, authority, **options)
        conflicts = self._published_conflicts(session, authority, **options)
        if exclude_conflict_group_ids:
            conflicts = [
                group
                for group in conflicts
                if group.conflict_group_id not in exclude_conflict_group_ids
            ]
        expectations = self._latest_expectations(session, authority)
        if exclude_expectation_ids:
            expectations = [
                item
                for item in expectations
                if item.expectation_id not in exclude_expectation_ids
            ]

        self._validate_referential_closure(
            facts=facts,
            events=events,
            exposures=exposures,
            conflicts=conflicts,
            expectations=expectations,
        )

        lane_assignments = [
            ProfileLaneAssignment(
                kind=ProfileItemKind.FACT,
                source_id=fact.fact_id,
                lane=fact.profile_lane,
            )
            for fact in facts
        ] + [
            ProfileLaneAssignment(
                kind=ProfileItemKind.EVENT,
                source_id=event.event_id,
                lane=event.profile_lane,
            )
            for event in events
        ]

        repository = PatientProfileRevisionRepository(session)
        latest = repository.latest_by_episode(authority.review_episode_id)
        revision = (latest.revision + 1) if latest is not None else 1
        profile = project_patient_profile(
            authority=authority,
            review_stage=episode.stage,
            facts=facts,
            events=events,
            exposures=exposures,
            conflicts=conflicts,
            expectations=expectations,
            lane_assignments=lane_assignments,
            revision=revision,
            created_at=created_at,
            generated_at=generated_at,
            fact_source_authorities={fact.fact_id: fact.authority for fact in facts if fact.authority != authority},
            source_authorities={
                ProfileItemKind.EVENT: {row.event_id: row.authority for row in events if row.authority != authority},
                ProfileItemKind.EXPOSURE: {row.exposure_id: row.authority for row in exposures if row.authority != authority},
                ProfileItemKind.CONFLICT: {row.conflict_group_id: row.authority for row in conflicts if row.authority != authority},
            },
            retained_snapshots=self._snapshot_chain(session, authority) if any(
                (row.authority.evidence_snapshot_v2_id, row.authority.complete_processing_revision_id) !=
                (authority.evidence_snapshot_v2_id, authority.complete_processing_revision_id)
                for row in (*facts, *events, *exposures, *conflicts)) else (),
        )
        return repository.create(profile)

    def record_status(
        self,
        session: Session,
        *,
        authority: FactAuthority,
        status: ProfileStatus,
        created_at: datetime | None = None,
    ) -> PatientProfileRevisionV2:
        """写一条显式状态记录（``generating`` / ``failed``，无投影）。

        生成中/失败是明确状态，绝不伪装成空成功 Profile（不带泳道/突出/待核对数，
        也无生成时间）。``stale`` 由读取派生，不由本方法写入。
        """
        if status not in (ProfileStatus.GENERATING, ProfileStatus.FAILED):
            raise PatientProfileProjectionError(
                f"Profile 显式状态记录只允许 generating/failed，得到 {status.value}"
            )
        episode = EpisodeRepository(session).get(authority.review_episode_id)
        self._require_episode_scope(authority, episode)

        repository = PatientProfileRevisionRepository(session)
        latest = repository.latest_by_episode(authority.review_episode_id)
        revision = (latest.revision + 1) if latest is not None else 1
        record = PatientProfileRevisionV2(
            patient_profile_revision_id=profile_revision_identity(
                authority.review_episode_id, revision
            ),
            authority=authority,
            status=status,
            revision=revision,
            review_stage=episode.stage,
            pending_review_count=0,
            created_at=created_at or datetime.now(UTC),
        )
        return repository.create(record)

    # ------------------------------------------------------------------ 读取

    def get(
        self, session: Session, patient_profile_revision_id: str
    ) -> PatientProfileRevisionV2:
        """按稳定 ID 读取一条 Profile revision（冻结状态，不派生 stale）。"""
        return PatientProfileRevisionRepository(session).get(
            patient_profile_revision_id
        )

    def latest(
        self, session: Session, review_episode_id: str
    ) -> PatientProfileRevisionV2 | None:
        """当前链头 Profile；冻结权威已落后于审核节点活动指针时派生 ``stale``。"""
        repository = PatientProfileRevisionRepository(session)
        revision = repository.latest_by_episode(review_episode_id)
        if revision is None:
            return None
        return self._derive_stale(session, revision)

    def history(
        self, session: Session, review_episode_id: str
    ) -> list[PatientProfileRevisionV2]:
        """全部历史 revision（按 revision 升序），逐条对照当前权威派生 ``stale``。"""
        repository = PatientProfileRevisionRepository(session)
        return [
            self._derive_stale(session, item)
            for item in repository.list_by_episode(review_episode_id)
        ]

    def _derive_stale(
        self, session: Session, revision: PatientProfileRevisionV2
    ) -> PatientProfileRevisionV2:
        """对照当前审核节点活动指针派生 ``stale``，绝不改写历史行。

        显式状态记录（generating/failed）保留其明确状态，不派生 stale；只有完整
        ``succeeded`` 投影在冻结权威（活动快照/完整处理修订/节点修订）落后时才
        标记为陈旧。缺失/损坏的审核节点上下文不是当前成功的证明：无法读取审核
        节点时抛 :class:`PatientProfileProjectionError`，绝不返回未确认的成功。
        """
        if revision.status != ProfileStatus.SUCCEEDED:
            return revision
        try:
            episode = EpisodeRepository(session).get(
                revision.authority.review_episode_id
            )
        except (NotFoundError, InvalidReferenceError) as exc:
            raise PatientProfileProjectionError(
                f"无法读取审核节点 {revision.authority.review_episode_id}，"
                "缺少当前权威上下文，拒绝返回成功 Profile"
            ) from exc
        frozen = (
            revision.authority.evidence_snapshot_v2_id,
            revision.authority.complete_processing_revision_id,
            revision.authority.episode_revision,
        )
        current = (
            episode.active_evidence_snapshot_id,
            episode.active_evidence_processing_revision_id,
            episode.revision,
        )
        if current != frozen:
            return revision.model_copy(update={"status": ProfileStatus.STALE})
        return revision

    # ------------------------------------------------------- 已发布实体选择

    @staticmethod
    def _validate_referential_closure(
        *,
        facts: list[Any],
        events: list[Any],
        exposures: list[Any],
        conflicts: list[Any],
        expectations: list[Any],
    ) -> None:
        """链头折叠后的 Profile 引用闭包校验，悬挂引用一律拒绝。

        事实/事件/暴露按稳定身份取链头后，事件/暴露引用的旧事实 revision、冲突
        引用的旧成员、期望覆盖的旧事实 ID 都不再出现在本 Profile 已选集合内；这类
        悬挂引用一旦存在就抛 :class:`PatientProfileProjectionError` 并给出实体类型
        与缺失 ID，绝不静默并入任意历史实体，也不改写任何 ID。
        """
        fact_ids = {fact.fact_id for fact in facts}
        event_ids = {event.event_id for event in events}
        exposure_ids = {exposure.exposure_id for exposure in exposures}
        for event in events:
            missing = sorted(set(event.fact_ids) - fact_ids)
            if missing:
                raise PatientProfileProjectionError(
                    f"事件 {event.event_id} 引用已折叠链头之外的事实 {missing}，拒绝投影"
                )
        for exposure in exposures:
            missing = sorted(set(exposure.fact_ids) - fact_ids)
            if missing:
                raise PatientProfileProjectionError(
                    f"暴露 {exposure.exposure_id} 引用已折叠链头之外的事实 {missing}，拒绝投影"
                )
        for conflict in conflicts:
            member_ids = {
                "fact": conflict.fact_ids,
                "event": conflict.event_ids,
                "exposure": conflict.exposure_ids,
            }[conflict.member_kind]
            pool = {
                "fact": fact_ids,
                "event": event_ids,
                "exposure": exposure_ids,
            }[conflict.member_kind]
            missing = sorted(set(member_ids) - pool)
            if missing:
                raise PatientProfileProjectionError(
                    f"冲突 {conflict.conflict_group_id} 引用已折叠链头之外的"
                    f"{conflict.member_kind} 成员 {missing}，拒绝投影"
                )
        for expectation in expectations:
            missing = sorted(set(expectation.coverage_fact_ids) - fact_ids)
            if missing:
                raise PatientProfileProjectionError(
                    f"期望 {expectation.expectation_id} 覆盖已折叠链头之外的事实"
                    f" {missing}，拒绝投影"
                )

    def _published_facts(
        self, session: Session, authority: FactAuthority, *, include_rule_revision_sources: bool = False,
    ) -> list[Any]:
        if not include_rule_revision_sources:
            return current_fact_heads(session, authority)
        from app.storage.fact_authority import FactAuthorityValidator
        from app.storage.fact_correction_repository import FactCorrectionRepository
        validator = FactAuthorityValidator(session)
        compatible = {}
        selected = []
        for fact in ClinicalFactV2Repository(session).list_by_episode(authority.review_episode_id):
            key = fact.authority.model_dump_json()
            if key not in compatible:
                compatible[key] = validator.rule_revision_source_is_reusable(fact.authority, authority)
            if compatible[key] or validator.retained_fact_source_is_reusable(fact, authority):
                selected.append(fact)
        validator.validate_locators(authority, sorted({locator for fact in selected for locator in fact.locator_ids}))
        superseded = {item.target_id for item in FactCorrectionRepository(session).list_by_review_episode(authority.review_episode_id)}
        heads = _chain_heads(selected, "stable_identity")
        return [fact for fact in heads if fact.fact_id not in superseded]

    @staticmethod
    def _snapshot_chain(session, authority):
        from app.storage.evidence_repositories import EvidenceSnapshotRepository
        rows, seen = [], set()
        key = authority.evidence_snapshot_v2_id
        while key is not None:
            if key in seen:
                raise PatientProfileProjectionError("资料版本链重复")
            seen.add(key)
            snapshot = EvidenceSnapshotRepository(session).get(key)
            if (snapshot.project_id, snapshot.subject_id, snapshot.review_episode_id) != (
                    authority.project_id, authority.subject_id, authority.review_episode_id):
                raise PatientProfileProjectionError("资料版本链属于其他个例或节点")
            rows.append(snapshot)
            key = snapshot.prior_snapshot_id
        return tuple(rows)

    def _published_events(
        self, session: Session, authority: FactAuthority, *, include_rule_revision_sources=False,
    ) -> list[Any]:
        repository = ClinicalEventV2Repository(session)
        superseded = self._retained_superseded_ids(session, authority) if include_rule_revision_sources else _superseded_ids(session, authority)
        from app.storage.fact_authority import FactAuthorityValidator
        validator = FactAuthorityValidator(session)
        bound = [
            event
            for event in repository.list_by_episode(authority.review_episode_id)
            if event.authority == authority or include_rule_revision_sources and validator.retained_fact_source_is_reusable(event, authority)
        ]
        superseded |= self._cascade_source_ids(session, bound, "event", "event_id")
        return [
            event for event in _chain_heads(bound, "stable_identity")
            if event.event_id not in superseded
        ]

    def _published_exposures(
        self, session: Session, authority: FactAuthority, *, include_rule_revision_sources=False,
    ) -> list[Any]:
        repository = MedicationExposureV2Repository(session)
        superseded = self._retained_superseded_ids(session, authority) if include_rule_revision_sources else _superseded_ids(session, authority)
        from app.storage.fact_authority import FactAuthorityValidator
        validator = FactAuthorityValidator(session)
        bound = [
            exposure
            for exposure in repository.list_by_episode(authority.review_episode_id)
            if exposure.authority == authority or include_rule_revision_sources and validator.retained_fact_source_is_reusable(exposure, authority)
        ]
        superseded |= self._cascade_source_ids(session, bound, "exposure", "exposure_id")
        return [
            exposure for exposure in _chain_heads(bound, "stable_identity")
            if exposure.exposure_id not in superseded
        ]

    def _published_conflicts(
        self, session: Session, authority: FactAuthority, *, include_rule_revision_sources=False,
    ) -> list[Any]:
        from app.storage.active_conflicts import current_conflict_heads
        if include_rule_revision_sources:
            from app.storage.active_conflicts import source_conflict_heads
            from app.storage.fact_authority import FactAuthorityValidator
            from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
            groups = ClinicalConflictGroupV2Repository(session).list_by_episode(authority.review_episode_id)
            excluded = set()
            for source in {row.authority.model_dump_json(): row.authority for row in groups}.values():
                excluded.update(FactCorrectionCommitRepository(session).superseded_conflict_ids(source))
            excluded.update(FactCorrectionCommitRepository(session).superseded_conflict_ids(authority))
            validator = FactAuthorityValidator(session)
            return [row for row in source_conflict_heads(groups) if row.conflict_group_id not in excluded
                and (row.authority == authority or validator.retained_fact_source_is_reusable(row, authority))]
        return current_conflict_heads(session, authority)

    @staticmethod
    def _retained_superseded_ids(session, authority):
        from app.storage.fact_correction_repository import FactCorrectionRepository
        return {row.target_id for row in FactCorrectionRepository(session).list_by_review_episode(authority.review_episode_id)}

    @staticmethod
    def _cascade_source_ids(session, entities, kind, id_field):
        """Fold only a host-generated successor bound to an actual fact correction.

        Same clinical wording is not enough: source IDs, changed references and
        the deterministic cascade candidate/gate must all agree. This preserves
        the original immutable entity while excluding it from today's heads.
        """
        from app.services.fact_correction_service import _cascade_ids
        from app.storage.fact_correction_repository import FactCorrectionRepository
        if not entities:
            return set()
        corrections = FactCorrectionRepository(session).list_by_review_episode(entities[0].authority.review_episode_id)
        mutable = {id_field, "run_id", "gate_id", "source_candidate_ids", "gate_ids", "authority", "stable_identity",
            "revision", "created_at", "fact_ids", "referenced_fact_objects", "source_strength", "source_revision_of"}
        by_candidate = {}
        for entity in entities:
            for candidate_id in entity.source_candidate_ids:
                by_candidate.setdefault(candidate_id, []).append(entity)
        superseded = set()
        for prior in entities:
            for correction in corrections:
                if correction.target_kind != "fact" or correction.target_id not in prior.fact_ids:
                    continue
                cascade = _cascade_ids(correction, kind, getattr(prior, id_field))
                expected_refs = sorted(correction.new_entity_id if identity == correction.target_id else identity for identity in prior.fact_ids)
                if any(successor.authority == correction.authority
                        and successor.gate_ids == [cascade["gate_id"]] and successor.gate_id == cascade["gate_id"]
                        and successor.fact_ids == expected_refs
                        and successor.model_dump(exclude=mutable) == prior.model_dump(exclude=mutable)
                        for successor in by_candidate.get(cascade["candidate_id"], ())):
                    superseded.add(getattr(prior, id_field))
        return superseded

    def _latest_expectations(
        self, session: Session, authority: FactAuthority
    ) -> list[Any]:
        repository = EvidenceExpectationV2Repository(session)
        bound = [
            expectation
            for expectation in repository.list_by_episode(
                authority.review_episode_id
            )
            if expectation.authority == authority
        ]
        return _chain_heads(bound, "template_id")

    @staticmethod
    def _require_episode_scope(
        authority: FactAuthority, episode: ReviewEpisode
    ) -> None:
        """审核节点作用域必须与不可变权威元组一致（活动指针由仓储校验）。"""
        if (
            episode.project_id,
            episode.subject_id,
            episode.revision,
            episode.rule_set_id,
            episode.rule_set_revision,
            episode.protocol_version_id,
        ) != (
            authority.project_id,
            authority.subject_id,
            authority.episode_revision,
            authority.rule_set_id,
            authority.rule_set_revision,
            authority.protocol_version_id,
        ):
            raise PatientProfileProjectionError(
                "Patient Profile 所用审核节点与不可变权威元组不一致"
            )
