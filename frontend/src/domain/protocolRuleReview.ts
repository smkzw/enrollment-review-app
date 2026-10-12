import type { RuleReviewEntry } from "../api/protocolRuleReviews";
import type { BindingView } from "../api/protocolVariables";
import type { IntegrityIssueView, IntegrityView, SourcesView } from "../api/protocolWorkbenchTypes";
import type { ProtocolDraftRuleView } from "./protocolViewModels";
import { mapProtocolDraftRules, mapProtocolSourceLocators } from "./protocolMappers";

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
    } else if (!needed.length) reasons.push("流程表操作尚未对应到审核要求，请核对节点及必需内容。");
    return { entry, rule, category: entry.kind === "rule" && rule?.kind !== "required_procedure"
      ? rule?.kind === "inclusion" || entry.official_code.startsWith("IN-") ? "inclusion" : "exclusion"
      : procedureCategory,
      medicationRelated: domains.has("medication"), title: rule?.components[0]?.title ?? entry.label,
      reasons: [...new Set(reasons)], requirements: [...new Map(needed.map(item => [String(item.description), {
        description: String(item.description ?? ""), stage: stageLabels[String(item.due_stage)] ?? "节点尚未明确",
      }])).values()] };
  });
}
