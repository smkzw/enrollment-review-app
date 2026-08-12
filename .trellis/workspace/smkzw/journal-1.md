# Journal - smkzw (Part 1)

> AI development session journal
> Started: 2026-08-12

---

## 2026-08-12 · V2 Phase 0 启动

- 冻结代码基线：`a02b833`；工作分支：`codex/v2-phase0-foundation`。
- 完成 Trellis 初始化、工程规范、V2 总任务和 Phase 0 子任务；Qwen 3.8 已按用户要求从本任务会商范围移除。
- legacy 实际运行时为 `/usr/bin/python3`（Python 3.9.6），131 项测试通过、1 项跳过；误用另一套缺 FastAPI 的 Python 曾造成假失败。
- V2 选用独立 CPython 3.12.13 + `uv`，避免 Alembic 新版本与 Python 3.9 不兼容；前端 Node 22.22.3。
- 固定 React/Vite/TanStack Table/SQLAlchemy/Alembic 等基础依赖并生成锁文件。
- 建立 V2 目录、写边界和依赖方向测试；V2 3 项测试通过。
- 安全清理仅处理 `.DS_Store`、源码字节码缓存和旧 `.playwright-cli` 临时缓存；`projects/`、`output/`、logs、执行/会商证据全部保留。
- 当前待办：合并独立 Worker 的 baseline/regression 索引，独立 checker 核验 Phase 0，完成退出门槛后进入 Phase 0.5。
