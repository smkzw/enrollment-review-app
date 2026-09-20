"""Slice 5.8 事实规范化命令入口：权威派生、登记配置选择与幂等。"""

from __future__ import annotations

from sqlalchemy import update

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    evidence_normalizer_prompt_template_sha256,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.enums import AgentNode
from app.services.fact_normalization_job_service import FACT_NORMALIZATION_JOB_TYPE
from app.storage.codecs import encode_contract
from app.storage.fact_repositories import FactNormalizationRunRepository
from app.storage.facts_models import FactNormalizationRunRecord
from app.storage.models import PromptVersionRecord, ReviewEpisodeRecord
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
)
from tests.v2.services.test_fact_normalization_persistence import _seed_chain as _seed_ocr_chain
from tests.v2.services.test_r3_page_review_normalizer_wiring import _persist_page_review
from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack
from app.storage.codecs import decode_contract
from app.storage.models import RuleSetRecord
from tests.v2.storage.test_fact_repositories import _update_episode


def _seed_chain(session, **kwargs):
    chain = _seed_ocr_chain(session, **kwargs)
    authority = chain["authority"]
    row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
    pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
    _persist_page_review(session, chain, pack=pack)
    return chain


def _endpoint(subject_id: str, episode_id: str) -> str:
    return (
        f"/api/v2/subjects/{subject_id}/review-episodes/"
        f"{episode_id}/fact-normalization-jobs"
    )


def test_v2_app_registers_fact_normalization_command_service(client):
    assert FACT_NORMALIZATION_JOB_TYPE in client.app.state.job_executors
    assert client.app.state.fact_normalization_job_service is not None
    assert client.app.state.fact_normalization_command_service is not None


def test_formal_normalization_ignores_other_reader_identity(client):
    from app.domain.contracts.page_review import SubjectPageCoverage
    from app.storage.page_review_repository import PageReviewRepository

    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-reader-binding")
        repository = PageReviewRepository(session)
        current = repository.get_coverage(f"{chain['subject_id']}-coverage")
        other = current.model_dump(mode="json")
        other.update(coverage_id="other-reader-result", main_reader_identity_sha256="a" * 64)
        repository.save_coverage(SubjectPageCoverage.model_validate(other))
    response = client.post(_endpoint(chain["subject_id"], chain["episode_id"]), json={})
    assert response.status_code == 201, response.text
    assert client.app.state.page_review_runtime._executor is None


def test_mtplx_dual_main_coverage_is_selectable_for_normalization(client, monkeypatch):
    """GLM main-A + MTPLX main-B 双主读结果必须能直接进入正式整理，不得因第三读语义回放失败。"""
    from app.domain.contracts.page_review import PageReviewLane
    from app.llm.page_review_harness import require_page_reader_routes

    monkeypatch.setenv("INDEPENDENT_VLM_PROVIDER", "zhipu-coding-plan")
    monkeypatch.setenv("PAGE_REVIEW_MAIN_A_MODEL", "glm-5.3-flash")
    monkeypatch.setenv("PAGE_REVIEW_MAIN_B_PROVIDER", "mtplx")
    monkeypatch.setenv("PAGE_REVIEW_MAIN_B_MODEL", "mtplx-flash-next-optimized-speed")
    routes = require_page_reader_routes(require_credentials=False)
    assert set(routes) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert routes[PageReviewLane.MAIN_A].reasoning_effort == "high"
    assert routes[PageReviewLane.MAIN_B].reasoning_effort == "xhigh"

    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_ocr_chain(session, prefix="api-mtplx-dual-main")
        authority = chain["authority"]
        row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
        pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
        _persist_page_review(session, chain, pack=pack, routes=routes)
    response = client.post(_endpoint(chain["subject_id"], chain["episode_id"]), json={})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"]


def test_formal_normalization_rejects_stale_reader_prompt(client, monkeypatch):
    from tests.v2.services import test_r3_page_review_normalizer_wiring as fixtures

    monkeypatch.setattr(fixtures, "PAGE_REVIEW_PROMPT_VERSION", "page-review-r3/obsolete")
    with client.app.state.session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-stale-reader-prompt")
    response = client.post(_endpoint(chain["subject_id"], chain["episode_id"]), json={})
    assert response.status_code == 409, response.text
    assert "PAGE_COVERAGE_NOT_READY" in response.text


def test_create_normalization_job_idempotent_and_chinese(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-norm")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]

    path = _endpoint(subject_id, episode_id)
    first = client.post(path, json={"idempotency_intent": "整理当前启用资料"})
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["created"] is True
    assert body["job_id"]
    assert body["run_id"]
    assert body["state_label"]
    assert body["recovery_action"]
    raw = first.text
    for forbidden in (
        "PromptVersion",
        "ModelConfig",
        "provider",
        "pipeline",
        "schema",
        "Agent",
        "inclusion_met",
        "verdict",
    ):
        assert forbidden not in raw

    second = client.post(path, json={"idempotency_intent": "整理当前启用资料"})
    assert second.status_code == 200, second.text
    assert second.json()["job_id"] == body["job_id"]
    assert second.json()["run_id"] == body["run_id"]
    assert second.json()["created"] is False

    job = client.get(f"/api/v2/jobs/{body['job_id']}")
    assert job.status_code == 200, job.text
    assert job.json()["job_id"] == body["job_id"]
    assert "recovery_action" in job.json()


def test_generic_retry_route_dispatches_cancelled_normalization_job(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-cancelled-retry")

    created = client.post(
        _endpoint(chain["subject_id"], chain["episode_id"]), json={}
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["job_id"]
    run_id = created.json()["run_id"]

    cancelled = client.post(f"/api/v2/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "cancelled"

    resumed = client.post(f"/api/v2/jobs/{job_id}/retry")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["state"] == "queued"
    with factory() as session:
        assert (
            FactNormalizationRunRepository(session).get(run_id).status.value
            == "running"
        )


def test_command_uses_lifespan_registered_pair_not_client_or_fixture_config(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-runtime-pair")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]

    registered = client.app.state.evidence_normalizer_runtime_config
    response = client.post(
        _endpoint(subject_id, episode_id),
        json={"idempotency_intent": chain["prompt_version_id"]},
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["run_id"]

    with factory() as session:
        run = session.get(FactNormalizationRunRecord, run_id)

    assert run is not None
    assert run.prompt_version_id == registered.prompt_version_id
    assert run.model_config_id == registered.model_config_id
    assert run.prompt_version_id != chain["prompt_version_id"]
    assert run.model_config_id != chain["model_config_id"]


def test_rejects_tampered_client_authority_and_config_fields(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-tamper")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]

    path = _endpoint(subject_id, episode_id)
    for payload in (
        {"prompt_version_id": "client-prompt"},
        {"model_config_id": "client-model"},
        {"authority": {"project_id": "x"}},
        {
            "evidence_snapshot_v2_id": "snap-x",
            "complete_processing_revision_id": "rev-x",
        },
        {"page_plan": [{"logical_document_id": "doc", "page_numbers": [1]}]},
        {"input_scope_sha256": "a" * 64},
    ):
        rejected = client.post(path, json=payload)
        assert rejected.status_code == 422, (payload, rejected.text)
        assert "error" in rejected.json()
        assert rejected.json()["error"]["title"]
        assert "sqlalchemy" not in rejected.text.lower()


def test_rejects_inactive_evidence(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-inactive")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        episode = session.get(ReviewEpisodeRecord, episode_id)
        _update_episode(
            session,
            episode,
            active_evidence_snapshot_id=None,
            active_evidence_processing_revision_id=None,
        )

    inactive = client.post(_endpoint(subject_id, episode_id), json={})
    assert inactive.status_code == 422, inactive.text
    error = inactive.json()["error"]
    assert "启用" in error["detail"] or "资料" in error["detail"]
    assert error["recovery_action"]
    assert "PromptVersion" not in inactive.text


def test_rejects_incomplete_or_mismatched_active_revision(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-stale")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        episode = session.get(ReviewEpisodeRecord, episode_id)
        # base 修订存在但不是可激活 complete，模拟活动资料不完整/失配。
        _update_episode(
            session,
            episode,
            active_evidence_processing_revision_id=chain["base_revision_id"],
        )

    mismatched = client.post(_endpoint(subject_id, episode_id), json={})
    assert mismatched.status_code in {409, 422}, mismatched.text
    assert mismatched.json()["error"]["recovery_action"]
    assert "sqlalchemy" not in mismatched.text.lower()


def test_rejects_missing_registered_prompt_config(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-cfg-miss")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        registered = client.app.state.evidence_normalizer_runtime_config
        wrong_prompt = PromptVersion(
            prompt_version_id=registered.prompt_version_id,
            node=AgentNode.PROTOCOL_DECONSTRUCTOR,
            template_sha256=evidence_normalizer_prompt_template_sha256(
                DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
            ),
            schema_version_id="phase5/facts/v1",
        )
        payload_json, payload_sha256 = encode_contract(wrong_prompt)
        session.execute(
            update(PromptVersionRecord)
            .where(
                PromptVersionRecord.prompt_version_id == registered.prompt_version_id
            )
            .values(
                node=AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )

    missing = client.post(_endpoint(subject_id, episode_id), json={})
    assert missing.status_code == 422, missing.text
    assert "配置" in missing.json()["error"]["detail"]
    assert missing.json()["error"]["recovery_action"]


def test_ignores_other_prompt_identity_when_lifespan_pair_is_frozen(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-cfg-amb")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        AppendRepository(session, PROMPT_VERSION_CONFIG).save(
            PromptVersion(
                prompt_version_id=f"{chain['prompt_version_id']}-dup",
                node=AgentNode.EVIDENCE_NORMALIZER,
                template_sha256=evidence_normalizer_prompt_template_sha256(
                    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
                ),
                schema_version_id="phase5/facts/v1",
            )
        )

    selected = client.post(_endpoint(subject_id, episode_id), json={})
    assert selected.status_code == 201, selected.text
    with factory() as session:
        run = session.get(FactNormalizationRunRecord, selected.json()["run_id"])
    assert run is not None
    assert (
        run.prompt_version_id
        == client.app.state.evidence_normalizer_runtime_config.prompt_version_id
    )


def test_ignores_other_agent_model_when_lifespan_pair_is_frozen(client):
    factory = client.app.state.session_factory
    with factory() as session, session.begin():
        chain = _seed_chain(session, prefix="api-model-amb")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        AppendRepository(session, MODEL_CONFIG_CONFIG).save(
            ModelConfigContract(
                model_config_id=f"{chain['model_config_id']}-protocol",
                provider="omlx",
                model="protocol-only-model",
                reasoning_effort="medium",
                parameters={
                    "agent_node": AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                    "max_tokens": 2048,
                    "temperature": 0.1,
                },
            )
        )

    selected = client.post(_endpoint(subject_id, episode_id), json={})
    assert selected.status_code == 201, selected.text
    with factory() as session:
        run = session.get(FactNormalizationRunRecord, selected.json()["run_id"])
    assert run is not None
    assert (
        run.model_config_id
        == client.app.state.evidence_normalizer_runtime_config.model_config_id
    )
