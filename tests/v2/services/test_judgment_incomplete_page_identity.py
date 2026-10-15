from types import SimpleNamespace

from app.domain.contracts.judgment_search import JudgmentSearchLanePageGap
from app.services.judgment_search_status import _incomplete_pages


def test_equal_page_numbers_from_different_documents_remain_separate():
    gaps = [
        JudgmentSearchLanePageGap(
            lane=lane, source_document_version_id=document,
            page_artifact_id=artifact, page_number=1,
        )
        for document, artifact, lane in [
            ("document-a", "page-a", "main-A"),
            ("document-b", "page-b", "main-A"),
            ("document-a", "page-a", "main-B"),
        ]
    ]
    summary = SimpleNamespace(
        pages_without_lane_result=gaps, unreadable_channels=(), ambiguous_channels=(),
    )
    rows = _incomplete_pages(summary)
    assert len(rows) == 2
    assert [(r["source_document_version_id"], r["page_artifact_id"]) for r in rows] == [
        ("document-a", "page-a"), ("document-b", "page-b"),
    ]
    assert [len(r["reasons"]) for r in rows] == [2, 1]
