/**
 * 草稿编辑区：展示选中子项的逻辑表达式、原文摘要与完整性提示。
 */

import { ExpressionView } from "../review/ExpressionView";
import type { ProtocolDraftComponentView } from "../../domain/protocolViewModels";
import type { IntegrityIssueView } from "../../api/protocolWorkbenchTypes";
import { EmptyState } from "../shell/Feedback";

interface ProtocolDraftEditPaneProps {
  component: ProtocolDraftComponentView | null;
  revisionLabel: string;
  issues: ReadonlyArray<IntegrityIssueView>;
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
        hint="宽屏下三列联动；窄屏请切换到「编辑」标签。"
      />
    );
  }

  const relatedIssues = issues.filter((issue) =>
    issue.affectedRefs.some((ref) => component.displayCode.startsWith(ref) || ref === component.displayCode.split("-")[0]),
  );

  return (
    <div className="protocol-edit-pane">
      <header className="protocol-edit-pane__head">
        <h3 className="protocol-edit-pane__title">
          <span className="protocol-edit-pane__code">{component.displayCode}</span>
          {component.title}
        </h3>
        <p className="protocol-edit-pane__meta">{revisionLabel} · 手工修订入口将在后续步骤开放</p>
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

      <section className="protocol-edit-pane__section" aria-labelledby="protocol-edit-logic">
        <h4 id="protocol-edit-logic" className="protocol-edit-pane__section-title">
          逻辑结构
        </h4>
        <ExpressionView
          expression={component.expression}
          exception={component.exceptionExpression}
        />
      </section>

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
        草稿由智能体辅助生成，关键排除条件需医学经理终审；本页不声称 OCR/LLM 已全部完成。
      </p>
    </div>
  );
}
