"""Deprecated alias: the protocol semantic transport now lives in
:mod:`app.agents.protocol_semantic_transport`.  Kept only so historical
acceptance scripts and external callers importing the original DeepSeek-named
path continue to work; new code must import the neutral module directly.
"""

from app.agents.protocol_semantic_transport import (
    DeepSeekProtocolAgentTransport,
    OpenAICompatibleProtocolAgentTransport,
    SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS,
    TRANSPORT_TRANSIENT_MAX_ATTEMPTS,
    TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS,
)

__all__ = [
    "DeepSeekProtocolAgentTransport",
    "OpenAICompatibleProtocolAgentTransport",
    "SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS",
    "TRANSPORT_TRANSIENT_MAX_ATTEMPTS",
    "TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS",
]
