"""Phase 4 证据快照与资料版本仓储（Slice 4.1）。

实现 worker_02 负责的作用域门禁、前序链无环、显式替代、集合哈希、重复集合
no-op 与候选状态机转换，全部以确定性领域错误拒绝非法写入：

- ``BlobRepository``                      内容寻址去重：同 SHA-256 只保存一份；
- ``SourceDocumentRepository``            逻辑资料版本：作用域门禁 + 显式替代
                                         线性链（紧邻版本号 + 链头约束）；
- ``SourceDocumentMetadataRevisionRepository``  元数据修订追加链；
- ``EvidenceSnapshotRepository``          快照：作用域、前序链无环、增量继承/
                                         显式替代/新增语义、集合哈希与三方交叉
                                         校验、重复集合 no-op、候选状态机。

表由 worker_03 的迁移 ``0008_evidence_ingestion`` 创建，本模块只依赖
``app.storage.evidence_models`` 的表形状。激活（ready->active + 活动指针原子
更新 + ActivationEvent）与回滚属 Slice 4.4，本切片不开放。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.domain.contracts.enums import SnapshotMemberOrigin, SnapshotStatus, UploadMode
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    EvidenceSnapshotStatusEvent,
    SourceBlob,
    SourceDocumentMetadataRevision,
    SourceDocumentVersion,
)
from app.domain.publication import canonical_hash, evidence_snapshot_collection_hash
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
    utc_now,
)
from app.storage.evidence_models import (
    EvidenceSnapshotMemberRecord,
    EvidenceSnapshotStatusEventRecord,
    EvidenceSnapshotV2Record,
    SourceBlobRecord,
    SourceDocumentMetadataRevisionRecord,
    SourceDocumentVersionV2Record,
)
from app.storage.idempotency import IdempotencyRepository
from app.storage.models import IdempotencyRecordRow
from app.storage.repositories import (
    DuplicateRecordError,
    EpisodeRepository,
    InvalidReferenceError,
    RepositoryError,
    ScopeViolationError,
    SubjectRepository,
    _flush_guarded,
    _get_required,
)

__all__ = [
    "BlobRepository",
    "DuplicateBlobMismatchError",
    "EvidenceRepositoryError",
    "EvidenceSnapshotRepository",
    "SnapshotCycleError",
    "SnapshotStatusTransitionError",
    "SnapshotSupersessionError",
    "SourceDocumentMetadataRevisionRepository",
    "SourceDocumentRepository",
]


class EvidenceRepositoryError(RepositoryError):
    """Phase 4 证据仓储领域错误基类。"""


class DuplicateBlobMismatchError(EvidenceRepositoryError):
    """同内容（同 SHA-256）但尺寸/媒体类型不一致，拒绝复用既有 blob。"""


class SnapshotCycleError(EvidenceRepositoryError):
    """证据快照前序链成环，拒绝建立非法链。"""


class SnapshotSupersessionError(EvidenceRepositoryError):
    """显式替代/增量继承语义不成立。"""


class SnapshotStatusTransitionError(EvidenceRepositoryError):
    """候选快照状态转换非法或终态被冻结。"""


# ---------------------------------------------------------------------------
# 候选状态机（设计书 §6 状态表）。ready->active / ready->revision_conflict
# 属发布与回滚路径，由 Slice 4.4 的 ActivationEvent 原子更新实现，本切片不开放。
# ---------------------------------------------------------------------------

_LEGAL_TRANSITIONS: dict[SnapshotStatus, dict[str, SnapshotStatus]] = {
    SnapshotStatus.STAGED: {
        "worker_start": SnapshotStatus.PROCESSING,
        "cancel": SnapshotStatus.CANCELLED,
    },
    SnapshotStatus.PROCESSING: {
        "checkpoint_success": SnapshotStatus.PROCESSING,
        "blocking_risk_found": SnapshotStatus.NEEDS_ATTENTION,
        "retryable_error": SnapshotStatus.RETRYABLE_FAILURE,
        "terminal_error": SnapshotStatus.TERMINAL_FAILURE,
        "cancel_at_safe_boundary": SnapshotStatus.CANCELLED,
        "all_gates_passed": SnapshotStatus.READY,
    },
    SnapshotStatus.RETRYABLE_FAILURE: {
        "retry": SnapshotStatus.PROCESSING,
        # JobRunner 恢复时可能在下一次执行尚未开始前耗尽尝试预算；
        # 追加专用事件，避免伪造一次 retry 再终败。
        "recovery_attempts_exhausted": SnapshotStatus.TERMINAL_FAILURE,
        "cancel": SnapshotStatus.CANCELLED,
    },
    SnapshotStatus.NEEDS_ATTENTION: {
        "correction_or_resolution": SnapshotStatus.PROCESSING,
        "cancel": SnapshotStatus.CANCELLED,
    },
    # READY -> ACTIVE 只在 WP-44B 激活事务内、与活动指针对更新同一事务追加；
    # transition_status 单独拦截 "activate" 事件，防止绕过激活门禁伪造 ACTIVE。
    SnapshotStatus.READY: {
        "activate": SnapshotStatus.ACTIVE,
    },
}

_TERMINAL_STATUSES = frozenset(
    {
        SnapshotStatus.ACTIVE,
        SnapshotStatus.REVISION_CONFLICT,
        SnapshotStatus.CANCELLED,
        SnapshotStatus.TERMINAL_FAILURE,
    }
)

# 重复集合 no-op 仍然有效匹配的状态（活动快照/仍在演进的候选）。
# 注意：这是“重复集合确认可复用”的匹配集合，与“有效前序/比较基线”
# （current_snapshot_for_episode，仅审核节点活动指针）是两个独立概念。候选可以被
# 同集合确认命中 no-op，但绝不是有效证据基准；只有活动指针对指向的快照才能作为
# 补充资料前序或完整资料比较基线。
_NOOP_MATCH_STATUSES = frozenset(
    {
        SnapshotStatus.STAGED,
        SnapshotStatus.PROCESSING,
        SnapshotStatus.NEEDS_ATTENTION,
        SnapshotStatus.RETRYABLE_FAILURE,
        SnapshotStatus.READY,
        SnapshotStatus.ACTIVE,
    }
)


class BlobRepository:
    """不可变原始文件身份/存储引用，内容寻址去重。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: SourceBlobRecord) -> SourceBlob:
        contract = decode_contract(SourceBlob, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "SourceBlob",
            record,
            payload,
            {
                "source_blob_id": "source_blob_id",
                "sha256": "sha256",
                "byte_size": "byte_size",
                "media_type": "media_type",
                "storage_ref": "storage_ref",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, source_blob_id: str) -> SourceBlob:
        record = _get_required(self.session, SourceBlobRecord, source_blob_id, "SourceBlob")
        return self._decode(record)

    def get_or_none(self, source_blob_id: str) -> SourceBlob | None:
        record = self.session.get(SourceBlobRecord, source_blob_id)
        return self._decode(record) if record is not None else None

    def get_or_create_by_sha256(self, blob: SourceBlob) -> SourceBlob:
        """内容去重：同 SHA-256 复用既有 blob（no-op），否则写入。

        合同已强制 ``source_blob_id == sha256``，因此按主键命中即内容命中。
        同内容但尺寸/媒体类型不一致视为数据完整性冲突，拒绝静默复用。
        SQLite 冲突忽略把跨会话的同 SHA 提交收敛到同一条既有记录。
        """
        existing = self.session.get(SourceBlobRecord, blob.source_blob_id)
        if existing is not None:
            decoded = self._decode(existing)
            if decoded.byte_size != blob.byte_size or decoded.media_type != blob.media_type:
                raise DuplicateBlobMismatchError(
                    f"SourceBlob {blob.source_blob_id} 已存在但尺寸/媒体类型不一致，"
                    "拒绝复用既有内容"
                )
            return decoded
        payload_json, payload_sha256 = encode_contract(blob)
        record = SourceBlobRecord(
            source_blob_id=blob.source_blob_id,
            sha256=blob.sha256,
            byte_size=blob.byte_size,
            media_type=blob.media_type,
            storage_ref=blob.storage_ref,
            created_at=to_utc_naive(blob.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.execute(
            sqlite_insert(SourceBlobRecord)
            .values(
                source_blob_id=record.source_blob_id,
                sha256=record.sha256,
                byte_size=record.byte_size,
                media_type=record.media_type,
                storage_ref=record.storage_ref,
                created_at=record.created_at,
                payload_json=record.payload_json,
                payload_sha256=record.payload_sha256,
            )
            .on_conflict_do_nothing()
        )
        _flush_guarded(self.session)
        winner = self.session.get(SourceBlobRecord, blob.source_blob_id)
        if winner is None:
            winner = self.session.execute(
                select(SourceBlobRecord).where(SourceBlobRecord.sha256 == blob.sha256)
            ).scalar_one_or_none()
        if winner is None:
            raise InvalidReferenceError(
                f"SourceBlob {blob.source_blob_id} 写入后无法读取，拒绝返回不完整结果"
            )
        decoded = self._decode(winner)
        if decoded.byte_size != blob.byte_size or decoded.media_type != blob.media_type:
            raise DuplicateBlobMismatchError(
                f"SourceBlob {blob.source_blob_id} 已存在但尺寸/媒体类型不一致，"
                "拒绝复用既有内容"
            )
        return decoded


def _check_document_scope(session, version: SourceDocumentVersion) -> None:
    """逻辑资料版本的项目/受试者/审核节点作用域门禁。"""
    episode = EpisodeRepository(session).get(version.review_episode_id)
    if episode.subject_id != version.subject_id:
        raise ScopeViolationError(
            f"SourceDocumentVersion {version.source_document_version_id} 的 subject "
            "超出其 review_episode"
        )
    if episode.project_id != version.project_id:
        raise ScopeViolationError(
            f"SourceDocumentVersion {version.source_document_version_id} 的 project "
            "超出其 review_episode"
        )
    subject = SubjectRepository(session).get(version.subject_id)
    if subject.project_id != version.project_id:
        raise ScopeViolationError(
            f"SourceDocumentVersion {version.source_document_version_id} 的 project "
            "与 subject 不一致"
        )


class SourceDocumentRepository:
    """逻辑资料版本：作用域门禁 + 显式替代线性链。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: SourceDocumentVersionV2Record) -> SourceDocumentVersion:
        contract = decode_contract(
            SourceDocumentVersion, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "SourceDocumentVersion",
            record,
            payload,
            {
                "source_document_version_id": "source_document_version_id",
                "logical_document_id": "logical_document_id",
                "source_blob_sha256": "source_blob_sha256",
                "file_name": "file_name",
                "media_type": "media_type",
                "page_count": "page_count",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "version_number": "version_number",
                "supersedes_version_id": "supersedes_version_id",
                "created_by": "created_by",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, source_document_version_id: str) -> SourceDocumentVersion:
        record = _get_required(
            self.session,
            SourceDocumentVersionV2Record,
            source_document_version_id,
            "SourceDocumentVersion",
        )
        version = self._decode(record)
        _check_document_scope(self.session, version)
        self._verify_blob_reference(self.session, version)
        self._assert_version_chain(version)
        return version

    def get_or_none(self, source_document_version_id: str) -> SourceDocumentVersion | None:
        record = self.session.get(SourceDocumentVersionV2Record, source_document_version_id)
        if record is None:
            return None
        version = self._decode(record)
        _check_document_scope(self.session, version)
        self._verify_blob_reference(self.session, version)
        self._assert_version_chain(version)
        return version

    def get_many(
        self, source_document_version_ids: list[str]
    ) -> dict[str, SourceDocumentVersion]:
        """批量读取资料版本，先校验所有持久合同再按 ID 选择。"""
        wanted = set(source_document_version_ids)
        if not wanted:
            return {}
        rows = self.session.execute(select(SourceDocumentVersionV2Record)).scalars().all()
        decoded = [self._decode(row) for row in rows]
        result: dict[str, SourceDocumentVersion] = {}
        for contract in decoded:
            self._verify_blob_reference(self.session, contract)
            self._assert_version_chain(contract)
            if contract.source_document_version_id in wanted:
                _check_document_scope(self.session, contract)
                result[contract.source_document_version_id] = contract
        missing = wanted - set(result)
        if missing:
            raise InvalidReferenceError("部分资料版本不存在")
        return result

    @staticmethod
    def _verify_blob_reference(session, version: SourceDocumentVersion) -> None:
        blob_record = session.get(SourceBlobRecord, version.source_blob_sha256)
        if blob_record is None:
            raise InvalidReferenceError(
                f"资料版本 {version.source_document_version_id} 引用的 SourceBlob "
                f"{version.source_blob_sha256} 不存在"
            )
        BlobRepository._decode(blob_record)

    def _assert_version_chain(self, start: SourceDocumentVersion) -> None:
        """读取时验证显式替代链存在、同作用域且按版本号连续。"""
        seen: set[str] = set()
        current = start
        while current.supersedes_version_id is not None:
            if current.source_document_version_id in seen:
                raise SnapshotCycleError(
                    f"逻辑资料版本替代链成环：重复访问 {current.source_document_version_id}"
                )
            seen.add(current.source_document_version_id)
            prior_record = self.session.get(
                SourceDocumentVersionV2Record, current.supersedes_version_id
            )
            if prior_record is None:
                raise InvalidReferenceError(
                    f"逻辑资料版本 {current.source_document_version_id} 的替代前序 "
                    f"{current.supersedes_version_id} 不存在"
                )
            prior = self._decode(prior_record)
            self._verify_blob_reference(self.session, prior)
            if prior.source_document_version_id in seen:
                raise SnapshotCycleError(
                    f"逻辑资料版本替代链成环：重复访问 {prior.source_document_version_id}"
                )
            if (
                prior.logical_document_id != current.logical_document_id
                or (
                    prior.project_id,
                    prior.subject_id,
                    prior.review_episode_id,
                )
                != (
                    current.project_id,
                    current.subject_id,
                    current.review_episode_id,
                )
            ):
                raise SnapshotSupersessionError(
                    f"逻辑资料版本 {current.source_document_version_id} 的替代前序作用域或逻辑资料不一致"
                )
            if prior.version_number != current.version_number - 1:
                raise SnapshotSupersessionError(
                    f"逻辑资料版本替代链不连续：{current.source_document_version_id} "
                    f"前序应为版本 {current.version_number - 1}"
                )
            current = prior

    def _latest_version(
        self, *, review_episode_id: str, logical_document_id: str
    ) -> SourceDocumentVersion | None:
        rows = self.session.execute(
            select(SourceDocumentVersionV2Record).order_by(
                SourceDocumentVersionV2Record.version_number
            )
        ).scalars().all()
        contracts = []
        for row in rows:
            contract = self._decode(row)
            if (
                contract.review_episode_id == review_episode_id
                and contract.logical_document_id == logical_document_id
            ):
                _check_document_scope(self.session, contract)
            self._verify_blob_reference(self.session, contract)
            if (
                contract.review_episode_id == review_episode_id
                and contract.logical_document_id == logical_document_id
            ):
                contracts.append(contract)
        contracts.sort(key=lambda contract: contract.version_number)
        for contract in contracts:
            self._assert_version_chain(contract)
        return contracts[-1] if contracts else None

    def create_version(self, version: SourceDocumentVersion) -> SourceDocumentVersion:
        """写入逻辑资料版本；作用域门禁 + 显式替代线性链校验。"""
        blob_record = _get_required(
            self.session, SourceBlobRecord, version.source_blob_sha256, "SourceBlob"
        )
        BlobRepository._decode(blob_record)
        _check_document_scope(self.session, version)

        latest = self._latest_version(
            review_episode_id=version.review_episode_id,
            logical_document_id=version.logical_document_id,
        )
        if version.version_number == 1:
            if version.supersedes_version_id is not None:
                raise SnapshotSupersessionError(
                    f"逻辑资料 {version.logical_document_id} 首版本不能引用前序版本"
                )
            if latest is not None:
                raise DuplicateRecordError(
                    f"逻辑资料 {version.logical_document_id} 已存在版本号 1，"
                    "不能重复创建首版本"
                )
        else:
            if version.supersedes_version_id is None:
                raise SnapshotSupersessionError(
                    f"逻辑资料 {version.logical_document_id} 版本号 {version.version_number} "
                    "必须显式替代其前序版本"
                )
            prior = _get_required(
                self.session,
                SourceDocumentVersionV2Record,
                version.supersedes_version_id,
                "SourceDocumentVersion",
            )
            prior_contract = self._decode(prior)
            self._verify_blob_reference(self.session, prior_contract)
            self._assert_version_chain(prior_contract)
            if prior_contract.logical_document_id != version.logical_document_id:
                raise SnapshotSupersessionError(
                    f"显式替代 {version.supersedes_version_id} 不属于同一逻辑资料 "
                    f"{version.logical_document_id}"
                )
            if (
                prior_contract.project_id,
                prior_contract.subject_id,
                prior_contract.review_episode_id,
            ) != (
                version.project_id,
                version.subject_id,
                version.review_episode_id,
            ):
                raise ScopeViolationError(
                    f"显式替代 {version.supersedes_version_id} 跨项目/受试者/审核节点"
                )
            if version.version_number != prior_contract.version_number + 1:
                raise SnapshotSupersessionError(
                    f"显式替代版本号必须紧邻前序版本号（前序 "
                    f"{prior_contract.version_number}，本次 {version.version_number}）"
                )
            if latest is None or latest.source_document_version_id != version.supersedes_version_id:
                raise SnapshotSupersessionError(
                    f"显式替代必须指向逻辑资料 {version.logical_document_id} 的当前链头"
                )

        payload_json, payload_sha256 = encode_contract(version)
        record = SourceDocumentVersionV2Record(
            source_document_version_id=version.source_document_version_id,
            logical_document_id=version.logical_document_id,
            source_blob_sha256=version.source_blob_sha256,
            file_name=version.file_name,
            media_type=version.media_type,
            page_count=version.page_count,
            project_id=version.project_id,
            subject_id=version.subject_id,
            review_episode_id=version.review_episode_id,
            version_number=version.version_number,
            supersedes_version_id=version.supersedes_version_id,
            created_by=version.created_by,
            created_at=to_utc_naive(version.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return version

    def list_by_scope(
        self, *, project_id: str, subject_id: str, review_episode_id: str
    ) -> list[SourceDocumentVersion]:
        rows = self.session.execute(
            select(SourceDocumentVersionV2Record).order_by(
                SourceDocumentVersionV2Record.logical_document_id,
                SourceDocumentVersionV2Record.version_number,
            )
        ).scalars().all()
        contracts = []
        for row in rows:
            contract = self._decode(row)
            self._verify_blob_reference(self.session, contract)
            if (
                contract.project_id == project_id
                and contract.subject_id == subject_id
                and contract.review_episode_id == review_episode_id
            ):
                _check_document_scope(self.session, contract)
                contracts.append(contract)
        for contract in contracts:
            self._assert_version_chain(contract)
        return contracts


class SourceDocumentMetadataRevisionRepository:
    """资料类型/来源方的不可变元数据修订追加链。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: SourceDocumentMetadataRevisionRecord) -> SourceDocumentMetadataRevision:
        contract = decode_contract(
            SourceDocumentMetadataRevision, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "SourceDocumentMetadataRevision",
            record,
            payload,
            {
                "metadata_revision_id": "metadata_revision_id",
                "source_document_version_id": "source_document_version_id",
                "revision": "revision",
                "document_type": "document_type",
                "source_party": "source_party",
                "reason": "reason",
                "is_auto_suggestion": "is_auto_suggestion",
                "supersedes_metadata_revision_id": "supersedes_metadata_revision_id",
                "created_by": "created_by",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, metadata_revision_id: str) -> SourceDocumentMetadataRevision:
        record = _get_required(
            self.session,
            SourceDocumentMetadataRevisionRecord,
            metadata_revision_id,
            "SourceDocumentMetadataRevision",
        )
        revision = self._decode(record)
        document_record = _get_required(
            self.session,
            SourceDocumentVersionV2Record,
            revision.source_document_version_id,
            "SourceDocumentVersion",
        )
        document = SourceDocumentRepository._decode(document_record)
        _check_document_scope(self.session, document)
        SourceDocumentRepository._verify_blob_reference(self.session, document)
        SourceDocumentRepository(self.session)._assert_version_chain(document)
        self._assert_metadata_chain(revision)
        return revision

    def _assert_metadata_chain(
        self, start: SourceDocumentMetadataRevision
    ) -> None:
        """读取时验证元数据修订链存在、同资料且按 revision 连续。"""
        seen: set[str] = set()
        current = start
        while current.supersedes_metadata_revision_id is not None:
            if current.metadata_revision_id in seen:
                raise SnapshotCycleError(
                    f"元数据修订链成环：重复访问 {current.metadata_revision_id}"
                )
            seen.add(current.metadata_revision_id)
            prior_record = self.session.get(
                SourceDocumentMetadataRevisionRecord,
                current.supersedes_metadata_revision_id,
            )
            if prior_record is None:
                raise InvalidReferenceError(
                    f"元数据修订 {current.metadata_revision_id} 的前序 "
                    f"{current.supersedes_metadata_revision_id} 不存在"
                )
            prior = self._decode(prior_record)
            if prior.metadata_revision_id in seen:
                raise SnapshotCycleError(
                    f"元数据修订链成环：重复访问 {prior.metadata_revision_id}"
                )
            if prior.source_document_version_id != current.source_document_version_id:
                raise ScopeViolationError("元数据修订前序必须属于同一资料版本")
            if prior.revision != current.revision - 1:
                raise InvalidReferenceError(
                    f"元数据修订链不连续：{current.metadata_revision_id} 的前序 revision 错误"
                )
            current = prior

    def _count_for_document(self, source_document_version_id: str) -> int:
        rows = self.session.execute(
            select(SourceDocumentMetadataRevisionRecord)
        ).scalars().all()
        count = 0
        for row in rows:
            revision = self._decode(row)
            if revision.source_document_version_id == source_document_version_id:
                count += 1
        return count

    def append(self, revision: SourceDocumentMetadataRevision) -> SourceDocumentMetadataRevision:
        document_record = _get_required(
            self.session,
            SourceDocumentVersionV2Record,
            revision.source_document_version_id,
            "SourceDocumentVersion",
        )
        document = SourceDocumentRepository._decode(document_record)
        _check_document_scope(self.session, document)
        SourceDocumentRepository._verify_blob_reference(self.session, document)
        SourceDocumentRepository(self.session)._assert_version_chain(document)
        if revision.revision == 1:
            if revision.supersedes_metadata_revision_id is not None:
                raise InvalidReferenceError(
                    f"初始元数据修订 {revision.metadata_revision_id} 不能引用前序修订"
                )
            if self._count_for_document(revision.source_document_version_id) > 0:
                raise DuplicateRecordError(
                    f"资料版本 {revision.source_document_version_id} 已存在初始元数据修订，"
                    "新修订必须引用前序修订且递增 revision"
                )
        else:
            if revision.supersedes_metadata_revision_id is None:
                raise InvalidReferenceError(
                    f"元数据修订 {revision.metadata_revision_id} 必须引用其前序修订"
                )
            prior = _get_required(
                self.session,
                SourceDocumentMetadataRevisionRecord,
                revision.supersedes_metadata_revision_id,
                "SourceDocumentMetadataRevision",
            )
            prior_contract = self._decode(prior)
            self._assert_metadata_chain(prior_contract)
            if prior_contract.source_document_version_id != revision.source_document_version_id:
                raise ScopeViolationError(
                    f"元数据修订 {revision.metadata_revision_id} 的前序不属于同一资料版本"
                )
            if prior_contract.revision != revision.revision - 1:
                raise InvalidReferenceError(
                    f"元数据修订 revision 必须紧邻前序（前序 "
                    f"{prior_contract.revision}，本次 {revision.revision}）"
                )
            successor = self.session.execute(
                select(SourceDocumentMetadataRevisionRecord).where(
                    SourceDocumentMetadataRevisionRecord.supersedes_metadata_revision_id
                    == revision.supersedes_metadata_revision_id
                )
            ).scalars().first()
            if successor is not None:
                raise InvalidReferenceError(
                    f"元数据修订 {revision.metadata_revision_id} 只能替代当前链头 "
                    f"{revision.supersedes_metadata_revision_id}（已存在后继，拒绝分支）"
                )

        payload_json, payload_sha256 = encode_contract(revision)
        record = SourceDocumentMetadataRevisionRecord(
            metadata_revision_id=revision.metadata_revision_id,
            source_document_version_id=revision.source_document_version_id,
            revision=revision.revision,
            document_type=revision.document_type,
            source_party=revision.source_party,
            reason=revision.reason,
            is_auto_suggestion=revision.is_auto_suggestion,
            supersedes_metadata_revision_id=revision.supersedes_metadata_revision_id,
            created_by=revision.created_by,
            created_at=to_utc_naive(revision.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return revision

    def list_chain(self, source_document_version_id: str) -> list[SourceDocumentMetadataRevision]:
        rows = self.session.execute(
            select(SourceDocumentMetadataRevisionRecord).order_by(
                SourceDocumentMetadataRevisionRecord.revision
            )
        ).scalars().all()
        revisions = [self._decode(row) for row in rows]
        result = [
            revision
            for revision in revisions
            if revision.source_document_version_id == source_document_version_id
        ]
        if result:
            document_record = _get_required(
                self.session,
                SourceDocumentVersionV2Record,
                source_document_version_id,
                "SourceDocumentVersion",
            )
            document = SourceDocumentRepository._decode(document_record)
            _check_document_scope(self.session, document)
            SourceDocumentRepository._verify_blob_reference(self.session, document)
            SourceDocumentRepository(self.session)._assert_version_chain(document)
        for revision in result:
            self._assert_metadata_chain(revision)
        return result

    def head(self, source_document_version_id: str) -> SourceDocumentMetadataRevision | None:
        rows = self.session.execute(
            select(SourceDocumentMetadataRevisionRecord).order_by(
                SourceDocumentMetadataRevisionRecord.revision
            )
        ).scalars().all()
        contracts = [self._decode(row) for row in rows]
        contracts = [
            revision
            for revision in contracts
            if revision.source_document_version_id == source_document_version_id
        ]
        if contracts:
            document_record = _get_required(
                self.session,
                SourceDocumentVersionV2Record,
                source_document_version_id,
                "SourceDocumentVersion",
            )
            document = SourceDocumentRepository._decode(document_record)
            _check_document_scope(self.session, document)
            SourceDocumentRepository._verify_blob_reference(self.session, document)
            SourceDocumentRepository(self.session)._assert_version_chain(document)
        for revision in contracts:
            self._assert_metadata_chain(revision)
        return contracts[-1] if contracts else None

    def heads_by_document_ids(
        self, source_document_version_ids: list[str]
    ) -> dict[str, SourceDocumentMetadataRevision]:
        """批量读取元数据链头，先校验全部合同再按资料归组。"""
        wanted = set(source_document_version_ids)
        if not wanted:
            return {}
        rows = self.session.execute(
            select(SourceDocumentMetadataRevisionRecord).order_by(
                SourceDocumentMetadataRevisionRecord.revision
            )
        ).scalars().all()
        revisions = [self._decode(row) for row in rows]
        grouped: dict[str, list[SourceDocumentMetadataRevision]] = defaultdict(list)
        for revision in revisions:
            if revision.source_document_version_id in wanted:
                self._assert_metadata_chain(revision)
                grouped[revision.source_document_version_id].append(revision)
        result: dict[str, SourceDocumentMetadataRevision] = {}
        documents = SourceDocumentRepository(self.session).get_many(list(wanted))
        for version_id, document in documents.items():
            chain = grouped.get(document.source_document_version_id, [])
            if chain:
                result[version_id] = chain[-1]
        return result


class EvidenceSnapshotRepository:
    """不可变证据快照：作用域门禁、前序链无环、显式替代、集合哈希与重复 no-op。"""

    def __init__(self, session) -> None:
        self.session = session

    # -- 读取 ---------------------------------------------------------------

    @staticmethod
    def _decode_record(record: EvidenceSnapshotV2Record) -> EvidenceSnapshot:
        contract = decode_contract(
            EvidenceSnapshot, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceSnapshot",
            record,
            payload,
            {
                "evidence_snapshot_id": "evidence_snapshot_id",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "upload_mode": "upload_mode",
                "prior_snapshot_id": "prior_snapshot_id",
                "comparison_snapshot_id": "comparison_snapshot_id",
                "collection_sha256": "collection_sha256",
                "created_by": "created_by",
                "created_at": "created_at",
            },
        )
        return contract

    @staticmethod
    def _decode_member_record(
        record: EvidenceSnapshotMemberRecord,
        *,
        expected_snapshot_id: str | None,
        expected_created_at=None,
    ) -> EvidenceSnapshotMember:
        contract = decode_contract(
            EvidenceSnapshotMember, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceSnapshotMember",
            record,
            payload,
            {
                "member_id": "member_id",
                "snapshot_id": "snapshot_id",
                "logical_document_id": "logical_document_id",
                "source_document_version_id": "source_document_version_id",
                "origin": "origin",
            },
        )
        if expected_snapshot_id is not None and (
            record.snapshot_id != expected_snapshot_id
            or contract.snapshot_id != expected_snapshot_id
        ):
            raise PersistedContractInvalid(
                f"证据快照成员 {record.member_id} 跨越当前快照，拒绝还原合同"
            )
        if expected_created_at is not None and to_utc_naive(record.created_at) != expected_created_at:
            raise PersistedContractInvalid(
                f"证据快照成员 {record.member_id} 的创建时间与快照不一致，拒绝还原合同"
            )
        return contract

    @staticmethod
    def _decode_status_event(
        record: EvidenceSnapshotStatusEventRecord,
    ) -> EvidenceSnapshotStatusEvent:
        contract = decode_contract(
            EvidenceSnapshotStatusEvent, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceSnapshotStatusEvent",
            record,
            payload,
            {
                "snapshot_id": "snapshot_id",
                "seq": "seq",
                "from_status": "from_status",
                "to_status": "to_status",
                "event": "event",
                "actor": "actor",
                "reason": "reason",
                "created_at": "created_at",
            },
        )
        return contract

    def _verify_members_mirror(
        self,
        snapshot_id: str,
        contract: EvidenceSnapshot,
        rows: list[EvidenceSnapshotMemberRecord] | None = None,
    ) -> None:
        if rows is None:
            rows = self._all_member_rows_by_snapshot().get(snapshot_id, [])
        decoded_members = [
            self._decode_member_record(
                row,
                expected_snapshot_id=snapshot_id,
                expected_created_at=to_utc_naive(contract.created_at),
            )
            for row in rows
        ]
        actual_members = [
            (
                member.member_id,
                member.logical_document_id,
                member.source_document_version_id,
                member.origin.value,
            )
            for member in decoded_members
        ]
        payload_members = [
            (
                m.member_id,
                m.logical_document_id,
                m.source_document_version_id,
                m.origin.value,
            )
            for m in contract.members
        ]
        if len(actual_members) != len(payload_members) or sorted(actual_members) != sorted(payload_members):
            raise PersistedContractInvalid(
                f"证据快照 {snapshot_id} 成员表与 payload 不一致，拒绝还原合同"
            )

    def _all_member_rows_by_snapshot(
        self,
    ) -> dict[str, list[EvidenceSnapshotMemberRecord]]:
        rows = self.session.execute(
            select(EvidenceSnapshotMemberRecord)
        ).scalars().all()
        grouped: dict[str, list[EvidenceSnapshotMemberRecord]] = defaultdict(list)
        for row in rows:
            member = self._decode_member_record(row, expected_snapshot_id=None)
            grouped[member.snapshot_id].append(row)
        return grouped

    def _validate_status_history(
        self,
        snapshot_id: str,
        rows: list[EvidenceSnapshotStatusEventRecord],
        fallback: SnapshotStatus,
    ) -> SnapshotStatus:
        current = fallback
        for expected_seq, row in enumerate(rows, start=1):
            event = self._decode_status_event(row)
            if row.snapshot_id != snapshot_id or event.snapshot_id != snapshot_id:
                raise PersistedContractInvalid(
                    f"证据快照 {snapshot_id} 的状态事件归属不一致，拒绝还原合同"
                )
            if event.seq != expected_seq:
                raise PersistedContractInvalid(
                    f"证据快照 {snapshot_id} 的状态事件序号不连续，拒绝还原合同"
                )
            if event.from_status != current:
                raise PersistedContractInvalid(
                    f"证据快照 {snapshot_id} 的状态事件前序状态不一致，拒绝还原合同"
                )
            legal = _LEGAL_TRANSITIONS.get(current)
            if legal is None or legal.get(event.event) != event.to_status:
                raise PersistedContractInvalid(
                    f"证据快照 {snapshot_id} 的状态事件违反状态机，拒绝还原合同"
                )
            current = event.to_status
        return current

    def _latest_status(self, snapshot_id: str, fallback: SnapshotStatus) -> SnapshotStatus:
        all_rows = self.session.execute(
            select(EvidenceSnapshotStatusEventRecord)
        ).scalars().all()
        rows = []
        for row in all_rows:
            event = self._decode_status_event(row)
            if event.snapshot_id == snapshot_id:
                rows.append(row)
        rows.sort(key=lambda row: row.seq)
        return self._validate_status_history(snapshot_id, rows, fallback)

    def current_status(self, snapshot_id: str) -> SnapshotStatus:
        record = _get_required(
            self.session, EvidenceSnapshotV2Record, snapshot_id, "EvidenceSnapshot"
        )
        contract = self._decode_record(record)
        self._verify_members_mirror(snapshot_id, contract)
        self._verify_snapshot_relationships(contract)
        return self._latest_status(snapshot_id, contract.status)

    def get(self, evidence_snapshot_id: str) -> EvidenceSnapshot:
        record = _get_required(
            self.session, EvidenceSnapshotV2Record, evidence_snapshot_id, "EvidenceSnapshot"
        )
        contract = self._decode_record(record)
        self._verify_members_mirror(evidence_snapshot_id, contract)
        self._verify_collection_hash(contract)
        self._verify_snapshot_relationships(contract)
        current = self._latest_status(evidence_snapshot_id, contract.status)
        if current != contract.status:
            contract = contract.model_copy(update={"status": current})
        return contract

    def list_by_episode(self, review_episode_id: str) -> list[EvidenceSnapshot]:
        rows = self.session.execute(
            select(EvidenceSnapshotV2Record).order_by(
                EvidenceSnapshotV2Record.created_at,
                EvidenceSnapshotV2Record.evidence_snapshot_id,
            )
        ).scalars().all()
        decoded_rows = [(record, self._decode_record(record)) for record in rows]
        matching = [
            (record, contract)
            for record, contract in decoded_rows
            if contract.review_episode_id == review_episode_id
        ]
        if not matching:
            return []
        ids = [record.evidence_snapshot_id for record, _contract in matching]
        member_map = self._all_member_rows_by_snapshot()
        for record, contract in decoded_rows:
            self._verify_members_mirror(
                record.evidence_snapshot_id,
                contract,
                member_map.get(record.evidence_snapshot_id, []),
            )
            self._verify_collection_hash(contract)
        event_map = self._latest_event_map(
            ids,
            fallbacks={
                record.evidence_snapshot_id: contract.status
                for record, contract in matching
            },
        )
        result: list[EvidenceSnapshot] = []
        for record, contract in matching:
            self._verify_snapshot_relationships(contract)
            current = event_map.get(record.evidence_snapshot_id) or contract.status
            if current != contract.status:
                contract = contract.model_copy(update={"status": current})
            result.append(contract)
        return result

    def _latest_event_map(
        self,
        ids: list[str],
        *,
        fallbacks: dict[str, SnapshotStatus],
    ) -> dict[str, SnapshotStatus]:
        if not ids:
            return {}
        rows = self.session.execute(
            select(EvidenceSnapshotStatusEventRecord)
        ).scalars().all()
        grouped: dict[str, list[EvidenceSnapshotStatusEventRecord]] = defaultdict(list)
        for row in rows:
            event = self._decode_status_event(row)
            if event.snapshot_id in ids:
                grouped[event.snapshot_id].append(row)
        for event_rows in grouped.values():
            event_rows.sort(key=lambda row: row.seq)
        return {
            snapshot_id: self._validate_status_history(
                snapshot_id,
                event_rows,
                fallbacks[snapshot_id],
            )
            for snapshot_id, event_rows in grouped.items()
        }

    def current_snapshot_for_episode(
        self, review_episode_id: str
    ) -> EvidenceSnapshot | None:
        """当前活动快照：只来自 ``ReviewEpisode`` 成对活动指针。

        绝不按 ACTIVE 状态、创建时间、列表顺序、最大 ID 或 legacy
        ``evidence_snapshot_id`` 推断（§5.5/§8.4 反例 3/4）。指针为 null 时返回
        None——即使作用域下存在一个或多个历史 ``ACTIVE`` 快照也不回退。返回前对
        指针指向的快照做完整镜像/闭包校验。
        """
        episode = EpisodeRepository(self.session).get(review_episode_id)
        pointer = episode.active_evidence_snapshot_id
        if pointer is None:
            return None
        return self.get(pointer)

    # -- 作用域门禁与前序链 -------------------------------------------------

    def _check_snapshot_scope(self, snapshot: EvidenceSnapshot) -> None:
        episode = EpisodeRepository(self.session).get(snapshot.review_episode_id)
        if episode.subject_id != snapshot.subject_id:
            raise ScopeViolationError(
                f"EvidenceSnapshot {snapshot.evidence_snapshot_id} 的 subject 超出其 review_episode"
            )
        if episode.project_id != snapshot.project_id:
            raise ScopeViolationError(
                f"EvidenceSnapshot {snapshot.evidence_snapshot_id} 的 project 超出其 review_episode"
            )
        subject = SubjectRepository(self.session).get(snapshot.subject_id)
        if subject.project_id != snapshot.project_id:
            raise ScopeViolationError(
                f"EvidenceSnapshot {snapshot.evidence_snapshot_id} 的 project 与 subject 不一致"
            )

    def _assert_acyclic(
        self,
        start_prior_id: str | None,
        *,
        expected_scope: tuple[str, str, str] | None = None,
    ) -> None:
        """沿前序链上行，遇环或断裂即拒绝。"""
        seen: set[str] = set()
        current = start_prior_id
        while current is not None:
            if current in seen:
                raise SnapshotCycleError(f"证据快照前序链成环：重复访问 {current}")
            seen.add(current)
            record = self.session.get(EvidenceSnapshotV2Record, current)
            if record is None:
                raise InvalidReferenceError(f"证据快照前序链断裂：{current} 不存在")
            prior = self._decode_record(record)
            if expected_scope is not None and (
                prior.project_id,
                prior.subject_id,
                prior.review_episode_id,
            ) != expected_scope:
                raise ScopeViolationError("证据快照前序链包含跨项目/受试者/审核节点记录")
            self._verify_members_mirror(current, prior)
            self._verify_collection_hash(prior)
            self._check_member_versions(prior)
            self._check_comparison_snapshot(prior)
            self._latest_status(prior.evidence_snapshot_id, prior.status)
            current = prior.prior_snapshot_id

    def _verify_collection_hash(self, snapshot: EvidenceSnapshot) -> None:
        expected = evidence_snapshot_collection_hash(
            members=[
                (m.logical_document_id, m.source_document_version_id)
                for m in snapshot.members
            ]
        )
        if snapshot.collection_sha256 != expected:
            raise SnapshotSupersessionError(
                f"证据快照 {snapshot.evidence_snapshot_id} 集合哈希与活动成员集合不一致"
            )

    def _check_member_versions(self, snapshot: EvidenceSnapshot) -> None:
        """成员引用的资料版本必须存在且与快照作用域一致。"""
        source_repo = SourceDocumentRepository(self.session)
        for member in snapshot.members:
            version = self.session.get(
                SourceDocumentVersionV2Record, member.source_document_version_id
            )
            if version is None:
                raise InvalidReferenceError(
                    f"快照成员 {member.member_id} 引用的资料版本 "
                    f"{member.source_document_version_id} 不存在"
            )
            version_contract = SourceDocumentRepository._decode(version)
            _check_document_scope(self.session, version_contract)
            blob = self.session.get(SourceBlobRecord, version_contract.source_blob_sha256)
            if blob is None:
                raise InvalidReferenceError(
                    f"资料版本 {version_contract.source_document_version_id} 引用的 SourceBlob "
                    f"{version_contract.source_blob_sha256} 不存在"
                )
            BlobRepository._decode(blob)
            source_repo._assert_version_chain(version_contract)
            if (
                version_contract.project_id,
                version_contract.subject_id,
                version_contract.review_episode_id,
            ) != (
                snapshot.project_id,
                snapshot.subject_id,
                snapshot.review_episode_id,
            ):
                raise ScopeViolationError(
                    f"快照成员 {member.member_id} 的资料版本超出快照作用域"
                )
            if version_contract.logical_document_id != member.logical_document_id:
                raise SnapshotSupersessionError(
                    f"快照成员 {member.member_id} 的逻辑资料与资料版本不一致"
                )

    def _check_comparison_snapshot(self, snapshot: EvidenceSnapshot) -> None:
        """完整快照的比较基线必须是同一作用域的已存快照。"""
        if snapshot.comparison_snapshot_id is None:
            return
        if snapshot.comparison_snapshot_id == snapshot.evidence_snapshot_id:
            raise SnapshotSupersessionError("快照不能把自身作为比较基线")
        record = self.session.get(
            EvidenceSnapshotV2Record, snapshot.comparison_snapshot_id
        )
        if record is None:
            raise InvalidReferenceError(
                f"比较基线快照 {snapshot.comparison_snapshot_id} 不存在"
            )
        comparison = self._decode_record(record)
        self._verify_members_mirror(snapshot.comparison_snapshot_id, comparison)
        self._verify_collection_hash(comparison)
        self._check_snapshot_scope(comparison)
        self._check_member_versions(comparison)
        self._latest_status(comparison.evidence_snapshot_id, comparison.status)
        if (
            comparison.project_id,
            comparison.subject_id,
            comparison.review_episode_id,
        ) != (
            snapshot.project_id,
            snapshot.subject_id,
            snapshot.review_episode_id,
        ):
            raise ScopeViolationError("快照比较基线必须属于同一项目/受试者/审核节点")

    def _verify_snapshot_relationships(self, snapshot: EvidenceSnapshot) -> None:
        """读取时重验快照来源闭包、作用域和显式关系，拒绝静默漂移。"""
        self._check_snapshot_scope(snapshot)
        self._check_member_versions(snapshot)
        self._verify_collection_hash(snapshot)
        self._check_comparison_snapshot(snapshot)
        self._assert_acyclic(
            snapshot.prior_snapshot_id,
            expected_scope=(
                snapshot.project_id,
                snapshot.subject_id,
                snapshot.review_episode_id,
            ),
        )

    # -- 重复集合 no-op -----------------------------------------------------

    def find_by_collection(
        self,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        upload_mode: UploadMode,
        collection_sha256: str,
    ) -> EvidenceSnapshot | None:
        """返回同作用域/活动成员集合的既有非终态快照（no-op 目标）。

        ``upload_mode`` 只描述用户如何形成集合，不是集合身份。同一成员集合从
        “完整资料”或“补充资料”进入都必须收敛到同一快照，避免制造没有新增证据的
        第二个待处理版本。参数保留用于兼容现有调用合同，但不参与匹配。
        """
        del upload_mode
        rows = self.session.execute(
            select(EvidenceSnapshotV2Record).order_by(
                EvidenceSnapshotV2Record.created_at,
                EvidenceSnapshotV2Record.evidence_snapshot_id,
            )
        ).scalars().all()
        decoded_rows = [(record, self._decode_record(record)) for record in rows]
        member_map = self._all_member_rows_by_snapshot()
        candidates: list[EvidenceSnapshot] = []
        for record, contract in decoded_rows:
            self._verify_members_mirror(
                record.evidence_snapshot_id,
                contract,
                member_map.get(record.evidence_snapshot_id, []),
            )
            self._verify_collection_hash(contract)
            if (
                contract.project_id != project_id
                or contract.subject_id != subject_id
                or contract.review_episode_id != review_episode_id
                or contract.collection_sha256 != collection_sha256
            ):
                continue
            self._verify_snapshot_relationships(contract)
            status = self._latest_status(record.evidence_snapshot_id, contract.status)
            if status in _NOOP_MATCH_STATUSES:
                if status != contract.status:
                    contract = contract.model_copy(update={"status": status})
                candidates.append(contract)
        if not candidates:
            return None
        active = next((c for c in candidates if c.status == SnapshotStatus.ACTIVE), None)
        return active if active is not None else candidates[0]

    def _find_duplicate(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot | None:
        return self.find_by_collection(
            project_id=snapshot.project_id,
            subject_id=snapshot.subject_id,
            review_episode_id=snapshot.review_episode_id,
            upload_mode=snapshot.upload_mode,
            collection_sha256=snapshot.collection_sha256,
        )

    @staticmethod
    def _collection_claim_key(snapshot: EvidenceSnapshot) -> str:
        return canonical_hash(
            {
                "scope": {
                    "project_id": snapshot.project_id,
                    "subject_id": snapshot.subject_id,
                    "review_episode_id": snapshot.review_episode_id,
                },
                "collection_sha256": snapshot.collection_sha256,
            }
        )

    def _claim_collection(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot | None:
        """以已有幂等唯一键串行化同集合并发创建。"""
        key = self._collection_claim_key(snapshot)
        submitted_hash = canonical_hash(
            {
                "key": key,
                "collection_sha256": snapshot.collection_sha256,
            }
        )
        record, created = IdempotencyRepository(self.session).resolve(
            scope="evidence_snapshot_collection/v1",
            idempotency_key=key,
            submitted_hash=submitted_hash,
            result_type="evidence_snapshot",
            result_id=snapshot.evidence_snapshot_id,
        )
        if created:
            return None

        existing = self.get(record.result_id)
        if existing.status in _NOOP_MATCH_STATUSES:
            return existing
        if existing.status not in _TERMINAL_STATUSES:
            raise PersistedContractInvalid(
                f"证据快照集合幂等记录 {key} 绑定了未知状态，拒绝复用"
            )

        # 终态候选按设计必须新建候选；释放仅用于并发集合声明，不删除临床快照
        # 或状态事件历史。删除与终态事件在同一外层事务内完成。
        self.session.execute(
            delete(IdempotencyRecordRow).where(
                IdempotencyRecordRow.scope == "evidence_snapshot_collection/v1",
                IdempotencyRecordRow.idempotency_key == key,
                IdempotencyRecordRow.result_id == record.result_id,
            )
        )
        self.session.flush()
        retry_record, retry_created = IdempotencyRepository(self.session).resolve(
            scope="evidence_snapshot_collection/v1",
            idempotency_key=key,
            submitted_hash=submitted_hash,
            result_type="evidence_snapshot",
            result_id=snapshot.evidence_snapshot_id,
        )
        if retry_created:
            return None
        return self.get(retry_record.result_id)

    # -- 写入 ---------------------------------------------------------------

    def _insert(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        payload_json, payload_sha256 = encode_contract(snapshot)
        record = EvidenceSnapshotV2Record(
            evidence_snapshot_id=snapshot.evidence_snapshot_id,
            project_id=snapshot.project_id,
            subject_id=snapshot.subject_id,
            review_episode_id=snapshot.review_episode_id,
            upload_mode=snapshot.upload_mode.value,
            prior_snapshot_id=snapshot.prior_snapshot_id,
            comparison_snapshot_id=snapshot.comparison_snapshot_id,
            collection_sha256=snapshot.collection_sha256,
            created_by=snapshot.created_by,
            created_at=to_utc_naive(snapshot.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        # 先落快照主行再落成员：自引用前序 FK 会让依赖排序把成员提前导致 FK 失败。
        _flush_guarded(self.session)
        for member in snapshot.members:
            member_json, member_sha = encode_contract(member)
            self.session.add(
                EvidenceSnapshotMemberRecord(
                    member_id=member.member_id,
                    snapshot_id=member.snapshot_id,
                    logical_document_id=member.logical_document_id,
                    source_document_version_id=member.source_document_version_id,
                    origin=member.origin.value,
                    created_at=to_utc_naive(snapshot.created_at),
                    payload_json=member_json,
                    payload_sha256=member_sha,
                )
            )
        _flush_guarded(self.session)
        return snapshot

    def _check_create_preconditions(self, snapshot: EvidenceSnapshot) -> None:
        if snapshot.status != SnapshotStatus.STAGED:
            raise InvalidReferenceError(
                f"候选快照 {snapshot.evidence_snapshot_id} 创建时状态必须为 staged"
            )
        self._verify_collection_hash(snapshot)
        for member in snapshot.members:
            if member.snapshot_id != snapshot.evidence_snapshot_id:
                raise SnapshotSupersessionError(
                    f"快照成员 {member.member_id} 必须属于当前快照"
                )

    def _check_incremental_members(
        self, snapshot: EvidenceSnapshot, prior: EvidenceSnapshot
    ) -> None:
        """增量语义：前序仍是超集，继承/显式替代/新增来源正确。"""
        prior_active = {
            m.logical_document_id: m.source_document_version_id for m in prior.members
        }
        new_by_logical = {m.logical_document_id: m for m in snapshot.members}

        # 1) 前序每个逻辑资料必须保留：继承同一版本，或新版本显式替代前序活动版本。
        for logical, prior_version in prior_active.items():
            member = new_by_logical.get(logical)
            if member is None:
                raise SnapshotSupersessionError(
                    f"补充资料不能静默移除前序活动逻辑资料 {logical}"
                )
            if member.origin == SnapshotMemberOrigin.INHERITED:
                if member.source_document_version_id != prior_version:
                    raise SnapshotSupersessionError(
                        f"继承成员 {logical} 必须沿用前序活动版本 {prior_version}"
                    )
            elif member.origin == SnapshotMemberOrigin.REPLACED:
                version = self.session.get(
                    SourceDocumentVersionV2Record, member.source_document_version_id
                )
                if version is None:
                    raise InvalidReferenceError(
                        f"显式替代成员 {member.member_id} 引用的资料版本不存在"
                    )
                version_contract = SourceDocumentRepository._decode(version)
                if version_contract.supersedes_version_id != prior_version:
                    raise SnapshotSupersessionError(
                        f"显式替代成员 {logical} 必须替代前序快照中的活动版本 {prior_version}"
                    )
            else:  # ADDED
                raise SnapshotSupersessionError(
                    f"已存在于前序快照的逻辑资料 {logical} 不能标记为本次新增"
                )

        # 2) 新增成员必须是前序不存在的逻辑资料；继承/显式替代成员引用前序逻辑资料合法。
        for logical, member in new_by_logical.items():
            if logical not in prior_active and member.origin != SnapshotMemberOrigin.ADDED:
                raise SnapshotSupersessionError(
                    f"前序不存在的逻辑资料 {logical} 必须标记为本次新增"
                )
            if logical in prior_active and member.origin == SnapshotMemberOrigin.ADDED:
                raise SnapshotSupersessionError(
                    f"逻辑资料 {logical} 在前序快照已存在，新增成员来源不合法"
                )

    def create_full(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        """建立完整资料快照：不继承前序；同集合重复确认返回既有快照（no-op）。"""
        self._check_create_preconditions(snapshot)
        if snapshot.upload_mode != UploadMode.FULL:
            raise SnapshotSupersessionError(
                f"create_full 要求上传方式为 full，收到 {snapshot.upload_mode.value}"
            )
        self._check_snapshot_scope(snapshot)
        self._check_comparison_snapshot(snapshot)
        self._check_member_versions(snapshot)
        existing = self._find_duplicate(snapshot)
        if existing is not None:
            return existing
        claimed = self._claim_collection(snapshot)
        if claimed is not None:
            return claimed
        self._insert(snapshot)
        return snapshot

    def create_incremental(self, snapshot: EvidenceSnapshot) -> EvidenceSnapshot:
        """建立补充资料快照：唯一 ACTIVE 前序 + 继承/显式替代；同集合 no-op；链无环。

        前序必须是当前有效（ACTIVE）快照：候选在通过发布门禁前不是有效证据，
        补充资料只能继承活动快照；没有活动快照时必须建立完整资料快照。该门禁在
        仓储层确定性执行，不依赖服务层是否选择了正确基准。
        """
        self._check_create_preconditions(snapshot)
        if snapshot.upload_mode != UploadMode.INCREMENTAL:
            raise SnapshotSupersessionError(
                f"create_incremental 要求上传方式为 incremental，收到 {snapshot.upload_mode.value}"
            )
        self._check_snapshot_scope(snapshot)
        if snapshot.prior_snapshot_id is None:
            raise SnapshotSupersessionError("补充资料快照必须引用唯一的前序快照")
        prior_record = _get_required(
            self.session, EvidenceSnapshotV2Record, snapshot.prior_snapshot_id, "EvidenceSnapshot"
        )
        prior = self._decode_record(prior_record)
        self._verify_members_mirror(snapshot.prior_snapshot_id, prior)
        self._verify_collection_hash(prior)
        if (
            prior.project_id,
            prior.subject_id,
            prior.review_episode_id,
        ) != (
            snapshot.project_id,
            snapshot.subject_id,
            snapshot.review_episode_id,
        ):
            raise ScopeViolationError("补充资料快照的前序快照必须属于同一作用域")
        prior_status = self._latest_status(prior.evidence_snapshot_id, prior.status)
        if prior_status != SnapshotStatus.ACTIVE:
            raise SnapshotSupersessionError(
                f"补充资料快照只能继承当前有效（ACTIVE）快照，前序 "
                f"{prior.evidence_snapshot_id} 处于 {prior_status.value}，拒绝建立"
            )
        self._assert_acyclic(
            snapshot.prior_snapshot_id,
            expected_scope=(
                snapshot.project_id,
                snapshot.subject_id,
                snapshot.review_episode_id,
            ),
        )
        self._check_member_versions(snapshot)
        self._check_incremental_members(snapshot, prior)
        existing = self._find_duplicate(snapshot)
        if existing is not None:
            return existing
        claimed = self._claim_collection(snapshot)
        if claimed is not None:
            return claimed
        self._insert(snapshot)
        return snapshot

    # -- 候选状态机 ---------------------------------------------------------

    def transition_status(
        self,
        snapshot_id: str,
        *,
        event: str,
        new_status: SnapshotStatus,
        actor: str,
        reason: str,
    ) -> EvidenceSnapshot:
        """候选状态机转换；非法转换与终态跳转一律拒绝，合法转换追加审计事件。"""
        try:
            new_status = SnapshotStatus(new_status)
        except (TypeError, ValueError) as exc:
            raise SnapshotStatusTransitionError(
                f"未知的候选状态：{new_status!r}"
            ) from exc
        record = _get_required(
            self.session, EvidenceSnapshotV2Record, snapshot_id, "EvidenceSnapshot"
        )
        contract = self._decode_record(record)
        self._verify_members_mirror(snapshot_id, contract)
        self._verify_collection_hash(contract)
        self._verify_snapshot_relationships(contract)
        current = self._latest_status(snapshot_id, contract.status)
        if current in _TERMINAL_STATUSES:
            raise SnapshotStatusTransitionError(
                f"证据快照 {snapshot_id} 处于终态 {current.value}，不允许再发生候选状态跳转"
            )
        if event == "activate":
            # ready -> active 只允许由 WP-44B 激活事务在同一事务内与 ActivationEvent
            # 及审核节点活动指针对更新一起完成；通用状态机不得单独伪造 ACTIVE。
            raise SnapshotStatusTransitionError(
                "ready→active 只能由证据版本激活事务完成（同一事务追加 ActivationEvent "
                "并原子更新审核节点活动指针），通用状态机拒绝该事件"
            )
        legal = _LEGAL_TRANSITIONS.get(current)
        if legal is None or legal.get(event) != new_status:
            raise SnapshotStatusTransitionError(
                f"非法状态转换：{current.value} --{event}--> {new_status.value}"
            )
        latest_seq = self.session.execute(
            select(func.max(EvidenceSnapshotStatusEventRecord.seq)).where(
                EvidenceSnapshotStatusEventRecord.snapshot_id == snapshot_id
            )
        ).scalar_one()
        seq = int(latest_seq or 0) + 1
        created_at = utc_now()
        event_payload = {
            "snapshot_id": snapshot_id,
            "seq": seq,
            "from_status": current.value,
            "to_status": new_status.value,
            "event": event,
            "actor": actor,
            "reason": reason,
            "created_at": created_at.replace(tzinfo=UTC),
        }
        event_contract = EvidenceSnapshotStatusEvent(**event_payload)
        payload_json, payload_sha256 = encode_contract(event_contract)
        self.session.add(
            EvidenceSnapshotStatusEventRecord(
                snapshot_id=snapshot_id,
                seq=seq,
                from_status=current.value,
                to_status=new_status.value,
                event=event,
                actor=actor,
                reason=reason,
                created_at=created_at,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )
        if new_status in _TERMINAL_STATUSES:
            self.session.execute(
                delete(IdempotencyRecordRow).where(
                    IdempotencyRecordRow.scope == "evidence_snapshot_collection/v1",
                    IdempotencyRecordRow.result_id == snapshot_id,
                )
            )
        _flush_guarded(self.session)
        return self.get(snapshot_id)
