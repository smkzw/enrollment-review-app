I'll re-read the prior report for continuity, then inspect the current gap-composition path independently without touching fixtures.The producer and adapter findings are closed. I’ll inspect how live and formal assessment currently merge expectation, evaluator, and search-summary states.I'll run a small in-memory composition example on the synthetic multi-predicate component, without writing fixtures.I have a concrete union counterexample. I’ll check stale-scope identity and whether verified facts can still be blocked by a leftover summary.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读续审，不改文件。前轮已关闭：`fallback_only=False` 供给域缺失、`RequirementGapState` 替代 `model_construct`、`test_judgment_summary_gap_states.py` 已有聚焦测试。本轮只回答：现场与正式评估如何在**不互相打架的行动**下组合这些状态。未跑全量套件，未宣称临床通过。

### 1. 已核实的当前发现

**组合粒度过粗：组件级 `set[GapType]` 并集。**

`derive_gate_gap_types`（`assessment.py:219-293`）把到期要求的 `expectation.gap_type` 与 `evaluation.trigger.reason_codes`（仅当 trigger=`UNKNOWN`）做并集。现场投影再 `gaps.update(_summary_gaps(...))`（`eligibility_review_projection.py:663-677`）。正式 `publish_assessment`（`assessment.py:501,593-599`）**不**读检索摘要，只读 `ReviewContextSnapshot.expectations`（v1）。

本会话内存复现（合成 `rule_set()`，无事实）：

| 案例 | 组件 | 输入 | `derive` 缺口 | 决策 | 将发出的行动 |
|---|---|---|---|---|---|
| A 同源 | EX-02 单判断谓词 | `RequirementGapState(req-professional, ABSENT, PROFESSIONAL_JUDGMENT)` + 求值器 `professional_judgment_unverified` | `observation_unverified` **且** `professional_judgment` | `professional_judgment` | CRA「核实前不要求补写判断」**+** 研究者「作出并记录明确判断」 |
| B 复合 | EX-01 六谓词一袋要求 | 袋要求 PJ + 无事实 | 同上两缺口 | `professional_judgment` | 同上互斥两条 |
| C 现场再并 | EX-02 | A 的结果 ∪ `_summary_gaps(ALL_SUPPLIED…)` | 仍是这两缺口 | — | `_summary_gaps` 不核对缺文件、不看期望 |
| F 缺文件 | EX-02 | 期望 `REFERENCED_FILE_MISSING` ∪ 摘要 PJ | `observation_unverified` + `professional_judgment` + `referenced_file_missing` | — | CRC 补文件 **+** CRA 先别让写 **+** 研究者去写 |
| G 未检索 | EX-02 | 无摘要 / 期望 OU | 仅 `observation_unverified` | `indeterminate` | 仅 CRA 核实 |
| H 有候选 | EX-02 | `CANDIDATES_PRESENT` | `_summary_gaps` → OU | — | 未核实，不报缺失 |

行动文案来源：`policies.py:67-111`。`publish_action_request` 对 `assessment.gap_types` **每个**类型各发一条（`actions.py:67-68,83-89`）。组件级并集一旦同时含 PJ 与 OU，正式行动必然对打。

**不能组件级丢掉 `OBSERVATION_UNVERIFIED`。** EX-01 求值器 trigger.reason_codes 为 `['professional_judgment_unverified', 'fact_not_observed']`（实验室/用药/例外记录）。`REASON_GAPS`（`assessment.py:205-216`）**不映射** `fact_not_observed`，所以实验室未观察本来就不会变成缺口；若再在有 PJ 时丢掉整个 OU，连判断谓词的未核实也会被抹掉。例外谓词 `exception_confirmed` 同样是 `requires_professional_judgment=True`，且 **没有任何** `EvidenceRequirement.fact_type` 与之相等。

**现合同没有 requirement→predicate 身份。**

- `EvidenceRequirement`（`rules.py:279-289`）：`requirement_id`、`fact_type`、`required_source_types`，**无** `predicate_ids`。
- `AtomicPredicate`（`rules.py:183-194`）：`predicate_id`、`subject`/`attribute`、`requires_professional_judgment`，**无** `requirement_id`。
- 检索摘要按 `requirement_id`（`judgment_search.py:395-396`；仓储 `judgment_search_repository.py:91-128`）。
- 求值器按 `predicate_id`（`expression.py:551-564`；`PredicateObservation` 同键）。

精确 `fact_type` 连接：

- EX-02：`investigator.rule_specific_judgment` ↔ 唯一判断谓词。可归因。
- EX-01：`fact_type="laboratory_and_investigator_risk"`，六个谓词 **零命中**。袋要求含 `laboratory_report`+`investigator_assessment`。检索「未见书面判断」不能代表实验室未观察，也无法区分 trigger 判断与 `exception_confirmed`。

**`_summary_gaps` 仍是第二套状态机，且比生产者更宽、比缺文件检查更松。**

- 生产者 `fact_expectation_gaps.py:245-270`：仅当 `required_source_types` 含 `investigator_assessment`；`ALL_SUPPLIED…` 发 `fallback_only=False` 的 PJ；缺文件信号会先占 `signaled_template_ids` 从而跳过（测试 `test_complete_supplied_search_does_not_override_missing_file` 覆盖此点，本轮未执行该测试）。
- `_summary_gaps`（`388-428`）：`determination_mode==investigator_judgment` **或** source type；**无**缺文件参数；不比较 `scope_sha256` 与当前 `build_judgment_search_scope`。
- 合成 EX-02 的 source types 只有 `screening_record`：生产者 **不会**发 PJ，`_summary_gaps` 因组件 mode **会**发 PJ。这是 §17.2「一处 source_types、一处 mode」的现存分叉，且落在正式 UAT 组件上。

**正式发布进不了 PJ。** `ReviewContextSnapshot.expectations` 仍是 v1 `EvidenceExpectation`（`context.py:16`）。v1 `ABSENT+PROFESSIONAL_JUDGMENT` 仍拒绝。`RequirementGapState`（`assessment.py:42-48`）只是派生输入，未进入快照。因此现场可用 v2/RequirementGapState 画出 PJ，`publish_assessment` 不能合法消费它。这不是放宽 v1 `ABSENT` 的理由。

**已核实判断会被旧缺口钉死。** `derive_component_decision`（`318-333`）：trigger 已 `TRUE` 但 `blocking_gaps` 非空 → 仍走 `_decision_for_unknown`；有 PJ 则决策保持 `professional_judgment`。现场若在事实已命中后仍 `update(_summary_gaps)`，陈旧 `ALL_SUPPLIED…` 会挡住 §17.2 第四态。摘要仓储按 `evidence_processing_revision_id` 隔离（`repository.py:99-105`），但 `_summary_gaps` 不重算当前 scope 哈希。

**适用性（本轮不改布尔）。** 检索选择用 `determine_component_mode`；生产者用 source type；`_summary_gaps` 用或。§17.2 09-13 附注：不得把诊断/评分布尔扩成「都要另写一份研究者声明」。组合层只消费**已执行检索目标**的摘要，不在缺口函数里新推 mode。

未关闭、但不在本组合问题内：四份冻结夹具的 `professional_judgment_missing` 观察 vs 现场 `unverified`；`_reason()` 在 `gap==PROFESSIONAL_JUDGMENT` 且 summaries 缺键时仍输出「不能据此认定缺少」（`eligibility_review_projection.py:588-601`）。

### 2. 最小实现顺序与合同边界

**现在可以做（不改已发布 `requires_professional_judgment`，不放宽 v1 `ABSENT`，不刷新夹具）：**

1. **单一派生入口**（现场与正式共用 `derive_gate_gap_types`）。删除投影里对 `_summary_gaps` 的第二次 `update`。检索态只通过已发布 v2 期望 / `RequirementGapState` 进入门控。生产者已能把 `ALL_SUPPLIED…` 写成 `fallback_only=False` 的 PJ；缺文件优先已在生产者。
2. **按要求组合，不按组件丢 OU。** 对每个到期 `requirement_id`：  
   缺文件 → 只保留 `referenced_file_missing`；  
   已执行检索且 `ALL_SUPPLIED…` 且当前 `scope_sha256` 等于 `build_judgment_search_scope` → 该要求为 PJ；  
   无摘要 / 不完整 / 有候选 → 该要求为 OU；  
   不得把摘要单独当作接受或缺失。
3. **只抑制已归因判断谓词上的 `professional_judgment_unverified`。** 归因证明物用现有持久数据当场装配，不新开作业引擎：

```
Attribution(requirement_id, predicate_ids, search_status, expectation_gap)
predicate_ids = {P.predicate_id |
  f"{P.subject}.{P.attribute}" == R.fact_type}
```

EX-02：一元组，可抑制该谓词的 unverified，保留 PJ。  
EX-01：空集 → **失败闭合**：不抑制任何求值器 reason；袋要求的 PJ 若搜索合格仍作为**该要求**缺口存在，但不得冒充实验室/用药谓词已解决。`fact_not_observed` 本来就不进 `REASON_GAPS`；复合袋的实验室缺口需要**另一条**资料要求，或保持未映射（诚实），而不是组件级丢 OU。

若同一组件有两条判断要求且 `fact_type` 都不能唯一命中谓词：不要抑制。缺的持久字段是 `EvidenceRequirement.predicate_ids`（或谓词上的 `requirement_id`）。这是规则合同扩展，**不是**改临床布尔，须随规则再发布；在此之前失败闭合。

4. **正式快照扩展**：`ReviewContextSnapshot` 增加已验证的 requirement 缺口视图（`RequirementGapState` 或 v2 期望投影），供 `publish_assessment` 使用。`derive_gate_gap_types` 已接受该类型。不把 PJ 写入 v1 `EvidenceExpectation`。
5. **陈旧范围**：消费摘要前用当前权威重算 `judgment_search_scope_sha256`；不等则当 `COVERAGE_INCOMPLETE`/OU，不报 PJ。修订隔离已在仓储，哈希比对是缺的那一步。
6. **已核实判断**：覆盖事实使该要求期望不再为 PJ 后，门控才能给出明确决策。求值器 TRUE 不得与残留 PJ 并存。

**上游语义（现在不要做）：** 用 `determine_component_mode` 扩大 PJ 报告面；按疾病/条款改布尔；把诊断记录当成缺书面声明；为绿测试改 v1 `ABSENT` 或降低 UAT `required_gaps`。

### 3. 应有测试（建议；本轮未跑除内存示例外）

合成、无病种分支。已有 `test_search_states_do_not_collapse_into_absence` / `test_expectation_producer_preserves_completed_search_gap` / `test_complete_supplied_search_does_not_override_missing_file` / `test_v2_gap_projection_does_not_bypass_legacy_contract` 覆盖生产者与适配器，**不**覆盖组合与正式发布。

| 场景 | 断言 |
|---|---|
| 已确认缺失（1:1，EX-02） | 仅 PJ；一条研究者行动；无 CRA「先别写」 |
| 未检索 | 仅 OU；`indeterminate`；不报 PJ |
| 找到未核实 | `CANDIDATES_PRESENT` → 仅 OU |
| 无关未核实 | 复合组件：判断要求 PJ + 实验室谓词仍 `fact_not_observed`；不得因 PJ 丢掉实验室未决；不得发互斥双行动 |
| 缺文件 | 有 `REFERENCED_FILE_MISSING` 时无 PJ（现场与正式同一函数） |
| 随后核实书面判断 | 覆盖事实 + 新期望 revision 后可明确决策；旧 PJ 行不改写；残留摘要不得钉死 |
| 陈旧 scope | `scope_sha256` ≠ 当前供给域 → OU，不报 PJ |
| 正式发布 | `publish_assessment` 经快照中的 requirement 缺口发出 PJ；v1 `ABSENT+PJ` 仍拒绝；行动集与现场一致 |

现有聚焦测试未覆盖 A/B/F 并集与正式快照。不要把「生产者已发 `fallback_only=False`」当成组合已完成。

### 4. 旧夹具阻断 vs v1 接受假设

**不能靠放宽 v1 `ABSENT` 解决，也不应现在刷新 JSON。**

四项失败的直接原因仍是：冻结观察 `professional_judgment_missing` vs 现场 `professional_judgment_unverified`，`validate_assessment_candidate` 逐谓词比 reason（含未进入缺口的 `exception_confirmed`）。这与 v1 是否允许 `ABSENT+PJ` 无关。

拆开：

- **clear/barrier 重发布**：观察字符串别名，且该谓词在 trigger 已确定时不进入 `REASON_GAPS`。可用只读兼容：观察比较把历史 `professional_judgment_missing` 视为与现场 `professional_judgment_unverified` **同一未核实 reason**，不得当成已确认缺失。这不是改 v1 期望接受集。
- **gap_conflict 专业判断候选**：冻结决策/缺口仍是旧的「无事实=缺失」。现场生成器已是 `indeterminate`+OU。在正式 PJ 路径（快照中的 requirement 缺口 + 合成检索覆盖）存在之前刷新，只会让 UAT 丢失 `GapType.PROFESSIONAL_JUDGMENT` 覆盖。
- **UAT 必选 PJ**：保留。v1 期望不必带 PJ；`UatWorkspaceFixture` 已并入 `final_assessments.gap_types`。真正缺的是正式快照能承载 `RequirementGapState`/v2 PJ，好让生成器在**不写** v1 `ABSENT+PJ` 的前提下发出评估级 PJ。

**必要扩展**：`ReviewContextSnapshot`（及生成器写入它的路径）增加 requirement 键缺口状态；不是放宽 v1 `EvidenceExpectation.validate_status`。袋要求安全归因若要超过失败闭合，再在规则再发布时加 `predicate_ids`，仍不改临床布尔。

### 异议 / Codex 决策点

现场继续调用 `_summary_gaps` 会绕过生产者的缺文件互斥和 EX-02 的 source-type 门槛，并在正式路径之外再画一遍 PJ。§17.2 要的是唯一 derive，不是投影特判。

若 Codex 坚持组件级丢 OU：EX-01 会把实验室 `fact_not_observed` 与 `exception_confirmed` 一起埋掉——请明示接受该损失，本角色不建议。

**暂定路径（未授权改代码）**：组合问题视为仍开放；四夹具失败继续阻断；不刷新、不降 UAT、不放宽 v1。

### 本轮证据

只读：前轮报告；`assessment.py`；`expression.py`；`eligibility_review_projection.py`；`fact_expectation_gaps.py`；`judgment_search.py`；`judgment_search_coverage.py`；`rules.py`；`evidence_expectations_v2.py`；`judgment_search_repository.py`；`judgment_search_source.py`；`test_judgment_summary_gap_states.py`；`generate_v2_contracts.py` 规则树；设计 §16–17.2。内存：合成 EX-01/EX-02 归因与案例 A/B/C/F/G/H。未执行 pytest，未写夹具/库。
