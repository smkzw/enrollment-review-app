收到 C03 接续审阅（核查选择＋跨 Job 预算继承）。只读、不改文件、不测试、不委派（Trellis 任务与本次只读边界不符，不创建；计划文件亦不写）。先定位两处修复与新增测试。

定位完成：`_merge_control_budget_reservations`（execution:4046）、`_inherited_control_budget_requests`（:4068，:4145 使用）、选择点（deconstructor:8392-8432）、合并单测（test_control_definition_scope.py:87-98）。读取核心实现。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

只读审阅（8 次工具已用满）。未改文件、未测试、未读临床/DB/env/私有目录、未替产品执行、未委派（Trellis 任务与本次只读边界不符，未创建）。110pass/1575deselected/36.80s 与 v1 夹具修正为宿主提供，未复核；**不称临床采用/启用/签发，不称真实 49 已核**。独立性折减：独立会话/适配器仍同 DeepSeek 家族，非模型金标。

**上一轮必修已被本包修复**：`source_scope_question_json_path` 成为共享事实（定义 `protocol_control_source_interpretation.py:659`），记录点（deconstructor `:8413`）、恢复兼容点（`:7769`）与服务种子证明（`protocol_control_execution.py:2659`）同源——先前"`json_path` 必须等于 `.unresolved` 会导致新真实历史种子证明返回 None"的第一因果缺口已闭合。

---

### 1) 漏记未知发送/历史调用、派生账重复或回退

**[代码事实] 内核正确（execution.py:4039-4163）**
- 预留即计：即使无失败回执，只要账本快照存在就走 `:4108-4115`（要求祖先 closure 含当前 batch，`:4111-4114`）→ 未知是否到达的预留仍被计。回执与账本不一致（`saved.requests[:used] != receipt.requests`）→ 抛"历史回执与实际调用账不一致"（`:4100-4107`）；**有回执无账本**（`saved is None`）同样抛（`:4103`），不当 cache miss。
- 去重键 `(origin_logical_task_id, origin_request_ordinal)`（`:4055-4061`），同键异记录→抛（`:4062-4063`），无静默回退；同 SHA 两次真实请求因序号不同仍计两次（测试 `test_control_definition_scope.py:54` 注释与 `:94` 的 `== 4`）。
- 活动祖先/错范围/循环：`lease_owner` 非空或 state∈{running,queued}→拒（`:4085-4086`）；三来源键不符→拒（`:4087-4089`）；`visited={context.job_id}` 防环（`:4076-4082`）。
- 发送前耗尽：`len(inherited) >= request_limit` 或预留 token 越界→`BUDGET_EXHAUSTED`（`:4152-4158`）；更大显式 limit 派生账携旧计数、`max_requests` 仅本代为新值（`:4159-4163`），祖先 cache 与 hash 不变（测试 `:93`）。尾文件丢失→`BUDGET_RECORD_INVALID` 硬拒（测试 `:100-104`）。
**[证据不足/边界]** ① 仅能发现**修改**（payload sha / 跨账比对），不能发现**删除**成功步骤的 DB 检查点行——需存储可信假设；建议在威胁模型里明示。② `LogicalCallBudget(saved=...)` 的篡改校验强度（`:4050-4054`）与 `_ProtocolSemanticBatchFileCache.load_call_budget` 的"缺部分即损"实现未读，仅由测试间接证明。③ 派生账必须保留下游条目的 origin 戳（merge 依赖）；测试主链通过（`:94`），但未见保存侧显式断言——**建议**在派生保存点断言该不变量。

### 2) 跳过"程序验证的已有目标"是否越权；失效是否仍完整

**[代码事实] 不算越权，且失效会重新开问**
- 跳过条件（deconstructor `:8395-8407`）：仅当问题类型为 `.eligibility_sequence` 且（a）无 wire 时 `force ∉ {required, prohibited, recommended}`（`:8402-8403`，descriptive 不升为患者义务）、（b）有 wire 时**重新计算的** `sequence_coverage[index].action_candidate_indexes` 为空（`:8389-8390、8403`）、（c）有经 `validated_source_review_seed` 保留的 review 且 `decision != additional_requirement`（`:8404`）、（d）保留 review 对应覆盖已 `semantically_aligned`（`:8405-8406`）。问题本身只改 `eligibility_sequence/quote/context`（`apply_*` 冻结其余字段），**不产生义务**；完整覆盖与 fresh 语义门在其后照常运行（`:8401` 注释）。
- 失效处理：保留 review 按当前陈述身份过滤（`_source_statement_reuse_identity` 含顺序字段，deconstructor `7345-7348`；runner 侧按身份比对过滤，前轮已读 `8963-8970`），身份一变即不保留→重新满足 `(c)` 的反条件→重新发问。**[证据不足]** 该过滤在本次未重读，属前轮证据；但与本包行为一致。
**[建议]** 跳过时在 attempt 账本记明原因（已覆盖目标/无有源候选/force 不允许），便于复盘"为何不问 7 而问 0-4"；不改判定。

### 3) 最小恢复消费者首因（必修候选）

- **[P1 候选-核对] 位置索引假设**：`sequence_coverage[index]` 直接按**位置**取（`:8403`），而该函数返回值在其它路径一律按 `statement_index` 建映射或显式排序校验（如 `restricted_source` 的 dict、种子证明的 `sorted(...) != range(...)` 检查）。若某来源的 coverage 顺序不保证，会问错/漏问（多一次调用或漏一次恢复，非错误采用）。**最小修复**：改为按 `statement_index` 取条目（或加断言）。**可复现反例**：构造 statement_index 非顺序的 coverage 列表传入 `_execute_deep` 的选择分支，观察跳过决策与预期不符；[] 我未读 `source_statement_coverage` 本体，故列为必修前的核对项。
- **[P1 候选-核对] 单问题失败的保留 kwargs**：标题失败路径显式回传 `source_target_review=resume_source_target_review` 与 `source_statement_coverage=list(resume_source_statement_coverage)`（`:8383-8387`）；问题失败路径在 `:8454` 后被读取截断，未能确认同样保留 review/coverage/alignment（`:8442-8470`）。若缺，会与"单问题失败保存原 source review/coverage/alignment、不抹掉兄弟"的声明不符。**最小修复**：与标题路径对齐回传保留字段。位置：deconstructor `:8454-8472`（请以实际文件为准）。
- 其余恢复面：选择、跳过、预算继承、发送前耗尽、尾损硬拒均有真实 Job/Runner 集成测试覆盖（`test_control_definition_scope.py:52-104`）；未发现新的恢复框架需求。

**必修**：上述两条先核对（若成立，各为一行级对齐）；**建议**：派生账 origin 不变量断言、跳过原因记录；**证据不足**：coverage 顺序保证、`load_call_budget` 缺件实现、`LogicalCallBudget` 篡改校验、以及 110pass/夹具修正的实跑数字。**给 Codex 的有界问题**：Q1 `source_statement_coverage` 是否恒按 statement_index 有序？Q2 `:8454` 失败回传是否含保留 review/coverage？两者确认即可关闭本包审阅。
