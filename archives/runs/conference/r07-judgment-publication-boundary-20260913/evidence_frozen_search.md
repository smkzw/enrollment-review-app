I'll inspect the new V2 review-context and frozen-search provenance path end to end, then check whether publication can still silently pick latest.继续只读审阅：先锚定当前切片源码与生产者，再按问题逐条核对冻结检索溯源与 V2 上下文绑定。先读会议输出格式和本切片源码定义，再核对生产者与绑定路径。接下来读仓储绑定、ReviewRun 合同和检索生产者，核对冻结身份是否真能复现。接着读 ReviewRun 合同、仓储绑定和检索生产者的完整实现。继续核对检索执行器、摘要仓储和 ActionRequest 的哈希/关联校验。# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读审阅冻结检索溯源与 V2 审核上下文。未改代码、未跑测试/迁移、未读库、未调模型。所有者编译通过不是功能证据。本切片是预备件：无 V2 正式发布入口、无装配器、无唯一评估器接入。缺 API 接线不记成未报告的完成。旧报告不当作真相。

### 问题结论

**1. 钉住 summary/job/checkpoint 并重载内容寻址回执，能否复现同一条要求的检索？**  
**能，前提是发布时来源仍是当时那份活动来源。** `freeze_judgment_search_result` 按 `summary_id` 取条目（`get_entry`，不是 `latest_for_authority`），再按该 job 的 `read:{index}:{lane}` 取最新 checkpoint 身份，然后走 `_rebuild`。`verify_frozen_judgment_search_result` 只用已钉住的 checkpoint，不再取最新。`_rebuild` 重跑 `prepare_judgment_search_target`（当前活动来源）、按 `storage_ref` 装回执、`assemble_judgment_search_coverage`，并要求重建摘要等于已存摘要。批次读器对一页全部目标要么全成要么全败，不会部分成功（`judgment_search_reader.py:599-601,710-761`）。失败页 checkpoint 无 `receipt_refs`，重建时跳过该页该读道。这复现的是**该 job、该要求、当时摘要所用回执**，不是任意历史报告重算。

**2. 缺页或失败页会不会变成完整未见？**  
**不会。** 执行器把非可重试读失败写成 `{page_failure}` 并完成步骤，摘要跳过这些回执（`judgment_search_job_executor.py:158-173,220-223`）。装配空缺读道/缺页 → `COVERAGE_INCOMPLETE`，只有范围内每页双读都有效且两通道均为 `not_found` 才是 `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE`（`judgment_search_coverage.py:159-171`）。摘要合同禁止该状态同时带候选或缺口（`judgment_search.py:408-418`）。`professional_judgment_absence_proven` 仍恒为 False。

**3. 页/读道/模型身份与 target/source 哈希是否兼容真实重试？**  
**兼容当前执行器的重试语义。** `transport`/`length` 且未用尽次数时抛可重试 `StepFailure`，不写 checkpoint；用尽后写 `page_failure` 并 `complete_step`（`runner.py:651-666`；`jobstore.py:662-671`）。一步只有一条完成 checkpoint。`freeze` 与 `get_last_checkpoint` 同一排序。身份核对对着 **job 载荷路由** 和 **当前 prepare 的页**，不是 live 路由表。`target_text` 由 `json.dumps(..., separators=(",", ":"))` 产生，无首尾空白；回执内 `target_sha256` 按 strip 计算，与当前紧凑 JSON 一致。发布核验会再次 `prepare`：来源仍当前则通过；来源漂移则拒绝。这符合「新发布、来源仍当前」，不是任意历史重算。

**4. 发布核验会不会误取 latest？**  
**`verify_frozen` 不会。** 它使用 `frozen.summary_id` 与 `frozen.checkpoints`。`latest_for_authority` 仍只给投影/缺口/状态用，本切片溯源未调用。`freeze()` 在钉住瞬间取该 job 每步最新 checkpoint；任务完成后一步只有一条完成记录，与 summary 所用相同。风险在未写的装配器：若用 `latest_for_authority` 选 `summary_id`，那是选最新检索，不是本核验函数。

**5. 上下文是否保留全部 fact/event/exposure/conflict 引用与权威？**  
**只保证已收录对象的内部闭合和权威一致，不保证权威下对象全量。** 校验：集合按身份排序去重；facts/events/exposures/expectations/conflicts 的 `authority` 必须等于上下文权威；模板属于该 rule_set 修订；event/exposure 的 `fact_ids` ⊆ facts；冲突成员 ⊆ 对应集合；expectation 绑定模板且 `coverage_fact_ids` ⊆ facts；检索每条要求至多一条且 scope 权威一致（`review_context_v2.py:109-159`）。不要求收录权威下全部事实/事件/暴露/冲突；不要求每条书面判断要求都有检索；`conflict.locator_ids` 与 `fact.locator_ids` 不交叉核对，上下文也无 locator 工件表。

**6. run 能否绑到确切上下文且无循环插入？**  
**能。** `review_context_snapshots` 无指向 run 的 FK；`review_runs.context_id` 有 FK。上下文 `review_run_id` 只是 payload 字符串。插入顺序：先上下文，再 run。run 保存时 `_check_run_scope` 要求上下文已存在、`context.review_run_id == run.review_run_id`、权威一致、冻结 episode dump 等于当前 episode dump（`repositories.py:445-468`）。无 SQL 环。

**7. 新改动是否破坏旧规范序列化或历史读回？**  
**合同层未见破坏。** `fixture/v1` 的 `ReviewRun` 省略 `episode_revision`/`context_id`（`review.py:176-182`）；谱系省略 V2 列（`review_evidence_scope.py:33-40`）；`ActionRequest`/`ActionTransition` 同样省略新键。`payload_get` 缺键为 `None`，与新列 NULL 镜像。GET 不跑 `scope_check`、不重跑 `prepare`、不重跑 `verify_frozen`。旧报告读冻结结果，不重算。v2 run **新写**仍要求当前活动权威（`FactAuthorityValidator.validate`）；这是新发布窗口，不是历史 GET。

### Evidence

- 冻结合同：`app/domain/contracts/review_context_v2.py`
- 溯源：`app/services/review_judgment_provenance.py`
- 上下文仓储：`app/storage/review_context_repository.py`（与 v1 共用 `review_context_snapshots`；GET/SAVE 不验证回执）
- run 绑定：`review.py:151-182`；`models.py:1004-1036`；`repositories.py:426-468,1212-1238`；`0023_review_v2_evidence_lineage.py:522-527` 另加 `ck_review_runs_context_lineage`
- ActionRequest GET：`repositories.py:2292-2348`（payload 哈希、列镜像、转换 id 集合、转换正文/哈希/时间镜像、按版本核对 span 或 locator 关联）；转换禁止混谱系（`review.py:335-336`）
- 生产者：`judgment_search_job_service.py`（入队冻结 target/pages；`target_sha256` 不 strip）；`judgment_search_job_executor.py`（失败页不折成未发现；summary 用 `get_last_checkpoint`；`_target_sha` 会 strip）；`judgment_search_artifacts.py` / `judgment_search_results.py` / `judgment_search_coverage.py`；`judgment_search_repository.py`（`get_entry` 钉身份；`latest_for_authority` 另用）
- JobStore：完成步骤才写 checkpoint，且要求 `state=="running"`（`jobstore.py:662-671`）；可重试失败不走完成路径
- 批次读：无效即整页失败，不输出部分成功（`judgment_search_reader.py:599-601`）
- 未版本化 `AssocSpec` 在 `_decode` 中跳过（`repositories.py:380-381`）：旧行为，所有者已说明不是回归；本切片不重开
- AgentCall CHECK 全空分支限于 `protocol_deconstructor`，**不**要求 `review_run_id IS NULL`（`models.py:50-57`）

### Inference

`freeze`/`verify`/`_rebuild` 能在「来源仍当前」时从钉住身份重建同一摘要。失败页在覆盖层只能是不完整。真正的空隙在装配器：上下文合同允许 `judgment_search_results` 为空或缺某条要求；丢掉一次不完整检索，合同上看就像从未检索。仓储 SAVE 只做身份去重和合同自洽，不调用 `verify_frozen`。这是刻意的：若 GET/SAVE 重跑 prepare，历史读回会在来源变更后失败。发布路径必须在来源仍当前时调用 `verify_frozen`；历史读只读冻结 payload。

`_rebuild` 比较 job 载荷里的 requirement 整表（含未 strip 的 `target_sha256`）与当前 prepare。当前 `target_text` 是紧凑 JSON，与回执 strip 哈希一致。executor summary 用 strip 比载荷哈希，是潜伏不一致；现生产者不会触发。若将来 target 带空白，summary 会 `SCOPE_CHANGED` 失败，任务完不成，freeze 也进不去。

共用上下文表无类型列。错用仓储解码会失败（闭失败）。`context_id` 碰撞时，V2 `get_or_none` 按 V2 解码 v1 行会抛 `PersistedContractInvalid`，而不是温和的重复提示。

### Findings（严重度）

1. **中：上下文不强制保留每条书面判断检索，失败检索可被省略。** `ReviewContextSnapshotV2` 只禁止检索重复和权威/要求错绑，允许零条或子集（`review_context_v2.py:149-159`）。`freeze` 可以把失败页冻成 `COVERAGE_INCOMPLETE`（步骤因 `page_failure` 为 `completed`），但装配器若因不完整而丢弃该 `FrozenJudgmentSearchResult`，合同无法区分「未检索」与「检索失败」。  
   **最小改法：** 装配器对每条拟用的书面判断要求调用 `freeze_judgment_search_result` 并写入上下文，包括 `COVERAGE_INCOMPLETE`；禁止用「没有检索条目」表示失败页。不要在上下文 GET/SAVE 上自动 `verify_frozen`（会破坏历史读回）。

2. **中：上下文不是事实/定位闭包的完备包。** 内部 ID 闭合成立；locator 工件不在快照内；冲突定位不与事实定位对账；不要求权威下对象全量。  
   **最小改法：** 装配器按权威把拟用的 facts/events/exposures/conflicts/templates/expectations 全部放入快照；发布/评估继续用冻结 `FactAuthority` 去仓储取 locator，不要把上下文当成自足证据包。不要为「全量」加第二套运行时扫描当合同证明。

3. **中：`freeze()` 钉住瞬间取最新 checkpoint；发布核验本身不取 latest，但装配器若走 `latest_for_authority` 就会选错检索。** `verify_frozen` 使用冻结引用（`review_judgment_provenance.py:61-71`）。`ReviewContextV2Repository` 不重验回执（`review_context_repository.py:22-29,30-38`）。投影仍用 `latest_for_authority`。  
   **最小改法：** 装配器：`get_entry(summary_id)` 或任务完成后的 `freeze(summary_id)` 一次，把结果写入上下文。发布：只 `verify_frozen_judgment_search_result`。禁止发布时调用 `latest_for_authority`。旧报告继续读冻结摘要，不重算。

4. **低：target 哈希 strip 不一致。** 入队/溯源：`hashlib.sha256(target.encode())`（`judgment_search_job_service.py:142-144`；`review_judgment_provenance.py:96`）。executor summary：`target.strip()`（`judgment_search_job_executor.py:254-255`）。回执装配也 strip。当前 prepare 输出无空白，三路相等。  
   **最小改法：** 三处与回执一致，统一 `strip` 后再哈希。不要为此铺测试矩阵。

5. **低：共用 `review_context_snapshots` 无类型列。** V2 仓储按 `ReviewContextSnapshotV2` 解码。与 v1 同 id 会在 SAVE 时以解码错误失败，而不是重复身份错误。  
   **最小改法：** 装配器使用不可与 v1 碰撞的 `context_id`（例如独立前缀）。不必拆表。

### 非缺陷（含所有者校正）

- 未版本化 `AssocSpec` 在 `_decode` 跳过：本来就不核，不是本切片回归。全面核旧关联要另算兼容成本，本切片不做。
- AgentCall 全空分支限于 `protocol_deconstructor`，允许 `review_run_id` 非空：保持旧合同。
- `ActionRequest.get` 已核转换正文、哈希、列镜像、v1 span / v2 locator 关联。
- 失败页不会在覆盖函数里变成 `ALL_SUPPLIED` 或 `absence_proven`。
- 无 SQL 循环依赖；v1 omit-null 仍在。
- 0023 在 ORM 之外为 `review_runs` 加了 `ck_review_runs_context_lineage`。本角色未执行迁移。

### Uncertainty（未验证运行时）

未执行 0023，未读 SQLite，未跑 freeze/verify/SAVE 事务，未跑套件。编译通过不是功能证据。批次读器「禁止部分成功」只看到源码，未跑模型。装配器、唯一评估器、`publish_assessment` 的 V2 分支、HTTP/报告未实现；不得把本切片写成正式 V2 发布已完成。`claims_complete` 与阳性谓词对应未批。上下文 SAVE 后 episode 再激活新资料：历史 GET 仍可读冻结 dump；新写 run 会被当前权威拒绝——源码如此，未实测。

### 对 Codex 的异议与决策点

- 不要在 `ReviewContextV2Repository.get/save` 上接 `verify_frozen` 或 `prepare_judgment_search_target`：那会把「来源仍当前」的发布核验打进历史读回。
- 不要把「上下文可保存」当成检索已证明缺失。不完整冻结必须保留为不完整。
- 装配器是下一刀，不是本切片漏做的完成声明。
- 安全暂定路径：装配时 `freeze` 一次并写入；发布时只 `verify_frozen`；旧报告只读冻结摘要。

本角色不主张最终临床/监管/产品接受。
