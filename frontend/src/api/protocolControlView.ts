import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";

export interface ControlAtomView {
  statement: string;
  excerpts: string[];
  professionalJudgment: boolean;
  qualifiers: string[];
  continuing: { statement: string; period: string; excerpts: string[] } | null;
}

export interface ControlGroupView {
  atoms: ControlAtomView[];
  triggerBranches: string[];
  activatedBy: string[];
  waivesBranches: string[];
  activatesGroups: string[];
}

export interface ControlRequirementView {
  id: string;
  title: string;
  population: string;
  applicability: ControlGroupView[];
  triggers: ControlGroupView[];
  obligations: ControlGroupView[];
  exceptions: ControlGroupView[];
  nodes: { label: string; role: string; guidance: string | null }[];
  evidence: {
    description: string; dueStage: string; sourcePolicy: string[]; excerpts: string[];
    purposes: { label: string; statement: string }[];
  }[];
  relations: { kind: string; left: string; right: string; node: string | null; notes: string | null }[];
}

export interface ProtocolControlRequirements {
  jobId: string;
  sourceJobId: string;
  checkpointId: string;
  requirements: ControlRequirementView[];
}

function invalid(): never {
  throw new ProtocolWorkbenchApiError(
    "INVALID_RESPONSE", "补充审核要求暂不可用",
    "整理结果的内容或关联不完整，暂不能随方案发布。",
    "请刷新查看；已经保存的结果不会被覆盖。",
  );
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  return value as Record<string, unknown>;
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? value : invalid(); }
function string(value: unknown): string { return typeof value === "string" && value.trim() ? value : invalid(); }
function optionalString(value: unknown): string | null { return value === null ? null : string(value); }
function strings(value: unknown): string[] { return array(value).map(string); }

const stages: Record<string, string> = {
  pre_screening: "预筛选", screening: "筛选期", run_in: "导入期", baseline: "基线期",
};
const roles: Record<string, string> = {
  early_attention: "提前关注", decide_at_node: "本次审核", later_node_review: "后续复核",
};
const relationKinds: Record<string, string> = {
  duplicate_statement: "重复表述", supplementary_requirement: "补充要求",
  further_explanation: "进一步说明", substantive_conflict: "内容存在冲突",
};
function label(mapping: Record<string, string>, value: unknown): string {
  return mapping[string(value)] ?? invalid();
}

function expression(raw: unknown): Record<string, unknown>[] {
  return raw === null ? [] : array(object(raw).groups).map(object);
}

function names(groups: Record<string, unknown>[], field: string, prefix: string): Map<string, string> {
  const result = new Map<string, string>();
  groups.forEach((group, index) => {
    const id = string(group[field]);
    if (result.has(id)) invalid();
    result.set(id, `${prefix}${index + 1}`);
  });
  return result;
}

function references(raw: unknown, known: Map<string, string>): string[] {
  return strings(raw).map((id) => known.get(id) ?? invalid());
}

const anchors: Record<string, string> = {
  icf_date: "签署知情同意日", screening_date: "筛选日", baseline_date: "基线日",
  randomization_date: "随机日", first_dose_date: "首次给药日",
  study_drug_administration_date: "研究药物给药日", last_dose_date: "末次给药日",
  study_completion_date: "研究完成日", event_date: "事件发生日", review_node_date: "本次审核节点日期",
};

function timeDescription(raw: unknown): string | null {
  if (raw === null) return null;
  const value = object(raw);
  const anchor = label(anchors, value.anchor_type);
  const direction = label({ before: "前", after: "后", on: "当日" }, value.direction);
  if (typeof value.lower_bound_inclusive !== "boolean" || typeof value.upper_bound_inclusive !== "boolean" ||
      typeof value.allow_partial_date !== "boolean") invalid();
  function bound(quantity: unknown, days: unknown): string | null {
    if (quantity !== null) {
      if (days !== null) return invalid();
      const q = object(quantity);
      if (typeof q.value !== "number" || !Number.isSafeInteger(q.value) || q.value <= 0) return invalid();
      return `${q.value}${label({ day: "天", week: "周", month: "个月", year: "年" }, q.unit)}`;
    }
    if (days === null) return null;
    if (typeof days !== "number" || !Number.isSafeInteger(days) || days < 0) return invalid();
    return `${days}天`;
  }
  const lower = bound(value.lower_bound, value.lower_bound_days);
  const upper = bound(value.upper_bound, value.upper_bound_days);
  const ranges: string[] = [];
  if (lower !== null) ranges.push(`${value.lower_bound_inclusive ? "至少" : "超过"}${lower}`);
  if (upper !== null) ranges.push(`${value.upper_bound_inclusive ? "不超过" : "少于"}${upper}`);
  const halfLife = value.half_life_multiplier;
  if (halfLife !== null && (typeof halfLife !== "number" || !Number.isFinite(halfLife) || halfLife <= 0)) invalid();
  if (value.direction === "on" && (ranges.length || halfLife !== null || value.combined_window_selection !== null)) invalid();
  let description = value.direction === "on" ? anchor : `${anchor}${direction}${ranges.join("且")}`;
  if (halfLife !== null) {
    if (ranges.length) {
      if (value.combined_window_selection !== "longer_of_calendar_and_half_life") invalid();
      description += `，与${halfLife}个半衰期相比取较长时间`;
    } else {
      if (value.combined_window_selection !== null) invalid();
      description += `${halfLife}个半衰期`;
    }
  } else if (value.combined_window_selection !== null) invalid();
  if (value.allow_partial_date) description += "；保留不完整日期范围";
  return description;
}

export function normalizeProtocolControlRequirements(raw: unknown): ProtocolControlRequirements {
  const payload = object(raw);
  const targetLabels = object(payload.relation_target_labels);
  function targetLabel(kind: unknown, id: unknown): string {
    const targetId = string(id);
    if (kind === "official_rule") {
      const match = /^(IN|EX)-(\d{2})$/.exec(targetId);
      if (!match) return invalid();
      return `${match[1] === "IN" ? "入选" : "排除"}标准第${Number(match[2])}条`;
    }
    return string(targetLabels[`${string(kind)}:${targetId}`]);
  }
  const nodeLabels = new Map<string, string>();
  array(payload.workflow_stages).forEach((rawNode) => {
    const node = object(rawNode);
    const id = string(node.workflow_stage_id);
    if (nodeLabels.has(id)) invalid();
    nodeLabels.set(id, string(node.display_name));
  });
  const ids = new Set<string>();
  const requirements = array(payload.candidates).map((rawCandidate): ControlRequirementView => {
    const candidate = object(rawCandidate);
    const id = string(candidate.control_candidate_id);
    if (ids.has(id)) invalid();
    ids.add(id);
    const semantics = object(candidate.semantics);
    if (semantics.control_candidate_id !== id || semantics.title !== candidate.title ||
        semantics.applicable_population !== candidate.applicable_population) invalid();
    const applicability = expression(semantics.applicability_expression);
    const triggers = expression(semantics.trigger_expression);
    const obligations = expression(semantics.obligation_expression);
    const exceptions = expression(semantics.exception_expression);
    if (!obligations.length) invalid();
    const triggerNames = names(triggers, "trigger_branch_id", "触发条件组");
    const obligationNames = names(obligations, "obligation_group_id", "要求组");
    const exceptionNames = names(exceptions, "exception_group_id", "例外组");
    function groups(rows: Record<string, unknown>[], layer: string): ControlGroupView[] {
      return rows.map((group) => {
        const atoms = array(group.atoms).map((rawAtom): ControlAtomView => {
          const atom = object(rawAtom);
          if (typeof atom.requires_professional_judgment !== "boolean") invalid();
          const excerpts = strings(atom.source_excerpts);
          if (!excerpts.length) invalid();
          const qualifiers: string[] = [];
          const time = timeDescription(atom.time_constraint);
          if (time !== null) qualifiers.push(time);
          if (layer === "obligation") {
            qualifiers.push(label({ mandatory: "必须", recommended: "建议", best_effort: "尽力完成" }, atom.modality));
            if (atom.temporal_scope !== null) qualifiers.push(label({
              calendar_lookback: "按规定时间回溯", full_history: "完整既往历程",
              official_rule_defined: "按对应入排标准的时间要求", since_previous_visit: "自上次访视以来",
            }, atom.temporal_scope));
            if (atom.prospective_period !== null) qualifiers.push(label({
              treatment_period: "治疗期间", study_period: "研究期间",
            }, object(atom.prospective_period).period));
          }
          let continuing: ControlAtomView["continuing"] = null;
          if (layer === "obligation" && atom.continuing_obligation != null) {
            const future = object(atom.continuing_obligation);
            if (future.status !== "not_due_at_review_node") invalid();
            continuing = {
              statement: string(future.statement),
              period: label({ treatment_period: "治疗期间", study_period: "研究期间" }, object(future.prospective_period).period),
              excerpts: strings(future.source_excerpts),
            };
            if (!continuing.excerpts.length) invalid();
          }
          return { statement: string(atom.statement), excerpts, qualifiers, continuing, professionalJudgment: atom.requires_professional_judgment };
        });
        if (!atoms.length) invalid();
        return {
          atoms,
          triggerBranches: layer === "obligation" ? references(group.applies_to_trigger_branch_ids, triggerNames) : [],
          activatedBy: layer === "obligation" ? references(group.activated_by_exception_group_ids, exceptionNames) : [],
          waivesBranches: layer === "exception" ? references(group.waives_trigger_branch_ids, triggerNames) : [],
          activatesGroups: layer === "exception" ? references(group.activates_obligation_group_ids, obligationNames) : [],
        };
      });
    }
    return {
      id, title: string(candidate.title), population: string(candidate.applicable_population),
      applicability: groups(applicability, "applicability"), triggers: groups(triggers, "trigger"),
      obligations: groups(obligations, "obligation"), exceptions: groups(exceptions, "exception"),
      nodes: array(semantics.review_node_bindings).map((rawNode) => {
        const node = object(rawNode);
        return {
          label: nodeLabels.get(string(node.workflow_stage_id)) ?? invalid(),
          role: label(roles, node.role), guidance: optionalString(node.guidance),
        };
      }),
      evidence: array(semantics.minimum_evidence).map((rawEvidence) => {
        const evidence = object(rawEvidence);
        const dependencyLayers: Record<string, { label: string; groups: Record<string, unknown>[] }> = {
          applicability: { label: "核实适用条件", groups: applicability },
          trigger: { label: "核实触发条件", groups: triggers },
          obligation: { label: "核实具体要求", groups: obligations },
          exception: { label: "核实例外条件", groups: exceptions },
        };
        const dependencyKeys = new Set<string>();
        const purposes = (evidence.atom_refs === undefined ? [] : array(evidence.atom_refs)).map((rawRef) => {
          const ref = object(rawRef);
          const layer = string(ref.layer);
          const groupIndex = ref.group_index;
          const atomIndex = ref.atom_index;
          if (typeof groupIndex !== "number" || !Number.isSafeInteger(groupIndex) || groupIndex < 0 ||
              typeof atomIndex !== "number" || !Number.isSafeInteger(atomIndex) || atomIndex < 0) return invalid();
          const dependency = Object.hasOwn(dependencyLayers, layer) ? dependencyLayers[layer] : invalid();
          const group = dependency.groups[groupIndex];
          if (!group) return invalid();
          const atom = object(array(group.atoms)[atomIndex]);
          const key = `${layer}:${groupIndex}:${atomIndex}`;
          if (dependencyKeys.has(key)) return invalid();
          dependencyKeys.add(key);
          return { label: dependency.label, statement: string(atom.statement) };
        });
        const evidenceNodes = strings(evidence.workflow_stage_ids);
        if (!evidenceNodes.length || new Set(evidenceNodes).size !== evidenceNodes.length) invalid();
        const dueStage = `${label(stages, evidence.due_stage)}：${evidenceNodes.map((node) => nodeLabels.get(node) ?? invalid()).join("、")}`;
        const policy = object(evidence.source_policy);
        function policyText(value: unknown, yes: string, no: string, unknown: string): string {
          return value === true ? yes : value === false ? no : value === null ? unknown : invalid();
        }
        const sourcePolicy = [
          policyText(policy.requires_contemporaneous_objective_source, "须有同期客观原始记录", "未要求同期客观原始记录", "是否需要同期原始记录尚未明确"),
          policyText(policy.allows_screening_record_transcription, "允许以筛选病历转述，仍保留来源提示", "不接受仅有筛选病历转述", "是否接受筛选病历转述尚未明确"),
        ];
        if (policy.result_validity_status === "specified") {
          const time = timeDescription(policy.result_validity_constraint);
          if (time === null) invalid();
          sourcePolicy.push(`结果时间要求：${time}`);
        } else {
          if (policy.result_validity_constraint !== null) invalid();
          sourcePolicy.push(label({ not_specified: "未另列结果有效期，仍须结合具体审核要求", unknown: "结果有效期尚未明确" }, policy.result_validity_status));
        }
        const excerpts = strings(policy.source_excerpts);
        if (!excerpts.length) invalid();
        return { description: string(evidence.description), dueStage, sourcePolicy, excerpts, purposes };
      }),
      relations: array(semantics.cross_source_relations).map((rawRelation) => {
        const relation = object(rawRelation);
        const node = optionalString(relation.affected_workflow_stage_id);
        return {
          kind: label(relationKinds, relation.kind),
          left: targetLabel(relation.left_target_kind, relation.left_target_id),
          right: targetLabel(relation.right_target_kind, relation.right_target_id),
          node: node === null ? null : nodeLabels.get(node) ?? invalid(),
          notes: optionalString(relation.notes),
        };
      }),
    };
  });
  return {
    jobId: string(payload.job_id), sourceJobId: string(payload.source_job_id),
    checkpointId: string(payload.checkpoint_id), requirements,
  };
}
