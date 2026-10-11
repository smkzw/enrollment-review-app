# Codex Main-Venue Plan: phase5-clinical-facts-profile-planning

Date: 2026-08-22
Objective: 只读审查 Phase 5 临床事实与 Patient Profile 规划。依据 context/phase5-clinical-facts-profile-planning_context.md 和当前 PRD/代码，分别挑战领域溯源、Agent/Gate/Job 运行图、临床用户体验与切片验收；主席综合必须修订、延后和拒绝项。不得修改文件或读取工作区外临床资料。

## Task Decomposition

1. Verify the active Phase 4 evidence/version authority and the existing Phase 5 placeholder contracts.
2. Challenge clinical fact provenance, source strength, polarity, partial dates, duplicates, and conflicts.
3. Challenge the Evidence Normalizer -> deterministic gate -> immutable publication -> Profile projection job graph.
4. Challenge the senior-monitor Profile information hierarchy, evidence navigation, and expectation-gap presentation.
5. Synthesize must-fix, deferred, and rejected proposals into a dependency-ordered Phase 5 implementation plan.

## Source Packet

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`
- `context/phase5-clinical-facts-profile-planning_context.md`
- `app/domain/contracts/evidence.py`
- `app/domain/contracts/normalization.py`
- `app/storage/models.py`
- `app/storage/repositories.py`
- Phase 4 evidence processing, locator, correction, and job runtime modules under `app/`
- Profile frontend pages/components and their tests under `frontend/src/`

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | declared `alibaba`, scheduled actual `cms-smk` | declared `qwen3.8-max`, actual `deepseek-v4-flash` max | `runs/conference/phase5-clinical-facts-profile-planning/general_pi_qwen38.md` |
| `general_grok46` | `grok-build` | `grok-4.6` | `runs/conference/phase5-clinical-facts-profile-planning/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- Record actual provider/model/session identity from runner metadata; do not infer it from role filenames.
- Initial dispatch starts after prompt preflight. Optional follow-ups run only if the first pass is materially incomplete.
- No late output will be called incorporated unless Codex reopens and reviews it before finalizing the plan.
- 21:27:49 Grok Build started; completed one pass in 351.651 seconds, session `a46a01dd-1b45-422c-bd13-905bf27570ca`, no fallback.
- The guard-generated Pi command was rejected before model dispatch because duplicate schedule arguments conflicted with the live manifest. No round was consumed. The live role manifest's daytime primary was then dispatched once.
- 21:28:57 Pi/CMS-SMK DeepSeek V4 Flash max started; completed one pass in 206.803 seconds, session `01a029a9-206b-7000-8d73-c342abe09c62`, no fallback.
- Both first passes were substantive and converged on the blocking identity, candidate/publication, locator, polarity, conflict, and phase-boundary defects. No follow-up round was needed.

## Codex Verification Checklist

- Compare every recommendation with the approved Phase 5 boundary and current code.
- Confirm no proposal allows stale snapshot/revision publication or silent earlier-stage rewriting.
- Confirm every material fact can retain file/version/page/excerpt/image-or-text location.
- Confirm silence creates an expectation gap, never a negative fact.
- Confirm conflicts remain side by side and unresolved unless a recorded correction changes the source.
- Confirm Profile first-screen emphasis and 1080P/2K/4K verification are included in implementation acceptance.
- Confirm tester roles and conference roles remain separate.
