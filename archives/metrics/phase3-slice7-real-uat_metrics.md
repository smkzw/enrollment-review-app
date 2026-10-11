# Metrics: phase3-slice7-real-uat

Date: 2026-08-18

| Field | Value |
|---|---|
| Task type | `long_horizon_code` |
| Risk | `high` |
| Semantic route | DeepSeek V4 Flash `max`（方案解构真实调用） |
| MG result | III 期 IN 7 / EX 16 / 必做项 41；1 个未命名时间锚点阻断 |
| D001 result | II 期 IN 6 / EX 30 / 必做项 50；正式发布第 1 版 |
| Backend | `765 passed, 53 warnings, 2 subtests passed` |
| Frontend unit | `267 passed` |
| Frontend build | Passed；既存入口包体积提示 |
| Real HTTP browser | 1920 / 2560 / 3840：`3 passed` |
| Result | Slice 7 accepted; paused before Slice 8 |

## Verification Burden

- 两份原始 DOCX 只读哈希、大小和 mtime 前后对比。
- 官方父规则编号顺序、父子组件闭包、必做项目来源、资料要求和审核节点逐项校验。
- 持久任务中断/租约、失败重试、反馈防回退、草稿恢复、发布冲突和幂等重放回归。
- 真实 HTTP、SQLite、后台执行器与生产前端三档宽屏浏览器联调。

## Residual Boundary

- MG EX-07 的 6 个月范围没有命名回溯锚点，保持阻断；这不是失败或待自动修复项。
- 三路独立视觉医学监查员试用属于 Slice 8，尚未启动，不计入本轮通过证据。
- `ruff` 未安装，因此未运行该可选格式器；全量 pytest、TypeScript build 和浏览器测试均已通过。
