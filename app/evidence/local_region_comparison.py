"""Isolated transcript comparison; matching text never approves a clinical fact.

The OCR adapter has no verified pixel coordinates. Logical rows and uniquely
labelled values can be compared, but they cannot establish field-level position.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from itertools import combinations
import re
import unicodedata

from app.domain.contracts.local_region_read import LocalRegionReadCandidate
from app.domain.page_normalization import normalize_scalar, normalize_text, source_arrow_marks


REGION_COMPARISON_VERSION = "local-region-transcript-comparison/v7"

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
    requires_review: bool = False
    association_only: bool = False


@dataclass(frozen=True)
class _TableCell:
    text: str
    requires_review: bool


class _TableReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.tables = []
        self.row = None
        self.cell = None
        self.unsupported = False
        self.table_depth = 0
        self.outside = []
        self.cell_format_uncertain = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_depth += 1
            self.unsupported |= self.table_depth > 1
            if self.table_depth == 1:
                self.rows = []
        if tag == "tr":
            self.unsupported |= self.row is not None or self.table_depth != 1
            self.row = []
        if tag in {"td", "th"}:
            self.unsupported |= self.cell is not None or self.row is None
            self.unsupported |= any(k in {"rowspan", "colspan"} and v != "1" for k, v in attrs)
            self.cell = [[]]
            self.cell_format_uncertain = False
        if self.cell is not None and tag in {"br", "p", "div", "li"}:
            self.cell.append([])
        if self.cell is not None and tag in {"sup", "sub"}:
            self.cell_format_uncertain = True
            self.cell[-1].append(self.get_starttag_text())

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[-1].append(data)
        elif data.strip():
            self.outside.append(data)

    def handle_endtag(self, tag):
        if self.cell is not None and tag in {"p", "div", "li"}:
            self.cell.append([])
        if self.cell is not None and tag in {"sup", "sub"}:
            self.cell[-1].append(f"</{tag}>")
        if tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                parts = ["".join(part).strip() for part in self.cell]
                parts = [part for part in parts if part]
                self.row.append(_TableCell("\n".join(parts), len(parts) > 1 or self.cell_format_uncertain))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.unsupported |= self.row is not None or self.cell is not None or self.table_depth != 1
            if self.table_depth == 1:
                self.tables.append(self.rows)
            self.table_depth -= 1


def _plain_table_header(line: str) -> int | None:
    names = [normalize_text(value) for value in line.split()]
    offset = 0
    if len(names) == 6 and names[0] in {"no.", "no", "序号"} and names[1] in {"代号", "代码"}:
        offset = 2
    if len(names) != offset + 4 or any(
        name not in aliases for name, aliases in zip(names[offset:], _TABLE_COLUMN_NAMES, strict=True)
    ):
        return None
    return offset


def _plain_table_row(line: str, offset: int) -> RegionOcrField | None:
    prefix = r"\d+\s+\S+\s+" if offset else ""
    number = r"[+-]?\d+(?:\.\d+)?"
    match = re.fullmatch(prefix + rf"(?P<label>.+?)\s+(?P<value>[<>≤≥]?{number}[↑↓]?)"
        + rf"\s+(?P<reference>{number}(?:--|[-~～–—至]){number})(?:\s+(?P<unit>\S+))?", line)
    if match is None:
        return None
    if offset and any(
        re.fullmatch(prefix + rf".+?\s+[<>≤≥]?{number}[↑↓]?"
                     + rf"\s+{number}(?:--|[-~～–—至]){number}(?:\s+\S+)?", line[start.start():])
        for start in re.finditer(r"(?<!\S)\d+\s+\S+\s+", line)
        if start.start() > 0
    ):
        return None
    return RegionOcrField(match['label'], match['value'], match['unit'], match['reference'], line,
                          requires_review=match['unit'] is None)


def _numbered_table_groups(line: str) -> tuple[bool, ...] | None:
    names = [normalize_text(value) for value in line.split()]
    starts = [index for index in range(len(names) - 1)
              if names[index] in {"no.", "no", "序号"} and names[index + 1] in {"代号", "代码"}]
    if not starts or starts[0] != 0 or not 2 <= len(starts) <= 4:
        return None
    groups = []
    for start, end in zip(starts, starts[1:] + [len(names)], strict=True):
        columns = names[start + 2:end]
        if len(columns) not in {3, 4} or any(
            column not in aliases for column, aliases in zip(columns, _TABLE_COLUMN_NAMES)
        ):
            return None
        groups.append(len(columns) == 4)
    return tuple(groups)


def _numbered_group_row(line: str, groups: tuple[bool, ...]) -> tuple[list[RegionOcrField], list[str]]:
    starts = [match.start() for match in re.finditer(r"(?<!\S)\d+\s+\S+\s+", line)]
    # Enumerate complete partitions instead of treating every number in a name
    # as a new column. Ambiguous partitions remain unread; keep work bounded.
    if not starts or starts[0] != 0 or len(starts) > 16:
        return [], ["并列表格行尚不能明确分组：" + line]
    partitions = []
    for middle in combinations(starts[1:], len(groups) - 1):
        boundaries = (0, *middle, len(line))
        fields = [_plain_table_row(line[start:end].strip(), 2)
                  for start, end in zip(boundaries, boundaries[1:])]
        if all(field is not None for field in fields):
            partitions.append(fields)
            if len(partitions) > 1:
                break
    if len(partitions) != 1:
        return [], ["并列表格行存在缺列或多种分组，未借相邻项目补全：" + line]
    accepted, gaps = [], []
    for complete_header, field in zip(groups, partitions[0], strict=True):
        if not complete_header:
            gaps.append("此组表头的单位列未完整读取，整组保留待核：" + field.excerpt)
            accepted.append(RegionOcrField(field.label, "", None, None, field.excerpt,
                                           requires_review=True, association_only=True))
            continue
        accepted.append(field)
        if field.raw_unit is None:
            gaps.append("单位列未完整读取：" + field.excerpt)
    return accepted, gaps


def region_ocr_fields(text: str) -> tuple[list[RegionOcrField], list[str]]:
    if "<table" in text.lower():
        reader = _TableReader()
        reader.feed(text)
        reader.close()
        if (reader.unsupported or reader.table_depth or reader.row is not None or reader.cell is not None
                or not reader.tables):
            return [], ["表格有合并、嵌套或未完整读取，暂不能逐项对应。"]
        fields, unresolved = [], ["表格之外尚有未对应文字：" + value for value in reader.outside]
        for rows in reader.tables:
            if not rows or any(cell.requires_review for cell in rows[0]):
                unresolved.append("表格列名分段或格式含义尚未明确，暂不推断各列含义。")
                continue
            if len(rows) == 1:
                unresolved.append("此表只有列名，没有完整读取数据行，暂不能确认覆盖。")
                continue
            header = [normalize_text(cell.text) for cell in rows[0]]
            matched_columns = [[index for index, name in enumerate(header) if name in aliases]
                               for aliases in _TABLE_COLUMN_NAMES]
            if any(len(matches) != 1 for matches in matched_columns):
                unresolved.append("表格列名不能明确对应，暂不推断各列含义。")
                continue
            positions = [matches[0] for matches in matched_columns]
            for cells in rows[1:]:
                row = [cell.text for cell in cells]
                if len(row) != len(header):
                    unresolved.append("一行的列数与表头不一致，未采用相邻行填补。")
                    continue
                for index, cell in enumerate(row):
                    if index not in positions and cell.strip():
                        unresolved.append("表格其他列尚未对应：" + header[index] + "：" + cell)
                if any(cells[index].requires_review for index in positions):
                    unresolved.append("此行含分段或上下标文字，尚不能合成单项结果：" + " | ".join(row))
                    continue
                label, value, reference, unit = [row[index] for index in positions]
                if not label or not value:
                    unresolved.append("一行缺少明确项目或结果，暂不能对应。")
                    continue
                fields.append(RegionOcrField(label, value, unit or None, reference or None, " | ".join(row)))
        return fields, unresolved
    # A single explicit label/value line is a literal transcription, not a
    # medical interpretation. Preserve the entire value, including qualifiers.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Keep the existing adjacent timestamp handling; do not reinterpret prose
    # or infer a label for unlabelled content.
    pattern = re.compile(
        r"(?P<label>[^:：\n]+)[:：]\s*(?P<value>"
        r"\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?"
        r"|[+-]?\d+(?:\.\d+)?(?:\s*[%\w\u4e00-\u9fff⁹¹²/×^+\-⁻]+)?)"
    )
    fields, leftovers = [], []
    table_offset = None
    table_groups = None
    for line in lines:
        header = _plain_table_header(line)
        if header is not None:
            table_offset = header
            table_groups = None
            continue
        groups = _numbered_table_groups(line)
        if groups is not None:
            table_groups, table_offset = groups, None
            continue
        if table_groups is not None:
            if re.match(r"\d+\s+", line):
                grouped, gaps = _numbered_group_row(line, table_groups)
                fields.extend(grouped)
                leftovers.extend(gaps)
                continue
            table_groups = None
        if normalize_text(line.split()[0]) in {"no.", "no", "序号"}:
            table_offset = None
            leftovers.append("表格列名不能明确对应：" + line)
            continue
        if table_offset is not None:
            field = _plain_table_row(line, table_offset)
            if field is not None:
                fields.append(field)
                if field.raw_unit is None:
                    leftovers.append("单位列未完整读取：" + line)
                continue
            # Do not carry a table's column meaning into a separate paragraph.
            # Numbered unread rows retain the header for the next intact row.
            if not table_offset or not re.match(r"\d+\s+", line):
                table_offset = None
        parts = re.split(r"[:：]", line)
        if len(parts) == 2 and all(part.strip() for part in parts):
            label, value = (part.strip() for part in parts)
            if not re.fullmatch(r"[\d\s.+/-]+", normalize_text(label)):
                fields.append(RegionOcrField(label, value, None, None, line))
                continue
        matches = [match for match in pattern.finditer(line)
                   if not re.fullmatch(r"[\d\s.+/-]+", normalize_text(match["label"]))]
        end = 0
        for match in matches:
            if line[end:match.start()].strip():
                leftovers.append(line[end:match.start()].strip())
            fields.append(RegionOcrField(match["label"].strip(), match["value"], None, None, match[0]))
            end = match.end()
        if line[end:].strip():
            leftovers.append(line[end:].strip())
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


def _field_matches(field: RegionOcrField, item) -> bool:
    if normalize_text(field.label) == normalize_text(item.label):
        return True
    # A display label may omit a printed marker only when the complete literal
    # row (including that marker) agrees. Never remove clinical words/arrows.
    unmarked = field.label.lstrip("★☆•·*")
    exact_row = lambda value: re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
    return (unmarked != field.label and normalize_text(unmarked) == normalize_text(item.label)
            and exact_row(field.excerpt) == exact_row(item.excerpt))


def compare_local_region_read(ocr_text: str, candidate: LocalRegionReadCandidate) -> dict:
    fields, unresolved = region_ocr_fields(ocr_text)
    visual_counts = Counter(normalize_text(item.label) for item in candidate.items if item.label)
    outcomes = []
    for item in candidate.items:
        reasons = []
        label = normalize_text(item.label)
        matches = [field for field in fields if _field_matches(field, item)]
        if item.script != "printed" or item.legibility != "clear":
            reasons.append("字迹或对应对象尚未核实")
        if not label or len(matches) != 1 or visual_counts[label] != 1:
            reasons.append("项目不能唯一对应")
        if item.raw_value is None:
            reasons.append("未读到明确值")
        if not reasons:
            field = matches[0]
            if field.association_only:
                reasons.append("项目所在列组尚未核清")
            elif field.requires_review:
                reasons.append("单位列未完整读取")
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
            "ocr_excerpt": matches[0].excerpt if len(matches) == 1 and not matches[0].association_only else None,
        })
    unmatched = [field.excerpt for field in fields if sum(_field_matches(field, item) for item in candidate.items) != 1]
    return {
        "contract": REGION_COMPARISON_VERSION, "candidate_only": True,
        "formal_adoption_authorized": False, "source_position_verified": False,
        "items": outcomes, "unmatched_ocr": unmatched,
        "unresolved": unresolved + candidate.unresolved,
    }
