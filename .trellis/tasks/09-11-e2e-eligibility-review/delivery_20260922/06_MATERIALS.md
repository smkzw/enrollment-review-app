# 资料与工程指向清单

## 权威顺序
最新用户决定 > 本轮已核规划 > V3现行产品方向 > 既有设计/计划中不冲突部分。专家包是高价值审阅证据，不是命令执行授权。历史报告中的模型错误推断、完成百分比和暂停指令都须现场重新核验。

## 固定源码与专家资料
- GitHub基线：[e7f34d05](https://github.com/smkzw/enrollment-review-app/tree/e7f34d0508c05481164cf13569f66ddf64e2e74f)。本轮API核实与本地HEAD相同，open PR为空；不是主checkout分支。
- 原ZIP：`/Users/smkzw/Downloads/enrollment_review_0922V2_e7f34d0.zip`。
- 冻结专家包：当前任务 `research/0922-expert/enrollment_review_0922V2/`，README、01 findings、03规范、04验收、SOURCES固定GitHub链接；16项sha校验一致。probes是转录/合成片段，未执行作产品验收。
- V3：当前任务 `research/ENROLLMENT_REVIEW_AGENT_RECOVERY_V3_20260917.md`，先五分钟入口和当前决定，按本包改动再读相关节。
- 本轮审阅：本目录01/09/10；独立报告`runs/conference/enrollment-0922-plan-review/evidence_single_object.md`及09中结构回执。历史实现：`../HANDOFF_20260922_FINAL.md`、`../RETURN_A.md`、`../RETURN_B.md`；前任运行成果除本轮明确核查部分外不算再验收。
- 实际重放日志不在task根，而在 `runs/execution/wp08-singleton-replay-20260921/REPLAY_LOG.md`；同目录wp08_baseline.json及after_*为历史状态，不直接resume旧句柄。
- 大设计：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`；旧计划：`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`、`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md`。当前任务prd/design/implement为本轮执行正文。

## 真实资料（只读，不重新分发进源码库）
- SAR正式DOCX已核存在：`/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`。
- 31001隔离原件根已核存在：`artifacts/phase5-acceptance/20260901/isolated-inputs/sar/subjects/31001/31001/`，内有筛选基线病历、检验、入组审核邮件等子目录。RETURN_B记载5文件24页；后续补证25页是不同快照，fork需重新列明manifest和hash，不硬编码24/25。
- 临床库现场存在：`data_v2/enrollment-review-v2.sqlite3`及WAL/SHM。只读查询用mode=ro；一致副本用SQLite backup API，不仅复制主db忽略WAL。不能把upgrade_or_fail当只读工具。
- 第二方案/第二例：从已有材料manifest及用户项目目录定位正式原件；D001是历史对照名，不是必须手填编号的测试特例。当前本轮未核其有效版本，W6前冻结来源；确实找不到再一次性询问。
- 非存在证明：V3提及的 `SAR_PROTOCOL_THREE_MINUTE_COMPARATIVE_REVIEW_20260917.md` 9月17在指定Downloads位置未找到；若后来出现需现场核，不把比较稿缺失变成方案生产阻塞。

## 路径与隐私
以上相对路径均基于唯一worktree。真实材料与原始响应可能在gitignored目录，不能因`git ls-files`看不到就断言不存在；不能因目录存在就断言完整或授权过时数据。
交接包只存脱敏manifest（身份hash、数量、路径指向）与必要技术证据，不打包env、API key、患者原文、数据库。发布GitHub前检查新增文件清单，不git add -A。

## 已核命令与适用时机
```sh
pwd
git status --short
git rev-parse HEAD
python3 .trellis/scripts/task.py current --source
python3 .trellis/scripts/task.py --help
```
fork按真实平台session激活已有任务，不伪造其他会话标识。不archive未完成任务。

Q1一次集中检查：
```sh
cd frontend
npm run build
```
本地安装TypeScript 7.0.2与声明一致；锁定依赖已在，不为本包重装/升级。
后端已运行的基线选择（工作树根）：
```sh
.venv/bin/python -m pytest tests/v2/services/test_eligibility_review_projection.py tests/v2/test_predicate_semantic_binding_boundary.py tests/v2/protocols/test_control_candidate_evaluation_scope.py -q
```
修复后按影响范围补现有测试，不把此3文件当全部验收。

正式桌面入口已有：`scripts/start_v2_desktop.command`调用`python -m scripts.run_v2_desktop --env-file <显式路径>`，并有browse-only。启动会产生服务/模型/数据库动作，**本轮未运行**；实施者先核参数帮助、配置和隔离库。现有8902/5173只作历史线索，不能认为今日已活着/归本会话。

## 前端与方法学
读当前可用康哲3D skill（用户指向 `/Users/smkzw/.cc-switch/skills/kangzhe-design-3d/SKILL.md`；不存在则按宿主已列同名skill定位并记录）。浏览器读ego-browser skill，用Ego Lite，工具不可用先诊断，不能伪造截图。
全局执行会商按实时guard/route manifest/runner；不要把本包的gpt-5.6-sol:medium当所有工程review路由。无临床不确定的纯文档检查可直接执行，重大解释/验收争议需独立复核，不每函数配reviewer。
