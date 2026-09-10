import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts import qwen_request_diagnostic as diagnostic


@pytest.mark.parametrize("text,expected", [(' {"value": 1}', "completed"), ('{"value":"wrong"}', "failed")])
@pytest.mark.parametrize("schema_prompt", [False, True])
@pytest.mark.parametrize("thinking_budget", [None, 131072])
def test_frozen_request_and_original_schema(tmp_path, monkeypatch, text, expected, schema_prompt, thinking_budget):
    body = {"model": "test", "reasoning_effort": "medium", "max_tokens": 131072,
            "messages": [{"role": "user", "content": "unchanged"}],
            "response_format": {"type": "json_schema", "json_schema": {"schema": {
                "type": "object", "required": ["value"],
                "properties": {"value": {"type": "integer"}}, "additionalProperties": False}}}}
    source = tmp_path / "frozen.json"
    source.write_text(json.dumps(body))
    original = source.read_bytes()

    class Meter:
        def __init__(self, *args):
            pass

        async def __call__(self, route, messages, budget, options):
            assert route.provider == ("omlx" if thinking_budget else "mlx-serve")
            assert options.get("thinking_budget") == thinking_budget
            assert messages[:1] == body["messages"]
            if schema_prompt:
                assert json.dumps(body["response_format"]["json_schema"]["schema"], ensure_ascii=False) in messages[-1]["content"]
            else:
                assert len(messages) == 1
            assert budget == 131072
            assert options["response_format"] == ({"type": "json_object"} if schema_prompt else body["response_format"])
            assert "generation_mode" not in options
            return SimpleNamespace(text=text, finish_reason="stop")

    monkeypatch.setattr(diagnostic, "MeasuredCompletion", Meter)
    args = SimpleNamespace(request=source, output=tmp_path / "out", tokenizer=tmp_path,
                           provider="omlx" if thinking_budget else "mlx-serve", thinking_budget=thinking_budget, url="http://localhost:11234/v1",
                           generation_mode=None, runtime_note="PLD off",
                           response_format="json_object" if schema_prompt else "original", schema_in_prompt=schema_prompt,
                           complete_response=None)
    asyncio.run(diagnostic.main(args))
    assert json.loads((args.output / "status.json").read_text())["state"] == expected
    assert source.read_bytes() == original


def test_truncated_completion_never_creates_merged_artifact(tmp_path, monkeypatch):
    schema = {"type": "object", "properties": {"a": {"type": "integer"},
              "b": {"type": "integer"}}, "required": ["a", "b"],
              "additionalProperties": False}
    source = tmp_path / "request.json"
    source.write_text(json.dumps({"model": "test", "reasoning_effort": "medium",
        "max_tokens": 131072, "messages": [], "response_format": {
            "type": "json_schema", "json_schema": {"schema": schema}}}))
    previous = tmp_path / "response.json"
    previous.write_text(json.dumps({"text": '{"a":1}'}))

    class Meter:
        def __init__(self, *args):
            pass

        async def __call__(self, *args):
            return SimpleNamespace(text='{"b":2}', finish_reason="length")

    monkeypatch.setattr(diagnostic, "MeasuredCompletion", Meter)
    args = SimpleNamespace(request=source, output=tmp_path / "out", tokenizer=tmp_path,
        provider="mlx-serve", url="http://localhost:11234/v1", generation_mode=None,
        runtime_note="", response_format="original", schema_in_prompt=False,
        complete_response=previous)
    asyncio.run(diagnostic.main(args))
    assert not (args.output / "completed_object.json").exists()
    assert json.loads((args.output / "status.json").read_text())["state"] != "completed"


@pytest.mark.parametrize("provider,budget", [("omlx", 0), ("omlx", 131073), ("mtplx", 131072)])
def test_invalid_thinking_override_rejected_before_artifacts(tmp_path, provider, budget):
    source = tmp_path / "request.json"
    source.write_text(json.dumps({"max_tokens": 131072}))
    args = SimpleNamespace(request=source, output=tmp_path / "out",
                           provider=provider, thinking_budget=budget)
    with pytest.raises(ValueError, match="Explicit thinking budget"):
        asyncio.run(diagnostic.main(args))
    assert not args.output.exists()


def test_contract_refresh_preserves_source_and_uses_both_product_contracts(tmp_path, monkeypatch):
    from app.agents.protocol_deconstructor import _SYSTEM_CONTRACT, _COMPACT_WIRE_COMPONENT_CONTRACT
    contracts = [_SYSTEM_CONTRACT, _COMPACT_WIRE_COMPONENT_CONTRACT]
    frozen_text = "SOURCE BEFORE\n" + "\n".join(
        c[:30] + "OLD MIDDLE" + c[-40:] for c in contracts) + "\nSOURCE AFTER"
    body = {"model": "test", "reasoning_effort": "medium", "max_tokens": 131072,
            "messages": [{"role": "user", "content": frozen_text}]}
    source = tmp_path / "request.json"
    source.write_text(json.dumps(body))
    original = source.read_bytes()

    class Meter:
        def __init__(self, *args):
            pass

        async def __call__(self, route, messages, budget, options):
            assert messages[0]["content"] == "SOURCE BEFORE\n" + "\n".join(contracts) + "\nSOURCE AFTER"
            return SimpleNamespace(text="{}", finish_reason="stop")

    monkeypatch.setattr(diagnostic, "MeasuredCompletion", Meter)
    args = SimpleNamespace(request=source, output=tmp_path / "out", tokenizer=tmp_path,
        provider="omlx", url="http://localhost/v1", generation_mode=None,
        runtime_note="", response_format="original", schema_in_prompt=False,
        complete_response=None, current_protocol_contract=True, current_wire_contract=True)
    asyncio.run(diagnostic.main(args))
    assert source.read_bytes() == original


def test_product_wire_validation_is_not_replaced_by_schema_success(monkeypatch):
    from app.agents import protocol_deconstructor

    def reject(text, *, compact):
        assert compact is True
        raise ValueError("DNF_WIRE_DUPLICATE_ATOM")

    monkeypatch.setattr(protocol_deconstructor, "_parse_semantic_candidate", reject)
    with pytest.raises(ValueError, match="DNF_WIRE_DUPLICATE_ATOM"):
        diagnostic.validate_product_wire({"wire_version": "dnf-v1", "proposed_rules": []})
    diagnostic.validate_product_wire({"unrelated": "schema"})
