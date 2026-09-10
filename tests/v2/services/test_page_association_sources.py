from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import page_association_sources as service
from tests.v2.evidence.test_slice44_effective_text_engine import RAW, _corr


def _setup(monkeypatch):
    entry = SimpleNamespace(ocr_page_id="op-1", page_artifact_id="page-1",
                            page_number=1, source_document_version_id="doc-1")
    revision = SimpleNamespace(correction_ids=[], manifest=[entry])
    ocr = SimpleNamespace(page_artifact_id="page-1", page_number=1, raw_text=RAW)
    ocr_repo, correction_repo = Mock(), Mock()
    ocr_repo.get.return_value = ocr
    monkeypatch.setattr(service, "OcrPageRepository", lambda session: ocr_repo)
    monkeypatch.setattr(service, "CorrectionRepository", lambda session: correction_repo)
    return revision, ocr, ocr_repo, correction_repo


def test_selected_correction_changes_only_projected_source(monkeypatch):
    revision, ocr, _, corrections = _setup(monkeypatch)
    original = service.page_association_sources(None, revision)["page-1"]
    revision.correction_ids = ["chosen"]
    corrections.get.return_value = _corr("chosen", 4, 7, "5.6", "5.60")
    projected = service.page_association_sources(None, revision)["page-1"]
    corrections.get.assert_called_once_with("chosen")
    assert projected.text == "ALT 5.60 mmol/L 且 AST 3.5 mmol/L"
    assert projected.text_sha256 == sha256(projected.text.encode()).hexdigest()
    assert projected.text_sha256 != original.text_sha256
    assert ocr.raw_text == RAW


@pytest.mark.parametrize("field,value", [("page_artifact_id", "other-page"), ("page_number", 2)])
def test_wrong_ocr_page_is_rejected(monkeypatch, field, value):
    revision, ocr, _, _ = _setup(monkeypatch)
    setattr(ocr, field, value)
    with pytest.raises(ValueError, match="原件页不一致"):
        service.page_association_sources(None, revision)


def test_no_ocr_does_not_read_or_invent_text(monkeypatch):
    revision, _, ocr_repo, _ = _setup(monkeypatch)
    revision.manifest[0].ocr_page_id = None
    assert service.page_association_sources(None, revision) == {}
    ocr_repo.get.assert_not_called()


def test_invalid_selected_correction_is_not_silently_ignored(monkeypatch):
    revision, _, _, corrections = _setup(monkeypatch)
    revision.correction_ids = ["chosen"]
    corrections.get.return_value = _corr("chosen", 4, 7, "5.6", "5.60", raw_text_sha256="0" * 64)
    with pytest.raises(ValueError, match="源文本不一致"):
        service.page_association_sources(None, revision)
