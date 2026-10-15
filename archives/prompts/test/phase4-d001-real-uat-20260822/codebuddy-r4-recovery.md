MODE=TEST

Delegated mode. 这是同一 CodeBuddy `hy3(max)` 真实浏览器试用的恢复轮，不是实现、会商或最终验收。

继续操作 `http://127.0.0.1:4261/#/subjects`，视口 1920×1080。上一轮已经建立正式受试者 `SA10004`，按 01、02、03 顺序提交三份 PDF；系统后台现在已经完成 16/16 页处理。不要重新建立受试者或重新做首次完整上传，直接从界面重新进入该受试者的“筛选期审核”并完成剩余闭环。

Hard boundaries:

- 只能使用真实浏览器和产品自身功能；禁止读取源码、数据库、服务日志、开发者工具网络响应或后端接口；禁止终端、curl、自写脚本和直接 API。
- 禁止修改代码、配置、研究方案或临床原始资料；禁止启动其他 Agent；禁止替换模型；不得用你自己的医学推理替代产品能力。
- 只可读取下列临床文件，并仅在需要对照原件时读取。
- 截图只写入 `runs/test/phase4-d001-real-uat-20260822/r4/codebuddy/screenshots/`。

Read these files only:
- `runs/test/phase4-d001-real-uat-20260822/codebuddy/input/01-知情病历.pdf`
- `runs/test/phase4-d001-real-uat-20260822/codebuddy/input/02-筛选期检查.pdf`
- `runs/test/phase4-d001-real-uat-20260822/codebuddy/input/03-既往病历.pdf`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r4/full/codebuddy-recovery.md`.

必须完成并留证：处理完成后的页面恢复；三份文件与 16 页页序；连续原件；至少 5 页识别文本与原件对照；至少 3 个定位及红框准确性核对；全部可见逐页风险复核；必要时的真实校对和关键语义二次确认；生成并启用识别版本；返回、刷新、重新进入后的历史恢复；整组三份相同文件的重复上传；以“补充资料”选择一份既有文件的增量上传；取消预览。若界面阻止重复或增量提交，要记录原生提示，不得绕过。

报告中合并上一轮已观察事实，统计完成/失败/未尝试、截图、误操作或犹豫、预览次数、原件页抽查数、文本对照数、定位核对数、风险核对数、校对数、恢复次数；分开写事实、推断和建议。最后只能给 `PASS`、`PASS_WITH_FINDINGS` 或 `BLOCKED`，不得宣布 Phase 4 通过。
