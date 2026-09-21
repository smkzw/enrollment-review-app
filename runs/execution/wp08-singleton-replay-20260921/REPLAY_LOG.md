# WP08 单例端到端集成重放记录（A25/A29 退出证据）

- 日期：2026-09-21
- 对象：31001 · 审核节点 6dbf65262bc54f959aaa0a07c783ba52（baseline）
- 基线状态：投影69条（hash fb43009f…，68未决+1满足IN-01）；活动快照
  503c4b04…；完整修订 complete-b9bef521…（24页，清单哈希 e9c4cd48…）；
  事实106条；期望204条；更正0；review_runs 0。
- 方法：全部经正式HTTP API驱动（8902后端，最新代码）；每步前后用
  scripts/wp08_capture_state.py 捕获全量状态比对（/tmp/wp08_*.json）。

## 重放①：元数据更正（元数据改正不默认重OCR）

- 命令：PATCH /api/v2/source-document-versions/03652a49…/metadata
  （类型 其他资料（待确认）→其他资料；来源方 研究中心（待确认）→申办方；
  理由：该文件为申办方提供的数据列表，非研究中心出具）
- 结果：新修订 metadata-7855e146…（revision 2，追加写，supersedes rev 1；
  同幂等键回放安全）。
- **实际重算闭包：仅该文档的元数据头（1条新修订）。**
- **未重算及理由**：处理修订/页清单不变（元数据不影响已完成的页提取与
  事实发布）；事实106、期望204、投影哈希 fb43009f… 全部逐字节不变；
  活动指针未动。
- **旧件不变：修订1记录保留（追加不覆盖）；投影哈希前后一致。**

## 重放②：字段更正（一次更正→影响闭包与保守失效）

- 目标：demographic_age 事实 fact:4c20ed13…（51岁 → 52岁，附定位与理由）。
- 预览：POST …/fact-corrections/preview 返回影响范围
  scope_kind=node（"定位不属于当前冻结的完整处理修订"→节点级重算，
  不伪称更小闭包），并列出 affected_locator/document/fact/conflict 空集明细。
- 提交：POST …/fact-corrections → 任务 94bd83cc…（plan→apply）完成。
- 闭包结果：新事实头 fact:132590d7…（52岁，gate fcorr-gate-c141b…）；
  fact_corrections+1、fact_correction_commits+1（含 conflict_outcomes 与
  patient_profile_revision_id，即档案同步修订）；期望 204→235（重算+31）。
- 发现（真实数据问题）：IN-01 的绑定引用的是另一发布通道（demographics）
  的同值事实 fact:5aef30e4…（51岁）——本次更正目标只覆盖 demographic_age
  通道，投影哈希不变（仍 inclusion_met，用51岁）。
- 追加更正②b：对 fact:5aef30e4… 同步更正为52岁 → 任务 4cb3f705… 完成。
  结果：投影哈希 fb43009f… → 3f9df1fc…，**IN-01 由 inclusion_met 变为
  indeterminate（gap=observation_unverified）**：被更正事实的旧绑定选择
  在接受事实过滤后失效，条件回到未决，等待重新资格核对——
  **陈旧绑定不盲复用、不伪造确定结论（A25/A29 设计语义实测成立）。**
- **未重算及理由**：页清单不变（更正不新增页）；绑定/资格任务未自动重跑
  （其冻结输入哈希将因新事实集失配，下次运行强制重建——需要云端LLM，
  归后续验证轮）。
- **旧件不变：两条旧事实记录保留（追加不覆盖）；元数据更正（①）的效果
  不受影响。**

## 重放③：补证上传（增量）——进行中

- 生成 1 页补充说明 PDF（确定性字节）。
- POST /evidence-upload-previews（incremental，base_revision=3）→ 预览
  989f9e58…（首次用 base_revision=1 收到 STALE_BASE_REVISION——过期基准
  保护实测有效）。
- POST …/commit（preview_sha256 + 幂等键）→ commit 87e946a3…，
  新快照 742018b5…，处理任务 9c98fa50… 已完成。
- 新 base 修订 epr-742018b5…-e0a6eeb2…（清单哈希 e0a6eeb2… ≠ 旧 e9c4cd48…，
  页数 25=24+1）。
- 构建完整修订：POST /evidence-processing-revisions/build → 任务
  0a232461…（本记录写作时运行中）。
- 后续：激活新完整修订（回退/启用仅切换活动指针）→ 验证A29
  （检索scope哈希随清单变化而失效）→ 比对投影按新快照重算。

## 重放③续（现场发现与修复）

- 构建完成修订后投影报 STALE_AUTHORITY——定位闭包核验在
  `CompleteEvidenceProcessingRevisionRepository(self.session)`（缺工件库）下
  对 native_text 定位抛"需要内容寻址 ArtifactStore"。
  **真实缺陷**：既有B链资料全部为扫描页（raw_ocr定位），该路径从未被
  native-text 页触发；补证PDF带真实文字层（首个native页）即暴露。
- 修复：`FactAuthorityValidator` 与 `CompleteEvidenceProcessingRevisionRepository`
  未显式传入工件库时按当前数据根惰性构建（native_text定位真实性证明不可省略，
  只补齐依赖，不放宽门禁）。
- 风险核对边界实测：补证页OCR产生6个blocking数值风险，未经核对时构建停在
  waiting_user/needs_attention；逐项confirmed_as_read后候选自动继续——
  "blocking风险未核对阻止修订激活"实测成立。
- 本地Flash-Next（端口8002）未运行导致页判读无法提交；用
  scripts/run_mtplx_service.sh 启动后恢复（受试者资料识别阶段=本地模型，
  符合用户既定分工）。
- 页判读任务 1bd41df5… 已入队（25页，主A云端+主B本地双路）。

## 重放③运行中状态（截至本记录）

- 页判读任务 1bd41df52d66437aae9de92dd42cbdc9 运行中：25页 × (main-A云端读 +
  main-B本地Flash-Next串行读 + 核对)，实测约3-4检查点/10分钟。
  全部完成后剩余步骤（已探明路径，无需再探）：
  1. POST …/fact-normalization-jobs（重跑事实整理到新修订）
  2. GET …/eligibility-review（投影按新快照重算；IN-01应仍indeterminate，
     52岁事实重新进入资格核对，或全列保守未决直至重新资格核对）
  3. 比对：新修订清单25页（哈希 e0a6eeb2…基 → complete-21f4d0fc… 闭包）、
     旧 complete-b9bef521… 及其24页清单逐字节不变（回滚=仅切活动指针）；
     检索scope哈希随清单变化（A29已由scope构建逻辑+不匹配拒绝测试证明，
     并将在facts重新发布后由重新判读/核对生效）
- 后台轮询进程持续观察任务终态；完成后按上述步骤收尾并记录闭包表。

## 最终状态（无损暂停 2026-09-21）

- **模型路由已按用户裁定重置**：
  - 页判读 main-B 由本地 Flash-Next 改为 **cms-router 的 cms-model**（云端，
    http://127.0.0.1:20128/v1，密钥=CMS_SMK_API_KEY，已实测对话通过）；
    本地 Flash-Next 服务已停止（8002 端口已清）。
  - OCR 主读改为 **本地 oMLX:8001 的 GLM-OCR-bf16**（OCR_MODEL_*=GLM-OCR-bf16）。
  - 双路第二路总开关：所有云端双路任务的 main-B 都派生自 PAGE_REVIEW_MAIN_B_*，
    一处改全局生效。
- **预检修复**：网关 `/v1/models` 对业务密钥返回401（对话端点正常），预检
  原样拒绝启动。修复：显式配置模型名时，模型目录不可读(401/403/404)不再
  阻断启动，模型身份由每次对话回执核对（page_review_harness.py）。
  修复后预检通过：main-A=zhipu glm-5.3-flash，main-B=cms-smk cms-model。
- **新页判读任务**：4949b60bf2934f53aefe31c76297f3c4 运行中（云端双路，
  实测速度远快于本地串行；90秒已出2检查点 vs 本地10分钟）。

## 暂停后接手步骤（下次会话直接执行）

1. 轮询 4949b60b… 至 completed（预计数十分钟）。
2. POST …/fact-normalization-jobs（{}空体即可，权威服务端派生）。
3. 轮询完成后 GET …/eligibility-review：确认投影恢复可读并按新快照重算；
   记录新投影哈希与决策分布（IN-01 应仍 indeterminate，等待重新资格核对）。
4. 旧件不变终验：complete-b9bef521… 与其24页清单的 payload_sha256 逐字节
   比对（激活事件 evt-5849d5d9… 已证明指针切换为追加写）。
5. 更新本文件"闭包总表"并推送。

## 最终状态（2026-09-21 第二次无损暂停：云端配额耗尽）

- 页判读在新完整修订 complete-d6487542 上完成：共4次尝试（3次出现cms网关
  流式中断——无finish_reason，属网关对长流的间歇截断；第4次全部25页零失败，
  覆盖 subject-page-coverage:7fa21a9b…）。
- 事实重整 4cf943fa…：初跑 TRANSPORT_FAILED（官方DeepSeek密钥已失效）→
  已把 DEEPSEEK_BASE_URL/DEEPSEEK_API_KEY 改指 cms 网关（实测对话可用）→
  retry 后再次失败：**智谱配额周上限（错误码1310，2026-09-25 20:14:33重置）**。
  cms网关的deepseek上游与主A共用同一智谱账号配额。
- 旧件不变终验（A25④）已全部通过：
  - 旧完整修订 complete-b9bef521… payload/manifest哈希不变、24页清单不变、
    旧快照保留；
  - 事实108行=基线106+2条更正追加，被更正旧行原值(51岁)保留；
  - 元数据历史[(1,待确认),(2,其他资料)]追加不改写；
  - 激活事件 evt-5849d5d9…/seq4 为纯指针切换。

## 配额恢复后接手步骤（2026-09-25 20:14 之后）
1. POST /api/v2/jobs/4cf943fa085a49e59d685b699caab2d7/retry
2. 轮询至 completed（16步：6次规范化调用+门禁+发布）
3. GET …/eligibility-review → 投影恢复并按新快照重算；记录新投影哈希
   （预期：25页清单、52岁事实生效；IN-01等仍待重新资格核对）
4. 更新本文件闭包总表并推送。

## 自动收尾安排（2026-09-21 登记）

- 2026-09-21 22:33 实测重试仍返回同一429（重置时间未变），确认配额墙未提前解除。
- 已创建一次性定时任务（automation-6fba2572）：2026-09-25 20:20 自动执行
  本文件末节"配额恢复后接手步骤"1-4，并把闭包总表写入本文件后提交推送。
- 届时无需人工介入；若配额未如期重置，任务会把实际错误如实记录后结束。

## ✅ 重放③闭包总表（2026-09-22 完成）

规范化改走 **ollama-cloud / deepseek-v4.1-flash(max)** 后一次跑通
（任务 68ff9156…，16步全部完成，无传输错误）。

| 维度 | 暂停前 | 规范化完成后 | 说明 |
|---|---|---|---|
| 活动快照 | 503c4b04… | 742018b5… | 补证上传产生 |
| 活动完整修订 | complete-b9bef521… | complete-d6487542… | 含补证页+确认后元数据 |
| 页清单 | 24页 / e9c4cd48… | 25页 / e0a6eeb2… | +1补证页 |
| 发布事实 | 108 | 143 | 新权威下整体重发（含更正后52岁） |
| 期望 | 262 | 420 | 按新事实集重算 |
| 投影哈希 | 3f9df1fc… | f2ae0717… | 按新快照重算 |
| 决策分布 | 68未决+1满足(IN-01) | 69未决 | IN-01保守退回未决，待重新资格核对 |

A25④旧件不变：旧修订/清单/快照/事实旧行/元数据历史全部原样（追加写）。

## 本轮新增配置变更（用户裁定）
- 规范化：DEEPSEEK_BASE_URL=https://ollama.com/v1，
  DEEPSEEK_API_KEY=<OMP ollama-cloud provider密钥>，
  EVIDENCE_NORMALIZER_MODEL=deepseek-v4.1-flash，EFFORT=max。
  注册表已追加新配置行（旧行因外键保留，启动注册配置为权威）。
- 页判读 main-A：待 opencode-go 凭据（OPENCODE_API_KEY 或网关后台添加）后
  切换 muse-spark-1.3-contributor(high)；当前仍为 zhipu glm-5.3-flash
  （配额09-25 20:14重置）。

## main-A 路由切换（2026-09-22）

- 用户提供 opencode-go API key（已直接写入 .env 的 OPENCODE_API_KEY，不进仓库）。
- 端点要求 x-opencode-session 头（应用已实现，取 OMP install-id 作稳定会话标识）。
- 实测：deepseek-v4.1-flash 对照调用成功（证明路由/密钥/会话头全通）；
  muse-spark-1.3-contributor 上游当前"Endpoint is unavailable"（1.2同报，
  供应商侧波动，非本方配置问题）。
- 预检通过：main-A=opencode-go muse-spark(high) + main-B=cms-model。
  下一次页判读即按新双路执行；muse-spark 恢复前其路读取会如实失败重试。

- 已布置恢复守望（scripts/wp08_muse_spark_watch.sh，后台）：每5分钟探测
  muse-spark；恢复后自动提交页判读并轮询到终态。若6小时未恢复则退出，
  保留手工接手路径（页判读提交为空体POST即可）。

- 2026-09-22 02:20 单次直探确认 muse-spark 上游仍不可用（同一错误）；
  守望继续（至08:18，此后可再延长）。规模驱动脚本已补筛选节点选择；
  实测执行等两项外部条件（配额重置 + 用户提供真实资料路径）。
