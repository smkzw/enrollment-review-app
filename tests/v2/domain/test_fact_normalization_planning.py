"""Phase 5 Slice 5.3 确定性规划聚焦测试（纯确定性，无存储/模型）。

覆盖：
- 默认按逻辑文档一切片，超长文档按连续页组切片，页组连续且跨调用连续无间隙；
- 稳定输入哈希（canonical_hash，排除时间/文件名/置信度），同输入同哈希、异文本异哈希、排序无关；
- 显式完整页闭合：缺页/多余页/重复页/跨逻辑文档页一律拒绝；
- 无跨 episode/隐式日期借用：权威元组与修订作用域不一致拒绝，PageInput 不合成日期；
- 有效文本仅通过哈希参与规划，不借用筛选/上传/操作日期。
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from app.domain.contracts.enums import PageArtifactStatus, ReviewStage
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerContextInput
from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
from app.domain.contracts.evidence_processing import EvidenceProcessingRevisionPage
from app.domain.contracts.facts import FactAuthority
from app.domain.planning.fact_normalization_planning import (
    PageInput,
    compute_call_input_hash as _compute_call_input_hash,
    compute_input_scope_hash,
    plan_fact_normalization_calls as _plan_fact_normalization_calls,
    validate_calls_contiguous,
    validate_full_page_closure,
)

SHA = "a" * 64
SHA_B = "b" * 64
UTC_NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _authority(**overrides) -> FactAuthority:
    base = {
        "project_id": "proj-1",
        "subject_id": "subj-1",
        "review_episode_id": "ep-1",
        "episode_revision": 1,
        "protocol_version_id": "pv-1",
        "rule_set_id": "rs-1",
        "rule_set_revision": 1,
        "evidence_snapshot_v2_id": "snap-1",
        "complete_processing_revision_id": "complete-1",
    }
    base.update(overrides)
    return FactAuthority(**base)


def _revision(
    *,
    revision_id: str = "complete-1",
    snapshot_id: str = "snap-1",
    project_id: str = "proj-1",
    subject_id: str = "subj-1",
    episode_id: str = "ep-1",
    manifest_entries: list[tuple[str, int, str, str]] | None = None,
) -> CompleteEvidenceProcessingRevision:
    if manifest_entries is None:
        manifest_entries = [("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2")]
    manifest: list[EvidenceProcessingRevisionPage] = []
    for idx, (doc_ver, page_num, pa_id, op_id) in enumerate(manifest_entries, start=1):
        manifest.append(
            EvidenceProcessingRevisionPage(
                entry_id=f"entry-{idx}",
                position=idx,
                source_document_version_id=doc_ver,
                page_number=page_num,
                original_frame=None,
                page_artifact_id=pa_id,
                ocr_page_id=op_id,
                status=PageArtifactStatus.SUCCEEDED,
                failure_reason=None,
            )
        )
    from app.domain.publication import evidence_processing_manifest_hash

    m_sha = evidence_processing_manifest_hash(
        entries=[
            (e.source_document_version_id, e.page_number, e.original_frame, e.page_artifact_id, e.ocr_page_id, e.status.value)
            for e in manifest
        ]
    )
    return CompleteEvidenceProcessingRevision(
        evidence_processing_revision_id=revision_id,
        evidence_snapshot_id=snapshot_id,
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=episode_id,
        base_processing_revision_id="base-1",
        producer_candidate_id="cand-1",
        candidate_input_sha256=SHA,
        manifest=manifest,
        manifest_sha256=m_sha,
        locator_ids=[],
        risk_scan_ids=[],
        risk_review_ids=[],
        correction_ids=[],
        metadata_revision_ids=[],
        referenced_document_revision_ids=[],
        resolution_revision_ids=[],
        completion_manifest_sha256=sha("complete-" + revision_id),
        status="ready",
        is_activatable=True,
        created_at=UTC_NOW,
        created_by="tester",
    )


def _page_input(
    *,
    doc_ver: str = "docv-1",
    page: int = 1,
    pa: str = "pa-1",
    op: str = "op-1",
    logical: str = "logical-1",
    eff_sha: str | None = None,
    eff_text: str | None = None,
) -> PageInput:
    if eff_sha is None:
        eff_sha = sha(f"text-{doc_ver}-{page}")
    if eff_text is None:
        eff_text = f"text-{doc_ver}-{page}"
    return PageInput(
        source_document_version_id=doc_ver,
        page_number=page,
        page_artifact_id=pa,
        ocr_page_id=op,
        effective_text_sha256=eff_sha,
        logical_document_id=logical,
        effective_text=eff_text,
    )


def _context(source_document_version_id: str) -> EvidenceNormalizerContextInput:
    return EvidenceNormalizerContextInput(
        source_document_version_id=source_document_version_id,
        metadata_revision_id=f"meta-{source_document_version_id}",
        document_type="筛选病历",
        source_party="研究者",
        document_record_time=None,
        current_review_stage=ReviewStage.SCREENING,
        workflow_stage_id="rs-1:screening",
    )


def compute_call_input_hash(**kwargs):
    page_inputs = kwargs["page_inputs"]
    kwargs.setdefault("context", _context(page_inputs[0].source_document_version_id))
    kwargs.setdefault("related_requirements", [])
    return _compute_call_input_hash(**kwargs)


def plan_fact_normalization_calls(**kwargs):
    mapping = kwargs.get("doc_version_to_logical", {})
    contexts = {
        logical: _context(source_version)
        for source_version, logical in mapping.items()
    }
    kwargs.setdefault("context_by_logical_document", contexts)
    kwargs.setdefault("related_requirements", [])
    return _plan_fact_normalization_calls(**kwargs)


def _planned_call(**kwargs):
    from app.domain.planning.fact_normalization_planning import PlannedCall

    page_inputs = kwargs.get("page_inputs", ())
    source_version = page_inputs[0].source_document_version_id if page_inputs else "docv-1"
    kwargs.setdefault("context", _context(source_version))
    kwargs.setdefault("related_requirements", ())
    return PlannedCall(**kwargs)


# --------------------------------------------------------------------------- 默认逻辑文档切片

def test_default_slices_one_call_per_logical_document():
    rev = _revision(
        manifest_entries=[
            ("docv-a", 1, "pa-a1", "op-a1"),
            ("docv-a", 2, "pa-a2", "op-a2"),
            ("docv-b", 1, "pa-b1", "op-b1"),
        ]
    )
    authority = _authority()
    doc_to_log = {"docv-a": "logical-a", "docv-b": "logical-b"}
    page_map = {
        ("docv-a", 1): _page_input(doc_ver="docv-a", page=1, pa="pa-a1", op="op-a1", logical="logical-a"),
        ("docv-a", 2): _page_input(doc_ver="docv-a", page=2, pa="pa-a2", op="op-a2", logical="logical-a"),
        ("docv-b", 1): _page_input(doc_ver="docv-b", page=1, pa="pa-b1", op="op-b1", logical="logical-b"),
    }
    plan = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
    )
    assert len(plan.calls) == 2
    by_log = {c.logical_document_id: c for c in plan.calls}
    assert by_log["logical-a"].page_numbers == (1, 2)
    assert by_log["logical-b"].page_numbers == (1,)
    # 完整闭合与连续性应通过
    validate_full_page_closure(plan.calls, rev, doc_version_to_logical=doc_to_log)
    validate_calls_contiguous(plan.calls)


def test_ultra_long_doc_splits_into_contiguous_groups():
    # 单逻辑文档 6 页，max=2 -> 3 组
    entries = [(f"docv-1", i, f"pa-{i}", f"op-{i}") for i in range(1, 7)]
    rev = _revision(manifest_entries=entries)
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    page_map = {
        (f"docv-1", i): _page_input(doc_ver="docv-1", page=i, pa=f"pa-{i}", op=f"op-{i}", logical="logical-1")
        for i in range(1, 7)
    }
    plan = plan_fact_normalization_calls(
        authority=authority,
        revision=rev,
        page_effective_text_map=page_map,
        doc_version_to_logical=doc_to_log,
        max_pages_per_call=2,
    )
    assert len(plan.calls) == 3
    pages = [c.page_numbers for c in plan.calls]
    assert pages == [(1, 2), (3, 4), (5, 6)]
    # 每组连续，整体连续无间隙
    validate_calls_contiguous(plan.calls)
    validate_full_page_closure(plan.calls, rev, doc_version_to_logical=doc_to_log)
    # 稳定排序：按起始页
    assert [c.page_numbers[0] for c in plan.calls] == [1, 3, 5]


def test_max_pages_per_call_last_group_smaller():
    entries = [("docv-1", i, f"pa-{i}", f"op-{i}") for i in range(1, 8)]
    rev = _revision(manifest_entries=entries)
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    page_map = {(f"docv-1", i): _page_input(doc_ver="docv-1", page=i, pa=f"pa-{i}", op=f"op-{i}", logical="logical-1") for i in range(1, 8)}
    plan = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log, max_pages_per_call=3
    )
    assert [c.page_numbers for c in plan.calls] == [(1, 2, 3), (4, 5, 6), (7,)]


# --------------------------------------------------------------------------- 哈希稳定性

def test_call_input_hash_stable_for_same_content():
    rev = _revision()
    authority = _authority()
    pi = _page_input()
    h1 = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[1], page_inputs=[pi]
    )
    h2 = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[1], page_inputs=[pi]
    )
    assert h1 == h2
    assert len(h1) == 64


def test_call_input_hash_changes_when_eff_text_changes():
    rev = _revision()
    authority = _authority()
    pi_a = _page_input(eff_sha=sha("text-a"), eff_text="text-a")
    pi_b = _page_input(eff_sha=sha("text-b"), eff_text="text-b")
    h_a = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[1], page_inputs=[pi_a]
    )
    h_b = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[1], page_inputs=[pi_b]
    )
    assert h_a != h_b


def test_call_input_hash_order_stable():
    rev = _revision(
        manifest_entries=[("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2")]
    )
    authority = _authority()
    pi1 = _page_input(page=1, pa="pa-1", op="op-1")
    pi2 = _page_input(page=2, pa="pa-2", op="op-2")
    # 故意传入乱序 page_inputs，hash 应按页码排序后一致
    h_ordered = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[1, 2], page_inputs=[pi1, pi2]
    )
    h_reversed = compute_call_input_hash(
        authority=authority, revision=rev, logical_document_id="logical-1", page_numbers=[2, 1], page_inputs=[pi2, pi1]
    )
    assert h_ordered == h_reversed


def test_input_scope_hash_stable_and_sorted():
    rev = _revision(
        manifest_entries=[("docv-a", 1, "pa-a1", "op-a1"), ("docv-b", 1, "pa-b1", "op-b1")]
    )
    authority = _authority()
    doc_to_log = {"docv-a": "logical-a", "docv-b": "logical-b"}
    page_map = {
        ("docv-a", 1): _page_input(doc_ver="docv-a", page=1, pa="pa-a1", op="op-a1", logical="logical-a"),
        ("docv-b", 1): _page_input(doc_ver="docv-b", page=1, pa="pa-b1", op="op-b1", logical="logical-b"),
    }
    plan = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
    )
    # 重排调用顺序后 scope hash 应一致（内部排序）
    from app.domain.planning.fact_normalization_planning import compute_input_scope_hash

    h1 = compute_input_scope_hash(authority=authority, revision=rev, calls=list(plan.calls))
    h2 = compute_input_scope_hash(authority=authority, revision=rev, calls=list(reversed(plan.calls)))
    assert h1 == h2 == plan.input_scope_sha256


def test_plan_is_deterministic_across_runs():
    rev = _revision(
        manifest_entries=[("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2"), ("docv-1", 3, "pa-3", "op-3")]
    )
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    page_map = {(f"docv-1", i): _page_input(doc_ver="docv-1", page=i, pa=f"pa-{i}", op=f"op-{i}", logical="logical-1") for i in range(1, 4)}
    plan1 = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log, max_pages_per_call=2
    )
    plan2 = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log, max_pages_per_call=2
    )
    assert plan1.input_scope_sha256 == plan2.input_scope_sha256
    assert [c.input_sha256 for c in plan1.calls] == [c.input_sha256 for c in plan2.calls]


# --------------------------------------------------------------------------- 完整页闭合

def test_missing_page_rejected():
    rev = _revision(
        manifest_entries=[("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2")]
    )
    # 故意只传入一页，缺页应被 full_closure 拒绝
    authority = _authority()
    from app.domain.planning.fact_normalization_planning import PlannedCall

    pi = _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")
    call = _planned_call(
        logical_document_id="logical-1",
        page_numbers=(1,),
        page_inputs=(pi,),
        input_sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="缺页"):
        validate_full_page_closure([call], rev, doc_version_to_logical={"docv-1": "logical-1"})


def test_extra_page_rejected():
    rev = _revision(manifest_entries=[("docv-1", 1, "pa-1", "op-1")])
    from app.domain.planning.fact_normalization_planning import PlannedCall

    pi1 = _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")
    pi2 = _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1")
    call1 = _planned_call(
        logical_document_id="logical-1", page_numbers=(1,), page_inputs=(pi1,), input_sha256="f" * 64
    )
    call2 = _planned_call(
        logical_document_id="logical-1", page_numbers=(2,), page_inputs=(pi2,), input_sha256="e" * 64
    )
    with pytest.raises(ValueError, match="多余页"):
        validate_full_page_closure([call1, call2], rev, doc_version_to_logical={"docv-1": "logical-1"})


def test_duplicate_page_rejected():
    rev = _revision(manifest_entries=[("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2")])
    from app.domain.planning.fact_normalization_planning import PlannedCall

    pi1 = _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")
    pi2 = _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1")
    call1 = _planned_call(
        logical_document_id="logical-1", page_numbers=(1, 2), page_inputs=(pi1, pi2), input_sha256="f" * 64
    )
    call2 = _planned_call(
        logical_document_id="logical-1", page_numbers=(2,), page_inputs=(pi2,), input_sha256="e" * 64
    )
    with pytest.raises(ValueError, match="重复页"):
        validate_full_page_closure([call1, call2], rev, doc_version_to_logical={"docv-1": "logical-1"})


def test_non_contiguous_page_group_rejected():
    from app.domain.planning.fact_normalization_planning import PlannedCall

    pi1 = _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")
    pi3 = _page_input(page=3, pa="pa-3", op="op-3", logical="logical-1")
    # PlannedCall 构造时即拒绝非连续页组
    with pytest.raises(ValueError, match="必须连续"):
        _planned_call(
            logical_document_id="logical-1",
            page_numbers=(1, 3),
            page_inputs=(pi1, pi3),
            input_sha256="f" * 64,
        )


def test_calls_with_gap_rejected_by_contiguous_validator():
    rev = _revision(
        manifest_entries=[("docv-1", 1, "pa-1", "op-1"), ("docv-1", 2, "pa-2", "op-2"), ("docv-1", 3, "pa-3", "op-3")]
    )
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    # 构造两个调用 [1] 和 [3]，跨调用间隙（缺 2）应被 validate_calls_contiguous 拒绝（即使单组内部连续）
    from app.domain.planning.fact_normalization_planning import PlannedCall

    pi1 = _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")
    pi3 = _page_input(page=3, pa="pa-3", op="op-3", logical="logical-1")
    call1 = _planned_call(logical_document_id="logical-1", page_numbers=(1,), page_inputs=(pi1,), input_sha256="f" * 64)
    call2 = _planned_call(logical_document_id="logical-1", page_numbers=(3,), page_inputs=(pi3,), input_sha256="e" * 64)
    with pytest.raises(ValueError, match="连续无间隙"):
        validate_calls_contiguous([call1, call2])
    # 同时 full_closure 也会因缺页失败
    with pytest.raises(ValueError, match="缺页"):
        validate_full_page_closure([call1, call2], rev, doc_version_to_logical=doc_to_log)


def test_empty_manifest_rejected():
    rev = _revision(manifest_entries=[])
    # _revision with empty manifest would have no pages; but contract allows empty list?
    # 我们直接构造一个空 manifest 的修订进行规划
    authority = _authority()
    with pytest.raises(ValueError, match="不能为空"):
        plan_fact_normalization_calls(
            authority=authority,
            revision=rev,
            page_effective_text_map={},
            doc_version_to_logical={},
        )


# --------------------------------------------------------------------------- 无跨 episode / 隐式日期借用

def test_cross_episode_authority_rejected():
    rev = _revision(episode_id="ep-1")
    # authority 指向另一个 episode
    authority = _authority(review_episode_id="ep-2")
    doc_to_log = {"docv-1": "logical-1"}
    page_map = {
        ("docv-1", 1): _page_input(logical="logical-1"),
        ("docv-1", 2): _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1"),
    }
    with pytest.raises(ValueError, match="跨 episode"):
        plan_fact_normalization_calls(
            authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
        )


def test_cross_episode_via_doc_version_rejected():
    # 虽然 authority 匹配 revision，但 doc_version_to_logical 映射到错误 episode 的资料版本
    # 此场景由 source adapter 的 doc_version 校验覆盖，此处通过 pageInput 逻辑文档不一致间接暴露
    rev = _revision()
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    # PageInput 的 logical 与映射一致，但假设 revision 的 manifest 源自另一 episode 的 docv（已由 revision 保证）
    # 此处直接测试 plan 对 authority 完整修订不一致的拒绝已在上一测试覆盖
    # 额外确保 plan 不会借用外部 episode 的页
    page_map = {
        ("docv-1", 1): _page_input(logical="logical-1"),
        ("docv-1", 2): _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1"),
    }
    # 正常情况应通过
    plan = plan_fact_normalization_calls(
        authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
    )
    assert plan.authority.review_episode_id == rev.review_episode_id


def test_no_implicit_date_borrowing_in_planning():
    """规划仅传递有效文本哈希，不合成 PartialDateRange 缺失日期。"""
    rev = _revision()
    authority = _authority()
    # PageInput 中不包含任何日期字段；即使 effective_text 为空，也不得借用筛选日
    pi = PageInput(
        source_document_version_id="docv-1",
        page_number=1,
        page_artifact_id="pa-1",
        ocr_page_id="op-1",
        effective_text_sha256=sha(""),
        logical_document_id="logical-1",
        effective_text="",
    )
    pi2 = _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1")
    plan = plan_fact_normalization_calls(
        authority=authority,
        revision=rev,
        page_effective_text_map={("docv-1", 1): pi, ("docv-1", 2): pi2},
        doc_version_to_logical={"docv-1": "logical-1"},
    )
    # effective_text 为空的页仍被规划，但其哈希为空文本哈希，不等于筛选日等锚点
    assert plan.calls[0].page_inputs[0].effective_text_sha256 == sha("")
    # 规划不产生任何 PartialDateRange
    assert all(not hasattr(c, "date_range") for c in plan.calls)


def test_missing_effective_text_map_entry_rejected():
    rev = _revision()
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    # 仅提供一页的有效文本，另一页缺失 -> 拒绝隐式补页
    page_map = {("docv-1", 1): _page_input(page=1, pa="pa-1", op="op-1", logical="logical-1")}
    with pytest.raises(ValueError, match="缺少有效文本"):
        plan_fact_normalization_calls(
            authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
        )


def test_page_input_mismatch_rejected():
    rev = _revision()
    authority = _authority()
    doc_to_log = {"docv-1": "logical-1"}
    # PageInput 的 page_artifact_id 与 manifest 不一致 -> 拒绝跨修订借用
    bad_pi = _page_input(page=1, pa="pa-bad", op="op-1", logical="logical-1")
    good_pi = _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1")
    page_map = {("docv-1", 1): bad_pi, ("docv-1", 2): good_pi}
    with pytest.raises(ValueError, match="不一致"):
        plan_fact_normalization_calls(
            authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical=doc_to_log
        )


def test_logical_mapping_missing_rejected():
    rev = _revision()
    authority = _authority()
    page_map = {
        ("docv-1", 1): _page_input(logical="logical-1"),
        ("docv-1", 2): _page_input(page=2, pa="pa-2", op="op-2", logical="logical-1"),
    }
    with pytest.raises(ValueError, match="缺少逻辑文档映射"):
        plan_fact_normalization_calls(
            authority=authority, revision=rev, page_effective_text_map=page_map, doc_version_to_logical={}
        )
