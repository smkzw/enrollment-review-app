# Frontend Development Guidelines

> V2 前端服务于不熟悉电脑和 AI 的资深医学监查员，必须使用自然中文、临床任务导向和可追溯交互。

## Product Contract

- 登录功能删除，本机启动后直接进入“今日工作”。
- Patient Profile 首屏只突出入排相关、异常、临界和趋势变化信息；完整时间轴按需展开。
- 用户可在规则判断、OCR 文本和原始文件之间快速往返，证据定位目标不超过 3 次操作。
- 前端不展示 Agent、schema、pipeline、provider、日志或内部状态机术语。
- 所有结论明确区分审核阶段，以及“证据不足”“需研究者判定”“溯源提醒”“后续阶段复核”。

## Guidelines Index

| Guide | Description | Status |
|---|---|---|
| [Directory Structure](./directory-structure.md) | React 功能域和共享模块 | 已定义 |
| [Component Guidelines](./component-guidelines.md) | 临床工作台组件、布局和无障碍 | 已定义 |
| [Hook Guidelines](./hook-guidelines.md) | 数据访问、任务订阅和选择同步 | 已定义 |
| [State Management](./state-management.md) | 服务端、URL、本地状态边界 | 已定义 |
| [Quality Guidelines](./quality-guidelines.md) | 视觉、交互和浏览器验收 | 已定义 |
| [Type Safety](./type-safety.md) | TypeScript 与运行时契约 | 已定义 |
| [本地界面试用启动](./local-trial-launcher.md) | 预构建页面、服务归属、桌面入口和验收矩阵 | 已定义 |

## Current And Target State

- `static/index.html` 是 legacy 只读参照，不继续堆叠 V2 功能。
- V2 使用 React + TypeScript + Vite，Phase 1 先连接契约一致的 stub API，再切换真实 API。
- 具体运行时校验库、表格库和数据请求库必须在 Phase 0.5 完成许可、维护和兼容性决策后锁定。
