# 会议输出：qwen-bounded-completion-review-20260910 - evidence_single_object

## 输出

续审第六遍（v13 逐页判读措辞 + 提示包缩减 + sar17 证据）。边界遵守：只读；未读两目录中的 `response-0.json`/`stream-*`/`request-0.json`（授权清单外且含私有推理）；无模型调用、无写入。

### v13 措辞评估：无临床范围矛盾，但“完整性”目前是无验证的指令

新增四句（harness 392–396 行）：先按原件顺序完整读取再列条款关系；**facts 不按条款相关性或异常与否筛选、正常结果也保留、同页多张报告分别读取不遗漏**；结束前逐项核对项目/结果/单位/日期；参考范围不当作结果。裁定：

- **无矛盾**。完整性义务限定在 `facts`（页内可见范围，与开头“只报告本页可见事实”的页界限定兼容），相关性筛选只作用于 `clause_signals`（“只报告本页实际涉及条款”）——两个输出数组的职责被显式分开，与源设计（完整采集、正常结果初始 UI 隐藏）一致。“正常结果也保留”是包含性措辞（“也保留”），未把正常/异常判断委托给模型（polarity 仍限于原文肯定/否定/不确定/未说明）。
- **无虚假声明、不掩盖失败**：record 仍只承载模型实际返回的内容，`has_eligibility_value` 语义未变。但要注意两点：(1) 测试只断言子串在场与双读道对称（`test_page_review_harness.py:70-84`）——**指令在场 ≠ 召回**，sar17 的 v12 完成运行（7/34 数值金标命中）正是这个差距的实测；(2) 完整性义务抬高密集检验页的输出量，与输出预算/length 重试的碰撞面变大——harness 已有翻倍重试与 early-termination 守卫，**漏采本身不可检测**（无金标时），这是措辞无法弥补的固有缺口，只能靠金标对账度量。
- v13 的召回改善**当前零证据**：唯一会检验它的运行（complete-page-contract）死于传输层（`peer closed connection…incomplete chunked read`，运行时 exit 137 内存压力）——按限定：不做临床结论、不主张 OOM 唯一成因（单样本、多因可能）、AR 后续 pending 不作评审证据。

### 提示包最小无损缩减建议

现状：`page_review_prompt_pack.py` 仅做 `exclude_none` + source_text 去重；sar17 实测输入文本 35,049 tokens（另图像 16,384）——大头仍在。可做的最小无损削减（只动投影副本，权威 ClausePack 与校验不变）：

1. **删 `rule_id`、`rule_component_id`**（可再评估 `display_code`）：纯不透明标识，输出契约只绑 `clause_id`（clause_signals），提示词与 `evaluate_page_review_response` 校验均不引用它们；配一个“clause_id/source_text_ref 完备性 + 输出无引用被删键”的测试。
2. **output_schema 递归剥离 `title` 注解键**：pydantic json_schema 为每个子模式生成的类名 title 是纯注解，验证语义不变，在同提示 JSON 内属于同类最小削减。
3. **`exclude_defaults` 严禁整体启用**（Codex 警告成立且我独立确认）：`RuleExpression` 是 `kind` 判别联合，`AtomicExpression.kind` 默认 `"predicate"` 会被整体 exclude 掉——投影无法 round-trip、模型失去显式节点类型。若要动，仅允许字段白名单（如空 `evidence_requirements` 列表）并**必须**加 `ClausePack.model_validate` 往返等价测试。
4. **不可动**：`source_texts`（语义锚）、expression 树的谓词内容（判别性词项/阈值是识别相关性的提示，删即变选择性抽取）、false/零值/negated、`clause_id/official_code/kind/determination_mode` 与身份字段（clause_pack_id/sha/rule_set/protocol_version）。
5. 诚实定量：上述削减是低个位数百分比；文本大头（条款原文+表达式树）与图像按设计保留——无损路线无法显著缩小，显著缩小必然语义有损，不应在本任务内做。缩减效果用现有 CPU tokenizer admission 前后计数即可量化，无需模型调用。

### sar17 证据状态（按限定表述）

- current-harness 运行：`prompt_version: page-review-r3/v12`（record 确认），完成、finish=stop、14 facts/6 signals/6 handwriting、prompt 37,196 tok——**7/34 数值金标命中是唯一已完成的召回数据点**（gold 不在输入，方法正确）。
- complete-page-contract 运行：同页同测量脚本（measurement_sha 一致）、仅提示哈希不同（v13），传输中断、无 record——**不产生任何临床信号**。

### 有界的下一步验证（非验收）

1. 在核实过空闲内存的运行时重放 v13 同冻结输入：判据=完成且 finish=stop，并输出**逐项金标对账工件**（34 项数值金标 matched/missing/extra + facts 计数对比 v12 的 14），把“指令在场≠召回”变成可追踪的版本间召回差；临床验收不在本任务范围。
2. 落地第 1、2 项缩减后用 CPU tokenizer 计数前后对比（无模型调用），连同 round-trip 测试一起提交。
3. OOM 归因留待 AR 路线，不在此下结论。

### 不确定度登记

未读两运行 request/response/stream（授权与私有推理边界）；7/34 的金标明细与判定口径未在授权工件内（只有所有权声明）；缩减收益的精确 token 数未实测（需冻结输入重建提示，超出本遍授权）。以上不影响本遍结论：v13 无矛盾但召回未证、缩减方案以“最小且可测”为界、两项运行均不构成临床证据。
