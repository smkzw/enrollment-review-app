已收集所有证据。报告如下。

# 会议参与者输出：r3-durable-reader-review-20260906 - general_single_object

## 边界检查

- 会话路由：`zcode/zcode/GLM-5.3-Flash`，thought `max`，新会话按 Beijing off_peak 准入，未切换模型或 effort。
- 仅读取了指定初读集合 + `app/workflow/`（jobstore.py、recovery.py、states.py、errors.py）+ `app/storage/page_review_repository.py`、`app/storage/models.py` 的定点 grep + 相关合成测试（`tests/v2/workflow/conftest.py`、`tests/v2/services/test_page_review_execution.py` 的 `_routes`/fixture、`app/services/job_service.py` 的 `create_job_in_session`）。未读取 `.env`、临床源文件、artifacts 内容、外部 harness 配置；未运行测试；未修改任何文件；未调用产品模型；未读取其他与会者输出。
- 不作临床结论；不主张最终验收。`app/llm/page_review_harness.py`（`read_page`/`direct_openai_completion`）超出授权读取范围，相关项列为验证需求（见问题 2）。

## 独立工作产出

对四个指定问题逐一给出基于代码的独立结论（行号均为当前 worktree 文件）。

### 问题 1：并行波次是否延迟已成功结果提交 —— 是，确认存在系统性延迟

**证据（观察）：**
- `app/workflow/runner.py:487-516`：波次内所有 future 经 `as_completed` 完成后，结果只写入进程内 `results` dict；真正提交在 `with ThreadPoolExecutor` 块退出（即全部 future 结束）之后，见 `runner.py:522-545`。
- 波次上限为两条主读路由 `max_concurrency` 之和（`app/services/page_review_job_service.py:103`），因此一个慢/挂起的 lane 读取会延迟其余 N-1 个已完成读取的持久化。
- 执行器在模型调用返回后立即写 `raw_response` 制品（`app/services/page_review_job_executor.py:101`），但 `response_attempts` 关联只在 checkpoint 提交时落库 —— 排空窗口内进程被杀，已完成的模型响应成为无链接孤儿制品。
- 取消路径上，成功提交循环中的每个成功后都会做取消检查（`runner.py:546-551`），一旦检出取消即 `return True`，`results` 中尚未提交的其余成功结果被丢弃（语义可接受：`resume_cancelled` 后重读，测试 `test_cancel_at_read_boundary_then_resume_preserves_committed_reads` 覆盖；代价是已花费的模型调用作废）。

**推断：** 真实 `kill`/断电/租约丢失发生在排空窗口时，丢失半径从"单个执行中步骤"扩大为"整个波次已完成的全部结果"。这是问题 2 损失的主要放大器。

**最小完整修复（runner.py 局部）：** 在 `as_completed` 循环内对每个完成的 future 就地提交成功结果（逐个 `_commit_step_success` + 既有取消检查），失败结果仍缓存到排空后按现有 `settle` 逻辑统一提交（保租约、避免孤儿 running 的理由不变）。心跳已覆盖整个排空期；逐个提交各自走 `_renew_if_due` + `acquire_step_commit` 写栅栏，状态机语义不变，只是把持久化点从"波次末尾"前移到"每个结果完成时"。

**测试建议：** 双步骤波次，future A 立即返回、future B 在 `threading.Event` 上阻塞；断言 B 未完成时 A 的 checkpoint 已可在独立会话查到（当前代码该断言失败）；随后释放 B 走完正常路径。

### 问题 2：进程死亡/取消/租约丢失下是否丢成功读道 —— 已提交的不丢；未提交的丢失窗口被波次放大；且存在一条"死亡把任务钉死为 failed_final、受控重读不可达"的路径

**已提交读道存活（证据）：** checkpoint + 领域记录同事务提交（`jobstore.py:647-697`）；取消只动非终态步骤（`jobstore.py:1509-1518`）；恢复把"有 checkpoint 的 running 步骤"视为完成（`jobstore.py:1443-1468`）；重读规划经仓储回读校验后复用（`page_review_recovery.py:59-68`）。测试覆盖取消续跑与重读复用。

**发现 A（高优先）：可重试失败 + 死亡 = 预算耗尽，任务 failed_final，成功 lane 的受控复用通道被关闭。**
- `read:` 步骤 `max_attempts=2`（`page_review_job_service.py:47-48`）。
- 时间线：attempt 1 endpoint 失败 → retryable StepFailure（`page_review_job_executor.py:113-115`），不写 checkpoint；退避后 attempt 2 启动（`start_step`，attempt=2）；期间进程死亡/断电。
- 恢复器 `_reset_interrupted_steps`：无 checkpoint 且 `attempt(2) >= max_attempts(2)` → `failed_final` + `RECOVERY_RESET`（`jobstore.py:1469-1487`），级联下游（reconcile/coverage，`jobstore.py:1520-1557`）→ 任务 `failed_final`。
- `plan_page_reread` 要求 `previous.state == "completed"`（`page_review_recovery.py:23`）→ 已成功 lane 的 receipt 虽持久存在，受控重读不可达；409 文案"请先查看或恢复原任务"指向一条对终态任务不存在的恢复路径。
- 通用 `retry_failed` 不重置 `attempt`（`jobstore.py:1231-1236`）：重试后 attempt=3，再遇任何一次可重试失败即因 `exhausted = attempt >= max_attempts`（`jobstore.py:725,734`）直接终败 —— 人工重试实际只给一次干净机会。

**修复建议（最小且完整）：** `retry_failed` 与 `resume_cancelled` 在把步骤重置为 queued 的同时 `step.attempt = 0`（历史完整保留在 JobEvent 与旧 checkpoint 中，不违反审计要求）。配套：确认 R3 对 failed_final 任务有可达的人工重试入口（见问题 1），并修正 `PAGE_REREAD_NOT_READY` 对终态任务的文案。
**测试建议：** R3 合成用例 —— lane endpoint 失败一次 → requeue → attempt 2 注入 ProcessDeath → `recover_expired_jobs` → 断言 job `failed_final`、error `RECOVERY_RESET`；`retry_failed` 后重跑成功 → 断言 completed 且成功 lane 未重复调用模型。

**发现 B（通用状态机潜在缺陷，R3 不可达但属"恢复身份"范畴）：** 用户等待步骤的 pause/resume checkpoint 会被恢复器误当作执行结果。`pause_running_step_for_user` 与 `resume_waiting_step` 都写 checkpoint（`jobstore.py:1004-1009, 1057-1062`）；resume 后 `start_step` 使 running，此时死亡，`_reset_interrupted_steps` 取 last checkpoint（用户输入的 C2）直接把步骤标记 completed —— 执行器从未在该 attempt 执行。R3 步骤无 `waiting_user_kind`、执行器不抛 `StepAwaitingUser`，故当前不可达。
**最小修复：** `_reset_interrupted_steps` 增加"checkpoint 属于当前 attempt"校验 —— `complete_step` 已写入 `{"attempt": step.attempt}`（`jobstore.py:669`），pause/resume checkpoint 的 attempt 必然小于 resume 后 start_step 递增的当前 attempt，取 `payload.get("attempt") == step.attempt` 作为"可视为完成"的条件即可，一行级改动。

### 问题 3：旧任务新增 execution_control 兼容是否过宽 —— 独立结论：不过宽，实际效果等价于"旧 payload 忽略该键"

**证据：**
- `page_review_recovery.py:26-31`：仅当旧 payload 无 `execution_control` 且新 payload 有时，把新 payload 的该键注入比较集。而 `enqueue` 恒定冻结 `execution_control`（`page_review_job_service.py:101-106`），且其取值完全由同时被严格比较的输入派生：`max_parallel_steps` 来自 `routes[lane].max_concurrency`，`parallelizable_step_ids` 来自 pages 数量。路由、页面、条款包、全部版本键中任一变化都会先在 `comparable != payload`（`page_review_recovery.py:30`）被拒。因此该 shim 唯一放行的人群就是"同契约、无 execution_control 的历史串行任务"，对该人群注入值恒等于自身 payload 值，比较上是无操作。
- 非遗留任务（有 `execution_control`）走严格比较；更旧的 `parallel_execution` 遗留键会造成不匹配而被拒 —— 拒绝方向安全。

**保留意见：** 语义上"调度方式不改变判读语义"成立（同 prompt 版本、同路由身份、receipt 内容与调度无关），我接受该兼容；但应补一条边界测试 —— 遗留任务 + 变更路由仍须 409（现有 legacy_serial 测试 `test_page_review.py:104-114` 只覆盖同路由），防止未来有人把该 shim 误推广到其他键。

### 问题 4：response_attempts 在失败恢复中的缺口 —— 三处，均为留痕/审计缺口而非正确性缺陷

1. **可重试抛出路径丢弃当次记录**（`page_review_job_executor.py:110-115`）：endpoint 失败直接 raise，不提交 checkpoint（`fail_step` 不写 checkpoint）；该次调用内若已有成功子调用（`read_page` 的 length 加倍重试等场景）其 `recorded_completion` 记录与 raw 制品链接全部丢失。且 endpoint 类失败最终 lane_failure checkpoint 的 `response_attempts` 恒为 `[]`（测试 `test_page_review_job_executor.py:156` 证实）——"发起过 2 次网络尝试"只存在于步骤 attempt 计数与事件里，不在 receipt 中。
2. **不跨步骤 attempt 累积**：`attempts` 是执行器单次调用的局部列表；重试后从 `[]` 重来。失败 lane 的跨 attempt 历史只能经前驱 job 的 checkpoint/事件追溯。重读路径中复用 lane 的 receipt 完整携带前驱 `response_attempts`（好）；重读 lane 从空开始（可接受，`predecessor_coverage_id` 提供链路，但未见文档声明）。
3. **波次死亡/租约丢失/取消时**：raw_response 制品已落盘（executor:101）但元数据永不提交 → 孤儿制品、无链接。已成功提交的读道不受此影响：`PageReviewRecord` 自带 `response_sha256`（`app/storage/page_review_repository.py:103`），原响应留存有双重锚点；`app/workflow/` 无任何 checkpoint/事件清理代码（grep 证实），留存是永久性的。

**最小修复：** 在 `recorded_completion` 中同时记录失败的调用（finish_reason=None + failure_kind），使 attempt 耗尽时的 lane_failure checkpoint 至少携带最后一次 attempt 的完整子调用轨迹；跨 attempt 轨迹明确以 JobEvent（可考虑在 `fail_step` 事件 payload 中附带该次 attempts）+ 前驱链为准并写入文档。孤儿制品问题通过问题 1 的提前提交收窄窗口，彻底治理（GC 无主 blob）超出本次范围。

### 附加发现

- **F6（应修）：波次取消路径在事务提交前调用投影回调。** `runner.py:546-551` 在 `session.begin()` 块内、`cancel_at_boundary` 之后立即 `_notify_cancelled`，违反其自身契约"在任务取消事务提交后投影"（`runner.py:719-727`）；串行路径是正确的（先出块再通知，`runner.py:369-371`）。回调读到的将是取消前状态，投影可能空转，靠启动重扫收敛（`runner.py:726` 自认）。修复：用标志位把通知移到 with 块之后。
- **F7（观察，不改）：** (a) `_select_parallel_wave` 以 `runnables[0]` 可并行性决定整波（`runner.py:264-265`）：page0 两读完成后 `reconcile:0` 居首且不可并行，会抑制后续页读波次，串行执行 reconcile 后才恢复 —— 吞吐凹陷，非缺陷；(b) `complete_step` 的 `{"attempt": step.attempt, **checkpoint_payload}` 合并顺序（`jobstore.py:669`）允许调用方 payload 覆盖 attempt —— 重读复用 receipt 恰好携带前驱 attempt（测试断言相等，属有意），仅作命名冲突警示；(c) `enqueue` 不校验 manifest 中重复 `page_artifact_id`，会产生重复 step_id 落到唯一约束报错（`page_review_job_service.py:93-100`），宜改为 `InvalidJobDefinitionError`；(d) 心跳 join 超时（>10s）会把仍有效的租约误判为丢失（`runner.py:652-654`），单写者 SQLite 下风险低，仅记录。

## 证据与假设

- 全部结论来自上述文件行号的直接阅读；测试行为引用自三个指定测试文件及 `conftest` fixture。测试中 `PAGE_REVIEW_CLOUD_CONCURRENCY="2"` 使 R3 用例确实走并行波次路径（`max_parallel_steps=4`），故波次相关分析对现有测试是活的。
- 假设 1：`direct_openai_completion`/`read_page`（`app/llm/`，超出授权范围）内部对每次完成调用有确定行为（length 重试为测试所证）；HTTP 超时是否存在未验证。
- 假设 2：`on_cancelled`/`on_failed` 投影回调打开独立会话（从 `runtime` 装配与文档语义推断）；F6 的实际影响依赖该假设。
- 假设 3：`PageReviewJobExecutor` 不会被注册到含 `waiting_user` 步骤的其他 job_type 上（发现 B 的"R3 不可达"前提）。
- 不确定性：`read_page` 是否会在一次执行器调用内先成功后 endpoint 失败（决定缺口 4-1 的实际触发频率）；`PageReviewRepository.get_review` 返回对象的字段集（binding 校验完整性依赖它，未见 定义体，仅 grep 到写入侧）。

## 风险、缺口与验证需求

按优先级：
1. **高** — 波次延迟提交（问题 1）：崩溃/断电丢失半径 = 整波模型花费 + raw 制品失联；修复为 as_completed 内逐个提交。
2. **高** — 死亡+可重试失败 → failed_final 钉死 + 受控重读不可达（问题 2 发现 A）：需要 `retry_failed`/`resume_cancelled` 重置 attempt + 确认 R3 人工重试入口 + 409 文案修正。
3. **中** — 波次取消路径 notify 时序违反契约（F6）：一处分层修正。
4. **中** — 恢复器 checkpoint 信任未绑定 attempt（发现 B）：当前 R3 不可达，属通用状态机地雷，一行级校验可拆除。
5. **低** — response_attempts 三处留痕缺口（问题 4）；孤儿 raw 制品留存策略；重复 page_artifact_id 入队校验；心跳 join 误判；波次队头抑制（F7）。
6. **验证需求**：(a) 双步波次"先到先持久化"测试（当前应失败）；(b) 死亡预算耗尽 + retry_failed 恢复的 R3 端到端合成测试；(c) 遗留任务 + 变更路由的 409 测试；(d) 确认 `read_page`/completion 的 HTTP 超时（见问题 2）；(e) 确认 R3 failed_final 任务的 v2 API 重试入口是否存在（`app/api/v2/jobs.py` 不在我的授权读取集，未验证）。

## 建议的下一步

请 Codex 裁定三件事：
1. **问题 1（授权外输入）**：`app/llm/page_review_harness.py` 的完成调用是否有 HTTP 超时？若无，问题 1 的逐个提交修复必须与每调用超时配对，否则一个挂起的 lane 读取将在无限期占住租约的同时逐个提交其余结果 —— 语义可接受但取消延迟无界。这决定修复是否需要两处改动。
2. **问题 2（产品决策）**：R3 任务 failed_final 后的恢复入口走通用 jobs API 重试，还是应扩展 `plan_page_reread`/API 语义？我的建议是前者 + attempt 重置（改动最小、状态机语义干净），但需要确认产品上"局部重读"是否被期望覆盖此场景。
3. **问题 4（方向确认）**：取消时"丢弃波次剩余成功结果"是否为有意设计（当前行为 + 测试默许）？若确认有意，我建议仅在 design 文档记一句；若希望取消前尽量落盘，可把取消检查移到全部成功提交之后。
在我这边，问题 3（execution_control shim）无需改动，仅补一条"遗留 + 变更路由仍拒绝"的测试即可关闭。以上均为只读审阅结论，最终采纳与验收归 Codex。
