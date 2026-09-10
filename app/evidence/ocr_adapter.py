"""OCR 配置指纹、页级缓存适配与冻结 text-only 识别适配器（Slice 4.3，worker_02）。

本模块实现「一次页识别」的确定性装配与缓存：``OCRProfile`` 指纹、页级缓存唯一
键、缓存命中校验、原始请求/响应工件落盘与 ``OCRPage`` 合同构建。共享 oMLX 门禁
与页工作租约由 worker_03 在调用方组合；本模块不实现任何全局并发额度。

**分阶段 API（worker_03 检查点边界）**：

- ``prepare``：只做零推理准备 —— 构建/复用不可变 ``OCRProfile`` 与原始请求工件
  （内容寻址），绝不调用外部推理。worker_03 在同一事务提交「准备结果 + 请求
  检查点」，然后**在事务外**经共享 oMLX 门禁排队推理；
- ``finalize_success`` / ``finalize_failure``：把注入的 ``InferenceResult`` 或
  已净化的失败类别/原因转为原始响应工件 + 不可变 ``OCRPage``（内容寻址、确定性）；
- ``recognize``：便捷组合包装（prepare -> 推理 -> finalize），不改变语义。

事务所有权：worker_03 负责 —— 1) 提交 prepare 的准备/请求检查点事务；2) 调用
共享 oMLX 门禁（事务外）；3) 用 ``PageWorkLeaseRepository.commit_guard`` 与
OCRPage/attempt 插入在**同一事务**内提交结果；被拒的晚到结果在门禁事务回滚后
以独立审计事务追加。

冻结路线约束（Slice 4.0 停止点）：

- 当前路由是 **text-only**：只返回识别文本，不产生任何 bbox/坐标；
  ``OcrRecognition.degradation_reason`` 必须携带真实的降级原因；
- 只有未来真实适配器从 provider 响应验证过机器坐标后，才允许产生区域定位；
- 缓存命中必须不可变且作用域中立，但不得绕过内容/识别配置校验；v2 缓存键
  绑定页产物身份（命中只在本页产物内），而**内容级推理复用**在 v2 未命中时
  按设计书内容哈希契约（内容哈希+页码+识别配置版本）寻找他版成功页，并把
  其推理结果复制为**本页产物自有**的新成功行（新 v2 键）——推理不重复付费，
  历史行不改写，跨产物借用（清单完整性门禁拒绝的根因）不可能发生；
- 任一决定性输入（模型/提示词/解析器/渲染/变换）变化必然产生新指纹与新缓存键；
- 领域失败文本只含稳定中文措辞：异常类名、provider 原文、stderr、密钥等细节
  归 worker_03 尝试/任务技术记录，绝不进入 ``OCRPage.failure_reason``。

原始请求与原始响应分别落盘为内容寻址工件（``ArtifactStore``），provider 原文
不删改；任何清洗都是派生步骤（``normalized_text``）；风险扫描由 Slice 4.4 负责。
"""
from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.domain.contracts.enums import (
    ExtractionRoute,
    OcrFailureCategory,
    OCRPageStatus,
)
from app.domain.contracts.ocr import (
    OCRPage,
    OCRProfile,
    PageQualityMetrics,
    RawOcrRequestArtifact,
    RawOcrResponseArtifact,
)
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.coordinates import COORDINATE_TRANSFORM_VERSION
from app.evidence.fingerprint import build_ocr_cache_key, build_profile_fingerprint
from app.evidence.segmentation import (
    DEFAULT_SEGMENTATION_CONFIG,
    SegmentationConfig,
    SegmentationPlan,
    segment_page_image,
)
from app.storage.ocr_repositories import (
    OcrPageRepository,
    OCRProfileRepository,
    RawOcrRequestArtifactRepository,
    RawOcrResponseArtifactRepository,
)

__all__ = [
    "DEFAULT_PROMPT",
    "DEFAULT_REQUEST_PARAMS",
    "TEXT_ONLY_DEGRADATION_REASON",
    "InferenceResult",
    "OcrAdapterError",
    "OcrCacheIdentityError",
    "OcrFailure",
    "OcrRecognition",
    "PreparedOcrRequest",
    "PreparedOcrSegment",
    "SegmentInferenceError",
    "TextOnlyOcrAdapter",
    "build_ocr_page",
    "build_ocr_request_payload",
    "combine_segment_results",
    "composite_segment_failure_response",
]

#: 冻结 text-only 识别提示词（Slice 4.0 探针冻结；提示词参与指纹）。
DEFAULT_PROMPT = (
    "请按页面阅读顺序逐行忠实抄录全部可辨文字，不总结、不推断、不改写，"
    "不要添加原图中不存在的序号、标签或解释。完整保留否定词、数值、小数点、"
    "单位、日期和参考范围；表格按每行从左至右输出。无法辨认的字符写作"
    "〔无法辨认〕，不得重复生成同一行，完成页面最后一项后立即停止。"
    "如果模型原生支持文字区域坐标，请同时返回模型真实生成的坐标；"
    "不支持时只返回识别文字，不要估算或编造坐标。"
)

# GLM-OCR 官方重复惩罚 1.1 在部分密集病历页会重复扩写至输出上限。真实原页
# 对照显示 1.15 可完整停止且较 1.20/1.25 保留更多文字；该参数进入配置指纹。
DEFAULT_REQUEST_PARAMS: dict[str, Any] = {
    "max_tokens": 4096,
    "temperature": 0,
    "repetition_penalty": 1.15,
}

#: text-only 冻结路线的真实降级原因（用户可见中文工作措辞，无工程术语）。
TEXT_ONLY_DEGRADATION_REASON = (
    "当前文字识别仅提供文本，未返回经验证的页面坐标，因此不显示区域标注"
)

#: 通用推理失败的稳定中文领域措辞（异常类名/消息归 worker_03 技术记录）。
INFERENCE_FAILURE_REASON = "本页文字识别未完成，请稍后重试"

#: 页图 MIME（本阶段统一渲染为 PNG）。
PAGE_IMAGE_MIME = "image/png"

_REQUEST_SCHEMA = "phase4_ocr_request/v1"
_REQUEST_PARAMS_VERSION = "slice4.3/request/v1"
_PARSER_VERSION = "slice4.3/text-only/v1"
_SEGMENTED_REQUEST_SCHEMA = "phase4_segmented_ocr_request/v1"
_SEGMENTED_RESPONSE_SCHEMA = "phase4_segmented_ocr_response/v1"


class OcrAdapterError(RuntimeError):
    """OCR 适配器领域错误基类。"""


class OcrCacheIdentityError(OcrAdapterError):
    """缓存命中与请求的识别身份不一致（缓存键空间投毒/漂移防护）。"""


class SegmentInferenceError(OcrAdapterError):
    """页内某一分段失败；保留已完成分段和失败响应的完整组合原文。"""

    def __init__(self, cause: BaseException, raw_response: bytes) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.raw_response = raw_response


@dataclass(frozen=True)
class InferenceResult:
    """一次真实推理的不可变结果（provider 原文 + 识别文本 + 坐标真实性）。"""

    raw_response: bytes
    recognized_text: str
    verified_coordinates: bool = False


@dataclass(frozen=True)
class OcrFailure:
    """已净化的推理失败描述：类别 + 稳定中文原因 + 内部技术诊断。

    ``reason`` 只含稳定中文领域措辞（用户可见）；``technical_detail`` 是非用户
    可见的内部异常细节（异常类名/消息/密钥等），供 worker_03 尝试/任务技术记录。
    """

    category: OcrFailureCategory
    reason: str
    technical_detail: str | None = None
    raw_response: bytes | None = None


@dataclass(frozen=True)
class PreparedOcrSegment:
    """页内一次真实推理的冻结输入。"""

    index: int
    row_index: int
    column_index: int
    x0: int
    x1: int
    y0: int
    y1: int
    crop_x0: int
    crop_x1: int
    crop_y0: int
    crop_y1: int
    image_bytes: bytes
    image_sha256: str
    request_payload: dict[str, Any]
    request_bytes: bytes
    request_artifact: RawOcrRequestArtifact


@dataclass(frozen=True)
class PreparedOcrRequest:
    """阶段 (a) 的不可变准备结果：零推理，可被 worker_03 作为检查点提交。"""

    profile: OCRProfile
    cache_key: str
    source_sha256: str
    page_number: int
    page_artifact_id: str
    page_input_sha256: str  # 实际送入 OCR 的页图字节哈希（== PageArtifact.page_image_sha256）
    page_image_bytes: bytes
    request_payload: dict[str, Any]
    request_bytes: bytes
    request_artifact: RawOcrRequestArtifact
    segmentation_plan: SegmentationPlan
    segments: tuple[PreparedOcrSegment, ...]
    started_at: datetime
    cached_page: OCRPage | None = None
    # 内容级推理复用源（v2 键未命中时）：同内容身份的他版成功页。
    # 命中后由 ``finalize_reuse`` 复制为本页产物自有新成功行，绝不跨产物借用。
    reused_page: OCRPage | None = None


@dataclass(frozen=True)
class OcrRecognition:
    """一次页识别的完整产物：不可变 OCRPage + 原始请求/响应工件引用。

    ``technical_detail`` 是非用户可见的内部异常细节（推理失败时携带），
    供 worker_03 写入尝试/任务技术记录，绝不进入用户可见中文。
    """

    ocr_page: OCRPage
    cached: bool
    degradation_reason: str
    raw_request_artifact: RawOcrRequestArtifact | None = None
    raw_response_artifact: RawOcrResponseArtifact | None = None
    technical_detail: str | None = None
    # 内容级推理复用来源页（cached=True 且发生了复用时携带，供审计/技术记录）。
    reused_from_ocr_page_id: str | None = None


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _artifact_for_request(
    *,
    session,
    artifact_store: ArtifactStore,
    request_bytes: bytes,
    created_at: datetime,
) -> RawOcrRequestArtifact:
    request_sha256 = sha256(request_bytes).hexdigest()
    artifact = RawOcrRequestArtifact(
        raw_request_artifact_id=f"raw-req-{request_sha256[:40]}",
        sha256=request_sha256,
        storage_ref=artifact_store.put("raw_request", request_bytes).storage_ref,
        created_at=created_at,
    )
    RawOcrRequestArtifactRepository(session).get_or_create(artifact)
    return artifact


def _segment_audit_payload(segment: PreparedOcrSegment) -> dict[str, Any]:
    return {
        "index": segment.index,
        "row_index": segment.row_index,
        "column_index": segment.column_index,
        "x0": segment.x0,
        "x1": segment.x1,
        "y0": segment.y0,
        "y1": segment.y1,
        "crop_x0": segment.crop_x0,
        "crop_x1": segment.crop_x1,
        "crop_y0": segment.crop_y0,
        "crop_y1": segment.crop_y1,
        "image_sha256": segment.image_sha256,
        "request_artifact_id": segment.request_artifact.raw_request_artifact_id,
        "request_sha256": segment.request_artifact.sha256,
        "request_bytes_base64": base64.b64encode(segment.request_bytes).decode("ascii"),
    }


def _merge_exact_overlap(
    left: str,
    right: str,
    *,
    allow_single_ascii: bool,
    separator: str,
) -> str:
    """只删除相邻请求中可证明的完全相同重叠，不做模糊臆测。"""
    left = left.strip("\r\n")
    right = right.strip("\r\n")
    if not left:
        return right
    if not right:
        return left
    for size in range(min(len(left), len(right), 256), 0, -1):
        if left[-size:] != right[:size]:
            continue
        if size >= 2 or (
            allow_single_ascii
            and left[-1].isascii()
            and left[-1].isalnum()
        ):
            return left + right[size:]
    return left + separator + right


def _joined_segment_text(
    completed: list[tuple[PreparedOcrSegment, InferenceResult, dict[str, Any]]],
) -> str:
    rows: dict[int, list[tuple[PreparedOcrSegment, InferenceResult]]] = {}
    for segment, result, _lease in completed:
        rows.setdefault(segment.row_index, []).append((segment, result))

    page_text = ""
    for row_index in sorted(rows):
        row_text = ""
        for segment, result in sorted(
            rows[row_index], key=lambda item: item[0].column_index
        ):
            row_text = _merge_exact_overlap(
                row_text,
                result.recognized_text,
                allow_single_ascii=True,
                separator="",
            )
        page_text = _merge_exact_overlap(
            page_text,
            row_text,
            allow_single_ascii=False,
            separator="\n",
        )
    return page_text


def combine_segment_results(
    prepared: PreparedOcrRequest,
    completed: list[tuple[PreparedOcrSegment, InferenceResult, dict[str, Any]]],
) -> tuple[InferenceResult, dict[str, Any]]:
    """按页面从上到下合并分段结果，并完整封存每段原始响应与租约。"""
    if len(completed) != len(prepared.segments):
        raise ValueError("页内分段结果数量不完整，不能生成成功页")
    if len(completed) == 1:
        return completed[0][1], completed[0][2]
    payload = {
        "schema": _SEGMENTED_RESPONSE_SCHEMA,
        "status": "succeeded",
        "segmentation": prepared.segmentation_plan.audit_payload(),
        "segments": [
            {
                "index": segment.index,
                "row_index": segment.row_index,
                "column_index": segment.column_index,
                "x0": segment.x0,
                "x1": segment.x1,
                "y0": segment.y0,
                "y1": segment.y1,
                "crop_x0": segment.crop_x0,
                "crop_x1": segment.crop_x1,
                "crop_y0": segment.crop_y0,
                "crop_y1": segment.crop_y1,
                "image_sha256": segment.image_sha256,
                "gate_lease_id": lease.get("lease_id"),
                "raw_response_base64": base64.b64encode(result.raw_response).decode("ascii"),
                "recognized_text": result.recognized_text,
            }
            for segment, result, lease in sorted(
                completed,
                key=lambda item: (
                    item[0].row_index,
                    item[0].column_index,
                    item[0].index,
                ),
            )
        ],
    }
    raw_response = _canonical_json_bytes(payload)
    return (
        InferenceResult(
            raw_response=raw_response,
            recognized_text=_joined_segment_text(completed),
            verified_coordinates=False,
        ),
        {"lease_id": f"segmented:{sha256(raw_response).hexdigest()[:40]}"},
    )


def composite_segment_failure_response(
    prepared: PreparedOcrRequest,
    completed: list[tuple[PreparedOcrSegment, InferenceResult, dict[str, Any]]],
    *,
    failed_segment: PreparedOcrSegment,
    failed_raw_response: bytes | None,
) -> bytes:
    """保留部分成功结果和失败段原文；该组合工件绝不产生成功 OCRPage。"""
    return _canonical_json_bytes(
        {
            "schema": _SEGMENTED_RESPONSE_SCHEMA,
            "status": "failed",
            "segmentation": prepared.segmentation_plan.audit_payload(),
            "completed_segments": [
                {
                    "index": segment.index,
                    "row_index": segment.row_index,
                    "column_index": segment.column_index,
                    "x0": segment.x0,
                    "x1": segment.x1,
                    "y0": segment.y0,
                    "y1": segment.y1,
                    "crop_x0": segment.crop_x0,
                    "crop_x1": segment.crop_x1,
                    "crop_y0": segment.crop_y0,
                    "crop_y1": segment.crop_y1,
                    "image_sha256": segment.image_sha256,
                    "gate_lease_id": lease.get("lease_id"),
                    "raw_response_base64": base64.b64encode(result.raw_response).decode("ascii"),
                    "recognized_text": result.recognized_text,
                }
                for segment, result, lease in completed
            ],
            "failed_segment": {
                "index": failed_segment.index,
                "row_index": failed_segment.row_index,
                "column_index": failed_segment.column_index,
                "x0": failed_segment.x0,
                "x1": failed_segment.x1,
                "y0": failed_segment.y0,
                "y1": failed_segment.y1,
                "crop_x0": failed_segment.crop_x0,
                "crop_x1": failed_segment.crop_x1,
                "crop_y0": failed_segment.crop_y0,
                "crop_y1": failed_segment.crop_y1,
                "image_sha256": failed_segment.image_sha256,
                "raw_response_base64": (
                    base64.b64encode(failed_raw_response).decode("ascii")
                    if failed_raw_response is not None
                    else None
                ),
            },
        }
    )


def build_ocr_request_payload(
    *,
    profile: OCRProfile,
    source_sha256: str,
    page_number: int,
    page_input_sha256: str,
    image_bytes: bytes,
    image_mime: str = PAGE_IMAGE_MIME,
    prompt: str | None = None,
    request_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造可复现的原始 OCR 请求载荷（base64 页图 + 识别身份 + 提示词 + 参数）。

    载荷只由决定性输入构成（不含文件名/mtime），同一输入产生同一 JSON 字节，
    其 SHA-256 即原始请求工件的内容身份。
    """
    return {
        "schema": _REQUEST_SCHEMA,
        "request_params_version": _REQUEST_PARAMS_VERSION,
        "extraction_route": profile.extraction_route.value,
        "provider": profile.provider,
        "model_id": profile.model_id,
        "model_revision": profile.model_revision,
        "prompt_sha256": profile.prompt_sha256,
        "prompt": prompt,
        "request_params": request_params,
        "page": {
            "source_sha256": source_sha256,
            "page_number": page_number,
            "page_input_sha256": page_input_sha256,
        },
        "image": {
            "mime": image_mime,
            "sha256": sha256(image_bytes).hexdigest(),
            "data_base64": base64.b64encode(image_bytes).decode("ascii"),
        },
    }


def build_ocr_page(
    *,
    ocr_page_id: str,
    page_artifact_id: str,
    source_sha256: str,
    page_number: int,
    page_input_sha256: str,
    ocr_profile: OCRProfile,
    cache_key: str,
    raw_text: str,
    status: OCRPageStatus,
    failure_reason: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> OCRPage:
    """按冻结合同装配不可变 OCRPage（text-only：无坐标，风险项留空）。

    ``page_input_sha256`` 是实际送入 OCR 的页图字节哈希（== 页产物页图哈希）。
    """
    raw_text_sha256 = sha256(raw_text.encode("utf-8")).hexdigest()
    quality = PageQualityMetrics(
        char_count=len(raw_text),
        word_count=len(raw_text.split()),
        confidence=None,
        layout_block_count=None,
    )
    return OCRPage(
        ocr_page_id=ocr_page_id,
        page_artifact_id=page_artifact_id,
        source_sha256=source_sha256,
        page_number=page_number,
        page_input_sha256=page_input_sha256,
        ocr_profile_sha256=ocr_profile.profile_sha256,
        cache_key=cache_key,
        layout_parser_version=ocr_profile.layout_parser_version,
        coordinate_transform_version=ocr_profile.coordinate_transform_version,
        raw_text=raw_text,
        raw_text_sha256=raw_text_sha256,
        normalized_text=raw_text,
        layout_sidecar_sha256=None,
        quality=quality,
        # Slice 4.3 only persists raw OCR. Risk scanning and its activation gate
        # belong to Slice 4.4; keep the contract field empty here.
        risk_items=[],
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        completed_at=completed_at,
    )


class TextOnlyOcrAdapter:
    """冻结 text-only 识别适配器：指纹、页级缓存与原始工件装配。

    任一本模块默认参数被替换都视为新的决定性输入：先构造适配器再使用，
    指纹/缓存键自动随之变化。
    """

    def __init__(
        self,
        *,
        provider: str = "omlx",
        model_id: str = "GLM-OCR-bf16",
        model_revision: str = "unknown",
        prompt: str = DEFAULT_PROMPT,
        parser_version: str = _PARSER_VERSION,
        render_params: dict[str, Any] | None = None,
        request_params: dict[str, Any] | None = None,
        segmentation_config: SegmentationConfig = DEFAULT_SEGMENTATION_CONFIG,
        layout_parser_version: str | None = None,
        coordinate_transform_version: str = COORDINATE_TRANSFORM_VERSION,
        profile_id: str | None = None,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.model_revision = model_revision
        self.prompt = prompt
        self.parser_version = parser_version
        self.render_params = render_params
        self.request_params = dict(
            DEFAULT_REQUEST_PARAMS if request_params is None else request_params
        )
        self.segmentation_config = segmentation_config
        self.layout_parser_version = layout_parser_version
        self.coordinate_transform_version = coordinate_transform_version
        self.prompt_sha256 = sha256(prompt.encode("utf-8")).hexdigest()
        self.render_params_sha256 = (
            canonical_hash(render_params) if render_params is not None else None
        )
        self.request_params_sha256 = canonical_hash(
            {
                "provider_request_params": self.request_params,
                "page_segmentation": segmentation_config.fingerprint_payload(),
            }
        )
        self.profile_fingerprint = build_profile_fingerprint(
            extraction_route=ExtractionRoute.VISION_OCR.value,
            provider=self.provider,
            model_id=self.model_id,
            model_revision=self.model_revision,
            prompt_sha256=self.prompt_sha256,
            parser_version=self.parser_version,
            render_params_sha256=self.render_params_sha256,
            request_params_sha256=self.request_params_sha256,
            layout_parser_version=self.layout_parser_version,
            coordinate_transform_version=self.coordinate_transform_version,
        )
        self.profile_id = profile_id or f"ocr-profile-{self.profile_fingerprint[:40]}"

    def profile(self, *, created_at: datetime | None = None) -> OCRProfile:
        """构建识别配置合同（指纹与身份字段一致，合同校验可复核）。"""
        return OCRProfile(
            ocr_profile_id=self.profile_id,
            profile_sha256=self.profile_fingerprint,
            extraction_route=ExtractionRoute.VISION_OCR,
            provider=self.provider,
            model_id=self.model_id,
            model_revision=self.model_revision,
            prompt_sha256=self.prompt_sha256,
            parser_version=self.parser_version,
            render_params_sha256=self.render_params_sha256,
            request_params_sha256=self.request_params_sha256,
            layout_parser_version=self.layout_parser_version,
            coordinate_transform_version=self.coordinate_transform_version,
            created_at=created_at or _now_utc(),
        )

    def cache_key(
        self,
        *,
        page_artifact_id: str,
        source_sha256: str,
        page_number: int,
        page_input_sha256: str,
    ) -> str:
        """页级缓存唯一键（v2：绑定页产物身份，任一决定性输入变化必然产生新键）。"""
        return build_ocr_cache_key(
            page_artifact_id=page_artifact_id,
            source_sha256=source_sha256,
            page_number=page_number,
            ocr_profile_sha256=self.profile_fingerprint,
            page_input_sha256=page_input_sha256,
            layout_parser_version=self.layout_parser_version,
            coordinate_transform_version=self.coordinate_transform_version,
        )

    def cached_page(
        self,
        session,
        *,
        cache_key: str,
        page_artifact_id: str,
        source_sha256: str,
        page_number: int,
        page_input_sha256: str,
    ) -> OCRPage | None:
        """校验过的缓存命中：不可变且只在本页产物身份内复用，绝不绕过内容/身份校验。

        仓储层已对同一缓存键全部行做完整镜像/Profile 闭包校验；此处再复核
        请求身份与命中行一致，防止缓存键空间漂移/投毒被当作命中。
        v2 缓存键已绑定 ``page_artifact_id``，命中行必然属于当前页产物；
        下面的身份复核是纵深防御。
        """
        hit = OcrPageRepository(session).get_successful_by_cache_key(cache_key)
        if hit is None:
            return None
        if hit.ocr_profile_sha256 != self.profile_fingerprint:
            raise OcrCacheIdentityError(
                "缓存命中页的识别配置指纹与请求不一致，拒绝命中"
            )
        if hit.page_input_sha256 != page_input_sha256:
            raise OcrCacheIdentityError(
                "缓存命中页的页输入哈希与请求不一致，拒绝命中"
            )
        if (
            hit.source_sha256 != source_sha256
            or hit.page_number != page_number
            or hit.page_artifact_id != page_artifact_id
        ):
            raise OcrCacheIdentityError(
                "缓存命中页的来源/页码/页产物与请求不一致，拒绝命中"
            )
        return hit

    def reusable_page(
        self,
        session,
        *,
        source_sha256: str,
        page_number: int,
        page_input_sha256: str,
    ) -> OCRPage | None:
        """内容级推理复用源（仅限 v2 键未命中后调用）：同内容身份的他版成功页。

        复用身份是设计书内容哈希缓存契约：内容哈希 + 页码 + 识别配置指纹 +
        实际页图输入哈希 + 布局/坐标变换版本；页产物绑定不参与。命中行的
        请求身份在此复核（纵深防御），仓储层已对全部候选行做完整镜像/闭包
        校验，漂移行暴露为 :class:`PersistedContractInvalid`，绝不静默复用。
        """
        hit = OcrPageRepository(session).get_latest_successful_by_content_identity(
            source_sha256=source_sha256,
            page_number=page_number,
            ocr_profile_sha256=self.profile_fingerprint,
            page_input_sha256=page_input_sha256,
            layout_parser_version=self.layout_parser_version,
            coordinate_transform_version=self.coordinate_transform_version,
        )
        if hit is None:
            return None
        if hit.ocr_profile_sha256 != self.profile_fingerprint:
            raise OcrCacheIdentityError(
                "内容复用页的识别配置指纹与请求不一致，拒绝复用"
            )
        if (
            hit.source_sha256 != source_sha256
            or hit.page_number != page_number
            or hit.page_input_sha256 != page_input_sha256
        ):
            raise OcrCacheIdentityError(
                "内容复用页的来源/页码/页输入与请求不一致，拒绝复用"
            )
        return hit

    def prepare(
        self,
        *,
        session,
        artifact_store: ArtifactStore,
        source_sha256: str,
        page_number: int,
        page_artifact_id: str,
        page_input_sha256: str,
        page_image_bytes: bytes,
        started_at: datetime | None = None,
    ) -> PreparedOcrRequest:
        """阶段 (a)：零推理准备 —— 构建/复用不可变 OCRProfile 与原始请求工件。

        不调用任何外部推理。worker_03 在同一事务提交本准备结果与请求检查点，
        然后在事务外经共享 oMLX 门禁排队推理；本方法只做确定性装配与内容寻址
        落盘（同输入同工件，可安全重放）。
        """
        started = started_at or _now_utc()
        profile = OCRProfileRepository(session).get_or_create(self.profile())
        cache_key = self.cache_key(
            page_artifact_id=page_artifact_id,
            source_sha256=source_sha256,
            page_number=page_number,
            page_input_sha256=page_input_sha256,
        )
        hit = self.cached_page(
            session,
            cache_key=cache_key,
            page_artifact_id=page_artifact_id,
            source_sha256=source_sha256,
            page_number=page_number,
            page_input_sha256=page_input_sha256,
        )
        # v2（页产物绑定）键未命中时，按设计书内容哈希契约寻找他版成功页作为
        # 内容级推理复用源；命中后 finalize 复制为本页产物自有新成功行。
        reused = (
            None
            if hit is not None
            else self.reusable_page(
                session,
                source_sha256=source_sha256,
                page_number=page_number,
                page_input_sha256=page_input_sha256,
            )
        )
        plan = segment_page_image(page_image_bytes, config=self.segmentation_config)
        prepared_segments: list[PreparedOcrSegment] = []
        for segment in plan.segments:
            request_payload = build_ocr_request_payload(
                profile=profile,
                source_sha256=source_sha256,
                page_number=page_number,
                page_input_sha256=page_input_sha256,
                image_bytes=segment.image_bytes,
                prompt=self.prompt,
                request_params=self.request_params,
            )
            if plan.dense:
                request_payload["segment"] = {
                    "algorithm_version": plan.algorithm_version,
                    "index": segment.index,
                    "row_index": segment.row_index,
                    "column_index": segment.column_index,
                    "x0": segment.x0,
                    "x1": segment.x1,
                    "y0": segment.y0,
                    "y1": segment.y1,
                    "crop_x0": segment.crop_x0,
                    "crop_x1": segment.crop_x1,
                    "crop_y0": segment.crop_y0,
                    "crop_y1": segment.crop_y1,
                    "page_width": plan.page_width,
                    "page_height": plan.page_height,
                }
            request_bytes = _canonical_json_bytes(request_payload)
            prepared_segments.append(
                PreparedOcrSegment(
                    index=segment.index,
                    row_index=segment.row_index,
                    column_index=segment.column_index,
                    x0=segment.x0,
                    x1=segment.x1,
                    y0=segment.y0,
                    y1=segment.y1,
                    crop_x0=segment.crop_x0,
                    crop_x1=segment.crop_x1,
                    crop_y0=segment.crop_y0,
                    crop_y1=segment.crop_y1,
                    image_bytes=segment.image_bytes,
                    image_sha256=segment.image_sha256,
                    request_payload=request_payload,
                    request_bytes=request_bytes,
                    request_artifact=_artifact_for_request(
                        session=session,
                        artifact_store=artifact_store,
                        request_bytes=request_bytes,
                        created_at=started,
                    ),
                )
            )
        segments = tuple(prepared_segments)
        if len(segments) == 1:
            request_payload = segments[0].request_payload
            request_bytes = segments[0].request_bytes
            request_artifact = segments[0].request_artifact
        else:
            request_payload = {
                "schema": _SEGMENTED_REQUEST_SCHEMA,
                "segmentation": plan.audit_payload(),
                "segments": [_segment_audit_payload(segment) for segment in segments],
            }
            request_bytes = _canonical_json_bytes(request_payload)
            request_artifact = _artifact_for_request(
                session=session,
                artifact_store=artifact_store,
                request_bytes=request_bytes,
                created_at=started,
            )
        return PreparedOcrRequest(
            profile=profile,
            cache_key=cache_key,
            source_sha256=source_sha256,
            page_number=page_number,
            page_artifact_id=page_artifact_id,
            page_input_sha256=page_input_sha256,
            page_image_bytes=page_image_bytes,
            request_payload=request_payload,
            request_bytes=request_bytes,
            request_artifact=request_artifact,
            segmentation_plan=plan,
            segments=segments,
            started_at=started,
            cached_page=hit,
            reused_page=reused,
        )

    def finalize_reuse(
        self,
        *,
        session,
        prepared: PreparedOcrRequest,
        artifact_store: ArtifactStore | None = None,
        persist: Callable[[OCRPage], object] | None = None,
    ) -> OcrRecognition:
        """内容级推理复用落地：把复用源成功页的识别文本写入**本页产物自有**新成功行。

        历史行不可改写：复用源行原样保留；新行携带当前页产物身份与当前 v2
        缓存键，因此冻结清单的跨产物完整性校验必然通过。无推理发生、无新
        响应工件（``cached=True``，原始响应仍由复用源行/尝试持有）。
        由 worker_03 在 ``commit_guard`` 事务内通过 ``persist`` 提交。
        """
        if prepared.cached_page is not None:
            return OcrRecognition(
                ocr_page=prepared.cached_page,
                cached=True,
                degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
                raw_request_artifact=prepared.request_artifact,
            )
        if prepared.reused_page is None:
            raise OcrAdapterError("内容级复用落地缺少复用源成功页")
        page = build_ocr_page(
            ocr_page_id=f"ocr-page-{uuid4().hex}",
            page_artifact_id=prepared.page_artifact_id,
            source_sha256=prepared.source_sha256,
            page_number=prepared.page_number,
            page_input_sha256=prepared.page_input_sha256,
            ocr_profile=prepared.profile,
            cache_key=prepared.cache_key,
            raw_text=prepared.reused_page.raw_text,
            status=OCRPageStatus.SUCCEEDED,
            started_at=prepared.started_at,
            completed_at=_now_utc(),
        )
        if persist is not None:
            persist(page)
        return OcrRecognition(
            ocr_page=page,
            cached=True,
            degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
            raw_request_artifact=prepared.request_artifact,
            reused_from_ocr_page_id=prepared.reused_page.ocr_page_id,
        )

    def finalize_success(
        self,
        *,
        session,
        artifact_store: ArtifactStore,
        prepared: PreparedOcrRequest,
        result: InferenceResult,
        persist: Callable[[OCRPage], object] | None = None,
    ) -> OcrRecognition:
        """阶段 (b) 成功：注入 ``InferenceResult`` -> 原始响应工件 + 不可变 OCRPage。

        原始响应内容寻址落盘（provider 原文不删改）；OCRPage 为确定性派生
        （同一响应字节 -> 同一响应哈希与文本）。由 worker_03 在
        ``commit_guard`` 事务内通过 ``persist`` 提交。
        """
        if prepared.cached_page is not None:
            return OcrRecognition(
                ocr_page=prepared.cached_page,
                cached=True,
                degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
                raw_request_artifact=prepared.request_artifact,
            )
        if prepared.reused_page is not None:
            return self.finalize_reuse(
                session=session,
                artifact_store=artifact_store,
                prepared=prepared,
                persist=persist,
            )
        response_artifact = self.persist_raw_response_artifact(
            session=session,
            artifact_store=artifact_store,
            raw_response=result.raw_response,
        )
        page = build_ocr_page(
            ocr_page_id=f"ocr-page-{uuid4().hex}",
            page_artifact_id=prepared.page_artifact_id,
            source_sha256=prepared.source_sha256,
            page_number=prepared.page_number,
            page_input_sha256=prepared.page_input_sha256,
            ocr_profile=prepared.profile,
            cache_key=prepared.cache_key,
            raw_text=result.recognized_text,
            status=OCRPageStatus.SUCCEEDED,
            started_at=prepared.started_at,
            completed_at=_now_utc(),
        )
        if persist is not None:
            persist(page)
        return OcrRecognition(
            ocr_page=page,
            cached=False,
            degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
            raw_request_artifact=prepared.request_artifact,
            raw_response_artifact=response_artifact,
        )

    def persist_raw_response_artifact(
        self,
        *,
        session,
        artifact_store: ArtifactStore,
        raw_response: bytes,
    ) -> RawOcrResponseArtifact:
        """保存已收到的 provider 原文，供成功和晚到审计路径共同复用。"""
        response_sha256 = sha256(raw_response).hexdigest()
        response_artifact = RawOcrResponseArtifact(
            raw_response_artifact_id=f"raw-resp-{response_sha256[:40]}",
            sha256=response_sha256,
            storage_ref=artifact_store.put("raw_response", raw_response).storage_ref,
            provider=self.provider,
            model_id=self.model_id,
            model_revision=self.model_revision,
            created_at=_now_utc(),
        )
        RawOcrResponseArtifactRepository(session).get_or_create(response_artifact)
        return response_artifact

    def finalize_failure(
        self,
        *,
        session,
        prepared: PreparedOcrRequest,
        failure: OcrFailure,
        artifact_store: ArtifactStore | None = None,
        persist: Callable[[OCRPage], object] | None = None,
    ) -> OcrRecognition:
        """阶段 (b) 失败：净化失败描述 -> 不可变 FAILED OCRPage。

        ``failure.reason`` 必须是稳定中文领域措辞；异常类名、provider 原文、
        stderr、密钥等细节由 worker_03 写入尝试/任务技术记录。若 provider 已返回
        原始字节，则通过 ``artifact_store`` 另存为不可变响应工件；失败行追加写，
        不进入成功缓存。
        """
        if prepared.cached_page is not None:
            return OcrRecognition(
                ocr_page=prepared.cached_page,
                cached=True,
                degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
                raw_request_artifact=prepared.request_artifact,
            )
        if prepared.reused_page is not None:
            # 复用落地后不存在推理失败：结果已定，只返回既定复用结果，
            # 绝不写失败页、也绝不在此重复落地成功行（提交属成功路径）。
            return self.finalize_reuse(
                session=session,
                prepared=prepared,
                artifact_store=artifact_store,
            )
        raw_response_artifact: RawOcrResponseArtifact | None = None
        if failure.raw_response is not None and artifact_store is not None:
            raw_response_artifact = self.persist_raw_response_artifact(
                session=session,
                artifact_store=artifact_store,
                raw_response=failure.raw_response,
            )
        page = build_ocr_page(
            ocr_page_id=f"ocr-page-{uuid4().hex}",
            page_artifact_id=prepared.page_artifact_id,
            source_sha256=prepared.source_sha256,
            page_number=prepared.page_number,
            page_input_sha256=prepared.page_input_sha256,
            ocr_profile=prepared.profile,
            cache_key=prepared.cache_key,
            raw_text="",
            status=OCRPageStatus.FAILED,
            failure_reason=failure.reason,
            started_at=prepared.started_at,
            completed_at=_now_utc(),
        )
        if persist is not None:
            persist(page)
        return OcrRecognition(
            ocr_page=page,
            cached=False,
            degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
            raw_request_artifact=prepared.request_artifact,
            raw_response_artifact=raw_response_artifact,
            technical_detail=failure.technical_detail,
        )

    def recognize(
        self,
        *,
        session,
        artifact_store: ArtifactStore,
        source_sha256: str,
        page_number: int,
        page_artifact_id: str,
        page_input_sha256: str,
        page_image_bytes: bytes,
        inference: Callable[[dict[str, Any], bytes], InferenceResult],
        persist: Callable[[OCRPage], object] | None = None,
        started_at: datetime | None = None,
    ) -> OcrRecognition:
        """便捷组合：prepare（零推理）-> 注入推理 -> finalize；语义不变。

        ``inference`` 由调用方注入：worker_03 用共享 oMLX 门禁租约包住它。
        ``persist`` 由调用方注入（worker_03 用 ``commit_guard`` 同事务提交；
        未注入则不落 OCRPage，只返回合同）。推理异常统一转为稳定中文失败文本，
        技术细节归 worker_03 尝试记录。
        """
        prepared = self.prepare(
            session=session,
            artifact_store=artifact_store,
            source_sha256=source_sha256,
            page_number=page_number,
            page_artifact_id=page_artifact_id,
            page_input_sha256=page_input_sha256,
            page_image_bytes=page_image_bytes,
            started_at=started_at,
        )
        if prepared.cached_page is not None:
            return OcrRecognition(
                ocr_page=prepared.cached_page,
                cached=True,
                degradation_reason=TEXT_ONLY_DEGRADATION_REASON,
                raw_request_artifact=prepared.request_artifact,
            )
        if prepared.reused_page is not None:
            # 内容级推理复用：同一内容+识别配置已有成功结果，不再发起推理。
            return self.finalize_reuse(
                session=session,
                prepared=prepared,
                artifact_store=artifact_store,
                persist=persist,
            )
        completed: list[tuple[PreparedOcrSegment, InferenceResult, dict[str, Any]]] = []
        try:
            for segment in prepared.segments:
                segment_result = inference(segment.request_payload, segment.image_bytes)
                completed.append((segment, segment_result, {}))
            result, _ = combine_segment_results(prepared, completed)
        except Exception as exc:  # noqa: BLE001 - 推理失败统一转为稳定中文失败文本
            failed_segment = prepared.segments[len(completed)]
            provider_raw = getattr(exc, "raw_response", None)
            raw_response = provider_raw
            if len(prepared.segments) > 1:
                raw_response = composite_segment_failure_response(
                    prepared,
                    completed,
                    failed_segment=failed_segment,
                    failed_raw_response=provider_raw,
                )
            return self.finalize_failure(
                session=session,
                prepared=prepared,
                failure=OcrFailure(
                    category=OcrFailureCategory.UNKNOWN,
                    reason=INFERENCE_FAILURE_REASON,
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    raw_response=raw_response,
                ),
                artifact_store=artifact_store,
                persist=persist,
            )
        return self.finalize_success(
            session=session,
            artifact_store=artifact_store,
            prepared=prepared,
            result=result,
            persist=persist,
        )
