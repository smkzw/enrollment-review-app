"""无受试者 EvidenceExpectation 模板投影：确定性身份、无受试者状态。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.contracts.enums import ReviewStage, StudyPhase
from app.domain.contracts.evidence import EvidenceExpectation
from app.domain.contracts.rules import EvidenceRequirement, WorkflowStage
from app.projections.evidence_expectation_templates import (
    ExpectationTemplateProjectionError,
    project_evidence_expectation_templates,
    template_identity,
    template_projection_sha256,
    verify_template_identity,
)

from tests.v2.protocols.slice4_helpers import NOW
from tests.v2.protocols.test_storage_slice4 import _procedure_requirements, _rule_set


def _stages(rule_set_id: str = "ruleset:slice4") -> list[WorkflowStage]:
    return [
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:1:stage-screening",
            stage=ReviewStage.SCREENING,
            display_name="筛选期审核",
            visit_instance="筛选期 D-28~D-1",
            due_requirement_ids=[
                "req-in",
                "req-ex",
                "requirement:procedure:screen",
            ],
        ),
        WorkflowStage(
            workflow_stage_id=f"{rule_set_id}:1:stage-baseline",
            stage=ReviewStage.BASELINE,
            display_name="基线审核",
            visit_instance="基线 D1",
            due_requirement_ids=["requirement:procedure:baseline"],
        ),
    ]


def test_projection_covers_all_requirements_with_stable_identity() -> None:
    rule_set = _rule_set()
    templates = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=_stages(),
        procedure_requirements=_procedure_requirements(),
        created_at=NOW,
    )
    assert sorted(item.requirement_id for item in templates) == [
        "req-ex",
        "req-in",
        "requirement:procedure:baseline",
        "requirement:procedure:screen",
    ]
    for template in templates:
        # 无任何受试者/review-episode 状态
        assert not hasattr(template, "subject_id")
        assert not hasattr(template, "review_episode_id")
        assert template.study_phase == StudyPhase.PHASE_II
        assert template.template_id == template_identity(
            rule_set.rule_set_id, rule_set.revision, template.requirement_id
        )
        # 投影哈希覆盖全部下游执行字段（含 required_source_types）
        assert template.projection_sha256 == template_projection_sha256(
            rule_set_id=rule_set.rule_set_id,
            revision=rule_set.revision,
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
        )
        verify_template_identity(template)


def test_projection_carries_evidence_semantics_fields() -> None:
    """模板必须完整投影 EvidenceRequirement 下游执行所需字段。"""
    rule_set = _rule_set()
    procedure = _procedure_requirements()[0].model_copy(
        update={
            "required_source_types": ["正式检验报告", "原始记录"],
            "requires_contemporaneous_objective_source": True,
            "allows_screening_record_transcription": False,
            "description": "必须提供同期客观来源的正式检验报告",
        }
    )
    templates = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=_stages(),
        procedure_requirements=[procedure, _procedure_requirements()[1]],
        created_at=NOW,
    )
    screen = next(
        item
        for item in templates
        if item.requirement_id == "requirement:procedure:screen"
    )
    assert screen.required_source_types == ["正式检验报告", "原始记录"]
    assert screen.requires_contemporaneous_objective_source is True
    assert screen.allows_screening_record_transcription is False
    assert screen.description == "必须提供同期客观来源的正式检验报告"
    verify_template_identity(screen)


def test_projection_is_deterministic_across_rebuilds() -> None:
    rule_set = _rule_set()
    first = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=_stages(),
        procedure_requirements=_procedure_requirements(),
        created_at=NOW,
    )
    second = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=_stages(),
        procedure_requirements=_procedure_requirements(),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    # 身份字段（template_id/projection_sha256）与投影时间无关，永远稳定；
    # created_at 只是重建时刻戳，不参与身份。
    assert [item.template_id for item in first] == [item.template_id for item in second]
    assert [item.projection_sha256 for item in first] == [
        item.projection_sha256 for item in second
    ]
    for item in first:
        assert item.projection_sha256 == template_projection_sha256(
            rule_set_id=item.rule_set_id,
            revision=item.rule_set_revision,
            requirement_id=item.requirement_id,
            due_stage=item.due_stage,
            study_phase=item.study_phase,
            workflow_stage_id=item.workflow_stage_id,
            fact_type=item.fact_type,
            required_source_types=item.required_source_types,
            requires_contemporaneous_objective_source=(
                item.requires_contemporaneous_objective_source
            ),
            allows_screening_record_transcription=(
                item.allows_screening_record_transcription
            ),
            description=item.description,
        )


def test_screening_and_baseline_instances_keep_separate_templates() -> None:
    """同名操作在筛选与基线投影为两个模板，绝不跨访视去重。"""
    rule_set = _rule_set()
    templates = project_evidence_expectation_templates(
        rule_set=rule_set,
        workflow_stages=_stages(),
        procedure_requirements=_procedure_requirements(),
        created_at=NOW,
    )
    by_requirement = {item.requirement_id: item for item in templates}
    screen = by_requirement["requirement:procedure:screen"]
    baseline = by_requirement["requirement:procedure:baseline"]
    assert screen.template_id != baseline.template_id
    assert screen.workflow_stage_id.endswith("stage-screening")
    assert baseline.workflow_stage_id.endswith("stage-baseline")
    assert screen.due_stage == ReviewStage.SCREENING
    assert baseline.due_stage == ReviewStage.BASELINE


def test_requirement_due_in_multiple_stages_is_rejected() -> None:
    rule_set = _rule_set()
    stages = _stages()
    stages[1] = stages[1].model_copy(
        update={"due_requirement_ids": ["requirement:procedure:screen"]}
    )
    with pytest.raises(ExpectationTemplateProjectionError) as exc_info:
        project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=stages,
            procedure_requirements=_procedure_requirements(),
            created_at=NOW,
        )
    assert exc_info.value.code == "requirement_due_twice"


def test_requirement_without_due_stage_is_rejected() -> None:
    rule_set = _rule_set()
    stages = _stages()
    stages[0] = stages[0].model_copy(
        update={"due_requirement_ids": ["requirement:procedure:screen"]}
    )
    with pytest.raises(ExpectationTemplateProjectionError) as exc_info:
        project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=stages,
            procedure_requirements=_procedure_requirements(),
            created_at=NOW,
        )
    assert exc_info.value.code == "requirement_without_due_stage"


def test_stage_referencing_unknown_requirement_is_rejected() -> None:
    rule_set = _rule_set()
    stages = _stages()
    stages[0] = stages[0].model_copy(
        update={"due_requirement_ids": ["requirement:ghost"]}
    )
    with pytest.raises(ExpectationTemplateProjectionError) as exc_info:
        project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=stages,
            procedure_requirements=[],
            created_at=NOW,
        )
    assert exc_info.value.code == "unknown_requirement"


def test_due_stage_mismatch_between_requirement_and_stage_is_rejected() -> None:
    rule_set = _rule_set()
    mismatched = EvidenceRequirement(
        requirement_id="requirement:procedure:screen",
        procedure_catalog_item_id="procedure:screening:lab",
        fact_type="方案要求事实",
        due_stage=ReviewStage.BASELINE,  # 与节点筛选不一致
        description="核对筛选期正式原始资料",
    )
    with pytest.raises(ExpectationTemplateProjectionError) as exc_info:
        project_evidence_expectation_templates(
            rule_set=rule_set,
            workflow_stages=_stages(),
            procedure_requirements=[mismatched, _procedure_requirements()[1]],
            created_at=NOW,
        )
    assert exc_info.value.code == "due_stage_mismatch"


def test_template_contract_rejects_subject_state_fields() -> None:
    """模板合同不携带受试者状态：构造带 subject 字段的对象必须失败。"""
    from app.domain.contracts.evidence import EvidenceExpectationTemplate

    template = project_evidence_expectation_templates(
        rule_set=_rule_set(),
        workflow_stages=_stages(),
        procedure_requirements=_procedure_requirements(),
        created_at=NOW,
    )[0]
    with pytest.raises(ValueError):
        EvidenceExpectationTemplate.model_validate(
            {
                **template.model_dump(mode="json"),
                "subject_id": "subject-1",
            }
        )
    # 受试者期望仍是另一份合同：模板不能冒充期望
    assert template.__class__ is not EvidenceExpectation
