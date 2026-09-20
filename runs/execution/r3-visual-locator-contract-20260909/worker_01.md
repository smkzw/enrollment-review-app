# 执行输出: r3-visual-locator-contract-20260909 - worker_01

## 边界与上下文检查

- 工作目录绑定在授权的 worktree（`.worktrees/phase5-clinical-facts-profile`）内；未读取或修改任何生产路径、真实临床资料、外部服务。
- 初始读取集已全部读取：`context/r3-visual-locator-contract-20260909_execution_context.md`、`plans/codex_execution_r3-visual-locator-contract-20260909.md`。另按 Source Of Truth 授权读取：`app/domain/contracts/enums.py`、`app/domain/contracts/evidence_locator.py`、`app/domain/page_review_evidence_sources.py`、`app/services/page_review_visual_sources.py`、`app/domain/contracts/common.py`、`app/domain/publication.py`（canonical_hash）、`app/projections/clause_pack.py`（风格参照）、设计书 `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` 2026-09-09 视觉事实来源裁决节，以及测试夹具 `tests/v2/domain/test_page_review_contracts.py`、`tests/v2/domain/test_page_review_evidence_sources.py`、`tests/v2/domain/test_slice44_contracts.py`（节选）与 `tests/v2/evidence/test_locator.py`。
- 修改严格限于四个授权路径。两个契约文件在会话开始前已带有本分支的未提交改动（如 `REVIEW_NODE_DATE`、`SOURCE_LINE_TARGET_PREFIX`），已原样保留，未回滚任何既有用户改动。
- 未做存储/发布接线，未改旧修订语义，未接 `effective_text` 既有字段规则。

## 已执行工作

1. **`app/domain/contracts/enums.py`** — `LocatorSourceLayer` 新增 `PAGE_REVIEW_VISUAL = "page_review_visual"`，docstring 说明该层摘录哈希与页图哈希严格分立。已用 rg 确认全部既有用法为相等比较/字段类型，无穷举 switch，新增成员不影响旧代码路径。

2. **`app/domain/contracts/evidence_locator.py`** —
   - 新增冻结紧凑模型 `PageReviewVisualProvenance`：绑定 `source_set_id`（`visual-source-set:` 32 hex 模式校验）、`coverage_id`、`processing_revision_id`（既有完整处理修订，放在溯源绑定内，不动顶层 `processing_revision_id`）、`source_target_id`、`page_review_id`、`page_image_sha256`。
   - `EvidenceLocatorArtifact` 新增可选字段 `page_review_visual: PageReviewVisualProvenance | None`，`exclude_if=lambda v: v is None`（缺省时完全不出现在 dump/JSON，旧序列化逐字节不变）。
   - `validate_locator` 新增视觉层硬校验：该层必须携带溯源绑定；只能 `page_excerpt` 精度；必须 `DEGRADED` 且降级原因含中文；禁带 bbox/坐标系/sidecar/字符范围/`ocr_page_id`/顶层处理修订/`effective_text_sha256`/`match_confidence`；`source_text_sha256` 必须等于所选判读摘录的真实 sha256（防篡改后连锚点一起重算）；溯源内页图哈希 ≠ 摘录哈希（严格分立）；`source_target_id` 必须等于 `target_id`。非视觉层携带溯源绑定一律拒绝。既有 `effective_text` 规则一字未松。

3. **`app/projections/page_review_visual_locators.py`（新增）** — 纯投影 `project_visual_locators(source_set)`：入口按 `model_validate(model_dump())` 重验证（上游合同未冻结的同一防御姿势，与物化器一致）；每条已采信事实/手写来源的每条主读读道各产生一个定位工件，摘录逐字取自 `observation.region.excerpt`，两读道摘录不同则各自保留；定位 ID `"visual-locator:" + canonical_hash(...)[:32]`（来源集合、来源目标、读道、摘录哈希）；锚点用既有 `locator_anchor_hash`；时间戳取来源集合 `created_at`；固定 `DEGRADED` + 中文降级原因 + `match_confidence=None`；不物化、不写存储、不改输入；空来源集合返回空元组。导出 `visual_locator_id` 与算法版本常量。

4. **`tests/v2/domain/test_page_review_visual_locators.py`（新增）** — 23 个测试覆盖合同点：旧文本定位序列化不变（无新键 + round-trip 相等）；视觉层缺溯源拒绝；文本层带溯源拒绝；摘录哈希篡改即使重算锚点仍被拒（两种错误路径分别断言）；来源目标不一致拒绝；bbox/坐标系/sidecar/ocr_page_id/text_start/text_end/match_confidence=1.0/顶层处理修订/有效文本投影逐项拒绝；非 degraded 与非中文降级原因拒绝；投影含双读道、ID 全体互异、溯源六字段逐一绑定正确、锚点可重算一致、摘录哈希≠页图哈希；两读道不同摘录逐字保留不合并；两次投影 + 重验证输入投影恒等（确定性）；输入不改写（deep dump 对比）；定位 ID 对读道/摘录哈希敏感；空集合产出空元组；`model_copy` 绕过验证器的污染输入在投影入口被拒。

## 产物与证据

- 修改：`app/domain/contracts/enums.py`（+13/-4，仅 LocatorSourceLayer 块为本次改动）
- 修改：`app/domain/contracts/evidence_locator.py`（本次改动：hashlib/ConfigDict/ContractModel 导入、`PageReviewVisualProvenance` 入 `__all__`、`_excerpt_text_sha256`/`_contains_chinese` 助手、溯源模型、可选字段、验证块、模块 docstring 一行）
- 新增：`app/projections/page_review_visual_locators.py`（约 160 行）
- 新增：`tests/v2/domain/test_page_review_visual_locators.py`（23 测试，全合成夹具）
- 证据：`git diff` 均已人工核对；四路径 `git status` 为 2 M + 2 untracked，无其他路径变更。

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/domain/test_page_review_visual_locators.py -q` → **23 passed**。
- `.venv/bin/python -m pytest tests/v2/domain/test_slice44_contracts.py tests/v2/evidence/test_locator.py tests/v2/domain/test_page_review_evidence_sources.py tests/v2/services/test_slice44_locator_service.py tests/v2/evidence/test_slice44_locator_engine.py tests/v2/projections/test_evidence_expectations.py tests/v2/domain/test_fact_evidence_closure.py -q` → **159 passed**。
- `.venv/bin/python -m pytest tests/v2/services/test_fact_normalization_source_adapter.py tests/v2/services/test_fact_normalization_persistence.py tests/v2/agents/test_evidence_normalizer_adapter.py tests/v2/domain/test_fact_batch_orchestration.py tests/v2/storage/test_slice44_repositories.py tests/v2/storage/test_fact_repositories.py tests/v2/services/test_fact_publication_service.py -q` → **360 passed**。
- 合计 542 passed, 0 failed（全部合成数据）。rg 确认 `LocatorSourceLayer` 无穷举匹配，新增枚举成员对既有门禁/服务/存储测试无回归。

## 阻碍或缺失环境

- 无阻塞。`.venv` 内无 ruff 且 pyproject 无 lint 配置，故未跑静态检查（如 Codex 要求可指定工具）。
- 设计决策记录（供 Codex 验收裁量，推断性内容）：视觉层 `disambiguation` 固定取 `unique_match`——语义类比既有 "text_range + unique_match + degraded" 组合（身份精确、无坐标），模块 docstring 已明确声明它只表示"定位身份由读道与摘录哈希唯一内容寻址"，不代表做过检索消歧或页上无重复文本；未取 `repeated_text_degraded` 以免对页文本做未验证的"重复"断言，未取 `not_found` 因 page_excerpt 合同禁止。

## 重跑请求或下一步

- 无重跑请求。诚实声明剩余未接部分（按合同明确不在本次范围）：类型化视觉溯源尚未接入存储持久化/回读、事实门禁（`LOCATOR_AND_TEXT_HASH`）与发布闭包、Normalizer 候选输入、Profile/原件 UI 消费；源集合内容寻址不等于来源真实性，后续仓储消费方须按仓库记录重新核对权威绑定与原判读记录。
