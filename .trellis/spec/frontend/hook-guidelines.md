# Hook Guidelines

> Hook 负责可复用的交互和数据协调，不拥有临床判定逻辑。

## Custom Hook Patterns

- Hook 以 `use` 开头，名称表达任务，例如 `useSubjectEpisode`、`useEvidenceNavigation`。
- 每个 Hook 处理一个边界：读取、mutation、URL 选择同步、Job 订阅或局部交互。
- Hook 返回稳定、命名清楚的领域状态和动作；组件不解析后端错误信封。
- 订阅、定时器、AbortController 和对象 URL 必须在 cleanup 中释放。

## Data Fetching

- 所有请求通过唯一的类型化 API repository；Phase 1 的 stub 与真实 API 实现同一接口。
- 不在组件 `useEffect` 中散落裸 `fetch`，不让不同面板各自请求同一事实并产生漂移。
- 请求切换项目、受试者或阶段时取消过期请求；响应必须校验 revision，拒绝覆盖更新数据。
- Job 使用事件/轮询适配器暴露进度，组件不解析服务端日志。
- 具体缓存库在 Phase 0.5 选型后固定；在此之前保持 repository 接口与库无关。

## Naming Conventions

- 查询：`useProjectList`、`usePatientProfile`。
- 动作：`useUploadEvidence`、`useOverrideDecision`。
- 选择和导航：`useReviewSelection`、`useEvidenceNavigation`。
- 返回字段使用 `data`、`status`、`errorMessage`、`retry` 等稳定语义，错误文案为自然中文。

## Common Mistakes

- 把 rollup、AND/OR 或“证据不足”推导写在 Hook 中。
- 通过依赖数组遗漏或禁用 lint 规避无限请求。
- 切换受试者后让旧请求覆盖当前页面。
- 在多个 Hook 中复制状态映射和 API 错误翻译。
- 用列表索引作为选择 ID，排序筛选后选中错误受试者。
