from concurrent.futures import ThreadPoolExecutor

import pytest

from app.llm.logical_call_budget import LogicalCallBudget, LogicalCallBudgetExhausted


def test_budget_preserves_failed_reservations_and_never_claims_actual_usage():
    budget = LogicalCallBudget("frozen", max_requests=3, max_output_tokens=180000)
    budget.reserve(request_sha256="initial", max_tokens=60000)
    budget.reserve(request_sha256="length", max_tokens=120000)
    before = budget.snapshot()
    with pytest.raises(LogicalCallBudgetExhausted):
        budget.reserve(request_sha256="outer-repair", max_tokens=60000)
    assert budget.snapshot() == before
    assert before["reserved_output_tokens"] == 180000
    assert before["reservation_is_actual_usage"] is False


def test_concurrent_attempts_share_the_atomic_request_limit():
    budget = LogicalCallBudget("frozen", max_requests=2, max_output_tokens=120000)
    def reserve(index):
        try:
            budget.reserve(request_sha256=str(index), max_tokens=60000)
            return True
        except LogicalCallBudgetExhausted:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(8))) == 2
    assert budget.snapshot()["requests_used"] == 2


def test_budget_restores_without_resetting_failed_attempts():
    saved = []
    initial = LogicalCallBudget("frozen", max_requests=2, max_output_tokens=180000, persist=saved.append)
    initial.reserve(request_sha256="first", max_tokens=60000)
    recovered = LogicalCallBudget("frozen", max_requests=2, max_output_tokens=180000, saved=saved[-1])
    recovered.reserve(request_sha256="second", max_tokens=120000)
    with pytest.raises(LogicalCallBudgetExhausted):
        recovered.reserve(request_sha256="third", max_tokens=60000)
    assert recovered.snapshot()["requests"][:1] == saved[-1]["requests"]


@pytest.mark.parametrize("mutation", [
    {"logical_task_id": "other"}, {"requests_used": 0}, {"reserved_output_tokens": 0},
    {"max_requests": 3}, {"requests": [{"request_sha256": "a", "requested_max_tokens": True}]},
])
def test_corrupt_or_changed_budget_is_not_a_fresh_budget(mutation):
    original = LogicalCallBudget("frozen", max_requests=2, max_output_tokens=180000)
    original.reserve(request_sha256="first", max_tokens=60000)
    with pytest.raises(ValueError):
        LogicalCallBudget("frozen", max_requests=2, max_output_tokens=180000, saved={**original.snapshot(), **mutation})


def test_job_scoped_budget_store_survives_transport_recreation(tmp_path):
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    store = _ProtocolSemanticBatchFileCache(resolve_data_paths(str(tmp_path / "data")), "job")
    task_id = "a" * 64
    first = LogicalCallBudget(task_id, max_requests=2, max_output_tokens=180000, persist=store.store_call_budget)
    first.reserve(request_sha256="first", max_tokens=60000)
    second = LogicalCallBudget(task_id, max_requests=2, max_output_tokens=180000,
                               saved=store.load_call_budget(task_id), persist=store.store_call_budget)
    second.reserve(request_sha256="second", max_tokens=120000)
    assert store.load_call_budget(task_id) == second.snapshot()
    ledger_dir = tmp_path / "data" / "blobs" / "protocol-semantic-batches" / "job" / "call-budgets" / task_id
    first_path = ledger_dir / "0001.json"
    assert first_path.exists()
    first_path.unlink()
    with pytest.raises(ValueError, match="缺失"):
        store.load_call_budget(task_id)


def test_recovery_policy_change_cannot_reset_a_used_job_budget(tmp_path):
    from app.services.protocol_deconstruction_executor import _ProtocolSemanticBatchFileCache
    from app.storage.config import resolve_data_paths

    store = _ProtocolSemanticBatchFileCache(resolve_data_paths(str(tmp_path / "data")), "job")
    task_id = "b" * 64
    original = LogicalCallBudget(
        task_id, max_requests=3, max_output_tokens=180000,
        contract_sha256="a" * 64, persist=store.store_call_budget,
    )
    original.reserve(request_sha256="first", max_tokens=60000)
    saved = store.load_call_budget(task_id)
    with pytest.raises(ValueError, match="不能重置"):
        LogicalCallBudget(
            task_id, max_requests=3, max_output_tokens=180000,
            contract_sha256="c" * 64, saved=saved,
            persist=store.store_call_budget,
        )
    assert store.load_call_budget(task_id) == saved
    compatible = LogicalCallBudget(
        task_id, max_requests=3, max_output_tokens=180000,
        contract_sha256="a" * 64, saved=saved,
    )
    assert compatible.snapshot() == saved
