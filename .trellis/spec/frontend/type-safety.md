# Type Safety

> TypeScript 类型必须与 V2 契约一致，并在运行时拒绝不可信的 API/Agent 数据。

## Overview

- 开启 TypeScript `strict`，领域状态使用判别联合和品牌 ID，避免字符串混用。
- OpenAPI/JSON Schema 是跨边界契约；生成类型或等价同步机制在 Phase 0.5 确定。
- 编译期类型不能替代运行时校验。API、stub、导入文件和 Agent 候选都视为不可信输入。

## Type Organization

- 跨功能域类型放 `shared/domain`，例如 `ProjectId`、`ReviewEpisodeStatus`、`EvidenceLocator`。
- API wire 类型放 `shared/api`，通过适配器转换为前端领域模型。
- 仅组件使用的 Props 和显示类型与组件同文件或同目录。
- 领域枚举以 schema 值为准，中文显示通过穷尽映射生成，不把中文文案当持久值。

## Validation

- Phase 0.5 选择支持 JSON Schema/OpenAPI、维护活跃且许可证合适的运行时校验方案。
- 校验失败进入统一错误边界，显示中文恢复动作并记录 correlation ID。
- 日期、单位、数值范围、EvidenceSpan locator 和规则表达式必须有专门校验。
- Stub fixtures 也必须通过同一契约，防止原型与真实 API 偏离。
- 多个布尔字段若表达可同时成立的独立事实，运行时校验必须复现后端不变量，不得因为界面想要单选状态而擅自改成“恰好一个为真”。

## Common Patterns

```ts
type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T; revision: number }
  | { status: "error"; message: string; retryable: boolean };
```

- 对状态映射使用穷尽 `switch` 和 `never` 检查。
- 使用类型守卫处理联合类型；ID 不跨实体复用。
- 可空值必须区分“未提供”“不适用”“未知”和真实空集合。

## Forbidden Patterns

- `any`、无依据的 `as`、非空断言 `!` 和 `// @ts-ignore`。
- 用字符串包含关系判断审核状态或规则逻辑。
- 把 API 原始对象直接传遍组件树。
- 用 `Date` 隐式解析无时区或不完整临床日期。
- 省略未知状态的 `default` 处理后静默显示为通过。

## Patient Profile 事件证据合同

事件视图必须显式包含：

```ts
type EventEvidenceRelation =
  | "direct"
  | "review_basis"
  | "related_rule"
  | "unavailable";

type ProfileEventEvidenceTarget = {
  evidenceRelation: EventEvidenceRelation;
  evidenceSpanId: EvidenceSpanId | null;
  evidenceTargetComponentId: RuleComponentId | null;
};
```

- `direct` 只能来自事件事实自身的 EvidenceSpan。
- `review_basis` 和 `related_rule` 必须使用相应中文动作，不得显示为事件“原始依据”。
- `unavailable` 不得生成可点击入口。
- `evidenceSpanId` 与 `evidenceTargetComponentId` 同时存在时，二者必须属于同一 FinalAssessment；不能依赖工作台收到冲突参数后静默决定优先级。
