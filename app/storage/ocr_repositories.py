"""Phase 4 OCR 持久化与基础证据处理修订仓储（Slice 4.3，worker_01）。

实现不可变 OCR 产物/运行的追加写、页级缓存唯一键、页工作租约与基础证据处理
修订回放，全部以确定性领域错误拒绝非法写入与漂移：

- ``OCRProfileRepository``                识别配置指纹去重（profile_sha256 唯一）；
- ``PageArtifactRepository``              不可变页产物（页级内容去重 +
                                          同身份冲突拒绝）；
- ``RawOcrRequestArtifactRepository`` / ``RawOcrResponseArtifactRepository``
                                          原始请求/响应工件内容寻址去重；
- ``OcrPageRepository``                   页级识别结果（追加写不可变行；同一缓存键
                                          至多一条成功缓存项，由部分唯一索引强制；
                                          成功缓存命中读取同样全量校验）；
- ``OcrRunRepository``                    文件级运行：创建、状态迁移与汇总；
- ``OcrAttemptRepository``                每次真实请求的追加写尝试（attempt_number
                                          自动递增，晚到尝试保留审计）；
- ``PageWorkLeaseRepository``             页工作租约：owner/过期/单调递增代次，
                                          条件更新领取/续租/释放/代次核对；
                                          ``commit_guard`` 是与结果写入同事务的
                                          原子晚到提交门禁；
- ``EvidenceProcessingRevisionRepository`` 不可变基础处理修订：冻结有序页清单，
                                          同一快照允许并存多个修订，读取时对
                                          payload/镜像列/页清单子表/引用产物做
                                          全量交叉校验，明确不可激活。

读取约定与 ``evidence_repositories.py`` 一致：先验 payload 哈希，再按合同严格
还原，交叉校验规范化列与 payload；漂移一律抛 :class:`PersistedContractInvalid`，
不得先用漂移列过滤把坏行静默隐藏。表由迁移 ``0009_ocr_artifacts`` 创建。
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.domain.contracts.enums import (
    OcrAttemptStatus,
    OCRPageStatus,
    OcrRunStatus,
    PageArtifactStatus,
    ProcessingRevisionStatus,
    SnapshotStatus,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
    OCRAttempt,
    OCRRun,
    PageWorkLease,
)
from app.domain.contracts.ocr import (
    OCRPage,
    OCRProfile,
    PageArtifact,
    RawOcrRequestArtifact,
    RawOcrResponseArtifact,
)
from app.domain.publication import ocr_page_cache_hash
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    mirror_json,
    mirror_values_equal,
    to_utc_naive,
    utc_now,
)
from app.storage.evidence_models import EvidenceSnapshotV2Record
from app.storage.evidence_repositories import EvidenceSnapshotRepository
from app.storage.models import JobRecord
from app.storage.ocr_models import (
    EvidenceProcessingRevisionPageRecord,
    EvidenceProcessingRevisionRecord,
    OCRAttemptRecord,
    OCRPageRecord,
    OCRProfileRecord,
    OCRRunRecord,
    PageArtifactRecord,
    PageWorkLeaseRecord,
    RawOcrRequestArtifactRecord,
    RawOcrResponseArtifactRecord,
)
from app.storage.repositories import (
    DuplicateRecordError,
    InvalidReferenceError,
    RepositoryError,
    ScopeViolationError,
    _flush_guarded,
    _get_required,
)

__all__ = [
    "EvidenceProcessingRevisionRepository",
    "OCRProfileRepository",
    "OcrAttemptRepository",
    "OcrIdentityError",
    "OcrLeaseError",
    "OcrPageRepository",
    "OcrRepositoryError",
    "OcrRunRepository",
    "PageArtifactIdentityConflictError",
    "PageArtifactRepository",
    "PageLeaseBusyError",
    "PageLeaseLostError",
    "PageWorkLeaseRepository",
    "RawOcrRequestArtifactRepository",
    "RawOcrResponseArtifactRepository",
    "RevisionManifestError",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# 修订只允许引用已完成（终态）的 OCR 页结果；待处理/处理中页不能被冻结进清单。
_TERMINAL_OCR_PAGE_STATUSES = frozenset(
    {
        OCRPageStatus.SUCCEEDED,
        OCRPageStatus.FAILED,
        OCRPageStatus.CANCELLED,
    }
)

_LEGAL_RUN_TRANSITIONS: dict[OcrRunStatus, frozenset[OcrRunStatus]] = {
    OcrRunStatus.RUNNING: frozenset(
        {
            OcrRunStatus.SUCCEEDED,
            OcrRunStatus.PARTIAL,
            OcrRunStatus.FAILED,
            OcrRunStatus.CANCELLED,
        }
    ),
}

# 候选快照处于这些状态时不允许冻结基础处理修订（已取消/终止失败的历史不可回放）。
_REVISION_FORBIDDEN_SNAPSHOT_STATUSES = frozenset(
    {SnapshotStatus.CANCELLED, SnapshotStatus.TERMINAL_FAILURE}
)


class OcrRepositoryError(RepositoryError):
    """Phase 4 OCR 持久化仓储领域错误基类。"""


class OcrIdentityError(OcrRepositoryError):
    """OCR 身份（缓存键/内容身份/镜像字段）不一致，拒绝写入或还原。"""


class PageArtifactIdentityConflictError(OcrRepositoryError):
    """同 (资料版本, 页码, 页图输入哈希) 但渲染/解码/坐标变换身份不一致。"""


class OcrLeaseError(OcrRepositoryError):
    """页工作租约协调错误基类。"""


class PageLeaseBusyError(OcrLeaseError):
    """页工作租约仍被其他 worker 持有且未过期，拒绝领取。"""


class PageLeaseLostError(OcrLeaseError):
    """页工作租约持有者/代次/过期不匹配（丢失或已被接管）。"""


class RevisionManifestError(OcrRepositoryError):
    """证据处理修订清单与快照/页产物/OCR 身份不一致。"""


def _require_cache_key(work_item_id: str) -> str:
    """页工作项身份必须是页级缓存唯一键（64 位十六进制内容寻址）。"""
    if not isinstance(work_item_id, str) or _SHA256_RE.fullmatch(work_item_id) is None:
        raise OcrIdentityError(
            f"页工作项身份必须是 64 位十六进制缓存唯一键，收到 {work_item_id!r}"
        )
    return work_item_id


def _check_json_mirror(entity: str, column_value: str, payload_value: Any, label: str) -> None:
    """JSON 列与 payload 的规范化文本交叉校验（列存 canonical JSON 文本）。"""
    try:
        parsed = json.loads(column_value)
    except json.JSONDecodeError as exc:
        raise PersistedContractInvalid(
            f"{entity} {label} 列无法解析为 JSON，拒绝还原合同"
        ) from exc
    if not mirror_values_equal(parsed, payload_value):
        raise PersistedContractInvalid(
            f"{entity} {label} 列与已验证 payload 不一致，拒绝还原合同"
        )


# ---------------------------------------------------------------------------
# OCRProfile
# ---------------------------------------------------------------------------


class OCRProfileRepository:
    """识别配置指纹去重：同 profile_sha256 只保存一份，字段必须逐项一致。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRProfileRecord) -> OCRProfile:
        contract = decode_contract(OCRProfile, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRProfile",
            record,
            payload,
            {
                "ocr_profile_id": "ocr_profile_id",
                "profile_sha256": "profile_sha256",
                "extraction_route": "extraction_route",
                "provider": "provider",
                "model_id": "model_id",
                "model_revision": "model_revision",
                "prompt_sha256": "prompt_sha256",
                "parser_version": "parser_version",
                "render_params_sha256": "render_params_sha256",
                "request_params_sha256": "request_params_sha256",
                "layout_parser_version": "layout_parser_version",
                "coordinate_transform_version": "coordinate_transform_version",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, ocr_profile_id: str) -> OCRProfile:
        record = _get_required(self.session, OCRProfileRecord, ocr_profile_id, "OCRProfile")
        return self._decode(record)

    def get_or_none(self, ocr_profile_id: str) -> OCRProfile | None:
        record = self.session.get(OCRProfileRecord, ocr_profile_id)
        return self._decode(record) if record is not None else None

    def get_by_fingerprint(self, fingerprint: str) -> OCRProfile:
        record = self.session.scalar(select(OCRProfileRecord).where(
            OCRProfileRecord.profile_sha256 == fingerprint))
        if record is None:
            raise InvalidReferenceError("识别配置记录缺失")
        return self._decode(record)

    def _verify_same_profile(self, existing: OCRProfile, incoming: OCRProfile) -> None:
        """同指纹必须完全同身份字段；漂移拒绝，绝不静默复用。"""
        if (
            existing.ocr_profile_id != incoming.ocr_profile_id
            or existing.extraction_route != incoming.extraction_route
            or existing.provider != incoming.provider
            or existing.model_id != incoming.model_id
            or existing.model_revision != incoming.model_revision
            or existing.prompt_sha256 != incoming.prompt_sha256
            or existing.parser_version != incoming.parser_version
            or existing.render_params_sha256 != incoming.render_params_sha256
            or existing.request_params_sha256 != incoming.request_params_sha256
            or existing.layout_parser_version != incoming.layout_parser_version
            or existing.coordinate_transform_version != incoming.coordinate_transform_version
            or existing.attempt_namespace != incoming.attempt_namespace
        ):
            raise OcrIdentityError(
                f"OCRProfile 指纹 {incoming.profile_sha256} 已存在但身份字段不一致，"
                "拒绝复用"
            )

    def get_or_create(self, profile: OCRProfile) -> OCRProfile:
        """指纹去重：同 profile_sha256 复用既有（字段一致才允许），否则写入。"""
        existing = self.session.get(OCRProfileRecord, profile.ocr_profile_id)
        if existing is not None:
            decoded = self._decode(existing)
            self._verify_same_profile(decoded, profile)
            return decoded
        payload_json, payload_sha256 = encode_contract(profile)
        record = OCRProfileRecord(
            ocr_profile_id=profile.ocr_profile_id,
            profile_sha256=profile.profile_sha256,
            extraction_route=profile.extraction_route.value,
            provider=profile.provider,
            model_id=profile.model_id,
            model_revision=profile.model_revision,
            prompt_sha256=profile.prompt_sha256,
            parser_version=profile.parser_version,
            render_params_sha256=profile.render_params_sha256,
            request_params_sha256=profile.request_params_sha256,
            layout_parser_version=profile.layout_parser_version,
            coordinate_transform_version=profile.coordinate_transform_version,
            created_at=to_utc_naive(profile.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.execute(
            sqlite_insert(OCRProfileRecord)
            .values(
                ocr_profile_id=record.ocr_profile_id,
                profile_sha256=record.profile_sha256,
                extraction_route=record.extraction_route,
                provider=record.provider,
                model_id=record.model_id,
                model_revision=record.model_revision,
                prompt_sha256=record.prompt_sha256,
                parser_version=record.parser_version,
                render_params_sha256=record.render_params_sha256,
                request_params_sha256=record.request_params_sha256,
                layout_parser_version=record.layout_parser_version,
                coordinate_transform_version=record.coordinate_transform_version,
                created_at=record.created_at,
                payload_json=record.payload_json,
                payload_sha256=record.payload_sha256,
            )
            .on_conflict_do_nothing()
        )
        _flush_guarded(self.session)
        winner = self.session.get(OCRProfileRecord, profile.ocr_profile_id)
        if winner is None:
            winner = self.session.execute(
                select(OCRProfileRecord).where(
                    OCRProfileRecord.profile_sha256 == profile.profile_sha256
                )
            ).scalar_one_or_none()
        if winner is None:
            raise InvalidReferenceError(
                f"OCRProfile {profile.ocr_profile_id} 写入后无法读取，拒绝返回不完整结果"
            )
        decoded = self._decode(winner)
        self._verify_same_profile(decoded, profile)
        return decoded


# ---------------------------------------------------------------------------
# 原始请求/响应工件（内容寻址去重）
# ---------------------------------------------------------------------------


class RawOcrRequestArtifactRepository:
    """不可变原始请求工件：同 sha256 只保存一份，存储引用必须一致。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: RawOcrRequestArtifactRecord) -> RawOcrRequestArtifact:
        contract = decode_contract(
            RawOcrRequestArtifact, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "RawOcrRequestArtifact",
            record,
            payload,
            {
                "raw_request_artifact_id": "raw_request_artifact_id",
                "sha256": "sha256",
                "storage_ref": "storage_ref",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, raw_request_artifact_id: str) -> RawOcrRequestArtifact:
        record = _get_required(
            self.session, RawOcrRequestArtifactRecord, raw_request_artifact_id, "RawOcrRequestArtifact"
        )
        return self._decode(record)

    def get_or_create(self, artifact: RawOcrRequestArtifact) -> RawOcrRequestArtifact:
        existing = self.session.get(
            RawOcrRequestArtifactRecord, artifact.raw_request_artifact_id
        )
        if existing is not None:
            decoded = self._decode(existing)
            if decoded.sha256 != artifact.sha256 or decoded.storage_ref != artifact.storage_ref:
                raise OcrIdentityError(
                    f"RawOcrRequestArtifact {artifact.raw_request_artifact_id} "
                    "已存在但内容哈希/存储引用不一致，拒绝复用"
                )
            return decoded
        payload_json, payload_sha256 = encode_contract(artifact)
        self.session.execute(
            sqlite_insert(RawOcrRequestArtifactRecord)
            .values(
                raw_request_artifact_id=artifact.raw_request_artifact_id,
                sha256=artifact.sha256,
                storage_ref=artifact.storage_ref,
                created_at=to_utc_naive(artifact.created_at),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
            .on_conflict_do_nothing()
        )
        _flush_guarded(self.session)
        winner = self.session.get(
            RawOcrRequestArtifactRecord, artifact.raw_request_artifact_id
        )
        if winner is None:
            raise InvalidReferenceError(
                f"RawOcrRequestArtifact {artifact.raw_request_artifact_id} "
                "写入后无法读取，拒绝返回不完整结果"
            )
        decoded = self._decode(winner)
        if decoded.sha256 != artifact.sha256 or decoded.storage_ref != artifact.storage_ref:
            raise OcrIdentityError(
                f"RawOcrRequestArtifact {artifact.raw_request_artifact_id} "
                "写入后与既有记录内容不一致，拒绝返回"
            )
        return decoded


class RawOcrResponseArtifactRepository:
    """不可变原始响应工件：provider 原文不删改；同 sha256 只保存一份。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: RawOcrResponseArtifactRecord) -> RawOcrResponseArtifact:
        contract = decode_contract(
            RawOcrResponseArtifact, record.payload_json, record.payload_sha256
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "RawOcrResponseArtifact",
            record,
            payload,
            {
                "raw_response_artifact_id": "raw_response_artifact_id",
                "sha256": "sha256",
                "storage_ref": "storage_ref",
                "provider": "provider",
                "model_id": "model_id",
                "model_revision": "model_revision",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, raw_response_artifact_id: str) -> RawOcrResponseArtifact:
        record = _get_required(
            self.session, RawOcrResponseArtifactRecord, raw_response_artifact_id, "RawOcrResponseArtifact"
        )
        return self._decode(record)

    def get_or_create(self, artifact: RawOcrResponseArtifact) -> RawOcrResponseArtifact:
        existing = self.session.get(
            RawOcrResponseArtifactRecord, artifact.raw_response_artifact_id
        )
        if existing is not None:
            decoded = self._decode(existing)
            if (
                decoded.sha256 != artifact.sha256
                or decoded.storage_ref != artifact.storage_ref
                or decoded.provider != artifact.provider
                or decoded.model_id != artifact.model_id
                or decoded.model_revision != artifact.model_revision
            ):
                raise OcrIdentityError(
                    f"RawOcrResponseArtifact {artifact.raw_response_artifact_id} "
                    "已存在但内容哈希/存储引用/provider 身份不一致，拒绝复用"
                )
            return decoded
        payload_json, payload_sha256 = encode_contract(artifact)
        self.session.execute(
            sqlite_insert(RawOcrResponseArtifactRecord)
            .values(
                raw_response_artifact_id=artifact.raw_response_artifact_id,
                sha256=artifact.sha256,
                storage_ref=artifact.storage_ref,
                provider=artifact.provider,
                model_id=artifact.model_id,
                model_revision=artifact.model_revision,
                created_at=to_utc_naive(artifact.created_at),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
            .on_conflict_do_nothing()
        )
        _flush_guarded(self.session)
        winner = self.session.get(
            RawOcrResponseArtifactRecord, artifact.raw_response_artifact_id
        )
        if winner is None:
            raise InvalidReferenceError(
                f"RawOcrResponseArtifact {artifact.raw_response_artifact_id} "
                "写入后无法读取，拒绝返回不完整结果"
            )
        decoded = self._decode(winner)
        if (
            decoded.sha256 != artifact.sha256
            or decoded.storage_ref != artifact.storage_ref
            or decoded.provider != artifact.provider
            or decoded.model_id != artifact.model_id
            or decoded.model_revision != artifact.model_revision
        ):
            raise OcrIdentityError(
                f"RawOcrResponseArtifact {artifact.raw_response_artifact_id} "
                "写入后与既有记录内容不一致，拒绝返回"
            )
        return decoded


# ---------------------------------------------------------------------------
# PageArtifact
# ---------------------------------------------------------------------------


class PageArtifactRepository:
    """不可变页产物：页级内容去重 + 同身份字段冲突拒绝。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: PageArtifactRecord) -> PageArtifact:
        contract = decode_contract(PageArtifact, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "PageArtifact",
            record,
            payload,
            {
                "page_artifact_id": "page_artifact_id",
                "source_document_version_id": "source_document_version_id",
                "page_number": "page_number",
                "original_frame": "original_frame",
                "source_sha256": "source_sha256",
                "page_input_sha256": "page_input_sha256",
                "page_image_sha256": "page_image_sha256",
                "native_text_sha256": "native_text_sha256",
                "native_coordinates_sha256": "native_coordinates_sha256",
                "page_width": "page_width",
                "page_height": "page_height",
                "rotation": "rotation",
                "renderer_version": "renderer_version",
                "decoder_version": "decoder_version",
                "derivative_sha256": "derivative_sha256",
                "coordinate_transform_version": "coordinate_transform_version",
                "status": "status",
                "failure_reason": "failure_reason",
            },
        )
        return contract

    def get(self, page_artifact_id: str) -> PageArtifact:
        record = _get_required(self.session, PageArtifactRecord, page_artifact_id, "PageArtifact")
        return self._decode(record)

    def get_many(self, page_artifact_ids: list[str]) -> list[PageArtifact]:
        """批量还原页产物，保留调用顺序并逐条执行完整合同/镜像校验。"""
        if not page_artifact_ids:
            return []
        rows = self.session.execute(
            select(PageArtifactRecord).where(
                PageArtifactRecord.page_artifact_id.in_(set(page_artifact_ids))
            )
        ).scalars().all()
        by_id = {row.page_artifact_id: row for row in rows}
        missing = next(
            (item_id for item_id in page_artifact_ids if item_id not in by_id), None
        )
        if missing is not None:
            _get_required(self.session, PageArtifactRecord, missing, "PageArtifact")
        return [self._decode(by_id[item_id]) for item_id in page_artifact_ids]

    def get_or_none(self, page_artifact_id: str) -> PageArtifact | None:
        record = self.session.get(PageArtifactRecord, page_artifact_id)
        return self._decode(record) if record is not None else None

    @staticmethod
    def _identity_equals(existing: PageArtifact, incoming: PageArtifact) -> bool:
        return (
            existing.source_document_version_id == incoming.source_document_version_id
            and existing.page_number == incoming.page_number
            and existing.original_frame == incoming.original_frame
            and existing.source_sha256 == incoming.source_sha256
            and existing.page_input_sha256 == incoming.page_input_sha256
            and existing.page_image_sha256 == incoming.page_image_sha256
            and existing.native_text_sha256 == incoming.native_text_sha256
            and existing.native_coordinates_sha256 == incoming.native_coordinates_sha256
            and existing.page_width == incoming.page_width
            and existing.page_height == incoming.page_height
            and existing.rotation == incoming.rotation
            and existing.renderer_version == incoming.renderer_version
            and existing.decoder_version == incoming.decoder_version
            and existing.derivative_sha256 == incoming.derivative_sha256
            and existing.coordinate_transform_version == incoming.coordinate_transform_version
            and existing.status == incoming.status
            and existing.failure_reason == incoming.failure_reason
        )

    def get_or_create(self, artifact: PageArtifact) -> PageArtifact:
        """页级内容去重：同资料页、输入和处理版本复用既有页产物。

        成功/降级页以资料版本、页码、页输入、渲染版本、解码版本和坐标变换版本
        为稳定身份；任一处理版本变化均可追加新页产物。失败页没有真实页输入或
        处理版本，只按确定性主键幂等；同一页的不同失败原因可以保留为不同记录。
        """
        existing_by_id = self.session.get(PageArtifactRecord, artifact.page_artifact_id)
        if existing_by_id is not None:
            decoded = self._decode(existing_by_id)
            if not self._identity_equals(decoded, artifact):
                raise PageArtifactIdentityConflictError(
                    f"PageArtifact {artifact.page_artifact_id} 已存在但内容身份不一致，拒绝复用"
                )
            return decoded

        if artifact.status == PageArtifactStatus.FAILED:
            payload_json, payload_sha256 = encode_contract(artifact)
            self.session.add(
                PageArtifactRecord(
                    page_artifact_id=artifact.page_artifact_id,
                    source_document_version_id=artifact.source_document_version_id,
                    page_number=artifact.page_number,
                    original_frame=artifact.original_frame,
                    source_sha256=artifact.source_sha256,
                    page_input_sha256=None,
                    page_image_sha256=None,
                    native_text_sha256=None,
                    native_coordinates_sha256=None,
                    page_width=None,
                    page_height=None,
                    rotation=None,
                    renderer_version=None,
                    decoder_version=None,
                    derivative_sha256=artifact.derivative_sha256,
                    coordinate_transform_version=artifact.coordinate_transform_version,
                    status=artifact.status.value,
                    failure_reason=artifact.failure_reason,
                    created_at=utc_now(),
                    payload_json=payload_json,
                    payload_sha256=payload_sha256,
                )
            )
            _flush_guarded(self.session)
            return artifact

        existing_rows = self.session.execute(
            select(PageArtifactRecord).where(
                PageArtifactRecord.source_document_version_id
                == artifact.source_document_version_id,
                PageArtifactRecord.page_number == artifact.page_number,
                PageArtifactRecord.page_input_sha256 == artifact.page_input_sha256,
                PageArtifactRecord.renderer_version == artifact.renderer_version,
                PageArtifactRecord.decoder_version == artifact.decoder_version,
                PageArtifactRecord.coordinate_transform_version
                == artifact.coordinate_transform_version,
            )
        ).scalars().all()
        if len(existing_rows) > 1:
            raise PageArtifactIdentityConflictError(
                f"PageArtifact 页 (资料版本 {artifact.source_document_version_id}, "
                f"页码 {artifact.page_number}) 存在重复处理身份，拒绝静默选择"
            )
        if existing_rows:
            decoded = self._decode(existing_rows[0])
            if not self._identity_equals(decoded, artifact):
                raise PageArtifactIdentityConflictError(
                    f"PageArtifact 页 (资料版本 {artifact.source_document_version_id}, "
                    f"页码 {artifact.page_number}, 输入 {artifact.page_input_sha256[:12] if artifact.page_input_sha256 else '未知'}) "
                    "已存在但渲染/解码/坐标变换身份不一致，拒绝复用"
                )
            return decoded
        payload_json, payload_sha256 = encode_contract(artifact)
        record = PageArtifactRecord(
            page_artifact_id=artifact.page_artifact_id,
            source_document_version_id=artifact.source_document_version_id,
            page_number=artifact.page_number,
            original_frame=artifact.original_frame,
            source_sha256=artifact.source_sha256,
            page_input_sha256=artifact.page_input_sha256,
            page_image_sha256=artifact.page_image_sha256,
            native_text_sha256=artifact.native_text_sha256,
            native_coordinates_sha256=artifact.native_coordinates_sha256,
            page_width=artifact.page_width,
            page_height=artifact.page_height,
            rotation=artifact.rotation,
            renderer_version=artifact.renderer_version,
            decoder_version=artifact.decoder_version,
            derivative_sha256=artifact.derivative_sha256,
            coordinate_transform_version=artifact.coordinate_transform_version,
            status=artifact.status.value,
            failure_reason=artifact.failure_reason,
            created_at=utc_now(),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return artifact

    def list_by_source_document_version(
        self, source_document_version_id: str
    ) -> list[PageArtifact]:
        """按资料版本返回全部页产物（按页码升序，逐条全量校验）。"""
        rows = self.session.execute(
            select(PageArtifactRecord)
            .where(
                PageArtifactRecord.source_document_version_id
                == source_document_version_id
            )
            .order_by(PageArtifactRecord.page_number, PageArtifactRecord.page_artifact_id)
        ).scalars().all()
        return [self._decode(row) for row in rows]


# ---------------------------------------------------------------------------
# OCRPage（页级缓存项）
# ---------------------------------------------------------------------------


class OcrPageRepository:
    """页级识别结果仓储：追加写不可变行，同一缓存键至多一条成功缓存项。

    每次结果都是一条独立不可变行（失败/取消/处理中可多条共存）；成功缓存命中只
    返回那条不可变 SUCCEEDED 行，命中前对同一缓存键全部行做完整校验，损坏的
    非成功行不会被静默隐藏。
    """

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRPageRecord) -> OCRPage:
        contract = decode_contract(OCRPage, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRPage",
            record,
            payload,
            {
                "ocr_page_id": "ocr_page_id",
                "page_artifact_id": "page_artifact_id",
                "source_sha256": "source_sha256",
                "page_number": "page_number",
                "page_input_sha256": "page_input_sha256",
                "ocr_profile_sha256": "ocr_profile_sha256",
                "cache_key": "cache_key",
                "layout_parser_version": "layout_parser_version",
                "coordinate_transform_version": "coordinate_transform_version",
                "raw_text": "raw_text",
                "raw_text_sha256": "raw_text_sha256",
                "normalized_text": "normalized_text",
                "layout_sidecar_sha256": "layout_sidecar_sha256",
                "status": "status",
                "failure_reason": "failure_reason",
                "started_at": "started_at",
                "completed_at": "completed_at",
            },
        )
        _check_json_mirror("OCRPage", record.quality_json, payload["quality"], "quality")
        _check_json_mirror(
            "OCRPage", record.risk_items_json, payload["risk_items"], "risk_items"
        )
        return contract

    def _decode_with_closure(self, record: OCRPageRecord) -> OCRPage:
        """解码 + 识别配置闭包校验：ocr_profile_id 指向的 Profile 指纹必须一致。

        ``ocr_profile_id`` 是存储层外键列（合同不携带），用 profile 指纹闭包校验
        防止外键与指纹漂移。
        """
        contract = self._decode(record)
        profile_record = self.session.get(OCRProfileRecord, record.ocr_profile_id)
        if profile_record is None:
            raise PersistedContractInvalid(
                f"OCRPage {record.ocr_page_id} 引用的 OCRProfile "
                f"{record.ocr_profile_id} 不存在，拒绝还原合同"
            )
        profile = OCRProfileRepository._decode(profile_record)
        if profile.profile_sha256 != contract.ocr_profile_sha256:
            raise PersistedContractInvalid(
                f"OCRPage {record.ocr_page_id} 的识别配置指纹与引用 Profile 不一致，"
                "拒绝还原合同"
            )
        return contract

    def _resolve_profile_id(self, ocr_profile_sha256: str) -> str:
        profile_record = self.session.execute(
            select(OCRProfileRecord).where(
                OCRProfileRecord.profile_sha256 == ocr_profile_sha256
            )
        ).scalar_one_or_none()
        if profile_record is None:
            raise InvalidReferenceError(
                f"OCRProfile 指纹 {ocr_profile_sha256[:12]}… 不存在，无法建立 OCRPage"
            )
        return profile_record.ocr_profile_id

    def get(self, ocr_page_id: str) -> OCRPage:
        record = _get_required(self.session, OCRPageRecord, ocr_page_id, "OCRPage")
        return self._decode_with_closure(record)

    def get_many(self, ocr_page_ids: list[str]) -> list[OCRPage]:
        """批量还原 OCR 页并一次加载 Profile 闭包，查询数不随页数增长。"""
        if not ocr_page_ids:
            return []
        rows = self.session.execute(
            select(OCRPageRecord).where(
                OCRPageRecord.ocr_page_id.in_(set(ocr_page_ids))
            )
        ).scalars().all()
        by_id = {row.ocr_page_id: row for row in rows}
        missing = next((item_id for item_id in ocr_page_ids if item_id not in by_id), None)
        if missing is not None:
            _get_required(self.session, OCRPageRecord, missing, "OCRPage")

        profile_ids = {row.ocr_profile_id for row in rows}
        profile_rows = self.session.execute(
            select(OCRProfileRecord).where(
                OCRProfileRecord.ocr_profile_id.in_(profile_ids)
            )
        ).scalars().all()
        profiles = {
            row.ocr_profile_id: OCRProfileRepository._decode(row)
            for row in profile_rows
        }
        decoded: dict[str, OCRPage] = {}
        for row in rows:
            contract = self._decode(row)
            profile = profiles.get(row.ocr_profile_id)
            if profile is None:
                raise PersistedContractInvalid(
                    f"OCRPage {row.ocr_page_id} 引用的 OCRProfile "
                    f"{row.ocr_profile_id} 不存在，拒绝还原合同"
                )
            if profile.profile_sha256 != contract.ocr_profile_sha256:
                raise PersistedContractInvalid(
                    f"OCRPage {row.ocr_page_id} 的识别配置指纹与引用 Profile不一致，"
                    "拒绝还原合同"
                )
            decoded[row.ocr_page_id] = contract
        return [decoded[item_id] for item_id in ocr_page_ids]

    def list_by_cache_key(self, cache_key: str) -> list[OCRPage]:
        """返回同一缓存键的全部不可变结果行（追加写历史，含失败/取消/处理中）。

        逐行做完整镜像/闭包校验；任一行的规范化列漂移都抛
        :class:`PersistedContractInvalid`，绝不静默隐藏坏行。
        """
        _require_cache_key(cache_key)
        rows = self.session.execute(
            select(OCRPageRecord)
            .where(OCRPageRecord.cache_key == cache_key)
            .order_by(OCRPageRecord.created_at, OCRPageRecord.ocr_page_id)
        ).scalars().all()
        return [self._decode_with_closure(row) for row in rows]

    def get_successful_by_cache_key(self, cache_key: str) -> OCRPage | None:
        """缓存命中：只返回那条不可变 SUCCEEDED 行（同一缓存键至多一条）。

        命中前对同一缓存键的**全部**行做完整镜像/闭包校验，任一行的漂移都抛
        :class:`PersistedContractInvalid`，因此损坏的非成功行不会被静默隐藏，
        也不会被错误地当作成功缓存。晚到/失败结果永不冒充成功缓存。
        """
        _require_cache_key(cache_key)
        success: OCRPage | None = None
        for page in self.list_by_cache_key(cache_key):
            if page.status != OCRPageStatus.SUCCEEDED:
                continue
            if success is not None:
                raise OcrIdentityError(
                    f"OCRPage 缓存键 {cache_key} 存在多条成功结果，"
                    "违反单成功缓存不变量，拒绝命中"
                )
            success = page
        return success

    def list_by_content_identity(
        self,
        *,
        source_sha256: str,
        page_number: int,
        ocr_profile_sha256: str,
        page_input_sha256: str,
        layout_parser_version: str | None,
        coordinate_transform_version: str,
    ) -> list[OCRPage]:
        """内容级身份（设计书内容哈希契约，不含页产物绑定）的全部不可变行。

        内容身份 = 文件内容哈希 + 页码 + 识别配置指纹 + 实际页图输入哈希 +
        布局/坐标变换版本；``page_artifact_id`` 不参与。跨资料版本的成功/失败行
        全部还原并逐行做完整镜像/闭包校验，坏行漂移照常抛
        :class:`PersistedContractInvalid`，绝不静默隐藏；供适配器在 v2
        （页产物绑定）键未命中时做内容级推理复用。
        """
        rows = self.session.execute(
            select(OCRPageRecord)
            .where(
                OCRPageRecord.source_sha256 == source_sha256,
                OCRPageRecord.page_number == page_number,
                OCRPageRecord.ocr_profile_sha256 == ocr_profile_sha256,
                OCRPageRecord.page_input_sha256 == page_input_sha256,
                OCRPageRecord.layout_parser_version == layout_parser_version,
                OCRPageRecord.coordinate_transform_version
                == coordinate_transform_version,
            )
            .order_by(OCRPageRecord.created_at, OCRPageRecord.ocr_page_id)
        ).scalars().all()
        return [self._decode_with_closure(row) for row in rows]

    def get_latest_successful_by_content_identity(
        self,
        *,
        source_sha256: str,
        page_number: int,
        ocr_profile_sha256: str,
        page_input_sha256: str,
        layout_parser_version: str | None,
        coordinate_transform_version: str,
    ) -> OCRPage | None:
        """内容级推理复用源：同内容身份下最新的成功行（可来自他版页产物）。

        同一内容身份在多个页产物上各自拥有成功行是 v2 缓存身份下的合法状态；
        复用源按 ``(completed_at, ocr_page_id)`` 确定性取最新，保证同一数据库
        状态的复用选择唯一。失败/取消/处理中行永不充当复用源。
        """
        latest: OCRPage | None = None
        for page in self.list_by_content_identity(
            source_sha256=source_sha256,
            page_number=page_number,
            ocr_profile_sha256=ocr_profile_sha256,
            page_input_sha256=page_input_sha256,
            layout_parser_version=layout_parser_version,
            coordinate_transform_version=coordinate_transform_version,
        ):
            if page.status != OCRPageStatus.SUCCEEDED:
                continue
            if (
                latest is None
                or (page.completed_at, page.ocr_page_id)
                > (latest.completed_at, latest.ocr_page_id)
            ):
                latest = page
        return latest

    def list_by_page_artifact(self, page_artifact_id: str) -> list[OCRPage]:
        rows = self.session.execute(
            select(OCRPageRecord)
            .where(OCRPageRecord.page_artifact_id == page_artifact_id)
            .order_by(OCRPageRecord.ocr_page_id)
        ).scalars().all()
        return [self._decode_with_closure(row) for row in rows]

    def list_by_source_document_version(
        self, source_document_version_id: str
    ) -> list[OCRPage]:
        """按资料版本读取全部不可变页行，供恢复/进度投影按缓存键去重。"""
        rows = self.session.execute(
            select(OCRPageRecord)
            .join(
                PageArtifactRecord,
                PageArtifactRecord.page_artifact_id == OCRPageRecord.page_artifact_id,
            )
            .where(
                PageArtifactRecord.source_document_version_id
                == source_document_version_id
            )
            .order_by(
                OCRPageRecord.page_number,
                OCRPageRecord.created_at,
                OCRPageRecord.ocr_page_id,
            )
        ).scalars().all()
        return [self._decode_with_closure(row) for row in rows]

    def create(self, page: OCRPage) -> OCRPage:
        """追加写一条不可变 OCR 页结果行（append-only，不覆盖历史）。

        - 同 ``ocr_page_id`` 重复写入由主键唯一约束拒绝；
        - 同缓存键已有 SUCCEEDED 成功缓存项时，再次写入成功结果被拒绝
          （部分唯一索引在存储层强制），绝不覆盖/污染既有成功缓存；
        - 失败/取消/处理中结果可与成功或其他非成功结果并存为独立不可变行，
          各自完整回放。

        worker 提交成功结果前必须先在同一事务内通过
        :meth:`PageWorkLeaseRepository.commit_guard` 的晚到门禁；本方法只负责
        不可变追加写，不负责代次校验。
        """
        _require_cache_key(page.cache_key)
        if page.status == OCRPageStatus.SUCCEEDED:
            existing_success = self.session.execute(
                select(OCRPageRecord).where(
                    OCRPageRecord.cache_key == page.cache_key,
                    OCRPageRecord.status == OCRPageStatus.SUCCEEDED.value,
                )
            ).scalar_one_or_none()
            if existing_success is not None:
                decoded = self._decode_with_closure(existing_success)
                raise DuplicateRecordError(
                    f"OCRPage 缓存键 {page.cache_key[:12]}… 已存在不可变成功缓存项 "
                    f"{decoded.ocr_page_id}，拒绝覆盖或污染成功缓存"
                )
        self._append(page)
        return self.get(page.ocr_page_id)

    def _append(self, page: OCRPage) -> None:
        payload_json, payload_sha256 = encode_contract(page)
        record = OCRPageRecord(
            ocr_page_id=page.ocr_page_id,
            page_artifact_id=page.page_artifact_id,
            source_sha256=page.source_sha256,
            page_number=page.page_number,
            page_input_sha256=page.page_input_sha256,
            ocr_profile_id=self._resolve_profile_id(page.ocr_profile_sha256),
            ocr_profile_sha256=page.ocr_profile_sha256,
            cache_key=page.cache_key,
            layout_parser_version=page.layout_parser_version,
            coordinate_transform_version=page.coordinate_transform_version,
            raw_text=page.raw_text,
            raw_text_sha256=page.raw_text_sha256,
            normalized_text=page.normalized_text,
            layout_sidecar_sha256=page.layout_sidecar_sha256,
            quality_json=_canonical_json_text(page.quality),
            risk_items_json=_canonical_json_text(
                [item.model_dump(mode="json") for item in page.risk_items]
            ),
            status=page.status.value,
            failure_reason=page.failure_reason,
            started_at=to_utc_naive(page.started_at),
            completed_at=to_utc_naive(page.completed_at),
            created_at=utc_now(),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)


def _canonical_json_text(value: Any) -> str:
    """把子合同/列表规范化为与 ``mirror_json`` 可比的紧凑 JSON 文本。"""
    return json.dumps(
        value.model_dump(mode="json") if hasattr(value, "model_dump") else value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# OCRRun / OCRAttempt
# ---------------------------------------------------------------------------


class OcrRunRepository:
    """文件级 OCR 运行：创建、状态迁移与页级汇总。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRRunRecord) -> OCRRun:
        contract = decode_contract(OCRRun, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRRun",
            record,
            payload,
            {
                "ocr_run_id": "ocr_run_id",
                "source_document_version_id": "source_document_version_id",
                "ocr_profile_id": "ocr_profile_id",
                "ocr_profile_sha256": "ocr_profile_sha256",
                "job_id": "job_id",
                "status": "status",
                "page_total": "page_total",
                "page_succeeded": "page_succeeded",
                "page_failed": "page_failed",
                "started_at": "started_at",
                "completed_at": "completed_at",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, ocr_run_id: str) -> OCRRun:
        record = _get_required(self.session, OCRRunRecord, ocr_run_id, "OCRRun")
        return self._decode(record)

    def create(self, run: OCRRun) -> OCRRun:
        """创建文件级运行；同 ID 重复创建被唯一约束拒绝。"""
        existing = self.session.get(OCRRunRecord, run.ocr_run_id)
        if existing is not None:
            raise DuplicateRecordError(f"OCRRun {run.ocr_run_id} 已存在")
        payload_json, payload_sha256 = encode_contract(run)
        record = OCRRunRecord(
            ocr_run_id=run.ocr_run_id,
            source_document_version_id=run.source_document_version_id,
            ocr_profile_id=run.ocr_profile_id,
            ocr_profile_sha256=run.ocr_profile_sha256,
            job_id=run.job_id,
            status=run.status.value,
            page_total=run.page_total,
            page_succeeded=run.page_succeeded,
            page_failed=run.page_failed,
            started_at=to_utc_naive(run.started_at),
            completed_at=to_utc_naive(run.completed_at),
            created_at=to_utc_naive(run.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return run

    def update_status(
        self,
        ocr_run_id: str,
        *,
        status: OcrRunStatus,
        page_succeeded: int,
        page_failed: int,
        completed_at=None,
    ) -> OCRRun:
        """运行状态迁移（RUNNING -> 终态），汇总与状态一致后重写 payload。"""
        record = _get_required(self.session, OCRRunRecord, ocr_run_id, "OCRRun")
        current = self._decode(record)
        if current.status not in _LEGAL_RUN_TRANSITIONS or status not in _LEGAL_RUN_TRANSITIONS[
            current.status
        ]:
            raise OcrRepositoryError(
                f"非法 OCR 运行状态迁移：{current.status.value} -> {status.value}"
            )
        updated = current.model_copy(
            update={
                "status": status,
                "page_succeeded": page_succeeded,
                "page_failed": page_failed,
                "completed_at": completed_at,
            }
        )
        payload_json, payload_sha256 = encode_contract(updated)
        record.payload_json = payload_json
        record.payload_sha256 = payload_sha256
        record.status = updated.status.value
        record.page_succeeded = updated.page_succeeded
        record.page_failed = updated.page_failed
        record.completed_at = to_utc_naive(updated.completed_at)
        _flush_guarded(self.session)
        return self.get(ocr_run_id)

    def list_by_job(self, job_id: str) -> list[OCRRun]:
        rows = self.session.execute(
            select(OCRRunRecord)
            .where(OCRRunRecord.job_id == job_id)
            .order_by(OCRRunRecord.created_at, OCRRunRecord.ocr_run_id)
        ).scalars().all()
        return [self._decode(row) for row in rows]

    def recover_running_for_job(
        self,
        job_id: str,
        *,
        status: OcrRunStatus,
        completed_at=None,
        source_document_version_id: str | None = None,
    ) -> list[str]:
        """收敛进程中断遗留的 ``RUNNING`` 文件运行。

        OCRRun 状态不是进程内内存；进程可能在页结果提交后、运行汇总前退出。
        恢复时把仍为 ``RUNNING`` 的历史运行转为明确终态，并只按已落盘的尝试
        统计成功/失败页。晚到审计尝试不计入页完成数，避免重试重复统计。
        """
        if status == OcrRunStatus.RUNNING:
            raise OcrRepositoryError("恢复中的 OCR 运行不能再次标记为 RUNNING")
        query = select(OCRRunRecord).where(
            OCRRunRecord.job_id == job_id,
            OCRRunRecord.status == OcrRunStatus.RUNNING.value,
        )
        if source_document_version_id is not None:
            query = query.where(
                OCRRunRecord.source_document_version_id == source_document_version_id
            )
        rows = self.session.execute(query.order_by(OCRRunRecord.created_at)).scalars().all()
        when = completed_at or datetime.now(UTC)
        if when.tzinfo is None:
            # ``app.storage.codecs.utc_now`` is intentionally SQLite-naive, while
            # domain contracts require UTC-aware timestamps before JSON encoding.
            when = when.replace(tzinfo=UTC)
        recovered: list[str] = []
        for row in rows:
            run = self._decode(row)
            attempts = self.session.execute(
                select(OCRAttemptRecord).where(
                    OCRAttemptRecord.ocr_run_id == run.ocr_run_id
                )
            ).scalars().all()
            succeeded_keys = {
                attempt.cache_key
                for attempt in attempts
                if attempt.status == OcrAttemptStatus.SUCCEEDED.value
            }
            failed_keys = {
                attempt.cache_key
                for attempt in attempts
                if attempt.status == OcrAttemptStatus.FAILED.value
            } - succeeded_keys
            page_succeeded = min(run.page_total, len(succeeded_keys))
            page_failed = min(run.page_total - page_succeeded, len(failed_keys))
            self.update_status(
                run.ocr_run_id,
                status=status,
                page_succeeded=page_succeeded,
                page_failed=page_failed,
                completed_at=when,
            )
            recovered.append(run.ocr_run_id)
        return recovered

    def recover_orphaned_running(self, *, completed_at=None) -> list[str]:
        """收敛已不再执行的 Job 遗留的 ``RUNNING`` OCRRun。

        这是启动恢复的最后兜底：即使取消/失败发生在 OCRRun 汇总写入之后，
        终态 Job 也不能让文件级运行永久停在处理中。仍由活动 Job 持有的运行
        保留给当前 worker；其页尝试统计规则与按 Job 恢复保持一致。
        """
        rows = self.session.execute(
            select(OCRRunRecord).where(
                OCRRunRecord.status == OcrRunStatus.RUNNING.value
            )
        ).scalars().all()
        when = completed_at or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        recovered: list[str] = []
        active_states = {"running", "cancel_requested", "recovering"}
        for row in rows:
            job = self.session.get(JobRecord, row.job_id) if row.job_id else None
            job_state = job.state if job is not None else None
            if job_state in active_states:
                continue
            run = self._decode(row)
            attempts = self.session.execute(
                select(OCRAttemptRecord).where(
                    OCRAttemptRecord.ocr_run_id == run.ocr_run_id
                )
            ).scalars().all()
            succeeded_keys = {
                attempt.cache_key
                for attempt in attempts
                if attempt.status == OcrAttemptStatus.SUCCEEDED.value
            }
            failed_keys = {
                attempt.cache_key
                for attempt in attempts
                if attempt.status == OcrAttemptStatus.FAILED.value
            } - succeeded_keys
            status = (
                OcrRunStatus.CANCELLED
                if job_state == "cancelled"
                else OcrRunStatus.FAILED
            )
            self.update_status(
                run.ocr_run_id,
                status=status,
                page_succeeded=min(run.page_total, len(succeeded_keys)),
                page_failed=min(
                    run.page_total - min(run.page_total, len(succeeded_keys)),
                    len(failed_keys),
                ),
                completed_at=when,
            )
            recovered.append(run.ocr_run_id)
        return recovered


class OcrAttemptRepository:
    """每次真实 OCR 请求的追加写尝试；attempt_number 在同一 cache_key 上自动递增。"""

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: OCRAttemptRecord) -> OCRAttempt:
        contract = decode_contract(OCRAttempt, record.payload_json, record.payload_sha256)
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "OCRAttempt",
            record,
            payload,
            {
                "attempt_id": "attempt_id",
                "ocr_run_id": "ocr_run_id",
                "ocr_page_id": "ocr_page_id",
                "cache_key": "cache_key",
                "attempt_number": "attempt_number",
                "status": "status",
                "failure_category": "failure_category",
                "rejection_reason": "rejection_reason",
                "started_at": "started_at",
                "completed_at": "completed_at",
                "raw_request_artifact_id": "raw_request_artifact_id",
                "raw_response_artifact_id": "raw_response_artifact_id",
                "work_lease_owner": "work_lease_owner",
                "work_lease_generation": "work_lease_generation",
                "omlx_lease_owner": "omlx_lease_owner",
                "retry_of_attempt_id": "retry_of_attempt_id",
                "created_at": "created_at",
            },
        )
        return contract

    def get(self, attempt_id: str) -> OCRAttempt:
        record = _get_required(self.session, OCRAttemptRecord, attempt_id, "OCRAttempt")
        return self._decode(record)

    def append(self, attempt: OCRAttempt) -> OCRAttempt:
        """追加写一次尝试；attempt_number = 同 cache_key 最大序号 + 1。

        尝试历史永不覆盖（包括被拒绝的晚到尝试）；``retry_of_attempt_id`` 记录
        重试关系。调用方传入的 attempt_number 仅作校验（必须 >= 1），实际序号由
        仓储确定。
        """
        _require_cache_key(attempt.cache_key)
        OcrRunRepository(self.session).get(attempt.ocr_run_id)  # 运行必须存在
        latest = self.session.execute(
            select(OCRAttemptRecord)
            .where(OCRAttemptRecord.cache_key == attempt.cache_key)
            .order_by(OCRAttemptRecord.attempt_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        attempt_number = (latest.attempt_number if latest is not None else 0) + 1
        retry_of_attempt_id = attempt.retry_of_attempt_id or (
            latest.attempt_id if latest is not None else None
        )
        if retry_of_attempt_id is not None:
            retry_of = self.session.get(OCRAttemptRecord, retry_of_attempt_id)
            if retry_of is None or retry_of.cache_key != attempt.cache_key:
                raise OcrIdentityError(
                    f"OCRAttempt {attempt.attempt_id} 的重试来源不属于同一页工作项，拒绝写入"
                )
        numbered = attempt.model_copy(
            update={
                "attempt_number": attempt_number,
                "retry_of_attempt_id": retry_of_attempt_id,
            }
        )
        payload_json, payload_sha256 = encode_contract(numbered)
        record = OCRAttemptRecord(
            attempt_id=numbered.attempt_id,
            ocr_run_id=numbered.ocr_run_id,
            ocr_page_id=numbered.ocr_page_id,
            cache_key=numbered.cache_key,
            attempt_number=numbered.attempt_number,
            status=numbered.status.value,
            failure_category=(
                numbered.failure_category.value if numbered.failure_category else None
            ),
            rejection_reason=numbered.rejection_reason,
            started_at=to_utc_naive(numbered.started_at),
            completed_at=to_utc_naive(numbered.completed_at),
            raw_request_artifact_id=numbered.raw_request_artifact_id,
            raw_response_artifact_id=numbered.raw_response_artifact_id,
            work_lease_owner=numbered.work_lease_owner,
            work_lease_generation=numbered.work_lease_generation,
            omlx_lease_owner=numbered.omlx_lease_owner,
            retry_of_attempt_id=numbered.retry_of_attempt_id,
            created_at=to_utc_naive(numbered.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return self.get(numbered.attempt_id)

    def list_by_cache_key(self, cache_key: str) -> list[OCRAttempt]:
        """返回同一页工作项的全部尝试（含晚到/失败，按序号升序）。"""
        _require_cache_key(cache_key)
        rows = self.session.execute(
            select(OCRAttemptRecord)
            .where(OCRAttemptRecord.cache_key == cache_key)
            .order_by(OCRAttemptRecord.attempt_number)
        ).scalars().all()
        return [self._decode(row) for row in rows]

    def list_by_run(self, ocr_run_id: str) -> list[OCRAttempt]:
        rows = self.session.execute(
            select(OCRAttemptRecord)
            .where(OCRAttemptRecord.ocr_run_id == ocr_run_id)
            .order_by(OCRAttemptRecord.cache_key, OCRAttemptRecord.attempt_number)
        ).scalars().all()
        return [self._decode(row) for row in rows]

    def list_by_page(self, ocr_page_id: str) -> list[OCRAttempt]:
        rows = self.session.execute(
            select(OCRAttemptRecord)
            .where(OCRAttemptRecord.ocr_page_id == ocr_page_id)
            .order_by(OCRAttemptRecord.attempt_number)
        ).scalars().all()
        return [self._decode(row) for row in rows]


# ---------------------------------------------------------------------------
# 页工作租约（只防重复执行，不是并发额度）
# ---------------------------------------------------------------------------


class PageWorkLeaseRepository:
    """页工作租约：owner/过期/单调递增代次，条件更新领取/续租/释放/代次核对。

    领取顺序由 worker 保证为“页工作租约 -> oMLX 门禁 -> 推理”；本仓储只提供
    确定性条件更新与身份校验，不实现并发额度。
    """

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _to_contract(record: PageWorkLeaseRecord) -> PageWorkLease:
        return PageWorkLease(
            work_item_id=record.work_item_id,
            lease_owner=record.lease_owner,
            lease_expires_at=(
                record.lease_expires_at.replace(tzinfo=UTC)
                if record.lease_expires_at is not None
                else None
            ),
            lease_generation=record.lease_generation,
            updated_at=record.updated_at.replace(tzinfo=UTC),
        )

    def get(self, work_item_id: str) -> PageWorkLease | None:
        _require_cache_key(work_item_id)
        record = self.session.get(PageWorkLeaseRecord, work_item_id)
        return self._to_contract(record) if record is not None else None

    @staticmethod
    def validate_work_identity(
        cache_key: str,
        *,
        page_artifact_id: str,
        source_sha256: str,
        page_number: int,
        ocr_profile_sha256: str,
        page_input_sha256: str,
        layout_parser_version: str | None,
        coordinate_transform_version: str,
    ) -> str:
        """结果提交前重算缓存唯一键，证明冻结输入/Profile 身份未被篡改。"""
        _require_cache_key(cache_key)
        expected = ocr_page_cache_hash(
            page_artifact_id=page_artifact_id,
            source_sha256=source_sha256,
            page_number=page_number,
            ocr_profile_sha256=ocr_profile_sha256,
            page_input_sha256=page_input_sha256,
            layout_parser_version=layout_parser_version,
            coordinate_transform_version=coordinate_transform_version,
        )
        if expected != cache_key:
            raise OcrIdentityError(
                f"页工作项缓存键 {cache_key} 与冻结输入/Profile 身份不符（应为 "
                f"{expected}），拒绝提交结果"
            )
        return cache_key

    def _ensure_row(self, work_item_id: str) -> None:
        self.session.execute(
            sqlite_insert(PageWorkLeaseRecord)
            .values(
                work_item_id=work_item_id,
                lease_owner=None,
                lease_expires_at=None,
                lease_generation=0,
                updated_at=utc_now(),
            )
            .on_conflict_do_nothing()
        )

    def claim(
        self, work_item_id: str, owner: str, lease_ttl: timedelta
    ) -> PageWorkLease:
        """条件领取：无持有者或租约已过期才成功，代次单调 +1。

        返回领取后的租约（含新代次与过期时间）；仍被持有且未过期时抛
        :class:`PageLeaseBusyError`。
        """
        _require_cache_key(work_item_id)
        if not owner:
            raise OcrLeaseError("页工作租约持有者不能为空")
        self._ensure_row(work_item_id)
        now = utc_now()
        expires_at = now + lease_ttl
        result = self.session.execute(
            update(PageWorkLeaseRecord)
            .where(
                PageWorkLeaseRecord.work_item_id == work_item_id,
                or_(
                    PageWorkLeaseRecord.lease_owner.is_(None),
                    PageWorkLeaseRecord.lease_expires_at.is_(None),
                    PageWorkLeaseRecord.lease_expires_at < now,
                ),
            )
            .values(
                lease_owner=owner,
                lease_expires_at=expires_at,
                lease_generation=PageWorkLeaseRecord.lease_generation + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            held = self.get(work_item_id)
            raise PageLeaseBusyError(
                f"页工作项 {work_item_id[:12]}… 租约仍由 "
                f"{held.lease_owner if held else '?'} 持有且未过期，拒绝重复领取"
            )
        claimed = self.get(work_item_id)
        if claimed is None or claimed.lease_owner != owner:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 领取后无法读回自身租约"
            )
        return claimed

    def heartbeat(
        self, work_item_id: str, owner: str, generation: int, lease_ttl: timedelta
    ) -> PageWorkLease:
        """续租：owner/代次/过期必须匹配；不匹配视为租约丢失。"""
        _require_cache_key(work_item_id)
        now = utc_now()
        result = self.session.execute(
            update(PageWorkLeaseRecord)
            .where(
                PageWorkLeaseRecord.work_item_id == work_item_id,
                PageWorkLeaseRecord.lease_owner == owner,
                PageWorkLeaseRecord.lease_generation == generation,
                PageWorkLeaseRecord.lease_expires_at.is_not(None),
                PageWorkLeaseRecord.lease_expires_at >= now,
            )
            .values(lease_expires_at=now + lease_ttl, updated_at=now)
        )
        if result.rowcount != 1:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 租约续租失败（owner/代次/过期不匹配）"
            )
        refreshed = self.get(work_item_id)
        if refreshed is None:
            raise PageLeaseLostError(f"页工作项 {work_item_id[:12]}… 续租后读回失败")
        return refreshed

    def release(self, work_item_id: str, owner: str, generation: int) -> PageWorkLease:
        """释放租约：保留代次（单调），清空持有者与过期。"""
        _require_cache_key(work_item_id)
        now = utc_now()
        result = self.session.execute(
            update(PageWorkLeaseRecord)
            .where(
                PageWorkLeaseRecord.work_item_id == work_item_id,
                PageWorkLeaseRecord.lease_owner == owner,
                PageWorkLeaseRecord.lease_generation == generation,
            )
            .values(
                lease_owner=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 租约释放失败（owner/代次不匹配）"
            )
        released = self.get(work_item_id)
        if released is None:
            raise PageLeaseLostError(f"页工作项 {work_item_id[:12]}… 释放后读回失败")
        return released

    def commit_guard(
        self,
        work_item_id: str,
        owner: str,
        generation: int,
        *,
        page_artifact_id: str,
        source_sha256: str,
        page_number: int,
        ocr_profile_sha256: str,
        page_input_sha256: str,
        layout_parser_version: str | None,
        coordinate_transform_version: str,
    ) -> PageWorkLease:
        """原子晚到结果提交门禁：条件写 + 冻结输入/Profile 身份校验。

        这是结果提交的**唯一**原子门禁：worker_03 必须先调用本方法，再在同一
        Session 事务内写入 OCRPage 结果与 OCRAttempt 尝试记录，最后一起提交。
        本方法先执行条件 UPDATE（命中 owner/代次/未过期的租约行才写入，零行匹配
        即失败），在结果插入前取得 SQLite 写事务；随后结果写与门禁在同一事务内
        原子提交或回滚，晚到结果不可能在门禁通过后因代次被接管而进入成功缓存。
        冻结输入/Profile 身份在本事务内重算缓存键，防止篡改输入提交。

        被拒绝的晚到尝试（``REJECTED_LATE``）必须写入**独立**的短事务：门禁
        失败的提交事务已回滚，不能共享；尝试记录保持追加写。``assert_current``
        只是只读探针，不构成提交门禁。
        """
        _require_cache_key(work_item_id)
        self.validate_work_identity(
            work_item_id,
            page_artifact_id=page_artifact_id,
            source_sha256=source_sha256,
            page_number=page_number,
            ocr_profile_sha256=ocr_profile_sha256,
            page_input_sha256=page_input_sha256,
            layout_parser_version=layout_parser_version,
            coordinate_transform_version=coordinate_transform_version,
        )
        if not owner:
            raise OcrLeaseError("页工作租约持有者不能为空")
        now = utc_now()  # naive，用于 SQLite 列写入与 WHERE 比较
        now_aware = datetime.now(UTC)  # aware，用于合同（PageWorkLease）比较
        result = self.session.execute(
            update(PageWorkLeaseRecord)
            .where(
                PageWorkLeaseRecord.work_item_id == work_item_id,
                PageWorkLeaseRecord.lease_owner == owner,
                PageWorkLeaseRecord.lease_generation == generation,
                PageWorkLeaseRecord.lease_expires_at.is_not(None),
                PageWorkLeaseRecord.lease_expires_at >= now,
            )
            .values(updated_at=now)
        )
        if result.rowcount != 1:
            lease = self.get(work_item_id)
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 提交门禁未通过（owner/代次/过期不匹配，"
                f"当前持有者 {lease.lease_owner if lease else '?'}，代次 "
                f"{lease.lease_generation if lease else '?'}），晚到结果被拒绝"
            )
        current = self.get(work_item_id)
        if (
            current is None
            or current.lease_owner != owner
            or current.lease_generation != generation
            or current.lease_expires_at is None
            or current.lease_expires_at < now_aware
        ):
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 提交门禁后读回不一致，晚到结果被拒绝"
            )
        return current

    def assert_current(
        self, work_item_id: str, owner: str, generation: int
    ) -> PageWorkLease:
        """只读探针：核对 owner/代次/过期策略是否仍匹配（不构成提交门禁）。

        只用于诊断/心跳式检查。结果提交必须使用 :meth:`commit_guard` 在同一
        事务内做条件写门禁；只读断言后再写缓存不是原子晚到结果门禁。
        """
        _require_cache_key(work_item_id)
        lease = self.get(work_item_id)
        now = datetime.now(UTC)
        if lease is None or lease.lease_owner != owner:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 租约持有者不匹配，晚到结果被拒绝"
            )
        if lease.lease_generation != generation:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 租约代次不匹配（期望 {generation}，"
                f"当前 {lease.lease_generation}），晚到结果被拒绝"
            )
        if lease.lease_expires_at is None or lease.lease_expires_at < now:
            raise PageLeaseLostError(
                f"页工作项 {work_item_id[:12]}… 租约已过期，晚到结果被拒绝"
            )
        return lease


# ---------------------------------------------------------------------------
# 不可变基础证据处理修订
# ---------------------------------------------------------------------------


class EvidenceProcessingRevisionRepository:
    """不可变基础处理修订：冻结有序页清单；读取时全量交叉校验；不可激活。

    Slice 4.3 约束：修订状态只能为 READY 且 ``is_activatable`` 恒为 False；
    同一快照允许并存多个不可变修订（校对/后续完整修订均派生新修订），重复主键
    ID 被拒绝；本仓储不提供也不触碰任何活动指针/激活路径。
    """

    def __init__(self, session) -> None:
        self.session = session

    @staticmethod
    def _decode_record(record: EvidenceProcessingRevisionRecord) -> EvidenceProcessingRevision:
        if record.revision_kind != "base":
            raise OcrIdentityError(
                f"证据处理修订 {record.evidence_processing_revision_id} 不是 base 修订"
                "（revision_kind != base），请使用 CompleteEvidenceProcessingRevisionRepository"
            )
        contract = decode_contract(
            EvidenceProcessingRevision,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceProcessingRevision",
            record,
            payload,
            {
                "evidence_processing_revision_id": "evidence_processing_revision_id",
                "evidence_snapshot_id": "evidence_snapshot_id",
                "project_id": "project_id",
                "subject_id": "subject_id",
                "review_episode_id": "review_episode_id",
                "manifest_sha256": "manifest_sha256",
                "status": "status",
                "is_activatable": "is_activatable",
                "created_by": "created_by",
                "created_at": "created_at",
            },
        )
        return contract

    @staticmethod
    def _decode_page_entry(
        record: EvidenceProcessingRevisionPageRecord,
        *,
        expected_revision_id: str,
    ) -> EvidenceProcessingRevisionPage:
        contract = decode_contract(
            EvidenceProcessingRevisionPage,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "EvidenceProcessingRevisionPage",
            record,
            payload,
            {
                "entry_id": "entry_id",
                "position": "position",
                "source_document_version_id": "source_document_version_id",
                "page_number": "page_number",
                "original_frame": "original_frame",
                "page_artifact_id": "page_artifact_id",
                "ocr_page_id": "ocr_page_id",
                "status": "status",
                "failure_reason": "failure_reason",
            },
        )
        if record.revision_id != expected_revision_id:
            raise PersistedContractInvalid(
                f"页清单条目 {record.entry_id} 跨越修订 {expected_revision_id}，拒绝还原合同"
            )
        if contract.position != record.position:
            raise PersistedContractInvalid(
                f"页清单条目 {record.entry_id} 位置与列不一致，拒绝还原合同"
            )
        return contract

    def _manifest_rows(self, revision_id: str) -> list[EvidenceProcessingRevisionPageRecord]:
        rows = self.session.execute(
            select(EvidenceProcessingRevisionPageRecord)
            .where(EvidenceProcessingRevisionPageRecord.revision_id == revision_id)
            .order_by(EvidenceProcessingRevisionPageRecord.position)
        ).scalars().all()
        return rows

    def _verify_manifest_mirror(
        self,
        revision_id: str,
        contract: EvidenceProcessingRevision,
        rows: list[EvidenceProcessingRevisionPageRecord] | None = None,
    ) -> None:
        """页清单子表与 payload 清单三方交叉校验（按位置逐项比较）。"""
        if rows is None:
            rows = self._manifest_rows(revision_id)
        decoded = [
            self._decode_page_entry(row, expected_revision_id=revision_id) for row in rows
        ]
        actual = [
            (
                entry.entry_id,
                entry.position,
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
                entry.failure_reason,
            )
            for entry in decoded
        ]
        expected = [
            (
                entry.entry_id,
                entry.position,
                entry.source_document_version_id,
                entry.page_number,
                entry.original_frame,
                entry.page_artifact_id,
                entry.ocr_page_id,
                entry.status.value,
                entry.failure_reason,
            )
            for entry in contract.manifest
        ]
        if actual != expected:
            raise PersistedContractInvalid(
                f"证据处理修订 {revision_id} 页清单子表与 payload 不一致，拒绝还原合同"
            )

    def _verify_manifest_artifacts(self, contract: EvidenceProcessingRevision) -> None:
        """页清单引用的 PageArtifact/OCRPage 必须存在且冻结身份一致。"""
        for entry in contract.manifest:
            artifact_record = self.session.get(PageArtifactRecord, entry.page_artifact_id)
            if artifact_record is None:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单引用的 "
                    f"PageArtifact {entry.page_artifact_id} 不存在"
                )
            artifact = PageArtifactRepository._decode(artifact_record)
            if artifact.source_document_version_id != entry.source_document_version_id:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的资料版本与页产物不一致"
                )
            if artifact.page_number != entry.page_number:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的页码与页产物不一致"
                )
            if artifact.original_frame != entry.original_frame:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的原始 frame 与页产物不一致"
                )
            if artifact.status != entry.status:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的状态与页产物不一致"
                )
            if artifact.status == PageArtifactStatus.FAILED and entry.ocr_page_id is not None:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 引用失败页产物，失败页无页图，不得绑定 OCR 结果"
                )
            if entry.ocr_page_id is None:
                continue
            ocr_record = self.session.get(OCRPageRecord, entry.ocr_page_id)
            if ocr_record is None:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单引用的 "
                    f"OCRPage {entry.ocr_page_id} 不存在"
                )
            ocr_page = OcrPageRepository._decode(ocr_record)
            if ocr_page.status not in _TERMINAL_OCR_PAGE_STATUSES:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 引用的 "
                    f"OCRPage {entry.ocr_page_id} 尚未完成，不能冻结进清单"
                )
            if ocr_page.page_artifact_id != entry.page_artifact_id:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的 OCRPage 与页产物不一致"
                )
            if ocr_page.page_number != entry.page_number:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的 OCRPage 页码与页产物不一致"
                )
            if ocr_page.source_sha256 != artifact.source_sha256:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的 OCRPage 源文件哈希与页产物不一致"
                )
            if ocr_page.page_input_sha256 != artifact.page_image_sha256:
                raise RevisionManifestError(
                    f"修订 {contract.evidence_processing_revision_id} 页清单条目 "
                    f"{entry.entry_id} 的 OCRPage 页图输入哈希与实际送入 OCR 的"
                    "页图字节哈希不一致，拒绝冻结"
                )

    def _check_snapshot(
        self, revision: EvidenceProcessingRevision
    ) -> EvidenceSnapshotV2Record:
        """快照必须存在、作用域一致且处于可回放状态（非取消/终止失败）。"""
        record = self.session.get(EvidenceSnapshotV2Record, revision.evidence_snapshot_id)
        if record is None:
            raise InvalidReferenceError(
                f"证据快照 {revision.evidence_snapshot_id} 不存在，无法建立处理修订"
            )
        snapshot_repo = EvidenceSnapshotRepository(self.session)
        snapshot = snapshot_repo.get(revision.evidence_snapshot_id)
        if (
            snapshot.project_id,
            snapshot.subject_id,
            snapshot.review_episode_id,
        ) != (
            revision.project_id,
            revision.subject_id,
            revision.review_episode_id,
        ):
            raise ScopeViolationError(
                f"证据处理修订 {revision.evidence_processing_revision_id} 的作用域 "
                "与绑定快照不一致"
            )
        if snapshot.status in _REVISION_FORBIDDEN_SNAPSHOT_STATUSES:
            raise RevisionManifestError(
                f"候选快照 {revision.evidence_snapshot_id} 处于 "
                f"{snapshot.status.value}，不能冻结基础处理修订"
            )
        return record

    def create(self, revision: EvidenceProcessingRevision) -> EvidenceProcessingRevision:
        """写入不可变基础证据处理修订（页清单 + 引用产物全部校验后一次性冻结）。

        同一快照允许并存多个不同修订：同快照上的校对会派生新修订，迁移 0010
        也会从基础修订新建完整修订，因此存储层不设“一快照一修订”约束。
        幂等属于创建命令/Job（重复请求回放既有修订），不是存储不变量；重复
        主键 ID 由主键唯一约束拒绝。本方法不触碰活动指针。
        """
        self.assert_non_activatable(revision)
        self._check_snapshot(revision)
        existing = self.session.get(
            EvidenceProcessingRevisionRecord, revision.evidence_processing_revision_id
        )
        if existing is not None:
            raise DuplicateRecordError(
                f"证据处理修订 {revision.evidence_processing_revision_id} 已存在，"
                "拒绝重复创建（幂等应由创建命令/Job 负责）"
            )
        self._verify_manifest_artifacts(revision)
        payload_json, payload_sha256 = encode_contract(revision)
        record = EvidenceProcessingRevisionRecord(
            evidence_processing_revision_id=revision.evidence_processing_revision_id,
            evidence_snapshot_id=revision.evidence_snapshot_id,
            project_id=revision.project_id,
            subject_id=revision.subject_id,
            review_episode_id=revision.review_episode_id,
            manifest_sha256=revision.manifest_sha256,
            status=revision.status.value,
            is_activatable=revision.is_activatable,
            revision_kind="base",
            created_by=revision.created_by,
            created_at=to_utc_naive(revision.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
        self.session.add(record)
        _flush_guarded(self.session)
        for entry in revision.manifest:
            entry_json, entry_sha = encode_contract(entry)
            self.session.add(
                EvidenceProcessingRevisionPageRecord(
                    revision_id=revision.evidence_processing_revision_id,
                    position=entry.position,
                    entry_id=entry.entry_id,
                    source_document_version_id=entry.source_document_version_id,
                    page_number=entry.page_number,
                    original_frame=entry.original_frame,
                    page_artifact_id=entry.page_artifact_id,
                    ocr_page_id=entry.ocr_page_id,
                    status=entry.status.value,
                    failure_reason=entry.failure_reason,
                    created_at=to_utc_naive(revision.created_at),
                    payload_json=entry_json,
                    payload_sha256=entry_sha,
                )
            )
        _flush_guarded(self.session)
        return self.get(revision.evidence_processing_revision_id)

    def get(self, evidence_processing_revision_id: str) -> EvidenceProcessingRevision:
        """不可变读取：payload 哈希 + 镜像列 + 页清单子表 + 引用产物全量校验。"""
        record = _get_required(
            self.session,
            EvidenceProcessingRevisionRecord,
            evidence_processing_revision_id,
            "EvidenceProcessingRevision",
        )
        contract = self._decode_record(record)
        self._verify_manifest_mirror(evidence_processing_revision_id, contract)
        self._verify_manifest_artifacts(contract)
        return contract

    def list_by_snapshot(self, evidence_snapshot_id: str) -> list[EvidenceProcessingRevision]:
        rows = self.session.execute(
            select(EvidenceProcessingRevisionRecord)
            .where(
                EvidenceProcessingRevisionRecord.evidence_snapshot_id
                == evidence_snapshot_id
            )
            .where(EvidenceProcessingRevisionRecord.revision_kind == "base")
            .order_by(
                EvidenceProcessingRevisionRecord.created_at,
                EvidenceProcessingRevisionRecord.evidence_processing_revision_id,
            )
        ).scalars().all()
        return [self.get(row.evidence_processing_revision_id) for row in rows]

    def list_by_episode(self, review_episode_id: str) -> list[EvidenceProcessingRevision]:
        rows = self.session.execute(
            select(EvidenceProcessingRevisionRecord)
            .where(EvidenceProcessingRevisionRecord.review_episode_id == review_episode_id)
            .where(EvidenceProcessingRevisionRecord.revision_kind == "base")
            .order_by(
                EvidenceProcessingRevisionRecord.created_at,
                EvidenceProcessingRevisionRecord.evidence_processing_revision_id,
            )
        ).scalars().all()
        return [self.get(row.evidence_processing_revision_id) for row in rows]

    # -- 显式不可激活：Slice 4.3 无任何激活/活动指针路径 ----------------------

    @staticmethod
    def assert_non_activatable(revision: EvidenceProcessingRevision) -> None:
        """领域门禁：基础修订不可激活（合同已强制，仓储写入前再兜底一次）。"""
        if revision.status != ProcessingRevisionStatus.READY or revision.is_activatable:
            raise RevisionManifestError(
                "基础证据处理修订明确不可激活，禁止携带激活状态或激活意图"
            )
