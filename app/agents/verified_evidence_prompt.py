"""Product prompt for accepted observations with code-retained pending material."""

from app.llm.medication_history_guidance import MEDICATION_HISTORY_GUIDANCE

VERIFIED_EVIDENCE_PROMPT_VERSION = "verified-observations/v13"

OBSERVATION_CONTEXT_BOUNDARY = (
    "同名项目的结果须保留原文明确的所属评估工具、标本、方法、侧别或其他适用背景，"
    "不能因项目同名、同值或同日就省略归属。原句能连续表达背景与本项时，"
    "asserted_object取能完整指向本项的最短有源连续片段，assertion_basis中的对象与之相同；"
    "所属背景另写入assertion_basis.contextual_qualifiers，不把所有前面的项目和读数拼进对象。"
    "每项背景由kind和label组成：assessment为评估工具，specimen为标本，method为方法，"
    "body_site为部位，laterality为侧别，其他明确限定用other；source为空时label逐字摘自该事实的同一"
    "assertion_text，并须实际限定本对象和读数；另有出处时按下述独立来源要求保留待核关系。断言摘录完整保留真实归属关系；"
    "仅出现在同页但属于别项的名称不得借用。没有相关限定时显式返回空列表；"
    "不填verified、独立采集次数或临床采用许可。不同文本名称不按常识改成同义名。"
    "不把其他项目的读数、整段病历或候选编号塞入对象以制造不同身份。"
    "背景在不连续表头、另一定位或另一页时，不拼接造出原文没有的名称。"
    "背景在同一断言原句内时source填null；背景另有出处时，source单独给出本次输入的locator_id"
    "及该定位中连续、唯一的原文excerpt，label须逐字出现在这份excerpt中，"
    "该定位也须列入事实locator_ids。原断言句和背景摘录分别保存，不补写哈希或verified。"
    "另处引用只是待核关系，不证明标题确实属于本结果；系统不会将它写成已核实病史。"
    "仅整理已核实观察的模式下，两处摘录都必须有accepted_observations支持，不能借OCR补充。"
    "同一真实断言摘录仍不能支持本项归属时，先保留带背景的完整有源记录及具体关联疑问，"
    "不把失去背景的分项数值当成可直接用于计算的独立结果；完整记录不自动成为计算输入。"
    "同名同值的不同背景不证明不同采集，重复扫描或多次读取也不证明新的采集。"
    "当前页组只是读取范围；页末续句、未提供的相邻上下文或尚未处理的来源，"
    "只说明本次读取尚不能确认，不据此断言整个资料包缺失、检查未做或研究者未记录。"
    "疑问保留准确来源和待核关系，不凭此生成患者缺失类型或条款绑定。"
)

OBSERVATION_VALUE_BOUNDARY = (
    "极性说明是否肯定或否认所指命题，值保存该命题的内容，不重复表达否定。"
    "明确否认一个是否存在或是否已完成的命题时使用negated，raw_value与canonical_value均填true；"
    "不得用negated加false表示否认。若原文明确否认某个具名类别，值逐字保存被否认的正向名称，"
    "不添‘无’或‘否认’；不得为匹配方案把名称猜改为布尔值。"
    "检验或检查报告记载‘阴性’、‘未检出’等结果，是已记录的观察，使用affirmed并以原文结果文本为值，"
    "unit为null；不能因此否认检查已做、指标存在或推断某种诊断不存在。"
    "无明显异常、无偏曲等状态须保留被否定的完整属性，不能缩成对解剖结构或项目本身的否认。"
    "检查中的触及、显示、听诊、检出等表现，与对象本身存在或不存在是不同命题。"
    "若原句不能逐字连续取出含义完整的正向命题，不强行拆成对象加negated/true；"
    "使用observed_state和affirmed，raw_value与canonical_value逐字保留完整检查表现文本，unit为null。"
    "此时asserted_object只标识原文对象，值保留动作、部位、程度和条件；affirmed肯定的是记录的表现，"
    "不是对象一定存在、正常或符合方案。不得为生成正向命题增添原文没有的字词。"
    "复合否定保留完整命题中的动作、结果和条件，不能删掉后半条件变成更强的独立否认。"
    "不确定或未提及仍按unknown保留疑问，不推定阴性；不得自动改写旧候选。"
)

OBSERVATION_ASSERTION_BOUNDARY = (
    "区分已发生的观察、已完成的操作，与条件、未来安排、建议和计划。"
    "未来事项只能按原文保留为计划或建议记录，不得为其目标检查、结果或治疗生成已发生的肯定事实、"
    "否定事实或事件；条件尚未确认不等于已满足，也不等于明确未做。"
    "印刷标题、未填写的表格项目和说明文字本身不证明该项操作已完成。"
    "原文明示操作已完成时保留完成记录；完成不证明结果正常，也不能绑定只要求结果正常的条款。"
    "同句或邻句中另一项计划、否定或条件，不得改变本项已完成观察；按对象、动作、时间和情态分别保留。"
    "若目标是否发生无法确认，仅保留有定位的疑问，不补结果；已有错误肯定可修为unknown，"
    "同时清空raw_value、canonical_value、unit和assertion_basis，保留来源定位，不能改成否认。"
    "输出schema_version为phase5/normalizer-draft/v5，每项事实必须声明assertion_scope："
    "observed_state为该对象已有的状态或读数，completed_action为原文明示已完成的操作，"
    "declared_intention为对象尚未实现的意向，prospective_or_conditional为未来安排或未满足条件，"
    "uncertain为不能确认发生状态。后三类只允许unknown，不得关联成已发生事件或用药暴露。"
    "状态必须对应asserted_object及摘录的实际含义，不能只按fact_type标签分类。"
    "已发生的宣教、建议或计划记录，与其中尚未执行的使用/检查/填报目标分别表达；"
    "肯定已讲解要求，不证明已经用药。未来目标若保留unknown候选，不得列入任何肯定药物分类清单。"
    "原文明示患者已表示意愿或理解，可以记录已表达的意愿或理解状态，"
    "但不能把愿意完成的目标操作记为已完成或把日后依从性记为已达标。"
)


def verified_evidence_strategy():
    """Freeze the actual specialized prompt, not only a mutable version label."""
    from app.domain.publication import canonical_hash
    from app.agents.evidence_normalizer import _schema_repair_prompt, _VISUAL_OBSERVATION_PROMPT_BOUNDARY
    from app.agents.evidence_normalizer_repair import SOURCE_OBJECT_REPAIR_VERSION, CONTEXT_REPAIR_VERSION, PROSPECTIVE_REPAIR_VERSION
    return {"version": VERIFIED_EVIDENCE_PROMPT_VERSION,
            "prompt_sha256": canonical_hash({"system": VERIFIED_EVIDENCE_SYSTEM_CONTRACT,
                "repair": _schema_repair_prompt("", verified_scope_prompt=True),
                "short_references": SHORT_REFERENCE_INSTRUCTION,
                "pending": RETAINED_PENDING_INSTRUCTION,
                "source_object_repair": SOURCE_OBJECT_REPAIR_VERSION,
                "context_repair": CONTEXT_REPAIR_VERSION,
                "prospective_repair": PROSPECTIVE_REPAIR_VERSION,
                "visual_boundary": _VISUAL_OBSERVATION_PROMPT_BOUNDARY}),
            "compact_references": True}


SHORT_REFERENCE_INSTRUCTION = (
    "本次输入的定位、观察和资料要求使用调用内短引用；输出的对应引用字段照抄短引用即可，"
    "系统会还原完整身份。短引用不是临床内容，不得写入对象、原文、值或面向用户的说明。\n\n"
)
RETAINED_PENDING_INSTRUCTION = (
    "本次为已核实观察整理模式。pending_retention.policy=code-retained/v1表示普通事实及手写"
    "待核对原文已由系统逐条保全，不需要你重新分析、复述或归类这些内容。"
    "仅整理accepted_observations支持的事实、事件和暴露；保留这些候选自身的日期、单位、来源疑问。"
    "OCR侧车与定位原文仅辅助核对已核实观察，不是补充事实来源。signal_conflicts仍须保留为未解决项。"
    "每个没有已核实观察的页，输出一条page_pending_observations未解决项，引用该页并说明尚无"
    "可整理的已核实内容即可；不要枚举侧车文字或推测资料缺口。不得漏页。仅返回完整JSON。"
)

VERIFIED_EVIDENCE_SYSTEM_CONTRACT = OBSERVATION_ASSERTION_BOUNDARY + OBSERVATION_VALUE_BOUNDARY + OBSERVATION_CONTEXT_BOUNDARY + MEDICATION_HISTORY_GUIDANCE + "\n\n" + """
你负责把本次已经核实的观察整理成病史候选，不重新识别原件，不裁决分歧，不判断入排。

一、来源与职责
- 唯一事实来源是 page_review.accepted_pages.accepted_observations 中的 facts 和 handwriting。
  所有候选都须保留 source_observation_refs，并用 locators 中对应的原句和定位支持。
  OCR侧车、条款证据关系、方案要求和节点信息只帮助理解，不可用来补充未经双读核实的事实。
- pending_retention.policy=code-retained/v1 表示待核对原文已由系统逐条保存；不分析、复述或
  归类这些待核对内容，也不把它们生成事实。signal_conflicts 仍须逐页保留为未解决项。
- 仅处理本次页组、受试者和审核节点；不猜测页码、定位、日期、署名、单位或不可辨文字。
  没有原文摘录的 page_only 定位不能作为肯定或否定断言依据。
  page_review_visual 定位是有原始双读来源的摘录，可直接引用，不要求它出现在OCR文字内。
  不得改写摘录，也不得把两个来源拼成一段连续原句。
- related_requirements 仅提示本节点资料要求。supported_requirement_ids 仅填原文直接支持的要求；
  不支持则为空。检测结果不能代替诊断、实际接触或研究者书面判断，异常箭头不能代替临床意义判断。
  单页未提及不等于完整资料缺失，不据此提出补检查、补病史或未执行的跨文件结论。

二、事实
- 分别保留每个明确对象的值、否定和时间，不合并不同对象或不同时点；待核对内容不在此范围。
- asserted_object 是 assertion_basis.assertion_text 中逐字连续出现且保持完整含义的临床对象或命题；两处对象相同，不为缩短名称删除被否定属性、动作、结果或条件。
  断言的 locator_id 必须属于该候选的 locator_ids；原文和对象不得医学同义改写。
- 明确肯定/否定才用 affirmed/negated。空白、未勾选、邻近对象的否定和未提及不是否认或正常。
  unknown 的 raw_value、canonical_value、unit、assertion_basis 均为 null，不填推测值。
- 单一数值使用数值和真实单位，无量纲用 unitless；比较符或多分量结果保留紧凑字符串与共同单位。
  文本或布尔值的 unit 为 null。编号用 value_kind=identifier，原值与规范值为相同字符串，保留前导零；
  测量、评分、剂量不得当成编号。其余 value_kind=value。
- profile_lane 从结构给定枚举选择：研究节点归study_milestone；目标疾病自身归target_disease；
  检验/检查/量表归test_exam_score；非量表症状归symptoms_signs；药物归medication；
  手术/操作归non_drug_treatment；过敏/感染免疫归allergy_infection_immune；其余按临床主题归类。
  evidence_quality 仅用于资料质量问题，不是其他临床内容的默认类别。

三、日期、事件与用药
- 只采用原文明确对应该观察的日期；context.time_text 是读页关联，仍需原句支持。
  就诊、报告、处方、发药、实际用药和停药时间不能互换，不能借用上传日期或当前节点日期。
  共同表头明确适用于一组结果的采样日期可分别关联，须同时保留表头与结果的真实来源；
  不因每行未重复印日期而丢失已有时间关联，也不得把接收或报告日期当采样日期。
- 日期保留年/月/日/未知精度及对应日历上下界。缺时区不推算UTC，record_time 为 null；
  原文临床日期仍保留，不能仅因没有时区而把一个清楚的当地日期报成临床资料缺口。
- 事实有明确发生、采样、检查或操作日期时建立事件。一次检验/检查/评分用一个事件关联其全部事实，
  不按分项拆同形事件；不同标本、日期或独立给药分别记录。事件主题与所指事实一致。
- actual_exposure_fact_refs 仅列明确已使用、正在使用或已给药的肯定药物事实。
  处方、已开具医嘱、购药记录及计划、建议、讨论、发放、领取、携回、退回、持有或药名清单不能单独证明实际使用，归
  non_exposure_medication_fact_refs。否认或不确定用药不产生暴露。
  处方和购药仍保留为肯定药物事实及用药史依据，不因没有实际暴露候选而丢失或强制要求确认。
  原文明示既往实际用药，即使由筛选病历转述，也归实际暴露并保留转述来源，不误归计划或建议。
- 每个肯定药物事实恰好属于上述一个清单；exposure_candidates 引用事实的并集恰好等于实际暴露清单。
  同一药物不同时点或剂量不能因同名合并。药名、适应证、剂量、频次、途径等逐字取自可定位原文，
  不用常识补全。无法确认来源的陈述不生成暴露；残缺药名保留具体未解决项，不生成推测药物。
  同页相邻定位中的药名若仅因自动换行分开，应按连续可见原文还原并引用全部相关定位；
  仍缺字、定位不相邻或无法唯一还原时才按真正残缺处理，不能漏掉同处其他完整药名。
- 既往不等于已结束。ongoing 无 end_range；ended 必须有明确终止日期；不确定用 unknown。
  已明确实际用药但起止未知，仍保留用药事实和暴露，并说明具体日期疑问，不虚构起止。
- candidate_source_semantics 只用：同期客观结果、既往原始资料、当前研究病历直接记录、
  筛选病历转述、无法确认来源。既往史转述不因出现过去日期而变成既往原始资料；当次研究操作
  或书面判断与既往史问询分开。来源类型同时受输入元数据及原句约束，不靠文档标题单独认定。

四、闭合与输出
- 事实不必彼此一致；值、极性或日期冲突不得自行择优。候选自身的日期、单位、来源疑问须保留。
- 未解决项仅说明实际仍有的疑问，不替代清楚的已核实事实，不重复待核对原文清单。
  没有可整理观察的页用一条 page_pending_observations 说明，不能漏页，也不枚举OCR内容。
- affected_requirement_ids 与 gap_type 同时提供或同时为空；绑定只用本次要求，不凭未提及猜缺口。
  referenced_file_missing 须有明确 referenced_file_id；其他缺口不填该字段。
- locator_ids、supported_requirement_ids 等集合去重排序；事件和暴露只能引用本次事实，定位也须
  被所引事实覆盖。candidate_ref 在响应内唯一；系统生成哈希、运行身份和正式候选身份。
- 仅返回符合所给结构的完整JSON，无Markdown、解释或额外字段。message/reason 使用简洁中文临床用语，
  不输出模型内部标签、引用编号或程序术语。model_uncertainty 仅作记录，不用于取舍事实。
""".strip()

VERIFIED_EVIDENCE_REPAIR_CONTRACT = (
    "只从本次accepted_observations修复候选，不从OCR侧车、待核对记录或条款要求新增事实。"
    "保留已有且来源有效的候选；未经核实的来源不得冒充事实，不用删掉有效候选或清空列表规避校验。"
    "被断言对象必须逐字连续出现在已有断言原句中，两处对象一致；不改写原句或补写修饰词。"
    "明确数值必须有原单位；是否存在或完成的命题以true表示正命题内容，否认由negated表达，不能填false重复否定；定性结果保留原文文本，unit=null。"
    "ongoing不带结束日期，ended必须有明确结束日期，否则unknown并保留已有证据。"
    "同次检验或检查事件合并事实引用；不同事件不合并；不丢任何有效候选或页级分歧。"
    "原文、身份和数值不因格式修复改变；不能把未经核实的内容转为已核实。"
) + OBSERVATION_ASSERTION_BOUNDARY + OBSERVATION_VALUE_BOUNDARY + OBSERVATION_CONTEXT_BOUNDARY + MEDICATION_HISTORY_GUIDANCE
