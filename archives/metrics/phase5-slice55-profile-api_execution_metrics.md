# Execution Metrics: phase5-slice55-profile-api

| Role | Provider | Model | Status | Duration | Tools | Result |
|---|---|---|---|---:|---:|---|
| `worker_01` | `cms-smk` | `deepseek-v4-flash` | completed | 1104.767s（含同会话补跑） | runner 未单列 | 领域合同、13 条泳道及确定性首屏投影完成；Codex 修复跨运行泳道身份冲突。 |
| `worker_02` | `cms-smk` | `deepseek-v4-flash` | completed | 1491.649s（含同会话补跑） | runner 未单列 | 不可变修订仓储、历史与投影服务完成；Codex 补齐定位批量权威读取。 |
| `worker_03` | `cms-smk` | `deepseek-v4-flash` | completed | 1051.703s | runner 未单列 | 真实 HTTP API、中文 DTO 和性能回归完成；Codex 补齐真实定位详情。 |

## Codex Verification

- Patient Profile 相关组合回归：`111 passed`。
- 500 事实 API 回归：`1 passed`，`26.63s`。
- V2 全量：`2144 passed, 1 skipped, 139 warnings, 2 subtests passed`，`647.19s`。
- 唯一跳过：既有 Phase 4 oMLX 真实探针工件未提供。
- `compileall` 通过，保留既有 `app/models.py:88` 转义警告；`git diff --check`、Trellis validate、Hermes 执行审计通过。
