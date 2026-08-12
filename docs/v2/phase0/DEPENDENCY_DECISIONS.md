# Phase 0 开源依赖决策

**核验日期：** 2026-08-12

**范围：** V2 基础运行时；业务库和交互库在 Phase 0.5 按实际合同另行评估。

## 决策

### Python 运行时

- **选择：** CPython 3.12.13，使用本机 `uv 0.11.7` 创建独立 `.venv`。
- **原因：** 本机已安装；支持 SQLAlchemy/Alembic 当前版本；较 3.13 对医学文档/OCR 生态更稳妥。
- **拒绝：** legacy 的 `/usr/bin/python3` 实际为 Xcode Python 3.9.6。Alembic 当前版本要求 Python >=3.10，继续共用会锁死迁移层。
- **隔离：** legacy 启动脚本保持 `/usr/bin/python3`；V2 只使用 `uv run` 或项目 `.venv`。

### 后端

| 依赖 | 固定版本 | 许可证 | 用途与依据 |
|---|---:|---|---|
| FastAPI | 0.128.8 | MIT | 保留已验证 API 框架，V2 仅重组领域边界 |
| Uvicorn | 0.39.0 | BSD-3-Clause | 本地 ASGI 服务 |
| Pydantic | 2.13.3 | MIT | API/领域边界校验；继续使用当前已验证版本 |
| SQLAlchemy | 2.0.52 | MIT | SQLite ORM、事务和乐观 revision；[官方文档](https://docs.sqlalchemy.org/en/20/) |
| Alembic | 1.19.1 | MIT | 版本化数据库迁移；[官方文档](https://alembic.sqlalchemy.org/en/latest/) |

版本来自 2026-08-12 的 PyPI JSON；`pyproject.toml` 与 `uv.lock` 固定完整解析结果。

### 前端

| 依赖 | 固定版本 | 许可证 | 用途与依据 |
|---|---:|---|---|
| React / React DOM | 19.2.8 | MIT | 产品 SPA；使用 Latest 稳定通道，[官方版本策略](https://react.dev/community/versioning-policy) |
| Vite | 8.2.1 | MIT | 开发/构建；Node 要求 `^20.19 || >=22.12`，[官方发布策略](https://vite.dev/releases) |
| TypeScript | 7.0.2 | Apache-2.0 | strict 类型检查 |
| `@vitejs/plugin-react` | 6.0.5 | MIT | React/Vite 官方插件 |
| TanStack React Table | 9.1.2 | MIT | 逐列排序、筛选、选择和受控状态；[官方说明](https://tanstack.com/table/latest) |
| React 类型定义 | 19.2.18 / 19.2.4 | MIT | React/DOM 类型 |

版本和许可证来自 2026-08-12 npm registry；`frontend/package-lock.json` 固定传递依赖。当前 Node 22.22.3、npm 10.9.8 满足要求。

## 未采纳

- 不引入完整 UI 组件库：自有临床视觉系统、响应式和可访问性要求更适合小型基础组件层。
- 不在 Phase 0 预选全局状态库、请求缓存库或运行时 JSON Schema 库：需先由 Phase 0.5 合同和原型复杂度证明必要性。
- Trellis 0.6.14（AGPL-3.0-only）仅为开发管理工具，不打包进产品运行时或用户分发物。

## 更新与回滚

- 依赖只通过锁文件更新；一次升级一个依赖族并重跑合同、构建、E2E 和视觉检查。
- 若新版本失败，回退 `pyproject.toml`/`uv.lock` 或 `package.json`/`package-lock.json` 的上一个已验证提交。
- 桌面启动只运行预构建前端和 Python 服务，不要求医学监查员安装或操作 Node。
