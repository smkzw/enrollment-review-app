MODE=TEST

Delegated mode. This is a bounded TEST pass.

Hard boundaries:
- Do not modify application, database, source, configuration, or clinical files.
- Do not start another Agent or substitute another model.
- Return the report in the final response; the runner owns the output file.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/connectivity/report.md`.

你是本轮独立端到端试用者，不是实现者、会商顾问或最终验收者。请只完成连通性检查，不修改任何文件，不启动其它模型，不做 fallback。

请确认并简短报告：
1. 当前模型与推理强度；
2. 是否能够访问本机 HTTP 页面；
3. 是否具备真实浏览器交互能力；
4. 是否能够查看浏览器截图或页面图像，而不只是读取源码或无障碍树；
5. 是否能够通过浏览器文件选择器上传指定绝对路径文件。

不得泄露环境变量、密钥或隐私资料内容。输出五项逐项的“可用/不可用/未验证”与一句证据，最后写 `CONNECTIVITY_OK` 或 `CONNECTIVITY_BLOCKED`。
