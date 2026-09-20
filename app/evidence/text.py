"""TXT 证据解码（确定性纯函数）。

按设计固定顺序尝试解码：UTF-8 -> UTF-8-SIG -> GB18030；记录实际编码。
解码保留原始行序；显示分页在 paging/render 中完成，只允许文本范围/摘录定位。
"""
from __future__ import annotations

from dataclasses import dataclass

_TEXT_DECODE_ORDER = ("utf-8", "utf-8-sig", "gb18030")


@dataclass(frozen=True)
class DecodedText:
    text: str
    encoding: str


class TextDecodeError(ValueError):
    """字节无法按固定顺序解码为文本。"""


def decode_text_bytes(payload: bytes) -> DecodedText:
    last_error: UnicodeDecodeError | None = None
    for encoding in _TEXT_DECODE_ORDER:
        try:
            return DecodedText(text=payload.decode(encoding), encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise TextDecodeError(f"字节无法按 UTF-8/UTF-8-SIG/GB18030 顺序解码: {last_error}")
