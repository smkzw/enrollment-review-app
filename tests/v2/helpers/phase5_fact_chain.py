"""Phase 5 聚焦测试共用的真实 Phase 4 证据链。"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.domain.contracts.enums import FactCallStatus, FactNormalizationRunStatus
from app.domain.contracts.facts import (
    FactNormalizationCall,
    FactNormalizationRun,
    fact_run_idempotency_key,
)
from app.domain.contracts.review import ReviewEpisode
from app.storage.codecs import decode_contract, encode_contract
from app.storage.fact_repositories import (
    FactNormalizationCallRepository,
    FactNormalizationRunRepository,
)
from app.storage.models import ReviewEpisodeRecord, WorkflowStageRecord
from sqlalchemy import select, update
from tests.v2.services.test_fact_normalization_persistence import (
    _seed_chain as _seed_phase4_chain,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def seed_valid_fact_chain(
    session,
    prefix: str,
    *,
    fixture_index: int = 0,
    create_run: bool = True,
) -> dict[str, object]:
    """创建经正式仓储验证的快照、OCR、定位、元数据和完整修订。"""
    chain = _seed_phase4_chain(
        session,
        prefix,
        fixture_index=fixture_index,
        include_metadata=True,
    )
    workflow_stage_id = session.execute(
        select(WorkflowStageRecord.workflow_stage_id).where(
            WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
            WorkflowStageRecord.stage == "screening",
        )
    ).scalar_one()
    episode_row = session.get(ReviewEpisodeRecord, chain["episode_id"])
    episode = decode_contract(
        ReviewEpisode, episode_row.payload_json, episode_row.payload_sha256
    ).model_copy(update={"workflow_stage_id": workflow_stage_id})
    payload_json, payload_sha256 = encode_contract(episode)
    session.execute(
        update(ReviewEpisodeRecord)
        .where(ReviewEpisodeRecord.review_episode_id == chain["episode_id"])
        .values(
            workflow_stage_id=workflow_stage_id,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
        )
    )
    session.expire_all()
    result: dict[str, object] = {
        **chain,
        "review_episode_id": chain["episode_id"],
        "evidence_snapshot_v2_id": chain["snapshot_id"],
        "complete_processing_revision_id": chain["complete_revision_id"],
        "base_processing_revision_id": chain["base_revision_id"],
        "workflow_stage_id": workflow_stage_id,
    }
    if not create_run:
        return result

    run_id = f"{prefix}-run"
    call_id = f"{prefix}-call"
    authority = chain["authority"]
    run = FactNormalizationRun(
        run_id=run_id,
        authority=authority,
        idempotency_key=fact_run_idempotency_key(
            authority=authority,
            prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"],
            input_scope_sha256=_sha(f"{prefix}-input-scope"),
        ),
        prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"],
        input_scope_sha256=_sha(f"{prefix}-input-scope"),
        status=FactNormalizationRunStatus.SUCCEEDED,
        created_at=NOW,
        created_by="tester",
    )
    FactNormalizationRunRepository(session).create_or_reuse(run)
    FactNormalizationCallRepository(session).create(
        FactNormalizationCall(
            call_id=call_id,
            run_id=run_id,
            logical_document_id=chain["logical_document_id"],
            page_numbers=[1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=_sha(f"{prefix}-call-input"),
            created_at=NOW,
        )
    )
    result.update({"run_id": run_id, "call_id": call_id})
    return result
