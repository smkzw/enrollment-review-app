"""Explicit context experiments stay separate from default product identities."""

import pytest

from app.agents.protocol_deconstructor import _compact_transport_history
from app.agents.protocol_semantic_transport import DeepSeekProtocolAgentTransport


@pytest.mark.parametrize("backend", ["zhipu-coding-plan", "deepseek", "mtplx"])
def test_explicit_context_policy_is_provider_neutral_and_cache_separated(backend):
    options = dict(client=object(), backend=backend, model="test", max_tokens=65536)
    default = DeepSeekProtocolAgentTransport(**options)
    bounded = DeepSeekProtocolAgentTransport(**options, bounded_batch_context=True)
    full = DeepSeekProtocolAgentTransport(**options, bounded_batch_context=False)
    assert bounded.supports_bounded_batch_context is True
    assert full.supports_bounded_batch_context is False
    assert default.supports_bounded_batch_context is (backend == "mtplx")
    identities = {
        t.semantic_cache_identity(output_kind="semantic_candidate")
        for t in (default, bounded, full)
    }
    assert len(identities) == 3
    for transport in (bounded, full):
        transport.restore_history(session_id="batch", messages=[
            {"role": "user", "content": "old batch source"},
            {"role": "assistant", "content": "old batch output"},
        ])
        _compact_transport_history(transport, "batch", context="current frozen identity")
    assert "old batch" not in str(bounded.history("batch"))
    assert "old batch source" in str(full.history("batch"))
