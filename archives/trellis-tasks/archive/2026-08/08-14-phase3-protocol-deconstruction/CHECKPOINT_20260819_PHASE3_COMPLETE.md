# Phase 3 完成检查点

## 状态

- Phase 3 切片 1-9 已完成，当前任务可提交并归档。
- 下一安全动作是按总实施计划建立/`start` Phase 4 受试者资料摄取与证据标准化任务；不得在无 Phase 4 合同时继续向 Phase 3 工作台塞入 OCR、Patient Profile 或受试者判定。

## 临床与方案锚点

- D001 II：方案 `D001-02-002` V1.0，官方父规则 IN 6 / EX 30，正式项目 `draft-project-d10dbadc4f50`，RuleSet 第 1 版已发布。
- MG-K10-SAR III：方案 V2.1，官方父觉则 IN 7 / EX 16，当前草稿第 5 稿含 73 个子组件、185 项资料要求。
- MG 唯一阻断：EX-07s “6个月内存在或疑似蠕虫感染”未命名回溯起点。这是方案解释问题，系统必须继续阻止发布，不得猜测筛选日、基线日或随机日。
- 终态证据：`output/phase3-slice8-uat/runtime/final-mg-draft-rev5.json`、`final-mg-integrity-rev5-gate3.json`、`final-d001-draft.json`、`final-d001-integrity-v2.json`、`final-d001-publish.json`。

## 本轮共享机制修复

1. 在任何语义模型调用前，将单期投影、官方父规则目录、基线及以前必做项目录和来源片段独立落盘；语义服务失败后仍可查来源，重试不重做前置工作。
2. 原子条件的时间语义优先归属自身 `source_term/attribute`；完整逐字来源句只在原子语义未说明时补充，防止 OR 兄弟分支或并列上下文把时间窗错绑到无关条件。
3. 局部反馈修订同时比较问题数和指纹；问题数变少但产生任何新问题仍算回退。默认语义修订器可带拒绝原因有界重试一次。
4. 完成且已发布的任务直链显示只读正式版本摘要，清除“继续上次任务”，并可一键进入已预选项目的重新解构页。
5. 长规则树默认只展开当前父项；选中子项的深链会自动展开父项。

## 独立审评

- CodeBuddy CLI / `hy3(max)`：有效终局会话 `phase3-slice8-codebuddy-postfix2-20260819`，完成 94 个内部回合，真实浏览器复测后“修正后接受”。原会话因 plan 权限无法用浏览器且读了旧快照，“17项阻断”已正式撤回。
- CodeBuddy CLI 调用坑：`--disallowedTools` 是可变长参数，若未用 `--` 终止选项，会吞掉后续位置提示词并以零输入“成功”结束。
- Pi / `cms-router/minimax-m3`：会话 `01a016ac-885c-7000-8f85-c4207103ecee`，同会话增量复测后“接受”；撤回不存在的 `/api/v2/jobs/{job}` 导致的 API 代理误报。
- Grok Build / `grok-4.6 medium`：原会话 `3ade2114-e437-41fa-bdd0-5e927778396c`、同会话恢复以及全新会话 `63f530d5-0c88-41b2-99ca-08fccf4ca6b6` 均在开始真实浏览器动作前因该 harness 的 `read_file` `tool_output_error` 被取消。无可用审评，未换模型、未转运输、未将调用成功冒充试用完成。

## 最终验证

- 后端全仓：`909 passed, 1 skipped, 60 warnings, 18 subtests passed`。首轮隔离工作树因 `.gitignore` 中的旧 `projects/MG-K10-SAR` 夹具未进入 worktree 而失败 5 项；只复制最小配置/规则/阶段/元数据副本后全量通过，不直接读写主工作树旧项目。唯一跳过为 06003 OCR 缓存夹具不存在。
- 前端：Vitest `35 files / 275 passed`；TypeScript + Vite 生产构建通过。
- Playwright：首轮 6 项失败为旧用例假定子项默认全展开；按真实用户动作先展开 EX-01 后，聚焦复测 `31 passed, 2 skipped`，全量矩阵 `256 passed, 41 skipped`。
- 真实 HTTP 视觉：1920×1080、2560×1440、3840×2160 的 MG 页 `scrollWidth === viewportWidth`，均为 1 个父项展开/22 个折叠、0 控制台错误；D001 已发布直链无恢复态，真实鼠标点击项目卡后 `aria-pressed=true`。

## 保留与清理边界

- 保留：`output/phase3-slice8-uat/final-data.KxMz2U/`、`inputs/`、上述终态 JSON、`screenshots/postfix/`、精简独立审评及本检查点。
- 删除：另三份测试者临时数据库、中间草稿/反馈轨迹、旧截图、Playwright trace/失败图、巨型 stdout、临时脚本、PID/服务日志和隔离旧项目副本。
