"""Synthetic receipts, real producer/runner/publication/Profile; no live model."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.agents.deepseek_evidence_normalizer_transport import evidence_normalizer_transport_from_model_config
from app.domain.contracts.enums import FactCallStatus
from app.domain.contracts.facts import FactNormalizationCall
from app.evidence.artifacts import ArtifactStore
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService, FactNormalizationCallSpec
from app.services.fact_normalization_source_adapter import build_fact_normalization_plan
from app.storage.codecs import encode_contract
from app.storage.fact_repositories import FactNormalizationCallRepository, FactNormalizationRunRepository, ClinicalFactV2Repository
from app.storage.facts_models import FactNormalizationCallRecord, PatientProfileRevisionV2Record
from app.storage.models import JobRecord
from app.storage.repositories import AppendRepository, MODEL_CONFIG_CONFIG, PROMPT_VERSION_CONFIG
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.services.test_fact_normalization_persistence import _seed_chain, _update_episode
from tests.v2.services.test_normalizer_candidate_partition import SourceDraftTransport


@pytest.mark.parametrize("changed", [
    "domain/contracts/facts.py", "domain/contracts/enums.py", "domain/contracts/fact_context.py",
    "domain/contracts/fact_gates.py", "domain/contracts/identifier_value.py",
    "domain/contracts/evidence_locator.py", "domain/gates/fact_candidate_gates.py",
    "evidence/risk.py", "storage/fact_authority.py",
])
def test_qualification_identity_tracks_contract_and_gate_semantics(tmp_path, monkeypatch, changed):
    from app.services import fact_normalization_revalidation as module

    root = tmp_path / "app"
    for path in module._QUALIFICATION_PATHS:
        source = root / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("frozen implementation: " + path)
    monkeypatch.setattr(module, "__file__", str(root / "services/fact_normalization_revalidation.py"))
    before = module.qualification_identity()
    assert module.qualification_identity() == before
    unrelated = root / "frontend-only.txt"
    unrelated.write_text("presentation is not adoption authority")
    assert module.qualification_identity() == before
    (root / changed).write_text("changed source or gate semantics")
    assert module.qualification_identity() != before


def test_qualification_identity_does_not_hide_missing_dependency(tmp_path, monkeypatch):
    from app.services import fact_normalization_revalidation as module

    monkeypatch.setattr(module, "__file__", str(tmp_path / "app/services/fact_normalization_revalidation.py"))
    with pytest.raises(FileNotFoundError):
        module.qualification_identity()


def successful_reading(session_factory, data_paths, *, partition=False, whitespace=False,
                       field_sources=False, source_guidance=None, compact_rows=False, preserve_schema=False):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="saved-success", source_qualification_mode="scoped_text_v1")
        model = AppendRepository(session, MODEL_CONFIG_CONFIG).get(chain["model_config_id"])
        if field_sources or compact_rows or preserve_schema:
            from app.agents.evidence_normalizer import DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
            from app.services.fact_normalization_command_service import _runtime_prompt, _model_identity

            model = model.model_copy(update={"parameters": {**model.parameters, "include_medication_field_sources": field_sources,
                "compact_requirement_rows": compact_rows,
                "preserve_repair_schema": preserve_schema,
                **({"medication_source_guidance": source_guidance} if source_guidance is not None else {})}})
            model = model.model_copy(update={"model_config_id": "evidence-normalizer/model/" + _model_identity(model)})
            prompt = _runtime_prompt(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
                include_medication_field_sources=field_sources, medication_source_material=source_guidance,
                compact_requirement_rows=compact_rows, preserve_repair_schema=preserve_schema)
            AppendRepository(session, MODEL_CONFIG_CONFIG).save(model)
            AppendRepository(session, PROMPT_VERSION_CONFIG).save(prompt)
            chain.update(model_config_id=model.model_config_id, prompt_version_id=prompt.prompt_version_id)
        plan, _ = build_fact_normalization_plan(session, authority=chain["authority"], revision_id=chain["complete_revision_id"])
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_job(authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"],
        calls=[FactNormalizationCallSpec.from_planned_call(call) for call in plan.calls],
        created_by="builder_verification", targeted_extraction=True, allow_candidate_partition=partition,
        account_source_text=True)
    payload = service.get_job(created.job_id)["payload"]
    artifacts = ArtifactStore(data_paths)
    call = payload["calls"][0]
    step_id = "normalize_000_" + chain["logical_document_id"]
    bindings = {"job_id": created.job_id, "step_id": step_id, "run_id": created.run_id, "call_id": call["call_id"]}
    requests = []
    raw = json.loads(SourceDraftTransport(chain).start(prompt="synthetic-fixture").text)
    if not partition:
        raw["fact_candidates"] = raw["fact_candidates"][:1]
    text = json.dumps(raw, ensure_ascii=False)
    if whitespace:
        text = "\n " + text + "\n\t"
    response = SimpleNamespace(id="synthetic-not-live", model=model.model, usage=None,
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: (requests.append(kwargs), response)[1])))

    def save(kind, body):
        return artifacts.put(kind, json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).sha256

    receipts = []
    def receipt_callback(receipt):
        receipts.append(save("raw_response", {**bindings, **receipt}))

    transport = evidence_normalizer_transport_from_model_config(model, client=client,
        request_callback=lambda body: save("raw_request", {**bindings, "request_receipt_version": "normalizer-request/v1",
            "provider": model.provider, "request_body": body}),
        receipt_callback=receipt_callback)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(session_factory=session_factory,
        artifact_store=artifacts, transport=transport, max_schema_repairs=0))
    def with_synthetic_receipt(context):
        result = executor(context)
        if context.step_id != "finalize":
            result.checkpoint["transport_receipt_sha256"] = list(receipts)
        return result
    JobRunner(session_factory, {"fact_normalization": with_synthetic_receipt}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "completed", service.get_job(created.job_id)
    assert len(requests) == 1
    return chain, service, created, artifacts


@pytest.mark.parametrize("frozen", [False, True], ids=["legacy-material", "explicit-material"])
@pytest.mark.parametrize("compact_rows", [False, True], ids=["objects", "rows"])
@pytest.mark.parametrize("preserve_schema", [False, True], ids=["legacy-repair", "same-schema-repair"])
def test_saved_medication_prompt_replays_without_using_a_new_current_guidance(
    session_factory, data_paths, monkeypatch, frozen, compact_rows, preserve_schema,
):
    from app.agents import evidence_normalizer as prompts
    from app.services.fact_normalization_revalidation import saved_readings
    from app.services.fact_normalization_executor import _prepare_response_revalidation, _build_input
    from app.services.fact_normalization_command_service import select_registered_evidence_normalizer_config, RegisteredNormalizerConfig

    material = prompts.MEDICATION_PARTIAL_SOURCE_GUIDANCE if frozen else None
    chain, service, original, artifacts = successful_reading(session_factory, data_paths,
        field_sources=True, source_guidance=material, compact_rows=compact_rows, preserve_schema=preserve_schema)
    monkeypatch.setattr(prompts, "MEDICATION_PARTIAL_SOURCE_GUIDANCE", "今后新请求的另一份提示，不得替换旧请求")
    with session_factory() as session:
        payload, rows = saved_readings(session, run_id=original.run_id, authority=chain["authority"],
            artifacts=artifacts, prompt_template=prompts.DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
        assert len(rows) == 1
        spec, proof, _ = rows[0]
        request = json.loads(artifacts.read_by_sha("raw_request", proof["request_artifact_sha256"]))
        body = request["request_body"]
        assert prompts.medication_source_guidance(True, material) in body["messages"][0]["content"]
        model = AppendRepository(session, MODEL_CONFIG_CONFIG).get(chain["model_config_id"])
        assert select_registered_evidence_normalizer_config(session,
            registered_config=RegisteredNormalizerConfig(prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"]))
        run = FactNormalizationRunRepository(session).get(original.run_id)
        evidence = _build_input(session, chain["authority"], original.run_id, spec,
            max_pages_per_call=payload["max_pages_per_call"], created_at=run.created_at)
        expected, _ = _prepare_response_revalidation(payload, evidence, model,
            prompts.DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, [])
        assert expected == body
        mismatched = model.model_copy(update={"parameters": {**model.parameters,
            "compact_requirement_rows": not compact_rows}})
        other_request, _ = _prepare_response_revalidation(payload, evidence, mismatched,
            prompts.DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, [])
        assert other_request != body
        before = {fact.fact_id: fact.model_dump_json() for fact in
            ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])}
    newer = service.create_revalidation_from_run(authority=chain["authority"], source_run_id=original.run_id,
        artifact_store=artifacts, created_by="builder_verification")
    def forbid(*args, **kwargs):
        raise AssertionError("旧材料重新核验不得重新调用模型")
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(session_factory=session_factory,
        artifact_store=artifacts, transport_fn=forbid, transport_factory=forbid))
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(newer.job_id)
    assert service.get_job(newer.job_id)["state"] == "completed", service.get_job(newer.job_id)
    with session_factory() as session:
        facts = {fact.fact_id: fact.model_dump_json() for fact in ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])}
        assert all(facts[key] == value for key, value in before.items())
        assert service.get_job(original.job_id)["state"] == "completed"


@pytest.mark.parametrize("partition", [False, True])
@pytest.mark.parametrize("whitespace", [False, True])
def test_new_qualification_uses_exact_saved_source_and_preserves_old_result(session_factory, data_paths, partition, whitespace):
    chain, service, original, artifacts = successful_reading(session_factory, data_paths, partition=partition, whitespace=whitespace)
    with session_factory() as session:
        old = session.get(JobRecord, original.job_id)
        old_hash = old.payload_sha256
        original_call = FactNormalizationCallRepository(session).list_by_run(original.run_id)[0]
        original_facts = {item.fact_id: item for item in ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])}
    created = service.create_revalidation_from_run(authority=chain["authority"], source_run_id=original.run_id,
        artifact_store=artifacts, created_by="builder_verification")
    assert created.created and created.run_id != original.run_id and created.job_id != original.job_id
    again = service.create_revalidation_from_run(authority=chain["authority"], source_run_id=original.run_id,
        artifact_store=artifacts, created_by="builder_verification")
    assert not again.created and again.job_id == created.job_id

    def forbid(*args, **kwargs):
        raise AssertionError("重新核验不得调用模型或隐式回退")
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(session_factory=session_factory,
        artifact_store=artifacts, transport_factory=forbid, transport_fn=forbid))
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "completed", service.get_job(created.job_id)
    with session_factory() as session:
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        assert call.reading_method == "saved_source_revalidation"
        proof = json.loads(artifacts.read_by_sha("evaluation_manifest", call.source_revalidation_sha256))
        assert proof["source_call_id"] == original_call.call_id and proof["model_called"] is False
        assert call.raw_output_sha256 == original_call.raw_output_sha256
        assert session.get(JobRecord, original.job_id).payload_sha256 == old_hash
        assert FactNormalizationCallRepository(session).get(original_call.call_id) == original_call
        facts = {item.fact_id: item for item in ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])}
        assert all(facts[key] == value for key, value in original_facts.items())
        assert session.scalars(select(PatientProfileRevisionV2Record)).all()
        checkpoint = JobStore(session).get_last_checkpoint(created.job_id, "normalize_000_" + chain["logical_document_id"])
    payload = service.get_job(created.job_id)["payload"]
    replay = executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="资料核验", attempt=1, max_attempts=1,
        last_checkpoint_id=checkpoint[0], last_checkpoint=checkpoint[1]))
    assert replay["model_called"] is False
    rebuilt = executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="资料核验", attempt=1, max_attempts=1,
        last_checkpoint_id=None, last_checkpoint=None))
    assert rebuilt["source_revalidation_sha256"] == replay["source_revalidation_sha256"]
    assert rebuilt["model_called"] is False
    from app.services.evidence_api_read_service import EvidenceApiReadService
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert view["can_revalidate_saved"] is False
    with pytest.raises(InvalidJobDefinitionError):
        service.create_revalidation_from_run(authority=chain["authority"], source_run_id=created.run_id,
            artifact_store=artifacts, created_by="builder_verification")


@pytest.mark.parametrize("fault", ["foreign_scope", "missing_response", "changed_source_call", "changed_gate"])
def test_saved_source_damage_never_reads_again_or_publishes(session_factory, data_paths, monkeypatch, fault):
    chain, service, original, artifacts = successful_reading(session_factory, data_paths)
    created = service.create_revalidation_from_run(authority=chain["authority"], source_run_id=original.run_id,
        artifact_store=artifacts, created_by="builder_verification")
    if fault == "missing_response":
        for path in (data_paths.root / "artifacts/raw_response").iterdir():
            path.unlink()  # Synthetic fixtures only.
    elif fault == "changed_gate":
        monkeypatch.setattr("app.services.fact_normalization_revalidation.qualification_identity", lambda: "f" * 64)
    else:
        with session_factory() as session, session.begin():
            if fault == "foreign_scope":
                from app.storage.models import ReviewEpisodeRecord
                episode = session.get(ReviewEpisodeRecord, chain["episode_id"])
                _update_episode(session, episode, revision=episode.revision + 1)
            else:
                call = FactNormalizationCallRepository(session).list_by_run(original.run_id)[0]
                row = session.get(FactNormalizationCallRecord, call.call_id)
                row.payload_json, row.payload_sha256 = encode_contract(call.model_copy(update={"raw_output_sha256": "e" * 64}))
    def forbid(*args, **kwargs):
        raise AssertionError("坏回执不得回退到模型")
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(session_factory=session_factory,
        artifact_store=artifacts, transport_fn=forbid))
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "failed_final"
    if fault == "changed_gate":
        from app.services.evidence_api_read_service import EvidenceApiReadService
        view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
            chain["subject_id"], chain["episode_id"], created.job_id)
        assert view["revalidation_source_run_id"] == original.run_id
        assert view["can_revalidate_saved"] is True
    with session_factory() as session:
        assert not session.scalars(select(FactNormalizationCallRecord).where(
            FactNormalizationCallRecord.run_id == created.run_id)).all()


def test_call_contract_does_not_mislabel_revalidation_as_model_read():
    from datetime import datetime, UTC
    base = dict(call_id="new", run_id="new-run", logical_document_id="doc", page_numbers=[1],
        status=FactCallStatus.SUCCEEDED, input_sha256="a" * 64, raw_output_sha256="b" * 64,
        created_at=datetime.now(UTC))
    with pytest.raises(ValueError):
        FactNormalizationCall(**base, reading_method="saved_source_revalidation")
    with pytest.raises(ValueError):
        FactNormalizationCall(**base, reading_method="model_response", source_revalidation_sha256="c" * 64)
    assert "source_revalidation_sha256" not in FactNormalizationCall(**base).model_dump()


@pytest.mark.parametrize("field", ["question_classification_sha256", "response_recovery_sha256"])
def test_unavailable_proof_type_does_not_offer_a_dead_end_action(field):
    from datetime import datetime, UTC
    from app.services.fact_normalization_revalidation import supports_saved_source
    call = FactNormalizationCall(call_id="old", run_id="old-run", logical_document_id="doc", page_numbers=[1],
        status=FactCallStatus.SUCCEEDED, input_sha256="a" * 64, raw_output_sha256="b" * 64,
        reading_method="model_response", created_at=datetime.now(UTC))
    assert supports_saved_source(call)
    assert not supports_saved_source(call.model_copy(update={field: "c" * 64}))
