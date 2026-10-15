# V2 总体设计约束

## Architecture

1. React/TypeScript 前端只依赖版本化 API 契约，不读取旧 Markdown 报告作为事实源。
2. FastAPI API 层调用 application/workflow；领域层不依赖框架、数据库或模型供应商。
3. SQLite/WAL 持久化版本化业务实体、Job、AgentCall 和审计记录；原始文件按内容哈希保存。
4. 语义 Agent 只写 draft/candidate；确定性 Gate 和 evaluator 负责发布、组件状态、rollup 与 ActionItem。
5. Patient Profile、看板和报告是可重建投影，不拥有独立临床事实。
6. Legacy 与 V2 写入路径物理隔离，并通过自动化测试证明旧项目不被修改。

## Non-negotiable Contracts

- RuleExpression 保留父子层级、AND/OR/NOT、阈值、单位、时间锚点、例外和研究者复合判断。
- EvidenceSpan 定位能力按 `bbox > text_range > page_excerpt > page_only` 降级并显式记录。
- ReviewEpisode 固定阶段、规则版本、证据快照、锚点日期和运行 revision。
- AgentCall 固定模型、推理参数、PromptVersion、SchemaVersion、输入/输出哈希、耗时、费用和 Gate 结果。
- 所有副作用幂等，乐观 revision 拒绝 stale 结果；人工 override 可追溯且可重新打开。

## Acceptance Ownership

- 实现 Worker 不能关闭自己的任务；独立 checker 提交问题和证据。
- Codex 以自动化测试、数据库/文件状态、真实浏览器和临床回归夹具决定阶段是否完成。
- 任何模型会商结论仅为建议，不替代本地事实、测试或用户已冻结的决定。
