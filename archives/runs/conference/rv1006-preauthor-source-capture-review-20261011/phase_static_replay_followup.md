只读复核阶段标签和已保存拒绝这两处控制流。先核对基线与四份冻结哈希，再读完整定义和调用方。哈希与基线一致。接下来读阶段判定和保留拒绝的完整定义，以及它们的调用方。四份冻结哈希与基线 `5c63ba1f04fface7d47a6e45a3551de91469b938` 一致。这是工程控制流复核，不是临床采用或发布批准。本轮未改文件、未跑测试。

## 已核对且成立的边界

期别枚举与筛选、基线窗口可以分开。`_STUDY_PHASE_LABEL_RE` 只完整匹配「每个标记都带期」的枚举（`protocol_control_source_interpretation.py` 3334–3345）。`Ⅱ期和Ⅲ期`、`II期/III期`、`第Ⅱ期及第Ⅲ期`、`二期或三期` 是期别；`筛选期`、`基线期`、`治疗期`、`筛选期和基线期`、`Ⅲ期治疗期` 不是。`source_requires_temporal_resolution`（3010–3021）把落在期别区间内的「期、期」从多次访视里排除，所以「Ⅱ期和Ⅲ期在筛选期完成登记」不是多次访视，而「筛选期和基线期」仍是。

`STUDY_PHASE_NOT_VISIT_TIME` 仍走作者前的原范围校正。校正不得改 `scope_quote`、`scope_context_unit_id`、`affected_stage`（deconstructor 8268–8288；回放 2690–2697）。`apply_source_scope_correction`（954–974）只从 `time_words` 去掉完整期别标记；摘录和「筛选/导入期」保留。陈述或标题里的非期别时间不能删（939–946）。

`6个月` 会让时间快捷路径关闭。3017 行的 `\d+(?:个)?(?:天|日|周|月|年)` 能命中「筛选前6个月内」。单访视编译、相对访视和来源功能重读都依赖 `source_requires_temporal_resolution`，因此不会把这段当成一次访视。

验证器身份变化不会把旧证明当成新接受。两个新标记只进 `validator_version`（execution.py 2172–2173）。旧的完成期别进入 `refresh_required`：`time_words` 里的期别由 3872–3877 行强制刷新；受限批的 `STUDY_PHASE_NOT_VISIT_TIME` / `STUDY_PHASE_NOT_VISIT_STAGE` 只在版本不同时刷新，同版本继续硬拒（3754–3762）。失败批在版本不同时只尝试静态数值回放，不再调用原来的负向、未决或时间证明（3810–3821）。

静态证明本身不产生正证明。它要求末次错误是 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`，且每条 `alignment_failures` 的原因都是 `numeric_relation_unverified`（3419–3438）。当前失败必须与保存的失败完全相同（3475–3479）。`statement_ids`、候选、依赖和来源引用必须一致，未决陈述直接拒绝（3483–3486）。返回的 `adopted` 为 false。执行期这个模式和负向对齐一样不进入受限临床歧义（4828–4831），然后以 `retained_failure=True`、`new_model_calls=0`、`adopted=False` 终败（4853–4860）。发布读取完成检查点；该记录挂在 `STEP_FAILED` 上，`checkpoint_is_diagnostic` 不把它当完成（jobstore.py 364–370）。计数器不把 `revalidated-retained-failure/v1` 算进新失败；策略 `max_failed_steps` 为 2（268–275，runner.py 244–275）。两次非保留的新失败会停掉独立续读。证明函数不写回来源诊断。

## 发现

### 1. 高：带「个」的月窗口没有进入必须保留的时间清单

`source_requires_temporal_resolution` 认识 `6个月`，但强制列明时间的正则没有改。

```195:199:app/agents/protocol_control_source_interpretation.py
_EXPLICIT_TIME_FRAGMENT_RE = re.compile(
    r"(?:筛选|导入|基线|治疗|研究|试验|随访)期(?:间|内)?|"
    ...
    r"\d+\s*(?:天|日|周|月|年)(?!岁|龄)(?:内|前|后|以上|以下)?|"
```

`6个月内` 里数字后面是「个」，这个模式不命中。`_unreported_time_fragments`（238–255）因此不报缺口。已覆盖的来源核对只在这份清单非空时拒绝（2650–2654）。

最小反例：摘录「筛选前6个月内有重大疾病」，`time_words` 只有「筛选前」，核对决定为 covered。时间快捷路径关闭，但覆盖路径不要求把「6个月内」写入 `time_words`。结构化时间可以丢掉这个窗口，原文仍在摘录里。

最小修补：在 199 行的单位前加上与 3017 行相同的 `(?:个)?`，让现有 `SOURCE_TIME_INCOMPLETE` 生效。不要另做一套时间政策。

### 2. 高：真实对齐失败写不出可保留证明

作者在每条对齐失败上先写一条 `publication_invalid`，原答就是完整对齐 JSON，并带 `SOURCE_CANDIDATE_ALIGNMENT_INVALID`（deconstructor 10364–10374）。之后才追加 `outcome="parsed"` 的同一原答（10417–10425）。末次语义失败没有 `raw_output_text`。

保留函数把第一条能解析成对齐、但不是干净 `parsed` 的尝试当成整份证明损坏：

```3464:3471:app/services/protocol_control_execution.py
        try:
            parsed = SourceCandidateAlignment.model_validate_json(raw)
        except ValueError:
            continue
        if attempt.get("outcome") != "parsed" or attempt.get("error_classes"):
            return None
        reply = (raw, parsed, witnessed_wire)
```

生产诊断会在这里返回 `None`。版本变化后的预检因此得不到静态证明，批次回到 `resume_partial`，不会跳过同一次模型调用。这是失败关闭，不会把拒绝收成采用。

合同测试的形状不是作者写出的形状。`_static_alignment_failure_fixture`（8086–8105）只有一条 parsed 对齐，没有前面的逐项 `publication_invalid` 原答。测试能通过，并不证明 JobRunner 消费者能保留真实检查点。

最小修补：非 parsed 或带 `error_classes` 的对齐副本用 `continue`，不要 `return None`。只接受一条 parsed、且无错误类的原答；现有摘要校验和 `current_failures != failures` 保持不变。

### 3. 中：「第一期」「第四期」会被当成试验期别从结构化时间中去掉

标记是 `(?:第)?(?:IV|III|II|I|[一二三四])期`（3335）。`第Ⅱ期` 应保留；`第一期`、`第四期` 也会整段命中。校验在 3558–3564 行直接拒绝，校正在 971–974 行把它从 `time_words` 删除。原文摘录还在，但这会去掉一个可能是疗程次序的结构化窗口。筛选期和基线期不受这个模式影响。

最小修补：`第` 只允许修饰罗马期别，不修饰中文数字。`第Ⅱ期` 和 `四期` 仍是期别，`第一期` 不再被删除。

## 其余边界

声明的请求范围没有单独再核。回放把 `expected_pairs` 设成回复自己的条目（3474–3476），`bind_partial_candidate_alignment` 的范围相等因此是同义反复（candidate_alignment.py 767–771）。作者在写入时用 `pending_alignment_pairs` 约束过原答（10352–10363）。诚实检查点的原答范围是当时的请求。事后同时改原答和失败清单，可以收窄范围；现有相等检查挡不住这种成对篡改。发现 2 修好后，应把当时的请求对保存进失败明细，回放时用那份清单，而不是用回复自报的清单。

正证明没有被新写进去。失败条目不进入对齐对象；证明只比较失败。保留检查点会整份复制旧诊断，其中可以仍有已通过的兄弟条目。本步是终败，发布不会收它。以后若把这份新失败诊断再拿去续读，旧的正面兄弟是否被复用，本轮没有追到发布。

执行期没有再判一次验证器版本。它调用完整的 `_preserved_source_review_proof`（4815–4816），再与预检证明做相等比较（4822–4824）。数值失败不会成为 negative proof 的 incomplete 条目，所以版本变化时两边都应得到同一份静态证明。若一份诊断将来同时满足两种证明，新任务会变成 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`，并计为一次新失败，而不是保留失败。

`Ⅱ期到Ⅲ期`、`I/II期` 这种中间没有「期」的范围没有被认作期别枚举，也没有被认作两次访视。它们要再撞上同名冻结访视才会进入短访视编译。`六个月` 这种中文数字不在这次数字加「个」的改动里。

## 未证实的限度

测试未执行。没有一条作业级测试用作者实际写出的逐项失败尝试去走预检、`JobRunner` 保留失败、失败计数和发布拒绝。来源作业历史不被这个路径回写，这是从 `fail_step` 只写当前任务看出来的，没有跑作业。不要把这份复核当成临床验收。
