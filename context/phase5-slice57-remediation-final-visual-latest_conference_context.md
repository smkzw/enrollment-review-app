# Conference Context: phase5-slice57-remediation-final-visual-latest

Created: 2026-08-23 22:42:15
Objective: 以懒惰但专业的中文临床试验医学监查员视角，独立审查 Phase 5.7 修订后的 Patient Profile 人工事实修订、生成后档案历史、原文证据定位一致性、草稿保留和 1080P/2K/4K 宽屏交互；识别任何误导、版本混用、错误红框、信息层级、中文原生性、可恢复性与视觉效率问题。仅审阅，不修改代码。
Task type: `visual_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh), then Codex subAgent Luna (max). The Codex subAgent route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, code-review, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh) -> Kimi Code `k3-256k` (high) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/OpenCode Go Muse (xhigh) -> Kimi Code K3 (high) -> Codex Luna (max). Participant 2 is Cursor `auto`, with Grok Build `grok-4.6` (medium) and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `frontend/e2e/screenshots/desktop-1080p-profile-two-column.png`
- `frontend/e2e/screenshots/desktop-2k-profile-two-column.png`
- `frontend/e2e/screenshots/desktop-4k-profile-two-column.png`
- `frontend/e2e/screenshots/desktop-1080p-profile-evidence-panel.png`
- `frontend/e2e/screenshots/desktop-2k-profile-evidence-panel.png`
- `frontend/e2e/screenshots/desktop-4k-profile-evidence-panel.png`
- `frontend/e2e/profile-correction.spec.ts`
- `frontend/src/components/profile/ProfileFactCorrectionDialog.tsx`
- `frontend/src/components/profile/ProfileCorrectionHistory.tsx`
- `frontend/src/components/profile/ProfileEvidencePanel.tsx`
- Current verification: backend `2255 passed, 1 skipped`; frontend unit `492 passed`; Playwright `283 passed, 50 skipped`; production build passed.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: inspect the six current screenshots at native dimensions; inspect the correction/history/evidence interaction contract; verify information hierarchy, Chinese clinical language, evidence locator honesty, red-box uniqueness, draft recoverability, and wide-screen efficiency from 1080P through 4K.
- Out of scope: editing files, making enrollment decisions, reading raw clinical materials outside this workspace, accepting test counts without visual inspection, security testing, mobile/narrow-screen design, and starting another conference.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- Findings name the exact screenshot or component/test evidence and distinguish observed defect, inference, and recommendation.
- A pass verdict is allowed only after inspecting all three desktop widths and both Profile overview and evidence-panel states.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-08-23 22:42:15: Conference initialized by `hermes_workflow_guard.py init-conference`.
