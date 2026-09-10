"""Deterministic acceptance functions for the control comparison matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.contracts.protocol_control_matrix import (
    ProtocolControlMatrix,
    ProtocolControlMatrixError,
    build_protocol_control_matrix_json,
    render_protocol_control_matrix_markdown,
    validate_protocol_control_matrix as _validate_protocol_control_matrix,
    validate_protocol_control_matrix_serializations,
)

CONTROL_MATRIX_VALIDATOR_VERSION = "phase5/control-matrix-validator/v5"

__all__ = [
    "CONTROL_MATRIX_VALIDATOR_VERSION",
    "ProtocolControlMatrixError",
    "ProtocolControlMatrixIssue",
    "ProtocolControlMatrixReport",
    "build_protocol_control_matrix_json",
    "check_protocol_control_matrix",
    "render_protocol_control_matrix_markdown",
    "validate_protocol_control_matrix",
    "validate_protocol_control_matrix_serializations",
]


@dataclass(frozen=True)
class ProtocolControlMatrixIssue:
    code: str
    message: str
    entity_id: str | None = None


@dataclass(frozen=True)
class ProtocolControlMatrixReport:
    accepted: bool
    validator_version: str
    issues: tuple[ProtocolControlMatrixIssue, ...] = ()


def validate_protocol_control_matrix(
    matrix: ProtocolControlMatrix,
    coverage_manifest: Any = None,
    **kwargs: Any,
) -> ProtocolControlMatrix:
    """Run the strict domain validator and return the unchanged matrix."""

    return _validate_protocol_control_matrix(matrix, coverage_manifest, **kwargs)


def check_protocol_control_matrix(
    matrix: ProtocolControlMatrix,
    coverage_manifest: Any = None,
    **kwargs: Any,
) -> ProtocolControlMatrixReport:
    try:
        validate_protocol_control_matrix(matrix, coverage_manifest, **kwargs)
    except ProtocolControlMatrixError as exc:
        return ProtocolControlMatrixReport(
            accepted=False,
            validator_version=CONTROL_MATRIX_VALIDATOR_VERSION,
            issues=(ProtocolControlMatrixIssue(exc.code, str(exc), exc.entity_id),),
        )
    return ProtocolControlMatrixReport(
        accepted=True,
        validator_version=CONTROL_MATRIX_VALIDATOR_VERSION,
    )
