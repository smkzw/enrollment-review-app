"""选择性视觉观察后处理服务：显式入口，只消费已落盘页产物与 OCR 质量。

边界：
- 不接入 ``EvidenceProcessingExecutor`` OCR 核心步骤；必须由调用方显式触发；
- 原生文字充分时跳过模型，不写成功观察；
- 远端/保真/缺图失败关闭：可追加 ``closed`` 审计，绝不写成功观察、不改 OCR；
- 不保存密钥、图像 data URL、绝对主机路径或完整请求载荷；
- 远端 VLM 调用不得占用数据库事务；读写各自使用短事务。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.config import INDEPENDENT_VLM_MODEL
from app.domain.contracts.selective_vision_observation import (
    SELECTIVE_VISION_PROMPT_VERSION,
    SelectiveVisionObservationRecord,
    SelectiveVisionObservationStatus,
    build_observation_identity_sha256,
    build_prompt_sha256,
    build_risk_reasons_sha256,
    sanitize_observation_usage,
)
from app.evidence.selective_vision_review import (
    PageVisionEligibility,
    PageVisionTriageSignals,
    SelectiveVisionClosedError,
    SelectiveVisionObservation,
    SelectiveVisionPlan,
    SelectiveVisionReviewOutcome,
    build_selective_vision_prompts,
    plan_selective_vision_reviews,
    run_selective_vision_review,
)
from app.storage.ocr_models import OCRPageRecord, PageArtifactRecord
from app.storage.ocr_repositories import OcrPageRepository
from app.storage.selective_vision_observation_repository import (
    SelectiveVisionObservationRepository,
)
from app.services.selective_vision_runtime import selective_vision_observation_plan_identity

if TYPE_CHECKING:
    from app.llm.independent_vlm import PageVisionInput

__all__ = [
    "SelectiveVisionObservationBatchResult",
    "SelectiveVisionObservationPageMaterial",
    "SelectiveVisionObservationService",
    "SelectiveVisionObservationServiceError",
    "SelectiveVisionOcrSideEffectError",
    "SelectiveVisionPageSkip",
]

logger = logging.getLogger(__name__)

ReviewRunner = Callable[..., Awaitable[SelectiveVisionReviewOutcome]]

_ROUTE_WIDE_FAILURE_KINDS = frozenset({
    "auth", "balance_insufficient", "config_error", "independent_vlm_error",
    "quota", "remote_error",
})


class SelectiveVisionObservationServiceError(RuntimeError):
    """观察后处理服务错误基类。"""


class SelectiveVisionOcrSideEffectError(SelectiveVisionObservationServiceError):
    """后处理前后 OCR 原文/哈希漂移，模块边界被破坏。"""


@dataclass(frozen=True)
class SelectiveVisionObservationPageMaterial:
    """已落盘页身份 + 结构/质量信号 + 可选图像载荷（不入库存图）。"""

    page_artifact_id: str
    source_ref: str
    page_ordinal: int
    page_image_sha256: str
    media_kind: str
    extraction_route: str | None = None
    page_artifact_status: str | None = None
    has_page_image: bool = False
    has_native_text: bool = False
    native_text_char_count: int = 0
    has_ocr_text: bool = False
    ocr_text_char_count: int = 0
    non_text_mark_count: int | None = None
    complex_layout_not_represented_by_native_text: bool = False
    native_extraction_anomaly: bool = False
    ocr_confidence: float | None = None
    ocr_risk_kinds: tuple[str, ...] = ()
    ocr_page_id: str | None = None
    image_bytes: bytes | None = None
    image_path: str | Path | None = None
    media_type: str = "image/png"

    def __post_init__(self) -> None:
        if not str(self.page_artifact_id).strip():
            raise ValueError("page_artifact_id must be non-empty")
        if not str(self.source_ref).strip():
            raise ValueError("source_ref must be non-empty")
        if int(self.page_ordinal) < 1:
            raise ValueError("page_ordinal must be >= 1")
        digest = str(self.page_image_sha256).strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("page_image_sha256 must be 64-char hex")
        object.__setattr__(self, "page_image_sha256", digest)


@dataclass(frozen=True)
class SelectiveVisionPageSkip:
    source_ref: str
    page_ordinal: int
    skip_reason: str
    page_artifact_id: str


@dataclass(frozen=True)
class SelectiveVisionObservationBatchResult:
    plan: SelectiveVisionPlan
    observations: tuple[SelectiveVisionObservationRecord, ...] = ()
    closed: tuple[SelectiveVisionObservationRecord, ...] = ()
    skipped: tuple[SelectiveVisionPageSkip, ...] = ()
    closed_error: SelectiveVisionClosedError | None = None
    created_observation_ids: tuple[str, ...] = ()
    reused_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PreparedSelectiveVisionBatch:
    """短读事务产物：规划与输入已冻结，远端调用必须在事务外进行。"""

    materials: tuple[SelectiveVisionObservationPageMaterial, ...]
    plan: SelectiveVisionPlan
    skipped: tuple[SelectiveVisionPageSkip, ...]
    ocr_snapshots: dict[str, tuple[str, str]]
    eligible_materials: tuple[SelectiveVisionObservationPageMaterial, ...]
    eligible_items: tuple[PageVisionEligibility, ...]
    vision_inputs: tuple[Any, ...]
    early_result: SelectiveVisionObservationBatchResult | None = None
    pending_missing_pages: tuple[tuple[SelectiveVisionObservationPageMaterial, tuple[str, ...]], ...] = ()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _resolve_image_bytes(page: SelectiveVisionObservationPageMaterial) -> bytes | None:
    if page.image_bytes is not None:
        return bytes(page.image_bytes)
    if page.image_path is None:
        return None
    path = Path(page.image_path)
    if not path.is_file():
        return None
    return path.read_bytes()


def _assert_image_hash(page: SelectiveVisionObservationPageMaterial, payload: bytes) -> None:
    digest = sha256(payload).hexdigest()
    if digest != page.page_image_sha256:
        raise SelectiveVisionObservationServiceError(
            f"页 {page.page_artifact_id} 图像字节哈希 {digest} 与声明的 "
            f"page_image_sha256 {page.page_image_sha256} 不一致"
        )


def _snapshot_ocr(session: Session, ocr_page_id: str | None) -> tuple[str, str] | None:
    if not ocr_page_id:
        return None
    ocr = OcrPageRepository(session).get(ocr_page_id)
    return ocr.raw_text, ocr.raw_text_sha256


def _assert_ocr_unchanged(
    session: Session,
    ocr_page_id: str | None,
    before: tuple[str, str] | None,
) -> None:
    if ocr_page_id is None or before is None:
        return
    after = _snapshot_ocr(session, ocr_page_id)
    if after is None:
        raise SelectiveVisionOcrSideEffectError(
            f"选择性视觉后处理期间 OCRPage {ocr_page_id} 无法重读"
        )
    after_text, after_sha = after
    if after_text != before[0] or after_sha != before[1]:
        raise SelectiveVisionOcrSideEffectError(
            f"选择性视觉后处理期间 OCRPage {ocr_page_id} 原文/哈希发生变化，拒绝继续"
        )


class SelectiveVisionObservationService:
    """显式证据后处理：规划 →（可选）调用 → 追加观察侧车。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        review_runner: ReviewRunner | None = None,
        default_model_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.review_runner = review_runner or run_selective_vision_review
        self.default_model_id = (
            default_model_id or os.getenv("INDEPENDENT_VLM_MODEL", INDEPENDENT_VLM_MODEL)
        ).strip()

    async def run_postprocess(
        self,
        pages: Sequence[SelectiveVisionObservationPageMaterial],
        *,
        persist_closed_failures: bool = True,
        enabled: bool | None = None,
    ) -> SelectiveVisionObservationBatchResult:
        """规划与持久化使用短事务；远端 VLM 调用在事务外执行。"""
        with self.session_factory() as session, session.begin():
            prepared = self.prepare_postprocess_in_session(
                session,
                pages,
                persist_closed_failures=persist_closed_failures,
                enabled=enabled,
            )
            if prepared.early_result is not None:
                return prepared.early_result

        if prepared.pending_missing_pages and not prepared.eligible_materials:
            with self.session_factory() as session, session.begin():
                return self._persist_missing_page_closed(
                    session,
                    prepared,
                    persist_closed_failures=persist_closed_failures,
                )

        observations: list[SelectiveVisionObservationRecord] = []
        closed: list[SelectiveVisionObservationRecord] = []
        created_ids: list[str] = []
        reused_ids: list[str] = []
        first_closed_error: SelectiveVisionClosedError | None = None
        size = prepared.plan.max_pages_per_call
        for start in range(0, len(prepared.eligible_items), size):
            stop = start + size
            with self.session_factory() as session:
                reused = [
                    self._existing_success(session, page, item.reason_values, prepared.plan)
                    for page, item in zip(
                        prepared.eligible_materials[start:stop],
                        prepared.eligible_items[start:stop],
                        strict=True,
                    )
                ]
            observations.extend(row for row in reused if row is not None)
            reused_ids.extend(row.observation_id for row in reused if row is not None)
            pending_indexes = [index for index, row in enumerate(reused) if row is None]
            if not pending_indexes:
                continue
            chunk_plan = replace(
                prepared.plan,
                eligible=tuple(prepared.eligible_items[start + index] for index in pending_indexes),
                skipped=(),
            )
            chunk_materials = tuple(prepared.eligible_materials[start + index] for index in pending_indexes)
            chunk = replace(
                prepared,
                materials=chunk_materials,
                plan=chunk_plan,
                skipped=(),
                ocr_snapshots={
                    page.ocr_page_id: prepared.ocr_snapshots[page.ocr_page_id]
                    for page in chunk_materials
                    if page.ocr_page_id in prepared.ocr_snapshots
                },
                eligible_materials=chunk_materials,
                eligible_items=tuple(prepared.eligible_items[start + index] for index in pending_indexes),
                vision_inputs=tuple(prepared.vision_inputs[start + index] for index in pending_indexes),
            )
            outcome = await self.review_runner(chunk_plan, list(chunk.vision_inputs))
            with self.session_factory() as session, session.begin():
                saved = self.persist_postprocess_in_session(
                    session,
                    chunk,
                    outcome,
                    persist_closed_failures=persist_closed_failures,
                )
            observations.extend(saved.observations)
            closed.extend(saved.closed)
            created_ids.extend(saved.created_observation_ids)
            reused_ids.extend(saved.reused_observation_ids)
            if saved.closed_error is not None and (
                first_closed_error is None
                or (
                    saved.closed_error.failure_kind in _ROUTE_WIDE_FAILURE_KINDS
                    and first_closed_error.failure_kind not in _ROUTE_WIDE_FAILURE_KINDS
                )
            ):
                first_closed_error = saved.closed_error
            if (
                saved.closed_error is not None
                and saved.closed_error.failure_kind in _ROUTE_WIDE_FAILURE_KINDS
            ):
                break
        if prepared.pending_missing_pages:
            with self.session_factory() as session, session.begin():
                missing_result = self._persist_missing_page_closed(
                    session, prepared, persist_closed_failures=persist_closed_failures,
                )
            closed.extend(missing_result.closed)
            if first_closed_error is None:
                first_closed_error = missing_result.closed_error
        return SelectiveVisionObservationBatchResult(
            plan=prepared.plan,
            observations=tuple(observations),
            closed=tuple(closed),
            skipped=prepared.skipped,
            closed_error=first_closed_error,
            created_observation_ids=tuple(created_ids),
            reused_observation_ids=tuple(reused_ids),
        )

    def _existing_success(
        self,
        session: Session,
        page: SelectiveVisionObservationPageMaterial,
        reasons: Sequence[str],
        plan: SelectiveVisionPlan,
    ) -> SelectiveVisionObservationRecord | None:
        expected = self._base_record_kwargs(
            session, page=page, plan=plan, reasons=reasons,
            model_id=self.default_model_id,
        )
        for row in SelectiveVisionObservationRepository(session).list_by_page_artifact(
            page.page_artifact_id
        ):
            if (
                row.status == SelectiveVisionObservationStatus.SUCCEEDED
                and row.source_ref == page.source_ref
                and row.page_ordinal == page.page_ordinal
                and row.page_image_sha256 == page.page_image_sha256
                and row.ocr_page_id == page.ocr_page_id
                and row.ocr_raw_text_sha256 == expected["ocr_raw_text_sha256"]
                and row.model_id == self.default_model_id
                and row.plan_version == expected["plan_version"]
                and row.prompt_sha256 == expected["prompt_sha256"]
                and row.risk_reasons_sha256 == expected["risk_reasons_sha256"]
            ):
                return row
        return None

    async def run_postprocess_in_session(
        self,
        session: Session,
        pages: Sequence[SelectiveVisionObservationPageMaterial],
        *,
        persist_closed_failures: bool = True,
        enabled: bool | None = None,
    ) -> SelectiveVisionObservationBatchResult:
        """兼容入口：不得在已开启的长事务中跨 await 调用。

        若需要远端调用，请使用 ``run_postprocess``（短事务拆分）。本方法在
        同一 session 上准备后立即返回可同步完成的结果；若仍需远端 VLM，则
        抛出错误，避免隐式占用调用方事务。
        """
        prepared = self.prepare_postprocess_in_session(
            session,
            pages,
            persist_closed_failures=persist_closed_failures,
            enabled=enabled,
        )
        if prepared.early_result is not None:
            return prepared.early_result
        if prepared.pending_missing_pages and not prepared.eligible_materials:
            return self._persist_missing_page_closed(
                session,
                prepared,
                persist_closed_failures=persist_closed_failures,
            )
        raise SelectiveVisionObservationServiceError(
            "run_postprocess_in_session 不能在持有数据库会话时发起远端 VLM 调用；"
            "请改用 run_postprocess（事务外调用）。"
        )

    def prepare_postprocess_in_session(
        self,
        session: Session,
        pages: Sequence[SelectiveVisionObservationPageMaterial],
        *,
        persist_closed_failures: bool = True,
        enabled: bool | None = None,
    ) -> _PreparedSelectiveVisionBatch:
        """短读：校验页产物、规划资格、解析图像输入；不调用远端 VLM。"""
        del persist_closed_failures  # 准备阶段不落库；缺图关闭在独立短写事务。
        materials = tuple(pages)
        if not materials:
            empty_plan = plan_selective_vision_reviews((), enabled=enabled)
            return _PreparedSelectiveVisionBatch(
                materials=(),
                plan=empty_plan,
                skipped=(),
                ocr_snapshots={},
                eligible_materials=(),
                eligible_items=(),
                vision_inputs=(),
                early_result=SelectiveVisionObservationBatchResult(plan=empty_plan),
            )

        ocr_snapshots: dict[str, tuple[str, str]] = {}
        for page in materials:
            self._verify_materialized_page(session, page)
            snap = _snapshot_ocr(session, page.ocr_page_id)
            if page.ocr_page_id and snap is not None:
                ocr_snapshots[page.ocr_page_id] = snap

        signals = tuple(self._to_signals(page) for page in materials)
        plan = plan_selective_vision_reviews(signals, enabled=enabled)

        skipped = tuple(
            SelectiveVisionPageSkip(
                source_ref=item.source_ref,
                page_ordinal=item.page_ordinal,
                skip_reason=str(item.skip_reason or "skipped"),
                page_artifact_id=self._page_artifact_id(
                    materials, item.source_ref, item.page_ordinal
                ),
            )
            for item in plan.skipped
        )

        if not plan.eligible:
            for page in materials:
                _assert_ocr_unchanged(
                    session,
                    page.ocr_page_id,
                    ocr_snapshots.get(page.ocr_page_id or ""),
                )
            return _PreparedSelectiveVisionBatch(
                materials=materials,
                plan=plan,
                skipped=skipped,
                ocr_snapshots=ocr_snapshots,
                eligible_materials=(),
                eligible_items=(),
                vision_inputs=(),
                early_result=SelectiveVisionObservationBatchResult(
                    plan=plan, skipped=skipped
                ),
            )

        by_key = {
            (str(page.source_ref).strip(), int(page.page_ordinal)): page
            for page in materials
        }
        eligible_materials: list[SelectiveVisionObservationPageMaterial] = []
        eligible_items: list[PageVisionEligibility] = []
        vision_inputs: list[Any] = []
        missing_pages: list[tuple[SelectiveVisionObservationPageMaterial, tuple[str, ...]]] = []
        # 延迟加载 PageVisionInput，避免证据模块冷启动拉起 VLM 传输依赖。
        from app.llm.independent_vlm import PageVisionInput as RuntimePageVisionInput

        for item in plan.eligible:
            page = by_key[(item.source_ref, item.page_ordinal)]
            payload = _resolve_image_bytes(page)
            if payload is None:
                missing_pages.append((page, tuple(item.reason_values)))
                continue
            _assert_image_hash(page, payload)
            eligible_materials.append(page)
            eligible_items.append(item)
            vision_inputs.append(
                RuntimePageVisionInput(
                    source_ref=page.source_ref,
                    page_ordinal=page.page_ordinal,
                    media_type=page.media_type,
                    image_bytes=payload,
                )
            )

        return _PreparedSelectiveVisionBatch(
            materials=materials,
            plan=plan,
            skipped=skipped,
            ocr_snapshots=ocr_snapshots,
            eligible_materials=tuple(eligible_materials),
            eligible_items=tuple(eligible_items),
            vision_inputs=tuple(vision_inputs),
            pending_missing_pages=tuple(missing_pages),
        )

    def persist_postprocess_in_session(
        self,
        session: Session,
        prepared: _PreparedSelectiveVisionBatch,
        outcome: SelectiveVisionReviewOutcome,
        *,
        persist_closed_failures: bool = True,
    ) -> SelectiveVisionObservationBatchResult:
        """短写：追加成功观察或失败关闭，并复核 OCR 未变。"""
        materials = prepared.materials
        plan = prepared.plan
        skipped = prepared.skipped
        ocr_snapshots = prepared.ocr_snapshots
        eligible_materials = prepared.eligible_materials

        if outcome.closed_error is not None:
            closed_rows: list[SelectiveVisionObservationRecord] = []
            for page, item in zip(eligible_materials, plan.eligible, strict=True):
                rows = self._persist_closed_for_page(
                    session,
                    page=page,
                    plan=plan,
                    reasons=item.reason_values,
                    failure_kind=outcome.closed_error.failure_kind,
                    persist=persist_closed_failures,
                )
                closed_rows.extend(rows)
            for material in materials:
                _assert_ocr_unchanged(
                    session,
                    material.ocr_page_id,
                    ocr_snapshots.get(material.ocr_page_id or ""),
                )
            return SelectiveVisionObservationBatchResult(
                plan=plan,
                closed=tuple(closed_rows),
                skipped=skipped,
                closed_error=outcome.closed_error,
            )

        created_ids: list[str] = []
        reused_ids: list[str] = []
        persisted: list[SelectiveVisionObservationRecord] = []
        for observation in outcome.observations:
            for page in eligible_materials:
                if page.source_ref not in observation.source_refs:
                    continue
                if page.page_ordinal not in observation.page_ordinals:
                    continue
                record, created = self._persist_succeeded(
                    session,
                    page=page,
                    plan=plan,
                    observation=observation,
                )
                persisted.append(record)
                if created:
                    created_ids.append(record.observation_id)
                else:
                    reused_ids.append(record.observation_id)

        for material in materials:
            _assert_ocr_unchanged(
                session,
                material.ocr_page_id,
                ocr_snapshots.get(material.ocr_page_id or ""),
            )

        return SelectiveVisionObservationBatchResult(
            plan=plan,
            observations=tuple(persisted),
            skipped=skipped,
            created_observation_ids=tuple(created_ids),
            reused_observation_ids=tuple(reused_ids),
        )

    def _persist_missing_page_closed(
        self,
        session: Session,
        prepared: _PreparedSelectiveVisionBatch,
        *,
        persist_closed_failures: bool,
    ) -> SelectiveVisionObservationBatchResult:
        if not prepared.pending_missing_pages:
            raise SelectiveVisionObservationServiceError("缺图关闭缺少页面上下文")
        closed = tuple(
            row
            for page, reasons in prepared.pending_missing_pages
            for row in self._persist_closed_for_page(
                session, page=page, plan=prepared.plan, reasons=reasons,
                failure_kind="missing_page_inputs", persist=persist_closed_failures,
            )
        )
        for material in prepared.materials:
            _assert_ocr_unchanged(
                session,
                material.ocr_page_id,
                prepared.ocr_snapshots.get(material.ocr_page_id or ""),
            )
        return SelectiveVisionObservationBatchResult(
            plan=prepared.plan,
            closed=closed,
            skipped=prepared.skipped,
            closed_error=SelectiveVisionClosedError(
                "选择性视觉核验已关闭：计划中的页面图片未完整提供。",
                failure_kind="missing_page_inputs",
                disabled=True,
            ),
        )

    def _page_artifact_id(
        self,
        materials: Sequence[SelectiveVisionObservationPageMaterial],
        source_ref: str,
        page_ordinal: int,
    ) -> str:
        for page in materials:
            if page.source_ref == source_ref and page.page_ordinal == page_ordinal:
                return page.page_artifact_id
        return ""

    def _to_signals(
        self, page: SelectiveVisionObservationPageMaterial
    ) -> PageVisionTriageSignals:
        return PageVisionTriageSignals(
            source_ref=page.source_ref,
            page_ordinal=page.page_ordinal,
            media_kind=page.media_kind,
            extraction_route=page.extraction_route,
            page_artifact_status=page.page_artifact_status,
            has_page_image=page.has_page_image,
            has_native_text=page.has_native_text,
            native_text_char_count=page.native_text_char_count,
            has_ocr_text=page.has_ocr_text,
            ocr_text_char_count=page.ocr_text_char_count,
            non_text_mark_count=page.non_text_mark_count,
            complex_layout_not_represented_by_native_text=(
                page.complex_layout_not_represented_by_native_text
            ),
            native_extraction_anomaly=page.native_extraction_anomaly,
            ocr_confidence=page.ocr_confidence,
            ocr_risk_kinds=page.ocr_risk_kinds,
        )

    def _verify_materialized_page(
        self, session: Session, page: SelectiveVisionObservationPageMaterial
    ) -> PageArtifactRecord:
        artifact = session.get(PageArtifactRecord, page.page_artifact_id)
        if artifact is None:
            raise SelectiveVisionObservationServiceError(
                f"页产物 {page.page_artifact_id} 不存在，拒绝视觉后处理"
            )
        if int(artifact.page_number) != int(page.page_ordinal):
            raise SelectiveVisionObservationServiceError(
                f"页产物 {page.page_artifact_id} 页码与声明 page_ordinal 不一致"
            )
        artifact_image_sha = artifact.page_image_sha256
        if artifact_image_sha is None:
            if page.has_page_image:
                raise SelectiveVisionObservationServiceError(
                    f"页产物 {page.page_artifact_id} 无页图哈希但材料声明 has_page_image=True"
                )
        elif artifact_image_sha != page.page_image_sha256:
            raise SelectiveVisionObservationServiceError(
                f"页产物 {page.page_artifact_id} 的 page_image_sha256 与声明不一致"
            )
        if page.ocr_page_id:
            ocr = session.get(OCRPageRecord, page.ocr_page_id)
            if ocr is None:
                raise SelectiveVisionObservationServiceError(
                    f"OCR 页 {page.ocr_page_id} 不存在，拒绝视觉后处理"
                )
            if ocr.page_artifact_id != page.page_artifact_id:
                raise SelectiveVisionObservationServiceError(
                    f"OCR 页 {page.ocr_page_id} 不属于页产物 {page.page_artifact_id}"
                )
        return artifact

    def _prompt_bundle(self, *, reasons: Sequence[str]) -> tuple[str, str, str, str]:
        system_prompt, user_prompt = build_selective_vision_prompts(reasons=reasons)
        prompt_version = SELECTIVE_VISION_PROMPT_VERSION
        prompt_digest = build_prompt_sha256(
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return system_prompt, user_prompt, prompt_version, prompt_digest

    def _ocr_raw_text_sha256(
        self, session: Session, page: SelectiveVisionObservationPageMaterial
    ) -> str | None:
        if not page.ocr_page_id:
            return None
        return OcrPageRepository(session).get(page.ocr_page_id).raw_text_sha256

    def _base_record_kwargs(
        self,
        session: Session,
        *,
        page: SelectiveVisionObservationPageMaterial,
        plan: SelectiveVisionPlan,
        reasons: Sequence[str],
        model_id: str,
    ) -> dict[str, Any]:
        artifact = self._verify_materialized_page(session, page)
        _system, _user, prompt_version, prompt_digest = self._prompt_bundle(
            reasons=reasons
        )
        reasons_list = [str(item) for item in reasons]
        reasons_digest = build_risk_reasons_sha256(reasons_list)
        ocr_raw_text_sha256 = self._ocr_raw_text_sha256(session, page)
        observation_plan_identity = selective_vision_observation_plan_identity(
            plan.plan_version,
            model_id=model_id,
            ocr_raw_text_sha256=ocr_raw_text_sha256,
        )
        identity = build_observation_identity_sha256(
            page_artifact_id=page.page_artifact_id,
            page_image_sha256=page.page_image_sha256,
            plan_version=observation_plan_identity,
            model_id=model_id,
            prompt_sha256=prompt_digest,
            risk_reasons_sha256=reasons_digest,
        )
        return {
            "page_artifact_id": page.page_artifact_id,
            "source_document_version_id": artifact.source_document_version_id,
            "source_ref": page.source_ref,
            "page_ordinal": page.page_ordinal,
            "page_image_sha256": page.page_image_sha256,
            "ocr_page_id": page.ocr_page_id,
            "ocr_raw_text_sha256": ocr_raw_text_sha256,
            "plan_version": observation_plan_identity,
            "risk_reasons": reasons_list,
            "risk_reasons_sha256": reasons_digest,
            "model_id": model_id,
            "prompt_version": prompt_version,
            "prompt_sha256": prompt_digest,
            "observation_identity_sha256": identity,
            "created_at": _utcnow(),
        }

    def _persist_succeeded(
        self,
        session: Session,
        *,
        page: SelectiveVisionObservationPageMaterial,
        plan: SelectiveVisionPlan,
        observation: SelectiveVisionObservation,
    ) -> tuple[SelectiveVisionObservationRecord, bool]:
        model_id = str(observation.model or self.default_model_id).strip()
        kwargs = self._base_record_kwargs(
            session,
            page=page,
            plan=plan,
            reasons=observation.reasons,
            model_id=model_id,
        )
        record = SelectiveVisionObservationRecord(
            observation_id=f"svo-{uuid4().hex}",
            status=SelectiveVisionObservationStatus.SUCCEEDED,
            observation_text=observation.text,
            finish_reason=observation.finish_reason,
            usage=sanitize_observation_usage(dict(observation.usage or {})),
            failure_kind=None,
            **kwargs,
        )
        return SelectiveVisionObservationRepository(session).get_or_create_succeeded(
            record
        )

    def _persist_closed_for_page(
        self,
        session: Session,
        *,
        page: SelectiveVisionObservationPageMaterial,
        plan: SelectiveVisionPlan,
        reasons: Sequence[str],
        failure_kind: str,
        persist: bool,
    ) -> tuple[SelectiveVisionObservationRecord, ...]:
        if not persist:
            return ()
        kwargs = self._base_record_kwargs(
            session,
            page=page,
            plan=plan,
            reasons=reasons,
            model_id=self.default_model_id or "independent-vlm",
        )
        record = SelectiveVisionObservationRecord(
            observation_id=f"svo-closed-{uuid4().hex}",
            status=SelectiveVisionObservationStatus.CLOSED,
            observation_text=None,
            finish_reason=None,
            usage={},
            failure_kind=failure_kind,
            **kwargs,
        )
        saved = SelectiveVisionObservationRepository(session).append_closed(record)
        return (saved,)
