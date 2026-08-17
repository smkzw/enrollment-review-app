/** 方案草稿的临床语义手工修订。来源摘录和来源绑定始终只读。 */

export type EditableLogicOperator = "all" | "any" | "not";
export type EditableComparator = "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists";
export type EditableReviewStage = "pre_screening" | "screening" | "run_in" | "baseline";

export interface EditableTimeWindow {
  anchorType: string;
  direction: "before" | "after" | "on";
  lowerValue: string;
  lowerUnit: "day" | "week" | "month" | "year";
  upperValue: string;
  upperUnit: "day" | "week" | "month" | "year";
  halfLifeMultiplier: string;
  allowPartialDate: boolean;
}

export interface EditablePredicate {
  predicateId: string;
  scope: "main" | "exception";
  subject: string;
  attribute: string;
  comparator: EditableComparator;
  valueText: string;
  originalValue: unknown;
  unit: string;
  requiresProfessionalJudgment: boolean;
  timeWindow: EditableTimeWindow | null;
}

export interface EditableRequirement {
  requirementId: string;
  description: string;
  dueStage: EditableReviewStage;
}

export interface EditableProtocolComponent {
  componentId: string;
  displayCode: string;
  title: string;
  mainOperator: EditableLogicOperator | null;
  exceptionOperator: EditableLogicOperator | null;
  predicates: EditablePredicate[];
  requirements: EditableRequirement[];
  sourceExcerpts: string[];
}

export interface ComponentSemanticPatch {
  title: string;
  mainOperator: EditableLogicOperator | null;
  exceptionOperator: EditableLogicOperator | null;
  predicate: EditablePredicate | null;
  requirements: EditableRequirement[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function clone(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(clone);
  if (isRecord(value)) return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clone(item)]));
  return value;
}

function logicOperator(expression: unknown): EditableLogicOperator | null {
  if (!isRecord(expression) || expression.kind !== "logical") return null;
  return expression.operator === "all" || expression.operator === "any" || expression.operator === "not" ? expression.operator : null;
}

type TimeUnit = EditableTimeWindow["lowerUnit"];

function boundValue(raw: unknown, dayValue: unknown): [string, TimeUnit] {
  if (isRecord(raw) && typeof raw.value === "number") {
    const unit: TimeUnit = raw.unit === "week" || raw.unit === "month" || raw.unit === "year" ? raw.unit : "day";
    return [String(raw.value), unit];
  }
  return typeof dayValue === "number" ? [String(dayValue), "day"] : ["", "day"];
}

function editableTimeWindow(raw: unknown): EditableTimeWindow | null {
  if (!isRecord(raw)) return null;
  const [lowerValue, lowerUnit] = boundValue(raw.lower_bound, raw.lower_bound_days);
  const [upperValue, upperUnit] = boundValue(raw.upper_bound, raw.upper_bound_days);
  return {
    anchorType: typeof raw.anchor_type === "string" ? raw.anchor_type : "screening_date",
    direction: raw.direction === "after" || raw.direction === "on" ? raw.direction : "before",
    lowerValue,
    lowerUnit,
    upperValue,
    upperUnit,
    halfLifeMultiplier: typeof raw.half_life_multiplier === "number" ? String(raw.half_life_multiplier) : "",
    allowPartialDate: raw.allow_partial_date === true,
  };
}

function valueText(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join("、");
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function collectPredicates(expression: unknown, scope: EditablePredicate["scope"], output: EditablePredicate[]): void {
  if (!isRecord(expression)) return;
  if (expression.kind === "predicate" && isRecord(expression.predicate)) {
    const predicate = expression.predicate;
    const comparator = predicate.comparator;
    if (comparator !== "eq" && comparator !== "ne" && comparator !== "gt" && comparator !== "gte" && comparator !== "lt" && comparator !== "lte" && comparator !== "in" && comparator !== "not_in" && comparator !== "exists") return;
    output.push({
      predicateId: String(predicate.predicate_id ?? ""),
      scope,
      subject: String(predicate.subject ?? ""),
      attribute: String(predicate.attribute ?? ""),
      comparator,
      valueText: valueText(predicate.value),
      originalValue: clone(predicate.value),
      unit: typeof predicate.unit === "string" ? predicate.unit : "",
      requiresProfessionalJudgment: predicate.requires_professional_judgment === true,
      timeWindow: editableTimeWindow(expression.time_constraint),
    });
    return;
  }
  if (expression.kind === "logical" && Array.isArray(expression.children)) {
    for (const child of expression.children) collectPredicates(child, scope, output);
  }
}

export function getEditableProtocolComponents(content: Record<string, unknown>): EditableProtocolComponent[] {
  const draftByComponent = new Map<string, Record<string, unknown>>();
  for (const rawDraft of Array.isArray(content.component_drafts) ? content.component_drafts : []) {
    if (!isRecord(rawDraft) || !isRecord(rawDraft.proposed_component)) continue;
    draftByComponent.set(String(rawDraft.proposed_component.rule_component_id ?? ""), rawDraft);
  }
  const result: EditableProtocolComponent[] = [];
  for (const rawRule of Array.isArray(content.proposed_rules) ? content.proposed_rules : []) {
    if (!isRecord(rawRule)) continue;
    for (const rawComponent of Array.isArray(rawRule.components) ? rawRule.components : []) {
      if (!isRecord(rawComponent)) continue;
      const componentId = String(rawComponent.rule_component_id ?? "");
      if (!componentId) continue;
      const predicates: EditablePredicate[] = [];
      collectPredicates(rawComponent.expression, "main", predicates);
      collectPredicates(rawComponent.exception_expression, "exception", predicates);
      const requirements: EditableRequirement[] = [];
      for (const rawRequirement of Array.isArray(rawComponent.evidence_requirements) ? rawComponent.evidence_requirements : []) {
        if (!isRecord(rawRequirement)) continue;
        const dueStage = rawRequirement.due_stage;
        if (dueStage !== "pre_screening" && dueStage !== "screening" && dueStage !== "run_in" && dueStage !== "baseline") continue;
        requirements.push({ requirementId: String(rawRequirement.requirement_id ?? ""), description: String(rawRequirement.description ?? ""), dueStage });
      }
      const draft = draftByComponent.get(componentId);
      result.push({
        componentId,
        displayCode: String(rawComponent.display_code ?? ""),
        title: String(rawComponent.title ?? ""),
        mainOperator: logicOperator(rawComponent.expression),
        exceptionOperator: logicOperator(rawComponent.exception_expression),
        predicates,
        requirements,
        sourceExcerpts: isRecord(draft) && Array.isArray(draft.source_excerpts) ? draft.source_excerpts.filter((item): item is string => typeof item === "string") : [],
      });
    }
  }
  return result;
}

function parseValue(text: string, original: unknown, comparator: EditableComparator): unknown {
  if (comparator === "exists") return null;
  if (Array.isArray(original)) {
    return text.split(/[、,，]/).map((item) => item.trim()).filter(Boolean).map((item) => {
      const numeric = Number(item);
      return original.some((value) => typeof value === "number") && Number.isFinite(numeric) ? numeric : item;
    });
  }
  if (typeof original === "number") {
    const numeric = Number(text);
    return Number.isFinite(numeric) ? numeric : original;
  }
  if (typeof original === "boolean") return text === "是" || text.toLowerCase() === "true";
  return text;
}

function patchTimeWindow(raw: Record<string, unknown>, patch: EditableTimeWindow): void {
  raw.anchor_type = patch.anchorType;
  raw.direction = patch.direction;
  raw.allow_partial_date = patch.allowPartialDate;
  raw.half_life_multiplier = patch.halfLifeMultiplier === "" ? null : Number(patch.halfLifeMultiplier);
  const setBound = (name: "lower" | "upper", text: string, unit: TimeUnit) => {
    const dayKey = `${name}_bound_days`;
    const quantityKey = `${name}_bound`;
    if (text === "") {
      raw[dayKey] = null;
      raw[quantityKey] = null;
      return;
    }
    const value = Number(text);
    if (unit === "day") {
      raw[dayKey] = value;
      raw[quantityKey] = null;
    } else {
      raw[dayKey] = null;
      raw[quantityKey] = { value, unit };
    }
  };
  setBound("lower", patch.lowerValue, patch.lowerUnit);
  setBound("upper", patch.upperValue, patch.upperUnit);
  if (patch.direction === "on") {
    raw.lower_bound_days = null;
    raw.upper_bound_days = null;
    raw.lower_bound = null;
    raw.upper_bound = null;
    raw.half_life_multiplier = null;
  }
}

function patchExpression(expression: unknown, operator: EditableLogicOperator | null, predicatePatch: EditablePredicate | null): void {
  if (!isRecord(expression)) return;
  if (expression.kind === "logical") {
    if (operator !== null) expression.operator = operator;
    if (Array.isArray(expression.children)) for (const child of expression.children) patchExpression(child, null, predicatePatch);
    return;
  }
  if (expression.kind !== "predicate" || !isRecord(expression.predicate)) return;
  if (predicatePatch === null || expression.predicate.predicate_id !== predicatePatch.predicateId) return;
  expression.predicate.subject = predicatePatch.subject;
  expression.predicate.attribute = predicatePatch.attribute;
  expression.predicate.comparator = predicatePatch.comparator;
  expression.predicate.value = parseValue(predicatePatch.valueText, predicatePatch.originalValue, predicatePatch.comparator);
  expression.predicate.unit = predicatePatch.unit || null;
  expression.predicate.requires_professional_judgment = predicatePatch.requiresProfessionalJudgment;
  if (predicatePatch.timeWindow !== null && isRecord(expression.time_constraint)) patchTimeWindow(expression.time_constraint, predicatePatch.timeWindow);
}

export function patchComponentSemantics(content: Record<string, unknown>, componentId: string, patch: ComponentSemanticPatch): Record<string, unknown> {
  const next = clone(content) as Record<string, unknown>;
  let matched = false;
  for (const rawRule of Array.isArray(next.proposed_rules) ? next.proposed_rules : []) {
    if (!isRecord(rawRule)) continue;
    for (const rawComponent of Array.isArray(rawRule.components) ? rawRule.components : []) {
      if (!isRecord(rawComponent) || rawComponent.rule_component_id !== componentId) continue;
      matched = true;
      rawComponent.title = patch.title;
      patchExpression(rawComponent.expression, patch.mainOperator, patch.predicate?.scope === "main" ? patch.predicate : null);
      patchExpression(rawComponent.exception_expression, patch.exceptionOperator, patch.predicate?.scope === "exception" ? patch.predicate : null);
      const requirementById = new Map(patch.requirements.map((item) => [item.requirementId, item]));
      rawComponent.evidence_requirements = (Array.isArray(rawComponent.evidence_requirements) ? rawComponent.evidence_requirements : []).map((rawRequirement) => {
        if (!isRecord(rawRequirement)) return rawRequirement;
        const replacement = requirementById.get(String(rawRequirement.requirement_id ?? ""));
        return replacement === undefined ? rawRequirement : { ...rawRequirement, description: replacement.description, due_stage: replacement.dueStage };
      });
    }
  }
  return matched ? next : content;
}
