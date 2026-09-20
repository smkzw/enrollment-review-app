/**
 * V2 方案解构 wire → 视图模型校验与归一化（单一解码层，组件不重复解析）。
 */

import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
import type { DatePrecision, StudyPhase } from "../domain/enums";
import type {
  ConfirmIdentityInput,
  DraftComparisonSideView,
  DraftComparisonView,
  DraftRevisionView,
  FeedbackInput,
  GenerationPreviewView,
  IdentityDecisionView,
  IdentityReviewView,
  IntegrityCheckView,
  IntegrityIssueView,
  IntegrityView,
  ManualEditInput,
  MetadataCandidateView,
  MetadataConflictView,
  OfficialProjectView,
  PhaseCandidateView,
  ProjectOfficialVersionView,
  ProjectVersionView,
  ProtocolSessionView,
  ProtocolCategoryChangeWire,
  ProtocolDiffPayload,
  ProtocolDraftDiffWire,
  ProtocolEvidencePayload,
  ProtocolLogicPayload,
  ProtocolOriginalTextPayload,
  ProtocolPredicateValue,
  ProtocolRuleDiffWire,
  ProtocolTimeEntryPayload,
  PublishResultView,
  SourcesView,
  StartDeconstructionResult,
} from "./protocolWorkbenchTypes";
function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（缺少 ${field}）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value;
}

function requireNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为数字）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value;
}

function requireArray<T>(value: unknown, field: string): T[] {
  if (!Array.isArray(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为列表）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value as T[];
}

function requireRecord(value: unknown, field: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为对象）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value as Record<string, unknown>;
}

function requireStudyPhase(value: unknown, field: string): StudyPhase {
  const candidate = requireString(value, field);
  if (
    candidate !== "phase_ii" &&
    candidate !== "phase_iii" &&
    candidate !== "seamless_phase_ii_iii" &&
    candidate !== "other"
  ) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 不是有效研究期别）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return candidate;
}

function optionalStudyPhase(value: unknown, field: string): StudyPhase | null {
  return value === null || value === undefined ? null : requireStudyPhase(value, field);
}

function optionalDatePrecision(value: unknown, field: string): DatePrecision | null {
  if (value === null || value === undefined) return null;
  const candidate = requireString(value, field);
  if (candidate !== "day" && candidate !== "month" && candidate !== "year" && candidate !== "unknown") {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 不是有效日期精度）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return candidate;
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function optionalBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function requireBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为是或否）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value;
}

function requireStringList(value: unknown, field: string): string[] {
  return requireArray<unknown>(value, field).map((item) =>
    requireString(item, `${field}[]`),
  );
}

type DiffChangeField =
  | "original_text_changes"
  | "logic_changes"
  | "time_window_changes"
  | "exception_changes"
  | "evidence_changes"
  | "due_stage_changes";

function invalidDiff(field: string, detail: string): never {
  throw new ProtocolWorkbenchApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    `方案解构服务返回的差异内容无法核对（${field}${detail}）。`,
    "请重新生成方案草稿；若问题持续出现，请联系维护人员。",
  );
}

function requireOneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
  field: string,
): T {
  const candidate = requireString(value, field);
  if (!allowed.includes(candidate as T)) invalidDiff(field, "取值无效");
  return candidate as T;
}

function requireFiniteNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    invalidDiff(field, "应为有效数字");
  }
  return value;
}

function requireNonNegativeNumber(value: unknown, field: string): number {
  const number = requireFiniteNumber(value, field);
  if (number < 0) invalidDiff(field, "不能小于零");
  return number;
}

function optionalStrictString(value: unknown, field: string): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  return requireString(value, field);
}

function optionalStrictBoolean(value: unknown, field: string): boolean | undefined {
  if (value === undefined) return undefined;
  return requireBoolean(value, field);
}

function normalizePredicateValue(value: unknown, field: string): ProtocolPredicateValue {
  if (typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") return requireFiniteNumber(value, field);
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      if (typeof item === "string" || typeof item === "boolean") return item;
      if (typeof item === "number") return requireFiniteNumber(item, `${field}[${index}]`);
      return invalidDiff(`${field}[${index}]`, "判断值只允许文字、数字或是/否");
    });
  }
  return invalidDiff(field, "判断值只允许文字、数字、是/否或其列表");
}

function normalizeLogicPayload(value: unknown, field: string): ProtocolLogicPayload {
  const row = requireRecord(value, field);
  const kind = requireOneOf(row.kind, ["predicate", "logical"] as const, `${field}.kind`);
  if (kind === "predicate") {
    const predicate = requireRecord(row.predicate, `${field}.predicate`);
    const comparator = requireOneOf(
      predicate.comparator,
      ["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "exists"] as const,
      `${field}.predicate.comparator`,
    );
    const hasValue = Object.prototype.hasOwnProperty.call(predicate, "value");
    if (comparator === "exists" && hasValue && predicate.value !== null) {
      invalidDiff(`${field}.predicate.value`, "存在性判断不应携带判断值");
    }
    if (comparator !== "exists" && (!hasValue || predicate.value === null)) {
      invalidDiff(`${field}.predicate.value`, "该比较方式必须携带判断值");
    }
    if ((comparator === "in" || comparator === "not_in") && !Array.isArray(predicate.value)) {
      invalidDiff(`${field}.predicate.value`, "属于或不属于必须使用值列表");
    }
    if (comparator !== "in" && comparator !== "not_in" && Array.isArray(predicate.value)) {
      invalidDiff(`${field}.predicate.value`, "该比较方式不能使用值列表");
    }
    const normalized = {
      subject: requireString(predicate.subject, `${field}.predicate.subject`),
      attribute: requireString(predicate.attribute, `${field}.predicate.attribute`),
      comparator,
    };
    const valuePayload = hasValue && predicate.value !== null
      ? normalizePredicateValue(predicate.value, `${field}.predicate.value`)
      : undefined;
    return {
      kind: "predicate",
      predicate: {
        ...normalized,
        ...(valuePayload === undefined ? {} : { value: valuePayload }),
        ...(optionalStrictString(predicate.unit, `${field}.predicate.unit`) === undefined
          ? {}
          : { unit: optionalStrictString(predicate.unit, `${field}.predicate.unit`) }),
        ...(optionalStrictString(predicate.applicable_population, `${field}.predicate.applicable_population`) === undefined
          ? {}
          : { applicable_population: optionalStrictString(predicate.applicable_population, `${field}.predicate.applicable_population`) }),
        ...(optionalStrictBoolean(predicate.requires_professional_judgment, `${field}.predicate.requires_professional_judgment`) === undefined
          ? {}
          : { requires_professional_judgment: predicate.requires_professional_judgment as boolean }),
        ...(predicate.unit_match_policy === undefined
          ? {}
          : { unit_match_policy: requireString(predicate.unit_match_policy, `${field}.predicate.unit_match_policy`) }),
      },
    };
  }
  const operator = requireOneOf(row.operator, ["all", "any", "not"] as const, `${field}.operator`);
  const children = requireArray<unknown>(row.children, `${field}.children`).map((child, index) =>
    normalizeLogicPayload(child, `${field}.children[${index}]`),
  );
  if (operator === "not" && children.length !== 1) invalidDiff(`${field}.children`, "否定关系必须且只能包含一个条件");
  if ((operator === "all" || operator === "any") && children.length < 2) {
    invalidDiff(`${field}.children`, "并列关系至少需要两个条件");
  }
  return { kind: "logical", operator, children };
}

function normalizeTimeQuantity(value: unknown, field: string) {
  const row = requireRecord(value, field);
  const quantity = requireFiniteNumber(row.value, `${field}.value`);
  if (!Number.isInteger(quantity) || quantity <= 0) invalidDiff(`${field}.value`, "应为大于零的整数");
  return {
    value: quantity,
    unit: requireOneOf(row.unit, ["day", "week", "month", "year"] as const, `${field}.unit`),
  };
}

function normalizeNullableTimeQuantity(value: unknown, field: string) {
  return value === null ? null : normalizeTimeQuantity(value, field);
}

function normalizeTimeEntry(value: unknown, field: string): ProtocolTimeEntryPayload {
  const row = requireRecord(value, field);
  for (const key of ["time_constraint", "occurrence_window", "prospective_window", "prospective_period"] as const) {
    if (!(key in row)) invalidDiff(field, `缺少 ${key}`);
  }
  let timeConstraint: ProtocolTimeEntryPayload["time_constraint"] = null;
  if (row.time_constraint !== null) {
    const constraint = requireRecord(row.time_constraint, `${field}.time_constraint`);
    const direction = requireOneOf(constraint.direction, ["before", "after", "on"] as const, `${field}.time_constraint.direction`);
    const lowerDays = constraint.lower_bound_days == null ? null : requireNonNegativeNumber(constraint.lower_bound_days, `${field}.time_constraint.lower_bound_days`);
    const upperDays = constraint.upper_bound_days == null ? null : requireNonNegativeNumber(constraint.upper_bound_days, `${field}.time_constraint.upper_bound_days`);
    const lowerBound = normalizeNullableTimeQuantity(constraint.lower_bound ?? null, `${field}.time_constraint.lower_bound`);
    const upperBound = normalizeNullableTimeQuantity(constraint.upper_bound ?? null, `${field}.time_constraint.upper_bound`);
    const halfLife = constraint.half_life_multiplier == null ? null : requireFiniteNumber(constraint.half_life_multiplier, `${field}.time_constraint.half_life_multiplier`);
    if (halfLife !== null && halfLife <= 0) invalidDiff(`${field}.time_constraint.half_life_multiplier`, "必须大于零");
    if (lowerDays !== null && lowerBound !== null) invalidDiff(`${field}.time_constraint`, "时间下界不能同时使用天数和日历单位");
    if (upperDays !== null && upperBound !== null) invalidDiff(`${field}.time_constraint`, "时间上界不能同时使用天数和日历单位");
    if (lowerDays !== null && upperDays !== null && lowerDays > upperDays) invalidDiff(`${field}.time_constraint`, "时间下界不能大于上界");
    if (lowerBound !== null && upperBound !== null && lowerBound.unit === upperBound.unit && lowerBound.value > upperBound.value) {
      invalidDiff(`${field}.time_constraint`, "时间下界不能大于上界");
    }
    if (direction === "on" && [lowerDays, upperDays, lowerBound, upperBound, halfLife].some((item) => item !== null)) {
      invalidDiff(`${field}.time_constraint`, "同日要求不能再携带时间范围");
    }
    timeConstraint = {
      anchor_type: requireOneOf(
        constraint.anchor_type,
        ["icf_date", "screening_date", "baseline_date", "randomization_date", "first_dose_date", "study_drug_administration_date", "last_dose_date", "study_completion_date", "event_date", "review_node_date"] as const,
        `${field}.time_constraint.anchor_type`,
      ),
      direction,
      lower_bound_days: lowerDays,
      upper_bound_days: upperDays,
      lower_bound: lowerBound,
      upper_bound: upperBound,
      half_life_multiplier: halfLife,
      allow_partial_date: constraint.allow_partial_date === undefined
        ? false
        : requireBoolean(constraint.allow_partial_date, `${field}.time_constraint.allow_partial_date`),
    };
  }
  let occurrenceWindow: ProtocolTimeEntryPayload["occurrence_window"] = null;
  if (row.occurrence_window !== null) {
    const occurrence = requireRecord(row.occurrence_window, `${field}.occurrence_window`);
    const minimumCount = occurrence.minimum_count == null ? null : requireFiniteNumber(occurrence.minimum_count, `${field}.occurrence_window.minimum_count`);
    if (minimumCount !== null && (!Number.isInteger(minimumCount) || minimumCount <= 0)) {
      invalidDiff(`${field}.occurrence_window.minimum_count`, "应为大于零的整数");
    }
    occurrenceWindow = {
      duration: normalizeTimeQuantity(occurrence.duration, `${field}.occurrence_window.duration`),
      minimum_count: minimumCount,
    };
  }
  let prospectiveWindow: ProtocolTimeEntryPayload["prospective_window"] = null;
  if (row.prospective_window !== null) {
    const prospective = requireRecord(row.prospective_window, `${field}.prospective_window`);
    prospectiveWindow = {
      anchor_type: requireOneOf(prospective.anchor_type, ["study_drug_administration_date", "last_dose_date", "study_completion_date"] as const, `${field}.prospective_window.anchor_type`),
      upper_bound: normalizeTimeQuantity(prospective.upper_bound, `${field}.prospective_window.upper_bound`),
    };
  }
  let prospectivePeriod: ProtocolTimeEntryPayload["prospective_period"] = null;
  if (row.prospective_period !== null) {
    const period = requireRecord(row.prospective_period, `${field}.prospective_period`);
    prospectivePeriod = {
      period: requireOneOf(period.period, ["treatment_period", "study_period"] as const, `${field}.prospective_period.period`),
    };
  }
  return {
    scope: requireOneOf(row.scope, ["main", "exception"] as const, `${field}.scope`),
    time_constraint: timeConstraint,
    occurrence_window: occurrenceWindow,
    prospective_window: prospectiveWindow,
    prospective_period: prospectivePeriod,
  };
}

function normalizeSourceBinding(value: unknown, field: string): ProtocolOriginalTextPayload["source_binding"] {
  if (value === null) return null;
  const row = requireRecord(value, field);
  return {
    source_refs: requireStringList(row.source_refs, `${field}.source_refs`),
    source_excerpts: requireStringList(row.source_excerpts, `${field}.source_excerpts`),
  };
}

function normalizeOriginalText(value: unknown, field: string): ProtocolDiffPayload {
  const row = requireRecord(value, field);
  if ("source_text" in row) return { source_text: requireString(row.source_text, `${field}.source_text`) };
  const fragments = requireArray<unknown>(row.verbatim_fragments, `${field}.verbatim_fragments`).map((item, index) => {
    const fragment = requireRecord(item, `${field}.verbatim_fragments[${index}]`);
    return {
      source_term: optionalStrictString(fragment.source_term, `${field}.verbatim_fragments[${index}].source_term`) ?? null,
      source_clause: optionalStrictString(fragment.source_clause, `${field}.verbatim_fragments[${index}].source_clause`) ?? null,
      source_clauses: requireStringList(fragment.source_clauses, `${field}.verbatim_fragments[${index}].source_clauses`),
    };
  });
  return {
    title: requireString(row.title, `${field}.title`),
    source_binding: normalizeSourceBinding(row.source_binding, `${field}.source_binding`),
    verbatim_fragments: fragments,
  };
}

function normalizeEvidence(value: unknown, field: string): ProtocolEvidencePayload | { evidence: ProtocolEvidencePayload } {
  const evidenceRow = requireRecord(value, field);
  const wrapped = Object.prototype.hasOwnProperty.call(evidenceRow, "evidence");
  const row = wrapped ? requireRecord(evidenceRow.evidence, `${field}.evidence`) : evidenceRow;
  const evidence = {
    fact_type: requireString(row.fact_type, `${field}.fact_type`),
    required_source_types: requireStringList(row.required_source_types, `${field}.required_source_types`),
    allows_screening_record_transcription: requireBoolean(row.allows_screening_record_transcription, `${field}.allows_screening_record_transcription`),
    requires_contemporaneous_objective_source: requireBoolean(row.requires_contemporaneous_objective_source, `${field}.requires_contemporaneous_objective_source`),
    source_validity_window: normalizeNullableTimeQuantity(
      row.source_validity_window ?? null,
      `${field}.source_validity_window`,
    ),
    description: requireString(row.description, `${field}.description`),
  };
  return wrapped ? { evidence } : evidence;
}

function normalizePayload(value: unknown, category: DiffChangeField, field: string): ProtocolDiffPayload | null {
  if (value === null) return null;
  if (category === "original_text_changes") return normalizeOriginalText(value, field);
  if (category === "logic_changes" || category === "exception_changes") return normalizeLogicPayload(value, field);
  if (category === "time_window_changes") {
    return requireArray<unknown>(value, field).map((item, index) => normalizeTimeEntry(item, `${field}[${index}]`));
  }
  if (category === "evidence_changes") {
    if (Array.isArray(value)) return value.map((item, index) => normalizeEvidence(item, `${field}[${index}]`));
    return normalizeEvidence(value, field);
  }
  return requireArray<unknown>(value, field).map((item, index) => {
    const row = requireRecord(item, `${field}[${index}]`);
    return {
      fact_type: requireString(row.fact_type, `${field}[${index}].fact_type`),
      due_stages: requireArray<unknown>(row.due_stages, `${field}[${index}].due_stages`).map((stage, stageIndex) =>
        requireOneOf(stage, ["pre_screening", "screening", "run_in", "baseline"] as const, `${field}[${index}].due_stages[${stageIndex}]`),
      ),
    };
  });
}

function normalizeCategoryChange(raw: unknown, field: string, category: DiffChangeField): ProtocolCategoryChangeWire {
  const row = requireRecord(raw, field);
  const kind = requireString(row.kind, `${field}.kind`);
  if (kind !== "rule" && kind !== "component" && kind !== "requirement") {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field}.kind 无法识别）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  if (!("previous" in row) || !("current" in row)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 缺少前后对照内容）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  if (row.previous === null && row.current === null) {
    invalidDiff(field, "前后内容不能同时为空");
  }
  if (
    (category === "logic_changes" ||
      category === "time_window_changes" ||
      category === "exception_changes" ||
      category === "due_stage_changes") &&
    kind !== "component"
  ) {
    invalidDiff(`${field}.kind`, "该差异只能归属入排子项");
  }
  if (category === "original_text_changes" && kind === "requirement") {
    invalidDiff(`${field}.kind`, "原文差异不能归属资料要求");
  }
  if (category === "evidence_changes" && kind === "rule") {
    invalidDiff(`${field}.kind`, "证据要求差异不能归属整条父规则");
  }
  if (
    category !== "exception_changes" &&
    category !== "evidence_changes" &&
    (row.previous === null || row.current === null)
  ) {
    invalidDiff(field, "该差异必须同时提供正式版本和新草稿内容");
  }
  if (
    category === "evidence_changes" &&
    kind === "component" &&
    (row.previous === null || row.current === null)
  ) {
    invalidDiff(field, "子项证据差异必须同时提供前后内容");
  }
  if (
    category === "evidence_changes" &&
    kind === "requirement" &&
    ((row.previous === null) === (row.current === null))
  ) {
    invalidDiff(field, "单条资料要求的新增或删除必须且只能有一侧内容");
  }
  return {
    stable_ref: requireString(row.stable_ref, `${field}.stable_ref`),
    kind,
    previous: normalizePayload(row.previous, category, `${field}.previous`),
    current: normalizePayload(row.current, category, `${field}.current`),
  };
}

const DIFF_CHANGE_FIELDS = [
  "original_text_changes",
  "logic_changes",
  "time_window_changes",
  "exception_changes",
  "evidence_changes",
  "due_stage_changes",
] as const satisfies readonly DiffChangeField[];

function normalizeRuleDiff(raw: unknown, index: number): ProtocolRuleDiffWire {
  const field = `rule_diffs[${index}]`;
  const row = requireRecord(raw, field);
  const changes = Object.fromEntries(
    DIFF_CHANGE_FIELDS.map((name) => [
      name,
      requireArray<unknown>(row[name], `${field}.${name}`).map((item, itemIndex) =>
        normalizeCategoryChange(item, `${field}.${name}[${itemIndex}]`, name),
      ),
    ]),
  ) as Pick<ProtocolRuleDiffWire, (typeof DIFF_CHANGE_FIELDS)[number]>;
  return {
    official_code: requireString(row.official_code, `${field}.official_code`),
    added: requireBoolean(row.added, `${field}.added`),
    removed: requireBoolean(row.removed, `${field}.removed`),
    added_component_refs: requireStringList(
      row.added_component_refs,
      `${field}.added_component_refs`,
    ),
    removed_component_refs: requireStringList(
      row.removed_component_refs,
      `${field}.removed_component_refs`,
    ),
    ...changes,
  };
}

export function normalizeProtocolDraftDiff(raw: unknown): ProtocolDraftDiffWire {
  const row = requireRecord(raw, "diff");
  return {
    added_rule_codes: requireStringList(row.added_rule_codes, "diff.added_rule_codes"),
    removed_rule_codes: requireStringList(row.removed_rule_codes, "diff.removed_rule_codes"),
    modified_rule_codes: requireStringList(row.modified_rule_codes, "diff.modified_rule_codes"),
    added_workflow_stage_ids: requireStringList(row.added_workflow_stage_ids, "diff.added_workflow_stage_ids"),
    removed_workflow_stage_ids: requireStringList(row.removed_workflow_stage_ids, "diff.removed_workflow_stage_ids"),
    modified_workflow_stage_ids: requireStringList(row.modified_workflow_stage_ids, "diff.modified_workflow_stage_ids"),
    changed_component_ids: requireStringList(row.changed_component_ids, "diff.changed_component_ids"),
    changed_requirement_ids: requireStringList(row.changed_requirement_ids, "diff.changed_requirement_ids"),
    changed_procedure_mapping_ids: requireStringList(row.changed_procedure_mapping_ids, "diff.changed_procedure_mapping_ids"),
    source_scope_changed: requireBoolean(row.source_scope_changed, "diff.source_scope_changed"),
    workflow_visit_rewritten: requireBoolean(row.workflow_visit_rewritten, "diff.workflow_visit_rewritten"),
    clarification_semantics_changed: requireBoolean(row.clarification_semantics_changed, "diff.clarification_semantics_changed"),
    rule_diffs: requireArray<unknown>(row.rule_diffs, "diff.rule_diffs").map(normalizeRuleDiff),
  };
}

export function decodeProtocolWorkbenchError(payload: unknown): ProtocolWorkbenchApiError {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "error" in payload &&
    payload.error !== null &&
    typeof payload.error === "object"
  ) {
    const error = requireRecord(payload.error, "error");
    const detail =
      typeof error.detail === "string" && error.detail.length > 0
        ? error.detail
        : "请求未能完成。";
    const title = typeof error.title === "string" ? error.title : "操作失败";
    const code = typeof error.code === "string" ? error.code : "UNKNOWN";
    const recovery =
      typeof error.recovery_action === "string" && error.recovery_action.length > 0
        ? error.recovery_action
        : "请稍后重试。";
    return new ProtocolWorkbenchApiError(code, title, detail, recovery);
  }
  return new ProtocolWorkbenchApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    "方案解构服务返回了无法识别的错误格式。",
    "请稍后重试；若问题持续出现，请联系维护人员。",
  );
}

export function normalizeStartDeconstruction(
  wire: unknown,
): StartDeconstructionResult {
  const row = requireRecord(wire, "start_deconstruction");
  return {
    jobId: requireString(row.job_id, "job_id"),
    state: requireString(row.state, "state"),
    stateLabel: requireString(row.state_label, "state_label"),
    created: row.created === true,
    sourceArtifactId: requireString(row.source_artifact_id, "source_artifact_id"),
    fileName: requireString(row.file_name, "file_name"),
  };
}

export function normalizeSession(wire: unknown): ProtocolSessionView {
  const row = requireRecord(wire, "session");
  return {
    jobId: requireString(row.job_id, "job_id"),
    jobType: requireString(row.job_type, "job_type"),
    state: requireString(row.state, "state"),
    stateLabel: requireString(row.state_label, "state_label"),
    progressCompleted: requireNumber(row.progress_completed, "progress_completed"),
    progressTotal: requireNumber(row.progress_total, "progress_total"),
    sessionKind: requireString(row.session_kind, "session_kind"),
    awaitingUser: optionalString(row.awaiting_user),
    awaitingUserLabel: optionalString(row.awaiting_user_label),
    sourceArtifactId: optionalString(row.source_artifact_id),
    fileName: optionalString(row.file_name),
    snapshotId: optionalString(row.snapshot_id),
    draftId: optionalString(row.draft_id),
    draftRevisionId: optionalString(row.draft_revision_id),
    draftRevisionNumber: optionalNumber(row.draft_revision_number),
    draftStatus: optionalString(row.draft_status),
    draftStatusLabel: optionalString(row.draft_status_label),
    selectedPhase: optionalStudyPhase(row.selected_phase, "selected_phase"),
    selectedPhaseLabel: optionalString(row.selected_phase_label),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    recoveryCheckpointId: optionalString(row.recovery_checkpoint_id),
    recoveryStepId: optionalString(row.recovery_step_id),
    nextAction: requireString(row.next_action, "next_action"),
    publishable: optionalBoolean(row.publishable),
    targetProjectId: optionalString(row.target_project_id),
    targetProjectName: optionalString(row.target_project_name),
    targetProjectCode: optionalString(row.target_project_code),
    targetProtocolCode: optionalString(row.target_protocol_code),
    targetStudyPhase: optionalStudyPhase(row.target_study_phase, "target_study_phase"),
    targetStudyPhaseLabel: optionalString(row.target_study_phase_label),
    targetOfficialVersion: optionalString(row.target_official_version),
    targetRuleSetRevision: optionalNumber(row.target_rule_set_revision),
  };
}

function normalizePhaseCandidate(
  raw: unknown,
): PhaseCandidateView {
  const row = requireRecord(raw, "phase_candidates[]");
  return {
    candidateId: requireString(row.candidate_id, "candidate_id"),
    phase: requireStudyPhase(row.phase, "phase"),
    phaseLabel: requireString(row.phase_label, "phase_label"),
    rationale: requireString(row.rationale, "rationale"),
    sourceExcerpt: requireString(row.source_excerpt, "source_excerpt"),
  };
}

function normalizeMetadataCandidate(
  raw: unknown,
): MetadataCandidateView {
  const row = requireRecord(raw, "metadata_candidates[]");
  return {
    candidateId: requireString(row.candidate_id, "candidate_id"),
    field: requireString(row.field, "field"),
    fieldLabel: requireString(row.field_label, "field_label"),
    value: requireString(row.value, "value"),
    sourceLabel: requireString(row.source_label, "source_label"),
    sourceExcerpt: requireString(row.source_excerpt, "source_excerpt"),
    isFallback: row.is_fallback === true,
  };
}

function normalizeMetadataConflict(
  raw: unknown,
): MetadataConflictView {
  const row = requireRecord(raw, "metadata_conflicts[]");
  const candidates = requireArray<unknown>(
    row.candidates,
    "metadata_conflicts[].candidates",
  ).map((item) => {
    const candidate = requireRecord(item, "metadata_conflicts[].candidates[]");
    return {
      candidateId: requireString(candidate.candidate_id, "candidate_id"),
      value: requireString(candidate.value, "value"),
      sourceLabel: requireString(candidate.source_label, "source_label"),
    };
  });
  return {
    conflictId: requireString(row.conflict_id, "conflict_id"),
    field: requireString(row.field, "field"),
    fieldLabel: requireString(row.field_label, "field_label"),
    reason: requireString(row.reason, "reason"),
    candidates,
  };
}

function normalizeIdentityDecision(wire: unknown): IdentityDecisionView {
  const row = requireRecord(wire, "identity");
  return {
    identityDecisionId: requireString(row.identity_decision_id, "identity_decision_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    status: requireString(row.status, "status"),
    statusLabel: requireString(row.status_label, "status_label"),
    projectName: optionalString(row.project_name),
    projectCode: optionalString(row.project_code),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    officialDateValue: optionalString(row.official_date_value),
    officialDatePrecision: optionalDatePrecision(
      row.official_date_precision,
      "official_date_precision",
    ),
    studyPhase: optionalStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: optionalString(row.study_phase_label),
    confirmationRequired: row.confirmation_required === true,
    conflictIds: requireArray<unknown>(row.conflict_ids, "conflict_ids").map((value) =>
      requireString(value, "conflict_ids[]"),
    ),
    selectedCandidateIds: requireArray<unknown>(
      row.selected_candidate_ids,
      "selected_candidate_ids",
    ).map((value) => requireString(value, "selected_candidate_ids[]")),
  };
}

export function normalizeIdentityReview(wire: unknown): IdentityReviewView {
  const row = requireRecord(wire, "identity_review");
  return {
    jobId: requireString(row.job_id, "job_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    confirmationRequired: row.confirmation_required === true,
    identity: normalizeIdentityDecision(row.identity),
    phaseCandidates: requireArray<unknown>(
      row.phase_candidates,
      "phase_candidates",
    ).map(normalizePhaseCandidate),
    metadataCandidates: requireArray<unknown>(
      row.metadata_candidates,
      "metadata_candidates",
    ).map(normalizeMetadataCandidate),
    metadataConflicts: requireArray<unknown>(
      row.metadata_conflicts,
      "metadata_conflicts",
    ).map(normalizeMetadataConflict),
  };
}

export function normalizeDraftRevision(wire: unknown): DraftRevisionView {
  const row = requireRecord(wire, "draft");
  return {
    jobId: requireString(row.job_id, "job_id"),
    revisionId: requireString(row.revision_id, "revision_id"),
    draftId: requireString(row.draft_id, "draft_id"),
    revisionNumber: requireNumber(row.revision_number, "revision_number"),
    status: requireString(row.status, "status"),
    statusLabel: requireString(row.status_label, "status_label"),
    reason: requireString(row.reason, "reason"),
    reasonLabel: requireString(row.reason_label, "reason_label"),
    actor: requireString(row.actor, "actor"),
    createdAt: requireString(row.created_at, "created_at"),
    studyPhase: requireStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: requireString(row.study_phase_label, "study_phase_label"),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    ruleCount: requireNumber(row.rule_count, "rule_count"),
    workflowStageCount: requireNumber(row.workflow_stage_count, "workflow_stage_count"),
    content: requireRecord(row.content, "content"),
    diff:
      row.diff === null || row.diff === undefined
        ? null
        : normalizeProtocolDraftDiff(row.diff),
  };
}

function normalizeIntegrityIssue(wire: unknown): IntegrityIssueView {
  const row = requireRecord(wire, "issues[]");
  return {
    issueCode: requireString(row.issue_code, "issue_code"),
    checkName: requireString(row.check_name, "check_name"),
    level: requireString(row.level, "level"),
    problem: requireString(row.problem, "problem"),
    impact: requireString(row.impact, "impact"),
    nextAction: requireString(row.next_action, "next_action"),
    affectedRefs: requireArray<unknown>(row.affected_refs, "affected_refs").map((value) =>
      requireString(value, "affected_refs[]"),
    ),
    repairScope: requireArray<unknown>(row.repair_scope, "repair_scope").map((value) =>
      requireString(value, "repair_scope[]"),
    ),
  };
}

function normalizeIntegrityCheck(wire: unknown): IntegrityCheckView {
  const row = requireRecord(wire, "checks[]");
  return {
    checkName: requireString(row.check_name, "check_name"),
    passed: row.passed === true,
    issueCount: requireNumber(row.issue_count, "issue_count"),
  };
}

export function normalizeIntegrity(wire: unknown): IntegrityView {
  const row = requireRecord(wire, "integrity");
  return {
    jobId: requireString(row.job_id, "job_id"),
    publishable: row.publishable === true,
    blockingCount: requireNumber(row.blocking_count, "blocking_count"),
    reviewCount: requireNumber(row.review_count, "review_count"),
    reminderCount: requireNumber(row.reminder_count, "reminder_count"),
    summary: requireString(row.summary, "summary"),
    checks: requireArray<unknown>(row.checks, "checks").map(normalizeIntegrityCheck),
    issues: requireArray<unknown>(row.issues, "issues").map(normalizeIntegrityIssue),
  };
}

export function normalizeSources(wire: unknown): SourcesView {
  const row = requireRecord(wire, "sources");
  return {
    jobId: requireString(row.job_id, "job_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    selectedPhase: requireStudyPhase(row.selected_phase, "selected_phase"),
    selectedPhaseLabel: requireString(row.selected_phase_label, "selected_phase_label"),
    sourceSpans: requireRecord(row.source_spans, "source_spans"),
    sourceMaterials: requireRecord(row.source_materials, "source_materials"),
  };
}

export function normalizeGenerationPreview(wire: unknown): GenerationPreviewView {
  const row = requireRecord(wire, "generation_preview");
  const reason = row.reason === null || row.reason === undefined ? null : requireString(row.reason, "reason");
  const detail = row.detail === null || row.detail === undefined ? null : requireString(row.detail, "detail");
  const updatedAt =
    row.updated_at === null || row.updated_at === undefined
      ? null
      : requireString(row.updated_at, "updated_at");
  return {
    jobId: requireString(row.job_id, "job_id"),
    available: row.available === true,
    reason,
    detail,
    previewOnly: row.preview_only !== false,
    batchIndex: requireNumber(row.batch_index, "batch_index"),
    batchTotal: requireNumber(row.batch_total, "batch_total"),
    updatedAt,
    pendingCodes: requireArray<unknown>(row.pending_codes, "pending_codes").map((value) =>
      requireString(value, "pending_codes[]"),
    ),
    unresolvedCount: requireNumber(row.unresolved_count, "unresolved_count"),
    content: requireRecord(row.content, "content"),
  };
}

export function normalizePublishResult(wire: unknown): PublishResultView {
  const row = requireRecord(wire, "publish");
  return {
    jobId: requireString(row.job_id, "job_id"),
    projectId: requireString(row.project_id, "project_id"),
    protocolVersionId: requireString(row.protocol_version_id, "protocol_version_id"),
    ruleSetId: requireString(row.rule_set_id, "rule_set_id"),
    ruleSetRevision: requireNumber(row.rule_set_revision, "rule_set_revision"),
    replay: row.replay === true,
  };
}

/** 确认身份请求：视图 camelCase → wire snake_case。 */
export function encodeConfirmIdentity(input: ConfirmIdentityInput): Record<string, unknown> {
  return {
    protocol_code: input.protocolCode,
    project_name: input.projectName,
    project_code: input.projectCode ?? null,
    official_version: input.officialVersion,
    official_date_value: input.officialDateValue,
    official_date_precision: input.officialDatePrecision,
    study_phase: input.studyPhase,
    selected_candidate_ids: input.selectedCandidateIds ?? [],
    actor: input.actor ?? "用户",
  };
}

function normalizeOfficialProject(raw: unknown): OfficialProjectView {
  const row = requireRecord(raw, "projects[]");
  return {
    projectId: requireString(row.project_id, "project_id"),
    projectCode: requireString(row.project_code, "project_code"),
    projectName: requireString(row.project_name, "project_name"),
    studyPhase: requireStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: requireString(row.study_phase_label, "study_phase_label"),
    protocolCode: requireString(row.protocol_code, "protocol_code"),
    officialVersion: requireString(row.official_version, "official_version"),
    officialDateValue: optionalString(row.official_date_value),
    officialDatePrecision: optionalDatePrecision(
      row.official_date_precision,
      "official_date_precision",
    ),
    ruleSetId: requireString(row.rule_set_id, "rule_set_id"),
    ruleSetRevision: requireNumber(row.rule_set_revision, "rule_set_revision"),
  };
}

export function normalizeOfficialProjectList(wire: unknown): OfficialProjectView[] {
  const row = requireRecord(wire, "official_project_list");
  return requireArray<unknown>(row.projects, "projects").map(normalizeOfficialProject);
}

export function normalizeProjectOfficialVersion(
  wire: unknown,
): ProjectOfficialVersionView {
  const row = requireRecord(wire, "project_official_version");
  const versions = requireArray<unknown>(row.versions, "versions").map((item) => {
    const version = requireRecord(item, "versions[]");
    return {
      ruleSetRevision: requireNumber(version.rule_set_revision, "rule_set_revision"),
      protocolVersionId: requireString(
        version.protocol_version_id,
        "protocol_version_id",
      ),
      officialVersion: requireString(version.official_version, "official_version"),
      officialDateValue: optionalString(version.official_date_value),
      officialDatePrecision: optionalDatePrecision(
        version.official_date_precision,
        "official_date_precision",
      ),
      sha256: requireString(version.sha256, "sha256"),
      ruleCount: requireNumber(version.rule_count, "rule_count"),
      publishedAt: requireString(version.published_at, "published_at"),
    } as ProjectVersionView;
  });
  return {
    project: normalizeOfficialProject(row.project),
    versions,
    publicationCount: requireNumber(row.publication_count, "publication_count"),
  };
}

function normalizeDraftComparisonSide(raw: unknown): DraftComparisonSideView {
  const row = requireRecord(raw, "draft_comparison_side");
  return {
    revisionId: requireString(row.revision_id, "revision_id"),
    draftId: requireString(row.draft_id, "draft_id"),
    protocolVersionId: requireString(
      row.protocol_version_id,
      "protocol_version_id",
    ),
    officialVersion: optionalString(row.official_version),
    revisionNumber: optionalNumber(row.revision_number),
    status: optionalString(row.status),
    ruleCount: requireNumber(row.rule_count, "rule_count"),
    workflowStageCount: requireNumber(row.workflow_stage_count, "workflow_stage_count"),
    isFormalBaseline: row.is_formal_baseline === true,
    content: requireRecord(row.content, "content"),
    sourceRefs: requireArray<unknown>(row.source_refs, "source_refs").map((value) =>
      requireString(value, "source_refs[]"),
    ),
  };
}

export function normalizeDraftComparison(wire: unknown): DraftComparisonView {
  const row = requireRecord(wire, "draft_comparison");
  return {
    jobId: requireString(row.job_id, "job_id"),
    baseline: normalizeDraftComparisonSide(row.baseline),
    candidate: normalizeDraftComparisonSide(row.candidate),
    diff: normalizeProtocolDraftDiff(row.diff),
    sourceBound: row.source_bound === true,
  };
}

/** 反馈修订请求：视图 → wire snake_case（原文理解纠错 / 补充解释）。 */
export function encodeFeedback(input: FeedbackInput): Record<string, unknown> {
  return {
    expected_revision_id: input.expectedRevisionId,
    feedback_kind: input.feedbackKind,
    target_rule_code: input.targetRuleCode,
    feedback_note: input.feedbackNote,
    actor: input.actor ?? "用户",
  };
}

/** 手工修订草稿请求：视图 → wire snake_case。 */
export function encodeManualEdit(input: ManualEditInput): Record<string, unknown> {
  return {
    expected_revision_id: input.expectedRevisionId,
    draft: input.draft,
    actor: input.actor ?? "用户",
  };
}
