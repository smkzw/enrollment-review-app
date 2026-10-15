# Execution Context: phase5-package108-irb-confidentiality-governance-boundary-20260830

Created: 2026-08-30 19:10:49 CST
Objective: 在D001 II期当前不可变131包候选计划中完成第108包body.p1260-p1269的IRB/EC与参与者保密语义闭环：逐项区分研究启动及持续伦理治理、参与者招募材料审批、SAE/安全通信治理、隐私授权与信息访问治理，以及任何真实参加研究前控制；保留第107/109包边界，产出最小配置、父级临床清单、确定性回归、独立验收和可恢复记录，不进入临床模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。
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
- Current immutable Phase II plan: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/frozen_phase_plan.json`; plan id `papl-e17d498106b6f71f440ff2be`, 1848 structure units, 1240 semantic targets and 131 packages. The legacy root `.trellis/.../research/d001-ii-phase-closure/frozen_phase_plan.json` has 217 packages and is not authoritative for current package identity.
- Active coverage manifest: `artifacts/phase5-slice61cm-d001-phase-context-boundary-rebaseline-20260830/coverage_manifest.json`.
- Package 108 identity: ordinal `108`, id `pap-f3fa399755a65a5a57ba306c`, selected Phase II, protocol SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- Package 108 owns exactly `body.p1260-p1269`; its 37 `context_units` are read-only unless Codex later authorizes one narrowly justified attachment. Package 107 ends at `body.p1259`; Package 109 `pap-2101c87c43a5499476169b81` starts at `body.p1270`; neither adjacent package may be absorbed.
- Owned source meaning must be read from the current plan verbatim. `body.p1260-p1263` are the IRB/EC subsection; `body.p1264-p1269` are the confidentiality subsection. Do not infer subject eligibility merely from phrases such as “研究启动前”, “签署的知情同意书允许”, or “必须”.
- Accepted adjacent boundary: `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE107_INFORMED_CONSENT_GOVERNANCE_CONTROL_BOUNDARY_ACCEPTED.md`.
- Current replay pattern and strict package identity contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package107_informed_consent_governance_control_boundary.v1.json`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61ct_package107_informed_consent_governance_control_boundary.py`, and `scripts/run_protocol_replay_harness.py`.
- Worker 02 may create or modify only:
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package108_irb_confidentiality_governance_boundary.v1.json`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61cu-package108-irb-confidentiality-governance-boundary-parent-checklist.md`
  - `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61cu_package108_irb_confidentiality_governance_boundary.py`
  - generated dry-run directory `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n-prepare/d001-ii-package108-irb-confidentiality-governance-boundary/`
- Workers 01, 03 and 04 are read-only. Worker 02 must report a reproducible shared-code blocker before any shared-code change; no shared-code change is pre-authorized.
- No production path, source protocol, raw subject material, existing clinical report, clinical semantic model, publication, subject/OCR/Profile/browser or visual execution is authorized.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对当前重基线冻结计划Package108身份、body.p1260-p1269逐字原文、37项只读语境及Package107/109边界；逐项判断研究治理、资料治理、隐私治理和潜在参加研究前动作，不修改文件。
2. 在父级精确授权路径内创建Package108配置、父级临床清单、专项确定性回归并运行模型外dry-run；不得把伦理报批、年度进展、SAE上报、资料保密或监管检查误成单例资格，也不得丢失任何真实前置控制。
3. 独立攻击审阅Package108的来源闭包、IRB/EC治理、参与者招募材料审批、个人健康信息授权、编码化与受限访问、监查稽查访问、私人医生披露、探索性样本结果不返还和监管检查边界；只读输出。
4. 待父级合并修正后独立验收实际文件：复跑专项、相邻包和共享语义回归及dry-run，核对所有权、37项语境隔离、第107/109包未吸收、零候选或候选处置均有逐项原文依据、claims_complete=false、中文临床语义和无跨包污染；只读输出。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
