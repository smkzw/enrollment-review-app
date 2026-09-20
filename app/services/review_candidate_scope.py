"""Reject changed preparation inputs before scheduling expensive model reads."""
from app.domain.publication import canonical_hash
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.services.predicate_binding_input import _frozen_component, _frozen_fact
from app.storage.repositories import ScopeViolationError, get_rule_set
from app.storage.review_context_repository import ReviewContextV2Repository


def verify_candidate_preparation(session, payload, frozen):
    keys = {"review_context_id", "review_context_sha256"}
    present = keys.intersection(payload)
    if not present:
        return
    if present != keys or any(not isinstance(payload[key], str) or not payload[key].strip() for key in keys):
        raise ScopeViolationError("审核准备记录不完整，未执行本次核对")
    is_control = isinstance(frozen, ControlBindingFrozenInput)
    digest = require_prepared_candidate_scope(
        session, payload["review_context_id"],
        frozen.evidence_input if is_control else frozen,
        control_input=frozen if is_control else None,
    )
    if digest != payload["review_context_sha256"]:
        raise ScopeViolationError("审核准备内容与任务创建时不一致，未采用本次结果")


def require_prepared_candidate_scope(session, context_id, source, *, control_input=None):
    context = ReviewContextV2Repository(session).get(context_id)
    if source.authority != context.authority or source.episode != context.review_episode:
        raise ScopeViolationError("资料版本或审核节点已变化，请重新准备本次审核")
    expected = sorted((_frozen_fact(item).model_dump(mode="json") for item in context.facts),
                      key=lambda item: item["fact_id"])
    actual = sorted((item.model_dump(mode="json") for item in source.facts),
                    key=lambda item: item["fact_id"])
    if actual != expected:
        raise ScopeViolationError("已核实资料已变化，未启动使用不同资料的核对任务")
    rules = get_rule_set(session, context.authority.rule_set_id, context.authority.rule_set_revision)
    if canonical_hash(rules.model_dump(mode="json")) != context.rule_set_sha256:
        raise ScopeViolationError("本次审核所依据的方案内容不一致")
    expected_components = sorted(
        (_frozen_component(component, rule).model_dump(mode="json")
         for rule in rules.rules for component in rule.components),
        key=lambda item: item["rule_component_id"],
    )
    actual_components = sorted((item.model_dump(mode="json") for item in source.components),
                               key=lambda item: item["rule_component_id"])
    if actual_components != expected_components:
        raise ScopeViolationError("正式审核需核对本次方案的完整条件，不能仅选择部分条件")
    if control_input is not None and control_input.publication != context.clause_pack.control_publication:
        raise ScopeViolationError("方案补充要求与本次审核准备记录不一致")
    return context.context_sha256
