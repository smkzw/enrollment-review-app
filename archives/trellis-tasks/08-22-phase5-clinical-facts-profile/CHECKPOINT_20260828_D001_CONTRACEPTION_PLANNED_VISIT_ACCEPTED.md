# Phase 5.8d 避孕附录计划访视闭包验收

日期：2026-08-28  
分支：`codex/phase5-clinical-facts-profile`  
工作树：`.worktrees/phase5-clinical-facts-profile`

## 本轮结论

本轮接受 D001 Ⅱ期 `body.p1325/body.p1326` 与 IN-06 的代表组结构化控制结果，
不代表 D001 Ⅱ期全文闭合，也不代表 Phase 5 完成。

## 根因与系统修复

1. v4 已正确保留避孕时间区间、附录增量、沟通和记录语义，但把原文“计划的访视点”压缩为仅筛选节点。技术门在旧代码下为绿色，父级临床核对拒绝。
2. 共享发布门现在从原子直接摘录识别计划访视量词作用域，要求冻结目录中每个 `visit_instance` 节点分别使用 `decide_at_node`；`early_attention` 不能冒充已判定。
3. `未计划访视`、`非计划访视` 不触发计划访视全节点闭包，避免将非计划检查扩散到所有节点。
4. Agent 首轮、自检和修订提示统一要求：只使用冻结目录、覆盖每个计划访视节点、每个决定阶段具备同阶段到期的最低证据，不得删除节点绕过要求或发明治疗期节点。
5. 上述机制为项目无关合同，没有写入 D001、IN-06 或避孕特异规则。

## v5 真实回放与父级验收

- 配置：`representative_group_contraception_documentation.v5.json`，继承 v4，不覆盖旧工件。
- 模型：`mtplx-qwen38-27b-optimized-quality`，`medium`，严格 JSON Schema，端点 `127.0.0.1:8002`。
- 运行：2 次调用，`118.86071s`；首轮发布拒绝、同会话修复后水合成功，2 候选、2 控制、技术门通过。
- `body.p1325`：仅保留禁止激素类避孕和方法讨论/选择/知晓增量；IN-06 已覆盖的持续避孕义务未重复。
- 时间区间：以 `study_period` 保留起点范围，以 `last_dose_date / after / upper_bound=3 months` 表达末次给药后三个月尾段；沟通动作不继承该持续期。
- `body.p1326`：保留计划访视告知、病历记录与参与者同意、停用方法或已知/怀疑怀孕时立即联系的条件指令；未把未来条件伪造成当前触发。
- 审核节点：`flow-screening` 与 `flow-baseline` 均为本节点判定；最低证据到期阶段同时覆盖 screening/baseline；未发明治疗期访视。
- 父级验收：`artifacts/phase5-slice60m-d001-contraception-documentation-replay-planned-visit-closure-20260828/parent-clinical-acceptance.json`。

## 验证证据

- 三路治理执行审计通过，实际路线均为 `cursor-cli/auto`，无 fallback 或身份漂移；父级审阅已记录并归档过程文件。
- 聚焦回归：`129 passed`。
- 完整方案层回归：`896 passed, 58 warnings in 116.93s`。
- `py_compile`、父级验收 JSON 解析、`git diff --check` 通过。
- v4 与 v5 的 `source_rows.json` 和 `execution/batch.json` 哈希分别一致，冻结输入未漂移。

## 活动边界

- D001 Ⅱ期仍为 `1848/1245/131`，剩余 128 包，`claims_complete=false`。
- 仅本代表组获得父级接受；此前被拒运行继续作为不可变反例保留。
- 未启动剩余包全量、受试者、OCR、病例审核、浏览器、视觉或用户指定的独立测试者。
- 不应因本轮模型两次调用即推断整体模型质量已经稳定。

## 下一安全动作

1. 从剩余冻结包中选择一个能增加新语义覆盖、且与已验收时间窗/访视/病毒学/结核/避孕不同的极小异质组。
2. 先建立人工来源闭包和父级临床检查清单，再运行至多一次真实 MTPLX medium；金标准不得注入 Agent 修订。
3. 若出现新错误，先判断是结构切分、目录身份、模型语义还是门禁缺口；只修共享机制并增加反例。
4. 不直接全跑 128 包，不提前进入受试者、OCR 或浏览器测试。
