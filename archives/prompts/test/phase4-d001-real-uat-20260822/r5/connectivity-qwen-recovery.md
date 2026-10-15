MODE=TEST

Delegated mode. 继续同一 Pi `alibaba/qwen3.8-max(high)` 连通性测试会话。

Hard boundaries:
- Read these files only: `prompts/test/phase4-d001-real-uat-20260822/r5/connectivity-qwen-recovery.md`。
- 仅通过真实浏览器与截图工具操作 `http://127.0.0.1:4273/#/subjects`；禁止读取源码、数据库、服务日志、接口、终端或开发者工具。
- 截图只写入 `runs/test/phase4-d001-real-uat-20260822/r5/qwen/screenshots/`；不得确认上传、新增数据或修改产品文件。

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r5/connectivity/qwen-recovery.md`。

上一轮 OMP 任务扩展超时，最后只输出了未执行的工具调用文本，因此不构成任何测试证据。不要再次把工具调用写成文本，也不要使用 `write` 向 `xd://browser` 写工具封装；请直接调用当前会话已连接的真实浏览器/puppeteer 工具完成原任务：访问 `http://127.0.0.1:4273/#/subjects`，视口 3840×2160；确认 D001-02、Ⅱ期、方案 1.0，检查项目选择、帮助入口和普通点击，并至少保存一张真实截图到 `runs/test/phase4-d001-real-uat-20260822/r5/qwen/screenshots/`。

仍禁止读取源码、数据库、服务日志、接口、终端或开发者工具；不得确认上传或新增数据；不得改动产品文件。只有页面、交互和截图均真实成功才以 `CONNECTIVITY_OK` 结尾，否则以 `CONNECTIVITY_BLOCKED` 结尾并写明实际原因。
