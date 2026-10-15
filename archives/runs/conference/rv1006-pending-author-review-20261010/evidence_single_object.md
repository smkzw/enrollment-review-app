Trellis SessionStart 上下文已加载。开始按 conference 角色 `evidence_single_object` 做只读证据审阅，先定位关键字段与函数位置。

已定位核心字段与函数。继续读取关键实现段落。

继续读取 runner 侧恢复/失败检查点逻辑与失败处理器，并确认组件身份辅助函数。

核对组件身份辅助函数与预算初始化，并按任务要求定位两个新测试。

# Conference Output: rv1006-pending-author-review-20261010 - evidence_single_object

## Output

### 0. 通行结论

- **证据（已读证）**：`pending_author_wire` 的保存、隔离、身份绑定与恢复重验框架在当前两个源文件与两个测试中基本自洽；我未发现“未核提案被当作已核采用”或“新 Job 静默整组重写”的可达采用级缺陷。
- **最高影响缺陷（建议修复，非阻断）**：恢复重放期 source 复核循环仍可调用模型并在成功改写 source 后于 deconstructor:8165-8167 **以裸 `ValueError` 终止**，而 runner `_execute_deep` 对 `ProtocolControlAgentRunner.run`（execution:4386）无包裹——该失败不会产生结构化 `StepFailure`/新 diagnostic checkpoint/该轮 receipts 记账。可达性受 `seen_questions` 与预算约束而有限，但一旦发生会跨 Job 重复消耗一次 source 复核调用且诊断缺失。
- **次高影响（验证项）**：pending 提案未与“其据以作者化的 source 内容”做哈希绑定（对照 source_seed_proof 带 `source_sha256`，execution:2721、2875）。完整重放 gate 会对当前 source 重新校核 wire，因此不会被静默采用；风险在归因/取证与伪修复范围，不在采用判定。
- **声明**：本审阅为同 DeepSeek 家族的程序/上下文隔离审查，非独立模型 gold，不构成临床或最终验收。未运行任何测试；工具操作 16 次，达到上限。测试未覆盖项与未读边界见 §6、§7。

---

### 1. 实测证据链（关键行位）

**保存侧（deconstructor）**
- 结果字段定义：`partial_wire` 4386；`pending_author_wire` 4387-4388（注释明确“parsed author proposal is not a gate-valid draft or source-review proof”）。
- `build_result` 互斥规则 7310-7312：仅当 `final_output is None and partial_wire is None` 时才挂载 `pending_author_wire`；成功返回（10398-10417，10415 `partial_wire=wire` + `final_output=output`）时该字段被排除。
- 捕获点 8454：`pending_author_wire = wire.model_copy(deep=True)`，位于有界合并（`_restore_bounded_wire_repair` 8424-8440、pending_source_insert 8441-8449）之后、hydrate（8455）与 `_complete_inline_scope_citations`（8478-8482）之前——即“最后结构化解析/合并的 wire”，与冻结表述一致。
- 失败重发：失败分支经 `build_result` 时若 `partial_wire is None` 会把最后一次解析的 wire 重新落为 pending（例如 10418+ 异常处理器；测试 11929-11931 断言 bad patch 下 `second.pending_author_wire == initial`，幂等而不漂移）。

**恢复侧（deconstructor）**
- 混用禁区 7412-7418：`resume_wire`/`source_target_review`/`coverage`/`alignment`/scope corrections/unit completions 任一存在即 `ValueError("未核作者提案不能与已核草稿或核对证明混用")`；且仅允许 `RV1001-BASELINE`。
- 有源复验 7419 `validate_source_interpretation`；7419-7422 要求 `restore_scoped_session` 必须可调用，否则 `ValueError("...未退回整组读取")`——**无整组回退**（对照 resume_wire 路径 7450-7456 该项为可选）。
- 私有检查点绑定 7423-7427：`context_sha256 = sha256(stable{batch, source, pending_author_wire})`。
- 不恢复审批 7434-7441：追加 receipt `error_detail={"workflow_phase":"pending_author_revalidation","adopted":False}`；`repair_used=True`（7433）。
- 重放由下方常规循环完成：无预先 `output_validator` 调用（对照 resume_wire 7449），解析/hydrate/门禁在 8455/8483-8492；修复范围仅由常规机制授予。
- source 漂移防线 8165-8167：`source_interpretation != resume_source_interpretation` → `ValueError`。
- 预算：`source_repairs` 由携带的问题历史推导（7524；`called is not False` 计数域仅部分读取），`repairs = source_repairs`（8218）；作者侧修复计数 `invalid_fingerprint_counts`/`no_progress` 每次运行重置（8225、10451-10461）。

**恢复侧（execution）**
- `_pending_author_resume` 2724-2737：排除 partial/review/coverage/alignment + 非空 `session_id` + 仅 BASELINE（2727-2731）；wire schema 重验（2732）；**wire 哈希重推导比对**（2733）；返回 `state="absent", reason="unaccepted_author_proposal_requires_revalidation"`，review=None、coverage=() —— **不携带任何下游复核种子**。
- `_validated_deep_partial_source` 身份门：`_require_compatible_deep_source` 2750-2752（`_DEEP_SOURCE_IDENTITY_FIELDS`，见 §7）；`failed_final` 2765-2766；全量 closure 计划与 batch 材料一致 2767-2777（`_same_deep_batch_material` 2138-2148 忽略 `batch_total`）；checkpoint 版本与 batch_id 2782-2786；**route**：`transport_identity` 摘要 vs `frozen_model_routes["deep"]` 2790-2795；**prompt/组件**：不一致即 `return None`（不恢复）2798-2801；repair 合同 64hex 硬校验 2803-2806；`_same_deep_components_with_current_gate` 2121-2135 允许 **validator 版本漂移**（其余字段全等）——与“validator may change”一致；组件实质变化时走 source_seed_proof 路径（2889-2924），pending 仅在 `source_seed_proof is None` 时进入（2934-2936）。
- 运行期 in-job 恢复：仅信任 `stage=="deep_failure_diagnostic"`（4130）；身份四连（prompt sha、transport identity、component identity、repair contract sha）+ 结构校验（4134-4163），任何不符 → 非重试 `StepFailure`，未发模型请求；`_pending_author_resume` 在 4170-4175 被调用；`ValueError → StepFailure`（4176-4178）。
- 新 Job 复用计划：preflight 3437-3441 记录 `expected_prompt_sha256/expected_route_sha256/component_identity`；决策理由 `unaccepted_author_proposal`（3384-3385）；计划工件重校验 4104-4117；来源检查点证明入队前后一致 4208-4215；`resume_partial` 再验 route（4332-4336）与 source（4337-4339）；runner 调用时精确接线 `resume_pending_author_wire`（4395-4398）。
- diagnostic 落盘：4517-4524 同时保存 `partial_wire` 与独立的 `pending_author_wire + pending_author_wire_sha256`；4535-4538 保存 source；4556-4560 保存 alignment/复用记录；4469-4480 非传输类失败 `retryable=False`。
- “通过恢复门 != 采用”：成功仍需 4422-4424 `_validate_saved_source_review` + `restricted_batch_from_review` 与完整门禁；失败错误码与诊断 4469-4508 明确“结果保持未采信”。

**测试（名称匹配；未运行）**
- `test_unaccepted_author_proposal_is_saved_and_revalidated_without_reauthoring`（slice58c:11886-11935）：首跑 `max_schema_repairs=0` 落 pending（11899-11900）；二跑要求 `restore_scoped_session` 被调用且 hash 长度 64（11909-11910）；`start`/`continue_session` 直接 `pytest.fail`（11912-11916）→ 不整组重写、不沿用旧会话盲续；仅 `continue_atom` 有界修复（11918-11920）；好/坏补丁分别收敛为“已解析且 pending 清空”（11932-11934）与“仍失败且 pending 等于原始 wire”（11929-11931）。
- `test_pending_author_resume_requires_scoped_restore_and_cannot_mix_approved_wire`（11937-11946）：缺恢复能力、与已核草稿混用各自 `ValueError`，且空 FakeTransport 证明未发模型调用。
- `test_pending_author_recovery_does_not_confer_approval_or_accept_corruption`（execution:5460-5484）：八类篡改（含 hash、session、flow、partial/review/coverage/alignment）→ `ValueError`；正常路径断言 `state=absent`、review/coverage 空、原因字符串精确匹配，且**保存字典未被原地改写**（5484）。
- `test_unaccepted_author_proposal_round_trips_failure_preflight_and_new_job`（5487-5532）：首 Job `failed_final`（5523）、入队计划理由 `unaccepted_author_proposal`（5528）、新 Job 恰一次携带 `resume_pending_author_wire` 且 `resume_wire is None`、`resume_source_target_review is None`（5516-5518、5531）、新 Job completed（5530），**来源 Job 检查点指纹不变**（5532）。
- 数字自洽：四个测试函数的参数化展开为 2+1+8+1 = 12，与 owner 的“12 focused / 1422 deselected”一致（推断，非运行证据）。

---

### 2. 任务列举的具体失败点逐一裁决

| # | 检查点 | 结论 | 证据 |
|---|---|---|---|
| 1 | 重放前 source 变化 | 已设防；残留 F1/F2 | 7419、8165-8167、4151-4154、4337-4339 |
| 2 | 陈旧下游复核复用 | 不可达（按构造） | 2737 返回空 review；7413-7417 拒绝 seeds；4351-4352 仅 wire 存在时算 alignment；测试 5518 |
| 3 | accepted/pending 混槽 | 四个关键槽位硬拒绝 + 有测；旁路槽位未证 | 2727-2731；11945；5474-5479；F5 |
| 4 | checkpoint 与 wire 哈希 | wire 哈希写读一致（4522-4523 / 2733）；checkpoint 身份四连双层校验（4134-4146 / 2790-2806）；计划证明 4208-4215 + 5532；残留 F4 | 同上 |
| 5 | 失败补丁保留基线 | 有界合并 + 捕获点在合并后；坏补丁不改写 pending | 8424-8454；11929-11931 |
| 6 | 预算重置 | 源额度仅经 source_seed_proof 结转（4380-4385）；**作者修复额度按 Job 重置** | F3 |
| 7 | 合法 pending 过门后仍走完整复核 | 成立：无复核种子 → `latest_source_target_review` 从 None 起（8243-8245），常规 reviewer 路径全新执行；成功仅在 10398-10417 完整门禁后 | 2737、8243-8245、10406-10416 |
| 8 | 过门 ≠ 临床采用 | 成立：`adopted=False` receipt（7436-7441）、非采信错误码与诊断（4469-4508）、采用仅由 4422-4424 判定 | 同上 |

---

### 3. 发现（按影响排序）

**F1 · 中 · 可达硬失败缺结构化诊断（本审阅最高影响缺陷）**
- 反例路径：resumed pending 重放中，`source_interpretation is not None and callable(source_reader)` 使其进入 8049-8102 的 source 复核循环；若存在未被 `seen_questions` 覆盖的合格问题且预算剩余，8074 发起模型调用、8076-8078 成功改写 source，随后 8165-8167 抛裸 `ValueError`。execution:4386 对 `run()` 无 try/except（对比 4247-4251 对同类调用有专用包裹）。
- 后果：无 `StepFailure` 错误码、无新 diagnostic checkpoint（本轮 receipts/预算消耗不落账）；旧 checkpoint 仍在（test 5532），语义上不至采用错误，但跨 Job 可能重复“发一次调用再硬失败”，且运维视角是裸异常。可达性受历史去重与预算约束（先前运行已问过的合格问题在 resumed 运行被跳过），故不是高频路径。
- 最小修复（二选一，均小改）：a) 恢复期（`resume_pending_author_wire is not None`）不调用 source reader；若存在待复核合格问题，改为结构化返回“需要核对”，保留 pending wire 并记录 `source_recheck_required`，交下一 Job 先走普通 source 路径并**显式**丢弃提案（保留放弃记录）；b) 保留现行为但把 8165-8167 的异常前移为 runner 可见的结构化失败（在 `_execute_deep` 包裹 `run()`，或将漂移判定改为进入循环前先检查合格未问问题集）。
- 建议 a：它不改变“source 变了就不恢复提案”的语义，只把“何时 source 会变”的判定从模型调用后提到调用前，符合“不发无谓模型调用”的项目基调。

**F2 · 中 · pending 提案缺 source 内容哈希绑定（验证项）**
- 事实：source_seed_proof 路径均含 `source_sha256`（2721、2875、2871-2888）；pending 路径的 `_pending_author_resume` 仅校验 wire 哈希与 session（2733），source 只经 `validate_source_interpretation` 对当前 batch 校核（7419、2932-2933）——这证明“来源与冻结批次一致”，**不证明“等于提案作者化时的来源”**。checkpoint 的 `source_interpretation` 若被等批次有效的另一个解释替换，pending 仍会以原措辞重放。
- 缓解事实：重放执行完整 hydrate + 当前门禁（8455、8483-8492），错配将以 gate 失败暴露，不会静默采用；影响是归因/取证精度与可能的伪修复范围。
- 最小修复：写入时增加 `pending_author_source_sha256 = sha256(source.model_dump_json())`（4521-4524 同处），读取时在 `_pending_author_resume` 比对（2724-2737），与 wire 哈希对称。若 §7-Q2 证明 `_deep_source_checkpoint_proof`（3155）已覆盖全量内容，则降级为文档项即可。

**F3 · 低 · 作者修复预算跨 Job 不结转（建议说明或收紧）**
- 事实：runner 的 `max_schema_repairs` 取自 payload 限值（4118）；仅当存在 `resume_review.source_seed_proof` 时以 `source_repair_limit` 收紧（4380-4385）。pending 恢复无 seed proof；deconstructor 的 `source_repairs` 只来自问题历史（7524），作者循环 no-progress/指纹计数每次运行重置（8225、10451-10461）。
- 后果：同一确定性失败下，每个新 Job 可再获一次限定修复尝试。不会整组重写、结果幂等（test 11929-11931），但可能多次小额消耗。若视为预期，请在 1006V1 文头或合同注释固化“作者修复额度按 Job 计”的说法；否则可仿 source_seed_proof 增加 `pending_author_repair_limit` 随 checkpoint 结转。

**F4 · 低 · wire 哈希基于模型重序列化而非存储字节**
- 2733 与 4522-4523 用 `model_dump_json()` 重推导。字段集/默认值/`exclude_if` 策略或字段顺序任一变化，都会让旧 checkpoint 硬失败（“实际保存摘要损坏”）→ 丢弃提案、整组重读。方向 fail-closed，可接受；建议在 checkpoint 注释中声明“schema 演进即失效”的策略（当前 schema_version 已固定 v3，284、4513）。

**F5 · 低 · 排除集未涵盖旁路槽位（未完成验证）**
- `_pending_author_resume` 只拒绝 partial_wire / source_target_review / coverage / alignment（2727-2731）。`capability_wire`（4391）、`source_front_target_review`（4360）、`pending_source_definition_consumers`（4374-4379）未在拒绝清单内。FLOW 与 front review 实际由 BASELINE 限制间接排除（2730、8165 语境）；`capability_wire` 的赋值点不在本次读取窗口，二者共存的**可达性未证**。若可达，注意错误码选择依赖 `result.capability_wire is not None`（4484-4485），需确认恢复重放会原样复现同一 capability 路由。

**F6 · 低 · 两处 `_validated_deep_partial_source` 调用未包裹 ValueError**
- 4315-4318（resume_partial）与 3378（preflight）未包裹；对比 4247-4251 的 preserve_unresolved 分支有 `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID` 专用处理。运行期 route/身份若在计划生成后漂移，会以裸 `ValueError` 越过 StepFailure 边界。建议统一包裹并复用 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`。

**边界澄清（非缺陷，需 Codex 拍板）**
- prompt 模板变化：preflight 处 `return None`（2798-2801，不恢复→后续整组读取），runner 运行期则是硬 `StepFailure`（4137-4139）。与“无回退整组读取”的字面张力只出现在 preflight 语义上（该语句按原文仅约束“scoped restore missing”，7420-7422 已严格 raise，测试 11943-11944）。请确认“prompt/组件身份变化 → 整组重读”是预期合同。

---

### 4. 支持性正面结论（防止未来回归时误删）

1. **隔离正确**：pending 与已核草稿/复核种子在任何入口互斥（7412-7418、2727-2731），且 build_result 保证不共储（7311-7312）。
2. **无审批恢复**：恢复 receipt 显式 `adopted=False`（7436-7441）；成功仍须完整门禁与 `_validate_saved_source_review`（4422-4424）。
3. **旧记录不伪造**：无 `pending_author_wire` 字段即 `return None`（2725-2726），不从 attempts 原文倒推提案；与冻结表述一致。
4. **失败补丁不污染基线**：有界合并 + 坏补丁场景 pending 保持原 wire（8424-8454、11929-11931）。
5. **来源 Job 不可变**：新 Job 只读复用并同步完成；来源检查点指纹不变（测试 5532、4517-4560 只写新 Job 的自有检查点）。

---

### 5. 决策点与给 Codex 的有界问题

- **D1**：是否采纳 F1 修复(a)（恢复期禁 source reader、结构化保留提案）？
- **D2**：是否为 pending 增加 `pending_author_source_sha256` 绑定（F2），还是以 Q2 结论文档化即可？
- **D3**：作者修复额度跨 Job 重置（F3）——接受并文档化，还是随检查点结转限值？
- **D4**：prompt/组件身份变化导致整组重读的 preflight 行为（§3 边界澄清）是否为预期？
- **Q1**：`restore_scoped_session`（transport，不在读取集）在会话缺失/上下文不符时的实际行为是 raise 还是静默通过？若是静默，7420-7427 的绑定会退化为象征性，F1 的严重度评估需上调。
- **Q2**：`_deep_source_checkpoint_proof`（execution:3155）是否哈希覆盖检查点全量内容（含 `source_interpretation` 与 `pending_author_wire`）？若是，F2 降级为文档项。
- **Q3**：`capability_wire` 赋值点能否与 `pending_author_wire` 同时落盘？若否，F5 关闭。
- **Q4**：新 Job 首跑时 `context.last_checkpoint` 是否可能直接继承来源 Job 的 diagnostic（决定 4134-4149 身份门在首跑是否立即生效，还是仅由 preflight 路径把守）？

---

### 6. 未读边界（诚实声明）

- transport 实现（`restore_scoped_session`、`take_call_receipts`、会话真伪）不在读取集内，未读。
- `capability_wire` 赋值点、`_deep_source_checkpoint_proof`(3155)、`_validated_deep_source`、`_DEEP_SOURCE_IDENTITY_FIELDS` 常量、准入分支 3280-3328（非恢复决策→整组重读的转换）、`_saved_deep_run_result` 等未读或仅读签名。
- deconstructor 7524 的精确求和域、7600-8048 source 读取循环主体、10680-10950 no-progress 出口与 `capability_wire` 落盘、execution 4560 之后的 attempts 序列化尾部未读。
- 测试仅读 grep 上下文（slice58c 11936 后、execution 5535 后正文被截断）；**未运行任何测试**；未核对 git HEAD/工作树状态（无 Bash 权限）。
- 提示的 775a750 实测失败现场未回放（无 DB/历史访问权限）；其“source 存活、提案丢失→整组重写”与当前字段缺失的因果为我基于代码的推断，非现场证据。

### 7. 不确定性与自限

- 同一家族模型审查（DeepSeek），程序/上下文分离，非独立验证；所有“可达/不可达”均为源码级反例推理，未在真实运行环境复现。
- 严重度分级假设单机单用户、本地 checkpoint 无对抗篡改威胁；若威胁模型含本地数据篡改，F2 应上调为中-高。
- 测试 12/1422 的构成匹配为推断；通过状态与“非临床采用”边界完全归属 owner 与 Codex，本报告不作最终接受声明。

（报告完，等待 Codex 同会话后续定向问题；如要求补读 F5/Q2 两处，预计 2-3 次聚焦读取可闭合。）
