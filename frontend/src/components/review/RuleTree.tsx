/**
 * 规则树（合同 §5.1）：官方编号父级 + 子组件缩进层级，逻辑关系保留在表达式视图中。
 * - 父级行显示官方编号、条件类别、原文与子项数量；点击展开/收起，折叠时保留父级状态。
 * - 子组件行选中后驱动判断区与证据区同步（选择由 URL component 参数持有）。
 * - 键盘：方向键在同层/父子间移动（roving tabindex），Enter 展开/收起或选中，Esc 不关闭页面。
 */

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type {
  RuleComponentView,
  RuleNodeView,
} from "../../domain/viewModels";
import type { RuleComponentId, RuleId } from "../../domain/ids";
import { ChevronDownIcon, ChevronRightIcon } from "../shell/icons";

interface FlatNode {
  key: string;
  ruleIndex: number;
  componentIndex: number | null;
  label: string;
}

function childSummary(rule: RuleNodeView): {
  label: string;
  tone: "barrier" | "conflict" | "attention" | "clear";
} {
  const decisions = rule.components
    .map((component) => component.decision)
    .filter((decision) => decision !== null);
  if (
    decisions.some(
      (decision) =>
        decision.decision === "exclusion_triggered" ||
        decision.decision === "inclusion_not_met" ||
        decision.decision === "requirement_not_met",
    )
  ) {
    return { label: "子项有明确障碍", tone: "barrier" };
  }
  if (
    decisions.some(
      (decision) =>
        decision.decision === "conflict" ||
        decision.gapTypes.includes("source_conflict") ||
        decision.gapTypes.includes("interpretation_conflict"),
    )
  ) {
    return { label: "子项有冲突", tone: "conflict" };
  }
  if (
    decisions.some(
      (decision) =>
        decision.blockingLevel !== "none" || decision.gapTypes.length > 0,
    )
  ) {
    return { label: "子项需处理", tone: "attention" };
  }
  return { label: "子项已核对", tone: "clear" };
}

export interface RuleTreeProps {
  rules: ReadonlyArray<RuleNodeView>;
  selectedComponentId: RuleComponentId | null;
  onSelectComponent: (componentId: RuleComponentId) => void;
}

export function RuleTree({
  rules,
  selectedComponentId,
  onSelectComponent,
}: RuleTreeProps) {
  const parentRuleOf = useMemo(() => {
    const map = new Map<RuleComponentId, RuleId>();
    for (const rule of rules) {
      for (const component of rule.components) {
        map.set(component.componentId, component.parentRuleId);
      }
    }
    return map;
  }, [rules]);

  /** 展开的父级：默认展开包含当前选中子项的父级 */
  const [expanded, setExpanded] = useState<ReadonlySet<RuleId>>(() => {
    const initial = new Set<RuleId>();
    if (selectedComponentId !== null) {
      const parent = parentRuleOf.get(selectedComponentId);
      if (parent !== undefined) initial.add(parent);
    }
    return initial;
  });

  // 外部导航选中子项时，自动展开其父级（§5.1：展开后当前子项不跳位）
  useEffect(() => {
    if (selectedComponentId === null) return;
    const parent = parentRuleOf.get(selectedComponentId);
    if (parent === undefined) return;
    setExpanded((current) => {
      if (current.has(parent)) return current;
      const next = new Set(current);
      next.add(parent);
      return next;
    });
  }, [selectedComponentId, parentRuleOf]);

  const flatNodes: FlatNode[] = useMemo(() => {
    const nodes: FlatNode[] = [];
    rules.forEach((rule, ruleIndex) => {
      nodes.push({
        key: `rule-${rule.ruleId}`,
        ruleIndex,
        componentIndex: null,
        label: `${rule.officialCode} ${rule.kindLabel}`,
      });
      if (expanded.has(rule.ruleId)) {
        rule.components.forEach((component, componentIndex) => {
          nodes.push({
            key: `component-${component.componentId}`,
            ruleIndex,
            componentIndex,
            label: `${component.displayCode} ${component.title}`,
          });
        });
      }
    });
    return nodes;
  }, [rules, expanded]);

  const nodeRefs = useRef(new Map<string, HTMLButtonElement>());
  const focusedKeyRef = useRef<string | null>(null);

  const setRef = (key: string, element: HTMLButtonElement | null) => {
    if (element === null) {
      nodeRefs.current.delete(key);
    } else {
      nodeRefs.current.set(key, element);
    }
  };

  const moveFocus = (fromKey: string, delta: number) => {
    const index = flatNodes.findIndex((node) => node.key === fromKey);
    if (index === -1) return;
    const target = flatNodes[index + delta];
    if (target === undefined) return;
    nodeRefs.current.get(target.key)?.focus();
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    node: FlatNode,
  ) => {
    const rule = rules[node.ruleIndex];
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        moveFocus(node.key, 1);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveFocus(node.key, -1);
        break;
      case "ArrowRight": {
        event.preventDefault();
        if (node.componentIndex === null && !expanded.has(rule.ruleId)) {
          setExpanded((current) => new Set(current).add(rule.ruleId));
        }
        break;
      }
      case "ArrowLeft": {
        event.preventDefault();
        if (node.componentIndex === null) {
          if (expanded.has(rule.ruleId)) {
            setExpanded((current) => {
              const next = new Set(current);
              next.delete(rule.ruleId);
              return next;
            });
          }
        } else {
          // 子项 → 回到父级
          nodeRefs.current.get(`rule-${rule.ruleId}`)?.focus();
        }
        break;
      }
      default:
        break;
    }
  };

  const ruleFor = (node: FlatNode) => rules[node.ruleIndex];
  const componentFor = (node: FlatNode): RuleComponentView | null =>
    node.componentIndex === null
      ? null
      : rules[node.ruleIndex].components[node.componentIndex];

  return (
    <div
      className="rule-tree"
      onKeyDown={(event) => {
        if (focusedKeyRef.current === null) return;
        const node = flatNodes.find(
          (candidate) => candidate.key === focusedKeyRef.current,
        );
        if (node !== undefined) handleKeyDown(event, node);
      }}
    >
      {flatNodes.map((node) => {
        const rule = ruleFor(node);
        const component = componentFor(node);
        if (component === null) {
          const isExpanded = expanded.has(rule.ruleId);
          const childCount = rule.components.length;
          const summary = childSummary(rule);
          return (
            <div key={node.key} className="rule-tree__item rule-tree__item--rule">
              <button
                ref={(element) => setRef(node.key, element)}
                type="button"
                className="rule-tree__rule"
                onFocus={() => {
                  focusedKeyRef.current = node.key;
                }}
                onClick={() => {
                  setExpanded((current) => {
                    const next = new Set(current);
                    if (next.has(rule.ruleId)) {
                      next.delete(rule.ruleId);
                    } else {
                      next.add(rule.ruleId);
                    }
                    return next;
                  });
                }}
                aria-expanded={isExpanded}
                aria-label={`${rule.officialCode} ${rule.kindLabel}，共 ${childCount} 个子项，${summary.label}，${isExpanded ? "已展开" : "已折叠"}`}
              >
                <span className="rule-tree__chevron" aria-hidden="true">
                  {isExpanded ? (
                    <ChevronDownIcon size={13} />
                  ) : (
                    <ChevronRightIcon size={13} />
                  )}
                </span>
                <span className="rule-tree__code">{rule.officialCode}</span>
                <span className="rule-tree__kind">{rule.kindLabel}</span>
                <span
                  className={`rule-tree__summary rule-tree__summary--${summary.tone}`}
                >
                  {summary.label}
                </span>
                <span className="rule-tree__count">{childCount} 项</span>
              </button>
              {isExpanded && (
                <p className="rule-tree__source">{rule.sourceText}</p>
              )}
            </div>
          );
        }
        const decision = component.decision;
        const isSelected = component.componentId === selectedComponentId;
        const gapCount = decision === null ? 0 : decision.gapTypes.length;
        return (
          <div
            key={node.key}
            className="rule-tree__item rule-tree__item--component"
          >
            <button
              ref={(element) => setRef(node.key, element)}
              type="button"
              className={`rule-tree__component${isSelected ? " rule-tree__component--selected" : ""}`}
              onFocus={() => {
                focusedKeyRef.current = node.key;
              }}
              onClick={() => onSelectComponent(component.componentId)}
              aria-current={isSelected ? "true" : undefined}
              aria-label={`${component.displayCode} ${component.title}${decision !== null ? `，当前判断：${decision.decisionLabel}` : ""}`}
            >
              <span className="rule-tree__marker" aria-hidden="true" />
              <span className="rule-tree__code">{component.displayCode}</span>
              <span className="rule-tree__title">{component.title}</span>
              {decision !== null && (
                <span className="rule-tree__decision">
                  {decision.decisionLabel}
                </span>
              )}
              {gapCount > 0 && (
                <span className="rule-tree__gaps">{gapCount} 项缺口</span>
              )}
            </button>
          </div>
        );
      })}
      {flatNodes.length === 0 && (
        <p className="rule-tree__empty">当前没有可显示的规则。</p>
      )}
    </div>
  );
}
