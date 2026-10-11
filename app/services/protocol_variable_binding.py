"""Variable correspondence changes data requirements, never clinical predicates."""
from __future__ import annotations

from hashlib import sha256

from pydantic import Field

from app.domain.contracts.agent_io import EvidenceRequirementDraft, ProtocolDeconstructionDraft
from app.domain.contracts.common import ContractModel
from app.domain.contracts.rules import iter_atomic_predicates, AtomicPredicate
from app.domain.variables.dictionary import VariableDef, load_dictionary


class VariableBinding(ContractModel):
    component_id: str = Field(min_length=1)
    predicate_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    variable_id: str = Field(min_length=1)


class VariableBindingProposal(ContractModel):
    variables: list[VariableDef] = Field(default_factory=list)
    bindings: list[VariableBinding] = Field(default_factory=list)


def component_predicates(component):
    for expression in (component.expression, component.exception_expression):
        if expression is not None:
            yield from iter_atomic_predicates(expression)
    for condition in getattr(component, "repeat_trigger_conditions", ()):
        yield from iter_atomic_predicates(condition.expression)


def validate_variable_predicate(variable: VariableDef, predicate: AtomicPredicate):
    values = predicate.value if isinstance(predicate.value, list) else [predicate.value]
    if any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        if variable.value_type != "number":
            raise ValueError("数值条件不能绑定非数值项目")
        for value in values:
            variable.convert(value, predicate.unit or "")
    elif any(isinstance(value, bool) for value in values):
        if variable.value_type not in {"boolean", "procedure"}:
            raise ValueError("是否类条件须绑定是否或检查完成项目")
    elif any(isinstance(value, str) for value in values):
        if variable.value_type not in {"category", "date"}:
            raise ValueError("分类条件不能绑定数值或其他项目")
    elif variable.value_type not in {"boolean", "exposure", "procedure", "category"}:
        raise ValueError("存在性条件不能把定量结果直接当作是否发生")


def binding_view(draft):
    variables = load_dictionary(draft.variable_definitions or ())
    predicates = []
    for rule in draft.proposed_rules:
        for component in rule.components:
            requirements = [item for item in draft.evidence_requirement_drafts
                            if item.proposed_requirement.rule_component_id == component.rule_component_id]
            for predicate in component_predicates(component):
                bound = [item.proposed_requirement.variable_id for item in requirements
                         if predicate.predicate_id in item.proposed_requirement.predicate_ids
                         and item.proposed_requirement.variable_id is not None]
                matching = [item for item in requirements
                            if predicate.predicate_id in item.proposed_requirement.predicate_ids]
                # Older drafts have component-level policies but no atomic correspondence yet.
                if not matching:
                    matching = requirements
                predicates.append({
                    "component_id": component.rule_component_id, "predicate_id": predicate.predicate_id,
                    "official_code": rule.official_code, "label": predicate.attribute,
                    "predicate": predicate.model_dump(mode="json"),
                    "variable_id": bound[0] if bound else None,
                    "requirements": [{"requirement_id": item.proposed_requirement.requirement_id,
                                      "description": item.proposed_requirement.description} for item in matching],
                })
    return {"variables": [item.model_dump(mode="json") for item in variables.values()],
            "predicates": predicates}


def apply_variable_bindings(draft: ProtocolDeconstructionDraft, proposal: VariableBindingProposal):
    definitions = load_dictionary([*(draft.variable_definitions or ()), *proposal.variables])
    result = draft.model_copy(deep=True)
    seen = set()
    selected_variables = {}
    components = {item.proposed_component.rule_component_id: item for item in result.component_drafts}
    for binding in proposal.bindings:
        key = (binding.component_id, binding.predicate_id)
        correspondence = (*key, binding.requirement_id)
        if correspondence in seen:
            raise ValueError("同一条件不能重复提交绑定")
        seen.add(correspondence)
        if key in selected_variables and selected_variables[key] != binding.variable_id:
            raise ValueError("同一条件不能对应不同数据项目")
        selected_variables[key] = binding.variable_id
        component_draft = components.get(binding.component_id)
        if component_draft is None or binding.variable_id not in definitions:
            raise ValueError("绑定引用了不存在的子项或数据项目")
        component = component_draft.proposed_component
        predicate = next((item for item in component_predicates(component)
                          if item.predicate_id == binding.predicate_id), None)
        template = next((item for item in result.evidence_requirement_drafts
                         if item.draft_component_id == component_draft.draft_component_id
                         and item.proposed_requirement.requirement_id == binding.requirement_id), None)
        if predicate is None or template is None:
            raise ValueError("条件与资料要求不属于同一子项")
        validate_variable_predicate(definitions[binding.variable_id], predicate)
        new_id = (template.proposed_requirement.requirement_id
                  if template.proposed_requirement.variable_id is not None
                  and binding.predicate_id in template.proposed_requirement.predicate_ids
                  else "variable_requirement:" + sha256(":".join(correspondence).encode()).hexdigest()[:32])
        payload = template.proposed_requirement.model_dump(mode="json") | {
            "requirement_id": new_id, "predicate_ids": [binding.predicate_id],
            "variable_id": binding.variable_id,
        }
        if predicate.requires_professional_judgment:
            payload["required_source_types"] = list(dict.fromkeys([
                *payload["required_source_types"], "investigator_assessment"]))
        requirement = type(template.proposed_requirement).model_validate(payload)
        stages = [stage for stage in result.proposed_workflow_stages
                  if template.proposed_requirement.requirement_id in stage.due_requirement_ids]
        if len(stages) != 1:
            raise ValueError("原资料要求缺少唯一到期节点，不能猜测新项目的适用节点")
        if new_id not in stages[0].due_requirement_ids:
            stages[0].due_requirement_ids.append(new_id)
        # One clinical variable, with separate source-backed due-node policies retained.
        for existing in component.evidence_requirements:
            if binding.predicate_id in existing.predicate_ids and existing.variable_id is not None:
                existing.variable_id = binding.variable_id
            else:
                existing.predicate_ids = [value for value in existing.predicate_ids if value != binding.predicate_id]
        for existing in result.evidence_requirement_drafts:
            if existing.draft_component_id == component_draft.draft_component_id:
                if (binding.predicate_id in existing.proposed_requirement.predicate_ids
                        and existing.proposed_requirement.variable_id is not None):
                    existing.proposed_requirement.variable_id = binding.variable_id
                else:
                    existing.proposed_requirement.predicate_ids = [value for value in existing.proposed_requirement.predicate_ids
                        if value != binding.predicate_id]
        component.evidence_requirements = [item for item in component.evidence_requirements
                                           if item.requirement_id != new_id] + [requirement]
        result.evidence_requirement_drafts = [item for item in result.evidence_requirement_drafts
                                              if item.proposed_requirement.requirement_id != new_id]
        result.evidence_requirement_drafts.append(EvidenceRequirementDraft(
            draft_requirement_id=new_id, draft_component_id=component_draft.draft_component_id,
            proposed_requirement=requirement, source_refs=list(template.source_refs)))
    for item in result.evidence_requirement_drafts:
        if item.procedure_catalog_item_id is not None:
            identifier = "procedure:" + item.procedure_catalog_item_id
            item.proposed_requirement.variable_id = identifier
            definitions[identifier] = VariableDef(variable_id=identifier,
                label_zh=item.proposed_requirement.description, value_type="procedure", domain="procedure")
    by_id = {item.proposed_component.rule_component_id: item.proposed_component for item in result.component_drafts}
    for rule in result.proposed_rules:
        rule.components = [by_id.get(item.rule_component_id, item) for item in rule.components]
    # Freeze the complete dictionary used by this revision for reproducible later consumption.
    result.variable_definitions = list(definitions.values())
    return type(draft).model_validate(result.model_dump(mode="json"))


def validated_variable_suggestions(draft, proposal):
    """Retain checked correspondences; one invalid condition does not erase its siblings."""
    load_dictionary([*(draft.variable_definitions or ()), *proposal.variables])
    groups = {}
    for binding in proposal.bindings:
        groups.setdefault((binding.component_id, binding.predicate_id), []).append(binding)
    accepted, issues = [], []
    for (component_id, predicate_id), bindings in groups.items():
        try:
            apply_variable_bindings(draft, VariableBindingProposal(variables=proposal.variables, bindings=bindings))
        except ValueError as exc:
            issues.append({"component_id": component_id, "predicate_id": predicate_id, "reason": str(exc)})
        else:
            accepted.extend(bindings)
    return VariableBindingProposal(variables=proposal.variables, bindings=accepted), issues


def validate_publication_bindings(draft):
    definitions = {item.variable_id: item for item in draft.variable_definitions or ()}
    missing = []
    for rule in draft.proposed_rules:
        for component in rule.components:
            for predicate in component_predicates(component):
                requirements = [item for item in component.evidence_requirements
                                if predicate.predicate_id in item.predicate_ids]
                if not requirements:
                    missing.append((rule.official_code, predicate.predicate_id))
                    continue
                identifiers = {item.variable_id for item in requirements}
                if len(identifiers) != 1 or None in identifiers:
                    raise ValueError("同一条件的数据项目不唯一或尚未选择")
                variable = definitions.get(next(iter(identifiers)))
                if variable is None:
                    raise ValueError("规则引用的数据项目没有保存定义")
                validate_variable_predicate(variable, predicate)
                if predicate.requires_professional_judgment and not any(
                    "investigator_assessment" in item.required_source_types for item in requirements
                ):
                    raise ValueError("研究者判断条件缺少书面判断来源要求")
    if missing:
        raise ValueError(f"仍有 {len(missing)} 个条件未选择数据项目")
