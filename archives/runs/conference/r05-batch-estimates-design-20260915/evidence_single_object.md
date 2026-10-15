All evidence is verified. Composing the complete conference report now.

---

# Conference Output: r05-batch-estimates-design-20260915 - evidence_single_object

## Output

### 结论（TL;DR）

现有持久记录**足以支撑**“按历史中位数、明确标注估算”的批量审核与批量OCR耗时估算，且**不需要新表、不需要写路径、不需要模型调用**：耗时证据在 `job_events.occurred_at`（作业级墙钟，含排队/重试/取消）、`raw_response` 回执工件（逐调用 `elapsed_seconds`，评审语义任务与页级VLM执行器均已写入）、`ocr_runs`/`ocr_attempts`（OCR页级与请求级时间戳）。费用侧只有 **token 用量**是可信回执（`PageReviewRecord.usage`、`usage_json`、响应工件），**全库不存在任何单价/费率来源**，且当前供应商为订阅制——货币金额不可从回执推导，必须“未配置单价→只报token、不折算金额”，禁止把未知费用当零。最大陷阱：`agent_calls` 表有时间/费用列但**没有任何生产写入方**，实现者若从它取数会得到空集中位数。UI接入点已存在（`BatchReviewPanel.tsx:137` 占位文案）。

---

### 一、证据清单（观测事实，均已读源核实）

**A. 兼容身份（可比性键）已冻结在批量载荷中**

- 审核批量：`enqueue_batch_review` 把 `routes`（每读道 `route_identity`）与 `task_versions`（每任务类型 `{contract, prompt_version}`）冻结进父作业载荷（`app/services/batch_review_workflow.py:60-62`）。`route_identity` 冒冻 `provider/base_url/model/reasoning_effort/max_tokens/max_concurrency/fallback_base_url`，凭据永不入载荷（`app/services/page_review_job_service.py:68-73`）。`change_batch_review` 重试前已用完全相同的比较拒绝新旧混跑（`batch_review_workflow.py:149-151`）——估算的分群键应复用这同一比较。
- OCR批量：父载荷冻结 `profile_sha256`（适配器指纹，`app/services/batch_evidence_reprocessing.py:157-158`）；页级缓存键 = 内容哈希+页码+OCR模型/参数版本（设计§3.3），`ocr_pages.cache_key` 有成功行部分唯一索引（`app/storage/ocr_models.py:194-199`），**缓存命中页耗时趋近于零且可判定**。
- 页级VLM回执身份：`PageReviewRecord` 携带 `lane/provider/model/reasoning_effort/endpoint_base_url/fallback_used/finish_reason/usage/prompt_version/clause_pack_sha256/response_sha256`（`app/domain/contracts/page_review.py:238-261`）。
- 选择性视觉观察侧车：`model_id/prompt_version/prompt_sha256/status/finish_reason/usage_json/failure_kind`（`app/storage/selective_vision_observation_models.py:63-72`）。

**B. 耗时回执（三层，互不重叠）**

- 作业级墙钟：`JobEventRecord` 追加写、`occurred_at` 非空、带 `attempt/retryable/progress_completed/progress_total/step_id`（`app/storage/models.py:1429-1446`）；事件类型覆盖 `STEP_STARTED/STEP_COMPLETED/STEP_FAILED/RETRY_SCHEDULED/WAITING_USER/CANCEL_REQUESTED/CANCELLED/COMPLETED/FAILED`（`app/workflow/jobstore.py:575-1605` 各转换点）。`make_event` 在转换时刻打点（`jobstore.py:213-239`）。`JobRecord.created_at/updated_at` 存在（RevisionedRecordMixin，`models.py:68-83`）。`batch_review_view` 已示范读取事件行（`app/services/batch_review_view.py:50-53`）。
- 逐调用墙钟：评审侧语义任务（predicate/control/qualification/judgment_content；control 继承 predicate 执行器，`control_binding_job.py:69`）在 `recorded()` 里写 `receipt["elapsed_seconds"] = monotonic() - start`，回执含 `job_id/step_id/attempt/route_identity/request_sha256/response_sha256`，失败时含 `error_type/status_code`，经 `self._put()` 落内容寻址工件，检查点携带 `receipt_sha256s`（`app/services/predicate_binding_job.py:278-300`；同构见 `binding_qualification.py:326`、`judgment_content_job.py:321`）。页级VLM执行器同样记录 `elapsed_seconds`（保留3位）+ `usage/response_model/finish_reason/max_tokens`（`app/services/page_review_job_executor.py:130-140`）。
- OCR层：`ocr_runs`（每文档 `page_total/page_succeeded/page_failed`，`started_at` 非空）与 `ocr_attempts`（每请求 `started_at` 非空、`completed_at`、`status/failure_category/retry_of_attempt_id` 重试谱系，`app/storage/ocr_models.py:225-283`）。

**C. 用量/费用回执**

- `PageCompletion` 数据类含 `usage/response_model/output_lengths/transport_contract`（`app/llm/page_review_harness.py:118-127`），usage 从响应提取、**传输层不返回时为空 dict**（`independent_vlm.py:562-573`）；落库时 `_usage_counts` 过滤为 int/float（`page_review_harness.py:556-559,744`）。
- 缺失≠零的现行先例：`local_early_length` 明确注释 "Unknown usage is not evidence of an early stop"（`app/llm/generation_completion.py:9-11`）。
- 响应工件（`receipt["response_sha256"] = self._put(dataclasses.asdict(result))`）内含 usage —— 评审语义任务的 token 数**已持久化**，只是藏在工件里。

**D. 空缺与陷阱**

- `agent_calls` 表：`started_at/finished_at` 非空、`input_tokens/output_tokens/estimated_cost` 可空（`models.py:1239-1301`），`AGENT_CALL_CONFIG` 仅在 `repositories.py` 定义且有读取（`repositories.py:530`）与 fixture 装载（`repositories.py:3620`），**全库无生产写入方**。设计§7.0的 AgentCall 回执要求在实现上由工件回执事实上承担。
- `PageReviewRecord` 只有 `created_at`，无逐调用时长；时长需从工件回执或作业事件取。
- `proposition_evidence_job` 未见 `elapsed_seconds`（有其专属回执模块 `proposition_evidence_receipts.py`，内容未核实）——唯一未验证的回执覆盖点。
- 全库无任何单价/费率/价格常量；无现成中位数/估算服务。
- UI：审核批量面板已有占位“本批暂未提供耗时与费用估算。”（`frontend/src/components/review/BatchReviewPanel.tsx:137`）；OCR批量面板（`BatchOcrPanel.tsx`）连占位都没有。API 面：`/api/v2/projects/{project_id}/review-batches`（列表/创建/详情/操作，`app/api/v2/batch_reviews.py`）。
- 批量成员**严格串行**（`StepSpec(..., depends_on=(f"member_{index-1}",))`，`batch_review_workflow.py:66-68`），且续跑靠维护回路轮询推进——成员间有轮询空隙，只有事件时间戳能如实反映。

---

### 二、推荐方案（最小、证据约束）

**原则：估算=只读投影。** 不新建表、不写任何实体、不触碰临床/原件数据；所有数字只来自已持久回执；确定性纯函数计算分位数；每个数字携带样本数与身份依据。

**1. 兼容身份（防混跑的分组键）**

- 审核估算键 = `{routes(逐读道route_identity), task_versions(逐任务contract+prompt_version), batch contract版本}`，与 `change_batch_review` 的重试比较**完全同源**。历史成员仅当其所属批的冻结身份 == 当前配置身份时才入样本；不等 → 不入样，绝不做跨配置平均。
- 页数/阶段/受试者体量：成员级样本天然按（subject, episode）匹配；若池化到项目级，必须加 `workflow_stage` 进分组键（`_workflow_stage_label` 已有），防止筛前/基线体量混批。
- OCR估算键 = `profile_sha256`；并对页级区分缓存命中（`ocr_pages` 成功行复用）与新识别。

**2. 耗时：两个口径，并列展示，各自标注**

- **完成墙钟（用户感知口径）**：子工作流 `terminal事件.occurred_at − JobRecord.created_at`。这是唯一诚实包含排队、重试退避、`waiting_user`、取消与维护回路轮询空隙的口径；可再分解为 `queue_wait / active_step / retry_backoff / waiting_user`（全部可从事件序列+attempt推出）。
- **活跃处理时间（模型口径）**：Σ 逐调用 `elapsed_seconds`（工件回执）。
- 批量总时 ≈ Σ 成员墙钟（**串行架构决定是求和不是求最大**）。App 重启停机会抬高中位数：不剔除（无法确定性判定），靠双口径并列让读者自辨——这是诚实下限。
- OCR批量：优先用同 `profile_sha256` 历史 `evidence_reprocess` 完成作业的墙钟；页级 `ocr_attempts` 时间戳作分解。

**3. 费用：token 为一等计量，货币为可选折算**

- 无费率来源是**事实**而非缺陷：智谱为 Coding Plan 订阅、MTPLX 为用户指定权重，按 token 计费金额不可从回执推导。
- 估算输出以 token（输入/输出分列）中位数为主；仅当用户配置了费率表（新配置项，按 `route_identity` 键控、带版本号）才折算金额；未配置 → 显式状态 `费率未配置，未折算金额`，**绝不是 ¥0**。
- OCR（本地 oMLX）标注 `本地识别，不产生云端API费用`（这是事实陈述，不是把未知当零）。

**4. 缺失≠零的落地规则**

- 每个聚合字段携带 `coverage: {present, total}`：如 `usage` 为空 dict 的调用计入时间样本、剔除出token样本并披露“12/15次调用含用量”。
- `n=0` → `unavailable_reason: "无同配置完成回执"`；`n<3` → 不给区间，只给单次参考值并标注样本数；`n>=3` → p25–p75 区间 + 中位数。规则表驱动、可单测。

**5. 具体字段与函数（建议形状）**

```
estimate_identity(routes) -> dict                      # 复用 route_identity + current_review_task_versions
member_wall_time_samples(session, identity, *, project_id, subject_id, review_episode_id)
    -> list[Sample]                                    # 完成子工作流 created_at→terminal事件，含来源batch/作业id
member_token_samples(session_factory, artifact_store, ...) 
    -> list[Sample]                                    # 步骤检查点→receipt_sha256s→响应工件usage
quantiles(samples) -> {p25, p50, p75, n} | {n: 0}      # 确定性纯函数
estimate_summary(samples, coverage) -> EstimateBlock   # 含 unavailable_reason / coverage / labelled=true
```

API：新增 `POST /api/v2/projects/{project_id}/review-batches/estimate`（成员身份列表入参；只读不落库，POST只为携带成员清单，需在docstring声明无副作用），响应含 `{"estimate": true, "method": "historical-median", "identity": {...}, "members": [...], "batch_total_wall_time_sec": Σ, "currency": "unconfigured"}`。UI：替换 `BatchReviewPanel.tsx:137` 占位为“预计 X–Y 分钟（中位 Z · 同配置历史 n 次 · 估算值）”，无样本时保留现状文案；OCR面板（`BatchOcrPanel.tsx`）后续同构接入。

**6. 明确不做**：不复活 `agent_calls` 写入（本特性不需要）；不做页级重derive（v2再议）；不读生产库（本次全部结论来自源码审阅，符合边界）。

---

### 三、最重要异议与缺陷（主动挑战）

1. **【最高影响】`agent_calls` 是伪朋友。** 设计§7.0的文字会诱导实现者从该表取耗时/费用，但它无生产写入方，取数得到空集。**补救**：估算服务数据源钉死为 job_events + raw_response 工件 + PageReview/OCR/侧车表；在实现注释与任务笔记中显式记录这一偏差（设计要求 vs 实现现实）。
2. **墙钟与活跃时间混算是系统性低估。** Σ`elapsed_seconds` 不含排队/重试/轮询空隙；批量串行+维护回路轮询意味着成员间隙可能不可忽略。**补救**：双口径并列 + 墙钟为预测主口径（预测的是用户等待时间）。
3. **订阅制下“费用估算”可能整体不成立。** 若用户视“费用”=token消耗，方案成立；若坚持要货币金额，则必须先有用户维护的费率表，否则整个费用列只能永远是“未折算”。这是产品裁决，不是工程选择（见决策点Q1）。
4. **单用户本地应用的历史样本量天然稀薄。** 同（受试者，节点）重复审核可能只有0–2次；项目级池化又引入体量/阶段混杂。**补救**：诚实规则（n<3不给区间）+ 分层键含 stage；宁可显示“无法估算”也不给假精确区间。
5. **跨时钟混算风险。** `elapsed_seconds` 用 `monotonic()`（进程内），作业事件用DB时钟（UTC naive）。两者**不得互相加减**，只各自聚合成独立指标。当前代码已正确分离，估算服务必须维持。
6. **首审受试者无历史的回退路径未定。** 用项目池化中位数（宽区间+标注）还是直接“不可估算”？我倾向：成员级→同项目同stage池化（标注“非本受试者历史”）→否则不可估算，三级显式标注回退来源。

---

### 四、给Codex的决策点与有界问题

- **Q1（阻塞费用口径）**：费用估算以 token 为默认计量、货币仅在用户配置费率表后折算——是否接受？若用户要求货币优先，需先裁决费率表归属（配置文件 vs 界面维护）。安全暂定：token口径 + `currency: "unconfigured"`。
- **Q2（API形状）**：preflight 估算用 `POST .../estimate`（只读）还是前端在现有 `POST /review-batches` 响应里附带估算（提交后才显示，与§8.7“批量运行前显示”不符）？我推荐前者；若Codex倾向减少端点，需明示接受“提交后显示”的偏差。
- **Q3（范围）**：OCR批量面板本次是否同批接入（无现成占位，需新增UI行），还是仅交付审核侧、OCR侧只出设计？安全暂定：两侧服务层同构、UI先审核侧。
- **Q4（待验证）**：`proposition_evidence` 任务是否记录 `elapsed_seconds` 未核实（专属回执模块存在但未读）；实现前需一次定向核查，否则该任务类型的时间样本会静默缺失。

---

### 五、不确定性与未验证项

- 未运行任何应用/查询，所有“回执存在”结论来自源码结构（列定义+写入点），**未用真实数据验证回执密度**（如 usage 空dict比例、历史批次数量）——这是实施时第一个校准动作。
- 维护回路轮询间隔未测（影响成员间隙大小，不影响方案成立）。
- `main_reader_identity`/`execution_versions`（SubjectPageCoverage）与再处理批的VLM读道可比性未展开（再处理子任务跑全量处理执行器，其读道身份在处理作业载荷中，未逐一追）。

**恢复点**：若Codex追问，直接从第四节Q1–Q4与第五节未验证项继续；实现顺序建议：Q4核查 → estimate_identity/quantiles纯函数 → 时间样本 → token样本 → API → UI占位替换。

*本报告为顾问输出，非最终接受；Codex保留临床、产品与实现裁决权。*
