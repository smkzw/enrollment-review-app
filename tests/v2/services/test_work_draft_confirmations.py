"""Confidence is explicit, source-bound and never a substitute for missing facts."""
from datetime import UTC, datetime

import pytest

from app.domain.contracts.enums import ComponentDecision as D, RuleKind
from app.domain.contracts.work_draft import (WorkDraftItem, WorkDraftSourceRef,
    WorkDraftAcknowledgement, SystemIssue, acknowledgement_input_hash)
from app.domain.publication import canonical_hash
from app.services.work_draft_review import confirmation_allowed, _apply_confirmations


def item():
    return WorkDraftItem(item_id="run:parent", review_run_id="run", official_code="IN-01",
        rule_kind=RuleKind.INCLUSION, title="合成要求", source_text="原始合成要求", decision=D.INCLUSION_MET,
        confidence="low", reason_text="原文支持本节点", input_hash="a" * 64,
        source_read_refs=[WorkDraftSourceRef(source_document_version_id="doc", page_artifact_id="page", page_number=1,
            excerpt="合成原文", disposition="mentioned")])


def test_confidence_only_job_has_no_inference_step():
    from app.graph.subject_graph import work_draft_steps
    assert list(work_draft_steps(0)) == [("calculate", ()), ("compose", ("calculate",)), ("save", ("compose",))]
    assert [name for name, _ in work_draft_steps(1)] == ["calculate", "semantic", "compose", "save"]


def acknowledgement(row, role="builder_verification"):
    return WorkDraftAcknowledgement(acknowledgement_id="ack", review_episode_id="episode", official_code=row.official_code,
        input_hash=acknowledgement_input_hash(row, "method"), base_review_run_id="run", base_item_id=row.item_id,
        work_draft_job_id="job", actor_kind=role, created_at=datetime(2026, 10, 14, tzinfo=UTC))


@pytest.mark.parametrize("role", ["builder_verification", "medical_manager"])
def test_explicit_source_confirmation_changes_only_confidence_and_marker(role):
    row = item()
    old = canonical_hash(row.model_dump(mode="json"))
    saved = _apply_confirmations([row], [acknowledgement(row, role)], "method")[0]
    assert saved.confidence == "high" and saved.confirmation_kind == role
    excluded = {"confidence", "confidence_reason", "acknowledgement_id", "confirmation_kind"}
    assert saved.model_dump(exclude=excluded) == row.model_dump(exclude=excluded)
    assert canonical_hash(row.model_dump(mode="json")) == old
    assert "confirmation_kind" not in row.model_dump(mode="json")
    assert "acknowledgement_id" not in row.model_dump(mode="json")


@pytest.mark.parametrize("damage", ["unknown", "judgment", "conflict", "system", "no_source", "unresolved_source", "child", "unresolved_sibling"])
def test_confirmation_cannot_turn_incomplete_or_conflicting_material_into_pass(damage):
    row = item()
    rows = [row]
    if damage in {"unknown", "judgment", "conflict"}:
        row = row.model_copy(update={"decision": {"unknown": D.INDETERMINATE,
            "judgment": D.PROFESSIONAL_JUDGMENT, "conflict": D.CONFLICT}[damage], "confidence": None})
    elif damage == "system":
        row = row.model_copy(update={"decision": None, "confidence": None, "system_issue": SystemIssue(
            kind="method_unsupported", affected_codes=[row.official_code], detail="能力未完成", alternative="原件保留")})
    elif damage == "no_source": row = row.model_copy(update={"source_read_refs": []})
    elif damage == "unresolved_source": row = row.model_copy(update={"source_read_refs": [row.source_read_refs[0].model_copy(update={"disposition": "unresolved"})]})
    elif damage == "child": row = row.model_copy(update={"rule_component_id": "child"})
    elif damage == "unresolved_sibling":
        rows.append(row.model_copy(update={"item_id": "run:child", "rule_component_id": "child", "decision": D.INDETERMINATE, "confidence": None}))
    rows[0] = row
    assert not confirmation_allowed(row, rows)
    assert _apply_confirmations(rows, [acknowledgement(row)], "method")[0] == row


@pytest.mark.parametrize("change", ["source", "input", "decision", "method", "excerpt", "page"])
def test_changed_clinical_input_does_not_reuse_old_confirmation(change):
    row = item()
    ack = acknowledgement(row)
    version = "method"
    if change == "source": row = row.model_copy(update={"source_text": "不同的要求"})
    elif change == "input": row = row.model_copy(update={"input_hash": "b" * 64})
    elif change == "decision": row = row.model_copy(update={"decision": D.INCLUSION_NOT_MET})
    elif change == "method": version = "new-method"
    else:
        row = row.model_copy(update={"source_read_refs": [row.source_read_refs[0].model_copy(update=
            {"excerpt": "不同原文"} if change == "excerpt" else {"page_number": 2})]})
    assert _apply_confirmations([row], [ack], version)[0].confidence == "low"
