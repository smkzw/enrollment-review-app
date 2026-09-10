/**
 * 差异分类变化单条展示：稳定引用 + 正式版本快照 / 新草稿快照并列。
 */

import type { ProtocolCategoryChangeView } from "../../domain/protocolDiffViewModels";

const COMPARATOR_LABELS: Record<string, string> = {
  eq: "等于",
  ne: "不等于",
  gt: "大于",
  gte: "大于或等于",
  lt: "小于",
  lte: "小于或等于",
  in: "属于",
  not_in: "不属于",
  contains: "包含",
  exists: "存在",
};

const STAGE_LABELS: Record<string, string> = {
  pre_screening: "预筛期",
  prescreening: "预筛期",
  screening: "筛选期",
  run_in: "导入期",
  baseline: "基线期",
  randomization: "随机前",
};

const ANCHOR_LABELS: Record<string, string> = {
  icf_date: "知情同意日期",
  prescreening_date: "预筛日期",
  screening_date: "筛选日期",
  consent_date: "知情同意日期",
  baseline_date: "基线日期",
  randomization_date: "随机日期",
  first_dose_date: "首次用药日期",
  study_drug_administration_date: "研究药物给药日期",
  last_dose_date: "末次用药日期",
  study_completion_date: "研究完成日期",
  event_date: "相关事件日期",
  current_review_date: "本次审核日期",
};

const DIRECTION_LABELS: Record<string, string> = {
  before: "前",
  after: "后",
  on_or_before: "当日或之前",
  on_or_after: "当日或之后",
  on: "当日",
};

const SUBJECT_LABELS: Record<string, string> = {
  investigator: "研究者判断",
  laboratory: "实验室检查",
  medication: "用药情况",
  exception: "例外条件",
  demographics: "人口学资料",
  baseline: "基线评估",
  history: "既往资料",
  procedure: "必做检查",
  "受试者": "受试者",
  "研究者判断": "研究者判断",
};

const ATTRIBUTE_LABELS: Record<string, string> = {
  age: "年龄",
  age_years: "年龄",
  unacceptable_participation_risk: "参与研究将构成不可接受的风险",
  rule_specific_judgment: "符合方案规定的研究者判断",
  exception_confirmed: "例外条件已确认",
  target_ratio_uln: "检查值相对正常上限的倍数",
  prohibited_exposure: "存在方案禁用的治疗或用药",
  required_completed: "必做检查已完成",
  referenced_document: "既往资料已有原始文件支持",
};

const UNIT_LABELS: Record<string, string> = {
  year: "岁",
  years: "岁",
  day: "天",
  days: "天",
  week: "周",
  weeks: "周",
  month: "个月",
  months: "个月",
  xULN: "倍正常上限",
  unitless: "",
};

function recordOf(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function localizePrimitive(value: unknown): string {
  if (value === null || value === undefined) return "未设置";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "string") {
    return STAGE_LABELS[value] ?? ANCHOR_LABELS[value] ?? DIRECTION_LABELS[value] ?? value;
  }
  return String(value);
}

function formatPredicate(raw: Record<string, unknown>): string | null {
  const predicate = recordOf(raw.predicate) ?? raw;
  const subjectRaw = typeof predicate.subject === "string" ? predicate.subject : "";
  const attributeRaw = typeof predicate.attribute === "string" ? predicate.attribute : "";
  if (subjectRaw === "" && attributeRaw === "") return null;
  const subject = SUBJECT_LABELS[subjectRaw] ?? subjectRaw;
  const attribute = ATTRIBUTE_LABELS[attributeRaw] ?? attributeRaw;
  const comparatorRaw = typeof predicate.comparator === "string" ? predicate.comparator : "eq";
  const comparator = COMPARATOR_LABELS[comparatorRaw] ?? "符合";
  const value = localizePrimitive(predicate.value);
  const unitRaw = typeof predicate.unit === "string" ? predicate.unit : "";
  const unit = UNIT_LABELS[unitRaw] ?? unitRaw;
  const item = [subject, attribute].filter((part) => part.length > 0).join("：");
  return `${item}${item.length > 0 ? " " : ""}${comparator} ${value}${unit.length > 0 ? ` ${unit}` : ""}`;
}

function formatLogic(raw: Record<string, unknown>, depth = 0): string[] {
  const predicate = formatPredicate(raw);
  if (predicate !== null) return [`${"  ".repeat(depth)}${predicate}`];
  const operator = raw.operator === "any"
    ? "任一条件满足"
    : raw.operator === "not"
      ? "以下条件不成立"
      : raw.operator === "all"
        ? "以下条件全部满足"
        : "逻辑关系需要核对";
  const children = Array.isArray(raw.children) ? raw.children : [];
  return [
    `${"  ".repeat(depth)}${operator}：`,
    ...children.flatMap((child) => {
      const childRecord = recordOf(child);
      return childRecord === null
        ? [`${"  ".repeat(depth + 1)}${localizePrimitive(child)}`]
        : formatLogic(childRecord, depth + 1);
    }),
  ];
}

function formatTimeQuantity(raw: unknown): string | null {
  const quantity = recordOf(raw);
  if (quantity === null || typeof quantity.value !== "number" || typeof quantity.unit !== "string") {
    return null;
  }
  const unit = quantity.unit === "day"
    ? "天"
    : quantity.unit === "week"
      ? "周"
      : quantity.unit === "month"
        ? "个月"
        : quantity.unit === "year"
          ? "年"
          : "个时间单位";
  return `${quantity.value}${unit}`;
}

function formatTimeConstraint(raw: Record<string, unknown>): string {
  const anchorRaw = typeof raw.anchor_type === "string" ? raw.anchor_type : "";
  const directionRaw = typeof raw.direction === "string" ? raw.direction : "";
  const anchor = ANCHOR_LABELS[anchorRaw] ?? (anchorRaw || "指定节点");
  const direction = DIRECTION_LABELS[directionRaw] ?? directionRaw;
  if (directionRaw === "on") return `${anchor}当日`;
  const lower = typeof raw.lower_bound_days === "number" ? raw.lower_bound_days : null;
  const upper = typeof raw.upper_bound_days === "number" ? raw.upper_bound_days : null;
  const lowerQuantity = formatTimeQuantity(raw.lower_bound);
  const upperQuantity = formatTimeQuantity(raw.upper_bound);
  const lowerInclusive = raw.lower_bound_inclusive !== false;
  const upperInclusive = raw.upper_bound_inclusive !== false;
  const range = lowerQuantity !== null && upperQuantity !== null
    ? `${lowerInclusive ? "至少" : "超过"}${lowerQuantity}且${upperInclusive ? "不超过" : "少于"}${upperQuantity}`
    : upperQuantity !== null
      ? upperInclusive ? `${upperQuantity}内` : `少于${upperQuantity}`
      : lowerQuantity !== null
        ? `${lowerInclusive ? "至少" : "超过"}${lowerQuantity}`
        : lower !== null && upper !== null
    ? `${lowerInclusive ? "至少" : "超过"}${lower}天且${upperInclusive ? "不超过" : "少于"}${upper}天`
    : upper !== null
      ? upperInclusive ? `${upper}天内` : `少于${upper}天`
      : lower !== null
        ? `${lowerInclusive ? "至少" : "超过"}${lower}天`
        : "方案规定时段";
  const halfLife = typeof raw.half_life_multiplier === "number"
    ? `；同时核对${raw.half_life_multiplier}个半衰期`
    : "";
  return `${anchor}${direction.length > 0 ? direction : "前后"}${range}${halfLife}`;
}

function formatTimePayload(raw: Record<string, unknown>): string[] {
  const scope = raw.scope === "exception" ? "例外条件" : "主条件";
  const lines: string[] = [];
  const constraint = recordOf(raw.time_constraint);
  if (constraint !== null) lines.push(`${scope}：${formatTimeConstraint(constraint)}`);

  const occurrence = recordOf(raw.occurrence_window);
  if (occurrence !== null) {
    const duration = formatTimeQuantity(occurrence.duration) ?? "方案规定周期";
    const count = typeof occurrence.minimum_count === "number"
      ? `，至少发生${occurrence.minimum_count}次`
      : "";
    lines.push(`${scope}：在${duration}内${count || "按规定频次发生"}`);
  }

  const prospective = recordOf(raw.prospective_window);
  if (prospective !== null) {
    const anchorRaw = typeof prospective.anchor_type === "string" ? prospective.anchor_type : "";
    const anchor = ANCHOR_LABELS[anchorRaw] ?? "指定节点";
    const upper = formatTimeQuantity(prospective.upper_bound) ?? "方案规定时段";
    lines.push(`${scope}：预计持续至${anchor}后${upper}`);
  }

  const period = recordOf(raw.prospective_period);
  if (period !== null) {
    const periodLabel = period.period === "treatment_period"
      ? "治疗期间"
      : period.period === "study_period"
        ? "研究期间"
        : "方案规定期间";
    lines.push(`${scope}：${periodLabel}`);
  }

  return lines.length > 0 ? lines : [`${scope}：未设置时间要求`];
}

function formatEvidence(raw: Record<string, unknown>): string[] {
  const description = typeof raw.description === "string" ? raw.description : null;
  const factType = typeof raw.fact_type === "string" ? raw.fact_type : null;
  const dueStage = typeof raw.due_stage === "string" ? STAGE_LABELS[raw.due_stage] ?? raw.due_stage : null;
  const sourceValidity = formatTimeQuantity(raw.source_validity_window);
  const lines = [
    description,
    factType === null ? null : `需核实：${factType}`,
    dueStage === null ? null : `应于${dueStage}完成`,
    sourceValidity === null ? null : `可采用${sourceValidity}内的检查结果`,
  ]
    .filter((item): item is string => item !== null && item.length > 0);
  return lines.length > 0 ? lines : ["资料要求发生变化"];
}

function humanReadableLines(payload: unknown, category: ProtocolCategoryChangeView["category"]): string[] {
  if (payload === null || payload === undefined) return ["无"];
  if (typeof payload === "string" || typeof payload === "number" || typeof payload === "boolean") {
    return [localizePrimitive(payload)];
  }
  if (Array.isArray(payload)) {
    if (payload.length === 0) return ["无"];
    return payload.flatMap((item) => humanReadableLines(item, category));
  }
  const raw = recordOf(payload);
  if (raw === null) return ["内容已变更"];

  if (category === "original_text") {
    const sourceText = typeof raw.source_text === "string" ? raw.source_text : null;
    const binding = recordOf(raw.source_binding);
    const excerpts = binding !== null && Array.isArray(binding.source_excerpts)
      ? binding.source_excerpts.filter((item): item is string => typeof item === "string")
      : [];
    return sourceText !== null ? [sourceText] : excerpts.length > 0 ? excerpts : ["方案原文摘录已变更"];
  }
  if (category === "logic" || category === "exception") return formatLogic(raw);
  if (category === "time_window") {
    return formatTimePayload(raw);
  }
  if (category === "evidence") return formatEvidence(raw);
  if (category === "due_stage") {
    return Object.values(raw).flatMap((value) => humanReadableLines(value, category));
  }
  return ["内容已变更"];
}

export function ProtocolCategoryChangeRow({
  change,
}: {
  change: ProtocolCategoryChangeView;
}) {
  return (
    <li className="protocol-redo-change">
      <span className="protocol-redo-change__ref">
        {change.kind === "rule" ? "标准" : change.kind === "requirement" ? "资料要求" : "子项"}
        {change.stableRef}
      </span>
      <div className="protocol-redo-change__compare">
        <div className="protocol-redo-change__side">
          <span className="protocol-redo-change__side-label">正式版本</span>
          <ProtocolPayload payload={change.previous} category={change.category} />
        </div>
        <div className="protocol-redo-change__side">
          <span className="protocol-redo-change__side-label">新草稿</span>
          <ProtocolPayload payload={change.current} category={change.category} />
        </div>
      </div>
    </li>
  );
}

export function ProtocolPayload({
  payload,
  category,
}: {
  payload: unknown;
  category: ProtocolCategoryChangeView["category"];
}) {
  const lines = humanReadableLines(payload, category);
  return (
    <ul className="protocol-redo-change__payload">
      {lines.map((line, index) => (
        <li key={`${index}-${line}`}>{line}</li>
      ))}
    </ul>
  );
}
