# 执行输出：phase5-closeout-r3-20260903 - worker_02

## 边界与上下文检查

- 仅在 runner 绑定的 worktree 内操作。初始读取 `context/phase5-closeout-r3-20260903_execution_context.md` 与 `plans/codex_execution_phase5-closeout-r3-20260903.md`，并读取了 `runs/execution/phase5-closeout-r3-20260903/worker_01.md`（同包 worker 交接，属授权上下文）。
- 执行 work item 2：按 Ponytail 最小改动修复通用提示或校验合同，运行定向自动测试与同页真实模型调用，无项目特异硬编码。
- 写入范围：`app/agents/evidence_normalizer.py` 与 `tests/v2/agents/test_evidence_normalizer_adapter.py`（两者在分支上本就是未跟踪的 Phase 5 新文件，我的修改未新增任何源码路径）；证据保留目录 `artifacts/phase5-acceptance/20260903/page4-assertion-repair-verification/`（沿用 worker_01 的未跟踪证据区惯例）；探针脚本在 `/tmp`。未触碰 `.trellis`、数据库、历史运行与生产路径。未安装任何包；未读 `.codex/AGENTS.md`/`.hermes/SOUL.md`；未做临床/监管验收。
- 敏感信息处理：GLM 密钥不在 worktree 环境中，我通过产品自身的 worktree 环境合同 `ENROLLMENT_ENV_FILE=<主仓库>/.env` 让 `app/config.py` 自行加载（主仓库 `.env` 在仓库根，属产品文档化的 worktree 配置机制）；我从未读取或输出密钥内容。

## 已执行工作

**1. 修复一：断言对象机械逐字还原（核心修复，针对 worker_01 定位的根因）**

新增 `_mechanical_verbatim_repair()` 并挂接在 `_normalize_evidence_json`（模块既有的"语义保持 JSON 实例规范化"层，`unknown` 极性剥离、raw→canonical 拷贝均在此层，先例一致）。模型把断言对象"顺口化"的两类通用转写漂移被确定性还原：

- 去后缀/前缀：模型给对象添加原句该处没有的 1-2 字类别后缀（如"司普奇拜单抗治疗"、"糠酸莫米松使用"）；
- 补虚词：模型漏抄原句中 1-2 字虚词（原句"眼部等疾病"→模型写"眼部疾病"），取原句中把模型对象作为子序列包含的**唯一**最短连续窗口。

安全边界（证据与推断分列）：修复结果必须是折叠空白后 `assertion_text` 的连续子串，不引入原句之外的字符；截取结果不唯一（等长候选并存，如"眼部"/"疾病"）或对象短于 3 字时返回 None 不动草稿，逐字门禁保持原合同 fail-closed；修复同步镜像顶层 `asserted_object` 与 `assertion_basis.asserted_object`（满足下游 `fact_candidate_gates.py:132` 一致性门禁），并同样通过 `fact_evidence_closure.py:275` 的逐字闭包与"无"前缀否定关系检查。无任何临床词表或项目字符串。

**2. 修复二：药名残缺定位上的暴露候选改为确定性删除**

r1/r2 真实调用发现第二个通用失败模式（与根因不同源但同样致命）：`_enforce_exposure_source_fields` 对"暴露候选引用 medication_name_incomplete 定位"直接 raise，而修复合同同时命令"不得删除已有候选"，两条指令自相矛盾——glm-5.3-flash(low) 在两次运行共 4 个修复轮中全部无法完成删除，耗尽预算。现按系统合同（该暴露本不得存在）确定性删除该 exposure_candidate，保留事实候选与药名残缺未解决项——与同函数已有的"非逐字可选字段清空"及 `_normalize_evidence_json` 的"unknown 极性剥离矛盾断言细节"先例语义一致；"药名未逐字"错误仍保持 raise（无确定性正确修复）。证据：观察（r1/r2 四轮修复失败）；推断（删除型修复对 low 档模型不可达，机械执行属系统职责）。

**3. 提示合同强化（通用）**

- `_SYSTEM_CONTRACT` 增加虚词分隔示例："家族无遗传病病史"应使用"遗传病病史"，不得把被虚词隔开的"家族遗传病病史"当作逐字对象；
- `_SCHEMA_REPAIR_CONTRACT` 增加：两处对象必须填同一字符串；因"无/未/有/等"虚词不连续时必须连同虚词原样截取；
- `_PROMPT_LAYOUT_VERSION` v4→v5（模板哈希 `8497bc27…`→`c2e9ad9b…`，运行时自动注册新 `evidence-normalizer/prompt/<hash>` 版本，`_is_usable_prompt` 运行时自洽，无需其他配置）。

**4. 同页真实模型调用（三轮迭代验证）**

复用 worker_01 字节级重建并 SHA 验证的冻结输入（`input_scope_sha256=9ccd09f1…6576ea` 与失败作业逐字节一致），按生产同路径（zhipu-coding-plan / glm-5.3-flash / low / max_tokens=16384 / 厂商默认采样 / 2-2 修复预算）：

- r1（机械还原+提示）：原逐字断言对象错误在 3 次尝试中均未再出现，但页仍因暴露残缺模式失败；
- r2（+修复合同例外条款）：同样失败——证明删除型修复对 low 档模型提示不可达（修复合同条款随后移除，改为修复一）；改为机械删除后条款已无触发场景；
- **r3：已解析（212 秒，尝试 ①日精度日期上下界（模型自修复）→②通过）**。26 事实/3 事件/0 暴露/1 未解决项；原失败点落为 `遗传病家族史 negated asserted_object=遗传病病史`（与上次成功运行 d71c1c28 的落库形态一致），"眼部等疾病""3个月内有大量饮酒""血液系统等疾病"等补全逐字保留，26 条 fact 两处对象全部一致。

## 工件与证据

目录 `artifacts/phase5-acceptance/20260903/page4-assertion-repair-verification/`（SHA-256 前 16 位）：

- `README.md`（d0a4424d…：修复说明、三轮对照表、残余风险）
- `page4-repair-probe-low-r1.json`（983f8eed…）/ `r2`（2d669b6f…）/ `r3`（b8692dfc…：含 26 条候选逐条摘要）
- `page4-v5-prompt.txt`（e6da06f5…：r3 实发完整提示 35,782 字符 = worker_01 的 35,690 + 新增虚词示例句）

代码变更：`app/agents/evidence_normalizer.py`（cbe935ba…）、`tests/v2/agents/test_evidence_normalizer_adapter.py`（3fb96c7b…）。

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/agents/ tests/v2/api/test_fact_normalization.py tests/v2/api/test_fact_normalization_registration.py` — **155 passed**（含 6 个新测试：后缀截取、虚词补全、歧义 fail-closed、第4页失败形态端到端回归、暴露确定性删除、合同内容断言）。
- `.venv/bin/python -m pytest tests/v2/domain/test_fact_batch_orchestration.py tests/v2/domain/test_fact_evidence_closure.py tests/v2/domain/test_fact_candidate_gates.py tests/v2/services tests/v2/agents -q` — **616 passed, 1 failed, 1 skipped**；唯一失败为 `tests/v2/services/test_evidence_processing_executor.py::test_native_pdf_creates_replayable_pages_without_external_ocr`（断言 `locator.source_layer == "native_text"`，与 normalizer 无导入关系，隔离复现确定性失败，判为本分支既有失败，未处理）。另 `tests/v2/test_architecture_boundaries.py` 等 153 passed。
- 探针：`ENROLLMENT_ENV_FILE=<主仓库>/.env .venv/bin/python /tmp/worker02_page4_repair_probe.py`（三轮，环境观察已记录）。
- 干跑验证：重建输入 `EvidenceNormalizerInput.model_validate` 通过，scope SHA 与冻结值一致；`validate_evidence_normalizer_model_config` 要求 `parameters.agent_node="evidence_normalizer"`。

## 阻碍或缺失的环境

- 无工具/环境阻塞。GLM 密钥通过产品 `ENROLLMENT_ENV_FILE` 机制加载（见边界声明），未做任何静默配置变更。
- 观察（非阻塞）：日精度"日期上下界必须相同"错误在本页 3/3 首试出现，均由模型在修复轮自修复；未做机械修复因 start/end 取舍存在歧义（非语义保持）。

## 重跑请求或下一步

- 给 worker_03：可直接开新全量不可变运行；本页已实证可通过。残余采样风险——若同页首试出现日精度错误且再叠加一个不可自修复错误，2 轮修复预算仍可能耗尽（未观测到第二个此类模式）。运行将自动注册新提示版本 `evidence-normalizer/prompt/c2e9ad9b…`。
- 给 Codex（验收提示）：(a) 暴露候选删除是"模型违约→系统确定性执行合同"，残缺药名信息仍由未解决项保留，临床核查时请确认该处理符合预期；(b) 既有失败 `test_native_pdf_creates_repairable_pages…`（native_text 定位断言）属本工作项外，需单独派工；(c) worker_01 报告的"作业 6b73614e 显示 completed 25/25 但运行状态 partial"对账遗留点未处理。
