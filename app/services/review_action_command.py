"""Append a documented manual response; never change the clinical assessment."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.domain.contracts.agents import GateResult
from app.domain.contracts.enums import ActionState, GateOutcome
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.review import ActionRequest, ActionTransition
from app.domain.publication import _build_gate_owned_model, canonical_hash
from app.services.evidence_app_errors import EvidenceAppError
from app.storage.idempotency import IdempotencyConflict, IdempotencyRepository
from app.storage.repositories import (
    GATE_RESULT_CONFIG, ActionRequestRepository, AppendRepository, EpisodeRepository, NotFoundError,
)
from app.storage.review_reference_validation import validate_action_response


class ActionResponseRejected(EvidenceAppError):
    status_code = 409
    code = "ACTION_RESPONSE_REJECTED"
    title = "暂不能保存办理记录"
    recovery = "请刷新办理情况并核对所选回应原件；原审核结论保持不变。"


@dataclass(frozen=True)
class ActionResponseResult:
    action_id: str
    transition_id: str
    record_revision: int


def record_action_response(
    session: Session, *, subject_id: str, review_episode_id: str, action_id: str,
    expected_revision: int, operation: Literal["close_manual", "reopen"], reason: str,
    locator_ids: list[str], response_snapshot_id: str | None,
    response_processing_revision_id: str | None, expected_episode_revision: int | None,
    idempotency_key: str,
) -> ActionResponseResult:
    """Caller owns the single transaction containing receipt, gate and revision."""
    repository = ActionRequestRepository(session)
    previous = repository.get(action_id)
    if (previous.subject_id, previous.review_episode_id) != (subject_id, review_episode_id):
        raise NotFoundError("该受试者审核节点不存在此办理事项")
    if previous.schema_version != "review/v2":
        raise ActionResponseRejected("旧版试运行事项不能在正式办理入口修改。")
    if (not reason.strip() or not idempotency_key.strip() or expected_revision < 1
        or len(set(locator_ids)) != len(locator_ids) or any(not value.strip() for value in locator_ids)):
        raise ActionResponseRejected("请填写办理说明并选择有效的回应原件。")
    command = {
        "version": "review-action-response/v1", "subject_id": subject_id, "episode_id": review_episode_id,
        "action_id": action_id, "expected_revision": expected_revision, "operation": operation,
        "reason": reason.strip(), "locator_ids": sorted(locator_ids), "response_snapshot_id": response_snapshot_id,
        "response_processing_revision_id": response_processing_revision_id,
        "expected_episode_revision": expected_episode_revision,
    }
    digest = canonical_hash(command)
    scope = f"review-action-response:{action_id}"
    receipts = IdempotencyRepository(session)
    receipt = receipts.get(scope, idempotency_key)
    if receipt is not None:
        if receipt.request_sha256 != digest:
            raise IdempotencyConflict(scope=scope, idempotency_key=idempotency_key,
                existing_sha256=receipt.request_sha256, submitted_sha256=digest)
        if receipt.result_type != "action_transition" or not any(
            item.transition_id == receipt.result_id for item in previous.transitions
        ):
            raise ActionResponseRejected("先前办理记录不完整，未重复写入。")
        # Receipt identifies this submission, not a later action revision.
        return ActionResponseResult(action_id, receipt.result_id, expected_revision + 1)
    if previous.revision != expected_revision:
        raise ActionResponseRejected("办理情况已变化，请刷新后核对，您的说明尚未保存。")
    if operation == "close_manual" and previous.state in {ActionState.OPEN, ActionState.REOPENED}:
        target = ActionState.CLOSED_MANUAL
    elif operation == "reopen" and previous.state == ActionState.CLOSED_MANUAL:
        target = ActionState.REOPENED
    else:
        raise ActionResponseRejected("当前办理情况不支持此操作，未改写记录。")

    authority = None
    if locator_ids:
        episode = EpisodeRepository(session).get(review_episode_id)
        if (episode.subject_id != subject_id or episode.project_id != previous.project_id
            or episode.revision != expected_episode_revision
            or episode.active_evidence_snapshot_id != response_snapshot_id
            or episode.active_evidence_processing_revision_id != response_processing_revision_id
            or response_snapshot_id is None or response_processing_revision_id is None):
            raise ActionResponseRejected("回应资料版本已变化，请重新选择原件后保存。")
        authority = FactAuthority(
            project_id=episode.project_id, subject_id=episode.subject_id, review_episode_id=review_episode_id,
            episode_revision=episode.revision, protocol_version_id=episode.protocol_version_id,
            rule_set_id=episode.rule_set_id, rule_set_revision=episode.rule_set_revision,
            evidence_snapshot_v2_id=response_snapshot_id, complete_processing_revision_id=response_processing_revision_id,
        )
    elif target == ActionState.CLOSED_MANUAL or any(value is not None for value in (
        response_snapshot_id, response_processing_revision_id, expected_episode_revision,
    )):
        raise ActionResponseRejected("办结需选择回应原件；无原件的重新办理不应携带资料版本。")
    now = datetime.now(UTC)
    transition_id = f"action-response:{canonical_hash([scope, idempotency_key])[:32]}"
    transition = ActionTransition(
        schema_version="review/v2", transition_id=transition_id, from_state=previous.state,
        to_state=target, occurred_at=now, reason=reason.strip(), locator_ids=sorted(locator_ids),
        response_authority=authority,
    )
    validate_action_response(session, previous, transition)
    gates = AppendRepository(session, GATE_RESULT_CONFIG)
    prior_gate = gates.get(previous.gate_result_id)
    if (prior_gate.result != GateOutcome.ACCEPTED or action_id not in prior_gate.accepted_entity_refs
        or prior_gate.output_hash != canonical_hash(previous.model_dump(mode="json"))):
        raise ActionResponseRejected("原办理记录的保存依据不一致，未追加新记录。")
    gate_id = f"gate:{transition_id}"
    data = previous.model_dump(exclude={"gate_result_id", "publication_fingerprint"})
    data.update(revision=previous.revision + 1, state=target, transitions=[*previous.transitions, transition])
    updated = _build_gate_owned_model(ActionRequest, entity_type="action_request", gate_result_id=gate_id, data=data)
    gate = GateResult(
        gate_result_id=gate_id, gate_name="manual-action-response-gate", result=GateOutcome.ACCEPTED,
        input_scope_hash=canonical_hash({"command": command, "prior_action": previous.model_dump(mode="json"),
            "response_authority": authority.model_dump(mode="json") if authority else None}),
        input_revision_map={action_id: previous.revision},
        input_entity_refs=[action_id, prior_gate.gate_result_id, *sorted(locator_ids)],
        accepted_entity_refs=[action_id, transition_id], affected_scope=[
            previous.rule_component_id if previous.control_origin is None else previous.control_origin.target_id
        ],
        recompute_scope=list(previous.recompute_scope), idempotency_key=f"action-response:{action_id}:{idempotency_key}",
        created_at=now, output_hash=canonical_hash(updated.model_dump(mode="json")),
    )
    gates.save(gate)
    repository.replace(updated, expected_revision)
    receipts.resolve(scope=scope, idempotency_key=idempotency_key, submitted_hash=digest,
        result_type="action_transition", result_id=transition_id)
    return ActionResponseResult(action_id, transition_id, updated.revision)
