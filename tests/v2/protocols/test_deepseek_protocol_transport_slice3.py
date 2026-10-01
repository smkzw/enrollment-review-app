from __future__ import annotations

import hashlib
from types import SimpleNamespace

import httpx
import pytest

from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport
from app.agents.protocol_deconstructor import ProtocolAgentCallError
from app.llm import client as llm_client


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_formal_generation_requires_atomic_source(kind):
    import jsonschema
    from app.agents.protocol_deconstructor import protocol_output_response_format
    from app.llm.omlx_schema_compat import decoding_response_format
    schema = decoding_response_format(protocol_output_response_format(kind))["json_schema"]["schema"]
    validator = jsonschema.Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/AtomicPredicate"})
    atom = {"predicate_id": "p", "subject": "受试者", "attribute": "事件", "comparator": "exists"}
    assert not validator.is_valid(atom)
    assert not validator.is_valid({"source_clause": "存在事件"})
    assert not validator.is_valid({**atom, "source_clause": None, "source_clauses": []})
    assert validator.is_valid({**atom, "source_clause": "存在事件"})
    assert validator.is_valid({**atom, "source_clauses": ["存在事件"]})


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        if isinstance(output, tuple):
            content, finish_reason, reasoning_content = output
        else:
            content, finish_reason, reasoning_content = output, "stop", ""
        if kwargs.get("stream"):
            return iter([SimpleNamespace(
                choices=[SimpleNamespace(
                    finish_reason=finish_reason,
                    delta=SimpleNamespace(content=content, reasoning_content=reasoning_content),
                )],
            )])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(
                        content=content,
                        reasoning_content=reasoning_content,
                    ),
                )
            ]
        )


def _client(outputs):
    completions = FakeCompletions(outputs)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    ), completions


def test_transport_retains_full_same_session_history_and_max_reasoning():
    client, completions = _client(['{"draft":1}', '{"draft":2}'])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="deepseek",
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    first = transport.start(prompt="首轮完整输入")
    second = transport.continue_session(
        session_id=first.session_id, prompt="仅修正时间锚点"
    )

    assert second.session_id == first.session_id
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert completions.calls[1]["messages"][1]["content"] == '{"draft":1}'
    assert completions.calls[1]["reasoning_effort"] == "max"
    assert completions.calls[1]["extra_body"] == {"thinking": {"type": "enabled"}}
    assert completions.calls[1]["response_format"] == {"type": "json_object"}
    assert completions.calls[0]["max_tokens"] == 60000
    assert completions.calls[1]["max_tokens"] == 60000
    assert len(transport.history(first.session_id)) == 4


def test_successful_stream_keeps_usage_and_reasoning_size_without_reasoning_text():
    class Completions:
        def create(self, **kwargs):
            assert kwargs["stream_options"] == {"include_usage": True}
            return iter([
                SimpleNamespace(
                    id="request-7", model="deepseek-v4-flash", usage=None,
                    choices=[SimpleNamespace(
                        finish_reason="stop",
                        delta=SimpleNamespace(content='{"ok":1}', reasoning_content="核对来源"),
                    )],
                ),
                SimpleNamespace(
                    id="request-7", model="deepseek-v4-flash",
                    usage={"prompt_tokens": 45, "completion_tokens": 12}, choices=[],
                ),
            ])

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash", max_tokens=60000,
    )
    response = transport.start(prompt="有源方案输入")

    assert response.text == '{"ok":1}'
    assert response.call_metadata == {"attempts": [{
        "request_sha256": hashlib.sha256('[{"content":"有源方案输入","role":"user"}]'.encode()).hexdigest(),
        "requested_model": "deepseek-v4-flash",
        "reported_model": "deepseek-v4-flash",
        "request_id": "request-7",
        "requested_max_tokens": 60000,
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 45, "completion_tokens": 12},
        "content_characters": 8,
        "reasoning_characters": 4,
    }]}
    assert "核对来源" not in str(response.call_metadata)


def test_direct_deepseek_model_keeps_json_object_without_backend_argument():
    client, completions = _client(['{"draft":1}'])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    transport.start(prompt="首轮完整输入")

    assert transport._backend == "deepseek"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert completions.calls[0]["reasoning_effort"] == "max"
    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.parametrize(
    "reported_model,finish_reason,expected",
    [
        ("other-model", "stop", "模型实际回报身份"),
        ("deepseek-v4-flash", "content_filter", "未正常完成"),
    ],
)
def test_formal_stream_rejects_wrong_model_or_incomplete_finish(
    reported_model, finish_reason, expected,
):
    class StreamCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return iter([SimpleNamespace(
                id="formal-request-1", model=reported_model,
                choices=[SimpleNamespace(
                    finish_reason=finish_reason,
                    delta=SimpleNamespace(content='{"draft":1}', reasoning_content=None),
                )],
            )])

    completions = StreamCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash",
        max_tokens=60000,
    )
    with pytest.raises(ProtocolAgentCallError, match=expected):
        transport.start(prompt="冻结方案输入")
    assert completions.calls == 1


def test_formal_stream_accepts_matching_reported_model() -> None:
    class StreamCompletions:
        def create(self, **kwargs):
            return iter([SimpleNamespace(
                id="formal-request-ok", model="DEEPSEEK-V4-FLASH",
                choices=[SimpleNamespace(
                    finish_reason="stop",
                    delta=SimpleNamespace(content='{"draft":1}', reasoning_content=None),
                )],
            )])

    client = SimpleNamespace(chat=SimpleNamespace(completions=StreamCompletions()))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash",
        max_tokens=60000,
    )
    assert transport.start(prompt="冻结方案输入").text == '{"draft":1}'


def test_formal_stream_ignores_empty_keepalive_before_model_response() -> None:
    frames = [
        SimpleNamespace(id="chatcmpl-keepalive", model="keepalive", choices=[
            SimpleNamespace(finish_reason=None, delta=SimpleNamespace(
                content=None, reasoning_content=None,
            )),
        ]),
        SimpleNamespace(id="real-request", model="deepseek-v4-flash", choices=[
            SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(
                content='{"draft":1}', reasoning_content=None,
            )),
        ]),
    ]
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: iter(frames),
    )))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash", max_tokens=60000,
    )
    assert transport.start(prompt="冻结方案输入").text == '{"draft":1}'


def test_formal_stream_rejects_identity_change_after_content() -> None:
    frames = [
        SimpleNamespace(id="first", model="deepseek-v4-flash", choices=[
            SimpleNamespace(finish_reason=None, delta=SimpleNamespace(
                content='{"draft":', reasoning_content=None,
            )),
        ]),
        SimpleNamespace(id="second", model="another-model", choices=[
            SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(
                content="1}", reasoning_content=None,
            )),
        ]),
    ]
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: iter(frames),
    )))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash", max_tokens=60000,
    )
    with pytest.raises(ProtocolAgentCallError, match="流式回包中断") as caught:
        transport.start(prompt="冻结方案输入")
    assert caught.value.error_code == "STREAM_INTERRUPTED"
    assert caught.value.error_metadata["reported_model"] == "deepseek-v4-flash"
    assert "模型流在有效内容之间变更了模型身份" in str(caught.value.__cause__.__cause__)


def test_interrupted_formal_stream_preserves_partial_identity_without_resending() -> None:
    class StreamCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1

            def chunks():
                yield SimpleNamespace(
                    id="formal-partial-1", model="deepseek-v4-flash",
                    usage={"completion_tokens": 9},
                    choices=[SimpleNamespace(
                        finish_reason=None,
                        delta=SimpleNamespace(content='{"draft":', reasoning_content="核对原文"),
                    )],
                )
                raise httpx.ReadError("stream disconnected")

            return chunks()

    completions = StreamCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash",
        max_tokens=60000,
    )
    with pytest.raises(ProtocolAgentCallError) as caught:
        transport.start(prompt="冻结方案输入")
    assert completions.calls == 1
    assert caught.value.error_code == "STREAM_INTERRUPTED"
    assert caught.value.error_metadata == {
        "request_id": "formal-partial-1", "reported_model": "deepseek-v4-flash",
        "finish_reason": None, "usage": {"completion_tokens": 9},
        "content_characters": 9, "reasoning_characters": 4,
        "partial_content_sha256": hashlib.sha256(b'{"draft":').hexdigest(),
    }
    assert len(transport._histories[caught.value.session_id]) == 1


def test_formal_stream_without_terminal_status_is_not_accepted_or_retried() -> None:
    class StreamCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return iter([SimpleNamespace(
                id="formal-no-finish", model="deepseek-v4-flash",
                choices=[SimpleNamespace(
                    finish_reason=None,
                    delta=SimpleNamespace(content='{"draft":1}', reasoning_content=None),
                )],
            )])

    completions = StreamCompletions()
    transport = DeepSeekProtocolAgentTransport(
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
        backend="deepseek", model="deepseek-v4-flash", max_tokens=60000,
    )
    with pytest.raises(ProtocolAgentCallError) as caught:
        transport.start(prompt="冻结方案输入")
    assert completions.calls == 1
    assert caught.value.error_code == "STREAM_INTERRUPTED"
    assert caught.value.error_metadata["request_id"] == "formal-no-finish"


def test_pre_response_transport_error_can_still_retry(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.protocol_semantic_transport.time.sleep", lambda _delay: None)
    client, completions = _client([
        httpx.ReadError("connection failed before response"), '{"draft":1}',
    ])
    transport = DeepSeekProtocolAgentTransport(
        client=client, backend="deepseek", model="deepseek-v4-flash",
        max_tokens=60000,
    )
    assert transport.start(prompt="冻结方案输入").text == '{"draft":1}'
    assert len(completions.calls) == 2


def test_parent_segmentation_capability_is_independent_from_compact_wire():
    glm = DeepSeekProtocolAgentTransport(
        client=object(),
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        api_key="test-key",
    )
    mtplx = DeepSeekProtocolAgentTransport(
        client=object(),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
    )
    deepseek = DeepSeekProtocolAgentTransport(
        client=object(),
        backend="deepseek",
        model="deepseek-v4-flash",
        api_key="test-key",
    )

    assert glm.uses_compact_wire_contract is False
    assert glm.supports_parent_rule_segmentation is True
    assert mtplx.uses_compact_wire_contract is True
    assert mtplx.supports_parent_rule_segmentation is True
    assert deepseek.supports_parent_rule_segmentation is True


@pytest.mark.parametrize("backend", ["omlx", "mtplx", "mlx-serve"])
def test_local_formal_contract_is_explicit_and_keeps_route(backend, monkeypatch):
    from app.agents import protocol_semantic_transport as _transport_module
    from app.llm import mtplx_model_lifecycle

    monkeypatch.setattr(
        _transport_module, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 131072
    )
    if backend == "mtplx":
        monkeypatch.setattr(
            mtplx_model_lifecycle, "mtplx_deployment_identity",
            lambda *_args: {"lifecycle": "isolated-test/v1"},
        )
    options = dict(client=object(), backend=backend, model="test-local-model",
                   reasoning_effort="medium", max_tokens=131072,
                   provider_defaults=True)
    default = DeepSeekProtocolAgentTransport(**options)
    formal = DeepSeekProtocolAgentTransport(**options, compact_wire=False)
    assert default.uses_compact_wire_contract is True
    assert formal.uses_compact_wire_contract is False
    assert formal.supports_parent_rule_segmentation is True
    before = default._completion_kwargs([])
    after = formal._completion_kwargs([])
    if backend == "mtplx":
        assert after["response_format"] == {"type": "json_object"}
    else:
        assert after["response_format"]["json_schema"]["name"] == "protocol_semantic_deconstruction_candidate"
    assert "temperature" not in after
    assert {k: v for k, v in before.items() if k != "response_format"} == {
        k: v for k, v in after.items() if k != "response_format"}
    for kind in ("semantic_candidate", "semantic_rule_repair"):
        assert default.semantic_cache_identity(output_kind=kind) != formal.semantic_cache_identity(output_kind=kind)


@pytest.mark.parametrize("backend,value", [("omlx", "false"), ("omlx", 0), ("deepseek", False)])
def test_explicit_wire_contract_rejects_invalid_route_or_value(backend, value):
    with pytest.raises(ValueError, match="输出合同选择"):
        DeepSeekProtocolAgentTransport(client=object(), backend=backend,
                                       model="test", compact_wire=value)


@pytest.mark.parametrize("kind,field", [("semantic_candidate", "proposed_rules"),
                                      ("semantic_rule_repair", "replacement_rules")])
def test_formal_schema_bounds_batch_count_and_codes(kind, field):
    from app.agents.protocol_deconstructor import protocol_output_response_format
    schema = protocol_output_response_format(kind, official_codes=["IN-01", "IN-02"])["json_schema"]["schema"]
    assert schema["properties"][field]["minItems"] == 2
    assert schema["properties"][field]["maxItems"] == 2
    assert schema["$defs"]["SemanticRule"]["properties"]["official_code"]["enum"] == ["IN-01", "IN-02"]
    unbounded = protocol_output_response_format(kind)["json_schema"]["schema"]
    assert "maxItems" not in unbounded["properties"][field]


@pytest.mark.parametrize("backend", ["omlx", "mtplx", "mlx-serve"])
def test_formal_local_batches_do_not_accumulate_history(backend, monkeypatch):
    from app.agents.protocol_deconstructor import _compact_transport_history
    from app.agents import protocol_semantic_transport
    monkeypatch.setattr(protocol_semantic_transport, "MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS", 65536)
    transport = DeepSeekProtocolAgentTransport(client=object(), backend=backend,
        model="test", compact_wire=False, max_tokens=65536)
    transport.restore_history(session_id="test", messages=[
        {"role": "user", "content": "previous source"},
        {"role": "assistant", "content": "previous output"},
    ])
    _compact_transport_history(transport, "test", context="frozen batch identity")
    assert transport.history("test")[0]["content"] == "frozen batch identity"
    assert "previous" not in str(transport.history("test"))


def test_formal_omlx_schema_uses_same_compatibility_projection():
    from app.agents.protocol_deconstructor import protocol_output_response_format
    from app.llm.omlx_schema_compat import decoding_response_format
    transport = DeepSeekProtocolAgentTransport(client=object(), backend="omlx",
        model="test", compact_wire=False)
    for kind in ("semantic_candidate", "semantic_rule_repair"):
        assert transport._completion_kwargs([], output_kind=kind)["response_format"] == (
            decoding_response_format(protocol_output_response_format(kind, compact=False)))


def test_formal_batch_repair_does_not_request_dnf_wire():
    from app.agents.protocol_deconstructor import DNF_WIRE_VERSION, _batch_schema_repair_prompt, _compact_schema
    options = dict(candidate_id="candidate-1", agent_call_id="call-1",
                   batch_id="batch-1", problem="invalid structure")
    formal = _batch_schema_repair_prompt(["IN-01"], compact=False, **options)
    compact = _batch_schema_repair_prompt(["IN-01"], compact=True, **options)
    assert formal.endswith("输出结构：" + _compact_schema())
    assert "wire_version=" not in formal
    assert f"wire_version='{DNF_WIRE_VERSION}'" in compact


def test_event_frequency_prompt_does_not_require_result_selection() -> None:
    from app.agents.protocol_deconstructor import _SYSTEM_CONTRACT, _batch_schema_repair_prompt

    assert "仅统计临床事件发生次数" in _SYSTEM_CONTRACT
    assert "observation_policy和repeat_scheme均填null" in _SYSTEM_CONTRACT
    repair = _batch_schema_repair_prompt(
        ["EX-01"], candidate_id="candidate", agent_call_id="call",
        batch_id="2/2", problem="频次计数不能与未定义先后关系的复查或观察选择混用",
        compact=False,
    )
    assert "仅统计事件次数且原文没有结果选择要求时" in repair
    assert "原文两者都要求而关系未明时" in repair
    assert "unanchored_lookback 的情况" in repair


def test_formal_local_semantic_repair_restores_frozen_source(monkeypatch):
    from types import SimpleNamespace
    from app.agents import protocol_deconstructor as module
    from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture
    captured = []
    source, _, _ = _fixture()
    def payload(source_input, rule_codes, **kwargs):
        captured.append((source_input, list(rule_codes)))
        return {"original_source": "frozen source excerpt"}
    monkeypatch.setattr(module, "_batch_prompt_payload", payload)
    options = dict(attempt=1, parsed_draft_available=True,
        replacement_rule_codes=["IN-02"], compact=False,
        candidate=SimpleNamespace(candidate_id="candidate"), source_input=source)
    prompt = module._repair_prompt([], include_frozen_context=True, **options)
    assert prompt.startswith(module._SYSTEM_CONTRACT + "\n")
    assert captured == [(source, ["IN-02"])]
    assert '"original_source": "frozen source excerpt"' in prompt
    assert '"current_target_rule_codes": ["IN-02"]' in prompt
    assert "compact wire" not in prompt
    captured.clear()
    assert "frozen source excerpt" not in module._repair_prompt([], **options)
    assert not module._repair_prompt([], **options).startswith(module._SYSTEM_CONTRACT)
    assert captured == []


def test_transport_classifies_timeout_for_bounded_segment_recovery():
    client, _completions = _client([httpx.ReadTimeout("provider timeout")])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="zhipu-coding-plan",
        model="glm-5.3-flash",
        api_key="test-key",
    )

    with pytest.raises(ProtocolAgentCallError) as caught:
        transport.start(prompt="一个冻结分段")

    assert caught.value.error_code == "TRANSPORT_TIMEOUT"


def test_omlx_batch_history_can_be_compacted_to_a_bounded_identity_anchor():
    client, completions = _client(['{"batch":1}', '{"batch":2}'])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
        max_tokens=60000,
    )

    first = transport.start(prompt="包含整批原文的首轮输入")
    transport.compact_session_history(
        session_id=first.session_id,
        context="已完成批次1；candidate_id='candidate-1'。",
    )
    second = transport.continue_session(
        session_id=first.session_id,
        prompt="仅发送批次2的来源材料",
    )

    assert second.session_id == first.session_id
    assert completions.calls[1]["messages"] == [
        {
            "role": "user",
            "content": "已完成批次1；candidate_id='candidate-1'。",
        },
        {"role": "assistant", "content": "已保留冻结上下文和批次身份。"},
        {"role": "user", "content": "仅发送批次2的来源材料"},
    ]
    assert "整批原文" not in completions.calls[1]["messages"][0]["content"]


def test_history_compaction_rejects_oversized_anchor_instead_of_truncating():
    client, _completions = _client(['{"batch":1}'])
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
    )
    first = transport.start(prompt="首轮输入")

    with pytest.raises(ValueError, match="超过 12000 字符操作上限"):
        transport.compact_session_history(
            session_id=first.session_id,
            context="x" * 12001,
        )

    assert transport.history(first.session_id) == (
        {"role": "user", "content": "首轮输入"},
        {"role": "assistant", "content": '{"batch":1}'},
    )


def test_unknown_session_is_rejected_instead_of_starting_fresh():
    client, _completions = _client([])
    transport = DeepSeekProtocolAgentTransport(client=client)
    with pytest.raises(ValueError, match="找不到原方案解构会话"):
        transport.continue_session(session_id="missing", prompt="修正")


def test_persisted_complete_history_can_resume_without_starting_fresh():
    client, completions = _client(['{"repair":1}'])
    transport = DeepSeekProtocolAgentTransport(client=client)
    history = [
        {"role": "user", "content": "首轮完整输入"},
        {"role": "assistant", "content": '{"draft":1}'},
    ]

    transport.restore_history(session_id="persisted-session", messages=history)
    response = transport.continue_session(
        session_id="persisted-session", prompt="仅修正EX-04"
    )

    assert response.session_id == "persisted-session"
    assert completions.calls[0]["messages"][:2] == history
    assert completions.calls[0]["messages"][2]["content"] == "仅修正EX-04"


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "assistant", "content": "无首轮请求"}],
        [
            {"role": "user", "content": "请求"},
            {"role": "user", "content": "角色顺序错误"},
        ],
        [{"role": "user", "content": "尚无模型响应"}],
    ],
)
def test_invalid_persisted_history_is_rejected(messages):
    client, _completions = _client([])
    transport = DeepSeekProtocolAgentTransport(client=client)
    with pytest.raises(ValueError, match="持久方案解构会话|只能从"):
        transport.restore_history(session_id="persisted-session", messages=messages)


def test_empty_body_is_retried_once_without_changing_logical_session():
    client, completions = _client(
        [(None, "length", "内部推理"), ('{"draft":1}', "stop", "")]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="deepseek",
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    response = transport.start(prompt="首轮完整输入")

    assert response.text == '{"draft":1}'
    assert len(completions.calls) == 2
    assert completions.calls[1]["messages"][:-1] == completions.calls[0]["messages"]
    assert "不要重复分析" in completions.calls[1]["messages"][-1]["content"]
    assert "长度上限" in completions.calls[1]["messages"][-1]["content"]
    assert len(transport.history(response.session_id)) == 2


def test_two_empty_bodies_report_finish_reason_without_exposing_reasoning():
    client, _completions = _client(
        [
            (None, "length", "不应出现在异常中的内部推理"),
            (None, "length", "仍不应暴露"),
        ]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        model="deepseek-v4-flash",
        reasoning_effort="max",
        max_tokens=60000,
    )

    with pytest.raises(RuntimeError, match="连续2次.*结束原因=length") as exc:
        transport.start(prompt="首轮完整输入")

    assert "内部推理" not in str(exc.value)
    assert len(transport.history(exc.value.session_id)) == 1
    assert transport.history(exc.value.session_id)[0]["content"] == "首轮完整输入"


def test_length_finish_reason_never_accepts_truncated_json_body():
    client, completions = _client(
        [
            ('{"candidate_id":"truncated"', "length", "不应暴露"),
            ('{"candidate_id":"still-truncated"', "length", "仍不应暴露"),
        ]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
        max_tokens=16000,
    )

    with pytest.raises(RuntimeError, match="长度上限截断") as exc:
        transport.start(prompt="首轮完整输入")

    assert len(completions.calls) == 2
    assert "truncated" not in str(exc.value)
    assert len(transport.history(exc.value.session_id)) == 1


def test_malformed_json_is_repaired_once_in_same_transport_call():
    client, completions = _client(
        [
            ('{"candidate_id":"broken" "rules":[]}', "stop", ""),
            ('{"candidate_id":"repaired","rules":[]}', "stop", ""),
        ]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
    )

    response = transport.start(prompt="首轮完整输入")

    assert response.text == '{"candidate_id":"repaired","rules":[]}'
    assert len(completions.calls) == 2
    assert [item["role"] for item in completions.calls[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert "JSON语法不完整" in completions.calls[1]["messages"][-1]["content"]
    assert len(transport.history(response.session_id)) == 2


def test_two_malformed_json_bodies_fail_without_exposing_raw_output():
    client, completions = _client(
        [
            ('{"candidate_id":"broken"', "stop", ""),
            ('{"candidate_id":"still-broken"', "stop", ""),
        ]
    )
    transport = DeepSeekProtocolAgentTransport(
        client=client,
        backend="omlx",
        model="Qwen3.8-27B-oQ8e-fp16-mtp",
    )

    with pytest.raises(RuntimeError, match="连续2次.*可解析的JSON") as exc:
        transport.start(prompt="首轮完整输入")

    assert len(completions.calls) == 2
    assert "still-broken" not in str(exc.value)
    assert "第1行" in str(exc.value)
    assert len(transport.history(exc.value.session_id)) == 1


def test_deconstruct_completion_kwargs_use_independent_reasoning_setting(monkeypatch):
    monkeypatch.setattr(llm_client, "DECONSTRUCT_BACKEND", "deepseek")
    monkeypatch.setattr(llm_client, "DECONSTRUCT_REASONING_EFFORT", "max")
    kwargs = llm_client._deconstruct_completion_kwargs(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": "方案"}],
        temperature=0.9,
        max_tokens=60000,
    )
    assert kwargs["reasoning_effort"] == "max"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "temperature" not in kwargs
