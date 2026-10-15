# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

续审第五遍（证伪证据 + oMLX 投影修复 + 标签循环检测器）。边界遵守：只读；无模型/服务调用、无写入、无凭据、未读 reasoning/streams；whole-pattern 仅读 status/response 元数据与正文头尾样本。

### 更正（本人前审）

**撤回 pass-4 的“JSON 转义层面无新风险”。** 该论断出自对 pattern 文本层面的推理，未约束编译后文法行为；CPU 证伪实验表明锚定版 `^[\s\S]*\S[\s\S]*$` 编译出的解码文法**接受未转义换行与内嵌双引号的非法 JSON 字符串**，而去 pattern 的 `type:string/minLength` 文法反而两者皆拒（且仍接受中文与 mg/dL）。教训与 pass-3 的 grammar 语义分离同构：**正则文本等价 ≠ 编译文法等价，任何“解码安全”结论必须以编译后接受集实测为准**。pass-4 中“过拒可能诱发变形”的风险方向分析维持，但漏掉了过纳方向——这正是被证伪处。

### whole-pattern 运行的证据状态（按限定表述）

`state=interrupted_after_observed_failure`：正文 111,492 字符（status 记 107,012+ 时触发），尾部为 `</function_results>`×3961、`</null>`×662 洪泛；对核实过的 PID 发 SIGINT、exit 130，回执与流保留，`natural_finish_reason:null`、usage 空——**非自然结束**。按指令：不称其为私有推理重复（重复发生在正文通道），不主张转义缺陷与循环的因果排他性。值得记录的观察（无因果主张）：`function_results`/`null` 是 qwen_3_5 结构标签协议的通道记号，洪泛出现在正文通道提示结构标签与文法的交互面，但单样本、被中断，不足以定位。

### oMLX-only 响应格式投影评审（`omlx_schema_compat.py`）

**方向与实现均正确，判定为合格的最小修复。**
- `decoding_response_format`：deepcopy 后仅在 `json_schema.schema` 子树递归删除 `type=="string"` 且 pattern 恰为两个已知 nonblank 值（`\S` 与锚定版，覆盖旧冻结请求与 pass-4 改后产品两形态）的 `pattern`；原 dict 不被改动（测试断言）；`{"type":"json_object"}` 无 schema 时为无害 no-op。
- **无其他约束损失**：minLength/additionalProperties/enum/其余 pattern（如 official_code 的锚定 ASCII 类）全部保留（测试对 `^[A-Z]+$` 保留有显式断言）；去 pattern 后的 string 槽恰为 CPU 实验证实的 safe-strings 文法。
- **oMLX-only 门控核实**：transport 侧 `protocol_semantic_transport.py:380-381` 仅 `backend=="omlx"` 投影（mlx-serve/mtplx 不变）；诊断侧 `--omlx-pattern-compat` 强制 provider==omlx 并落盘 `decoding_intervention.json`（含 `authoritative_validation_retained:true`）；冻结请求文件不被改写。
- **权威校验仍在**：产品解析层 strip 非空检查（pass-4 已核实 `protocol_deconstructor.py:1746-1844`）继续拒绝空白串，纵深防御成立。

### 标签循环检测器评审（`repetitive_closing_tag_tail`）

窄域设计合理：≥8192 尾窗、丢弃首尾残行、行级 fullmatch 纯闭合标签、**≥128 个 + ≤4 种 + 覆盖尾窗 90% 字符**三重合取。假阳性分析：合法临床/JSON 内容即使重复也不会同时满足“≤4 种且占尾窗九成字符”；含开放标签或正文的行落入分母压低覆盖率；仅作用于诊断测量脚本（`qwen_platform_measurement.py:141-145`，每 2048 新字符增量检查，计数器已正确初始化），不进产品读取路径，误杀后果限于诊断重跑。`repetitive_reasoning_tail` 未改动。**缺两个有价值的负向测试**：5 种不同标签的洪泛（钉死 ≤4 闸）、标签行与正文行交错致覆盖 <90%（钉死 90% 闸）；建议补上。

### 残余限制与最小必要后续

1. **投影是枚举式防御**：将来 wire schema 若新增其他 nonblank 类 pattern，隐患会静默回归。最小守卫：一个静态清单测试，断言 wire schema 中全部 `pattern` 值 ∈ 已审计集合（锚定 ASCII 类 + 两个被投影的 nonblank 值）。
2. **safe-strings 真实运行（请求 95238…）pending**：投影的真实解码效果（多字符词项存活 + JSON 合法 + 无标签循环）未验证，不作为验收输入；落地前不推断产品适配已生效。
3. 标签循环成因未解（结构标签交互假说未检）：保留 single-sample 状态，不在本任务内归因。
4. 71 项回归通过为所有权声明，本次仅独立复核了其中投影/检测器/测试四文件的一致性。

### 不确定度登记

xgrammar 对其余保留 pattern 的编译行为未逐一实测（official_code 等锚定 ASCII 类风险低但未证）；`_is_grammar_accept_string` 方法名取自诊断文档，其实现未读（授权外）；safe-strings 结果未知；标签洪泛与其他grammar 元素的交互面无第二样本。以上不动摇本遍三条结论：投影修复合格且门控正确、检测器窄域、我的转义风险推断已被证伪并撤回。
