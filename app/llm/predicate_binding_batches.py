"""Complete, source-preserving prompt batches; no clinical relevance pruning."""

import json

from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash


class PredicateBindingBatch(ContractModel):
    frozen_input_sha256: str
    component_ids: list[str]
    fact_ids: list[str]
    locator_ids: list[str]
    batch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _batch(frozen, fact_ids, component_ids):
    facts = {fact.fact_id: fact for fact in frozen.facts}
    material = {
        "frozen_input_sha256": frozen.frozen_input_sha256,
        "component_ids": sorted(component_ids),
        "fact_ids": sorted(fact_ids),
        "locator_ids": sorted({locator for key in fact_ids for locator in facts[key].locator_ids}),
    }
    return PredicateBindingBatch(**material, batch_sha256=canonical_hash(material))


def validate_binding_batch(frozen: PredicateBindingFrozenInput, batch: PredicateBindingBatch):
    """Every selected component and fact retains its frozen identity and sources."""
    if (not batch.component_ids or len(batch.component_ids) != len(set(batch.component_ids))
            or not set(batch.component_ids) <= {c.rule_component_id for c in frozen.components}):
        raise ValueError("分批规则子项身份重复或超出冻结范围")
    if len(batch.fact_ids) != len(set(batch.fact_ids)) or not set(batch.fact_ids) <= {f.fact_id for f in frozen.facts}:
        raise ValueError("分批事实身份重复或超出冻结范围")
    if batch != _batch(frozen, batch.fact_ids, batch.component_ids):
        raise ValueError("分批来源或内容身份与冻结事实不一致")


def project_binding_batch(prompt_input: dict, frozen, batch):
    validate_binding_batch(frozen, batch)
    projected = dict(prompt_input)
    selected_components = set(batch.component_ids)
    projected["components"] = [
        component for component in prompt_input["components"]
        if component["rule_component_id"] in selected_components
    ]
    parent_ids = {component["parent_rule_id"] for component in projected["components"]}
    projected["rule_sources"] = {
        key: value for key, value in prompt_input["rule_sources"].items()
        if key in parent_ids
    }
    for name, key, selected in (("facts", "fact_id", batch.fact_ids), ("sources", "locator_id", batch.locator_ids)):
        table = prompt_input[name]
        index = table["columns"].index(key)
        selected = set(selected)
        projected[name] = {"columns": table["columns"], "rows": [row for row in table["rows"] if row[index] in selected]}
    projected["batch"] = batch.model_dump(mode="json")
    return projected


def plan_binding_batches(frozen, prompt_input: dict, *, max_characters: int):
    """Cover every component × fact pair with bounded, source-complete batches.

    Character admission is a reproducible packing limit, not a tokenizer claim.
    Model-specific input/output capacity must still be checked before calling.
    """
    if max_characters < 1:
        raise ValueError("分批长度必须为正数")
    locators = {locator.locator_id: locator for locator in frozen.locators}
    def order(fact):
        sources = [(locators[key].source_document_version_id, locators[key].page_number or 0, key) for key in fact.locator_ids]
        return (min(sources) if sources else ("", 0, ""), fact.fact_id)
    def size(batch):
        return len(json.dumps(project_binding_batch(prompt_input, frozen, batch), ensure_ascii=False, separators=(",", ":")))
    ordered_facts = sorted(frozen.facts, key=order)
    ordered_components = sorted(frozen.components, key=lambda item: item.rule_component_id)
    if not ordered_components:
        raise ValueError("冻结规则缺少可核对的子项")
    component_ids = [item.rule_component_id for item in ordered_components]

    def pack_width(width):
        batches = []
        for start in range(0, len(component_ids), width):
            components = component_ids[start:start + width]
            pending_facts = []
            for fact in ordered_facts:
                proposed = _batch(frozen, [*pending_facts, fact.fact_id], components)
                if pending_facts and size(proposed) > max_characters:
                    batches.append(_batch(frozen, pending_facts, components))
                    pending_facts = []
                    proposed = _batch(frozen, [fact.fact_id], components)
                if size(proposed) > max_characters:
                    return None
                pending_facts.append(fact.fact_id)
            if not ordered_facts and size(_batch(frozen, [], components)) > max_characters:
                return None
            batches.append(_batch(frozen, pending_facts, components))
        return tuple(batches)

    widths = {len(component_ids)}
    width = 1
    while width < len(component_ids):
        widths.update((width, min(len(component_ids), width + width // 2)))
        width *= 2
    widths.update((max(1, len(component_ids) // divisor) for divisor in (2, 3)))
    plans = [plan for width in sorted(widths) if (plan := pack_width(width)) is not None]
    if not plans:
        raise ValueError("单条规则子项及一条事实的完整来源超过分批长度，不能截断原文")
    return min(plans, key=lambda plan: (sum(size(batch) for batch in plan), len(plan)))
