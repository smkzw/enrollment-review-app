# Journal - codex (Part 1)

> AI development session journal
> Started: 2026-08-18

---

## Session 10: Phase 5 Slice 5.2 确定性门禁

**Date**: 2026-08-23
**Task**: Phase 5 临床事实与 Patient Profile
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成不调用模型的候选级确定性门禁、Phase 4 定位/原文/OCR 风险闭包、跨调用批量
去重与冲突编排，并把每项门禁结果与受影响范围收敛为可持久合同。

### Root Causes And Fixes

- 否定词与被断言对象必须建立直接语义关系，不能以同句共现替代；沉默、缺页和邻近
  否定不生成否定事实。
- 事实身份新增被断言对象，事件身份新增去重后的引用事实对象；候选、发布、仓储和读回
  使用同一身份语义，避免不同检验项目或不同临床事件错误合并。
- 运行只接受成功调用和完整处理修订，冻结权威元组与当前活动指针均需复核；Slice 5.2
  不伪造事务发布门成功。
- 不回改既有 `0013`；以 `0014` 收紧断言对象非空约束，遇历史空值拒绝猜测并恢复。

### Verification

- Codex 聚焦 `222 passed`；全量 V2 `1854 passed, 1 skipped, 139 warnings, 2 subtests passed`。
- `compileall`、`git diff --check`、Trellis validate 通过；项目未直接安装 Ruff，独立 Trellis
  核查完成限定 Ruff/mypy、历史迁移与同基线全量测试并无未闭合问题。

### Boundaries And Next Step

- 仅 Slice 5.2 放行；未调用真实模型、未发布事实、未生成 Profile、未新增 API/UI 或入排结论。
- 下一安全动作是 Slice 5.3 Evidence Normalizer 与可恢复持久运行；5.8 才执行三路指定模型的
  真实项目浏览器试用，测试角色继续与执行/会商角色分离。



## Session 1: Phase 3 Slice 6 完成与无损暂停

**Date**: 2026-08-18
**Task**: Phase 3 Slice 6 完成与无损暂停
**Branch**: `codex/phase3-slice6-exec`

### Summary

完成重新解构、八类差异、局部反馈修订、编辑边界、发布交互和宽屏真实 HTTP 验收；独立 Luna 终局 ACCEPT。

### Main Changes

- 修复任务初始化竞态、稳定来源对齐、例外时间语义、手工来源冻结、局部修订范围、全局身份闭包和前端严格差异解码。

### Git Commits

(No commits - planning session)

### Testing

- [OK] V2 746 passed；Vitest 258 passed；build 通过；Playwright 256 passed/41 skipped；真实 HTTP 三宽度 3 passed。

### Status

[BLOCKED] **共享代码与确定性回归已完成；真实模型父级验收受 MTPLX 服务端错误阻断**

## Session 9: Phase 5 Slice 5.1 合同与权威存储基座

**Date**: 2026-08-23
**Task**: Phase 5 临床事实与 Patient Profile
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成 5.0 基线与 5.1 合同/持久化基座。候选与发布实体物理分离，所有发布对象冻结方案、规则、审核节点、活动证据快照和完整处理修订权威元组；旧占位事实表保持只读。

### Root Causes And Fixes

- 初始 worker 结果未直接接受。独立复审发现运行权威未绑定发布、断言哈希未核对定位、候选正文未持久化、事件无法表达独立起止与持续状态，均在共享合同/仓储层修复。
- Trellis 全量检查继续发现候选缺少调用归属、规范化列可在列表查询前隐藏镜像漂移、多态定位/规则链接缺少真实父外键、数值和记录时间边界不完整；已增加候选 `call_id/candidate_kind/created_at`、先解码后筛选、组合外键/判别约束及相邻合同校验。
- 事实的断言对象与 AssertionBasis 必须一致，断言原文哈希必须等于 Phase 4 locator 哈希；事件/暴露/冲突只能引用同一不可变权威元组下成员事实的定位闭包。

### Verification

- Codex 聚焦合同/仓储/历史迁移：`129 passed`。
- Codex 完整 V2：`1735 passed, 1 skipped, 139 warnings, 2 subtests passed`；唯一跳过为既有 oMLX 探测工件缺失。
- `compileall`、`git diff --check`、Trellis task validate、迁移/ORM parity、含数据降级恢复、legacy 隔离和 governed execution audit 通过。
- 未安装或配置 `ruff/mypy/pyright/basedpyright`，未为本切片新增依赖。

### Boundaries And Next Step

- Slice 5.2+ 尚未实现：确定性候选门禁、真实 Evidence Normalizer、事实发布编排、Patient Profile API/UI、ReviewRun 和入排结论均未提前放行。
- 下一安全动作：提交 Slice 5.1 后开始 5.2，以结构化候选 fixture 实现页覆盖、定位/哈希、极性、单位、日期、来源、重复和冲突门禁；失败候选不得生成空 Profile。
- Phase 5 终局独立测试路线按用户最新要求固定为 Cursor CLI `auto`、Pi `cms-router/minimax-m3(high)`、Pi `opencode-go/ox-alpha-free`，测试与执行/会商角色分离，待 5.8 再做真实项目端到端试用。

### Next Steps

- 按用户要求暂停；恢复后从 Slice 7 清洁 V2 数据目录真实方案验收开始，不启动 Slice 8。

## Session 2: Phase 3 Slice 7 真实方案验收与无损暂停

**Date**: 2026-08-18
**Task**: MG III / D001 II 清洁全流程验收
**Branch**: `codex/phase3-slice7-real-uat`

### Summary

完成 MG III 与 D001 II 原始方案的真实持久任务、规则/流程/来源核对及浏览器验收；D001 正式发布，MG 对未命名时间锚点诚实阻断。

### Main Changes

- 修复跨休眠任务租约、反馈修订防回退、门禁缓存版本、频次/指标分型、资料时效/事件窗分型、恢复 revision 生命周期和前端规则问题归属。

### Testing

- [OK] V2 765 passed / 2 subtests；Vitest 267 passed；build 通过；真实 HTTP 三宽度 3 passed。

### Status

[OK] **Slice 7 completed; paused before Slice 8**

### Next Steps

- 从 `CHECKPOINT_20260818_SLICE7_COMPLETE_PAUSED.md` 恢复，先审阅/提交 Slice 7，再在清洁数据根启动三路独立视觉医学监查员试用。


## Session 3: Phase 3 方案解构终局验收与归档

**Date**: 2026-08-19
**Task**: Phase 3 方案解构终局验收与归档
**Branch**: `codex/phase3-slice7-real-uat`

### Summary

完成切片8-9共享机制修正、真实方案终局验收、两路独立医学监查员视觉复测、全量回归与阶段清理；D001 II已发布，MG III因EX-07s未命名回溯锚点保持阻断，下一阶段进入受试者资料摄取与证据标准化。

### Git Commits

| Hash | Message |
|------|---------|
| `94c8625` | (see git log) |

### Status

[OK] **Completed**


## Session 4: Phase 4 证据快照与 OCR V2 最终规划

**Date**: 2026-08-19
**Task**: Phase 4 证据快照与 OCR V2 最终规划
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

从 Phase 3 归档基线恢复，完成领域存储、旧 OCR 来源保真、上传前端和外部候选审计；收敛 10 项需求、13 项验收标准及 6 个实施切片。任务保持 planning，等待用户审阅后再启动 Slice 4.0。

### Main Changes

- 建立独立 Phase 4 Trellis 子任务、worktree、工作流上下文和实施/检查清单
- 冻结补充资料/完整资料快照、内容哈希去重、页级 OCR、诚实定位、风险校对与持久恢复边界
- 将 Patient Profile、入排判断、批量报告和真实临床结论明确留给后续阶段

### Git Commits

| Hash | Message |
|------|---------|
| `75544f3` | (see git log) |

### Testing

- [OK] task.py validate：implement 15 项、check 10 项，全部通过
- [OK] git diff --check 通过；主仓库用户改动未触碰

### Status

[OK] **Completed**

### Next Steps

- 等待用户明确批准最新 Phase 4 规划；获批后运行 task.py start，从 Slice 4.0 金标准与布局能力试验开始

## Session 5: Phase 4 批准与 Slice 4.0 启动

**Date**: 2026-08-19
**Task**: Phase 4 证据快照、上传与 OCR V2
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

用户批准最终规划；任务进入 `in_progress`。补充冻结右栏原始资料连续滚动、真实坐标红框和无坐标诚实降级合同，并按执行图启动 Slice 4.0 能力基线。

### Main Changes

- PRD/设计/实施计划新增原始资料连续滚动、证据跳转、真实红框缩放映射和禁止伪框验收
- 将遗留停止点从 P4-AC01–AC12 修正为 P4-AC01–AC13
- 当前实施工单只覆盖金标准、页图/坐标、OCR 风险与采用决策，不提前进入迁移或正式持久化

### Status

[IN PROGRESS] **Slice 4.0 running through the declared primary route**

### Next Steps

- 等待首个实施会话终态；由独立检查者复测量化门槛。通过后才进入 Slice 4.1。

## Session 6: Phase 4 Slice 4.0-4.1 验收与无损暂停

**Date**: 2026-08-19
**Task**: Phase 4 证据快照、上传与 OCR V2
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成 Slice 4.0 能力基线和 Slice 4.1 领域合同、六表仓储、0008 迁移及受试者/审核节点 API。
新鲜独立检查者修复并发去重、不可变事件/成员校验、降级保护和作用域问题后放行。用户要求
无损暂停，因此未进入 Slice 4.2。

### Testing

- Codex 检查者修订前：V2 900 passed；目标 Ruff、diff check 通过。
- 独立检查者修订后：V2 914 passed；目标 Ruff、限定 Pyright、编译、diff check 通过。
- 恢复后先由 Codex重跑修订后的全量回归，再启动 Slice 4.2。

### Status

[PAUSED] **Slice 4.1 accepted; Slice 4.2 not started**

### Next Steps

- 从 `CHECKPOINT_20260819_SLICE41_PAUSED.md` 恢复并执行记录中的五步恢复顺序。

## Session 7: Phase 4 Slice 4.3 页产物与识别底座

**Date**: 2026-08-19
**Task**: Phase 4 证据页产物、OCR 缓存与持久流程
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成 0009、不可变页/OCR/处理修订仓储、逐格式分页、内容寻址工件、原生 PDF 文本坐标、
扫描页纯文字识别和分阶段请求/结果适配；尚未进入页级执行器与共享 8 路门禁。

### Root-Cause Repairs

- 删除失败页全零哈希、1×1 尺寸和虚构旋转；允许同页不同失败历史并存。
- OCRPage 追加写，成功缓存单独唯一；同快照允许多个处理修订。
- 晚到提交改为同事务条件写门禁；OCR 输入严格绑定已存页图哈希。
- TXT 保留原文无伪坐标；DOCX/DOC 身份隔离转换元数据噪声；同一页只决定一次路线。
- 页工件身份/数据库唯一键纳入渲染、解码和坐标变换版本。
- 用户可见文本去除技术异常、provider、text-only、适配器和推理措辞。

### Testing

- [OK] 聚焦 141 passed。
- [OK] V2 全量 1187 passed, 58 warnings, 2 subtests passed。
- [OK] Ruff、Pyright、git diff --check。

### Status

[IN PROGRESS] **Slice 4.3 底座已验收；页级执行与恢复工作包待实施**

### Next Steps

- 执行 worker_03：页租约、共享 oMLX 8 路门禁、渲染背压、晚到拒绝、恢复/取消/限定重试和 SSE。

## Session 8: Phase 4 Slice 4.3 最终验收

**Date**: 2026-08-19
**Task**: Phase 4 证据页产物、OCR 缓存与持久流程
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成页级持久执行、共享 oMLX 8 路准入、租约心跳/代次/晚到拒绝、限定重试、取消、恢复和只读进度；真实合成 OCR 与多进程并发通过，Slice 4.3 放行。

### Root-Cause Repairs

- 统一应用与 oMLX 桌面服务实际端口，模型移入真实扫描根并验证服务清单与启动日志。
- 生产响应严格核对模型身份、结构和非空文本；错误响应原文持久化但不进入成功缓存。
- 修复完成/失败与取消竞态、取消后快照投影、重试统计重复和进程死亡恢复。
- 删除 Slice 4.3 越界风险扫描；无坐标继续不画红框，风险/校对/激活留给 4.4。

### Testing

- [OK] 聚焦 172 passed；V2 1233 passed, 58 warnings, 2 subtests passed。
- [OK] 真实顺序探针 2/2；真实并发 12/12，峰值 8，租约残留 0。
- [OK] Ruff、限定 Pyright、启动脚本语法、git diff check。

### Status

[OK] **Slice 4.3 accepted; Slice 4.4 next**

### Next Steps

- 从 `0010_evidence_locator_corrections` 开始 Slice 4.4；先冻结定位、风险、校对、活动指针和全状态矩阵的详细合同，再实施。
- CodeBuddy hy3(max)、Pi minimax-m3、Grok Build 4.6 medium 的视觉医学监查员端到端试用继续保留到 Slice 4.6。
## 2026-08-20 Phase 4 Slice 4.4 WP-44A accepted

- 独立复核先后拒绝根记录自证闭包、任意定位锚点、链分支、历史回放被当前链头破坏、当前校对/被提及资料可遗漏、同一原文范围多根校对和可选定位读取少做来源复核。
- 修复采用共享不变量而非个例补丁：新建完整修订验证全部当前集合，历史读取验证冻结集合；校对 occurrence 单根单后继；完整修订根/页/关联同保存点；定位绑定精确页产物与同源文本。
- 最终聚焦 `225 passed`，全量 V2 `1361 passed, 2 subtests passed`，Ruff/Pyright/diff check 通过；fresh-context Sol 终局 `ACCEPT`。WP-44B 已解锁，WP-44C/D 仍按串行顺序阻塞。

## 2026-08-20 Phase 4 Slice 4.4 WP-44B accepted

- 独立 Sol 会话第一轮拒绝重叠 occurrence、被提及资料链和默认激活/仓储旁路；第二轮继续发现陈旧 READY 候选可直切权威指针而候选不进入 ACTIVE。两轮都按共享系统不变量修复，不加项目特异规则。
- 最终唯一激活仓储入口校验候选冻结修订号，并在同一保存点写事件、成对指针和候选 ACTIVE 状态；候选状态故障会连同首次快照启用整体回滚。
- 被提及资料保留唯一链头、确定性来源、用户复核、触发定位和非空操作原因；风险种子分母固定为 26/13/10/23。
- Codex 聚焦 `209 passed`，全量 V2 `1455 passed, 130 warnings, 2 subtests passed`，静态检查通过；独立第三轮 `ACCEPT`，无未闭合 P0/P1/P2。WP-44C 已解锁，WP-44D 仍阻塞。

## Session 10: Phase 4 Slice 4.4 WP-44C accepted

**Date**: 2026-08-21
**Task**: Phase 4 证据接口、当前版本与应用错误边界
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成页/校对/风险核对/完整修订/激活回滚/被提及资料接口和 current 指针投影。独立 Sol 首轮拒绝三个 P1，修复后同会话终局接受。

### Root-Cause Repairs

- 重复启用当前成对版本统一返回结构化 409，不新增事件、幂等记录或审核节点修订。
- 被提及资料的已提供关系在服务与仓储双层要求同作用域且属于当前活动快照，拒绝跨受试者和非成员资料。
- API 错误映射器只消费应用错误；上传内部异常在公共服务边界转换为固定中文错误，不泄露路径、SQL、哈希或内部类型。
- 旧测试不再断言内部异常；全量回归发现的旧“先写非成员、后由完整修订拒绝”语义已前移为写入即拒绝。

### Testing

- [OK] 聚焦 39 passed；API/services 335 passed。
- [OK] V2 1537 passed, 130 warnings, 2 subtests passed。
- [OK] Ruff、项目虚拟环境 Pyright、git diff check。
- [OK] fresh-context Sol 同会话终局 ACCEPT，无未闭合 P0/P1/P2。

### Status

[OK] **WP-44C accepted; WP-44D unlocked**

### Next Steps

- 仅实施 WP-44D 中文核对闭环前端；连续原件滚动与完整真实红框体验继续留在 Slice 4.5。

## Session 11: Phase 4 Slice 4.4 final acceptance

**Date**: 2026-08-21
**Task**: 持久候选构建与中文识别核对闭环
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成 WP-44C-R/WP-44D。构建从 HTTP 同步执行改为原子排队、冻结输入和后台持久执行；前端可恢复候选、持续轮询、保留冲突输入，并隔离旧候选晚到结果。

### Root-Cause Repairs

- 候选冻结校对、风险核对、资料元数据和被提及资料输入，排队后新增记录不被旧候选吸收。
- READY/ACTIVE 候选重放直接返回原完成检查点；进程在候选就绪与任务检查点之间死亡时不会重复生成。
- 新候选返回时立即更新当前候选与本地锚点；旧恢复和旧轮询落地前双重核对，404 不误删新锚点。
- 冲突区用户语言统一为“系统当前记录”，清除“服务端”工程术语。

### Testing

- [OK] 后端全量 1543 passed, 130 warnings, 2 subtests passed。
- [OK] 前端 41 files / 336 tests；生产构建通过。
- [OK] 证据工作台 Playwright 1080P、2K、4K 共 6 passed。
- [OK] Ruff、项目虚拟环境 Pyright、git diff check。
- [OK] 同一 fresh-context Sol 会话终局 ACCEPT。

### Status

[OK] **Slice 4.4 accepted; Slice 4.5 next**

### Next Steps

- 实施连续原始资料滚动、文件/页/文本/原图统一选择状态和真实 bbox 缩放红框；无 bbox 继续只展示中文降级定位。
- 完成 P4-AC01 至 P4-AC13 后，再按既定路线开展 CodeBuddy、Pi、Grok Build 三路独立试用。

## Session 12: Phase 4 Slice 4.5/4.6 immediate lossless pause

**Date**: 2026-08-21
**Task**: 连续原始资料、真实标注、持久任务详情与三路独立试用
**Branch**: `codex/phase4-evidence-ocr-v2`
**Pause reason**: 用户要求立即无损暂停，后续在同一 Codex 任务中恢复。

### Completed Before Pause

- Slice 4.5 的连续原始资料滚动、文件/页/识别文本/原图联动、真实坐标红框与无坐标诚实降级已实现并完成本地验证。
- 持久证据任务中文详情、任务深链、证据页入口和帮助页已补齐；持久任务首屏不再显示演示任务的“继续未完成事项”。
- 本地确定性验收已覆盖 P4-AC01 至 P4-AC12：后端 V2 全量 `1546 passed, 130 warnings, 2 subtests passed`；前端 `45 files / 344 tests passed`；证据工作台 Playwright `15 passed`；生产构建、限定 Ruff/Pyright 和 `git diff --check` 通过。
- 静态检查曾误用不存在的 `.venv/bin/ruff` 与未绑定项目 Python 的全局 Pyright，产生伪失败；正确方式为 `uvx ruff` 和 `uvx pyright --pythonpath .venv/bin/python`。

### Independent UAT State

- CodeBuddy `hy3(max)`：连通性成功，但正式任务因非交互权限未能操作浏览器，只形成静态/源码审阅；提示真实浏览器缩放尚未被现有 CSS 布局压力矩阵直接覆盖，不能作为完整端到端验收。
- Pi `cms-router/minimax-m3`：在独立端口启动真实前后端并创建干净 V2 数据，发现生产前端的项目/受试者/审核节点基线仓储仍默认使用 Phase 1 stub，而证据仓储使用真实 HTTP。真实受试者无法由前端进入证据工作台，stub 受试者又会被真实后端拒绝。该问题是 P4-AC13 的系统级阻断，Phase 4 尚未放行。
- Grok Build `grok-4.6:medium`：首次正式输出仅为起始语，运行记录为 `cancelled`，不能作为验收。已按同一会话发起续跑，用户暂停时停止本地运行；可恢复会话 ID 为 `5dbfce0f-a5e8-4dd6-a249-d86c4fba4e39`。
- 三路产物位于 `runs/conference/phase4-slice46-independent-uat/`，提示词位于 `prompts/conference/phase4-slice46-independent-uat/`。Pi 的干净环境报告位于 `runs/conference/phase4-slice46-independent-uat/scratch/pi_minimax/REPORT.md`。

### Exact Resume Anchor

1. 先确认工作树、服务和会商进程状态，不重派新的 Grok 会话。
2. 使用 `--resume-session 5dbfce0f-a5e8-4dd6-a249-d86c4fba4e39` 恢复 Grok 同一会话，提示词为 `prompts/conference/phase4-slice46-independent-uat/uat_grok_followup.md`，输出仍写入 `runs/conference/phase4-slice46-independent-uat/grok.md`。
3. 核实 Pi 指出的混合仓储根因，规划并实施“生产默认 HTTP、stub 仅显式演示/测试模式”的修复切片；不得用项目特异补丁绕过。
4. 修复后重跑后端、前端、构建、1080P/2K/4K 浏览器验收和三路独立 UAT，再判断 P4-AC13 与 Phase 4 是否放行。
5. Phase 4 未放行前不得进入 Phase 5；本次暂停未执行阶段清理，避免删除尚待复核的 UAT 证据。

### Pause Confirmation

- 已确认没有 `uat_grok_followup`、对应 conference runner 或 Grok 会话的本地活动进程。
- 未继续修改产品代码、未清理证据、未进入下一阶段。

## Session 13: Phase 4 R4 后系统修复与无损暂停

**Date**: 2026-08-21 15:51 CST
**Branch**: `codex/phase4-evidence-ocr-v2`

- 用户明确纠正：会商与测试可以是不同角色。后续固定为只读会商顾问和隔离环境真实试用者两条独立证据链。
- R4 根因修复覆盖跨上传方式重复集合、补充资料旁路核对沿用、风险扫描时机、自动真实定位、全页任务进度和前端完成状态表达，不以单个受试者或单个测试环境打补丁。
- 合成 PDF 的康熙部首来自 Chromium 字体映射。LibreOffice 初次重建消除异常字符，但暴露 CSS Grid 不兼容和中文日期断行；最终改为两列表格及 ISO 日期，达到 1 页、异常字符 0、关键句 6/6，并通过高分辨率视觉检查。
- 前端全量 `372 passed`、生产构建通过；后端聚焦回归通过。全量后端先后暴露三处旧测试将相同集合当作新补充版本的假设，均已按真实业务语义修正。最后一次全量回归因用户暂停在约 9% 主动中断，不能记作通过。
- 暂停时已关闭所有本任务 R3/R4/final 临时服务，没有测试进程。完整恢复说明见任务目录 `CHECKPOINT_20260821_1551_PAUSED.md`。

## Session 14: Phase 4 Slice 4.5 终局与 R3 独立复测裁决

**Date**: 2026-08-21 22:25 CST
**Branch**: `codex/phase4-evidence-ocr-v2`

- 逐份核对 CodeBuddy `hy3(max)`、Pi `cms-router/minimax-m3(high)`、Grok Build `grok-4.6(medium)` R3 报告；三路测试角色与执行/会商角色保持分离，未替换路线。
- 用真实截图确认 Grok 报告的 1080P 短文本红框压字，改为外侧描边和透明内部；同时从通用定位列表过滤纯标点、收拢空白资料追踪登记表、修正受试者/中心分隔及“原件可查看”业务措辞。未接受范围外 1366×768 阻断意见。
- 聚焦回归 `55 passed`；前端全量 `382 passed`；生产构建通过；stub 证据流程 `15 passed`；真实后端三档宽屏 `3 passed`。目视复核 1080P 和 4K 最终截图，红框不再遮字、页面无横向溢出。
- 清理根目录 R3/UAT 临时截图、Playwright 临时结果和最终构建前截图；保留三路报告、提示词、金标准、最终宽屏截图和决策记录。
- P4-AC13 尚未满足“每名测试者在隔离清洁库完成创建/删除项目与受试者和量化无辅助全流程”。任务不归档、不提交 Phase 4 终局、不进入 Phase 5。恢复锚点为 `CHECKPOINT_20260821_2225.md`。

## Session 15: Phase 4 P4-AC13 测试路线纠正

**Date**: 2026-08-22
**Branch**: `codex/phase4-evidence-ocr-v2`

- 用户将第三名测试者由 `pi/opencode-go/ox-alpha-free(high)` 替换为 Pi/oMLX `Qwen3.8-27B-oQ8e-fp16-mtp(medium)`；另外两路保持 Cursor CLI `cursor-grok-4.6(medium)` 与 Pi `cms-router/minimax-m3(high)`。
- 已统一 `prd.md` 与 `implement.md` 的 P4-AC13/Slice 4.6 路线，删除待执行清单中的上一轮 CodeBuddy/Qwen3.8-Max 残留。旧 `ox-alpha` 输出仅保留为历史失败证据，不计入当前验收。

## Session 16: Phase 4 终局验收与归档准备

- 指定三路 Cursor CLI `cursor-grok-4.6(medium)`、Pi `cms-router/minimax-m3(high)`、Pi/oMLX `Qwen3.8-27B-oQ8e-fp16-mtp(medium)` 已完成连通性和隔离真实项目试用；测试角色与会商/执行角色保持分离。
- 终局系统修复覆盖处理中快照任务深链、关键校对最小持久范围、半开区间边界、风险修订隔离、批量聚合查询和严重整页重复风险关闭条件。独立 checker 首轮发现 N+1 后完成批量修复，fresh-context 终审又发现 `OUTPUT_REPETITION` 可被普通阅览误关，修复后结论为 `ACCEPT`。
- 最终验证：后端 `1633 passed, 139 warnings, 2 subtests passed`；前端 `49 files / 416 tests passed`；生产构建通过；1080P/2K/4K Playwright `9 passed`；真实 D001 隔离库可从证据页进入对应持久任务详情。
- 已清理可再生缓存、旧轮次测试目录及 42 MB 等大体积原始模型输出，`runs/` 从约 360 MB 降至约 45 MB。首次清理因 zsh 的 `path`/`PATH` 绑定在删除前失败，未损失文件；后续禁止用 `path` 作为 shell 变量名。
- 完成记录见 `CHECKPOINT_20260822_PHASE4_COMPLETE.md`。Phase 5 唯一安全输入为已激活的不可变证据快照和完整处理修订；不得读取候选、失败或旧修订。
- 本地 Qwen 指定路由已完成真实连通性检查，测试完成后已卸载；后续正式试用继续遵守与产品 OCR 串行、完成后卸载的约束。


## Session 7: Phase 4 证据工作流终局验收与归档

**Date**: 2026-08-22
**Task**: Phase 4 证据工作流终局验收与归档
**Branch**: `codex/phase4-evidence-ocr-v2`

### Summary

完成不可变证据快照、两种上传、OCR、校对、定位、风险核对、恢复和宽屏证据工作台的 Phase 4 验收；三路指定模型完成隔离真实项目试用，独立终审 ACCEPT。

### Main Changes

- 修复处理中快照任务深链、最小校对范围、半开区间覆盖、修订隔离、批量风险聚合和严重整页重复关闭语义。
- 清理旧轮次缓存与大体积原始输出，并固化 Phase 4 完成检查点。

### Git Commits

| Hash | Message |
|------|---------|
| `b750dda` | (see git log) |

### Testing

- [OK] 后端 1633 passed；前端 416 passed；生产构建通过；1080P/2K/4K Playwright 9 passed。
- [OK] 真实 D001 隔离库证据页可进入准确的资料处理详情，fresh-context 独立检查 ACCEPT。

### Status

[OK] **Completed**

### Next Steps

- 新建 Phase 5 任务，仅以已激活的不可变证据快照和完整处理修订作为临床事实抽取入口。


## Session 8: Phase 5 临床事实与 Patient Profile 最终规划

**Date**: 2026-08-22
**Task**: Phase 5 临床事实与 Patient Profile 最终规划
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

从 Phase 4 终局建立 Phase 5 隔离任务；完成代码现状审计、双路独立规划会商、PRD/设计/分片实施计划与 Trellis 上下文；修正活动处理修订错链、候选/发布混用、定位权威、沉默/否定、冲突和 Phase 6/7 越界；任务保持 planning，等待用户明确批准。

### Git Commits

| Hash | Message |
|------|---------|
| `ad7113a` | (see git log) |

### Status

[OK] **Completed**

## Phase 5 Milestone: Slice 5.3 Evidence Normalizer 与持久运行

**Date**: 2026-08-23
**Task**: Evidence Normalizer 真实传输、确定性规划和可恢复持久任务
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成候选/未解决项唯一输出、逻辑文档连续页组、Phase 4 定位局部原文输入、系统字段回填、配置内容绑定，以及可恢复运行/调用/检查点/租约。真实模型第一次语义失败被拒绝，根因修订后才通过最小闭环。

### Root-Cause Repairs

- 定位摘要内容而非仅定位编号进入调用和运行幂等哈希；模型不再自行生成系统身份、时间或来源哈希。
- 中文资料类型/来源方进入确定性来源强度派生；沉默不能制造伴随字段缺口，清晰数值不能只写未解决项。
- 终败重试在同一事务重开领域运行；提交回调失败立即终败并回滚领域副作用与检查点。
- 未解决项与候选同受租约写栅栏保护并持久化；检查点回放重新校验活动权威和持久清单。

### Testing

- [OK] 聚焦扩展 348 passed。
- [OK] V2 全量 1972 passed, 1 skipped, 139 warnings, 2 subtests passed。
- [OK] 真实 oMLX 合成探针修订后闭合；fresh-context 独立复核原阻断复现全部消失。
- [OK] compileall、git diff check、Trellis task validate。
- [INFO] 仓库未配置 Ruff/Pyright 可执行入口，未临时安装依赖；独立检查者的临时 ad-hoc 静态工具结果不作为项目门槛。

### Status

[OK] **Slice 5.3 accepted; Slice 5.4 next**

### Next Steps

- 事务发布事实/事件/用药暴露；构建精确 FactRuleLink 双向索引；投影五类资料覆盖和细分缺口原因。
- 不提前实施 Patient Profile UI、ReviewRun、入排结论或 Phase 5.8 三路真实项目试用。

## Phase 5 Milestone: Slice 5.4 事实发布、规则索引与资料期望

**Date**: 2026-08-23
**Task**: 事务发布事实/事件/暴露、精确规则关联及资料期望投影
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成规范化运行的原子发布：同一事务内发布去重后的临床事实、事件、用药/治疗暴露、未解决冲突、定位链接、规则双向索引及资料期望；任何必要输入不完整或投影失败均回滚全部副作用。

### Root-Cause Repairs

- 候选显式携带冻结资料要求编号；规则索引只按精确要求身份和事实类型关联，不解析自由文本或阶段描述。
- 当前阶段只取权威审核节点；同阶段存在多个工作节点时拒绝猜测。同期客观结果必须来自当前中心，外院或来源不明结果不提升来源强度。
- 时间不重叠的重复测量、用药或治疗方案变化保留为纵向历时信息；仅时间重叠或时间未知且语义值不兼容时形成并列冲突。
- 冲突检测原先能识别事件和暴露，但存储只接受事实成员；新增 `0016` 和两张类型化成员表，从合同、仓储到迁移完整保存三类同类型冲突。
- 新增迁移最初污染了 0008/0008a 历史 metadata 快照；根因是后续表排除清单未随迁移扩展。补齐清单并写入后台质量规范。
- `member_kind` 列有数据库默认值，但 0013 旧事实冲突 payload 没有新增字段；读取若直接取旧路径会误报镜像漂移。改为对照合同解码默认值，并增加旧正文回放测试。
- SQLite JSON 数值可能把 `5.0` 读为 `5`，日期列也可能与 ISO 字符串比较；共享镜像比较器现在保持布尔值严格区分，同时容忍等值数值和日期/时间表示。

### Testing

- [OK] 受影响聚焦组合回归 326 项通过；新增旧冲突正文兼容及事件/暴露冲突定向回归通过。
- [OK] 0013/0014/0015/0016 迁移 20 项通过；0008/0008a 历史迁移快照 16 项通过。
- [OK] 更新后 V2 全量 `2040 passed, 1 skipped, 139 warnings, 2 subtests passed`，耗时 505.59 秒。
- [INFO] 唯一跳过为既有 Phase 4 oMLX 真实探针工件未提供；本切片不含 Patient Profile 页面，未制造视觉验收结论。

### Status

[OK] **Slice 5.4 accepted; Slice 5.5 next**

### Next Steps

- 实现不可变 Patient Profile revision、13 条泳道、后端首屏突出集合及历史 revision 查询。
- 提供真实 HTTP API、严格运行时解码、陈旧/生成中/失败状态和 Phase 4 locator 深链。
- 在 5.6 之前不切换 fixture 页面；在 5.8 之前不启动 Cursor/MiniMax/OX Alpha 真实项目视觉测试。

## Phase 5 Milestone: Slice 5.5 Patient Profile API 与投影

**Date**: 2026-08-23
**Task**: 不可变 Patient Profile、13 条泳道、真实 HTTP API 与证据深链
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成冻结权威下的 Patient Profile revision、当前链头/历史/指定修订读取、13 条主题泳道、确定性首屏突出集合和真实 HTTP API。每条 Profile 响应同时提供经 Phase 4 读取服务重验的资料版本、页码、定位精度与可回放摘录；没有真实坐标时不伪造红框数据。

### Root-Cause Repairs

- 初版 API 只有定位编号，无法让界面直接核对资料版本、页码和定位精度。新增批量定位读取服务，并严格限定在 Profile 冻结的完整处理修订内；缺失或越界定位大声失败。
- Phase 4 与 Profile 各自复制定位 DTO 映射会造成标签和坐标语义漂移，现统一复用共享映射器。
- 稳定身份原先包含泳道，后续运行只改变泳道即可重复发布同一语义事实/事件。发布服务现对同一冻结权威的既有实体做跨运行泳道冲突校验。
- 工作流补跑提示文件位于主提示目录，首次治理审计报未登记角色；证据未删除，已归入对应 `followups/` 子目录后审计通过。

### Testing

- [OK] 本切片组合回归 `111 passed`。
- [OK] 500 事实 API 回归 `1 passed`，`26.63s`。
- [OK] V2 全量 `2144 passed, 1 skipped, 139 warnings, 2 subtests passed`，`647.19s`。
- [OK] `compileall`、`git diff --check`、Trellis validate 与 Hermes 执行审计。
- [INFO] 唯一跳过为既有 Phase 4 oMLX 真实探针工件未提供；`compileall` 仅保留既有 `app/models.py:88` 转义警告。

### Status

[OK] **Slice 5.5 accepted; Slice 5.6 next**

### Next Steps

- 将 fixture Patient Profile 页面切换到真实 HTTP repository，fixture 仅保留隔离测试入口。
- 实现适合 1080P 至 4K 宽屏的首屏重点、全量历时信息、冲突并列和右侧原件滚动定位；只有真实 bbox 才画红框。
- 完成组件测试、构建和 1080P/2K/4K Playwright 验收后，才进入 5.7；不提前启动 Phase 5.8 三路独立试用。

## Phase 5 Milestone: Slice 5.6 宽屏 Patient Profile 界面

**Date**: 2026-08-23
**Task**: 真实 Profile 页面、原件回源与宽屏视觉验收
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

生产受试者页已接入真实 Patient Profile HTTP repository，首屏严格使用后端重点集合，展开后保留 13 条完整泳道。事实、事件和冲突可在右侧连续原件中回源；只有真实、已核验 bbox 绘制单一红框。

### Root-Cause Repairs

- 拆分“发热”事件与血压事实定位，防止测试 fixture 用错误证据链掩盖语义错链。
- 将原图解码、红框与预期原文目标相交纳入门槛，不能再以“页面有框”代替证据正确。
- 真实 Chrome 缩放发现 200% 时旧媒体查询把原件移到下方；调整为隐藏次要导航、保持 Profile/原件并列，原件内部再适配单列。
- 清除常驻 preview 与构建产物交叉污染造成的假失败，并把原子 E2E 启动要求写入质量规范。

### Testing

- [OK] 前端 `57 files / 479 passed`，生产构建通过。
- [OK] 完整 Playwright `280 passed, 50 skipped`，无失败。
- [OK] 真实 Chrome 100%/150%/200% 缩放均验证宽度、DPR、原图解码、目标红框、并列布局和无横向溢出。
- [OK] 后端同一基线 `2145 passed, 1 skipped, 139 warnings, 2 subtests passed`；唯一跳过为既有 Phase 4 oMLX 探测工件缺失。

### Status

[OK] **Slice 5.6 accepted; Slice 5.7 next**

### Next Steps

- 实现有理由的人工事实修订、影响范围追踪和不可变修订历史。
- 证明局部重算边界，无法证明时保守扩大到审核节点，并覆盖取消、迟到回包、重启与重复回调。
- 不提前启动 Phase 5.8 三路真实项目独立试用，不生成入排主结论。

## Phase 5 Milestone: Slice 5.7 人工事实修订与增量重算

**Date**: 2026-08-23
**Task**: 有理由的事实修订、局部影响范围、不可变档案历史与宽屏修订交互
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成事实修订预览、确认、持久任务执行、完整语义快照、影响范围、重算与新档案版本绑定。修订前档案和定位保持可回放；新档案只追加，不覆盖既有版本。

### Root-Cause Repairs

- 生成后档案 revision 与修订提交绑定，并验证新实体和提交定位确实存在于该档案；不允许绑定修订前 Profile。
- 定位页码、资料版本、页产物和处理修订再次交叉复核；展示层也拒绝在身份不一致时声称精确定位。
- 查看原文不卸载修订草稿；持久任务未终结时阻止关闭，避免轮询被卸载后用户长期看到旧档案。
- 会商指出的摘录缺字、失败页无恢复入口、宽屏信息单列堆叠、重复阶段文案和重复断言均在共享组件/fixture 修复。
- 全量 E2E 首轮因摘录从“血压”纠正为“基线血压”暴露旧精确文本断言。确认页面、定位详情和红框一致后，将测试收紧到定位摘录元素，而非回退正确数据。

### Testing

- [OK] 后端同一最终基线 `2255 passed, 1 skipped, 139 warnings, 2 subtests passed`。
- [OK] 前端 `60 files / 493 passed`；生产构建通过。
- [OK] 完整 Playwright `283 passed, 50 skipped`，覆盖 1080P、2K、4K，无失败。
- [OK] 六张 Profile/证据面板截图按原始尺寸逐张检查；单真实红框、连续原件、失败页恢复指引和流体宽屏布局成立。
- [OK] `compileall`、`git diff --check`；最新会商为 `kimi-code/k3-256k high`，无 fallback。

### Status

[OK] **Slice 5.7 accepted; Slice 5.8 next**

### Next Steps

- 先冻结 Slice 5.8 的隔离数据目录、代表受试者与病例级核对清单，再分别进行 D001 II、MG-K10-SAR III 真实输入闭环。
- 测试者继续使用单独声明的测试路线；执行/会商模型只做实现与顾问审查，不能替代真实浏览器端到端测试者。

## 2026-08-24 Slice 5.8 结构化输出运行修订与无损暂停

- 最新执行路线经实时 guard 选择为 `codex-subagent/codex/gpt-5.6-luna:max`。同一 session `01a02ff6-afbf-7011-8176-d05274fc34bb` 完成五轮修订，无 fallback；本轮没有启动会商或独立测试者。
- D001 真实运行一在 `artifacts/phase5-acceptance/20260823/data-wire-rerun-20260824` 暴露 16K 输出截断和可空语义字段；运行二在 `data-wire-rerun2-20260824` 暴露混合节点 Schema 无法表达谓词/逻辑互斥；运行三在 `data-wire-rerun3-20260824` 暴露 `exists` 仍可携带值，说明比较符与值没有在 Schema 层同构约束。三次均失败，不得计入验收。
- 第四轮后的直接首批探针约 159 秒返回完整三条规则，但因孤儿 `p2-sex` 被拒绝；同会话定向修复约 146 秒后通过。该证据证明图校验和修复路径有效，但不等于完整项目通过。
- 第五轮把谓词拆成存在性、标量、集合三类不相交节点数组，逻辑节点独立；系统合并后再做统一图验证和领域水合，不使用 `oneOf/anyOf/allOf`，保持 oMLX 8192 token、temperature 0、SDK `max_retries=0` 和应用层有限重试。
- Codex 父进程已复核 80 项聚焦协议测试、Python 编译及定向差异检查；执行器报告完整协议测试 425 项通过。第五轮真实 oMLX 尚未复跑，因此 Slice 5.8 仍为进行中。
- 暂停时停止临时 8912 后端；保留三个失败数据目录、runner 报告和 stdout 作为根因证据。4174 前端与 8001 oMLX 为既有环境，不由本轮关闭。
- 恢复入口：先读 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260824_STRUCTURED_OUTPUT_PAUSED.md`；新建第四个隔离数据目录，先跑 D001 第一批真实探针，再决定是否完整重跑。后续还需改善终败中文诊断、评估全任务截止时间，完成 D001/MG 病例核对与三路独立测试者验收。

### 恢复后立即暂停补记

- 第五轮 D001 首批真实 oMLX 探针已在 140.025 秒返回，但领域解析拒绝：原子条件同时携带单段/多段原文定位；一个 `ALL/ANY` 只有一个子表达式。严格 wire Schema 仍未完整表达领域互斥与最小基数，这是共享合同缺陷，不是 D001 特异内容问题。
- 原始回包与摘要保存在 `artifacts/phase5-acceptance/20260824/probe-wire-v5/`，旧数据库保持只读。用户要求立即无损暂停，因此未做修复、重跑、完整流程或独立测试。
- 下次恢复先修 wire Schema/提示词/水合合同并增加通用回归，再用新探针目录重跑 `IN-01/IN-02/IN-03`；当前 Slice 5.8 继续保持 `in_progress`。

## 2026-08-24 10:45 `dnf-v1` 实施立即无损暂停

- 完成引用图根因复盘与三份 Luna max 独立设计复核，一致选择无引用 `dnf-v1`；设计 review-gate 通过并归档，v5-v9 保留。
- 实施 worker_01 完成候选/修订共用严格 Schema 与中文合同，报告 `20 passed`；worker_02 完成确定性 DNF 水合、原子 NOT、系统身份、重复/空组/旧图/复杂度拒绝，报告 `29 passed`。
- 用户在 worker_03 迁移旧测试和运行全协议回归期间要求“立即无损暂停”。已向 runner session `35805` 发送 Ctrl-C，退出 130，无残留子进程。worker_03 报告仍是 `PENDING`，其中断前测试改动未验收。
- 未运行完整 `tests/v2/protocols`、未填实施 review/metrics、未过实施审计/清理、未调用真实 oMLX。恢复见 `CHECKPOINT_20260824_DNF_V1_IMPLEMENTATION_INTERRUPTED.md`，先完成当前活动，不提前进入 D001/MG/浏览器/独立测试。

## 2026-08-24 `dnf-v1` 实施恢复与验收

- 只恢复原 Worker 03，同路线完成测试迁移和反例矩阵；三个执行角色均由 guard 审计为完成，无 fallback。
- 主控复跑时发现来源片段顺序曾在稳定身份中被排序，已从共享归一化机制修复并加回归，避免协议上位限定语和结尾条件被错当成无序集合。
- 聚焦测试 `105 passed`；完整协议测试 `450 passed, 58 warnings`；编译、差异检查、执行审计和 review gate 通过。过程文件已归档。
- 产品内置本地 LLM/VLM 不继承执行/会商路由的 32K 注入限制；后续按真实模型能力、硬件和准确性决定上下文策略。
- 下一步为新隔离 D001 第一批真实 oMLX 探针；在一次接受且语义核对通过前，不启动完整项目、浏览器或三路独立测试者。

## 2026-08-24 Phase 5.8b/5.8c 全文控制 Agent 与发布门禁

- 最新 guard 路线 `codex-subagent/codex/gpt-5.6-luna:max` 完成三名串行执行者，无模型替换；经多轮同会话修正后建立冻结批次、独立控制 Agent、系统水合和完整发布门禁。
- 主控拒绝了模型拥有稳定身份、关键词改变来源顺序、候选借用同批其他原文、自由文本审核节点、单数候选链接及调用者独立候选绕过完整批次等共享缺陷。
- 聚焦 `73 passed`，协议全量 `561 passed, 58 warnings`；公开导入和编译通过。D001 真实只读清单保留 1,689 单元与表 5 全部 13 行。
- 802 个 `UNKNOWN/MIXED` 单元证明全文不漏项但期别语义仍未闭合。下一步必须做通用期别适用性解析和 D001 II 人工矩阵，不能把未知默认成共享，也不能在发布门禁中补猜。

## 2026-08-24 Phase 5.8c-1 DOCX 标题结构恢复

- 根因是 D001 使用数字自定义样式 ID，旧提取器没有保留 `styles.xml` 的中文样式名和 outline level；全文清单及期别图只能使用文本猜测。
- 三个 Luna max 执行单元分别修复样式继承/直接轮廓、标题/表题路径和期别上下文关闭；无 fallback，执行模型未充当独立测试者。
- Codex 复测 D001：1,689 个全文单元未减少，表 5 十三行完整且标题链正确，但恢复为 `UNKNOWN`；未决/混合项升至 1,433，暴露旧Ⅲ期跨章节泄漏。源文件未改。
- 验证：聚焦 `53 passed`，协议全量 `566 passed, 58 warnings`，`git diff --check` 通过。
- 下一安全动作：实现独立语义期别适用性解析，输出选定期别、对侧期别、跨期共用或仍待确认及来源依据；再建 D001 II 人工矩阵。

## 2026-08-25 Phase 5.8c-2 语义期别适用性验收

**Task**: 模糊期别四类处置、目标相关上下文规划、非变异发布视图与源包闭包

### Summary

- 结构明确项不再交给 Agent 重判；1,433 个真正模糊单元保留为 Agent 目标。
- 四类结果和逐字回源合同已稳定，未知不默认共享；未决人工覆盖必须有原始未解决依据。
- 初版 D001 上下文复制路线产生约 4.03 亿字符，按根因改为全清单索引+目标相关检索+同表完整闭包后，总量降为 17,337,795 字符，每批最大 207,886 字符。
- 发布视图对完整源包做精确身份校验，不再只比较 ID；同 ID 内容篡改、旧快照、旧哈希或错期别均拒绝。

### Testing

- [OK] 聚焦集成回归 `100 passed`。
- [OK] 协议全量 `605 passed, 58 warnings in 269.17s`；中间执行者遇到的 8 个 LibreOffice abort 在父级清洁重跑中未复现。
- [OK] D001 只读探针保留 1,689 单元、表 5 全部 13 个结构单元，源 SHA-256/大小/mtime 未变。
- [OK] `compileall` 与 `git diff --check`。

### Status

[OK] **Slice 5.8c-2 accepted; Slice 5.8d next**

### Next Steps

- 建立 D001 II 人工控制对照矩阵，覆盖官方 IN/EX、流程必做项、表 5、复测/结果有效期、结核/妊娠及随机/首次给药锚点。
- 运行真实语义 Agent，以矩阵和源文逐项核对；任一异常先追溯系统根因。
- 不提前启动受试者审核、浏览器端到端或独立测试者。

## 2026-08-25 06:57 Phase 5.8d 立即无损暂停

- 用户要求向当前同一执行会话发出立即无损暂停；已向统一会话 `13612` 发送中断，执行器 `KeyboardInterrupt` 退出，未残留 runner/子进程。
- D001 II v4 JSON/Markdown 已保留，但没有正式执行报告且未经父级合同与临床语义验收，只能作为中间状态。
- 未启动 Worker 03、会商、独立测试者、浏览器或病例审核；未清理过程件，避免破坏恢复现场。
- 恢复时先读 `CHECKPOINT_20260825_D001_V4_RECONSTRUCTION_INTERRUPTED.md`，先验收或定向续修当前工件，不得直接发布。

## 2026-08-25 Phase 5.8d 混合期别表格原子化无损暂停

**现场**：紧凑 v2 批次 32 暴露表格行聚合导致 II/III 成员语义被合并；技术门禁通过不代表临床语义成立。

**已做**：拒绝“任一 UNKNOWN 即拆分”造成的 2,403 单元方案；向同一 Worker 01 会话下发窄化修订。代码和测试在中断前已落盘，但没有续修报告和通过证据。

**暂停确认**：已停止原执行会话，进程表无 runner/guard/任务子进程。未启动 Worker 02/03、全量 Agent、会商、浏览器或测试者。

**恢复**：先读 `CHECKPOINT_20260825_MIXED_TABLE_ATOMIZATION_INTERRUPTED.md`，验收当前 helper 与矩阵用例；重建 D001 并确认普通全未知行聚合、真正混合行拆分，再重跑真实批次 32。未通过前禁止 217 批全量运行。


## Session 9: Phase 5.8d 期别合批与理由门禁验收

**Date**: 2026-08-26
**Task**: Phase 5.8d 期别合批与理由门禁验收
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成 D001 II 相邻小章节合批、历史 v1 兼容、真实第69包根因修复与新提示断点。

### Main Changes

- 期别语义计划由217包压缩为137包且保持1298目标完整闭包
- 修复无期别限定即共享、跨单元片段引用和待确认候选误写问题
- 新增20260826无损检查点并冻结slice58i当前提示断点

### Git Commits

(No commits - planning session)

### Testing

- [OK] 聚焦50 passed, 5 warnings
- [OK] 完整协议715 passed, 58 warnings
- [OK] D001源SHA-256保持362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98

### Status

[OK] **Completed**

### Next Steps

- 用D001 II人工控制矩阵确认共同章节结构适用范围后，选择少量异质包继续真实验证

## Session 10: Phase 5.8d D001 矩阵来源闭包验收

**Date**: 2026-08-26
**Task**: D001 II 人工控制矩阵与当前冻结全文清单的确定性来源闭包
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成 25 行交叉章节清单和 82 行合并矩阵的来源身份、标题路径、来源范围及关系目标闭包；明确保持期别与完整声明阻断。

### Main Changes

- 新增精确且唯一命中的矩阵来源映射器、闭包报告和回归测试
- 47/47 与 155/155 来源锚点完成当前冻结单元回绑
- 将外部关系目标统计修正为真实引用集合，交叉清单 16、合并矩阵 0
- 旧 1,689 单元汇总移入历史目录，不再污染当前 1,840 单元状态
- 新增无损检查点并更新项目上下文、执行计划和后端质量规范

### Testing

- [OK] 聚焦矩阵与方案控制合同 `92 passed`
- [OK] 执行 review gate 与 `audit-execution`
- [OK] D001 源 SHA-256 保持 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

### Status

[OK] **来源与关系闭包完成；期别闭包继续阻断**

### Next Steps

- 为矩阵实际引用的 152 个冻结单元建立正向期别依据视图
- 优先核对共同治疗章节、表 5、结果有效期/复测、结核、妊娠及随机/首次给药控制
- 未形成权威处置前不运行全部 137 包，不设置 `claims_complete=true`

## 暂停记录：Phase 5.8d 单位级期别证据父级复核

**Date**: 2026-08-26 06:18 CST
**Task**: `phase5-slice58k-d001-unit-phase-evidence-20260826`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

三个执行者均已返回，但父级验收发现共同章节正向证据被错误实现为理由文本关键词门禁，因此立即停止后续工作并保存未验收现场。

### Accepted Observations Only

- 独立复算一致：82 行、155 个锚点、152 个唯一单元。
- 本轮未运行语义包，`claims_complete=false`，D001 源 SHA-256 未变。
- 六个代表包覆盖七类异质分层，仅是后续定向验证清单。

### Blocking Findings

- Worker 02 的“同一义务家族/全局广播/部分闭合”等理由文本词法门禁违反共享质量规范，必须删除，不能通过修改关键词继续修补。
- Worker 01 的 `candidate_closed` 状态名可能过度承诺语义闭合，须先复核并改为结构支持候选。
- execution review、metrics、review gate、audit 均未完成；三个 Worker 报告不是验收结论。

### Resume

读取 `CHECKPOINT_20260826_D001_UNIT_PHASE_EVIDENCE_PARENT_REVIEW_PAUSED.md`，严格按“撤词法门禁 -> 重命名非权威候选 -> 重建/测试 -> 父级复核 -> review gate/audit”的顺序恢复。恢复前不运行 137 包、病例审核、浏览器或视觉测试者。

## Phase 5.8d 单位级期别证据视图验收

**Date**: 2026-08-26

### Summary

完成暂停检查点规定的父级修复与验收：删除理由文本关键词门禁，将“候选闭合”降为“结构支持候选”，并重建真实 D001 单位视图。

### Evidence

- 82 行、155 锚点、152 单元；29/116/6/1 分别为结构支持候选、语义未决、来源冲突、结构阻断。
- 双次生成字节一致；D001 源 SHA-256 未变；137 包均 pending，`claims_complete=false`。
- 聚焦 `162 passed`；协议全量 `716 passed, 58 warnings`；review gate 与 execution audit 通过。

### Next

按 `CHECKPOINT_20260826_D001_UNIT_PHASE_EVIDENCE_ACCEPTED.md` 只运行 6 个异质代表包做真实语义验证。不得直接全跑 137 包或提前进入病例/视觉测试。

## Session 11: Phase 5.8d 同一规则标题族来源闭包验收

**Date**: 2026-08-26
**Task**: D001 II 代表包跨期来源闭包
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

修复提示词自相矛盾、成对来源单侧选择和同标题族交叉引用过窄三个共享根因；删除残留的理由关键词死代码。

### Evidence

- 第 59 包真实运行 12/12 跨期共用，每条均引用Ⅱ/Ⅲ期成对来源。
- 第 73 包第三次真实响应在当前门禁下离线重放为 9/9 跨期共用；原运行状态不改写。
- 聚焦 `70 passed`；协议层全量 `724 passed, 58 warnings`；`compileall` 通过。
- 1,840 单元、1,298 目标、137 包不变，`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260826_D001_RULE_FAMILY_CLOSURE_ACCEPTED.md`，只运行尚能增加临床信息的异质代表包；不启动 137 包全量、受试者、浏览器或独立测试。

## Session 12: Phase 5.8d 当前期别全局章节纳入验收

**Date**: 2026-08-26
**Task**: D001 II 全局章节与当前期别适用性
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

修复“不能证明跨期共用即保留未决”的错误等价关系，并以真实第 63、69、70 包验证全局章节可纳入当前固定Ⅱ期项目而不外推两期共用。

### Evidence

- 第 63 包 6/6、第 70 包 12/12、第 69 包质量重跑 11/11 为当前Ⅱ期适用。
- 第 69 包首次响应可重复出现未闭合引号；新统一中文完整性合同拒绝后，同会话修复通过。
- 支持来源必须直接指向目标或明确规则标题/表题族；第 59、73 包合法跨期引用重放仍通过。
- 聚焦 `46 passed, 5 warnings`；协议层全量 `730 passed, 58 warnings`。

### Boundary

第 70 包只覆盖表 5 子集；其余 134 包未运行，`claims_complete=false`。不启动受试者、浏览器或独立测试者。

### Next

读取 `CHECKPOINT_20260826_D001_SELECTED_PHASE_GLOBAL_CHAPTER_ACCEPTED.md`，继续只选择能增加新临床信息的异质包。

## Session 13: Phase 5.8d 混合段落强边界修复无损暂停

**Date**: 2026-08-26
**Task**: `phase5-slice58p-mixed-paragraph-atomization-20260826`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

首轮真实重建发现段落原子化按软标点和期别标记切分会破坏完整临床义务。父级拒绝该结果，并在同一 Worker 01 会话启动强边界修复；用户要求暂停时续修尚未完成，已立即中断并保存现场。

### Preserved State

- 已接受基线仍为 `1840/1298/137`，`claims_complete=false`。
- 首轮失败诊断为 `1857/1304/138`；`semantic_atom_boundary=needs_revision`。
- 强边界代码已有部分落盘，但没有报告、测试、重建或验收，必须按未验证中间态处理。
- D001 源 SHA-256 未变；执行器和子进程已停止。

### Resume

读取 `CHECKPOINT_20260826_D001_MIXED_PARAGRAPH_STRONG_BOUNDARY_FIX_INTERRUPTED.md`。先检查中断代码的一致性，完成实现并改写不安全测试，再在新产物目录重建并核对 `body.p729/p801/p815/p1237` 与 package 79/80/111；此前不得全跑语义包或启动病例/视觉测试。

## Session 14: Phase 5.8d 混合段落强边界原子化验收

**Date**: 2026-08-26
**Task**: `phase5-slice58p-mixed-paragraph-atomization-20260826`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成中断后的强边界实现、通用反向回归、真实 D001 重建、四个父段临床复核和五个受影响包叙述一致性修订。当前结构结果予以接受，但不提升全文语义完成状态。

### Evidence

- 当前 `1846/1303/138`；9/9 衍生原子完整回放，无法解释结果 0。
- `body.p801` 保持完整；`body.p1237#atom-100-160` 直接适用于 II 期且无包主权。
- 第 67/78/79/80/111 包机器关系与中文叙述一致，历史语义结果未复用。
- 源 SHA-256、大小和 mtime 不变；协议层 `741 passed, 58 warnings`。
- 修复全局执行审计器对正式同会话续跑的自相矛盾，真实包及伪造异常正反向检查均通过。

### Boundary

`claims_complete=false`。未运行语义模型、全部 138 包、病例、浏览器、视觉或三路独立测试者。

### Next

读取 `CHECKPOINT_20260826_D001_MIXED_PARAGRAPH_STRONG_BOUNDARY_ACCEPTED.md`，新建独立治理任务，只运行第 67/78/79/80/111 包的真实语义验证。

## Session 15: Phase 5.8d 期别交接与有边界语义验收

**Date**: 2026-08-27
**Task**: `phase5-slice58r3-phase-semantic-contract-repair-20260827` 及父级真实验证
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

父级没有把三名执行者的测试通过直接视为临床接受，而是以真实 D001 复跑发现并修复并列期别义务边界与模型重复无效“跨期共用”的系统原因。

### Evidence

- 当前真实结构基线 `1848/1301/137`，源 SHA-256 不变。
- 第 67、110 包在 r7 接受；第 79 包在 r7 被拒绝，在 v11 问题驱动修复的 r9 接受。
- 三包共 22 个单元通过父级临床核对；妊娠试验Ⅱ期访视未混入Ⅲ期访视。
- 协议层 `774 passed, 58 warnings in 761.65s`；聚焦 `14 passed` 与 `45 passed, 5 warnings`。
- 聚合验收位于 `artifacts/phase5-slice58r10-d001-bounded-semantic-acceptance-20260827/acceptance-summary.json`。

### Boundary

`claims_complete=false`。r5/r8 失败产物保留为反例；未启动其余 134 包、受试者、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260827_D001_PHASE_HANDOFF_AND_BOUNDED_SEMANTIC_ACCEPTED.md`，选择下一组不同结构风险的代表包，继续有边界语义验证。

## Session 16: MTPLX 默认语义 Agent 路由验收

**Date**: 2026-08-27
**Task**: `phase5-mtplx-default-semantic-agent-20260827`

### Summary

将后续审核、方案解构、期别判断和证据规范化默认切换到 `MTPLX/mtplx-qwen38-27b-optimized-quality:medium`，保持 OCR 独立走 oMLX。父级统一端口为 8002，并把 MTPLX 方案/证据输出收紧为严格 JSON Schema。

### Evidence

- 本机真实加载目标模型并精确公布目标 ID。
- 首次严格 Schema 400 定位为 MTPLX 缺少官方 `llguidance` server extra；安装 1.8.0 后探针通过，约 1.99 秒。
- 应用连通性返回 true；聚焦 `71 passed, 5 warnings`；编译、shell、diff 和执行审计通过。

### Boundary

旧根目录 `.env` 和桌面静态 UAT 入口未提前切换；D001 `claims_complete=false`，未扩大真实临床运行。

### Next

读取 `CHECKPOINT_20260827_MTPLX_DEFAULT_SEMANTIC_ROUTE_ACCEPTED.md`，只用新模型重跑少量异质代表包。
- 2026-08-27：恢复 Phase 5.8d 后先用 MTPLX medium 运行源包 36/60/78。首轮在 `PAIRED_RULE_FAMILY_SOURCE_IGNORED` 与 `SHARED_POSITIVE_SOURCE_MISSING` 间反复，定位到 `_same_rule_family` 把相同末级章节标题下的不同原子义务错误配对；共享修复改为相同非通用标题且逐字相同的原子义务才允许隐式同族传播，并增加同章节不同子义务/逐字重复义务回归。
- 修复后 MTPLX 36/36 接受；按用户补充要求加入 DeepSeek V4 Flash max 同源对照，组合重试后同为 36/36，处置差异 0。DeepSeek 8K 的包 36 输出截断，16K 重试闭合；默认仍为 MTPLX。详细数据在 `artifacts/phase5-slice59a-d001-mtplx-deepseek-comparison-20260827/`。
- 相邻重验发现旧源包 67 的“随机化”两项依赖不同分组比例形成过度共享。当前门禁按预期拒绝旧结果；MTPLX 重新生成后 11/11 为选定期适用，只引用目标自身全局流程。源包 79、110 用当前门禁仍接受。源包 67 首轮长度终止保留为诊断，第二次实际仍是本地 8192 上限并一次成功；不得按目录名误记为 16K。
- 协议层全量 `781 passed, 58 warnings`；`claims_complete=false`，剩余 131 包、病例、浏览器/视觉和独立测试者未启动。恢复入口更新为 `CHECKPOINT_20260827_RULE_FAMILY_AND_MODEL_COMPARISON_ACCEPTED.md`。

## Session 17: Phase 5.8d 当前小批量方案适用性修复与 16K 预算验收

**Date**: 2026-08-27
**Task**: `phase5-slice59g-20260827`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

真实运行新代表包 57、61、121，修复新预算用例误插导致的 live 测试结构破坏，验证 MTPLX 16K 与 OMLX 8K 输出预算独立，并建立本小批量持久检查点。

### Evidence

- 包 121 首轮链即接受（12/12 选定期适用，8192）；包 57 修复后以 8192 接受（1 选定期 + 11 跨期共用）；包 61 第 9 次同会话修复尝试（slice59f r3，16384）接受，12/12 跨期共用、0 未决。
- 包 61 的 8192 修复响应连续两次达到长度上限；16K 解决截断后，又通过聚合门禁反馈和定向修复提示解决异质分组、成对来源、共享正向证据及候选处置冲突。16K 必要但不充分。
- 16K 预算独立验证：配置默认、传输独立钳制、聚焦预算测试通过。
- 完整 protocols `786 passed, 58 warnings in 179.99s`；聚焦预算/修复 `25 passed`；gate v2 强类型正位重放 3/3 accepted、0 问题。Codex 逐条核对 36 个目标，未发现期别错误或 AND/OR 改写。
- 正位工件在 `artifacts/phase5-slice59{b,c,d,e,f}-*`；执行报告在 `runs/execution/phase5-slice59g-20260827/`。

### Boundary

`claims_complete=false`；剩余 128 包未运行；受试者、浏览器、视觉与独立测试者未启动；无生产写入。

### Next

读取 `CHECKPOINT_20260827_SMALL_BATCH_PHASE_APPLICABILITY_ACCEPTED.md`，临床核对后选择下一组结构风险不同的少量代表包；不全跑 128 包。

## Session 18: Phase 5.8d 流程表期别作用域与表 5 小批量验收

**Date**: 2026-08-27
**Task**: `phase5-slice59h/59j` 及父级结构修复
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

父级拒绝旧第 39 包的技术绿色结果，定位并修复普通段落形式的Ⅱ/Ⅲ期流程表题没有约束表后说明的通用结构缺陷；在新 131 包基线上完成表 5 三包真实验证，并补齐不可见控制字符门禁。

### Evidence

- 新基线 `1848/1245/131`；稳定原文差异恰为 56 条明确期别流程说明，其他目标语义不变。
- 新第 63/64/65 包共 24 个目标均为Ⅱ期适用，表 5 r0-r12 来源闭合。
- 第 63 包旧结果含 82 个 U+000B，被拒；新不可变重跑 11/11、控制字符 0。
- 聚焦 `58 passed, 5 warnings`；协议层 `789 passed, 58 warnings`；两轮 review gate 与 execution audit 通过。

### Boundary And Next

期别适用性不是控制点解构完成。较长者、条件缩短、嵌套例外、表/附录引用继续保持待结构化；新计划只接受 3 包，剩余 128 包，`claims_complete=false`。恢复读取 `CHECKPOINT_20260827_D001_PHASE_TABLE_SCOPE_AND_TABLE5_ACCEPTED.md`。

## Session 19: Phase 5.8d 表 5 结构化控制点代表行验收

**Date**: 2026-08-27
**Task**: `phase5-slice59m-20260827`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

将发布语义门禁接入控制点 Agent 的同一会话修复链，并在真实重放暴露越界改写后增加确定性修复范围保护。最终只接受 D001 Ⅱ期表 5 的 4 个异质代表行。

### Evidence

- 首轮调用因来氟米特 6 个月替代窗缺少持续至研究结束的直接支持而拒绝；第二次同会话修复后 4/4 发布。
- 第一次技术绿色重放越界改写 3 个无关候选，父级拒绝；范围保护版重放中 3 个范围外候选及处置逐字段完全一致。
- 接受工件：`artifacts/phase5-slice59m-d001-table5-mtplx-control-replay-bounded-repair-20260827/`；真实耗时 `202.690291` 秒。
- 聚焦 `75 passed`；协议层 `823 passed, 58 warnings in 154.78s`；review gate、execution audit、编译和 JSON 重载通过。

### Boundary

`claims_complete=false`；仍为 `1848/1245/131`，剩余 128 包。未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260827_TABLE5_STRUCTURED_CONTROL_REPLAY_ACCEPTED.md`，选择另一组不同结构风险的少量控制点，先做来源闭包人工核对；不得直接全跑 128 包。

## Session 20: Phase 5.8d 病毒学与结核跨章节控制点验收

**Date**: 2026-08-28
**Task**: `phase5-slice59n-20260827`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

使用冻结 D001 Ⅱ期原始方案结构完成病毒学和结核两组真实 MTPLX medium 重放。父级拒绝多轮技术绿色或近似绿色输出，围绕已覆盖条款重复发布、条件分支丢失、例外层缺失、可选语气弱化、禁止事件时间锚点错误和不同决定阶段混合做通用修复。

### Evidence

- 病毒学 V10 接受 3 个真实增量候选；结核 V5 接受 4 个真实增量候选。
- 例外门禁由整个来源单元收窄为候选自身引用语义，新增兄弟候选例外不泄漏反例。
- 聚焦 `76 passed`；协议层 `845 passed, 58 warnings in 125.19s`；编译和差异检查通过。
- 父级验收与哈希：`artifacts/phase5-slice59n-d001-viral-tb-parent-acceptance-20260828/acceptance-summary.json`。

### Boundary

`claims_complete=false`。D001 Ⅱ期仍为 `1848/1245/131`，剩余 128 包；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_VIRAL_TB_CONTROL_REPLAY_ACCEPTED.md`，只选择另一组能暴露新结构风险的真实控制点继续验证。

## Session 21: Phase 5.8d 妊娠/FSH 控制点加固，父级未接受

**Date**: 2026-08-28
**Task**: `phase5-slice59p` 至 `phase5-slice59u`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

以未经用户预处理的 D001 II 原始 DOCX 冻结结构验证妊娠试验/FSH 跨章节控制。父级拒绝 V4 技术绿色结果，并将暴露的重复控制、阶段混合、治疗后程序污染和豁免语气强化收敛为通用门禁。V5 门禁正确阻断，但模型未在当前混合来源输出合同上收敛。

### Evidence

- V4：7 次调用、结构与发布门绿色；父级临床拒绝 4 项语义问题，保留为反例。
- V5：11 次调用，无终稿；最后 8 轮持续出现 `p816` 候选处置与候选草稿冲突，其中同一错误响应重复 5 次。
- 全量协议回归 `861 passed, 58 warnings in 129.03s`；编译、JSON 重载、差异检查通过。
- 父级评估：`artifacts/phase5-slice59u-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。

### Boundary

只接受通用系统加固，不接受本组临床解构。D001 II 保持 `1848/1245/131`，剩余 128 包，`claims_complete=false`。未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_PREGNANCY_FSH_CONTROL_REPLAY_HARDENED_NOT_ACCEPTED.md`。先按最终入排决定时点和已知目标覆盖差异拆分混合来源单元，再做一次有边界重放；禁止原样重跑 V5。

## Session 22: Phase 5.8d 妊娠/FSH V7 最早节点对齐未接受

**Date**: 2026-08-28
**Task**: `phase5-slice59v` 至 `phase5-slice59x`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

从 V6 技术绿色但临床混合时点的反例继续，门禁下沉到每个触发事实的陈述与直接摘录。V7 已正确拆分筛选和首次给药前触发，但父级发现初潮前豁免没有绑定最早受影响的筛选节点，因此仍拒绝整组。

### Evidence

- 新增混合时点拒绝、拆分通过及单一区间不误拒回归；聚焦 `120 passed in 1.23s`。
- 协议层全量 `866 passed, 58 warnings in 124.39s`。
- V7 使用真实 MTPLX medium，9 次同会话调用、`734.447232s`，3 个候选，技术门禁绿色。
- 父级评估：`artifacts/phase5-slice59x-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。

### Boundary

只接受共享时点门禁，不接受 V7 临床解构。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_PREGNANCY_FSH_V7_STAGE_ALIGNMENT_NOT_ACCEPTED.md`。先建立“补充控制最早受影响节点对齐”通用合同和反例，不运行 V8。

## Session 23: Phase 5.8d 妊娠/FSH 多访视闭包与 V9 非收敛复盘

**Date**: 2026-08-28
**Task**: `phase5-slice59y` 至 `phase5-slice60b`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

真实 DOCX 产品链证明妊娠/FSH 是筛选、基线和 D1 三个访视级流程目标。当前 wire、领域草稿、水合处置和发布边界已支持一个原文单元完整关联多个目标；V8 单候选临床合理但旧单值处置丢失访视闭包，V9 则在发布问题与临床遗漏分轮暴露时未收敛。

### Evidence

- V8 父级拒绝：`artifacts/phase5-slice59z-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。
- V9：11 次真实 MTPLX medium 调用，732.838904 秒，无水合终稿，正确停为“需要核对”。
- V9 父级拒绝：`artifacts/phase5-slice60b-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。
- 聚焦回归 `165 passed`；完整方案层 `872 passed, 58 warnings`。

### Boundary

只接受通用合同与验收反馈汇总修复，不接受妊娠/FSH 临床解构。D001 II 仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_PREGNANCY_FSH_V9_MULTI_VISIT_REPAIR_NOT_ACCEPTED.md`。先补复合缺陷一次性反馈的确定性回归，再决定是否只运行一次 V10。

## Session 24: Phase 5.8d 妊娠/FSH V10 收敛，访视覆盖边界未接受

**Date**: 2026-08-28
**Task**: `phase5-slice60c` 至 `phase5-slice60d`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

把发布问题与临床遗漏并入同一轮修订后，唯一一次 V10 真实重放形成技术终稿。父级逐单元核对没有采信绿色门禁，发现流程目标的来源范围与访视身份不一致，以及首次给药前节点被一般基线节点吞并，整组继续拒绝。

### Evidence

- 复合缺陷及相关聚焦回归 `167 passed in 1.55s`；协议层 `872 passed, 58 warnings in 130.10s`。
- V10：6 次 MTPLX medium 调用、`414.810655s`、3 个候选、技术门禁通过。
- 父级拒绝证据：`artifacts/phase5-slice60d-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。
- 未运行 V11。

### Root Cause

筛选、基线和 D1 目录目标虽然有不同 `visit_instance`，却各自复用了同一整段跨访视说明。模型据此将 W12 和提前退出误判为已覆盖，而发布门禁只验证目标身份集合，没有验证访视语义集合。首次给药前候选同时错用 `flow-baseline`，暴露“同一review_stage不等于同一workflow节点”的合同缺口。

### Boundary

D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_PREGNANCY_FSH_V10_VISIT_SCOPE_NOT_ACCEPTED.md`。先实现访视级来源范围、结构化覆盖集合和首次给药前精确节点校验，再考虑任何真实模型调用。

## Session 25: Phase 5.8d 访视覆盖范围与精确节点门禁接受

**Date**: 2026-08-28
**Task**: `phase5-slice60e`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

将 V10 父级拒绝下沉为共享确定性门禁。流程必做处置现在按选定期明确访视与链接目录项访视身份做闭包比较；后续时间锚点在存在专门冻结节点时必须使用精确节点，而不是同阶段任意节点。

### Evidence

- 保存的 V10 终稿重放为 `accepted=false`，首个问题 `PROCEDURE_VISIT_SCOPE_UNCOVERED`，中文缺口为“提前退出访视、第12周访视”。
- 反例证明 II 期比较会排除明确属于 III 期的 W16/W52。
- 反例证明首次给药锚点在存在 `flow-d1-pre-dose` 等价专门节点时不能绑定普通基线。
- 聚焦 `169 passed in 1.52s`；协议层 `874 passed, 58 warnings in 125.93s`。

### Boundary

只接受系统门禁，不接受 V10 临床解构；未运行 V11。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`，后续受试者/OCR/前端/视觉测试未启动。

### Next

读取 `CHECKPOINT_20260828_VISIT_SCOPE_AND_EXACT_NODE_GATE_ACCEPTED.md`，选择新的极小异质控制组继续，不直接扩大或重放妊娠/FSH。

## Session 26: Phase 5.8d 访视合并时间边界修复，基线值层级未接受

**Date**: 2026-08-28
**Task**: `phase5-slice60e` 至 `phase5-slice60f`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

新代表组直接来自未经用户预处理的 D001 Ⅱ期 DOCX。共享时间合同现能区分开闭边界，真实模型也正确编码 `≤7天` 与 `＞7天`；但模型把明确要求 D1 给药前取值的项目扩展到较宽的基线窗口，并重复冻结流程目标，因此父级不接受。

### Evidence

- 真实回放：`artifacts/phase5-slice60f-d001-visit-merge-baseline-value-open-bound-replay-20260828/`，3 次同会话调用、`214.199618s`、无 fallback、无终稿。
- 保存响应离线重放后，`TIME_ANCHOR_MISSING` 精确定位至 `pca-ea2531bf1ddda28a347a2db0` 及原句“以给药前最近一次评估结果作为基线值”。
- 发布门禁新增原文比较符核对；前端结构合同和中文显示同步开闭边界。
- 组合回归 `213 passed in 4.06s`。

### Boundary

只接受通用时间合同、诊断和提示修复；不接受本组临床解构，不发布新控制点。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_VISIT_MERGE_OPEN_BOUND_FIXED_REPLAY_NOT_ACCEPTED.md`。先建立通用“默认规则与明确精确特例”层级反例，证明精确项目不会继承较宽窗口，也不会重复冻结流程目标。

## Session 27: Phase 5.8d 时间义务作用域合同接受

**Date**: 2026-08-28
**Task**: `phase5-slice60g`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

上轮失败不是单一时间锚点缺失，而是 Agent 把访视安排、检查结果有效期和基线值选取都压成通用“完成/核对”，导致通用访视窗向精确检查项扩散。当前合同将三者分型，并以冻结流程节点或精确流程必做项限制其作用域。

### Evidence

- 保存的 D001 第三次响应在新 wire 下稳定拒绝；人工只做结构化等价拆分后可水合为 2 个候选，义务类型分别为 `访视安排/核对` 和 `基线值选取`。
- 通用反例覆盖：访视窗挂到单项检查拒绝、挂到自身流程节点通过、通用基线原则与检查特例混合拒绝、结果有效期缺少精确检查目标拒绝。
- 聚焦回归 `218 passed in 4.10s`；协议层完整回归 `887 passed, 58 warnings in 124.64s`。

### Boundary

只接受共享合同和发布边界，不接受或发布原 D001 Agent 临床结果。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉及独立测试者未启动。

### Next

读取 `CHECKPOINT_20260828_TEMPORAL_OBLIGATION_SCOPE_ACCEPTED.md`。下一步选取新的极小异质控制组，验证结果有效期和基线值特例在真实方案中的分离表现；不得把人工修正结果当作模型成功。

## Session 28: Phase 5.8d 胸部CT有效期与验收确认偏差修复

**Date**: 2026-08-28
**Task**: `phase5-slice60h`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

胸部CT代表组首次响应正确识别“知情同意书签署日前1个月内且满足评估要求”的结果有效期已在冻结流程必做项中，并把“可酌情复测”保留为非强制裁量。验收器却将人工预设的“必须有候选”回传给同一会话，迫使模型制造新的访视记录义务。当前只将客观合同/发布错误用于 Agent 修订，金标准期望留给父级最终验收。

### Evidence

- 原运行首轮响应 SHA-256：`8dc87a94d3036a6ea05d4fdd7aabaf78d3945ee1432e00efba8035fa3c78c94f`。
- 新代码离线水合：0 候选、1 条 `required_procedure` 处置，发布门禁接受，临床拒绝问题 0。
- 被拒终稿把“可酌情决定是否复测”改成“筛选访视记录中应体现是否复测的决定”，属于无方案依据的资料义务。
- 聚焦 `146 passed in 1.33s`；完整方案层 `887 passed, 58 warnings in 126.51s`。
- 父级评估：`artifacts/phase5-slice60h-d001-ct-result-validity-parent-assessment-20260828/assessment-summary.json`。

### Boundary

本组接受无新增候选处置，不发布新控制点；未再次调用模型。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉和独立测试者未启动。

### Next

读取 `CHECKPOINT_20260828_CT_VALIDITY_CONFIRMATION_BIAS_FIXED.md`。选择下一组小型异质控制点时，临床金标准只做盲态父级验收，不能作为修订指令向 Agent 泄露。

## Session 32: Phase 5.8d 病史/治疗史采集节点验收

**Date**: 2026-08-28
**Task**: `phase5-slice60n` 至 `phase5-slice60w`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

病史/治疗史代表组连续暴露了只读上下文未入提示、回顾起点误作执行访视、给药前事项误判治疗后、额外访视绑定、改处分类型逃逸和并列资料家族漏链。父级拒绝每个技术绿色但临床错误的中间结果，并最终以结构化访视和资料家族合同闭合。

### Evidence

- v9：2 次 MTPLX medium 调用、`109.65441s`、0 新候选、4 条流程必做处置，发布门禁通过。
- p772/p773 仅覆盖筛选+基线；p858 仅覆盖基线；p871 仅覆盖 D1 给药前；后两者均同时覆盖病史和治疗史。
- 家族期望不进入 Agent 首轮提示；父级验收位于 `artifacts/phase5-slice60w-d001-history-treatment-collection-replay-structured-family-20260828/parent-clinical-acceptance.md`。
- 最终代码聚焦 `189 passed`；完整方案层回归 `911 passed, 58 warnings in 127.37s`。
- 执行治理审计通过；提示、运行输出与日志已归档，紧凑审阅、指标、检查点和临床验收证据保留。

### Boundary

D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

完成最终回归、执行审计与过程清理；随后核对 131 包活动冻结计划第 67 包的知情同意/人口学筛选前置与筛选期单节点，以稳定 `source_ref` 为身份。工作区内 217 包旧研究快照不得用于活动包序号，不扩大到剩余 128 包。
# Session 30 - 2026-08-28 避孕附录 v3 语义回放暂停

- 受治理执行包三路只读审阅完成，实际路线均为 Cursor CLI/auto，无 fallback。
- 修复条件分句句末标点绕过和“告知条件内容”被误作当前触发；提示版本升至 v1.1，相关聚焦回归 85 通过。
- v3 真实 MTPLX medium 回放 5 次调用均成功但未水合；p1326 已正确，p1325 时间区间仍错误。
- 最后追加 ICF 至末次给药后 N 的通用结构化提示后收到暂停指令，该补丁尚未验证。
- 恢复必须先读 `CHECKPOINT_20260828_CONTRACEPTION_SEMANTIC_REPLAY_V3_PAUSED.md`，先验证再考虑 v4；Phase 5 与 D001 全量均未完成。

## Session 31: Phase 5.8d 避孕附录计划访视闭包验收

**Date**: 2026-08-28
**Task**: `phase5-slice60l` 至 `phase5-slice60m`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

v4 技术绿色但因计划访视仅绑定筛选而被父级拒绝。共享门禁、Agent 合同和回归现要求全部冻结访视分别判定并具备分期证据；v5 在相同冻结输入上完成父级临床验收。

### Evidence

- 三路 `cursor-cli/auto` 只读审阅及执行审计通过；过程文件已归档。
- v5：2 次 MTPLX medium 调用、`118.86071s`、2 候选/2 控制、技术门通过。
- 冻结来源与 v4 字节一致；p1325/p1326 与 IN-06 九项父级检查通过。
- 聚焦 `129 passed`；完整方案层 `896 passed, 58 warnings in 116.93s`。

### Boundary

只接受避孕附录代表组。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未进入受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_CONTRACEPTION_PLANNED_VISIT_ACCEPTED.md`，从剩余包选择一个新的极小异质控制组；先建人工来源闭包和父级检查清单，不把金标准注入 Agent 修订。

## Session 33: Phase 5.8d 知情同意/人口学动作闭包验收

**Date**: 2026-08-28
**Task**: `phase5-slice60x` 至 `phase5-slice60zb`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

活动 131 包计划第 67 包的知情同意/人口学代表组完成父级验收。真实回放证明提示词不能弥补结构合同缺失：模型先后把“筛选前解释研究程序”吞并为签署事实，随后又无法用旧类型表达一般动作早于命名节点。当前以通用动作覆盖和“节点前完成”合同闭合，不包含项目专有规则。

### Evidence

- v4：2 次 MTPLX medium 调用，`79.382436s`，1 候选、1 流程必做处置、发布门禁通过、无 fallback。
- p768 仅保留筛选前解释程序；p770 由人口学采集流程覆盖；IN-01/IN-02 与流程义务分离。
- 聚焦 `174 passed`；完整方案层 `912 passed, 58 warnings`。
- 三路 `cursor-cli/auto` 执行审计通过；父级 review 明确拒绝旧 217 包序号和“现有合同足够”的错误架构判断。

### Boundary

只接受本代表组。D001 Ⅱ期保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_ICF_DEMOGRAPHICS_ACTION_CLOSURE_ACCEPTED.md`，从活动计划中选择下一组不同结构风险的极小来源，先做来源闭包和父级检查清单。

## Session 34: Phase 5.8d 身高/体重门禁接受，Agent 终稿未收敛

**Date**: 2026-08-28
**Task**: `phase5-slice60zc` 至 `phase5-slice60zl`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

活动 131 包计划第 68 包证明流程目录中的“执行/记录”不能覆盖章节里的测量准备、设备、体位、操作步骤和记录精度。系统已加入目标范围、结构标题、动作聚合与精度分层门禁；MTPLX medium 在既定七次调用内仍未形成同时满足全部合同的终稿，因此只接受门禁修复，不接受临床解构。

### Evidence

- v4–v9 依次暴露：身高阶段越界、逐项修订耗尽预算、模糊访视误判、标题提升、kg 一位小数和 cm 整数精度压缩。
- 聚焦 `149 passed, 5 warnings`；完整方案层 `919 passed, 58 warnings`。
- `finite_code_task` 治理审计通过；三路均为 `cursor-cli/auto`，无 fallback，过程文件已归档。

### Boundary

第 68 包控制点未发布。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

### Next

读取 `CHECKPOINT_20260828_D001_HEIGHT_WEIGHT_GATES_ACCEPTED_AGENT_UNRESOLVED.md`。检查 runner 修订状态保留方式，先以保存响应和合成反例实现确定性局部保留/补丁，不增加重试次数、不直接重跑第 68 包。

## Session 35: Phase 5.8d 修订状态确定性保留

**Date**: 2026-08-28
**Task**: `phase5-slice60zm`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

第 68 包 v7-v9 事后核对表明，runner 的问题不是单纯重试次数不足，而是无范围错误扩大、首个失败版永久成为基线、候选拆分/合并无来源守恒、以及整候选替换无法保留兄弟义务。当前以机器可读范围、来源闭包和义务原文定位建立三级失效关闭保留。

### Evidence

- 保存 v9 第 6/7 次响应逐原子核对：`body.p780` 错误在第 6 次已存在，第 7 次仅修复体重 DNF。
- 新回归覆盖无范围停止、滚动基线、跨候选保留、候选重分区来源守恒、原子级保留和系统 ID 重算。
- 聚焦 `153 passed`；组合回归 `1033 passed, 58 warnings in 140.00s`。
- 执行审计通过；评估位于 `artifacts/phase5-slice60zm-d001-height-weight-repair-retention-20260828/assessment.md`。

### Boundary

只接受通用机制。D001 第 68 包仍未接受且未发布；本轮未调用真实模型，未增加预算，未启动受试者/OCR/前端/视觉流程。D001 II 仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_BOUNDED_REPAIR_RETENTION_ACCEPTED_D001_UNRESOLVED.md`。按稳定 `source_ref` 选新的极小异质代表组，先做盲态来源闭包和父级检查清单，不重跑第 68 包或扩大全量运行。

## Session 36: Phase 5.8d 权威目标原文传递

**Date**: 2026-08-28
**Task**: `phase5-slice60zn`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

实验室代表组运行前发现，真实产品目录到控制 Agent 的链路丢失官方规则和流程目标原文，旧研究脚本靠人工矩阵补齐。当前将摘录冻结到目录并透传；来源编号与摘录成对排序，纯结构表格根以 `null` 保留。

### Evidence

- 首次广泛回归在 MG-K10-SAR 暴露无文本表格根导致整项目标摘录清空；修订后 CMS-D001 与 MG-K10-SAR 均通过真实 DOCX 链。
- D001 EX-20 提示保留 ALT/AST/总胆红素阈值与研究者不可接受风险合取，未混入 GGT。
- 聚焦 `143 passed`；方案层与合同工件 `974 passed, 58 warnings`；受控执行审计通过。

### Boundary

只接受通用权威原文传递机制。第 70-71 包尚未调用模型，第 68 包仍未接受；D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_AUTHORITATIVE_TARGET_EXCERPTS_ACCEPTED_LAB_NOT_RUN.md`。用产品冻结目录准备第 70-71 包干跑，禁止再以人工矩阵补齐已知目标。

## Session 37: Phase 5.8d 实验室动作遗失门控

**Date**: 2026-08-28
**Task**: `phase5-slice60zo` 至 `phase5-slice60zt`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

实验室代表组的跨章节来源闭包已完成；唯一一次 MTPLX medium 运行结构合法，但丢弃 `body.p799` 的采样和标准程序动作，因此只接受共享机制修复，不接受该模型结果。

### Evidence

- 最终干跑 60zs 包含 `p316/p325/p802`、四个流程表行及 EX-20 权威原文；无人工矩阵。
- 60zt：1 次调用，`121.617064s`，7 处置、0 候选、无重试、无 fallback。
- 共享规划器现填充 gate-only 必备动作元数据；原始输出重放触发 `REQUIRED_ACTION_DISCARDED`。
- 聚焦 `158 passed`；完整方案模块 `944 passed, 58 warnings`；编译、JSON、diff 检查与 Hermes 治理门通过。

### Boundary

没有发布方案控制点。第 68 包和剩余 128 个单元未改；D001 II 仍为 `1848/1245/131`、`claims_complete=false`。未启动受试者/OCR/前端/视觉/独立试用。

### Next

读取 `CHECKPOINT_20260828_LABORATORY_ACTION_GATE_REJECTED.md`。建立新的不可变修复切片，用修复后批次执行一次新语义运行；不覆写 60zt，不把父级期望注入 Agent。

## Session 38: Phase 5.8d 实验室动作门控重放拒绝

**Date**: 2026-08-28
**Task**: `phase5-slice60zu` 至 `phase5-slice60zv`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

修复后的产品包完成一次真实 MTPLX medium 调用。模型看见并复述 p799 的采样和标准程序动作，却把检查项目/访视目录错误提升为对两项动作的完整覆盖；动作门控稳定拒绝，模型结果未接纳。

### Evidence

- 60zu 第 70 包冻结 `collect_biospecimen`、`follow_specified_procedure`，Agent 输入与提示无门控答案。
- 60zv：1 次调用，`112.78853s`，3 条处置、0 候选、无重试。
- 门控：`PROCEDURE_ACTION_UNCOVERED`；父级审查确认是语义包含错误，不是 OCR 或来源缺失。
- GGT、尿糖、尿潜血及 EX-20 合取边界未出现新增错误。
- 聚焦回归 `181 passed, 5 warnings`；完整方案模块 `944 passed, 58 warnings`；编译、JSON 和差异检查通过。
- Hermes 路线审计和评审门通过；执行过程已归档，60zu 临时产品链已清理。

### Boundary

第 71 包未做冗余调用；第 68 包、60zt、其余 128 包和现有控制点均未改。`claims_complete=false`，未发布。

### Next

读取 `CHECKPOINT_20260828_LABORATORY_ACTION_GATE_RERUN_REJECTED.md`。先离线建立候选义务的动作覆盖证明合同，不再原样调用模型，不扩大全量运行。

## Session 39: Phase 5.8d 候选义务动作覆盖证明

**Date**: 2026-08-28
**Task**: `phase5-slice60zw`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

共享门控现要求其他控制候选的义务陈述逐项保留流程目录未覆盖动作，并按当前来源单元定位证明，关闭只改 disposition、摘录冒充和跨单元借用三条绕过路径。

### Evidence

- 新增 `CANDIDATE_OBLIGATION_ACTION_UNCOVERED`、`OBLIGATION_ACTION_SOURCE_ONLY`。
- 保存的 60zv 响应仍稳定触发 `PROCEDURE_ACTION_UNCOVERED`。
- 聚焦 `132 passed`；完整方案模块 `950 passed, 58 warnings`；编译和差异检查通过。
- 三路 `cursor-cli/auto` 无 fallback；worker_03 同一会话复核最终实现后建议接受。
- Hermes 审计与评审门通过；过程文件已归档，同会话临时复核提示已清理。

### Boundary

本轮无模型调用、无发布。第 70–71 包、第 68 包和剩余 128 包状态未变，`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_CANDIDATE_ACTION_SEMANTIC_COVERAGE_ACCEPTED.md`。按活动 131 包稳定来源选择新的极小异质代表组，先做来源闭包和父级检查清单。

## Session 40: Phase 5.8d 病毒学条件豁免重评暂停

**Date**: 2026-08-28
**Task**: `phase5-slice61aa` 至 `phase5-slice61af`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

病毒学代表组完成候选重分区、条件豁免和同源多候选定向修订加固。v6 虽通过当时技术门禁，但独立审查证明 p804 的三项新增检查被错误强化为无条件筛选执行，父级接受已撤回。

### Evidence

- v6 MTPLX medium：4 次响应，3 个候选，总耗时 339.509 秒。
- 独立 Grok 审查指出 p804 整组检查共享 28 天有效期/无需再次检查；该意见有效。
- 同源候选乱序修订改为未授权兄弟唯一匹配，聚焦 `17 passed in 0.06s`。
- 旧完整方案层 `975 passed, 58 warnings` 早于最新乱序修订，不能证明当前全量通过。

### Boundary

v6 不发布，旧父级接受文件仅作历史记录。未运行 v7、完整回归、受试者、OCR、浏览器或视觉测试；`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_VIROLOGY_WAIVER_REASSESSMENT_PAUSED.md`。先追加 v6 重评文件，再实现条件豁免证据变体和跨候选范围门禁，跑聚焦及完整方案层回归后才允许一次 v7 重放。

## Session 41: Phase 5.8d 病毒学 v7/v8 修复与范围拆分拒绝

**Date**: 2026-08-28
**Task**: `phase5-slice61ag` 至 `phase5-slice61ak`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

条件豁免绑定缺失已收窄为固定候选内部表达式修复。v7、v8 均未形成可发布终稿；v8 的不同来源越界改写可由系统恢复，但 p804 同源无条件筛选兄弟仍造成条件豁免范围拆分，因此父级临床拒绝。

### Evidence

- v7：5 次响应、262.553825 秒，失败关闭；父级重评 SHA-256 `cfff258066537cf484bcb039df9bc2b07e80409487111a56d1a5a20a8b944a69`。
- v8：5 次响应、336.866189 秒，`hydrated=false`、`gate_accepted=false`、未发布；运行结果 SHA-256 `6e54d7bef4789e809919056c9b503a00fedcd8abc48208c5abc1d228c13085dc`。
- v8 第 4→5 次离线恢复后，p805 恢复正确，p804 仍触发 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`。
- 不同来源候选现按来源键消费后恢复上一轮对象；同源未授权兄弟、数量和来源分区继续严格冻结。
- 聚焦 `29 passed`；完整方案层 `989 passed, 58 warnings`；编译和差异检查通过。
- Gemini/Grok 独立审查一致支持隔离修复和 v8 拒绝。`review-gate` 通过；当前 guard 生成器未生成验证器要求的 `cursor-cli` 角色，`validate-conference` 未闭合，已如实保留。

### Boundary

没有发布任何病毒学控制点，没有增加 v8 修订预算，也没有扩展至剩余方案包、受试者、OCR、病例审核、Patient Profile 或视觉测试。`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_V8_SCOPE_SPLIT_REJECTED.md`。下一独立切片先设计通用 p804 同源来源闭包候选合并/重写合同，冻结 p805；确定性测试和独立审查通过前不调用模型。

## Session 42: Phase 5.8d p804 来源闭包权限验收

**Date**: 2026-08-28
**Task**: `phase5-slice61al` 至 `phase5-slice61an`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

共享有界修订现将模型建议的候选闭包与确定性问题授权分离；闭包全集越界时在第二次模型调用前失效关闭。修订轮次只允许一个结构修订类占有权限，关闭混合问题扩大处置范围。

### Evidence

- 控制级候选起点、字面跨单元候选、混合问题隔离和错误消息保留已回归。
- 聚焦 `47 passed`；完整产品代码 `1007 passed, 58 warnings`；编译、差异检查通过。
- 四轮 CodeBuddy DeepSeek V4 Flash max 同会话独立审查，822.145 秒、101 次工具调用，无 fallback；最终无有界工程阻断。

### Boundary

工程合同通过不等于 p804 临床通过。v8 仍为不可变拒绝反例，未重放、未发布；`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260828_P804_SOURCE_CLOSURE_AUTHORITY_ACCEPTED_REPLAY_DEFERRED.md`。先固化可重现 harness 并决定修订预算，再单独决定是否做一次新的不可变 p803-p805 重放。

## Session 43: Phase 5.8d 模型无关重放与修订预算验收

**Date**: 2026-08-29
**Task**: `phase5-slice61ao` 至 `phase5-slice61ap`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

建立了从原始 DOCX 到冻结来源批次的模型无关重放 harness，并把全局修订预算、结构化错误类别、无进展终止和外部指纹校验固化为产品合同。D001 p803-p805 仅作为只读工程锚点。

### Evidence

- 聚焦 `73 passed`；协议全量 `1033 passed, 58 warnings`；编译、JSON 和差异检查通过。
- 两次独立 D001 构建得到同一外部指纹 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`，batch/manifest/snapshot/prompt 身份完全一致。
- CodeBuddy DeepSeek V4 Flash max 同会话独立复审提出 F1-F6；修复后第 4 轮逐项确认全部关闭，无 fallback。
- 再锚定流程要求工具链有意变化后双构建、来源/身份复核和完整回归，不能用更新检查点掩盖漂移。

### Boundary

没有临床模型调用、控制点发布、受试者处理或前端变更。v8 仍拒绝，`claims_complete=false`；PDF 结构化方案入口尚未实现。

### Next

读取 `CHECKPOINT_20260829_MODEL_FREE_REPLAY_HARNESS_ACCEPTED_CLINICAL_REPLAY_DEFERRED.md`。下一独立切片先实现 PDF 到统一结构单元的产品入口，通过确定性回归和独立审查后再决定临床重放。

## Session 44: Phase 5.8d 原生文字 PDF 结构入口验收

**Date**: 2026-08-29
**Task**: `phase5-slice61aq-native-pdf-structure-entry-20260829`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

原生文字 PDF 现可进入 DOCX 共享的冻结结构链，保留原始页、文本区间和字符坐标框，并在对齐前逐字核对原页内容。扫描、混合文本层、零页、加密、损坏和哈希不一致均失效关闭。

### Evidence

- 新增可复现真实 PDF 验证脚本与持久 JSON/标准输出。
- SAR V2.1 PDF 两次均为 120 页、285 块、285/285 bbox 直接定位，哈希 `7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3`，源文件未变。
- D001 冻结回放指纹保持 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`。
- 聚焦 `12 passed`；后端全量 `2977 passed, 1 skipped, 139 warnings, 2 subtests passed`；`git diff --check` 通过。
- CodeBuddy / DeepSeek V4 Flash max 独立审查提出的持久证据缺口已关闭。新增加密 PDF 回归时发现并修复了 `pdfplumber` 异常包装导致错误分类的共享根因。

### Boundary

本轮只接受 PDF 入口，不接受标题、表格和多栏阅读顺序与 DOCX 等价。没有临床模型调用或控制点发布；`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260829_NATIVE_TEXT_PDF_ENTRY_ACCEPTED_STRUCTURAL_PARITY_PENDING.md`。下一独立质量切片统一处理 PDF 版面分区、栏阅读顺序、标题层级、表格结构及空白页/图像扫描页分流；不直接启动临床重放。

## Session 45: Phase 5.8d 原生文字 PDF 结构保真验收

**Date**: 2026-08-29
**Task**: `phase5-slice61ar-pdf-layout-structure-quality-20260829`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成原生文字 PDF 的版面结构质量闭包。标题、临床单位、重复页边文字、横线表格、合并单元格和来源范围冲突均采用项目无关的确定性机制，不依赖人工预处理或项目特异规则。

### Evidence

- 真实 SAR V2.1：120 页、2756 块、48 表、158 正文标题；2756/2756 坐标级对齐，0 降级、0 未对齐、0 异常，源文件未改变。
- DOCX/PDF 标题归一化对照：DOCX 154 项无缺失，PDF 仅多出 4 个封面/目录视觉标题。
- D001 两次重放指纹保持 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`。
- 聚焦 `83 passed`；最终后端全量 `3154 passed, 3 skipped, 141 warnings, 18 subtests passed`；编译和差异检查通过。
- 同一 Gemini 3.7 Flash high 会商会话首轮提出问题，修复后第三轮确认无高、中等级阻断；无 fallback。

### Boundary

只接受原生文字 PDF 结构保真。扫描/混合 PDF、跨页表语义拼接、多栏与全宽表混排仍未完成；没有临床模型调用、控制点发布、受试者处理或视觉验收。D001 v8 仍拒绝，`claims_complete=false`。

### Next

读取 `CHECKPOINT_20260829_PDF_STRUCTURAL_PARITY_ACCEPTED_NEXT_FULL_PROTOCOL_DECONSTRUCTION.md`。从原始 DOCX/PDF 上传链选择新的极小跨章节来源组，先冻结来源闭包和父级检查清单，再决定一次有界语义重放。

## Session 46: Phase 5.8d 心电图控制点与动作合同验收

**Date**: 2026-08-29
**Task**: `phase5-slice61as` 至 `phase5-slice61au`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

心电图代表组第二次真实运行的第三响应已通过完整离线门禁。修复不仅处理方案原文与模型输出的引号字形差异，还定位并关闭了冻结动作代码无法被共享检测器识别的系统合同缺口。

### Evidence

- 精确原始响应 SHA-256：`6e18be457055732ca68697a495e60db4e12fd47d5f2df6dc8c916e76a7e1cba0`。
- 离线重放：1 候选、1 控制，发布门禁与临床拒绝门禁均通过。
- 引号恢复仅限唯一、连续、等长来源；原始 wire 不变，其他语义或普通标点变化继续拒绝。
- 通用动作语义目录补齐静息准备、QTcF 计算及相邻项目无关动作，并加入设备名称误报负向回归。
- 聚焦 `283 passed`；协议模块全量 `1106 passed, 58 warnings`；受控执行审计通过。

### Boundary

仅接受心电图代表组，不并入完整 131 包正式目录。D001 II 剩余 128 包，`claims_complete=false`；未进入受试者、OCR、Patient Profile 或视觉工作。

### Next

读取 `CHECKPOINT_20260829_D001_ECG_CONTROL_ACCEPTED_ACTION_CONTRACT_FIXED.md`。选择新的最小异质来源组，先冻结来源闭包、流程目录覆盖和父级检查清单，再决定一次有界语义重放。


## Session 47: Phase 5.8d 生命体征模态代码闭环与模型阻断

**Date**: 2026-08-29
**Task**: Phase 5.8d 生命体征模态代码闭环与模型阻断
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成生命体征动作主体、阶段、模态、证据、列举项和关系强度的通用门禁；完整回归通过。v11/v12 连续 500 后，会话缓存自动回落至约 24.1 GB；唯一 v13 同源重放仍两次 500，未形成父级可验收终稿。

### Main Changes

- 新增审核指引动作、最低证据模态、参与者准备落实、列举项计数及动作增量关系强度门禁
- 补全 slice61av 执行审阅、slice61aw 独立会商审阅及指标，明确 revise 而非临床接受
- 新增无损恢复检查点并同步实施计划、项目上下文和后端质量规范

### Git Commits

(No commits - planning session)

### Testing

- [OK] 聚焦回归 155 passed, 5 warnings
- [OK] 方案模块完整回归 1145 passed, 58 warnings
- [OK] review-gate、validate-conference、audit-execution、py_compile、git diff --check 通过
- [BLOCKED] v13 两次新会话分别在 110.188 秒和 95.547 秒返回 MTPLX 500，请求 `e0c906e5d034`、`c283bba62027`

### Status

[OK] **Completed**

### Next Steps

- 先用非临床诊断夹具隔离 MTPLX 长提示与严格 response schema 服务端路径；修复后再基于相同冻结来源运行一次同源重放和 Codex 父级临床验收

## Session 48: Phase 5.8d 生命体征模态与严格结构输出验收

**Date**: 2026-08-29
**Task**: `phase5-slice61bi` 至 `phase5-slice61bj`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成MTPLX严格结构化输出故障的系统修复与生命体征代表组父级验收。修复采用请求级AR，不依赖服务重启、环境变量或提示词缩短；v14保持冻结来源和临床问题不变并获得完整终稿。

### Evidence

- 四条MTPLX严格JSON Schema传输均增加 `generation_mode=ar`；DeepSeek/oMLX不变。
- 聚焦 `45 passed, 5 warnings`；方案与语义传输组合 `1189 passed, 58 warnings`。
- v14真实重放三轮结果为结构错误、发布错误、成功解析；最终1候选、1控制，技术门禁和临床父级检查通过。
- 两次独立会商完成；夜间DeepSeek V4 Flash max无回退复核无临床或结构阻断。主线程纠正“四类应拆成五类”和“服务环境变量已修改”两项推断。

### Boundary

只接受生命体征代表组，不并入正式131包。D001 II保持`1848/1245/131`、剩余128包，`claims_complete=false`；受试者、OCR、Patient Profile、浏览器和视觉阶段均未启动。

### Next

读取 `CHECKPOINT_20260829_VITAL_SIGN_MODALITY_AR_ACCEPTED.md`。选择新的极小异质跨章节来源组，先冻结来源闭包、已知控制覆盖和父级检查清单，再决定一次有界重放。


## Session 49: Phase 5.8d 疗效评分方法与阶段来源闭包验收

**Date**: 2026-08-30
**Task**: Phase 5.8d 疗效评分方法与阶段来源闭包验收
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

第74包经五次保留回放后有限接受；系统级修复脚注作用域、方法增量、问卷回顾期、证据边界、专业判断和同原子溯源。

### Main Changes

- 接受4个疗效评分方法控制点，不并入正式131包目录
- 补齐执行包来源、评审、指标和父级临床接受记录
- 保留前4次拒绝回放为系统级反例

### Git Commits

(No commits - planning session)

### Testing

- [OK] 聚焦回归186 passed, 5 warnings
- [OK] 方案与Agent全量回归1197 passed, 58 warnings
- [OK] audit-execution通过且无警告

### Status

[OK] **Completed**

### Next Steps

- 按冻结计划检查第75包自有单元与跨章节权威来源，先冻结最小来源闭包和父级临床清单


## Session 50: Session 50 - 第75包模型外语义边界验收

**Date**: 2026-08-30
**Task**: Session 50 - 第75包模型外语义边界验收
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

第75包完成来源闭包、异质语义分区、来源组成要素门禁、模型外准备、全回归和治理审计；未调用临床语义模型，正式状态不变。

### Main Changes

- p831/p832/p835处置为治疗期执行，p833为非入排研究执行，p837为唯一阶段资料候选。
- 新增candidate_required_markers_by_source_ref与CONTROL_DELTA_COMPONENT_DROPPED，且只检查模型语义陈述。
- 修正无关冻结流程节点被错误注入本批已知语义目标的问题，保留为只读防重来源。

### Git Commits

(No commits - planning session)

### Testing

- [OK] 模型外准备：9 owned、17 attached、26 total、prompt 40787字符。
- [OK] 聚焦回归109 passed, 5 warnings；方案与Agent全量1198 passed, 58 warnings。
- [OK] hermes audit-execution ok=true，warnings/errors均为空；git diff --check通过。

### Status

[OK] **Completed**

### Next Steps

- 从CHECKPOINT_20260830_PACKAGE75_MODEL_FREE_BOUNDARY_ACCEPTED.md恢复，选择一次有界第75包语义重放或第76包模型外闭包。

## Session 51: 第 76 包安全性摘要模型外边界验收

**Date**: 2026-08-30
**Task**: `phase5-slice61bn-package76-safety-summary-boundary`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成第 76 包安全性指标摘要与后续 AE 定义的模型外边界。父级识别并修复“后续来源只写入元数据、未进入真实提示”的假闭包，保持第 77-80 包所有权不变。

### Main Changes

- p982/p983 固定为安全性分析背景，不形成入排候选；所有拥有来源禁止升格。
- p985-p1024 全部以只读附加来源进入提示，p988/p1023 的 AE 与病史边界可直接核对。
- 新增准备证据和 hydrated gate 回归，阻断元数据假闭包、候选升格与处置漂移。

### Testing

- [OK] 模型外准备：5 owned、47 attached、52 total、prompt 51527 字符。
- [OK] 第 76 包 24 passed；聚焦 198 passed；方案与 Agent 全量 1198 passed, 58 warnings。
- [OK] `git diff --check` 与 `audit-execution` 通过。

### Status

[OK] **Completed**

### Next Steps

- 从 `CHECKPOINT_20260830_PACKAGE76_SAFETY_SUMMARY_BOUNDARY_ACCEPTED.md` 恢复，进入第 77 包 AE/TEAE 定义、除外情形与筛选前病史边界的最小来源闭包。

## Session 52: 第 77 包 AE/TEAE 与给药前病史边界验收

**Date**: 2026-08-30
**Task**: phase5-slice61bo-package77-ae-teae-history-boundary
**Branch**: codex/phase5-clinical-facts-profile

### Summary

完成第 77 包模型外来源闭包和父级临床语义边界验收。AE/TEAE 定义与五类不作为 AE 记录情形不会升格为筛选/基线入排门槛；给药前入排复核和给药后 AE 记录保持独立。

### Main Changes

- body.p985-p994 保持 10 个拥有来源，41 个背景与后续定义来源真实进入只读提示闭包。
- 补齐研究者判断、加重、致检查疾病、高于预期、未恶化及 TEAE 双路径的确定性门禁。
- 修复共享 runner 对 CodeBuddy 结构化 429 且退出码为 0 的错误成功判定。

### Testing

- [OK] 第 77 包 32 passed；相邻回归 112 passed。
- [OK] 方案与 Agent 全量 1198 passed, 58 warnings。
- [OK] 治理工具单元测试 16 passed；git diff --check 与 audit-execution 通过。

### Status

[OK] **Completed**

### Next Steps

- 从 CHECKPOINT_20260830_PACKAGE77_AE_TEAE_HISTORY_BOUNDARY_ACCEPTED.md 恢复，进入第 78 包 SAE 定义与严重性标准的最小模型外来源闭包。

## Session 53: 第 78 包 SAE 严重性模型外边界验收

**Date**: 2026-08-30
**Task**: phase5-slice61bp-package78-sae-seriousness-boundary
**Branch**: codex/phase5-clinical-facts-profile

### Summary

完成第 78 包 SAE 定义、任一严重性标准与住院除外清单的模型外来源闭包。所有内容保持为治疗期安全性分类，不倒灌为筛选或基线入排门槛。

### Main Changes

- `body.p995-p1006` 保持 12 个拥有来源，33 个前接、流程和后续来源真实进入只读提示闭包。
- 固化 OR、死亡结果、实际危及生命、重大干扰、住院因果和研究者综合判断语义。
- 新增 `p1011` 与 `p1012` 独立来源单元回归，驳回将两个相邻备选项合并为一个原子条件的建议。

### Testing

- [OK] 模型外准备：12 owned、33 attached、45 total、prompt 48398 字符。
- [OK] 第 78 包 37 passed；相邻回归 149 passed。
- [OK] 方案与 Agent 全量 1198 passed, 58 warnings；治理工具 16 passed。

### Status

[OK] **Completed**

### Next Steps

- 从 `CHECKPOINT_20260830_PACKAGE78_SAE_SERIOUSNESS_BOUNDARY_ACCEPTED.md` 恢复，进入第 79 包 `body.p1007-p1014` 的最小模型外来源闭包。

## Session 54: 通用控制点链真实冒烟与D001只读回放暂停

**Date**: 2026-08-31
**Task**: `phase5-clinical-facts-profile`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成通用控制点链的同会话候选发布门禁和词汇中立真实模型冒烟。随后以同一harness启动D001 II期只读异构回放，按用户要求在第6个发现批次执行中无损暂停。

### Durable State

- 中立冒烟：`runs/protocol_control_smoke/quality-positive-control-packed48-v4-20260831/run_record.json`，正式目录未物化。
- D001数据库：`runs/protocol_control_replay/d001-phase-ii-20260831/data_v2/enrollment-review-v2.sqlite3`。
- 控制任务：`3259ab5f070447c3938ff2de5f45c9cd`；0001-0005完成，0006中断，0007-0039及闭包未开始。
- 来源SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。
- SAR未开始；`claims_complete=false`。

### Status

[PAUSED] **Recoverable, not completed**

### Next Steps

- 从`CHECKPOINT_20260831_D001_READONLY_REPLAY_PAUSED.md`恢复，优先复用现有SQLite任务和检查点；禁止直接新建重复全量回放。

## Session 55: D001 发现链恢复、性能诊断与无损暂停

**Date**: 2026-08-31
**Task**: `phase5-clinical-facts-profile`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

复用既有 D001 SQLite 任务和冻结快照，完成失败步骤恢复和第11–19发现包。随后根据真实耗时确认固定48单元、39包串行本地27B路线不具备产品可用时效，在第19包落盘后中断第20包并暂停。

### Durable State

- D001任务：`3259ab5f070447c3938ff2de5f45c9cd`，`completed=19 / running=1 / queued=20`。
- 数据库：`runs/protocol_control_replay/d001-phase-ii-20260831/data_v2/enrollment-review-v2.sqlite3`。
- 来源SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。
- 最近单包耗时中位约409秒；服务无排队，暂停时`active_requests=0`。
- 聚焦恢复与通用性验证`54 passed`，语法和差异检查通过。
- DeepSeek API只完成模型目录探测，未发起语义请求。
- 恢复链文件仍未跟踪；未提交、未发布、未清理。

### Status

[PAUSED] **Recoverable, not completed**

### Next Steps

- 从`CHECKPOINT_20260831_D001_DISCOVERY_PERFORMANCE_PAUSED.md`恢复。
- 不直接继续第20包；先结合用户可能提供的独立VLM API，冻结VLM/LLM职责、token预算分包、有限并发、模型路由和时效/费用验收合同。

## Session 56: GLM-5.3-Flash 独立视觉适配离线验收

**Date**: 2026-08-31
**Task**: `phase5-independent-glm53-vlm-20260831`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

建立智谱 `glm-5.3-flash:high` 共享视觉核验适配层，并复核方案控制发现链的性能改造。视觉模型目录和鉴权通过，但真实图片请求因 provider code `1113` 被拒绝，因此只接受离线合同，不接受“各业务 harness 已启用”或真实视觉完成声明。

### Main Changes

- 独立 VLM 配置、图片输入、页级来源锚点、来源保真和余额/鉴权/限流失败关闭已完成，且与 OCR 和各语义 Agent 隔离。
- 新任务按输入令牌和预计输出预算自适应分包。
- 删除未接入持久化 `JobRunner` 的并发和指标表面；当前同一任务仍为串行执行。
- worker_03 误删重建方案控制规划模块后，父级恢复既有行为合同并保留事故记录。

### Testing

- [OK] 聚焦合同与回归：`110 passed, 5 warnings in 3.71s`。
- [OK] BigModel 模型目录与鉴权；目标模型存在。
- [BLOCKED] 最小图片 completion：HTTP 429 / `1113`，无成功视觉结果或性能数据。

### Status

[PARTIAL] **Offline accepted; live visual call blocked**

### Next Steps

- 从 `CHECKPOINT_20260831_GLM53_VISION_ADAPTER_OFFLINE_ACCEPTED_LIVE_BLOCKED.md` 恢复。
- 账户具备额度后先做两页小型视觉冒烟，再接入需要原始页核验的业务 harness；D001 旧任务继续保持暂停。

## Session 57: 智谱 Coding Plan 独立视觉模型真实连通验收

**Date**: 2026-08-31
**Task**: `phase5-zhipu-coding-plan-vlm-20260831`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

核对本机 OMP 的真实 provider 合同后，确认此前 429 / code 1113 来自应用仍使用公共 `/api/paas/v4` 端点。独立 VLM 已迁移到 Coding Plan `/api/coding/paas/v4`，并完成严格真实视觉请求。

### Main Changes

- 默认 provider 改为 `zhipu-coding-plan`，保留 `bigmodel` 兼容；模型 `glm-5.3-flash`、推理强度 `high`。
- 运行时应用继续使用独立环境变量，不耦合 OMP 凭据数据库；主启动 `.env` 已安全同步现有 Coding Plan 凭据。
- live 测试由“远端错误也视为分类成功”收紧为任何远端错误都失败。
- 三 worker 并发写共享适配器导致截断的事故已由父级复核修复并记入后续单写者约束。

### Testing

- [OK] 适配器、配置和测试语法编译。
- [OK] 合同与相邻回归：`44 passed, 1 skipped`。
- [OK] 真实视觉连通：`1 passed in 4.73s`。
- [OK] `audit-execution` 无警告、无错误；执行过程文件已归档。

### Status

[OK] **Shared adapter and live connectivity accepted; business harness integration remains pending**

### Next Steps

- 从 `CHECKPOINT_20260831_ZHIPU_CODING_PLAN_VLM_LIVE_ACCEPTED.md` 恢复，先做单页最小业务调用和来源定位验证，再按页面风险选择性接入；不得整份方案重复视觉识别。
- D001 旧回放继续无损暂停。

## Session 58: 选择性页面视觉核验规划验收

**Date**: 2026-08-31
**Task**: `phase5-selective-vlm-page-triage-20260831`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

建立内容中立的页面风险规划：原生文字优先，只有扫描、复杂版面、结构异常或OCR低置信页进入独立GLM视觉核验。补齐来源声明、计划缺图和远端错误失败关闭，并通过真实单页调用。

### Verification

- 聚焦：`56 passed, 1 skipped`。
- 扩展：`326 passed, 2 skipped`。
- 真实视觉：`1 passed in 5.50s`。
- 全库：`3425 passed, 4 skipped`；冷启动回归已修复。
- 已知既存失败：D001只读检查点的v1.5提示哈希漂移；旧锚点未改。

### Status

[OK] **规划与显式单页调用接受；持久化服务接线待下一切片**

### Next Steps

- 从`CHECKPOINT_20260831_SELECTIVE_VISION_PAGE_TRIAGE_ACCEPTED.md`恢复，新增独立观察侧车持久化和证据处理后置钩子。
- D001任务继续保持19个完成检查点后的无损暂停。

## Session 59: 选择性页面视觉核验用户闭环

**Date**: 2026-09-01
**Task**: `phase5-selective-vision-user-control-20260831`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成冻结证据修订的页面视觉核验查询、失败范围、重试/取消与证据工作台中文展示。父级独立发现并修复完整修订和基础修订的任务身份错链，然后完成三档宽屏真实浏览器验收。

### Verification

- 后端聚焦 `41 passed`；services + API `610 passed`。
- 前端聚焦 `13 passed`；全量 `525 passed`；构建通过。
- Playwright 1080P/2K/4K 新面板和相邻证据回归 `9 passed`；Codex 已查看 1080P/4K 截图。
- `review-gate` 和 `audit-execution` 通过，执行过程文件已归档。

### Status

[OK] **本切片接受；Phase 5 仍为进行中**

### Next Steps

- 从 `CHECKPOINT_20260901_SELECTIVE_VISION_USER_CONTROL_ACCEPTED.md` 恢复，用新建隔离快照和一页中性风险资料运行真实端到端闭环。
- D001 继续无损暂停，不恢复第 20 批。

## Session 60: 单页选择性视觉真实端到程验收

**Date**: 2026-09-01
**Task**: `phase5-selective-vision-single-page-e2e-20260901`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

使用隔离冻结修订和一页内容中立风险资料，完成从选择性视觉入队到 OMP 等价智谱 Coding Plan 真实调用、不可变观察落库和用户查询投影的闭环。

### Main Changes

- 新增默认跳过、显式启用的真实单页端到程测试。
- 父级将合成页图从 Pillow 传递依赖改为 Python 标准库 PNG 生成。
- 追踪启动链后确认 `app.config` 已负责从应用根目录 `.env` 加载独立 VLM 配置，未重复复制密钥。

### Verification

- [OK] 真实 Coding Plan 单页闭环：`2 passed in 21.31s`。
- [OK] 相邻回归：`109 passed, 2 skipped in 18.58s`。
- [OK] zsh 语法、Python 编译、目标 diff 检查、review gate 和执行审计通过。
- [OK] 执行过程文件已归档。

### Status

[OK] **单页真实闭环接受；Phase 5 仍未完成**

### Next Steps

- 从 `CHECKPOINT_20260901_SELECTIVE_VISION_SINGLE_PAGE_E2E_ACCEPTED.md` 恢复，先建立视觉观察到事实规范化候选的最小来源保真合同，不覆盖 OCR。
- D001 任务保持第 19 批后无损暂停。

## Session 61: 视觉观察进入事实规范化候选合同验收

**Date**: 2026-09-01
**Task**: `phase5-visual-observation-normalizer-contract-20260901`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成选择性视觉观察到事实规范化候选提示的最小来源保真接线。观察只补充候选材料或提示 OCR 风险，不覆盖 OCR、有效文本和定位器，也不能绕过正式事实发布门禁。

### Main Changes

- 新增观察附件合同、运行级观察范围冻结、执行期漂移复核和调用级观察选取。
- 无观察任务保持旧幂等键兼容；有观察任务按观察身份集合形成新运行范围。
- 父级修复 Pydantic after-validator 返回副本的问题。
- 补齐跨资料版本排除和视觉提示注入不得发布两条负向端到端回归。

### Verification

- [OK] 聚焦测试：`14 passed`。
- [OK] 受影响层：`105 passed in 28.51s`。
- [OK] Python 编译、目标差异格式检查、review gate 和执行审计通过。
- [OK] 三名执行者均为 `zcode/GLM-5.3-Flash:max`，无超时、无 fallback；过程文件已归档。
- [KNOWN] 全量 `tests/v2` 的既存 D001 checkpoint 哈希漂移仍单独保留，未在本切片修改。

### Status

[OK] **候选接线合同接受；Phase 5 仍未完成**

### Next Steps

- 从 `CHECKPOINT_20260901_VISUAL_OBSERVATION_NORMALIZER_CONTRACT_ACCEPTED.md` 恢复，先建立 D001 II 与 MG-K10-SAR III 隔离代表病例验收数据包和逐事件核对清单。
- 运行系统内真实 Evidence Normalizer，并核对事实/Profile 与原始资料定位；D001 旧控制任务继续保持第 19 批后暂停。

## Session 63: 超大父规则层级分段离线验收

**Date**: 2026-09-01
**Task**: `phase5-large-parent-hierarchical-segmentation-remediation-20260901`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

真实冻结输入证明初版一层式分段仍会被引用方括号噪声阻断，并可能退化为 11 次调用。本轮改为根/嵌套限定语继承、逻辑作用域失败关闭和最多 3 个正文单元的小批聚合；未加入项目特异切点。

### Verification

- [OK] 聚焦两套测试：`41 passed`。
- [OK] 只读冻结复杂父规则：4 段 `[3,3,3,2]`，11 个正文来源完整且输入字节不变。
- [OK] 完整协议回归：`1286 passed`；仅既存 D001 提示词哈希漂移失败。
- [OK] 同会话修复、独立测试与最终执行审计通过。

### Status

[OK] **离线层级分段接受；真实 GLM 性能与质量仍待验证**

### Next Steps

- 从 `CHECKPOINT_20260901_LARGE_PARENT_HIERARCHICAL_SEGMENTATION_ACCEPTED_LIVE_PENDING.md` 恢复，新建只读 GLM 分段探针。
- 不恢复 D001 第 20 包或旧 SAR 失败任务；`claims_complete=false`。

## Session 62: 代表受试者验收工具完成并无损暂停

**Date**: 2026-09-01
**Task**: `phase5-representative-subject-acceptance-harness-20260901`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成项目无关的隔离输入清单和只读代表受试者验收运行包，并在尚未启动真实 SAR 31001 流程前按用户要求无损暂停。

### Verification

- [OK] 独立 Coding Plan 视觉脱敏连通：`1 passed`。
- [OK] 父级相关回归：`135 passed, 1 deselected, 5 warnings`。
- [OK] 编译、目标差异格式、项目特异硬编码扫描、review gate 和执行审计通过。
- [OK] 暂停时无本轮 V2、验收包或模型请求进程。

### Status

[PAUSED] **工具准备已接受；真实代表病例和 Phase 5 均未完成**

### Next Steps

- 从 `CHECKPOINT_20260901_REPRESENTATIVE_SUBJECT_ACCEPTANCE_PREPARED_PAUSED.md` 恢复。
- 先检查 oMLX 8001 和 MTPLX 8002，再创建 SAR 31001 的新隔离副本；不得复用旧验收产物。
- D001 继续停在第 19 包后，不恢复第 20 包。

## Session 64: Phase 5 环境门禁、SAR 定向修订与无损暂停

**Date**: 2026-09-02
**Task**: `08-22-phase5-clinical-facts-profile`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成 worktree 显式环境合同、`DECONSTRUCT_GLM_API_KEY` 配置入口和启动凭据/端点预检。受控 SAR 新作业已推进到修订 14：`IN-06` 的 9 项问题已清零，只剩 `EX-07` 的例外作用域和蠕虫感染漏项。局部反馈子项作用域的通用缺陷已修复，聚焦回归为 `210 passed`；31001 下游尚未开始。

### Pause

- 已停止隔离 V2 服务 `8910` 和本 worktree 临时静态验收服务，未触碰长期主服务 `8900`。
- 未清理执行包、数据库、模型响应、路由审计或未提交改动。
- Phase 5 保持 `claims_complete=false`；不得为蠕虫感染“6 个月内”猜测筛选/随机/给药锚点。
- 精确恢复入口见 `CHECKPOINT_20260902_SAR_TARGETED_REPAIR_PAUSED.md`。

## Session 65: Qwen3.8-Next-Flash 规范化受控恢复与无损暂停

**Date**: 2026-09-03
**Task**: `08-22-phase5-clinical-facts-profile`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

现行 MTPLX 路由已核实为 Qwen3.8-Next-Flash。通用 Evidence Normalizer 合同经小范围修复后，31001 筛选期首页组成功生成 30 条候选、5 条未解决项和检查点。用户要求暂停后立即停止后续派发并关闭专用服务。

### Pause

- 作业 `67478824...` 保留 `cancel_requested`，进度 `1/15`；第二页组无持久结果。
- `8910` 已停止；MTPLX `8002` 无活动请求；未触碰 OCR `8001` 与主应用 `8900`。
- SQLite `quick_check=ok`，主库哈希 `2d19774519ec67c8f9ad75eda4e25c7dc886eaf9677b2d617a51a52aff7c876c`。
- `claims_complete=false`；恢复入口为 `CHECKPOINT_20260903_NEXT_FLASH_NORMALIZATION_PAUSED.md`。

## Session 66: Phase 5.5 页级合同与产品自有 harness

**Date**: 2026-09-05
**Task**: `09-05-phase55-dual-vlm-page-review`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成 R3 ClausePack、页级合同、确定性对账和产品自有单阶段双 VLM 调度。产品读道仅从显式 env 直连指定端点，不借用 Hermes、OMP 或 ZCode。

### Verification

- [OK] 聚焦合同与调度：`41 passed`。
- [OK] 完整 `tests/v2`：`3700 passed, 3 skipped, 2 subtests passed`。
- [OK] 编译和定向差异格式检查通过。

### Status

[IN PROGRESS] 持久化与真实复跑待完成；显式 env 尚缺 main-B `CMS_SMK_API_KEY`，本轮未发送真实临床页面。Phase 5 保持 `claims_complete=false`。

## Session 67: Phase 5.5 页级持久化与 R3 Evidence Normalizer 接线

**Date**: 2026-09-05
**Task**: `09-05-phase55-dual-vlm-page-review`
**Branch**: `codex/phase5-clinical-facts-profile`

### Summary

完成迁移 0020 的页级判读/对账/覆盖追加写持久化，并把采信页级记录以内容寻址方式接入 Evidence Normalizer。R3 新作业以双主读对账后的事实、信号、手写和冲突为权威，OCR 降为侧车；历史 Phase 5 作业仍保持原输入兼容。修正成功复读与失败覆盖身份碰撞，收紧空页价值声明门禁。

### Verification

- [OK] 聚焦测试最高 `190 passed`。
- [OK] 完整 `tests/v2`：`3714 passed, 3 skipped, 2 subtests passed`，无失败。
- [OK] 编译通过；未调用真实模型或外部 harness。

### Pause

- `8001/8002/8910` 关闭；`8900` 属外部 Vibe-Research，不触碰。
- worktree `.env` 缺失，main-B 显式凭据仍缺；真实三端点预检阻断。
- Phase 5/5.5 均未完成，`claims_complete=false`。
- 完整 GPT-6 接管文档：`.trellis/tasks/09-05-phase55-dual-vlm-page-review/HANDOFF_20260905_GPT6_PHASE55_R3.md`。
