"""Compute from qualified exposures; show related records without inventing use."""
import unicodedata

from app.domain.calendar_dates import date_bounds
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import ComponentDecision as D, DurationStatus, FactPolarity, ProfileLane, ProtocolPeriod, RuleKind, TruthValue
from app.domain.contracts.work_draft import SystemIssue, WorkDraftItem
from app.domain.medication_timing import medication_window_violation, medication_period_violation
from app.domain.publication import canonical_hash
from app.domain.risk_flags import RiskFlag
from app.services.work_draft_calculation import review_anchor_dates, review_source_cutoff


def _name(value):
    return unicodedata.normalize("NFKC", value).strip().casefold()


def scope_source_issues(rule_set):
    """Retain unresolved protocol sources without inventing patient obligations."""
    supplement = rule_set.scope_supplement
    if supplement is None:
        return []
    sources = {source.source_span_id: source for source in supplement.sources}
    issues = []
    for disposition in supplement.source_dispositions:
        if disposition.disposition != "unresolved":
            continue
        source = sources.get(disposition.source_span_id)
        if source is None or not source.excerpt.strip():
            from app.storage.repositories import ScopeViolationError
            raise ScopeViolationError("补充方案的未决位置无法对应已保存原文")
        codes = sorted({code for section in supplement.sections
            if source.source_span_id in section.source_span_ids for code in section.official_codes})
        issues.append(SystemIssue(kind="component_unstructured", affected_codes=codes,
            detail=f"补充方案要求尚未形成可用判断：{disposition.reason}\n方案原文：{source.excerpt}",
            alternative="请在方案规则的审核范围中完善这段要求；其他有独立依据的条款继续判断。"))
    return issues


def _record_refs(facts, evidence_refs, source_pages, members, cutoff):
    """Navigation only: a published medication record is not a dated exposure."""
    refs = {}
    for fact in facts.values():
        if (fact.profile_lane != ProfileLane.MEDICATION or fact.polarity != FactPolarity.AFFIRMED
                or not any(member in _name(fact.asserted_object) for member in members)
                or fact.assertion_basis is None):
            continue
        if cutoff is None or fact.record_time is not None and fact.record_time.date() > cutoff:
            continue
        if (fact.date_range is not None and fact.date_range.lower_bound is not None
                and fact.date_range.lower_bound > cutoff):
            continue
        basis = fact.assertion_basis
        for ref in evidence_refs[fact.fact_id]:
            if (ref.fact_id == fact.fact_id and ref.locator_id in fact.locator_ids
                    and ref.locator_id == basis.locator_id and basis.assertion_text in ref.excerpt
                    and (ref.source_document_version_id, ref.page_artifact_id, ref.page_number) in source_pages):
                refs[(ref.fact_id, ref.locator_id)] = ref
    return refs


def _classified_history_refs(frozen, supplement, evidence_refs, source_pages, cutoff):
    """Do not call an accepted subset complete while source issues remain."""
    if (cutoff is None or not frozen.source_pages or frozen.system_issues or frozen.conflict_groups
            or not all(page.extraction_covers() for page in frozen.source_pages)):
        return {}
    members = {_name(name) for names in supplement.drug_classes.values() for name in names}
    medications = [fact for fact in frozen.facts if fact.profile_lane == ProfileLane.MEDICATION]
    if not members or not medications or any(fact.polarity == FactPolarity.UNKNOWN for fact in medications):
        return {}
    medications = [fact for fact in medications if fact.polarity == FactPolarity.AFFIRMED]
    if not medications or any(_name(fact.asserted_object) not in members or fact.assertion_basis is None
            or _name(fact.assertion_basis.asserted_object) != _name(fact.asserted_object) for fact in medications):
        return {}
    facts = {fact.fact_id: fact for fact in medications}
    if not facts.keys() <= evidence_refs.keys():
        return {}
    refs = _record_refs(facts, evidence_refs, source_pages, members, cutoff)
    if {ref.fact_id for ref in refs.values()} != facts.keys():
        return {}
    history_pages = {(page.source_document_version_id, page.page_artifact_id, page.page_number)
        for page in frozen.source_pages if page.document_category in {
            "study_chart", "screening_transcription", "historical_record"}}
    if not any((ref.source_document_version_id, ref.page_artifact_id, ref.page_number) in history_pages
            for ref in refs.values()):
        return {}
    covered = set()
    for exposure in frozen.medication_exposures:
        if (not exposure.fact_ids or not set(exposure.fact_ids) <= facts.keys()
                or _name(exposure.medication_name) not in members
                or exposure.record_time is not None and exposure.record_time.date() > cutoff):
            return {}
        for fact_id in exposure.fact_ids:
            fact = facts[fact_id]
            if (_name(fact.asserted_object) != _name(exposure.medication_name)
                    or not any(ref.fact_id == fact_id and ref.locator_id in exposure.locator_ids
                        for ref in refs.values())):
                return {}
            covered.add(fact_id)
    return refs if covered == facts.keys() else {}


def calculate_medications(frozen, rule_set, *, evidence_refs):
    supplement = rule_set.scope_supplement
    if supplement is None:
        return []
    facts = {fact.fact_id: fact for fact in frozen.facts if fact.fact_id in evidence_refs}
    source_pages = {(page.source_document_version_id, page.page_artifact_id, page.page_number)
                    for page in frozen.source_pages}
    anchors = review_anchor_dates(frozen.review_episode.anchor_dates, frozen.review_episode.stage)
    cutoff = review_source_cutoff(anchors, frozen.review_episode.stage, frozen.review_episode.evidence_cutoff_date)
    history_refs = _classified_history_refs(frozen, supplement, evidence_refs, source_pages, cutoff)
    results = []
    for restriction in supplement.medications:
        values = dict(item_id=f"{frozen.review_run_id}:medication:{restriction.item_id}",
            review_run_id=frozen.review_run_id, official_code=restriction.item_id,
            rule_kind=RuleKind.EXCLUSION, title=restriction.drug_text,
            source_text="\n".join(dict.fromkeys(quote.excerpt for quote in restriction.source_quotes)),
            input_hash=canonical_hash({"restriction": restriction.model_dump(mode="json"),
                "classes": supplement.drug_classes, "context": frozen.context_sha256}), policy_group="medication")
        decision, reason, issue, refs = D.INDETERMINATE, "尚未获得可用于本条时间核对的用药或治疗记录；不能据此认定没有发生。", None, {}
        if frozen.review_episode.stage not in restriction.applicable_stages:
            if restriction.applicable_stages:
                decision, reason = D.NOT_APPLICABLE, "本条未规定在当前审核阶段判断；后续阶段要求仍保留。"
            else:
                issue = SystemIssue(kind="component_unstructured", affected_codes=[restriction.item_id],
                    detail="本条用药限制的适用阶段尚未核清。", alternative="请在方案规则中核对适用阶段。")
        elif restriction.unresolved_reason:
            issue = SystemIssue(kind="component_unstructured", affected_codes=[restriction.item_id],
                detail=restriction.unresolved_reason, alternative="请核对本条方案原文；无关要求继续判断。")
        elif restriction.period is None and (restriction.window is None or restriction.window_interpretation is None):
            issue = SystemIssue(kind="method_unsupported", affected_codes=[restriction.item_id],
                detail="本条用药时间范围或禁用、停药间隔的含义尚未接入计算。",
                alternative="核清本条时间要求后更新工作稿，不改动原用药记录。")
        else:
            members = (supplement.drug_classes.get(restriction.drug_class_id, [])
                if restriction.drug_class_id else [restriction.drug_text])
            members = {_name(member) for member in members}
            records = _record_refs(facts, evidence_refs, source_pages, members, cutoff)
            matching = [exposure for exposure in frozen.medication_exposures
                if _name(exposure.medication_name) in members]
            observed = []
            conflicted = {exposure_id for group in frozen.conflict_groups if group.member_kind == "exposure"
                for exposure_id in group.exposure_ids}
            has_conflict = False
            for exposure in matching:
                # Context assembly validates authority and locators. Require all
                # linked fact excerpts as well; another record on the page is not proof.
                if not set(exposure.fact_ids) <= facts.keys():
                    continue
                if cutoff is None or exposure.record_time is not None and exposure.record_time.date() > cutoff:
                    continue
                own_refs = {fact_id: [ref for ref in evidence_refs[fact_id]
                    if ref.fact_id == fact_id and ref.locator_id in exposure.locator_ids and
                    (ref.source_document_version_id, ref.page_artifact_id, ref.page_number) in source_pages]
                    for fact_id in exposure.fact_ids}
                if any(not source for source in own_refs.values()):
                    continue
                for sources in own_refs.values():
                    for ref in sources:
                        refs[(ref.fact_id, ref.locator_id)] = ref
                if exposure.exposure_id in conflicted:
                    has_conflict = True
                    continue
                if restriction.drug_class_id is not None and restriction.class_scope != "all_members":
                    issue = SystemIssue(kind="method_unsupported", affected_codes=[restriction.item_id],
                        detail="已找到类别表中的药名，但本条所需的给药途径、制剂等类别限定尚未完成核对。",
                        alternative="核实具体用药与本条类别限定的关系；不能仅凭药名触发限制。")
                    continue
                if exposure.duration_status == DurationStatus.ONGOING:
                    # Ongoing is an explicitly published state, not inferred
                    # from a prescription or an absent end date.
                    anchor = anchors.get(restriction.window.anchor_type if restriction.window else "review_node_date")
                    bounds = date_bounds(anchor, allow_partial=False) if anchor else None
                    use_date = anchor if (bounds and exposure.start_range is not None
                        and exposure.start_range.upper_bound is not None
                        and exposure.record_time is not None
                        and exposure.start_range.upper_bound <= bounds[0] <= exposure.record_time.date()) else None
                    if use_date is None and exposure.start_range is not None and exposure.start_range.lower_bound is not None:
                        use_date = DateValue(value=exposure.start_range.lower_bound, precision=exposure.start_range.precision)
                else:
                    # A known start proves use on that date, not the last dose.
                    # A date outside the window never establishes a negative below.
                    bound = exposure.end_range if exposure.duration_status == DurationStatus.ENDED else exposure.start_range
                    use_date = DateValue(value=bound.lower_bound, precision=bound.precision
                    ) if bound is not None and bound.lower_bound is not None else None
                use_bounds = date_bounds(use_date, allow_partial=True) if use_date else None
                if use_bounds and use_bounds[1] > cutoff:
                    use_date = None
                if restriction.period is not None:
                    # A current-stage use falls within a whole-study restriction
                    # only when that stage is explicitly included. Treatment
                    # additionally needs the actual first dose; do not guess it.
                    start = anchors.get("first_dose_date" if restriction.period == "treatment_period" else "review_node_date")
                    observed.append(medication_period_violation(use_date=use_date, period_start=start, cutoff_date=cutoff))
                else:
                    observed.append(medication_window_violation(restriction, use_date=use_date, anchor_dates=anchors))
            if has_conflict:
                issue = None
                decision, reason = D.CONFLICT, "相关用药记录存在尚未核清的矛盾，未选择其中一条作为最终依据。"
            elif any(row.truth == TruthValue.TRUE for row in observed):
                if restriction.exception_excerpt and restriction.exception_period != ProtocolPeriod.TREATMENT_PERIOD:
                    reason = "已有记录落在限制时间内，但方案另有例外，尚需核对该例外是否适用。"
                else:
                    decision, reason = D.EXCLUSION_TRIGGERED, "已有来源依据的用药日期落在本条限制时间内；不据此推断完整疗程或停药日期。"
            elif observed:
                reason = ("已有用药记录的时间未落入限制窗口；完整用药史及未归类用药尚未核清，暂不认定未触发。"
                    if all(row.truth == TruthValue.FALSE for row in observed)
                    else "已找到相关用药，但停药时间、命名起点或半衰期依据尚不完整。")
            elif records:
                reason = "发现可能相关的药物记录，可查看原文；这不代表药物类别、实际使用或停药日期已经核实。"
                # Record-only sources support inspection, never the calculation.
                if issue is None:
                    refs.update(records)
            # A dated start outside the window is not a last dose. Only known
            # single/ended courses can establish this absence within the read scope.
            anchor_key = ("first_dose_date" if restriction.period == "treatment_period" else "review_node_date"
                ) if restriction.period is not None else restriction.window.anchor_type
            anchor = anchors.get(anchor_key)
            anchor_bounds = date_bounds(anchor, allow_partial=False) if anchor is not None else None
            if (issue is None and decision == D.INDETERMINATE and history_refs and members
                    and restriction.drug_class_id is not None and restriction.class_scope == "all_members"
                    and anchor_bounds is not None
                    and (restriction.period is None or anchor_bounds[0] <= cutoff)
                    and len(observed) == len(matching)
                    and all(row.truth == TruthValue.FALSE for row in observed)
                    and all(exposure.duration_status in {DurationStatus.SINGLE, DurationStatus.ENDED}
                        and (exposure.duration_status != DurationStatus.ENDED or exposure.end_range is not None)
                        for exposure in matching)):
                decision = D.EXCLUSION_NOT_TRIGGERED
                reason = "本次已核对的用药记录均已归类，未见落入本条限制时间的使用记录；结论仅限本次资料范围。"
                refs.update(history_refs)
        if issue is not None:
            decision, reason = None, issue.detail
        ocr_warning = issue is None and any(
            RiskFlag.LOW_OCR_CONFIDENCE in facts[ref.fact_id].risk_flags
            for ref in refs.values())
        if ocr_warning:
            reason = "识别可能有误，请核对所引原件。" + reason
        results.append(WorkDraftItem(**values, decision=decision, reason_text=reason,
            confidence="low" if decision in {D.EXCLUSION_TRIGGERED, D.EXCLUSION_NOT_TRIGGERED} else None,
            confidence_reason=("识别可能有误；按本次资料范围提示用药风险。" if ocr_warning
                else "时间判断有原件依据，按本次资料范围提示用药风险。" if decision == D.EXCLUSION_TRIGGERED
                else "按本次已核对的用药资料判断，不代表未提供的全部用药史。")
                if decision in {D.EXCLUSION_TRIGGERED, D.EXCLUSION_NOT_TRIGGERED} else None,
            evidence_refs=list(refs.values()), system_issue=issue))
    return results
