"""R3 视觉事实来源合同与纯物化器（独立追加合同，未接入正式写入）。

本模块只冻结确定性校验与内容寻址身份，不含存储、文件路径或外部模型调用。
它把一次页级双主读对账后「已采信」的事实观察与手写批注物化为不可变、
内容寻址的视觉来源记录，严格绑定原页、来源文档版本、ClausePack、页级对账、
页覆盖处置与既有快照/完整处理修订权威。

诚实边界（术语与实现一致）：

- 本合同各模型 ``frozen`` 且列表字段全部为 ``tuple``；但上游 page-review
  合同对象并未冻结，``model_copy``/字段改写可以绕过其验证器。因此物化器在
  入口对所有输入按 ``model_validate(model_dump())`` 重新验证，来源可信度由
  内容寻址哈希与绑定校验共同保证，而不是由上游对象的可变性声明保证。
- 读道 ``observation`` 保留模型原始观察（含模型自报 bbox）作为原始出处；
  这些坐标未经真实性门禁认证。派生字段 ``locator`` 才是定位表示：精度固定
  为 ``page_excerpt``、不含任何坐标，且 ``excerpt_sha256`` 必须等于
  ``sha256(excerpt.encode())`` 的真实值。文本哈希与页图哈希严格分立，
  绝不允许把页图哈希写入任何文本哈希字段。
- 对账仍只由既有 ``reconcile_page_reviews`` 完成；本模块不实现第二种对账
  或关联算法。跨读道「归一化键不同」的已采信配对必须提供与
  ``reconciliation.association_text_sha256`` 哈希一致的
  ``PageAssociationSource``，并复用既有 ``source_aligned_fact_keys`` 结果
  作为配对资格；配对只按精确规范化同源身份（归一化字段 + 不含
  location_text 的上下文键 + 规范值/单位 + 原件异常标记）唯一推导，
  不做模糊匹配。既有原语只返回键集合，不返回配对：当同一同源身份在页上
  命中多个来源范围时，配对不唯一，本模块按歧义拒绝并把该边界留待
  所有者集成评审，而不是重新实现定位算法。

硬不变量：只物化已采信事实与已采信手写，绝不输出条款信号、NONE、
冲突或单读道内容；已采信目标不得同时出现在冲突记录中；冲突引用的页审
记录必须属于输入读道；不改写任何既有修订；不创建替代处理修订；本合同在
所有者集成评审前保持独立、不与正式写入连接。
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.domain.contracts.common import ContractModel, VersionedModel
from app.domain.contracts.page_review import (
    HandwritingKind,
    HandwritingObservation,
    PageDisposition,
    PageFactObservation,
    PageReconciliation,
    PageReviewLane,
    PageReviewRecord,
    SubjectPageCoverage,
)
from app.domain.page_source_association import (
    PageAssociationSource,
    source_aligned_fact_pairs,
)
from app.domain.publication import canonical_hash

PAGE_REVIEW_EVIDENCE_SOURCES_CONTRACT_VERSION = "page-review-evidence-sources/v1"

_SHA256 = r"^[0-9a-f]{64}$"
_MAIN_LANES = [PageReviewLane.MAIN_A, PageReviewLane.MAIN_B]


class PageVisualEvidenceSourceError(ValueError):
    """视觉来源物化的输入不一致、陈旧或绑定失败。"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_utc(value: datetime, field_name: str) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _excerpt_sha256(excerpt: str) -> str:
    return hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def _check_reading_binding(observation, locator: "VisualPageExcerptLocator") -> None:
    if locator.excerpt != observation.region.excerpt:
        raise ValueError("派生摘录定位必须与原始观察摘录完全一致")


# --------------------------------------------------------------------------- 定位与读道绑定


class VisualPageExcerptLocator(ContractModel):
    """派生定位表示：page_excerpt 精度、无坐标、携带摘录真实 sha256。"""

    model_config = ConfigDict(frozen=True)

    precision: Literal["page_excerpt"] = "page_excerpt"
    excerpt: str = Field(min_length=1)
    excerpt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_locator(self) -> "VisualPageExcerptLocator":
        if self.excerpt_sha256 != _excerpt_sha256(self.excerpt):
            raise ValueError("摘录哈希必须等于摘录原文的真实 sha256")
        return self


class _VisualReadingBase(ContractModel):
    """一条主读读道的逐字来源绑定（原始观察 + 派生无坐标定位）。"""

    model_config = ConfigDict(frozen=True)

    lane: PageReviewLane
    page_review_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"]
    prompt_version: str = Field(min_length=1)
    response_sha256: str = Field(pattern=_SHA256)
    locator: VisualPageExcerptLocator


class VisualFactReading(_VisualReadingBase):
    """已采信事实观察的读道绑定；``observation`` 保留原始模型出处。"""

    observation: PageFactObservation

    @model_validator(mode="after")
    def validate_reading(self) -> "VisualFactReading":
        _check_reading_binding(self.observation, self.locator)
        return self


class VisualHandwritingReading(_VisualReadingBase):
    """已采信手写批注的读道绑定；``observation`` 保留原始模型出处。"""

    observation: HandwritingObservation

    @model_validator(mode="after")
    def validate_reading(self) -> "VisualHandwritingReading":
        _check_reading_binding(self.observation, self.locator)
        return self


def _validate_reading_pair(readings) -> None:
    if [item.lane for item in sorted(readings, key=lambda item: item.lane.value)] != _MAIN_LANES:
        raise ValueError("视觉来源必须且只能绑定 main-A 与 main-B 两条主读读道")
    if len({item.page_review_id for item in readings}) != 2:
        raise ValueError("视觉来源必须引用两份不同的页级判读记录")
    identities = [(item.provider, item.model) for item in readings]
    if len(set(identities)) != len(identities):
        raise ValueError("相同模型身份的两个读道不构成独立双主读")


# --------------------------------------------------------------------------- 来源记录


def visual_fact_source_id(
    *,
    normalization_keys: Sequence[str],
    normalized_value: str,
    normalized_unit: str | None,
    readings: Sequence[VisualFactReading],
) -> str:
    """已采信事实来源的确定性内容身份（读道按读道名排序）。"""
    return "visual-fact:" + canonical_hash({
        "identity": "visual_fact_source/v1",
        "normalization_keys": list(normalization_keys),
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "readings": [
            item.model_dump(mode="json")
            for item in sorted(readings, key=lambda item: item.lane.value)
        ],
    })[:32]


class VisualFactSource(ContractModel):
    """一条已采信事实的不可变视觉来源：双主读逐字绑定 + 内容寻址。

    同键双读 ``normalization_keys`` 只有一个键；来源关联接受的跨键配对
    恰有两个键（各读道一条）。来源级规范值/单位必须逐条等于读道观察值：
    内容寻址不是语义校验的替代品。
    """

    model_config = ConfigDict(frozen=True)

    fact_source_id: str = Field(pattern=r"^visual-fact:[0-9a-f]{32}$")
    normalization_keys: tuple[str, ...]
    normalized_value: str = Field(min_length=1)
    normalized_unit: str | None = None
    readings: tuple[VisualFactReading, VisualFactReading]

    @model_validator(mode="after")
    def validate_source(self) -> "VisualFactSource":
        _validate_reading_pair(self.readings)
        keys = self.normalization_keys
        if len(keys) not in (1, 2) or keys != tuple(sorted(set(keys))):
            raise ValueError("来源归一化键必须去重排序且不超过两个")
        observed_keys = {item.observation.normalization_key for item in self.readings}
        if not observed_keys <= set(keys):
            raise ValueError("读道观察的归一化键必须属于来源归一化键集合")
        if len(keys) == 1 and len(observed_keys) != 1:
            raise ValueError("单键来源的两条读道必须携带同一归一化键")
        if len(keys) == 2 and len(observed_keys) != 2:
            raise ValueError("跨键配对来源的两条读道必须分别携带两个归一化键")
        for item in self.readings:
            if (item.observation.normalized_value, item.observation.normalized_unit) != (
                self.normalized_value,
                self.normalized_unit,
            ):
                raise ValueError("读道观察的规范值/单位必须与来源记录一致")
        expected = visual_fact_source_id(
            normalization_keys=keys,
            normalized_value=self.normalized_value,
            normalized_unit=self.normalized_unit,
            readings=self.readings,
        )
        if self.fact_source_id != expected:
            raise ValueError("事实来源 ID 必须由读道内容确定性计算")
        return self


def visual_handwriting_source_id(
    *,
    kind: HandwritingKind,
    normalization_key: str,
    normalized_text: str,
    readings: Sequence[VisualHandwritingReading],
) -> str:
    """已采信手写来源的确定性内容身份（读道按读道名排序）。"""
    return "visual-handwriting:" + canonical_hash({
        "identity": "visual_handwriting_source/v1",
        "kind": kind.value,
        "normalization_key": normalization_key,
        "normalized_text": normalized_text,
        "readings": [
            item.model_dump(mode="json")
            for item in sorted(readings, key=lambda item: item.lane.value)
        ],
    })[:32]


class VisualHandwritingSource(ContractModel):
    """一条已采信手写批注的不可变视觉来源：双主读逐字绑定 + 内容寻址。"""

    model_config = ConfigDict(frozen=True)

    handwriting_source_id: str = Field(pattern=r"^visual-handwriting:[0-9a-f]{32}$")
    kind: HandwritingKind
    normalization_key: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    readings: tuple[VisualHandwritingReading, VisualHandwritingReading]

    @model_validator(mode="after")
    def validate_source(self) -> "VisualHandwritingSource":
        _validate_reading_pair(self.readings)
        if any(
            item.observation.normalization_key != self.normalization_key
            for item in self.readings
        ):
            raise ValueError("读道观察的归一化键与来源记录不一致")
        if any(
            (item.observation.kind, item.observation.normalized_text)
            != (self.kind, self.normalized_text)
            for item in self.readings
        ):
            raise ValueError("读道观察的手写类型/规范文字必须与来源记录一致")
        expected = visual_handwriting_source_id(
            kind=self.kind,
            normalization_key=self.normalization_key,
            normalized_text=self.normalized_text,
            readings=self.readings,
        )
        if self.handwriting_source_id != expected:
            raise ValueError("手写来源 ID 必须由读道内容确定性计算")
        return self


def page_visual_evidence_source_set_id(
    *,
    page_artifact_id: str,
    source_document_version_id: str,
    page_number: int,
    page_image_sha256: str,
    clause_pack_id: str,
    clause_pack_sha256: str,
    reconciliation_id: str,
    coverage_id: str,
    evidence_snapshot_id: str,
    evidence_processing_revision_id: str,
    page_text_sha256: str | None,
    fact_source_ids: Sequence[str],
    handwriting_source_ids: Sequence[str],
) -> str:
    """页级视觉来源集合的确定性内容身份（来源按 ID 排序；不含 created_at）。"""
    return "visual-source-set:" + canonical_hash({
        "identity": "page_visual_evidence_source_set/v1",
        "page": {
            "page_artifact_id": page_artifact_id,
            "source_document_version_id": source_document_version_id,
            "page_number": page_number,
            "page_image_sha256": page_image_sha256,
        },
        "clause_pack": {
            "clause_pack_id": clause_pack_id,
            "clause_pack_sha256": clause_pack_sha256,
        },
        "reconciliation_id": reconciliation_id,
        "coverage_id": coverage_id,
        "evidence_snapshot_id": evidence_snapshot_id,
        "evidence_processing_revision_id": evidence_processing_revision_id,
        "page_text_sha256": page_text_sha256,
        "fact_source_ids": sorted(fact_source_ids),
        "handwriting_source_ids": sorted(handwriting_source_ids),
    })[:32]


class PageVisualEvidenceSourceSet(VersionedModel):
    """一页已采信视觉观察的不可变来源集合（内容寻址，追加写）。"""

    contract_version: Literal["page-review-evidence-sources/v1"] = (
        PAGE_REVIEW_EVIDENCE_SOURCES_CONTRACT_VERSION
    )
    source_set_id: str = Field(pattern=r"^visual-source-set:[0-9a-f]{32}$")
    page_artifact_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    clause_pack_id: str = Field(pattern=r"^clause-pack:[0-9a-f]{32}$")
    clause_pack_sha256: str = Field(pattern=_SHA256)
    reconciliation_id: str = Field(min_length=1)
    coverage_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_processing_revision_id: str = Field(min_length=1)
    page_text_sha256: str | None = Field(
        default=None, pattern=_SHA256, exclude_if=lambda value: value is None
    )
    fact_sources: tuple[VisualFactSource, ...] = ()
    handwriting_sources: tuple[VisualHandwritingSource, ...] = ()
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def validate_set(self) -> "PageVisualEvidenceSourceSet":
        _require_utc(self.created_at, "PageVisualEvidenceSourceSet.created_at")
        if self.page_text_sha256 is not None and self.page_text_sha256 == self.page_image_sha256:
            raise ValueError("来源文本哈希与页图哈希必须相互独立，不得写入同一哈希")
        source_ids = [item.fact_source_id for item in self.fact_sources] + [
            item.handwriting_source_id for item in self.handwriting_sources
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("视觉来源集合内来源 ID 不得重复")
        expected = page_visual_evidence_source_set_id(
            page_artifact_id=self.page_artifact_id,
            source_document_version_id=self.source_document_version_id,
            page_number=self.page_number,
            page_image_sha256=self.page_image_sha256,
            clause_pack_id=self.clause_pack_id,
            clause_pack_sha256=self.clause_pack_sha256,
            reconciliation_id=self.reconciliation_id,
            coverage_id=self.coverage_id,
            evidence_snapshot_id=self.evidence_snapshot_id,
            evidence_processing_revision_id=self.evidence_processing_revision_id,
            page_text_sha256=self.page_text_sha256,
            fact_source_ids=[item.fact_source_id for item in self.fact_sources],
            handwriting_source_ids=[
                item.handwriting_source_id for item in self.handwriting_sources
            ],
        )
        if self.source_set_id != expected:
            raise ValueError("来源集合 ID 必须由页绑定与来源集合确定性计算")
        return self


# --------------------------------------------------------------------------- 纯物化器


def _unique_page_identity(records: Sequence[PageReviewRecord]) -> dict[str, object]:
    fields = (
        "page_artifact_id",
        "source_document_version_id",
        "page_number",
        "page_image_sha256",
        "clause_pack_id",
        "clause_pack_sha256",
    )
    for field in fields:
        if len({getattr(record, field) for record in records}) != 1:
            raise PageVisualEvidenceSourceError(
                "同一次视觉来源物化必须绑定同一页、同一资料版本、同一页图与同一条款包"
            )
    return {field: getattr(records[0], field) for field in fields}


def _pair_accepted_facts(
    by_lane: dict[PageReviewLane, PageReviewRecord],
    accepted_keys: Sequence[str],
    association_pairs: list[tuple[PageFactObservation, PageFactObservation]] | None,
) -> list[tuple[PageFactObservation, PageFactObservation]]:
    """同键双读直接配对；跨键余项仅按已绑定来源关联的精确同源身份配对。"""
    lane_a = by_lane[PageReviewLane.MAIN_A].facts
    lane_b = by_lane[PageReviewLane.MAIN_B].facts
    pairs: list[tuple[PageFactObservation, PageFactObservation]] = []
    consumed_keys: set[str] = set()
    consumed_obs: set[tuple[PageReviewLane, str]] = set()
    for key in sorted(accepted_keys):
        if key in consumed_keys:
            continue
        in_a = [item for item in lane_a if item.normalization_key == key]
        in_b = [item for item in lane_b if item.normalization_key == key]
        if len(in_a) > 1 or len(in_b) > 1:
            raise PageVisualEvidenceSourceError(
                "已采信事实键在读道中存在多个候选观察，无法唯一绑定来源目标"
            )
        if len(in_a) == 1 and len(in_b) == 1:
            pairs.append((in_a[0], in_b[0]))
            consumed_keys.add(key)
            consumed_obs.update({
                (PageReviewLane.MAIN_A, in_a[0].observation_id),
                (PageReviewLane.MAIN_B, in_b[0].observation_id),
            })
            continue
        if not in_a and not in_b:
            raise PageVisualEvidenceSourceError(
                "已采信事实键在读道中无匹配观察：对账结果对输入记录已陈旧或输入不一致"
            )
        if association_pairs is None:
            raise PageVisualEvidenceSourceError(
                "已采信事实键未在两条主读同时出现；必须提供与对账记录"
                " association_text_sha256 绑定的 PageAssociationSource 才能按来源关联配对"
            )
        if in_a:
            holder, holder_lane, partner_pool, partner_lane = (
                in_a[0], PageReviewLane.MAIN_A, lane_b, PageReviewLane.MAIN_B
            )
        else:
            holder, holder_lane, partner_pool, partner_lane = (
                in_b[0], PageReviewLane.MAIN_B, lane_a, PageReviewLane.MAIN_A
            )
        holder_index = 0 if holder_lane == PageReviewLane.MAIN_A else 1
        # 伙伴只承担视觉来源绑定：对账可能只采信跨键配对的单侧键（另一侧
        # 因同身份重复被列为歧义），因此不要求伙伴键本身已被采信，只要求
        # 未被消费且来源关联唯一命中。
        candidates = [
            pair[1 - holder_index] for pair in association_pairs
            if pair[holder_index] == holder
            and (item := pair[1 - holder_index]).normalization_key not in consumed_keys
            and (partner_lane, item.observation_id) not in consumed_obs
        ]
        if not candidates:
            raise PageVisualEvidenceSourceError(
                "来源关联无法为已采信事实键找到精确同源的唯一对应观察"
            )
        if len(candidates) > 1:
            raise PageVisualEvidenceSourceError(
                "来源关联在对应读道命中多个同源观察，配对不唯一，拒绝物化"
            )
        partner = candidates[0]
        pair = (holder, partner) if holder_lane == PageReviewLane.MAIN_A else (partner, holder)
        pairs.append(pair)
        consumed_keys.update({key, partner.normalization_key})
        consumed_obs.update({
            (holder_lane, holder.observation_id),
            (partner_lane, partner.observation_id),
        })
    return pairs


def _check_conflicts_binding(
    reconciliation: PageReconciliation, review_ids: set[str]
) -> None:
    for group in (
        reconciliation.fact_conflicts,
        reconciliation.signal_conflicts,
        reconciliation.handwriting_conflicts,
    ):
        for conflict in group:
            if set(conflict.page_review_ids) - review_ids:
                raise PageVisualEvidenceSourceError("对账冲突引用了未知页审记录")
    # Existing conflicts group all observations of a field, including accepted
    # observations at other timepoints. Only an entirely accepted group is invalid.
    accepted = set(reconciliation.accepted_fact_keys)
    if any(set(conflict.normalization_keys) and set(conflict.normalization_keys) <= accepted
           for conflict in reconciliation.fact_conflicts):
        raise PageVisualEvidenceSourceError("已采信事实键同时记入冲突记录，输入自相矛盾")
    handwriting_conflict_keys = {
        key for conflict in reconciliation.handwriting_conflicts
        for key in conflict.normalization_keys
    }
    for representative in reconciliation.accepted_handwriting:
        if representative.normalization_key in handwriting_conflict_keys:
            raise PageVisualEvidenceSourceError("已采信手写键同时记入冲突记录，输入自相矛盾")


def materialize_page_visual_evidence_sources(
    reviews: Sequence[PageReviewRecord],
    reconciliation: PageReconciliation,
    coverage: SubjectPageCoverage,
    *,
    page_text_sha256: str | None = None,
    association_source: PageAssociationSource | None = None,
) -> PageVisualEvidenceSourceSet:
    """把一页双主读对账后的已采信事实/手写物化为不可变视觉来源集合。

    纯函数：不写库、不改既有修订、不重新对账。所有输入先经
    ``model_validate(model_dump())`` 重验证再参与绑定；对账结果与页覆盖处置
    都是显式输入并逐一做绑定校验。``page_text_sha256`` 只允许携带 OCR 侧车
    文本版本哈希，与页图哈希严格分立，不参与摘录核对。
    ``association_source`` 为可选显式输入：其哈希必须等于
    ``reconciliation.association_text_sha256``，配对资格复用既有
    ``source_aligned_fact_keys``；不提供时仅支持同键双读模式。
    """
    # 上游合同未冻结：model_copy/字段改写可绕过验证器，入口按 dump 重验证。
    reviews = [PageReviewRecord.model_validate(item.model_dump()) for item in reviews]
    reconciliation = PageReconciliation.model_validate(reconciliation.model_dump())
    coverage = SubjectPageCoverage.model_validate(coverage.model_dump())
    if association_source is not None:
        association_source = PageAssociationSource.model_validate(
            association_source.model_dump()
        )

    if len(reviews) != 2 or len({record.lane for record in reviews}) != 2:
        raise PageVisualEvidenceSourceError("视觉来源物化必须且只能接受两条不同读道的主读记录")
    by_lane = {record.lane: record for record in reviews}
    if set(by_lane) != set(_MAIN_LANES):
        raise PageVisualEvidenceSourceError("视觉来源物化只接受 main-A 与 main-B 主读读道")
    identity = _unique_page_identity(reviews)

    if len({(record.provider, record.model) for record in reviews}) != 2:
        raise PageVisualEvidenceSourceError(
            "两条主读读道不得使用相同模型身份；相同模型不构成独立双读"
        )

    if reconciliation.page_artifact_id != identity["page_artifact_id"]:
        raise PageVisualEvidenceSourceError("对账记录不属于当前页工件")
    if reconciliation.clause_pack_sha256 != identity["clause_pack_sha256"]:
        raise PageVisualEvidenceSourceError("对账记录与页级判读的条款包版本不一致")
    if sorted(reconciliation.page_review_ids) != sorted(
        record.page_review_id for record in reviews
    ):
        raise PageVisualEvidenceSourceError("对账记录引用的页审记录与输入读道不一致")
    _check_conflicts_binding(reconciliation, {record.page_review_id for record in reviews})

    entry = next(
        (item for item in coverage.entries if item.page_artifact_id == identity["page_artifact_id"]),
        None,
    )
    if entry is None:
        raise PageVisualEvidenceSourceError("页覆盖中未找到当前页工件的处置记录")
    if (entry.source_document_version_id, entry.page_number) != (
        identity["source_document_version_id"],
        identity["page_number"],
    ):
        raise PageVisualEvidenceSourceError("页覆盖处置的资料版本或页码与判读记录不一致")
    if coverage.clause_pack_sha256 != identity["clause_pack_sha256"]:
        raise PageVisualEvidenceSourceError("页覆盖与页级判读的条款包版本不一致")
    if entry.disposition != PageDisposition.ACCEPTED:
        raise PageVisualEvidenceSourceError("只有页覆盖中已采信页面才能物化视觉事实来源")
    if entry.reconciliation_id != reconciliation.reconciliation_id:
        raise PageVisualEvidenceSourceError("页覆盖处置绑定的对账记录与输入对账记录不一致")

    if page_text_sha256 is not None and page_text_sha256 == identity["page_image_sha256"]:
        raise PageVisualEvidenceSourceError("来源文本哈希与页图哈希必须相互独立，不得写入同一哈希")

    association_pairs = None
    if association_source is not None:
        if reconciliation.association_text_sha256 != association_source.text_sha256:
            raise PageVisualEvidenceSourceError(
                "来源关联文本哈希必须与对账记录的 association_text_sha256 一致"
            )
        if (association_source.source_document_version_id, association_source.page_number) != (
            identity["source_document_version_id"],
            identity["page_number"],
        ):
            raise PageVisualEvidenceSourceError("来源关联文本不属于当前文档页")
        try:
            association_pairs = source_aligned_fact_pairs(reviews, association_source)
        except ValueError as exc:
            raise PageVisualEvidenceSourceError(str(exc)) from exc

    def fact_reading(record: PageReviewRecord, observation: PageFactObservation):
        excerpt = observation.region.excerpt
        return VisualFactReading(
            lane=record.lane,
            page_review_id=record.page_review_id,
            provider=record.provider,
            model=record.model,
            reasoning_effort=record.reasoning_effort,
            prompt_version=record.prompt_version,
            response_sha256=record.response_sha256,
            observation=observation,
            locator=VisualPageExcerptLocator(
                excerpt=excerpt, excerpt_sha256=_excerpt_sha256(excerpt)
            ),
        )

    fact_sources: list[VisualFactSource] = []
    for obs_a, obs_b in _pair_accepted_facts(
        by_lane, reconciliation.accepted_fact_keys, association_pairs
    ):
        keys = tuple(sorted({obs_a.normalization_key, obs_b.normalization_key}))
        readings = tuple(
            fact_reading(record, obs_a if record.lane == PageReviewLane.MAIN_A else obs_b)
            for record in reviews
        )
        fact_sources.append(
            VisualFactSource(
                fact_source_id=visual_fact_source_id(
                    normalization_keys=keys,
                    normalized_value=obs_a.normalized_value,
                    normalized_unit=obs_a.normalized_unit,
                    readings=readings,
                ),
                normalization_keys=keys,
                normalized_value=obs_a.normalized_value,
                normalized_unit=obs_a.normalized_unit,
                readings=readings,
            )
        )

    def handwriting_reading(record: PageReviewRecord, observation: HandwritingObservation):
        excerpt = observation.region.excerpt
        return VisualHandwritingReading(
            lane=record.lane,
            page_review_id=record.page_review_id,
            provider=record.provider,
            model=record.model,
            reasoning_effort=record.reasoning_effort,
            prompt_version=record.prompt_version,
            response_sha256=record.response_sha256,
            observation=observation,
            locator=VisualPageExcerptLocator(
                excerpt=excerpt, excerpt_sha256=_excerpt_sha256(excerpt)
            ),
        )

    handwriting_sources: list[VisualHandwritingSource] = []
    for representative in reconciliation.accepted_handwriting:
        matches = {
            lane: [
                item for item in record.handwriting
                if item.normalization_key == representative.normalization_key
            ]
            for lane, record in by_lane.items()
        }
        for found in matches.values():
            if len(found) > 1:
                raise PageVisualEvidenceSourceError(
                    "已采信手写键在读道中存在多个候选观察，无法唯一绑定来源目标"
                )
            if not found:
                raise PageVisualEvidenceSourceError(
                    "已采信手写键在读道中无匹配观察：对账结果对输入记录已陈旧或输入不一致"
                )
        lane_observations = [
            matches[PageReviewLane.MAIN_A][0],
            matches[PageReviewLane.MAIN_B][0],
        ]
        if representative not in lane_observations:
            raise PageVisualEvidenceSourceError(
                "已采信手写记录必须逐字来自其中一条主读读道，不得由物化器合成"
            )
        readings = tuple(
            handwriting_reading(record, matches[record.lane][0]) for record in reviews
        )
        handwriting_sources.append(
            VisualHandwritingSource(
                handwriting_source_id=visual_handwriting_source_id(
                    kind=representative.kind,
                    normalization_key=representative.normalization_key,
                    normalized_text=representative.normalized_text,
                    readings=readings,
                ),
                kind=representative.kind,
                normalization_key=representative.normalization_key,
                normalized_text=representative.normalized_text,
                readings=readings,
            )
        )

    set_id = page_visual_evidence_source_set_id(
        page_artifact_id=identity["page_artifact_id"],
        source_document_version_id=identity["source_document_version_id"],
        page_number=identity["page_number"],
        page_image_sha256=identity["page_image_sha256"],
        clause_pack_id=identity["clause_pack_id"],
        clause_pack_sha256=identity["clause_pack_sha256"],
        reconciliation_id=reconciliation.reconciliation_id,
        coverage_id=coverage.coverage_id,
        evidence_snapshot_id=coverage.evidence_snapshot_id,
        evidence_processing_revision_id=coverage.evidence_processing_revision_id,
        page_text_sha256=page_text_sha256,
        fact_source_ids=[item.fact_source_id for item in fact_sources],
        handwriting_source_ids=[item.handwriting_source_id for item in handwriting_sources],
    )
    return PageVisualEvidenceSourceSet(
        source_set_id=set_id,
        page_artifact_id=identity["page_artifact_id"],
        source_document_version_id=identity["source_document_version_id"],
        page_number=identity["page_number"],
        page_image_sha256=identity["page_image_sha256"],
        clause_pack_id=identity["clause_pack_id"],
        clause_pack_sha256=identity["clause_pack_sha256"],
        reconciliation_id=reconciliation.reconciliation_id,
        coverage_id=coverage.coverage_id,
        evidence_snapshot_id=coverage.evidence_snapshot_id,
        evidence_processing_revision_id=coverage.evidence_processing_revision_id,
        page_text_sha256=page_text_sha256,
        fact_sources=tuple(fact_sources),
        handwriting_sources=tuple(handwriting_sources),
    )


__all__ = [
    "PAGE_REVIEW_EVIDENCE_SOURCES_CONTRACT_VERSION",
    "PageVisualEvidenceSourceError",
    "PageVisualEvidenceSourceSet",
    "VisualFactReading",
    "VisualFactSource",
    "VisualHandwritingReading",
    "VisualHandwritingSource",
    "VisualPageExcerptLocator",
    "materialize_page_visual_evidence_sources",
    "page_visual_evidence_source_set_id",
    "visual_fact_source_id",
    "visual_handwriting_source_id",
]
