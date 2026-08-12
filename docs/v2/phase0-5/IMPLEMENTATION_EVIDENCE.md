# Phase 0.5 合同候选实施证据

**日期：** 2026-08-12
**状态：** 待独立 checker 验收；本文件不表示 Phase 0.5 已冻结。

## 已形成的合同

- Pydantic `fixture/v1` 领域模型：项目、正式方案版本、独立研究期别、受试者、审核节点、规则树、证据快照、事实、Patient Profile、判断候选、最终判断、行动、Agent 调用、Gate、Job 和运行差异。
- 有限递归 `ALL / ANY / NOT` 规则表达式；阈值、单位、时间锚点/窗口、例外和专业判断要求保持结构化。
- 确定性 Assessment Gate、Action 阻断推导、Agent 写域限制、表达式逻辑求值和节点汇总。
- 三类合成受试者 Fixture：未发现明确障碍、明确障碍、当前缺口/来源冲突；定位覆盖 `bbox / text_range / page_excerpt / page_only`。
- 生成式 JSON Schema、OpenAPI 3.1 草案、版本化中文错误信封。
- 四类 Agent/Gate/Projection 合同、交互设计合同和 14 项脚本化 UAT。

## 不变量

- Agent 只能产生草稿、候选或 CriticRun，不能写 FinalAssessment、Action 阻断等级或 EpisodeRollup。
- FinalAssessment 的状态/缺口矩阵和阻断等级由 Gate 计算；Action 阻断等级由 gap 类型确定性推导。
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

候选生成与测试结果：

- Phase 0.5 合同专项：`60 passed`。
- V2 默认全套：`196 passed, 1 skipped`，另有 18 个 subtests；跳过项为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- legacy Python 3.9：`130 passed, 1 skipped`；跳过原因相同。
- 连续两次生成后的 2 个 Schema/OpenAPI 和 3 个 Fixture SHA-256 完全一致。
- 本阶段未调用真实 LLM/OCR、未重审临床项目、未修改 legacy 项目数据、未调用 Qwen 3.8。

## 待验收

独立 checker 需检查：Schema/文档漂移、AND/OR 和复合专业判断、证据状态与判断状态分离、阶段隔离、Agent 写权限、OpenAPI 错误合同、Fixture 内部引用、交互合同可执行性及 UAT 停止门槛。只有无阻断 finding 且 Codex 接受后，才归档 Phase 0.5 并进入 Phase 1。
