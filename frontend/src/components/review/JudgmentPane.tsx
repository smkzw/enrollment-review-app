/**
 * 判断区（工作台第二区）：当前组件的判断、缺口、应备证据、行动与差异（合同 §5.2）。
 * - 判断状态与缺口原因分开显示（§1.2），阻断程度用中文徽标。
 * - 行动显示责任方、需补内容、可关闭证据与到期节点，并直达行动中心详情。
 * - 差异区显式区分“没有变化记录”空状态，不虚构审核运行。
 */

import { RouteLink } from "../../app/router";
import type {
  ActionView,
  ComponentDecisionView,
  RuleComponentView,
} from "../../domain/viewModels";
import { BlockingBadge } from "../shell/StatusBadge";
import { OpenIcon } from "../shell/icons";
import { attributeDisplayName } from "./attributes";
import { ExpressionView } from "./ExpressionView";

export interface JudgmentPaneProps {
  component: RuleComponentView | null;
  decision: ComponentDecisionView | null;
  /** 差异条目（按组件过滤后的前后判断对比） */
  diffItems: ReadonlyArray<{ priorLabel: string; currentLabel: string }>;
  /** 可滚动面板的键盘焦点入口（axe scrollable-region-focusable） */
  paneTabIndex?: number;
}

function ActionLine({ action }: { action: ActionView }) {
  return (
    <li className="judgment-action">
      <div className="judgment-action__head">
        <span className="judgment-action__code">{action.displayCode}</span>
        <span className="judgment-action__gap">{action.gapLabel}</span>
        <BlockingBadge level={action.blockingLevel} />
        <span className="judgment-action__state">{action.stateLabel}</span>
      </div>
      <p className="judgment-action__text">{action.requestedAction}</p>
      <p className="judgment-action__meta">
        责任方：{action.targetPartyLabel} · 到期节点：{action.dueStageLabel} ·
        可关闭证据：{action.acceptableEvidence}
      </p>
      <RouteLink
        to="/actions"
        params={{ action: action.actionId }}
        className="button button--quiet judgment-action__open"
        ariaLabel={`打开行动详情：${action.subjectCode} ${action.gapLabel}`}
      >
        <OpenIcon size={13} />
        行动详情
      </RouteLink>
    </li>
  );
}

export function JudgmentPane({
  component,
  decision,
  diffItems,
  paneTabIndex = 0,
}: JudgmentPaneProps) {
  if (component === null || decision === null) {
    return (
      <div className="workbench-pane workbench-pane--empty" tabIndex={paneTabIndex}>
        <p className="workbench-pane__empty-title">尚未选择规则子项</p>
        <p className="workbench-pane__empty-hint">
          在左侧规则区选择一项子规则后，这里会显示它的判断、缺口、行动与差异。
        </p>
      </div>
    );
  }

  return (
    <section
      className="workbench-pane judgment-pane"
      aria-label="判断与行动"
      tabIndex={paneTabIndex}
    >
      <header className="workbench-pane__head">
        <h2 className="workbench-pane__title">
          <span className="workbench-pane__code">{component.displayCode}</span>
          {component.title}
        </h2>
        <div className="judgment-pane__badges">
          <span className="status-badge status-badge--decision">
            {decision.decisionLabel}
          </span>
          <BlockingBadge level={decision.blockingLevel} />
        </div>
      </header>

      <div className="judgment-pane__section">
        <h3 className="judgment-pane__subtitle">判断条件（含父子逻辑）</h3>
        <ExpressionView
          expression={component.expression}
          exception={component.exceptionExpression}
        />
      </div>

      <div className="judgment-pane__section">
        <h3 className="judgment-pane__subtitle">缺口原因</h3>
        {decision.gapLabels.length === 0 ? (
          <p className="judgment-pane__muted">当前没有缺口。</p>
        ) : (
          <ul className="judgment-pane__gaps">
            {decision.gapLabels.map((label) => (
              <li key={label} className="count-chip">
                {label}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="judgment-pane__section">
        <h3 className="judgment-pane__subtitle">应备证据</h3>
        {component.evidenceRequirements.length === 0 ? (
          <p className="judgment-pane__muted">该规则子项没有额外的应备证据要求。</p>
        ) : (
          <ul className="judgment-pane__requirements">
            {component.evidenceRequirements.map((requirement) => {
              const displayName = attributeDisplayName(
                requirement.factType.split(".")[0],
                requirement.factType,
              );
              return (
                <li key={requirement.requirementId} className="judgment-requirement">
                  <span className="judgment-requirement__name">
                    {displayName ?? requirement.description}
                  </span>
                  <span className="judgment-requirement__stage">
                    到期节点：{requirement.dueStageLabel}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="judgment-pane__section">
        <h3 className="judgment-pane__subtitle">待办行动</h3>
        {component.actions.length === 0 ? (
          <p className="judgment-pane__muted">当前没有针对该子项的待办行动。</p>
        ) : (
          <ul className="judgment-pane__actions">
            {component.actions.map((action) => (
              <ActionLine key={action.actionId} action={action} />
            ))}
          </ul>
        )}
      </div>

      <div className="judgment-pane__section">
        <h3 className="judgment-pane__subtitle">前后差异</h3>
        {diffItems.length === 0 ? (
          <p className="judgment-pane__muted">
            当前没有需要比较的变化记录。若有人工确认使判断发生变化，这里会显示前后差异与新的整理结果。
          </p>
        ) : (
          <ul className="judgment-pane__diffs">
            {diffItems.map((item, index) => (
              <li key={index} className="judgment-diff">
                <span className="judgment-diff__prior">{item.priorLabel}</span>
                <span className="judgment-diff__arrow" aria-hidden="true">
                  →
                </span>
                <span className="judgment-diff__current">{item.currentLabel}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
