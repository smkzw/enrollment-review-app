# Phase 0.5 领域与交互合同

## Goal

冻结 fixture/v1、领域状态、API、Agent/Gate、Job 事件、错误信封和交互合同，为 React 产品壳提供唯一数据契约。

## Requirements

- 使用 Pydantic v2 定义 `fixture/v1`，并生成稳定 JSON Schema；合同覆盖项目/方案、受试者/阶段、Patient Profile、规则表达式、证据、判断、行动、运行差异和 Job 事件。
- RuleExpression 必须表示有限嵌套 `ALL/ANY/NOT`、原子谓词、阈值/单位、时间锚点/窗口、例外树和研究者复合判断。
- 判断状态与 gap_type 分离；通过确定性 Gate 拒绝不合法组合，模型候选不能直接形成最终状态。
- 节点汇总为纯函数，覆盖入选/排除组件状态、阻断等级、EvidenceExpectation、溯源待办、计数和固定排序。
- 至少 3 名示例受试者：未发现明确障碍、明确障碍、缺口/冲突；证据定位覆盖 bbox、text_range、page_excerpt、page_only。
- 定义 Protocol Deconstructor、Evidence Normalizer、Eligibility Assessor、Safety/Provenance Critic 的输入、输出、写权限、PromptVersion、Gate、重试、幂等和停止条件。
- 形成 OpenAPI 草案和统一中文错误信封；前端不得依赖旧 Markdown 或模型自由文本。
- 冻结设计 token、密度、键盘、证据查看器、宽/窄屏降级和页面级滚动合同。
- 编写不少于 10 项 Phase 1 脚本化 UAT，记录测量方法、临时阈值、错误分类和停止条件。

## Acceptance Criteria

- [x] 所有 fixture 通过 Pydantic 和生成 JSON Schema 验证，Schema 快照变更必须显式审阅。
- [x] 历史 AND/OR、复合研究者判断、时间窗、例外、否定/沉默和指标串项均有项目无关合同测试。
- [x] 节点汇总真值表覆盖全部组件状态、gap、阻断和溯源组合，顺序与计数确定。
- [x] Agent 写权限测试证明语义节点只能产生 draft/candidate/CriticRun，不能发布最终组件状态。
- [x] OpenAPI 草案、错误信封和前端 fixture 使用同一版本字段与枚举。
- [x] 3 名示例受试者包含可点击 EvidenceSpan、Patient Profile 和阶段隔离信息。
- [x] 交互合同在 1280/1440/1920、窄窗口及 100/150/200% 缩放下有可执行验收描述。
- [x] UAT 至少 10 项；临时门槛为无辅助完成率 >=90%、错误结论 0、关键证据 <=3 次操作可达，并明确须用户批准。
- [ ] 独立 checker 无阻断 findings，Codex 接受后才进入 Phase 1。

## Notes

- 本阶段不创建 SQLite 业务表、不调用真实 LLM/OCR、不开始临床全流程重审。
- Qwen 3.8 不属于本任务执行或检查路线。
