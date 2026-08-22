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

[OK] **Completed**

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
