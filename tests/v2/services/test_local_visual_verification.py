"""Local source checks must not certify page coverage or clinical facts."""

import asyncio
import io
import json
from hashlib import sha256

import pytest
from PIL import Image

from app.domain.contracts.evidence import BoundingBox
from app.evidence.artifacts import ArtifactStore
from app.evidence.reading_view import ReadingRegion, make_focus_reading_image, make_reading_region, make_reading_view
from app.llm.independent_vlm import IndependentVlmChatResult, IndependentVlmSourceFidelityError
from app.services.selective_vision_observation_service import SelectiveVisionObservationService
from app.services.selective_vision_postprocess_executor import load_selective_vision_page_materials_for_revision
from app.storage.selective_vision_observation_repository import SelectiveVisionObservationRepository
from tests.v2.services.test_selective_vision_postfreeze_orchestration import _seed_frozen_revision


def _image(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (80, 60), color).save(out, format="PNG")
    return out.getvalue()


@pytest.mark.parametrize("angle,expected", [
    (0, (10, 5, 40, 25)), (90, (5, 20, 25, 50)),
    (180, (40, 35, 70, 55)), (270, (55, 10, 75, 40)),
])
def test_region_maps_pixel_edges_to_original(angle, expected):
    image = _image()
    view = make_reading_view(image, source_page_artifact_id="page",
                             source_image_sha256=sha256(image).hexdigest(), clockwise_degrees=angle)
    region = make_reading_region(view, BoundingBox(x0=10, y0=5, x1=40, y1=25))
    assert tuple(region.identity()["source_bbox"][k] for k in ("x0", "y0", "x1", "y1")) == expected
    assert region.identity()["coverage_scope"] == "region_only"
    with Image.open(io.BytesIO(region.image_bytes)) as cropped:
        assert cropped.size == (30, 20)


def test_region_rejects_fractional_edges_outside_page_and_forged_pixels():
    image = _image()
    view = make_reading_view(image, source_page_artifact_id="page",
                             source_image_sha256=sha256(image).hexdigest(), clockwise_degrees=0)
    with pytest.raises(ValueError, match="整数"):
        make_reading_region(view, BoundingBox(x0=1.5, y0=2, x1=20, y1=20))
    with pytest.raises(ValueError, match="超出"):
        make_reading_region(view, BoundingBox(x0=1, y0=2, x1=81, y1=20))
    other = make_reading_view(_image("black"), source_page_artifact_id="other",
                              source_image_sha256=sha256(_image("black")).hexdigest(), clockwise_degrees=0)
    box = BoundingBox(x0=1, y0=2, x1=20, y1=20)
    forged = make_reading_region(other, box)
    with pytest.raises(ValueError, match="像素"):
        ReadingRegion(view, box, forged.image_bytes)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA"])
@pytest.mark.parametrize("edges", [(10, 5, 40, 25), (0, 0, 40, 25), (10, 5, 80, 60)])
def test_focus_frame_preserves_target_and_size(mode, edges):
    source = Image.new(mode, (80, 60), {"RGB": (41, 61, 91), "RGBA": (41, 61, 91, 127), "L": 91, "LA": (91, 127)}[mode])
    raw = io.BytesIO()
    source.save(raw, "PNG")
    original = raw.getvalue()
    marked = make_focus_reading_image(original, BoundingBox(**dict(zip(("x0", "y0", "x1", "y1"), edges))))
    with Image.open(io.BytesIO(marked)) as actual:
        assert actual.size == source.size
        assert actual.crop(edges).tobytes() == source.convert(actual.mode).crop(edges).tobytes()
        color = (220, 30, 30, 255) if actual.mode == "RGBA" else (220, 30, 30)
        assert any(actual.getpixel((x, y)) == color for x in range(actual.width) for y in range(actual.height))
    assert raw.getvalue() == original
    assert marked == make_focus_reading_image(original, BoundingBox(**dict(zip(("x0", "y0", "x1", "y1"), edges))))


def test_focus_frame_rejects_fractional_or_outside_target():
    for box in (BoundingBox(x0=1.5, y0=1, x1=20, y1=20), BoundingBox(x0=1, y0=1, x1=81, y1=20), BoundingBox(x0=0, y0=0, x1=80, y1=60)):
        with pytest.raises(ValueError):
            make_focus_reading_image(_image(), box)


@pytest.mark.parametrize("finish,source_error,status", [
    ("stop", False, "read"), ("length", False, "failed"), ("stop", True, "failed"),
])
def test_local_receipt_is_not_page_observation_or_human_approval(
    session_factory, data_paths, monkeypatch, finish, source_error, status,
):
    store = ArtifactStore(data_paths)
    _seed_frozen_revision(session_factory, data_paths, revision_id="local-base", image_bytes=_image())
    with session_factory() as session:
        page = load_selective_vision_page_materials_for_revision(
            session, evidence_processing_revision_id="local-base", artifact_store=store,
        )[0]
    calls = []

    async def chat(prompt, pages, **kwargs):
        calls.append((prompt, pages, kwargs))
        response = IndependentVlmChatResult(
            text=f"source_ref={pages[0].source_ref}\n手写字母辨认不清。",
            model="fixture-model", finish_reason=finish,
            usage={"completion_tokens": 21, "api_key": "not-stored"},
            reasoning_content="private-thought-not-stored",
            reported_model="provider-fixture", response_id="response-fixture", request_id="request-fixture",
        )
        if source_error:
            raise IndependentVlmSourceFidelityError("wrong source", rejected_response=response)
        return response

    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", chat)
    service = SelectiveVisionObservationService(session_factory, default_model_id="fixture-model")
    receipt = asyncio.run(service.verify_local_region(
        page, base_processing_revision_id="local-base", view_bbox=BoundingBox(x0=2, y0=3, x1=20, y1=25),
        clockwise_degrees=0, artifact_store=store, max_tokens=65536, reasoning_effort="high",
    ))
    payload = json.loads(store.read(receipt.storage_ref))
    assert payload["status"] == status
    assert payload["coverage_scope"] == "region_only" and payload["candidate_only"] is True
    assert payload["region_source_ref"] != page.source_ref
    assert payload["requested_max_tokens"] == 65536
    assert payload["usage"] == {"completion_tokens": 21}
    assert payload["reported_model"] == "provider-fixture"
    assert payload["response_id"] == "response-fixture"
    assert payload["request_id"] == "request-fixture"
    assert "private-thought" not in json.dumps(payload)
    assert "api_key" not in json.dumps(payload)
    assert "没有研究者判断" in calls[0][0]
    with session_factory() as session:
        assert not SelectiveVisionObservationRepository(session).list_by_page_artifact(page.page_artifact_id)
    assert sha256(store.read(payload["image_artifact_ref"])).hexdigest() == payload["region"]["region_image_sha256"]

    with pytest.raises(Exception, match="超出指定资料版本"):
        asyncio.run(service.verify_local_region(
            page.__class__(**{**page.__dict__, "page_artifact_id": "out-of-scope"}),
            base_processing_revision_id="local-base", view_bbox=BoundingBox(x0=2, y0=3, x1=20, y1=25),
            clockwise_degrees=0, artifact_store=store,
        ))
    assert len(calls) == 1
