"""判断检索回执工件保存/装载测试（tmp_path 真实 ArtifactStore + 合成回执）。

回执经真实 v4 读器注入 fake completion 产生（复用 results 测试中可导入的
助手）；存储为既有 raw_response 工件类别，无新框架。
"""
from __future__ import annotations

import hashlib

import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.evidence.artifacts import (
    ArtifactIntegrityError,
    ArtifactStore,
    ArtifactStoreError,
)
from app.services.judgment_search_artifacts import (
    JudgmentSearchArtifactError,
    load_judgment_search_receipt,
    save_judgment_search_receipt,
)
from tests.v2.services.test_judgment_search_results import (
    _IMAGE_A,
    _IMAGE_B,
    _TARGET,
    _ambiguous_payload,
    _found_payload,
    _gather,
    _not_found_payload,
    _page_input,
    _read,
    _route,
    _scope_two,
)


@pytest.fixture
def store(data_paths) -> ArtifactStore:
    return ArtifactStore(data_paths)


def _receipts():
    scope = _scope_two()
    receipts = _gather(
        scope,
        lane_a_text=lambda page_number: (
            _found_payload() if page_number == 1 else _not_found_payload()
        ),
        lane_b_text=lambda page_number: (
            _ambiguous_payload() if page_number == 1 else _not_found_payload()
        ),
    )
    return scope, receipts


def test_roundtrip_preserves_ambiguous_note_and_raw_completion(store):
    scope, receipts = _receipts()
    pairs = [
        (receipt, save_judgment_search_receipt(store, scope, _TARGET, receipt))
        for receipt in receipts
    ]
    assert all(artifact.kind == "raw_response" for _, artifact in pairs)
    for receipt, artifact in pairs:
        loaded = load_judgment_search_receipt(
            store, scope, _TARGET, artifact.storage_ref
        )
        assert loaded == receipt
        assert loaded.completion.text == receipt.completion.text
        assert loaded.product_acceptance is False
    ambiguous = next(
        r for r in receipts
        if r.requested.lane == PageReviewLane.MAIN_B and r.page.page_number == 1
    )
    ambiguous_receipt = next(
        r for r in receipts
        if r.requested.lane == PageReviewLane.MAIN_B and r.page.page_number == 1
    )
    loaded = load_judgment_search_receipt(
        store, scope, _TARGET,
        next(a for r, a in pairs if r is ambiguous_receipt).storage_ref,
    )
    candidate = loaded.page_result.printed_analysis.candidates[0]
    assert candidate.uncertainty_note == "作者与日期不可辨"
    assert candidate.coordinate_convention == "unverified"
    assert candidate.text == "疑似病程记录判断（指向不明）"
    assert ambiguous.page_result.printed_analysis.candidates[0] == candidate


def test_same_bytes_same_identity(store):
    scope, receipts = _receipts()
    receipt = receipts[0]
    first = save_judgment_search_receipt(store, scope, _TARGET, receipt)
    second = save_judgment_search_receipt(store, scope, _TARGET, receipt)
    assert first == second
    assert first.storage_ref == second.storage_ref
    assert first.sha256 == second.sha256


def test_saved_receipt_rejects_markdown_wrapper(store):
    scope, receipts = _receipts()
    wrapped = "```json\n" + receipts[0].model_dump_json() + "\n```"
    artifact = store.put("raw_response", wrapped.encode("utf-8"))
    with pytest.raises(JudgmentSearchArtifactError, match="纯 JSON"):
        load_judgment_search_receipt(store, scope, _TARGET, artifact.storage_ref)


def test_changed_reply_gets_new_identity_and_preserves_old(store):
    scope = _scope_two()
    plain = _read(
        scope, _page_input("pa-1", 1, _IMAGE_A),
        _route(PageReviewLane.MAIN_A), _not_found_payload(),
    )
    found = _read(
        scope, _page_input("pa-1", 1, _IMAGE_A),
        _route(PageReviewLane.MAIN_A), _found_payload(),
    )
    old = save_judgment_search_receipt(store, scope, _TARGET, plain)
    new = save_judgment_search_receipt(store, scope, _TARGET, found)
    assert new.sha256 != old.sha256
    assert new.storage_ref != old.storage_ref
    loaded_old = load_judgment_search_receipt(store, scope, _TARGET, old.storage_ref)
    assert loaded_old == plain
    assert loaded_old.page_result.handwritten.disposition.value == "not_found"
    loaded_new = load_judgment_search_receipt(store, scope, _TARGET, new.storage_ref)
    assert loaded_new.page_result.handwritten.disposition.value == "found"


def test_stale_target_rejected_on_load(store):
    scope, receipts = _receipts()
    artifact = save_judgment_search_receipt(store, scope, _TARGET, receipts[0])
    with pytest.raises(Exception, match="目标"):
        load_judgment_search_receipt(
            store, scope, "漂移后的目标文本", artifact.storage_ref
        )


def test_stale_scope_rejected_on_load(store):
    scope, receipts = _receipts()
    artifact = save_judgment_search_receipt(store, scope, _TARGET, receipts[0])
    drifted = _scope_two().model_copy(update={"requirement_id": "IN-2"})
    from app.domain.contracts.judgment_search import judgment_search_scope_sha256

    drifted = type(drifted)(
        authority=drifted.authority,
        requirement_id="IN-2",
        pages=drifted.pages,
        scope_sha256=judgment_search_scope_sha256(
            authority=drifted.authority, requirement_id="IN-2", pages=drifted.pages
        ),
    )
    with pytest.raises(Exception, match="范围哈希"):
        load_judgment_search_receipt(store, drifted, _TARGET, artifact.storage_ref)


def test_stale_prompt_version_rejected_before_save(store):
    scope, receipts = _receipts()
    stale = receipts[0].model_copy(update={
        "prompt_version": "judgment-search-reader/v3",
    })
    with pytest.raises(Exception, match="不重标"):
        save_judgment_search_receipt(store, scope, _TARGET, stale)
    # 过时回执不被静默接纳：没有任何字节落盘。
    assert not (store.data_paths.root / "artifacts" / "raw_response").exists() or (
        not list((store.data_paths.root / "artifacts" / "raw_response").iterdir())
    )


def test_raw_response_page_result_mismatch_rejected_before_save(store):
    scope, receipts = _receipts()
    victim = next(
        r for r in receipts
        if r.requested.lane == PageReviewLane.MAIN_A and r.page.page_number == 1
    )
    drifted_candidate = victim.page_result.handwritten.candidates[0].model_copy(
        update={"text": "与原始回答无关的漂移摘录"}
    )
    forged = victim.model_copy(update={
        "page_result": victim.page_result.model_copy(update={
            "handwritten": victim.page_result.handwritten.model_copy(
                update={"candidates": (drifted_candidate,)}
            ),
        }),
    })
    with pytest.raises(Exception, match="原始回答"):
        save_judgment_search_receipt(store, scope, _TARGET, forged)


def test_non_raw_response_reference_rejected(store):
    page_image = store.put("page_image", b"page-bytes")
    scope, receipts = _receipts()
    artifact = save_judgment_search_receipt(store, scope, _TARGET, receipts[0])
    with pytest.raises(JudgmentSearchArtifactError, match="raw_response"):
        load_judgment_search_receipt(
            store, scope, _TARGET, page_image.storage_ref
        )
    with pytest.raises(JudgmentSearchArtifactError, match="raw_response"):
        load_judgment_search_receipt(store, scope, _TARGET, "blobs/abcdef")


def test_missing_artifact_rejected_with_cause(store):
    scope, receipts = _receipts()
    ghost_ref = (
        "artifacts/raw_response/" + hashlib.sha256(b"ghost").hexdigest()
    )
    with pytest.raises(JudgmentSearchArtifactError) as error:
        load_judgment_search_receipt(store, scope, _TARGET, ghost_ref)
    assert isinstance(error.value.__cause__, ArtifactStoreError)


def test_corrupted_bytes_rejected_with_integrity_cause(store, data_paths):
    scope, receipts = _receipts()
    artifact = save_judgment_search_receipt(store, scope, _TARGET, receipts[0])
    target = data_paths.root / artifact.storage_ref
    target.write_bytes(b'{"tampered": true}')
    with pytest.raises(JudgmentSearchArtifactError) as error:
        load_judgment_search_receipt(store, scope, _TARGET, artifact.storage_ref)
    assert isinstance(error.value.__cause__, ArtifactIntegrityError)


def test_duplicate_json_keys_rejected(store):
    scope, receipts = _receipts()
    crafted = (
        b'{"scope_sha256": "a", "scope_sha256": "b", "target_sha256": "c"}'
    )
    forged = store.put("raw_response", crafted)
    with pytest.raises(JudgmentSearchArtifactError) as error:
        load_judgment_search_receipt(store, scope, _TARGET, forged.storage_ref)
    assert isinstance(error.value.__cause__, Exception)
    assert "JSON" in str(error.value)
