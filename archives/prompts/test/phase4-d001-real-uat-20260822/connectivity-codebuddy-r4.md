MODE=TEST

Delegated mode. 这是一次有边界的真实浏览器连通性测试，不是实现、会商或验收。

Hard boundaries:

- 只能使用当前指定模型和它自身可用的视觉/浏览器工具操作 `http://127.0.0.1:4261/#/subjects`。
- 禁止读取代码、数据库、服务日志、开发者工具网络响应或后端接口；禁止使用终端、curl、自写脚本或直接 API 完成界面操作。
- 禁止修改代码、配置、研究方案和临床原始资料；禁止启动其他 Agent；禁止替换模型。
- 只可读取本提示文件；截图只写入 `runs/test/phase4-d001-real-uat-20260822/r4/codebuddy/connectivity/`。

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-codebuddy-r4.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r4/connectivity/codebuddy.md`.

## 任务

以 1920×1080 视口打开页面，确认 D001-02 Ⅱ期项目可见、页面实际渲染、普通点击可用并保存至少一张真实截图。可创建一个名称明确的临时空受试者进入资料工作台，选择本提示文件以验证文件选择器，但不得确认上传；若出现预览，优先点击“取消预览”。不要求删除临时对象，控制端会在正式试用前重建清洁库。

返回简短中文表格，逐项给出页面加载、视觉、交互、截图、文件选择器的真实结果。只有全部成功且截图确实落盘时，最后一行写 `CONNECTIVITY_OK`；否则写 `CONNECTIVITY_BLOCKED` 并保留实际失败原因。
