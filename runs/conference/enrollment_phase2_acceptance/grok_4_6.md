# Phase 2 独立验收报告（静态；grok-4.6）

角色：新鲜上下文独立验收者，只读。未改任何文件，未读其他参会者输出，未读工作区外临床原始资料。浏览器打开 `http://127.0.0.1:4173` 与 API 探测 `http://127.0.0.1:8912` 均在工具调用阶段被运行时取消，**本报告不声称这些检查已完成**。

依据：本会话已读的 `AGENTS.md`、会议上下文、Trellis PRD/design/implement、总设计/计划前部，以及 `models.py`、`jobstore.py`、`runner.py`、`recovery.py`、`migrate.py`、`jobs.py`、`job_service.py`、`staleness.py`、`idempotency.py`、`concurrency.py`、`errors.py`、`states.py`、`app.py`、`vocabulary.py`、`db.py`、`repositories.py` 的 scope 校验段，和 `test_staleness.py`、`test_idempotency.py`、`test_repositories_roundtrip.py` 跨 scope 段。

---

## 1) Findings

### P1

**本会话静态审查未发现已证实的 P1 阻断项。**

未看到：不可变临床记录被原地覆盖、取消删除已提交 Checkpoint/事件、恢复后用过期租约写入步骤结果、或“processing”作为业务终态且启动恢复完全扫不到。这些是“未证实”，不是“已证明不存在”——`JobRepository.append_event`、迁移 SQL、前端、以及运行中的库/进程均未读到或未跑到。

### P2

**P2-1 同一来源 revision 的 stale 关闭后无法再打开**

- 证据：`app/storage/staleness.py` 第 68–82 行。`open()` 按 `(target_type, target_id, reason, source_entity_type, source_entity_id, source_revision)` 查找后，无论 `cleared_at` 是否已写，直接返回旧行。`EntityStalenessRow` 唯一约束正是这组字段（`models.py` 第 977–985 行）。`close_covered()`（第 121–149 行）按 `(target_type, target_id)` 关闭该目标上**全部**未关闭记录。
- 复现（静态）：打开 stale → `close_covered` 关闭 → 以同一 source revision 再 `open()` → 得到已关闭记录，`list_open()` 为空。`test_staleness.py` 只覆盖“仍打开时重复 open 幂等”和“按目标精确关闭”，没有关闭后再打开。
- 根因：把“打开幂等”实现成“唯一键命中即返回”，没有区分 open/cleared；关闭粒度是目标实体，重开没有清除 `cleared_*` 或插入新行。
- 修复：关闭后的同一键应重新打开（清空 `cleared_at` / `cleared_by_review_run_id`）或改为可追加的新行；`close_covered` 的覆盖集应包含 reason/source，避免一次 ReviewRun 误关无关来源。这是后续事实/规则变化的合同洞，不是单 fixture 补丁能收口的。

**P2-2 退避未到期步骤被当成可运行，runner 不退还租约**

- 证据：`jobstore.next_runnable_step`（第 272–282 行）只看 `RUNNABLE_STEP_STATES`（含 `failed_retryable`，`states.py` 第 66–69 行），不看 `retry_not_before`。`start_step`（第 497–498 行）在未到期时抛 `StepDeferredError`。`runner._run_claimed`（第 157–179 行）未捕获该异常。`step_is_deferred` 被 runner 导入但未使用。`release_deferred` 只在 `next_runnable_step is None` 时调用。
- 复现：任务进入 `failed_retryable` 且退避未到期 → worker claim 后 `start_step` 抛错 → `serve()` 记异常后继续 → 任务保持 `running` 直到租约过期，再被恢复器打回 `queued`，循环。若同任务另有已满足依赖的步骤，只要未到期失败步骤排序更前，后者被饿死。
- 根因：可运行性判断与退避约束分裂；异常被当成循环级故障，而不是“无当前可跑步骤，退还租约”。
- 修复：`next_runnable_step` 跳过 `step_is_deferred`；若仅剩延期步骤则 `release_deferred`；不要让 `StepDeferredError` 泄漏出步骤事务。

**P2-3 取消与步骤提交并发写同一 `jobs` 行**

- 证据：`request_cancel`（`jobstore.py` 第 717–753 行）在 running 时无租约校验即改 `JobRecord` 并追加事件。`complete_step` / `fail_step` 同时改同一行的进度/状态/事件序号。`JobRecord` 使用 mapper `version_id_col`（`models.py` 第 53–57 行）。`_commit_step_success` 只把 `LeaseLostError` 当丢弃；其它异常在 `_run_claimed`（第 214–221 行）被打成 `retryable=False` 的 fatal。
- 复现：步骤事务外执行将结束时调用取消 → 两事务争 `revision` / `last_event_seq` → 成功步骤的提交可因 `StaleDataError` 失败；随后 fatal 失败提交或二次冲突，已成功的执行器结果未落 Checkpoint；租约过期后该步骤被标 cancelled。
- 根因：取消是第二个 writer，却与持租约的步骤提交共享可变根行和乐观版本。
- 修复：取消只写 `cancel_requested` 标志（条件更新、不碰 version 冲突路径），或要求取消与 event_seq 分配走无 revision 碰撞的条件 `UPDATE`；步骤提交失败若是版本冲突，应重读后按“取消优先 / 重试提交”裁决，禁止把已成功执行打成 fatal。

**P2-4 幂等竞态在外层事务内 `session.rollback()`**

- 证据：`IdempotencyRepository.resolve`（`idempotency.py` 第 136–156 行）遇到 `IntegrityError` 先 `rollback()`，再读赢家。未提交的同哈希并发会走 `existing_sha256="(并发提交记录暂不可读)"` 并抛 `IDEMPOTENCY_CONFLICT`。`_flush_guarded`（`repositories.py` 第 151–163 行）同样 rollback 整会话。`test_idempotency.py` 第 116–155 行用“赢家已 commit + monkeypatch 第一次 get 未命中”模拟，不是两条未提交写事务。
- 复现：同键同内容并发 `create_job`，或 `resolve` 失败发生在 `session.begin()` 中途。
- 根因：用会话级 rollback 处理一行唯一约束冲突，破坏外层“一次用户动作一事务”；读不到未提交赢家时把同内容误判为冲突。
- 修复：`flush` 失败后只 `expire`/`begin` 嵌套保存点；同哈希重试读取，读不到则让调用方用新事务重试，不要对同内容报冲突。

**P2-5 `ReviewRun` 没有 `rule_set_id`，范围约束不完整**

- 证据：`ReviewRunRecord`（`models.py` 第 574–596 行）只有 `rule_set_revision`。`_check_run_scope`（`repositories.py` 第 345–360 行）只比 episode 的 protocol / revision / snapshot，不绑定 rule set 身份。
- 复现：两个 RuleSet 使用相同 revision 号时，仓储无法拒绝“episode 用 A、run 只带 B 的 revision 数字”。
- 根因：把 revision 当成规则集身份。设计要求 ReviewRun 绑定正式方案版本和 RuleModelRevision；缺少 rule set 外键就无法在库层保证。
- 修复：补 `rule_set_id` + 复合外键，并与 episode 的 `(rule_set_id, revision)` 交叉校验。

### P3

- **P3-1** `finish_failure`（`jobstore.py` 第 698–713 行）不写任务级失败事件；SSE 靠状态终态收口，审计序列不完整。
- **P3-2** `close_covered` 全表扫描未关闭 stale（正确性次要，规模后会放大）。
- **P3-3** 一切 `OperationalError` 都映射成 `DATABASE_BUSY`（`errors.py` 第 128–136 行），磁盘/损坏会被说成“繁忙”。
- **P3-4** 仓储异常（`ScopeViolationError` 等）未进 V2 错误处理器；当前只有 Job 路由，暂不爆，领域 API 一接就会 500。
- **P3-5** `mark_expired_running` / `cancel_expired_cancel_requests` 要求 `lease_expires_at IS NOT NULL`。正常 claim 会写入到期时间；若出现 `running`/`cancel_requested` 且租约为空，会留下非终态。未见写入路径，但是恢复器盲区。
- **P3-6** 默认 `create_app(executors={})`。若线上 runner 未注册执行器，任务会 `EXECUTOR_MISSING` 终败。未核对运行进程的执行器表。
- **P3-7** Job 状态接口仍返回英文 `state` / `error_code`；中文在 `state_label` / `recovery_action`。是否落到合成 UI 未验证。

---

## 2) 实际执行的检查与结果

| 检查 | 结果 |
|---|---|
| 必读任务/设计/计划与会议上下文 | 已读。范围是 SQLite 领域持久化、Job 恢复、中文错误、Phase 1.5 无回归；不含真实方案/OCR/审核。 |
| ORM / 迁移编排 / Job 状态机 / 租约 / 恢复 / SSE 路由 / 错误信封 | 已读上表所列实现。与 design §3–8 总体对齐。 |
| 跨 scope 仓储测试与 stale/幂等测试源码 | 已读。服务层拒绝多种错配；stale 关闭后再打开、真实并发幂等未覆盖。 |
| `pytest`、迁移 upgrade/downgrade、故障注入、legacy 树哈希 | **未执行**。 |
| `GET http://127.0.0.1:8912/openapi.json` 及创建/取消/重试/SSE | **未执行**（命令被取消）。 |
| 浏览器打开 `http://127.0.0.1:4173` | **未执行**（导航被取消）。 |
| 独立验收数据根上创建/删除测试任务 | **未执行**。 |
| 其他参会者报告、`runs/execution/.../manager.md`、前端源码、`JobRepository.append_event`、迁移 0001–0003 正文 | **未读**。 |

因此：持久化合同上的缺陷来自源码与测试缺口；“运行中无永久 processing / SSE 不丢不重 / UI 不夸大”不能当作已证实。

---

## 3) 视觉 / 交互审查

**未做真实浏览器审查。** 两次 `playwright` 导航均被取消，没有快照、没有窄屏、没有任务页点击。

只能根据已读设计/实施说明做边界判断，不能当视觉验收：

- Phase 2 明确不切 legacy 默认入口；V2 是独立 `app.api.v2.app:create_app`。
- Phase 1.5 仍是合成壳；implement 只允许“最小任务订阅适配”，不得让人以为方案解构、OCR、Patient Journey、入排审核已接真实后端。
- 未验证页面是否仍写“模拟/示例”，是否把 stub Job 画成可恢复的真实后台任务，中文是否泄漏 `failed_retryable` / `RECOVERY_RESET` 等词。

本节结论：视觉验收**未完成**，不能为“合成 UI 诚实、无回归”背书。

---

## 4) 已实现与尚未实现能力边界

**已在代码中看到、且与 Phase 2 合同一致的部分：**

- 独立 V2 数据根意图、`WriteBoundary` 设计、连接 PRAGMA（FK / WAL / FULL / busy_timeout）与 SQLite 版本门禁。
- Alembic 升级前 `sqlite3.backup()` + `integrity_check` + 清单；失败停止写服务；首次失败清未完成库；显式 `restore`。
- 可变根带 `revision`；不可变记录 append + payload SHA-256；有序 association table，不用逗号串。
- 关键跨项目/跨受试者/跨 episode 在仓储 `scope_check` 中拒绝，并有对应单测。
- 幂等 `(scope, key)` 唯一；顺序同哈希复用、异哈希冲突。
- 人工记录 `expected revision` + 字段 diff + `StaleDataError` 转信封。
- Job：先落库再执行；租约 owner/generation/到期；Checkpoint 与事件同事务；启动扫描过期租约；取消是持久请求；重试只重置失败步骤；步骤图有环/自依赖/缺边校验。
- Job API：创建/查询/取消/重试/SSE；`after_seq` 与 `Last-Event-ID`；断开只停订阅；时间在 API 边界补 `+00:00`；错误信封为中文问题/影响/恢复动作。

**按计划不属于本阶段、代码也未当成已交付的部分：**

- 真实方案上传/解构、II/III 判定、规则发布（Phase 3）。
- 上传、OCR、页图、EvidenceSpan 生产（Phase 4）。
- Patient Profile 抽取、Agent 审核、报告、真实项目（Phase 5–8）。
- 登录、多用户、权限、生产部署。
- `models.py` 未见 Amendment / InterpretationSource / OCRPage / CorrectionRecord 等后期表；Job 无 project 作用域。
- 默认执行器为空：持久任务底座在，业务步骤执行器不是本阶段临床能力。

**已实现但不完整、后续阶段会踩到的部分：**

- stale 是持久表，关闭/重开合同有洞。
- 跨 scope 主要靠服务层，库层没有 subject⊂project、fact⊂episode 的复合外键；绕过仓储的写入仍可能混搭。
- `SourceDocumentVersion` / `EvidenceSpan` 无项目/受试者外键。
- `AgentCall.rule_set_id` 无外键；无 episode 时可跳过范围检查。

---

## 5) 残余风险

- 长步骤若心跳失败，未提交 Checkpoint 的执行器会再跑一遍。单用户本机可接受；一旦步骤有外部副作用，必须靠执行器幂等。本会话未跑租约过期双执行实验。
- 取消与提交的 revision 竞争可能导致“执行已成功但库中无 Checkpoint”。
- `running` + 空租约、或 `cancel_requested` + 空租约，不在恢复 SQL 里。
- 迁移“已是 head 只校验”的路径失败时不会做备份回滚（会拒启动并保留原库）。未读 0001–0003，不能排除 schema 与 metadata 的边角差。
- 合成 UI 若把 stub 数据画成真实审核/OCR/恢复，会直接违反会议通过条件。此项未观察。
- 本机 4173/8912 是否指向独立验收数据根、是否碰 legacy `projects/`，未验证。

---

## 6) 结论

静态代码与已读测试表明：Phase 2 的主骨架（独立库、PRAGMA、备份迁移、append/hash、租约恢复、中文 Job API）已经按设计落地，**没有在已读代码里发现静默覆盖不可变临床史、或把“processing”做成不可恢复终态**。

但 stale 关闭/重开、Job 退避与取消并发、幂等事务 rollback、ReviewRun 缺 `rule_set_id` 都落在本次验收点名的合同上，且会进入后续阶段共享底座。浏览器与 API 运行证据缺失，不能把通过条件中的 UI 诚实、SSE、重启恢复写成已证实。

**结论：REVISE**
