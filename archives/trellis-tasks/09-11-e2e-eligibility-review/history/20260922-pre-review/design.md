# V3 当前增量设计与实际接点

现行论证：research/ENROLLMENT_REVIEW_AGENT_RECOVERY_V3_20260917.md，先0–1，方案查2.21–2.25，资料查4–8。具体分工见AGENT_ASSIGNMENTS_V3_20260917.md；步骤状态只记implement.md。此文是待执行设计，不是已实现声明。

## 现场已核的两条链
方案：app/api/v2/protocols.py → ProtocolWorkbenchService → protocol_deconstruction_executor（_handle_extract/_handle_generate、_ProtocolSemanticBatchFileCache）与protocol_control_executor（实际重导出protocol_control_execution）→草稿/完整性→ProtocolPublicationService.publish →控制目录与正式规则→下游。
事实：app/api/v2/evidence.py → evidence_upload_service写DIRECT_VISION_PREPARATION → evidence_processing_executor选择original-page-images/v1 →原图处理修订；现行页读/coverage → fact_normalization_command_service/source_adapter/executor → FactPublicationService.publish → Profile/绑定/冻结报告。
有实现不等于运行通过。本次未启动模型、未查询临床库。方案生成/修复的全部实际调用尚需执行者读取完整函数，不能把此短图称全量review。

已存在：官方分包缓存、父条款分段、自适应跨章模块、任务检查点、托管释放、reading_view、事实事务发布。不能从零重复建设。
需重点确认：ProtocolPublicationService只在control_job_id非空时prepare/save控制目录；核UI/request是否确实带共同发布依赖，不凭有函数宣称全部要求共同发布。protocol_control_executor.py只是公共边界，实际逻辑在app/services/protocol_control_execution/。

## P0 短图：方案链真实调用与断点（2026-09-17 Agent A 现场核验）
链：DOCX上传 → `app/api/v2/protocols.py` → `ProtocolWorkbenchService.start_first_deconstruction`（持久job步骤 REGISTER→EXTRACT→RENDER→IDENTIFY→AWAIT_IDENTITY→FREEZE→GENERATE→INTEGRITY→AWAIT_REVIEW→PUBLISH）→ FREEZE落确定性目录（父规则/程序/期别投影，`_handle_freeze`）→ GENERATE（`_run_semantic_generation_with_routing`：默认路由GLM glm-5.3-flash@zhipu-coding-plan，preflight校验凭据+TCP，审计逐attempt落盘）→ `ProtocolDeconstructorRunner.run`（`_plan_semantic_rule_batches`初始3条/批+父条款分段+自适应预算；wire Schema用`allowed_source_span_ids`枚举，source_ref≠来源编号已入提示；每批2次结构修复；`_ProtocolSemanticBatchFileCache`逐批文件缓存）→ `_merge_semantic_batches`（纯拼接+闭合校验，增量可复用）→ `_hydrate_semantic_candidate` → 门禁评估+有界语义修订（上限16轮/每轮≤3条，回归恢复）→ `save_initial_draft`（不可变revision）→ INTEGRITY复核 → 工作台预览（get_draft_detail/comparison）→ 前端`useProtocolControls`自动起控制job并轮询candidate_ready → 发布请求带control_job_id+checkpoint_id（`ProtocolJobFlow` publicationBlocked保证不缺）→ `ProtocolPublicationService.publish`单事务：control_job_id非空才prepare/save控制目录（383/464行）→ 下游。
断点（真实、已核）：B1 草稿仅整轮完成后保存，无逐批增量保存/预览（P0.P1主改动点；批文件缓存已有但工作台不可见）；B2 首读/完整/核对/可发布/发布事件未记入job（P0.P3计量）；B3 本树data_v2无任何已发布RuleSet（B不能复用旧规则，仅fixture调试）；B4 SAR比较附件Downloads未找到（不阻塞，正式DOCX在 `MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`）。环境：MTPLX 8002活（共享勿动）、oMLX 8001停、后端启动 `ENROLLMENT_ENV_FILE=$W/.env .venv/bin/python -m uvicorn app.api.v2.app:create_app --factory --port 8902`、前端 `npm run dev`（/api→8902）。

## 方案增量
复用来源结构与既有作者wire/草稿。短源引用由宿主映射，首次/紧凑/修复与水合必填一致。生成一个合法草稿即持久并只读展示，同一对象续核、续修、发布；预览不获得正式判断权威。
核研究部分/官方父子内容、锚点用途、否定/例外/未知、研究者归属、测量聚合与真实跨章依赖。最多两轮有据小对象修订，无新信息提前停止；格式宿主错误不要求模型重做整份。
共同发布沿现有事务，源歧义与暂不支持要求明确保留，不删难项/恒真代替。源、首次有源草稿、完整草稿、核对、可发布、发布与人工等待分别计量。

## 资料增量
保留original-page-images/v1。其后使用现有JobRunner的新明确读取策略，原生可靠文字或OCR形成原始读数；局部视觉/人工确认形成实际核实依据。ReadingManifest是逻辑名称，先找等价对象，不强制新表。
冻结来源/图像/阅读视图/读取策略/原响应/区域/字段可用性/未决。新来源与legacy双读按判别分支验证，旧记录不改义。只关require_page_review、假造两份VisualFactSource.readings、model_construct或伪Gate均禁止。
同步输入选择、EvidenceNormalizerInput、locator、提示及格式修复、候选gates、共同发布、恢复历史、Profile和审核消费者；一个小切片也须完成这一条链。
OCR不具备可靠坐标就保持页级/文本定位。PDF可复制文字不自动视可靠原生。关键扫描数值/否定/日期/剂量/手写按报告或行组视觉核查，首次不提供候选答案或入组阈值；不清楚转人工，不能无限再读。
一份临床报告经多个工具读取仍是一份来源。人工核对不能替研究者新增意见。跨页连续来源须可验证，不能任意去分隔符拼接。

## 运行与预算
按职责显式预算/思考配置，不继承全角色65K要求。OCR复用已有共享准入，局部Qwen优先已有可执行配置；不凭V3建议强制选未证实35B或安装新平台。资料读取不携整套ClausePack。
非思考模式需实测适配支持，low不等于关闭思考。带图MTP/文本JSON兼容按当前服务保持；失败回执完整，禁止静默换收费路线。本地平台严格串行，保留进程/端口/内存释放等待，未授权不扩共享服务/杀其他任务。

## 兼容与验收
新策略版本明确，旧覆盖/回执只读回放，不能冒充新验收。补证/更正追加修订、受影响重算，历史报告冻结。复用FastAPI/React/SQLite/JobRunner/ArtifactStore及事实发布，不另建通用Agent/队列。
验收按V3第11节A1–A12，特别看实际采用的事实/结论与有效产出，旧双模型并集召回不再作为新路线唯一/强制指标；没有金标不得造百分比。
