"""选择性视觉观察后处理服务：显式入口，只消费已落盘页产物与 OCR 质量。

边界：
- 不接入 ``EvidenceProcessingExecutor`` OCR 核心步骤；必须由调用方显式触发；
- 原生文字充分时跳过模型，不写成功观察；
- 远端/保真/缺图失败关闭：可追加 ``closed`` 审计，绝不写成功观察、不改 OCR；
- 不保存密钥、图像 data URL、绝对主机路径或远端请求封套；局部提示文本单独保存；
- 远端 VLM 调用不得占用数据库事务；读写各自使用短事务。
"""

from __future__ import annotations

import logging
import os
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.config import INDEPENDENT_VLM_MODEL
from app.domain.contracts.reading_view import ReadingViewBinding
from app.domain.contracts.local_region_read import LocalReadFormat, local_region_read_model, parse_local_region_read
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
from app.domain.contracts.evidence import BoundingBox
from app.evidence.artifacts import ArtifactStore, StoredArtifact
from app.evidence.reading_view import make_reading_region, make_reading_view
from app.storage.ocr_models import OCRPageRecord, PageArtifactRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, OcrPageRepository
from app.domain.publication import canonical_hash
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
    reading_view: ReadingViewBinding | None = None

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
        if self.reading_view is not None and (
            self.reading_view.source_page_artifact_id != self.page_artifact_id
            or self.reading_view.source_image_sha256 != digest
        ):
            raise ValueError("阅读方向必须绑定当前原始页图")


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


def local_visual_prompts(region_ref: str, read_format: LocalReadFormat = "transcript") -> tuple[str, str]:
    if read_format in {"structured_candidate", "localized_candidate"}:
        schema = json.dumps(local_region_read_model(read_format).model_json_schema(), ensure_ascii=False)
        location_instruction = (
            "proposed_bbox只是待检查的位置提案，以本次局部图片左上为原点，横纵各按0至1000表示。"
            "框应同时包含这一项目的名称、值及本行可见的单位和参考范围，不能包含邻行。"
            "无法单独圈出、同一框内混有多个项目或对应对象不清时填null并说明疑问。"
            "坐标不是已核实依据，不能为了凑齐结构猜位置。"
            if read_format == "localized_candidate" else ""
        )
        return (
            "你只逐项记录所附局部原图中可见内容，不批准事实、不推断临床含义。",
            "图片只是原始页面中明确选定的局部区域。第一行原样输出 source_ref=" + region_ref
            + "\n其后只输出符合以下结构的JSON，不加解释：" + schema
            + "\n每个可见项目独立记录。label为原图项目名，raw_value为原始值或字迹，"
            "raw_unit为该项目单位，reference_text为对应参考范围；原图未见则填null，不能借邻行内容。"
            "只有该项目本身是日期或时刻时，time_label才抄该项日期标题；"
            "普通测量项填null，其他可见时点关系另以原文写unresolved，不把采样、接收、报告日期互换。"
            "excerpt逐字保留对应文字，position只描述该项在本区域的位置，不编造像素坐标。"
            "script区分印刷、手写或混合，legibility区分清楚、裁切不完整或无法辨认。"
            "读不清时保留疑似读法并标unclear，不能补全字符。annotation_target仅在明确连线或"
            "原图直接说明时摘录批注对象，否则null。可见不清的手写字不得写成没有研究者判断。"
            "截取范围外的内容、书写者及医学含义不得推断；疑问写unresolved，不能编造新项目。"
            + location_instruction,
        )
    if read_format != "transcript":
        raise ValueError("局部读取格式不受支持")
    return (
        "你只核对所附原件局部的可见笔迹和文字，不采信事实、不批准临床结论。",
        "本次图片只是原始页面中明确选定的局部区域，不是整页。"
        "仅逐字摘录区域内确实可见的印刷文字、手写字、缩写及符号，分别说明位置。"
        "不要展开缩写、补全不清笔画或推断医学含义。"
        "无法辨认的字符逐项标明，保留可能的读法和不确定位置。"
        "如批注所指对象不在区域内或没有明确连线，只说明无法确定对象。"
        "可见但读不清的批注不得被描述为没有批注或没有研究者判断。"
        "不要推断书写者、日期、整页或其他页面是否存在判断，不作入排结论。"
        "第一行原样输出 source_ref=" + region_ref,
    )


def local_visual_prompt_identity(read_format: LocalReadFormat = "transcript") -> str:
    return canonical_hash(local_visual_prompts("{region_source_ref}", read_format))


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

    async def verify_local_region(
        self, page: SelectiveVisionObservationPageMaterial, *,
        base_processing_revision_id: str, view_bbox: BoundingBox,
        clockwise_degrees: int, artifact_store: ArtifactStore,
        max_tokens: int | None = None, reasoning_effort: str | None = None,
        read_format: LocalReadFormat = "transcript",
    ) -> StoredArtifact:
        """Read an explicitly selected region without qualifying a page or fact.

        The receipt is an isolated verification proposal, not an OCRRiskReview
        or SelectiveVisionObservationRecord. Full-page coverage is unchanged.
        """
        from app.llm import independent_vlm as vlm

        with self.session_factory() as session:
            base = EvidenceProcessingRevisionRepository(session).get(base_processing_revision_id)
            if not any(entry.page_artifact_id == page.page_artifact_id
                       and entry.ocr_page_id == page.ocr_page_id for entry in base.manifest):
                raise SelectiveVisionObservationServiceError("局部核实超出指定资料版本")
            artifact = self._verify_materialized_page(session, page)
            document_id = artifact.source_document_version_id
            before = _snapshot_ocr(session, page.ocr_page_id)
        image = _resolve_image_bytes(page)
        if image is None:
            raise SelectiveVisionObservationServiceError("局部核实缺少原始页图")
        _assert_image_hash(page, image)
        view = make_reading_view(
            image, source_page_artifact_id=page.page_artifact_id,
            source_image_sha256=page.page_image_sha256,
            clockwise_degrees=clockwise_degrees,
        )
        region = make_reading_region(view, view_bbox)
        binding = region.identity()
        region_ref = "region:" + canonical_hash(binding)
        system, prompt = local_visual_prompts(region_ref, read_format)
        request_options = vlm.independent_vlm_completion_kwargs(
            messages=[], model=self.default_model_id, max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
        image_artifact = artifact_store.put("reading_view_image", region.image_bytes)
        payload = {
            "schema_version": "local-visual-verification/v1",
            "coverage_scope": "region_only", "candidate_only": True,
            "base_processing_revision_id": base_processing_revision_id,
            "page_artifact_id": page.page_artifact_id,
            "source_document_version_id": document_id,
            "page_ordinal": page.page_ordinal,
            "ocr_page_id": page.ocr_page_id,
            "ocr_raw_text_sha256": before[1] if before is not None else None,
            "region_source_ref": region_ref, "region": binding,
            "image_artifact_ref": image_artifact.storage_ref,
            "prompt": prompt, "system_prompt": system,
            "prompt_sha256": local_visual_prompt_identity(read_format),
            "read_format": read_format,
            "requested_model": request_options["model"],
            "requested_max_tokens": request_options["max_tokens"],
            "requested_effort": request_options["reasoning_effort"],
            "created_at": _utcnow().isoformat(),
        }
        try:
            result = await vlm.independent_vlm_page_chat(
                prompt, [vlm.PageVisionInput(
                    source_ref=region_ref, page_ordinal=page.page_ordinal,
                    image_bytes=region.image_bytes,
                )], system_prompt=system, model=self.default_model_id,
                max_tokens=max_tokens, reasoning_effort=reasoning_effort,
            )
            payload.update({
                "status": "read" if result.finish_reason == "stop" and any(
                    line.strip() and not line.strip().startswith("source_ref=")
                    for line in result.text.splitlines()
                ) else "failed",
                "model": result.model, "finish_reason": result.finish_reason,
                "usage": sanitize_observation_usage(dict(result.usage)),
                "observation_text": result.text,
            })
            if read_format in {"structured_candidate", "localized_candidate"} and payload["status"] == "read":
                try:
                    candidate = parse_local_region_read(result.text, source_ref=region_ref, read_format=read_format)
                    payload["structured_read"] = candidate.model_dump(mode="json")
                except (ValueError, TypeError):
                    payload.update({"status": "failed", "failure_kind": "local_structure_invalid"})
        except vlm.IndependentVlmError as exc:
            rejected = getattr(exc, "rejected_response", None)
            payload.update({
                "status": "failed", "failure_kind": getattr(exc, "failure_kind", "source_fidelity"),
                "observation_text": rejected.text if rejected is not None else None,
                "model": rejected.model if rejected is not None else None,
                "finish_reason": rejected.finish_reason if rejected is not None else None,
                "usage": sanitize_observation_usage(dict(rejected.usage)) if rejected is not None else {},
            })
        with self.session_factory() as session:
            _assert_ocr_unchanged(session, page.ocr_page_id, before)
        return artifact_store.put("evaluation_manifest", json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8"))

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
                and row.reading_view == page.reading_view
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
            if page.reading_view is not None:
                from app.evidence.reading_view import make_reading_view
                view = make_reading_view(
                    payload,
                    source_page_artifact_id=page.page_artifact_id,
                    source_image_sha256=page.page_image_sha256,
                    clockwise_degrees=page.reading_view.clockwise_degrees,
                )
                if view.identity() != page.reading_view.model_dump(mode="json"):
                    raise SelectiveVisionObservationServiceError("阅读视图与冻结来源不一致")
                payload = view.image_bytes
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
            reading_view=page.reading_view,
        )
        return {
            "page_artifact_id": page.page_artifact_id,
            "source_document_version_id": artifact.source_document_version_id,
            "source_ref": page.source_ref,
            "page_ordinal": page.page_ordinal,
            "page_image_sha256": page.page_image_sha256,
            "reading_view": page.reading_view,
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
