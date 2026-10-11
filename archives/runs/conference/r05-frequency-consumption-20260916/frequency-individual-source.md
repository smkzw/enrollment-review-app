# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`frequency_individual_qualification.py`（63 行全读）、`frequency_period_qualification.py` 现行结构、`contracts/frequency_evidence.py` v3 段、`llm/frequency_evidence.py` v3 段、`qualified_frequency_evidence.py`（consumer4）、`frequency_total_resolution.py` v2、`frequency_review_presentation.py`、receipts 版本段。仅审本增量；既有消费者仍未获临床接受。

---

### 1. 健全性核验（evidence，逐条验算通过）

- **下界构造健全**：`qualify_individual_occurrences` 只在“确定在窗内”的组上取显式 distinct 团（`frequency_individual_qualification.py:52-55`）——团内每员都是可证在窗内的发生，逐对显式异次→组内不同发生数 ≥ 团大小。位置判定用全端点可能世界的最严测试：inside ⇒ `lower ≥ max(starts) 且 upper ≤ min(ends)`（对每个世界都在窗内，43-44）；outside ⇒ 对每个世界都在窗外（46-47）；其余 unresolved 不计也不排除 ✓。distinct 边若任一端不在窗内不参与计数（53-54）——正确（窗外组不贡献窗内下界）。
- **同次合并与日期同一性**：合并组日期 = 成员 occurrence_date 界的交集（36-39）；交集为空→`frequency_same_occurrence_date_conflict`（40-41，同次声明日期不相交=矛盾，正确）；**无日期成员不加约束**（dates 列表只收有日期者）——缺日期既不当冲突也不当在窗/窗外 ✓。来源同一性：occurrence_date 仅 individual_occurrence 可带（`frequency_evidence.py:119-120` 拒绝汇总/未决携带）、excerpt 逐字且过 pair 定位包含校验（llm:118-119）与消费侧 `quote_reasons`（`qualified_frequency_evidence.py:82`）；prompt 明令“就诊/抄录/报告日期≠发生日期，不从前后记录补年份或具体日”（llm:71-72）；source_key 纳入 occurrence_date 哈希（contract:93）→跨路一致覆盖该字段 ✓。**未复制 fact.date_range**（模块只吃 statement dumps）。
- **上界**：`enumeration_complete=False` 恒定、`upper` 显式 None（56）——缺失列举≠完整列举 ✓。
- **resolution v2 交集**：individual `[k,None]` 与总数界走 `intersect_count_bounds`（65），永不相加；交集 None→`occurrence_count_bounds_conflict`（如“共N次”与已证 k>N 矛盾→显式冲突）✓；individual 路径强制 unit=occurrences（40，`frequency_detail_period_reconciliation_pending`+原因透传）——**天数仍不支持，未把发生数当活动天数** ✓；`statement_sources` 保留 kind/occurrence_date 逐条原记录，used_fact_ids 覆盖全部来源事实（70）✓。
- **接口/键匹配**：links 的 `[relation, left, right]` 解包与 compose 输出一致；links 端点已被 consumer 门限在 accepted 内（:96），故传入 `bound_distinct_occurrences` 的 pair 必然落在 rows 键内（合同禁止跨 kind 关系）——无键失配；`FrequencySourceDate.model_validate` 对 dump 反序列化 ✓。
- **版本无陈旧**：prompt/合同 `frequency-evidence/v3`（Literal 兼容读 v1/v2＋pop）、summary `v3`、consumer `v4`、individual 计算 `v1`、period 计算 `v2`——`verify_completed_content_job` 钉 prompt_version，旧 summary 重建即失配关闭。
- **抽取忠实**：`required_frequency_period`（`frequency_period_qualification.py:30-64`）与原内联逻辑逐行等价（scope 门→锚点解析＋provenance→shift→端点枚举），`_qualify_total_period` 改为调用共享函数并合并 trace（anchor_provenance/required_boundaries 保留）——算术无变化 ✓；individual 路径复用同一函数，两路要求窗口语义一致。

### 2. 发现（均为观察级，无健全性缺陷）

- **R1'（cosmetic）** `frequency_individual_qualification.py:62-63` 的日历异常路径返回**新建 dict，缺 window_sha256/episode_sha256**，与其他返回路径的 trace 形状不一致。仅元数据不齐（resolution 整体哈希仍闭合），最小处置：改为 `{**trace, "bounds": None, "reason_codes": [...]}` 同型返回。
- **R2'（观察）** 部分精度锚/日期下 definite-inside 判定会很严（组日期界须落在 `max(starts)/min(ends)` 内）→ 下界常缺、UNKNOWN 常见。方向保守正确；建议方法评测记录该路径的判定率，不为通过而放宽“全部世界”语义。
- **R3'（观察）** 呈现层对 individual 组的 membership/date_bounds 细节未上报告（仅 bounds 汇总与来源标签区分“原文逐次记载”，`frequency_review_presentation.py:22-23`）——trace 已持久化可供下钻，可接受。

**非声明**：本增量仍未构成逐次-汇总对账（individual 与 total 并存时是交集约束而非对账）、不支持逐次天数、消费者未注册临床采信；仅编译级事实，无运行/写入/临床访问；方法批准与最终验收归 Codex/owner。会话保持可续。
