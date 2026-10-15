离线核验完成，两项关键事实落定（规模相当、形式 schema 递归）。汇总报告。

# Conference Output: qwen-bounded-completion-review-20260910 - evidence_single_object

## Output

续审第八遍（`compact_wire=False` 形式合同实验的入路审查）。边界遵守：只读 + 仓库 `.venv` 离线核验（无安装、无模型/服务、无写入）；`run_frozen_protocol_comparison.py` 不在本遍授权清单，编排胶水层未核（见限度）。

### 一致性核实（正面结论，均有代码/测试依据）

`compact_wire` 全链路穿线一致：构造守卫仅限本地后端且强制布尔（transport 192–197，测试 slice3:140–144）；默认 `None` 时按后端取默认、远端构造不变（测试 54–77、120–137 断言除 response_format 外 kwargs 全等、缓存身份分离）；提示词三分支（候选批次 1255–1284、续批 1287–1332、结构修复 1335–1377）与修复流（2886–2996）均按 `compact` 选形式/线格式文本；解析（3006–3026）形式走 `_normalize_model_json`+pydantic、线格式走严格 wire 解析器；**分段重试的身份守卫**（3855–3860）要求重试 transport 合同模式不变；缓存键经 `semantic_cache_identity`（哈希含 response_format）+ 提示词差异双重分离，跨模式不可能撞键。oMLX 的 nonblank 投影在形式模式下同样生效（transport 380–381 无条件应用于 omlx 后端）。

### 优先级行动项

**P1｜真实诊断前需要编译预检守卫（最高优先）。** 离线实测：形式候选 schema 含**递归 `$defs`**（`LogicalExpression`、`SemanticRule` 自引用）+ `oneOf/discriminator`（30 处 `$ref`）——xgrammar 对递归引用/判别联合的编译支持有限，在 oMLX 上编译失败概率高；失败即静默降级 prompt 注入（回执 Warning 可见，但跑一次约 10 分钟/批，且测的就不再是“文法约束下的形式表示”）。仓库 `.venv` 无 xgrammar（已验证），预检须用 oMLX 自带环境按 pass-4/5 方法做 CPU 编译探针（所有权在 owner，本遍未执行）。编译失败应视为实验阻断项，或显式改标“prompt-only formal”后再跑。

**P2｜形式模式的 scope 失效应被记录而非事后发现。** `protocol_output_response_format` 形式分支**忽略全部 scope 参数**（deconstructor.py:1002–1017：official_codes 枚举、来源 span 枚举、四类基数上限全不入 schema），且 `_configure_transport_output_scope` 对形式模式直接返回（3599）。后果：形式批次失去解码期收窄，只剩解析后校验（3029–3100 的顺序/candidate_id/来源闭包，fail-late）。安全性成立（闭包仍强制），但实验因此**同时改变两个变量**（表示形式 + 执行紧度）——不阻断，但必须在 `wire-contract.json` 记录（如 `"decode_time_scope": false`）并加一个钉住测试（断言形式 schema 对 scope 参数不变），使对比解释有界。

**P3｜CLI 记录的区分度不足。** `wire-contract.json` 现有 `compact_wire_override/diagnostic_only/clinical_acceptance`，缺：所用 schema 的 name+sha256、oMLX 投影是否应用。回执层已捕获 Warning ✓，但工件层无法回答“这次跑的是哪个形式 schema 版本”。最小修复：补两个字段。

**P4｜预算担忧撤回（自我更正）。** 实测形式 vs 线格式 schema 序列化后 10,964 vs 11,341 字节（≈1:1）——我预设的“形式 schema 显著膨胀 prompt”不成立；8192 本地输出上限与 length 重试对两者同等。保留一条观察项：形式输出每规则更重（predicate_id、嵌套联合），以回执中 finish=length 发生率监控即可，无需预置守卫。

**P5｜缺三个小测试**：(a) 形式 schema 对 scope 参数不变的钉住测试（兼作 P2 文档）；(b) 形式+omlx 仍过 `decoding_response_format` 投影的断言；(c) 形式分支提示词选择（`_batch_schema_repair_prompt`/`_repair_prompt` 的 else 路径）——slice3 只覆盖了 kwargs/缓存身份。

### 限度

编排层（`execute()` 的批次循环、缓存读写、工件命名）在授权外未核；无任何在线/临床验证；形式 schema 的 xgrammar 编译行为未实测（P1 即为此而设）；按指令不以 HTTP stop 或无 Warning 等同于“可用/受约束”——输出可用性仍以解析+校验链为准，先前 source-bound 失败保持未接受状态。本遍不构成对实验或形式表示的接受，仅界定其入路风险与最小修复。
