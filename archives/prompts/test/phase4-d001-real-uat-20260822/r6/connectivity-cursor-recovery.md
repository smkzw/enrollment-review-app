MODE=TEST

Delegated mode. 这是 Cursor CLI `cursor-grok-4.6-medium` 的真实浏览器连通性恢复测试，不是实现、会商或最终验收。

Hard boundaries:
- Read these files only: `prompts/test/phase4-d001-real-uat-20260822/r6/connectivity-cursor-recovery.md`。
- 仅通过模型自身的视觉/浏览器工具操作 `http://127.0.0.1:4274/#/subjects`，视口 1920×1080。
- 禁止读取源码、数据库、服务日志、开发者工具网络响应或后端接口；禁止终端、curl、自写脚本、直接 API、其他 Agent 和模型替换。
- 不修改代码、配置、研究方案或临床原始资料；本轮不确认任何资料上传。
- 截图只写入 `runs/test/phase4-d001-real-uat-20260822/r6/cursor/screenshots/`。

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r6/connectivity/cursor-recovery.md`。

前一轮只因把推理强度写成了不存在的基础模型选择器，未建立会话、未进入页面。本轮使用 Cursor CLI 目录中的同一指定模型中等强度标识 `cursor-grok-4.6-medium`。打开受试者与资料页，确认 D001-02、Ⅱ期、方案 1.0 的正式项目页面真实渲染；检查普通点击、项目选择、帮助入口和截图保存。不得把工具调用文本当作已执行结果。仅当页面、交互和至少一张截图均真实成功时，最后一行写 `CONNECTIVITY_OK`，否则写 `CONNECTIVITY_BLOCKED` 并说明实际原因。
