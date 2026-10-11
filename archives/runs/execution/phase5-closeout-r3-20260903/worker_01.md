# Execution Output: phase5-closeout-r3-20260903 - worker_01

## Boundary And Context Check

- 仅在 runner 绑定的工作区内操作。初始读取 `context/phase5-closeout-r3-20260903_execution_context.md` 与 `plans/codex_execution_phase5-closeout-r3-20260903.md`，执行 work item 1（只读复原 31001 第4页标准化输入与失败响应链，定位断言对象校验失败的共同根因并保留证据）。
- 只读纪律：对 31001 运行数据库全部查询使用 SQLite `mode=ro` URI + `PRAGMA query_only=ON`；代码重建路径只做 SELECT。未修改任何产品源码、数据库、历史证据或 `.trellis` 文件。写入仅限授权的证据保留产物（见下）与 /tmp 工作文件；未创建 runner 报告文件，未启动会商，未读 `.codex/AGENTS.md`/`.hermes/SOUL.md`，未安装任何包。
- 任务范围内的“保留证据”按既有惯例落在 `artifacts/phase5-acceptance/20260903/` 下新建的一个目录（3 个文件），全部为只读重建的派生产物，原始数据零改动。

## Work Performed

**1. 定位失败作业与失败页（证据：jobs/job_events/job_steps 表）**

- 失败作业：`6c2c99735d0348cb9a1d59613b1b60bc`（fact_normalization，运行 `9f48d6b411324fc8a8796d3754d7ec4c`，2026-09-03 13:55 创建），`failed_final / PARTIAL_OUTPUT`，进度 18/25，失败时间 14:30:42。此前 18 个已记录调用全部 succeeded。
- 失败步骤：`normalize_018_f0be4759…` = **筛选病历（document_type 病历资料，source_party 研究中心，stage screening）第 4 页**，逻辑文档 `f0be475961c2f54f5a8fbe4e71876b3568f57732d812818a16685283208e4ac9`（源文档版本 `f55350a8cb57…`），call `call_92f574d74d1365fde35e3c36`。
- 失败原文（job_events seq39）：`以下断言对象必须逐字出现在各自断言原句中：家族遗传病病史`。

**2. 只读复原第4页标准化输入（字节级验证通过）**

- 用生产执行器同一代码路径 `build_evidence_normalizer_input`（`app/services/fact_normalization_source_adapter.py:424`）从冻结修订 `complete-529c2876…` 重建输入：**重建 `input_scope_sha256 = 9ccd09f1…6576ea`，与任务载荷冻结值逐字节一致**；冻结视觉观察范围 `65d6f361…` 复核通过（本调用 0 条观察附件）。
- 第4页有效文本 629 字符、40 个定位、58 条冻结资料要求；关键原句（locator `locator-ca2f284ee3202e3ef70b6407db5f1e2a`，raw_ocr 层）：**“家族史：父母体健，家族无遗传病病史。”**
- 冻结提示版本 `evidence-normalizer/prompt/7e238da1…` 的 template_sha256 `8497bc27…` 与当前工作区代码重算值**完全一致**——失败运行跑的就是当前代码（含现行修复合同）。完整提示重建为 35,690 字符。

**3. 复原失败响应链**

失败模型配置（冻结）：zhipu-coding-plan / glm-5.3-flash / low / max_tokens 16384 / 厂商默认采样。链条：step_started 14:26:41 → 提示构建（冻结模板+输入）→ 模型调用 → `parse_evidence_normalizer_output` → `_hydrate_draft_output` 逐字门禁（`app/agents/evidence_normalizer.py:714-727`：`assertion_basis.asserted_object` 须为 `assertion_text` 折叠空白后的子串）→ 模型草稿把“家族遗传病病史”放进断言对象，而原句中 家族|无|遗传病病史 被否定字“无”隔开，非连续子串 → ValueError → 记 `schema_invalid/PARTIAL_OUTPUT` → 修复提示（`_SCHEMA_REPAIR_CONTRACT`，`max_schema_repairs=2` 默认预算，`FactNormalizationExecutorConfig` 未覆盖）两轮后仍未通过 → runner 返回“需要核对” → StepFailure(fatal, PARTIAL_OUTPUT) → finalize DEPENDENCY_FAILED → 作业 18/25 failed_final（本页前 3 页及此前全部页均成功）。

**4. 共同根因（证据 + 推断分列）**

- 观察证据 A（运行间对照，同一冻结输入 SHA `9ccd09f1…`）：前次运行 `d71c1c28…`（作业 `6b73614e…`，13:29 完成 25/25）同页**首试成功**，其落库家族史事实为 `fact_type=家族遗传病病史（展示分类，允许自由词）、asserted_object=遗传病病史（逐字✓）、polarity=negated`；本次新运行把同一个流畅短语放进了必须逐字的 `assertion_basis.asserted_object`。
- 观察证据 B（同门禁的另一次失败）：作业 `01d26ed6…`（06:23，邮件资料页）同类错误对象为“司普奇拜单抗治疗；肝功能检查；糠酸莫米松使用”——模型给原词**添加了原句没有的后缀** 治疗/检查/使用。
- 观察证据 C（同页探针，17:08 `screening-page4-value-repair-low.json`）：attempt 2 同门禁报“眼部疾病；中枢神经系统…疾病；3个月内大量饮酒”——原文为“眼部**等**疾病”“3个月内**有**大量饮酒”，即**漏抄虚词**。
- 推断（标注为推断）：共同根因是 **glm-5.3-flash（low）在密集罗列否定句上系统性把断言对象“顺口化”——补类别后缀或漏虚词（无/有/等）——而确定性逐字门禁 fail-closed**；修复合同只给提示、不做机械抽取，low 档下模型在修复轮重复同类行为，导致同页通过与否取决于采样（同输入一过一败）。已排除：输入漂移（SHA 相同）、资料要求措辞泄露（58 条要求中无“家族/遗传”字样）、失败运行的提示模板漂移（哈希与当前代码一致）。

**5. 证据保留（本会话唯一写入，3 个文件）**

目录 `artifacts/phase5-acceptance/20260903/page4-assertion-root-cause/`：
- `page4-reconstructed-input.json`（SHA 验证过的重建输入，51,591 B）
- `page4-reconstructed-prompt.txt`（重建完整提示，47,195 B）
- `failure-chain-evidence.json`（作业/步骤/门禁/合同/运行对照/探针/根因/证据边界的结构化记录，7,757 B）

SHA-256：`8bcc7ce5…83d3` / `3417cba7…c3d6` / `83bd4452…7eae`。worker_02 可直接用该目录在同页做真实模型调用验证。

## Artifacts And Evidence

- 失败作业/事件/步骤：DB `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`（只读查询：jobs、job_events、job_steps、fact_normalization_runs/calls、prompt_versions、model_configs）。
- 代码锚点：`app/agents/evidence_normalizer.py:714-727`（逐字门禁）、`:275-285`（`_SCHEMA_REPAIR_CONTRACT` 断言对象与规范值修复规则）、`:287-387`（`_SYSTEM_CONTRACT`，初始提示已含逐字要求与示例）、`:1103-1287`（runner 传输/修复预算）；`app/services/fact_normalization_executor.py:824-993`（StepFailure 组装）；`app/api/v2/app.py:289-291`（预算默认 2/2）。
- 同页对照与探针：`fact_normalization_candidates`（run d71c1c28 call_74385bc9 的 26 条事实）；`artifacts/phase5-acceptance/20260903/glm-single-page-quality-gate/`（email-page4-source-gate-low.json、screening-page4-value-repair-low.json）。
- 检查点背景：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260903_PHASE5_CLINICAL_QC_AND_R3_CLEANUP.md`（三次历史失败与修复合同演进）。

## Commands And Observations

- `sqlite3 "file:<DB>?mode=ro"` 查询 jobs/job_events/job_steps/fact_normalization_*/prompt_versions/model_configs — 全部只读成功。
- `.venv/bin/python /tmp/rebuild_page4_full.py`（自建脚本，sqlalchemy 只读 creator + `PRAGMA query_only=ON`）— 输入重建 SHA 匹配、视觉范围复核通过、提示 35,690 字符。
- Python 哈希比对：`evidence_normalizer_prompt_template_sha256(DEFAULT_…) == 8497bc27…`（True）；子串校验 `"家族遗传病病史" in 原句`（False），`"遗传病病史"/"家族史"`（True）。
- `git status` 复核：本会话对 `app/`、`tests/` 零写入（255 项均为分支既有改动）；新增仅 `artifacts/phase5-acceptance/20260903/page4-assertion-root-cause/`（该 20260903 目录本身在分支上即为未跟踪证据区）。

## Blockers Or Missing Environment

- **不可恢复的证据缺口 1**：失败调用 3 次模型原始响应未持久化——传输层会话历史仅在内存（`deepseek_evidence_normalizer_transport.py:259-275`），失败时不写 `fact_normalization_calls` 行、无 raw_output_sha256、无 checkpoint；持久化证据仅剩最后一条异常明细。无法逐字展示 3 次草稿。
- **不可恢复的证据缺口 2**：前次成功运行的提示文本（`362c5eb0…`）不可复原——`app/agents/evidence_normalizer.py` 为未跟踪工作区文件、无 git 历史快照，仅存其 template_sha256。因此“13:54 提示合同变更是否影响通过率”无法直接对比，只能以后续同页真实调用实证。
- 无其他阻塞：未发现缺工具/缺环境；数据库、代码、证据均在位。

## Rerun Requests Or Next Step

- 无需重跑本工作项；结论已被字节级输入重建与运行间对照支撑。
- 给 worker_02 的精确交接：修复对象是“断言对象流畅化 vs 逐字门禁”这一通用矛盾，禁止项目特异硬编码；可评估方向（供 Codex 裁决，非本 worker 决定）——(a) 强化修复合同给出“从 assertion_text 中机械可验证”的抽取步骤；(b) 系统侧语义保持归一化（如同 `_normalize_evidence_json` 先例）在门禁前做白名单式规整（去后缀/提示重试），但不得替模型猜测临床对象；(c) 同页真实模型调用可直接复用 `page4-assertion-root-cause/` 的重建提示与冻结配置（zhipu-coding-plan/glm-5.3-flash/low/16384/厂商默认采样）。
- 给 worker_03 的提示：新全量运行前，本失败页无需人工干预即可由合同修复后重跑；作业 `6b73614e…` 在 DB 中已显示 `completed 25/25` 但运行状态为 `partial`，与检查点“cancelled 4/25”记录不一致，属 Codex 验收时需只读对账的遗留点（本 worker 未处理）。
- `claims_complete` 状态未触碰；临床/监管验收与生产写入均留待 Codex。
