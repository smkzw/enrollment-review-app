"""选择性视觉观察侧车仓储：追加写、来源闭包、成功身份幂等复用。

- 成功观察按 ``observation_identity_sha256`` 幂等复用；同身份不同正文/哈希冲突拒绝；
- 失败关闭只追加明确 ``closed`` 行，不得含模型伪输出；
- 写入/回读均校验 PageArtifact（及可选 OCRPage）来源闭包，不改写 OCR。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.selective_vision_observation import (
    SelectiveVisionObservationRecord,
    SelectiveVisionObservationStatus,
    build_observation_identity_sha256,
    build_risk_reasons_sha256,
    sanitize_observation_usage,
)
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    to_utc_naive,
)
from app.storage.ocr_models import OCRPageRecord, PageArtifactRecord
from app.storage.repositories import (
    InvalidReferenceError,
    NotFoundError,
    RepositoryError,
    _flush_guarded,
    _get_required,
)
from app.storage.selective_vision_observation_models import SelectiveVisionObservationORM

__all__ = [
    "SelectiveVisionObservationConflictError",
    "SelectiveVisionObservationRepository",
    "SelectiveVisionObservationSourceError",
]


class SelectiveVisionObservationRepositoryError(RepositoryError):
    """观察侧车仓储错误基类。"""


class SelectiveVisionObservationConflictError(SelectiveVisionObservationRepositoryError):
    """同一成功身份已存在但内容冲突。"""


class SelectiveVisionObservationSourceError(SelectiveVisionObservationRepositoryError):
    """页产物 / OCR 来源闭包不成立。"""


class SelectiveVisionObservationRepository:
    """不可变视觉观察侧车仓储。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _decode(record: SelectiveVisionObservationORM) -> SelectiveVisionObservationRecord:
        contract = decode_contract(
            SelectiveVisionObservationRecord,
            record.payload_json,
            record.payload_sha256,
        )
        payload = json.loads(record.payload_json)
        check_column_mirrors(
            "SelectiveVisionObservationRecord",
            record,
            payload,
            {
                "observation_id": "observation_id",
                "page_artifact_id": "page_artifact_id",
                "source_document_version_id": "source_document_version_id",
                "source_ref": "source_ref",
                "page_ordinal": "page_ordinal",
                "page_image_sha256": "page_image_sha256",
                "ocr_page_id": "ocr_page_id",
                "ocr_raw_text_sha256": "ocr_raw_text_sha256",
                "plan_version": "plan_version",
                "risk_reasons_sha256": "risk_reasons_sha256",
                "model_id": "model_id",
                "prompt_version": "prompt_version",
                "prompt_sha256": "prompt_sha256",
                "status": "status",
                "observation_text": "observation_text",
                "finish_reason": "finish_reason",
                "failure_kind": "failure_kind",
                "observation_identity_sha256": "observation_identity_sha256",
            },
        )
        if list(record.risk_reasons_json) != list(contract.risk_reasons):
            raise PersistedContractInvalid(
                f"观察 {contract.observation_id} 的 risk_reasons_json 与 payload 不一致"
            )
        if dict(record.usage_json or {}) != dict(contract.usage or {}):
            raise PersistedContractInvalid(
                f"观察 {contract.observation_id} 的 usage_json 与 payload 不一致"
            )
        return contract

    def _verify_source_closure(
        self, observation: SelectiveVisionObservationRecord
    ) -> PageArtifactRecord:
        page = self.session.get(PageArtifactRecord, observation.page_artifact_id)
        if page is None:
            raise InvalidReferenceError(
                f"观察 {observation.observation_id} 引用的 PageArtifact 不存在"
            )
        if page.source_document_version_id != observation.source_document_version_id:
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 的 source_document_version_id "
                "与 PageArtifact 不一致"
            )
        if int(page.page_number) != int(observation.page_ordinal):
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 的 page_ordinal 与 PageArtifact 不一致"
            )
        if page.page_image_sha256 is None:
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 锚定的页产物缺少 page_image_sha256"
            )
        if page.page_image_sha256 != observation.page_image_sha256:
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 的 page_image_sha256 与 PageArtifact 不一致"
            )

        if observation.ocr_page_id is None:
            return page

        ocr = self.session.get(OCRPageRecord, observation.ocr_page_id)
        if ocr is None:
            raise InvalidReferenceError(
                f"观察 {observation.observation_id} 引用的 OCRPage 不存在"
            )
        if ocr.page_artifact_id != observation.page_artifact_id:
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 的 OCRPage 不属于同一 PageArtifact"
            )
        if ocr.raw_text_sha256 != observation.ocr_raw_text_sha256:
            raise SelectiveVisionObservationSourceError(
                f"观察 {observation.observation_id} 的 ocr_raw_text_sha256 与 OCRPage 不一致"
            )
        return page

    def _assert_identity_payload(
        self, observation: SelectiveVisionObservationRecord
    ) -> None:
        expected_reasons = build_risk_reasons_sha256(observation.risk_reasons)
        if observation.risk_reasons_sha256 != expected_reasons:
            raise SelectiveVisionObservationConflictError(
                f"观察 {observation.observation_id} 的 risk_reasons_sha256 与理由集合不一致"
            )
        expected_identity = build_observation_identity_sha256(
            page_artifact_id=observation.page_artifact_id,
            page_image_sha256=observation.page_image_sha256,
            plan_version=observation.plan_version,
            model_id=observation.model_id,
            prompt_sha256=observation.prompt_sha256,
            risk_reasons_sha256=observation.risk_reasons_sha256,
        )
        if observation.observation_identity_sha256 != expected_identity:
            raise SelectiveVisionObservationConflictError(
                f"观察 {observation.observation_id} 的 observation_identity_sha256 不正确"
            )

    def _same_succeeded_payload(
        self,
        existing: SelectiveVisionObservationRecord,
        incoming: SelectiveVisionObservationRecord,
    ) -> bool:
        return (
            existing.page_artifact_id == incoming.page_artifact_id
            and existing.source_document_version_id == incoming.source_document_version_id
            and existing.source_ref == incoming.source_ref
            and existing.page_ordinal == incoming.page_ordinal
            and existing.page_image_sha256 == incoming.page_image_sha256
            and existing.ocr_page_id == incoming.ocr_page_id
            and existing.ocr_raw_text_sha256 == incoming.ocr_raw_text_sha256
            and existing.plan_version == incoming.plan_version
            and list(existing.risk_reasons) == list(incoming.risk_reasons)
            and existing.risk_reasons_sha256 == incoming.risk_reasons_sha256
            and existing.model_id == incoming.model_id
            and existing.prompt_version == incoming.prompt_version
            and existing.prompt_sha256 == incoming.prompt_sha256
            and existing.status == incoming.status
            and existing.observation_text == incoming.observation_text
            and existing.finish_reason == incoming.finish_reason
            and dict(existing.usage or {}) == dict(incoming.usage or {})
            and existing.failure_kind == incoming.failure_kind
            and existing.observation_identity_sha256
            == incoming.observation_identity_sha256
        )

    def _add_row(self, observation: SelectiveVisionObservationRecord) -> None:
        payload_json, payload_sha256 = encode_contract(observation)
        self.session.add(
            SelectiveVisionObservationORM(
                observation_id=observation.observation_id,
                page_artifact_id=observation.page_artifact_id,
                source_document_version_id=observation.source_document_version_id,
                source_ref=observation.source_ref,
                page_ordinal=observation.page_ordinal,
                page_image_sha256=observation.page_image_sha256,
                ocr_page_id=observation.ocr_page_id,
                ocr_raw_text_sha256=observation.ocr_raw_text_sha256,
                plan_version=observation.plan_version,
                risk_reasons_json=list(observation.risk_reasons),
                risk_reasons_sha256=observation.risk_reasons_sha256,
                model_id=observation.model_id,
                prompt_version=observation.prompt_version,
                prompt_sha256=observation.prompt_sha256,
                status=observation.status.value,
                observation_text=observation.observation_text,
                finish_reason=observation.finish_reason,
                usage_json=sanitize_observation_usage(observation.usage),
                failure_kind=observation.failure_kind,
                observation_identity_sha256=observation.observation_identity_sha256,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                created_at=to_utc_naive(observation.created_at),
            )
        )
        _flush_guarded(self.session)

    def get(self, observation_id: str) -> SelectiveVisionObservationRecord:
        record = _get_required(
            self.session,
            SelectiveVisionObservationORM,
            observation_id,
            "SelectiveVisionObservationRecord",
        )
        observation = self._decode(record)
        self._verify_source_closure(observation)
        return observation

    def get_or_none(self, observation_id: str) -> SelectiveVisionObservationRecord | None:
        record = self.session.get(SelectiveVisionObservationORM, observation_id)
        if record is None:
            return None
        observation = self._decode(record)
        self._verify_source_closure(observation)
        return observation

    def list_by_page_artifact(
        self, page_artifact_id: str
    ) -> list[SelectiveVisionObservationRecord]:
        rows = self.session.execute(
            select(SelectiveVisionObservationORM)
            .where(SelectiveVisionObservationORM.page_artifact_id == page_artifact_id)
            .order_by(
                SelectiveVisionObservationORM.created_at,
                SelectiveVisionObservationORM.observation_id,
            )
        ).scalars().all()
        observations = [self._decode(row) for row in rows]
        for observation in observations:
            self._verify_source_closure(observation)
        return observations

    def get_succeeded_by_identity(
        self, observation_identity_sha256: str
    ) -> SelectiveVisionObservationRecord | None:
        record = self.session.execute(
            select(SelectiveVisionObservationORM)
            .where(
                SelectiveVisionObservationORM.observation_identity_sha256
                == observation_identity_sha256
            )
            .where(
                SelectiveVisionObservationORM.status
                == SelectiveVisionObservationStatus.SUCCEEDED.value
            )
        ).scalars().first()
        if record is None:
            return None
        observation = self._decode(record)
        self._verify_source_closure(observation)
        return observation

    def append_closed(
        self, observation: SelectiveVisionObservationRecord
    ) -> SelectiveVisionObservationRecord:
        """追加一条失败关闭审计行（允许多条，从不写成功正文）。"""
        if observation.status != SelectiveVisionObservationStatus.CLOSED:
            raise SelectiveVisionObservationConflictError(
                "append_closed 只接受 status=closed 的观察记录"
            )
        if self.session.get(SelectiveVisionObservationORM, observation.observation_id) is not None:
            raise SelectiveVisionObservationConflictError(
                f"观察 {observation.observation_id} 已存在，拒绝重复写入"
            )
        self._assert_identity_payload(observation)
        self._verify_source_closure(observation)
        self._add_row(observation)
        return self.get(observation.observation_id)

    def get_or_create_succeeded(
        self, observation: SelectiveVisionObservationRecord
    ) -> tuple[SelectiveVisionObservationRecord, bool]:
        """追加成功观察；相同身份与内容直接复用，内容冲突则拒绝。"""
        if observation.status != SelectiveVisionObservationStatus.SUCCEEDED:
            raise SelectiveVisionObservationConflictError(
                "get_or_create_succeeded 只接受 status=succeeded 的观察记录"
            )
        self._assert_identity_payload(observation)
        self._verify_source_closure(observation)

        existing = self.get_succeeded_by_identity(
            observation.observation_identity_sha256
        )
        if existing is not None:
            if not self._same_succeeded_payload(existing, observation):
                raise SelectiveVisionObservationConflictError(
                    f"成功观察身份 {observation.observation_identity_sha256} 已存在，"
                    "但观察内容不一致"
                )
            return existing, False

        if self.session.get(SelectiveVisionObservationORM, observation.observation_id) is not None:
            raise SelectiveVisionObservationConflictError(
                f"观察 {observation.observation_id} 已存在，拒绝以其他身份覆盖"
            )
        self._add_row(observation)
        return self.get(observation.observation_id), True
