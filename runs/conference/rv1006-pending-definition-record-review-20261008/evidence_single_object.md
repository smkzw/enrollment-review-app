# Conference Output: rv1006-pending-definition-record-review-20261008 - evidence_single_object

## Output

**角色结论先行：独立核查未发现阻断性缺陷（mandatory correction = 无）。四文件改动与冻结提案一致：未决来源核对后的定义消费者登记严格停留在诊断层，触发点确在门禁之后，采纳面零接触。以下按冻结提案逐条给出证据、按严重度给出发现、并列出对 Codex 的主动质疑与有界问题。**

---

### 一、冻结提案逐项独立核查（证据为实际代码，非测试转述）

**1. 触发范围确为“门禁有效 hydration + 已验证来源 + 类型化 SOURCE_TARGET_REVIEW_UNRESOLVED”——证实。**
- `SOURCE_TARGET_REVIEW_UNRESOLVED` 全仓唯一抛出点是 `_require_resolved_source_target_review`（`app/agents/protocol_control_deconstructor.py:6834-6842`），且仅在 review 中存在 `decision=="unresolved"` 条目时抛出。其三个调用点（9015、9146、9179）全部位于 try（7853 起）内的复核接受段。
- 该 try 之前已完成 hydration（7714、7741）与批门禁 `output_validator(output)`（7743-7751），异常处理器 9188 的注释与代码结构一致：“candidate wire has already passed hydration and the batch gate"。
- 新触发条件（9278-9285）额外要求 `source_interpretation is not None`、`output is not None`、reader 可调用；其他错误码（`REVIEW_SCOPE_INVALID`、`SOURCE_REQUIREMENT_*`、`TEMPORAL_SCOPE_UNRESOLVED`、传输失败）均不触发。我独立确认 `validate_source_target_review`（`protocol_control_source_interpretation.py:1411` 起）只抛逐条类型化码，绝不抛该未决码，因此预门禁的复核修正循环（7918-7929 的嵌套处理）不会误触。
- 无 UnboundLocalError 风险：`output` 在 try 前必然已绑定（7714/7741），`source_interpretation` 在 7736 已被读取，`official_predicate_identities/sources` 为 `run()` 参数且被既有接受路径（9308-9311）同域使用。
- 恰好一次：处理器构造 pending 声明后立即 `return build_result(...)`（9295-9307），与接受路径（每条路径恰好一次声明：9019 或 9308）互斥，同一 run 不可能既 pending 又 accepted。

**2. 提案与尝试存入独立 pending 字段、不进采纳字段、原失败不动——证实。**
- 新字段 `pending_source_definition_consumers` / `pending_source_definition_consumer_attempts`（4253-4258）与采纳字段 `source_definition_consumers`（4246）物理分离。
- `declare_source_definition_consumers`（4270-4361）只向传入的 attempts 列表追加、编号 `len(attempts)+1` 从 1 起，不触碰主 `attempts`。pending 路径传入全新 `pending_definition_attempts`（9277、9290）。
- 主失败回执先追加（9214-9266）后声明，`result.attempts[-1]` 保持 `SOURCE_TARGET_REVIEW_UNRESOLVED`；执行层判定 `source_review_failure` 只读主 attempts（`protocol_control_execution.py:3619-3621`），不受影响。
- `final_output=None`、`status="需要核对"`（9295-9296）；两个 pending 字段仅在该 except 返回处赋值，任何已解析/待跨章核验返回路径都不可能携带 pending（结构核实）。

**3. 接受路径保持既有“恰好一次”登记——证实。** 9019 与 9308 两条互斥接受路径各调用一次既有函数；diff 未改动。新测试同时断言接受 run 的两 pending 字段为空（test_control_definition_consumer_producer.py:569-570）。

**4. 旧序列化无空默认键——证实。** `exclude_if` 是本仓已确立模式（如 `protocol_deconstructor.py:87,251`、`evidence_normalizer.py:2288-2290`；pydantic 2.13.4 支持）。测试断言默认时两键均不在 `model_dump(mode="json")` 输出中。`ProtocolControlAgentAttempt.raw_output_text` 本身 `exclude=True`（4211），公开 result 模型不泄露原答。

**5. 私有失败检查点分开保存原答/哈希/角色；编译身份变更不覆盖历史——证实。**
- `_pending_definition_consumer_checkpoint`（execution:3753-3780）仅在存在 pending 时输出两键；原答/哈希/角色按条目保存于 `pending_source_definition_consumer_attempts`，与主 `attempts`（3702-3715，保持旧形、无 role 键）分开。失败诊断检查点中不存在 `_deep_attempt_raw_outputs`，原答单副本。
- `_deep_attempt_raw_outputs`（3736-3750）仅为 pending 条目添加 `"role": "pending_source_definition_consumer"`；旧条目键集不变。我核实其仅被写入两处成功形检查点（3283、3731）；仓内无任何 app 侧读取 deep 检查点 `attempt_raw_outputs` 的消费者（`scripts/review_frozen_control_author.py:50` 读的是 `run_frozen_control_slice.py:107` 自建的不同形状 record，且其 `len==4`/逐位校验与 deep 检查点无交集）。
- 身份边界：`pending-definition-consumer-diagnostic/v1` 加入 `compiler_versions`（execution:1955）。旧检查点经 `_same_deep_components_with_current_gate` 判为变更 → 仅走 `_revalidated_source_seed_proof` 的源读取重放作证（2245-2376，逐哈希校验、丢弃下游作者产物），历史不被改写；同 job 旧诊断恢复硬失败（3365-3380，retryable=False）、旧 `deep_reuse_plan` 工件失配拒绝（3344-3348）——与本列表中此前每个版本号提升的既有行为一致。
- `_revalidated_source_seed_proof` 只重放 `attempts[0]`（主 attempts，不含 pending），pending 原答不可能被冒充为源解释重放输入。
- preserve 路径的 `ProtocolControlAgentRunResult.model_validate`（3441-3445）先按 `model_fields` 过滤键，`extra="forbid"`（`app/domain/contracts/common.py:12`）不会被新增键击穿；pending 字段属于 model_fields，旧/新检查点双向可解析。

**6. 登记复用同一物理传输预算、无新分配——证实。**
- `start_source_definition_consumers`（transport:1366-1383）走同一 `self._complete`，请求前经 `_reserve_logical_request`→`budget.reserve`（transport:736、852）从运行时已绑定的同一 `LogicalCallBudget` 预留；回执自动带预算快照（1150-1158），与 `.trellis/spec/backend/persistent-jobs.md` “共用物理请求账本；HTTP发送前持久预留，失败不退款”一致。
- 预算耗尽：reserve 抛 `LogicalCallBudgetExhausted`（发送前，无实际请求）→ transport 包装为 `ProtocolControlAgentCallError` → declare 的宽 except（4323）捕获，`protocol_control_call_failure_code`（transport:331-354）沿 `__cause__` 返回 `LOGICAL_BUDGET_EXHAUSTED`，记为一条失败诊断尝试；run 仍返回“需要核对”，不崩溃。声明函数内除两次纯读取守卫外，prompt 构建/reader/解析全部在 try 内（4313-4323），诊断步骤自身异常不可能改变主结果。

**7. pending 成功数据不能影响采纳/全局范围——证实。**
- 发布侧 `protocol_control_catalog_publication.py` 只读采纳字段：195、346 行读 `result.get("source_definition_consumers")` 记录（执行层转换后的冻结 record 形状），pending 键名不同、pending run 不产生成功形 `source_definition_consumers` 记录。
- `restricted_batch_from_review`（`protocol_control_restricted_source.py:307-354`）只检查采纳字段 `result.source_definition_consumers is not None`（347），不读 pending。
- `_run_diagnostics(result.attempts, ...)`（3637）与 `_execute_deep` 的错误码归类均只看主 attempts，失败回执/错误码不变。

---

### 二、按严重度排序的发现（均为 optional follow-up / 记录项，无 mandatory）

**F1（Low-Med，边界不对称，先前已存在、本改动使其可交互）：`definition` 型定义语句可同时携带 pending 诊断并保留 restricted 资格。**
`source_definition_statement_indexes` 匹配 `calculation_input` **或** `definition`（`protocol_control_source_interpretation.py:805-809`），而 `restricted_batch_from_review` 仅阻断 `calculation_input`（`protocol_control_restricted_source.py:348`）。仅含 `definition`（非 `calculation_input`）语句的未决 run 既能触发 pending 声明，又能通过 restricted 资格检查；随后 `_restricted_deep_checkpoint` 会把带 pending 字段的 `run_result` 与 role 标记的 pending 原答写入成功形 stage-deep 检查点（3282-3283）。今日无采纳消费者，但两种诊断域共享一个检查点，未来任何按 attempt 序号（而非 role）索引原答的新消费者都可能把 pending 原答误挂到主 attempt 1——pending 尝试与主尝试序号都从 1 起。**建议**：或对齐 348 行的判定为 `source_definition_statement_indexes`，或在 `_restricted_deep_checkpoint` 注释/合同中明确“restricted 检查点可含 role 标记 pending 条目，消费者必须按 role 过滤”。不阻断本次合入。

**F2（Low，证据完备性）：reader 缺失时 pending 路径完全不记录，与接受路径不对称。**
接受路径 reader 缺失会记一条合成失败尝试（`definition-consumer-unavailable`，4300-4311）；pending 路径的 runner 级守卫（9283-9285）直接跳过，两个待核 run 的私有检查点无法区分“reader 缺失而跳过”与“无定义可声明”。**建议**（可选）：在主最后尝试的 `issues` 或检查点加一个“声明诊断跳过（reader 缺失）”的非调用型标记；**不要**伪造 attempt 条目——现行为（不造调用）方向正确。

**F3（Low，披露打磨）：pending 诊断失败对公开回执不可见。**
声明无效/传输失败/预算耗尽只存于私有检查点与 pending 尝试的 `issues`；公开 `StepFailure` detail（3637）与错误码不变。预算审计无损（pending 调用回执进入 `model_call_receipts`，3657），但 UI 侧审阅者看不出该次失败 run 额外花了一次调用。**建议**（可选）：在主最后尝试 `issues` 追加“已尝试定义消费声明诊断（未采用）：&lt;错误类&gt;”。

**F4（Info，发布操作项）：编译身份提升的可见后果。** 部署时在途任务：(a) 同 job 对旧 deep_failure_diagnostic 的重试将以 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` 终态失败（3365-3380）；(b) 旧 `deep_reuse_plan` 工件失配拒绝（3344-3348）。跨 job preserve_unresolved 仍可经源重放作证（2447-2472、2466）。与既有版本提升一致，建议写入发布说明，不需代码变更。

**F5（Info）：两种序列化形状差异。** 失败检查点中声明失败时 `pending_source_definition_consumers` 显式输出为 `null` 键，而 result 模型序列化在 None 时整键排除。preserve 读取按 model_fields 过滤且容忍 None，无害；仅作形状记录。

**残余风险声明**：(1) pending 与主尝试共用 1 起编号，靠 `role` 键区分——今日无冲突消费者，属未来合同约束；(2) `declare_source_definition_consumers` 内 try 之前的 `source_definition_statement_indexes`（纯列表推导）理论抛错会穿透处理器使 run 崩溃——审阅为纯属性访问，风险可忽略；(3) `_pending_failed` 返回值被弃置（9287），失败状态实际记录在尝试条目中，行为正确但可读性上可加一行注释。

---

### 三、主动质疑（对提案本身，非对实现）

1. **最有分量的不确定性：每个未决批次现在固定多花一次真实模型调用，而结果不变。** 预算账本“失败不退款”，重试同一 step 时 pending 声明已消耗的预留会压缩重试可用额度；在额度恰好够“诊断 vs 重试真实工作”之一时，诊断可能挤掉重试的关键调用。当前实现的自然保护是“预算耗尽→reserve 失败→零成本失败诊断条目”，因此仅在临界余量时产生竞争。这是产品取舍而非缺陷，但与 1006V1“不默认继续扩展”的窗口精神存在张力，见下给 Codex 的问题 Q1。
2. **对“诊断不含语义”的提醒（按任务要求明示）：pending 声明通过既有 parser 校验（含 `SOURCE_DEFINITION_CONSUMER_IDENTITY_UNPROVEN` 身份证明，`protocol_control_source_interpretation.py:1905`）只证明声明格式与锚点可证，不证明消费者语义完整性或医学对应；测试 `_pending_official_identity_substitution_stays_a_failed_diagnostic_only` 正确锁定“冻结父编号+杜撰措辞≠消费者”。我未将 pending 声明的存在当作任何语义结论的证据。**
3. **对测试的边界说明**：合成夹具始终未决（`_PendingDeepTransport` 每次 review 都返回 unresolved），覆盖了类型化路径与各失败形态；未覆盖“先 unresolved→修复→再 unresolved→再 pending”的多轮路径——但因处理器即 return，结构性保证每次 run 至多一次 pending，风险低。

### 四、给 Codex 的有界问题（附安全暂定路径）

- **Q1（预算取舍）**：是否确认“每个未决批次固定 +1 次物理调用换取诊断”为有意决策？若是，建议发布说明标注；若想保守，安全暂定路径是 pending 触发前检查 `budget.snapshot()["requests_used"] < max_requests - 1`（余量不足则跳过，不发送、不记调用），一行守卫即可，且不改变任何采纳语义。
- **Q2（F1 对齐）**：是否将 `restricted_batch_from_review` 的 348 行从 `calculation_input` 扩为 `source_definition_statement_indexes` 同口径？这会收紧 restricted 资格（行为变化），属规范决定而非修复，我未擅自建议默认执行。

### 五、证据边界

- 实读文件：四目标文件（diff + 相关全段）、`app/agents/protocol_control_source_interpretation.py`（800-930、1364-1450、1900-1915 局部）、`app/agents/protocol_control_agent_transport.py`（331-354、736/842-876、1100-1175、1330-1400 局部）、`app/services/protocol_control_execution.py`（1900-1978、2245-2519、3240-3286、3289-3735 局部）、`app/services/protocol_control_restricted_source.py`（300-410 局部）、`app/services/protocol_control_catalog_publication.py`（80-200 局部）、`scripts/review_frozen_control_author.py`（30-180 局部）、`app/domain/contracts/common.py`（1-17）、`.trellis/spec/backend/persistent-jobs.md`（全文）、两个测试文件 diff 全文。
- 未做：未运行测试/模型/网络/写入（只读约束）；未读执行者说明性报告、临床材料、runs/context 历史；`logical_call_budget.py` 未直接打开（预算行为经 transport 调用点与 spec 双重印证，已在证据中标注）。若需我补查 `LogicalCallBudget.snapshot` 的具体一致性语义或某条恢复路径的行级证据，可在本会话定向继续。
