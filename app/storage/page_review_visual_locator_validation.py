"""Validate visual locators against persisted source records, including history.

``VisualLocatorBatchContext`` is the only sanctioned reuse scope for the
revision-wide inputs of this check. It is explicit, single-session, and
conservative: a cached revision entry is reused only while an opaque
DB-generation token (open transaction, DBAPI connection, clean ORM state,
SQLite ``data_version``/``total_changes``) is unchanged. Anything else —
same-session writes, commit/rollback, nested rollback, external commits,
pending state, non-SQLite backends, introspection failures — forces the full
verification. Coverage, reconciliation, reviews, and the cycle probe are
always read fresh.

Transaction reuse assumes SQLAlchemy-managed transactions/savepoints. Raw SQL
SAVEPOINT/ROLLBACK TO bypasses that tracking and must not be used by callers.
Identity-map freshness remains the same requirement as the full validation path.
"""

from sqlalchemy import select, text

from app.domain.contracts.page_review import PageDisposition
from app.domain.page_review_evidence_sources import materialize_page_visual_evidence_sources
from app.projections.page_review_visual_locators import project_visual_locators
from app.services.page_association_sources import page_association_sources
from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord
from app.storage.page_review_repository import PageReviewRepository
from app.storage.repositories import InvalidReferenceError


class _CachedVisualRevision:
    """Single verified revision: contract + full page sources + generation token."""

    __slots__ = ("revision", "sources", "token")

    def __init__(self, revision, sources, token):
        self.revision = revision
        self.sources = sources
        self.token = token


class VisualLocatorBatchContext:
    """Explicit single-session batch scope for visual locator verification.

    The first ``verify`` for a processing revision performs the full check
    (complete-revision closure + full page-association build). Later verifies
    in the same session reuse those inputs only while ``_snapshot_token``
    is unchanged; any database change visible through the token — or any
    inability to prove freshness — evicts the entry and reruns the full
    path. Failed verifications never leave an entry behind.
    No process-global state: concurrent sessions need separate instances.
    """

    def __init__(self, session):
        self._session = session
        self._entries = {}

    @property
    def session(self):
        return self._session

    def _require_session(self, session) -> None:
        if session is not self._session:
            raise InvalidReferenceError("视觉定位批量核验上下文不得跨会话复用")

    def verify(self, session, artifact):
        """Verify one visual locator, reusing verified revision inputs when safe."""
        self._require_session(session)
        binding, coverage, entry, reconciliation, records = _load_verification_inputs(
            session, artifact
        )
        revision, source = self._revision_and_page_source(
            session, binding.processing_revision_id, entry.page_artifact_id
        )
        try:
            return _materialize_and_compare(
                session, artifact, coverage, reconciliation, records, source
            )
        except Exception:
            self._entries.pop(binding.processing_revision_id, None)
            raise

    def _revision_and_page_source(self, session, revision_id, page_artifact_id):
        from app.storage.evidence_locator_repositories import (
            CompleteEvidenceProcessingRevisionRepository,
        )

        token = _snapshot_token(session)
        cached = self._entries.get(revision_id)
        if (
            cached is not None
            and token is not None
            and cached.token[0] is token[0]
            and cached.token[1:] == token[1:]
        ):
            return cached.revision, cached.sources.get(page_artifact_id)
        self._entries.pop(revision_id, None)
        try:
            revision = CompleteEvidenceProcessingRevisionRepository(session).get(revision_id)
            sources = page_association_sources(session, revision)
        except Exception:
            self._entries.pop(revision_id, None)
            raise
        after_token = _snapshot_token(session)
        if token is None or after_token != token:
            return revision, sources.get(page_artifact_id)
        self._entries[revision_id] = _CachedVisualRevision(revision, sources, token)
        return revision, sources.get(page_artifact_id)


def _snapshot_token(session):
    """Opaque DB-generation token, or None when reuse cannot be proven safe.

    Reuse requires all of: no pending ORM new/dirty/deleted state, an open
    session transaction, a SQLite backend, the same DBAPI connection, and
    unchanged SQLite ``data_version`` (cross-connection commits) plus
    per-connection ``total_changes`` (same-connection writes; the counter
    never goes backwards). ORM savepoints disable reuse because rollback does
    not increment that counter. Anything
    else returns None: the caller full-verifies without reusing or storing.
    """
    try:
        if session.new or session.dirty or session.deleted or session.in_nested_transaction():
            return None
        txn = session.get_transaction()
        if txn is None:
            return None
        bind = session.get_bind()
        if bind is None or getattr(getattr(bind, "dialect", None), "name", None) != "sqlite":
            return None
        connection = session.connection()
        dbapi_connection = getattr(connection, "connection", None)
        total_changes = getattr(dbapi_connection, "total_changes", None)
        data_version = connection.execute(text("PRAGMA data_version")).scalar()
        return (txn, id(dbapi_connection), int(data_version), int(total_changes))
    except Exception:
        return None


def _load_verification_inputs(session, artifact):
    """Fresh per-locator reads: binding, cycle probe, coverage, reconciliation."""
    binding = artifact.page_review_visual
    if binding is None:
        raise InvalidReferenceError("视觉定位缺少原始判读来源")
    # Reject cycles before resolving the immutable text processing revision.
    if session.scalar(select(ProcessingRevisionLocatorRecord.locator_id).where(
        ProcessingRevisionLocatorRecord.locator_id == artifact.locator_id
    )) is not None:
        raise InvalidReferenceError("视觉定位不能追加到既有文字处理修订")
    repository = PageReviewRepository(session)
    coverage = repository.get_coverage(binding.coverage_id)
    if coverage.evidence_processing_revision_id != binding.processing_revision_id:
        raise InvalidReferenceError("视觉定位与资料处理版本不一致")
    entry = next((entry for entry in coverage.entries
                  if entry.page_artifact_id == artifact.page_artifact_id), None)
    if entry is None or entry.disposition != PageDisposition.ACCEPTED:
        raise InvalidReferenceError("视觉定位未关联到已完成核对的原件页")
    reconciliation = repository.get_reconciliation(entry.reconciliation_id)
    records = [repository.get_review(key) for key in reconciliation.page_review_ids]
    return binding, coverage, entry, reconciliation, records


def _materialize_and_compare(session, artifact, coverage, reconciliation, records, source):
    try:
        source_set = materialize_page_visual_evidence_sources(
            records, reconciliation, coverage, association_source=source,
            page_text_sha256=source.text_sha256 if source else None,
        ).model_copy(update={"created_at": reconciliation.created_at})
    except ValueError as exc:
        raise InvalidReferenceError("原件定位的核对依据不完整或与保存记录不一致") from exc
    expected = next((item for item in project_visual_locators(source_set)
                     if item.locator_id == artifact.locator_id), None)
    if expected is None or expected.model_dump(mode="json") != artifact.model_dump(mode="json"):
        raise InvalidReferenceError("视觉定位与保存的双模型原始判读不一致")
    return coverage


def verify_visual_locator(session, artifact, *, batch=None):
    """Verify one visual locator against persisted source records.

    Without ``batch`` every call runs the full check (complete-revision
    closure + full page-association build). Pass a
    ``VisualLocatorBatchContext`` to reuse verified revision inputs within a
    single session; results are identical, only repeated work is removed.
    """
    if batch is not None:
        return batch.verify(session, artifact)
    from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository

    binding, coverage, entry, reconciliation, records = _load_verification_inputs(
        session, artifact
    )
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(binding.processing_revision_id)
    source = page_association_sources(session, revision).get(entry.page_artifact_id)
    return _materialize_and_compare(
        session, artifact, coverage, reconciliation, records, source
    )


def verify_visual_locator_authority(session, artifact, authority, *, batch=None):
    coverage = verify_visual_locator(session, artifact, batch=batch)
    if (coverage.subject_id, coverage.review_episode_id, coverage.evidence_snapshot_id,
        coverage.evidence_processing_revision_id) != (
        authority.subject_id, authority.review_episode_id, authority.evidence_snapshot_v2_id,
        authority.complete_processing_revision_id
    ):
        raise InvalidReferenceError("视觉定位不属于本次审核的原始资料")
