独立审查从初始读集开始：先读会议上下文与主会场计划，再按证据核对门禁冲突、冻结来源闭包和中文结构指令。主会场计划和上下文仍是 TODO，需要在工作区内定位 5.8d 协议、v7 失败证据、冻结来源闭包和中文结构指令。已定位 61ag 执行、61ah 重放和门禁代码。接着只读核对 v7 失败链、重分区集合和中文修订指令。v7 第 4 次尝试已出现 `REPAIR_SCOPE_ESCAPE`。接着核对有界修订如何限制义务组改写，以及 `BINDING_MISSING` 为何进入重分区集合。发现三向冲突迹象：`BINDING_MISSING` 要求同组并列，`MIXED_DECISION_STAGE_CONTROL` 又要求拆候选。接着核对门禁实现、v7 候选结构和 985 回归口径。审查结论已经对齐：v7 失败来自门禁与有界修订冲突，把 `BINDING_MISSING` 放进来源闭包重分区过宽。下面按会议输出格式给出独立审查。

# Conference Participant Output: phase5-slice61ai-conditional-waiver-repair-contract-review-20260828 - general_grok46

## Boundary Check

- **Role:** `general_grok46` / Grok Build `grok-4.6`；Codex 主持的并行会商参与者 2。只读审查，不修改源文件，不启动模型重放，不发布控制点，不声称最终临床/监管/视觉验收。
- **Workspace:** runner 绑定的当前工作区 `.`。未读 `/Users/smkzw/.codex/AGENTS.md`、`/Users/smkzw/.hermes/SOUL.md`。未读本会商其他参与者输出，也未读 `reviews/codex_conference_phase5-slice61ai-..._review.md`。
- **Initial read set:** `context/phase5-slice61ai-..._conference_context.md`、`plans/codex_main_venue_phase5-slice61ai-...md`。两者 Source/Scope/分解均为 TODO，不能单独构成审查依据。
- **Why extra reads:** 必须独立重建权威链路。额外只读：`app/protocols/protocol_control_repair_errors.py`、`app/protocols/protocol_control_gate.py`、`app/agents/protocol_control_deconstructor.py`、`tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`、v6 重评 `artifacts/phase5-slice61af-.../parent-clinical-reassessment.json`、v7 重放 `artifacts/phase5-slice61ah-...`（`runner-result.json`、`replay-summary.json`、`conversation-history.json`、`clinical-qc.json`、`compact-handoff.md`）、`reviews/codex_execution_phase5-slice61ag-..._review.md`、61ag worker 记录、checkpoint `CHECKPOINT_20260828_VIROLOGY_WAIVER_REASSESSMENT_PAUSED.md`、`docs/PROJECT_CONTEXT.md` 相关段。
- **Changed artifacts:** 无。`pytest tests/v2/protocols --collect-only` 仅用于核对 985 收集数，未跑通全量、未调用模型。
- **Dedup note:** 关联执行包 `phase5-slice61ag` 已落地代码；本轮审查该合同，不把 61ag `accept` 当作 v7 临床闭包。

## Independent Work Product

### 最高影响缺陷（先于其他结论）

**缺陷：** `CONDITIONAL_EXEMPTION_BINDING_MISSING` 的目标形态（同一义务组内并列 `verify_result_validity` + 免予 `complete_or_verify`）与当前有界修订机械装置互斥；把它放进 `CANDIDATE_REPARTITION_GATE_CODES` 能“解开”组改写，但解的是来源闭包 1→N 重分区，宽度覆盖 v6 已否决的同源无条件筛选兄弟改写。这不是措辞问题，是门禁、修订授权和临床否决三者对不齐。

**替代修复（建议合同，非本轮实现）：**

1. **从 `CANDIDATE_REPARTITION_GATE_CODES` 移出 `CONDITIONAL_EXEMPTION_BINDING_MISSING`。** 保留 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`（以及既有 `MIXED_*` / `ACTION_TARGET_SCOPE_MISMATCH`）。
2. **新增更窄授权**，例如 `allow_same_candidate_obligation_regrouping`：只允许被点名候选在**同一 `source_structure_unit_ids` 键、不增删候选、不扩展兄弟来源闭包**的前提下合并/重排义务组并增补同组原子。
3. **`SCOPE_SPLIT` 才走来源闭包重分区**，因为修复对象是同源兄弟，不是单候选组结构。
4. **合成回归必须覆盖 v7 真实形状：** 先前 2 个替代 DNF 组（组 0 有效期、组 1 免予）→ 合并为 1 组 2 原子应通过窄授权；同一授权不得允许再拆出无时间约束的筛选 `complete_or_verify` 兄弟。
5. **中文结构指令保留当前 kind 级表述，并补一句禁止抄执行清单。** 见下文。

### 1. v7 失败是否源于门禁与有界修订冲突

**结论（推断，有工件支撑）：是。主因是 attempt 3→4 的门禁要求与原子级有界修订互斥，不是单纯模型胡写。** 次要失败（attempt 1/2/5）是另一条链，不能用来否定主因。

**Evidence — v7 五次结果**（`runner-result.json`，`status=需要核对`，`final_output=null`）：

| 轮次 | 结果 | 问题 |
|---|---|---|
| 1 | `schema_invalid` | 流程必做单/多目标字段并存；补充关系缺 `affected_workflow_stage_id` |
| 2 | `publication_invalid` | `PROCEDURE_VISIT_SCOPE_UNCOVERED`：p805 含首次给药前访视，链接目录只覆盖筛选 |
| 3 | `publication_invalid` | `CONDITIONAL_EXEMPTION_BINDING_MISSING` `[pcc-eb7ff7003b1a10e3100ded18]` |
| 4 | `schema_invalid` | `REPAIR_SCOPE_ESCAPE: 义务原子定向修订不得拆分、合并或重排义务组` |
| 5 | `schema_invalid` | 带时间约束的新义务用了泛化 `complete_or_verify` |

**Evidence — attempt 3 的真实 wire（conversation-history assistant msg 5）：** 单一候选，来源 `su-3de4633…`（p805）+ `su-86389…`（p804），**两个替代 DNF 组**：

- 组 0：`verify_result_validity`，`first_dose_date` 前 28 天，陈述里已含“无需再次检查”。
- 组 1：`complete_or_verify`，`time_constraint=null`，纯免予陈述。

门禁 `_check_conditional_exemption_binding` 只看**同一义务组**内的 `timed_spans`。组 1 的免予原子因此被判未绑定。临床语义上两组其实是“有效期 OR 免予”，不是“有效期 AND 免予”。门禁拒绝是对的。

**Evidence — 有界修订为何挡住正确修复：** `BINDING_MISSING` 会带上 `obligation_source_span_ids`（v7 为 `body.p804`/`body.p805`）。当 `allow_candidate_repartition=False` 时，`_restore_bounded_wire_repair` 进入原子路径：组数必须不变、原子 `source_span_ids` 键必须一一对应。因此：

- 不能把 2 组合并为 1 组（attempt 4 正是 2→1，触发“不得拆分、合并或重排义务组”）；
- 也不能在组 1 增补有效期原子（键集合会变，将触发“需要唯一且不变的原文定位”）。

attempt 4 丢掉了有效期原子、只留免予，形状更差，但**组数变化这一动作本身正是门禁所要求的并列**。这是机械冲突，不是偶然。

**Evidence — 当前代码若启用重分区会怎样：** `allow_candidate_repartition=True` 会清空 `mutable_obligation_source_span_ids`，从而绕过组锁。v7 attempt 4 的逃逸文案只在原子路径出现，说明 **v7 当时并未按重分区解锁组改写**。当前仓库却已把 `BINDING_MISSING` 列入 `CANDIDATE_REPARTITION_GATE_CODES`，属于事后扩权，不是 v7 现场行为。

**Inference：** 把 attempt 1 的 schema、attempt 2 的访视覆盖算进“v7 因豁免门禁失败”会稀释主因。它们消耗了修复预算，但 attempt 3 已经给出可诊断的豁免结构；失败在授权无法执行“同组合并”。

### 2. 将 `BINDING_MISSING` 纳入冻结来源闭包重分区是否过宽

**结论：过宽。应否决该扩权，或至少不得与 `SCOPE_SPLIT` 共用闭包扩张。**

**Evidence — 闭包扩张算法**（`protocol_control_deconstructor.py` 约 2573–2632）：`allow_candidate_repartition` 会把与被点名候选**任一来源单元相交**的全部候选键吸入 `mutable_candidate_source_union`，并允许该全集上增删候选，只要并集守恒。

**Evidence — v7 被点名候选已跨 p804+p805。** 闭包至少是这两个 owned 单元。v6 形状下，无条件筛选兄弟 `pcc-136f6e944a758e942f4aa33b` 与豁免候选共享 `su-86389…`，会被一并解冻。那正是父级临床否决点。

**Evidence — 测试把扩权正当化：** `test_conditional_exemption_binding_allows_bounded_obligation_regrouping` 在 `allow_candidate_repartition=True` 下接受 2 组→1 组。测试名写 “bounded obligation regrouping”，实现却借用**候选重分区**通道。这是合同把“组改写”误挂到“候选拆分”上。

**Inference：** `BINDING_MISSING` 的最小必要突变是**一个候选内部的 DNF 组结构**。来源闭包重分区的最小必要突变是**候选个数/分区**。两者不是同一授权。`SCOPE_SPLIT` 需要兄弟可变；`BINDING_MISSING` 不需要。

**Recommendation：**

| 代码 | 修订授权 |
|---|---|
| `BINDING_MISSING` | 同候选义务组改写；禁止候选计数变化；禁止闭包扩张 |
| `SCOPE_SPLIT` | 来源闭包重分区（合并/收回无条件兄弟）；禁止再拆出无条件筛选完成 |
| `MIXED_DECISION_STAGE_CONTROL` | 保持现有重分区（筛查执行 vs 未来锚点有效性） |

若 Codex 坚持不增新旗标，次优但仍窄的做法是：`BINDING_MISSING` 只把 `mutable_obligation_source_span_ids` 放宽为“允许同候选内增补/合并组”，**仍设置 `allow_candidate_repartition=False`**。当前实现做不到：重分区旗标会无条件清空 span 锁。

### 3. 通用中文结构指令能否忠实表达结果有效期与免予后果

对照两版指令。

**v7 现场指令（conversation user msg 6）：**  
“必须在同一候选、同一语义分支中同时保留该条件与免予后果。不得把有条件豁免改写为无条件豁免，也不得删除豁免后果。”

**当前代码指令（deconstructor L1054–1060）：**  
同一候选**同一义务组**并列 `verify_result_validity`（带有效期 `time_constraint`）与 `complete_or_verify`（只表达免予且 `time_constraint=null`）；不得把有效期改成 trigger、不得拆成替代义务组、不得删除免予后果；最低证据只保留结果日期与命名锚点，删除“确认未重复/未再次执行”。

**当前门禁文案（gate L1808–1809）：**  
“结果有效期核对与免予后果必须在同一义务组并列表达”。

**Evidence：**

- v7 指令的“语义分支”不足以禁止 DNF **替代组**。attempt 3 完全符合“同一候选、同一语义分支”，仍被门禁拒绝。
- 当前指令与门禁对齐，且能解释 attempt 5：把 28 天绑到 `complete_or_verify` 会被 schema 拒绝。
- 当前指令要求删除非发生证据，与 v7 全程证据“确认未重复执行病毒学检查”一致，也与 `EXEMPTION_EVIDENCE_OVERSTATED` 一致。attempt 3 先死在 `BINDING_MISSING`，过度证据门禁可能未作为独立修复轮发出。
- `_routine_requirement_text` 会剥掉含“无需”的分句，因此**纯免予** `complete_or_verify` 一般不会触发 `MIXED_DECISION_STAGE_CONTROL`。`test_combined_routine_action_and_waiver_still_requires_stage_split` 触发 MIXED 是因为同组还留着“完成三项检查”类执行句。

**Inference：** 当前中文指令对“有效期 vs 免予”的 kind/组/时间约束表达是忠实的，**仍缺一条防回归**：不得把“将根据标准实验室程序进行…检查”等执行清单写入免予原子的 statement/excerpt。否则 MIXED 会在修好绑定后立刻打回。指令也不应承担 p804 八项共享豁免——那是 `SCOPE_SPLIT` 的职责，混写会把模型推向错误拆分。

**Recommendation：** 保留当前 kind 级中文；把“语义分支”永久停用；补一句“免予原子不得抄录检查执行清单”；`SCOPE_SPLIT` 指令保持“不得拆成兄弟无条件执行”。不要在 `BINDING_MISSING` 指令里写 D001/病毒学专名。

### 4. 985 项回归与 v7 临床否决边界

**回归：**

- **Evidence：** 本轮 `pytest tests/v2/protocols --collect-only -q` → **`985 tests collected in 0.35s`**。
- **Evidence：** 61ag Codex 独立验证记录为 **`984 passed, 58 warnings`**。checkpoint 更早为 975/977 collect。
- **Uncertainty：** 本轮未重跑 985。收集数 ≠ 通过数。+1 相对 984 的身份未核（很可能是组改写/重分区合同测试，而这些测试会把有问题的扩权锁进绿线）。
- **Recommendation：** 在改授权之前，不要把 985 collected 或 984 passed 当作当前合同已回归。先改测试合同（`BINDING_MISSING` 不在重分区集合；窄授权有正反例），再跑 `tests/v2/protocols`。失败先定位共享原因，不启动 v8。

**v7 临床否决边界（建议 Codex 维持否决，不发布）：**

v6 否决点仍然有效，且 v7 **没有**给出可接受替代：

1. **不得发布。** `gate.accepted=false`，无 hydrated 终稿，`claims_complete=false`。
2. **不得把 attempt 3 的“已有有效期原子”读成临床通过。** 有效期与免予被放在替代组，语义是 OR。
3. **v7 没有再现 v6 的 HBsAb/HBeAg/HBeAb 无条件筛选兄弟**，但不能因此翻案。处置笔记承认三项为流程增量，义务原子却从未点名这三项，也未证明它们继承 28 天有效期。
4. **p804 与 p805 被合成一个候选。** p805 的条件性 HBV-DNA / HCV-RNA / 梅毒非特异性检测被推给流程目录“已覆盖”，豁免句被并进 p804 候选。这会掩盖 p805 自有条件分支，也放大来源闭包。
5. **非发生证据全程未删**，与豁免模态门禁冲突。
6. **attempt 2 的访视覆盖**说明 p805“首次给药前 28 天结果”与仅含筛选的流程目标冲突；用 `required_procedure` 声称完整覆盖会逼模型改处置或改候选范围，和豁免绑定抢同一轮预算。

**Safe provisional path：** 保持 v6 重评 `parent_clinical_acceptance=rejected`；v7 不得升级为接受；不覆盖 v5/v6/v7 工件；不扩大到其余方案包。

### 最重要异议、方案、决策点、给 Codex 的有界问题

**异议 1：** 用候选重分区修复义务组绑定，等于用 v6 的病给 v7 的伤做手术。  
**方案：** 窄的同候选组改写授权，见上。

**异议 2：** `test_conditional_exemption_binding_allows_bounded_obligation_regrouping` 和 `CANDIDATE_REPARTITION_GATE_CODES` 含 `BINDING_MISSING` 会把过宽合同测成绿。985 收集数不能为该合同背书。

**异议 3：** 当前中文指令已比 v7 现场稿忠实，但若机械授权仍是重分区，模型仍可在闭包内合法拆出无条件筛选兄弟；`SCOPE_SPLIT` 只有在“仍存在已绑定豁免兄弟”时才开火（`has_bound_waiver` 前置）。若修订先拆掉绑定再拆检查，两道门禁都可能漏。

**Decision points for Codex：**

1. 是否接受“`BINDING_MISSING` ≠ 来源闭包重分区”？
2. 窄授权是新旗标，还是改造原子路径允许组数变化/增补原子但禁止候选计数变化？
3. v8 是否必须先有上述合成回归，再允许一次 MTPLX medium？本参与者建议：**先合同+测试，后重放。**
4. p804/p805 是否必须拆成不同候选（面板豁免 vs 条件性追加检测）？建议作为临床合同写明，不要靠模型自由合并。

**Bounded questions：**

1. Codex 是否授权新增 `allow_same_candidate_obligation_regrouping`（或等价原子路径放宽），并命令下一执行包从 `CANDIDATE_REPARTITION_GATE_CODES` 删除 `BINDING_MISSING`？若否，请给出仍要把 `BINDING_MISSING` 留在闭包重分区里的临床例子。  
   *Why it matters:* 这是能否在不重开 v6 缺口的前提下修好 v7 的分叉点。  
   *Provisional:* 视为过宽，不重放。

2. 对 DNF，Codex 是否确认义务 `groups` 仅为替代（OR），绑定检查必须同组 AND，不得把“候选内任一组有有效期”算通过？  
   *Why it matters:* 若放宽为候选级绑定，v7 attempt 3 会假通过。  
   *Provisional:* 保持同组 AND。

3. 本轮可否将 985 仅记为 collect，不记为 pass，并要求改合同后重跑全量才允许 v8？  
   *Provisional:* 是。

## Evidence And Assumptions

**Evidence（观察/工件）：**

- 会商上下文与主会场计划未填 Source/Scope；审查依据是代码、测试与 v6/v7 工件。
- v7：5 次 MTPLX medium，262.55s，未水合，未发布。
- attempt 3 双替代组 + attempt 4 组数变化被 `REPAIR_SCOPE_ESCAPE` 拒绝。
- 当前 `CANDIDATE_REPARTITION_GATE_CODES` 含 `BINDING_MISSING` 与 `SCOPE_SPLIT`。
- 重分区路径清空义务 span 锁并按来源并集解冻兄弟候选。
- 门禁绑定按组检查 `timed_spans`；MIXED 在剥除豁免分句后仍看到无锚点执行句才开火。
- 中文指令已从“语义分支”改为“同一义务组 + 两个 kind”。
- collect-only = 985；61ag 记录 984 passed。
- v6 重评否决 HBsAb/HBeAg/HBeAb 无条件筛选完成。

**Assumptions：**

- 义务 DNF `groups` 是替代不是合取。这与代码和 v7 失败一致。
- v7 运行时 `BINDING_MISSING` 尚未按重分区解锁（否则 attempt 4 不会走到组锁文案）。
- 未读其他会商角色，结论独立。

**Inference：** 见上各节。核心推断：v7 主失败 = 正确门禁 × 过窄原子修订；拟议扩权 = 过宽闭包重分区。

**Uncertainty：**

- 未重跑 985。
- 未做 live gate 对 v7 raw JSON 的离线回放（避免被理解为重放）；结构判断来自 conversation JSON。
- `_candidate_ids_from_wire` 同源指纹歧义未在本轮深挖（61ag worker_02 已标）。
- 未核对 p328/流程第 14 项目录 visit_instance 的完整字段，attempt 2 访视缺口以 runner 文案为准。

## Risks, Gaps, And Verification Needs

- **临床风险：** 闭包重分区可再次把 p804 八项里的增量检查写成无条件筛选完成。
- **工程风险：** `REPAIR_SCOPE_ESCAPE` 不更新 `repair_baseline`，但下一轮 prompt 改写为逃逸问题（v7 user msg 8 义务定位为空、候选 id 已变）。模型在旧锁上执行新指令，attempt 5 形状恶化。
- **测试缺口：** 没有 runner 级用例：attempt 3 的 2 组豁免结构 → 同候选 1 组 2 原子应成功，且禁止拆出筛选兄弟。
- **指令缺口：** 免予原子抄执行清单 → MIXED。
- **回归缺口：** 985 collected 未证明当前工作区 passed。
- **范围缺口：** p804/p805 合并、p805 条件追加检测、非发生证据、访视覆盖，均未进入本修订合同。
- **Verification needed (Codex-owned)：** 合同测试改写后的 `tests/v2/protocols` 全量；对冻结 v7 raw JSON 的**离线** hydrate/gate（非新模型调用）；临床否决清单写入不可变记录，不覆盖 v6 重评。不要做浏览器/视觉验收。

## Recommended Next Step

请 Codex 将本轮合同定为：**拒绝把 `CONDITIONAL_EXEMPTION_BINDING_MISSING` 留在冻结来源闭包候选重分区集合中**；改为同候选义务组改写授权；`SCOPE_SPLIT` 单独承担同源无条件兄弟。先改测试合同并跑协议层回归，再考虑一次 v8 MTPLX medium。保持 v6/v7 不发布，`claims_complete=false`。

若 Codex 需要同会话跟进，恢复点是：确认是否新增窄旗标，以及是否立即从 `CANDIDATE_REPARTITION_GATE_CODES` 删除 `BINDING_MISSING`。在得到该决定前，安全路径是停止模型重放。
