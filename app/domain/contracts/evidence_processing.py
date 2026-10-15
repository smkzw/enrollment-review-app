"""Phase 4 OCR 持久化与基础证据处理修订领域契约（Slice 4.3）。

本模块冻结文件级 OCR 运行、真实请求尝试、页工作租约与不可变基础证据处理修订的
纯校验合同，只包含确定性身份计算与结构不变量，不含存储、文件路径或外部调用。
覆盖设计书 §3.3 的 ``OCRRun``/``OCRAttempt``/页工作租约与 §3.2 的
``EvidenceProcessingRevision`` 基础页清单：

- ``EvidenceProcessingRevisionPage``   页清单条目：逐页冻结 PageArtifact 与
                                        OCRPage 身份、页序、状态与失败原因；
- ``EvidenceProcessingRevision``       不可变基础证据处理修订：绑定一个快照，
                                        冻结有序页清单与清单哈希，明确不可激活，
                                        不推断也不改写活动指针；
- ``OCRRun``                           文件级 OCR 运行：Profile、任务、状态与汇总；
- ``OCRAttempt``                       每次真实 OCR 请求：开始/结束、失败类别、
                                        原始请求/响应工件引用、页工作租约代次、
                                        oMLX 租约与重试关系；追加写且保留晚到尝试；
- ``PageWorkLease``                    页工作租约：owner/过期/单调递增代次，
                                        只防止同一页被重复 worker 执行，不是并发额度。

Slice 4.3 停止点约束：基础证据处理修订状态只能为 ``READY`` 且
``is_activatable`` 恒为 ``False``；不出现激活状态、活动指针或 ActivationEvent；
页清单按 ``(source_document_version_id, page_number)`` 升序且无重复页；清单哈希
与条目集合必须一致；晚到尝试（``rejected_late``）只作审计，不得进入成功缓存。
页工作租约 ``work_item_id`` 必须等于页级缓存唯一键（内容寻址，不来自文件名）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, VersionedModel
from .enums import (
    OcrAttemptStatus,
    OcrFailureCategory,
    OcrRunStatus,
    PageArtifactStatus,
    ProcessingRevisionStatus,
)

__all__ = [
    "EvidenceProcessingRevision",
    "EvidenceProcessingRevisionPage",
    "OCRAttempt",
    "OCRRun",
    "PageWorkLease",
]

_SHA256 = r"^[0-9a-f]{64}$"


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the Phase 4 contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")


def _check_interval(started_at, completed_at, what: str) -> None:
    if started_at is not None and completed_at is not None:
        try:
            if completed_at < started_at:
                raise ValueError(f"{what} 完成时间不能早于开始时间")
        except TypeError as exc:
            raise ValueError(f"{what} 开始和完成时间必须使用一致的时区语义") from exc


class EvidenceProcessingRevisionPage(VersionedModel):
    """基础证据处理修订页清单条目（追加写，不可变）。

    每个条目把一页冻结到不可变 PageArtifact 与（可选的）OCRPage 身份：
    ``page_artifact_id`` 必须非空；``ocr_page_id`` 仅在成功/降级页上可引用，
    失败页不得携带 OCR 结果。``position`` 是 1 起的有序位置；同一修订内
    不允许重复 ``(source_document_version_id, page_number)`` 页。
    """

    entry_id: str = Field(min_length=1)
    position: int = Field(ge=1)
    source_document_version_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    original_frame: str | None = None
    page_artifact_id: str = Field(min_length=1)
    ocr_page_id: str | None = None
    status: PageArtifactStatus
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_page_entry(self) -> EvidenceProcessingRevisionPage:
        if self.status == PageArtifactStatus.SUCCEEDED and self.failure_reason is not None:
            raise ValueError("清单成功页不应携带失败原因")
        if self.status == PageArtifactStatus.DEGRADED and not self.failure_reason:
            raise ValueError("清单降级页必须说明降级原因")
        if self.status == PageArtifactStatus.FAILED and not self.failure_reason:
            raise ValueError("清单失败页必须说明失败原因")
        if self.status == PageArtifactStatus.FAILED and self.ocr_page_id is not None:
            raise ValueError("失败页不得携带 OCR 结果引用")
        return self


class EvidenceProcessingRevision(VersionedModel):
    """不可变基础证据处理修订：冻结快照、有序页清单与清单哈希。

    绑定一个证据快照并逐页冻结 PageArtifact/OCRPage 身份；``manifest_sha256``
    对有序页清单内容寻址，任一页序、重复页或身份漂移都会在回放时被拒绝。
    基础修订状态恒为 ``READY`` 且 ``is_activatable`` 恒为 ``False``：它不产生
    ActivationEvent，不推断也不更新审核节点活动指针，只可回放。Scope 列与快照
    必须一致（由仓储在写入时校验）。
    """

    evidence_processing_revision_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    manifest: list[EvidenceProcessingRevisionPage] = Field(default_factory=list)
    manifest_sha256: str = Field(pattern=_SHA256)
    status: ProcessingRevisionStatus = ProcessingRevisionStatus.READY
    is_activatable: Literal[False] = False
    preparation_policy: Literal["legacy-text/v1", "original-page-images/v1"] = "legacy-text/v1"
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_revision(self) -> EvidenceProcessingRevision:
        _require_utc(self.created_at, "EvidenceProcessingRevision.created_at")
        if self.status != ProcessingRevisionStatus.READY:
            raise ValueError(
                "基础证据处理修订只能处于 READY 状态，且不得携带激活语义"
            )
        if self.is_activatable:
            raise ValueError("基础证据处理修订明确不可激活")

        positions: set[int] = set()
        seen_pages: set[tuple[str, int]] = set()
        current_document_id: str | None = None
        closed_document_ids: set[str] = set()
        previous_page_number = 0
        for entry in self.manifest:
            if entry.position in positions:
                raise ValueError("页清单位置不能重复")
            positions.add(entry.position)

            page = (entry.source_document_version_id, entry.page_number)
            if page in seen_pages:
                raise ValueError("页清单不允许重复同一页")
            seen_pages.add(page)

            if entry.source_document_version_id != current_document_id:
                if entry.source_document_version_id in closed_document_ids:
                    raise ValueError("同一资料的页面必须连续排列，不能被其他资料分隔")
                if current_document_id is not None:
                    closed_document_ids.add(current_document_id)
                current_document_id = entry.source_document_version_id
                previous_page_number = 0
            if entry.page_number <= previous_page_number:
                raise ValueError("同一资料的页码必须升序")
            previous_page_number = entry.page_number

        if sorted(positions) != list(range(1, len(self.manifest) + 1)):
            raise ValueError("页清单位置必须从 1 连续递增")

        from app.domain.publication import evidence_processing_manifest_hash

        expected = evidence_processing_manifest_hash(
            entries=[
                (
                    entry.source_document_version_id,
                    entry.page_number,
                    entry.original_frame,
                    entry.page_artifact_id,
                    entry.ocr_page_id,
                    entry.status.value,
                )
                for entry in self.manifest
            ]
        )
        if self.manifest_sha256 != expected:
            raise ValueError("证据处理修订清单哈希与页清单集合不一致")
        return self


class OCRRun(VersionedModel):
    """文件级 OCR 运行：Profile、任务、状态与页级汇总。

    绑定一个 ``source_document_version_id`` 与识别配置；``job_id`` 指向触发它的
    持久 Job。汇总计数满足 ``0 <= page_succeeded + page_failed <= page_total``；
    状态与时间戳必须一致。运行本身不承载临床判断。
    """

    ocr_run_id: str = Field(min_length=1)
    source_document_version_id: str = Field(min_length=1)
    ocr_profile_id: str = Field(min_length=1)
    ocr_profile_sha256: str = Field(pattern=_SHA256)
    job_id: str | None = None
    status: OcrRunStatus = OcrRunStatus.RUNNING
    page_total: int = Field(ge=0)
    page_succeeded: int = Field(default=0, ge=0)
    page_failed: int = Field(default=0, ge=0)
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_run(self) -> OCRRun:
        _require_utc(self.started_at, "OCRRun.started_at")
        _require_utc(self.created_at, "OCRRun.created_at")
        if self.completed_at is not None:
            _require_utc(self.completed_at, "OCRRun.completed_at")
        if self.page_succeeded + self.page_failed > self.page_total:
            raise ValueError("OCR 运行页汇总不能超过总页数")
        if self.status == OcrRunStatus.RUNNING and self.completed_at is not None:
            raise ValueError("运行中 OCR 运行不能携带完成时间")
        if self.status != OcrRunStatus.RUNNING and self.completed_at is None:
            raise ValueError("非运行中 OCR 运行必须提供完成时间")
        if self.status == OcrRunStatus.SUCCEEDED and self.page_failed != 0:
            raise ValueError("成功的 OCR 运行不能有失败页")
        if self.status == OcrRunStatus.FAILED and self.page_total == 0:
            raise ValueError("失败的 OCR 运行不能宣称零页文件")
        _check_interval(self.started_at, self.completed_at, "OCRRun")
        return self


class OCRAttempt(VersionedModel):
    """每次真实 OCR 请求的尝试记录（追加写，包含被拒绝的晚到尝试）。

    ``cache_key`` 是页工作项身份（页级缓存唯一键），必须非空；``ocr_page_id``
    在结果被接受/创建页结果后回填，失败或晚到尝试可为空。``attempt_number``
    是同一 ``cache_key`` 上的 1 起递增序号。``work_lease_owner``/``work_lease_generation``
    记录本次推理持有页工作租约时的代次（晚到拒绝的依据）；``omlx_lease_owner``
    记录共享门禁租约。``retry_of_attempt_id`` 指向被重试的前一尝试。原始请求/
    响应工件引用分别指向不可变内容寻址工件。``rejected_late`` 只作审计。
    """

    attempt_id: str = Field(min_length=1)
    ocr_run_id: str = Field(min_length=1)
    ocr_page_id: str | None = None
    cache_key: str = Field(pattern=_SHA256)
    attempt_number: int = Field(ge=1)
    status: OcrAttemptStatus
    failure_category: OcrFailureCategory | None = None
    rejection_reason: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    raw_request_artifact_id: str | None = None
    raw_response_artifact_id: str | None = None
    work_lease_owner: str | None = None
    work_lease_generation: int | None = Field(default=None, ge=0)
    omlx_lease_owner: str | None = None
    retry_of_attempt_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_attempt(self) -> OCRAttempt:
        _require_utc(self.started_at, "OCRAttempt.started_at")
        _require_utc(self.created_at, "OCRAttempt.created_at")
        if self.completed_at is not None:
            _require_utc(self.completed_at, "OCRAttempt.completed_at")
        if self.failure_category is not None and self.status != OcrAttemptStatus.FAILED:
            raise ValueError("只有失败尝试才允许携带失败类别")
        if self.rejection_reason is not None and self.status not in {
            OcrAttemptStatus.REJECTED_LATE,
            OcrAttemptStatus.CANCELLED,
        }:
            raise ValueError("只有晚到或取消尝试才允许携带拒绝原因")
        if self.status in {
            OcrAttemptStatus.SUCCEEDED,
            OcrAttemptStatus.FAILED,
            OcrAttemptStatus.REJECTED_LATE,
            OcrAttemptStatus.CANCELLED,
        } and self.completed_at is None:
            raise ValueError("已结束的尝试必须提供完成时间")
        if self.status == OcrAttemptStatus.FAILED and self.failure_category is None:
            raise ValueError("失败尝试必须提供失败类别")
        if self.status == OcrAttemptStatus.REJECTED_LATE and not self.rejection_reason:
            raise ValueError("晚到尝试必须说明拒绝原因")
        if self.status == OcrAttemptStatus.CANCELLED and not self.rejection_reason:
            raise ValueError("取消尝试必须说明原因")
        _check_interval(self.started_at, self.completed_at, "OCRAttempt")
        return self


class PageWorkLease(ContractModel):
    """页工作租约（持久协调结构，不是并发额度）。

    ``work_item_id`` 必须等于页级缓存唯一键；``lease_generation`` 单调递增，
    每次成功领取 +1，续租与结果提交都核对 owner/代次/过期。只防止同一页被重复
    worker 执行；全局真实推理并发额度由共享 oMLX 门禁单独提供。
    """

    work_item_id: str = Field(pattern=_SHA256)
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    lease_generation: int = Field(default=0, ge=0)
    updated_at: datetime

    @model_validator(mode="after")
    def validate_lease(self) -> PageWorkLease:
        _require_utc(self.updated_at, "PageWorkLease.updated_at")
        if self.lease_expires_at is not None:
            _require_utc(self.lease_expires_at, "PageWorkLease.lease_expires_at")
        if self.lease_owner is not None and self.lease_generation < 1:
            raise ValueError("持有页工作租约时代次必须大于等于 1")
        return self
