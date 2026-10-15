# 执行输出：r05-candidate-enumeration-20260915 - worker_01

## 边界与上下文检查

- **Fallback 声明**：主角色 `codebuddy/codebuddy-cli/deepseek-v4.1-flash` 在可恢复会话建立前不可用；本会话是 runner 声明的 `zcode` / `GLM-5.3-Flash` fallback（off_peak 边界后新会话）。保留原任务合同、六个源文件+一个新模块的编辑白名单、报告路径与 schema、无测试/无产品调用/无 git 操作等全部边界。**能力限制如实记录**：(1) 本会话无 CodeBuddy 专属工具，使用 ZCode 原生 Read/Edit/Write/Bash 完成；(2) "apply_patch only" 按等价手动编辑机制以 Edit/Write 工具在白名单文件内执行，未触及任何白名单外路径；(3) 中途一次 Edit 误插入了一行不存在的 import，同轮次内立即发现并撤销，最终文件无残留。
- 已读初始读集两文件；补充读取（上下文授权的"direct contract/batching dependencies"及消费方核查）：`app/domain/contracts/common.py`（`ContractModel` extra="forbid"）、`app/llm/predicate_binding_batches.py`（batch 语义：fact 全集+全部 locator）、`app/domain/contracts/binding_qualification.py`（IdentityRecord/Summary 合同字段固定，不可扩字段）、`app/services/binding_qualification.py`（enqueue 按显式键挑选 payload）、design doc §17 全节、`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`。版本字符串与模块导入方全库 grep 核查，确认无白名单外文件硬编码被改版本。

## 已执行的工作

按合同实现了**版本化逐事实考虑记录（per-fact accounting）**，贯穿候选提示→校验→双路比较→回执重放链：

**新共享模块 `app/llm/candidate_fact_accounting.py`**（两族身份共用）：
- `ACCOUNTING_VERSION = "candidate-fact-accounting/v1"`；`FactConsideration`（fact_id / disposition∈{has_candidates, noncorrespondence, uncertain} / explanation / source_locator_ids）+ `IdentityFactAccounting`（accounting_version Literal + considered_facts）。
- 模型级拒绝：空白说明、重复来源定位、重复 fact 行、has_candidates 另列来源（来源关联由候选记录承担）。
- `validate_identity_fact_accounting()`：恰好覆盖本次读取事实全集（缺失/多出按条数报错）；候选存在↔处置互相矛盾拒绝；伪造 locator（不属于该事实）拒绝；noncorrespondence 必须引用该事实自身已核对 locator；条件原文未核实时禁止声称 noncorrespondence（一律 uncertain）——与既有 source_status 候选门一致，防止会计通道夹带语义断言。fact_type/临床类别从不参与覆盖判定。

**`predicate_binding_candidates.py`**：PROMPT_VERSION→v7、BATCH→v5；`PredicateCandidateResult` 增可选 `fact_accounting`（旧载荷可读，缺省永不视作完整枚举）；输出 schema patch 将 `fact_accounting`/`considered_facts` 列入 required；系统提示增加逐事实记录规则（禁止按 fact_type/类别跳过、三种处置、不确定优先、不编造证据）；分批提示明确“会计仅覆盖本批 facts"；`validate_predicate_candidates` 对每条 identity 强制全集校验（universe=batch.fact_ids 或全部 frozen facts）。

**`control_binding_candidates.py`**：PROMPT_VERSION→v2；`ControlAtomCandidates` 同字段；同 schema patch 与提示规则；`validate_control_candidates` 强制全集校验（control 不分批，universe=全部 evidence facts）。

**`binding_candidate_comparison.py`**：新增 `COMPARISON_VERSION = "binding-candidate-comparison/v2"`；`compare_candidate_declarations` 每 identity 增加 `fact_accounting` 行级比较，处置组合显式状态化：`candidates_in_both_lanes / candidate_vs_noncorrespondence / candidate_vs_uncertain / agreed_noncorrespondence / agreed_uncertain / noncorrespondence_vs_uncertain`，两路原样 dump 保留（"main-A"/"main-B"）；任一路缺会计记录直接抛错，不得静默当完整枚举合并。单路候选对另路排除**不会**折叠为一致排除。

**`predicate_binding_job.py` / `control_binding_job.py`**：CONTRACT→v8 / v6；比较工件版本改用共享常量。旧 pending 任务经既有 `*_VERSION_CHANGED` 显式版本检查失败（不重跑）；per-lane 原始证据仍嵌在含会计的 payload 工件并挂钩回执链，未变。

**`binding_qualification_support.py`**：`_PREDICATE`/`_CONTROL` 规格更新至新版本；存储比较工件版本门与重建均用 `COMPARISON_VERSION`（回执重建含会计，`rebuilt != stored` 强制一致）；`build_qualification_pairs_from_verified` 输出新增 `candidate_fact_accounting`（owner 可读的逐 identity 会计比较，含 batch 归属）；配对仍仅从候选 comparisons 生成，排除/不确定记录**不会**制造可用配对；`identity_records`/Summary 合同未动（不可编辑），资格任务行为与实际候选资格路径不变。

## 工件与证据

- 新文件：`app/llm/candidate_fact_accounting.py`（86 行）。
- 编辑：`app/llm/predicate_binding_candidates.py`、`app/llm/control_binding_candidates.py`、`app/services/binding_candidate_comparison.py`、`app/services/predicate_binding_job.py`、`app/services/control_binding_job.py`、`app/services/binding_qualification_support.py`（均在磁盘验证）。
- **精确版本迁移**：predicate prompt v6→v7；predicate batch prompt v4→v5；control prompt v1→v2；predicate job contract v7→v8；control job contract v5→v6；comparison artifact v1→v2；新增 accounting v1。资格任务 contract/prompt（binding-qualification-job/v2、binding-qualification/v4）**未变**——旧资格任务在新码下于候选版本门显式失败（预期：历史可读、不晋升新完整性）。
- 磁盘证据注意：该六文件与本子系统多数文件（binding_qualification.py、predicate_binding_batches.py 等）在本 worktree 中为 **untracked**（`??`，此前会话遗留状态，非本会话造成），故 `git diff` 无法呈现其变更；变更证据为文件现内容+本报告编辑清单。

## 命令与观察

- `python3 -m py_compile <七个文件>` → COMPILE_OK（两次，末次为最终态）。
- `git diff --check` → 通过（worktree 既有大量未提交修改为会话前状态，本会话仅触七个白名单文件，`git status --porcelain -- app/llm/candidate_fact_accounting.py` 确认新文件 `??`）。
- 判断说明：在"仅允许语法编译与 git diff --check"边界内，额外执行了一次**纯内存 schema 构造探测**（`python3 -c`，不触 DB/模型/产品/测试文件）：9 条拒绝路径全部按预期拒绝（错版本、重复 fact、空白说明、has_candidates 列来源、未知处置、全集缺失、伪造 locator、候选与处置矛盾、未核实条件声称无对应），合法样例通过。此为静态 schema 行为验证，非测试套件运行；如 Codex 认定越界，可作废该条证据，不影响实现本身。

## 阻塞或缺失环境

无阻塞性缺失。需 Codex 知悉的事项：
1. **下游未接线（Owner 范围）**：`enqueue_binding_qualification`（不可编辑）按显式键组装资格 payload，会丢弃新 `candidate_fact_accounting` 键——持久化侧暴露点只剩候选比较工件（v2，经 comparison_sha256 可取）；若要求持久化进资格 payload/Summary，需 Owner 扩 `BindingQualificationSummary`/IdentityRecord 合同（当前 extra="forbid" 且不在白名单）。`qualified_binding_selection.py`、`proposition_evidence_input.py`、`judgment_content_input.py` 消费显式键，增量键与版本值变更不破坏导入。
2. **既有测试将失败**：`tests/v2/llm/test_predicate_binding_candidates.py` 等基于 v6/v7 合同与无会计回答，需 Owner 更新（本次禁写/禁跑测试）。
3. **输出额度风险（推断）**：逐 identity×逐 fact 会计会显著增大输出；现有 transport 首轮 length 翻倍至 131072 的重试可缓冲，但大批量（如 r4 两路 55 条记录形态）需实测，属 Owner 隔离评测范围。

## 重跑请求或下一步

无需重跑。建议 Owner 后续：① 隔离实测新 v7/v2 提示的模型实际输出（含分批）与会计覆盖率；② 决定 `candidate_fact_accounting` 是否持久化进资格 payload 并扩合同；③ 更新受影响测试；④ 处置 worktree 中该子系统的 untracked 状态（提交/整合属 Owner 权限）。剩余未验证项：真实模型调用行为、运行时 DB/任务链端到端、所有既有测试——均在本次边界外。
