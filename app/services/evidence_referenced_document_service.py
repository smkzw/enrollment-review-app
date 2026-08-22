"""Slice 4.4 “资料中提及但未提供”修订/满足服务（WP-44B）。

两层不可变追加链（§4.5）：登记修订（proposed/confirmed/dismissed）与满足修订
（unresolved/provided）。确定性模式只能生成 proposed，绝不自动 confirmed/provided；
每条 confirmed 必须有可回放触发定位；dismiss 只解除候选，不删除候选/触发原文/
历史；解除关联产生新的 unresolved 满足修订，不删除旧的满足关系。

本服务不创建 ``ClinicalFact``、``EvidenceExpectation`` 结论、规则影响、入排判断
或 ``ActionRequest``（§4.5 停止点）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    ReferencedDocumentOrigin,
    ReferencedDocumentResolutionStatus,
    ReferencedDocumentStatus,
)
from app.domain.contracts.evidence_locator import (
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
)
from app.services.evidence_activation_service import EvidenceActivationService
from app.storage.evidence_locator_models import (
    ReferencedDocumentResolutionRevisionRecord,
    ReferencedDocumentRevisionRecord,
)
from app.storage.evidence_locator_repositories import ReferencedDocumentRepository
from app.storage.evidence_repositories import SourceDocumentRepository

__all__ = [
    "EvidenceReferencedDocumentService",
    "ReferencedDocumentServiceError",
]




def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)

class ReferencedDocumentServiceError(RuntimeError):
    """被提及资料服务领域错误基类。"""


class EvidenceReferencedDocumentService:
    """被提及资料登记/确认/解除/满足修订服务（追加写）。"""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def register(
        self,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        description: str,
        document_type: str | None = None,
        source_party: str | None = None,
        origin: ReferencedDocumentOrigin = ReferencedDocumentOrigin.MANUAL,
        pattern_version: str | None = None,
        trigger_locator_id: str | None = None,
        referenced_document_id: str | None = None,
        revision_id: str | None = None,
        created_by: str,
    ) -> ReferencedDocumentRevision:
        """登记一条被提及资料修订（初始 revision=1）。

        确定性模式只能生成 proposed（合同校验器兜底）；手工登记默认 proposed。
        """
        with self.session_factory() as session, session.begin():
            return self.register_in_session(
                session,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=review_episode_id,
                description=description,
                document_type=document_type,
                source_party=source_party,
                origin=origin,
                pattern_version=pattern_version,
                trigger_locator_id=trigger_locator_id,
                referenced_document_id=referenced_document_id,
                revision_id=revision_id,
                created_by=created_by,
            )

    def register_in_session(
        self,
        session: Session,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        description: str,
        document_type: str | None = None,
        source_party: str | None = None,
        origin: ReferencedDocumentOrigin = ReferencedDocumentOrigin.MANUAL,
        pattern_version: str | None = None,
        trigger_locator_id: str | None = None,
        referenced_document_id: str | None = None,
        revision_id: str | None = None,
        created_by: str,
    ) -> ReferencedDocumentRevision:
        """在调用方事务内登记（供 API 命令服务与幂等键同事务提交）。"""
        from uuid import uuid4

        origin = ReferencedDocumentOrigin(origin)
        status = ReferencedDocumentStatus.PROPOSED
        if origin == ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE:
            status = ReferencedDocumentStatus.PROPOSED
        revision = ReferencedDocumentRevision(
            revision_id=revision_id or f"rd-{uuid4().hex}",
            referenced_document_id=referenced_document_id or f"refdoc-{uuid4().hex}",
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=review_episode_id,
            description=description,
            document_type=document_type,
            source_party=source_party,
            trigger_locator_id=trigger_locator_id,
            origin=origin,
            pattern_version=pattern_version,
            status=status,
            revision=1,
            created_at=_utcnow(),
            created_by=created_by,
        )
        return ReferencedDocumentRepository(session).create_revision(revision)

    def confirm(
        self,
        *,
        referenced_document_id: str,
        trigger_locator_id: str,
        reason: str,
        created_by: str,
    ) -> ReferencedDocumentRevision:
        """确认候选：必须保留可回放触发定位（合同校验器拒绝无 trigger 的 confirmed）。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("确认被提及资料必须说明原因")
        with self.session_factory() as session, session.begin():
            return self.confirm_in_session(
                session,
                referenced_document_id=referenced_document_id,
                trigger_locator_id=trigger_locator_id,
                reason=reason,
                created_by=created_by,
            )

    def confirm_in_session(
        self,
        session: Session,
        *,
        referenced_document_id: str,
        trigger_locator_id: str,
        reason: str,
        created_by: str,
        revision_id: str | None = None,
    ) -> ReferencedDocumentRevision:
        """在调用方事务内确认候选（可传入确定性修订 ID 供幂等回放）。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("确认被提及资料必须说明原因")
        head = self._revision_head(session, referenced_document_id)
        if head is None:
            raise ReferencedDocumentServiceError(
                f"被提及资料 {referenced_document_id} 没有任何登记修订，无法确认"
            )
        revision = ReferencedDocumentRevision(
            revision_id=revision_id or f"rd-{_uuid()}",
            referenced_document_id=referenced_document_id,
            project_id=head.project_id,
            subject_id=head.subject_id,
            review_episode_id=head.review_episode_id,
            description=head.description,
            document_type=head.document_type,
            source_party=head.source_party,
            trigger_locator_id=trigger_locator_id,
            origin=head.origin,
            pattern_version=head.pattern_version,
            status=ReferencedDocumentStatus.CONFIRMED,
            user_reviewed=True,
            reason=reason,
            revision=head.revision + 1,
            supersedes_revision_id=head.revision_id,
            created_at=_utcnow(),
            created_by=created_by,
        )
        return ReferencedDocumentRepository(session).create_revision(revision)

    def revise(
        self,
        *,
        referenced_document_id: str,
        description: str,
        document_type: str | None,
        source_party: str | None,
        reason: str,
        created_by: str,
    ) -> ReferencedDocumentRevision:
        """修改候选描述/类型/来源方：追加新修订，不改写历史状态与触发定位。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("修改被提及资料必须说明原因")
        with self.session_factory() as session, session.begin():
            return self.revise_in_session(
                session,
                referenced_document_id=referenced_document_id,
                description=description,
                document_type=document_type,
                source_party=source_party,
                reason=reason,
                created_by=created_by,
            )

    def revise_in_session(
        self,
        session: Session,
        *,
        referenced_document_id: str,
        description: str,
        document_type: str | None,
        source_party: str | None,
        reason: str,
        created_by: str,
        revision_id: str | None = None,
    ) -> ReferencedDocumentRevision:
        """在调用方事务内修改候选（可传入确定性修订 ID 供幂等回放）。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("修改被提及资料必须说明原因")
        head = self._revision_head(session, referenced_document_id)
        if head is None:
            raise ReferencedDocumentServiceError(
                f"被提及资料 {referenced_document_id} 没有任何登记修订，无法修改"
            )
        revision = ReferencedDocumentRevision(
            revision_id=revision_id or f"rd-{_uuid()}",
            referenced_document_id=referenced_document_id,
            project_id=head.project_id,
            subject_id=head.subject_id,
            review_episode_id=head.review_episode_id,
            description=description,
            document_type=document_type,
            source_party=source_party,
            trigger_locator_id=head.trigger_locator_id,
            origin=head.origin,
            pattern_version=head.pattern_version,
            status=head.status,
            user_reviewed=head.user_reviewed,
            reason=reason,
            revision=head.revision + 1,
            supersedes_revision_id=head.revision_id,
            created_at=_utcnow(),
            created_by=created_by,
        )
        return ReferencedDocumentRepository(session).create_revision(revision)

    def dismiss(
        self,
        *,
        referenced_document_id: str,
        reason: str,
        created_by: str,
    ) -> ReferencedDocumentRevision:
        """解除候选：追加 dismissed 修订，不删除候选/触发原文/历史。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("解除被提及资料必须说明原因")
        with self.session_factory() as session, session.begin():
            return self.dismiss_in_session(
                session,
                referenced_document_id=referenced_document_id,
                reason=reason,
                created_by=created_by,
            )

    def dismiss_in_session(
        self,
        session: Session,
        *,
        referenced_document_id: str,
        reason: str,
        created_by: str,
        revision_id: str | None = None,
    ) -> ReferencedDocumentRevision:
        """在调用方事务内解除候选（可传入确定性修订 ID 供幂等回放）。"""
        if not reason.strip():
            raise ReferencedDocumentServiceError("解除被提及资料必须说明原因")
        head = self._revision_head(session, referenced_document_id)
        if head is None:
            raise ReferencedDocumentServiceError(
                f"被提及资料 {referenced_document_id} 没有任何登记修订，无法解除"
            )
        revision = ReferencedDocumentRevision(
            revision_id=revision_id or f"rd-{_uuid()}",
            referenced_document_id=referenced_document_id,
            project_id=head.project_id,
            subject_id=head.subject_id,
            review_episode_id=head.review_episode_id,
            description=head.description,
            document_type=head.document_type,
            source_party=head.source_party,
            trigger_locator_id=head.trigger_locator_id,
            origin=head.origin,
            pattern_version=head.pattern_version,
            status=ReferencedDocumentStatus.DISMISSED,
            user_reviewed=True,
            reason=reason,
            revision=head.revision + 1,
            supersedes_revision_id=head.revision_id,
            created_at=_utcnow(),
            created_by=created_by,
        )
        return ReferencedDocumentRepository(session).create_revision(revision)

    def resolve(
        self,
        *,
        referenced_document_id: str,
        status: ReferencedDocumentResolutionStatus,
        source_document_version_id: str | None = None,
        created_by: str,
    ) -> ReferencedDocumentResolutionRevision:
        """追加满足修订：provided 必须绑定同一 scope 的快照成员资料版本。"""
        with self.session_factory() as session, session.begin():
            return self.resolve_in_session(
                session,
                referenced_document_id=referenced_document_id,
                status=status,
                source_document_version_id=source_document_version_id,
                created_by=created_by,
            )

    def resolve_in_session(
        self,
        session: Session,
        *,
        referenced_document_id: str,
        status: ReferencedDocumentResolutionStatus,
        source_document_version_id: str | None = None,
        created_by: str,
        resolution_revision_id: str | None = None,
    ) -> ReferencedDocumentResolutionRevision:
        """在调用方事务内追加满足修订（可传入确定性修订 ID 供幂等回放）。"""
        from uuid import uuid4

        status = ReferencedDocumentResolutionStatus(status)
        revision_head = self._revision_head(session, referenced_document_id)
        if revision_head is None:
            raise ReferencedDocumentServiceError(
                "找不到对应的被提及资料登记，不能建立满足关系"
            )
        if status == ReferencedDocumentResolutionStatus.PROVIDED:
            self._validate_provided_document(
                session,
                referenced_document=revision_head,
                source_document_version_id=source_document_version_id,
            )
        head = self._resolution_head(session, referenced_document_id)
        resolution = ReferencedDocumentResolutionRevision(
            resolution_revision_id=resolution_revision_id or f"res-{uuid4().hex}",
            referenced_document_id=referenced_document_id,
            status=status,
            source_document_version_id=source_document_version_id,
            revision=(head.revision + 1) if head is not None else 1,
            supersedes_resolution_revision_id=(
                head.resolution_revision_id if head is not None else None
            ),
            created_at=_utcnow(),
            created_by=created_by,
        )
        return ReferencedDocumentRepository(session).create_resolution(resolution)

    @staticmethod
    def _validate_provided_document(
        session: Session,
        *,
        referenced_document: ReferencedDocumentRevision,
        source_document_version_id: str | None,
    ) -> None:
        """provided 只能绑定同一审核节点当前活动快照中的真实资料成员。"""
        if source_document_version_id is None:
            raise ReferencedDocumentServiceError("标记资料已提供时必须选择一份当前资料")
        source_document = SourceDocumentRepository(session).get(
            source_document_version_id
        )
        expected_scope = (
            referenced_document.project_id,
            referenced_document.subject_id,
            referenced_document.review_episode_id,
        )
        actual_scope = (
            source_document.project_id,
            source_document.subject_id,
            source_document.review_episode_id,
        )
        if actual_scope != expected_scope:
            raise ReferencedDocumentServiceError(
                "所选资料不属于这名受试者的当前审核节点，不能用于解除该资料缺口"
            )
        current_snapshot = EvidenceActivationService.current_snapshot(
            session, referenced_document.review_episode_id
        )
        if current_snapshot is None:
            raise ReferencedDocumentServiceError(
                "当前审核节点尚未启用资料版本，不能把资料标记为已提供"
            )
        if not any(
            member.source_document_version_id == source_document_version_id
            for member in current_snapshot.members
        ):
            raise ReferencedDocumentServiceError(
                "所选资料不在当前启用的资料版本中，不能用于解除该资料缺口"
            )

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def revision_head(
        session: Session, referenced_document_id: str
    ) -> ReferencedDocumentRevision | None:
        """当前登记修订链头（只读投影；与 WP-44B 服务链头选择一致）。"""
        return EvidenceReferencedDocumentService._revision_head(
            session, referenced_document_id
        )

    @staticmethod
    def resolution_head(
        session: Session, referenced_document_id: str
    ) -> ReferencedDocumentResolutionRevision | None:
        """当前满足修订链头（只读投影）。"""
        return EvidenceReferencedDocumentService._resolution_head(
            session, referenced_document_id
        )

    @staticmethod
    def _revision_head(session: Session, referenced_document_id: str) -> ReferencedDocumentRevision | None:
        rows = session.execute(
            select(ReferencedDocumentRevisionRecord).where(
                ReferencedDocumentRevisionRecord.referenced_document_id
                == referenced_document_id
            )
        ).scalars().all()
        superseded_ids = {
            r.supersedes_revision_id
            for r in rows
            if r.supersedes_revision_id is not None
        }
        head_ids = {r.revision_id for r in rows} - superseded_ids
        heads = [r for r in rows if r.revision_id in head_ids]
        if not heads:
            return None
        if len(heads) != 1:
            raise ReferencedDocumentServiceError(
                f"被提及资料 {referenced_document_id} 存在多个修订链头，拒绝猜测当前版本"
            )
        head = heads[0]
        return ReferencedDocumentRepository(session).get_revision(head.revision_id)

    @staticmethod
    def _resolution_head(
        session: Session, referenced_document_id: str
    ) -> ReferencedDocumentResolutionRevision | None:
        rows = session.execute(
            select(ReferencedDocumentResolutionRevisionRecord).where(
                ReferencedDocumentResolutionRevisionRecord.referenced_document_id
                == referenced_document_id
            )
        ).scalars().all()
        superseded_ids = {
            r.supersedes_resolution_revision_id
            for r in rows
            if r.supersedes_resolution_revision_id is not None
        }
        head_ids = {r.resolution_revision_id for r in rows} - superseded_ids
        heads = [r for r in rows if r.resolution_revision_id in head_ids]
        if not heads:
            return None
        if len(heads) != 1:
            raise ReferencedDocumentServiceError(
                f"被提及资料 {referenced_document_id} 存在多个满足关系链头，拒绝猜测当前版本"
            )
        head = heads[0]
        return ReferencedDocumentRepository(session).get_resolution(head.resolution_revision_id)


def _uuid() -> str:
    from uuid import uuid4

    return uuid4().hex
