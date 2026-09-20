"""Rebuild visual provenance from persisted reviews without changing revisions."""

from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review import PageDisposition
from app.domain.contracts.rules import RuleSet
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.page_review_evidence_sources import materialize_page_visual_evidence_sources
from app.projections.clause_pack import clause_determination_modes
from app.services.published_clause_pack import project_published_clause_pack
from app.services.page_association_sources import page_association_sources
from app.storage.codecs import decode_contract
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.models import RuleSetRecord
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.page_review_repository import PageReviewRepository

VISUAL_SOURCE_POLICY = "page-review-visual-sources/v1"


def persist_visual_locators(session, authority, coverage_id):
    from app.projections.page_review_visual_locators import project_visual_locators
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
    from app.storage.page_review_visual_locator_validation import VisualLocatorBatchContext
    from app.services.fact_normalization_source_adapter import FactPlanningSourceError
    repository = EvidenceLocatorRepository(session)
    batch = VisualLocatorBatchContext(session)
    pending = {}
    for group in rebuild_visual_sources(session, authority, coverage_id):
        for locator in project_visual_locators(group):
            if session.get(EvidenceLocatorArtifactRecord, locator.locator_id) is None:
                if locator.locator_id in pending and pending[locator.locator_id] != locator:
                    raise FactPlanningSourceError("同一原件定位对应了不一致的核对记录")
                pending[locator.locator_id] = locator
            elif repository.get(locator.locator_id, batch=batch) != locator:
                raise FactPlanningSourceError("已保存的原件定位与本次核对记录不一致")
    repository.create_visual_many(list(pending.values()))


def rebuild_visual_sources(session: Session, authority: FactAuthority, coverage_id: str, *, page_ids=None):
    from app.services.fact_normalization_source_adapter import FactPlanningSourceError

    try:
        return _rebuild_visual_sources(session, authority, coverage_id, page_ids=page_ids)
    except ValueError as exc:
        raise FactPlanningSourceError("原件核对记录与本次资料不一致，请重新核对资料后再整理。") from exc


def _rebuild_visual_sources(session: Session, authority: FactAuthority, coverage_id: str, *, page_ids=None):
    """Validate persisted authority and reconciliation before deriving source sets.

    No model calls or writes. This builder is for the active authority; historical
    presentation must consume its frozen input rather than rebind old coverage.
    """
    FactAuthorityValidator(session).validate(authority)
    repository = PageReviewRepository(session)
    coverage = repository.get_coverage(coverage_id)
    actual = (coverage.subject_id, coverage.review_episode_id,
              coverage.evidence_snapshot_id, coverage.evidence_processing_revision_id)
    expected = (authority.subject_id, authority.review_episode_id,
                authority.evidence_snapshot_v2_id, authority.complete_processing_revision_id)
    if actual != expected:
        raise ValueError("视觉来源与本次审核资料版本不一致")
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(
        authority.complete_processing_revision_id)
    row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
    if row is None:
        raise ValueError("视觉来源所依据的审核要求不存在")
    pack = project_published_clause_pack(session, decode_contract(RuleSet, row.payload_json, row.payload_sha256))
    if coverage.clause_pack_sha256 != pack.clause_pack_sha256:
        raise ValueError("视觉来源与本次审核要求版本不一致")
    associations = page_association_sources(session, revision)
    modes = clause_determination_modes(pack)
    results = []
    for entry in coverage.entries:
        if page_ids is not None and entry.page_artifact_id not in page_ids:
            continue
        if entry.disposition != PageDisposition.ACCEPTED:
            continue
        reconciliation = repository.get_reconciliation(entry.reconciliation_id)
        records = [repository.get_review(key) for key in reconciliation.page_review_ids]
        source = associations.get(entry.page_artifact_id)
        rebuilt = reconcile_page_reviews(records, determination_modes=modes, association_source=source)
        if rebuilt.reconciliation_id != reconciliation.reconciliation_id:
            raise ValueError("视觉来源的核对记录与原始判读不一致")
        result = materialize_page_visual_evidence_sources(
            records, reconciliation, coverage,
            page_text_sha256=source.text_sha256 if source else None,
            association_source=source,
        )
        # The stored reconciliation timestamp makes serialized rebuilds repeatable.
        results.append(result.model_copy(update={"created_at": reconciliation.created_at}))
    return tuple(results)
