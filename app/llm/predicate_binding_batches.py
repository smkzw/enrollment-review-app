"""Complete, source-preserving prompt batches; no clinical relevance pruning."""

import json

from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash


class PredicateBindingBatch(ContractModel):
    frozen_input_sha256: str
    fact_ids: list[str]
    locator_ids: list[str]
    batch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _batch(frozen, fact_ids):
    facts = {fact.fact_id: fact for fact in frozen.facts}
    material = {
        "frozen_input_sha256": frozen.frozen_input_sha256,
        "fact_ids": sorted(fact_ids),
        "locator_ids": sorted({locator for key in fact_ids for locator in facts[key].locator_ids}),
    }
    return PredicateBindingBatch(**material, batch_sha256=canonical_hash(material))


def validate_binding_batch(frozen: PredicateBindingFrozenInput, batch: PredicateBindingBatch):
    """Every selected fact retains all its original locators, not a chosen subset."""
    if len(batch.fact_ids) != len(set(batch.fact_ids)) or not set(batch.fact_ids) <= {f.fact_id for f in frozen.facts}:
        raise ValueError("分批事实身份重复或超出冻结范围")
    if batch != _batch(frozen, batch.fact_ids):
        raise ValueError("分批来源或内容身份与冻结事实不一致")


def project_binding_batch(prompt_input: dict, frozen, batch):
    validate_binding_batch(frozen, batch)
    projected = dict(prompt_input)
    for name, key, selected in (("facts", "fact_id", batch.fact_ids), ("sources", "locator_id", batch.locator_ids)):
        table = prompt_input[name]
        index = table["columns"].index(key)
        selected = set(selected)
        projected[name] = {"columns": table["columns"], "rows": [row for row in table["rows"] if row[index] in selected]}
    projected["batch"] = batch.model_dump(mode="json")
    return projected


def plan_binding_batches(frozen, prompt_input: dict, *, max_characters: int):
    """Pack in document/page order without deleting any fact or source excerpt.

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
    batches, pending = [], []
    for fact in sorted(frozen.facts, key=order):
        proposed = _batch(frozen, [*pending, fact.fact_id])
        if size(proposed) > max_characters and pending:
            batches.append(_batch(frozen, pending))
            pending = []
            proposed = _batch(frozen, [fact.fact_id])
        if size(proposed) > max_characters:
            raise ValueError("单条事实及其完整来源超过分批长度，不能截断原文")
        pending.append(fact.fact_id)
    if pending or not batches:
        batch = _batch(frozen, pending)
        if size(batch) > max_characters:
            raise ValueError("完整审核条件超过分批长度，不能截断规则")
        batches.append(batch)
    return tuple(batches)
