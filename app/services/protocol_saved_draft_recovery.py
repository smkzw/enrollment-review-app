"""Validate a saved proposal against its failed source run; never revive that run."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.domain.contracts.agent_io import ProtocolDeconstructionDraft, ProtocolDeconstructionInput
from app.domain.contracts.protocol_ingestion import ProtocolExtractionSnapshot
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.storage.codecs import verify_payload_sha256
from app.storage.config import DataPaths
from app.workflow.jobstore import JobStore


class SavedDraftRecoveryError(ValueError):
    """A retained proposal cannot be bound to this source and attempt."""


def load_saved_draft_recovery(
    store: JobStore,
    paths: DataPaths,
    *,
    source_job_id: str,
    candidate_ref: str,
    expected_freeze_sha256: str,
    source_steps: tuple[str, ...],
) -> tuple[dict[str, Any], ProtocolDeconstructionDraft]:
    source_job = store.get_job(source_job_id)
    if (source_job.job_type != "protocol_deconstruction"
            or source_job.state not in {"failed_final", "cancelled"}
            or source_job.lease_owner is not None or source_job.lease_expires_at is not None):
        raise SavedDraftRecoveryError("只能从已结束且无租约的方案解构任务恢复提案。")
    payload = verify_payload_sha256(source_job.payload_json, source_job.payload_sha256)
    if payload.get("session_kind") != "first_deconstruction":
        raise SavedDraftRecoveryError("此入口仅恢复未发布的首次解构，不替代新版方案的基线核验。")
    steps = {step.step_id: step for step in store.list_steps(source_job_id)}
    merged = dict(payload)
    for step_id in source_steps:
        step = steps.get(step_id)
        if step is None or step.state != "completed":
            raise SavedDraftRecoveryError("原任务的来源准备或身份确认没有完整完成。")
        checkpoints = store.list_checkpoints(source_job_id, step_id)
        if not checkpoints:
            raise SavedDraftRecoveryError("已完成的来源步骤缺少可复核记录。")
        for checkpoint_id, checkpoint in checkpoints:
            if store.checkpoint_is_diagnostic(source_job_id, checkpoint_id):
                raise SavedDraftRecoveryError("失败诊断不能冒充成功来源准备记录。")
            merged.update({key: value for key, value in checkpoint.items() if key != "attempt"})
    frozen = store.get_last_checkpoint(source_job_id, source_steps[-1])
    if frozen is None or canonical_hash(frozen[1]) != expected_freeze_sha256:
        raise SavedDraftRecoveryError("原任务的冻结输入与恢复请求不一致。")
    source = ProtocolDeconstructionInput.model_validate(merged["source_input"])
    if (merged.get("sha256") != source.protocol_file_sha256
            or merged.get("snapshot_id") != source.extraction_snapshot_id):
        raise SavedDraftRecoveryError("登记文件、结构快照和冻结来源身份不一致。")
    reference = merged.get("storage_ref")
    if not isinstance(reference, str) or not reference:
        raise SavedDraftRecoveryError("原任务缺少方案原件引用。")
    original = paths.boundary.require_v2_target(paths.blobs_dir / reference)
    if not original.is_file() or sha256(original.read_bytes()).hexdigest() != merged.get("sha256"):
        raise SavedDraftRecoveryError("方案原件缺失或与登记哈希不一致。")
    snapshot = ProtocolExtractionSnapshot.model_validate(merged["extraction_snapshot"])
    if snapshot.snapshot_id != source.extraction_snapshot_id or snapshot.source_sha256 != source.protocol_file_sha256:
        raise SavedDraftRecoveryError("结构快照的实际身份与原件不一致。")
    blocks = paths.boundary.require_v2_target(paths.blobs_dir / snapshot.content_storage_ref)
    if not blocks.is_file() or sha256(blocks.read_bytes()).hexdigest() != snapshot.content_sha256:
        raise SavedDraftRecoveryError("结构块集缺失或与保存的快照哈希不一致。")
    if not candidate_ref.startswith("artifacts/evaluation_manifest/"):
        raise SavedDraftRecoveryError("恢复提案必须来自当前工件库的保存结果。")
    draft = ProtocolDeconstructionDraft.model_validate_json(ArtifactStore(paths).read(candidate_ref))
    if (draft.draft_revision != 1 or draft.project_id != source.project_id
            or draft.protocol_version_id != source.protocol_version_id
            or draft.selected_phase != source.selected_phase):
        raise SavedDraftRecoveryError("保存提案的项目、版本、期别或首稿身份与来源不一致。")
    return merged, draft


def reconcile_saved_source_identity(
    current: ProtocolDeconstructionInput, original: ProtocolDeconstructionInput,
) -> tuple[ProtocolDeconstructionInput, dict[str, Any] | None]:
    """Renew only accidental freeze metadata; changed source content is rejected.

    Interpretation materials are separately registered, not original protocol text.
    The caller appends this renewal at an explicit waiting-user update boundary.
    """
    current_body = current.model_dump(mode="json")
    original_body = original.model_dump(mode="json")
    for body in (current_body, original_body):
        body.pop("interpretation_source_ids", None)
        body.pop("interpretation_sources", None)
        for key in ("parent_rule_catalog", "required_procedure_catalog"):
            body[key].pop("frozen_at")
            body[key].pop("catalog_sha256")
    if current_body != original_body:
        raise SavedDraftRecoveryError("当前来源或目录内容已改变，不能沿用原任务的核对身份和额度。")
    if original.parent_rule_catalog.frozen_at != original.required_procedure_catalog.frozen_at:
        raise SavedDraftRecoveryError("原来源目录的冻结时间不一致。")
    renewed = current.model_copy(update={
        "parent_rule_catalog": original.parent_rule_catalog.model_copy(deep=True),
        "required_procedure_catalog": original.required_procedure_catalog.model_copy(deep=True),
    })
    if renewed == current:
        return current, None
    return renewed, {
        "version": "saved-source-freeze-renewal/v1",
        "previous_source_sha256": canonical_hash(current.model_dump(mode="json")),
        "renewed_source_sha256": canonical_hash(renewed.model_dump(mode="json")),
        "original_source_sha256": canonical_hash(original.model_dump(mode="json")),
        "unchanged_source_and_catalog_content": True,
        "new_model_reading": False,
    }
