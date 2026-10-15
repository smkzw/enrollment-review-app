# Execution Output: phase5-protocol-control-recovery-20260831 - worker_02

## Boundary And Context Check

- 仅执行分配项：新增确定性测试。
- 未修改生产代码、数据库、生成物或外部环境。
- 变更限定于 `tests/v2/services/test_protocol_control_execution.py`。

## Work Performed

新增测试：

`test_recovery_requeues_interrupted_dynamic_step_without_replaying_source_or_discovery`

覆盖以下行为：

1. 使用多个 discovery batch，确保已完成发现批次不止一个。
2. 在动态 `deep_*` 步骤执行期间注入 `ProcessDeath`。
3. 使租约过期并运行 `recover_expired_jobs`。
4. 验证中断动态步骤重新进入 `queued`，随后按新租约恢复执行。
5. 验证已完成 discovery 步骤保持 `completed`、`attempt == 1`，且没有再次调用 discovery transport。
6. 删除冻结结构快照文件后再执行恢复流程，验证恢复依赖持久化 payload/checkpoint，不重新读取来源结构文件。
7. 验证恢复后动态深析步骤正常完成，任务最终为 `completed`。

## Artifacts And Evidence

- 修改文件：`tests/v2/services/test_protocol_control_execution.py`
- 新增测试约 94 行。
- 测试断言包括：
  - `recovery.requeued_jobs`
  - 中断动态步骤从 `running` → `queued` → `completed`
  - discovery transport 调用次数恢复前后不变
  - discovery 步骤每个仅产生一次 `step_started`
  - 删除 snapshot blob 后任务仍可完成
  - 动态 deep transport 仅执行中断步骤及其余尚未完成步骤

## Commands And Observations

首次使用系统 `pytest`：

```text
ModuleNotFoundError: No module named 'sqlalchemy'
```

仓库已有 `.venv`，未安装依赖。使用项目虚拟环境执行：

```text
.venv/bin/pytest -q tests/v2/services/test_protocol_control_execution.py \
  -k recovery_requeues_interrupted_dynamic_step_without_replaying_source_or_discovery
```

结果：

```text
1 passed, 6 deselected
```

完整同域测试：

```text
.venv/bin/pytest -q tests/v2/services/test_protocol_control_execution.py
```

结果：

```text
7 passed
```

格式修正后再次执行新增测试：

```text
1 passed, 6 deselected
```

仅观察到既有第三方库 deprecation warnings；无测试失败。

## Blockers Or Missing Environment

- 系统 Python 环境缺少 `sqlalchemy`。
- 项目 `.venv` 已包含所需依赖，使用 `.venv/bin/pytest` 后无阻塞。
- 未执行项目全量测试；Codex 可在整合 worker_01 变更后决定是否运行更大范围回归。

## Rerun Requests Or Next Step

- Codex 应复核新增测试与 worker_01 恢复入口变更的交互。
- 建议整合后重跑：
  - `tests/v2/services/test_protocol_control_execution.py`
  - `tests/v2/workflow/test_runner.py`
  - `tests/v2/workflow/test_jobstore.py`
- Codex 保留最终恢复语义、反过拟合边界及临床/发布接受权。
