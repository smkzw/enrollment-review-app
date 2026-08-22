MODE=TEST

Delegated mode. This is the single allowed recovery pass in the existing CodeBuddy connectivity session.

Hard boundaries:
- Do not modify application, database, source, configuration, or clinical files.
- Do not start another Agent or substitute another model.
- Use the now-authorized headless tool mode only for local HTTP/browser/screenshot/upload connectivity checks.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-codebuddy-recovery.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/connectivity/codebuddy-recovered.md`.

上一轮因 plan 权限无法调用 Bash/浏览器。本轮不要重复解释权限问题：请实际访问 `http://127.0.0.1:4261/#/subjects`，优先显式调用可用的 Playwright/MCP 浏览器工具；验证页面交互、真实截图查看和通过文件选择器选择本提示文件本身的能力（不要提交上传）。逐项给出证据，最后写 `CONNECTIVITY_OK` 或 `CONNECTIVITY_BLOCKED`。
