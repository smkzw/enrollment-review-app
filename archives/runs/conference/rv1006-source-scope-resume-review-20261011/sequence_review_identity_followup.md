收到同包身份取舍补充核对。此前对 v22 的推断按你的更正撤回——本包未改 `SourceTargetReview` schema（v23 未动）。只读、不测试、不委派（Explore/Plan 子代理与"不委派"边界冲突；计划文件不写）。先定位新政策版本常量、写入点与集成点。

定位完成：常量 `:47`，写入目标核对提示 `:1956`，进入组件身份 `execution.py:2104`，新测试 `test_protocol_control_execution.py:715`。读取四处关键实现。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

补充核对（6 次只读已用满）。未改文件、未测试、未读临床/DB/env/tmp、未委派（Explore/Plan 子代理与"不委派"边界冲突；计划文件未写）。**前报告对 v22 的推断按宿主更正撤回**：本包未动 `SourceTargetReview` schema（v23 一直未变），旧产物可读；真正触发全量 refresh 的是被撤回的 v9→v10 聚合策略实验（由 aggregate prompt hash 判为生成材料变化，90 组 refresh_required），该实验无真实新 Job/模型调用。**同 DeepSeek 家族仅程序/上下文分离，非模型金标、非医学批准。**

---

### 本次核实的事实链（源码）

**[代码事实]**
- 常量为审查政策级：`SOURCE_TARGET_SEQUENCE_REVIEW_VERSION = "source-target-sequence-disagreement/v1"`（`protocol_control_source_interpretation.py:47`），**写在真实目标核对提示文本内**（`:1956` `f"先后关系核对政策：{…}。"`，位于 `build_source_target_review_prompt` 返回串中）→ 提示文本变化，新请求不会命中旧文本缓存（文本入散列为 [代码事实]，缓存键实现本轮未读，故为 [推断]）。
- 身份分层正确：`_deep_component_identity` 的 `validator_version` join 在审阅校验层加入该常量（`protocol_control_execution.py:2104`），与 `SOURCE_TARGET_REVIEW_VALIDATION_VERSION`（`:2103`）、`SOURCE_TARGET_REVIEW_GAP_VERSION`、`SOURCE_TARGET_CONTEXT_RECHECK_VERSION`、`SOURCE_TARGET_COCITED_CONTEXT_VERSION`、`TABLE_SEQUENCE_SOURCE_VERSION`（`:2102`）同层；作者提示与编译版本在身份中另有独立字段。
- 新测试给出边界证明（`tests/v2/services/test_protocol_control_execution.py:715-728`）：仅 `validator_version` 不同 → `{差异字段} == {"validator_version"}`、`prompt_material_sha256` 与 `compiler_versions` 不变、且 `_same_deep_components_with_current_gate(previous, current) is True`；`prompt_text_sha256` 变化 → 不兼容（`:726-728`）。其上邻测试（`:705-712`）同向：validator 差异可过"当前门"比较，compiler/source 差异不可。
- 相邻消费证据：部分来源恢复测试（`:731-783`）在 `previous_gate` 与坏/缺输入下仍走 `_validated_deep_partial_source` 的**当前**重验（`partial[2].state == "reused"`、范围修正索引受控、`saved` 字节冻结）。

---

### 1) 复用范围是否越权；是否需要新框架

**结论：不越权；既有"当前 gate 重验"足够，不需要新框架。**
- [推断/代码事实结合] 新常量只动**目标复核政策/校验层**（`:2104` 同层），作者生成材料（prompt_material_sha256）与编译身份保持（测试 `:722-723`）；`_same_deep_components_with_current_gate` 对 validator 差异放行（`:724`、`:706`），意味着**材料可复用但必须过当前门**，而不是把复核政策变更当作作者生成变更去重读/重生成。
- [代码事实] 旧 `additional_requirement`+`after` 由新 typed 门拒绝、真实 `unresolved` 可通过（前包 `:2265-2269` 与测试），已确认的 `not_current_control` 仍须定位原答回显与完整门（前包 `:2404-2438`）。
- [建议] 把"该常量只进 validator 层、不得进入聚合材料哈希"写成注释/契约（撤回实验的教训），防止再次用聚合策略版本误触 90 组 refresh。

### 2) 具体漏验入口与反例

**已核消费入口（均调用当前 `validate_source_target_review`）**：`_validated_deep_partial_source → _resumable_saved_source_review`（本轮测试 `:731-783`）、`_validate_saved_source_review`、`validated_source_review_seed`、`restricted_batch_from_review/_restricted_statement_batch_from_review`（前轮已读其入口先校验）。这些入口会自动带上新 typed 门——**未发现漏验**。
**需 Codex 有界确认的候选点**：任何**只读 `SourceTargetReview.items` 而不先调用 `validate_source_target_review`** 的消费者。本轮 6 次预算内未做全库消费面 grep；反例模板：某路径直接 `review.items` 构造下游（如受限语句/计划决策），则 v9 政策下保存的 `additional_after` 条目可绕过新门。**最小核查**：`grep "source_target_review.items|review.items" app/`，逐一确认前置校验；若有，补一行"先校验后消费"即可，不需框架。
**[反例已成立]** 保存的 v9 政策 `additional_after`：经上述任一入口的当前校验即被拒→该批按既有机制 refresh（非重读来源）；若经未校验入口，则不受门约束——这正是上述 grep 要关掉的尾巴。
**不作事实**：v22 不可读的推断已撤回；本轮无证据表明旧 schema 载荷不可解析。

### 3) 是否应建议全量重读

**不建议**。测试证明作者提示/编译身份未变且"当前门兼容"（`:722-724`）；全量重读会以更高成本换取不超过当前门的保护，属越权成本。既有路径已是"当前完整来源核对/装配门重验 + 不无条件复用"，保持即可。

---

**必修**：无（在已核入口面内）。
**建议**：① 完成 `review.items` 消费面 grep 并逐一确认前置校验（唯一未闭合的漏验候选）；② 注释固化"sequence-review 常量只进 validator 层"；③ 新政策提示文本的缓存失效按命中率观测一次（成本可见性）。
**证据不足**：① 请求缓存的键实现（我只证了政策串在提示文本内）；② `review.items` 全消费面未 grep（预算所限）；③ 90 组再预检与"不称最终方案"按宿主口径接受，未复核，无真实新 Job 证据在本审阅范围。

**给 Codex 的有界问题**：Q1 是否要求我下一轮用 1–2 次 grep 关闭 `review.items` 消费面？Q2 是否确认"当前 gate 重验 + 不重读"为最终姿态（我按此不提出重读建议）？
