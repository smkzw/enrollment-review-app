"""Recheck successful saved readings without changing history or invoking a model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.agents.evidence_normalizer import (
    parse_evidence_normalizer_output, validate_evidence_normalizer_output,
)
from app.domain.contracts.enums import FactCallStatus
from app.domain.publication import canonical_hash
from app.storage.codecs import verify_payload_sha256
from app.storage.fact_repositories import FactNormalizationCallRepository, FactNormalizationRunRepository
from app.storage.facts_models import FactNormalizationRunRecord
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore


_QUALIFICATION_PATHS = (
    "domain/contracts/facts.py", "domain/contracts/enums.py", "domain/contracts/fact_context.py",
    "domain/contracts/fact_gates.py", "domain/contracts/identifier_value.py",
    "domain/contracts/evidence_locator.py", "domain/gates/fact_candidate_gates.py",
    "domain/contracts/medication_source.py",
    "domain/gates/fact_evidence_closure.py", "domain/gates/fact_batch_orchestration.py",
    "domain/risk_flags.py", "evidence/risk.py", "storage/fact_authority.py",
    "services/fact_publication_service.py", "services/fact_normalization_revalidation.py",
    "agents/evidence_normalizer.py", "agents/evidence_candidate_partition.py",
    "services/fact_normalization_executor.py", "services/fact_normalization_source_adapter.py",
    "projections/normalizer_text_accounting.py", "storage/source_reference_successors.py",
    "storage/evidence_expectation_repository.py",
)


def qualification_identity() -> str:
    """A gate change creates a new append-only result, never an old approval."""
    root = Path(__file__).resolve().parents[1]
    return canonical_hash({path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in _QUALIFICATION_PATHS})


def supports_saved_source(call) -> bool:
    return (call.status == FactCallStatus.SUCCEEDED and call.reading_method == "model_response"
            and call.question_classification_sha256 is None and call.response_recovery_sha256 is None)


def saved_readings(session, *, run_id, authority, artifacts, prompt_template, only_call_id=None):
    from app.storage.read_retention import retain_read_records
    with retain_read_records(session):
        return _saved_readings(session, run_id=run_id, authority=authority, artifacts=artifacts,
            prompt_template=prompt_template, only_call_id=only_call_id)


def _saved_readings(session, *, run_id, authority, artifacts, prompt_template, only_call_id):
    """Only the exact successful calls of one explicitly selected terminal run.

    Reparse their actual accepted response, compare persisted candidates/questions,
    and verify source, prompt, model and actual request. No answer search/fallback.
    """
    from app.services.fact_normalization_executor import (
        _build_input, _load_frozen_agent_config, _prepare_response_revalidation,
        _validate_call_checkpoint_replay, _validate_saved_output_matches, _get_call_for_step,
    )

    if artifacts is None:
        raise InvalidJobDefinitionError("重新核验需要已有请求和回答的工件存储")
    run = FactNormalizationRunRepository(session).get(run_id)
    if run.authority != authority or run.status.value not in {"partial", "succeeded"}:
        raise InvalidJobDefinitionError("已读记录不属于当前资料范围或尚未结束")
    record = session.get(FactNormalizationRunRecord, run_id)
    if record is None or not record.job_id:
        raise InvalidJobDefinitionError("已读记录缺少原任务身份")
    store = JobStore(session)
    job = store.get_job(record.job_id)
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if (job.state != "completed" or payload.get("run_id") != run_id or not payload.get("targeted_extraction")
            or payload.get("source_revalidation") or payload.get("page_review_coverage_id")
            or payload.get("visual_source_policy") or payload.get("retained_reads")):
        raise InvalidJobDefinitionError("仅可重新核验已完成的当前文字主读，不借用旧双读或递归复用")
    model = _load_frozen_agent_config(session, payload=payload, run_id=run_id,
        authority=authority, prompt_template=prompt_template)
    calls = {call.call_id: call for call in FactNormalizationCallRepository(session).list_by_run(run_id)}
    if set(calls) != {call["call_id"] for call in payload["calls"]}:
        raise InvalidJobDefinitionError("已读页清单与原任务不一致")
    rows = []
    for step in store.list_steps(job.job_id):
        if step.step_id == "finalize":
            continue
        saved = store.get_last_checkpoint(job.job_id, step.step_id)
        if saved is None:
            raise InvalidJobDefinitionError("已读步骤缺少原检查点")
        checkpoint = saved[1]
        if only_call_id is not None and checkpoint.get("call_id") != only_call_id:
            continue
        call = calls[checkpoint["call_id"]]
        spec = next(item for item in payload["calls"] if item["call_id"] == call.call_id)
        if _get_call_for_step(payload, step.step_id) != spec:
            raise InvalidJobDefinitionError("步骤检查点不属于声明的原读取")
        if not supports_saved_source(call):
            raise InvalidJobDefinitionError("本入口只重验已完整保存的原始成功读取")
        _validate_call_checkpoint_replay(session, authority=authority, run_id=run_id,
            call=spec, checkpoint=checkpoint, payload=payload, artifact_store=artifacts,
            prompt_template=prompt_template)
        evidence = _build_input(session, authority, run_id, spec,
            max_pages_per_call=payload["max_pages_per_call"], created_at=run.created_at)
        expected_request, aliases = _prepare_response_revalidation(payload, evidence, model, prompt_template, [])
        matching = []
        for sha in checkpoint.get("transport_receipt_sha256", ()):
            receipt = json.loads(artifacts.read_by_sha("raw_response", sha))
            raw = receipt.get("raw_text")
            # The existing transport returns content.strip() to the runner;
            # the immutable receipt keeps the original bytes, including whitespace.
            if not isinstance(raw, str) or hashlib.sha256(raw.strip().encode()).hexdigest() != call.raw_output_sha256:
                continue
            matching.append((sha, receipt))
        if len(matching) != 1:
            raise InvalidJobDefinitionError("无法唯一对应原来实际采用的回答")
        receipt_sha, receipt = matching[0]
        request_sha = receipt.get("request_artifact_sha256")
        request = json.loads(artifacts.read_by_sha("raw_request", request_sha))
        bindings = {"job_id": job.job_id, "step_id": step.step_id, "run_id": run_id, "call_id": call.call_id}
        body = request.get("request_body", {})
        messages = body.get("messages", [])
        prefix = expected_request.get("messages", [])
        expected_aliases = aliases.aliases if aliases is not None else None
        # Format repair may append messages; it must retain the original source
        # prompt and schema. A length retry may only double the recorded budget.
        immutable = lambda value: {key: val for key, val in value.items() if key not in {"messages", "max_tokens"}}
        budget = expected_request.get("max_tokens")
        if (any(obj.get(key) != value for obj in (request, receipt) for key, value in bindings.items())
                or request.get("provider") != model.provider or receipt.get("provider") != model.provider
                or receipt.get("finish_reason") != "stop" or not receipt.get("response_id")
                or receipt.get("requested_model") != model.model
                or str(receipt.get("response_model", "")).casefold() != model.model.casefold()
                or canonical_hash(body) != receipt.get("request_sha256")
                or immutable(body) != immutable(expected_request) or messages[:len(prefix)] != prefix
                or body.get("max_tokens") not in {budget, budget * 2 if isinstance(budget, int) else None}
                or receipt.get("reference_aliases") != expected_aliases):
            raise InvalidJobDefinitionError("原请求的来源、提示、模型或预算身份无法核实")
        if call.candidate_partition_sha256:
            from app.agents.evidence_candidate_partition import recover_source_local_candidates
            output = recover_source_local_candidates(receipt["raw_text"].strip(), evidence, reference_aliases=aliases).output
        else:
            output = parse_evidence_normalizer_output(receipt["raw_text"].strip(),
                expected_run_id=run_id, expected_call_id=call.call_id,
                expected_logical_document_id=call.logical_document_id, expected_page_numbers=call.page_numbers,
                available_locator_ids=set(evidence.available_locator_ids),
                locator_source_hashes={item.locator_id: item.source_text_sha256 for item in evidence.available_locators},
                locator_source_texts={item.locator_id: item.localized_text for item in evidence.available_locators},
                created_at=run.created_at, reference_aliases=aliases, require_current_draft=True)
            output = validate_evidence_normalizer_output(output, evidence)
        _validate_saved_output_matches(session, payload, run, call, evidence, output)
        proof = {"source_run_id": run_id, "source_job_id": job.job_id, "source_call_id": call.call_id,
            "source_payload_sha256": job.payload_sha256, "checkpoint_sha256": canonical_hash(checkpoint),
            "request_artifact_sha256": request_sha, "receipt_sha256": receipt_sha,
            "candidate_partition_sha256": call.candidate_partition_sha256,
            "raw_output_sha256": call.raw_output_sha256, "output_sha256": canonical_hash(output.model_dump(mode="json"))}
        rows.append((spec, proof, output))
    if len(rows) != (1 if only_call_id is not None else len(calls)) or not rows:
        raise InvalidJobDefinitionError("已读范围不完整，不能作为重新核验依据")
    return payload, rows


def revalidated_output(session, *, payload, call, authority, artifacts, prompt_template):
    """Bind verified old observations to a new run, not to a new model reading."""
    selection = payload["source_revalidation"]
    if selection["qualification_sha256"] != qualification_identity():
        raise InvalidJobDefinitionError("核验实现已变化，请从新入口建立本次核验")
    source_call_id = selection["calls"][call["call_id"]]["source_call_id"]
    _, readings = saved_readings(session, run_id=selection["source_run_id"], authority=authority,
        artifacts=artifacts, prompt_template=prompt_template, only_call_id=source_call_id)
    spec, proof, output = next(row for row in readings if row[0]["call_id"] == source_call_id)
    if proof != selection["calls"][call["call_id"]] or any(
            call[key] != spec[key] for key in ("logical_document_id", "page_numbers", "input_sha256")):
        raise InvalidJobDefinitionError("重新核验与冻结的原读取不一致")
    updates = {"run_id": payload["run_id"], "call_id": call["call_id"]}
    rebound = output.model_copy(update={**updates, **{key: [item.model_copy(update=updates) for item in getattr(output, key)]
        for key in ("fact_candidates", "event_candidates", "exposure_candidates")}})
    return rebound, {**proof, **updates, "qualification_sha256": selection["qualification_sha256"], "model_called": False}
