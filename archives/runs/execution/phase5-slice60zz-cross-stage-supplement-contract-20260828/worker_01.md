Trellis SessionStart 已加载。正在读取执行上下文与计划文件，分析跨阶段补充关系合同冲突。
正在搜索保存的回包、补充关系合同与双重门禁相关文件。
# Execution Output: phase5-slice60zz-cross-stage-supplement-contract-20260828 - worker_01

## Boundary And Context Check

- **Role**: `worker_01`, read-only analysis; no source edits authorized.
- **Workspace**: `.worktrees/phase5-clinical-facts-profile` (bound correctly).
- **Initial read set consumed**: `context/phase5-slice60zz-cross-stage-supplement-contract-20260828_execution_context.md`, `plans/codex_execution_phase5-slice60zz-cross-stage-supplement-contract-20260828.md`.
- **Additional reads** (justified by task): saved virology replay artifact, wire/gate implementation, existing slice58c tests.
- **Hard boundaries respected**: no production writes, no report file write, no final acceptance claim.

**Objective (from context)**: 修复「流程必做项在较早访视完成、但其新增结果有效窗只能在后续首次给药/基线节点最终判定」时，补充关系门禁与时间锚点门禁互相冲突的**通用**合同；不得写 D001 特例。

---

## Work Performed

### 1. 三轮保存回包轨迹（病毒学失败 replay）

来源：`artifacts/phase5-slice60zy-virology-single-mtplx-20260828/execution/runner-result.json`, `raw-responses.json`, `batch.json`

| 轮次 | 结果 | 触发门禁 | Agent 关键形态 |
|------|------|----------|----------------|
| **R1** | `schema_invalid` | Wire: `补充流程必做项必须声明首次受影响的冻结审核节点` | 2 候选；`affected_workflow_stage_id=null`；`decide_at_node@flow-baseline`；含 `verify_result_validity` + `first_dose_date` |
| **R2** | `publication_invalid` | `EARLY_DECISION_FOR_FUTURE_ANCHOR` | 补 `affected=flow-screening`；改 `decide_at_node@flow-screening`；evidence `due_stage=screening`；仍含 `first_dose_date` 锚 |
| **R3** | `schema_invalid` | `AFFECTED_STAGE_DECISION_MISSING` | `affected=flow-screening`；`early_attention@screening` + `decide_at_node@baseline`；evidence `due_stage=baseline` |

**临床/结构背景（batch 冻结目录）**：
- 流程必做目标 `pcm-row-2a4db6b98190f7f0c22da3b3`：`review_stage=screening`, `visit_instance=筛选访视`
- 冻结节点：`flow-screening`（筛选）、`flow-baseline`（基线及随机前复核）
- Owned 原文（p804/p805）：额外检测项 +「可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查」

**R1→R2→R3 是典型 ping-pong**：每轮只修上一个门禁报错，下一门禁立即反杀，三轮后 `final_output=null`, `status=需要核对`。

### 2. 双重门禁冲突机理

#### 门禁 A — 补充流程对齐（Wire + Publication 共用）

实现位置：
- Wire 水合：`app/agents/protocol_control_deconstructor.py` `_validate_supplementary_relations` (~1291–1328)
- 发布门禁：`app/protocols/protocol_control_gate.py` `_check_supplementary_procedure_stage_alignment` (~2955–3047)

**当前不变量（同阶段补充）**：

```
IF kind=supplementary_requirement AND target=required_procedure:
  affected_workflow_stage_id MUST == procedure.(review_stage, visit_instance) 对应节点
  MUST decide_at_node @ affected
  MUST evidence.due_stage == affected.review_stage
```

#### 门禁 B — 后续锚点早期判定禁止

实现：`app/protocols/protocol_control_gate.py` `_check_anchor_decision_alignment` (~2619–2722)

**当前不变量**：

```
IF obligation/global_time_constraint 含 baseline_date|randomization_date|first_dose_date|study_drug_administration_date:
  任一 decide_at_node 的 workflow index MUST NOT < 首个 baseline 节点 index
  screening 只能 early_attention，不能 decide_at_node
```

已有接受形态（测试证据）：`test_future_first_dose_check_accepts_early_attention_and_baseline_decision` — screening `early_attention` + baseline `decide_at_node` **可通过** 门禁 B。

#### 冲突核心（推断）

病毒学场景同时满足：
1. 补充对象 = **筛选访视**流程必做（执行访视 = screening）
2. 义务增量 = `verify_result_validity` + `first_dose_date`（最终判定只能在 baseline）
3. 现有补充门禁强制 **affected = 执行访视 = screening** 且 **decide@affected**
4. 锚点门禁禁止 **decide@screening** 对 future anchor

→ **不存在同时满足 A+B 的合法输出**。R3 已找到 B 的正确形态（early_attention + baseline decide），但被 A 的 `AFFECTED_STAGE_DECISION_MISSING` 拒绝。

### 3. 提示合同与修复引导缺口

`app/agents/protocol_control_deconstructor.py` `_CONTROL_AGENT_CONTRACT` 关键条款：

- L841–844：`affected_workflow_stage_id` 必须选**访视目标对应节点**，表示「首次产生入排影响的节点」；候选须在该节点 `decide_at_node`，证据在该阶段到期。
- L825–827：后续锚点最终判定必须绑后续决定节点；较早筛选只能 `early_attention`。
- L833–835：筛选完成 + 基线/首次给药有效性 → **按最终决定阶段拆候选**。
- L894 自检 #9：`affected`、流程目标访视、`decide`、证据到期阶段**必须一致**。

**缺口**：
- 合同把「执行访视」「首次影响」「最终判定」压成同一 `affected_workflow_stage_id` + 同节点 `decide`。
- `_repair_problem_guidance` **无** `EARLY_DECISION_FOR_FUTURE_ANCHOR` / `AFFECTED_STAGE_DECISION_MISSING` 的跨阶段补充专用引导；R2→R3 修复靠模型自行推断，导致 R3 形态正确但仍过不了 A。

### 4. 通用跨阶段补充语义（建议合同）

#### 定义：跨阶段后续控制补充（Cross-Stage Subsequent-Control Supplement）

```
relation.kind == supplementary_requirement
AND relation.external_target_kind == required_procedure
AND 义务增量 ⊆ { verify_result_validity, select_baseline_value, ...后续锚点控制 }
AND 增量 time_constraint.anchor ∈ { baseline_date, randomization_date, first_dose_date, study_drug_administration_date }
AND order(final_decision_stage) > order(procedure_execution_stage)
```

**语义拆分（建议保留两个概念，不一定新增字段）**：

| 概念 | 含义 | 病毒学例 |
|------|------|----------|
| **procedure_execution_stage** | 被补充流程必做项的冻结执行访视 | `flow-screening` |
| **supplement_decision_stage** | 增量义务最终判定的冻结节点 | `flow-baseline` |

`affected_workflow_stage_id` 应重新定义为 **supplement_decision_stage**（增量首次构成可发布入排判定的节点），而非机械等于 procedure 执行访视。

#### 建议不变量（通用）

**I1 — 关系目标不变**  
`external_target_id` 仍必须指向被补充的 `required_procedure`；不得发明新流程目标。

**I2 — 跨阶段后续控制路径（新增）**  
当且仅当满足 Cross-Stage Subsequent-Control Supplement：
- `affected_workflow_stage_id` **允许且必须** = 与后续锚点一致的最终判定节点（如 `flow-baseline`）
- **不要求** `affected == procedure_execution_stage`
- **必须** `decide_at_node @ affected`
- **必须** `evidence.due_stage == affected.review_stage`
- **可选/推荐** `early_attention @ procedure_execution_stage`（当同一候选仍含 `complete_or_verify` 等同访视执行核对时）

**I3 — 同阶段补充路径（保持现状）**  
不满足 I2 时，沿用现有规则：`affected == procedure 访视` + `decide@affected` + 同阶段 evidence。

**I4 — 锚点门禁（不放宽）**  
含 future anchor 的候选：**禁止** screening `decide_at_node`（`EARLY_DECISION_FOR_FUTURE_ANCHOR` 保持）。

**I5 — 混合义务（提示已有，门禁应配合）**  
同一 owned 单元若同时含「筛选期执行项」与「首次给药前有效窗」：
- **优先拆成两候选**（执行候选 @ screening；有效窗候选 @ baseline，均 `supplementary_requirement` 关联同一 procedure）
- 若不拆，则执行原子走 `early_attention@execution`，后续控制原子走 `decide@affected(baseline)`

#### 拒绝边界（必须继续拒绝）

| 场景 | 预期拒绝码 | 理由 |
|------|-----------|------|
| 同阶段补充却 `decide` 早于 procedure 访视 | `PROCEDURE_AFFECTED_STAGE_MISMATCH` / `AFFECTED_STAGE_*` | 防止错绑访视 |
| future anchor + screening `decide_at_node` | `EARLY_DECISION_FOR_FUTURE_ANCHOR` | 防止早期终判 |
| 跨阶段路径但 `affected` 仍填 execution 且仅 baseline `decide` | `AFFECTED_STAGE_DECISION_MISSING` | 当前 R3；修复后应改为 `affected=baseline` |
| 跨阶段路径但 evidence 早于 decision stage | `AFFECTED_STAGE_EVIDENCE_MISSING` / `DECISION_STAGE_EVIDENCE_MISSING` | 防止证据缺口 |
| 用跨阶段路径包装普通同访视增量（无 subsequent control） | 新检或现有 `PROCEDURE_AFFECTED_STAGE_MISMATCH` | 防止放宽同阶段补充 |
| `affected` 指向无锚点依据的更晚访视 | `ANCHOR_WORKFLOW_STAGE_MISMATCH` | 防止随意后移 |
| 流程目标访视错配（引用 baseline procedure 却绑 screening 关系等） | `UNKNOWN_RELATION_TARGET` 等 | 防止目标伪造 |

### 5. 最小修复建议（供 worker_02）

**范围**：通用逻辑，禁止 D001 硬编码。

1. **新增判定 helper**（gate + wire 共用）：`_is_cross_stage_subsequent_control_supplement(candidate|control, relation, procedure, workflow_targets) -> bool`  
   条件：I2 定义；至少识别 `verify_result_validity` + future anchor。

2. **放宽 `_check_supplementary_procedure_stage_alignment` / `_validate_supplementary_relations`**：  
   - I2 为真：`expected_id = workflow_stage_for(anchor_decision_stage)`，**不再**要求 `expected_id == procedure 访视节点`  
   - I2 为假：保持现有 `workflow_by_key[(procedure.review_stage, procedure.visit_instance)]` 检查  
   - `decide@affected` 与 `evidence@affected.review_stage` 规则保留，但 `affected` 语义改为 decision stage

3. **提示合同同步**（`protocol_control_deconstructor.py`）：  
   - 改写 L841–844、L894 #9：区分同阶段 vs 跨阶段后续控制  
   - 增加 `_repair_problem_guidance` 分支：`EARLY_DECISION_FOR_FUTURE_ANCHOR` + `AFFECTED_STAGE_DECISION_MISSING` 联合提示「跨阶段有效窗补充：`affected`=baseline 决定节点，procedure 仍指向执行访视目标，screening 仅 early_attention」

4. **不新增 wire 字段（最小路径）**：复用 `affected_workflow_stage_id` 承载 **supplement_decision_stage**；procedure 执行访视由 `external_target_id → known_procedure_targets` 隐式确定。

### 6. 病毒学 replay 的预期合法形态（修复后）

**候选 B（p805，纯有效窗）** — 应接受：
```json
{
  "cross_source_relations": [{
    "kind": "supplementary_requirement",
    "external_target_kind": "required_procedure",
    "external_target_id": "pcm-row-2a4db6b98190f7f0c22da3b3",
    "affected_workflow_stage_id": "flow-baseline",
    "candidate_side": "left"
  }],
  "review_node_bindings": [
    {"workflow_stage_id": "flow-baseline", "review_stage": "baseline", "role": "decide_at_node"}
  ],
  "minimum_evidence": [{"due_stage": "baseline", ...}],
  "obligation_expression": { "atoms": [{"kind": "verify_result_validity", "time_constraint": {"anchor_type": "first_dose_date", ...}}]}
}
```

**候选 A（p804，额外检测 + 有效窗）** — 建议拆成两个候选，或单候选：
- `early_attention@flow-screening` + `complete_or_verify`（额外三项）
- `decide@flow-baseline` + `verify_result_validity` + `affected=flow-baseline`

### 7. 合成正反例（供 worker_03）

| ID | 类型 | 要点 | 预期 |
|----|------|------|------|
| **SYN-ACCEPT-01** | 正例 | screening procedure + 28d `first_dose_date` validity, `affected=baseline`, `decide@baseline` | PASS |
| **SYN-ACCEPT-02** | 正例 | 同上 + `early_attention@screening` + 执行核对 evidence@screening（若保留执行原子） | PASS |
| **SYN-REJECT-01** | 反例 | 同 SYN-ACCEPT-01 但 `decide@screening` | `EARLY_DECISION_FOR_FUTURE_ANCHOR` |
| **SYN-REJECT-02** | 反例 | 同阶段 screening 补充（无 future anchor），`affected=baseline` | `PROCEDURE_AFFECTED_STAGE_MISMATCH` |
| **SYN-REJECT-03** | 反例 | 跨阶段路径但 `affected=screening`, 仅 baseline `decide`（R3 形态） | `AFFECTED_STAGE_DECISION_MISSING`（修复前）；修复后应引导改为 SYN-ACCEPT-01 |
| **SYN-REJECT-04** | 反例 | `affected=baseline` 但 evidence 仅 screening | `AFFECTED_STAGE_EVIDENCE_MISSING` / `DECISION_STAGE_EVIDENCE_MISSING` |
| **SYN-REJECT-05** | 反例 | 普通 screening 补充（如额外问卷，无 subsequent control）试图 `affected=baseline` | 仍拒（不得放宽同阶段） |
| **ARTIFACT-R1/R2/R3** | 回归 | 保存三轮 raw JSON | 修复后 R3 形态改 `affected=baseline` 应可 hydrated + publication pass |

---

## Artifacts And Evidence

| 证据 | 路径 | 用途 |
|------|------|------|
| 三轮 raw 回包 | `artifacts/phase5-slice60zy-virology-single-mtplx-20260828/execution/raw-responses.json` | R1/R2/R3 完整 wire |
| Runner 门禁轨迹 | `.../execution/runner-result.json` | 三轮 issue 码 |
| 冻结 batch 上下文 | `.../execution/batch.json` | procedure/workflow 目录 |
| Replay 摘要 | `.../replay-summary.json` | 3 attempts, 0 candidates hydrated |
| Wire 关系校验 | `app/agents/protocol_control_deconstructor.py:414–446, 1291–1328, 841–894` | 补充关系 + 提示合同 |
| 锚点判定门禁 | `app/protocols/protocol_control_gate.py:2619–2722` | `EARLY_DECISION_FOR_FUTURE_ANCHOR` |
| 补充对齐门禁 | `app/protocols/protocol_control_gate.py:2955–3047` | `AFFECTED_STAGE_*`, `PROCEDURE_AFFECTED_STAGE_MISMATCH` |
| 已有接受/拒绝测试 | `tests/v2/protocols/test_slice58c_protocol_control_gate.py:3369–3492, 3824–3913` | 锚点 early_attention 模式；同阶段补充严格对齐 |

---

## Commands And Observations

| 工具 | 目标 | 观察 |
|------|------|------|
| Read | execution context + plan | worker_01 只读分析；worker_02/03 负责实现与验证 |
| Grep/Glob | `slice60zz`, `supplementary`, `EARLY_DECISION`, `affected_workflow_stage` | 定位 artifact 与 gate 实现 |
| Read | virology artifact 全套 | 确认三轮 ping-pong 与冻结目录 |
| Read | gate/deconstructor 源码 + slice58c tests | 确认双重门禁逻辑与现有测试覆盖缺口 |

**未运行测试**（worker_01 授权范围外）；worker_03 应跑聚焦协议测试。

---

## Blockers Or Missing Environment

- **Execution context Source Of Truth** 仍为 `TODO`；本次分析以 `artifacts/phase5-slice60zy-virology-single-mtplx-20260828` 为实际证据源。
- **无代码 blocker**；分析完整，可交 worker_02 实现。
- **不确定性**：`select_baseline_value` 等其他 subsequent-control 种类是否一并纳入 I2，需 worker_02 在 helper 中显式枚举并在 worker_03 补测；本报告建议至少覆盖 `verify_result_validity` + future anchor（病毒学 replay 已证明必需）。

---

## Rerun Requests Or Next Step

1. **worker_02**：按「最小修复建议 §5」实现通用 cross-stage subsequent-control 路径；同步 wire 水合、publication gate、prompt、repair guidance；**不写 D001 特例**。
2. **worker_03**：用保存三轮回包 + §7 合成正反例验证；重点确认 **SYN-REJECT-02/05** 不被误放行；跑 `tests/v2/protocols/test_slice58c_protocol_control_gate.py` 及新增 slice60zz 聚焦测试。
3. **Codex 决策点（如需）**：混合义务（执行+有效窗）是否**强制拆候选**，或允许单候选双绑定；本报告倾向**强制拆分**（与现有 prompt L833–835 一致），实现成本更低且与 R1 双候选结构一致。

**Resume point**：worker_02 从 `_check_supplementary_procedure_stage_alignment` 与 `_validate_supplementary_relations` 引入 I2 分支开始；完成后用 ARTIFACT-R3 改 `affected=flow-baseline` 作为首个 replay 验收用例。
