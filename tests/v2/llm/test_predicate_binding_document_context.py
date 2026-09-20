"""Source metadata is frozen context, never a clinical acceptance shortcut."""

import pytest
from pydantic import ValidationError

from app.domain.contracts.predicate_binding import (
    FrozenSourceDocumentIdentity, PredicateBindingFrozenInput,
    predicate_binding_frozen_input_sha256,
)
from app.llm.predicate_binding_candidates import predicate_binding_prompt_input
from tests.v2.llm.test_predicate_binding_candidates import _case


def _with_documents():
    frozen = _case()[0]
    documents = [FrozenSourceDocumentIdentity(
        source_document_version_id=key, source_blob_sha256="b" * 64,
        file_name="来源说明.pdf", media_type="application/pdf",
    ) for key in sorted({item.source_document_version_id for item in frozen.locators})]
    fields = dict(authority=frozen.authority, episode=frozen.episode,
                  rule_set_id=frozen.rule_set_id, rule_set_revision=frozen.rule_set_revision,
                  protocol_version_id=frozen.protocol_version_id, study_phase=frozen.study_phase,
                  components=frozen.components, facts=frozen.facts, locators=frozen.locators,
                  documents=documents)
    return PredicateBindingFrozenInput(
        **fields, binding_input_version="predicate-binding-frozen-input/v2",
        frozen_input_sha256=predicate_binding_frozen_input_sha256(**fields))


def test_legacy_input_preserves_its_content_identity_without_document_inference():
    old = _case()[0]
    payload = old.model_dump(mode="json", exclude={"documents"})
    restored = PredicateBindingFrozenInput.model_validate(payload)
    assert restored.documents is None
    assert restored.frozen_input_sha256 == old.frozen_input_sha256
    assert restored.model_dump(mode="json", exclude={"documents"}) == payload
    assert predicate_binding_prompt_input(restored)["documents"] is None


@pytest.mark.parametrize("field,value", [
    ("file_name", "另一份病历.pdf"), ("media_type", "text/plain"),
    ("source_blob_sha256", "c" * 64),
])
def test_metadata_change_invalidates_frozen_identity(field, value):
    payload = _with_documents().model_dump(mode="json")
    payload["documents"][0][field] = value
    with pytest.raises(ValidationError, match="哈希"):
        PredicateBindingFrozenInput.model_validate(payload)


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "wrong_version"])
def test_document_context_rejects_incomplete_or_unrelated_source_list(change):
    payload = _with_documents().model_dump(mode="json")
    if change == "missing":
        payload["documents"] = []
    elif change == "duplicate":
        payload["documents"].append(payload["documents"][0].copy())
    elif change == "extra":
        payload["documents"].append({**payload["documents"][0], "source_document_version_id": "other"})
    else:
        payload["binding_input_version"] = "predicate-binding-frozen-input/v1"
    with pytest.raises(ValidationError):
        PredicateBindingFrozenInput.model_validate(payload)


def test_prompt_carries_filename_and_media_type_without_changing_facts():
    frozen = _with_documents()
    prompt = predicate_binding_prompt_input(frozen)
    rows = [dict(zip(prompt["documents"]["columns"], row)) for row in prompt["documents"]["rows"]]
    assert rows == [{"source_document_version_id": item.source_document_version_id,
                     "file_name": item.file_name, "media_type": item.media_type}
                    for item in frozen.documents]
    assert prompt["facts"] == predicate_binding_prompt_input(_case()[0])["facts"]
