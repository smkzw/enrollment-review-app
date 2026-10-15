"""研究者书面判断检索的纯覆盖核验（CANDIDATE-only，无存储、无模型调用）。

``summarize_judgment_search_coverage`` 对给定 ``JudgmentSearchScope`` 与两条独立
main-A/main-B 读道的候选检索结果做确定性比对：

- 直接拒绝（``JudgmentSearchCoverageError``）：范围哈希不一致、超出来源范围之外的
  多余页、页图哈希与范围身份不符、读道重复、两条读道使用相同 provider+model
  （忽略首尾空白与大小写后仍相同即拒绝；同模型不同推理强度亦不构成独立双读；
  该比较不证明跨 provider 别名消解）、以及模型层形状矛盾
  （found 空摘录 / not_found 或 unreadable 携带摘录等，在合同层已拒绝）。
- 覆盖不完整（返回 ``coverage_incomplete``，绝不折叠成 not_found 或判断缺失）：
  范围内页在某条已提交读道上无逐页结果、unreadable、ambiguous、或整条读道缺席。
  ambiguous 缺口按原样携带全部暂定摘录，与 found 候选并列保留，绝不只留第一条。
- 仅当范围内每一页都有两条独立有效记录、且手写与打印分析两条通道在两条读道上
  均显式 not_found 时，返回 ``all_supplied_pages_searched_without_candidate``；
  任一 found 候选存在时返回 ``candidates_present`` 并原样保留全部 found 摘录与
  未闭合缺口。

诚实边界：范围由后续仓储构建器提供，本核验不证明给定范围覆盖全部适格临床来源；
输出恒携带 ``source_scope_verified=False``、``product_acceptance=False``、
``professional_judgment_absence_proven=False``。本模块只产出检索候选与覆盖状态，
绝不产生入排满足、适用性或 professional_judgment 缺口。
"""
from __future__ import annotations

from collections.abc import Sequence

from app.domain.contracts.judgment_search import (
    JudgmentSearchChannel,
    JudgmentSearchChannelGap,
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
    JudgmentSearchDisposition,
    JudgmentSearchExcerptCandidate,
    JudgmentSearchFoundCandidate,
    JudgmentSearchLane,
    JudgmentSearchLanePageGap,
    JudgmentSearchLaneResult,
    JudgmentSearchPageResult,
    JudgmentSearchScope,
)

#: 逐页结果中两条检索通道的确定性遍历顺序。
_CHANNELS = (JudgmentSearchChannel.HANDWRITTEN, JudgmentSearchChannel.PRINTED_ANALYSIS)

_ALL_LANES = (JudgmentSearchLane.MAIN_A, JudgmentSearchLane.MAIN_B)


class JudgmentSearchCoverageError(ValueError):
    """候选检索结果与冻结页域不一致、读道身份重复或其他形状矛盾。"""


def summarize_judgment_search_coverage(
    scope: JudgmentSearchScope,
    lane_results: Sequence[JudgmentSearchLaneResult],
) -> JudgmentSearchCoverageSummary:
    """比对冻结页域与两条独立读道的检索候选，返回纯覆盖核验摘要。

    纯函数：不写库、不调用模型、不推导时间戳。输入先按 ``model_validate``
    重新验证再参与比对（上游合同对象的可变性不作为信任依据）。
    """
    scope = JudgmentSearchScope.model_validate(scope.model_dump())
    lane_results = [
        JudgmentSearchLaneResult.model_validate(item.model_dump())
        for item in lane_results
    ]

    if len(lane_results) > len(_ALL_LANES):
        raise JudgmentSearchCoverageError("判断检索至多接受 main-A 与 main-B 两条读道")
    by_lane: dict[JudgmentSearchLane, JudgmentSearchLaneResult] = {}
    for result in lane_results:
        if result.lane in by_lane:
            raise JudgmentSearchCoverageError("同一条读道不得重复提交检索结果")
        if result.scope_sha256 != scope.scope_sha256:
            raise JudgmentSearchCoverageError(
                "读道检索结果引用的范围哈希与冻结页域不一致"
            )
        by_lane[result.lane] = result
    identities = [
        (result.provider.casefold(), result.model.casefold())
        for result in lane_results
    ]
    if len(identities) != len(set(identities)):
        raise JudgmentSearchCoverageError(
            "两条读道不得使用相同 provider+model 身份（大小写/空白差异不构成独立）；"
            "同模型不构成独立双读。别名消解属真实路由核验，不在本核验范围"
        )

    scope_pages = {page.order_key: page for page in scope.pages}
    missing_lanes = tuple(
        lane for lane in _ALL_LANES if lane not in by_lane
    )

    found_candidates: list[JudgmentSearchFoundCandidate] = []
    pages_without_lane_result: list[JudgmentSearchLanePageGap] = []
    unreadable_channels: list[JudgmentSearchChannelGap] = []
    ambiguous_channels: list[JudgmentSearchChannelGap] = []

    for lane in _ALL_LANES:
        result = by_lane.get(lane)
        if result is None:
            continue
        covered_keys: set[tuple[str, str, int]] = set()
        for page_result in sorted(
            result.page_results, key=lambda item: item.order_key
        ):
            key = page_result.order_key
            scope_page = scope_pages.get(key)
            if scope_page is None:
                raise JudgmentSearchCoverageError(
                    "读道检索结果包含来源范围之外的页，不得作为覆盖证据"
                )
            if page_result.page_image_sha256 != scope_page.page_image_sha256:
                raise JudgmentSearchCoverageError(
                    "逐页结果的页图哈希与冻结页域身份不一致"
                )
            covered_keys.add(key)
            for channel in _CHANNELS:
                channel_result = page_result.channel_result(channel)
                if channel_result.disposition == JudgmentSearchDisposition.FOUND:
                    found_candidates.append(
                        JudgmentSearchFoundCandidate(
                            lane=lane,
                            provider=result.provider,
                            model=result.model,
                            source_document_version_id=page_result.source_document_version_id,
                            page_artifact_id=page_result.page_artifact_id,
                            page_number=page_result.page_number,
                            page_image_sha256=page_result.page_image_sha256,
                            channel=channel,
                            candidates=channel_result.candidates,
                        )
                    )
                elif channel_result.disposition == JudgmentSearchDisposition.UNREADABLE:
                    unreadable_channels.append(
                        _channel_gap(
                            lane, page_result, channel,
                            disposition=channel_result.disposition,
                        )
                    )
                elif channel_result.disposition == JudgmentSearchDisposition.AMBIGUOUS:
                    ambiguous_channels.append(
                        _channel_gap(
                            lane, page_result, channel,
                            disposition=channel_result.disposition,
                            tentative_excerpts=channel_result.candidates,
                        )
                    )
        for key in sorted(set(scope_pages) - covered_keys):
            pages_without_lane_result.append(
                JudgmentSearchLanePageGap(
                    lane=lane,
                    source_document_version_id=key[0],
                    page_artifact_id=key[1],
                    page_number=key[2],
                )
            )

    if found_candidates:
        status = JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    elif (
        missing_lanes
        or pages_without_lane_result
        or unreadable_channels
        or ambiguous_channels
    ):
        status = JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    else:
        status = (
            JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
        )
    return JudgmentSearchCoverageSummary(
        scope_sha256=scope.scope_sha256,
        requirement_id=scope.requirement_id,
        status=status,
        found_candidates=tuple(found_candidates),
        missing_lanes=missing_lanes,
        pages_without_lane_result=tuple(pages_without_lane_result),
        unreadable_channels=tuple(unreadable_channels),
        ambiguous_channels=tuple(ambiguous_channels),
    )


def _channel_gap(
    lane: JudgmentSearchLane,
    page_result: JudgmentSearchPageResult,
    channel: JudgmentSearchChannel,
    *,
    disposition: JudgmentSearchDisposition,
    tentative_excerpts: Sequence[JudgmentSearchExcerptCandidate] = (),
) -> JudgmentSearchChannelGap:
    return JudgmentSearchChannelGap(
        lane=lane,
        source_document_version_id=page_result.source_document_version_id,
        page_artifact_id=page_result.page_artifact_id,
        page_number=page_result.page_number,
        channel=channel,
        disposition=disposition,
        tentative_excerpts=tuple(tentative_excerpts),
    )


__all__ = [
    "JudgmentSearchCoverageError",
    "summarize_judgment_search_coverage",
]
