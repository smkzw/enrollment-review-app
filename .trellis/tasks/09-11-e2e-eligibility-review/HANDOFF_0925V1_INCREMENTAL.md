# 0925V1 增量交接（2026-09-25，实施中）

## 本轮最新增量：B 来源回执逐页闭包

- `selective_vision_postprocess_job_service.py` 对已完成任务的每个观察 ID 回读追加写仓储，核成功状态、当前复合计划身份以及与预期原件页的一一对应。原有页/ID数量检查保留；不匹配则事实整理入口无可采用范围。未改失败重试、已成功页幂等复用或原OCR。新反例用错页记录证明拒绝，正常路径证明接受。
- 相关三组集中最终 `52 passed`、退出0。首次3项失败归因于复合计划身份比较方式和新反例缺既有来源声明，修正后复测。此项不是原始病例的医疗内容验收；手写/表格漏识别、整方案发布、W7/Q3未完成。无需重跑已覆盖的失败重试测试来制造新作业。当前模型及许可状态仍依现行配置/0925V1包，未下载/试跑新模型。
- 下方 A09 段仍有效；本轮 HEAD `6bd6ce95ebf08001b698ca25f38e1d3b28766c9b`、工作树未提交，未发模型、未改临床库、未正式发布或推送，`claims_complete=false`。

## 本轮最新增量：A09 无关补答文案不再重跑成功批次

- 首次方案解构提示与补答合同拆分摘要；成功检查点留存实际补答使用标记及补答材料摘要。仅未调用补答的批次可忽略补答文案变化，仍须通过原来源、线路、组成与发布门禁；已调用补答者文案变化需重算。历史未留痕者保守重算，摘要损坏拒绝。人工局部恢复也要求补答合同相同。执行身份 v130、组成身份 v2；旧回执未改。
- 服务/深审/传输三组合并 `200 passed`、退出0；这是新增 A09 路径的离线工程检查，不覆盖前轮目录四组219项，也非完整方案或临床验收。未发模型、未改数据库、未发布、未提交/推送。`claims_complete=false`。
- A10 仍由整份来源身份阻断跨来源版本复用；不能因此删全局哈希。A13 普通完成行为的观察见证语义仍未实现。下文较早“未处理 A09”的表述是当时状态，以本段为准。
- A10 只读追踪补充：`ProtocolControlDispositionBatch` 虽分别保存 owned/context 单元及冻结目标，`stable_protocol_control_batch_id` 仍包含整份 `coverage_manifest_id` 和批次序号；`ProtocolControlDiscoveryToDeepPlan` 也绑定全文文档摘要与完整来源清单。故跨版本即使单元正文相同，批次 ID、目标集合及可能的跨章引用都不保证相同。仅放宽 `_DEEP_SOURCE_IDENTITY_FIELDS` 会绕开这些依赖，现明确未实施。下一步需以旧/新批次的来源闭包、目录目标、上下文及顺序逐项建立映射和负例后才可考虑局部采纳；无证据时仍全局拒绝。

## 本次续作增量（以后述现场状态为准）

- A11 同批混合要求：`protocol_control_deconstructor.py` 将可装配的来源要求逐条装配并逐条经原批次门禁；不支持的要求保持未决。失败结果带 `partial_wire`，`protocol_control_execution.py` 的 v3 失败检查点保存它及来源解释，人工重试按批次、提示、线路和组件身份重新核对后才读回。`protocol_control_agent_transport.py` 新增独立来源补入会话，因为进程内 `_histories` 不能跨重启使用。新执行身份 v129，复用组成身份含局部恢复版本。
- 合成反例证明同批3条中2条保存、1条保持未决；服务级人工重试证明检查点可读、旧批不重新产生整稿、下一批正常处理；独立传输测试核新会话候选 Schema。集中四组 `219 passed`、退出0，5项第三方弃用警告；`git diff --check` 退出0。这是离线工程证据，不是条件/例外语义装配或真实方案完整发布。旧回执和临床库未改。
- 实际当前修改另含 `app/agents/protocol_control_agent_transport.py` 与 `tests/v2/protocols/test_protocol_control_agent_transport.py`；其余清单见下文。未处理 A09/A10 的跨来源变更精确复用、A13 普通动作消费者，以及 B 病例、W6/W7/Q3。`claims_complete=false`。后续只在获得收费模型/临床试跑的明确授权后，才能把此机制带入真实DOCX整方案；不可将本次合成通过写成临床验收。
- A13 已定位而未实施：阶段装配器对普通“完成/核查”动作写 `observation_policy.mode=unresolved`（没有假造 `single`），但 `app/domain/proposition_observations.py::combine_observations` 对 `unresolved` 恒返回未知。因此即便有对应完成记录，也无法在当前消费者给出有据结果。不能把它简单改成 `single` 或无条件 `any`；须定义并验证“完成行为的有源见证”与明确未完成、资料未提供的不同语义，再联动资格工作稿消费者。
- A09/A10 源码定位：`protocol_control_agent_prompt_template_sha256` 同时把基础提示与 `_CONTROL_REPAIR_CONTRACT` 算入一项摘要，即便旧成功作业未用修订也会因修订文案变化被列为重算；旧回执没有可证明的逐调用提示身份，因此不能事后反推“未用”。`_DEEP_SOURCE_IDENTITY_FIELDS` 当前比较整份来源哈希、覆盖清单及分包；原文一处脚注改动会在预检时整体拒绝跨版本采纳。要改成局部复用，先新增逐请求实际提示/修订使用记录与来源依赖闭包，再用未改上下文的批次正例和跨章引用反例证明安全，不能只删全局哈希比较。

## 接手入口与边界

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`；分支 `codex/phase5-clinical-facts-profile`；本轮检查时 HEAD 仍为 `6bd6ce95ebf08001b698ca25f38e1d3b28766c9b`，未提交、未推送、未 reset/clean。进入时先核实际 HEAD/dirty，不用此文本覆盖新工作。
- 现行目标/进度：同任务 `prd.md`、`design.md`、`implement.md`；0925V1 用户包 `/Users/smkzw/Downloads/enrollment_review_0925V1_6bd6ce9.zip`，其 `04_ACCEPTANCE_0925V1.md` 是待完成反例清单，不是已通过记录；旧无损暂停事实见 `HANDOFF_20260925_W6_REVIEW_AND_PAUSE.md`。`docs/PROJECT_CONTEXT.md` 文头已指向本轮。
- 起始 dirty 只有未跟踪的 `conference/`、`context/`、`metrics/`、`plans/codex_main_venue_*`、`prompts/conference/`、`reviews/`、`runs/conference/` 历史文件；保持原状。本轮修改仅下述已跟踪源码/测试/任务文档。
- 本包没有收费模型、临床作业恢复、模型下载、凭据变更、正式发布或 Git 推送授权；本轮均未做。原方案/病例/旧回执不改。隔离库只读查看：`/Users/smkzw/tmp/enrollment-review-w6-20260924-v102-isolated-data/enrollment-review-v2.sqlite3`。共享监听 8001、8002、8900、8910、20128 均未停用；8910 的进程 cwd 是医学经理工作台，不属本任务。

## 已做与真实证据

1. **原文覆盖 A**：`app/protocols/procedure_catalog.py` 修复访视表注释的末尾嵌套、前言/续行、同节编号列表恢复和下一节边界，版本 `required-procedures/v4`；反例在 `tests/v2/protocols/test_procedure_catalog_slice3.py`。真实冻结结构 `protocol_blocks/25c713e2…7903.json` 3,280块，SAR `body.t3` 表后28条编号注释/40个段落。新冻结目录 `f05217cc62924d4d9d2ce73968fdc8d5` 41项，引用37个表后段落；另3段在全方案来源清单而非该目录：`body.p279` 发现为基线控制候选、待深审；`body.p315`、`body.p316` 发现为后续访视非当前控制。不能把发现处置说成正式规则。真实回放曾发现新样式逻辑把另一个编号体系的子列表截断为21条/28段，修复后恢复28/40；这是合成反例不能代替真实原件的证据。
2. **复用/恢复 B**：`app/services/protocol_control_execution.py` 在创建长作业前对旧批次逐项预检，形成内容寻址 `protocol_control_reuse_plan`（允许的工件类型在 `app/evidence/artifacts.py`），分别标可复用、材料变化需重算和硬损坏拒绝；组成身份缺字段或摘要格式坏了按损坏拒绝，不伪装正常失效。新批次记录来源/发现计划/覆盖清单、提示正文与组成、作者Schema、装配/校验版本、请求线路摘要；旧回执无这些分项时不凭旧执行版本反推。执行时再次比对计划工件、批次与可复用批次组成身份。真实 v126 首批旧提示摘要 `327fed01…513771e`，当前组成摘要 `a084f09d…b8960276`；旧分项未存，不能证明具体哪项变化，故重算而非强行采纳。新执行版本 `phase5/protocol-control-execution/v128`，旧历史哈希不可变。传输回执尚无供应商实际返回模型名，不能伪称已核别名。
3. **条目定位 C 的前段**：`app/agents/protocol_control_source_interpretation.py` 把逐项目标核对错误变成 code、statement_id、实际 JSON 数组位置、source_refs、retry_class、affected_dependents；`app/agents/protocol_control_deconstructor.py` 不再从中文报错正则猜条目，`app/services/protocol_control_execution.py` 将该诊断保存在失败回执。倒序条目测试证明数组位置与陈述编号不同也能定位。混合条目的局部保存和恢复见文头续作增量。

## 检查与未证

- 前段相关集中命令：`.venv/bin/python -m pytest tests/v2/protocols/test_procedure_catalog_slice3.py tests/v2/services/test_protocol_control_execution.py tests/v2/protocols/test_slice58c_control_deconstructor.py -q`，当时 `180 passed`、退出0，5项第三方SWIG弃用警告；本次续作四组最新 `219 passed` 见文头。旧作者通过记录、本轮检查与未来临床验收必须分开。没有全库/浏览器/正式产品长作业验收。
- 0925V1 A01/A02/A04/A07/A08/A12及部分A03/A05/A06/A14有源码或局部反例；A11新增离线中间结果和重试正反例，但真实来源/模型及完整消费者闭环未证。A09/A10/A13/A15未闭合，不能以219项总数覆盖它们。尤其 A10 的脚注实质修改与无依赖批次复用仍受全局来源身份约束。D病例 B01–B10 未用授权脱敏原件完成独立评测；E小模型默认不启用，LensVLM-9B许可未改变。没有新的模型调用/成本数据。
- W6：新来源的官方+跨章完整同源发布未完成；旧 v123–v127 隔离作业失败终态，不恢复。W7：完整当前节点病例、报告、更正/补证后的新结果未完成。Q3：第二结构、Ego Lite宽屏交互、部署/备份恢复未完成。`claims_complete=false`。
- 未解决的方向风险：原文结构来源与语义引用不能合并；当前阶段控制候选需核召回和不实率。不能继续把每个新错误都转成专用补答后重跑整方案；已有来源解释和阶段装配器应按独立条目消化、冻结局部成果，工程字段失败不得改写成研究者医学判断。也不能为“提速”删严格发布门禁。

## 变更清单与下一动作

- 本轮已跟踪改动：`app/protocols/procedure_catalog.py`、`app/services/protocol_control_execution.py`、`app/evidence/artifacts.py`、`app/agents/protocol_control_source_interpretation.py`、`app/agents/protocol_control_deconstructor.py`；对应三份 `tests/v2/...`；同任务 `prd.md`、`design.md`、`implement.md` 及 `docs/PROJECT_CONTEXT.md`。均未提交。原作者旧通过结果保留在历史记录，不算本轮执行。
- **下一安全动作**：在不发模型、不改临床库的条件下，针对 A09/A10 建立真实结构来源变更与未使用修订提示变化的逐项依赖对照；先证明哪些批次确实无依赖，再决定是否放宽全局来源身份。A13 普通必做动作的“完成见证”需设计成与未提供资料、明确未完成不同的消费者语义，不能把 `unresolved` 偷换成 `single`。随后按0925V1 B01–B10建立获授权脱敏病例来源候选测试。收费模型/临床试跑仍须用户明确授权；授权前不要恢复旧作业或正式发布。
