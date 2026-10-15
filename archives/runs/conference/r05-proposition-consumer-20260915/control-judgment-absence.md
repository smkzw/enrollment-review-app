# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

同会话第 6 轮只读源码复审（未编辑/导入/运行）。结论：**未发现把未读/歧义/缺文件/找到未核实/未来阶段提升为“缺席”的路径；原因到动作链路完整；无真相/选择造出。1 个范围说明（F1）。** ≤50 行。

### 发现
- **F1（范围说明，非缺陷，方向保守）** `control_judgment_gaps.py:16-17` 以 `due_stage == episode.stage` 精确限定当前节点——与所述设计一致，但早于当前节点到期的 investigator_assessment 要求即使已确证“搜遍无判断”，也不会为本原子附加 `professional_judgment_missing`（`linked` 漏掉它→不标记→原子以通用未核实原因呈现）。方向安全（不会误报缺席）；如需覆盖早到期关联要求，最小修复是把过滤器放宽为 `STAGE_RANK[due_stage] <= STAGE_RANK[episode.stage]`——`requirement_summary_gaps` 自身已排除未来阶段（`eligibility_review_projection.py:425-426`）。属范围澄清，请 Codex 裁决是否纳入。
- **F2（低，防御性）** `selections.get(...)` 伪造检查（`control_judgment_gaps.py:31`）对缺键与空表同义；正式路径实验端强制全键覆盖（`control_calculation_experiment.py:186-192` 编号沿用 v8），不可达，无需修复。

### 已核实正确（证据）
1. 用户规则映射：PROFESSIONAL_JUDGMENT 仅出自 `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE` 且无矛盾观察记录（`eligibility_review_projection.py:458-466`）；summary 缺失/有候选/覆盖不全/被观察矛盾→OBSERVATION_UNVERIFIED（`:449-457,:464`）；**缺文件（REFERENCED_FILE_MISSING）被跳过→永不成缺席**（`:415-429`）；未来阶段按 STAGE_RANK 跳过（`:425-426`）；兄弟 workflow stage 双重过滤（`:433-436` + `control_judgment_gaps.py:16-17`）。
2. 归因绑定：同控制、当前节点、investigator_assessment 候选集内**任一无 atom_refs 要求即阻断整个控制**（`control_judgment_gaps.py:33-36`）；按 `(layer, group_index, atom_index)` 精确键关联（`:37-38`），键形与 `ControlEvidenceAtomReference.key`（`control_evidence_dependency.py:12-18`）及 identity.layer 字符串（`control_atom_binding_input.py:17`）一致；**全部 linked 须为 PROFESSIONAL_JUDGMENT**（`:39`）——混合缺口/找到未合格均阻断。`shared_control_requirements` 复用同一 requirement_id 身份（`control_evidence_requirements.py:105`），current_ids 过滤可靠；其无 atom_refs，helper 正确保留原投影供引用（`:23` vs `:33`）。
3. 不造真相：原因经集合并附加不删旧因（`frozen_review_calculation.py:73-75`，evaluator v12 `:27`）；被标记原子必然空选择→UNKNOWN（`selected_observation_missing`→未核实覆盖）；实验端校验未核实⇒空 chosen（`:186-192`）；旧 v11 上下文在 `:159` 拒绝重算——重准备纪律。
4. 原因→动作链完整：`unresolved_atoms`→义务 `observation_reason_codes` 取并集（`control_review_outcome.py:40-44,:79-80`，空 observations 时未核实原因仍汇入）→directive 仅当原因在场才给 PROFESSIONAL_JUDGMENT 动作（`control_action_directives.py:41-46`）；未知激活归组为单一通用前置目标不扇出（`:32-38`）；`ACTION_CONTENT[gap]` 消费既有 GapType（`control_action_publication.py:30-36`）——历史快照无此原因保持 OBSERVATION_UNVERIFIED，行为不变（兼容）。
5. 输入完备：episode.stage/workflow_stage_id、expectation_templates/judgment_search_results/expectations 均为快照既有字段，与 `calculate_frozen_review` 同构调用（`frozen_review_calculation.py:210-212` 同模式）；延迟导入 `control_judgment_gaps`（`:71`）无环（其不回导 frozen_review_calculation）。
6. “两读者搜遍”语义由冻结的 judgment_search_results 覆盖状态承载，helper 不碰 lane 数据，消费回执核实的状态字段。

### 未决（范围声明）
本功能覆盖“当前节点义务原子+已归因 investigator_assessment 要求”的缺席归因；早到期要求（F1）、触发/例外层缺席的专门动作（现归入未知激活组或 unresolved_atoms 呈现）不在本轮声明内；无方法审批/临床结果发布，无运行或阶段测试证据（build-first）。
