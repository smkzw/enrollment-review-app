/**
 * 条件/事实属性中文显示映射：fixture/v1 合成规则集中出现的属性全覆盖。
 * 内部字段名不直接出现在可见文案（spec: quality-guidelines forbidden patterns）。
 */

import type { PredicateNodeView } from "../../domain/viewModels";

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
  "investigator.rule_specific_judgment": "方案要求判断",
  "investigator.exception_confirmed": "确认例外成立",
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

/** 事实类型（如 “investigator.unacceptable_participation_risk”）→ 中文临床表达；未知返回 null。 */
export function factTypeDisplayName(factType: string): string | null {
  const dot = factType.indexOf(".");
  if (dot <= 0 || dot === factType.length - 1) return null;
  return attributeDisplayName(
    factType.slice(0, dot),
    factType.slice(dot + 1),
  );
}

/** 单位 → 中文表达；与属性名内单位去重，避免“年龄（岁）…岁”重复。 */
const UNIT_LABELS: Record<string, string> = {
  year: "岁",
  xULN: "倍正常上限",
};

function formatValue(
  value: boolean | number | string,
  unit: string | null,
  attribute: string | null,
): string {
  const localizedUnit =
    unit === null || unit === undefined ? null : (UNIT_LABELS[unit] ?? unit);
  const unitAlreadyInAttribute =
    localizedUnit !== null &&
    attribute?.includes(`（${localizedUnit}）`) === true;
  return `${String(value)}${
    localizedUnit !== null && !unitAlreadyInAttribute
      ? ` ${localizedUnit}`
      : ""
  }`;
}

/**
 * 谓词整句中文表达（I2 修复）：属性与比较词一次性拼接，
 * 不再出现“为 等于 是”等机械叠加。
 * - eq + 布尔：属性本身已是肯定句 → “研究者·构成不可接受参与风险” / “…：否”。
 * - 数值比较：属性 + 比较词 + 带单位的格式化值（单位已含在属性名内时不重复）。
 */
export function formatPredicateStatement(
  predicate: Pick<
    PredicateNodeView,
    "subject" | "attribute" | "comparator" | "comparatorLabel" | "value" | "unit"
  >,
): string {
  const attribute = attributeDisplayName(predicate.subject, predicate.attribute);
  const name = attribute ?? "该事项";
  if (typeof predicate.value === "boolean") {
    if (predicate.comparator === "eq") {
      return predicate.value ? name : `${name}：否`;
    }
    if (predicate.comparator === "ne") {
      return predicate.value ? `不成立：${name}` : name;
    }
  }
  if (predicate.value === null || predicate.value === undefined) {
    return `${name}（未给出具体值）`;
  }
  const formatted = formatValue(predicate.value, predicate.unit, attribute);
  return `${name} ${predicate.comparatorLabel}${formatted === "" ? "" : ` ${formatted}`}`;
}
