"""Isolated transcript comparison; matching text never approves a clinical fact.

The OCR adapter has no verified pixel coordinates. Logical rows and uniquely
labelled values can be compared, but they cannot establish field-level position.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
import re

from app.domain.contracts.local_region_read import LocalRegionReadCandidate
from app.domain.page_normalization import normalize_scalar, normalize_text, source_arrow_marks


REGION_COMPARISON_VERSION = "local-region-transcript-comparison/v3"

_TABLE_COLUMN_NAMES = (
    frozenset({"项目", "名称", "项目名称", "检验项目"}),
    frozenset({"结果", "检验结果", "测定结果"}),
    frozenset({"参考范围", "参考区间", "参考值"}),
    frozenset({"单位", "结果单位"}),
)


@dataclass(frozen=True)
class RegionOcrField:
    label: str
    raw_value: str
    raw_unit: str | None
    reference_text: str | None
    excerpt: str


class _TableReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.unsupported = False
        self.table_depth = 0
        self.outside = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_depth += 1
            self.unsupported |= self.table_depth > 1
        if tag == "tr":
            self.unsupported |= self.row is not None
            self.row = []
        if tag in {"td", "th"}:
            self.unsupported |= self.cell is not None or self.row is None
            self.unsupported |= any(k in {"rowspan", "colspan"} and v != "1" for k, v in attrs)
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif data.strip():
            self.outside.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.table_depth -= 1


def region_ocr_fields(text: str) -> tuple[list[RegionOcrField], list[str]]:
    if "<table" in text.lower():
        reader = _TableReader()
        reader.feed(text)
        reader.close()
        if (reader.unsupported or reader.table_depth or reader.row is not None or reader.cell is not None
                or not reader.rows):
            return [], ["表格有合并、嵌套或未完整读取，暂不能逐项对应。"]
        header = [normalize_text(cell) for cell in reader.rows[0]]
        matched_columns = [[index for index, name in enumerate(header) if name in aliases]
                           for aliases in _TABLE_COLUMN_NAMES]
        if any(len(matches) != 1 for matches in matched_columns):
            return [], ["表格列名不能明确对应，暂不推断各列含义。"]
        positions = [matches[0] for matches in matched_columns]
        fields, unresolved = [], ["表格之外尚有未对应文字：" + value for value in reader.outside]
        for row in reader.rows[1:]:
            if len(row) != len(header):
                unresolved.append("一行的列数与表头不一致，未采用相邻行填补。")
                continue
            label, value, reference, unit = [row[index] for index in positions]
            for index, cell in enumerate(row):
                if index not in positions and cell.strip():
                    unresolved.append("表格其他列尚未对应：" + header[index] + "：" + cell)
            if not label or not value:
                unresolved.append("一行缺少明确项目或结果，暂不能对应。")
                continue
            fields.append(RegionOcrField(label, value, unit or None, reference or None, " | ".join(row)))
        return fields, unresolved
    # Explicit labelled numeric/date values only. Free prose and handwriting are
    # retained by the read receipt, never guessed into labelled measurements.
    pattern = re.compile(
        r"(?P<label>[^:：\n]+)[:：]\s*(?P<value>"
        r"\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?"
        r"|[+-]?\d+(?:\.\d+)?(?:\s*[%\w\u4e00-\u9fff⁹¹²/×^+\-⁻]+)?)"
    )
    matches = list(pattern.finditer(text))
    fields = [RegionOcrField(match["label"].strip(), match["value"], None, None, match[0]) for match in matches]
    leftovers, end = [], 0
    for match in matches:
        if text[end:match.start()].strip():
            leftovers.append(text[end:match.start()].strip())
        end = match.end()
    if text[end:].strip():
        leftovers.append(text[end:].strip())
    gaps = ["仍有未对应的文字：" + value for value in leftovers]
    if not fields:
        gaps.append("文字主读没有可明确对应的项目和值，仍需原件核对。")
    return fields, gaps


def _scalar(value: str, unit: str | None) -> tuple[str, str | None]:
    normalized, embedded_unit = normalize_scalar(value)
    separate_unit = (normalize_scalar("1" + unit)[1] or normalize_text(unit)) if unit else None
    if embedded_unit and separate_unit and embedded_unit != separate_unit:
        raise ValueError("同一次读取的值与单位互相矛盾")
    return normalized, separate_unit or embedded_unit


def compare_local_region_read(ocr_text: str, candidate: LocalRegionReadCandidate) -> dict:
    fields, unresolved = region_ocr_fields(ocr_text)
    ocr_counts = Counter(normalize_text(field.label) for field in fields)
    visual_counts = Counter(normalize_text(item.label) for item in candidate.items if item.label)
    outcomes = []
    for item in candidate.items:
        reasons = []
        label = normalize_text(item.label)
        matches = [field for field in fields if normalize_text(field.label) == label]
        if item.script != "printed" or item.legibility != "clear":
            reasons.append("字迹或对应对象尚未核实")
        if not label or ocr_counts[label] != 1 or visual_counts[label] != 1:
            reasons.append("项目不能唯一对应")
        if item.raw_value is None:
            reasons.append("未读到明确值")
        if not reasons:
            field = matches[0]
            try:
                left, left_unit = _scalar(field.raw_value, field.raw_unit)
                right, right_unit = _scalar(item.raw_value, item.raw_unit)
            except ValueError:
                reasons.append("数值、日期或单位不能规范核对")
            else:
                if left != right:
                    reasons.append("数值或日期不一致")
                if left_unit != right_unit:
                    reasons.append("单位不一致或未读全")
                if source_arrow_marks(field.raw_value) != source_arrow_marks(item.raw_value):
                    reasons.append("异常标记未能对应")
                if normalize_text(field.reference_text) != normalize_text(item.reference_text):
                    reasons.append("参考范围未能对应")
                if item.time_label and normalize_text(item.time_label) != label:
                    reasons.append("日期标题与项目不一致")
        outcomes.append({
            "label": item.label, "candidate_only": True, "source_position_verified": False,
            "status": "unresolved" if reasons else "consistent_transcription_candidate",
            "reasons": reasons, "visual_excerpt": item.excerpt,
            "ocr_excerpt": matches[0].excerpt if len(matches) == 1 else None,
        })
    unmatched = [field.excerpt for field in fields if visual_counts[normalize_text(field.label)] != 1]
    return {
        "contract": REGION_COMPARISON_VERSION, "candidate_only": True,
        "formal_adoption_authorized": False, "source_position_verified": False,
        "items": outcomes, "unmatched_ocr": unmatched,
        "unresolved": unresolved + candidate.unresolved,
    }
