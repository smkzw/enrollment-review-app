import { describe, expect, it } from "vitest";
import { ruleReviewAdvice, ruleReviewPresentations } from "./protocolRuleReview";
import type { RuleReviewEntry } from "../api/protocolRuleReviews";
import type { BindingView } from "../api/protocolVariables";
import type { IntegrityView, SourcesView } from "../api/protocolWorkbenchTypes";
import { formatPredicateStatement } from "../components/review/attributes";

const entry: RuleReviewEntry = { official_code: "IN-01", kind: "rule", label: "年龄要求", rule_content_hash: "a".repeat(64),
  source_refs: ["s"], issue_refs: ["c"], review: null };
const expression = { kind: "predicate", predicate: { predicate_id: "p", subject: "受试者", attribute: "年龄", comparator: "gte", value: 18, unit: "岁" } };
const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: "年龄要求", components: [
  { rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "年龄范围", expression, exception_expression: null },
] }], component_drafts: [{ draft_component_id: "cd", parent_official_code: "IN-01", source_refs: ["s"], source_excerpts: ["年龄要求"] }],
evidence_requirement_drafts: [{ draft_component_id: "cd", proposed_requirement: { variable_id: "age", description: "人口学记录", due_stage: "screening" } }] };
const bindings: BindingView = { job_id: "j", draft_revision_id: "d", variables: [{ variable_id: "age", label_zh: "年龄", value_type: "number", canonical_unit: "岁", unit_conversions: {}, plausible_range: null, aliases_zh: [], domain: "demographic" }],
  predicates: [{ component_id: "c", predicate_id: "p", official_code: "IN-01", label: "年龄", variable_id: "age", requirements: [] }] };
const integrity: IntegrityView = { jobId: "j", publishable: true, blockingCount: 0, reminderCount: 0, reviewCount: 0, summary: "", checks: [], issues: [] };
const sources: SourcesView = { jobId: "j", snapshotId: "s", selectedPhase: "phase_iii", selectedPhaseLabel: "III期", sourceMaterials: {}, sourceSpans: { s: { excerpt: "年龄要求", precision: "block" } } };

describe("审定重点投影", () => {
  it("书面判断方向只有对应原文明确要求时才推荐，不能仅凭旧判断标记", () => {
    const sourceClause = "研究者认为该情况影响评价";
    const raw = { ...content.proposed_rules[0]!.components[0]!, expression: { ...expression,
      predicate: { ...expression.predicate, requires_professional_judgment: true, source_clause: sourceClause } } };
    const sample = { proposed_rules: [{ ...content.proposed_rules[0]!, components: [raw] }],
      component_drafts: [{ proposed_component: raw, source_excerpts: [sourceClause] }] };
    const item = ruleReviewPresentations([entry], sample, bindings, integrity, sources)[0]!;
    expect(ruleReviewAdvice(item, sample)[0]?.options.find(option => option.recommended)?.label).toBe("按研究者书面判断核对");
    expect(ruleReviewAdvice(item, { ...sample, component_drafts: [] })[0]?.options.some(option => option.recommended)).toBe(false);
    expect(ruleReviewAdvice(item, sample)[0]?.options[1]?.manual).toBe(true);
  });
  it("局部任选不放宽整组；只有有源线索才推荐，未知关系保留人工调整", () => {
    const clause = "诊断明确，病史符合，至少一种相关检测阳性";
    const raw = { rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "联合要求", exception_expression: null, expression: { kind: "logical", operator: "any", children: [
      { kind: "predicate", predicate: { ...expression.predicate, source_clause: "诊断明确" } },
      { kind: "predicate", predicate: { ...expression.predicate, predicate_id: "p2", source_clause: "病史符合" } },
      { kind: "predicate", predicate: { ...expression.predicate, predicate_id: "p3", source_clause: "至少一种相关检测阳性", observation_policy: { mode: "any" } } },
    ] } };
    const sample = { proposed_rules: [{ ...content.proposed_rules[0], components: [raw] }],
      component_drafts: [{ proposed_component: raw, source_excerpts: [clause] }] };
    const item = ruleReviewPresentations([entry], sample, bindings, integrity, sources)[0]!;
    const advice = ruleReviewAdvice(item, sample)[0]!;
    expect(advice.options.find(value => value.recommended)?.operator).toBe("all");
    expect(advice.options.find(value => value.current)?.operator).toBe("any");
    expect(advice.analysis).toContain("项目内部可任选");
    const noSource = { ...sample, component_drafts: [] };
    expect(ruleReviewAdvice(item, noSource)[0]?.options.some(value => value.recommended)).toBe(false);
    const alternative = { ...sample, component_drafts: [{ proposed_component: raw, source_excerpts: [`符合下列任一条件：${clause}`] }] };
    expect(ruleReviewAdvice(item, alternative)[0]?.options.find(value => value.recommended)?.operator).toBe("any");
    expect(raw.expression.operator).toBe("any");
  });
  it("年龄按岁显示、病史时长按年显示，存在性条件不虚构阈值", () => {
    const predicate = { subject: "history", attribute: "duration", comparator: "gte", comparatorLabel: "大于等于", value: 2, unit: "year" };
    expect(formatPredicateStatement(predicate, "病史时长")).toBe("病史时长 大于等于 2 年");
    expect(formatPredicateStatement(predicate, "年龄")).toBe("年龄 大于等于 2 岁");
    expect(formatPredicateStatement({ ...predicate, comparator: "exists", value: null }, "研究者诊断判断"))
      .toBe("研究者诊断判断：需有相应记录");
    expect(formatPredicateStatement({ ...predicate, unit: "unitless", value: "阴性" }, "检验结果"))
      .not.toContain("unitless");
  });
  it("从真实条件与绑定给出结构清楚，不用原文重述冒充解析", () => {
    const item = ruleReviewPresentations([entry], content, bindings, integrity, sources)[0]!;
    expect(item.category).toBe("inclusion");
    expect(item.reasons).toEqual([]);
    expect(item.rule?.components[0]?.expression).toMatchObject({ kind: "predicate", value: 18 });
    expect(item.requirements).toEqual([{ description: "人口学记录", stage: "筛选" }]);
  });
  it("相同资料说明在不同节点分别保留，不能只按文字去重", () => {
    const sample = { ...content, evidence_requirement_drafts: [
      ...content.evidence_requirement_drafts,
      { draft_component_id: "cd", proposed_requirement: { variable_id: "age", description: "人口学记录", due_stage: "baseline" } },
    ] };
    expect(ruleReviewPresentations([entry], sample, bindings, integrity, sources)[0]?.requirements)
      .toEqual([{ description: "人口学记录", stage: "筛选" }, { description: "人口学记录", stage: "基线" }]);
  });
  it("缺来源、缺绑定、例外和书面判断显式降低把握度，不制造新规则", () => {
    const changed = { ...content, proposed_rules: content.proposed_rules.map(rule => ({ ...rule,
      components: rule.components.map(component => ({ ...component, exception_expression: {
        ...expression, predicate: { ...expression.predicate, requires_professional_judgment: true },
      } })),
    })) };
    const item = ruleReviewPresentations([entry], changed, null, integrity, { ...sources, sourceSpans: {} })[0]!;
    expect(item.reasons).toContain("部分原文依据尚不能完整展示，请核对来源。");
    expect(item.reasons).toContain("判断条件与病例数据项目尚未完整对应。");
    expect(item.reasons.some(value => value.includes("例外"))).toBe(true);
    expect(item.reasons.some(value => value.includes("研究者判断"))).toBe(true);
    expect(content.proposed_rules[0]!.components[0]!.exception_expression).toBeNull();
  });
  it("流程分类不改变操作身份，101条不会被截掉，只有流程项也可用", () => {
    const entries = Array.from({ length: 101 }, (_, i) => ({ ...entry, official_code: `procedure:${i}`, kind: "procedure" as const, label: i === 0 ? "生命体征" : i === 1 ? "症状评分" : "血常规" }));
    const projected = ruleReviewPresentations(entries, { proposed_rules: [] }, null, integrity, sources);
    expect(projected).toHaveLength(101);
    expect(projected.slice(0, 3).map(item => item.category)).toEqual(["exam", "score", "lab"]);
    expect(projected[100]?.entry.official_code).toBe("procedure:100");
    expect(ruleReviewPresentations([], {}, null, integrity, sources)).toEqual([]);
  });
  it("有正文依据的表格整体定位不是缺来源；真正的缺失仍提示", () => {
    const combined = { ...entry, source_refs: ["s", "table"] };
    const table = { excerpt: null, precision: "page_only", render_page: 2 };
    expect(ruleReviewPresentations([combined], content, bindings, integrity,
      { ...sources, sourceSpans: { ...sources.sourceSpans, table } })[0]?.reasons).toEqual([]);
    expect(ruleReviewPresentations([combined], content, bindings, integrity, sources)[0]?.reasons)
      .toContain("部分原文依据尚不能完整展示，请核对来源。");
  });
});
