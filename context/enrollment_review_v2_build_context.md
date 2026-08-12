# Task Context: enrollment_review_v2_build

Created: 2026-08-12 19:09:33
Objective: 依据V2架构设计与分阶段计划构建本地单用户AI主导的临床试验入排审核工作台，先完成Phase 0/0.5/1并在Phase 1.5用户验收前停止后台核心实施
Task type: `long_horizon_code`
Risk: `high`
Selected agent route: `cms-smk` / `deepseek-v4-flash` / `max`

## Trigger Reason

This task was initialized through the Codex x Hermes complex-task entrypoint because it is expected to involve more than three execution steps, research/writing/report/code/report-visual work, or source-grounded verification.

## Source Of Truth

- TODO: Add authoritative local files, extracts, datasets, screenshots, URLs, or user-provided materials.
- Do not add production paths unless the user has explicitly authorized reading them for this task.

## Scope

- In scope: TODO
- Out of scope: TODO

## Success Criteria

- TODO

## Risk Boundaries

- Do not write to production paths until Codex review gate passes and writable paths are explicit.
- The delegated agent is not final authority; Codex owns verification and acceptance.

## Timeout Policy

- Do not mark the delegated agent failed for slow response alone.
- For complex or artifact-heavy work, wait and poll generously; use conference mode when multiple independent model perspectives are needed.
- Failure requires terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no progress after hard wait plus one retry.
- A provider catalog/auth/transport preflight is diagnostic, not a live capability verdict: timeout, auth refresh failure, or malformed probe output must be recorded and followed by one real route attempt. Only a missing executable or explicit invalid/retired/unlisted model may stop before that attempt.

## Loop Log

- 2026-08-12 19:09:33: Task initialized by `tools/hermes_workflow_guard.py init-task`.
