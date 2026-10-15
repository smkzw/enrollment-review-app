"""Slice 4.4 有效文本确定性投影引擎（WP-44B）。

把「不可变原 OCR + 完整处理修订所选的非重叠校对链头」确定性投影为有效文本层：

- 所有校对都锚定同一不可变 ``raw_text``（``raw_text_sha256`` + 原始字符范围），
  绝不锚定前一版 effective text，避免字符偏移逐版漂移（§4.4 规则 1）；
- 投影按原始 offset 确定性应用并重算 ``effective_text_sha256``；读取时每次重算
  核对，从不链式沿用旧投影（§4.4 规则 4）；
- 两个有效校对范围重叠但无显式替代时拒绝投影（§4.4 规则 3；显式 supersede 由
  ``CorrectionRepository`` 保证同一 occurrence 单链，本引擎再兜底拒绝重叠）；
- 本模块是纯函数，不访问数据库/存储/工件：它只接受 raw text 与选中的
  ``CorrectionRecord`` 集合，输出投影文本与内容哈希。仓储/服务负责从完整修订
  读取校正集合并调用本引擎回验（effective_text 定位 / 页面读取）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from app.domain.contracts.evidence_locator import (
    CorrectionRecord,
    validate_correction_source_anchor,
)

__all__ = [
    "EffectiveTextProjection",
    "ProjectionOverlapError",
    "correction_anchors_conflict",
    "project_effective_text",
]


class ProjectionOverlapError(ValueError):
    """两个有效校对范围重叠且无显式替代，投影被拒绝。"""


@dataclass(frozen=True)
class EffectiveTextProjection:
    """一次有效文本投影：文本、内容哈希与按原始 offset 排序的已应用校对。"""

    effective_text: str
    effective_text_sha256: str
    applied: tuple[CorrectionRecord, ...]

    @property
    def is_empty(self) -> bool:
        return not self.applied


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise ValueError(f"无效的 raw_text_sha256：{value!r}")


def correction_anchors_conflict(left: CorrectionRecord, right: CorrectionRecord) -> bool:
    """同页两个有效来源锚点是否冲突。

    两个零长度插入不得占用同一位置；插入位于替换范围内部时冲突，
    但在替换范围起点或终点时属于相邻操作，可确定性共存。
    """
    if left.ocr_page_id != right.ocr_page_id:
        return False
    left_insert = left.text_start == left.text_end
    right_insert = right.text_start == right.text_end
    if left_insert and right_insert:
        return left.text_start == right.text_start
    return left.text_start < right.text_end and right.text_start < left.text_end


def project_effective_text(
    raw_text: str,
    corrections: Iterable[CorrectionRecord],
) -> EffectiveTextProjection:
    """投影原 OCR + 所选校对为有效文本并计算内容哈希。

    :param raw_text: 不可变 ``OCRPage.raw_text``（调用方必须从不可变 OCR 页读取）。
    :param corrections: 完整处理修订选中的有效校对集合（链头、无重叠、关键变化
        已完成二次确认——确认门禁由完整修订闭包执行，本引擎只做投影与锚定校验）。
    :raises ProjectionOverlapError: 校对范围越界/原文本不匹配/两个范围重叠。
    """
    raw_sha = sha256(raw_text.encode("utf-8")).hexdigest()
    selected = list(corrections)
    for item in selected:
        if not isinstance(item, CorrectionRecord):
            raise TypeError("投影引擎只接受 CorrectionRecord 校对记录")
        _require_sha256(item.raw_text_sha256)
        if item.raw_text_sha256 != raw_sha:
            raise ProjectionOverlapError(
                f"校对 {item.correction_id} 锚定的 raw_text_sha256 与投影源文本不一致，"
                "校对必须锚定同一不可变原 OCR"
            )
        try:
            validate_correction_source_anchor(
                raw_text,
                text_start=item.text_start,
                text_end=item.text_end,
                original_text=item.original_text,
            )
        except ValueError as error:
            raise ProjectionOverlapError(
                f"校对 {item.correction_id} 的来源锚点无效：{error}，拒绝投影"
            ) from error
        if item.corrected_text == item.original_text:
            raise ProjectionOverlapError(
                f"校对 {item.correction_id} 必须改变文本（原合同已禁止无变化记录）"
            )

    ordered = sorted(selected, key=lambda c: (c.text_start, c.text_end, c.correction_id))
    for index in range(1, len(ordered)):
        prev, current = ordered[index - 1], ordered[index]
        if correction_anchors_conflict(prev, current):
            raise ProjectionOverlapError(
                f"校对 {prev.correction_id} 与 {current.correction_id} 的原始范围重叠"
                "且无显式替代，拒绝投影"
            )

    parts: list[str] = []
    cursor = 0
    for item in ordered:
        parts.append(raw_text[cursor : item.text_start])
        parts.append(item.corrected_text)
        cursor = item.text_end
    parts.append(raw_text[cursor:])
    effective_text = "".join(parts)
    return EffectiveTextProjection(
        effective_text=effective_text,
        effective_text_sha256=sha256(effective_text.encode("utf-8")).hexdigest(),
        applied=tuple(ordered),
    )
