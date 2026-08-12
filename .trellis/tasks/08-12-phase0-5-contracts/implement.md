# Phase 0.5 实施步骤

1. 创建领域枚举、基础值对象、规则/证据/受试者/审核/行动/Job 合同。
2. 实现状态-gap Gate、Agent 权限 Gate、规则表达式结构校验和节点 rollup 纯函数。
3. 建立合同测试和历史错误族的最小合成用例。
4. 编写确定性 schema 生成器，产出 JSON Schema 和 OpenAPI 草案。
5. 创建 3 个自包含 fixture 并验证 EvidenceSpan、Patient Profile、阶段和状态。
6. 记录 4 个语义 Agent 合同及确定性 Gate 的审计边界。
7. 编写设计 token、响应式、证据查看器、键盘和中文状态词合同。
8. 编写 Phase 1 UAT 任务、指标、临时阈值和停止条件。
9. 重跑完整测试、schema 重生成差异检查和独立 checker。

## 2026-08-13 第五次复核后的检查点

- 服务端只读发布注册表与版本化审核上下文已落地，发布函数不能再用待发布对象自建信任。
- 方案确认事件、来源记录、RuleSet 完整哈希、typed Candidate 和 Fixture Fact/Span 已进入同一发布闭包。
- V2 `115 passed + 2 subtests`；默认全套 `245 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品双跑一致。
- 当前仍等待同一 Luna checker 第六次验收；任务保持 `in_progress`，Phase 1 未创建。
