# Phase 4 Slice 4.1 无损暂停检查点

记录时间：2026-08-19 12:18 CST

## 当前目标

按照已批准 Phase 4 计划建立受试者资料的不可变证据底座。当前只完成 Slice 4.0 能力基线和
Slice 4.1 领域合同/存储/API；不得把这些结果解释为上传、OCR 正式处理或证据工作台已完成。

## 工作区与状态

- 工作树：`.worktrees/phase4-evidence-ocr-v2`
- 分支：`codex/phase4-evidence-ocr-v2`
- Trellis 任务：`.trellis/tasks/08-19-phase4-evidence-ocr-v2`，状态 `in_progress`
- 代码尚未提交或合并；用户要求无损暂停，因此不进入 Slice 4.2。
- 主仓库和本工作树中既有用户改动不得重置或覆盖。

## 已完成并放行

### Slice 4.0

- 金标准、原生 PDF 真实坐标、四级诚实定位和 OCR 风险合同已建立。
- oMLX 隔离探针只证明 2 个合成视觉页在门禁下逐字回读一致，响应为 text-only。
- 响应中的模型名是 provider 自报；没有独立服务清单/启动日志，不能宣称实际模型身份或一般准确率。
- 扫描/照片没有真实机器坐标，因此不得绘制红框；PaddleOCR-VL 坐标路线未采用。

### Slice 4.1

- 冻结 SourceBlob、资料版本、元数据修订、快照成员/状态事件和 ReviewEpisode 指针合同。
- 实现六张 Phase 4 证据表 ORM、不可变仓储、作用域/前序链/继承/替代/集合哈希/no-op 校验。
- 实施 `0008_evidence_ingestion`，覆盖备份、升级、降级、恢复、WAL、外键和镜像一致性；含证据
  数据时拒绝降级，避免静默删除历史。
- 补齐受试者列表/创建和审核节点列表 API，使用中文错误信封并验证作用域。
- 新鲜独立 `gpt-5.6-luna:max` 检查者修复后裁决 Slice 4.1 停止点通过。

## 验证证据与边界

- 检查者修订前 Codex：V2 `900 passed, 58 warnings, 2 subtests passed`；目标 Ruff 和
  `git diff --check` 通过。
- 检查者修订后独立检查者：V2 `914 passed, 58 warnings, 2 subtests`；目标 Ruff、限定 Pyright
  0 error、编译和 `git diff --check` 通过。
- 暂停时 Codex 没有再次重跑检查者修订后的 914 项全量回归。恢复后必须先重跑，不能用检查者
  报告替代 Codex 的最终环境验证。
- 项目级 Ruff 仍有 895 项既有问题，目标变更文件通过；不得把既有全项目问题计为本切片新增。
- `subjects(project_id, subject_code)` 没有数据库级唯一约束，跨进程并发创建有残余风险；当前
  单机单用户不阻断 Slice 4.1，恢复后在后续迁移设计中明确处理。

## 明确未完成

- Slice 4.2 上传暂存、预览、取消、确认、幂等提交和前端三栏骨架。
- Slice 4.3 正式页产物、OCR 缓存、持久任务和 8 路真实推理准入。
- Slice 4.4 处理修订、定位/风险/校对、ActivationEvent 激活与回滚。
- Slice 4.5 完整证据工作台与 1080P/2K/4K 真实浏览器验收。
- Slice 4.6 三路独立视觉医学监查员试用。
- Phase 5 之后的临床事实、Patient Profile、入排判定、行动闭环和报告。

## 恢复顺序

1. 读取最新 `AGENTS.md`、本文件、`prd.md`、`design.md`、`implement.md` 和
   `docs/PROJECT_CONTEXT.md`。
2. 核对工作树、分支、未提交文件和 Slice 4.1 独立检查者最终修改，禁止重置用户改动。
3. 串行运行 Slice 4.1 目标测试、目标 Ruff、限定 Pyright、`git diff --check`，再运行
   `.venv/bin/python -m pytest tests/v2 -q`。
4. 结果与 914 项基线一致且无漂移后，补齐执行 review-gate/清理可再生执行日志；保留紧凑报告。
5. 再按 `implement.md` 启动 Slice 4.2。不得提前实现 OCR 正式持久化、激活/回滚或外部试用。

## 关键恢复文件

- `archives/execution/phase4-evidence-ocr-v2-slice41/phase4-evidence-ocr-v2-slice41/worker_01.md`
- `archives/execution/phase4-evidence-ocr-v2-slice41/phase4-evidence-ocr-v2-slice41/worker_02.md`
- `archives/execution/phase4-evidence-ocr-v2-slice41/phase4-evidence-ocr-v2-slice41/worker_03.md`
- `reviews/codex_execution_phase4-evidence-ocr-v2-slice41_review.md`
- `metrics/phase4-evidence-ocr-v2-slice41_execution_metrics.md`
- `research/slice4-real-omlx-probe.json`
- `research/slice4-omlx-gate-probe.md`
- `research/slice4-goldset-coordinate-spike.md`

## 暂停纪律

- 不启动服务、不派发新 Agent、不运行新临床资料、不删除正式证据。
- 已完成的独立检查者会话可以关闭；任务和工作树保持 `in_progress`，等待用户继续。
