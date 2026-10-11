# Harness 修复与横评交接

## 2026-09-10 07:39 已无损暂停

本节覆盖下文继续执行状态。用户要求立即暂停后，1876/PID65908 SIGINT退出130，oMLX16975/PID46438 TERM退出143；服务日志确认卸载模型、回收内存、引擎及服务关闭。独立复核均结束。17个完整调用4480.163秒/149356输出，最后在途请求被用户授权中断，不能算模型失败或完整总耗时。当前隔离任务bc103cde5e7546f6b3e593fee9b707b4尚未完成，无临床验收。所有原始流/响应/缓存/修改保留，不自动恢复。1419协议回归通过；语义修复重附冻结来源代码晚于本轮启动，仍需真实小样验证。详细安全恢复步骤见同目录CHECKPOINT最新顶部；独立复盘见runs/conference/qwen-bounded-completion-review-20260910/retrospective.md。

## 最新续行：2026-09-10，优化—验证循环

最新状态覆盖下文05:36：76550已自然终止，failed_final，第7/17批补答仍缺两条；无草稿或临床验收。发现正式表达绕过历史压缩和范围约束，已将本地批次能力与表达方式解耦，加入正式Schema冻结编号/数量限制，保留原顺序/重复及临床校验。31项聚焦测试通过，全protocols44596在途。唯一服务oMLX16975，新隔离复测1876：diagnostic-formal-bounded-omlx-medium-protocol-d001，任务bc103cde5e7546f6b3e593fee9b707b4。说明文字保留时长却遗漏计算条件的问题仍未解决，不算成功；新增修订尚待独立续审。标准化横评未完成，当前持续执行，勿按旧暂停段操作。

05:36最新状态优先：MTPLX50408两轮stop但两份正文未闭合，格式纠正后失败，总1323.031秒/28457输出；已idle后关闭60145/PID36033，exit143。当前唯一oMLX16975；76550在新隔离原始D001输入上运行--formal-wire（任务9971d45778bf45aaa135fd08df522025）。新增compact_wire=False仅本地显式选择，默认不变，复用现有正式合同而非新造harness。独立33176同会话zcode/GLM-5.3:max审过贯通，建议已加入差异元数据与53项回归。实际oMLX xgrammar及同分词器CPU编译成功0.607秒，不代表临床通过。正式表达少了解码期scope枚举/基数约束，因此实验不是严格单变量；后置校验保留，不能将差异全归表示法。源文件/提取正文/块数/期别与旧D001完全一致；详见CHECKPOINT，不按下文旧在途号启动。

本段优先于下方旧在途号：oMLX三档同SAR17原生Schema诊断已结束、服务已卸载关闭；medium1476.797秒/45227输出，low513.382秒/15507输出，xhigh990.754秒/30274输出，均34/34生化数值匹配，均cache0。low未独立保留报告时间；xhigh保留上下报告6个采样/接收/报告时分。手写姓名与范围未临床验收，不能据数值齐全称质量无损。补充原图核对见artifacts/qwen-three-platform-20260909-v3/sar17-supplemental-source-qc.md；不是正式全矩阵或权威修订验收。

新增page_review_transport_options复用同一output_schema及oMLX兼容投影，产品SDK和计量共用；实际返回transport_contract参与版本，不能仅凭provider或Warning null推定启用语法。真实SDK的raw_response.parse是同步，已修并测试；218项相关回归通过/1真实连接跳过，90聚焦重叠不可相加。原生约束medium反而较旧格式修复总耗时更长，性能优越性未成立。

MTPLX完整页fresh首次请求345.499秒断流，sustained单因素328.131秒同样断流；两请求SHA完全相同。sustained日志明确allocator_fraction1.431/1.258、停顿后仍有token进度，不能判为纯思维循环。两个服务均已不在；tee管道退出0不代表服务优雅退出。现60145为唯一MTPLX turbo服务，仅MTPLX_VISION_SESSION_CACHE=0；50408正在diagnostic-mtplx-no-vision-session-medium-sar17。源码确认SSD缓存off并不关闭图片内存会话缓存，因此此轮保持完整提示与图像仅验证缓存路径。不提高内存上限、不丢条款、不改产品默认配置；失败时不重试同一假设。程序化无损重复对象检查只发现少量时间结构重复，暂不足以解释或解决35K提示负担，未实施有损删减。

03:37覆盖旧在途状态：仅oMLX74213运行、页17复测33001在途；下文所有MTPLX/旧oMLX/MLXServe调用均终态。协议提示已纠正正式/compact字段位置冲突及开放列举逻辑矛盾，实际产品wire解析加入诊断校验，但两平台仍有频次或原文连续性错误，未通过。页级提示v13明确完整facts与相关clause_signals分工，80项相关测试通过；独立续审同意范围但不认临床召回。MTPLX旧页17只7/34数值匹配，新提示试验连接中断、服务137退出，不能采信部分42项正文；AR诊断被接口明确拒绝图片，已关闭。计量增加HTTP错误正文保存，避免只记400而丢根因。不要重复相同MTPLX高内存配置，不改原资料、不回填临床结果。详细性能、配置、失败证据和后续核查在CHECKPOINT最新顶部。

最新实质修复：原nonblank正则被xgrammar按整串解释，迫使完整分类词变单字。锚定修正虽Schema等价却被CPU和真实循环证伪（绕过JSON转义）。因此正式oMLX传输新增最小decoding projection，删该生成约束但保留原Schema/strip验收，不改其他provider；原始请求与失败不改。safe-strings调用已stop，577.333秒/19333输出，完整词恢复、无循环、格式通过，但临床频次仍遗漏。当前83327同修复另一组条款验证中，唯一服务43758；不要当验收/排名。第五次独立续审认可边界并撤回先前无转义风险推论。详情以CHECKPOINT顶部和artifacts/.../nonblank-grammar-diagnosis.md为准。

接入审计补充（覆盖下文旧服务号）：当前服务为隔离 omlx-diagnostic-runtime-reasoning，PID76934；open-scope调用已结束且不合格。隐藏server.log确认 parser=qwen 在当前库不存在，strict请求已明确降级为提示，之前关于正确分段的推论撤回。配置 thinking_budget 也不是有效设置键；当前49036正在显式请求 thinking_budget=131072诊断，共享max_tokens不变，仍不能当严格约束样本。已准备但未启动 omlx-diagnostic-runtime-validated（qwen_3_5 + thinking_budget_enabled/tokens）；等待当前调用终态并卸载后再验证它。测量新增保留HTTP Warning，避免再次把声明支持当真实支持。相关20项测试及新增3项额度拒绝测试通过，语义问题仍未收口。不能据此宣布模型可靠，也不暂停任务。

01:10补充：下方42610等已结束。格式修复补全3条后，既有频次检查仍发现遗漏；局部语义修复补频次却错误合取，再修范围又删频次。不能称已修好。独立续审确认作用域问题，新增保守源位置检查仅用于隔离诊断。MLX Serve已优雅exit0并释放。oMLX默认加载98.2GB连13token都被预检拒绝；隔离配置仅启用PLE SSD offload后68.30GB、OK最小调用成功，不改系统上限、不冒充默认性能。当前oMLX 31264服务、91552严格Schema小样在途。详细证据和安全续行入口以CHECKPOINT顶部01:10段为准，不按本文旧session启动。

用户已恢复并要求主动分析异常，以下19:12暂停为历史。当前不机械扩大失败矩阵。主记录为同目录CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md顶部续行段。

已验证：MLX Serve平台会以length报告尚未用尽预算的提前终止；新增本地用量判别，禁止因此盲目扩预算/重试，不推定所有提前终止都是思维循环。关闭PLD后同请求仍一成功一JSON失败，不能认定修好。json_object+完整原Schema提示可解析但存在缺字段/漏规则及语义范围错误，全部诊断，不排名。未改采样默认。服务为78116，--no-pld，其他本地平台未启动。

新增json_missing_fields_repair模块仅供诊断：只允许补顶层缺字段，禁止覆盖已有字段、嵌套错误、异常结束合并。重复补答01/02分别60.091/43.663秒，2615/2016输出；规则内容不变，但一次指出正确的频次适用范围问题、一次漏报，因此格式成功绝非临床成功。独立C03 zcode/GLM-5.3:max确认保真和正确警示，未批准正式集成。其关键词校验建议未采纳，不能将子句存在等同语义绑定正确。

提示框架发现歧义并做通用最小澄清：括号内子类频次不得附着上位条件，同时保留上位范围与示例。新小样263.488秒/11063输出，仍缺整条EX06且子类频次未结构化；受限补答在模型调用前拒绝。现42610按既有_batch_schema_repair_prompt对实际结构错误做一次受控修复，输出diagnostic-scope-schema-repair-d001-medium-01，未改正式数据库/路线。变更后的提示哈希单独留存，不能与原v3混排。85项聚焦回归+172项规则解析/校验回归通过，不是临床验收。

下一动作：等待上述真实修复终态，逐项核原文、规则数量、频次归属及两节点资料要求；若仍不合理，改变分解或表示方法而非重复大请求。新提示与后续诊断代码还需同会话独立复核；复核session sess_64d4a3c5-fdc3-4f3a-8fd6-73a422c7a41e。标准横评须冻结统一新版本后再跑，旧失败/缓存/人为中断证据不删除，不宣称全部模型可靠。

## 最新暂停：2026-09-09 19:12 CST

用户明确要求无损暂停，覆盖本文下方所有继续运行描述。本轮测试已停止，不自动续跑。MLX Serve medium/low 七页分别7/7形成记录（仅结构有效，未临床QC）；medium两方案、low D001均完整流程失败。low D001第6/12批两轮stop但JSON语法错误（3083/5414列）。low SAR来源任务58ef18cfc44a4c10a384ca8b282a5ba3，在request-2在途时收到暂停：执行PID81091收到INT后exit130，测量finally保留部分流及无最终usage回执，不当作模型自然失败。request-0 stop；request-1 length但实际18010输出，服务日志明确repetition_loop平台提前截断，绝非耗尽131072额度。request-2人为中断，不能按完整样本排名。

服务session18531退出139，发生在客户端断开附近，TERM时PID20430已不存在；不能声称此次为优雅关闭，退出139原因待查。主线程未强杀进程。pgrep无本轮测试/推理进程，绕过代理核对8001/8002/11234均拒绝连接。cell141已关闭，所有本轮等待均结束。平台日志保存到v3/mlx-serve/pause-server-11234.log；原始输入、响应、流、缓存和未提交工作全部保留，git diff --check通过。未修改原临床数据库；未把goal标完成。

恢复时先只读检查low-protocol-sar作业和租约、request-2部分流、退出139日志及代码版本，再决定合法的新受控尝试，禁止直接覆盖输出目录或把运行中持久状态当可续跑证明。下一批尚包括MLX Serve xhigh全套、oMLX v3全套及MTPLX余项；此前v2不混入v3排名。先核对平台length真实含义和结构化输出失效日志（有“disabling further mask enforcement”），再评估修订；目前还不能完成三平台排名。本文其余章节保留历史证据，禁止据旧session号重启。

更新时间：2026-09-09，MTPLX 完整尝试结束并切换 MLX Serve 后。本文是交接快照，不是暂停指令；横评仍在运行。下方第7节11:39记录为历史启动快照，以本段后续状态为准。

最新状态：MTPLX medium D001 已自然终止，`execute/execute_record.json` 为 `state=failed`、`job_state=failed_final`，未生成草稿，`claims_complete=false`。request-14 同样耗尽131072输出额度，耗时4421.7491秒；两轮并非被人为提前停止。服务已关闭（原服务38570、执行30198均已结束，cell53已关闭）。避免无新证据重复该失败，现先切换 MLX Serve，同版流程、同一D001输入、medium；模型列表确认 `ddalcu_Qwen3.8-Flash-Next-MLX-Serve-mixed-4-8bit` ready，11234端口。新服务session93065、执行session18259，输出 `artifacts/qwen-three-platform-20260909-v3/mlx-serve/medium-protocol-d001`，来源任务 `fd4e87a3ed39439fa99da15d2bec0487`。MTPLX其余组合仍未完成，不得将切换解释为全部MTPLX测试完成。

后续重要反例：v3 MTPLX medium D001 request-13 即使显式AR仍发生可见输出停滞，最终4538.9058秒、finish_reason=length、131072输出；约4590进度token后无新可见文字。前13请求正常完成不能掩盖此失败。产品随后自动发request-14（同额度、追加原生修订指令），仍在途。因此AR配置修复成立，但“已解决MTPLX全部无效生成”不成立；需保留该反例，未完成全组合排名。

## 1. 当前授权与边界

用户要求查清本地模型长耗时原因、修复 harness、使用修订版继续真实资料横评，并同步提供本交接文档。

- 唯一工作目录：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。不要误在主 checkout 修改或运行。
- 当前任务：`.trellis/tasks/09-05-phase55-dual-vlm-page-review`。
- 持久动态记录：同目录 `CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md`，文头修订版恢复段优先；下方历史暂停和其他产品线程描述不能当作当前横评状态。
- 不修改原始研究方案、受试者资料、原临床数据库或其他线程未提交工作。现有工作区大量未提交变更，不 reset、不批量清理。
- 产品模型调用必须由本系统独立 harness 直接访问推理端点；不使用 Hermes/OMP 替代产品执行。工程独立审阅使用全局批准机制，两者职责不同。
- 本地平台及模型严格串行；完成后卸载并关闭，再切换平台。不同档位用独立会话与缓存，不能污染输入。
- 不因输出文件存在或结构校验通过宣布临床验收；`claims_complete=false`。
- 仅在确需用户决策、不可自行解决的阻塞、用户要求暂停或目标真正完成时结束。写本文不构成暂停。

## 2. 用户要比较什么

三个固定平台/权重，各测 xhigh、medium、low，九个组合：

| 平台 | 权重 |
|---|---|
| oMLX | `Jundot__Qwen3.8-Flash-Next-oQ4e-mtp` |
| MLX Serve | `ddalcu_Qwen3.8-Flash-Next-MLX-Serve-mixed-4-8bit` |
| MTPLX | `Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed` |

每次请求输入上限65536、输出上限131072，思考与正文合计；不自行调低额度。采样保持厂商默认，不新增 temperature、top_p 等覆盖。修订后 MTPLX 严格 JSON 使用 AR 兼容措施，必须如实标注，不能仍说所有解码设置完全默认。

维度一：真实 DOCX 方案的筛选/基线要求解构，包括跨章节限制；SAR III期、D001 II期。

维度二：带冻结权威 ClausePack 的真实页面读取，SAR零基索引0/9/17/18，D001零基索引0/42/44。不得将某候选自己解出的不同条款包带入其他候选，造成输入不一致。

质量：来源忠实、数值/单位、遗漏、手写归属、冲突/不确定保留、条款关联及结构接受；速度：总耗时、TTFT、首正文、输入/输出/思考token、prefill、decode、缓存、内存。缺失指标为未知，不填0。单次小样不能证明统计稳定性或全受试者验收。

## 3. 原始问题与证据等级

### 3.1 MTPLX：确定的调用配置缺陷

`DeepSeekProtocolAgentTransport` 是沿用的历史类名，并不意味着实际调用 DeepSeek。`backend=mtplx` 时实际访问 MTPLX。

修复前 `provider_defaults=True` 同时移除了 temperature 和 `generation_mode=ar`。但 AR 是严格 JSON 的兼容措施，不是采样参数。横评入口固定启用 provider_defaults，导致严格结构化请求绕过已有兼容措施。冻结失败请求确实没有 generation_mode。

此前四份方案调用可见思考恰4000字符，后续无新可见内容但平台进度增长至131072，最后断流。MTPLX已安装源码 `constrained.py` 存在4000字符默认思考前导约束，不能把后面所有计数都称作有效思考token。无最终usage的失败请求不补造用量。

已证明配置缺陷及修复后的两次成功；尚不能单凭两次不同随机采样结果断言平台内部唯一根因。旧调用不当作正常速度排名。

### 3.2 oMLX：确定的重复生成，平台内部根因未闭合

旧 `omlx/xhigh-sar-18/response-0.json`：2793.20秒、131072输出、length；思考268168字符，长句段最高重复2050次。结束时正文与思考逐字相同，正文几乎最后才出现，不能当作有效JSON或双份产出。

另一 SAR17 修复轮：stop但正文为空，思考231517字符。首轮仅未知条款ID，整页纠正又消耗大量输出。空正文与思考重复不是同一个现象；解析器/未闭合思考/权重因素尚未完成单因素诊断。

旧oMLX命中36864个SSD缓存token，热缓存清理不足以建立干净冷启动。不得全局清空其他模型SSD；后续用独立目录并保留/恢复原设置。

### 3.3 提示与修复成本

每页输入约3.7万至3.9万token，SAR条款包81条占大部分。`build_format_repair_messages` 保留整图整条款，并把整份旧回答回填，要求完整重读。小格式错误可能变成第二次完整生成。

目前未实施局部格式修复；不能声称该问题已解决。临床事实不能用猜测ID、删除未知条款或机械项目专属映射修好。

## 4. 本次实际修改

| 文件 | 修改及边界 |
|---|---|
| `app/agents/protocol_semantic_transport.py` | 将MTPLX AR设置移至默认采样开关之外；其他平台、提示、额度不变。默认产品路径原先已有AR，因此该路径行为不变。 |
| `tests/v2/agents/test_protocol_benchmark_defaults.py` | 更新断言及说明，验证默认采样仍保留AR，其他本地平台不受影响。 |
| `scripts/run_frozen_protocol_comparison.py` | CLI帮助和说明同步纠正；不改方案执行逻辑。 |
| `app/llm/generation_repetition.py` | 新增纯函数检查思考尾部的持续精确重复。 |
| `scripts/qwen_platform_measurement.py` | 隔离流式测量接入重复保护；触发显式失败并保留原始流。正式产品默认completion尚未接该保护。 |
| `tests/v2/llm/test_generation_repetition.py` | 长句、轮换句循环及正常内容反例。 |
| `scripts/qwen_request_diagnostic.py` | 冻结产品请求的单因素AR/mtp诊断入口，记录源请求hash，不是替代产品的新提示。 |

重复保护：至少8192字符；尾窗8192；句段至少32字符、至少12次重复；重复字符占尾窗60%以上；每2048新增思考字符检查。不检查正文，不判断临床内容。阈值属于初步防失控措施，不代表一般质量分类器。

真实旧oMLX8响应回放：只命中严重SAR18，在40960字符时检出；其余7份未命中。第一版只查单句长重复未命中真实循环，已修为多句轮换重复。不能据此声称零误报或能发现隐藏无输出停滞。

缓存：产品 `semantic_cache_identity` 哈希实际请求参数，因此修复后的横评请求身份自动改变；默认产品路径身份不变。不要手工把旧缓存改成新身份。

## 5. 复测结果

使用完全相同冻结请求内容，新增AR参数，独立SSD目录；无temperature覆盖，无gold注入。

| 请求 | 原失败 | 修复后耗时 | 输入 | 输出（含思考） | 思考 | 缓存 |
|---|---|---:|---:|---:|---:|---:|
| D001 medium request-2 | 1934.1秒后断流 | 90.8658秒 | 5332 | 2878 | 1197 | 0 |
| SAR low request-12 | 2891.6秒后断流 | 447.1942秒 | 9429 | 11995 | 1394 | 0 |

两次 finish_reason=stop，使用请求原始 `response_format.json_schema.schema` 做 jsonschema.validate 均通过。不是完整方案发布门禁或临床QC。

证据：
- `artifacts/qwen-three-platform-20260908/diagnostic-ar-d001-medium-20260909/`
- `artifacts/qwen-three-platform-20260908/diagnostic-ar-sar-low-20260909/`
- 原失败在同根 `mtplx/medium-protocol-d001/measurements/`、`mtplx/low-protocol-sar/measurements/`。

聚焦回归：32 passed，第三方SWIG弃用警告；git diff --check通过。非全库回归。

```sh
.venv/bin/python -m pytest tests/v2/agents/test_protocol_benchmark_defaults.py tests/v2/scripts/test_protocol_benchmark_defaults.py tests/v2/scripts/test_qwen_platform_measurement.py tests/v2/llm/test_generation_repetition.py -q
```

## 6. 独立审阅

批准runner实际执行C03 `qwen-harness-diagnostic-review-20260909`，zcode / GLM-5.3 / max，无fallback，终态成功。报告：`runs/conference/qwen-harness-diagnostic-review-20260909/evidence_single_object.md`。

主线程采纳：采样/兼容设置分离、缓存身份核对、CLI和测试docstring修正。审阅发生时docstring未更新，现已改，不应重复修。

仍待处理：
1. 格式重读可能丢失或改写原本合法事实。不能只加提示，应有结构保真验证；审阅建议仅按normalization_key匹配还需防同键多时点/多对象冲突，不能照抄为充分条件。
2. 测量器tokenizer/idle预检位于请求try/finally之外，可能留下request无完整receipt；新诊断入口有失败status，但原测量器该缺口尚未整体修复。
3. 仅有进度计数、无新内容的停滞尚无明确保护；与正常prefill、长思考区分后再接，不能简单短超时。
4. 相同传输失败重试可能再付完整生成成本；不能未经版本化直接改变产品恢复语义。

## 7. 正在进行的修订版横评

后续进展：MLX Serve medium 已完成两方案和七页尝试。D001 第4/12批两次stop但JSON无法解析（第1554/1551列），完整流程failed_final；SAR第2/9批首次stop但JSON无法解析，修订轮length，完整流程failed_final。七页均形成record，但尚未原件临床QC，不能写准确率100%。medium服务93065已优雅退出；重新启动服务18531，清空内存前缀缓存，准备下一档。执行18259、65957和页循环cell134均已结束。以上状态覆盖下方历史启动详情。证据均在v3/mlx-serve目录，保留原始流，不人工改写失败回答。

根目录：`artifacts/qwen-three-platform-20260909-v3/`，契约 `benchmark-contract.json`。旧v2与v3不混合排名。

当前组合：MTPLX medium，D001完整正式方案解构。不是单请求重放；使用 `run_frozen_protocol_comparison.prepare/execute` 和产品执行器。

- 独立数据目录：`mtplx/medium-protocol-d001/data_v2`（以prepare_record记录为准）。
- 冻结来源任务：`81a1ebf1dbf24207bbda30cfec6f73b7`。
- 模型公开身份：`mtplx-flash-next-optimized-speed`，8002/v1。
- 独立SSD缓存：`/Users/smkzw/tmp/qwen-benchmark-v3-mtplx-medium-cache`。
- 服务exec session：38570；方案执行exec session：30198。
- functions长等待cell：53，内部最多120分钟等待session30198完成；不要重复对同session发并发wait或重跑。
- 截至11:39，前5次请求均stop，耗时80.12/87.85/161.01/168.18/117.89秒；尚未完整方案终态，不说明已通过。后续同会话前缀缓存属于实际运行成本，应记录，不与其他档位缓存混淆。
- 没有启动oMLX或MLX Serve。本地保持单平台。

运行入口：
```sh
env MTPLX_PROTOCOL_BATCH_MAX_TOKENS=131072 OMLX_PROTOCOL_BATCH_MAX_TOKENS=131072 MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS=131072 .venv/bin/python -m scripts.qwen_protocol_measurement --run-dir artifacts/qwen-three-platform-20260909-v3/mtplx/medium-protocol-d001 --provider mtplx --url http://127.0.0.1:8002/v1 --model mtplx-flash-next-optimized-speed --effort medium --tokenizer /Users/smkzw/.mtplx/models/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed
```

以上命令是已运行命令的记录，不是要求再次执行；输出目录存在时不要覆盖。

## 8. 接续顺序

1. 先接收cell53/30198终态；核对真实execute_record、模型回执、发布校验问题，不以stdout安静判失败。
2. 相同medium完成SAR方案及7页；档位结束关闭平台，换独立缓存测其他档位。不同平台同理串行。
3. 新组合前核对端点实际模型、档位支持、空闲状态、缓存隔离和输入额度。MLX Serve/oMLX不能凭列表别名假定档位生效。
4. 每个结果分开报告模型失败、合同失败、医学遗漏/错误、耗时和缓存。失败不得通过补写人工答案转为成功。
5. 最终同源质量回看及独立审阅，才作平台/档位推荐。保留重构中的产品线程边界，不自行修改正式默认模型。

尚未完成全九组合；本文不宣布横评完成、工程目标完成或暂停。
