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
    RestrictedProtocolControlStatement,
)
from app.domain.publication import canonical_hash
from app.services.protocol_control_definition_scope import (
    close_definition_scope, definition_scope_inputs,
)
from app.services import protocol_control_execution as execution
from app.evidence.artifacts import ArtifactStore
from app.storage.config import resolve_data_paths
from app.agents.protocol_control_agent_transport import ProtocolControlAgentCallError
from app.llm.logical_call_budget import LogicalCallBudget
from app.services.job_service import JobService, StepSpec
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, StepContext

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
        "method-batch": SimpleNamespace(candidates=[], restricted_statements=[]),
        "other-batch": SimpleNamespace(candidates=[_candidate()], restricted_statements=[]),
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


def test_global_scope_cannot_replace_unexecuted_local_registration():
    record, inventory, keyed, definition_key = _basis()
    missing = "来源定义缺少实际依赖登记回执，需补齐后重新核对"
    record.unresolved_reasons.append(missing)
    closed = close_definition_scope(
        [record], _review(inventory, definition_key, list(keyed)), inventory, keyed,
        scope_unproven_reason=UNPROVEN,
    )
    assert closed[0].scope_complete is False
    assert missing in closed[0].unresolved_reasons
    assert UNPROVEN in closed[0].unresolved_reasons


def test_global_inventory_includes_restricted_consumers_without_resolving_their_meaning():
    statement = RestrictedProtocolControlStatement(
        restricted_statement_id="restricted:other-source", source_structure_unit_id="other-unit",
        source_statement_index=0, source_quote="该期间的均值仍须核查",
        source_span_ids=["span:restricted"], limitation_kind="interpretation_unresolved",
        unresolved_dimensions=["适用期间未核清"],
    )
    record = _record()
    outputs = {"other-batch": SimpleNamespace(candidates=[], restricted_statements=[statement])}
    inventory, keyed = definition_scope_inputs([record], outputs, {})
    assert len(keyed) == 1
    entry = next(iter(keyed.values()))
    assert entry.consumer_kind == "restricted_statement"
    assert entry.key == ("restricted_statement", statement.restricted_statement_id)
    assert inventory["consumers"][0]["unresolved_dimensions"] == statement.unresolved_dimensions
    key = canonical_hash([record.batch_id, record.source_structure_unit_id, record.source_statement_index])
    closed = close_definition_scope([record], _review(inventory, key, list(keyed)),
                                    inventory, keyed, scope_unproven_reason=UNPROVEN)
    assert closed[0].scope_complete and closed[0].consumers == [entry]
    assert statement.unresolved_dimensions == ["适用期间未核清"]
    ambiguous = record.model_copy(update={"unresolved_reasons": [UNPROVEN, "定义本身的期间未核清"]})
    still_open = close_definition_scope([ambiguous], _review(inventory, key, list(keyed)),
                                        inventory, keyed, scope_unproven_reason=UNPROVEN)
    assert not still_open[0].scope_complete
    assert "定义本身的期间未核清" in still_open[0].unresolved_reasons
    empty, _ = definition_scope_inputs([record], {}, {})
    with pytest.raises(ValueError, match="冻结来源清单"):
        validate_definition_scope_review(_review(empty, key, [] , complete=False, unresolved=["未核清"]), inventory)


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
    outputs = {"method-batch": SimpleNamespace(candidates=[], restricted_statements=[])}
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


def test_scope_checkpoint_cannot_be_rewritten_after_the_model_call(monkeypatch, tmp_path):
    record, inventory, keyed, definition_key = _basis()
    review = _review(inventory, definition_key, list(keyed))
    paths = resolve_data_paths(tmp_path / "scope-data")
    artifacts = ArtifactStore(paths)
    prompt = build_definition_scope_prompt(inventory)
    raw = review.model_dump_json()
    checkpoint = {
        "stage": execution.STEP_SCOPE,
        "inventory_sha256": inventory["sha256"],
        "prompt_sha256": hashlib.sha256(
            build_definition_scope_prompt(inventory).encode("utf-8")
        ).hexdigest(),
        "raw_output_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "session_id": "test-scope-session",
        "review": review.model_dump(mode="json"),
        "source_definition_consumers": [],
        "source_scope_evidence": {
            "raw_request_ref": artifacts.put("raw_request", prompt.encode()).storage_ref,
            "raw_response_ref": artifacts.put("raw_response", raw.encode()).storage_ref,
        },
    }
    monkeypatch.setattr(execution, "_definition_scope_basis",
                        lambda context, config: ([record], inventory, keyed))
    monkeypatch.setattr(execution, "_checkpoint_for_step",
                        lambda context, step, config: checkpoint)
    with pytest.raises(Exception, match="已保存结果不一致"):
        execution._verified_definition_scope(SimpleNamespace(), SimpleNamespace(data_paths=paths))


@pytest.mark.parametrize("failure", [None, "old_hash_only", "review_changed", "wrong_kind", "corrupt_response"])
def test_scope_step_preserves_model_receipt_and_revalidates_frozen_record(monkeypatch, tmp_path, failure):
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
    config = SimpleNamespace(data_paths=resolve_data_paths(tmp_path / "scope-data"))
    saved = execution._execute_definition_scope(context, config)
    assert saved["prompt_sha256"] == hashlib.sha256(
        build_definition_scope_prompt(inventory).encode("utf-8")
    ).hexdigest()
    assert saved["raw_output_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert ArtifactStore(config.data_paths).read(saved["source_scope_evidence"]["raw_response_ref"]).decode() == raw
    if failure == "old_hash_only":
        saved.pop("source_scope_evidence")
    elif failure == "review_changed":
        saved["review"]["items"][0]["complete"] = False
        saved["review"]["items"][0]["unresolved_aspects"] = ["来源范围尚未核清"]
        changed = DefinitionScopeReview.model_validate(saved["review"])
        saved["source_definition_consumers"] = [item.model_dump(mode="json") for item in close_definition_scope(
            [record], changed, inventory, keyed, scope_unproven_reason=UNPROVEN,
        )]
    elif failure == "wrong_kind":
        saved["source_scope_evidence"]["raw_response_ref"] = ArtifactStore(config.data_paths).put(
            "evaluation_manifest", raw.encode(),
        ).storage_ref
    elif failure == "corrupt_response":
        # Deliberate damage in the disposable test root, not a historical record.
        (config.data_paths.root / saved["source_scope_evidence"]["raw_response_ref"]).write_bytes(b"{}")
    monkeypatch.setattr(execution, "_checkpoint_for_step",
                        lambda context, step, config: saved)
    if failure is None:
        assert execution._verified_definition_scope(context, config)[0].scope_complete
    else:
        with pytest.raises(execution.StepFailure) as rejected:
            execution._verified_definition_scope(context, config)
        assert rejected.value.error_code == "PROTOCOL_CONTROL_DEFINITION_SCOPE_INVALID"
        assert not rejected.value.retryable


def test_scope_invalid_response_keeps_actual_evidence_without_another_call(monkeypatch, tmp_path):
    record, inventory, keyed, _ = _basis()
    calls = []
    raw = "{broken response"
    monkeypatch.setattr(execution, "_definition_scope_basis",
                        lambda context, config: ([record], inventory, keyed))
    def reader(*, prompt):
        calls.append(prompt)
        return SimpleNamespace(session_id="test-failed-scope", text=raw)
    monkeypatch.setattr(execution, "_resolve_transport", lambda config, stage: SimpleNamespace(
        start_definition_scope=reader,
    ))
    monkeypatch.setattr(execution, "_require_frozen_route", lambda *args, **kwargs: None)
    config = SimpleNamespace(data_paths=resolve_data_paths(tmp_path / "scope-data"))
    with pytest.raises(execution.StepFailure) as rejected:
        execution._execute_definition_scope(SimpleNamespace(job_payload={}), config)
    diagnostic = rejected.value.diagnostic_checkpoint
    assert len(calls) == 1 and diagnostic["session_id"] == "test-failed-scope"
    artifacts = ArtifactStore(config.data_paths)
    assert artifacts.read(diagnostic["source_scope_evidence"]["raw_response_ref"]).decode() == raw
    assert artifacts.read(diagnostic["source_scope_evidence"]["raw_request_ref"]).decode() == calls[0]
    assert "source_definition_consumers" not in diagnostic


class _ScopeTransport:
    max_tokens = 32

    def __init__(self, raw):
        self.raw = raw
        self.calls = []
        self.budget = None
        self.receipts = []

    def bind_logical_call_budget(self, budget):
        self.budget = budget

    def take_call_receipts(self):
        receipts, self.receipts = self.receipts, []
        return receipts

    def start_definition_scope(self, *, prompt):
        try:
            if self.budget is not None:
                self.budget.reserve(request_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                                    max_tokens=self.max_tokens)
        except Exception as exc:
            raise ProtocolControlAgentCallError("test-scope-session", str(exc)) from exc
        self.calls.append(prompt)
        self.receipts.append({"fixture_call": len(self.calls)})
        return SimpleNamespace(session_id="test-scope-session", text=self.raw)


def _install_scope_basis(monkeypatch):
    record, inventory, keyed, definition_key = _basis()
    monkeypatch.setattr(execution, "_definition_scope_basis",
                        lambda context, config: ([record], inventory, keyed))
    monkeypatch.setattr(execution, "_require_frozen_route", lambda *args, **kwargs: None)
    from app.llm import mtplx_model_lifecycle
    monkeypatch.setattr(mtplx_model_lifecycle, "require_local_deployment_job", lambda payload: None)
    return _review(inventory, definition_key, list(keyed))


@pytest.mark.parametrize("limit", [1, 2])
def test_durable_scope_retry_resumes_failure_but_never_resets_budget(
    monkeypatch, data_paths, session_factory, limit,
):
    review = _install_scope_basis(monkeypatch)
    transport = _ScopeTransport("{invalid fixture response")
    config = execution.ProtocolControlExecutorConfig(
        data_paths=data_paths, session_factory=session_factory, deep_transport=transport,
    )
    executor = execution.create_protocol_control_executor(config)
    service = JobService(session_factory)
    created = service.create_job(
        idempotency_key="scope-retry", job_type=execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload={"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION,
                 "deep_workflow_variant": "RV1001-FLOW", "deep_request_limit": limit},
        steps=[StepSpec(step_id=execution.STEP_SCOPE, name="核对定义影响范围")],
    )
    runner = JobRunner(session_factory, {execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: executor},
                       sleep=lambda _: None)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        store = JobStore(session)
        original = store.get_last_checkpoint(created.job_id, execution.STEP_SCOPE)
        assert store.get_job(created.job_id).state == "failed_final"
    assert original[1]["stage"] == "definition_scope_failure_diagnostic"
    assert original[1]["model_call_receipts"] == [{"fixture_call": 1}]
    assert len(transport.calls) == 1
    transport.raw = review.model_dump_json()
    service.retry(created.job_id)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        store = JobStore(session)
        job = store.get_job(created.job_id)
        latest = store.get_last_checkpoint(created.job_id, execution.STEP_SCOPE)
        if limit == 1:
            assert job.state == "failed_final"
            assert job.error_code == "PROTOCOL_CONTROL_LOGICAL_BUDGET_EXHAUSTED"
            assert len(transport.calls) == 1
            assert latest[1]["stage"] == "definition_scope_failure_diagnostic"
        else:
            assert job.state == "completed" and len(transport.calls) == 2
            assert latest[1]["model_call_receipts"] == [{"fixture_call": 2}]
            replay = StepContext(job_id=created.job_id, job_type=job.job_type,
                                 job_payload={"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION},
                                 step_id=execution.STEP_SCOPE, name="恢复核对", attempt=2,
                                 last_checkpoint_id=latest[0], last_checkpoint=latest[1])
            assert executor(replay) == {key: value for key, value in latest[1].items() if key != "attempt"}
            assert len(transport.calls) == 2
        from app.storage.models import JobCheckpointRecord
        from app.storage.codecs import verify_payload_sha256
        old = session.get(JobCheckpointRecord, original[0])
        assert verify_payload_sha256(old.payload_json, old.payload_sha256) == original[1]


def test_scope_without_frozen_budget_clears_shared_transport_previous_step(monkeypatch, tmp_path):
    review = _install_scope_basis(monkeypatch)
    transport = _ScopeTransport(review.model_dump_json())
    transport.budget = LogicalCallBudget("unrelated-step", max_requests=1, max_output_tokens=32)
    transport.budget.reserve(request_sha256="old-request", max_tokens=32)
    transport.receipts = [{"fixture_call": "foreign-step"}]
    monkeypatch.setattr(execution, "_resolve_transport", lambda config, stage: transport)
    config = SimpleNamespace(data_paths=resolve_data_paths(tmp_path / "scope-data"))
    saved = execution._execute_definition_scope(SimpleNamespace(job_payload={}), config)
    assert transport.budget is None and len(transport.calls) == 1
    assert saved["model_call_receipts"] == [{"fixture_call": 1}]
    assert saved["prior_unassigned_model_receipts"] == [{"fixture_call": "foreign-step"}]


@pytest.mark.parametrize("loss", ["tail", "all"])
def test_scope_budget_cannot_rewind_after_reservation_files_are_lost(
    monkeypatch, data_paths, session_factory, loss,
):
    _install_scope_basis(monkeypatch)
    transport = _ScopeTransport("{invalid response")
    reader = transport.start_definition_scope
    def two_requests(*, prompt):
        response = reader(prompt=prompt)
        transport.budget.reserve(request_sha256="fixture-second-request", max_tokens=32)
        return response
    transport.start_definition_scope = two_requests
    executor = execution.create_protocol_control_executor(execution.ProtocolControlExecutorConfig(
        data_paths=data_paths, session_factory=session_factory, deep_transport=transport,
    ))
    service = JobService(session_factory)
    created = service.create_job(
        idempotency_key="scope-budget-loss", job_type=execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload={"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION,
                 "deep_workflow_variant": "RV1001-FLOW", "deep_request_limit": 3},
        steps=[StepSpec(step_id=execution.STEP_SCOPE, name="核对定义影响范围")],
    )
    runner = JobRunner(session_factory, {execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: executor},
                       sleep=lambda _: None)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        original = JobStore(session).get_last_checkpoint(created.job_id, execution.STEP_SCOPE)
    assert original[1]["logical_call_budget"]["requests_used"] == 2
    reservations = list(data_paths.blobs_dir.glob("protocol-semantic-batches/**/call-budgets/*/*.json"))
    assert len(reservations) == 2
    for path in reservations:
        if loss == "all" or path.name == "0002.json":
            path.unlink()
    for _ in range(2):
        service.retry(created.job_id)
        assert runner.run_job(created.job_id)
        with session_factory() as session:
            store = JobStore(session)
            assert store.get_job(created.job_id).error_code == "PROTOCOL_CONTROL_BUDGET_RECORD_INVALID"
            assert store.get_last_checkpoint(created.job_id, execution.STEP_SCOPE)[1]["stage"] == "definition_scope_failure_diagnostic"
    assert len(transport.calls) == 1
    from app.storage.models import JobCheckpointRecord
    from app.storage.codecs import verify_payload_sha256
    with session_factory() as session:
        old = session.get(JobCheckpointRecord, original[0])
        assert verify_payload_sha256(old.payload_json, old.payload_sha256) == original[1]


def test_scope_failure_before_reservation_can_retry_without_missing_budget_false_alarm(
    monkeypatch, data_paths, session_factory,
):
    review = _install_scope_basis(monkeypatch)
    transport = _ScopeTransport(review.model_dump_json())
    original_reader = transport.start_definition_scope
    def unavailable_before_send(*, prompt):
        raise ProtocolControlAgentCallError("pre-reserve-session", "fixture model catalog unavailable")
    transport.start_definition_scope = unavailable_before_send
    service = JobService(session_factory)
    created = service.create_job(
        idempotency_key="scope-zero-reservation", job_type=execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload={"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION,
                 "deep_workflow_variant": "RV1001-FLOW", "deep_request_limit": 1},
        steps=[StepSpec(step_id=execution.STEP_SCOPE, name="核对定义影响范围", max_attempts=1)],
    )
    executor = execution.create_protocol_control_executor(execution.ProtocolControlExecutorConfig(
        data_paths=data_paths, session_factory=session_factory, deep_transport=transport,
    ))
    runner = JobRunner(session_factory, {execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: executor}, sleep=lambda _: None)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(created.job_id).error_code == "PROTOCOL_CONTROL_DEFINITION_SCOPE_TRANSPORT_FAILED"
        assert store.get_last_checkpoint(created.job_id, execution.STEP_SCOPE)[1]["logical_call_budget"]["requests_used"] == 0
    assert not list(data_paths.blobs_dir.glob("protocol-semantic-batches/**/call-budgets/*/*.json"))
    transport.start_definition_scope = original_reader
    service.retry(created.job_id)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        assert JobStore(session).get_job(created.job_id).state == "completed"
    assert len(transport.calls) == 1


@pytest.mark.parametrize("damage", [None, "gate_records", "missing_raw", "modified_review", "changed_basis"])
def test_adoption_rechecks_actual_completed_scope_answer(
    monkeypatch, data_paths, session_factory, damage,
):
    import copy
    from app.services.protocol_control_catalog_publication import require_saved_definition_scope
    from app.storage.repositories import ScopeViolationError
    review = _install_scope_basis(monkeypatch)
    transport = _ScopeTransport(review.model_dump_json())
    executor = execution.create_protocol_control_executor(execution.ProtocolControlExecutorConfig(
        data_paths=data_paths, session_factory=session_factory, deep_transport=transport,
    ))
    payload = {"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION,
               "deep_workflow_variant": "RV1001-FLOW", "deep_request_limit": 2}
    service = JobService(session_factory)
    created = service.create_job(
        idempotency_key="scope-adoption", job_type=execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload=payload, steps=[StepSpec(step_id=execution.STEP_SCOPE, name="核对定义影响范围")],
    )
    runner = JobRunner(session_factory, {execution.PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: executor}, sleep=lambda _: None)
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        found = JobStore(session).get_last_checkpoint(created.job_id, execution.STEP_SCOPE)
        result = {"source_definition_consumers": copy.deepcopy(found[1]["source_definition_consumers"])}
        if damage == "gate_records":
            result["source_definition_consumers"][0]["scope_complete"] = False
        elif damage == "missing_raw":
            (data_paths.root / found[1]["source_scope_evidence"]["raw_response_ref"]).unlink()
        elif damage == "modified_review":
            from app.storage.codecs import encode_value
            from app.storage.models import JobCheckpointRecord
            row = session.get(JobCheckpointRecord, found[0])
            changed = copy.deepcopy(found[1])
            changed["review"]["items"][0]["complete"] = False
            changed["review"]["items"][0]["unresolved_aspects"] = ["试验变更"]
            row.payload_json, row.payload_sha256 = encode_value(changed)
            session.flush()
        elif damage == "changed_basis":
            record, inventory, keyed, _ = _basis()
            inventory["sha256"] = "0" * 64
            monkeypatch.setattr(execution, "_definition_scope_basis", lambda *_: ([record], inventory, keyed))
        if damage is None:
            require_saved_definition_scope(session, source_job_id=created.job_id, payload=payload, result=result)
        else:
            with pytest.raises(ScopeViolationError):
                require_saved_definition_scope(session, source_job_id=created.job_id, payload=payload, result=result)
    assert len(transport.calls) == 1


@pytest.mark.parametrize("failure,code,retryable", [
    (None, "PROTOCOL_CONTROL_DEFINITION_SCOPE_TRANSPORT_FAILED", True),
    ("uncertain", "PROTOCOL_CONTROL_DEFINITION_SCOPE_COMPLETION_UNCERTAIN", False),
])
def test_scope_transport_failure_preserves_prompt_and_does_not_become_completed(
    monkeypatch, tmp_path, failure, code, retryable,
):
    _install_scope_basis(monkeypatch)
    def reader(*, prompt):
        raise ProtocolControlAgentCallError("test-interrupted-scope", "fixture connection failure",
                                            uncertain_completion=failure == "uncertain")
    monkeypatch.setattr(execution, "_resolve_transport", lambda config, stage: SimpleNamespace(
        start_definition_scope=reader, take_call_receipts=lambda: [{"fixture_call": "failed"}],
    ))
    config = SimpleNamespace(data_paths=resolve_data_paths(tmp_path / "scope-data"))
    with pytest.raises(execution.StepFailure) as failure_record:
        execution._execute_definition_scope(SimpleNamespace(job_payload={}), config)
    rejected = failure_record.value
    assert rejected.error_code == code and rejected.retryable is retryable
    assert rejected.diagnostic_checkpoint["stage"] == "definition_scope_failure_diagnostic"
    assert rejected.diagnostic_checkpoint["session_id"] == "test-interrupted-scope"
    assert rejected.diagnostic_checkpoint["source_scope_evidence"]["raw_request_ref"]
    assert "raw_response_ref" not in rejected.diagnostic_checkpoint["source_scope_evidence"]
    assert "source_definition_consumers" not in rejected.diagnostic_checkpoint


@pytest.mark.parametrize("step", [execution.STEP_HYDRATE, execution.STEP_GATE])
def test_replay_of_downstream_result_rechecks_current_sources_not_saved_acceptance(
    monkeypatch, step,
):
    _install_scope_basis(monkeypatch)
    saved = {"stage": step, "fixture_output": "old"}
    monkeypatch.setattr(execution, "_replay_checkpoint", lambda context, config: saved)
    entry = "_execute_hydrate" if step == execution.STEP_HYDRATE else "_execute_gate"
    checks = []
    def current(context, config):
        checks.append(context.step_id)
        return {**saved, "fixture_output": "current"}
    monkeypatch.setattr(execution, entry, current)
    executor = execution.create_protocol_control_executor(SimpleNamespace())
    context = StepContext(job_id="job-scope-test", job_type=execution.PROTOCOL_CONTROL_JOB_TYPE,
                          job_payload={"execution_version": execution.PROTOCOL_CONTROL_EXECUTION_VERSION},
                          step_id=step, name=step, attempt=1,
                          last_checkpoint_id="checkpoint-test", last_checkpoint=saved)
    with pytest.raises(execution.StepFailure) as failure:
        executor(context)
    assert failure.value.error_code == "PROTOCOL_CONTROL_CHECKPOINT_INVALID"
    assert checks == [step] and saved["fixture_output"] == "old"
