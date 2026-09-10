"""Phase 5 Slice 5.3 Evidence Normalizer 合同聚焦测试。

覆盖输入/输出合同的纯校验集合：不触数据库、不调模型、不生成 Profile。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerContextInput,
    EvidenceNormalizerInput,
    EvidenceNormalizerLocatorInput,
    EvidenceNormalizerOutput,
    EvidenceNormalizerPageInput,
    EvidenceNormalizerUnresolvedItem,
    evidence_normalizer_input_scope_hash,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalEventCandidateV2,
    ClinicalFactCandidateV2,
    FactAuthority,
    MedicationExposureCandidateV2,
)
from app.domain.contracts.enums import (
    DurationStatus,
    FactPolarity,
    LocatorPrecision,
    LocatorSourceLayer,
    ReviewStage,
)
from app.domain.contracts.rules import EvidenceRequirement


UTC = timezone.utc
NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
SHA = "a" * 64


def _authority(**overrides):
    base = dict(
        project_id="p1",
        subject_id="s1",
        review_episode_id="e1",
        episode_revision=1,
        protocol_version_id="pv1",
        rule_set_id="rs1",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snap1",
        complete_processing_revision_id="rev1",
    )
    base.update(overrides)
    return FactAuthority(**base)


def _page(num: int, text: str, locs: list[str]) -> EvidenceNormalizerPageInput:
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return EvidenceNormalizerPageInput(
        source_document_version_id="docv-A",
        page_artifact_id=f"page-{num}",
        ocr_page_id=f"ocr-{num}",
        page_number=num,
        effective_text=text,
        effective_text_sha256=sha,
        locator_ids=sorted(locs),
    )


def _context(**overrides) -> EvidenceNormalizerContextInput:
    base = dict(
        source_document_version_id="docv-A",
        metadata_revision_id="meta-A-1",
        document_type="筛选病历",
        source_party="研究者",
        document_record_time=None,
        current_review_stage=ReviewStage.SCREENING,
        workflow_stage_id="rs1:screening",
    )
    base.update(overrides)
    return EvidenceNormalizerContextInput(**base)


def _locators(
    pages: list[EvidenceNormalizerPageInput], locator_ids: list[str]
) -> list[EvidenceNormalizerLocatorInput]:
    return [
        EvidenceNormalizerLocatorInput(
            locator_id=locator_id,
            page_number=next(
                (page.page_number for page in pages if locator_id in page.locator_ids),
                pages[0].page_number,
            ),
            source_layer=LocatorSourceLayer.EFFECTIVE_TEXT,
            precision=LocatorPrecision.TEXT_RANGE,
            source_text_sha256=next(
                (
                    page.effective_text_sha256
                    for page in pages
                    if locator_id in page.locator_ids
                ),
                pages[0].effective_text_sha256,
            ),
            localized_text=next(
                (page.effective_text for page in pages if locator_id in page.locator_ids),
                pages[0].effective_text,
            ),
        )
        for locator_id in sorted(locator_ids)
    ]


def _requirement(requirement_id: str = "req-1") -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id=requirement_id,
        procedure_catalog_item_id=f"procedure-{requirement_id}",
        fact_type="肝功能检查",
        required_source_types=["检验报告"],
        due_stage=ReviewStage.SCREENING,
        description="筛选期应完成肝功能检查",
    )


def _input(**overrides):
    auth = overrides.pop("authority", _authority())
    pages = overrides.pop("pages", [_page(1, "有效文本", ["loc-1"])])
    page_numbers = overrides.pop("page_numbers", [p.page_number for p in pages])
    avail = overrides.pop("available_locator_ids", sorted({loc for p in pages for loc in p.locator_ids}) or ["loc-1"])
    context = overrides.pop("context", _context())
    requirements = overrides.pop("related_requirements", [])
    base = dict(
        run_id="run-1",
        call_id="call-1",
        authority=auth,
        logical_document_id="doc-A",
        context=context,
        related_requirements=requirements,
        manifest_sha256=SHA,
        completion_manifest_sha256="b" * 64,
        page_numbers=page_numbers,
        pages=pages,
        available_locator_ids=avail,
        available_locators=_locators(pages, avail),
        created_at=NOW,
    )
    # compute hash unless overridden
    if "input_scope_sha256" not in overrides:
        hs = evidence_normalizer_input_scope_hash(
            authority=base["authority"],
            logical_document_id=base["logical_document_id"],
            context=base["context"],
            related_requirements=base["related_requirements"],
            manifest_sha256=base["manifest_sha256"],
            completion_manifest_sha256=base["completion_manifest_sha256"],
            page_numbers=base["page_numbers"],
            pages=base["pages"],
            available_locator_ids=base["available_locator_ids"],
            available_locators=base["available_locators"],
        )
        base["input_scope_sha256"] = hs
    base.update(overrides)
    return EvidenceNormalizerInput(**base)


def _basis(locator_id: str = "loc-1") -> AssertionBasis:
    return AssertionBasis(
        asserted_object="糖尿病病史",
        assertion_text="无糖尿病病史",
        locator_id=locator_id,
        source_text_sha256=SHA,
    )


def _fact_candidate(**overrides):
    base = dict(
        candidate_id="cand-f1",
        run_id="run-1",
        call_id="call-1",
        candidate_kind="fact",
        fact_type="既往史",
        polarity=FactPolarity.NEGATED,
        asserted_object="糖尿病病史",
        raw_value=False,
        canonical_value=False,
        unit="unitless",
        locator_ids=["loc-1"],
        candidate_source_semantics="当前研究病历直接记录",
        assertion_basis=_basis("loc-1"),
        model_uncertainty=0.15,
        created_at=NOW,
    )
    base.update(overrides)
    return ClinicalFactCandidateV2(**base)


def _event_candidate(**overrides):
    base = dict(
        candidate_id="cand-e1",
        run_id="run-1",
        call_id="call-1",
        candidate_kind="event",
        event_type="诊断",
        duration_status=DurationStatus.UNKNOWN,
        fact_candidate_ids=["cand-f1"],
        locator_ids=["loc-1"],
        candidate_source_semantics="同期客观结果",
        model_uncertainty=0.2,
        created_at=NOW,
    )
    base.update(overrides)
    return ClinicalEventCandidateV2(**base)


def _exposure_candidate(**overrides):
    base = dict(
        candidate_id="cand-m1",
        run_id="run-1",
        call_id="call-1",
        candidate_kind="exposure",
        medication_name="阿司匹林",
        duration_status=DurationStatus.UNKNOWN,
        fact_candidate_ids=["cand-f1"],
        locator_ids=["loc-1"],
        candidate_source_semantics="既往原始资料",
        model_uncertainty=0.1,
        created_at=NOW,
    )
    base.update(overrides)
    return MedicationExposureCandidateV2(**base)


def _unresolved(**overrides):
    base = dict(
        code="ambiguous_date",
        message="日期仅有年份，无法确定月日",
        affected_pages=[1],
        affected_locator_ids=[],
        reason="原文仅写 2023 年，未提供月日",
    )
    base.update(overrides)
    return EvidenceNormalizerUnresolvedItem(**base)


# ------------------------------------------------------------- 输入合同

def test_input_ok_single_page():
    inp = _input()
    assert inp.page_numbers == [1]
    assert inp.pages[0].page_number == 1


def test_input_page_hash_must_match_text():
    with pytest.raises(ValidationError, match="哈希与原文不一致"):
        EvidenceNormalizerPageInput(
            source_document_version_id="docv-A",
            page_artifact_id="page-1",
            page_number=1,
            effective_text="有效文本",
            effective_text_sha256="b" * 64,
            locator_ids=["loc-1"],
        )


def test_input_page_locators_must_be_sorted():
    text = "有效文本"
    sha = hashlib.sha256(text.encode()).hexdigest()
    with pytest.raises(ValidationError, match="排序"):
        EvidenceNormalizerPageInput(
            source_document_version_id="docv-A", page_artifact_id="page-1",
            page_number=1, effective_text=text, effective_text_sha256=sha, locator_ids=["loc-2", "loc-1"]
        )


def test_input_pages_must_align_with_page_numbers():
    auth = _authority()
    p1 = _page(1, "文本1", ["loc-1"])
    p2 = _page(2, "文本2", ["loc-2"])
    # page_numbers [1,2] but pages only [1]
    with pytest.raises(ValidationError, match="一一对应"):
        _input(authority=auth, pages=[p1], page_numbers=[1, 2], available_locator_ids=["loc-1", "loc-2"])


def test_input_page_numbers_must_be_sorted_unique_positive():
    with pytest.raises(ValidationError, match="升序"):
        _input(page_numbers=[2, 1], pages=[_page(2, "t2", []), _page(1, "t1", [])])


def test_input_available_locators_must_be_sorted():
    p = _page(1, "文本", ["loc-1"])
    with pytest.raises(ValidationError, match="可用定位集合"):
        _input(pages=[p], page_numbers=[1], available_locator_ids=["loc-2", "loc-1"])


def test_input_page_locator_must_be_subset_of_available():
    p = _page(1, "文本", ["loc-99"])
    with pytest.raises(ValidationError, match="可用 locator 集合"):
        _input(pages=[p], page_numbers=[1], available_locator_ids=["loc-1"])


def test_input_scope_hash_tamper_rejected():
    inp = _input()
    with pytest.raises(ValidationError, match="输入范围哈希"):
        _input(input_scope_sha256="b" * 64)


def test_input_scope_hash_is_deterministic_and_order_stable():
    auth = _authority()
    p1 = _page(1, "文本1", ["loc-1"])
    p2 = _page(2, "文本2", ["loc-2"])
    locators = _locators([p1, p2], ["loc-1", "loc-2"])
    hs1 = evidence_normalizer_input_scope_hash(
        authority=auth, logical_document_id="doc-A", manifest_sha256=SHA,
        context=_context(), related_requirements=[],
        completion_manifest_sha256="b" * 64, page_numbers=[1, 2], pages=[p1, p2],
        available_locator_ids=["loc-1", "loc-2"], available_locators=locators,
    )
    hs2 = evidence_normalizer_input_scope_hash(
        authority=auth, logical_document_id="doc-A", manifest_sha256=SHA,
        context=_context(), related_requirements=[],
        completion_manifest_sha256="b" * 64, page_numbers=[2, 1], pages=[p2, p1],
        available_locator_ids=["loc-2", "loc-1"], available_locators=list(reversed(locators)),
    )
    assert hs1 == hs2
    hs3 = evidence_normalizer_input_scope_hash(
        authority=auth, logical_document_id="doc-B", manifest_sha256=SHA,
        context=_context(), related_requirements=[],
        completion_manifest_sha256="b" * 64, page_numbers=[1, 2], pages=[p1, p2],
        available_locator_ids=["loc-1", "loc-2"], available_locators=locators,
    )
    assert hs1 != hs3


def test_input_hash_changes_with_document_context_or_requirement():
    base = _input()
    changed_context = _context(document_type="既往门诊病历")
    context_hash = evidence_normalizer_input_scope_hash(
        authority=base.authority,
        logical_document_id=base.logical_document_id,
        context=changed_context,
        related_requirements=[],
        manifest_sha256=base.manifest_sha256,
        completion_manifest_sha256=base.completion_manifest_sha256,
        page_numbers=base.page_numbers,
        pages=base.pages,
        available_locator_ids=base.available_locator_ids,
        available_locators=base.available_locators,
    )
    requirement_hash = evidence_normalizer_input_scope_hash(
        authority=base.authority,
        logical_document_id=base.logical_document_id,
        context=base.context,
        related_requirements=[_requirement()],
        manifest_sha256=base.manifest_sha256,
        completion_manifest_sha256=base.completion_manifest_sha256,
        page_numbers=base.page_numbers,
        pages=base.pages,
        available_locator_ids=base.available_locator_ids,
        available_locators=base.available_locators,
    )
    assert context_hash != base.input_scope_sha256
    assert requirement_hash != base.input_scope_sha256


def test_input_hash_changes_when_locator_descriptor_changes():
    base = _input()
    changed = base.available_locators[0].model_copy(
        update={"localized_text": "不同的定位原文", "source_text_sha256": "c" * 64}
    )
    changed_hash = evidence_normalizer_input_scope_hash(
        authority=base.authority,
        logical_document_id=base.logical_document_id,
        context=base.context,
        related_requirements=base.related_requirements,
        manifest_sha256=base.manifest_sha256,
        completion_manifest_sha256=base.completion_manifest_sha256,
        page_numbers=base.page_numbers,
        pages=base.pages,
        available_locator_ids=base.available_locator_ids,
        available_locators=[changed],
    )
    assert changed_hash != base.input_scope_sha256


def test_input_rejects_page_outside_document_context():
    with pytest.raises(ValidationError, match="资料语义上下文一致"):
        _input(context=_context(source_document_version_id="docv-other"))


def test_input_requires_sorted_unique_requirements():
    with pytest.raises(ValidationError, match="相关资料要求"):
        _input(related_requirements=[_requirement("req-2"), _requirement("req-1")])


def test_input_requires_utc():
    with pytest.raises(ValidationError, match="UTC"):
        _input(created_at=datetime(2026, 8, 22, 12, 0, 0))


# ------------------------------------------------------------- 未解决项

def test_unresolved_requires_affected_scope():
    with pytest.raises(ValidationError, match="至少关联"):
        EvidenceNormalizerUnresolvedItem(code="x", message="中", affected_pages=[], affected_locator_ids=[], reason="原因")


def test_unresolved_pages_must_be_sorted_positive():
    with pytest.raises(ValidationError, match="升序"):
        EvidenceNormalizerUnresolvedItem(code="x", message="中", affected_pages=[2, 1], affected_locator_ids=[], reason="原因")


def test_unresolved_locators_must_be_sorted():
    with pytest.raises(ValidationError, match="排序"):
        EvidenceNormalizerUnresolvedItem(code="x", message="中", affected_pages=[], affected_locator_ids=["loc-2", "loc-1"], reason="原因")


def test_unresolved_ok():
    item = _unresolved()
    assert item.code == "ambiguous_date"


# ------------------------------------------------------------- 输出合同

def test_output_ok_empty_candidates_but_with_unresolved():
    out = EvidenceNormalizerOutput(
        run_id="run-1",
        call_id="call-1",
        logical_document_id="doc-A",
        page_numbers=[1],
        fact_candidates=[],
        event_candidates=[],
        exposure_candidates=[],
        unresolved_items=[_unresolved()],
    )
    assert out.fact_candidates == []


def test_output_allows_empty_all_when_pages_closed():
    # 空候选零未解决也允许通过校验（由门禁判定是否遗漏），此处仅校验形状
    out = EvidenceNormalizerOutput(
        run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[1],
    )
    assert out.unresolved_items == []


def test_output_rejects_mismatched_run_id_in_candidate():
    bad_fact = _fact_candidate(run_id="run-2")
    with pytest.raises(ValidationError, match="run_id/call_id"):
        EvidenceNormalizerOutput(
            run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[1],
            fact_candidates=[bad_fact],
        )


def test_output_rejects_duplicate_candidate_ids():
    f1 = _fact_candidate(candidate_id="dup")
    e1 = _event_candidate(candidate_id="dup")
    with pytest.raises(ValidationError, match="全局唯一"):
        EvidenceNormalizerOutput(
            run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[1],
            fact_candidates=[f1], event_candidates=[e1],
        )


def test_output_unresolved_pages_must_belong_to_call():
    item = _unresolved(affected_pages=[99])
    with pytest.raises(ValidationError, match="属于本次调用页清单"):
        EvidenceNormalizerOutput(
            run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[1],
            unresolved_items=[item],
        )


def test_output_page_numbers_must_be_sorted_unique():
    with pytest.raises(ValidationError, match="升序"):
        EvidenceNormalizerOutput(run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[2, 1])


def test_output_extra_top_level_rejected():
    with pytest.raises(ValidationError, match="extra"):
        EvidenceNormalizerOutput.model_validate(
            {
                "run_id": "run-1", "call_id": "call-1", "logical_document_id": "doc-A",
                "page_numbers": [1], "accepted_facts": [],
            }
        )


def test_output_schema_version_is_phase5():
    out = EvidenceNormalizerOutput(run_id="run-1", call_id="call-1", logical_document_id="doc-A", page_numbers=[1])
    assert out.schema_version == "phase5/v1"


def test_candidate_and_published_physically_separate():
    cand = _fact_candidate()
    assert hasattr(cand, "model_uncertainty")
    assert cand.schema_version == "phase5/v1"
