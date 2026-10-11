# Codex Execution Plan: phase5-slice55-profile-api

Objective: 实现 Phase 5 Slice 5.5：基于已发布 v2 事实、事件、暴露、冲突与资料期望，生成可回放的不可变 Patient Profile revision、13 条主题泳道、确定性首屏突出集合、状态与 Phase 4 证据深链，并提供真实 HTTP API 和 500 事实性能回归。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 设计并实现 Patient Profile v2 领域合同、13 条泳道归类、确定性首屏突出规则与严格验证。 | `runs/execution/phase5-slice55-profile-api/worker_01.md` |
| `worker_02` | 设计并实现不可变 Patient Profile revision 仓储、权威元组/镜像/历史/链头校验与 Profile 投影服务。 | `runs/execution/phase5-slice55-profile-api/worker_02.md` |
| `worker_03` | 设计并实现薄 Patient Profile HTTP API、中文原生 DTO、状态/历史/证据深链及 API/500 事实性能测试。 | `runs/execution/phase5-slice55-profile-api/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

1. Execute workers in dependency order and review every changed file; do not merge model output by confidence.
2. Confirm 13 lanes, highlight allowlist, typed source identities, locator closure, immutable history and stale semantics with deterministic tests.
3. Add missing cross-layer checks, runtime strict-decode counterexamples and a measured 500-fact projection benchmark.
4. Run focused tests, adjacent Phase 5 storage/migration/API tests, then full `tests/v2`, compileall, `git diff --check` and Trellis validation.
5. Do not claim browser or visual acceptance in Slice 5.5; that belongs to 5.6. Do not launch Phase 5.8 testing routes.
