"""回执到当前目标的绑定装配（candidate-only 纯函数，无存储、无模型调用）。

``assemble_judgment_search_coverage`` 消费**当前仓储准备**的
``JudgmentSearchScope`` + ``target_text`` 与一串 ``JudgmentSearchReaderReceipt``，
在确定性一致性核对全部通过后，为每条读道构建原生
``JudgmentSearchLaneResult`` 并交由既有 ``summarize_judgment_search_coverage``
返回 ``JudgmentSearchCoverageSummary``。

诚实边界（术语与实现一致）：

- 这只是**候选供给页覆盖**装配：不是来源全集证明（``source_scope_verified``
  恒 False）、不是临床接受、也不是 professional_judgment 生产者。
- 调用方负责用 ``prepare_judgment_search_target`` 从当前数据库准备
  scope/target；scope/target 引用本身**不是**发生了真实模型调用的声明——
  是否真读过，只能由回执与原始回答的逐项一致证明到本装配所能核对的强度。
- 不新增证书 DTO 或存储框架；输出全部复用既有合同与覆盖函数。
- 跨 provider 的模型别名不支持：响应模型必须与请求模型逐字一致（忽略大小写
  与首尾空白），未知或不一致一律拒绝；无自动回退、无重试。
- 历史提示版本的回执原样保留但**不接纳**：既不重标版本也不混入当前语义。
- 合法地在不同页/不同上下文出现相同文本候选**不**被当作污染：本装配没有任何
  跨上下文重复文本启发式；每条候选只按其页/通道/逐字绑定核对。
"""

from __future__ import annotations

import hashlib

from pydantic import ValidationError

from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageSummary,
    JudgmentSearchLaneResult,
    JudgmentSearchPageIdentity,
    JudgmentSearchPageResult,
    JudgmentSearchScope,
)
from app.domain.contracts.page_review import PageReviewLane
from app.domain.judgment_search_coverage import summarize_judgment_search_coverage
from app.llm.judgment_search_reader import (
    JudgmentSearchReaderError,
    JudgmentSearchReaderReceipt,
    select_candidate_page_channels,
)

_MAIN_LANES = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)

__all__ = [
    "JudgmentSearchResultsError",
    "assemble_judgment_search_coverage",
]


class JudgmentSearchResultsError(ValueError):
    """回执与当前 scope/target 不一致、身份漂移或原始回答与绑定结果矛盾。"""


def _require_nonblank(value: str, message: str) -> str:
    stripped = (value or "").strip()
    if not stripped:
        raise JudgmentSearchResultsError(message)
    return stripped


def _page_key(page: JudgmentSearchPageIdentity) -> tuple[str, str, int]:
    return (
        page.source_document_version_id,
        page.page_artifact_id,
        page.page_number,
    )


def assemble_judgment_search_coverage(
    scope: JudgmentSearchScope,
    target_text: str,
    receipts: list[JudgmentSearchReaderReceipt],
) -> JudgmentSearchCoverageSummary:
    """核对回执与当前 scope/target 后装配原生覆盖摘要（语义见模块 docstring）。"""
    # model_copy 可绕过 frozen 验证器：scope 与回执都按转储重验证。
    try:
        scope = JudgmentSearchScope.model_validate(scope.model_dump())
    except ValidationError as exc:
        raise JudgmentSearchResultsError(
            f"冻结检索页域未通过合同重验证：{exc.error_count()} 项错误"
        ) from exc
    revalidated: list[JudgmentSearchReaderReceipt] = []
    for receipt in receipts:
        try:
            revalidated.append(
                JudgmentSearchReaderReceipt.model_validate(receipt.model_dump())
            )
        except ValidationError as exc:
            raise JudgmentSearchResultsError(
                f"回执未通过合同重验证（拒绝 model_copy 变造）："
                f"{exc.error_count()} 项错误"
            ) from exc

    stripped_target = target_text.strip()
    if not stripped_target:
        raise JudgmentSearchResultsError("目标文本不得为空白")
    target_sha256 = hashlib.sha256(stripped_target.encode("utf-8")).hexdigest()

    scope_pages = {page.order_key: page for page in scope.pages}
    lane_identities: dict[PageReviewLane, tuple[str, str, str]] = {}
    seen_lane_pages: set[tuple[PageReviewLane, tuple[str, str, int]]] = set()
    pages_by_lane: dict[
        PageReviewLane, list[JudgmentSearchPageResult]
    ] = {}

    for receipt in revalidated:
        if receipt.scope_sha256 != scope.scope_sha256:
            raise JudgmentSearchResultsError(
                "回执引用的范围哈希与当前冻结页域不一致"
            )
        if receipt.target_sha256 != target_sha256:
            raise JudgmentSearchResultsError(
                "回执目标哈希与当前准备的目标文本不一致"
            )

        requested = receipt.requested
        if requested.lane not in _MAIN_LANES:
            raise JudgmentSearchResultsError(
                "判断候选装配只支持 main-A/main-B 读道"
            )
        _require_nonblank(requested.provider, "回执读道 provider 不得为空白")
        _require_nonblank(requested.model, "回执读道 model 不得为空白")
        _require_nonblank(
            requested.reasoning_effort, "回执读道 reasoning_effort 不得为空白"
        )
        if requested.max_tokens <= 0:
            raise JudgmentSearchResultsError("回执读道完成预算必须为正数")
        response_model = _require_nonblank(
            receipt.response_model or "",
            "回执响应模型缺失或空白：响应身份未知即拒绝，不虚构、不忽略",
        )
        if response_model.strip().casefold() != requested.model.strip().casefold():
            raise JudgmentSearchResultsError(
                f"回执响应模型 {response_model} 与请求模型 {requested.model} "
                "不一致：别名不受支持，拒绝装配"
            )

        completion = receipt.completion
        if receipt.finish_reason != "stop" or completion.finish_reason != "stop":
            raise JudgmentSearchResultsError(
                "回执或原始完成调用未确认完整结束，拒绝装配部分结果"
            )
        if receipt.response_model != completion.response_model:
            raise JudgmentSearchResultsError(
                "回执镜像的响应模型与原始完成调用不一致"
            )
        if receipt.response_id != completion.response_id:
            raise JudgmentSearchResultsError(
                "回执镜像的响应 ID 与原始完成调用不一致"
            )
        actual_text_sha256 = hashlib.sha256(
            (completion.text or "").encode("utf-8")
        ).hexdigest()
        if receipt.completion_text_sha256 != actual_text_sha256:
            raise JudgmentSearchResultsError(
                "回执镜像的回答文本哈希与原始完成调用不一致"
            )

        key = _page_key(receipt.page)
        scope_page = scope_pages.get(key)
        if scope_page is None or receipt.page != scope_page:
            raise JudgmentSearchResultsError(
                f"回执页 {key} 不是当前冻结页域成员或身份不一致"
            )
        page_result = receipt.page_result
        if (
            page_result.source_document_version_id,
            page_result.page_artifact_id,
            page_result.page_number,
            page_result.page_image_sha256,
        ) != (
            receipt.page.source_document_version_id,
            receipt.page.page_artifact_id,
            receipt.page.page_number,
            receipt.page.page_image_sha256,
        ):
            raise JudgmentSearchResultsError(
                f"回执页结果身份与回执页身份不一致（{key}）"
            )
        lane_page = (requested.lane, key)
        if lane_page in seen_lane_pages:
            raise JudgmentSearchResultsError(
                f"同一读道同一页出现重复回执（{requested.lane.value} {key}）："
                "不按最后一条静默采纳，也不把重复当作第二个模型"
            )
        seen_lane_pages.add(lane_page)

        identity = (
            requested.provider.strip(),
            requested.model.strip(),
            requested.reasoning_effort.strip(),
        )
        previous = lane_identities.get(requested.lane)
        if previous is not None and previous != identity:
            raise JudgmentSearchResultsError(
                f"读道 {requested.lane.value} 各页的 provider/model/effort 不一致"
            )
        lane_identities[requested.lane] = identity

        # 用当前候选解析器重解原始回答：绑定页结果必须与原始回答的两条通道
        # 逐字段一致（含 uncertainty_note 与 coordinate_convention=unverified），
        # 不信任与原始回答矛盾的伪造结果；无坐标缩放、无引文修补、无重试。
        try:
            reparsed = select_candidate_page_channels(
                completion.text or "",
                prompt_version=receipt.prompt_version,
                scope_sha256=receipt.scope_sha256,
                target_sha256=receipt.target_sha256,
                requirement_id=scope.requirement_id,
                batch_targets=receipt.batch_targets,
            )
        except (JudgmentSearchReaderError, ValidationError, ValueError) as exc:
            raise JudgmentSearchResultsError(
                f"原始回答无法按当前候选合同解析：{exc}"
            ) from exc
        if (
            reparsed.handwritten != page_result.handwritten
            or reparsed.printed_analysis != page_result.printed_analysis
        ):
            raise JudgmentSearchResultsError(
                f"回执绑定的页结果与原始回答通道不一致（{key}），拒绝采信伪造结果"
            )
        pages_by_lane.setdefault(requested.lane, []).append(page_result)

    lane_results = []
    for lane in _MAIN_LANES:
        identity = lane_identities.get(lane)
        if identity is None:
            continue
        page_results = sorted(
            pages_by_lane[lane],
            key=lambda item: (
                item.source_document_version_id,
                item.page_artifact_id,
                item.page_number,
            ),
        )
        lane_results.append(
            JudgmentSearchLaneResult(
                scope_sha256=scope.scope_sha256,
                lane=lane,
                provider=identity[0],
                model=identity[1],
                reasoning_effort=identity[2],
                page_results=tuple(page_results),
            )
        )
    distinct_models = {
        (provider.casefold(), model.casefold())
        for provider, model, _effort in lane_identities.values()
    }
    if len(distinct_models) != len(lane_identities):
        raise JudgmentSearchResultsError(
            "两条读道使用相同 provider+model：同模型不构成独立双读；"
            "别名不受支持，无自动回退"
        )
    return summarize_judgment_search_coverage(scope, lane_results)
