"""A bounded receipt ledger shared by nested retries of one frozen work unit."""
from __future__ import annotations

from threading import Lock
from collections.abc import Callable, Mapping
from typing import Any


class LogicalCallBudgetExhausted(RuntimeError):
    code = "LOGICAL_BUDGET_EXHAUSTED"


class LogicalCallBudget:
    def __init__(self, logical_task_id: str, *, max_requests: int, max_output_tokens: int,
                 saved: Mapping[str, Any] | None = None,
                 persist: Callable[[dict[str, Any]], None] | None = None,
                 contract_sha256: str | None = None):
        if not logical_task_id or max_requests < 1 or max_output_tokens < 1:
            raise ValueError("逻辑任务身份和调用预算必须明确且大于零")
        self.logical_task_id = logical_task_id
        self.max_requests = max_requests
        self.max_output_tokens = max_output_tokens
        self.contract_sha256 = contract_sha256
        self._requests: list[dict[str, Any]] = []
        self._lock = Lock()
        self._persist = persist
        if saved is not None:
            requests = saved.get("requests")
            if (saved.get("policy") != "logical-call-budget/v1"
                    or saved.get("logical_task_id") != logical_task_id
                    or saved.get("max_requests") != max_requests
                    or saved.get("max_output_tokens") != max_output_tokens
                    or saved.get("contract_sha256") != contract_sha256
                    or not isinstance(requests, list)
                    or any(not isinstance(item, dict) or not isinstance(item.get("request_sha256"), str)
                           or type(item.get("requested_max_tokens")) is not int or item["requested_max_tokens"] < 1
                           for item in requests)
                    or saved.get("requests_used") != len(requests)
                    or len(requests) > max_requests
                    or saved.get("reserved_output_tokens") != sum(item["requested_max_tokens"] for item in requests)
                    or saved["reserved_output_tokens"] > max_output_tokens):
                raise ValueError("既有调用预算记录损坏或范围不兼容，不能重置后继续")
            self._requests = [dict(item) for item in requests]

    def reserve(self, *, request_sha256: str, max_tokens: int) -> None:
        if max_tokens < 1:
            raise ValueError("输出额度必须大于零")
        with self._lock:
            reserved = sum(item["requested_max_tokens"] for item in self._requests)
            if len(self._requests) >= self.max_requests or reserved + max_tokens > self.max_output_tokens:
                raise LogicalCallBudgetExhausted("本次读取的累计调用或输出预算已用尽，未再次发送请求")
            # Reserve before sending, including failed/unknown upstream attempts.
            self._requests.append({
                "request_sha256": request_sha256,
                "requested_max_tokens": max_tokens,
            })
            if self._persist is not None:
                self._persist(self._snapshot())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        return {
            "policy": "logical-call-budget/v1",
            "logical_task_id": self.logical_task_id,
            "max_requests": self.max_requests,
            "max_output_tokens": self.max_output_tokens,
            "contract_sha256": self.contract_sha256,
            "requests_used": len(self._requests),
            "reserved_output_tokens": sum(item["requested_max_tokens"] for item in self._requests),
            "requests": [dict(item) for item in self._requests],
            "reservation_is_actual_usage": False,
        }
