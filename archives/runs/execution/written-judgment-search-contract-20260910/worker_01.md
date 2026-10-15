所有检查完成。以下为执行报告。

# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 工作目录为 runner 绑定的 worktree（`phase5-clinical-facts-profile` 分支），未越界。初始读集两份文件均已读取：`context/written-judgment-search-contract-20260910_execution_context.md`、`plans/codex_execution_written-judgment-search-contract-20260910.md`。
- 按 Source of Truth 补充读取（只读）：`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`（§11 判断边界、§16 完成定义、2026-09-06/09-09/09-10 裁决段）、`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` §2（2026-09-10 判断实施顺序，含被否决的“仅测量页”方案——本实现未采用该方案，范围含全部文件的打印分析与手写两通道）、`app/domain/contracts/page_review.py`、`facts.py`、`common.py`、`evidence.py`（BoundingBox）、`enums.py`（StableEnum）、`app/domain/page_review_evidence_sources.py`（frozen + 内容寻址 + 入口重验证模式）、`app/domain/publication.py`（`canonical_hash`）、`app/projections/written_judgment_evidence.py`、测试风格参照 `tests/v2/domain/test_page_review_candidate_sources.py`。
- 三个授权目标文件此前均不存在（`ls` 确认），为全新创建；未改任何 `__init__.py` 导出、未接线仓储/模型调用、未动 worktree 中其他既有未提交修改。
- 工具限制说明：本运行时无 `apply_patch`，改用 ZCode 的 Write/Edit 工具完成新文件创建与修正，效果等同且未触碰无关行。

## Work Performed

实现了最小 CANDIDATE-only 合同与纯覆盖核验，共 3 个新文件：

1. **`app/domain/contracts/judgment_search.py`**（合同，纯校验无存储）：
   - `JudgmentSearchScope`：冻结页域，绑定 `FactAuthority` + requirement 身份 + 逐页来源身份（`JudgmentSearchPageIdentity`：资料版本/页工件/页码/页图 SHA256）；`scope_sha256` 内容寻址（`canonical_hash`，identity `judgment_search_scope/v1`）且构造时强制重算一致。硬不变量：页域非空、页身份唯一（同版本+工件+页码视为重复，哈希不同按陈旧重复拒绝）、成员按 `(版本, 工件, 页码)` 确定性排序（乱序拒绝）。页域只接受显式逐页清单，无任何按可读性/日期/文档类别过滤的字段——不可读或日期不明资料无法被静默排除。
   - `JudgmentSearchLaneResult`（main-A/main-B 读道，引用精确 `scope_sha256` 与 provider/model 身份，页结果唯一）/ `JudgmentSearchPageResult`（每页手写+打印分析两通道齐备）/ `JudgmentSearchChannelResult`（found/not_found/unreadable/ambiguous；found 必须携带逐字摘录、bbox 可选；非 found 不得携带摘录或坐标）。
   - 设计决策（请 Codex 知悉）：读道身份仅 `(provider, model)`，无 reasoning_effort 字段——同模型不同强度不构成第二条独立读道（对应设计书“GLM low 与 high 不构成两票”）。
   - `JudgmentSearchCoverageSummary`：三个不变量字段类型锁定 `Literal[False]`（`source_scope_verified` / `product_acceptance` / `professional_judgment_absence_proven`），构造即拒绝 True；无任何时间戳字段；命名全部为 candidate/coverage，无 certified/accepted 语义。
2. **`app/domain/judgment_search_coverage.py`**（纯函数 `summarize_judgment_search_coverage`）：
   - 直接拒绝（`JudgmentSearchCoverageError`）：范围哈希不一致、范围外多余页、页图哈希与范围身份不符、读道重复、两条读道相同 provider+model、超过两条读道；形状矛盾由合同层拒绝。
   - 覆盖不完整（`coverage_incomplete`，绝不折叠成 not_found 或判断缺失）：范围内页在某读道无逐页结果、unreadable、ambiguous、整条读道缺席；缺口逐项结构化保留。
   - 仅当给定范围每页均有两条独立有效记录且两通道在两读道均显式 not_found → `all_supplied_pages_searched_without_candidate`；任一 found（任何页/文件/通道/读道）→ `candidates_present`，found 与未闭合缺口并列保留；混合 found/none 不构成共识通过。
   - 输入经 `model_validate(model_dump())` 重验证（防上游 frozen 可变性绕过），与 `page_review_evidence_sources.py` 同约定。
3. **`tests/v2/domain/test_judgment_search_coverage.py`**：22 项合成测试，覆盖任务书全部指定场景（详见下节）。

**未实现/未接线（按要求显式声明）**：仓储构建完整来源范围、产品独立双检索执行、持久化、适用性判定、以及“判断缺失”结论的生产者均**未**实现、**未**接线；本模块不能直接产生专业判断缺口，也**未**声称范围覆盖全部适格临床来源（`source_scope_verified` 恒 False）。无任何产品临床行为变更。

## Artifacts And Evidence

| 文件 | 状态 | 说明 |
|---|---|---|
| `app/domain/contracts/judgment_search.py` | 新建 | 冻结页域 + 双读候选检索合同 + 覆盖摘要合同 |
| `app/domain/judgment_search_coverage.py` | 新建 | 纯覆盖核验函数 + `JudgmentSearchCoverageError` |
| `tests/v2/domain/test_judgment_search_coverage.py` | 新建 | 22 项合成测试 |

测试覆盖映射：两文件且打印分析在非测量页 found 阻断 all-not-found；第二通道不完整（unreadable）；缺页；双读道 unreadable；ambiguous；仅单读道；同模型冒充第二读道（拒绝）；范围哈希不一致（拒绝）；页图哈希伪造（拒绝）；范围外多余页（拒绝）；重复读道（拒绝）；读道内重复页（构造期拒绝）；空页域（拒绝）；乱序页域（拒绝）+ 顺序确定性 + 哈希绑定 authority/requirement/页域 + 陈旧哈希拒绝；全 not_found 仍不证明判断缺失（三不变量 False 且不可改写）；混合 found/none 非共识；found 缺摘录 / 非 found 带摘录或坐标（拒绝）；judgment/eligibility 等额外字段（extra="forbid" 拒绝，含 Summary 层）；页域/页身份无过滤字段（字段集合冻结断言）。

## Commands And Observations

- `rg`/`sed` 读取 Source of Truth 各文件（观察：`canonical_hash`、`ContractModel`/`StableEnum`、frozen+tuple+入口重验证为既有约定，已沿用）。
- `.venv/bin/python -m pytest tests/v2/domain/test_judgment_search_coverage.py -q` → **22 passed**（首跑 2 项失败均为测试自身笔误：`_scope` 辅助函数预先排序掩盖了模型层乱序拒绝、非 found 用例漏传摘录；修正后通过。pydantic `model_copy(update=...)` 绕过验证，相关断言已改为 `model_validate` 回路）。
- `.venv/bin/python -m pytest tests/v2/domain/test_phase5_fact_contracts.py tests/v2/domain/test_page_review_evidence_sources.py -q` → **73 passed**（最小相关既有合同测试，验证 `FactAuthority` 依赖与同模式模块无回归）。
- `git status --porcelain`（限定三文件路径）→ 仅三个新增未跟踪文件；`app/domain/contracts/__init__.py` 等既有修改系会话开始前已存在（见初始 git status 快照），本次未触碰。

## Blockers Or Missing Environment

- 无阻断。唯一环境说明：`apply_patch` 在本运行时不可用（已按边界要求记录）；以 Write/Edit 等价新建，未产生副作用。

## Rerun Requests Or Next Step

- 无需重跑。留给 Codex 验收的两个声明式决策点：(1) 读道身份刻意不含 reasoning_effort（同模型不同强度不构成双读）；(2) 空读道结果不可构造（`min_length=1`），整读道缺席以“不提交该读道”表达并计入 `missing_lanes`。若 Codex 希望调整任一语义，属小改动。
- 后续（本步范围外、仍为必需）：仓储构建器冻结完整来源范围（含不可读/日期不明资料显式在列）、产品双读检索执行与持久化、条款级判断缺失报告生产者、真实模型与原件验证。
