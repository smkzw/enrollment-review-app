继续只读审阅待办回应来源：先核对 Action 合同、scope 校验与历史读取的完整定义，再挑战拟议的最小方案。# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读续审待办回应来源。未改代码、未跑测试、未读库。拟议方案方向对，不能原样落地：缺转换前缀与身份冻结、缺回应原件与原审核原件分权威核验、以及历史阅读器仍按原 context 装定位。不是临床签收。

### 问题结论

**方案能修现在的两处拒办，且不应让新证据继续走旧 authority。** 阻塞在仓储，不在「再做一个状态机」。

`_check_action_scope` 把全部 `transition.locator_ids` 与 `trigger_locator_id` 一并交给 `review_authority(run, 当前 episode)`（`repositories.py:585-594`）。`validate_locators` 要求定位属于该权威的快照成员和 complete 清单（`fact_authority.py:204-278`）。补上传落在新 snapshot/complete 上，关闭必拒。同函数还用**当前** `episode.rule_set_id/revision` 去对旧 Action（`561-566`）。方案修订后旧事项无法 `replace`。历史 GET 不跑 scope_check，只读仍可能成功；一办理就失败。

**FactAuthority 略重，但不必新类型。** `validate_locators` 实际只用 episode + snapshot + complete（及定位清单）。`validate()` 才会要当前活动指针、当前 `episode.revision`、可激活 complete（`76-86,111-148`）——那才会逼人先激活、连带病史整理。回应路径**禁止** `validate()`。`protocol_version_id` / `rule_set_*` / `episode_revision` 对定位闭合无用，不得拿来和原 Action 或当前 episode 规则修订对齐。

**不要新 ActionState。** 已有 `OPEN / CLOSED_MANUAL / REOPENED / CLOSED_SYSTEM / SUPERSEDED`（`enums.py:163-168`）。人工办结 = `CLOSED_MANUAL` + 原因 + 回应原件，只表示事项已办理。缺口是否消失 = 另一次 `ReviewRun` 的 `FinalAssessment`。报告已把行动当前状态与冻结结论分开（`review_history_service.py:1-26`；设计 §17.6）。勾选关闭不得改原结论。首版不开放 `CLOSED_SYSTEM`/`SUPERSEDED`（那是新审核替代的证明，还没有）。

**必须补上、否则会再坏的：** `replace` 前缀与同 ID 正文冻结；触发定位永远走原 run 资料链；历史面板按**每条转换自己的回应权威**装定位，不得把新定位丢进原 `context.authority` 校验。

### 已核实事实

- v2 转换已要求明确 `locator_ids`（可空列表），禁止 span；v2 `occurred_at` 须 UTC；序列化 v1 省略 `locator_ids`（`review.py:315-346`）。
- Action 合同：v2 禁止 `trigger_evidence_span_id`；转换 ID 不重复；有转换则末条 `to_state == state`；时间与状态链连续；`CLOSED_SYSTEM` 必须有对应转换；指纹含整份 payload（含转换）（`381-426`）。
- `replace` 只把「表里还没有的 ID」插入，**不**核前缀、**不**核同 ID 正文（`2350-2378`）。`apply_revisioned_update` 用整份 dump 合并，`mutable_fields` 只用于并发 diff，**不是**不可变字段白名单（`concurrency.py:79-94,135-148`）。`MUTABLE_FIELDS` 含 `trigger_locator_id`（`2261-2272`）。若 payload 改历史转换或丢掉旧 ID，replace 能写成功，随后 GET 因表/payload 不一致而 `PersistedContractInvalid`（`2322-2337`）。
- `publish_action_request` 初态 `OPEN`、`transitions=[]`（`actions.py:91-118`）。无办理命令。
- 历史 `get_run` 只按**评估** `locator_ids` 用 `context.authority` 装 `evidence_locators`（`review_history_service.py:490-505`）。转换上的 `locator_ids` 进 DTO 字符串（`review_history.py:364-371`），不进原件面板。用原权威去核回应定位，关闭后的报告会拒读或显示不出新原件。
- 关联表已指向 `evidence_locator_artifacts`（`models.py:1574-1579`），可复用，不必新表。

### Findings（严重度）

1. **高：办理写路径把新定位和原触发绑在同一旧权威上，并用当前规则修订卡旧 Action。** `repositories.py:561-594`。这就是用户描述的拒办。  
   **最小改法：** scope 只把 Action 对到冻结 `ReviewRun`/`FinalAssessment`（含原 `rule_set_revision`、资料三指针）。**不要**比当前 `episode.rule_set_*`。`trigger_locator_id` 只对 `review_authority(run, 冻结节点身份)` → `validate_locators`（可从 run 取 snapshot/complete，project/subject/episode 用 Action 上的值，不要用当前 episode 的规则修订去填 FactAuthority 的 rule 字段当作校验条件）。每条转换：空定位则无回应权威；非空则按其 `response_authority` 只 `validate_locators`。

2. **高：`replace` 不能保证历史转换是原样前缀。** `2350-2378`。同 ID 改正文或丢掉旧行会导致 GET 永久失败。  
   **最小改法：** 读出已存转换列表；新列表长度 ≥ 旧；`new[:len(old)]` 与旧 `model_dump` 逐条相等；只插入后缀。身份字段（run/assessment/gap/lineage/`trigger_*`/规则修订/组件）必须与已存相等。办理命令可变的只有 `state`、`transitions` 后缀、随之重算的 `publication_fingerprint`/`revision`。`expected_revision` 沿用现 OCC。幂等键首版可用 revision；不必新队列。

3. **中：只加可空 `response_authority` 不够挡住「空定位关闭」。** 现合同允许 v2 `locator_ids=[]`（`326-331`）。若「非空才带权威」，勾选关闭仍能写成 `CLOSED_MANUAL`。T5/§17.6：关闭需证据，补资料不改判。  
   **最小改法：** 进入 `CLOSED_MANUAL` 的转换必须 `locator_ids` 非空且带 `response_authority`，`reason` 非空白（已有 min_length）。`REOPENED` 允许空定位、权威为空。禁止本命令写 `CLOSED_SYSTEM`/`SUPERSEDED`。不把关闭写成缺口已解决。

4. **中：历史原件仍按原审核权威装载，回应原件会丢或误伤。** `review_history_service.py:490-495`。  
   **最小改法：** 原件面板继续只核评估+触发（原 context/run）。转换定位按各自 `response_authority` 另装，UI/DTO 标明办理原件，不与原审核页混合。历史 GET **不要**对回应定位调用 `validate(context.authority)`。

5. **低：FactAuthority 字段会诱使调用 `validate()` 或对齐当前规则修订。** 定位检查不需要 rule/protocol/当前 revision。  
   **最小改法：** 增加 `validate_action_response_locators(session, action, authority, locator_ids)`：核对 project/subject/`review_episode_id` 与 Action 相同；snapshot 作用域这三项；complete 属于该 snapshot/episode；然后只 `validate_locators`。文档写明禁止 `validate()`。不必新 DTO；回应权威里的 rule/protocol/episode_revision 只是产生这些定位的处理版本抄本，不参与与原 Action 比较。

### 时间/节点：不必作为本轮阻塞

不要用 `due_stage` 或「必须仍是当时节点」拒绝迟到补传。缺文件类事项经常在后续节点才补上。也不要在本轮证明回应原件与缺口同时期——那是来源时间窗，T1 未收口。`occurred_at` UTC + 链单调已够办理审计（`review.py:332-404`）。

闭环语义：人工关闭 ≠ 临床缺口消失 ≠ 用户确认「已核实缺失」。缺研究者判断继续是报告里的 PJ 待办；关闭只表示交了回应原件。新审核若不再产生该缺口，那是新 `FinalAssessment`，不是把旧 Action 标成符合。

### 最小实施顺序

1. 合同：v2 `ActionTransition.response_authority: FactAuthority | None`；v1 省略。非空定位 ⇔ 非空权威。  
2. `_check_action_scope` 拆触发/回应；去掉当前 episode 规则修订比较。  
3. `replace` 前缀 + 身份冻结；办理入口只追加 `CLOSED_MANUAL`/`REOPENED`。  
4. 历史阅读器分装回应定位。  
5. 不接谓词对应、不接自动关闭、不改评估器。

### 非缺陷 / 不要做的

- 不要建议新证据继续按旧 authority 验。  
- 不要用户确认已核实缺失。  
- 不要新表/新队列/新枚举。  
- 不要为回应去跑 Profile/事实发布。  
- `CLOSED_SYSTEM` 仍保留给将来「新 ReviewRun 证明替代」；本版命令层关闭该入口即可，不必删枚举。

### Uncertainty

未跑 replace/GET，未测方案修订后的真实 Action 行。关联 FK 只保证定位行存在，不保证属于某 snapshot；权威校验必须留在 scope，不能只靠 FK。原库未迁。本角色不主张临床接受。
