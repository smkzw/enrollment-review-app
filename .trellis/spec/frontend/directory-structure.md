# Directory Structure

> V2 前端按用户任务和临床功能域组织，不按页面堆放所有逻辑。

## Directory Layout

```text
frontend/
├── src/
│   ├── app/                 # 路由、壳层、全局错误边界、启动配置
│   ├── features/
│   │   ├── today/           # 今日工作与待办
│   │   ├── projects/        # 项目和方案版本
│   │   ├── protocols/       # 方案解构与规则工作台
│   │   ├── subjects/        # 受试者资料与上传
│   │   ├── eligibility/     # 分阶段入排审核
│   │   ├── actions/         # 补充资料、研究者判定和 override
│   │   ├── jobs/            # OCR/审核任务状态与恢复
│   │   ├── reports/         # 个例、中心、项目报告
│   │   └── help/            # 流程化帮助
│   ├── shared/
│   │   ├── api/             # 唯一的类型化 API/stub 适配层
│   │   ├── domain/          # 前端领域类型和显示映射
│   │   ├── ui/              # 无业务含义的基础组件
│   │   ├── design-system/   # token、排版、状态颜色和响应式规则
│   │   ├── utils/           # 纯函数
│   │   └── test/            # fixtures 与测试工具
│   ├── assets/
│   └── main.tsx
├── tests/
└── dist/
```

## Module Organization

- 每个 feature 可包含 `components/`、`hooks/`、`api/`、`model/`、`routes/`、`tests/`，仅创建实际需要的目录。
- 功能域之间通过 `shared/domain` 契约或公开入口协作，禁止跨域深层导入内部文件。
- API 原始响应只在 `shared/api` 或 feature API 适配器中出现，组件接收可显示的领域模型。
- 设计 token 集中管理；页面不得定义另一套颜色、间距和状态词。

## Naming Conventions

- 组件文件使用 `PascalCase.tsx`，Hook 使用 `useXxx.ts`，纯函数和适配器使用 `camelCase.ts`。
- 路由、API 字段和持久 ID 使用英文稳定标识；所有可见文字使用自然中文资源，不把变量名直接展示。
- 状态显示词统一从领域映射获取，例如 `evidence_missing -> 证据不足`。

## Reference Surfaces

- 产品和流程基座：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`。
- 分阶段实现与验收：`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
- Legacy 行为参照：`static/index.html`，只读使用，不作为 V2 组件模板。
