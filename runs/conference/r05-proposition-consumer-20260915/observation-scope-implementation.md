# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

同会话第 4 轮只读源码复审（未编辑/导入/运行）。结论：**v2 双读范围链与 v4 工作流冻结整体成立，声明可接纳用例端到端无阻断；发现 1 个违反“先计数后选择”规则的对粒度源码缺陷（D1）**。≤60 行。

### 发现（按严重度）
- **D1（源码缺陷，中）** 单次观察计数检查用事实粒度而非配对粒度：`app/services/qualified_binding_selection.py:476-480` 比较 `eligible`（合格 value/assertion_basis **事实**集，`:477-478`）与关系 `set(fact_ids)`（`:471`）。失败路径：同一事实 F 有两条合格摘录配对 P1（entails_agreed+scope supported）与 P2（relation disagreement/unresolved）→ 两集合都为 {F} → 相等通过 → 实验端经 P1 准入单次 TRUE（`app/projections/control_calculation_experiment.py:216-230`），P2 仅落入 `unresolved_proposition_pairs`，不阻断——违反“选择单事实前计数全部合格 value/assertion 候选”，且 P2 可能恰含声明观察的其余部分。最小修复：改比配对集——`{item.pair_id for item in usable if item.fact_attribute in {"value","assertion_basis"}} != set(pair_ids)`（`pair_ids` 即关系配对清单，`:472`），一行。
- **D2（建议，非缺陷）** `scope_quote` 不在 `agreement_key`（contract `app/domain/contracts/proposition_evidence.py:47-50`），两路可各自引用不同原文片段但同判 supported；可接受——每条 quote 已被代码独立校验 ⊆ 该配对摘录（`app/llm/proposition_evidence.py:93-94`），且提示明令“范围核实不改变 relation”（`:66`），不会产生矛盾标签。

### 已核实正确（证据）
1. 可接纳用例贯通：标记（`binding_qualification_support.py:583-588`）→ 严格通过 → v2 双读（scope 字段 contract`:15-16,30-31`；提示`:61-66`；校验`:93-98`）→ 扩展 agreement_key 判 agreed → 选择（`qualified_proposition_evidence.py:58-73`）→ 单次计数门（selection`:476-480`）→ 实验准入（`_proposition_observation` `:78-83`、`scope_verified` `:223-229`、`_conditional_truth` `:48-56`）：恰一事实、双路 supported+quote、无时间（`:76-77`）、无争议组（`:217,227`）、显式 single 政策 → TRUE/FALSE。
2. UNKNOWN 纪律：多事实→`observation_selection_unverified`（`:48-49`）；scope partial/unresolved→UNKNOWN（`:78-79,:50-53`）；无政策→强制 unresolved+null quote（校验`:95-98`）；空关系→UNKNOWN（`:74-75`）；ANY-TRUE/ALL-FALSE 单向见证与反向 UNKNOWN 不变（`:57-69`）；混合真值不作冲突（遵循 owner 裁决）；批次单配对不得推全域（提示`:65`）。
3. 工作流 v4 冻结五处：入队（`prepared_review_workflow.py:68`）、推进（`:189`）、重试（`:365`）、发布（`prepared_review_publication.py:20`）、子任务挂接（`review_runtime_ownership.py:46-57`）；版本漂移→ScopeViolationError→步骤不可重试失败并取消子任务（`:233-240`），旧法不得静默续跑；旧 v1-v3 契约仅 `_material` 可读（`:27`），推进/发布均显式拒绝。
4. 接线/环/兼容：ownership→workflow 为函数内延迟导入（ownership`:47`），反向顶层（workflow`:15`），各执行器对 ownership 亦延迟——导入与调用期均无环；receipts 钉 v2 拒绝 v1 旧任务（`proposition_evidence_receipts.py:89`）；experiment v7 Literal 与 payload 版本一致（`:26,:243`）；`.observations` 消费方形状未变（`control_review_outcome.py:61`）；`current_review_task_versions` 五执行器各一键（`:41-50`）。

### 未决（运行时/临床，非源码缺陷）
- 审批 gate 数据仍未签（F2 pending）：发布端将 fail-closed 直至重签覆盖 binding v4/proposition v2；语义时间明确未实现（时间门恒 UNKNOWN，`:76-77`，按设计）；无已暂存测试/运行证据，仅有编译通过（owner 声明）。
