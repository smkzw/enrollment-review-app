# V2 分阶段实施

1. Phase 0：冻结 legacy 基线、建立只读隔离、依赖决策和 V2 目录。
2. Phase 0.5：冻结领域、API、Agent/Gate、Job、fixture 和交互合同。
3. Phase 1：以 stub API 构建可直接演进的 React 产品壳和核心工作台。
4. Phase 1.5：用量化任务和真实浏览器完成 UAT，未通过则继续原型迭代。
5. Phase 2-7：依次完成数据层、方案解构、OCR/证据、Patient Profile、审核与 Action/报告闭环。
6. Phase 8：用新项目执行方案到报告的临床全流程验证，偏差必须修复共享根因。
7. Phase 9：切换、清理、桌面启动、帮助页和最终验收。

每个阶段建立 Trellis 子任务，包含 PRD、设计、实施、上下文清单和独立检查证据；不得跨越未通过的退出门槛。
