# 设计：SQLite领域层与持久任务

## 1. Architecture

```text
app/api/v2 -> app/services -> app/workflow -> domain ports
                                      -> app/storage SQLAlchemy adapters
                                      -> app/agents adapters (later phases)
app/projections <- read repositories / verified domain records
```

- `domain` 保持纯 Python/Pydantic，不导入 SQLAlchemy、FastAPI 或本机路径。
- `storage` 拥有 ORM、Engine、Session、Alembic、备份和仓储实现。
- `workflow` 拥有 Job 状态机、租约、重试、取消、Checkpoint 与恢复策略。
- `services` 定义事务边界和跨仓储用例；API 只做协议转换。

## 2. Runtime And Database Root

- 新增 `ENROLLMENT_V2_DATA_DIR`，默认 `<repo>/data_v2`。
- 数据库：`data_v2/enrollment-review-v2.sqlite3`。
- 备份：`data_v2/backups/<utc>-<alembic-revision>.sqlite3`。
- 大对象：`data_v2/blobs/<sha256-prefix>/<sha256>`；本阶段只建立边界和元数据，不接入上传。
- `WriteBoundary` 同时保护 `projects/` 与其他声明 legacy 根目录。

使用同步 SQLAlchemy 2 `Session`，由应用服务持有最外层 `with session.begin()`。本机单用户与 SQLite 单写者约束下，不引入 `aiosqlite`；FastAPI 需要调用同步服务时放入线程池，SSE 订阅读事务保持短连接、短事务。

## 3. SQLite Connection Contract

每个连接执行并验证：

```sql
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA busy_timeout=10000;
```

- WAL 允许读写并行但仍只有一个 writer，因此仓储禁止长写事务。
- 保留默认自动 checkpoint；健康信息记录 WAL 大小与最后 checkpoint 结果，Phase 2 不自行并发跑多个 checkpoint。
- 启动要求 SQLite `>=3.51.3`；项目 `.venv` 当前为 `3.53.1`。原因是 SQLite 官方披露的 WAL-reset 并发竞态在 3.51.3 修复。
- 测试使用临时文件数据库，不使用 `:memory:` 冒充多连接行为。

Primary references:

- https://www.sqlite.org/wal.html
- https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
- https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- https://docs.sqlalchemy.org/en/20/orm/versioning.html
- https://alembic.sqlalchemy.org/en/latest/batch.html

## 4. Storage Shape

### 4.1 Mutable roots

- `projects`, `subjects`, `review_episodes`, `evidence_expectations`, `action_requests`, `jobs`, `job_steps` include integer `revision` and timestamps.
- SQLAlchemy mapper versioning protects ordinary ORM updates；应用服务仍显式执行 expected-revision 检查，以返回中文 diff 信封。

### 4.2 Immutable/versioned records

- `protocol_document_versions`, `rule_sets`, `source_document_versions`, `evidence_snapshots`, `evidence_spans`, `clinical_facts`, `review_runs`, `final_assessments`, `action_transitions`, `review_run_diffs`, `prompt_versions`, `model_configs`, `agent_calls`, `gate_results`, `job_checkpoints`, `job_events` 追加写。
- 每表保留关键可查询列、scope 外键、`payload_json`、`payload_sha256`、`created_at`。读取时校验 payload hash 并转回对应 Pydantic 合同。
- `rule_components` 与 `evidence_requirements` 独立成表，保证官方编号、父子关系和 requirement 查询不依赖 JSON 扫描；RuleExpression 作为组件的 canonical JSON/hash 保存。

### 4.3 Relationship and projection support

- 关键外键覆盖 project -> protocol/rules，subject -> project，episode -> subject/project/rules/snapshot，assessment/action -> episode/run/component/snapshot。
- 多值有序引用使用 association table，不以逗号字符串保存。
- `entity_staleness` 保存 target type/id、原因、来源实体/revision、opened_at、cleared_by_review_run_id；它是业务状态，不由前端自行推测。
- `idempotency_records` 唯一键为 `(scope, idempotency_key)`，保存 request hash、result type/id、状态与首次事务时间。

## 5. Job State Machine

```text
queued -> running -> completed
                  -> failed_retryable -> queued
                  -> failed_final
                  -> cancel_requested -> cancelled
running --lease expired/startup recovery--> recovering -> queued
```

- Job 与 Step 状态使用稳定机器值；中文由 API projection 提供。
- Claim 使用条件更新：仅 queued/recovering 且无有效租约可领取，同时递增 lease generation。
- Heartbeat 与 step commit 必须匹配 job id、owner token、generation 和未过期租约。
- Step 成功在一个事务内写 Checkpoint、Step 状态、Job 进度和递增 `event_seq` 的 JobEvent。
- 恢复器只根据持久状态工作；进程内 task/thread 不是真相。
- 取消请求持久化；worker 在声明的 safe boundary 检查并提交 cancelled 事件。

## 6. SSE Subscription

- `POST /api/v2/jobs` 或领域用例先落库返回 `job_id`。
- `GET /api/v2/jobs/{job_id}` 返回当前快照。
- `GET /api/v2/jobs/{job_id}/events?after_seq=N` 只读取 `job_events.seq > N` 并发送心跳；断开只结束订阅，不修改 Job。
- `(job_id, seq)` 唯一且单调；重连可无损补齐。SSE 不承载 worker coroutine，也不持有取消权。

## 7. Migration And Backup

1. 获取本机迁移锁并拒绝业务写入。
2. 打开源库，运行 passive checkpoint 后使用 Python `sqlite3.Connection.backup()` 生成一致备份。
3. 对备份执行 `PRAGMA integrity_check`，记录源 schema revision、文件大小和 SHA-256。
4. Alembic `upgrade head`；运行 metadata/schema 和基础读写验证。
5. 失败则停止启动，不自动用部分迁移库继续服务；提供从已验证备份恢复的显式命令。

初始 migration 提供 downgrade。SQLite 表结构变更使用 Alembic batch mode，禁止在无历史保留策略时删除旧列。

## 8. Error And Concurrency Contract

- 数据库锁超时 -> `DATABASE_BUSY`，中文建议稍后重试；不无限重试。
- expected revision 不匹配 -> `STALE_REVISION`，响应带 current revision、submitted revision 和字段 diff。
- 幂等键同 hash -> 返回原结果；不同 hash -> `IDEMPOTENCY_CONFLICT`。
- 过期/错误租约提交 -> `LEASE_LOST`，丢弃该 worker 结果，不写 JobStep 完成。
- payload hash 或 Pydantic 还原失败 -> `PERSISTED_CONTRACT_INVALID`，阻止发布，不返回空对象。

## 9. Rollout And Rollback

- Phase 2 只新增 `/api/v2` 与独立数据根，不切换 legacy 默认入口。
- 先完成 schema/仓储，再完成 Job 状态机，再接 API/SSE；每批都可独立回滚。
- rollback 删除的是未投入真实使用的 V2 数据目录或降级 migration；绝不触碰 legacy `projects/`。
- Phase 2 通过后，Phase 3 才让方案解构写入这些仓储。

## 10. Key Trade-offs

- 选择“规范化关键列 + canonical JSON”而非把所有嵌套 Pydantic 字段完全摊平：保持合同往返和证据完整，同时让关键范围/版本/状态可索引、可外键约束。
- 选择同步 SQLAlchemy 而非新增异步驱动：SQLite 仍是单 writer，短事务和后台 worker 解耦比异步 ORM 更直接；减少两套会话/迁移语义。
- 选择数据库事件序列而非进程内消息总线：本机吞吐足够，断线恢复、审计和测试更确定。
