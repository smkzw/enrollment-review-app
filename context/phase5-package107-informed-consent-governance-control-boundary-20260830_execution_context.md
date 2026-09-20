# Execution Context: phase5-package107-informed-consent-governance-control-boundary-20260830

Created: 2026-08-30 18:38:27 CST
Objective: 在D001 II期不可变候选计划中完成第107包body.p1251-p1259的伦理与知情同意语义闭环：逐项区分研究级伦理治理、ICF文件治理、知情过程、签署与重新同意控制；对照第67包已接受的筛选前解释和自愿签署控制避免重复，保留第108包边界；产出最小配置、父级清单、确定性回归、独立验收和可恢复记录，不进入临床模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Project boundary and local method: `AGENTS.md`.
- Immutable active Phase II plan: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`; plan id `papl-e17d498106b6f71f440ff2be`, 1848 structure units, 1240 semantic targets, 131 packages.
- Active coverage manifest: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`.
- Package 107 identity: ordinal `107`, id `pap-b119517783facd407b628e1e`, selected Phase II, protocol SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- Package 107 owns exactly `body.p1251-p1259`; its 41 `context_units` are read-only unless Codex later authorizes a narrowly justified attachment. Package 106 ends at `body.p1250`; Package 108 `pap-f3fa399755a65a5a57ba306c` starts at `body.p1260` and must not be absorbed.
- The active plan itself contains the exact owned excerpts and source order. Do not use the legacy 217-package root `frozen_phase_plan.json` for ownership.
- Existing accepted ICF/action closure: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_ICF_DEMOGRAPHICS_ACTION_CLOSURE_ACCEPTED.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_icf_demographics.v4.json` and its v3 extension. Package 67 owns `body.p767-p770`; `body.p768` already governs screening-before explanation of all study procedures and voluntary ICF signature. Package 107 may add distinct source-backed detail but must not publish a duplicate generic ICF-signature control.
- Current replay pattern and strict package identity contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package106_record_retention_governance_boundary.v1.json`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cs_package106_record_retention_governance_boundary.py`, and `scripts/run_protocol_replay_harness.py`.
- Accepted Package 106 boundary: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE106_RECORD_RETENTION_GOVERNANCE_BOUNDARY_ACCEPTED.md`.
- Worker 02 may create or modify only:
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package107_informed_consent_governance_control_boundary.v1.json`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61ct-package107-informed-consent-governance-control-boundary-parent-checklist.md`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61ct_package107_informed_consent_governance_control_boundary.py`
  - generated dry-run directory `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package107-informed-consent-governance-control-boundary/`
- Workers 01, 03 and 04 are read-only. Worker 02 must report a reproducible shared-code blocker before any shared-code change; Codex has not pre-authorized such a change.
- No production path, source protocol, raw subject material, existing clinical report, clinical semantic model, publication, subject/OCR/Profile/browser or visual execution is authorized.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对冻结计划第107包身份、p1251-p1259逐字原文、41项语境、第106/108包边界，并对照第67包p767-p770及已接受ICF动作闭包判断哪些是研究治理、哪些是前置知情同意控制、哪些已被现有来源权威覆盖；输出来源闭包和重复/遗漏风险，不修改文件。
2. 在父级授权的精确路径内创建Package107配置、父级临床清单和专项确定性回归，并运行模型外dry-run；保持官方来源所有权与第67包控制去重，严禁把ICF模板内容、伦理报批或持续告知全部误成单例资格，也不得把真正参与研究前的签署/日期/充分理解控制丢失。共享代码仅在可复现系统根因且先向父级报告后修改。
3. 独立攻击审阅Package107临床语义与产品边界：重点检查研究开始前伦理批准、口头和书面告知、无阅读能力时公正见证人、可理解解释、充分时间、参与者或监护人与执行知情同意研究者分别签名日期、非本人签署关系、双方留存、重要新资料后的伦理批准和再次同意，以及与第67包筛选前解释/自愿签署控制的来源权威去重。只读输出。
4. 待父级合并修正后独立验收实际文件：复跑专项、相邻包及ICF既有回归和dry-run，核对Package107所有权、41项语境隔离、第108包未吸收、控制不重复不漏项、claims_complete=false、中文临床语义和无跨包污染；只读输出。

Workers 01-03 may run after prompt preflight. Worker 04 must not be dispatched until Codex has reviewed Workers 01-03, inspected the actual artifacts, and completed any parent corrections.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
