# Phase 0.5 合同候选实施证据

**日期：** 2026-08-13
**状态：** 待独立 checker 验收；本文件不表示 Phase 0.5 已冻结。

## 已形成的合同

- Pydantic `fixture/v1` 领域模型：项目、正式方案版本、独立研究期别、受试者、审核节点、规则树、证据快照、事实、Patient Profile、判断候选、最终判断、行动、Agent 调用、Gate、Job 和运行差异。
- 有限递归 `ALL / ANY / NOT` 规则表达式；三值 Evaluator 确定性计算比较器、规范单位、时间锚点/窗口及独立例外树，缺失、冲突或不可比时保守返回 unknown。首版禁止隐式单位换算，`on` 不能夹带区间或半衰期参数。
- 每个原子谓词有 RuleSet 内唯一的 `predicate_id`；AssessmentCandidate 必须逐项输出谓词真值、事实与原因引用，Gate 与确定性 Evaluator 逐谓词对比，拒绝漏项或改写。
- 确定性 Assessment Gate 从规则类型、trigger/exception 和 gap 推导最终状态，并拒绝不一致的 Agent 候选；Action 阻断、Agent 写域、阶段闭包和节点汇总同样由确定性代码控制。
- 三类合成受试者 Fixture：未发现明确障碍、明确障碍、当前缺口/来源冲突；定位覆盖 `bbox / text_range / page_excerpt / page_only`。
- 生成式 Fixture、Agent I/O、Phase 1 UAT JSON Schema；可直接消费的 OpenAPI 3.1 草案含路径参数、请求/响应 DTO 和版本化中文错误信封。
- 四类 Agent/Gate/Projection 合同、交互设计合同和 14 项脚本化 UAT。
- 独立 UAT 工作区：6 名主要合成受试者的 12 个筛选/基线 Episode，加预筛和导入/洗脱期模板，共 14 个 Episode；覆盖全量/增量快照链、四级定位、主要 gap/Action、两个真实 RuleSet 的方案差异和 Job 失败/重试/恢复事件。

## 不变量

- Agent 只能产生草稿、候选或 CriticRun，不能写 FinalAssessment、Action 阻断等级或 EpisodeRollup。
- FinalAssessment 的求值、状态、缺口矩阵和阻断等级由 Gate 内部重算；调用方不能提交自算 `evaluation`。FinalAssessment、ActionRequest 和 EpisodeRollup 只接受完整上游 publication 闭包。
- EvidenceNormalizationCandidate、AssessmentCandidate、FinalAssessment、ActionRequest、EpisodeRollup 和 ProtocolIntegrity 均产生或验证 accepted GateResult；发布指纹只是实体自校验，不能替代 Gate 闭包。Evidence Gate 不再接受脱离 Normalizer AgentCall/Candidate 的另一组调用方事实。
- `ProtocolAuthorityRecord` 绑定正式方案哈希、每条规则来源锚点及完整 Rule/Workflow；由服务记录的 `ProtocolAuthorityConfirmation` 精确绑定方案文件和权威记录，并携带确认命令、确认人、时间及自身哈希。Authority Gate 必须同时消费两者，之后才能构建 Manifest；Protocol Integrity Gate 再逐项重算并封闭 RuleSet/Workflow/ProtocolVersion。
- AgentCall 的 `gate_result_ids` 非空；受试者 Agent 与其输出完整绑定 Project/ProtocolVersion/RuleSet revision/Subject/Episode/Run/Snapshot/Source。Agent 输出 Schema Gate 是后续 Candidate Gate 的强制上游，跨作用域、跨调用或未经接受的调用被拒绝。
- UNKNOWN ClinicalFact 不能携带 typed value/unit；原子观察的值、单位、fact/span 引用由 Evaluator 从 accepted Evidence Gate 输入推导，拒绝候选伪造。
- `provenance_followup` 单独计数且不阻断；`future_stage_not_due` 为关注；当前资料/判断/冲突缺口为阻断。
- 节点主状态固定按：明确障碍、当前节点缺口、冲突、需专业判断、后续节点关注、未发现明确障碍。
- OpenAPI 所有已声明的非成功响应均引用 `ErrorEnvelope`，不由前端自行猜错误结构。
- `AgentCall.error_codes` 与 `GateResult.error_codes` 使用版本化 `RuntimeErrorCode` 枚举；UNKNOWN 事实和值、`on` 与时间窗的互斥约束同时进入 Pydantic、JSON Schema 和 OpenAPI，不能只靠 Python runtime validator。
- 合同与文档统一使用 `RuleSet.revision`、`EpisodeRollup` 和 `AgentCall.model_config_id`。

## 可重复验证

```text
uv run --python 3.12.13 python -m scripts.generate_v2_contracts
uv run --python 3.12.13 pytest -q tests/v2/test_contract_logic.py tests/v2/test_contract_artifacts.py
uv run --python 3.12.13 pytest -q
/usr/bin/python3 -m pytest -q tests --ignore=tests/v2
```

本轮候选生成与测试结果：

- Phase 0.5 合同专项：`111 passed`，另有 2 个 subtests。
- V2 默认全套：`241 passed, 1 skipped`，另有 18 个 subtests；跳过项为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- legacy Python 3.9：`130 passed, 1 skipped`；跳过原因相同。
- `compileall` 和 `git diff --check` 通过。
- 生成器覆盖 4 个 Schema/OpenAPI 和 4 个 Fixture；连续两次生成的 8 个 SHA-256 完全一致：
  - `agent-contracts-v1.schema.json`: `9ecd1715febe2bcbc7fa4a6ca07dfdb11a8992a721506e5de1e7b49b9eb75595`
  - `fixture-v1.schema.json`: `c0e184a99b886e77c0ebc531a7dd568b8ebed2ed1e19b99e93be26b3e6c4b2e1`
  - `openapi-v1.draft.json`: `58a09301174681461a21e8609f14e61cec45677530e7b85eb419f18daf4fe18d`
  - `uat-phase1-workspace.schema.json`: `95ffe351d797121bb74e77ecb0ff90d68b322f0a38ac92f2ec010006610fe361`
  - `subject-barrier.json`: `8df5a08d5efeb654120d44a6b6fa42d058233a8080b4575dd379ec89871e0f2a`
  - `subject-clear.json`: `757cae8857fa89032cd74f1ff764a12234c038df67a93c3b93495a7b29e021b1`
  - `subject-gap_conflict.json`: `b7f53c6fbe5061da37f91e10b95ad4305cf17ba82d7bcb3a8581fbad5fb13ec0`
  - `uat-phase1-workspace.json`: `c2e2151c217b6febbd9cf6a50f316a057606bfbceb440099b7fa0d31b07f8b11`
- 第四次独立复核识别 7 个 P1 和 2 个 P2：Action/Rollup 只验局部 Gate、Agent 输出未绑定具体候选、Assessment 组件可替换、Fixture 候选未持久化为发布版本、Agent 方案 scope 未核对、权威记录缺服务侧确认事件、runtime validator 未进入 Schema，以及 UAT 只验计数、错误码开放字符串。
- 根因修复：AssessmentPublication 与 ActionPublication 保存并重算完整上游闭包；Fixture 由最终 Gate 输入引用反向锁定唯一 Candidate/Evidence Gate；Agent typed output 哈希逐候选绑定；Fixture AgentCall 强制 Protocol/RuleSet revision scope 和唯一 Schema Gate；新增人工确认事件；Schema 条件与错误枚举机器可读；UAT 锁定关键 ALL/ANY/NOT 树和随机前 28 天窗口，并包含真实 `historical_source_unavailable` Episode。
- 当前针对性 V2 契约测试、完整套件、legacy 回归和生成哈希均已更新；同一 checker 复核仍待完成。
- 本阶段未调用真实 LLM/OCR、未重审临床项目、未修改 legacy 项目数据、未调用 Qwen 3.8；用户已明确后续也不使用 Qwen 3.8 会商。

## 待验收

独立 checker 需检查：Schema/文档漂移、AND/OR 和复合专业判断、证据状态与判断状态分离、阶段隔离、Agent 写权限、OpenAPI 错误合同、Fixture 内部引用、交互合同可执行性及 UAT 停止门槛。只有无阻断 finding 且 Codex 接受后，才归档 Phase 0.5 并进入 Phase 1。
