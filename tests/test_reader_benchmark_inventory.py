import json
import asyncio
from types import SimpleNamespace

import pytest

from scripts.summarize_frozen_reader_runs import collect


def test_formal_reader_rejects_low_budget_before_request(tmp_path, monkeypatch):
    from scripts import run_frozen_product_reader as runner

    (tmp_path / 'input.json').write_text(json.dumps({'pages': [{}]}))
    (tmp_path / 'manifest.json').write_text(json.dumps({'files': {}}))
    monkeypatch.setattr(runner, 'require_page_reader_routes', lambda: {
        runner.PageReviewLane.MAIN_B: SimpleNamespace(max_tokens=12000),
    })
    args = SimpleNamespace(output=tmp_path / 'output', page_index=0, provider=None,
                           frozen=tmp_path, batch_pages=None, lane='main-B')
    with pytest.raises(ValueError, match='PAGE_REVIEW_MAX_TOKENS'):
        asyncio.run(runner.run(args))
    assert not args.output.exists()


def test_usage_conflicts_and_missing_prices_remain_explicit(tmp_path):
    run = tmp_path / "product-runs-64k" / "sample"
    run.mkdir(parents=True)
    (run / "receipts.json").write_text(json.dumps([{
        "model": "sample", "usage": {"completion_tokens": 32, "output_tokens": 0},
        "elapsed_seconds": 2, "finish_reason": "stop",
    }]))
    rows = collect(tmp_path)
    assert len(rows) == 1
    assert rows[0]["output_tokens_reported"] == 32
    assert rows[0]["output_usage_disagreement"] is True
    assert rows[0]["reader_state"] == "pending"
    assert rows[0]["clinical_acceptance"] is False
    assert rows[0]["api_cost"] is None
    assert rows[0]["output_budget_enforced"] is None


def test_direct_receipt_budget_is_retained_without_subscription_transport(tmp_path):
    run = tmp_path / "product-runs-64k" / "sample"
    run.mkdir(parents=True)
    (run / "receipts.json").write_text(json.dumps([{
        "model": "sample", "output_budget_enforced": True,
    }]))
    assert collect(tmp_path)[0]["output_budget_enforced"] is True
    (run / "transport-0.json").write_text(json.dumps({"output_budget_enforced": False}))
    assert collect(tmp_path)[0]["output_budget_enforced"] is False


def test_native_normalizer_keeps_budget_and_does_not_imply_clinical_acceptance(tmp_path):
    run = tmp_path / "normalizer-native-runs" / "sample"
    run.mkdir(parents=True)
    for filename, content in {
        "receipts.json": [{"usage": {"promptTokenCount": 100, "candidatesTokenCount": 20,
                                       "thoughtsTokenCount": 30}}],
        "request-0.json": {"max_tokens": 65536},
        "result.json": {"status": "parsed"},
        "transport-contract.json": {"kind": "product_native_transport", "formal_transport_comparison": True},
    }.items():
        (run / filename).write_text(json.dumps(content))
    row, = collect(tmp_path, "normalizer*-runs/*/receipts.json")
    assert row["requested_budget"] == 65536
    assert row["reader_state"] == "parsed"
    assert row["formal_transport_comparison"] is True
    assert row["output_tokens_reported"] == 20
    assert row["reasoning_tokens_reported"] == 30
    assert row["clinical_acceptance"] is False


def test_native_timeout_keeps_identity_and_unknown_usage(tmp_path):
    run = tmp_path / "normalizer-native-runs" / "timeout"
    run.mkdir(parents=True)
    (run / "receipts.json").write_text(json.dumps([{
        "requested_model": "sample", "reasoning_effort": "high", "usage": None,
    }]))
    row, = collect(tmp_path, "normalizer*-runs/*/receipts.json")
    assert row["requested_model"] == "sample"
    assert row["requested_effort"] == "high"
    assert row["input_tokens"] is None
    assert row["output_tokens_reported"] is None
    assert row["api_cost"] is None
