"""真实 oMLX 探针解析和坐标证据判定测试。"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from tests.v2.evidence.probe_omlx_glm import (
    _content,
    _has_machine_coordinates,
    _probe_succeeded,
)


def test_coordinate_detection_requires_numeric_payload() -> None:
    assert not _has_machine_coordinates({}, "纯文字 <|LOC_1|>")
    assert not _has_machine_coordinates({"layout": "plain text"}, "")
    assert not _has_machine_coordinates({}, "bbox: [1, 2]")
    assert _has_machine_coordinates({}, '{"bbox":[1,2,30,40]}')
    assert _has_machine_coordinates({"layout": [{"bbox": [1, 2, 30, 40]}]}, "")
    assert _has_machine_coordinates(
        {"choices": [{"message": {"layout": [{"bbox": [1, 2, 30, 40]}]}}]}, ""
    )
    assert _has_machine_coordinates({"bbox": {"x0": 1, "y0": 2, "x1": 30, "y1": 40}}, "")


def test_content_requires_a_string_chat_message() -> None:
    assert _content({"choices": [{"message": {"content": "识别文本"}}]}) == "识别文本"
    with pytest.raises(TypeError, match="字符串"):
        _content({"choices": [{"message": {"content": ["识别文本"]}}]})
    with pytest.raises(TypeError, match="choices"):
        _content({})


def test_probe_success_requires_exact_text_and_model_identity() -> None:
    summary = {
        "total_pages": 2,
        "raw_exact_pages": 2,
        "all_responses_successful": True,
        "all_response_models_match": True,
        "all_expected_fragments_found": True,
    }
    assert _probe_succeeded(summary)
    assert not _probe_succeeded({**summary, "all_response_models_match": False})
    assert not _probe_succeeded({**summary, "raw_exact_pages": 1})


def test_record_preserves_raw_response_and_model_identity() -> None:
    root = Path(__file__).resolve().parents[3]
    record_path = root / ".trellis/tasks/08-19-phase4-evidence-ocr-v2/research/slice4-real-omlx-probe.json"
    if not record_path.exists():
        pytest.skip("Slice 4.0 real probe artifact is not present")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["all_responses_successful"] is True
    assert record["all_response_models_match"] is True
    assert record["text_exact_pages"] == record["raw_exact_pages"] == record["total_pages"] == 2
    assert record["all_expected_fragments_found"] is True
    assert record["layout_coordinates_observed"] is False
    assert record["model_identity_evidence"]["independent_server_catalog_captured"] is False
    assert record["model_identity_evidence"]["independent_process_launch_log_captured"] is False
    assert record["gate"]["request_state"] == "released"
    assert record["gate"]["kind"] == "ocr"
    assert record["gate"]["model"] == record["model"]
    assert record["gate"]["owner"] == "phase4-evidence-ocr-v2"
    for page in record["pages"]:
        assert page["response_status"] == 200
        assert page["model_matches_request"] is True
        assert page["machine_coordinates_present"] is False
        assert page["exact_text"] is True
        assert len(page["expected_fragments_found"]) == page["expected_fragment_count"]
        assert page["finish_reason"] == "stop"
        raw = base64.b64decode(page["raw_response_base64"])
        assert hashlib.sha256(raw).hexdigest() == page["response_sha256"]
        parsed = json.loads(raw)
        assert parsed["model"] == record["model"] == page["response_model"]
        assert parsed["choices"][0]["message"]["content"] == page["recognized_text"]
