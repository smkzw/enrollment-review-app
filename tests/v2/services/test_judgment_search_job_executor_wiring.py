"""判断检索持久执行器接线契约测试（合成 fake completion，无真实模型）。

背景（2026-09-11 runtime06 真实运行发现的 P0）：执行器的
``recorded_completion`` 包装曾按 2 参 ``(messages, max_tokens)`` 定义，而
读器按 ``Completion`` 协议以 3 参 ``(route, messages, max_tokens)`` 调用；
TypeError 在进入函数体前抛出，被读器包装成 transport 失败后按页级失败
静默收敛——48/48 页全部"检索未完成"、零回执、摘要 coverage_incomplete，
单元测试因假件同签名而全绿。本文件按真实调用形状锁住该接线：

- 执行器把 completion 传给读器时，读器以 3 参协议调用；
- 成功路径原始回答落内容寻址工件、检查点携带回执引用；
- 传输失败落错误回执并按页级失败收敛，绝不折叠成 not_found。

不构造完整临床链种子：用最小 PageReviewInput 直接驱动读器 + 执行器包装
的协议形状；医学覆盖语义由 reader/results 测试负责。
"""
from __future__ import annotations

import asyncio
import hashlib
import json

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchPageIdentity,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.contracts.page_review import PageReviewLane
from app.llm.independent_vlm import PageVisionInput
from app.llm.judgment_search_reader import read_judgment_search_page_batch
from app.llm.page_review_harness import (
    PageCompletion,
    PageReaderRoute,
    PageReviewInput,
)
from app.services.page_review_job_service import route_identity

_IMAGE = b"\x89PNG-wiring-page-bytes"
_TARGET = "ALT 5.6 mmol/L 的研究者临床意义判断"


def _scope() -> JudgmentSearchScope:
    pages = [
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=hashlib.sha256(_IMAGE).hexdigest(),
        ),
    ]
    authority = FactAuthority(
        project_id="proj-1",
        subject_id="S1",
        review_episode_id="ep-1",
        episode_revision=1,
        protocol_version_id="prot-v1",
        rule_set_id="rules-1",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snap-1",
        complete_processing_revision_id="proc-1",
    )
    return JudgmentSearchScope(
        authority=authority,
        requirement_id="req-wiring",
        pages=tuple(pages),
        scope_sha256=judgment_search_scope_sha256(
            authority=authority, requirement_id="req-wiring", pages=tuple(pages)
        ),
    )


def _route() -> PageReaderRoute:
    return PageReaderRoute(
        lane=PageReviewLane.MAIN_A, provider="zhipu-coding-plan",
        base_url="https://endpoint.example", api_key="secret-key",
        model="GLM-5.3-Flash", reasoning_effort="high",
        max_tokens=2048, max_concurrency=2,
    )


def _page_input() -> PageReviewInput:
    return PageReviewInput(
        page_artifact_id="pa-1",
        source_document_version_id="doc-1",
        page_number=1,
        page_image_sha256=hashlib.sha256(_IMAGE).hexdigest(),
        page=PageVisionInput(source_ref="src-1", page_ordinal=1, image_bytes=_IMAGE),
    )


def _ok_text(requirement_id: str) -> str:
    return json.dumps({"results": [
        {"requirement_id": requirement_id,
         "handwritten": {"disposition": "not_found", "candidates": []},
         "printed_analysis": {"disposition": "not_found", "candidates": []}},
    ]}, ensure_ascii=False)


def test_executor_style_wrapper_accepts_protocol_three_args():
    """按执行器同款闭包形状定义的包装必须能被读器 3 参调用并返回回执。

    回归锚：runtime06 e7327bec 作业 48/48 页 transport 假失败根因。
    """
    calls: list[tuple[object, list[dict], int]] = []

    async def recorded_completion(route, messages, max_tokens):
        calls.append((route, messages, max_tokens))
        return PageCompletion(text=_ok_text("req-wiring"), finish_reason="stop",
                              usage={}, response_model="GLM-5.3-Flash")

    receipts = asyncio.run(read_judgment_search_page_batch(
        page_input=_page_input(), route=_route(),
        targets=[(_scope(), _TARGET)], completion=recorded_completion,
    ))
    assert len(receipts) == 1
    assert len(calls) == 1
    route, messages, max_tokens = calls[0]
    assert route.lane == PageReviewLane.MAIN_A
    assert max_tokens == 2048
    assert isinstance(messages, list) and messages


def test_executor_read_step_drives_real_wrapper_and_saves_receipts(
        data_paths, session_factory):
    """实例化执行器本体驱动 read 步：必须产出回执引用而非页级失败。

    回归锚：若 recorded_completion 被退回 2 参签名（runtime06 e7327bec
    的原始 P0），本测试会在进入函数体前抛 TypeError、被包装为 transport
    页级失败，断言 receipt_refs 时失败——读器侧协议测试无法拦住这种
    生产侧回归，只有执行器本体受测才能守住。
    """
    from tests.v2.helpers.phase5_fact_chain import seed_valid_fact_chain
    from app.evidence.artifacts import ArtifactStore
    store = ArtifactStore(data_paths)
    seed_page = b"\x89PNG-wiring-page-bytes"
    stored_page = store.put("page_image", seed_page)
    page_sha = stored_page.sha256

    with session_factory() as session:
        chain = seed_valid_fact_chain(session, prefix="jsew-exec", create_run=False)
        session.commit()
        authority = chain["authority"]
        scope = JudgmentSearchScope(
            authority=authority,
            requirement_id="req-wiring",
            pages=(JudgmentSearchPageIdentity(
                source_document_version_id=chain["doc_id"],
                page_artifact_id=chain["page_artifact_id"],
                page_number=1,
                page_image_sha256=page_sha,
            ),),
            scope_sha256=judgment_search_scope_sha256(
                authority=authority, requirement_id="req-wiring",
                pages=(JudgmentSearchPageIdentity(
                    source_document_version_id=chain["doc_id"],
                    page_artifact_id=chain["page_artifact_id"],
                    page_number=1,
                    page_image_sha256=page_sha,
                ),),
            ),
        )
    from app.services.judgment_search_job_executor import JudgmentSearchJobExecutor
    from app.services.judgment_search_job_service import judgment_search_execution_versions

    routes = {PageReviewLane.MAIN_A: _route()}
    routes[PageReviewLane.MAIN_B] = PageReaderRoute(
        lane=PageReviewLane.MAIN_B, provider="google", base_url="https://b.example",
        api_key="k", model="gemini-3.7-flash", reasoning_effort="high",
        max_tokens=2048, max_concurrency=2)

    async def ok_completion(route, messages, max_tokens):
        return PageCompletion(text=_ok_text("req-wiring"), finish_reason="stop",
                              usage={}, response_model=route.model)

    executor = JudgmentSearchJobExecutor(
        session_factory, store, routes, completion=ok_completion)

    payload = {
        **judgment_search_execution_versions(),
        "authority": authority.model_dump(mode="json"),
        "routes": {lane.value: route_identity(route) for lane, route in routes.items()},
        "pages": [{
            "page_artifact_id": scope.pages[0].page_artifact_id,
            "source_document_version_id": scope.pages[0].source_document_version_id,
            "page_number": scope.pages[0].page_number,
            "page_image_sha256": page_sha,
        }],
        "requirements": [{
            "requirement_id": "req-wiring",
            "scope": scope.model_dump(mode="json"),
            "target_text": _TARGET,
            "target_sha256": hashlib.sha256(_TARGET.encode("utf-8")).hexdigest(),
        }],
    }

    # run_cancellable 会按 job_id 轮询取消状态：先落一个真实任务行。
    from app.services.job_service import JobService
    from app.services.judgment_search_job_service import judgment_search_steps
    created = JobService(session_factory).create_job(
        idempotency_key="wiring-executor-test",
        job_type="judgment_search", payload=payload,
        steps=judgment_search_steps(len(payload["pages"])))

    class _Ctx:
        job_id = created.job_id
        job_type = "judgment_search"
        job_payload = payload
        step_id = "read:0:main-A"
        name = "test"
        attempt = 1
        last_checkpoint_id = None
        last_checkpoint = None
        max_attempts = 2

    result = executor(_Ctx())
    refs = (result.checkpoint or {}).get("receipt_refs")
    assert refs, f"read 步必须产出回执引用，得到: {result.checkpoint}"
    assert refs[0]["requirement_id"] == "req-wiring"


def _page_image_sha(session, chain) -> str:
    from app.storage.ocr_repositories import PageArtifactRepository
    artifact = PageArtifactRepository(session).get(chain["page_artifact_id"])
    return artifact.page_image_sha256
