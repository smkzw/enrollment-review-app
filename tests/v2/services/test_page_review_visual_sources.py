import pytest

from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack
from app.services.page_review_visual_sources import rebuild_visual_sources
from app.storage.codecs import decode_contract
from app.storage.models import RuleSetRecord
from app.storage.fact_authority import FactAuthorityError
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_r3_page_review_normalizer_wiring import _persist_page_review


def test_visual_locators_persist_without_ocr_text_or_revision_rewrite(session_factory):
    from app.domain.contracts.page_review import PageFactObservation
    from app.projections.page_review_visual_locators import project_visual_locators
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository, EvidenceLocatorRepository,
    )
    from app.storage.repositories import InvalidReferenceError
    from tests.v2.domain.test_page_review_contracts import _fact

    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="visual-locator-store")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        payload = _fact().model_dump()
        payload["region"]["excerpt"] = "原图可见而文字识别遗漏的检查记录"
        observation = PageFactObservation.model_validate(payload)
        coverage_id = _persist_page_review(session, chain, pack=pack, facts=[observation])
        before = CompleteEvidenceProcessingRevisionRepository(session).get(
            authority.complete_processing_revision_id).model_dump_json()
        sources = rebuild_visual_sources(session, authority, coverage_id)
        locators = project_visual_locators(sources[0])
        assert len(locators) == 2
        repository = EvidenceLocatorRepository(session)
        for locator in locators:
            repository.create(locator)
            assert repository.get(locator.locator_id) == locator
        from app.storage.fact_authority import FactAuthorityValidator
        from app.domain.gates.fact_evidence_closure import validate_locator_and_text_hash
        from app.domain.contracts.enums import GateOutcome
        from types import SimpleNamespace
        FactAuthorityValidator(session).validate_locators(authority, [item.locator_id for item in locators])
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(authority.complete_processing_revision_id)
        outcome, reasons, _ = validate_locator_and_text_hash(
            session, SimpleNamespace(candidate_id="visual", locator_ids=[locators[0].locator_id]), revision)
        assert outcome == GateOutcome.ACCEPTED, reasons
        assert CompleteEvidenceProcessingRevisionRepository(session).get(
            authority.complete_processing_revision_id).model_dump_json() == before
        forged = locators[0].model_copy(update={"locator_id": "visual-locator:" + "f" * 32})
        with pytest.raises(InvalidReferenceError, match="双模型原始判读"):
            repository.create(forged)


def test_rebuild_persisted_clause_only_page_does_not_create_facts(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="visual-source-rebuild")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        coverage_id = _persist_page_review(session, chain, pack=pack)
    with session_factory() as session:
        first = rebuild_visual_sources(session, authority, coverage_id)
        second = rebuild_visual_sources(session, authority, coverage_id)
        assert len(first) == 1
        assert first[0].fact_sources == ()
        assert first[0].handwriting_sources == ()
        assert first[0].model_dump_json() == second[0].model_dump_json()
        assert not session.new and not session.dirty and not session.deleted
        with pytest.raises(FactAuthorityError):
            rebuild_visual_sources(session, authority.model_copy(update={"subject_id": "other"}), coverage_id)


def test_visual_source_validation_error_is_a_repository_reference_error(session_factory, monkeypatch):
    from app.projections.page_review_visual_locators import project_visual_locators
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
    from app.storage.repositories import InvalidReferenceError
    from tests.v2.domain.test_page_review_contracts import _fact

    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="visual-source-error")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        coverage_id = _persist_page_review(session, chain, pack=pack, facts=[_fact()])
        sources = rebuild_visual_sources(session, authority, coverage_id)
        locator = project_visual_locators(sources[0])[0]
        def invalid_sources(*args, **kwargs):
            raise ValueError("frozen source mismatch")
        monkeypatch.setattr("app.storage.page_review_visual_locator_validation.materialize_page_visual_evidence_sources",
                            invalid_sources)
        with pytest.raises(InvalidReferenceError, match="核对依据") as caught:
            EvidenceLocatorRepository(session).create(locator)
        assert isinstance(caught.value.__cause__, ValueError)


def test_visual_policy_job_freezes_and_rebuilds_matching_input(session_factory):
    from app.services.fact_normalization_job_service import FactNormalizationJobService
    from app.services.fact_normalization_source_adapter import build_evidence_normalizer_input
    from tests.v2.domain.test_page_review_contracts import _fact
    from app.agents.evidence_normalizer import (
        DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        build_evidence_normalizer_prompt,
    )
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="visual-policy-job")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        coverage_id = _persist_page_review(session, chain, pack=pack, facts=[_fact()])
    service = FactNormalizationJobService(session_factory)
    parameters = dict(authority=authority, prompt_version_id=chain["prompt_version_id"],
                      model_config_id=chain["model_config_id"], created_by="test",
                      page_review_coverage_id=coverage_id, include_visual_sources=True)
    result = service.create_or_reuse_from_source(**parameters)
    assert service.create_or_reuse_from_source(**parameters).job_id == result.job_id
    payload = service.get_job(result.job_id)["payload"]
    assert payload["visual_source_policy"] == "page-review-visual-sources/v1"
    call = payload["calls"][0]
    with session_factory() as session:
        evidence = build_evidence_normalizer_input(
            session, authority=authority, run_id=result.run_id, call_id=call["call_id"],
            logical_document_id=call["logical_document_id"], page_numbers=call["page_numbers"],
            expected_input_sha256=call["input_sha256"], page_review_coverage_id=coverage_id,
            include_visual_sources=True)
    assert len([item for item in evidence.available_locators if item.page_review_visual]) == 2
    assert evidence.page_review.visual_source_policy == payload["visual_source_policy"]
    from app.agents.evidence_normalizer import _model_input_payload
    projected = _model_input_payload(evidence)
    visual = [item for item in projected["locators"] if item.get("page_review_visual")]
    assert len(visual) == 2
    assert all(item["page_review_visual"] is True for item in visual)
    assert all(item.page_review_visual.page_image_sha256
               for item in evidence.available_locators if item.page_review_visual)
    assert "page_review_visual" in build_evidence_normalizer_prompt(
        evidence, prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
    )


def test_visual_fact_publishes_through_product_job(session_factory):
    from app.domain.contracts.evidence_normalizer import EvidenceNormalizerOutput
    from app.domain.contracts.page_review import PageFactObservation
    from app.projections.page_review_sources import accepted_observations
    from app.services.fact_normalization_executor import (
        FactNormalizationExecutorConfig, create_fact_normalization_executor,
    )
    from app.services.fact_normalization_job_service import FactNormalizationJobService
    from app.storage.fact_repositories import ClinicalFactV2Repository
    from app.workflow.runner import JobRunner
    from tests.v2.domain.test_page_review_contracts import _fact
    from tests.v2.services.test_fact_normalization_persistence import _candidate_fact

    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="visual-publish")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        fact = _fact().model_dump()
        fact["region"]["excerpt"] = fact["raw_text"]
        coverage_id = _persist_page_review(session, chain, pack=pack,
                                          facts=[PageFactObservation.model_validate(fact)])
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(
        authority=authority, prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="test",
        page_review_coverage_id=coverage_id, include_visual_sources=True)

    def transport(evidence):
        locator = next(item for item in evidence.available_locators if item.page_review_visual)
        review = next(item for item in evidence.page_review.reviews
                      if item.page_review_id == locator.page_review_visual.page_review_id)
        refs = accepted_observations([review], evidence.page_review.reconciliations[0],
                                     include_clause_signals=False)
        candidate = _candidate_fact(evidence.run_id, evidence.call_id, locator.locator_id)
        candidate = candidate.model_copy(update={
            "asserted_object": "白细胞", "raw_value": 4.2, "canonical_value": 4.2,
            "unit": "x10^9/L", "source_observation_refs": [refs[0]["source_observation_ref"]],
            "assertion_basis": candidate.assertion_basis.model_copy(update={
                "asserted_object": "白细胞", "assertion_text": locator.localized_text,
                "source_text_sha256": locator.source_text_sha256,
            }),
        })
        return EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
            logical_document_id=evidence.logical_document_id, page_numbers=evidence.page_numbers,
            fact_candidates=[candidate])

    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport_fn=transport))
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert len(facts) == 1, service.get_job(created.job_id)
        assert facts[0].asserted_object == "白细胞"
        assert facts[0].value == 4.2
    from app.services.evidence_api_read_service import EvidenceApiReadService
    from app.api.v2.evidence_processing_schemas import locator_dto
    locators = EvidenceApiReadService(session_factory, None).locators_by_ids(
        facts[0].locator_ids,
        complete_processing_revision_id=authority.complete_processing_revision_id)
    assert set(locators) == set(facts[0].locator_ids)
    assert locator_dto(next(iter(locators.values()))).source_layer_label == "原件核对摘录"
