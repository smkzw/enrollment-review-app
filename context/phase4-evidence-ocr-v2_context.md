# Task Context: phase4-evidence-ocr-v2

Created: 2026-08-19 05:56:57
Objective: 实现Phase 4证据快照、显式增量/全量上传、内容哈希去重、OCR V2、文档分类、来源定位与风险校对，并完成确定性和真实浏览器验收
Task type: `long_horizon_code`
Risk: `high`
Selected agent route: `opencode-go` / `deepseek-v4-flash` / `max`

## Trigger Reason

This task was initialized through the Codex x Hermes complex-task entrypoint because it is expected to involve more than three execution steps, research/writing/report/code/report-visual work, or source-grounded verification.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/design.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/implement.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/research/*.md`
- `.trellis/spec/backend/*.md`、`.trellis/spec/frontend/*.md` 与相关跨层指南
- Phase 3 已归档实现和验收仅作为上游基座；旧 `projects/` 与真实临床资料只读。

## Scope

- In scope: 不可变证据快照、补充/完整资料上传预览与确认、内容哈希去重、页产物、来源保留 OCR、真实定位精度、OCR 风险校对、持久恢复和宽屏中文证据工作台。
- Out of scope: Phase 5 临床事实与 Patient Profile、Phase 6 入排判断与行动、Phase 7 批量审核/报告、Phase 8 真实临床结论、旧项目写入、登录/多用户、安全专项及窄屏适配。

## Success Criteria

- `prd.md` 的 P4-AC01 至 P4-AC13 全部有确定性或真实浏览器证据。
- 同文件同配置不重复 OCR，文件/配置变化仅重跑相关页；全局 OCR 峰值不超过 8。
- 补充资料形成前序快照超集，完整资料快照不继承旧成员；旧快照不删除，跨节点资料不串入。
- 原 OCR 不覆盖，关键极性/数值/单位/日期校对需明确确认；EvidenceSpan 不伪造区域坐标。
- 故障注入、浏览器关闭和服务重启后可恢复，无永久处理中或部分失败伪完整。
- 有效 CSS 宽度不低于 1280 的宽屏组合下无页面级横滚、文字裁切或重叠；覆盖 1920×1080（100%/125%）、2560×1440（100%/150%）、3840×2160（100%/150%/200%）。
- CodeBuddy hy3(max)、Pi minimax-m3、Grok Build 4.6 medium 各自先通过真实连通性测试，再进行独立端到端试用；Codex 最终验收。

## Risk Boundaries

- 只在 Phase 4 worktree、隔离测试数据库和任务产物路径内写入。
- 不修改原始方案、真实受试者原始资料、旧项目、旧报告或 Phase 3 已验收数据。
- 不把纯文本 OCR 当布局结果，不把模型判断当确定性门禁，不在 Phase 4 形成入排结论。
- 数据迁移先备份；候选快照通过门禁前不改变现行快照。
- The delegated agent is not final authority; Codex owns verification and acceptance.

## Timeout Policy

- Do not mark the delegated agent failed for slow response alone.
- For complex or artifact-heavy work, wait and poll generously; use conference mode when multiple independent model perspectives are needed.
- Failure requires terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no progress after hard wait plus one retry.
- A provider catalog/auth/transport preflight is diagnostic, not a live capability verdict: timeout, auth refresh failure, malformed output, or a stale/incomplete catalog must be recorded and followed by one real route attempt. Explicit user-selected routes are not blocked merely because the catalog does not list them; only a missing executable or native transport boundary may stop before that attempt.

## Loop Log

- 2026-08-19 05:56:57: Task initialized by `tools/hermes_workflow_guard.py init-task`.
- 2026-08-19: Completed codebase gap audit, three independent research passes, and bounded external discovery. Planning artifacts converged to 10 requirements, 13 acceptance criteria, and six implementation slices.
- 2026-08-19: Planning gate remains closed. Do not run `task.py start` or modify product code until the user explicitly approves the latest final planning summary.
- 2026-08-19: Independent Sol review found reproducibility, logical document replacement, state-machine, format rendering, quantitative OCR/locator, concurrency-unit, wide-screen, hard-stop, and referenced-document gaps. The plan was revised around immutable EvidenceProcessingRevision plus append-only ActivationEvent; human UAT was not added because the user explicitly delegated testing to three model roles, and that limitation is now stated as residual risk.
- 2026-08-19: After four read-only review rounds, the independent Sol reviewer found no remaining internal blocker and declared the plan ready for user final approval. Final closures include versioned document metadata/reference relations, a complete terminal-safe state table, and aligned 0008/0009/0010 plus Slice 4.1/4.3/4.4 boundaries.
