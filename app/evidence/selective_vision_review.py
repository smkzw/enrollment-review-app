"""通用、按页面风险选择的独立视觉核验规划与调用适配。

本模块位于证据处理共享边界：在已有页产物 / OCR 质量元数据之上，决定哪些页面
值得调用独立 GLM-5.3-Flash 视觉模型做**观察性核验**，并适配一次失败关闭的调用。

产品合同（内容中立）：
- 原生 DOCX/PDF 文本仍是主路径；不得只因 VLM 可用就整份逐页重发；
- 仅当结构/质量元数据给出页级风险理由时才进入视觉核验：
  扫描/纯图页、复杂表格/版面无法被原生文本代表、原生提取结构异常、
  OCR/证据低置信或低质量风险；
- 判定不读取研究号、疾病、药物、评分、访视、条款号或任何项目特异关键词；
- 视觉响应是带稳定来源身份的证据观察，不是入排结论，也不得覆盖原 OCR；
- 提供方失败显式关闭；不得静默回退到 OCR 或语义路由。

本模块不修改 OCR 执行器语义，不恢复已暂停的回放工件，不接入临床判定。
"""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from app.config import (
    SELECTIVE_VISION_ENABLED,
    SELECTIVE_VISION_MAX_PAGES_PER_CALL,
    SELECTIVE_VISION_OCR_CONFIDENCE_THRESHOLD,
)
from app.domain.contracts.enums import (
    ExtractionRoute,
    OcrRiskKind,
    PageArtifactStatus,
)
if TYPE_CHECKING:
    from app.llm.independent_vlm import IndependentVlmChatResult, PageVisionInput

logger = logging.getLogger(__name__)

SELECTIVE_VISION_PLAN_VERSION = "selective_vision_review/v1"
NATIVE_TEXT_SUFFICIENT_CHARS = 8

VisionRiskReason = Literal[
    "scan_or_image_only",
    "complex_visual_or_table_layout",
    "native_extraction_anomaly",
    "ocr_evidence_risk",
]

VISION_REASON_SCAN_OR_IMAGE_ONLY: VisionRiskReason = "scan_or_image_only"
VISION_REASON_COMPLEX_VISUAL_OR_TABLE: VisionRiskReason = (
    "complex_visual_or_table_layout"
)
VISION_REASON_NATIVE_EXTRACTION_ANOMALY: VisionRiskReason = (
    "native_extraction_anomaly"
)
VISION_REASON_OCR_EVIDENCE_RISK: VisionRiskReason = "ocr_evidence_risk"

ALLOWED_VISION_RISK_REASONS: frozenset[str] = frozenset(
    {
        VISION_REASON_SCAN_OR_IMAGE_ONLY,
        VISION_REASON_COMPLEX_VISUAL_OR_TABLE,
        VISION_REASON_NATIVE_EXTRACTION_ANOMALY,
        VISION_REASON_OCR_EVIDENCE_RISK,
    }
)

SKIP_SELECTIVE_VISION_DISABLED = "selective_vision_disabled"
SKIP_NATIVE_TEXT_PRIMARY = "native_text_primary"
SKIP_BLANK_OR_NO_CONTENT = "blank_or_no_content"
SKIP_FAILED_PAGE = "failed_page"
SKIP_MISSING_PAGE_IMAGE = "missing_page_image"
SKIP_NO_RISK_REASON = "no_page_risk_reason"

_NATIVE_TEXT_ROUTES = frozenset(
    {
        ExtractionRoute.SOURCE_TEXT.value,
        ExtractionRoute.NATIVE_PDF_TEXT.value,
        ExtractionRoute.RENDERED_PDF_TEXT.value,
    }
)
_IMAGE_MEDIA_KINDS = frozenset({"image", "tiff"})

_DEFAULT_REVIEW_SYSTEM_PROMPT = (
    "你负责核对临床试验入排资料的原始页面。只描述页面中确实可见的内容；"
    "必须原样保留 PAGE_ANCHOR 中的 source_ref 和 page_ordinal，不得编造来源。"
    "每页回答的第一行必须使用纯文本格式 source_ref=<原值>，不要为这一行添加 Markdown 标记。"
    "不得判断受试者是否符合入排标准，不得把观察结果写成入组结论，也不得覆盖或替换原始识别文字。"
)

_DEFAULT_REVIEW_USER_PROMPT = (
    "请核对所附原始页面。逐页引用 PAGE_ANCHOR 中的 source_ref，说明版面、表格、"
    "文字可辨识性及需要人工确认之处；每页先单独输出一行 source_ref=<原值>；"
    "不要推断任何项目特异的医学结论。"
)


class SelectiveVisionReviewError(RuntimeError):
    """选择性视觉核验领域错误基类（失败关闭，不回退其他路由）。"""


class SelectiveVisionConfigError(SelectiveVisionReviewError):
    """配置缺失或路线未启用。"""


class SelectiveVisionClosedError(SelectiveVisionReviewError):
    """远程/保真失败后显式关闭；调用方不得改走 OCR/语义路由。"""

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str,
        disabled: bool = True,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.disabled = disabled
        self.cause = cause


async def check_independent_vlm() -> bool:
    """延迟加载独立 VLM，避免确定性证据/方案模块冷启动模型传输。"""
    from app.llm import independent_vlm as vlm

    return await vlm.check_independent_vlm()


async def independent_vlm_page_chat(*args: Any, **kwargs: Any) -> Any:
    """保留可注入的页级调用边界，同时把模型依赖推迟到真正执行时。"""
    from app.llm import independent_vlm as vlm

    return await vlm.independent_vlm_page_chat(*args, **kwargs)


@dataclass(frozen=True)
class PageVisionTriageSignals:
    """页级结构/质量信号；不含临床正文，供内容中立判定。"""

    source_ref: str
    page_ordinal: int
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

    def __post_init__(self) -> None:
        if not str(self.source_ref).strip():
            raise ValueError("PageVisionTriageSignals.source_ref must be non-empty")
        if int(self.page_ordinal) < 1:
            raise ValueError("PageVisionTriageSignals.page_ordinal must be >= 1")
        if self.native_text_char_count < 0:
            raise ValueError("native_text_char_count must be >= 0")
        if self.ocr_text_char_count < 0:
            raise ValueError("ocr_text_char_count must be >= 0")
        if self.ocr_confidence is not None and not (
            0.0 <= float(self.ocr_confidence) <= 1.0
        ):
            raise ValueError("ocr_confidence must be in [0, 1] when provided")


@dataclass(frozen=True)
class PageVisionEligibility:
    """单页视觉核验资格判定结果。"""

    source_ref: str
    page_ordinal: int
    eligible: bool
    reasons: tuple[VisionRiskReason, ...] = ()
    skip_reason: str | None = None

    @property
    def reason_values(self) -> tuple[str, ...]:
        return tuple(str(reason) for reason in self.reasons)


@dataclass(frozen=True)
class SelectiveVisionPlan:
    """一批页面的选择性视觉核验计划（确定性、可测）。"""

    plan_version: str
    enabled: bool
    eligible: tuple[PageVisionEligibility, ...]
    skipped: tuple[PageVisionEligibility, ...]
    max_pages_per_call: int
    ocr_confidence_threshold: float

    @property
    def eligible_source_refs(self) -> tuple[str, ...]:
        return tuple(item.source_ref for item in self.eligible)


@dataclass(frozen=True)
class SelectiveVisionObservation:
    """单次视觉观察结果；永不作为入排结论或 OCR 覆盖。"""

    source_refs: tuple[str, ...]
    page_ordinals: tuple[int, ...]
    reasons: tuple[str, ...]
    text: str
    model: str
    finish_reason: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    allowed_source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectiveVisionReviewOutcome:
    """调用适配结果：成功观察或显式关闭失败（二者互斥）。"""

    plan: SelectiveVisionPlan
    observations: tuple[SelectiveVisionObservation, ...] = ()
    closed_error: SelectiveVisionClosedError | None = None
    disabled: bool = False

    @property
    def ok(self) -> bool:
        return self.closed_error is None and not self.disabled


def _route_value(route: str | ExtractionRoute | None) -> str | None:
    if route is None:
        return None
    if isinstance(route, ExtractionRoute):
        return route.value
    return str(route).strip() or None


def _status_value(status: str | PageArtifactStatus | None) -> str | None:
    if status is None:
        return None
    if isinstance(status, PageArtifactStatus):
        return status.value
    return str(status).strip() or None


def _normalized_risk_kinds(kinds: Sequence[str] | None) -> frozenset[str]:
    if not kinds:
        return frozenset()
    return frozenset(str(kind).strip() for kind in kinds if str(kind).strip())


def infer_complex_layout_not_represented(
    *,
    has_ruled_table: bool = False,
    has_native_text: bool = False,
    native_text_char_count: int = 0,
    layout_block_count: int | None = None,
) -> bool:
    """从结构元数据推断“复杂版面未被原生文本代表”（内容中立）。"""
    sufficient = (
        has_native_text and native_text_char_count >= NATIVE_TEXT_SUFFICIENT_CHARS
    )
    if has_ruled_table and not sufficient:
        return True
    if layout_block_count is not None and layout_block_count >= 8 and not sufficient:
        return True
    return False


def assess_page_vision_eligibility(
    signals: PageVisionTriageSignals,
    *,
    enabled: bool | None = None,
    ocr_confidence_threshold: float | None = None,
) -> PageVisionEligibility:
    """对单页做内容中立的视觉核验资格判定。"""
    is_enabled = SELECTIVE_VISION_ENABLED if enabled is None else bool(enabled)
    threshold = (
        SELECTIVE_VISION_OCR_CONFIDENCE_THRESHOLD
        if ocr_confidence_threshold is None
        else float(ocr_confidence_threshold)
    )
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("ocr_confidence_threshold must be in [0, 1]")

    source_ref = str(signals.source_ref).strip()
    page_ordinal = int(signals.page_ordinal)
    if not is_enabled:
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=False,
            skip_reason=SKIP_SELECTIVE_VISION_DISABLED,
        )

    status = _status_value(signals.page_artifact_status)
    if status == PageArtifactStatus.FAILED.value:
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=False,
            skip_reason=SKIP_FAILED_PAGE,
        )
    if not signals.has_page_image:
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=False,
            skip_reason=SKIP_MISSING_PAGE_IMAGE,
        )

    route = _route_value(signals.extraction_route)
    risk_kinds = _normalized_risk_kinds(signals.ocr_risk_kinds)
    reasons: list[VisionRiskReason] = []

    media = str(signals.media_kind or "").strip().lower()
    sufficient_native = (
        bool(signals.has_native_text)
        and int(signals.native_text_char_count) >= NATIVE_TEXT_SUFFICIENT_CHARS
    )
    sufficient_ocr = (
        bool(signals.has_ocr_text)
        and int(signals.ocr_text_char_count) >= NATIVE_TEXT_SUFFICIENT_CHARS
    )
    sufficient_primary_text = sufficient_native or sufficient_ocr
    marks = signals.non_text_mark_count

    if media in _IMAGE_MEDIA_KINDS and not sufficient_primary_text:
        reasons.append(VISION_REASON_SCAN_OR_IMAGE_ONLY)
    elif route == ExtractionRoute.VISION_OCR.value and not sufficient_primary_text:
        reasons.append(VISION_REASON_SCAN_OR_IMAGE_ONLY)
    elif not sufficient_primary_text and marks is not None and marks > 0:
        reasons.append(VISION_REASON_SCAN_OR_IMAGE_ONLY)

    if signals.complex_layout_not_represented_by_native_text:
        reasons.append(VISION_REASON_COMPLEX_VISUAL_OR_TABLE)

    if signals.native_extraction_anomaly or status == PageArtifactStatus.DEGRADED.value:
        reasons.append(VISION_REASON_NATIVE_EXTRACTION_ANOMALY)
    elif (
        route in _NATIVE_TEXT_ROUTES
        and signals.has_native_text
        and not sufficient_native
    ):
        reasons.append(VISION_REASON_NATIVE_EXTRACTION_ANOMALY)

    low_confidence = (
        signals.ocr_confidence is not None
        and float(signals.ocr_confidence) < threshold
    )
    if low_confidence or OcrRiskKind.LOW_CONFIDENCE.value in risk_kinds:
        reasons.append(VISION_REASON_OCR_EVIDENCE_RISK)

    ordered: list[VisionRiskReason] = []
    seen: set[str] = set()
    for reason in (
        VISION_REASON_SCAN_OR_IMAGE_ONLY,
        VISION_REASON_COMPLEX_VISUAL_OR_TABLE,
        VISION_REASON_NATIVE_EXTRACTION_ANOMALY,
        VISION_REASON_OCR_EVIDENCE_RISK,
    ):
        if reason in reasons and reason not in seen:
            ordered.append(reason)
            seen.add(reason)

    if ordered:
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=True,
            reasons=tuple(ordered),
        )

    if (
        not sufficient_primary_text
        and marks == 0
        and media not in _IMAGE_MEDIA_KINDS
        and route != ExtractionRoute.VISION_OCR.value
    ):
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=False,
            skip_reason=SKIP_BLANK_OR_NO_CONTENT,
        )

    if sufficient_primary_text:
        return PageVisionEligibility(
            source_ref=source_ref,
            page_ordinal=page_ordinal,
            eligible=False,
            skip_reason=SKIP_NATIVE_TEXT_PRIMARY,
        )

    return PageVisionEligibility(
        source_ref=source_ref,
        page_ordinal=page_ordinal,
        eligible=False,
        skip_reason=SKIP_NO_RISK_REASON,
    )


def plan_selective_vision_reviews(
    pages: Sequence[PageVisionTriageSignals],
    *,
    enabled: bool | None = None,
    ocr_confidence_threshold: float | None = None,
    max_pages_per_call: int | None = None,
) -> SelectiveVisionPlan:
    """为一批页面生成选择性视觉核验计划。

    ``max_pages_per_call`` 只限定单次调用页数；所有合格页面均保留在计划中，
    由观察服务分批处理，避免因单次调用上限静默漏页。
    """
    is_enabled = SELECTIVE_VISION_ENABLED if enabled is None else bool(enabled)
    threshold = (
        SELECTIVE_VISION_OCR_CONFIDENCE_THRESHOLD
        if ocr_confidence_threshold is None
        else float(ocr_confidence_threshold)
    )
    budget = (
        SELECTIVE_VISION_MAX_PAGES_PER_CALL
        if max_pages_per_call is None
        else int(max_pages_per_call)
    )
    if budget < 1:
        raise ValueError("max_pages_per_call must be >= 1")

    eligible: list[PageVisionEligibility] = []
    skipped: list[PageVisionEligibility] = []
    identities: set[tuple[str, int]] = set()
    for signals in pages:
        decision = assess_page_vision_eligibility(
            signals,
            enabled=is_enabled,
            ocr_confidence_threshold=threshold,
        )
        identity = (decision.source_ref, decision.page_ordinal)
        if identity in identities:
            raise ValueError(
                "页面来源标识重复："
                f"source_ref={decision.source_ref}, page_ordinal={decision.page_ordinal}"
            )
        identities.add(identity)
        if not decision.eligible:
            skipped.append(decision)
            continue
        eligible.append(decision)

    return SelectiveVisionPlan(
        plan_version=SELECTIVE_VISION_PLAN_VERSION,
        enabled=is_enabled,
        eligible=tuple(eligible),
        skipped=tuple(skipped),
        max_pages_per_call=budget,
        ocr_confidence_threshold=threshold,
    )


def select_page_inputs_for_plan(
    plan: SelectiveVisionPlan,
    pages: Sequence[PageVisionInput],
) -> tuple[PageVisionInput, ...]:
    """按计划挑选带图像载荷的 ``PageVisionInput``（保序、来源身份对齐）。"""
    wanted = {(item.source_ref, item.page_ordinal): item for item in plan.eligible}
    selected: list[PageVisionInput] = []
    seen: set[tuple[str, int]] = set()
    for page in pages:
        key = (str(page.source_ref).strip(), int(page.page_ordinal))
        if key not in wanted or key in seen:
            continue
        selected.append(page)
        seen.add(key)
    return tuple(selected)


def build_selective_vision_prompts(
    *,
    reasons: Sequence[str] | None = None,
) -> tuple[str, str]:
    """构造内容中立的系统/用户提示；不注入项目特异临床关键词。"""
    system_prompt = _DEFAULT_REVIEW_SYSTEM_PROMPT
    cleaned = [str(r).strip() for r in (reasons or ()) if str(r).strip()]
    unknown = [r for r in cleaned if r not in ALLOWED_VISION_RISK_REASONS]
    if unknown:
        raise ValueError(
            "Unsupported vision risk reasons in prompt builder: "
            + ", ".join(sorted(set(unknown)))
        )
    reason_note = ""
    if cleaned:
        reason_note = (
            " 本页因以下结构或识别质量风险进入视觉核验："
            + ", ".join(cleaned)
            + "。"
        )
    return system_prompt, _DEFAULT_REVIEW_USER_PROMPT + reason_note


def _close_from_independent_error(exc: Exception) -> SelectiveVisionClosedError:
    from app.llm import independent_vlm as vlm

    if isinstance(exc, vlm.IndependentVlmConfigError):
        return SelectiveVisionClosedError(
            f"Selective vision closed: {exc}",
            failure_kind="config_error",
            disabled=True,
            cause=exc,
        )
    if isinstance(exc, vlm.IndependentVlmSourceFidelityError):
        return SelectiveVisionClosedError(
            f"Selective vision closed: {exc}",
            failure_kind="source_fidelity",
            disabled=True,
            cause=exc,
        )
    if isinstance(exc, vlm.IndependentVlmRemoteError):
        return SelectiveVisionClosedError(
            f"Selective vision closed: {exc}",
            failure_kind=str(getattr(exc, "failure_kind", None) or "remote_error"),
            disabled=bool(getattr(exc, "disabled", True)),
            cause=exc,
        )
    return SelectiveVisionClosedError(
        f"Selective vision closed: {exc}",
        failure_kind="independent_vlm_error",
        disabled=True,
        cause=exc,
    )


def observation_from_chat_result(
    result: IndependentVlmChatResult,
    *,
    pages: Sequence[PageVisionInput],
    reasons: Sequence[str],
) -> SelectiveVisionObservation:
    """把 Independent VLM 传输结果投影为证据观察（非临床结论）。"""
    return SelectiveVisionObservation(
        source_refs=tuple(str(page.source_ref) for page in pages),
        page_ordinals=tuple(int(page.page_ordinal) for page in pages),
        reasons=tuple(str(reason) for reason in reasons),
        text=result.text,
        model=result.model,
        finish_reason=result.finish_reason,
        usage=dict(result.usage or {}),
        allowed_source_refs=tuple(result.allowed_source_refs),
    )


async def run_selective_vision_review(
    plan: SelectiveVisionPlan,
    pages: Sequence[PageVisionInput],
    *,
    prompt: str | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    require_route_ready: bool = True,
) -> SelectiveVisionReviewOutcome:
    """按计划调用独立 VLM；失败显式关闭，绝不回退 OCR/语义路由。"""
    from app.llm import independent_vlm as vlm

    if not plan.enabled:
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(),
            closed_error=SelectiveVisionClosedError(
                "选择性视觉核验未启用。",
                failure_kind="disabled",
                disabled=True,
            ),
            disabled=True,
        )

    selected = select_page_inputs_for_plan(plan, pages)
    if not plan.eligible:
        return SelectiveVisionReviewOutcome(plan=plan, observations=())
    expected = {
        (item.source_ref, item.page_ordinal)
        for item in plan.eligible
    }
    supplied = {
        (str(page.source_ref).strip(), int(page.page_ordinal))
        for page in selected
    }
    if supplied != expected:
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(),
            closed_error=SelectiveVisionClosedError(
                "选择性视觉核验已关闭：计划中的页面图片未完整提供。",
                failure_kind="missing_page_inputs",
                disabled=True,
            ),
            disabled=True,
        )

    if len(selected) > plan.max_pages_per_call:
        selected = selected[: plan.max_pages_per_call]

    reason_values: list[str] = []
    for item in plan.eligible:
        if any(
            page.source_ref == item.source_ref
            and page.page_ordinal == item.page_ordinal
            for page in selected
        ):
            reason_values.extend(item.reason_values)
    ordered_reasons: list[str] = []
    seen_reasons: set[str] = set()
    for reason in reason_values:
        if reason not in seen_reasons:
            ordered_reasons.append(reason)
            seen_reasons.add(reason)

    default_system, default_user = build_selective_vision_prompts(
        reasons=ordered_reasons
    )
    final_system = system_prompt if system_prompt is not None else default_system
    final_prompt = prompt if prompt is not None else default_user

    if require_route_ready:
        try:
            ready = await check_independent_vlm()
        except vlm.IndependentVlmError as exc:
            closed = _close_from_independent_error(exc)
            logger.warning("selective vision config gate failed: %s", closed)
            return SelectiveVisionReviewOutcome(
                plan=plan,
                observations=(),
                closed_error=closed,
                disabled=closed.disabled,
            )
        if not ready:
            closed = SelectiveVisionClosedError(
                "选择性视觉核验已关闭：独立视觉模型尚未完成配置。",
                failure_kind="config_error",
                disabled=True,
            )
            return SelectiveVisionReviewOutcome(
                plan=plan,
                observations=(),
                closed_error=closed,
                disabled=True,
            )

    try:
        result = await independent_vlm_page_chat(
            final_prompt,
            selected,
            system_prompt=final_system,
            model=model,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
    except vlm.IndependentVlmError as exc:
        closed = _close_from_independent_error(exc)
        logger.warning(
            "selective vision fail-closed kind=%s disabled=%s",
            closed.failure_kind,
            closed.disabled,
        )
        return SelectiveVisionReviewOutcome(
            plan=plan,
            observations=(),
            closed_error=closed,
            disabled=closed.disabled,
        )

    observation = observation_from_chat_result(
        result,
        pages=selected,
        reasons=ordered_reasons,
    )
    return SelectiveVisionReviewOutcome(
        plan=plan,
        observations=(observation,),
        closed_error=None,
        disabled=False,
    )


__all__ = [
    "ALLOWED_VISION_RISK_REASONS",
    "NATIVE_TEXT_SUFFICIENT_CHARS",
    "SELECTIVE_VISION_PLAN_VERSION",
    "SKIP_BLANK_OR_NO_CONTENT",
    "SKIP_FAILED_PAGE",
    "SKIP_MISSING_PAGE_IMAGE",
    "SKIP_NATIVE_TEXT_PRIMARY",
    "SKIP_NO_RISK_REASON",
    "SKIP_SELECTIVE_VISION_DISABLED",
    "VISION_REASON_COMPLEX_VISUAL_OR_TABLE",
    "VISION_REASON_NATIVE_EXTRACTION_ANOMALY",
    "VISION_REASON_OCR_EVIDENCE_RISK",
    "VISION_REASON_SCAN_OR_IMAGE_ONLY",
    "PageVisionEligibility",
    "PageVisionTriageSignals",
    "SelectiveVisionClosedError",
    "SelectiveVisionConfigError",
    "SelectiveVisionObservation",
    "SelectiveVisionPlan",
    "SelectiveVisionReviewError",
    "SelectiveVisionReviewOutcome",
    "VisionRiskReason",
    "assess_page_vision_eligibility",
    "build_selective_vision_prompts",
    "infer_complex_layout_not_represented",
    "observation_from_chat_result",
    "plan_selective_vision_reviews",
    "run_selective_vision_review",
    "select_page_inputs_for_plan",
]
