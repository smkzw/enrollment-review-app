"""Slice 4.4 校对覆盖层与有效文本投影服务（WP-44B）。

- ``create_correction``      追加一条校对记录：锚定不可变 ``OCRPage.raw_text``
  （哈希 + 原始字符范围），逐字回验原文本；关键变化类别（极性/数值/小数点/单位/
  日期/语义连接词）必须携带显式二次确认 payload，缺确认即拒绝（§8.3.1）；
- ``supersede_correction``   明确替代当前链头（同一页/同一 raw 哈希/同一原始范围）；
- ``effective_text_for_revision`` / ``effective_text_for_page``
                              从不可变 raw OCR + 完整修订所选校对链头确定性投影
                              有效文本并重算哈希（每次重算，不链式沿用旧投影）。

本服务只保存来源校对与投影，不据此更新 ``RuleExpression`` / ``ClinicalFact`` /
入排判断（Phase 4 停止点）。
"""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import CorrectionChangeKind
from app.domain.contracts.evidence_locator import (
    BLOCKING_CORRECTION_KINDS,
    CorrectionRecord,
    validate_correction_source_anchor,
)
from app.evidence.effective_text import EffectiveTextProjection, project_effective_text
from app.evidence.risk import critical_semantics_changed
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository,
    CorrectionRepository,
)
from app.storage.ocr_repositories import OcrPageRepository

__all__ = [
    "CorrectionConfirmationRequiredError",
    "CorrectionRangeError",
    "EvidenceCorrectionService",
]




def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)

class EvidenceCorrectionServiceError(RuntimeError):
    """校对服务领域错误基类。"""


class CorrectionRangeError(EvidenceCorrectionServiceError):
    """校对字符范围/原文本与不可变原 OCR 不一致。"""


class CorrectionConfirmationRequiredError(EvidenceCorrectionServiceError):
    """关键语义变化（极性/数值/小数点/单位/日期/语义连接词）缺二次确认。"""


def _minimal_changed_range(
    *, text_start: int, original_text: str, corrected_text: str
) -> tuple[int, int, str, str]:
    """Shrink a validated submitted replacement to its actual raw-text change."""
    if original_text == corrected_text:
        raise CorrectionRangeError("校对前后文字没有实际变化，拒绝保存")

    prefix_length = 0
    shared_length = min(len(original_text), len(corrected_text))
    while (
        prefix_length < shared_length
        and original_text[prefix_length] == corrected_text[prefix_length]
    ):
        prefix_length += 1

    suffix_length = 0
    original_remaining = len(original_text) - prefix_length
    corrected_remaining = len(corrected_text) - prefix_length
    while (
        suffix_length < original_remaining
        and suffix_length < corrected_remaining
        and original_text[len(original_text) - suffix_length - 1]
        == corrected_text[len(corrected_text) - suffix_length - 1]
    ):
        suffix_length += 1

    original_end = len(original_text) - suffix_length
    corrected_end = len(corrected_text) - suffix_length
    minimal_start = text_start + prefix_length
    return (
        minimal_start,
        text_start + original_end,
        original_text[prefix_length:original_end],
        corrected_text[prefix_length:corrected_end],
    )


class EvidenceCorrectionService:
    """校对覆盖层 + 有效文本投影服务（只锚定不可变 raw OCR）。"""

    def __init__(self, session_factory: sessionmaker, artifact_store=None) -> None:
        self.session_factory = session_factory
        self.artifact_store = artifact_store

    def create_correction(
        self,
        *,
        ocr_page_id: str,
        text_start: int,
        text_end: int,
        original_text: str,
        corrected_text: str,
        change_kind: CorrectionChangeKind,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        supersedes_correction_id: str | None = None,
        confirmation_actor: str | None = None,
        confirmation_at=None,
        correction_id: str | None = None,
        affected_scope: list[str] | None = None,
    ) -> CorrectionRecord:
        with self.session_factory() as session, session.begin():
            return self.create_correction_in_session(
                session,
                ocr_page_id=ocr_page_id,
                text_start=text_start,
                text_end=text_end,
                original_text=original_text,
                corrected_text=corrected_text,
                change_kind=change_kind,
                reason=reason,
                actor=actor,
                base_processing_revision_id=base_processing_revision_id,
                supersedes_correction_id=supersedes_correction_id,
                confirmation_actor=confirmation_actor,
                confirmation_at=confirmation_at,
                correction_id=correction_id,
                affected_scope=affected_scope,
            )

    def create_correction_in_session(
        self,
        session: Session,
        *,
        ocr_page_id: str,
        text_start: int,
        text_end: int,
        original_text: str,
        corrected_text: str,
        change_kind: CorrectionChangeKind,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        supersedes_correction_id: str | None = None,
        confirmation_actor: str | None = None,
        confirmation_at=None,
        correction_id: str | None = None,
        affected_scope: list[str] | None = None,
    ) -> CorrectionRecord:
        ocr = OcrPageRepository(session).get(ocr_page_id)
        raw = ocr.raw_text
        try:
            validate_correction_source_anchor(
                raw,
                text_start=text_start,
                text_end=text_end,
                original_text=original_text,
            )
        except ValueError as error:
            raise CorrectionRangeError(str(error)) from error
        change_kind = CorrectionChangeKind(change_kind)
        # Critical semantics are assessed against the caller's fully validated
        # before/after text so surrounding units, dates and logical words remain
        # visible to the detector. Only the persisted source range is narrowed.
        requires_confirmation = (
            change_kind in BLOCKING_CORRECTION_KINDS
            or critical_semantics_changed(original_text, corrected_text)
        )
        if requires_confirmation and confirmation_actor is None:
            reason_text = (
                "所选变化类别属于关键语义变化"
                if change_kind in BLOCKING_CORRECTION_KINDS
                else "系统在校对前后识别到极性、数值、单位、日期或逻辑关系变化"
            )
            raise CorrectionConfirmationRequiredError(
                f"{reason_text}，必须携带显式二次确认（确认人与确认时间）"
            )
        if confirmation_actor is not None and confirmation_at is None:
            raise CorrectionConfirmationRequiredError(
                "确认人与确认时间必须同时提供"
            )
        text_start, text_end, original_text, corrected_text = _minimal_changed_range(
            text_start=text_start,
            original_text=original_text,
            corrected_text=corrected_text,
        )
        correction = CorrectionRecord(
            correction_id=correction_id or f"corr-{uuid4().hex}",
            ocr_page_id=ocr_page_id,
            raw_text_sha256=ocr.raw_text_sha256,
            text_start=text_start,
            text_end=text_end,
            original_text=original_text,
            corrected_text=corrected_text,
            change_kind=change_kind,
            requires_confirmation=requires_confirmation,
            confirmation_actor=confirmation_actor,
            confirmation_at=confirmation_at,
            reason=reason,
            actor=actor,
            base_processing_revision_id=base_processing_revision_id,
            supersedes_correction_id=supersedes_correction_id,
            affected_scope=affected_scope or [],
            created_at=_utcnow(),
        )
        return CorrectionRepository(session).create(correction)

    def supersede_correction(
        self,
        *,
        supersedes_correction_id: str,
        ocr_page_id: str,
        text_start: int,
        text_end: int,
        original_text: str,
        corrected_text: str,
        change_kind: CorrectionChangeKind,
        reason: str,
        actor: str,
        base_processing_revision_id: str,
        confirmation_actor: str | None = None,
        confirmation_at=None,
        correction_id: str | None = None,
        affected_scope: list[str] | None = None,
    ) -> CorrectionRecord:
        """明确替代当前链头（必须同页同 raw 哈希同原始范围；仓储拒绝分支/跳链）。"""
        return self.create_correction(
            ocr_page_id=ocr_page_id,
            text_start=text_start,
            text_end=text_end,
            original_text=original_text,
            corrected_text=corrected_text,
            change_kind=change_kind,
            reason=reason,
            actor=actor,
            base_processing_revision_id=base_processing_revision_id,
            supersedes_correction_id=supersedes_correction_id,
            confirmation_actor=confirmation_actor,
            confirmation_at=confirmation_at,
            correction_id=correction_id,
            affected_scope=affected_scope,
        )

    def effective_text_for_revision(
        self, processing_revision_id: str
    ) -> dict[str, EffectiveTextProjection]:
        """投影完整修订每页的有效文本（key=ocr_page_id）。每次从不可变 raw OCR +
        该修订所选校对重算，不缓存/不链式沿用。"""
        with self.session_factory() as session, session.begin():
            return self._project_revision(session, processing_revision_id)

    def effective_text_for_page(
        self, processing_revision_id: str, ocr_page_id: str
    ) -> EffectiveTextProjection | None:
        with self.session_factory() as session, session.begin():
            projections = self._project_revision(session, processing_revision_id)
            return projections.get(ocr_page_id)

    def _project_revision(
        self, session: Session, processing_revision_id: str
    ) -> dict[str, EffectiveTextProjection]:
        revision = CompleteEvidenceProcessingRevisionRepository(
            session, self.artifact_store
        ).get(processing_revision_id)
        correction_repo = CorrectionRepository(session)
        corrections = [
            correction_repo.get(cid) for cid in revision.correction_ids
        ]
        projections: dict[str, EffectiveTextProjection] = {}
        ocr_pages = {entry.ocr_page_id for entry in revision.manifest if entry.ocr_page_id}
        for ocr_page_id in ocr_pages:
            ocr = OcrPageRepository(session).get(ocr_page_id)
            page_corrections = [
                c for c in corrections if c.ocr_page_id == ocr_page_id
            ]
            projections[ocr_page_id] = project_effective_text(
                ocr.raw_text, page_corrections
            )
        return projections
