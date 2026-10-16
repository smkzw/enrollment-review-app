"""Synthetic source, real normalizer transport/job/gates/storage/Profile/consumer."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from types import SimpleNamespace

import pytest

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, EvidenceNormalizerDraftOutput,
    evidence_normalizer_compact_schema, evidence_normalizer_json_schema,
    evidence_normalizer_prompt_template_sha256,
)
from app.agents.deepseek_evidence_normalizer_transport import evidence_normalizer_transport_from_model_config
from app.domain.contracts.common import DateValue
from app.domain.contracts.ocr import OcrRiskFlag
from app.domain.contracts.work_draft import WorkDraftEvidenceRef
from app.evidence.artifacts import ArtifactStore
from app.services.fact_normalization_command_service import (
    _runtime_prompt, _model_identity, RegisteredNormalizerConfig,
    select_registered_evidence_normalizer_config, AppFactNormalizationConfigError,
)
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.services.patient_profile_service import PatientProfileService
from app.services.work_draft_medications import calculate_medications
from app.storage.fact_repositories import ClinicalFactV2Repository, MedicationExposureV2Repository, FactNormalizationCandidateRepository
from app.storage.repositories import AppendRepository, MODEL_CONFIG_CONFIG, PROMPT_VERSION_CONFIG
from app.workflow.runner import JobRunner
from tests.v2.domain.test_medication_field_sources import TEXT, exposure_with_sources
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_work_draft_medications import medication_context


def test_default_prompt_and_schema_remain_exactly_replayable():
    assert hashlib.sha256(evidence_normalizer_compact_schema().encode()).hexdigest() == (
        "4f5ed28c03b0fef5cfbc057ff55748ebd94b3a34d60e04e6ff817c57b75ff75d")
    assert evidence_normalizer_prompt_template_sha256(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE) == (
        "dd2d86d2da5d1ee69ea98aa6f7bb8854c3fa915c077f4b78f2af5c2cc4d3dbe8")
    old = evidence_normalizer_json_schema()
    new = evidence_normalizer_json_schema(include_medication_field_sources=True)
    assert "field_sources" not in old["$defs"]["EvidenceExposureDraft"]["properties"]
    assert "field_sources" in new["$defs"]["EvidenceExposureDraft"]["required"]
    assert _runtime_prompt(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE).template_sha256 != (
        _runtime_prompt(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, include_medication_field_sources=True).template_sha256)


def medication_draft(locator_id):
    exposure = exposure_with_sources(locator_id)
    fields = exposure.model_dump(mode="json")
    for field in ("schema_version", "candidate_id", "run_id", "call_id", "candidate_kind", "created_at"):
        fields.pop(field)
    fields["candidate_ref"] = "e1"
    fields["fact_candidate_refs"] = fields.pop("fact_candidate_ids")
    for source in fields["field_sources"]:
        source.pop("source_text_sha256")
    fact = {"candidate_ref": "f1", "assertion_scope": "completed_action", "fact_type": "实际用药",
        "profile_lane": "medication", "polarity": "affirmed", "asserted_object": "药物甲",
        "raw_value": True, "canonical_value": True, "locator_ids": [locator_id],
        "candidate_source_semantics": "既往原始资料", "assertion_basis": {"asserted_object": "药物甲",
            "assertion_text": TEXT, "locator_id": locator_id}, "model_uncertainty": 0.1}
    return EvidenceNormalizerDraftOutput.model_validate({"schema_version": "phase5/normalizer-draft/v5",
        "fact_candidates": [fact], "exposure_candidates": [fields], "actual_exposure_fact_refs": ["f1"],
        "non_exposure_medication_fact_refs": []}).model_dump(mode="json")


def test_planned_or_prescribed_record_cannot_gain_exposure_from_field_annotations():
    body = medication_draft("loc-1")
    body["fact_candidates"][0]["assertion_scope"] = "prospective_or_conditional"
    with pytest.raises(ValueError, match="尚未发生|未确认|意向"):
        EvidenceNormalizerDraftOutput.model_validate(body)


def test_flagged_prompt_is_selected_only_with_its_explicit_matching_model(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="fields-registration")
        base = AppendRepository(session, MODEL_CONFIG_CONFIG).get(chain["model_config_id"])
        model = base.model_copy(update={"parameters": {**base.parameters, "include_medication_field_sources": True}})
        model = model.model_copy(update={"model_config_id": "evidence-normalizer/model/" + _model_identity(model)})
        prompt = _runtime_prompt(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, include_medication_field_sources=True)
        AppendRepository(session, MODEL_CONFIG_CONFIG).save(model)
        AppendRepository(session, PROMPT_VERSION_CONFIG).save(prompt)
        pair = RegisteredNormalizerConfig(prompt_version_id=prompt.prompt_version_id, model_config_id=model.model_config_id)
        assert select_registered_evidence_normalizer_config(session, registered_config=pair) == pair
        wrong = RegisteredNormalizerConfig(prompt_version_id=chain["prompt_version_id"], model_config_id=model.model_config_id)
        with pytest.raises(AppFactNormalizationConfigError, match="不一致"):
            select_registered_evidence_normalizer_config(session, registered_config=wrong)


@pytest.mark.parametrize("fault", [None, "two_drugs", "blocking_date", "blocking_date_outside", "unannotated_date", "negation", "aligned_ongoing",
    "wrong_role", "wrong_object", "missing_unit"])
def test_new_field_reading_publishes_only_source_bound_exposure_and_reaches_consumer(
    session_factory, data_paths, fault,
):
    medication_text = TEXT + ("同时口服药物乙10mg一次。" if fault == "two_drugs" else "")
    source_text = ("否认" if fault == "negation" else "") + medication_text + "\nAST 3.5 mmol/L"
    flag = OcrRiskFlag(risk_id="date", kind="negation_polarity" if fault == "negation" else "date",
        level="blocking", text="否认" if fault == "negation" else "2025-04-12",
        text_start=0, text_end=2 if fault == "negation" else 10, rule_version="facts-test/v1")
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="medication-fields", source_text=source_text, first_excerpt=medication_text,
            document_type="既往病历", source_party="外院", source_qualification_mode="scoped_text_v1",
            risk_flags=(flag,) if fault in {"blocking_date", "blocking_date_outside", "unannotated_date", "negation", "aligned_ongoing"} else ())
        base = AppendRepository(session, MODEL_CONFIG_CONFIG).get(chain["model_config_id"])
        model = base.model_copy(update={"model_config_id": "medication-fields-model",
            "parameters": {**base.parameters, "include_medication_field_sources": True}})
        prompt = _runtime_prompt(DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, include_medication_field_sources=True)
        AppendRepository(session, MODEL_CONFIG_CONFIG).save(model)
        AppendRepository(session, PROMPT_VERSION_CONFIG).save(prompt)
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(authority=chain["authority"],
        prompt_version_id=prompt.prompt_version_id, model_config_id=model.model_config_id,
        created_by="builder_verification", account_source_text=True)
    body = medication_draft(chain["locator_id"])
    if fault == "two_drugs":
        second_fact = deepcopy(body["fact_candidates"][0])
        second_fact.update(candidate_ref="f2", asserted_object="药物乙")
        second_fact["assertion_basis"].update(asserted_object="药物乙", assertion_text=medication_text)
        second = deepcopy(body["exposure_candidates"][0])
        second.update(candidate_ref="e2", medication_name="药物乙", fact_candidate_refs=["f2"])
        for source in second["field_sources"]:
            source.update(object_text="药物乙", excerpt=medication_text)
            if source["field"] == "medication_name":
                source["value_text"] = "药物乙"
        body["fact_candidates"].append(second_fact)
        body["exposure_candidates"].append(second)
        body["actual_exposure_fact_refs"].append("f2")
        for source in body["exposure_candidates"][0]["field_sources"]:
            source["excerpt"] = medication_text
    fields = body["exposure_candidates"][0]["field_sources"]
    if fault == "wrong_role":
        fields[1]["role"] = "recorded_at"
    elif fault == "wrong_object":
        fields[1]["object_text"] = "药物乙"
    elif fault == "missing_unit":
        fields.pop()
    elif fault == "unannotated_date":
        body["exposure_candidates"][0].pop("field_sources")
    elif fault == "aligned_ongoing":
        body["exposure_candidates"][0]["duration_status"] = "ongoing"
        fields[2].update(role="status_ongoing", value_text="药物甲")
    requests = []
    response = SimpleNamespace(id="synthetic-no-network", model=model.model, usage=None,
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(body, ensure_ascii=False)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: (requests.append(kwargs), response)[1])))
    transport = evidence_normalizer_transport_from_model_config(model, client=client)
    artifacts = ArtifactStore(data_paths)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=transport, artifact_store=artifacts, max_schema_repairs=0))
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "completed", service.get_job(created.job_id)
    assert len(requests) == 1
    assert "field_sources" in requests[0]["response_format"]["json_schema"]["schema"]["$defs"]["EvidenceExposureDraft"]["required"]
    with session_factory() as session:
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        exposures = MedicationExposureV2Repository(session).list_by_episode(chain["episode_id"])
        expected = 2 if fault == "two_drugs" else 1
        assert len(facts) == expected, facts
        assert len(exposures) == (expected if fault in (None, "two_drugs", "blocking_date", "blocking_date_outside") else 0)
        profile = PatientProfileService().latest(session, chain["episode_id"])
        assert profile is not None
        if fault not in (None, "blocking_date", "blocking_date_outside"):
            return
        if fault in {"blocking_date", "blocking_date_outside"}:
            assert "LOW_OCR_CONFIDENCE" in facts[0].risk_flags
        saved = FactNormalizationCandidateRepository(session).get(exposures[0].source_candidate_ids[0])
        assert len(saved.field_sources) == 5
        assert all(item.source_text_sha256 == hashlib.sha256(source_text.encode()).hexdigest() for item in saved.field_sources)
        assert exposures[0].fact_ids == [facts[0].fact_id]
    frame, rules, _ = medication_context(use_day=date(2025, 4, 12))
    frame.authority, frame.facts, frame.medication_exposures = chain["authority"], facts, exposures
    anchor = date(2025, 6, 20) if fault == "blocking_date_outside" else date(2025, 4, 20)
    frame.review_episode.evidence_cutoff_date = anchor
    frame.review_episode.anchor_dates = {"screening_date": DateValue(value=anchor, precision="day")}
    frame.source_pages = [SimpleNamespace(source_document_version_id=chain["doc_id"], page_artifact_id=chain["page_artifact_id"], page_number=1)]
    refs = {facts[0].fact_id: [WorkDraftEvidenceRef(fact_id=facts[0].fact_id, locator_id=chain["locator_id"],
        source_document_version_id=chain["doc_id"], page_artifact_id=chain["page_artifact_id"], page_number=1, excerpt=TEXT)]}
    before = deepcopy(exposures[0].model_dump(mode="json"))
    item, = calculate_medications(frame, rules, evidence_refs=refs)
    if fault == "blocking_date_outside":
        assert item.decision.value == "indeterminate" and item.confidence is None
        assert "未落入" in item.reason_text
    else:
        assert item.decision.value == "exclusion_triggered" and item.confidence == "low"
        assert ("识别可能有误" in (item.confidence_reason or "")) == (fault == "blocking_date")
    assert ("识别可能有误" in item.reason_text) == (fault in {"blocking_date", "blocking_date_outside"})
    assert exposures[0].model_dump(mode="json") == before


def test_unreadable_source_cannot_enter_the_normalization_chain(session_factory):
    from app.storage.evidence_locator_repositories import RevisionClosureError

    flag = OcrRiskFlag(risk_id="repetition", kind="output_repetition", level="blocking",
        text=TEXT, text_start=0, text_end=len(TEXT), rule_version="facts-test/v1")
    with session_factory() as session, session.begin():
        with pytest.raises(RevisionClosureError, match="blocking"):
            _seed_chain(session, prefix="unreadable-medication", source_text=TEXT + "\nAST 3.5 mmol/L", first_excerpt=TEXT,
                document_type="既往病历", source_party="外院", source_qualification_mode="scoped_text_v1",
                risk_flags=(flag,))
