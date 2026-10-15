# Phase 1 视觉验收同会话复核

继续使用会话 `019ff816-9fb5-7000-990c-36ce6ad29bd4`。这是只读复核轮，不是新的审查会话，也不授权修改任何文件。

Hard boundaries:

- 仅在当前工作区内进行只读复核，不修改源代码、测试、截图或任务记录。
- 不读取工作区外的临床原始资料，不做安全性测试。
- Runner-managed output path: `runs/conference/enrollment_phase1_visual_acceptance/visual_pi_k3_256k_round2.md`. Never write this path with tools; return the complete report and let the runner persist it.
- Codex 保留最终验收权。本轮只判断首轮问题是否关闭以及是否允许进入 Phase 1.5。

Read these files only:

- `AGENTS.md`
- `context/enrollment_phase1_visual_acceptance_conference_context.md`
- `plans/codex_main_venue_enrollment_phase1_visual_acceptance.md`
- `.trellis/tasks/08-13-phase1-frontend-shell/prd.md`
- `.trellis/tasks/08-13-phase1-frontend-shell/design.md`
- `runs/conference/enrollment_phase1_visual_acceptance/visual_pi_k3_256k.md`
- `frontend/src/api/wire.ts`
- `frontend/src/domain/mappers.ts`
- `frontend/src/domain/viewModels.ts`
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/pages/WorkbenchPage.tsx`
- `frontend/src/components/review/RuleTree.tsx`
- `frontend/src/components/review/ExpressionView.tsx`
- `frontend/src/test/`
- `frontend/e2e/`
- `frontend/e2e/screenshots/`

你在首轮报告中给出“阻断并修订”，核心阻断项是工作台把冻结 fixture 中的时间约束错误映射为 `时间窗：undefined undefined undefined 天`。Codex 已按 Wire -> ViewModel -> UI 的真实数据契约修复根因，并连带处理首轮列出的重要问题。请不要采信下面的完成声明；请重新读取当前代码、测试、截图，并在可达时亲自检查 `http://127.0.0.1:4173/`，独立判断原阻断项是否关闭、是否引入新缺陷。

## 本轮必须复核的修订

1. 时间约束已按 fixture 的 `anchor_type / direction / lower_bound_days / upper_bound_days / half_life_multiplier / allow_partial_date` 建模和映射，不再使用不存在的 `relation / reference / window_days`。当前示例应显示为自然中文 `随机前 28 天内`，页面不得出现 `undefined`、`null` 或技术字段名。
2. 年龄等单位已中文化，页面不得出现 `18 year`；`xULN` 应以用户可理解的中文表达展示，且不得重复单位。
3. “今日工作”每条事项展示关联规则编号；冲突、明确障碍和到期事项应直接携带高风险规则组件定位，用户从事项进入对应证据路径应不超过三次操作。
4. 合成演示文件名不再暴露 `clear`、`gap_conflict` 等实现标签。
5. 父规则应汇总并明显显示子项状态，例如“子项有明确障碍”“子项有冲突”“子项需处理”，同时保持父子层级清晰。
6. 工作台未指定受试者时应优先打开有风险的个例和对应风险组件，而非默认打开无风险个例。
7. 不仅工作台，全部 9 个一级页面都应在 1440 宽度下以 150% 和 200% 缩放代理检查无页面级横向滚动、遮挡和无意义断行；390 窄屏也应可用。
8. 对用户可见的必做检查规则编号统一显示为 `必做-01`、`必做-01a` 等中文标签，内部 `REQ-` 标识不得出现在界面。内部数据契约无需改名。

## 可核查的验证锚点

- 单元/组件测试：19 个文件、137 项通过。
- 前端构建：通过。
- Playwright：153 项通过、27 项因项目视口设计而有意跳过、0 项失败；严重/致命可访问性问题为 0。
- 截图已重新生成于 `frontend/e2e/screenshots/`，至少重看桌面/窄屏的今日工作、审核工作台、受试者个例，以及 200% 缩放工作台。
- 重点代码：`frontend/src/api/wire.ts`、`frontend/src/domain/mappers.ts`、`frontend/src/domain/viewModels.ts`、`frontend/src/pages/TodayPage.tsx`、`frontend/src/pages/WorkbenchPage.tsx`、`frontend/src/components/review/RuleTree.tsx`、`frontend/src/components/review/ExpressionView.tsx`。

## 输出要求

沿用首轮输出结构，给出一份完整更新报告。逐项说明首轮阻断项和重要问题是“已关闭”“仍存在”还是“证据不足”，并注明你实际核查的页面、截图或代码。重点再次从不熟悉计算机和 AI 的中文资深医学监查人员视角检查：首屏风险是否直观、下一步是否明确、规则与证据是否可追溯、父子规则是否有真实层级、缩放和窄屏是否可用、中文是否原生。

最后必须只给出以下两个明确结论之一：

- `接受进入 Phase 1.5`
- `阻断并修订`，并附可复现的剩余阻断项。

不要因为 Codex 提供了验证数字就直接接受，也不要把后续阶段功能缺失错误判作当前只读前端壳的阻断项。
