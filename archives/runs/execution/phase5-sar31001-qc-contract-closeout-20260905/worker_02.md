# Execution Output: phase5-sar31001-qc-contract-closeout-20260905 - worker_02

## Boundary And Context Check

- 已读初始读取集：`context/phase5-sar31001-qc-contract-closeout-20260905_execution_context.md`、`plans/codex_execution_phase5-sar31001-qc-contract-closeout-20260905.md`。全部工作在 runner 绑定的工作区内完成，未读写任何生产路径，未安装包，未创建/修改任何文件（runner 管理的报告除外，由本响应返回）。
- 会话开始后发现工作区存在**并发编辑活动**（Codex 侧在同步落修复包）：`app/domain/gates/fact_evidence_closure.py` mtime 06:49、`fact_candidate_gates.py` 06:51、`tests/v2/domain/test_fact_candidate_gates.py` 06:51、`app/agents/evidence_normalizer.py` 06:52 与 07:08 两次更新。因此本 pass 的实现职责事实上已由并发编辑完成，我的角色转为：**根因定位 → 对并发修复做逐项验证 → 确定性重放取证 → 给出残余根因与测试边界**。本报告所有验证均标注了验证时的代码锚点；Codex 收口前应在编辑序列结束后重跑聚焦回归。
- 数据源：隔离运行库 `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`（全程 `sqlite3 mode=ro` 只读）。注意主库 `data_v2/enrollment-review-v2.sqlite3` 的 `fact_normalization_runs` 为 0 行，不是本任务运行包的来源库。

## Work Performed

**审计对象（最新不可变事实规范化运行）**：隔离库中最新终态运行 `916bf32f2f0d4ee8b08f187a246cbc9d`（2026-09-04 21:27:01 UTC 创建，终态 partial，prompt `c5b8f5ed…`，416 个候选，发布 271 事实 / 22 事件 / 8 暴露，71 条未解决项，Profile `pending_review_count=104`）。作为对照：`f6fe423a…`=151 事实（20260904 检查点的主gap运行）、`d0e3a463…`=281、`4ffa83f3…`=272。

### 1. 数值/单位规范化链（已闭合，验证通过）

- **根因（项目无关）**：提示合同与门禁直接矛盾。`evidence_normalizer.py` 系统合同（“血压、比较值或多分量结果可用只含数值、比较符、分隔符和阳性/阴性标记的紧凑字符串并保留共同单位”）明确指示模型输出带单位的紧凑字符串；而 `fact_candidate_gates.py` 的 `validate_fact_value_unit` 曾无条件拒绝一切“字符串值+单位”。该规则全链路仅此一处（无合同层/仓储层重复），单点成立。
- 上一检查点的 gap-1 修复（工作树未提交的 `_normalize_numeric_scalar`，evidence_normalizer.py:811）已在生产运行中验证生效：最新运行已发布心电图全套（心率 85 bpm、PR 160 ms、QRS 81 ms、P 103 ms、RV5+SV1 1.297 mV、QT 346/QTc 413 ms）、胆红素三项（30.5/8.7/21.8 μmol/L）、肌酐 79、尿素 4.28、白蛋白 49.3、ALP 84、多项 sIgE（271 事实 vs f6fe423a 的 151）。
- 剩余 12 个“非数值事实不应携带单位”拒绝逐例取证：9 例为提示合同明确要求的紧凑值串（`132/96` mmHg×2、`>100.00` kUA/L、`>1000.00阳性(+)`、`>4.00阳性(+)`、`<0.05阴性(-)`、`1.55阳性(+)`、`46/-4/34` deg、`0.736/0.561` mV）；3 例为叙述串/无数字定性值（2 条把用药叙述写成事实候选、`未检测到靶基因`+IU/mL）。
- **并发修复验证**：新 `_is_compact_measurement_value`（字符集+必须含数字）+门禁豁免分支，与测试规范 `test_fact_value_unit_accepts_compact_measurement_strings` 一致。确定性重放 12 例：**9 例获救、3 例保持 fail-closed（正确）**——门禁现与提示合同完全对齐，且不弱化对叙述串的拒绝。

### 2. 来源语义对齐链（已闭合，验证通过；为本轮最大漏项来源）

- **根因（项目无关）**：门禁权威规则 `resolve_source_strength_for_candidate`（fact_evidence_closure.py:744）只允许“由冻结 Phase 4 元数据派生的单一来源强度”（病历/筛选病历共享两个标签的例外）。模型在 5 标签词表内持续漂移选错：最新运行 44 个候选因此被拒（候选级：入组审核邮件×当前研究病历直接记录 31、入组审核邮件×筛选病历转述 4、检查报告×当前研究病历直接记录 6、实验室检验结果×当前研究病历直接记录 3；类型：fact 37 / event 5 / exposure 2）。提示合同虽已公布 5 个中文标签及选择规则（evidence_normalizer.py:486-493），但采样依赖的漂移在两次运行中均未消除。
- **并发修复验证**：新 `_align_source_semantics`（evidence_normalizer.py:1329）——单强度文档把模型标签确定性强制为派生标签；病历/筛选病历保留模型二选一并做安全映射（同期客观结果→当前研究病历直接记录、既往原始资料→筛选病历转述）。已确认双传输路径均接线（确定性路径 :1289 与真实 runner 循环 :1664），且**先于** `_enforce_exposure_source_fields`(:1433-1444) 执行——后者会丢弃 `无法确认来源` 的暴露候选，因此“邮件讨论不构成暴露”合同在修复后依然闭合（邮件暴露在发布前被确定性拦截；这也实际以 fail-closed 方向落了 20260904 检查点 flag-1 的实现取向，供 Codex 追认）。
- **确定性重放**：用真实 `_align_source_semantics` + 未改动的门禁允许集规则，对 44 个被拒候选逐一重放：**44/44 通过**（邮件→无法确认来源，检查报告/实验室检验结果→同期客观结果）。方向上只会弱化（不可溯源化）或按元数据归位，不引入强化。

### 3. 事件与用药暴露引用闭包链（残余缺口，未修复，需 Codex 裁决）

- 最新运行 9 个 `page_coverage_and_reference_closure` 拒绝**全部是事件**，且全是检验检查类事件（血常规检验×2、血生化检验采样、尿常规、12导联心电图检查、鼻内镜检查、肺功能测定、乙肝DNA定量检测采样、传染病血清学检测采样）。逐例验证：9 例的 `locator_ids` 与其引用事实的定位并集交集为 **0**（keep=0），即模型一律给事件挂了表头/页级定位——“缩小定位集合”式机械修复不可行。
- 跨运行对比证明这是**采样依赖的持续缺口**而非一次性回归：`4ffa83f3` 发布了“12导联心电图检查”事件，`916bf32f` 因定位闭包丢失；各运行检验检查类事件仅 2-3 个浮动。事实本身大多已发布，损失集中在 Profile 事件时间线。
- 可行的最小通用修复（**未实施**，属证据锚定语义变更，需 Codex/worker_03 评审）：事件/暴露定位闭包失败时，机械重锚 `locator_ids := 其引用事实候选的定位并集`（确定性、与合同“不得为事件增加表头/日期栏定位”一致、锚点不弱于事实证据）；或维持 fail-closed 并配合第 4 点可见性修复。前置条件：引用事实集合非空且至少一条通过门禁。
- 并发新增的“暴露必须至少由一条肯定事实支撑”门禁规则已验证为纯收紧且不翻转现有数据：最新运行 8 条已发布暴露全部有 affirmed 支撑（8/8）。

### 4. 残余根因（本轮未闭合，均已取证）

- **RC-可见性（建议优先）**：71 条未解决项全部来自模型自身输出；约 107 个门禁拒绝候选（12 unit + 44 semantics + 17 negation + 9 closure + 2 逐字对象等）不生成任何未解决项，复核者不可见。与 AGENTS.md 证据保存要求相悖。最小方案：终态发布门禁为每个被拒候选生成未解决项（code/reason/locator 绑定）。
- **RC-否定词表（fail-closed 正确，临床语义需 Codex 裁决）**：17 例否定拒绝中，多数为“宾语错位”（如“扁桃体无肿大”以“扁桃体”为对象——被否定的实为“肿大”，模型应选被否定的发现作对象，模型合规问题）；少数为确定性词表缺口——`_has_explicit_negation_relation`（fact_evidence_closure.py:234）的 `未(发现|提示|检出|诊断…)` 交替项缺少体检常用直接否定词“未及/未触及/未闻及/未扪及”（如“未及干湿啰音”被拒）。此项不属于本人三个指定子链，仅交证据与位置。
- 2 例“被断言对象不在当前定位有效原文内”为模型逐字违规且机械还原无唯一解，fail-closed 正确。

### 5. 测试边界

- 已有且通过：`test_fact_value_unit_accepts_compact_measurement_strings`（132/96、>1000.00阳性(+)、46/-4/34）+ `rejects_narrative…` + 门禁全套 48 项。
- **缺口（最高优先补测）**：`_align_source_semantics` 无任何专属测试。建议用例：① 邮件类文档强制“无法确认来源”（fact/event/exposure 三类）；② 检验/检查报告强制“同期客观结果”；③ 病历类保留模型在“当前研究病历直接记录/筛选病历转述”间的选择；④ 病历类“同期客观结果→当前研究病历直接记录”安全映射；⑤ 对齐后 `无法确认来源` 暴露被 `_enforce_exposure_source_fields` 丢弃（邮件暴露不发布不变式）；⑥ 对齐永不弱化门禁允许集（aligned label ∈ gate allowed）。
- 可选固化重放边界：以隔离库 56 个被拒候选 payload 为 fixture，断言 9+44 获救与 3 fail-closed 的精确划分（本 pass 重放脚本逻辑见下节，可整理为回归用例）。

## Artifacts And Evidence

- 本 pass 未创建/修改任何文件；报告即唯一产物。证据均为只读取证，要点如下：
  - 运行量化：`fact_gate_results`（run 916bf32f）——value_unit_date_source 360 accept/56 reject；locator_and_text_hash 396/20；page_coverage 407/9；transactional_publish 322/94；polarity 360/0。发布：clinical_facts_v2=271、clinical_events_v2=22、medication_exposures_v2=8；unresolved=71（code 分布：record_incomplete 17、ambiguous_date 11 等，无一门禁拒绝来源）。
  - 代码锚点（验证时快照）：evidence_normalizer.py:811-839（数值/剂量标量还原）、:475-493（值单位与来源语义提示合同）、:1329-1365（_align_source_semantics）、:1663-1664 与 :1289-1290（两传输路径接线顺序 align→enforce）、:1433-1444（不可溯源暴露丢弃）；fact_candidate_gates.py:141-190（紧凑值串豁免）、:408 附近（暴露肯定支撑规则）；fact_evidence_closure.py:234-250（否定词表）、:744-782（来源语义门禁权威，未改动）。
  - Phase 5 代码全部为未提交工作树状态（`evidence_normalizer.py`、`fact_normalization_executor.py` 为 untracked，其余多为 M），HEAD 尚无 `_normalize_numeric_scalar`/紧凑豁免/对齐逻辑。

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/domain/test_fact_candidate_gates.py tests/v2/domain/test_fact_evidence_closure.py tests/v2/domain/test_fact_batch_orchestration.py tests/v2/domain/test_evidence_normalizer_contracts.py tests/v2/domain/test_phase5_fact_contracts.py -q` → **209 passed**。
- `.venv/bin/python -m pytest tests/v2/agents/test_evidence_normalizer_adapter.py -q` → **79 passed**；`tests/v2/services/test_fact_normalization_*` + `test_fact_publication_service.py` → **65 passed**。
- 全量 `pytest tests/v2 -q` → **3644 passed / 3 failed / 3 skipped**（788s）。3 个失败均不在本人指定事实链内：`test_slice44_replay.py::test_replay_r1_frozen_corrections_not_later`（`RevisionClosureError: 完整修订的定位集合与生产候选及被提及资料闭包不一致`，evidence_locator_repositories.py:3308）、`test_evidence_processing_executor.py::test_native_pdf_creates_replayable_pages_without_external_ocr`、`test_patient_profile_repository.py::test_authority_stale_episode_revision_rejected`。需 Codex 分诊是否为并发编辑序列的中间态。
- 确定性重放（内联脚本，只读隔离库）：`validate_fact_value_unit` 重放 12 个 unit 拒绝 → 9 获救/3 保持拒绝；`_align_source_semantics`（真实函数，stub Output/Input）+ 门禁允许集规则重放 44 个 semantics 拒绝 → 44/44 通过；9 个闭包拒绝事件 keep=0（子集修复不可行）；8 条已发布暴露 affirmed 支撑 8/8。
- 提示版本核查：`prompt_versions` 仅存哈希（run c5b8f5ed 的 template_sha256=2b17d9b4…，当前默认模板哈希 19731130…），下次运行将自动登记新 prompt 版本——属设计内不可变行为，重跑时不应视为异常。

## Blockers Or Missing Environment

- **并发编辑未收尾**：验证期间 `evidence_normalizer.py` 仍在变化（06:52→07:08），本报告验证结论对应该快照；最终收口前需在编辑停止后重跑上述聚焦回归。
- 3 个全量套件失败（非本链）需分诊，可能是并发编辑中间态。
- `_align_source_semantics` 无专属测试（测试边界已给出 6 条用例规格）。
- 需 Codex 裁决项：① 事件定位机械重锚修复是否纳入本次最小修复包；② 门禁拒绝生成未解决项的可见性方案；③ flag-1 的实现现状（邮件实际使用直述 → 对齐为不可溯源 → 暴露被丢弃）是否即预期裁决方向；④ 否定词表是否补充“未及/未触及/未闻及/未扪及”（临床语义裁决）。

## Rerun Requests Or Next Step

- 本 pass 无需重跑；所有边界（工具、工作区、只读约束）均未触顶，报告完整交付。
- 建议的全量重跑前退出门槛（供 Codex 采信）：① 并发编辑序列收尾后重跑 353 项聚焦回归 + 全量套件失败分诊清零；② 落地 `_align_source_semantics` 专属测试与（可选）56 候选重放回归；③ 就上述 4 项裁决形成决定并落对应最小修复；④ 经正式 API 新建不可变运行，QC 对照预期增量：≥53 个候选级恢复（9 unit + 44 semantics）及依赖事件/暴露恢复、检验检查事件按裁决恢复，`claims_complete` 保持 false、结果不激活复核；⑤ 若采纳可见性方案，验证每个门禁拒绝均产出可复核未解决项后再进入临床逐项 QC（worker_01 清单）。
- 遗留不确定：并发修复的最终形态可能超出我验证的快照；重放为门禁级确定性证据，不等价于全链发布保证（去重/冲突组仍可能拒个别候选），最终临床 QC 与验收归 Codex。
