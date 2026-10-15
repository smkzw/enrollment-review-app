I'll start with the conference packet and the named source files, then audit frozen-context consumption of investigator written judgments without writing files or running the app.The packet is a stub; I’ll read the assigned source files next and trace how written-judgment results feed frozen gaps and actions.Next I’ll read `_summary_gaps`, the design-doc section, and the action-generation path that consumes frozen search results.I’ll now read `_summary_gaps`, section 17.2, freeze provenance, and the action-generation path.I’ll trace freeze provenance, action policies, and whether unverified flags hide absence results.# Conference Output: r05-judgment-consumption-20260914 - evidence_single_object

## Output

只读审阅。未跑测试、未导入应用、未写库、未改应用文件、未批准语义采用。packet 的 `context/` 与 `plans/` 仍是 TODO 壳；结论来自指定源码及直接依赖。Codex 保留最终接受权。

### 1. 审阅前置（异议与假设）

**用户规则（设计 §17.2 表，`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:332-340`）**

- 双读完成**本次供给范围**且无书面判断候选 → `professional_judgment` + **研究者补充行动**；继续出报告，**不是**再开一轮用户确认。
- 找到摘录 ≠ 已核实书面判断，不得代入结论。
- `source_scope_verified` 恒 False 守卫的是「研究者从未在任何地方写过」，不是「本次供给页未见」。不得把该布尔改成 True。

**我反对的隐含假设**

1. 「冻结上下文里已有 `judgment_search_results`，计算时不必再核页域」——装配时核过，**发布路径没有重放**。
2. 「求值器 `unverified` 与检索缺失可以叠在同一组件上」——会同时发出互相否定的 CRA / 研究者行动。
3. 「期望行上的 `gap_type` 可与最新检索摘要并集」——两者在装配时各自取 latest，**无同代证明**，可把过期 PJ 灌进已有候选的检索。

---

### 2. Evidence（源码事实）

**E1. 检索合同不证明缺失，也不证明范围全集**

- `app/domain/contracts/judgment_search.py:19-21, 387-400`：`found` 不是入排证明；`not_found` 不是判断缺失证明；`source_scope_verified` / `professional_judgment_absence_proven` 类型锁 `False`。
- 覆盖核验只产出候选状态（`app/domain/judgment_search_coverage.py:19-22`），不产 PJ 缺口。

**E2. 供给范围「未见候选」在消费层被做成 PJ**

`_summary_gaps`（`app/services/eligibility_review_projection.py:395-460`）：

| 摘要状态 | 产出缺口 |
|---|---|
| 无摘要 / `COVERAGE_INCOMPLETE` / `CANDIDATES_PRESENT` | `OBSERVATION_UNVERIFIED` |
| `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE` | `PROFESSIONAL_JUDGMENT`（同要求缺文件则跳过；期望已 `OBSERVED` 则退回 OU） |

适用性只看 `required_source_types` 含 `investigator_assessment`（`:388-392, 437-441`），不把 `requires_professional_judgment` 扩散到兄弟要求。与 §17.2:330 一致。

**E3. 冻结计算消费摘要状态，不重放页域**

- 装配：`assemble_review_context`（`review_context_assembly.py:29-30, 58-64`）取 latest 摘要，经 `freeze_judgment_search_result` 用 **当前** `prepare_judgment_search_target` 重建页域并与任务 payload 比对（`review_judgment_provenance.py:90-98, 140-142`）。不完整检索保留，不滤成失败。
- 快照校验只查权威、要求归属、不重复（`review_context_v2.py:279-287`），**不**比对冻结页集合与处理修订页清单。
- `calculate_frozen_review`（`frozen_review_calculation.py:208-238`）只把 `item.summary` 按 `requirement_id` 交给 `_summary_gaps`。**不读** `source_scope_verified`，**不调用** `verify_frozen_judgment_search_result`。
- `verify_frozen_judgment_search_result`（`review_judgment_provenance.py:61-71`）写明 “Publication replays exact references”，全仓 **只有定义、无调用方**。
- `publish_frozen_review`（`frozen_review_publication.py:66-87`）只 `FactAuthorityValidator.validate` + `calculate_frozen_review`，**不重放检索回执**。

**E4. 专业判断谓词的 unverified 旗标绕过原子求值**

- 资格选择对 `requires_professional_judgment` **一律**空选择 + `investigator_judgment_not_deterministic_value`（`qualified_binding_selection.py:177-180`），不论有无可用 pair、不论检索是未见还是已有摘录。
- 冻结计算把 unresolved 身份打进 `unverified_predicate_ids`（`frozen_review_calculation.py:210-229`）。
- `evaluate_component`（`expression.py:608-614`）：旗标命中则直接 `UNKNOWN` / **`observation_unverified`**，不进 `_evaluate_atomic`。
- 若走显式空清单、无旗标，`_evaluate_atomic`（`:487-493`）对 PJ 谓词会发 `professional_judgment_unverified`。旗标把这条区分抹掉。

**E5. 缺口并集与决策**

- `REASON_GAPS`（`assessment.py:206-212`）：`professional_judgment_unverified` → `OBSERVATION_UNVERIFIED`；`professional_judgment_missing` → `PROFESSIONAL_JUDGMENT`（当前求值器已不发 missing）。
- `derive_gate_gap_types`（`:254, 274-275, 286-299`）：`gaps = set(source_gaps)`，再并入 **期望 `gap_type`**，再并入 trigger/exception 的 `REASON_GAPS`。**没有**「检索已给出 PJ 则去掉同谓词 OU」的规则。§17.2:326 禁止因一条 PJ **全局**删除 OU，但当前实现是无差别并集。
- `_decision_for_unknown`（`:314-321`）：集合含 PJ 则组件结论为 `PROFESSIONAL_JUDGMENT`（优先于 INDETERMINATE）。PJ 缺口本身不被旗标吃掉。

**E6. 行动按缺口集合逐项生成，文案互斥**

- `publish_review_actions`（`review_action_publication.py:54-55`）对 `assessment.gap_types` **每一个**缺口建一条 Action。
- `ACTION_CONTENT`（`policies.py:68-72, 108-112`）：
  - OU → CRA：「核对现有原始资料……**核实前不要求补写研究者判断**」
  - PJ → 研究者：「**研究者针对本条要求作出并记录明确的临床判断**」

**E7. 找到摘录不会被本路径采信（未实现，且被挡住）**

- `_summary_gaps` 对 `CANDIDATES_PRESENT` 只给 OU。
- 资格选择拒绝把 PJ 谓词做成确定性事实。
- 冻结 `EvaluationContext` 不设类型别名，且强制显式选择。
- **对照（非冻结主路径）**：实时投影仍用 `_component_candidate_types`（`eligibility_review_projection.py:636-645, 714-715`）把组件全部 `fact_type` 灌给谓词，可走遗留类别匹配。

**E8. 期望缺口与检索摘要无同代约束**

装配同时纳入 `profile._latest_expectations` 与 latest 检索（`review_context_assembly.py:48, 58-64`），二者无交叉校验。`derive_gate_gap_types:274-275` 无条件并入期望 `gap_type`。

**E9. 文案用「任一要求缺摘要」否定 PJ**

`_reason`（`eligibility_review_projection.py:568-582`）：组件 gap 已是 PJ 时，若任一 `investigator_assessment` 要求不在 `summaries`，改口「不能据此认定缺少研究者判断」。

---

### 3. Inference（缺陷 vs 未实现）

**D1（最高影响，已证实消费缺陷）：供给范围确认未见后，OU 与 PJ 并存，发出互斥行动**

反例：组件一条到期 `investigator_assessment` 要求；冻结摘要 `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE`；资格路径将该 PJ 谓词标 unverified。

1. `_summary_gaps` → `{PROFESSIONAL_JUDGMENT}`
2. 求值器 → `observation_unverified` → 并入 `{OBSERVATION_UNVERIFIED}`
3. 决策仍是 `PROFESSIONAL_JUDGMENT`（E5）
4. 发布两条 OPEN 行动：CRA「先别让研究者写判断」+ 研究者「请写出判断」

这直接违反用户规则「不是另一轮用户确认」。旗标**没有**删掉 PJ 缺口，但用 OU 行动把缺失报告**盖成核对循环**。无旗标的显式空选择同样会经 `professional_judgment_unverified`→OU 并集，得到同一双缺口。

这是缺陷，不是缺功能。`_summary_gaps` 已能区分四态；损坏点在并集与按缺口枚举行动。

**D2（已证实）：冻结发布不重放检索页域**

反例：快照已存；同权威下回执/摘要漂移，或发布时未再走 `prepare_judgment_search_target`。`calculate_frozen_review` 仍按存储 `summary.status` 出 PJ。`verify_frozen_judgment_search_result` 已写好却未接线。这是接线缺陷，不是从零的新功能。

不要求把 `source_scope_verified` 改 True。要核的是：冻结 `scope.pages` 仍等于该权威完整修订清单页，且回执能重建同一摘要。

**D3（已证实）：期望 `gap_type` 可伪造或打脸检索态**

反例 A：规范化时期望已是 PJ；之后检索跑出 `CANDIDATES_PRESENT`。冻结 latest 摘要 → `_summary_gaps` 给 OU；期望仍并入 PJ → 决策按 PJ 当缺失。有摘录却报「未见判断」。

反例 B：从未检索或覆盖不完整，但历史期望仍是 PJ。`_summary_gaps` 给 OU，期望并入 PJ → 未完成核对被晋升为缺失。

**D4（次要，已证实）：PJ 文案被兄弟缺摘要带跑**

要求 A 完成未见（PJ），要求 B 无摘要。主缺口因优先级是 PJ（`:71-76`），文案却走「不能认定缺少判断」（`:568-581`）。

**不是本轮缺陷（未实现 / 有意挡住）**

- 已找到摘录的作者/对象/节点语义采用：未实现。资格选择拒绝 PJ 谓词是正确挡板。本轮不得做项目映射、不得把摘录制成已接受事实。
- `source_scope_verified=True` / `professional_judgment_absence_proven=True`：合同有意锁死。
- 要求↔谓词正式归属合同：未实现。本修复不得用 `fact_type` 或条款号猜配对。
- 实时投影类别别名可把 PJ 谓词打成 TRUE：旧路径问题，不在冻结显式选择链上；不要混进本最小修复。

---

### 4. Recommendation（最小完整、保真源码的修复）

三处都要做才完整：缺口集合正确、发布重放页域、期望不再抢检索态。只改行动层会留下错误的 `gap_types` 合同。

**R1. 求值器恢复原因码（`expression.py:608-614`）**

`unverified_predicate_ids` 短路时：若 `atom.predicate.requires_professional_judgment`，发 `professional_judgment_unverified`，不要发 `observation_unverified`。空选择的 `_evaluate_atomic` 已如此。不把 unverified 改成 `professional_judgment_missing`。

**R2. 缺口并集：检索 PJ 不叠加「同一判断谓词」的 OU（`assessment.py:derive_gate_gap_types`）**

在映射 `REASON_GAPS` 时：

- 若 `source_gaps` 已含 `PROFESSIONAL_JUDGMENT`，**不要**再把 `professional_judgment_unverified` 映成 `OBSERVATION_UNVERIFIED`。
- **必须保留**其它谓词的 `observation_unverified` / 冲突 / 日期等。禁止「组件一旦有 PJ 就删掉全部 OU」（§17.2:326）。

R1 让合并后的 `reason_codes` 能区分判断未核实与其它观察未核实，不必发明要求↔谓词表。

**R3. 书面判断要求的缺口所有权归冻结检索（同函数 + `_summary_gaps` 调用方）**

对 `_summary_gaps` **实际处理过**的要求（到期、`investigator_assessment`、且非同要求缺文件跳过）：不要再并入期望上的 PJ/OU。缺文件仍由期望的 `REFERENCED_FILE_MISSING` 加入（`_summary_gaps` 已 skip 这些 id）。

效果：有摘录 → 只有 OU；供给范围确认未见 → 只有 PJ；未检索/不完整 → 只有 OU。过期期望 PJ 不能晋升缺失。

**R4. 发布前重放冻结检索（接线已有函数）**

`publish_frozen_review` 在 `calculate_frozen_review` 之前，对 `context.judgment_search_results` 逐条调用 `verify_frozen_judgment_search_result`。失败则拒绝保存，不改摘要、不改合同布尔。计算层继续只消费已重放的 `summary.status`。

**R5. 行动层不另做策略**

R2+R3 后，纯缺失组件的 `gap_types == {PROFESSIONAL_JUDGMENT}`，现有 `publish_review_actions` 只发研究者行动。不要按组件「有 PJ 就丢掉 OU 行动」——混合实验室未核实仍需要 CRA。

**R6. 文案（可选、同 diff）**

`_reason` 的 PJ 分支按**产生 PJ 的那条要求**是否有完整未见摘要来写，不要用「任一兄弟缺摘要」否定。不作为闭合 D1 的必要条件。

**明确不做**

- 不改 `source_scope_verified` / `absence_proven`
- 不把 `CANDIDATES_PRESENT` 当已核实判断或改 TRUE
- 不按项目/疾病/条款号做映射
- 不把资格选择对 PJ 谓词的拒绝放开
- 不改已发布 `requires_professional_judgment`
- 不在本轮修实时类别别名 TRUE 绕过

---

### 5. Uncertainty

- 未执行测试或运行时，D1 是源码路径闭合推理；`test_judgment_summary_gap_states.py:13-37` 只钉 `_summary_gaps` 单函数，**不覆盖**与求值器并集、也不覆盖双行动。
- 完整修订页集合在同一 `complete_processing_revision_id` 下是否物理不可变：未读仓储闭包实现。R4 在可变与不可变下都只是重放，不扩大证明范围。
- 控制族 `determination_mode == investigator_judgment` 同样被资格选择打成 unresolved（`qualified_binding_selection.py:194-195`），经 `unverified_atom_reasons` 覆盖真值（`control_calculation_experiment.py:168-169`）。未逐条核对控制行动是否同样双缺口；官方条款路径已足够独立成立。
- 现场是否仍有「无检索却带 PJ」的历史期望行：源码允许并集，库内流行率未知。

---

### 6. 给 Codex 的反对、决策点、有界问题

**反对**

- 不能把 D1 说成「未实现四态」。四态在 `_summary_gaps` 已在；损坏的是冻结消费并集与行动枚举。
- 不能用「组件级去掉 OU」修 D1，那违反 §17.2:326。
- 不能靠把 `source_scope_verified` 设 True 来「加强」缺失证明。
- 找到摘录的语义采用必须另做，且仍要隔离评测 + 用户授权；本次只修缺失报告。

**请 Codex 拍板**

1. 主修复落在 `derive_gate_gap_types` 并集（R2+R3），而不是只在 `publish_review_actions` 过滤。推荐接受。
2. 是否把已有的 `verify_frozen_judgment_search_result` 接到 `publish_frozen_review`（R4）。推荐接受。
3. 实时投影类别别名 TRUE 绕过是否另开任务。推荐**不要**并进本 diff。

**有界问题（卡住结论时的安全暂态）**

1. 要求↔谓词正式归属合同是否已批准？若无，R2 只能用「`professional_judgment_unverified` vs 其它 `observation_unverified`」区分，不能按 requirement_id 精确抑制。**暂态：按 R1+R2 做，不发明配对。**
2. 历史期望行上的 PJ 是否视为权威，即使冻结检索已是 `CANDIDATES_PRESENT`？**暂态：检索摘要覆盖书面判断缺口（R3）；期望只保留缺文件等非检索态。**

**安全暂态路径（未拍板前）**：不发布带 PJ+OU 双缺口的正式 run；不把找到的摘录当判断；不声称临床缺失已在全宇宙被证明。
