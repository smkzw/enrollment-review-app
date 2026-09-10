"""证据规范化器输入/输出合同（纯校验，无存储）。

本模块冻结证据规范化 Agent 的输入/输出形状与中文原生校验规则，覆盖设计书
§3.1 候选/发布分离、§3.2 部分日期、§3.3 极性/沉默/来源强度、§3.4 重复与冲突
以及 §4.1 规范化调用输入闭包：

- ``EvidenceNormalizerPageInput``  单页有效文本与定位清单；
- ``EvidenceNormalizerInput``      一次调用的确定性输入（含权威元组、逻辑文档、连续页组、有效文本哈希）；
- ``EvidenceNormalizerUnresolvedItem`` 模型显式报告的未解决项（候选外）；
- ``EvidenceNormalizerOutput``     结构化候选与未解决项的唯一合法输出（候选/unresolved-only）；
- 输入/输出一致性与严格 JSON 模式由本模块与 ``app/agents/evidence_normalizer.py`` 共享。

硬不变量：
- 输入页清单必须升序、无重复、页码从 1 起；pages 必须与 page_numbers 一一对应；
- 关联的 locator 必须属于输入可用 locator 集合；模型不得虚构 locator；
- 输出只能包含 fact/event/exposure 候选与 unresolved_items；不得包含发布事实、冲突裁决、Expectation 状态、入排结论或模型置信度阈值；
- 输出候选的 run_id/call_id/logical_document_id 必须与输入一致；跨调用/跨文档/跨 episode 引用一律拒绝；
- 空输出（空字符串/空 JSON/零候选零未解决且有有效文本）视为未闭合，需由确定性门禁判定失败，不生成空 Profile；
- 有效文本哈希必须与原文一致，沉默/未提及不得生成否定或正常事实。
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel
from .evidence_locator import PageReviewVisualProvenance
from .enums import (
    DurationStatus,
    FactPolarity,
    GapType,
    LocatorPrecision,
    LocatorSourceLayer,
    ReviewStage,
    SourceStrength,
)
from .facts import (
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    MedicationExposureCandidateV2,
    PartialDateRange,
)
from .page_review import (
    PageCoverageEntry,
    PageDisposition,
    PageReconciliation,
    PageReviewRecord,
)
from .rules import EvidenceRequirement

__all__ = [
    "EvidenceNormalizerInput",
    "EvidenceNormalizerContextInput",
    "EvidenceNormalizerLocatorInput",
    "EvidenceNormalizerOutput",
    "EvidenceNormalizerPageInput",
    "EvidenceNormalizerPageReviewInput",
    "PersistedEvidenceNormalizerUnresolvedItem",
    "EvidenceNormalizerUnresolvedItem",
    "evidence_normalizer_input_scope_hash",
]

_SHA256 = r"^[0-9a-f]{64}$"


def _require_utc(value: datetime, field_name: str) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _require_sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须按 ID 排序且不得重复")


def _require_sorted_unique_int(values: list[int], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} 必须升序、无重复")
    if any(v < 1 for v in values):
        raise ValueError(f"{label} 页码必须从 1 起")


class EvidenceNormalizerPageInput(ContractModel):
    """单页有效文本与定位清单（已校对后的有效文本，非原始 OCR）。"""

    model_config = ConfigDict(extra="forbid")

    source_document_version_id: str = Field(min_length=1)
    page_artifact_id: str = Field(min_length=1)
    ocr_page_id: str | None = None
    page_number: int = Field(ge=1)
    effective_text: str = Field(min_length=0)
    effective_text_sha256: str = Field(pattern=_SHA256)
    locator_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_page(self) -> "EvidenceNormalizerPageInput":
        # 有序且无重复的定位；页内定位可为空（无可定位文本），但若有则必须排序
        if self.locator_ids != sorted(set(self.locator_ids)):
            raise ValueError("页定位列表必须按 ID 排序且不得重复")
        # 哈希必须与有效文本一致（截断空白不计，保留原文精确性）
        expected = hashlib.sha256(self.effective_text.encode("utf-8")).hexdigest()
        if self.effective_text_sha256 != expected:
            raise ValueError("页有效文本哈希与原文不一致")
        return self


class EvidenceNormalizerLocatorInput(ContractModel):
    """模型可引用定位的确定性摘要；内容来自 Phase 4，不由模型补写。"""

    model_config = ConfigDict(extra="forbid")

    locator_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    source_layer: LocatorSourceLayer
    precision: LocatorPrecision
    source_text_sha256: str = Field(pattern=_SHA256)
    localized_text: str | None = None
    page_review_visual: PageReviewVisualProvenance | None = Field(
        default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_locator(self) -> "EvidenceNormalizerLocatorInput":
        if self.source_layer == LocatorSourceLayer.PAGE_REVIEW_VISUAL:
            if self.page_review_visual is None or self.precision != LocatorPrecision.PAGE_EXCERPT:
                raise ValueError("视觉定位输入必须绑定原始判读与页面摘录")
            if not self.localized_text or hashlib.sha256(self.localized_text.encode()).hexdigest() != self.source_text_sha256:
                raise ValueError("视觉定位输入的摘录与文本哈希不一致")
        elif self.page_review_visual is not None:
            raise ValueError("文字定位不能使用视觉来源绑定")
        if self.precision == LocatorPrecision.PAGE_ONLY:
            if self.localized_text is not None:
                raise ValueError("page_only 定位不能携带伪精确原文")
        elif not self.localized_text or not self.localized_text.strip():
            raise ValueError("非 page_only 定位必须提供可回放的具体原文")
        return self


class EvidenceNormalizerContextInput(ContractModel):
    """本次调用冻结的审核与资料语义上下文。

    ``document_record_time`` 只允许承载资料元数据中已有的权威记录时间；当前资料
    底座没有该字段时必须为 ``None``。不得用上传时间、筛选日、操作日或节点锚点
    填充。Agent 仍可从有真实定位的正文中抽取候选 ``record_time``。
    """

    model_config = ConfigDict(extra="forbid")

    source_document_version_id: str = Field(min_length=1)
    metadata_revision_id: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    source_party: str = Field(min_length=1)
    document_record_time: PartialDateRange | None = None
    current_review_stage: ReviewStage
    workflow_stage_id: str | None = None


class EvidenceNormalizerPageReviewInput(ContractModel):
    """一次规范化调用内已冻结的 R3 页级判读结果。"""

    model_config = ConfigDict(extra="forbid")

    coverage_id: str = Field(min_length=1)
    clause_pack_sha256: str = Field(pattern=_SHA256)
    entries: list[PageCoverageEntry] = Field(min_length=1)
    reviews: list[PageReviewRecord] = Field(default_factory=list)
    reconciliations: list[PageReconciliation] = Field(default_factory=list)
    scope_sha256: str = Field(pattern=_SHA256)
    visual_source_policy: Literal["page-review-visual-sources/v1"] | None = Field(
        default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_closure(self) -> "EvidenceNormalizerPageReviewInput":
        if any(
            item.disposition == PageDisposition.FAILED_PENDING_REREAD
            for item in self.entries
        ):
            raise ValueError("存在失败待复读页面，不能进入事实规范化")
        page_ids = [item.page_artifact_id for item in self.entries]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("页级判读输入不得重复页面")
        accepted = {
            item.reconciliation_id: item
            for item in self.entries
            if item.disposition == PageDisposition.ACCEPTED
        }
        reconciliations = {item.reconciliation_id: item for item in self.reconciliations}
        if set(reconciliations) != set(accepted):
            raise ValueError("采信页面必须逐项闭合页级对账记录")
        review_ids = {item.page_review_id for item in self.reviews}
        expected_review_ids: set[str] = set()
        for reconciliation_id, reconciliation in reconciliations.items():
            entry = accepted[reconciliation_id]
            if (
                reconciliation.page_artifact_id != entry.page_artifact_id
                or reconciliation.clause_pack_sha256 != self.clause_pack_sha256
            ):
                raise ValueError("页级对账与采信页面或条款包不一致")
            expected_review_ids.update(reconciliation.page_review_ids)
        if review_ids != expected_review_ids:
            raise ValueError("页级判读记录必须与对账引用逐项闭合")
        entry_by_page = {item.page_artifact_id: item for item in self.entries}
        for review in self.reviews:
            entry = entry_by_page.get(review.page_artifact_id)
            if entry is None or (
                review.source_document_version_id != entry.source_document_version_id
                or review.page_number != entry.page_number
                or review.clause_pack_sha256 != self.clause_pack_sha256
            ):
                raise ValueError("页级判读记录与调用页面或条款包不一致")
        expected_scope = page_review_input_scope_hash(
            coverage_id=self.coverage_id,
            clause_pack_sha256=self.clause_pack_sha256,
            entries=self.entries,
            reviews=self.reviews,
            reconciliations=self.reconciliations,
            visual_source_policy=self.visual_source_policy,
        )
        if self.scope_sha256 != expected_scope:
            raise ValueError("页级判读输入范围哈希不一致")
        return self


def page_review_input_scope_hash(
    *,
    coverage_id: str,
    clause_pack_sha256: str,
    entries: list[PageCoverageEntry],
    reviews: list[PageReviewRecord],
    reconciliations: list[PageReconciliation],
    visual_source_policy: str | None = None,
) -> str:
    payload = {
        "coverage_id": coverage_id,
        "clause_pack_sha256": clause_pack_sha256,
        "entries": [item.model_dump(mode="json") for item in entries],
        "reviews": [
            item.model_dump(mode="json")
            for item in sorted(reviews, key=lambda value: value.page_review_id)
        ],
        "reconciliations": [
            item.model_dump(mode="json")
            for item in sorted(
                reconciliations, key=lambda value: value.reconciliation_id
            )
        ],
    }
    if visual_source_policy is not None:
        payload["visual_source_policy"] = visual_source_policy
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceNormalizerInput(ContractModel):
    """一次 Evidence Normalizer 调用的确定性输入（单逻辑文档连续页组）。

    该输入由确定性规划层从活动完整处理修订的项目有效文本与
    locator 闭包派生；本模块只冻结形状与校验，不负责规划或持久化。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="phase5/v1", pattern=r"^phase5/v1$")
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    authority: FactAuthority
    logical_document_id: str = Field(min_length=1)
    context: EvidenceNormalizerContextInput
    related_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    manifest_sha256: str = Field(pattern=_SHA256)
    completion_manifest_sha256: str = Field(pattern=_SHA256)
    page_numbers: list[int] = Field(min_length=1)
    pages: list[EvidenceNormalizerPageInput] = Field(min_length=1)
    page_review: EvidenceNormalizerPageReviewInput | None = None
    available_locator_ids: list[str] = Field(default_factory=list)
    available_locators: list[EvidenceNormalizerLocatorInput] = Field(default_factory=list)
    input_scope_sha256: str = Field(pattern=_SHA256)
    created_at: datetime

    @model_validator(mode="after")
    def validate_input(self) -> "EvidenceNormalizerInput":
        _require_utc(self.created_at, "created_at")
        _require_sorted_unique_int(self.page_numbers, "调用页清单")
        if len(self.pages) != len(self.page_numbers):
            raise ValueError("pages 数量必须与 page_numbers 一一对应")
        page_nums = [p.page_number for p in self.pages]
        if page_nums != sorted(self.page_numbers):
            raise ValueError("pages 的 page_number 必须与 page_numbers 排序一致")
        if page_nums != sorted(set(page_nums)):
            raise ValueError("pages 的 page_number 必须无重复")
        # 可用 locator 集合必须排序且无重复
        if self.available_locator_ids != sorted(set(self.available_locator_ids)):
            raise ValueError("可用定位集合必须按 ID 排序且不得重复")
        available = set(self.available_locator_ids)
        for page in self.pages:
            if not set(page.locator_ids).issubset(available):
                raise ValueError("页定位必须属于本次调用可用 locator 集合")
        locator_ids = [item.locator_id for item in self.available_locators]
        if locator_ids != self.available_locator_ids:
            raise ValueError("定位摘要必须按 ID 排序并逐项闭合可用定位集合")
        locator_page_by_id = {
            locator_id: page.page_number
            for page in self.pages
            for locator_id in page.locator_ids
        }
        for locator in self.available_locators:
            if locator_page_by_id.get(locator.locator_id) != locator.page_number:
                raise ValueError("定位摘要页码必须与页面定位清单一致")
        # 每页资料版本必须与冻结的资料语义上下文一致
        for page in self.pages:
            if page.source_document_version_id != self.context.source_document_version_id:
                raise ValueError("页资料版本必须与本次调用的资料语义上下文一致")
        if self.page_review is not None:
            review_pages = [item.page_number for item in self.page_review.entries]
            if review_pages != self.page_numbers:
                raise ValueError("页级判读处置必须与本次调用页清单逐项一致")
        requirement_ids = [item.requirement_id for item in self.related_requirements]
        if requirement_ids != sorted(set(requirement_ids)):
            raise ValueError("相关资料要求必须按 requirement_id 排序且不得重复")
        # 输入范围哈希必须与页及权威元组一致（可重建性）
        expected = evidence_normalizer_input_scope_hash(
            authority=self.authority,
            logical_document_id=self.logical_document_id,
            context=self.context,
            related_requirements=self.related_requirements,
            manifest_sha256=self.manifest_sha256,
            completion_manifest_sha256=self.completion_manifest_sha256,
            page_numbers=self.page_numbers,
            pages=self.pages,
            page_review=self.page_review,
            available_locator_ids=self.available_locator_ids,
            available_locators=self.available_locators,
        )
        if self.input_scope_sha256 != expected:
            raise ValueError("输入范围哈希与权威元组/文档/页/定位清单不一致")
        return self


def evidence_normalizer_input_scope_hash(
    *,
    authority: FactAuthority,
    logical_document_id: str,
    context: EvidenceNormalizerContextInput,
    related_requirements: list[EvidenceRequirement],
    manifest_sha256: str,
    completion_manifest_sha256: str,
    page_numbers: list[int],
    pages: list[EvidenceNormalizerPageInput],
    page_review: EvidenceNormalizerPageReviewInput | None = None,
    available_locator_ids: list[str],
    available_locators: list[EvidenceNormalizerLocatorInput],
) -> str:
    """计算输入范围的稳定哈希（用于幂等键与调用闭包校验）。"""
    payload = {
        "authority": authority.model_dump(mode="json"),
        "logical_document_id": logical_document_id,
        "context": context.model_dump(mode="json"),
        "related_requirements": [
            item.model_dump(mode="json")
            for item in sorted(related_requirements, key=lambda item: item.requirement_id)
        ],
        "manifest_sha256": manifest_sha256,
        "completion_manifest_sha256": completion_manifest_sha256,
        "page_numbers": sorted(page_numbers),
        "pages": [
            {
                "page_number": p.page_number,
                "source_document_version_id": p.source_document_version_id,
                "page_artifact_id": p.page_artifact_id,
                "ocr_page_id": p.ocr_page_id,
                "effective_text_sha256": p.effective_text_sha256,
                "locator_ids": sorted(p.locator_ids),
            }
            for p in sorted(pages, key=lambda x: x.page_number)
        ],
        "available_locator_ids": sorted(available_locator_ids),
        "available_locators": [
            item.model_dump(mode="json")
            for item in sorted(available_locators, key=lambda item: item.locator_id)
        ],
    }
    if page_review is not None:
        payload["page_review_scope_sha256"] = page_review.scope_sha256
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceNormalizerUnresolvedItem(ContractModel):
    """模型显式报告的未解决项：候选外的不确定性、缺口或风险线索。

    该结构仅承载模型在本次页组内无法确认的字段、缺失整页、模糊日期、单位不
    确定、否定范围不明或 OCR 风险；最终的 EvidenceExpectation 状态与 Action
    由确定性代码在 Phase 5 R07 投影，不由模型裁决。
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, description="未解决编码，如 page_unreadable/ambiguous_date/missing_unit 等")
    message: str = Field(min_length=1, description="中文原生未解决说明")
    affected_pages: list[int] = Field(default_factory=list)
    affected_locator_ids: list[str] = Field(default_factory=list)
    affected_requirement_ids: list[str] = Field(default_factory=list)
    gap_type: GapType | None = None
    referenced_file_id: str | None = None
    reason: str = Field(min_length=1, description="中文原因，需指向具体页/定位与原文缺口")

    @model_validator(mode="after")
    def validate_item(self) -> "EvidenceNormalizerUnresolvedItem":
        if not self.affected_pages and not self.affected_locator_ids:
            raise ValueError("未解决项必须至少关联一个受影响页或定位")
        if self.affected_pages != sorted(set(self.affected_pages)):
            raise ValueError("未解决项受影响页必须升序且无重复")
        if any(p < 1 for p in self.affected_pages):
            raise ValueError("未解决项受影响页码必须从 1 起")
        if self.affected_locator_ids != sorted(set(self.affected_locator_ids)):
            raise ValueError("未解决项受影响定位必须按 ID 排序且不得重复")
        _require_sorted_unique(self.affected_requirement_ids, "未解决项受影响资料要求")
        if bool(self.affected_requirement_ids) != (self.gap_type is not None):
            raise ValueError("资料要求绑定与结构化缺口类型必须同时提供")
        allowed_gap_types = {
            GapType.RECORD_INCOMPLETE,
            GapType.DESCRIPTION_INSUFFICIENT,
            GapType.REQUIRED_PROCEDURE_NOT_DONE,
            GapType.RESULT_FIELDS_MISSING,
            GapType.DATE_OR_ANCHOR_MISSING,
            GapType.REFERENCED_FILE_MISSING,
            GapType.PROVENANCE_FOLLOWUP,
            GapType.OCR_OR_PARSE_RISK,
            GapType.HISTORICAL_SOURCE_UNAVAILABLE,
        }
        if self.gap_type is not None and self.gap_type not in allowed_gap_types:
            raise ValueError("未解决项使用了不支持的资料缺口类型")
        if self.gap_type == GapType.REFERENCED_FILE_MISSING:
            if not self.referenced_file_id:
                raise ValueError("已引用文件未提供必须给出结构化文件身份")
        elif self.referenced_file_id is not None:
            raise ValueError("非已引用文件缺失项不能携带文件身份")
        return self


class PersistedEvidenceNormalizerUnresolvedItem(ContractModel):
    """可回放的逐页未解决项，和候选一起受任务租约写栅栏保护。"""

    model_config = ConfigDict(extra="forbid")

    unresolved_item_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    item: EvidenceNormalizerUnresolvedItem
    created_at: datetime

    @model_validator(mode="after")
    def validate_persisted_item(self) -> "PersistedEvidenceNormalizerUnresolvedItem":
        _require_utc(self.created_at, "created_at")
        return self


class EvidenceNormalizerOutput(ContractModel):
    """Evidence Normalizer 的唯一合法输出：结构化候选与未解决项。

    - 只允许 fact_candidates / event_candidates / exposure_candidates /
      unresolved_items 四个业务字段；任何发布事实、冲突裁决、Expectation、
      入排结论、ReviewRun、ActionRequest、blocking_level 字段均被 ``extra=forbid``
      拒绝；
    - 候选与未解决项均携带 run_id/call_id 绑定，跨调用引用一律拒绝；
    - 空候选零未解决在有有效文本时会由确定性页覆盖门禁判为遗漏，不生成空 Profile；
      本合同允许空列表以支持“本页组无可抽取事实但已逐页闭合”的合法场景。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="phase5/v1", pattern=r"^phase5/v1$")
    run_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    page_numbers: list[int] = Field(min_length=1)
    fact_candidates: list[ClinicalFactCandidateV2] = Field(default_factory=list)
    event_candidates: list[ClinicalEventCandidateV2] = Field(default_factory=list)
    exposure_candidates: list[MedicationExposureCandidateV2] = Field(default_factory=list)
    unresolved_items: list[EvidenceNormalizerUnresolvedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_output(self) -> "EvidenceNormalizerOutput":
        _require_sorted_unique_int(self.page_numbers, "输出页清单")
        # 候选 run_id/call_id/logical_document 必须与输出头一致
        for cand in self.fact_candidates:
            if cand.run_id != self.run_id or cand.call_id != self.call_id:
                raise ValueError("事实候选的 run_id/call_id 必须与输出头一致")
        for cand in self.event_candidates:
            if cand.run_id != self.run_id or cand.call_id != self.call_id:
                raise ValueError("事件候选的 run_id/call_id 必须与输出头一致")
        for cand in self.exposure_candidates:
            if cand.run_id != self.run_id or cand.call_id != self.call_id:
                raise ValueError("暴露候选的 run_id/call_id 必须与输出头一致")
        # 候选 ID 全局唯一（跨 fact/event/exposure）
        all_ids = [c.candidate_id for c in self.fact_candidates] + \
                  [c.candidate_id for c in self.event_candidates] + \
                  [c.candidate_id for c in self.exposure_candidates]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("候选 ID 在本次输出内必须全局唯一")
        fact_ids = {candidate.candidate_id for candidate in self.fact_candidates}
        for candidate in self.event_candidates:
            unknown = set(candidate.fact_candidate_ids) - fact_ids
            if unknown:
                raise ValueError(f"事件候选引用了本次输出不存在的事实候选：{sorted(unknown)}")
        for candidate in self.exposure_candidates:
            unknown = set(candidate.fact_candidate_ids) - fact_ids
            if unknown:
                raise ValueError(f"暴露候选引用了本次输出不存在的事实候选：{sorted(unknown)}")
        # 候选 locator 仍需在 Pydantic 层保证排序唯一；跨输入可用集合的核对由 decoder+gate 完成
        # unresolved_items 的页必须属于本次页清单
        page_set = set(self.page_numbers)
        for item in self.unresolved_items:
            if item.affected_pages and not set(item.affected_pages).issubset(page_set):
                raise ValueError("未解决项受影响页必须属于本次调用页清单")
        # 允许空候选+空未解决的输出通过校验（语义空闭合由门禁判定），但拒绝完全无输入页的非法状态
        return self
