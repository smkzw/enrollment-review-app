"""Synthetic source/search seams; real jobs, artifacts, recovery and receipts.

No network, clinical originals, fact publication or approval is represented here.
"""
import copy
import json
from hashlib import sha256

import pytest

from app.domain.contracts.enums import TruthValue
from app.domain.contracts.history_source_search import (
    VERSION, HistorySearchPage, history_scope_hash, summarize_history_search,
)
from app.domain.contracts.record_semantics import RecordSemantics
from app.evidence.artifacts import ArtifactStore
from app.llm.history_source_search import build_history_search_messages, parse_history_search
from app.llm.page_review_harness import PageCompletion
from app.services import history_source_search_job as jobs
from app.services.history_source_search_calculation import calculate_history_not_seen
from app.services.job_service import JobService
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.llm.test_predicate_binding_candidates import _route


def _sha(value):
    return sha256(value.encode()).hexdigest()


def _scope(*, texts=("合成资料记载定期随访。",), blockers=(), page_blockers=(), targets=True):
    purpose = {"target_kind": "event_history", "record_obligation": "not_required_by_source",
               "proposition_direction": "event_present", "source_excerpts": ["合成既往事件条件"]}
    pages = [{"page_key": _sha(str(number)), "source_document_version_id": "synthetic-document",
              "page_number": number, "page_artifact_id": f"synthetic-page-{number}",
              "page_image_sha256": _sha(f"image-{number}"), "effective_text_sha256": _sha(text),
              "effective_text": text, "metadata": {"source_kind": "synthetic"},
              "blockers": list(page_blockers)} for number, text in enumerate(texts, 1)]
    value = {"version": VERSION, "candidate_family": "predicate", "candidate_job_id": "synthetic-candidate",
             "review_context_id": "synthetic-context", "review_context_sha256": _sha("context"),
             "frozen_input_sha256": _sha("input"), "targets": [{"identity_sha256": _sha("target"),
                "family": "predicate", "proposition": "曾发生示例事件", "record_semantics": purpose,
                "condition": {}, "parent_source": {"source_text": "合成既往事件条件"}}] if targets else [],
             "pages": pages if targets else [], "blockers": list(blockers)}
    return {**value, "scope_sha256": history_scope_hash(value)}


def _answer(scope, page, *, disposition="not_seen", excerpts=()):
    return {"version": VERSION, "scope_sha256": scope["scope_sha256"], "page_key": page["page_key"],
            "findings": [{"identity_sha256": item["identity_sha256"], "disposition": disposition,
                          "excerpts": list(excerpts), "explanation": "合成页面检索说明"}
                         for item in scope["targets"]]}


def _sealed_row(scope, reads):
    return {**summarize_history_search(scope, reads)[0], "candidate_mentions_present": False,
            "summary_sha256": _sha("synthetic-summary")}


@pytest.mark.parametrize("direction,expected", [("event_present", TruthValue.FALSE), ("event_absent", TruthValue.TRUE)])
def test_complete_actual_page_set_and_proposition_direction_not_fact_creation(direction, expected):
    scope = _scope(texts=("合成随访一。", "合成随访二。"))
    scope["targets"][0]["record_semantics"]["proposition_direction"] = direction
    scope["scope_sha256"] = history_scope_hash(scope)
    reads = [_answer(scope, page) for page in scope["pages"]]
    row = _sealed_row(scope, reads)
    purpose = RecordSemantics.model_validate(scope["targets"][0]["record_semantics"])
    result = calculate_history_not_seen(row, purpose)
    assert result.truth == expected and result.used_fact_ids == []
    assert result.reason_codes == ["supplied_records_history_not_seen"]
    assert calculate_history_not_seen({**row, "candidate_mentions_present": True}, purpose) is None


@pytest.mark.parametrize("problem", ["missing-page", "known-missing", "unreadable", "reading-risk", "uncertain"])
def test_missing_or_unclear_scope_never_becomes_not_seen(problem):
    scope = _scope(texts=("合成资料一。", "合成资料二。"),
                   blockers=("known_missing_document",) if problem == "known-missing" else (),
                   page_blockers=("reading_risk",) if problem in {"unreadable", "reading-risk"} else ())
    reads = [_answer(scope, page, disposition="unresolved" if problem in {
        "unreadable", "reading-risk", "uncertain"} else "not_seen") for page in scope["pages"]]
    if problem == "missing-page":
        reads.pop()
    row = _sealed_row(scope, reads)
    assert row["status"] in {"incomplete", "unresolved"}
    assert calculate_history_not_seen(row, RecordSemantics.model_validate(scope["targets"][0]["record_semantics"])) is None


@pytest.mark.parametrize("text", ["既往处方日期不详。", "明确否认示例事件。", "多年前曾购药。", "存在疑似事件。"])
def test_related_mention_does_not_disappear_by_grade_date_or_denial(text):
    scope = _scope(texts=(text, "本页没有额外内容。"))
    reads = [_answer(scope, scope["pages"][0], disposition="mentioned", excerpts=(text,)),
             _answer(scope, scope["pages"][1])]
    row = _sealed_row(scope, reads)
    assert row["status"] == "mentioned"
    assert calculate_history_not_seen(row, RecordSemantics.model_validate(scope["targets"][0]["record_semantics"])) is None
    messages = build_history_search_messages(scope, scope["pages"][0])
    assert "不因日期可能超窗" in messages[0]["content"]


@pytest.mark.parametrize("fault", ["page", "target", "duplicate", "invented-excerpt", "empty-page", "duplicate-target"])
def test_scope_identity_quote_and_coverage_are_not_count_checks(fault):
    scope = _scope()
    read = _answer(scope, scope["pages"][0])
    if fault == "page":
        read["page_key"] = _sha("other-page")
    elif fault == "target":
        read["findings"][0]["identity_sha256"] = _sha("other-target")
    elif fault == "duplicate":
        read["findings"] *= 2
    elif fault == "invented-excerpt":
        read["findings"][0].update(disposition="mentioned", excerpts=["不存在的原文"])
    elif fault == "duplicate-target":
        scope["targets"] *= 2
        scope["scope_sha256"] = history_scope_hash(scope)
        read["scope_sha256"] = scope["scope_sha256"]
    else:
        scope["pages"][0]["effective_text"] = ""
        scope["scope_sha256"] = history_scope_hash(scope)
        read["scope_sha256"] = scope["scope_sha256"]
    with pytest.raises(ValueError):
        summarize_history_search(scope, [read])


def test_required_written_judgment_or_unknown_purpose_is_not_a_history_shortcut():
    scope = _scope()
    row = _sealed_row(scope, [_answer(scope, scope["pages"][0])])
    purpose = RecordSemantics.model_validate(scope["targets"][0]["record_semantics"])
    for obligation in ("required", "unresolved"):
        other = purpose.model_copy(update={"record_obligation": obligation})
        assert calculate_history_not_seen(row, other) is None
    from app.domain.contracts.rules import TimeConstraint
    constraint = TimeConstraint(anchor_type="screening_date", direction="before",
                                upper_bound={"value": 2, "unit": "year"})
    assert calculate_history_not_seen(row, purpose, time_constraint=constraint, anchor_dates={}).truth == TruthValue.UNKNOWN


def _runtime(session_factory, data_paths, monkeypatch, scope, completion):
    monkeypatch.setattr(jobs, "load_history_search_scope", lambda *_args, **_kwargs: copy.deepcopy(scope))
    route = _route(max_tokens=65536)
    routes = {route.lane: route}
    store = ArtifactStore(data_paths)
    job = jobs.enqueue_history_source_search(session_factory, candidate_job_id="synthetic-candidate",
        context_id="synthetic-context", routes=routes, artifact_store=store)
    executor = jobs.HistorySourceSearchJobExecutor(session_factory, store, routes, completion=completion)
    runner = JobRunner(session_factory, {jobs.JOB_TYPE: executor})
    return job, store, runner


def test_actual_source_adapter_freezes_visual_layers_and_checks_current_revision(
    session_factory, data_paths, monkeypatch,
):
    from types import SimpleNamespace
    from app.domain.contracts.rules import AtomicPredicate
    from app.services import history_source_search_input as source_input
    from app.storage.selective_vision_observation_repository import SelectiveVisionObservationRepository
    from tests.v2.services.test_fact_normalization_persistence import _seed_chain
    from tests.v2.services.test_fact_normalization_visual_observation_wiring import _observation_record
    from tests.v2.services.test_receipt_verified_work_draft_consumer import (
        _synthetic_material, POSITIVE_PREDICATE_ID,
    )
    prefix = "history-source-actual"
    clause = "合成条件：曾发生示例事件"
    positive = AtomicPredicate(predicate_id=POSITIVE_PREDICATE_ID, subject="history",
        attribute="source_statement", comparator="exists", source_clause=clause,
        semantic_proposition=clause, record_semantics=dict(target_kind="event_history",
            record_obligation="not_required_by_source", proposition_direction="event_present",
            source_excerpts=[clause]))
    _, _, frozen, _, episode, _ = _synthetic_material(positive=positive)
    digest = _sha("synthetic-context")
    # Candidate/context seams are isolated here; source storage, closure checks,
    # source adapter and visual collection below are the actual implementations.
    monkeypatch.setattr(source_input, "load_completed_candidate_qualification_input",
        lambda *_a, **_k: dict(family="predicate", review_context_id="context",
            review_context_sha256=digest, frozen_input=frozen.model_dump(mode="json"),
            frozen_input_sha256=frozen.frozen_input_sha256))
    monkeypatch.setattr(source_input, "require_prepared_candidate_scope", lambda *_a, **_k: digest)
    monkeypatch.setattr(source_input, "current_review_clinical_material_sha256", lambda *_a: digest)
    monkeypatch.setattr(source_input, "frozen_review_clinical_material_sha256", lambda *_a: digest)
    with session_factory() as session:
        chain = _seed_chain(session, prefix=prefix)
        observation = _observation_record(prefix=prefix, observation_id="visual-first",
            observation_text=f"source_ref={prefix}-pa\n手写补记示例事件。")
        SelectiveVisionObservationRepository(session).get_or_create_succeeded(observation)
        session.commit()
        context = SimpleNamespace(authority=chain["authority"], review_episode=episode,
                                  context_sha256=digest, conflict_groups=[])
        monkeypatch.setattr(source_input.ReviewContextV2Repository, "get", lambda *_: context)
        scope = source_input.load_history_search_scope(session, ArtifactStore(data_paths),
            candidate_job_id="candidate", context_id="context")
        assert len(scope["pages"]) == 1
        page = scope["pages"][0]
        assert page["visual_sources"][0]["observation_text"] == observation.observation_text
        assert page["page_artifact_id"] == chain["page_artifact_id"]
        assert observation.observation_text not in page["effective_text"]
        later = _observation_record(prefix=prefix, observation_id="visual-later", model_id="other-reader",
            observation_text=f"source_ref={prefix}-pa\n手写补记另一事件。")
        SelectiveVisionObservationRepository(session).get_or_create_succeeded(later)
        session.commit()
        new_scope = source_input.load_history_search_scope(session, ArtifactStore(data_paths),
            candidate_job_id="candidate", context_id="context")
        assert len(new_scope["pages"][0]["visual_sources"]) == 2
        assert new_scope["scope_sha256"] != scope["scope_sha256"]
        assert new_scope["pages"][0]["page_key"] != page["page_key"]
        # Historical revision remains readable; current-head validation is not
        # bypassed by the candidate fixture or the unchanged material digest.
        from app.storage.evidence_locator_repositories import RevisionClosureError
        monkeypatch.setattr(source_input.CompleteEvidenceProcessingRevisionRepository,
            "get_current", lambda *_: (_ for _ in ()).throw(RevisionClosureError("synthetic stale head")))
        with pytest.raises(RevisionClosureError, match="stale head"):
            source_input.load_history_search_scope(session, ArtifactStore(data_paths),
                candidate_job_id="candidate", context_id="context")


def _request_page(messages):
    return json.loads(messages[1]["content"][0]["text"])["page"]


def test_actual_job_receipts_reserve_before_call_and_survive_failed_page_retry(session_factory, data_paths, monkeypatch):
    scope = _scope(texts=("合成资料一。", "合成资料二。"))
    calls = []
    job_id = None
    fail = True
    async def complete(route, messages, budget):
        page = _request_page(messages)
        calls.append(page["page_key"])
        with session_factory() as session:
            assert any(item.event.payload.get("history_search_budget")
                       for item in JobStore(session).list_event_rows(job_id))
        if len(calls) == 2 and fail:
            raise ConnectionError("synthetic transport failure")
        return PageCompletion(json.dumps(_answer(scope, page), ensure_ascii=False), "stop", {}, response_model=route.model)
    job, store, runner = _runtime(session_factory, data_paths, monkeypatch, scope, complete)
    job_id = job.job_id
    runner.run_job(job_id)
    with session_factory() as session:
        persisted = JobStore(session)
        assert persisted.get_job(job_id).state == "failed_retryable"
        first = persisted.get_last_checkpoint(job_id, f"page:{scope['pages'][0]['page_key']}")
        with pytest.raises(InvalidJobDefinitionError):
            jobs.verify_completed_history_search(session, store, job_id)
    fail = False
    JobService(session_factory).retry(job_id)
    runner.run_job(job_id)
    with session_factory() as session:
        receipt = jobs.verify_completed_history_search(session, store, job_id)
        assert receipt["summary"][0]["status"] == "not_seen"
        assert first == JobStore(session).get_last_checkpoint(job_id, f"page:{scope['pages'][0]['page_key']}")
        assert len(calls) == 3 and calls.count(scope["pages"][0]["page_key"]) == 1
    scope["pages"][0]["metadata"]["correction"] = "new-source-version"
    scope["scope_sha256"] = history_scope_hash(scope)
    with session_factory() as session, pytest.raises(InvalidJobDefinitionError, match="已变化"):
        jobs.verify_completed_history_search(session, store, job_id)


@pytest.mark.parametrize("mode", ["length", "wrong-model", "malformed", "changed-source", "cancelled", "blocked", "no-targets"])
def test_actual_recovery_and_apply_boundaries(session_factory, data_paths, monkeypatch, mode):
    scope = _scope(page_blockers=("unreadable",) if mode == "blocked" else (), targets=mode != "no-targets")
    calls = []
    job_id = None
    async def complete(route, messages, budget):
        page = _request_page(messages)
        calls.append(budget)
        response = _answer(scope, page)
        if mode == "length" and len(calls) == 1:
            return PageCompletion("truncated", "length", {}, response_model=route.model)
        if mode == "changed-source":
            scope["blockers"] = ["newly_discovered_missing_source"]
            scope["scope_sha256"] = history_scope_hash(scope)
        if mode == "cancelled":
            JobService(session_factory).cancel(job_id)
        return PageCompletion("not JSON" if mode == "malformed" else json.dumps(response), "stop", {},
                              response_model="other-model" if mode == "wrong-model" else route.model)
    job, store, runner = _runtime(session_factory, data_paths, monkeypatch, scope, complete)
    job_id = job.job_id
    runner.run_job(job_id)
    if mode == "length":
        JobService(session_factory).retry(job_id)
        runner.run_job(job_id)
        assert calls == [65536, 131072]
    with session_factory() as session:
        persisted = JobStore(session)
        state = persisted.get_job(job_id).state
        if mode in {"length", "blocked", "no-targets"}:
            assert state == "completed"
            summary = jobs.verify_completed_history_search(session, store, job_id)["summary"]
            assert not summary if mode == "no-targets" else summary[0]["status"] == (
                "incomplete" if mode == "blocked" else "not_seen")
            if mode in {"blocked", "no-targets"}:
                assert calls == []
        else:
            assert state in {"failed_final", "cancelled"}
            with pytest.raises(InvalidJobDefinitionError):
                jobs.verify_completed_history_search(session, store, job_id)
        if mode not in {"blocked", "no-targets", "cancelled", "changed-source"}:
            assert any(persisted.checkpoint_is_diagnostic(job_id, persisted.get_last_checkpoint(job_id, step.step_id)[0])
                       for step in persisted.list_steps(job_id) if step.step_id.startswith("page:")
                       and persisted.get_last_checkpoint(job_id, step.step_id) is not None) == (mode != "length")


def test_parser_never_accepts_duplicate_json_keys():
    scope = _scope()
    raw = json.dumps(_answer(scope, scope["pages"][0]))
    raw = raw[:-1] + ', "version": "history-source-search/v1"}'
    with pytest.raises(ValueError):
        parse_history_search(scope, HistorySearchPage.model_validate(scope["pages"][0]), raw)


@pytest.mark.parametrize("fault", [None, "wrong-page", "combined-quote", "omitted-visual"])
def test_visual_mention_is_separate_source_and_never_an_ocr_absence(fault):
    from app.domain.contracts.selective_vision_observation import SelectiveVisionObservationAttachment
    from tests.v2.services.test_fact_normalization_visual_observation_wiring import _observation_record

    scope = _scope()
    page = scope["pages"][0]
    record = _observation_record(prefix="synthetic", observation_id="synthetic-visual",
        page_artifact_id=page["page_artifact_id"], source_document_version_id=page["source_document_version_id"],
        page_image_sha256=page["page_image_sha256"], ocr_page_id=None, ocr_raw_text_sha256=None,
        observation_text=f"source_ref={page['page_artifact_id']}\n手写：既往示例事件，日期不详。")
    attachment = SelectiveVisionObservationAttachment.model_validate({
        key: value for key, value in record.model_dump(mode="json").items()
        if key in SelectiveVisionObservationAttachment.model_fields})
    page["visual_sources"] = [attachment.model_dump(mode="json")]
    quote = "手写：既往示例事件，日期不详。"
    if fault == "wrong-page":
        page["page_number"] = 2
    elif fault == "combined-quote":
        quote = page["effective_text"] + quote
    elif fault == "omitted-visual":
        page["visual_sources"] = []
    scope["scope_sha256"] = history_scope_hash(scope)
    read = _answer(scope, page, disposition="mentioned", excerpts=(quote,))
    if fault:
        with pytest.raises(ValueError):
            summarize_history_search(scope, [read])
        return
    row = summarize_history_search(scope, [read])[0]
    assert row["status"] == "mentioned"
    refs = row["source_refs"][0]["excerpts"][0]["sources"]
    assert refs == [{"source_layer": "visual_observation",
                    "source_sha256": attachment.observation_identity_sha256,
                    "observation_id": attachment.observation_id}]
    prompt = json.loads(build_history_search_messages(scope, page)[1]["content"][0]["text"])
    assert prompt["page"]["effective_text"] == page["effective_text"]
    assert prompt["page"]["visual_sources"][0]["observation_text"] == record.observation_text
    assert calculate_history_not_seen({**row, "candidate_mentions_present": False},
        RecordSemantics.model_validate(scope["targets"][0]["record_semantics"])) is None


@pytest.mark.parametrize("direction,mention", [("event_present", False), ("event_absent", False), ("event_present", True)])
def test_saved_search_enters_actual_sealed_factory_calculator_and_projection(
    session_factory, data_paths, monkeypatch, direction, mention,
):
    from app.domain.contracts.rules import AtomicPredicate
    from app.domain.contracts.page_review import PageReviewLane
    from app.services.binding_qualification import BindingQualificationJobExecutor, enqueue_binding_qualification
    from app.services.eligibility_review_projection import EligibilityReviewProjectionService
    from app.services.frozen_review_calculation import calculate_frozen_review
    from app.services.history_source_search_input import history_search_targets
    from app.services.predicate_binding_job import PredicateBindingJobExecutor, enqueue_predicate_candidates
    from app.services.qualified_binding_selection import build_receipt_verified_work_draft_selections
    from tests.v2.llm.test_predicate_binding_candidates import _v2_accounting
    from tests.v2.services.test_receipt_verified_work_draft_consumer import (
        _synthetic_material, _aligned_review_context, _qualification_payload_for_messages,
        POSITIVE_PREDICATE_ID, FACT_ID,
    )
    clause = "合成条件：曾发生示例事件" if direction == "event_present" else "合成条件：无示例事件史"
    purpose = {"target_kind": "event_history", "record_obligation": "not_required_by_source",
               "proposition_direction": direction, "source_excerpts": [clause]}
    positive = AtomicPredicate(predicate_id=POSITIVE_PREDICATE_ID, subject="history", attribute="source_statement",
        comparator="exists", source_clause=clause, semantic_proposition=clause, record_semantics=purpose)
    authority, rules, frozen, fact, episode, answer = _synthetic_material(positive=positive)
    context = _aligned_review_context(authority=authority, rule_set=rules, clinical_fact=fact, episode=episode)
    monkeypatch.setattr("app.storage.review_context_repository.ReviewContextV2Repository.get", lambda *_: context)
    monkeypatch.setattr("app.services.review_candidate_scope.get_rule_set", lambda *_: rules)
    for module in ("predicate_binding_job", "binding_qualification"):
        monkeypatch.setattr(f"app.services.{module}.build_predicate_binding_frozen_input", lambda *a, **k: frozen)
    for row in answer["results"]:
        row.update(status="unresolved", candidates=[], uncertainty="合成已整理事实中未见相关候选",
                   fact_accounting=_v2_accounting(candidate_fact_ids=(), universe=(FACT_ID,)))
    routes = {lane: _route(lane=lane, model=f"synthetic-{lane.value}")
              for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    store = ArtifactStore(data_paths)
    async def candidates(*_args):
        return PageCompletion(json.dumps(answer, ensure_ascii=False), "stop", {})
    async def qualification(_route, messages, _budget):
        return PageCompletion(json.dumps(_qualification_payload_for_messages(messages)), "stop", {})
    candidate = enqueue_predicate_candidates(session_factory, review_episode_id=authority.review_episode_id,
        component_ids=["component-a"], routes=routes, review_context_id=context.context_id)
    executor = PredicateBindingJobExecutor(session_factory, store, routes, completion=candidates)
    JobRunner(session_factory, {executor.job_type: executor}).run_job(candidate.job_id)
    qualified = enqueue_binding_qualification(session_factory, candidate_job_id=candidate.job_id,
                                             routes=routes, artifact_store=store)
    executor = BindingQualificationJobExecutor(session_factory, store, routes, completion=qualification)
    JobRunner(session_factory, {executor.job_type: executor}).run_job(qualified.job_id)
    scope = _scope(texts=("合成随访：既往示例事件日期不详。" if mention else "合成随访：未记载其他病史。",))
    scope.update(candidate_job_id=candidate.job_id, review_context_id=context.context_id,
                 review_context_sha256=context.context_sha256, frozen_input_sha256=frozen.frozen_input_sha256,
                 targets=history_search_targets(frozen, "predicate"))
    assert len(scope["targets"]) == 1
    scope["scope_sha256"] = history_scope_hash(scope)
    monkeypatch.setattr(jobs, "load_history_search_scope", lambda *_args, **_kwargs: copy.deepcopy(scope))
    async def search_completion(route, messages, budget):
        page = _request_page(messages)
        return PageCompletion(json.dumps(_answer(scope, page,
            disposition="mentioned" if mention else "not_seen",
            excerpts=(page["effective_text"],) if mention else ())), "stop", {}, response_model=route.model)
    search = jobs.enqueue_history_source_search(session_factory, candidate_job_id=candidate.job_id,
        context_id=context.context_id, routes=routes, artifact_store=store)
    executor = jobs.HistorySourceSearchJobExecutor(session_factory, store, routes, completion=search_completion)
    JobRunner(session_factory, {executor.job_type: executor}).run_job(search.job_id)
    with session_factory() as session:
        draft = build_receipt_verified_work_draft_selections(session, store,
            qualification_job_id=qualified.job_id, history_source_search_job_id=search.job_id)
        assert draft.history_source_search == search.job_id
        assert all(not row.fact_ids for row in draft.identity_outcomes)
        calculation = calculate_frozen_review(context, rules, work_draft_selections=draft)
        result = calculation.components[0].result.evaluation.predicate_evaluations[POSITIVE_PREDICATE_ID]
        assert result.truth == (TruthValue.UNKNOWN if mention else
                                TruthValue.FALSE if direction == "event_present" else TruthValue.TRUE)
        assert result.used_fact_ids == [] and calculation.accepted is False
        projection = EligibilityReviewProjectionService()._project_frozen_work_draft(
            session, frozen=context, rule_set=rules, selections=(draft,))
        assert ("1页资料已核对，未见相关事件记录" in projection.clauses[0].reason) is not mention
        assert projection.clauses[0].fact_refs == ()
        assert len(projection.clauses[0].source_read_refs) == 1
        ref = projection.clauses[0].source_read_refs[0]
        assert ref.page_artifact_id == scope["pages"][0]["page_artifact_id"]
        assert ref.disposition == ("mentioned" if mention else "not_seen")
        assert (ref.excerpt is not None) is mention
        assert projection.clauses[1].rule_component_id == "component-restricted-sibling"
        before = len(context.facts)
        draft.history_search_results[0]["status"] = "not_seen" if mention else "mentioned"
        with pytest.raises(ValueError, match="已变化"):
            draft.require_unchanged()
        assert len(context.facts) == before


@pytest.mark.parametrize("mode", ["not_seen", "mentioned", "missing", "definition-unverified", "professional"])
def test_same_history_policy_reaches_control_layers_and_outcome_consumer(mode):
    from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput, control_binding_input_hash
    from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
    from app.projections.control_atom_binding_input import project_control_atom_identities
    from app.projections.control_calculation_experiment import evaluate_control_layers_experiment
    from app.projections.control_review_outcome import project_control_review_outcomes
    from app.services.control_history_search_calculation import apply_control_history_search
    from app.services.history_source_search_input import history_search_targets
    from tests.v2.services.test_receipt_verified_work_draft_consumer import _synthetic_control_input
    frozen, _, _ = _synthetic_control_input(computation=False)
    raw = frozen.publication.model_dump(mode="json")
    raw.pop("publication_id")
    control = raw["catalog"]["controls"][0]
    atom = control["obligation_expression"]["groups"][0]["atoms"][0]
    clause = "合成补充要求：无示例事件史"
    atom.update(statement=clause, source_excerpts=[clause], requires_professional_judgment=mode == "professional")
    atom["evaluation"] = dict(determination_mode="semantic", proposition=clause,
        time_purpose="not_applicable", source_span_ids=atom["source_span_ids"], source_excerpts=[clause],
        observation_policy=dict(mode="any", scope="本次资料中的事件史",
            source_span_ids=atom["source_span_ids"], source_excerpts=[clause]),
        record_semantics=dict(target_kind="event_history", record_obligation="not_required_by_source",
                              proposition_direction="event_absent", source_excerpts=[clause]))
    for evidence in control["minimum_evidence"]:
        evidence["source_policy"]["source_excerpts"] = [clause]
    publication = ControlCatalogPublication.model_validate(raw)
    frozen = ControlBindingFrozenInput(publication=publication, evidence_input=frozen.evidence_input,
                                      frozen_input_sha256=control_binding_input_hash(publication, frozen.evidence_input))
    identity, = project_control_atom_identities(publication)
    scope = _scope()
    scope.update(candidate_family="control", targets=history_search_targets(frozen, "control"))
    if mode == "professional":
        assert scope["targets"] == []
        return
    scope["scope_sha256"] = history_scope_hash(scope)
    if mode == "mentioned":
        page = scope["pages"][0]
        reads = [_answer(scope, page, disposition="mentioned", excerpts=(page["effective_text"],))]
    else:
        reads = [] if mode == "missing" else [_answer(scope, scope["pages"][0])]
    row = _sealed_row(scope, reads)
    calculated = evaluate_control_layers_experiment(frozen, frozen_input_sha256=frozen.frozen_input_sha256,
                                                   selections={identity.identity_sha256: []})
    result = apply_control_history_search(calculated, frozen, [row], blocked_identities=(
        [identity.identity_sha256] if mode == "definition-unverified" else []))
    outcomes = project_control_review_outcomes(frozen, result)
    obligation = outcomes[0].obligations[0]
    assert obligation.status == ("fulfilled" if mode == "not_seen" else "unverified")
    assert obligation.used_fact_ids == [] and result.accepted is False
    assert len(result.history_search_results) == (1 if mode == "not_seen" else 0)
    assert calculated.version == "control-calculation-experiment/v19"


def test_budget_reservation_prefix_is_immutable_not_only_latest_count():
    from types import SimpleNamespace
    from app.llm.logical_call_budget import LogicalCallBudget
    scope = _scope()
    payload = {"scope": scope, "budget_requests_per_page": 3, "budget_output_tokens_per_page": 3 * 131072}
    allowance = LogicalCallBudget("job:page", max_requests=3, max_output_tokens=3 * 131072,
                                  contract_sha256=scope["scope_sha256"])
    allowance.reserve(request_sha256=_sha("first"), max_tokens=65536)
    first = allowance.snapshot()
    allowance.reserve(request_sha256=_sha("second"), max_tokens=65536)
    second = allowance.snapshot()
    second["requests"][0]["request_sha256"] = _sha("replacement")
    events = [SimpleNamespace(event=SimpleNamespace(step_id="page", payload={"history_search_budget": True, "budget": value}))
              for value in (first, second)]
    store = SimpleNamespace(list_event_rows=lambda *_: events)
    with pytest.raises(InvalidJobDefinitionError, match="不连续"):
        jobs._page_allowance(store, "job", "page", payload)
