# Phase 5.8d 病毒学 v8 范围拆分拒绝检查点

日期：2026-08-28  
分支：`codex/phase5-clinical-facts-profile`  
任务状态：`in_progress`  
完整性：`claims_complete=false`

## 当前结论

- D001 II 期病毒学代表组 v8 已完成一次不可变 MTPLX medium 回放：5 次响应、336.866189 秒，最终未水合、未通过发布门禁、未发布。
- 第 5 次响应对获授权的 `body.p804` 候选作了正确修改，但同时改写了不同来源 `body.p805`。共享有界恢复现按来源键消费并恢复不同来源冻结候选；同源未授权兄弟仍必须完全相同，候选数量和来源分区变化仍拒绝。
- 将第 4→5 次响应按修复后的合同离线恢复后，`body.p805` 的三条触发分支、首次给药前 28 天结果有效性和条件性无需再次检查可接受。
- `body.p804` 仍不可接受：HBsAb、HBeAg、HBeAb 被保留为无条件筛选完成候选，没有继承同段 8 项病毒学检查共同的 28 天有效期和无需再次检查条件，确定性门禁触发 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`。
- 工程恢复成功不等于临床结果可接受；v8 保持拒绝，不得覆盖、发布、增加修订预算或按同一单候选合同重跑。

## 不可变证据

- 运行结果：`artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/runner-result.json`
  - SHA-256：`6e54d7bef4789e809919056c9b503a00fedcd8abc48208c5abc1d228c13085dc`
- 回放摘要：`artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/replay-summary.json`
  - SHA-256：`6375310e3c3adbbea9d371958a3d395c87772bb655cec2ed9061ed0b62560316`
- 第 4→5 次离线恢复：`artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/post-failure-bounded-recovery.json`
  - SHA-256：`138ca09560c417079e30ef7208d22c4e334feefb11a05148193bcfb956367954`
- 父级临床重评：`artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/parent-clinical-reassessment.json`
  - SHA-256：`832d6ef52f83998f7f6c0a59482e3f7eb9f9de5b10d2793f9c7253f9bcbc8efe`
- 独立审查：`reviews/codex_conference_phase5-slice61ak-v8-bounded-repair-audit-20260828_review.md`

## 当前代码与验证

- `app/agents/protocol_control_deconstructor.py`：`a560612f47fa45043a68215ed3d0a63e6a2a1156535122119ff7c36e6936f913`
- `app/protocols/protocol_control_gate.py`：`3917d56fc44d5fab9fabf2c4acdf847b50f5dd693a98f3a5aa2466318feb8c05`
- `app/protocols/protocol_control_repair_errors.py`：`d532351c3bc1a31d4b38719cef965b25a576de384484275e3c86c04f76e9f354`
- `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`：`c5728f165c9bf52fab85e00c0eb8d16966e43786a4e37719146cbfdf5389f485`
- 聚焦合同回归：`29 passed in 0.09s`。
- 完整方案层回归：`989 passed, 58 warnings in 133.77s`。
- `compileall`、`git diff --check` 通过。

## 独立审查与治理状态

- Gemini 3.7 Flash high 与 Grok 4.6 medium 均独立确认：不同来源恢复正确，p804 范围拆分仍应拒绝，下一修复必须覆盖 p804 同源候选闭包并冻结 p805。
- `review-gate` 已通过。
- `validate-conference` 报告 `general conference missing required role: cursor-cli`。本次 `init-conference` 生成的数据包只含 Gemini 与 Grok 两个角色，而当前验证器又要求 `cursor-cli`，属于 guard 生成器与验证器不一致。不得伪造 Cursor 审查或手改数据包冒充通过；该治理问题不改变两路审查内容和非模型回归证据，但会议治理状态必须保留为未完全闭合。

## 下一安全动作

建立新的独立切片，先用确定性测试设计通用的“同一来源闭包内候选合并/重写”合同：

1. 只开放 `body.p804` 的来源闭包，允许同源两个候选合并或共同继承条件豁免。
2. `body.p805` 及其他来源候选必须恢复为上一轮冻结内容。
3. 候选来源全集必须守恒，不能跨来源吸收、丢失或新增来源。
4. 先用合成反例和保存响应验证，再做独立审查；未通过前不得启动 v9 或其他真实模型回放。

## 禁止事项

- 不发布 v6、v7 或 v8 控制点。
- 不覆写任何历史运行、父级重评或独立审查工件。
- 不提高 v8 修订次数，不沿单候选位置合同重跑。
- 不扩大到其余 128 包、受试者、OCR、病例审核、Patient Profile、浏览器或视觉测试。
