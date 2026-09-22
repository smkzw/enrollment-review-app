"""Deterministic tests for selective page-risk vision review (Phase 5).

Acceptance boundary (worker_03):
  ACCEPT — page-risk triage: native-text SKIP; enter only for
           scan / complex table / structure anomaly / OCR quality risk;
           fail-closed provider errors; source-locator fidelity;
           content-neutral planner (no project-specific gating).
  REJECT — whole-document page-by-page VLM; silent OCR/semantic fallback;
           OCR raw_text overwrite; enrollment verdict from vision text;
           D001 restore; study/disease/drug/score/visit/criterion hardcoding.
  LIVE   — not required here; Independent VLM live coverage stays in
           tests/v2/llm/test_independent_vlm.py.

Aligned to worker_02 production surface:
  app.evidence.selective_vision_review
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from app.domain.contracts.enums import (
    ExtractionRoute,
    OcrRiskKind,
    OcrRiskLevel,
    PageArtifactStatus,
)
from app.llm import independent_vlm as vlm
from app.llm.independent_vlm import PageVisionInput
from app.evidence import selective_vision_review as svr

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "app" / "evidence" / "selective_vision_review.py"

EXPECTED_REASON_CODES = frozenset(
    {
        "scan_or_image_only",
        "complex_visual_or_table_layout",
        "native_extraction_anomaly",
        "ocr_evidence_risk",
    }
)

FORBIDDEN_SOURCE_TOKENS = (
    "D001",
    "3259ab5f070447c3938ff2de5f45c9cd",
    "入排最终",
    "enrollment_verdict",
    "SAR",
    "RECIST",
    "ECOG",
    "Nivolumab",
    "Pembrolizumab",
    "criteria_id",
    "visit_window",
)


def _signals(
    *,
    source_ref: str = "src.doc.v1.p1",
    page_ordinal: int = 1,
    media_kind: str = "pdf",
    extraction_route: str | ExtractionRoute | None = ExtractionRoute.NATIVE_PDF_TEXT,
    page_artifact_status: str | PageArtifactStatus | None = PageArtifactStatus.SUCCEEDED,
    has_page_image: bool = True,
    has_native_text: bool = True,
    native_text_char_count: int = 64,
    non_text_mark_count: int | None = None,
    complex_layout_not_represented_by_native_text: bool = False,
    native_extraction_anomaly: bool = False,
    ocr_confidence: float | None = None,
    ocr_risk_kinds: tuple[str, ...] = (),
) -> svr.PageVisionTriageSignals:
    return svr.PageVisionTriageSignals(
        source_ref=source_ref,
        page_ordinal=page_ordinal,
        media_kind=media_kind,
        extraction_route=(
            extraction_route.value
            if isinstance(extraction_route, ExtractionRoute)
            else extraction_route
        ),
        page_artifact_status=(
            page_artifact_status.value
            if isinstance(page_artifact_status, PageArtifactStatus)
            else page_artifact_status
        ),
        has_page_image=has_page_image,
        has_native_text=has_native_text,
        native_text_char_count=native_text_char_count,
        non_text_mark_count=non_text_mark_count,
        complex_layout_not_represented_by_native_text=(
            complex_layout_not_represented_by_native_text
        ),
        native_extraction_anomaly=native_extraction_anomaly,
        ocr_confidence=ocr_confidence,
        ocr_risk_kinds=ocr_risk_kinds,
    )


def _page_input(
    *,
    source_ref: str = "src.doc.v1.p1",
    page_ordinal: int = 1,
    image_bytes: bytes = b"\x89PNG\r\n\x1a\npage",
) -> PageVisionInput:
    return PageVisionInput(
        source_ref=source_ref,
        page_ordinal=page_ordinal,
        image_bytes=image_bytes,
    )


# ---------------------------------------------------------------------------
# Contract surface: closed reason vocabulary
# ---------------------------------------------------------------------------


def test_allowed_vision_risk_reasons_are_closed_and_content_neutral():
    assert set(svr.ALLOWED_VISION_RISK_REASONS) == EXPECTED_REASON_CODES
    joined = " ".join(sorted(svr.ALLOWED_VISION_RISK_REASONS))
    for token in ("d001", "sar", "ecog", "drug", "disease", "visit", "criterion"):
        assert token not in joined


# ---------------------------------------------------------------------------
# Native text primary → SKIP
# ---------------------------------------------------------------------------


def test_native_pdf_text_page_skips_vision_review():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.NATIVE_PDF_TEXT,
            has_native_text=True,
            native_text_char_count=120,
        )
    )
    assert decision.eligible is False
    assert decision.reasons == ()
    assert decision.skip_reason == svr.SKIP_NATIVE_TEXT_PRIMARY


@pytest.mark.parametrize(
    "route",
    [ExtractionRoute.SOURCE_TEXT, ExtractionRoute.RENDERED_PDF_TEXT],
)
def test_source_text_and_rendered_pdf_text_also_skip_when_native_sufficient(route):
    decision = svr.assess_page_vision_eligibility(
        _signals(
            source_ref=f"src.{route.value}.p1",
            extraction_route=route,
            has_native_text=True,
            native_text_char_count=80,
        )
    )
    assert decision.eligible is False
    assert decision.skip_reason == svr.SKIP_NATIVE_TEXT_PRIMARY


def test_configured_vlm_does_not_force_review_on_clean_native_pages():
    decision = svr.assess_page_vision_eligibility(
        _signals(has_native_text=True, native_text_char_count=64),
        enabled=True,
    )
    assert decision.eligible is False
    assert decision.skip_reason == svr.SKIP_NATIVE_TEXT_PRIMARY


# ---------------------------------------------------------------------------
# Enter reasons: scan / table / structure anomaly / OCR quality
# ---------------------------------------------------------------------------


def test_scan_or_image_only_page_enters_vision_review():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            media_kind="image",
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
        )
    )
    assert decision.eligible is True
    assert svr.VISION_REASON_SCAN_OR_IMAGE_ONLY in decision.reasons


def test_vision_ocr_route_without_image_media_still_enters_as_scan():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            media_kind="pdf",
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
        )
    )
    assert decision.eligible is True
    assert decision.reasons[0] == svr.VISION_REASON_SCAN_OR_IMAGE_ONLY


def test_complex_visual_table_enters_vision_review():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.NATIVE_PDF_TEXT,
            has_native_text=True,
            native_text_char_count=40,
            complex_layout_not_represented_by_native_text=True,
        )
    )
    assert decision.eligible is True
    assert svr.VISION_REASON_COMPLEX_VISUAL_OR_TABLE in decision.reasons


def test_infer_complex_layout_helper_is_content_neutral():
    assert (
        svr.infer_complex_layout_not_represented(
            has_ruled_table=True,
            has_native_text=False,
            native_text_char_count=0,
        )
        is True
    )
    assert (
        svr.infer_complex_layout_not_represented(
            has_ruled_table=True,
            has_native_text=True,
            native_text_char_count=64,
        )
        is False
    )
    assert (
        svr.infer_complex_layout_not_represented(
            layout_block_count=12,
            has_native_text=False,
            native_text_char_count=0,
        )
        is True
    )


def test_native_structure_anomaly_enters_vision_review():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
            page_artifact_status=PageArtifactStatus.DEGRADED,
            native_extraction_anomaly=True,
        )
    )
    assert decision.eligible is True
    assert svr.VISION_REASON_NATIVE_EXTRACTION_ANOMALY in decision.reasons


def test_insufficient_native_text_on_claimed_native_route_is_anomaly():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.NATIVE_PDF_TEXT,
            has_native_text=True,
            native_text_char_count=3,  # below NATIVE_TEXT_SUFFICIENT_CHARS
        )
    )
    assert decision.eligible is True
    assert svr.VISION_REASON_NATIVE_EXTRACTION_ANOMALY in decision.reasons


def test_ocr_low_confidence_enters_vision_review():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
            ocr_confidence=0.42,
            ocr_risk_kinds=(OcrRiskKind.LOW_CONFIDENCE.value,),
        ),
        ocr_confidence_threshold=0.80,
    )
    assert decision.eligible is True
    assert svr.VISION_REASON_OCR_EVIDENCE_RISK in decision.reasons


def test_informational_non_confidence_risk_alone_does_not_force_ocr_evidence_reason():
    """BLOCKING/other risks without low confidence are not auto-mapped in v1."""
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.NATIVE_PDF_TEXT,
            has_native_text=True,
            native_text_char_count=64,
            ocr_confidence=0.95,
            ocr_risk_kinds=(OcrRiskKind.REPEATED_TEXT.value,),
        ),
        ocr_confidence_threshold=0.80,
    )
    assert decision.eligible is False
    assert svr.VISION_REASON_OCR_EVIDENCE_RISK not in decision.reasons
    assert decision.skip_reason == svr.SKIP_NATIVE_TEXT_PRIMARY


def test_reasons_are_stable_and_deduplicated_when_multiple_signals_fire():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            media_kind="tiff",
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
            native_extraction_anomaly=True,
            complex_layout_not_represented_by_native_text=True,
            ocr_confidence=0.10,
            ocr_risk_kinds=(OcrRiskKind.LOW_CONFIDENCE.value,),
        )
    )
    assert decision.eligible is True
    assert decision.reasons == (
        svr.VISION_REASON_SCAN_OR_IMAGE_ONLY,
        svr.VISION_REASON_COMPLEX_VISUAL_OR_TABLE,
        svr.VISION_REASON_NATIVE_EXTRACTION_ANOMALY,
        svr.VISION_REASON_OCR_EVIDENCE_RISK,
    )
    assert set(decision.reasons) <= EXPECTED_REASON_CODES


# ---------------------------------------------------------------------------
# Explicit closed / skip states (not silent “reviewed”)
# ---------------------------------------------------------------------------


def test_disabled_flag_skips_without_pretending_reviewed():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
        ),
        enabled=False,
    )
    assert decision.eligible is False
    assert decision.skip_reason == svr.SKIP_SELECTIVE_VISION_DISABLED


def test_eligible_page_without_page_image_does_not_pretend_reviewed():
    decision = svr.assess_page_vision_eligibility(
        _signals(
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
            has_page_image=False,
        )
    )
    assert decision.eligible is False
    assert decision.skip_reason == svr.SKIP_MISSING_PAGE_IMAGE


def test_call_size_limit_keeps_all_eligible_pages_for_chunking():
    pages = [
        _signals(
            source_ref=f"src.scan.p{i}",
            page_ordinal=i,
            media_kind="image",
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
        )
        for i in range(1, 5)
    ]
    plan = svr.plan_selective_vision_reviews(pages, max_pages_per_call=2)
    assert len(plan.eligible) == 4
    assert len(plan.skipped) == 0
    assert plan.max_pages_per_call == 2
    assert all(item.reasons for item in plan.eligible)


def test_duplicate_page_identity_is_rejected():
    page = _signals(
        source_ref="src.scan.p1",
        page_ordinal=1,
        media_kind="image",
        extraction_route=ExtractionRoute.VISION_OCR,
        has_native_text=False,
        native_text_char_count=0,
    )
    with pytest.raises(ValueError, match="页面来源标识重复"):
        svr.plan_selective_vision_reviews([page, page], max_pages_per_call=2)


# ---------------------------------------------------------------------------
# Fail-closed adapter + source fidelity
# ---------------------------------------------------------------------------


def test_provider_balance_failure_is_fail_closed_without_ocr_or_semantic_fallback(
    monkeypatch,
):
    async def _boom(*args, **kwargs):
        raise vlm.IndependentVlmBalanceError(
            "余额不足 — Independent VLM disabled",
            provider_code="1113",
            status_code=429,
        )

    async def _ready():
        return True

    monkeypatch.setattr(svr, "independent_vlm_page_chat", _boom)
    monkeypatch.setattr(svr, "check_independent_vlm", _ready)

    signals = _signals(
        extraction_route=ExtractionRoute.VISION_OCR,
        has_native_text=False,
        native_text_char_count=0,
        media_kind="image",
    )
    plan = svr.plan_selective_vision_reviews([signals], max_pages_per_call=1)
    assert plan.eligible
    outcome = asyncio.run(
        svr.run_selective_vision_review(plan, [_page_input()])
    )
    assert outcome.ok is False
    assert outcome.disabled is True
    assert outcome.closed_error is not None
    assert isinstance(outcome.closed_error, svr.SelectiveVisionClosedError)
    assert outcome.closed_error.failure_kind == "balance_insufficient"
    assert outcome.observations == ()
    message = str(outcome.closed_error).lower()
    assert "mtplx" not in message
    assert "deepseek" not in message
    assert "omlx" not in message


def test_partial_page_inputs_fail_closed(monkeypatch):
    async def _ready():
        return True

    monkeypatch.setattr(svr, "check_independent_vlm", _ready)
    signals = [
        _signals(
            source_ref=f"src.scan.p{i}",
            page_ordinal=i,
            media_kind="image",
            extraction_route=ExtractionRoute.VISION_OCR,
            has_native_text=False,
            native_text_char_count=0,
        )
        for i in (1, 2)
    ]
    plan = svr.plan_selective_vision_reviews(signals, max_pages_per_call=2)
    outcome = asyncio.run(
        svr.run_selective_vision_review(
            plan,
            [_page_input(source_ref="src.scan.p1", page_ordinal=1)],
        )
    )
    assert outcome.ok is False
    assert outcome.disabled is True
    assert outcome.closed_error is not None
    assert outcome.closed_error.failure_kind == "missing_page_inputs"


def test_source_fidelity_error_surfaces_and_does_not_rewrite_ocr(monkeypatch):
    async def _forged(*args, **kwargs):
        raise vlm.IndependentVlmSourceFidelityError(
            "invented source_ref=body.forged"
        )

    async def _ready():
        return True

    monkeypatch.setattr(svr, "independent_vlm_page_chat", _forged)
    monkeypatch.setattr(svr, "check_independent_vlm", _ready)

    signals = _signals(
        source_ref="body.p803",
        extraction_route=ExtractionRoute.VISION_OCR,
        has_native_text=False,
        native_text_char_count=0,
        media_kind="image",
    )
    plan = svr.plan_selective_vision_reviews([signals], max_pages_per_call=1)
    outcome = asyncio.run(
        svr.run_selective_vision_review(
            plan,
            [_page_input(source_ref="body.p803")],
        )
    )
    assert outcome.ok is False
    assert outcome.closed_error is not None
    assert outcome.closed_error.failure_kind == "source_fidelity"
    assert "invented" in str(outcome.closed_error.cause)
    assert outcome.observations == ()


def test_successful_review_observation_preserves_source_ref_and_is_not_verdict(
    monkeypatch,
):
    async def _ok(prompt, pages, **kwargs):
        assert pages[0].source_ref == "body.p803"
        return vlm.IndependentVlmChatResult(
            text="observation only; source_ref=body.p803 page_ordinal=1",
            model="glm-5.3-flash",
            finish_reason="stop",
            usage={"total_tokens": 12},
            allowed_source_refs=("body.p803",),
        )

    async def _ready():
        return True

    monkeypatch.setattr(svr, "independent_vlm_page_chat", _ok)
    monkeypatch.setattr(svr, "check_independent_vlm", _ready)

    signals = _signals(
        source_ref="body.p803",
        extraction_route=ExtractionRoute.VISION_OCR,
        has_native_text=False,
        native_text_char_count=0,
        media_kind="image",
    )
    plan = svr.plan_selective_vision_reviews([signals], max_pages_per_call=1)
    outcome = asyncio.run(
        svr.run_selective_vision_review(
            plan,
            [_page_input(source_ref="body.p803")],
        )
    )
    assert outcome.ok is True
    assert len(outcome.observations) == 1
    obs = outcome.observations[0]
    assert obs.source_refs == ("body.p803",)
    assert "body.p803" in obs.text
    assert "入排通过" not in obs.text
    assert "入排失败" not in obs.text
    assert not hasattr(obs, "raw_text")


def test_select_page_inputs_for_plan_preserves_source_identity_order():
    plan = svr.plan_selective_vision_reviews(
        [
            _signals(
                source_ref="page.a",
                page_ordinal=1,
                media_kind="image",
                extraction_route=ExtractionRoute.VISION_OCR,
                has_native_text=False,
                native_text_char_count=0,
            ),
            _signals(
                source_ref="page.b",
                page_ordinal=2,
                media_kind="image",
                extraction_route=ExtractionRoute.VISION_OCR,
                has_native_text=False,
                native_text_char_count=0,
            ),
        ],
        max_pages_per_call=2,
    )
    selected = svr.select_page_inputs_for_plan(
        plan,
        [
            _page_input(source_ref="page.b", page_ordinal=2, image_bytes=b"b"),
            _page_input(source_ref="page.a", page_ordinal=1, image_bytes=b"a"),
            _page_input(source_ref="page.c", page_ordinal=3, image_bytes=b"c"),
        ],
    )
    assert [p.source_ref for p in selected] == ["page.b", "page.a"]


# ---------------------------------------------------------------------------
# Content-neutral / no project-specific hardcoding
# ---------------------------------------------------------------------------


def test_triage_signals_have_no_clinical_free_text_predicate_field():
    fields = set(svr.PageVisionTriageSignals.__dataclass_fields__)
    forbidden_fields = {
        "clinical_text",
        "page_text",
        "ocr_text",
        "disease",
        "drug",
        "study_id",
        "criterion",
        "visit",
        "score",
        "protocol_id",
    }
    assert forbidden_fields.isdisjoint(fields)


def test_module_source_has_no_project_specific_hardcoding():
    assert MODULE_PATH.is_file()
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source, f"forbidden token {token!r}"

    tree = ast.parse(source)
    string_consts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    joined = "\n".join(string_consts)
    for token in ("D001", "入排最终", "criteria_id=", "visit_window="):
        assert token not in joined


def test_prompts_reject_unknown_project_specific_reason_codes():
    with pytest.raises(ValueError, match="Unsupported vision risk reasons"):
        svr.build_selective_vision_prompts(reasons=["study_D001_gate"])


def test_planner_stays_isolated_from_ocr_executor_and_semantic_backends():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "evidence_processing_executor" not in source
    assert "omlx_gate" not in source
    assert "REVIEW_BACKEND" not in source
    assert "OCR_BACKEND" not in source
    assert "independent_vlm" in source


def test_ocr_risk_level_matrix_still_marks_low_confidence_informational():
    from app.evidence.risk import OCR_RISK_LEVEL_MATRIX

    assert OCR_RISK_LEVEL_MATRIX[OcrRiskKind.LOW_CONFIDENCE] == OcrRiskLevel.INFORMATIONAL
