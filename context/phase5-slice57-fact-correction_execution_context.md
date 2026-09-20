# Execution Context: phase5-slice57-fact-correction

Created: 2026-08-23 15:16:07
Objective: 实现 Phase 5 Slice 5.7：有理由的人工临床事实修订、可证明的影响范围与保守节点回退、不可变新事实/Profile revision、重启取消迟到结果和重复回调幂等，以及最小中文宽屏修订界面；不修改原 OCR、候选或旧事实，不进入 Phase 6/7 入排结论或 ActionRequest。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md`、`.trellis/workflow.md`、`.trellis/spec/backend/**`、`.trellis/spec/frontend/**`。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` §4.2、§4.3、§7.2、§7.3、§8，以及 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 5。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`，尤其 design §6 与 P5-AC08/P5-AC11。
- Slice 5.1-5.6 当前实现：`app/domain/contracts/facts.py`、`app/storage/facts_models.py`、`app/storage/fact_repositories.py`、`app/storage/fact_rule_link_repository.py`、`app/services/fact_publication_service.py`、`app/services/patient_profile_service.py`、`app/storage/patient_profile_repository.py`、`app/services/fact_normalization_job_service.py`、`app/workflow/{jobstore.py,runner.py}`、`app/api/v2/patient_profiles.py`、`frontend/src/api/patient-profile/**`、`frontend/src/pages/SubjectsPage.tsx`、`frontend/src/components/profile/**`。
- 当前测试与迁移约定：`tests/v2/**`、`frontend/src/**/*.test.tsx`、`frontend/e2e/**`、`app/storage/migrations/versions/0013_*` 至 `0016_*`。
- 不读取或修改工作树外的真实项目、原始方案、受试者资料、旧临床报告或生产数据库。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- 不修改源文件、原 OCR、校对原值、Normalizer 候选、既有发布事实/事件/暴露、冲突、期望或历史 Profile；修订只能追加新记录和新 revision。
- 允许修订 `fact / event / exposure` 三类 Profile 语义实体；冲突组和资料期望只能由新投影变化，不能被用户直接改写或“关闭”。
- 修订必须保存目标原实体、旧/新规范正文与哈希、理由、来源 locator、操作者、北京时间可回放的 UTC 时间、影响范围及局部/节点级依据。理由不得为空，定位必须属于同一冻结权威。
- 影响范围只允许沿显式 locator、文档版本、实体引用、FactRuleLink 和 Profile revision 反向索引传播；任一必要反向链缺失或无法证明闭包时，明确使用整个审核节点范围，禁止自由文本或相似度猜测。
- 新结果生成新实体 revision 和新 Profile revision；历史 Profile 继续按原 revision 完整读取。后续审核节点不得改写早期节点链头。
- 复用现有持久 Job/Step/Checkpoint/Lease/PreparedStepResult 和写栅栏；取消只在安全边界生效，迟到回包不能提交，重复请求/回调必须幂等。
- 本切片不生成入选/排除、通过/不通过、洗脱期裁决、ActionRequest、责任方任务或 ReviewRun 主结论。

## Ordered Dependencies And Write Sets

1. `worker_01` 先完成领域/迁移/仓储。可写：新增 `app/domain/contracts/fact_corrections.py`、新增 `app/storage/fact_correction_repository.py`、`app/storage/facts_models.py`、新增 `app/storage/migrations/versions/0017_*`，以及对应 `tests/v2/domain|storage/**`。不得修改服务、API、前端。
2. `worker_02` 在 worker_01 终局后执行。可写：新增 `app/domain/planning/fact_correction_impact.py`、新增 `app/services/fact_correction_service.py` 与持久任务服务、必要的 `app/api/v2/*` 注册/Schema、最小共享仓储查询扩展及对应后端测试。除修复 worker_01 明确缺陷外不改其合同/迁移。
3. `worker_03` 在真实后端合同稳定后执行。可写：`frontend/src/api/patient-profile/**`、`frontend/src/components/profile/**`、`frontend/src/pages/SubjectsPage.tsx`、`frontend/src/styles/profile.css`、相关组件/页面/E2E 测试。不得改后端。

## Done Signals

- 合同、迁移升降级和仓储证明历史不可变、定位同权威、理由必填、幂等与旧 Profile 回放。
- 局部影响范围与节点级保守回退均有确定性测试；重启、取消、迟到提交、重复回调和局部失败不产生重复实体/Profile 或永久处理中。
- 中文界面在提交前同时展示原值、原文来源、拟修改内容、理由和影响范围；提交后可回看旧/新修订，不出现程序员枚举或 Phase 6/7 结论。
- Codex 最终运行受影响层及全量回归，并在真实 1080P/2K/4K 浏览器中验收；worker 自报通过不构成完成。

## Work Items

1. 领域与存储：冻结人工事实修订合同、修订记录、旧值/新值/理由/定位/操作者/时间/影响范围，新增迁移和仓储，所有历史不可变且旧 Profile 可回放。
2. 影响与执行：基于 locator、文档、事实和 FactRuleLink 计算局部重算；无法证明时扩大到审核节点；复用持久 Job/Step/Checkpoint/Lease，覆盖取消、重启、迟到回包、重复回调和局部失败。
3. 用户界面：在 Patient Profile 提供最小中文事实修订入口，先核对原值、来源和影响范围，要求理由后提交；显示新修订与旧修订历史，不出现入排结论或程序员标签。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
