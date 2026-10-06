"""Freeze only calculation-bearing source groups from proven candidate receipts."""
import json

from app.domain.contracts.binding_qualification import BindingQualificationPairContext
from app.domain.contracts.computation_input import VERSION, ComputationInputContext, computation_for_condition
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.computation_input import build_computation_input_messages
from app.llm.observation_relation import relation_batch
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.review_candidate_scope import require_prepared_candidate_scope
from app.storage.repositories import ScopeViolationError


def plan_computation_input_batches(groups, *, max_characters):
    if max_characters < 1:
        raise ScopeViolationError("计算输入核对分批额度须为正数")
    batches = []
    for group in sorted(groups, key=lambda item: item.pair_id):
        batch = relation_batch([group])
        messages = build_computation_input_messages([group], batch)
        if len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"))) > max_characters:
            raise ScopeViolationError("本项计算输入及完整来源超过核对额度，不能截去部分记录继续计算")
        batches.append(batch)
    return batches


def load_computation_input_sources(session, artifact_store, *, candidate_job_id, context_id):
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    family = material.get("family")
    if family not in {"predicate", "control"} or material.get("review_context_id") != context_id:
        raise ScopeViolationError("计算输入须来自本次审核已完成的有源候选")
    if family == "predicate":
        frozen = PredicateBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen)
        definitions = {item.predicate_identity_sha256: item.predicate.source_computation
                       for component in frozen.components for item in component.binding_predicates
                       if item.predicate.source_computation is not None}
    else:
        frozen = ControlBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen.evidence_input, control_input=frozen)
        definitions = {item.identity_sha256: item.atom.evaluation.predicate.source_computation
                       for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
                       if item.atom.evaluation is not None and item.atom.evaluation.predicate is not None
                       and item.atom.evaluation.predicate.source_computation is not None}
    if digest != material["review_context_sha256"]:
        raise ScopeViolationError("计算输入与当前审核准备版本不一致")
    by_identity = {identity: [] for identity in definitions}
    for raw in material["pairs"]:
        pair = BindingQualificationPairContext.model_validate(raw)
        if pair.identity_sha256 in by_identity:
            if pair.candidate_family != family or computation_for_condition(pair.condition) != definitions[pair.identity_sha256]:
                raise ScopeViolationError("计算输入对应了不同的要求或方案声明")
            by_identity[pair.identity_sha256].append(pair)
    groups, coverage = [], []
    for identity, computation in sorted(definitions.items()):
        rows = sorted(by_identity[identity], key=lambda item: item.pair_id)
        group_id = None
        if rows:
            content = {"version": VERSION, "identity_sha256": identity,
                       "candidate_job_id": candidate_job_id, "frozen_input_sha256": material["frozen_input_sha256"],
                       "computation": computation.model_dump(mode="json"),
                       "members": [item.model_dump(mode="json") for item in rows]}
            group_id = canonical_hash(content)
            groups.append(ComputationInputContext(pair_id=group_id, **content).model_dump(mode="json"))
        coverage.append({"identity_sha256": identity, "group_id": group_id,
                         "supplied_pair_ids": [item.pair_id for item in rows],
                         "reasons": [] if rows else ["no_computation_sources_in_candidate_input"],
                         "clinical_scope_complete": False})
    payload = {"version": VERSION, "candidate_job_id": candidate_job_id,
               "review_context_id": context_id, "review_context_sha256": digest,
               "frozen_input_sha256": material["frozen_input_sha256"],
               "comparison_sha256": material["comparison_sha256"],
               "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
               "pairs": sorted(groups, key=lambda item: item["pair_id"]), "identity_coverage": coverage}
    return {**payload, "input_sha256": canonical_hash(payload)}
