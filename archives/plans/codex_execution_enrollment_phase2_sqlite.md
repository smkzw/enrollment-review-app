# Codex Execution Plan: enrollment_phase2_sqlite

Objective: 实现并验证Phase 2 SQLite领域层与持久任务，严格遵循Trellis任务08-14-phase2-sqlite-domain-jobs

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现SQLite配置、SQLAlchemy基础设施、Alembic迁移、备份恢复与写边界测试 | `runs/execution/enrollment_phase2_sqlite/worker_01.md` |
| `worker_02` | 实现领域ORM、合同编解码、仓储、幂等、乐观并发与过期范围 | `runs/execution/enrollment_phase2_sqlite/worker_02.md` |
| `worker_03` | 实现持久Job状态机、租约恢复、取消重试、V2 API/SSE与故障注入测试 | `runs/execution/enrollment_phase2_sqlite/worker_03.md` |

## Manager

| Role | Provider | Model | Report |
|---|---|---|---|
| `complex_manager_cursor` | `cursor-cli` | `auto` | `runs/execution/enrollment_phase2_sqlite/manager.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
