Trellis SessionStart 上下文已加载 ✓

开始只读复核。先读初始读取集。

Bash 被拒；改用只读工具（Read/Glob/Grep）。

`full-suite.log` 不在 artifacts 目录中——先确认证据文件实际落点。

Bash 在当前会话被禁用。我改用 Explore 子代理做 XML 聚合（只读），同时自己读核心源码。

I'll handle this as a read-only aggregation. Bash with python3 (pure read of the XML, stdout output) is consistent with "Read-only aggregation task". Let me first check file existence and size, then parse.

Bash is denied in this non-interactive session. I won't paste the raw XML as you directed. Let me see what I can extract with the readonly tools I do have (Glob for the file-name check), and report the rest as gaps.

Tool "Write" does not exist in the current tool set.

Bash is denied in this non-interactive session, and `Write` is not in this tool's toolset, so I cannot create the plan file at `/Users/smkzw/.codebuddy/plans/electric-aurora-tesla-7weeqG1y.md`. I also will not paste raw XML.

What I could verify via `Grep` `-c` and `Glob` (both readonly; every count below is exact on the single-line file because each match is one literal occurrence, and `glob` failed to find anything matching the literal pattern was treated as an exact negative).

# Read-only aggregation: `artifacts/acceptance-20260916/full-suite.xml`

## 1. File size + sibling log
- File size in bytes: **CANNOT COMPUTE** — `stat`/`wc`/`ls -la` all require Bash.
- `full-suite.log` anywhere under the worktree (excluding `.venv`): **NO** (Glob `**/full-suite.log` returned no files).
- Also `*.log` anywhere in the worktree (Glob `**/*.log`): **NO**, so the JUnit XML is the sole runtime artifact for this run.
- Other `full-suite*` files present (older review-20260912 snapshots, not the acceptance run):
  - `artifacts/review-20260912/full-suite-20260913-binding-v6.xml`
  - `artifacts/review-20260912/full-suite-20260913-recovery-gap-view.xml`
  - `artifacts/review-20260912/full-suite-20260913-r06-source-successors.xml`
  - `artifacts/review-20260912/full-suite-20260913-r06-conflict-successors.xml`

## 2. Top-level XML structure (counts are exact Grep `-c` matches on the single-line file)
- `<testsuite ...>` element: 2 literal occurrences (open + close; the open tag's attribute text is on the same giant line and was truncated as "Omitted long matching line" by ripgrep, so I could not parse `name= failures= tests= skipped=` verbatim — **CANNOT COMPUTE totals from `<testsuite>` attributes as text**).
- `<testcase classname=` : **343** testcases
- `<failure ` : **342** failures
- `<error ` : **0** (no errors, only failures)
- `<skipped` (any): **3** skipped testcases
  - of which `<skipped type="pytest.xfail">` : **1** (one xfail)
  - `<xfail` (lowercase element): **0** — pytest emits this as `<skipped type="pytest.xfail">`, not as `<xfail>`
- `<properties` / `<property name=` : **0** — no `<properties>` block at all
- `<system-out` / `<system-err` : **0** — no captured stdout/stderr sections
- `<failure message=` : **342** (every failure carries a `message=` attribute)
- `message="[A-Z][a-z]+Error"` (any leading exception class) : **136**

Failures by leading exception class in `message=`:
| Exception prefix | Count |
|---|---|
| AssertionError | 63 |
| ValueError | 35 |
| AttributeError | 32 |
| TypeError | 3 |
| KeyError | 2 |
| RuntimeError | 0 |
| (other / no `xxxError:` prefix) | 207 |

The 207 unaccounted-for failures are messages whose text does not start with `<ClassName>Error:`. Likely candidates (cannot enumerate without a real parser):
- `DID NOT RAISE` style messages from `pytest.raises` mismatches → 2 occurrences of `DID NOT RAISE`, 2 of `Failed: DID NOT`, 4 of `<failure message="Failed` → at minimum 4 of those 207 are `Failed: ...`-prefixed
- `NotImplementedError` (0 matches)
- `message=` missing on 0 failures (every failure has one), so all 207 are real messages with non-Error-leading text

## 3. Failure families — top aggregate available without a parser

I cannot reliably group-by-normalized-message without a python parser, because ripgrep collapses every `<failure message="...">` block into one trimmed snippet per pattern, and many `<failure>` bodies contain literal addresses/numbers/`<...>` fragments that defeat one-shot regex.

What I *can* say from focused greps:

Largest single dominant family is the **`AttributeError` from `validate_control_evaluations`** cluster:
- `validate_control_evaluations` (function name in tracebacks) → **58** occurrences
- Top project frame `app/domain/contracts/control_evaluation_spec.py:[0-9]+: in` → **29** distinct occurrences (deepest project frame for ~29 of the 342 failures)
- `message="AttributeError` → **32** failures
- Sub-cluster messages of that 32 confirmed include:
  - `AttributeError: module 'app.services.eligibility_review_projection' has no attribute 'evaluate_component'`
  - `raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')`
- Driver test module for this sub-cluster: `tests/v2/services/test_predicate_candidate_scope.py` (3 testcases use that classname, anchor line `tests/v2/services/test_predicate_candidate_scope.py:29: in test_candidate_types_stay_with_their_own_component` → **3** occurrences)

Per the user's keyword list, here is what is in the XML text:
| Keyword asked | Count | Notes |
|---|---|---|
| `evaluation spec` (literal phrase) | 0 | not present |
| `evaluation_spec` (snake-case token) | 29 | only inside the path `app/domain/contracts/control_evaluation_spec.py` and adjacent text in tracebacks |
| `MissingEvaluationSpec` | 0 | not present |
| `time binding` | 0 | not present |
| `check_control_publication` | 0 | not present |
| `AttributeError` | 63 (any); 32 (leading `message="AttributeError`) | see breakdown above |

The user asked for "the full set of test ids for families whose message mentions `<those keywords>`" with exact messages. **CANNOT COMPUTE without a per-testcase parsed dump, which requires `python3` via Bash.**

## 4. Per-module (classname file) failure counts ≥ 5

**CANNOT COMPUTE authoritatively.** What I could verify from focused classname greps:
- All 343 testcases have `classname="tests.…"` (zero have `classname="app.…"`); total 343 vs `classname="tests.` = 343 (exact).
- `classname="tests.v2.services.*` : 31 testcases total
- `classname="tests.v2.services.test_predicate_candidate_scope"` : 3 testcases
- Specific module names of failures (≥ 5) require parsing each `<testcase>` block and pairing `<failure>` with its parent. With Grep alone I cannot distinguish "testcase with no failure" from "testcase with one failure" without per-occurrence streaming, which ripgrep's `-c` does not provide.

## 5. Traceback source anchors (`(tests|app)/.*:[0-9]+: in `)

- `tests/.*:[0-9]+: in ` → **648** total occurrences
- `app/.*:[0-9]+: in` → **574** total occurrences
- Combined frame anchors ≈ 1222 → ≈ 3.6 project frames per failure on average.

Top app-code anchors I could confirm:
| Anchor (file:line pattern) | Count |
|---|---|
| `app/domain/contracts/control_evaluation_spec.py:[0-9]+: in` (frame `validate_control_evaluations`) | 29 |
| `app/services/eligibility_review_projection.py:[0-9]+: in` | 18 |

All remaining ~527 `app/*:NN: in` frames are spread across other source files; I cannot enumerate the top-20 list without reading per-failure tracebacks line by line.

Top test-side anchor I could confirm:
- `tests/v2/services/test_predicate_candidate_scope.py:[0-9]+: in` → 3 (matches the 3 testcases above)

The deeper top-20 list of `file:line: in func` anchors **CANNOT BE COMPUTED without Bash + python3.**

## 6. Pytest plugin / ordering hints

- `<properties>` element: **0** (no `<properties>` block exists in the JUnit XML, so neither pytest-randomly's seed nor pytest-xdist's `worker_id` is recorded).
- `randomly` text anywhere: **0**
- `xdist` text anywhere: **0**
- `pytest-randomly` text: **0**
- `ordering` text: **2** — both occurrences are inside long failure-message bodies (the lines were truncated by ripgrep as "Omitted long matching line"); they are not pytest configuration markers. JUnit-XML carries `-p no:randomly`/`-p xdist` only via the `<properties>` block, and there is none.

So the XML gives **no affirmative hint** that pytest was invoked with `-p no:randomly` or with xdist/any ordering plugin. The 2 `ordering` substrings are content text inside failure messages, not plugin markers. To be certain, the runner's actual command line (which is not in this XML) would need to be checked separately — **flagged as unverifiable from this artifact alone**.

# Gaps flagged (could not compute in this session)

1. File size in bytes (need Bash `stat`/`wc -c` or `ls -la`).
2. Verbatim `<testsuite name=... failures=... tests=... skipped=...>` attributes (single line truncated by ripgrep; needs a parser).
3. Failure-family groupings by normalized message (needs python3 + `xml.etree.ElementTree`).
4. Top-25 family table with example test ids (needs a parser).
5. Full set of test ids + truncated messages for families whose message mentions `evaluation spec`, `evaluation_spec`, `MissingEvaluationSpec`, `time binding`, `check_control_publication`, `AttributeError` — `MissingEvaluationSpec`, `time binding`, `check_control_publication`, and `evaluation spec` are not present in the XML at all; `evaluation_spec` and `AttributeError` are present (29 and 63 occurrences respectively) but enumerating test ids and exact messages needs a parser.
6. Per-module failure counts ≥5 (needs a parser).
7. Top-20 `file:line: in func` anchors (needs a parser to pick the last matching frame per failure).
8. The `<testsuite>` attribute totals cannot be cross-checked against my element counts (343 testcases + 3 skipped = 343 counted by `<testcase>`; failures 342) without reading the attribute text, which requires a parser.

I stopped per your instruction. If you grant Bash with `python3` (or grant `Write` so I can persist a plan), I can produce the full aggregations in one run by streaming the file through `xml.etree.ElementTree`. End of report.

Explore 子代理同样无 Bash，且其计数语义可疑。我自己校准计数并用结构化 grep 提取失败帧。

计数语义需要校准。并行做校准 grep 并读取核心契约源码。

校准结果异常：`<testcase ` 计数=343 与表头 tests="4944" 矛盾。需要判定 XML 是否被截断。

计数语义已校准：Grep count = 命中**行**数，不是元素数（343 = 342 个失败边界行 + 首行）。开始按族提取。

关键发现：冻结 XML 的 3988 行帧文本是 `validate_control_evaluations(semantics)`，而当前源码已是 `validate_control_expression_evaluations` —— 该 XML 早于修复。继续核对调用链与会话契约。

会话契约已明确。现在按 `message="` 属性（每个失败一个）做族计数，并检查新测试文件是否在（修复前）XML 中。

`test_control_candidate_evaluation_scope` 在 XML 中不存在 → 佐证 XML 早于修复。继续量化 29 与真实缺陷族。

# Conference Output: acceptance-backend-triage-20260916 - evidence_single_object

## Output

**Role**: `evidence_single_object`（重要证据审阅），serial 单次有界通过。
**方式**: 只读。未修改任何文件，未运行测试，未调用产品模型，未读取工作区外临床资料，未写 runner 报告路径。
**工具限制（影响证据强度，如实披露）**: 本会话 `Bash` 被权限拒绝，Explore 子代理同样被拒。因此 `.xml` 无法用解析器聚合；下文所有计数均来自 ripgrep 行计数，并已校准语义（见 E0）。凡不能由行计数可靠得到的数据，我标注为不可验证，不用估算值冒充事实。

---

### E0. 证据口径校准（先立规矩，否则全篇计数会被误读）

1. `artifacts/acceptance-20260916/full-suite.xml` 是**单行巨型 XML**：全部 `<testcase>` 与失败开标签挤在物理第 1 行，各失败的回溯体按行展开。
2. 因此 Grep `count` 返回的是**命中行数**，不是元素数。校准证据：`<testcase ` = 343 行，`type="pytest.xfail"` = 1 行，而表头 `tests="4944"`——只有"行计数"解释自洽（343 = 342 个失败边界行 + 首行）。
3. 有效族计数用法：`message="…"` 属性每失败恰好一次；`^E   <异常类>` 每失败恰好一次（链式异常会多出 1–4 行）。两者交叉一致，故下述族规模可用。
4. **表头事实（我直接读到）**：`errors="0" failures="342" skipped="11" tests="4944" time="1124.877" timestamp="2026-09-16T08:25:21.745311+08:00"`。
   - 口径冲突：任务书写"4589 passes, 3 skips, 8 xfails"。342+4589+3+8 = **4942 ≠ 4944**；按表头应为 4591 passes（342+4591+11=4944）。差值 2，来源不明（可能把 xfail 计入了 passed）。**下游结论不要引用 4589 这个数。**
   - `artifacts/acceptance-20260916/full-suite.log` **不存在**（Glob `**/full-suite.log` 无匹配；`artifacts/` 下只有 xml/png/json/receipt）。任务书把 log 列为冻结证据，实际不可用。

---

### F1（最高影响，阻断性）冻结证据早于被审修复，因此不能作为修复后状态的判据

- **证据（观察）**：XML 回溯帧原文为
  `app/protocols/protocol_control_gate.py:3988: in _validate_candidate` → `validate_control_evaluations(semantics)`（`full-suite.xml:1438–1441`，第二例 `:1450–1454`）。
  而当前源码同一行是 `validate_control_expression_evaluations(semantics)`（`app/protocols/protocol_control_gate.py:3986–3990`）。行号完全相同、函数名不同 ⇒ 文本级单行改名。
- **证据（观察）**：`test_control_candidate_evaluation_scope` 在 XML 中 0 命中，但该文件现存在（`tests/v2/protocols/test_control_candidate_evaluation_scope.py`）⇒ 修复件（含新测试文件）晚于 08:25 的运行。
- **证据（观察）**：XML 内 `求值规格` 0 命中、`尚未提供求值规格` 0 命中、`MissingEvaluationSpec` 0 命中。即：**没有任何冻结证据记录过"缺少求值规格"这一新错误文本**。
- **推论**：XML 是 pre-fix 快照；任务书"old gate file 现在 29 个失败改报 missing evaluation specs"这一状态，在当前冻结证据集内**不可验证**。
- **建议（最小修复次序第 1 步）**：先冻结一份 post-fix 证据：`uv run pytest tests/v2/protocols/test_control_candidate_evaluation_scope.py tests/v2/protocols/test_slice58c_protocol_control_gate.py --junit-xml=artifacts/acceptance-20260916/postfix-gate.xml`，并把确切命令、节点集、随机种子写入 receipt。成本极低，且是"3 pass / 29 fail"能否采信的唯一路径。
- **不确定性**：我只能证明快照早于修复，不能反推修复后数字。pre-fix 的 29（下文 F6）与任务书 post-fix 的 29 数字巧合，**不构成同一组测试的证明**。

---

### F2 候选/正式校验分离本身经复核成立——请勿以吞掉 AttributeError 的方式"修"

被要求挑战的正是这一点，我按实际 schema 逐条对：

| 项 | 证据 | 判定 |
|---|---|---|
| 候选 schema 无控制级时间字段 | `ProtocolControlCandidateSemantics`（`app/domain/contracts/protocol_controls.py:1450–1469`）只声明 title/population/四层表达式/review_node_bindings/minimum_evidence/source_*/cross_source_relations，**无** `control_time_bindings`、**无** `control_time_constraint` | 分离有 schema 依据，不是权宜 |
| 正式 schema 拥有并自校验 | `ProtocolReviewControl`（`:1697`），字段 `control_time_constraint`（`:1724`）、`control_time_bindings`（`:1725`），模型校验器 `:1763` 调 `validate_control_time_bindings(self)` | 正式侧契约未被削弱 |
| 校验器拆分 | `app/domain/contracts/control_evaluation_spec.py:141–144`（绑定 + 表达式）vs `:147–155`（仅表达式层） | 语义清晰 |
| 发布边界两侧都跑 | `_validate_candidate`（def `:3805`）在 `:3988` 只做表达式；`_validate_control`（def `:4118`）在 `:4284` 做全套；`validate_protocol_control_publication`（def `:4448`）**同时**调用 `_validate_candidate`（`:4559`）与 `_validate_control`（`:4585`） | **发布检查无覆盖损失**，这是本次复核最关键的一条 |
| 无同类残留路径 | `compose_control_layers`（`app/domain/control_layer_evaluation.py:85–90`）先 `ProtocolReviewControl.model_validate` 再调绑定校验 ⇒ 不会被候选对象触发 AttributeError | 无第二处同型缺陷 |
| 候选侧要求未放松 | 表达式校验仍为 `require_explicit=True`（`:154`）；pre-fix 回溯在 `:143` 崩、从未走到 `:144` | 修复只是**解除遮挡**，未新增要求 |

- **结论**：pre-fix 的 AttributeError 是"同一校验器假设了正式专有属性"的缺陷；拆分是正确修法。**明确反对**任何 `try/except AttributeError`、`getattr(control, "control_time_bindings", ())` 之类兜底：那会让正式控件在缺失绑定时静默通过，直接违反 AGENTS.md 的"不得隐式补写"。
- **仍存在的缺口（我的挑战）**：拆分只修了这一处"校验器跨 schema 假设"，没有防止同类复现。建议加一条结构性守护测试：断言 `validate_control_expression_evaluations` 只读取候选 schema 已声明的属性（例如用 schema 字段集合与校验器访问集的子集断言），这样未来再加正式专有属性时会得到清晰失败而非 AttributeError。

---

### 族谱（按实际来源分类，含可核查计数）

总量的 86% 可由异常类消息定位：`message="<类名>…Error"` = **293/342**；`^E   …(Error|Exception)` = 346 行（含少量链式异常）。

| # | 族 | 规模 | 锚点证据 | 分类 |
|---|---|---|---|---|
| A | `wire_version 必须是 dnf-v18` | `^E   ValueError: …dnf-v18` = **34** | 抛出点 `app/agents/protocol_deconstructor.py:2750`；样本 `tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py:539,619`、`test_slice58_dnf_hydration.py:97,129,159,190,203,237,249`、`test_slice58_dnf_tristate_and_legacy_regressions.py:93` | **陈旧测试合同**（夹具版本常量），单点根因 |
| B | pydantic `ValidationError` | **95**（`message` 口径 96）；其中 `Field required` = 94 | 模型占比（按 E 行）：`ProtocolControlAgentWireObligationAtom` ≈37、`WireEvidence` ≈29（每条 3 个错误）、`WireConditionAtom` ≈26、`Wire` 1、`ProtocolSemanticDeconstructionCandidate` 1 | **待定**：夹具现代化为主，但含真实产品风险（见 F5） |
| C | `AssertionError` | **63** | 含 PUBLICATION_BLOCKED 信封断言（`full-suite.xml:119,135,142,149`）与 409 断言（`^E   assert 409 == 200` = 4，`full-suite.xml:120,136,143,150`） | 混合：发布阻断行为变更 vs 陈旧断言 |
| D | `ValueError`（其他） | **35** | 例：`缺少版本化逐事实考虑记录，不能当作完整枚举`（`full-suite.xml:279,306`）；`候选稿产生了新的完整性问题：TIME_ANCHOR_UNRESOLVED…OBSERVATION_POLICY_SOURCE_UNVERIFIED…`（`:341`） | 混合 |
| E | `AttributeError` | **32** | 其中 **29** 条经 `validate_control_evaluations`（`in validate_control_evaluations$` = 29 行，`full-suite.xml:1442…`）；另 3 条为 `evaluate_component` 接缝失效 | 见 F6 |
| F | `KeyError/TypeError` | 5 | `KeyError: 'project_id'`（`full-suite.xml:137`） | 见 F7（诊断质量） |
| G | `Failed: …` | 4 | `message="Failed` | 未深入 |
| — | 其余 | ≈49 | 消息不以异常类名开头 | **不可验证**（需解析器），已标注 |

---

### F3 最高杠杆且零产品风险：wire_version 夹具常量（≈34 个失败）

- **证据**：抛出点 `app/agents/protocol_deconstructor.py:2750`；测试侧样本见上表 A。
- **判定**：陈旧夹具。产品侧是一个显式版本闸门（"必须是 dnf-v18"），报错清晰、有稳定语义，不是缺陷。
- **下一步核查（具体）**：定位夹具中声明旧 `wire_version` 的常量（很可能集中在少数 helper），确认 34 个失败是否同源；同时确认 `dnf-v18` 提升是**有意契约变更**并有迁移说明——若有历史候选 payload 落库，硬版本闸门会阻断历史回放，需要产品决策（见 Q4）。

### F4 新增必填字段遮蔽后续校验（测试设计问题，非产品缺陷）

- **证据（`full-suite.xml:462–469`）**：`tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py:491`（`test_wire_partial_semantic_objects_are_rejected_precisely`）期望 `occurrence_window 的 duration`，实际得到
  `app.agents.protocol_deconstructor.ProtocolWireError: DNF_WIRE_MISSING_SEMANTIC_PROPOSITION: wire existence atom 缺少 semantic_proposition；…`（抛出链 `:2070 → :181`）。
- **判定**：**陈旧夹具 + 测试设计缺陷**，非产品缺陷。关键正面证据：错误边界完好——抛的是带稳定 code 的 `ProtocolWireError`，不是裸 pydantic 回溯。
- **建议**：给该组 partial payload 补 `semantic_proposition`（显式 null）；并把一条测试内的多个 `pytest.raises` 拆开（一个断言一个测试），否则"新必填字段"会持续遮蔽"被测守卫本身是否还生效"。这一族是"守卫顺序即产品行为"的典型，值得单独说明。

### F5 最大族（95 个 ValidationError）：不能默认判为陈旧测试

- **证据**：见族谱 B；`full-suite.xml:1433–1435` 为典型（`ProtocolControlAgentWireConditionAtom … evaluation / Field required`）。
- **分类冲突点（我的反对意见）**：这些模型同时是**真实 deconstructor 输出**的解析闸门。若 LLM 侧 prompt/schema 未同步产出新必填字段，真实运行会在解析处失败，而不是测试失败——那时这 95 个不是技术债而是发布阻断。
- **最小核查（三条，缺一不可）**：(1) 确认 wire schema 变更已同步到 deconstructor 的 prompt/内嵌 schema（`prompt_template_sha`/version 断言）; (2) 找**至少一次真实/金标端到端运行**能通过 `_parse_semantic_candidate`（`app/agents/protocol_deconstructor.py:3496`）的产物证据; (3) 若无该证据，把本族升级为 product-risk blocker，暂不现代化夹具。
- **不确定性**：我未读 LLM 适配器与金标产物（超出本次冻结读取范围），故只能提出核查项，不能下结论。

### F6 32 个 AttributeError 的两条实际来源

1. **29 个**：候选对象无 `control_time_bindings` ⇒ 已由 F2 的拆分修掉（pre-fix 计数，来源与任务书"29"数字巧合，见 F1 不确定性）。post-fix 预期转为 `CONTROL_EVALUATION_SPEC_INVALID`（`app/protocols/protocol_control_gate.py:3990` 的 ValueError 映射），**需 F1 的 post-fix 证据确认**。
2. **3 个**：`module 'app.services.eligibility_review_projection' has no attribute 'evaluate_component'`（`tests/v2/services/test_predicate_candidate_scope.py:29`）。该服务不再暴露 `evaluate_component`，调用已迁至 `app/services/component_review.py:13,41`。
   - **判定**：陈旧**测试接缝**，但同时是**验证空窗**——"一个组件的候选类别不得扩张另一组件词表"这一不变量当前**无人验证**（monkeypatch 目标已死，测试无从生效）。
   - **最小修复**：把 monkeypatch/断言重指到 `app.services.component_review.evaluate_component`，并确认新委托链上 `predicate_fact_type_aliases` 仍按组件隔离；然后在同一 PR 里保留该不变量。

### F7 诊断质量缺陷（会持续消耗复核轮次）：先取值后断言状态码

- **证据**：`tests/v2/api/test_protocols_api.py:659` 直接 `published.json()["project_id"]`，无 `status_code` 断言 ⇒ 失败报 `KeyError: 'project_id'`（`full-suite.xml:137`），而真实根因是同族发布阻断（同文件区块 `full-suite.xml:119–156`，体为 `PUBLICATION_BLOCKED … 完整性检查仍有 1 项阻止发布的问题 … blocking_count:1`）。
- **建议**：所有取 body 字段处先断言状态码并带 `resp.text`（`assert published.status_code == 200, published.text`）。这是把多个"不可解释失败"变成可直接读根因的**最便宜改动**。
- **附带观察**：`E   assert 'page-review-r3/v15' == 'page-review-r3/v13'`（`full-suite.xml:153`）属提示词版本常量漂移，同类陈旧常量，建议与 F3 一并批量处理。

### F8 迁移测试的共享 helper 单点根因（≈24–26 个失败）

- **证据（`full-suite.xml:2999`）**：`sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'action_requests.complete_processing_revision_id' could not find table 'evidence_processing_revisions'`，路径 `tests/v2/storage/test_migration_0008.py:228: in _upgrade_to_0007` → `MigrationManager(..., metadata=_phase3_metadata())`，helper 定义于 `tests/v2/storage/test_migration_0008.py:185`。
- **规模**：同族测试帧至少 `test_migration_0008`（5）、`test_migration_0008a`（8）、`test_migration_0009`（11）、`test_migration_0010`（≥1）。
- **判定**：测试侧 metadata 自相矛盾（FK 指向未定义表），不是迁移/产品缺陷；疑似**一个 helper 修好清掉整族**。
- **下一步核查**：确认四个模块共用 `_phase3_metadata()`；确认该 FK 不是来自产品侧 metadata（若来自 `app/storage/*`，则升级为产品侧发现）。

---

### 最小修复次序（建议，按风险/收益）

1. **冻结 post-fix 证据**（F1）——不先做这步，后面所有"通过/剩余"结论都不可审计。
2. **wire_version 夹具扫描替换**（F3，≈34）——单根因、零产品风险。
3. **semantic_proposition payload 补齐 + 断言拆分**（F4）。
4. **重指 `evaluate_component` 接缝并恢复不变量**（F6-2）——这会补回一个当前无人看守的不变量，优先级高于多数夹具修复。
5. **迁移 helper 补齐表定义**（F8，≈24）。
6. **状态码先行断言卫生**（F7）——让后续失败可读。
7. **ValidationError 族三问核查后再决定是否现代化**（F5）——这是唯一可能翻盘为"发布阻断"的族。
8. **校验器/schema 同步守护测试**（F2 缺口）——防止同类 AttributeError 复现。

### 我主动提出的反对意见 / 决策点

- **反对**：任何"吞 AttributeError"或给 `validate_control_time_bindings` 加 `getattr` 默认值的修法（会同时削弱正式控件；违反"不得隐式补写"）。
- **反对**：在 F5 三问未答前，把 95 个 ValidationError 统记为"陈旧测试"。这是我发现的最大未被任务书覆盖的风险。
- **反对**：用 pre-fix XML 的 29 去佐证 post-fix 的 29（F1）。二者数字相同不代表同组。
- **决策点**：29 个旧闸门测试的夹具，是逐个补 evaluation spec，还是统一改为复用 wire 构建器（推荐后者：单一测试数据源，未来契约变更只在一处失败）？

### 给 Codex 的有界提问（每条都给出安全临时路径）

- **Q1**：08:25 的运行是在 `_validate_candidate` 改动**之前**还是之后？我推断"之前"（帧行号相同、函数名不同、新测试文件缺席）。*临时路径*：按"之前"处理，先冻结 post-fix 证据。
- **Q2**：是否存在 post-fix 的 `test_control_candidate_evaluation_scope.py` + `test_slice58c_protocol_control_gate.py` 运行产物（3 pass / 29 fail）？若无，该断言只能标记为未验证。*临时路径*：不采信 29，只采信"分离结构成立"（F2）。
- **Q3**：本次运行是否用了与既往同一节点集/种子/顺序？XML 无 `<properties>`，插件与顺序来源**无法自证**；由于 F4/F3 这类族的失败形态取决于守卫顺序，顺序变更会改变族谱。*临时路径*：重跑时显式固定并记录 `-p no:randomly` 与节点集到 receipt。
- **Q4**：`dnf-v18` 硬闸门对**已落库的历史候选 payload** 是否有兼容/迁移策略？若无，历史回放或重新水合会被版本闸门阻断，属产品决策而非测试问题。*临时路径*：先只为新运行固定 v18，历史数据暂不重放，记录为已知限制。

### 我未能验证的事项（如实声明）

- 未能运行/未运行任何测试；"3 focused tests pass"与"29 剩余"均未由我复核。
- 未能用解析器做精确元素级聚合：≈49 条无异常类消息的失败、每模块精确失败数、xfail/skip 的逐条归属均**不可验证**（表头为准：342/11/4944）。
- 未读 LLM 适配器与金标产物，故 F5 只给核查项不给结论。
- 未查 git 历史（无 Bash），F1 的时间线由**行号+函数名+文件缺席**三重旁证推得，非版本控制直接证据。

**恢复点**：若需继续，同一会话内最有价值的两步是（a）若 Codex 提供 post-fix gate 运行 XML，我立即按其重算 29 的族与消息；（b）若授权读取 deconstructor 提示词/schema 与金标产物，我可把 F5 从"待定"收敛为"陈旧夹具"或"发布阻断"的确定结论。当前 workflow 仍是集中验收、非临床验收；`claims_complete=false`；最终临床/产品判定权在 Codex。
