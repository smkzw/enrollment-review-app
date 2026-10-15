"""Source-scoped follow-up wording for the V2 publication path."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.contracts.enums import ActionTarget, GapType, ReviewStage
from app.domain.contracts.review import FinalAssessment
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.policies import ACTION_CONTENT, STAGE_RANK

REVIEW_ACTION_DIRECTIVE_VERSION = "review-action-directive/v3"


@dataclass(frozen=True)
class ReviewActionDirective:
    target_party: ActionTarget
    requested_action: str
    acceptable_evidence: str
    due_stage: ReviewStage
    recompute_scope: tuple[str, ...]
    trigger_locator_id: str | None


def derive_review_action_directive(
    *, assessment: FinalAssessment, context: ReviewContextSnapshotV2, gap_type: GapType,
) -> ReviewActionDirective:
    """Describe an existing assessment gap, without deciding or closing it."""
    authority = context.authority
    if (
        assessment.schema_version != "review/v2"
        or assessment.review_run_id != context.review_run_id
        or gap_type not in assessment.gap_types
        or any(getattr(assessment, key) != getattr(authority, key) for key in (
            "project_id", "subject_id", "review_episode_id", "protocol_version_id",
            "rule_set_id", "rule_set_revision", "evidence_snapshot_v2_id",
            "complete_processing_revision_id",
        ))
    ):
        raise ValueError("办理要求必须来自本次审核已记录的具体缺口")
    clause = next((item for item in context.clause_pack.clauses
                   if item.rule_component_id == assessment.rule_component_id), None)
    if clause is None:
        raise ValueError("办理要求不属于本次保存的方案条款")
    requirements = {item.requirement_id: item for item in clause.evidence_requirements}
    templates = {item.template_id: item for item in context.expectation_templates}
    relevant = [item for item in context.expectations
                if templates[item.template_id].requirement_id in requirements
                and item.gap_type == gap_type]
    stage = context.review_episode.stage
    if gap_type == GapType.FUTURE_STAGE_NOT_DUE:
        future = [item.due_stage for item in requirements.values()
                  if STAGE_RANK[item.due_stage] > STAGE_RANK[stage]]
        if not future:
            raise ValueError("后续办理必须对应尚未到期的方案要求")
        due_stage = min(future, key=STAGE_RANK.__getitem__)
    else:
        due_stage = max([stage, *(templates[item.template_id].due_stage for item in relevant)],
                        key=STAGE_RANK.__getitem__)
    target, action, evidence = ACTION_CONTENT[gap_type]
    if gap_type == GapType.OBSERVATION_UNVERIFIED and GapType.PROFESSIONAL_JUDGMENT in assessment.gap_types:
        action = (
            "核对本条仍未核实的原始资料，明确对应的检查、时间及对象。"
            "已列明需研究者补充的书面判断，按相应事项办理。"
        )
    if gap_type == GapType.OBSERVATION_UNVERIFIED and any(
        "half_life_missing" in item.reason_codes for item in assessment.predicate_observations or ()
    ):
        action += " 本条洗脱时间还缺少适用于相关用药的半衰期依据，暂不能完成计算。"
        evidence += " 请提供可核对的半衰期出处、适用对象及数值单位，不以药名或推测值代替；补齐后重新审核。"
    if gap_type == GapType.DATE_OR_ANCHOR_MISSING and any(
        "half_life_time_precision_insufficient" in item.reason_codes for item in assessment.predicate_observations or ()
    ):
        action += " 本条处于洗脱时间边界，仅有日期还不能确定实际间隔，不应补填推测时刻。"
        evidence += " 核对停药与相应研究节点的实际时间记录；现有日期不能证明的部分继续保留待核实。"
    descriptions = sorted({templates[item.template_id].description.strip() for item in relevant})
    if descriptions:
        action = f"{'；'.join(descriptions)}：{action}"
    locators = sorted({*(assessment.locator_ids or ()),
                       *(locator for item in relevant for locator in item.locator_ids)})
    return ReviewActionDirective(
        target_party=target, requested_action=action, acceptable_evidence=evidence,
        due_stage=due_stage, recompute_scope=(clause.rule_component_id,),
        trigger_locator_id=locators[0] if locators else None,
    )
