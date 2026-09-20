"""Select an unambiguous, source-bound coverage for the formal normalizer."""

from sqlalchemy import select

from app.domain.contracts.rules import RuleSet
from app.domain.contracts.page_review import PAGE_REVIEW_CONTRACT_VERSION
from app.domain.page_reconciliation import reconcile_page_reviews
from app.llm.page_review_harness import PAGE_REVIEW_PROMPT_VERSION
from app.llm.page_review_transport_options import page_transport_contract
from app.projections.clause_pack import clause_determination_modes
from app.services.published_clause_pack import project_published_clause_pack
from app.services.evidence_app_errors import EvidenceAppError
from app.storage.codecs import decode_contract
from app.storage.models import RuleSetRecord
from app.storage.page_review_models import SubjectPageCoverageORM
from app.storage.page_review_repository import PageReviewRepository
from app.services.page_review_job_service import page_review_execution_versions


class PageCoverageNotReady(EvidenceAppError):
    status_code = 409
    code = "PAGE_COVERAGE_NOT_READY"
    title = "资料判读尚未完成"
    recovery = "请先完成当前资料的逐页判读，处理未能读取的页面后再整理个例档案。"


def select_normalizer_coverage(session, authority, *, main_reader_identity_sha256=None):
    row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
    if row is None:
        raise PageCoverageNotReady()
    pack = project_published_clause_pack(session, decode_contract(RuleSet, row.payload_json, row.payload_sha256))
    ids = session.scalars(select(SubjectPageCoverageORM.coverage_id).where(
        SubjectPageCoverageORM.subject_id == authority.subject_id,
        SubjectPageCoverageORM.review_episode_id == authority.review_episode_id,
        SubjectPageCoverageORM.evidence_snapshot_id == authority.evidence_snapshot_v2_id,
        SubjectPageCoverageORM.evidence_processing_revision_id == authority.complete_processing_revision_id,
        SubjectPageCoverageORM.clause_pack_sha256 == pack.clause_pack_sha256,
    )).all()
    repository = PageReviewRepository(session)
    versions = page_review_execution_versions()
    candidates = [repository.get_coverage(key) for key in ids]
    candidates = [item for item in candidates if item.execution_versions == versions]
    by_id = {item.coverage_id: item for item in candidates}
    superseded = set()
    for item in candidates:
        predecessor = item.predecessor_coverage_id
        if predecessor is not None:
            if predecessor not in by_id or predecessor == item.coverage_id:
                raise PageCoverageNotReady("资料重读历史不完整，请核对处理记录。")
            superseded.add(predecessor)
        visited = {item.coverage_id}
        while predecessor is not None:
            if predecessor not in by_id or predecessor in visited:
                raise PageCoverageNotReady("资料重读历史不完整，请核对处理记录。")
            visited.add(predecessor)
            predecessor = by_id[predecessor].predecessor_coverage_id
    candidates = [item for item in candidates if item.coverage_id not in superseded]
    if main_reader_identity_sha256 is not None:
        candidates = [item for item in candidates
                      if item.main_reader_identity_sha256 == main_reader_identity_sha256]
    # Failed terminal attempts remain history, not competing usable coverage.
    # Apply this after lineage resolution so a failed successor cannot revive its parent.
    candidates = [item for item in candidates if not any(entry.lane_failures for entry in item.entries)]
    if len(candidates) != 1:
        raise PageCoverageNotReady("当前资料没有唯一可用的判读结果，请核对资料处理记录。")
    coverage = candidates[0]
    if any(entry.lane_failures for entry in coverage.entries):
        raise PageCoverageNotReady()
    from app.services.page_association_sources import page_association_sources
    from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
    revision = CompleteEvidenceProcessingRevisionRepository(session).get(authority.complete_processing_revision_id)
    sources = page_association_sources(session, revision)
    for entry in coverage.entries:
        if entry.reconciliation_id is None:
            continue
        reconciliation = repository.get_reconciliation(entry.reconciliation_id)
        records = [repository.get_review(key) for key in reconciliation.page_review_ids]
        for record in records:
            transport = page_transport_contract(record.provider)
            expected_prompt = PAGE_REVIEW_PROMPT_VERSION + (":" + transport if transport else "")
            if record.contract_version != PAGE_REVIEW_CONTRACT_VERSION or record.prompt_version != expected_prompt:
                raise PageCoverageNotReady("现有判读采用旧处理方式，请重新判读当前资料；历史记录仍保留。")
        expected = reconcile_page_reviews(
            records, determination_modes=clause_determination_modes(pack),
            association_source=sources.get(entry.page_artifact_id),
        )
        if expected.reconciliation_id != reconciliation.reconciliation_id:
            raise PageCoverageNotReady("现有核对结果与当前处理方式不一致，请重新核对资料。")
    return coverage.coverage_id
