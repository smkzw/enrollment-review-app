全部证据到位。以下为终稿。

# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

续审第四遍（nonblank pattern 修正评审 + 前审更正）。边界遵守：只读；无模型/服务调用、无写入、无凭据、未读 reasoning/streams；`protocol_deconstructor.py` 仅查 wire schema 与相邻 strip 校验行。

### 前审更正（已核实并接受）

- **B1 撤回**：实测旧回执（open-scope、explicit-thinking）**根本不含** `response_format_warning` 键——我第三遍用 `dict.get()` 提取，把“缺键”误读为“值为 null”，进而误判捕获失效。捕获代码部署于旧进程启动之后；新 supported-parser 回执含该键（值 null）。`test_qwen_platform_measurement.py:71-106` 已补 mock Warning 头→回执断言测试（我此前指出的缺口已闭合）。保留的残余不确定点仅一处：**服务端是否真的发出该头**仍无在体证据（捕获部署后尚未发生过真实降级），下次真实降级事件可仲裁。
- **parser 失效结论限缩**：`"qwen"` 未注册、每请求必抛 ValueError、降级日志逐条对齐——这些仅对 **reasoning-base 运行时**成立（日志+配置双证）。我第三遍把结论外推到“更早的 strict-scope 类运行”属于无配置证据的越界，撤回该外推。

### nonblank 正则修正评审（三处：categorical values、scalar source_term、scalar unit）

**JSON Schema 语义保持：成立，且为逐点等价。** 原 `{"minLength":1,"pattern":"\\S"}` 在 JSON Schema 搜索语义下 = “含至少一个非空白字符”；新 `^[‌\s\S]*\S[\s\S]*$` 锚定后同一语义（`minLength:1` 两边均冗余）。二者在 Draft 2020-12 下接受集相同。关键收益在另一侧：**新模式对“搜索 vs 全匹配”两种解释不变**——xgrammar 把 root regex 按全匹配编译，旧 `\S` 被编成“仅一个非空白字符”，这正是 supported-parser 运行中 `values:['播','重','严','型','状','疱']` 单字截断的根因（该请求字节级复用了 explicit-thinking 的请求，sha `ec3255e0…` 相同，仅换服务端；grammar 真实生效——无 Warning、无降级、schema 通过——却静默压碎内容）。修正使 JSON Schema 含义与解码文法含义重新对齐。测试 `test_wire_nonblank_pattern.py` 同时钉死两种解释在 7 个用例（含全角空格 U+3000、跨行）上一致，覆盖恰为改动的三个字段；wire schema 中其余 pattern（official_code、sha256）均已是锚定 ASCII 类，无同类隐患，无未锚定残留（冻结 request-4 中恰 3 处 `\S`，与改动半径一致）。`--whole-string-patterns` 诊断干预只做精确旧值替换并单独落盘 schema 干预记录、`ranking_eligible:false`，设计合格。

**残余 Unicode/escape/grammar 局限（如实保留，不扩大）**：CPU 测试编译期出现非 ASCII 负字符类 clamping 警告——`\S` 的 Unicode 边界（稀有汉字区、组合符、U+00A0 等非常规空白）在三个引擎（Python re / ECMA-262 / xgrammar）间不保证一致，五用例表不足以宣称全覆盖；过拒类别字符仍可能诱发变形输出（该通道未消，仅范围收窄）。`^…$` 的行尾语义差异被 `[\s\S]*` 吸收，两引擎一致。JSON 转义层面无新风险。

**下游空白校验仍在：确认。** 解析层保留 strip 非空判断（`protocol_deconstructor.py:1746-1844` 对 value/source_term/unit/source_clause 等逐项 strip 检查；Python `str.strip()` 覆盖 U+3000），故即使引擎间空白判定分歧漏过 schema，产品解析层仍拒绝——纵深防御未因本次修改削弱。

### 证据状态与最小后续

- 当前证据等级：CPU 文法等价性 + 仓库内双引擎回归测试 + 一次“错误编译且生效的 grammar 造成 schema 合格的内容损坏”反例。**pending 的 `diagnostic-whole-pattern-omlx` 真实解码运行是必要下一步**（同输入、仅换 pattern），其结果不构成验收输入；在它落地前不推断多字符词项在真实解码下完整存活，更不得据此推断临床可靠性——语义正确性仍由前几遍确立的 gate/逻辑审阅链条负责。
- 附带观测（不影响结论）：同一请求字节在两服务端的 prompt 计数相差悬殊（14261 vs 8302），跨服务端的输入侧指标不可直接比较，基准契约应按服务端分别记录。

### 不确定度登记

xgrammar clamped 字符集的精确边界未授权核查；`_wire_semantic_rule` 是否对 set values 做原文可核对校验未在本遍范围内验证；服务端 Warning 头的在体发出仍未演练；pending 运行结果未知。以上均不动摇三条已证结论：修正语义等价、单字截断根因成立、下游 strip 校验存续。
