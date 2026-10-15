MODE=TEST

Delegated mode. 继续同一 CodeBuddy `hy3(max)` 连通性测试会话。

Hard boundaries:
- Read these files only: `prompts/test/phase4-d001-real-uat-20260822/r5/connectivity-codebuddy-recovery.md`。
- 仅通过真实浏览器与截图工具操作 `http://127.0.0.1:4271/#/subjects`；禁止读取源码、数据库、服务日志、接口、终端或开发者工具。
- 截图只写入 `runs/test/phase4-d001-real-uat-20260822/r5/codebuddy/screenshots/`；不得确认上传、新增数据或修改产品文件。

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r5/connectivity/codebuddy-recovery.md`。

上一轮只因非交互权限模式阻止视觉工具执行，未完成任何页面操作。现在浏览器与截图工具已获本轮授权，请直接继续原任务：仅通过真实浏览器访问 `http://127.0.0.1:4271/#/subjects`，视口 1920×1080；确认 D001-02、Ⅱ期、方案 1.0，检查项目选择、帮助入口和普通点击，并至少保存一张真实截图到 `runs/test/phase4-d001-real-uat-20260822/r5/codebuddy/screenshots/`。

仍禁止读取源码、数据库、服务日志、接口、终端或开发者工具；不得确认上传或新增数据；不得改动产品文件。只有页面、交互和截图均真实成功才以 `CONNECTIVITY_OK` 结尾，否则以 `CONNECTIVITY_BLOCKED` 结尾并写明实际原因。
