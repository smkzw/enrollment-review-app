# 实施：SQLite领域层与持久任务

## 1. 基础设施与初始迁移

- [x] 新增 V2 数据目录配置、SQLite 运行时版本门禁和 legacy 写边界测试。
- [x] 建立 SQLAlchemy Base、命名约定、Engine/Session 工厂和连接 PRAGMA。
- [x] 建立 Alembic 配置、初始 migration、备份/完整性校验/恢复命令。
- [x] 测试空库 upgrade/downgrade/upgrade、迁移失败保留原库和备份。

## 2. 领域表与仓储

- [x] 实现核心 ORM 表、外键、唯一约束、索引、payload JSON/hash 和 association tables。
- [x] 实现 Pydantic contract <-> ORM codec，拒绝 hash 或 schema 不一致。
- [x] 实现 Project/Protocol/Rule、Subject/Episode、Evidence、Review/Action、Agent/Gate 仓储。
- [x] 用三个 Phase 0.5 fixture 做完整 round-trip、跨 scope 反向测试和 N+1 查询检查。

## 3. 幂等、乐观并发与 stale

- [x] 实现 idempotency repository 和同键同/异 payload 行为。
- [x] 实现 expected revision 更新、字段 diff 和两会话冲突测试。
- [x] 实现 entity staleness 的打开、影响范围查询和 ReviewRun 精确关闭。

## 4. 持久 Job 工作流

- [x] 扩展 Job/Step/Checkpoint/Event 合同和状态转换纯函数。
- [x] 实现持久 JobStore、单调事件序号、租约 claim/heartbeat/generation。
- [x] 实现步骤事务、重试退避、失败范围、取消安全边界和启动恢复。
- [x] 故障注入：步骤提交前/后终止、租约过期、重复 worker、重启恢复、最终失败。

## 5. V2 API 与 SSE

- [x] 新增 Job 创建/状态/事件订阅/取消/重试 API；路由只调用 service/workflow。
- [x] SSE 仅订阅持久事件，支持 `after_seq`，断开不改变 Job。
- [x] 错误信封提供自然中文问题、影响和恢复动作；不泄露实现术语。
- [x] API 集成测试覆盖断线重连、无重复事件、错误租约与 revision 冲突。

## 6. 验收与收口

- [x] 运行后端全套、迁移、故障注入、API/SSE、启动恢复和 legacy 树哈希测试。
- [x] 运行前端既有测试/构建/Playwright，确认 Phase 1 壳未回归。
- [x] 更新 `.trellis/spec/backend` 的数据库、工作流、迁移和错误合同。
- [x] 独立 checker 在新鲜上下文复核数据完整性、恢复、幂等和并发；Codex 裁决。
- [x] 清理临时数据库、备份、测试 stdout 和缓存，保留最小恢复证据。

## Rollback Points

- 基础设施提交：尚无业务表，可删除独立测试库并回退配置。
- 初始 migration 提交：用 Alembic downgrade 和已验证 backup 恢复。
- Job 提交：API 尚未切换 legacy，回退 `/api/v2/jobs` 不影响旧流程。
- 任一阶段发现 scope/版本/历史被覆盖，停止后续实现并回到合同层修复，不给单表或单 fixture 打补丁。

## Validation Commands

```bash
uv lock --check
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/pytest -q tests/v2/storage tests/v2/workflow tests/v2/api
PYTHONPATH=. .venv/bin/pytest -q
cd frontend && npm test && npm run build && npm run e2e
git diff --check
```
