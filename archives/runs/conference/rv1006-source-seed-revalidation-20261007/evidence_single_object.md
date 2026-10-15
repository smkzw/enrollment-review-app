我先按会议指定的两份材料读完边界和审阅标准，再只核对冻结提交与当前两文件补丁里的来源复用与身份拒绝。材料把范围定在 `c55a528e` 加上两个文件的当前补丁。我先取这两处差异，再只读受影响的定义和实际调用点。# Conference Output: rv1006-source-seed-revalidation-20261007 - evidence_single_object

## Output

最高影响缺陷：编译器或修复合同已经变化、作者草稿将被丢弃时，`_validated_deep_partial_source` 仍先对 `partial_wire` 跑当前发布门禁。门禁失败会在来源重放之前抛出，已证实的原文清单无法复用。这与“组件变化后只复用来源、作者结果不继承”直接冲突。当前测试没有覆盖这条路径。

### Evidence

- 冻结点是 `c55a528e`。工作区只有两份未提交差异：`app/services/protocol_control_execution.py`、`tests/v2/services/test_protocol_control_execution.py`。本次未改文件、未跑测试、未读临床或凭据。
- 新证明在 `_revalidated_source_seed_proof`（`app/services/protocol_control_execution.py` 2219–2317）。它允许 `compiler_versions` 与 `validator_version` 不同，其余组件必须相同；提示摘要由调用方在 2368–2370 先核对。摘要不符时 2241–2243 抛出 `ValueError`，不是缓存未命中。
- 调用顺序在 2377–2395：组件或修复合同变化后，只要 `partial_wire` 不是 `None`，就先 `ProtocolControlAgentWire.model_validate`，再 `_validate_deep_batch_output`。两步都没有捕获。通过后才可能调用 `_revalidated_source_seed_proof`。
- 证明一旦成立，2402–2409 会把 wire、逐项核对、覆盖账、候选对齐和 `session_id` 清空，并以 `state="absent"` 交给运行器。跨任务消费者 3288–3346 只在 `partial_wire is None` 时恢复来源，不把旧核对或旧候选送回运行器。
- 同一任务的原地续跑不走该证明。3184–3203 要求 `component_identity` 与当前值完全相等，且修复合同一致，否则直接 `StepFailure`。3264 的部分恢复只在新任务、`decision == "resume_partial"` 且当前 `resume_wire is None` 时发生。
- `_same_deep_components_with_current_gate`（1938–1951）只豁免 `validator_version`。因此仅门禁版本变化时，`changed_components` 为假；修复合同又未变时，2410–2417 会连同旧 wire 和旧核对一起返回。
- 生产者在 `app/agents/protocol_control_deconstructor.py` 6951–7100。初次失败先写入 attempt（6986–7014），`error_detail` 含 `code`、`statement_id`、`source_refs`。随后最多两次范围校正（7021）。只有第一次失败携带该明细。第二次校正的触发错误只留在内存变量 `scope_issue`（7074–7076），不写入 attempt。
- 重放只在 `offset == 0` 核对这次明细（2272–2278）。`offset > 0` 时按列表下标取 `attempts[offset + 1]`，不核对 attempt 序号，也不核对第二次错误身份。范围锁（2290–2294）使用的是当前校验错误，不是生产者发出该校正时的错误。
- 生产者与重放使用同一组六个范围码，以及同一套 `parse`、日程锚点规范化和混合范围规范化。`_sha256`（10113–10114）与重放都按 UTF-8 摘要。诊断检查点 3482–3495 会保存 `raw_output_text`；公开 attempt 模型 4212 行对该字段 `exclude=True`，所以重放必须读诊断检查点，不能读公开 `run_result`。
- `apply_source_scope_correction`（330–385）只改目标下标，并用仅含该陈述的孤立清单做校验。兄弟陈述对象不会被这个函数改写。最终还要求 `model_dump` 与保存的 `source_interpretation` 完全相同（2304–2305）。
- 辅助测试 `test_revalidated_source_seed_never_reuses_changed_material_or_author_approval` 与 `test_revalidated_source_seed_replays_only_proven_scope_corrections` 直接调用证明函数。集成测试 `source_witness_compiler` / `source_witness_repair` 使用当前传输仍能通过门禁的 wire。未看到“结构合法但当前发布门禁失败”的 wire，也未看到第二次校正的错误身份、原地 `retry_failed` 与来源任务指纹断言。既有无 wire 路径在 2954 才断言旧指纹不变。

可复现的控制流反例：用现有辅助测试里的 `compiler` 保存体，保留结构合法的 `partial_wire`，让 `_validate_deep_batch_output` 抛出 `ValueError`。`_validated_deep_partial_source` 在 2382–2383 终止，2390 的来源重放不会执行。辅助测试仍会返回证明，因为那条测试不经过这个消费者。生产形态是：检查点的 `compiler_versions` 少一个当前编译器记号，其余组件和提示摘要相同，attempt 1 的原文能通过现行 `validate_source_interpretation`，但旧作者 wire 已过不了现行发布门禁。

### Inference

- 这是消费者顺序缺陷，不是证明函数本身算错。组件变化的主要场景，就是旧作者草稿不再满足现行门禁；当前写法把“将被丢弃的草稿不合格”变成整段续跑硬失败。
- 损坏与不合格被混在同一次未捕获调用里。结构损坏应硬拒。发布门禁失败只说明作者结果不能继承，不应阻止已经能按原文重放的来源。
- 原地续跑与新任务续跑不一致。新任务有机会走来源证明；同一任务在编译器或门禁版本变化后于 3194 硬拒。`合法 API 续跑` 至少有一条入口没有遵守新证明。
- 仅 `validator_version` 变化时，跨任务路径仍可能继承旧候选和旧核对。这与目标句“组件变化不继承旧候选或采用”冲突，但是沿用了旧的 same-gate 豁免。辅助测试把 `validator` 当成可返回来源证明的输入，消费者却根本不会为这种输入调用它。
- 第二次范围校正没有见证过的错误身份。现行校验若在第一次校正后给出另一个允许码，重放仍会套用下一条 `outcome == "parsed"` 的 JSON。最终内容被保存快照和全量校验卡住，所以不会凭空变成另一份清单；不健全处是授权对象，不是最终字节。现行中间码若落在 `STUDY_PHASE_NOT_VISIT_TIME` 或 `SOURCE_TIME_INCOMPLETE`，历史中本来允许改范围的校正会被新锁拒绝，造成不必要的整段放弃。
- 生产者成功前缀与重放的下标假设一致：失败原答、然后最多两条范围校正。其后的全文重读、摘录校正、FLOW 回答或对齐回答不会被当成范围校正接受，因为 `SourceScopeCorrection.version` 是固定字面量。摘录校正和第二次全文读取因此只能整段重跑，这符合本次“只重放范围校正”的边界。
- 从已恢复来源再次失败时，6945–6947 不会把原始来源回答重新记成 attempt 1。若下一次把该续跑任务当作 `deep_source_job_id`，重放会找不到见证而放弃。旧任务上的原始检查点仍在。

### Recommendation

- 在 2380–2383，对确定丢弃的 wire 只保留结构解析。`model_validate` 失败继续硬拒。不要对这份 wire 调用 `_validate_deep_batch_output`。源证明失败时仍返回 `None`，由预检走重新读取，而不是硬拒。
- 3184–3203 的原地续跑改为与跨任务同一规则：组件或修复合同变化时调用同一证明；证明成立才恢复来源并清空作者结果；证明不成立才重新读取。不要在证明之前因编译器列表不完全相同而硬拒。
- 生产者在每次范围校正前把当时的 `code`、`statement_id`、`source_refs` 写入该校正 attempt 的 `error_detail`。重放对每一次校正都核对这三项，并用该见证码而不是事后的现行码执行范围锁。第二次校正没有这份见证时返回 `None`。
- 补三条合成测试：结构合法但发布门禁失败的 wire 仍能复用来源；非 wire 对象仍然硬拒；第二次校正的见证码或陈述编号不符时不复用。原地续跑与新任务使用同一断言。
- 不要为了解这些缺口去改临床表关系或扩大执行框架。

### Uncertainty

- 本次没有执行测试。上下文里的 36 通过不能当作本角色的验收。
- 预检把 `ValueError` 收成 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` 的包装层本次没读到。结构损坏会硬拒，这由 `wire_corrupt` 测试源码可以支持；包装函数本身未核。
- 没有构造一个真实编译器增量，证明现有夹具 wire 一定通不过现行发布门禁。能确定的是调用顺序：门禁一旦抛出，重放不可达。
- 复用计划经过 JSON 工件往返后与重新计算的证明是否字节级相等，本次没有用真实工件核对。证明字典本身是普通 JSON 类型。
- 旧任务检查点在新代码中没有看到被回写。新的集成测试没有断言来源指纹，因此历史保留是结构推断，不是这次观察到的运行结果。

### Objections

- 辅助测试全部通过也不能说明续跑成立。它们绕过了生产者的 attempt 顺序和消费者的 wire 门禁。
- “丢弃前仍要证明旧 wire 有效”并不增加来源安全性。wire 随后被显式丢弃；这次校验唯一的作用是阻断本来允许的来源续跑。
- `validator_version` 不应在没有决定的情况下继续沿用旧豁免。目标把组件变化和候选继承分开，而现行跨任务路径只对编译器列表这么做。
- 第二次校正不能靠“最终快照碰巧相等”代替授权见证。相等只能防止内容被改坏，不能证明这条校正回答的是当前这一项错误。

### Decision points

- 被丢弃 wire 的发布门禁失败，是硬拒，还是只丢弃作者结果并继续来源重放。本角色建议后者；结构损坏仍硬拒。
- 原地 `retry_failed` 是否必须与新任务 `deep_source_job_id` 使用同一来源证明。本角色建议必须。
- 仅 `validator_version` 变化时，是继续在现行门禁下继承旧草稿，还是也改走只复用来源。本角色建议不继承旧候选和旧采用。
- 是否要求生产者补记第二次校正的错误身份后再启用两条校正的重放。本角色建议要求；在补记前，第二条校正应拒绝复用。

### Bounded questions

- 组件变化后的正式续跑入口，是否只包含带 `deep_source_job_id` 的新任务，原地重试被故意排除。这决定 3184–3203 是缺陷还是范围外。
- `validator_version` 是否属于“变化后不得继承旧候选”的组件。这决定 1938–1951 的旧豁免可否保留。
