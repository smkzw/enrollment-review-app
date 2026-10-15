"""跨章控制目录发布的不可变持久化模型（迁移 0024）。

表 ``protocol_control_catalog_publications`` 与同一数据库内的协议、规则、Job、
检查点和门禁结果保持真实外键关系；正文以 ``payload_json``（规范化 JSON + 哈希）
为准，镜像列仅供直接查询。``(rule_set_id, rule_set_revision)`` 唯一：目录内容变化
必须发布新的正式规则修订，不能覆盖或挂接替换既有版本。
"""

from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.models import AppendedRecordMixin

__all__ = ["ProtocolControlCatalogRecord"]


class ProtocolControlCatalogRecord(AppendedRecordMixin, Base):
    """单个正式 RuleSet 修订的已发布跨章控制目录（追加写，永不原地覆盖）。"""

    __tablename__ = "protocol_control_catalog_publications"

    publication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("projects.project_id"),
        nullable=False,
    )
    protocol_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("protocol_document_versions.protocol_version_id"),
        nullable=False,
    )
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_job_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("jobs.job_id"),
        nullable=False,
    )
    source_checkpoint_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("job_checkpoints.checkpoint_id"),
        nullable=False,
    )
    gate_result_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("gate_results.gate_result_id"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "rule_set_id", "rule_set_revision", name="uq_pccp_rule_set_revision"
        ),
        ForeignKeyConstraint(
            ["rule_set_id", "rule_set_revision"],
            ["rule_sets.rule_set_id", "rule_sets.revision"],
        ),
    )
