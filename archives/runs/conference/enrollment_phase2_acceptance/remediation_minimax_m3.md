I have all I need. Let me write the final report.

# Phase2 修复后独立验收 — Codex 独立验收者

## 1) 裁决

**REVISE**

骨架闭合（P0 通过项见下），但仍有 **1 个 P1 真实缺陷 + 1 个 P2 真实缺陷 + 2 个 P3 真实缺陷**。其中 P1已经在隔离复现中确认；P2 同样在生产 schema 中确认；P3 中 P3-1 在 `_validation_handler` 中显式存在未修复代码。

## 2) 仍存在的真实问题（按严重度）

### P1-1 `next_runnable_step` 忽略 `retry_not_before`，runner 泄漏租约
**文件**：`app/workflow/jobstore.py:272-282`、`app/workflow/runner.py:157-179`
**复现**：任务进入 `failed_retryable` 且 `retry_not_before` 在未来 →任何把 `state` 拨回 `queued` 但保留 `retry_not_before` 的路径（手动 SQL、调试回填、或后续路径若不当清除）→ worker claim → `_run_claimed` 第 169 行 `next_runnable_step` 返回该步 → 第 179 行 `start_step` 抛 `StepDeferredError` → 异常向上传播 → `_commit_step_*` 未执行 → 租约写但未释放 →任务卡在 `state=running, lease_owner=<worker>`。
**隔离证据**：8 月 14 日 11:30 在 `tests/v2/workflow/` 下临时写入定向测试（已删除），调用 `JobRunner.run_job("job-1")`，断言任务状态：
```
run_job returned=None raised=StepDeferredError('步骤 s1 的退避等待期未结束（不早于 2026-08-14T00:00:30）')
  job.state = running
  job.lease_owner = 'w2'
  step.state = failed_retryable
  step.attempt = 1
  step.retry_not_before = 2026-08-14 00:00:30
  events = [(1, 'created'), (2, 'step_started'), (3, 'step_failed'), (4, 'retry_scheduled')]
```
**影响**：未到期的 `failed_retryable` 任务被错误认领后，`StepDeferredError` 不是 `LeaseLostError`，不被 `run_once` 的 `except LeaseLostError` 吞掉。Grok 报告 P2-2 描述的"不退租、循环"。现有 `tests/v2/workflow/test_jobstore.py::test_start_step_increments_attempt_and_step_deferred_rejected` 仅验证 `start_step` 在直接调用时抛错，未覆盖"runner 把这条抛出路径走通后任务/事件/租约状态"。
**注**：标准生产路径（`requeue_due_retries` 在 `failed_retryable` 上筛选 `retry_not_before <= now`）不会构造该状态，但任何直接重置 `state=queued` 而不重置 `retry_not_before` 的路径都会触发。设计 §3.2 中 `_check_run_claimed` 应在 `next_runnable_step` 中应用 `step_is_deferred`。
**修复方向**：`next_runnable_step` 跳过 `step_is_deferred(state, retry_not_before, now)` 为真的步；若全部候选都被推迟则返回 `None`，让 runner 走 `release_deferred`。或：在 `start_step` 抛 `StepDeferredError` 处，让 runner 把任务转回 `queued` 且保持 `retry_not_before`。

### P2-1 `ReviewRunRecord` 缺 `rule_set_id`，跨 rule_set 的 scope 错误无法被数据库或仓储拦下
**文件**：`app/storage/models.py:574-596`、`app/storage/repositories.py:345-360`、`app/domain/contracts/review.py:89-97`
**复现**：当前 `data_v2/enrollment-review-v2.sqlite3` 的 `review_runs` 表只有 `rule_set_revision`：
```
review_runs columns:
  review_run_id, review_episode_id, protocol_version_id, rule_set_revision,
  evidence_snapshot_id, started_at, completed_at, supersedes_review_run_id,
  payload_json, payload_sha256, created_at
```
无 `rule_set_id`。`ReviewEpisodeRecord`（`models.py:106-145`）有 `rule_set_id` + `rule_set_revision`，与 `(rule_sets.rule_set_id, rule_sets.revision)` 形成复合外键。
`_check_run_scope` 只比较 `episode.rule_set_revision == run.rule_set_revision`，不比较 `rule_set_id`。两个 RuleSet 恰好使用相同 revision 号时，仓储无法拒绝"episode绑 A、run 数字撞 B"的错位。
**影响**：在 Phase 3 多协议/多 RuleSet 之前这是理论风险；当前单用户本机数据根永远只挂一个 RuleSet。但域合同里 `ReviewRun` 缺 `rule_set_id` 是后续阶段会踩的合同洞。Schemas (`fixture-v1.schema.json` `ReviewRun`) 与领域一致地缺 `rule_set_id`，是系统性省略。
**裁决**：Grok P2-5 是**真实缺陷**，但**当前阶段（单 Mac 单用户单 RuleSet）无实际触发条件**。在 Phase 3 协议解构之前补齐，避免事后改 schema撕裂已落库记录。

### P3-1 `_validation_handler` 丢弃 `RequestValidationError.errors()`，422 不返回字段路径
**文件**：`app/api/v2/errors.py:180-196`
**复现**：`POST /api/v2/jobs` 提交 `{"idempotency_key":"<256字符>","job_type":"t","payload":{},"steps":[]}` 时，所有422 都走 `_validation_handler`，`exc.errors()` 完全丢弃，`context=None`，前端只能拿到 `"请求参数不合法"` 标题。
**影响**：用户在超过 256 字符幂等键、步骤编号拼错、依赖字段名写错等场景下，无法定位被拒字段，需对照原始 JSON 排查。
**裁决**：Pi F-1 是**真实缺陷**，未修复。`context=None` 写死在 `_validation_handler`。可修复但需遵守"不泄露 SQL/堆栈/枚举"，仅把 `loc`投影成 `steps.0.step_id` 这类路径。

### P3-2 `StalenessRepository.open()` 返回已关闭的旧行，无法在同 source revision 下重新打开
**文件**：`app/storage/staleness.py:58-94`
**复现**：打开 stale → 关闭 → 用完全相同的 `(target_type, target_id, reason, source_entity_type, source_entity_id, source_revision)` 调 `open()` → 返回 `cleared_at` 已写的旧记录，`list_open()` 仍空。
**影响**：仅在"上游在同一 revision 反复触发"才会撞到。正常情况下新上游变化伴随 `source_revision` 递增，会落新行。
**裁决**：Grok P2-1 是**真实合同洞**，但当前域合同里 `source_revision` 是不可变整数（每次上游变化伴随 `revision++`），单用户场景不易触发。修复方向：关闭后重开需要清空 `cleared_at`/`cleared_by_review_run_id`，或 `close_covered` 后允许同键重新 `open()`。
**测试缺口**：`tests/v2/storage/test_staleness.py` 覆盖了"重复 open 幂等"和"按目标精确关闭"，但未覆盖"关闭后再 open 同源同版本"。

## 3) 对四项争议结论逐项裁决

### 争议 A：stale 同源同版本重开（上一轮 Grok P2-1）
**裁决**：**真实缺陷**。代码层证据：`staleness.py:69-82` 按全键查重，无视 `cleared_at`。测试层证据：缺关闭后再 open 的回归测试。领域层论证：`source_revision` 在 Phase 0.5 合同中代表"上游某实体的某一发布版本"，同一上游重复发布同一版本在临床治理流程中可能发生（撤回/重发），按合同不应吞掉事件。当前实现会让第二次 `open()` 静默返回已关闭记录，调用方无法判断"曾经 closed"还是"从未 open"。
**阶段风险**：低（需要同 source_revision 重复出现才触发）。

### 争议 B：ReviewRun 规则集作用域（上一轮 Grok P2-5）
**裁决**：**真实缺陷**。代码层证据：`models.py:574-596` 缺 `rule_set_id`；`repositories.py:345-360` `_check_run_scope` 只比 revision；schema (`fixture-v1.schema.json` `ReviewRun`) 同步缺 `rule_set_id`；域模型 `ReviewRun` 缺 `rule_set_id`（line 89-97）。**注意：缺 `rule_set_id` 在 schema、域、DB 三处保持一致，是设计层面的省略而非单点遗漏**。
**阶段风险**：低（单 Mac 单 RuleSet），但应早于 Phase 3 协议解构补齐。补法：补列 + 复合 FK 到 `rule_sets` + `_check_run_scope` 加 `episode.rule_set_id == run.rule_set_id` 校验。这是增量 migration，不破坏0002/0003 的现有数据（任何已有 `review_runs` 行可填入 `rule_set_id` 等于 episode 的 `rule_set_id`，因为 episode 已有外键保证唯一性）。

### 争议 C：取消与步骤提交并发（上一轮 Grok P2-3）
**裁决**：**误报（在 SQLite WAL 下不会触发丢更新）**。`JobRecord` 通过 `RevisionedRecordMixin` 启用 mapper versioning（`version_id_col=revision`），但 SQLite WAL 单写者约束 + SQLAlchemy 默认 `BEGIN IMMEDIATE` 序列化写锁，`request_cancel` 与 `_commit_step_*` 不会同时持锁。两种顺序都正确：
- runner 先 commit step：cancel 读到 revision=R+1，写入 cancel_requested；下次循环 `cancel_at_boundary` 处理。
- cancel 先 commit：runner 读到 `state="cancel_requested"`，`_run_claimed` 第 166 行检查并 `cancel_at_boundary`。
**未复核**：跨进程并发（多 uvicorn worker 同时跑同一租约）。在本地单用户单进程产品边界外，不在本次验收范围。
**建议**：把 mapper versioning 的处理保留作 safety net；无需返工。

### 争议 D：退避未到期步骤被错误认领（上一轮 Grok P2-2 + 本次 P1-1）
**裁决**：**真实缺陷**。本次已用定向测试复现（`StepDeferredError` 泄漏，`lease_owner` 持有，`retry_not_before` 保留）。runner 需要 `next_runnable_step` 主动应用 `step_is_deferred`，或在 `start_step` 抛 `StepDeferredError` 后让 runner 走"释放租约回到 queued"分支。

## 5) 已关闭问题的证据

| 上轮报告 | 当前状态 | 证据 |
|---|---|---|
| Grok P2-4 幂等 `session.rollback()` | **已关闭** | `app/storage/idempotency.py:116-164`：`resolve()` 使用 `on_conflict_do_nothing` + 重新 `get()`；无 `session.rollback()`。`tests/v2/storage/test_idempotency.py:159-179` 新增 8 线程并发同键同 payload 测试，所有线程拿到同一 `result_id`、仅1 个 `created=True`。本地运行通过。 |
| Codebuddy P2-1 恢复进度 | **已关闭** | `app/workflow/jobstore.py:972-973`：`_reset_interrupted_steps` 在 `append_event` 前调用 `_completed_count`，事件携带正确 `progress_completed`。 |
| Codebuddy P3-1终败事件 | **已关闭** | `app/workflow/jobstore.py:1108-1115`：`_finalize_job_failure` 写 `JobEventType.FAILED` 事件。`JobEventType.FAILED = "failed"` 在 `enums.py:178` 注册。 |
| Pi F-1422 字段路径 | **未关闭** | `app/api/v2/errors.py:180-196`：`_validation_handler` 仍 `context=None`。 |
| Pi F-2 SSE done `last_seq` | **已关闭** | `app/api/v2/jobs.py:244`：`"last_seq": snapshot.last_event_seq`。 |
| Pi F-3 级联事件 `progress_total=0` | **已关闭** | `app/workflow/jobstore.py:1066-1067`：`_cascade_final_failure` 写 `progress_total=job.progress_total`。 |
| Pi F-5 `EXECUTOR_MISSING` 泄露 `job_type` | **已关闭** | `app/workflow/runner.py:201`：detail 改为"当前任务暂时无法执行，请联系维护人员检查任务配置。"。 |
| 上轮 P3-3 OperationalError 全归 DATABASE_BUSY | **部分关闭** | `app/api/v2/errors.py:133-150`：先 `_is_sqlite_busy` 区分；剩余 OperationalError → `LOCAL_DATA_ERROR`。 |

## 6) 验证锚点核对

- 后端：`PYTHONPATH=. .venv/bin/pytest -q` → **464 passed, 1 skipped, 18 subtests passed**。跳过的 `MG-K10-SAR/06003` OCR 缓存夹具与本阶段无关（历史夹具）。
- 前端：`cd frontend && npm test` → **207 passed (25 files)**。
- 聚焦套件：`tests/v2/storage tests/v2/workflow tests/v2/api` → **183 passed**。
- 现场库：`data_v2/enrollment-review-v2.sqlite3` revision `0003`、`integrity_check=ok`、`journal_mode=wal`、`synchronous=FULL(2)`；表 `review_runs` 缺 `rule_set_id` 已确认。

## 7) 尚未验证的边界

1. **多 uvicorn 进程并发**：本机单用户产品边界外。本地 `runs/execution/.../manager.md` 也仅验证"同机多进程由 SQLite WAL 写锁保证"，未跑 `run_once` 同时多进程。
2. **`_flush_guarded` 在嵌套事务中的效果**：`session.rollback()` 在 `_flush_guarded` 中用于 IntegrityError，调用方多为 `with session.begin()`。Idempotency 路径不再触发此问题；其他 `IntegrityError`（外键违反）路径未在测试中覆盖"rollback 把外层未提交的同行写入一并丢弃"的回归测试。
3. **Staleness 同源同版本重开**：当前测试未覆盖。
4. **Alembic `downgrade` 在真实数据集上**：测试仅空库；未跑带数据降级。
5. **长步骤跨租约时长**：测试用 FakeClock 推进时钟；未跑真实时钟下的30s+ 步骤。
7. **Playwright e2e**：未在本次执行；按 implement.md §6 应在 dirty screenshot 清理后单独跑。

## 8) 决议REVISE。P1-1 必须修复（runner 退避泄漏）；P2-1建议在 Phase 3 之前补 `review_runs.rule_set_id` 列与复合 FK（同时调整 schema 与领域 `ReviewRun`）；P3-1（422 字段路径）和 P3-2（stale 重开）可随下一轮修复。

无需返工的：取消/步骤提交并发（争议 C，已是 WAL 序列化下安全）。

---

实际产物：本轮工作写入了定向测试 (`tests/v2/workflow/test_runner_deferred_repro.py`)、发现后已删除；运行了 `tests/v2/storage/test_idempotency.py`、`tests/v2/workflow tests/v2/api`、全量 `pytest -q`、`npm test`，对 live `data_v2` 库查询 schema。运行产物未污染 V2 数据根或测试树。
