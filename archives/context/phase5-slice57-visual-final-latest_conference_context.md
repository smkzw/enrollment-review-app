# Conference Context: phase5-slice57-visual-final-latest

Created: 2026-08-23 21:34:03
Objective: 以懒惰但专业的中文临床试验医学监查员视角，独立审查 Phase 5.7 Patient Profile 人工事实修订、历史版本对比、原文回源和宽屏交互；重点识别误导、版本混用、信息层级、中文原生性、1080P至4K视觉效率与可恢复性问题
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

- `frontend/e2e/test-results/profile-correction-宽屏-Profile-修订：原文联动、只读预览、持久完成状态与追加历史-desktop-1080p/{correction-preview.png,correction-history.png}`
- `frontend/e2e/test-results/profile-correction-宽屏-Profile-修订：原文联动、只读预览、持久完成状态与追加历史-desktop-2k/{correction-preview.png,correction-history.png}`
- `frontend/e2e/test-results/profile-correction-宽屏-Profile-修订：原文联动、只读预览、持久完成状态与追加历史-desktop-4k/{correction-preview.png,correction-history.png}`
- `frontend/src/components/profile/{ProfileFactCorrectionDialog.tsx,ProfileCorrectionHistory.tsx,ProfileEvidencePanel.tsx}`
- `frontend/src/pages/SubjectsPage.tsx`, `frontend/src/styles/profile.css`, and `frontend/e2e/profile-correction.spec.ts`
- `reviews/codex_execution_phase5-slice57-review-remediation-latest_review.md`
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: actual visual inspection of all six current screenshots; Patient Profile correction preview, historical correction entry, exact historical title/page/excerpt, original-evidence action, hierarchy, Chinese clinical wording, density, empty-space use, scrolling, focus/recovery, and 1080P/2K/4K consistency. Browser or Playwright may be used read-only when useful.
- Out of scope: editing source, changing clinical rules, retesting raw clinical materials, security review, narrow/mobile layouts, or accepting the feature on Codex's behalf.

## Success Criteria

- The participant actually opens and visually inspects all six screenshots, records concrete observations by viewport, and distinguishes screenshot evidence from source-code inference.
- The participant challenges whether a time-poor senior medical monitor can understand what changed, why, which historical Profile is shown, and how to return to the original source without version confusion.
- Findings identify exact UI region, user consequence, severity, and a concrete remedy; generic style preferences are not sufficient.
- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

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

- 2026-08-23 21:34:03: Conference initialized by `hermes_workflow_guard.py init-conference`.
