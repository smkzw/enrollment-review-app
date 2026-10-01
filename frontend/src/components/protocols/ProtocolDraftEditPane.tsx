/**
 * 草稿编辑区：展示选中子项的逻辑表达式、原文摘要与完整性提示。
 */

import { ExpressionView } from "../review/ExpressionView";
import type { ProtocolDraftItemView } from "../../domain/protocolViewModels";
import type { IntegrityIssueView } from "../../api/protocolWorkbenchTypes";
import { EmptyState } from "../shell/Feedback";
import type { ExpressionNodeView } from "../../domain/viewModels";

interface ProtocolDraftEditPaneProps {
  component: ProtocolDraftItemView | null;
  revisionLabel: string;
  issues: ReadonlyArray<IntegrityIssueView>;
}

function collectPredicateIds(expression: ExpressionNodeView | null): Set<string> {
  if (expression === null) return new Set();
  if (expression.kind === "predicate") return new Set([expression.predicateId]);

  const predicateIds = new Set<string>();
  expression.children.forEach((child) => {
    collectPredicateIds(child).forEach((predicateId) => predicateIds.add(predicateId));
  });
  return predicateIds;
}

export function isIntegrityIssueRelatedToComponent(
  issue: IntegrityIssueView,
  component: ProtocolDraftItemView,
): boolean {
  const componentRefs = new Set<string>([
    component.componentId,
    component.parentRuleId,
    component.displayCode,
    component.displayCode.split("-")[0],
    ...component.sourceRefs,
    ...("expression" in component ? collectPredicateIds(component.expression) : []),
    ...("exceptionExpression" in component ? collectPredicateIds(component.exceptionExpression) : []),
  ]);

  return issue.affectedRefs.some((ref) =>
    componentRefs.has(ref) || component.displayCode.startsWith(ref),
  );
}

export function ProtocolDraftEditPane({
  component,
  revisionLabel,
  issues,
}: ProtocolDraftEditPaneProps) {
  if (component === null) {
    return (
      <EmptyState
        message="请选择左侧规则树中的子项"
        hint="选择后将同步显示逻辑结构、完整性问题和方案原文定位。"
      />
    );
  }

  const relatedIssues = issues.filter((issue) =>
    isIntegrityIssueRelatedToComponent(issue, component),
  );

  return (
    <div className="protocol-edit-pane">
      <header className="protocol-edit-pane__head">
        <h3 className="protocol-edit-pane__title">
          <span className="protocol-edit-pane__code">{component.displayCode}</span>
          {component.title}
        </h3>
        <p className="protocol-edit-pane__meta">
          {revisionLabel} · {"expression" in component
            ? "请逐项核对原文、逻辑和资料要求"
            : "请核对尚未厘清的方案原文含义"}
        </p>
      </header>

      <section className="protocol-edit-pane__section" aria-labelledby="protocol-edit-source">
        <h4 id="protocol-edit-source" className="protocol-edit-pane__section-title">
          方案原文摘要
        </h4>
        {component.sourceExcerpts.length === 0 ? (
          <p className="protocol-edit-pane__muted">暂无绑定的原文摘录。</p>
        ) : (
          <ul className="protocol-edit-pane__excerpts">
            {component.sourceExcerpts.map((excerpt, index) => (
              <li key={index}>{excerpt}</li>
            ))}
          </ul>
        )}
      </section>

      {"expression" in component ? (
        <section className="protocol-edit-pane__section" aria-labelledby="protocol-edit-logic">
          <h4 id="protocol-edit-logic" className="protocol-edit-pane__section-title">逻辑结构</h4>
          <ExpressionView expression={component.expression} exception={component.exceptionExpression} />
        </section>
      ) : (
        <section className="protocol-edit-pane__section" aria-labelledby="protocol-edit-unresolved">
          <h4 id="protocol-edit-unresolved" className="protocol-edit-pane__section-title">方案含义待核清</h4>
          <p className="protocol-edit-pane__muted">
            {component.limitationKind === "consumer_unavailable"
              ? "这项要求已有原文依据，但当前审核方式还不能可靠判断。"
              : "这项要求已有原文依据，适用含义尚未核清。"}
            本项不能据此判为符合或不符合。
          </p>
          <ul className="protocol-edit-pane__excerpts">
            {component.unresolvedDimensions.map((dimension, index) => <li key={index}>{dimension}</li>)}
          </ul>
        </section>
      )}

      {relatedIssues.length > 0 && (
        <section className="protocol-edit-pane__section" aria-labelledby="protocol-edit-issues">
          <h4 id="protocol-edit-issues" className="protocol-edit-pane__section-title">
            完整性问题
          </h4>
          <ul className="protocol-issue-list">
            {relatedIssues.map((issue) => (
              <li key={issue.issueCode} className={`protocol-issue protocol-issue--${issue.level}`}>
                <strong>{issue.problem}</strong>
                <p>{issue.impact}</p>
                <p className="protocol-issue__action">下一步：{issue.nextAction}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="protocol-edit-pane__note" role="note">
        发现原文理解、逻辑关系或资料要求不准确时，请先记录具体条目；草稿修订时可据此逐项修改并再次检查。
      </p>
    </div>
  );
}
