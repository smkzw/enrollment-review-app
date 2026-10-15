"""Prepare frequency evidence from the existing frozen candidate sources."""
import json

from app.domain.contracts.binding_qualification import BindingQualificationPairContext
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.frequency_evidence import FREQUENCY_EVIDENCE_VERSION, FrequencyEvidenceContext
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.frequency_evidence import build_frequency_evidence_messages, frequency_batch
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.review_candidate_scope import require_prepared_candidate_scope
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository


def plan_frequency_evidence_batches(groups, *, max_characters):
    if max_characters < 1:
        raise ScopeViolationError("频次核对分批额度须为正数")
    batches = []
    for group in sorted(groups, key=lambda item: item.pair_id):
        batch = frequency_batch([group])
        messages = build_frequency_evidence_messages([group], batch)
        if len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"))) > max_characters:
            raise ScopeViolationError("该项频次原文超出单次核对范围，资料已保留，不截去记录继续计数")
        batches.append(batch)
    return batches


def load_frequency_evidence_input(session, artifact_store, *, candidate_job_id, context_id):
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    family = material.get("family")
    if family not in {"predicate", "control"} or material.get("review_context_id") != context_id:
        raise ScopeViolationError("频次原文必须来自当前审核候选")
    if family == "predicate":
        frozen = PredicateBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen)
        windows = {item.predicate_identity_sha256: item.predicate.occurrence_window
                   for component in frozen.components for item in component.binding_predicates
                   if item.predicate.occurrence_window is not None}
    else:
        frozen = ControlBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen.evidence_input, control_input=frozen)
        windows = {item.identity_sha256: item.atom.evaluation.predicate.occurrence_window
                   for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
                   if item.atom.evaluation is not None and item.atom.evaluation.predicate is not None
                   and item.atom.evaluation.predicate.occurrence_window is not None}
    if digest != material["review_context_sha256"]:
        raise ScopeViolationError("频次输入与当前审核资料版本不同")
    context = ReviewContextV2Repository(session).get(context_id)
    if context.context_sha256 != digest:
        raise ScopeViolationError("频次节点说明与审核输入不同")
    stage = next(item for item in context.workflow_stages
                 if item.workflow_stage_id == context.review_episode.workflow_stage_id)
    members = {identity: [] for identity in windows}
    for raw in material["pairs"]:
        pair = BindingQualificationPairContext.model_validate(raw)
        if pair.identity_sha256 in members:
            if pair.candidate_family != family:
                raise ScopeViolationError("频次候选混入其他要求类型")
            members[pair.identity_sha256].append(pair)
    groups, coverage = [], []
    for identity, window in sorted(windows.items()):
        rows = sorted(members[identity], key=lambda item: item.pair_id)
        group_id = None
        if rows:
            content = {
                "version": FREQUENCY_EVIDENCE_VERSION, "identity_sha256": identity,
                "candidate_job_id": candidate_job_id, "frozen_input_sha256": material["frozen_input_sha256"],
                "window": window.model_dump(mode="json"),
                "members": [item.model_dump(mode="json") for item in rows],
                "workflow_stage": stage.model_dump(mode="json"),
            }
            group_id = canonical_hash(content)
            groups.append(FrequencyEvidenceContext(pair_id=group_id, **content).model_dump(mode="json"))
        coverage.append({
            "identity_sha256": identity, "group_id": group_id,
            "supplied_pair_ids": [item.pair_id for item in rows],
            "clinical_scope_complete": False,
            "reasons": [] if rows else ["no_frequency_sources_in_candidate_input"],
        })
    payload = {
        "version": "frequency-evidence-input/v4", "candidate_job_id": candidate_job_id,
        "review_context_id": context_id, "review_context_sha256": digest,
        "frozen_input_sha256": material["frozen_input_sha256"],
        "comparison_sha256": material["comparison_sha256"],
        "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
        "pairs": sorted(groups, key=lambda item: item["pair_id"]), "identity_coverage": coverage,
    }
    return {**payload, "input_sha256": canonical_hash(payload)}
