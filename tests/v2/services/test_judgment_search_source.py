"""判断检索范围构建器的真实 SQLite 仓储测试（只读构建，未接产品临床链路）。

复用既有合成种子：`seed_valid_fact_chain`（完整修订链 + 活动指针 + FactAuthority）、
`_seed_rule_set_revision2`（跨规则集 revision 反例）、夹具 workflow stages +
`project_evidence_expectation_templates` + `save_expectation_templates`（既有已验证
模板边界）。多页链在测试内按同一仓储边界构建（现有共享夹具只有单页）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.domain.contracts.enums import PageArtifactStatus, ReviewStage, StudyPhase
from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import judgment_search_scope_sha256
from app.domain.contracts.ocr import PageArtifact
from app.domain.contracts.rules import EvidenceRequirement
from app.domain.publication import canonical_hash
from app.services.judgment_search_source import (
    JudgmentSearchSourceError,
    build_judgment_search_scope,
    prepare_judgment_search_target,
    scope_page_identity,
)
from app.storage.codecs import decode_contract, encode_contract
from app.storage.evidence_locator_repositories import RevisionClosureError
from app.storage.models import EvidenceExpectationTemplateRecord
from app.storage.ocr_models import PageArtifactRecord
from app.storage.ocr_repositories import PageArtifactRepository
from app.storage.repositories import (
    get_evidence_requirement,
    get_rule,
    get_rule_component,
    get_rule_set,
    list_expectation_templates,
)
from tests.v2.helpers.phase5_fact_chain import seed_valid_fact_chain

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
_REQUIREMENT = "req-professional"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- 种子助手


def _seed_templates(session, chain: dict) -> dict[str, object]:
    """经既有已验证边界落库冻结期望模板（发布同款：命名空间节点 + 投影 + 保存）。"""
    from app.projections.evidence_expectation_templates import (
        project_evidence_expectation_templates,
    )
    from app.storage.repositories import (
        WORKFLOW_STAGE_CONFIG,
        AppendRepository,
        get_rule_set,
        save_expectation_templates,
    )
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES

    fixture = FIXTURES[0]
    rule_set = get_rule_set(session, chain["rule_set_id"], 1)
    namespaced = [
        stage.model_copy(update={
            "workflow_stage_id": (
                f"{chain['rule_set_id']}:{chain['authority'].rule_set_revision}:"
                f"{stage.workflow_stage_id}"
            )
        })
        for stage in fixture.workflow_stages
    ]
    stage_repo = AppendRepository(session, WORKFLOW_STAGE_CONFIG)
    for stage in namespaced:
        stage_repo.save(stage, scope={
            "protocol_version_id": fixture.project.protocol_version.protocol_version_id,
            "study_phase": rule_set.study_phase.value,
        })
    templates = project_evidence_expectation_templates(
        rule_set=rule_set, workflow_stages=namespaced
    )
    save_expectation_templates(session, templates)
    return {template.requirement_id: template for template in templates}


def _seed_two_page_chain(session, prefix: str) -> dict[str, object]:
    """按同一仓储边界构建两页资料的完整修订链（现有共享夹具仅单页）。"""
    from app.domain.contracts.enums import (
        DisambiguationOutcome,
        EvidenceProcessingCandidateStatus,
        LocatorAuthenticity,
        LocatorPrecision,
        LocatorSourceLayer,
        SnapshotMemberOrigin,
        SnapshotStatus,
    )
    from app.domain.contracts.evidence_ingestion import (
        EvidenceSnapshot,
        EvidenceSnapshotMember,
        SourceDocumentMetadataRevision,
    )
    from app.domain.contracts.evidence_locator import (
        CompleteEvidenceProcessingRevision,
        EvidenceLocatorArtifact,
        EvidenceProcessingCandidate,
        EvidenceProcessingCandidateEvent,
        OCRRiskScan,
        ProcessingCandidateAttemptManifest,
        processing_candidate_input_hash,
    )
    from app.domain.contracts.evidence_processing import EvidenceProcessingRevision
    from app.domain.publication import (
        canonical_hash,
        evidence_processing_manifest_hash,
        evidence_snapshot_collection_hash,
    )
    from app.storage.evidence_locator_repositories import (
        CompleteEvidenceProcessingRevisionRepository,
        EvidenceLocatorRepository,
        EvidenceProcessingCandidateRepository,
        OCRRiskScanRepository,
    )
    from app.storage.evidence_repositories import (
        BlobRepository,
        EvidenceSnapshotRepository,
        SourceDocumentMetadataRevisionRepository,
        SourceDocumentRepository,
    )
    from app.storage.models import ProjectRecord, ReviewEpisodeRecord
    from app.storage.ocr_repositories import (
        EvidenceProcessingRevisionRepository,
        OcrPageRepository,
        OCRProfileRepository,
        PageArtifactRepository,
    )
    from app.storage.repositories import EpisodeRepository, persist_fixture
    from tests.v2.services.test_fact_normalization_persistence import _update_episode
    from tests.v2.storage.test_ocr_repositories import (
        make_artifact,
        make_blob,
        make_ocr_page,
        make_profile,
        make_version,
    )
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES
    from tests.v2.storage.test_slice44_repositories import RAW_TEXT

    fixture = FIXTURES[0]
    if session.get(ProjectRecord, fixture.project.project_id) is None:
        persist_fixture(session, fixture)
    project_id = fixture.project.project_id
    subject_id = fixture.subject.subject_id
    episode_id = fixture.review_episode.review_episode_id
    rule_set_id = fixture.rule_set.rule_set_id
    protocol_version_id = fixture.project.protocol_version.protocol_version_id
    snapshot_id = f"{prefix}-snapshot-v2"
    doc_id = f"{prefix}-doc"
    logical_document_id = f"{prefix}-log"

    blob = make_blob(f"{prefix}-pdf".encode("utf-8"))
    BlobRepository(session).get_or_create_by_sha256(blob)
    SourceDocumentRepository(session).create_version(
        make_version(
            version_id=doc_id,
            logical_id=logical_document_id,
            blob_sha=blob.sha256,
            scope=(project_id, subject_id, episode_id),
            page_count=2,
        )
    )
    EvidenceSnapshotRepository(session).create_full(
        EvidenceSnapshot(
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            upload_mode="full",
            members=[EvidenceSnapshotMember(
                member_id=f"{prefix}-member",
                snapshot_id=snapshot_id,
                logical_document_id=logical_document_id,
                source_document_version_id=doc_id,
                origin=SnapshotMemberOrigin.ADDED,
            )],
            collection_sha256=evidence_snapshot_collection_hash(
                members=[(logical_document_id, doc_id)]
            ),
            status=SnapshotStatus.STAGED,
            created_at=NOW,
            created_by="tester",
        )
    )
    profile = OCRProfileRepository(session).get_or_create(
        make_profile(profile_id=f"{prefix}-ocr-profile")
    )
    entries = []
    for page_number in (1, 2):
        page_input = _sha(f"{prefix}-page-input-{page_number}")
        page_source = _sha(f"{prefix}-page-source-{page_number}")
        artifact_id = f"{prefix}-pa-{page_number}"
        ocr_page_id = f"{prefix}-op-{page_number}"
        PageArtifactRepository(session).get_or_create(
            make_artifact(
                artifact_id=artifact_id,
                version_id=doc_id,
                page_number=page_number,
                page_input=page_input,
                source_sha=page_source,
            )
        )
        OcrPageRepository(session).create(
            make_ocr_page(
                page_id=ocr_page_id,
                artifact_id=artifact_id,
                page_number=page_number,
                profile_sha=profile.profile_sha256,
                page_input=page_input,
                source_sha=page_source,
                raw_text=RAW_TEXT,
            )
        )
        entries.append(
            EvidenceProcessingRevisionPage(
                entry_id=f"{prefix}-entry-{page_number}",
                position=page_number,
                source_document_version_id=doc_id,
                page_number=page_number,
                original_frame=None,
                page_artifact_id=artifact_id,
                ocr_page_id=ocr_page_id,
                status=PageArtifactStatus.SUCCEEDED,
            )
        )
    base_revision_id = f"{prefix}-base"
    manifest_sha = evidence_processing_manifest_hash(entries=[
        (doc_id, 1, None, f"{prefix}-pa-1", f"{prefix}-op-1", "succeeded"),
        (doc_id, 2, None, f"{prefix}-pa-2", f"{prefix}-op-2", "succeeded"),
    ])
    EvidenceProcessingRevisionRepository(session).create(
        EvidenceProcessingRevision(
            evidence_processing_revision_id=base_revision_id,
            evidence_snapshot_id=snapshot_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            manifest=entries,
            manifest_sha256=manifest_sha,
            created_at=NOW,
            created_by="tester",
        )
    )
    locator_repo = EvidenceLocatorRepository(session)
    locator_ids = []
    for seq, (start, end, excerpt) in enumerate(
        ((0, 5, "ALT 5"), (17, 22, "AST 3")), start=1
    ):
        locator_id = f"{prefix}-locator-{seq}"
        locator_ids.append(locator_id)
        locator_repo.create(
            EvidenceLocatorArtifact(
                locator_id=locator_id,
                page_artifact_id=f"{prefix}-pa-1",
                ocr_page_id=f"{prefix}-op-1",
                source_document_version_id=doc_id,
                page_number=1,
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=_sha(RAW_TEXT),
                target_id=f"{prefix}-target-{seq}",
                precision=LocatorPrecision.TEXT_RANGE,
                text_start=start,
                text_end=end,
                excerpt=excerpt,
                disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
                locator_algorithm_version="v1",
                authenticity=LocatorAuthenticity.DEGRADED,
                degradation_reason="仅有文本范围",
                created_at=NOW,
            )
        )
    metadata_id = f"{prefix}-metadata"
    SourceDocumentMetadataRevisionRepository(session).append(
        SourceDocumentMetadataRevision(
            metadata_revision_id=metadata_id,
            source_document_version_id=doc_id,
            document_type="检验报告",
            source_party="研究者所在机构",
            reason="测试资料类型已确认",
            is_auto_suggestion=False,
            revision=1,
            created_at=NOW,
            created_by="tester",
        )
    )
    scan_ids = []
    for page_number in (1, 2):
        scan_id = f"{prefix}-scan-{page_number}"
        scan_ids.append(scan_id)
        OCRRiskScanRepository(session).get_or_create(
            OCRRiskScan(
                scan_id=scan_id,
                ocr_page_id=f"{prefix}-op-{page_number}",
                raw_text_sha256=_sha(RAW_TEXT),
                scanner_rule_version=f"{prefix}/v1",
                flags=[],
                flags_sha256=canonical_hash([]),
                coverage_status="complete",
                created_at=NOW,
            )
        )
    producer_id = f"{prefix}-processing-candidate"
    selected_locator_ids = sorted(locator_ids)
    attempt_manifest = ProcessingCandidateAttemptManifest(
        metadata_revision_ids=[metadata_id],
        risk_scan_ids=sorted(scan_ids),
        locator_ids=selected_locator_ids,
    )
    producer_input_sha = processing_candidate_input_hash(
        evidence_snapshot_id=snapshot_id,
        base_processing_revision_id=base_revision_id,
        expected_revision=fixture.review_episode.revision,
        scanner_rule_version=f"{prefix}/v1",
        selected_locator_ids=selected_locator_ids,
        attempt_manifest=attempt_manifest,
    )
    EvidenceProcessingCandidateRepository(session).create(
        EvidenceProcessingCandidate(
            candidate_id=producer_id,
            evidence_snapshot_id=snapshot_id,
            base_processing_revision_id=base_revision_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            expected_revision=fixture.review_episode.revision,
            idempotency_key=f"{prefix}-processing-key",
            scanner_rule_version=f"{prefix}/v1",
            selected_locator_ids=selected_locator_ids,
            attempt_manifest=attempt_manifest,
            candidate_input_sha256=producer_input_sha,
            status=EvidenceProcessingCandidateStatus.STAGED,
            created_by="tester",
            created_at=NOW,
        ),
        EvidenceProcessingCandidateEvent(
            candidate_id=producer_id,
            seq=1,
            from_status="staged",
            to_status="processing",
            event_kind="worker_start",
            actor="tester",
            reason="构建两页测试完整处理修订",
            attempt_manifest=attempt_manifest,
            attempt_input_sha256=producer_input_sha,
            created_at=NOW,
        ),
    )
    complete_repo = CompleteEvidenceProcessingRevisionRepository(session)
    complete = CompleteEvidenceProcessingRevision(
        evidence_processing_revision_id=f"{prefix}-complete",
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        base_processing_revision_id=base_revision_id,
        producer_candidate_id=producer_id,
        candidate_input_sha256=producer_input_sha,
        manifest=entries,
        manifest_sha256=manifest_sha,
        locator_ids=selected_locator_ids,
        risk_scan_ids=sorted(scan_ids),
        metadata_revision_ids=[metadata_id],
        completion_manifest_sha256="0" * 64,
        created_at=NOW,
        created_by="tester",
    )
    complete = complete.model_copy(
        update={"completion_manifest_sha256": complete_repo.manifest_sha256_for(complete)}
    )
    complete_repo.create(complete)
    _update_episode(
        session,
        session.get(ReviewEpisodeRecord, episode_id),
        active_evidence_snapshot_id=snapshot_id,
        active_evidence_processing_revision_id=complete.evidence_processing_revision_id,
    )
    return {
        "authority": FactAuthority(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=episode_id,
            episode_revision=fixture.review_episode.revision,
            protocol_version_id=protocol_version_id,
            rule_set_id=rule_set_id,
            rule_set_revision=1,
            evidence_snapshot_v2_id=snapshot_id,
            complete_processing_revision_id=complete.evidence_processing_revision_id,
        ),
        "doc_id": doc_id,
        "artifact_ids": [f"{prefix}-pa-1", f"{prefix}-pa-2"],
        "complete_revision_id": complete.evidence_processing_revision_id,
        "rule_set_id": rule_set_id,
    }


# --------------------------------------------------------------------------- 纯函数边界


def _entry(status=PageArtifactStatus.SUCCEEDED, *, doc="doc-1", page=1,
           artifact_id="pa-1") -> EvidenceProcessingRevisionPage:
    return EvidenceProcessingRevisionPage(
        entry_id="e1",
        position=1,
        source_document_version_id=doc,
        page_number=page,
        original_frame=None,
        page_artifact_id=artifact_id,
        ocr_page_id=None if status == PageArtifactStatus.FAILED else "op-1",
        status=status,
        failure_reason=(
            "识别降级" if status == PageArtifactStatus.DEGRADED
            else ("读取失败" if status == PageArtifactStatus.FAILED else None)
        ),
    )


def _artifact(**overrides) -> PageArtifact:
    fields = dict(
        page_artifact_id="pa-1",
        source_document_version_id="doc-1",
        page_number=1,
        original_frame=None,
        source_sha256=_sha("src"),
        page_input_sha256=_sha("page-input"),
        page_image_sha256=_sha("page-image"),
        native_text_sha256=None,
        native_coordinates_sha256=None,
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        renderer_version="renderer-1",
        decoder_version="decoder-1",
        derivative_sha256=_sha("derivative"),
        coordinate_transform_version="transform-1",
        status=PageArtifactStatus.SUCCEEDED,
        failure_reason=None,
    )
    fields.update(overrides)
    return PageArtifact(**fields)


def test_page_identity_binds_entry_and_artifact_exactly():
    identity = scope_page_identity(_entry(), _artifact())
    assert identity.source_document_version_id == "doc-1"
    assert identity.page_artifact_id == "pa-1"
    assert identity.page_number == 1
    assert identity.page_image_sha256 == _sha("page-image")


def test_missing_page_image_is_bounded_error_without_fabrication():
    failed_artifact = _artifact(
        status=PageArtifactStatus.FAILED,
        failure_reason="整页渲染失败",
        page_input_sha256=None,
        page_image_sha256=None,
        page_width=None,
        page_height=None,
        rotation=None,
    )
    with pytest.raises(JudgmentSearchSourceError, match="页图哈希"):
        scope_page_identity(_entry(), failed_artifact)


def test_foreign_artifact_identity_is_bounded_error():
    # 查找键及来源归属都必须与冻结清单相同。
    for overrides in (
        {"page_artifact_id": "pa-other"},
        {"source_document_version_id": "doc-other"},
        {"page_number": 2},
    ):
        with pytest.raises(JudgmentSearchSourceError, match="不一致"):
            scope_page_identity(_entry(), _artifact(**overrides))


def test_entry_status_is_never_a_filter():
    """范围不按页状态过滤：降级/失败清单条目只要页产物身份与页图齐备就纳入。"""
    for status in (
        PageArtifactStatus.DEGRADED,
        PageArtifactStatus.FAILED,
    ):
        identity = scope_page_identity(_entry(status=status), _artifact())
        assert identity.page_artifact_id == "pa-1"


# --------------------------------------------------------------------------- 真实仓储


def _prepare(session, prefix: str) -> dict:
    chain = seed_valid_fact_chain(session, prefix=prefix, create_run=False)
    templates = _seed_templates(session, chain)
    assert _REQUIREMENT in templates
    session.commit()
    return chain


def test_build_scope_complete_authoritative_and_stable_hash(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-stable")
        listed = list_expectation_templates(
            session, chain["rule_set_id"], chain["authority"].rule_set_revision
        )
        assert len([t for t in listed if t.requirement_id == _REQUIREMENT]) == 1
        scope = build_judgment_search_scope(session, chain["authority"], _REQUIREMENT)
    assert scope.authority == chain["authority"]
    assert scope.requirement_id == _REQUIREMENT
    assert len(scope.pages) == 1
    page = scope.pages[0]
    with session_factory() as session:
        artifact = PageArtifactRepository(session).get(chain["page_artifact_id"])
    assert page.source_document_version_id == chain["doc_id"]
    assert page.page_artifact_id == chain["page_artifact_id"]
    assert page.page_number == 1
    assert page.page_image_sha256 == artifact.page_image_sha256
    assert scope.scope_sha256 == judgment_search_scope_sha256(
        authority=scope.authority,
        requirement_id=scope.requirement_id,
        pages=scope.pages,
    )
    with session_factory() as session:
        rebuilt = build_judgment_search_scope(
            session, chain["authority"], _REQUIREMENT
        )
    assert rebuilt == scope
    assert rebuilt.scope_sha256 == scope.scope_sha256


def test_build_scope_is_read_only_and_mutates_nothing(session_factory):
    from app.services.judgment_search_source import build_judgment_search_scope as build

    with session_factory() as session:
        chain = _prepare(session, "jss-readonly")

        def fingerprint() -> str:
            from sqlalchemy import inspect

            digest = hashlib.sha256()
            for table in sorted(inspect(session.get_bind()).get_table_names()):
                rows = session.execute(text(f"SELECT * FROM {table}")).fetchall()
                digest.update(table.encode("utf-8"))
                for row_repr in sorted(repr(row) for row in rows):
                    digest.update(row_repr.encode("utf-8"))
            return digest.hexdigest()

        before = fingerprint()
        build(session, chain["authority"], _REQUIREMENT)
        session.flush()
        assert fingerprint() == before
        assert len(session.new) == 0
        assert len(session.dirty) == 0


def test_scope_validates_complete_revision_once_per_call(session_factory, monkeypatch):
    from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
    from app.storage.fact_authority import FactAuthorityValidator

    original = CompleteEvidenceProcessingRevisionRepository.get
    calls = []

    def counted_get(repository, revision_id):
        calls.append(revision_id)
        return original(repository, revision_id)

    with session_factory() as session:
        chain = _prepare(session, "jss-once")
        monkeypatch.setattr(CompleteEvidenceProcessingRevisionRepository, "get", counted_get)
        scope = build_judgment_search_scope(session, chain["authority"], _REQUIREMENT)
        assert calls == [chain["authority"].complete_processing_revision_id]
        assert build_judgment_search_scope(session, chain["authority"], _REQUIREMENT) == scope
        assert len(calls) == 2
        # Existing callers retain their None return contract; validation is not cached.
        assert FactAuthorityValidator(session).validate(chain["authority"]) is None
        assert len(calls) == 3
        stale = chain["authority"].model_copy(update={"episode_revision": 999})
        with pytest.raises(JudgmentSearchSourceError):
            build_judgment_search_scope(session, stale, _REQUIREMENT)
        assert len(calls) == 3


def test_stale_authority_pointers_are_rejected(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-stale")
        authority = chain["authority"]
        stale_revision = authority.model_copy(update={
            "complete_processing_revision_id": chain["base_revision_id"],
        })
        with pytest.raises(JudgmentSearchSourceError, match="活动指针"):
            build_judgment_search_scope(session, stale_revision, _REQUIREMENT)
        stale_snapshot = authority.model_copy(update={
            "evidence_snapshot_v2_id": "snap-not-active",
        })
        with pytest.raises(JudgmentSearchSourceError, match="活动指针"):
            build_judgment_search_scope(session, stale_snapshot, _REQUIREMENT)
        foreign_scope = authority.model_copy(update={"rule_set_id": "ruleset-other"})
        with pytest.raises(JudgmentSearchSourceError, match="作用域"):
            build_judgment_search_scope(session, foreign_scope, _REQUIREMENT)
        stale_episode = authority.model_copy(update={
            "episode_revision": authority.episode_revision + 1,
        })
        with pytest.raises(JudgmentSearchSourceError, match="修订号"):
            build_judgment_search_scope(session, stale_episode, _REQUIREMENT)


def test_missing_or_foreign_requirement_is_rejected(session_factory):
    from tests.v2.storage.test_fact_rule_link_repository import _seed_rule_set_revision2

    with session_factory() as session:
        chain = _prepare(session, "jss-req")
        with pytest.raises(JudgmentSearchSourceError, match="命中 0 条"):
            build_judgment_search_scope(session, chain["authority"], "req-nope")
        with pytest.raises(JudgmentSearchSourceError, match="空白"):
            build_judgment_search_scope(session, chain["authority"], "   ")
        # 外来 requirement：只存在于同一规则集的 revision 2，不在权威 revision 1。
        _seed_rule_set_revision2(session, chain)
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="命中 0 条"):
            build_judgment_search_scope(session, chain["authority"], "req-v2")


def test_multipage_scope_includes_all_manifest_pages(session_factory):
    with session_factory() as session:
        chain = _seed_two_page_chain(session, "jss-multi")
        _seed_templates(session, chain)
        session.commit()
        scope = build_judgment_search_scope(session, chain["authority"], _REQUIREMENT)
    assert [page.page_number for page in scope.pages] == [1, 2]
    assert [page.page_artifact_id for page in scope.pages] == chain["artifact_ids"]
    assert scope.scope_sha256 == judgment_search_scope_sha256(
        authority=scope.authority,
        requirement_id=scope.requirement_id,
        pages=scope.pages,
    )


def test_artifact_tampering_is_bounded_error_without_silent_omission(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-tamper")
        row = session.get(PageArtifactRecord, chain["page_artifact_id"])
        contract = decode_contract(
            PageArtifact, row.payload_json, row.payload_sha256
        ).model_copy(update={"page_number": 7})
        row.payload_json, row.payload_sha256 = encode_contract(contract)
        row.page_number = 7
        session.flush()
        with pytest.raises(JudgmentSearchSourceError) as error:
            build_judgment_search_scope(session, chain["authority"], _REQUIREMENT)
        assert isinstance(error.value.__cause__.__cause__, RevisionClosureError)


# --------------------------------------------------------------------------- 目标准备


def _seed_procedure_requirement_with_template(session, chain: dict) -> None:
    """行级合成一条流程必做项目目录来源 requirement 及其模板（模拟已发布链形态）。

    既有已验证投影边界只覆盖夹具 stage due 清单内的 requirement；这里按发布链
    同款行结构（``_save_requirement_row`` / 模板投影公式）落库，使 prepare 走到
    流程必做分支，显式验证不支持边界。绝不虚构父组件。
    """
    from tests.v2.storage.test_repositories_roundtrip import FIXTURES

    fixture = FIXTURES[0]
    rule_set_id = chain["rule_set_id"]
    rule_set = get_rule_set(session, rule_set_id, 1)
    revision = 1
    namespaced_stage = f"{rule_set_id}:{revision}:stage-screening"
    requirement = EvidenceRequirement(
        requirement_id="req-proc-x",
        rule_component_id=None,
        procedure_catalog_item_id="catalog-req-proc-x",
        fact_type="vital_sign",
        due_stage=ReviewStage.SCREENING,
        description="流程必做项目测试要求：血压测量记录",
    )
    requirement_json, requirement_sha = encode_contract(requirement)
    from app.storage.models import EvidenceRequirementRecord

    session.add(EvidenceRequirementRecord(
        rule_set_id=rule_set_id,
        rule_set_revision=revision,
        requirement_id=requirement.requirement_id,
        rule_component_id=None,
        procedure_catalog_item_id=requirement.procedure_catalog_item_id,
        fact_type=requirement.fact_type,
        due_stage=requirement.due_stage.value,
        payload_json=requirement_json,
        payload_sha256=requirement_sha,
        created_at=NOW,
    ))
    session.flush()
    projection = {
        "projection": "evidence_expectation_template/v1",
        "rule_set_id": rule_set_id,
        "rule_set_revision": revision,
        "requirement_id": requirement.requirement_id,
        "due_stage": requirement.due_stage.value,
        "study_phase": rule_set.study_phase.value,
        "workflow_stage_id": namespaced_stage,
        "fact_type": requirement.fact_type,
        "required_source_types": sorted(set(requirement.required_source_types)),
        "requires_contemporaneous_objective_source":
            requirement.requires_contemporaneous_objective_source,
        "allows_screening_record_transcription":
            requirement.allows_screening_record_transcription,
        "description": requirement.description,
    }
    template = EvidenceExpectationTemplate(
        template_id="expectation-template:" + canonical_hash({
            "rule_set_id": rule_set_id,
            "rule_set_revision": revision,
            "requirement_id": requirement.requirement_id,
        })[:32],
        rule_set_id=rule_set_id,
        rule_set_revision=revision,
        requirement_id=requirement.requirement_id,
        due_stage=ReviewStage.SCREENING,
        study_phase=rule_set.study_phase,
        workflow_stage_id=namespaced_stage,
        fact_type=requirement.fact_type,
        required_source_types=[],
        requires_contemporaneous_objective_source=False,
        allows_screening_record_transcription=True,
        description=requirement.description,
        projection_sha256=canonical_hash(projection),
        created_at=NOW,
    )
    template_json, template_sha = encode_contract(template)
    template_payload = json.loads(template_json)
    session.add(EvidenceExpectationTemplateRecord(
        template_id=template.template_id,
        rule_set_id=template.rule_set_id,
        rule_set_revision=template.rule_set_revision,
        requirement_id=template.requirement_id,
        due_stage=template.due_stage.value,
        study_phase=template.study_phase.value,
        workflow_stage_id=template.workflow_stage_id,
        fact_type=template.fact_type,
        required_source_types=template.required_source_types,
        projection_sha256=template.projection_sha256,
        created_at=NOW,
        payload_json=template_json,
        payload_sha256=template_sha,
    ))
    session.flush()


def test_prepare_target_includes_published_parent_source_and_child_context(
    session_factory,
):
    with session_factory() as session:
        chain = _prepare(session, "jss-target")
        scope, target_text = prepare_judgment_search_target(
            session, chain["authority"], _REQUIREMENT
        )
        requirement = get_evidence_requirement(
            session, chain["rule_set_id"], 1, _REQUIREMENT
        )
        assert scope.scope_sha256 == build_judgment_search_scope(
            session, chain["authority"], _REQUIREMENT
        ).scope_sha256
    payload = json.loads(target_text)
    assert payload["identity"] == "judgment_search_target/v1"
    assert payload["rule_set"] == {
        "rule_set_id": chain["rule_set_id"],
        "revision": 1,
        "protocol_version_id": chain["authority"].protocol_version_id,
        "study_phase": "phase_iii",
    }
    assert payload["requirement"] == requirement.model_dump(mode="json")
    with session_factory() as session:
        component = get_rule_component(session, chain["rule_set_id"], 1, "component-ex-02")
        rule = get_rule(session, chain["rule_set_id"], 1, "rule-ex-02")
        templates = list_expectation_templates(session, chain["rule_set_id"], 1)
    rule_payload = payload["rule"]
    assert rule_payload["rule_id"] == "rule-ex-02"
    assert rule_payload["official_code"] == "EX-02"
    assert rule_payload["source_text"] == rule.source_text
    component_payload = payload["component"]
    assert component_payload["rule_component_id"] == "component-ex-02"
    assert component_payload["parent_rule_id"] == "rule-ex-02"
    assert component_payload["title"] == component.title
    assert component_payload["expression"] == component.expression.model_dump(mode="json")
    template_payload = payload["template"]
    expected_template = next(
        t for t in templates if t.requirement_id == _REQUIREMENT
    )
    assert template_payload["template_id"] == expected_template.template_id
    assert template_payload["projection_sha256"] == expected_template.projection_sha256
    assert template_payload["workflow_stage_id"] == expected_template.workflow_stage_id
    # 目标文本随实际内容确定性变化：同库重取逐字相同。
    with session_factory() as session:
        _repeat_scope, repeat_text = prepare_judgment_search_target(
            session, chain["authority"], _REQUIREMENT
        )
    assert repeat_text == target_text
    assert _repeat_scope == scope


def test_prepare_target_differs_for_different_published_requirement(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target2")
        _, professional_text = prepare_judgment_search_target(
            session, chain["authority"], _REQUIREMENT
        )
        _, age_text = prepare_judgment_search_target(
            session, chain["authority"], "req-age"
        )
    assert professional_text != age_text
    assert json.loads(professional_text)["rule"]["source_text"] not in age_text


def test_prepare_target_excludes_whole_rule_set(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target3")
        _, target_text = prepare_judgment_search_target(
            session, chain["authority"], _REQUIREMENT
        )
    payload = json.loads(target_text)
    assert "rules" not in payload and "clause_pack" not in payload
    with session_factory() as session:
        other_rule = get_rule(session, chain["rule_set_id"], 1, "rule-in-01")
    assert other_rule.source_text not in target_text
    assert len(payload["rule"]) == 5


def test_prepare_rejects_template_requirement_mismatch(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target4")
        listed = list_expectation_templates(session, chain["rule_set_id"], 1)
        template = next(t for t in listed if t.requirement_id == _REQUIREMENT)
        from app.storage.models import EvidenceExpectationTemplateRecord as Record

        row = session.get(Record, template.template_id)
        # 模板合同对投影哈希自校验：构造"自洽但与已发布 requirement 语义分歧"的
        # 现实反例需按投影公式同步重算哈希。
        tampered = template.model_copy(update={"fact_type": "other_fact_type"})
        tampered = tampered.model_copy(update={"projection_sha256": canonical_hash({
            "projection": "evidence_expectation_template/v1",
            "rule_set_id": tampered.rule_set_id,
            "rule_set_revision": tampered.rule_set_revision,
            "requirement_id": tampered.requirement_id,
            "due_stage": tampered.due_stage.value,
            "study_phase": tampered.study_phase.value,
            "workflow_stage_id": tampered.workflow_stage_id,
            "fact_type": "other_fact_type",
            "required_source_types": sorted(set(tampered.required_source_types)),
            "requires_contemporaneous_objective_source":
                tampered.requires_contemporaneous_objective_source,
            "allows_screening_record_transcription":
                tampered.allows_screening_record_transcription,
            "description": tampered.description,
        })})
        row.payload_json, row.payload_sha256 = encode_contract(tampered)
        row.fact_type = "other_fact_type"
        row.projection_sha256 = tampered.projection_sha256
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="不一致"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_different_source_validity_window(session_factory):
    from app.domain.contracts.rules import TimeQuantity, TimeUnit
    from app.projections.evidence_expectation_templates import template_projection_sha256
    from app.storage.models import EvidenceExpectationTemplateRecord

    with session_factory() as session:
        chain = _prepare(session, "jss-window-drift")
        template = next(t for t in list_expectation_templates(
            session, chain["rule_set_id"], 1
        ) if t.requirement_id == _REQUIREMENT)
        changed = template.model_copy(update={
            "source_validity_window": TimeQuantity(value=7, unit=TimeUnit.DAY),
        })
        fields = changed.model_dump()
        fields["revision"] = fields.pop("rule_set_revision")
        for key in ("schema_version", "template_id", "projection_sha256", "created_at"):
            fields.pop(key, None)
        # Pass typed fields to the same hash helper used by the product projection.
        fields["due_stage"] = changed.due_stage
        fields["study_phase"] = changed.study_phase
        fields["source_validity_window"] = changed.source_validity_window
        changed = changed.model_copy(update={"projection_sha256": template_projection_sha256(**fields)})
        row = session.get(EvidenceExpectationTemplateRecord, template.template_id)
        row.payload_json, row.payload_sha256 = encode_contract(changed)
        row.projection_sha256 = changed.projection_sha256
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="不一致"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_unknown_requirement_and_stale_authority(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target5")
        stale = chain["authority"].model_copy(update={
            "complete_processing_revision_id": chain["base_revision_id"],
        })
        with pytest.raises(JudgmentSearchSourceError, match="作用域、活动指针或修订号"):
            prepare_judgment_search_target(session, stale, _REQUIREMENT)
        with pytest.raises(JudgmentSearchSourceError, match="命中 0 条"):
            prepare_judgment_search_target(session, chain["authority"], "req-nope")


def test_prepare_procedure_requirement_boundary_is_explicit(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target6")
        _seed_procedure_requirement_with_template(session, chain)
        session.flush()
        with pytest.raises(JudgmentSearchSourceError) as error:
            prepare_judgment_search_target(session, chain["authority"], "req-proc-x")
    message = str(error.value)
    assert "流程必做项目目录来源" in message
    assert "catalog-req-proc-x" in message
    assert "尚不支持" in message


def test_prepare_target_is_read_only(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-target7")

        def fingerprint() -> str:
            from sqlalchemy import inspect

            digest = hashlib.sha256()
            for table in sorted(inspect(session.get_bind()).get_table_names()):
                rows = session.execute(text(f"SELECT * FROM {table}")).fetchall()
                digest.update(table.encode("utf-8"))
                for row_repr in sorted(repr(row) for row in rows):
                    digest.update(row_repr.encode("utf-8"))
            return digest.hexdigest()

        before = fingerprint()
        prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)
        session.flush()
        assert fingerprint() == before
        assert len(session.new) == 0
        assert len(session.dirty) == 0


def _tamper_template(session, template, **changes) -> None:
    """把模板行改写为"自洽但语义漂移"的反例：投影哈希按公式重算 + 镜像列同步。

    绝不只是破坏校验和——合同与镜像必须全部通过，漂移只能被语义核对发现。
    """
    tampered = template.model_copy(update=changes)
    tampered = tampered.model_copy(update={"projection_sha256": canonical_hash({
        "projection": "evidence_expectation_template/v1",
        "rule_set_id": tampered.rule_set_id,
        "rule_set_revision": tampered.rule_set_revision,
        "requirement_id": tampered.requirement_id,
        "due_stage": tampered.due_stage.value,
        "study_phase": tampered.study_phase.value,
        "workflow_stage_id": tampered.workflow_stage_id,
        "fact_type": tampered.fact_type,
        "required_source_types": sorted(set(tampered.required_source_types)),
        "requires_contemporaneous_objective_source":
            tampered.requires_contemporaneous_objective_source,
        "allows_screening_record_transcription":
            tampered.allows_screening_record_transcription,
        "description": tampered.description,
    })})
    row = session.get(EvidenceExpectationTemplateRecord, template.template_id)
    row.payload_json, row.payload_sha256 = encode_contract(tampered)
    row.rule_set_id = tampered.rule_set_id
    row.rule_set_revision = tampered.rule_set_revision
    row.requirement_id = tampered.requirement_id
    row.due_stage = tampered.due_stage.value
    row.study_phase = tampered.study_phase.value
    row.workflow_stage_id = tampered.workflow_stage_id
    row.fact_type = tampered.fact_type
    row.required_source_types = tampered.required_source_types
    row.projection_sha256 = tampered.projection_sha256


def _target_template(session, chain: dict):
    listed = list_expectation_templates(session, chain["rule_set_id"], 1)
    return next(t for t in listed if t.requirement_id == _REQUIREMENT)


def test_prepare_rejects_template_description_drift(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-drift-desc")
        _tamper_template(
            session, _target_template(session, chain),
            description="语义漂移后的描述文本：研究者判断相关要求",
        )
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="语义不一致"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_template_source_types_drift(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-drift-src")
        _tamper_template(
            session, _target_template(session, chain),
            required_source_types=["随访记录"],
        )
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="语义不一致"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_template_flag_drift(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-drift-flag")
        _tamper_template(
            session, _target_template(session, chain),
            requires_contemporaneous_objective_source=True,
        )
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="语义不一致"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_template_wrong_due_stage_node(session_factory):
    with session_factory() as session:
        chain = _prepare(session, "jss-drift-stage")
        namespaced_baseline = f"{chain['rule_set_id']}:1:stage-baseline"
        _tamper_template(
            session, _target_template(session, chain),
            workflow_stage_id=namespaced_baseline,
        )
        session.flush()
        # 节点真实存在、命名空间与方案版本/期别均正确，但 baseline 不是到期阶段，
        # requirement 也不在其 due 清单：必须按写边界同语义拒绝。
        with pytest.raises(JudgmentSearchSourceError, match="按期到期"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_ruleset_rule_payload_drift(session_factory):
    from app.storage.models import RuleSetRecord

    with session_factory() as session:
        chain = _prepare(session, "jss-drift-ruleset")
        rule_set = get_rule_set(session, chain["rule_set_id"], 1)
        drifted_rules = [
            rule.model_copy(update={"source_text": rule.source_text + "（漂移）"})
            if rule.rule_id == "rule-ex-02" else rule
            for rule in rule_set.rules
        ]
        drifted = rule_set.model_copy(update={"rules": drifted_rules})
        row = session.get(RuleSetRecord, (chain["rule_set_id"], 1))
        row.payload_json, row.payload_sha256 = encode_contract(drifted)
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="载荷漂移"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)


def test_prepare_rejects_requirement_payload_drift_inside_component(session_factory):
    from app.storage.models import RuleComponentRecord

    with session_factory() as session:
        chain = _prepare(session, "jss-drift-req")
        component = get_rule_component(session, chain["rule_set_id"], 1, "component-ex-02")
        drifted_requirements = [
            requirement.model_copy(
                update={"description": requirement.description + "（漂移）"}
            )
            if requirement.requirement_id == _REQUIREMENT else requirement
            for requirement in component.evidence_requirements
        ]
        drifted = component.model_copy(
            update={"evidence_requirements": drifted_requirements}
        )
        row = session.get(
            RuleComponentRecord, (chain["rule_set_id"], 1, "component-ex-02")
        )
        row.payload_json, row.payload_sha256 = encode_contract(drifted)
        session.flush()
        with pytest.raises(JudgmentSearchSourceError, match="载荷漂移"):
            prepare_judgment_search_target(session, chain["authority"], _REQUIREMENT)
