Trellis SessionStart 上下文已加载。开始定向首错只读审阅（基线 5749dd12；上限 12 次读取；不跑测试/模型/服务、不写文件、不新建任务；仅工程边界意见）。先定位四组真实引用点。

定位完成（SourceScopeCorrection 452/736、validate 3186-3253、RepeatScheme 合同与三处真实消费者：control_repeat_trigger_calculation、repeat_review_presentation、repeat_observation_count）。并行读取七区。

补最后两处：来源范围校正通道的单条派发（旧提案/旧作者次数保持）与阶段/时间覆盖助手。

Trellis SessionStart 上下文已加载。定向首错只读审阅完成（12/12 次读取用尽；未运行测试/模型/服务、未写文件、不新建任务；git diff 不可用——Bash 非交互权限早前已拒、未重试；以下为工程边界意见，非临床批准）。先给两问的直接答案，再列已证/反证/未验/建议。

## 已读范围（12/12）

`protocol_control_source_interpretation.py`：198-247（`_scope_carries_stage_fragment`/`_time_words_cover_stage_label`/`_unreported_time_fragments`）、440-810（**SourceScopeCorrection 452-459、recheck 611-722、apply_source_scope_correction 736-792、提示 504-558**）、3109-3260（**validate_source_interpretation：范围/阶段/时间 3147-3224**）；`protocol_control_deconstructor.py` 7780-7845（**单条来源范围校正通道**）；`repeat_scheme.py` 全文（1-221）；`repeat_observation_count.py` 18-44；`control_repeat_trigger_calculation.py` 35-109；`repeat_review_presentation.py` 1-138；`candidate_alignment.py` 780-940（**numbers/directions/predicates 尾部 869-937**）。

## 问题 1：能否用现有来源/修订合同有据纠正"非时点标题误归阶段"

**答案：现有合同对"研究期别（I/II/III/IV 期）"可纠正，对一般标题短语（如"审核不通过的记录"）不足——删除保护会挡住，不能用本通道改正；需要一条最小接口边界。**

- 已证（通道与保护）：`correct_source_scope` 单条通道按 statement 派发、有独立额度与去重（deconstructor 7812-7813）、提案经 `apply_source_scope_correction` 后整体重验（7825-7827）、失败保留旧解释并回待核（7784-7787）——**不重读整包、不重置写入、不自动清疑问**（`correction.unresolved` 非空直接拒，747-748）已由代码证明。
- 已证（不足点）：删除保护 749-760 的判据是"旧词逐字出现在 quoted_text 或 heading_path"⇒ 不可在局部校正中删除；**不区分"动作约束时点"与"章节/人群结果标签"**，且仅对 `is_study_phase_label` 网开一面（751-752、762-782）。因此一个逐字位于 `heading_path`、被旧解释误填入 time_words/affected_stage 的非期别标题，任何"改为空"的校正都会被 750-760 拒绝；若该标题实为表头（row/column header），它本就不能通过 3191-3194/3210-3213 的接地校验（除非 scope_quote 覆盖），也不存在"合法删除"路径。`apply_source_scope_question_recheck` 原生列路径同样先走该保护（713-718），非原生列只允许改 unresolved（707）——都救不了这一类。
- 反证/边界：761-782 的期别剥离（`STUDY_PHASE_NOT_VISIT_STAGE` 3186-3189、`STUDY_PHASE_NOT_VISIT_TIME` 3202-3208 对应）说明合同**有能力**表达"期别不是访视阶段"，但仅限期别词；把它推广到任意标题需要新判据。
- 最小必要接口边界（建议，二选一，均不加关键词表）：
  - **S1a 重分类不删除（零新字段）**：当且仅当 ①该词**仅**逐字接地于 heading_path（不在 quoted_text 和动作 scope_quote 中），且 ②校正后该词**逐字保留在 `correction.scope_quote`** 中时，允许从 time_words/affected_stage 移除。正例："审核不通过的记录"（标题）→ scope_quote 保留原词、time_words=[]、affected_stage=None，动作原子"重复检查前"等真实窗口不动；危险反例：把 quoted_text 中的"重复检查前"搬进 scope_quote 再删（接地在 quoted_text ⇒ 仍拒，750-755 不变）；真实阶段"治疗期"从 heading 搬走后不保留（②不满足 ⇒ 拒）。影响消费者：`validate_source_interpretation`（3186-3224，唯一放行来自 ②的逐字保留）、`_unreported_time_fragments`（230-247，仍以动作句/scope 为准）。
  - **S1b 声明式重分类（最小字段）**：若产品不接受 S1a 对"仅 heading 接地"的真阶段也可搬移（S1a 会把 heading 里的真实阶段一并变为可搬移，只要保留在 scope_quote），则在 `SourceScopeCorrection` 增一个必填的逐字重分类声明字段（被移除词原样列出），由 750-760 校验该声明与移除集合一致；危险反例：声明字段与移除词不一致、或未声明即删——仍拒。
  - **不建议**：对该标题加关键词例外；重读整包；让校正重置旧作者次数（通道独立于作者修订计数，见"未验"）。
- 未验：作者有界修订计数与 `source_repairs` 是否完全独立（本轮只见 `source_repairs`/`seen_context_attempts` 的独立额度 7812；持久化作者标记未读）；"旧解释不被自动覆盖"由 7784-7787+验证采纳序列支撑，跨 Job 保存语义未读。

## 问题 2：RepeatScheme 能否忠实表达许可次数，且被正式消费者使用

**答案：能。合同字段与**真实**消费者齐备（非枚举名推断）：许可=`permission:"optional"`、次数=`count_status:"specified"+maximum_repeats+count_scope`、触发=`trigger:"source_condition"+trigger_condition_id+trigger_excerpt`；缺口在**对齐层的数值门**，需要一处授权字段补丁。**

- 已证（合同）：`RepeatScheme` 105-198：permission 五态（110）、count 三态+`maximum_repeats`（115-116）、`count_scope`（117）、trigger 三态+条件引用（111-114）、`permission_condition_id`（研究者裁量强制，208-209）、`no_repeat_result_use`（125、210-211"原文不明用 unresolved，不默认退回初查"）、来源逐字绑定（108-109、183-191、214-221）；一致性校验 160-197（specified⇔maximum_repeats、source_condition⇔trigger_condition_id 等）。"可重复检验1次"可逐字落为 optional+specified(1)+per_current_episode+source_condition。
- 已证（真实消费者，处理 optional/无复查/触发未知）：
  - `evaluate_repeat_count`（repeat_observation_count 18-44）：未声明次数→TRUE 且 reason `repeat_count_not_specified`（"undeclared count says nothing about permission"）；未核实/范围不符→UNKNOWN；超上限→FALSE；资料不全→UNKNOWN（部分资料永不证明合规）。
  - `calculate_control_repeat_triggers`（35-109）：以回执合格选择逐范围求值，owner 引用来自 `trigger_condition_id/permission_condition_id`（100-102），研究者书面许可单列（82-95），区分 `repeat` 与 `initial_without_repeat`（29、106）。
  - `repeat_review_presentation`（6-138）：触发未知→"尚未核清是否触发"、已触发未见复查→"已触发，但本次未见复查结果"、已核实未触发→"false"（33-35、127）；次数不全明确"不能证明未超过方案上限"（28-30、95-96）；permission/count/time 检查各有 unknown 态（97-104）。
  - 旁置角色语义（grep 实证）：`binding_qualification.py:178-179`"repeat_trigger 是旁置复查条件，不是新增入排要求"。
- 已证（缺口位置）：`validate_candidate_alignment` 数值尾部把**任何数字**当比较——单数字+单方向+无 predicate → `CandidateNumericAlignmentError`（869-879）；有数字则要求恰 1 数字+1 方向+predicate 且逐字保留（920-937）。"可重复检验1次"无比较方向/predicate，全表达路径会以"数值原文不能由模糊比较条件宣布完整"（923）拒绝——**这是错层，不是能力缺失**。
- 最小路径（授权字段补丁，非新能力）：在数值分支增加"复查次数证明"通道——当源的数字与 `atom.evaluation.repeat_scheme.maximum_repeats` 相等、`count_status=="specified"`、且该数字逐字来自该 scheme 的 `source_excerpts`（其 trigger/scope 亦已接地）时，以复查合同满足该数字，不再要求 comparator/predicate；否则维持现门。正例："可重复检验1次"+scheme(optional,1,per_current_episode,trigger=条件甲)；危险反例："至多 3 次事件发作"（频次阈值而非检查复查）不得借道——其数字不满足"等于 scheme.maximum_repeats 且 scheme 来自本陈述"；"≥2 次"而 count_status=unresolved/mismatch→仍拒；时间窗"7 天"与任何 scheme 无关→仍走比较/窗口门。消费者：`evaluate_repeat_count`、`calculate_control_repeat_triggers`、`repeat_review_presentation`（上述已证）；影响面限于"数字∈复查合同"的窄类。
- 何时合法按既有受限记录保留：当候选无法忠实填出 repeat_scheme（count_scope/trigger 未明、或源根本没给复查许可）而数字又无法用谓词表达时——保持 incomplete/受限并保留逐字原文，不把"没有复查结构"改名成"能力缺口"，也不放宽数值门让无资格计数通过（`count_status=unresolved→UNKNOWN` 的消费者语义已证会正确悬置）。
- 未验：控制线 wire 的原子 `evaluation` 是否随 wire 携带 `repeat_scheme` 直达对齐层（control_evaluation_spec 有该字段=早前已读；控制线 wire schema 本轮未读）；若未携带，补丁应落在 hydrate 后的消费点而非 wire 对齐。

## 反证

- 可能推翻问题 1 结论：若真实案例的"标题"属表头而非 heading_path，则既不接地也不可删，结论"不足"更成立；若该标题被允许保留在 scope_quote 且产品接受 S1a 的残余（真阶段也可随 scope_quote 搬移），则 750-760 需按 S1a 精确改写——两种走向都需产品选边，不是工程可自决。
- 可能推翻问题 2 结论：若既有 direct/author wire 未把 repeat_scheme 带入控制线，则"合同能表达"仍真，但最小路径要从"对齐补丁"改为"hydrate/发布前构造点补丁"；consumer 已证存在。
- 未运行任何测试/模型；`git diff` 不可用，无法比对 5749dd12 的精确变更行。

## 建议（均附正例/危险反例/消费者）

1. 【问题 1 必修级决策点】S1a 或 S1b 二选一改动 `apply_source_scope_correction` 749-760（及校验 3186-3224 的对应负例）；消费者=范围校正通道+验证器；正例/反例见上。不改则本类误归只能靠新一轮来源读避免（owner 新证据即此），旧解释保持原样直到人工核。
2. 【问题 2 建议-必修级】candidate_alignment 869-937 增复查次数证明支路；消费者=对齐校验层（受 `_independent...`/合取检查不变）；危险反例=事件频次阈值借道。
3. 【证据边界】同时补两枚负例测试：S1a 的"quoted_text 窗口搬移仍拒"、问题 2 的"scheme 不匹配/未明仍拒"。不新增通用能力、不第四路线、不全改 unknown。

本轮只读、未新建任务；如需确认"控制线 wire 是否携带 repeat_scheme"这一末项未验点，可在下一窗口只读对应 schema/构造点定义后再定补丁落点。
