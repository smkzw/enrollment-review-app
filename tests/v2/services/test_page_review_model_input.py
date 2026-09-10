from copy import deepcopy

from app.projections.page_review_model_input import compact_page_review_input


def test_projection_preserves_semantics_references_and_original():
    observation = {"raw_value": "0", "normalized_value": "0", "normalized_unit": "U/L",
                   "normalization_key": "audit-key", "region": {"excerpt": "X 0 U/L"},
                   "context": {"target_text": "X", "time_text": "2025-01-01", "polarity": "asserted"}}
    pending = {"page_review_id": "reader-B", "lane": "main-B", "page_artifact_id": "page",
               "source_document_version_id": "document", "page_number": 1,
               "use": "unresolved_only", "observation": observation,
               "text_anchor": {"source_layer": "effective_text", "text_start": 0, "text_end": 7,
                               "excerpt": "X 0 U/L", "source_text_sha256": "a" * 64}}
    source = {"accepted_pages": [{"page_number": 1, "accepted_facts": [observation],
              "accepted_clause_signals": [], "accepted_handwriting": [],
              "accepted_observations": [{"source_observation_ref": "stable-ref", "kind": "facts",
                                          "observation": observation}],
              "pending_observations": [pending], "signal_conflicts": [{"reason": "retain"}]}]}
    before = deepcopy(source)
    projected = compact_page_review_input(source)["accepted_pages"][0]
    assert source == before
    assert "accepted_facts" not in projected
    accepted = projected["accepted_observations"][0]
    assert accepted["source_observation_ref"] == "stable-ref"
    assert accepted["observation"] == {k: v for k, v in observation.items() if k != "normalization_key"}
    assert projected["pending_use"] == "unresolved_only"
    assert projected["pending_source_document_version_id"] == "document"
    group = projected["pending_observation_groups"][0]
    pending_detail = {**group["shared"], **group["observations"][0]["detail"]}
    assert pending_detail["text_anchor"] == {
        "source_layer": "effective_text", "text_start": 0, "text_end": 7}
    assert pending_detail["observation"] == {
        "raw_value": "0", "region": {"excerpt": "X 0 U/L"}, "context": observation["context"]}
    assert projected["signal_conflicts"] == [{"reason": "retain"}]


def test_pending_handwriting_retains_original_and_disagreement_without_normalized_value():
    pending = {"page_review_id": "reader-C", "lane": "handwriting-C", "kind": "handwriting",
               "page_artifact_id": "page", "source_document_version_id": "document", "page_number": 1,
               "use": "unresolved_only", "review_status": "association_pending",
               "review_message": "手写内容及所指对象尚待核对", "text_anchor": None,
               "observation": {"observation_id": "note", "kind": "cs_ncs_judgment",
                               "raw_text": "NCS?", "normalized_text": "ncs?", "normalization_key": "key",
                               "region": {"excerpt": "NCS? 签名", "bbox": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}},
                               "context": {"target_text": "检查", "polarity": "uncertain"}}}
    source = {"accepted_pages": [{"accepted_observations": [], "pending_observations": [pending]}]}
    before = deepcopy(source)
    group = compact_page_review_input(source)["accepted_pages"][0]["pending_observation_groups"][0]
    result = {**group["shared"], **group["observations"][0]["detail"]}
    assert source == before
    assert result["observation"]["raw_text"] == "NCS?"
    assert result["observation"]["context"]["polarity"] == "uncertain"
    assert result["review_status"] == "association_pending"
    assert result["observation"]["region"] == {"excerpt": "NCS? 签名"}
    assert "normalized_text" not in result["observation"]
