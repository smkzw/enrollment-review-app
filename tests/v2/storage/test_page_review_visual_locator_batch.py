"""视觉定位批量核验上下文的回归测试：结果等价 + 污染拒绝 + 查询削减。"""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain.contracts.page_review import PageDisposition
from app.domain.contracts.rules import RuleSet
from app.projections.clause_pack import project_clause_pack
from app.services.page_review_visual_sources import rebuild_visual_sources
from app.storage.codecs import decode_contract, encode_contract, to_utc_naive
from app.storage.models import RuleSetRecord
from app.storage.page_review_visual_locator_validation import (
    VisualLocatorBatchContext,
    verify_visual_locator,
    verify_visual_locator_authority,
)
from app.storage.repositories import InvalidReferenceError
from tests.v2.domain.test_page_review_contracts import _fact
from tests.v2.services.test_fact_normalization_persistence import NOW, _seed_chain
from tests.v2.services.test_r3_page_review_normalizer_wiring import _persist_page_review


def _fact_two():
    from app.domain.contracts.page_review import ObservationContext, PageFactObservation
    from app.domain.page_normalization import fact_normalization_key

    context = ObservationContext(target_text="血红蛋白")
    key, value, unit = fact_normalization_key(
        "实验室检查值", "150 g/L", context=context.model_dump()
    )
    payload = _fact().model_dump()
    payload.update(
        observation_id="fact-2",
        raw_text="血红蛋白 150 g/L",
        raw_value="150 g/L",
        normalized_value=value,
        normalized_unit=unit,
        normalization_key=key,
        region={"excerpt": "血红蛋白 150 g/L"},
        context=context.model_dump(),
    )
    return PageFactObservation.model_validate(payload)


def _setup_visual(session, prefix, *, persist=True):
    from app.projections.page_review_visual_locators import project_visual_locators
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    chain = _seed_chain(session, prefix=prefix)
    authority = chain["authority"]
    row = session.get(RuleSetRecord, (authority.rule_set_id, authority.rule_set_revision))
    pack = project_clause_pack(decode_contract(RuleSet, row.payload_json, row.payload_sha256))
    coverage_id = _persist_page_review(session, chain, pack=pack, facts=[_fact(), _fact_two()])
    sources = rebuild_visual_sources(session, authority, coverage_id)
    locators = [locator for group in sources for locator in project_visual_locators(group)]
    assert len(locators) >= 2
    repository = EvidenceLocatorRepository(session)
    for locator in locators if persist else []:
        repository.create(locator)
    return chain, authority, coverage_id, locators


def test_create_many_new_visual_locators_validates_before_writes(session_factory, monkeypatch):
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, "visual-new-batch", persist=False)
        count = _count_rebuilds(monkeypatch)
        result = EvidenceLocatorRepository(session).create_visual_many(locators)
        assert result == locators
        assert count == {"revision_get": 1, "association_build": 1}
        assert EvidenceLocatorRepository(session).get_many([item.locator_id for item in locators]) == locators


def test_create_visual_many_rejects_invalid_batch_before_any_insert(session_factory):
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, "visual-new-bad", persist=False)
        invalid = locators[-1].model_copy(update={"excerpt": "并非原文"})
        with pytest.raises((InvalidReferenceError, ValueError)):
            EvidenceLocatorRepository(session).create_visual_many([locators[0], invalid])
        assert session.get(EvidenceLocatorArtifactRecord, locators[0].locator_id) is None


def _count_gets(monkeypatch):
    from sqlalchemy.orm import Session

    counter = {"n": 0}
    original = Session.get

    def counting(self, *args, **kwargs):
        counter["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Session, "get", counting)
    return counter


def _count_rebuilds(monkeypatch):
    import app.storage.page_review_visual_locator_validation as validation
    from app.storage import evidence_locator_repositories as repositories

    counter = {"revision_get": 0, "association_build": 0}
    original_get = repositories.CompleteEvidenceProcessingRevisionRepository.get
    original_sources = validation.page_association_sources

    def counting_get(self, revision_id):
        counter["revision_get"] += 1
        return original_get(self, revision_id)

    def counting_sources(session, revision):
        counter["association_build"] += 1
        return original_sources(session, revision)

    monkeypatch.setattr(
        repositories.CompleteEvidenceProcessingRevisionRepository, "get", counting_get
    )
    monkeypatch.setattr(validation, "page_association_sources", counting_sources)
    return counter


def _ocr_page_id(session, revision_id):
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )

    revision = CompleteEvidenceProcessingRevisionRepository(session).get(revision_id)
    return revision.manifest[0].ocr_page_id


def test_batch_verify_returns_same_coverage(session_factory):
    with session_factory() as session, session.begin():
        chain, authority, _, locators = _setup_visual(session, prefix="visual-batch-equiv")
        batch = VisualLocatorBatchContext(session)
        for locator in locators:
            single = verify_visual_locator(session, locator)
            batched = verify_visual_locator(session, locator, batch=batch)
            assert batched == single
            verify_visual_locator_authority(session, locator, authority, batch=batch)
        with pytest.raises(InvalidReferenceError):
            verify_visual_locator_authority(
                session, locators[0],
                authority.model_copy(update={"subject_id": "other-subject"}),
                batch=batch,
            )


def test_batch_rebuilds_shared_revision_once(session_factory, monkeypatch):
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-count")
        gets = _count_gets(monkeypatch)
        rebuilds = _count_rebuilds(monkeypatch)
        for locator in locators:
            verify_visual_locator(session, locator)
        single_gets = gets["n"]
        assert rebuilds["revision_get"] == len(locators)
        assert rebuilds["association_build"] == len(locators)

        gets["n"] = 0
        rebuilds["revision_get"] = 0
        rebuilds["association_build"] = 0
        batch = VisualLocatorBatchContext(session)
        for locator in locators:
            verify_visual_locator(session, locator, batch=batch)
        assert rebuilds["revision_get"] == 1
        assert rebuilds["association_build"] == 1
        assert gets["n"] < single_gets


def test_get_many_batches_shared_revision(session_factory, monkeypatch):
    from app.storage.evidence_locator_repositories import EvidenceLocatorRepository

    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-getmany")
        rebuilds = _count_rebuilds(monkeypatch)
        repository = EvidenceLocatorRepository(session)
        ids = [locator.locator_id for locator in locators]
        for locator_id in ids:
            repository.get(locator_id)
        assert rebuilds["revision_get"] == len(locators)
        rebuilds["revision_get"] = 0
        rebuilds["association_build"] = 0
        assert [item.locator_id for item in repository.get_many(ids)] == ids
        assert rebuilds["revision_get"] == 1
        assert rebuilds["association_build"] == 1


def test_persist_visual_locators_shares_batch(session_factory, monkeypatch):
    from app.services.page_review_visual_sources import persist_visual_locators

    with session_factory() as session, session.begin():
        _, authority, coverage_id, locators = _setup_visual(
            session, prefix="visual-batch-persist"
        )
        rebuilds = _count_rebuilds(monkeypatch)
        persist_visual_locators(session, authority, coverage_id)
        # rebuild_visual_sources 自带两次整修订核验（权威校验 + 来源重建，不在本
        # 次授权改动面内）；已存在定位的逐个复核只做一次整修订核验和一次来源重建。
        assert rebuilds["revision_get"] == 3
        assert rebuilds["association_build"] == 1


def test_tampered_locator_rejected_before_and_after_reuse(session_factory):
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-tamper")
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        forged = locators[0].model_copy(update={"excerpt": "伪造的摘录内容"})
        with pytest.raises(InvalidReferenceError, match="双模型原始判读"):
            verify_visual_locator(session, forged)
        with pytest.raises(InvalidReferenceError, match="双模型原始判读"):
            verify_visual_locator(session, forged, batch=batch)
        # 拒绝之后，合法定位仍可通过：拒绝没有污染上下文。
        verify_visual_locator(session, locators[0], batch=batch)


def test_changed_source_text_rejected_after_reuse(session_factory):
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.ocr_models import OCRPageRecord

    with session_factory() as session, session.begin():
        chain, _, _, locators = _setup_visual(session, prefix="visual-batch-source")
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        ocr_id = _ocr_page_id(session, chain["complete_revision_id"])
        row = session.get(OCRPageRecord, ocr_id)
        altered = row.raw_text + "（篡改追加）"
        row.raw_text = altered
        row.raw_text_sha256 = hashlib.sha256(altered.encode()).hexdigest()
        session.flush()
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(session, locators[0], batch=batch)


def test_changed_reconciliation_rejected_after_reuse(session_factory):
    from app.domain.contracts.page_review import PageReconciliation
    from app.storage.page_review_models import PageReconciliationORM
    from app.storage.page_review_repository import PageReviewRepository

    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-recon")
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        binding = locators[0].page_review_visual
        coverage = PageReviewRepository(session).get_coverage(binding.coverage_id)
        entry = next(
            item for item in coverage.entries
            if item.page_artifact_id == locators[0].page_artifact_id
        )
        row = session.get(PageReconciliationORM, entry.reconciliation_id)
        record = decode_contract(PageReconciliation, row.payload_json, row.payload_sha256)
        shifted = record.created_at + timedelta(seconds=1)
        payload_json, payload_sha256 = encode_contract(
            record.model_copy(update={"created_at": shifted})
        )
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256
        row.created_at = to_utc_naive(shifted)
        session.flush()
        with pytest.raises(InvalidReferenceError):
            verify_visual_locator(session, locators[0], batch=batch)


def test_changed_coverage_rejected_after_reuse(session_factory):
    from app.domain.contracts.page_review import SubjectPageCoverage
    from app.storage.page_review_models import (
        SubjectPageCoverageEntryORM,
        SubjectPageCoverageORM,
    )

    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-coverage")
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        binding = locators[0].page_review_visual
        row = session.get(SubjectPageCoverageORM, binding.coverage_id)
        record = decode_contract(SubjectPageCoverage, row.payload_json, row.payload_sha256)
        entries = [
            item.model_copy(update={"disposition": PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE,
                                    "discard_reason": "测试覆盖变脏",
                                    "reconciliation_id": None,
                                    "lane_failures": []})
            if item.page_artifact_id == locators[0].page_artifact_id
            else item
            for item in record.entries
        ]
        payload_json, payload_sha256 = encode_contract(
            record.model_copy(update={"entries": entries})
        )
        row.payload_json = payload_json
        row.payload_sha256 = payload_sha256
        child = session.execute(
            select(SubjectPageCoverageEntryORM).where(
                SubjectPageCoverageEntryORM.coverage_id == binding.coverage_id,
                SubjectPageCoverageEntryORM.page_artifact_id
                == locators[0].page_artifact_id,
            )
        ).scalars().all()[0]
        child.disposition = PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE.value
        child.reconciliation_id = None
        child.discard_reason = "测试覆盖变脏"
        session.flush()
        with pytest.raises(InvalidReferenceError, match="已完成核对"):
            verify_visual_locator(session, locators[0], batch=batch)


def test_cycle_still_rejected_with_batch(session_factory):
    from app.storage.evidence_locator_models import ProcessingRevisionLocatorRecord

    with session_factory() as session, session.begin():
        chain, _, _, locators = _setup_visual(session, prefix="visual-batch-cycle")
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        session.add(
            ProcessingRevisionLocatorRecord(
                revision_id=chain["complete_revision_id"],
                position=9999,
                locator_id=locators[0].locator_id,
            )
        )
        session.flush()
        with pytest.raises(InvalidReferenceError, match="不能追加"):
            verify_visual_locator(session, locators[0])
        with pytest.raises(InvalidReferenceError, match="不能追加"):
            verify_visual_locator(session, locators[0], batch=batch)


def test_batch_context_rejects_foreign_session(session_factory):
    with session_factory() as first, session_factory() as second:
        with first.begin():
            _, _, _, locators = _setup_visual(first, prefix="visual-batch-foreign")
        batch = VisualLocatorBatchContext(first)
        with pytest.raises(InvalidReferenceError, match="跨会话"):
            batch.verify(second, locators[0])
        other = VisualLocatorBatchContext(second)
        assert other._entries is not batch._entries


def test_committed_mutation_in_other_session_does_not_pass(session_factory):
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.ocr_models import OCRPageRecord

    with session_factory() as first:
        with first.begin():
            chain, _, _, locators = _setup_visual(first, prefix="visual-batch-xact")
        batch = VisualLocatorBatchContext(first)
        verify_visual_locator(first, locators[0], batch=batch)
        ocr_id = _ocr_page_id(first, chain["complete_revision_id"])
        with session_factory() as second:
            with second.begin():
                row = second.get(OCRPageRecord, ocr_id)
                altered = row.raw_text + "（他会话篡改）"
                row.raw_text = altered
                row.raw_text_sha256 = hashlib.sha256(altered.encode()).hexdigest()
        first.expire_all()
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(first, locators[0], batch=batch)
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(first, locators[0])


def test_changed_metadata_child_rejected_after_reuse(session_factory):
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord

    prefix = "visual-batch-metadata"
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix=prefix)
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        assert batch._entries, "首检应缓存整修订核验输入"
        row = session.get(SourceDocumentMetadataRevisionRecord, f"{prefix}-metadata")
        row.document_type = "被篡改的资料类型"
        session.flush()
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(session, locators[0], batch=batch)
        assert batch._entries == {}


def test_same_session_sql_update_and_commit_invalidates(session_factory):
    from sqlalchemy import update

    from app.storage.codecs import PersistedContractInvalid
    from app.storage.ocr_models import OCRPageRecord
    with session_factory() as session:
        with session.begin():
            chain, _, _, locators = _setup_visual(session, prefix="visual-batch-sqlcommit")
            ocr_id = _ocr_page_id(session, chain["complete_revision_id"])
        with session.begin():
            batch = VisualLocatorBatchContext(session)
            verify_visual_locator(session, locators[0], batch=batch)
            assert batch._entries, "首检应缓存整修订核验输入"
            altered = "SQL 直写篡改"
            session.execute(
                update(OCRPageRecord)
                .where(OCRPageRecord.ocr_page_id == ocr_id)
                .values(
                    raw_text=altered,
                    raw_text_sha256=hashlib.sha256(altered.encode()).hexdigest(),
                )
                .execution_options(synchronize_session=False)
            )
        with session.begin():
            with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
                verify_visual_locator(session, locators[0], batch=batch)
            assert batch._entries == {}


def test_nested_rollback_forces_full_reverification(session_factory, monkeypatch):
    from app.storage.ocr_models import OCRPageRecord

    with session_factory() as session, session.begin():
        chain, _, _, locators = _setup_visual(session, prefix="visual-batch-savepoint")
        ocr_id = _ocr_page_id(session, chain["complete_revision_id"])
        rebuilds = _count_rebuilds(monkeypatch)
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        assert rebuilds["revision_get"] == 1
        savepoint = session.begin_nested()
        try:
            row = session.get(OCRPageRecord, ocr_id)
            row.raw_text = row.raw_text + "（回滚的脏写）"
            session.flush()
        finally:
            savepoint.rollback()
        verify_visual_locator(session, locators[0], batch=batch)
        assert rebuilds["revision_get"] == 2


def test_valid_savepoint_cannot_cache_state_restored_invalid_by_rollback(session_factory):
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord

    prefix = "visual-batch-reverse-savepoint"
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix=prefix)
        row = session.get(SourceDocumentMetadataRevisionRecord, f"{prefix}-metadata")
        original = row.document_type
        row.document_type = "篡改"
        session.flush()
        nested = session.begin_nested()
        row.document_type = original
        session.flush()
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        assert not batch._entries
        nested.rollback()
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(session, locators[0], batch=batch)


def test_changes_during_source_build_do_not_qualify_cache(session_factory, monkeypatch):
    import app.storage.page_review_visual_locator_validation as validation
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord

    prefix = "visual-batch-build-change"
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix=prefix)
        original = validation.page_association_sources

        def changing_sources(session, revision):
            sources = original(session, revision)
            row = session.get(SourceDocumentMetadataRevisionRecord, f"{prefix}-metadata")
            row.document_type = "篡改"
            session.flush()
            return sources

        monkeypatch.setattr(validation, "page_association_sources", changing_sources)
        batch = VisualLocatorBatchContext(session)
        verify_visual_locator(session, locators[0], batch=batch)
        assert not batch._entries
        with pytest.raises((InvalidReferenceError, PersistedContractInvalid)):
            verify_visual_locator(session, locators[0], batch=batch)


def test_authority_revalidates_same_locator_on_later_call(session_factory, monkeypatch):
    from app.storage.fact_authority import FactAuthorityValidator

    with session_factory() as session, session.begin():
        _, authority, _, locators = _setup_visual(session, prefix="visual-authority-again")
        validator = FactAuthorityValidator(session)
        validator.validate_locators(authority, [locators[0].locator_id])

        def reject(*args):
            raise InvalidReferenceError("来源已变化")

        monkeypatch.setattr(validator, "_validate_locator", reject)
        with pytest.raises(InvalidReferenceError, match="来源已变化"):
            validator.validate_locators(authority, [locators[0].locator_id])


def test_non_sqlite_backend_skips_reuse_without_changing_results(
    session_factory, monkeypatch
):
    with session_factory() as session, session.begin():
        _, _, _, locators = _setup_visual(session, prefix="visual-batch-dialect")
        rebuilds = _count_rebuilds(monkeypatch)
        monkeypatch.setattr(session.get_bind().dialect, "name", "postgresql")
        batch = VisualLocatorBatchContext(session)
        first = verify_visual_locator(session, locators[0], batch=batch)
        second = verify_visual_locator(session, locators[0], batch=batch)
        assert second == first
        assert rebuilds["revision_get"] == 2
        assert rebuilds["association_build"] == 2
        assert batch._entries == {}


def test_authority_validate_locators_shares_revision_check(
    session_factory, monkeypatch
):
    from app.storage.fact_authority import FactAuthorityValidator

    with session_factory() as session, session.begin():
        _, authority, _, locators = _setup_visual(
            session, prefix="visual-batch-authority"
        )
        ids = sorted({loc.locator_id for loc in locators})
        assert len(ids) >= 2
        rebuilds = _count_rebuilds(monkeypatch)
        FactAuthorityValidator(session).validate_locators(authority, ids)
        assert rebuilds["revision_get"] == 1
        assert rebuilds["association_build"] == 1


def test_gates_visual_batch_shared_across_candidates(session_factory, monkeypatch):
    from app.domain.contracts.enums import FactPolarity
    from app.domain.contracts.facts import ClinicalFactCandidateV2
    from app.domain.gates.fact_evidence_closure import validate_locator_and_text_hash
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
    )

    with session_factory() as session, session.begin():
        chain, _, _, locators = _setup_visual(session, prefix="visual-batch-gates")
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(
            chain["complete_revision_id"]
        )
        ids = sorted({loc.locator_id for loc in locators})
        assert len(ids) >= 2

        def _candidate(cid, lids):
            return ClinicalFactCandidateV2(
                candidate_id=cid,
                run_id="run-1",
                call_id="call-1",
                fact_type="diagnosis",
                polarity=FactPolarity.UNKNOWN,
                asserted_object="视觉定位来源等价",
                locator_ids=sorted(lids),
                candidate_source_semantics="测试",
                model_uncertainty=0.1,
                created_at=NOW,
            )
        candidates = [
            _candidate("gates-batch-c1", ids[:1]),
            _candidate("gates-batch-c2", ids[1:2]),
        ]
        rebuilds = _count_rebuilds(monkeypatch)
        single = [validate_locator_and_text_hash(session, cand, revision) for cand in candidates]
        # 未批处理时同一修订被重复核验；批处理把全部重复压缩到一次。
        assert rebuilds["revision_get"] > 1
        assert rebuilds["association_build"] > 1
        rebuilds["revision_get"] = 0
        rebuilds["association_build"] = 0
        batch = VisualLocatorBatchContext(session)
        batched = [
            validate_locator_and_text_hash(session, cand, revision, visual_batch=batch)
            for cand in candidates
        ]
        assert [(out, sorted(reasons)) for out, reasons, _ in batched] == [
            (out, sorted(reasons)) for out, reasons, _ in single
        ]
        assert rebuilds["revision_get"] == 1
        assert rebuilds["association_build"] == 1
