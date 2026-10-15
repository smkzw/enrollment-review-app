"""Opt-in multi-page batch reading experiment; the default per-page reader is unchanged.

把同一审核节点的一组 PageReviewInput 合并为一次图文请求：完整 ClausePack、页级
output_schema、临床提示约束与页级校验全部沿用现有 build_page_review_messages 和
read_page，本模块只添加通用批次框架，不生成任何临床题目，不接入默认流程。

限制（experiment scope）：
- 调用前逐一复核每页冻结图像哈希与页身份（page_number 与图像页序一致）；
- 429 限流按 read_page 同样方式等待重试（60 秒、至多 max_rate_limit_waits 次），
  但不换模型、不做端点回退，其余传输失败显式抛出；
- 输出预算初始为 route.max_tokens（不乘页数；真实实验可直接配置 65536），
  截断时只翻倍一次，不改采样参数；
- 批次 usage 只记在批次结果上，不摊入每页记录；
- 不支持针对性复核（review_focus）。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Sequence

from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.page_review import (
    PAGE_REVIEW_CONTRACT_VERSION,
    PageReviewRecord,
)
from app.domain.publication import canonical_hash
from app.llm.independent_vlm import page_to_data_url
from app.llm.page_review_harness import (
    _failure_kind,
    PAGE_REVIEW_PROMPT_VERSION,
    Completion,
    PageCompletion,
    PageReaderRoute,
    PageReviewConfigError,
    PageReviewHarnessError,
    PageReviewInput,
    build_page_review_messages,
    direct_completion,
    read_page,
    repair_json_quotes,
)
from app.projections.clause_pack import verify_clause_pack

BATCH_PROMPT_VERSION = "page-review-batch/v2"

_PAGE_ONLY_KEYS = ("page_artifact_id", "page_number")

_BATCH_FRAMING = (
    "本次请求是同一审核节点的多页合并读片实验：页面图像按 pages 数组顺序提供，共 {count} 页。"
    "只输出一个 JSON 对象，键为每页的 page_artifact_id，"
    "值为该页完全符合 output_schema 的原始页级 JSON 载荷；"
    "必须覆盖全部页面，不得遗漏，也不得新增未提供的页面键。"
    "每页载荷只描述该页图像自身可见内容，不得引用、归因或补充其他页面。"
)


@dataclass(frozen=True)
class PageReviewBatchFailure:
    page_artifact_id: str
    failure_kind: str
    detail: str


@dataclass(frozen=True)
class PageReviewBatchResult:
    batch_id: str
    prompt_version: str
    batch_request_sha256: str
    finish_reason: str | None
    usage: dict[str, int | float]
    records: list[PageReviewRecord]
    failures: list[PageReviewBatchFailure]


def _page_context_key(page_input: PageReviewInput) -> str | None:
    if page_input.review_context is None:
        return None
    return canonical_hash(page_input.review_context.model_dump(mode="json"))


def _verify_batch_pages(page_inputs: Sequence[PageReviewInput]) -> None:
    """Re-verify frozen image bytes and page identity immediately before the call."""
    for page_input in page_inputs:
        if page_input.page_number != page_input.page.page_ordinal:
            raise ValueError(
                f"批次页面 {page_input.page_artifact_id} 页码与图像页序不一致"
            )
        image_url = page_to_data_url(page_input.page)
        if not image_url.startswith("data:") or ";base64," not in image_url:
            raise ValueError(
                f"批次页面 {page_input.page_artifact_id} 图像必须为已校验的内嵌数据"
            )
        image_bytes = base64.b64decode(image_url.split(",", 1)[1], validate=True)
        if hashlib.sha256(image_bytes).hexdigest() != page_input.page_image_sha256:
            raise ValueError(
                f"批次页面 {page_input.page_artifact_id} 图像与冻结原件不一致"
            )


def _build_batch_messages(
    route: PageReaderRoute,
    page_inputs: Sequence[PageReviewInput],
    clause_pack: ClausePack,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    image_parts: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    shared: dict[str, Any] | None = None
    system_prompt = ""
    for page_input in page_inputs:
        messages = build_page_review_messages(route, page_input, clause_pack)
        parts = messages[1]["content"]
        images = [part for part in parts if part.get("type") == "image_url"]
        texts = [part for part in parts if part.get("type") == "text"]
        if len(images) != 1 or len(texts) != 1:
            raise PageReviewHarnessError(
                "页级请求结构不符合批次实验假设", failure_kind="configuration"
            )
        payload = json.loads(texts[0]["text"])
        current_shared = {
            key: value for key, value in payload.items() if key not in _PAGE_ONLY_KEYS
        }
        if shared is None:
            shared = current_shared
            system_prompt = messages[0]["content"]
        elif current_shared != shared:
            raise PageReviewHarnessError(
                "各页共享上下文不一致，不能合并为一次批次请求",
                failure_kind="configuration",
            )
        image_parts.append(images[0])
        pages.append({key: payload[key] for key in _PAGE_ONLY_KEYS})
    batch_prompt: dict[str, Any] = {
        "batch_response_contract": {
            "type": BATCH_PROMPT_VERSION,
            "response": "单一 JSON 对象",
            "keys": "page_artifact_id",
            "values": "该页符合 output_schema 的原始页级载荷",
            "coverage": "必须覆盖全部页面，无遗漏、无新增",
            "isolation": "每页仅描述该页图像自身可见内容，不引用或归因其他页面",
        },
        "page_count": len(page_inputs),
        "pages": pages,
        **shared,
    }
    return [
        {
            "role": "system",
            "content": system_prompt + "\n" + _BATCH_FRAMING.format(count=len(page_inputs)),
        },
        {
            "role": "user",
            "content": [
                *image_parts,
                {
                    "type": "text",
                    "text": json.dumps(
                        batch_prompt, ensure_ascii=False, separators=(",", ":")
                    ),
                },
            ],
        },
    ], batch_prompt


def _parse_batch_pages(text: str) -> tuple[dict[str, Any], list[str]]:
    """Split the batch JSON; top-level key order stays observable for duplicate detection."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise PageReviewHarnessError("模型未返回批次 JSON 对象", failure_kind="invalid_json")
    key_orders: list[list[str]] = []

    def record_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        # The outermost object closes last, so its keys land at the end of key_orders.
        key_orders.append([key for key, _ in pairs])
        return dict(pairs)

    decoder = json.JSONDecoder(object_pairs_hook=record_keys, strict=False)
    body = match.group(0)
    try:
        envelope = decoder.raw_decode(body)[0]
    except json.JSONDecodeError:
        try:
            envelope = decoder.raw_decode(repair_json_quotes(body))[0]
        except json.JSONDecodeError as exc:
            raise PageReviewHarnessError(
                "模型批次 JSON 无法修复", failure_kind="invalid_json"
            ) from exc
    if not isinstance(envelope, dict):
        raise PageReviewHarnessError("批次响应不是 JSON 对象", failure_kind="invalid_json")
    return envelope, (key_orders[-1] if key_orders else [])


async def read_page_batch(
    route: PageReaderRoute,
    page_inputs: Sequence[PageReviewInput],
    clause_pack: ClausePack,
    *,
    completion: Completion = direct_completion,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_rate_limit_waits: int = 12,
) -> PageReviewBatchResult:
    if not route.model:
        raise PageReviewConfigError(f"{route.lane.value} 尚未通过模型身份预检")
    verify_clause_pack(clause_pack)
    page_inputs = list(page_inputs)
    if not page_inputs:
        raise ValueError("批次读片至少需要一页")
    page_ids = [page.page_artifact_id for page in page_inputs]
    if len(set(page_ids)) != len(page_ids):
        raise ValueError("批次读片的页面不得重复")
    if len({_page_context_key(page) for page in page_inputs}) > 1:
        raise ValueError("批次读片仅允许同一审核节点的页面")

    _verify_batch_pages(page_inputs)
    batch_messages, batch_prompt = _build_batch_messages(route, page_inputs, clause_pack)
    batch_request_sha256 = canonical_hash(batch_prompt)
    budget = route.max_tokens
    length_retried = False
    rate_limit_waits = 0
    while True:
        try:
            result = await completion(route, batch_messages, budget)
        except Exception as exc:
            # Same wait discipline as read_page; the batch never switches model or endpoint.
            kind = _failure_kind(exc)
            if kind == "rate_limit" and rate_limit_waits < max_rate_limit_waits:
                rate_limit_waits += 1
                await sleep(60)
                continue
            raise PageReviewHarnessError(
                f"{route.lane.value} 批次判读失败：{exc}", failure_kind=kind
            ) from exc
        if result.finish_reason == "length":
            if length_retried:
                raise PageReviewHarnessError(
                    "输出额度用尽，结果仍不完整", failure_kind="length"
                )
            budget *= 2
            length_retried = True
            continue
        break
    if result.finish_reason in {"content_filter", "content-filter"}:
        raise PageReviewHarnessError(
            f"{route.lane.value} 页面内容被端点拦截", failure_kind="content_filter"
        )
    if result.finish_reason != "stop":
        raise PageReviewHarnessError(
            "模型未确认资料判读完整结束，请保留原件并重新核对",
            failure_kind="schema",
        )

    scope = canonical_hash(
        {
            "contract_version": PAGE_REVIEW_CONTRACT_VERSION,
            "batch_prompt_version": BATCH_PROMPT_VERSION,
            "lane": route.lane.value,
            "provider": route.provider,
            "model": route.model,
            "reasoning_effort": route.reasoning_effort,
            "endpoint_base_url": route.base_url,
            "clause_pack_sha256": clause_pack.clause_pack_sha256,
            "page_artifact_ids": page_ids,
            "batch_request_sha256": batch_request_sha256,
        }
    )
    batch_id = "page-review-batch:" + scope[:32]

    envelope, top_keys = _parse_batch_pages(result.text)
    expected_ids = set(page_ids)
    returned: dict[str, str] = {}
    failures: list[PageReviewBatchFailure] = []
    for key in dict.fromkeys(top_keys):
        if top_keys.count(key) > 1:
            failures.append(
                PageReviewBatchFailure(
                    key, "duplicate_page", "批次响应为同一页返回了多个条目"
                )
            )
            continue
        if key not in expected_ids:
            failures.append(
                PageReviewBatchFailure(key, "unknown_page", "批次响应返回了未请求的页面")
            )
            continue
        returned[key] = json.dumps(envelope[key], ensure_ascii=False)
    for page_id in page_ids:
        if page_id not in returned and not any(
            failure.page_artifact_id == page_id for failure in failures
        ):
            failures.append(
                PageReviewBatchFailure(page_id, "missing_page", "批次响应缺少该页面")
            )
    failed_ids = {failure.page_artifact_id for failure in failures}

    async def split_completion(_route: PageReaderRoute, messages, _budget: int) -> PageCompletion:
        prompt = json.loads(
            next(
                part["text"]
                for part in messages[1]["content"]
                if part.get("type") == "text"
            )
        )
        # Batch usage stays on the batch result; per-page records cannot split it truthfully.
        return PageCompletion(returned[prompt["page_artifact_id"]], result.finish_reason, {})

    records: list[PageReviewRecord] = []
    for page_input in page_inputs:
        # Missing or refused pages already carry their explicit failure entry.
        if page_input.page_artifact_id in failed_ids:
            continue
        try:
            record = await read_page(
                route,
                page_input,
                clause_pack,
                completion=split_completion,
                retry_length=False,
            )
        except Exception as exc:  # per-page failure; valid pages continue below
            failures.append(
                PageReviewBatchFailure(
                    page_input.page_artifact_id,
                    getattr(exc, "failure_kind", None) or "page_validation",
                    str(exc),
                )
            )
            continue
        records.append(
            record.model_copy(
                update={
                    "prompt_version": record.prompt_version + "+" + BATCH_PROMPT_VERSION,
                    "page_review_id": "page-review:"
                    + hashlib.sha256(
                        (record.page_review_id + "|" + scope).encode("utf-8")
                    ).hexdigest()[:32],
                }
            )
        )
    usage = {
        str(key): value
        for key, value in result.usage.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    base_prompt_version = PAGE_REVIEW_PROMPT_VERSION
    return PageReviewBatchResult(
        batch_id=batch_id,
        prompt_version=base_prompt_version + "+" + BATCH_PROMPT_VERSION,
        batch_request_sha256=batch_request_sha256,
        finish_reason=result.finish_reason,
        usage=usage,
        records=records,
        failures=failures,
    )


__all__ = [
    "BATCH_PROMPT_VERSION",
    "PageReviewBatchFailure",
    "PageReviewBatchResult",
    "read_page_batch",
]
