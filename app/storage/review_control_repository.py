"""Immutable control report parts; no current-head lookup or clinical inference."""
from sqlalchemy.orm import Session

from app.domain.contracts.control_review_outcome import ReviewControlSnapshot
from app.domain.contracts.enums import GateOutcome
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.storage.repositories import (
    AppendRepository, DuplicateRecordError, GATE_RESULT_CONFIG, REVIEW_RUN_CONFIG,
    ScopeViolationError, _config,
)
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.review_control_models import ReviewControlSnapshotRecord

REVIEW_CONTROL_GATE_NAME = "review-control-publication"
_CONFIG = _config(
    ReviewControlSnapshotRecord, ReviewControlSnapshot,
    {"review_run_id": "review_run_id", "context_id": "context_id", "gate_result_id": "gate_result_id"},
    mirrors={"context_id": "context_id", "gate_result_id": "gate_result_id"},
    created_at_key="created_at",
)


class ReviewControlRepository:
    """The enclosing publisher owns the transaction and semantic evidence checks."""
    def __init__(self, session: Session):
        self.session = session
        self.repository = AppendRepository(session, _CONFIG)

    def get_or_none(self, review_run_id: str) -> ReviewControlSnapshot | None:
        value = self.repository.get_or_none(review_run_id)
        if value is not None:
            self._verify(value)
        return value

    def save(self, snapshot: ReviewControlSnapshot) -> ReviewControlSnapshot:
        value = ReviewControlSnapshot.model_validate(snapshot.model_dump(mode="json"))
        self._verify(value)
        existing = self.get_or_none(value.review_run_id)
        if existing is not None:
            if existing != value:
                raise DuplicateRecordError("同次审核的补充要求结果不能覆盖")
            return existing
        self.repository.save(value)
        return value

    def _verify(self, value: ReviewControlSnapshot) -> None:
        run = AppendRepository(self.session, REVIEW_RUN_CONFIG).get(value.review_run_id)
        context = ReviewContextV2Repository(self.session).get(value.context_id)
        if (run.schema_version != "review/v2" or run.context_id != value.context_id
                or context.review_run_id != value.review_run_id
                or context.context_sha256 != value.context_sha256
                or run.completed_at != value.created_at):
            raise ScopeViolationError("补充要求结果与本次审核保存依据不一致")
        publication = context.clause_pack.control_publication
        controls = {} if publication is None else {
            item.protocol_control_id: item for item in publication.catalog.controls
        }
        if {item.protocol_control_id for item in value.outcomes} != set(controls):
            raise ScopeViolationError("本次补充要求审核结果不完整")
        identities = {} if publication is None else {
            (item.protocol_control_id, item.atom_id): item
            for item in project_control_atom_identities(publication)
        }
        facts = {item.fact_id: item for item in context.facts}
        for outcome in value.outcomes:
            control = controls[outcome.protocol_control_id]
            if outcome.control_sha256 != canonical_hash(control.model_dump(mode="json")):
                raise ScopeViolationError("补充要求结果使用了不同的方案内容")
            if control.obligation_expression is None:
                raise ScopeViolationError("补充要求缺少完整的条件结构")
            atom_hashes = {identity.identity_sha256 for identity in identities.values()
                           if identity.protocol_control_id == control.protocol_control_id}
            if not set(outcome.unresolved_atoms) <= atom_hashes:
                raise ScopeViolationError("待核实条件不属于本项方案要求")
            if not set(outcome.observation_ordering) <= atom_hashes:
                raise ScopeViolationError("检查选择依据不属于本项方案要求")
            if not set(outcome.repeat_evaluations) <= atom_hashes:
                raise ScopeViolationError("复查依据不属于本项方案要求")
            for identity_hash, repeat in outcome.repeat_evaluations.items():
                identity = next(item for item in identities.values() if item.identity_sha256 == identity_hash)
                scheme = identity.atom.evaluation.repeat_scheme if identity.atom.evaluation is not None else None
                if (scheme is None or repeat.atom_sha256 != canonical_hash(identity.atom.model_dump(mode="json"))
                        or repeat.context_sha256 != outcome.frozen_input_sha256
                        or repeat.resolution.get("owner_identity_sha256") != identity_hash
                        or repeat.resolution.get("parent_id") != control.protocol_control_id
                        or repeat.resolution.get("scheme_sha256") != canonical_hash(scheme.model_dump(mode="json"))
                        or not repeat.evidence_fact_ids <= set(facts)):
                    raise ScopeViolationError("复查结果使用了不同的方案或原始资料")
            if not set(outcome.frequency_evaluations) <= atom_hashes:
                raise ScopeViolationError("频次依据不属于本项方案要求")
            for identity_hash, frequency in outcome.frequency_evaluations.items():
                identity = next(item for item in identities.values() if item.identity_sha256 == identity_hash)
                spec = identity.atom.evaluation
                if (spec is None or spec.predicate is None or spec.predicate.occurrence_window is None
                        or spec.determination_mode != "deterministic" or spec.repeat_scheme is not None
                        or identity.atom.requires_professional_judgment
                        or frequency.atom_sha256 != canonical_hash(identity.atom.model_dump(mode="json"))
                        or frequency.context_sha256 != outcome.frozen_input_sha256
                        or frequency.resolution.get("identity_sha256") != identity_hash
                        or not frequency.evidence_fact_ids <= set(facts)
                        or any(source["fact_id"] not in facts
                               or source["locator_id"] not in facts[source["fact_id"]].locator_ids
                               for source in frequency.resolution.get("statement_sources", ()) )):
                    raise ScopeViolationError("频次结果使用了不同的方案或原始资料")
            for identity_hash, audit in outcome.observation_ordering.items():
                identity = next(item for item in identities.values() if item.identity_sha256 == identity_hash)
                policy = identity.atom.evaluation.observation_policy if identity.atom.evaluation else None
                if (policy is None or policy.selection is None
                        or canonical_hash(policy.model_dump(mode="json")) != audit.policy_sha256
                        or not set(audit.selected_fact_ids) <= set(facts)
                        or any(item.fact_id not in facts for item in audit.not_selected)):
                    raise ScopeViolationError("检查选择依据与冻结方案或资料不一致")
            trigger_ids = sorted(branch.trigger_branch_id for branch in (
                control.trigger_expression.groups if control.trigger_expression else ()
            ) if branch.trigger_branch_id is not None)
            expected = {atom.obligation_id: (group, atom)
                        for group in control.obligation_expression.groups for atom in group.atoms}
            if (len(outcome.obligations) != len(expected)
                    or {item.obligation_id for item in outcome.obligations} != set(expected)):
                raise ScopeViolationError("补充要求的逐项记录有重复或遗漏")
            for item in outcome.obligations:
                group, atom = expected[item.obligation_id]
                identity = identities[(control.protocol_control_id, atom.obligation_id)]
                repeat = outcome.repeat_evaluations.get(identity.identity_sha256)
                frequency = outcome.frequency_evaluations.get(identity.identity_sha256)
                if frequency is not None and (frequency.result.truth != item.observation_truth
                                              or set(frequency.result.used_fact_ids) != set(item.used_fact_ids)):
                    raise ScopeViolationError("本项结果与保存的频次计算不一致")
                if repeat is not None and (repeat.result.truth != item.observation_truth
                                           or set(repeat.result.used_fact_ids) != set(item.used_fact_ids)):
                    raise ScopeViolationError("本项结果与保存的复查计算不一致")
                audit = outcome.observation_ordering.get(identity.identity_sha256)
                if audit is not None and set(item.used_fact_ids).intersection(
                    excluded.fact_id for excluded in audit.not_selected
                ):
                    raise ScopeViolationError("未采用的记录不能同时列为本项判断依据")
                if audit is not None and set(item.used_fact_ids) != set(audit.selected_fact_ids):
                    raise ScopeViolationError("本项采用事实与检查选择依据不一致")
                if (item.identity_sha256 != identity.identity_sha256
                        or item.obligation_group_id != group.obligation_group_id
                        or item.statement != atom.statement or item.kind != atom.kind
                        or item.modality != atom.modality
                        or item.proposition != (atom.evaluation.proposition if atom.evaluation else None)
                        or item.protocol_span_ids != atom.source_span_ids
                        or item.protocol_excerpts != atom.source_excerpts
                        or item.activation_route != ("exception_replacement" if group.activated_by_exception_group_ids else "default_remaining")
                        or item.trigger_branch_ids != sorted(group.applies_to_trigger_branch_ids or trigger_ids)
                        or item.exception_group_ids != sorted(group.activated_by_exception_group_ids)
                        or not set(item.unresolved_atom_identities) <= set(outcome.unresolved_atoms)
                        or not set(item.used_fact_ids) <= set(facts)):
                    raise ScopeViolationError("补充要求结果的方案原文或事实归属不一致")
                allowed_locators = {locator for fact_id in item.used_fact_ids
                                    for locator in facts[fact_id].locator_ids}
                if not set(item.locator_ids) <= allowed_locators:
                    raise ScopeViolationError("补充要求的原件定位不属于所引用事实")
                gap_pairs = set()
                for gap in item.unverified_evidence:
                    fact = facts.get(gap.fact_id)
                    if (gap.identity_sha256 != item.identity_sha256 or fact is None
                            or gap.locator_id not in fact.locator_ids or gap.pair_id in gap_pairs
                            or atom.evaluation is None or atom.evaluation.determination_mode == "deterministic"
                            or any(not reason.strip() for reason in gap.reasons)):
                        raise ScopeViolationError("补充要求的原文疑问与本次资料或条件不一致")
                    gap_pairs.add(gap.pair_id)
        gate = AppendRepository(self.session, GATE_RESULT_CONFIG).get(value.gate_result_id)
        expected_input = None if not value.outcomes else canonical_hash({
            "context": value.context_sha256, "review_selections": value.selections_sha256,
            "control_selections": value.outcomes[0].selections_sha256,
            "control_input": value.outcomes[0].frozen_input_sha256,
        })
        if (gate.gate_name != REVIEW_CONTROL_GATE_NAME or gate.result != GateOutcome.ACCEPTED
                or value.review_run_id not in gate.accepted_entity_refs
                or value.context_id not in gate.input_entity_refs
                or gate.created_at != value.created_at
                or (expected_input is not None and gate.input_scope_hash != expected_input)
                or gate.output_hash != canonical_hash(value.model_dump(mode="json"))):
            raise ScopeViolationError("补充要求结果缺少正式保存回执")
