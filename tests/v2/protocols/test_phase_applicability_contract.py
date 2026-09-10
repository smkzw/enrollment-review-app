from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityCandidateDraft,
    PhaseApplicabilityDisposition,
    PhaseApplicabilityEvidenceDraft,
    PhaseApplicabilityEvidencePolarity,
    PhaseApplicabilityFrozenPackage,
    PhaseApplicabilityResolutionBatchDraft,
    PhaseApplicabilityResolutionDraft,
    PhaseApplicabilityResolutionSet,
    stable_phase_applicability_package_id,
    stable_phase_applicability_evidence_id,
)
from app.domain.contracts.protocol_controls import (
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.protocols.phase_applicability import (
    PhaseApplicabilityHydrationError,
    check_phase_applicability_resolution,
    gate_phase_applicability_resolution,
    hydrate_phase_applicability_resolution,
    record_phase_applicability_manual_override,
)


_SHA = "a" * 64


def _unit(
    unit_id: str,
    order: int,
    *,
    scope: PhaseScope,
    span: str | None = None,
    excerpt: str | None = None,
    heading_path: list[str] | None = None,
) -> ProtocolStructureUnit:
    span_id = span or f"span-{unit_id}"
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"body.p{order}",
        member_source_refs=[f"body.p{order}"],
        source_span_ids=[span_id],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=heading_path or ["5 研究设计"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[scope],
        excerpt=excerpt or f"来源 {unit_id}：本段明确限定研究期别",
    )


def _package(
    *,
    owned: list[ProtocolStructureUnit] | None = None,
    context: list[ProtocolStructureUnit] | None = None,
) -> PhaseApplicabilityFrozenPackage:
    owned = owned or [
        _unit("su-explicit", 0, scope=PhaseScope.PHASE_II),
        _unit("su-ambiguous", 1, scope=PhaseScope.UNKNOWN),
    ]
    context = context or []
    owned_ids = [item.structure_unit_id for item in owned]
    spans = sorted(
        {
            span_id
            for item in [*owned, *context]
            for span_id in item.source_span_ids
        }
    )
    manifest_id = "manifest:phase-applicability"
    return PhaseApplicabilityFrozenPackage(
        package_id=stable_phase_applicability_package_id(manifest_id, 1, owned_ids),
        coverage_manifest_id=manifest_id,
        protocol_version_id="protocol:v1",
        protocol_document_sha256=_SHA,
        snapshot_id="snapshot:phase-applicability",
        package_ordinal=1,
        selected_phase=StudyPhase.PHASE_II,
        opposite_phase=StudyPhase.PHASE_III,
        owned_units=owned,
        context_units=context,
        frozen_source_span_ids=spans,
    )


def _evidence(
    *,
    polarity: PhaseApplicabilityEvidencePolarity = PhaseApplicabilityEvidencePolarity.SUPPORTS,
    unit_indexes: list[int] | None = None,
    span_indexes: list[int] | None = None,
    excerpt: str = "本段明确限定研究期别",
    rationale: str = "来源直接表达期别适用范围",
) -> PhaseApplicabilityEvidenceDraft:
    return PhaseApplicabilityEvidenceDraft(
        polarity=polarity,
        source_unit_indexes=unit_indexes or [1],
        source_span_indexes=span_indexes or [0],
        excerpt=excerpt,
        rationale=rationale,
    )


def _draft(
    *,
    disposition: PhaseApplicabilityDisposition = PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE,
    candidates: list[PhaseApplicabilityCandidateDraft] | None = None,
    evidence: list[PhaseApplicabilityEvidenceDraft] | None = None,
    unresolved_reason: str | None = None,
    unit_index: int = 1,
) -> PhaseApplicabilityResolutionDraft:
    evidence = evidence or [_evidence()]
    candidates = candidates or [
        PhaseApplicabilityCandidateDraft(
            scope=PhaseScope.PHASE_II,
            supporting_evidence_indexes=[0],
        )
    ]
    return PhaseApplicabilityResolutionDraft(
        unit_index=unit_index,
        evidence=evidence,
        candidates=candidates,
        final_disposition=disposition,
        rationale="依据冻结来源完成期别语义判断",
        unresolved_reason=unresolved_reason,
    )


def _resolve(
    package: PhaseApplicabilityFrozenPackage | None = None,
    draft: PhaseApplicabilityResolutionDraft | PhaseApplicabilityResolutionBatchDraft | None = None,
):
    package = package or _package()
    draft = draft or _draft()
    return package, hydrate_phase_applicability_resolution(package, draft)


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_structurally_explicit_scope_can_be_preserved_but_unknown_requires_result() -> None:
    package, resolutions = _resolve()
    accepted = gate_phase_applicability_resolution(package, resolutions)
    assert accepted.results[0].structure_unit_id == "su-ambiguous"

    missing = resolutions.model_copy(update={"results": []})
    report = check_phase_applicability_resolution(package, missing)
    assert not report.accepted
    assert "UNIT_RESULT_MISSING" in _codes(report)

    explicit_package = _package(
        owned=[_unit("su-only-explicit", 0, scope=PhaseScope.SHARED)]
    )
    empty = PhaseApplicabilityResolutionSet(
        package_id=explicit_package.package_id,
        coverage_manifest_id=explicit_package.coverage_manifest_id,
        protocol_version_id=explicit_package.protocol_version_id,
        selected_phase=explicit_package.selected_phase,
        opposite_phase=explicit_package.opposite_phase,
        results=[],
    )
    assert gate_phase_applicability_resolution(explicit_package, empty) is empty


def test_batch_draft_hydrates_without_provider_owned_identities() -> None:
    package, resolutions = _resolve(
        draft=PhaseApplicabilityResolutionBatchDraft(results=[_draft()])
    )
    assert gate_phase_applicability_resolution(package, resolutions) is resolutions
    assert resolutions.results[0].resolution_id.startswith("par-")


def test_semantic_final_cannot_override_structurally_explicit_shared_scope() -> None:
    package = _package(
        owned=[_unit("su-explicit-shared", 0, scope=PhaseScope.SHARED)]
    )
    draft = _draft(
        unit_index=0,
        evidence=[_evidence(unit_indexes=[0], span_indexes=[0])],
    )
    package, resolutions = _resolve(package=package, draft=draft)
    report = check_phase_applicability_resolution(package, resolutions)
    assert "CONTRADICTORY_FINAL_DISPOSITION" in _codes(report)


def test_cross_phase_shared_rejects_generic_phase_sources_outside_target_rule_family() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["6 研究人群", "6.2 排除标准"],
            )
        ],
        context=[
            _unit("su-phase-ii", 1, scope=PhaseScope.PHASE_II, excerpt="Ⅱ期设有筛选访视"),
            _unit("su-phase-iii", 2, scope=PhaseScope.PHASE_III, excerpt="Ⅲ期设有筛选访视"),
        ],
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="Ⅱ期设有筛选访视",
            ),
            _evidence(
                unit_indexes=[2],
                span_indexes=[1],
                excerpt="Ⅲ期设有筛选访视",
            ),
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                supporting_evidence_indexes=[0, 1],
            )
        ],
    )
    resolutions = hydrate_phase_applicability_resolution(package, draft)

    report = check_phase_applicability_resolution(package, resolutions)

    assert "SHARED_POSITIVE_SOURCE_MISSING" in _codes(report)


def test_selected_phase_rejects_support_from_an_unrelated_package_unit() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["8 研究治疗", "8.2 禁止的合并用药"],
                excerpt="首次给药前四周不得使用系统治疗",
            )
        ],
        context=[
            _unit(
                "su-unrelated",
                1,
                scope=PhaseScope.PHASE_II,
                heading_path=["6 研究人群", "6.1 入选标准"],
                excerpt="Ⅱ期参与者应完成知情同意",
            )
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[1],
                excerpt="Ⅱ期参与者应完成知情同意",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    assert "TARGET_RELATED_SUPPORT_MISSING" in _codes(report)


def test_selected_phase_accepts_the_table_title_that_owns_the_target_row() -> None:
    package = _package(
        owned=[
            _unit(
                "su-table-row",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=[
                    "8 研究治疗",
                    "8.2 禁止的合并用药/治疗",
                    "表 5 禁止的合并用药/治疗",
                ],
                excerpt="首次给药前四周至试验结束 | 系统治疗",
            )
        ],
        context=[
            _unit(
                "su-table-title",
                1,
                scope=PhaseScope.UNKNOWN,
                heading_path=["8 研究治疗", "8.2 禁止的合并用药/治疗"],
                excerpt="表 5 禁止的合并用药/治疗",
            )
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[1],
                excerpt="表 5 禁止的合并用药/治疗",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert gate_phase_applicability_resolution(package, resolutions) is resolutions


def test_common_parent_heading_does_not_broadcast_phase_support_to_another_rule() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["5 研究设计", "5.1 入选标准"],
            )
        ],
        context=[
            _unit(
                "su-common-parent",
                1,
                scope=PhaseScope.PHASE_II,
                heading_path=["5 研究设计", "5.2 排除标准"],
                excerpt="Ⅱ/Ⅲ期评估和程序一致，详见研究流程。",
            )
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[package.frozen_source_span_ids.index("span-su-common-parent")],
                excerpt="Ⅱ/Ⅲ期评估和程序一致，详见研究流程。",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert "TARGET_RELATED_SUPPORT_MISSING" in _codes(
        check_phase_applicability_resolution(package, resolutions)
    )


def test_ordinary_title_mention_does_not_count_as_target_rule_evidence() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["6 研究人群", "6.2 排除标准"],
            )
        ],
        context=[
            _unit(
                "su-mention",
                1,
                scope=PhaseScope.PHASE_II,
                heading_path=["9 安全性", "9.1 一般原则"],
                excerpt="本段仅提及排除标准，但没有对应的规则要求。",
            )
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[package.frozen_source_span_ids.index("span-su-mention")],
                excerpt="本段仅提及排除标准，但没有对应的规则要求。",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert "TARGET_RELATED_SUPPORT_MISSING" in _codes(
        check_phase_applicability_resolution(package, resolutions)
    )


def test_target_title_relation_without_phase_scope_cannot_create_paired_range() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["6 研究人群", "6.2 排除标准"],
            )
        ],
        context=[
            _unit(
                "su-unscoped-title",
                1,
                scope=PhaseScope.UNKNOWN,
                heading_path=["9 安全性", "9.1 排除标准"],
                excerpt="排除标准",
            ),
            _unit(
                "su-opposite-unrelated",
                2,
                scope=PhaseScope.PHASE_III,
                heading_path=["9 安全性", "9.2 一般原则"],
                excerpt="Ⅲ期研究按一般原则执行。",
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[package.frozen_source_span_ids.index("span-su-unscoped-title")],
                excerpt="排除标准",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    assert report.accepted


def test_cross_phase_shared_accepts_paired_phase_sources_naming_target_rule_family() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["6 研究人群", "6.2 排除标准"],
            )
        ],
        context=[
            _unit(
                "su-phase-ii",
                1,
                scope=PhaseScope.PHASE_II,
                excerpt="Ⅱ期参与者须不符合任何排除标准。",
            ),
            _unit(
                "su-phase-iii",
                2,
                scope=PhaseScope.PHASE_III,
                excerpt="Ⅲ期参与者须不符合任何排除标准。",
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="Ⅱ期参与者须不符合任何排除标准。",
            ),
            _evidence(
                unit_indexes=[2],
                span_indexes=[1],
                excerpt="Ⅲ期参与者须不符合任何排除标准。",
            ),
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                supporting_evidence_indexes=[0, 1],
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert check_phase_applicability_resolution(package, resolutions).accepted


def test_phase_specific_general_safety_summary_cannot_scope_every_lab_subrule() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt="根据新出现的安全性数据，可能需要进行其他检测。",
            )
        ],
        context=[
            _unit(
                "su-phase-ii-summary",
                1,
                scope=PhaseScope.PHASE_II,
                heading_path=["5 研究设计", "5.1 总体设计"],
                excerpt="安全性评估内容包括评估临床实验室检查结果。",
            ),
            _unit(
                "su-phase-iii-summary",
                2,
                scope=PhaseScope.PHASE_III,
                heading_path=["5 研究设计", "5.1 总体设计"],
                excerpt="安全性评估内容包括评估临床实验室检查结果。",
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="安全性评估内容包括评估临床实验室检查结果。",
            ),
            _evidence(
                unit_indexes=[2],
                span_indexes=[1],
                excerpt="安全性评估内容包括评估临床实验室检查结果。",
            ),
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                supporting_evidence_indexes=[0, 1],
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    assert "SHARED_POSITIVE_SOURCE_MISSING" in _codes(report)
    assert "PAIRED_RULE_FAMILY_SOURCE_IGNORED" not in _codes(report)


def test_different_subrules_under_same_section_do_not_create_paired_phase_scope() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                span="span-a-target",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt="根据新出现的安全性数据，可能需要进行其他检测。",
            )
        ],
        context=[
            _unit(
                "su-phase-ii-subrule",
                1,
                scope=PhaseScope.PHASE_II,
                span="span-b-phase-ii",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt="Ⅱ期糖化血红蛋白仅在筛选和第12周检测。",
            ),
            _unit(
                "su-phase-iii-subrule",
                2,
                scope=PhaseScope.PHASE_III,
                span="span-c-phase-iii",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt="Ⅲ期糖化血红蛋白仅在筛选、第16周和第52周检测。",
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[0],
                span_indexes=[0],
                excerpt="根据新出现的安全性数据，可能需要进行其他检测。",
            )
        ],
    )

    report = check_phase_applicability_resolution(
        package,
        hydrate_phase_applicability_resolution(package, draft),
    )

    assert report.accepted
    assert "PAIRED_RULE_FAMILY_SOURCE_IGNORED" not in _codes(report)


def test_verbatim_repeated_atomic_obligation_can_still_form_paired_scope() -> None:
    repeated = "发生异常时须复查该项实验室检查。"
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                span="span-a-target",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt=repeated,
            )
        ],
        context=[
            _unit(
                "su-phase-ii-copy",
                1,
                scope=PhaseScope.PHASE_II,
                span="span-b-phase-ii",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt=repeated,
            ),
            _unit(
                "su-phase-iii-copy",
                2,
                scope=PhaseScope.PHASE_III,
                span="span-c-phase-iii",
                heading_path=["7 研究评估和程序", "7.2 实验室检查"],
                excerpt=repeated,
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(unit_indexes=[1], span_indexes=[1], excerpt=repeated),
            _evidence(unit_indexes=[2], span_indexes=[2], excerpt=repeated),
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                supporting_evidence_indexes=[0, 1],
            )
        ],
    )

    report = check_phase_applicability_resolution(
        package,
        hydrate_phase_applicability_resolution(package, draft),
    )

    assert report.accepted


def test_downstream_phase_reference_cannot_become_scope_from_distant_universal_word() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["10 统计学考虑", "10.1 期中分析"],
                excerpt="本研究包含一个预设的期中分析。",
            )
        ],
        context=[
            _unit(
                "su-phase-ii",
                1,
                scope=PhaseScope.PHASE_II,
                heading_path=["5 研究设计", "5.1 总体设计"],
                excerpt="Ⅱ期所有参与者完成第12周访视后进行期中分析。",
            ),
            _unit(
                "su-phase-iii-downstream",
                2,
                scope=PhaseScope.PHASE_III,
                heading_path=["5 研究设计", "5.2 Ⅲ期总体设计"],
                excerpt=(
                    "安慰剂组可根据期中分析结果转入推荐剂量组；治疗期内所有参与者"
                    "按方案时间点进行访视。"
                ),
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="Ⅱ期所有参与者完成第12周访视后进行期中分析。",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    assert report.accepted
    assert "PAIRED_RULE_FAMILY_SOURCE_IGNORED" not in _codes(report)


def test_single_phase_cannot_ignore_other_half_of_paired_rule_family_sources() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["6 研究人群", "6.2 排除标准"],
            )
        ],
        context=[
            _unit(
                "su-phase-ii",
                1,
                scope=PhaseScope.PHASE_II,
                excerpt="Ⅱ期参与者须不符合任何排除标准。",
            ),
            _unit(
                "su-phase-iii",
                2,
                scope=PhaseScope.PHASE_III,
                excerpt="Ⅲ期参与者须不符合任何排除标准。",
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="Ⅱ期参与者须不符合任何排除标准。",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert "PAIRED_RULE_FAMILY_SOURCE_IGNORED" in _codes(
        check_phase_applicability_resolution(package, resolutions)
    )


def test_cross_phase_shared_accepts_direct_source_and_opposite_phase_cross_reference() -> None:
    package = _package(
        owned=[
            _unit(
                "su-target",
                0,
                scope=PhaseScope.UNKNOWN,
                heading_path=["7 研究评估和程序", "7.1 签署知情同意书"],
            )
        ],
        context=[
            _unit(
                "su-phase-ii",
                1,
                scope=PhaseScope.PHASE_II,
                excerpt="签署知情同意书",
                heading_path=["7 研究评估和程序", "7.2 访视安排", "Ⅱ期筛选期"],
            ),
            _unit(
                "su-phase-iii",
                2,
                scope=PhaseScope.PHASE_III,
                excerpt="与Ⅱ期临床研究试验一致，详见7.2.1.1",
                heading_path=["7 研究评估和程序", "7.2 访视安排", "Ⅲ期筛选期"],
            ),
        ],
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[0],
                excerpt="签署知情同意书",
            ),
            _evidence(
                unit_indexes=[2],
                span_indexes=[1],
                excerpt="与Ⅱ期临床研究试验一致，详见7.2.1.1",
            ),
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                supporting_evidence_indexes=[0, 1],
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert check_phase_applicability_resolution(package, resolutions).accepted


def test_duplicate_unit_results_and_results_outside_owned_scope_are_blocked() -> None:
    package, resolutions = _resolve()
    duplicate = resolutions.model_copy(
        update={"results": [resolutions.results[0], resolutions.results[0]]}
    )
    report = check_phase_applicability_resolution(package, duplicate)
    assert "UNIT_RESULT_DUPLICATE" in _codes(report)

    context = _unit("su-context", 2, scope=PhaseScope.PHASE_II)
    package_with_context = _package(context=[context])
    outside = resolutions.results[0].model_copy(
        update={"structure_unit_id": "su-context"}
    )
    outside_set = resolutions.model_copy(update={"results": [outside]})
    report = check_phase_applicability_resolution(package_with_context, outside_set)
    assert "UNIT_RESULT_OUTSIDE_FROZEN_PACKAGE" in _codes(report)


def test_evidence_must_close_to_frozen_unit_and_package_spans() -> None:
    package, resolutions = _resolve()
    evidence = resolutions.results[0].evidence[0].model_copy(
        update={
            "source_structure_unit_ids": ["outside-unit"],
            "source_span_ids": ["outside-span"],
        }
    )
    result = resolutions.results[0].model_copy(update={"evidence": [evidence]})
    tampered = resolutions.model_copy(update={"results": [result]})
    report = check_phase_applicability_resolution(package, tampered)
    assert "EVIDENCE_UNIT_OUTSIDE_FROZEN_PACKAGE" in _codes(report)
    assert "EVIDENCE_SPAN_OUTSIDE_FROZEN_PACKAGE" in _codes(report)


def test_hydration_rejects_fabricated_and_similar_non_verbatim_excerpts() -> None:
    for excerpt in ("模型编造的来源摘录", "本段明确限制研究期别"):
        with pytest.raises(
            PhaseApplicabilityHydrationError,
            match="EVIDENCE_EXCERPT_NOT_VERBATIM",
        ):
            _resolve(draft=_draft(evidence=[_evidence(excerpt=excerpt)]))


def test_exact_excerpt_recovers_after_whitespace_normalization() -> None:
    package = _package(
        owned=[
            _unit("su-explicit", 0, scope=PhaseScope.PHASE_II),
            _unit(
                "su-ambiguous",
                1,
                scope=PhaseScope.UNKNOWN,
                excerpt="上位来源：本段  \n明确限定研究期别；",
            ),
        ]
    )
    draft = _draft(
        evidence=[
            _evidence(
                excerpt="本段 明确限定研究期别",
                unit_indexes=[1],
                span_indexes=[0],
            )
        ]
    )
    package, resolutions = _resolve(package=package, draft=draft)
    assert gate_phase_applicability_resolution(package, resolutions) is resolutions


def test_wrong_source_unit_index_is_rebound_only_by_unique_span_and_excerpt() -> None:
    package = _package(
        owned=[
            _unit("su-target", 0, scope=PhaseScope.UNKNOWN, span="span-target"),
        ],
        context=[
            _unit(
                "su-wrong",
                1,
                scope=PhaseScope.PHASE_II,
                span="span-wrong",
                excerpt="无关上下文",
            ),
            _unit(
                "su-source",
                2,
                scope=PhaseScope.PHASE_II,
                span="span-source",
                excerpt="可唯一恢复的直接来源原文",
            ),
        ],
    )
    span_index = package.frozen_source_span_ids.index("span-source")
    draft = _draft(
        unit_index=0,
        evidence=[
            _evidence(
                unit_indexes=[1],
                span_indexes=[span_index],
                excerpt="唯一恢复的直接来源",
            )
        ],
    )

    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert resolutions.results[0].evidence[0].source_structure_unit_ids == [
        "su-source"
    ]


def test_single_source_mixed_unit_can_be_resolved_by_actual_operation_phase() -> None:
    package = _package(
        owned=[_unit("su-mixed", 0, scope=PhaseScope.MIXED)]
    )
    draft = _draft(
        unit_index=0,
        evidence=[_evidence(unit_indexes=[0], span_indexes=[0])],
    )
    resolutions = hydrate_phase_applicability_resolution(package, draft)

    assert gate_phase_applicability_resolution(package, resolutions) is resolutions


def test_unresolved_must_explain_selected_phase_not_only_shared_scope() -> None:
    package = _package(
        owned=[_unit("su-unknown", 0, scope=PhaseScope.UNKNOWN)]
    )
    draft = _draft(
        unit_index=0,
        disposition=PhaseApplicabilityDisposition.UNRESOLVED,
        evidence=[
            _evidence(
                polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
                unit_indexes=[0],
                span_indexes=[0],
            )
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                unresolved_evidence_indexes=[0],
            )
        ],
        unresolved_reason="尚未证明两期共同适用",
    )
    resolutions = hydrate_phase_applicability_resolution(package, draft)
    report = check_phase_applicability_resolution(package, resolutions)

    assert "SELECTED_PHASE_UNRESOLVED_EVIDENCE_MISSING" in _codes(report)


def test_multisource_excerpt_must_be_exact_in_at_least_one_cited_unit() -> None:
    context = _unit(
        "su-context",
        2,
        scope=PhaseScope.PHASE_II,
        excerpt="交叉引用来源：共同适用证据",
    )
    package = _package(context=[context])
    valid = _draft(
        evidence=[
            _evidence(
                excerpt="共同适用证据",
                unit_indexes=[1, 2],
                span_indexes=[0, 1],
            )
        ]
    )
    assert gate_phase_applicability_resolution(
        package,
        hydrate_phase_applicability_resolution(package, valid),
    )

    with pytest.raises(
        PhaseApplicabilityHydrationError,
        match="EVIDENCE_EXCERPT_NOT_VERBATIM",
    ):
        hydrate_phase_applicability_resolution(
            package,
            _draft(
                evidence=[
                    _evidence(
                        excerpt="本段明确限定研究期别共同适用",
                        unit_indexes=[1, 2],
                        span_indexes=[0, 1],
                    )
                ]
            ),
        )


def test_gate_rejects_fabricated_excerpt_even_when_identity_is_recomputed() -> None:
    package, resolutions = _resolve()
    original = resolutions.results[0]
    original_evidence = original.evidence[0]
    fabricated_excerpt = "模型改写而非原文的摘录"
    fabricated_id = stable_phase_applicability_evidence_id(
        original.resolution_id,
        original_evidence.polarity,
        original_evidence.source_structure_unit_ids,
        original_evidence.source_span_ids,
        fabricated_excerpt,
        original_evidence.rationale,
    )
    fabricated_evidence = original_evidence.model_copy(
        update={"evidence_id": fabricated_id, "excerpt": fabricated_excerpt}
    )
    tampered_result = original.model_copy(update={"evidence": [fabricated_evidence]})
    tampered = resolutions.model_copy(update={"results": [tampered_result]})
    report = check_phase_applicability_resolution(package, tampered)
    assert "EVIDENCE_EXCERPT_NOT_VERBATIM" in _codes(report)


def test_contradictory_final_disposition_is_not_publishable() -> None:
    evidence = [
        _evidence(excerpt="本段明确限定研究期别", rationale="支持选定期别"),
        _evidence(
            polarity=PhaseApplicabilityEvidencePolarity.SUPPORTS,
            excerpt="本段明确限定研究期别",
            rationale="支持对侧期别",
        ),
    ]
    draft = _draft(
        evidence=evidence,
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.PHASE_II,
                supporting_evidence_indexes=[0],
            ),
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.PHASE_III,
                supporting_evidence_indexes=[1],
            ),
        ],
    )
    package, resolutions = _resolve(draft=draft)
    report = check_phase_applicability_resolution(package, resolutions)
    assert "CONTRADICTORY_FINAL_DISPOSITION" in _codes(report)


def test_shared_requires_explicit_support() -> None:
    draft = _draft(
        disposition=PhaseApplicabilityDisposition.CROSS_PHASE_SHARED,
        evidence=[
            _evidence(
                polarity=PhaseApplicabilityEvidencePolarity.OPPOSES,
                excerpt="本段明确限定研究期别",
                rationale="来源仅指向单一期别",
            )
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.SHARED,
                opposing_evidence_indexes=[0],
            )
        ],
    )
    package, resolutions = _resolve(draft=draft)
    report = check_phase_applicability_resolution(package, resolutions)
    assert "SHARED_UNSUPPORTED" in _codes(report)


def test_unresolved_requires_reason_and_unresolved_source() -> None:
    with pytest.raises(ValidationError, match="unresolved_reason"):
        _draft(disposition=PhaseApplicabilityDisposition.UNRESOLVED)

    draft = _draft(
        disposition=PhaseApplicabilityDisposition.UNRESOLVED,
        unresolved_reason="上位章节与表头未能闭合到同一期别",
        evidence=[
            _evidence(
                polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
                excerpt="本段明确限定研究期别",
                rationale="当前冻结来源不足以判定",
            )
        ],
        candidates=[
            PhaseApplicabilityCandidateDraft(
                scope=PhaseScope.PHASE_II,
                unresolved_evidence_indexes=[0],
            )
        ],
    )
    package, resolutions = _resolve(draft=draft)
    tampered_result = resolutions.results[0].model_copy(update={"unresolved_reason": None})
    tampered = resolutions.model_copy(update={"results": [tampered_result]})
    report = check_phase_applicability_resolution(package, tampered)
    assert "UNRESOLVED_REASON_MISSING" in _codes(report)


def test_model_draft_cannot_supply_system_or_source_identity_fields() -> None:
    with pytest.raises(ValidationError, match="resolution_id"):
        PhaseApplicabilityResolutionDraft.model_validate(
            {
                "unit_index": 1,
                "evidence": [_evidence().model_dump(mode="json")],
                "candidates": [
                    {
                        "scope": "phase_ii",
                        "supporting_evidence_indexes": [0],
                    }
                ],
                "final_disposition": "selected_phase_applicable",
                "rationale": "有依据",
                "resolution_id": "model-created-id",
            }
        )


def test_manual_override_keeps_before_after_identity_immutable() -> None:
    package, resolutions = _resolve()
    original = resolutions.results[0]
    with pytest.raises(ValueError, match="UNRESOLVED_OVERRIDE_EVIDENCE_MISSING"):
        record_phase_applicability_manual_override(
            original,
            after_disposition=PhaseApplicabilityDisposition.UNRESOLVED,
            reason="人工复核发现表头与上位章节存在冲突",
            overridden_by="reviewer-1",
            overridden_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )

    unresolved_source_draft = _draft(
        evidence=[
            _evidence(),
            _evidence(
                polarity=PhaseApplicabilityEvidencePolarity.UNRESOLVED,
                excerpt="本段明确限定研究期别",
                rationale="来源仍不足以确认对侧期别",
            ),
        ],
            candidates=[
                PhaseApplicabilityCandidateDraft(
                    scope=PhaseScope.PHASE_II,
                    supporting_evidence_indexes=[0],
                ),
                PhaseApplicabilityCandidateDraft(
                    scope=PhaseScope.PHASE_III,
                    unresolved_evidence_indexes=[1],
                ),
            ],
    )
    package, resolutions = _resolve(draft=unresolved_source_draft)
    original = resolutions.results[0]
    gate_phase_applicability_resolution(package, resolutions)
    overridden = record_phase_applicability_manual_override(
        original,
        after_disposition=PhaseApplicabilityDisposition.UNRESOLVED,
        reason="人工复核发现表头与上位章节存在冲突",
        overridden_by="reviewer-1",
        overridden_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert overridden.resolution_id == original.resolution_id
    assert overridden.unresolved_reason == "人工复核发现表头与上位章节存在冲突"
    assert overridden.manual_overrides[0].before_resolution_id == original.resolution_id
    assert overridden.manual_overrides[0].after_resolution_id == original.resolution_id
    overridden_set = resolutions.model_copy(update={"results": [overridden]})
    assert gate_phase_applicability_resolution(package, overridden_set) is overridden_set

    changed = overridden.manual_overrides[0].model_copy(
        update={"after_resolution_id": "mutated-resolution-id"}
    )
    tampered_result = overridden.model_copy(update={"manual_overrides": [changed]})
    tampered = resolutions.model_copy(update={"results": [tampered_result]})
    report = check_phase_applicability_resolution(package, tampered)
    assert "MANUAL_OVERRIDE_IDENTITY_MUTATED" in _codes(report)
