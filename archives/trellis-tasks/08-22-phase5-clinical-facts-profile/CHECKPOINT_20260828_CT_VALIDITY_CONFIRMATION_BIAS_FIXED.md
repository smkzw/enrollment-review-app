# Phase 5.8d 胸部CT有效期代表组与验收确认偏差修复检查点

日期：2026-08-28  
分支：`codex/phase5-clinical-facts-profile`  
任务：`.trellis/tasks/08-22-phase5-clinical-facts-profile`

## 已完成

1. 直接使用 D001 Ⅱ期未经用户预处理的原始 DOCX 冻结结构，验证 `body.p797` 胸部CT结果有效期。
2. 真实 MTPLX medium 首轮响应判定：检查、知情同意书签署日前1个月有效期及“满足评估要求”均已被冻结流程必做项 `pcm-row-02a2cd07e9ccaeb65c4d156c` 覆盖；可酌情复测不产生新候选。
3. 父级拒绝后续技术绿色终稿，因为它凭空要求“筛选访视记录中应体现是否复测的决定”。
4. 根因修复：`CONTROL_DELTA_DROPPED` 仍进入最终临床验收，但不再作为同会话修订错误回传给 Agent。客观结构/发布错误仍照常修订。
5. 胸部CT配置不再预设必须生成候选。保存的首轮响应只读重放为 0 候选、1 条流程必做处置、发布接受、临床拒绝问题 0。

## 决定性证据

- 首轮响应文本 SHA-256：`8dc87a94d3036a6ea05d4fdd7aabaf78d3945ee1432e00efba8035fa3c78c94f`
- 父级评估：`artifacts/phase5-slice60h-d001-ct-result-validity-parent-assessment-20260828/assessment-summary.json`
- 聚焦回归：`146 passed in 1.33s`
- 完整方案层回归：`887 passed, 58 warnings in 126.51s`
- 未进行新的模型调用；未发布新控制点。

## 当前边界

- Phase 5 未完成，`claims_complete=false`。
- D001 II 保持 `1848` 个覆盖单元、`1245` 个语义目标、`131` 个包，剩余 `128` 包。
- 受试者、OCR、病例审核、浏览器、视觉和独立测试者均未启动。
- 原始三轮模型响应继续作为不可变反例保留，不覆写历史工件。

## 下一安全动作

选择另一组结构风险不同的小型真实控制点。Agent 首轮必须在不知道父级金标准答案的情况下运行；父级只在输出完成后做临床核对。不得全跑剩余 128 包，也不得进入受试者流程。
