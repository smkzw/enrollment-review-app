# Execution Output: phase5-slice58d-v2-target-group-homogeneity-20260825 - worker_01

## Boundary And Context Check

已读取指定 execution context 与 plan，并只读检查相关 v2 输入、wire、扩展、hydration/gate、transport、提示词、测试及工作区内 D001 冻结批次资料。

工作树初始已有大量预存改动；本轮未修改源码、测试、生产路径或 runner 管理的报告文件。

## Work Performed

发现当前缺陷：

- `PhaseApplicabilityAgentWireV2` 仅检查组内 payload 指纹，未检查组内 target 的结构语义。
- `app/agents/phase_applicability.py:1150-1163` 的 `_compact_group_fingerprint()` 不包含 target 的摘录、标题、表格语境或期别范围。
- `:1263` 将同一 group payload 无条件复制给所有 target。
- 现有 hydration/gate 只验证每个展开结果的来源闭包和处置逻辑，不验证多个 target 是否具备同组资格。
- 当前 prompt 只要求“处置/证据/理由相同即合组”，没有系统确定的 target 等价边界。

建议的最小确定性 target 等价键：

```text
K(target) = (
  study_phase,
  unit_kind,
  normalized_heading_path,
  normalized_excerpt,
  normalized_table_context,
  is_footnote_or_note,
  sorted_phase_scopes,
)
```

其中：

- 仅做首尾空白及连续空白归一化，不做关键词、同义词或模型语义合并。
- `table_context` 至少保留表题/行表头/列表头及定位；最安全实现是对其完整结构字段做规范化比较。
- 不纳入 `structure_unit_id`、`source_ref`、`member_source_refs`、`source_span_ids`、`source_order`、priority 字段；这些是身份或来源定位，不是 target 语义。
- 只有组内所有 target 的 `K(target)` 完全相同，且现有共享 payload 指纹相同，才允许合组。
- 不满足时应在 v2 扩展阶段失败关闭，例如 `HETEROGENEOUS_TARGET_GROUP`，保留相关 `unit_indexes`/`structure_unit_ids`，交给同会话中文定向修复；不能静默自动拆组或继续发布。

该检查应放在 `expand_phase_applicability_agent_wire_v2()`，因为 Pydantic 的 `PhaseApplicabilityAgentWireV2` 校验器无法访问冻结 `agent_input`。

额外残留风险：若多 target group 的 evidence 只引用其中一个 owned target，当前 gate 仍可能接受并复制该 evidence。最严格的后续边界应要求多 target group 的 evidence 使用共同 context，或证明摘录可在组内每个 target 回源；这不是当前最小 target-key 修复的必要 schema 变更，但应作为复核项保留。

## Artifacts And Evidence

关键代码：

- `app/agents/phase_applicability.py:386-463`：冻结 owned/context 输入。
- `:585-689`：v2 group schema 及仅基于 payload 的去重。
- `:897-928`：system prompt/repair contract。
- `:987-1086`：输入投影、输出提示及修复提示。
- `:1150-1286`：payload 指纹及逐 target 展开。
- `:1352-1444`：v2 展开后进入 hydration/gate。
- `app/protocols/phase_applicability.py:178-310`：来源片段归属与水合。
- `app/protocols/phase_applicability.py:491-628`：逐结果 publication gate。
- `app/domain/contracts/protocol_controls.py:292-365`：`TableCellContext` 与 `ProtocolStructureUnit` 语义字段。

合成缺陷证据：

- 测试 helper 中 `target-01` 是 paragraph，`target-02` 是 table row。
- 两者摘录不同、unit kind 不同、table context 不同，但当前 v2 仍能共享一个 group。
- 共享 evidence 来自 context，因此 hydration/gate 均通过。
- 当前测试输出：`CURRENT_V2_HYDRATION_ACCEPTED 2 ['target-01', 'target-02']`。

输出预算影响：

- 测试 fixture 序列化长度：
  - v1 两个逐 target 结果：975 字符；
  - v2 一个同质 group：539 字符；
  - v2 两个独立 group：980 字符。
- 因此真正同质目标仍保留原有 v2 压缩收益；异质目标拆组后输出将接近或略高于 v1，不应继续按“所有目标可共享”估算预算。
- 当前 local transport 的 `max_tokens` 下限及默认批次上限为 8192：`app/config.py:81-85`、`app/agents/phase_applicability_transport.py:146-157`。
- D001 当前批次大小为 12；若 12 个 target 的等价键均不同，v2 必须返回最多 12 个 groups，不能因预算压力再次合并。

v1 兼容影响：

- 不需要修改 `PhaseApplicabilityAgentWire`、`parse_phase_applicability_agent_wire_v1()` 或 v1 hydration 路径。
- 该边界只应用于 v2 group expansion。
- 若修改 v2 prompt，`phase_applicability_agent_prompt_template_sha256` 会变化，旧 execution checkpoint 应按现有 `EXECUTION_PROMPT_CONFLICT` 规则失效并重新准备，不能静默续跑。

D001 批次 32 源结构审计：

- 冻结包：`pap-3e3ed5979a2051e0d3724e04`，12 个 owned targets。
- 按上述确定性键计算，12 个 target 得到 12 个不同 key。
- 批次同时包含概要段落、表头、阶段/目的/终点/试验设计/持续时间/研究人群/入排标准/药物信息/给药及嵌套表头。
- 期别范围包含 `unknown`、`mixed`、`phase_ii`、`phase_iii` 等组合，不能共享一套期别理由。

## Commands And Observations

执行：

```bash
./.venv/bin/pytest -q \
  tests/v2/protocols/test_slice58c2_phase_applicability_agent.py \
  tests/v2/protocols/test_phase_applicability_contract.py \
  tests/v2/protocols/test_phase_applicability_live_execution.py
```

结果：

```text
40 passed, 5 warnings
```

执行只读合成 probe，确认：

```text
SYNTHETIC_TARGETS_EQUAL_EXCERPT False
SYNTHETIC_TARGETS_EQUAL_UNIT_KIND False
SYNTHETIC_TARGETS_EQUAL_TABLE_CONTEXT False
SYNTHETIC_TARGETS_EQUAL_PHASE_SCOPES True
CURRENT_V2_HYDRATION_ACCEPTED 2 ['target-01', 'target-02']
D001_BATCH_32 ... owned= 12 unique_target_keys= 12
```

D001 execution 状态：

- `execution_summary.json`：`accepted_batch_count=0`、`accepted_unit_count=0`、`batch_count=235`。
- `execution/d001-ii-phase-closure-20260825.json` 第 32 批：`status=needs_review`、`final_output=null`。
- 失败原因为：`模型请求失败：APIConnectionError: Connection error.`

## Blockers Or Missing Environment

真实 D001 批次 32 没有可供审计的模型输出，不能声称完成真实 provider 语义重跑或 gate 验收。

当前可确认的是冻结源结构语义：批次 32 的 12 个 target 均不满足同组等价条件。实际模型重跑仍需可用的 oMLX endpoint。

## Rerun Requests Or Next Step

1. 在 `app/agents/phase_applicability.py` 的 v2 expansion 中加入确定性 target-key 校验及 `HETEROGENEOUS_TARGET_GROUP` 失败关闭。
2. 更新中文 prompt/repair prompt，明确“只有系统 target 等价键完全相同才可合组”。
3. 保留 v1 解析与历史读取不变。
4. 运行合成回归：摘录、标题、表格上下文、期别范围任一不同均拒绝；完整等价 target 可合组。
5. 修复 transport 后仅重跑 D001 冻结批次 32，记录原始 v2 输出、group 数量、逐 target gate 结果和是否仍有 target-specific evidence 风险。
