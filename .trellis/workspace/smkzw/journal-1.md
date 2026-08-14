# Journal - smkzw (Part 1)

> AI development session journal
> Started: 2026-08-12

---

## 2026-08-12 · V2 Phase 0 启动

- 冻结代码基线：`a02b833`；工作分支：`codex/v2-phase0-foundation`。
- 完成 Trellis 初始化、工程规范、V2 总任务和 Phase 0 子任务；Qwen 3.8 已按用户要求从本任务会商范围移除。
- legacy 实际运行时为 `/usr/bin/python3`（Python 3.9.6），共收集 131 项：130 项通过、1 项跳过；误用另一套缺 FastAPI 的 Python 曾造成假失败。
- V2 选用独立 CPython 3.12.13 + `uv`，避免 Alembic 新版本与 Python 3.9 不兼容；前端 Node 22.22.3。
- 固定 React/Vite/TanStack Table/SQLAlchemy/Alembic 等基础依赖并生成锁文件。
- 建立 V2 目录、写边界和依赖方向测试；首次候选为 4 项 V2 测试，独立 checker 要求进一步补强默认测试门禁与真实写入路径。
- 安全清理仅处理 `.DS_Store`、源码字节码缓存和旧 `.playwright-cli` 临时缓存；`projects/`、`output/`、logs、执行/会商证据全部保留。
- 当前待办：合并独立 Worker 的 baseline/regression 索引，独立 checker 核验 Phase 0，完成退出门槛后进入 Phase 0.5。

### 独立检查与修订

- 首次候选 `97dbadd` 被独立 checker 拒绝：默认 pytest 仅收集 V2、写边界测试未经过真实 writer、依赖来源记录不完整、基线文档时态过期。
- 修订默认 pytest 为完整 `tests/`，补足 legacy 测试开发依赖；统一入口现为 136 通过、1 跳过，legacy 单独仍为 130 通过、1 跳过。
- 新增原子写入路径、V2/legacy root 重叠拒绝、硬链接/符号链接拒绝和 legacy 快照不变测试。
- 依赖记录明确本机 npm 锁文件使用 npmmirror，官方文档/仓库仅作为交叉核验；补充维护、替代、数据外传和移除说明。
- 原 checker 首次复验已确认默认测试和写边界问题关闭；剩余 PyMuPDF 许可/分发边界及文档时态修订后，仍需最终复验，未提前进入 Phase 0.5。

### Phase 0 接受

- 最终候选提交：`8036d6a`（包含 `6fa901d` 写入/测试修订）。
- 原 checker 第二次定向复验无阻断 findings，明确结论为“Phase 0 候选可接受”。
- Codex 复核锚点：默认测试 136 通过、1 跳过；legacy 单独 130 通过、1 跳过；锁文件可复现；服务 8901 健康；工作树干净。
- Phase 0 可归档。下一步只进入 Phase 0.5 合同设计，不跨越到 Phase 2 数据层。


## Session 1: Phase 1.5 正式界面试用任务包就绪

**Date**: 2026-08-13
**Task**: Phase 1.5 正式界面试用任务包就绪
**Branch**: `codex/v2-phase0-foundation`

### Summary

补齐14项独立可执行任务、记录人员指南和批次汇总；增加统一界面试用复位与版本；修正显示码、期别及缩放证据口径；全量测试与独立复核通过，继续停在正式用户试用批准门。

### Git Commits

| Hash | Message |
|------|---------|
| `e598c9e` | (see git log) |
| `b6580e9` | (see git log) |

### Status

[OK] **Completed**

## Session 2: 补齐正式界面试用桌面入口与窄屏复位验收

**Date**: 2026-08-13
**Task**: 补齐正式界面试用桌面入口与窄屏复位验收
**Branch**: `codex/v2-phase0-foundation`

### Summary

新增V2预构建页面一键启动/停止入口与服务归属合同；完成390像素复位交互、状态边界、视觉证据和Finder实点；门状态保持awaiting_user_uat。

### Git Commits

| Hash | Message |
|------|---------|
| `756004d` | (see git log) |

### Status

[OK] **Completed**


## Session 3: Phase 1.5 多模型医学监查员验收与根因修订

**Date**: 2026-08-14
**Task**: Phase 1.5 多模型医学监查员验收与根因修订
**Branch**: `codex/v2-phase0-foundation`

### Summary

完成真实浏览器独立审评、共享根因修订、事件证据归属合同、全量确定性与视觉验收；Phase 1.5 通过并将父任务推进到 Phase 2 ready。

### Git Commits

| Hash | Message |
|------|---------|
| `4c89da8` | (see git log) |

### Status

[OK] **Completed**


## Session 4: Phase 2 最终规划 checkpoint

**Date**: 2026-08-14
**Task**: Phase 2 SQLite领域层与持久任务规划
**Branch**: `codex/v2-phase0-foundation`

### Summary

已创建 Trellis 子任务 `08-14-phase2-sqlite-domain-jobs` 并完成 PRD、设计、实施清单及执行/检查上下文清单。规划确定独立 `data_v2/`、同步 SQLAlchemy 2、SQLite WAL、Alembic 一致备份、不可变领域历史、持久任务、租约恢复、幂等、乐观并发和结构化过期范围；不提前接入真实方案解析、OCR 或医学审核。

### Status

[WAIT] **Planning approved summary presented; explicit user approval required before `task.py start`**


## Session 5: Phase 2 worker_01 存储基础设施

**Date**: 2026-08-14
**Task**: Phase 2 SQLite领域层与持久任务（worker_01：SQLite 配置、SQLAlchemy 基础设施、Alembic 迁移、备份恢复与写边界测试）
**Branch**: `codex/v2-phase0-foundation`

### Summary

完成 V2 持久化基础设施：`ENROLLMENT_V2_DATA_DIR` 数据根配置与 SQLite >=3.51.3 运行时门禁（`app/storage/config.py`）；SQLAlchemy Base/命名约定/Engine/Session 工厂与连接 PRAGMA 合同（WAL、foreign_keys、synchronous=FULL、busy_timeout=10000，`app/storage/db.py`）；Alembic 配置与空基线迁移 `0001`（`alembic.ini` + `app/storage/migrations/`，batch mode）；迁移编排器（`app/storage/migrate.py`：flock 迁移锁、sqlite3 backup API 一致备份 + integrity_check + 清单、upgrade/downgrade/restore、schema/metadata 一致性校验、`upgrade_or_fail` 启动入口）与运维 CLI（`python -m app.storage.cli`）。

验证：`tests/v2/storage` 37 项新测试通过（升级/降级/再升级、失败注入保留原库、恢复、PRAGMA 实测、版本门禁、写边界与 legacy `projects/` 树哈希不变性）；全套 312 passed / 1 skipped；真实数据根 `data_v2/`（已 gitignore）完成 CLI upgrade→verify→downgrade→upgrade→restore→upgrade 闭环，legacy 树 8797 项哈希一致。

### Status

[OK] **Completed**（worker_01 切片完成；领域 ORM/仓储与 Job 工作流留待 worker_02/03）

## Session 6: Phase 2 worker_02 领域ORM、合同编解码、仓储、幂等、乐观并发与过期范围

**Date**: 2026-08-14
**Task**: Phase 2 SQLite领域层与持久任务（worker_02：领域 ORM、合同编解码、仓储、幂等、乐观并发与过期范围）
**Branch**: `codex/v2-phase0-foundation`

### Summary

完成 worker_02 切片：`app/storage/models.py` 51 张表（5 个可变根 revision+version_id 乐观并发；协议/规则/证据/审核/Agent/Gate/Job 追加写记录 canonical JSON payload+hash；9 张有序 association table；`entity_staleness` 与 `idempotency_records`；episode<->snapshot 双向 DEFERRED 外键解环）；`app/storage/codecs.py`（canonical 编解码、哈希校验、列/payload 镜像交叉核对，`PersistedContractInvalid` 阻止发布）；`app/storage/concurrency.py`（`StaleRevisionError` 中文差异信封 + mapper versioning 兜底）；`app/storage/idempotency.py`（同键同哈希复用、异哈希冲突）；`app/storage/staleness.py`（开/查/按 ReviewRun 覆盖范围精确关闭）；`app/storage/repositories.py`（追加写仓储骨架 + Project/Subject/Episode/Expectation/Action 可变仓储 + 规则集树/协议权威链组合写入 + 跨 scope 服务校验 + Job 存储原语 + `persist_fixture` 三 fixture 播种）；迁移 `0002_domain_schema.py`（由 metadata 生成后冻结，upgrade/downgrade，schema↔metadata 一致）。

验证：`tests/v2/storage` 106 项新测试（三 fixture 完整往返、跨 scope 反向拒绝、N+1 常量查询、编解码篡改、幂等、两会话 revision 冲突、stale 精确关闭、Job 事件单调序号/after_seq）；全套 387 passed / 1 skipped；`git diff --check`、`uv lock --check` 通过；真实数据根升级至 head `0002` 且 CLI verify 通过；legacy `projects/` 8797 项哈希一致。

### Status

[OK] **Completed**（worker_02 切片完成；持久 Job 状态机/租约恢复/取消重试/V2 API/SSE 留待 worker_03）


## Session 4: Phase 2 SQLite领域层与持久任务完成

**Date**: 2026-08-14
**Task**: Phase 2 SQLite领域层与持久任务完成
**Branch**: `codex/v2-phase0-foundation`

### Summary

完成独立V2 SQLite领域持久化、Alembic备份恢复、幂等与乐观并发、stale、持久Job/Checkpoint/租约恢复、中文V2 API与SSE；多模型审评后修复并发幂等、终败事件、恢复进度、退避保护和字段定位；后端467项、前端207项、Playwright283项通过，Phase 2归档。

### Git Commits

| Hash | Message |
|------|---------|
| `02b2936` | (see git log) |
| `07f8b45` | (see git log) |
| `9edc7b3` | (see git log) |

### Status

[OK] **Completed**
