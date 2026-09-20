我将按只读审阅角色先核对会议上下文与主场计划，再独立核验 R01 r5 失败证据与最小恢复方案。已读入会议上下文与主场计划。接下来只读核验设计条款、恢复计划 T1 和 r5 冻结工件。冻结工件与设计条款已定位。接着读 r5 回执、§17.1.1 绑定规格和 T1 恢复边界。r5 已确认 `failed_final`，失败点在 `read:3:main-B` 的 900 秒超时。接着核对该回执 SHA、超时实现与恢复契约。失败回执已核对：900.03 秒、`APITimeoutError`、无用量。接下来核对超时常量、作业恢复与 SHA 一致性。作业在 `failed_final` 后无法原样续跑。接着核对分批范围、SHA、runner 事务边界和候选语义。接下来用只读命令核回执 SHA、作业步骤状态和分批规模，不触碰临床原件。# Conference Output: r01-r5-recovery-review-20260913 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅，只读顾问）。Codex 保留终裁。本轮未改产品、未调临床模型、未重跑、未把候选当采信。

---

### 1. Evidence（观察）

**作业终态**

- 隔离作业 `027e00ecb0774ab4a8b4ced5927de423`，类型 `predicate_binding_candidates`，合同 `predicate-binding-candidate-job/v6`，提示 `predicate-binding-candidates/v4` + 分批 `predicate-binding-candidates-batch/v2`，目的 `isolated_unverified_candidates`。
- SQLite 行：`state=failed_final`，`error_code=PREDICATE_READ_INCOMPLETE`，`error_classification=fatal`，`progress_completed=12` / `progress_total=13`，`summary` 检查点不存在。
- `result.json`：`accepted=false`，`summary=null`。
- 墙钟：`2026-09-13 07:11:18.738256` → `08:11:24.409069`（约 60 分钟）。范围仅 `component:IN-01:01`、`component:IN-02:02`；冻结输入 `075a8198debacde546e1ade580f722e1c3ce2cbf8ff1d553e9958ee3b0c2b45c`，516 事实 / 342 定位 / 6 批。

**失败回执 SHA（已按内容重算）**

- 步骤 `read:3:main-B` 检查点 `a7f170d5748140cb951a0284cb2b737e`：`status=incomplete`，`accepted=false`，失败文案「对应任务调用失败，不能当作无对应事实」，`candidate_sha256=null`。
- 回执文件 `72053029ba5ef114ad82819861ea8e235655bc00bfa2f96ac2bceace53a3bc0c`：字节 SHA 与文件名一致；266 字节；键为 `attempt/elapsed_seconds/error_type/job_id/request_sha256/status_code/step_id`。
- `elapsed_seconds=900.0316637079814`，`error_type=APITimeoutError`，`status_code=null`，无 `response_sha256`，无 `usage`。
- 请求文件 `3c37abe4952ad14de39413fa338477fa915d73413d80c7a0598e6a6b9112c518`：字节 SHA 一致；90355 字节；`model=mtplx-flash-next-optimized-speed`，`reasoning_effort=xhigh`，`max_tokens=65536`，`extra_body.generation_mode=ar`，`response_format=json_schema`。
- 同批 `read:3:main-A` 与失败 B 请求的 `frozen_input_sha256` 与 `batch_sha256`（`59ba9c1a474276aebc2438bb784a3fa6caa5fe8991a339bc5d71f523c0f51192`）相同；A 无 schema/AR。

**900 秒超时与用量**

- `app/config.py`：`PAGE_REVIEW_TIMEOUT_SECONDS` 默认 `"900"`。
- `app/llm/page_review_harness.py`：`httpx.Timeout(PAGE_REVIEW_TIMEOUT_SECONDS, connect=15)`，`max_retries=0`，`chat.completions.create` / `with_raw_response.create`，无 `stream=True`。
- 11 次成功调用均有 `finish_reason=stop` 与 usage；失败 1 次 usage 为 null。不得把失败步用量记为 0。
- 11 次合计：prompt 346062、completion 132127、reasoning 120238。
- 同路 B 成功耗时：604.9 / 384.8 / 775.1 / 354.3 / 209.7 秒。B2 已到 775 秒仍返回；B3 在 900.03 秒被客户端切断。

**步骤状态与「12/13」**

- 12 个 `read:*` 的 `job_steps.state` 全是 `completed`，`attempt=1`，`max_attempts=1`，`retryable=0`。
- 仅 `summary` 为 `failed_final` / `PREDICATE_READ_INCOMPLETE`。
- 事件 17：`read:3:main-B` 记为 `step_completed`（07:59:47），不是 `step_failed`。之后 B4/B5 仍执行并留下可核验回执。
- `JobStore.retry_failed` 只把 `failed_final`/`failed_retryable` 步骤改回 `queued`。按当前行，可重试范围只有 `summary`。
- `enqueue_predicate_candidates` 幂等键为合同哈希；同 payload 会回到同一 `job_id`，不能当新作业。

**长事务**

- Runner 注释与实现：执行器在写事务外跑；900 秒等待靠租约心跳（默认 TTL 30 秒），不是 SQLite 写锁。
- 各读步检查点写入与完成事件间隔为毫秒级；summary 启动到失败约 15 秒，发生在 `StepFailure` 路径，未留下 summary 检查点。
- 隔离库 WAL 文件 0 字节。本轮只对 `127.0.0.1:8002` 做了 `connect_ex`，返回 61（拒绝连接）；未发 completion。

**来源语义（候选 ≠ 绑定）**

- 设计 §17.1.1：`supported_requirement_ids`、`FactRuleLink`、`PredicateObservation` 都不能改名为已验证绑定。
- 代码：`candidate_value_shape` 一律 `accepted: false`；时间属性对数值比较谓词标 `time_operand_needs_derivation`（「时间范围不是时长」）。
- 11 份候选包均 `accepted: false`。结果状态 18 `candidates` / 15 `unresolved`。操作数形态：24 `numeric_value`、9 `time_operand_needs_derivation`、2 `non_numeric_value`。`pending_checks` 均含 `semantic_correspondence_unverified` 与 `temporal_applicability_unverified`；部分另有 `professional_judgment_applicability_unverified` / `source_unverifiable` / `unit_equivalence_unverified`。
- 分批 4B、5A、5B 候选数为 0，但是 `unverified` 完成步，不是超时，也不是「资料未见」。
- `runtime-contract.json` 为旁路文件（当前 `scripts/run_predicate_binding_probe.py` 不写它）：声明思考前导上限已关（`MTPLX_THINK_PRELUDE_MAX_CHARS=0`），并写明与 r4 不是单变量对比。`accepted: false`。

**已读材料**

- 指定：`context/r01-r5-recovery-review-20260913_conference_context.md`、`plans/codex_main_venue_r01-r5-recovery-review-20260913.md`。
- 为核验另读：§17.1.1、T1、r5 的 `job.json`/`result.json`/`read-audit.json`/`runtime-contract.json`、失败回执与请求 blob、`predicate_binding_job.py`、`predicate_binding_input.py`、`predicate_binding_candidates.py`、`predicate_binding_batches.py`、`page_review_harness.py`、`page_review_transport_options.py`、`runner.py`、`jobstore.py` 相关段、`run_predicate_binding_probe.py`、`tests/v2/services/test_predicate_binding_job.py`、隔离库 jobs/steps/checkpoints/events（只读）。未读工作树外临床原件，未读 `PROJECT_CONTEXT` 作为替代源。

---

### 2. Inference（推论，非采信）

1. **直接失败原因是客户端 900 秒非流式等待，不是「无对应事实」。** 回执与 `PredicateCandidateReadError` 文案一致。切断时没有模型用量，不能推断输出耗尽或语义失败。
2. **11 份 stop 回答不是完整双读。** 缺的是同一 `batch_sha256` 上的 B 路。A3 的 8 条候选不能填 B3。B4/B5 的 0 候选也不能反推 B3。
3. **当前恢复入口与失败形态错位，这是本轮最高影响缺陷。** 超时被当成步骤成功 + `incomplete` 检查点；`retry_failed` 只会重跑 `summary`，而 summary 仍会看到同一 incomplete 检查点并再次 `PREDICATE_READ_INCOMPLETE`。`run_job` 对 `failed_final` 不会重入读步。
4. **把超时改成 `StepFailure(retryable=True)` 会破坏已经付费的 B4/B5。** 若当时按失败级联，B4/B5 不会留下回执。r5 的可恢复资产正是：超时回执保留、后续 B 路已完成。
5. **900 秒是峭壁，不是死机孤例。** B2=775s 已接近上限；思考前导上限关闭后 B 路 reasoning 达 5k–20k。原样重放同一请求/同一 runtime，再次撞 900 秒是实质风险，不是「重试就会过」。
6. **长事务不是这次失败的机制。** 代价是墙钟约 60 分钟 + 租约心跳 + 本地 B 路串行；WAL=0。真正的产品风险是：非流式 900 秒内既没有用量，也无法把超时步标成可重放的失败步。
7. **即便 B3 补齐且 summary 变成 `unverified`，仍不得采信。** 形态检查已标明时长谓词选 `date_range` 只是推导操作数；这是 §17.1.1 要留的语义缺口，不是引用格式问题。

---

### 3. Recommendation（顾问建议，待 Codex 裁定）

**最小可测恢复（只补失败步，不改写旧失败）**

1. 冻结身份：继续用 r5 隔离库与作业 `027e00ec…`，不要从源库再 backup 覆盖。校验 `frozen_input_sha256`、`batch_sha256=59ba9c1a…`、合同/提示/路由仍与 payload 一致；重放前重建请求 SHA 必须等于 `3c37abe4…`。
2. 不要调用现有 `retry_failed`，也不要同 payload 再 enqueue。
3. 新增有界恢复：在核验身份后，只把 `read:3:main-B` 从 `completed` 拉回 `queued`，**不删除**检查点 `a7f170d5…` 与回执 `72053029…`。新尝试追加检查点；`get_last_checkpoint` 按 `created_at` 取新记录。然后只跑该步 + `summary`。
4. 成功判据：B3 新回执有 `response_sha256` 与 usage，`status=unverified`，`accepted=false`；旧超时回执仍可读；其余 11 步 SHA 不变；summary 仍 `accepted=false`。失败判据：再次 `APITimeoutError` 则保留为第二次 incomplete 检查点，进入新实验而不是改写 r5。
5. 运行前阻塞：`127.0.0.1:8002` 当前拒绝连接。必须先有与 `runtime-contract.json` 相符且空闲的 MTPLX，才能重放。本角色不启动服务、不改参数。

**测试（无模型）**

- 超时 → 读步 `completed` + incomplete 检查点 → summary `failed_final`。
- `retry_failed` 只重置 summary，不能修复。
- 身份一致时只重放 incomplete 读步，旧回执仍在。
- 冻结哈希或请求 SHA 漂移则拒绝。
- 0 候选完成步 ≠ 超时 ≠ 未见。

**明确不要做**

- 不把 11 份回答或 A3 候选当双读闭合。
- 不把 0 候选批或超时当「未见/符合」。
- 不把 `numeric_value`/`date_range` 候选接入正式审核。
- 不把加超时、开 stream、或恢复 4000 字思考前导伪装成 r5 恢复；那是新探针。
- 不拿 r5 与 r4 比速度（旁路合同已禁止单变量对比）。
- 不把本探针 2 个组件说成全量 R01。

---

### 4. Uncertainty（未核实）

- 未验证超时瞬间模型是否仍在生成；无 usage，无法区分排队、思考或 JSON 约束。
- 未独立核验 `runtime-contract.json` 与当时进程内存一致；它不是探针脚本产出。
- 未打开候选原文做临床对错判断；只统计形态字段。
- 未在恢复原语落地后做重放；8002 当前不可用。
- 未读 r4 原请求；r4 差异以 r5 旁路合同为准。
- `_verify_current` 在恢复时是否仍得到同一冻结哈希，只能在不改隔离库的前提下再测。

---

### 5. 异议、替代方案、决策点、给 Codex 的有界问题

**最重要异议**

「只补失败步骤」若理解为调用现有 `retry_failed`/`run_job`，**不能恢复 r5**。失败步在作业状态机里是成功的；失败的是 summary。若不先改恢复契约，重试只会再花一次冻结输入校验然后再次 `PREDICATE_READ_INCOMPLETE`。

次要异议：即便补上专用重放，**原样 runtime 再次撞 900 秒的先验不低**（B2 已 775 秒，思考前导已关）。把「再等更久」或「打开 stream」塞进同一次 r5 恢复，会把身份冻结和新实验混在一起。

**替代方案**

| 方案 | 作用 | 风险 |
|---|---|---|
| A. 只重放 `read:3:main-B`，旧检查点只追加 | 对齐「只补失败步」且保留 B4/B5 | 需新原语；可能再次超时 |
| B. `retry_failed` 现状 | 无代码 | 必失败，浪费校验 |
| C. 超时改为 `StepFailure` | 以后能重试读步 | 会级联丢掉后续批；改变的是未来作业，修不了本份 r5 |
| D. 整作业重跑 | 实现简单 | 重付约 12 次调用；违背最小恢复 |
| E. 先改 900s/stream/思考前导再重放 | 可能降低再撞线概率 | 新实验，不能叫 r5 恢复 |

建议 Codex 采用 **A**；若 A 再超时，另开 r6 实验，不改写 r5 回执。

**决策点（会改变恢复目标）**

1. r5 恢复是否必须保持 `job_id` 与全部旧 SHA，还是允许新作业引用旧 blob？
2. 重放是否允许任何 runtime 漂移（思考前导、超时、stream）？
3. 本探针是否只覆盖 IN-01/IN-02，全量组件是否另案？

**有界问题（需要 Codex 同会话答复）**

1. 是否授权新增「重放 `completed`+`incomplete` 对应读步、禁止删除旧检查点」的 JobStore/探针入口，而不是扩展 `retry_failed`？这决定最小补丁落点。
2. 若重放前 8002 服务与 `runtime-contract.json` 不完全一致，是硬拒绝还是记差异后仍重放？这决定身份冻结的严格度。
3. 若 A 再次 `APITimeoutError`，r5 是保持 `failed_final` 作为证据，还是允许把超时改成可重试失败（仅未来作业）？本顾问建议前者。

**暂定安全路径（在 Codex 答复前）**

保持 r5 目录与作业只读；不 `retry_failed`；不启动 MTPLX；不采信 37 条候选；不把 11 份回答当双读完成。下一步工程应先写无模型回归覆盖上述错位，再在匹配 runtime 空闲时重放唯一步骤 `read:3:main-B`。

本输出不是临床、监管、视觉或当前 Web 终审。
