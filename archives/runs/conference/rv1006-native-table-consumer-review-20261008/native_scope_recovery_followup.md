同一来源接线包复核开始。先定位五文件内的受影响定义与新测试。

定位新函数的调用点与两处测试标记。

读取核心定义与新接线：来源核对门、Runner 修正装配、新测试、validator 用例与恢复块。

最后读取：既有范围/时间校验门（确认未降低、共同标题门）与 services 层 validator-only 用例。

# 同源接线包复核（只读，~10 次有界读取）

**结论**：本轮局部接线未发现必须修项；未发现"旧合格含义必须失效"的反证。我未运行测试、未调用产品模型、未做临床核实。

## 必须修
无。

## 残余
1) **子串退化选择（具体越界形状）**：`native_schedule_time_excerpt_is_grounded`（`source_interpretation.py:318-333`）用 `value in header_text` 子串判定。反例形状：标记列共同表头为"筛选期"/"基线期 / V2 / D0"时，reviewer 回复 `source_time_excerpt="期"` 即通过选择门；随后修正模型可提出 `scope_quote="期"`，旧门（`:2615-2619`，同为子串）会放行，全链无最短长度/整词约束。建议最小加固：要求该值等于某列表头的完整分段（按 `/`、空白切分）而非子串；现有六变体测试（`test_slice58c_control_deconstructor.py:6640-6661`）未覆盖此轴。
2) **第一因果错误仍在解释阶段**：17 组第 5 条 scope/stage/time 全空，源头是解释步骤只提供同格标签（`_cell_scope_label_packet:2700`），不含原生标记列；`schedule_column_links` 无匹配目标即空，不代表无表头。本补丁只在核对失败后经修复轮兜底，未改上游材料——属窗口取舍，代价是每组多一次 review+repair；记为残余非缺陷。

## 关键落点与验证
- 选择门只回 bool，不写来源含义（`:321-333`）；接线仅对 `SOURCE_TIME_UNGROUNDED` 走旧入口（`protocol_control_deconstructor.py:8155-8161`），复用 `build_source_scope_correction_prompt`/`apply_source_scope_correction`（`:8169-8190`）。
- **兄弟依赖/真实共同标题**：要求全部标记列均有源表头、含同一摘录、`visit_unresolved`/脚注为假（`:329-333`）；测试 `mixed/other_column/partial_quote/footnote/no_header` 覆盖。
- **预算/重复**：`source_repairs` 共享计数（`:8168`），≥max 即抛（`:8164-8165`）；`repaired_review_indexes` 阻断同条二次修正（`:8112-8114`）；测试 `None/transport/wrong_scope/empty_time/budget/repeated`（`:6680-6732`）覆盖"预算耗尽/错误范围/空时间保留草稿、不重置"。
- **不采信模型判断为批准**：修正后仍要求 `scope_context_unit_id` 不变、`scope_quote/time_words` 非空并再次过同一门（`:8191-8199`），并逐项补齐时间（`:8200-8201`）。
- **旧门未降**：`validate_source_interpretation` 范围/阶段/时间门原样（`:2601-2659`），retry 仍为 `correct_source_scope`。
- **恢复重放**：新门只在 review 修复环调用；`protocol_control_execution.py:2490` 的已保存修正重放不走新门；身份仅 `validator_version` 增量（`:2060` `native-table-scope-recovery/v1`）；services 用例断言 reusable + `revalidated_from_gate_version` + 新版本串（`:5686-5700`）。

## 反证（若有请给）
未找到旧含义须失效的具体反例：写入路径未变、身份仅 validator 增量、旧记录与修复历史不反算；compiler/schema/source/route 变化仍拒绝复用（`:5703-5714`，及既有 `508/5655`）。

**声明**：未测试、未临床核实，此审阅不构成采用或发布批准。
