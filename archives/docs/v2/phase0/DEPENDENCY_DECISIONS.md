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

版本来自 2026-08-12 的 PyPI JSON；许可证和维护状态同时核对官方项目文档/仓库。`pyproject.toml` 与 `uv.lock` 固定完整解析结果。所有组件仅在本机运行；除用户主动配置的模型 API 外，这些依赖不发送临床数据。移除方式是删除对应依赖并回退 Alembic 迁移/适配层提交，legacy 运行时不受影响。

**替代方案：** SQLite 标准库直写会减少依赖，但迁移、关系映射和 revision 查询需要大量自研；SQLModel 增加对 SQLAlchemy/Pydantic 的耦合而无本项目必需收益。因此选择 SQLAlchemy + Alembic。FastAPI/Uvicorn/Pydantic 延续已验证栈，避免为重构同时更换 HTTP 框架。

### 前端

| 依赖 | 固定版本 | 许可证 | 用途与依据 |
|---|---:|---|---|
| React / React DOM | 19.2.8 | MIT | 产品 SPA；使用 Latest 稳定通道，[官方版本策略](https://react.dev/community/versioning-policy) |
| Vite | 8.2.1 | MIT | 开发/构建；Node 要求 `^20.19 || >=22.12`，[官方发布策略](https://vite.dev/releases) |
| TypeScript | 7.0.2 | Apache-2.0 | strict 类型检查 |
| `@vitejs/plugin-react` | 6.0.5 | MIT | React/Vite 官方插件 |
| TanStack React Table | 9.1.2 | MIT | 逐列排序、筛选、选择和受控状态；[官方说明](https://tanstack.com/table/latest) |
| Lucide React | 1.31.0 | ISC；部分 Feather 衍生图标为 MIT | 统一使用熟悉图标并保留中文可访问名称；[官方许可证](https://github.com/lucide-icons/lucide/blob/main/LICENSE) |
| React 类型定义 | 19.2.18 / 19.2.4 | MIT | React/DOM 类型 |

版本和许可证元数据通过 2026-08-12 本机 npm 配置的 `registry.npmmirror.com` 获取，随后以 React、Vite、TanStack 和 TypeScript 官方文档/仓库交叉核对。`frontend/package-lock.json` 因本机 registry 配置记录 npmmirror 下载地址并固定传递依赖；切换 registry 后必须重新生成和复核锁文件，不能把镜像地址误称为官方 npm registry。当前 Node 22.22.3、npm 10.9.8 满足要求。

**维护与适配：** React 19.2 是官方 Latest 稳定线；Vite 8 是官方支持线；TanStack Table 是活跃维护的无头表格引擎，允许自有临床视觉和受控状态；TypeScript 7 提供 strict 类型。以上依赖仅在开发/本机构建下载代码，预构建前端在桌面运行时不访问包 registry，也不发送临床数据。

**替代方案：** 原生 DOM 或继续扩展单文件 SPA 会放大状态和可测试性问题；完整 UI/数据网格组件库会限制响应式临床工作台。React + 无头 TanStack Table 保留布局和交互控制。若移除 TanStack Table，可由自有列表组件替代而不改变 API 合同；若回退构建栈，则恢复上一锁文件和预构建产物。

### 前端测试依赖

| 测试依赖 | 固定版本 | 许可证 | 边界决定 |
|---|---:|---|---|
| Vitest | 4.1.10 | MIT | 单元和组件测试；只在开发阶段运行 |
| Testing Library（DOM / jest-dom / React / user-event） | 10.4.1 / 7.0.1 / 16.3.2 / 14.6.4 | MIT | 以用户可见行为和可访问名称测试交互 |
| jsdom | 30.0.1 | MIT | 单元测试浏览器环境 |
| Playwright Test | 1.62.1 | Apache-2.0 | 真实浏览器、多视口、键盘路径与截图验收；[官方仓库](https://github.com/microsoft/playwright) |
| axe-core / axe Playwright | 4.13.0 / 4.13.0 | MPL-2.0 | 仅在 Playwright 测试中检查严重可访问性问题；[官方许可证](https://github.com/dequelabs/axe-core/blob/develop/LICENSE) |
| Node 类型定义 | 26.2.0 | MIT | 测试配置与构建脚本类型 |

axe-core 只存在于 `devDependencies`，不会进入 Vite 的预构建产品代码，也不会随本地医学监查员入口启动。MPL-2.0 允许将其作为较大作品的一部分使用，但若未来分发测试工具或 axe-core 本身，必须保留许可证通知，并按许可证提供对应源代码获取方式；本项目不修改 axe-core 源码。回滚方式为删除 axe 两个开发依赖及 `frontend/e2e/axe.spec.ts`，不影响其余浏览器用例。选择 axe 是因为它能稳定自动发现严重的可访问名称、焦点和结构问题；它不能替代键盘实测与视觉复核。

## 未采纳

- 不引入完整 UI 组件库：自有临床视觉系统、响应式和可访问性要求更适合小型基础组件层。
- 不在 Phase 0 预选全局状态库、请求缓存库或运行时 JSON Schema 库：需先由 Phase 0.5 合同和原型复杂度证明必要性。
- Trellis 0.6.14（AGPL-3.0-only）仅为开发管理工具，不打包进产品运行时或用户分发物。

## 开发与 legacy 回归依赖

为保证默认 `pytest` 不静默绕过旧系统，V2 开发组额外固定 `pytest 9.0.2`、`httpx 0.28.1`、`openai 2.37.0`、`PyMuPDF 1.26.4`、`python-docx 1.2.0`、`openpyxl 3.1.5`、`python-multipart 0.0.20` 和 `requests 2.32.4`。它们用于测试收集、旧适配器导入、方案/Excel 夹具或本地 API 测试，不改变 V2 领域边界。默认测试入口必须同时收集 `tests/test_phase_workflow.py` 与 `tests/v2/`。

| 开发依赖 | 许可证 | 分发与边界决定 |
|---|---|---|
| pytest 9.0.2 | MIT | 仅测试，不进入预构建产品 |
| httpx 0.28.1 | BSD-3-Clause | legacy API 测试依赖；V2 若作为运行时使用需在相应阶段重新登记 |
| openai 2.37.0 | Apache-2.0 | 仅用于导入 legacy 模型适配器；不代表 V2 已选定模型 SDK |
| PyMuPDF 1.26.4 | AGPL-3.0 或 Artifex 商业许可 | **仅本机 legacy 回归测试**，不进入 V2 产品运行时或分发物；Phase 4 重新评估许可证更适合的 PDF 解析器。若未来必须分发 PyMuPDF，则先满足 AGPL 源码义务或另购商业许可 |
| python-docx 1.2.0 | MIT | 读取 legacy 方案夹具；未来方案解析层可复评 |
| openpyxl 3.1.5 | MIT | 读取 legacy 人工对照 Excel 夹具 |
| python-multipart 0.0.20 | Apache-2.0 | FastAPI 上传测试 |
| requests 2.32.4 | Apache-2.0 | legacy 批处理脚本导入测试 |

开发依赖通过 `dependency-groups.dev` 隔离。桌面产品安装/打包必须排除 dev group；删除这些依赖会失去 legacy 回归收集能力，因此移除前先以等价 fixture 或替代解析器覆盖相同测试。PyMuPDF 的双许可来自其[官方许可说明](https://pymupdf.readthedocs.io/en/latest/about.html)，不能按普通宽松许可处理。

## 更新与回滚

- 依赖只通过锁文件更新；一次升级一个依赖族并重跑合同、构建、E2E 和视觉检查。
- 若新版本失败，回退 `pyproject.toml`/`uv.lock` 或 `package.json`/`package-lock.json` 的上一个已验证提交。
- 桌面启动只运行预构建前端和 Python 服务，不要求医学监查员安装或操作 Node。
