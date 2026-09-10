"""Phase 5 EvidenceExpectation 覆盖投影（Slice 5.4，worker_03）。

纯确定性投影器：从当前审核节点绑定的 ``EvidenceExpectationTemplate`` 生成受试者级
期望覆盖状态，五类状态按固定优先级决策，绝不解析散文。覆盖证据只接受同权威元组、
精确 ``fact_type`` 的已发布事实；来源要求（``required_source_types`` /
``requires_contemporaneous_objective_source`` / ``allows_screening_record_transcription``）
确定性决定完整还是较弱覆盖；OCR/解析风险、缺失文件、未完成流程等一律来自结构化
``CoverageGapSignal`` 输入，不从文本推断。

状态决策优先级（高 → 低，PRD P5-R07 / 任务要求）：

1. ``not_due``           模板到期节点在未来审核节点之后（缺口 future_stage_not_due）；
2. ``observed``          到期且有完整来源覆盖（缺口无）；
3. ``observed_weak``     到期但仅较弱来源覆盖（转述/历史来源未就位/OCR 解析风险，
                         携带溯源提醒，绝不重复报无证据）；
4. ``referenced_missing`` 到期、无覆盖、且存在结构化缺失文件信号；
5. ``absent``            到期、无覆盖、选择调用方供应的具体当前缺口
                         （无任何结构化缺口信号时拒绝投影，绝不回退通用缺口）。

本模块为纯函数，不做任何持久化；revision 追加写、权威元组/定位/模板绑定校验由
``app/storage/evidence_expectation_repository.py`` 负责。
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.evidence_expectations_v2 import (
    CoverageGapSignal,
    CoverageObservation,
    EvidenceExpectationV2,
    canonical_input_gap_signals,
    expectation_identity,
)
from app.domain.contracts.enums import (
    ExpectationStatus,
    GapType,
    ReviewStage,
    SourceStrength,
)
from app.domain.contracts.facts import ClinicalFactV2, FactAuthority

__all__ = [
    "ProjectionInputError",
    "project_expectation",
    "project_expectations",
    "stage_rank",
]

#: 审核节点先后顺序（PRE_SCREENING < SCREENING < RUN_IN < BASELINE）。
_STAGE_RANK = {
    ReviewStage.PRE_SCREENING: 1,
    ReviewStage.SCREENING: 2,
    ReviewStage.RUN_IN: 3,
    ReviewStage.BASELINE: 4,
}

#: 默认完整来源集：同期客观结果 / 既往原始资料 / 当前研究病历直接记录。
_DEFAULT_STRONG_SOURCES = {
    SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
    SourceStrength.HISTORICAL_PRIMARY,
    SourceStrength.CURRENT_STUDY_CHART,
}

_SOURCE_TYPE_FAMILIES = {
    "实验室检验结果": {"lab_report", "laboratory_test"},
    "检验报告": {"lab_report", "laboratory_test"},
    "lab": {"lab_report", "laboratory_test"},
    "检查报告": {
        "ecg",
        "ecg_report",
        "echocardiogram",
        "imaging",
        "ophthalmic_exam",
        "pft_report",
    },
    "exam_report": {
        "ecg",
        "ecg_report",
        "echocardiogram",
        "imaging",
        "ophthalmic_exam",
        "pft_report",
    },
    "病历资料": {
        "adverse_event_record",
        "clinical_exam",
        "medical_history",
        "medical_record",
        "medication_record",
        "patient_history",
        "patient_report",
        "physical_exam",
        "procedure_record",
        "surgical_record",
        "trauma_record",
    },
}

#: 到期缺口选择优先级（结构化信号 → 具体当前缺口，高优先级先选）。
_ABSENT_GAP_PRECEDENCE = (
    GapType.OBSERVATION_UNVERIFIED,
    GapType.PROFESSIONAL_JUDGMENT,
    GapType.REQUIRED_PROCEDURE_NOT_DONE,
    GapType.RESULT_FIELDS_MISSING,
    GapType.DESCRIPTION_INSUFFICIENT,
    GapType.OCR_OR_PARSE_RISK,
    GapType.RECORD_INCOMPLETE,
    GapType.DATE_OR_ANCHOR_MISSING,
)


class ProjectionInputError(ValueError):
    """投影输入不满足确定性前提（模板未绑定权威元组规则修订 / 到期缺口未结构化提供）。"""


def stage_rank(stage: ReviewStage) -> int:
    """审核节点先后排序；用于判断模板到期节点是否在将来。"""
    return _STAGE_RANK[stage]


def _coverage_verdict(
    observation: CoverageObservation, template: EvidenceExpectationTemplate
) -> str:
    """单个已发布事实相对模板来源要求的覆盖判定：complete / weak / none。

    - complete：来源强度满足模板完整来源要求；
    - weak：仅筛选病历转述且模板允许转述（仍为较弱覆盖，需溯源提醒）；
    - none：其他（无法确认来源等不构成覆盖）。
    """
    fact = observation.fact
    required_source_types = {
        item.strip().casefold() for item in template.required_source_types
    }
    observed_source_types = {
        item.strip().casefold() for item in observation.source_types
    }
    expanded_source_types = set(observed_source_types)
    for source_type in observed_source_types:
        expanded_source_types.update(_SOURCE_TYPE_FAMILIES.get(source_type, ()))
    source_type_matches = not required_source_types or bool(
        expanded_source_types & required_source_types
    )
    # A laboratory result or generic chart category is not written investigator judgment.
    if "investigator_assessment" in required_source_types:
        source_type_matches = "investigator_assessment" in observed_source_types
    objective_matches = (
        not template.requires_contemporaneous_objective_source
        or fact.source_strength == SourceStrength.CONTEMPORANEOUS_OBJECTIVE
    )
    if (
        fact.source_strength in _DEFAULT_STRONG_SOURCES
        and source_type_matches
        and objective_matches
    ):
        return "complete"
    if (
        fact.source_strength == SourceStrength.SCREENING_RECORD_TRANSCRIPTION
        and template.allows_screening_record_transcription
    ):
        return "weak"
    if fact.source_strength == SourceStrength.SCREENING_RECORD_TRANSCRIPTION:
        return "none"
    if fact.source_strength != SourceStrength.UNVERIFIABLE:
        return "weak"
    return "none"


def _matching_observations(
    template: EvidenceExpectationTemplate,
    authority: FactAuthority,
    observations: Sequence[CoverageObservation],
) -> list[CoverageObservation]:
    """覆盖观察过滤：同权威元组 + 明确资料要求绑定。"""
    return [
        observation
        for observation in observations
        if observation.fact.authority == authority
        and template.requirement_id in observation.fact.supported_requirement_ids
    ]


def _signals_for(
    template: EvidenceExpectationTemplate,
    gap_signals: Sequence[CoverageGapSignal],
) -> list[CoverageGapSignal]:
    return [
        signal
        for signal in gap_signals
        if signal.applies_to_template_id in (None, template.template_id)
    ]


def _coverage_locators(facts: Sequence[ClinicalFactV2]) -> list[str]:
    return sorted({locator_id for fact in facts for locator_id in fact.locator_ids})


def project_expectation(
    *,
    template: EvidenceExpectationTemplate,
    authority: FactAuthority,
    current_stage: ReviewStage,
    observations: Sequence[CoverageObservation],
    gap_signals: Sequence[CoverageGapSignal] = (),
    expectation_id: str | None = None,
    revision: int = 1,
    created_at: datetime | None = None,
) -> EvidenceExpectationV2:
    """投影单个模板的受试者级期望（纯函数，不做持久化）。

    ``observations`` 为结构化已发布事实（同权威元组过滤在投影器内执行）；
    ``gap_signals`` 为结构化缺失/风险输入。缺失/风险绝不从散文推断。
    """
    if (
        template.rule_set_id != authority.rule_set_id
        or template.rule_set_revision != authority.rule_set_revision
    ):
        raise ProjectionInputError(
            f"模板 {template.template_id} 不属于权威元组的规则集修订 "
            f"({authority.rule_set_id} r{authority.rule_set_revision})，拒绝投影"
        )
    signals = _signals_for(template, gap_signals)
    #: 冻结本次投影实际接收、适用于本模板的输入信号（含 fallback_only）：
    #: 每个返回路径都携带同一份 provenance，供后续修订重投影区分
    #: 「具体输入信号」与「兜底提示」/「无信号」，绝不从可见状态反推。
    input_provenance = canonical_input_gap_signals(template.template_id, signals)
    expectation_id = expectation_id or expectation_identity(
        authority.review_episode_id, template.template_id, revision
    )
    created_at = created_at or datetime.now(UTC)

    # 1. 尚未到期（优先级最高）。
    if stage_rank(template.due_stage) > stage_rank(current_stage):
        return EvidenceExpectationV2(
            expectation_id=expectation_id,
            authority=authority,
            template_id=template.template_id,
            status=ExpectationStatus.NOT_DUE,
            gap_type=GapType.FUTURE_STAGE_NOT_DUE,
            input_gap_signals=input_provenance,
            revision=revision,
            created_at=created_at,
        )

    # 2/3. 覆盖观察：同权威元组 + 显式资料要求绑定的已发布事实。
    matching = _matching_observations(template, authority, observations)
    verdicts = [
        (observation.fact, _coverage_verdict(observation, template))
        for observation in matching
    ]
    complete_facts = [fact for fact, verdict in verdicts if verdict == "complete"]
    weak_facts = [fact for fact, verdict in verdicts if verdict == "weak"]
    coverage_facts = complete_facts + weak_facts

    if coverage_facts:
        locator_ids = _coverage_locators(coverage_facts)
        coverage_fact_ids = sorted(fact.fact_id for fact in coverage_facts)
        ocr_risk = any(
            signal.kind == GapType.OCR_OR_PARSE_RISK for signal in signals
        )
        unverified = any(
            signal.kind == GapType.OBSERVATION_UNVERIFIED
            and (not signal.fallback_only or not complete_facts)
            for signal in signals
        )
        judgment_gap = next(
            (signal for signal in signals
             if signal.kind == GapType.PROFESSIONAL_JUDGMENT),
            None,
        )
        # 检验事实仍保留，但非要求来源不能覆盖研究者书面判断。
        if (
            not complete_facts
            and not ocr_risk
            and not unverified
            and judgment_gap is not None
            and "investigator_assessment" in {
                item.strip().casefold() for item in template.required_source_types
            }
        ):
            return EvidenceExpectationV2(
                expectation_id=expectation_id,
                authority=authority,
                template_id=template.template_id,
                status=ExpectationStatus.ABSENT,
                gap_type=GapType.PROFESSIONAL_JUDGMENT,
                input_gap_signals=input_provenance,
                revision=revision,
                gap_detail=judgment_gap.detail,
                created_at=created_at,
            )
        if complete_facts and not ocr_risk and not unverified:
            return EvidenceExpectationV2(
                expectation_id=expectation_id,
                authority=authority,
                template_id=template.template_id,
                status=ExpectationStatus.OBSERVED,
                input_gap_signals=input_provenance,
                revision=revision,
                locator_ids=locator_ids,
                coverage_fact_ids=coverage_fact_ids,
                source_coverage="complete",
                created_at=created_at,
            )
        # 较弱覆盖：OCR/解析风险 > 历史来源未就位 > 转述溯源提醒。
        if ocr_risk:
            gap_type = GapType.OCR_OR_PARSE_RISK
            provenance_followup = False
            reason = "覆盖证据受 OCR/解析风险影响，需人工校对后确认完整"
        elif unverified:
            gap_type = GapType.OBSERVATION_UNVERIFIED
            provenance_followup = False
            reason = "现有资料尚未核实是否包含本条要求的记录，暂无法判定"
        elif any(
            signal.kind == GapType.HISTORICAL_SOURCE_UNAVAILABLE
            for signal in signals
        ):
            gap_type = GapType.HISTORICAL_SOURCE_UNAVAILABLE
            provenance_followup = True
            reason = "既往原始资料未就位，当前覆盖来源较弱，需补充溯源"
        else:
            gap_type = GapType.PROVENANCE_FOLLOWUP
            provenance_followup = True
            reason = "当前覆盖来自较弱转述/非要求来源，需追溯更高等级来源"
        return EvidenceExpectationV2(
            expectation_id=expectation_id,
            authority=authority,
            template_id=template.template_id,
            status=ExpectationStatus.OBSERVED_WEAK,
            gap_type=gap_type,
            input_gap_signals=input_provenance,
            revision=revision,
            locator_ids=locator_ids,
            coverage_fact_ids=coverage_fact_ids,
            source_coverage="complete" if complete_facts else "weak",
            provenance_followup=provenance_followup,
            provenance_reason=reason,
            created_at=created_at,
        )

    # 4. 已引用未提供：只能由结构化缺失文件信号触发。
    referenced = [
        signal
        for signal in signals
        if signal.kind == GapType.REFERENCED_FILE_MISSING
    ]
    if referenced:
        return EvidenceExpectationV2(
            expectation_id=expectation_id,
            authority=authority,
            template_id=template.template_id,
            status=ExpectationStatus.REFERENCED_MISSING,
            gap_type=GapType.REFERENCED_FILE_MISSING,
            input_gap_signals=input_provenance,
            revision=revision,
            gap_detail=referenced[0].detail,
            created_at=created_at,
        )

    # 5. 未观察到：选择调用方供应的具体当前缺口，绝不回退通用缺口。
    for candidate in _ABSENT_GAP_PRECEDENCE:
        chosen = next(
            (signal for signal in signals if signal.kind == candidate), None
        )
        if chosen is not None:
            return EvidenceExpectationV2(
                expectation_id=expectation_id,
                authority=authority,
                template_id=template.template_id,
                status=ExpectationStatus.ABSENT,
                gap_type=candidate,
                input_gap_signals=input_provenance,
                revision=revision,
                gap_detail=chosen.detail,
                created_at=created_at,
            )
    raise ProjectionInputError(
        f"到期模板 {template.template_id} 无覆盖且未提供具体结构化缺口信号，"
        "拒绝以通用缺口回退"
    )


def project_expectations(
    *,
    templates: Sequence[EvidenceExpectationTemplate],
    authority: FactAuthority,
    current_stage: ReviewStage,
    observations: Sequence[CoverageObservation],
    gap_signals: Sequence[CoverageGapSignal] = (),
    revision: int = 1,
    created_at: datetime | None = None,
) -> list[EvidenceExpectationV2]:
    """投影当前审核节点规则修订的全部模板（一个模板恰好一条期望）。

    - 覆盖当前节点规则修订的所有模板（含未来到期节点模板 → not_due）；
    - 同一模板绝不重复投影（无双重报告）；结果按模板 ID 稳定排序。
    """
    created_at = created_at or datetime.now(UTC)
    projected: list[EvidenceExpectationV2] = []
    seen: set[str] = set()
    for template in sorted(templates, key=lambda item: item.template_id):
        if template.template_id in seen:
            raise ProjectionInputError(
                f"模板 {template.template_id} 重复出现，拒绝重复投影"
            )
        seen.add(template.template_id)
        projected.append(
            project_expectation(
                template=template,
                authority=authority,
                current_stage=current_stage,
                observations=observations,
                gap_signals=gap_signals,
                revision=revision,
                created_at=created_at,
            )
        )
    return projected
