# Codex Execution Plan: phase5-slice56-profile-ui

Objective: 实现 Phase 5 Slice 5.6：把受试者 Patient Profile 页面从旧 fixture/旧审核详情切换到 Slice 5.5 真实 HTTP API，建立严格运行时解码与前端领域适配；以中文原生临床监查工作台呈现 13 条历时泳道、后端首屏重点、冲突与资料期望；复用 Phase 4 原件查看能力，实现文件滚动、真实定位和仅真实 bbox 红框；使用流体宽屏布局完成 1080P、2K、4K 浏览器验收，不提前显示 Phase 6/7 结论或行动，也不启动 Phase 5.8 测试者。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 设计并实现 Patient Profile v2 前端 wire 合同、严格运行时解码、HTTP repository、领域 ViewModel 适配及契约测试；fixture 仅作为显式隔离测试实现，不进入正式默认路径。 | `runs/execution/phase5-slice56-profile-ui/worker_01.md` |
| `worker_02` | 重构受试者 Patient Profile 页面和组件状态：使用正式项目目录选择审核节点、读取真实 Profile；按后端 highlights 和 13 条泳道呈现首屏/全量历时信息、生成中/失败/陈旧/空态，去除旧总体结论和旧 fixture 文案。 | `runs/execution/phase5-slice56-profile-ui/worker_02.md` |
| `worker_03` | 实现宽屏 Patient Profile 与 Phase 4 原件查看器联动：流体三栏/详情布局、冲突并列、定位详情和证据滚动；只有真实 bbox 绘制当前单框；补齐组件、可访问性、构建及 1080P/2K/4K Playwright 验收。 | `runs/execution/phase5-slice56-profile-ui/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

1. Execute workers sequentially in dependency order and review every changed file; do not merge model output by confidence.
2. Verify production Profile data goes through the new HTTP repository and strict decoder. Fixture mode must be explicit and isolated.
3. Verify the first-screen set is exactly the backend highlights, all 13 lanes remain available, and no Phase 6/7 conclusion or action leaks into the page.
4. Verify every locator against the selected Profile revision and Phase 4 viewer. Draw one transparent outside red outline only for a real bbox; never synthesize coordinates.
5. Run focused and full frontend tests, TypeScript/Vite build, Chinese terminology scan, and actual browser checks at 1920x1080, 2560x1440 and 3840x2160 plus 100/150/200 percent zoom. Check overflow, text clipping, overlap, sticky header, keyboard focus and basic axe.
6. Do not launch the Phase 5.8 Cursor/MiniMax/OX Alpha testers in this execution packet.
