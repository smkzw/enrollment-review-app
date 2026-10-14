"""Source-bound inputs for a new review; no model calls or implicit publication."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services.published_clause_pack import project_published_clause_pack
from app.services.fact_normalization_command_service import authority_from_active_episode
from app.services.patient_profile_service import PatientProfileService
from app.services.review_judgment_provenance import freeze_judgment_search_result
from app.services.review_protocol_source import load_review_protocol_source
from app.storage.fact_authority import FactAuthorityValidator, clinical_source_scope_is_compatible
from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
from app.storage.judgment_search_repository import JudgmentSearchSummaryRepository
from app.storage.repositories import (
    EpisodeRepository, ProjectRepository, ScopeViolationError, SubjectRepository,
)


def _source_reading_identity(item):
    basis = item.assertion_basis
    if basis is None:
        return None
    return canonical_hash({"variable_id": item.variable_id, "object": item.asserted_object,
        "value": getattr(item, "canonical_value", getattr(item, "value", None)), "unit": item.unit,
        "polarity": item.polarity.value, "date_role": item.date_role,
        "date_range": item.date_range.model_dump(mode="json") if item.date_range is not None else None,
        "locator_id": basis.locator_id, "source_hash": basis.source_text_sha256, "excerpt": basis.assertion_text})


def normalization_source_is_reusable(run, authority, old_rules, current_rules, old_protocol, current_protocol):
    """Coverage of immutable text is not approval of a new rule's interpretation."""
    return run.status.value in {"succeeded", "partial"} and clinical_source_scope_is_compatible(
        run.authority, authority, old_rules, current_rules, old_protocol, current_protocol)


def review_method_is_current(context: ReviewContextSnapshotV2) -> bool:
    from app.services.frozen_review_calculation import EVALUATOR_VERSION

    return (context.evaluator_version == EVALUATOR_VERSION
            and context.requirements_scope_version == "review-requirements-scope/v1")


def require_current_review_method(context: ReviewContextSnapshotV2) -> None:
    if not review_method_is_current(context):
        raise ScopeViolationError("审核方式已更新，请保留原记录并重新准备本次审核")


def review_clinical_material_sha256(
    *,
    facts,
    fact_rule_links,
    events,
    medication_exposures,
    expectations,
    conflict_groups,
    judgment_search_results,
) -> str:
    """Current heads and pinned search summaries; not clinical acceptance."""
    return canonical_hash({
        "identity": "review-clinical-material/v2",
        "facts": [item.model_dump(mode="json") for item in facts],
        "fact_rule_links": [item.model_dump(mode="json") for item in fact_rule_links],
        "events": [item.model_dump(mode="json") for item in events],
        "medication_exposures": [item.model_dump(mode="json") for item in medication_exposures],
        "expectations": [item.model_dump(mode="json") for item in expectations],
        "conflict_groups": [item.model_dump(mode="json") for item in conflict_groups],
        "judgment_search_results": sorted(
            (item.summary_id, item.job_id, item.payload_sha256)
            for item in judgment_search_results
        ),
    })


def current_review_clinical_material_sha256(session: Session, authority) -> str:
    """Rebuild the current clinical-head identity without creating a new context."""
    profile = PatientProfileService()
    facts = tuple(sorted(profile._published_facts(session, authority), key=lambda item: item.fact_id))
    links_by_fact = FactRuleLinkV2Repository(session).list_for_facts(
        [item.fact_id for item in facts], facts=facts,
    )
    links = tuple(sorted(
        (link for values in links_by_fact.values() for link in values),
        key=lambda item: item.link_id,
    ))
    return review_clinical_material_sha256(
        facts=facts,
        fact_rule_links=links,
        events=tuple(sorted(profile._published_events(session, authority), key=lambda item: item.event_id)),
        medication_exposures=tuple(sorted(
            profile._published_exposures(session, authority), key=lambda item: item.exposure_id,
        )),
        expectations=tuple(sorted(
            profile._latest_expectations(session, authority), key=lambda item: item.template_id,
        )),
        conflict_groups=tuple(sorted(
            profile._published_conflicts(session, authority), key=lambda item: item.conflict_group_id,
        )),
        judgment_search_results=JudgmentSearchSummaryRepository(session).latest_entries_for_authority(
            authority,
        ).values(),
    )


def frozen_review_clinical_material_sha256(context: ReviewContextSnapshotV2) -> str:
    """Read the same clinical-head identity from an immutable review context."""
    return review_clinical_material_sha256(
        facts=context.facts,
        fact_rule_links=context.fact_rule_links,
        events=context.events,
        medication_exposures=context.medication_exposures,
        expectations=context.expectations,
        conflict_groups=context.conflict_groups,
        judgment_search_results=context.judgment_search_results,
    )


def require_current_review_clinical_material(session: Session, context: ReviewContextSnapshotV2) -> None:
    if (
        current_review_clinical_material_sha256(session, context.authority)
        != frozen_review_clinical_material_sha256(context)
    ):
        raise ScopeViolationError("当前病史或书面判断核查已经更新，请重新准备本次审核")


def assemble_review_context(
    session: Session, artifact_store: ArtifactStore, *, review_episode_id: str,
    review_run_id: str, evaluator_version: str, created_at: datetime,
    context_id: str | None = None,
    work_draft: bool = False,
) -> ReviewContextSnapshotV2:
    """Caller owns one transaction and stores this before its preallocated run.

    Current heads and search choices are selected only here, never when rendering
    an older report. Incomplete searches are included, not filtered as failures.
    """
    authority = authority_from_active_episode(session, review_episode_id)
    validator = FactAuthorityValidator(session, artifact_store)
    validator.validate(authority)
    episode = EpisodeRepository(session).get(review_episode_id)
    subject = SubjectRepository(session).get(authority.subject_id)
    project = ProjectRepository(session).get(authority.project_id)
    protocol = load_review_protocol_source(session, authority)
    pack = project_published_clause_pack(session, protocol.rule_set)
    profile = PatientProfileService()
    issues = []
    ancestors = ()
    source_pages = ()
    procedure_catalog = None
    if work_draft:
        from app.domain.contracts.work_draft import SystemIssue
        from app.storage.fact_repositories import ClinicalFactV2Repository
        from app.storage.fact_correction_repository import FactCorrectionRepository
        from app.storage.evidence_repositories import EvidenceSnapshotRepository
        from app.storage.fact_authority import FactLocatorReferenceError
        chain = []
        snapshot_id = authority.evidence_snapshot_v2_id
        while snapshot_id is not None:
            if snapshot_id in chain:
                raise ScopeViolationError("资料版本链重复，暂不能生成工作稿")
            snapshot = EvidenceSnapshotRepository(session).get(snapshot_id)
            if (snapshot.project_id, snapshot.subject_id, snapshot.review_episode_id) != (
                authority.project_id, authority.subject_id, authority.review_episode_id):
                raise ScopeViolationError("资料版本链属于其他个例或节点")
            chain.append(snapshot_id)
            snapshot_id = snapshot.prior_snapshot_id
        ancestors = tuple(chain)
        superseded = {item.target_id for item in FactCorrectionRepository(session).list_by_review_episode(review_episode_id)}
        heads = {}
        for fact in ClinicalFactV2Repository(session).list_by_episode(review_episode_id):
            if fact.authority.project_id != authority.project_id or fact.authority.subject_id != authority.subject_id:
                raise ScopeViolationError("病例记录属于其他项目或受试者")
            if fact.authority.evidence_snapshot_v2_id not in chain or fact.fact_id in superseded:
                continue
            prior = heads.get(fact.stable_identity)
            if prior is None or fact.revision > prior.revision:
                heads[fact.stable_identity] = fact
        facts = []
        frozen_source_revision = validator.validate_frozen_source(authority)
        for fact in heads.values():
            try:
                validator.validate_locators(authority, fact.locator_ids)
                from app.domain.gates.fact_evidence_closure import _localized_locator_text
                from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
                if fact.assertion_basis is not None:
                    locator = EvidenceLocatorRepository(session).get(fact.assertion_basis.locator_id)
                    localized = _localized_locator_text(session, locator, frozen_source_revision)
                    if not localized or fact.assertion_basis.assertion_text not in localized:
                        raise FactLocatorReferenceError("记录摘录不能逐字对应原件")
            except FactLocatorReferenceError:
                affected = sorted({clause.official_code for clause in pack.clauses
                    if any(req.variable_id == fact.variable_id and fact.variable_id is not None
                           for req in clause.evidence_requirements)})
                issues.append(SystemIssue(kind="fact_closure_failed", affected_codes=affected,
                    detail="系统暂不能把这条记录对应到当前原件，未用于本次判断。",
                    alternative="请查看该记录原件或补充资料。"))
                continue
            facts.append(fact)
        links_by_fact = {}
        from app.services.fact_normalization_source_adapter import build_fact_normalization_plan
        from app.domain.contracts.work_draft import WorkDraftSourcePage
        from app.storage.fact_repositories import (FactNormalizationRunRepository, FactNormalizationCallRepository,
            FactGateResultRepository, FactNormalizationCandidateRepository)
        from app.domain.contracts.enums import FactCallStatus
        from app.services.protocol_draft_service import resolve_formal_baseline_revision
        from app.services.protocol_workbench_service import ProtocolWorkbenchService
        from app.domain.contracts.agent_io import ProtocolDeconstructionInput
        from sqlalchemy.orm import sessionmaker
        baseline = resolve_formal_baseline_revision(session=session, project_id=authority.project_id)
        if baseline.content.protocol_version_id != authority.protocol_version_id:
            raise ScopeViolationError("本节点的方案版本与现行已发布规则不同")
        context = ProtocolWorkbenchService(sessionmaker(bind=session.get_bind()), data_paths=artifact_store.data_paths
            if artifact_store is not None else validator._require_artifact_store().data_paths)._source_context_for_revision(baseline.revision_id)
        if context is None:
            raise ScopeViolationError("流程项目缺少正式发布时的来源记录")
        source_input = ProtocolDeconstructionInput.model_validate(context["source_input"])
        if source_input.protocol_version_id != authority.protocol_version_id:
            raise ScopeViolationError("流程项目来源属于其他方案版本")
        procedure_catalog = source_input.required_procedure_catalog
        revision = validator.validate_and_get_revision(authority)
        _, source = build_fact_normalization_plan(session, authority=authority, revision=revision)
        read_pages = set()
        from app.storage.repositories import get_rule_set, AppendRepository, PROTOCOL_DOC_CONFIG
        runs = []
        for run in FactNormalizationRunRepository(session).list_by_episode(review_episode_id):
            if (run.authority.project_id, run.authority.subject_id, run.authority.review_episode_id,
                    run.authority.evidence_snapshot_v2_id, run.authority.complete_processing_revision_id) != (
                    authority.project_id, authority.subject_id, authority.review_episode_id,
                    authority.evidence_snapshot_v2_id, authority.complete_processing_revision_id):
                continue
            old_rules = get_rule_set(session, run.authority.rule_set_id, run.authority.rule_set_revision)
            old_protocol = AppendRepository(session, PROTOCOL_DOC_CONFIG).get(run.authority.protocol_version_id)
            if normalization_source_is_reusable(run, authority, old_rules, protocol.rule_set,
                    old_protocol, project.protocol_version):
                runs.append(run)
        logical_to_version = {value: key for key, value in source.doc_version_to_logical.items()}
        adopted_readings = {_source_reading_identity(fact) for fact in facts if fact.assertion_basis is not None}
        for run in runs:
            from app.storage.facts_models import FactNormalizationRunRecord
            from app.workflow.jobstore import JobStore
            row = session.get(FactNormalizationRunRecord, run.run_id)
            checkpoint = JobStore(session).get_last_checkpoint(row.job_id, "finalize") if row.job_id else None
            accounting_issue_ids = set(checkpoint[1].get("accounting_issue_call_ids", ())) if checkpoint else set()
            candidates = {item.candidate_id: item for item in FactNormalizationCandidateRepository(session).list_by_run(run.run_id)}
            for gate in FactGateResultRepository(session).list_by_run(run.run_id):
                if gate.outcome.value == "accepted":
                    continue
                candidate = candidates.get(gate.candidate_id)
                from app.domain.contracts.fact_context import has_standalone_measurement
                from app.domain.contracts.facts import ClinicalFactCandidateV2
                if (isinstance(candidate, ClinicalFactCandidateV2)
                        and gate.gate.value in {"polarity_and_asserted_object", "transactional_publish"}
                        and has_standalone_measurement(candidate)
                        and _source_reading_identity(candidate) in adopted_readings):
                    # Only this exact base reading was adopted. Its separate
                    # context question remains; another result on the page proves nothing.
                    continue
                variable_id = getattr(candidate, "variable_id", None)
                codes = sorted({clause.official_code for clause in pack.clauses
                    if variable_id is not None and any(req.variable_id == variable_id for req in clause.evidence_requirements)})
                from app.storage.evidence_locator_repositories import EvidenceLocatorRepository
                basis = getattr(candidate, "assertion_basis", None)
                primary = basis.locator_id if basis is not None else (
                    candidate.locator_ids[0] if candidate is not None and candidate.locator_ids else None)
                locator = EvidenceLocatorRepository(session).get_or_none(primary) if primary else None
                if locator is not None and (locator.source_document_version_id, locator.page_number) not in source.page_inputs:
                    locator = None
                issues.append(SystemIssue(kind="excerpt_unverified", affected_codes=codes,
                    detail="相关识别记录仍有内容未通过原文或归属核对，未用于本次判断。",
                    alternative="请查看相关原件或补充资料；已经核实的其他记录仍可使用。",
                    source_document_version_id=locator.source_document_version_id if locator else None,
                    page_artifact_id=locator.page_artifact_id if locator else None,
                    page_number=locator.page_number if locator else None))
            for call in FactNormalizationCallRepository(session).list_by_run(run.run_id):
                if call.status == FactCallStatus.SUCCEEDED and call.call_id not in accounting_issue_ids:
                    document_id = logical_to_version.get(call.logical_document_id)
                    read_pages.update((document_id, page) for page in call.page_numbers)
        source_pages = tuple(WorkDraftSourcePage(
            source_document_version_id=page.source_document_version_id, page_artifact_id=page.page_artifact_id,
            page_number=page.page_number, effective_text=page.effective_text or "",
            effective_text_sha256=page.effective_text_sha256,
            document_category=source.context_by_logical_document[page.logical_document_id].document_category,
            extraction_complete=key in read_pages,
        ) for key, page in sorted(source.page_inputs.items()))
        for page in source_pages:
            if not page.extraction_complete:
                from app.domain.variables.dictionary import load_dictionary
                import unicodedata
                normalize = lambda value: unicodedata.normalize("NFKC", value).casefold()
                text = normalize(page.effective_text)
                mentioned = {key for key, definition in load_dictionary(protocol.rule_set.variable_definitions or ()).items()
                    if any(normalize(term) in text for term in (definition.label_zh, *definition.aliases_zh) if term)}
                codes = sorted({clause.official_code for clause in pack.clauses
                    if any(req.variable_id in mentioned for req in clause.evidence_requirements)})
                issues.append(SystemIssue(kind="extraction_failed", affected_codes=codes,
                    detail="这页资料尚未完成记录整理，不把未读内容当作未发生。",
                    alternative="请查看原件；已成功读取的记录仍可用于核对。",
                    source_document_version_id=page.source_document_version_id, page_number=page.page_number,
                    page_artifact_id=page.page_artifact_id))
    else:
        facts = profile._published_facts(session, authority)
        links_by_fact = FactRuleLinkV2Repository(session).list_for_facts(
            [item.fact_id for item in facts], facts=facts,
        )
    issues = list({canonical_hash(issue.model_dump(mode="json")): issue for issue in issues}.values())
    events = profile._published_events(session, authority)
    exposures = profile._published_exposures(session, authority)
    conflicts = profile._published_conflicts(session, authority)
    expectations = profile._latest_expectations(session, authority)
    if work_draft:
        fact_ids = {item.fact_id for item in facts}
        def keep_linked(values, key):
            kept = []
            for item in values:
                if not set(getattr(item, key)) <= fact_ids:
                    issues.append(SystemIssue(kind="fact_closure_failed", affected_codes=[],
                        detail="一项派生记录的依据尚未完整对应当前原件，未用于本次判断。",
                        alternative="已保留依据完整的记录，请核查这项记录的原件。"))
                    continue
                try:
                    validator.validate_locators(authority, item.locator_ids)
                except FactLocatorReferenceError:
                    issues.append(SystemIssue(kind="fact_closure_failed", affected_codes=[],
                        detail="一项派生记录暂不能对应当前原件，未用于本次判断。",
                        alternative="请查看该记录原件或补充资料。"))
                    continue
                kept.append(item)
            return kept
        events = keep_linked(events, "fact_ids")
        exposures = keep_linked(exposures, "fact_ids")
        expectations = keep_linked(expectations, "coverage_fact_ids")
        pools = {"fact": fact_ids, "event": {item.event_id for item in events},
                 "exposure": {item.exposure_id for item in exposures}}
        retained_conflicts = []
        for group in conflicts:
            if not set(getattr(group, f"{group.member_kind}_ids")) <= pools[group.member_kind]:
                issues.append(SystemIssue(kind="fact_closure_failed", affected_codes=[],
                    detail="一项争议记录的依据不完整，已保留疑问，未假称争议已解除。",
                    alternative="请核查争议记录的原件。"))
                continue
            try:
                validator.validate_locators(authority, group.locator_ids)
            except FactLocatorReferenceError:
                issues.append(SystemIssue(kind="fact_closure_failed", affected_codes=[],
                    detail="一项争议记录不能对应当前原件，争议尚未解除。", alternative="请核对争议记录原件。"))
                continue
            retained_conflicts.append(group)
        conflicts = retained_conflicts
    profile._validate_referential_closure(
        facts=facts, events=events, exposures=exposures,
        conflicts=conflicts, expectations=expectations,
    )
    locator_ids = sorted({
        locator_id for item in (*facts, *events, *exposures, *conflicts, *expectations)
        for locator_id in item.locator_ids
    })
    validator.validate_locators(authority, locator_ids)
    entries = JudgmentSearchSummaryRepository(session).latest_entries_for_authority(authority)
    searches = [
        freeze_judgment_search_result(
            session, artifact_store, authority=authority, summary_id=entry.summary_id,
        )
        for entry in entries.values()
    ]
    data = {
        "context_id": context_id if context_id is not None else f"review-context-v2:{uuid4().hex}",
        "review_run_id": review_run_id, "authority": authority,
        "review_episode": episode,
        "subject": subject, "project_name": project.project_name,
        "project_revision": project.revision,
        "protocol_document": protocol.protocol_document,
        "rule_set_sha256": canonical_hash(protocol.rule_set.model_dump(mode="json")),
        "clause_pack_sha256": pack.clause_pack_sha256,
        "clause_pack": pack,
        "protocol_integrity_gate_result_id": protocol.integrity_gate.gate_result_id,
        "evaluator_version": evaluator_version,
        "requirements_scope_version": "review-requirements-scope/v1",
        "workflow_stages": protocol.workflow_stages,
        "facts": tuple(sorted(facts, key=lambda item: item.fact_id)),
        "fact_rule_links": tuple(sorted(
            (link for links in links_by_fact.values() for link in links),
            key=lambda item: item.link_id,
        )),
        "events": tuple(sorted(events, key=lambda item: item.event_id)),
        "medication_exposures": tuple(sorted(exposures, key=lambda item: item.exposure_id)),
        "expectation_templates": tuple(sorted(protocol.expectation_templates, key=lambda item: item.template_id)),
        "expectations": tuple(sorted(expectations, key=lambda item: item.template_id)),
        "conflict_groups": tuple(sorted(conflicts, key=lambda item: item.conflict_group_id)),
        "judgment_search_results": tuple(sorted(searches, key=lambda item: item.summary_id)),
        "created_at": created_at,
    }
    if work_draft:
        data.update(work_draft=True, ancestor_snapshot_ids=ancestors, system_issues=tuple(issues), source_pages=source_pages,
                    procedure_catalog=procedure_catalog, procedure_requirements=protocol.procedure_requirements)
    draft = ReviewContextSnapshotV2.model_construct(**data, context_sha256="0" * 64)
    return ReviewContextSnapshotV2(
        **data,
        context_sha256=canonical_hash(draft.model_dump(mode="json", exclude={"context_sha256"})),
    )
