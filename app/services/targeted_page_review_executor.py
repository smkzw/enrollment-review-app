"""Durable auxiliary rounds; original reconciliations and coverage stay immutable."""

from dataclasses import replace

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.domain.contracts.page_review import PageReviewRecord
from app.domain.contracts.targeted_review_outcome import TargetedReviewOutcome
from app.domain.targeted_page_review import compare_targeted_reads
from app.domain.targeted_handwriting_review import compare_handwriting_reads, pending_handwriting_excerpts
from app.domain.page_normalization import normalize_field_name
from app.llm.page_review_harness import PAGE_REVIEW_PROMPT_VERSION, TARGETED_REVIEW_PROMPT_VERSION
from app.services.page_review_job_executor import PageReviewJobExecutor
from app.services.page_review_job_service import page_review_execution_versions, route_identity
from app.services.targeted_page_review_jobs import MAIN_LANES, TARGETED_REVIEW_VERSION, targeted_routes
from app.storage.fact_authority import FactAuthorityValidator
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult


class TargetedPageReviewExecutor:
    def __init__(self, session_factory, artifact_store, routes, *, completion):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes = targeted_routes(routes)
        self.completion = completion

    def __call__(self, context):
        payload = context.job_payload
        if (payload.get("version") != TARGETED_REVIEW_VERSION
                or payload.get("base_prompt_version") != PAGE_REVIEW_PROMPT_VERSION
                or payload.get("targeted_prompt_version") != TARGETED_REVIEW_PROMPT_VERSION
                or payload.get("routes") != {lane.value: route_identity(r) for lane, r in self.routes.items()}):
            raise StepFailure(retryable=False, error_code="TARGETED_REVIEW_CONTRACT_CHANGED")
        authority = FactAuthority.model_validate(payload["authority"])
        focus = PageReviewFocus.model_validate(payload["focus"])
        parts = context.step_id.split(":")
        if context.step_id not in {f"read:{n}:{lane.value}" for n in (1, 2) for lane in MAIN_LANES} | {"compare:1", "compare:2"}:
            raise StepFailure(retryable=False, error_code="TARGETED_REVIEW_STEP_INVALID")
        number = int(parts[1])

        def checked(session):
            FactAuthorityValidator(session).validate(authority)

        with self.session_factory() as session:
            checked(session)
            store = JobStore(session)

            def receipt(step):
                result = store.get_last_checkpoint(context.job_id, step)
                if result is None:
                    raise StepFailure(retryable=False, error_code="TARGETED_REVIEW_RECEIPT_MISSING")
                return result[1]

            if number == 2:
                previous = receipt("compare:1")
                if (not previous["pending_targets"] and not previous.get("handwriting_pending")) or previous.get("read_failures"):
                    return PreparedStepResult(checkpoint={**previous, "round_skipped": True}, apply=checked)
                ids = tuple(receipt(f"read:1:{lane.value}")["page_review_id"] for lane in MAIN_LANES)
                records = [PageReviewRecord.model_validate(receipt(f"read:1:{lane.value}")["auxiliary_review"])
                           for lane in MAIN_LANES]
                excerpts = tuple(f.region.excerpt for record in records for f in record.facts
                                 if normalize_field_name(f.field_name) in previous["pending_targets"])
                if previous.get("handwriting_pending"):
                    excerpts += pending_handwriting_excerpts(records)
                focus = PageReviewFocus(**{**focus.model_dump(), "round_number": 2,
                    "targets": tuple(previous["pending_targets"]),
                    "handwriting_review": previous.get("handwriting_pending", False),
                    "previous_round_review_ids": ids, "candidate_excerpts": excerpts})
            if parts[0] == "compare":
                receipts = [receipt(f"read:{number}:{lane.value}") for lane in MAIN_LANES]
                failures = [r["lane_failure"] for r in receipts if "lane_failure" in r]
                if failures:
                    result = {"agreed_candidate_targets": [], "pending_targets": list(focus.targets),
                              "candidate_auto_accept": False, "read_failures": failures}
                else:
                    records = [PageReviewRecord.model_validate(r["auxiliary_review"]) for r in receipts]
                    result = compare_targeted_reads(records, focus.targets)
                if focus.handwriting_review:
                    agreed = not failures and compare_handwriting_reads(records)
                    result.update(handwriting_candidate_agreement=agreed, handwriting_pending=not agreed)
                pending = bool(result["pending_targets"]) or result.get("handwriting_pending", False)
                kind = ("conflict_preserved_read_failed" if failures else
                        "candidate_agreement_unaccepted" if not pending else
                        "next_round_pending" if number == 1 else "conflict_pending_user")
                outcome = TargetedReviewOutcome(**result, round_number=number, outcome_kind=kind,
                    cue_kind="prior_excerpts_visible" if focus.candidate_excerpts else "blind",
                    requires_user_review=pending and (number == 2 or bool(failures)))
                return PreparedStepResult(checkpoint=outcome.model_dump(mode="json"), apply=checked)

        # Reuse the ordinary reader's receipts, truncation retry and atomic persistence.
        read_payload = {**page_review_execution_versions(), "authority": payload["authority"],
                        "clause_pack": payload["clause_pack"], "routes": payload["routes"],
                        "pages": [payload["page"]], "review_context": payload["review_context"]}
        read_context = replace(context, job_payload=read_payload)
        executor = PageReviewJobExecutor(self.session_factory, self.artifact_store, self.routes,
                                        completion=self.completion, review_focus=focus)
        result = executor(read_context)
        return PreparedStepResult(checkpoint={**result.checkpoint, "review_focus": focus.model_dump(mode="json")},
                                  apply=result.apply)
