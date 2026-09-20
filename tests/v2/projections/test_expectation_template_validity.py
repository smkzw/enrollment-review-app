"""Source validity is protocol data, not a disease-specific evaluator heuristic."""
import pytest
from pydantic import ValidationError

from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.rules import TimeQuantity, TimeUnit, WorkflowStage
from app.domain.contracts.enums import ReviewStage
from app.projections.evidence_expectation_templates import (
    project_evidence_expectation_templates,
    verify_template_identity,
)
from tests.v2.protocols.test_storage_slice4 import _rule_set


def _project(window=None):
    rules = _rule_set()
    requirement = rules.rules[0].components[0].evidence_requirements[0]
    requirement.source_validity_window = window
    stage = WorkflowStage(
        workflow_stage_id="ruleset:slice4:1:screen",
        stage=ReviewStage.SCREENING,
        display_name="筛选期",
        visit_instance="筛选期",
        due_requirement_ids=[
            item.requirement_id
            for rule in rules.rules
            for component in rule.components
            for item in component.evidence_requirements
        ],
    )
    templates = project_evidence_expectation_templates(
        rule_set=rules, workflow_stages=[stage]
    )
    return next(item for item in templates if item.requirement_id == requirement.requirement_id)


@pytest.mark.parametrize("unit", list(TimeUnit))
def test_projection_preserves_protocol_validity_and_binds_hash(unit):
    window = TimeQuantity(value=2, unit=unit)
    template = _project(window)
    assert template.source_validity_window == window
    assert template.projection_sha256 != _project().projection_sha256
    verify_template_identity(template)
    payload = template.model_dump(mode="json")
    payload["source_validity_window"]["value"] = 3
    with pytest.raises(ValidationError, match="投影哈希"):
        EvidenceExpectationTemplate.model_validate(payload)


def test_legacy_template_without_validity_remains_readable():
    template = _project()
    payload = template.model_dump(mode="json")
    payload.pop("source_validity_window", None)
    restored = EvidenceExpectationTemplate.model_validate(payload)
    verify_template_identity(restored)
    assert restored.projection_sha256 == template.projection_sha256
    assert restored.model_dump(mode="json") == payload


def test_storage_preserves_validity_and_rejects_a_self_consistent_omission(session):
    from app.storage.repositories import (
        save_expectation_templates, list_expectation_templates, ScopeViolationError,
    )
    from tests.v2.protocols.test_storage_slice4 import _seed_template_context

    window = TimeQuantity(value=2, unit=TimeUnit.MONTH)
    rule_set, _, templates = _seed_template_context(session, window)
    expected = next(item for item in templates if item.source_validity_window is not None)
    # An internally valid legacy hash is not sufficient to match the published rule.
    from app.projections.evidence_expectation_templates import template_projection_sha256
    payload = expected.model_dump(mode="json")
    payload["source_validity_window"] = None
    payload["projection_sha256"] = template_projection_sha256(
        rule_set_id=expected.rule_set_id, revision=expected.rule_set_revision,
        requirement_id=expected.requirement_id, due_stage=expected.due_stage,
        study_phase=expected.study_phase, workflow_stage_id=expected.workflow_stage_id,
        fact_type=expected.fact_type, required_source_types=expected.required_source_types,
        requires_contemporaneous_objective_source=expected.requires_contemporaneous_objective_source,
        allows_screening_record_transcription=expected.allows_screening_record_transcription,
        description=expected.description,
    )
    stripped = EvidenceExpectationTemplate.model_validate(payload)
    with pytest.raises(ScopeViolationError, match="资料语义"):
        save_expectation_templates(session, [stripped])
    save_expectation_templates(session, templates)
    session.flush()
    loaded = list_expectation_templates(session, rule_set.rule_set_id, rule_set.revision)
    assert next(item for item in loaded if item.template_id == expected.template_id).source_validity_window == window
