"""Focused checks for the R1 source-definition → consumer chain.

These tests pin the corrected fail-closed foundation: the relation carries two
independent source anchors (the definition quote on the record and the
consumer's own excerpt), covers both a control atom and an official predicate,
and no completeness or release is claimed while the consumer scope including
other batches remains unproven.
"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.protocol_control_source_interpretation import (
    SOURCE_DEFINITION_CONSUMER_VERSION,
    SourceDefinitionAtomConsumer,
    SourceDefinitionConsumerItem,
    SourceDefinitionConsumers,
    SourceTargetReviewValidationError,
    normalize_source_excerpt,
    validate_source_definition_consumers,
    build_source_definition_consumers_prompt,
)
from app.domain.contracts.protocol_controls import (
    ProtocolControlDefinitionAtomConsumption,
    ProtocolControlDefinitionConsumerRecord,
    PublishedProtocolControlCatalog,
)
from app.domain.contracts.control_catalog_publication import ControlCatalogPublication
from app.domain.contracts.enums import StudyPhase
from app.domain.publication import canonical_hash
from app.services import frozen_review_calculation as calculation_module
from app.services import protocol_control_catalog_publication as publication_module
from app.services import protocol_control_execution as execution_module
from app.storage.repositories import ScopeViolationError
from app.workflow.errors import StepFailure

# The definition lives in a calculation/method chapter; the consumer is
# excerpted from an eligibility/visit chapter. Neither anchor contains the other.
DEFINITION_QUOTE = "体质指数（BMI）＝体重（kg）÷身高²（m²）"
CONSUMER_EXCERPT = "筛选期访视1必须记录体重与身高"
FOREIGN_EXCERPT = "给药前必须完成生命体征测量"
RELATION_NOTE = "筛选期体重与身高用于按该方法计算BMI"
OFFICIAL_CODE = "IN-01"
OFFICIAL_EXCERPT = "筛选期访视1必须记录体重与身高并计算体质指数"
RULE_COMPONENT_ID = "component-in-01"
PREDICATE_ID = "predicate-in-01"


def _definition_statement(
    *,
    decision_functions: list[str] | None = None,
    unresolved: list[str] | None = None,
    unit_id: str = "su-method",
) -> SimpleNamespace:
    return SimpleNamespace(
        structure_unit_id=unit_id,
        quoted_text=DEFINITION_QUOTE,
        decision_functions=decision_functions or ["definition", "calculation_input"],
        unresolved=list(unresolved or []),
    )


def _unit(
    unit_id: str = "su-method",
    *,
    spans: tuple[str, ...] = ("span:method",),
    excerpt: str = DEFINITION_QUOTE,
    heading_path: tuple[str, ...] = ("5.2 计算方法",),
) -> SimpleNamespace:
    return SimpleNamespace(
        structure_unit_id=unit_id,
        source_span_ids=list(spans),
        excerpt=excerpt,
        heading_path=list(heading_path),
    )


def _dnf(*excerpt_lists: list[str]) -> SimpleNamespace:
    return SimpleNamespace(groups=[
        SimpleNamespace(atoms=[
            SimpleNamespace(source_excerpts=list(excerpts), continuing_obligation=None)
            for excerpts in excerpt_lists
        ]),
    ])


def _candidate(candidate_id: str, obligation: SimpleNamespace | None) -> SimpleNamespace:
    return SimpleNamespace(
        control_candidate_id=candidate_id,
        semantics=SimpleNamespace(
            applicability_expression=None,
            trigger_expression=None,
            obligation_expression=obligation,
            exception_expression=None,
            repeat_trigger_conditions=[],
        ),
    )


def _declaration(
    *,
    statement_index: int = 0,
    consumer_excerpt: str = CONSUMER_EXCERPT,
    atom_index: int = 0,
    candidate_index: int = 0,
    relation_note: str | None = RELATION_NOTE,
) -> SourceDefinitionConsumers:
    return SourceDefinitionConsumers(
        version=SOURCE_DEFINITION_CONSUMER_VERSION,
        items=[SourceDefinitionConsumerItem(
            statement_index=statement_index,
            consumers=[SourceDefinitionAtomConsumer(
                candidate_index=candidate_index,
                layer="obligation",
                group_index=0,
                atom_index=atom_index,
                consumer_excerpt=consumer_excerpt,
                relation_note=relation_note,
            )],
        )],
    )


def _official_declaration(
    *,
    statement_index: int = 0,
    official_code: str = OFFICIAL_CODE,
    predicate_id: str = PREDICATE_ID,
    consumer_excerpt: str = OFFICIAL_EXCERPT,
    relation_note: str | None = RELATION_NOTE,
) -> SourceDefinitionConsumers:
    return SourceDefinitionConsumers(
        version=SOURCE_DEFINITION_CONSUMER_VERSION,
        items=[SourceDefinitionConsumerItem(
            statement_index=statement_index,
            consumers=[SourceDefinitionAtomConsumer(
                consumer_kind="official_predicate",
                official_code=official_code,
                rule_component_id=RULE_COMPONENT_ID,
                predicate_id=predicate_id,
                consumer_excerpt=consumer_excerpt,
                relation_note=relation_note,
            )],
        )],
    )


def _official_target(
    *,
    official_code: str = OFFICIAL_CODE,
    excerpts: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        official_code=official_code,
        source_span_ids=["span-official"],
        source_excerpts=list(excerpts if excerpts is not None else [OFFICIAL_EXCERPT]),
    )


def _batch(
    unit: SimpleNamespace | None = None,
    *,
    official_targets: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        batch_id="batch-a",
        batch_number=1,
        owned_units=[unit or _unit()],
        context_units=[],
        known_official_targets=list(official_targets or []),
        known_procedure_targets=[],
    )


def _plan(*batches: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(batches=list(batches) if batches else [_batch()])


def _run(
    statement: SimpleNamespace,
    *,
    declarations: SourceDefinitionConsumers | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        source_interpretation=SimpleNamespace(statements=[statement]),
        source_target_review=SimpleNamespace(items=[]),
        source_definition_consumers=declarations,
    )


def _assemble(
    statement: SimpleNamespace | None = None,
    declarations: SourceDefinitionConsumers | None = None,
    candidate: SimpleNamespace | None = None,
    official_targets: list[SimpleNamespace] | None = None,
) -> list[ProtocolControlDefinitionConsumerRecord]:
    batch = _batch(official_targets=official_targets)
    return execution_module._source_definition_consumers(
        _plan(batch),
        {batch.batch_id: SimpleNamespace(candidates=[candidate if candidate is not None else _candidate(
            "pcc-consumer", _dnf([CONSUMER_EXCERPT]),
        )])},
        {batch.batch_id: _run(statement or _definition_statement(), declarations=declarations)},
    )


def test_deep_step_uses_frozen_draft_predicate_identity_and_source(monkeypatch) -> None:
    predicate = SimpleNamespace(
        predicate_id=PREDICATE_ID,
        exact_source_clauses=[OFFICIAL_EXCERPT],
    )
    component = SimpleNamespace(
        rule_component_id=RULE_COMPONENT_ID,
        expression=SimpleNamespace(kind="predicate", predicate=predicate),
        exception_expression=None,
        repeat_trigger_conditions=[],
    )
    revision = SimpleNamespace(
        content_sha256="a" * 64,
        project_id="study-a",
        protocol_version_id="protocol-a",
        study_phase="phase-3",
        content=SimpleNamespace(proposed_rules=[SimpleNamespace(
            official_code=OFFICIAL_CODE, components=[component],
        )]),
    )
    monkeypatch.setattr(
        execution_module.ProtocolDraftRevisionRepository, "get",
        lambda self, revision_id: revision,
    )
    config = SimpleNamespace(session_factory=lambda: nullcontext(object()))
    payload = {
        "draft_revision_id": "revision-a",
        "draft_content_sha256": "a" * 64,
        "source_input": {
            "project_id": "study-a", "protocol_version_id": "protocol-a",
            "selected_phase": "phase-3",
        },
    }
    official_target = _official_target()
    official_target.label = "入选条件一"
    batch = _batch(official_targets=[official_target])
    identities, sources = execution_module._frozen_official_predicates(
        config, payload, batch,
    )
    assert identities == {OFFICIAL_CODE: [(RULE_COMPONENT_ID, PREDICATE_ID)]}
    assert sources[OFFICIAL_CODE][RULE_COMPONENT_ID, PREDICATE_ID] == (OFFICIAL_EXCERPT,)

    statement = SimpleNamespace(
        structure_unit_id="su-method", quoted_text=DEFINITION_QUOTE,
        scope_quote=None, force="required", decision_functions=["calculation_input"],
        unresolved=[],
    )
    candidate = _candidate("pcc-consumer", _dnf([CONSUMER_EXCERPT]))
    candidate.semantics.title = "访视检查"
    prompt = build_source_definition_consumers_prompt(
        batch, SimpleNamespace(statements=[statement]),
        SimpleNamespace(candidates=[candidate]),
        official_predicate_identities=identities,
        official_predicate_sources=sources,
    )
    assert RULE_COMPONENT_ID in prompt and PREDICATE_ID in prompt
    assert OFFICIAL_EXCERPT in prompt

    with pytest.raises(StepFailure, match="冻结来源不一致"):
        execution_module._frozen_official_predicates(
            config, {**payload, "draft_content_sha256": "b" * 64}, batch,
        )


def test_deep_reuse_identity_changes_with_draft_revision() -> None:
    original = execution_module._deep_component_identity({
        "draft_revision_id": "revision-a", "draft_content_sha256": "a" * 64,
    }, "冻结提示")
    changed = execution_module._deep_component_identity({
        "draft_revision_id": "revision-b", "draft_content_sha256": "b" * 64,
    }, "冻结提示")
    assert original["schema_version"] == "phase5/deep-component-identity/v3"
    assert original != changed


# -- declaration validation -------------------------------------------------


def test_official_declaration_requires_a_known_official_target() -> None:
    # The declared code must be one of this batch's frozen official targets; a
    # parent code alone never selects a consumer.
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_definition_consumers(
            _batch(), SimpleNamespace(statements=[_definition_statement()]),
            _official_declaration(),
        )
    assert error.value.code == "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID"
    validate_source_definition_consumers(
        _batch(official_targets=[_official_target()]),
        SimpleNamespace(statements=[_definition_statement()]),
        _official_declaration(),
    )


def test_official_declaration_shape_is_exclusive() -> None:
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            consumer_kind="official_predicate", official_code=OFFICIAL_CODE,
            rule_component_id=RULE_COMPONENT_ID, predicate_id=PREDICATE_ID,
            candidate_index=0, consumer_excerpt=OFFICIAL_EXCERPT,
        )
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            consumer_kind="official_predicate", official_code=OFFICIAL_CODE,
            consumer_excerpt=OFFICIAL_EXCERPT,
        )
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            consumer_kind="official_predicate", official_code=OFFICIAL_CODE,
            rule_component_id=RULE_COMPONENT_ID, predicate_id=PREDICATE_ID,
            consumer_excerpt=OFFICIAL_EXCERPT, condition_id="repeat-1",
        )
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            candidate_index=0, layer="obligation", group_index=0, atom_index=0,
            predicate_id=PREDICATE_ID, consumer_excerpt=CONSUMER_EXCERPT,
        )


def test_official_declaration_version_is_bound() -> None:
    with pytest.raises(ValidationError):
        SourceDefinitionConsumers(
            version="phase5/control-source-definition-consumer/v1",
            items=[SourceDefinitionConsumerItem(
                statement_index=0, consumers=[SourceDefinitionAtomConsumer(
                    candidate_index=0, layer="obligation", group_index=0, atom_index=0,
                    consumer_excerpt=CONSUMER_EXCERPT,
                )],
            )],
        )


def test_declaration_requires_a_calculation_definition() -> None:
    batch = _batch()
    validate_source_definition_consumers(
        batch, SimpleNamespace(statements=[_definition_statement()]), _declaration(),
    )
    with pytest.raises(SourceTargetReviewValidationError) as error:
        validate_source_definition_consumers(
            batch,
            SimpleNamespace(statements=[_definition_statement(decision_functions=["action"])]),
            _declaration(),
        )
    assert error.value.code == "SOURCE_DEFINITION_CONSUMER_SCOPE_INVALID"


def test_declaration_accepts_a_cross_chapter_consumer_excerpt() -> None:
    # The consumer anchor lives in another chapter and never carries the
    # definition text; the statement-side check must not require that overlap.
    assert normalize_source_excerpt(DEFINITION_QUOTE) not in normalize_source_excerpt(CONSUMER_EXCERPT)
    validate_source_definition_consumers(
        _batch(), SimpleNamespace(statements=[_definition_statement()]), _declaration(),
    )


def test_declaration_condition_reference_rules() -> None:
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            candidate_index=0, layer="obligation", group_index=0, atom_index=0,
            condition_id="repeat-1", consumer_excerpt=CONSUMER_EXCERPT,
        )
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            candidate_index=0, layer="repeat_trigger", group_index=0, atom_index=0,
            consumer_excerpt=CONSUMER_EXCERPT,
        )
    with pytest.raises(ValidationError):
        SourceDefinitionAtomConsumer(
            candidate_index=0, layer="obligation", group_index=0, atom_index=0,
            consumer_excerpt="   ",
        )


# -- deterministic closure --------------------------------------------------


def test_cross_chapter_consumer_closes_to_the_frozen_candidate_atom() -> None:
    records = _assemble(declarations=_declaration())
    assert len(records) == 1
    record = records[0]
    assert [consumer.control_candidate_id for consumer in record.consumers] == ["pcc-consumer"]
    consumer = record.consumers[0]
    assert (consumer.layer, consumer.group_index, consumer.atom_index) == ("obligation", 0, 0)
    assert consumer.consumer_excerpt == CONSUMER_EXCERPT
    assert consumer.relation_note == RELATION_NOTE
    assert record.source_quote == DEFINITION_QUOTE
    # Two independent anchors: neither side proves the other.
    assert normalize_source_excerpt(DEFINITION_QUOTE) not in normalize_source_excerpt(CONSUMER_EXCERPT)
    assert normalize_source_excerpt(CONSUMER_EXCERPT) not in normalize_source_excerpt(DEFINITION_QUOTE)
    # Completeness of the consumer scope stays unproven in this slice.
    assert record.scope_complete is False
    assert execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN in record.unresolved_reasons


def test_consumer_excerpt_foreign_to_the_atom_is_rejected() -> None:
    with pytest.raises(StepFailure) as error:
        _assemble(declarations=_declaration(consumer_excerpt=FOREIGN_EXCERPT))
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_UNGROUNDED"


def test_same_wording_without_declaration_is_never_complete() -> None:
    record = _assemble(
        declarations=None,
        candidate=_candidate("pcc-consumer", _dnf([DEFINITION_QUOTE])),
    )[0]
    assert record.consumers == []
    assert record.scope_complete is False
    assert execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN in record.unresolved_reasons


def test_unresolved_aspects_are_recorded_without_scope_claim() -> None:
    batch = _batch()
    records = execution_module._source_definition_consumers(
        _plan(batch),
        {batch.batch_id: SimpleNamespace(candidates=[_candidate("pcc-consumer", _dnf([CONSUMER_EXCERPT]))])},
        {batch.batch_id: _run(_definition_statement(unresolved=["定义来源待核"]), declarations=_declaration())},
    )
    assert records[0].scope_complete is False
    assert "定义来源待核" in records[0].unresolved_reasons
    assert execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN in records[0].unresolved_reasons


def test_proven_post_eligibility_calculation_does_not_require_current_consumers() -> None:
    batch = _batch()
    statement = _definition_statement(decision_functions=["action", "calculation_input"])
    statement.eligibility_sequence = "after_eligibility_decision"
    run = _run(statement, declarations=None)
    run.source_target_review.items = [SimpleNamespace(
        statement_index=0, decision="not_current_control", unresolved_aspects=[],
    )]
    records = execution_module._source_definition_consumers(
        _plan(batch), {batch.batch_id: SimpleNamespace(candidates=[])},
        {batch.batch_id: run},
    )
    assert records == []


def test_missing_atom_or_candidate_is_rejected() -> None:
    with pytest.raises(StepFailure) as error:
        _assemble(declarations=_declaration(atom_index=3))
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"
    with pytest.raises(StepFailure) as error:
        _assemble(declarations=_declaration(candidate_index=2))
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"


def test_stray_declaration_for_an_action_statement_is_rejected() -> None:
    with pytest.raises(StepFailure) as error:
        _assemble(
            statement=_definition_statement(decision_functions=["action"]),
            declarations=_declaration(),
        )
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"


def test_record_model_rejects_an_unproven_complete_claim() -> None:
    with pytest.raises(ValidationError):
        ProtocolControlDefinitionConsumerRecord(
            batch_id="batch-a", source_structure_unit_id="su-method",
            source_statement_index=0, source_quote=DEFINITION_QUOTE,
            source_span_ids=["span:method"], consumers=[], scope_complete=True,
        )
    duplicate = ProtocolControlDefinitionAtomConsumption(
        control_candidate_id="pcc-consumer", layer="obligation",
        group_index=0, atom_index=0, consumer_excerpt=CONSUMER_EXCERPT,
    )
    with pytest.raises(ValidationError):
        ProtocolControlDefinitionConsumerRecord(
            batch_id="batch-a", source_structure_unit_id="su-method",
            source_statement_index=0, source_quote=DEFINITION_QUOTE,
            source_span_ids=["span:method"], consumers=[duplicate, duplicate],
            scope_complete=False,
        )


# -- frozen-checkpoint behaviour -------------------------------------------


def _frozen_record() -> ProtocolControlDefinitionConsumerRecord:
    return ProtocolControlDefinitionConsumerRecord(
        batch_id="batch-a", source_structure_unit_id="su-method",
        source_statement_index=0, source_quote=DEFINITION_QUOTE,
        source_span_ids=["span:method"],
        consumers=[ProtocolControlDefinitionAtomConsumption(
            control_candidate_id="pcc-consumer", layer="obligation",
            group_index=0, atom_index=0, consumer_excerpt=CONSUMER_EXCERPT,
            relation_note=RELATION_NOTE,
        )],
        scope_complete=False,
        unresolved_reasons=[execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN],
    )


def test_old_hydrate_checkpoint_cannot_acquire_the_relation() -> None:
    record = _frozen_record()
    with pytest.raises(StepFailure) as error:
        execution_module._require_definition_consumer_checkpoint_match(
            {"stage": "hydrate"}, [record],
        )
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"
    execution_module._require_definition_consumer_checkpoint_match(
        {"source_definition_consumers": [record.model_dump(mode="json")]}, [record],
    )


# -- publication re-verification -------------------------------------------


def _publication_inputs(
    record: ProtocolControlDefinitionConsumerRecord,
    *,
    candidate_id: str = "pcc-consumer",
    include_candidate: bool = True,
    unit: SimpleNamespace | None = None,
    atom_excerpts: list[str] | None = None,
    rule_set: SimpleNamespace | None = None,
) -> tuple[dict[str, object], SimpleNamespace, list[SimpleNamespace], SimpleNamespace, SimpleNamespace]:
    source_unit = unit or _unit()
    candidate = _candidate(candidate_id, _dnf(atom_excerpts or [CONSUMER_EXCERPT]))
    result: dict[str, object] = {
        "source_definition_consumers": [record.model_dump(mode="json")],
    }
    plan = SimpleNamespace(batches=[SimpleNamespace(batch_id="batch-a")])
    batches = [SimpleNamespace(candidates=[candidate] if include_candidate else [])]
    coverage = SimpleNamespace(units=[source_unit])
    return result, plan, batches, coverage, rule_set if rule_set is not None else _rule_set()


def test_publication_reverifies_a_cross_chapter_record() -> None:
    publication_module._require_valid_source_definition_consumers(
        *_publication_inputs(_frozen_record())
    )


def test_publication_rejects_a_foreign_consumer_excerpt() -> None:
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(_frozen_record(), atom_excerpts=[FOREIGN_EXCERPT])
        )


def test_publication_rejects_a_dangling_consumer_candidate() -> None:
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(_frozen_record(), include_candidate=False)
        )


def test_publication_rejects_a_definition_span_mismatch() -> None:
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(_frozen_record(), unit=_unit(spans=("span:other",)))
        )


def test_publication_absence_of_records_is_not_evidence() -> None:
    # A pre-contract job carries no records; re-verification accepts the empty
    # set without inventing a relation, so the calculation block still applies.
    plan = SimpleNamespace(batches=[SimpleNamespace(batch_id="batch-a")])
    publication_module._require_valid_source_definition_consumers(
        {"stage": "gate"}, plan, [], SimpleNamespace(units=[]), _rule_set(),
    )
    assert publication_module._released_definition_keys(
        publication_module._require_valid_source_definition_consumers(
            {"stage": "gate"}, plan, [], SimpleNamespace(units=[]), _rule_set(),
        ),
        SimpleNamespace(batches=[SimpleNamespace(batch_id="batch-a", batch_number=1)]),
    ) == frozenset()


# -- official predicate consumers -------------------------------------------


def _rule_set(
    *,
    predicate_id: str = PREDICATE_ID,
    component_id: str = RULE_COMPONENT_ID,
    clauses: list[str] | None = None,
) -> SimpleNamespace:
    predicate = SimpleNamespace(
        predicate_id=predicate_id,
        exact_source_clauses=list(clauses if clauses is not None else [OFFICIAL_EXCERPT]),
    )
    return SimpleNamespace(rules=[SimpleNamespace(components=[SimpleNamespace(
        rule_component_id=component_id,
        expression=SimpleNamespace(kind="predicate", predicate=predicate),
        exception_expression=None,
        repeat_trigger_conditions=[],
    )])])


def _official_frozen_record(
    *,
    predicate_id: str = PREDICATE_ID,
    component_id: str = RULE_COMPONENT_ID,
    consumer_excerpt: str = OFFICIAL_EXCERPT,
) -> ProtocolControlDefinitionConsumerRecord:
    return ProtocolControlDefinitionConsumerRecord(
        batch_id="batch-a", source_structure_unit_id="su-method",
        source_statement_index=0, source_quote=DEFINITION_QUOTE,
        source_span_ids=["span:method"],
        consumers=[ProtocolControlDefinitionAtomConsumption(
            consumer_kind="official_predicate",
            rule_component_id=component_id, predicate_id=predicate_id,
            consumer_excerpt=consumer_excerpt, relation_note=RELATION_NOTE,
        )],
        scope_complete=False,
        unresolved_reasons=[execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN],
    )


def test_official_consumer_closes_to_the_frozen_official_target() -> None:
    records = _assemble(
        declarations=_official_declaration(),
        official_targets=[_official_target()],
    )
    assert len(records) == 1
    consumer = records[0].consumers[0]
    assert consumer.consumer_kind == "official_predicate"
    assert (consumer.rule_component_id, consumer.predicate_id) == (
        RULE_COMPONENT_ID, PREDICATE_ID,
    )
    assert consumer.control_candidate_id is None
    assert consumer.consumer_excerpt == OFFICIAL_EXCERPT
    # The parent code is transport, not the stored consumer identity.
    assert "official_code" not in consumer.model_dump(mode="json")
    assert records[0].scope_complete is False
    assert execution_module._DEFINITION_CONSUMER_SCOPE_UNPROVEN in records[0].unresolved_reasons


def test_official_consumer_excerpt_foreign_to_the_target_is_rejected() -> None:
    with pytest.raises(StepFailure) as error:
        _assemble(
            declarations=_official_declaration(consumer_excerpt=FOREIGN_EXCERPT),
            official_targets=[_official_target()],
        )
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_UNGROUNDED"


def test_official_consumer_without_a_frozen_target_is_rejected() -> None:
    with pytest.raises(StepFailure) as error:
        _assemble(declarations=_official_declaration(), official_targets=[])
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"


def test_publication_reverifies_the_official_predicate_identity() -> None:
    publication_module._require_valid_source_definition_consumers(
        *_publication_inputs(_official_frozen_record())
    )


def test_publication_rejects_an_unbound_official_predicate() -> None:
    # Equal wording and the same parent code never substitute for the frozen
    # identity of the official predicate.
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(_official_frozen_record(predicate_id="predicate-other"))
        )
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(_official_frozen_record(component_id="component-other"))
        )


def test_publication_rejects_a_foreign_official_excerpt() -> None:
    with pytest.raises(ScopeViolationError):
        publication_module._require_valid_source_definition_consumers(
            *_publication_inputs(
                _official_frozen_record(),
                rule_set=_rule_set(clauses=[CONSUMER_EXCERPT]),
            )
        )


# -- working-draft consumption ----------------------------------------------


def _pack(
    *,
    clauses: list[str] | None = None,
    control_publication: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        clauses=[SimpleNamespace(rule_component_id=item)
                 for item in (clauses if clauses is not None else [RULE_COMPONENT_ID])],
        restricted_clauses=[],
        control_publication=control_publication,
    )


def test_work_draft_consumes_only_the_affected_consumers() -> None:
    predicate_unverified, control_unverified, consumed = (
        calculation_module._definition_consumer_consumption(
            _pack(), _rule_set(), [_official_frozen_record()],
        )
    )
    assert predicate_unverified == {RULE_COMPONENT_ID: frozenset({PREDICATE_ID})}
    assert control_unverified == {}
    assert [(item.batch_id, item.source_statement_index) for item in consumed] == [("batch-a", 0)]
    assert consumed[0].predicate_ids == ((RULE_COMPONENT_ID, PREDICATE_ID),)
    # An unrelated component is never touched, so its status stays evidence-based.
    assert set(predicate_unverified) == {RULE_COMPONENT_ID}


def test_work_draft_rejects_an_unresolvable_consumer() -> None:
    with pytest.raises(ValueError):
        calculation_module._definition_consumer_consumption(
            _pack(), _rule_set(), [_official_frozen_record(predicate_id="predicate-other")],
        )
    with pytest.raises(ValueError):
        calculation_module._definition_consumer_consumption(
            _pack(clauses=["component-other"]), _rule_set(), [_official_frozen_record()],
        )
    with pytest.raises(ValueError):
        calculation_module._definition_consumer_consumption(
            _pack(control_publication=None), _rule_set(),
            [_frozen_record()],
        )


def test_work_draft_without_records_changes_nothing() -> None:
    assert calculation_module._definition_consumer_consumption(
        _pack(), _rule_set(), None,
    ) == ({}, {}, ())


def test_derived_control_truth_cannot_override_an_unverified_definition() -> None:
    evaluated = {"affected": object(), "independent": object()}
    retained = calculation_module._eligible_control_calculations(
        evaluated, {"affected": (calculation_module.DEFINITION_CONSUMER_UNVERIFIED_REASON,)},
    )
    assert set(retained) == {"independent"}
    assert evaluated["affected"] is not retained["independent"]


def test_unproven_definition_withholds_only_its_predicate_and_derived_result() -> None:
    choices = {"component": {"affected": ["fact-a"], "sibling": ["fact-b"]}}
    propositions = {"component": {"affected": object(), "sibling": object()}}
    repeats = {}
    frequencies = {"component": {"sibling": object()}}
    unverified = {}
    calculation_module._withhold_unverified_definition_predicates(
        choices, (propositions, repeats, frequencies), unverified,
        {"component": frozenset({"affected"})},
    )
    assert choices == {"component": {"affected": [], "sibling": ["fact-b"]}}
    assert set(propositions["component"]) == {"sibling"}
    assert set(frequencies["component"]) == {"sibling"}
    assert unverified == {"component": frozenset({"affected"})}


def test_unproven_definition_rejects_a_missing_frozen_predicate() -> None:
    with pytest.raises(ValueError, match="完整资料对应清单"):
        calculation_module._withhold_unverified_definition_predicates(
            {"component": {"sibling": ["fact-b"]}}, ({},), {},
            {"component": frozenset({"affected"})},
        )


def test_work_draft_reverifies_the_official_excerpt() -> None:
    with pytest.raises(ValueError):
        calculation_module._definition_consumer_consumption(
            _pack(), _rule_set(clauses=[CONSUMER_EXCERPT]),
            [_official_frozen_record()],
        )


# -- block narrowing --------------------------------------------------------


def _complete_record() -> ProtocolControlDefinitionConsumerRecord:
    return ProtocolControlDefinitionConsumerRecord(
        batch_id="batch-a", source_structure_unit_id="su-method",
        source_statement_index=0, source_quote=DEFINITION_QUOTE,
        source_span_ids=["span:method"],
        consumers=[ProtocolControlDefinitionAtomConsumption(
            consumer_kind="official_predicate",
            rule_component_id=RULE_COMPONENT_ID, predicate_id=PREDICATE_ID,
            consumer_excerpt=OFFICIAL_EXCERPT,
        )],
        scope_complete=True, unresolved_reasons=[],
    )


def _publication_with_definition_records(records=(), *, schema_version="control-catalog/v1"):
    return ControlCatalogPublication(
        schema_version=schema_version,
        project_id="project-generic", protocol_version_id="protocol-generic",
        rule_set_id="rules-generic", rule_set_revision=1,
        rule_set_sha256="a" * 64,
        source_job_id="job-generic", source_job_payload_sha256="b" * 64,
        source_checkpoint_id="checkpoint-generic", source_checkpoint_sha256="c" * 64,
        catalog=PublishedProtocolControlCatalog(
            catalog_id="catalog-generic", protocol_version_id="protocol-generic",
            protocol_document_sha256="d" * 64,
            study_phase=StudyPhase.PHASE_III, coverage_manifest_id="manifest-generic",
            allowed_source_span_ids=["span:method"], controls=[],
        ),
        definition_consumer_records=list(records), workflow_stage_map={},
        gate_result_id="gate-generic", created_at=datetime.now(timezone.utc),
    )


def test_published_definition_relation_is_automatically_consumed_and_identity_bound() -> None:
    record = _complete_record()
    publication = _publication_with_definition_records(
        [record], schema_version="control-catalog/v2",
    )
    restored = ControlCatalogPublication.model_validate(publication.model_dump(mode="json"))
    assert restored == publication
    assert calculation_module._definition_records_for_review(restored, None) == [record]
    with pytest.raises(ValueError, match="冻结发布版本"):
        calculation_module._definition_records_for_review(restored, [])
    with pytest.raises(ValueError, match="冻结发布版本"):
        calculation_module._definition_records_for_review(
            restored, [_official_frozen_record()],
        )
    with pytest.raises(ValidationError):
        _publication_with_definition_records(
            [_official_frozen_record()], schema_version="control-catalog/v2",
        )


def test_legacy_publication_keeps_its_original_content_identity() -> None:
    publication = _publication_with_definition_records()
    payload = publication.model_dump(mode="json")
    assert "definition_consumer_records" not in payload
    assert publication.publication_id == "control-publication:" + canonical_hash({
        key: value for key, value in payload.items() if key != "publication_id"
    })
    assert ControlCatalogPublication.model_validate(payload) == publication


def test_release_requires_a_complete_consumed_record() -> None:
    plan = SimpleNamespace(batches=[SimpleNamespace(batch_id="batch-a", batch_number=1)])
    assert publication_module._released_definition_keys([], plan) == frozenset()
    # Unproven scope and untyped unresolved reasons never release anything.
    assert publication_module._released_definition_keys([_official_frozen_record()], plan) == frozenset()
    assert publication_module._released_definition_keys(
        [_complete_record().model_copy(update={"unresolved_reasons": ["定义来源待核"]})], plan,
    ) == frozenset()
    assert publication_module._released_definition_keys([_complete_record()], plan) == frozenset({(1, 0)})
    # A consumer list is mandatory: an empty relation is not a release.
    assert publication_module._released_definition_keys(
        [_complete_record().model_copy(update={"consumers": []})], plan,
    ) == frozenset()


def test_preview_and_publication_release_share_frozen_consumer_and_gap_checks() -> None:
    gap = publication_module.SourceCalculationGap(
        batch_number=1, statement_index=0, structure_unit_id="su-method",
        source_span_ids=("span:method",), source_quote=DEFINITION_QUOTE,
        linked_official_code=None, review_decision=None, unresolved_aspects=(),
    )
    inputs = _publication_inputs(_complete_record())
    inputs[1].batches[0].batch_number = 1
    assert publication_module._verified_calculation_release(*inputs, [gap]) == frozenset({(1, 0)})
    deep_gap = gap.__class__(**{**gap.__dict__, "batch_number": 7, "batch_id": "batch-a"})
    assert publication_module._verified_calculation_release(*inputs, [deep_gap]) == frozenset({(7, 0)})
    with pytest.raises(ScopeViolationError):
        publication_module._verified_calculation_release(
            *inputs, [gap.__class__(**{**gap.__dict__, "source_span_ids": ("span:other",)})],
        )
    wrong = _publication_inputs(_complete_record(), rule_set=_rule_set(clauses=[FOREIGN_EXCERPT]))
    wrong[1].batches[0].batch_number = 1
    with pytest.raises(ScopeViolationError):
        publication_module._verified_calculation_release(*wrong, [gap])


def test_calculation_block_narrows_only_for_a_released_definition(monkeypatch) -> None:
    gap = publication_module.SourceCalculationGap(
        batch_number=1, statement_index=0, structure_unit_id="su-method",
        source_span_ids=("span:method",), source_quote=DEFINITION_QUOTE,
        linked_official_code=None, review_decision=None, unresolved_aspects=(),
    )
    monkeypatch.setattr(
        publication_module, "source_calculation_gaps", lambda store, job: (gap,),
    )
    with pytest.raises(ScopeViolationError, match="计算定义尚无可核验的正式求值方式"):
        publication_module._require_source_calculations_consumable(object(), "job-generic")
    with pytest.raises(ScopeViolationError):
        publication_module._require_source_calculations_consumable(
            object(), "job-generic", released=frozenset({(1, 1)}),
        )
    publication_module._require_source_calculations_consumable(
        object(), "job-generic", released=frozenset({(1, 0)}),
    )


def test_pre_contract_hydrate_cannot_reach_the_gate_without_records() -> None:
    # The gate compares the saved relation with the re-derived one; a checkpoint
    # from before the contract has no key at all and fails closed.
    with pytest.raises(StepFailure) as error:
        execution_module._require_definition_consumer_checkpoint_match(
            {"stage": "gate", "source_definition_consumers": []},
            [_official_frozen_record()],
        )
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID"
