"""Source-local reading through existing Jobs, immutable artifacts and budgets."""
import asyncio
import dataclasses
import json
from time import monotonic

from sqlalchemy import text

from app.domain.contracts.enums import JobEventType
from app.domain.contracts.history_source_search import (
    VERSION, PROMPT_VERSION, HistorySearchPage, summarize_history_search,
)
from app.domain.publication import canonical_hash
from app.llm.history_source_search import build_history_search_messages, parse_history_search
from app.llm.logical_call_budget import LogicalCallBudget, LogicalCallBudgetExhausted
from app.llm.page_review_harness import direct_completion
from app.llm.page_review_transport_options import page_completion_options
from app.services.history_source_search_input import load_history_search_scope
from app.services.job_service import JobService, StepSpec
from app.services.page_review_cancellation import run_cancellable
from app.services.page_review_job_service import route_identity
from app.services.review_runtime_ownership import mark_prepared_review_job
from app.storage.codecs import utc_now, verify_payload_sha256
from app.workflow.errors import InvalidJobDefinitionError, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult

JOB_TYPE = "history_source_search"
CONTRACT = "history-source-search-job/v2"


def _put(store, value):
    return store.put("raw_response", json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).sha256


def _read(store, sha):
    return json.loads(store.read_by_sha("raw_response", sha))


def _page_allowance(jobs, job_id, step_id, payload):
    previous = []
    saved = None
    for item in jobs.list_event_rows(job_id):
        if item.event.step_id != step_id or not item.event.payload.get("history_search_budget"):
            continue
        saved = item.event.payload["budget"]
        ledger = LogicalCallBudget(f"{job_id}:{step_id}",
            max_requests=payload["budget_requests_per_page"],
            max_output_tokens=payload["budget_output_tokens_per_page"],
            contract_sha256=payload["scope"]["scope_sha256"], saved=saved)
        current = ledger.snapshot()["requests"]
        if len(current) != len(previous) + 1 or current[:-1] != previous:
            raise InvalidJobDefinitionError("病史检索累计调用记录不连续，不能按零调用继续")
        previous = current
    return LogicalCallBudget(f"{job_id}:{step_id}",
        max_requests=payload["budget_requests_per_page"],
        max_output_tokens=payload["budget_output_tokens_per_page"],
        contract_sha256=payload["scope"]["scope_sha256"], saved=saved)


def enqueue_history_source_search(session_factory, *, candidate_job_id, context_id, routes,
                                  artifact_store, product_runtime=False):
    from app.domain.contracts.page_review import PageReviewLane
    route = routes[PageReviewLane.MAIN_A]
    if not 1 <= route.max_tokens <= 131072:
        raise InvalidJobDefinitionError("病史检索输出额度须来自明确且受支持的读取配置")
    with session_factory() as session, session.begin():
        scope = load_history_search_scope(session, artifact_store,
            candidate_job_id=candidate_job_id, context_id=context_id)
        for page in scope["pages"] if scope["targets"] else []:
            messages = build_history_search_messages(scope, page)
            if len(json.dumps(messages, ensure_ascii=False)) > 180000:
                raise InvalidJobDefinitionError("本次条款与资料页超过单次检索范围，须先按完整条件分包；未截断或调用模型")
        payload = {"contract": CONTRACT, "prompt_version": PROMPT_VERSION, "scope": scope,
                   "candidate_job_id": candidate_job_id, "review_context_id": context_id,
                   "review_context_sha256": scope["review_context_sha256"],
                   "routes": {lane.value: route_identity(item) for lane, item in routes.items()},
                   "reader_lane": route.lane.value, "budget_requests_per_page": 3,
                   "budget_output_tokens_per_page": 3 * 131072}
        mark_prepared_review_job(payload, enabled=product_runtime, session=session,
                                 parent_job_id=candidate_job_id)
        steps = []
        if scope["targets"]:
            for page in scope["pages"]:
                steps.append(StepSpec(f"page:{page['page_key']}", "查找本页相关病史记录",
                    max_attempts=3, retryable=True,
                    depends_on=(steps[-1].step_id,) if steps else ()))
        steps.append(StepSpec("summary", "保存本次病史检索范围与未核清事项",
                              depends_on=tuple(item.step_id for item in steps)))
        return JobService(session_factory).create_job_in_session(session, job_type=JOB_TYPE,
            payload=payload, idempotency_key=f"{CONTRACT}:{canonical_hash(payload)}", steps=steps)


def _require_current(session, store, payload):
    if payload.get("contract") != CONTRACT or payload.get("prompt_version") != PROMPT_VERSION:
        raise InvalidJobDefinitionError("病史检索版本不一致，请重新准备审核")
    if (payload.get("budget_requests_per_page") != 3
            or payload.get("budget_output_tokens_per_page") != 3 * 131072
            or payload.get("reader_lane") != "main-A"):
        raise InvalidJobDefinitionError("病史检索累计额度或主读配置不一致")
    scope = load_history_search_scope(session, store, candidate_job_id=payload["candidate_job_id"],
                                      context_id=payload["review_context_id"])
    if scope != payload["scope"]:
        raise InvalidJobDefinitionError("本次病史检索的资料或条件已变化，请重新准备审核")
    return scope


def _verified_reads(session, store, job_id, payload):
    scope = payload["scope"]
    checkpoints = JobStore(session)
    result = []
    for raw in scope["pages"] if scope["targets"] else []:
        page = HistorySearchPage.model_validate(raw)
        step_id = f"page:{page.page_key}"
        checkpoint = checkpoints.get_last_checkpoint(job_id, step_id)
        if checkpoint is None or checkpoints.checkpoint_is_diagnostic(job_id, checkpoint[0]):
            raise InvalidJobDefinitionError("尚有资料页没有完成病史检索")
        proof = _read(store, checkpoint[1]["proof_sha256"])
        step = next(item for item in checkpoints.list_steps(job_id) if item.step_id == step_id)
        if (proof.get("job_id") != job_id or proof.get("step_id") != step_id
                or step.state != "completed" or proof.get("attempt") != step.attempt
                or proof.get("scope_sha256") != scope["scope_sha256"]):
            raise InvalidJobDefinitionError("资料页检索记录不属于本次审核")
        messages = build_history_search_messages(scope, raw)
        if page.blockers:
            expected = _blocked_read(scope, page)
            if proof.get("method") != "unreadable_source" or proof.get("read") != expected:
                raise InvalidJobDefinitionError("未核清资料页的限制记录无法核实")
        else:
            route = payload["routes"][payload["reader_lane"]]
            request = _read(store, proof["request_sha256"])
            budget = proof["max_tokens"]
            if (type(budget) is not int or not 1 <= budget <= 131072
                    or request != _request(route, messages, budget)
                    or proof.get("method") != "single_source_reader"
                    or proof.get("route") != route):
                raise InvalidJobDefinitionError("病史检索请求或读取配置与实际来源不一致")
            response = _read(store, proof["response_sha256"])
            reservations = [item.event for item in checkpoints.list_event_rows(job_id)
                            if item.event.step_id == step_id and item.event.payload.get("history_search_budget")]
            if not reservations:
                raise InvalidJobDefinitionError("病史检索缺少调用前保存的额度记录")
            allowance = _page_allowance(checkpoints, job_id, step_id, payload)
            if (reservations[-1].attempt != proof["attempt"] or allowance.snapshot()["requests"][-1] !=
                    {"request_sha256": proof["request_sha256"], "requested_max_tokens": budget}):
                raise InvalidJobDefinitionError("病史检索请求没有对应的调用前额度记录")
            if (response.get("finish_reason") != "stop" or not response.get("response_model")
                    or response["response_model"].strip().casefold() != route["model"].strip().casefold()):
                raise InvalidJobDefinitionError("病史检索没有身份明确的完整回答")
            read = parse_history_search(scope, page, response["text"]).model_dump(mode="json")
            if proof.get("read") != read:
                raise InvalidJobDefinitionError("保存的病史检索与实际回答不一致")
        result.append(proof["read"])
    return result


def verify_completed_history_search(session, store, job_id):
    jobs = JobStore(session)
    row = jobs.get_job(job_id)
    payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
    if row.job_type != JOB_TYPE or row.state != "completed" or row.cancel_requested:
        raise InvalidJobDefinitionError("病史检索未完成或已取消，不能作为工作稿依据")
    scope = _require_current(session, store, payload)
    reads = _verified_reads(session, store, job_id, payload)
    summary = summarize_history_search(scope, reads)
    checkpoint = jobs.get_last_checkpoint(job_id, "summary")
    if (checkpoint is None or jobs.checkpoint_is_diagnostic(job_id, checkpoint[0])
            or _read(store, checkpoint[1]["summary_sha256"]) != summary):
        raise InvalidJobDefinitionError("病史检索汇总不对应实际逐页阅读记录")
    return {"job_id": job_id, "payload": payload, "scope": scope, "summary": summary,
            "summary_sha256": checkpoint[1]["summary_sha256"]}


def _request(route, messages, budget):
    return {"model": route["model"], "reasoning_effort": route["reasoning_effort"],
            "messages": messages, "max_tokens": budget,
            **page_completion_options(route["provider"], messages, budget)}


def _blocked_read(scope, page):
    return {"version": VERSION, "scope_sha256": scope["scope_sha256"], "page_key": page.page_key,
            "findings": [{"identity_sha256": item["identity_sha256"], "disposition": "unresolved",
                          "excerpts": [], "explanation": "本页资料尚未核清，不能按未见记录处理"}
                         for item in scope["targets"]]}


class HistorySourceSearchJobExecutor:
    job_type = JOB_TYPE
    contract = CONTRACT
    prompt_version = PROMPT_VERSION

    def __init__(self, session_factory, artifact_store, routes, *, completion=direct_completion):
        self.session_factory, self.store, self.routes = session_factory, artifact_store, routes
        self.completion = completion

    def __call__(self, context):
        payload = context.job_payload
        if context.job_type != JOB_TYPE or payload.get("routes") != {
                lane.value: route_identity(route) for lane, route in self.routes.items()}:
            raise StepFailure(retryable=False, error_code="HISTORY_SEARCH_ROUTE_CHANGED")
        with self.session_factory() as session:
            scope = _require_current(session, self.store, payload)

        def apply(session):
            _require_current(session, self.store, payload)

        if context.step_id == "summary":
            with self.session_factory() as session:
                reads = _verified_reads(session, self.store, context.job_id, payload)
            return PreparedStepResult({"summary_sha256": _put(self.store, summarize_history_search(scope, reads)),
                                       "clinical_adoption": False}, apply)
        page = next((HistorySearchPage.model_validate(item) for item in scope["pages"]
                     if context.step_id == f"page:{item['page_key']}"), None)
        if page is None or not scope["targets"]:
            raise StepFailure(retryable=False, error_code="HISTORY_SEARCH_STEP_INVALID")
        proof = {"job_id": context.job_id, "step_id": context.step_id, "attempt": context.attempt,
                 "scope_sha256": scope["scope_sha256"]}
        if page.blockers:
            proof.update(method="unreadable_source", read=_blocked_read(scope, page))
        else:
            route = next(item for lane, item in self.routes.items() if lane.value == payload["reader_lane"])
            messages = build_history_search_messages(scope, page.model_dump(mode="json"))
            budget = route.max_tokens
            if context.last_checkpoint and context.last_checkpoint.get("finish_reason") == "length":
                budget = min(131072, 2 * context.last_checkpoint["max_tokens"])
            request_sha = _put(self.store, _request(route_identity(route), messages, budget))
            self._reserve(context, payload, request_sha, budget)
            proof.update(method="single_source_reader", route=route_identity(route),
                         request_sha256=request_sha, max_tokens=budget)
            start = monotonic()
            try:
                response = asyncio.run(run_cancellable(lambda: self.completion(route, messages, budget),
                                                       self.session_factory, context.job_id))
                proof["response_sha256"] = _put(self.store, dataclasses.asdict(response))
                proof["elapsed_seconds"] = monotonic() - start
                if response.finish_reason != "stop":
                    raise StepFailure(retryable=response.finish_reason == "length" and budget < 131072,
                        error_code="HISTORY_SEARCH_RESPONSE_INCOMPLETE", diagnostic_checkpoint={
                            **proof, "finish_reason": response.finish_reason})
                if (not response.response_model
                        or response.response_model.strip().casefold() != route.model.strip().casefold()):
                    raise StepFailure(retryable=False, error_code="HISTORY_SEARCH_MODEL_IDENTITY_UNKNOWN",
                                      diagnostic_checkpoint=proof)
                proof["read"] = parse_history_search(scope, page, response.text).model_dump(mode="json")
            except StepFailure:
                raise
            except Exception as exc:
                proof.update(elapsed_seconds=monotonic() - start, error_type=type(exc).__name__)
                raise StepFailure(retryable=not isinstance(exc, ValueError),
                    error_code="HISTORY_SEARCH_READING_FAILED", diagnostic_checkpoint=proof,
                    detail="本页病史检索未完成，已保留调用记录和其他完成资料页") from exc
        return PreparedStepResult({"proof_sha256": _put(self.store, proof), "clinical_adoption": False}, apply)

    def _reserve(self, context, payload, request_sha, budget):
        with self.session_factory() as session, session.begin():
            session.execute(text("BEGIN IMMEDIATE"))
            jobs = JobStore(session)
            row = jobs.get_job(context.job_id)
            step = next(item for item in jobs.list_steps(context.job_id) if item.step_id == context.step_id)
            if (row.state != "running" or row.cancel_requested or step.state != "running"
                    or step.attempt != context.attempt or row.lease_expires_at is None
                    or row.lease_expires_at <= utc_now()):
                raise StepFailure(retryable=False, error_code="HISTORY_SEARCH_LEASE_CHANGED")
            allowance = _page_allowance(jobs, context.job_id, context.step_id, payload)
            try:
                allowance.reserve(request_sha256=request_sha, max_tokens=budget)
            except LogicalCallBudgetExhausted as exc:
                raise StepFailure(retryable=False, error_code=exc.code, detail=str(exc)) from exc
            jobs.append_event(jobs.make_event(job_id=context.job_id, step_id=context.step_id,
                attempt=context.attempt, event_type=JobEventType.PAGE_PROGRESS,
                payload={"history_search_budget": True, "budget": allowance.snapshot()}))
