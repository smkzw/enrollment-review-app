"""Opt-in front-loading of the existing single-requirement compiler.

The pending wire is only a comparison input, never a publishable result.
Actual source-target review precedes one author per independent statement;
the caller still runs the normal publication and alignment consumers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json

from .protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireValidationError,
    source_statement_coverage,
)
from .protocol_control_source_interpretation import (
    SourceInterpretation,
    SourceTargetReview,
    SourceTargetReviewValidationError,
    build_source_target_review_prompt,
    normalize_source_excerpt,
    target_action_established,
    validate_source_interpretation,
    validate_source_target_review,
    target_review_indexes,
)
from .protocol_control_stage_compiler import (
    assemble_source_requirement_inserts,
    compile_source_requirement_response,
    build_stage_bound_requirement_prompt,
    can_compile_stage_bound_requirement,
    can_compile_stage_bound_source,
)
from .protocol_control_candidate_alignment import (
    SourceCandidateAlignment, bind_candidate_alignment, build_candidate_alignment_prompt,
    validate_candidate_alignment,
)
from app.domain.contracts.protocol_controls import (
    ProtocolControlDispositionBatch,
    StructureUnitDispositionKind,
)

BASELINE = "RV1001-BASELINE"
FIXED_FLOW = "RV1001-FLOW"
FIXED_FLOW_VERSION = "rv1001/front-stage-flow/v16"
FRONT_REVIEW_CORRECTION_CODES = frozenset({
    "TARGET_VISIT_SCOPE_UNPROVEN", "TIME_SCOPE_MISMATCH",
    "TARGET_TIME_INCOMPLETE", "TARGET_EXCEPTION_UNGROUNDED",
})


def _failure_code(exc: Exception) -> str | None:
    from .protocol_control_agent_transport import protocol_control_call_failure_code
    terminal = protocol_control_call_failure_code(exc)
    if terminal is not None:
        return terminal
    seen = set()
    current = exc
    uncertain_completion = False
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if getattr(current, "code", None):
            return current.code
        uncertain_completion |= bool(getattr(current, "uncertain_completion", False))
        current = current.__cause__
    return "FLOW_COMPLETION_UNCERTAIN" if uncertain_completion else None


def workflow_template(template: str, variant: str) -> str:
    if variant == BASELINE:
        return template
    if variant != FIXED_FLOW:
        raise ValueError("未知方案语义工作流程")
    return template + "\n" + FIXED_FLOW_VERSION


def pending_front_wire(batch) -> ProtocolControlAgentWire:
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[ProtocolControlAgentWireDisposition(
            structure_unit_id=unit.structure_unit_id,
            disposition=StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
            linked_official_code=None,
            linked_procedure_catalog_item_id=None,
            linked_procedure_catalog_item_ids=[],
            notes="候选读取范围，尚未生成或采用要求",
        ) for unit in batch.owned_units],
        candidate_drafts=[],
    )


def validate_front_review(batch, interpretation, review) -> None:
    """A pre-author review is bound to pending, not final, coverage."""
    validate_source_interpretation(batch, interpretation)
    coverage = source_statement_coverage(batch, interpretation, pending_front_wire(batch))
    validate_source_target_review(batch, interpretation, coverage, review)


def front_stage_supported_indexes(batch, interpretation: SourceInterpretation) -> set[int]:
    """Compiler capability is per statement, not a clinical coverage decision."""
    units = {unit.structure_unit_id: unit for unit in batch.owned_units}
    return {
        index for index, statement in enumerate(interpretation.statements)
        if ("action" in statement.decision_functions
            and set(statement.decision_functions) <= {"action", "time_validity"}
            and statement.control_authority == "study_or_unknown"
            and statement.eligibility_sequence == "current_or_unknown"
            and statement.structure_unit_id in units
            and len(units[statement.structure_unit_id].source_span_ids) == 1
            and can_compile_stage_bound_source(batch, interpretation, index))
    }


def supports_front_stage_flow(batch, interpretation: SourceInterpretation) -> bool:
    """Mixed sources may preserve supported points without certifying the rest."""
    validate_source_interpretation(batch, interpretation)
    if not interpretation.statements or interpretation.units_without_statement:
        return False
    if {s.structure_unit_id for s in interpretation.statements} != {
        unit.structure_unit_id for unit in batch.owned_units
    }:
        return False
    background_only = all(
        statement.decision_functions == ["background"]
         and statement.force in {"descriptive", "unclear"}
         and not statement.unresolved
        for statement in interpretation.statements
    )
    if not background_only and not front_stage_supported_indexes(batch, interpretation):
        return False
    coverage = source_statement_coverage(batch, interpretation, pending_front_wire(batch))
    # An exact match only routes to the established comparison path; it does
    # not certify clinical equivalence or silently discard the source.
    if any(entry.exact_official_excerpt_matches or entry.exact_procedure_excerpt_matches
           for entry in coverage):
        return False
    return set(target_review_indexes(interpretation, coverage, batch)) == set(
        range(len(interpretation.statements))
    )


@dataclass
class FrontStageFlowResult:
    responses: list[tuple[str, ProtocolControlAgentResponse]] = field(default_factory=list)
    review: SourceTargetReview | None = None
    review_validated: bool = False
    wire: ProtocolControlAgentWire | None = None
    alignment: SourceCandidateAlignment | None = None
    error: Exception | None = None
    error_code: str | None = None
    error_detail: dict[str, object] | None = None


def _target_action_established(batch, statement, target) -> bool:
    return target_action_established(batch, statement, target)


def build_front_target_review_prompt(batch, interpretation, coverage) -> str:
    action_proofs = [{
        "statement_index": index,
        "action_supported_target_ids": [
            target.official_code if hasattr(target, "official_code") else target.catalog_item_id
            for target in [*batch.known_official_targets, *batch.known_procedure_targets]
            if _target_action_established(batch, statement, target)
        ],
    } for index, statement in enumerate(interpretation.statements)]
    return build_source_target_review_prompt(batch, interpretation, coverage) + (
        "\n本次简单节点动作流程同时提供宿主已核的动作依据范围；这不是完整语义或时间核对的结论。"
        "只有 action_supported_target_ids 中的目标具备当前装配器可验证的动作依据，"
        "仍须核对对象、时间、条件及例外后才能报告完整覆盖。其他目录项保留为关联线索，"
        "不能仅凭项目名称或同一访视认定具体动作已覆盖。原文动作和范围明确但目标缺此依据时，"
        "选 additional_requirement 并说明差额；原文自身无法核清时选 unresolved。"
        "不得改写原文、替原文增加条件或把这些线索当成已经发布的新增规则。\n"
        "当前动作依据范围：" + json.dumps(action_proofs, ensure_ascii=False, sort_keys=True)
    )


def _review_error_detail(exc: SourceTargetReviewValidationError) -> dict[str, object]:
    return {
        "code": exc.code, "statement_id": exc.statement_index,
        "json_path": exc.json_path, "source_refs": list(exc.source_refs),
        "retry_class": exc.retry_class,
        "affected_dependents": list(exc.affected_dependents),
    }


def _correct_front_review(batch, interpretation, coverage, exc, transport):
    """One actual local proposal; unchanged siblings and full gates remain."""
    index = exc.statement_index
    entries = [entry for entry in coverage if entry.statement_index == index]
    if index is None or len(entries) != 1:
        raise exc
    reader = getattr(transport, "start_source_target_review", None)
    if not callable(reader):
        raise exc
    prompt = build_front_target_review_prompt(batch, interpretation, entries) + (
        "\n仅核对被拒绝的这一条，不重读或重答其他条目；返回 items 中恰好这一条。"
        "原文、已有目标及来源范围不变。上一项未经采信，不得原样重复被拒声明。"
        "不强制把失败改为新增要求或未知，不得因格式或程序错误要求研究者判断。"
        "只有原文关系本身无法核清才说明该关系的未决。\n"
        + json.dumps(_review_error_detail(exc), ensure_ascii=False, sort_keys=True)
    )
    response = reader(prompt=prompt)
    return response


def covered_front_wire(
    batch, interpretation, review, *, allow_additional_units: bool = False,
    retained_indexes: frozenset[int] = frozenset(),
) -> ProtocolControlAgentWire:
    """Whole-unit links require full coverage; mixed units keep point-level proof."""
    validate_front_review(batch, interpretation, review)
    if (len(review.items) != len(interpretation.statements)
            or any(item.statement_index not in retained_indexes and item.decision not in ({"covered_by_official", "covered_by_procedure", "background_context", "additional_requirement"}
                                        if allow_additional_units else
                                        {"covered_by_official", "covered_by_procedure", "background_context"})
                   for item in review.items)):
        raise ProtocolControlAgentWireValidationError(
            "FLOW_TARGET_COVERAGE_UNASSEMBLED", "已有覆盖和新增要求混合，尚无对应装配，保留全部来源")
    procedures = {target.catalog_item_id: target for target in batch.known_procedure_targets}
    officials = {target.official_code: target for target in batch.known_official_targets}
    pending_dispositions = {item.structure_unit_id: item for item in pending_front_wire(batch).dispositions}
    for item in review.items:
        if item.statement_index in retained_indexes or item.decision in {"additional_requirement", "background_context"}:
            continue
        statement = interpretation.statements[item.statement_index]
        target = (procedures if item.decision == "covered_by_procedure" else officials)[item.target_id]
        # A grounded noun label is a relation, not an action-bearing requirement.
        # Exact source containment is a bounded shortcut, not an equivalence oracle.
        if not _target_action_established(batch, statement, target):
            raise ProtocolControlAgentWireValidationError(
                "FLOW_TARGET_ACTION_UNESTABLISHED",
                "已有目录仅证明项目关联，尚未证明本条动作要求已被覆盖；保留来源，不自动省略要求")
    dispositions = []
    for unit in batch.owned_units:
        items = [item for item in review.items
                 if interpretation.statements[item.statement_index].structure_unit_id == unit.structure_unit_id]
        if any(item.statement_index in retained_indexes for item in items):
            dispositions.append(pending_dispositions[unit.structure_unit_id])
            continue
        kinds = {item.decision for item in items} - {"background_context"}
        if not kinds:
            if batch.owned_required_action_kinds_by_structure_unit_id.get(unit.structure_unit_id):
                raise ProtocolControlAgentWireValidationError(
                    "REQUIRED_ACTION_DISCARDED",
                    "冻结来源仍有独立动作，不能仅凭已枚举的背景陈述省略整段要求",
                    structure_unit_ids=[unit.structure_unit_id],
                )
            dispositions.append(ProtocolControlAgentWireDisposition(
                structure_unit_id=unit.structure_unit_id,
                disposition=StructureUnitDispositionKind.ADMINISTRATIVE_STATISTICAL_BACKGROUND,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="逐项有源核对确认为纯背景，不生成受试者义务",
            ))
            continue
        if "additional_requirement" in kinds and allow_additional_units:
            # No whole-unit coverage claim: the saved front review owns each
            # covered point, while the compiler appends only the new points.
            dispositions.append(pending_dispositions[unit.structure_unit_id])
            continue
        targets = sorted({item.target_id for item in items if item.target_id is not None})
        if len(kinds) != 1 or not targets or ("covered_by_official" in kinds and len(targets) != 1):
            raise ProtocolControlAgentWireValidationError(
                "FLOW_TARGET_COVERAGE_UNASSEMBLED", "同一来源单元的已有覆盖与新增要求或多种目录归属尚不能分别装配")
        dispositions.append(ProtocolControlAgentWireDisposition(
            structure_unit_id=unit.structure_unit_id,
            disposition=(StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY
                         if "covered_by_official" in kinds else StructureUnitDispositionKind.REQUIRED_PROCEDURE),
            linked_official_code=targets[0] if "covered_by_official" in kinds else None,
            linked_procedure_catalog_item_id=None,
            linked_procedure_catalog_item_ids=targets if "covered_by_procedure" in kinds else [],
            notes="逐项来源核对指向已有完整要求，未新增重复控制",
        ))
    return ProtocolControlAgentWire(wire_version=CONTROL_AGENT_WIRE_VERSION,
                                   dispositions=dispositions, candidate_drafts=[])


def prepare_front_stage_flow(
    batch: ProtocolControlDispositionBatch,
    interpretation: SourceInterpretation,
    transport,
    output_validator,
    *, review_seed: SourceTargetReview | None = None,
) -> FrontStageFlowResult:
    """No whole-wire reread on failure and no invented review declarations."""
    result = FrontStageFlowResult()
    phase = "source_review"
    try:
        if not supports_front_stage_flow(batch, interpretation):
            raise ValueError("本批来源不属于单阶段动作解释范围")
        pending = pending_front_wire(batch)
        coverage = source_statement_coverage(batch, interpretation, pending)
        if review_seed is None:
            response = transport.start_source_target_review(
                prompt=build_front_target_review_prompt(batch, interpretation, coverage),
            )
            result.responses.append((phase, response))
            result.review = SourceTargetReview.model_validate_json(response.text)
        else:
            result.review = review_seed.model_copy(deep=True)
        try:
            validate_source_target_review(batch, interpretation, coverage, result.review)
        except SourceTargetReviewValidationError as exc:
            # An unproven restored seed is not permission for another repair.
            if (review_seed is not None or exc.statement_index is None
                    or exc.code not in FRONT_REVIEW_CORRECTION_CODES):
                raise
            phase = "source_review_correction"
            response = _correct_front_review(
                batch, interpretation, coverage, exc, transport,
            )
            result.responses.append((phase, response))
            correction = SourceTargetReview.model_validate_json(response.text)
            selected = [entry for entry in coverage if entry.statement_index == exc.statement_index]
            validate_source_target_review(batch, interpretation, selected, correction)
            result.review = result.review.model_copy(update={"items": [
                correction.items[0] if item.statement_index == exc.statement_index else item
                for item in result.review.items
            ]})
            validate_source_target_review(batch, interpretation, coverage, result.review)
        result.review_validated = True
        supported = front_stage_supported_indexes(batch, interpretation)
        retained = [item for item in result.review.items
                    if item.decision not in {"additional_requirement", "covered_by_official", "covered_by_procedure", "background_context"}
                    or (item.decision == "additional_requirement" and (
                        item.statement_index not in supported
                        or not can_compile_stage_bound_requirement(batch, interpretation, item)))]
        retained_indexes = frozenset(item.statement_index for item in retained)
        if not retained and all(item.decision != "additional_requirement"
               for item in result.review.items):
            phase = "assembly"
            wire = covered_front_wire(batch, interpretation, result.review)
            final_coverage = source_statement_coverage(batch, interpretation, wire)
            required_indexes = set(target_review_indexes(interpretation, final_coverage, batch))
            validate_source_target_review(batch, interpretation, final_coverage,
                result.review.model_copy(update={"items": [
                    item for item in result.review.items if item.statement_index in required_indexes
                ]}))
            from .protocol_control_deconstructor import hydrate_protocol_control_agent_output
            output_validator(hydrate_protocol_control_agent_output(wire, batch))
            result.wire = wire
            result.error_code = None
            return result
        # Mixed physical units retain individual source-target decisions,
        # rather than lending one point's target link to its neighbours.
        phase = "assembly"
        pending = covered_front_wire(batch, interpretation, result.review, allow_additional_units=True,
                                     retained_indexes=retained_indexes)
        reviews = sorted((item for item in result.review.items if item.decision == "additional_requirement"
                          and item.statement_index not in retained_indexes),
                         key=lambda item: item.statement_index)
        if retained:
            result.error_detail = {
                "code": "FLOW_STATEMENTS_RETAINED",
                "retained_statements": [{
                    "statement_index": item.statement_index,
                    "structure_unit_id": interpretation.statements[item.statement_index].structure_unit_id,
                    "source_refs": [unit.source_ref for unit in batch.owned_units
                                    if unit.structure_unit_id == interpretation.statements[item.statement_index].structure_unit_id],
                    "json_path": f"source_front_target_review.items[{index}]",
                    "reason": ("source_review_unresolved" if item.decision == "unresolved"
                               or interpretation.statements[item.statement_index].unresolved
                               else "compiler_capability_gap"),
                    "retry_class": ("source_review" if item.decision == "unresolved"
                                    or interpretation.statements[item.statement_index].unresolved
                                    else "capability_review"),
                    "decision": item.decision,
                } for index, item in enumerate(result.review.items) if item.statement_index in retained_indexes],
                "completed_author_indexes": [],
            }
        # Preserve source order rather than trusting provider item ordering.
        authors = []
        for position, item in enumerate(reviews):
            phase = f"author:{item.statement_index}"
            response = transport.read_stage_bound_requirement(
                prompt=build_stage_bound_requirement_prompt(batch, interpretation, item),
            )
            result.responses.append((phase, response))
            phase = "assembly"
            compile_source_requirement_response(batch, interpretation, item, response)
            authors.append(response)
            # Freeze each accepted author through the same constructor and
            # validator; a later failure cannot erase its assembled artifact.
            result.wire, _, coverage = assemble_source_requirement_inserts(
                batch, interpretation, reviews[:position + 1], pending, authors, output_validator,
                validate_complete=not retained and position == len(reviews) - 1,
            )
            if result.error_detail is not None:
                result.error_detail["completed_author_indexes"] = [
                    accepted.statement_index for accepted in reviews[:position + 1]
                ]
        if not reviews:
            result.error_code = "FLOW_COMPILER_CAPABILITY_GAP" if any(
                item["reason"] == "compiler_capability_gap" for item in result.error_detail["retained_statements"]
            ) else "FLOW_SOURCE_SCOPE_UNRESOLVED"
            raise ValueError("本批已保留逐项来源核对；尚无可完整装配的新增要求，不生成采用结果")
        # A source quote alone does not prove the chosen observation policy.
        # Reuse the existing fresh-session reviewer and source-bound proof.
        phase = "candidate_review"
        pairs = [(item.statement_index, index) for item in reviews
                 for index in coverage[item.statement_index].candidate_indexes]
        if len(pairs) != len(reviews):
            raise ProtocolControlAgentWireValidationError(
                "FLOW_CANDIDATE_SCOPE_UNRESOLVED", "装配要求尚不能逐项对应独立原文要求")
        response = transport.start_source_candidate_alignment(
            prompt=build_candidate_alignment_prompt(batch, interpretation, result.wire, pairs),
        )
        result.responses.append((phase, response))
        alignment = SourceCandidateAlignment.model_validate_json(response.text)
        validate_candidate_alignment(batch, interpretation, coverage, result.wire, alignment)
        result.alignment = bind_candidate_alignment(
            batch, interpretation, coverage, result.wire, alignment, response.text,
        )
        if (sorted((item.statement_index, item.candidate_index) for item in alignment.items)
                != sorted(pairs) or any(item.decision != "fully_expressed" for item in alignment.items)):
            raise ProtocolControlAgentWireValidationError(
                "FLOW_CANDIDATE_SEMANTICS_UNVERIFIED", "要求的结果条件或其他含义尚未核实，保留原答，不继续自动改写")
        if retained:
            result.error_code = "FLOW_COMPILER_CAPABILITY_GAP" if any(
                item["reason"] == "compiler_capability_gap" for item in result.error_detail["retained_statements"]
            ) else "FLOW_SOURCE_SCOPE_UNRESOLVED"
            raise ValueError("已保存可装配要求及其核对依据；其余具体来源仍待处理，整批未完成、未采用")
    except Exception as exc:  # product boundary; retained without parent reread
        result.error = exc
        if isinstance(exc, SourceTargetReviewValidationError):
            result.error_detail = _review_error_detail(exc)
        result.error_code = result.error_code or _failure_code(exc) or (
            "FLOW_ASSEMBLY_INVALID" if phase == "assembly" else
            "FLOW_RESPONSE_INVALID" if result.responses and result.responses[-1][0] == phase else
            "FLOW_TRANSPORT_FAILED"
        )
    return result
