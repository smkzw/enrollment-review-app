import type { RuleReviewEntry } from "../api/protocolRuleReviews";
import type { BindingView } from "../api/protocolVariables";
import type { IntegrityIssueView, IntegrityView, SourcesView } from "../api/protocolWorkbenchTypes";
import type { ProtocolDraftRuleView } from "./protocolViewModels";
import { mapProtocolDraftRules, mapProtocolSourceLocators } from "./protocolMappers";
import { getEditableProtocolComponents } from "./protocolManualEdit";

export interface RuleReviewAdvice {
  componentId: string | null;
  title: string;
  analysis: string;
  options: { label: string; explanation: string; operator?: "all" | "any"; recommended?: boolean; current?: boolean; manual?: boolean; keep?: boolean; defer?: boolean }[];
}

/** Suggestions are review directions, never edits or model-calibrated probabilities. */
export function ruleReviewAdvice(item: RuleReviewPresentation, content: Record<string, unknown>): RuleReviewAdvice[] {
  if (item.entry.kind === "medication" || item.entry.kind === "scope") return [];
  const components = getEditableProtocolComponents(content).filter(value =>
    item.rule?.components.some(component => component.componentId === value.componentId));
  const rule = reviewObjects(content.proposed_rules).find(value => value.official_code === item.entry.official_code);
  const result: RuleReviewAdvice[] = [];
  for (const component of components) {
    if (component.mainOperator !== "any") continue;
    const raw = reviewObjects(rule?.components).find(value => value.rule_component_id === component.componentId);
    const root = reviewObjects([raw?.expression])[0];
    const children = reviewObjects(root?.children);
    if (children.length < 2) continue;
    const predicates = children.map(child => reviewObjects([child.predicate])[0]);
    const clauses = predicates.map(predicate => typeof predicate?.source_clause === "string" ? predicate.source_clause : "");
    const source = component.sourceExcerpts.join("\n");
    const wholeChoiceCue = /(?:以下|下列)(?:任一|至少一项|条件之一)/.test(source);
    const localChoice = !wholeChoiceCue && children.every(child => child.kind === "predicate") && predicates.some(predicate =>
      reviewObjects([predicate?.observation_policy])[0]?.mode === "any")
      && clauses.every(clause => clause.length > 0 && source.includes(clause)) && new Set(clauses).size === clauses.length;
    const explicitWholeChoice = wholeChoiceCue;
    result.push({ componentId: component.componentId, title: `${component.displayCode}：条件怎样组合`,
      analysis: localChoice
        ? "原文中有只针对一个检测或观察项目的“至少一种”选择。这说明该项目内部可任选，不足以证明诊断、病史或其他并列要求也可任选。建议把外层独立要求与项目内部选择分开核对。"
        : explicitWholeChoice ? "原文明确列出可选条件，但仍需核对这段选择究竟涵盖哪些子项；不能把例外或另一层的条件一起放宽。"
          : "当前采用“任一条件成立”的组合。改成“全部成立”会缩小这个子项命中的范围；混合关系应逐层分组。下列选项用于比较调整影响，不表示当前解释有误；没有充分原文依据时不推荐改选。",
      options: [
        { label: "各项必须同时满足", explanation: `只有所有独立条件都成立才${item.rule?.kind === "exclusion" ? "触发这一排除子项" : "满足这一入选子项"}；项目内部的任选关系保留。`, operator: "all", recommended: localChoice },
        { label: "任一项满足即可", explanation: `任一独立条件成立即可${item.rule?.kind === "exclusion" ? "触发这一排除子项" : "满足这一入选子项"}，不要求其他条件同时成立。`, operator: "any", recommended: explicitWholeChoice, current: true },
        { label: "分组或手动调整", manual: true, explanation: "部分条件须同时成立、部分可任选时，逐层指定关系，不把整组统一改成全部或任一。" },
      ],
    });
  }
  if (!result.length) {
    const component = components.find(value => value.predicates.some(predicate => predicate.requiresProfessionalJudgment));
    if (component) {
      const raw = reviewObjects(rule?.components).find(value => value.rule_component_id === component.componentId);
      const clauses: string[] = [];
      function collect(value: unknown): void {
        const node = reviewObjects([value])[0];
        const predicate = reviewObjects([node?.predicate])[0];
        if (predicate?.requires_professional_judgment && typeof predicate.source_clause === "string") clauses.push(predicate.source_clause);
        reviewObjects(node?.children).forEach(collect);
      }
      collect(raw?.expression); collect(raw?.exception_expression);
      const written = clauses.length > 0 && clauses.every(clause => component.sourceExcerpts.some(excerpt => excerpt.includes(clause))
        && /研究者(?:判断|评估|认为)/.test(clause));
      result.push({ componentId: component.componentId, title: "判断依据由谁提供",
        analysis: written ? "对应原文明确要求研究者判断，建议保留该要求；普通检验异常标记不能代替研究者意见。"
          : "当前解析要求研究者判断，但对应原文并未明确写出所有这些判断都必须由研究者另行书面提供。应区分已有诊断或检查记录是否足够，以及确实需要研究者裁量的内容；没有充分依据时不强推其中一种。",
        options: [
          { label: "按研究者书面判断核对", recommended: written, manual: true,
            explanation: "原文要求研究者判断时保留；缺少记录在病例审核中说明，不能把单纯异常标记当书面判断。" },
          { label: "按已有诊断或客观结果核对", manual: true,
            explanation: "仅在原文允许且记录能证明对应条件时选择；需同时核对条件的数据对应与资料要求，不能只取消判断标记。" },
          { label: "暂保留待审，明确依据后再定", defer: true, explanation: "来源或医学含义仍不足时不作无依据的推荐，也不默认为已批准。" },
        ],
      });
    }
  }
  if (item.reasons.length && !result.length) result.push({ componentId: components[0]?.componentId ?? null,
    title: "这一项为什么需要核对", analysis: item.reasons.join("\n"), options: [
      { label: "核对原文后保留现有解释", keep: true, explanation: "提示可能来自复杂条件或书面判断要求，不一定是解析错误；原文支持时可以保持现状。" },
      { label: "手动调整当前条款", manual: true, explanation: "可调整条件、数值、时间窗及所需资料；修改后需重新审定，不自动发布。" },
      { label: "暂不审定，补充依据", defer: true, explanation: "来源或关系仍不清时保留待审；不会把未核内容当作已批准。" },
    ] });
  return result;
}

export const reviewCategories = {
  inclusion: "入选标准", exclusion: "排除标准", medication: "合并用药与治疗要求",
  lab: "必做检验", exam: "必做检查", score: "评分与评估", other: "其他必做操作",
} as const;
export type ReviewCategory = keyof typeof reviewCategories;
export interface RuleReviewPresentation {
  entry: RuleReviewEntry;
  category: ReviewCategory;
  medicationRelated: boolean;
  title: string;
  reasons: string[];
  rule: ProtocolDraftRuleView | null;
  requirements: { description: string; stage: string }[];
}

export function reviewObjects(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> =>
    item !== null && typeof item === "object" && !Array.isArray(item)) : [];
}
const stageLabels: Record<string, string> = {
  pre_screening: "预筛", screening: "筛选", run_in: "导入／洗脱", baseline: "基线",
};
export function ruleReviewIssueText(issue: IntegrityIssueView): string {
  if (issue.issueCode === "PROCEDURE_REVIEW_STAGE_MISMATCH") return "本项在流程表中的期别与当前审核节点标注不同，请核对对应关系。";
  if (issue.issueCode === "PROCEDURE_VISIT_INSTANCE_MISMATCH") return "本项在流程表中的访视与当前审核节点不同，请核对对应关系。";
  return issue.affectedRefs.filter(ref => !/^(IN|EX|REQ)-\d{2}$/.test(ref))
    .sort((a, b) => b.length - a.length).reduce((text, ref) => text.split(ref).join("本项"), issue.problem);
}
export function ruleReviewPresentations(entries: RuleReviewEntry[], content: Record<string, unknown>,
  bindings: BindingView | null, integrity: IntegrityView, sources: SourcesView): RuleReviewPresentation[] {
  const rules = mapProtocolDraftRules(content);
  const drafts = reviewObjects(content.component_drafts);
  const requirements = reviewObjects(content.evidence_requirement_drafts);
  return entries.map(entry => {
    const rule = rules.find(item => item.officialCode === entry.official_code) ?? null;
    const ids = new Set(drafts.filter(item => item.parent_official_code === entry.official_code)
      .map(item => item.draft_component_id));
    const needed = requirements.filter(item => entry.kind === "procedure"
      ? item.procedure_catalog_item_id === entry.official_code : ids.has(item.draft_component_id))
      .flatMap(item => reviewObjects([item.proposed_requirement]));
    const domains = new Set(needed.flatMap(item => bindings?.variables.filter(v => v.variable_id === item.variable_id)
      .map(v => v.domain) ?? []));
    // These are display groups only, never rule eligibility or source adoption decisions.
    const procedureCategory: ReviewCategory = /评分|量表|评估/.test(entry.label) || domains.has("score") ? "score"
      : /血常规|尿常规|生化|检测|抗体|检验|血清|凝血/.test(entry.label) || domains.has("lab") ? "lab"
      : /用药|治疗|药物/.test(entry.label) || domains.has("medication") ? "medication"
      : /检查|心电|胸片|体格|生命体征|肺功能|影像|内镜|超声/.test(entry.label) || domains.has("vital") ? "exam" : "other";
    const reasons = integrity.issues.filter(issue => issue.affectedRefs.some(ref => entry.issue_refs.includes(ref)))
      .map(ruleReviewIssueText);
    const locators = mapProtocolSourceLocators(sources.sourceSpans, entry.source_refs);
    if (!entry.source_refs.length || locators.length !== entry.source_refs.length || !locators.some(item => item.excerpt)
      || locators.some(item => !item.excerpt && item.precision !== "page_only"))
      reasons.push("部分原文依据尚不能完整展示，请核对来源。");
    if (locators.some(item => item.degradationReason)) reasons.push("部分原文定位范围有限，请对照原文。");
    if (entry.kind === "rule") {
      if (!rule || !rule.components.length) reasons.push("尚无可展示的判断条件，不能仅凭原文标题确认解析。");
      if (rule?.restrictedComponents.length) reasons.push("存在尚未核清或暂不能自动审核的子项。");
      if (rule?.components.some(item => item.exceptionExpression)) reasons.push("含例外条件，请重点核对例外与主条件的关系。");
      const predicates = bindings?.predicates.filter(item => item.official_code === entry.official_code);
      if (!predicates?.length || predicates.some(item => !item.variable_id)) reasons.push("判断条件与病例数据项目尚未完整对应。");
      const raw = reviewObjects(content.proposed_rules).find(item => item.official_code === entry.official_code);
      function inspect(value: unknown): void {
        const node = reviewObjects([value])[0];
        if (!node) return;
        const predicate = reviewObjects([node.predicate])[0];
        if (predicate?.requires_professional_judgment) reasons.push("含研究者判断，请核对需要书面判断的具体事项。");
        if (predicate?.applicable_population) reasons.push("含适用人群限制，请核对适用范围。");
        if (predicate?.source_computation) reasons.push("含多次结果的计算或选择规则，请核对输入与缺失处理。");
        if (node.operator === "not") reasons.push("含否定条件，请核对排除与否定方向。");
        if (node.operator === "any") reasons.push("含“任一满足”的组合，请对照原文核对哪些条件可任选、哪些必须同时满足。");
        reviewObjects(node.children).forEach(inspect);
      }
      reviewObjects(raw?.components).forEach(item => { inspect(item.expression); inspect(item.exception_expression); });
    } else if (entry.kind === "procedure" && !needed.length) reasons.push("流程表操作尚未对应到审核要求，请核对节点及必需内容。");
    if (entry.kind === "medication") {
      const supplement = reviewObjects([content.scope_supplement])[0];
      const medication = reviewObjects(supplement?.medications).find(value => value.item_id === entry.official_code);
      if (medication?.exception_excerpt) reasons.push("含用药例外，请核对适用对象及期间。");
      if (typeof medication?.unresolved_reason === "string") reasons.push(medication.unresolved_reason);
    }
    return { entry, rule, category: entry.kind === "rule" && rule?.kind !== "required_procedure"
      ? rule?.kind === "inclusion" || entry.official_code.startsWith("IN-") ? "inclusion" : "exclusion"
      : entry.kind === "medication" || entry.kind === "scope" ? "medication" : procedureCategory,
      medicationRelated: entry.kind === "medication" || entry.kind === "scope" || domains.has("medication"), title: rule?.components[0]?.title ?? entry.label,
      reasons: [...new Set(reasons)], requirements: [...new Map(needed.map(item => [JSON.stringify([item.due_stage, item.description]), {
        description: String(item.description ?? ""), stage: stageLabels[String(item.due_stage)] ?? "节点尚未明确",
      }])).values()] };
  });
}
