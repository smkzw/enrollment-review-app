# V2 Phase 0 基线清单

**核验日期：** 2026-08-12

**工作区：** /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app

**文档状态：** 基线与边界记录，不代表整个 Phase 0 已完成
**本 Worker 文档写入范围：** 仅本文件和 DECISION_AND_REGRESSION_INDEX.md

## 1. 结论和状态语义

| 状态 | 含义 |
|---|---|
| 已观察 | 本轮命令、当前文件系统或现有源码直接支持的事实。 |
| 已冻结 | 用户、设计或会商已经确定，后续实现不得自行改写的边界。 |
| 待验证 | 尚未由本清单或独立 checker 证明；不得写成 Phase 0 完成。 |
| 历史记录 | 既有报告、测试或日志中的事实，只用于回归设计，不升级为 V2 业务真相。 |

本清单冻结 legacy 的可复现入口、回滚锚点、资产保护边界和当前运行证据。没有运行临床重审，没有删除或清理临床资产，没有接受整个 Phase 0、Phase 0.5 或后续重构。

## 2. Git 回滚锚点

### 2.1 已观察事实

| 项目 | 结果 |
|---|---|
| legacy 基线提交 | a02b8332421626dbaf88dad02bce9a8fc811c9ed（短号 a02b833） |
| 基线分支 | main |
| 基线提交主题 | chore: 冻结V2重构前基线 |
| 当前分支 | codex/v2-phase0-foundation |
| Trellis 初始化提交 | 4bf277bbc6f683d9cbba692d612983c3542b3f96（短号 4bf277b） |
| 首次 Phase 0 候选提交 | 97dbadd（随后由独立 checker 提出问题，需以 `git log` 查看修订后的当前提交） |
| 祖先关系 | a02b833 是当前 HEAD 的祖先；本轮未执行回滚。 |

a02b833 是 legacy 代码的回滚锚点，不是当前工作树所有文件的完整快照。首次记录本表时，V2/Phase 0 文件仍处于并行工作树；随后已进入 97dbadd 候选提交。独立 checker 对该候选提出默认测试入口、写入隔离测试、依赖记录和文档时态问题，因此 97dbadd 仅是历史候选，不代表 Phase 0 已接受。当前状态必须以 `git status`、`git log` 和 Trellis 任务状态为准。

### 2.2 复核命令

```bash
git show -s --format='%H%n%h%n%ad%n%s' --date=iso-strict a02b833
git show -s --format='%H%n%h%n%ad%n%s' --date=iso-strict HEAD
git merge-base --is-ancestor a02b833 HEAD
git status --short --branch --untracked-files=all
```

比较 legacy 基线与当前提交：

```bash
git diff --stat a02b833..HEAD
git diff --name-status a02b833..HEAD
```

只读检查回滚对象：

```bash
git show --stat --oneline a02b833
```

需要恢复时，应由拥有变更授权的人在确认工作树和备份后执行恢复；本 Worker 没有执行 reset、回滚、切换分支或删除操作。

## 3. 运行时与依赖证据

### 3.1 Legacy 实际运行时

已观察：scripts/run_enrollment_review_service.sh 将工作目录固定为本项目，并使用 /usr/bin/python3 -m uvicorn app.main:app。当前 output/runtime_state/port 为 8901，该端口有 enrollment-review 服务监听。根目录 run.sh 的默认端口 8900 是旧入口提示，不能替代当前实际服务证据。

```bash
/usr/bin/python3 --version
# Python 3.9.6

/usr/bin/python3 -c 'import sys; print(sys.executable)'
# /Applications/Xcode.app/Contents/Developer/usr/bin/python3

/usr/bin/python3 -c 'import app, app.main; print("app_import=ok")'
# app_import=ok
```

这里的运行时身份按启动脚本记录为 /usr/bin/python3；其解析后的实际解释器路径为 Xcode Python 3.9.6。后续命令不能仅凭 shell 中的 python3 名称判断环境。

### 3.2 Legacy 依赖可用性

本轮从同一解释器观察到：

```bash
/usr/bin/python3 -m pytest --version
# pytest 8.4.2
/usr/bin/python3 -c 'import fastapi; print(fastapi.__version__)'
# 0.128.8
/usr/bin/python3 -c 'import uvicorn; print(uvicorn.__version__)'
# 0.39.0
```

这只是当前 legacy 解释器的导入证据，不是 V2 依赖锁定或许可证验收。V2 依赖、版本和许可证已在独立决策文档中记录，并需由 Phase 0 checker 单独验收；不能把 V2 锁文件倒写成 legacy 基线。

### 3.3 环境误用边界

历史验证中曾有另一套 Python 因缺少 FastAPI 而失败。该失败是解释器/依赖环境误用，不是应用回归，不能替代 /usr/bin/python3 的基线结果。复核失败时必须先记录 sys.executable、Python 版本和 FastAPI 导入结果，再判断是否属于应用故障；不得把任意 Python 的导入失败写成 legacy 不可运行。

## 4. 测试基线

### 4.1 当前 legacy 测试结果

为独立确认 legacy 基线、不受 V2 新测试数量影响，legacy 测试使用实际运行时并显式指定文件：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -m pytest -q tests/test_phase_workflow.py
```

本轮实测结果：

- 收集：131 tests collected；
- 通过：130 passed；
- 跳过：1 skipped；
- 失败：0；
- pytest 报告耗时：4.29s；shell time 的 real 为 4.76s；
- 跳过原因：MG-K10-SAR/06003 OCR cache fixture not available；
- 警告：8 条，主要为 FastAPI on_event 弃用和本机 LibreSSL 兼容性提示。

因此本清单将“131 个 legacy 用例，130 个通过、1 个跳过”作为当前可复核表述。此前记录的 3.425s 是历史运行耗时，不作为当前性能承诺；测试耗时随解释器缓存、机器负载和测试集合变化。用户提供的“131 tests OK，skipped=1”在数量上对应上述 131 个收集用例。

收集命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -m pytest --collect-only -q tests/test_phase_workflow.py
```

### 4.2 编译检查

已验证的基线命令和结果：

```bash
/usr/bin/python3 -m compileall -q app tests scripts
# 通过
```

本 Worker 未为重新记录而再次执行该命令，因为 compileall 会生成或更新时间缓存文件，而本任务只允许写入指定的两个文档。

### 4.3 测试边界

现有 legacy 测试包含临时项目、审计记录、用户/中心状态和路径写入测试。临时项目多数有清理逻辑，但现有测试本身不是 legacy 只读写保护的证明；测试期间可观察到 _system/audit_ledger.jsonl 等运行资产被写入或重写。后续必须以独立 snapshot/写保护测试证明：V2 操作前后 legacy 项目、原始文件、旧报告和审计资产不被修改。

本轮没有运行全量临床项目、没有调用批量重审脚本、没有把测试输出当作临床结论。

## 5. 服务健康

### 5.1 当前服务

```bash
if [ -f output/runtime_state/port ]; then tr -cd '0-9\n' < output/runtime_state/port; fi
lsof -nP -iTCP:8901 -sTCP:LISTEN
curl --fail --silent --show-error --max-time 20 \
  http://127.0.0.1:8901/api/health
```

当前响应：

```json
{"service":"enrollment-review-app","version":"2.0.0","status":"ok","omlx":true,"deepseek":true}
```

这证明本地服务身份和两个依赖健康探针当前返回就绪；不证明任何受试者审核正确，不证明 V2 已接入，也不证明临床流程已验收。

### 5.2 服务日志边界

服务日志和历史会商日志只作为运行/决策证据，不作为临床事实来源。报告和本清单不复制日志中的密钥、凭证、病历原文或内部审计事件。

## 6. 主要目录与资产

本轮使用 du -sh 和文件计数进行只读清点：

| 路径 | 当前规模 | 角色与边界 |
|---|---:|---|
| projects/ | 约 3.5G，约 8,797 个文件 | legacy 项目、原始资料、OCR/审核产物和审计记录；只读回归资产，不删除、不迁移、不由 V2 写入。 |
| projects/D001-02-II/ | 约 2.9G | 大型 legacy 项目回归资产。 |
| projects/MG-K10-SAR-III/ | 约 553M | legacy 项目和历史验证资产。 |
| projects/MG-K10-SAR/ | 约 63M | legacy 项目和测试/回归资产。 |
| projects/D001-02-II-TEST/ | 约 21M | 历史测试项目资产；仍按只读回归锚点保留。 |
| output/ | 约 3.3G，约 3,290 个文件 | 历史报告、模型比较、视觉证据、staging 和恢复备份；不删除、不当作 V2 业务真相。 |
| output/d001_phase2_upload_staging/ | 约 2.5G | D001 阶段性回归/staging 资产；未完成哈希、可恢复性和替代证据核验前保留。 |
| output/deleted_project_backups/ | 约 734M | 可恢复备份；不是清理授权。 |
| logs/ | 约 18M，约 9 个文件 | 服务、会商和运行证据；不删除、不改写历史记录。 |
| context/、prompts/、runs/、reviews/、metrics/ | 约 1M 级 | 任务、会商、执行和验收证据；不作为临床原始事实，不清理。 |

规模命令：

```bash
du -sh projects output logs
du -sh projects/*
du -sh output/*
du -sh logs/*
```

明确冻结：projects/、output/、logs/ 及旧报告都是只读回归资产。体积大不是删除理由；本 Worker 未删除或清理任何文件。

## 7. Legacy/V2 写入边界

已冻结的边界：

1. legacy 项目、原始文件、旧 OCR、旧审核报告和审计链不作为 V2 可写数据库；
2. V2 新项目从方案输入重新创建，不导入旧项目结论作为业务真相；
3. V2 repository/storage 只接受 V2 root/database；任何 legacy 路径都必须显式拒绝；
4. 后续写保护测试须在 V2 操作前后对代表性 legacy 树做内容快照，并覆盖文件、目录、旧报告和审计记录；
5. V2 代码不得调用 legacy 的写 API；legacy 适配器只能提供显式只读读取；
6. 证据、事实、规则、Action 和 ReviewRun 的变更必须通过版本/快照/差异记录，不能静默覆盖历史。

这些是设计约束，不是本轮已通过的 V2 实现验收。V2 目录、最小导入、写保护测试、依赖 checker 和独立 Phase 0 checker 均仍需分别验收。

## 8. 可复现入口汇总

| 目的 | 命令 |
|---|---|
| 查看基线提交 | git show -s --format='%H%n%h%n%ad%n%s' --date=iso-strict a02b833 |
| 确认基线祖先关系 | git merge-base --is-ancestor a02b833 HEAD |
| legacy 测试 | env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q tests/test_phase_workflow.py |
| legacy 测试收集 | env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest --collect-only -q tests/test_phase_workflow.py |
| 编译检查 | /usr/bin/python3 -m compileall -q app tests scripts |
| 导入检查 | /usr/bin/python3 -c 'import app, app.main; print("app_import=ok")' |
| 服务健康 | curl --fail --silent --show-error http://127.0.0.1:8901/api/health |
| 资产清点 | du -sh projects output logs |

运行临床批处理、修改端口、重新生成报告、清理目录或改变 legacy 依赖前，必须重新确认授权和回滚边界。

## 9. 残余不确定性与未完成项

- 首次记录本清单时 V2 文件尚未提交；`97dbadd` 和后续修订已将其纳入 Git。当前工作树状态以实时 `git status` 为准，不从本段历史描述推断。
- legacy 测试仍有 1 个 OCR fixture 跳过项；“131 用例”不等于 131 个全部执行。
- compileall 的状态来自已验证证据，本 Worker 未重复执行；需要后续 checker 在允许写缓存的隔离环境中重跑。
- /api/health 只验证服务和依赖探针，不验证规则逻辑、证据定位、任务恢复或临床结论。
- 依赖许可证、V2 目录方向、写保护和清理 manifest 已形成候选证据；仍需独立 checker 复验后才能关闭 Phase 0。
- 现有测试对 legacy 审计资产有写入副作用，后续需要隔离测试 root 或增加可证明的只读测试夹具。
- 没有执行新的临床重审、浏览器 UAT、V2 端到端流程、数据库迁移或生产切换。

## 10. 首次独立检查后的修订

首次 Phase 0 候选 `97dbadd` 未被 checker 接受，随后完成以下修订：

- 默认 `uv run pytest -q` 同时收集 legacy 与 V2，不再以 `testpaths=tests/v2` 静默缩小测试范围；修订后为 136 通过、1 跳过。
- V2 写边界通过真实原子 writer 验证；V2/legacy root 重叠、实际 `projects/`/`output/` 目标、硬链接和符号链接均被拒绝，legacy 夹具快照不变。
- 依赖记录改为真实 npmmirror 锁文件来源，并补充官方交叉核验、维护、替代方案、数据外传和移除路径。
- 本节记录修订事实，不替代 checker 的复验和 Codex 最终接受。
