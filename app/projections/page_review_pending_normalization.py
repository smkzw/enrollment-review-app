"""Retain page-level uncertainty without asking a model to invent a history."""

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerInput,
    EvidenceNormalizerOutput,
    EvidenceNormalizerUnresolvedItem,
)
from app.projections.page_review_sources import accepted_observations


LEGACY_PENDING_NORMALIZATION_POLICY = "preserve-pending/v1"
PENDING_NORMALIZATION_POLICY = "preserve-pending/v2"


def pending_only_output(evidence_input: EvidenceNormalizerInput) -> EvidenceNormalizerOutput | None:
    attachment = evidence_input.page_review
    if attachment is None:
        return None
    reviews = {item.page_review_id: item for item in attachment.reviews}
    for reconciliation in attachment.reconciliations:
        if accepted_observations(
            [reviews[key] for key in reconciliation.page_review_ids], reconciliation,
            include_clause_signals=attachment.visual_source_policy is None,
        ):
            return None
    return EvidenceNormalizerOutput(
        run_id=evidence_input.run_id,
        call_id=evidence_input.call_id,
        logical_document_id=evidence_input.logical_document_id,
        page_numbers=evidence_input.page_numbers,
        unresolved_items=[
            EvidenceNormalizerUnresolvedItem(
                code="no_verified_observations",
                message=f"第{page}页暂无已核实、可整理为病史的内容。",
                affected_pages=[page],
                reason="原始资料及逐页核对记录已保留；本次未生成病史，不代表符合入排要求。",
            )
            for page in evidence_input.page_numbers
        ],
    )
