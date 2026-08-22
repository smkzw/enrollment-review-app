# Connectivity Report

- 当前模型与推理强度 — 可用。`MiniMax-M3` 工作站 M5 Max / Darwin arm64，会话内可执行 `read`/`grep`/`bash` 等工具。
- 本机 HTTP 访问 — 可用。`curl https://example.com -I` 返回 `HTTP/2 200`；`127.0.0.1:65530` 收到本机栈响应（`502`），证明本机 TCP/HTTP 可发包。
- 真实浏览器交互 — 可用。Playwright Node 1.60.0 + 本机缓存的 `chromium`（ms-playwright `chromium-1234`）启动并访问 `https://example.com`，`status=200`，title=`"Example Domain"`，无 pageerror。
- 浏览器截图/页面图像查看 — 可用。`page.screenshot()` 写入 `/tmp/connectivity-shot.png` 17,091字节；ARIA 快照可获取（232 字符）。
- 浏览器文件上传能力 — 可用。注入 `<input type=file>` 后 `setInputFiles` 成功，`document.getElementById('f').files.length === 1`。

未泄露任何环境变量、密钥或临床内容。

`CONNECTIVITY_OK`
