# Codex Execution Plan: phase1_5_uat_package

Objective: 补齐Phase 1.5正式UAT任务包、统一界面试用复位和页面版本，不进入Phase 2

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现中央状态清单、四调用点复用、帮助页两步复位、页面版本及组件测试 | `runs/execution/phase1_5_uat_package/worker_01.md` |
| `worker_02` | 补齐14项参与者任务卡的明确目标，编写记录人员指南和正式批次汇总模板 | `runs/execution/phase1_5_uat_package/worker_02.md` |
| `worker_03` | 增加真实浏览器复位/版本/关键任务可达性测试，执行中文原生与无占位审计 | `runs/execution/phase1_5_uat_package/worker_03.md` |

## Manager

| Role | Provider | Model | Report |
|---|---|---|---|
| `finite_code_manager_cursor` | `cursor-cli` | `auto` | `runs/execution/phase1_5_uat_package/manager.md` |

## Sequence And Acceptance

1. `worker_01` 先完成实现和组件测试。
2. `worker_02` 仅处理正式用户试用文档，可与实现解耦。
3. `worker_03` 在前两项完成后，从用户视角编写独立浏览器验收，不修改实现来规避失败。
4. 管理者核对三份产物、异常路径、测试证据和未覆盖项；有缺口时给出同会话定向返工请求。
5. Codex 运行全量前端测试、构建、真实 Chrome 多缩放视觉检查并完成最终接受。

停止条件：本执行包验收后仍保持 `.trellis` 门状态为 `awaiting_user_uat`；不得标记 Phase 1.5 正式用户试用通过，不得启动 Phase 2。
