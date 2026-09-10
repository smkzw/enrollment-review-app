"""Use the complete immutable read identity, not response-only deduplication."""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_NAME = "uq_prr_page_pack_lane_response"
_COLUMNS = ["page_artifact_id", "clause_pack_sha256", "lane", "response_sha256"]


def _alter(*, restore):
    bind = op.get_bind()
    raw = bind.connection.driver_connection
    enabled = raw.execute("PRAGMA foreign_keys").fetchone()[0]
    raw.commit()
    raw.execute("PRAGMA foreign_keys = OFF")
    try:
        with op.batch_alter_table("page_review_records") as batch:
            if restore:
                batch.create_unique_constraint(_NAME, _COLUMNS)
            else:
                batch.drop_constraint(_NAME, type_="unique")
    finally:
        raw.commit()
        raw.execute(f"PRAGMA foreign_keys = {int(enabled)}")
    if raw.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("0021 页判读历史关联完整性检查未通过")


def upgrade():
    _alter(restore=False)


def downgrade():
    duplicate = op.get_bind().exec_driver_sql(
        "SELECT 1 FROM page_review_records GROUP BY page_artifact_id, clause_pack_sha256, "
        "lane, response_sha256 HAVING COUNT(*) > 1 LIMIT 1"
    ).first()
    if duplicate:
        raise RuntimeError("0021 已有相同响应的不同判读历史，拒绝有损降级")
    _alter(restore=True)
