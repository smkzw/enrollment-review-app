"""Pure qualification material, receipt proof and structural compose helpers."""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Literal

from app.domain.contracts.binding_qualification import (
    BINDING_QUALIFICATION_PROMPT_VERSION,
    BINDING_QUALIFICATION_SUMMARY_VERSION,
    BindingQualificationBatch,
    BindingQualificationIdentityRecord,
    BindingQualificationLaneDeclaration,
    BindingQualificationLanePayload,
    BindingQualificationPairContext,
    BindingQualificationPairRecord,
    BindingQualificationStructuralCheck,
    BindingQualificationSummary,
    binding_qualification_pair_id,
    binding_qualification_summary_hash,
)
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput, iter_binding_atoms
from app.domain.publication import canonical_hash
from app.llm.binding_qualification import (
    DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
    PROMPT_VERSION,
    build_binding_qualification_messages,
    plan_qualification_batches,
    read_binding_qualification,
    validate_binding_qualification_payload,
)
from app.llm.control_binding_candidates import (
    PROMPT_VERSION as CONTROL_PROMPT_VERSION,
    build_control_binding_messages,
    validate_control_candidates,
)
from app.llm.predicate_binding_batches import PredicateBindingBatch
from app.llm.predicate_binding_candidates import (
    PROMPT_VERSION as PREDICATE_PROMPT_VERSION,
    BATCH_PROMPT_VERSION as PREDICATE_BATCH_PROMPT_VERSION,
    PredicateCandidateReadError,
    build_predicate_binding_messages,
    candidate_value_shape,
    validate_predicate_candidates,
)
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_candidate_comparison import COMPARISON_VERSION, compare_candidate_declarations
from app.services.predicate_binding_job import LANES
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import InvalidJobDefinitionError, StepFailure
from app.workflow.jobstore import JobStore

JOB_TYPE = "binding_qualification"
CONTRACT = "binding-qualification-job/v2"
SEMANTIC_DIMENSIONS = [
    "source_admissibility",
    "object_match",
    "attribute_match",
    "denial_scope",
    "temporal_role",
    "direct_operand_usable",
]

_PREDICATE = {
    "job_type": "predicate_binding_candidates",
    "contract": "predicate-binding-candidate-job/v8",
    "prompt_version": PREDICATE_PROMPT_VERSION,
    "batch_prompt_version": PREDICATE_BATCH_PROMPT_VERSION,
    "family": "predicate",
    "identity_field": "predicate_identity_sha256",
}
_CONTROL = {
    "job_type": "control_binding_candidates",
    "contract": "control-binding-candidate-job/v6",
    "prompt_version": CONTROL_PROMPT_VERSION,
    "batch_prompt_version": None,
    "family": "control",
    "identity_field": "atom_identity_sha256",
}


def _family_spec(job_type: str, contract: str) -> dict[str, Any]:
    for item in (_PREDICATE, _CONTROL):
        if item["job_type"] == job_type and item["contract"] == contract:
            return item
    raise InvalidJobDefinitionError("只能对已完成的官方谓词或控制候选任务做来源资格核对")


def _candidate_reads(payload: dict) -> list[tuple[str, PageReviewLane, PredicateBindingBatch | None]]:
    if payload.get("batches") is None:
        return [(f"read:{lane.value}", lane, None) for lane in LANES]
    return [
        (f"read:{index}:{lane.value}", lane, PredicateBindingBatch.model_validate(batch))
        for index, batch in enumerate(payload["batches"]) for lane in LANES
    ]


def _excerpt_sha(excerpt: str | None) -> str | None:
    return None if excerpt is None else sha256(excerpt.encode("utf-8")).hexdigest()


def _date_precision(fact) -> str | None:
    date_range = getattr(fact, "date_range", None)
    if date_range is None:
        return None
    precision = getattr(date_range, "precision", None)
    return None if precision is None else getattr(precision, "value", precision)


def _policy_unknown(policy: dict) -> bool:
    return (
        policy.get("allows_screening_record_transcription") is None
        or policy.get("requires_contemporaneous_objective_source") is None
        or policy.get("result_validity_status") == "unknown"
        or policy.get("control_validity_status") == "unknown"
    )


def _source_policies_for_predicate(
    component, predicate_id: str,
) -> tuple[str, list[dict], list[str]]:
    policies = []
    source_types: list[str] = []
    for requirement in component.evidence_requirements:
        refs = list(requirement.predicate_ids)
        # Mirror control atom_refs: empty refs remain visible shells; nonempty
        # refs that omit this predicate are unrelated and skipped.
        if refs and predicate_id not in refs:
            continue
        source_types.extend(requirement.required_source_types)
        policy = {
            "requirement_id": requirement.requirement_id,
            "fact_type": requirement.fact_type,
            "required_source_types": list(requirement.required_source_types),
            "allows_screening_record_transcription": (
                requirement.allows_screening_record_transcription
            ),
            "requires_contemporaneous_objective_source": (
                requirement.requires_contemporaneous_objective_source
            ),
            "source_validity_window": (
                None if requirement.source_validity_window is None
                else requirement.source_validity_window.model_dump(mode="json")
            ),
            "control_validity_status": requirement.control_validity_status,
            "control_validity_constraint": (
                None if requirement.control_validity_constraint is None
                else requirement.control_validity_constraint.model_dump(mode="json")
            ),
            "description": requirement.description,
        }
        if refs:
            policy["predicate_ids"] = refs
        policies.append(policy)
    types = sorted(set(source_types))
    if not policies:
        return "missing", [], types
    if any(not item.get("predicate_ids") for item in policies):
        # Absent explicit attribution stays unattributed; never infer singleton/fact_type.
        return "unattributed", policies, types
    # Every retained row explicitly names this predicate; multiple mandatory
    # sources do not erase that attribution or invent an OR between policies.
    return "present", policies, types


def _source_policies_for_control(publication, atom_identity: str) -> tuple[str, list[dict], list[str]]:
    identities = {
        item.identity_sha256: item
        for item in project_control_atom_identities(publication, include_repeat_triggers=True)
    }
    identity = identities.get(atom_identity)
    if identity is None:
        return "missing", [], []
    key = identity.reference.key
    matches = []
    source_types: list[str] = []
    for control in publication.catalog.controls:
        if control.protocol_control_id != identity.protocol_control_id:
            continue
        for evidence in control.minimum_evidence:
            refs = {ref.key for ref in evidence.atom_refs}
            if evidence.atom_refs and key not in refs:
                continue
            source_types.extend(evidence.required_source_types)
            policy_body = (
                None if evidence.source_policy is None
                else evidence.source_policy.model_dump(mode="json")
            )
            matches.append({
                "protocol_control_id": control.protocol_control_id,
                "evidence_key": evidence.evidence_key,
                "fact_type": evidence.fact_type,
                "required_source_types": list(evidence.required_source_types),
                "description": evidence.description,
                "workflow_stage_ids": list(evidence.workflow_stage_ids),
                "atom_refs": [
                    ref.model_dump(mode="json")
                    for ref in evidence.atom_refs
                ],
                "source_policy": policy_body,
            })
    types = sorted(set(source_types))
    if not matches:
        return "missing", [], types
    if any(not item["atom_refs"] for item in matches):
        return "unattributed", matches, types
    if any(item["source_policy"] is None for item in matches):
        # Evidence rows exist but policy object absent: preserve shells, do not drop.
        return "ambiguous", matches, types
    if any(_policy_unknown(item["source_policy"]) for item in matches):
        return "ambiguous", matches, types
    # Each retained row explicitly references this atom; multiple mandatory
    # sources do not erase that attribution or imply an OR between policies.
    return "present", matches, types


def _condition_material(*, family: str, frozen, identity: str) -> dict:
    if family == "predicate":
        for component in frozen.components:
            for item in component.binding_predicates:
                if item.predicate_identity_sha256 == identity:
                    return {
                        "role": item.role,
                        "rule_component_id": item.rule_component_id,
                        "official_code": item.official_code,
                        "predicate_id": item.predicate_id,
                        "predicate": item.predicate.model_dump(mode="json"),
                        "time_constraint": (
                            None if item.time_constraint is None
                            else item.time_constraint.model_dump(mode="json")
                        ),
                        "source_status": item.source_status,
                    }
        raise ValueError("冻结输入中不存在该谓词身份")
    for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True):
        if item.identity_sha256 == identity:
            return {
                "protocol_control_id": item.protocol_control_id,
                "layer": item.layer,
                "group_index": item.group_index,
                "atom_index": item.atom_index,
                "atom_id": item.atom_id,
                "atom": item.atom.model_dump(mode="json"),
                **({"condition_id": item.condition_id} if item.condition_id is not None else {}),
            }
    raise ValueError("冻结输入中不存在该控制原子身份")


def _policies_for_identity(*, family: str, frozen, identity: str):
    if family == "predicate":
        for component in frozen.components:
            for item in component.binding_predicates:
                if item.predicate_identity_sha256 == identity:
                    return _source_policies_for_predicate(component, item.predicate_id)
        raise ValueError("冻结输入中不存在该谓词身份")
    return _source_policies_for_control(frozen.publication, identity)


def _fact_material(fact) -> dict:
    return fact.model_dump(
        mode="json",
        include={
            "fact_id", "fact_type", "asserted_object", "polarity", "value", "unit",
            "source_strength", "date_range", "record_time", "locator_ids", "assertion_basis",
        },
        exclude_none=True,
    )


def _locator_material(locator) -> dict:
    return locator.model_dump(
        mode="json",
        include={
            "locator_id", "source_document_version_id", "page_number", "source_layer",
            "precision", "authenticity", "excerpt", "degradation_reason",
            "source_text_sha256",
        },
        exclude_none=True,
    )


def _episode_material(frozen, family: str) -> dict:
    evidence = frozen if family == "predicate" else frozen.evidence_input
    return evidence.episode.model_dump(
        mode="json",
        include={
            "review_episode_id", "stage", "workflow_stage_id", "anchor_dates",
            "study_phase", "due_at", "revision",
        },
    )


def _parent_source_context(*, family: str, frozen, identity: str) -> dict:
    if family == "predicate":
        for component in frozen.components:
            for item in component.binding_predicates:
                if item.predicate_identity_sha256 == identity:
                    context = {
                        "kind": "official_component",
                        "rule_component_id": component.rule_component_id,
                        "parent_rule_id": component.parent_rule_id,
                        "official_code": component.official_code,
                        "title": component.title,
                        "rule_source_text": component.rule_source_text,
                        "evidence_requirements": [
                            requirement.model_dump(mode="json")
                            for requirement in component.evidence_requirements
                        ],
                    }
                    if item.role == "repeat_trigger":
                        condition = next(
                            condition for condition in component.repeat_trigger_conditions
                            if any(atom.predicate.predicate_id == item.predicate_id
                                   for atom in iter_binding_atoms(condition.expression))
                        )
                        context["repeat_trigger_condition"] = condition.model_dump(mode="json")
                        context["repeat_owner_predicate_ids"] = [
                            owner.predicate_id for owner in (
                                *component.trigger_predicates, *component.exception_predicates,
                            )
                            if owner.predicate.repeat_scheme is not None
                            and condition.condition_id in owner.predicate.repeat_scheme.ancillary_condition_ids
                        ]
                        permission_owners = [
                            owner.predicate_id for owner in (
                                *component.trigger_predicates, *component.exception_predicates,
                            ) if owner.predicate.repeat_scheme is not None
                            and owner.predicate.repeat_scheme.permission_condition_id == condition.condition_id
                        ]
                        if permission_owners:
                            context["repeat_permission_owner_predicate_ids"] = permission_owners
                    return context
        raise ValueError("冻结输入中不存在该谓词身份")
    for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True):
        if item.identity_sha256 == identity:
            control = next(
                control for control in frozen.publication.catalog.controls
                if control.protocol_control_id == item.protocol_control_id
            )
            context = {
                "kind": "control_atom",
                "protocol_control_id": item.protocol_control_id,
                "layer": item.layer,
                "group_index": item.group_index,
                "atom_index": item.atom_index,
                "workflow_stage_map": frozen.publication.workflow_stage_map,
                "minimum_evidence": [
                    evidence.model_dump(mode="json") for evidence in control.minimum_evidence
                ],
                "review_node_bindings": [
                    binding.model_dump(mode="json") for binding in control.review_node_bindings
                ],
            }
            if item.condition_id is not None:
                context["repeat_trigger_condition"] = next(
                    condition.model_dump(mode="json") for condition in control.repeat_trigger_conditions
                    if condition.condition_id == item.condition_id
                )
                context["condition_id"] = item.condition_id
            return context
    raise ValueError("冻结输入中不存在该控制原子身份")


def verify_completed_candidate_comparison(
    session, artifact_store, candidate_job_id: str, *, require_route_receipts: bool = False,
) -> dict:
    """Rebuild comparison from completed read receipts; equality is required."""
    store = JobStore(session)
    job = store.get_job(candidate_job_id)
    if job.state != "completed":
        raise InvalidJobDefinitionError("只能消费已完成的候选对应任务")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    spec = _family_spec(job.job_type, payload.get("contract"))
    if (
        payload.get("purpose") != "isolated_unverified_candidates"
        or payload.get("prompt_version") != spec["prompt_version"]
        or payload.get("batch_prompt_version") != spec["batch_prompt_version"]
    ):
        raise InvalidJobDefinitionError("候选任务合同或提示版本不是当前官方版本")
    summary = store.get_last_checkpoint(candidate_job_id, "summary")
    if summary is None or summary[1].get("accepted") is not False:
        raise InvalidJobDefinitionError("候选任务缺少未采信的汇总检查点")
    stored_comparison = json.loads(
        artifact_store.read_by_sha("raw_response", summary[1]["comparison_sha256"]),
    )
    if (
        stored_comparison.get("version") != COMPARISON_VERSION
        or stored_comparison.get("accepted") is not False
    ):
        raise InvalidJobDefinitionError("候选比较工件版本或采信状态无效")
    family = spec["family"]
    frozen_type = PredicateBindingFrozenInput if family == "predicate" else ControlBindingFrozenInput
    frozen = frozen_type.model_validate(payload["frozen_input"])
    if (
        summary[1].get("frozen_input_sha256") != frozen.frozen_input_sha256
        or stored_comparison.get("frozen_input_sha256") != frozen.frozen_input_sha256
    ):
        raise InvalidJobDefinitionError("候选汇总与冻结输入不一致")
    routes = payload.get("routes") or {}
    if set(routes) != {lane.value for lane in LANES}:
        raise InvalidJobDefinitionError("候选任务缺少完整双路路由身份")
    reads = {}
    for step_id, lane, batch in _candidate_reads(payload):
        checkpoint = store.get_last_checkpoint(candidate_job_id, step_id)
        if checkpoint is None:
            raise InvalidJobDefinitionError("候选任务缺少完整读取检查点")
        record = checkpoint[1]
        batch_hash = None if batch is None else batch.batch_sha256
        if (
            record.get("frozen_input_sha256") != frozen.frozen_input_sha256
            or record.get("batch_sha256") != batch_hash
            or record.get("lane") != lane.value
            or record.get("accepted") is not False
            or record.get("status") != "unverified"
        ):
            raise InvalidJobDefinitionError("候选读取检查点范围或状态无效")
        reads[step_id] = record
    groups = {}
    for step_id, lane, batch in _candidate_reads(payload):
        read = reads[step_id]
        artifact = json.loads(artifact_store.read_by_sha("raw_response", read["candidate_sha256"]))
        batch_hash = None if batch is None else batch.batch_sha256
        if (
            artifact.get("input_sha256") != frozen.frozen_input_sha256
            or artifact.get("batch_sha256") != batch_hash
            or artifact.get("accepted") is not False
        ):
            raise InvalidJobDefinitionError("候选工件范围或采信状态无效")
        raw_payload = json.dumps(artifact["payload"], ensure_ascii=False)
        if family == "predicate":
            validated = validate_predicate_candidates(frozen, raw_payload, batch=batch)
            expected_messages = canonical_hash(build_predicate_binding_messages(frozen, batch=batch))
        else:
            validated = validate_control_candidates(frozen, raw_payload)
            expected_messages = canonical_hash(build_control_binding_messages(frozen))
        receipt_ids = read.get("receipt_sha256s") or []
        if not receipt_ids:
            raise InvalidJobDefinitionError("候选任务缺少原始调用回执")
        receipt = json.loads(artifact_store.read_by_sha("raw_response", receipt_ids[-1]))
        if receipt.get("job_id") != candidate_job_id or receipt.get("step_id") != step_id:
            raise InvalidJobDefinitionError("候选回执不属于当前任务步骤")
        request = json.loads(artifact_store.read_by_sha("raw_response", receipt["request_sha256"]))
        response = json.loads(artifact_store.read_by_sha("raw_response", receipt["response_sha256"]))
        route = routes[lane.value]
        if require_route_receipts:
            budget, request_budget = route.get("max_tokens"), request.get("max_tokens")
            if (receipt.get("route_identity") != route
                    or type(budget) is not int or budget <= 0
                    or type(request_budget) is not int
                    or request_budget not in {budget, min(budget * 2, 131072)}):
                raise InvalidJobDefinitionError("候选读取缺少与本次配置一致的完整调用记录")
        if (
            canonical_hash(request.get("messages")) != expected_messages
            or artifact.get("messages_sha256") != expected_messages
            or request.get("model") != route.get("model")
            or request.get("reasoning_effort") != route.get("reasoning_effort")
            or response.get("finish_reason") != "stop"
        ):
            raise InvalidJobDefinitionError("候选请求/回答与冻结提示或路由不一致")
        if family == "predicate":
            original = validate_predicate_candidates(frozen, response["text"], batch=batch)
        else:
            original = validate_control_candidates(frozen, response["text"])
        if original != validated:
            raise InvalidJobDefinitionError("候选工件与最终原始回答不一致")
        group = groups.setdefault(batch_hash, {})
        if lane in group:
            raise InvalidJobDefinitionError("候选比较存在重复读取")
        group[lane] = (validated, read)
    rebuilt_batches = []
    for batch_hash, group in groups.items():
        if set(group) != set(LANES):
            raise InvalidJobDefinitionError("候选比较缺少完整双路结果")
        rebuilt_batches.append({
            "batch_sha256": batch_hash,
            "sources": {lane.value: group[lane][1] for lane in LANES},
            "results": compare_candidate_declarations(
                group[LANES[0]][0], group[LANES[1]][0],
                identity_field=spec["identity_field"],
            ),
        })
    rebuilt = {
        "version": COMPARISON_VERSION,
        "accepted": False,
        "frozen_input_sha256": frozen.frozen_input_sha256,
        "batches": rebuilt_batches,
    }
    if rebuilt != stored_comparison:
        raise InvalidJobDefinitionError("候选比较工件与回执重建结果不一致")
    if not rebuilt["batches"]:
        raise InvalidJobDefinitionError("候选比较缺少批次覆盖")
    return {
        "family": family,
        "identity_field": spec["identity_field"],
        "candidate_job_id": candidate_job_id,
        "candidate_job_type": job.job_type,
        "candidate_contract": payload["contract"],
        "candidate_prompt_version": payload["prompt_version"],
        "candidate_payload": payload,
        "frozen": frozen,
        "frozen_input_sha256": frozen.frozen_input_sha256,
        "comparison": stored_comparison,
        "comparison_sha256": summary[1]["comparison_sha256"],
        "candidate_summary": summary[1],
        "candidate_routes": routes,
        "reads": reads,
    }


def expected_pair_frozen_bodies(*, family: str, frozen, identity: str, fact, locator, document):
    status, policies, source_types = _policies_for_identity(
        family=family, frozen=frozen, identity=identity,
    )
    return {
        "condition": _condition_material(family=family, frozen=frozen, identity=identity),
        "fact": _fact_material(fact),
        "locator": _locator_material(locator),
        "document": (
            None if document is None else document.model_dump(
                mode="json",
                include={"source_document_version_id", "file_name", "media_type"},
            )
        ),
        "episode": _episode_material(frozen, family),
        "parent_source_context": _parent_source_context(
            family=family, frozen=frozen, identity=identity,
        ),
        "source_policies": policies,
        "source_policy_status": status,
        "required_source_types": source_types,
    }


def validate_binding_qualification_structure(
    pair: BindingQualificationPairContext,
    *,
    frozen,
    family: Literal["predicate", "control"],
) -> BindingQualificationStructuralCheck:
    """Compare pair body with frozen material; keep shape separate from semantic review."""
    reasons: list[str] = []
    pending: list[str] = []
    evidence = frozen if family == "predicate" else frozen.evidence_input
    facts = {item.fact_id: item for item in evidence.facts}
    locators = {item.locator_id: item for item in evidence.locators}
    documents = {
        item.source_document_version_id: item
        for item in (evidence.documents or [])
    }
    fact = facts.get(pair.fact_id)
    locator = locators.get(pair.locator_id)
    if fact is None:
        reasons.append("fact_not_in_frozen_input")
    elif pair.locator_id not in fact.locator_ids:
        reasons.append("locator_not_bound_to_fact")
    if locator is None:
        reasons.append("locator_not_in_frozen_input")
    if fact is not None and getattr(fact, pair.fact_attribute, None) is None:
        reasons.append("fact_attribute_missing")
    excerpt = None if locator is None else locator.excerpt
    if locator is not None and not (excerpt or "").strip():
        reasons.append("locator_excerpt_missing")
    document = None if locator is None else documents.get(locator.source_document_version_id)
    body_matches = False
    operand_shape = None
    referenced_value = None
    referenced_unit = None
    if fact is not None and locator is not None and not reasons:
        expected = expected_pair_frozen_bodies(
            family=family, frozen=frozen, identity=pair.identity_sha256,
            fact=fact, locator=locator, document=document,
        )
        actual = {
            "condition": pair.condition,
            "fact": pair.fact,
            "locator": pair.locator,
            "document": pair.document,
            "episode": pair.episode,
            "parent_source_context": pair.parent_source_context,
            "source_policies": pair.source_policies,
            "source_policy_status": pair.source_policy_status,
            "required_source_types": pair.required_source_types,
        }
        body_matches = actual == expected
        if not body_matches:
            reasons.append("pair_body_diverges_from_frozen_material")
        if family == "predicate":
            predicates = {
                item.predicate_identity_sha256: item.predicate
                for component in frozen.components
                for item in component.binding_predicates
            }
            predicate = predicates.get(pair.identity_sha256)
            if predicate is None:
                reasons.append("predicate_identity_missing")
            else:
                shape = candidate_value_shape(
                    predicate, fact, pair.fact_attribute,
                )
                operand_shape = shape["operand_shape"]
                if (pair.fact_attribute == "date_range"
                        and expected["condition"].get("time_constraint") is not None):
                    operand_shape = "event_date_for_time_constraint"
                pending.extend(shape["pending_checks"])
        else:
            atoms = {
                item.identity_sha256: item.atom
                for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
            }
            atom = atoms.get(pair.identity_sha256)
            if atom is None:
                reasons.append("control_atom_identity_missing")
            else:
                spec = getattr(atom, "evaluation", None)
                if (spec is not None and spec.determination_mode in {"semantic", "investigator_judgment"}
                        and pair.fact_attribute in {"value", "assertion_basis"}
                        and spec.operand_attribute in {None, pair.fact_attribute}):
                    operand_shape = "bound_assertion_for_proposition"
                    if fact.assertion_basis is None or fact.assertion_basis.locator_id != pair.locator_id:
                        reasons.append("assertion_source_not_bound")
                elif spec is not None and spec.operand_attribute == pair.fact_attribute:
                    operand_shape = "declared_operand_attribute"
                elif spec is not None and spec.time_operand_attribute == pair.fact_attribute:
                    operand_shape = "declared_time_operand_attribute"
                elif spec is not None:
                    operand_shape = "declared_operand_attribute_mismatch"
                else:
                    operand_shape = "evaluation_spec_missing"
                if spec is not None and spec.time_purpose == "source_validity":
                    pending.append("source_validity_requires_policy_evaluation")
                if spec is not None and spec.predicate is not None:
                    pending.extend(candidate_value_shape(spec.predicate, fact, pair.fact_attribute)["pending_checks"])
        if pair.fact_attribute == "value":
            referenced_value = fact.value
            referenced_unit = fact.unit
        elif pair.fact_attribute == "assertion_basis" and fact.assertion_basis is not None:
            referenced_value = fact.assertion_basis.assertion_text
        if fact.source_strength.value == "unverifiable_source":
            reasons.append("source_strength_unverifiable")
    return BindingQualificationStructuralCheck(
        pair_id=pair.pair_id,
        structurally_valid=not reasons,
        reasons=sorted(set(reasons)),
        pending_checks=sorted(set(pending)),
        source_policy_status=pair.source_policy_status,
        referenced_value=referenced_value,
        referenced_unit=referenced_unit,
        referenced_date_precision=_date_precision(fact) if fact is not None else None,
        referenced_record_time=(
            None if fact is None or fact.record_time is None else fact.record_time.isoformat()
        ),
        locator_excerpt_sha256=_excerpt_sha(excerpt),
        source_strength=None if fact is None else fact.source_strength.value,
        operand_shape=operand_shape,
        body_matches_frozen=body_matches and not reasons,
    )


def build_qualification_pairs_from_verified(verified: dict) -> dict[str, Any]:
    family = verified["family"]
    frozen = verified["frozen"]
    identity_field = verified["identity_field"]
    evidence = frozen if family == "predicate" else frozen.evidence_input
    documents = {
        item.source_document_version_id: item
        for item in (evidence.documents or [])
    }
    facts = {item.fact_id: item for item in evidence.facts}
    locators = {item.locator_id: item for item in evidence.locators}
    pairs = []
    identity_records = []
    candidate_receipts = {lane.value: [] for lane in LANES}
    for batch in verified["comparison"]["batches"]:
        batch_hash = batch.get("batch_sha256")
        sources = batch.get("sources") or {}
        for lane in LANES:
            source = sources.get(lane.value)
            if not source or not source.get("receipt_sha256s"):
                raise InvalidJobDefinitionError("候选比较缺少完整双路回执")
            candidate_receipts[lane.value] = list(dict.fromkeys(
                candidate_receipts[lane.value] + list(source["receipt_sha256s"])
            ))
        for result in batch.get("results") or []:
            identity = result[identity_field]
            comparisons = result.get("comparisons") or []
            pair_ids = []
            for item in comparisons:
                fact = facts[item["fact_id"]]
                locator = locators[item["locator_id"]]
                document = documents.get(locator.source_document_version_id)
                bodies = expected_pair_frozen_bodies(
                    family=family, frozen=frozen, identity=identity,
                    fact=fact, locator=locator, document=document,
                )
                declarations = {}
                for lane in LANES:
                    declared = item.get(lane.value)
                    declarations[lane.value] = BindingQualificationLaneDeclaration(
                        proposed=declared is not None,
                        object_correspondence=(
                            None if declared is None else declared["object_correspondence"]
                        ),
                        attribute_correspondence=(
                            None if declared is None else declared["attribute_correspondence"]
                        ),
                    )
                pair_id = binding_qualification_pair_id(
                    candidate_job_id=verified["candidate_job_id"],
                    frozen_input_sha256=verified["frozen_input_sha256"],
                    identity_field=identity_field,
                    identity_sha256=identity,
                    fact_id=item["fact_id"],
                    fact_attribute=item["fact_attribute"],
                    locator_id=item["locator_id"],
                    candidate_batch_sha256=batch_hash,
                )
                pair_ids.append(pair_id)
                pairs.append(BindingQualificationPairContext(
                    pair_id=pair_id,
                    identity_field=identity_field,
                    identity_sha256=identity,
                    candidate_family=family,
                    candidate_job_id=verified["candidate_job_id"],
                    candidate_job_type=verified["candidate_job_type"],
                    candidate_contract=verified["candidate_contract"],
                    frozen_input_sha256=verified["frozen_input_sha256"],
                    candidate_batch_sha256=batch_hash,
                    comparison_sha256=verified["comparison_sha256"],
                    fact_id=item["fact_id"],
                    fact_attribute=item["fact_attribute"],
                    locator_id=item["locator_id"],
                    lane_declarations=declarations,
                    candidate_receipt_sha256s={
                        lane.value: list(sources[lane.value]["receipt_sha256s"])
                        for lane in LANES
                    },
                    **bodies,
                ))
            identity_records.append(BindingQualificationIdentityRecord(
                identity_field=identity_field,
                identity_sha256=identity,
                candidate_batch_sha256=batch_hash,
                status=(
                    "candidates_present" if pair_ids else "no_candidates_in_supplied_input"
                ),
                unresolved_reasons=(
                    [] if pair_ids else ["no_candidate_pairs_in_completed_job"]
                ),
                pair_ids=pair_ids,
            ))
    # Owner-facing per-fact accounting carried from the verified comparison.
    # Exclusion/uncertainty rows never become pairs; this only exposes what
    # each lane considered, for the later selection scope proof.
    candidate_fact_accounting = [
        {
            identity_field: result[identity_field],
            "candidate_batch_sha256": batch.get("batch_sha256"),
            "fact_accounting": result.get("fact_accounting") or [],
        }
        for batch in verified["comparison"]["batches"]
        for result in batch.get("results") or []
    ]
    return {
        **{key: verified[key] for key in (
            "family", "identity_field", "candidate_job_id", "candidate_job_type",
            "candidate_contract", "candidate_prompt_version", "frozen_input_sha256",
            "comparison_sha256", "candidate_summary",
        )},
        "frozen_input": verified["frozen"].model_dump(mode="json"),
        "candidate_method": {
            "candidate_job_type": verified["candidate_job_type"],
            "candidate_contract": verified["candidate_contract"],
            "candidate_prompt_version": verified["candidate_prompt_version"],
            "candidate_batch_prompt_version": verified["candidate_payload"].get("batch_prompt_version"),
            "candidate_routes": verified["candidate_routes"],
        },
        "candidate_receipt_sha256s": candidate_receipts,
        "pairs": [item.model_dump(mode="json") for item in pairs],
        "identity_records": [item.model_dump(mode="json") for item in identity_records],
        "candidate_fact_accounting": candidate_fact_accounting,
    }


def load_completed_candidate_qualification_input(
    session, artifact_store, candidate_job_id: str, *, require_route_receipts: bool = False,
) -> dict[str, Any]:
    verified = verify_completed_candidate_comparison(
        session, artifact_store, candidate_job_id, require_route_receipts=require_route_receipts,
    )
    from app.services.review_candidate_scope import verify_candidate_preparation
    verify_candidate_preparation(session, verified["candidate_payload"], verified["frozen"])
    material = build_qualification_pairs_from_verified(verified)
    for key in ("review_context_id", "review_context_sha256"):
        if key in verified["candidate_payload"]:
            material[key] = verified["candidate_payload"][key]
    return material

def _merge_unique(*groups: list[str]) -> list[str]:
    return sorted({item for group in groups for item in group if item and item.strip()})


def compose_qualification_summary(
    *,
    payload: dict,
    frozen,
    pairs: list[BindingQualificationPairContext],
    batches: list[BindingQualificationBatch],
    lane_payloads: dict[str, dict[str, BindingQualificationLanePayload | None]],
    lane_receipts: dict[str, dict[str, list[str]]],
) -> BindingQualificationSummary:
    family = payload["candidate_family"]
    pair_records = []
    for pair in pairs:
        structural = validate_binding_qualification_structure(
            pair, frozen=frozen, family=family,
        )
        batch_sha = next(
            (batch.batch_sha256 for batch in batches if pair.pair_id in batch.pair_ids),
            None,
        )
        judgments = {}
        lane_reasons = {}
        for lane in (item.value for item in LANES):
            payload_for_batch = None if batch_sha is None else (
                None if lane_payloads.get(batch_sha) is None
                else lane_payloads[batch_sha].get(lane)
            )
            judgment = None if payload_for_batch is None else next(
                item for item in payload_for_batch.results if item.pair_id == pair.pair_id
            )
            judgments[lane] = judgment
            lane_reasons[lane] = [] if judgment is None else list(judgment.unresolved_reasons)
        present = [item for item in judgments.values() if item is not None]
        dual = (
            len(present) == 2
            and present[0].public_agreement_key() == present[1].public_agreement_key()
        )
        remaining = ["clinical_adoption_not_authorized", "evaluation_activation_absent",
                     *structural.pending_checks]
        if pair.source_policy_status != "present":
            remaining.append(f"source_policy_{pair.source_policy_status}")
        if pair.fact_attribute == "record_time":
            remaining.append("record_time_is_not_clinical_event_date")
        if structural.operand_shape in {
            "time_operand_needs_derivation",
            "declared_operand_attribute_mismatch",
            "evaluation_spec_missing",
        }:
            remaining.append(f"operand_shape_{structural.operand_shape}")
        if not dual:
            remaining.append("dual_lane_disagreement_or_incomplete")
        if not structural.structurally_valid:
            remaining.append("structurally_invalid")
        unresolved = _merge_unique(
            structural.reasons,
            *[lane_reasons[lane] for lane in lane_reasons],
            remaining,
        )
        pair_records.append(BindingQualificationPairRecord(
            pair_id=pair.pair_id,
            identity_field=pair.identity_field,
            identity_sha256=pair.identity_sha256,
            candidate_family=family,
            candidate_job_id=payload["candidate_job_id"],
            frozen_input_sha256=payload["frozen_input_sha256"],
            comparison_sha256=payload["comparison_sha256"],
            qualification_batch_sha256=batch_sha,
            candidate_batch_sha256=pair.candidate_batch_sha256,
            fact_id=pair.fact_id,
            fact_attribute=pair.fact_attribute,
            locator_id=pair.locator_id,
            structural=structural,
            lane_judgments=judgments,
            lane_receipt_sha256s={
                lane: list((lane_receipts.get(batch_sha) or {}).get(lane) or [])
                for lane in (item.value for item in LANES)
            },
            lane_unresolved_reasons=lane_reasons,
            structurally_valid=structural.structurally_valid,
            dual_agreement=dual,
            semantic_dimensions_rechecked=list(SEMANTIC_DIMENSIONS) if len(present) == 2 else [],
            remaining_unverified=sorted(set(remaining)),
            unresolved_reasons=unresolved,
        ))
    material = {
        "version": BINDING_QUALIFICATION_SUMMARY_VERSION,
        "prompt_version": BINDING_QUALIFICATION_PROMPT_VERSION,
        "candidate_family": family,
        "candidate_job_id": payload["candidate_job_id"],
        "candidate_job_type": payload["candidate_job_type"],
        "candidate_contract": payload["candidate_contract"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "batches": [item.model_dump(mode="json") for item in batches],
        "pair_records": [item.model_dump(mode="json") for item in pair_records],
        "identity_records": payload.get("identity_records") or [],
        "accepted": False,
        "authorized_clinical_adoption": False,
        "clinically_qualified": False,
    }
    material["summary_sha256"] = binding_qualification_summary_hash(material)
    return BindingQualificationSummary.model_validate(material)

def _qualification_frozen(payload: dict):
    if payload["candidate_family"] == "predicate":
        return PredicateBindingFrozenInput.model_validate(payload["frozen_input"])
    return ControlBindingFrozenInput.model_validate(payload["frozen_input"])


def _reconstruct_qualification_lane_state(
    *,
    session,
    artifact_store,
    job_id: str,
    payload: dict,
    pairs: list[BindingQualificationPairContext],
    batches: list[BindingQualificationBatch],
    routes: dict[str, dict],
    require_route_receipts: bool = False,
) -> tuple[
    dict[str, dict[str, BindingQualificationLanePayload | None]],
    dict[str, dict[str, list[str]]],
]:
    """Rebuild qualify-step payloads from stored request/response receipts."""
    store = JobStore(session)
    lane_payloads = {batch.batch_sha256: {lane.value: None for lane in LANES} for batch in batches}
    lane_receipts = {batch.batch_sha256: {lane.value: [] for lane in LANES} for batch in batches}
    if not pairs:
        return lane_payloads, lane_receipts
    for index, batch in enumerate(batches):
        batch_pairs = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        for lane in LANES:
            step_id = f"qualify:{index}:{lane.value}"
            checkpoint = store.get_last_checkpoint(job_id, step_id)
            if checkpoint is None:
                raise InvalidJobDefinitionError("资格任务缺少完整双路核对检查点")
            record = checkpoint[1]
            if (
                record.get("frozen_input_sha256") != payload["frozen_input_sha256"]
                or record.get("batch_sha256") != batch.batch_sha256
                or record.get("lane") != lane.value
                or record.get("accepted") is not False
                or record.get("status") != "unverified"
            ):
                raise InvalidJobDefinitionError("资格读取检查点范围或状态无效")
            artifact = json.loads(
                artifact_store.read_by_sha("raw_response", record["qualification_sha256"]),
            )
            if artifact.get("accepted") is not False:
                raise InvalidJobDefinitionError("资格工件不得声明已采信")
            if (
                artifact.get("input_sha256") != payload["frozen_input_sha256"]
                or artifact.get("candidate_job_id") != payload["candidate_job_id"]
                or artifact.get("comparison_sha256") != payload["comparison_sha256"]
                or artifact.get("authorized_clinical_adoption") is not False
                or artifact.get("clinically_qualified") is not False
            ):
                raise InvalidJobDefinitionError("资格工件范围或采信状态无效")
            validated = validate_binding_qualification_payload(
                batch_pairs,
                json.dumps(artifact["payload"], ensure_ascii=False),
                batch=batch,
            )
            receipt_ids = record.get("receipt_sha256s") or []
            if not receipt_ids:
                raise InvalidJobDefinitionError("资格任务缺少原始调用回执")
            receipt = json.loads(artifact_store.read_by_sha("raw_response", receipt_ids[-1]))
            if receipt.get("job_id") != job_id or receipt.get("step_id") != step_id:
                raise InvalidJobDefinitionError("资格回执不属于当前任务步骤")
            request = json.loads(artifact_store.read_by_sha("raw_response", receipt["request_sha256"]))
            response = json.loads(artifact_store.read_by_sha("raw_response", receipt["response_sha256"]))
            expected_messages = canonical_hash(
                build_binding_qualification_messages(batch_pairs, batch),
            )
            route = routes[lane.value]
            budget = route.get("max_tokens")
            request_budget = request.get("max_tokens")
            if require_route_receipts and (
                receipt.get("route_identity") != route
                or type(budget) is not int or budget <= 0
                or type(request_budget) is not int
                or request_budget not in {
                    budget, min(131072, 2 * budget),
                }
            ):
                raise InvalidJobDefinitionError("资格回执未保留对应服务和实际请求额度，不能采用历史核对结果")
            if (
                canonical_hash(request.get("messages")) != expected_messages
                or artifact.get("messages_sha256") != expected_messages
                or artifact.get("batch_sha256") != batch.batch_sha256
                or request.get("model") != route.get("model")
                or request.get("reasoning_effort") != route.get("reasoning_effort")
                or response.get("finish_reason") != "stop"
            ):
                raise InvalidJobDefinitionError("资格请求/回答与冻结提示或路由不一致")
            original = validate_binding_qualification_payload(
                batch_pairs, response["text"], batch=batch,
            )
            if original != validated:
                raise InvalidJobDefinitionError("资格工件与最终原始回答不一致")
            lane_payloads[batch.batch_sha256][lane.value] = validated
            lane_receipts[batch.batch_sha256][lane.value] = list(receipt_ids)
    return lane_payloads, lane_receipts


def verify_completed_binding_qualification(
    session, artifact_store, qualification_job_id: str, *, require_candidate_route_receipts: bool = False,
) -> dict[str, Any]:
    """Rebuild a completed qualification from frozen source + two-lane receipts.

    Caller-supplied summary hashes alone are never trusted. Clinical adoption
    flags remain false; this proof only reconstructs the unauthorized record.
    """
    store = JobStore(session)
    job = store.get_job(qualification_job_id)
    if job.state != "completed":
        raise InvalidJobDefinitionError("只能消费已完成的来源资格核对任务")
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    if (
        job.job_type != JOB_TYPE
        or payload.get("contract") != CONTRACT
        or payload.get("prompt_version") != PROMPT_VERSION
        or payload.get("purpose") != "isolated_source_qualification"
    ):
        raise InvalidJobDefinitionError("资格任务合同或提示版本不是当前官方版本")
    routes = payload.get("routes") or {}
    if set(routes) != {lane.value for lane in LANES}:
        raise InvalidJobDefinitionError("资格任务缺少完整双路路由身份")
    rebuilt_material = load_completed_candidate_qualification_input(
        session, artifact_store, payload["candidate_job_id"],
        require_route_receipts=require_candidate_route_receipts,
    )
    expected = {
        "candidate_job_type": payload["candidate_job_type"],
        "candidate_contract": payload["candidate_contract"],
        "family": payload["candidate_family"],
        "identity_field": payload["identity_field"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "pairs": payload["pairs"],
        "identity_records": payload["identity_records"],
        "candidate_receipt_sha256s": payload["candidate_receipt_sha256s"],
    }
    actual = {key: rebuilt_material[key] for key in expected}
    for key in ("review_context_id", "review_context_sha256"):
        if key in rebuilt_material or key in payload:
            expected[key] = payload.get(key)
            actual[key] = rebuilt_material.get(key)
    if actual != expected:
        raise InvalidJobDefinitionError("资格配对或政策材料与来源候选任务重建结果不一致")
    if rebuilt_material["frozen_input"] != payload["frozen_input"]:
        raise InvalidJobDefinitionError("资格冻结输入与来源候选任务重建结果不一致")
    frozen = _qualification_frozen(payload)
    pairs = [BindingQualificationPairContext.model_validate(item) for item in payload.get("pairs") or []]
    expected_batches = [
        batch.model_dump(mode="json")
        for batch in plan_qualification_batches(
            pairs,
            max_characters=payload.get(
                "pair_batch_max_characters", DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
            ),
        )
    ]
    if payload.get("batches") != expected_batches:
        raise InvalidJobDefinitionError("资格分批与配对材料不一致")
    batches = [BindingQualificationBatch.model_validate(item) for item in expected_batches]
    summary_checkpoint = store.get_last_checkpoint(qualification_job_id, "summary")
    if summary_checkpoint is None or summary_checkpoint[1].get("accepted") is not False:
        raise InvalidJobDefinitionError("资格任务缺少未采信的汇总检查点")
    summary_record = summary_checkpoint[1]
    if (
        summary_record.get("frozen_input_sha256") != payload["frozen_input_sha256"]
        or summary_record.get("comparison_sha256") != payload["comparison_sha256"]
        or summary_record.get("candidate_job_id") != payload["candidate_job_id"]
        or summary_record.get("authorized_clinical_adoption") is not False
        or summary_record.get("clinically_qualified") is not False
        or summary_record.get("status") != "unverified"
    ):
        raise InvalidJobDefinitionError("资格汇总检查点范围或状态无效")
    stored_summary = json.loads(
        artifact_store.read_by_sha("raw_response", summary_record["summary_sha256"]),
    )
    if (
        stored_summary.get("version") != BINDING_QUALIFICATION_SUMMARY_VERSION
        or stored_summary.get("accepted") is not False
        or stored_summary.get("authorized_clinical_adoption") is not False
        or stored_summary.get("clinically_qualified") is not False
    ):
        raise InvalidJobDefinitionError("资格汇总工件版本或采信状态无效")
    lane_payloads, lane_receipts = _reconstruct_qualification_lane_state(
        session=session,
        artifact_store=artifact_store,
        job_id=qualification_job_id,
        payload=payload,
        pairs=pairs,
        batches=batches,
        routes=routes,
        require_route_receipts=True,
    )
    rebuilt_summary = compose_qualification_summary(
        payload=payload,
        frozen=frozen,
        pairs=pairs,
        batches=batches,
        lane_payloads=lane_payloads,
        lane_receipts=lane_receipts,
    )
    rebuilt_dump = rebuilt_summary.model_dump(mode="json")
    if rebuilt_dump != stored_summary:
        raise InvalidJobDefinitionError("资格汇总工件与回执重建结果不一致")
    # The checkpoint points to the artifact bytes, not the self-excluding
    # semantic hash embedded in that artifact. read_by_sha verified the former.
    return {
        "qualification_job_id": qualification_job_id,
        "candidate_method": rebuilt_material["candidate_method"],
        # Reconstructed from the candidate response receipts, not copied from
        # a caller-supplied qualification payload or treated as qualification.
        "candidate_fact_accounting": rebuilt_material["candidate_fact_accounting"],
        "job_type": JOB_TYPE,
        "contract": CONTRACT,
        "prompt_version": PROMPT_VERSION,
        "payload": payload,
        "routes": routes,
        "frozen": frozen,
        "pairs": pairs,
        "batches": batches,
        "summary": rebuilt_summary,
        "summary_sha256": rebuilt_dump["summary_sha256"],
        "summary_artifact_sha256": summary_record["summary_sha256"],
        "candidate_family": payload["candidate_family"],
        "identity_field": payload["identity_field"],
        "frozen_input_sha256": payload["frozen_input_sha256"],
        "comparison_sha256": payload["comparison_sha256"],
        "lane_payloads": lane_payloads,
        "lane_receipts": lane_receipts,
    }
