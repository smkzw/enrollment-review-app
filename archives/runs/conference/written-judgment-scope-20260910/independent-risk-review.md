# Conference Output: written-judgment-scope-20260910 - evidence_single_object

## Output

F1/F2 收尾复审完成（只读，未改代码；独立复跑四个合成套件 127 passed，与执行者报告一致：correction-gap + expectations 投影 + normalization_persistence + correction_job）。结论：**两项残余风险已按 owner 要求修复到位——保留判定采用五元组结构化全等（kind/detail/referenced_file_id/模板绑定/fallback_only 的 canonical 哈希），不是 kind 级匹配；UNVERIFIABLE 排除与实际覆盖判定契约一致。本轮未发现新的实际缺陷；遗留两个低优先级测试缺口与两条行为备注。**

### 一、逐点核实（代码 + 测试证据）

1. **全结构等值（owner 要求，满足）**：`_signal_key` = 信号完整 `model_dump` 的 canonical 哈希（`fact_expectation_gaps.py:350-354`）；pad 触发条件是“先前期望适用于该模板的每一条具体信号都被当前重建信号**逐条全等复现**，任一未复现即补”（:409-425）。上一轮的模板级 `covered` 跳过已被彻底移除，老的反例路径（无关新信号掩盖旧风险、同 kind 不同 detail 视为复现）在结构上关闭。
2. **全局信号不能绕过先期溯源**：键内含 `applies_to_template_id`，全局（None 绑定）当前信号的键永远不等于模板绑定先期键，反之先期全局信号也只能被全等的当前全局信号复现——两个方向结构上都无法绕过。此点为源码推演结论，pad 层无专门测试（见缺口 G1；活管线推导不产生全局具体信号，实际暴露为零）。
3. **同 kind 不同 detail 保持独立**：`test_same_kind_different_detail_prior_input_not_erased` 两侧都用真实可持久化的 `ocr_or_parse_risk`（先期 detail=A、源运行补 item detail=B），断言：pad（关联先前期望 ID）在、B 在、A 不被原样重申为事实（:1146-1151）——正面钉死等值语义且不违反“不复制旧缺口”。
4. **legacy None 持续未决**：`prior_input is None → 无条件 pad`，明确“不受任何当前新具体信号影响”（:405-408）。代码核实；correction 层无 None 行模拟测试（见 G2）。
5. **精确复现不产生多余 pad**：`test_correction_keeps_source_risk_recorded_on_unresolved_item` 现在显式断言 `not any("先前期望" in detail)` 且复现信号在列（:469-476）。
6. **跨权威排除**：`prior.authority != authority → continue`（:396-397）；`test_prior_pad_ignores_expectation_from_other_authority` 以旧权威期望实测无 pad 泄漏。
7. **UNVERIFIABLE 排除符合覆盖契约（F2，满足）**：`accepted_requirements` 过滤 `SourceStrength.UNVERIFIABLE`（:470-476），与 `_coverage_verdict` 一致——UNVERIFIABLE 落到 "none"、永不构成 complete/weak 覆盖（`evidence_expectations.py:151-166` 本轮复核未变）。`test_unverifiable_current_fact_cannot_erase_rejected_source_risk` 的判别力经过设计：修订只改 fact_type、保留要求绑定，若过滤缺失则重投影与 r1 幂等同形，`revision == 2` 断言即失败（测试注释自证此点，:1240-1242）；同一测试还先验证了终结语义不变（None 覆盖下接受门禁仍压制 → 纯 fallback，:1218-1232）。
8. **原始终结行为不变**：共享函数默认路径与上轮逐行相同（仅新增 `SourceStrength` 导入与文档）；executor 无 `accepted_requirements` 使用（grep 证实），别名注入不变；normalization_persistence 套件随 127 全绿。

### 二、实际遗留缺陷

**无新缺陷。** F1/F2 按规格关闭。

遗留测试缺口（非缺陷，建议后续补）：
- **G1**：全局（None 绑定）具体信号无法掩盖先期模板绑定信号的 pad 层反例无测试（结构上已不可能绕过；活管线无全局具体信号生产者）。
- **G2**：correction 层缺“legacy None 先期行 → pad 且无视新信号”的端到端模拟（expectations 套件仅覆盖 legacy 解码；pad-legacy 分支 ：406-408 仅源码核实）。

### 三、集成风险与行为备注

- **pad 永不幂等收敛（设计使然，需知悉）**：pad 的 detail 内嵌先前期望 ID（含 revision），每次修订产生不同 detail → provenance 元组每次不同，被 pad 的模板在源记录重放或显式处置前不会进入幂等复用路径，每笔修订必然追加新 revision。方向保守正确（“未复现≠已解决”），但意味着 pad 状态在修订序列中持续改写 provenance；若未来需要“pad 稳定化”，应把 detail 中的期望引用改为 (episode, template) 级定位——不建议现在动。
- **压制集按强度、不按 verdict（与终结对称，非回归）**：活动转录事实绑定到“不允许转述”的模板时仍压制被拒候选信号（verdict 会是 none）——原始终结的“接受即压制”同样如此；改成 verdict 形压制会同时改变终结语义，超出本轮范围，仅记录。
- 同厂商复审独立性受限；owner 正在复跑。

### 四、验收边界

本报告仅为合成数据上的工程复审：127 项测试通过、源码逐点核实，不构成临床、监管或用户面验收。D2（研究者书面判断 PROFESSIONAL_JUDGMENT 生产者，活管线仍不可达）与 R1（批注时间/测量绑定无确定性校验）仍为独立未完成工作，本轮未触及、未并入本结论。
