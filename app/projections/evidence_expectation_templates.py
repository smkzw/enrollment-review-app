"""无受试者 EvidenceExpectation 模板投影（Phase 3 切片 4）。

从一份已发布的 RuleSet 与其 WorkflowStage 确定性投影出资料核对期望模板：
模板不含任何 subject/review-episode 状态，``template_id`` 与
``projection_sha256`` 由稳定身份字段计算，同一 RuleSet revision 的同一
requirement 永远得到同一模板。Phase 4/5 创建 ReviewEpisode 时再由此模板
投影具体受试者期望。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.rules import (
    EvidenceRequirement,
    RuleSet,
    WorkflowStage,
)
from app.domain.publication import canonical_hash


class ExpectationTemplateProjectionError(ValueError):
    """模板投影的前提（已发布 RuleSet/workflow 的到期闭包）不成立。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str) -> None:
    raise ExpectationTemplateProjectionError(code, message)


def _all_requirements(
    rule_set: RuleSet,
    procedure_requirements: Sequence[EvidenceRequirement],
) -> dict[str, EvidenceRequirement]:
    requirements: dict[str, EvidenceRequirement] = {}
    for rule in rule_set.rules:
        for component in rule.components:
            for requirement in component.evidence_requirements:
                if requirement.requirement_id in requirements:
                    _fail(
                        "duplicate_requirement",
                        f"资料要求 ID 重复：{requirement.requirement_id}",
                    )
                requirements[requirement.requirement_id] = requirement
    for requirement in procedure_requirements:
        if requirement.requirement_id in requirements:
            _fail(
                "duplicate_requirement",
                f"流程资料要求 ID 与规则资料要求重复：{requirement.requirement_id}",
            )
        requirements[requirement.requirement_id] = requirement
    return requirements


def project_evidence_expectation_templates(
    *,
    rule_set: RuleSet,
    workflow_stages: Sequence[WorkflowStage],
    procedure_requirements: Sequence[EvidenceRequirement] = (),
    created_at: datetime | None = None,
) -> list[EvidenceExpectationTemplate]:
    """投影一个 RuleSet revision 的全部资料核对期望模板。

    每个资料要求必须在 WorkflowStage 中且仅到期一次，到期阶段必须与该要求
    自身 ``due_stage`` 一致；不满足时抛 :class:`ExpectationTemplateProjectionError`，
    绝不投影出悬空期望。
    """
    requirements = _all_requirements(rule_set, procedure_requirements)
    due_stage_by_requirement: dict[str, str] = {}
    stage_by_requirement: dict[str, WorkflowStage] = {}
    for stage in workflow_stages:
        for requirement_id in stage.due_requirement_ids:
            if requirement_id in due_stage_by_requirement:
                _fail(
                    "requirement_due_twice",
                    f"资料要求 {requirement_id} 在多个审核节点到期",
                )
            if requirement_id not in requirements:
                _fail(
                    "unknown_requirement",
                    f"审核节点引用了不存在的资料要求：{requirement_id}",
                )
            due_stage_by_requirement[requirement_id] = stage.stage
            stage_by_requirement[requirement_id] = stage
    missing = sorted(set(requirements) - set(due_stage_by_requirement))
    if missing:
        _fail(
            "requirement_without_due_stage",
            f"以下资料要求没有到期节点：{'、'.join(missing)}",
        )
    templates: list[EvidenceExpectationTemplate] = []
    for requirement_id, requirement in sorted(requirements.items()):
        stage = stage_by_requirement[requirement_id]
        if requirement.due_stage.value != due_stage_by_requirement[requirement_id]:
            _fail(
                "due_stage_mismatch",
                f"资料要求 {requirement_id} 的 due_stage 与审核节点不一致",
            )
        projection_sha256 = canonical_hash(
            {
                "projection": "evidence_expectation_template/v1",
                "rule_set_id": rule_set.rule_set_id,
                "rule_set_revision": rule_set.revision,
                "requirement_id": requirement.requirement_id,
                "due_stage": requirement.due_stage.value,
                "study_phase": rule_set.study_phase.value,
                "workflow_stage_id": stage.workflow_stage_id,
                "fact_type": requirement.fact_type,
                "required_source_types": sorted(
                    set(requirement.required_source_types)
                ),
                "requires_contemporaneous_objective_source": (
                    requirement.requires_contemporaneous_objective_source
                ),
                "allows_screening_record_transcription": (
                    requirement.allows_screening_record_transcription
                ),
                "description": requirement.description,
            }
        )
        template_id = (
            "expectation-template:"
            + canonical_hash(
                {
                    "rule_set_id": rule_set.rule_set_id,
                    "rule_set_revision": rule_set.revision,
                    "requirement_id": requirement.requirement_id,
                }
            )[:32]
        )
        templates.append(
            EvidenceExpectationTemplate(
                template_id=template_id,
                rule_set_id=rule_set.rule_set_id,
                rule_set_revision=rule_set.revision,
                requirement_id=requirement.requirement_id,
                due_stage=requirement.due_stage,
                study_phase=rule_set.study_phase,
                workflow_stage_id=stage.workflow_stage_id,
                fact_type=requirement.fact_type,
                required_source_types=list(requirement.required_source_types),
                requires_contemporaneous_objective_source=(
                    requirement.requires_contemporaneous_objective_source
                ),
                allows_screening_record_transcription=(
                    requirement.allows_screening_record_transcription
                ),
                description=requirement.description,
                projection_sha256=projection_sha256,
                created_at=created_at or datetime.now(UTC),
            )
        )
    return templates


def template_identity(
    rule_set_id: str, revision: int, requirement_id: str
) -> str:
    """稳定模板 ID；与模板合同校验使用同一身份算法。"""

    return (
        "expectation-template:"
        + canonical_hash(
            {
                "rule_set_id": rule_set_id,
                "rule_set_revision": revision,
                "requirement_id": requirement_id,
            }
        )[:32]
    )


def template_projection_sha256(
    *,
    rule_set_id: str,
    revision: int,
    requirement_id: str,
    due_stage,
    study_phase,
    workflow_stage_id: str | None,
    fact_type: str | None = None,
    required_source_types: Sequence[str] = (),
    requires_contemporaneous_objective_source: bool | None = None,
    allows_screening_record_transcription: bool | None = None,
    description: str | None = None,
) -> str:
    """稳定投影哈希；与模板合同校验使用同一算法。

    哈希覆盖模板的全部下游执行字段（含 required_source_types），同一
    RuleSet revision 的同一 requirement 必须投影出同一模板内容。
    """

    return canonical_hash(
        {
            "projection": "evidence_expectation_template/v1",
            "rule_set_id": rule_set_id,
            "rule_set_revision": revision,
            "requirement_id": requirement_id,
            "due_stage": due_stage.value,
            "study_phase": study_phase.value,
            "workflow_stage_id": workflow_stage_id,
            "fact_type": fact_type,
            "required_source_types": sorted(set(required_source_types)),
            "requires_contemporaneous_objective_source": (
                requires_contemporaneous_objective_source
            ),
            "allows_screening_record_transcription": (
                allows_screening_record_transcription
            ),
            "description": description,
        }
    )


def verify_template_identity(template: EvidenceExpectationTemplate) -> None:
    """读取侧完整性校验：模板 ID/投影哈希必须与稳定身份一致。"""

    if template.template_id != template_identity(
        template.rule_set_id, template.rule_set_revision, template.requirement_id
    ):
        _fail("template_identity_mismatch", "模板 ID 与稳定身份不一致")
    if template.projection_sha256 != template_projection_sha256(
        rule_set_id=template.rule_set_id,
        revision=template.rule_set_revision,
        requirement_id=template.requirement_id,
        due_stage=template.due_stage,
        study_phase=template.study_phase,
        workflow_stage_id=template.workflow_stage_id,
        fact_type=template.fact_type,
        required_source_types=template.required_source_types,
        requires_contemporaneous_objective_source=(
            template.requires_contemporaneous_objective_source
        ),
        allows_screening_record_transcription=(
            template.allows_screening_record_transcription
        ),
        description=template.description,
    ):
        _fail("template_projection_mismatch", "模板投影哈希与身份字段不一致")


__all__ = [
    "ExpectationTemplateProjectionError",
    "project_evidence_expectation_templates",
    "template_identity",
    "template_projection_sha256",
    "verify_template_identity",
]
