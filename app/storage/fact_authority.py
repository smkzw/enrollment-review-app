"""Phase 5 权威元组与定位引用确定性校验（Slice 5.1，worker_03）。

设计书 §2.1/§2.3 与 PRD P5-R01/P5-AC01 的权威边界由本模块在持久化边界强制：

- 证据快照必须存在于 ``evidence_snapshots_v2`` 且作用域与权威元组一致；legacy
  ``evidence_snapshots`` 占位 id 一律拒绝（新写路径只有一个明确权威源）；
- 审核节点必须已激活且活动版本指针对成对存在（``active_evidence_snapshot_id`` 与
  ``active_evidence_processing_revision_id`` 同时非空），任一缺失即拒绝；
- 权威快照/完整处理修订必须等于审核节点当前活动指针，否则视为引用非活动版本；
- ``episode_revision`` 必须等于审核节点当前 ``revision``，否则视为陈旧修订；
- 权威元组其余成员（project/subject/rule_set/rule_set_revision/protocol_version）
  必须与审核节点作用域一致；
- 完整处理修订必须是可激活的 complete 修订（``revision_kind='complete'``、
  ``is_activatable=1``、``status='ready'``），base/未激活/未就绪修订一律拒绝；
- 定位引用只接受当前审核节点/当前活动快照成员资料的真实 locator：跨审核节点、
  跨快照、跨处理修订的 locator id 一律拒绝。

本模块只做确定性校验，不写任何持久状态；发布实体仓储（``fact_repositories``）在
写入前调用 ``validate`` 与 ``validate_locators``。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.storage.codecs import PersistedContractInvalid
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    EvidenceLocatorRepository,
)
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotV2Record,
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.models import ReviewEpisodeRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.storage.repositories import EpisodeRepository, RepositoryError

__all__ = [
    "FactAuthorityError",
    "FactAuthorityValidator",
    "FactLocatorReferenceError",
]


class FactAuthorityError(RepositoryError):
    """权威元组校验失败：legacy/缺失快照、未激活/未配对指针、陈旧修订、非 complete
    修订或作用域不一致，拒绝发布。"""


class FactLocatorReferenceError(RepositoryError):
    """定位引用不在当前审核节点/活动快照/处理修订闭包内（跨节点/跨快照/跨修订）。"""


class FactAuthorityValidator:
    """把不可变权威元组与数据库当前状态确定性核对。

    校验失败抛 :class:`FactAuthorityError` / :class:`FactLocatorReferenceError`，
    不写入任何记录；调用方负责在事务内先校验后发布。
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ 权威元组

    def validate(self, authority: FactAuthority) -> None:
        """校验权威元组对应当前活动证据链；任一不满足即拒绝。"""
        self.validate_and_get_revision(authority)

    def validate_and_get_revision(
        self, authority: FactAuthority
    ) -> CompleteEvidenceProcessingRevision:
        """完整核验并返回本次读取的修订；不缓存，也不接受外部已验证标记。"""
        self._validate_snapshot(authority)
        self._validate_episode(authority)
        return self._validate_complete_revision(authority)

    def validate_frozen_source(self, authority: FactAuthority) -> CompleteEvidenceProcessingRevision:
        """Verify retained source scope without requiring today's active pointers.

        This proves document/processing membership, not current clinical facts or
        rule applicability; callers separately establish subject/episode ownership.
        """
        self._validate_snapshot(authority)
        return self._validate_complete_revision(authority)

    def _validate_snapshot(self, authority: FactAuthority) -> None:
        snapshot = self.session.get(
            EvidenceSnapshotV2Record, authority.evidence_snapshot_v2_id
        )
        if snapshot is None:
            raise FactAuthorityError(
                f"证据快照 {authority.evidence_snapshot_v2_id} 不存在于 "
                "evidence_snapshots_v2；legacy evidence_snapshots 占位 id 一律拒绝"
            )
        decoded = EvidenceSnapshotRepository._decode_record(snapshot)
        if (
            decoded.project_id,
            decoded.subject_id,
            decoded.review_episode_id,
        ) != (
            authority.project_id,
            authority.subject_id,
            authority.review_episode_id,
        ):
            raise FactAuthorityError(
                f"权威快照 {authority.evidence_snapshot_v2_id} 作用域与权威元组不一致"
            )

    def _validate_episode(self, authority: FactAuthority) -> None:
        episode = self.session.get(
            ReviewEpisodeRecord, authority.review_episode_id
        )
        if episode is None:
            raise FactAuthorityError(
                f"审核节点 {authority.review_episode_id} 不存在"
            )
        decoded = EpisodeRepository._decode_record(episode)
        # 活动指针对必须成对：任一为空即视为未激活/未配对。
        if (
            decoded.active_evidence_snapshot_id is None
            or decoded.active_evidence_processing_revision_id is None
        ):
            raise FactAuthorityError(
                f"审核节点 {authority.review_episode_id} 未激活或活动版本指针未配对，"
                "拒绝发布事实"
            )
        if decoded.active_evidence_snapshot_id != authority.evidence_snapshot_v2_id:
            raise FactAuthorityError(
                f"权威快照 {authority.evidence_snapshot_v2_id} 不是审核节点当前活动快照 "
                f"({decoded.active_evidence_snapshot_id})，拒绝发布"
            )
        if (
            decoded.active_evidence_processing_revision_id
            != authority.complete_processing_revision_id
        ):
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 不是审核节点"
                f"当前活动处理修订 ({decoded.active_evidence_processing_revision_id})，"
                "拒绝发布"
            )
        if decoded.revision != authority.episode_revision:
            raise FactAuthorityError(
                f"陈旧审核节点修订：权威元组 episode_revision="
                f"{authority.episode_revision}，当前审核节点 revision="
                f"{decoded.revision}，拒绝发布"
            )
        if (
            decoded.project_id,
            decoded.subject_id,
            decoded.rule_set_id,
            decoded.rule_set_revision,
            decoded.protocol_version_id,
        ) != (
            authority.project_id,
            authority.subject_id,
            authority.rule_set_id,
            authority.rule_set_revision,
            authority.protocol_version_id,
        ):
            raise FactAuthorityError(
                f"权威元组与审核节点 {authority.review_episode_id} 作用域不一致，拒绝发布"
            )

    def _validate_complete_revision(
        self, authority: FactAuthority
    ) -> CompleteEvidenceProcessingRevision:
        revision_row = self.session.get(
            EvidenceProcessingRevisionRecord, authority.complete_processing_revision_id
        )
        if revision_row is None:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 不存在"
            )
        try:
            decoded = CompleteEvidenceProcessingRevisionRepository(self.session).get(
                authority.complete_processing_revision_id
            )
        except (RepositoryError, PersistedContractInvalid) as exc:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} "
                "的页、定位、风险或资料元数据闭包不完整"
            ) from exc
        if not decoded.is_activatable or decoded.status.value != "ready":
            raise FactAuthorityError(
                f"处理修订 {authority.complete_processing_revision_id} 不是可激活的"
                "complete 修订（base/未激活/未就绪一律拒绝）"
            )
        if decoded.evidence_snapshot_id != authority.evidence_snapshot_v2_id:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 与权威快照 "
                f"{authority.evidence_snapshot_v2_id} 不一致"
            )
        if decoded.review_episode_id != authority.review_episode_id:
            raise FactAuthorityError(
                f"完整处理修订 {authority.complete_processing_revision_id} 与审核节点 "
                f"{authority.review_episode_id} 不一致"
            )
        return decoded

    # ------------------------------------------------------------------ 定位引用

    def validate_locators(
        self, authority: FactAuthority, locator_ids: list[str]
    ) -> None:
        """逐个校验定位引用都在指定审核节点/冻结快照/处理修订闭包内。

        同一批定位共享一个视觉核验上下文：同一事务内重复的整修订核验只
        执行一次；上下文随本次调用结束而丢弃，不跨事务复用。
        """
        from app.storage.page_review_visual_locator_validation import (
            VisualLocatorBatchContext,
        )

        batch = VisualLocatorBatchContext(self.session)
        for locator_id in sorted(set(locator_ids)):
            self._validate_locator(authority, locator_id, batch)

    def _validate_locator(self, authority: FactAuthority, locator_id: str, batch=None) -> None:
        locator = self.session.get(EvidenceLocatorArtifactRecord, locator_id)
        if locator is None:
            raise FactLocatorReferenceError(f"定位 {locator_id} 不存在")
        decoded_locator = EvidenceLocatorRepository._decode(locator)
        if decoded_locator.page_review_visual is not None:
            from app.storage.page_review_visual_locator_validation import verify_visual_locator_authority
            verify_visual_locator_authority(self.session, decoded_locator, authority, batch=batch)
            return
        document = self.session.get(
            SourceDocumentVersionV2Record,
            decoded_locator.source_document_version_id,
        )
        if document is None:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 引用的资料版本 "
                f"{decoded_locator.source_document_version_id} 不存在"
            )
        decoded_document = SourceDocumentRepository._decode(document)
        if decoded_document.review_episode_id != authority.review_episode_id:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 属于其他审核节点 "
                f"({decoded_document.review_episode_id})，跨审核节点定位引用拒绝"
            )
        member_rows = self.session.execute(
            select(EvidenceSnapshotMemberRecord).where(
                EvidenceSnapshotMemberRecord.snapshot_id == authority.evidence_snapshot_v2_id
            )
        ).scalars().all()
        decoded_members = [
            EvidenceSnapshotRepository._decode_member_record(
                row,
                expected_snapshot_id=authority.evidence_snapshot_v2_id,
            )
            for row in member_rows
        ]
        matching_members = [
            member
            for member in decoded_members
            if member.snapshot_id == authority.evidence_snapshot_v2_id
            and member.source_document_version_id
            == decoded_document.source_document_version_id
        ]
        if not matching_members:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 的资料不属于指定快照成员（跨快照/跨处理修订"
                "定位引用拒绝）"
            )
        revision_member = self.session.execute(
            select(ProcessingRevisionLocatorRecord).where(
                ProcessingRevisionLocatorRecord.revision_id
                == authority.complete_processing_revision_id,
                ProcessingRevisionLocatorRecord.locator_id == locator_id,
            )
        ).scalar_one_or_none()
        if revision_member is None:
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 未收录于指定完整处理修订 "
                f"{authority.complete_processing_revision_id} 的定位清单，拒绝引用"
            )
        if (
            decoded_locator.processing_revision_id is not None
            and decoded_locator.processing_revision_id
            != authority.complete_processing_revision_id
        ):
            raise FactLocatorReferenceError(
                f"定位 {locator_id} 绑定其他处理修订 "
                f"({decoded_locator.processing_revision_id})，拒绝引用"
            )
