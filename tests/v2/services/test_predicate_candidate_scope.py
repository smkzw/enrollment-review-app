"""Unrelated components must not expand one another's candidate vocabulary."""

from types import SimpleNamespace

import pytest

from app.services import eligibility_review_projection as module
from app.services import component_review
from app.projections.evidence_expectation_templates import project_evidence_expectation_templates
from tests.v2.storage.test_fact_repositories import _seed_chain
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


@pytest.mark.parametrize("categories", [
    ("candidate-category-a", "candidate-category-b"),
    ("另一类资料", "不同资料"),
    ("candidate-category-b", "candidate-category-a"),
])
def test_candidate_types_stay_with_their_own_component(session, monkeypatch, categories):
    chain = _seed_chain(session, prefix="predicate-scope")
    fixture = FIXTURES[0]
    templates = project_evidence_expectation_templates(
        rule_set=fixture.rule_set, workflow_stages=fixture.workflow_stages,
    )
    monkeypatch.setattr(module, "list_expectation_templates", lambda *_: templates)
    project = module.project_clause_pack
    captured = []

    def clauses(rule_set):
        clause = project(rule_set).clauses[0]
        requirement = clause.evidence_requirements[0]
        return SimpleNamespace(clauses=tuple(clause.model_copy(update={
            "rule_component_id": f"component-{index}",
            "evidence_requirements": (requirement.model_copy(update={"fact_type": fact_type}),),
        }) for index, fact_type in enumerate(categories)))

    evaluate = component_review.evaluate_component

    def checked(component, context, **kwargs):
        captured.append({value for values in context.predicate_fact_type_aliases.values() for value in values})
        return evaluate(component, context, **kwargs)

    monkeypatch.setattr(module, "project_clause_pack", clauses)
    monkeypatch.setattr(component_review, "evaluate_component", checked)
    module.EligibilityReviewProjectionService().project(session, chain["episode_id"])
    assert captured == [{category} for category in categories]
