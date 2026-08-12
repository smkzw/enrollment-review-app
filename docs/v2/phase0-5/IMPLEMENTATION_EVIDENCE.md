# Phase 0.5 合同候选实施证据

**日期：** 2026-08-13
**状态：** 同一 checker 第六次复核为 `REJECT`；第六次拒绝项已完成本地根因修复，等待同一 checker 第七次复核。本文件不表示本阶段已冻结。

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
- Assessment 只能从应用服务已登记的版本化审核上下文读取阶段、日期锚点、证据要求、冲突组和半衰期；发布函数不再接受这些字段的调用方副本。Action 的临床业务字段由规则组件、证据要求、审核节点和最终判断确定性派生；节点汇总必须覆盖已登记的全部组件、证据要求和缺口待办。
- EvidenceNormalizationCandidate、AssessmentCandidate、FinalAssessment、ActionRequest、EpisodeRollup 和 ProtocolIntegrity 均产生或验证 accepted GateResult；发布指纹只是实体自校验，不能替代 Gate 闭包。Evidence Gate 不再接受脱离 Normalizer AgentCall/Candidate 的另一组调用方事实。
- `ProtocolAuthorityRecord` 绑定正式方案哈希、每条规则来源锚点及完整 Rule/Workflow；确认只能从服务端已登记的操作事件生成，确认人和时间由事件派生。Manifest 的每个来源必须解析到已登记且绑定同一方案文件的来源记录；Protocol Integrity Gate 再逐项重算并封闭 RuleSet/Workflow/ProtocolVersion。
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

第六次拒绝后的本地候选生成与测试结果：

- Phase 0.5 合同专项：`128 passed`，另有 2 个 subtests。
- V2 默认全套：`258 passed, 1 skipped`，另有 18 个 subtests；跳过项为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- legacy Python 3.9：`130 passed, 1 skipped`；跳过原因相同。
- `compileall` 和 `git diff --check` 通过。
- 生成器覆盖 4 个 Schema/OpenAPI 和 4 个 Fixture；连续两次生成的 8 个 SHA-256 完全一致：
  - `agent-contracts-v1.schema.json`: `9ecd1715febe2bcbc7fa4a6ca07dfdb11a8992a721506e5de1e7b49b9eb75595`
  - `fixture-v1.schema.json`: `d8511d506c1a5b8fc3471bc0f6240e228c5f5113d37b6a06b2c0c099e42a058f`
  - `openapi-v1.draft.json`: `ded66de3930a8e7517fe41b5ebfa35a9df8da4782b41e75dc6732a2150eaf933`
  - `uat-phase1-workspace.schema.json`: `f5e1a49ca67c1751d566e3474dca50d0a614b1a2d8d077b25b6f239e3fc816f9`
  - `subject-barrier.json`: `d3c9c92fd2dc778b1f067b6a44261bf2720d26f3f009cd89b8c295dc9204932c`
  - `subject-clear.json`: `87a090eb2d8fa255154b594971dcffdea0653c00865388d5a6e6f9b2bb04e425`
  - `subject-gap_conflict.json`: `eb5abc17c8c8554c319c767078b46c5c3f8660fe3281931ea6d2a14c9daa9991`
  - `uat-phase1-workspace.json`: `1db98f9059111342e72397199c7d18bc2ccc92d1a07dfc13bc1cf510b108e1ca`
- 第四次独立复核识别 7 个 P1 和 2 个 P2：Action/Rollup 只验局部 Gate、Agent 输出未绑定具体候选、Assessment 组件可替换、Fixture 候选未持久化为发布版本、Agent 方案 scope 未核对、权威记录缺服务侧确认事件、runtime validator 未进入 Schema，以及 UAT 只验计数、错误码开放字符串。
- 第五次独立复核结论为 `REJECT`。Schema、UAT、错误码与部分 scope 已关闭，但仅重算调用方传入的完整对象仍不能证明它们来自服务端已接受状态。当前测试证据有效，但不足以证明 Phase 0.5 完成。
- 第五次拒绝项已按根因改造：新增应用服务签发的只读发布注册表与版本化审核上下文；Assessment 按 ID 反查唯一上游并重算 typed Candidate；RuleSet 用完整哈希绑定已登记 Protocol Integrity Gate；确认来自登记操作事件，方案来源来自登记目录；Fixture Fact/Span 逐 payload 比对；多 Gate 按类型、声明和唯一性解析。
- 新增同步重算对抗测试：即使伪造方同时重算 Candidate、AgentCall、Schema/Candidate/Evidence Gate、自哈希确认事件或来源记录，只要与验证前的服务端注册表不一致仍被拒绝。`validate_fixture_scope` 不再从待验证 Fixture 反向构建信任。
- 第六次 checker 复现的开放项已按统一根因关闭：Candidate/Evidence/Authority Gate 精确反查注册表；Rollup 拒绝空、不完整或重复集合；Action 接口不再接受调用方业务文案和范围；来源文件、Prompt、Model、Subject、Episode、Snapshot、Run 均按完整 payload 登记；Fixture 夹带未登记调用或 Gate 会被拒绝。
- 新增 13 项对抗场景，覆盖未登记 AgentCall/Schema Gate/Candidate、来源文件同 ID 哈希替换、Authority Gate 时间戳替换后完整性 Gate 失效、Assessment/Expectation/Action 缺件与重复、Action 六类业务字段替换、Fixture 额外未登记调用/Gate，以及临床和审计实体同 ID payload 替换。
- 本地测试与确定性生成只证明候选满足当前自动化合同，不代替独立 checker 验收；Phase 0.5 在同一 checker 明确接受前继续保持 `in_progress`。
- 本阶段未调用真实 LLM/OCR、未重审临床项目、未修改 legacy 项目数据、未调用 Qwen 3.8；用户已明确后续也不使用 Qwen 3.8 会商。

## 待验收

同一独立 checker 需复核第六次拒绝项和回归面：注册表全集、发布闭包、Rollup 完整集合、Action 确定性派生、Fixture 额外对象、Schema/文档漂移及 UAT 停止门槛。只有无阻断 finding 且 Codex 接受后，才归档 Phase 0.5 并进入 Phase 1。
