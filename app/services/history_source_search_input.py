"""Freeze published questions and actual source pages, not candidate counts."""
from app.domain.contracts.history_source_search import (
    VERSION, HistorySearchTarget, HistorySearchPage, history_scope_hash,
)
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.contracts.protocol_controls import ControlObligationAtom
from app.domain.publication import canonical_hash
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.services.binding_qualification_support import load_completed_candidate_qualification_input
from app.services.fact_normalization_source_adapter import (
    build_fact_normalization_plan, collect_visual_observation_attachments,
)
from app.services.review_candidate_scope import require_prepared_candidate_scope
from app.services.review_context_assembly import (
    current_review_clinical_material_sha256, frozen_review_clinical_material_sha256,
)
from app.storage.evidence_locator_repositories import (
    ReferencedDocumentRepository, CompleteEvidenceProcessingRevisionRepository,
)
from app.storage.ocr_repositories import PageArtifactRepository
from app.storage.review_context_repository import ReviewContextV2Repository


def _eligible(purpose, *, professional=False, future=False, complex_policy=False):
    return bool(purpose is not None and purpose.target_kind == "event_history"
                and purpose.record_obligation == "not_required_by_source"
                and purpose.proposition_direction != "unresolved"
                and not professional and not future and not complex_policy)


def history_search_targets(frozen, family):
    result = []
    if family == "predicate":
        for component in frozen.components:
            for entry in (*component.trigger_predicates, *component.exception_predicates):
                predicate = entry.predicate
                policy = predicate.observation_policy
                if (entry.source_status != "verbatim" or not predicate.semantic_proposition
                        or not _eligible(predicate.record_semantics,
                            professional=predicate.requires_professional_judgment,
                            future=predicate.prospective_period is not None or predicate.prospective_window is not None,
                            complex_policy=predicate.occurrence_window is not None or predicate.repeat_scheme is not None
                                or predicate.source_computation is not None
                                or policy is not None and policy.mode not in {"single", "any"})):
                    continue
                result.append(HistorySearchTarget(
                    identity_sha256=entry.predicate_identity_sha256, family=family,
                    proposition=predicate.semantic_proposition, record_semantics=predicate.record_semantics,
                    condition=entry.model_dump(mode="json"), parent_source={
                        "rule_source_text": component.rule_source_text,
                        "expression": component.expression.model_dump(mode="json"),
                        "exception_expression": component.exception_expression.model_dump(mode="json")
                            if component.exception_expression is not None else None,
                        "evidence_requirements": [item.model_dump(mode="json") for item in component.evidence_requirements],
                    },
                ))
    elif family == "control":
        controls = {item.protocol_control_id: item for item in frozen.publication.catalog.controls}
        for entry in project_control_atom_identities(frozen.publication):
            atom, spec = entry.atom, entry.atom.evaluation
            if spec is None or spec.determination_mode != "semantic":
                continue
            if spec.time_purpose == "unresolved" or (
                    atom.time_constraint is not None and spec.time_purpose != "event_membership"):
                continue
            policy = spec.observation_policy
            if not _eligible(spec.record_semantics, professional=atom.requires_professional_judgment,
                             future=isinstance(atom, ControlObligationAtom) and (
                                 atom.prospective_period is not None or atom.continuing_obligation is not None),
                             complex_policy=spec.repeat_scheme is not None
                                or policy is not None and policy.mode not in {"single", "any"}):
                continue
            result.append(HistorySearchTarget(
                identity_sha256=entry.identity_sha256, family=family, proposition=spec.proposition,
                record_semantics=spec.record_semantics, condition=entry.model_dump(mode="json"),
                parent_source=controls[entry.protocol_control_id].model_dump(mode="json"),
            ))
    else:
        raise ValueError("未知的常规病史条件来源")
    return [item.model_dump(mode="json") for item in sorted(result, key=lambda item: item.identity_sha256)]


def load_history_search_scope(session, artifact_store, *, candidate_job_id, context_id):
    material = load_completed_candidate_qualification_input(
        session, artifact_store, candidate_job_id, require_route_receipts=True,
    )
    family = material.get("family")
    if family not in {"predicate", "control"} or material.get("review_context_id") != context_id:
        raise ValueError("资料检索必须对应本次已冻结的方案条件")
    frozen = (PredicateBindingFrozenInput if family == "predicate" else ControlBindingFrozenInput).model_validate(
        material["frozen_input"])
    digest = require_prepared_candidate_scope(session, context_id,
        frozen if family == "predicate" else frozen.evidence_input,
        **({"control_input": frozen} if family == "control" else {}))
    context = ReviewContextV2Repository(session).get(context_id)
    if (digest != context.context_sha256 or digest != material["review_context_sha256"]
            or current_review_clinical_material_sha256(session, context.authority)
                != frozen_review_clinical_material_sha256(context)):
        raise ValueError("当前资料已变化，请重新准备审核")
    targets = history_search_targets(frozen, family)
    if not targets:
        scope = {"version": VERSION, "candidate_family": family, "candidate_job_id": candidate_job_id,
                 "review_context_id": context_id, "review_context_sha256": digest,
                 "frozen_input_sha256": material["frozen_input_sha256"],
                 "authority": context.authority.model_dump(mode="json"),
                 "episode": context.review_episode.model_dump(mode="json"),
                 "targets": [], "pages": [], "blockers": []}
        return {**scope, "scope_sha256": history_scope_hash(scope)}
    # Use the existing closure-verified source adapter; no second OCR or source store.
    revision = CompleteEvidenceProcessingRevisionRepository(session).get_current(
        context.authority.complete_processing_revision_id)
    _, source = build_fact_normalization_plan(session, authority=context.authority,
        revision=revision, allow_image_only=True)
    visual_sources = collect_visual_observation_attachments(session,
        revision=source.revision, doc_version_to_logical=source.doc_version_to_logical)
    blockers = []
    if context.conflict_groups:
        blockers.append("source_conflict_unresolved")
    referenced = ReferencedDocumentRepository(session)
    resolutions = {item.referenced_document_id: item for item in (
        referenced.get_resolution(key) for key in source.revision.resolution_revision_ids)}
    for key in source.revision.referenced_document_revision_ids:
        item = referenced.get_revision(key)
        resolution = resolutions.get(item.referenced_document_id)
        if item.status.value != "dismissed" and (resolution is None or resolution.status.value != "provided"):
            blockers.append(f"referenced_document_unresolved:{key}")
    pages = []
    for (version, number), page in source.page_inputs.items():
        artifact = PageArtifactRepository(session).get(page.page_artifact_id)
        page_blockers = []
        if not page.effective_text.strip():
            page_blockers.append("page_text_unreadable")
        if artifact.status.value != "succeeded":
            page_blockers.append("page_render_degraded")
        # Unresolved coverage risks are not silently reclassified as irrelevant.
        if source.revision.unresolved_blocking_risk_ids:
            page_blockers.append("source_reading_risk_unresolved")
        metadata = source.context_by_logical_document[page.logical_document_id].model_dump(mode="json")
        visuals = [item for item in visual_sources if item.page_artifact_id == page.page_artifact_id]
        identity = {"version": version, "page_number": number, "page_artifact_id": page.page_artifact_id,
                    "page_image_sha256": artifact.page_image_sha256,
                    "effective_text_sha256": page.effective_text_sha256,
                    "metadata": metadata, "blockers": page_blockers,
                    "visual_sources": [item.model_dump(mode="json") for item in visuals]}
        pages.append(HistorySearchPage(page_key=canonical_hash(identity),
            source_document_version_id=version, page_number=number, page_artifact_id=page.page_artifact_id,
            page_image_sha256=artifact.page_image_sha256, effective_text_sha256=page.effective_text_sha256,
            effective_text=page.effective_text, metadata=metadata, blockers=page_blockers,
            visual_sources=visuals).model_dump(mode="json"))
    scope = {"version": VERSION, "candidate_family": family, "candidate_job_id": candidate_job_id,
             "review_context_id": context_id, "review_context_sha256": digest,
             "authority": context.authority.model_dump(mode="json"),
             "episode": context.review_episode.model_dump(mode="json"),
             "frozen_input_sha256": material["frozen_input_sha256"],
             "completion_manifest_sha256": source.revision.completion_manifest_sha256,
             "processing_revision": source.revision.model_dump(mode="json"),
             "targets": targets, "pages": sorted(pages, key=lambda item: item["page_key"]),
             "blockers": sorted(blockers)}
    return {**scope, "scope_sha256": history_scope_hash(scope)}
