# Phase 0.5 合同候选实施证据

**日期：** 2026-08-12
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
- `ProtocolAuthorityRecord` 绑定正式方案哈希、人工核对人/时间/方式、每条规则来源锚点及完整 Rule/Workflow；Authority Gate 之后才能构建 Manifest，Protocol Integrity Gate 再逐项重算并封闭 RuleSet/Workflow/ProtocolVersion。
- AgentCall 的 `gate_result_ids` 非空；受试者 Agent 与其输出完整绑定 Project/ProtocolVersion/RuleSet revision/Subject/Episode/Run/Snapshot/Source。Agent 输出 Schema Gate 是后续 Candidate Gate 的强制上游，跨作用域、跨调用或未经接受的调用被拒绝。
- UNKNOWN ClinicalFact 不能携带 typed value/unit；原子观察的值、单位、fact/span 引用由 Evaluator 从 accepted Evidence Gate 输入推导，拒绝候选伪造。
- `provenance_followup` 单独计数且不阻断；`future_stage_not_due` 为关注；当前资料/判断/冲突缺口为阻断。
- 节点主状态固定按：明确障碍、当前节点缺口、冲突、需专业判断、后续节点关注、未发现明确障碍。
- OpenAPI 所有已声明的非成功响应均引用 `ErrorEnvelope`，不由前端自行猜错误结构。
- 合同与文档统一使用 `RuleSet.revision`、`EpisodeRollup` 和 `AgentCall.model_config_id`。

## 可重复验证

```text
uv run --python 3.12.13 python -m scripts.generate_v2_contracts
uv run --python 3.12.13 pytest -q tests/v2/test_contract_logic.py tests/v2/test_contract_artifacts.py
uv run --python 3.12.13 pytest -q
/usr/bin/python3 -m pytest -q tests --ignore=tests/v2
```

本轮候选生成与测试结果：

- Phase 0.5 合同专项：`106 passed`，另有 2 个 subtests。
- V2 默认全套：`236 passed, 1 skipped`，另有 18 个 subtests；跳过项为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- legacy Python 3.9：`130 passed, 1 skipped`；跳过原因相同。
- `compileall` 和 `git diff --check` 通过。
- 生成器覆盖 4 个 Schema/OpenAPI 和 4 个 Fixture；连续两次生成的 8 个 SHA-256 完全一致：
  - `agent-contracts-v1.schema.json`: `972f1b30dc782f96bdd65408e429791dc6600efd5e9a3e0d58eff1b3cc1e2da1`
  - `fixture-v1.schema.json`: `5797d1db63e5182d64a00df65aa13a6e2ba1f8f5fc182401f2e47053ed873f31`
  - `openapi-v1.draft.json`: `a7828539cd9590e8a05765b3ad350245e6fd78f0d376b05e8c40ecfee5b6c4b3`
  - `uat-phase1-workspace.schema.json`: `82e8ced0a9aead0f14fb664b2b990d27e82939a02f194ca7af897ec5824812cd`
  - `subject-barrier.json`: `7045d8e88b1724befef41d9e7d43220fdf9583352b4d09ef6eed941dfe394317`
  - `subject-clear.json`: `71462a0f9f9e07d54323094037c53f0ec45202e878ed2804eff63670586229dc`
  - `subject-gap_conflict.json`: `cdadbf795c4565dc64230834567c62ed6ca78386cc471709742b7cc8b7ed5b4d`
  - `uat-phase1-workspace.json`: `438b9fb6a2a4dd2ef6ca41f9bd6492301eeffa407d8632d9a892d22ebbb059f1`
- 第三次独立复核识别并已修复：caller-supplied evaluation、UNKNOWN 携带值、`on` 忽略区间参数、候选伪造观察值/单位/Span、Agent scope 漂移、调用方自证方案权威、Action/Rollup 未验证完整上游 publication，以及 UAT 语义覆盖不足。
- 当前针对性 V2 契约测试、完整套件、legacy 回归和生成哈希均已更新；同一 checker 复核仍待完成。
- 本阶段未调用真实 LLM/OCR、未重审临床项目、未修改 legacy 项目数据、未调用 Qwen 3.8；用户已明确后续也不使用 Qwen 3.8 会商。

## 待验收

独立 checker 需检查：Schema/文档漂移、AND/OR 和复合专业判断、证据状态与判断状态分离、阶段隔离、Agent 写权限、OpenAPI 错误合同、Fixture 内部引用、交互合同可执行性及 UAT 停止门槛。只有无阻断 finding 且 Codex 接受后，才归档 Phase 0.5 并进入 Phase 1。
