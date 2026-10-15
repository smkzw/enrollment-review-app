MODE=TEST

Delegated mode. This is the single allowed same-session recovery pass for the Qwen connectivity test.

Hard boundaries:
- Do not modify application, database, source, configuration, or clinical files.
- Do not start another Agent or substitute another model.
- Call exactly one tool per assistant turn. Never emit two tool calls in one response and never print raw tool-call markup as final text.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-qwen-recovery.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/connectivity/qwen-recovered.md`.

上一轮因同一响应并发发出多个工具调用而没有完成。请逐轮单工具地实际访问 `http://127.0.0.1:4263/#/subjects`，验证本机 HTTP、真实浏览器交互、真实截图查看和通过文件选择器选择本提示文件本身的能力（不要提交上传）。完成后只输出结构化连通性报告，最后写 `CONNECTIVITY_OK` 或 `CONNECTIVITY_BLOCKED`。
