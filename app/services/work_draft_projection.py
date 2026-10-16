"""Read saved working results; never rerun inference while rendering."""
import re

from sqlalchemy import select

from app.domain.publication import canonical_hash
from app.storage.models import ReviewRunRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.work_draft_repository import WorkDraftRepository
from app.services.work_draft_calculation import LABELS


def display_source_reason(text, *, decision=None):
    """Clean transport vocabulary in explanations, never source excerpts."""
    labels = {"supports": "原文支持", "refutes": "原文明示不符合该条件",
              "not_found": "本次资料未见记录", "unclear": "尚未核清", "conflict": "资料矛盾",
              "relation": "原文关系", "applicable": "适用范围", "site": "研究中心"}
    if decision == "not_applicable":
        text = text.removeprefix("已找到相关原文，但尚不足以证明本条件，不能当作未见记录。")
    text = re.sub(r"(?<![A-Za-z0-9_])applicable\s*=\s*(yes|no|unclear)(?![A-Za-z0-9_])",
        lambda match: {"yes": "适用范围已核对", "no": "有据不适用", "unclear": "适用范围尚未核清"}[match[1]], text)
    text = re.sub(r"(?<![A-Za-z0-9_])(?:relation\s*=\s*)?(supports|refutes|not_found|unclear|conflict)(?![A-Za-z0-9_])",
                  lambda match: labels[match[1]], text)
    text = re.sub(r"(?<![A-Za-z0-9_])(?:relation|applicable|site)(?![A-Za-z0-9_])", lambda match: labels[match[0]], text)
    text = re.sub(r"(?<![A-Za-z0-9_])requires_professional_judgment\s*=\s*(true|false)(?![A-Za-z0-9_])", lambda match:
        "本条件需要研究者判断" if match[1] == "true" else "本条件不额外要求研究者判断", text)
    for key, descriptions in {"object_matches": {"true": "记录对象一致", "false": "记录对象尚未核清"},
            "time_matches": {"true": "记录时间适用", "false": "记录时间尚未核清"}}.items():
        text = re.sub(r"(?<![A-Za-z0-9_])" + key + r"\s*=\s*(true|false)(?![A-Za-z0-9_])",
            lambda match: descriptions[match[1]], text)
    for key, label in {"applicable_population": "条款限定的适用人群", "observed_value": "原始读数",
                       "observed_unit": "原始单位", "anchor_date": "节点日期", "subject": "判断对象",
                       "object_matches": "记录对象核对", "time_matches": "记录时间核对"}.items():
        text = re.sub(r"(?<![A-Za-z0-9_])" + key + r"(?![A-Za-z0-9_])", label, text)
    return re.sub(r"(?<![A-Za-z0-9_])[PT]\d{2}(?![A-Za-z0-9_])", "所列原文", text)


def project_work_draft(session, *, authority, rule_set, clause_pack, artifact_store=None):
    from app.services.eligibility_review_projection import (
        EligibilityClauseProjection,
    )
    from app.services.work_draft_review import CALCULATION_VERSION
    ids = session.scalars(select(ReviewRunRecord.review_run_id).where(
        ReviewRunRecord.review_episode_id == authority.review_episode_id,
        ReviewRunRecord.run_kind == "work_draft").order_by(ReviewRunRecord.created_at.desc())).all()
    rows, issues, run_id, state = [], (), None, "not_started"
    if ids:
        run = AppendRepository(session, REVIEW_RUN_CONFIG).get(ids[0])
        frozen = ReviewContextV2Repository(session).get(run.context_id)
        if frozen.evaluator_version != CALCULATION_VERSION:
            state = "method_changed"
        elif frozen.authority != authority or frozen.rule_set_sha256 != canonical_hash(rule_set.model_dump(mode="json")):
            state = "source_changed"
        else:
            from app.services.review_context_assembly import assemble_review_context
            current = assemble_review_context(session, artifact_store, review_episode_id=authority.review_episode_id,
                review_run_id=frozen.review_run_id, evaluator_version=CALCULATION_VERSION,
                created_at=frozen.created_at, context_id=frozen.context_id, work_draft=True)
            if current.context_sha256 != frozen.context_sha256:
                state = "source_changed"
            else:
                rows = WorkDraftRepository(session).list_for_run(run.review_run_id)
                issues, run_id, state = tuple(run.system_issues), run.review_run_id, "current"
    clauses, components = [], []
    if rows:
        return project_saved_items(rows, authority=authority, rule_set=rule_set, run_id=run_id, issues=issues)
    else:
        for rule in rule_set.rules:
            clauses.append(EligibilityClauseProjection(rule_component_id=rule.rule_id, rule_code=rule.official_code,
                rule_kind=rule.kind.value, text_summary=rule.source_text, source_text=rule.source_text,
                parent_rule_code=None, decision="system_issue", decision_label="尚未生成工作稿",
                reason="请开始审核；旧结果和资料仍会保留。", fact_refs=(), gap_type=None, determination_mode="restricted"))
        if rule_set.scope_supplement is not None:
            for index, item in enumerate(rule_set.scope_supplement.medications):
                clauses.append(EligibilityClauseProjection(rule_component_id=f"medication:{item.item_id}",
                    rule_code=f"用药{index + 1:02d}", rule_kind="medication", text_summary=item.drug_text,
                    source_text="\n".join(dict.fromkeys(quote.excerpt for quote in item.source_quotes)),
                    parent_rule_code=None, decision="system_issue", decision_label="尚未生成工作稿",
                    reason="请开始审核；旧结果和资料仍会保留。", fact_refs=(), gap_type=None, determination_mode="restricted"))
    return _review_projection(authority, rule_set, clauses, components, run_id, issues, state)


def project_saved_items(rows, *, authority, rule_set, run_id, issues=()):
    """One presentation for current and frozen history; no evaluation or active lookup."""
    from app.services.eligibility_review_projection import EligibilityClauseProjection, EligibilityFactRef, EligibilitySourceReadRef
    from app.services.work_draft_review import confirmation_allowed
    clauses, components = [], []
    medication_labels = {item.item_id: f"用药{index + 1:02d}" for index, item in enumerate(
        rule_set.scope_supplement.medications if rule_set.scope_supplement else [])}
    navigation_scope = canonical_hash({"rule_set": canonical_hash(rule_set.model_dump(mode="json")),
        "project": authority.project_id, "subject": authority.subject_id, "episode": authority.review_episode_id})
    for item in rows:
        projection = EligibilityClauseProjection(rule_component_id=item.item_id,
            navigation_key=f"{navigation_scope}:{item.policy_group}:" + (
                f"component:{item.rule_component_id}" if item.rule_component_id is not None
                else f"parent:{item.official_code}"),
            rule_code=medication_labels[item.official_code] if item.policy_group == "medication" else item.official_code,
            rule_kind="medication" if item.policy_group == "medication" else item.rule_kind.value,
            text_summary=item.title, source_text=item.source_text,
            parent_rule_code=item.official_code if item.rule_component_id is not None else None,
            decision=item.decision.value if item.decision else "system_issue",
            decision_label=LABELS[item.decision] if item.decision else "系统问题",
            reason=display_source_reason(item.reason_text, decision=item.decision.value if item.decision else None),
            fact_refs=tuple(EligibilityFactRef(**ref.model_dump(mode="json")) for ref in item.evidence_refs),
            source_read_refs=tuple(EligibilitySourceReadRef(**ref.model_dump(mode="json")) for ref in item.source_read_refs),
            gap_type=None, determination_mode="restricted" if item.system_issue else "semantic" if item.source_read_refs else "deterministic",
            confidence=item.confidence, confidence_reason=item.confidence_reason,
            can_confirm=confirmation_allowed(item, rows), confirmation_kind=item.confirmation_kind,
            reason_parts=tuple(part.model_dump(mode="json") | {
                "reason_text": display_source_reason(part.reason_text)} for part in item.reason_parts))
        (components if item.rule_component_id is not None else clauses).append(projection)
    return _review_projection(authority, rule_set, clauses, components, run_id, issues, "current")


def _review_projection(authority, rule_set, clauses, components, run_id, issues, state):
    from app.services.eligibility_review_projection import EligibilityReviewProjection
    medication_labels = {item.item_id: f"用药{index + 1:02d}" for index, item in enumerate(
        rule_set.scope_supplement.medications if rule_set.scope_supplement else [])}
    display_issues = tuple(issue.model_copy(update={"affected_codes": [medication_labels.get(code, code)
        for code in issue.affected_codes]}) for issue in issues)
    return EligibilityReviewProjection(subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
        rule_set_id=authority.rule_set_id, rule_set_revision=authority.rule_set_revision,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id,
        clauses=tuple(clauses), work_draft_state=state, review_run_id=run_id, system_issues=display_issues,
        verification_only=rule_set.verification_only is not False, component_clauses=tuple(components))
