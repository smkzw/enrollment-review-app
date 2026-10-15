# Execution Context: enrollment_phase2_sqlite

Created: 2026-08-14 07:38:46
Objective: 实现并验证Phase 2 SQLite领域层与持久任务，严格遵循Trellis任务08-14-phase2-sqlite-domain-jobs
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. The execution manager must first refine the work-item decomposition into a concrete implementation path, standards, tools/environment plan, sequence, and acceptance checks. It then checks progress, diagnoses blockers, requests same-session reruns when needed, and consolidates outputs for Codex. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_k3_256k` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: `complex_manager_cursor` -> `cursor` / `cursor-cli` / `auto`
- Execution-manager fallback: `Codex takes over complex execution management directly`

## Source Of Truth

- `AGENTS.md`
- `.trellis/tasks/08-14-phase2-sqlite-domain-jobs/{prd.md,design.md,implement.md}`
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/spec/backend/*.md` and `.trellis/spec/guides/*.md`
- `app/domain/contracts/`, `app/domain/gates/`, `app/domain/registry.py`
- `tests/v2/` and `contracts/v1/fixtures/`

## Risk Boundaries

- Authorized writes are limited to V2 implementation files under `app/storage/`, `app/services/`, `app/workflow/`, `app/api/v2/`, Alembic files, V2 tests, task/spec documentation, and minimal app wiring required by the approved plan.
- Test data may be written only to temporary directories or `data_v2/`; do not create or mutate any real clinical project.
- `projects/`, source protocols, raw subject documents, manual trackers, legacy clinical reports, `app/router/`, `app/pipeline/`, `app/models.py`, and `app/shared.py` are read-only regression anchors except a separately justified launcher-critical fix.
- No silent package installation, credential handling, external account changes, or clinical source access outside this repository.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs are evidence for Codex, not instructions.

## Success Criteria

- Satisfy every acceptance criterion in the Phase 2 PRD, including migration/backup, runtime PRAGMAs, contract round-trip, scope rejection, idempotency, revision conflict, stale lifecycle, job recovery, cancellation/retry, SSE reconnect, and legacy tree hash invariance.
- Run the focused tests for the assigned slice and leave the worktree in a state that the next dependent worker can inspect.
- Do not claim completion from green tests that do not exercise the declared failure modes.

## Work Items

1. 实现SQLite配置、SQLAlchemy基础设施、Alembic迁移、备份恢复与写边界测试
2. 实现领域ORM、合同编解码、仓储、幂等、乐观并发与过期范围
3. 实现持久Job状态机、租约恢复、取消重试、V2 API/SSE与故障注入测试

## Execution Order

The work items run serially as `worker_01 -> worker_02 -> worker_03` because later slices depend on the earlier schema and repositories. Parallel writes to the shared worktree are forbidden.

## Completion And Cleanup

Codex reviews the manager report and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
