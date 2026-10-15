"""Slice 4.4 领域合同确定性测试（WP-44A，纯校验，无存储）。

覆盖：ReviewEpisode 成对活动指针收敛；base/complete 修订辨别与解码；occurrence-aware
定位旁路工件真实性门禁；风险扫描集合哈希；校对覆盖层二次确认与范围校验；被提及资料
两层不可变修订；激活事件；处理候选状态机；完整处理修订闭包清单哈希。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import (
    ActivationEventKind,
    DisambiguationOutcome,
    EvidenceProcessingCandidateStatus,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    ProcessingCandidateEventKind,
    ProcessingRevisionStatus,
    ReferencedDocumentStatus,
)
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.evidence_ingestion import ReviewEpisode as IngestionEpisode
from app.domain.contracts.evidence_locator import (
    BLOCKING_CORRECTION_KINDS,
    CANDIDATE_TRANSITIONS,
    CompleteEvidenceProcessingRevision,
    CorrectionRecord,
    EvidenceActivationEvent,
    EvidenceLocatorArtifact,
    EvidenceProcessingCandidate,
    EvidenceProcessingCandidateEvent,
    OCRRiskScan,
    ReferencedDocumentResolutionRevision,
    ReferencedDocumentRevision,
    activation_command_hash,
    completion_manifest_hash,
    locator_anchor_hash,
    processing_candidate_input_hash,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
)
from app.domain.contracts.ocr import CoordinateFrame, OcrRiskFlag
from app.domain.contracts.review import ReviewEpisode as RuntimeEpisode

SHA = "a" * 64
_UTC = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)


def _episode(**overrides):
    base = {
        "review_episode_id": "ep-1",
        "subject_id": "subject-1",
        "project_id": "project-1",
        "rule_set_id": "ruleset-1",
        "study_phase": "phase_iii",
        "stage": "screening",
        "protocol_version_id": "protocol-v1",
        "rule_set_revision": 1,
        "evidence_snapshot_id": "snapshot-legacy",
        "anchor_dates": {},
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------- ReviewEpisode 收敛


def test_review_episode_single_runtime_contract():
    """运行期只有一个 ReviewEpisode 合同：review.py 与 evidence_ingestion 再导出同一对象。"""
    assert RuntimeEpisode is IngestionEpisode


def test_review_episode_legacy_field_retained_and_pointers_nullable():
    ep = RuntimeEpisode(**_episode())
    assert ep.evidence_snapshot_id == "snapshot-legacy"
    assert ep.active_evidence_snapshot_id is None
    assert ep.active_evidence_processing_revision_id is None


def test_review_episode_paired_pointers_required():
    """只设一个活动指针必须被拒绝（成对约束）。"""
    with pytest.raises(ValidationError):
        RuntimeEpisode(**_episode(active_evidence_snapshot_id="snap-1"))
    with pytest.raises(ValidationError):
        RuntimeEpisode(**_episode(active_evidence_processing_revision_id="rev-1"))


def test_review_episode_paired_pointers_ok():
    ep = RuntimeEpisode(
        **_episode(
            active_evidence_snapshot_id="snap-1",
            active_evidence_processing_revision_id="rev-1",
        )
    )
    assert ep.active_evidence_snapshot_id == "snap-1"
    assert ep.active_evidence_processing_revision_id == "rev-1"


def test_review_episode_requires_utc_due_at():
    # 故意构造 naive datetime 验证 UTC 拒绝
    with pytest.raises(ValidationError):
        RuntimeEpisode(**_episode(due_at=datetime(2026, 1, 1)))  # noqa: DTZ001


# ------------------------------------------------------------- base/complete 辨别


def _page(position, page_number, *, ocr_page_id=None, status="succeeded"):
    return EvidenceProcessingRevisionPage(
        entry_id=f"entry-{position}",
        position=position,
        source_document_version_id="doc-1",
        page_number=page_number,
        original_frame=None,
        page_artifact_id=f"pa-{position}",
        ocr_page_id=ocr_page_id,
        status=status,
    )


def _base_revision(**overrides):
    manifest = [_page(1, 1, ocr_page_id="ocr-1")]
    from app.domain.publication import evidence_processing_manifest_hash

    base = {
        "evidence_processing_revision_id": "base-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": "project-1",
        "subject_id": "subject-1",
        "review_episode_id": "ep-1",
        "manifest": manifest,
        "manifest_sha256": evidence_processing_manifest_hash(
            entries=[
                (
                    e.source_document_version_id,
                    e.page_number,
                    e.original_frame,
                    e.page_artifact_id,
                    e.ocr_page_id,
                    e.status.value,
                )
                for e in manifest
            ]
        ),
        "created_at": _UTC,
        "created_by": "tester",
    }
    base.update(overrides)
    return base


def test_base_revision_is_never_activatable():
    """base 修订 is_activatable 恒为 False（Literal[False]），状态必须 READY。"""
    rev = EvidenceProcessingRevision(**_base_revision())
    assert rev.is_activatable is False
    with pytest.raises(ValidationError):
        EvidenceProcessingRevision(**_base_revision(is_activatable=True))
    with pytest.raises(ValidationError):
        EvidenceProcessingRevision(**_base_revision(status="active"))


def _complete_revision(**overrides):
    manifest = [_page(1, 1, ocr_page_id="ocr-1")]
    base = {
        "evidence_processing_revision_id": "complete-1",
        "evidence_snapshot_id": "snap-1",
        "project_id": "project-1",
        "subject_id": "subject-1",
        "review_episode_id": "ep-1",
        "base_processing_revision_id": "base-1",
        "producer_candidate_id": "cand-1",
        "candidate_input_sha256": "c" * 64,
        "manifest": manifest,
        "manifest_sha256": manifest_sha(manifest),
        # 合同只校验 sha256 格式；DB-bound 闭包哈希由仓储重算校验。
        "completion_manifest_sha256": "e" * 64,
        "created_at": _UTC,
        "created_by": "tester",
    }
    base.update(overrides)
    return base


def manifest_sha(manifest):
    from app.domain.publication import evidence_processing_manifest_hash

    return evidence_processing_manifest_hash(entries=page_entries(manifest))


def page_entries(manifest):
    return [
        (
            e.source_document_version_id,
            e.page_number,
            e.original_frame,
            e.page_artifact_id,
            e.ocr_page_id,
            e.status.value,
        )
        for e in manifest
    ]


def test_complete_revision_decodes_and_is_activatable():
    rev = CompleteEvidenceProcessingRevision(**_complete_revision())
    assert rev.revision_kind == "complete"
    assert rev.is_activatable is True
    assert rev.status == ProcessingRevisionStatus.READY


def test_complete_revision_preserves_user_document_order():
    """内部资料编号不决定阅读顺序；完整修订必须逐项继承 base 的用户顺序。"""
    manifest = [
        _page(1, 1, ocr_page_id="ocr-z").model_copy(
            update={"source_document_version_id": "doc-z"}
        ),
        _page(2, 1, ocr_page_id="ocr-a").model_copy(
            update={"source_document_version_id": "doc-a"}
        ),
    ]
    revision = CompleteEvidenceProcessingRevision(
        **_complete_revision(
            manifest=manifest,
            manifest_sha256=manifest_sha(manifest),
        )
    )
    assert [entry.source_document_version_id for entry in revision.manifest] == [
        "doc-z",
        "doc-a",
    ]


def test_complete_revision_rejects_split_document_or_reversed_pages():
    split = [
        _page(1, 1, ocr_page_id="ocr-a1"),
        _page(2, 1, ocr_page_id="ocr-b1").model_copy(
            update={"source_document_version_id": "doc-2"}
        ),
        _page(3, 2, ocr_page_id="ocr-a2"),
    ]
    with pytest.raises(ValidationError, match="连续排列"):
        CompleteEvidenceProcessingRevision(
            **_complete_revision(manifest=split, manifest_sha256=manifest_sha(split))
        )

    reversed_pages = [
        _page(1, 2, ocr_page_id="ocr-2"),
        _page(2, 1, ocr_page_id="ocr-1"),
    ]
    with pytest.raises(ValidationError, match="页码必须升序"):
        CompleteEvidenceProcessingRevision(
            **_complete_revision(
                manifest=reversed_pages,
                manifest_sha256=manifest_sha(reversed_pages),
            )
        )


def test_complete_revision_must_use_complete_kind():
    with pytest.raises(ValidationError):
        CompleteEvidenceProcessingRevision(**_complete_revision(revision_kind="base"))


def test_complete_revision_duplicate_ref_rejected():
    with pytest.raises(ValidationError):
        CompleteEvidenceProcessingRevision(
            **_complete_revision(correction_ids=["corr-1", "corr-1"])
        )


def test_complete_revision_manifest_hash_format_enforced():
    """合同层只校验闭包哈希格式（64 位十六进制）；DB-bound 重算在仓储层校验。"""
    with pytest.raises(ValidationError):
        CompleteEvidenceProcessingRevision(
            **_complete_revision(completion_manifest_sha256="not-a-hash")
        )
    # 重复子引用仍然被合同拒绝。
    with pytest.raises(ValidationError):
        CompleteEvidenceProcessingRevision(
            **_complete_revision(correction_ids=["corr-1", "corr-1"])
        )


def test_completion_manifest_hash_order_sensitive():
    """闭包清单哈希顺序保持：任一有序引用换序/缺行/子 payload 漂移都改变哈希。"""
    sha_a = "a" * 64
    sha_b = "b" * 64

    def _h(locators, base_sha="b" * 64):
        return completion_manifest_hash(
            base_processing_revision_id="base-1",
            base_processing_revision_sha256=base_sha,
            page_entries=[("e1", sha_a)],
            locators=locators,
            risk_scans=[],
            risk_reviews=[],
            corrections=[],
            metadata_revisions=[],
            referenced_documents=[],
            resolutions=[],
        )

    h1 = _h([("loc-1", sha_a), ("loc-2", sha_b)])
    h2 = _h([("loc-2", sha_b), ("loc-1", sha_a)])
    h3 = _h([("loc-1", sha_a)])
    h4 = _h([("loc-1", sha_a)], base_sha=sha_a)  # base payload 漂移
    h5 = _h([("loc-1", sha_b)])  # 子 payload 漂移
    assert h1 != h2 and h1 != h3 and h1 != h4 and h1 != h5
    # 同 id 同 payload 换序之外：相同输入幂等。
    assert _h([("loc-1", sha_a)]) == _h([("loc-1", sha_a)])


# ------------------------------------------------------------- 定位旁路工件


def _locator(**overrides):
    base = {
        "locator_id": "loc-1",
        "page_artifact_id": "pa-1",
        "ocr_page_id": "ocr-1",
        "source_document_version_id": "doc-1",
        "page_number": 1,
        "source_layer": "raw_ocr",
        "source_text_sha256": SHA,
        "target_id": "target-1",
        "precision": "text_range",
        "text_start": 0,
        "text_end": 5,
        "excerpt": "12345",
        "disambiguation": "unique_match",
        "locator_algorithm_version": "v1",
        "authenticity": "degraded",
        "degradation_reason": "text-only 路线无真实坐标",
        "created_at": _UTC,
    }
    base.update(overrides)
    return base


def test_locator_text_range_ok():
    artifact = EvidenceLocatorArtifact(**_locator())
    assert artifact.precision == LocatorPrecision.TEXT_RANGE


def test_locator_bbox_requires_authenticity_and_sidecar():
    """有页尺寸但无同源 sidecar、或未通过真实性门禁的 bbox 必须拒绝。"""
    frame = CoordinateFrame(
        space="pdf_points",
        page_width=595.0,
        page_height=842.0,
        rotation=0,
        transform_version="t/v1",
    )
    bbox = BoundingBox(x0=10, y0=20, x1=100, y1=120)
    bbox_base = {
        "precision": "bbox",
        "bbox": bbox,
        "coordinate_frame": frame,
        "text_start": 0,
        "text_end": 5,
        "excerpt": "12345",
    }
    # authenticity=degraded + bbox → 拒绝
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(**bbox_base, authenticity="degraded")
        )
    # authenticity=authenticated + bbox 但无 sidecar → 拒绝
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                **bbox_base,
                authenticity="authenticated",
                sidecar_sha256=None,
            )
        )
    # bbox 缺少具体原始字符范围 → 拒绝（occurrence 身份必须绑定范围）
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                precision="bbox",
                bbox=bbox,
                coordinate_frame=frame,
                text_start=None,
                text_end=None,
                excerpt=None,
                authenticity="authenticated",
                sidecar_sha256=SHA,
            )
        )
    # 通过：authenticated + bbox + sidecar + unique_match + 范围
    ok = EvidenceLocatorArtifact(
        **_locator(**bbox_base, authenticity="authenticated", sidecar_sha256=SHA)
    )
    assert ok.authenticity == LocatorAuthenticity.AUTHENTICATED


def test_locator_bbox_must_stay_inside_page():
    frame = CoordinateFrame(
        space="pdf_points", page_width=595.0, page_height=842.0, rotation=0,
        transform_version="t/v1",
    )
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                precision="bbox",
                bbox=BoundingBox(x0=0, y0=0, x1=700, y1=100),
                coordinate_frame=frame,
                authenticity="authenticated",
                sidecar_sha256=SHA,
                text_start=0,
                text_end=5,
                excerpt="12345",
            )
        )


def test_locator_page_only_requires_reason_and_no_excerpt():
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(**_locator(precision="page_only", excerpt="12345"))
    # 缺少稳定目标身份锚点 → 拒绝
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                precision="page_only",
                excerpt=None,
                text_start=None,
                text_end=None,
                disambiguation="not_found",
                degradation_reason="目标未找到",
            )
        )
    # 完整 page_only：not_found + 稳定目标锚点 + 降级原因。
    ok = EvidenceLocatorArtifact(
        **_locator(
            precision="page_only",
            excerpt=None,
            text_start=None,
            text_end=None,
            disambiguation="not_found",
            anchor_hash=locator_anchor_hash(
                page_artifact_id="pa-1",
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=SHA,
                precision=LocatorPrecision.PAGE_ONLY,
                target_id="target-1",
                excerpt=None,
                disambiguation=DisambiguationOutcome.NOT_FOUND,
                degradation_reason="目标未找到",
            ),
            degradation_reason="目标未找到",
        )
    )
    assert ok.precision == LocatorPrecision.PAGE_ONLY


def test_locator_page_excerpt_requires_anchor_and_not_notfound():
    """page_excerpt 必须携带可回放摘录锚点哈希；NOT_FOUND 不能产生摘录。"""
    no_range = {"text_start": None, "text_end": None}
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                precision="page_excerpt",
                disambiguation="repeated_text_degraded",
                degradation_reason="多处相同文本",
                **no_range,
            )
        )
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                precision="page_excerpt",
                disambiguation="not_found",
                anchor_hash=SHA,
                **no_range,
            )
        )
    ok = EvidenceLocatorArtifact(
        **_locator(
            precision="page_excerpt",
            disambiguation="repeated_text_degraded",
            anchor_hash=locator_anchor_hash(
                page_artifact_id="pa-1",
                source_layer=LocatorSourceLayer.RAW_OCR,
                source_text_sha256=SHA,
                precision=LocatorPrecision.PAGE_EXCERPT,
                target_id="target-1",
                excerpt="12345",
                disambiguation=DisambiguationOutcome.REPEATED_TEXT_DEGRADED,
                degradation_reason="多处相同文本无法稳定消歧",
            ),
            degradation_reason="多处相同文本无法稳定消歧",
            **no_range,
        )
    )
    assert ok.precision == LocatorPrecision.PAGE_EXCERPT


def test_locator_degraded_anchor_cannot_be_self_reported():
    """任意合法格式哈希不能冒充摘录/目标的可回放锚点。"""
    with pytest.raises(ValidationError, match="确定性计算"):
        EvidenceLocatorArtifact(
            **_locator(
                precision="page_excerpt",
                disambiguation="repeated_text_degraded",
                anchor_hash=SHA,
                degradation_reason="多处相同文本",
                text_start=None,
                text_end=None,
            )
        )


def test_locator_effective_text_binds_revision():
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(
                source_layer="effective_text",
                processing_revision_id=None,
                effective_text_sha256=None,
            )
        )
    ok = EvidenceLocatorArtifact(
        **_locator(
            source_layer="effective_text",
            processing_revision_id="rev-1",
            effective_text_sha256=SHA,
        )
    )
    assert ok.source_layer == LocatorSourceLayer.EFFECTIVE_TEXT


def test_locator_disambiguation_required_for_bbox_and_range():
    """重复文本未消歧时不得生成区域/文本范围定位（须降级）。"""
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact(
            **_locator(disambiguation="repeated_text_degraded")
        )


# ------------------------------------------------------------- 风险扫描


def _flag(risk_id="risk-1", **overrides):
    base = {
        "risk_id": risk_id,
        "kind": "numeric_value",
        "level": "blocking",
        "text": "3.5",
        "text_start": 0,
        "text_end": 3,
        "detail": None,
        "rule_version": "rules/v1",
    }
    base.update(overrides)
    return OcrRiskFlag(**base)


def _scan(**overrides):
    flags = [_flag()]
    from app.domain.publication import canonical_hash

    base = {
        "scan_id": "scan-1",
        "ocr_page_id": "ocr-1",
        "raw_text_sha256": SHA,
        "scanner_rule_version": "rules/v1",
        "flags": flags,
        "flags_sha256": canonical_hash(
            [
                {
                    "risk_id": f.risk_id,
                    "kind": f.kind.value,
                    "level": f.level.value,
                    "text": f.text,
                    "text_start": f.text_start,
                    "text_end": f.text_end,
                    "detail": f.detail,
                    "rule_version": f.rule_version,
                }
                for f in sorted(flags, key=lambda f: f.risk_id)
            ]
        ),
        "created_at": _UTC,
    }
    base.update(overrides)
    return base


def test_risk_scan_flags_sha_consistency():
    scan = OCRRiskScan(**_scan())
    assert scan.coverage_status == "complete"
    with pytest.raises(ValidationError):
        OCRRiskScan(**_scan(flags_sha256="b" * 64))


def test_risk_scan_duplicate_risk_id_rejected():
    with pytest.raises(ValidationError):
        OCRRiskScan(**_scan(flags=[_flag("r1"), _flag("r1")]))


def test_risk_scan_idempotent_flags_sha_order_independent():
    """同一风险集合换序应得到相同 flags_sha256（集合内容寻址）。"""
    from app.domain.publication import canonical_hash

    def _sha(flags):
        return canonical_hash(
            [
                {
                    "risk_id": f.risk_id,
                    "kind": f.kind.value,
                    "level": f.level.value,
                    "text": f.text,
                    "text_start": f.text_start,
                    "text_end": f.text_end,
                    "detail": f.detail,
                    "rule_version": f.rule_version,
                }
                for f in sorted(flags, key=lambda f: f.risk_id)
            ]
        )

    flags_a = [_flag("a", text="x", text_start=0, text_end=1),
               _flag("b", text="yy", text_start=1, text_end=3)]
    flags_b = [_flag("b", text="yy", text_start=1, text_end=3),
               _flag("a", text="x", text_start=0, text_end=1)]
    sa = OCRRiskScan(**_scan(flags=flags_a, flags_sha256=_sha(flags_a)))
    sb = OCRRiskScan(**_scan(flags=flags_b, flags_sha256=_sha(flags_b)))
    assert sa.flags_sha256 == sb.flags_sha256


# ------------------------------------------------------------- 校对


def _correction(**overrides):
    base = {
        "correction_id": "corr-1",
        "ocr_page_id": "ocr-1",
        "raw_text_sha256": SHA,
        "text_start": 0,
        "text_end": 3,
        "original_text": "3.5",
        "corrected_text": "3.5",
        "change_kind": "other_text",
        "requires_confirmation": False,
        "base_processing_revision_id": "base-1",
        "reason": "修正",
        "actor": "user",
        "affected_scope": [],
        "created_at": _UTC,
    }
    base.update(overrides)
    return base


def test_correction_requires_real_change():
    with pytest.raises(ValidationError):
        CorrectionRecord(**_correction())


def test_correction_length_must_match_range():
    """原文本长度必须与字符范围一致（防偏移漂移）。"""
    with pytest.raises(ValidationError):
        CorrectionRecord(
            **_correction(
                text_start=0,
                text_end=4,
                corrected_text="35",
                change_kind="numeric",
                requires_confirmation=True,
            )
        )


def test_correction_allows_zero_length_source_anchored_insertion():
    correction = CorrectionRecord(
        **_correction(
            text_start=3,
            text_end=3,
            original_text="",
            corrected_text=" mmol/L",
        )
    )
    assert correction.text_start == correction.text_end == 3
    assert correction.original_text == ""


def test_correction_insertion_requires_empty_original_text():
    with pytest.raises(ValidationError, match="原文必须为空"):
        CorrectionRecord(
            **_correction(
                text_start=3,
                text_end=3,
                original_text="3",
                corrected_text=" mmol/L",
            )
        )


def test_correction_blocking_kinds_require_confirmation():
    for kind in BLOCKING_CORRECTION_KINDS:
        with pytest.raises(ValidationError):
            CorrectionRecord(
                **_correction(
                    corrected_text="3.0",
                    change_kind=kind,
                    requires_confirmation=False,
                )
            )
        ok = CorrectionRecord(
            **_correction(
                corrected_text="3.0",
                change_kind=kind,
                requires_confirmation=True,
            )
        )
        assert ok.requires_confirmation


def test_correction_confirmation_actor_pairing():
    with pytest.raises(ValidationError):
        CorrectionRecord(
            **_correction(
                corrected_text="3.0",
                change_kind="numeric",
                requires_confirmation=True,
                confirmation_actor="user",
                confirmation_at=None,
            )
        )


# ------------------------------------------------------------- 被提及资料


def test_referenced_document_confirmed_requires_trigger():
    with pytest.raises(ValidationError):
        ReferencedDocumentRevision(
            revision_id="rd-1",
            referenced_document_id="doc-ref",
            project_id="project-1",
            subject_id="subject-1",
            review_episode_id="ep-1",
            description="报告",
            origin="manual",
            status="confirmed",
            revision=1,
            created_at=_UTC,
            created_by="user",
        )
    ok = ReferencedDocumentRevision(
        revision_id="rd-1",
        referenced_document_id="doc-ref",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="ep-1",
        description="报告",
        origin="manual",
        status="confirmed",
        trigger_locator_id="loc-1",
        revision=1,
        created_at=_UTC,
        created_by="user",
    )
    assert ok.status == ReferencedDocumentStatus.CONFIRMED


def test_referenced_document_deterministic_only_proposed():
    """确定性生成只能是 proposed；确认必须是带用户复核标记的后续修订。"""
    with pytest.raises(ValidationError):
        ReferencedDocumentRevision(
            revision_id="rd-2",
            referenced_document_id="doc-ref",
            project_id="project-1",
            subject_id="subject-1",
            review_episode_id="ep-1",
            description="报告",
            origin="deterministic_candidate",
            status="confirmed",
            trigger_locator_id="loc-1",
            revision=1,
            created_at=_UTC,
            created_by="user",
        )
    confirmed = ReferencedDocumentRevision(
        revision_id="rd-3",
        referenced_document_id="doc-ref",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="ep-1",
        description="报告",
        origin="deterministic_candidate",
        status="confirmed",
        trigger_locator_id="loc-1",
        user_reviewed=True,
        reason="用户确认原文确有提及",
        revision=2,
        supersedes_revision_id="rd-2",
        created_at=_UTC,
        created_by="user",
    )
    assert confirmed.user_reviewed is True

    with pytest.raises(ValidationError, match="非空操作原因"):
        ReferencedDocumentRevision(
            revision_id="rd-4",
            referenced_document_id="doc-ref",
            project_id="project-1",
            subject_id="subject-1",
            review_episode_id="ep-1",
            description="报告",
            origin="deterministic_candidate",
            status="dismissed",
            user_reviewed=True,
            reason="   ",
            revision=3,
            supersedes_revision_id="rd-3",
            created_at=_UTC,
            created_by="user",
        )


def test_referenced_document_resolution_provided_requires_source():
    with pytest.raises(ValidationError):
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-1",
            referenced_document_id="doc-ref",
            status="provided",
            revision=1,
            created_at=_UTC,
            created_by="user",
        )
    with pytest.raises(ValidationError):
        ReferencedDocumentResolutionRevision(
            resolution_revision_id="res-2",
            referenced_document_id="doc-ref",
            status="unresolved",
            source_document_version_id="doc-1",
            revision=1,
            created_at=_UTC,
            created_by="user",
        )


# ------------------------------------------------------------- 激活事件


def test_activation_event_pairing_and_no_self_switch():
    base = {
        "event_id": "evt-1",
        "review_episode_id": "ep-1",
        "activation_seq": 1,
        "event_kind": "activate",
        "candidate_id": "cand-1",
        "to_snapshot_id": "snap-2",
        "to_revision_id": "rev-2",
        "reason": "发布",
        "actor": "user",
        "expected_revision": 1,
        "resulting_episode_revision": 2,
        "snapshot_status_transitioned": True,
        "created_at": _UTC,
    }
    base["command_sha256"] = activation_command_hash(
        event_kind=ActivationEventKind.ACTIVATE,
        candidate_id="cand-1",
        target_snapshot_id="snap-2",
        target_revision_id="rev-2",
        expected_revision=1,
        actor="user",
        reason="发布",
        job_id=None,
    )
    ok = EvidenceActivationEvent(**base)
    assert ok.event_kind == ActivationEventKind.ACTIVATE
    # 自切换拒绝
    with pytest.raises(ValidationError):
        EvidenceActivationEvent(
            **base, from_snapshot_id="snap-2", from_revision_id="rev-2"
        )
    # 只设一个旧指针拒绝
    with pytest.raises(ValidationError):
        EvidenceActivationEvent(**base, from_snapshot_id="snap-1")


# ------------------------------------------------------------- 处理候选状态机


def _candidate(**overrides):
    base = {
        "candidate_id": "cand-1",
        "evidence_snapshot_id": "snap-1",
        "base_processing_revision_id": "base-1",
        "project_id": "project-1",
        "subject_id": "subject-1",
        "review_episode_id": "ep-1",
        "expected_revision": 1,
        "idempotency_key": "key-1",
        "scanner_rule_version": "slice4.0/v1",
        "selected_locator_ids": [],
        "candidate_input_sha256": SHA,
        "status": "staged",
        "created_by": "user",
        "created_at": _UTC,
    }
    base.update(overrides)
    base["candidate_input_sha256"] = processing_candidate_input_hash(
        evidence_snapshot_id=base["evidence_snapshot_id"],
        base_processing_revision_id=base["base_processing_revision_id"],
        expected_revision=base["expected_revision"],
        scanner_rule_version=base["scanner_rule_version"],
        selected_locator_ids=base["selected_locator_ids"],
    )
    return base


def _event(seq, from_status, event_kind, to_status, **overrides):
    base = {
        "candidate_id": "cand-1",
        "seq": seq,
        "from_status": from_status,
        "to_status": to_status,
        "event_kind": event_kind,
        "actor": "user",
        "reason": "r",
        "created_at": _UTC,
    }
    base.update(overrides)
    return base


def test_candidate_transition_table_matches_design():
    """状态表必须包含设计书 §6 的全部合法转换。"""
    assert (
        CANDIDATE_TRANSITIONS[EvidenceProcessingCandidateStatus.PROCESSING][
            ProcessingCandidateEventKind.BLOCKING_RISK_FOUND
        ]
        == EvidenceProcessingCandidateStatus.NEEDS_ATTENTION
    )
    assert (
        CANDIDATE_TRANSITIONS[EvidenceProcessingCandidateStatus.READY][
            ProcessingCandidateEventKind.ACTIVATE
        ]
        == EvidenceProcessingCandidateStatus.ACTIVE
    )
    assert (
        CANDIDATE_TRANSITIONS[EvidenceProcessingCandidateStatus.READY][
            ProcessingCandidateEventKind.REVISION_MISMATCH
        ]
        == EvidenceProcessingCandidateStatus.REVISION_CONFLICT
    )


def test_candidate_event_valid_transition():
    EvidenceProcessingCandidateEvent(
        **_event(1, "staged", "worker_start", "processing")
    )
    EvidenceProcessingCandidateEvent(
        **_event(
            2,
            "processing",
            "all_gates_passed",
            "ready",
            complete_revision_id="complete-1",
        )
    )
    EvidenceProcessingCandidateEvent(
        **_event(3, "ready", "activate", "active", complete_revision_id="complete-1")
    )


def test_candidate_event_invalid_transition_rejected():
    """未列出的转换一律拒绝（如 ready -> worker_start 回退）。"""
    with pytest.raises(ValidationError):
        EvidenceProcessingCandidateEvent(
            **_event(1, "ready", "worker_start", "processing")
        )


def test_candidate_event_terminal_no_further_transition():
    """终态（active/cancelled/terminal_failure/revision_conflict）无出边。"""
    for terminal in (
        "active",
        "cancelled",
        "terminal_failure",
        "revision_conflict",
    ):
        assert CANDIDATE_TRANSITIONS.get(EvidenceProcessingCandidateStatus(terminal), {}) == {}


def test_candidate_contract_ok():
    EvidenceProcessingCandidate(**_candidate())
