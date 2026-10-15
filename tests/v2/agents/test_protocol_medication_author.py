"""One local correction cannot rewrite successfully authored sibling requirements."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest

from app.agents import protocol_medication_author as author
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.rules import MedicationRestriction
from app.llm.page_review_harness import PageReaderRoute
from app.evidence.artifacts import ArtifactStore, ArtifactIntegrityError
from tests.v2.protocols.test_medication_restrictions import frozen_medications


def test_only_failed_item_is_reissued_and_valid_sibling_remains_identical(data_paths, monkeypatch):
    selection, view, proposal = frozen_medications()
    text = "筛选前2个月内禁止使用药物乙。"
    view["candidates"][0]["source_span_ids"].append("second")
    view["source_records"].append({"source_span_id": "second", "identity_status": "ok", "raw_text": text})
    sibling = deepcopy(proposal["medications"][0])
    sibling.update(drug_text="药物乙", exception_excerpt=None, source_quotes=[{"source_span_id": "second", "excerpt": text}],
        window={"anchor_type": "screening_date", "direction": "before", "upper_bound": {"value": 2, "unit": "month"}})
    proposal["medications"].append(sibling)
    correct = deepcopy(proposal["medications"][0])
    proposal["medications"][0]["window"]["upper_bound"]["value"] = 3
    monkeypatch.setattr(author, "medication_author_route", lambda: PageReaderRoute(PageReviewLane.MAIN_A,
        "fixture", "http://fixture.invalid/v1", "not-a-key", "fixture", "high", 65536, 1))
    calls = []

    async def completion(route, messages, budget):
        value = json.loads(messages[1]["content"])
        calls.append(value)
        if len(calls) == 1:
            output = proposal
        else:
            assert value["item_index"] == 0
            assert [row["source_span_id"] for row in value["sources"]] == ["clause"]
            assert "药物乙" not in json.dumps(messages, ensure_ascii=False)
            output = correct
        return SimpleNamespace(text=json.dumps(output), finish_reason="stop", usage={}, response_model="fixture",
            response_id="fixture-response", output_lengths={})

    result = asyncio.run(author.author_medications(view=view, selection=selection, phase="phase_iii",
        official_codes={"EX-01"}, data_paths=data_paths, completion=completion))
    assert len(calls) == 2 and result["system_issue"] is None
    stored = result["supplement"]["medications"][1]
    assert {key: value for key, value in stored.items() if key != "item_id"} == MedicationRestriction.model_validate(sibling).model_dump(mode="json")


@pytest.mark.parametrize("fault", [None, "source_changed", "repair_prompt", "response_mismatch", "corrupt"])
def test_revalidation_proves_initial_request_not_a_favorable_retry(data_paths, monkeypatch, fault):
    selection, view, proposal = frozen_medications()
    route = PageReaderRoute(PageReviewLane.MAIN_A, "fixture", "http://fixture.invalid/v1", "not-a-key", "fixture", "high", 65536, 1)
    monkeypatch.setattr(author, "medication_author_route", lambda: route)
    readable = author.selected_scope_material(view, selection)[2]
    request = {"messages": author.medication_messages(phase="phase_iii", official_codes={"EX-01"}, readable=readable),
        "provider": route.provider, "model": route.model, "effort": route.reasoning_effort,
        "max_tokens": route.max_tokens, "input_sha256": author.medication_input_hash("phase_iii", readable)}
    if fault == "repair_prompt": request["messages"].append({"role": "user", "content": "改正上次结果"})
    store = ArtifactStore(data_paths)
    request_ref = store.put("raw_request", json.dumps(request, ensure_ascii=False).encode()).storage_ref
    raw = {"request_ref": request_ref if fault != "response_mismatch" else "different", "finish_reason": "stop", "text": json.dumps(proposal)}
    response_ref = store.put("raw_response", json.dumps(raw).encode()).storage_ref
    if fault == "corrupt":
        # Only a fictional test artifact is corrupted; product records are immutable.
        (data_paths.root / response_ref).write_bytes(b"damaged")
    if fault == "source_changed": view["source_records"][1]["raw_text"] += "新的限定。"
    saved = {"receipts": [{"request_ref": request_ref, "response_ref": response_ref}]}
    kwargs = dict(view=view, selection=selection, phase="phase_iii", official_codes={"EX-01"}, data_paths=data_paths)
    if fault == "corrupt":
        with pytest.raises(ArtifactIntegrityError): author.revalidate_medication_result(saved, **kwargs)
        return
    result = author.revalidate_medication_result(saved, **kwargs)
    if fault:
        assert result["supplement"] is None
    else:
        assert result["supplement"] and result["supplement"]["reader_identity"] is None
        assert result["revalidation"]["endpoint_identity_recorded"] is False
