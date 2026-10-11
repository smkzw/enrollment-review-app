All evidence gathered. Compiling the final report.

# Execution Output: phase5-slice58r-affected-package-semantic-validation-20260826 - worker_02

## Boundary And Context Check

- 已读初始读集：`context/phase5-slice58r-affected-package-semantic-validation-20260826_execution_context.md`、`plans/codex_execution_phase5-slice58r-affected-package-semantic-validation-20260826.md`。上下文中 Source Of Truth 仍为 TODO；本审计以工作树内已接受的 58q 工件为权威输入（`artifacts/phase5-slice58q-mixed-paragraph-strong-boundary-20260826/`，run_id `d001-ii-phase-closure-20260826-slice58q`，源 sha256 `362443…f2dd98` 经 `source-identity-check.json`/`freeze_metadata.json` 校验未变）。
- 边界遵守：只读。未修改任何代码/工件/源文件，未调用任何语义模型 Provider，未启动浏览器。`claims_complete=false` 维持（58q 工件自身即声明 `claims_complete:false`、`semantic_agent_calls_performed:0`）。
- 额外读取（为补齐逐包证据，均在工作区内）：五包 agent-input/review、`atom-target-reconciliation.json`、`coverage_manifest.json`、`frozen_phase_plan.json`、`diff-qc.json`、`package-narrative-consistency.json`，以及历史语义运行 `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/`（3 个 run）、`artifacts/phase5-slice58m-d001-six-package-semantic-remediation-20260826/`（1 个 run）。

## Work Performed

对 58q 第 67、78、79、80、111 包做了逐包只读临床与来源审计：核对其冻结身份、owned/context 成员、混合段落原子、全文（coverage manifest 原文）、与已接受 5.8o / 被拒 58p 的成员差异、包邻位（81/112），并全库检索历史语义结果目录。

## Artifacts And Evidence

无新工件（任务只要求输出面向父级的核对清单）。证据全部来自上述只读工件，要点如下。

### 五包身份基线（58q 当前，selected_phase=phase_ii，opposite=phase_iii）

| 包 | package_id | owned | 相对已接受 5.8o |
|---|---|---|---|
| 67 | `pap-ec4f98ba80a20709642f02c5` | 12（p719–p728 整段 + p729 两原子） | 改变：整段 p729 → atom-0-223 / atom-223-362，11→12 |
| 78 | `pap-6cc36c4dd60c8dcfb917548c` | 5（p801–p805） | **完全一致**（唯一未变身份包） |
| 79 | `pap-2e662c2807a2441886f59ff0` | 8（p806–p813） | 改变：失去 p814/p815/p816（转入 80），11→8 |
| 80 | `pap-15734206834cfab1e9acf554` | 7（p814、p815 三原子、p816–p818） | 改变：p819–p827 转入 81；仅 p817/p818 与旧 80 共有 |
| 111 | `pap-b1e63af74b347b8a6f54b612` | 4（p1236、p1237 三原子） | **全量换血**：旧 111=p1238–p1247（已全数转入 112“数据采集与管理”），新 111=p1236–p1237，common=0 |

### 逐包核对清单

**第 67 包 — 试验用药品管理 + 随机化**
- 目标主题：`研究治疗 > 试验用药品管理`（包装和标签、运送/储存/分发，p719–p726）+ `研究治疗 > 随机化和盲法 > 随机化`（p727–p729）。
- 期别混合点：`body.p729#atom-223-362`（scopes=mixed）——“Ⅱ期按 **1:1:1** 随机至 CMS-D001 50 mg QD / 100 mg QD / 安慰剂；Ⅲ期按 **2:2:1** 随机至 50 mg QD / 100 mg QD（**或基于Ⅱ期研究结果确定的推荐剂量组**）/ 安慰剂”。全文已回放核实。
- 重点验证：① II/III 随机比例与组构成必须分离输出，不得互相污染；② Ⅲ期 100 mg 组的“基于Ⅱ期结果确定”是跨期依赖，应记为 cross-phase 条件，不能作为 III 独立事实；③ p719–p728 全部 scopes=unknown（IPM 编号/标签/专柜上锁/护士分发、IWRS 随机、PGA 3/4 分层随机表），条款内无期别标记，语义判定为真正的未决边界；④ 强边界完整性：随机比例/剂量/安慰剂组保留在 atom-223-362 单一条款内（58q review 已确认未碎裂）。
- 未决边界：p729#atom-0-223（随机方法学）是 II 独享、III 独享还是 cross-phase，文本无标记，需模型判定。

**第 78 包 — 实验室检查注脚 + 病毒学检查**
- 目标主题：`研究评估和程序 > 研究期间的检查和评估 > 实验室检查`（p801 注脚、p802）+ `> 病毒学检查`（p803–p805）。
- 期别混合点：`body.p801`（scopes=mixed，**完整单元，禁止再拆**）——“空腹采样；糖化血红蛋白 **Ⅱ期仅筛选、12周**；**Ⅲ期仅筛选、16周、52周**”。
- 重点验证：① HbA1c 的 II/III 访视清单须按期输出且不得把 12周 误挂 III、16/52周 误挂 II；② “空腹采样”与 ②（p802 新安全性数据下可加测）应识别为 cross-phase 共享；③ 病毒学 panel（HBV/HCV/HIV/梅毒）及 HBV-DNA/HCV-RNA 确认检测、梅毒非特异复测，p804–p805 均 unknown，28 天窗口条款“可接受首次给药前 28 天内结果，无需再次检查”对两期均适用。
- 未决边界：病毒学 28 天窗口在 II 与 III 是否一致（文本同一句，默认 cross-phase，需模型确认）。

**第 79 包 — 结核筛查**
- 目标主题：`研究期间的检查和评估 > 结核筛查`（p806–p813，含注脚 p810、三条 list_item p811–p813）。
- 期别混合点：**无 mixed-scope 单元**；全部 8 单元 scopes=unknown。
- 重点验证：① 活动性结核不得随机（p808）、潜伏性结核须随机前完成 ≥4 周治疗（p809/p811）是随机前要求，默认 cross-phase；② 禁用利福平/利福喷丁预防（p812）、不确定结果复测一次（p813）应识别为通用规则；③ 本包是五包中唯一存在**真实历史语义结果**的包（见下），执行时必须与旧身份隔离。
- 未决边界：TB 筛查要求整体无期别标记，II/III 适用性完全依赖模型判定。

**第 80 包 — 妊娠试验/FSH + 皮损照片**
- 目标主题：`研究期间的检查和评估 > 妊娠试验或 FSH 检测`（p814–p816）+ `> 获取皮损照片`（p817–p818）。
- 期别混合点：`body.p815#atom-11-74`（scopes=mixed）——“筛选、基线、**第12周（Ⅱ期）**、**第16、52周（Ⅲ期）**和提前退出访视进行血清妊娠试验”。
- 重点验证：① atom-11-74 按期拆分时“提前退出访视”对 II/III 均适用，不得只挂一期；② “仅限有生育能力的女性”（atom-0-11）与 p816（绝经 FSH 仅筛选期；初潮前/绝经/永久绝育=无生育能力）是共享资格界定；③ 筛选妊娠阳性=筛选失败（atom-74-161）跨期适用；④ 皮损照片（p817–p818）明确“仅为客观记录”、细节见独立拍照手册——边界事实，不得引申为疗效评估条款（疗效评价已属第 81 包 p819 起）。
- 未决边界：FSH 检测（仅绝经、仅筛选期）无期别标记；II 与 III 的妊娠试验频次是否除 12周/16/52周 外一致。

**第 111 包 — 期中分析**
- 目标主题：`统计学考虑 > 统计分析 > 期中分析`（p1236 标题 + p1237 拆分原子）。
- 期别混合点：`body.p1237#atom-15-100`（scopes=mixed）——“基于累积的 **II 期**有效性和安全性数据，由 IDMC 向申办方提供建议：能否继续 **Ⅲ期**、推荐 Ⅲ期剂量”。
- 重点验证：① 该原子是“以 II 期数据服务 III 期决策”的跨期条款，II 侧事实（数据输入）与 III 侧事实（决策输出）须分列，不得整体判为单一期；② p1237#atom-0-15（预设期中分析）与 atom-160-208（IDMC 综合评估、另见独立期中 SAP）为 unknown 研究级陈述；③ **孤儿单元 `body.p1237#atom-100-160`**（“II 期 50% 参与者完成第 12 周访视后启动”）：scopes 直接为 `["phase_ii"]`，在 `expected_structure_unit_ids`（1303）之外、无包主权（111 与 112 均不拥有）——reconciliation 已将其单列为 `direct_selected_phase_applicable_outside_unresolved_plan=1`。
- 未决边界：父级需确认孤儿单元 p1237#atom-100-160 的处理口径——按合同它不是语义目标（结构性 II 期直接单元），执行入口必须**显式声明其去向**（结构直录而非丢弃、不得被 111/112 借包认领），不得静默消失。

### 旧语义结果不得复用清单（身份变化）

| 包 | 历史语义目录（均已只读核实） | 不得复用原因 |
|---|---|---|
| 79 | ① `phase5-slice58l-…/qwen38-baseline-host-real-run-20260826/package-0079`（状态“需要核对”，2×transport_failed）② `…/qwen38-baseline-host-real-run2-20260826/package-0079`（“需要核对”，3×schema_invalid）③ `…/qwen38-baseline-worker_02-real-run-20260826/package-0079`（“需要核对”，summary 无有效 result）④ `phase5-slice58m-…/qwen38-remediation-host-real-run-20260826/package-0079`（**唯一有效结果**：“已解析”，cross_phase_shared=10、unresolved=1，2 次尝试 1×schema_invalid+1×parsed） | 四个 run 全部针对**旧身份** `pap-d6a1c7d3d06a1c9d18281cda`（5.8o 身份，11 单元 p806–**p816**）。当前 58q 第 79 包为 `pap-2e662c2807a2441886f59ff0`（8 单元，p814/p815 已转 80）。package_id 与成员集双变 → 全部 4 份输出不得机械复用，包括 58m 的有效结果；最多作为共有单元 p806–p813 的人工临床对照参考（推断，需父级决定是否允许） |
| 67 / 78 / 80 / 111 | **不存在**（五包 review 的 `historical_semantic_results.detected_historical_package_directories` 均为空；全库 `artifacts/**/package-0067\*`、`0078*`、`0080*`、`0111*` 检索仅命中 58q 自身文件） | 无旧语义结果可复用。风险在身份连续性本身：67（p729 原子化）、80（±p814–p827 换血）、111（全量换血，common=0）相对 5.8o 的包身份均已改变——任何将来以 5.8o 身份生成的语义结果同样不得回填；78 是唯一与 5.8o 身份完全一致的包，但其历史目录同样不存在 |

### 跨包未决边界（父级复核项）

1. **计数差异已被 58q 自身标记为需父级复核**（`diff-qc.json: count_delta_requires_parent_review=true`）：58q（1846 单元/138 包/1303 未决目标）相对 5.8o 基线（1840/137/1298）+6 单元/+5 目标/+1 包；相对被拒 58p（1857/138/1299）−11 单元/−1 目标/包数不变。差异归因于强边界原子化与包重排，不能仅凭数量认定正确。
2. 四个混合父段落分区 QC 全部 pass（p729→2、p801→1、p815→3、p1237→4，共 10 结果单元，9 个未决目标 + 1 个孤儿直接单元），`all_unresolved_targets_owned_exactly_once`、`all_source_replays_exact`、`all_resulting_units_partitioned_exactly_once` 均 true；`arithmetic_reconciliation_status=accepted_by_deterministic_explanation`，`clinical_acceptance_status=needs_parent_review`。
3. `package-narrative-consistency.json`：五包机器关系与叙述一致性 `all_packages_consistent=true`（fail-closed 通过）。
4. 每包 agent-input 与当前冻结计划一致（各 review `input_frozen_package_matches_current_plan=true`、`frozen_source_span_ids_match_current_package=true`），context 包只读（`context_is_read_only=true`；67/111 为 5 个 context 包，78/79/80 为 6 个）。

## Commands And Observations

- `jq` 提取五包 agent-input（frozen_package 身份/owned/context 计数）、五包 review（`current_vs_accepted_5_8o`/`current_vs_rejected_5_8p`/`historical_semantic_results`/`frozen_input_checks`）、reconciliation（父段落全文与分区）、coverage_manifest（p729/p801/p815/p816–p818/p1236/p1237 等关键单元原文，混合单元全文已逐字回放核对）、frozen_plan（138 包；邻位 81=p819–p827 疗效评价、112=p1238–p1247 数据采集与管理）、diff-qc、narrative-consistency。
- `glob artifacts/**/package-00{67,78,80,111}*`：仅 58q 自身 8 个文件命中 → 确认 67/78/80/111 无历史语义目录。
- 58l/58m run summary 的 0079 条目：三次 58l 均“需要核对”（transport_failed×2 / schema_invalid×3 / 无有效 result），58m 唯一“已解析”（cross_phase_shared=10、unresolved=1）；58l 与 58m 的 package-0079-agent-input 身份均为旧 `pap-d6a1c7d3d06a1c9d18281cda`（11 单元含 p814–p816）。
- 观察：所有只读操作，源 docx sha256 未动；未产生任何新文件（本报告由 runner 持久化）。

## Blockers Or Missing Environment

无阻塞。环境齐备（jq、文件可读）。注意事项：上下文 Source Of Truth 段为 TODO，本审计按 58q 工件为准；若父级认定另有权威源，需重跑身份核对（推断风险，低）。

## Rerun Requests Or Next Step

建议父级（Codex）下一步：
1. 裁决孤儿单元 `body.p1237#atom-100-160` 的处理口径（结构性 II 期直录，显式记录去向），确认限包执行入口不会静默丢弃或让 111/112 借包认领。
2. 对 `count_delta_requires_parent_review=true` 的计数差异做最终父级复核（+6/+5/+1 vs 5.8o）。
3. 决定是否允许将 58m 第 79 包旧有效结果（cross_phase_shared=10/unresolved=1，旧身份 11 单元）作为**人工对照参考**（不机械复用），用于新执行结果的事后临床交叉核对。
4. 放行 worker_01/03 的限包执行入口后，按 67→78→79→80→111 串行真实模型执行；结果必须落在新的隔离结果目录，禁止与 58l/58m 历史目录混存；79 包执行前再次校验其结果引用未触碰四个历史目录。

**claims_complete=false**（本审计为结构/来源层只读核对，非语义模型确认或最终临床验收）。
