"""Cross-batch definition scope uses frozen identities, not shared wording."""

import hashlib
from types import SimpleNamespace

import pytest

from app.agents.protocol_control_definition_scope import (
    DefinitionScopeChoice, DefinitionScopeReview, SCOPE_REVIEW_VERSION,
    build_definition_scope_prompt,
    validate_definition_scope_review,
)
from app.domain.contracts.protocol_controls import (
    ProtocolControlDefinitionAtomConsumption, ProtocolControlDefinitionConsumerRecord,
)
from app.domain.publication import canonical_hash
from app.services.protocol_control_definition_scope import (
    close_definition_scope, definition_scope_inputs,
)
from app.services import protocol_control_execution as execution

UNPROVEN = execution._DEFINITION_CONSUMER_SCOPE_UNPROVEN


def _record(consumers=()):
    return ProtocolControlDefinitionConsumerRecord(
        batch_id="method-batch", source_structure_unit_id="method-unit",
        source_statement_index=0, source_quote="根据两次独立采集计算均值",
        source_span_ids=["span:method"], consumers=list(consumers),
        scope_complete=False, unresolved_reasons=[UNPROVEN],
    )


def _candidate():
    atom = SimpleNamespace(source_excerpts=["筛选期应满足该均值要求"], continuing_obligation=None)
    expression = SimpleNamespace(groups=[SimpleNamespace(atoms=[atom])])
    semantics = SimpleNamespace(
        applicability_expression=None, trigger_expression=None,
        obligation_expression=expression, exception_expression=None,
        repeat_trigger_conditions=[],
    )
    return SimpleNamespace(control_candidate_id="candidate-other-batch",
                           source_span_ids=["span:control"], title="筛选期数值要求",
                           semantics=semantics)


def _basis(local=()):
    record = _record(local)
    outputs = {
        "method-batch": SimpleNamespace(candidates=[]),
        "other-batch": SimpleNamespace(candidates=[_candidate()]),
    }
    official = {"IN-01": {
        ("component-official", "predicate-official"):
        ("入选时该均值应达到方案规定的条件",),
    }}
    inventory, keyed = definition_scope_inputs([record], outputs, official)
    definition_key = canonical_hash([record.batch_id, record.source_structure_unit_id,
                                     record.source_statement_index])
    return record, inventory, keyed, definition_key


def _review(inventory, definition_key, consumer_keys, *, complete=True, unresolved=()):
    return DefinitionScopeReview(
        version=SCOPE_REVIEW_VERSION, inventory_sha256=inventory["sha256"],
        items=[DefinitionScopeChoice(
            definition_key=definition_key, consumer_keys=list(consumer_keys),
            complete=complete, unresolved_aspects=list(unresolved),
        )],
    )


def test_global_scope_closes_definition_to_other_batch_and_official_predicate():
    record, inventory, keyed, definition_key = _basis()
    assert len(inventory["consumers"]) == 2
    review = _review(inventory, definition_key, list(keyed))
    closed = close_definition_scope([record], review, inventory, keyed,
                                    scope_unproven_reason=UNPROVEN)
    assert closed[0].scope_complete is True
    assert closed[0].unresolved_reasons == []
    assert {item.consumer_kind for item in closed[0].consumers} == {
        "control_atom", "official_predicate",
    }
    assert {item.consumer_excerpt for item in closed[0].consumers} == {
        "筛选期应满足该均值要求", "入选时该均值应达到方案规定的条件",
    }


def test_scope_rejects_stale_inventory_and_unlisted_consumer():
    _, inventory, keyed, definition_key = _basis()
    with pytest.raises(ValueError, match="冻结来源清单"):
        validate_definition_scope_review(
            _review(inventory, definition_key, list(keyed)).model_copy(
                update={"inventory_sha256": "0" * 64}
            ), inventory,
        )
    with pytest.raises(ValueError, match="未冻结"):
        validate_definition_scope_review(
            _review(inventory, definition_key, ["made-up"]), inventory,
        )


def test_same_statement_index_in_distinct_source_units_keeps_distinct_identity():
    first = _record()
    second = first.model_copy(update={
        "source_structure_unit_id": "other-method-unit",
        "source_quote": "另一来源单元也有编号零的定义",
    })
    outputs = {"method-batch": SimpleNamespace(candidates=[])}
    inventory, _ = definition_scope_inputs([first, second], outputs, {})
    assert len({item["key"] for item in inventory["definitions"]}) == 2


def test_unresolved_or_disagreeing_global_scope_never_becomes_complete():
    record, inventory, keyed, definition_key = _basis()
    selected = next(key for key, value in keyed.items()
                    if value.consumer_kind == "official_predicate")
    closed = close_definition_scope(
        [record], _review(inventory, definition_key, [selected],
                          complete=False, unresolved=["另一章节的适用关系仍未核清"]),
        inventory, keyed, scope_unproven_reason=UNPROVEN,
    )
    assert closed[0].scope_complete is False
    assert "另一章节的适用关系仍未核清" in closed[0].unresolved_reasons

    local = [ProtocolControlDefinitionAtomConsumption(
        control_candidate_id="candidate-other-batch", layer="obligation",
        group_index=0, atom_index=0, consumer_excerpt="筛选期应满足该均值要求",
    )]
    record, inventory, keyed, definition_key = _basis(local)
    closed = close_definition_scope(
        [record], _review(inventory, definition_key, [selected]),
        inventory, keyed, scope_unproven_reason=UNPROVEN,
    )
    assert closed[0].scope_complete is False
    assert len(closed[0].consumers) == 2
    assert any("逐批登记与全量核对不一致" in reason for reason in closed[0].unresolved_reasons)


def test_untyped_local_question_cannot_be_promoted_to_complete_scope():
    record, inventory, keyed, definition_key = _basis()
    record = record.model_copy(update={
        "unresolved_reasons": [UNPROVEN, "均值是否采用两次独立采集仍待核对"],
    })
    closed = close_definition_scope(
        [record], _review(inventory, definition_key, list(keyed)),
        inventory, keyed, scope_unproven_reason=UNPROVEN,
    )
    assert closed[0].scope_complete is False
    assert "均值是否采用两次独立采集仍待核对" in closed[0].unresolved_reasons


def test_scope_checkpoint_cannot_be_rewritten_after_the_model_call(monkeypatch):
    record, inventory, keyed, definition_key = _basis()
    review = _review(inventory, definition_key, list(keyed))
    checkpoint = {
        "stage": execution.STEP_SCOPE,
        "inventory_sha256": inventory["sha256"],
        "prompt_sha256": hashlib.sha256(
            build_definition_scope_prompt(inventory).encode("utf-8")
        ).hexdigest(),
        "raw_output_sha256": "a" * 64,
        "session_id": "test-scope-session",
        "review": review.model_dump(mode="json"),
        "source_definition_consumers": [],
    }
    monkeypatch.setattr(execution, "_definition_scope_basis",
                        lambda context, config: ([record], inventory, keyed))
    monkeypatch.setattr(execution, "_checkpoint_for_step",
                        lambda context, step, config: checkpoint)
    with pytest.raises(Exception, match="已保存结果不一致"):
        execution._verified_definition_scope(SimpleNamespace(), SimpleNamespace())


def test_scope_step_preserves_model_receipt_and_revalidates_frozen_record(monkeypatch):
    record, inventory, keyed, definition_key = _basis()
    review = _review(inventory, definition_key, list(keyed))
    raw = review.model_dump_json()
    monkeypatch.setattr(execution, "_definition_scope_basis",
                        lambda context, config: ([record], inventory, keyed))
    monkeypatch.setattr(execution, "_resolve_transport", lambda config, stage: SimpleNamespace(
        start_definition_scope=lambda prompt: SimpleNamespace(
            session_id="test-scope-session", text=raw,
        ),
    ))
    monkeypatch.setattr(execution, "_require_frozen_route", lambda *args, **kwargs: None)
    context = SimpleNamespace(job_payload={})
    saved = execution._execute_definition_scope(context, SimpleNamespace())
    assert saved["prompt_sha256"] == hashlib.sha256(
        build_definition_scope_prompt(inventory).encode("utf-8")
    ).hexdigest()
    assert saved["raw_output_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    monkeypatch.setattr(execution, "_checkpoint_for_step",
                        lambda context, step, config: saved)
    assert execution._verified_definition_scope(context, SimpleNamespace())[0].scope_complete
