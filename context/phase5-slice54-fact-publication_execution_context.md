# Execution Context: phase5-slice54-fact-publication

Created: 2026-08-23 07:53:07
Objective: 实现 Phase 5 Slice 5.4：把已通过确定性门禁的候选事务发布为不可变临床事实、事件、用药暴露和冲突组，并构建精确规则索引与五类资料覆盖投影。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md` P5-R06/P5-R07
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md` sections 2, 3.4, 4.2 and 5.1-5.2
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md` Slice 5.4
- `.trellis/spec/backend/{directory-structure,database-guidelines,quality-guidelines,error-handling}.md`
- `app/domain/contracts/{facts,evidence,enums,rules}.py`
- `app/storage/{facts_models,fact_repositories,repositories,models,fact_authority}.py`
- `tests/v2/storage/test_fact_repositories.py` and the Slice 5.2/5.3 tests
- `0013_clinical_facts_profile_v2` already created all Slice 5.4 tables. Do not add a migration unless a demonstrated contract cannot be represented by the existing schema.

## Risk Boundaries

- No production writes.
- Do not read or modify raw clinical source material, legacy project data, or files outside this worktree.
- Do not modify `AGENTS.md`, `.trellis/workflow.md`, `.trellis/config.yaml`, or `.codex/agents/*.toml`.
- Do not modify Slice 5.3 implementation files except where the assigned service imports their public contracts.
- Do not create ReviewRun, enrollment verdict, ActionRequest, Patient Profile, API, or frontend behavior in Slice 5.4.
- Do not use model confidence, free-text similarity, keywords, project/center/subject IDs, or project-specific clinical rules to link facts or choose coverage states.
- All writes must be immutable, idempotent, authority-bound, source-linked, and rollback together inside the caller's transaction. Recheck the active episode/snapshot/complete-revision pointer immediately before publish.
- Existing `clinical_facts`, `evidence_expectations`, and `patient_profiles` remain read-only legacy anchors and must not be queried by new code.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 事务发布服务：从运行级门禁结果构造并原子写入事实、事件、用药暴露、冲突组及 Phase 4 定位链接，复核活动权威指针并保证幂等。
2. 规则索引：建立仅基于已发布事实类型、RuleComponent 和 EvidenceRequirement 明确身份的双向可重建 FactRuleLink，不使用自由文本模糊匹配。
3. 资料覆盖投影：从当前审核节点模板生成五类 EvidenceExpectation，细分缺口原因，并正确表达较弱转述事实加溯源提醒而不重复报无证据。

## File Ownership And Integration

- Worker 01 may create only `app/services/fact_publication_service.py` and `tests/v2/services/test_fact_publication_service.py`.
- Worker 02 may create only `app/domain/contracts/fact_rule_index.py`, `app/storage/fact_rule_link_repository.py`, and `tests/v2/storage/test_fact_rule_link_repository.py`.
- Worker 03 may create only `app/domain/contracts/evidence_expectations_v2.py`, `app/projections/evidence_expectations.py`, `app/storage/evidence_expectation_repository.py`, and `tests/v2/projections/test_evidence_expectations.py`.
- Do not edit shared files to export symbols; Codex will integrate imports and make any demonstrated shared adjustment after reviewing all three outputs.
- Run only focused tests for owned files plus directly adjacent existing fact repository tests. Do not run the full suite; Codex owns broad regression.

## Required Semantics

- Publish only candidates whose run-level aggregate has an accepted `transactional_publish` gate. A conflict marker does not reject its member facts; conflicting facts publish side by side and then form one unresolved conflict group.
- Same stable fact content within one immutable authority tuple becomes one fact revision with the union of sorted locator IDs. Different semantic values/polarity/date/duration must not merge.
- Event/exposure fact references must resolve from system candidate IDs to published fact IDs and their locators must stay within that published fact closure.
- FactRuleLink is a deterministic, rebuildable projection. It links a fact to an `EvidenceRequirement` only when the requirement's published `fact_type` equals the fact's `fact_type`; it links the owning `RuleComponent` only through that exact requirement identity. Procedure-catalog requirements have no RuleComponent link.
- EvidenceExpectation is projected for every template bound to the current episode stage/rule revision. Status precedence is `not_due`, `observed`, `observed_weak`, `referenced_missing`, `absent`; weak evidence covers the expectation and may carry a provenance reminder, so it must not also be absent.
- Coverage evidence must be published facts/locators from the same authority tuple and exact `fact_type`. Source requirements determine complete versus weak coverage; OCR/parser risk and specific missing-file/procedure/description facts are structured inputs, not inferred from prose.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
