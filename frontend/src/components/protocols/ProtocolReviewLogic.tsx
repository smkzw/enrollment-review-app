import type { BindingView } from "../../api/protocolVariables";
import type { RuleReviewPresentation } from "../../domain/protocolRuleReview";
import { reviewObjects } from "../../domain/protocolRuleReview";
import { ExpressionView } from "../review/ExpressionView";
import { GitBranch, CalendarDays } from "lucide-react";

export function ProtocolReviewLogic({ item, content, bindings }: {
  item: RuleReviewPresentation; content: Record<string, unknown>; bindings: BindingView | null;
}) {
  const raw = reviewObjects(content.proposed_rules).find(rule => rule.official_code === item.entry.official_code);
  return <section className="protocol-review-logic" aria-label="逻辑解析">
    <h4>逻辑解析</h4>
    {item.rule ? <>
      {item.rule.components.map(component => <details className="protocol-review-logic__component" key={component.componentId}
        open={item.rule?.components.length === 1}>
        <summary><strong>{component.displayCode}</strong><span>{component.title}</span>
          <small><GitBranch size={13} aria-hidden="true" />{component.expression.kind === "logic" ? component.expression.operatorLabel : "单项条件"}</small>
          {component.exceptionExpression && <small>含例外</small>}</summary>
        <ExpressionView expression={component.expression} exception={component.exceptionExpression}
          predicateLabel={predicate => {
            const binding = bindings?.predicates.find(value => value.component_id === component.componentId && value.predicate_id === predicate.predicateId);
            // A variable name must not erase the condition's scope or relationship.
            return /[\u3400-\u9fff]/.test(predicate.attribute) ? predicate.attribute
              : bindings?.variables.find(value => value.variable_id === binding?.variable_id)?.label_zh;
          }} />
        {reviewObjects(raw?.components).filter(value => value.rule_component_id === component.componentId).map(value => {
          const notes: string[] = [];
          function inspect(expression: unknown) {
            const node = reviewObjects([expression])[0];
            if (!node) return;
            const predicate = reviewObjects([node.predicate])[0];
            if (typeof predicate?.applicable_population === "string") notes.push(`适用人群：${predicate.applicable_population}`);
            const computation = reviewObjects([predicate?.source_computation])[0];
            if (computation) {
              const labels: Record<string, string> = { mean: "平均值", sum: "合计", minimum: "最小值", maximum: "最大值", count: "次数", ratio: "比值" };
              notes.push(`计算方式：${labels[String(computation.operator)] ?? "计算方式待核清"}`);
              reviewObjects(computation.input_refs).forEach(ref => { if (typeof ref.quote === "string") notes.push(`计算输入原文：${ref.quote}`); });
              notes.push(`缺失处理：${computation.missing_policy === "exclude" ? "排除缺失项" : computation.missing_policy === "impute" ? "按方案补值" : "原文未明确或尚待核清"}`);
            }
            const occurrence = reviewObjects([predicate?.occurrence_window])[0];
            const quantity = reviewObjects([occurrence?.duration])[0];
            const units: Record<string, string> = { day: "天", week: "周", month: "个月", year: "年" };
            if (quantity) notes.push(`发生频次：每${quantity.value}${units[String(quantity.unit)] ?? "（时间单位待核清）"}${occurrence?.minimum_count == null ? "，次数未明确" : `至少${occurrence.minimum_count}次`}`);
            if (predicate?.prospective_period || predicate?.prospective_window) notes.push("含后续持续要求，请结合原文核对覆盖期间。");
            reviewObjects(node.children).forEach(inspect);
          }
          inspect(value.expression); inspect(value.exception_expression);
          return notes.length ? <ul key={component.componentId}>{[...new Set(notes)].map(note => <li key={note}>{note}</li>)}</ul> : null;
        })}
      </details>)}
      {item.rule.restrictedComponents.map(component => <p key={component.componentId}>{component.displayCode} · {component.title}：{component.limitationKind === "consumer_unavailable" ? "审核方法待补齐" : "方案含义待核清"}。{component.unresolvedDimensions.join("；")}</p>)}
    </> : item.entry.kind === "procedure" ? <p>核对操作是否完成、是否在所列节点内；必需结果仅按本次审定明确选择的项目核查，不等同于检验结果正常。</p>
      : <p>尚无可展示的判断条件，不能将原文标题当作逻辑解析。</p>}
    {!!item.requirements.length && <details className="protocol-review-requirements"><summary><CalendarDays size={15} aria-hidden="true" /> 节点与所需资料（{item.requirements.length}）</summary>
      <dl>{item.requirements.map(value => <div key={`${value.stage}:${value.description}`}><dt>{value.stage}</dt><dd>{value.description}</dd></div>)}</dl></details>}
  </section>;
}
