# 会议输出：r05-frequency-consumption-20260916 - evidence_single_object

## 输出

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮完整读取：`frequency_period.py`、`frequency_evidence.py`（v2 现状）、`frequency_period_qualification.py`、`occurrence_count_bounds.py`、`occurrence_evidence_bounds.py`、`qualified_frequency_evidence.py`、`frequency_total_resolution.py`、`frequency_atom_calculation.py`、`frozen_review_calculation.py` 频次接线段、`qualified_binding_selection.py` 选择段、`control_calculation_experiment.py` 频次段、`expression.py` 频次分支、`AnchorType`/`ReviewEpisode` 类型定义。**父注册、授权签发、辅助-复查条件频次、完整报告呈现按声明未完成，不在此索求。**

**先承认两处更正**：(a) 我上轮认可 `bound_stated_total` 部分重叠→None 时的反例写错了——[1–6月]=N 对要求[3–4月]是 W⊆P，`count(W)≤N` 成立且代码 `[0,N]` 分支正确处理；只有 **W⊄P 的非包含重叠**才失去上界，该情形代码返回 None 同样正确。(b) 撤回"穷举最大团"建议——现行贪心团（`occurrence_evidence_bounds.py:58-72`，确定性序+位掩码）是健全见证下界，不宣称最大；紧致性差异只是方法评测的观测项。

---

### 1. 健全性核验（evidence，逐一验算通过）

- **计数不等式**（`occurrence_evidence_bounds.py:96-110`）：eq→[N,N]；gte/gt→[N+δ,∞)；lte/lt→[0,N−δ]。三分支对三种包含关系：相等→原样；P⊆W→保留下界弃上界（`[N+δ,None]`/`[0,None]`——后者对 lte 是正确退化）；P⊇W→保留上界弃下界（`[0,N]`/`[0,N−δ]`——lte 情形这正是可证假方向）。部分重叠→None。全部方向健全，无方向盲 TRUE。
- **部分日期组合**（`frequency_period_qualification.py:75-87`）：全端点组合（≤16）逐个调 `bound_stated_total`，任一组合 None→整体 unresolved（无界世界中计数可为 0，任何部分主张都不健全——正确）；全有界时取 hull `[min lower, max upper]`——"唯一真世界"语义下 hull⊇可能集，`evaluate_count_bounds` 要求区间内全部计数同真值→保守健全。开闭端 ±1 天对部分精度两点同时平移（73-74）正确。
- **锚点区分**：方案命名锚走 `scope.anchor_type`＋`anchor_provenance{source: protocol}`；`unanchored_lookback`（occurrence_scope v2 新 kind，已入双族 wire+gate）按 `episode.stage` 映射 `screening_date`/`baseline_date`（枚举值核实一致，`enums.py:48-49`），provenance 记 `{source: application_policy, policy_identity: "unnamed-lookback/current-screening-baseline/v1", stage, workflow_stage_id}`（`frequency_period_qualification.py:39-47`）；其他期别→`frequency_application_node_unresolved` 关闭。政策锚只进 trace/resolution，不回写来源合同——符合"保存应用政策出处、不伪造方案措辞"。声明侧 `anchor_relative` 禁用 `REVIEW_NODE_DATE`/`EVENT_DATE` 作总数计数锚（`frequency_period.py:50-51`），与枚举注释（`enums.py:56-63`）的严格解释一致。
- **未知≠零**：无总数→`frequency_total_not_available`；争议/未决/notes→`frequency_sources_unresolved`；逐次存在→`frequency_detail_period_reconciliation_pending`；外层时间约束→`frequency_outer_window_combination_unresolved`。观察值仅在单点区间时给出（`frequency_total_resolution.py:62`），不造点值。
- **列举完整性**：`enumeration_complete` 在资格输出恒 False（`qualified_frequency_evidence.py:126`），缺失列举→上界 None＋`occurrence_enumeration_incomplete`；distinct 边落同组→`occurrence_identity_conflict` 整体 None（`occurrence_evidence_bounds.py:54-55`）。
- **来源完整性**：period 各 quote ⊆ period_excerpt（合同 117-118）⊆ locator excerpt（llm 校验 111-114）；`calculate_frequency_atoms:19-33` 校验 context/authority/锚点/事实逐字段等同＋定位闭合；冲突事实→`source_conflict` 覆盖（75-76）。
- **双族消费**：官方 `expression.py:692-710` 镜像 repeat 校验（键⊆窗口原子且非 repeat/非研究判断、与 repeat/proposition 映射互斥、三哈希、used==selections、未核实强制 UNKNOWN），`_evaluate_atomic:505` 原样保留（未绑定原子仍 UNKNOWN——无回归）；控制 `control_calculation_experiment.py:212-230`（仅 deterministic＋窗口＋非 repeat/PJ）+ `:354` 结果替代判定；`frozen_review_calculation.py:281-303` 双族装配，被消费的 control 身份从普通选择/未决/关系集中移除——无双重消费。
- **版本**：`frequency-evidence/v2` 常量＋v1/v2 双 Literal 读旧＋v1 载荷 pop 序列化（`frequency_evidence.py:92-99`）＋新批强制当前版（llm:44）＋仅当前版强制 count_relation/period（llm:103-109）；`OccurrenceScope` v2 同型处置。旧身份可读。

**结论**：未发现不健全的正面判定通路。TRUE 只能经过：方法采用授权（`qualified_binding_selection.py:486-497` 的 `authorization.frequency_evidence` 门）→双路一致→逐 quote 来源资格→无争议无 notes→期间界可解析→计数越界的完整链条，每层失败关闭。

---

### 2. 发现的残余（全部 fail-closed，非不健全；最小处置建议）

- **R1** `frequency_period_qualification.py:119-122`：对全部 stated_total 计算期间界（不分 count_unit），单位不匹配在 resolve 层才拦（`frequency_total_resolution.py:39-40`）——仅浪费计算，无健全性问题；可选在资格层按谓词单位过滤。
- **R2** 声明侧 `anchor_relative` 的锚必须在冻结 episode.anchor_dates 中（`frequency_period_qualification.py:67-69`→`frequency_statement_anchor_missing`）——病例记载的锚（如"确诊后3年"而确诊日非冻结锚）永远无法资格化。诚实边界；若将来放宽，须新增锚事实来源合同，不属本增量。
- **R3** 部分精度日期下 hull 常塌缩为宽/无上界（如 eq＋混合包含关系→`[0,None]`）——健全但常不可判定；建议方法评测记录实际紧致率，不为通过而放宽组合语义。
- **R4** `unresolved_notes` 取双路并集整组阻断（`qualified_frequency_evidence.py:125`）——即使 note 涉及组内无关配对。保守方向正确，v1 接受；若日后细化须逐 note 归属，不得静默丢弃。
- **R5** 旧规则修订（无 scope 时代）理论上可载 repeat_scheme×occurrence_window 谓词进频次任务输入，到 `frequency_atom_calculation.py:58-60` 才拒绝——fail-closed 且新解构不可能产生该组合（scope 存在即禁混用），仅提示存量迁移前不采纳频次授权即可。

**无回归**：所有新映射默认 None、空时 pop、`_evaluate_atomic`/repeat/proposition 校验未动、`OccurrenceScope` v2 双 Literal 读旧。

**标注**：§1 为 evidence（file:line，算术为逐步验算）；§2 为 recommendation；父注册、授权签发、辅助-复查频次、报告呈现仍按声明待建，本报告不构成任何验收。会话保持可续。
