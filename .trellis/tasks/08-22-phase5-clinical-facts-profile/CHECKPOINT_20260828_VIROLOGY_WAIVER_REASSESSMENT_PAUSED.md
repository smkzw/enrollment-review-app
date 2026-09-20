# Phase 5.8d 病毒学条件豁免重评无损暂停点

时间：2026-08-28 20:24 CST  
分支：`codex/phase5-clinical-facts-profile`  
任务：`phase5-clinical-facts-profile`，保持 `in_progress`  
完成声明：`claims_complete=false`

## 本轮目标

以未经用户预处理的 D001 Ⅱ期原始 DOCX 产品链，验证 `body.p803`–`body.p805` 病毒学检查、补充检测、首次给药前 28 天有效期及条件性“无需再次检查”能否被控制 Agent 忠实解构，并修复同一来源拆出多个候选后的有界修订问题。

## 已完成且可保留的系统修订

1. 新增候选重分区错误分类，允许 `ACTION_TARGET_SCOPE_MISMATCH`、`MIXED_DECISION_STAGE_CONTROL`、`MIXED_TRIGGER_DECISION_STAGES` 在授权来源全集守恒时修订；未授权重分区继续失效关闭。
2. 规划器把“无需/不需要/不要求/可免”识别为必须保留的条件豁免语义。
3. 发布门禁新增条件豁免与同组有效期条件绑定检查，以及“没有重复执行”不能冒充既往客观证据的检查。
4. 修复纯“无需再次检查”被误判为当前阶段检查动作的问题。
5. 同一来源多候选的定向修订不再直接信任模型数组位置：当前实现先在全体当前候选中唯一匹配所有未授权兄弟候选，再校验剩余候选的来源键多重集合并按稳定内容排序回填。乱序通过、兄弟候选被修改时拒绝的聚焦测试已通过。

## 真实模型证据

- v5：5 次有界响应仍未发布，主要暴露同源多候选无法精确定位修订目标。
- v6：MTPLX `mtplx-qwen38-27b-optimized-quality:medium`，4 次响应后得到 3 个候选并通过当时门禁；总耗时 339.509 秒。
- v6 工件：`artifacts/phase5-slice61af-same-source-repair-addressing-20260828/`。
- v6 只能证明现有链路可解析，不能证明临床语义可接受，也没有真实触发最新同源候选乱序修订路径。

## 独立审查后的否决点

原 `parent-clinical-acceptance.json` 不再代表当前父级结论，后续必须以追加的重评文件明确将其标记为被取代，不能删除或覆写原始记录。

决定性临床问题：`body.p804` 后续的 28 天有效期及满足条件时无需再次检查适用于该段列出的整组病毒学检查。v6 第 3 个候选却把乙肝表面抗体、乙肝 e 抗原、乙肝 e 抗体拆成筛选期无条件“完成检查”，削弱了同段有效期/豁免条件。该控制点不得发布。

决定性工程问题：此前以 `mutable_candidate_indexes` 对齐同源候选依赖模型输出顺序；最新代码已改为未授权兄弟候选唯一匹配，但尚未完成完整方案层回归和真实模型验证。

独立审查记录：

- `runs/conference/phase5-slice61af-independent-clinical-code-review-20260828/general_grok46.md`
- `runs/conference/phase5-slice61af-independent-clinical-code-review-20260828/general_pi_antigravity.md`

其中 Grok 对 p804 条件豁免范围的质疑有效；其关于空分支绑定的推测不成立，因为水合结果保留了 3 个 `applies_to_trigger_branch_ids`。Gemini 建议维持 v6 接受的结论不采纳，因为它没有处理 p804 整组检查共享豁免这一临床语义。

## 暂停时验证状态

- 最新同源候选乱序修订：`17 passed in 0.06s`。
- 更早版本完整方案层：`975 passed, 58 warnings in 132.22s`。
- 重要边界：上述完整回归发生在最新乱序修订之后之前，因此不能当作当前代码全量通过证明。
- 未运行 v7、未发布控制点、未更新 D001 总体闭包。
- 未启动受试者、OCR、病例审核、Patient Profile、浏览器或视觉测试。
- 当前入排工作树无运行中的模型、会商或 pytest 进程。检测到的 `mm_r7_slice07a` 是另一工作流，未触碰。

## 当前关键文件哈希

- `app/agents/protocol_control_deconstructor.py`: `24b3b1e62e3dcd5e39dcd69d12c027a8e725862365a681f274db8bfc17344c5e`
- `app/protocols/protocol_control_gate.py`: `a6cedc9bf267b2ee380d9983f5061788e35a829186a4fd1b4b820cc007ead4c6`
- `app/protocols/protocol_control_planning.py`: `aac22d0c17d150249ae55c9a85db38ee5efd981cbf08060b200393a333e7a74f`
- `app/protocols/protocol_control_repair_errors.py`: `5754431d3c9ab091e2ee624a61521882043c384f2c4f4b6b9d1874fab6c8fe37`
- `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`: `9b59254fce90bd10fc68458a3ab7c62238b8a6b8ae4a49dad037ee808615fd53`
- v6 原父级接受文件：`82e1620890e765fa0f45eb0ce2655b70d2506cc26184a60a3b88dd3f1ef80c93`

## 下一步安全恢复顺序

1. 先读本文件、两份独立审查和 v6 三个候选，不从旧 `task.json.notes` 或旧父级接受文件直接启动模型。
2. 增加不可变 `parent-clinical-reassessment.json`，明确取代而不删除 v6 原接受记录。
3. 扩展条件豁免证据变体，但仅在冻结来源本身含豁免时启用，避免全局误报；覆盖“无重复、无再次、未重新、未再行”及常见英文表达。
4. 增加同源跨候选条件豁免范围门禁 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`：有效期/豁免与被豁免检查不得拆成无条件筛选完成义务；同一原子同时含完成动作和豁免时也必须结构化绑定。
5. 先跑聚焦测试，再跑完整 `tests/v2/protocols`。任何失败先定位共享原因，不启动模型掩盖问题。
6. 新建不可变 v7 配置并只运行一次有界 MTPLX medium 产品重放。父级临床验收必须确认 p804 的三项新增结果继承整段 28 天有效期/条件豁免，且不得形成无条件筛选执行要求。
7. 再做独立复核和治理审计。只有新工件通过父级临床审查、完整回归、独立复核及治理审计后，才可标记该代表组接受。

## 禁止事项

- 不得把 v6 的 `gate.accepted=true` 或旧 `parent-clinical-acceptance.json` 当作当前接受结论。
- 不得覆写 v5/v6 失败或反例工件。
- 不得直接扩大到剩余 128 包、受试者流程或全量模型运行。
- 不得通过增加重试次数替代条件豁免范围和同源候选身份问题的系统修复。
