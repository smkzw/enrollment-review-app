"""Phase 5 Slice 5.7 人工事实修订合同确定性测试（worker_01 重制）。

覆盖新 lineage 模型：target/new 稳定身份分离、同稳定+1/异稳定1、新旧快照规范 JSON 与哈希、
理由、定位、操作者、时间、影响范围、幂等键。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.fact_corrections import (
    FactCorrectionImpactScope,
    FactCorrectionV2,
    canonical_json,
    event_semantic_snapshot,
    exposure_semantic_snapshot,
    fact_correction_idempotency_key,
    fact_semantic_snapshot,
)
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.enums import DatePrecision, DurationStatus, FactPolarity, SourceStrength, ProfileLane
from app.domain.contracts.facts import ClinicalFactV2, ClinicalEventV2, MedicationExposureV2, PartialDateRange, AssertionBasis

UTC = timezone.utc
SHA_A = "a" * 64
SHA_B = "b" * 64


def _authority(**overrides):
    base = {
        "project_id": "proj-1",
        "subject_id": "subj-1",
        "review_episode_id": "ep-1",
        "episode_revision": 1,
        "protocol_version_id": "pv-1",
        "rule_set_id": "rs-1",
        "rule_set_revision": 1,
        "evidence_snapshot_v2_id": "snap-1",
        "complete_processing_revision_id": "proc-1",
    }
    base.update(overrides)
    return FactAuthority(**base)


def _impact(**overrides):
    base = {"scope_kind": "local", "affected_locator_ids": ["loc-1"], "affected_document_ids": ["doc-1"], "affected_fact_ids": ["fact-1"]}
    base.update(overrides)
    return FactCorrectionImpactScope(**base)


def _snap_pair():
    old_snap = {
        "kind": "fact",
        "fact_type": "vital_sign",
        "profile_lane": "evidence_quality",
        "polarity": "affirmed",
        "asserted_object": "血压",
        "value": "120/80",
        "unit": "unitless",
        "date_range": None,
        "source_strength": "contemporaneous_objective_result",
        "assertion_object": None,
        "assertion_text": None,
        "supported_requirement_ids": [],
    }
    new_snap = {
        **old_snap,
        "value": "130/80",
    }
    old_json = canonical_json(old_snap)
    new_json = canonical_json(new_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    new_sha = hashlib.sha256(new_json.encode()).hexdigest()
    return old_json, old_sha, new_json, new_sha


OLD_JSON, OLD_SHA, NEW_JSON, NEW_SHA = _snap_pair()


def test_incomplete_semantic_snapshot_is_rejected():
    fragment = canonical_json({"kind": "fact", "value": "120/80"})
    fragment_sha = hashlib.sha256(fragment.encode()).hexdigest()
    with pytest.raises(ValidationError, match="完整语义快照"):
        _correction(
            old_snapshot_json=fragment,
            old_snapshot_sha256=fragment_sha,
            new_snapshot_json=NEW_JSON,
            new_snapshot_sha256=NEW_SHA,
        )


def _correction(**overrides):
    auth = overrides.pop("authority", _authority())
    impact = overrides.pop("impact_scope", _impact())
    old_json = overrides.pop("old_snapshot_json", OLD_JSON)
    new_json = overrides.pop("new_snapshot_json", NEW_JSON)
    old_sha = overrides.pop("old_snapshot_sha256", OLD_SHA)
    new_sha = overrides.pop("new_snapshot_sha256", NEW_SHA)
    # allow caller to override stables via overrides
    target_stable = overrides.pop("target_stable_identity", SHA_A)
    new_stable = overrides.pop("new_stable_identity", SHA_B)
    # if new_stable == target_stable, default new_revision = target+1 else 1
    target_rev = overrides.get("target_revision", 1)
    default_new_rev = target_rev + 1 if target_stable == new_stable else 1
    new_rev = overrides.pop("new_revision", default_new_rev)
    reason = overrides.pop("reason", "核对原文第3页，旧值录入错误")
    locator_ids = overrides.pop("locator_ids", ["loc-1"])
    operator_id = overrides.pop("operator_id", "op-1")
    corrected_at = overrides.pop("corrected_at", datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC))
    created_at = overrides.pop("created_at", datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC))
    # idempotency now binds concrete entity IDs and revisions to prevent lineage edge collision
    target_id = overrides.get("target_id", "fact-1")
    target_revision = overrides.get("target_revision", target_rev)
    new_entity_id = overrides.get("new_entity_id", "fact-1-r2")
    new_revision = new_rev
    id_key = overrides.pop(
        "idempotency_key",
        fact_correction_idempotency_key(
            authority=auth,
            target_kind=overrides.get("target_kind", "fact"),
            target_id=target_id,
            target_stable_identity=target_stable,
            target_revision=target_revision,
            new_entity_id=new_entity_id,
            new_stable_identity=new_stable,
            new_revision=new_revision,
            old_snapshot_sha256=old_sha,
            new_snapshot_sha256=new_sha,
            reason=reason,
            locator_ids=locator_ids,
            operator_id=operator_id,
        ),
    )
    base = {
        "correction_id": "corr-1",
        "authority": auth,
        "target_kind": "fact",
        "target_id": target_id,
        "target_stable_identity": target_stable,
        "new_stable_identity": new_stable,
        "target_revision": target_revision,
        "new_entity_id": new_entity_id,
        "new_revision": new_rev,
        "old_snapshot_json": old_json,
        "old_snapshot_sha256": old_sha,
        "new_snapshot_json": new_json,
        "new_snapshot_sha256": new_sha,
        "reason": reason,
        "locator_ids": locator_ids,
        "operator_id": operator_id,
        "corrected_at": corrected_at,
        "created_at": created_at,
        "impact_scope": impact,
        "idempotency_key": id_key,
    }
    base.update(overrides)
    return FactCorrectionV2(**base)


def test_fact_correction_ok_same_stable_plus_one():
    corr = _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_A, target_revision=2, new_revision=3)
    assert corr.new_revision == 3


def test_fact_correction_ok_different_stable_from_one():
    corr = _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_B, target_revision=5, new_revision=1)
    assert corr.new_stable_identity == SHA_B
    assert corr.new_revision == 1


def test_fact_correction_beijing_replay():
    from app.domain.contracts.fact_corrections import to_beijing_naive

    corr = _correction()
    beijing = to_beijing_naive(corr.corrected_at)
    assert beijing.hour == 15
    assert beijing.tzinfo is None


def test_fact_correction_reason_trim():
    with pytest.raises(ValidationError, match="理由不得为空"):
        _correction(reason="   ")
    with pytest.raises(ValidationError):
        _correction(reason="")
    corr = _correction(reason="  核对原文  ")
    assert corr.reason == "  核对原文  "
    key1 = fact_correction_idempotency_key(authority=_authority(), target_kind="fact", target_id="fact-1", target_stable_identity=SHA_A, target_revision=1, new_entity_id="fact-1-r2", new_stable_identity=SHA_B, new_revision=1, old_snapshot_sha256=OLD_SHA, new_snapshot_sha256=NEW_SHA, reason="核对原文", locator_ids=["loc-1"], operator_id="op-1")
    key2 = fact_correction_idempotency_key(authority=_authority(), target_kind="fact", target_id="fact-1", target_stable_identity=SHA_A, target_revision=1, new_entity_id="fact-1-r2", new_stable_identity=SHA_B, new_revision=1, old_snapshot_sha256=OLD_SHA, new_snapshot_sha256=NEW_SHA, reason="  核对原文  ", locator_ids=["loc-1"], operator_id="op-1")
    assert key1 == key2


def test_fact_correction_locators_sorted():
    with pytest.raises(ValidationError, match="排序"):
        _correction(locator_ids=["loc-2", "loc-1"])
    with pytest.raises(ValidationError, match="排序"):
        _correction(locator_ids=["loc-1", "loc-1"])


def test_fact_correction_snapshot_must_differ():
    with pytest.raises(ValidationError, match="必须不同"):
        _correction(old_snapshot_json=OLD_JSON, new_snapshot_json=OLD_JSON)
    with pytest.raises(ValidationError, match="旧快照哈希"):
        _correction(old_snapshot_sha256="b" * 64)
    with pytest.raises(ValidationError, match="新快照哈希"):
        _correction(new_snapshot_sha256="b" * 64)


def test_fact_correction_same_stable_requires_plus_one():
    with pytest.raises(ValidationError, match="必须为目标 revision \\+ 1"):
        _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_A, target_revision=1, new_revision=1)
    with pytest.raises(ValidationError, match="必须为目标 revision \\+ 1"):
        _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_A, target_revision=1, new_revision=3)


def test_fact_correction_different_stable_allows_one():
    ok = _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_B, target_revision=10, new_revision=1)
    assert ok.new_revision == 1
    ok2 = _correction(target_stable_identity=SHA_A, new_stable_identity=SHA_B, target_revision=10, new_revision=5)
    # 不同稳定时允许任意 >=1，但需与实际新实体一致（仓储校验），领域层仅放宽
    assert ok2.new_revision == 5


def test_fact_correction_new_entity_must_differ():
    with pytest.raises(ValidationError, match="新实体 ID 不得与目标 ID 相同"):
        _correction(target_id="fact-1", new_entity_id="fact-1")


def test_fact_correction_idempotency_tamper():
    with pytest.raises(ValidationError, match="幂等键"):
        _correction(idempotency_key="b" * 64)


def test_fact_correction_idempotency_binds_concrete_lineage_edge():
    kwargs = {
        "authority": _authority(),
        "target_kind": "fact",
        "target_id": "fact-old",
        "target_stable_identity": SHA_A,
        "target_revision": 1,
        "new_entity_id": "fact-new",
        "new_stable_identity": SHA_B,
        "new_revision": 1,
        "old_snapshot_sha256": OLD_SHA,
        "new_snapshot_sha256": NEW_SHA,
        "reason": "核对原文",
        "locator_ids": ["loc-1"],
        "operator_id": "op-1",
    }
    exact_retry = fact_correction_idempotency_key(**kwargs)
    assert fact_correction_idempotency_key(**kwargs) == exact_retry
    for field, value in (
        ("target_id", "fact-old-2"),
        ("target_revision", 2),
        ("new_entity_id", "fact-new-2"),
        ("new_revision", 2),
    ):
        assert fact_correction_idempotency_key(**{**kwargs, field: value}) != exact_retry


def test_fact_correction_utc_required():
    with pytest.raises(ValidationError, match="UTC"):
        _correction(corrected_at=datetime(2026, 8, 23, 7, 0, 0))
    with pytest.raises(ValidationError, match="UTC"):
        _correction(created_at=datetime(2026, 8, 23, 7, 0, 0))


def test_fact_correction_kind_invalid():
    with pytest.raises(ValidationError):
        _correction(**{"target_kind": "conflict"})
    with pytest.raises(ValidationError):
        _correction(**{"target_kind": "expectation"})


def test_impact_scope_local_requires_affected():
    with pytest.raises(ValidationError, match="必须包含至少一类"):
        _correction(impact_scope=FactCorrectionImpactScope(scope_kind="local"))
    with pytest.raises(ValidationError, match="不得携带回退原因"):
        _correction(impact_scope=FactCorrectionImpactScope(scope_kind="local", fallback_reason="x", affected_locator_ids=["loc-1"]))


def test_impact_scope_node_requires_fallback():
    with pytest.raises(ValidationError, match="必须给出明确的回退原因"):
        _correction(impact_scope=FactCorrectionImpactScope(scope_kind="node"))
    ok = FactCorrectionImpactScope(scope_kind="node", fallback_reason="缺少索引")
    assert ok.scope_kind == "node"


def test_impact_scope_sorted():
    with pytest.raises(ValidationError, match="排序"):
        FactCorrectionImpactScope(scope_kind="local", affected_fact_ids=["fact-2", "fact-1"])


def test_fact_correction_is_frozen():
    corr = _correction()
    with pytest.raises(ValidationError):
        setattr(corr, "reason", "new")
    scope = _impact()
    with pytest.raises(ValidationError):
        setattr(scope, "scope_kind", "node")


def test_snapshot_helpers_canonical():
    from app.domain.contracts.facts import clinical_fact_stable_identity as _cfs, clinical_event_stable_identity as _ces, medication_exposure_stable_identity as _mes
    _auth = _authority()
    _dr = PartialDateRange(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound="2026-03-01", upper_bound="2026-03-01")
    _stable_fact = _cfs(authority=_auth, fact_type="vital_sign", asserted_object="血压", polarity=FactPolarity.AFFIRMED, value="120/80", unit="unitless", date_range=_dr)
    # fact
    fact = ClinicalFactV2(
        fact_id="f1", run_id="r1", gate_id="g1", authority=_auth, fact_type="vital_sign", polarity=FactPolarity.AFFIRMED, asserted_object="血压", value="120/80", unit="unitless", source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE, date_range=_dr, record_time=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC), locator_ids=["loc-1"], assertion_basis=AssertionBasis(asserted_object="血压", assertion_text="ALT 5", locator_id="loc-1", source_text_sha256="a"*64), stable_identity=_stable_fact, revision=1, created_at=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC)
    )
    snap = fact_semantic_snapshot(fact)
    assert snap["fact_type"] == "vital_sign"
    assert snap["supported_requirement_ids"] == []
    assert "fact_id" not in snap and "run_id" not in snap and "gate_id" not in snap and "revision" not in snap
    j = canonical_json(snap)
    assert hashlib.sha256(j.encode()).hexdigest() == hashlib.sha256(canonical_json(snap).encode()).hexdigest()
    # event
    _dr2 = PartialDateRange(source_text="2026-03-01", precision=DatePrecision.DAY, lower_bound="2026-03-01", upper_bound="2026-03-01")
    _stable_event = _ces(authority=_auth, event_type="diagnosis", referenced_fact_objects=["vital_sign:血压"], start_range=_dr2, end_range=None, duration_status=DurationStatus.ONGOING, profile_lane=ProfileLane.EVIDENCE_QUALITY)
    event = ClinicalEventV2(event_id="e1", run_id="r1", gate_id="g1", authority=_auth, event_type="diagnosis", start_range=_dr2, end_range=None, duration_status=DurationStatus.ONGOING, record_time=None, fact_ids=["f1"], referenced_fact_objects=["vital_sign:血压"], locator_ids=["loc-1"], source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE, stable_identity=_stable_event, revision=1, created_at=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC))
    esnap = event_semantic_snapshot(event)
    assert esnap["event_type"] == "diagnosis"
    assert "event_id" not in esnap
    # exposure
    _stable_exp = _mes(authority=_auth, medication_name="二甲双胍", category="降糖药", indication="糖尿病", dose="500", unit="mg", frequency="bid", route="口服", start_range=None, end_range=None, duration_status=DurationStatus.ONGOING)
    exp = MedicationExposureV2(exposure_id="ex1", run_id="r1", gate_id="g1", authority=_auth, medication_name="二甲双胍", category="降糖药", indication="糖尿病", dose="500", unit="mg", frequency="bid", route="口服", start_range=None, end_range=None, duration_status=DurationStatus.ONGOING, record_time=None, fact_ids=["f1"], locator_ids=["loc-1"], source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE, stable_identity=_stable_exp, revision=1, created_at=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC))
    exsnap = exposure_semantic_snapshot(exp)
    assert exsnap["medication_name"] == "二甲双胍"
    assert "exposure_id" not in exsnap


def test_supported_requirement_ids_change_snapshot_hash_and_idempotency():
    _auth = _authority()
    _dr = PartialDateRange(
        source_text="2026-03-01",
        precision=DatePrecision.DAY,
        lower_bound="2026-03-01",
        upper_bound="2026-03-01",
    )
    from app.domain.contracts.facts import clinical_fact_stable_identity as _cfs

    stable = _cfs(
        authority=_auth,
        fact_type="vital_sign",
        asserted_object="血压",
        polarity=FactPolarity.AFFIRMED,
        value="120/80",
        unit="unitless",
        date_range=_dr,
    )
    common = dict(
        run_id="r1",
        gate_id="g1",
        authority=_auth,
        fact_type="vital_sign",
        polarity=FactPolarity.AFFIRMED,
        asserted_object="血压",
        value="120/80",
        unit="unitless",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        date_range=_dr,
        record_time=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC),
        locator_ids=["loc-1"],
        assertion_basis=AssertionBasis(
            asserted_object="血压",
            assertion_text="ALT 5",
            locator_id="loc-1",
            source_text_sha256="a" * 64,
        ),
        stable_identity=stable,
        revision=1,
        created_at=datetime(2026, 8, 23, 7, 0, 0, tzinfo=UTC),
    )
    old_fact = ClinicalFactV2(fact_id="f-old", supported_requirement_ids=[], **common)
    new_fact = ClinicalFactV2(
        fact_id="f-new",
        supported_requirement_ids=["req-1"],
        **common,
    )
    old_snap = fact_semantic_snapshot(old_fact)
    new_snap = fact_semantic_snapshot(new_fact)
    assert old_snap["supported_requirement_ids"] == []
    assert new_snap["supported_requirement_ids"] == ["req-1"]
    old_json = canonical_json(old_snap)
    new_json = canonical_json(new_snap)
    old_sha = hashlib.sha256(old_json.encode()).hexdigest()
    new_sha = hashlib.sha256(new_json.encode()).hexdigest()
    assert old_sha != new_sha
    shared = dict(
        authority=_auth,
        target_kind="fact",
        target_id="f-old",
        target_stable_identity=stable,
        target_revision=1,
        new_entity_id="f-new",
        new_stable_identity=stable,
        new_revision=2,
        reason="只改资料要求绑定",
        locator_ids=["loc-1"],
        operator_id="op-1",
        old_snapshot_sha256=old_sha,
        new_snapshot_sha256=new_sha,
    )
    changed_key = fact_correction_idempotency_key(**shared)
    reused_old = fact_correction_idempotency_key(
        **{**shared, "new_snapshot_sha256": old_sha}
    )
    assert changed_key != reused_old
