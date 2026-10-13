"""Current-entry hashes and immutable review events, shared by API and publication."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.contracts.agent_io import ProtocolDeconstructionDraft, ProtocolDeconstructionInput
from app.domain.contracts.rule_reviews import RuleReviewRecord
from app.domain.publication import canonical_hash
from app.storage.models import JobRecord, RuleReviewRecordRow
from app.storage.repositories import AppendConfig, AppendRepository, ProtocolDraftRevisionRepository


REVIEW_CONFIG = AppendConfig(
    record_cls=RuleReviewRecordRow, contract_type=RuleReviewRecord,
    entity_name="规则审定记录",
    specs={key: key for key in (
        "record_id", "draft_id", "protocol_version_id", "official_code", "rule_content_hash",
    )},
    created_at_key="reviewed_at",
)


def review_entries(source: ProtocolDeconstructionInput, draft: ProtocolDeconstructionDraft,
                   *, scoped_stages: bool = False) -> list[dict]:
    entries = []
    for rule in draft.proposed_rules:
        components = [item for item in draft.component_drafts if item.parent_official_code == rule.official_code]
        ids = {item.draft_component_id for item in components}
        mappings = [item for item in draft.parent_catalog_mappings if item.proposed_rule_id == rule.rule_id]
        refs = list(dict.fromkeys([ref for item in mappings for ref in item.source_span_ids]
                                 + [ref for item in components for ref in item.source_refs]))
        payload = {
            "rule": rule.model_dump(mode="json"),
            "components": [item.model_dump(mode="json") for item in components],
            "requirements": [item.model_dump(mode="json") for item in draft.evidence_requirement_drafts
                             if item.draft_component_id in ids],
            "parent_sources": [item.model_dump(mode="json") for item in mappings],
            "source_materials": [item.model_dump(mode="json") for item in source.source_materials
                                 if item.source_span_id in refs],
        }
        used_variables = {item.proposed_requirement.variable_id for item in draft.evidence_requirement_drafts
                          if item.draft_component_id in ids}
        if draft.variable_definitions is not None:
            payload["variables"] = [item.model_dump(mode="json") for item in draft.variable_definitions
                                    if item.variable_id in used_variables]
        entries.append({"official_code": rule.official_code, "kind": "rule", "label": rule.source_text,
                        "rule_content_hash": canonical_hash(payload),
                        "source_refs": refs, "issue_refs": [rule.rule_id, rule.official_code, *sorted(ids), *refs]})
    # The frozen source catalog, not model-produced mappings, is the denominator.
    for item in source.required_procedure_catalog.items:
        mappings = [value for value in draft.procedure_catalog_mappings if value.catalog_item_id == item.item_id]
        requirements = [value for value in draft.evidence_requirement_drafts
                        if value.procedure_catalog_item_id == item.item_id]
        stage_ids = {value.proposed_workflow_stage_id for value in mappings}
        requirement_ids = {value.proposed_requirement.requirement_id for value in requirements}
        payload = {
            "catalog": item.model_dump(mode="json"),
            "mappings": [value.model_dump(mode="json") for value in mappings],
            "requirements": [value.model_dump(mode="json") for value in requirements],
            "stages": [value.model_dump(mode="json") | ({"due_requirement_ids": [
                key for key in value.due_requirement_ids if key in requirement_ids]} if scoped_stages else {})
                       for value in draft.proposed_workflow_stages
                       if value.workflow_stage_id in stage_ids],
            "source_materials": [value.model_dump(mode="json") for value in source.source_materials
                                 if value.source_span_id in item.source_span_ids],
        }
        if draft.variable_definitions is not None:
            payload["variables"] = [value.model_dump(mode="json") for value in draft.variable_definitions
                                    if value.variable_id in {entry.proposed_requirement.variable_id for entry in requirements}]
        entries.append({"official_code": item.item_id, "kind": "procedure", "label": item.label,
                        "rule_content_hash": canonical_hash(payload), "source_refs": list(item.source_span_ids),
                        "issue_refs": [item.item_id, *item.source_span_ids]})
    if len({entry["official_code"] for entry in entries}) != len(entries):
        raise ValueError("规则与检查项目的审定身份重复")
    return entries


def _formal_review_history(session, source, draft):
    """Use actual source-copy receipts, not a caller's claimed approval lineage."""
    from app.domain.contracts.protocol_drafts import DraftRevisionStatus
    from app.storage.codecs import verify_payload_sha256
    from app.workflow.jobstore import JobStore
    from app.services.protocol_workbench_service import STEP_FREEZE, STEP_GENERATE
    if source.interpretation_sources:
        return [], {}
    store = JobStore(session)
    jobs = session.scalars(select(JobRecord).where(
        JobRecord.job_type == "protocol_deconstruction",
        func.json_extract(JobRecord.payload_json, "$.target_project_id") == draft.project_id,
        func.json_extract(JobRecord.payload_json, "$.re_deconstruction_origin") == "formal_feedback"))
    for job in jobs:
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        generated = store.get_last_checkpoint(job.job_id, STEP_GENERATE)
        frozen = store.get_last_checkpoint(job.job_id, STEP_FREEZE)
        if (not generated or generated[1].get("draft_id") != draft.draft_id or not frozen
                or canonical_hash(frozen[1].get("source_input")) != canonical_hash(source.model_dump(mode="json"))):
            continue
        baseline = ProtocolDraftRevisionRepository(session).get(frozen[1]["formal_baseline_revision_id"])
        if (baseline.status != DraftRevisionStatus.PUBLISHED or baseline.project_id != draft.project_id
                or baseline.study_phase != draft.selected_phase or payload.get("target_project_id") != draft.project_id):
            continue
        repository = AppendRepository(session, REVIEW_CONFIG)
        rows = session.scalars(select(RuleReviewRecordRow).where(
            RuleReviewRecordRow.draft_id == baseline.draft_id,
            RuleReviewRecordRow.protocol_version_id == baseline.protocol_version_id,
        ).order_by(RuleReviewRecordRow.sequence))
        history = [repository.get(row.sequence) for row in rows]
        approved = {record.official_code: record for record in history}
        before = {entry["official_code"]: entry for entry in review_entries(source, baseline.content)}
        before_scoped = {entry["official_code"]: entry for entry in review_entries(source, baseline.content, scoped_stages=True)}
        after_scoped = {entry["official_code"]: entry for entry in review_entries(source, draft, scoped_stages=True)}
        equivalent = {entry["official_code"]: entry["rule_content_hash"] for entry in review_entries(source, draft)
            if entry["official_code"] in approved and approved[entry["official_code"]].action == "approved"
            and approved[entry["official_code"]].rule_content_hash == before[entry["official_code"]]["rule_content_hash"]
            and before_scoped[entry["official_code"]]["rule_content_hash"] == after_scoped[entry["official_code"]]["rule_content_hash"]}
        return history, equivalent
    return [], {}


def current_reviews(session: Session, source: ProtocolDeconstructionInput,
                    draft: ProtocolDeconstructionDraft) -> tuple[list[dict], list[RuleReviewRecord]]:
    repository = AppendRepository(session, REVIEW_CONFIG)
    rows = session.scalars(select(RuleReviewRecordRow).where(
        RuleReviewRecordRow.protocol_version_id == draft.protocol_version_id,
        RuleReviewRecordRow.draft_id == draft.draft_id,
    ).order_by(RuleReviewRecordRow.sequence)).all()
    history = [repository.get(row.sequence) for row in rows]
    latest = {record.official_code: record for record in history}
    inherited_history, equivalent = _formal_review_history(session, source, draft)
    inherited = {record.official_code: record for record in inherited_history}
    entries = review_entries(source, draft)
    for entry in entries:
        # A current revocation or changed-current review must not resurrect an old one.
        code = entry["official_code"]
        record = latest.get(code, inherited.get(code))
        valid = (record is not None and record.action == "approved"
                 and (record.rule_content_hash == entry["rule_content_hash"]
                      or code not in latest and equivalent.get(code) == entry["rule_content_hash"]))
        entry["review"] = record if valid else None
        entry["reviewed_content_hash"] = entry["rule_content_hash"] if valid else None
    return entries, [*inherited_history, *history]
