# Execution Output: phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827 - worker_03

## Boundary And Context Check

- 已完整读取初始上下文与计划。
- 本 work item 仅做五包只读来源、主题、标题族和历史结果核查；未修改源码、测试、生产路径或临床来源文件。
- 未调用语义模型、未启动服务、浏览器、受试者审核或会议。
- 当前执行上下文的 `Source Of Truth` 仍为 `TODO`。本报告将 58q 冻结目录作为待 Codex 确认的审计输入，不宣称其已被项目上下文正式授权。
- 当前全局状态仍应保持 `claims_complete=false`；本轮不形成临床最终验收。

## Work Performed

### 1. 当前冻结身份与包输入核查

当前冻结来源：

- 文档：`CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
- 隔离来源 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 大小：`405567` bytes
- `protocol_version_id`：`D001-02-002:v1.0:phase-ii`
- selected phase：`phase_ii`
- opposite phase：`phase_iii`
- manifest：`d001-ii-phase-closure-20260825-slice58e-manifest`
- snapshot：`d001-ii-phase-closure-20260825-slice58e-snapshot`
- 当前 58q execution state：`planned`，0 个 `run_results`，0 个 `final_output`
- 当前五包目标总数：`12 + 5 + 8 + 7 + 4 = 36`

五个当前包输入均通过 `PhaseApplicabilityAgentInput.model_validate`，并与冻结计划中的 owned 单元逐项一致：

| 包 | 当前 package_id | owned targets | context units | 主题 |
|---|---|---:|---:|---|
| 67 | `pap-ec4f98ba80a20709642f02c5` | 12 | 43 | 试验用药品管理、随机化和盲法 |
| 78 | `pap-6cc36c4dd60c8dcfb917548c` | 5 | 42 | 实验室检查、病毒学检查 |
| 79 | `pap-2e662c2807a2441886f59ff0` | 8 | 40 | 结核筛查 |
| 80 | `pap-15734206834cfab1e9acf554` | 7 | 40 | 妊娠/FSH、皮损照片 |
| 111 | `pap-b1e63af74b347b8a6f54b612` | 4 | 59 | 期中分析 |

### 2. 逐包主题、直接来源和标题族边界

| 包 | 直接 owned 来源与标题族边界 | 关键语义风险及模型验收要求 |
|---|---|---|
| 67 | `body.p719–p726`：试验用药品管理、包装标签、运送储存分发；`body.p727–p729`：随机化和盲法。当前包在 `body.p729` 前结束，`p731` 及 `p734/p738–p741` 为只读上下文，不是 owned。 | `target_index=11`，`body.p729#atom-223-362` 为 `mixed`，必须 `final_disposition=unresolved`；比例、剂量、安慰剂和 II/III 期安排必须完整保留。不得把药品管理、随机化、盲法上下文合并成一个结论。 |
| 78 | `body.p801–p802`：实验室检查；`body.p803–p805`：病毒学检查。 | `target_index=0` 的 `body.p801` 是混合期别注释，必须保持 II 期筛选/12 周与 III 期筛选/16、52 周的糖化血红蛋白访视差异，不能输出单一 `cross_phase_shared`。实验室证据不得广播到病毒学条目。 |
| 79 | `body.p806–p813` 全部属于“结核筛查”标题族；边界在 `p813` 后、`p814` 前。 | 当前八个目标均为 `unknown`，不能因标题或 `body.p765` 的一般性“评估和程序一致”自动判为跨期共用。`p806` 是标题，`p810` 仅为“注：”，二者不能单独支撑临床处置。 |
| 80 | `body.p814–p816`：妊娠试验/FSH；`body.p817–p818`：获取皮损照片。两个标题族不得互相广播。 | `target_index=2` 的 `body.p815#atom-11-74` 为 `mixed`，必须 `unresolved`，保留 II 期第12周与 III 期第16、52周访视差异。皮损照片只说明客观记录/说明，不得扩展成评分或入组条件。 |
| 111 | `body.p1236` 与 `body.p1237#atom-0-15/#15-100/#160-208` 属于“期中分析”标题族。`body.p1237#atom-100-160` 在 context 中，但不是第111或第112包 owned。 | `target_index=2` 的 `body.p1237#atom-15-100` 为 `mixed`，必须 `unresolved`。不得把无包主权的直接 II 期兄弟原子 `body.p1237#atom-100-160` 作为第111包结果，或用它补写 owned 单元。 |

### 3. 逐目标重点核对

- 包67：
  - `target_index=0–7`：药品管理及包装、储存、分发和回收。
  - `target_index=8–10`：随机化/盲法标题及 IWRS、随机表、PGA 分层。
  - `target_index=11`：II 期 `1:1:1`、50/100 mg 和安慰剂与 III 期 `2:2:1`、推荐剂量安排，属于混合期别单元，不能机械归入 II 期。
- 包78：
  - `target_index=0`：空腹采样及两期糖化血红蛋白访视差异。
  - `target_index=1`：新安全性数据触发的其他检测。
  - `target_index=2`：病毒学检查标题。
  - `target_index=3–4`：病毒学筛查项目、28 天内结果接受、HBV/HCV/梅毒条件性复检。
- 包79：
  - `target_index=0`：结核筛查标题。
  - `target_index=1`：γ-干扰素释放试验阳性后的胸部 CT。
  - `target_index=2–3`：活动性/潜伏性结核与随机分组限制。
  - `target_index=4`：注释标记。
  - `target_index=5–7`：潜伏性结核预防治疗、利福平/利福喷丁限制、不确定结果复测。
- 包80：
  - `target_index=0–1`：妊娠/FSH 标题及适用人群。
  - `target_index=2`：混合期别访视安排。
  - `target_index=3–4`：妊娠阳性排除、绝经/非生育能力和 FSH。
  - `target_index=5–6`：皮损照片标题及客观记录要求。
- 包111：
  - `target_index=0–1`：预设期中分析。
  - `target_index=2`：基于 II 期累积数据、是否继续 III 期及推荐剂量，明确为混合语义。
  - `target_index=3`：IDMC 综合疗效/安全性证据及独立统计分析计划。
  - context-only `body.p1237#atom-100-160`：直接 II 期条件，不能进入第111包结果。

### 4. 真实模型输出的通用验收矩阵

真实运行时必须满足：

1. 每包完整覆盖当前 `target_index=0..N-1`，且 `structure_unit_id` 逐项回显；不得多包、漏包或跨包输出。
2. 每条证据的 source unit、source span 和摘录必须来自当前冻结包，并能逐字回溯；context 只能支持判断，不能取得目标所有权。
3. 异质目标不得合并。`unit_kind`、`heading_path`、`phase_scopes`、`excerpt` 或表格语境任一不同，都应独立分组。
4. 当前四个混合目标必须保持 `unresolved`：
   - 67：`body.p729#atom-223-362`
   - 78：`body.p801`
   - 80：`body.p815#atom-11-74`
   - 111：`body.p1237#atom-15-100`
5. `cross_phase_shared` 必须由同一要求/操作/人群的正向两期依据支持；“未限定某期”“两期评估和程序一致”或标题相同不能单独构成依据。
6. `unresolved` 必须记录具体缺失依据；候选 scope 不得返回 `unknown` 或 `mixed`。
7. 不得接受 `UNIT_RESULT_OUTSIDE_FROZEN_PACKAGE`、`EVIDENCE_SPAN_UNIT_MISMATCH`、`EVIDENCE_EXCERPT_NOT_VERBATIM`、`MIXED_UNIT_REQUIRES_ATOMIZATION`、`TARGET_GROUP_HETEROGENEOUS` 等门禁问题。
8. 五包结果仅是限定语义验证证据，不能将 `claims_complete` 改为 `true`。

## Artifacts And Evidence

本轮未创建文件。只读证据：

- `artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/coverage_manifest.json`
- `frozen_phase_plan.json`
- `package-0067-agent-input.json`
- `package-0078-agent-input.json`
- `package-0079-agent-input.json`
- `package-0080-agent-input.json`
- `package-0111-agent-input.json`
- 五个对应的 `package-*-review.json`
- `execution/d001-ii-phase-closure-20260826-slice58q.json`
- `verification-results.json`
- `source-identity-check.json`
- `source-snapshot.json`

历史第79包语义结果：

- 58m 旧包 ID：`pap-d6a1c7d3d06a1c9d18281cda`
- 旧包 owned 单元：11 个，`body.p806–p816`
- 旧结果：11 条，`cross_phase_shared=10`、`unresolved=1`
- 当前第79包：`pap-2e662c2807a2441886f59ff0`，仅 owned `body.p806–p813`
- 旧 `p814–p816` 已属于当前第80包，旧 `p815` 一个混合单元也已拆成当前第80包的三个原子。

因此，历史第79包只能用于人工对照和发现模型行为问题，不能按包号、结果序号或 source ref 机械复用。

## Commands And Observations

使用 `exec_command` 执行只读检查：

- `sed`：读取初始上下文与计划。
- `find`、`rg --files`：定位 58q、58m、58p 包输入、审阅和运行结果。
- `jq`、内联 `python3`：提取五包 owned/context 单元、标题路径、source refs、phase scopes、历史包成员和历史结果状态。
- `PYTHONPATH=. .venv/bin/python`：重新加载五个 `PhaseApplicabilityAgentInput` 合同。

关键结果：

```text
PASS package=67 id=pap-ec4f98ba80a20709642f02c5 targets=12 context=43 packets=5
PASS package=78 id=pap-6cc36c4dd60c8dcfb917548c targets=5 context=42 packets=6
PASS package=79 id=pap-2e662c2807a2441886f59ff0 id=... targets=8 context=40 packets=6
PASS package=80 id=pap-15734206834cfab1e9acf554 targets=7 context=40 packets=6
PASS package=111 id=pap-b1e63af74b347b8a6f54b612 targets=4 context=59 packets=5
PASS all five PhaseApplicabilityAgentInput contract reloads
```

另核对：

- 五包 owned 单元与 manifest 逐项完全一致。
- 源文件现场 SHA-256 与 manifest 一致，大小 `405567` bytes，mtime_ns `1779871799537588300`。
- 58q 当前 execution state 为 `planned`，没有语义结果。
- 58q `verification-results.json` 明确记录 `claims_complete=false`、`semantic_agent_calls_performed=0`。
- 当前代码中 `stable_phase_applicability_package_id()` 将包序号纳入 package identity；冻结包合同要求 owned/context 不重叠且 package ID 必须由冻结 owned 身份生成。
- 当前 gate 对 mixed unit 的非 `unresolved` 结果会产生 `MIXED_UNIT_REQUIRES_ATOMIZATION`。

### 此前执行报告的过度结论

1. `runs/execution/phase5-slice58r-affected-package-semantic-validation-20260826/worker_03.md:27` 写有“**No D001 semantic execution has ever run**”。该表述过宽：58l/58m 已存在第79包真实语义运行及持久化结果。准确说法应是：58o/58p/58q 当前检查点没有语义结果；并不代表 D001 从未执行过语义模型。
2. 同一报告的“没有历史语义结果可复用或失效”也不成立于全局范围。当前 58q 确实未复用历史结果，但 58m 的第79包历史目录和结果明确存在。
3. 58m 第79包的 `status=已解析` 和 `cross_phase_shared=10` 只能说明旧包输出通过了当时的解析/门禁路径，不能等同于当前第79包的临床接受。旧包成员已经包含当前第80包的内容。
4. 旧第79包将标题 `p806`、注释标记 `p810` 以及多个结核限制条目统一依据 `p765` 判为跨期共用，属于需要人工复核的过度推断：`p765` 是一般章节级语句，不能自动覆盖每一个结核义务，更不能给标题或“注：”本身赋予临床处置。
5. 58q 身份审阅中“历史语义结果未复用”的结论在“本次 58q 未复制旧结果”这一窄范围内成立；不能扩展解释为“没有历史语义运行”或“当前五包语义已验收”。

## Blockers Or Missing Environment

- Source Of Truth 未由当前执行上下文明确列出；需 Codex 确认 58q 冻结目录及其中隔离 DOCX 是本次真实运行的授权来源。
- 当前尚无本次五包隔离子计划的最终 package IDs。若 worker_01 将全计划重编号为 1–5，必须重新生成 package ID、plan ID 和 old→new identity map；旧 58q package ID 不得直接用于新运行。
- 当前没有五包真实模型输出，因此尚不能判断 unknown 条目的最终期别处置，也不能进行临床最终接受。
- 本轮无读取/环境工具阻塞；未运行模型是任务边界要求，不是故障。

## Rerun Requests Or Next Step

1. Codex 确认 58q 冻结目录及隔离来源授权范围。
2. 待限定包选择/检查点修复完成后，建立全新的隔离子计划和 run ID，持久化：
   - 旧 ordinal/package ID；
   - 新 ordinal/package ID；
   - owned source refs/structure IDs；
   - 当前 manifest、plan、prompt 和 source hash。
3. 串行执行 67、78、79、80、111 五包；只接受当前新冻结包的完整结果。
4. 对四个 mixed 目标执行确定性门禁；任何非 `unresolved` 结果需要拒绝或人工修复。
5. 对第79包历史结果仅做人工对照，重点核查其 `p765` 广播行为；不得导入旧 `p814–p816` 结果。
6. 五包即使全部通过，也必须继续保持 `claims_complete=false`，不得扩大到其余包、受试者或前端。
