"""Keep each requirement's supplied observation set together without pair explosion."""
import json

from app.domain.contracts.binding_qualification import BindingQualificationPairContext
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.observation_relation import OBSERVATION_RELATION_VERSION, ObservationRelationContext
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.observation_relation import build_observation_relation_messages, relation_batch
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.review_candidate_scope import require_prepared_candidate_scope
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository


def plan_observation_relation_batches(groups, *, max_characters):
    if max_characters < 1:
        raise ScopeViolationError("观察关系分批额度须为正数")
    batches = []
    for group in sorted(groups, key=lambda item: item.pair_id):
        batch = relation_batch([group])
        messages = build_observation_relation_messages([group], batch)
        if len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"))) > max_characters:
            raise ScopeViolationError("本项要求对应的原文过多，暂不能一次核实；资料已保留，不会截去部分原文继续判断")
        batches.append(batch)
    return batches


def load_observation_relation_input(session, artifact_store, *, candidate_job_id, context_id):
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    family = material.get("family")
    if family not in {"predicate", "control"} or material.get("review_context_id") != context_id:
        raise ScopeViolationError("复查对应须使用本次审核的原文候选")
    if family == "predicate":
        frozen = PredicateBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen)
        schemes = {item.predicate_identity_sha256: item.predicate.repeat_scheme
                   for component in frozen.components
                   for item in (*component.trigger_predicates, *component.exception_predicates)
                   if item.predicate.repeat_scheme is not None}
        auxiliary_identities = {}
        for component in frozen.components:
            for owner in (*component.trigger_predicates, *component.exception_predicates):
                if owner.predicate.repeat_scheme is None:
                    continue
                wanted = {key for condition in component.repeat_trigger_conditions
                          if condition.condition_id in owner.predicate.repeat_scheme.ancillary_condition_ids
                          for key, role in condition.predicate_evidence_roles.items()
                          if role.role in {"initial_observation", "preceding_observation", "target_observation"}}
                auxiliary_identities[owner.predicate_identity_sha256] = {
                    item.predicate_identity_sha256 for item in component.repeat_trigger_predicates
                    if item.predicate_id in wanted
                }
    else:
        frozen = ControlBindingFrozenInput.model_validate(material["frozen_input"])
        digest = require_prepared_candidate_scope(session, context_id, frozen.evidence_input, control_input=frozen)
        schemes = {item.identity_sha256: item.atom.evaluation.repeat_scheme
                   for item in project_control_atom_identities(frozen.publication)
                   if item.atom.evaluation is not None and item.atom.evaluation.repeat_scheme is not None}
        identities = project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
        auxiliary_identities = {}
        for owner in identities:
            if owner.identity_sha256 not in schemes:
                continue
            control = next(item for item in frozen.publication.catalog.controls
                           if item.protocol_control_id == owner.protocol_control_id)
            wanted = {key for condition in control.repeat_trigger_conditions
                      if condition.condition_id in schemes[owner.identity_sha256].ancillary_condition_ids
                      for key, role in condition.predicate_evidence_roles.items()
                      if role.role in {"initial_observation", "preceding_observation", "target_observation"}}
            auxiliary_identities[owner.identity_sha256] = {
                item.identity_sha256 for item in identities
                if item.protocol_control_id == owner.protocol_control_id
                and item.layer == "repeat_trigger" and item.atom_id in wanted
            }
    if digest != material["review_context_sha256"]:
        raise ScopeViolationError("复查对应的资料版本与当前审核不一致")
    context = ReviewContextV2Repository(session).get(context_id)
    if context.context_sha256 != digest:
        raise ScopeViolationError("复查对应的流程说明与审核准备不一致")
    workflow_stage = next(item for item in context.workflow_stages
                          if item.workflow_stage_id == context.review_episode.workflow_stage_id)
    members = {identity: [] for identity in set(schemes) | {
        key for values in auxiliary_identities.values() for key in values
    }}
    for raw in material["pairs"]:
        pair = BindingQualificationPairContext.model_validate(raw)
        if pair.identity_sha256 in members:
            if pair.candidate_family != family:
                raise ScopeViolationError("复查对应的要求类型与原文候选不一致")
            members[pair.identity_sha256].append(pair)
    groups, coverage = [], []
    for identity, scheme in sorted(schemes.items()):
        rows = sorted(members[identity], key=lambda item: item.pair_id)
        auxiliary_rows = sorted((item for key in auxiliary_identities[identity] for item in members[key]),
                                key=lambda item: item.pair_id)
        group_id = None
        if rows:
            content = {
                "version": OBSERVATION_RELATION_VERSION,
                "identity_sha256": identity, "candidate_job_id": candidate_job_id,
                "frozen_input_sha256": material["frozen_input_sha256"],
                "scheme": scheme.model_dump(mode="json"),
                "members": [item.model_dump(mode="json") for item in rows],
                "auxiliary_members": [item.model_dump(mode="json") for item in auxiliary_rows],
                "workflow_stage": workflow_stage.model_dump(mode="json"),
            }
            group_id = canonical_hash({"version": OBSERVATION_RELATION_VERSION, **content})
            groups.append(ObservationRelationContext(pair_id=group_id, **content).model_dump(mode="json"))
        coverage.append({
            "identity_sha256": identity, "group_id": group_id,
            "supplied_fact_ids": sorted({item.fact_id for item in rows}),
            "supplied_pair_ids": [item.pair_id for item in rows],
            "auxiliary_pair_ids": [item.pair_id for item in auxiliary_rows],
            "auxiliary_identity_sha256s": sorted(auxiliary_identities[identity]),
            "clinical_scope_complete": False,
            "reasons": [] if rows else ["no_observation_sources_in_candidate_input"],
        })
    payload = {
        "version": "observation-relation-input/v5", "candidate_job_id": candidate_job_id,
        "review_context_id": context_id, "review_context_sha256": digest,
        "frozen_input_sha256": material["frozen_input_sha256"],
        "comparison_sha256": material["comparison_sha256"],
        "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
        "pairs": sorted(groups, key=lambda item: item["pair_id"]), "identity_coverage": coverage,
    }
    return {**payload, "input_sha256": canonical_hash(payload)}
