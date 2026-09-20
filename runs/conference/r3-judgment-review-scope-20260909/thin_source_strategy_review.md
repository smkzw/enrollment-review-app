I'll verify the slim written-judgment projection and the new normalizer strategy freeze against current source and focused tests, without treating the removed DTO design as still in play.# Conference Output: r3-judgment-review-scope-20260909 - evidence_single_object

## Output

同会话只读复核。未写文件、未跑模型、未读库/病例/其它产物。不把空手数当缺席，不把 effort/prompt/endpoint 当独立模型，不把政策阻断与入组阻断混为一谈。

---

### 书面判断（现投影）

薄函数成立，且与已采信视觉来源对齐。

**已证实**

- `app/projections/written_judgment_evidence.py` 只从 `PageVisualEvidenceSourceSet` 取 **CS_NCS_JUDGMENT**、两侧 `context.target_text` 规范化后相等、再映射 `project_visual_locators` 的精确 `locator_id`。空对象、同页其它对象、NOTE/OTHER、单侧手写都不返回定位（`tests/v2/projections/test_written_judgment_evidence.py`）。
- `_observations`（`evidence_expectation_projection_service.py:132-151`）文件类别仍不能写成 `investigator_assessment`；仅当定位带 `page_review_visual`、事实有 `supported_requirement_ids`、且该 `locator_id` 落在上述集合时才加入。重建走 `rebuild_visual_sources`。
- 默认缺口是 `fallback_only=True` 的 `observation_unverified` / `record_incomplete`（`fact_normalization_executor.py:240-254`），文案已改为「尚未核实是否包含本条要求的记录」。完整判断事实只撤默认未核实，显式未核实仍为弱覆盖（`test_verified_judgment_removes_only_default_unverified_notice`）。
- **没有**缺席生产者。空手数/无已采信批注不会变成 `professional_judgment`。

**阻断接入/发布覆盖的问题**

1. **任意事实只要引用了匹配的 CS/NCS 定位，就会带上 `investigator_assessment` 来源类型。**  
   `_observations` 不看 `fact_type`。`_matching_observations` 仍只看 `supported_requirement_ids`。检验值事实若 `asserted_object` 为「白细胞」且 `locator_ids` 含该 CS/NCS 视觉定位，判断类模板会被当成 **complete**（`evidence_expectations.py:145-146, 286-297`）。  
   现有 `test_lab_result_does_not_replace_required_written_judgment` 用手写 `source_types=["检验报告"]`，**打不到**这条生产路径。  
   **最小修复：** 仅当 `fact.fact_type == "investigator_assessment"`（或与模板 `fact_type` 一致）时才 `source_types.add("investigator_assessment")`。不要新框架。

2. **定位用整对象 `in`，不是 `locator_id`。**  
   `locator not in project_visual_locators(group)`（`:148`）。测试里 `locator` 就是投影对象；生产是 `EvidenceLocatorRepository.get()`，相等性含 `created_at` 等。`persist_visual_locators` 在创建时做过 `get() != locator`，正式作业若重建完全一致则可通过，但投影失败会在 finalize 炸掉整次发布。  
   **最小修复：** 用 `locator.locator_id` 与 provenance 的 `source_set_id/coverage_id` 比对。

3. **`rebuild_visual_sources` 的 `FactPlanningSourceError` 未译成期望错误。**  
   finalize（`executor.py:1391-1436`）只抓 `EvidenceExpectationProjectionError` 等。带视觉定位且有 `supported_requirement_ids` 的已发布事实会走重建；规划错误会漏出 try，作业失败形态不可控。  
   **最小修复：** `_observations` 内把 `FactPlanningSourceError` 包成 `EvidenceExpectationProjectionError`。

**残余（不是缺陷）**

- 无缺席生产者：不能声称「双读未见判断」。只能声称「有对象绑定的已采信 CS/NCS 才能当判断来源」。
- 印刷体病历分析/NOTE 明确不当 complete。
- 不能声称临床验收。

薄投影本身合理，不要再加平行 DTO。

---

### 受控正式整理策略

默认关、新作业新身份、旧作业不改写：**成立**。

**已证实**

- `verified_scope_prompt: bool = False`（command/job service）。`create_app` 不打开该旗标（`app.py:248-254`）。HTTP body 也设不了；隔离脚本改 `command_service.verified_scope_prompt` 再 POST `json={}`（`run_isolated_page_revision.py:123, 49-55`）。
- 策略写入 `effective_scope` 与幂等键、job payload（`job_service.py:451-455, 489-490, 572-573`）。无旗标的旧 payload 不含该字段（`test_strategy_freezes_new_identity_without_mutating_old_job`）。
- 执行器在 **checkpoint 回放之前** 比对现行 `verified_evidence_strategy()` + pending/visual policy（`executor.py:1028-1035` vs `1041-1068`）。改策略则 `NORMALIZATION_POLICY_INVALID`，不调模型。
- `strategy is not None` 时 runner 才带 `pending_details_retained` / `compact_references` / `verified_scope_prompt`（`:1191-1192`）。无已核实观察的页组走 `pending_only_output`，不调模型（`page_review_pending_normalization.py:15-26`）。
- 策略哈希是 system+repair 正文（`verified_evidence_prompt.py:6-12`），不是只冻版本号。

**跑正式新作业前要修的缺口**

1. **失败路径：finalize 重建视觉来源。** 同上 `FactPlanningSourceError`。受控作业会 `include_visual_sources` 并 persist 定位；若模型产出带视觉定位+条款绑定的事实，finalize 必重建。漏译会导致「提示已冻、发布阶段非策略错误失败」。先包错误再开跑。

2. **配方未完全冻结。** `prompt_sha256` 不含：`prompt_template` 短句（登记 `prompt_version_id` 另管）、`pending_details_retained` 追加段（`evidence_normalizer.py:913-918`）、compact 短引用说明（`:897-901`）、视觉边界段。改这些仍会通过策略比对并跑出不同提示。  
   **最小修复：** 把实际 overlay 字符串（verified system、repair、pending 追加段、compact 说明）一并打进 `prompt_sha256`。不要新策略框架。`prompt_version_id` 继续管登记模板。

3. **检查点不含策略。** 回放靠 payload，执行入口已比 payload 与现行函数，足够。不要扩 checkpoint。

4. **隔离脚本在 201 之后才核对策略**（`run_isolated_page_revision.py:49-55`）。旗标未生效会先建出**非** verified 新作业再 `RuntimeError`。副本里会留一个不该跑的作业。  
   **最小修复：** 提交后若 `verified_scope_prompt` 且 payload 无策略，**不要** `run_job`（现已 raise）。跑前人工看 receipt；或提交前 assert `command_service.verified_scope_prompt is True`。

**非阻断**

- 旧作业缺策略字段则不走专用 runner，行为保持。
- `transport_fn` 测试路径不传 verified 旗标；正式路径走 `model_runner.run`。
- 测试未覆盖隔离脚本/HTTP；脚本路径靠读码，不是合成测试证明。

---

### 按严重度

| 级 | 位置 | 问题 | 最小动作 |
|---|---|---|---|
| **P0** | `_observations` + finalize `1391-1436` | `FactPlanningSourceError` 未映射 | 包成 `EvidenceExpectationProjectionError` |
| **P1** | `_observations:150-151` + `_coverage_verdict` | 检验事实引用 CS/NCS 定位即可 complete 判断要求 | 仅 `fact_type` 为判断类才加 `investigator_assessment` |
| **P1** | `_observations:148` | 整份 locator 对象相等 | 比 `locator_id`（及 coverage/source_set） |
| **P1** | `verified_evidence_strategy()` | overlay 段未进哈希 | 把实际 overlay 正文打进 `prompt_sha256` |
| **P2** | 隔离脚本 49-55 | 先建作业再发现未冻策略 | 跑前确认 payload；已 raise 则不要 start |

---

### 仍不能声称

- 未核实 ≠ 确无研究者判断（缺席链未做，这是刻意的）。
- 判断覆盖在生产投影中已正确（缺 `fact_type` 门）。
- 正式受控作业的提示配方已闭包（overlay 未全部进哈希）。
- 临床/全例验收。

**可声称（读码+合成测试）：** 平行 DTO 已不在 `app/domain`；肯定判断只从已采信、对象绑定的 CS/NCS 视觉定位来；默认未核实可被完整判断证据撤掉，显式未核实不行；verified 策略默认关、新键、旧作业不改写；执行前比对失败则不调模型。

跑受控新作业前至少做 P0 错误映射；P1 的 `fact_type` 门若打算发布判断覆盖也要做。不要扩框架。
