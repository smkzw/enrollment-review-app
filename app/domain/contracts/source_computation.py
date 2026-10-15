"""Source-declared calculations, independent of an Agent or execution engine."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .common import ContractModel


class SourceQuote(ContractModel):
    statement_index: int = Field(ge=0, strict=True,
        description="本条件source_clause/source_clauses内从0开始的序号，不是父规则或整份来源目录的序号。")
    quote: str = Field(min_length=1,
        description="对应本条件指定原文片段的逐字子串；不重述、补写或换算原文。")


class SourceCount(ContractModel):
    value: int = Field(ge=0, strict=True)
    number_text: str = Field(min_length=1,
        description="仅原文数词，如4或四；共4个应以number_text=4并在source.quote保留共4个，不自行相加填总数。")
    source: SourceQuote


class SourceInputSelection(ContractModel):
    """A source proposal, not a qualified patient operand set."""

    mode: Literal["all", "single", "latest_n", "earliest_n", "unresolved"]
    source: SourceQuote
    ordering_basis: Literal["collection_time", "report_time", "record_time", "source_sequence", "unresolved"] | None = Field(
        default=None,
        description="all/single不填写排序；unresolved只可为null或unresolved且无ordering_ref，不证明输入可计算。",
    )
    ordering_ref: SourceQuote | None = None
    window_refs: list[SourceQuote] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ordering(self):
        ordered = self.mode in {"latest_n", "earliest_n"}
        unresolved = self.mode == "unresolved"
        if unresolved and (self.ordering_basis not in {None, "unresolved"} or self.ordering_ref is not None):
            raise ValueError("输入选取未核清时不得声明已确定的排序依据")
        if not ordered and not unresolved and (self.ordering_basis is not None or self.ordering_ref is not None):
            raise ValueError("未声明按先后选取时不得附加排序方式")
        if ordered and self.ordering_basis is None:
            raise ValueError("按先后选取须保留日期角色，未明确时填未核清")
        if self.ordering_basis == "unresolved" and self.ordering_ref is not None:
            raise ValueError("日期角色未核清时不能附加已确定的排序依据")
        if ordered and self.ordering_basis != "unresolved" and self.ordering_ref is None:
            raise ValueError("排序日期或原文顺序须有逐字依据")
        return self


def count_from_text(text: str) -> int | None:
    token = unicodedata.normalize("NFKC", text.strip())
    if re.fullmatch(r"\d{1,5}", token):
        return int(token)
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if token in digits:
        return digits[token]
    if token == "十":
        return 10
    match = re.fullmatch(r"([一二三四五六七八九])?十([一二三四五六七八九])?", token)
    if match:
        return 10 * (digits[match[1]] if match[1] else 1) + (digits[match[2]] if match[2] else 0)
    return None


def count_is_quoted(number_text: str, quote: str) -> bool:
    wanted = unicodedata.normalize("NFKC", number_text.strip())
    source = unicodedata.normalize("NFKC", quote)
    return wanted in re.findall(r"\d+|[零一二两三四五六七八九十百千]+", source)


class SourceQuantityBasis(ContractModel):
    """A quoted amount-per-period basis, not an executable rate or conversion."""

    period_ref: SourceQuote
    period_partition: Literal["source_defined", "unresolved"]
    partition_ref: SourceQuote | None = None
    unit_equivalence_refs: list[SourceQuote] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_partition_source(self):
        if (self.period_partition == "source_defined") != (self.partition_ref is not None):
            raise ValueError("期间划分有明确规定时须引用依据；未核清时不得补写期间口径")
        keys = [(ref.statement_index, ref.quote) for ref in self.unit_equivalence_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("单位换算定义的来源不得重复")
        return self


class SourceComputation(ContractModel):
    operator: Literal["mean", "sum", "minimum", "maximum", "count", "ratio", "other", "unresolved"]
    operator_ref: SourceQuote
    input_refs: list[SourceQuote] = Field(default_factory=list,
        description="计算输入选择的逐字来源，mean等明确计算不可为空；即使input_selection未核清，也须提供有源输入范围，不由宿主补写。")
    missing_policy: Literal["exclude", "impute", "not_specified", "unresolved"]
    missing_ref: SourceQuote | None = None
    declared_input_count: SourceCount | None = None
    max_missing_count: SourceCount | None = None
    input_selection: SourceInputSelection | None = None
    quantity_basis: SourceQuantityBasis | None = Field(default=None,
        description="每期间数量的原文口径与单位换算定义；不是发生次数、外层回溯窗或已可执行的换算。")

    @model_serializer(mode="wrap")
    def preserve_legacy_selection(self, handler):
        value = handler(self)
        if self.input_selection is None:
            value.pop("input_selection", None)
        if self.quantity_basis is None:
            value.pop("quantity_basis", None)
        return value

    @model_validator(mode="after")
    def require_source_for_missing_policy(self):
        selection = self.input_selection
        if selection is not None and selection.mode in {"single", "latest_n", "earliest_n"}:
            count = self.declared_input_count
            if count is None or count.value < 1:
                raise ValueError("限定输入数量的选取方式须保留原文明确声明的正数")
            if selection.mode == "single" and count.value != 1:
                raise ValueError("单次输入的声明数量须为一，不能代替多次记录")
        if self.missing_policy == "unresolved" and (
            self.missing_ref is not None or self.max_missing_count is not None
        ):
            raise ValueError("缺失规则适用范围未核清时不得填写已适用的处理依据或次数")
        if self.missing_policy in {"exclude", "impute"} and self.missing_ref is None:
            raise ValueError("缺失值处理方式须有逐字来源")
        if self.missing_policy == "not_specified" and self.missing_ref is not None:
            raise ValueError("原文未规定缺失处理时不能附加处理依据")
        if self.max_missing_count is not None and self.missing_ref is None:
            raise ValueError("允许缺失的次数须与缺失处理原文一起核对")
        return self


def input_selection_references(computation: SourceComputation) -> list[SourceQuote]:
    selection = computation.input_selection
    if selection is None:
        return []
    return [selection.source, *selection.window_refs,
            *([selection.ordering_ref] if selection.ordering_ref is not None else [])]


def validate_input_selection_scope(computation: SourceComputation) -> None:
    if any(not any(ref.statement_index == parent.statement_index and ref.quote in parent.quote
                   for parent in computation.input_refs)
           for ref in input_selection_references(computation)):
        raise ValueError("选取方式、日期角色和窗口须属于该计算声明的输入依据")


def validate_computation_count_scope(computation: SourceComputation) -> None:
    if computation.declared_input_count is not None and not any(
        computation.declared_input_count.source.statement_index == ref.statement_index
        and computation.declared_input_count.source.quote in ref.quote
        for ref in computation.input_refs
    ):
        raise ValueError("输入次数须属于该计算声明的输入选择依据")
    if computation.max_missing_count is not None and computation.missing_ref is not None:
        count = computation.max_missing_count
        if (count.source.statement_index != computation.missing_ref.statement_index
                or count.source.quote not in computation.missing_ref.quote):
            raise ValueError("允许缺失次数须属于该计算的缺失处理依据")
        if computation.declared_input_count is not None and count.value > computation.declared_input_count.value:
            raise ValueError("允许缺失次数不能超过声明输入数")


def validate_computation_quotes(computation: SourceComputation, quotes: Sequence[str]) -> None:
    """Bind a calculation to its local frozen clause inventory, not patient values.

    A quoted operation/input does not prove a qualified operand selection or
    authorize evaluation. Those remain separate producer/consumer obligations.
    """
    refs = [computation.operator_ref, *computation.input_refs]
    refs.extend(input_selection_references(computation))
    if computation.quantity_basis is not None:
        basis = computation.quantity_basis
        refs.extend([basis.period_ref, *basis.unit_equivalence_refs])
        if basis.partition_ref is not None:
            refs.append(basis.partition_ref)
        if not any(basis.period_ref.statement_index == ref.statement_index
                   and basis.period_ref.quote in ref.quote for ref in computation.input_refs):
            raise ValueError("每期间数量口径须属于本计算已声明的输入范围")
    if computation.missing_ref is not None:
        refs.append(computation.missing_ref)
    for count in (computation.declared_input_count, computation.max_missing_count):
        if count is None:
            continue
        if count_from_text(count.number_text) != count.value or not count_is_quoted(count.number_text, count.source.quote):
            raise ValueError("计算次数须与逐字原文数词一致")
        refs.append(count.source)
    if any(ref.statement_index >= len(quotes) or ref.quote not in quotes[ref.statement_index]
           or not ref.quote.strip() for ref in refs):
        raise ValueError("计算依据须逐项对应本条件声明的原文片段")
    if computation.operator not in {"other", "unresolved"} and not computation.input_refs:
        raise ValueError("计算操作须声明输入选择的逐字来源")
    validate_input_selection_scope(computation)
    validate_computation_count_scope(computation)
