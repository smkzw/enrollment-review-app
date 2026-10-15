# 文档地图：本仓库所有材料的关系说明

> 本文件回答一个问题：仓库里这么多目录、文档、日志，彼此是什么关系、从哪份读起。
> 上传时间：2026-09-20。此后每次构建同步推送，本文件随材料演进更新。

## 一、这个项目是什么

临床试验入排审核系统：把试验方案（入选/排除标准）拆解成机器可判定的规则，把受试者原始资料（检验单、病历、邮件等）识别成结构化事实，再让规则去评价事实，产出带完整出处的资格审核报告。系统定位为本地单机、研究者自用、AI主导但最终判断权在人。

## 二、三条主链（读懂项目的工作主线）

| 链条 | 内容 | 状态（2026-09-20） |
|---|---|---|
| A 方案链 | 方案DOCX → 语义拆解 → 门禁审查 → 共同发布成正式规则集 | ✅ 已发布（rule_set rev=1，blocking=0） |
| B 资料链 | 受试者31001的5份原件24页 → OCR → 页级核对 → 双AI判读 → 事实归一化与发布 | ✅ 已发布（55条事实、1份受试者档案、136条资料期望） |
| C 审核链 | 判断检索 → 候选绑定 → 资格评价 → 审核报告 | ⏸ 机制全通，卡在绑定读取的模型输出篇幅（见下） |

## 三、从哪份文档读起（推荐阅读顺序）

1. **AGENTS.md**（仓库根）——项目边界与工作纪律：临床证据边界、产品定位、会商与调度规则。
2. **docs/PROJECT_CONTEXT.md**——项目当前上下文的权威综述。
3. **.trellis/tasks/09-11-e2e-eligibility-review/prd.md 与 design.md**——当前任务（V3分工）的产品需求与设计。
4. **.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md**——A/B/C三链分工的冻结文件。
5. **.trellis/tasks/09-11-e2e-eligibility-review/implement.md**——执行顺序表与逐步退出记录（做什么、做到哪）。
6. **.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260920_ABC_B_DONE_C_BINDING_LLM_BLOCKED.md**——最新无损暂停点：环境清单、接手第一步、已做未验证的修改。
7. **RETURN_A.md / RETURN_B.md**（同任务目录）——A链与B链的历史回执综述。

## 四、历史文档的谱系（按时间）

项目经历五轮任务阶段，全部保留在 `.trellis/tasks/` 下，旧的被新的承接但未删除：

| 任务目录 | 时间 | 内容 | 与当前的关系 |
|---|---|---|---|
| 08-12-enrollment-review-v2 | 08-12起 | 重构发现与总体设计 | 产出 docs/REARCHITECTURE_DISCOVERY_20260812.md 与 FINAL_DESIGN_20260812.md，是一切后续的地基 |
| 08-13-phase1-frontend-shell | 08-13起 | 前端外壳 | frontend/ 目录的由来 |
| 08-22-phase5-clinical-facts-profile | 08-22~09-19 | 方案拆解与临床事实（Phase 5全程，最大的一轮） | 数十份CHECKPOINT/HANDOFF记录了门禁演进、拆解切片、模型对比；当前A/B链能力都从这里长出 |
| 09-05-phase55-dual-vlm-page-review | 09-05起 | 双模型逐页判读（main-A/main-B读道、手写批注C道） | 页判读双道制的出处 |
| 09-11-e2e-eligibility-review | 09-11至今 | **当前任务**：端到端资格审核（V3分工A/B/C） | 上面三链的现状都在这里 |

另有 docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md（R3工程设计）与根目录 SYSTEM_REVIEW_REPORT.md（系统评审）。

## 五、目录速览

| 目录 | 是什么 | 备注 |
|---|---|---|
| app/ | 后端（FastAPI）：方案拆解、证据处理、事实发布、资格评价 | 运行于 127.0.0.1:8902 |
| frontend/ | 前端（React/Vite） | 5173 |
| scripts/ | 运维与启动脚本（含本地模型装卸） | |
| tests/ | 契约/回归测试（.trellis spec 对应各层规范） | |
| .trellis/ | 任务管理与分层编码规范（workflow.md、spec/、tasks/） | 历史任务全谱系在此 |
| context/ plans/ reviews/ metrics/ | 每个执行切片的四件套：上下文、计划、评审、度量 | 与08-22/09-11任务的切片一一对应 |
| runs/ | 真实运行证据：会商记录、验证、控制任务重放、历史审计 | |
| artifacts/ | 仅保留：MTPLX本地模型装卸日志（20260918/0919）、后端运行日志 | 重型历史工件（GB级模型对比/截图）未入公开库，见第七节 |
| docs/v2 | v2 API与数据合同文档 | |
| DOCUMENTS_MAP.md | 本文件 | |

## 六、运行入口（本机构建）

- 后端：`.venv/bin/python -m uvicorn app.api.v2.app:create_app --factory --host 127.0.0.1 --port 8902`，环境变量清单见 CHECKPOINT_20260920（密钥一律走 .env，不入库；模板见 .env.example）。
- 本地模型装卸：scripts/start_local_model_services.sh；属主清单 artifacts/mtplx-owned-runtime-20260919/owned-lifecycle-models.json。
- 测试：`.venv/bin/python -m pytest tests/v2/ -q`（分层规范见 .trellis/spec/）。

## 七、未入库的内容与原因

- **.env（真实密钥）与 data_v2/（受试者资料数据库、原件、页图、识别工件）**：前者是凭据，后者是临床原始材料与派生数据，均不入公开仓库。这是本项目AGENTS.md临床证据边界与数据治理决定的；如需另建私有库承载，另行确认。
- **artifacts/ 下GB级历史工件**（模型对比、接管快照、验收截图等约8.7GB）：属于一次性运行证据，公开库仅保留轻量日志。本机原件保留，未删除。

## 八、后续同步约定

当前分支 codex/phase5-clinical-facts-profile 已设置远端指向本仓库；此后每次构建在本分支提交并 `git push` 即同步。如需把 main 历史一并镜像，`git push <remote> main` 即可。
