"""确定性证据定位器：区域坐标 > 文本范围 > 页内摘录 > 仅页码。

定位精度由确定性算法判定，Agent 无权提升精度。重复文本无法稳定消歧时
按 ``page_excerpt`` 降级并说明原因，绝不生成伪精确高亮。

Slice 4.4（WP-44B）扩展：occurrence-aware 身份与诚实文本定位决策。

- ``occurrence_locator_id``  定位身份按「页工件 + 来源层 + 来源文本哈希 + 精度 +
  原始字符范围 / 摘录锚点 + 坐标 sidecar + 算法版本」确定性计算，不再只按
  “页 + 规范化目标字符串”生成会碰撞的 ID（§4.2 重复文本规则）；
- ``locate_in_text``         对绑定来源文本做诚实精度决策：有可信原始范围时直接
  定位该 occurrence（TEXT_RANGE）；只有目标字符串时按出现次数决定
  TEXT_RANGE / PAGE_EXCERPT（重复降级）/ PAGE_ONLY（未找到）。禁止“取第一处”
  “取最近处”“按阅读顺序猜测”。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import TypedDict

from app.domain.contracts.enums import (
    CoordinateSpace,
    DisambiguationOutcome,
    LocatorPrecision,
    LocatorSourceLayer,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.ocr import CoordinateFrame, LocatorResult
from app.evidence.coordinates import COORDINATE_TRANSFORM_VERSION
from app.evidence.pdf_native import NativeChar, NativePage

LOCATOR_ALGORITHM_VERSION = "slice4.0/v1"
#: WP-44B occurrence-aware 定位身份算法版本（与 Slice 4.0 的 ``_locator_id`` 区分）。
OCCURRENCE_LOCATOR_ALGORITHM_VERSION = "slice4.4/v1"


class _LocatorCommon(TypedDict):
    locator_id: str
    locator_algorithm_version: str
    source_text_sha256: str
    page_artifact_id: str
    anchor_hash: str


def _normalized(value: str) -> str:
    return "".join(value.split())


def find_all_whitespace_insensitive(text: str, target: str) -> list[tuple[int, int]]:
    """在 ``text`` 中查找 ``target`` 的所有忽略空白匹配，返回原文 ``(start, end)`` 区间。"""
    needle = _normalized(target)
    if not needle:
        return []
    results: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        j = i
        k = 0
        last = j
        while j < n and k < len(needle):
            if text[j].isspace():
                j += 1
                continue
            if text[j] != needle[k]:
                break
            last = j + 1
            j += 1
            k += 1
        if k == len(needle):
            results.append((i, last))
            # 继续从下一个原文字符起点搜索，不能跳到当前命中末尾；否则
            # ``AAA`` 中的 ``AA`` 只会返回第一处并被误判为唯一 occurrence。
            i += 1
        else:
            i += 1
    return results


def _union_bbox(chars: Iterable[NativeChar]) -> BoundingBox:
    char_list = list(chars)
    if not char_list:
        raise ValueError("没有可用字符无法计算 bbox")
    return BoundingBox(
        x0=min(c.x0 for c in char_list),
        y0=min(c.y0 for c in char_list),
        x1=max(c.x1 for c in char_list),
        y1=max(c.y1 for c in char_list),
    )


def _locator_id(target: str, page_artifact_id: str | None, version: str) -> str:
    digest = sha256(
        f"{version}|{page_artifact_id or ''}|{_normalized(target)}".encode()
    ).hexdigest()
    return f"locator-{digest[:32]}"


def locate_target(
    native_page: NativePage,
    target_text: str,
    *,
    source_text_sha256: str,
    page_artifact_id: str,
    locator_version: str = LOCATOR_ALGORITHM_VERSION,
    transform_version: str = COORDINATE_TRANSFORM_VERSION,
) -> LocatorResult:
    """在原生页上定位目标文本并返回诚实精度结果。

    ``source_text_sha256`` and ``page_artifact_id`` are mandatory even for a
    degraded result: a page-only result must still be replayable against the
    exact source page and text revision that was inspected.
    """
    expected_source_hash = sha256(native_page.text.encode("utf-8")).hexdigest()
    if source_text_sha256 != expected_source_hash:
        raise ValueError("定位来源文本哈希与实际页文本不一致")
    occurrences = find_all_whitespace_insensitive(native_page.text, target_text)
    common: _LocatorCommon = {
        "locator_id": _locator_id(target_text, page_artifact_id, locator_version),
        "locator_algorithm_version": locator_version,
        "source_text_sha256": source_text_sha256,
        "page_artifact_id": page_artifact_id,
        "anchor_hash": sha256(_normalized(target_text).encode("utf-8")).hexdigest(),
    }

    if not occurrences:
        return LocatorResult(
            precision=LocatorPrecision.PAGE_ONLY,
            disambiguation=DisambiguationOutcome.NOT_FOUND,
            match_confidence=0.0,
            degradation_reason="目标文本未在原生文本中找到",
            **common,
        )

    if len(occurrences) > 1:
        return LocatorResult(
            precision=LocatorPrecision.PAGE_EXCERPT,
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
            excerpt=target_text,
            match_confidence=0.0,
            degradation_reason="多处相同文本无法稳定消歧，降级为页内摘录，不生成伪精确高亮",
            **common,
        )

    start, end = occurrences[0]
    chars = native_page.chars_in_range(start, end)
    if chars:
        bbox = _union_bbox(chars)
        frame = CoordinateFrame(
            space=CoordinateSpace.PDF_POINTS,
            page_width=native_page.page_width,
            page_height=native_page.page_height,
            rotation=native_page.rotation,
            transform_version=transform_version,
        )
        return LocatorResult(
            precision=LocatorPrecision.BBOX,
            coordinate_frame=frame,
            bbox=bbox,
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            excerpt=target_text,
            match_confidence=1.0,
            **common,
        )

    # 唯一命中但无可用字符坐标：诚实降级到文本范围。
    return LocatorResult(
        precision=LocatorPrecision.TEXT_RANGE,
        text_start=start,
        text_end=end,
        disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
        excerpt=target_text,
        match_confidence=1.0,
        **common,
    )


def occurrence_locator_id(
    *,
    page_artifact_id: str,
    source_layer: LocatorSourceLayer,
    source_text_sha256: str,
    precision: LocatorPrecision,
    target_id: str,
    text_start: int | None = None,
    text_end: int | None = None,
    sidecar_sha256: str | None = None,
    anchor_hash: str | None = None,
    disambiguation: DisambiguationOutcome = DisambiguationOutcome.UNIQUE_MATCH,
    degradation_reason: str | None = None,
    locator_algorithm_version: str = OCCURRENCE_LOCATOR_ALGORITHM_VERSION,
) -> str:
    """计算 occurrence-aware 定位身份的确定性 ID。

    身份至少包含页工件、来源层、来源文本哈希、精度、目标身份与算法版本，并按
    精度附加区分字段（§4.2 定位身份）：

    - ``bbox``/``text_range``  绑定具体原始字符范围（occurrence 身份），bbox 另加
      同源坐标 sidecar 哈希；同页两处相同文本以不同范围各自定位、互不碰撞；
    - ``page_excerpt``         绑定可回放摘录锚点哈希 + 消歧结果（不同摘录不碰撞）；
    - ``page_only``            绑定稳定目标身份 + 消歧/降级证明（不同目标不碰撞）。

    拒绝调用方自报任意 ID：所有身份输入都由本函数确定性内容寻址。
    """
    if precision in (LocatorPrecision.BBOX, LocatorPrecision.TEXT_RANGE):
        if text_start is None or text_end is None:
            raise ValueError("bbox/text_range 定位身份必须绑定具体原始字符范围")
        if text_end <= text_start:
            raise ValueError("定位身份字符范围必须有效")
        material = {
            "anchor": "occurrence/v1",
            "page_artifact_id": page_artifact_id,
            "source_layer": source_layer.value,
            "source_text_sha256": source_text_sha256,
            "precision": precision.value,
            "text_start": text_start,
            "text_end": text_end,
            "sidecar_sha256": sidecar_sha256,
            "locator_algorithm_version": locator_algorithm_version,
        }
    elif precision == LocatorPrecision.PAGE_EXCERPT:
        if anchor_hash is None:
            raise ValueError("page_excerpt 定位身份必须携带可回放摘录锚点哈希")
        material = {
            "anchor": "occurrence-excerpt/v1",
            "page_artifact_id": page_artifact_id,
            "source_layer": source_layer.value,
            "source_text_sha256": source_text_sha256,
            "precision": precision.value,
            "anchor_hash": anchor_hash,
            "disambiguation": disambiguation.value,
            "locator_algorithm_version": locator_algorithm_version,
        }
    elif precision == LocatorPrecision.PAGE_ONLY:
        material = {
            "anchor": "occurrence-page/v1",
            "page_artifact_id": page_artifact_id,
            "source_layer": source_layer.value,
            "source_text_sha256": source_text_sha256,
            "precision": precision.value,
            "target_id": target_id,
            "disambiguation": disambiguation.value,
            "degradation_reason": degradation_reason,
            "locator_algorithm_version": locator_algorithm_version,
        }
    else:
        raise ValueError(f"未知定位精度 {precision.value}")
    from app.domain.publication import canonical_hash

    return f"locator-{canonical_hash(material)[:32]}"


@dataclass(frozen=True)
class TextLocateDecision:
    """对绑定来源文本的一次诚实定位决策（不含坐标；坐标证明由调用方/仓储完成）。"""

    precision: LocatorPrecision
    disambiguation: DisambiguationOutcome
    text_start: int | None = None
    text_end: int | None = None
    excerpt: str | None = None
    match_confidence: float = 0.0
    degradation_reason: str | None = None


def locate_in_text(
    text: str,
    *,
    excerpt: str,
    text_start: int | None = None,
    text_end: int | None = None,
) -> TextLocateDecision:
    """对绑定来源文本做诚实精度决策。

    - 有可信原始范围 ``[text_start, text_end)``：范围必须有效且摘录逐字等于该范围，
      直接定位该 occurrence（``TEXT_RANGE``，``UNIQUE_MATCH``）——这是
      occurrence-aware 定位，不猜第一处/最近处；
    - 只有目标字符串：``find_all_whitespace_insensitive`` 统计出现次数——
      恰好 1 次 → ``TEXT_RANGE``；多次 → ``PAGE_EXCERPT``（重复文本降级，说明原因）；
      0 次 → ``PAGE_ONLY``（未找到）。
    """
    if not excerpt and text_start is None and text_end is None:
        raise ValueError("定位必须提供摘录文本或原始字符范围")
    if text_start is not None or text_end is not None:
        if text_start is None or text_end is None or not (0 <= text_start < text_end <= len(text)):
            raise ValueError("occurrence 定位范围必须有效且位于绑定文本内")
        derived = text[text_start:text_end]
        if excerpt and text[text_start:text_end] != excerpt:
            raise ValueError(
                "occurrence 定位摘录必须逐字等于绑定文本对应范围"
            )
        excerpt = excerpt or derived
        return TextLocateDecision(
            precision=LocatorPrecision.TEXT_RANGE,
            disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
            text_start=text_start,
            text_end=text_end,
            excerpt=excerpt,
            match_confidence=1.0,
        )
    occurrences = find_all_whitespace_insensitive(text, excerpt)
    if not occurrences:
        return TextLocateDecision(
            precision=LocatorPrecision.PAGE_ONLY,
            disambiguation=DisambiguationOutcome.NOT_FOUND,
            match_confidence=0.0,
            degradation_reason="目标文本未在绑定来源文本中找到，只定位到页面",
        )
    if len(occurrences) > 1:
        return TextLocateDecision(
            precision=LocatorPrecision.PAGE_EXCERPT,
            disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
            excerpt=excerpt,
            match_confidence=0.0,
            degradation_reason="多处相同文本无法稳定消歧，降级为页内摘录，不生成伪精确高亮",
        )
    start, end = occurrences[0]
    return TextLocateDecision(
        precision=LocatorPrecision.TEXT_RANGE,
        disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
        text_start=start,
        text_end=end,
        excerpt=excerpt,
        match_confidence=1.0,
    )
