import json
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from app.llm.page_review_context_layout import stable_prefix_messages, read_page_stable_prefix
from app.llm.page_review_context_layout import source_reading_messages, read_page_source_reading


def test_stable_prefix_preserves_every_value_and_image_without_mutation():
    payload = {'page_number': 2, 'review_context': {'stage': 'screen'},
               'clause_pack': {'clauses': [{'source_text': 'exact source', 'value': 0}]},
               'output_schema': {'required': ['handwriting']}}
    messages = [{'role': 'system', 'content': 'unchanged'}, {'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}},
        {'type': 'text', 'text': json.dumps(payload)}]}]
    before = json.dumps(messages)
    result = stable_prefix_messages(messages)
    assert json.dumps(messages) == before
    assert result[0] == messages[0]
    assert result[1]['content'][1] == messages[1]['content'][0]
    decoded = json.loads(result[1]['content'][0]['text'])
    assert decoded == payload
    assert list(decoded)[:2] == ['clause_pack', 'output_schema']


def test_layout_variant_gets_distinct_repeatable_identity(monkeypatch):
    original = SimpleNamespace(prompt_version="original/v1", page_review_id="page-review:original")
    original.model_copy = Mock(side_effect=lambda *, update: SimpleNamespace(**update))

    async def baseline(*args, **kwargs):
        return original

    monkeypatch.setattr("app.llm.page_review_context_layout.read_page", baseline)
    first = asyncio.run(read_page_stable_prefix(None, None, None))
    second = asyncio.run(read_page_stable_prefix(None, None, None))
    assert first.page_review_id == second.page_review_id
    assert first.page_review_id != original.page_review_id
    assert first.prompt_version == "original/v1+stable-prefix/v1"
    assert original.prompt_version == "original/v1"


def test_source_reading_preserves_all_sources_and_only_removes_evaluator_fields():
    clause = {"clause_id": "component:EX-01:01", "title": "Original title",
              "source_text_ref": "source-1", "determination_mode": "deterministic",
              "expression": {"and": [1, 2]}, "exception_expression": {"or": [3]},
              "evidence_requirements": [{"due_stage": "baseline"}]}
    pack = {"clauses": [clause], "source_texts": {"source-1": "Exact original condition and exception"}}
    payload = {"clause_pack": pack, "review_context": {"stage": "screen"},
               "page_number": 4, "output_schema": {"required": ["handwriting"]}}
    messages = [{"role": "system", "content": "unchanged"}, {"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"type": "text", "text": json.dumps(payload)}]}]
    before = json.dumps(messages)
    output = source_reading_messages(messages)
    assert json.dumps(messages) == before
    assert output[0] == messages[0]
    assert output[1]["content"][0] == messages[1]["content"][0]
    expected = json.loads(json.dumps(payload))
    for name in ("expression", "exception_expression", "evidence_requirements"):
        del expected["clause_pack"]["clauses"][0][name]
    assert json.loads(output[1]["content"][1]["text"]) == expected
    # Smaller input is an experiment, not proof that clinical information is equivalent.
    assert len(output[1]["content"][1]["text"]) < len(messages[1]["content"][1]["text"])


def test_source_reading_rejects_handwriting_only_input():
    with pytest.raises(ValueError, match="main reading lane"):
        source_reading_messages([{}, {"content": [{"type": "text", "text": "{}"}]}])


def test_source_reading_has_its_own_identity(monkeypatch):
    original = SimpleNamespace(prompt_version="original/v1", page_review_id="page-review:original")
    original.model_copy = Mock(side_effect=lambda *, update: SimpleNamespace(**update))

    async def baseline(*args, **kwargs):
        return original

    monkeypatch.setattr("app.llm.page_review_context_layout.read_page", baseline)
    source = asyncio.run(read_page_source_reading(None, None, None))
    stable = asyncio.run(read_page_stable_prefix(None, None, None))
    assert source.prompt_version == "original/v1+source-reading/v1"
    assert source.page_review_id not in {stable.page_review_id, original.page_review_id}
