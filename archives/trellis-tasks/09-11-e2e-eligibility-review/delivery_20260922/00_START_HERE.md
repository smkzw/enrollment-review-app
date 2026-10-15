# 0922V2 后续实施总入口

本包由 Codex 于 2026-09-22 对本地工程、GitHub 固定提交及 GPT Pro 专家包交叉审阅后形成。工程基线：`e7f34d0508c05481164cf13569f66ddf64e2e74f`。本轮只审阅与准备实施，不代表产品修复完成。

## 五分钟接手

1. 唯一实施目录：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。分支 `codex/phase5-clinical-facts-profile`。主 checkout 是旧版，禁止误改。
2. 读取最新全局/项目 AGENTS.md、`.trellis/workflow.md`，然后只读本文件、`../prd.md`、`../implement.md`、`02_EXECUTION_RULES.md`、`03_PLAN.md`。
3. 任务继续使用 `09-11-e2e-eligibility-review`，不新开重构项目。先核 `pwd`、HEAD、dirty 和当前实际服务归属；本文旧作业/PID不能授权终止服务。
4. 在 `04_WORK_PACKAGES.md` 找下一未完成包。只读该包列出的完整函数、相关消费者和对应专家条目，不每轮重读历史。
5. 使用 `06_MATERIALS.md` 找原件/代码/证据；实施完成后按 `05_ACCEPTANCE.md` 集中验收。唯一进度在 `../implement.md`。

## 文件导航

| 文件 | 用途 |
|---|---|
| `01_REVIEW.md` | 已核发现、专家意见裁决、审阅边界与停滞原因 |
| `02_EXECUTION_RULES.md` | 连续实施、验证节奏、最小改动和资源约束 |
| `03_PLAN.md` | 全交付范围、顺序、依赖和阻塞旁路 |
| `04_WORK_PACKAGES.md` | W0–W7 具体实施包、文件与交付证据 |
| `05_ACCEPTANCE.md` | Q1–Q3 集中检查与最终验收场景 |
| `06_MATERIALS.md` | 权威资料、固定 GitHub 链接、真实材料定位、命令 |
| `07_FORK_PROMPT.md` | 可原样发送给 fork 的持续实施指令 |
| `08_RETURN_TEMPLATE.md` | 暂停/交班/完工记录模板 |
| `09_REVIEW_EVIDENCE.md` | 本轮实际检查结果，不冒充临床验收 |
| `10_MODEL_AVAILABILITY.md` | 实测区分配置错配、缺会话头与上游故障；原始回执在同目录 |
| `../design.md` | 当前实现决策与共享合同 |

## 优先级和现行决定

- 用户 2026-09-22 要求优先于历史笔记；专家包是重点审阅证据，仍须对照真实实现，不自动获得执行/临床裁定权。
- 延续 V3：内置前置方案 Agent；官方条款和跨章要求共同发布；原图 + 主 OCR/可靠原生文字 + 必要的局部视觉/人工核实。不能再把所有事实必须双 VLM 一致作为默认。
- 医学经理工作稿与正式采用/签发分开：工作稿使用完整、同源、已核实的证据语义，不用伪签字，也不能用“未正式采用”挡住正常查看与处理问题。
- 本轮没有重新指定产品模型。fork 运行模型为用户要求的 `gpt-5.6-sol:medium`，这是开发者模型，不是产品读图配置。产品路由需核当前显式配置和已授权能力，不照旧聊天模型表擅换。
- 默认同树单写者，不启动第二套队列、通用多 Agent 框架、数据库或独立展示壳；利用既有持久 Job、ArtifactStore 和 API。
- 最终交付是正式入口完整可用，不是只修 R2 清单或只生成一份全未决报告。

## fork 的启动方式

建议在当前任务创建**同目录 fork**，将模型手动选为 `gpt-5.6-sol`、思考强度 `medium`，发送 `07_FORK_PROMPT.md`。本轮没有创建 fork 或更改会话模型。
注意宿主显示的当前cwd仍可能是主checkout；同目录fork不会自动切到本包worktree。接手者必须把工具workdir显式设为上面的唯一实施目录，或先在终端切换并核pwd/HEAD；不得仅凭“已fork”认定目录正确。
如果使用 worktree fork，仅从 HEAD 建树会漏掉本包未提交文档；必须先由用户决定提交或受控复制本包并核 hash。不得为方便交接自动提交/推送，也不要把资料、env、数据库一并打包。

新 fork 不应每包交完就结束：执行顺序已经给定，完成一包直接取下一包。只有真实需用户决定、所有可推进路径都被外部阻塞、用户要求暂停或达到完整交付标准时才结束。
