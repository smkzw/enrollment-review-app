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
