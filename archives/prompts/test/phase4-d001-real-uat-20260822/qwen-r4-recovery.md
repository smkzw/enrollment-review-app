MODE=TEST

Delegated mode. 这是 Qwen `qwen3.8-max(high)` 同路由恢复测试，不是实现、会商或最终验收。上一正式会话因 Pi 扩展超时而只输出了未执行的工具调用文本，没有写入任何受试者、预览或资料；本轮必须重新通过真实浏览器完成原任务，任何工具调用文本都不能冒充执行结果。

Hard boundaries:

- 完整遵守下列原始测试说明中的真实浏览器、只读资料、禁止终端和禁止模型替换边界。
- 截图只写入 Qwen 指定目录，报告由运行器保存。

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/qwen-r4.md`
- `runs/test/phase4-d001-real-uat-20260822/qwen/input/01-筛选期病历.pdf`
- `runs/test/phase4-d001-real-uat-20260822/qwen/input/02-筛选期检查.pdf`
- `runs/test/phase4-d001-real-uat-20260822/qwen/input/03-既往病历.pdf`

完整执行 `prompts/test/phase4-d001-real-uat-20260822/qwen-r4.md` 的角色、边界、真实资料、业务闭环与报告要求。目标仍是 `http://127.0.0.1:4263/#/subjects`、3840×2160、受试者 `SA01023`。先确认截图真正落盘且页面快照可读，再继续完整试用；若工具仍超时或不能执行，立即保留真实错误并判定 `BLOCKED`，不得使用终端、API、其他模型或其他测试通道代替。

截图只写入 `runs/test/phase4-d001-real-uat-20260822/r4/qwen/screenshots/`。

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r4/full/qwen-recovery.md`.
