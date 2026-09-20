"""Receipt-verified consumer from binding qualification to frozen-review selections.

Does not enable adoption, register an API, or invent authorization. Owning services
must supply an explicit version-bound QualificationAdoptionAuthorization that matches
the reconstructed job, routes, summary and approved evaluation evidence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.contracts.binding_qualification import BindingQualificationPairRecord
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.contracts.qualified_binding_selection import (
    QUALIFIED_BINDING_CONSUMER_ALGORITHM,
    QUALIFIED_BINDING_SELECTION_VERSION,
    QualificationAdoptionAuthorization,
    QualifiedBindingIdentityOutcome,
    QualifiedBindingRejectedPair,
    QualifiedBindingSelectionMaterial,
    qualified_binding_selection_hash,
)
from app.domain.publication import canonical_hash
from app.domain.contracts.enums import GateOutcome
from app.storage.repositories import AppendRepository, GATE_RESULT_CONFIG, NotFoundError
from app.services.predicate_binding_input import _frozen_fact, _frozen_component
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import (
    CONTRACT,
    JOB_TYPE,
    SEMANTIC_DIMENSIONS,
    verify_completed_binding_qualification,
)
from app.workflow.errors import InvalidJobDefinitionError
from app.services.review_method_evidence import read_binding_evaluation, require_evaluated_binding_method

_SEAL = object()

# Always present on unauthorized qualification records. Authorization unlocks
# evaluation activation for formal calculation input only; clinical adoption stays
# unauthorized on both the qualification and selection materials.
_AUTHORIZATION_WAIVED_REASONS = frozenset({
    "evaluation_activation_absent",
    "clinical_adoption_not_authorized",
})


def _sorted_unique(values: Sequence[str]) -> list[str]:
    return sorted({item for item in values if item and str(item).strip()})


def source_validity_operand_calculable(record, spec):
    if spec is None:
        return False
    return (record.fact_attribute in {spec.operand_attribute, spec.time_operand_attribute}
            or spec.determination_mode != "deterministic" and spec.operand_attribute is None
            and record.fact_attribute in {"value", "assertion_basis"})


def pair_direct_selection_rejection_reasons(
    record: BindingQualificationPairRecord,
    *, written_content_verified: bool = False, source_validity_calculable: bool = False,
) -> list[str]:
    """Reject dual-rejected/unresolved agreement and unsupported semantics."""
    reasons: list[str] = []
    judgments = [item for item in record.lane_judgments.values() if item is not None]
    resolved_checks = set()
    if (record.structurally_valid and record.structural.source_policy_status == "present"
            and len(judgments) == 2 and record.dual_agreement
            and judgments[0].public_agreement_key() == judgments[1].public_agreement_key()
            and set(record.semantic_dimensions_rechecked) == set(SEMANTIC_DIMENSIONS)):
        checked = judgments[0]
        if (checked.source_admissibility == "admissible" and checked.object_match == "supported"
                and checked.attribute_match == "direct" and checked.denial_scope == "compatible"
                and checked.direct_operand_usable == "usable"
                and checked.temporal_role == (
                    "event_date" if record.fact_attribute == "date_range" else "not_applicable")):
            # Correspondence is checked here. Temporal applicability is deferred to
            # identity selection (qualified event date) and the window evaluator;
            # not_applicable on a value field is not evidence of window membership.
            resolved_checks = {"semantic_correspondence_unverified", "temporal_applicability_unverified"}
            if written_content_verified:
                resolved_checks.add("professional_judgment_applicability_unverified")
            if source_validity_calculable:
                resolved_checks.add("source_validity_requires_policy_evaluation")
    for judgment in record.lane_judgments.values():
        if judgment is not None:
            reasons.extend(judgment.unresolved_reasons)
    if not record.structurally_valid:
        reasons.extend(record.structural.reasons or ["structurally_invalid"])
    for check in record.structural.pending_checks:
        if check not in resolved_checks:
            reasons.append(f"pending:{check}")
    if record.structural.source_policy_status != "present":
        reasons.append(f"source_policy_{record.structural.source_policy_status}")
    if record.fact_attribute == "record_time":
        reasons.append("record_time_is_not_clinical_event_date")
    if record.structural.operand_shape in {
        "time_operand_needs_derivation",
        "declared_operand_attribute_mismatch",
        "evaluation_spec_missing",
    }:
        reasons.append(f"operand_shape_{record.structural.operand_shape}")
    if len(judgments) != 2:
        reasons.append("dual_lane_incomplete")
    elif not record.dual_agreement:
        reasons.append("dual_lane_disagreement_or_incomplete")
    else:
        judgment = judgments[0]
        if set(record.semantic_dimensions_rechecked) != set(SEMANTIC_DIMENSIONS):
            reasons.append("semantic_dimensions_incomplete")
        if judgment.source_admissibility != "admissible":
            reasons.append(f"source_admissibility_{judgment.source_admissibility}")
        if judgment.object_match != "supported":
            reasons.append(f"object_match_{judgment.object_match}")
        if judgment.attribute_match != "direct":
            # derivation_operand / context_only / uncertain / rejected stay unresolved
            reasons.append(f"attribute_match_{judgment.attribute_match}")
        if judgment.denial_scope != "compatible":
            reasons.append(f"denial_scope_{judgment.denial_scope}")
        if record.fact_attribute == "date_range":
            if judgment.temporal_role != "event_date":
                reasons.append(f"temporal_role_{judgment.temporal_role}")
        elif judgment.temporal_role != "not_applicable":
            reasons.append(f"temporal_role_{judgment.temporal_role}")
        if judgment.direct_operand_usable != "usable":
            reasons.append(f"direct_operand_{judgment.direct_operand_usable}")
    for item in record.remaining_unverified:
        if item not in _AUTHORIZATION_WAIVED_REASONS and item not in resolved_checks:
            reasons.append(item)
    return _sorted_unique(reasons)


def _validate_authorization(
    session,
    authorization: QualificationAdoptionAuthorization,
    verified: dict[str, Any],
) -> None:
    try:
        gate = AppendRepository(session, GATE_RESULT_CONFIG).get(authorization.authorization_id)
    except NotFoundError as exc:
        raise InvalidJobDefinitionError("尚未保存该核对方法的采用授权") from exc
    if (gate.gate_name != "binding-adoption-authorization"
            or gate.result != GateOutcome.ACCEPTED
            or gate.output_hash != canonical_hash(authorization.model_dump(mode="json"))
            or authorization.approved_evaluation_evidence_sha256 not in gate.input_entity_refs
            or authorization.qualification_job_id not in gate.accepted_entity_refs):
        raise InvalidJobDefinitionError("缺少与本次资料和评测依据一致的已保存授权，不采用核对结果")
    summary = verified["summary"]
    payload = verified["payload"]
    if authorization.judgment_content is not None and any(
        ref not in gate.input_entity_refs for ref in (
            authorization.judgment_content.job_id, authorization.judgment_content.evaluation_sha256,
        )
    ):
        raise InvalidJobDefinitionError("授权缺少本次书面判断核实依据")
    if authorization.proposition_evidence is not None and any(
        ref not in gate.input_entity_refs for ref in (
            authorization.proposition_evidence.job_id, authorization.proposition_evidence.evaluation_sha256,
        )
    ):
        raise InvalidJobDefinitionError("授权缺少本次原文含义核实依据")
    if authorization.observation_relation is not None and any(
        ref not in gate.input_entity_refs for ref in (
            authorization.observation_relation.job_id, authorization.observation_relation.evaluation_sha256,
        )
    ):
        raise InvalidJobDefinitionError("授权缺少本次复查对应核实依据")
    if authorization.frequency_evidence is not None and any(
        ref not in gate.input_entity_refs for ref in (
            authorization.frequency_evidence.job_id, authorization.frequency_evidence.evaluation_sha256,
        )
    ):
        raise InvalidJobDefinitionError("授权缺少本次频次原文核实依据")
    if authorization.consumer_algorithm_version != QUALIFIED_BINDING_CONSUMER_ALGORITHM:
        raise InvalidJobDefinitionError("采信授权的消费算法版本不受支持")
    if (
        authorization.qualification_job_id != verified["qualification_job_id"]
        or authorization.qualification_job_type != JOB_TYPE
        or authorization.qualification_contract != CONTRACT
        or authorization.qualification_prompt_version != verified["prompt_version"]
        or authorization.qualification_summary_version != summary.version
        or authorization.candidate_family != verified["candidate_family"]
        or authorization.frozen_input_sha256 != verified["frozen_input_sha256"]
        or authorization.comparison_sha256 != verified["comparison_sha256"]
        or authorization.summary_logical_sha256 != verified["summary_sha256"]
        or authorization.summary_artifact_sha256 != verified["summary_artifact_sha256"]
        or authorization.route_identities != verified["routes"]
    ):
        raise InvalidJobDefinitionError("采信授权与回执重建的资格任务身份不一致")
    if payload.get("routes") != authorization.route_identities:
        raise InvalidJobDefinitionError("采信授权路由与任务载荷不一致")


def _expected_predicate_identities(frozen: PredicateBindingFrozenInput) -> dict[str, dict]:
    expected = {}
    for component in frozen.components:
        local_ids = [item.predicate_id for item in component.binding_predicates]
        if len(local_ids) != len(set(local_ids)):
            raise InvalidJobDefinitionError("同一组件的条件编号重复，不能归并核对结果")
        for item in component.binding_predicates:
            identity = item.predicate_identity_sha256
            if identity in expected:
                raise InvalidJobDefinitionError("冻结输入中存在重复的谓词身份")
            expected[identity] = {
                "role": item.role,
                "rule_component_id": component.rule_component_id,
                "predicate_id": item.predicate_id,
                "predicate": item.predicate,
                "time_constraint": item.time_constraint,
            }
    return expected


def _expected_control_identities(frozen: ControlBindingFrozenInput) -> dict[str, Any]:
    return {
        item.identity_sha256: item
        for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)
    }


def _select_facts_for_identity(
    *,
    family: str,
    identity: str,
    usable_records: list[BindingQualificationPairRecord],
    expected_meta,
    written_content_verified: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Return fact_ids, usable_pair_ids, unresolved_reasons."""
    if family == "predicate":
        predicate = expected_meta["predicate"]
        policy = predicate.observation_policy
        if policy is not None and policy.mode == "unresolved":
            return [], [], ["observation_selection_unverified"]
        if getattr(predicate, "requires_professional_judgment", False) and not written_content_verified:
            return [], [], ["investigator_judgment_not_deterministic_value"]
        value_records = [item for item in usable_records if item.fact_attribute == "value"]
        fact_ids = _sorted_unique(item.fact_id for item in value_records)
        pair_ids = _sorted_unique(item.pair_id for item in value_records)
        if not fact_ids:
            return [], [], ["no_usable_qualified_pair"]
        if expected_meta.get("time_constraint") is not None:
            date_records = [item for item in usable_records if item.fact_attribute == "date_range"]
            qualified_dates = {item.fact_id for item in date_records}
            if any(fact_id not in qualified_dates for fact_id in fact_ids):
                return [], [], ["event_date_not_qualified_for_selected_value"]
            pair_ids = _sorted_unique([*pair_ids, *(item.pair_id for item in date_records
                                                   if item.fact_id in fact_ids)])
        if len(fact_ids) > 1 and (policy is None or policy.mode == "single"):
            return [], [], ["multiple_usable_pairs_without_selection_policy"]
        return fact_ids, pair_ids, []

    atom = expected_meta.atom
    spec = getattr(atom, "evaluation", None)
    if spec is None:
        return [], [], ["evaluation_spec_missing"]
    mode = spec.determination_mode
    if mode in {"semantic", "investigator_judgment"}:
        return [], [], [f"determination_mode_{mode}_not_direct_arithmetic"]
    if mode != "deterministic":
        return [], [], [f"determination_mode_{mode}_unsupported"]
    policy = spec.observation_policy
    if policy is None or policy.mode == "unresolved":
        return [], [], ["observation_selection_unverified"]
    operand_records = [item for item in usable_records if item.fact_attribute == spec.operand_attribute]
    fact_ids = _sorted_unique(item.fact_id for item in operand_records)
    pair_ids = _sorted_unique(item.pair_id for item in operand_records)
    if not fact_ids:
        return [], [], ["declared_operand_not_qualified"]
    if spec.time_operand_attribute is not None:
        time_records = [item for item in usable_records if item.fact_attribute == spec.time_operand_attribute]
        qualified_times = {item.fact_id for item in time_records}
        if any(fact_id not in qualified_times for fact_id in fact_ids):
            return [], [], ["declared_time_operand_not_qualified"]
        pair_ids = _sorted_unique([*pair_ids, *(item.pair_id for item in time_records
                                               if item.fact_id in fact_ids)])
    if policy.mode == "single" and len(fact_ids) != 1:
        return [], [], ["observation_selection_unverified"]
    if policy.mode not in {"single", "any", "all"}:
        return [], [], [f"observation_policy_mode_{policy.mode}_unsupported"]
    return fact_ids, pair_ids, []


def _select_with_ordering(*, frozen, accounting, review_context, **kwargs):
    """Apply source-declared ordering only inside the receipt-authorized path."""
    from app.services.ordered_observation_selection import observation_scope_reasons, select_ordered_observation
    family, meta = kwargs["family"], kwargs["expected_meta"]
    if family == "predicate":
        if meta["predicate"].repeat_scheme is not None:
            return [], [], ["repeat_relation_unverified"], None
        policy = meta["predicate"].observation_policy
        operand = "value"
        constraint = meta["time_constraint"]
        purpose = "event_membership"
        if meta["predicate"].requires_professional_judgment and not kwargs.get("written_content_verified"):
            return (*_select_facts_for_identity(**kwargs), None)
    else:
        spec = meta.atom.evaluation
        if spec is not None and spec.repeat_scheme is not None:
            return [], [], ["repeat_relation_unverified"], None
        policy = spec.observation_policy if spec is not None else None
        if spec is None or spec.determination_mode != "deterministic":
            return (*_select_facts_for_identity(**kwargs), None)
        operand, constraint, purpose = spec.operand_attribute, meta.atom.time_constraint, spec.time_purpose
    if policy is None:
        return (*_select_facts_for_identity(**kwargs), None)
    if policy.mode == "unresolved":
        return [], [], ["observation_selection_unverified"], None
    source = frozen if family == "predicate" else frozen.evidence_input
    identity_field = "predicate_identity_sha256" if family == "predicate" else "atom_identity_sha256"
    rows = [row for group in accounting if group[identity_field] == kwargs["identity"]
            for row in group["fact_accounting"]]
    usable = kwargs["usable_records"]
    if policy.selection is None:
        reasons = observation_scope_reasons(
            facts={fact.fact_id: fact for fact in source.facts},
            operand_fact_ids=[record.fact_id for record in usable if record.fact_attribute == operand],
            accounting=rows,
        )
        if reasons:
            return [], [], list(reasons), None
        return (*_select_facts_for_identity(**kwargs), None)
    if review_context is None:
        return [], [], ["observation_scope_unverified"], None
    selection = select_ordered_observation(
        policy=policy, facts={fact.fact_id: fact for fact in source.facts},
        operand_fact_ids=[record.fact_id for record in usable if record.fact_attribute == operand],
        date_fact_ids=[record.fact_id for record in usable if record.fact_attribute == "date_range"],
        accounting=rows, time_constraint=constraint, anchor_dates=source.episode.anchor_dates,
        time_purpose=purpose,
        conflicting_fact_ids=[fact_id for group in review_context.conflict_groups for fact_id in group.fact_ids],
    )
    audit = {
        "policy_sha256": canonical_hash(policy.model_dump(mode="json")),
        "accounting_sha256": canonical_hash(rows),
        "selected_fact_ids": list(selection.fact_ids),
        "not_selected": [{"fact_id": fact_id, "reason": reason} for fact_id, reason in selection.excluded],
    }
    pair_ids = sorted({record.pair_id for record in usable if record.fact_id in selection.fact_ids
                       and record.fact_attribute in {operand, "date_range"}})
    return list(selection.fact_ids), pair_ids, list(selection.reasons), audit


def _semantic_ordering(*, frozen, family, identity, policy, relations, records,
                       usable, accounting, review_context, constraint, purpose):
    from app.services.semantic_observation_selection import select_semantic_ordered_observation

    source = frozen if family == "predicate" else frozen.evidence_input
    identity_field = "predicate_identity_sha256" if family == "predicate" else "atom_identity_sha256"
    rows = [row for group in accounting if group[identity_field] == identity
            for row in group["fact_accounting"]]
    return select_semantic_ordered_observation(
        policy=policy, facts={fact.fact_id: fact for fact in source.facts},
        relations=relations, source_records=[item for item in records if item.identity_sha256 == identity],
        usable_records=usable, accounting=rows, review_context=review_context,
        time_constraint=constraint, anchor_dates=source.episode.anchor_dates, time_purpose=purpose,
    )


@dataclass(frozen=True)
class ReceiptVerifiedQualifiedBindingSelections:
    """Sealed alternative input for calculate_frozen_review; not a raw dict."""

    _seal: object
    material: QualifiedBindingSelectionMaterial
    control_input: ControlBindingFrozenInput | None
    predicate_frozen_input: PredicateBindingFrozenInput | None
    qualification_job_id: str
    candidate_family: str
    _verified_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _SEAL:
            raise TypeError("须通过回执核实工厂构造资格选择，不能直接伪造")
        object.__setattr__(self, "_verified_digest", self._content_digest())

    def _content_digest(self) -> str:
        return canonical_hash({
            "material": self.material.model_dump(mode="json"),
            "control_input": None if self.control_input is None else self.control_input.model_dump(mode="json"),
            "predicate_input": None if self.predicate_frozen_input is None else self.predicate_frozen_input.model_dump(mode="json"),
            "job_id": self.qualification_job_id, "family": self.candidate_family,
        })

    def require_unchanged(self) -> None:
        if self._seal is not _SEAL or self._content_digest() != self._verified_digest:
            raise ValueError("回执核实后的资料对应内容已变化，不能继续计算")

    @property
    def predicate_fact_ids_by_component(self) -> Mapping[str, Mapping[str, Sequence[str]]] | None:
        return self.material.predicate_fact_ids_by_component

    @property
    def control_selections(self) -> Mapping[str, Sequence[str]] | None:
        return self.material.control_selections


def build_receipt_verified_qualified_binding_selections(
    session,
    artifact_store,
    *,
    qualification_job_id: str,
    authorization: QualificationAdoptionAuthorization,
) -> ReceiptVerifiedQualifiedBindingSelections:
    """Verify receipts then project usable/unresolved selections under authorization."""
    if not isinstance(authorization, QualificationAdoptionAuthorization):
        raise InvalidJobDefinitionError("正式使用资格结果必须提供版本化采信授权对象")
    authorization = QualificationAdoptionAuthorization.model_validate(
        authorization.model_dump(mode="json"),
    )
    verified = verify_completed_binding_qualification(
        session, artifact_store, qualification_job_id,
        require_candidate_route_receipts=True,
    )
    _validate_authorization(session, authorization, verified)
    manifest = read_binding_evaluation(artifact_store, authorization.approved_evaluation_evidence_sha256)
    binding_method = require_evaluated_binding_method(manifest, verified, QUALIFIED_BINDING_CONSUMER_ALGORITHM)
    content, supported = None, frozenset()
    content_sources = set()
    content_pair_ids = set()
    if authorization.judgment_content is not None:
        from app.services.qualified_judgment_content import verify_qualified_content
        content, supported = verify_qualified_content(
            session, artifact_store, source=verified, binding_method=binding_method,
            adoption=authorization.judgment_content,
        )
        content_sources = {(pair.identity_sha256, pair.fact_id) for pair in content["pairs"]
                           if pair.pair_id in supported and pair.fact_attribute == "value"}
        content_pair_ids = {pair.pair_id for pair in content["pairs"]}
    family = verified["candidate_family"]
    frozen = verified["frozen"]
    summary = verified["summary"]
    records = list(summary.pair_records)
    review_context = None
    context_id = verified["payload"].get("review_context_id")
    if context_id is not None:
        from app.storage.review_context_repository import ReviewContextV2Repository
        review_context = ReviewContextV2Repository(session).get(context_id)
        if review_context.context_sha256 != verified["payload"].get("review_context_sha256"):
            raise InvalidJobDefinitionError("观察选择的审核资料版本已变化")
    proposition_relations, unresolved_proposition_pairs = [], []
    requires_proposition = (
        any(item.predicate.semantic_proposition is not None for component in frozen.components
            for item in component.binding_predicates)
        if isinstance(frozen, PredicateBindingFrozenInput) else
        any(item.atom.evaluation is not None
            and item.atom.evaluation.determination_mode in {"semantic", "investigator_judgment"}
            for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True))
    )
    if requires_proposition and authorization.proposition_evidence is None:
        raise InvalidJobDefinitionError("本方案包含需要核实原文含义的条件，请先完成该步骤；没有可核对原文时也须保留检查记录")
    if authorization.proposition_evidence is not None:
        from app.services.qualified_proposition_evidence import (
            verify_qualified_proposition_evidence, select_qualified_relations,
        )
        proposition = verify_qualified_proposition_evidence(
            session, artifact_store, source=verified, binding_method=binding_method,
            adoption=authorization.proposition_evidence,
        )
    validity_specs = {}
    if isinstance(frozen, ControlBindingFrozenInput):
        for identity in project_control_atom_identities(frozen.publication, include_repeat_triggers=True):
            spec = identity.atom.evaluation
            if (spec is not None and (spec.determination_mode == "deterministic"
                                     or spec.version in {"control-atom-evaluation/v2", "control-atom-evaluation/v3", "control-atom-evaluation/v4"})
                    and spec.time_purpose == "source_validity"
                    and identity.atom.time_constraint is not None
                    and spec.observation_policy is not None and spec.observation_policy.mode == "single"
                    and (spec.operand_attribute if spec.operation == "time_constraint"
                         else spec.time_operand_attribute) == "date_range"):
                validity_specs[identity.identity_sha256] = spec
    if authorization.proposition_evidence is not None:
        proposition_relations, unresolved_proposition_pairs = select_qualified_relations(
            proposition, records, source_validity_specs=validity_specs,
            written_content_verified_pair_ids=frozenset(
                record.pair_id for record in records if record.pair_id in supported
                or (record.fact_attribute == "date_range" and (record.identity_sha256, record.fact_id) in content_sources)),
        )
    frequency_statements = []
    if authorization.frequency_evidence is not None:
        from app.services.qualified_frequency_evidence import (
            verify_qualified_frequency_evidence, select_qualified_frequency_sources,
        )
        frequency_evidence = verify_qualified_frequency_evidence(
            session, artifact_store, source=verified, binding_method=binding_method,
            adoption=authorization.frequency_evidence,
        )
        frequency_statements = select_qualified_frequency_sources(
            frequency_evidence, records, source_validity_specs=validity_specs,
        )
    observation_relations = []
    if authorization.observation_relation is not None:
        from app.services.qualified_observation_relation import (
            verify_qualified_observation_relation, select_qualified_observation_relations,
        )
        observation_evidence = verify_qualified_observation_relation(
            session, artifact_store, source=verified, binding_method=binding_method,
            adoption=authorization.observation_relation,
        )
        observation_relations = select_qualified_observation_relations(
            observation_evidence, records, source_validity_specs=validity_specs,
            frozen_facts=(frozen.facts if family == "predicate" else frozen.evidence_input.facts),
            candidate_fact_accounting=verified["candidate_fact_accounting"],
            written_content_verified_pair_ids=frozenset(
                record.pair_id for record in records if (
                    record.pair_id in supported or (record.fact_attribute == "date_range"
                    and (record.identity_sha256, record.fact_id) in content_sources))),
        )
    professional_identities = ({item.predicate_identity_sha256
                               for component in frozen.components
                               for item in component.binding_predicates
                               if item.predicate.requires_professional_judgment}
                              if isinstance(frozen, PredicateBindingFrozenInput) else {
                                  item.identity_sha256 for item in project_control_atom_identities(
                                      frozen.publication, include_repeat_triggers=True)
                                  if item.atom.requires_professional_judgment})
    by_identity: dict[str, list[BindingQualificationPairRecord]] = {}
    rejected_pairs: list[QualifiedBindingRejectedPair] = []
    for record in records:
        content_verified = (record.pair_id in supported or (
            record.fact_attribute == "date_range" and (record.identity_sha256, record.fact_id) in content_sources))
        validity_spec = validity_specs.get(record.identity_sha256)
        rejection = pair_direct_selection_rejection_reasons(
            record, written_content_verified=content_verified,
            source_validity_calculable=source_validity_operand_calculable(record, validity_spec),
        )
        if (content is not None and record.fact_attribute == "value"
                and record.identity_sha256 in professional_identities
                and record.pair_id in content_pair_ids and not content_verified):
            rejection = _sorted_unique([*rejection, "written_content_unverified"])
        if rejection:
            rejected_pairs.append(QualifiedBindingRejectedPair(
                pair_id=record.pair_id,
                identity_sha256=record.identity_sha256,
                fact_id=record.fact_id,
                reasons=rejection,
            ))
            continue
        by_identity.setdefault(record.identity_sha256, []).append(record)

    identity_records: dict[str, list] = {}
    for item in summary.identity_records:
        identity_records.setdefault(item.identity_sha256, []).append(item)
    if observation_relations:
        from app.services.repeat_condition_selection import build_repeat_condition_selections
        build_repeat_condition_selections(
            frozen=frozen, family=family, observation_relations=observation_relations,
            records=records, by_identity=by_identity, identity_records=identity_records,
            accounting=verified["candidate_fact_accounting"], proposition_relations=proposition_relations,
            proposition_pair_gaps=unresolved_proposition_pairs, supported_pair_ids=supported,
            review_context=review_context,
        )
    outcomes: list[QualifiedBindingIdentityOutcome]
    predicate_map: dict[str, dict[str, list[str]]] | None = None
    control_map: dict[str, list[str]] | None = None
    predicate_frozen = None
    control_input = None

    if family == "predicate":
        if not isinstance(frozen, PredicateBindingFrozenInput):
            raise InvalidJobDefinitionError("谓词资格任务冻结输入类型无效")
        predicate_frozen = frozen
        expected = _expected_predicate_identities(frozen)
        outcomes = []
        predicate_map = {
            component.rule_component_id: {}
            for component in frozen.components
        }
        for identity, meta in expected.items():
            usable = by_identity.get(identity, [])
            fact_ids, pair_ids, unresolved, ordering = _select_with_ordering(
                frozen=frozen, accounting=verified["candidate_fact_accounting"], review_context=review_context,
                family=family, identity=identity, usable_records=usable, expected_meta=meta,
                written_content_verified=any(item.fact_attribute == "value" for item in usable) and all(
                    item.pair_id in supported for item in usable if item.fact_attribute == "value"),
            )
            if (meta["predicate"].semantic_proposition is not None
                    and meta["predicate"].repeat_scheme is None):
                ordering = None
                relations = [item for item in proposition_relations if item["identity_sha256"] == identity]
                fact_ids = _sorted_unique([item["fact_id"] for item in relations])
                pair_ids = _sorted_unique([item["pair_id"] for item in relations])
                unresolved = [] if relations else ["semantic_evidence_unverified"]
                source_pairs = {item.pair_id for item in records if item.identity_sha256 == identity
                                and item.fact_attribute in {"value", "assertion_basis"}}
                for relation in relations:
                    relation["scope_candidates_complete"] = source_pairs == set(pair_ids)
                policy = meta["predicate"].observation_policy
                if policy is None or policy.mode == "unresolved":
                    unresolved.append("observation_selection_unverified")
                if policy is not None and policy.selection is not None:
                    selected = _semantic_ordering(
                        frozen=frozen, family=family, identity=identity, policy=policy,
                        relations=relations, records=records, usable=usable,
                        accounting=verified["candidate_fact_accounting"], review_context=review_context,
                        constraint=meta["time_constraint"], purpose="event_membership",
                    )
                    fact_ids, pair_ids = list(selected.fact_ids), list(selected.pair_ids)
                    unresolved, ordering = list(selected.reasons), selected.ordering
                elif policy is not None and policy.mode == "single" and source_pairs != set(pair_ids):
                    unresolved.append("single_observation_relations_incomplete")
                if meta["time_constraint"] is not None:
                    dates = [item for item in usable if item.fact_attribute == "date_range"]
                    if not set(fact_ids) <= {item.fact_id for item in dates}:
                        unresolved.append("declared_time_operand_not_qualified")
                    else:
                        pair_ids = _sorted_unique([*pair_ids, *(item.pair_id for item in dates
                                                              if item.fact_id in fact_ids)])
            if meta["predicate"].repeat_scheme is not None:
                unresolved = _sorted_unique([*unresolved, "repeat_relation_unverified"])
                ordering = None
            records_for_identity = identity_records.get(identity) or []
            if not records_for_identity:
                unresolved = _sorted_unique([*unresolved, "identity_absent_from_qualification"])
            elif all(item.status == "no_candidates_in_supplied_input" for item in records_for_identity):
                unresolved = _sorted_unique([
                    *unresolved,
                    *(
                        reason
                        for item in records_for_identity
                        for reason in (item.unresolved_reasons or ["no_candidate_pairs_in_completed_job"])
                    ),
                ])
                fact_ids, pair_ids = [], []
            # Attach concrete rejection reasons when every candidate pair failed.
            if not fact_ids:
                pair_rejections = [
                    reason
                    for item in rejected_pairs
                    if item.identity_sha256 == identity
                    for reason in item.reasons
                ]
                if pair_rejections:
                    unresolved = _sorted_unique([*unresolved, *pair_rejections, "no_usable_qualified_pair"])
            if unresolved:
                fact_ids, pair_ids = [], []
                status = "unresolved"
            else:
                status = "usable"
            outcomes.append(QualifiedBindingIdentityOutcome(
                identity_field="predicate_identity_sha256",
                identity_sha256=identity,
                status=status,
                fact_ids=fact_ids,
                usable_pair_ids=pair_ids,
                unresolved_reasons=unresolved,
                observation_ordering=ordering,
            ))
            # Auxiliary checks retain outcomes without changing eligibility inputs.
            if meta["role"] != "repeat_trigger":
                predicate_map[meta["rule_component_id"]][meta["predicate_id"]] = list(fact_ids)
        # Preserve identities that appear only as no-candidate qualification rows
        # outside the current frozen expected set? Formal consumer requires the
        # frozen expected set; extras are ignored after accounting via rejected pairs.
    else:
        if not isinstance(frozen, ControlBindingFrozenInput):
            raise InvalidJobDefinitionError("控制资格任务冻结输入类型无效")
        control_input = frozen
        expected = _expected_control_identities(frozen)
        outcomes = []
        control_map = {}
        for identity, meta in expected.items():
            usable = by_identity.get(identity, [])
            fact_ids, pair_ids, unresolved, ordering = _select_with_ordering(
                frozen=frozen, accounting=verified["candidate_fact_accounting"], review_context=review_context,
                family=family, identity=identity, usable_records=usable, expected_meta=meta,
            )
            spec = meta.atom.evaluation
            if (spec is not None and spec.repeat_scheme is None
                    and spec.determination_mode in {"semantic", "investigator_judgment"}):
                relations = [item for item in proposition_relations if item["identity_sha256"] == identity]
                if not relations:
                    fact_ids, pair_ids, ordering = [], [], None
                    unresolved = ["semantic_evidence_unverified"]
                    if spec.observation_policy is not None and spec.observation_policy.selection is not None:
                        selected = _semantic_ordering(
                            frozen=frozen, family=family, identity=identity, policy=spec.observation_policy,
                            relations=relations, records=records, usable=usable,
                            accounting=verified["candidate_fact_accounting"], review_context=review_context,
                            constraint=meta.atom.time_constraint, purpose=spec.time_purpose,
                        )
                        unresolved, ordering = list(selected.reasons), selected.ordering
                if relations:
                    fact_ids = _sorted_unique([item["fact_id"] for item in relations])
                    pair_ids = _sorted_unique([item["pair_id"] for item in relations])
                    source_content_pairs = {item.pair_id for item in records
                                            if item.identity_sha256 == identity
                                            and item.fact_attribute in {"value", "assertion_basis"}}
                    for relation in relations:
                        relation["scope_candidates_complete"] = source_content_pairs == set(pair_ids)
                    # These are selected source relations, not arithmetic values.
                    # The combiner still checks policy, time and source conflicts.
                    unresolved = []
                    if spec.observation_policy is None or spec.observation_policy.mode == "unresolved":
                        unresolved.append("observation_selection_unverified")
                    if spec.observation_policy is not None and spec.observation_policy.selection is not None:
                        selected = _semantic_ordering(
                            frozen=frozen, family=family, identity=identity, policy=spec.observation_policy,
                            relations=relations, records=records, usable=usable,
                            accounting=verified["candidate_fact_accounting"], review_context=review_context,
                            constraint=meta.atom.time_constraint, purpose=spec.time_purpose,
                        )
                        fact_ids, pair_ids = list(selected.fact_ids), list(selected.pair_ids)
                        unresolved, ordering = list(selected.reasons), selected.ordering
                    elif spec.observation_policy is not None and spec.observation_policy.mode == "single":
                        eligible = {item.pair_id for item in usable
                                    if item.fact_attribute in {"value", "assertion_basis"}}
                        if eligible != set(pair_ids):
                            unresolved = ["single_observation_relations_incomplete"]
                    if meta.atom.time_constraint is not None:
                        dates = [item for item in usable if item.fact_attribute == spec.time_operand_attribute]
                        if (spec.version not in {"control-atom-evaluation/v2", "control-atom-evaluation/v3", "control-atom-evaluation/v4"}
                                or spec.time_operand_attribute != "date_range"
                                or not set(fact_ids) <= {item.fact_id for item in dates}):
                            unresolved = _sorted_unique([*unresolved, "declared_time_operand_not_qualified"])
                        else:
                            pair_ids = _sorted_unique([*pair_ids, *(item.pair_id for item in dates
                                                                  if item.fact_id in fact_ids)])
            if spec is not None and spec.repeat_scheme is not None:
                unresolved = _sorted_unique([*unresolved, "repeat_relation_unverified"])
                ordering = None
            records_for_identity = identity_records.get(identity) or []
            if not records_for_identity:
                unresolved = _sorted_unique([*unresolved, "identity_absent_from_qualification"])
            elif all(item.status == "no_candidates_in_supplied_input" for item in records_for_identity):
                unresolved = _sorted_unique([
                    *unresolved,
                    *(
                        reason
                        for item in records_for_identity
                        for reason in (item.unresolved_reasons or ["no_candidate_pairs_in_completed_job"])
                    ),
                ])
                fact_ids, pair_ids = [], []
            # Attach concrete rejection reasons when every candidate pair failed.
            if not fact_ids:
                pair_rejections = [
                    reason
                    for item in rejected_pairs
                    if item.identity_sha256 == identity
                    for reason in item.reasons
                ]
                if pair_rejections:
                    unresolved = _sorted_unique([*unresolved, *pair_rejections, "no_usable_qualified_pair"])
            if unresolved:
                fact_ids, pair_ids = [], []
                status = "unresolved"
            else:
                status = "usable"
            outcomes.append(QualifiedBindingIdentityOutcome(
                identity_field="atom_identity_sha256",
                identity_sha256=identity,
                status=status,
                fact_ids=fact_ids,
                usable_pair_ids=pair_ids,
                unresolved_reasons=unresolved,
                observation_ordering=ordering,
            ))
            if meta.layer != "repeat_trigger":
                control_map[identity] = list(fact_ids)

    if proposition_relations:
        selected_pairs = {pair_id for outcome in outcomes if outcome.status == "usable"
                          for pair_id in outcome.usable_pair_ids}
        excluded_facts = {(outcome.identity_sha256, item.fact_id)
                          for outcome in outcomes if outcome.status == "usable"
                          and outcome.observation_ordering is not None
                          for item in outcome.observation_ordering.not_selected}
        for relation in proposition_relations:
            if relation["pair_id"] not in selected_pairs:
                if (relation["identity_sha256"], relation["fact_id"]) in excluded_facts:
                    continue
                original_pair = next((pair for pair in verified["pairs"]
                                      if pair.pair_id == relation["pair_id"]), None)
                if original_pair is None:
                    raise InvalidJobDefinitionError("原文关系未找到对应的冻结配对")
                unresolved_proposition_pairs.append({
                    "pair_id": relation["pair_id"], "identity_sha256": relation["identity_sha256"],
                    "fact_id": relation["fact_id"],
                    "locator_id": original_pair.locator_id,
                    "reasons": ["identity_selection_unresolved"],
                })
        proposition_relations = [relation for relation in proposition_relations
                                 if relation["pair_id"] in selected_pairs]

    # Keep rejection rows for expected identities that had only rejected pairs and
    # no usable path, including identities never proposed.
    accounted = {item.identity_sha256 for item in outcomes}
    for identity, group in by_identity.items():
        if identity in accounted:
            continue
        for record in group:
            rejected_pairs.append(QualifiedBindingRejectedPair(
                pair_id=record.pair_id,
                identity_sha256=record.identity_sha256,
                fact_id=record.fact_id,
                reasons=["identity_outside_current_frozen_expected_set"],
            ))

    verified_requirements = []
    if content is not None and family == "predicate":
        from app.services.qualified_judgment_content import verified_judgment_requirements
        from app.storage.review_context_repository import ReviewContextV2Repository
        review = ReviewContextV2Repository(session).get(content["review_context_id"])
        verified_requirements = verified_judgment_requirements(review, frozen, outcomes, content, supported)
    material = {
        "version": QUALIFIED_BINDING_SELECTION_VERSION,
        "consumer_algorithm_version": QUALIFIED_BINDING_CONSUMER_ALGORITHM,
        "candidate_family": family,
        "qualification_job_id": qualification_job_id,
        "authorization_id": authorization.authorization_id,
        "authorizing_service": authorization.authorizing_service,
        "frozen_input_sha256": verified["frozen_input_sha256"],
        "comparison_sha256": verified["comparison_sha256"],
        "summary_logical_sha256": verified["summary_sha256"],
        "summary_artifact_sha256": verified["summary_artifact_sha256"],
        "approved_evaluation_evidence_sha256": (
            authorization.approved_evaluation_evidence_sha256
        ),
        "identity_outcomes": [item.model_dump(mode="json") for item in outcomes],
        "rejected_pairs": [item.model_dump(mode="json") for item in rejected_pairs],
        "predicate_fact_ids_by_component": predicate_map,
        "control_selections": control_map,
        "review_context_id": verified["payload"].get("review_context_id"),
        "review_context_sha256": verified["payload"].get("review_context_sha256"),
        "judgment_content": (None if authorization.judgment_content is None
                             else authorization.judgment_content.model_dump(mode="json")),
        "proposition_evidence": (None if authorization.proposition_evidence is None
                                 else authorization.proposition_evidence.model_dump(mode="json")),
        "proposition_relations": proposition_relations,
        "unresolved_proposition_pairs": unresolved_proposition_pairs,
        "content_supported_pair_ids": sorted(supported),
        "verified_judgment_requirement_ids": verified_requirements,
        "accepted": False,
        "authorized_clinical_adoption": False,
        "clinically_qualified": False,
    }
    if authorization.observation_relation is not None:
        material["observation_relation"] = authorization.observation_relation.model_dump(mode="json")
        material["observation_relations"] = observation_relations
    if authorization.frequency_evidence is not None:
        material["frequency_evidence"] = authorization.frequency_evidence.model_dump(mode="json")
        material["frequency_statements"] = frequency_statements
    material["selection_sha256"] = qualified_binding_selection_hash(material)
    validated = QualifiedBindingSelectionMaterial.model_validate(material)
    return ReceiptVerifiedQualifiedBindingSelections(
        _seal=_SEAL,
        material=validated,
        control_input=control_input,
        predicate_frozen_input=predicate_frozen,
        qualification_job_id=qualification_job_id,
        candidate_family=family,
    )


def assert_qualified_selections_match_review_context(
    *,
    frozen_review,
    rule_set,
    selections: ReceiptVerifiedQualifiedBindingSelections,
) -> None:
    """Bind sealed selections to the current frozen review authority/facts/publication."""
    if not isinstance(selections, ReceiptVerifiedQualifiedBindingSelections):
        raise ValueError("回执核实选择类型无效")
    selections.require_unchanged()
    if selections.material.review_context_id is not None and (
        selections.material.review_context_id != frozen_review.context_id
        or selections.material.review_context_sha256 != frozen_review.context_sha256
    ):
        raise ValueError("核实结果属于另一份审核准备，不能改接当前审核")
    if selections.candidate_family == "predicate":
        source = selections.predicate_frozen_input
        if source is None:
            raise ValueError("缺少谓词冻结输入")
        if source.authority != frozen_review.authority or source.episode != frozen_review.review_episode:
            raise ValueError("资格选择与本次审核权威范围不一致")
        expected_facts = sorted(
            (_frozen_fact(item).model_dump(mode="json") for item in frozen_review.facts),
            key=lambda item: item["fact_id"],
        )
        supplied_facts = sorted(
            (item.model_dump(mode="json") for item in source.facts),
            key=lambda item: item["fact_id"],
        )
        if canonical_hash(expected_facts) != canonical_hash(supplied_facts):
            raise ValueError("资格选择事实集合与本次审核不一致")
        component_ids = {clause.rule_component_id for clause in frozen_review.clause_pack.clauses}
        if set(selections.predicate_fact_ids_by_component or {}) != component_ids:
            raise ValueError("资格选择未完整覆盖本次审核的每项条件")
        expected_components = sorted(
            (_frozen_component(component, rule).model_dump(mode="json")
             for rule in rule_set.rules for component in rule.components),
            key=lambda item: item["rule_component_id"],
        )
        actual_components = sorted(
            (item.model_dump(mode="json") for item in source.components),
            key=lambda item: item["rule_component_id"],
        )
        if actual_components != expected_components:
            raise ValueError("资格核对的具体条件及来源政策与本次方案不一致")
        return
    source = selections.control_input
    if source is None:
        raise ValueError("缺少控制冻结输入")
    publication = frozen_review.clause_pack.control_publication
    if publication is None:
        raise ValueError("本次审核没有补充要求，不能使用控制资格选择")
    if source.publication != publication:
        raise ValueError("资格选择控制目录与本次审核不一致")
    if (source.evidence_input.authority != frozen_review.authority
            or source.evidence_input.episode != frozen_review.review_episode):
        raise ValueError("资格选择与本次审核权威范围不一致")
    expected_facts = sorted(
        (_frozen_fact(item).model_dump(mode="json") for item in frozen_review.facts),
        key=lambda item: item["fact_id"],
    )
    supplied_facts = sorted(
        (item.model_dump(mode="json") for item in source.evidence_input.facts),
        key=lambda item: item["fact_id"],
    )
    if canonical_hash(expected_facts) != canonical_hash(supplied_facts):
        raise ValueError("资格选择事实集合与本次审核不一致")
