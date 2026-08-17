/**
 * 重新解构规则栏（左侧当前正式版本 / 右侧新草稿）。
 * 复用既有草稿规则映射，展示父规则与子项编号/标题；不在此重新推导差异。
 */

import { useState } from "react";
import type { ProtocolDraftRuleView } from "../../domain/protocolViewModels";
import { ChevronDownIcon, ChevronRightIcon } from "../shell/icons";

interface ProtocolRedoRuleColumnProps {
  title: string;
  subtitle: string;
  rules: ReadonlyArray<ProtocolDraftRuleView>;
}

export function ProtocolRedoRuleColumn({
  title,
  subtitle,
  rules,
}: ProtocolRedoRuleColumnProps) {
  const [expandedRules, setExpandedRules] = useState<ReadonlySet<string>>(
    () => new Set(rules.map((rule) => rule.ruleId)),
  );

  const toggleRule = (ruleId: string) => {
    setExpandedRules((current) => {
      const next = new Set(current);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
  };

  return (
    <div className="protocol-redo-column">
      <header className="protocol-redo-column__head">
        <h2 className="protocol-redo-column__title">{title}</h2>
        <span className="protocol-redo-column__subtitle">
          {subtitle} · {rules.length} 条规则
        </span>
      </header>
      {rules.length === 0 ? (
        <p className="protocol-redo-column__empty">该侧没有可展示的规则条目。</p>
      ) : (
        <ul className="protocol-redo-column__list">
          {rules.map((rule) => {
            const expanded = expandedRules.has(rule.ruleId);
            return (
              <li key={rule.ruleId} className="protocol-redo-column__rule">
                <button
                  type="button"
                  className="protocol-redo-column__parent"
                  aria-expanded={expanded}
                  onClick={() => toggleRule(rule.ruleId)}
                >
                  {expanded ? <ChevronDownIcon size={14} /> : <ChevronRightIcon size={14} />}
                  <span className="protocol-redo-column__code">{rule.officialCode}</span>
                  <span className="protocol-redo-column__text">{rule.sourceText}</span>
                </button>
                {expanded && (
                  <ul className="protocol-redo-column__components">
                    {rule.components.map((component) => (
                      <li key={component.componentId} className="protocol-redo-column__component">
                        <span className="protocol-redo-column__code">{component.displayCode}</span>
                        <span className="protocol-redo-column__text">{component.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
