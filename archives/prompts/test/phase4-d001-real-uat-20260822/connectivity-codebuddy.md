MODE=TEST

Delegated mode. This is a bounded TEST pass.

Hard boundaries:
- Do not modify application, database, source, configuration, or clinical files.
- Do not start another Agent or substitute another model.
- Return the report in the final response; the runner owns the output file.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-codebuddy.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/connectivity/codebuddy.md`.

请只完成连通性检查。逐项报告当前模型与推理强度、本机 HTTP 访问、真实浏览器交互、浏览器截图/页面图像查看、浏览器文件上传能力，分别写“可用/不可用/未验证”与一句证据。不得泄露环境变量、密钥或临床内容。最后写 `CONNECTIVITY_OK` 或 `CONNECTIVITY_BLOCKED`。
