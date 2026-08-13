/**
 * 规则表达式视图：递归渲染判断条件树（合同 §5.1）。
 * - 逻辑词使用固定中文：全部满足 / 任一满足 / 不满足以下条件 / 例外条件。
 * - 父子层级通过缩进与连线保持，不把子项渲染成独立父级。
 * - 条件属性使用中文临床表达；需要研究者判断的谓词单独标注。
 */

import type { ExpressionNodeView, PredicateNodeView } from "../../domain/viewModels";
import { JudgmentIcon } from "../shell/icons";
import { UI_PHRASES } from "../../domain/labels";
import { formatPredicateStatement } from "./attributes";

function PredicateRow({ predicate }: { predicate: PredicateNodeView }) {
  const statement = formatPredicateStatement(predicate);
  return (
    <li className="expr-node expr-node--predicate">
      <span className="expr-node__condition">
        <span className="expr-node__attribute">{statement}</span>
      </span>
      {predicate.requiresProfessionalJudgment && (
        <span className="expr-node__judgment">
          <JudgmentIcon size={12} />
          需要研究者判断
        </span>
      )}
      {predicate.timeConstraint !== null && (
        <span className="expr-node__time">时间窗：{predicate.timeConstraint}</span>
      )}
    </li>
  );
}

function ExpressionViewInner({
  node,
  depth,
}: {
  node: ExpressionNodeView;
  depth: number;
}) {
  if (node.kind === "predicate") {
    return <PredicateRow predicate={node} />;
  }
  return (
    <li className="expr-node expr-node--logic">
      <span className="expr-node__operator">{node.operatorLabel}</span>
      <ul className="expr-children" style={{ "--expr-depth": depth } as React.CSSProperties}>
        {node.children.map((child, index) => (
          <ExpressionViewInner
            key={`${child.kind}-${index}`}
            node={child}
            depth={depth + 1}
          />
        ))}
      </ul>
    </li>
  );
}

/** 完整表达式（含例外条件）。 */
export function ExpressionView({
  expression,
  exception,
}: {
  expression: ExpressionNodeView;
  exception: ExpressionNodeView | null;
}) {
  return (
    <div className="expression-view">
      <ul className="expr-children">
        <ExpressionViewInner node={expression} depth={0} />
      </ul>
      {exception !== null && (
        <div className="expression-view__exception">
          <span className="expression-view__exception-label">例外条件</span>
          <p className="expression-view__exception-connective">
            {UI_PHRASES.exceptionConnective}
          </p>
          <ul className="expr-children">
            <ExpressionViewInner node={exception} depth={0} />
          </ul>
          <p className="expression-view__exception-note">
            {UI_PHRASES.exceptionEffectHint}
          </p>
        </div>
      )}
    </div>
  );
}
