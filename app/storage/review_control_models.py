"""One immutable supplemental-requirement report part per review run."""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base
from app.storage.models import AppendedRecordMixin


class ReviewControlSnapshotRecord(AppendedRecordMixin, Base):
    __tablename__ = "review_control_snapshots"

    review_run_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_runs.review_run_id"), primary_key=True,
    )
    context_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("review_context_snapshots.context_id"), nullable=False,
    )
    gate_result_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("gate_results.gate_result_id"), nullable=False,
    )
