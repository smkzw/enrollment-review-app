"""Replay a frozen product request with one explicit decoding intervention."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

import jsonschema

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageReaderRoute
from scripts.qwen_platform_measurement import MeasuredCompletion, save
from app.llm.json_missing_fields_repair import completion_messages, merge_completion


def validate_product_wire(value):
    if isinstance(value, dict) and value.get("wire_version") == "dnf-v1":
        from app.agents.protocol_deconstructor import _parse_semantic_candidate, _parse_semantic_repair
        parser = _parse_semantic_repair if "replacement_rules" in value else _parse_semantic_candidate
        parser(json.dumps(value, ensure_ascii=False), compact=True)


async def main(args):
    original = args.request.read_bytes()
    body = json.loads(original)
    thinking_budget = getattr(args, "thinking_budget", None)
    if thinking_budget is not None:
        if args.provider != "omlx" or not 0 < thinking_budget <= body["max_tokens"]:
            raise ValueError("Explicit thinking budget requires oMLX and must fit shared output budget")
        body["thinking_budget"] = thinking_budget
    if getattr(args, "model", None):
        body["model"] = args.model
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "diagnostic.json", {
        "source_request": str(args.request.resolve()),
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "intervention": {"generation_mode": args.generation_mode,
                         "thinking_budget": thinking_budget,
                         "runtime_note": args.runtime_note,
                         "response_format": args.response_format,
                         "schema_in_prompt": args.schema_in_prompt,
                         "complete_response": str(args.complete_response) if args.complete_response else None},
        "clinical_acceptance": False,
        "ranking_eligible": False,
    })
    schema = body.get("response_format", {}).get("json_schema", {}).get("schema")
    if getattr(args, "whole_string_patterns", False):
        def replace_patterns(value):
            if isinstance(value, dict):
                if value.get("pattern") == r"\S":
                    value["pattern"] = r"^[\s\S]*\S[\s\S]*$"
                for child in value.values():
                    replace_patterns(child)
            elif isinstance(value, list):
                for child in value:
                    replace_patterns(child)
        replace_patterns(schema)
        save(args.output / "schema_intervention.json", {
            "mode": "equivalent_nonblank_whole_string_pattern", "ranking_eligible": False})
    if args.response_format == "json_object":
        body["response_format"] = {"type": "json_object"}
    if getattr(args, "omlx_pattern_compat", False):
        from app.llm.omlx_schema_compat import decoding_response_format
        if args.provider != "omlx":
            raise ValueError("oMLX schema compatibility requires oMLX")
        body["response_format"] = decoding_response_format(body["response_format"])
        save(args.output / "decoding_intervention.json", {
            "mode": "product_omlx_nonblank_compat", "authoritative_validation_retained": True})
    route = PageReaderRoute(PageReviewLane.MAIN_A, args.provider, args.url,
                            "local-benchmark", body.pop("model"),
                            body.pop("reasoning_effort"), body["max_tokens"], 1)
    messages, budget = body.pop("messages"), body.pop("max_tokens")
    if getattr(args, "current_protocol_contract", False):
        from app.agents.protocol_deconstructor import _SYSTEM_CONTRACT

        start = _SYSTEM_CONTRACT[:30]
        end = _SYSTEM_CONTRACT[-40:]
        matches = 0
        for message in messages:
            content = message.get("content")
            if not isinstance(content, str) or start not in content:
                continue
            begin = content.index(start)
            finish = content.index(end, begin) + len(end)
            message["content"] = content[:begin] + _SYSTEM_CONTRACT + content[finish:]
            matches += 1
        if matches != 1:
            raise ValueError("Expected one frozen protocol contract to replace")
        save(args.output / "prompt_intervention.json", {
            "contract_sha256": hashlib.sha256(_SYSTEM_CONTRACT.encode()).hexdigest(),
            "mode": "current_product_contract", "ranking_eligible": False})
    previous = None
    if getattr(args, "current_wire_contract", False):
        from app.agents.protocol_deconstructor import _COMPACT_WIRE_COMPONENT_CONTRACT
        contract = _COMPACT_WIRE_COMPONENT_CONTRACT
        matches = 0
        for message in messages:
            content = message.get("content")
            if not isinstance(content, str) or contract[:30] not in content:
                continue
            begin = content.index(contract[:30])
            finish = content.index(contract[-40:], begin) + 40
            message["content"] = content[:begin] + contract + content[finish:]
            matches += 1
        if matches != 1:
            raise ValueError("Expected one frozen compact contract to replace")
        save(args.output / "wire_prompt_intervention.json", {
            "contract_sha256": hashlib.sha256(contract.encode()).hexdigest(),
            "ranking_eligible": False})
    if getattr(args, "repair_response", None):
        if args.complete_response:
            raise ValueError("Choose completion or product schema repair, not both")
        from app.agents.protocol_deconstructor import _batch_schema_repair_prompt

        prior = json.loads(args.repair_response.read_bytes())
        value = json.loads(prior["text"])
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(value))
        wire_problem = None
        if not errors:
            try:
                validate_product_wire(value)
            except ValueError as exc:
                wire_problem = str(exc)
            if wire_problem is None:
                raise ValueError("Schema repair requires actual validation errors")
        codes = schema["properties"]["proposed_rules"]["items"]["properties"]["official_code"]["enum"]
        problem = wire_problem or "; ".join(f"{list(e.absolute_path)}: {e.validator} {e.validator_value}" for e in errors)
        messages.extend([{"role": "assistant", "content": prior["text"]},
                         {"role": "user", "content": _batch_schema_repair_prompt(
                             codes, candidate_id=value.get("candidate_id"),
                             agent_call_id=value.get("created_by_agent_call_id"),
                             batch_id=value.get("batch_id"), problem=problem, compact=True)}])
        save(args.output / "repair_source.json", {
            "source_sha256": hashlib.sha256(args.repair_response.read_bytes()).hexdigest(),
            "validator_errors": problem, "strategy": "product_batch_schema_repair"})
    if args.complete_response:
        previous_bytes = args.complete_response.read_bytes()
        previous = json.loads(json.loads(previous_bytes)["text"])
        messages = completion_messages(messages, previous, schema)
        body["response_format"] = {"type": "json_object"}
        save(args.output / "completion_source.json", {
            "path": str(args.complete_response.resolve()),
            "sha256": hashlib.sha256(previous_bytes).hexdigest()})
    if args.schema_in_prompt:
        if not schema:
            raise ValueError("Original request has no schema to preserve")
        messages = [*messages, {"role": "user", "content":
            "输出必须完整满足以下原始JSON Schema；它只规定格式，不增加或改变任何临床要求。"
            "只输出一个JSON对象，不附加解释。\n" + json.dumps(schema, ensure_ascii=False)}]
    if args.generation_mode:
        if args.provider != "mtplx":
            raise ValueError("generation_mode intervention requires MTPLX")
        body["generation_mode"] = args.generation_mode
    meter = MeasuredCompletion(args.output, args.tokenizer)
    try:
        result = await meter(route, messages, budget, body)
        status = {"state": "completed", "finish_reason": result.finish_reason,
                  "content_characters": len(result.text), "clinical_acceptance": False,
                  "completion_merged": False, "fields_added": [],
                  "semantic_verification": "not_performed"}
        parsed = json.loads(result.text)
        if previous is not None and result.finish_reason == "stop":
            parsed = merge_completion(previous, parsed, schema)
            save(args.output / "completed_object.json", parsed)
            status["completion_merged"] = True
            status["fields_added"] = sorted(set(parsed) - set(previous))
        if schema:
            jsonschema.validate(parsed, schema)
        validate_product_wire(parsed)
        status["product_wire_validated"] = isinstance(parsed, dict) and parsed.get("wire_version") == "dnf-v1"
        status["original_schema_valid"] = bool(schema)
        if result.finish_reason != "stop":
            status["state"] = "incomplete"
    except Exception as exc:
        status = {"state": "failed", "error_type": type(exc).__name__,
                  "detail": str(exc)[:500],
                  "clinical_acceptance": False}
    save(args.output / "status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--generation-mode", choices=["ar", "mtp"])
    parser.add_argument("--provider", choices=["mtplx", "mlx-serve", "omlx"], default="mtplx")
    parser.add_argument("--url", default="http://127.0.0.1:8002/v1")
    parser.add_argument("--runtime-note", default="")
    parser.add_argument("--response-format", choices=["original", "json_object"], default="original")
    parser.add_argument("--schema-in-prompt", action="store_true")
    parser.add_argument("--complete-response", type=Path)
    parser.add_argument("--current-protocol-contract", action="store_true")
    parser.add_argument("--repair-response", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--thinking-budget", type=int)
    parser.add_argument("--whole-string-patterns", action="store_true")
    parser.add_argument("--omlx-pattern-compat", action="store_true")
    parser.add_argument("--current-wire-contract", action="store_true")
    asyncio.run(main(parser.parse_args()))
