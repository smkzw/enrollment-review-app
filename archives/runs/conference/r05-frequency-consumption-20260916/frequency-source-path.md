# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同一角色，仍以 `zcode`/`GLM-5.3-Flash`（effort max）执行 fallback；只读边界同前。本轮完整读取：`frequency_evidence.py`（合同 162 行）、`llm/frequency_evidence.py`、`frequency_evidence_input/receipts/job.py`、`occurrence_count_bounds.py`、`frequency_method_evaluation.py`、`review_method_evidence.py`、`content_job_verification.py`、`judgment_content_job.py`（373 行执行器全读）、`binding_qualification_prompt_payload`，及 gate/rules/control prompt 的更正段。**确认：该任务未注册、未父接线、无任何消费者；所有 accepted/authorized_clinical_adoption/clinically_qualified 标志硬编码 False 且验证器强制——非临床验收，也不得被描述为验收。**

---

### 0. 更正承认（runner 三处指正全部属实，其中一处是我第二轮未重读的陈旧重复）

1. **“每…N次不认”已过时**：现行 `every_period_day_pattern`（`deconstruction_gate.py:1053-1057`）为 `每\s*(?P<duration>\d+)?\s*(unit)`＋`count_unit: 天|日|次`——可选数值时长且已接受“次”。我第一轮读到的旧版确实只有 `天|日`，但第二轮报告未重读函数就重复该主张，是我的错误。
2. **`FREQUENCY_SOURCE_FORM_UNVERIFIED` 已存在**（gate:2283-2290）：未匹配形态不再落入误导性的 NOT_IN_SOURCE，文案明确“形式识别未匹配不等于原文没有该要求，不得为通过检查而删除频次限制”。
3. **scope 校验已无条件**（gate:2262）：对一切 `occurrence_window.scope is None` 报 `FREQUENCY_SCOPE_NOT_DECLARED`，不再以正则命中为前提——我第二轮 §3-a 的补救建议已按建议实现。控制 prompt 亦已补 occurrence/scope 摆放指引并与顶层混用禁令一致（`protocol_control_deconstructor.py:1282-1286`：“频次期间已声明时 evaluation.observation_policy 和 repeat_scheme 均为 null”）。

---

### 1. 频次来源路径审阅（evidence，file:line）

**1.1 接口闭合（全部通过）**
- **执行器钩子全匹配**：`FrequencyEvidenceJobExecutor` 的 pair_model/coverage_fields/六钩子/step/empty/summary 名与 `JudgmentContentJobExecutor` 及 `_enqueue_content_job`（`judgment_content_job.py:63-147`）的额度（65536–131072）、双模型、空配对零调用路径（111-119，`empty_name` 保存 `no_frequency_sources_in_candidate_input` 覆盖）完全一致；步骤依赖、取消、回执（`recorded` 请求/响应 sha）复用共享实现。
- **hash/rebuild 闭包**：`rebuild_frequency_evidence_input` 按全字段重建比对；`verify_completed_content_job`（`content_job_verification.py:10-55`）重放 rebuild→双路 routes→pairs 再验证→batches 重排比对→checkpoint 必须 status=unverified 且三标志 False→reconstruct→compose→与 `raw_response` 原文逐字节比对。summary 内每路再核 `(frozen_input_sha256, batch_sha256, messages_sha256)` 三元组与两模型独立性（receipts:54-65）。
- **局部序号 vs 跨路身份**（receipts:37-45）：声明身份＝`canonical_hash(source_key())`（source_pair_id+kind+count+count_unit+两摘录），关系键＝两端 source_key 哈希排序对——局部 `statement_index` 明确不作为共享身份（代码注释同义）。同意关系额外要求两端声明在双路共同集合内（73-74）。保守正确：两路摘录字符串不同即争议，无错误趋同通道。
- **多声明材料不丢**：合同允许每原文对多条 statements（`source_key` 去重仅防完全同内容重复，`frequency_evidence.py:136-137`）；prompt 明令“不得只保留最新总数”“一条来源包含多个期间须分别保留，不选有利结果”（llm:54,66）；`reviewed_source_pair_ids` 必须逐条覆盖全部成员（contract:132-133、llm:83-84）。

**1.2 更正语义已固化进生产面（evidence）**
- prompt（llm:62-64）：“不同记录日期也不能证明异次，可能是同一次事件的持续记录”“未连关系不能当作独立发生”“某月发生一次不能当作整月每天发生，发作次数也不能当发生天数”——**日期不交≠异次、点发生≠1..31活动日两条更正逐字落实**。
- 合同：`distinct_occurrence` 只能由原文声明（须双端逐字 quotes＋解释，“不得仅凭记录条数推断”，contract:110-116）；无任何日期自动证明通道；`individual_occurrence` 禁止携带 count（“逐次记录或未决内容不能由模型补算次数”，contract:93-94）；“同份原文既有总数又有逐次明细时分列，不相加”（llm:59）。
- `occurrence_count_bounds.py`：`evaluate_count_bounds` 仅当**区间内每个计数同真值**才给 TRUE/FALSE（39-71），eq 要求单点区间且整数阈值，布尔阈值被 `type()` 检查排除；`intersect_count_bounds` 矛盾返回 None（“相互矛盾的来源不能合成区间”）而非空证据。无方向盲 TRUE 见证。

**1.3 发现的缺陷/边界（按严重度；均为最小补救建议，非阻断）**

- **D1（最值得改）裸总数无界约束风险**：`stated_total` 允许 `period_excerpt=null`（“未说期间填null”）。若未来消费者把无期间总数直接转成 `count(W) ≤ N` 上界（“共3次覆盖全部历史”的直觉），会把未知期间当全史——正是“未提供记录不等于未发生”的镜像错误。**补救**：消费者侧对 null 期间总数只作引用证据＋`frequency_total_period_unverified`，不转数值界（§3 采纳为默认）。
- **D2 期间-窗口关系判定无归属**：总数→界的转换需要 P vs W 覆盖关系（⊆/⊇/＝/部分/不可判），现合同只在双路摘录里保存期间原文，分类步骤属消费者——目前无定义也无错误实现。须在消费者增量中显式定义（Q2''）。
- **D3 逐次发生的天数跨度无表达**：`individual_occurrence` 强制 count=None 且无 duration 字段——“持续五天的一次事件”无法按天数贡献。这是有意的 v1 边界（发作次数≠发生天数），但消费者必须把“按逐次记录核 N 天”类条件显式 `unresolved`（`occurrence_day_extent_unmodeled`），不得用 1 天/次近似代替。
- **D4 摘录精确一致即同意**：两路对同一声明引用不同长度的摘录 → source_key 不同 → 全部争议。保守方向正确，但会把“同义异宽引用”打成争议；v1 不修复（宁争议不趋同），方法评测时应观察该类争议率。
- **D5 `FrequencyEvidenceContext` 窗口相等校验**（contract:44）用 dict 全等比较冻结条件里的 `occurrence_window` 与上下文窗口——两处同源于同一冻结输入，序列化一致，风险低；仅提示未来若 window 增可空字段须同步两侧 pop 规则。
- **D6 未注册状态确认**：`enqueue_frequency_evidence`/`verify_completed_frequency_evidence` 仅存在于自身模块，无 workflow/API/父任务调用——与“注册和父接线是剩余工作”的声明一致。

**1.4 区间算术反例核验（针对 `occurrence_count_bounds`，通过）**
- `[3,∞)` vs gte 5 → UNKNOWN（下界3不能证≥5）✓；vs lt 5 → UNKNOWN（上限缺失）✓。
- `[3,4]` vs gte 4 → UNKNOWN、vs lte 4 → TRUE ✓；`[2,3]`∩`[4,∞)` → None（须显式冲突保留）✓。
- eq 3 on `[3,3]` → TRUE；eq 2.5 任意区间 → FALSE（非整数不可能）✓；bool 阈值被 `type()` 拒绝 ✓。
- 关键反例（针对我第二轮被修正的方案）：已核实合并组数 K 作下界的路径已不存在——合同无日期不交通道，prompt 明令未连关系≠独立发生；下界只能来自 `distinct_occurrence` 声明（见 §3 簇/团语义）。

---

### 2. 剩余不安全假设（消费计划必须继承的约束）

1. 不同/同次关系只能来自双路一致的原文明示；任何日期、同日、同值、同文件推断都不得重建（prompt/合同已禁，消费者不得另开旁路）。
2. distinct 声明**不传递**：1≠2 且 2≠3 不能推出 1≠3（1 与 3 可能同次）——下界取“声明相异图上的最大团”，不得用传递闭包或连通块计数。
3. 单条部分精度发生＝恰好 1 个未知日，不是跨度日；天数只能来自 `count_unit=days` 的声明总数。
4. 裸“每月”不蕴含公历月；`calendar_period` 的期间语义只在摘录中，消费者须核实不得默认。
5. any_consecutive 的 any/every 不可互化：∃ 型单窗可证即真，∀ 型须全覆盖否则 UNKNOWN。
6. 未知期间总数不转数值界（D1）。

---

### 3. 最小连贯的下一步接线建议（recommendation；声明消费为主，不要求阶段测试）

- **步骤1 纯函数桥**（落点 `app/domain/occurrence_evidence_bounds.py`，输入为双路同意后的封存子集）：同次边并查集合并 → 节点=合并后声明；**下界＝相异声明图最大团**（图极小，穷举即可，附健全性注释）、**上界＝合并后节点数**；`stated_total(occurrences/days)` 经期间关系分类（⊂ ⇒ ≥N；⊃ ⇒ ≤N；＝ ⇒ 单点；不可判 ⇒ `frequency_total_period_unverified`）转约束后 `intersect_count_bounds`；交为 None → `occurrence_count_bounds_conflict` 显式保留；逐次天数跨度 → `occurrence_day_extent_unmodeled`；window.scope.kind=unresolved → 全部界不应用。
- **步骤2 封存+方法批准**：`OccurrenceAtomEvaluation`（三哈希形状）；`FrequencyEvaluationManifest` 已入 `read_method_evaluation` 联合（`review_method_evidence.py:42-44`）且 kind=`frequency_statement_fidelity` 就绪，消费者用共享 `require_evaluated_binding_method`（13-29）核 consumer_algorithm_version——批准链无需新机制。
- **步骤3 双入口消费**：官方 `_evaluate_bound_predicates` 增 `occurrence_evaluations` 映射（镜像 repeat 校验、与 repeat/proposition 映射互斥），`expression.py:505` 仅为未供结果原子保留；控制 `_calculate_operand:82-85` 分支改用 `evaluate_count_bounds(comparator=predicate.comparator, threshold=predicate.value)`。
- **步骤4 注册与父接线**（runner 已声明为剩余工作）：父工作流 v6+ 子任务版本化挂 `enqueue_frequency_evidence`；报告侧新原因码独立列（期间未核/天数跨度未建模/区间冲突/范围未声明）。

**有界问题**：Q1'' 期间-窗口分类 v1 是否限于“两侧均可解析为日期区间才判定，否则 unresolved”（我的建议：是，避免文本级猜测）；Q2'' 最大团下界与“裸总数不转界”两项默认是否采纳。

**标注**：§1 为 evidence（file:line）；D5、版本衔接为 inference；§3 为 recommendation；本轮增量与建议均不构成临床、运行或方法批准，最终验收归 Codex/owner。会话保持可续。
