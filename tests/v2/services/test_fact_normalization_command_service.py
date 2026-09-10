"""事实规范化命令服务：权威派生与登记配置选择。"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.agents.evidence_normalizer import (
    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
    evidence_normalizer_prompt_template_sha256,
)
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.enums import AgentNode
from app.services.evidence_app_errors import AppNotFoundError, AppStaleAuthorityError
from app.services.fact_normalization_command_service import (
    AppFactNormalizationConfigError,
    AppFactNormalizationRejectedError,
    FactNormalizationCommandService,
    register_evidence_normalizer_runtime_config,
    authority_from_active_episode,
    select_registered_evidence_normalizer_config,
)
from app.storage.codecs import encode_contract
from app.storage.models import PromptVersionRecord, ReviewEpisodeRecord
from app.storage.repositories import (
    MODEL_CONFIG_CONFIG,
    PROMPT_VERSION_CONFIG,
    AppendRepository,
)
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.storage.test_fact_repositories import _update_episode


def test_command_service_reuses_job_for_same_active_authority(session_factory):
    registered = register_evidence_normalizer_runtime_config(session_factory)
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-idem")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]

    svc = FactNormalizationCommandService(
        session_factory, registered_config=registered
    )
    first = svc.create_or_reuse(subject_id=subject_id, review_episode_id=episode_id)
    second = svc.create_or_reuse(
        subject_id=subject_id,
        review_episode_id=episode_id,
        idempotency_intent="ignored-for-key",
    )
    assert first.created is True
    assert second.created is False
    assert first.job_id == second.job_id
    assert first.run_id == second.run_id
    assert svc.job_service.get_job(first.job_id)["payload"]["max_pages_per_call"] == 2


def test_authority_rejects_inactive_episode(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-inactive")
        episode = session.get(ReviewEpisodeRecord, chain["episode_id"])
        _update_episode(
            session,
            episode,
            active_evidence_snapshot_id=None,
            active_evidence_processing_revision_id=None,
        )
        with pytest.raises(AppFactNormalizationRejectedError, match="启用"):
            authority_from_active_episode(session, chain["episode_id"])


def test_authority_rejects_mismatched_active_revision(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-mismatch")
        episode = session.get(ReviewEpisodeRecord, chain["episode_id"])
        _update_episode(
            session,
            episode,
            active_evidence_processing_revision_id=chain["base_revision_id"],
        )
        with pytest.raises(AppStaleAuthorityError):
            authority_from_active_episode(session, chain["episode_id"])


def test_select_config_happy_path(session_factory):
    registered = register_evidence_normalizer_runtime_config(session_factory)
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-cfg")
        selected = select_registered_evidence_normalizer_config(
            session, registered_config=registered
        )
        assert selected == registered
        assert selected.prompt_version_id != chain["prompt_version_id"]
        assert selected.model_config_id != chain["model_config_id"]
        model = AppendRepository(session, MODEL_CONFIG_CONFIG).get_or_none(
            selected.model_config_id
        )
        assert model is not None
        assert (
            model.parameters["normalization_policy_version"]
            == "phase5/normalization-policy/v9"
        )


def test_select_config_absent_prompt(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-cfg-miss")
        wrong_prompt = PromptVersion(
            prompt_version_id=chain["prompt_version_id"],
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
                PromptVersionRecord.prompt_version_id == chain["prompt_version_id"]
            )
            .values(
                node=AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )
        with pytest.raises(AppFactNormalizationConfigError, match="尚未登记"):
            select_registered_evidence_normalizer_config(session)


def test_select_config_ambiguous_prompt(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-cfg-amb")
        AppendRepository(session, PROMPT_VERSION_CONFIG).save(
            PromptVersion(
                prompt_version_id=f"{chain['prompt_version_id']}-2",
                node=AgentNode.EVIDENCE_NORMALIZER,
                template_sha256=evidence_normalizer_prompt_template_sha256(
                    DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
                ),
                schema_version_id="phase5/facts/v1",
            )
        )
        with pytest.raises(AppFactNormalizationConfigError, match="多份"):
            select_registered_evidence_normalizer_config(session)


def test_select_config_ambiguous_model(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-model-amb")
        AppendRepository(session, MODEL_CONFIG_CONFIG).save(
            ModelConfigContract(
                model_config_id=f"{chain['model_config_id']}-2",
                provider="omlx",
                model="other",
                reasoning_effort="medium",
                parameters={
                    "max_tokens": 1024,
                    "temperature": 0.0,
                    "agent_node": AgentNode.EVIDENCE_NORMALIZER.value,
                },
            )
        )
        with pytest.raises(AppFactNormalizationConfigError, match="模型配置"):
            select_registered_evidence_normalizer_config(session)


def test_marked_model_preferred_over_unmarked_siblings(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(
            session, prefix="cmd-mark", mark_normalizer_model=False
        )
        AppendRepository(session, MODEL_CONFIG_CONFIG).save(
            ModelConfigContract(
                model_config_id=f"{chain['model_config_id']}-marked",
                provider="omlx",
                model="marked-normalizer",
                reasoning_effort="medium",
                parameters={
                    "max_tokens": 2048,
                    "temperature": 0.0,
                    "agent_node": AgentNode.EVIDENCE_NORMALIZER.value,
                },
            )
        )
        selected = select_registered_evidence_normalizer_config(session)
        assert selected.model_config_id == f"{chain['model_config_id']}-marked"


def test_unmarked_model_is_never_selected_as_normalizer(session_factory):
    with session_factory() as session, session.begin():
        _seed_chain(
            session,
            prefix="cmd-unmarked-only",
            mark_normalizer_model=False,
        )

        with pytest.raises(AppFactNormalizationConfigError, match="无归属"):
            select_registered_evidence_normalizer_config(session)


def test_command_rejects_subject_mismatch(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-scope")
        episode_id = chain["episode_id"]

    svc = FactNormalizationCommandService(session_factory)
    with pytest.raises(AppNotFoundError):
        svc.create_or_reuse(
            subject_id="not-the-subject",
            review_episode_id=episode_id,
        )


def test_client_intent_cannot_force_config_ids(session_factory):
    """命令路径不接受配置 id；登记提示词失效时意图字符串不能冒充配置。"""
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="cmd-no-seed")
        subject_id = chain["subject_id"]
        episode_id = chain["episode_id"]
        prompt_version_id = chain["prompt_version_id"]
        wrong_prompt = PromptVersion(
            prompt_version_id=prompt_version_id,
            node=AgentNode.PROTOCOL_DECONSTRUCTOR,
            template_sha256=evidence_normalizer_prompt_template_sha256(
                DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
            ),
            schema_version_id="phase5/facts/v1",
        )
        payload_json, payload_sha256 = encode_contract(wrong_prompt)
        session.execute(
            update(PromptVersionRecord)
            .where(PromptVersionRecord.prompt_version_id == prompt_version_id)
            .values(
                node=AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
        )

    svc = FactNormalizationCommandService(session_factory)
    with pytest.raises(AppFactNormalizationConfigError):
        svc.create_or_reuse(
            subject_id=subject_id,
            review_episode_id=episode_id,
            idempotency_intent=prompt_version_id,
        )
