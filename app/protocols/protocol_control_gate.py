"""Deterministic publication gates for Phase 5.8b/5.8c controls.

The control Agent and the batch hydrator deliberately stop before publication.
This module is the small, model-free boundary after hydration.  It does not
repair text, infer a phase, invent a workflow node, or resolve a conflict.  A
candidate/control is publishable only when the frozen manifest, planner
catalogues and source spans prove the claimed scope.

The public entry point raises :class:`ProtocolControlGateError` on the first
blocking finding and returns the unchanged catalog on success.  The separate
``check_*`` helper is intentionally non-throwing for callers that need a
bounded diagnostic without treating a rejected catalog as a draft repair.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.phase_applicability import PhaseApplicabilityDisposition
from app.domain.contracts.protocol_controls import (
    ControlConditionDnf,
    ControlExceptionDnf,
    ControlObligationKind,
    ControlObligationModality,
    ControlTemporalScopeKind,
    ControlObligationDnf,
    ControlRelationTargetKind,
    CrossSourceRelationKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlBatchDispositionHydrated,
    ProtocolControlBatchPlan,
    ProtocolControlCandidate,
    ProtocolControlCandidateSemantics,
    ProtocolControlUnitDisposition,
    ProtocolReviewControl,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    PublishedProtocolControlCatalog,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)
from app.protocols.full_protocol_coverage import FullProtocolCoverageResolutionView
from app.protocols.supplementary_relation_contract import (
    is_cross_stage_subsequent_control_supplement,
    procedure_execution_workflow_stage_id,
)
from app.protocols.protocol_control_planning import detect_required_action_kinds


CONTROL_PUBLICATION_GATE_VERSION = "phase5/control-publication-gate/v30"

__all__ = [
    "CONTROL_PUBLICATION_GATE_VERSION",
    "ProtocolControlGateError",
    "ProtocolControlPublicationError",
    "ProtocolControlGateIssue",
    "ProtocolControlGateReport",
    "check_protocol_control_batch_candidates",
    "validate_protocol_control_batch_candidates",
    "check_protocol_control_publication",
    "gate_protocol_control_publication",
    "publish_protocol_control_catalog",
    "validate_protocol_control_catalog",
    "validate_protocol_control_gate",
    "validate_protocol_control_publication",
]


class ProtocolControlGateError(ValueError):
    """A deterministic publication stop with a stable, searchable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        entity_id: str | None = None,
        structure_unit_ids: Sequence[str] = (),
        candidate_ids: Sequence[str] = (),
        obligation_source_span_ids: Sequence[str] = (),
    ) -> None:
        self.code = code
        self.message = message
        self.entity_id = entity_id
        self.structure_unit_ids = tuple(sorted(set(structure_unit_ids)))
        self.candidate_ids = tuple(sorted(set(candidate_ids)))
        self.obligation_source_span_ids = tuple(
            sorted(set(obligation_source_span_ids))
        )
        suffix = f" [{entity_id}]" if entity_id else ""
        super().__init__(f"{code}{suffix}: {message}")


# Naming alias for callers that use the publication boundary rather than the
# implementation name; both names carry the same stable ``code`` field.
ProtocolControlPublicationError = ProtocolControlGateError


@dataclass(frozen=True)
class ProtocolControlGateIssue:
    code: str
    message: str
    entity_id: str | None = None
    structure_unit_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    obligation_source_span_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProtocolControlGateReport:
    accepted: bool
    gate_version: str
    issues: tuple[ProtocolControlGateIssue, ...] = ()


_TEMPORAL_CUE_RE = re.compile(
    r"(?:首次给药|给药前|给药后|随机(?:化|分组)?|随机前|随机时|基线前|基线后|"
    r"筛选前|筛选后|洗脱|半衰期|试验期间|研究期间|至试验结束|至研究结束|"
    r"在此期间|\b(?:within|before|after|washout|half[- ]?life|until|throughout)\b|"
    r"\d+\s*(?:天|日|周|月|年|days?|weeks?|months?|years?)\s*(?:内|前|后)? )",
    re.IGNORECASE | re.VERBOSE,
)
_ENROLLMENT_PROHIBITION_RE = re.compile(
    r"(?:(?:筛选|导入|基线|入组前|随机(?:化|分组)?前|首次给药前)"
    r"[^。；;\n]{0,100}(?:不允许|不得|禁止|严禁|不应)"
    r"|(?:不允许|不得|禁止|严禁|不应)[^。；;\n]{0,100}"
    r"(?:筛选|导入|基线|入组前|随机(?:化|分组)?前|首次给药前))",
    re.IGNORECASE,
)
_ENROLLMENT_STAGE_RE = re.compile(r"筛选|导入|基线|入组前|随机(?:化|分组)?前|首次给药前")
_PROHIBITION_WORD_RE = re.compile(r"不允许|不得|禁止|严禁|不应")
_POST_ENROLLMENT_RE = re.compile(r"随机(?:化|分组)?后|首次给药后|治疗期|给药后")


def _normalize_prohibition_quote(value: str) -> str:
    return re.sub(r"[。；;]+$", "", re.sub(r"\s+", "", value))


def _split_prohibition_atom_covers_clause(clause: str, atom: object) -> bool:
    """Accept only a verbatim shared-action sentence split by review period."""

    continuation = getattr(atom, "continuing_obligation", None)
    if continuation is None or _value(getattr(continuation, "status", None)) != "not_due_at_review_node":
        return False
    if set(getattr(atom, "source_span_ids", ()) or ()) != set(
        getattr(continuation, "source_span_ids", ()) or ()
    ):
        return False

    def has_exact_sentence(excerpts: object) -> bool:
        return any(
            _normalize_prohibition_quote(sentence) == clause
            for quote in excerpts or () if isinstance(quote, str)
            for sentence in re.split(r"[。；;\n]", quote)
        )

    if not has_exact_sentence(getattr(atom, "source_excerpts", ())):
        return False
    if not has_exact_sentence(getattr(continuation, "source_excerpts", ())):
        return False
    current = _normalize_prohibition_quote(str(getattr(atom, "statement", "") or ""))
    proposition = _normalize_prohibition_quote(str(
        getattr(getattr(atom, "evaluation", None), "proposition", "") or ""
    ))
    future = _normalize_prohibition_quote(str(getattr(continuation, "statement", "") or ""))
    if current != proposition:
        return False
    matches = [_PROHIBITION_WORD_RE.search(text) for text in (clause, current, future)]
    if any(match is None for match in matches):
        return False
    source_match, current_match, future_match = matches
    if not (
        source_match.group() == current_match.group() == future_match.group()
        and clause[source_match.start():] == current[current_match.start():] == future[future_match.start():]
    ):
        return False
    source_prefix = clause[:source_match.start()]
    current_prefix = current[:current_match.start()]
    future_prefix = future[:future_match.start()]
    return any(
        source_prefix == f"{first}{separator}{second}"
        for first, second in ((current_prefix, future_prefix), (future_prefix, current_prefix))
        for separator in ("、", "，", ",", "和", "及", "与")
    )
_AND_CUE_RE = re.compile(
    r"(?:且|并且|同时|以及|均须|均需|both|\band\b)", re.IGNORECASE
)
_LONGER_OF_CUE_RE = re.compile(
    r"(?:以时间较长者为准|取较长|较长者|较长者为准|whichever\s+is\s+longer)",
    re.IGNORECASE,
)
_CONDITIONAL_SHORTEN_CUE_RE = re.compile(
    r"(?:(?:清除剂|洗脱).{0,32}(?:可缩短|缩短至)|可缩短至|缩短至|"
    r"washout\s+may\s+be\s+shortened)",
    re.IGNORECASE | re.DOTALL,
)
_STUDY_PERIOD_CUE_RE = re.compile(
    r"(?:试验期间|研究期间|整个试验|整个研究|至(?:试验|研究)结束|"
    r"until\s+(?:study\s+)?completion|throughout\s+the\s+study)",
    re.IGNORECASE,
)
_TREATMENT_PERIOD_CUE_RE = re.compile(
    r"(?:治疗期(?:间|内)?|用药期间|给药期间|during\s+(?:the\s+)?treatment)",
    re.IGNORECASE,
)
_SINCE_VISIT_REFERENCE_RE = re.compile(
    r"(?:自|从)?(?:筛选|基线|上次|前次|上一(?:次)?)[^，。；\n]{0,8}访视以来",
    re.IGNORECASE,
)
_PERIOD_CUE_AS_REPORTED_CONTENT_RE = re.compile(
    r"(?:确认[^，。；\n]{0,32}(?:知晓|理解)|知晓|理解|告知[^，。；\n]{0,32})$",
    re.IGNORECASE,
)
_ICF_BOUNDED_STUDY_PERIOD_RE = re.compile(
    r"(?:签署[^，。；\n]{0,24}知情同意[^，。；\n]{0,12}(?:开始|起))"
    r"[^。；\n]{0,96}(?:末次给药|研究结束|试验结束|随访结束)",
    re.IGNORECASE,
)
_CALENDAR_DURATION_RE = re.compile(
    r"(?P<value>\d+)\s*(?:个\s*)?(?P<unit>天|日|周|月|年|days?|weeks?|months?|years?)",
    re.IGNORECASE,
)
_TIME_BOUND_PREFIX_RE = re.compile(
    r"(?P<operator>≤|<=|不超过|至多|<|＜|少于|不足|≥|>=|不少于|至少|>|＞|超过|大于)"
    r"\s*(?P<value>\d+)\s*(?:个\s*)?"
    r"(?P<unit>天|日|周|月|年|days?|weeks?|months?|years?)",
    re.IGNORECASE,
)
_TIME_BOUND_SUFFIX_RE = re.compile(
    r"(?P<value>\d+)\s*(?:个\s*)?"
    r"(?P<unit>天|日|周|月|年|days?|weeks?|months?|years?)\s*(?:以内|内)",
    re.IGNORECASE,
)
_TIME_UNIT_CANONICAL = {
    "天": "day",
    "日": "day",
    "day": "day",
    "days": "day",
    "周": "week",
    "week": "week",
    "weeks": "week",
    "月": "month",
    "month": "month",
    "months": "month",
    "年": "year",
    "year": "year",
    "years": "year",
}
_AUTHORITY_REFERENCE_SOURCE_TYPE_RE = re.compile(
    r"(?:研究方案|方案(?:正文|原文|附录)|附录\s*\d*|评分细则|操作规范|"
    r"评估手册|评分手册|研究者手册|疗效评价\s*SOP|\bSOP\b)",
    re.IGNORECASE,
)
_SELF_REPORTED_INSTRUMENT_RE = re.compile(
    r"(?:患者|受试者|参与者).{0,12}(?:自填|自评|主观感受)|"
    r"(?:自填|自评)(?:量表|问卷)|(?:问卷).{0,24}(?:主观感受|生活质量)",
    re.IGNORECASE,
)
_PROFESSIONAL_ASSESSMENT_RE = re.compile(
    r"(?:研究者|医生|医师|临床医生|专业人员).{0,12}(?:判断|评估|评分|判定)|"
    r"(?:研究者判断|医生评分|医师评分|临床评估)",
    re.IGNORECASE,
)
_RESEARCHER_ASSESSMENT_SOURCE_RE = re.compile(
    r"(?:研究者|医生|医师|临床医生).{0,8}(?:判断|评估|评分|判定)(?:记录|表)?",
    re.IGNORECASE,
)
_MEASUREMENT_RECALL_PERIOD_RE = re.compile(
    r"(?:量表|问卷|评分|scale|questionnaire|score)"
    r"[^\u3002；;\n]{0,120}(?:用于)?评估"
    r"[^\u3002；;\n]{0,48}(?:过去|近|上)\s*\d+\s*"
    r"(?:天|日|周|月|年|days?|weeks?|months?|years?)(?:内)?",
    re.IGNORECASE,
)
_RECORD_UNIT_PATTERNS = {
    "unit:centimeter": re.compile(r"(?:厘米|cm(?![A-Za-z]))", re.IGNORECASE),
    "unit:kilogram": re.compile(r"(?:千克|公斤|kg(?![A-Za-z]))", re.IGNORECASE),
    "unit:millimeter": re.compile(r"(?:毫米|mm(?![A-Za-z]))", re.IGNORECASE),
    "unit:gram": re.compile(r"(?:(?<!千)克|(?<![A-Za-z])g(?![A-Za-z]))", re.IGNORECASE),
}
_INTEGER_PRECISION_RE = re.compile(r"(?:保留|记录为|精确到?)\s*(?:至|到)?\s*整数")
_DECIMAL_PRECISION_RES = (
    re.compile(r"小数点后\s*(?P<places>\d+)\s*位"),
    re.compile(r"保留\s*(?P<places>\d+)\s*位小数"),
)
_HALF_LIFE_DURATION_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:个\s*)?半衰期|"
    r"(?P<english_value>\d+(?:\.\d+)?)\s*half[- ]?lives?",
    re.IGNORECASE,
)
_EXCEPTION_BROAD_SCOPE_CUES = (
    "全部",
    "所有",
    "任一",
    "任意",
    "无论",
    "均适用",
    "all triggers",
    "any trigger",
)
_STRONG_CLAUSE_BOUNDARY_RE = re.compile(r"[。！？!?；;]+")
_CONDITIONAL_SUBJECT_RE = re.compile(
    r"(?:若|如|如果|当|凡|除非|的参与者|的患者|\b(?:if|when|unless)\b)",
    re.IGNORECASE,
)
_CONDITIONAL_ACTION_RE = re.compile(
    r"(?:需要|需|应|须|则|方可|不得|禁止|进行|完成|复测|检测|检查|评估|"
    r"\b(?:must|shall|should|requires?|perform|assess)\b)",
    re.IGNORECASE,
)
_PLANNED_VISIT_SCOPE_RE = re.compile(
    r"(?:各|每(?:次)?|所有)?(?<!未)(?<!非)计划(?:的)?访视(?:点)?",
    re.IGNORECASE,
)
_CONDITIONAL_CUE_AS_REPORTED_CONTENT_RE = re.compile(
    r"(?:告知|说明|提醒|确认(?:参与者|受试者)?(?:知晓|理解))"
    r"[^。；\n]{0,32}(?:如果|若|如|当)",
    re.IGNORECASE,
)
_EXCEPTION_CUE_RE = re.compile(r"(?:除非|除外|例外|\b(?:unless|except)\b)", re.IGNORECASE)
_OPTIONAL_ACTION_CUE_RE = re.compile(
    r"(?:可(?:以)?(?:进行|复测|检查|检测|评估|记录)|允许(?:进行|复测|检查|检测|评估|记录)|"
    r"\bmay\s+(?:perform|repeat|test|assess|record)\b)",
    re.IGNORECASE,
)
_OPTIONAL_ACTION_STATEMENT_RE = re.compile(r"(?:可|允许|\bmay\b)", re.IGNORECASE)
_BEST_EFFORT_CUE_RE = re.compile(
    r"(?:尽可能|在可获得范围内|尽力|尽量|as\s+(?:far|much)\s+as\s+possible|best\s+effort)",
    re.IGNORECASE,
)
_RECOMMENDED_CUE_RE = re.compile(r"(?:建议|推荐|recommended\b|recommend\b)", re.IGNORECASE)
_RECOMMENDED_NEGATION_SUFFIX_RE = re.compile(
    r"(?:暂|并|通常|一般|原则上)?不$|尚?未$|非$|无须?$|"
    r"\bnot(?:\s+\w+){0,2}\s+$|\b(?:isn't|isnt|aren't|arent)\s+$",
    re.IGNORECASE,
)
_PARTICIPANT_PREPARATION_RECAST_AS_ADVICE_RE = re.compile(
    r"(?:核对|确认|查看|判断)?[^。；\n]{0,20}(?:是否|有无)?"
    r"(?:已)?建议(?:参与者|受试者)[^。；\n]{0,20}"
    r"(?:静息|安静休息|休息|脱掉|脱去|摘掉|取下|排空膀胱)"
)
_ITEM_COUNT_RE = re.compile(r"(?P<count>[一二三四五六七八九十]|\d+)\s*项")
_CHINESE_ITEM_COUNTS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_COLLECTION_ACTION_CUE_RE = re.compile(
    r"(?:收集|采集|问询|记录).{0,48}(?:病史|治疗史|用药史|诊治情况)|"
    r"(?:病史|治疗史|用药史|诊治情况).{0,48}(?:收集|采集|问询|记录)|"
    r"\b(?:collect|record|obtain).{0,48}(?:history|treatment)\b",
    re.IGNORECASE,
)
_FULL_HISTORY_SCOPE_CUE_RE = re.compile(
    r"(?:完整|全部|全程|详细).{0,32}(?:病史|病程|治疗史)|"
    r"(?:诊断时间).{0,48}(?:病程)|尽可能收集.{0,32}(?:相关)?治疗史|"
    r"\b(?:complete|entire|full).{0,24}(?:history|course)\b",
    re.IGNORECASE,
)
_OFFICIAL_RULE_SCOPE_CUE_RE = re.compile(
    r"(?:入选|排除|入排)(?:标准|条款|规则).{0,48}(?:时间范围|规定时间|时间窗)|"
    r"(?:时间范围|规定时间|时间窗).{0,48}(?:入选|排除|入排)(?:标准|条款|规则)|"
    r"\b(?:inclusion|exclusion|eligibility).{0,48}(?:window|lookback|period)\b",
    re.IGNORECASE,
)
_SINCE_PREVIOUS_VISIT_CUE_RE = re.compile(
    r"(?:自|从)?(?:筛选|基线|上次|前次|最近一次)访视以来|"
    r"\bsince\s+(?:the\s+)?(?:screening|baseline|previous|last)\s+visit\b",
    re.IGNORECASE,
)
_EXEMPTION_MODALITY_RE = re.compile(
    r"(?:无需|不需要|不要求|可免(?:除)?|\b(?:not\s+required|need\s+not)\b)",
    re.IGNORECASE,
)
_CONDITIONAL_EXEMPTION_SOURCE_RE = re.compile(
    r"(?:若|如|如果|当|符合|满足|可接受|\b(?:if|when|provided\s+that)\b)"
    r"[^；\n]{0,160}[,，。；;][^。；\n]{0,48}"
    r"(?:无需|不需要|不要求|可免(?:除)?|\b(?:not\s+required|need\s+not)\b)",
    re.IGNORECASE,
)
_EXEMPTION_NONOCCURRENCE_EVIDENCE_RE = re.compile(
    r"(?:"
    r"(?:未|没有|无)[^。；\n]{0,16}(?:再次|重复|重新|再行|再做)"
    r"[^。；\n]{0,24}(?:检查|检测|执行|操作|处置|复测)|"
    r"(?:未做|没有做|未进行)[^。；\n]{0,24}(?:检查|检测|执行|操作|处置|复测)|"
    r"(?:无重复|无再次)[^。；\n]{0,24}(?:检查|检测|执行|操作|处置|复测|记录)|"
    r"\b(?:no\s+repeat|not\s+repeated|did\s+not\s+repeat|without\s+repeat(?:ing)?)\b"
    r"[^.;\n]{0,40}(?:test|check|exam|assessment|procedure)?"
    r")",
    re.IGNORECASE,
)
_RANDOMIZATION_EVENT_RE = re.compile(r"(?:不得|禁止).{0,12}(?:被)?随机(?:分组)?")
_FIRST_DOSE_EVENT_RE = re.compile(r"(?:不得|禁止).{0,12}(?:首次)?给药")
_TRIGGER_DECISION_STAGE_CUES = {
    "screening": re.compile(r"(?:筛选时|筛选访视|筛选日|\bscreening(?:\s+(?:visit|date|result))?\b)", re.IGNORECASE),
    "baseline": re.compile(r"(?:基线时|基线访视|基线日|\bbaseline(?:\s+(?:visit|date|result))?\b)", re.IGNORECASE),
    "randomization": re.compile(
        r"(?:随机(?:化|分组)?(?:前|时|日)|\b(?:before\s+)?randomi[sz]ation\b)",
        re.IGNORECASE,
    ),
    "first_dose": re.compile(
        r"(?:(?:研究药物)?首次给药前|\bbefore\s+(?:the\s+)?first\s+dose\b)",
        re.IGNORECASE,
    ),
}
_ROUTINE_ACTION_RE = re.compile(
    r"(?:必须|应|须|需(?:要)?|将).{0,48}(?:进行|完成|记录|核对|检查|检测|评估|提供|采集)|"
    r"(?:^|[，,；;。.!！？?])\s*(?:进行|完成|记录|核对|检查|检测|评估|提供|采集)|"
    r"\b(?:must|shall|should|required\s+to).{0,48}(?:perform|complete|record|verify|assess|provide|collect)\b",
    re.IGNORECASE,
)
_PHASE_QUALIFIED_VISIT_RE = re.compile(
    r"(?:第?\s*\d+(?:\s*[、,，]\s*\d+)*\s*周(?:访视)?|"
    r"[WD]\s*[-≤]?\s*\d+(?:\s*[、,，]\s*\d+)*)\s*"
    r"[（(]\s*(?P<phase>Ⅱ|Ⅲ|II|III|2|3)\s*期[^）)]*[）)]",
    re.IGNORECASE,
)
_NUMBERED_WEEK_RE = re.compile(
    r"第\s*(?P<weeks>\d+(?:\s*[、,，]\s*\d+)*)\s*周"
)
_WEEK_VISIT_RE = re.compile(r"\bW\s*[-≤]?\s*(?P<week>\d+)\b", re.IGNORECASE)
_DAY_VISIT_RE = re.compile(r"\bD\s*[-≤]?\s*(?P<day>\d+)\b", re.IGNORECASE)


def _value(value: object) -> str | None:
    """Read an enum or a deliberately malformed model_copy value safely."""

    if value is None:
        return None
    return str(getattr(value, "value", value))


def _fail(
    code: str,
    message: str,
    *,
    entity_id: str | None = None,
    structure_unit_ids: Sequence[str] = (),
    candidate_ids: Sequence[str] = (),
    obligation_source_span_ids: Sequence[str] = (),
) -> None:
    raise ProtocolControlGateError(
        code,
        message,
        entity_id=entity_id,
        structure_unit_ids=structure_unit_ids,
        candidate_ids=candidate_ids,
        obligation_source_span_ids=obligation_source_span_ids,
    )


def _ids(values: Iterable[object], field: str) -> list[str]:
    result: list[str] = []
    for value in values:
        item = getattr(value, field, None)
        if not isinstance(item, str) or not item.strip():
            _fail("IDENTITY_MISSING", f"{field} 缺失或为空")
        result.append(item)
    if len(result) != len(set(result)):
        _fail("IDENTITY_DUPLICATE", f"{field} 不得重复")
    return result


def _manifest_units(
    coverage_manifest: ProtocolSectionCoverageManifest,
) -> tuple[dict[str, ProtocolStructureUnit], set[str]]:
    units = list(getattr(coverage_manifest, "units", ()))
    unit_by_id: dict[str, ProtocolStructureUnit] = {}
    for unit in units:
        unit_id = getattr(unit, "structure_unit_id", None)
        if not isinstance(unit_id, str) or not unit_id.strip():
            _fail("MANIFEST_UNIT_ID_MISSING", "全文结构单元缺少稳定身份")
        if unit_id in unit_by_id:
            _fail("MANIFEST_UNIT_DUPLICATE", "全文结构单元身份重复", entity_id=unit_id)
        unit_by_id[unit_id] = unit
    if not unit_by_id:
        _fail("MANIFEST_EMPTY", "全文覆盖清单不能为空")
    span_ids = {
        span_id
        for unit in unit_by_id.values()
        for span_id in getattr(unit, "source_span_ids", ())
    }
    return unit_by_id, span_ids


def _check_phase_applicability(
    coverage_manifest: ProtocolSectionCoverageManifest,
    unit_by_id: dict[str, ProtocolStructureUnit],
    *,
    resolved_view: FullProtocolCoverageResolutionView | None = None,
) -> dict[str, PhaseApplicabilityDisposition]:
    phase = _value(getattr(coverage_manifest, "study_phase", None))
    if phase not in {
        StudyPhase.PHASE_II.value,
        StudyPhase.PHASE_III.value,
        StudyPhase.SEAMLESS_II_III.value,
    }:
        _fail("PHASE_UNRESOLVED", "发布必须绑定已确认的 II/III 或无缝期别")

    if resolved_view is not None:
        if resolved_view.coverage_manifest.manifest_id != coverage_manifest.manifest_id:
            _fail(
                "PHASE_APPLICABILITY_VIEW_MANIFEST_MISMATCH",
                "期别语义结果视图未绑定当前全文覆盖清单",
            )
        if resolved_view.coverage_manifest.protocol_version_id != coverage_manifest.protocol_version_id:
            _fail(
                "PHASE_APPLICABILITY_VIEW_PROTOCOL_VERSION_MISMATCH",
                "期别语义结果视图未绑定当前方案版本",
            )
        if resolved_view.coverage_manifest.protocol_document_sha256 != coverage_manifest.protocol_document_sha256:
            _fail(
                "PHASE_APPLICABILITY_VIEW_HASH_MISMATCH",
                "期别语义结果视图未绑定当前方案原文哈希",
            )
        if resolved_view.coverage_manifest.study_phase != coverage_manifest.study_phase:
            _fail(
                "PHASE_APPLICABILITY_VIEW_PHASE_MISMATCH",
                "期别语义结果视图未绑定当前选定期别",
            )
        if tuple(resolved_view.coverage_manifest.units) != tuple(coverage_manifest.units):
            _fail(
                "PHASE_APPLICABILITY_VIEW_SOURCE_MISMATCH",
                "期别语义结果视图的冻结结构单元与当前全文覆盖清单不一致",
            )
        if not resolved_view.accepted:
            if resolved_view.issues:
                issue = resolved_view.issues[0]
                code = (
                    "PHASE_APPLICABILITY_UNRESOLVED"
                    if resolved_view.pending_structure_unit_ids
                    else issue.code
                )
                _fail(code, issue.message, entity_id=issue.structure_unit_id)
            pending = ",".join(resolved_view.pending_structure_unit_ids)
            _fail(
                "PHASE_APPLICABILITY_UNRESOLVED",
                "仍有未完成期别语义结果：" + pending,
            )

        resolved_by_unit = resolved_view.resolution_by_unit
        if set(resolved_by_unit) != set(unit_by_id):
            _fail(
                "PHASE_APPLICABILITY_SCOPE_INCOMPLETE",
                "期别语义结果视图未逐项覆盖全文结构单元",
            )
        for unit_id in unit_by_id:
            disposition = resolved_by_unit.get(unit_id)
            if disposition is None or disposition == PhaseApplicabilityDisposition.UNRESOLVED:
                _fail(
                    "PHASE_APPLICABILITY_UNRESOLVED",
                    "结构单元仍缺少可发布的期别语义处置",
                    entity_id=unit_id,
                )
            if _value(getattr(unit_by_id[unit_id], "study_phase", None)) != phase:
                _fail(
                    "PHASE_MISMATCH",
                    "结构单元期别与覆盖清单期别不一致",
                    entity_id=unit_id,
                )
        return resolved_by_unit

    selected_scope = {
        StudyPhase.PHASE_II.value: PhaseScope.PHASE_II,
        StudyPhase.PHASE_III.value: PhaseScope.PHASE_III,
        StudyPhase.SEAMLESS_II_III.value: PhaseScope.SEAMLESS_CANDIDATE,
    }[phase]
    opposite_scope = {
        StudyPhase.PHASE_II.value: PhaseScope.PHASE_III,
        StudyPhase.PHASE_III.value: PhaseScope.PHASE_II,
        StudyPhase.SEAMLESS_II_III.value: None,
    }[phase]
    structural_dispositions: dict[str, PhaseApplicabilityDisposition] = {}

    for unit_id, unit in unit_by_id.items():
        if _value(getattr(unit, "study_phase", None)) != phase:
            _fail(
                "PHASE_MISMATCH",
                "结构单元期别与覆盖清单期别不一致",
                entity_id=unit_id,
            )
        scopes = {_value(scope) for scope in getattr(unit, "phase_scopes", ())}
        if len(scopes) != 1 or scopes & {
            PhaseScope.UNKNOWN.value,
            PhaseScope.MIXED.value,
        }:
            _fail(
                "PHASE_APPLICABILITY_UNRESOLVED",
                "结构单元的期别适用范围仍待确认或存在多期混合",
                entity_id=unit_id,
            )
        scope = next(iter(scopes))
        if scope == selected_scope.value:
            structural_dispositions[unit_id] = (
                PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE
            )
        elif scope == PhaseScope.SHARED.value:
            structural_dispositions[unit_id] = (
                PhaseApplicabilityDisposition.CROSS_PHASE_SHARED
            )
        elif opposite_scope is not None and scope == opposite_scope.value:
            structural_dispositions[unit_id] = (
                PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
            )
        else:
            _fail(
                "PHASE_APPLICABILITY_UNRESOLVED",
                "结构单元未证明属于选定期别、对侧期别或跨期共享范围",
                entity_id=unit_id,
            )
    return structural_dispositions


def _check_legacy_manifest_compatibility(
    coverage_manifest: ProtocolSectionCoverageManifest,
    authoritative_by_unit: dict[str, ProtocolControlUnitDisposition],
) -> None:
    """Audit the old singular surface without making it publication authority.

    The 5.8a manifest fields are retained as optional evidence for old
    snapshots.  In particular, ``linked_control_candidate_id`` is deliberately
    ignored here: a legacy row can name at most one candidate while the
    hydrated 5.8c disposition may own several.
    """

    dispositions = list(getattr(coverage_manifest, "dispositions", ()))
    seen: set[str] = set()
    for item in dispositions:
        unit_id = getattr(item, "structure_unit_id", None)
        if not isinstance(unit_id, str) or unit_id not in authoritative_by_unit:
            _fail(
                "DISPOSITION_UNIT_UNKNOWN",
                "处置引用了覆盖清单外的结构单元",
                entity_id=str(unit_id),
            )
        if unit_id in seen:
            _fail("DISPOSITION_DUPLICATE", "每个结构单元只能有一个主处置", entity_id=unit_id)
        seen.add(unit_id)
        authoritative = authoritative_by_unit[unit_id]
        kind = _value(getattr(item, "disposition", None))
        if kind != _value(getattr(authoritative, "disposition", None)):
            _fail(
                "LEGACY_DISPOSITION_CONFLICT",
                "旧版全文处置类型与水合批次权威处置不一致",
                entity_id=unit_id,
            )
        for field in (
            "linked_official_code",
            "linked_procedure_catalog_item_id",
        ):
            if getattr(item, field, None) != getattr(authoritative, field, None):
                _fail(
                    "LEGACY_DISPOSITION_CONFLICT",
                    "旧版全文处置字段与水合批次权威处置不一致",
                    entity_id=unit_id,
                )


def _check_catalog_identity(
    catalog: PublishedProtocolControlCatalog,
    coverage_manifest: ProtocolSectionCoverageManifest,
    manifest_span_ids: set[str],
) -> set[str]:
    expected_version = getattr(coverage_manifest, "protocol_version_id", None)
    if getattr(catalog, "protocol_version_id", None) != expected_version:
        _fail("PROTOCOL_VERSION_MISMATCH", "发布目录与全文覆盖清单方案版本不一致")
    if getattr(catalog, "study_phase", None) != getattr(
        coverage_manifest, "study_phase", None
    ):
        _fail("PHASE_MISMATCH", "发布目录与全文覆盖清单期别不一致")
    if getattr(catalog, "coverage_manifest_id", None) != getattr(
        coverage_manifest, "manifest_id", None
    ):
        _fail("MANIFEST_ID_MISMATCH", "发布目录未绑定当前全文覆盖清单")
    if getattr(catalog, "protocol_document_sha256", None) != getattr(
        coverage_manifest, "protocol_document_sha256", None
    ):
        _fail("PROTOCOL_HASH_MISMATCH", "发布目录与全文覆盖清单原文哈希不一致")

    allowed = set(getattr(catalog, "allowed_source_span_ids", ()))
    if not allowed:
        _fail("ALLOWED_SOURCE_SCOPE_EMPTY", "发布目录允许来源不能为空")
    outside = sorted(allowed - manifest_span_ids)
    if outside:
        _fail("ALLOWED_SOURCE_SCOPE_ESCAPE", "允许来源不属于全文清单：" + ",".join(outside))
    return allowed


def _target_signatures(
    plan: ProtocolControlBatchPlan,
) -> tuple[
    tuple[KnownOfficialRuleTarget, ...],
    tuple[KnownRequiredProcedureTarget, ...],
    tuple[KnownWorkflowStageTarget, ...],
]:
    batches = list(getattr(plan, "batches", ()))
    if not batches:
        _fail("PLAN_EMPTY", "发布计划不能为空")

    def signature(items: Iterable[object], fields: Sequence[str]) -> tuple[tuple[object, ...], ...]:
        return tuple(tuple(getattr(item, field, None) for field in fields) for item in items)

    first = batches[0]
    first_official = tuple(getattr(first, "known_official_targets", ()))
    first_procedure = tuple(getattr(first, "known_procedure_targets", ()))
    first_workflow = tuple(getattr(first, "known_workflow_stage_targets", ()))
    expected = (
        signature(first_official, ("catalog_item_id", "official_code", "position")),
        signature(first_procedure, ("catalog_item_id", "visit_instance", "review_stage", "position")),
        signature(first_workflow, ("workflow_stage_id", "review_stage", "visit_instance")),
    )
    for batch in batches[1:]:
        actual = (
            signature(getattr(batch, "known_official_targets", ()), ("catalog_item_id", "official_code", "position")),
            signature(getattr(batch, "known_procedure_targets", ()), ("catalog_item_id", "visit_instance", "review_stage", "position")),
            signature(getattr(batch, "known_workflow_stage_targets", ()), ("workflow_stage_id", "review_stage", "visit_instance")),
        )
        if actual != expected:
            _fail("FROZEN_TARGET_CATALOG_DRIFT", "不同批次的冻结目标目录不一致")

    workflow_ids = [getattr(item, "workflow_stage_id", None) for item in first_workflow]
    if len(workflow_ids) != len(set(workflow_ids)):
        _fail("WORKFLOW_TARGET_DUPLICATE", "冻结审核节点身份不得重复")
    workflow_keys = [
        (_value(getattr(item, "review_stage", None)), getattr(item, "visit_instance", None))
        for item in first_workflow
    ]
    if len(workflow_keys) != len(set(workflow_keys)):
        _fail("WORKFLOW_TARGET_DUPLICATE", "同一审核阶段下的访视实例不得折叠")
    return first_official, first_procedure, first_workflow


def _resolve_targets(
    plan: ProtocolControlBatchPlan | None,
    *,
    official_targets: Sequence[KnownOfficialRuleTarget],
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    workflow_stage_targets: Sequence[KnownWorkflowStageTarget],
) -> tuple[
    tuple[KnownOfficialRuleTarget, ...],
    tuple[KnownRequiredProcedureTarget, ...],
    tuple[KnownWorkflowStageTarget, ...],
]:
    if plan is not None:
        # The planner is the authority.  Explicit targets cannot override a
        # missing or changed planner catalogue.
        return _target_signatures(plan)
    workflow = tuple(workflow_stage_targets)
    workflow_ids = [getattr(item, "workflow_stage_id", None) for item in workflow]
    if len(workflow_ids) != len(set(workflow_ids)):
        _fail("WORKFLOW_TARGET_DUPLICATE", "冻结审核节点身份不得重复")
    workflow_keys = [
        (_value(getattr(item, "review_stage", None)), getattr(item, "visit_instance", None))
        for item in workflow
    ]
    if len(workflow_keys) != len(set(workflow_keys)):
        _fail("WORKFLOW_TARGET_DUPLICATE", "同一审核阶段下的访视实例不得折叠")
    return tuple(official_targets), tuple(procedure_targets), workflow


def _selected_phase_visit_text(text: str, study_phase: StudyPhase) -> str:
    """Remove only explicitly opposite-phase visit phrases before scope checks."""

    selected = _value(study_phase)
    opposite_markers = (
        {"Ⅲ", "III", "3"}
        if selected == StudyPhase.PHASE_II.value
        else {"Ⅱ", "II", "2"}
        if selected == StudyPhase.PHASE_III.value
        else set()
    )

    def keep_or_remove(match: re.Match[str]) -> str:
        return "" if match.group("phase").upper() in opposite_markers else match.group(0)

    return _PHASE_QUALIFIED_VISIT_RE.sub(keep_or_remove, text)


def _visit_scope_keys(text: str) -> set[str]:
    """Project explicit visit names/numbers without inferring an unstated schedule."""

    # A phrase such as "问询筛选访视以来的病史" names the retrospective
    # interval start, not the visit where the question is performed.
    compact = _SINCE_VISIT_REFERENCE_RE.sub("", re.sub(r"\s+", "", text))
    keys: set[str] = set()
    if "筛选" in compact:
        keys.add("screening")
    if "基线" in compact:
        keys.add("baseline")
    if "首次给药" in compact or "给药前复核" in compact:
        keys.add("first_dose")
    if "随机" in compact:
        keys.add("randomization")
    if re.search(r"(?:提前退出|退出访视)", compact):
        keys.add("early_exit")
    for match in _NUMBERED_WEEK_RE.finditer(compact):
        for value in re.split(r"[、,，]", match.group("weeks")):
            keys.add(f"week:{int(value)}")
    keys.update(
        f"week:{int(match.group('week'))}" for match in _WEEK_VISIT_RE.finditer(compact)
    )
    keys.update(
        f"day:{int(match.group('day'))}" for match in _DAY_VISIT_RE.finditer(compact)
    )
    return keys


def _visit_scope_label(key: str) -> str:
    labels = {
        "screening": "筛选访视",
        "baseline": "基线访视",
        "first_dose": "首次给药前访视",
        "randomization": "随机访视",
        "early_exit": "提前退出访视",
    }
    if key.startswith("week:"):
        return f"第{key.split(':', 1)[1]}周访视"
    if key.startswith("day:"):
        return f"第{key.split(':', 1)[1]}天访视"
    return labels.get(key, key)


def _procedure_semantic_family_label(key: str) -> str:
    return {
        "medical_history": "病史",
        "treatment_history": "治疗史",
        "informed_consent": "知情同意",
        "demographics": "人口学资料",
    }.get(key, key)


def _check_required_procedure_visit_scope(
    *,
    disposition: ProtocolControlUnitDisposition,
    unit: ProtocolStructureUnit,
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    study_phase: StudyPhase,
    owned_visit_instance: str | None = None,
    owned_procedure_semantic_families: Sequence[str] = (),
    owned_required_action_kinds: Sequence[str] = (),
    owned_required_procedure_target_ids: Sequence[str] = (),
) -> None:
    """A visit-level target may cover only visits present in its frozen identity."""

    linked_ids = set(disposition.linked_procedure_catalog_item_ids) or {
        disposition.linked_procedure_catalog_item_id
    }
    targets = [
        item for item in procedure_targets if item.catalog_item_id in linked_ids
    ]
    source_text = _selected_phase_visit_text(unit.excerpt, study_phase)
    if owned_required_procedure_target_ids:
        claimed_visits = {
            key
            for target in procedure_targets
            if target.catalog_item_id in set(owned_required_procedure_target_ids)
            for key in _visit_scope_keys(target.visit_instance)
        }
    else:
        claimed_visits = _visit_scope_keys(source_text)
        if owned_visit_instance is not None:
            claimed_visits.update(_visit_scope_keys(owned_visit_instance))
    covered_visits = {
        key
        for target in targets
        for key in _visit_scope_keys(target.visit_instance)
    }
    uncovered = sorted(claimed_visits - covered_visits)
    if uncovered:
        _fail(
            "PROCEDURE_VISIT_SCOPE_UNCOVERED",
            "流程必做处置声称完整覆盖原文，但链接目录项未覆盖原文中的全部选定期访视："
            + "、".join(_visit_scope_label(key) for key in uncovered),
            entity_id=disposition.structure_unit_id,
        )
    overbound = sorted(covered_visits - claimed_visits)
    if claimed_visits and overbound:
        _fail(
            "PROCEDURE_VISIT_SCOPE_OVERBOUND",
            "流程必做处置链接了原文未声明的选定期访视："
            + "、".join(_visit_scope_label(key) for key in overbound),
            entity_id=disposition.structure_unit_id,
        )
    linked_families = {
        target.semantic_family
        for target in targets
        if target.semantic_family is not None
    }
    missing_families = sorted(
        set(owned_procedure_semantic_families) - linked_families
    )
    if missing_families:
        _fail(
            "PROCEDURE_SEMANTIC_FAMILY_UNCOVERED",
            "流程必做处置遗漏了原文明示且同一访视已有冻结目录的资料家族："
            + "、".join(
                _procedure_semantic_family_label(family)
                for family in missing_families
            ),
            entity_id=disposition.structure_unit_id,
        )
    covered_action_kinds = {
        action_kind
        for target in targets
        for action_kind in target.covered_action_kinds
    }
    missing_action_kinds = sorted(
        set(owned_required_action_kinds) - covered_action_kinds
    )
    if missing_action_kinds:
        _fail(
            "PROCEDURE_ACTION_UNCOVERED",
            "流程必做处置声称完整覆盖原文，但链接目录未覆盖原文中的独立动作："
            + "、".join(missing_action_kinds)
            + "。必须将该单元处置为其他控制候选，仅保留未覆盖动作并关联已知流程目标。",
            entity_id=disposition.structure_unit_id,
        )


def _candidate_procedure_covered_action_kinds(
    candidate: ProtocolControlCandidate,
    procedure_by_id: dict[str, KnownRequiredProcedureTarget],
) -> set[str]:
    """Actions already covered by procedure targets linked from one candidate."""

    semantics = candidate.semantics
    if semantics is None:
        return set()
    covered: set[str] = set()
    for relation in semantics.cross_source_relations or ():
        for target_kind, target_id in (
            (_value(relation.left_target_kind), relation.left_target_id),
            (_value(relation.right_target_kind), relation.right_target_id),
        ):
            if target_kind != ControlRelationTargetKind.REQUIRED_PROCEDURE.value:
                continue
            target = procedure_by_id.get(str(target_id))
            if target is not None:
                covered.update(target.covered_action_kinds)
    return covered


def _obligation_statement_action_kinds(
    obligation_expression: object,
    *,
    source_span_ids: set[str] | None = None,
) -> set[str]:
    """Action kinds explicitly preserved in source-local obligation statements."""

    covered: set[str] = set()
    for atom in _iter_expression_atoms(obligation_expression):
        atom_span_ids = set(getattr(atom, "source_span_ids", ()) or ())
        if source_span_ids is not None and not atom_span_ids & source_span_ids:
            continue
        covered.update(
            detect_required_action_kinds(str(getattr(atom, "statement", "")))
        )
    return covered


def _check_review_guidance_action_fidelity(
    *,
    entity_id: str,
    units: Sequence[ProtocolStructureUnit],
    obligation_expression: object,
    bindings: Sequence[object],
) -> None:
    """Reject user guidance that substitutes an action absent from the source."""

    source_actions = {
        action
        for unit in units
        for action in detect_required_action_kinds(unit.excerpt)
    }
    obligation_actions = _obligation_statement_action_kinds(obligation_expression)
    guidance_actions = {
        action
        for binding in bindings
        for action in detect_required_action_kinds(
            str(getattr(binding, "guidance", "") or "")
        )
    }
    invented_actions = sorted(guidance_actions - source_actions - obligation_actions)
    if invented_actions:
        _fail(
            "REVIEW_GUIDANCE_ACTION_INVENTED",
            "审核指引不得把原文要求替换为另一项动作；下列动作没有来源或义务支持："
            + "、".join(invented_actions),
            entity_id=entity_id,
        )


def _check_minimum_evidence_modality_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
    evidence: Sequence[object],
) -> None:
    """Keep softened source duties softened when evidence describes the action."""

    evidence_text = " ".join(
        str(getattr(item, "description", "") or "") for item in evidence
    )
    evidence_actions = set(detect_required_action_kinds(evidence_text))
    if not evidence_actions:
        return

    for atom in _iter_expression_atoms(obligation_expression):
        modality = _value(getattr(atom, "modality", None))
        if modality not in {
            ControlObligationModality.RECOMMENDED.value,
            ControlObligationModality.BEST_EFFORT.value,
        }:
            continue
        action_kinds = set(
            detect_required_action_kinds(
                " ".join(
                    (
                        str(getattr(atom, "statement", "") or ""),
                        *(
                            str(item)
                            for item in getattr(atom, "source_excerpts", ()) or ()
                        ),
                    )
                )
            )
        )
        if not action_kinds & evidence_actions:
            continue
        cue_present = (
            _has_recommended_cue(evidence_text)
            if modality == ControlObligationModality.RECOMMENDED.value
            else bool(_BEST_EFFORT_CUE_RE.search(evidence_text))
        )
        if not cue_present:
            _fail(
                "MINIMUM_EVIDENCE_MODALITY_DROPPED",
                "最低证据描述涉及建议或尽力完成的动作时，必须显式保留原完成强度，"
                "不得将其写成必须达到的证据条件",
                entity_id=entity_id,
            )


def _check_minimum_evidence_authority_boundary(
    *,
    entity_id: str,
    evidence: Sequence[object],
) -> None:
    """Keep protocol authority references out of participant evidence needs."""

    conflated = sorted(
        {
            str(source_type).strip()
            for item in evidence
            for source_type in getattr(item, "required_source_types", ()) or ()
            if _AUTHORITY_REFERENCE_SOURCE_TYPE_RE.search(str(source_type))
        }
    )
    if conflated:
        _fail(
            "MINIMUM_EVIDENCE_AUTHORITY_SOURCE_CONFLATED",
            "方案、附录、评分细则、操作规范、评估手册或SOP是规则依据，不得列为受试者个例最低证据："
            + "、".join(conflated),
            entity_id=entity_id,
        )


def _check_professional_judgment_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
    evidence: Sequence[object],
) -> None:
    """Do not turn a patient-reported instrument into investigator judgment."""

    atoms = list(_iter_expression_atoms(obligation_expression))
    self_reported = False
    has_professional_atom = False
    for atom in atoms:
        atom_requires_judgment = bool(
            getattr(atom, "requires_professional_judgment", False)
        )
        text = " ".join(
            (
                str(getattr(atom, "statement", "") or ""),
                *(str(item) for item in getattr(atom, "source_excerpts", ()) or ()),
            )
        )
        is_self_reported = bool(_SELF_REPORTED_INSTRUMENT_RE.search(text))
        self_reported = self_reported or is_self_reported
        has_professional_atom = has_professional_atom or atom_requires_judgment
        if atom_requires_judgment and is_self_reported and not _PROFESSIONAL_ASSESSMENT_RE.search(text):
            _fail(
                "SELF_REPORTED_TOOL_MARKED_PROFESSIONAL",
                "患者自填或自评工具不得仅因需要审核而标记为研究者专业判断",
                entity_id=entity_id,
            )
    if self_reported and not has_professional_atom:
        researcher_sources = sorted(
            {
                str(source_type).strip()
                for item in evidence
                for source_type in getattr(item, "required_source_types", ()) or ()
                if _RESEARCHER_ASSESSMENT_SOURCE_RE.search(str(source_type))
            }
        )
        if researcher_sources:
            _fail(
                "SELF_REPORTED_TOOL_RESEARCHER_EVIDENCE",
                "纯患者自填或自评工具不得额外要求研究者评估记录："
                + "、".join(researcher_sources),
                entity_id=entity_id,
            )


def _check_authority_reference_provenance(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Require each authority reference to be supported by that atom's excerpts."""

    for atom in _iter_expression_atoms(obligation_expression):
        statement = str(getattr(atom, "statement", "") or "")
        if not _AUTHORITY_REFERENCE_SOURCE_TYPE_RE.search(statement):
            continue
        excerpts = " ".join(
            str(item) for item in getattr(atom, "source_excerpts", ()) or ()
        )
        if not _AUTHORITY_REFERENCE_SOURCE_TYPE_RE.search(excerpts):
            _fail(
                "AUTHORITY_REFERENCE_SOURCE_DROPPED",
                "义务陈述中的附录、评分细则、操作规范、评估手册或SOP引用必须由该原子的直接摘录支持",
                entity_id=entity_id,
            )


def _check_participant_preparation_realization_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
    user_facing_texts: Sequence[str],
) -> None:
    """Do not turn a softened preparation action into proof that advice was given."""

    has_preparation_obligation = any(
        "prepare_participant"
        in detect_required_action_kinds(
            " ".join(
                (
                    str(getattr(atom, "statement", "") or ""),
                    *(
                        str(item)
                        for item in getattr(atom, "source_excerpts", ()) or ()
                    ),
                )
            )
        )
        for atom in _iter_expression_atoms(obligation_expression)
    )
    if not has_preparation_obligation:
        return
    if any(
        _PARTICIPANT_PREPARATION_RECAST_AS_ADVICE_RE.search(text)
        for text in user_facing_texts
    ):
        _fail(
            "PARTICIPANT_PREPARATION_RECAST_AS_ADVICE",
            "建议强度修饰的是参与者准备动作；审核指引和最低证据应核对实际准备事实，"
            "不得改成核对是否向参与者提出建议",
            entity_id=entity_id,
        )


def _check_user_facing_item_count_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
    user_facing_texts: Sequence[str],
) -> None:
    """Keep explicit item counts consistent across structured and visible text."""

    def counts(texts: Sequence[str]) -> set[int]:
        values: set[int] = set()
        for text in texts:
            for match in _ITEM_COUNT_RE.finditer(text):
                raw = match.group("count")
                values.add(_CHINESE_ITEM_COUNTS.get(raw, int(raw) if raw.isdigit() else 0))
        values.discard(0)
        return values

    obligation_counts = counts(
        [
            str(getattr(atom, "statement", "") or "")
            for atom in _iter_expression_atoms(obligation_expression)
        ]
    )
    visible_counts = counts(user_facing_texts)
    if obligation_counts and visible_counts and obligation_counts != visible_counts:
        _fail(
            "USER_FACING_ITEM_COUNT_MISMATCH",
            "审核指引和最低证据中的项目数量必须与正式义务一致；"
            f"义务={sorted(obligation_counts)}，用户可见内容={sorted(visible_counts)}",
            entity_id=entity_id,
        )


def _check_obligation_source_action_impersonation(
    obligation_expression: object,
    *,
    entity_id: str,
    required_actions: set[str],
    statement_covered: set[str],
    procedure_covered: set[str],
    source_span_ids: set[str] | None = None,
) -> None:
    """Reject frozen actions that appear only in source excerpts, not obligations."""

    for atom in _iter_expression_atoms(obligation_expression):
        atom_span_ids = set(getattr(atom, "source_span_ids", ()) or ())
        if source_span_ids is not None and not atom_span_ids & source_span_ids:
            continue
        excerpts = " ".join(
            str(item) for item in getattr(atom, "source_excerpts", ()) or ()
        )
        excerpt_kinds = set(detect_required_action_kinds(excerpts))
        impersonated = (
            (excerpt_kinds & required_actions) - statement_covered - procedure_covered
        )
        if impersonated:
            _fail(
                "OBLIGATION_ACTION_SOURCE_ONLY",
                "来源摘录不能代替义务陈述保留独立动作；下列动作仅出现在来源摘录中："
                + "、".join(sorted(impersonated)),
                entity_id=entity_id,
                obligation_source_span_ids=list(
                    getattr(atom, "source_span_ids", ()) or ()
                ),
            )


def _check_hydrated_result_links(
    result: ProtocolControlBatchDispositionHydrated,
    *,
    known_procedure_targets: Sequence[KnownRequiredProcedureTarget],
    unit_by_id: dict[str, ProtocolStructureUnit],
    study_phase: StudyPhase,
    pre_enrollment_structure_unit_ids: Sequence[str] = (),
    structural_only_structure_unit_ids: Sequence[str] = (),
    owned_visit_instance_by_structure_unit_id: dict[str, str] | None = None,
    owned_procedure_semantic_families_by_structure_unit_id: dict[
        str, list[str]
    ] | None = None,
    owned_required_action_kinds_by_structure_unit_id: dict[
        str, list[str]
    ] | None = None,
    owned_required_procedure_target_ids_by_structure_unit_id: dict[
        str, list[str]
    ] | None = None,
) -> None:
    """Recheck candidate and visit-level procedure closure at publication."""

    known_procedure_ids = {
        item.catalog_item_id for item in known_procedure_targets
    }
    candidate_ids = _ids(result.candidates, "control_candidate_id")
    candidate_id_set = set(candidate_ids)
    disposition_by_unit = {
        item.structure_unit_id: item for item in result.dispositions
    }
    candidate_by_id = {
        item.control_candidate_id: item for item in result.candidates
    }
    clinical_dispositions = {
        StructureUnitDispositionKind.OFFICIAL_ELIGIBILITY.value,
        StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
        StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
    }
    invalid_structural_units = [
        item.structure_unit_id
        for item in result.dispositions
        if item.structure_unit_id in set(structural_only_structure_unit_ids)
        and _value(item.disposition) in clinical_dispositions
    ]
    if invalid_structural_units:
        _fail(
            "STRUCTURAL_LABEL_PROMOTED",
            "下列冻结单元只是章节标题或结构标签，不得处置为官方入排、流程必做或其他控制候选："
            + "、".join(invalid_structural_units),
            entity_id=result.batch_id,
            structure_unit_ids=invalid_structural_units,
        )
    pre_enrollment_ids = set(pre_enrollment_structure_unit_ids)
    non_enrollment_action_dispositions = {
        StructureUnitDispositionKind.POST_TREATMENT_EXECUTION.value,
        StructureUnitDispositionKind.NON_ENROLLMENT_EXECUTION.value,
    }
    discarded_actions: dict[str, list[str]] = {}
    for item in result.dispositions:
        required_actions = list(
            (owned_required_action_kinds_by_structure_unit_id or {}).get(
                item.structure_unit_id,
                [],
            )
        )
        disposition = _value(item.disposition)
        preserves_action = disposition in {
            StructureUnitDispositionKind.REQUIRED_PROCEDURE.value,
            StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
        }
        preserves_out_of_scope_action = (
            item.structure_unit_id not in pre_enrollment_ids
            and disposition in non_enrollment_action_dispositions
        )
        if required_actions and not (
            preserves_action or preserves_out_of_scope_action
        ):
            discarded_actions[item.structure_unit_id] = sorted(required_actions)
    if discarded_actions:
        _fail(
            "REQUIRED_ACTION_DISCARDED",
            "下列冻结来源包含必须保留的独立动作；保留动作不等于把其完成强度改为必做。"
            "不得仅因动作属于建议、尽力遵循，或只读上下文出现相似表述，就降为普通说明或无控制处置；"
            "入排阶段内若既有流程目录未完整覆盖，必须建立补充控制候选；"
            "明确属于治疗期或其他非入排阶段的动作，应保留为相应执行处置，不得强绑筛选或基线节点："
            + "；".join(
                f"{unit_id}=" + "、".join(actions)
                for unit_id, actions in sorted(discarded_actions.items())
            ),
            entity_id=result.batch_id,
            structure_unit_ids=discarded_actions,
        )

    uncovered_procedure_actions: dict[str, list[str]] = {}
    procedure_by_id = {
        item.catalog_item_id: item for item in known_procedure_targets
    }
    for item in result.dispositions:
        if _value(item.disposition) != StructureUnitDispositionKind.REQUIRED_PROCEDURE.value:
            continue
        required_actions = set(
            (owned_required_action_kinds_by_structure_unit_id or {}).get(
                item.structure_unit_id,
                [],
            )
        )
        procedure_ids = set(item.linked_procedure_catalog_item_ids)
        if item.linked_procedure_catalog_item_id is not None:
            procedure_ids.add(item.linked_procedure_catalog_item_id)
        covered_actions = {
            action_kind
            for procedure_id in procedure_ids
            for action_kind in (
                procedure_by_id.get(procedure_id).covered_action_kinds
                if procedure_id in procedure_by_id
                else []
            )
        }
        missing_actions = sorted(required_actions - covered_actions)
        if missing_actions:
            uncovered_procedure_actions[item.structure_unit_id] = missing_actions
    if uncovered_procedure_actions:
        _fail(
            "PROCEDURE_ACTION_UNCOVERED",
            "下列流程必做处置声称完整覆盖原文，但链接目录未覆盖其独立动作；"
            "必须同时改为其他控制候选，只保留未覆盖动作、保持原文完成强度并关联已知流程目标："
            + "；".join(
                f"{unit_id}=" + "、".join(actions)
                for unit_id, actions in sorted(uncovered_procedure_actions.items())
            ),
            entity_id=result.batch_id,
            structure_unit_ids=uncovered_procedure_actions,
        )

    candidate_obligation_gaps: dict[str, list[str]] = {}
    understated_action_relations: dict[str, list[str]] = {}
    for item in result.dispositions:
        if (
            _value(item.disposition)
            != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value
        ):
            continue
        required_actions = set(
            (owned_required_action_kinds_by_structure_unit_id or {}).get(
                item.structure_unit_id,
                [],
            )
        )
        if not required_actions:
            continue
        unit_source_span_ids = set(
            unit_by_id[item.structure_unit_id].source_span_ids
        )
        procedure_covered: set[str] = set()
        obligation_covered: set[str] = set()
        for candidate_id in item.linked_control_candidate_ids:
            candidate = candidate_by_id.get(candidate_id)
            if candidate is None:
                continue
            candidate_procedure_covered = _candidate_procedure_covered_action_kinds(
                candidate,
                procedure_by_id,
            )
            procedure_covered.update(candidate_procedure_covered)
            procedure_relations = [
                relation
                for relation in (
                    () if candidate.semantics is None else candidate.semantics.cross_source_relations
                )
                if ControlRelationTargetKind.REQUIRED_PROCEDURE.value
                in {
                    _value(relation.left_target_kind),
                    _value(relation.right_target_kind),
                }
            ]
            if (
                procedure_relations
                and required_actions - candidate_procedure_covered
                and not any(
                    _value(relation.kind)
                    == CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT.value
                    for relation in procedure_relations
                )
            ):
                understated_action_relations.setdefault(
                    item.structure_unit_id, []
                ).append(candidate_id)
            semantics = candidate.semantics
            if (
                semantics is not None
                and semantics.obligation_expression is not None
            ):
                statement_covered = _obligation_statement_action_kinds(
                    semantics.obligation_expression,
                    source_span_ids=unit_source_span_ids,
                )
                obligation_covered.update(statement_covered)
                _check_obligation_source_action_impersonation(
                    semantics.obligation_expression,
                    entity_id=candidate_id,
                    required_actions=required_actions,
                    statement_covered=statement_covered,
                    procedure_covered=procedure_covered,
                    source_span_ids=unit_source_span_ids,
                )
        missing = sorted(required_actions - procedure_covered - obligation_covered)
        if missing:
            candidate_obligation_gaps[item.structure_unit_id] = missing
    if candidate_obligation_gaps:
        _fail(
            "CANDIDATE_OBLIGATION_ACTION_UNCOVERED",
            "下列其他控制候选的义务陈述未逐项保留冻结来源中的独立动作；"
            "流程目录未覆盖的动作必须按原文完成强度写入候选义务，不能只改变处置类型："
            + "；".join(
                f"{unit_id}=" + "、".join(actions)
                for unit_id, actions in sorted(candidate_obligation_gaps.items())
            ),
            entity_id=result.batch_id,
            structure_unit_ids=candidate_obligation_gaps,
            candidate_ids=sorted(
                {
                    candidate_id
                    for unit_id in candidate_obligation_gaps
                    for candidate_id in disposition_by_unit[
                        unit_id
                    ].linked_control_candidate_ids
                }
            ),
        )

    if understated_action_relations:
        _fail(
            "ACTION_INCREMENT_RELATION_UNDERSTATED",
            "候选保留了流程目录未覆盖的独立动作时，与流程必做项的关系必须标记为补充要求，"
            "不得降为仅作进一步说明："
            + "；".join(
                f"{unit_id}=" + "、".join(sorted(candidate_ids))
                for unit_id, candidate_ids in sorted(
                    understated_action_relations.items()
                )
            ),
            entity_id=result.batch_id,
            structure_unit_ids=sorted(understated_action_relations),
            candidate_ids=sorted(
                {
                    candidate_id
                    for candidate_ids in understated_action_relations.values()
                    for candidate_id in candidate_ids
                }
            ),
        )

    target_scope_issues: dict[str, str] = {}
    for item in result.dispositions:
        expected = set(
            (owned_required_procedure_target_ids_by_structure_unit_id or {}).get(
                item.structure_unit_id,
                [],
            )
        )
        if not expected:
            continue
        disposition_kind = _value(item.disposition)
        if disposition_kind == StructureUnitDispositionKind.REQUIRED_PROCEDURE.value:
            actual = set(item.linked_procedure_catalog_item_ids)
            if item.linked_procedure_catalog_item_id is not None:
                actual.add(item.linked_procedure_catalog_item_id)
            candidate_target_sets: list[set[str]] = [actual]
        elif disposition_kind == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value:
            candidate_target_sets = []
            for candidate_id in item.linked_control_candidate_ids:
                candidate = candidate_by_id.get(candidate_id)
                relations = (
                    ()
                    if candidate is None or candidate.semantics is None
                    else candidate.semantics.cross_source_relations
                )
                candidate_target_sets.append(
                    {
                        str(target_id)
                        for relation in relations
                        for target_kind, target_id in (
                            (
                                _value(relation.left_target_kind),
                                relation.left_target_id,
                            ),
                            (
                                _value(relation.right_target_kind),
                                relation.right_target_id,
                            ),
                        )
                        if target_kind
                        == ControlRelationTargetKind.REQUIRED_PROCEDURE.value
                    }
                )
        else:
            candidate_target_sets = []
        actual_union = set().union(*candidate_target_sets) if candidate_target_sets else set()
        overreach = set().union(
            *(targets - expected for targets in candidate_target_sets)
        ) if candidate_target_sets else set()
        missing = expected - actual_union
        if overreach or missing:
            parts = []
            if missing:
                parts.append("漏绑=" + "、".join(sorted(missing)))
            if overreach:
                parts.append("越界=" + "、".join(sorted(overreach)))
            target_scope_issues[item.structure_unit_id] = "，".join(parts)
    if target_scope_issues:
        target_scope_candidate_ids = sorted(
            {
                candidate_id
                for unit_id in target_scope_issues
                for candidate_id in disposition_by_unit[
                    unit_id
                ].linked_control_candidate_ids
            }
        )
        _fail(
            "ACTION_TARGET_SCOPE_MISMATCH",
            "下列来源动作与冻结流程目标的适用范围不一致；不得把只属于较早节点的动作扩散到更晚节点，"
            "也不得遗漏原文明确适用的节点。请按相同目标集合拆分候选："
            + "；".join(
                f"{unit_id}={detail}"
                for unit_id, detail in sorted(target_scope_issues.items())
            ),
            entity_id=result.batch_id,
            structure_unit_ids=target_scope_issues,
            candidate_ids=target_scope_candidate_ids,
        )
    referenced_ids = {
        candidate_id
        for item in result.dispositions
        for candidate_id in item.linked_control_candidate_ids
    }
    unknown_ids = sorted(referenced_ids - candidate_id_set)
    if unknown_ids:
        _fail(
            "BATCH_CANDIDATE_LINK_UNKNOWN",
            "水合处置引用了批次结果外的候选身份：" + ",".join(unknown_ids),
            entity_id=result.batch_id,
        )
    if referenced_ids != candidate_id_set:
        _fail(
            "BATCH_CANDIDATE_LINK_INCOMPLETE",
            "水合批次候选必须全部被结构单元处置引用且不得遗漏",
            entity_id=result.batch_id,
        )
    for item in result.dispositions:
        links = list(item.linked_control_candidate_ids)
        required_action_kinds = list(
            (owned_required_action_kinds_by_structure_unit_id or {}).get(
                item.structure_unit_id,
                [],
            )
        )
        frozen_visit_instance = (
            (owned_visit_instance_by_structure_unit_id or {}).get(
                item.structure_unit_id
            )
        )
        procedure_ids = list(item.linked_procedure_catalog_item_ids) or (
            [item.linked_procedure_catalog_item_id]
            if item.linked_procedure_catalog_item_id is not None
            else []
        )
        if (
            item.structure_unit_id in set(pre_enrollment_structure_unit_ids)
            and _value(item.disposition)
            == StructureUnitDispositionKind.POST_TREATMENT_EXECUTION.value
        ):
            _fail(
                "PRE_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
                "冻结访视顺序已确认该操作发生在入排复核、随机或首次给药边界之前，不得处置为治疗后事项",
                entity_id=item.structure_unit_id,
            )
        if (
            frozen_visit_instance is not None
            and _value(item.disposition)
            != StructureUnitDispositionKind.REQUIRED_PROCEDURE.value
        ):
            _fail(
                "KNOWN_PROCEDURE_DISPOSITION_MISMATCH",
                "冻结流程已确认该单元为本节点必做事项，不得降级为普通补充说明或其他处置",
                entity_id=item.structure_unit_id,
            )
        if _value(item.disposition) == StructureUnitDispositionKind.REQUIRED_PROCEDURE.value:
            if not procedure_ids:
                _fail(
                    "BATCH_PROCEDURE_LINK_MISSING",
                    "流程必做处置必须绑定一个或多个访视级流程目录项",
                    entity_id=item.structure_unit_id,
                )
            unknown_procedure_ids = sorted(set(procedure_ids) - known_procedure_ids)
            if unknown_procedure_ids:
                _fail(
                    "BATCH_PROCEDURE_LINK_UNKNOWN",
                    "流程必做处置引用了批次计划外的访视级流程目录项："
                    + ",".join(unknown_procedure_ids),
                    entity_id=item.structure_unit_id,
                )
            _check_required_procedure_visit_scope(
                disposition=item,
                unit=unit_by_id[item.structure_unit_id],
                procedure_targets=known_procedure_targets,
                study_phase=study_phase,
                owned_visit_instance=frozen_visit_instance,
                owned_procedure_semantic_families=(
                    (owned_procedure_semantic_families_by_structure_unit_id or {}).get(
                        item.structure_unit_id,
                        [],
                    )
                ),
                owned_required_action_kinds=(
                    required_action_kinds
                ),
                owned_required_procedure_target_ids=(
                    (owned_required_procedure_target_ids_by_structure_unit_id or {}).get(
                        item.structure_unit_id,
                        [],
                    )
                ),
            )
        elif procedure_ids:
            _fail(
                "BATCH_PROCEDURE_LINK_INVALID",
                "非流程必做处置不得绑定访视级流程目录项",
                entity_id=item.structure_unit_id,
            )
        if _value(item.disposition) == StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value:
            if not links:
                _fail(
                    "BATCH_CANDIDATE_LINK_MISSING",
                    "其他控制处置必须绑定一个或多个水合候选",
                    entity_id=item.structure_unit_id,
                )
        elif links:
            _fail(
                "BATCH_CANDIDATE_LINK_INVALID",
                "非其他控制处置不得绑定水合候选",
                entity_id=item.structure_unit_id,
            )
    for candidate in result.candidates:
        referring_unit_ids = {
            item.structure_unit_id
            for item in result.dispositions
            if candidate.control_candidate_id in item.linked_control_candidate_ids
        }
        candidate_unit_ids = set(candidate.frozen_structure_unit_ids)
        if referring_unit_ids != candidate_unit_ids:
            _fail(
                "BATCH_CANDIDATE_UNIT_LINK_NOT_CLOSED",
                "水合候选与结构单元处置之间必须保持双向精确闭包",
                entity_id=candidate.control_candidate_id,
            )
        for unit_id in candidate_unit_ids:
            disposition = disposition_by_unit.get(unit_id)
            if disposition is None or (
                _value(disposition.disposition)
                != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value
            ):
                _fail(
                    "BATCH_CANDIDATE_UNIT_LINK_INVALID",
                    "水合候选来源结构单元必须是其他控制处置",
                    entity_id=candidate.control_candidate_id,
                )


def _check_plan_and_batch_results(
    coverage_manifest: ProtocolSectionCoverageManifest,
    plan: ProtocolControlBatchPlan | None,
    batch_dispositions: Sequence[ProtocolControlBatchDispositionHydrated],
) -> tuple[dict[str, ProtocolControlUnitDisposition], list[ProtocolControlCandidate]]:
    """Build the only publication disposition map from complete hydrated batches."""

    if plan is None:
        if batch_dispositions:
            _fail("PLAN_REQUIRED_FOR_BATCH_RESULTS", "批次结果必须绑定冻结处置计划")
        _fail(
            "PLAN_REQUIRED_FOR_PUBLICATION",
            "5.8b/5.8c 发布必须绑定冻结处置计划",
        )
    manifest_ids = [unit.structure_unit_id for unit in coverage_manifest.units]
    manifest_id_set = set(manifest_ids)
    if list(getattr(plan, "expected_structure_unit_ids", ())) != manifest_ids:
        _fail("PLAN_MANIFEST_SCOPE_MISMATCH", "计划必须逐项覆盖当前全文结构单元")
    if getattr(plan, "coverage_manifest_id", None) != coverage_manifest.manifest_id:
        _fail("MANIFEST_ID_MISMATCH", "计划未绑定当前全文覆盖清单")
    if getattr(plan, "protocol_version_id", None) != coverage_manifest.protocol_version_id:
        _fail("PROTOCOL_VERSION_MISMATCH", "计划未绑定当前方案版本")
    if getattr(plan, "study_phase", None) != coverage_manifest.study_phase:
        _fail("PHASE_MISMATCH", "计划未绑定当前方案期别")

    if not batch_dispositions:
        _fail(
            "BATCH_DISPOSITIONS_REQUIRED",
            "5.8b/5.8c 发布必须提供每个计划批次的完整水合结果",
        )
    batches = list(plan.batches)
    if len(batch_dispositions) != len(batches):
        _fail("BATCH_DISPOSITION_INCOMPLETE", "批次结果必须逐批返回且不得缺批")
    batch_by_id = {batch.batch_id: batch for batch in batches}
    result_by_id: dict[str, ProtocolControlBatchDispositionHydrated] = {}
    candidates: list[ProtocolControlCandidate] = []
    all_owned: list[str] = []
    authoritative_by_unit: dict[str, ProtocolControlUnitDisposition] = {}
    for result in batch_dispositions:
        if not isinstance(result, ProtocolControlBatchDispositionHydrated):
            _fail(
                "BATCH_RESULT_TYPE_INVALID",
                "发布批次结果必须是系统水合的完整结果",
            )
        batch_id = getattr(result, "batch_id", None)
        if batch_id in result_by_id:
            _fail("BATCH_RESULT_DUPLICATE", "批次结果身份重复", entity_id=str(batch_id))
        batch = batch_by_id.get(batch_id)
        if batch is None:
            _fail("BATCH_RESULT_UNKNOWN", "批次结果不属于当前计划", entity_id=str(batch_id))
        result_by_id[batch_id] = result
        if getattr(result, "coverage_manifest_id", None) != coverage_manifest.manifest_id:
            _fail(
                "MANIFEST_ID_MISMATCH",
                "批次结果未绑定当前全文覆盖清单",
                entity_id=batch_id,
            )
        if list(result.owned_structure_unit_ids) != list(batch.owned_structure_unit_ids):
            _fail(
                "BATCH_RESULT_SCOPE_MISMATCH",
                "批次结果所含结构单元与计划不一致",
                entity_id=batch_id,
            )
        if list(result.owned_source_span_ids) != list(batch.owned_source_span_ids):
            _fail("BATCH_RESULT_SOURCE_SCOPE_MISMATCH", "批次结果来源闭包与计划不一致", entity_id=batch_id)
        result_disposition_ids = [item.structure_unit_id for item in result.dispositions]
        if result_disposition_ids != list(batch.owned_structure_unit_ids):
            _fail(
                "BATCH_DISPOSITION_INCOMPLETE",
                "批次结果必须逐项处置所有本批待判断结构单元",
                entity_id=batch_id,
            )
        for item in result.dispositions:
            if item.structure_unit_id in authoritative_by_unit:
                _fail(
                    "BATCH_OWNERSHIP_NOT_CLOSED",
                    "每个全文结构单元只能由一个水合批次处置",
                    entity_id=item.structure_unit_id,
                )
            if item.structure_unit_id not in manifest_id_set:
                _fail("DISPOSITION_UNIT_UNKNOWN", "批次结果引用了未知结构单元", entity_id=item.structure_unit_id)
            authoritative_by_unit[item.structure_unit_id] = item
        uncovered = _uncovered_enrollment_prohibitions(batch, result)
        if uncovered:
            raise uncovered[0]
        _check_hydrated_result_links(
            result,
            known_procedure_targets=batch.known_procedure_targets,
            unit_by_id={unit.structure_unit_id: unit for unit in coverage_manifest.units},
            study_phase=coverage_manifest.study_phase,
            pre_enrollment_structure_unit_ids=(
                batch.pre_enrollment_structure_unit_ids
            ),
            structural_only_structure_unit_ids=(
                batch.structural_only_structure_unit_ids
            ),
            owned_visit_instance_by_structure_unit_id=(
                batch.owned_visit_instance_by_structure_unit_id
            ),
            owned_procedure_semantic_families_by_structure_unit_id=(
                batch.owned_procedure_semantic_families_by_structure_unit_id
            ),
            owned_required_action_kinds_by_structure_unit_id=(
                batch.owned_required_action_kinds_by_structure_unit_id
            ),
            owned_required_procedure_target_ids_by_structure_unit_id=(
                batch.owned_required_procedure_target_ids_by_structure_unit_id
            ),
        )
        all_owned.extend(result.owned_structure_unit_ids)
        candidates.extend(result.candidates)
    if set(result_by_id) != set(batch_by_id):
        _fail("BATCH_DISPOSITION_INCOMPLETE", "批次结果未覆盖计划中的全部批次")
    if len(all_owned) != len(set(all_owned)) or set(all_owned) != set(manifest_ids):
        _fail("BATCH_OWNERSHIP_NOT_CLOSED", "每个全文结构单元必须由且仅由一个批次拥有")
    if set(authoritative_by_unit) != set(manifest_ids):
        _fail("BATCH_DISPOSITION_INCOMPLETE", "水合批次未逐项覆盖全文结构单元")
    return authoritative_by_unit, candidates


def _source_units_for(
    source_unit_ids: Sequence[str],
    unit_by_id: dict[str, ProtocolStructureUnit],
    *,
    entity_id: str,
) -> list[ProtocolStructureUnit]:
    if not source_unit_ids:
        _fail("SOURCE_UNIT_SCOPE_EMPTY", "来源结构单元不能为空", entity_id=entity_id)
    if len(source_unit_ids) != len(set(source_unit_ids)):
        _fail("SOURCE_UNIT_SCOPE_DUPLICATE", "来源结构单元不得重复", entity_id=entity_id)
    units: list[ProtocolStructureUnit] = []
    for unit_id in source_unit_ids:
        unit = unit_by_id.get(unit_id)
        if unit is None:
            _fail("SOURCE_UNIT_SCOPE_ESCAPE", "来源结构单元不在全文清单内", entity_id=entity_id)
        units.append(unit)
    return units


def _source_scope(
    *,
    entity_id: str,
    source_unit_ids: Sequence[str],
    source_span_ids: Sequence[str],
    unit_by_id: dict[str, ProtocolStructureUnit],
    allowed_span_ids: set[str],
) -> list[ProtocolStructureUnit]:
    if not source_span_ids:
        _fail("SOURCE_SPAN_SCOPE_EMPTY", "来源片段不能为空", entity_id=entity_id)
    if len(source_span_ids) != len(set(source_span_ids)):
        _fail("SOURCE_SPAN_SCOPE_DUPLICATE", "来源片段不得重复", entity_id=entity_id)
    spans = set(source_span_ids)
    outside_allowed = sorted(spans - allowed_span_ids)
    if outside_allowed:
        _fail("SOURCE_SCOPE_ESCAPE", "来源片段越出发布允许范围：" + ",".join(outside_allowed), entity_id=entity_id)
    units = _source_units_for(source_unit_ids, unit_by_id, entity_id=entity_id)
    unit_spans = {span for unit in units for span in getattr(unit, "source_span_ids", ())}
    outside_units = sorted(spans - unit_spans)
    if outside_units:
        _fail("SOURCE_UNIT_SCOPE_ESCAPE", "来源片段不属于自身来源结构单元：" + ",".join(outside_units), entity_id=entity_id)

    # A table row is one immutable review unit, not a first-cell shortcut.  A
    # row citation must carry all member spans so that a row cannot be
    # published with partial provenance.
    for unit in units:
        kind = _value(getattr(unit, "unit_kind", None))
        if kind in {"table_header", "table_row", "table_note"}:
            missing = sorted(set(getattr(unit, "source_span_ids", ())) - spans)
            if missing:
                _fail(
                    "TABLE_ROW_SOURCE_CLOSURE_PARTIAL",
                    "表格结构单元来源必须闭合到全部成员片段：" + ",".join(missing),
                    entity_id=entity_id,
                )
    return units


def _iter_expression_atoms(expression: object | None) -> list[object]:
    if expression is None:
        return []
    atoms: list[object] = []
    for group in getattr(expression, "groups", ()) or ():
        atoms.extend(getattr(group, "atoms", ()) or ())
    return atoms


def _semantic_expression_fingerprint(expression: object) -> str:
    """Fingerprint an expression without system-generated atom identities."""

    payload = expression.model_dump(mode="json")
    for group in payload.get("groups", ()):
        for atom in group.get("atoms", ()):
            atom.pop("condition_atom_id", None)
            atom.pop("obligation_id", None)
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _check_atom_sources(
    atoms: Sequence[object],
    *,
    entity_id: str,
    source_unit_ids: Sequence[str],
    source_span_ids: set[str],
    units: Sequence[ProtocolStructureUnit],
) -> None:
    ids: list[str] = []
    for atom in atoms:
        atom_id = getattr(atom, "condition_atom_id", None) or getattr(atom, "obligation_id", None)
        if not isinstance(atom_id, str) or not atom_id.strip():
            _fail("ATOM_ID_MISSING", "水合语义原子必须有系统身份", entity_id=entity_id)
        ids.append(atom_id)
        atom_span_ids = list(getattr(atom, "source_span_ids", ()) or ())
        atom_excerpts = list(getattr(atom, "source_excerpts", ()) or ())
        if not atom_span_ids or not atom_excerpts or len(atom_span_ids) != len(atom_excerpts):
            _fail("ATOM_SOURCE_CLOSURE_INVALID", "每个语义原子必须带一一对应的来源片段和精确摘录", entity_id=entity_id)
        if not set(atom_span_ids) <= source_span_ids:
            _fail("ATOM_SOURCE_SCOPE_ESCAPE", "语义原子来源越出控制来源闭包", entity_id=entity_id)
        constraint = getattr(atom, "time_constraint", None)
        evidence = getattr(constraint, "half_life_evidence", None)
        if evidence is not None and not any(
            evidence.source_span_id == span_id
            and evidence.source_excerpt in excerpt
            and evidence.applies_to_quote in excerpt
            for span_id, excerpt in zip(atom_span_ids, atom_excerpts, strict=True)
        ):
            _fail("HALF_LIFE_SOURCE_UNVERIFIED", "半衰期时长与适用对象必须来自本项明确引用的方案原文", entity_id=entity_id)
        for span_id, excerpt in zip(atom_span_ids, atom_excerpts, strict=True):
            if not any(
                span_id in set(getattr(unit, "source_span_ids", ()))
                and isinstance(excerpt, str)
                and excerpt.strip()
                and excerpt.strip() in str(getattr(unit, "excerpt", ""))
                for unit in units
            ):
                _fail("FABRICATED_EXCERPT", "精确摘录无法在本控制来源结构单元中逐字核验", entity_id=entity_id)
    if len(ids) != len(set(ids)):
        _fail("ATOM_ID_DUPLICATE", "同一语义层原子身份不得重复", entity_id=entity_id)


def _check_dnf(
    expression: object | None,
    *,
    label: str,
    entity_id: str,
    source_unit_ids: Sequence[str],
    source_span_ids: set[str],
    units: Sequence[ProtocolStructureUnit],
) -> list[object]:
    if expression is None:
        return []
    groups = list(getattr(expression, "groups", ()) or ())
    if not groups:
        _fail("DNF_EMPTY", f"{label} DNF 不能为空", entity_id=entity_id)
    atoms: list[object] = []
    fingerprints: set[str] = set()
    for group in groups:
        group_atoms = list(getattr(group, "atoms", ()) or ())
        if not group_atoms:
            _fail("DNF_EMPTY_GROUP", f"{label} DNF 不得包含空合取组", entity_id=entity_id)
        atoms.extend(group_atoms)
        atom_payloads = [
            {
                key: value
                for key, value in getattr(atom, "model_dump", lambda **_: {})(mode="json").items()
                if key not in {"condition_atom_id", "obligation_id"}
            }
            for atom in group_atoms
        ]
        atom_fingerprints = [
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for payload in atom_payloads
        ]
        if len(atom_fingerprints) != len(set(atom_fingerprints)):
            _fail(
                "DNF_DUPLICATE_ATOM",
                f"{label} DNF 同一合取组内不得包含重复原子",
                entity_id=entity_id,
            )
        fingerprint = json.dumps(
            atom_payloads,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if fingerprint in fingerprints:
            _fail("DNF_DUPLICATE_GROUP", f"{label} DNF 不得包含重复替代组", entity_id=entity_id)
        fingerprints.add(fingerprint)
    _check_atom_sources(
        atoms,
        entity_id=entity_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_span_ids,
        units=units,
    )
    return atoms


def _conditional_action_clauses(units: Sequence[ProtocolStructureUnit]) -> list[str]:
    """Return source clauses that independently pair a condition with an action."""

    clauses: list[str] = []
    for unit in units:
        for clause in _STRONG_CLAUSE_BOUNDARY_RE.split(str(unit.excerpt)):
            normalized = re.sub(r"\s+", "", clause)
            if (
                normalized
                and _CONDITIONAL_SUBJECT_RE.search(normalized)
                and _CONDITIONAL_ACTION_RE.search(normalized)
                and not _CONDITIONAL_CUE_AS_REPORTED_CONTENT_RE.search(normalized)
            ):
                clauses.append(normalized)
    return clauses


def _normalize_clause_fragment(value: object) -> str:
    """Normalize whitespace and trailing clause punctuation before containment checks."""

    return re.sub(r"[。！？!?；;]+$", "", re.sub(r"\s+", "", str(value))).strip()


def _check_conditional_branch_mapping(
    *,
    entity_id: str,
    units: Sequence[ProtocolStructureUnit],
    trigger_expression: object | None,
    obligation_expression: object,
) -> None:
    """Map only this candidate's conditional clauses to distinct trigger branches."""

    candidate_excerpts = {
        _normalize_clause_fragment(excerpt)
        for expression in (trigger_expression, obligation_expression)
        for atom in _iter_expression_atoms(expression)
        for excerpt in getattr(atom, "source_excerpts", ()) or ()
        if str(excerpt).strip()
    }
    clauses = [
        clause
        for clause in _conditional_action_clauses(units)
        if any(
            _normalize_clause_fragment(clause) in excerpt
            or excerpt in _normalize_clause_fragment(clause)
            for excerpt in candidate_excerpts
        )
    ]
    if not clauses:
        return

    trigger_groups = list(getattr(trigger_expression, "groups", ()) or ())
    matched_branch_ids: list[str] = []
    for clause in clauses:
        matches: list[str] = []
        for group in trigger_groups:
            branch_id = str(getattr(group, "trigger_branch_id", "") or "")
            if not branch_id:
                continue
            excerpts = [
                _normalize_clause_fragment(excerpt)
                for atom in getattr(group, "atoms", ()) or ()
                for excerpt in getattr(atom, "source_excerpts", ()) or ()
            ]
            if any(excerpt and excerpt in clause for excerpt in excerpts):
                matches.append(branch_id)
        if not matches:
            _fail(
                "CONDITIONAL_BRANCH_MAPPING_INVALID",
                "候选引用的条件及后续操作必须用最小逐字摘录映射到触发分支",
                entity_id=entity_id,
            )
        matched_branch_ids.extend(matches)

    if len(matched_branch_ids) != len(set(matched_branch_ids)):
        _fail(
            "CONDITIONAL_BRANCH_MAPPING_INVALID",
            "不同条件及后续操作不得复用同一个笼统触发分支；同句替代条件可以各自成分支并共享后果",
            entity_id=entity_id,
        )

    scoped_branch_ids = {
        branch_id
        for group in getattr(obligation_expression, "groups", ()) or ()
        for branch_id in getattr(group, "applies_to_trigger_branch_ids", ()) or ()
    }
    missing = set(matched_branch_ids) - scoped_branch_ids
    if missing:
        _fail(
            "CONDITIONAL_BRANCH_CONSEQUENCE_MISSING",
            "每个条件触发分支必须显式绑定对应义务；共用后果应由一个义务组同时声明全部分支",
            entity_id=entity_id,
        )


def _check_exception_layer(
    *,
    entity_id: str,
    semantic_expressions: Sequence[object | None],
    exception_expression: object | None,
) -> None:
    """Keep exceptions referenced by this control out of free-text obligations."""

    semantic_texts = [
        text
        for expression in semantic_expressions
        for atom in _iter_expression_atoms(expression)
        for text in (
            str(getattr(atom, "statement", "")),
            *(str(item) for item in getattr(atom, "source_excerpts", ()) or ()),
        )
    ]
    if any(_EXCEPTION_CUE_RE.search(text) for text in semantic_texts) and not list(
        getattr(exception_expression, "groups", ()) or ()
    ):
        _fail(
            "EXCEPTION_LAYER_MISSING",
            "原文明确包含除非、除外或例外条件；必须在例外层逐项结构化，不得只留在义务文字中",
            entity_id=entity_id,
        )


def _check_obligation_modality_and_event_anchor(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Preserve optional actions and anchor prohibited events to the event itself."""

    for atom in _iter_expression_atoms(obligation_expression):
        excerpts = " ".join(
            str(item) for item in getattr(atom, "source_excerpts", ()) or ()
        )
        statement = str(getattr(atom, "statement", ""))
        if _OPTIONAL_ACTION_CUE_RE.search(excerpts) and not _OPTIONAL_ACTION_STATEMENT_RE.search(
            statement
        ):
            _fail(
                "OPTIONAL_ACTION_MODALITY_DROPPED",
                "原文允许或可执行的操作不得改写成无条件必做；义务陈述必须保留可选语气",
                entity_id=entity_id,
            )

        constraint = getattr(atom, "time_constraint", None)
        anchor = _value(getattr(constraint, "anchor_type", None))
        direction = _value(getattr(constraint, "direction", None))
        prohibited_event = _value(getattr(atom, "kind", None)) == "prohibit_event"
        if prohibited_event and _EXEMPTION_MODALITY_RE.search(excerpts):
            _fail(
                "EXEMPTION_MODALITY_OVERSTATED",
                "无需或不要求执行表示豁免，不得强化为禁止事件",
                entity_id=entity_id,
            )
        if prohibited_event and (
            (anchor == "randomization_date" and _RANDOMIZATION_EVENT_RE.search(excerpts))
            or (anchor == "first_dose_date" and _FIRST_DOSE_EVENT_RE.search(excerpts))
        ) and direction != "on":
            _fail(
                "PROHIBITED_EVENT_ANCHOR_MISMATCH",
                "不得随机或不得给药描述的是锚点事件本身，必须使用 on；事件前窗口应另由直接来源表达",
                entity_id=entity_id,
            )


def _check_conditional_exemption_binding(
    *,
    entity_id: str,
    units: Sequence[ProtocolStructureUnit],
    trigger_expression: object | None,
    obligation_expression: object,
) -> None:
    """Keep a source condition attached to the operation it exempts."""

    conditional_source_spans = {
        span_id
        for unit in units
        if _CONDITIONAL_EXEMPTION_SOURCE_RE.search(str(unit.excerpt))
        for span_id in unit.source_span_ids
    }
    if not conditional_source_spans:
        return
    trigger_spans = {
        span_id
        for atom in _iter_expression_atoms(trigger_expression)
        for span_id in (getattr(atom, "source_span_ids", ()) or ())
    }
    for group in getattr(obligation_expression, "groups", ()) or ():
        atoms = list(getattr(group, "atoms", ()) or ())
        timed_spans = {
            span_id
            for atom in atoms
            if getattr(atom, "time_constraint", None) is not None
            for span_id in (getattr(atom, "source_span_ids", ()) or ())
        }
        for atom in atoms:
            atom_text = " ".join(
                (
                    str(getattr(atom, "statement", "")),
                    *(str(item) for item in getattr(atom, "source_excerpts", ()) or ()),
                )
            )
            atom_spans = set(getattr(atom, "source_span_ids", ()) or ())
            conditional_spans = atom_spans & conditional_source_spans
            if (
                conditional_spans
                and _EXEMPTION_MODALITY_RE.search(atom_text)
                and not conditional_spans & (trigger_spans | timed_spans)
            ):
                _fail(
                    "CONDITIONAL_EXEMPTION_BINDING_MISSING",
                    "原文中的免予操作受同源条件限制；结果有效期核对与免予后果必须在同一义务组并列表达",
                    entity_id=entity_id,
                    obligation_source_span_ids=sorted(conditional_spans),
                )


def _check_exemption_evidence_modality(
    *,
    entity_id: str,
    units: Sequence[ProtocolStructureUnit],
    obligation_expression: object,
    evidence: Sequence[object],
) -> None:
    """An optional waiver needs proof of eligibility, not proof of non-action."""

    # Scope this protection to source text that actually grants a conditional
    # waiver. Otherwise an ordinary note that an action was not repeated could
    # be valid evidence for a different control.
    if not any(
        _CONDITIONAL_EXEMPTION_SOURCE_RE.search(str(unit.excerpt))
        for unit in units
    ):
        return
    if any(
        _EXEMPTION_NONOCCURRENCE_EVIDENCE_RE.search(
            str(getattr(item, "description", ""))
        )
        for item in evidence
    ):
        _fail(
            "EXEMPTION_EVIDENCE_OVERSTATED",
            "免予操作只需证明适用条件成立；不得要求证明被免予的操作未发生",
            entity_id=entity_id,
        )


def _routine_requirement_text(value: str) -> str:
    """Return mandatory-action clauses after removing exemption-only clauses."""

    return " ".join(
        clause
        for clause in re.split(r"[，,。；;]+", value)
        if clause.strip() and not _EXEMPTION_MODALITY_RE.search(clause)
    )


def _entity_control_semantics(entity: object) -> object:
    return getattr(entity, "semantics", None) or entity


def _entity_source_unit_ids(entity: object) -> set[str]:
    return set(
        getattr(entity, "frozen_structure_unit_ids", ())
        or getattr(entity, "source_structure_unit_ids", ())
        or ()
    )


def _entity_identifier(entity: object) -> str:
    return str(
        getattr(entity, "control_candidate_id", None)
        or getattr(entity, "protocol_control_id", None)
        or ""
    )


def _check_conditional_exemption_scope_split(
    entities: Sequence[object],
    *,
    unit_by_id: dict[str, ProtocolStructureUnit],
    candidate_scope: bool,
) -> None:
    """Do not split one source waiver into a sibling's unconditional action."""

    for unit_id, unit in unit_by_id.items():
        if not _CONDITIONAL_EXEMPTION_SOURCE_RE.search(str(unit.excerpt)):
            continue
        source_spans = set(unit.source_span_ids)
        scoped: list[tuple[object, object, list[object]]] = []
        for entity in entities:
            if unit_id not in _entity_source_unit_ids(entity):
                continue
            semantics = _entity_control_semantics(entity)
            atoms = [
                atom
                for atom in _iter_expression_atoms(
                    getattr(semantics, "obligation_expression", None)
                )
                if set(getattr(atom, "source_span_ids", ()) or ()) & source_spans
            ]
            if atoms:
                scoped.append((entity, semantics, atoms))
        if len(scoped) < 2:
            continue
        has_bound_waiver = False
        for _, semantics, _ in scoped:
            for group in getattr(
                getattr(semantics, "obligation_expression", None), "groups", ()
            ) or ():
                group_atoms = [
                    atom
                    for atom in getattr(group, "atoms", ()) or ()
                    if set(getattr(atom, "source_span_ids", ()) or ()) & source_spans
                ]
                has_exemption = any(
                    _EXEMPTION_MODALITY_RE.search(
                        " ".join(
                            (
                                str(getattr(atom, "statement", "")),
                                *(
                                    str(item)
                                    for item in getattr(atom, "source_excerpts", ()) or ()
                                ),
                            )
                        )
                    )
                    for atom in group_atoms
                )
                has_condition = any(
                    getattr(atom, "time_constraint", None) is not None
                    for atom in group_atoms
                )
                if has_exemption and has_condition:
                    has_bound_waiver = True
                    break
            if has_bound_waiver:
                break
        if not has_bound_waiver:
            continue
        offending = []
        for entity, _, atoms in scoped:
            for atom in atoms:
                atom_text = " ".join(
                    (
                        str(getattr(atom, "statement", "")),
                        *(str(item) for item in getattr(atom, "source_excerpts", ()) or ()),
                    )
                )
                if (
                    getattr(atom, "time_constraint", None) is None
                    and _ROUTINE_ACTION_RE.search(_routine_requirement_text(atom_text))
                ):
                    offending.append(entity)
                    break
        if not offending:
            continue
        scoped_ids = sorted(
            identifier
            for entity, _, _ in scoped
            if (identifier := _entity_identifier(entity))
        )
        _fail(
            "CONDITIONAL_EXEMPTION_SCOPE_SPLIT",
            "同源条件豁免不得拆成兄弟候选中的无条件执行义务；被豁免操作必须与有效期及豁免条件保持同一语义范围",
            entity_id=_entity_identifier(offending[0]) or unit_id,
            structure_unit_ids=[unit_id],
            candidate_ids=scoped_ids if candidate_scope else (),
            obligation_source_span_ids=sorted(source_spans),
        )


def _recording_requirements(value: str) -> set[str]:
    requirements = {
        key for key, pattern in _RECORD_UNIT_PATTERNS.items() if pattern.search(value)
    }
    if _INTEGER_PRECISION_RE.search(value):
        requirements.add("precision:integer")
    for pattern in _DECIMAL_PRECISION_RES:
        requirements.update(
            f"precision:decimal:{match.group('places')}"
            for match in pattern.finditer(value)
        )
    return requirements


def _check_recording_precision_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Keep source-defined recording units and precision in every DNF path."""

    for group in getattr(obligation_expression, "groups", ()) or ():
        required_by_span: dict[str, set[str]] = {}
        recorded_by_span: dict[str, set[str]] = {}
        for atom in getattr(group, "atoms", ()) or ():
            span_ids = list(getattr(atom, "source_span_ids", ()) or ())
            excerpts = list(getattr(atom, "source_excerpts", ()) or ())
            for span_id, excerpt in zip(span_ids, excerpts, strict=True):
                requirements = _recording_requirements(str(excerpt))
                if any(item.startswith("precision:") for item in requirements):
                    required_by_span.setdefault(span_id, set()).update(requirements)
                if _value(getattr(atom, "kind", None)) == ControlObligationKind.MUST_RECORD.value:
                    recorded_by_span.setdefault(span_id, set()).update(
                        _recording_requirements(str(getattr(atom, "statement", "")))
                    )

        for span_id, requirements in required_by_span.items():
            missing = requirements - recorded_by_span.get(span_id, set())
            if missing:
                _fail(
                    "RECORD_PRECISION_COMPRESSED",
                    "原文明确规定记录单位或精度时，记录义务必须完整保留，不得只写成完成测量或笼统记录："
                    + "、".join(sorted(missing)),
                    entity_id=entity_id,
                    obligation_source_span_ids=[span_id],
                )


def _check_collection_obligation_semantics(
    *,
    entity_id: str,
    obligation_expression: object,
    bindings: Sequence[object],
) -> None:
    """Keep collection effort, temporal authority and visit closure distinct."""

    _check_obligation_modality_fidelity(
        entity_id=entity_id,
        obligation_expression=obligation_expression,
    )
    collection_atoms: list[object] = []
    for atom in _iter_expression_atoms(obligation_expression):
        if _value(getattr(atom, "kind", None)) != ControlObligationKind.MUST_RECORD.value:
            continue
        source_text = " ".join(
            str(item) for item in getattr(atom, "source_excerpts", ()) or ()
        )
        if not source_text:
            source_text = str(getattr(atom, "statement", ""))
        if not _COLLECTION_ACTION_CUE_RE.search(source_text):
            continue
        collection_atoms.append(atom)
        temporal_scope = _value(getattr(atom, "temporal_scope", None))
        has_calendar_duration = bool(_CALENDAR_DURATION_RE.search(source_text))

        required_scopes: set[str] = set()
        if has_calendar_duration:
            required_scopes.add(ControlTemporalScopeKind.CALENDAR_LOOKBACK.value)
        if _FULL_HISTORY_SCOPE_CUE_RE.search(source_text):
            required_scopes.add(ControlTemporalScopeKind.FULL_HISTORY.value)
        if _OFFICIAL_RULE_SCOPE_CUE_RE.search(source_text):
            required_scopes.add(ControlTemporalScopeKind.OFFICIAL_RULE_DEFINED.value)
        if _SINCE_PREVIOUS_VISIT_CUE_RE.search(source_text):
            required_scopes.add(ControlTemporalScopeKind.SINCE_PREVIOUS_VISIT.value)
        if len(required_scopes) > 1:
            _fail(
                "COLLECTION_TEMPORAL_SCOPES_MIXED",
                "日历回顾、完整历程、正式条款自有窗口和访视间更新必须拆成不同收集义务",
                entity_id=entity_id,
            )
        if required_scopes and temporal_scope not in required_scopes:
            _fail(
                "COLLECTION_TEMPORAL_SCOPE_MISSING",
                "资料收集义务必须显式保存其时间作用域，不能只留在自由文本中",
                entity_id=entity_id,
            )

    if not collection_atoms:
        return

    excerpts = " ".join(
        str(item)
        for atom in collection_atoms
        for item in getattr(atom, "source_excerpts", ()) or ()
    )
    decision_stages = {
        _value(getattr(binding, "review_stage", None))
        for binding in bindings
        if _value(getattr(binding, "role", None)) == ReviewNodeRole.DECIDE_AT_NODE.value
    }
    if re.search(r"筛选和/或基线|筛选(?:期|访视)?.{0,12}(?:和|及|/或|或).{0,12}基线", excerpts):
        if not {ReviewStage.SCREENING.value, ReviewStage.BASELINE.value}.issubset(
            decision_stages
        ):
            _fail(
                "COLLECTION_VISIT_CLOSURE_MISSING",
                "原文同时指定筛选与基线收集时，两个审核节点都必须保留本节点判定，不能压缩为单一晚期节点",
                entity_id=entity_id,
            )
    if _SINCE_PREVIOUS_VISIT_CUE_RE.search(excerpts) and not (
        decision_stages - {ReviewStage.SCREENING.value, None}
    ):
        _fail(
            "COLLECTION_INTERVAL_REVIEW_NODE_MISSING",
            "访视间增量问询必须绑定后续审核节点，不能只保留筛选节点",
            entity_id=entity_id,
        )


def _has_recommended_cue(source_text: str) -> bool:
    """Return true only for affirmative recommendation language."""

    for match in _RECOMMENDED_CUE_RE.finditer(source_text):
        prefix = source_text[max(0, match.start() - 24) : match.start()]
        if not _RECOMMENDED_NEGATION_SUFFIX_RE.search(prefix):
            return True
    return False


def _modality_source_for_atom(atom: object) -> str:
    excerpts = [
        str(item) for item in getattr(atom, "source_excerpts", ()) or ()
        if isinstance(item, str)
    ]
    statement = str(getattr(atom, "statement", "") or "")
    if not excerpts:
        return statement

    def compact(value: str) -> str:
        return re.sub(r"[\s：:、，,。；;]+", "", value)

    statement_key = compact(statement)
    matched: list[str] = []
    for excerpt in excerpts:
        for clause in re.split(r"[。；;\n，,]", excerpt):
            clause_key = compact(clause)
            if (
                len(statement_key) >= 4 and len(clause_key) >= 4
                and (clause_key in statement_key or statement_key in clause_key)
            ) or _split_prohibition_atom_covers_clause(
                _normalize_prohibition_quote(clause), atom
            ):
                matched.append(clause)
    return " ".join(matched) if matched else " ".join(excerpts)


def _check_obligation_modality_fidelity(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Ensure recommended / best-effort cues are preserved without source downgrade."""

    for atom in _iter_expression_atoms(obligation_expression):
        source_text = _modality_source_for_atom(atom)
        modality = _value(getattr(atom, "modality", None)) or ControlObligationModality.MANDATORY.value
        has_recommended = _has_recommended_cue(source_text)
        has_best_effort = bool(_BEST_EFFORT_CUE_RE.search(source_text))
        # Recommended cue requires recommended modality, and vice versa
        if has_recommended:
            if modality != ControlObligationModality.RECOMMENDED.value:
                _fail(
                    "RECOMMENDED_MODALITY_DROPPED",
                    "原文为建议完成时必须保留建议完成强度，不得强化为必须完成",
                    entity_id=entity_id,
                )
        elif modality == ControlObligationModality.RECOMMENDED.value:
            _fail(
                "RECOMMENDED_MODALITY_UNSUPPORTED",
                "建议完成强度必须由该义务的直接来源明确支持",
                entity_id=entity_id,
            )
        # Best-effort cue (including 尽量) requires best-effort modality
        if has_best_effort:
            if modality != ControlObligationModality.BEST_EFFORT.value:
                _fail(
                    "BEST_EFFORT_MODALITY_DROPPED",
                    "原文为尽力完成时必须保留尽力完成强度，不得强化为必须完成",
                    entity_id=entity_id,
                )
        elif modality == ControlObligationModality.BEST_EFFORT.value:
            _fail(
                "BEST_EFFORT_MODALITY_UNSUPPORTED",
                "尽力完成强度必须由该义务的直接来源明确支持",
                entity_id=entity_id,
            )



def _check_routine_action_not_trigger(
    *,
    entity_id: str,
    trigger_expression: object | None,
    obligation_expression: object,
) -> None:
    """Keep unconditional procedures and records in obligations, not triggers."""

    obligation_excerpts = {
        re.sub(r"\s+", "", str(excerpt))
        for group in getattr(obligation_expression, "groups", ()) or ()
        for atom in getattr(group, "atoms", ()) or ()
        for excerpt in getattr(atom, "source_excerpts", ()) or ()
    }
    for atom in _iter_expression_atoms(trigger_expression):
        excerpts = [
            re.sub(r"\s+", "", str(excerpt))
            for excerpt in getattr(atom, "source_excerpts", ()) or ()
        ]
        for excerpt in excerpts:
            if (
                excerpt in obligation_excerpts
                and _ROUTINE_ACTION_RE.search(excerpt)
                and not _CONDITIONAL_SUBJECT_RE.search(excerpt)
            ):
                _fail(
                    "ROUTINE_OBLIGATION_MISLABELED_AS_TRIGGER",
                    "无条件必做的检查、操作或记录属于义务，不得同时伪装成触发条件",
                    entity_id=entity_id,
                )


def _check_mixed_decision_stage_control(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Split current-stage procedures from future-anchor validity decisions."""

    atoms = list(_iter_expression_atoms(obligation_expression))
    future_anchors = {
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
    }
    has_future_anchor = any(
        _value(getattr(getattr(atom, "time_constraint", None), "anchor_type", None))
        in future_anchors
        for atom in atoms
    )
    has_unanchored_routine_action = any(
        getattr(atom, "time_constraint", None) is None
        and _ROUTINE_ACTION_RE.search(_routine_requirement_text(atom_text))
        for atom in atoms
        for atom_text in [
            " ".join(
                (
                    str(getattr(atom, "statement", "")),
                    *(str(item) for item in getattr(atom, "source_excerpts", ()) or ()),
                )
            )
        ]
    )
    if has_future_anchor and has_unanchored_routine_action:
        _fail(
            "MIXED_DECISION_STAGE_CONTROL",
            "筛选期应完成的无锚点操作与基线/随机/首次给药前有效性判定必须拆成不同候选",
            entity_id=entity_id,
        )


def _check_mixed_trigger_decision_stages(
    *,
    entity_id: str,
    trigger_expression: object | None,
) -> None:
    """Do not collapse screening and later decisive triggers into one control."""

    for atom in _iter_expression_atoms(trigger_expression):
        atom_text = " ".join(
            [str(getattr(atom, "statement", ""))]
            + [str(item) for item in getattr(atom, "source_excerpts", ()) or ()]
        )
        named_stages = {
            stage
            for stage, pattern in _TRIGGER_DECISION_STAGE_CUES.items()
            if pattern.search(atom_text)
        }
        if "screening" in named_stages and named_stages - {"screening"}:
            _fail(
                "MIXED_TRIGGER_DECISION_STAGES",
                "单个触发事实不得同时承载筛选与基线/随机/首次给药等不同最终判定时点，必须按时点拆分",
                entity_id=entity_id,
            )

    anchors = {
        _value(getattr(getattr(atom, "time_constraint", None), "anchor_type", None))
        for atom in _iter_expression_atoms(trigger_expression)
    }
    if "screening_date" in anchors and anchors & {
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
    }:
        _fail(
            "MIXED_TRIGGER_DECISION_STAGES",
            "筛选时触发的结论与基线/随机/首次给药前触发的结论必须拆成不同候选，不能把筛选结论降为提前关注",
            entity_id=entity_id,
        )


def _texts_for_control(control: ProtocolReviewControl) -> list[str]:
    texts = [
        str(getattr(control, "title", "")),
        str(getattr(control, "applicable_population", "")),
        str(getattr(control, "trigger_condition", "") or ""),
    ]
    for expression in (
        getattr(control, "applicability_expression", None),
        getattr(control, "trigger_expression", None),
        getattr(control, "obligation_expression", None),
        getattr(control, "exception_expression", None),
    ):
        for atom in _iter_expression_atoms(expression):
            texts.append(str(getattr(atom, "statement", "")))
            texts.extend(str(item) for item in getattr(atom, "source_excerpts", ()) or ())
    for atom in getattr(control, "obligations", ()) or ():
        texts.append(str(getattr(atom, "statement", "")))
        texts.extend(str(item) for item in getattr(atom, "source_excerpts", ()) or ())
    return texts


def _check_time_constraints(
    *,
    entity_id: str,
    texts: Sequence[str],
    expressions: Sequence[object | None],
    flat_atoms: Sequence[object],
    global_time_constraint: object | None,
) -> None:
    atoms: list[object] = list(flat_atoms)
    for expression in expressions:
        atoms.extend(_iter_expression_atoms(expression))
    constraints = [global_time_constraint]
    if getattr(global_time_constraint, "half_life_evidence", None) is not None:
        _fail("HALF_LIFE_SCOPE_UNRESOLVED", "半衰期时长须绑定具体用药条件，不能作为整个控制的通用数值", entity_id=entity_id)
    constraints.extend(getattr(atom, "time_constraint", None) for atom in atoms)
    constraints = [item for item in constraints if item is not None]
    obligation_atoms = [atom for atom in atoms if getattr(atom, "kind", None) is not None]
    periods = [
        getattr(atom, "prospective_period", None)
        for atom in obligation_atoms
        if getattr(atom, "prospective_period", None) is not None
    ]
    for constraint in constraints:
        anchor = _value(getattr(constraint, "anchor_type", None))
        direction = _value(getattr(constraint, "direction", None))
        if not anchor or not direction:
            _fail("TIME_ANCHOR_UNRESOLVED", "时间约束必须有命名锚点和方向", entity_id=entity_id)
        if direction == "on" and any(
            getattr(constraint, field, None) is not None
            for field in (
                "lower_bound_days",
                "upper_bound_days",
                "lower_bound",
                "upper_bound",
                "half_life_multiplier",
                "combined_window_selection",
            )
        ):
            _fail("TIME_CONSTRAINT_INVALID", "on 锚点不得携带窗口或半衰期参数", entity_id=entity_id)
        has_calendar_bound = any(
            getattr(constraint, field, None) is not None
            for field in (
                "lower_bound_days",
                "upper_bound_days",
                "lower_bound",
                "upper_bound",
            )
        )
        has_half_life = getattr(constraint, "half_life_multiplier", None) is not None
        selection = _value(getattr(constraint, "combined_window_selection", None))
        if has_calendar_bound and has_half_life:
            if selection != "longer_of_calendar_and_half_life":
                _fail(
                    "TIME_COMBINED_SELECTION_MISSING",
                    "固定窗口与半衰期并存时必须显式声明 longer_of 择长语义",
                    entity_id=entity_id,
                )
        elif selection is not None:
            _fail(
                "TIME_COMBINED_SELECTION_INVALID",
                "combined_window_selection 仅用于固定窗口与半衰期并存",
                entity_id=entity_id,
            )

    has_temporal_text = any(_TEMPORAL_CUE_RE.search(text) for text in texts)
    has_temporal_atom = any(
        _TEMPORAL_CUE_RE.search(
            " ".join(
                [str(getattr(atom, "statement", ""))]
                + [str(item) for item in getattr(atom, "source_excerpts", ()) or ()]
            )
        )
        for atom in atoms
    )
    if has_temporal_text and not has_temporal_atom and not constraints and not periods:
        _fail("TIME_ANCHOR_MISSING", "时间性控制缺少可求值的命名时间锚点", entity_id=entity_id)

    for atom in atoms:
        source_texts = list(getattr(atom, "source_excerpts", ()) or ())
        if not source_texts:
            source_texts = [str(getattr(atom, "statement", ""))]
        source_text = "\n".join(str(item) for item in source_texts)
        constraint = getattr(atom, "time_constraint", None)
        if constraint is None:
            continue
        evidence = getattr(constraint, "half_life_evidence", None)
        calendar_text = source_text
        if evidence is not None:
            calendar_text = source_text.replace(
                evidence.source_excerpt,
                evidence.mask_duration(),
            )
        calendar_durations = {
            (
                int(match.group("value")),
                _TIME_UNIT_CANONICAL[match.group("unit").lower()],
            )
            for match in _CALENDAR_DURATION_RE.finditer(calendar_text)
        }
        structured_durations: set[tuple[int, str]] = set()
        for field in ("lower_bound", "upper_bound"):
            quantity = getattr(constraint, field, None)
            if quantity is not None:
                structured_durations.add(
                    (int(getattr(quantity, "value")), _value(getattr(quantity, "unit")))
                )
        for field in ("lower_bound_days", "upper_bound_days"):
            value = getattr(constraint, field, None)
            if value is not None:
                structured_durations.add((int(value), "day"))
        if calendar_durations and not structured_durations:
            _fail(
                "TIME_CALENDAR_BOUND_MISSING",
                "义务原文含明确日历时长，但结构化时间窗未保存该数值和单位",
                entity_id=entity_id,
            )
        if structured_durations and structured_durations.isdisjoint(calendar_durations):
            _fail(
                "TIME_CALENDAR_BOUND_UNSUPPORTED",
                "结构化时间窗的数值和单位必须由该义务的直接来源原文支持",
                entity_id=entity_id,
                obligation_source_span_ids=getattr(atom, "source_span_ids", ()) or (),
            )
        expected_bounds: set[tuple[str, int, str, bool]] = set()
        for match in _TIME_BOUND_PREFIX_RE.finditer(calendar_text):
            operator = match.group("operator")
            bound_kind, inclusive = {
                "≤": ("upper", True),
                "<=": ("upper", True),
                "不超过": ("upper", True),
                "至多": ("upper", True),
                "<": ("upper", False),
                "＜": ("upper", False),
                "少于": ("upper", False),
                "不足": ("upper", False),
                "≥": ("lower", True),
                ">=": ("lower", True),
                "不少于": ("lower", True),
                "至少": ("lower", True),
                ">": ("lower", False),
                "＞": ("lower", False),
                "超过": ("lower", False),
                "大于": ("lower", False),
            }[operator.lower()]
            expected_bounds.add(
                (
                    bound_kind,
                    int(match.group("value")),
                    _TIME_UNIT_CANONICAL[match.group("unit").lower()],
                    inclusive,
                )
            )
        for match in _TIME_BOUND_SUFFIX_RE.finditer(calendar_text):
            expected_bounds.add(
                (
                    "upper",
                    int(match.group("value")),
                    _TIME_UNIT_CANONICAL[match.group("unit").lower()],
                    True,
                )
            )
        structured_bounds: set[tuple[str, int, str, bool]] = set()
        for kind in ("lower", "upper"):
            inclusive = bool(getattr(constraint, f"{kind}_bound_inclusive", True))
            days = getattr(constraint, f"{kind}_bound_days", None)
            if days is not None:
                structured_bounds.add((kind, int(days), "day", inclusive))
            quantity = getattr(constraint, f"{kind}_bound", None)
            if quantity is not None:
                structured_bounds.add(
                    (
                        kind,
                        int(getattr(quantity, "value")),
                        _value(getattr(quantity, "unit")),
                        inclusive,
                    )
                )
        if expected_bounds and not expected_bounds.issubset(structured_bounds):
            _fail(
                "TIME_BOUND_COMPARATOR_MISMATCH",
                "结构化时间窗必须逐字保留原文的大于、小于及是否包含边界",
                entity_id=entity_id,
            )
        half_life_multiplier = getattr(constraint, "half_life_multiplier", None)
        if half_life_multiplier is not None:
            source_half_lives = {
                float(match.group("value") or match.group("english_value"))
                for match in _HALF_LIFE_DURATION_RE.finditer(source_text)
            }
            if float(half_life_multiplier) not in source_half_lives:
                _fail(
                    "TIME_HALF_LIFE_UNSUPPORTED",
                    "结构化半衰期倍数必须由该原子的直接来源原文支持",
                    entity_id=entity_id,
                )

    def point_visit_action(source_text: str) -> bool:
        return bool(
            re.fullmatch(
                r"\s*(?:在|于)?[^。；;\n]{0,120}访视[^。；;\n]{0,80}"
                r"(?:完成|进行|实施|接受|安排)[^。；;\n]*。?\s*",
                source_text,
            )
            and not re.search(
                r"(?:前|后|以内|至少|不超过|持续|洗脱|半衰期|"
                r"至[^。；;\n]{0,20}结束|\d+\s*(?:天|日|周|月|年)\s*(?:内|前|后)?)",
                source_text,
            )
            and not _PROHIBITION_WORD_RE.search(source_text)
        )

    def action_scoped_period(source_text: str, pattern: re.Pattern[str]) -> bool:
        if point_visit_action(source_text):
            return False
        return any(
            not _PERIOD_CUE_AS_REPORTED_CONTENT_RE.search(
                source_text[: match.start()].rstrip()
            )
            for match in pattern.finditer(source_text)
        )

    def action_scoped_temporal_cue(source_text: str) -> bool:
        if re.fullmatch(r"\s*(?:进行|完成|实施|接受|安排)?随机(?:化|分组)?[。；;]?\s*", source_text):
            return False
        if point_visit_action(source_text):
            return False
        recall_spans = [
            (match.start(), match.end())
            for match in _MEASUREMENT_RECALL_PERIOD_RE.finditer(source_text)
        ]
        for match in _TEMPORAL_CUE_RE.finditer(source_text):
            if any(start <= match.start() < end for start, end in recall_spans):
                continue
            cue = match.group(0)
            is_period_cue = bool(
                _STUDY_PERIOD_CUE_RE.fullmatch(cue)
                or _TREATMENT_PERIOD_CUE_RE.fullmatch(cue)
            )
            if is_period_cue and _PERIOD_CUE_AS_REPORTED_CONTENT_RE.search(
                source_text[: match.start()].rstrip()
            ):
                continue
            return True
        return False

    for atom in obligation_atoms:
        source_text = _modality_source_for_atom(atom)
        continuation = getattr(atom, "continuing_obligation", None)
        period_holder = continuation if continuation is not None else atom
        period = _value(getattr(getattr(period_holder, "prospective_period", None), "period", None))
        expected_period = None
        if action_scoped_period(source_text, _STUDY_PERIOD_CUE_RE):
            expected_period = "study_period"
        elif action_scoped_period(source_text, _TREATMENT_PERIOD_CUE_RE):
            expected_period = "treatment_period"
        evaluation = getattr(atom, "evaluation", None)
        if (
            expected_period is not None
            and continuation is None
            and _value(getattr(evaluation, "determination_mode", None)) == "deterministic"
        ):
            _fail(
                "PROSPECTIVE_PERIOD_HOLDER_INVALID",
                "当前节点的确定性核对不能承担未来持续期间；须分别保留当前事实与未到期义务的原文",
                entity_id=entity_id,
            )
        if expected_period is not None and period != expected_period:
            _fail(
                "PROSPECTIVE_PERIOD_MISSING",
                "义务原文的持续期间必须结构化保存，不能只留在标题、说明或摘录中",
                entity_id=entity_id,
            )
        supported_periods = {expected_period} if expected_period is not None else set()
        if _ICF_BOUNDED_STUDY_PERIOD_RE.search(source_text):
            supported_periods.add("study_period")
        if period is not None and period not in supported_periods:
            _fail(
                "PROSPECTIVE_PERIOD_UNSUPPORTED",
                "义务持续期间必须由该原子的直接来源原文支持",
                entity_id=entity_id,
            )

    if any(_LONGER_OF_CUE_RE.search(text) for text in texts):
        has_labeled_longer_of = any(
            _value(getattr(constraint, "combined_window_selection", None))
            == "longer_of_calendar_and_half_life"
            for constraint in constraints
        )
        if not has_labeled_longer_of:
            _fail(
                "TIME_COMBINED_SELECTION_MISSING",
                "原文要求较长者时必须显式保留 combined_window_selection",
                entity_id=entity_id,
            )

    global_anchor = _value(getattr(global_time_constraint, "anchor_type", None))
    for expression in expressions:
        groups = list(getattr(expression, "groups", ()) or ())
        if groups:
            atom_groups = [
                (group, atom)
                for group in groups
                for atom in getattr(group, "atoms", ()) or ()
            ]
        else:
            atom_groups = [(None, atom) for atom in _iter_expression_atoms(expression)]
        for group, atom in atom_groups:
            # Exception condition atoms express predicates only; substitute
            # windows must live on activated obligation groups.
            group_fields = getattr(type(group), "model_fields", {}) if group is not None else {}
            if "activates_obligation_group_ids" in group_fields:
                continue
            source_excerpts = [
                str(item) for item in getattr(atom, "source_excerpts", ()) or ()
            ]
            atom_text = " ".join(
                source_excerpts or [str(getattr(atom, "statement", ""))]
            )
            if not action_scoped_temporal_cue(atom_text):
                continue
            constraint = getattr(atom, "time_constraint", None) or global_time_constraint
            if constraint is None:
                atom_id = next(
                    (
                        str(value)
                        for field in (
                            "condition_atom_id",
                            "obligation_id",
                            "exception_atom_id",
                            "predicate_id",
                        )
                        if (value := getattr(atom, field, None))
                    ),
                    "temporal-atom",
                )
                statement = str(getattr(atom, "statement", "")).strip()
                _fail(
                    "TIME_ANCHOR_MISSING",
                    "时间性原子缺少命名时间锚点"
                    + (f"；原句：{statement}" if statement else ""),
                    entity_id=f"{entity_id}/{atom_id}",
                )
            anchor = _value(getattr(constraint, "anchor_type", None))
            if not anchor:
                _fail("TIME_ANCHOR_UNRESOLVED", "时间性原子的锚点未命名", entity_id=entity_id)
            if anchor == "screening_date" and re.search(
                r"(?:首次给药|给药前|随机(?:化|分组)?|randomization|first\s+dose)",
                atom_text,
                re.IGNORECASE,
            ):
                _fail(
                    "TIME_ANCHOR_GUESSED_FROM_SCREENING",
                    "首次给药/随机锚点不得猜测为筛选日",
                    entity_id=entity_id,
                )
    if global_anchor == "screening_date" and any(
        re.search(r"(?:首次给药|给药前|随机(?:化|分组)?|randomization|first\s+dose)", text, re.IGNORECASE)
        for text in texts
    ):
        _fail(
            "TIME_ANCHOR_GUESSED_FROM_SCREENING",
            "首次给药/随机锚点不得由全局时间约束猜测为筛选日",
            entity_id=entity_id,
        )


def _group_text(group: object) -> str:
    texts: list[str] = []
    for atom in getattr(group, "atoms", ()) or ():
        texts.append(str(getattr(atom, "statement", "")))
        texts.extend(str(item) for item in getattr(atom, "source_excerpts", ()) or ())
    return " ".join(texts)


def _constraint_has_calendar_bound(constraint: object | None) -> bool:
    if constraint is None:
        return False
    return any(
        getattr(constraint, field, None) is not None
        for field in (
            "lower_bound_days",
            "upper_bound_days",
            "lower_bound",
            "upper_bound",
        )
    )


def _check_branch_scope_and_paired_consequences(
    *,
    entity_id: str,
    trigger_expression: object | None,
    obligation_expression: object | None,
    exception_expression: object | None,
) -> None:
    """Keep conditional overrides paired to named trigger/obligation scopes.

    Conditional shortening must bind ``exception condition → activated
    obligation group`` with the substitute window on the obligation, never on
    the condition atom.  Activated obligation groups are replacements, not
    unconditional OR siblings of the default window.
    """

    trigger_groups = list(getattr(trigger_expression, "groups", ()) or ())
    trigger_branch_ids = [
        getattr(group, "trigger_branch_id", None) for group in trigger_groups
    ]
    if trigger_groups:
        if any(branch_id is None or not str(branch_id).strip() for branch_id in trigger_branch_ids):
            _fail(
                "TRIGGER_BRANCH_ID_MISSING",
                "触发 DNF 每个替代分支必须有系统派生身份",
                entity_id=entity_id,
            )
        if len(trigger_branch_ids) != len(set(trigger_branch_ids)):
            _fail(
                "TRIGGER_BRANCH_ID_DUPLICATE",
                "触发 DNF 分支身份不得重复",
                entity_id=entity_id,
            )
    known_trigger_ids = {branch_id for branch_id in trigger_branch_ids if branch_id}

    obligation_groups = list(getattr(obligation_expression, "groups", ()) or ())
    obligation_by_id: dict[str, object] = {}
    for group in obligation_groups:
        scoped_ids = list(getattr(group, "applies_to_trigger_branch_ids", ()) or ())
        if scoped_ids and list(scoped_ids) != sorted(set(scoped_ids)):
            _fail(
                "OBLIGATION_SCOPE_ORDER_INVALID",
                "义务触发分支作用域必须按字典序唯一排列",
                entity_id=entity_id,
            )
        if scoped_ids and not known_trigger_ids:
            _fail(
                "OBLIGATION_SCOPE_WITHOUT_TRIGGER",
                "无触发 DNF 时义务不得声明触发分支作用域",
                entity_id=entity_id,
            )
        unknown = set(scoped_ids) - known_trigger_ids
        if unknown:
            _fail(
                "OBLIGATION_SCOPE_UNKNOWN_TRIGGER",
                "义务作用域引用了未知触发 DNF 分支",
                entity_id=entity_id,
            )
        activated_by = list(getattr(group, "activated_by_exception_group_ids", ()) or ())
        if activated_by and list(activated_by) != sorted(set(activated_by)):
            _fail(
                "OBLIGATION_ACTIVATION_ORDER_INVALID",
                "义务条件激活例外组必须按字典序唯一排列",
                entity_id=entity_id,
            )
        group_id = getattr(group, "obligation_group_id", None)
        if group_id:
            if group_id in obligation_by_id:
                _fail(
                    "OBLIGATION_GROUP_ID_DUPLICATE",
                    "义务组身份不得重复",
                    entity_id=entity_id,
                )
            obligation_by_id[str(group_id)] = group

    activated_obligation_ids: set[str] = set()
    if exception_expression is not None:
        if not trigger_groups:
            _fail(
                "EXCEPTION_TRIGGER_MISSING",
                "存在例外 DNF 时必须同时存在可被作用的触发 DNF",
                entity_id=entity_id,
            )
        for group in getattr(exception_expression, "groups", ()) or ():
            scoped_ids = list(getattr(group, "waives_trigger_branch_ids", ()) or ())
            if not scoped_ids:
                _fail(
                    "EXCEPTION_SCOPE_MISSING",
                    "每个例外 DNF 路径必须明确声明可作用的触发分支",
                    entity_id=entity_id,
                )
            if list(scoped_ids) != sorted(set(scoped_ids)):
                _fail(
                    "EXCEPTION_SCOPE_ORDER_INVALID",
                    "例外触发分支作用域必须按字典序唯一排列",
                    entity_id=entity_id,
                )
            unknown = set(scoped_ids) - known_trigger_ids
            if unknown:
                _fail(
                    "EXCEPTION_SCOPE_UNKNOWN_TRIGGER",
                    "例外作用域引用了未知触发 DNF 分支",
                    entity_id=entity_id,
                )
            group_text = _group_text(group)
            if (
                len(known_trigger_ids) > 1
                and set(scoped_ids) == known_trigger_ids
                and not any(
                    cue.lower() in group_text.lower() for cue in _EXCEPTION_BROAD_SCOPE_CUES
                )
            ):
                _fail(
                    "EXCEPTION_SCOPE_ALL_UNSUPPORTED",
                    "例外作用于全部触发分支时必须有来源明确支持",
                    entity_id=entity_id,
                )

            activates = list(getattr(group, "activates_obligation_group_ids", ()) or ())
            if activates and list(activates) != sorted(set(activates)):
                _fail(
                    "EXCEPTION_ACTIVATION_ORDER_INVALID",
                    "例外激活义务组必须按字典序唯一排列",
                    entity_id=entity_id,
                )
            exception_group_id = getattr(group, "exception_group_id", None)
            has_condition_time = any(
                _constraint_has_calendar_bound(getattr(atom, "time_constraint", None))
                or getattr(atom, "time_constraint", None) is not None
                for atom in getattr(group, "atoms", ()) or ()
            )
            is_shorten = bool(_CONDITIONAL_SHORTEN_CUE_RE.search(group_text))

            if has_condition_time and (activates or is_shorten):
                _fail(
                    "EXCEPTION_TIME_ON_CONDITION",
                    "条件性替代窗口不得挂在例外条件原子上；必须写在被激活的义务后果上",
                    entity_id=entity_id,
                )

            if is_shorten and not activates:
                _fail(
                    "EXCEPTION_ACTIVATION_MISSING",
                    "条件性缩短必须显式激活替代义务组，不能只声明条件",
                    entity_id=entity_id,
                )

            if activates:
                waived = set(scoped_ids)
                for obligation_group_id in activates:
                    activated_obligation_ids.add(obligation_group_id)
                    obligation_group = obligation_by_id.get(obligation_group_id)
                    if obligation_group is None:
                        _fail(
                            "EXCEPTION_ACTIVATION_UNKNOWN_OBLIGATION",
                            "例外激活了未知义务组",
                            entity_id=entity_id,
                        )
                    reverse = set(
                        getattr(
                            obligation_group,
                            "activated_by_exception_group_ids",
                            (),
                        )
                        or ()
                    )
                    if exception_group_id and exception_group_id not in reverse:
                        _fail(
                            "BRANCH_CONSEQUENCE_MISMATCH",
                            "例外激活义务组与义务侧激活回链不一致",
                            entity_id=entity_id,
                        )
                    applies = set(
                        getattr(obligation_group, "applies_to_trigger_branch_ids", ())
                        or ()
                    )
                    if applies != waived:
                        _fail(
                            "BRANCH_CONSEQUENCE_MISMATCH",
                            "替代义务作用域必须与例外豁免的触发分支完全一致，不得漂移到兄弟分支",
                            entity_id=entity_id,
                        )
                    if not any(
                        _constraint_has_calendar_bound(
                            getattr(atom, "time_constraint", None)
                        )
                        for atom in getattr(obligation_group, "atoms", ()) or ()
                    ):
                        _fail(
                            "BRANCH_CONSEQUENCE_MISMATCH",
                            "被激活的替代义务组必须携带替代时间窗",
                            entity_id=entity_id,
                        )

                default_groups = [
                    obligation_group
                    for obligation_group in obligation_groups
                    if not (
                        getattr(obligation_group, "activated_by_exception_group_ids", ())
                        or ()
                    )
                    and set(
                        getattr(obligation_group, "applies_to_trigger_branch_ids", ())
                        or ()
                    )
                    == waived
                ]
                if not default_groups or not any(
                    _constraint_has_calendar_bound(getattr(atom, "time_constraint", None))
                    for obligation_group in default_groups
                    for atom in getattr(obligation_group, "atoms", ()) or ()
                ):
                    _fail(
                        "BRANCH_CONSEQUENCE_MISMATCH",
                        "条件性替代不得吞掉默认路径；同一触发分支必须保留未激活的默认义务时间窗",
                        entity_id=entity_id,
                    )
                if any(
                    set(
                        getattr(obligation_group, "applies_to_trigger_branch_ids", ())
                        or ()
                    )
                    != waived
                    for obligation_group in default_groups
                ):
                    _fail(
                        "BRANCH_CONSEQUENCE_MISMATCH",
                        "默认义务与替代义务必须指向同一触发分支集合",
                        entity_id=entity_id,
                    )

    for group in obligation_groups:
        group_id = getattr(group, "obligation_group_id", None)
        activated_by = list(getattr(group, "activated_by_exception_group_ids", ()) or ())
        if activated_by and (not group_id or group_id not in activated_obligation_ids):
            _fail(
                "OBLIGATION_ACTIVATION_ORPHAN",
                "替代义务组必须由例外条件分支显式激活，不得无条件漂浮",
                entity_id=entity_id,
            )

    # Reject unconditional OR between default and substitute windows that share
    # the same trigger scope but have no activation link.
    scoped_defaults: dict[frozenset[str], list[object]] = {}
    for group in obligation_groups:
        if getattr(group, "activated_by_exception_group_ids", ()) or ():
            continue
        key = frozenset(getattr(group, "applies_to_trigger_branch_ids", ()) or ())
        if any(
            _constraint_has_calendar_bound(getattr(atom, "time_constraint", None))
            for atom in getattr(group, "atoms", ()) or ()
        ):
            scoped_defaults.setdefault(key, []).append(group)
    for groups in scoped_defaults.values():
        if len(groups) > 1:
            _fail(
                "OBLIGATION_WINDOW_UNCONDITIONAL_OR",
                "同一触发作用域不得把多个默认时间窗写成无条件 OR；条件性替代必须经例外激活",
                entity_id=entity_id,
            )


def _check_anchor_decision_alignment(
    *,
    entity_id: str,
    bindings: Sequence[object],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
    expressions: Sequence[object | None],
    global_time_constraint: object | None,
) -> None:
    """Do not turn a future-anchor check into an earlier-stage failure."""

    anchors = {
        _value(getattr(global_time_constraint, "anchor_type", None))
    }
    for expression in expressions:
        anchors.update(
            _value(getattr(getattr(atom, "time_constraint", None), "anchor_type", None))
            for atom in _iter_expression_atoms(expression)
        )
    anchors.discard(None)
    if not anchors:
        return
    future_anchor_values = {
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
    }
    if not anchors & future_anchor_values:
        return

    target_order = {
        item.workflow_stage_id: index for index, item in enumerate(workflow_targets)
    }
    baseline_indexes = [
        target_order[item.workflow_stage_id]
        for item in workflow_targets
        if _value(getattr(item, "review_stage", None)) == ReviewStage.BASELINE.value
    ]
    if not baseline_indexes:
        _fail(
            "LATER_STAGE_DECISION_MISLABELED",
            "首次给药/随机/基线锚点没有冻结的后续基线节点",
            entity_id=entity_id,
        )
    decision_indexes = [
        target_order[getattr(binding, "workflow_stage_id")]
        for binding in bindings
        if _value(getattr(binding, "role", None)) == ReviewNodeRole.DECIDE_AT_NODE.value
    ]
    first_baseline_index = min(baseline_indexes)
    if any(decision_index < first_baseline_index for decision_index in decision_indexes):
        _fail(
            "EARLY_DECISION_FOR_FUTURE_ANCHOR",
            "首次给药/随机/基线锚点要求在较早节点只能提前关注，不能同时作最终判定",
            entity_id=entity_id,
        )
    if not any(
        decision_index >= baseline_index
        for baseline_index in baseline_indexes
        for decision_index in decision_indexes
    ):
        _fail(
            "LATER_STAGE_DECISION_MISLABELED",
            "后续基线/随机/首次给药决定不得标记为当前筛选失败",
            entity_id=entity_id,
        )

    decision_stage_ids = {
        getattr(binding, "workflow_stage_id")
        for binding in bindings
        if _value(getattr(binding, "role", None))
        == ReviewNodeRole.DECIDE_AT_NODE.value
    }
    exact_stage_patterns = {
        "first_dose_date": re.compile(
            r"(?:首次给药|给药前复核|\bW\s*0\b|\bD\s*1\b|first\s+dose)",
            re.IGNORECASE,
        ),
        "study_drug_administration_date": re.compile(
            r"(?:首次给药|给药前复核|\bW\s*0\b|\bD\s*1\b|first\s+dose)",
            re.IGNORECASE,
        ),
        "randomization_date": re.compile(r"(?:随机|randomi[sz])", re.IGNORECASE),
        "baseline_date": re.compile(r"(?:基线|baseline)", re.IGNORECASE),
    }
    for anchor in anchors & future_anchor_values:
        pattern = exact_stage_patterns[anchor]
        exact_ids = {
            item.workflow_stage_id
            for item in workflow_targets
            if pattern.search(
                " ".join(
                    value
                    for value in (item.display_name, item.visit_instance)
                    if value
                )
            )
        }
        if exact_ids and decision_stage_ids.isdisjoint(exact_ids):
            _fail(
                "ANCHOR_WORKFLOW_STAGE_MISMATCH",
                "时间锚点已有专门的冻结审核节点，最终判定不得退化为同阶段的其他访视节点",
                entity_id=entity_id,
            )


def _check_post_enrollment_procedure_classification(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Keep future protocol execution out of pre-enrollment controls."""

    future_anchors = {
        "baseline_date",
        "randomization_date",
        "first_dose_date",
        "study_drug_administration_date",
    }
    for atom in _iter_expression_atoms(obligation_expression):
        if _value(getattr(atom, "kind", None)) not in {
            ControlObligationKind.COMPLETE_OR_VERIFY.value,
            ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT.value,
        }:
            continue
        period = _value(
            getattr(getattr(atom, "prospective_period", None), "period", None)
        )
        constraint = getattr(atom, "time_constraint", None)
        anchor = _value(getattr(constraint, "anchor_type", None))
        direction = _value(getattr(constraint, "direction", None))
        has_positive_bound = (
            any(
                value is not None and int(getattr(value, "value", value)) > 0
                for value in (
                    getattr(constraint, "lower_bound_days", None),
                    getattr(constraint, "upper_bound_days", None),
                    getattr(constraint, "lower_bound", None),
                    getattr(constraint, "upper_bound", None),
                )
            )
            if constraint is not None
            else False
        )
        if period == "treatment_period" or (
            anchor in future_anchors and direction == "after" and has_positive_bound
        ):
            _fail(
                "POST_ENROLLMENT_PROCEDURE_MISCLASSIFIED",
                "治疗期或明确在首次给药后才执行的检查属于后续研究执行事项，不能作为筛选/基线入排控制发布",
                entity_id=entity_id,
            )


def _check_future_prohibition_not_decided_at_current_node(
    *,
    entity_id: str,
    obligation_expression: object,
    bindings: Sequence[object],
    minimum_evidence: Sequence[object] = (),
) -> None:
    """A pre-dose decision cannot certify that a future prohibition was obeyed."""

    if not any(_value(getattr(binding, "role", None)) == "decide_at_node" for binding in bindings):
        return
    for atom in _iter_expression_atoms(obligation_expression):
        if _value(getattr(atom, "kind", None)) not in {
            ControlObligationKind.PROHIBIT_EVENT.value,
            ControlObligationKind.PROHIBIT_MEDICATION_OR_TREATMENT_EXPOSURE.value,
        }:
            continue
        evaluation = getattr(atom, "evaluation", None)
        proposition = str(getattr(evaluation, "proposition", "") or "")
        source = " ".join(str(item or "") for item in getattr(atom, "source_excerpts", ()) or ())
        future_in_source = bool(_STUDY_PERIOD_CUE_RE.search(source) or _TREATMENT_PERIOD_CUE_RE.search(source))
        if not future_in_source:
            continue
        continuation = getattr(atom, "continuing_obligation", None)
        if continuation is None or getattr(atom, "prospective_period", None) is not None:
            _fail(
                "FUTURE_PROHIBITION_DECIDED_EARLY",
                "同时覆盖当前节点和后续期间的禁止要求，须分开保存可核事实和未到期持续义务",
                entity_id=entity_id,
            )
        observation_policy = getattr(evaluation, "observation_policy", None)
        observation_scope = str(getattr(observation_policy, "scope", "") or "")
        if _STUDY_PERIOD_CUE_RE.search(observation_scope) or _TREATMENT_PERIOD_CUE_RE.search(observation_scope):
            _fail(
                "FUTURE_PROHIBITION_DECIDED_EARLY",
                "当前节点的观察范围不得要求覆盖后续期间；未到期记录与本节点资料分开",
                entity_id=entity_id,
            )
        statement = str(getattr(atom, "statement", "") or "")
        if any(
            _STUDY_PERIOD_CUE_RE.search(text) or _TREATMENT_PERIOD_CUE_RE.search(text)
            for text in (proposition, statement)
        ):
            _fail(
                "FUTURE_PROHIBITION_DECIDED_EARLY",
                "当前节点的义务与求值命题不得包含后续期间；后续义务由未到期记录承载",
                entity_id=entity_id,
            )
        for text in (
            *(str(getattr(binding, "guidance", "") or "") for binding in bindings),
            *(str(getattr(item, "description", "") or "") for item in minimum_evidence),
        ):
            if _requires_future_compliance_proof(text):
                _fail(
                    "FUTURE_PROHIBITION_DECIDED_EARLY",
                    "当前审核指引或最低证据不得要求证明后续期间已经遵守",
                    entity_id=entity_id,
                )


def _requires_future_compliance_proof(text: str) -> bool:
    """Distinguish an actual proof demand from an explicit refusal to demand it."""

    if not (_STUDY_PERIOD_CUE_RE.search(text) or _TREATMENT_PERIOD_CUE_RE.search(text)):
        return False
    for clause in _STRONG_CLAUSE_BOUNDARY_RE.split(text):
        for segment in re.split(r"[，,、]", clause):
            if not (_STUDY_PERIOD_CUE_RE.search(segment) or _TREATMENT_PERIOD_CUE_RE.search(segment)):
                continue
            for match in re.finditer(
                r"(?:证明|确认|核实|判定)[^，,、。；\n]{0,40}(?:已|未|均未|没有发生)",
                segment,
            ):
                prefix = segment[:match.start()]
                if re.search(r"(?:不要求|无需|不必|不需|不得|不能|不应)[^，,、。；\n]{0,12}$", prefix):
                    continue
                return True
    return False


def _check_nodes(
    *,
    entity_id: str,
    bindings: Sequence[object],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
    evidence: Sequence[object] = (),
) -> None:
    if not workflow_targets:
        _fail("WORKFLOW_STAGE_TARGETS_MISSING", "发布控制必须使用冻结流程节点目录", entity_id=entity_id)
    target_by_id = {item.workflow_stage_id: item for item in workflow_targets}
    target_order = {item.workflow_stage_id: index for index, item in enumerate(workflow_targets)}
    seen_ids: set[str] = set()
    role_bindings: list[tuple[int, str]] = []
    decision_nodes: set[str] = set()
    for binding in bindings:
        stage_id = getattr(binding, "workflow_stage_id", None)
        review_stage = _value(getattr(binding, "review_stage", None))
        role = _value(getattr(binding, "role", None))
        if not isinstance(stage_id, str) or not stage_id.strip() or not review_stage or not role:
            _fail("NODE_ROLE_MISSING_OR_AMBIGUOUS", "审核节点必须同时包含冻结身份、期别和明确作用", entity_id=entity_id)
        if stage_id in seen_ids:
            _fail("NODE_ROLE_MISSING_OR_AMBIGUOUS", "同一审核节点不得绑定多个作用", entity_id=entity_id)
        seen_ids.add(stage_id)
        target = target_by_id.get(stage_id)
        if target is None:
            _fail("UNKNOWN_WORKFLOW_STAGE_TARGET", "审核节点不是冻结流程节点", entity_id=entity_id)
        if review_stage != _value(getattr(target, "review_stage", None)):
            _fail("WORKFLOW_REVIEW_STAGE_MISMATCH", "审核节点 ReviewStage 与冻结目标不一致", entity_id=entity_id)
        role_bindings.append((target_order[stage_id], role))
        if role == ReviewNodeRole.DECIDE_AT_NODE.value:
            decision_nodes.add(stage_id)

    if not any(role == ReviewNodeRole.DECIDE_AT_NODE.value for _, role in role_bindings):
        if any(role == ReviewNodeRole.LATER_NODE_REVIEW.value for _, role in role_bindings):
            _fail(
                "LATER_NODE_DECISION_MISSING",
                "后续节点复核不得被伪装为当前节点失败，且必须有后续决定性节点",
                entity_id=entity_id,
            )
        _fail("DECISION_NODE_ROLE_MISSING", "正式控制至少需要一个本节点判定作用", entity_id=entity_id)
    decision_indexes = [index for index, role in role_bindings if role == ReviewNodeRole.DECIDE_AT_NODE.value]
    for index, role in role_bindings:
        if role == ReviewNodeRole.EARLY_ATTENTION.value and not any(decision >= index for decision in decision_indexes):
            _fail("DECISION_NODE_ROLE_MISSING", "提前关注必须有本节点或后续判定节点", entity_id=entity_id)
        if role == ReviewNodeRole.LATER_NODE_REVIEW.value and not any(decision > index for decision in decision_indexes):
            _fail(
                "LATER_NODE_DECISION_MISSING",
                "后续节点复核不得被伪装为当前节点失败，且必须有后续决定性节点",
                entity_id=entity_id,
            )

    valid_review_stages = {_value(getattr(item, "review_stage", None)) for item in workflow_targets}
    evidence_nodes: set[str] = set()
    for item in evidence:
        due_stage = _value(getattr(item, "due_stage", None))
        if not due_stage or due_stage not in valid_review_stages:
            _fail("EVIDENCE_NODE_TARGET_MISSING", "最低证据的应完成节点不在冻结节点目录", entity_id=entity_id)
        node_ids = getattr(item, "workflow_stage_ids", ())
        if not node_ids or len(node_ids) != len(set(node_ids)):
            _fail("EVIDENCE_NODE_TARGET_MISSING", "最低证据须明确对应的具体访视且不得重复", entity_id=entity_id)
        for node_id in node_ids:
            target = target_by_id.get(node_id)
            if target is None or node_id not in seen_ids:
                _fail("EVIDENCE_NODE_TARGET_MISSING", "最低证据节点必须属于本控制的冻结节点绑定", entity_id=entity_id)
            if _value(getattr(target, "review_stage", None)) != due_stage:
                _fail("EVIDENCE_NODE_TARGET_MISSING", "最低证据期别与具体访视不一致", entity_id=entity_id)
            evidence_nodes.add(node_id)
    if decision_nodes - evidence_nodes:
        _fail(
            "DECISION_STAGE_EVIDENCE_MISSING",
            "每个本节点判定都必须有明确对应该访视的最低证据",
            entity_id=entity_id,
        )


def _check_planned_visit_node_closure(
    *,
    entity_id: str,
    expressions: Sequence[object | None],
    bindings: Sequence[object],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
) -> None:
    excerpts = [
        str(excerpt)
        for expression in expressions
        for atom in _iter_expression_atoms(expression)
        for excerpt in (getattr(atom, "source_excerpts", ()) or ())
    ]
    if not any(_PLANNED_VISIT_SCOPE_RE.search(text) for text in excerpts):
        return
    planned_visit_ids = {
        target.workflow_stage_id
        for target in workflow_targets
        if getattr(target, "visit_instance", None)
    }
    decision_bound_ids = {
        str(getattr(binding, "workflow_stage_id", ""))
        for binding in bindings
        if _value(getattr(binding, "role", None)) == ReviewNodeRole.DECIDE_AT_NODE.value
    }
    missing = sorted(planned_visit_ids - decision_bound_ids)
    if missing:
        labels = {
            target.workflow_stage_id: target.display_name
            for target in workflow_targets
        }
        _fail(
            "PLANNED_VISIT_SCOPE_DROPPED",
            "原文要求在计划访视执行的控制必须在冻结目录中的全部访视节点分别判定，当前遗漏："
            + "、".join(labels.get(stage_id, stage_id) for stage_id in missing),
            entity_id=entity_id,
        )


def _validate_relation_targets(
    relations: Sequence[object],
    *,
    entity_id: str,
    self_kind: ControlRelationTargetKind,
    self_id: str,
    known_official_codes: set[str],
    known_procedure_ids: set[str],
    known_control_ids: set[str],
    known_candidate_ids: set[str],
    known_rule_component_ids: set[str],
    known_workflow_stage_ids: set[str],
    candidate_wire_mode: bool = False,
) -> None:
    relation_ids: list[str] = []
    for relation in relations:
        relation_id = getattr(relation, "relation_id", None)
        if relation_id is not None:
            relation_ids.append(relation_id)
        kind = _value(getattr(relation, "kind", None))
        if kind == CrossSourceRelationKind.SUBSTANTIVE_CONFLICT.value:
            _fail("UNRESOLVED_SUBSTANTIVE_CONFLICT", "实质性跨来源冲突必须停止发布", entity_id=entity_id)

        left_kind = _value(getattr(relation, "left_target_kind", None))
        right_kind = _value(getattr(relation, "right_target_kind", None))
        left_id = getattr(relation, "left_target_id", None)
        right_id = getattr(relation, "right_target_id", None)
        if candidate_wire_mode:
            candidate_side = getattr(relation, "candidate_side", None)
            external_kind = _value(getattr(relation, "external_target_kind", None))
            external_id = getattr(relation, "external_target_id", None)
            if candidate_side not in {"left", "right"} or external_kind not in {
                ControlRelationTargetKind.OFFICIAL_RULE.value,
                ControlRelationTargetKind.REQUIRED_PROCEDURE.value,
                ControlRelationTargetKind.WORKFLOW_STAGE.value,
            }:
                _fail("RELATION_TARGET_INVALID", "候选关系必须包含一个当前候选和一个冻结外部目标", entity_id=entity_id)
            if external_kind == ControlRelationTargetKind.OFFICIAL_RULE.value and external_id not in known_official_codes:
                _fail("UNKNOWN_RELATION_TARGET", "关系引用了未知官方规则", entity_id=entity_id)
            if external_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE.value and external_id not in known_procedure_ids:
                _fail("UNKNOWN_RELATION_TARGET", "关系引用了未知流程必做目标", entity_id=entity_id)
            if external_kind == ControlRelationTargetKind.WORKFLOW_STAGE.value and external_id not in known_workflow_stage_ids:
                _fail("UNKNOWN_RELATION_TARGET", "关系引用了未知流程节点", entity_id=entity_id)
            continue

        self_count = int(left_kind == self_kind.value and left_id == self_id) + int(
            right_kind == self_kind.value and right_id == self_id
        )
        if self_count != 1:
            _fail("RELATION_CURRENT_ENDPOINT_INVALID", "跨来源关系必须恰好包含当前控制身份", entity_id=entity_id)

        endpoints = ((left_kind, left_id), (right_kind, right_id))
        for target_kind, target_id in endpoints:
            if target_kind == self_kind.value and target_id == self_id:
                continue
            known = {
                ControlRelationTargetKind.OFFICIAL_RULE.value: target_id in known_official_codes,
                ControlRelationTargetKind.REQUIRED_PROCEDURE.value: target_id in known_procedure_ids,
                ControlRelationTargetKind.PROTOCOL_CONTROL.value: target_id in known_control_ids,
                ControlRelationTargetKind.CONTROL_CANDIDATE.value: target_id in known_candidate_ids,
                ControlRelationTargetKind.RULE_COMPONENT.value: target_id in known_rule_component_ids,
                ControlRelationTargetKind.WORKFLOW_STAGE.value: target_id in known_workflow_stage_ids,
            }.get(target_kind, False)
            if not known:
                _fail("UNKNOWN_RELATION_TARGET", "跨来源关系引用了未知或未冻结的目标", entity_id=entity_id)
        if kind == CrossSourceRelationKind.DUPLICATE_STATEMENT.value and not getattr(
            relation, "shared_assessment_identity", None
        ):
            _fail("DUPLICATE_RELATION_IDENTITY_MISSING", "重复表述关系必须经过确认并携带共享评估身份", entity_id=entity_id)
        if kind != CrossSourceRelationKind.DUPLICATE_STATEMENT.value and getattr(
            relation, "shared_assessment_identity", None
        ):
            _fail("RELATION_SHARED_IDENTITY_INVALID", "非重复表述关系不得共享评估身份", entity_id=entity_id)
    if len(relation_ids) != len(set(relation_ids)):
        _fail("RELATION_ID_DUPLICATE", "跨来源关系身份不得重复", entity_id=entity_id)


def _check_supplementary_procedure_stage_alignment(
    relations: Sequence[object],
    *,
    entity_id: str,
    bindings: Sequence[object],
    evidence: Sequence[object],
    obligation_expression: object | None = None,
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
) -> None:
    procedures = {item.catalog_item_id: item for item in procedure_targets}
    workflow_by_id = {item.workflow_stage_id: item for item in workflow_targets}
    for relation in relations:
        affected_id = getattr(relation, "affected_workflow_stage_id", None)
        required_ids = [
            target_id
            for target_kind, target_id in (
                (
                    _value(getattr(relation, "left_target_kind", None)),
                    getattr(relation, "left_target_id", None),
                ),
                (
                    _value(getattr(relation, "right_target_kind", None)),
                    getattr(relation, "right_target_id", None),
                ),
            )
            if target_kind == ControlRelationTargetKind.REQUIRED_PROCEDURE.value
        ]
        is_supplement = (
            _value(getattr(relation, "kind", None))
            == CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT.value
        )
        if not is_supplement or not required_ids:
            if affected_id is not None:
                _fail(
                    "AFFECTED_STAGE_NOT_APPLICABLE",
                    "只有补充流程必做项可以声明受影响审核节点",
                    entity_id=entity_id,
                )
            continue
        if len(required_ids) != 1:
            _fail(
                "PROCEDURE_RELATION_TARGET_INVALID",
                "补充流程关系必须恰好引用一个流程必做目标",
                entity_id=entity_id,
            )
        if not affected_id:
            _fail(
                "AFFECTED_STAGE_MISSING",
                "补充流程必做项必须声明首次受影响的冻结审核节点",
                entity_id=entity_id,
            )
        procedure = procedures.get(required_ids[0])
        affected = workflow_by_id.get(affected_id)
        if procedure is None or affected is None:
            _fail(
                "UNKNOWN_AFFECTED_WORKFLOW_STAGE",
                "补充流程必做项引用了未知的受影响审核节点",
                entity_id=entity_id,
            )
        execution_id = procedure_execution_workflow_stage_id(
            procedure, workflow_targets
        )
        cross_stage = is_cross_stage_subsequent_control_supplement(
            obligation_expression=obligation_expression,
            procedure=procedure,
            affected_workflow_stage_id=affected_id,
            workflow_targets=workflow_targets,
        )
        if cross_stage:
            if execution_id == affected_id:
                _fail(
                    "PROCEDURE_AFFECTED_STAGE_MISMATCH",
                    "跨阶段后续控制补充的受影响审核节点必须晚于流程必做执行访视",
                    entity_id=entity_id,
                )
        elif execution_id != affected_id:
            _fail(
                "PROCEDURE_AFFECTED_STAGE_MISMATCH",
                "补充关系的受影响审核节点与所引用流程必做访视不一致",
                entity_id=entity_id,
            )
        if not any(
            getattr(binding, "workflow_stage_id", None) == affected_id
            and _value(getattr(binding, "role", None))
            == ReviewNodeRole.DECIDE_AT_NODE.value
            for binding in bindings
        ):
            _fail(
                "AFFECTED_STAGE_DECISION_MISSING",
                "补充流程必做项必须在其受影响审核节点作本节点判定",
                entity_id=entity_id,
            )
        if not any(
            _value(getattr(item, "due_stage", None))
            == _value(affected.review_stage)
            for item in evidence
        ):
            _fail(
                "AFFECTED_STAGE_EVIDENCE_MISSING",
                "补充流程必做项的最低证据不得晚于受影响审核节点",
                entity_id=entity_id,
            )


def _check_temporal_obligation_relation_scope(
    *,
    entity_id: str,
    obligation_expression: object,
    relations: Sequence[object],
    bindings: Sequence[object],
) -> None:
    kinds = {
        _value(getattr(atom, "kind", None))
        for atom in _iter_expression_atoms(obligation_expression)
    }
    if {
        ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT.value,
        ControlObligationKind.VERIFY_RESULT_VALIDITY.value,
    }.issubset(kinds):
        _fail(
            "MIXED_OBLIGATION_KIND_SCOPE",
            "访视安排与结果有效期必须分别表达，并保留各自来源",
            entity_id=entity_id,
        )
    relation_target_kinds: set[str] = set()
    workflow_relation_ids: set[str] = set()
    for relation in relations:
        for target_kind, target_id in (
            (
                _value(getattr(relation, "left_target_kind", None)),
                getattr(relation, "left_target_id", None),
            ),
            (
                _value(getattr(relation, "right_target_kind", None)),
                getattr(relation, "right_target_id", None),
            ),
        ):
            if target_kind in {
                ControlRelationTargetKind.REQUIRED_PROCEDURE.value,
                ControlRelationTargetKind.WORKFLOW_STAGE.value,
            }:
                relation_target_kinds.add(target_kind)
            if target_kind == ControlRelationTargetKind.WORKFLOW_STAGE.value:
                workflow_relation_ids.add(str(target_id))
    binding_ids = {
        str(getattr(binding, "workflow_stage_id", "")) for binding in bindings
    }
    if ControlObligationKind.SCHEDULE_OR_VERIFY_VISIT.value in kinds:
        if ControlRelationTargetKind.REQUIRED_PROCEDURE.value in relation_target_kinds:
            _fail(
                "VISIT_SCHEDULE_TARGET_TOO_NARROW",
                "访视安排规则不得把通用时间窗传播到单个检查项",
                entity_id=entity_id,
            )
        if not workflow_relation_ids or not workflow_relation_ids.issubset(binding_ids):
            _fail(
                "VISIT_SCHEDULE_WORKFLOW_TARGET_MISSING",
                "访视安排规则必须关联本控制已绑定的冻结流程节点",
                entity_id=entity_id,
            )
    if ControlObligationKind.VERIFY_RESULT_VALIDITY.value in kinds and not any(
        _value(getattr(relation, "kind", None))
        == CrossSourceRelationKind.SUPPLEMENTARY_REQUIREMENT.value
        and ControlRelationTargetKind.REQUIRED_PROCEDURE.value
        in {
            _value(getattr(relation, "left_target_kind", None)),
            _value(getattr(relation, "right_target_kind", None)),
        }
        for relation in relations
    ):
        _fail(
            "RESULT_VALIDITY_PROCEDURE_TARGET_MISSING",
            "结果有效期必须补充到受影响的冻结流程必做项",
            entity_id=entity_id,
        )
    if ControlObligationKind.SELECT_BASELINE_VALUE.value in kinds:
        if not relation_target_kinds:
            _fail(
                "BASELINE_VALUE_SCOPE_MISSING",
                "基线值选取原则必须明确关联通用流程节点或精确检查项",
                entity_id=entity_id,
            )
        if len(relation_target_kinds) > 1:
            _fail(
                "BASELINE_VALUE_SCOPE_MIXED",
                "通用基线值原则与具体检查项特例必须分开表达",
                entity_id=entity_id,
            )


def _validate_candidate(
    candidate: ProtocolControlCandidate,
    *,
    unit_by_id: dict[str, ProtocolStructureUnit],
    allowed_span_ids: set[str],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    official_codes: set[str],
    procedure_ids: set[str],
    candidate_ids: set[str],
) -> None:
    candidate_id = getattr(candidate, "control_candidate_id", None)
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        _fail("CANDIDATE_ID_MISSING", "控制候选必须有系统身份")
    if _value(getattr(candidate, "study_phase", None)) not in {
        _value(getattr(next(iter(unit_by_id.values())), "study_phase", None)),
    }:
        _fail("PHASE_MISMATCH", "控制候选期别与全文清单不一致", entity_id=candidate_id)
    semantics = getattr(candidate, "semantics", None)
    if not isinstance(semantics, ProtocolControlCandidateSemantics):
        _fail("CANDIDATE_SEMANTICS_MISSING", "候选发布前必须完成系统水合语义", entity_id=candidate_id)
    if getattr(semantics, "control_candidate_id", None) != candidate_id:
        _fail("CANDIDATE_ID_MISMATCH", "候选语义未绑定当前系统候选身份", entity_id=candidate_id)
    source_unit_ids = list(getattr(candidate, "frozen_structure_unit_ids", ()))
    source_span_ids = list(getattr(candidate, "source_span_ids", ()))
    units = _source_scope(
        entity_id=candidate_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_span_ids,
        unit_by_id=unit_by_id,
        allowed_span_ids=allowed_span_ids,
    )
    if list(getattr(semantics, "source_structure_unit_ids", ())) != source_unit_ids:
        _fail("CANDIDATE_SCOPE_MISMATCH", "候选语义结构单元范围与冻结候选不一致", entity_id=candidate_id)
    if list(getattr(semantics, "source_span_ids", ())) != source_span_ids:
        _fail("CANDIDATE_SCOPE_MISMATCH", "候选语义来源闭包与冻结候选不一致", entity_id=candidate_id)
    source_spans = set(source_span_ids)
    _check_dnf(
        getattr(semantics, "applicability_expression", None),
        label="适用性",
        entity_id=candidate_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_dnf(
        getattr(semantics, "trigger_expression", None),
        label="触发",
        entity_id=candidate_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    obligation_expression = getattr(semantics, "obligation_expression", None)
    _check_dnf(
        obligation_expression,
        label="义务",
        entity_id=candidate_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_dnf(
        getattr(semantics, "exception_expression", None),
        label="例外",
        entity_id=candidate_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_conditional_branch_mapping(
        entity_id=candidate_id,
        units=units,
        trigger_expression=getattr(semantics, "trigger_expression", None),
        obligation_expression=obligation_expression,
    )
    _check_exception_layer(
        entity_id=candidate_id,
        semantic_expressions=(
            getattr(semantics, "applicability_expression", None),
            getattr(semantics, "trigger_expression", None),
            obligation_expression,
        ),
        exception_expression=getattr(semantics, "exception_expression", None),
    )
    _check_routine_action_not_trigger(
        entity_id=candidate_id,
        trigger_expression=getattr(semantics, "trigger_expression", None),
        obligation_expression=obligation_expression,
    )
    _check_mixed_trigger_decision_stages(
        entity_id=candidate_id,
        trigger_expression=getattr(semantics, "trigger_expression", None),
    )
    _check_mixed_decision_stage_control(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
    )
    _check_post_enrollment_procedure_classification(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
    )
    _check_future_prohibition_not_decided_at_current_node(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        bindings=getattr(semantics, "review_node_bindings", ()),
        minimum_evidence=getattr(semantics, "minimum_evidence", ()),
    )
    _check_obligation_modality_and_event_anchor(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
    )
    _check_conditional_exemption_binding(
        entity_id=candidate_id,
        units=units,
        trigger_expression=getattr(semantics, "trigger_expression", None),
        obligation_expression=obligation_expression,
    )
    _check_exemption_evidence_modality(
        entity_id=candidate_id,
        units=units,
        obligation_expression=obligation_expression,
        evidence=getattr(semantics, "minimum_evidence", ()),
    )
    _check_recording_precision_fidelity(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
    )
    _check_collection_obligation_semantics(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        bindings=getattr(semantics, "review_node_bindings", ()),
    )
    _check_review_guidance_action_fidelity(
        entity_id=candidate_id,
        units=units,
        obligation_expression=obligation_expression,
        bindings=getattr(semantics, "review_node_bindings", ()),
    )
    _check_minimum_evidence_modality_fidelity(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        evidence=getattr(semantics, "minimum_evidence", ()),
    )
    _check_minimum_evidence_authority_boundary(
        entity_id=candidate_id,
        evidence=getattr(semantics, "minimum_evidence", ()),
    )
    _check_professional_judgment_fidelity(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        evidence=getattr(semantics, "minimum_evidence", ()),
    )
    _check_authority_reference_provenance(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
    )
    _check_participant_preparation_realization_fidelity(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        user_facing_texts=[
            *(
                str(getattr(item, "guidance", "") or "")
                for item in getattr(semantics, "review_node_bindings", ())
            ),
            *(
                str(getattr(item, "description", "") or "")
                for item in getattr(semantics, "minimum_evidence", ())
            ),
        ],
    )
    _check_user_facing_item_count_fidelity(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        user_facing_texts=[
            *(
                str(getattr(item, "guidance", "") or "")
                for item in getattr(semantics, "review_node_bindings", ())
            ),
            *(
                str(getattr(item, "description", "") or "")
                for item in getattr(semantics, "minimum_evidence", ())
            ),
        ],
    )
    from app.protocols.control_evidence_policy import validate_control_evidence_policy_sources
    from app.domain.contracts.control_evidence_dependency import validate_control_evidence_dependencies
    from app.domain.contracts.control_evaluation_spec import validate_control_expression_evaluations
    try:
        validate_control_expression_evaluations(semantics)
    except ValueError as exc:
        _fail("CONTROL_EVALUATION_SPEC_INVALID", str(exc), entity_id=candidate_id)
    try:
        validate_control_evidence_policy_sources(semantics.minimum_evidence, source_spans, units)
        validate_control_evidence_dependencies(semantics)
    except ValueError as exc:
        _fail("EVIDENCE_SOURCE_POLICY_INVALID", str(exc), entity_id=candidate_id)
    _check_nodes(
        entity_id=candidate_id,
        bindings=getattr(semantics, "review_node_bindings", ()),
        workflow_targets=workflow_targets,
        evidence=getattr(semantics, "minimum_evidence", ()),
    )
    texts = [getattr(semantics, "title", ""), getattr(semantics, "applicable_population", "")]
    for expression in (
        getattr(semantics, "applicability_expression", None),
        getattr(semantics, "trigger_expression", None),
        obligation_expression,
        getattr(semantics, "exception_expression", None),
    ):
        for atom in _iter_expression_atoms(expression):
            texts.append(str(getattr(atom, "statement", "")))
            texts.extend(str(item) for item in getattr(atom, "source_excerpts", ()) or ())
    _check_planned_visit_node_closure(
        entity_id=candidate_id,
        expressions=(
            getattr(semantics, "applicability_expression", None),
            getattr(semantics, "trigger_expression", None),
            obligation_expression,
            getattr(semantics, "exception_expression", None),
        ),
        bindings=getattr(semantics, "review_node_bindings", ()),
        workflow_targets=workflow_targets,
    )
    _check_branch_scope_and_paired_consequences(
        entity_id=candidate_id,
        trigger_expression=getattr(semantics, "trigger_expression", None),
        obligation_expression=obligation_expression,
        exception_expression=getattr(semantics, "exception_expression", None),
    )
    _check_time_constraints(
        entity_id=candidate_id,
        texts=texts,
        expressions=(
            getattr(semantics, "applicability_expression", None),
            getattr(semantics, "trigger_expression", None),
            obligation_expression,
            getattr(semantics, "exception_expression", None),
        ),
        flat_atoms=(),
        global_time_constraint=None,
    )
    _check_anchor_decision_alignment(
        entity_id=candidate_id,
        bindings=semantics.review_node_bindings,
        workflow_targets=workflow_targets,
        expressions=(
            getattr(semantics, "applicability_expression", None),
            getattr(semantics, "trigger_expression", None),
            obligation_expression,
            getattr(semantics, "exception_expression", None),
        ),
        global_time_constraint=None,
    )
    _validate_relation_targets(
        getattr(semantics, "cross_source_relations", ()),
        entity_id=candidate_id,
        self_kind=ControlRelationTargetKind.CONTROL_CANDIDATE,
        self_id=candidate_id,
        known_official_codes=official_codes,
        known_procedure_ids=procedure_ids,
        known_control_ids=set(),
        known_candidate_ids={candidate_id},
        known_rule_component_ids=set(),
        known_workflow_stage_ids={
            item.workflow_stage_id for item in workflow_targets
        },
        candidate_wire_mode=False,
    )
    _check_temporal_obligation_relation_scope(
        entity_id=candidate_id,
        obligation_expression=obligation_expression,
        relations=getattr(semantics, "cross_source_relations", ()),
        bindings=getattr(semantics, "review_node_bindings", ()),
    )
    _check_supplementary_procedure_stage_alignment(
        getattr(semantics, "cross_source_relations", ()),
        entity_id=candidate_id,
        bindings=getattr(semantics, "review_node_bindings", ()),
        evidence=getattr(semantics, "minimum_evidence", ()),
        obligation_expression=obligation_expression,
        procedure_targets=procedure_targets,
        workflow_targets=workflow_targets,
    )


def _check_obligation_logic(
    control: ProtocolReviewControl,
    *,
    entity_id: str,
    obligation_expression: ControlObligationDnf,
) -> None:
    if getattr(control, "obligation_combination", "all") == "any":
        _fail(
            "OBLIGATION_AND_WEAKENED",
            "5.8b 显式义务 DNF 不得被兼容 any 组合标志弱化",
            entity_id=entity_id,
        )
    groups = list(getattr(obligation_expression, "groups", ()))
    texts = [
        str(getattr(atom, "statement", ""))
        for group in groups
        for atom in getattr(group, "atoms", ()) or ()
    ]
    texts.extend(
        str(excerpt)
        for group in groups
        for atom in getattr(group, "atoms", ()) or ()
        for excerpt in getattr(atom, "source_excerpts", ()) or ()
    )
    if len(groups) > 1 and all(len(getattr(group, "atoms", ()) or ()) == 1 for group in groups):
        if any(_AND_CUE_RE.search(text) for text in texts):
            _fail(
                "OBLIGATION_AND_WEAKENED",
                "原文合取义务不得拆成多个可择一的 DNF 分支",
                entity_id=entity_id,
            )


def _validate_control(
    control: ProtocolReviewControl,
    *,
    unit_by_id: dict[str, ProtocolStructureUnit],
    allowed_span_ids: set[str],
    workflow_targets: Sequence[KnownWorkflowStageTarget],
    procedure_targets: Sequence[KnownRequiredProcedureTarget],
    official_codes: set[str],
    procedure_ids: set[str],
    control_ids: set[str],
    candidate_ids: set[str],
    rule_component_ids: set[str],
) -> None:
    control_id = getattr(control, "protocol_control_id", None)
    if not isinstance(control_id, str) or not control_id.strip():
        _fail("CONTROL_ID_MISSING", "正式控制必须有系统身份")
    if _value(getattr(control, "study_phase", None)) != _value(next(iter(unit_by_id.values())).study_phase):
        _fail("PHASE_MISMATCH", "正式控制期别与全文清单不一致", entity_id=control_id)
    source_unit_ids = list(getattr(control, "source_structure_unit_ids", ()))
    source_span_ids = list(getattr(control, "source_span_ids", ()))
    units = _source_scope(
        entity_id=control_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_span_ids,
        unit_by_id=unit_by_id,
        allowed_span_ids=allowed_span_ids,
    )
    source_spans = set(source_span_ids)

    obligation_expression = getattr(control, "obligation_expression", None)
    if obligation_expression is None:
        _fail(
            "LEGACY_FLAT_OBLIGATION_REJECTED",
            "5.8b 发布必须使用显式义务 DNF，不能只使用 5.8a flat obligations",
            entity_id=control_id,
        )
    _check_dnf(
        getattr(control, "applicability_expression", None),
        label="适用性",
        entity_id=control_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_dnf(
        getattr(control, "trigger_expression", None),
        label="触发",
        entity_id=control_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_dnf(
        obligation_expression,
        label="义务",
        entity_id=control_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    exception_expression = getattr(control, "exception_expression", None)
    _check_dnf(
        exception_expression,
        label="例外",
        entity_id=control_id,
        source_unit_ids=source_unit_ids,
        source_span_ids=source_spans,
        units=units,
    )
    _check_obligation_logic(control, entity_id=control_id, obligation_expression=obligation_expression)
    _check_mixed_decision_stage_control(
        entity_id=control_id,
        obligation_expression=obligation_expression,
    )
    _check_mixed_trigger_decision_stages(
        entity_id=control_id,
        trigger_expression=getattr(control, "trigger_expression", None),
    )
    _check_future_prohibition_not_decided_at_current_node(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        bindings=getattr(control, "review_node_bindings", ()),
        minimum_evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_obligation_modality_and_event_anchor(
        entity_id=control_id,
        obligation_expression=obligation_expression,
    )
    _check_conditional_exemption_binding(
        entity_id=control_id,
        units=units,
        trigger_expression=getattr(control, "trigger_expression", None),
        obligation_expression=obligation_expression,
    )
    _check_exemption_evidence_modality(
        entity_id=control_id,
        units=units,
        obligation_expression=obligation_expression,
        evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_collection_obligation_semantics(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        bindings=getattr(control, "review_node_bindings", ()),
    )
    _check_review_guidance_action_fidelity(
        entity_id=control_id,
        units=units,
        obligation_expression=obligation_expression,
        bindings=getattr(control, "review_node_bindings", ()),
    )
    _check_minimum_evidence_modality_fidelity(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_minimum_evidence_authority_boundary(
        entity_id=control_id,
        evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_professional_judgment_fidelity(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_authority_reference_provenance(
        entity_id=control_id,
        obligation_expression=obligation_expression,
    )
    _check_participant_preparation_realization_fidelity(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        user_facing_texts=[
            *(
                str(getattr(item, "guidance", "") or "")
                for item in getattr(control, "review_node_bindings", ())
            ),
            *(
                str(getattr(item, "description", "") or "")
                for item in getattr(control, "minimum_evidence", ())
            ),
        ],
    )
    _check_user_facing_item_count_fidelity(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        user_facing_texts=[
            *(
                str(getattr(item, "guidance", "") or "")
                for item in getattr(control, "review_node_bindings", ())
            ),
            *(
                str(getattr(item, "description", "") or "")
                for item in getattr(control, "minimum_evidence", ())
            ),
        ],
    )
    flat_obligations = list(getattr(control, "obligations", ()) or ())
    if flat_obligations:
        expression_ids = [
            getattr(atom, "obligation_id", None)
            for group in getattr(obligation_expression, "groups", ())
            for atom in getattr(group, "atoms", ()) or ()
        ]
        flat_ids = [getattr(atom, "obligation_id", None) for atom in flat_obligations]
        if expression_ids != flat_ids:
            _fail("OBLIGATION_COMPATIBILITY_MISMATCH", "显式义务 DNF 与兼容义务集表达了不同语义", entity_id=control_id)

    from app.protocols.control_evidence_policy import validate_control_evidence_policy_sources
    from app.domain.contracts.control_evidence_dependency import validate_control_evidence_dependencies
    from app.domain.contracts.control_evaluation_spec import validate_control_evaluations
    try:
        validate_control_evaluations(control)
    except ValueError as exc:
        _fail("CONTROL_EVALUATION_SPEC_INVALID", str(exc), entity_id=control_id)
    try:
        validate_control_evidence_policy_sources(control.minimum_evidence, source_spans, units)
        validate_control_evidence_dependencies(control)
    except ValueError as exc:
        _fail("EVIDENCE_SOURCE_POLICY_INVALID", str(exc), entity_id=control_id)
    _check_nodes(
        entity_id=control_id,
        bindings=getattr(control, "review_node_bindings", ()),
        workflow_targets=workflow_targets,
        evidence=getattr(control, "minimum_evidence", ()),
    )
    _check_planned_visit_node_closure(
        entity_id=control_id,
        expressions=(
            getattr(control, "applicability_expression", None),
            getattr(control, "trigger_expression", None),
            obligation_expression,
            exception_expression,
        ),
        bindings=getattr(control, "review_node_bindings", ()),
        workflow_targets=workflow_targets,
    )
    _check_branch_scope_and_paired_consequences(
        entity_id=control_id,
        trigger_expression=getattr(control, "trigger_expression", None),
        obligation_expression=obligation_expression,
        exception_expression=exception_expression,
    )
    _check_time_constraints(
        entity_id=control_id,
        texts=_texts_for_control(control),
        expressions=(
            getattr(control, "applicability_expression", None),
            getattr(control, "trigger_expression", None),
            obligation_expression,
            exception_expression,
        ),
        flat_atoms=flat_obligations,
        global_time_constraint=getattr(control, "control_time_constraint", None),
    )
    _check_anchor_decision_alignment(
        entity_id=control_id,
        bindings=getattr(control, "review_node_bindings", ()),
        workflow_targets=workflow_targets,
        expressions=(
            getattr(control, "applicability_expression", None),
            getattr(control, "trigger_expression", None),
            obligation_expression,
            exception_expression,
        ),
        global_time_constraint=getattr(control, "control_time_constraint", None),
    )
    _validate_relation_targets(
        getattr(control, "cross_source_relations", ()),
        entity_id=control_id,
        self_kind=ControlRelationTargetKind.PROTOCOL_CONTROL,
        self_id=control_id,
        known_official_codes=official_codes,
        known_procedure_ids=procedure_ids,
        known_control_ids=control_ids,
        known_candidate_ids=candidate_ids,
        known_rule_component_ids=rule_component_ids,
        known_workflow_stage_ids={
            item.workflow_stage_id for item in workflow_targets
        },
    )
    _check_temporal_obligation_relation_scope(
        entity_id=control_id,
        obligation_expression=obligation_expression,
        relations=getattr(control, "cross_source_relations", ()),
        bindings=getattr(control, "review_node_bindings", ()),
    )
    _check_supplementary_procedure_stage_alignment(
        getattr(control, "cross_source_relations", ()),
        entity_id=control_id,
        bindings=getattr(control, "review_node_bindings", ()),
        evidence=getattr(control, "minimum_evidence", ()),
        obligation_expression=obligation_expression,
        procedure_targets=procedure_targets,
        workflow_targets=workflow_targets,
    )


def _check_exception_sibling_locality(
    controls: Sequence[ProtocolReviewControl],
    candidates: Sequence[ProtocolControlCandidate],
) -> None:
    entries: list[tuple[str, str, str, frozenset[str]]] = []
    for control in controls:
        expression = getattr(control, "exception_expression", None)
        if expression is None:
            continue
        fingerprint = _semantic_expression_fingerprint(expression)
        entries.append(("control", control.protocol_control_id, fingerprint, frozenset(control.source_structure_unit_ids)))
    for candidate in candidates:
        semantics = getattr(candidate, "semantics", None)
        expression = getattr(semantics, "exception_expression", None) if semantics else None
        if expression is None:
            continue
        fingerprint = _semantic_expression_fingerprint(expression)
        entries.append(("candidate", candidate.control_candidate_id, fingerprint, frozenset(candidate.frozen_structure_unit_ids)))
    for index, (kind, entity_id, fingerprint, source_units) in enumerate(entries):
        for other_kind, other_id, other_fingerprint, other_units in entries[index + 1 :]:
            if fingerprint == other_fingerprint and source_units.isdisjoint(other_units):
                _fail(
                    "EXCEPTION_SIBLING_COPY",
                    "例外表达式被复制到不相干的 sibling 分支，未保持来源局部性",
                    entity_id=entity_id,
                )


def _uncovered_enrollment_prohibitions(
    batch: ProtocolControlDispositionBatch,
    output: ProtocolControlBatchDispositionHydrated,
) -> tuple[ProtocolControlGateError, ...]:
    """Stop explicit stage-scoped prohibitions from vanishing as no-op rows."""

    by_unit = {item.structure_unit_id: item for item in output.dispositions}
    by_candidate = {item.control_candidate_id: item for item in getattr(output, "candidates", ())}
    issues: list[ProtocolControlGateError] = []
    for unit in batch.owned_units:
        disposition = by_unit.get(unit.structure_unit_id)
        if disposition is None:
            continue
        if disposition.disposition == StructureUnitDispositionKind.PHASE_EXCLUDED:
            continue
        table_context = getattr(unit, "table_context", None)
        headings = list(getattr(unit, "heading_path", ())[-2:])
        if table_context is not None:
            headings.extend(getattr(table_context, "row_headers", ()))
            headings.extend(getattr(table_context, "column_headers", ()))
        stage_in_context = bool(_ENROLLMENT_STAGE_RE.search(" ".join(headings)))
        clauses = [
            clause.strip()
            for clause in re.split(r"[。；;\n]", unit.excerpt)
            if _ENROLLMENT_PROHIBITION_RE.search(clause)
            or (
                stage_in_context
                and _PROHIBITION_WORD_RE.search(clause)
                and not _POST_ENROLLMENT_RE.search(clause)
            )
        ]
        # A linked candidate does not settle a second, separately quoted
        # requirement. Only an exact atom-level quote proves partial coverage;
        # broader semantic coverage remains for the source review, not regex.
        quoted_clauses: set[str] = set()
        split_atoms: list[object] = []
        if disposition.linked_control_candidate_ids:
            for candidate_id in disposition.linked_control_candidate_ids:
                candidate = by_candidate.get(candidate_id)
                semantics = getattr(candidate, "semantics", None)
                if semantics is None:
                    continue
                for group in semantics.obligation_expression.groups:
                    for atom in group.atoms:
                        split_atoms.append(atom)
                        statement = _normalize_prohibition_quote(getattr(atom, "statement", ""))
                        for quote in atom.source_excerpts:
                            if not isinstance(quote, str):
                                continue
                            for sentence in re.split(r"[。；;\n]", quote):
                                normalized = _normalize_prohibition_quote(sentence)
                                if normalized and (
                                    normalized == statement
                                    or _normalize_prohibition_quote(quote) == normalized
                                ):
                                    quoted_clauses.add(normalized)
        for clause in clauses:
            quote = clause.strip()
            normalized_quote = _normalize_prohibition_quote(quote)
            if normalized_quote in quoted_clauses or any(
                _split_prohibition_atom_covers_clause(normalized_quote, atom)
                for atom in split_atoms
            ):
                continue
            linked_official = getattr(disposition, "linked_official_code", None)
            linked_procedures = set(
                getattr(disposition, "linked_procedure_catalog_item_ids", ()) or ()
            )
            single_procedure = getattr(disposition, "linked_procedure_catalog_item_id", None)
            if single_procedure:
                linked_procedures.add(single_procedure)
            linked_targets = (
                target
                for target in (*batch.known_official_targets, *batch.known_procedure_targets)
                if (
                    getattr(target, "official_code", None) == linked_official
                    and linked_official is not None
                ) or getattr(target, "catalog_item_id", None) in linked_procedures
            )
            if any(
                any(
                    normalized_quote in _normalize_prohibition_quote(target_quote)
                    and (
                        bool(set(unit.source_span_ids) & set(target.source_span_ids))
                        or (
                            linked_official is not None
                            and getattr(target, "official_code", None) == linked_official
                            and getattr(unit, "unit_kind", None) == "table_row"
                            and any("摘要" in heading for heading in getattr(unit, "heading_path", ()))
                            and "排除标准" in getattr(getattr(unit, "table_context", None), "row_headers", ())
                            and _normalize_prohibition_quote(unit.excerpt)
                            == _normalize_prohibition_quote(target_quote)
                        )
                    )
                    for target_quote in target.source_excerpts
                    if isinstance(target_quote, str)
                )
                for target in linked_targets
            ):
                continue
            issues.append(
                ProtocolControlGateError(
                    "ENROLLMENT_PROHIBITION_UNCOVERED",
                    "冻结原文含当前入排阶段的禁止性要求，但该句未获独立来源绑定的候选，"
                    "也没有同句逐字来源证明已由正式条款或流程事项覆盖；须按原文核对，不能仅凭同段其他候选省略。",
                    entity_id=unit.structure_unit_id,
                    structure_unit_ids=[unit.structure_unit_id],
                    obligation_source_span_ids=unit.source_span_ids,
                )
            )
            break
    return tuple(issues)


def check_protocol_control_batch_candidates(
    batch: ProtocolControlDispositionBatch,
    output: ProtocolControlBatchDispositionHydrated,
) -> tuple[ProtocolControlGateError, ...]:
    """Report one independent finding per candidate without changing the gate.

    Batch identity and cross-candidate checks still stop at their first error.
    Findings are diagnostic only; no candidate is accepted until every gate passes.
    """

    try:
        if output.batch_id != batch.batch_id:
            _fail("BATCH_ID_MISMATCH", "深析结果未绑定当前冻结批次")
        if output.coverage_manifest_id != batch.coverage_manifest_id:
            _fail("MANIFEST_ID_MISMATCH", "深析结果未绑定当前全文覆盖清单")
        if output.owned_structure_unit_ids != batch.owned_structure_unit_ids:
            _fail("BATCH_SCOPE_MISMATCH", "深析结果未闭合到当前批次的 owned 结构单元")
        if output.owned_source_span_ids != batch.owned_source_span_ids:
            _fail("BATCH_SCOPE_MISMATCH", "深析结果未闭合到当前批次的来源范围")
    except ProtocolControlGateError as error:
        return (error,)

    unit_by_id = {unit.structure_unit_id: unit for unit in batch.owned_units}
    allowed_span_ids = set(batch.owned_source_span_ids)
    candidate_ids = _ids(output.candidates, "control_candidate_id")
    candidate_id_set = set(candidate_ids)
    official_codes = {
        target.official_code for target in batch.known_official_targets
    }
    procedure_ids = {
        target.catalog_item_id for target in batch.known_procedure_targets
    }
    issues: list[ProtocolControlGateError] = []
    issues.extend(_uncovered_enrollment_prohibitions(batch, output))
    for candidate in output.candidates:
        try:
            _validate_candidate(
                candidate,
                unit_by_id=unit_by_id,
                allowed_span_ids=allowed_span_ids,
                workflow_targets=batch.known_workflow_stage_targets,
                procedure_targets=batch.known_procedure_targets,
                official_codes=official_codes,
                procedure_ids=procedure_ids,
                candidate_ids=candidate_id_set,
            )
        except ProtocolControlGateError as error:
            issues.append(error)
    if issues:
        return tuple(issues)
    try:
        _check_conditional_exemption_scope_split(
            output.candidates,
            unit_by_id=unit_by_id,
            candidate_scope=True,
        )
    except ProtocolControlGateError as error:
        return (error,)
    return ()


def validate_protocol_control_batch_candidates(
    batch: ProtocolControlDispositionBatch,
    output: ProtocolControlBatchDispositionHydrated,
) -> ProtocolControlBatchDispositionHydrated:
    """Require all batch candidates to pass before full publication validation."""

    issues = check_protocol_control_batch_candidates(batch, output)
    if issues:
        raise issues[0]
    return output


def validate_protocol_control_publication(
    coverage_manifest: ProtocolSectionCoverageManifest,
    catalog: PublishedProtocolControlCatalog,
    plan: ProtocolControlBatchPlan | None = None,
    batch_dispositions: Sequence[ProtocolControlBatchDispositionHydrated] = (),
    *,
    candidates: Sequence[ProtocolControlCandidate] = (),
    official_targets: Sequence[KnownOfficialRuleTarget] = (),
    procedure_targets: Sequence[KnownRequiredProcedureTarget] = (),
    workflow_stage_targets: Sequence[KnownWorkflowStageTarget] = (),
    rule_component_ids: Sequence[str] = (),
    phase_applicability_view: FullProtocolCoverageResolutionView | None = None,
) -> PublishedProtocolControlCatalog:
    """Validate one complete control publication and return it unchanged.

    New 5.8b/5.8c publication is authorized only by a complete frozen plan and
    one complete system-hydrated result per planned batch.  When supplied,
    ``phase_applicability_view`` is the separate semantic resolution view over
    the same frozen manifest; it never rewrites source phase scopes.  The
    legacy manifest disposition fields and caller-supplied candidate list are
    audit inputs at most; neither can bypass the Agent disposition chain.
    """

    if not isinstance(coverage_manifest, ProtocolSectionCoverageManifest):
        _fail("INPUT_TYPE_INVALID", "全文覆盖清单类型不正确")
    if not isinstance(catalog, PublishedProtocolControlCatalog):
        _fail("INPUT_TYPE_INVALID", "catalog 类型不正确")
    unit_by_id, manifest_span_ids = _manifest_units(coverage_manifest)
    allowed_span_ids = _check_catalog_identity(catalog, coverage_manifest, manifest_span_ids)

    disposition_by_unit, plan_candidates = _check_plan_and_batch_results(
        coverage_manifest,
        plan,
        batch_dispositions,
    )
    if candidates:
        _fail(
            "STANDALONE_CANDIDATES_NOT_ALLOWED",
            "发布候选必须来自完整水合批次结果，不得由调用方另行注入",
        )
    # Result-derived disposition is authoritative.  Resolve UNKNOWN/MIXED only
    # after complete batch disposition so the phase stop is stable and cannot
    # be bypassed by an older manifest completion claim.
    phase_disposition_by_unit = _check_phase_applicability(
        coverage_manifest,
        unit_by_id,
        resolved_view=phase_applicability_view,
    )
    for unit_id, phase_disposition in phase_disposition_by_unit.items():
        actual_disposition = disposition_by_unit[unit_id].disposition
        if (
            phase_disposition
            == PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
            and actual_disposition != StructureUnitDispositionKind.PHASE_EXCLUDED
        ):
            _fail(
                "PHASE_EXCLUDED_DISPOSITION_REQUIRED",
                "对侧期别结构单元必须明确标记为当前期别不适用",
                entity_id=unit_id,
            )
        if (
            phase_disposition
            != PhaseApplicabilityDisposition.OPPOSITE_PHASE_APPLICABLE
            and actual_disposition == StructureUnitDispositionKind.PHASE_EXCLUDED
        ):
            _fail(
                "PHASE_EXCLUDED_DISPOSITION_CONFLICT",
                "当前期别或跨期共享结构单元不得标记为当前期别不适用",
                entity_id=unit_id,
            )
    _check_legacy_manifest_compatibility(coverage_manifest, disposition_by_unit)

    all_candidates = plan_candidates
    candidate_ids = _ids(all_candidates, "control_candidate_id") if all_candidates else []
    if len(candidate_ids) != len(set(candidate_ids)):
        _fail("CANDIDATE_ID_DUPLICATE", "控制候选身份不得重复")
    candidate_id_set = set(candidate_ids)
    if plan is not None:
        owned_batch_by_unit: dict[str, str] = {}
        for batch in plan.batches:
            for unit_id in batch.owned_structure_unit_ids:
                owned_batch_by_unit[unit_id] = batch.batch_id
        for candidate in all_candidates:
            source_batches = {
                owned_batch_by_unit.get(unit_id)
                for unit_id in candidate.frozen_structure_unit_ids
            }
            if None in source_batches or len(source_batches) != 1:
                _fail(
                    "CANDIDATE_BATCH_SCOPE_ESCAPE",
                    "候选来源结构单元必须全部属于同一冻结批次",
                    entity_id=candidate.control_candidate_id,
                )
    for candidate in all_candidates:
        for unit_id in candidate.frozen_structure_unit_ids:
            disposition = disposition_by_unit.get(unit_id)
            if disposition is None:
                _fail(
                    "CANDIDATE_SOURCE_UNIT_UNKNOWN",
                    "候选来源结构单元未进入全文处置清单",
                    entity_id=candidate.control_candidate_id,
                )
            if _value(getattr(disposition, "disposition", None)) != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value:
                _fail(
                    "CANDIDATE_SOURCE_UNIT_NOT_CANDIDATE",
                    "候选来源结构单元必须处置为其他控制候选",
                    entity_id=candidate.control_candidate_id,
                )
    official, procedure, workflow = _resolve_targets(
        plan,
        official_targets=official_targets,
        procedure_targets=procedure_targets,
        workflow_stage_targets=workflow_stage_targets,
    )
    official_codes = {item.official_code for item in official}
    procedure_ids = {item.catalog_item_id for item in procedure}
    if all_candidates:
        for candidate in all_candidates:
            _validate_candidate(
                candidate,
                unit_by_id=unit_by_id,
                allowed_span_ids=allowed_span_ids,
                workflow_targets=workflow,
                procedure_targets=procedure,
                official_codes=official_codes,
                procedure_ids=procedure_ids,
                candidate_ids=candidate_id_set,
            )
        _check_conditional_exemption_scope_split(
            all_candidates,
            unit_by_id=unit_by_id,
            candidate_scope=True,
        )

    controls = list(getattr(catalog, "controls", ()))
    control_ids = _ids(controls, "protocol_control_id") if controls else []
    ordinals = [getattr(control, "display_ordinal", None) for control in controls]
    if any(not isinstance(ordinal, int) or ordinal < 1 for ordinal in ordinals):
        _fail("CONTROL_ORDINAL_INVALID", "方案控制展示顺序必须是正整数")
    if len(ordinals) != len(set(ordinals)) or ordinals != sorted(ordinals):
        _fail("CONTROL_ORDINAL_INVALID", "方案控制必须按唯一展示顺序排列")
    if controls and not workflow:
        _fail("WORKFLOW_STAGE_TARGETS_MISSING", "存在可发布控制但计划未携带冻结流程节点")
    for control in controls:
        _validate_control(
            control,
            unit_by_id=unit_by_id,
            allowed_span_ids=allowed_span_ids,
            workflow_targets=workflow,
            procedure_targets=procedure,
            official_codes=official_codes,
            procedure_ids=procedure_ids,
            control_ids=set(control_ids),
            candidate_ids=candidate_id_set,
            rule_component_ids=set(rule_component_ids),
        )
        source_units = set(control.source_structure_unit_ids)
        for unit_id in source_units:
            disposition = disposition_by_unit.get(unit_id)
            if disposition is None:
                _fail("SOURCE_UNIT_SCOPE_ESCAPE", "控制来源结构单元未处置", entity_id=control.protocol_control_id)
            if _value(getattr(disposition, "disposition", None)) != StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value:
                _fail(
                    "CONTROL_SOURCE_UNIT_NOT_CANDIDATE",
                    "发布控制的来源结构单元必须处置为其他控制候选",
                    entity_id=control.protocol_control_id,
                )
        originating = getattr(control, "originating_candidate_id", None)
        if originating is not None and originating not in candidate_id_set:
            _fail("UNKNOWN_CANDIDATE_TARGET", "正式控制引用了未知候选身份", entity_id=control.protocol_control_id)
        if originating is not None:
            candidate = next(item for item in all_candidates if item.control_candidate_id == originating)
            if set(candidate.frozen_structure_unit_ids) != source_units:
                _fail("CANDIDATE_CONTROL_SCOPE_MISMATCH", "正式控制与起源候选来源范围不一致", entity_id=control.protocol_control_id)
    _check_conditional_exemption_scope_split(
        controls,
        unit_by_id=unit_by_id,
        candidate_scope=False,
    )
    _check_exception_sibling_locality(controls, all_candidates)
    return catalog


def publish_protocol_control_catalog(
    catalog: PublishedProtocolControlCatalog,
    coverage_manifest: ProtocolSectionCoverageManifest,
    plan: ProtocolControlBatchPlan | None = None,
    batch_dispositions: Sequence[ProtocolControlBatchDispositionHydrated] = (),
    **kwargs: Any,
) -> PublishedProtocolControlCatalog:
    """Publication-shaped alias that keeps the gate as the only write boundary."""

    return validate_protocol_control_publication(
        coverage_manifest,
        catalog,
        plan,
        batch_dispositions,
        **kwargs,
    )


def validate_protocol_control_catalog(
    catalog: PublishedProtocolControlCatalog,
    coverage_manifest: ProtocolSectionCoverageManifest,
    plan: ProtocolControlBatchPlan | None = None,
    batch_dispositions: Sequence[ProtocolControlBatchDispositionHydrated] = (),
    **kwargs: Any,
) -> PublishedProtocolControlCatalog:
    return validate_protocol_control_publication(
        coverage_manifest,
        catalog,
        plan,
        batch_dispositions,
        **kwargs,
    )


def validate_protocol_control_gate(*args: Any, **kwargs: Any) -> PublishedProtocolControlCatalog:
    return validate_protocol_control_publication(*args, **kwargs)


gate_protocol_control_publication = validate_protocol_control_publication


def check_protocol_control_publication(*args: Any, **kwargs: Any) -> ProtocolControlGateReport:
    """Return a bounded report without converting rejection into acceptance."""

    try:
        validate_protocol_control_publication(*args, **kwargs)
    except ProtocolControlGateError as exc:
        return ProtocolControlGateReport(
            accepted=False,
            gate_version=CONTROL_PUBLICATION_GATE_VERSION,
            issues=(
                ProtocolControlGateIssue(
                    exc.code,
                    str(exc),
                    exc.entity_id,
                    exc.structure_unit_ids,
                    exc.candidate_ids,
                    exc.obligation_source_span_ids,
                ),
            ),
        )
    return ProtocolControlGateReport(
        accepted=True,
        gate_version=CONTROL_PUBLICATION_GATE_VERSION,
    )
