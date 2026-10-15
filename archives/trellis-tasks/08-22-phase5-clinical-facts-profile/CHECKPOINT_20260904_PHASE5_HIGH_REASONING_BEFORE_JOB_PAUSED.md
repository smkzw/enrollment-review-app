# Phase 5 高推理质量重跑前无损暂停点

- 暂停时间：2026-09-04 16:37 CST
- 工作树：`.worktrees/phase5-clinical-facts-profile`
- 分支：`codex/phase5-clinical-facts-profile`
- Trellis 任务：`08-22-phase5-clinical-facts-profile`
- 暂停性质：用户指令立即无损暂停

## 本轮已完成

1. 修正了事实发布仓库对日期范围的错误等值比较：一致性校验现在只比较精度、下界和上界，不再把来源原文 `source_text` 当作日期语义。
2. 修正了合并事实后事件/用药暴露的候选引用闭包：被引用的候选必须属于已列出的发布事实，且每个已列事实至少有一个实际支持候选；不再错误要求事件/暴露引用合并事实的全部候选。
3. 增加了事实、事件和用药暴露三类日期原文等价回归测试，并跑通相关集成范围：`191 passed, 5 warnings`。
4. 低推理基线 v9 作业已完成 25/25，导出包位于 `artifacts/phase5-acceptance/20260904/sar31001-v9-qc/run-packet.json`，机械完整性可验证。
5. v9 临床核对确认两项修复有效：“带回剩余糠酸莫米松”不再被误发布为实际用药；Profile 剂量不再重复拼接单位。
6. v9 临床核对仍不通过：原始资料中明确的奥马珠单抗给药已形成事实/事件，但模型未生成对应用药暴露候选；部分口服药亦有遗漏或因“文本值却携带单位”被合理拒绝。因此 `claims_complete` 仍必须保持 `false`。

## 刚才的运行状态

1. 已以显式 env 契约启动过专用 `8910`：
   - 数据目录：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh`
   - provider：`zhipu-coding-plan`
   - model：`glm-5.3-flash`
   - reasoning effort：`high`
   - max tokens：`16384`
   - pages per call：`1`
2. Uvicorn 已成功完成 application startup，但在创建新作业之前收到用户暂停指令。
3. 已立即向同一终端会话发送 `Ctrl-C`；Uvicorn 完成 application shutdown 并正常退出。
4. 本轮未向规范化 API 发送 POST，因此没有新增、半成品或需要取消的高推理作业；旧的 `cancel_requested` 作业也未被复用。

## 当前验收边界

- Phase 5 尚未收口。
- 不得将 v9 的技术完成状态当作临床验收通过。
- 不得设置 `claims_complete=true`。
- 尚不得回写实施计划中 Phase 5 为完成，也不得提前启动 Phase 5.5 实施任务。
- R3 读道裁决不变：main-A GLM-5.3-Flash:high，main-B MiniMax-M3:high，handwriting-C Qwen3.8-Flash-Next low 仅写 `handwriting[]`，DeepSeek 不进读道，GLM-OCR 仅作 OCR 侧车。

## 下一安全动作

1. 先确认 `8910` 未监听，并只读核对数据目录中没有新生成的未登记高推理作业。
2. 使用上述显式 env 契约重新启动 `8910`，在不暴露凭据的前提下核对健康状态和实际模型身份。
3. 为受试者 `31001` 从合法 API 入口新建不可变的 `GLM-5.3-Flash:high` 规范化作业，不复用任何 `cancel_requested` 作业。
4. 长轮询至明确终态；完成后导出新运行包，以原始证据逐项核对事实、事件、用药暴露及 Profile，特别检查所有明确实际给药是否完整投影。
5. 若高推理仍遗漏，先保留原始输出和失败证据，再设计通用的同模型语义完整性检查/修复回路；禁止为 SAR、31001、具体药物或日期写硬编码。
6. 只有 Phase 5 临床核对和计划回写真正收口后，才新建 Phase 5.5 Trellis 任务并先实施不依赖模型的 5.5-a ClausePack 投影与 5.5-b 页级合同层。

