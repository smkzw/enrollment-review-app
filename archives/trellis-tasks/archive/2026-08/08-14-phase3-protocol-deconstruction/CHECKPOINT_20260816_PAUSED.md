# Phase 3 无损暂停检查点（2026-08-16）

## 当前状态

- Trellis 任务：`08-14-phase3-protocol-deconstruction`
- 任务状态：`in_progress`
- 已完成切片：1、2、3
- 下一切片：4（流程节点、证据要求与发布事务）
- 当前代码基线：`e3dddb5 feat(protocols): complete phase 3 deconstruction core`
- 本次暂停前只重读了切片 4 范围和后端规范，未修改业务代码、数据库结构或接口。

## 已验收能力

1. 原始方案按内容哈希登记，结构提取与派生渲染物不可变，来源定位不会用猜测页面冒充精确来源。
2. 方案编号、正式版本、正式日期、项目代号和研究期别分别识别；模板版本不覆盖正式方案版本。
3. II 期与 III 期默认形成独立项目空间；单期投影不混入对侧期别比较文字。
4. Agent 前冻结官方父规则目录和基线及以前必做项目录，Agent 或修订不能增删目录成员。
5. 规则合同保留父子逻辑、AND/OR/NOT、指标、比较符、阈值、单位、时间锚点、例外、研究者复合判断和逐条来源。
6. 12 类确定性门禁可阻止零规则、编号/数量不一致、流程漏项、占位项、逻辑变异、来源不足及时间锚点丢失进入发布状态。
7. DeepSeek 会话支持持久历史恢复、同会话有限修复和指定父规则替换；空正文不会伪装成成功。

## 真实方案验收锚点

### MG-K10-SAR III 期

- 最终目录：`metrics/real-agent-acceptance/mg-iii/`
- 会话：`protocol-chat-d13b5ca3a69944b099912d92bc6f4671`
- 结果：IN 7、EX 16、基线及以前必做项 41。
- EX-04 正确保留“1 周内至少 4 天”的频次窗口。
- 唯一保留问题：EX-07w“6 个月内存在或疑似蠕虫感染”未明确回溯起点，保持 `TIME_ANCHOR_UNRESOLVED`；不得擅自替换为筛选日或随机日。

### CMS-D001 II 期

- 最终目录：`metrics/real-agent-acceptance/d001-ii/`
- 会话：`protocol-chat-0cf91707a73a40a4ad46964068ae336d`
- 结果：IN 6、EX 30、基线及以前必做项 50，全部门禁通过。
- EX-04 复发性带状疱疹为独立事件分支，正确保留“2 年内 2 次或以上”。

## 验证证据

- 最终全仓：`687 passed, 1 skipped, 7 warnings, 18 subtests passed`。
- 唯一跳过：`tests/test_phase_workflow.py:388`，原因是遗留 MG-K10-SAR/06003 OCR 缓存夹具不存在，与 V2 方案解构无关。
- 新鲜独立 `gpt-5.6-luna:max` 审查结论：`ACCEPT`。
- 两份源方案的哈希、大小和修改时间未改变。

## 下一步：切片 4

恢复后从 `implement.md` 的“切片 4：流程节点、证据要求与发布事务”开始，先冻结合同再编辑：

1. 从流程表、流程图和正文建立基线及以前 `WorkflowStage`，同名工作按研究期别和访视实例分开。
2. 生成规则事实要求、流程必做要求及无受试者 `EvidenceExpectation` 模板。
3. 实现草稿 revision、手工编辑、反馈分类、保存、取消/恢复和结构化差异；历史只追加，不物理删除。
4. 手工编辑和反馈不得增删冻结目录、改写流程节点，或用解释材料改变方案阈值/逻辑。
5. 实现发布事务、幂等、权威记录/清单/确认及新项目或新规则版本；冲突和失败不得覆盖正式版本。
6. 补 SQLite 事务回滚、任务检查点、重复发布、双标签页 revision 冲突和完整性哈希测试，再做全仓回归与独立审查。

切片 5 的 V2 API 和首次解构工作台尚未开始；前端视觉、多模型真实医学监查员端到端试用也尚未到执行时点。

## 恢复入口与保护边界

1. 先运行 `python3 ./.trellis/scripts/get_context.py`，读取本文件、`prd.md`、`design.md`、`implement.md` 和后端持久任务/数据库规范。
2. 运行 `git status --short`；以下两张截图是用户或并行任务改动，不得暂存、覆盖或回退：
   - `frontend/e2e/screenshots/uat-recorder-desktop-overview.png`
   - `frontend/e2e/screenshots/uat-recorder-e4-stop-banner.png`
3. 最终 MG/D001 验收目录、`page_locator_spike.json`、设计书、实施计划、任务文档和源方案必须保留。
4. `output/` 下旧临床项目备份和受试者资料未纳入本次清理；未经重新确认，不得因体积大而删除。

## 本次清理范围

- 删除 Phase 3 最终修复前的 63 个归档 Agent 中间文件，仅保留两份最终真实方案验收结果。
- 删除仓库源码和测试目录中的 Python 字节码缓存、`.pytest_cache` 及 Playwright `test-results`。
- 不删除虚拟环境、前端依赖、正式验收证据、源文件、旧临床数据或用户截图。
