我先读会议上下文和主会场计划，再只读核对 e7f34d05 的入排实现与 0922V2 专家意见。上下文已定位到冻结基线 e7f34d05 与交付包。接下来核对专家意见原文和计划里点名的资格选择、来源采信、跨章发布与更正失效实现。计划与专家意见已读完。下一步按引用行核对资格选择、来源政策、跨章发布和更正失效的真实代码，确认哪些裁决被源码支持。只读核对已完成。活工作台在整条件被拒时会折成 `None` 并走回旧类别匹配，跨章控制项也不在当前资格接口里；下面按证据、推断、建议和未决分开写。

# Conference Output: enrollment-0922-plan-review - evidence_single_object

## Output

本轮是只读审阅，不是验收。工作树 `HEAD` 为 `e7f34d0508c05481164cf13569f66ddf64e2e74f`；`git status` 只有未跟踪的交付/会议文件，没有已跟踪产品源码改动。未改文件，未跑测试、构建、模型、浏览器或网络。`09_REVIEW_EVIDENCE.md` 里的 `npm run build` 与 14 项 pytest 失败是该文件的记录，本轮没有复跑。

**能否把 W0–W7 加 Q1–Q3 原样交给 gpt-5.6-sol:medium：不能。** 主 OCR、局部核实、格式错误不得写成研究者判断、工作稿与正式结果同语义、三次集中验收，这些方向已经写明。还会改变合同形状的三处仍是“或”：资格内核是调用、读已有结果，还是再抽纯函数；跨章是并列字段还是塞进条款；守望脚本是退役还是修补。不先闭合，执行者会猜出第二套临床合同。闭合下面的暂定路径后，不必再问产品方向。

暂定路径：资格只调用已有 `_select_with_ordering` / `_select_facts_for_identity`，授权留在发布；空选择保持显式空，禁止 `None`。活接口增加与冻结历史同形的 `controls`，不伪造官方编号。`scripts/wp08_muse_spark_watch.sh` 从恢复说明移除且禁止执行。`source_policy.py` 只作核实词汇，不新建观察库。否定检索按现有 scope 与事实头失效，不新做影响引擎。

### 证据

1. 整条件选择没有接到工作稿。`eligibility_review_projection.py` 的 `_load_binding_predicate_fact_ids`（865–960 行）只把 `pair_direct_selection_rejection_reasons` 为空的 `fact_id` 放进映射，不看 `fact_attribute`、日期资格、`observation_policy` 或排序。868–870 行的注释写“选择内核与正式发布完全一致”，与同文件实现不符。960 行 `return` 之后 961–970 行是旧的双路一致逻辑，当前到不了。907–915 行和 925–932 行用 `except Exception: continue` 跳过坏载荷；作用域内没有可用任务时 916–917 行返回 `None`。
2. 空映射被折成旧路径。754–767 行先滤掉不在已接受事实里的 id，再删掉空列表；全部为空时 `or None`。`expression.py` 648–652 行写明 `None` 保留旧类别路径，空列表不走该路径。524–526 行只在已有 `observation_policy` 且 `fact_ids is None` 时返回 `observation_selection_unverified`。513–535 行在无 policy 且 `fact_ids is None` 时按别名或 `fact_type` 重新收集事实。585–609 行里，`single` 不在 `any`/`all` 分支；多个事实的值、单位、极性相同且没有冲突组时，仍会给出确定真值。
3. 正式选择内核在另一处，且更严。`qualified_binding_selection.py` 224–254 行：只有日期则 `no_usable_qualified_pair`；值没有合格事件日期则 `event_date_not_qualified_for_selected_value`；无 policy 或 `single` 下多个事实则 `multiple_usable_pairs_without_selection_policy`。287–325 行的 `_select_with_ordering` 才处理范围和排序。这些函数本身不调用 `_validate_authorization`（137 行起）。`component_review.py` 26–48 行只是把调用方给的 `predicate_fact_ids` 交进去，自己不补选择。
4. 跨章没有进入当前工作台合同。投影 700 行调用 `project_clause_pack(rule_set)`，不带 `control_publication`，随后只循环 `clauses`。`published_clause_pack.py` 10–14 行才会附上控制发布。`frozen_review_calculation.py` 56–84 行单独计算控制项。`eligibility_review.py` 83–93、127–141 行的响应只有 `clauses`，`extra=forbid`，且 `min_length=1`。冻结历史 `review_history.py` 584–589、641 行另有 `controls`。`protocol_publication_service.py` 382–399 行在 `control_job_id is None` 时仍发布官方规则，`control_publication` 保持 `None`；516–525 行只要求任务 id 与检查点成对，不要求“有控制”或“有来源的零控制”。396 行失败时把异常和 traceback 打到 stderr。`clause_pack.py` 161–171 行把全部控制项的页读方向改成 `DETERMINISTIC`，注释写这不是四层临床求值。
5. 新来源合同没有生产消费者，页覆盖却能用字符串放行。全库没有 `from app.domain.contracts.source_policy`。该文件 69–75 行的 `is_verified` 不含 `self_consistent`。`page_review.py` 427–445 行允许非空 `source_policy_kind` 加上 `self_consistent` 等四个字符串，在没有 `reconciliation_id` 时仍为 `ACCEPTED`。另有两套同名不同物：`ControlEvidenceSourcePolicy`、`binding_qualification.py` 的 `SourcePolicyStatus`。`page_review_job_service.py` 51–73、161–162 行始终计划并要求 `MAIN_A` 与 `MAIN_B`。`app/api/v2/app.py` 273 行把规范化服务设为 `require_page_review=True`；`fact_normalization_command_service.py` 554–559 行因此要选页覆盖，而不是按 `SourcePolicy` 选来源。
6. 400 根因仍未被这条产品客户端证明。`page_review_transport_options.py` 19–21 行对非 `omlx`/`mtplx` 返回 `{}`。`page_review_harness.py` 711–734 行不注入 `response_format`，也没有 `x-opencode-session`。971、992 行用 `result.response_model or route.model` 填主记录；973 行的 `requested_model` 只进身份哈希。守望脚本 17–18 行却另发 session 头，与产品客户端不是同一请求。
7. 更正预览不是同观察，否定检索也不会随事实更新。`fact_correction_service.py` 482–532 行只比 `asserted_object` 和 locator 交集，未知对象也可以相等；这是预览字段。`fact_correction_impact.py` 的闭包有事实、事件、暴露、冲突、期望和 Profile，没有检索摘要。`judgment_search_repository.py` 151–192 行按节点、处理修订和规则版本取最新摘要，不比较 `scope_sha256`，也不比较其后的事实头。投影 466–474 行把“已搜全部提供页且无候选”变成 `professional_judgment`，除非该要求已经是 `OBSERVED`。`judgment_search_source.py` 205–213 行其实已经有 scope 哈希。
8. 方案预清洗会补研究者判断。`protocol_control_deconstructor.py` 902–941 行对校验失败或漏填的 evaluation 写入 `determination_mode=investigator_judgment`，命题来自 `attribute`、`source_term` 或固定句“待人工核实的控制条件”；945–975 行解析入口会调用它。
9. 规模脚本与守望脚本。`build_scale_validation_set.py` 53 行使用 `os`，`import os` 在 `main` 的 61 行；默认输出在仓库内，会走进这条路径。53–56 行对 `SCALE_SET_DIR` 不再次核对是否仍在源码树。90–116 行非 PDF 的 `pages` 保持 `None`，`if pages` 不计入 `total_pages`。`run_scale_validation.py` 14–17 行说拆解、绑定、资格和正式发布会“报告为前置、不静默跳过”；168–224 行实际只做到页审、规范化和投影，HTTP 200 且无错误信封就返回 0，空 `clauses` 也能成功，没有 `not_run` 记录。`wp08_muse_spark_watch.sh` 在 `cd` 之前从当前目录 `.env` 取密钥（7–10 行），读取 `~/.omp/install-id`（5 行），写死受试者与节点（9–12 行），用任意含 `finish_reason` 的响应当恢复（21 行），并用 `upgrade_or_fail` 打开库（47–48 行）。注释写 6 小时，循环是 4032 次、间隔 300 秒。
10. 前端类型漂移与本文件一致，构建退出码本轮未复跑。后端 `app/domain/contracts/enums.py` 102–142 行已有 `pending_control_applicability` 和 `control_applicability_pending`。前端 `enums.ts` 76–81 行的 `ExpectationStatus` 停在 `not_due`，但 `GapType` 含控制项。`labels.ts` 142 行把控制状态写进窄类型。`wire.ts` 85–100 行的 `GapCountsWire` 没有 `control_applicability_pending`，`mappers.ts` 160–164 行用 `GapType` 去索引它。`EligibilityWorkbenchPage.tsx` 365–369 行 `severityOf` 无使用。测试第 3 行导入 `cleanup` 且全文件无调用；250 行对 `within()` 的结果取 `parentElement`。267 行起的分组夹具省略 `actionOwner` / `actionDetail` / `actionEvidence`，而 `eligibilityReviewViewModels.ts` 35–37 行这三项是必填（允许 `null`，不允许缺省）。55、71、87 行的 `actionOwner: null` 与该类型相符。工作台 385–388 行组按严重性排序，组成员保持输入顺序；833 行默认 `groups[0]?.clauses[0]`。607–622 行无已选事实时把 `pages[0]` 当作引用页。962 行资料版本用 `selectedEpisode.revision`。

0922V2 的 R2-01、02、04、05、08、10、11 与上述源码一致。R2-03、07 的“交接证据不足 / 身份被回填”成立；供应商 400 的真实原因未证实。R2-06 的脚本缺口成立。R2-09 的栏宽本轮未做浏览器测量。R2-12 成立，而且脚本还写死了具体受试者并会迁移数据库。交付包 C01–C10 的方向与源码相符；C01 把“有 policy 即受保护”说窄了，见推断。

### 推断

无 `observation_policy` 的原子，在资格全部拒绝、过滤后全空、或根本没有资格任务时，都会得到 `None`，然后按事实类别重新进入比较。这和 763–764 行“空选择留给未核实、不冒充 FALSE”相反。有 policy 时，`None` 会停在未核实；可是投影一旦给出 fact id，`single` 下两个同值事实仍可得到确定结论，正式选择则会拒绝。因此“有 policy 就不会错”不成立。这仍是选择层差异，不是已经看到的某份真实个例误判。

活工作台即使把官方条款的计算补齐，`EligibilityReviewResponse` 仍不会携带控制项。冻结报告可以有控制项。用户看到的当前审核和已冻结报告不是同一要求范围。`min_length=1` 还会让“只有跨章要求、没有官方条款”无法合法返回。

`self_consistent` 放行是合同洞。本轮没有看到生产代码写入这两个可选字符串，不能说现网事实已经由此被采信。页读把控制项改成确定性方向，按注释只影响读页，不自动等于临床结论被改写；在投影不算控制项的前提下，用户当前屏幕仍会漏掉它们。

同一处理修订上新发布或更正事实后，旧的“全页无候选”摘要仍可被投影成研究者判断。新处理修订会因为修订号不同而自然对不上旧摘要。W5 若再造一套失效引擎，会和这条已有分界重复。

### 建议

按严重度，只改计划里对应的一句，不新增阶段或框架。

- P1。W1 删掉“抽取最小纯函数或复用”里的“或”。工作稿调用现有无授权副作用的 `_select_with_ordering`；输出保留已选 pair、属性、日期来源、policy、未决原因。全拒绝、无任务、坏载荷、陈旧任务都用显式状态，禁止折成 `None`，禁止回退别名。960 行后的死代码删除。坏 JSON 不得静默改用更旧的一条。Q1 反例除“只有日期、缺日期、single 多值、全拒绝”外，加上“single 且同值多条不得确定”。
- P1。W1/W4 写明活响应增加并列 `controls`，字段对齐 `review_history.py` 已有展示，官方编号只留在官方条款。禁止把控制项塞进 `clauses`。`clauses` 允许为空的条件仅是：同一次发布有来源化的控制覆盖，包括明确的零控制。页读方向覆盖不得当作临床 `determination_mode`。
- P1。W2 保留“非法 evaluation 不得补成无来源的 `investigator_judgment`”。已发布数据只列影响清单，不改原 JSON。396 行的 `print` 与 traceback 删掉，只留已有的 `PublicationLineageError`。
- P1。W3 写明采用 `SourcePolicy` / `VerificationStatus`，并且以 `is_verified` 为准，因此 `self_consistent` 不能单独让页成为 `ACCEPTED`。不要把 `ObservationRecord` 做成第二套事实，也不要接上 `ControlEvidenceSourcePolicy` 或绑定状态字面量。旧双读只在显式 legacy。不要只把 `require_page_review` 改成 `False`。新主路径若不使用失败中的 provider，就不为旧双读做 25 页矩阵。
- P1。W0 的六个前端错误按后端枚举补齐窄类型和 `GapCountsWire`，保留控制项标签。分组夹具补上三个动作字段。不要为了编译删掉 `pending_control_applicability`。`severityOf` 若不用就删，排序仍用现有 `clauseIssueKey`。
- P2。W5 预览继续只列候选，未知对象不相等，不按同页写值。否定摘要仅在 `scope_sha256` 等于当前清单、且没有更新的事实或期望头时，才可变成研究者判断缺口。不新表。
- P2。W0/W6 规模脚本：模块级 `os`；所有回退路径解析后再检查源码树和软链；非 PDF 按解码帧数，不能确定则 `unknown` 且不得算完整。驱动只编排正式入口，绑定与资格未跑必须记 `not_run`，空条款返回非 0。文档与代码不一致时改代码。
- P2。W0 关闭“确需保留则修补守望”。从恢复说明删除该脚本，不执行、不提交页审、不调用 `upgrade_or_fail`。

Q1 必须挡住 W3 的真实模型调用和 W6 的新方案：先看到非法 evaluation 保持技术未决，并且同一冻结输入下工作稿与正式选择对上述反例一致。做不到就不要进入读页或全链。

### 不确定性

未复跑专家探针、pytest、`npm run build` 和任何个例，所以没有新的最终误判、构建退出码或 400 响应体。没有统计现网有多少原子缺少 `observation_policy`，也没有打开已发布控制项，不能说历史发布已被预清洗污染。没有证明 `source_policy_kind` 已写入生产覆盖记录。栏宽、引用红框和 1080p/2K/4K 未在浏览器核实。`09` 中的 14 项失败里，哪一些是夹具、哪一些是产品，本轮未分类；其中“期望 `source_conflict`、得到 `observation_selection_unverified`”与 524–526 行同向，但是推断，不是复跑结果。

### 异议

交付包把 C01 的有 policy 分支写成基本安全，源码不支持。W1“抽取纯函数或复用”会让执行者再写一套选择器，而正式内核已经在 `qualified_binding_selection.py`。W0“守望确需保留”不安全：该脚本写死节点、读个人安装标识，并会升级数据库。W3 若把未使用的 `source_policy.py` 整模块落地，会把 `ObservationRecord` 变成平行事实。W5 若新做观察身份系统，会绕过已有 locator、属性和 scope 哈希。规模脚本头上的“前置流程会报告”目前是不实描述。这些都不是再加一个 Phase 能解决的。

### 决定点与给 Codex 的问题

只需回这三句，执行即可按暂定路径开工，不必再拆产品方向。

1. 是否同意工作稿直接调用现有 `_select_with_ordering`，而不是新纯函数，也不是只读已授权后的落盘结果？
2. 是否同意活资格响应增加并列 `controls`，并允许在有来源化零控制覆盖时官方条款为空？
3. 是否同意守望脚本只退役、不修补、不执行？

未回答时的安全做法：不改选择语义、不发布跨章、不跑该脚本、不启动模型或服务。
