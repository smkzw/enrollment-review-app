MODE=TEST

Delegated mode. 这是 Pi/oMLX `Qwen3.8-27B-oQ8e-fp16-mtp` 中等推理强度的真实浏览器连通性测试，不是实现、会商或最终验收。

Hard boundaries:
- Read these files only: `prompts/test/phase4-d001-real-uat-20260822/r6/connectivity-localqwen.md`。
- 仅通过模型自身的视觉/浏览器工具操作 `http://127.0.0.1:4275/#/subjects`，视口 3840×2160。
- 禁止读取源码、数据库、服务日志、开发者工具网络响应或后端接口；禁止终端、curl、自写脚本、直接 API、其他 Agent 和模型替换。
- 不修改代码、配置、研究方案或临床原始资料；本轮不确认任何资料上传。
- 截图只写入 `runs/test/phase4-d001-real-uat-20260822/r6/localqwen/screenshots/`。

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r6/connectivity/localqwen.md`。

打开受试者与资料页，确认 D001-02、Ⅱ期、方案 1.0 的正式项目页面真实渲染；检查普通点击、项目选择、帮助入口和截图保存。不得把工具调用文本当作已执行结果。仅当页面、交互和至少一张截图均真实成功时，最后一行写 `CONNECTIVITY_OK`，否则写 `CONNECTIVITY_BLOCKED` 并说明实际原因。
