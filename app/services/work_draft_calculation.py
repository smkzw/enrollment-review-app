"""Deterministic working results from frozen variable bindings and original facts."""
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import re
import unicodedata
from app.domain.contracts.enums import AnchorType, ComponentDecision as D, ReviewStage, RuleKind, TruthValue
from app.domain.contracts.rules import AtomicExpression, RuleComponent, iter_atomic_predicates
from app.domain.contracts.work_draft import SystemIssue, WorkDraftItem
from app.domain.expression import EvaluationContext, _evaluate_time, _compare
from app.domain.policies import STAGE_RANK
from app.domain.publication import canonical_hash
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


def atomic_expressions(expression):
    if isinstance(expression, AtomicExpression):
        yield expression
    else:
        for operand in expression.children:
            yield from atomic_expressions(operand)


@dataclass(frozen=True)
class VariableSelection:
    fact_ids: tuple[str, ...]
    considered_fact_ids: tuple[str, ...] = ()
    conflict: bool = False
    date_uncertain: bool = False


def source_record_date(fact, evidence_refs, source_pages):
    """Explicit visit/sample headers may exclude future records, not date an event."""
    pages = {(page.source_document_version_id, page.page_number, page.page_artifact_id): page for page in source_pages}
    values = set()
    for ref in (evidence_refs or {}).get(fact.fact_id, ()):
        page = pages.get((ref.source_document_version_id, ref.page_number, ref.page_artifact_id))
        if page is None:
            continue
        for match in re.finditer(r"(?m)^\s*(?:采样时间|就诊时间)\s*[:：]\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)", page.effective_text):
            try:
                values.add(date(*(int(value) for value in match.groups())))
            except ValueError:
                return None
    return next(iter(values)) if len(values) == 1 else None


def select_by_variable(component, facts, anchor_dates, *, authority, definitions, stage=ReviewStage.SCREENING, evidence_refs=None, source_pages=()):
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
        anchor_dates=anchor_dates)
    result = {}
    for expression in (component.expression, component.exception_expression):
        if expression is None:
            continue
        for atom in atomic_expressions(expression):
            variable_id = bindings.get(atom.predicate.predicate_id)
            eligible = []
            for fact in facts:
                if (fact.authority.project_id, fact.authority.subject_id, fact.authority.review_episode_id) != (
                        authority.project_id, authority.subject_id, authority.review_episode_id):
                    raise ValueError("事实属于其他项目、受试者或审核节点")
                if variable_id is None or fact.variable_id != variable_id:
                    continue
                from app.domain.contracts.enums import FactPolarity
                if fact.polarity == FactPolarity.UNKNOWN or fact.value is None:
                    continue
                adapted = adapt_clinical_fact_v2(fact)
                temporal = _evaluate_time(atom, adapted, base)
                if temporal.truth == TruthValue.FALSE:
                    continue
                # Unknown windows are retained as questions, not made usable by guessing a date.
                if temporal.truth == TruthValue.UNKNOWN:
                    continue
                anchor = base.anchor_dates.get(atom.time_constraint.anchor_type) if atom.time_constraint else (
                    base.anchor_dates.get(AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE)
                )
                if anchor is not None and anchor.value is not None and fact.date_range is not None:
                    lower = fact.date_range.lower_bound
                    if lower is not None and lower > anchor.value:
                        continue
                recorded = source_record_date(fact, evidence_refs, source_pages)
                if fact.date_range is None and recorded is not None and anchor is not None and anchor.value is not None and recorded > anchor.value:
                    continue
                eligible.append(fact)
            definition = definitions.get(variable_id)
            def value_key(fact):
                if definition is not None and definition.value_type == "number" and isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool):
                    return fact.polarity.value + ":" + str(definition.convert(fact.value, fact.unit or ""))
                return canonical_hash({"value": fact.value, "unit": fact.unit, "polarity": fact.polarity.value})
            conflict = False
            for index, fact in enumerate(eligible):
                for other in eligible[index + 1:]:
                    same_day = (fact.date_range is not None and other.date_range is not None
                        and fact.date_role == other.date_role == "sampling"
                        and fact.date_range.precision.value == other.date_range.precision.value == "day"
                        and fact.date_range.lower_bound == other.date_range.lower_bound)
                    # A PDF can bundle several reports. Only a shared actual
                    # source position proves that these readings refer to one field.
                    distinct_samples = (fact.date_range is not None and other.date_range is not None
                        and fact.date_role == other.date_role == "sampling"
                        and fact.date_range.precision.value == other.date_range.precision.value == "day"
                        and fact.date_range.lower_bound != other.date_range.lower_bound)
                    same_report = bool(set(fact.locator_ids) & set(other.locator_ids)) and not distinct_samples
                    if (same_day or same_report) and value_key(fact) != value_key(other):
                        conflict = True
            dated = [fact for fact in eligible if fact.date_range is not None and fact.date_range.lower_bound is not None]
            if dated:
                nearest = max(fact.date_range.lower_bound for fact in dated)
                chosen = [fact for fact in dated if fact.date_range.lower_bound == nearest]
            else:
                chosen = eligible
            undated_choice_unclear = not conflict and not dated and len({value_key(fact) for fact in chosen}) > 1
            if undated_choice_unclear:
                chosen = []
            result[atom.predicate.predicate_id] = VariableSelection(
                tuple(sorted(fact.fact_id for fact in (eligible if conflict else chosen))),
                tuple(sorted(fact.fact_id for fact in eligible)), conflict,
                undated_choice_unclear or (not base.anchor_dates.get(AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE)
                 or base.anchor_dates[AnchorType.BASELINE_DATE if stage == ReviewStage.BASELINE else AnchorType.SCREENING_DATE].value is None
                 or any(fact.date_range is None or fact.date_range.precision.value != "day"
                    or fact.date_role not in {"sampling", "visit"} for fact in chosen)
                 )
                if atom.time_constraint or definition is not None and definition.domain in {"lab", "vital", "score", "procedure"} else False)
    return result


def _issue(code, detail):
    return SystemIssue(kind="method_unsupported", affected_codes=[code],
        detail=detail, alternative="请对照本条方案原文和已有资料核对；其余独立要求仍可查看。")


def comparison_reading(fact, definition, predicate):
    """Use an explicit qualitative lab label, never derive it from a numeric threshold."""
    value, unit = fact.value, fact.unit
    if definition.value_type == "number":
        return float(definition.convert(value, unit or "")), definition.canonical_unit
    expected = predicate.value if isinstance(predicate.value, list) else [predicate.value]
    if definition.domain == "lab" and definition.value_type == "category" and any(
            item in {"阳性", "阴性"} for item in expected if isinstance(item, str)):
        from app.domain.contracts.enums import FactPolarity
        if not isinstance(value, str) or fact.polarity != FactPolarity.AFFIRMED:
            raise ValueError("检验定性结果未明确")
        literal = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
        match = re.fullmatch(r"(?:[<>≤≥=]?\d+(?:\.\d+)?)?(阳性|阴性)(?:\(([+-])\))?", literal)
        if match is None or match[2] and match[2] != ("+" if match[1] == "阳性" else "-"):
            raise ValueError("检验定性结果包含未核实或相互矛盾的文字")
        # The requested comparison concerns the literal qualitative label. The
        # original quantitative reading/unit remain unchanged in the saved fact.
        return match[1], "unitless"
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
    if clause.exception_expression is not None or not atoms or any(
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


def calculate_work_component(clause, frozen, rule_set, *, evidence_refs):
    from app.storage.repositories import ScopeViolationError
    if any((fact.authority.project_id, fact.authority.subject_id, fact.authority.review_episode_id) != (
            frozen.authority.project_id, frozen.authority.subject_id, frozen.authority.review_episode_id) for fact in frozen.facts):
        raise ScopeViolationError("事实属于其他项目、受试者或审核节点")
    component = RuleComponent(rule_component_id=clause.rule_component_id, parent_rule_id=clause.rule_id,
        display_code=clause.display_code, title=clause.title, expression=clause.expression,
        exception_expression=clause.exception_expression, repeat_trigger_conditions=clause.repeat_trigger_conditions,
        evidence_requirements=clause.evidence_requirements)
    input_hash = canonical_hash({"clause": clause.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in frozen.facts
                  if fact.variable_id in {req.variable_id for req in component.evidence_requirements}],
        "anchors": frozen.review_episode.model_dump(mode="json")["anchor_dates"]})
    input_hash = canonical_hash({"calculation_input": input_hash,
        "source_pages": [(page.source_document_version_id, page.page_artifact_id, page.effective_text_sha256)
                         for page in getattr(frozen, "source_pages", ())],
        "references": {key: [ref.model_dump(mode="json") for ref in values] for key, values in evidence_refs.items()}})
    common = dict(item_id=f"{frozen.review_run_id}:{clause.rule_component_id}",
        review_run_id=frozen.review_run_id, official_code=clause.official_code,
        rule_component_id=clause.rule_component_id, rule_kind=clause.kind,
        title=clause.title, source_text=clause.source_text, input_hash=input_hash)
    due = [req for req in component.evidence_requirements
           if STAGE_RANK[req.due_stage] <= STAGE_RANK[frozen.review_episode.stage]]
    if component.evidence_requirements and not due:
        return WorkDraftItem(**common, decision=D.NOT_DUE, reason_text="本条要求属于后续审核节点。")
    predicates = [predicate for expression in (component.expression, component.exception_expression)
                  if expression is not None for predicate in iter_atomic_predicates(expression)]
    definitions = load_dictionary(rule_set.variable_definitions or ())
    policy = absence_policy(clause, frozen, definitions)
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
    if component.repeat_trigger_conditions or any(predicate.source_computation is not None or predicate.repeat_scheme is not None
            or predicate.occurrence_window is not None or predicate.prospective_period is not None
            or predicate.prospective_window is not None for predicate in predicates):
        issue = _issue(clause.official_code, "系统暂不能完成本条特殊计算或多次记录关系的核对。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
    if any(predicate.semantic_proposition or predicate.applicable_population for predicate in predicates):
        issue = _issue(clause.official_code, "本条还需要核对语义或适用人群，当前工作稿尚未接入这部分判断。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
    if any(definitions[req.variable_id].value_type == "exposure" for req in due if req.variable_id in definitions):
        issue = _issue(clause.official_code, "本条需要核对用药记录的性质及对应时间，当前工作稿尚未接入这部分判断。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
    if any(predicate.requires_professional_judgment for predicate in predicates):
        issue = _issue(clause.official_code, "本条需要核对研究者书面判断，当前工作稿尚未接入这部分核查。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
    try:
        selection = select_by_variable(component, frozen.facts, frozen.review_episode.anchor_dates,
            authority=frozen.authority, definitions=definitions, stage=frozen.review_episode.stage,
            evidence_refs=evidence_refs, source_pages=getattr(frozen, "source_pages", ()))
        selected_ids = {fact_id for value in selection.values() for fact_id in value.fact_ids}
        selected = [fact for fact in frozen.facts if fact.fact_id in selected_ids]
        if any(value.conflict for value in selection.values()):
            return WorkDraftItem(**common, decision=D.CONFLICT, reason_text="同一采样日或同一来源位置的记录不一致，未自动择优。",
                evidence_refs=[ref for fact in selected for ref in evidence_refs.get(fact.fact_id, ())])
        adapted = []
        for fact in selected:
            item = adapt_clinical_fact_v2(fact)
            definition = definitions[fact.variable_id]
            bound_predicates = [predicate for predicate in predicates
                if any(req.variable_id == fact.variable_id and predicate.predicate_id in req.predicate_ids for req in due)]
            readings = {comparison_reading(fact, definition, predicate) for predicate in bound_predicates}
            if len(readings) > 1:
                raise ValueError("同一结果对应不同定量与定性比较，须分别核对")
            if readings:
                value, unit = next(iter(readings))
                item = item.model_copy(update={"value": value, "unit": unit})
            # Membership was proven by the snapshot chain; the calculation frame is current.
            adapted.append(item.model_copy(update={"evidence_snapshot_id": frozen.authority.evidence_snapshot_v2_id}))
        calculation_component = component.model_copy(deep=True)
        predicate_variables = {pid: req.variable_id for req in due for pid in req.predicate_ids}
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
            anchor_dates=frozen.review_episode.anchor_dates)
        from app.domain.contracts.enums import ExpectationStatus, GapType
        from app.domain.gates.assessment import RequirementGapState
        observed = {req.requirement_id for req in due if req.predicate_ids
            and all(selection.get(pid) and selection[pid].fact_ids for pid in req.predicate_ids)}
        observed.update(req.requirement_id for req in due
            if any(req.requirement_id in fact.supported_requirement_ids for fact in selected))
        # WP2 retained the source requirement and appended derived bindings. Its
        # exact content-derived identity proves ancestry; a display type does not.
        for original in due:
            if original.variable_id is not None:
                continue
            derived = [req for req in due if req.variable_id is not None and len(req.predicate_ids) == 1
                and req.requirement_id == "variable_requirement:" + sha256(":".join((
                    component.rule_component_id, req.predicate_ids[0], original.requirement_id)).encode()).hexdigest()[:32]
                and req.model_dump(exclude={"requirement_id", "variable_id", "predicate_ids"})
                    == original.model_dump(exclude={"requirement_id", "variable_id", "predicate_ids"})]
            if derived and all(req.requirement_id in observed for req in derived):
                observed.add(original.requirement_id)
        expectations = [RequirementGapState(req.requirement_id, ExpectationStatus.OBSERVED, None)
                        for req in due if req.requirement_id in observed]
        outcome = calculate_component_review(component=calculation_component, rule_kind=clause.kind,
            context=context, episode_stage=frozen.review_episode.stage, expectations=expectations,
            conflicts=[], predicate_fact_ids={key: value.fact_ids for key, value in selection.items()},
            unverified_predicate_ids=frozenset(key for key, value in selection.items() if not value.fact_ids))
        if GapType.CALCULATION_CAPABILITY_UNAVAILABLE in outcome.gaps:
            issue = _issue(clause.official_code, "系统暂不支持本条所需的计算方式。")
            return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)
        used_ids = set(outcome.evaluation.trigger.used_fact_ids)
        if outcome.evaluation.exception is not None:
            used_ids.update(outcome.evaluation.exception.used_fact_ids)
        used = [fact for fact in selected if fact.fact_id in used_ids]
        low_reason = next(("所用记录有需要核对的识别或归属标记。" for fact in used if fact.risk_flags), None)
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
                        value, _ = comparison_reading(fact, definition, predicate)
                        return _compare(predicate, value)
                    if any(truth(key) != truth(selected_for_predicate.fact_ids[0]) for key in selected_for_predicate.considered_fact_ids):
                        low_reason = "时间窗内其他次结果会导致不同判断，已保留最近一次结果及其余依据。"
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
        missing_labels = list(dict.fromkeys(definitions[variable_id].label_zh
            for predicate_id, variable_id in predicate_variables.items()
            if variable_id in definitions and (predicate_id not in selection or not selection[predicate_id].fact_ids)))
        reason = (("；".join(summaries) + "。已按本条方案条件核对。") if outcome.decision in DETERMINATE else
            "尚缺少可用于本条的" + "、".join(missing_labels) + "记录或对应时间依据。" if missing_labels else
            "现有记录尚不能核对本条全部条件，请查看所列依据与具体子项。")
        return WorkDraftItem(**common, decision=outcome.decision,
            confidence=("low" if low_reason else "high") if outcome.decision in DETERMINATE else None,
            confidence_reason=low_reason, reason_text=reason,
            evidence_refs=[ref for fact in used for ref in evidence_refs.get(fact.fact_id, ())])
    except (ValueError, TypeError) as exc:
        issue = _issue(clause.official_code, "系统暂不能按已保存的数据项目、单位或条件结构核对本条。")
        return WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail)


def compose_parent(rule, children, review_run_id):
    """R-C8: ALL for inclusion; ANY for exclusions, retaining unresolved siblings."""
    if not children:
        issue = _issue(rule.official_code, "本条没有可核对的子项结果，系统暂不能生成结论。")
        return WorkDraftItem(item_id=f"{review_run_id}:parent:{rule.rule_id}", review_run_id=review_run_id,
            official_code=rule.official_code, rule_kind=rule.kind, title=rule.source_text,
            source_text=rule.source_text, system_issue=issue, reason_text=issue.detail,
            input_hash=canonical_hash({"rule": rule.model_dump(mode="json"), "children": []}))
    decisions = {item.decision for item in children}
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
        issue = next((item.system_issue for item in children if item.system_issue), None)
        if issue is None:
            decision = next((value for value in (D.CONFLICT, D.PROFESSIONAL_JUDGMENT, D.INDETERMINATE, D.NOT_DUE)
                             if value in decisions), D.INDETERMINATE)
    low = any(item.confidence == "low" or item.system_issue or item.decision not in DETERMINATE | {D.NOT_APPLICABLE}
              for item in children)
    refs = {ref.locator_id + ":" + ref.fact_id: ref for item in children for ref in item.evidence_refs}
    return WorkDraftItem(item_id=f"{review_run_id}:parent:{rule.rule_id}", review_run_id=review_run_id,
        official_code=rule.official_code, rule_kind=rule.kind, title=rule.source_text,
        source_text=rule.source_text, decision=decision, system_issue=issue,
        confidence=("low" if low else "high") if decision in DETERMINATE else None,
        confidence_reason="部分子项仍需核对；已按原有父子逻辑组合。" if low and decision in DETERMINATE else None,
        reason_text=issue.detail if issue else "；".join(f"{item.title}：{item.reason_text}" for item in children),
        policy_group="not_seen_in_supplied_records" if any(item.policy_group == "not_seen_in_supplied_records" for item in children) else None,
        evidence_refs=list(refs.values()), input_hash=canonical_hash([item.input_hash for item in children]))


def calculate_procedures(frozen, rule_set, *, evidence_refs):
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
        def in_node_scope(fact):
            return not (anchor is not None and anchor.value is not None and fact.date_range is not None
                and fact.date_range.lower_bound is not None and fact.date_range.lower_bound > anchor.value)
        scoped = [fact for fact in frozen.facts if in_node_scope(fact)]
        if any(req.source_validity_window is not None or req.control_validity_status is not None for req in due):
            issue = _issue(code, "本项还需要核对方案规定的资料有效期，当前操作完成记录不足以替代有效期核查。")
            result.append(WorkDraftItem(**common, system_issue=issue, reason_text=issue.detail))
            continue
        facts = [fact for fact in scoped if fact.variable_id in required_ids]
        if not facts:
            result.append(WorkDraftItem(**common, decision=D.INDETERMINATE,
                reason_text=f"本次资料尚未找到{item.label}已完成的报告或记录。"))
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
                confidence_reason="记录的时间、识别或归属尚需核对。" if low else None,
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
            confidence_reason="所用记录仍有识别、归属或节点时间需核对。" if low else None,
            reason_text="已找到本项完成记录，审定时要求的结果字段已提供；结果是否符合入排阈值由对应条款另行判断。",
            evidence_refs=[ref for fact in values for ref in evidence_refs.get(fact.fact_id, ())]))
    return result
