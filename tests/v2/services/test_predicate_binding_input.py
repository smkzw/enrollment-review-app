"""R01 绑定链冻结输入构建器测试（隔离临时库 + 合成资料，设计 §17.1.1 第 1 步）。

复用既有已验证种子与仓储边界：

- ``tests.v2.storage.test_fact_repositories`` 的 ``_seed_chain``/``_fact``（真实
  Phase 4 证据链 + 发布候选/门禁/事实仓储边界）；
- ``FactCorrectionRepository``/``FactCorrectionV2``（真实校正排除链）；
- ``EvidenceLocatorRepository``/``FactAuthorityValidator``（读取即来源核验）。

覆盖：合法冻结、乱序同哈希、校正导致哈希变化、不同对象同值不合并、缺定位、
跨节点/跨权威拒绝、重复身份冲突与伪造来源拒绝。全部为确定性测试：不调用模型、
不写原临床库、不接消费链。
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from app.domain.contracts.enums import (
    FactGate,
    FactPolarity,
    GateOutcome,
    LocatorAuthenticity,
    LocatorPrecision,
    LocatorSourceLayer,
    ProfileLane,
    RuleKind,
    SourceStrength,
    StudyPhase,
)
from app.domain.contracts.fact_corrections import (
    FactCorrectionImpactScope,
    FactCorrectionV2,
    canonical_json,
    fact_correction_idempotency_key,
    fact_semantic_snapshot,
)
from app.domain.contracts.facts import (
    AssertionBasis,
    ClinicalFactCandidateV2,
    ClinicalFactV2,
    FactAuthority,
    FactGateResult,
    clinical_fact_stable_identity,
)
from app.domain.contracts.predicate_binding import (
    FrozenFactRecord,
    FrozenLocatorIdentity,
    FrozenPredicateIdentity,
    PredicateBindingFrozenInput,
    predicate_binding_frozen_input_sha256,
    predicate_component_identity_sha256,
    predicate_identity_sha256,
)
from app.domain.contracts.predicate_binding import FrozenRuleComponent
from app.domain.contracts.rules import AtomicPredicate, AtomicExpression, LogicalExpression
from app.domain.contracts.review import ReviewEpisode
from app.services.evidence_app_errors import AppStaleAuthorityError
from app.services.predicate_binding_input import (
    PredicateBindingInputError,
    build_predicate_binding_frozen_input,
)
from app.storage.fact_authority import FactLocatorReferenceError
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactGateResultRepository,
    FactNormalizationCandidateRepository,
)
from app.storage.ocr_models import OCRPageRecord
from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
from app.storage.repositories import InvalidReferenceError, NotFoundError
from tests.v2.storage.test_fact_repositories import (
    _basis,
    _date_range,
    _fact,
    _seed_chain,
)

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _publish_fact(session, ids: dict, **overrides) -> ClinicalFactV2:
    """经真实发布仓储边界落一条事实（候选/门禁语义与既有种子一致）。"""
    return ClinicalFactV2Repository(session).create(_fact(ids, **overrides))


def _publish_variant_fact(
    session, ids: dict, suffix: str, *, asserted_object: str = "血压", value: str = "120/80"
) -> ClinicalFactV2:
    """同 run/call 下追加一条不同语义候选 + 门禁 + 发布事实。"""
    candidate_id = f"{ids['run_id']}-cand-{suffix}"
    gate_id = f"{ids['run_id']}-gate-{suffix}"
    locator_record = session.get(EvidenceLocatorArtifactRecord, ids["locator_id"])
    assert locator_record is not None
    basis = AssertionBasis(
        asserted_object=asserted_object,
        assertion_text=locator_record.excerpt or "",
        locator_id=ids["locator_id"],
        source_text_sha256=locator_record.source_text_sha256,
    )
    FactNormalizationCandidateRepository(session).create(
        ids["call_id"],
        ClinicalFactCandidateV2(
            candidate_id=candidate_id,
            run_id=ids["run_id"],
            call_id=ids["call_id"],
            fact_type="vital_sign",
            polarity=FactPolarity.AFFIRMED,
            asserted_object=asserted_object,
            raw_value=value,
            canonical_value=value,
            unit="unitless",
            date_range=_date_range(),
            record_time=NOW,
            locator_ids=[ids["locator_id"]],
            candidate_source_semantics="objective_result",
            assertion_basis=basis,
            model_uncertainty=0.01,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=ids["run_id"],
            call_id=ids["call_id"],
            candidate_id=candidate_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    return _publish_fact(
        session,
        ids,
        fact_id=f"{ids['run_id']}-fact-{suffix}",
        gate_id=gate_id,
        source_candidate_ids=[candidate_id],
        gate_ids=[gate_id],
        asserted_object=asserted_object,
        value=value,
        assertion_basis=basis,
    )


def _correction_for_facts(
    old_fact: ClinicalFactV2,
    new_fact: ClinicalFactV2,
    locator_ids: list[str],
    *,
    correction_id: str = "pbi-corr-1",
) -> FactCorrectionV2:
    old_json = canonical_json(fact_semantic_snapshot(old_fact))
    new_json = canonical_json(fact_semantic_snapshot(new_fact))
    reason = "核对原文后校正数值"
    return FactCorrectionV2(
        correction_id=correction_id,
        authority=old_fact.authority,
        target_kind="fact",
        target_id=old_fact.fact_id,
        target_stable_identity=old_fact.stable_identity,
        new_stable_identity=new_fact.stable_identity,
        target_revision=old_fact.revision,
        new_entity_id=new_fact.fact_id,
        new_revision=new_fact.revision,
        old_snapshot_json=old_json,
        old_snapshot_sha256=_sha(old_json),
        new_snapshot_json=new_json,
        new_snapshot_sha256=_sha(new_json),
        reason=reason,
        locator_ids=sorted(locator_ids),
        operator_id="op-1",
        corrected_at=NOW,
        created_at=NOW,
        impact_scope=FactCorrectionImpactScope(
            scope_kind="local",
            affected_locator_ids=sorted(locator_ids),
            affected_fact_ids=[old_fact.fact_id],
        ),
        idempotency_key=fact_correction_idempotency_key(
            authority=old_fact.authority,
            target_kind="fact",
            target_id=old_fact.fact_id,
            target_stable_identity=old_fact.stable_identity,
            target_revision=old_fact.revision,
            new_entity_id=new_fact.fact_id,
            new_stable_identity=new_fact.stable_identity,
            new_revision=new_fact.revision,
            old_snapshot_sha256=_sha(old_json),
            new_snapshot_sha256=_sha(new_json),
            reason=reason,
            locator_ids=sorted(locator_ids),
            operator_id="op-1",
        ),
    )


_COMPONENT_FIELDS = dict(
    parent_rule_id="rule-ex-01",
    official_code="EX-01",
    kind=RuleKind.EXCLUSION,
    display_code="1",
    title="合成组件",
    rule_source_text="合成排除原文",
)


def _frozen_predicate(
    predicate_id: str,
    *,
    component_id: str = "component-a",
    source_clause: str | None = None,
) -> FrozenPredicateIdentity:
    predicate = AtomicPredicate(
        predicate_id=predicate_id,
        subject="laboratory",
        attribute="target_ratio_uln",
        comparator="exists",
        source_clause=source_clause,
    )
    return FrozenPredicateIdentity(
        predicate_id=predicate_id,
        role="trigger",
        rule_component_id=component_id,
        parent_rule_id=_COMPONENT_FIELDS["parent_rule_id"],
        official_code=_COMPONENT_FIELDS["official_code"],
        predicate=predicate,
        time_constraint=None,
        predicate_identity_sha256=predicate_identity_sha256(
            role="trigger",
            rule_component_id=component_id,
            parent_rule_id=_COMPONENT_FIELDS["parent_rule_id"],
            official_code=_COMPONENT_FIELDS["official_code"],
            predicate=predicate,
            time_constraint=None,
        ),
    )


def _component_contract(
    predicate_ids: list[str],
    component_id: str,
    *,
    source_clause: str | None = None,
    operator: str = "all",
):
    predicates = [
        _frozen_predicate(
            item, component_id=component_id, source_clause=source_clause
        )
        for item in predicate_ids
    ]
    atoms = [AtomicExpression(predicate=item.predicate) for item in predicates]
    expression = atoms[0] if len(atoms) == 1 else LogicalExpression(operator=operator, children=atoms)
    return FrozenRuleComponent(
        rule_component_id=component_id,
        **_COMPONENT_FIELDS,
        expression=expression,
        exception_expression=None,
        evidence_requirements=[],
        trigger_predicates=predicates,
        exception_predicates=[],
        component_identity_sha256=predicate_component_identity_sha256(
            rule_component_id=component_id,
            **_COMPONENT_FIELDS,
            expression=expression,
            exception_expression=None,
            evidence_requirements=[],
            trigger_predicates=predicates,
            exception_predicates=[],
        ),
    )


def _fact_record(
    fact_id: str,
    stable_identity: str,
    locator_ids: list[str],
) -> FrozenFactRecord:
    return FrozenFactRecord(
        fact_id=fact_id,
        stable_identity=stable_identity,
        revision=1,
        fact_type="vital_sign",
        profile_lane=ProfileLane.EVIDENCE_QUALITY,
        asserted_object="血压",
        polarity=FactPolarity.AFFIRMED,
        value="120/80",
        unit="unitless",
        source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
        locator_ids=locator_ids,
    )


def _locator_record(locator_id: str) -> FrozenLocatorIdentity:
    return FrozenLocatorIdentity(
        locator_id=locator_id,
        page_artifact_id=f"{locator_id}-pa",
        source_document_version_id=f"{locator_id}-doc",
        page_number=1,
        source_layer=LocatorSourceLayer.RAW_OCR,
        source_text_sha256=_sha(locator_id),
        precision=LocatorPrecision.TEXT_RANGE,
        authenticity=LocatorAuthenticity.DEGRADED,
        target_id=f"{locator_id}-target",
        text_start=0,
        text_end=5,
        excerpt="ALT 5",
        degradation_reason="仅有文本范围",
    )


def _frozen_input(components, facts, locators, *, anchor_dates=None, stage="screening") -> PredicateBindingFrozenInput:
    authority = _authority()
    episode = ReviewEpisode(
        project_id=authority.project_id, subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id, rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision, protocol_version_id=authority.protocol_version_id,
        study_phase=StudyPhase.PHASE_III, stage=stage,
        revision=authority.episode_revision,
        anchor_dates=anchor_dates or {},
        active_evidence_snapshot_id=authority.evidence_snapshot_v2_id,
        active_evidence_processing_revision_id=authority.complete_processing_revision_id,
    )
    return PredicateBindingFrozenInput(
        authority=authority,
        episode=episode,
        rule_set_id=authority.rule_set_id,
        rule_set_revision=authority.rule_set_revision,
        protocol_version_id=authority.protocol_version_id,
        study_phase=StudyPhase.PHASE_III,
        components=components,
        facts=facts,
        locators=locators,
        frozen_input_sha256=predicate_binding_frozen_input_sha256(
            authority=authority,
            episode=episode,
            rule_set_id=authority.rule_set_id,
            rule_set_revision=authority.rule_set_revision,
            protocol_version_id=authority.protocol_version_id,
            study_phase=StudyPhase.PHASE_III,
            components=components,
            facts=facts,
            locators=locators,
        ),
    )


def _authority(**overrides) -> FactAuthority:
    base = dict(
        project_id="proj",
        subject_id="subj",
        review_episode_id="episode",
        episode_revision=1,
        protocol_version_id="protocol-v1",
        rule_set_id="ruleset-synthetic-phase-iii",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snapshot",
        complete_processing_revision_id="complete",
    )
    base.update(overrides)
    return FactAuthority(**base)


# --------------------------------------------------------------------------- 合同层


def test_out_of_order_construction_yields_identical_hash():
    first = _frozen_input(
        components=[
            _component_contract(["p-1", "p-2"], "component-a"),
            _component_contract(["p-3"], "component-b"),
        ],
        facts=[
            _fact_record("fact-1", _sha("identity-1"), ["loc-1"]),
            _fact_record("fact-2", _sha("identity-2"), ["loc-2"]),
        ],
        locators=[_locator_record("loc-1"), _locator_record("loc-2")],
    )
    second = _frozen_input(
        components=[
            _component_contract(["p-3"], "component-b"),
            _component_contract(["p-2", "p-1"], "component-a"),
        ],
        facts=[
            _fact_record("fact-2", _sha("identity-2"), ["loc-2"]),
            _fact_record("fact-1", _sha("identity-1"), ["loc-1"]),
        ],
        locators=[_locator_record("loc-2"), _locator_record("loc-1")],
    )
    assert first.frozen_input_sha256 == second.frozen_input_sha256


def test_duplicate_stable_identity_conflict_is_rejected():
    with pytest.raises(ValidationError, match="重复身份冲突"):
        _frozen_input(
            components=[_component_contract(["p-1"], "component-a")],
            facts=[
                _fact_record("fact-1", _sha("same-identity"), ["loc-1"]),
                _fact_record("fact-2", _sha("same-identity"), ["loc-1"]),
            ],
            locators=[_locator_record("loc-1")],
        )


def test_different_objects_same_value_are_separate_records():
    identity_a = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="vital_sign",
        asserted_object="血压",
        polarity=FactPolarity.AFFIRMED,
        value="120/80",
        unit="unitless",
        date_range=None,
    )
    identity_b = clinical_fact_stable_identity(
        authority=_authority(),
        fact_type="vital_sign",
        asserted_object="静息心率",
        polarity=FactPolarity.AFFIRMED,
        value="120/80",
        unit="unitless",
        date_range=None,
    )
    assert identity_a != identity_b
    frozen = _frozen_input(
        components=[_component_contract(["p-1"], "component-a")],
        facts=[
            _fact_record("fact-1", identity_a, ["loc-1"]),
            FrozenFactRecord(
                fact_id="fact-2",
                stable_identity=identity_b,
                revision=1,
                fact_type="vital_sign",
                profile_lane=ProfileLane.EVIDENCE_QUALITY,
                asserted_object="静息心率",
                polarity=FactPolarity.AFFIRMED,
                value="120/80",
                unit="unitless",
                source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
                locator_ids=["loc-1"],
            ),
        ],
        locators=[_locator_record("loc-1")],
    )
    assert {item.asserted_object for item in frozen.facts} == {"血压", "静息心率"}
    assert len(frozen.facts) == 2


def test_fact_referencing_absent_locator_is_rejected():
    with pytest.raises(ValidationError, match="不在冻结输入内的定位"):
        _frozen_input(
            components=[_component_contract(["p-1"], "component-a")],
            facts=[_fact_record("fact-1", _sha("i-1"), ["loc-missing"])],
            locators=[_locator_record("loc-1")],
        )


def test_predicate_source_must_be_verbatim_published_rule_text():
    with pytest.raises(ValidationError, match="原文定位"):
        _component_contract(
            ["p-1"], "component-a", source_clause="伪造且不属于规则原文"
        )


def test_missing_predicate_source_is_explicitly_unverified():
    component = _component_contract(["p-1"], "component-a")
    assert component.trigger_predicates[0].source_status == "unverified"


def test_present_predicate_source_is_marked_verbatim():
    component = _component_contract(
        ["p-1"], "component-a", source_clause="合成排除原文"
    )
    assert component.trigger_predicates[0].source_status == "verbatim"


# --------------------------------------------------------------------------- 服务层


def test_legal_freeze_builds_deterministic_frozen_input(session):
    ids = _seed_chain(session, "pbi-legal")
    _publish_fact(session, ids)
    frozen = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    assert frozen.binding_input_version == "predicate-binding-frozen-input/v2"
    from app.storage.evidence_repositories import SourceDocumentRepository
    assert frozen.documents is not None
    assert {item.source_document_version_id for item in frozen.documents} == {
        item.source_document_version_id for item in frozen.locators}
    for item in frozen.documents:
        source = SourceDocumentRepository(session).get(item.source_document_version_id)
        assert item.file_name == source.file_name
        assert item.media_type == source.media_type
        assert item.source_blob_sha256 == source.source_blob_sha256
    assert frozen.authority == ids["authority"]
    assert frozen.rule_set_id == ids["authority"].rule_set_id
    assert [item.rule_component_id for item in frozen.components] == [
        "component-ex-01"
    ]
    component = frozen.components[0]
    assert component.official_code == "EX-01"
    assert component.kind == RuleKind.EXCLUSION
    assert component.rule_source_text
    trigger_ids = {item.predicate_id for item in component.trigger_predicates}
    assert {
        "predicate-investigator-unacceptable_participation_risk-eq",
        "predicate-laboratory-target_ratio_uln-gte",
        "predicate-medication-prohibited-window",
        "predicate-laboratory-critical_measurement_invalid-eq",
    } <= trigger_ids
    medication = next(
        item
        for item in component.trigger_predicates
        if item.predicate_id == "predicate-medication-prohibited-window"
    )
    assert medication.time_constraint is not None
    assert medication.time_constraint.upper_bound_days == 28
    assert medication.role == "trigger"
    assert medication.source_status == "unverified"
    investigator = next(
        item
        for item in component.trigger_predicates
        if item.predicate_id == "predicate-investigator-unacceptable_participation_risk-eq"
    )
    assert investigator.source_status == "unverified"
    assert {item.predicate_id for item in component.exception_predicates} == {
        "predicate-exception-protocol_exception_documented-eq",
        "predicate-investigator-exception_confirmed-eq",
    }
    assert all(item.role == "exception" for item in component.exception_predicates)
    assert [(item.asserted_object, item.value) for item in frozen.facts] == [
        ("血压", "120/80")
    ]
    assert frozen.facts[0].locator_ids == [ids["locator_id"]]
    locator = frozen.locators[0]
    assert locator.locator_id == ids["locator_id"]
    assert locator.excerpt == "ALT 5"
    assert locator.source_layer == LocatorSourceLayer.RAW_OCR
    rebuilt = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    assert rebuilt.frozen_input_sha256 == frozen.frozen_input_sha256
    whole = build_predicate_binding_frozen_input(session, ids["review_episode_id"])
    assert len(whole.components) == 7
    assert whole.frozen_input_sha256 != frozen.frozen_input_sha256


def test_correction_changes_frozen_input_and_does_not_revive_old_value(session):
    ids = _seed_chain(session, "pbi-corr")
    old_fact = _publish_fact(session, ids)
    before = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    corrected = _publish_variant_fact(
        session,
        ids,
        "corrected",
        asserted_object="血压",
        value="130/85",
    )
    assert corrected.stable_identity != old_fact.stable_identity
    FactCorrectionRepository(session).create(
        _correction_for_facts(old_fact, corrected, [ids["locator_id"]])
    )
    after = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    assert after.frozen_input_sha256 != before.frozen_input_sha256
    assert [item.fact_id for item in after.facts] == [corrected.fact_id]
    assert [item.value for item in after.facts] == ["130/85"]
    assert old_fact.fact_id not in {item.fact_id for item in after.facts}


def test_different_objects_same_value_publish_separately(session):
    ids = _seed_chain(session, "pbi-obj")
    _publish_fact(session, ids)
    second = _publish_variant_fact(session, ids, "hr", asserted_object="静息心率")
    frozen = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    assert len(frozen.facts) == 2
    by_object = {item.asserted_object: item for item in frozen.facts}
    assert set(by_object) == {"血压", "静息心率"}
    assert by_object["血压"].stable_identity != by_object["静息心率"].stable_identity
    assert by_object["血压"].value == by_object["静息心率"].value == "120/80"
    assert second.fact_id in {item.fact_id for item in frozen.facts}


def test_missing_locator_reference_is_rejected(session):
    ids = _seed_chain(session, "pbi-miss")
    ghost = _fact(
        ids,
        fact_id=f"{ids['run_id']}-ghost",
        locator_ids=["pbi-missing-locator"],
    )
    with pytest.raises(NotFoundError, match="pbi-missing-locator"):
        build_predicate_binding_frozen_input(
            session, ids["review_episode_id"], fact_heads=[ghost]
        )


def test_cross_authority_fact_is_rejected(session):
    ids_a = _seed_chain(session, "pbi-a")
    ids_b = _seed_chain(session, "pbi-b", fixture_index=1)
    fact_b = _fact(ids_b)
    with pytest.raises(PredicateBindingInputError, match="跨 authority"):
        build_predicate_binding_frozen_input(
            session, ids_a["review_episode_id"], fact_heads=[fact_b]
        )


def test_cross_node_locator_is_rejected(session):
    ids_a = _seed_chain(session, "pbi-xa")
    ids_b = _seed_chain(session, "pbi-xb", fixture_index=1)
    borrowed = _fact(ids_a, locator_ids=[ids_b["locator_id"]])
    with pytest.raises(FactLocatorReferenceError, match="跨审核节点"):
        build_predicate_binding_frozen_input(
            session, ids_a["review_episode_id"], fact_heads=[borrowed]
        )


def test_tampered_ocr_source_is_rejected_on_read(session):
    """DB 级篡改 OCR 原文：镜像校验先于定位核验拒绝（伪造来源不产生冻结输入）。"""
    ids = _seed_chain(session, "pbi-forge")
    _publish_fact(session, ids)
    ocr_page_id = session.get(
        EvidenceLocatorArtifactRecord, ids["locator_id"]
    ).ocr_page_id
    session.execute(
        update(OCRPageRecord)
        .where(OCRPageRecord.ocr_page_id == ocr_page_id)
        .values(raw_text="ALT 9.9 mmol/L 且 AST 9.9 mmol/L")
    )
    with pytest.raises(AppStaleAuthorityError) as excinfo:
        build_predicate_binding_frozen_input(session, ids["review_episode_id"])
    assert any(
        "闭包不完整" in str(arg)
        for arg in excinfo.value.__cause__.args
    )


def test_duplicate_identity_conflict_is_rejected_not_chosen(session):
    ids = _seed_chain(session, "pbi-dup")
    first = _fact(ids, fact_id="dup-a")
    second = _fact(ids, fact_id="dup-b")
    with pytest.raises(InvalidReferenceError, match="相同修订号"):
        build_predicate_binding_frozen_input(
            session, ids["review_episode_id"], fact_heads=[first, second]
        )


@pytest.mark.parametrize("change", [{"value": "999"}, {"asserted_object": "其他对象"}])
def test_supplied_fact_cannot_change_published_content(session, change):
    ids = _seed_chain(session, "pbi-supplied-change")
    published = _publish_fact(session, ids)
    changed = published.model_copy(update=change)
    with pytest.raises(PredicateBindingInputError, match="已发布事实"):
        build_predicate_binding_frozen_input(
            session, ids["review_episode_id"], fact_heads=[changed]
        )


def test_supplied_facts_cannot_hide_current_published_facts(session):
    ids = _seed_chain(session, "pbi-supplied-empty")
    _publish_fact(session, ids)
    with pytest.raises(PredicateBindingInputError, match="已发布事实"):
        build_predicate_binding_frozen_input(
            session, ids["review_episode_id"], fact_heads=[]
        )


def test_supplied_published_facts_have_same_identity_as_repository_read(session):
    ids = _seed_chain(session, "pbi-supplied-valid")
    published = _publish_fact(session, ids)
    loaded = build_predicate_binding_frozen_input(session, ids["review_episode_id"])
    supplied = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], fact_heads=[published]
    )
    assert supplied.frozen_input_sha256 == loaded.frozen_input_sha256


def test_boolean_operator_changes_frozen_identity():
    conjunction = _component_contract(["a", "b"], "component-a", operator="all")
    disjunction = _component_contract(["a", "b"], "component-a", operator="any")
    assert conjunction.component_identity_sha256 != disjunction.component_identity_sha256
    assert _frozen_input([conjunction], [], []).frozen_input_sha256 != _frozen_input([disjunction], [], []).frozen_input_sha256


def test_source_status_cannot_claim_verbatim_without_source():
    payload = _frozen_predicate("missing-source").model_dump(mode="json")
    payload["source_status"] = "verbatim"
    with pytest.raises(ValidationError, match="原文核实标记"):
        FrozenPredicateIdentity.model_validate(payload)


def test_review_stage_and_dates_are_part_of_frozen_identity():
    component = _component_contract(["a"], "component-a")
    first = _frozen_input([component], [], [])
    dated = _frozen_input([component], [], [], anchor_dates={
        "screening_date": {"value": "2026-09-01", "precision": "day"}
    })
    baseline = _frozen_input([component], [], [], stage="baseline")
    assert len({first.frozen_input_sha256, dated.frozen_input_sha256, baseline.frozen_input_sha256}) == 3


def test_review_episode_revision_must_match_authority():
    frozen = _frozen_input([_component_contract(["a"], "component-a")], [], [])
    payload = frozen.model_dump(mode="json")
    payload["episode"]["revision"] += 1
    with pytest.raises(ValidationError, match="审核节点活动资料"):
        PredicateBindingFrozenInput.model_validate(payload)


def test_atom_time_must_match_expression_time(session):
    ids = _seed_chain(session, "pbi-time-mismatch")
    frozen = build_predicate_binding_frozen_input(
        session, ids["review_episode_id"], component_ids=["component-ex-01"]
    )
    payload = frozen.components[0].model_dump(mode="json")
    item = next(p for p in payload["trigger_predicates"] if p["time_constraint"])
    item["time_constraint"] = None
    item["predicate_identity_sha256"] = predicate_identity_sha256(
        role=item["role"], rule_component_id=item["rule_component_id"],
        parent_rule_id=item["parent_rule_id"], official_code=item["official_code"],
        predicate=AtomicPredicate.model_validate(item["predicate"]), time_constraint=None,
    )
    with pytest.raises(ValidationError, match="表达式与谓词清单"):
        FrozenRuleComponent.model_validate(payload)
