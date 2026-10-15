import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from scripts.qwen_platform_measurement import MeasuredCompletion
from app.domain.contracts.page_review import PageReviewRecord
from pydantic import TypeAdapter, ValidationError
from unittest.mock import AsyncMock, Mock
from scripts import qwen_platform_measurement as measurement
from scripts.qwen_protocol_measurement import StreamingClient


def test_budget_over_ceiling_rejected_before_request(tmp_path):
    meter = MeasuredCompletion(tmp_path, tmp_path)
    with pytest.raises(ValueError, match="authorized output ceiling"):
        asyncio.run(meter(None, [], 131073))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("requested", ["xhigh", "medium", "low"])
def test_effort_is_retained_without_remapping(requested):
    effort = TypeAdapter(PageReviewRecord.model_fields["reasoning_effort"].annotation)
    assert effort.validate_python(requested) == requested
    with pytest.raises(ValidationError):
        effort.validate_python("default")


def test_waits_for_stream_cleanup_before_next_request(monkeypatch):
    check = Mock(side_effect=[RuntimeError("still active"), None])
    monkeypatch.setattr(measurement, "require_idle_local_reader", check)
    monkeypatch.setattr(measurement.asyncio, "sleep", AsyncMock())
    asyncio.run(measurement.await_idle("mtplx"))
    assert check.call_count == 2


def test_persistent_busy_never_submits_a_request(monkeypatch):
    check = Mock(side_effect=RuntimeError("still active"))
    monkeypatch.setattr(measurement, "require_idle_local_reader", check)
    monkeypatch.setattr(measurement.asyncio, "sleep", AsyncMock())
    with pytest.raises(RuntimeError):
        asyncio.run(measurement.await_idle("mtplx"))
    assert check.call_count == 31


def test_protocol_clients_share_one_local_request_slot():
    active = 0
    peak = 0

    async def meter(route, messages, budget, kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return SimpleNamespace(response_id="test", response_model="test", usage={},
                               finish_reason="stop", text="{}")

    lock = threading.Lock()
    clients = [StreamingClient(meter, None, lock) for _ in range(3)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda c: c.create(messages=[], max_tokens=131072,
                                                  model="test"), clients))
    assert len(results) == 3
    assert peak == 1


@pytest.mark.parametrize("failed", [False, True])
def test_stream_warning_is_preserved_in_receipt(tmp_path, monkeypatch, failed):
    warning = "299 omlx structured output not enforced"

    class Response:
        status_code = 400 if failed else 200
        is_error = failed
        text = "image content requires MTP generation mode"
        headers = {"Warning": warning}

        def raise_for_status(self):
            if failed:
                raise RuntimeError("rejected")

        async def aread(self):
            return self.text.encode()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            yield 'data: {"model":"test","choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}'

    class Client(Response):
        def __init__(self, **kwargs):
            pass

        def stream(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(measurement.httpx, "AsyncClient", Client)
    monkeypatch.setattr(measurement, "metrics", AsyncMock(return_value={}))
    monkeypatch.setattr(measurement, "await_idle", AsyncMock())
    monkeypatch.setattr(measurement.subprocess, "run", Mock(return_value=SimpleNamespace(
        stdout='{"text_tokens":10,"image_allowance":0}')))
    route = SimpleNamespace(model="test", reasoning_effort="medium", provider="omlx",
                            base_url="http://localhost/v1", api_key="test")
    if failed:
        with pytest.raises(RuntimeError, match="rejected"):
            asyncio.run(MeasuredCompletion(tmp_path, tmp_path)(route, [], 131072))
    else:
        asyncio.run(MeasuredCompletion(tmp_path, tmp_path)(route, [], 131072))
    receipt = json.loads((tmp_path / "response-0.json").read_text())
    assert receipt["response_format_warning"] == warning
    if failed:
        assert receipt["http_error_body"] == Response.text
