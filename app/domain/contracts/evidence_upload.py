"""Phase 4 上传预览、逐文件差异与确认合同（Slice 4.2 冻结）。

本模块冻结“预览不是临床快照”的完整合同：用户先选择补充资料/完整资料快照并生成
逐文件差异预览（暂存 + SHA-256 + 格式探测 + 分类），取消只清理预览自有暂存且不
触碰共享 blob 或历史；确认在同一事务内创建或复用候选快照、初始持久 Job、幂等记录
与确认记录，不在 HTTP/服务调用内运行 OCR。

设计书 §3.2 与 §5.2 覆盖：

- ``EvidenceUploadPreview``  短期候选：绑定作用域、上传方式、基准快照、创建时
                              修订号与状态；``preview_sha256`` 对逐文件内容做
                              确定性摘要，确认时服务端重算并核验，不信任前端摘要；
- ``EvidenceUploadItem``     逐文件指纹/格式/大小/分类/处理建议/重复关系/冲突，
                              文件名从来不是内容身份；
- ``EvidenceUploadCommit``   确认动作：预览摘要哈希、幂等键、产生的候选快照、
                              实际应用的处置与是否命中重复集合 no-op；
- ``EvidenceUploadConfirmInput``  确认命令：预览 ID、摘要哈希、基准修订号、
                              幂等键与同名异内容处置；服务端重新校验作用域、
                              文件、快照基准与修订号；
- ``EvidenceUploadConfirmResult`` 确认结果：复用/新建快照、持久任务与重复标志。

确定性身份与摘要函数（``logical_document_id``、``source_document_version_id``、
``evidence_preview_digest``）把内容与作用域映射为稳定身份，使同一输入重复确认产生
同一成员集合，从而支持重复集合 no-op 与并发收敛；文件名不参与任何身份计算。

本模块只包含纯校验与确定性身份/摘要计算，不含存储、文件路径或外部调用。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.domain.publication import canonical_hash

from .common import ContractModel
from .enums import (
    SnapshotStatus,
    UploadConflictResolution,
    UploadItemStatus,
    UploadMode,
    UploadPreviewStatus,
)
from .evidence_ingestion import EvidenceSnapshot

__all__ = [
    "EVIDENCE_PROCESSING_JOB_TYPE",
    "EvidenceUploadCommit",
    "EvidenceUploadConfirmInput",
    "EvidenceUploadConfirmResult",
    "EvidenceUploadItem",
    "EvidenceUploadPreview",
    "ProcessingHint",
    "ResolutionDecision",
    "evidence_preview_digest",
    "logical_document_id",
    "source_document_version_id",
]

#: 确认后创建的初始持久任务类型（OCR/处理在后台 worker 执行，不在确认调用内）。
EVIDENCE_PROCESSING_JOB_TYPE = "evidence_processing"
DIRECT_VISION_PREPARATION = "original-page-images/v1"

_SHA256 = r"^[0-9a-f]{64}$"


class ProcessingHint(str):
    """逐文件处理建议的机器值；由 :data:`PROCESSING_HINT_BY_STATUS` 冻结映射。"""


#: 分类 -> 处理建议的确定映射；预览条目必须携带与状态一致的建议，杜绝漂移。
PROCESSING_HINT_BY_STATUS: dict[UploadItemStatus, str] = {
    UploadItemStatus.ADDED: "process_new",
    UploadItemStatus.DUPLICATE: "reuse_existing",
    UploadItemStatus.CONFLICT: "require_resolution",
    UploadItemStatus.UNSUPPORTED: "rejected",
    UploadItemStatus.UNREADABLE: "rejected",
    UploadItemStatus.FULL_SNAPSHOT_OMISSION: "omitted",
    UploadItemStatus.EXPECTED_REPROCESSING: "reprocess",
}


# ---------------------------------------------------------------------------
# 确定性身份
# ---------------------------------------------------------------------------


def logical_document_id(
    *,
    project_id: str,
    subject_id: str,
    review_episode_id: str,
    sha256: str,
) -> str:
    """逻辑资料的内容身份（作用域 + 内容 SHA-256）。

    同一内容在同一审核节点作用域内映射到同一逻辑资料；不同受试者/节点/项目因
    作用域不同而不合并。文件名不参与计算，因此改名不改变逻辑资料身份。
    """
    return canonical_hash(
        {
            "logical_document": "v1",
            "scope": {
                "project_id": project_id,
                "subject_id": subject_id,
                "review_episode_id": review_episode_id,
            },
            "sha256": sha256,
        }
    )


def source_document_version_id(
    *,
    logical_document_id: str,
    version_number: int,
    sha256: str,
) -> str:
    """资料版本的内容身份：逻辑资料 + 版本号 + 内容 SHA-256。

    确定性的版本身份使重复确认同一内容产生同一版本行，可安全复用而不重复创建；
    同逻辑资料不同内容产生不同版本身份。
    """
    return canonical_hash(
        {
            "version": "v1",
            "logical_document_id": logical_document_id,
            "version_number": version_number,
            "sha256": sha256,
        }
    )


def evidence_preview_digest(preview: EvidenceUploadPreview) -> str:
    """预览摘要：对作用域、上传方式、基准修订号/快照与逐文件内容做确定性哈希。

    与文件时间戳、路径无关；服务端在确认时从存储条目重算并与前端回传摘要比对，
    拒绝任何不一致，保证用户确认的就是服务端实际持有的预览。
    """
    items = sorted(
        (
            item.file_name,
            item.sha256 or "",
            item.status.value,
            item.logical_document_id or "",
        )
        for item in preview.items
    )
    return canonical_hash(
        {
            "preview": "evidence_upload_preview/v1",
            "scope": {
                "project_id": preview.project_id,
                "subject_id": preview.subject_id,
                "review_episode_id": preview.review_episode_id,
            },
            "upload_mode": preview.upload_mode.value,
            "base_revision": preview.base_revision,
            "base_snapshot_id": preview.base_snapshot_id,
            "items": items,
        }
    )


# ---------------------------------------------------------------------------
# 预览与条目
# ---------------------------------------------------------------------------


class EvidenceUploadItem(ContractModel):
    """逐文件指纹/格式/大小/分类/处理建议/重复关系/冲突（预览条目）。

    ``file_name`` 只用于展示与同名冲突判断，永不作为内容身份；``sha256`` 是内容
    身份。``storage_ref`` 指向预览自有的暂存引用（相对路径），不暴露本机绝对路径；
    取消只清理该暂存，不触碰共享 blob。``logical_document_id`` /
    ``existing_version_id`` 在命中基准快照时绑定被关联的逻辑资料与活动版本。
    """

    item_id: str = Field(min_length=1)
    preview_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=_SHA256)
    byte_size: int = Field(ge=0)
    media_type: str = Field(default="application/octet-stream", min_length=1)
    storage_ref: str | None = None
    status: UploadItemStatus
    processing_hint: str = Field(min_length=1)
    logical_document_id: str | None = None
    existing_version_id: str | None = None
    error_detail: str | None = None

    @model_validator(mode="after")
    def validate_item(self) -> EvidenceUploadItem:
        expected_hint = PROCESSING_HINT_BY_STATUS[self.status]
        if self.processing_hint != expected_hint:
            raise ValueError(
                f"处理建议与分类不一致：{self.status.value} 应为 {expected_hint}，"
                f"收到 {self.processing_hint}"
            )

        staged_statuses = {
            UploadItemStatus.ADDED,
            UploadItemStatus.DUPLICATE,
            UploadItemStatus.CONFLICT,
            UploadItemStatus.UNSUPPORTED,
            UploadItemStatus.EXPECTED_REPROCESSING,
        }
        if self.status in staged_statuses:
            if self.storage_ref is None:
                raise ValueError(f"{self.status.value} 条目必须携带暂存引用")
            if self.storage_ref.startswith("/") or ".." in self.storage_ref:
                raise ValueError("暂存引用必须是可移植相对路径，不能是本机绝对路径")
        else:
            # unreadable / full_snapshot_omission：无本次暂存文件。
            if self.storage_ref is not None:
                raise ValueError(f"{self.status.value} 条目不能携带暂存引用")

        if (
            self.status == UploadItemStatus.UNREADABLE
            and self.sha256 is not None
        ):
            raise ValueError("无法读取的文件不能登记内容哈希")
        if self.status != UploadItemStatus.UNREADABLE and self.sha256 is None:
            raise ValueError(f"{self.status.value} 条目必须携带内容 SHA-256")

        if self.status in {
            UploadItemStatus.CONFLICT,
            UploadItemStatus.EXPECTED_REPROCESSING,
        } and (self.logical_document_id is None or self.existing_version_id is None):
            raise ValueError(
                f"{self.status.value} 条目必须绑定基准快照中的逻辑资料与活动版本"
            )
        if self.status == UploadItemStatus.DUPLICATE and self.logical_document_id is None:
            raise ValueError("内容重复条目必须绑定被去重的逻辑资料")
        if self.status == UploadItemStatus.UNSUPPORTED and not self.error_detail:
            raise ValueError("不支持的格式必须给出原因")
        if self.status == UploadItemStatus.UNREADABLE and not self.error_detail:
            raise ValueError("无法读取的文件必须给出原因")
        return self


class EvidenceUploadPreview(ContractModel):
    """短期候选预览：绑定作用域、上传方式、基准快照、创建时修订号与状态。

    补充资料（incremental）必须绑定唯一有效前序快照；完整资料（full）不继承前序，
    可绑定上一有效快照作为比较基线。``preview_sha256`` 是确定性摘要，确认时服务端
    重算核验。预览不是临床快照：取消/确认都不改写既有快照或历史。
    """

    preview_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    upload_mode: UploadMode
    base_revision: int = Field(ge=1)
    base_snapshot_id: str | None = None
    status: UploadPreviewStatus
    items: list[EvidenceUploadItem] = Field(default_factory=list)
    matching_snapshot_id: str | None = None
    matching_snapshot_status: SnapshotStatus | None = None
    preview_sha256: str = Field(pattern=_SHA256)
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_preview(self) -> EvidenceUploadPreview:
        _require_utc(self.created_at, "EvidenceUploadPreview.created_at")
        if self.upload_mode == UploadMode.INCREMENTAL and self.base_snapshot_id is None:
            raise ValueError("补充资料预览必须绑定唯一的有效前序快照")
        # 完整资料预览可绑定上一有效快照作为比较基线（全量方式保留旧快照并展示
        # 本次与上一有效快照的差异基线），无前序快照时可为空。
        for item in self.items:
            if item.preview_id != self.preview_id:
                raise ValueError("预览条目必须属于当前预览")
        if (self.matching_snapshot_id is None) != (
            self.matching_snapshot_status is None
        ):
            raise ValueError("重复资料版本标识与状态必须同时存在或同时为空")
        expected = evidence_preview_digest(self)
        if self.preview_sha256 != expected:
            raise ValueError("预览摘要与逐文件内容不一致")
        return self


# ---------------------------------------------------------------------------
# 确认
# ---------------------------------------------------------------------------


class ResolutionDecision(ContractModel):
    """一个同名异内容文件在确认时实际应用的处置决策（追加进确认记录）。"""

    item_id: str = Field(min_length=1)
    logical_document_id: str = Field(min_length=1)
    resolution: UploadConflictResolution
    source_document_version_id: str = Field(min_length=1)
    supersedes_version_id: str | None = None


class EvidenceUploadConfirmInput(ContractModel):
    """确认命令：服务端重算校验摘要、作用域、基准修订号与处置，不信任前端摘要。"""

    preview_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    upload_mode: UploadMode
    base_revision: int = Field(ge=1)
    preview_sha256: str = Field(pattern=_SHA256)
    idempotency_key: str = Field(min_length=1)
    resolutions: dict[str, UploadConflictResolution] = Field(default_factory=dict)


class EvidenceUploadConfirmResult(ContractModel):
    """确认结果：返回既有候选/活动快照（重复 no-op）或新建快照与初始持久任务。

    ``created``/``replayed``/``duplicate`` 三个标志互斥可解释：

    - 首次创建新候选：``created=True, replayed=False, duplicate=False``；
    - 同一幂等键再次请求（回放）：``created=False, replayed=True``，
      ``duplicate`` 保留原确认是否命中重复集合的事实；
    - 新预览/新幂等键命中同集合候选：``created=False, replayed=False,
      duplicate=True``。

    ``replayed`` 只能由 service 在幂等记录命中分支赋值，不允许调用方用
    ``not created`` 猜测；同键回放与跨预览同集合 no-op 是两种不同事实。
    """

    commit_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    snapshot: EvidenceSnapshot
    job_id: str | None = None
    created: bool = False
    replayed: bool = False
    duplicate: bool = False

    @model_validator(mode="after")
    def validate_flags(self) -> EvidenceUploadConfirmResult:
        if self.created and (self.replayed or self.duplicate):
            raise ValueError("新建候选不能同时标记为回放或重复集合 no-op")
        if not self.created and not self.replayed and not self.duplicate:
            raise ValueError("确认结果必须标记为新建、回放或重复集合 no-op 之一")
        return self


class EvidenceUploadCommit(ContractModel):
    """确认动作：预览摘要哈希、幂等键、产生的候选快照/持久任务与重复 no-op 标志。

    与候选快照、初始持久 Job、幂等记录在同一事务中创建或复用；``duplicate=True``
    表示命中同作用域/上传方式/活动成员集合的既有候选或活动快照，未创建新 Job
    （此时 ``job_id`` 为空）。
    """

    commit_id: str = Field(min_length=1)
    preview_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    upload_mode: UploadMode
    preview_sha256: str = Field(pattern=_SHA256)
    idempotency_key: str = Field(min_length=1)
    job_id: str | None = None
    duplicate: bool = False
    resolutions: list[ResolutionDecision] = Field(default_factory=list)
    created_at: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_commit(self) -> EvidenceUploadCommit:
        _require_utc(self.created_at, "EvidenceUploadCommit.created_at")
        return self


def _require_utc(value: datetime, field_name: str) -> None:
    """Reject naive or non-UTC timestamps at the Phase 4 contract boundary."""
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{field_name} 必须携带 UTC 时区")
    if offset.total_seconds() != 0:
        raise ValueError(f"{field_name} 必须使用 UTC 时区")
