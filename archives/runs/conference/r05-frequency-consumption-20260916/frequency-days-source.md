# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮仅读 individual_day 扩展涉及文件（contract v4、llm v4、receipts summary v4、consumer v5、`frequency_individual_qualification.py` 全文、resolution 日界段、presentation）。仅编译级事实；仍未获临床接受。

**先认领更正**：我上轮 R1'（“occurrence 异常路径丢 window/episode 哈希”）不成立——现行代码全部错误路径均为 `{**trace, ...}` 展开（`frequency_individual_qualification.py:71,81,88,113`），trace 字段完整。撤回该发现。

---

### 1. 逐日扩展核验（evidence，逐条验算通过）

- **语义类型分立**：`individual_day` 为独立 statement kind（`frequency_evidence.py:76`），强制 `count_unit=="days"`（119-120“单日记载只能用于发生天数，不能充作独立发作次数”）、count 恒 None（落既有“不能由模型补算次数”分支）、`occurrence_date` 仅两种 individual kind 可带（121-122）、period 仍仅限 stated_total；关系图校验的端点集合仍仅 individual_occurrence——**逐日记载不进同次/异次关系**，与 prompt“同日重复记载由代码按日核对，不由模型加总”（llm:77）一致。次数与天数在类型层不可混用。
- **stabbing 下界健全**（`frequency_individual_qualification.py:103-108`）：按右端点排序的经典贪心最小点覆盖——`last=upper` 放点、`lower > last` 才计新日。数学事实：真实逐日指派的不同日数 ≥ 最小 stabbing 数（真值是某个一致指派，最小一致指派即下界）。部分精度日期供给**一个可能日所在区间**而非整段活动日（docstring 69 明示），日精度退化为单点 ✓。重复排序键 `(upper, lower, key)` 确定性可复现 ✓。
- **在窗判定与逐次路径同语义**：inside ⇒ 对全部端点可能世界都在窗内（96-97）；outside ⇒ 全世界都在窗外；未知不计不排除（93-100）。全在窗外的记录集产生 `{lower:0, upper:None}`——**不违反“未知≠零”**：0 只是“这些已核实记录贡献 0 天”的真命题，交集取 max 后从不压低合计下界；单独存在时对任意阈值 gte→UNKNOWN、lte→上界 None 亦 UNKNOWN，不可能借它证合规 ✓。上界恒 None、`enumeration_complete=False`——未知覆盖≠完整列举 ✓。
- **不发布选定日期**：trace 只含逐条 membership/date_bounds 与日数（101-102, 108），无任何日期指派输出 ✓（docstring 71 明示）。
- **resolution 集成**：日界与总数界走同一 `intervals` 列表交集（`frequency_total_resolution.py:43-52`），**不相加**；混合单位组（如次数总数+逐日记载并存）落 `frequency_count_unit_unresolved`——保守正确（跨单位不可比较、不折算）；日路径缺失/异常原因透传 ✓。
- **来源资格与版本**：occurrence_date excerpt 过 pair 定位包含＋`quote_reasons`（consumer v5，`qualified_frequency_evidence.py:82`）；source_key 含日期哈希→跨路一致覆盖；contract v4（Literal v1–v4 读旧＋pop）、summary v4、prompt v4、`frequency-day-calculation/v1`——`verify_completed_content_job` 钉 prompt_version，旧 summary 重建即失配，无陈旧版本混入 ✓。
- **呈现正确性**：`"individual_day": "原文发生日记载"` 独立标签（presentation:22）；bounds 注释沿用“至少可确认N天”措辞，与 stabbing 语义一致；政策锚出处集合已并入 day_calculation ✓。

### 2. 发现

无健全性缺陷、无接口/键失配、无来源丢失。两条观察（无需改动）：(a) 同组并存次数类与天数类记载时整组 `frequency_count_unit_unresolved`——保守正确，将来若分单位并行消费需显式设计，不得折算；(b) 全无日期的 individual_day 记录只能停留 unresolved——诚实边界，补齐需新的日期来源而非猜测。

**非声明**：逐日下界为“已核实显式单日记载”的最小一致日数，不证明病史完整；该路径未获方法批准与临床接受；仅编译级事实，无运行/写入/临床访问。会话保持可续。
