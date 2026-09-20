# Execution Output: phase5-slice58l-d001-six-package-semantic-baseline-20260826 - worker_03

## Boundary And Context Check

- 已读取声明的执行上下文和计划，并补充读取冻结输入、六个包文件、run2运行证据及相关本地合同/门禁代码。
- 仅核对六个包：0059、0063、0069、0070、0073、0079；未运行其余131包。
- 未读取或修改生产路径、受试者材料、视觉测试材料或同工报告；未联网、未启动会议。
- 未修改任何工作区文件；runner报告文件未直接写入。
- 本报告提供独立执行证据，不构成最终临床、视觉或产品验收。

## Work Performed

### 1. 冻结输入与来源身份核对

六个外部 `package-*.json` 与 `controlled-input.json` 中对应的 `agent_input` 逐包Canonical JSON哈希完全一致；run2六个首次调用的 `prompt_sha256` 也全部与冻结包输入一致。

共同身份：

- 选定期别：`phase_ii`
- 对侧期别：`phase_iii`
- 协议版本：`D001-02-002:v1.0:phase-ii`
- 协议SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 选定包：6
- 排除冻结包：131
- `claims_complete=false`
- 运行合同：每包单独调用、最多2次schema修复、同会话修复、不得提交聚合文件

六包期别/义务核对：

| 包 | 代表性分层 | owned目标 | source phase scope | 关键观察 |
|---|---|---:|---|---|
| 0059 | 对侧期引用 | 12 | 全部 `unknown` | 排除标准；无同义务正向跨期证据 |
| 0063 | validity/retest | 6 | 全部 `unknown` | 生活方式及重筛选要求；无明确跨期适用证据 |
| 0069 | shared unknown leaf | 11 | 全部 `unknown` | 合并用药/治疗及Table 5；不能由流程表全局广播 |
| 0070 | Table 5 | 12 | 全部 `unknown` | 禁止用药具体行；期别适用性未明 |
| 0073 | explicit phase-II flow | 9 | 全部 `unknown` | 研究评估/程序；存在同一义务族的明确共享证据 |
| 0079 | TB/pregnancy | 11 | 10个`unknown`、1个`mixed` | `p815`同时列出II期和III期不同时间点，必须结构拆分或阻断 |

### 2. 期别处置和同一义务边界核对

- 0059、0063、0069、0070的目标均为`unknown`。模型默认输出`cross_phase_shared`或`shared`缺乏足够同一义务族证据，应保持未解决，不能依靠共同章节标题、流程表或泛化的“II/III一致”结论进行全局扩散。
- 0073的`p765`明确说明除给药时长外，II期和III期评估与程序一致；`p937`进一步存在III期筛选对II期研究的交叉引用。二者均属于“研究评估和程序”同一义务边界，模型最终输出`cross_phase_shared`在语义方向上有依据。
- 0079的`p815`不是普通共享单元，而是混合单元：明确区分第12周（II期）和第16、52周（III期）。将其整体判为`cross_phase_shared`属于语义越界，即使修正证据索引，也不应由单值语义Agent直接决定。
- 0059模型引用流程表作为跨期共享依据，不能替代排除标准本身的同义务跨期证据。
- 0070模型最终将12个Table 5目标标为`unresolved`，方向符合证据边界；不能将Table 5标题或章节共享解释为II/III共同适用。

### 3. 实际模型运行和门禁结果

使用实际run2证据：

- 模型：`Qwen3.8-27B-oQ8e-fp16-mtp`
- 六包总耗时：`6961.689258 s`，约116.0分钟
- 已解析：2包（0070、0073）
- 未解析需复核：4包（0059、0063、0069、0079）
- 所有包均在同一会话内完成首次调用及修复调用

| 包 | 调用次数 | 耗时(s) | 门禁状态 | 主要问题 |
|---|---:|---:|---|---|
| 0059 | 3 | 2557.767694 | `needs_review` | 3次均`EVIDENCE_SPAN_UNIT_MISMATCH` |
| 0063 | 3 | 348.617462 | `needs_review` | 首次wire schema错误，后续理由字段不完整 |
| 0069 | 3 | 964.101418 | `needs_review` | 证据索引错位；最终`seamless_candidate`超出允许范围 |
| 0070 | 2 | 969.121482 | `parsed` | 12个目标均`unresolved` |
| 0073 | 2 | 946.043781 | `parsed` | 9个目标均`cross_phase_shared` |
| 0079 | 3 | 1176.037421 | `needs_review` | 3次均`EVIDENCE_SPAN_UNIT_MISMATCH` |

主要根因定位：

- 0059、0069、0079反复把当前目标的source span与第一个owned source unit绑定，导致目标索引与证据单元不一致。这是模型的证据索引绑定行为，不是冻结输入身份错误。
- 0063首轮只返回1个group，修复后虽补齐6个目标，但候选期别/理由字段仍不符合合同。
- 0069第三次修复基本修正了source unit索引，但输出`seamless_candidate`；在选定期别为II、对侧期别为III时，该候选范围被确定性门禁拒绝。
- 0079对`p815`使用共享的`p765`作为泛化依据，将混合单元整体判定为跨期共享；这是上游结构边界和模型语义行为共同暴露的问题。
- 0070首次引用Table 5标题单元处理所有目标，后续修复改为逐行证据并成功解析。
- 0073首次理由缺少支持关系，第二次同会话修复后成功解析，且证据指向`p765/p937`及对应评估流程单元。

## Artifacts And Evidence

重点证据位于：

- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/controlled-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/controlled-input.sha256`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0059-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0063-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0069-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0070-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0073-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/package-0079-agent-input.json`
- `artifacts/phase5-slice58l-d001-six-package-semantic-baseline-20260826/qwen38-baseline-host-real-run2-20260826/summary.json`
- 各包下的`runner-result.json`、`raw-responses.json`、`transport-calls.json`

确定性门禁错误汇总：

- `EVIDENCE_SPAN_UNIT_MISMATCH`：7条issue记录，集中在0059、0069、0079
- `WIRE_SCHEMA_INVALID`：2条记录
- `RATIONALE_INCOMPLETE`：3条记录
- `UNRESOLVED_EVIDENCE_MISSING`：1条记录
- `CANDIDATE_SCOPE_UNSUPPORTED`：1条记录，来自0069的`seamless_candidate`

运行前另有两类非质量证据：

- 首次host run因模型busy/unload pending，六包均transport failed；不能作为质量基线。
- `worker_02`独立transport预检因socket权限`[Errno 1] Operation not permitted`失败；无模型输出，不能与run2质量结果混淆。

## Commands And Observations

执行了以下只读核查：

- `sed`读取声明的context和plan：确认六包allowlist、禁止131包、同会话修复和无subject/visual边界。
- `find`/`jq`列出冻结输入、六包、run2目录及逐包状态。
- `jq`提取包ID、目标数、phase scope、prompt hash、runner issue codes。
- `shasum -a 256`核对controlled input、coverage manifest、freeze metadata、control matrix、unit-phase view及六包输入。
- `jq`核对run2每包首次prompt hash与冻结包prompt hash。
- 读取本地`phase_applicability`合同、Agent提示和确定性门禁实现，确认source unit/span归属检查、候选期别限制及mixed单元未被结构性拒绝的现状。
- 读取run2 raw responses，重建模型首次输出及同会话修复行为。

尝试本地独立调用hydrate/gate进行重放，但环境只有系统`/usr/bin/python3` 3.9.6；项目代码使用`date | None`等Python 3.10+类型语法，导入阶段失败。未安装依赖或修改环境。

## Blockers Or Missing Environment

### 已确认阻塞

- 当前工作区没有可用项目Python虚拟环境；系统Python为3.9.6，无法独立重放项目门禁代码。
- 因未安装或切换环境，本报告的门禁结论基于runner保存的确定性结果、JSON结构、source map和raw response交叉核对，而非本地二次执行。
- 四包未解析，当前不能形成六包完整质量基线。
- 当前耗时只有一次有效run2，且配置max tokens与实际有效本地max tokens存在差异（配置60000、实际8192）；不宜作为通用速度结论。
- 未进行临床人工复核；0073的共享结论仍需Codex按临床/产品边界最终判断。

### 共享合同/模型行为问题

1. `p815`混合owned unit已经进入单值语义Agent，但现有门禁对`mixed` source scope没有强制结构阻断。即使source index修正，模型仍可能输出错误的整体`cross_phase_shared`。
2. 合同允许`shared`作为未解决结果的candidate scope，0070因此能够解析为12个`unresolved`。需明确未解决结果究竟应列II/III候选，还是允许`shared`仅作为“共享适用性待确认”的占位。
3. 模型存在稳定的source unit/span错配行为。当前合同虽能拦截，但反复修复无法稳定纠正，应该增加确定性输入提示或预检，而不是仅增加重试次数。

## Rerun Requests Or Next Step

建议不要立即重新运行模型。先完成以下最小修订：

1. 将0079的`p815`拆为II期、III期两个结构单元，或在进入语义Agent前标记为`structural_blocked`；禁止mixed owned unit直接产生单一最终期别处置。
2. 增加确定性输入/门禁提示：owned target的自证据必须引用对应target source unit，且source span必须属于该unit；对连续目标索引生成明确source-unit映射。
3. 明确`unresolved`的candidate scope合同，避免仅以`shared`掩盖实际的II/III适用性不确定。
4. 保留当前run2作为失败/部分成功证据，不将0070、0073的解析状态等同于临床最终接受；先由Codex人工复核0073，并在0079结构拆分后复核。
5. 修订后仅重跑六包，仍保持逐包、同会话最多2次修复，不得扩展至131包。

后续质量门槛建议：

- 六包均成功解析；
- 全部目标均有输出（0079拆分后目标数应按新结构重新确认）；
- 无`EVIDENCE_SPAN_UNIT_MISMATCH`；
- 无UNKNOWN/MIXED/不支持的`seamless_candidate`；
- unresolved结果保留具体未解决证据；
- 不发生跨义务族全局广播；
- `claims_complete`保持`false`。

速度测试边界：

- 当前116分钟仅作为该单次六包run2的观察值，不作为模型通用速度基线。
- 后续速度测试应分别记录首次调用与修复调用耗时、冷/热模型状态、实际有效token上限、每包context单位数/字符数，并避免与模型busy、socket权限或并发负载混在同一结果中。
- 在六包质量门禁全部通过前，不应开展更大规模速度或质量扩展测试。

需Codex确认的精确决策点：

- 是否同意将`p815`正式改为结构拆分/阻断，而不是继续交给单值语义Agent？
- 对于`unresolved`结果，是否要求显式保留II期与III期候选，而不再允许仅用`shared`作为占位？
