Evidence for the revision is complete. The candidate task supplies the full frozen fact table with per-identity forced results but no per-fact negative accounting — that is exactly where the enumeration hole lives. Reason sentences live in `frontend/src/domain/reviewConditionNotes.ts` and `app/services/eligibility_review_projection.py`. Producing the addendum now.

# Conference Output: r05-observation-selection-20260915 - evidence_single_object

## Output

### Addendum（回复所有者对 D2/D3/复查计数的否决，同一只读边界；未运行测试、未改文件）

#### A. 接受的否决与修正要点

- **D2 作为完备性证明被否决——成立。** 我原定义“有限集合 = 该身份资格可用配对”，其全集是**候选任务实际提出的配对**。经核对候选链路：候选提示把**完整冻结事实表**发给模型并强制逐身份返回（`app/llm/predicate_binding_candidates.py:40-46, 121-125, 148-149`），但输出 schema（`PredicateCandidateResult` :64-79）只有“该身份的候选清单或整体 unresolved”，**没有逐事实的‘已考虑并排除’记录**。模型漏提某条同型事实时，该事实从集合中静默消失；已知日期未合格时同样只是缺口而非显式留痕。D2 把“候选任务没提出”当成了“不存在”，这是必须修的洞。
- **复查计数否决——成立。** 计数 ≤ 上限不证明触发条件、授权关系、时序或替代语义；且 D3 的 `>=` 优势条件在同日双观察时双向同时成立，未定义唯一主导。
- **官方 any/all 不得无限期后置**、不得新增分阶段测试——均已纳入下文。

#### B. 修正后的最小来源绑定范围证明（分层，全部用既有结构）

范围证明 = 以下 P0–P3 的合取，任一层不满足即该身份 unresolved 并带具体原因码；**它证明的是“冻结上传资料内的枚举闭合”，不证明完整临床病史**。

- **P0 方案依据（不变）**：已发布要求/原子携带逐字 scope 与选择依据（政策 source_span_ids/excerpts，来源包含校验），无依据不得默认最近。
- **P1 冻结资料内枚举闭合（新增，可在现有消费端检查）**：检查点在 `build_receipt_verified_qualified_binding_selections`（`app/services/qualified_binding_selection.py:309` 起），该处同时持有 `frozen`（完整事实集）、`records`（全部配对记录，含被拒）、`summary.identity_records`。规则：对带选择判据的确定性身份，按其**已发布机器范围过滤器**（`predicate.subject + "." + predicate.attribute` 构成的 fact_type，与 `app/domain/expression.py:478` 同构）枚举冻结事实；每条命中事实必须在该身份的配对记录中出现（任意属性），否则该身份 unresolved，原因 `candidate_enumeration_incomplete`，并在 material 新增 `enumeration_gaps: list[{identity_sha256, fact_id, reason}]` 逐条留痕。事实层面无新任务、无双读改动——这是“现有冻结事实/定位 + 既有双资格审查”能達到的最小枚举证明。语义型（非确定性）身份不适用 fact_type 过滤，仍走既有 scope_correspondence / assertion_extent 通道（`app/llm/proposition_evidence.py`），边界不变。
- **P2 逐观察资格与日期闭合（细化所有者点名两洞）**：有限集合内每条 value 事实必须有同事实**已合格** date_range 配对才能参与排序；两种缺分别留痕：冻结事实本身无日期 → `ordering_date_missing`；事实有日期但日期配对未提出/未合格（“已知日期未合格”）→ `known_date_unqualified` 并携带该日期配对的被拒原因。二者均阻断该身份的 latest/earliest 选择，不静默剔除。
- **P3 窗口 + 唯一主导（修正 D3）**：先按 `evaluate_time_constraint` + 冻结 anchor 计算窗口归属（复用 `app/domain/expression.py:298` 起纯函数）；FALSE 剔除留痕、UNKNOWN 保留参与排序。优势改为**严格且唯一**：设区间 [lo, hi]，A 对 B 的 latest 优势 ⇔ `A.lo >= B.hi` 且 **非**(`B.lo >= A.hi`)。日精度下退化为 A.date > B.date 严格大于；同日或部分日期互叠（如月精度 vs 同月日精度）不构成优势。取“无被任何成员严格支配”的**顶端集**：|顶端集|=1 → 唯一主导；>1 且全部同 (value, unit, polarity) → 一致性去重后主导；否则 `observation_tie_unresolved`（同日异值）或 `observation_order_ambiguous_partial_date`（区间互叠）。若唯一主导者本身窗口 UNKNOWN → `observation_window_membership_unverified`，不回退取次优。earliest 镜像。
- **P4 明确不证明的（防伪造）**：本证明不证明未上传病史、不证明“读完全部页”等价于任何临床断言；报告文案必须限定“在本次冻结资料范围内”。**原文自述最新**（如报告写明“系最近一次复查”）是潜在证据但只能经既有命题通道逐字核实后使用，**不得由页序或覆盖度制造**；该扩展列为后续步骤（`source_recency_statement_unverified` 语义占位），不入首期。

#### C. 复查语义修正（计数只是负面护栏，不是证明）

- **可表示（简单来源授权替代）**：当方案原文逐字声明**计数无关的治理规则**（“以最近一次结果为准”，含复查后以复查为准），`selection.criterion=latest` + 逐字依据即可计算——主导地位完全由日期唯一优势决定，与观察次数无关。
- **不可表示（显式 unresolved，不装作计数解决）**：条件触发（“异常方可复查”）、复查独立时限、取高/取均值、中心实验室确认等，代码无法核实触发/授权/时序/替代关系 → 政策保持 unresolved，新增原因 `retest_semantics_not_representable`，scope 保留原文。原 D1 的 `retest.max_additional_observations` 从可计算合同中**移除**；计数至多作为记录性上下文，且仅当“方案声明的观察模式与实际集合形态矛盾”（如原文描述一次复查却出现无法识别何者为复查的多份观察）时作为**失败方向**护栏触发 unresolved（`observation_set_exceeds_declared_basis`），永不作为授权成立的正向证明。

#### D. 精确的输入/输出改动清单（首期一致实现：单观察选择）

合同与生产端：
1. `app/domain/contracts/observation_selection.py`（新中立模块）：政策 v2（mode + scope + 逐字来源 + 可选 `selection{criterion: latest|earliest|explicit, ordering_attribute: "date_range"}`）；`explicit` 即现状恰一项。
2. `app/domain/contracts/rules.py:184`：`AtomicPredicate` 增可选 `observation_policy`，omit-when-None wrap 序列化（保 `predicate_identity_sha256` 稳定，`app/domain/contracts/predicate_binding.py:93-113`）。
3. `app/agents/protocol_control_deconstructor.py:1237-1241`：prompt v2.3/wire v7——计数无关“最近/最早为准”发 selection 块，条件性复查逻辑保持 unresolved。
4. `app/agents/protocol_deconstructor.py`（dnf-v1 wire）+ `app/services/protocol_draft_service.py`（:465-509 谓词装配透传）：官方 dnf-v2。
5. `app/domain/contracts/control_evaluation_spec.py:61-129`：校验扩展——selection 块来源包含、`ordering_attribute="date_range"`、解除“无 atom.time_constraint 不得声明日期操作数”对 ordering_attribute 的误伤（F4）。

消费端（唯一新逻辑落点）：
6. `app/services/qualified_binding_selection.py:211-268` `_select_facts_for_identity` 两分支：签名增入冻结事实、anchor、身份 fact_type 范围；实现 P1/P2/P3；同文件 ：309 起装配 `enumeration_gaps` 与被淘汰观察留痕（`not_governing_observation` 等逐条原因）。
7. `app/domain/contracts/qualified_binding_selection.py:107-129`：outcome 增 superseded/enumeration 字段；material v3→v4、消费算法 v9→v10（:21-23）。
8. `app/domain/gates/assessment.py:206-220` REASON_GAPS + `app/services/eligibility_review_projection.py`（缺口成句）+ `frontend/src/domain/reviewConditionNotes.ts`（已有 `observation_selection_unverified` 句式处）补新原因码中文句。

**不改**：两个求值器（`app/domain/expression.py:475`、`app/projections/control_calculation_experiment.py:40`）首期零改动；`app/services/frozen_review_calculation.py` 计算版本不动；无新调度器；范围过滤器取自已发布谓词，非患者特定启发式。

#### E. 官方 any/all 纳入最终范围（声明的剩余步骤，不后置丢弃）

首期一致实现仅单观察选择（上列 1–8）。剩余必做步骤，按序：
- **R1**：`_evaluate_atomic`（expression.py:475-562）增观察量词聚合——对多事实选择按政策 mode any/all 聚合，聚合规则与控制侧 `_conditional_truth`（control_calculation_experiment.py:40-85）**抽成共享纯函数**，禁止两套实现；保留逐观察真值/原因与 out-of-window 不制造冲突的既有语义（:494-498）。
- **R2**：`EVALUATOR_VERSION` v13→v14（frozen_review_calculation.py:27）及选择 material 允许官方身份多事实选择（消费 v10 已为多事实 outcome 预留形状）。
- **R3**：REASON_GAPS/中文句/报告展示按量词结果扩展。
- **R4**：P1 枚举护栏对 any/all 同样生效（多观察聚合同样要求枚举闭合）。
- **R5**：若 P1 的 fact_type 过滤在实践中过度阻断（同 fact_type 多对象场景），下一步不是放宽，而是候选任务 wire 下一版增“已考虑未对应”逐事实负面记录（对 `PredicateCandidateResult` 的扩展），仍走既有双读。
- **R6**：原文自述最新经命题通道核实的扩展（P4）。

#### F. 验证边界与遗留问题

按本轮指示**不新增任何测试**；首期实现后的验证仅编译/静态检查，最终验证（含本 addendum 的枚举、优势、复查矩阵）推迟到所有者指定的整链验证。遗留两个有界问题：
- **Q1**：P1 用 fact_type 做机器范围过滤器（跨对象、宁可保守阻断）作为首期边界是否可接受，还是 R5（候选任务逐事实负面记录）应提前与首期同批做？暂定：先 P1，R5 观察。
- **Q2**：唯一主导者窗口 UNKNOWN 时（`observation_window_membership_unverified`）保持 unresolved 而不回退次优——确认此保守取向。

本 addendum 未运行模型/库/浏览器，未写任何文件；所有 file:line 均为本 worktree 当前源码核实。Codex 保留最终裁决权。
