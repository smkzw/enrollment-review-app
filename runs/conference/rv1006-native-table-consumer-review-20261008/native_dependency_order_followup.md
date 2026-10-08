第四轮差异复核开始：先定位新选择助手，再读五文件受影响定义与测试。

读取新接线与测试，并确认 validator 组成。

核对预算/重复保护与列作用域定义，再确认 validator 组成与复用用例。

最后三处：列作用域字段构成、validator 组成、复用用例。

# 原生来源依赖修复：有界差异审阅（基础 a7de55be）

**必须修**：无。四项挑战均未找到越界反例：选择输入已与核对者措辞解耦（`native_schedule_scope_requires_recheck` 只读冻结单元/列，`source_interpretation.py:318-332`）。

**第一因果位置**：修复点位于核对失败处理入口（`protocol_control_deconstructor.py:8156-8161`），先于目标字段修复；上游解释步骤仍不产出原生列范围（本轮未改），根因仍在解释阶段，本补丁给出一次修复机会。

## 建议
1) **首答合法时不触发**：唯一调用点在 8156 的 review 异常分支（grep 实证）。若首答本身合法（unresolved+aspects、source_time=null）即被接受，scope/stage/time 仍空且不修源——"填 null 也先修源"仅在首答另有非法字段时成立（测试 `missing_aspects_no_time_first` 即该形态）。建议合法 unresolved 落定前对该表再判一次，或明示接受此缺口。
2) **表头脚注未纳入**：`marker_footnotes` 只取标记格 `^\d+`（`procedure_catalog.py:860`），表头格脚注（如"基线期^1"）不阻断；`visit_unresolved` 仅查访视/日期样式（`:859`）。加表头脚注检查即可闭合（旧门同样如此，属继承）。

## 残余
- **共同标题**：等值取代了旧子串（`:352-356`，`subword` 用例锁死）；两列不同标题即不触发（`mixed`）。错列反例→假；跨期仅在全部标记列字面相同（如都只写"D0"）时成立，期别区分留待重核，非新采用。
- **修正范围**：仅写授权单条 scope/stage/time；修正后要求 context 不变、time/scope 非空、再经同一等值门与 `_unreported_time_fragments`（`:8191-8201`）；原句/用途/例外/兄弟不改（`apply_source_scope_correction:523-540`）。
- **预算/重复**：首次错误即登记 `repaired_review_indexes`（`:8115`），同条二次即抛（`:8113`）；`source_repairs` 共用（`:8163-8167`）；budget/repeated/transport/wrong_scope/empty_time 用例覆盖"失败不重置、只存草稿"。
- **恢复复用**：validator_version 仅追加 `native-table-scope-recovery/v3`（`protocol_control_execution.py:2060`）；当前门仍只容忍 validator 差，services 例断言 reusable+`revalidated_from_gate_version`+精确版本串（`:5686-5700`），并保留 schema/来源/编译变更拒绝复用反例（`:5703-5714`）。未发现旧成功须失效反例；新路径只在修复环执行，已保存 scope 修订重放（execution:2490）不经过它。

**声明**：静态读取 9 次；未运行测试、未调用产品模型、未核临床；本输出为同会话差异复核，非独立模型金标。
