# Execution Output: phase5-slice58d-phase-closure-repair-20260825 - worker_01 follow-up

## Boundary And Context Check

已读取指定 context、plan、Agent runner、execution service 及两组测试。仅修改 Worker 01 授权文件；未调用 D001、oMLX，未修改 Worker 02/03 研究工件或生产路径。

## Work Performed

- `_render_unit` 为每个 source member 增加与 `source_span_ids` 同序的全局 `source_span_indexes`。
- 强化中文 prompt 合同：证据索引必须来自同一已展示 source member；来源充分时优先一条直接证据及简洁说明。
- 为 `PhaseApplicabilityAgentRunner.run()` 增加通用 `on_attempt` callback。
- 每次 `parsed`、`schema_invalid` 或 `transport_failed` attempt 完成后，execution service 立即原子 checkpoint：
  - parsed output/errors
  - raw output hash
  - session/recovery 状态
  - 不持久化原始模型文本
- 中断恢复时保留既有 attempt 历史，仅重试未接受批次。

## Artifacts And Evidence

本轮涉及：

- `app/agents/phase_applicability.py`
- `app/services/phase_applicability_execution.py`
- `tests/v2/protocols/test_phase_applicability_live_execution.py`
- `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`

此前 Worker 01 实现仍保留：

- `app/agents/phase_applicability_transport.py`
- `app/agents/__init__.py`
- `app/services/__init__.py`
- `scripts/run_phase_applicability_acceptance.py`

新增测试验证：

- prompt 中 target/context/source member 的 span ID 与全局 span index 一一对应；
- repair 调用中断后，首个 schema-invalid attempt hash 与错误已持久化；
- 重启后只重新执行未接受批次，并保留中断前 attempt 历史。

## Commands And Observations

- 聚焦回归：

  `.venv/bin/pytest -q ...`

  结果：`43 passed, 5 warnings`

- Python `compileall`：通过。
- `git diff --check`：通过。
- 新增文件尾随空白检查：通过。
- `scripts/run_phase_applicability_acceptance.py --help`：通过。
- 工作区存在大量其他既有改动，本轮未触及。

## Blockers Or Missing Environment

- 未执行真实 D001/oMLX 调用，故未验证 1689/1433/235 实际闭包。
- 系统 Python 缺少 SQLAlchemy；使用既有 `.venv` 验证，未安装依赖。
- 最终临床、矩阵及生产验收仍由 Codex 负责。

## Rerun Requests Or Next Step

请 Codex review 后，用首个冻结批次重新进行真实验收，重点确认模型能够使用新增全局 span 映射，并检查中断 checkpoint 中 attempt hash、校验问题、session/recovery 状态及恢复后的严格 gate 结果。
