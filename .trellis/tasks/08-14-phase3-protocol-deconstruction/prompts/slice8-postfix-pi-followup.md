Active task: .trellis/tasks/08-14-phase3-protocol-deconstruction

继续同一只读审评会话，复核你上一轮的 F1-F5 是否已经闭环。不要重读大篇文档，不得修改文件、运行数据或服务，不得启动子代理。

请用真实浏览器重新访问：

- `http://127.0.0.1:4196/#/protocols?job=d10dbadc4f5040798f30e80e7f36b002`
- `http://127.0.0.1:4196/#/protocols?job=6562172759e24cb4903be26ecf59ad81`
- `http://127.0.0.1:4196/#/protocols?mode=redo`

修订后机器视觉证据：`output/phase3-slice8-uat/screenshots/postfix/visual-qc.json` 及同目录截图。

必须重新判定：

1. F1/F5：D001 已发布任务是否进入“方案已发布”摘要，且不再保留为首页待继续任务；是否可直接进入预选 D001 的重新解构页。
2. F2：你上一轮请求的是不存在的 `/api/v2/jobs/{job_id}`。真实方案任务接口为 `/api/v2/protocol/deconstructions/{job_id}`；请实际请求该接口和 `/draft`，判定前端代理是否工作，撤回或保留 F2。
3. F3：用真实浏览器鼠标点击项目卡，观察 `aria-pressed` 与目标摘要，不要用不完整的坐标事件推断。
4. F4：MG 是否只默认展开当前父项，其余22项折叠且可点击展开。
5. 三档宽屏的横向溢出、控制台错误和中文自然度。

返回紧凑的增量复测报告，逐项写“已闭环 / 误报撤回 / 仍存在”，最后给出“接受 / 修正后接受 / 阻止进入下一阶段”之一。不要自行写报告文件。
