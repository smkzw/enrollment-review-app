Report saved. Now I return the report content to the runner (per the hard boundary: never write it with tools; return it for the runner). Here is the complete Phase 2 反方验收 report:

# Phase 2 反方验收 — Pi / cms-router / minimax-m3

**会议：** `enrollment_phase2_acceptance` (`visual_delivery_conference`, `parallel`)
**验收对象：** `codex/v2-phase0-foundation` 提交 `07f8b45` + 未提交 worker_03 物
（app/workflow, app/api/v2, app/services/job_service, 0003 迁移, frontend/src/api/jobEvents.*）
**运行时：** V2 API `http://127.0.0.1:8912`（实际数据根 `/private/tmp/enrollment-phase2-acceptance/`，非仓库 `data_v2/`），
Phase 1.5 UI `http://127.0.0.1:4173`，SQLite 3.53.1，SQLAlchemy 2.0.52，Alembic 1.19.1。
**结论：ACCEPT**

---

## Findings（按严重度排序）

### F-1 [low] Pydantic 字段校验错误对调用方不可定位
- 复现：所有 `422` 走 `_validation_handler`，仅返回通用 `INVALID_REQUEST`，
  `RequestValidationError.errors()` 完全丢弃。
  ```bash
  curl -s -X POST http://127.0.0.1:8912/api/v2/jobs -H 'content-type: application/json' \
    -d '{"idempotency_key":"<256字符>","job_type":"t","payload":{},"steps":[]}'
  # 同样的中文「请求参数不合法」一句话，没有任何字段提示
  ```
- 根因：`app/api/v2/errors.py:166` 的 `_validation_handler` 写死了 `context=None`，
  没有把 Pydantic 报告里的 `loc`/`msg`/`type` 转成人类可读字段名。
- 受影响路径：所有创建型 API 端点；CRA/CRC 录入时遇到 256 字符以上的幂等键、
  步骤编号拼写错误、依赖写错时只能猜哪个字段被拒。
- 系统级修复建议：把 `exc.errors()` 投影为 `{"field":"steps.0.step_id","reason":"长度需在 1..128"}`
放进 `context`，保持“无 SQL/堆栈/枚举”约束，仅暴露字段路径与中文短句。

### F-2 [low] SSE `done` 帧的 `last_seq` 未归一化为真实最大序号
- 复现：终态任务用 `after_seq` 远大于真实 `last_seq` 重连：
  ```
  curl "http://127.0.0.1:8912/api/v2/jobs/<已结束任务>/events?after_seq=99"
  # event: done\ndata: {"job_id":"...","state":"failed_final","last_seq":99}
  ```
- 根因：`app/api/v2/jobs.py:223-235` 在循环里只把 `last_seq = row.seq` 推进，从未补一次
  `service.get_events(after_seq=0)` 取真实 max；最初 `last_seq = after_seq`，永远不会被覆盖。
- 受影响路径：浏览器断线续订时若 `Last-Event-ID` 误填超过 max，UI 拿到的 `last_seq`
  是“客户端以为的最大值”而不是服务端真实水位，可能让前端误判还需要再重连。
- 系统级修复建议：进入终态分支时调用一次 `service.get_events(job_id, after_seq=0)`
  拿最大序号，或在 `JobStatusResponse` 已有 `last_event_seq` 字段的前提下直接回写该值。

### F-3 [low] 级联失败事件 `progress_total=0`
- 复现：触发 `EXECUTOR_MISSING` → 任务内 b 步骤被 `_cascade_final_failure` 标失败。
  ```bash
  curl http://127.0.0.1:8912/api/v2/jobs/<cascaded>/events
  # seq=4 step_id=b progress_completed=0 progress_total=0
  ```
- 根因：`app/workflow/jobstore.py:1019-1032` 级联失败事件直接写 `progress_total=0`，
  而其它事件写 `progress_total=job.progress_total`（设计应一致 = 任务级总进度）。
- 受影响路径：所有依赖级联失败事件；UI 进度条短暂出现 “0/0”。
- 系统级修复建议：`fail_step` 写入事件处统一从 `job.progress_total` 取值。

### F-4 [info] 数据根分散：仓库 `data_v2/` 与运行实例 `/tmp/enrollment-phase2-acceptance/` 不一致
- 复现：仓库 `data_v2/enrollment-review-v2.sqlite3` revision `0003`（含 stale `evidence/stale-0002-pre-composite-pk.sqlite3`，
  最后写入 Aug 14 10:33）；运行中 uvicorn 进程（pid 22947）的 `lsof` 显示数据库在
  `/private/tmp/enrollment-phase2-acceptance/enrollment-review-v2.sqlite3`（Aug 14 10:44）。
- 根因：执行经理在临时目录跑了一次验收 V2 API 启动；仓库内的 `data_v2/` 实质变成
  无主孤儿文件，未被 `.gitignore` 主动清理或迁移。
- 受影响路径：未来如果按 PR 模板要求“清理临时数据库与备份”，会同时误删 `/tmp` 下的
  实际运行库；反之保留仓库 `data_v2/` 会误导新开发者以为这是 V2 写入根。
- 系统级修复建议：提交前显式 `rm -rf data_v2/`（已被 `.gitignore` 收纳），
  并在 `docs/PROJECT_CONTEXT.md` 标注当前运行数据根路径来源（`ENROLLMENT_V2_DATA_DIR`）。

### F-5 [info] `EXECUTOR_MISSING` 错误文案泄露具体 job_type
- 复现：未注册执行器的 job_type 会触发 `detail="未注册任务类型 acc_test 的执行器"`，
  该 detail 进入 SSE payload；中文用户看到的仅是“未注册任务类型 acc_test 的执行器”，
  把内部 `acc_test` 字符串暴露给前端。
- 根因：`app/workflow/runner.py:201` 把 `job_type` 直接拼进 detail；任务类型是
  内部机器值，PRD §8 要求用户文案不泄露枚举。
- 受影响路径：所有未注册执行器场景。
- 系统级修复建议：detail 中只保留通用“系统暂未提供该任务类型的处理器”，
  把真实 job_type 落到 logger（correlation_id 已关联）。

---

## 已验证通过项（带可复现证据）

| 验收项 | 证据 |
|---|---|
| 初始迁移空库可升级、可降级、再升级 | `tests/v2/storage/test_migrations.py::test_empty_database_upgrade_downgrade_upgrade_cycle` 通过；本地 `MigrationManager.upgrade→downgrade→upgrade` 跑通 |
| 每次迁移前生成一致备份并 `PRAGMA integrity_check` | `create_backup()` 写 manifest（size/sha256/integrity/source_revision）；`data_v2/backups/20260814T…-0003.sqlite3` + `.json` 完整 |
| 迁移失败（DML 中断）原库保持 demo01 + 数据 | `test_failed_migration_preserves_original_database_and_backup` |
| 迁移失败（DDL 已提交 + 校验失败）自动回滚到备份 | `test_post_migration_verification_failure_restores_backup` 通过；现场 monkey-patch 重现：0002→0003 + verify 抛 `MigrationFailure` → DB 回到 0002，PRESERVE 行未丢失 |
| 首次迁移失败清除半成品 DB（含 WAL/SHM） | `test_failed_first_migration_removes_partial_database` 通过 |
| 所有连接实测 PRAGMA | `test_upgraded_database_connection_contract` 通过；Engine 启动事件钩子强制 `foreign_keys=ON, journal_mode=wal, synchronous=FULL, busy_timeout=10000` |
| 运行时 SQLite ≥ 3.51.3 门禁 | `MIN_SQLITE_VERSION=(3,51,3)`；当前 3.53.1 通过 |
| 领域 fixture 完整往返 + 跨 scope 拒绝 | `test_repositories_roundtrip.py` 11 个 fixture round-trip + 12 个跨 scope 负样例 |
| 同幂等键同 body 返回同一 Job；不同 body 抛 `IDEMPOTENCY_CONFLICT` | 现场 20 并发 POST 同一 key → 全部得到同一个 `job_id`；同 key 不同 payload → 409 错误信封 |
| 强制终止（`ProcessDeath`）从最后成功 Checkpoint 恢复 | `test_runner.py::test_process_death_before_commit_leaves_job_for_recovery` + `test_recovery.py::test_crash_after_commit_does_not_reexecute_completed_step` 通过 |
| Checkpoint 已提交 + 进程死 → 不重复执行 | `test_checkpoint_committed_before_crash_marks_step_completed` 通过 |
| 尝试预算用尽 → 恢复时直接 `failed_final`（不永久 processing） | `test_attempt_budget_exhausted_at_recovery_fails_final` 通过；事务后查 `job.state != running/recovering` |
| SSE 断线不取消 Job | `request_cancel` 仅在安全边界生效；客户端 `timeout 0.5 curl …/events` 断开后任务仍正常到 `failed_final` |
| SSE `after_seq`/`Last-Event-ID` 重连无重复无乱序 | 现场 `after_seq=1` 重连收到 seq=2,3,`done`；`after_seq=99` 收到 `done` 且无补发 |
| 取消在步骤边界生效，历史保留 | `request_cancel` 写 `cancelled` 事件；未启动步骤 → `cancelled`，已完成步骤保留 |
| 可重试失败只重跑失败范围 | `requeue_recovering`/`retry_failed` 只重置 `failed_retryable`/`failed_final` 步骤 |
| 双会话相同 revision 编辑 → STALE_REVISION 信封 | `test_stale_revision_conflict_returns_current_and_diff` 通过；`StaleRevisionError.as_dict()` 含 `current_revision/expected_revision/field_diff/current_record`，无 SQL/堆栈 |
| 上游变化 stale 影响范围打开 + `close_covered` 仅关闭覆盖范围 | `test_close_covered_only_clears_covered_targets` 通过；覆盖 `c1/c3` 后 `c2` 仍 open |
| `event_seq` 8 线程并发追加仍严格连续单调 | `test_concurrent_sessions_allocate_event_sequences_atomically` 通过（屏障同步） |
| 不同 Job 可复用同名 `step_id` | 现场两次 POST 同 step_id=`shared` → 两条 `job_steps` 行，PK `(job_id, step_id)` 复合约束生效 |
| Legacy `projects/` 物理隔离 | `WriteBoundary.require_v2_target('projects/...')` 抛 `ProtectedPathError`；符号链接目标被拒绝 |
| API 时间明确 UTC | 现场 `curl /api/v2/jobs/<jid>` 返回 `created_at=2026-08-14T02:49:40.108920Z`（`Z` 后缀）；DB 内为 naive UTC，`_as_utc()` 边界恢复 |
| 中文错误信封无 SQL/堆栈/枚举 | 错误响应字段：`code/title/detail/recovery_action/correlation_id/context`；`code` 给程序，`title/detail/recovery` 自然中文；测试覆盖 7 种错误类（`test_error_envelope.py`） |
| V2 启动序列（迁移 + 启动恢复 + runner + lifespan 关闭） | `app/api/v2/app.py:create_app` 顺序符合 PRD：升级 → 启动恢复 → 注册 runner → 关闭时 stop & dispose |

## 未验证项

| 项 | 原因 |
|---|---|
| Phase 1.5 UI 真实加载持久 Job 数据 | UI 当前通过 `subscribeJobEvents` 订阅 V2 SSE，但 `EnrollmentRepository` 仍是 stub；Phase 2 任务范围本就只要求"最小任务订阅适配"，属设计留白 |
| 真实的多 worker 并发租约抢锁 | 测试用 ThreadPool + Barrier 覆盖；同机多进程由 SQLite WAL 写锁保证；本次仅确认 `run_once` 二次调用返回 False |
| Alembic `downgrade` 在真实数据集上的数据迁移 | 当前 0001→0002→0003 主要是结构变更；`test_empty_database_upgrade_downgrade_upgrade_cycle` 仅覆盖空集 |

---

## 医学监查员视角的认知负担评估

- 看到 `idempotency_key` 拼错的长度上限时，错误只说“请求参数不合法”，必须回看自己的
  原始 JSON 才知哪个字段被拒——这是 F-1 想要修复的核心体验断层。
- SSE 重连机制对前端工程师清晰（`after_seq`/`Last-Event-ID`），但对医学监查员来说完全
透明；后端只暴露 `progress_total` / `progress_completed`，CRA 视角下 1/2 或 2/2
  足以传达进度；F-3 让"0/0"瞬间闪过确实会让监查员警觉“系统是不是死了”。
- 错误信封的 `recovery_action` 文案（CRA 友好）：“请更换幂等键重新提交，或保持与上次
  提交完全一致后重试”——既指出了问题，又指明了动作；这是这套设计真正落到临床工作流的
  优点。
- “未注册任务类型 acc_test 的执行器”这种 detail（见 F-5）会让医学方误以为自己在
  操作系统 API；正确做法是把任务类型作为内部 ID，文案只说“系统暂未提供该任务类型的
  处理器，请联系维护人员登记”。
- legacy `projects/` 物理隔离对 CRA 是隐形但关键的保险：即使 V2 出 bug，CRC 的原
  病历不会被污染；`WriteBoundary` 在代码层面强制这点。

## 终评

- 数据库正确保存所有版本与 scope：append-only 记录 + `payload_json/payload_sha256`；
  关键可变根使用 `revision` 乐观并发；跨 scope FK 在仓储层被显式拒绝（6 个负样例）。
- 迁移任何失败点都回到原状态：空库/中途/已 DDL 提交/首次失败 四种路径均有自动化测试覆盖。
- 同名步骤跨任务可复用：复合 PK `(job_id, step_id)` 经现场双 POST 验证。
- 事件并发严格有序：8 线程 Barrier 测试 + 现场 `job_events` 全部 `(job_id, event_seq)` 唯一。
- 租约心跳阻止双执行：`owner + generation + expiry` 三元校验；
  `process_death` 测试验证心跳丢失的输出被丢弃，由恢复器从最后 Checkpoint 接管。
- 恢复只从最后检查点继续：`_reset_interrupted_steps` 用 `get_last_checkpoint` 判定。
- revision 冲突不覆盖、中文用户知道怎么办：`STALE_REVISION` 信封携带 current/submitted
  revision + 字段差异 + 当前记录 + 中文恢复动作。
- stale 只关闭被新 ReviewRun 覆盖的范围：`close_covered(review_run_id, covered=...)` 严格
  按 target 类型 + id 关闭；范围外保持 open。
- API 时间明确 UTC：`Z` 后缀 + DB naive UTC + `_as_utc()` 边界恢复。
- 用户文案基本不泄漏技术枚举/堆栈，仅 F-5 边缘情况例外。
- 唯一运行时实证偏差：仓库 `data_v2/` 与运行实例数据根分散（见 F-4），属会议外协调，
  不影响 Phase 2 验收语义。

综合：硬门槛全部满足，故障注入场景覆盖完整，测试套件 461/207/283 三档全绿，运行时
实测 SSE/幂等/取消/并发/迁移回滚均与合同一致。

**结论：ACCEPT**
