Delegated mode: same-session targeted follow-up, evidence_single_object.
Assigned route: grok/grok-build/grok-4.7:high; resume the existing session.
You are an independent read-only engineering adviser, not the clinical reader or approver. Hermes workflow guard/runner supplies governed engineering routing only; no personal harness reads patient material here.

Read only these current workspace files, bounded to the affected complete definitions:
- app/services/protocol_workbench_service.py: apply_feedback, _expired_feedback_scope_reviews, _validate_source_error_scope.
- app/protocols/official_scope_review.py: scope_review_basis, reviewed_scope_stages.
- app/protocols/deconstruction_gate.py: temporal scope review validation and generated issue refs.
- app/services/protocol_scope_review_service.py: source/proposal review and validation.
- app/services/protocol_publication_service.py: final gate consumption.
- tests/v2/api/test_protocols_api.py: test_local_feedback_saves_expired_scope_as_pending_not_approval.
- tests/v2/protocols/test_official_scope_review.py: test_pending_feedback_expiry_requires_valid_prior_proof_and_changed_basis.
Do not read clinical documents, raw responses, tmp, databases, credentials, other task logs or private reasoning. No edits, tests, network, Git, external model calls or recursive delegation. At most 20 material read/search operations plus 2 necessary environment operations. Return your report; runner persists it.

Frozen question: A field-correct source repair passed target scope checks, but its changed whole-parent basis invalidates formerly valid sibling scope proofs. The feedback API rejects even saving a pending draft because it counts expected proof expiry as new semantic regression. Proposed minimal fix: after unchanged-sibling/source guards, re-read the old proof through the real receipt validator, require changed old/new full basis, and qualify only previously accepted existing components. Exclude only SOURCE_SCOPE_REVIEW_INVALID and REVIEW_STAGE_SCOPE_UNVERIFIED with nonempty refs wholly within those components from the draft regression/reduction comparison. All actual integrity issues remain unchanged in persistence/readback/publication. New drafts still cannot publish until current source/proposal scope review. Corrupt/missing/rejected/unresolved old proof, unchanged basis and foreign refs cannot qualify. Clinical/source/logic/numeric errors remain counted.

Challenge whether this admits bad meaning, erases an existing problem, excuses new scope errors not attributable to expiry, or causes extra calls/state problems. Is a pending unpublished draft the correct limited recovery boundary? Identify a decisive unsafe positive case if present. Give concrete minimal alternatives, not another orchestration framework or cross-basis auto-approval. Verify the publication consumer rather than assuming null proof is approved. Tests are synthetic; you do not run them and they do not prove clinical accuracy. Previous review was design-only; this round reviews the current uncommitted implementation plus tests at HEAD 2d217fa0 + scoped patch.

Return: findings by severity with code references, decisive evidence/limitations, recommended changes or explicit bounded acceptance, and any remaining question. No final product acceptance. Slow progress is pending, not route failure.
