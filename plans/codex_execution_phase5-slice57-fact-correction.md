# Codex Execution Plan: phase5-slice57-fact-correction

Objective: 实现 Phase 5 Slice 5.7：有理由的人工临床事实修订、可证明的影响范围与保守节点回退、不可变新事实/Profile revision、重启取消迟到结果和重复回调幂等，以及最小中文宽屏修订界面；不修改原 OCR、候选或旧事实，不进入 Phase 6/7 入排结论或 ActionRequest。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 领域与存储：冻结人工事实修订合同、修订记录、旧值/新值/理由/定位/操作者/时间/影响范围，新增迁移和仓储，所有历史不可变且旧 Profile 可回放。 | `runs/execution/phase5-slice57-fact-correction/worker_01.md` |
| `worker_02` | 影响与执行：基于 locator、文档、事实和 FactRuleLink 计算局部重算；无法证明时扩大到审核节点；复用持久 Job/Step/Checkpoint/Lease，覆盖取消、重启、迟到回包、重复回调和局部失败。 | `runs/execution/phase5-slice57-fact-correction/worker_02.md` |
| `worker_03` | 用户界面：在 Patient Profile 提供最小中文事实修订入口，先核对原值、来源和影响范围，要求理由后提交；显示新修订与旧修订历史，不出现入排结论或程序员标签。 | `runs/execution/phase5-slice57-fact-correction/worker_03.md` |

依赖顺序固定为 `worker_01 -> Codex 检查/聚焦测试 -> worker_02 -> Codex 检查/聚焦测试 -> worker_03`。三个工作项不并行写同一合同，避免 UI 或任务层依据尚未冻结的字段自行发明接口。

## Implementation Contract

- 修订是追加式领域事件，不是 SQL `UPDATE`。旧实体和旧 Profile 保持可回放；新链头通过明确修订关系产生。
- 允许修订事实、事件和用药/治疗暴露；冲突与资料期望只允许重新投影。
- 先计算并向用户显示影响范围，再提交；范围无法完整证明时必须显示“将重新整理本审核节点全部事实”，不能假装局部。
- 任务成功提交时，新实体、修订记录、新 Profile 与检查点在写栅栏事务内保持一致；失败时上一活动 Profile 不变。
- 前端不得把本功能写成“修正 AI”“覆盖结果”或最终医学裁决。中文动词使用“修订事实记录”“核对原文”“重新整理受影响信息”。

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Codex 逐阶段复核 worker diff、合同与迁移，运行聚焦测试后才放行下一 worker。终局要求后端全量、前端全量/构建、1080P/2K/4K Playwright、取消/恢复故障注入、`git diff --check`、Trellis validate 和执行工作流 audit；Phase 5.8 测试者仍不启动。
