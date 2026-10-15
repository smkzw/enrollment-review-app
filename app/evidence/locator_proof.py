"""确定性定位真实性证明读取器（WP-44A）。

定位的 bbox/文本范围必须由与来源文本同源的**内容寻址工件**证明，不能只靠自报的
页尺寸、任意 64 位哈希或镜像列。本模块提供从 ``ArtifactStore`` 读取原生文本与
原生坐标 sidecar、解析其确定性 schema、并依据字符偏移映射确定性重算目标 bbox
的能力。定位仓储用它回读工件字节后重算/回验，再决定是否放行 authenticated bbox。

- ``native_text``            原生 PDF 文本工件（UTF-8 字节，内容寻址）；
- ``native_coordinates``      ``serialize_native_coordinates`` 输出的
                              ``native_coordinates/v1`` JSON（字符/词坐标）。

``raw_ocr`` 路线当前没有持久化的机器坐标 sidecar（text-only），因此原始 OCR 的
bbox 一律无法证明，必须拒绝/诚实降级，绝不输出红框工件。
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.domain.contracts.enums import CoordinateSpace
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import CoordinateFrame
from app.evidence.artifacts import ArtifactStore, ArtifactStoreError
from app.evidence.coordinates import pdf_points_to_image_pixels

NATIVE_COORDINATES_SCHEMA = "native_coordinates/v1"

#: bbox 重算时允许的浮点容差（points/像素）。
_BBOX_TOLERANCE = 1e-6


class LocatorProofError(RuntimeError):
    """定位真实性证明失败（工件缺失/漂移/无法重算/越界）。"""


@dataclass(frozen=True)
class NativeChar:
    """原生坐标 sidecar 中的一个字符：文本、起始偏移、PDF points bbox。"""

    text: str
    start: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class NativeCoordinateSidecar:
    """解析后的原生坐标 sidecar（``native_coordinates/v1``）。"""

    schema: str
    page_number: int
    page_width: float
    page_height: float
    rotation: int
    text: str
    chars: tuple[NativeChar, ...]

    def chars_in_range(self, start: int, end: int) -> tuple[NativeChar, ...]:
        return tuple(
            c
            for c in self.chars
            if c.start < end and c.start + len(c.text) > start
        )


def parse_native_coordinates(payload: bytes) -> NativeCoordinateSidecar:
    """解析并校验 ``native_coordinates/v1`` 工件字节为确定性 sidecar。"""
    import json

    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocatorProofError(f"原生坐标工件不是合法 UTF-8 JSON：{exc}") from exc
    if data.get("schema") != NATIVE_COORDINATES_SCHEMA:
        raise LocatorProofError(
            f"原生坐标工件 schema 必须是 {NATIVE_COORDINATES_SCHEMA}，"
            f"得到 {data.get('schema')!r}"
        )
    try:
        chars = tuple(
            NativeChar(
                text=str(c["text"]),
                start=int(c["start"]),
                x0=float(c["x0"]),
                y0=float(c["y0"]),
                x1=float(c["x1"]),
                y1=float(c["y1"]),
            )
            for c in data["chars"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LocatorProofError(f"原生坐标工件缺少或类型错误的字段：{exc}") from exc
    return NativeCoordinateSidecar(
        schema=data["schema"],
        page_number=int(data["page_number"]),
        page_width=float(data["page_width"]),
        page_height=float(data["page_height"]),
        rotation=int(data["rotation"]),
        text=str(data["text"]),
        chars=chars,
    )


class LocatorProofReader:
    """从 ArtifactStore 读取并校验原生文本/坐标工件，按字符映射重算 bbox。"""

    def __init__(self, artifact_store: ArtifactStore) -> None:
        if artifact_store is None:
            raise LocatorProofError("定位真实性证明需要内容寻址 ArtifactStore")
        self._store = artifact_store

    def native_text(self, digest: str) -> str:
        """读取 ``native_text/<sha>`` 字节，校验内容哈希并解码 UTF-8。"""
        try:
            payload = self._store.read_by_sha("native_text", digest)
        except ArtifactStoreError as exc:
            raise LocatorProofError(f"原生文本工件读取失败：{exc}") from exc
        if sha256(payload).hexdigest() != digest:
            raise LocatorProofError("原生文本工件内容哈希与引用不一致")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LocatorProofError("原生文本工件不是合法 UTF-8") from exc

    def native_coordinates(self, digest: str) -> NativeCoordinateSidecar:
        """读取 ``native_coordinates/<sha>`` 字节，校验内容哈希并解析 schema。"""
        try:
            payload = self._store.read_by_sha("native_coordinates", digest)
        except ArtifactStoreError as exc:
            raise LocatorProofError(f"原生坐标工件读取失败：{exc}") from exc
        if sha256(payload).hexdigest() != digest:
            raise LocatorProofError("原生坐标工件内容哈希与引用不一致")
        return parse_native_coordinates(payload)

    @staticmethod
    def recompute_bbox(
        sidecar: NativeCoordinateSidecar,
        *,
        text_start: int,
        text_end: int,
        frame: CoordinateFrame,
        pixels_per_point: float | None = None,
    ) -> BoundingBox:
        """把 ``[text_start, text_end)`` 的字符映射到 bbox。

        原生坐标是 PDF points（原点左下、y 向上）。若 ``frame.space`` 是
        ``page_image_pixels``，则用 ``pdf_points_to_image_pixels`` 换算到页图像素；
        否则要求 PDF points 坐标系。只允许唯一字符范围（不取第一处/最近处）。
        """
        if not (0 <= text_start < text_end <= len(sidecar.text)):
            raise LocatorProofError("目标文本范围越出原生坐标 sidecar 的文本")
        chars = sidecar.chars_in_range(text_start, text_end)
        if not chars:
            raise LocatorProofError("目标范围没有任何原生坐标字符，无法证明 bbox")
        # 字符并集 bbox 必须逐字符覆盖目标范围（不允许间隙/越界）。
        pdf_bbox = BoundingBox(
            x0=min(c.x0 for c in chars),
            y0=min(c.y0 for c in chars),
            x1=max(c.x1 for c in chars),
            y1=max(c.y1 for c in chars),
        )
        if frame.space == CoordinateSpace.PAGE_IMAGE_PIXELS:
            if pixels_per_point is None or pixels_per_point <= 0:
                raise LocatorProofError(
                    "page_image_pixels bbox 必须提供正的 pixels_per_point 才能证明"
                )
            pdf_frame = CoordinateFrame(
                space=CoordinateSpace.PDF_POINTS,
                page_width=sidecar.page_width,
                page_height=sidecar.page_height,
                rotation=sidecar.rotation,
                transform_version=frame.transform_version,
            )
            converted = pdf_points_to_image_pixels(
                pdf_bbox, pdf_frame, pixels_per_point=pixels_per_point
            )
            if (
                converted.x1 > frame.page_width + 1
                or converted.y1 > frame.page_height + 1
            ):
                raise LocatorProofError("换算后的区域坐标越出页图像素范围")
            return converted
        if frame.space != CoordinateSpace.PDF_POINTS:
            raise LocatorProofError(f"不支持的坐标空间 {frame.space.value}")
        return pdf_bbox

    @staticmethod
    def bbox_matches(
        recomputed: BoundingBox, claimed: BoundingBox, tolerance: float = _BBOX_TOLERANCE
    ) -> bool:
        """重算 bbox 与声明的 bbox 必须在容差内一致。"""
        return (
            abs(recomputed.x0 - claimed.x0) <= tolerance
            and abs(recomputed.y0 - claimed.y0) <= tolerance
            and abs(recomputed.x1 - claimed.x1) <= tolerance
            and abs(recomputed.y1 - claimed.y1) <= tolerance
        )
