/**
 * 方案解构规则树：官方编号父级 + 子组件层级；不含审核判断状态。
 */

import { useMemo, useState, type KeyboardEvent } from "react";
import type { ProtocolDraftRuleView } from "../../domain/protocolViewModels";
import type { RuleComponentId } from "../../domain/ids";
import { ChevronDownIcon, ChevronRightIcon } from "../shell/icons";

export interface ProtocolDeconstructionRuleTreeProps {
  rules: ReadonlyArray<ProtocolDraftRuleView>;
  selectedComponentId: RuleComponentId | null;
  onSelectComponent: (componentId: RuleComponentId) => void;
}

export function ProtocolDeconstructionRuleTree({
  rules,
  selectedComponentId,
  onSelectComponent,
}: ProtocolDeconstructionRuleTreeProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(
    () => new Set(rules.map((rule) => rule.ruleId)),
  );

  const flatKeys = useMemo(() => {
    const keys: string[] = [];
    for (const rule of rules) {
      keys.push(`rule:${rule.ruleId}`);
      if (expanded.has(rule.ruleId)) {
        for (const component of rule.components) {
          keys.push(`component:${component.componentId}`);
        }
      }
    }
    return keys;
  }, [rules, expanded]);

  const toggleRule = (ruleId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
  };

  const onKeyDown = (event: KeyboardEvent, key: string, ruleId?: string) => {
    const index = flatKeys.indexOf(key);
    if (index === -1) return;
    if (event.key === "ArrowDown" && index < flatKeys.length - 1) {
      event.preventDefault();
      focusKey(flatKeys[index + 1]!);
    }
    if (event.key === "ArrowUp" && index > 0) {
      event.preventDefault();
      focusKey(flatKeys[index - 1]!);
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (key.startsWith("rule:") && ruleId !== undefined) toggleRule(ruleId);
      else if (key.startsWith("component:")) {
        onSelectComponent(key.replace("component:", "") as RuleComponentId);
      }
    }
  };

  const focusKey = (key: string) => {
    document.getElementById(`protocol-tree-${key}`)?.focus();
  };

  if (rules.length === 0) {
    return <p className="protocol-tree__empty">当前草稿没有可展示的规则条目。</p>;
  }

  return (
    <ul className="protocol-tree" role="tree" aria-label="方案规则树">
      {rules.map((rule) => {
        const isExpanded = expanded.has(rule.ruleId);
        return (
          <li key={rule.ruleId} className="protocol-tree__rule" role="treeitem" aria-expanded={isExpanded}>
            <button
              id={`protocol-tree-rule:${rule.ruleId}`}
              type="button"
              className="protocol-tree__parent"
              onClick={() => toggleRule(rule.ruleId)}
              onKeyDown={(event) => onKeyDown(event, `rule:${rule.ruleId}`, rule.ruleId)}
            >
              {isExpanded ? <ChevronDownIcon size={14} /> : <ChevronRightIcon size={14} />}
              <span className="protocol-tree__code">{rule.officialCode}</span>
              <span className="protocol-tree__kind">{rule.kindLabel}</span>
              <span className="protocol-tree__text">{rule.sourceText}</span>
            </button>
            {isExpanded && (
              <ul className="protocol-tree__children" role="group">
                {rule.components.map((component) => {
                  const selected = selectedComponentId === component.componentId;
                  return (
                    <li key={component.componentId} role="treeitem">
                      <button
                        id={`protocol-tree-component:${component.componentId}`}
                        type="button"
                        className={`protocol-tree__component${selected ? " protocol-tree__component--selected" : ""}`}
                        aria-selected={selected}
                        onClick={() => onSelectComponent(component.componentId)}
                        onKeyDown={(event) =>
                          onKeyDown(event, `component:${component.componentId}`)
                        }
                      >
                        <span className="protocol-tree__code">{component.displayCode}</span>
                        <span className="protocol-tree__text">{component.title}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
