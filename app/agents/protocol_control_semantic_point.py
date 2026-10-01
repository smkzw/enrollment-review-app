"""Source-bound local meaning for an isolated protocol-control experiment."""

from __future__ import annotations

import json
import re
import unicodedata
from hashlib import sha256
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.protocol_controls import ProtocolControlDispositionBatch
from app.protocols.procedure_catalog import schedule_column_scope, schedule_row_values

from .protocol_control_source_interpretation import (
    SourceInterpretation, SourceStatement, normalize_source_excerpt,
)


SEMANTIC_POINT_VERSION = "phase5/control-semantic-point/v14"
SEMANTIC_BINDER_VERSION = "phase5/control-semantic-binder/v33"
SourceSemanticRole = Literal[
    "definition", "condition", "exception", "constraint", "action",
    "evidence_policy", "context", "unresolved",
]
ReviewScope = Literal[
    "patient_eligibility", "supporting_definition", "patient_study_procedure",
    "study_level_background", "unresolved",
]


class SourceQuote(ContractModel):
    statement_index: int = Field(ge=0)
    quote: str = Field(min_length=1)


class SourceCount(ContractModel):
    value: int = Field(ge=0)
    number_text: str = Field(min_length=1)
    source: SourceQuote


def _count_from_text(text: str) -> int | None:
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
        return 10 * digits[match[1]] if match[2] is None and match[1] else (
            10 * (digits[match[1]] if match[1] else 1) + (digits[match[2]] if match[2] else 0)
        )
    return None


def _count_is_quoted(number_text: str, quote: str) -> bool:
    wanted = unicodedata.normalize("NFKC", number_text.strip())
    source = unicodedata.normalize("NFKC", quote)
    return wanted in re.findall(r"\d+|[零一二两三四五六七八九十百千]+", source)


class SourceComputation(ContractModel):
    operator: Literal[
        "mean", "sum", "minimum", "maximum", "count", "ratio", "other", "unresolved",
    ]
    operator_ref: SourceQuote
    input_refs: list[SourceQuote] = Field(default_factory=list)
    missing_policy: Literal["exclude", "impute", "not_specified", "unresolved"]
    missing_ref: SourceQuote | None = None
    declared_input_count: SourceCount | None = None
    max_missing_count: SourceCount | None = None

    @model_validator(mode="after")
    def require_source_for_missing_policy(self):
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


class SourcePointDependency(ContractModel):
    statement_index: int = Field(ge=0)
    point_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class SourceSemanticPoint(ContractModel):
    statement_index: int = Field(ge=0)
    point_key: str = Field(default="main", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    exact_source_quote: str | None = Field(default=None, min_length=1)
    proposition: str = Field(min_length=1)
    role: SourceSemanticRole
    review_scope: ReviewScope = "unresolved"
    computation: SourceComputation | None = None
    dependencies: list[SourcePointDependency] = Field(default_factory=list)
    dependency_statement_indexes: list[int] = Field(default_factory=list)
    dependency_point_keys: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_consistent_role(self):
        if self.role == "context" and self.computation is not None:
            raise ValueError("纯背景不得携带计算要求")
        if self.review_scope == "study_level_background" and self.computation is not None:
            raise ValueError("研究层背景不能携带本次个例的计算提案")
        if self.review_scope == "patient_eligibility" and self.role == "context":
            raise ValueError("个例入排要求不能标为纯背景")
        if self.role == "unresolved" and not self.unresolved_dimensions:
            raise ValueError("未核清的语义点须说明具体缺口")
        if self.computation is not None and self.unresolved_dimensions and (
            self.computation.missing_policy in {"exclude", "impute"}
            or self.computation.missing_ref is not None
            or self.computation.max_missing_count is not None
        ):
            raise ValueError("语义点尚有未核清维度时不得附加已适用的缺失处理")
        if len(self.dependency_statement_indexes) != len(set(self.dependency_statement_indexes)):
            raise ValueError("语义点依赖不得重复")
        if (len(self.dependency_point_keys) != len(set(self.dependency_point_keys))
                or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key)
                       for key in self.dependency_point_keys)):
            raise ValueError("同句语义点依赖须引用有效且不重复的内部标识")
        identities = [(ref.statement_index, ref.point_key) for ref in self.dependencies]
        if len(identities) != len(set(identities)):
            raise ValueError("来源语义点依赖不得重复")
        return self


class SourceSemanticPacket(ContractModel):
    version: Literal[SEMANTIC_POINT_VERSION]
    items: list[SourceSemanticPoint] = Field(min_length=1)

    @model_validator(mode="after")
    def require_identified_dependencies(self):
        if any(point.dependency_statement_indexes or point.dependency_point_keys
               for point in self.items):
            raise ValueError("当前语义点依赖须同时标明来源陈述序位和语义点标识")
        return self


class BoundSemanticPoint(ContractModel):
    semantic_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    statement_index: int
    point_key: str
    structure_unit_id: str
    source_ref: str
    source_span_ids: list[str] = Field(min_length=1)
    exact_quote: str = Field(min_length=1)
    source_statement: SourceStatement
    source_unit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_point_quote: str = Field(min_length=1)
    proposition: str = Field(min_length=1)
    role: SourceSemanticRole
    review_scope: ReviewScope
    source_function_disagreement: bool
    computation: SourceComputation | None
    dependencies: list[SourcePointDependency]
    dependency_statement_indexes: list[int]
    dependency_point_keys: list[str]
    unresolved_dimensions: list[str]
    capability: Literal["existing_consumer", "capability_gap", "not_applicable", "unresolved"]


class SemanticPointBindingIssue(ContractModel):
    statement_index: int = Field(ge=0)
    point_key: str | None = None
    reason: str = Field(min_length=1)
    code: Literal["point_invalid", "dependency_blocked", "group_invalid"] = "group_invalid"
    blocked_by: SourcePointDependency | None = None


class _PointBindingError(ValueError):
    def __init__(self, point: SourceSemanticPoint, reason: str):
        super().__init__(reason)
        self.statement_index = point.statement_index
        self.point_key = point.point_key


def _reject_point(point: SourceSemanticPoint, reason: str) -> None:
    raise _PointBindingError(point, reason)


def _propagate_dependency_limitations(points: list[BoundSemanticPoint]) -> list[BoundSemanticPoint]:
    """A sourced dependent cannot be more resolved than its sourced premise."""

    current = list(points)
    while True:
        by_key = {(point.statement_index, point.point_key): point for point in current}
        by_statement: dict[int, list[BoundSemanticPoint]] = {}
        for point in current:
            by_statement.setdefault(point.statement_index, []).append(point)
        updated = []
        changed = False
        for point in current:
            premises = [
                by_key[(point.statement_index, key)]
                for key in point.dependency_point_keys
                if (point.statement_index, key) in by_key
            ]
            premises.extend(by_key[(ref.statement_index, ref.point_key)]
                            for ref in point.dependencies
                            if (ref.statement_index, ref.point_key) in by_key)
            premises.extend(
                premise for index in point.dependency_statement_indexes
                for premise in by_statement.get(index, [])
            )
            if any(premise.capability == "unresolved" for premise in premises):
                capability = "unresolved"
            elif (point.capability == "existing_consumer"
                  and any(premise.capability == "capability_gap" for premise in premises)):
                capability = "capability_gap"
            else:
                capability = point.capability
            changed |= capability != point.capability
            updated.append(point.model_copy(update={"capability": capability})
                           if capability != point.capability else point)
        if not changed:
            return current
        current = updated


def semantic_point_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_semantic_point_v14",
            "strict": True,
            "schema": SourceSemanticPacket.model_json_schema(),
        },
    }


def build_semantic_point_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_indexes: list[int],
    *,
    context_indexes: list[int] | None = None,
) -> str:
    if not statement_indexes or len(statement_indexes) != len(set(statement_indexes)):
        raise ValueError("须提供不重复的来源陈述序位")
    context_indexes = context_indexes or []
    if (len(context_indexes) != len(set(context_indexes))
            or set(context_indexes) & set(statement_indexes)):
        raise ValueError("只读关联原文不得与待解释陈述重复")
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    source = []
    for index in [*statement_indexes, *context_indexes]:
        if index < 0 or index >= len(interpretation.statements):
            raise ValueError("来源陈述序位不属于本批")
        statement = interpretation.statements[index]
        unit = units[statement.structure_unit_id]
        schedule_columns = schedule_column_scope(unit, batch.context_units)
        source.append({
            "statement_index": index,
            "purpose": "output" if index in statement_indexes else "read_only_context",
            "statement": statement.model_dump(mode="json"),
            "source_ref": unit.source_ref,
            "heading_path": unit.heading_path,
            "unit_excerpt": unit.excerpt,
            "table_context": (
                None if unit.table_context is None
                else unit.table_context.model_dump(mode="json")
            ),
            "schedule_columns": [{
                "column_index": column.column_index,
                "header_text": column.header_text,
                "header_source_refs": column.header_source_refs,
                "boundary_side": column.boundary_side,
                "review_stage": (
                    None if column.review_stage is None else column.review_stage.value
                ),
                "marker_footnotes": column.marker_footnotes,
            } for column in schedule_columns],
        })
    return (
        "你是本系统内置方案Agent的局部语义解释步骤，不判断受试者，不生成正式规则。"
        "只对 purpose=output 的每条陈述返回一个或多个独立语义点；同一陈述含研究规模、个例条件、动作或例外等不同功能时分开输出，"
        "每条语义点给出本陈述内逐字 exact_source_quote，point_key 在本陈述内唯一。"
        "purpose=read_only_context 仅供核对并可逐字引用，"
        "不得额外输出其语义点。说明它在本次审核中的功能，并明确与同批其他陈述的依赖。"
        "主条件可标 condition，原文明确的例外可标 exception；例外不能被解释为另一条无条件要求。"
        "原陈述的 decision_functions 仅是待核线索，不是最终相关性结论。"
        "review_scope 分开个例入排、支持定义、受试者研究流程、研究层背景和未核清；研究计划样本量不自动成为个例条件，"
        "人群适用定义也不能因与样本量同句而整体退出。不能判清时保留 unresolved。"
        "方案正文要求每例受试者在预筛、筛选、导入或基线完成的动作，即使不在入排列表中，"
        "也不能仅因写在统一研究流程里就称为研究层背景；须核它是否为入排节点前置控制。"
        "访视表上的 X 仅表明安排了操作或记录，不自动证明其结果、完成情况或入排作用；"
        "若只有日程安排而无本次入排依据，可标 patient_study_procedure；"
        "尚无法判断该流程是否影响入排时标 unresolved，不能猜成 patient_eligibility。"
        "纯研究规模、设计或统计说明若不要求个例满足，才可作为研究层背景。"
        "表格中的 X 必须结合给出的行列、列名和访视边界理解；列名或当前阶段不清时不能标成已确定的纯背景。"
        "同一要求的时间窗、对象、动作和用途通常是同一命题的限定，不要把完整要求与其组成短句重复列成独立要求；"
        "只有独立改变审核或计算方式的定义、例外、共享约束才另列语义点。"
        "若同一句把同一动作明确用于两个可分别核对的访视或时期，按各自时期拆成两个语义点；"
        "两点仍引用同一完整原句，但 exact_source_quote 各摘录本句中不同的时期短语，"
        "proposition 分别说明该时期与共同动作的关系。不能把原文未写出的拆分句冒充逐字引文；"
        "时期归属不清时保留 unresolved，不把另一访视的完成情况用于本访视。"
        "只有解释本点确实需要另一独立点（如定义、例外或共同计算政策）时，"
        "才在 dependencies 填其 statement_index 与 point_key；同句和跨句都使用这一对明确身份。"
        "原文并列列出的两个条件不互相依赖，不能仅因同句或同一受试者而相互挂靠。"
        "需要前提时仅在文字中说‘结合’却留空依赖不可视为已核清；"
        "旧字段 dependency_point_keys 与 dependency_statement_indexes 必须留空；"
        "只使用 dependencies 同时标明陈述序位和语义点标识。"
        "原文规定计算时，仅用枚举说明操作类型，operator_ref.quote 必须逐字来自对应来源陈述；"
        "输入选择和缺失值政策分别用 statement_index 与 quote 指明真实短句，不能借用其他陈述。"
        "若同批另一陈述明确约束该计算的缺失处理，须引用那条陈述的序位及逐字短句；"
        "原文若明确给出输入总次数或允许缺失次数，分别填 declared_input_count、max_missing_count；"
        "number_text 只摘录数词本身，value 填其确切整数，source.quote 摘录含数词的原文短句。"
        "没有明确次数时填 null，不能用经验补数。"
        "仅本次所给来源均未规定时才写 not_specified。适用关系不清写 unresolved，"
        "此时 missing_ref 和 max_missing_count 均填 null；共用政策来源可作为独立约束点，"
        "用 dependencies 明确关联，不能当作已经适用于本计算。"
        "语义点还有未核清维度时，也不能填 exclude/impute 或已适用的缺失处理依据与次数。"
        "计算不能核清时说明具体缺口。"
        "不要补造时间点、样本数、数值、单位或研究者意见。"
        "proposition 是对原文的解释，绝非原文引文；原文身份由程序绑定。"
        "只返回请求结构指定的 JSON 对象。"
        "\n冻结来源：" + json.dumps(source, ensure_ascii=False, sort_keys=True)
    )


def bind_semantic_packet(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_indexes: list[int],
    packet: SourceSemanticPacket,
    *,
    context_indexes: list[int] | None = None,
) -> list[BoundSemanticPoint]:
    context_indexes = context_indexes or []
    if (len(context_indexes) != len(set(context_indexes))
            or set(context_indexes) & set(statement_indexes)
            or any(index < 0 or index >= len(interpretation.statements) for index in context_indexes)):
        raise ValueError("只读关联原文序位不属于本次可见来源")
    visible_indexes = set(statement_indexes) | set(context_indexes)
    if len(statement_indexes) != len(set(statement_indexes)) or {
        item.statement_index for item in packet.items
    } != set(statement_indexes):
        raise ValueError("每条请求的来源陈述须至少对应一个语义点，不得夹带其他陈述")
    keys = [(item.statement_index, item.point_key) for item in packet.items]
    if len(keys) != len(set(keys)):
        raise ValueError("同一陈述的语义点身份不得重复")
    points_by_key = {(item.statement_index, item.point_key): item for item in packet.items}
    for item in packet.items:
        if item.computation is not None and item.unresolved_dimensions and (
            item.computation.missing_policy in {"exclude", "impute"}
            or item.computation.missing_ref is not None
            or item.computation.max_missing_count is not None
        ):
            _reject_point(item, "未核清的语义点不能携带已适用的缺失处理")
        available = {key for index, key in keys if index == item.statement_index}
        if item.point_key in item.dependency_point_keys or not set(item.dependency_point_keys) <= available:
            _reject_point(item, "同句依赖必须指向本次返回的另一独立语义点")
        if any((ref.statement_index, ref.point_key) == (item.statement_index, item.point_key)
               or (ref.statement_index, ref.point_key) not in keys for ref in item.dependencies):
            _reject_point(item, "语义点依赖必须指向本次返回的另一条有身份语义点")
        if item.computation is not None and item.computation.missing_policy in {"exclude", "impute"}:
            if any(
                points_by_key[(ref.statement_index, ref.point_key)].unresolved_dimensions
                or points_by_key[(ref.statement_index, ref.point_key)].role == "unresolved"
                for ref in item.dependencies
            ):
                _reject_point(item, "共用来源尚未核清时不能认定缺失处理已适用于本计算")
    remaining = {}
    for item in packet.items:
        remaining[(item.statement_index, item.point_key)] = {
            (item.statement_index, key) for key in item.dependency_point_keys
        } | {
            (ref.statement_index, ref.point_key) for ref in item.dependencies
        }
    point_dependencies = {key: set(value) for key, value in remaining.items()}
    while remaining:
        ready = {key for key, dependencies in remaining.items() if not dependencies}
        if not ready:
            raise ValueError("语义点依赖形成循环，不能互相证明")
        remaining = {
            key: dependencies - ready for key, dependencies in remaining.items()
            if key not in ready
        }
    points_by_statement = {
        index: [point for point in packet.items if point.statement_index == index]
        for index in statement_indexes
    }
    for points in points_by_statement.values():
        if len(points) > 1 and (
            any(point.exact_source_quote is None for point in points)
            or len({normalize_source_excerpt(point.exact_source_quote) for point in points}) != len(points)
        ):
            raise ValueError("同句多个语义点须分别引用不同的逐字原文片段")
    point_by_key = {(point.statement_index, point.point_key): point for point in packet.items}

    def dependent_points(key: tuple[int, str]) -> list[dict]:
        pending = list(point_dependencies[key])
        seen: set[tuple[int, str]] = set()
        while pending:
            dependency = pending.pop()
            if dependency in seen:
                continue
            seen.add(dependency)
            pending.extend(point_dependencies[dependency])
        return [point_by_key[dependency].model_dump(mode="json") for dependency in sorted(seen)]
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    calculation_source_quotes: dict[int, list[str]] = {}
    shared_missing_counts: dict[tuple[int, str, int], list[SourceSemanticPoint]] = {}
    for point in packet.items:
        computation = point.computation
        if computation is not None:
            if computation.missing_ref is not None and computation.max_missing_count is not None:
                count = computation.max_missing_count
                shared_missing_counts.setdefault((count.source.statement_index,
                    count.source.quote, count.value), []).append(point)
            refs = [computation.operator_ref, *computation.input_refs]
            if computation.missing_ref is not None:
                refs.append(computation.missing_ref)
            for count in (computation.declared_input_count, computation.max_missing_count):
                if count is not None:
                    refs.append(count.source)
            for ref in refs:
                calculation_source_quotes.setdefault(ref.statement_index, []).append(
                    normalize_source_excerpt(ref.quote)
                )
    unqualified_shared_counts = {
        (point.statement_index, point.point_key)
        for points in shared_missing_counts.values()
        if len({tuple((ref.statement_index, ref.quote) for ref in point.computation.input_refs)
                for point in points}) > 1
        for point in points
    }
    bound = []
    for item in packet.items:
        if item.statement_index < 0 or item.statement_index >= len(interpretation.statements):
            _reject_point(item, "语义点引用了本批之外的陈述")
        statement = interpretation.statements[item.statement_index]
        unit = units.get(statement.structure_unit_id)
        if unit is None or normalize_source_excerpt(statement.quoted_text) not in normalize_source_excerpt(unit.excerpt):
            _reject_point(item, "来源陈述与冻结原文不一致")
        point_quote = item.exact_source_quote or statement.quoted_text
        normalized_point_quote = normalize_source_excerpt(point_quote)
        if point_quote not in statement.quoted_text or point_quote not in unit.excerpt:
            _reject_point(item, "语义点逐字摘录不是冻结原文中的连续原串")
        used_as_calculation_source = any(
            quote in normalized_point_quote or normalized_point_quote in quote
            for quote in calculation_source_quotes.get(item.statement_index, [])
        ) or any(
            other.computation is not None
            and other.computation.missing_policy == "unresolved" and (
                any(ref.statement_index == item.statement_index
                    and ref.point_key == item.point_key for ref in other.dependencies)
            )
            for other in packet.items
        )
        background = item.review_scope == "study_level_background"
        row_values = schedule_row_values(unit) if unit.table_context is not None else ()
        has_schedule_mark = bool(
            row_values and any(
                re.fullmatch(r"[（(]?\s*[xX×]\s*[)）]?(?:\^\d+)*", cell.strip())
                for _column, cell, _refs in row_values[1:]
            )
        )
        schedule_only_markers = has_schedule_mark and all(
            not cell.strip() or re.fullmatch(
                r"[（(]?\s*[xX×]\s*[)）]?(?:\^\d+)*", cell.strip()
            ) for _column, cell, _refs in row_values[1:]
        )
        if has_schedule_mark:
            schedule_columns = schedule_column_scope(unit, batch.context_units)
        else:
            schedule_columns = ()
        schedule_scope_unresolved = background and has_schedule_mark and (
            not schedule_columns or any(
                column.boundary_side != "after_baseline" for column in schedule_columns
            )
        )
        schedule_eligibility_unresolved = (
            item.review_scope == "patient_eligibility" and schedule_only_markers
            and not item.dependency_statement_indexes and not item.dependency_point_keys
            and not item.dependencies
        )
        calculation = item.computation
        disagreement = (
            background and (
                statement.decision_functions != ["background"] or statement.force != "descriptive"
            )
        ) or (
            calculation is not None
            and not {"calculation_input", "definition"} & set(statement.decision_functions)
        )
        if background and (
            statement.unresolved or used_as_calculation_source
            or (disagreement and item.exact_source_quote is None)
        ):
            _reject_point(item, "具有计算依赖、尚未核清或无单独来源片段的陈述不能降为纯背景")
        if item.role == "context" and not background:
            _reject_point(item, "纯背景必须说明不是个例入排要求")
        if ("calculation_input" in statement.decision_functions and calculation is None
                and not background
                and not used_as_calculation_source
                and not item.unresolved_dimensions
                and not (item.role == "constraint" and item.exact_source_quote is not None)
                and not any(
                    other is not item and other.statement_index == item.statement_index
                    and other.computation is not None for other in packet.items
                )):
            _reject_point(item, "计算相关陈述既未表达计算，也未说明未核清维度")
        dependencies = [*item.dependency_statement_indexes]
        if any(index == item.statement_index or index not in visible_indexes
               for index in dependencies):
            _reject_point(item, "语义点依赖必须指向本次可见的另一条来源陈述")
        if calculation is not None:
            if calculation.operator_ref.statement_index != item.statement_index:
                _reject_point(item, "计算操作须由本条来源直接支持")
            refs = [calculation.operator_ref, *calculation.input_refs]
            if calculation.missing_ref is not None:
                refs.append(calculation.missing_ref)
            for count in (calculation.declared_input_count, calculation.max_missing_count):
                if count is None:
                    continue
                if _count_from_text(count.number_text) != count.value:
                    _reject_point(item, "次数与原文数词不一致或数词无法核实")
                if not _count_is_quoted(count.number_text, count.source.quote):
                    _reject_point(item, "次数必须逐字出现在所引原文中")
                refs.append(count.source)
            if (calculation.declared_input_count is not None
                    and calculation.declared_input_count.source.statement_index not in {
                        ref.statement_index for ref in calculation.input_refs
                    }):
                _reject_point(item, "输入次数须引用该计算的输入选择原文")
            if (calculation.max_missing_count is not None
                    and calculation.missing_ref is not None
                    and calculation.max_missing_count.source.statement_index
                    != calculation.missing_ref.statement_index):
                _reject_point(item, "允许缺失次数须引用该计算的缺失处理原文")
            if (calculation.declared_input_count is not None
                    and calculation.max_missing_count is not None
                    and calculation.max_missing_count.value > calculation.declared_input_count.value):
                _reject_point(item, "允许缺失次数不能超过原文输入总次数")
            for ref in refs:
                if ref.statement_index not in visible_indexes:
                    _reject_point(item, "计算引用了本次未提供的来源陈述")
                cited_statement = interpretation.statements[ref.statement_index]
                cited_unit = units[cited_statement.structure_unit_id]
                if ref.quote not in cited_statement.quoted_text or ref.quote not in cited_unit.excerpt:
                    _reject_point(item, "计算摘录必须是所标明冻结原文中的连续原串")
                if ref.statement_index != item.statement_index:
                    dependencies.append(ref.statement_index)
            if calculation.operator in {"mean", "sum", "minimum", "maximum", "count", "ratio"} and not calculation.input_refs:
                _reject_point(item, "计算操作未说明输入的原文来源")
            for ref in refs:
                if ref.statement_index == item.statement_index or ref.statement_index not in statement_indexes:
                    continue
                matching = [
                    points_by_key[(dependency.statement_index, dependency.point_key)]
                    for dependency in item.dependencies
                    if dependency.statement_index == ref.statement_index
                    and (dependency.statement_index, dependency.point_key) in points_by_key
                ]
                if not any(
                    ref.quote in (point.exact_source_quote or interpretation.statements[ref.statement_index].quoted_text)
                    or (point.exact_source_quote is not None and point.exact_source_quote in ref.quote)
                    for point in matching
                ):
                    _reject_point(item, "跨陈述计算依赖须指向包含该原文摘录的有身份语义点")
        if (item.role == "unresolved" or item.review_scope == "unresolved"
                or statement.unresolved or item.unresolved_dimensions):
            capability = "unresolved"
        elif calculation is None:
            capability = (
                "unresolved" if disagreement or schedule_scope_unresolved
                or schedule_eligibility_unresolved
                or item.review_scope == "patient_study_procedure" else
                "not_applicable" if background or (
                    item.role == "constraint"
                    and used_as_calculation_source
                ) else "capability_gap"
            )
        elif calculation.operator == "unresolved":
            capability = "unresolved"
        else:
            # No series aggregation or input-selection operator exists in the
            # current formal calculation contract. A numeric comparison alone
            # cannot stand in for a source-defined computation.
            capability = "capability_gap"
        source_dependency_indexes = set(dependencies) | {
            ref.statement_index for ref in item.dependencies
        }
        unverified_context = sorted(source_dependency_indexes & set(context_indexes))
        if unverified_context:
            capability = "unresolved"
        limitations = list(item.unresolved_dimensions)
        if (item.statement_index, item.point_key) in unqualified_shared_counts:
            capability = "unresolved"
            limitations.append("同一允许缺失次数关联多个不同计算，计数适用范围尚未核清")
        if unverified_context:
            limitations.append("引用的相邻原文尚未逐条核实含义")
        identity = json.dumps(
            [SEMANTIC_BINDER_VERSION, SEMANTIC_POINT_VERSION, batch.batch_id,
             item.statement_index, unit.model_dump(mode="json"),
             statement.model_dump(mode="json"), item.model_dump(mode="json"),
             [
                 [index, interpretation.statements[index].model_dump(mode="json"),
                  units[interpretation.statements[index].structure_unit_id].model_dump(mode="json")]
                 for index in sorted(source_dependency_indexes)
             ], dependent_points((item.statement_index, item.point_key))],
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        bound.append(BoundSemanticPoint(
            semantic_id=sha256(identity).hexdigest(),
            statement_index=item.statement_index,
            point_key=item.point_key,
            structure_unit_id=unit.structure_unit_id,
            source_ref=unit.source_ref,
            source_span_ids=list(unit.source_span_ids),
            exact_quote=statement.quoted_text,
            source_statement=statement,
            source_unit_sha256=sha256(json.dumps(
                unit.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest(),
            exact_point_quote=point_quote,
            proposition=item.proposition,
            role=item.role,
            review_scope=item.review_scope,
            source_function_disagreement=disagreement,
            computation=calculation,
            dependencies=list(item.dependencies),
            dependency_statement_indexes=sorted(set(dependencies)),
            dependency_point_keys=list(item.dependency_point_keys),
            unresolved_dimensions=limitations,
            capability=capability,
        ))
    return _propagate_dependency_limitations(bound)


def bind_semantic_packet_partially(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_indexes: list[int],
    packet: SourceSemanticPacket,
    *,
    context_indexes: list[int] | None = None,
) -> tuple[list[BoundSemanticPoint], list[SemanticPointBindingIssue]]:
    """Keep independently verified points, never treating partial coverage as complete."""
    context_indexes = context_indexes or []
    if (not statement_indexes or len(set(statement_indexes)) != len(statement_indexes)
            or len(set(context_indexes)) != len(context_indexes)
            or set(statement_indexes) & set(context_indexes)
            or any(index < 0 or index >= len(interpretation.statements)
                   for index in [*statement_indexes, *context_indexes])):
        raise ValueError("待解释陈述与只读范围不合法")
    requested = set(statement_indexes)
    grouped: dict[int, list[SourceSemanticPoint]] = {}
    issues: list[SemanticPointBindingIssue] = []
    for point in packet.items:
        if point.statement_index not in requested:
            issues.append(SemanticPointBindingIssue(
                statement_index=point.statement_index, point_key=point.point_key,
                reason="语义点不属于本次待解释来源",
            ))
            continue
        grouped.setdefault(point.statement_index, []).append(point)
    eligible: list[SourceSemanticPoint] = []
    for index in statement_indexes:
        points = grouped.get(index, [])
        if not points:
            issues.append(SemanticPointBindingIssue(
                statement_index=index, reason="请求的来源陈述没有语义点",
            ))
            continue
        keys = [point.point_key for point in points]
        quotes = [normalize_source_excerpt(point.exact_source_quote or "") for point in points]
        for point in points:
            if keys.count(point.point_key) != 1 or (len(points) > 1 and (
                not point.exact_source_quote or quotes.count(
                    normalize_source_excerpt(point.exact_source_quote)
                ) != 1
            )):
                issues.append(SemanticPointBindingIssue(
                    statement_index=index, point_key=point.point_key,
                    reason="同一陈述的语义点身份或逐字摘录重复",
                ))
                continue
            eligible.append(point)

    def dependencies(point: SourceSemanticPoint | BoundSemanticPoint) -> set[tuple[int, str]]:
        return {
            (ref.statement_index, ref.point_key) for ref in point.dependencies
        } | {
            (point.statement_index, key) for key in point.dependency_point_keys
        }

    accepted: list[BoundSemanticPoint] = []
    remaining = list(eligible)
    while remaining:
        group = [remaining.pop(0)]
        group_indexes = {group[0].statement_index}
        group_keys = {(group[0].statement_index, group[0].point_key)}
        while True:
            linked = [point for point in remaining if (
                (point.statement_index, point.point_key) in set().union(
                    *(dependencies(member) for member in group)
                )
                or bool(dependencies(point) & group_keys)
                or any(
                    point.computation is not None and member.computation is not None
                    and point.computation.max_missing_count is not None
                    and member.computation.max_missing_count is not None
                    and point.computation.max_missing_count == member.computation.max_missing_count
                    for member in group
                )
            )]
            if not linked:
                break
            remaining = [point for point in remaining if point not in linked]
            group.extend(linked)
            group_indexes.update(point.statement_index for point in linked)
            group_keys.update((point.statement_index, point.point_key) for point in linked)
        try:
            accepted.extend(bind_semantic_packet(
                batch, interpretation, sorted(group_indexes),
                SourceSemanticPacket(version=SEMANTIC_POINT_VERSION, items=group),
                context_indexes=sorted((requested | set(context_indexes)) - group_indexes),
            ))
        except (ValueError, TypeError) as exc:
            culprit = (exc.statement_index, exc.point_key) if isinstance(exc, _PointBindingError) else None
            for point in group:
                own_error = culprit == (point.statement_index, point.point_key)
                issues.append(SemanticPointBindingIssue(
                    statement_index=point.statement_index, point_key=point.point_key,
                    reason=str(exc) if own_error or culprit is None else "依赖组中另一语义点未通过来源核验",
                    code="point_invalid" if own_error else "dependency_blocked" if culprit else "group_invalid",
                    blocked_by=SourcePointDependency(statement_index=culprit[0], point_key=culprit[1])
                    if culprit is not None and not own_error else None,
                ))
    # A source reference may be visible while its separately requested meaning
    # failed verification. Do not promote dependent points on that basis.
    while True:
        accepted_keys = {(point.statement_index, point.point_key) for point in accepted}
        dependent = [point for point in accepted if dependencies(point) - accepted_keys]
        if not dependent:
            break
        rejected_ids = {point.semantic_id for point in dependent}
        accepted = [point for point in accepted if point.semantic_id not in rejected_ids]
        issues.extend(SemanticPointBindingIssue(
            statement_index=point.statement_index, point_key=point.point_key,
            reason="依赖陈述的语义尚未核实",
        ) for point in dependent)
    return _propagate_dependency_limitations(accepted), issues
