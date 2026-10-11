四项修正全部完成并通过测试。以下为修正报告。

# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 同会话续作，写入范围仍限于三个授权文件：`app/domain/contracts/judgment_search.py`、`app/domain/judgment_search_coverage.py`、`tests/v2/domain/test_judgment_search_coverage.py`（`git status --porcelain` 确认仍仅为这三个未跟踪新文件，无既有产品路径被修改）。
- 未接网络、未调模型、未装依赖、未派子代理、未做会议；实现仍为 candidate-only、未接线仓储或产品运行时。
- 按所有者审阅意见执行四项修正，其中确认所有者原始“ambiguous 不得携带摘录”的措辞过严——已按新指令放宽为“ambiguous 可保留零或多条暂定摘录，保持歧义、不得晋升 found”。

## Work Performed

**1. 多摘录候选（替换单一 excerpt/bbox）**
- 新增 `JudgmentSearchExcerptCandidate`（frozen：`text` + 可选 `bbox`，无模型标识字段，字段集合就是 `{text, bbox}`）。
- `JudgmentSearchChannelResult.excerpt/bbox` 替换为 `candidates: tuple[...]`：found 必须非空；not_found / unreadable 必须为空（拒绝虚构）；ambiguous 允许零或多条暂定摘录。
- 覆盖摘要：`JudgmentSearchFoundCandidate.candidates` 整组保留全部摘录；新增 `JudgmentSearchChannelGap.disposition`（只允许 unreadable/ambiguous）与 `tentative_excerpts`——ambiguous 缺口按原样携带全部暂定摘录，与 `found_candidates` 并列保留，绝不只留第一条；unreadable 缺口携带摘录在合同层直接拒绝。summarize 对 candidates 做整元组透传，无截断、无重排。

**2. 来源页身份冲突拒绝（范围与读道结果同规则）**
- 新增共享检查 `_check_page_identity_collisions`，`JudgmentSearchScope` 与 `JudgmentSearchLaneResult` 构造时均执行，拒绝三类：精确重复（版本+工件+页码，原有）；**同一资料版本同一页码由两个页工件代表**；**同一页工件复用于不同页/不同文档**。错误信息明确“来源页身份冲突，不是两页”。既有页图哈希精确核对不变；summarize 因输入重验证而自动继承该拒绝。

**3. 读道身份规范化 + reasoning_effort 审计字段**
- `provider` / `model` / `reasoning_effort` 统一经过校验器：拒绝纯空白、存储前剥离首尾空白。独立性比较改为 `(provider.casefold(), model.casefold())`——仅大小写/空白差异的两条读道被拒绝，不构成独立双读。
- 合同与核验模块 docstring 明确声明：该比较只为拒绝同一身份伪装双读，**不证明跨 provider 的模型别名消解，真实路由身份核验仍是仓储/运行时职责**。
- `reasoning_effort` 为必填非空审计字段，**绝不参与**独立性比较（同 provider+model 不同 effort 仍拒绝）。
- 无任何时间戳字段（维持原状，无 fabricated timestamp）。

**4. 报告措辞更正**：本会话与后续报告如实写明使用 ZCode Write/Edit 工具；`apply_patch` 在本运行时不存在，不再声称“效果等同 apply_patch 合规”，仅陈述事实：三个新文件由 Write/Edit 创建、未触碰无关行。

## Artifacts And Evidence

三个文件的修改点：
- `app/domain/contracts/judgment_search.py`：模块 docstring 重写诚实边界；新增 `JudgmentSearchExcerptCandidate`、`_normalize_nonblank`、`_check_page_identity_collisions`；`JudgmentSearchChannelResult`/`JudgmentSearchFoundCandidate`/`JudgmentSearchChannelGap` 改多摘录结构；`JudgmentSearchLaneResult` 增 `reasoning_effort` 与身份剥离校验器；`JudgmentSearchScope`/`JudgmentSearchLaneResult` 接入身份冲突检查；`__all__` 增 `JudgmentSearchExcerptCandidate`。
- `app/domain/judgment_search_coverage.py`：身份比较 casefold 化（含别名消解免责声明）；found 候选整组透传 candidates；ambiguous 缺口携带 `disposition=AMBIGUOUS` + 全部 `tentative_excerpts`，unreadable 缺口携带 `disposition=UNREADABLE` 且无摘录。
- `tests/v2/domain/test_judgment_search_coverage.py`：更新 8 个既有用例以适配新结构，新增 9 个用例。现共 **31 项**，覆盖：同页多 found 候选全量保留（绝不只留第一条）；ambiguous 暂定摘录全量保留且保持歧义（found 为空、状态 incomplete）；unreadable 缺口禁带摘录 + 缺口处置只允许 unreadable/ambiguous；范围拒绝同版本同页码双工件、工件跨页/跨文档复用；读道结果同规则拒绝；纯空白 provider/model/effort 拒绝 + 存储剥离断言；reasoning_effort 必填且不参与身份（同身份不同 effort 仍拒绝）；仅大小写差异不构成独立；其余原有场景（缺页/失败/歧义/单读道/范围哈希/页哈希/多余页/重复读道/空页域/乱序/全 not_found 非证明/混合 found 非共识/额外字段拒绝）全部保留。

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/domain/test_judgment_search_coverage.py -q` → 首跑 4 failed / 27 passed；4 项失败均为测试侧问题而非合同缺陷：(a) 旧夹具让两个文档版本复用同名页工件 `page-1`——在新身份冲突规则下被**正确**拒绝，改用各文档独立工件名；(b) drifted 读道构造缺新增必填 `reasoning_effort`；(c)(d) 两处 list/tuple 断言写法。修正后 → **31 passed**。
- `.venv/bin/python -m pytest tests/v2/domain/test_phase5_fact_contracts.py tests/v2/domain/test_page_review_evidence_sources.py -q` → **73 passed**（与修正前同一范围，无回归）。
- `git status --porcelain`（限定三文件）→ 仅三个未跟踪新文件；既有产品路径零改动。

## Blockers Or Missing Environment

- 无阻断。工具事实：本运行时无 `apply_patch`，全部修改经 ZCode Write/Edit 完成；本报告不作等价性声明。

## Rerun Requests Or Next Step

- 无需重跑。仍为必需且**未**实现的后续（与上轮声明一致，本轮无变化）：仓储构建器冻结完整来源范围（含不可读/日期不明资料显式在列，并依赖本轮新增的来源页身份唯一性）；真实路由身份核验（provider/model 别名消解属运行时职责，合同层已声明不覆盖）；产品独立双检索执行、检索结果持久化与回读核对（receipt 重验 scope_sha256 与页哈希绑定）；条款级判断缺失报告生产者；真实模型与原件验证。实现保持 candidate-only、未接线、无任何临床采信或来源完整性声明。
