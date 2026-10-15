"""Opt-in context-order experiment; does not change the default reader."""

from copy import deepcopy
import hashlib
import json

from app.llm.page_review_harness import direct_completion, read_page

LAYOUT_VERSION = "stable-prefix/v1"
SOURCE_READING_VERSION = "source-reading/v1"


def stable_prefix_messages(messages):
    result = deepcopy(messages)
    parts = result[1]["content"]
    texts = [part for part in parts if part["type"] == "text"]
    if len(texts) != 1:
        raise ValueError("Expected exactly one page input object")
    payload = json.loads(texts[0]["text"])
    ordered = {key: payload[key] for key in ("clause_pack", "output_schema") if key in payload}
    ordered.update({key: value for key, value in payload.items() if key not in ordered})
    texts[0]["text"] = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    result[1]["content"] = texts + [part for part in parts if part["type"] != "text"]
    return result


def source_reading_messages(messages):
    """Experimental reading scope, not a lossless replacement for evaluator input."""
    result = deepcopy(messages)
    texts = [part for part in result[1]["content"] if part["type"] == "text"]
    if len(texts) != 1:
        raise ValueError("Expected exactly one page input object")
    payload = json.loads(texts[0]["text"])
    if "clause_pack" not in payload:
        raise ValueError("Source-reading experiment requires a main reading lane")
    for clause in payload["clause_pack"]["clauses"]:
        for field in ("expression", "exception_expression", "evidence_requirements"):
            clause.pop(field, None)
    texts[0]["text"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return result


async def _read_variant(route, page_input, clause_pack, *, completion, transform, layout_version):
    async def reordered_completion(active_route, messages, budget):
        return await completion(active_route, transform(messages), budget)

    record = await read_page(route, page_input, clause_pack, completion=reordered_completion)
    version = record.prompt_version + "+" + layout_version
    identity = hashlib.sha256((record.page_review_id + "|" + version).encode()).hexdigest()
    return record.model_copy(update={"prompt_version": version, "page_review_id": "page-review:" + identity[:32]})


async def read_page_stable_prefix(route, page_input, clause_pack, *, completion=direct_completion):
    return await _read_variant(route, page_input, clause_pack, completion=completion,
                               transform=stable_prefix_messages, layout_version=LAYOUT_VERSION)


async def read_page_source_reading(route, page_input, clause_pack, *, completion=direct_completion):
    return await _read_variant(route, page_input, clause_pack, completion=completion,
                               transform=source_reading_messages, layout_version=SOURCE_READING_VERSION)
