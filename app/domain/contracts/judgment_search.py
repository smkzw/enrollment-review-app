"""研究者书面判断跨文件检索的最小候选合同（CANDIDATE-only，纯校验，无存储）。

本模块只冻结确定性校验与内容寻址身份，不含存储、文件路径或外部模型调用：

- ``JudgmentSearchScope``        冻结检索页域：绑定不可变权威元组
                                （``FactAuthority``）、 requirement 身份与逐页来源身份
                                （资料版本、页工件、页码、页图 SHA256）；内容寻址范围哈希。
- ``JudgmentSearchLaneResult``   一条独立 main-A/main-B 读道检索结果：引用精确范围哈希与
                                provider/model 身份（附 reasoning_effort 审计字段），每个被
                                检索页恰有一条逐页结果。
- ``JudgmentSearchPageResult``   单页结果：手写批注与打印病历分析两条检索通道必须齐备，
                                处置为 found / not_found / unreadable / ambiguous；found
                                携带非空候选摘录集合，ambiguous 可保留零或多条暂定摘录。
- ``JudgmentSearchCoverageSummary`` 纯覆盖核验输出（见
                                ``app.domain.judgment_search_coverage``）。

诚实边界（术语与实现一致）：

- 这是模型检索候选合同，不是证明 DTO。found 候选绝不构成入排满足、适用性或临床
  意义判断；not_found 绝不构成研究者书面判断缺失的证明。本模块不输出
  professional_judgment 缺口，也不产生任何采信或接受结论。
- 一页/一通道可含多条独立判断摘录：``JudgmentSearchChannelResult.candidates``
  以元组整体保留，覆盖摘要原样投影全部摘录，绝不静默只留第一条。
  ambiguous 的暂定摘录始终停留在歧义集合（``ambiguous_channels``）中，
  绝不在本合同内晋升为 found。
- 范围由后续仓储构建器提供。本合同无法证明给定范围覆盖全部适格临床来源；
  ``JudgmentSearchCoverageSummary.source_scope_verified`` 恒为 ``False``。
- 范围只接受显式逐页身份清单：没有按可读性、日期或文档类别过滤的字段，
  不可读或日期不明的资料无法被静默排除——要么显式在列，要么范围本身不完整。
  同一来源页只允许一个身份：同一资料版本同一页码出现两个页工件、或同一页工件
  复用于不同页/文档，均为来源页身份冲突并直接拒绝。
- found 必须携带来源绑定的逐字摘录集合；not_found / unreadable 不得携带任何摘录，
  绝不虚构"未找到"的原文。不携带任何由上传时间推断的时间戳。
- provider/model 身份比较忽略首尾空白与大小写，仅用于拒绝同一身份伪装成第二条
  独立读道；这不证明跨 provider 的模型别名消解，真实路由身份核验仍是
  仓储/运行时职责。``reasoning_effort`` 仅为审计元数据，绝不参与独立性比较。
"""
from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, ValidationInfo, field_validator, model_validator

from .common import ContractModel
from .enums import StableEnum
from .evidence import BoundingBox
from .facts import FactAuthority

JUDGMENT_SEARCH_CONTRACT_VERSION = "judgment-search/v1"

_SHA256 = r"^[0-9a-f]{64}$"

class JudgmentSearchModel(ContractModel):
    """判断检索合同基类：与 legacy ``fixture/v1`` 及 Phase 5 事实合同明确区分。"""

    schema_version: Literal["judgment-search/v1"] = JUDGMENT_SEARCH_CONTRACT_VERSION


def _normalize_nonblank(value: str, field_name: str) -> str:
    """审计/身份字符串：拒绝纯空白并归一化首尾空白（比较与存储一致）。"""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} 不得为空白")
    return stripped


def _check_page_identity_collisions(identities, *, label: str) -> None:
    """来源页身份唯一性：一页一个身份，身份冲突不是两页。

    - 精确重复（版本+工件+页码）不得出现；
    - 同一资料版本同一页码不得由两个页工件代表；
    - 同一页工件不得复用于不同页或不同文档。
    """
    seen: set[tuple[str, str, int]] = set()
    doc_page_to_artifact: dict[tuple[str, int], str] = {}
    artifact_to_doc_page: dict[str, tuple[str, int]] = {}
    for identity in identities:
        triple = identity.order_key
        if triple in seen:
            raise ValueError(f"{label}不得重复同一页身份")
        seen.add(triple)
        doc_page = (identity.source_document_version_id, identity.page_number)
        artifact = identity.page_artifact_id
        previous_artifact = doc_page_to_artifact.setdefault(doc_page, artifact)
        if previous_artifact != artifact:
            raise ValueError(
                f"{label}同一资料版本的同一页码出现两个页工件：来源页身份冲突，"
                "不是两页"
            )
        previous_doc_page = artifact_to_doc_page.setdefault(artifact, doc_page)
        if previous_doc_page != doc_page:
            raise ValueError(
                f"{label}同一页工件复用于不同页或不同文档：来源页身份冲突，不是两页"
            )


class JudgmentSearchLane(StableEnum):
    """独立检索读道；同模型不同推理强度不构成第二条读道。"""

    MAIN_A = "main-A"
    MAIN_B = "main-B"


class JudgmentSearchChannel(StableEnum):
    """逐页检索通道：手写批注与打印病历分析各自独立给出处置。"""

    HANDWRITTEN = "handwritten"
    PRINTED_ANALYSIS = "printed_analysis"


class JudgmentSearchDisposition(StableEnum):
    """单通道逐页检索处置；not_found 只能来自显式检索，绝不由缺页折叠。"""

    FOUND = "found"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    AMBIGUOUS = "ambiguous"


# --------------------------------------------------------------------------- 冻结页域


class JudgmentSearchPageIdentity(ContractModel):
    """一页来源身份：资料版本 + 页工件 + 页码 + 页图哈希，全部显式。"""

    model_config = ConfigDict(frozen=True)

    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)

    @property
    def order_key(self) -> tuple[str, str, int]:
        return (
            self.source_document_version_id,
            self.page_artifact_id,
            self.page_number,
        )


def judgment_search_scope_sha256(
    *,
    authority: FactAuthority,
    requirement_id: str,
    pages: tuple[JudgmentSearchPageIdentity, ...],
) -> str:
    """检索页域的内容寻址身份（页域按规范顺序纳入；不含任何时间戳）。"""
    from app.domain.publication import canonical_hash

    return canonical_hash(
        {
            "identity": "judgment_search_scope/v1",
            "authority": authority.model_dump(mode="json"),
            "requirement_id": requirement_id,
            "pages": [page.model_dump(mode="json") for page in pages],
        }
    )


class JudgmentSearchScope(JudgmentSearchModel):
    """冻结检索页域：一次判断候选检索的显式逐页范围。

    硬不变量：页域非空；来源页身份唯一且无冲突（精确重复、同一资料版本同一页码
    双页工件、页工件跨页/跨文档复用均拒绝）；成员按
    ``(source_document_version_id, page_artifact_id, page_number)`` 确定性排序，
    拒绝乱序输入以杜绝身份漂移；``scope_sha256`` 必须等于内容寻址重算值。
    本模型不声明也不证明该范围覆盖全部适格临床来源。
    """

    model_config = ConfigDict(frozen=True)

    authority: FactAuthority
    requirement_id: str = Field(min_length=1)
    pages: tuple[JudgmentSearchPageIdentity, ...] = Field(min_length=1)
    scope_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_scope(self) -> "JudgmentSearchScope":
        order_keys = [page.order_key for page in self.pages]
        if order_keys != sorted(order_keys):
            raise ValueError("检索页域必须按资料版本/页工件/页码确定性排序")
        _check_page_identity_collisions(self.pages, label="检索页域")
        expected = judgment_search_scope_sha256(
            authority=self.authority,
            requirement_id=self.requirement_id,
            pages=self.pages,
        )
        if self.scope_sha256 != expected:
            raise ValueError("检索页域哈希必须由权威元组/requirement/页域内容确定性计算")
        return self


# --------------------------------------------------------------------------- 逐页候选结果


class JudgmentSearchExcerptCandidate(ContractModel):
    """一条来源绑定的候选摘录：逐字文本 + 可选坐标，无任何模型标识。

    同一页/同一通道可含多条独立摘录，必须整体保留，绝不静默只留第一条。
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    bbox: BoundingBox | None = None
    coordinate_convention: Literal["unverified"] = "unverified"
    uncertainty_note: str | None = None

    @field_validator("text")
    @classmethod
    def reject_blank_excerpt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("候选摘录不得仅含空白")
        return value


class JudgmentSearchChannelResult(ContractModel):
    """单通道逐页检索处置。

    - found 必须携带非空来源绑定候选摘录集合（bbox 每条可选）；
    - not_found / unreadable 不得携带任何摘录，绝不虚构"未找到"的原文；
    - ambiguous 可保留零或多条暂定摘录；暂定摘录始终是歧义的，绝不在此
      晋升为 found。
    """

    model_config = ConfigDict(frozen=True)

    disposition: JudgmentSearchDisposition
    candidates: tuple[JudgmentSearchExcerptCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_disposition_payload(self) -> "JudgmentSearchChannelResult":
        if self.disposition == JudgmentSearchDisposition.FOUND:
            if not self.candidates:
                raise ValueError("found 处置必须携带非空来源绑定候选摘录集合")
            return self
        if self.disposition == JudgmentSearchDisposition.AMBIGUOUS:
            return self
        if self.candidates:
            raise ValueError(
                f"{self.disposition.value} 处置不得携带候选摘录，绝不虚构原文"
            )
        return self


class JudgmentSearchPageResult(ContractModel):
    """单页检索结果：页身份显式，手写与打印分析两条通道必须同时给出。"""

    model_config = ConfigDict(frozen=True)

    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    handwritten: JudgmentSearchChannelResult
    printed_analysis: JudgmentSearchChannelResult

    @property
    def order_key(self) -> tuple[str, str, int]:
        return (
            self.source_document_version_id,
            self.page_artifact_id,
            self.page_number,
        )

    def channel_result(self, channel: JudgmentSearchChannel) -> JudgmentSearchChannelResult:
        if channel == JudgmentSearchChannel.HANDWRITTEN:
            return self.handwritten
        return self.printed_analysis


class JudgmentSearchLaneResult(JudgmentSearchModel):
    """一条独立 main-A/main-B 读道的检索结果。

    引用精确范围哈希与 provider/model 身份；每个被检索页恰有一条逐页结果，
    来源页身份不得重复或冲突。provider/model 存储前剥离首尾空白、拒绝纯空白；
    独立性比较忽略大小写与首尾空白——这只为拒绝同一身份伪装成第二条读道，
    不证明跨 provider 的别名消解（真实路由身份核验仍是仓储/运行时职责）。
    ``reasoning_effort`` 为必填审计元数据，绝不参与独立性比较。
    """

    model_config = ConfigDict(frozen=True)

    scope_sha256: str = Field(pattern=_SHA256)
    lane: JudgmentSearchLane
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    page_results: tuple[JudgmentSearchPageResult, ...] = Field(min_length=1)

    @field_validator("provider", "model", "reasoning_effort")
    @classmethod
    def _strip_nonblank(cls, value: str, info: ValidationInfo) -> str:
        return _normalize_nonblank(value, info.field_name)

    @model_validator(mode="after")
    def validate_page_results(self) -> "JudgmentSearchLaneResult":
        _check_page_identity_collisions(self.page_results, label="读道检索结果")
        return self


# --------------------------------------------------------------------------- 覆盖核验输出


class JudgmentSearchCoverageStatus(StableEnum):
    """覆盖核验状态；命名只说候选/覆盖，绝不断言临床证明。"""

    ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE = (
        "all_supplied_pages_searched_without_candidate"
    )
    CANDIDATES_PRESENT = "candidates_present"
    COVERAGE_INCOMPLETE = "coverage_incomplete"


class JudgmentSearchFoundCandidate(ContractModel):
    """一条 found 检索候选的投影：全部候选摘录原样保留，绝无任何采信或适用性字段。"""

    model_config = ConfigDict(frozen=True)

    lane: JudgmentSearchLane
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    page_image_sha256: str = Field(pattern=_SHA256)
    channel: JudgmentSearchChannel
    candidates: tuple[JudgmentSearchExcerptCandidate, ...] = Field(min_length=1)


class JudgmentSearchLanePageGap(ContractModel):
    """某条已提交读道在范围内缺失的页。"""

    model_config = ConfigDict(frozen=True)

    lane: JudgmentSearchLane
    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)


class JudgmentSearchChannelGap(ContractModel):
    """某条读道某页某通道的失败/歧义缺口。

    ``disposition`` 只允许 unreadable 或 ambiguous；只有 ambiguous 缺口可携带
    暂定摘录——它们仍是歧义的，与 found 候选并列保留，绝不晋升、绝不只留第一条。
    """

    model_config = ConfigDict(frozen=True)

    lane: JudgmentSearchLane
    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    channel: JudgmentSearchChannel
    disposition: JudgmentSearchDisposition
    tentative_excerpts: tuple[JudgmentSearchExcerptCandidate, ...] = ()

    @model_validator(mode="after")
    def validate_gap(self) -> "JudgmentSearchChannelGap":
        if self.disposition not in (
            JudgmentSearchDisposition.UNREADABLE,
            JudgmentSearchDisposition.AMBIGUOUS,
        ):
            raise ValueError("覆盖缺口只允许 unreadable 或 ambiguous 处置")
        if (
            self.disposition == JudgmentSearchDisposition.UNREADABLE
            and self.tentative_excerpts
        ):
            raise ValueError("unreadable 缺口不得携带暂定摘录")
        return self


class JudgmentSearchCoverageSummary(JudgmentSearchModel):
    """纯覆盖核验输出：候选与缺口并列，恒不构成临床证明。

    - ``candidates_present``：任一页任一读道任一通道 found。found 候选与
      未闭合缺口原样保留；混合 found/none 不是共识通过，更不是要求满足。
    - ``all_supplied_pages_searched_without_candidate``：仅当给定范围内的每一页
      都有两条独立有效记录、且两条通道在两条读道上均显式 not_found。这只说明
      给定页域内未检索到候选，绝不证明研究者书面判断不存在。
    - ``coverage_incomplete``：缺页、读取失败、歧义或读道缺席。这是覆盖不完整，
      不是判断缺失，也不是 not_found。

    ``ambiguous_channels`` 中的歧义缺口按原样携带全部暂定摘录，与
    ``found_candidates`` 并列保留；暂定摘录始终是歧义的，绝不晋升、绝不只留
    第一条。三个不变量字段类型锁定为 ``False``：调用方无法传入任意接受布尔。
    ``source_scope_verified`` 恒为 False——本纯核验不证明范围覆盖全部适格来源；
    ``product_acceptance`` 与 ``professional_judgment_absence_proven`` 恒为 False。
    """

    model_config = ConfigDict(frozen=True)

    scope_sha256: str = Field(pattern=_SHA256)
    requirement_id: str = Field(min_length=1)
    status: JudgmentSearchCoverageStatus
    source_scope_verified: Literal[False] = False
    product_acceptance: Literal[False] = False
    professional_judgment_absence_proven: Literal[False] = False
    found_candidates: tuple[JudgmentSearchFoundCandidate, ...] = ()
    missing_lanes: tuple[JudgmentSearchLane, ...] = ()
    pages_without_lane_result: tuple[JudgmentSearchLanePageGap, ...] = ()
    unreadable_channels: tuple[JudgmentSearchChannelGap, ...] = ()
    ambiguous_channels: tuple[JudgmentSearchChannelGap, ...] = ()


__all__ = [
    "JUDGMENT_SEARCH_CONTRACT_VERSION",
    "JudgmentSearchChannel",
    "JudgmentSearchChannelGap",
    "JudgmentSearchChannelResult",
    "JudgmentSearchCoverageStatus",
    "JudgmentSearchCoverageSummary",
    "JudgmentSearchDisposition",
    "JudgmentSearchExcerptCandidate",
    "JudgmentSearchFoundCandidate",
    "JudgmentSearchLane",
    "JudgmentSearchLanePageGap",
    "JudgmentSearchLaneResult",
    "JudgmentSearchPageIdentity",
    "JudgmentSearchPageResult",
    "JudgmentSearchScope",
    "judgment_search_scope_sha256",
]
