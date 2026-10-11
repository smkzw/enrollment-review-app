# Execution Context: r05-candidate-enumeration-20260915

Created: 2026-09-15 08:44:45 CST
Objective: 补齐现有官方和补充要求候选双读的逐事实枚举说明，保留历史身份，直至比较与资格输入可核验；不作临床采信。
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read current app/llm/predicate_binding_candidates.py, app/llm/control_binding_candidates.py, app/services/binding_candidate_comparison.py, app/services/predicate_binding_job.py, app/services/control_binding_job.py, app/services/binding_qualification_support.py and direct contract/batching dependencies; docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17 is source authority.
- Allowed manual edits (apply_patch only): the six source files above and one new small shared app/llm/candidate_fact_accounting.py. Do not modify other paths. Owner handles downstream selection, documentation and acceptance.
- No tests (writing or running), app/model/browser/DB calls, raw clinical files, credentials, dependencies, cleanup or git operations. Python syntax compilation of changed files and git diff --check are allowed.

## Concrete Contract

- Candidate generation currently forces one answer per identity but silently omits facts with no candidate. Add versioned per-identity accounting of every supplied fact. A fact either has candidates, has a source-bound noncorrespondence explanation, or remains explicitly uncertain. Do not filter the accounting universe using fact_type or clinical names. Batch accounting must exactly cover that batch, not facts absent from its input.
- Reuse compact fact IDs and source locators. Avoid repeating full excerpts and avoid one full model call per fact. A small shared schema/validator handles both identity families. Structural completeness is not semantic correctness and not proof of full patient history.
- Newly generated responses must reject missing/extra/duplicate accounting, contradictions between candidate presence and disposition, forged fact/locator associations, and unexplained uncertainty. For unrelated facts with no readable source, use uncertain rather than inventing evidence. Existing source-status restrictions remain.
- Preserve old payload serialization and identities: optional legacy absence must not silently become a complete enumeration. New prompts/jobs require accounting explicitly; historical artifacts remain readable but are never promoted to new completeness. Version prompt/job/comparison as required, and let old pending tasks fail explicit version checks rather than rerunning under new prompts.
- Carry and compare both lanes' accounting into the candidate comparison and its receipt replay in binding_qualification_support. Dual disagreement or either uncertain remains visible. Do not collapse a one-lane candidate versus other-lane exclusion into agreed exclusion. Do not claim dual agreement verifies clinical semantics or issue adoption authorization.
- Expose a clear comparison accounting representation for the owner to consume in the later selection scope proof. Qualification pair creation must not manufacture usable pairs from exclusion records. Existing actual candidate qualification behavior remains intact. Keep raw per-lane evidence linked to its response receipts.
- This finite execution creates the working producer-to-comparison/replay segment, not the final observation selector. Report exact version transitions and remaining downstream consumers. No new scheduler or generic framework.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 在现有候选提示/校验/比较和资格输入重放链中增加版本化的逐事实考虑记录，禁止fact_type作为完整性证明，无新队列，无测试或产品调用。

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
