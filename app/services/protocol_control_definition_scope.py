"""Close source-definition consumers over the frozen complete deep-plan inventory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.agents.protocol_control_definition_scope import (
    DefinitionScopeReview, frozen_scope_inventory, validate_definition_scope_review,
)
from app.agents.protocol_control_source_interpretation import definition_consumer_candidate_atoms
from app.domain.contracts.protocol_controls import (
    ProtocolControlBatchDispositionHydrated, ProtocolControlDefinitionAtomConsumption,
    ProtocolControlDefinitionConsumerRecord,
)
from app.domain.publication import canonical_hash


def definition_scope_inputs(
    records: Sequence[ProtocolControlDefinitionConsumerRecord],
    outputs: Mapping[str, ProtocolControlBatchDispositionHydrated],
    official_sources: Mapping[str, Mapping[tuple[str, str], Sequence[str]]],
) -> tuple[dict[str, object], dict[str, ProtocolControlDefinitionAtomConsumption]]:
    """Build one exhaustive inventory from completed batches and frozen draft predicates."""
    definitions = [{
        "key": canonical_hash([record.batch_id, record.source_structure_unit_id,
                               record.source_statement_index]),
        "batch_id": record.batch_id,
        "statement_index": record.source_statement_index,
        "structure_unit_id": record.source_structure_unit_id,
        "source_quote": record.source_quote,
        "source_span_ids": list(record.source_span_ids),
    } for record in records]
    if len({item["key"] for item in definitions}) != len(definitions):
        raise ValueError("冻结计算定义身份重复")
    consumers: list[dict[str, object]] = []
    keyed: dict[str, ProtocolControlDefinitionAtomConsumption] = {}

    def add(entry: ProtocolControlDefinitionAtomConsumption, excerpts: Sequence[str], **context) -> None:
        clauses = [part for part in excerpts if part.strip()]
        if not clauses:
            return
        key = canonical_hash(list(entry.key))
        if key in keyed:
            raise ValueError("冻结消费者身份重复")
        keyed[key] = entry
        consumers.append({"key": key, "kind": entry.consumer_kind,
                          "source_excerpts": clauses, **context})

    for batch_id, output in sorted(outputs.items()):
        for candidate in output.candidates:
            for atom in definition_consumer_candidate_atoms(candidate):
                excerpts = atom["excerpts"]
                if not excerpts:
                    continue
                entry = ProtocolControlDefinitionAtomConsumption(
                    control_candidate_id=candidate.control_candidate_id,
                    layer=atom["layer"], condition_id=atom["condition_id"],
                    group_index=atom["group_index"], atom_index=atom["atom_index"],
                    consumer_excerpt=excerpts[0],
                )
                add(entry, excerpts, batch_id=batch_id,
                    candidate_id=candidate.control_candidate_id,
                    source_span_ids=list(candidate.source_span_ids),
                    title=candidate.title)
    for code, predicates in sorted(official_sources.items()):
        for (component_id, predicate_id), excerpts in sorted(predicates.items()):
            if not excerpts:
                continue
            entry = ProtocolControlDefinitionAtomConsumption(
                consumer_kind="official_predicate",
                rule_component_id=component_id, predicate_id=predicate_id,
                consumer_excerpt=excerpts[0],
            )
            add(entry, excerpts, official_code=code,
                rule_component_id=component_id, predicate_id=predicate_id)
    return frozen_scope_inventory(definitions, consumers), keyed


def close_definition_scope(
    records: Sequence[ProtocolControlDefinitionConsumerRecord],
    review: DefinitionScopeReview,
    inventory: Mapping[str, object],
    keyed_consumers: Mapping[str, ProtocolControlDefinitionAtomConsumption],
    *, scope_unproven_reason: str,
) -> list[ProtocolControlDefinitionConsumerRecord]:
    validate_definition_scope_review(review, inventory)
    choices = {item.definition_key: item for item in review.items}
    by_identity = {tuple(consumer.key): key for key, consumer in keyed_consumers.items()}
    closed = []
    for record in records:
        definition_key = canonical_hash([record.batch_id, record.source_structure_unit_id,
                                         record.source_statement_index])
        choice = choices[definition_key]
        local_keys = {by_identity.get(tuple(item.key)) for item in record.consumers}
        if None in local_keys:
            raise ValueError("批次内消费身份不属于冻结全量清单")
        selected = set(choice.consumer_keys) | local_keys
        reasons = set(record.unresolved_reasons) - {scope_unproven_reason}
        reasons.update(choice.unresolved_aspects)
        local_disagreement = not set(choice.consumer_keys) >= local_keys
        if local_disagreement:
            reasons.add("逐批登记与全量核对不一致，需重新核对影响范围")
        # Local unresolved text is not typed yet: it may itself question the
        # affected scope. Do not promote it to a complete scope by model vote.
        complete = choice.complete and bool(selected) and not reasons
        if not complete:
            reasons.add(scope_unproven_reason)
        closed.append(record.model_copy(update={
            "consumers": [keyed_consumers[key] for key in sorted(selected)],
            "scope_complete": complete,
            "unresolved_reasons": sorted(reasons),
        }))
    return [ProtocolControlDefinitionConsumerRecord.model_validate(
        item.model_dump(mode="json"),
    ) for item in closed]
