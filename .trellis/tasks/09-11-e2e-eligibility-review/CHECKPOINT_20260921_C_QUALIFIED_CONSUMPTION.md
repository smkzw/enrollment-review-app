# CHECKPOINT 2026-09-21：C链资格消费接入完成（WP05核心）+ WP03/A01 + 评测证据harness

## 追加（同日晚些）

### 4. WP03/A01 位图正文门控（提交 9e5621ec）
- `decide_route_detailed`新增A01混合页降级：正文是整页位图（image coverage≥0.5）
  且文字层只挂页边（行带覆盖≤0.2）→ VISION_OCR。纯版面几何合取，无字符数启发；
  只降级不升级——真文本页/可检索扫描PDF不受影响。
- `NativePage`新增`large_image_coverage`（钳制位图面积占比）。
- 真实blob扫描验证：现有纯扫描页（93-98%位图、零文字）本就走VISION_OCR，
  文本页维持native——零既有路线变化，纯前瞻保护。
- 新增6个场景测试（tests/v2/evidence/test_page_processor_a01.py）全过。

### 5. 方法采用评测证据harness（用户接手路径已打通）
- `app/services/binding_evaluation.py`：gold拆分校验+打分+类型化
  `BindingEvaluationManifest`落盘（evaluation_manifest工件）。
  方法字段直接取自verify_completed_binding_qualification重建结果，
  与`require_evaluated_binding_method`按构造一致。
- `scripts/build_binding_gold_split_template.py`：从真实资格任务生成137条
  标注模板（expected/forbidden留空，参考清单仅作对照，不从模型输出派生金标）。
- `scripts/record_review_method_adoption.py`：**用户亲自行使**采用决定的工具
  （写入ReviewMethodApproval + review-method-adoption gate）。AI不得代跑。
- 13个纯逻辑测试全过（tests/v2/services/test_binding_evaluation.py）。

### 用户接手路径（C链最后一步）
1. `python scripts/build_binding_gold_split_template.py --qualification-job-id d37600378dea4952935bb098c4f007d7 --out gold.json`
2. 依据原件/方案独立标注 gold.json（expected/forbidden + annotated_by）
3. `build_binding_evaluation_manifest(...)` 产出评测清单（manifest sha）
4. 审阅指标后：`record_review_method_adoption.py --manifest-sha <sha> --approving-principal ... --approval-source-file ...`
5. 配置`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID=<gate_result_id>`后
   `POST .../prepared-review-workflows/47c4ef67bf0a45ee.../publish`

## 本次完成

### 1. get_coverage持久化比对修复（阻塞投影的硬bug）
- `PageCoverageEntry`新增`source_policy_kind/verification`为payload-only字段（无ORM镜像列），
  `get_coverage`的entries表比对把所有历史覆盖记录误判为不一致
  （`PersistedContractInvalid: 页覆盖处置关联表与合同正文不一致`）。
- 修复：`app/storage/page_review_repository.py`比对时剔除`source_policy_*`两个无镜像键。
  payload完整性仍由`payload_sha256`保证，不弱化校验。
- 同时修复`test_reread_predecessor_is_source_bound...`的措辞不匹配（改为当前报错文案）。

### 2. 投影消费资格核对结果（WP05完整资格消费）
- `_load_binding_predicate_fact_ids`不再使用未核实的双路候选交集，
  改为：定位authority匹配的predicate candidates任务→定位其对应的已完成
  `binding_qualification`任务→`verify_completed_binding_qualification`完整重建→
  仅取`structurally_valid && dual_agreement`配对的fact选择。
- 映射对全部官方谓词完整（未核实=空表→evaluator按observation未核实UNKNOWN）。
- 投影侧expectations/source_gaps无条件传递（ER-03修复已在位）；
  `component_review`仅在trigger为definite时移除观察/记录类gap（合理范围）。

### 3. 验证结果
- IN-01 = inclusion_met（直接投影+API双重验证，6个fact refs，无gap）。
- 68条indeterminate是正确安全行为，原因有二：
  a) 候选任务对137个谓词全部求值，但只有8-9个谓词在55条已发布事实中找到候选
     （B链事实覆盖是确定性上限，不是C链管线缺陷）；
  b) 跨章control的采用与消费仍在前方。
- 测试：storage/domain/llm套件与基线对比修复4个、无新增失败
  （其余为MTPLX/云环境依赖的预存失败）。
- 提交：0db7b1b3 已推送GitHub。

## C链当前全貌（决策所需）

已完成管线（全部completed）：
- prepared_review_workflow 47c4ef67（含predicate+control qualification子任务）
- predicate_binding_candidates 4c87dff9 → binding_qualification d3760037（21对/9身份，5身份双路一致）
- control_binding_candidates bf61e93e → binding_qualification 2bee93ec
- protocol_control_execution 09084347（23:43完成，175检查点）

官方ReviewRun发布的剩余前置（不可由AI自授权，设计边界）：
1. 方法采用评测证据：`binding_semantic_correspondence`评测清单
   （`BindingEvaluationManifest`：source_corpus+gold_split+scoring_report+methods+observed_metrics）。
   gold_split须独立人工标注（评测文档：gold不入生产Agent；legacy K10项目协议不同，
   不能作当前链gold）。
2. 用户方法采用：`ReviewMethodApproval`（approving_principal+approval_source）+
   `review-method-adoption` gate（gate_results中尚无）。
   `authorized_clinical_adoption`为`Literal[False]`硬编码——资格阶段永不自授权。
3. 二者齐备后：`POST .../prepared-review-workflows/{id}/publish`
   （`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`当前为空，需配置）。

## 下一步（按V4顺序）

1. WP03：页manifest全覆盖检查（A01：只有页码文字层、正文扫描场景）。
2. WP05余项：control资格消费接入投影（跨章处置已有PENDING_CONTROL_APPLICABILITY基础）。
3. 评测harness脚手架（corpus/gold split/scoring程序），gold标注与采用决定留给用户。
4. WP06前端工作台（B1-B4）。
- B链事实覆盖（55条）是当前条款确定性上限；更多证据文件上传→更多事实→更多definite。

## 续（同日第二轮）：WP03收尾 + WP05审计 + WP06问题队列

### 6. WP03 A02–A09 审计结论（4f244670）
- 逐场景核对既有机制与测试：旋转canonical坐标（pdf_native+executor测试）、
  重复文本降级（locator+risk测试+R13不按文本去重）、分段OCR区域隔离
  （segmentation+分段请求合同）、手写对账主A优先（reconciliation+回归测试）、
  标量语法保真（test_page_scalar_grammar）、数值事实必须显式单位（合同校验+
  unitless测试）——均已实现且有测试。
- 补齐两个薄弱钉扎（tests/v2/evidence/test_wp03_scenarios.py，7个测试）：
  A08 低置信INFORMATIONAL不阻断+OCR提示禁补字；A09 未知/空内容→显式FAILED页
  （缺页不静默丢弃）+record_time与date_range字段级分离（记录日期≠事件日期）。

### 7. WP05控制消费审计
- 控制资格任务（2bee93ec）23个控制原子全部no_candidates_in_supplied_input、
  0对双路一致——上游候选为空（55条基线事实不含控制相关观察）。
- 无可消费数据；模板级PENDING_CONTROL_APPLICABILITY处置（R05）即当前正确状态。
  完整控制消费路径已在frozen_review_calculation（control_input/control_selections）
  就位，等待上游证据。

### 8. WP06 问题队列（c8568be6）
- EligibilityWorkbenchPage新增问题队列：风险/冲突/未决按根因（投影gapType）
  聚合+条款影响计数；组内全量渲染不截断；点击即复用条款详情/原件下钻。
- 前端GapType联合类型与labels卫生测试补齐control_applicability_pending。
- 验证：工作台12/12、全前端583/583、tsc清；ego-browser实测1080P/2K/4K
  真实数据（68条→1根因组）渲染与下钻正常。

### 下一步
- WP06余项：issue详情增强（对象/时间/冲突各方/具体动作聚合显示）。
- WP07：更正/补证增量复用与影响闭包。
- WP08：30–150页规模验证与全仓剩余验收。
- C链官方发布：等待用户gold标注与方法采用（人机边界，见上文第5节）。

### 9. WP06 issue详情动作指令（9c3c3479）
- 投影线新增action_owner/action_detail/action_evidence（来自domain.policies
  ACTION_CONTENT注册合同，仅有缺口时给出）；API DTO、前端视图模型、详情面板
  "建议动作·责任方+动作+可接受证据"贯通。
- 验证：API对68条缺口条款全部返回动作字段；前端584/584、tsc清；
  1080P实测渲染正常。对象/时间经fact_refs下钻呈现，冲突各方经
  病史不一致横幅+档案页呈现（既有能力）。

### WP06退出标准对照（当前数据前沿）
- 默认风险/冲突/未决队列+根因聚合+条款影响计数：✅（问题队列）
- 全量条款/事实/原件下钻：✅（队列→详情→原件三栏贯通）
- 具体动作+可接受证据：✅（本节）
- 不用top-N隐藏：✅（全量渲染+测试钉扎）
- 1080P/2K/4K真实浏览器：✅（截图验证）
- 保存系统审核报告无需逐条勾选：属正式ReviewRun发布路径（方法采用门后）。

### 10. WP07 机制审计（本轮完成审计；集成重放归WP08真实闭环）
- A29（新证据使"范围内未发现"失效）：机制在位——检索范围由当前完整修订
  清单构建并冻结scope_sha256（build_judgment_search_scope）；新资料→新清单
  →新scope哈希→旧"未发现"结果无法挂接（test_current_target_and_scope_mismatch
  _rejected拒绝作用域不匹配；test_full_not_found_pair_binds_to_native_absence
  _status钉扎缺席状态绑定）。失效按证据集合依赖，不依赖直接fact链接。
- A25（补证/字段更正/元数据更正→影响闭包、旧报告不变）：追加写修订工作流
  （evidence_revision_builder/workflow）、更正影响反向索引
  （test_fact_correction_impact_queries：定位/事实/冲突成员/档案来源反向索引
  +有界图加载）、review_runs不可变。机制与单测在位。
- A15（旧双读历史可读、不改标签）：legacy读取路径有专项测试
  （test_page_review_legacy_read）。A12已由WP02来源政策合同覆盖。
- 剩余：端到端集成重放（三种更正各一次→给出实际重算闭包/未重算理由清单、
  旧报告hash比对）——按WP08"先单例后规模"用真实运行完成，不以源码会商代替。

---

# 复盘（2026-09-21 无损暂停）

## 做了什么（本轮全部提交）
- WP08单例重放①②完成：元数据更正闭包=仅元数据修订+1；字段更正闭包=新事实头
  +期望重算+档案修订，且实测"更正被绑定引用的事实→IN-01由满足转未决"
  （陈旧绑定不盲复用的设计语义首次跑通）。
- 重放③补证上传全链路打通：增量预览→过期基准拒绝→提交→OCR→风险核对边界
  （6个blocking风险逐项核对后自动续跑）→base修订→完整修订构建→激活切换
  （activation_seq=3追加写事件）。
- 真实缺陷修复×2：①native_text定位闭包核验缺工件库（补证PDF是首个带文字层
  的页面，暴露该路径从未被测过）；②模型目录401导致预检拒绝启动（显式配置
  模型名时不再强依赖目录）。
- 模型路由按用户裁定重置：OCR=本地GLM-OCR-bf16@8001；main-B=cms-router的
  cms-model（云端）；本地Flash-Next停用并清理。

## 踩了哪些坑
1. payload-only合同字段+ORM镜像比对 → 全部历史覆盖记录被误判不一致（已修）。
2. 修正"一个年龄事实"时，同值事实存在另一发布通道（demographics vs
   demographic_age），只改一个不改判定——重复发表事实的更正闭包是产品级问题，
   需在更正工具中提示同值兄弟事实。
3. omlx8001的GLM-OCR、20128的cms-model都是现成可用资源，但.env遗留配置
   （mtplx本地、MiniMax-M3）与用户最新决策脱节——配置漂移导致两次返工。
4. 模型目录接口401把预检卡死：显式配置模型名的场景不该强依赖目录接口。
5. rg -r/--include等参数误用浪费了若干轮排查（工具习惯问题）。

## 没做什么 / 下一步
- 页判读4949b60b…运行中（云端双路），完成后按REPLAY_LOG"接手步骤"1-5收尾。
- 事实重整→投影重算→旧件哈希终验（③的收尾）。
- 用户接手：gold标注→评测→方法采用→publish（人机边界，工具已备）。
- 30页级规模验证（WP08后半）与跨方案验证。
- control资格消费：等B链新证据产生控制相关事实后重跑绑定/资格。

---

# 补充复盘（2026-09-21 第二次暂停：云端配额）

## 做了什么
- 把模型路由整改收尾：页判读/绑定/资格/检索/判断的main-B=cms-router的
  cms-model；OCR=本地GLM-OCR-bf16@8001；DeepSeek规范化也改走cms网关
  （官方DeepSeek密钥已失效）。
- 补证链路在云送上全部打通：页判读遇到网关长流截断（无finish_reason），
  3次重试失败后第4次全绿（25页零失败，覆盖7fa21a9b…）；补证材料的元数据
  "待确认"按R14规则正确阻断了规范化，人工确认后闭环。
- 完整修订因元数据变化重建并激活（complete-d6487542, activation seq 4）。
- A25④旧件不变终验全部通过（旧修订/清单/快照/事实旧行/元数据历史全部
  原样保留，一切更正均为追加写）。

## 踩的坑（新增）
1. cms网关对最长页的流式判读会间歇性截断（无finish_reason），同一页连续
   3次失败——重试是当前唯一对策，根治需网关侧超时/重连配置。
2. "元数据确认晚于页判读"会触发完整修订重建→已完成的页判读覆盖与修订
   失配→页判读返工。正确顺序：先确认元数据，再页判读。
3. 官方DeepSeek密钥早已失效，且cms网关的deepseek上游与智谱共用配额——
   云端配额是全链路的单点依赖（2026-09-25 20:14重置）。

## 配额恢复后的接手路径
见 runs/execution/wp08-singleton-replay-20260921/REPLAY_LOG.md 末节
（retry任务→轮询→投影重算→哈希记录→推送，共4步，无需再探路）。

---

# 2026-09-22 模型路由二轮调整（用户裁定）

## 已生效
- 规范化 → **ollama-cloud / deepseek-v4.1-flash (max)**：密钥取自 OMP
  凭据库（agent.db auth_credentials 的 ollama-cloud 行，与 OMP provider
  同源），实测对话通过；事实重整任务 68ff9156 16步全绿（重放③闭包，
  投影哈希 f2ae0717…，69条未决）。
- 页判读 main-A → **opencode-go / muse-spark-1.3-contributor (high)** 的
  接入代码已实现（新 provider + 专用密钥解析，绝不回退他厂密钥），
  **待用户在 .env 填 OPENCODE_API_KEY= 一行后重启即生效**（密钥不经过
  任何会话——此前要求用户明文提供密钥是错误做法，已纠正）。
- main-B = cms-router 的 cms-model（此前已生效）。

## 排障记录
- opencode.ai/zen/go 对直连有 Cloudflare 防护：无键请求能到鉴权层
  （报 Missing API key），带无效键报 Invalid API key——说明带有效键的
  常规请求可通；但 OMP 的浏览器 OAuth cookie（钥匙串 cookie.opencodego，
  Fe26.2 封装）不能被应用直接复用（1010 拦截），所以应用必须用 API key。
- 注意：OMP 默认 profile 的 auth_credentials 里没有 opencode-go 行——
  用户所称"用 API key 配置"可能配置在 OMP 某个 profile 或 omniroute
  后台；无论在哪，只要 key 进入 .env 的 OPENCODE_API_KEY 即可。
