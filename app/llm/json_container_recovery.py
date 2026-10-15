"""Bounded syntax-only recovery; clinical/schema validation remains upstream."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from jsonschema.validators import validator_for

POLICY = "single-container-close/v1"
MAX_CHARACTERS = 262144
MAX_POSITIONS = 128


@dataclass(frozen=True)
class ContainerRecovery:
    text: str
    position: int
    token: str

    def receipt(self, original: str) -> dict[str, object]:
        return {
            "policy": POLICY, "insert_position": self.position, "insert_token": self.token,
            "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "recovered_sha256": hashlib.sha256(self.text.encode()).hexdigest(),
            "clinical_validation_complete": False,
        }


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-JSON constant")


def strict_json_loads(text: str):
    """Reject duplicate keys and non-JSON constants rather than choosing a value."""
    try:
        return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
    except json.JSONDecodeError:
        raise
    except ValueError as exc:
        raise json.JSONDecodeError(str(exc), text, 0) from exc


def recover_single_container_close(text: str, schema: dict) -> ContainerRecovery | None:
    """Insert only one ] or } outside strings, with one unique schema-valid result.

    EOF, string/value repair, omitted fields and duplicate keys are never repaired.
    More than one possible container structure is ambiguous and remains a failure.
    Callers must require normal provider completion and preserve original bytes.
    """
    if len(text) > MAX_CHARACTERS:
        return None
    try:
        json.loads(text)
        return None
    except json.JSONDecodeError:
        pass
    positions = []
    in_string = escaped = False
    for index, token in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif token == "\\":
                escaped = True
            elif token == '"':
                in_string = False
        elif token == '"':
            in_string = True
        elif token in ",}]":
            positions.append(index)
            if len(positions) > MAX_POSITIONS:
                return None
    if in_string:
        return None
    validator = validator_for(schema)(schema)
    recovered = None
    for position in positions:
        for token in "]}":
            candidate = text[:position] + token + text[position:]
            try:
                payload = json.loads(candidate, object_pairs_hook=_unique_keys,
                                     parse_constant=_reject_constant)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(payload, dict) or not validator.is_valid(payload):
                continue
            if recovered is not None:
                if recovered.text != candidate:
                    return None
                continue
            recovered = ContainerRecovery(candidate, position, token)
    return recovered
