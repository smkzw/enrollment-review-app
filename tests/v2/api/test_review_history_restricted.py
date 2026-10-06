"""Frozen-source presentation only; no publication/adoption or clinical data."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v2.review_history import (
    ReviewHistoryRestrictedRequirementDTO,
    ReviewHistoryRunResponse,
    _restricted_requirement_dtos,
)
from app.domain.contracts.protocol_controls import RestrictedProtocolControlStatement
from app.domain.publication import canonical_hash
from tests.v2.services.test_receipt_verified_work_draft_consumer import (
    _aligned_review_context,
    _synthetic_material,
)


def test_frozen_official_and_control_limitations_remain_sources_not_assessments():
    authority, rules, _, fact, episode, _ = _synthetic_material()
    context = _aligned_review_context(
        authority=authority, rule_set=rules, clinical_fact=fact, episode=episode,
    )
    before = canonical_hash(context.model_dump(mode="json"))
    official = _restricted_requirement_dtos(context)
    assert len(official) == 1
    assert official[0].requirement_id == "component-restricted-sibling"
    assert official[0].source_excerpts == ["同源受限兄弟要求原文"]
    assert official[0].limitation_kind == "interpretation_unresolved"
    assert canonical_hash(context.model_dump(mode="json")) == before

    statement = RestrictedProtocolControlStatement(
        restricted_statement_id="limited-current-period",
        source_structure_unit_id="structure-period", source_statement_index=0,
        source_quote="核对持续期间。", source_span_ids=["span-period"],
        limitation_kind="consumer_unavailable", unresolved_dimensions=["期间计算尚未支持"],
        scope_quote="符合相应定义时", time_words=["筛选时"], exception_words="特殊情况除外",
        affected_stage="筛选期至治疗结束", decision_functions=["time_validity"], source_force="prohibited",
    )
    # Explicit presentation seam, not a forged published control catalog.
    source = SimpleNamespace(clause_pack=SimpleNamespace(
        restricted_clauses=context.clause_pack.restricted_clauses,
        control_publication=SimpleNamespace(catalog=SimpleNamespace(restricted_statements=[statement])),
    ))
    output = _restricted_requirement_dtos(source)
    assert len(output) == 2
    assert output[1].origin == "control"
    assert output[1].display_label == "方案补充要求"
    assert output[1].scope_quote == "符合相应定义时"
    assert output[1].time_words == ["筛选时"]
    assert output[1].exception_words == "特殊情况除外"
    assert output[1].affected_stage == "筛选期至治疗结束"
    assert output[1].decision_functions == ["time_validity"]
    assert output[1].source_force == "prohibited"
    assert all("decision" not in item.model_dump() and "fact_ids" not in item.model_dump() for item in output)
    assert canonical_hash(context.model_dump(mode="json")) == before


@pytest.mark.parametrize("mutation", [
    {"limitation_kind": "satisfied"}, {"source_span_ids": []},
    {"source_excerpts": []}, {"unresolved_dimensions": []}, {"decision": "inclusion_met"},
])
def test_limited_requirement_cannot_become_a_fabricated_assessment(mutation):
    data = dict(origin="official", requirement_id="limited", display_label="IN-01-b",
                title="范围待核", source_text="原文要求", source_span_ids=["span"],
                source_excerpts=["原文要求"], limitation_kind="interpretation_unresolved",
                unresolved_dimensions=["对象尚待核清"])
    with pytest.raises(ValidationError):
        ReviewHistoryRestrictedRequirementDTO.model_validate({**data, **mutation})


def test_history_http_uses_the_frozen_source_not_current_material(client, monkeypatch):
    from app.domain.contracts.review import ReviewRun
    from tests.v2.services.test_receipt_verified_work_draft_consumer import NOW

    authority, rules, _, fact, episode, _ = _synthetic_material()
    context = _aligned_review_context(
        authority=authority, rule_set=rules, clinical_fact=fact, episode=episode,
    )
    before = canonical_hash(context.model_dump(mode="json"))
    run = ReviewRun(
        schema_version="review/v2", review_run_id=context.review_run_id,
        review_episode_id=authority.review_episode_id, protocol_version_id=authority.protocol_version_id,
        rule_set_revision=authority.rule_set_revision, episode_revision=authority.episode_revision,
        context_id=context.context_id, evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id, started_at=NOW,
    )
    # The history storage boundary is explicit; HTTP/DTO consume a real typed frozen context.
    detail = SimpleNamespace(run=run, context=context, status="in_progress", controls=(),
                             assessments=(), actions=(), missing_rule_component_ids=("component-a",),
                             evidence_locators=(), missing_protocol_control_ids=())
    monkeypatch.setattr("app.api.v2.review_history.get_run", lambda *args: detail)
    url = (f"/api/v2/subjects/{authority.subject_id}/review-episodes/"
           f"{authority.review_episode_id}/review-runs/{context.review_run_id}")
    response = client.get(url)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["status"] == "in_progress"
    assert body["missing_rule_component_ids"] == ["component-a"]
    assert body["assessments"] == []
    assert body["restricted_requirements"][0]["source_span_ids"] == ["span-restricted-sibling"]
    assert canonical_hash(context.model_dump(mode="json")) == before
    for kind in ("duplicate", "dangling"):
        changed = {**body, "restricted_requirements": [dict(body["restricted_requirements"][0])]}
        if kind == "duplicate":
            changed["restricted_requirements"] *= 2
        else:
            changed["restricted_requirements"][0]["dependency_refs"] = ["missing-requirement"]
        with pytest.raises(ValidationError, match="身份不一致"):
            ReviewHistoryRunResponse.model_validate(changed)
