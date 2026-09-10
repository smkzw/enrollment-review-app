from types import SimpleNamespace

import pytest

from app.agents.verified_evidence_prompt import verified_evidence_strategy
from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.storage.codecs import decode_contract
from app.storage.models import RuleSetRecord
from app.workflow.runner import StepContext, StepFailure
from tests.v2.domain.test_page_review_contracts import _fact
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_r3_page_review_normalizer_wiring import _persist_page_review


@pytest.mark.parametrize("name", ["SHORT_REFERENCE_INSTRUCTION", "RETAINED_PENDING_INSTRUCTION",
                                  "VERIFIED_EVIDENCE_SYSTEM_CONTRACT", "VERIFIED_EVIDENCE_REPAIR_CONTRACT"])
def test_strategy_hash_covers_actual_prompt_overlays(monkeypatch, name):
    from app.agents import verified_evidence_prompt as prompt
    old = verified_evidence_strategy()
    monkeypatch.setattr(prompt, name, getattr(prompt, name) + "changed")
    assert verified_evidence_strategy()["prompt_sha256"] != old["prompt_sha256"]


@pytest.fixture
def planned(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="verified-strategy")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        coverage = _persist_page_review(session, chain, pack=pack, facts=[_fact()])
    service = FactNormalizationJobService(session_factory)
    args = dict(authority=authority, prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"], created_by="test",
                page_review_coverage_id=coverage, include_visual_sources=True)
    return chain, service, args


def _context(chain, service, created):
    return StepContext(job_id=created.job_id, job_type="fact_normalization",
        job_payload=service.get_job(created.job_id)["payload"],
        step_id="normalize_000_" + chain["logical_document_id"], name="test", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)


def test_strategy_freezes_new_identity_without_mutating_old_job(planned):
    chain, service, args = planned
    old = service.create_or_reuse_from_source(**args)
    original = service.get_job(old.job_id)["payload"]
    new = service.create_or_reuse_from_source(**args, verified_scope_prompt=True)
    assert new.job_id != old.job_id
    assert service.create_or_reuse_from_source(**args, verified_scope_prompt=True).job_id == new.job_id
    assert service.get_job(old.job_id)["payload"] == original
    assert "verified_evidence_strategy" not in original
    assert service.get_job(new.job_id)["payload"]["verified_evidence_strategy"] == verified_evidence_strategy()


def test_strategy_reaches_real_runner_options(planned, session_factory, monkeypatch):
    from app.agents.evidence_normalizer import EvidenceNormalizerRunner
    from app.domain.contracts.evidence_normalizer import EvidenceNormalizerOutput, EvidenceNormalizerUnresolvedItem
    chain, service, args = planned
    new = service.create_or_reuse_from_source(**args, verified_scope_prompt=True)
    seen = []
    def run(self, evidence, transport, **kwargs):
        seen.append(kwargs)
        output = EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
            logical_document_id=evidence.logical_document_id, page_numbers=evidence.page_numbers,
            unresolved_items=[EvidenceNormalizerUnresolvedItem(code="test_only", message="待核实",
                reason="合成测试，不作临床结论", affected_pages=evidence.page_numbers)])
        return SimpleNamespace(final_output=output, attempts=[SimpleNamespace(raw_output_sha256="a" * 64)])
    monkeypatch.setattr(EvidenceNormalizerRunner, "run", run)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=lambda _: "unused"))
    executor(_context(chain, service, new))
    assert len(seen) == 1
    assert all(seen[0][key] is True for key in (
        "pending_details_retained", "compact_references", "verified_scope_prompt"))


@pytest.mark.parametrize("finalize", [False, True])
def test_changed_strategy_rejected_before_recovery_or_model(planned, session_factory, finalize):
    from dataclasses import replace
    from app.services.fact_normalization_job_service import FACT_NORMALIZATION_FINALIZE_STEP_ID
    chain, service, args = planned
    new = service.create_or_reuse_from_source(**args, verified_scope_prompt=True)
    context = _context(chain, service, new)
    if finalize:
        context = replace(context, step_id=FACT_NORMALIZATION_FINALIZE_STEP_ID)
    context.job_payload["verified_evidence_strategy"] = {"version": "changed"}
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=lambda _: pytest.fail("must not call model")))
    with pytest.raises(StepFailure) as error:
        executor(context)
    assert error.value.error_code == "NORMALIZATION_POLICY_INVALID"
