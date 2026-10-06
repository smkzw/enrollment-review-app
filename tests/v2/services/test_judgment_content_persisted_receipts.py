"""Synthetic transport -> persisted jobs/receipts -> content/work-draft verification.

Frozen source/context and search provenance are fixture seams, not clinical proof.
Actual candidate, qualification, content JobRunner, ArtifactStore and receipt
verification run unchanged. No network, real materials or adoption authority.
"""
import json

import pytest

from app.domain.contracts.judgment_search import JudgmentSearchCoverageSummary
from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services import judgment_content_input
from app.services.binding_qualification import BindingQualificationJobExecutor, enqueue_binding_qualification
from app.services.judgment_content_job import JudgmentContentJobExecutor, _enqueue_content_job
from app.services.judgment_content_receipts import verify_completed_judgment_content
from app.services.judgment_fact_linkage import judgment_content_input_version, link_judgment_excerpts
from app.services.predicate_binding_job import PredicateBindingJobExecutor, enqueue_predicate_candidates
from app.services.qualified_binding_selection import build_receipt_verified_work_draft_selections
from app.storage.models import JobRecord
from app.storage.codecs import encode_value
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.runner import JobRunner
from tests.v2.llm.test_predicate_binding_candidates import _route
from tests.v2.services.test_receipt_verified_work_draft_consumer import (
    _synthetic_material, _aligned_review_context, _qualification_payload_for_messages, REQUIREMENT_ID,
)


@pytest.mark.parametrize("version", [1, 2])
def test_nonempty_persisted_content_receipts_and_actual_work_draft_version_gate(
    session_factory, data_paths, monkeypatch, version,
):
    authority, rules, frozen, fact, episode, answer = _synthetic_material()
    context = _aligned_review_context(authority=authority, rule_set=rules, clinical_fact=fact, episode=episode)
    monkeypatch.setattr("app.storage.review_context_repository.ReviewContextV2Repository.get",
        lambda _self, _id: context)
    monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_: rules)
    for module in ("predicate_binding_job", "binding_qualification"):
        monkeypatch.setattr(f"app.services.{module}.build_predicate_binding_frozen_input", lambda *a, **k: frozen)
    locator = frozen.locators[0]
    summary = JudgmentSearchCoverageSummary.model_validate({
        "scope_sha256": "d" * 64, "requirement_id": REQUIREMENT_ID, "status": "candidates_present",
        "found_candidates": [{"lane": "main-A", "provider": "synthetic", "model": "synthetic",
            "source_document_version_id": locator.source_document_version_id,
            "page_artifact_id": locator.page_artifact_id, "page_number": locator.page_number,
            "page_image_sha256": "e" * 64, "channel": "printed_analysis",
            "candidates": [{"text": frozen.facts[0].assertion_basis.assertion_text}]}],
    })
    # Synthetic search seam: real linkage algorithm, not a fake accepted flag.
    monkeypatch.setattr(judgment_content_input, "load_prepared_judgment_links",
        lambda *a, linkage_version=2, **k: link_judgment_excerpts(summary, frozen, linkage_version=linkage_version))
    routes = {lane: _route(lane=lane, model=f"synthetic-{lane.value}")
        for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    artifacts = ArtifactStore(data_paths)
    async def candidates(*args):
        return PageCompletion(json.dumps(answer, ensure_ascii=False), "stop", {})
    async def qualification(route, messages, budget):
        return PageCompletion(json.dumps(_qualification_payload_for_messages(messages), ensure_ascii=False), "stop", {})
    candidate = enqueue_predicate_candidates(session_factory, review_episode_id=authority.review_episode_id,
        component_ids=["component-a"], routes=routes, review_context_id=context.context_id)
    executor = PredicateBindingJobExecutor(session_factory, artifacts, routes, completion=candidates)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(candidate.job_id)
    qualified = enqueue_binding_qualification(session_factory, candidate_job_id=candidate.job_id,
        routes=routes, artifact_store=artifacts)
    executor = BindingQualificationJobExecutor(session_factory, artifacts, routes, completion=qualification)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(qualified.job_id)

    class HistoricalInputExecutor(JudgmentContentJobExecutor):
        @staticmethod
        def load_input(session, artifact_store, **kwargs):
            return judgment_content_input.load_judgment_content_input(session, artifact_store,
                **kwargs, input_version=judgment_content_input_version("predicate", version))
    calls = []
    async def content_completion(route, messages, budget):
        request = json.loads(messages[1]["content"][0]["text"])
        calls.append(route.lane.value)
        return PageCompletion(json.dumps({"results": [{
            "pair_id": pair_id, "explicit_written_judgment": "unresolved",
            "investigator_attribution": "unresolved", "target_correspondence": "supported",
            "node_correspondence": "unresolved", "encoded_value_fidelity": "supported",
            "quoted_evidence": locator.excerpt, "explanation": "合成读数不证明研究者判断。",
            "unresolved_reasons": ["本合成资料没有书面判断或节点归属。"],
        } for pair_id in request["required_pair_ids"]]}, ensure_ascii=False), "stop", {})
    content = _enqueue_content_job(session_factory, candidate_job_id=candidate.job_id,
        context_id=context.context_id, routes=routes, artifact_store=artifacts,
        pair_batch_max_characters=24000, product_runtime=False, definition=HistoricalInputExecutor)
    executor = HistoricalInputExecutor(session_factory, artifacts, routes, completion=content_completion)
    assert JobRunner(session_factory, {executor.job_type: executor}).run_job(content.job_id)
    with session_factory() as session:
        row = session.get(JobRecord, content.job_id)
        old_bytes = row.payload_json
        rebuilt = verify_completed_judgment_content(session, artifacts, content.job_id)
        assert rebuilt["payload"]["input_version"] == judgment_content_input_version("predicate", version)
        assert rebuilt["pairs"] and rebuilt["excerpt_coverage"]
        assert all(rebuilt["lane_receipts"].values()) and len(calls) == 2
        assert rebuilt["summary"]["comparisons"] and not rebuilt["clinically_qualified"]
        if version == 1:
            with pytest.raises(InvalidJobDefinitionError, match="输入版本"):
                build_receipt_verified_work_draft_selections(session, artifacts,
                    qualification_job_id=qualified.job_id, judgment_content_job_id=content.job_id)
        else:
            draft = build_receipt_verified_work_draft_selections(session, artifacts,
                qualification_job_id=qualified.job_id, judgment_content_job_id=content.job_id)
            assert draft.verified_judgment_requirement_ids == ()
            assert draft.content_supported_pair_ids == ()
        assert session.get(JobRecord, content.job_id).payload_json == old_bytes
    # Simulated corrupt payload cannot reuse the unchanged receipt/summary.
    with session_factory() as session, session.begin():
        row = session.get(JobRecord, content.job_id)
        changed = json.loads(row.payload_json)
        changed["comparison_sha256"] = "f" * 64
        row.payload_json, row.payload_sha256 = encode_value(changed)
        with pytest.raises(InvalidJobDefinitionError, match="输入"):
            verify_completed_judgment_content(session, artifacts, content.job_id)
