# Metrics: enrollment_phase1_frontend

Date: 2026-08-13

| Field | Value |
|---|---|
| Task type | `long_horizon_code` |
| Risk | `medium`（独立视觉验收按 high） |
| Execution | 3 个 DeepSeek V4 Flash worker + Cursor CLI manager |
| Visual verifier | Kimi K3-256K high，同一会话 2 轮 |
| Unit/component tests | 137 passed |
| Browser tests | 153 passed / 27 viewport skips / 0 failed |
| Screenshots | 38 |
| Result | Phase 1 完成，等待 Phase 1.5 用户验收 |

## Verification Burden

真实界面涉及九个一级页面、三种桌面宽度、390 窄屏、键盘、证据深链、父子规则、任务状态和 150%/200% 等效缩放，因此采用自动化矩阵、独立视觉挑战和 Codex 逐图复核三层证据。

## Routing Decision

构建与视觉验收分离。执行 worker 不关闭自己的任务；Cursor 只做工程管理；Kimi K3 只读独立审查；Codex 根据真实浏览器、测试和源码作最终阶段判断。没有使用 Qwen 3.8。
