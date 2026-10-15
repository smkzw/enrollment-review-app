"""Evidence Normalizer runtime registration at the real V2 app boundary.

These tests intentionally start the application against a brand-new temporary
database.  A hand-seeded PromptVersion/ModelConfig pair is not sufficient
evidence here: the command endpoint must work from the application lifespan's
own registration, and a restart must preserve the append-only identities.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import config as runtime_config
from app.domain.contracts.agents import ModelConfigContract, PromptVersion
from app.domain.contracts.enums import AgentNode
from app.services.fact_normalization_command_service import (
    AppFactNormalizationConfigError,
    register_evidence_normalizer_runtime_config,
    select_registered_evidence_normalizer_config,
)
from app.services.fact_normalization_job_service import FACT_NORMALIZATION_JOB_TYPE
from app.storage.codecs import encode_contract
from app.storage.models import ModelConfigRecord, PromptVersionRecord
from app.storage.repositories import MODEL_CONFIG_CONFIG, AppendRepository


def _runtime_snapshot(app):
    """Return the persisted runtime identities and payloads for one app run."""
    with app.state.session_factory() as session:
        prompts = session.execute(select(PromptVersionRecord)).scalars().all()
        models = session.execute(select(ModelConfigRecord)).scalars().all()
        return {
            "prompts": [
                {
                    "id": row.prompt_version_id,
                    "node": row.node,
                    "template_sha256": row.template_sha256,
                    "schema_version_id": row.schema_version_id,
                    "payload_json": row.payload_json,
                    "payload_sha256": row.payload_sha256,
                }
                for row in sorted(prompts, key=lambda item: item.prompt_version_id)
                if row.node == AgentNode.EVIDENCE_NORMALIZER.value
            ],
            "models": [
                {
                    "id": row.model_config_id,
                    "provider": row.provider,
                    "model": row.model,
                    "reasoning_effort": row.reasoning_effort,
                    "parameters": json.loads(row.payload_json)["parameters"],
                    "payload_json": row.payload_json,
                    "payload_sha256": row.payload_sha256,
                }
                for row in sorted(models, key=lambda item: item.model_config_id)
                if json.loads(row.payload_json)["parameters"].get("agent_node")
                == AgentNode.EVIDENCE_NORMALIZER.value
            ],
        }


def test_fresh_app_start_registers_exactly_one_normalizer_pair(build_app):
    app = build_app()
    with TestClient(app):
        snapshot = _runtime_snapshot(app)
        assert len(snapshot["prompts"]) == 1
        assert len(snapshot["models"]) == 1

        with app.state.session_factory() as session:
            selected = select_registered_evidence_normalizer_config(session)

        assert selected.prompt_version_id == snapshot["prompts"][0]["id"]
        assert selected.model_config_id == snapshot["models"][0]["id"]
        assert snapshot["models"][0]["parameters"]["max_tokens"] >= 1
        assert "temperature" not in snapshot["models"][0]["parameters"]


def test_restart_reuses_immutable_runtime_identities_and_payloads(build_app):
    first_app = build_app()
    with TestClient(first_app):
        before = _runtime_snapshot(first_app)

    second_app = build_app()
    with TestClient(second_app):
        after = _runtime_snapshot(second_app)

    assert after == before


def test_runtime_setting_change_appends_new_model_identity_without_rewriting_old(
    build_app, monkeypatch,
):
    first_app = build_app()
    with TestClient(first_app):
        before = _runtime_snapshot(first_app)
        original = before["models"][0]

    monkeypatch.setattr(
        runtime_config,
        "EVIDENCE_NORMALIZER_MODEL",
        f"{original['model']}-changed-for-regression",
    )
    second_app = build_app()
    with TestClient(second_app):
        after = _runtime_snapshot(second_app)
        changed = second_app.state.evidence_normalizer_runtime_config

        assert changed.model_config_id != original["id"]
        assert len(after["prompts"]) == len(before["prompts"]) == 1
        assert len(after["models"]) == len(before["models"]) + 1
        preserved = next(
            row for row in after["models"] if row["id"] == original["id"]
        )
        assert preserved == original

    third_app = build_app()
    with TestClient(third_app):
        assert _runtime_snapshot(third_app) == after
        assert third_app.state.evidence_normalizer_runtime_config == changed


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"provider": "agent-that-is-not-supported"}, "供应商"),
        ({"model": "   "}, "模型名称"),
        ({"reasoning_effort": "unsupported"}, "推理强度"),
        ({"max_tokens": 0}, "最大输出"),
        ({"temperature": 3.1}, "采样温度"),
    ],
)
def test_invalid_runtime_setting_is_rejected_without_partial_registration(
    build_app, overrides, message
):
    app = build_app()
    with TestClient(app):
        before = _runtime_snapshot(app)
        with pytest.raises(AppFactNormalizationConfigError, match=message):
            register_evidence_normalizer_runtime_config(
                app.state.session_factory,
                **overrides,
            )
        assert _runtime_snapshot(app) == before


def test_contract_drift_on_existing_identity_fails_closed_on_next_start(build_app):
    first_app = build_app()
    with TestClient(first_app):
        registered = first_app.state.evidence_normalizer_runtime_config
        with first_app.state.session_factory() as session, session.begin():
            prompt = session.get(
                PromptVersionRecord, registered.prompt_version_id
            )
            assert prompt is not None
            drifted = PromptVersion(
                prompt_version_id=registered.prompt_version_id,
                node=AgentNode.EVIDENCE_NORMALIZER,
                template_sha256=prompt.template_sha256,
                schema_version_id="phase5/facts/drifted-v1",
            )
            payload_json, payload_sha256 = encode_contract(drifted)
            session.execute(
                update(PromptVersionRecord)
                .where(
                    PromptVersionRecord.prompt_version_id
                    == registered.prompt_version_id
                )
                .values(
                    schema_version_id=drifted.schema_version_id,
                    payload_json=payload_json,
                    payload_sha256=payload_sha256,
                )
            )

    second_app = build_app()
    with pytest.raises(AppFactNormalizationConfigError, match="合同漂移"):
        with TestClient(second_app):
            pass


def test_frozen_normalizer_pair_ignores_other_agent_model_registration(build_app):
    app = build_app()
    with TestClient(app):
        registered = app.state.evidence_normalizer_runtime_config
        with app.state.session_factory() as session, session.begin():
            AppendRepository(session, MODEL_CONFIG_CONFIG).save(
                ModelConfigContract(
                    model_config_id="protocol-deconstructor/runtime-sibling",
                    provider="omlx",
                    model="protocol-only-model",
                    reasoning_effort="medium",
                    parameters={
                        "agent_node": AgentNode.PROTOCOL_DECONSTRUCTOR.value,
                        "max_tokens": 1024,
                        "temperature": 0.0,
                    },
                )
            )
            selected = select_registered_evidence_normalizer_config(
                session, registered_config=registered
            )

        assert selected == registered


def test_v2_app_registers_fact_normalization_executor(client):
    assert FACT_NORMALIZATION_JOB_TYPE in client.app.state.job_executors
