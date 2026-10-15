"""Phase 4 证据页、OCR 与诚实定位领域契约（Slice 4.0 冻结）。

本模块只冻结可复用契约与纯校验，不包含任何存储、文件路径或外部模型调用。
覆盖设计书 §3.3 与 §3.4 的页级产物、识别配置、原始工件引用、坐标系、
定位精度与风险输出合同：

- ``CoordinateFrame``         定位坐标系：PDF points 或渲染页图像素，含页尺寸/旋转/变换版本；
- ``PageArtifact``            不可变页产物：页图输入哈希、原生文本/坐标哈希、渲染器版本、
                              派生物哈希与失败原因；
- ``OCRProfile``              识别配置稳定指纹：路线、提供方、模型、参数、解析器与坐标变换版本；
- ``RawOcrRequestArtifact``   不可变原始请求工件引用（内容寻址存储引用，不暴露本机路径）；
- ``RawOcrResponseArtifact``  不可变原始响应工件引用；
- ``PageQualityMetrics``      页级质量指标；
- ``OcrRiskFlag``             结构化 OCR 风险（极性/数值/小数/单位/日期 + 提示性风险）；
- ``LocatorResult``           四级定位结果，绑定坐标系与不可变来源文本哈希；
- ``OCRPage``                 页级识别结果，保存不可变原文与风险项。

Slice 4.0 停止点约束：区域坐标必须携带真实坐标系与页尺寸；非 bbox 定位不得携带坐标；
``page_only`` 必须说明降级原因；重复文本未稳定消歧时不得生成伪精确高亮。
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from pydantic import Field, model_serializer, model_validator

from .common import ContractModel, VersionedModel
from .enums import (
    CoordinateSpace,
    DisambiguationOutcome,
    ExtractionRoute,
    LocatorPrecision,
    OCRPageStatus,
    OcrRiskKind,
    OcrRiskLevel,
    PageArtifactStatus,
)
from .evidence import BoundingBox

_SHA256 = r"^[0-9a-f]{64}$"


class CoordinateFrame(ContractModel):
    """定位坐标系与页尺寸。

    ``space`` 决定 bbox 的语义与原点方向：
    ``pdf_points`` 原点在页面左下、y 向上；``page_image_pixels`` 原点在左上、y 向下。
    ``page_width/page_height`` 是解析器或渲染器提供的**可视页**尺寸；旋转页的 90/270
    度尺寸可能已交换。旋转本身只记录在 frame 中，换算函数不再对已经可视化的坐标重复旋转。
    ``transform_version`` 冻结 ``pdf_points -> page_image_pixels`` 的换算规则版本，
    只有渲染页图与解析器同时升级时才改变。
    """

    space: CoordinateSpace
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    rotation: int = Field(ge=0, le=270)
    transform_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_frame(self) -> CoordinateFrame:
        if self.rotation % 90 != 0:
            raise ValueError("页面旋转必须是 0/90/180/270 的倍数")
        return self


class PageArtifact(VersionedModel):
    """不可变页产物：页图、原生文本/坐标与派生信息的身份与哈希。

    页面身份由 ``source_sha256 + page_number/original_frame + page_input_sha256``
    共同决定；``page_input_sha256`` 是**渲染/解码输入**的内容哈希（稳定身份），
    同一字节输入配合同一渲染器版本才可能复用页产物。

    字段语义与状态：
    - ``SUCCEEDED`` / ``DEGRADED``：必须提供真实 ``page_input_sha256``、正数
      ``page_width``/``page_height``、合法 ``rotation`` 与 ``page_image_sha256``；
    - ``FAILED``：表示整文件无法分页或该页无法解码，此时不存在真实页输入哈希、
      页宽、页高与旋转信息，这些字段必须允许为 ``None``，不得用 ``0*64``、
      ``1x1`` 或 ``rotation=0`` 等伪值填充；
    - 原生文本可以没有空间坐标（如 TXT），即 ``native_text_sha256`` 可单独存在；
      但 ``native_coordinates_sha256`` 绝不允许在无 ``native_text_sha256`` 时存在，
      不得伪造坐标。
    """

    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    original_frame: str | None = None
    source_sha256: str = Field(pattern=_SHA256)
    page_input_sha256: str | None = Field(default=None, pattern=_SHA256)
    page_image_sha256: str | None = Field(default=None, pattern=_SHA256)
    native_text_sha256: str | None = Field(default=None, pattern=_SHA256)
    native_coordinates_sha256: str | None = Field(default=None, pattern=_SHA256)
    page_width: float | None = Field(default=None, gt=0)
    page_height: float | None = Field(default=None, gt=0)
    rotation: int | None = Field(default=None, ge=0, le=270)
    renderer_version: str | None = None
    decoder_version: str | None = None
    derivative_sha256: str = Field(pattern=_SHA256)
    coordinate_transform_version: str = Field(min_length=1)
    status: PageArtifactStatus
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_artifact(self) -> PageArtifact:
        if self.rotation is not None and self.rotation % 90 != 0:
            raise ValueError("页面旋转必须是 0/90/180/270 的倍数")
        if self.status in {PageArtifactStatus.SUCCEEDED, PageArtifactStatus.DEGRADED}:
            if self.page_input_sha256 is None:
                raise ValueError("成功或降级页产物必须提供真实页图输入哈希")
            if self.page_width is None or self.page_height is None:
                raise ValueError("成功或降级页产物必须提供真实页宽与页高")
            if self.rotation is None:
                raise ValueError("成功或降级页产物必须提供合法页面旋转")
            if self.page_image_sha256 is None:
                raise ValueError("成功或降级页产物必须提供页图内容哈希")
            if not self.renderer_version or not self.decoder_version:
                raise ValueError("成功或降级页产物必须提供渲染与解码版本")
        if self.status == PageArtifactStatus.SUCCEEDED and self.failure_reason is not None:
            raise ValueError("页产物成功不应携带失败原因")
        if self.status == PageArtifactStatus.DEGRADED and not self.failure_reason:
            raise ValueError("降级页产物必须说明降级原因")
        if self.status == PageArtifactStatus.FAILED and not self.failure_reason:
            raise ValueError("失败页产物必须说明失败原因")
        if self.native_coordinates_sha256 is not None and self.native_text_sha256 is None:
            raise ValueError("原生坐标哈希必须伴随原生文本哈希，不得伪造坐标")
        return self


class OCRProfile(VersionedModel):
    """识别配置的稳定指纹；任一识别决定性输入变化必然产生新指纹。"""

    ocr_profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=_SHA256)
    extraction_route: ExtractionRoute
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    # 服务无法给出模型修订号时必须显式 "unknown"，不得省略该字段。
    model_revision: str = Field(default="unknown", min_length=1)
    prompt_sha256: str | None = Field(default=None, pattern=_SHA256)
    parser_version: str = Field(min_length=1)
    render_params_sha256: str | None = Field(default=None, pattern=_SHA256)
    request_params_sha256: str | None = Field(default=None, pattern=_SHA256)
    layout_parser_version: str | None = None
    coordinate_transform_version: str = Field(min_length=1)
    attempt_namespace: str | None = Field(default=None, min_length=1)
    created_at: datetime

    @model_serializer(mode="wrap")
    def serialize_profile(self, handler):
        payload = handler(self)
        if self.attempt_namespace is None:
            payload.pop("attempt_namespace", None)
        return payload

    @model_validator(mode="after")
    def validate_profile_identity(self) -> OCRProfile:
        _require_utc(self.created_at, "OCRProfile.created_at")
        from app.domain.publication import canonical_hash

        payload = {
                "profile": "ocr_profile/v1",
                "extraction_route": self.extraction_route.value,
                "provider": self.provider,
                "model_id": self.model_id,
                "model_revision": self.model_revision,
                "prompt_sha256": self.prompt_sha256,
                "parser_version": self.parser_version,
                "render_params_sha256": self.render_params_sha256,
                "request_params_sha256": self.request_params_sha256,
                "layout_parser_version": self.layout_parser_version,
                "coordinate_transform_version": self.coordinate_transform_version,
            }
        if self.attempt_namespace is not None:
            if not self.attempt_namespace.strip() or self.extraction_route != ExtractionRoute.VISION_OCR:
                raise ValueError("重新识别尝试仅适用于视觉转录")
            payload["attempt_namespace"] = self.attempt_namespace
        expected = canonical_hash(payload)
        if self.profile_sha256 != expected:
            raise ValueError("OCRProfile 指纹与识别身份字段不一致")
        return self


class RawOcrRequestArtifact(VersionedModel):
    """不可变原始 OCR 请求工件引用（内容寻址存储引用，不暴露本机绝对路径）。"""

    raw_request_artifact_id: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)
    storage_ref: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_ref(self) -> RawOcrRequestArtifact:
        _require_utc(self.created_at, "RawOcrRequestArtifact.created_at")
        if self.storage_ref.startswith("/") or ".." in self.storage_ref:
            raise ValueError("原始请求存储引用必须是可移植内容寻址引用，不能是本机绝对路径")
        return self


class RawOcrResponseArtifact(VersionedModel):
    """不可变原始 OCR 响应工件引用；provider 原文不删改，任何清洗都是派生步骤。"""

    raw_response_artifact_id: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)
    storage_ref: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(default="unknown", min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_ref(self) -> RawOcrResponseArtifact:
        _require_utc(self.created_at, "RawOcrResponseArtifact.created_at")
        if self.storage_ref.startswith("/") or ".." in self.storage_ref:
            raise ValueError("原始响应存储引用必须是可移植内容寻址引用，不能是本机绝对路径")
        return self


class PageQualityMetrics(ContractModel):
    """页级质量指标；不承载任何临床判断。"""

    char_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    layout_block_count: int | None = Field(default=None, ge=0)


class OcrRiskFlag(ContractModel):
    """结构化 OCR 风险输出：类别、阻断等级、原文位置与规则版本。

    风险扫描只决定该页是否需要核对及发布门禁是否可继续，不修改文义。
    """

    risk_id: str = Field(min_length=1)
    kind: OcrRiskKind
    level: OcrRiskLevel
    text: str = Field(min_length=1)
    text_start: int = Field(ge=0)
    text_end: int = Field(gt=0)
    detail: str | None = None
    rule_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> OcrRiskFlag:
        if self.text_end <= self.text_start:
            raise ValueError("风险文本范围必须有效")
        if self.text_end - self.text_start != len(self.text):
            raise ValueError("风险文本长度必须与范围一致")
        return self


class LocatorResult(VersionedModel):
    """四级定位结果（区域坐标 > 文本范围 > 页内摘录 > 仅页码）。

    与 ``EvidenceSpan`` 的四级合同一致，并补齐定位产物身份：坐标系/页尺寸/旋转、
    定位算法版本、来源文本哈希与页产物引用。只有通过真实性门禁的真实坐标才能形成
    ``bbox``；重复文本未稳定消歧时按 ``page_excerpt`` 降级并说明原因。
    """

    locator_id: str = Field(min_length=1)
    precision: LocatorPrecision
    coordinate_frame: CoordinateFrame | None = None
    bbox: BoundingBox | None = None
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)
    excerpt: str | None = None
    anchor_hash: str | None = None
    source_text_sha256: str = Field(pattern=_SHA256)
    page_artifact_id: str = Field(min_length=1)
    locator_algorithm_version: str = Field(min_length=1)
    disambiguation: DisambiguationOutcome = DisambiguationOutcome.UNIQUE_MATCH
    match_confidence: float | None = Field(default=None, ge=0, le=1)
    degradation_reason: str | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> LocatorResult:
        if self.precision == LocatorPrecision.BBOX:
            if self.bbox is None:
                raise ValueError("bbox 定位必须提供坐标")
            if self.coordinate_frame is None:
                raise ValueError("bbox 定位必须提供坐标系与页尺寸")
            if self.disambiguation != DisambiguationOutcome.UNIQUE_MATCH:
                raise ValueError("区域定位只能在唯一消歧后产生")
            if (
                self.bbox.x0 < 0
                or self.bbox.y0 < 0
                or self.bbox.x1 > self.coordinate_frame.page_width
                or self.bbox.y1 > self.coordinate_frame.page_height
            ):
                raise ValueError("bbox 定位不能越出绑定页工件的页面边界")
        else:
            if self.bbox is not None or self.coordinate_frame is not None:
                raise ValueError("非 bbox 定位不能携带坐标或坐标系")
        if self.precision == LocatorPrecision.TEXT_RANGE:
            if self.text_start is None or self.text_end is None or self.text_end <= self.text_start:
                raise ValueError("text_range 必须提供有效字符范围")
            if self.source_text_sha256 is None:
                raise ValueError("text_range 必须绑定不可变来源文本哈希")
            if self.disambiguation != DisambiguationOutcome.UNIQUE_MATCH:
                raise ValueError("text_range 只能在唯一消歧后产生")
        elif self.text_start is not None or self.text_end is not None:
            raise ValueError("非 text_range 定位不能携带字符范围")
        if self.precision == LocatorPrecision.PAGE_EXCERPT:
            if not self.excerpt:
                raise ValueError("page_excerpt 必须提供页面摘录")
            if self.disambiguation == DisambiguationOutcome.NOT_FOUND:
                raise ValueError("目标未找到时不能产生 page_excerpt")
            if (
                self.disambiguation != DisambiguationOutcome.UNIQUE_MATCH
                and not self.degradation_reason
            ):
                raise ValueError("重复文本的 page_excerpt 必须说明降级原因")
        if self.precision == LocatorPrecision.PAGE_ONLY:
            if self.excerpt is not None:
                raise ValueError("page_only 不能携带伪精确页面摘录")
            if not self.degradation_reason:
                raise ValueError("page_only 必须说明定位降级原因")
            if self.disambiguation != DisambiguationOutcome.NOT_FOUND:
                raise ValueError("page_only 只能在目标文本未找到时产生")
        return self


class OCRPage(VersionedModel):
    """页级识别结果：不可变原始文本、规范化派生物、质量、风险与状态。

    ``page_input_sha256`` 是**实际送入 OCR 的页图字节哈希**（与
    ``PageArtifact.page_image_sha256`` 一致）；``PageArtifact.page_input_sha256``
    则是渲染/解码输入的稳定身份，二者语义不同。缓存键以实际页图输入为准。
    """

    ocr_page_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=_SHA256)
    page_number: int = Field(ge=1)
    page_input_sha256: str = Field(pattern=_SHA256)
    ocr_profile_sha256: str = Field(pattern=_SHA256)
    cache_key: str = Field(pattern=_SHA256)
    layout_parser_version: str | None = None
    coordinate_transform_version: str = Field(min_length=1)
    raw_text: str = ""
    raw_text_sha256: str = Field(pattern=_SHA256)
    normalized_text: str | None = None
    layout_sidecar_sha256: str | None = Field(default=None, pattern=_SHA256)
    quality: PageQualityMetrics
    risk_items: list[OcrRiskFlag] = Field(default_factory=list)
    status: OCRPageStatus
    failure_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_page(self) -> OCRPage:
        for field_name, timestamp in (
            ("started_at", self.started_at),
            ("completed_at", self.completed_at),
        ):
            if timestamp is not None:
                _require_utc(timestamp, f"OCRPage.{field_name}")
        if self.raw_text_sha256 != sha256(self.raw_text.encode("utf-8")).hexdigest():
            raise ValueError("OCRPage 原文哈希与原始文本不一致")
        from app.domain.publication import (
            legacy_ocr_page_cache_hash,
            ocr_page_cache_hash,
        )

        legacy_inputs = dict(
            source_sha256=self.source_sha256,
            page_number=self.page_number,
            ocr_profile_sha256=self.ocr_profile_sha256,
            page_input_sha256=self.page_input_sha256,
            layout_parser_version=self.layout_parser_version,
            coordinate_transform_version=self.coordinate_transform_version,
        )
        expected_cache_key = ocr_page_cache_hash(
            page_artifact_id=self.page_artifact_id, **legacy_inputs
        )
        # 历史行以 v1（仅内容键）持久化且不可改写；解码回放仍必须可验证。
        # 新写入由适配器/执行器统一产生 v2（绑定 page_artifact_id）。
        if self.cache_key not in (
            expected_cache_key,
            legacy_ocr_page_cache_hash(**legacy_inputs),
        ):
            raise ValueError("OCRPage 缓存键与页面/识别配置身份不一致")

        risk_ids: set[str] = set()
        for item in self.risk_items:
            if item.risk_id in risk_ids:
                raise ValueError("OCRPage 风险项不能重复使用同一风险 ID")
            risk_ids.add(item.risk_id)
            if item.text_end > len(self.raw_text) or self.raw_text[item.text_start : item.text_end] != item.text:
                raise ValueError("OCRPage 风险项范围必须指向原始识别文本")

        if self.status == OCRPageStatus.PENDING:
            if self.started_at is not None or self.completed_at is not None or self.failure_reason is not None:
                raise ValueError("等待识别页不能携带开始/完成时间或失败原因")
        elif self.status == OCRPageStatus.PROCESSING:
            if self.started_at is None:
                raise ValueError("处理中页必须提供开始时间")
            if self.completed_at is not None or self.failure_reason is not None:
                raise ValueError("处理中页不能携带完成时间或失败原因")
        elif self.status == OCRPageStatus.SUCCEEDED:
            if self.started_at is None or self.completed_at is None:
                raise ValueError("识别成功必须同时提供开始和完成时间")
            if self.failure_reason is not None:
                raise ValueError("识别成功不应携带失败原因")
        elif self.status in {OCRPageStatus.FAILED, OCRPageStatus.CANCELLED}:
            if self.completed_at is None:
                raise ValueError("失败或取消页必须提供完成时间")
            if self.failure_reason is None:
                raise ValueError("失败或取消页必须说明原因")

        if self.started_at is not None and self.completed_at is not None:
            try:
                if self.completed_at < self.started_at:
                    raise ValueError("识别完成时间不能早于开始时间")
            except TypeError as exc:
                raise ValueError("识别开始和完成时间必须使用一致的时区语义") from exc
        return self


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the OCR contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")
