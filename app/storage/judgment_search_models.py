"""研究者书面判断检索覆盖摘要的不可变持久化模型。"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.evidence_models import PAYLOAD_SHA_LEN, EvidenceAppendedRecordMixin


class JudgmentSearchSummaryORM(EvidenceAppendedRecordMixin, Base):
    """每条要求在当前权威元组下的检索覆盖摘要（追加写，最新行即当前结论）。

    ``summary_id`` 内容寻址：同一权威、同一范围、同一回执集合得到同一身份；
    检索重跑产生新行，旧行按不可变历史保留。列镜像便于按权威元组直接查询，
    正文合同仍以 ``payload_json`` 为准。
    """

    __tablename__ = "judgment_search_summaries"

    summary_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), ForeignKey("subjects.subject_id"), nullable=False)
    review_episode_id: Mapped[str] = mapped_column(String(128), ForeignKey("review_episodes.review_episode_id"), nullable=False)
    evidence_snapshot_id: Mapped[str] = mapped_column(String(128), ForeignKey("evidence_snapshots_v2.evidence_snapshot_id"), nullable=False)
    evidence_processing_revision_id: Mapped[str] = mapped_column(String(128), ForeignKey("evidence_processing_revisions.evidence_processing_revision_id"), nullable=False)
    rule_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_set_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(PAYLOAD_SHA_LEN), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    found_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('candidates_present','all_supplied_pages_searched_without_candidate',"
            "'coverage_incomplete')",
            name="ck_jss_status",
        ),
        CheckConstraint("found_candidate_count >= 0", name="ck_jss_found_count"),
        Index(
            "ix_jss_authority_requirement",
            "review_episode_id",
            "evidence_processing_revision_id",
            "rule_set_id",
            "rule_set_revision",
            "requirement_id",
        ),
    )


__all__ = ["JudgmentSearchSummaryORM"]
