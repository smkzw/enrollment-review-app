Active task: .trellis/tasks/08-13-phase1-5-agent-monitor-uat

Continue the same worker_02 session. Your first pass is accepted except for one current-stage acceptance gap that you identified yourself.

Hard boundaries:
- Work only inside the current workspace.
- Do not read or modify production paths.
- Do not edit fixture clinical meaning, board/action/navigation files, or unrelated source.
- Tools remain enabled; use them only for this bounded repair and verification.
- Runner-managed report path: `runs/execution/phase1_5_agent_monitor_remediation/worker_02.md`. Never write this path with tools; return the complete report for the runner to persist.

Read these files only before following demonstrated dependencies:
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/prd.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/design.md`
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/findings.md`
- `frontend/src/pages/SubjectsPage.tsx`
- `frontend/src/pages/SubjectsPage.test.tsx`
- `frontend/src/components/evidence/ConflictSources.tsx`
- `frontend/src/styles/profile.css`

The Phase 1.5 PRD and UAT-P1-06 require a monitor who is already on Patient Profile to see conflicting sources side by side. The first pass renders `ConflictSources` only in the workbench EvidencePane, while the Subjects page shows a single conflict event and requires a cross-page jump. Close this gap without changing fixture clinical meaning:

1. Reuse the already mapped `ConflictGroupView` and `ConflictSources` component on `SubjectsPage` for the selected episode. Do not duplicate conflict projection logic.
2. Place it in the risk-first Profile view near the conflicting event/coverage, with native Chinese scope text and without turning the page into a second workbench.
3. Resolved groups remain hidden or clearly resolved according to the shared component contract; never select a preferred source.
4. Add a focused `SubjectsPage.test.tsx` assertion that both facts, stance, source file/page/precision and snapshot version are visible for UAT-03, and that no raw IDs are primary labels.
5. Check 1440px and 390/480px for page-level overflow and stacking. Run focused Vitest, then full Vitest/build if focused checks pass.

Authorized additional files for this follow-up: `frontend/src/pages/SubjectsPage.tsx`, its test, and only the minimal Profile CSS needed to place the existing component. Preserve all worker_03 empty-lane and longitudinal changes. Return the complete execution report schema with incremental diff and verification evidence; do not rewrite the runner report path.
