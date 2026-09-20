Review complete. All evidence gathered — probe confirmed the central defect, tests verified green, retry state matrix and transport boundaries mapped. Final report:

---

# Conference Output: r3-normalizer-type-stream-review-20260909 - evidence_single_object

## Output

**Verdict: 阻断通过（1 项 HIGH 工程缺陷需在合入前修复；GLM 流式/重试/隔离脚本整体质量良好）。** 核心结论：v21 标识编号（leading-zero 保留）功能本身正确且有测试覆盖，但它引入了一条可被模型标签绕过数值单位门禁的通道，且 `value_kind` 在领域边界被丢弃，下游永久无法区分“编号”与“文本测量值”。

### F1 (HIGH) 测量值误标为 identifier 可静默绕过数值单位门禁 — 已本地实证

- **证据（实测，`/tmp/probe_identifier_bypass.py`，无模型调用）**：对冻结输入页文本 `收缩压 120 mmHg。`：
  - `value_kind=value, unit=None` → 正确拒绝（“数值候选必须声明单位”，既有测试 `test_decoder_does_not_let_numeric_string_without_unit_bypass_numeric_gate`）；
  - **`value_kind=identifier, raw=canonical="120", unit=None` → 通过解析（canonical 变为字符串 `'120'`、单位被静默丢弃），且确定性门禁 `value_unit_date_source: accepted`**；小数测量 `血糖 6.1 mmol/L` 误标 identifier 同样通过（`'6.1'`、无单位）；
  - 合法编号 `0047`/`84721` 逐字保留（功能正常）。
- **根因链**：
  1. `app/agents/evidence_normalizer.py:181-193` 草稿校验只检查 identifier 自身一致性（字符串、canonical==raw、unit=None、原句逐字出现），不检查“该值在原句中是否为带单位的测量值”；且生成 schema 已把 `value_kind` 设为必填（`evidence_normalizer_json_schema` 的 `require_declared_properties`，实测 `required` 含 `value_kind`）——每条测量值都只距绕过一个模型标签；
  2. `app/agents/evidence_normalizer.py:1076` 对 identifier 跳过数值规范化（这是保留前导零的正确设计，同时也不再把 `"120"` 转成 int）；
  3. 领域合同 `app/domain/contracts/facts.py:279-282` 与门禁 `app/domain/gates/fact_candidate_gates.py:173-185` 的单位强制**只作用于 int/float**；字符串 + unit=None 一律放行。
- **影响**：带单位的测量被降级为无单位字符串事实，发布后规则层无法做数值比较（漏报而非误判方向），Patient Profile 展示缺单位；违反“数值事实必须声明单位”的确定性不变量。
- **最小修复（确定性、无模型调用）**，在 `validate_identifier` 追加两条拒绝并走既有同会话修复回路：
  1. `_PLAIN_NUMERIC_SCALAR` 全匹配且含 `.`/`e` → 拒绝（带小数/指数的编号在临床资料中不成立；实测不影响 `0047`/`84721`/`A-0003`）；
  2. `re.search(re.escape(raw_value) + r"\s*[A-Za-zµμ%％²³]", assertion_text)` 命中 → 拒绝（编号后紧跟计量单位即测量形态）。
  - **残留风险（如实声明）**：原句本就无单位的整数误标（“心率 85”）在字符串形态上与合法纯数字编号不可区分，确定性层无法闭合；影响受限于规则层按类型不匹配（漏报），修复提示词可进一步压低概率。
- **回归测试缺口**：`tests/v2/agents/test_evidence_normalizer_adapter.py:1317-1350` 只测了 identifier 的自身一致性与 value 路径的单位门禁，**缺“测量值误标 identifier”负例**。

### F2 (MEDIUM) `value_kind` 在水合边界被丢弃，领域层永久失去“编号”语义

- **证据**：`_hydrate_draft_output`（`app/agents/evidence_normalizer.py:1338-1360`）构造 `ClinicalFactCandidateV2` 时不传 `value_kind`；`app/domain/contracts/facts.py:233-289` 无该字段；发布合同/稳定身份/门禁/投影均无（`rg value_kind` 全库仅 `evidence_normalizer.py` 命中）。
- **影响**：即便草稿层校验通过，候选落库、重放、Profile 展示都无法区分编号与普通文本值；后续任何基于值形态的确定性检查（如 `%` 启发式 `evidence_normalizer.py:1090-1099` 目前因类型不匹配恰好不碰 identifier）都建立在脆弱的类型巧合上；直接构造候选（非草稿路径）完全不受 identifier 约束。
- **最小修复**：`ClinicalFactCandidateV2` 增加可选字段 `value_kind: Literal["value","identifier"] | None = None`（默认 None 保证全部历史载荷兼容，已验证 `ContractModel` 为 `extra="forbid"` 但新增带默认字段不破坏旧数据）；`_hydrate_draft_output` 透传；`validate_fact_value_unit` 复述 identifier⇒unit 必须为 None 且 canonical 为与 raw 相等的字符串。稳定身份无需改动（值/单位已含编号语义）。

### F3 (LOW) 旧全量输出路径与新 `value_kind` 字段互斥

- **证据**：`parse_evidence_normalizer_output` 的 `run_id` 存在分支（`evidence_normalizer.py:1457-1465`）直接 `EvidenceNormalizerOutput.model_validate`，而 `ContractModel` 为 `extra="forbid"`（`app/domain/contracts/common.py:12`）——携带 `value_kind` 的全量载荷会被拒绝。当前无真实调用方（该路径仅结构化测试/旧探针，注释自述），属埋雷非缺陷。建议在该分支剥离 `value_kind` 或在文档注明。

### F4 (LOW) 终态投影崩溃窗口会阻断人工重试（直到重启愈合）

- **证据**：`app/workflow/runner.py:700-717` 的取消/失败投影回调**吞掉异常仅记日志**（设计上依赖启动扫描收敛）；若 jobstore 终态已提交而 run 投影失败/进程崩溃，则 job=`failed_final`/`cancelled` 而 run 仍 `RUNNING`。此时 `FactNormalizationJobService.retry`（`fact_normalization_job_service.py:628-642`）调用 `reopen_for_retry`（`fact_repositories.py:347-364`）因 RUNNING ∉ {FAILED, CANCELLED} 抛 `Phase5RepositoryError`，**整个重试事务回滚，用户被阻断**，只能等 `recover_fact_normalization_runs` 启动收敛。
- **最小修复**：`service.retry` 中当 `run.status == RUNNING` 时跳过 reopen（目标态本就是 RUNNING），而非改库函数语义。

### F5 (LOW) 每步新建的 OpenAI/httpx 客户端从不关闭

- **证据**：executor 每步经 `evidence_normalizer_transport_from_model_config` 新建传输（`fact_normalization_executor.py:1150-1166`），GLM 后端在构造器里新建 `httpx.Client(trust_env=False)`（`deepseek_evidence_normalizer_transport.py:276-289`），执行完无任何 close。单用户本地产品为慢积累；建议传输加 `close()` 并在 executor 步级 finally 调用。注意：**流本身的释放是正确的**——`_request_stream` 的 finally 关闭 stream（`transport:394-400`），测试 `test_glm_stream_closes_and_checks_actual_model` 断言 `stream.closed`。

### F6 (INFO) 部分流拒绝与请求身份：GLM 路径实现良好，两处非对称

- **良好（有测试）**：缺 `finish_reason`、流中断、`finish≠stop`（含 length 重试后仍不完整）均拒绝部分结果且小票保留 `partial_result` 诊断；块间 600s 不活动/1200s 总时长上限的粒度局限在 docstring 如实声明并有 clock 测试；流中模型身份变化与响应模型≠请求模型均硬拒（`transport:105-167, 365-366`）；length 仅一次翻倍重试、部分内容绝不拼接采信。
- **非对称 1**：非流式 `_request`（deepseek/mtplx/omlx）不校验响应模型身份——历史行为，本次未改，可接受但建议后续补齐。
- **非对称 2**：runner 初始传输失败时用合成 `transport-failed-N` 会话号（`evidence_normalizer.py:1967-1981`），丢弃了传输特意附上的 `exc.session_id` 审计线索；一行改为优先取 `getattr(exc, "session_id", "")`。

### F7 (INFO, 运维注意) v21 提示词哈希变更使升级前在途任务响亮失败

executor 执行/重放时用**当前代码**的模板哈希复核冻结 PromptVersion（`fact_normalization_executor.py:542-549`；哈希覆盖 v21 布局+系统合同+schema，`evidence_normalizer.py:605-617`）。升级到 v21 后，旧哈希的在途任务重试/恢复将以不可重试的 `PARTIAL_OUTPUT` 失败闭合（非静默混跑）。与幂等键设计一致（新提示词版本→新键→新任务），但**部署说明应写明：升级后需注册新 PromptVersion 并为中断运行重建任务**。

### F8 (LOW) 隔离脚本对 normalization 路由的核验弱于页读路由

`scripts/run_isolated_page_revision.py` 对页读有 `verify_frozen_readers`（逐字段比对+≥65536 tokens，`run_isolated_page_revision.py:22-31`），而 `normalize_selected_job`（41-62 行）POST `{}` 后不核验任务实际冻结的 model_config/提示词身份，仅依赖服务端白名单校验（不钉具体模型）。作为“正式对比”载体，建议提交后从 job payload 读回 `model_config_id`/`prompt_version_id` 并与预期路由身份比对。脚本其余边界（源只读连接、活动任务检查、快照哈希、`failed_retryable` 交给正式重试端点）正确。

### 测试与兼容性总评

- 三个焦点测试文件 **172 passed**（本 worktree 实跑，21.6s）。
- 前导零/编号保真、GLM 流式（关闭/身份/部分拒绝/有界截止/凭据闭合/base_url/努力档词表/小票脱敏）、重试状态矩阵（取消续跑保留 checkpoint、可重试失败保持 run RUNNING、终败重开可完成）覆盖充分。
- 历史兼容：draft `schema_version` 仍为 `phase5/normalizer-draft/v3`，旧原始输出（无 value_kind）可重放；创建期 scope-only 哈希与执行期一致（scope 哈希不含 run/call，`app/domain/contracts/evidence_normalizer.py:315`）。
- 建议补测：F1 负例（含小数误标、编号后跟单位）、GLM 流中模型身份变化（`transport:111-115` 无测试）、F4 崩溃窗口重试。

### 决策点（请 Codex 裁决）

1. F1 修复采用我提的两条草稿级确定性拒绝（推荐，最小且可测），还是同时把单位邻接检查下沉到门禁层（需先落 F2）？
2. F2 的 `value_kind` 领域透传是否纳入本次合入（涉及候选载荷持久化形状，默认 None 向后兼容）？
3. F7 的升级运维说明（重新注册 PromptVersion + 重建中断任务）是否写入发布清单？

### 有界问题（不阻塞，可同会话答复）

- 编号后紧跟 Latin 单位 token 的拒绝阈值（`[A-Za-zµμ%％²³]`）是否满足产品语料？若存在“编号+英文后缀”真实形态（如批次号 `0047A`），值本身会含后缀、不受影响，但我没有临床语料佐证，仅基于代码与常识推断。

**证据/推断/建议已分层标注；无临床接受主张；未读取临床工件、环境或凭据；未调用模型 API；未修改任何 app/tests 文件（探针脚本在 /tmp）。**
