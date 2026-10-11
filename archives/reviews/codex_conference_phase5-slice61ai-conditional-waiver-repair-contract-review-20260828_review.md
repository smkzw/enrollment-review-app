# Codex Conference Review: phase5-slice61ai-conditional-waiver-repair-contract-review-20260828

Date: 2026-08-28

## Verdict

有条件采纳。两名独立参与者关于“条件豁免绑定缺失不应开放候选重分区”的异议成立；主线程已按更窄的固定候选表达式修订合同完成修正并通过当前方案层全量回归。v6、v7 均维持否决和未发布状态。

## Boundary Compliance

- 两名参与者均只读审查，没有修改应用文件、启动真实模型重放或发布控制点。
- 参与者使用声明的独立路由：`google-antigravity/gemini-3.7-flash:high` 与 `grok-build/grok-4.6:medium`，均无替代路由。
- 会商只审查 Phase 5.8d 的条件豁免修订合同及 v7 失败证据，没有扩展到其余方案包、受试者、OCR、Patient Profile 或视觉验收。
- Codex 保留最终工程、临床语义和发布边界的裁决权。

## Hermes Governance

会商由 guard 生成的数据包和 runner 执行；两份 Hermes 运行日志均记录请求路由、实际路由、session、`returncode=0` 与耗时。未手工改写参与者提示词、未替换模型，也未把参与者结论当作自动验收。

## Participant Outputs Reviewed

- `general_pi_antigravity`：确认 v7 在“门禁要求两组并为一组”与“原子级有界修订禁止组结构变化”之间形成确定性闭锁；指出把该错误归入候选重分区会过度授权。
- `general_grok46`：独立得出相同结论，并进一步指出来源闭包重分区会重新解冻 v6 已否决的同源无条件筛选兄弟候选。
- 两者都建议保留同组 AND 语义、将 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 与候选内部绑定修订分开治理，并先完成合同测试再考虑 v8。

## Conference Panel Review

会商最重要的异议成立。`CONDITIONAL_EXEMPTION_BINDING_MISSING` 是单一候选内部 DNF 表达缺陷，不是跨候选重分区缺陷。此前拟将其加入 `CANDIDATE_REPARTITION_GATE_CODES` 会放开候选数量、同源兄弟和来源闭包，超出修复所需权限。

采纳的架构裁决：候选 ID、候选数量和来源键保持不变，仅允许该候选内部义务组和原子的完整表达式重组；`CONDITIONAL_EXEMPTION_SCOPE_SPLIT` 仍单独负责跨同源候选的范围错误。中文修订指令继续要求同一义务组内同时保留带有效期的 `verify_result_validity` 与不带时间约束的免予 `complete_or_verify`，并禁止免予原子抄录无条件检查执行清单。

## Main-Venue Codex Review

Codex 接受两名参与者共同指出的权限分层问题，但不直接照搬其实现命名。现有修订恢复机制已经支持按固定 `source_structure_unit_ids` 键匹配唯一候选，因此无需新增并行旗标；只需将该错误归入候选表达式修订分类，并停止传递会锁死组结构的原子定位，即可得到最小且可验证的权限边界。

不采纳任何将 v7 视为“接近通过”的解释。v7 的两个义务组是 OR，不是同组 AND；p804/p805 合并、p805 三个条件性补充检测分支及非发生证据仍需在新工件中逐项核对。独立审查是修订合同的反证和纠偏依据，不替代 Codex 的父级临床验收。

## Codex Independent Verification

- 代码核对：`CONDITIONAL_EXEMPTION_BINDING_MISSING` 已从候选重分区集合移除，并进入固定候选表达式修订集合；发布错误不再为该错误传递原子级 span 锁，但候选来源键仍固定。
- 合同测试：新增正向用例，验证“两组 OR”可在固定候选中重组为“一组内两个 AND 原子”；新增集合边界断言，防止该错误重新进入候选重分区。
- 聚焦回归：`26 passed in 0.07s`。
- 当前方案层全量回归：`986 passed, 58 warnings in 127.18s`。
- 静态验证：`compileall` 与 `git diff --check` 通过。
- v7 真实工件复核：五次响应后仍 `hydrated=false`、`gate_accepted=false`，第 3 次为错误的两个替代义务组，第 4 次触发修订闭锁；不存在可发布终稿。
- 本切片不涉及 UI，因此未进行浏览器或视觉验收。

## Final Decision

采纳会商修订，拒绝原过宽候选重分区方案。当前系统合同已收窄并通过确定性回归，但尚未证明真实模型能在新合同下生成临床可接受结构。允许创建一个新的不可变 v8 配置并执行一次 MTPLX medium 重放；不得增加重试预算，不得覆盖 v5/v6/v7 工件，也不得在父级临床复核前发布控制点。
