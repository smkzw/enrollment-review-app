"""Phase 4 上传预览/条目/确认仓储（Slice 4.2）。

实现预览生命周期（staged -> committed / staged -> cancelled）、条目镜像三方
交叉校验与确认记录的追加写；预览不是临床快照，取消只清理预览自有暂存，本模块
不触碰共享 blob、快照或状态历史。作用域门禁复用 Phase 4 证据仓储的
``_check_document_scope`` 语义（项目/受试者/审核节点一致）。

- ``EvidenceUploadPreviewRepository``  预览主行 + 逐文件条目（payload/列镜像校验），
                                       状态转换只允许 staged -> committed/cancelled；
- ``EvidenceUploadCommitRepository``   确认记录追加写。

表由迁移 ``0008a_evidence_upload_previews`` 创建，本模块只依赖
``app.storage.evidence_upload_models`` 的表形状。
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.enums import UploadPreviewStatus
from app.domain.contracts.evidence_upload import (
    EvidenceUploadCommit,
    EvidenceUploadItem,
    EvidenceUploadPreview,
)
from app.storage.codecs import (
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.evidence_repositories import EvidenceRepositoryError
from app.storage.evidence_upload_models import (
    EvidenceUploadCommitRecord,
    EvidenceUploadItemRecord,
    EvidenceUploadPreviewRecord,
)
from app.storage.repositories import (
    EpisodeRepository,
    InvalidReferenceError,
    SubjectRepository,
    _flush_guarded,
    _get_required,
)

__all__ = [
    "EvidenceUploadCommitNotFoundError",
    "EvidenceUploadCommitRepository",
    "EvidenceUploadPreviewRepository",
    "EvidenceUploadRepositoryError",
    "PreviewNotFoundError",
    "PreviewStatusTransitionError",
]


class EvidenceUploadRepositoryError(EvidenceRepositoryError):
    """Phase 4 上传预览仓储领域错误基类。"""


class PreviewNotFoundError(EvidenceUploadRepositoryError):
    """上传预览不存在。"""


class PreviewStatusTransitionError(EvidenceUploadRepositoryError):
    """预览状态转换非法：已确认/已取消的预览不可再转换。"""


class EvidenceUploadCommitNotFoundError(EvidenceUploadRepositoryError):
    """确认记录不存在。"""


_PREVIEW_MIRRORS = {
    "preview_id": "preview_id",
    "project_id": "project_id",
    "subject_id": "subject_id",
    "review_episode_id": "review_episode_id",
    "upload_mode": "upload_mode",
    "base_revision": "base_revision",
    "base_snapshot_id": "base_snapshot_id",
    "status": "status",
    "preview_sha256": "preview_sha256",
    "created_by": "created_by",
    "created_at": "created_at",
}

_ITEM_MIRRORS = {
    "item_id": "item_id",
    "preview_id": "preview_id",
    "file_name": "file_name",
    "sha256": "sha256",
    "byte_size": "byte_size",
    "media_type": "media_type",
    "storage_ref": "storage_ref",
    "status": "status",
    "processing_hint": "processing_hint",
    "logical_document_id": "logical_document_id",
    "existing_version_id": "existing_version_id",
    "error_detail": "error_detail",
}

_COMMIT_MIRRORS = {
    "commit_id": "commit_id",
    "preview_id": "preview_id",
    "evidence_snapshot_id": "evidence_snapshot_id",
    "project_id": "project_id",
    "subject_id": "subject_id",
    "review_episode_id": "review_episode_id",
    "upload_mode": "upload_mode",
    "preview_sha256": "preview_sha256",
    "idempotency_key": "idempotency_key",
    "job_id": "job_id",
    "duplicate": "duplicate",
    "created_by": "created_by",
    "created_at": "created_at",
}

# 预览生命周期：确认 staged -> committed；取消 staged -> cancel_pending -> cancelled。
# cancel_pending 是“已取消但暂存清理尚未验证完成”的可重试中间态，不允许确认使用。
_PREVIEW_TRANSITIONS: dict[UploadPreviewStatus, frozenset[UploadPreviewStatus]] = {
    UploadPreviewStatus.STAGED: frozenset(
        {
            UploadPreviewStatus.COMMITTED,
            UploadPreviewStatus.CANCELLED,
            UploadPreviewStatus.CANCEL_PENDING,
        }
    ),
    UploadPreviewStatus.CANCEL_PENDING: frozenset({UploadPreviewStatus.CANCELLED}),
}


def _check_preview_scope(session: Session, preview: EvidenceUploadPreview) -> None:
    """预览的项目/受试者/审核节点作用域门禁（与证据仓储一致）。"""
    episode = EpisodeRepository(session).get(preview.review_episode_id)
    if episode.subject_id != preview.subject_id:
        raise InvalidReferenceError(
            f"EvidenceUploadPreview {preview.preview_id} 的 subject 超出其 review_episode"
        )
    if episode.project_id != preview.project_id:
        raise InvalidReferenceError(
            f"EvidenceUploadPreview {preview.preview_id} 的 project 超出其 review_episode"
        )
    subject = SubjectRepository(session).get(preview.subject_id)
    if subject.project_id != preview.project_id:
        raise InvalidReferenceError(
            f"EvidenceUploadPreview {preview.preview_id} 的 project 与 subject 不一致"
        )


class EvidenceUploadPreviewRepository:
    """上传预览：作用域门禁 + 条目镜像校验 + 三态生命周期。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- 读取 ---------------------------------------------------------------

    @staticmethod
    def _decode_record(record: EvidenceUploadPreviewRecord) -> EvidenceUploadPreview:
        contract = decode_contract(
            EvidenceUploadPreview, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors("EvidenceUploadPreview", record, payload, _PREVIEW_MIRRORS)
        return contract

    @staticmethod
    def _decode_item_record(record: EvidenceUploadItemRecord) -> EvidenceUploadItem:
        contract = decode_contract(
            EvidenceUploadItem, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors("EvidenceUploadItem", record, payload, _ITEM_MIRRORS)
        return contract

    def _verify_items_mirror(
        self,
        preview_id: str,
        contract: EvidenceUploadPreview,
        rows: Sequence[EvidenceUploadItemRecord] | None = None,
    ) -> None:
        rows = (
            rows
            if rows is not None
            else self.session.execute(
                select(EvidenceUploadItemRecord).where(
                    EvidenceUploadItemRecord.preview_id == preview_id
                )
            ).scalars().all()
        )
        actual = {
            (
                item.item_id,
                item.file_name,
                item.sha256,
                item.byte_size,
                item.media_type,
                item.storage_ref,
                item.status,
                item.processing_hint,
                item.logical_document_id,
                item.existing_version_id,
                item.error_detail,
            )
            for item in (self._decode_item_record(row) for row in rows)
        }
        payload = {
            (
                item.item_id,
                item.file_name,
                item.sha256,
                item.byte_size,
                item.media_type,
                item.storage_ref,
                item.status.value,
                item.processing_hint,
                item.logical_document_id,
                item.existing_version_id,
                item.error_detail,
            )
            for item in contract.items
        }
        if actual != payload:
            raise EvidenceUploadRepositoryError(
                f"上传预览 {preview_id} 条目表与 payload 不一致，拒绝还原合同"
            )

    def get(self, preview_id: str) -> EvidenceUploadPreview:
        record = self.session.get(EvidenceUploadPreviewRecord, preview_id)
        if record is None:
            raise PreviewNotFoundError(f"上传预览 {preview_id!r} 不存在")
        contract = self._decode_record(record)
        _check_preview_scope(self.session, contract)
        self._verify_items_mirror(preview_id, contract)
        return contract

    def get_or_none(self, preview_id: str) -> EvidenceUploadPreview | None:
        record = self.session.get(EvidenceUploadPreviewRecord, preview_id)
        if record is None:
            return None
        contract = self._decode_record(record)
        _check_preview_scope(self.session, contract)
        self._verify_items_mirror(preview_id, contract)
        return contract

    def list_by_scope(
        self, *, project_id: str, subject_id: str, review_episode_id: str
    ) -> list[EvidenceUploadPreview]:
        rows = self.session.execute(
            select(EvidenceUploadPreviewRecord).order_by(
                EvidenceUploadPreviewRecord.created_at,
                EvidenceUploadPreviewRecord.preview_id,
            )
        ).scalars().all()
        result: list[EvidenceUploadPreview] = []
        for record in rows:
            contract = self._decode_record(record)
            if (
                contract.project_id == project_id
                and contract.subject_id == subject_id
                and contract.review_episode_id == review_episode_id
            ):
                _check_preview_scope(self.session, contract)
                self._verify_items_mirror(contract.preview_id, contract)
                result.append(contract)
        return result

    # -- 写入 ---------------------------------------------------------------

    def create(self, preview: EvidenceUploadPreview) -> EvidenceUploadPreview:
        """预览主行 + 逐文件条目一次写入；条目归属与作用域在写入前校验。"""
        if preview.status != UploadPreviewStatus.STAGED:
            raise PreviewStatusTransitionError(
                f"上传预览 {preview.preview_id} 创建时状态必须为 staged"
            )
        _check_preview_scope(self.session, preview)
        for item in preview.items:
            if item.preview_id != preview.preview_id:
                raise EvidenceUploadRepositoryError(
                    f"预览条目 {item.item_id} 必须属于当前预览"
                )
        preview_json, preview_sha = encode_contract(preview)
        self.session.add(
            EvidenceUploadPreviewRecord(
                preview_id=preview.preview_id,
                project_id=preview.project_id,
                subject_id=preview.subject_id,
                review_episode_id=preview.review_episode_id,
                upload_mode=preview.upload_mode.value,
                base_revision=preview.base_revision,
                base_snapshot_id=preview.base_snapshot_id,
                status=preview.status.value,
                preview_sha256=preview.preview_sha256,
                created_by=preview.created_by,
                created_at=to_utc_naive(preview.created_at),
                payload_json=preview_json,
                payload_sha256=preview_sha,
            )
        )
        # 先落预览主行再落条目：条目外键依赖预览行。
        _flush_guarded(self.session)
        for item in preview.items:
            item_json, item_sha = encode_contract(item)
            self.session.add(
                EvidenceUploadItemRecord(
                    item_id=item.item_id,
                    preview_id=item.preview_id,
                    file_name=item.file_name,
                    sha256=item.sha256,
                    byte_size=item.byte_size,
                    media_type=item.media_type,
                    storage_ref=item.storage_ref,
                    status=item.status.value,
                    processing_hint=item.processing_hint,
                    logical_document_id=item.logical_document_id,
                    existing_version_id=item.existing_version_id,
                    error_detail=item.error_detail,
                    created_at=to_utc_naive(preview.created_at),
                    payload_json=item_json,
                    payload_sha256=item_sha,
                )
            )
        _flush_guarded(self.session)
        return preview

    def transition_status(
        self,
        preview_id: str,
        *,
        to_status: UploadPreviewStatus,
        actor: str,
        reason: str,
    ) -> EvidenceUploadPreview:
        """预览生命周期转换：staged -> committed；取消 staged -> cancel_pending -> cancelled。

        预览不是临床快照：转换只改写预览自身的状态（追加取消/确认状态），不触碰
        共享 blob、快照或状态历史。``cancel_pending`` 表示取消意图已追加但暂存清理
        尚未验证完成（清理失败保持该状态以便重试）。committed/cancelled 为终态，
        不得再转换。
        """
        try:
            to_status = UploadPreviewStatus(to_status)
        except (TypeError, ValueError) as exc:
            raise PreviewStatusTransitionError(
                f"未知的预览状态：{to_status!r}"
            ) from exc
        record = _get_required(
            self.session, EvidenceUploadPreviewRecord, preview_id, "EvidenceUploadPreview"
        )
        contract = self._decode_record(record)
        _check_preview_scope(self.session, contract)
        self._verify_items_mirror(preview_id, contract)
        if contract.status == to_status:
            return contract
        legal = _PREVIEW_TRANSITIONS.get(contract.status)
        if legal is None or to_status not in legal:
            if contract.status in {
                UploadPreviewStatus.COMMITTED,
                UploadPreviewStatus.CANCELLED,
            }:
                raise PreviewStatusTransitionError(
                    f"上传预览 {preview_id} 处于终态 {contract.status.value}，不允许再发生转换"
                )
            raise PreviewStatusTransitionError(
                f"非法预览状态转换：{contract.status.value} -> {to_status.value}"
            )
        updated = contract.model_copy(update={"status": to_status})
        # 状态转换以追加语义改写 payload 与列（保持双写一致），不删除任何行；
        # created_by 保留原创建者，不因转换被覆盖。
        preview_json, preview_sha = encode_contract(updated)
        record.status = to_status.value
        record.payload_json = preview_json
        record.payload_sha256 = preview_sha
        _flush_guarded(self.session)
        return updated


class EvidenceUploadCommitRepository:
    """确认记录：与候选快照/幂等记录/初始 Job 在同一事务内追加写。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _decode_record(record: EvidenceUploadCommitRecord) -> EvidenceUploadCommit:
        contract = decode_contract(
            EvidenceUploadCommit, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors("EvidenceUploadCommit", record, payload, _COMMIT_MIRRORS)
        return contract

    def get(self, commit_id: str) -> EvidenceUploadCommit:
        record = _get_required(
            self.session, EvidenceUploadCommitRecord, commit_id, "EvidenceUploadCommit"
        )
        return self._decode_record(record)

    def get_or_none(self, commit_id: str) -> EvidenceUploadCommit | None:
        record = self.session.get(EvidenceUploadCommitRecord, commit_id)
        return self._decode_record(record) if record is not None else None

    def processing_job_id_for_snapshot(self, evidence_snapshot_id: str) -> str | None:
        """Return the persisted upload-processing job for one snapshot.

        Duplicate/no-op commits may point at an existing snapshot without creating a
        job of their own, so only commits carrying a job participate in this lookup.
        """
        records = self.session.execute(
            select(EvidenceUploadCommitRecord)
            .order_by(
                EvidenceUploadCommitRecord.created_at.desc(),
                EvidenceUploadCommitRecord.commit_id.desc(),
            )
        ).scalars().all()
        # Decode every immutable commit before filtering. A drifted snapshot/job
        # mirror must fail loudly instead of disappearing behind a column predicate.
        for record in records:
            commit = self._decode_record(record)
            if (
                commit.evidence_snapshot_id == evidence_snapshot_id
                and commit.job_id is not None
            ):
                return commit.job_id
        return None

    def create(self, commit: EvidenceUploadCommit) -> EvidenceUploadCommit:
        """追加写确认记录；预览/快照/作用域引用由外键保证存在。"""
        commit_json, commit_sha = encode_contract(commit)
        self.session.add(
            EvidenceUploadCommitRecord(
                commit_id=commit.commit_id,
                preview_id=commit.preview_id,
                evidence_snapshot_id=commit.evidence_snapshot_id,
                project_id=commit.project_id,
                subject_id=commit.subject_id,
                review_episode_id=commit.review_episode_id,
                upload_mode=commit.upload_mode.value,
                preview_sha256=commit.preview_sha256,
                idempotency_key=commit.idempotency_key,
                job_id=commit.job_id,
                duplicate=commit.duplicate,
                created_by=commit.created_by,
                created_at=to_utc_naive(commit.created_at),
                payload_json=commit_json,
                payload_sha256=commit_sha,
            )
        )
        _flush_guarded(self.session)
        return commit
