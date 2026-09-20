# 会议输出：r05-observation-scope-design-20260915 - evidence_single_object

## Output

第三轮同会话续审完成。只读；未改文件、未运行测试/模型/库/浏览器、未派发。八个核心文件全部重读，API/前端/导出/历史链已追踪。总结论：S4 修复（独立 `unverified_evidence` 字段 + 仓库按原 fact/locator/identity 验证）核对通过；S1（extent/population）合同、提示、护栏总体正确，single 无回归，未发现掩盖通道；但聚合分支有 **2 个决定性缺陷**（F1 错误的"矛盾"标签、F2 同 fact 混合 extent 时前向见证静默丢失），各有 ≤5 行最小修订。以下均为源码级结论，仅编译/静态推演，未运行验证，不构成临床验收。

### A. 核对通过项（证据）

1. **合同 v4**（`app/domain/contracts/proposition_evidence.py`）：`assertion_extent`/`scope_population`/`population_quote` 校验链完整——population 非 unresolved 须逐字引用（`:45-46`）；非 universal 不得声明 population（`:47-50`）；universal 须 scope supported 且 relation 确定（`:51-54`）；`agreement_key` 含 extent 与 population（`:70-73`），双路任一维度分歧即整体 `disagreement`、不得进入消费。
2. **提示 v4**（`app/llm/proposition_evidence.py:72-83`）：量词定义严格（universal+entails=范围内每项 P 成立、+contradicts=每项 P 均不成立，`:76-77`）；"提到整个范围≠对整个范围作断言"（`:73`）、"目前/本次/某标本"收缩不得 universal（`:75`）、命题自带不可分辖域填 unresolved（`:78`）——覆盖我上轮 B2 的否定辖域漂移风险；population 不从"全部"推断（`:80`）；自述按既有来源资格而非一刀切（`:81`）；载荷校验 population_quote 逐字属该配对摘录（`:112-113`）、universal 仅 any/all 政策（`:114-118`）。
3. **候选完备性**（`app/services/qualified_binding_selection.py:483-487`）：`source_content_pairs` 取该 identity **全部**内容候选配对（含被拒与因属性/断言来源未入读的对），与已核实关系 pair 集合比较——`scope_candidates_complete` 语义确为候选核对完备性；`_universal_statement`（`app/projections/control_calculation_experiment.py:124-134`）要求双路 scope supported + 全记录该标志 True + 双路 universal +（all 模式）nonempty 与逐字 population_quote。
4. **反方向护栏**（`control_calculation_experiment.py:285-295,75-78`）：需非确定性 any/all、无 selected_conflicts、无该 identity 任何 gap、全部观测非 UNKNOWN、存在合格 universal 陈述，且全部 truth 同向 opposite 才落定；vacuity 由 all 模式 nonempty 挡住；`scope_population="empty"` 不作任何肯定用途。
5. **single 无回归**：读取层已拒绝非 any/all 政策的 universal（`llm/proposition_evidence.py:114-118`），`_conditional_truth` single 路径与 `scope_verified` 原样（`control_calculation_experiment.py:51-61,296-302`）；`_select_facts_for_identity` 逐行比对未变。
6. **同 fact 多 pair 缺口**：gap 校验为 pair 级不重叠（`:218-225`），且已补 `semantic_identities` 限定（`:216-217`，上轮 A3-2 已修）；仓库逐 gap 核 identity/fact/locator/非确定性/原因非空（`app/storage/review_control_repository.py:104-111`）。
7. **不掩盖**：universal 记录同样过 `_proposition_observation` 时间分支，过期/窗外即 UNKNOWN 并阻断 `universal_ready`（`:290`）；冲突组阻断（`:288`）；任何 gap 阻断（`:289`）且 gap 原因并入 unresolved（`:310-322`）。
8. **R1 修复与形状**：`locator_ids` 回到纯 operands（`app/projections/control_review_outcome.py:79-81`），`control_action_publication.py:53` 首定位不再被 gap 污染；`next(...)` 已带默认值与显式错误（`qualified_binding_selection.py:548-551`）；API DTO `locator_id`+`reason_codes`（`app/api/v2/review_history.py:226-228,512-514`）与前端 decoder `exactKeys(["locator_id","reason_codes"])`、空原因报错（`frontend/src/api/review-history/reviewHistoryHttp.ts:832-839`）一致；报告/导出分开渲染（`FrozenReviewReport.tsx:145`、`frozenReviewExport.ts:49`、`review_history_service.py:572`）。
9. **旧 payload 哈希**：`ControlObligationOutcome` 空字段不序列化、v1 禁补新疑问（`app/domain/contracts/control_review_outcome.py:36-41,67-71`），旧快照重序列化字节不变；旧 v3 命题任务在 `prompt_version` 闸门即被拒（`proposition_evidence_receipts.py` 版本检查 + `PROPOSITION_EVIDENCE_VERSION` 已升 v4），不会进入新合同校验；experiment v9 的 `PropositionPairGap` 移至合同模块后字段名不变，选择载荷哈希不受影响。

### B. 决定性发现（最小修订）

**F1（量词分支·错误标签）`control_calculation_experiment.py:75-79`**：当**全部**观测均为 universal 且方向为决胜方向（any+universal-entails、或 all+universal-contradicts，且无 individual 见证）时，`set(truths) == {opposite}` 不成立而落入 `:79`，被标为 `proposition_relation_conflict`。此时不存在任何方向矛盾——真实语义是"全称不作前向见证"（所有者明定规则），truth=UNKNOWN 正确，但该错误原因码会经 `unresolved_atoms` 进入 `observation_reason_codes` 与报告（`control_review_outcome.py:82-83`），向读者虚构"原文互相矛盾"。最小修订：

```python
if universal_ready:
    opposite = TruthValue.FALSE if policy.mode == "any" else TruthValue.TRUE
    if set(truths) == {opposite}:
        return opposite, []
    if opposite in truths:                      # 仅混合方向才是真矛盾
        return TruthValue.UNKNOWN, ["proposition_relation_conflict"]
    return TruthValue.UNKNOWN, ["universal_statement_not_forward_witness"]  # 新码，或复用 observation_scope_completeness_unverified
```

**F2（同 fact 混合 extent·前向见证丢失）`control_calculation_experiment.py:279-284,57,64-67`**：`universal_facts` 以 `any(...)` 判定——fact 只要有**一条**记录为 universal 即整体剔除出 `individual_truths`。可达场景：同 fact 两 pair 同向均 agreed（如 individual-entails + universal-entails，`_proposition_observation:106-108` 单一状态通过），该 fact 的 TRUE 不再触发 `:64` 前向决胜，`_universal_statement` 又因记录不全 universal 为 False → 落 `:82`。S4 轮此场景给 ANY-TRUE，本轮静默降为 UNKNOWN——非 single 回归，但属见证丢失，且修复不能简单改为 `all(...)`（那会使"混合 fact 内的 universal 反向陈述"逃过 `:66-67` 的矛盾检测）。最小修订：拆成两个集合——

```python
records_by_fact = {fid: by_observation.get((identity.identity_sha256, fid), [])
                   for fid in {item.fact_id for item in interpreted}}
strict_universal = {fid for fid, recs in records_by_fact.items() if recs and all(
    lane.get("assertion_extent") == "universal_over_declared_scope"
    for record in recs for lane in record.get("lanes", {}).values())}
any_universal = {fid for fid, recs in records_by_fact.items() if any(
    lane.get("assertion_extent") == "universal_over_declared_scope"
    for record in recs for lane in record.get("lanes", {}).values())}
```

`individual_truths` 按 `strict_universal` 剔除（恢复同向混合 fact 的前向决胜），`:66` 的 `opposite in universal_truths` 改查 `any_universal` 方向的观测（保留混合 fact 内相反 universal 的矛盾检测）。`universal_ready`/`_universal_statement` 本就只可能对 strict fact 成立，无需改。

两处修订均不动合同、提示与版本号要求（聚合语义属 experiment v9 内修正；因链未启用、无已存 v9 正式记录，无哈希迁移问题——若有已存隔离 v9 工件则须按项目纪律声明修订而非静默改写）。

### C. 建议级

- **B1**：job 级 `observation_scope_verified` 仍硬编码 False（`proposition_evidence_input.py:59`、`proposition_evidence_receipts.py:78`），无消费者；本轮起该名与下游 universal 证明更易混淆，建议下次输入合同变更时改名（如 `identity_pair_coverage_complete`）或删除。
- **B2**：F1 若复用 `observation_scope_completeness_unverified` 而不新增原因码，报告文案需能区分"缺资料"与"有整范围总结但不用作存在见证"。
- **B3**：最终统一评测负例（本轮推演出的可达分支，均为"仅编译、未运行"）：① any 模式唯一记录为 universal+entails → 不得 TRUE 且不得报矛盾（F1）；② 同 fact 混合 extent 同向两 pair → 保持前向决胜（F2 修订后）；③ individual 见证 + 相反 universal → conflict（既有意行为）；④ all 模式 universal+empty population → 不得 TRUE；⑤ 双路 extent 分歧 → disagreement 成 gap 并阻断反方向。
- **B4**：`scope_population="empty"` 于 any 模式反方向不参与判定（`_universal_statement` 对 any 不查 population）——"从无观察推 ANY-FALSE"被保守排除，符合"不从缺失推否定"边界；建议在设计记录明示，防后续误扩。

### D. 量词前后向正确性总表（推演结论）

| 场景 | 结果 | 判定 |
|---|---|---|
| any+individual TRUE / all+individual FALSE | 前向决胜 | 不变，正确 |
| individual 决胜 + 相反 universal | conflict(UNKNOWN) | 有意变更，正确 |
| any 反向：全 FALSE + 双路 universal 否定 + 无 gap/UNKNOWN/冲突 + 候选完备 | FALSE | 新增，护栏齐全 |
| all 反向：全 TRUE + 双路 universal 肯定 + nonempty 引文 + 同上护栏 | TRUE | 新增，vacuity 已挡 |
| 全 universal 且决胜方向 | 现：UNKNOWN+错误矛盾码 | F1：值对、码错 |
| 同 fact 混合 extent 同向 | 现：UNKNOWN | F2：应保持决胜 |

### E. 不确定性声明

以上为静态源码推演，未运行任何验证；F1/F2 的可达性基于对生产者（payload 校验允许 any/all 政策下 universal+entails/contradicts）与聚合路径的推演，实际频次取决于模型输出分布，须由最终统一评测确认。整链未启用、无评测与采信授权；本报告不构成临床、监管、视觉或最终采信结论。
