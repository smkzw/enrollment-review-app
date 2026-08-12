/**
 * 条件/事实属性中文显示映射：fixture/v1 合成规则集中出现的属性全覆盖。
 * 内部字段名不直接出现在可见文案（spec: quality-guidelines forbidden patterns）。
 */

/** 属性主体 → 中文临床表达 */
export const SUBJECT_LABELS: Record<string, string> = {
  investigator: "研究者",
  laboratory: "实验室",
  medication: "用药",
  exception: "例外情况",
  demographics: "人口学",
  baseline: "基线节点",
  history: "既往资料",
  procedure: "必做检查",
};

/** subject.attribute → 中文临床表达 */
export const ATTRIBUTE_LABELS: Record<string, string> = {
  "investigator.unacceptable_participation_risk": "构成不可接受参与风险",
  "investigator.rule_specific_judgment": "研究者方案要求判断",
  "investigator.exception_confirmed": "研究者确认例外成立",
  "laboratory.target_ratio_uln": "检查值相对正常上限的倍数",
  "laboratory.critical_measurement_invalid": "关键测量被判定无效",
  "laboratory.required_fields_complete": "检查结果关键字段完整",
  "medication.prohibited_exposure": "禁用用药暴露",
  "exception.protocol_exception_documented": "方案例外已记录",
  "demographics.age_years": "年龄（岁）",
  "baseline.future_assessment": "后续节点评估",
  "history.referenced_document": "病历引用的原始文件",
  "procedure.required_completed": "必做检查已完成",
};

/** 完整属性表达（如“研究者·构成不可接受参与风险”）；未知属性返回 null。 */
export function attributeDisplayName(subject: string, attribute: string): string | null {
  const full = ATTRIBUTE_LABELS[`${subject}.${attribute}`];
  if (full === undefined) return null;
  const subjectLabel = SUBJECT_LABELS[subject];
  return subjectLabel === undefined ? full : `${subjectLabel}·${full}`;
}
