"""Bounded assembly of a single stage-bound source requirement.

The semantic reader chooses the action and its source.  This module supplies
only the mechanical fields of the existing control wire.  Unsupported timing,
conditions, and exceptions remain compilation gaps, not inferred rules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from types import SimpleNamespace
from typing import Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.control_evidence_policy import ControlEvidenceSourcePolicy
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ProtocolControlDispositionBatch,
    ReviewNodeRole,
)
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.enums import ProtocolPeriod
from app.protocols.protocol_control_gate import _split_prohibition_atom_covers_clause
from app.protocols.supplementary_relation_contract import procedure_execution_workflow_stage_id
from app.protocols.source_time_fragments import intraday_time_fragments
from app.protocols.control_scope_sources import resolve_ancestor_scope_citation

from .protocol_control_deconstructor import (
    ProtocolControlAgentResponse,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    _merge_source_candidate_insert,
    hydrate_protocol_control_agent_output,
    source_statement_coverage,
)
from .protocol_control_source_interpretation import (
    SourceInterpretation,
    SourceTargetReviewItem,
    normalize_source_excerpt,
    source_requires_temporal_resolution,
    source_visit_scope_matches,
    source_has_single_visit_anchor,
)


STAGE_BOUND_REQUIREMENT_VERSION = "phase5/control-stage-bound-requirement/v10"
RELATIVE_STAGE_REQUIREMENT_VERSION = "phase5/control-relative-stage-requirement/v8"
SHARED_PROHIBITION_REQUIREMENT_VERSION = "phase5/control-shared-prohibition-requirement/v3"


class _SourceRequirement(ContractModel):
    """Only semantic choices shared by the two bounded assembly paths."""

    statement_index: int = Field(ge=0)
    action_excerpt: str = Field(min_length=1)
    stage_scope_excerpt: str = Field(min_length=1)
    workflow_stage_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    obligation_statement: str = Field(min_length=1)
    kind: Literal["complete_or_verify", "must_record", "must_professional_assessment"]
    determination_mode: Literal["semantic", "investigator_judgment"]
    result_requirement: Literal["action_only", "result_required", "unresolved"] = "unresolved"
    observation_scope: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    evidence_description: str = Field(min_length=1)
    required_source_types: list[str]
    source_policy: ControlEvidenceSourcePolicy | None = None
    unresolved_aspects: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_action_mode(self) -> "_SourceRequirement":
        if self.result_requirement == "action_only" and (
            self.kind != "complete_or_verify" or self.determination_mode != "semantic"
        ):
            raise ValueError("只核操作完成须采用普通必做操作类型，不能改作记录或研究者判断")
        return self


class StageBoundRequirement(_SourceRequirement):
    version: Literal[STAGE_BOUND_REQUIREMENT_VERSION]


class RelativeStageRequirement(_SourceRequirement):
    version: Literal[RELATIVE_STAGE_REQUIREMENT_VERSION]
    prior_workflow_stage_id: str = Field(min_length=1)
    target_procedure_id: str = Field(min_length=1)
    relative_time_excerpt: str = Field(min_length=1)


class SharedProhibitionRequirement(ContractModel):
    version: Literal[SHARED_PROHIBITION_REQUIREMENT_VERSION]
    statement_index: int = Field(ge=0)
    current_statement: str = Field(min_length=1)
    future_statement: str = Field(min_length=1)
    workflow_stage_id: str = Field(min_length=1)
    prospective_period: ProtocolPeriod
    kind: Literal["prohibit_event", "prohibit_medication_or_treatment_exposure"]
    title: str = Field(min_length=1)
    applicable_population: str = Field(min_length=1)
    observation_scope: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    evidence_description: str = Field(min_length=1)
    required_source_types: list[str]
    unresolved_aspects: list[str] = Field(default_factory=list)


class StageBoundCompilationGap(ValueError):
    """A source dimension cannot be assembled without semantic invention."""


def _time_parts(text: str) -> list[str]:
    return [
        normalize_source_excerpt(part)
        for part in re.split(r"[（）()，,；;：:]", text)
        if normalize_source_excerpt(part)
    ]


def _visit_scope_in_stage(part: str, frozen_visit: str) -> bool:
    """A simple 'visit period 内' belongs to that period, not to a new visit."""
    if part in frozen_visit:
        return True
    if re.fullmatch(r"[^、，和及与/]+期内", part):
        return part[:-1] in frozen_visit
    return False


def _simple_stage_scope(statement: SourceStatement) -> str | None:
    if statement.scope_quote:
        return statement.scope_quote
    if len(statement.time_words) != 1:
        return None
    word = statement.time_words[0]
    if normalize_source_excerpt(word) in normalize_source_excerpt(statement.quoted_text):
        return word
    return None


def requires_temporal_resolution(interpretation: SourceInterpretation, statement_index: int) -> bool:
    """Keep explicit durations and cross-period duties out of the short visit path."""

    return source_requires_temporal_resolution(interpretation.statements[statement_index])


def can_compile_shared_prohibition_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> bool:
    if review.decision != "additional_requirement" or review.statement_index >= len(interpretation.statements):
        return False
    return can_compile_shared_prohibition_source(batch, interpretation, review.statement_index)


def can_compile_shared_prohibition_source(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
) -> bool:
    """Source-only capability check; no invented source-target decision."""
    if not 0 <= statement_index < len(interpretation.statements):
        return False
    statement = interpretation.statements[statement_index]
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    return bool(
        statement.force == "prohibited"
        and not statement.exception_words
        and not statement.unresolved
        and not intraday_time_fragments(" ".join(filter(None, (
            statement.quoted_text, statement.scope_quote, *statement.time_words,
        ))))
        and unit is not None
        and len(unit.source_span_ids) == 1
        and requires_temporal_resolution(interpretation, statement_index)
        and re.search(r"不允许|不得|禁止|严禁|不应", statement.quoted_text)
    )


def build_shared_prohibition_requirement_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> str:
    if not can_compile_shared_prohibition_requirement(batch, interpretation, review):
        raise StageBoundCompilationGap("本条不属于有源跨阶段禁止短解释范围")
    statement = interpretation.statements[review.statement_index]
    unit = next(item for item in batch.owned_units
                if item.structure_unit_id == statement.structure_unit_id)
    source = {
        "statement_index": review.statement_index,
        "quoted_text": statement.quoted_text,
        "owned_unit": {"structure_unit_id": unit.structure_unit_id,
                       "excerpt": unit.excerpt, "heading_path": unit.heading_path},
        "frozen_stages": [
            {"workflow_stage_id": stage.workflow_stage_id,
             "review_stage": stage.review_stage.value,
             "display_name": stage.display_name,
             "visit_instance": stage.visit_instance}
            for stage in batch.known_workflow_stage_targets
        ],
    }
    return (
        "你是本系统内置方案 Agent 的单条来源解释步骤。仅当同一句原文把两个时期并列在"
        "同一个禁止动作前，且可逐字拆成截至本次审核节点的禁止与后续禁止，才填写两条陈述；"
        "否则在 unresolved_aspects 写明不能拆分之处，系统不会发布。"
        "current_statement 只写本次节点需要核对的时期和原禁止动作；future_statement "
        "只写后续时期和完全相同的原禁止动作。observation_scope 须逐字保留本次时期名称，"
        "不得把未来未发生的行为写进本次观察范围，"
        "不得创造节点、日期、药物或医学结论。prospective_period 只从原文明确的治疗期或研究期选择。"
        "全部字段只根据这条原文和冻结节点填写，不能借同单元另一句话补时间。"
        "required_source_types 仅填写原文明文限定的受试者资料种类；未限定时必须填写空列表 []，"
        "不把可用的证明材料编成强制来源限制。"
        "只返回随附结构的 JSON 对象。\n"
        f"冻结来源：{json.dumps(source, ensure_ascii=False, sort_keys=True)}"
    )


def shared_prohibition_requirement_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_shared_prohibition_requirement_v1",
            "strict": True,
            "schema": SharedProhibitionRequirement.model_json_schema(),
        },
    }


def can_compile_stage_bound_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> bool:
    """Avoid a model call when the frozen visit cannot cover source timing."""

    if review.decision != "additional_requirement" or review.statement_index >= len(interpretation.statements):
        return False
    return can_compile_stage_bound_source(batch, interpretation, review.statement_index)


def can_compile_stage_bound_source(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    statement_index: int,
) -> bool:
    """Capability preflight only; this does not approve a source or its meaning."""
    if not 0 <= statement_index < len(interpretation.statements):
        return False
    statement = interpretation.statements[statement_index]
    if not source_has_single_visit_anchor(statement):
        return False
    if (
        statement.force != "required"
        or not _simple_stage_scope(statement)
        or not statement.time_words
        or statement.exception_words
        or statement.unresolved
    ):
        return False
    required = [part for word in statement.time_words for part in _time_parts(word)]
    scope_text = _simple_stage_scope(statement)
    assert scope_text is not None
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        return False
    try:
        resolve_ancestor_scope_citation(unit, scope_text, [*batch.owned_units, *batch.context_units])
    except ValueError:
        return False
    scope_parts = _time_parts(scope_text)
    if not scope_parts or not all(
        part in normalize_source_excerpt(scope_text) for part in required
    ):
        return False
    for stage in batch.known_workflow_stage_targets:
        frozen_visit = normalize_source_excerpt(" ".join(filter(None, (
            stage.display_name, stage.visit_instance, stage.visit_window,
        ))))
        if source_visit_scope_matches(scope_text, frozen_visit):
            return True
    return False


def can_compile_relative_stage_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> bool:
    if review.decision != "additional_requirement" or review.statement_index >= len(interpretation.statements):
        return False
    statement = interpretation.statements[review.statement_index]
    if requires_temporal_resolution(interpretation, review.statement_index):
        return False
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None or not statement.scope_quote:
        return False
    try:
        resolve_ancestor_scope_citation(unit, statement.scope_quote, [*batch.owned_units, *batch.context_units])
    except ValueError:
        return False
    return bool(
        statement.force == "required"
        and statement.scope_quote
        and not statement.exception_words
        and not statement.unresolved
        and review.target_id
        and any(item.catalog_item_id == review.target_id for item in batch.known_procedure_targets)
        and review.source_time_excerpt
        and normalize_source_excerpt(review.source_time_excerpt)
        in normalize_source_excerpt(statement.quoted_text)
        and all(normalize_source_excerpt(word) in normalize_source_excerpt(statement.quoted_text)
                for word in statement.time_words)
    )


def build_stage_bound_requirement_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> str:
    """Ask the existing product reader for semantics, not final rule storage."""

    if review.statement_index >= len(interpretation.statements):
        raise StageBoundCompilationGap("增量陈述序位不存在")
    statement = interpretation.statements[review.statement_index]
    if review.decision != "additional_requirement":
        raise StageBoundCompilationGap("本路径只处理已核的增量要求")
    unit = next((item for item in batch.owned_units
                 if item.structure_unit_id == statement.structure_unit_id), None)
    if unit is None:
        raise StageBoundCompilationGap("增量要求不属于冻结来源单元")
    source = {
        "statement_index": review.statement_index,
        "quoted_text": statement.quoted_text,
        "scope_quote": statement.scope_quote,
        "simple_stage_scope": _simple_stage_scope(statement),
        "time_words": statement.time_words,
        "force": statement.force,
        "exception_words": statement.exception_words,
        "source_action_excerpt": review.source_action_excerpt,
        "reason_for_insertion": review.unresolved_aspects,
        "owned_unit": {"structure_unit_id": unit.structure_unit_id,
                       "source_span_ids": unit.source_span_ids,
                       "excerpt": unit.excerpt, "heading_path": unit.heading_path},
        "frozen_stages": [
            {"workflow_stage_id": item.workflow_stage_id,
             "review_stage": item.review_stage.value,
             "display_name": item.display_name,
             "visit_instance": item.visit_instance,
             "visit_window": item.visit_window}
            for item in batch.known_workflow_stage_targets
        ],
    }
    return (
        "你是本系统内置方案 Agent 的单项语义解释步骤，不审核受试者，也不输出完整规则。"
        "只处理一个已核实尚未覆盖的原文动作。选择原文逐字动作摘录、逐字访视范围和冻结节点；"
        "访视范围可来自动作句内唯一明确的时间措辞，也可来自已核共同范围，不得借相邻动作的时点；"
        "不要凭 D 日标记换算首次给药日期或补日历时限。"
        "仅当动作与全部时间措辞均能由同一冻结访视直接支持，且无未明条件、例外、持续期、"
        "复查频率或跨节点义务时才给出可装配的字段。其余情形在 unresolved_aspects 逐项说明，"
        "系统会保留为待核，不能靠你填写其他字段而通过。"
        "reason_for_insertion 只是前一步判定现有目录未完整覆盖的原因，不等于本条原文语义未明；"
        "请勿把它原样复制到 unresolved_aspects。若本条动作/访视本身可解释，该列表应为空。"
        "obligation_statement 必须完整保留本条逐字 quoted_text，不得另写入排合格结论。"
        "普通必做操作用 semantic，确需研究者书面判断才用 investigator_judgment；"
        "result_requirement 仅按本条方案原文判断：只要求在该节点完成操作、不要求结果方向时填 action_only；"
        "另要求结果或合格性时填 result_required；无法区分时填 unresolved。"
        "action_only 必须与 kind=complete_or_verify、determination_mode=semantic 配套；"
        "must_record 表示独立的记录义务，不能与 action_only 搭配。"
        "操作已完成只能证明操作要求，不能证明检验结果正常或其他入排条款满足。"
        "required_source_types 只填写原文明文限定的受试者资料种类；未限定时必须填写空列表 []，"
        "不把可能用于证明操作的记录种类改成强制来源限制，也不额外要求未写明的签名或时间。"
        "source_policy 仅按冻结原文解释同期客观原件、筛选记录转述及结果有效期要求，并逐字引用对应 source_span_ids；"
        "不能仅凭本句没有说明就推断整个方案没有限制。未查清的布尔维度填 null、有效期填 unknown；"
        "已有明确依据的维度须保留，不能把整个对象一律清空。没有可引用的政策依据时 source_policy 填 null。"
        "本路径不向你询问选用哪次观察；原文未规定时系统固定保留为未核实，"
        "不得在其他字段暗示只取一份、最新一份或所有记录。"
        "不要把来源标题、背景信息或已有官方条款文字改写为新动作。"
        "只返回符合随附结构的 JSON 对象。\n"
        f"冻结来源：{json.dumps(source, ensure_ascii=False, sort_keys=True)}"
    )


def stage_bound_requirement_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_stage_bound_requirement_v10",
            "strict": True,
            "schema": StageBoundRequirement.model_json_schema(),
        },
    }


def build_relative_stage_requirement_prompt(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
) -> str:
    if not can_compile_relative_stage_requirement(batch, interpretation, review):
        raise StageBoundCompilationGap("本陈述不具备有源相对节点核查条件")
    statement = interpretation.statements[review.statement_index]
    unit = next(item for item in batch.owned_units
                if item.structure_unit_id == statement.structure_unit_id)
    source = {
        "statement_index": review.statement_index,
        "quoted_text": statement.quoted_text,
        "scope_quote": statement.scope_quote,
        "time_words": statement.time_words,
        "source_action_excerpt": review.source_action_excerpt,
        "source_time_excerpt": review.source_time_excerpt,
        "reason_for_insertion": review.unresolved_aspects,
        "owned_unit": {"structure_unit_id": unit.structure_unit_id,
                       "source_span_ids": unit.source_span_ids,
                       "excerpt": unit.excerpt, "heading_path": unit.heading_path},
        "frozen_stages": [
            {"workflow_stage_id": stage.workflow_stage_id,
             "review_stage": stage.review_stage.value,
             "display_name": stage.display_name,
             "visit_instance": stage.visit_instance,
             "visit_window": stage.visit_window}
            for stage in batch.known_workflow_stage_targets
        ],
        "frozen_procedure_target": [
            {"catalog_item_id": target.catalog_item_id,
             "review_stage": target.review_stage.value,
             "visit_instance": target.visit_instance,
             "source_excerpts": target.source_excerpts}
            for target in batch.known_procedure_targets
            if target.catalog_item_id == review.target_id
        ],
    }
    return (
        "你是本系统内置方案 Agent 的单项相对访视语义解释步骤，不审核受试者。"
        "只解释来源中该动作发生在先前阶段结束后的要求，以及哪个冻结节点承担复核；"
        "不要把相对先后关系换算成首次给药日回溯天数，不把既有目标声称为完全覆盖。"
        "仅当原文相对时间措辞逐字存在、先前与后续审核节点都在冻结目录、"
        "目标流程原文记录同类操作且后续节点确实晚于先前节点时，才给出字段。"
        "若条件、例外、持续期、频次、节点对应关系不清，在 unresolved_aspects 明示，"
        "系统将拒绝装配。reason_for_insertion 是旧目录没有完整表达的原因，"
        "不是本条原文语义未明，不能原样抄入 unresolved_aspects。"
        "按已有入排条款再次核查合格性是 complete_or_verify 加 semantic；"
        "result_requirement 只按本条来源判断：仅完成复核动作填 action_only；"
        "还要求资格结果填 result_required；不明填 unresolved。不能把复核已做当作资格合格。"
        "action_only 必须与 complete_or_verify 加 semantic 配套，不能与 must_record 搭配。"
        "只有原文要求研究者作独立书面临床判断时才用 must_professional_assessment"
        "加 investigator_judgment。两字段不能互相矛盾。"
        "workflow_stage_id 是执行此次核查的后续节点，不是先前导入节点；"
        "先后关系由 prior_workflow_stage_id 和 relative_time_excerpt 表达。"
        "obligation_statement 必须完整保留本条逐字 quoted_text，不得把复核动作改写成合格结论。"
        "本路径不询问选用哪次记录，原文未定则系统保留未核实。"
        "required_source_types 只填写原文明文限定的受试者资料种类，未限定时必须填写空列表 []；"
        "不得把可能的证明材料改成强制来源限制。"
        "source_policy 按冻结原文保留同期原件、筛选记录转述与有效期要求及逐字引用；"
        "只允许使用所给 source_span_ids。未查清维度保持 null 或 unknown，不能从本句未提及推断全方案无限制；"
        "没有可引用的政策依据时 source_policy 填 null。"
        "只返回随附结构的 JSON 对象。\n"
        f"冻结来源：{json.dumps(source, ensure_ascii=False, sort_keys=True)}"
    )


def relative_stage_requirement_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "protocol_control_relative_stage_requirement_v8",
            "strict": True,
            "schema": RelativeStageRequirement.model_json_schema(),
        },
    }


def compile_shared_prohibition_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
    selection: SharedProhibitionRequirement,
) -> ProtocolControlAgentWireCandidate:
    if not can_compile_shared_prohibition_requirement(batch, interpretation, review):
        raise StageBoundCompilationGap("本条禁止要求的原文或时间条件未核实")
    if selection.statement_index != review.statement_index or selection.unresolved_aspects:
        raise StageBoundCompilationGap("跨阶段禁止仍有未核实的原文含义")
    statement = interpretation.statements[selection.statement_index]
    unit = next(item for item in batch.owned_units
                if item.structure_unit_id == statement.structure_unit_id)
    stage = next((item for item in batch.known_workflow_stage_targets
                  if item.workflow_stage_id == selection.workflow_stage_id), None)
    if stage is None:
        raise StageBoundCompilationGap("本次判定节点不属于冻结目录")
    raw_quote = statement.quoted_text
    quote = normalize_source_excerpt(raw_quote)
    clause = re.sub(r"[。；;]+$", "", re.sub(r"\s+", "", raw_quote))
    if not quote or raw_quote not in unit.excerpt:
        raise StageBoundCompilationGap("禁止原句不属于冻结来源单元")
    if normalize_source_excerpt(review.source_action_excerpt) not in quote:
        raise StageBoundCompilationGap("禁止动作不得省略已核原文")
    current = selection.current_statement
    future = selection.future_statement
    atom_shape = SimpleNamespace(
        statement=current,
        evaluation=SimpleNamespace(proposition=current),
        source_span_ids=unit.source_span_ids,
        source_excerpts=[raw_quote],
        continuing_obligation=SimpleNamespace(
            statement=future,
            status="not_due_at_review_node",
            source_span_ids=unit.source_span_ids,
            source_excerpts=[raw_quote],
        ),
    )
    if not _split_prohibition_atom_covers_clause(clause, atom_shape):
        raise StageBoundCompilationGap("当前与后续禁止不能由同一句原文逐字拆分")
    verb = re.search(r"不允许|不得|禁止|严禁|不应", current)
    assert verb is not None  # guaranteed by the exact split check above
    current_prefix = current[:verb.start()]
    future_prefix = future[:future.index(verb.group())]
    if selection.prospective_period == ProtocolPeriod.TREATMENT_PERIOD:
        if not re.search(r"治疗|给药|用药", future_prefix):
            raise StageBoundCompilationGap("后续时期未明确属于治疗或用药期")
    elif not re.search(r"(?:随机|基线|给药|入组)后", future_prefix):
        raise StageBoundCompilationGap("研究期未明确从本次审核节点以后开始")
    if normalize_source_excerpt(current_prefix) not in normalize_source_excerpt(selection.observation_scope) or (
        normalize_source_excerpt(future_prefix) in normalize_source_excerpt(selection.observation_scope)
    ):
        raise StageBoundCompilationGap("本次观察范围不得包含后续时期")
    stage_texts = [normalize_source_excerpt(" ".join(filter(None, (
        item.display_name, item.visit_instance, item.visit_window
    )))) for item in batch.known_workflow_stage_targets]
    stage_parts = [normalize_source_excerpt(part).rstrip("期")
                   for part in re.split(r"[/、，,和及与]", current_prefix) if part]
    matching = [item.review_stage for item, text in zip(batch.known_workflow_stage_targets,
                                                         stage_texts, strict=True)
                if any(part and part in text for part in stage_parts)]
    ordered = list(ReviewStage)
    if not matching or max(ordered.index(value) for value in matching) > ordered.index(stage.review_stage):
        raise StageBoundCompilationGap("当前禁止范围尚未由所选审核节点完整覆盖")

    spans = [unit.source_span_ids[0]]
    try:
        return ProtocolControlAgentWireCandidate.model_validate({
            "title": selection.title,
            "applicable_population": selection.applicable_population,
            "applicability_expression": None,
            "trigger_expression": None,
            "obligation_expression": {"groups": [{"atoms": [{
                "kind": selection.kind,
                "statement": current,
                "evaluation": {
                    "version": "control-atom-evaluation/v4",
                    "determination_mode": "semantic",
                    "proposition": current,
                    "time_purpose": "not_applicable",
                    "repeat_scheme": None,
                    "observation_policy": {"mode": "unresolved", "scope": selection.observation_scope,
                                           "source_span_ids": spans, "source_excerpts": [raw_quote]},
                    "source_span_ids": spans, "source_excerpts": [raw_quote],
                },
                "time_constraint": None,
                "prospective_period": None,
                "continuing_obligation": {
                    "statement": future,
                    "prospective_period": {"period": selection.prospective_period.value},
                    "source_span_ids": spans,
                    "source_excerpts": [raw_quote],
                    "status": "not_due_at_review_node",
                },
                "modality": "mandatory",
                "temporal_scope": None,
                "source_span_ids": spans, "source_excerpts": [raw_quote],
                "requires_professional_judgment": False,
            }], "applies_to_trigger_branch_indexes": []}]},
            "exception_expression": None,
            "repeat_trigger_conditions": [],
            "review_node_bindings": [{
                "workflow_stage_id": stage.workflow_stage_id,
                "review_stage": stage.review_stage,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }],
            "minimum_evidence": [{
                "fact_type": selection.fact_type,
                "description": selection.evidence_description,
                "due_stage": stage.review_stage,
                "required_source_types": selection.required_source_types,
                "workflow_stage_ids": [stage.workflow_stage_id],
                "source_policy": {
                    "requires_contemporaneous_objective_source": None,
                    "allows_screening_record_transcription": None,
                    "result_validity_status": "not_specified",
                    "result_validity_constraint": None,
                    "source_span_ids": spans,
                    "source_excerpts": [raw_quote],
                },
                "atom_refs": [{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            }],
            "source_structure_unit_ids": [unit.structure_unit_id],
            "source_span_ids": spans,
            "cross_source_relations": [],
        })
    except ValueError as exc:
        raise StageBoundCompilationGap(str(exc)) from exc


def compile_stage_bound_requirement(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
    selection: StageBoundRequirement | RelativeStageRequirement,
) -> ProtocolControlAgentWireCandidate:
    """Compile only when each source time phrase has a supported stage path.

    This path does not invent calendar lookbacks, conditional branches,
    exceptions, or future continuing obligations.
    """

    if (
        selection.statement_index != review.statement_index
        or selection.statement_index >= len(interpretation.statements)
        or review.decision != "additional_requirement"
    ):
        raise StageBoundCompilationGap("本次解释不是已核的增量来源陈述")
    statement = interpretation.statements[selection.statement_index]
    if requires_temporal_resolution(interpretation, selection.statement_index):
        raise StageBoundCompilationGap("原文持续期或跨节点时间要求不能由单次访视装配")
    if selection.unresolved_aspects or statement.unresolved or statement.exception_words:
        raise StageBoundCompilationGap("原文条件、例外或未核实之处不能由单阶段路径装配")
    if statement.force != "required":
        raise StageBoundCompilationGap("单阶段路径只处理已明确的必做要求")
    if selection.kind == ControlObligationKind.MUST_PROFESSIONAL_ASSESSMENT.value:
        if selection.determination_mode != "investigator_judgment":
            raise StageBoundCompilationGap("研究者判断要求须保留独立判断模式")
    elif selection.determination_mode != "semantic":
        raise StageBoundCompilationGap("普通操作不能伪装成研究者判断")
    if selection.result_requirement == "action_only" and selection.kind != "complete_or_verify":
        raise StageBoundCompilationGap("只核操作完成须对应原文中的必做操作")

    units = [unit for unit in batch.owned_units if unit.structure_unit_id == statement.structure_unit_id]
    stages = [stage for stage in batch.known_workflow_stage_targets if stage.workflow_stage_id == selection.workflow_stage_id]
    if len(units) != 1 or len(stages) != 1:
        raise StageBoundCompilationGap("来源单元或审核节点不属于本次冻结批次")
    unit, stage = units[0], stages[0]
    source = normalize_source_excerpt(unit.excerpt)
    action = normalize_source_excerpt(selection.action_excerpt)
    scope = normalize_source_excerpt(selection.stage_scope_excerpt)
    if not action or not scope or action not in source:
        raise StageBoundCompilationGap("动作摘录不属于冻结原文")
    if scope not in source and not any(scope in normalize_source_excerpt(part) for part in unit.heading_path):
        raise StageBoundCompilationGap("访视范围摘录不属于冻结原文")
    if action not in normalize_source_excerpt(statement.quoted_text):
        raise StageBoundCompilationGap("动作不属于本条来源陈述")
    if scope != normalize_source_excerpt(_simple_stage_scope(statement) or ""):
        raise StageBoundCompilationGap("访视范围必须采用已核陈述的原文范围")
    if normalize_source_excerpt(review.source_action_excerpt) not in action:
        raise StageBoundCompilationGap("动作不得省略已核增量摘录中的限定")
    source_proposition = normalize_source_excerpt(statement.quoted_text).rstrip("。；;.!！?？")
    selected_proposition = normalize_source_excerpt(selection.obligation_statement).rstrip("。；;.!！?？")
    if not source_proposition or source_proposition not in selected_proposition:
        raise StageBoundCompilationGap("义务陈述必须完整保留本条逐字来源，不得改写判断方向")

    declared_time = [part for word in statement.time_words for part in _time_parts(word)]
    scope_parts = _time_parts(selection.stage_scope_excerpt)
    frozen_visit = normalize_source_excerpt(" ".join(filter(None, (
        stage.display_name, stage.visit_instance, stage.visit_window
    ))))
    relations: list[dict[str, object]] = []
    if isinstance(selection, RelativeStageRequirement):
        previous = next((item for item in batch.known_workflow_stage_targets
                         if item.workflow_stage_id == selection.prior_workflow_stage_id), None)
        procedure = next((item for item in batch.known_procedure_targets
                          if item.catalog_item_id == selection.target_procedure_id), None)
        ordered = list(ReviewStage)
        if (
            previous is None or procedure is None
            or review.target_id != selection.target_procedure_id
            or ordered.index(previous.review_stage) >= ordered.index(stage.review_stage)
            or procedure_execution_workflow_stage_id(
                procedure, batch.known_workflow_stage_targets
            ) != stage.workflow_stage_id
        ):
            raise StageBoundCompilationGap("相对节点先后或流程目标不受冻结目录支持")
        previous_visit = normalize_source_excerpt(" ".join(filter(None, (
            previous.display_name, previous.visit_instance, previous.visit_window
        ))))
        relative = normalize_source_excerpt(selection.relative_time_excerpt)
        target_action = normalize_source_excerpt(review.target_action_excerpt or "")
        if (
            not scope_parts or any(part not in previous_visit for part in scope_parts)
            or not relative or relative != normalize_source_excerpt(review.source_time_excerpt or "")
            or relative not in normalize_source_excerpt(statement.quoted_text)
            or any(part not in relative for part in declared_time)
            or relative not in normalize_source_excerpt(selection.obligation_statement)
            or not target_action
            or not any(target_action in normalize_source_excerpt(value or "")
                       for value in procedure.source_excerpts)
        ):
            raise StageBoundCompilationGap("相对时间、原文动作或流程摘录不能逐项回源")
        relations.append({
            "kind": "supplementary_requirement",
            "external_target_kind": "required_procedure",
            "external_target_id": procedure.catalog_item_id,
            "candidate_side": "left",
            "affected_workflow_stage_id": stage.workflow_stage_id,
            "notes": "原文限定先前阶段结束后再次核查，现有流程仅记录核查动作与访视。",
        })
    elif not declared_time or not scope_parts or any(
        part not in scope for part in declared_time
    ) or any(not _visit_scope_in_stage(part, frozen_visit) for part in scope_parts):
        raise StageBoundCompilationGap("原文时间要求未被所选冻结访视逐项覆盖")
    if isinstance(selection, StageBoundRequirement) and review.target_id:
        procedure = next((item for item in batch.known_procedure_targets
                          if item.catalog_item_id == review.target_id), None)
        target_action = normalize_source_excerpt(review.target_action_excerpt or "")
        if (procedure is not None and target_action and target_action in action
                and any(target_action in normalize_source_excerpt(excerpt or "")
                        for excerpt in procedure.source_excerpts)
                and procedure_execution_workflow_stage_id(
                    procedure, batch.known_workflow_stage_targets,
                ) == stage.workflow_stage_id):
            relations.append({
                "kind": "supplementary_requirement",
                "external_target_kind": "required_procedure",
                "external_target_id": procedure.catalog_item_id,
                "candidate_side": "left",
                "affected_workflow_stage_id": stage.workflow_stage_id,
                "notes": "原文动作在同一访视对既有流程目标提出增量要求。",
            })
    if not selection.observation_scope:
        raise StageBoundCompilationGap("资料范围未说明")

    if len(unit.source_span_ids) != 1:
        raise StageBoundCompilationGap("多处来源定位需要逐处语义解释")
    try:
        scope_citation = resolve_ancestor_scope_citation(
            unit, selection.stage_scope_excerpt, [*batch.owned_units, *batch.context_units],
        )
    except ValueError as exc:
        raise StageBoundCompilationGap(str(exc)) from exc
    # Only physically inline scopes belong to the body's atom source pairs.
    spans = ([unit.source_span_ids[0]] if scope_citation else
             [unit.source_span_ids[0], unit.source_span_ids[0]])
    excerpts = ([statement.quoted_text] if scope_citation else
                [selection.stage_scope_excerpt, statement.quoted_text])
    judgment = selection.determination_mode == "investigator_judgment"
    evaluation = {
        "version": "control-atom-evaluation/v4",
        "determination_mode": selection.determination_mode,
        "proposition": statement.quoted_text,
        "time_purpose": "not_applicable",
        "repeat_scheme": None,
        "observation_policy": {
            "mode": "action_completion" if selection.result_requirement == "action_only" else "unresolved",
            "scope": selection.observation_scope,
            "source_span_ids": spans,
            "source_excerpts": excerpts,
        },
        "source_span_ids": spans,
        "source_excerpts": excerpts,
    }
    try:
        return ProtocolControlAgentWireCandidate.model_validate({
            "title": selection.title,
            "applicable_population": selection.applicable_population,
            "applicability_expression": None,
            "trigger_expression": None,
            "obligation_expression": {"groups": [{"atoms": [{
                "kind": selection.kind,
                "statement": statement.quoted_text,
                "evaluation": evaluation,
                "time_constraint": None,
                "prospective_period": None,
                "continuing_obligation": None,
                "modality": "mandatory",
                "temporal_scope": None,
                "source_span_ids": spans,
                "source_excerpts": excerpts,
                "requires_professional_judgment": judgment,
            }], "applies_to_trigger_branch_indexes": []}]},
            "exception_expression": None,
            "repeat_trigger_conditions": [],
            "review_node_bindings": [{
                "workflow_stage_id": stage.workflow_stage_id,
                "review_stage": stage.review_stage,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
                "scope_citation": scope_citation.model_dump(mode="json") if scope_citation else None,
            }],
            "minimum_evidence": [{
                "fact_type": selection.fact_type,
                "description": selection.evidence_description,
                "due_stage": stage.review_stage,
                "required_source_types": selection.required_source_types,
                "workflow_stage_ids": [stage.workflow_stage_id],
                "source_policy": selection.source_policy.model_dump(mode="json") if selection.source_policy else {
                    "requires_contemporaneous_objective_source": None,
                    "allows_screening_record_transcription": None,
                    "result_validity_status": "unknown",
                    "result_validity_constraint": None,
                    "source_span_ids": spans,
                    "source_excerpts": excerpts,
                },
                "atom_refs": [{"layer": "obligation", "group_index": 0, "atom_index": 0}],
            }],
            "source_structure_unit_ids": [unit.structure_unit_id],
            "source_span_ids": [unit.source_span_ids[0]],
            "cross_source_relations": relations,
        })
    except ValueError as exc:
        raise StageBoundCompilationGap(str(exc)) from exc


def compile_source_requirement_response(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    review: SourceTargetReviewItem,
    response: ProtocolControlAgentResponse,
) -> ProtocolControlAgentWireCandidate:
    """Check one actual short answer before spending on the next author."""

    payload = json.loads(response.text)
    if not isinstance(payload, dict):
        raise StageBoundCompilationGap("单项解释必须返回本次合同的对象")
    if payload.get("version") == STAGE_BOUND_REQUIREMENT_VERSION:
        selection = StageBoundRequirement.model_validate(payload)
    elif payload.get("version") == RELATIVE_STAGE_REQUIREMENT_VERSION:
        selection = RelativeStageRequirement.model_validate(payload)
    elif payload.get("version") == SHARED_PROHIBITION_REQUIREMENT_VERSION:
        selection = SharedProhibitionRequirement.model_validate(payload)
    else:
        raise StageBoundCompilationGap("单项解释版本不属于本次装配合同")
    if isinstance(selection, SharedProhibitionRequirement):
        return compile_shared_prohibition_requirement(batch, interpretation, review, selection)
    return compile_stage_bound_requirement(batch, interpretation, review, selection)


def assemble_source_requirement_inserts(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    reviews: list[SourceTargetReviewItem],
    baseline: ProtocolControlAgentWire,
    responses: list[ProtocolControlAgentResponse],
    output_validator: Callable[..., None],
    *, validate_complete: bool = True,
):
    """Compile each insert; incomplete checkpoints are never publication proof."""

    if not reviews or len(reviews) != len(responses):
        raise StageBoundCompilationGap("逐项解释回执与待补来源数目不一致")
    candidates = [compile_source_requirement_response(batch, interpretation, review, response)
                  for review, response in zip(reviews, responses, strict=True)]
    owned = {interpretation.statements[item.statement_index].structure_unit_id for item in reviews}
    merged = _merge_source_candidate_insert(
        json.dumps({"candidate_drafts": [item.model_dump(mode="json") for item in candidates]}, ensure_ascii=False),
        baseline,
        authorized_unit_ids=owned,
    )
    output = hydrate_protocol_control_agent_output(merged, batch) if validate_complete else None
    if validate_complete:
        output_validator(output)
    coverage = source_statement_coverage(batch, interpretation, merged)
    if any(coverage[item.statement_index].status != "expressed" for item in reviews):
        raise StageBoundCompilationGap("新增义务没有逐字表达全部授权来源陈述")
    return merged, output, coverage
