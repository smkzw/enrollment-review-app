All evidence is gathered. Returning the complete conference report.

# Conference Output: r05-conditional-observations-20260915 - evidence_single_object

## Output

只读源码审阅（未写/运行测试、未import应用、未访问DB、未启动任何服务、未读取workspace外资料、未修改源码；本报告不是临床验收，Codex保留最终采信权）。所有行号基于当前工作树 `.worktrees/phase5-clinical-facts-profile`。

### 一、总裁决（先说结论）

1. **occurrence/prospective 的 UNKNOWN 保护本身接线正确且覆盖两条主链**，但**存在一个具体缺陷**：官方条款链的新原因码 `occurrence_scope_unverified`/`prospective_scope_unverified` 未进入 `REASON_GAPS` 映射，UNKNOWN 会被兜底归类为 `RECORD_INCOMPLETE`（记录不完整），把“频次/未来期间语义尚未核实”与“记录不完整”混为一谈——这正是项目指令明令禁止的缺口原因合并。修复约2行。
2. **条件性复查、发生次数、未来期间三者应走三条不同的最小消费路径**，全部可复用既有 来源资格（binding_qualification）→ 语义内容（proposition_evidence/judgment_content）→ 冻结消费（qualified_binding_selection → frozen_review_calculation → 四层组合/evaluate_component → 报告）链，不需要新建任何平行合同。唯一的合同扩展点是 `ObservationOrdering` 增加方案声明的复查方案（declared repeat scheme），且必须与确定性选择器扩展成对落地，避免孤立合同。
3. 保护性 UNKNOWN 目前是**未提交的工作树改动**（见下），审阅结论针对该状态。

### 二、证据基础（观察，附行号）

**保护现状核查：**

- 官方条款链：`app/domain/expression.py:478-481` — `_evaluate_atomic` 在 `occurrence_window` 非空时返回 UNKNOWN/`occurrence_scope_unverified`，`prospective_window`/`prospective_period` 非空时返回 UNKNOWN/`prospective_scope_unverified`。该守卫先于事实匹配、选择清单与数值比较，fail-safe 正确。
- 控制链：`app/projections/control_operand_calculation.py:82-87` — spec.predicate 带 occurrence/prospective 任一字段或原子级 `prospective_period` 时返回 `unresolved_reason="频次或未来期间仍需独立核实"`/`"未来期间仍需独立核实"`；该 unresolved 经 `app/projections/control_calculation_experiment.py:140-144`（`_conditional_observation` 首行）转为 UNKNOWN，并经 `app/projections/control_review_outcome.py:44-48,86-87` 进入 `unresolved_atoms`/`observation_reason_codes`，报告侧逐原子保留。覆盖完整。
- 纯值比较：`app/domain/expression.py:456-472` `evaluate_observed_value` 本身不看 occurrence 字段（docstring 明示“值计算而已，来源/对象/时间选择归调用方”）。**不构成漏洞**，因为两个守卫都在其上游；但它意味着任何新增消费入口（如未来给复查方案加的求值）必须自带 occurrence 检查，不能裸调该函数后当结论。
- 解构侧结构保证：`app/domain/contracts/rules.py:237-249` 强制 occurrence_window 只能与“次”/天数单位数值谓词或 `minimum_count` 配套；`app/protocols/deconstruction_gate.py:1099-1146` 校验频率结构从原文保留。未来期间锚点限定见 `rules.py:168-176`。

**未提交状态（观察）**：`git status` 显示 `app/domain/expression.py` 为已修改未提交（diff 含 ：478-481 守卫），`app/domain/contracts/observation_selection.py`、`app/projections/control_operand_calculation.py`、`app/services/ordered_observation_selection.py` 为新增未跟踪文件。与恢复计划T3（`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md:79`“已接源码……无新增采用批准”）一致。

**关键缺陷（证据）**：`app/domain/gates/assessment.py:206-220` 的 `REASON_GAPS` 无上述两个新原因码；`assessment.py:307-318` 只映射表内码，`assessment.py:320-329` 触发UNKNOWN且无缺口时兜底 `RECORD_INCOMPLETE`。该路径是官方条款唯一缺口派生入口（`app/services/component_review.py:42` 复用同一函数），冻结审核同样经 `app/services/frozen_review_calculation.py:258-276` 走到此。结论：含频次/未来期间谓词的官方组件会被报告为“记录不完整”，语义错标。

**选择/资格链现状（复用基础）**：

- 资格链按 `(identity, fact, attribute)` 逐对核实，属性枚举含 `value/date_range/record_time/assertion_basis`（`app/domain/contracts/binding_qualification.py:97,253`；候选侧 `app/llm/predicate_binding_candidates.py:58`）——**逐事件合格日期已可由既有链产出**，发生次数消费不需要新资格合同。
- 观察选择政策：`app/domain/contracts/observation_selection.py:40-53`（仅 latest/earliest + window_order）、`63-87`（single/any/all/unresolved + 逐字原文强制）；确定性唯一主导选择在 `app/services/ordered_observation_selection.py:44-112`（严格区间主导、同日并列保持未定，符合所有者对“同日≥即主导”的否决）。
- 消费链：`app/services/qualified_binding_selection.py:274-327`（`_select_with_ordering` 把排序审计接入资格选择）、`368-692`（回执核实工厂）、`app/services/frozen_review_calculation.py:141-305`（冻结整审计算，官方+控制双族强制同备）、`app/projections/control_calculation_experiment.py:174-359`（四层组合，政策化聚合 + 作用域完整性未证不合成）。

### 三、端到端最小消费设计（建议，区分三条路径）

**总原则**（对应“不得以日期顺序或计数推定许可”）：
- **许可只来自方案声明的政策/方案字段**（携带逐字 source_excerpts，受 `rules.py:216-220` 同款“原文内包含”校验约束）；日期顺序只在方案已声明复查方案后用于**角色指派**（谁初查谁复查），绝不用于推断“是否允许复查”；可用事实条数超出方案允许次数时保持未定并逐条留 not_selected 原因，绝不静默择优。
- 不新增项目/药物/疾病分支；所有新判断维度沿用 `BindingQualificationJudgment` 的结构化双路一致模式（`binding_qualification.py:162-202`）。

**B1 条件性复查（declared repeat scheme）——最小且优先**
- 方案触发：复查方案的触发条件（如“初查异常且有临床意义”）表达为对同身份/兄弟谓词的显式引用（复用 §17.3 atom_refs 模式），初查的“异常”用既有数值比较求值；“有临床意义”类专业判断成分走既有 requires_professional_judgment/judgment_content 链（决策点Q2）。
- 许可：`ObservationOrdering` 扩展 `criterion="declared_repeat"` + 方案对象（允许次数上限、替代或聚合方式、触发引用、时限），全部带原文。超过允许次数的观察 → 未定 + `not_selected` 原因（新增 reason 字面量，不新增顶层合同）。
- 时限：复用 `TimeConstraint`/`evaluate_time_constraint`（`expression.py:298-453`），锚点为初查事件日期或命名锚点；部分日期沿用区间端点组合语义。
- 初查/复查关系：日期只做角色指派；同身份同对象由既有逐事实资格保证；冲突事实沿 `conflict_by_fact` 保留 source_conflict（`ordered_observation_selection.py:67-68` 已有）。
- 替代聚合：`declared_repeat`（复查替代初查，选主结果）与既有 `any`/`all`（聚合）并列，均方案声明；`select_ordered_observation` 增加对应分支，审计仍写入现有 `OrderedObservationAudit` 形状。
- 报告：选中/未选中及原因已有持久位（`observation_selection.py:14-37`；`control_review_outcome.py:97-98`），仅扩 reason 枚举。

**B2 发生次数（occurrence counting，官方条款先行）**
- 前提：谓词已带 `occurrence_window`（结构由解构门保证）；资格链对每条候选事件产出合格 `value` + 合格 `date_range` 对。
- 选择层：`_select_facts_for_identity`（`qualified_binding_selection.py:227-241`）目前对>1值事实无政策即拒（`multiple_usable_pairs_without_selection_policy`）。为 occurrence 谓词增加一条“计数集合直通”分支：全部合格值+合格日期事实整体带入（沿用 `observation_scope_reasons` 的双路账目核查），消费算法版本 v11→v12。
- 求值层：`_evaluate_atomic` 的 occurrence 守卫改为**有显式选择清单时进入确定性计数分支**：按合格事件日期在滚动 `duration` 窗内计数，与 comparator+value 比较；日精度不满或部分日期跨界 → UNKNOWN（沿用 `_calendar_bound_truth` 端点组合思路）。
- **真值方向性（关键边界）**：TRUE 方向由见证集合即可成立（存在语义）；FALSE 方向（“不足N次”）要求窗口内事件枚举完整，而所有者已否决“已提出配对全集就是观察全集”（§17.2，设计文档：318）。故本切片 FALSE 一律 UNKNOWN/`occurrence_scope_completeness_unverified`（与 `control_calculation_experiment.py:85` 的既有模式一致），除非未来另有批准的完整性证明。无选择清单（旧 fact_type 路径）守卫保持 UNKNOWN 不变。
- 控制族 occurrence（spec.predicate 带 occurrence_window）：`calculate_control_operands` 守卫保持；跨观察计数需在 `_conditional_truth` 加 occurrence 分支，**建议列入后续切片**，避免本切片同时动两层。

**B3 未来期间（prospective）**
- 本质是意图/计划命题，不是确定性行为预言：TRUE/FALSE 都只能来自被核实的书面声明内容，不来自日期或既往事实。
- 控制族：现有 semantic/investigator_judgment 模式 + proposition_evidence 链（`qualified_binding_selection.py:412-435`）+ `_proposition_observation`/`_conditional_truth` 的 individual/universal 断言辖域（`control_calculation_experiment.py:40-137`）**已经足以表达**“受试者声明无怀孕计划”的个体断言与相反冲突；period 边界作为义务/随访信息随 `ControlObligationOutcome` 报告，不当判定。方案原文政策未知时保持 unresolved。
- 官方族：`proposition_evidence` 目前绑定 control 族（`qualified_binding_selection.py:225-226` 强制），官方 prospective 谓词本切片**保持 UNKNOWN 守卫不撤**，等待 §17.2（设计文档：328）已声明的“非确定性命题求值独立明确结果合同”——提前撤守卫或临时借用 judgment_content 语义（其现义是研究者评估来源的书面判断核实，设计文档：346）都会改变链的临床含义（决策点Q1）。

**报告链（三者共用）**：`frozen_review_publication` / `component_review` / `control_review_outcome` 均已按原子/谓词保留 reason_codes、used_fact_ids 与未选记录；本设计只需新增 reason 字面量与（B2）缺口类型映射，不新增报告合同。

### 四、最小文件改动清单（建议，非实施授权）

| # | 文件 | 改动性质 | 量级 |
|---|---|---|---|
| 1 | `app/domain/gates/assessment.py` | REASON_GAPS 增两码→`OBSERVATION_UNVERIFIED` | ~2行，独立可先行 |
| 2 | `app/domain/contracts/observation_selection.py` | ObservationOrdering 增 declared_repeat 方案字段（版本感知序列化，仿 window_order） | 小 |
| 3 | `app/services/ordered_observation_selection.py` | declared_repeat 确定性分支：角色指派、次数上限、时限、触发核对、超额未定 | 中 |
| 4 | `app/services/qualified_binding_selection.py` | `_select_with_ordering`/`_select_facts_for_identity` 透传复查方案与 occurrence 计数集合 | 中 |
| 5 | `app/domain/contracts/qualified_binding_selection.py` | 消费算法 v11→v12（选择语义变化按惯例隔离旧批准） | 小 |
| 6 | `app/domain/expression.py` | occurrence 守卫改条件分支：有清单→计数（TRUE见证/FALSE未定）；无清单守卫不变 | 中 |
| 7 | `app/agents/protocol_deconstructor.py` + `app/protocols/deconstruction_gate.py` | wire schema 自动携带（`:576-584`）；门校验新方案原文与配套 | 小 |
| 8 | `app/services/frozen_review_calculation.py` | 仅 EVALUATOR_VERSION v14→v15（若 evaluate_component 语义变更） | 1行 |

版本升级、迁移与“最终集中验证前不写/不运行阶段测试”按既有边界执行；B1/B2 分两批落地，每批与对应发布门版本同事务。

### 五、未能完成/不应完成的边界（明确声明）

- 本报告为静态源码审阅；未运行任何验证，行号仅对当前工作树有效。
- occurrence FALSE 方向的完整性证明：所有者已否决配对全集=观察全集，本设计不为其造新合同；FALSE 保持不可达是刻意边界。
- 官方族 prospective 的求值合同未设计（见Q1）；控制族 occurrence 计数、复查方案含专业判断触发的完整语义（见Q2）列为后续切片。
- REASON_GAPS 修复建议落地前，现网含频次谓词的官方组件会继续错标 RECORD_INCOMPLETE——这是当前真实用户可见缺陷，应优先处理。
- 未涉及前端展示、迁移编号、真实双模型与原件验证；均属 Codex/最终集中验证职权。

### 六、最重要异议与决策点（主动质询）

1. **异议（最高影响）**：设计文档 §17.2（:320）称条件性复查“须核触发条件、允许次数、时限、初查/复查关系及替代或聚合方式”，但 `ObservationOrdering` 只有 latest/earliest——若直接用 `latest` 实现复查替代，就是被明令禁止的“以日期顺序推定许可”。**任何实现不得走这条捷径**；declared_repeat 必须先有方案声明字段，再有选择器分支（上表#2/#3必须成对）。
2. **异议**：新增守卫码未接入缺口映射即接入计算链，属于“半截接线”——建议#1先独立合入，避免报告语义错标随批次放大。
3. **决策点Q1（有界问题）**：官方族 prospective 谓词本切片保持 UNKNOWN、待 §17.2 非确定性命题合同（方案a，安全、推荐），还是扩展 judgment_content 链含义覆盖受试者声明（方案b，改变链的临床语义，需用户与方法批准）？此选择决定 B3 是否能在官方族落地。
4. **决策点Q2（有界问题）**：复查方案的触发含专业判断成分（“有临床意义”）时，复用初查谓词的 requires_professional_judgment/judgment_content 链，还是在方案对象内做 atom_refs 式兄弟谓词引用？前者零新合同但把判断义务挂在初查谓词上，后者更显式但多一层引用校验。请Codex裁定。
5. **决策点Q3（有界问题）**：occurrence FALSE 侧是否维持本切片不可达？若Codex要求现在设计完整性证明，须先回答“什么证据能证明窗口内枚举完整”而不回到被否决的配对全集论。

### 七、不确定性与恢复点

- 推断（非源码事实）：#1 修复后 `derive_component_decision` 对该类组件将走 INDETERMINATE+OBSERVATION_UNVERIFIED（基于 `assessment.py:333-340` 静态读出，未运行验证）。
- 报告中所有“已可复用/足以表达”的判断基于合同与服务静态审阅；实际双路模型能否稳定产出 declared_repeat 所需声明未经评测（本会商无权启动）。
- 若Codex需要我继续：可就 #2/#3 的合同字段级草案、或 Q1–Q3 裁定后的修订路径做同会话补充审阅。
