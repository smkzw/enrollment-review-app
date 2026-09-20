# Execution Output: phase5-slice58d-d001-control-matrix-20260825 - worker_02

## Boundary And Context Check

仅修改两个授权工件，未修改合同、校验器、测试、应用文件或原始 DOCX。

## Work Performed

- 迁移至 `phase5/control-matrix/v2`。
- 保留 36 条官方父级和 22 条流程候选。
- 22 条流程行均使用稳定候选身份；正式流程目录链接均为空。
- 重建冻结覆盖清单：3581 个结构块、1689 个结构单元、114 条来源处置。
- 未重新纳入建议性皮损照片、DLQI、随机动作、PK/IL-17A 研究采样、给药及治疗支持项目。
- `claims_complete=false` 保持不变。

36 个官方标题：

IN-01｜知情同意、沟通与遵从能力  
IN-02｜签署知情同意时年龄范围  
IN-03｜斑块状银屑病病史与稳定期  
IN-04｜银屑病严重程度及受累范围阈值  
IN-05｜光疗或系统治疗适应条件  
IN-06｜生育计划与研究期间避孕要求  
EX-01｜近期非斑块状银屑病  
EX-02｜影响评估的其他皮肤病及研究者判断  
EX-03｜药物诱发或加重的银屑病  
EX-04｜严重或活动性疱疹病毒感染  
EX-05｜需住院或静脉治疗的严重感染  
EX-06｜需口服抗感染治疗的近期感染  
EX-07｜近期活动性感染或急性疾病  
EX-08｜慢性或复发性感染及安全性风险判断  
EX-09｜结核感染筛查及预防治疗风险  
EX-10｜减毒活疫苗接种或接种计划  
EX-11｜严重系统性疾病及研究者适合性判断  
EX-12｜恶性肿瘤或淋巴组织增生性疾病  
EX-13｜其他自身免疫性疾病  
EX-14｜免疫缺陷及免疫状态受损风险  
EX-15｜精神疾病、依从性及自杀风险  
EX-16｜IL-12/17/23靶向药疗效不佳史  
EX-17｜TYK2或JAK抑制剂既往治疗史  
EX-18｜影响银屑病治疗的既往用药洗脱  
EX-19｜其他临床试验药物或研究参与  
EX-20｜实验室异常阈值与不可接受风险评估  
EX-21｜生命体征及检查异常与风险判断  
EX-22｜病毒性肝炎、HIV及梅毒感染  
EX-23｜近期酗酒或药物滥用史  
EX-24｜可能影响药物吸收的疾病或手术  
EX-25｜CYP3A强诱导剂或抑制剂暴露  
EX-26｜圣约翰草或葡萄柚暴露及规避要求  
EX-27｜近期献血失血及献血计划  
EX-28｜试验药物成分或严重药物过敏  
EX-29｜妊娠或哺乳期状态  
EX-30｜其他影响研究适合性的原因  

## Artifacts And Evidence

- [d001-ii-official-flow-controls.json](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.json)
- [d001-ii-official-flow-controls.md](/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/research/d001-ii-official-flow-controls.md)

验证结果：

- `ProtocolControlMatrix.model_validate_json()`：通过。
- 严格来源、期别和候选处置闭合：通过。
- builder、renderer、序列化一致性：通过。
- 聚焦测试：47 passed。
- Markdown 可见层内部身份、英文枚举和来源引用扫描：通过。

## Commands And Observations

使用项目 `.venv/bin/python` 完成结构提取、矩阵构建、渲染和验证；未安装依赖。

产物大小：

- JSON：279955 bytes
- Markdown：212240 bytes

## Blockers Or Missing Environment

正式 `required_procedure_catalog` 仍因 `body.t5` 缺少唯一 `ALIGNED TEXT_RANGE/PAGE_ONLY` 定位而未发布；未伪造正式目录身份。LibreOffice 已知 Abort trap 未重试。该真实限制由 `claims_complete=false` 保留。

## Rerun Requests Or Next Step

由 Codex 进行最终临床标题和渲染验收。若需发布正式流程目录，应先修复来源定位链，再将候选身份迁移为正式目录身份。
