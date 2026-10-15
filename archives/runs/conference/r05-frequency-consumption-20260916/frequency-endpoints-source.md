# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前；本轮仅读指定五个对象（`occurrence_scope.py`、`frequency_period_qualification.py`、双解构器 scope schema/prompt 段、`qualified_frequency_evidence.py` 版本、`frozen_review_publication.py` 评测集合段）及 F1/F2/F3 修复点。

**先认领更正**：我上轮 R2“related 恒空”错误——早期 unresolved 结果（如 `frequency_sources_unresolved`、`frequency_total_not_available`）的 `used_fact_ids` 为空而 `source_fact_ids` 保留全部已资格来源，`frequency_review_presentation.py:30-33` 的 related 记录正是让用户看到“核对了哪些原文”的必要呈现，不应移除。

---

### 核验结论（evidence，全部通过）

1. **F1 已修复**：`frozen_review_publication.py:81-82` 频次评测摘要并入采用门复验集合；`:95-96` 增加 `frequency_statement_fidelity` 种类核验——与三个兄弟族同款纵深防御，绕过命令直调发布时不再有豁免。
2. **F2 已修**：`reviewConditionNotes.ts:33` 补 `occurrence_count_bounds_inconclusive`（“现有记载已核实，但次数范围仍跨越方案要求的限值”）。**F3 已修**：`api/v2/review_history.py:450` 改 `elif`。
3. **v3 端点语义健全**（逐步验算）：
   - `_endpoint_possibilities`（`frequency_period_qualification.py:24-27`）：已知 inclusive→单可能；未知→{+0,+1}（start）/−{0,1}（end）；与部分精度的双界叠加后每端点至多 4 可能（2 精度×2 开闭），全笛卡尔积 hull——与此前核验的“唯一真世界”语义相同，健全；全部世界同界时 hull 即该界，**不强制 unknown** ✓。
   - 两处 false default 已消除：v1 代码对**要求窗口**端点隐式按含端处理且对**声明期间**强设 `frequency_period_boundary_unverified`（旧 62-63 行）；现两侧均枚举，未知开闭不再有默认、也不再强制未决（80-81 替代旧检查）✓。倒置（85-86）与非包含重叠（90-91）仍 unresolved ✓。
   - 旧数据行为：v1/v2 载荷缺字段→模型默认 None→序列化 pop（`occurrence_scope.py:27-29`）→**旧字节身份不变**；非 v3 补入非 null 字段拒绝（34-35）、v1 补 unanchored_lookback 拒绝（36-37）；v3 载荷显式保留 null 字段——重序列化字节稳定，无身份漂移。对旧 scope 的重算只会**变宽不会变窄**（枚举⊇旧隐式含端假设），历史存储结果不受影响。
4. **同步与版本一致**：官方 wire `_wire_occurrence_scope_schema` 内联 `OccurrenceScope.model_json_schema()`（`protocol_deconstructor.py:696-698`），控制 wire 经 `ProtocolControlAgentWire.model_json_schema()` 传递——v3 新字段自动进入双族 provider schema（`_inline_required_contract_schema` 键必填、值可 null），**schema 由共享合同生成、无手抄漂移**；`dnf-v16`、控制 prompt `v2.18`（`:1288` "未能从方案确定填null"）、`qualified-frequency-evidence/v3`、`frequency-period-calculation/v2` 均与声明一致；官方 prompt `:301` 同步指示按原文填写开闭。

### 残余（观察级，无需改动）

- v3 对未声明开闭的 scope（null）在新解构中是否应由 gate 提示（如边界未核）——现资格层枚举已健全，gate 提示仅为提示质量项，可留待方法评测观察误判率再定。
- 最坏组合规模 4⁴=256 次纯日期比较，量级无虞。

**非声明**：仅编译级事实；无运行、无测试、无临床数据访问；不构成方法批准或完成宣告。会话保持可续。
