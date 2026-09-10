"""Versioned V2 semantic-agent contracts and adapters."""

from importlib import import_module

_PHASE_APPLICABILITY_EXPORTS = frozenset(
    {
        "ConfiguredPhaseApplicabilityAgentTransport",
        "OpenAICompatiblePhaseApplicabilityAgentTransport",
        "OpenAICompatiblePhaseApplicabilityTransport",
        "PhaseApplicabilityAgentModelTransport",
        "PhaseApplicabilityAgentCallError",
        "PhaseApplicabilityModelTransport",
        "phase_applicability_agent_transport_from_environment",
        "phase_applicability_agent_transport_from_model_config",
        "phase_applicability_transport_from_config",
        "phase_applicability_transport_from_environment",
        "phase_applicability_transport_from_model_config",
    }
)
_PROTOCOL_CONTROL_EXPORTS = frozenset(
    {
        "ConfiguredProtocolControlAgentTransport",
        "OpenAICompatibleProtocolControlAgentTransport",
        "OpenAICompatibleProtocolControlTransport",
        "ProtocolControlAgentCallError",
        "ProtocolControlAgentModelTransport",
        "ProtocolControlModelTransport",
        "protocol_control_agent_transport_from_environment",
        "protocol_control_agent_transport_from_model_config",
        "protocol_control_transport_from_config",
        "protocol_control_transport_from_environment",
        "protocol_control_transport_from_model_config",
    }
)
_PROTOCOL_CONTROL_DISCOVERY_EXPORTS = frozenset(
    {
        "ConfiguredProtocolControlDiscoveryAgentTransport",
        "OpenAICompatibleProtocolControlDiscoveryAgentTransport",
        "OpenAICompatibleProtocolControlDiscoveryTransport",
        "PROTOCOL_CONTROL_DISCOVERY_BACKEND",
        "PROTOCOL_CONTROL_DISCOVERY_MAX_TOKENS",
        "PROTOCOL_CONTROL_DISCOVERY_MODEL",
        "PROTOCOL_CONTROL_DISCOVERY_REASONING_EFFORT",
        "ProtocolControlDiscoveryAgentCallError",
        "ProtocolControlDiscoveryAgentModelTransport",
        "ProtocolControlDiscoveryModelTransport",
        "protocol_control_discovery_agent_json_schema",
        "protocol_control_discovery_agent_response_format",
        "protocol_control_discovery_agent_transport_from_environment",
        "protocol_control_discovery_agent_transport_from_model_config",
        "protocol_control_discovery_transport_from_config",
        "protocol_control_discovery_transport_from_environment",
        "protocol_control_discovery_transport_from_model_config",
    }
)
__all__ = sorted(
    _PHASE_APPLICABILITY_EXPORTS
    | _PROTOCOL_CONTROL_EXPORTS
    | _PROTOCOL_CONTROL_DISCOVERY_EXPORTS
)



def __getattr__(name: str):
    if name in _PHASE_APPLICABILITY_EXPORTS:
        module = import_module(".phase_applicability_transport", __name__)
        return getattr(module, name)
    if name in _PROTOCOL_CONTROL_EXPORTS:
        module = import_module(".protocol_control_agent_transport", __name__)
        return getattr(module, name)
    if name in _PROTOCOL_CONTROL_DISCOVERY_EXPORTS:
        module = import_module(".protocol_control_discovery_transport", __name__)
        return getattr(module, name)
    raise AttributeError(name)
