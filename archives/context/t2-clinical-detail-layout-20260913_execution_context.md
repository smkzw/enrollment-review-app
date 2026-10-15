# Execution Context: t2-clinical-detail-layout-20260913

Created: 2026-09-13 22:07:27 CST
Objective: Improve existing wide-screen clinical review detail readability using kangzhe-design-3d site styling without changing business logic, evidence identity, or starting a test stage. Codex owns integration.
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Read-only inspect frontend/src/pages/EligibilityWorkbenchPage.tsx and its existing stylesheet frontend/src/styles/workbench.css plus shared tokens; follow /Users/smkzw/.cc-switch/skills/kangzhe-design-3d/SKILL.md site route with existing React operational app and project desktop-only constraints overriding static-site guidance. Only edit selectors starting eligibility- in frontend/src/styles/workbench.css; do not modify other selectors, TS/JS, contracts, API, database, source documents, tokens/base/shared files, or test files. Improve readable spacing, hierarchy, long Chinese wrapping, source excerpt presentation, and stable control sizing for 1080P to 4K desktops. No hero, nested cards, gradients/orbs, mobile variants, animation or movement of evidence, disease/model-specific styling. Preserve previous uncommitted edits including pre-wrap. Inspect full affected definitions, use apply_patch, no git reset or cleanup, no delegation/network/models/browser or services, no test suite; npm run build and scoped diff check allowed. Return exact changed selectors, build result, limitations. Do not claim visual or clinical acceptance.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
