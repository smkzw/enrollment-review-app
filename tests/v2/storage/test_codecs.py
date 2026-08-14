"""合同编解码：往返、哈希校验与列/payload 交叉核对。"""
from __future__ import annotations

import json

import pytest

from app.domain.contracts import Subject, Project
from app.domain.publication import canonical_hash
from app.storage.codecs import (
    PersistedContractInvalid,
    check_column_mirrors,
    decode_contract,
    encode_contract,
    parse_datetime_column,
    to_utc_naive,
)
from app.storage.models import SubjectRecord


def _subject_payload() -> dict:
    return {
        "schema_version": "fixture/v1",
        "revision": 1,
        "subject_id": "subject-t1",
        "subject_code": "T-001",
        "project_id": "project-t1",
        "center_code": None,
        "center_name": None,
        "sex": "female",
        "age_years": 57.5,
    }


def test_roundtrip_preserves_ids_dates_enums_and_floats() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload_json, payload_sha256 = encode_contract(subject)
    decoded = decode_contract(Subject, payload_json, payload_sha256)
    assert decoded == subject
    assert decoded.subject_id == "subject-t1"
    assert decoded.age_years == 57.5
    assert decoded.sex == "female"


def test_encode_hash_matches_domain_canonical_hash() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload_json, payload_sha256 = encode_contract(subject)
    assert payload_sha256 == canonical_hash(json.loads(payload_json))


def test_tampered_payload_json_is_rejected() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload_json, payload_sha256 = encode_contract(subject)
    tampered = payload_json.replace('"T-001"', '"T-999"')
    with pytest.raises(PersistedContractInvalid, match="哈希不一致"):
        decode_contract(Subject, tampered, payload_sha256)


def test_tampered_sha256_column_is_rejected() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload_json, payload_sha256 = encode_contract(subject)
    with pytest.raises(PersistedContractInvalid, match="哈希不一致"):
        decode_contract(Subject, payload_json, "f" * 64)


def test_payload_failing_pydantic_validation_is_rejected() -> None:
    payload = _subject_payload()
    payload["age_years"] = -3  # 违反 ge=0
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha256 = canonical_hash(payload)
    with pytest.raises(PersistedContractInvalid, match="校验失败"):
        decode_contract(Subject, payload_json, sha256)


def test_corrupt_json_is_rejected() -> None:
    import hashlib

    corrupt = "{not json"
    sha256 = hashlib.sha256(corrupt.encode("utf-8")).hexdigest()
    with pytest.raises(PersistedContractInvalid, match="无法解析"):
        decode_contract(Subject, corrupt, sha256)


def test_column_payload_mirror_mismatch_is_rejected() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload_json, payload_sha256 = encode_contract(subject)
    record = SubjectRecord(
        subject_id="subject-t1",
        subject_code="DRIFTED",  # 与 payload 不一致
        project_id="project-t1",
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        revision=1,
        created_at=to_utc_naive(__import__("datetime").datetime(2026, 8, 14)),
        updated_at=to_utc_naive(__import__("datetime").datetime(2026, 8, 14)),
    )
    payload = json.loads(payload_json)
    with pytest.raises(PersistedContractInvalid, match="与已验证 payload 不一致"):
        check_column_mirrors(
            "Subject",
            record,
            payload,
            {"subject_code": "subject_code", "project_id": "project_id"},
        )


def test_datetime_column_parsing_normalizes_to_utc_naive() -> None:
    parsed = parse_datetime_column("2026-08-12T12:00:00Z")
    assert parsed.tzinfo is None
    assert parsed.isoformat() == "2026-08-12T12:00:00"


def test_contract_with_extra_field_is_rejected_by_codec() -> None:
    subject = Subject.model_validate(_subject_payload())
    payload = _subject_payload()
    payload["unexpected"] = True
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha256 = canonical_hash(payload)
    with pytest.raises(PersistedContractInvalid, match="校验失败"):
        decode_contract(Subject, payload_json, sha256)


def test_project_nested_protocol_roundtrip() -> None:
    payload = {
        "schema_version": "fixture/v1",
        "revision": 1,
        "project_id": "project-t1",
        "project_code": "P-001",
        "project_name": "测试项目",
        "study_phase": "phase_iii",
        "protocol_version": {
            "schema_version": "fixture/v1",
            "protocol_version_id": "protocol-v1",
            "protocol_code": "PROTO-1",
            "official_version": "v1.0",
            "official_date": {"value": "2026-01-15", "precision": "day", "source_text": None},
            "sha256": "a" * 64,
            "integrity_manifest_sha256": "b" * 64,
            "authority_record_sha256": "c" * 64,
            "authority_confirmation_id": "confirmation-1",
            "authority_gate_result_id": "gate-authority-1",
            "integrity_gate_result_id": "gate-integrity-1",
        },
        "rule_set_id": "ruleset-1",
    }
    project = Project.model_validate(payload)
    payload_json, payload_sha256 = encode_contract(project)
    decoded = decode_contract(Project, payload_json, payload_sha256)
    assert decoded == project
    assert decoded.protocol_version.official_date.value.isoformat() == "2026-01-15"
