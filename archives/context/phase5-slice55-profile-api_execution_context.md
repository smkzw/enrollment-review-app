# Execution Context: phase5-slice55-profile-api

Created: 2026-08-23 11:04:11
Objective: 实现 Phase 5 Slice 5.5：基于已发布 v2 事实、事件、暴露、冲突与资料期望，生成可回放的不可变 Patient Profile revision、13 条主题泳道、确定性首屏突出集合、状态与 Phase 4 证据深链，并提供真实 HTTP API 和 500 事实性能回归。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md` P5-R08/P5-R09 and P5-AC01/02/05/08/09/11.
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md` sections 2, 5.3, 6 and 7.
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md` Slice 5.5.
- `.trellis/spec/backend/{index,directory-structure,database-guidelines,error-handling,quality-guidelines}.md` and `.trellis/spec/guides/{index,code-reuse-thinking-guide,cross-layer-thinking-guide}.md`.
- `app/domain/contracts/{facts,evidence_expectations_v2,enums,review}.py`, `app/storage/{facts_models,fact_repositories,evidence_expectation_repository,fact_rule_link_repository}.py`, and `app/services/evidence_api_read_service.py`.
- `PatientProfileRevisionV2Record` already exists in migration `0013`; do not add or rewrite a migration unless Codex first confirms a reproduced physical-schema gap.

## Risk Boundaries

- No production writes.
- Do not read or modify raw clinical source material, legacy project data, or files outside this worktree.
- Do not modify `AGENTS.md`, `.trellis/workflow.md`, `.trellis/config.yaml`, `.codex/agents/*.toml`, prior Slice 5.1-5.4 implementation, or frontend files.
- Do not read the legacy `patient_profiles` table or the fixture PatientProfile as runtime truth; it remains an isolated regression/prototype anchor.
- Do not create ReviewRun, rule assessment, enrollment verdict, ActionRequest, responsibility assignment, action count, or through/not-through labels.
- Do not infer abnormal/critical/trend status from protocol thresholds, keywords, model confidence, or free text. Highlights may use only structured source-report flags/ranges when present, unresolved conflicts, current-due expectations, weak provenance, and structured OCR/parse risks.
- Every profile revision is immutable, authority-bound and strictly decoded. Historical revision reads must not be filtered through a possibly drifted mirror column before validation.
- Profile evidence deep links reuse Phase 4 locator IDs and precision; no new locator or simulated red box may be generated.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 设计并实现 Patient Profile v2 领域合同、13 条泳道归类、确定性首屏突出规则与严格验证。
2. 设计并实现不可变 Patient Profile revision 仓储、权威元组/镜像/历史/链头校验与 Profile 投影服务。
3. 设计并实现薄 Patient Profile HTTP API、中文原生 DTO、状态/历史/证据深链及 API/500 事实性能测试。

## File Ownership And Execution Order

- Worker 01 runs first and may create only `app/domain/contracts/patient_profile_v2.py`, `app/projections/patient_profile.py`, `tests/v2/domain/test_patient_profile_contracts.py`, and `tests/v2/projections/test_patient_profile_projection.py`.
- Worker 02 runs after Worker 01 and may create only `app/storage/patient_profile_repository.py`, `app/services/patient_profile_service.py`, `tests/v2/storage/test_patient_profile_repository.py`, and `tests/v2/services/test_patient_profile_service.py`.
- Worker 03 runs after Worker 02 and may create only `app/api/v2/patient_profile_schemas.py`, `app/api/v2/patient_profiles.py`, and `tests/v2/api/test_patient_profiles.py`; it may edit `app/api/v2/app.py` only to register the service and router.
- Workers must not export symbols through shared `__init__.py` files or edit each other's files. Codex owns any cross-file integration demonstrated necessary after all passes.
- Each worker runs only focused tests for owned files and directly required existing contracts. Codex owns migration, broad regression, performance acceptance and final review.

## Required Profile Semantics

- Exactly the 13 `ProfileLane` values are present in stable display order, including empty lanes; the API may later let the UI collapse them but must not silently omit a clinical category.
- Published `ClinicalFactV2.profile_lane` and `ClinicalEventV2.profile_lane` are the sole fact/event lane authority. The Profile service constructs typed assignments from those fields and must not reclassify from `fact_type`, `event_type`, clinical prose, project labels or caller input.
- Profile items reference a published fact, event, exposure, conflict or expectation by typed identity; an item cannot invent clinical prose not present in the referenced validated contract.
- Preserve event time separately from record time, partial date bounds/precision, review stage, source strength, all locator IDs and exact rule/requirement identities where available.
- Highlights are a deterministic subset of full items with explicit structured reasons. A FactRuleLink by itself is never a highlight reason.
- Current-due expectation gaps, unresolved conflicts, weak-source positive long-term history and structured OCR/parse risk are highlights. `not_due` is retained in the full profile but is not current-due. Source-report abnormal/critical and comparable source-report trend inputs may be highlighted only when represented by explicit structured fields; do not derive them from protocol criteria.
- `succeeded` revision must contain a complete deterministic projection. `generating` and `failed` are explicit status records and cannot masquerade as an empty successful profile. `stale` is derived against current ReviewEpisode authority without mutating the historical row. The contract and storage field are both named `patient_profile_revision_id`.
- Latest and historical reads always return the exact frozen authority tuple and payload; later-stage evidence never rewrites an earlier-stage profile.
- Runtime API uses strict DTO decoding and natural Chinese labels. Internal machine states are not user-facing copy. Evidence links include project/subject/episode/snapshot/processing revision/source document/page/locator/precision sufficient for Phase 4 navigation, without absolute local paths.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
