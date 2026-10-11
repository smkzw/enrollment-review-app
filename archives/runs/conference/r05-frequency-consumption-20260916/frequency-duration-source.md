# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`occurrence_scope.py` v4（duration_basis 段）、`frequency_quantified_periods.py` 现行全文、`frequency_review_presentation.py` 量化段、双解构器 prompt 行、前端新码。仅报告新发现问题或更正后的源码边界；仍为编译/tsc 级事实，非临床接受。

---

### 1. F1 修复核验（evidence，通过）

- **`duration_basis` 三值显式化**（`occurrence_scope.py:25,36,43-44,50-51`）：v4 专属、旧版 pop＋拒绝补入、仅 `any_consecutive`/`anchored_period` 可声明——calendar_period **天然 calendar_span**（`frequency_quantified_periods.py:114` 的 `scope.kind == "calendar_period" or ...`），月期间 [Mar 1, Mar 31] 恒精确。
- **calendar_span 关闭 29 天通道**：枚举器 56-57 强制 `start_inclusive 且 end_inclusive`，否则 `frequency_calendar_span_endpoints_unresolved`（fail-closed）；满足时 `raw_end = following − 1天`（113-114）→ 滑动窗恰为 duration 个日历日（“连续4周”=28 天）✓。我上轮指出的 (true,true)→29 天无声漂移被该强制条件封死。
- **boundary_offset 保留显式历时边界语义**：`raw_end = following`（114 else 支）＋声明开闭——(true,true) 的 29 天现在是**一等的来源声明选择**（记录在 scope 与 window_sha256 覆盖的 trace 内），不再是无声默认；误声明属声明保真问题，归方法评测，非隐藏缺陷。未强制半开（避免覆写来源措辞）——与 owner 决策一致。
- **未声明 → fail-closed**：`frequency_duration_basis_unresolved`（54-55），两个新原因码前端均已映射（`reviewConditionNotes.ts:28-29`）✓。
- **固定纪元月时长**：`shift_date(epoch, value*n)` 非迭代（109）保持不变——纪元=1月31日时各期边界 2/28、3/31 各自从纪元直接推得，无累积漂移；boundary_offset 下月长随日历月自然变化，属声明语义 ✓。
- **full_only 排除留痕入报告**：`excluded_partial_periods` 在 trace 初始化（36）并逐期间记录未纳入的不足周期（126-127）；呈现层计数并明示“不将其当作满足或不满足”（presentation:9-10）——**无部分期间被判 true/false** ✓，我上轮 R 观察已被采纳落实。

### 2. 新发现

无新的健全性缺陷。保留一条观察（非缺陷）：`anchored_period`＋`boundary_offset`＋双含端声明下，相邻周期共享边界日，同一事件可计入相邻两期的下界——这是声明语义的固有结果，prompt（control:1296“时间界限”）已要求按原文声明；归属保真由方法评测检验，不需要代码层强制。

**边界更正**：F1 的正确修复形态是显式 basis 三值而非强制半开——已按现行源码确认。除此之外我上一轮对量化枚举器、包装器见证政策、hash 闭包的核验结论不变。

**非声明**：仍属未执行的 v4 增量，无运行时身份变化；仅编译/tsc 级事实，无运行/写入/临床访问；不构成方法批准或完成宣告。会话保持可续。
