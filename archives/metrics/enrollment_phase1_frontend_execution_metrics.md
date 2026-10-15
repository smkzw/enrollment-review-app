# Execution Metrics: enrollment_phase1_frontend

Date: 2026-08-13

| Role | Provider | Model | Status | Runner duration | Result |
|---|---|---|---|---:|---|
| `worker_01` | `cms-smk` | `deepseek-v4-flash` | completed | 15m 52s | stub API、ViewModel、fixture 与基础测试完成 |
| `worker_02` | `cms-smk` | `deepseek-v4-flash` | completed | 5m 45s（含同会话修订） | 全局壳、今日工作、项目看板与图标完成 |
| `worker_03` | `cms-smk` | `deepseek-v4-flash` | completed | 约 63m 56s（含同会话视觉修订） | Profile、工作台、行动/任务/报告/帮助和 E2E 完成 |
| `complex_manager_cursor` | `cursor-cli` | `auto` | completed | 2m 19s | 依赖与边界复核，关闭残余“原型”显示 |

## Verification Burden

- 工程汇总后由 Codex 修订 3 个共享根因，再由独立 Kimi K3 做首轮和同会话复核。
- 最终证据：137 项单元/组件测试、构建、153 项 Playwright 通过、27 项视口专属跳过、0 失败、九页 axe 无 serious/critical、38 张截图。
- fixture 四份副本与合同来源保持字节一致；前端只消费 `fixture/v1` 和 stub API，不读取旧 Markdown 或 legacy SPA 状态。

## Routing Decision

执行按既定 finite/long-horizon code 路线拆成三个有界工作项，并由 Cursor CLI 管理者统一复核。所有 worker 保持工具可用；只有具体缺陷触发同会话修订，没有因等待而重派。视觉最终验收另用独立 Kimi K3 路线，符合构建者与验收者上下文隔离。
