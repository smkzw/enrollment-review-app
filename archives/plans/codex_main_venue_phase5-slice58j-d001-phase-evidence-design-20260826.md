# Codex Main-Venue Plan: phase5-slice58j-d001-phase-evidence-design-20260826

Date: 2026-08-26
Objective: 以只读独立顾问身份挑战 D001 II 人工控制矩阵的期别正向依据闭包设计。审阅当前 82 行闭包矩阵、1,840 单元冻结清单、期别 Agent 合同和 5.8d 检查点，回答：如何只针对矩阵实际引用的 152 个单元建立可回源的 selected/opposite/shared/unresolved 依据视图；如何区分共同章节的正向共用依据、仅未限定期别、对侧期引用、II期流程表、表5及结核妊娠等异质结构；哪些结论可确定性派生，哪些必须真实语义 Agent 或 Codex 临床核对；如何用最小代表包而非全跑137包证明闭包；列出会导致治疗后污染、重复计数、错误跨期共享或伪完整声明的反例和验收门槛。不得修改文件，不得宣称最终医学验收。

## Task Decomposition

1. 独立核对 152 个来源单元的结构、既有期别范围与矩阵处置之间的矛盾类型，不接受“未限定即共用”。
2. 设计正向依据视图：每个处置必须能回到冻结单元、标题/表格语境、直接原文和证据极性，并区分确定性派生、语义建议与 Codex 临床裁定。
3. 设计最小代表包和反例矩阵，证明共同章节、II 期流程、混合表格、对侧期引用及入组前时间边界不会被误合并。
4. Codex 对两份独立意见逐条回到当前矩阵/清单验证，选择最小实现，不由参与者关闭 5.8d。

## Source Packet

- 当前冻结清单：`research/d001-ii-phase-closure/coverage_manifest.json`
- 当前闭包矩阵及报告：`research/d001-ii-phase-closure/d001-ii-control-matrix-closed.json`、`d001-ii-control-matrix-closure-report.json`
- 交叉章节子集及报告：`research/d001-ii-phase-closure/d001-ii-cross-section-controls-closed.json`、`d001-ii-cross-section-controls-closure-report.json`
- 期别合同：`app/agents/phase_applicability.py`、`app/protocols/phase_applicability.py`、`app/domain/contracts/phase_applicability.py`
- 当前检查点：`CHECKPOINT_20260826_PHASE_PACKING_AND_RATIONALE_ACCEPTED.md`、`CHECKPOINT_20260826_D001_MATRIX_SOURCE_CLOSURE_ACCEPTED.md`
- 已知事实：82 行矩阵引用 152 个唯一单元；116 个仅 `unknown`、35 个仅 `phase_ii`、1 个 `mixed`；矩阵当前有 60 行 `cross_phase_shared`、22 行 `selected_phase_applicable`，但这只是待核对人工处置，不是最终真值。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | `alibaba` | `qwen3.8-max` | `runs/conference/phase5-slice58j-d001-phase-evidence-design-20260826/general_pi_qwen38.md` |
| `general_grok46` | `cursor-cli` | `auto` | `runs/conference/phase5-slice58j-d001-phase-evidence-design-20260826/general_grok46.md` |

- `general_pi_qwen38` 重点挑战临床期别证据语义、共同章节正向证据、对侧期引用和治疗后污染。
- `general_grok46` 重点挑战数据合同、代表包覆盖、确定性门禁、重复计数和可执行验收矩阵；仍须独立核对整体目标，不得只做代码审查。

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 初始化：2026-08-26 04:31 北京时间。
- 运行：按 guard 生成命令串行执行；单角色最长 120 分钟硬等待，同会话补全优先于 fallback。
- 结束、fallback 和采纳情况待实际 runner 返回后填写。

## Codex Verification Checklist

- [ ] 每个重要结论能回到当前冻结清单或闭包矩阵的具体字段，不引用旧 1,689 单元汇总。
- [ ] 参与者没有把矩阵既有处置当成真值，也没有把来源闭包等同于期别闭包。
- [ ] “共同适用”均要求正向依据；无期别限定、标题邻近、方案总体名称不能单独成立。
- [ ] 代表包按异质风险覆盖，不以随机抽样或纯数量阈值替代。
- [ ] 后续实现保持 `claims_complete=false`，直到 82 行控制与所需全文处置都通过临床核对。
