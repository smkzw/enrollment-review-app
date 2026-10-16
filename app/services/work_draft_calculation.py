"""Deterministic working results from frozen variable bindings and original facts."""
from dataclasses import dataclass
from calendar import isleap
from datetime import date
from hashlib import sha256
import re
import unicodedata
from app.domain.contracts.enums import AnchorType, ComponentDecision as D, ReviewStage, RuleKind, TruthValue
from app.domain.contracts.rules import AtomicExpression, RuleComponent, iter_atomic_predicates
from app.domain.contracts.work_draft import SystemIssue, WorkDraftItem, WorkDraftReasonPart
from app.domain.expression import EvaluationContext, _evaluate_time, _compare
from app.domain.policies import STAGE_RANK
from app.domain.publication import canonical_hash
from app.domain.risk_flags import RiskFlag
from app.domain.variables.dictionary import load_dictionary
from app.services.component_review import calculate_component_review
from app.services.eligibility_review_projection import adapt_clinical_fact_v2


DETERMINATE = {D.INCLUSION_MET, D.INCLUSION_NOT_MET, D.EXCLUSION_TRIGGERED,
               D.EXCLUSION_NOT_TRIGGERED, D.REQUIREMENT_MET, D.REQUIREMENT_NOT_MET}
LABELS = {D.INCLUSION_MET: "满足", D.INCLUSION_NOT_MET: "不满足",
          D.EXCLUSION_TRIGGERED: "已触发", D.EXCLUSION_NOT_TRIGGERED: "未触发",
          D.REQUIREMENT_MET: "满足", D.REQUIREMENT_NOT_MET: "不满足",
          D.INDETERMINATE: "证据不足", D.PROFESSIONAL_JUDGMENT: "需研究者判断",
          D.CONFLICT: "资料矛盾", D.NOT_DUE: "未到期", D.NOT_APPLICABLE: "不适用"}

_RISK_REASONS = {
    RiskFlag.NEAR_THRESHOLD: "临近阈值", RiskFlag.HANDWRITTEN: "手写内容",
    RiskFlag.LOW_OCR_CONFIDENCE: "识别可能有误", RiskFlag.DATE_ROLE_UNCLEAR: "日期含义不清",
    RiskFlag.UNIT_INFERRED: "单位为推定", RiskFlag.PARTIAL_DATE: "日期不完整",
    RiskFlag.PRESCRIPTION_ONLY: "仅有处方记录", RiskFlag.SINGLE_WEAK_SOURCE: "来源较弱",
    RiskFlag.IMPLAUSIBLE_VALUE: "数值不合理，请核对原件", RiskFlag.ATTRIBUTION_UNCERTAIN: "数值归属需核对",
}


def _risk_reason(facts):
    flags = {flag for fact in facts for flag in fact.risk_flags}
    return next((label for flag, label in _RISK_REASONS.items() if flag in flags), None)


def atomic_expressions(expression):
    if isinstance(expression, AtomicExpression):
        yield expression
    else:
        for operand in expression.children:
            yield from atomic_expressions(operand)


def positive_event_predicate_ids(expression, negated=False):
    """Keep absence policy on positive event leaves, never a negated or exception leaf."""
    if isinstance(expression, AtomicExpression):
        predicate = expression.predicate
        return {predicate.predicate_id} if not negated and (predicate.comparator.value == "exists"
            or predicate.comparator.value == "eq" and predicate.value is True) else set()
    return set().union(*(positive_event_predicate_ids(child, not negated if expression.operator.value == "not" else negated)
                         for child in expression.children))


def verified_population_scope(row, predicate, source_text):
    """A reader's applicability needs both the rule scope and subject evidence."""
    excerpt = row.get("population_scope_excerpt")
    return bool(row.get("applicable") == "no" and not row.get("conflict")
        and any(ref.get("excerpt") for ref in row.get("source_read_refs", ()))
        and (predicate.get("applicable_population")
            or isinstance(excerpt, str) and excerpt.strip() and excerpt in source_text))


def is_numeric_history_condition(predicate, definition):
    return (definition is not None and definition.value_type == "number"
        and definition.domain in {"history", "medication"}
        and not predicate.source_computation and not predicate.repeat_scheme)


def applicable_expression(expression, excluded_predicates):
    """Build a calculation-only tree; inapplicable atoms are not TRUE or FALSE."""
    if expression is None:
        return None
    if isinstance(expression, AtomicExpression):
        return None if expression.predicate.predicate_id in excluded_predicates else expression
    children = [active for child in expression.children
                if (active := applicable_expression(child, excluded_predicates)) is not None]
    if not children:
        return None
    if len(children) == 1 and expression.operator.value != "not":
        return children[0]
    return expression.model_copy(update={"children": children})


def binding_preserves_source_requirement(original, bound):
    excluded = {"requirement_id", "variable_id", "predicate_ids"}
    # An original without a source-type restriction permits a stricter binding,
    # not the reverse; every other source policy must still match exactly.
    if not original.required_source_types:
        excluded.add("required_source_types")
    return original.model_dump(exclude=excluded) == bound.model_dump(exclude=excluded)


def independent_source_requirements(component):
    """Unbound source requirements are records to check, never inferred predicates."""
    independent = []
    for req in component.evidence_requirements:
        if req.variable_id is not None or req.predicate_ids:
            continue
        bindings = [bound for bound in component.evidence_requirements if
            bound.variable_id is not None and len(bound.predicate_ids) == 1
            and bound.requirement_id == "variable_requirement:" + sha256(":".join((
                component.rule_component_id, bound.predicate_ids[0], req.requirement_id)).encode()).hexdigest()[:32]]
        if not bindings or not all(binding_preserves_source_requirement(req, bound) for bound in bindings):
            independent.append(req)
    return independent


@dataclass(frozen=True)
class VariableSelection:
    fact_ids: tuple[str, ...]
    considered_fact_ids: tuple[str, ...] = ()
    conflict: bool = False
    date_uncertain: bool = False
    calculation_unverified_ids: tuple[str, ...] = ()
    chronology_conflict: bool = False
    age_consensus: TruthValue | None = None


def source_record_date(fact, evidence_refs, source_pages, *, allow_report_date=False, date_role=None,
                       allow_exam_date=False):
    """Explicit visit/sample headers may exclude future records, not date an event."""
    pages = {(page.source_document_version_id, page.page_number, page.page_artifact_id): page for page in source_pages}
    labels = [{"sampling": "采样时间", "visit": "就诊时间"}.get(date_role, "采样时间|就诊时间")]
    if allow_exam_date and date_role is None:
        labels.append("检查日期|检查时间|摄片日期")
    labels += ["报告日期|报告时间"] if allow_report_date else []
    texts = [page.effective_text for ref in (evidence_refs or {}).get(fact.fact_id, ())
        if (page := pages.get((ref.source_document_version_id, ref.page_number, ref.page_artifact_id))) is not None]
    return source_header_date(texts, labels)


def source_header_date(texts, label_groups):
    """Use explicit header roles in priority order; ambiguous or invalid dates stay unknown."""
    header = re.compile(r"\s*(" + "|".join(label_groups) + r")\s*[:：]\s*"
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?")
    fields = []
    for text in texts:
        for first in re.finditer(r"(?m)^" + header.pattern, text):
            fields.append(first.groups())
            offset = first.end()
            # Continue only across complete adjacent date fields. A narrative,
            # appointment prefix or arbitrary text is not a header boundary.
            while match := header.match(text, offset):
                fields.append(match.groups())
                offset = match.end()
    for label in label_groups:
        values = set()
        for role, *parts in fields:
            if re.fullmatch(label, role):
                try:
                    values.add(date(*(int(value) for value in parts)))
                except ValueError:
                    return None
        if values:
            return next(iter(values)) if len(values) == 1 else None
    return None


def age_record_chronology(facts, evidence_refs, source_pages, definition, predicate):
    """Compare dated age readings without inventing an event date or birth date."""
    from app.domain.contracts.enums import FactPolarity
    dates, readings = {}, []
    for fact in facts:
        if fact.polarity != FactPolarity.AFFIRMED:
            continue
        explicit = (fact.date_range.lower_bound if fact.date_range is not None
            and fact.date_range.precision.value == "day" and fact.date_role in {"sampling", "visit"} else None)
        document_date = source_record_date(fact, evidence_refs, source_pages,
            date_role=fact.date_role if explicit is not None else None, allow_exam_date=True)
        if explicit is not None and document_date is not None and explicit != document_date:
            return dates, True
        recorded = explicit or document_date or source_record_date(
            fact, evidence_refs, source_pages, allow_report_date=True, allow_exam_date=True)
        if recorded is not None:
            dates[fact.fact_id] = recorded
            value, _ = comparison_reading(fact, definition, predicate)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer():
                readings.append((recorded, int(value)))
    readings.sort()
    for index, (earlier, age) in enumerate(readings):
        for later, later_age in readings[index + 1:]:
            if earlier == later:
                # Same-day disagreement is checked against the actual age
                # condition below; it cannot establish a backward chronology.
                continue
            years = later.year - earlier.year
            first_day, last_day = (earlier.month, earlier.day), (later.month, later.day)
            minimum = years - (last_day < first_day)
            maximum = years + (last_day > first_day)
            # Only a February-28 anniversary across a leap-year boundary can
            # shift this bound. Never tolerate an extra year over arbitrary dates.
            if earlier != later and first_day == last_day == (2, 28):
                if not isleap(earlier.year) and isleap(later.year):
                    minimum -= 1
                elif isleap(earlier.year) and not isleap(later.year):
                    maximum += 1
            if not minimum <= later_age - age <= maximum:
                return dates, True
    return dates, False


def review_anchor_dates(anchor_dates, stage):
    """Only an explicit date of this stage can bind an approved node-relative window."""
    result = dict(anchor_dates)
    result.pop(AnchorType.REVIEW_NODE_DATE, None)
    stage_anchor = {ReviewStage.SCREENING: AnchorType.SCREENING_DATE,
                    ReviewStage.BASELINE: AnchorType.BASELINE_DATE}.get(stage)
    if stage_anchor in result:
        result[AnchorType.REVIEW_NODE_DATE] = result[stage_anchor]
    return result


def review_source_cutoff(anchor_dates, stage, evidence_cutoff_date=None):
    """Source availability is separate from protocol-relative time anchors."""
    if evidence_cutoff_date is not None:
        return evidence_cutoff_date
    anchor_type = AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
    anchor = anchor_dates.get(anchor_type)
    return anchor.value if anchor is not None else None


def select_by_variable(component, facts, anchor_dates, *, authority, definitions, stage=ReviewStage.SCREENING, evidence_refs=None, source_pages=(), evidence_cutoff_date=None):
    """Variable identity is explicit; display labels never select clinical evidence."""
    bindings = {}
    for requirement in component.evidence_requirements:
        if requirement.variable_id is not None:
            for predicate_id in requirement.predicate_ids:
                prior = bindings.setdefault(predicate_id, requirement.variable_id)
                if prior != requirement.variable_id:
                    raise ValueError("同一条件对应不同数据项目，暂不能计算")
    base = EvaluationContext(project_id=authority.project_id, subject_id=authority.subject_id,
        review_episode_id=authority.review_episode_id, evidence_snapshot_id=authority.evidence_snapshot_v2_id,
        anchor_dates=review_anchor_dates(anchor_dates, stage))
    result = {}
    for expression in (component.expression, component.exception_expression):
        if expression is None:
            continue
        for atom in atomic_expressions(expression):
            variable_id = bindings.get(atom.predicate.predicate_id)
            definition = definitions.get(variable_id)
            accepted_variables = {variable_id}
            if definition is not None and definition.reference_ratio_of is not None:
                accepted_variables.add(definition.reference_ratio_of)
            is_age = (variable_id == "age" and definition is not None and definition.value_type == "number"
                and definition.domain == "demographic" and definition.canonical_unit == "周岁")
            eligible, chronology_facts = [], []
            invalid_calculations = []
            for fact in facts:
                if (fact.authority.project_id, fact.authority.subject_id, fact.authority.review_episode_id) != (
                        authority.project_id, authority.subject_id, authority.review_episode_id):
                    raise ValueError("事实属于其他项目、受试者或审核节点")
                if variable_id is None or fact.variable_id not in accepted_variables:
                    continue
                from app.domain.contracts.enums import FactPolarity
                if fact.polarity == FactPolarity.UNKNOWN or fact.value is None:
                    continue
                cutoff = review_source_cutoff(anchor_dates, stage, evidence_cutoff_date)
                if cutoff is not None and fact.date_range is not None:
                    lower = fact.date_range.lower_bound
                    if lower is not None and lower > cutoff:
                        continue
                recorded = source_record_date(fact, evidence_refs, source_pages)
                if recorded is not None and cutoff is not None and recorded > cutoff:
                    continue
                if is_age:
                    explicit_age_date = (fact.date_range is not None and fact.date_range.precision.value == "day"
                        and fact.date_role in {"sampling", "visit"})
                    age_recorded = (fact.date_range.lower_bound if explicit_age_date else
                        source_record_date(fact, evidence_refs, source_pages, allow_report_date=True,
                                           allow_exam_date=True))
                    if cutoff is not None and age_recorded is not None and age_recorded > cutoff:
                        continue
                    chronology_facts.append(fact)
                adapted = adapt_clinical_fact_v2(fact)
                temporal = _evaluate_time(atom, adapted, base)
                if temporal.truth in {TruthValue.FALSE, TruthValue.UNKNOWN}:
                    continue
                if definition is not None and definition.reference_ratio_of is not None:
                    try:
                        comparison_reading(fact, definition, atom.predicate, definitions=definitions)
                    except (ValueError, TypeError):
                        invalid_calculations.append(fact.fact_id)
                        continue
                eligible.append(fact)
            def value_key(fact):
                if definition is not None and definition.value_type == "number" and isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool):
                    value, _ = comparison_reading(fact, definition, atom.predicate, definitions=definitions)
                    return fact.polarity.value + ":" + str(value)
                if definition is not None and definition.domain == "lab" and definition.value_type == "category":
                    value, unit = comparison_reading(fact, definition, atom.predicate, definitions=definitions)
                    return canonical_hash({"value": value, "unit": unit, "polarity": fact.polarity.value})
                return canonical_hash({"value": fact.value, "unit": fact.unit, "polarity": fact.polarity.value})
            age_dates, chronology_conflict = (age_record_chronology(chronology_facts, evidence_refs, source_pages,
                definition, atom.predicate) if is_age else ({}, False))
            if chronology_conflict:
                eligible = chronology_facts
            conflict = chronology_conflict
            conflicting_ids = set()
            for index, fact in enumerate(eligible):
                for other in eligible[index + 1:]:
                    same_day = (fact.date_range is not None and other.date_range is not None
                        and fact.date_role == other.date_role == "sampling"
                        and fact.date_range.precision.value == other.date_range.precision.value == "day"
                        and fact.date_range.lower_bound == other.date_range.lower_bound)
                    if is_age and fact.fact_id in age_dates and other.fact_id in age_dates:
                        same_day = age_dates[fact.fact_id] == age_dates[other.fact_id]
                    # A PDF can bundle several reports. Only a shared actual
                    # source position proves that these readings refer to one field.
                    distinct_samples = (fact.date_range is not None and other.date_range is not None
                        and fact.date_role == other.date_role == "sampling"
                        and fact.date_range.precision.value == other.date_range.precision.value == "day"
                        and fact.date_range.lower_bound != other.date_range.lower_bound)
                    same_report = bool(set(fact.locator_ids) & set(other.locator_ids)) and not distinct_samples
                    if (same_day or same_report) and value_key(fact) != value_key(other):
                        conflict = True
                        conflicting_ids.update((fact.fact_id, other.fact_id))
            selection_dates = ({fact.fact_id: age_dates[fact.fact_id] for fact in eligible if fact.fact_id in age_dates}
                if is_age else {fact.fact_id: fact.date_range.lower_bound
                for fact in eligible if fact.date_range is not None and fact.date_range.lower_bound is not None})
            node_anchor = base.anchor_dates.get(AnchorType.REVIEW_NODE_DATE)
            if is_age and node_anchor is not None and node_anchor.value is not None:
                # A later birthday does not change age at the protocol's node date.
                selection_dates = {key: day for key, day in selection_dates.items() if day <= node_anchor.value}
            dated = [fact for fact in eligible if fact.fact_id in selection_dates]
            if dated:
                nearest = max(selection_dates[fact.fact_id] for fact in dated)
                chosen = [fact for fact in dated if selection_dates[fact.fact_id] == nearest]
            else:
                chosen = [] if is_age and age_dates else eligible
            age_consensus = None
            if (is_age and chosen and not chronology_conflict and node_anchor is not None and node_anchor.value is not None
                    and not any((atom.predicate.requires_professional_judgment,
                        atom.predicate.semantic_proposition, atom.predicate.repeat_scheme,
                        atom.predicate.source_computation, atom.predicate.occurrence_window,
                        atom.predicate.observation_policy, atom.predicate.applicable_population,
                        atom.predicate.prospective_period, atom.predicate.prospective_window))
                    and conflicting_ids <= {fact.fact_id for fact in chosen}
                    and not any(fact.fact_id not in age_dates
                        and value_key(fact) not in {value_key(row) for row in chosen} for fact in eligible)
                    and all(fact.fact_id in age_dates and fact.polarity.value == "affirmed"
                        and float(comparison_reading(fact, definition, atom.predicate)[0]).is_integer() for fact in chosen)
                    and len({value_key(fact) for fact in chosen}) > 1):
                predicate = atom.predicate.model_copy(deep=True)
                expected = predicate.value if isinstance(predicate.value, list) else [predicate.value]
                if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in expected):
                    normalized = [float(definition.convert(value, predicate.unit or definition.canonical_unit))
                        for value in expected]
                    predicate.value = normalized if isinstance(predicate.value, list) else normalized[0]
                    truths = {_compare(predicate, comparison_reading(fact, definition, predicate)[0]) for fact in chosen}
                    if len(truths) == 1 and TruthValue.UNKNOWN not in truths:
                        age_consensus = truths.pop()
                        conflict = False
            undated_choice_unclear = not conflict and not dated and len({value_key(fact) for fact in chosen}) > 1
            if undated_choice_unclear:
                chosen = []
            undated_age_difference = is_age and dated and any(
                fact.fact_id not in age_dates and value_key(fact) not in {value_key(row) for row in chosen}
                for fact in eligible)
            result[atom.predicate.predicate_id] = VariableSelection(
                tuple(sorted(fact.fact_id for fact in (eligible if conflict else chosen))),
                tuple(sorted(fact.fact_id for fact in eligible)), conflict,
                undated_choice_unclear or bool(undated_age_difference) or ((not base.anchor_dates.get(AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE)
                 or base.anchor_dates[AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE].value is None
                 or any(fact.date_range is None or fact.date_range.precision.value != "day"
                    or fact.date_role not in {"sampling", "visit"} for fact in chosen)
                 )
                if atom.time_constraint or definition is not None and definition.domain in {"lab", "vital", "score", "procedure"} else False),
                tuple(sorted(invalid_calculations)), chronology_conflict, age_consensus)
    return result


def _issue(code, detail):
    return SystemIssue(kind="method_unsupported", affected_codes=[code],
        detail=detail, alternative="请对照本条方案原文和已有资料核对；其余独立要求仍可查看。")


def comparison_reading(fact, definition, predicate, *, definitions=None):
    """Use an explicit qualitative lab label, never derive it from a numeric threshold."""
    value, unit = fact.value, fact.unit
    if definition.value_type == "number":
        if definition.reference_ratio_of is not None and fact.variable_id == definition.reference_ratio_of:
            from decimal import Decimal
            from app.domain.risk_flags import reference_upper_bound
            base = (definitions or {}).get(definition.reference_ratio_of)
            if base is None or fact.assertion_basis is None or not any(
                    label.casefold() in fact.asserted_object.casefold() for label in [base.label_zh, *base.aliases_zh]):
                raise ValueError("原始项目与倍数计算要求没有明确对应")
            base.convert(value, unit or "")
            return float(Decimal(str(value)) / reference_upper_bound(fact)), definition.canonical_unit
        return float(definition.convert(value, unit or "")), definition.canonical_unit
    expected = predicate.value if isinstance(predicate.value, list) else [predicate.value]
    if definition.domain == "lab" and definition.value_type == "category" and any(
            item in {"阳性", "阴性"} for item in expected if isinstance(item, str)):
        from app.domain.contracts.enums import FactPolarity
        if not isinstance(value, str) or fact.polarity != FactPolarity.AFFIRMED:
            raise ValueError("检验定性结果未明确")
        literal = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
        # Explicit non-detection is a reported qualitative result, not a
        # negative inferred from a concentration or a quantification limit.
        if literal in {"未检出", "未检测到靶基因"}:
            return "阴性", "unitless"
        match = re.fullmatch(r"(?:[<>≤≥=]?\d+(?:\.\d+)?)?(?:(阳性|阴性)(?:\(([+-])\))?|\((阳性|阴性)(?:\(([+-])\))?\))", literal)
        if match is None:
            raise ValueError("检验定性结果包含未核实或相互矛盾的文字")
        label, sign = match[1] or match[3], match[2] or match[4]
        if sign and sign != ("+" if label == "阳性" else "-"):
            raise ValueError("检验定性结果包含未核实或相互矛盾的文字")
        # The requested comparison concerns the literal qualitative label. The
        # original quantitative reading/unit remain unchanged in the saved fact.
        return label, "unitless"
    return value, unit


def absence_policy(clause, frozen, definitions):
    """R-C6 operates on the supplied, fully read scope; never creates a negative fact."""
    if clause.kind != RuleKind.EXCLUSION:
        return None
    variables = {item.variable_id for item in clause.evidence_requirements if item.variable_id}
    if not variables or any(key not in definitions or definitions[key].domain != "history" for key in variables):
        return None
    if any(fact.variable_id in variables for fact in frozen.facts):
        return None
    pages = getattr(frozen, "source_pages", ())
    if not pages or any(not page.extraction_complete for page in pages):
        return None
    predicates = [predicate for expression in (clause.expression, clause.exception_expression)
                  if expression is not None for predicate in iter_atomic_predicates(expression)]
    from app.domain.contracts.enums import Comparator, TimeDirection
    # A broad history category also contains consent and current status. Only an
    # explicit, positive historical-event condition qualifies for absence policy.
    atoms = [atom for expression in (clause.expression, clause.exception_expression)
             if expression is not None for atom in atomic_expressions(expression)]
    if (clause.exception_expression is not None or not atoms
            or {atom.predicate.predicate_id for atom in atoms} != positive_event_predicate_ids(clause.expression)) or any(
        atom.time_constraint is None or atom.time_constraint.direction != TimeDirection.BEFORE
        or atom.predicate.comparator not in {Comparator.EXISTS, Comparator.EQ}
        or atom.predicate.comparator == Comparator.EQ and atom.predicate.value is not True
        for atom in atoms):
        return None
    if any(predicate.requires_professional_judgment or predicate.source_computation or predicate.repeat_scheme
           or predicate.prospective_window or predicate.occurrence_window for predicate in predicates):
        return None
    import unicodedata
    normalize = lambda value: unicodedata.normalize("NFKC", value).casefold()
    terms = {term for key in variables for term in [definitions[key].label_zh, *definitions[key].aliases_zh] if term}
    terms.update(predicate.source_term for predicate in predicates if predicate.source_term)
    if any(normalize(term) in normalize(page.effective_text) for term in terms for page in pages):
        return "mentioned"
    has_history = any(page.document_category in {"historical_record", "study_chart", "screening_transcription"} for page in pages)
    count = len({page.source_document_version_id for page in pages})
    return count, has_history


def calculate_work_component(clause, frozen, rule_set, *, evidence_refs, source_results=None):
    from app.storage.repositories import ScopeViolationError
    if any((fact.authority.project_id, fact.authority.subject_id, fact.authority.review_episode_id) != (
            frozen.authority.project_id, frozen.authority.subject_id, frozen.authority.review_episode_id) for fact in frozen.facts):
        raise ScopeViolationError("事实属于其他项目、受试者或审核节点")
    component = RuleComponent(rule_component_id=clause.rule_component_id, parent_rule_id=clause.rule_id,
        display_code=clause.display_code, title=clause.title, expression=clause.expression,
        exception_expression=clause.exception_expression, repeat_trigger_conditions=clause.repeat_trigger_conditions,
        evidence_requirements=clause.evidence_requirements)
    definitions = load_dictionary(rule_set.variable_definitions or ())
    bound_variables = {req.variable_id for req in component.evidence_requirements if req.variable_id}
    bound_variables.update(definitions[key].reference_ratio_of for key in tuple(bound_variables)
        if key in definitions and definitions[key].reference_ratio_of is not None)
    input_hash = canonical_hash({"clause": clause.model_dump(mode="json"),
        "evaluator_version": getattr(frozen, "evaluator_version", None),
        "facts": [fact.model_dump(mode="json") for fact in frozen.facts
                  if fact.variable_id in bound_variables],
        "calculations": [definitions[key].model_dump(mode="json") for key in sorted(bound_variables) if key in definitions],
        "anchors": frozen.review_episode.model_dump(mode="json")["anchor_dates"],
        **({"evidence_cutoff_date": frozen.review_episode.evidence_cutoff_date.isoformat()}
            if frozen.review_episode.evidence_cutoff_date is not None else {})})
    input_hash = canonical_hash({"calculation_input": input_hash,
        "source_pages": [(page.source_document_version_id, page.page_artifact_id, page.effective_text_sha256)
                         for page in getattr(frozen, "source_pages", ())],
        "references": {key: [ref.model_dump(mode="json") for ref in values] for key, values in evidence_refs.items()}})
    common = dict(item_id=f"{frozen.review_run_id}:{clause.rule_component_id}",
        review_run_id=frozen.review_run_id, official_code=clause.official_code,
        rule_component_id=clause.rule_component_id, rule_kind=clause.kind,
        title=clause.title, source_text=clause.source_text, input_hash=input_hash)
    available = [fact for fact in frozen.facts if fact.variable_id in bound_variables]
    available_refs = [ref for fact in available for ref in evidence_refs.get(fact.fact_id, ())]
    due = [req for req in component.evidence_requirements
           if STAGE_RANK[req.due_stage] <= STAGE_RANK[frozen.review_episode.stage]]
    if component.evidence_requirements and not due:
        return WorkDraftItem(**common, decision=D.NOT_DUE, reason_text="本条要求属于后续审核节点。")
    predicates = [predicate for expression in (component.expression, component.exception_expression)
                  if expression is not None for predicate in iter_atomic_predicates(expression)]
    records = {req.requirement_id: source_results[f"requirement:{clause.rule_component_id}:{req.requirement_id}"]
        for req in independent_source_requirements(component) if req in due and source_results
        and f"requirement:{clause.rule_component_id}:{req.requirement_id}" in source_results}
    has_source_relations = bool(records or source_results and any(
        f"{clause.rule_component_id}:{p.predicate_id}" in source_results for p in predicates))
    policy = None if has_source_relations else absence_policy(clause, frozen, definitions)
    if policy == "mentioned":
        return WorkDraftItem(**common, decision=D.INDETERMINATE,
            reason_text="本次资料中有相关字样，但尚未形成可用于本条的记录，请核对具体原文。")
    if policy is not None:
        count, history = policy
        return WorkDraftItem(**common, decision=D.EXCLUSION_NOT_TRIGGERED,
            confidence="high" if history else "low",
            confidence_reason=None if history else "本次资料范围内没有病历或既往史类资料。",
            reason_text=f"本次资料（{count}份）未见相关记录；仅限已提供且已读取的范围。",
            policy_group="not_seen_in_supplied_records")
    relations = {p.predicate_id: source_results[f"{clause.rule_component_id}:{p.predicate_id}"]
                 for p in predicates if source_results and f"{clause.rule_component_id}:{p.predicate_id}" in source_results}
    policy_predicates = positive_event_predicate_ids(clause.expression) - {
        predicate.predicate_id for predicate in iter_atomic_predicates(clause.exception_expression)} if clause.exception_expression else positive_event_predicate_ids(clause.expression)
    relations = {key: {**row, "truth": TruthValue.UNKNOWN.value, "policy": False,
            "reason": "本条含否定、例外或其他非事件条件，未见记录不能替代这些条件的核实。"}
                if row["policy"] and key not in policy_predicates else row for key, row in relations.items()}
    from app.domain.contracts.work_draft import WorkDraftSourceRef
    source_refs = [WorkDraftSourceRef.model_validate(ref) for row in (*relations.values(), *records.values())
                   for ref in row.get("source_read_refs", ())]
    common["source_read_refs"] = source_refs
    common["input_hash"] = canonical_hash({"calculation_input": input_hash,
        "source_relations": relations, "source_requirements": records})
    try:
        selection = select_by_variable(component, frozen.facts, frozen.review_episode.anchor_dates,
            authority=frozen.authority, definitions=definitions, stage=frozen.review_episode.stage,
            evidence_refs=evidence_refs, source_pages=getattr(frozen, "source_pages", ()),
            evidence_cutoff_date=frozen.review_episode.evidence_cutoff_date)
        dated_selection = dict(selection)
        needs_source = {p.predicate_id for p in predicates if p.requires_professional_judgment
            or p.semantic_proposition or p.applicable_population or p.prospective_period or p.prospective_window}
        needs_source.update(pid for req in due if req.variable_id in definitions
            and definitions[req.variable_id].value_type == "exposure" for pid in req.predicate_ids)
        predicate_variables = {pid: req.variable_id for req in due for pid in req.predicate_ids}
        numeric_history = {p.predicate_id for p in predicates if is_numeric_history_condition(
            p, definitions.get(predicate_variables.get(p.predicate_id)))}
        # A normalizer's generic value/EXISTS result is not proof of a written
        # judgment, a future intention or an actual medication-use relationship.
        for pid in needs_source:
            selection[pid] = VariableSelection((), selection[pid].considered_fact_ids,
                date_uncertain=selection[pid].date_uncertain)
        selected_ids = {fact_id for value in selection.values() for fact_id in value.fact_ids}
        selected = [fact for fact in frozen.facts if fact.fact_id in selected_ids]
        if any(value.calculation_unverified_ids and not value.fact_ids for value in selection.values()):
            issue = _issue(clause.official_code, "已找到原始检验结果，但参考范围或同排单位关系尚未核实，暂不能计算本条所需倍数。")
            return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail, evidence_refs=available_refs)
        if any(value.conflict for value in selection.values()):
            detail = ("年龄记录与单据日期前后不一致，存在倒退或明显不合理的增长，未自动择优。"
                if any(value.chronology_conflict for value in selection.values()) else
                "同一采样日或同一来源位置的记录不一致，未自动择优。")
            return WorkDraftItem(**common, decision=D.CONFLICT, reason_text=detail,
                evidence_refs=[ref for fact in selected for ref in evidence_refs.get(fact.fact_id, ())])
        adapted = []
        for fact in selected:
            item = adapt_clinical_fact_v2(fact)
            bound_predicates = [predicate for predicate in predicates
                if fact.fact_id in selection.get(predicate.predicate_id, VariableSelection(())).fact_ids]
            readings = {comparison_reading(fact, definitions[predicate_variables[predicate.predicate_id]], predicate,
                definitions=definitions) for predicate in bound_predicates}
            if len(readings) > 1:
                raise ValueError("同一结果对应不同定量与定性比较，须分别核对")
            if readings:
                value, unit = next(iter(readings))
                item = item.model_copy(update={"value": value, "unit": unit})
            # Membership was proven by the snapshot chain; the calculation frame is current.
            adapted.append(item.model_copy(update={"evidence_snapshot_id": frozen.authority.evidence_snapshot_v2_id}))
        calculation_component = component.model_copy(deep=True)
        for expression in (calculation_component.expression, calculation_component.exception_expression):
            if expression is None:
                continue
            for predicate in iter_atomic_predicates(expression):
                definition = definitions.get(predicate_variables.get(predicate.predicate_id))
                if definition is not None and definition.value_type == "number" and predicate.value is not None:
                    values = predicate.value if isinstance(predicate.value, list) else [predicate.value]
                    converted = [float(definition.convert(value, predicate.unit or definition.canonical_unit)) for value in values]
                    predicate.value = converted if isinstance(predicate.value, list) else converted[0]
                    predicate.unit = definition.canonical_unit
        context = EvaluationContext(project_id=frozen.authority.project_id, subject_id=frozen.authority.subject_id,
            review_episode_id=frozen.authority.review_episode_id, evidence_snapshot_id=frozen.authority.evidence_snapshot_v2_id,
            accepted_fact_ids=[fact.fact_id for fact in adapted], facts=adapted,
            anchor_dates=review_anchor_dates(frozen.review_episode.anchor_dates, frozen.review_episode.stage))
        if calculation_component.exception_expression is not None:
            from app.domain.expression import evaluate_component
            evaluation = evaluate_component(calculation_component, context,
                predicate_fact_ids={key: value.fact_ids for key, value in selection.items()},
                unverified_predicate_ids=frozenset(key for key, value in selection.items() if not value.fact_ids))
            if evaluation.trigger.truth == TruthValue.FALSE:
                trigger_ids = {p.predicate_id for p in iter_atomic_predicates(calculation_component.expression)}
                exception_ids = {p.predicate_id for p in iter_atomic_predicates(calculation_component.exception_expression)} - trigger_ids
                inactive = {req.requirement_id for req in due if req.predicate_ids
                    and set(req.predicate_ids) <= exception_ids}
                # A source requirement may have WP2-derived bindings. Remove it
                # only when all of its actual bindings concern the inactive exception.
                for original in due:
                    if original.variable_id is not None:
                        continue
                    derived = [req for req in due if len(req.predicate_ids) == 1
                        and req.requirement_id == "variable_requirement:" + sha256(":".join((
                            component.rule_component_id, req.predicate_ids[0], original.requirement_id)).encode()).hexdigest()[:32]]
                    if derived and all(req.requirement_id in inactive for req in derived):
                        inactive.add(original.requirement_id)
                calculation_component.evidence_requirements = [req for req in calculation_component.evidence_requirements
                    if req.requirement_id not in inactive]
        from app.domain.contracts.enums import ExpectationStatus, GapType
        from app.domain.gates.assessment import RequirementGapState
        observed = {req.requirement_id for req in due if req.predicate_ids
            and all(selection.get(pid) and selection[pid].fact_ids
                    or pid in relations and relations[pid]["truth"] != TruthValue.UNKNOWN.value
                    for pid in req.predicate_ids)}
        observed.update(req.requirement_id for req in due
            if any(req.requirement_id in fact.supported_requirement_ids for fact in selected))
        observed.update(key for key, row in records.items() if row["truth"] == TruthValue.TRUE.value
            and row["relation"] == "supports" and not row["conflict"] and row["applicable"] == "yes"
            and row.get("source_read_refs"))
        # WP2 retained the source requirement and appended derived bindings. Its
        # exact content-derived identity proves ancestry; a display type does not.
        for original in due:
            if original.variable_id is not None:
                continue
            derived = [req for req in due if req.variable_id is not None and len(req.predicate_ids) == 1
                and req.requirement_id == "variable_requirement:" + sha256(":".join((
                    component.rule_component_id, req.predicate_ids[0], original.requirement_id)).encode()).hexdigest()[:32]]
            if derived and all(req.requirement_id in observed
                    and binding_preserves_source_requirement(original, req) for req in derived):
                observed.add(original.requirement_id)
        expectations = [RequirementGapState(req.requirement_id, ExpectationStatus.OBSERVED, None)
                        for req in due if req.requirement_id in observed]
        outcome = calculate_component_review(component=calculation_component, rule_kind=clause.kind,
            context=context, episode_stage=frozen.review_episode.stage, expectations=expectations,
            conflicts=[], predicate_fact_ids={key: value.fact_ids for key, value in selection.items()},
            unverified_predicate_ids=frozenset(key for key, value in selection.items() if not value.fact_ids))
        inactive_requirements = set()
        age_agreements = {pid: value for pid, value in selection.items() if value.age_consensus is not None}
        if relations or age_agreements:
            from app.domain.expression import ComponentEvaluation, EvaluationResult, _combine_bound_expression
            from app.domain.gates.assessment import derive_component_decision, derive_gate_gap_types
            values = dict(outcome.evaluation.predicate_evaluations)
            for pid, agreed in age_agreements.items():
                values[pid] = EvaluationResult(truth=agreed.age_consensus,
                    used_fact_ids=list(agreed.fact_ids), evidence_span_ids=sorted({span
                        for fact in adapted if fact.fact_id in agreed.fact_ids for span in fact.evidence_span_ids}))
            unverified_source_times = set()
            numeric_source_conflicts = set()
            atoms = {atom.predicate.predicate_id: atom for expression in (
                calculation_component.expression, calculation_component.exception_expression)
                if expression is not None for atom in atomic_expressions(expression)}
            for pid, row in relations.items():
                if row.get("scope_only"):
                    continue
                truth = TruthValue(row["truth"])
                if truth != TruthValue.UNKNOWN and not row.get("source_read_refs"):
                    raise ValueError("原文关系缺少逐字来源或已查范围")
                constraint = atoms[pid].time_constraint
                anchor = context.anchor_dates.get(constraint.anchor_type) if constraint else None
                if truth != TruthValue.UNKNOWN and constraint is not None and (anchor is None or anchor.value is None):
                    truth = TruthValue.UNKNOWN
                    unverified_source_times.add(pid)
                elif truth == TruthValue.TRUE and constraint is not None:
                    # Source support proves the event, not its calendar window.
                    # Use only a dated accepted observation at that exact excerpt.
                    dated_ids = set(dated_selection.get(pid, VariableSelection(())).fact_ids)
                    dated = [fact for fact in frozen.facts if fact.fact_id in dated_ids
                        and fact.date_role in {"sampling", "visit"} and fact.date_range is not None
                        and any(ref.excerpt and all(getattr(ref, key) == quote.get(key) for key in (
                            "source_document_version_id", "page_artifact_id", "page_number", "excerpt"))
                            for ref in evidence_refs.get(fact.fact_id, ()) for quote in row["source_read_refs"])]
                    if not dated:
                        truth = TruthValue.UNKNOWN
                        unverified_source_times.add(pid)
                computed = values[pid]
                if pid in numeric_history and computed.truth != TruthValue.UNKNOWN:
                    # A chart denial is not a replacement quantity. Keep proven
                    # arithmetic and its fact references; retain opposing evidence.
                    if row["conflict"] or truth not in {TruthValue.UNKNOWN, computed.truth}:
                        numeric_source_conflicts.add(pid)
                        values[pid] = computed.model_copy(update={"truth": TruthValue.UNKNOWN,
                            "reason_codes": [*computed.reason_codes, "source_conflict"]})
                    continue
                values[pid] = EvaluationResult(truth=truth,
                    reason_codes=["source_conflict"] if row["conflict"] else [] if truth != TruthValue.UNKNOWN else ["observation_unverified"])
            excluded = {p.predicate_id for p in predicates if verified_population_scope(
                relations.get(p.predicate_id, {}), p.model_dump(mode="json"), clause.source_text)}
            active_trigger = applicable_expression(calculation_component.expression, excluded)
            active_exception = applicable_expression(calculation_component.exception_expression, excluded)
            evaluation = ComponentEvaluation(applicable=TruthValue.FALSE if active_trigger is None else TruthValue.TRUE,
                trigger=_combine_bound_expression(active_trigger, values) if active_trigger is not None
                    else EvaluationResult(truth=TruthValue.UNKNOWN),
                exception=_combine_bound_expression(active_exception, values) if active_exception is not None else None,
                predicate_evaluations=values)
            # An absent sibling cannot block a result that stays identical under
            # both counterfactual values. Keep source requirements unrelated to it.
            inactive_predicates = set(excluded)
            for pid, value in values.items():
                if value.truth != TruthValue.UNKNOWN or pid in excluded or active_trigger is None:
                    continue
                signatures = set()
                for possible in (TruthValue.TRUE, TruthValue.FALSE):
                    variant = {**values, pid: EvaluationResult(truth=possible)}
                    t = _combine_bound_expression(active_trigger, variant).truth
                    e = _combine_bound_expression(active_exception, variant).truth if active_exception is not None else None
                    signatures.add((t, e if t == TruthValue.TRUE else None))
                if signatures == {(evaluation.trigger.truth,
                        evaluation.exception.truth if evaluation.exception and evaluation.trigger.truth == TruthValue.TRUE else None)}:
                    inactive_predicates.add(pid)
            inactive_requirements = {req.requirement_id for req in due if req.predicate_ids
                and set(req.predicate_ids) <= inactive_predicates}
            for original in due:
                derived = [req for req in due if req.variable_id is not None and len(req.predicate_ids) == 1
                    and req.requirement_id == "variable_requirement:" + sha256(":".join((
                        component.rule_component_id, req.predicate_ids[0], original.requirement_id)).encode()).hexdigest()[:32]]
                if original.variable_id is None and derived and all(req.requirement_id in inactive_requirements for req in derived):
                    inactive_requirements.add(original.requirement_id)
                elif (original.variable_id is None and original.requirement_id not in observed and derived
                        and all(req.requirement_id in observed | inactive_requirements for req in derived)
                        and all(binding_preserves_source_requirement(original, req) for req in derived)):
                    expectations.append(RequirementGapState(original.requirement_id, ExpectationStatus.OBSERVED, None))
            gap_component = calculation_component.model_copy(update={"evidence_requirements": [
                req for req in calculation_component.evidence_requirements if req.requirement_id not in inactive_requirements]})
            gaps = derive_gate_gap_types(component=gap_component, evaluation=evaluation,
                episode_stage=frozen.review_episode.stage, expectations=expectations, conflict_groups=[])
            from dataclasses import replace
            outcome = replace(outcome, evaluation=evaluation, gaps=frozenset(gaps),
                decision=derive_component_decision(rule_kind=clause.kind, evaluation=evaluation, gaps=gaps))
        if GapType.CALCULATION_CAPABILITY_UNAVAILABLE in outcome.gaps:
            issue = _issue(clause.official_code, "系统暂不支持本条所需的计算方式。")
            return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
        if any(row.get("unsupported_record_time") for row in records.values()) and outcome.decision not in DETERMINATE | {D.NOT_DUE, D.NOT_APPLICABLE}:
            issue = _issue(clause.official_code, "本项独立资料的有效时间要求尚未由系统核对，原文记录与其他结果保留。")
            return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail, evidence_refs=available_refs)
        if (needs_source | numeric_history) - set(relations) and outcome.decision not in DETERMINATE | {D.NOT_DUE, D.NOT_APPLICABLE, D.CONFLICT}:
            issue = _issue(clause.official_code, "本条病历及用药记录的原文核对尚未完成，已有读取内容和其他独立结果保留。")
            return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail, evidence_refs=available_refs)
        used_ids = set(outcome.evaluation.trigger.used_fact_ids)
        if outcome.evaluation.exception is not None and outcome.evaluation.trigger.truth == TruthValue.TRUE:
            used_ids.update(outcome.evaluation.exception.used_fact_ids)
        used = [fact for fact in selected if fact.fact_id in used_ids]
        low_reason = _risk_reason(used)
        if age_agreements:
            low_reason = "年龄记录不一致；各记载均得到本条相同结论，未认定哪个年龄正确。" + (low_reason or "")
        if low_reason is None and (relations or records):
            low_reason = "依据原文作出的含义判断，尚未经人工核实。"
        if low_reason is None and any(value.calculation_unverified_ids for value in selection.values()):
            low_reason = "另有相关检验记录的参考范围未核实，本结论仅依据已有完整读数。"
        age_date_uncertain = any(predicate_variables.get(key) == "age" and value.date_uncertain
            for key, value in selection.items())
        if low_reason is None and age_date_uncertain:
            low_reason = "另有年龄记录的单据日期尚未核实，当前结论仅依据日期明确的记录。"
        if low_reason is None and any(value.date_uncertain for value in selection.values()):
            low_reason = "时间依据只记到部分日期，或采样与报告日期尚未明确区分。"
        if low_reason is None:
            facts_by_id = {fact.fact_id: fact for fact in frozen.facts}
            for expression in (calculation_component.expression, calculation_component.exception_expression):
                if expression is None:
                    continue
                for predicate in iter_atomic_predicates(expression):
                    selected_for_predicate = selection.get(predicate.predicate_id)
                    if selected_for_predicate is None or not selected_for_predicate.fact_ids:
                        continue
                    definition = definitions[predicate_variables[predicate.predicate_id]]
                    def truth(fact_id):
                        fact = facts_by_id[fact_id]
                        value, _ = comparison_reading(fact, definition, predicate, definitions=definitions)
                        return _compare(predicate, value)
                    if any(truth(key) != truth(selected_for_predicate.fact_ids[0]) for key in selected_for_predicate.considered_fact_ids):
                        low_reason = "时间窗内其他次结果会导致不同判断，已保留最近一次结果及其余依据。"
                        break
                    if definition.value_type == "number":
                        value, _ = comparison_reading(facts_by_id[selected_for_predicate.fact_ids[0]], definition,
                            predicate, definitions=definitions)
                        thresholds = predicate.value if isinstance(predicate.value, list) else [predicate.value]
                        if any(isinstance(threshold, (int, float)) and not isinstance(threshold, bool) and threshold
                                and abs(value - threshold) / abs(threshold) <= 0.05 for threshold in thresholds):
                            low_reason = "采用数值接近方案阈值，需核对原始读数与参考范围。"
                            break
        if low_reason is None and any(not page.extraction_complete for page in getattr(frozen, "source_pages", ())):
            low_reason = "本次部分资料尚未完成读取，结果仅依据已核对的记录。"
        if low_reason is None and any(clause.official_code in issue.affected_codes for issue in getattr(frozen, "system_issues", ())):
            low_reason = "本条还有识别记录未通过核对，结果仅依据已核实的部分。"
        # Unknown siblings never grant high confidence to a definitive logical shortcut.
        if low_reason is None and any(item.truth == TruthValue.UNKNOWN for item in outcome.evaluation.predicate_evaluations.values()):
            low_reason = "其他子条件仍有资料不足，本结论由已有独立依据决定。"
        def displayed_value(fact):
            from app.domain.contracts.enums import FactPolarity
            if isinstance(fact.value, bool):
                return "明确否认" if fact.polarity == FactPolarity.NEGATED else "是" if fact.value else "否"
            return f"{fact.value}{fact.unit or ''}"
        summaries = list(dict.fromkeys(f"{definitions[fact.variable_id].label_zh}：{displayed_value(fact)}" for fact in used))
        for predicate in predicates:
            definition = definitions.get(predicate_variables.get(predicate.predicate_id))
            if definition is None or definition.reference_ratio_of is None:
                continue
            from app.domain.risk_flags import reference_upper_bound
            for fact in used:
                if fact.variable_id == definition.reference_ratio_of:
                    value, unit = comparison_reading(fact, definition, predicate, definitions=definitions)
                    summaries.append(f"{definition.label_zh}：{value:.6g}{unit}（原值{fact.value}{fact.unit}，本行参考上限{reference_upper_bound(fact)}{fact.unit}）")
        missing_labels = list(dict.fromkeys(definitions[variable_id].label_zh
            for predicate_id, variable_id in predicate_variables.items()
            if variable_id in definitions and (predicate_id not in selection or not selection[predicate_id].fact_ids)))
        unavailable = [label for variable_id, label in ((key, definitions[key].label_zh) for key in bound_variables if key in definitions)
            if label in missing_labels and any(fact.variable_id == variable_id for fact in available)]
        reason = (("；".join(summaries) + "。已按本条方案条件核对。") if outcome.decision in DETERMINATE else
            "已找到相关记录，但" + "、".join(unavailable) + "的内容、归属或适用时间尚未核实，暂不能据此完成判断。" if unavailable else
            "尚未形成可用于本条的" + "、".join(missing_labels) + "已核实记录；请查看原件及尚未采用的内容，不代表原件没有记载。" if missing_labels else
            "现有记录尚不能核对本条全部条件，请查看所列依据与具体子项。")
        pending_requirements = [req for req in due if req.requirement_id not in observed
            and req.requirement_id not in inactive_requirements]
        if relations:
            notes = list(dict.fromkeys(row["reason"] for row in relations.values()))
            reason = "；".join([*summaries, *notes])
            missing_calculations = list(dict.fromkeys(definitions[variable_id].label_zh
                for predicate_id, variable_id in predicate_variables.items()
                if variable_id in definitions and predicate_id not in relations
                and predicate_id not in inactive_predicates and not selection[predicate_id].fact_ids))
            if outcome.decision not in DETERMINATE and missing_calculations:
                reason += "。尚未形成可用于本条的" + "、".join(missing_calculations) + "已核实记录；不代表原件没有记载。"
            if unverified_source_times:
                reason += "。已找到相关记录，但方案要求的日期锚点或同一记录的发生时间尚未核实，不能直接认作落入规定期间。"
            if numeric_source_conflicts:
                reason += "。已采用的数量记录与病历原文关系不一致，两者均已保留，未选择有利结果。"
            if any(row["policy"] for row in relations.values()):
                reason += "。按本次已提供且已核对资料未见排除依据，不表示原件明确否认或研究者另行签字。"
        if outcome.decision not in DETERMINATE | {D.NOT_DUE, D.NOT_APPLICABLE} and pending_requirements:
            labels = list(dict.fromkeys(req.description for req in pending_requirements if req.description))
            reason += "。以下记录尚未核实：" + "；".join(labels)
        if any(row["conflict"] for row in relations.values()) and outcome.decision not in DETERMINATE:
            outcome = replace(outcome, decision=D.CONFLICT)
        elif outcome.decision == D.PROFESSIONAL_JUDGMENT and relations:
            outcome = replace(outcome, decision=D.INDETERMINATE)
            reason = "对应节点病历尚无足以支持本条判断的记录，现为证据不足；不要求另外重复签名。" + reason
        reason_parts = []
        attention_predicates = set()
        if relations:
            # Trace unresolved branches together: changing one leaf alone can
            # hide uncertainty shared by nested alternatives.
            pending_expressions = [active_trigger]
            if evaluation.trigger.truth != TruthValue.FALSE:
                pending_expressions.append(active_exception)
            while pending_expressions:
                expression = pending_expressions.pop()
                if expression is None or _combine_bound_expression(expression, values).truth != TruthValue.UNKNOWN:
                    continue
                if isinstance(expression, AtomicExpression):
                    attention_predicates.add(expression.predicate.predicate_id)
                else:
                    pending_expressions.extend(expression.children)
            for predicate in predicates:
                pid = predicate.predicate_id
                attention = pid in attention_predicates and outcome.decision != D.NOT_APPLICABLE
                row = relations.get(pid)
                if row is None and not attention:
                    continue
                note = row["reason"] if row else "尚未核实可用于本条件的相关记录；请对照原件核对，不代表检查未做。"
                if pid in unverified_source_times:
                    note = "已找到相关记录，但日期锚点或同一记录的发生时间尚未核实，不能直接认作落入规定期间。" + note
                if pid in numeric_source_conflicts:
                    note = "数量记录与病历原文关系不一致，两者均已保留。" + note
                definition = definitions.get(predicate_variables.get(pid))
                label = (predicate.attribute if re.search(r"[\u3400-\u9fff]", predicate.attribute) or definition is None
                    else definition.label_zh)
                reason_parts.append(WorkDraftReasonPart(condition_id=f"{clause.rule_component_id}:{pid}",
                    condition_text=label, reason_text=note, requires_attention=attention))
        if outcome.decision not in DETERMINATE | {D.NOT_DUE, D.NOT_APPLICABLE}:
            for original in pending_requirements:
                if not original.description or original.predicate_ids:
                    continue
                linked_attention = any(req.variable_id is not None and len(req.predicate_ids) == 1
                    and req.predicate_ids[0] in attention_predicates
                    and req.requirement_id == "variable_requirement:" + sha256(":".join((
                        component.rule_component_id, req.predicate_ids[0], original.requirement_id)).encode()).hexdigest()[:32]
                    and binding_preserves_source_requirement(original, req) for req in due)
                if not linked_attention:
                    reason_parts.append(WorkDraftReasonPart(
                        condition_id=f"{clause.rule_component_id}:requirement:{original.requirement_id}",
                        condition_text=original.description,
                        reason_text="这项所需记录尚未核实。已有原件可继续查看，不表示检查未做或资料一定未提供。",
                        requires_attention=True))
        return WorkDraftItem(**common, decision=outcome.decision,
            confidence=("low" if low_reason else "high") if outcome.decision in DETERMINATE else None,
            confidence_reason=low_reason if outcome.decision in DETERMINATE else None,
            reason_text=reason, reason_parts=reason_parts,
            policy_group="not_seen_in_supplied_records" if any(row["policy"] for row in relations.values()) else None,
            evidence_refs=[ref for fact in used for ref in evidence_refs.get(fact.fact_id, ())]
                if outcome.decision in DETERMINATE and not age_date_uncertain else available_refs)
    except (ValueError, TypeError) as exc:
        issue = _issue(clause.official_code, "系统暂不能按已保存的数据项目、单位或条件结构核对本条。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail, evidence_refs=available_refs)


def compose_parent(rule, children, review_run_id):
    """R-C8: aggregate due children; retain future requirements without judging them."""
    if not children:
        issue = _issue(rule.official_code, "本条没有可核对的子项结果，系统暂不能生成结论。")
        return WorkDraftItem(item_id=f"{review_run_id}:parent:{rule.rule_id}", review_run_id=review_run_id,
            official_code=rule.official_code, rule_kind=rule.kind, title=rule.source_text,
            source_text=rule.source_text, system_issue=issue, reason_text=issue.detail,
            input_hash=canonical_hash({"rule": rule.model_dump(mode="json"), "children": []}))
    due_children = [item for item in children if item.decision != D.NOT_DUE]
    current = due_children or children
    decisions = {item.decision for item in current}
    if rule.kind == RuleKind.EXCLUSION:
        positive, negative = D.EXCLUSION_TRIGGERED, D.EXCLUSION_NOT_TRIGGERED
        decision = positive if positive in decisions else negative if decisions <= {negative, D.NOT_APPLICABLE} else None
    else:
        positive, negative = D.INCLUSION_MET, D.INCLUSION_NOT_MET
        decision = negative if negative in decisions else positive if decisions <= {positive, D.NOT_APPLICABLE} else None
    if decisions == {D.NOT_DUE}:
        decision = D.NOT_DUE
    if decisions == {D.NOT_APPLICABLE}:
        decision = D.NOT_APPLICABLE
    issue = None
    if decision is None:
        issue = next((item.system_issue for item in current if item.system_issue), None)
        if issue is None:
            decision = next((value for value in (D.CONFLICT, D.PROFESSIONAL_JUDGMENT, D.INDETERMINATE, D.NOT_DUE)
                             if value in decisions), D.INDETERMINATE)
    low = any(item.confidence == "low" or item.system_issue or item.decision not in DETERMINATE | {D.NOT_APPLICABLE}
              for item in current)
    refs = {ref.locator_id + ":" + ref.fact_id: ref for item in current for ref in item.evidence_refs}
    source_refs = {canonical_hash(ref.model_dump(mode="json")): ref for item in current for ref in item.source_read_refs}
    reason = issue.detail if issue else "；".join(f"{item.title}：{item.reason_text}" for item in children)
    if due_children and len(due_children) != len(children):
        reason = "本次节点结论仅依据已到期要求；后续要求未到期，届时须重新审核。" + reason
    return WorkDraftItem(item_id=f"{review_run_id}:parent:{rule.rule_id}", review_run_id=review_run_id,
        official_code=rule.official_code, rule_kind=rule.kind, title=rule.source_text,
        source_text=rule.source_text, decision=decision, system_issue=issue,
        confidence=("low" if low else "high") if decision in DETERMINATE else None,
        confidence_reason=("；".join(dict.fromkeys(item.confidence_reason for item in current if item.confidence_reason))
            or "部分子项仍未核实，本结论只由已有独立依据决定。") if low and decision in DETERMINATE else None,
        reason_text=reason, reason_parts=[part for item in current for part in item.reason_parts] if issue is None else [],
        policy_group="not_seen_in_supplied_records" if any(item.policy_group == "not_seen_in_supplied_records" for item in current) else None,
        evidence_refs=list(refs.values()), source_read_refs=list(source_refs.values()),
        input_hash=canonical_hash([item.input_hash for item in children]))


def calculate_procedures(frozen, rule_set, *, evidence_refs, source_results=None):
    """REQs come from the frozen published catalog, not inferred IN/EX numbers."""
    if frozen.procedure_catalog is None:
        raise ValueError("工作稿没有完整流程项目录")
    reviews = {item.official_code: item for item in rule_set.review_records or ()}
    result = []
    for item in sorted(frozen.procedure_catalog.items, key=lambda item: item.position):
        code = item.official_code or f"REQ-{item.position + 1:02d}"
        requirements = [req for req in frozen.procedure_requirements if req.procedure_catalog_item_id == item.item_id]
        review = reviews.get(item.item_id)
        due = [req for req in requirements if STAGE_RANK[req.due_stage] <= STAGE_RANK[frozen.review_episode.stage]]
        source_text = "\n".join(text for text in item.source_excerpts if text) or item.label
        common = dict(item_id=f"{frozen.review_run_id}:procedure:{item.item_id}", review_run_id=frozen.review_run_id,
            official_code=code, rule_kind=RuleKind.REQUIRED_PROCEDURE, title=item.label, source_text=source_text,
            input_hash=canonical_hash({"catalog_item": item.model_dump(mode="json"),
                "requirements": [req.model_dump(mode="json") for req in requirements],
                "review": review.model_dump(mode="json") if review else None,
                **({"evidence_cutoff_date": frozen.review_episode.evidence_cutoff_date.isoformat()}
                    if frozen.review_episode.evidence_cutoff_date is not None else {}),
                "facts": [fact.model_dump(mode="json") for fact in frozen.facts
                    if fact.variable_id in {req.variable_id for req in requirements} | set(review.result_variables if review else ())]}))
        if review is not None and review.note == "excluded":
            result.append(WorkDraftItem(**common, decision=D.NOT_APPLICABLE, reason_text="审定时已排除入组前必需核对；原流程要求仍保留。"))
            continue
        if not due:
            result.append(WorkDraftItem(**common, decision=D.NOT_DUE, reason_text="这项检查或操作属于后续审核节点。"))
            continue
        required_ids = {req.variable_id for req in due if req.variable_id}
        anchor_type = AnchorType.BASELINE_DATE if frozen.review_episode.stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE
        anchor = frozen.review_episode.anchor_dates.get(anchor_type)
        cutoff = review_source_cutoff(frozen.review_episode.anchor_dates, frozen.review_episode.stage,
            frozen.review_episode.evidence_cutoff_date)
        def in_node_scope(fact):
            recorded = source_record_date(fact, evidence_refs, getattr(frozen, "source_pages", ()))
            return not (cutoff is not None and (recorded is not None and recorded > cutoff
                or fact.date_range is not None and fact.date_range.lower_bound is not None
                and fact.date_range.lower_bound > cutoff))
        scoped = [fact for fact in frozen.facts if in_node_scope(fact)]
        relation = (source_results or {}).get(f"procedure:{item.item_id}")
        if relation:
            common["input_hash"] = canonical_hash({"calculation_input": common["input_hash"],
                "source_relation": relation})
        if relation and verified_population_scope(relation, {}, source_text):
            from app.domain.contracts.work_draft import WorkDraftSourceRef
            result.append(WorkDraftItem(**common, decision=D.NOT_APPLICABLE, reason_text=relation["reason"],
                source_read_refs=[WorkDraftSourceRef.model_validate(ref) for ref in relation["source_read_refs"]]))
            continue
        if any(req.source_validity_window is not None or req.control_validity_status is not None for req in due):
            issue = _issue(code, "本项还需要核对方案规定的资料有效期，当前操作完成记录不足以替代有效期核查。")
            result.append(WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail))
            continue
        facts = [fact for fact in scoped if fact.variable_id in required_ids]
        if relation and relation["conflict"]:
            from app.domain.contracts.work_draft import WorkDraftSourceRef
            result.append(WorkDraftItem(**common, decision=D.CONFLICT, reason_text=relation["reason"],
                source_read_refs=[WorkDraftSourceRef.model_validate(ref) for ref in relation["source_read_refs"]]))
            continue
        if relation and relation["truth"] != TruthValue.UNKNOWN.value:
            from app.domain.contracts.work_draft import WorkDraftSourceRef
            source_refs = [WorkDraftSourceRef.model_validate(ref) for ref in relation["source_read_refs"]]
            requested = set(review.result_variables if review else ())
            found = {fact.variable_id for fact in scoped if fact.value is not None and fact.polarity.value == "affirmed"}
            missing = requested - found
            decision = D.REQUIREMENT_MET if relation["truth"] == TruthValue.TRUE.value else D.REQUIREMENT_NOT_MET
            if decision == D.REQUIREMENT_MET and missing:
                definitions = load_dictionary(rule_set.variable_definitions or ())
                reason = "病历或报告证实操作已完成，但审定指定的结果尚未全部核实：" + "、".join(definitions[key].label_zh for key in sorted(missing))
                result.append(WorkDraftItem(**common, decision=D.INDETERMINATE, reason_text=reason, source_read_refs=source_refs))
            else:
                result.append(WorkDraftItem(**common, decision=decision, confidence="low",
                    confidence_reason="依据完成记录作出的含义判断，尚未经人工核实。",
                    reason_text=relation["reason"], source_read_refs=source_refs))
            continue
        if not facts:
            result.append(WorkDraftItem(**common, decision=D.INDETERMINATE,
                reason_text=f"本次资料尚未形成与{item.label}对应的已核实完成记录；请核对原件及尚未采用的内容，不代表检查未做。"))
            continue
        from app.domain.contracts.enums import FactPolarity
        completed = [fact for fact in facts if fact.polarity == FactPolarity.AFFIRMED and fact.value is not False]
        not_completed = [fact for fact in facts if fact.polarity == FactPolarity.NEGATED or fact.value is False]
        refs = [ref for fact in facts for ref in evidence_refs.get(fact.fact_id, ())]
        if completed and not_completed:
            result.append(WorkDraftItem(**common, decision=D.CONFLICT, reason_text="同一核对项目同时有已完成和未完成记录，需核对时间和来源。", evidence_refs=refs))
            continue
        if not_completed:
            low = anchor is None or anchor.value is None or any(fact.risk_flags or fact.date_range is None
                or fact.date_range.precision.value != "day" or fact.date_role not in {"sampling", "visit"}
                for fact in not_completed)
            result.append(WorkDraftItem(**common, decision=D.REQUIREMENT_NOT_MET,
                confidence="low" if low else "high",
                confidence_reason=(_risk_reason(not_completed) or "记录的节点时间尚需核对。") if low else None,
                reason_text="已有记录明确记载本项未完成。", evidence_refs=refs))
            continue
        requested = set(review.result_variables if review else ())
        found = {fact.variable_id for fact in scoped if fact.value is not None and fact.polarity == FactPolarity.AFFIRMED}
        missing = requested - found
        if not completed or missing:
            definitions = load_dictionary(rule_set.variable_definitions or ())
            labels = [definitions[key].label_zh for key in sorted(missing)]
            result.append(WorkDraftItem(**common, decision=D.INDETERMINATE,
                reason_text="已找到操作记录，但还缺少审定时指定的结果：" + "、".join(labels) if missing else "尚未找到本项明确完成的记录。",
                evidence_refs=refs))
            continue
        values = completed + [fact for fact in scoped if fact.variable_id in requested]
        low = any(fact.risk_flags or fact.date_range is None or fact.date_range.precision.value != "day"
                  or fact.date_role not in {"sampling", "visit"} for fact in values) or anchor is None or anchor.value is None
        result.append(WorkDraftItem(**common, decision=D.REQUIREMENT_MET, confidence="low" if low else "high",
            confidence_reason=(_risk_reason(values) or "记录的节点时间尚需核对。") if low else None,
            reason_text=("已找到本项完成记录，审定时指定的结果字段已提供。" if requested else
                "已找到本项完成记录；本次审定未指定必需结果字段，未据此确认报告内所有结果齐全。")
                + "结果是否符合入排阈值由对应条款另行判断。",
            evidence_refs=[ref for fact in values for ref in evidence_refs.get(fact.fact_id, ())]))
    return result
