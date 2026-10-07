"""跨章未决来源陈述的受限合同：v3 保留、旧版不携带、序列化往返。

对应现行 R1 设计与受限采用结论：完整有源但含义未决的跨章陈述必须能在同一冻结发布
身份里忠实保留（原文单元/陈述序号/逐字摘录/片段、未决种类、显式依赖），不得被简化
成可执行控制，也不得让旧版本目录静默携带；v1/v2 旧字节保持原样。

本文件只测领域合同，不测发布服务、门禁、投影或界面。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.control_catalog_publication import (
    ControlCatalogPublication,
    control_catalog_publication_id,
)
from app.domain.contracts.enums import ReviewStage, StudyPhase
from app.domain.contracts.clause_pack import ClausePack
from app.domain.contracts.enums import RuleKind
from app.domain.contracts.rules import AtomicExpression, AtomicPredicate, Rule, RuleComponent, RuleSet
from app.domain.publication import canonical_hash
from app.projections.clause_pack import project_clause_pack, verify_clause_pack
from app.services.frozen_review_calculation import _definition_records_for_review
from app.services.eligibility_review_projection import _restricted_control_projections
from app.agents.protocol_control_deconstructor import (
    ProtocolControlAgentAttempt, ProtocolControlAgentRunResult,
    hydrate_protocol_control_agent_output,
)
from app.agents.protocol_control_source_interpretation import (
    SOURCE_INTERPRETATION_VERSION, SOURCE_TARGET_REVIEW_VERSION,
    SourceInterpretation, SourceStatementCoverage, SourceTargetReview,
)
from app.protocols.protocol_control_gate import (
    check_protocol_control_batch_candidates,
    locate_source_quote_offsets,
)
from app.services.protocol_control_restricted_source import restricted_batch_from_review
from tests.v2.protocols.test_slice58c_control_deconstructor import (
    _batch, _candidate, _wire,
)
from app.domain.contracts.protocol_controls import (
    ControlMinimumEvidence,
    ControlObligationAtom,
    ControlObligationKind,
    ProtocolControlDefinitionAtomConsumption,
    ProtocolControlDefinitionConsumerRecord,
    ProtocolReviewControl,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlUnitDisposition,
    PublishedProtocolControlCatalog,
    RestrictedProtocolControlStatement,
    RestrictedStatementIndependentExcerpt,
    RestrictedStatementScopeProof,
    ReviewNodeBinding,
    ReviewNodeRole,
    StructureUnitDisposition,
    StructureUnitDispositionKind,
)
from tests.v2.protocols.test_slice58c_protocol_control_gate import (
    _catalog as _gate_catalog, _gate, _manifest, _paragraph_unit, _plan,
    _workflow_targets,
)

_PROTOCOL = "protocol-generic"
_STAGE_MAP = {"stage:screening": "rules-generic:1:stage:screening"}
_CREATED_AT = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
_QUOTE = "既往接受过前一阶段治疗者不得入组"
_DIMENSION = "“前一阶段”指哪个治疗阶段尚未核清"

#: v1/v2 目录正文的既有键集合；新增键会改变旧发布身份，必须被本测试挡住。
_LEGACY_CATALOG_KEYS = {
    "allowed_source_span_ids",
    "catalog_id",
    "controls",
    "coverage_manifest_id",
    "protocol_document_sha256",
    "protocol_version_id",
    "schema_version",
    "study_phase",
}


def _unresolved_batch_review():
    batch = _batch()
    quotes = ["年龄至少18岁", "筛选时记录末次用药日期"]
    interpretation = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [
            {
                "structure_unit_id": unit.structure_unit_id,
                "quoted_text": quote,
                "force": "required",
                "decision_functions": ["action"],
                "time_words": [],
                "unresolved": ["适用对象未核清"],
            }
            for unit, quote in zip(batch.owned_units, quotes, strict=True)
        ],
        "units_without_statement": [],
    })
    coverage = [SourceStatementCoverage(
        statement_index=index, structure_unit_id=unit.structure_unit_id,
        disposition="other_control_candidate", status="not_located",
    ) for index, unit in enumerate(batch.owned_units)]
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": index, "decision": "unresolved",
            "source_action_excerpt": quote,
            "unresolved_aspects": ["与已有目标的关系未核清"],
        } for index, quote in enumerate(quotes)],
    })
    result = ProtocolControlAgentRunResult(
        status="需要核对", batch_id=batch.batch_id, session_id="test",
        attempts=[ProtocolControlAgentAttempt(
            attempt=1, session_id="test", raw_output_sha256="a" * 64,
            outcome="publication_invalid",
            error_classes=["SOURCE_TARGET_REVIEW_UNRESOLVED"],
        )],
        source_interpretation=interpretation,
        source_statement_coverage=coverage,
        source_target_review=review,
    )
    return batch, result


def test_unresolved_review_preserves_source_without_adopting_candidate() -> None:
    batch, result = _unresolved_batch_review()
    restricted = restricted_batch_from_review(batch, result)
    assert restricted is not None
    assert restricted.candidates == []
    assert len(restricted.restricted_statements) == 2
    assert all(item.disposition.value == "restricted_source" for item in restricted.dispositions)
    assert restricted.model_dump(mode="json")["restricted_statements"]

    resolved = result.model_copy(deep=True)
    resolved.source_interpretation.statements[0].unresolved = []
    assert restricted_batch_from_review(batch, resolved) is None

    invented = result.model_copy(deep=True)
    invented.source_interpretation.statements[0].quoted_text = "不存在的原文"
    with pytest.raises(ValueError, match="陈述摘录"):
        restricted_batch_from_review(batch, invented)
    transport_failed = result.model_copy(deep=True)
    transport_failed.attempts[-1].outcome = "transport_failed"
    assert restricted_batch_from_review(batch, transport_failed) is None


def test_restricted_source_requires_matching_frozen_batch_and_quote() -> None:
    text = "上一阶段记录均需核实；任一异常不得入组"
    unit = _paragraph_unit("su-control", "span:control", 1, text)
    manifest = _manifest(units=[unit], dispositions=[StructureUnitDisposition(
        structure_unit_id=unit.structure_unit_id,
        disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
    )])
    workflow = _workflow_targets()
    plan = _plan(manifest, workflow)
    batch = plan.batches[0]
    statement = _restricted_statement(
        "restricted:generic", unit_id=unit.structure_unit_id,
        quote="任一异常不得入组", spans=("span:control",),
    )
    result = ProtocolControlBatchDispositionHydrated(
        batch_id=batch.batch_id, coverage_manifest_id=manifest.manifest_id,
        owned_structure_unit_ids=list(batch.owned_structure_unit_ids),
        owned_source_span_ids=list(batch.owned_source_span_ids),
        dispositions=[ProtocolControlUnitDisposition(
            structure_unit_id=unit.structure_unit_id,
            disposition=StructureUnitDispositionKind.RESTRICTED_SOURCE,
        )],
        restricted_statements=[statement],
    )
    catalog = _gate_catalog([], allowed_spans=["span:control"]).model_copy(
        update={"restricted_statements": [statement]}
    )
    assert _gate(manifest=manifest, catalog=catalog, plan=plan,
                 batch_dispositions=[result], workflow_targets=workflow) == catalog

    forged = result.model_copy(deep=True)
    forged.restricted_statements[0].source_quote = "原文没有这句话"
    with pytest.raises(ValueError, match="受限陈述必须逐字"):
        _gate(manifest=manifest, catalog=catalog, plan=plan,
              batch_dispositions=[forged], workflow_targets=workflow)


def _statement_payload(**overrides) -> dict:
    payload = {
        "restricted_statement_id": "restricted:batch5-a",
        "source_structure_unit_id": "su-batch5",
        "source_statement_index": 0,
        "source_quote": _QUOTE,
        "source_span_ids": ["span:batch5.p1"],
        "limitation_kind": "interpretation_unresolved",
        "unresolved_dimensions": [_DIMENSION],
    }
    payload.update(overrides)
    return payload


def _restricted_statement(
    statement_id: str,
    *,
    unit_id: str = "su-batch5",
    statement_index: int = 0,
    quote: str = _QUOTE,
    spans: tuple[str, ...] = ("span:batch5.p1",),
    limitation_kind: str = "interpretation_unresolved",
    dimensions: tuple[str, ...] = (_DIMENSION,),
    dependencies: tuple[str, ...] = (),
) -> RestrictedProtocolControlStatement:
    return RestrictedProtocolControlStatement(
        **_statement_payload(
            restricted_statement_id=statement_id,
            source_structure_unit_id=unit_id,
            source_statement_index=statement_index,
            source_quote=quote,
            source_span_ids=sorted(spans),
            limitation_kind=limitation_kind,
            unresolved_dimensions=list(dimensions),
            dependency_refs=sorted(dependencies),
        )
    )


def _published_control(
    *,
    control_id: str = "pc-washout-01",
    candidate_id: str | None = None,
    spans: tuple[str, ...] = ("span:batch5.p1",),
) -> ProtocolReviewControl:
    return ProtocolReviewControl(
        protocol_control_id=control_id,
        display_ordinal=1,
        protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_III,
        title="禁用合并用药洗脱",
        applicable_population="全部拟入组受试者",
        obligations=[
            ControlObligationAtom(
                obligation_id="ob-1",
                kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                statement="首次给药前 4 周内不得使用禁用药物",
            )
        ],
        review_node_bindings=[
            ReviewNodeBinding(
                workflow_stage_id="stage:screening",
                review_stage=ReviewStage.SCREENING,
                role=ReviewNodeRole.EARLY_ATTENTION,
                guidance="筛选时提前关注洗脱期不足风险",
            )
        ],
        minimum_evidence=[
            ControlMinimumEvidence(
                evidence_key="ev:washout-med",
                fact_type="medication_exposure",
                description="用药史或医嘱记录",
                due_stage=ReviewStage.BASELINE,
                required_source_types=["用药记录"],
            )
        ],
        source_span_ids=sorted(spans),
        source_structure_unit_ids=["su-batch5"],
        originating_candidate_id=candidate_id,
    )


def _catalog(
    *,
    restricted: tuple[RestrictedProtocolControlStatement, ...] = (),
    controls: tuple[ProtocolReviewControl, ...] = (),
    allowed: tuple[str, ...] = ("span:batch5.p1", "span:batch5.p2"),
) -> PublishedProtocolControlCatalog:
    return PublishedProtocolControlCatalog(
        catalog_id="catalog-restricted",
        protocol_version_id=_PROTOCOL,
        protocol_document_sha256="d" * 64,
        study_phase=StudyPhase.PHASE_III,
        coverage_manifest_id="manifest-generic",
        allowed_source_span_ids=sorted(allowed),
        controls=list(controls),
        restricted_statements=list(restricted),
    )


def _publication(
    catalog: PublishedProtocolControlCatalog,
    *,
    schema_version: str = "control-catalog/v3",
    records: tuple[ProtocolControlDefinitionConsumerRecord, ...] = (),
    workflow_stage_map: dict[str, str] | None = None,
) -> ControlCatalogPublication:
    return ControlCatalogPublication(
        schema_version=schema_version,
        project_id="project-generic",
        protocol_version_id=_PROTOCOL,
        rule_set_id="rules-generic",
        rule_set_revision=1,
        rule_set_sha256="a" * 64,
        source_job_id="job-generic",
        source_job_payload_sha256="b" * 64,
        source_checkpoint_id="checkpoint-generic",
        source_checkpoint_sha256="c" * 64,
        catalog=catalog,
        definition_consumer_records=list(records),
        workflow_stage_map=workflow_stage_map if workflow_stage_map is not None else {},
        gate_result_id="gate-generic",
        created_at=_CREATED_AT,
    )


def _definition_record(*, scope_complete: bool) -> ProtocolControlDefinitionConsumerRecord:
    return ProtocolControlDefinitionConsumerRecord(
        batch_id="batch-a",
        source_structure_unit_id="su-method",
        source_statement_index=0,
        source_quote="按体表面积计算给药剂量",
        source_span_ids=["span:method"],
        consumers=(
            [
                ProtocolControlDefinitionAtomConsumption(
                    consumer_kind="official_predicate",
                    rule_component_id="component-generic",
                    predicate_id="predicate-generic",
                    consumer_excerpt="按体表面积给药",
                )
            ]
            if scope_complete
            else []
        ),
        scope_complete=scope_complete,
        unresolved_reasons=[] if scope_complete else ["跨批消费者尚未核清"],
    )


# -- 正向：v3 在同一冻结身份内保留受限来源陈述 --------------------------------


def test_v3_publication_preserves_restricted_statements_in_one_identity() -> None:
    ambiguous = _restricted_statement("restricted:batch5-a", statement_index=0)
    dependent = _restricted_statement(
        "restricted:batch5-b",
        statement_index=1,
        quote="不得使用前一阶段允许的补救药物",
        spans=("span:batch5.p2",),
        dimensions=("依赖的“前一阶段”定义尚未核清",),
        dependencies=("restricted:batch5-a",),
    )
    publication = _publication(_catalog(restricted=(ambiguous, dependent)))

    assert publication.schema_version == "control-catalog/v3"
    dumped = publication.model_dump(mode="json")
    statements = dumped["catalog"]["restricted_statements"]
    assert [item["restricted_statement_id"] for item in statements] == [
        "restricted:batch5-a",
        "restricted:batch5-b",
    ]
    assert statements[0]["source_quote"] == _QUOTE
    assert statements[0]["source_statement_index"] == 0
    assert statements[0]["unresolved_dimensions"] == [_DIMENSION]
    assert statements[1]["dependency_refs"] == ["restricted:batch5-a"]
    assert "definition_consumer_records" not in dumped
    assert publication.publication_id == control_catalog_publication_id(dumped)
    assert publication.publication_id.startswith("control-publication:")

    restored = ControlCatalogPublication.model_validate(dumped)
    assert restored == publication
    assert restored.model_dump(mode="json") == dumped
    assert restored.publication_id == publication.publication_id


def test_restricted_statement_participates_in_publication_identity() -> None:
    base = _publication(
        _catalog(restricted=(_restricted_statement("restricted:batch5-a"),))
    )
    changed = _publication(
        _catalog(
            restricted=(
                _restricted_statement(
                    "restricted:batch5-a", dimensions=("另一处未核清",)
                ),
            )
        )
    )
    assert base.publication_id != changed.publication_id


def test_v3_restricted_publication_keeps_definition_records_and_pack_boundary() -> None:
    rule_set = RuleSet(
        rule_set_id="rules-generic", revision=1, protocol_version_id=_PROTOCOL,
        study_phase=StudyPhase.PHASE_III,
        rules=[Rule(
            rule_id="rule-generic", official_code="IN-01", kind=RuleKind.INCLUSION,
            source_text="完成方案要求的检查", study_phase=StudyPhase.PHASE_III,
            components=[RuleComponent(
                rule_component_id="component-generic", parent_rule_id="rule-generic",
                display_code="IN-01-a", title="完成检查",
                expression=AtomicExpression(predicate=AtomicPredicate(
                    predicate_id="predicate-generic", subject="受试者",
                    attribute="检查完成", comparator="exists",
                )),
            )],
        )],
    )
    record = _definition_record(scope_complete=True)
    payload = _publication(
        _catalog(restricted=(_restricted_statement("restricted:batch5-a"),)),
        records=(record,),
    ).model_dump(mode="json", exclude={"publication_id"})
    payload["rule_set_sha256"] = canonical_hash(rule_set.model_dump(mode="json"))
    publication = ControlCatalogPublication.model_validate(payload)
    assert _definition_records_for_review(publication, None) == [record]
    with pytest.raises(ValueError, match="冻结发布版本不一致"):
        _definition_records_for_review(publication, [])

    pack = project_clause_pack(rule_set, control_publication=publication)
    assert pack.projection_version == "clause-pack/v4"
    verify_clause_pack(pack)
    assert ClausePack.model_validate(pack.model_dump(mode="json")) == pack

    old_pack = pack.model_dump(mode="json")
    old_pack["projection_version"] = "clause-pack/v2"
    with pytest.raises(ValidationError, match="有源未决子项"):
        ClausePack.model_validate(old_pack)

    collision = pack.model_dump(mode="json")
    collision["control_publication"]["catalog"]["restricted_statements"][0][
        "restricted_statement_id"
    ] = "component-generic"
    collision["control_publication"].pop("publication_id")
    with pytest.raises(ValidationError, match="身份重复"):
        ClausePack.model_validate(collision)


def test_restricted_control_is_visible_as_protocol_question_not_missing_patient_data() -> None:
    publication = _publication(_catalog(restricted=(
        _restricted_statement("restricted:batch5-a"),
    )))
    control = _restricted_control_projections(publication)[0]
    item = control.obligations[0]
    assert control.source_span_ids == ("span:batch5.p1",)
    assert item.status == "restricted"
    assert item.source_excerpts == (_QUOTE,)
    assert item.fact_refs == ()
    assert item.action_owner == "sponsor_medical_or_project"
    assert "研究者" not in item.reason


def test_independent_published_control_coexists_with_restricted_statement() -> None:
    catalog = _catalog(
        restricted=(
            _restricted_statement("restricted:batch5-outcome", statement_index=1),
        ),
        controls=(_published_control(),),
    )
    dumped = _publication(catalog, workflow_stage_map=_STAGE_MAP).model_dump(
        mode="json"
    )
    assert [
        item["protocol_control_id"] for item in dumped["catalog"]["controls"]
    ] == ["pc-washout-01"]
    assert len(dumped["catalog"]["restricted_statements"]) == 1
    assert set(dumped["catalog"]) == _LEGACY_CATALOG_KEYS | {"restricted_statements"}


# -- 反向：旧版本不得携带，v3 不得空载或夹带未核清定义 ------------------------


def test_legacy_publication_versions_do_not_carry_new_keys() -> None:
    v1 = _publication(_catalog(), schema_version="control-catalog/v1")
    v1_dump = v1.model_dump(mode="json")
    assert set(v1_dump["catalog"]) == _LEGACY_CATALOG_KEYS
    assert "definition_consumer_records" not in v1_dump
    assert "restricted_statements" not in v1_dump["catalog"]
    assert ControlCatalogPublication.model_validate(v1_dump).model_dump(mode="json") == v1_dump

    v2 = _publication(
        _catalog(),
        schema_version="control-catalog/v2",
        records=(_definition_record(scope_complete=True),),
    )
    v2_dump = v2.model_dump(mode="json")
    assert set(v2_dump["catalog"]) == _LEGACY_CATALOG_KEYS
    assert "restricted_statements" not in v2_dump["catalog"]
    assert len(v2_dump["definition_consumer_records"]) == 1
    assert ControlCatalogPublication.model_validate(v2_dump).model_dump(mode="json") == v2_dump


def test_older_publication_versions_cannot_carry_restricted_statements() -> None:
    restricted = (_restricted_statement("restricted:batch5-a"),)
    with pytest.raises(ValidationError, match="旧版控制目录不能携带跨章未决来源陈述"):
        _publication(_catalog(restricted=restricted), schema_version="control-catalog/v1")
    with pytest.raises(ValidationError, match="旧版控制目录不能携带跨章未决来源陈述"):
        _publication(
            _catalog(restricted=restricted),
            schema_version="control-catalog/v2",
            records=(_definition_record(scope_complete=True),),
        )


def test_v3_requires_an_explicit_restricted_statement() -> None:
    with pytest.raises(ValidationError, match="受限控制目录必须显式保留跨章未决来源陈述"):
        _publication(_catalog())


def test_v3_still_rejects_an_unproven_definition_record() -> None:
    with pytest.raises(ValidationError, match="来源定义影响范围尚未核清"):
        _publication(
            _catalog(restricted=(_restricted_statement("restricted:batch5-a"),)),
            records=(_definition_record(scope_complete=False),),
        )


def _restricted_consumer_record(statement):
    return _definition_record(scope_complete=True).model_copy(update={
        "consumers": [ProtocolControlDefinitionAtomConsumption(
            consumer_kind="restricted_statement", restricted_statement_id=statement.restricted_statement_id,
            consumer_excerpt=statement.source_quote,
        )],
    })


def test_v4_restricted_consumer_roundtrips_without_executable_identity():
    statement = _restricted_statement("restricted:generic-consumer")
    record = _restricted_consumer_record(statement)
    catalog = _catalog(restricted=(statement,))
    publication = _publication(catalog, schema_version="control-catalog/v4", records=(record,))
    payload = publication.model_dump(mode="json")
    assert ControlCatalogPublication.model_validate(payload) == publication
    entry = payload["definition_consumer_records"][0]["consumers"][0]
    assert set(entry) == {"schema_version", "consumer_kind", "restricted_statement_id", "consumer_excerpt"}
    assert _definition_records_for_review(publication, None) == [record]
    assert catalog.controls == [] and catalog.restricted_statements == [statement]
    for version in ("control-catalog/v2", "control-catalog/v3"):
        with pytest.raises(ValidationError, match="旧版控制目录不能携带受限来源消费引用"):
            _publication(catalog, schema_version=version, records=(record,))
    with pytest.raises(ValidationError, match="实际受限消费引用"):
        _publication(catalog, schema_version="control-catalog/v4", records=(_definition_record(scope_complete=True),))
    with pytest.raises(ValidationError, match="影响范围尚未核清"):
        _publication(catalog, schema_version="control-catalog/v4", records=(record.model_copy(update={
            "scope_complete": False, "unresolved_reasons": ["定义本身未核清"],
        }),))


@pytest.mark.parametrize("overrides", [
    {"restricted_statement_id": "restricted:foreign"},
    {"consumer_excerpt": "语义相近但不是该条逐字来源"},
])
def test_v4_rejects_foreign_restricted_reference_or_excerpt(overrides):
    statement = _restricted_statement("restricted:generic-consumer")
    record = _restricted_consumer_record(statement)
    record = record.model_copy(update={"consumers": [record.consumers[0].model_copy(update=overrides)]})
    with pytest.raises(ValidationError, match="本目录的原文陈述"):
        _publication(_catalog(restricted=(statement,)), schema_version="control-catalog/v4", records=(record,))


@pytest.mark.parametrize("extra", [
    {"control_candidate_id": "candidate"}, {"predicate_id": "predicate"},
    {"layer": "obligation"}, {"condition_id": "condition"},
])
def test_restricted_consumer_cannot_impersonate_executable_reference(extra):
    with pytest.raises(ValidationError, match="只能携带受限陈述身份"):
        ProtocolControlDefinitionAtomConsumption(
            consumer_kind="restricted_statement", restricted_statement_id="restricted:generic",
            consumer_excerpt="真实原文", **extra,
        )


# -- 反向：受限记录本身不得携带可执行语义 ------------------------------------


def test_restricted_statement_has_no_executable_semantics() -> None:
    with pytest.raises(ValidationError):
        RestrictedProtocolControlStatement(
            **_statement_payload(
                obligations=[
                    ControlObligationAtom(
                        obligation_id="ob-1",
                        kind=ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE,
                        statement="不得使用禁用药物",
                    )
                ]
            )
        )
    with pytest.raises(ValidationError):
        RestrictedProtocolControlStatement(
            **_statement_payload(protocol_control_id="pc-washout-01")
        )
    with pytest.raises(ValidationError):
        RestrictedProtocolControlStatement(**_statement_payload(display_ordinal=1))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source_quote": "   "}, "必须逐字保留原文摘录"),
        ({"unresolved_dimensions": ["  "]}, "必须说明具体尚未核清之处"),
        ({"source_span_ids": []}, None),
        ({"source_span_ids": ["span:b", "span:a"]}, "必须按 ID 排序且不得重复"),
        ({"dependency_refs": ["restricted:x", "restricted:x"]}, "必须按 ID 排序且不得重复"),
        ({"restricted_statement_id": "IN-01"}, "不得使用 IN/EX/REQ/CTRL"),
        ({"restricted_statement_id": "CTRL-1"}, "不得使用 IN/EX/REQ/CTRL"),
        ({"limitation_kind": "known_wrong"}, None),
    ],
)
def test_restricted_statement_requires_typed_source_and_reason(
    overrides: dict, message: str | None
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        RestrictedProtocolControlStatement(**_statement_payload(**overrides))
    if message is not None:
        assert message in str(excinfo.value)


# -- 反向：目录身份、来源闭包与受限依赖 --------------------------------------


def test_catalog_rejects_reused_executable_identity() -> None:
    with pytest.raises(ValidationError, match="不得复用可执行控制身份"):
        _catalog(
            restricted=(_restricted_statement("pc-washout-01"),),
            controls=(_published_control(control_id="pc-washout-01"),),
        )
    with pytest.raises(ValidationError, match="不得复用可执行控制身份"):
        _catalog(
            restricted=(_restricted_statement("candidate:batch5-a"),),
            controls=(_published_control(candidate_id="candidate:batch5-a"),),
        )


def test_catalog_rejects_duplicate_restricted_identities() -> None:
    with pytest.raises(ValidationError, match="受限来源陈述 ID 必须唯一"):
        _catalog(
            restricted=(
                _restricted_statement("restricted:batch5-a", statement_index=0),
                _restricted_statement("restricted:batch5-a", statement_index=1),
            )
        )


def test_catalog_rejects_unordered_or_duplicate_source_statements() -> None:
    with pytest.raises(ValidationError, match="升序排列且不得重复"):
        _catalog(
            restricted=(
                _restricted_statement("restricted:batch5-a", statement_index=1),
                _restricted_statement("restricted:batch5-b", statement_index=0),
            )
        )
    with pytest.raises(ValidationError, match="升序排列且不得重复"):
        _catalog(
            restricted=(
                _restricted_statement("restricted:batch5-a", statement_index=1),
                _restricted_statement("restricted:batch5-b", statement_index=1),
            )
        )


def test_catalog_rejects_out_of_closure_sources() -> None:
    with pytest.raises(ValidationError, match="受限来源陈述来源越界"):
        _catalog(
            restricted=(
                _restricted_statement(
                    "restricted:batch5-a", spans=("span:outside",)
                ),
            )
        )


def test_catalog_rejects_source_index_out_of_range() -> None:
    with pytest.raises(ValidationError):
        _restricted_statement("restricted:batch5-a", statement_index=-1)


def test_catalog_rejects_dangling_self_and_cyclic_dependencies() -> None:
    with pytest.raises(ValidationError, match="受限来源陈述不得依赖自身"):
        _restricted_statement(
            "restricted:batch5-a", dependencies=("restricted:batch5-a",)
        )
    with pytest.raises(ValidationError, match="依赖必须指向本目录内的受限来源陈述"):
        _catalog(
            restricted=(
                _restricted_statement(
                    "restricted:batch5-a", dependencies=("restricted:missing",)
                ),
            )
        )
    # 受限依赖不得指向可执行控制：那会把未决含义重新接回可执行语义。
    with pytest.raises(ValidationError, match="依赖必须指向本目录内的受限来源陈述"):
        _catalog(
            controls=(_published_control(),),
            restricted=(
                _restricted_statement(
                    "restricted:batch5-b", dependencies=("pc-washout-01",)
                ),
            ),
        )
    first = _restricted_statement(
        "restricted:batch5-a",
        statement_index=0,
        dependencies=("restricted:batch5-b",),
    )
    second = _restricted_statement(
        "restricted:batch5-b",
        statement_index=1,
        dependencies=("restricted:batch5-a",),
    )
    with pytest.raises(ValidationError, match="受限来源陈述依赖不得成环"):
        _catalog(restricted=(first, second))


# -- 同段独立陈述：受限陈述与可执行候选共存的显式来源区间证明 --------------------

_INDEPENDENT_QUOTE = "年龄至少18岁"
_RESTRICTED_QUOTE = "其他控制"


def _independent_excerpt(
    *,
    quote: str = _INDEPENDENT_QUOTE,
    start: int = 5,
    end: int = 12,
    candidates: tuple[str, ...] = ("pcc-generic",),
    statement_index: int = 0,
) -> RestrictedStatementIndependentExcerpt:
    return RestrictedStatementIndependentExcerpt(
        statement_index=statement_index,
        source_quote=quote,
        source_start=start,
        source_end=end,
        candidate_control_ids=list(candidates),
        decision_functions=["action"],
        source_force="required",
    )


def _scope_proof(
    *,
    restricted: tuple[int, int] = (0, 4),
    independent: tuple[RestrictedStatementIndependentExcerpt, ...] | None = None,
    digest: str = "a" * 64,
) -> RestrictedStatementScopeProof:
    return RestrictedStatementScopeProof(
        unit_excerpt_sha256=digest,
        restricted_source_start=restricted[0],
        restricted_source_end=restricted[1],
        independent_excerpts=(
            list(independent)
            if independent is not None
            else [_independent_excerpt()]
        ),
    )


def _coexisting_candidate_batch():
    """One frozen unit whose executable candidate is proven independent of its restriction."""

    batch = _batch()
    wire = _wire(candidate=_candidate())
    wire.candidate_drafts[0].exception_expression = None
    original = hydrate_protocol_control_agent_output(wire, batch)
    unit = batch.owned_units[0]
    independent = locate_source_quote_offsets(unit.excerpt, _INDEPENDENT_QUOTE)
    restricted = locate_source_quote_offsets(unit.excerpt, _RESTRICTED_QUOTE)
    assert independent is not None and restricted is not None
    candidate_id = original.candidates[0].control_candidate_id
    statement = _restricted_statement(
        "restricted:same-unit",
        unit_id=unit.structure_unit_id,
        quote=_RESTRICTED_QUOTE,
        spans=tuple(unit.source_span_ids),
    ).model_copy(update={"source_statement_index": 1,
                        "decision_functions": ["action"], "source_force": "required",
                        "independent_scope_proof": _scope_proof(
        restricted=restricted,
        independent=(_independent_excerpt(
            start=independent[0], end=independent[1], candidates=(candidate_id,),
        ),),
        digest=hashlib.sha256(unit.excerpt.encode("utf-8")).hexdigest(),
    )})
    payload = original.model_dump(mode="json")
    payload["restricted_statements"] = [statement.model_dump(mode="json")]
    hydrated = ProtocolControlBatchDispositionHydrated.model_validate(payload)
    return batch, statement, hydrated, candidate_id


def test_scope_proof_requires_disjoint_literal_ranges() -> None:
    with pytest.raises(ValidationError, match="不得与受限陈述区间重叠"):
        _scope_proof(restricted=(0, 8), independent=(_independent_excerpt(start=4, end=12),))
    with pytest.raises(ValidationError, match="不得与受限陈述区间重叠"):
        _scope_proof(independent=(
            _independent_excerpt(start=5, end=12, statement_index=0),
            _independent_excerpt(start=10, end=16, statement_index=1),
        ))
    with pytest.raises(ValidationError, match="升序排列且不得重复"):
        _scope_proof(independent=(
            _independent_excerpt(start=14, end=20, statement_index=1),
            _independent_excerpt(start=5, end=12, statement_index=0),
        ))
    with pytest.raises(ValidationError, match="非空半开区间"):
        _scope_proof(independent=(_independent_excerpt(start=12, end=12),))
    with pytest.raises(ValidationError):
        _scope_proof(independent=())
    with pytest.raises(ValidationError, match="必须按 ID 排序且不得重复"):
        _independent_excerpt(candidates=("pcc-b", "pcc-a"))


def test_restricted_statement_without_proof_keeps_legacy_bytes() -> None:
    legacy = _restricted_statement("restricted:batch5-a")
    assert "independent_scope_proof" not in legacy.model_dump(mode="json")

    catalog = _catalog(restricted=(legacy,))
    dumped = catalog.model_dump(mode="json")
    assert "independent_scope_proof" not in dumped["restricted_statements"][0]
    assert PublishedProtocolControlCatalog.model_validate(dumped).model_dump(
        mode="json"
    ) == dumped

    publication = _publication(catalog)
    publication_dump = publication.model_dump(mode="json")
    assert ControlCatalogPublication.model_validate(publication_dump).model_dump(
        mode="json"
    ) == publication_dump


def test_hydrated_batch_requires_a_proof_before_keeping_a_candidate() -> None:
    _, statement, hydrated, candidate_id = _coexisting_candidate_batch()
    assert [item.disposition.value for item in hydrated.dispositions] == [
        "other_control_candidate", "supporting_or_supplement",
    ]
    proof = hydrated.restricted_statements[0].independent_scope_proof
    assert proof is not None
    assert proof.independent_excerpts[0].candidate_control_ids == [candidate_id]
    assert hydrated.model_dump(mode="json")["restricted_statements"][0][
        "independent_scope_proof"
    ]["independent_excerpts"][0]["source_quote"] == _INDEPENDENT_QUOTE

    without_proof = hydrated.model_dump(mode="json")
    without_proof["restricted_statements"][0].pop("independent_scope_proof")
    with pytest.raises(ValidationError, match="同单元保留可执行候选必须逐条提供独立来源区间证明"):
        ProtocolControlBatchDispositionHydrated.model_validate(without_proof)

    unknown_candidate = hydrated.model_dump(mode="json")
    unknown_candidate["restricted_statements"][0]["independent_scope_proof"][
        "independent_excerpts"
    ][0]["candidate_control_ids"] = ["pcc-missing"]
    with pytest.raises(ValidationError, match="必须绑定本单元内已有的可执行候选"):
        ProtocolControlBatchDispositionHydrated.model_validate(unknown_candidate)

    # 共同目录的保存/重建必须原样保留该证明，不能只留受限记录本身。
    publication = _publication(
        _catalog(restricted=(statement,), allowed=tuple(statement.source_span_ids))
    )
    published_dump = publication.model_dump(mode="json")
    restored = ControlCatalogPublication.model_validate(published_dump)
    assert restored.model_dump(mode="json") == published_dump
    assert restored.catalog.restricted_statements[0].independent_scope_proof is not None
    assert restored.publication_id == publication.publication_id


def test_gate_rejects_forged_independence_proofs() -> None:
    batch, _, hydrated, _ = _coexisting_candidate_batch()
    assert check_protocol_control_batch_candidates(batch, hydrated) == ()

    tampered = hydrated.model_copy(deep=True)
    tampered.restricted_statements[0].source_quote = "年龄至少19岁"
    assert [issue.code for issue in check_protocol_control_batch_candidates(batch, tampered)] == [
        "RESTRICTED_SOURCE_SCOPE_MISMATCH"
    ]

    unproven = hydrated.model_copy(deep=True)
    unproven.restricted_statements[0].independent_scope_proof = None
    assert [issue.code for issue in check_protocol_control_batch_candidates(batch, unproven)] == [
        "RESTRICTED_SOURCE_SCOPE_UNPROVEN"
    ]

    foreign_quote = hydrated.model_copy(deep=True)
    foreign_quote.restricted_statements[0].independent_scope_proof.independent_excerpts[
        0
    ].source_quote = "年龄达到18岁"
    assert [issue.code for issue in check_protocol_control_batch_candidates(batch, foreign_quote)] == [
        "RESTRICTED_SOURCE_SCOPE_MISMATCH"
    ]


def test_gate_rechecks_unreported_scope_outside_valid_quote_ranges() -> None:
    batch, _, hydrated, _ = _coexisting_candidate_batch()
    prefix = "仅用于已符合资格者："
    unit = batch.owned_units[0]
    unit.excerpt = prefix + unit.excerpt
    proof = hydrated.restricted_statements[0].independent_scope_proof
    proof.unit_excerpt_sha256 = hashlib.sha256(unit.excerpt.encode("utf-8")).hexdigest()
    proof.restricted_source_start += len(prefix)
    proof.restricted_source_end += len(prefix)
    for entry in proof.independent_excerpts:
        entry.source_start += len(prefix)
        entry.source_end += len(prefix)
    assert "RESTRICTED_SOURCE_UNINTERPRETED_CONTEXT" in [
        issue.code for issue in check_protocol_control_batch_candidates(batch, hydrated)
    ]


def _resite_candidate(candidate, excerpt: str):
    """Rewrite every atom citation of one hydrated candidate to a single excerpt."""

    semantics = candidate.semantics

    def rebuild(expression):
        if expression is None:
            return None
        groups = []
        for group in expression.groups:
            atoms = []
            for atom in group.atoms:
                update: dict[str, object] = {"source_excerpts": [excerpt]}
                evaluation = getattr(atom, "evaluation", None)
                if evaluation is not None:
                    update["evaluation"] = evaluation.model_copy(
                        update={"source_excerpts": [excerpt]}
                    )
                atoms.append(atom.model_copy(update=update))
            groups.append(group.model_copy(update={"atoms": atoms}))
        return expression.model_copy(update={"groups": groups})

    return candidate.model_copy(update={"semantics": semantics.model_copy(update={
        "applicability_expression": rebuild(semantics.applicability_expression),
        "trigger_expression": rebuild(semantics.trigger_expression),
        "obligation_expression": rebuild(semantics.obligation_expression),
        "exception_expression": rebuild(semantics.exception_expression),
    })})


def test_gate_rejects_an_unattributed_independent_excerpt() -> None:
    batch, _, hydrated, _ = _coexisting_candidate_batch()
    drifted = hydrated.model_copy(deep=True)
    drifted.candidates[0] = _resite_candidate(
        drifted.candidates[0], "其他方案控制",
    )
    codes = [
        issue.code
        for issue in check_protocol_control_batch_candidates(batch, drifted)
    ]
    assert "RESTRICTED_SOURCE_SCOPE_UNATTRIBUTED" in codes


def test_gate_rejects_a_candidate_that_reuses_the_restricted_statement() -> None:
    batch, _, hydrated, _ = _coexisting_candidate_batch()
    reused = hydrated.model_copy(deep=True)
    offsets = locate_source_quote_offsets(batch.owned_units[0].excerpt, _INDEPENDENT_QUOTE)
    assert offsets is not None
    proof = reused.restricted_statements[0].independent_scope_proof
    assert (proof.independent_excerpts[0].source_start,
            proof.independent_excerpts[0].source_end) == offsets
    # 受限陈述被改写成候选正在执行的那条陈述：同一个语义点不得同时可执行与受限。
    reused.restricted_statements[0].source_quote = _INDEPENDENT_QUOTE
    proof.restricted_source_start, proof.restricted_source_end = offsets
    assert [issue.code for issue in check_protocol_control_batch_candidates(batch, reused)] == [
        "RESTRICTED_SOURCE_POINT_REUSED"
    ]


def test_quote_location_does_not_guess_between_repeated_occurrences() -> None:
    assert locate_source_quote_offsets("年龄至少18岁；年龄至少18岁", "年龄至少18岁") is None
    assert locate_source_quote_offsets("年龄至少18岁；\n年龄 至少18岁", "年龄至少18岁") is None
    assert locate_source_quote_offsets("年 龄至少18岁", "年龄至少18岁") == (0, 8)


@pytest.mark.parametrize("field", ["scope_quote", "time_words", "exception_words"])
def test_gate_rejects_external_or_shared_qualifiers(field: str) -> None:
    batch, _, output, _ = _coexisting_candidate_batch()
    statement = output.restricted_statements[0]
    setattr(statement, field, ["不存在的时限"] if field == "time_words" else "不存在的时限")
    assert "RESTRICTED_SOURCE_CONTEXT_UNGROUNDED" in [
        issue.code for issue in check_protocol_control_batch_candidates(batch, output)
    ]
    setattr(statement, field, [_INDEPENDENT_QUOTE] if field == "time_words" else _INDEPENDENT_QUOTE)
    assert "RESTRICTED_SOURCE_CONTEXT_UNPROVEN" in [
        issue.code for issue in check_protocol_control_batch_candidates(batch, output)
    ]


def test_wire_cannot_inject_system_restricted_proofs() -> None:
    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentWireValidationError, validate_protocol_control_agent_wire,
    )

    batch = _batch()
    wire = _wire()
    assert hydrate_protocol_control_agent_output(wire, batch).restricted_statements == []
    injected = wire.model_dump(mode="json")
    injected["restricted_statements"] = [_restricted_statement("restricted:injected").model_dump(mode="json")]
    with pytest.raises((ProtocolControlAgentWireValidationError, ValidationError)):
        validate_protocol_control_agent_wire(type(wire).model_validate(injected), batch)


@pytest.mark.parametrize("function", ["definition", "threshold", "calculation_input", "unclassified"])
def test_gate_cannot_separate_a_restricted_definition_from_its_possible_consumer(function: str) -> None:
    batch, _, output, _ = _coexisting_candidate_batch()
    output.restricted_statements[0].decision_functions = [function]
    assert "RESTRICTED_SOURCE_CONTEXT_UNPROVEN" in [
        issue.code for issue in check_protocol_control_batch_candidates(batch, output)
    ]
