/**
 * 方案解构草稿 → 前端 ViewModel 映射。
 */

import type { RuleComponentWire, RuleWire } from "../api/wire";
import { mapExpression } from "./mappers";
import { ruleKindLabel } from "./labels";
import type { RuleKind } from "./enums";
import type { RuleComponentId, RuleId } from "./ids";
import { toId } from "./ids";
import type {
  ProtocolDraftRuleView,
  ProtocolSourceLocatorView,
} from "./protocolViewModels";
import { protocolSourcePrecisionLabel } from "./labels";
import type { ProtocolSourcePrecision } from "./enums";

function displayRuleCode(code: string): string {
  return code.replace(/^REQ-/, "必做-");
}

function asRuleWire(rule: Record<string, unknown>): RuleWire {
  return rule as unknown as RuleWire;
}

function asComponentWire(component: Record<string, unknown>): RuleComponentWire {
  return component as unknown as RuleComponentWire;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function protocolSourceLabel(raw: Record<string, unknown>): string {
  const part = String(raw.document_part ?? "body");
  if (part === "header") return "页眉";
  if (part === "footer") return "页脚";
  if (raw.table_path !== null && raw.table_path !== undefined) return "方案表格";
  return "方案正文";
}

export function mapProtocolDraftRules(
  content: Record<string, unknown>,
): ProtocolDraftRuleView[] {
  const rules = (content.proposed_rules as ReadonlyArray<Record<string, unknown>>) ?? [];
  const componentDrafts =
    (content.component_drafts as ReadonlyArray<Record<string, unknown>>) ?? [];
  const draftRefByRule = new Map<string, string[]>();
  const draftsByRule = new Map<string, Record<string, unknown>[]>();
  const draftByComponentId = new Map<string, Record<string, unknown>>();
  for (const draft of componentDrafts) {
    const parentCode = String(draft.parent_official_code ?? "");
    const refs = stringList(draft.source_refs);
    draftsByRule.set(parentCode, [...(draftsByRule.get(parentCode) ?? []), draft]);
    draftRefByRule.set(parentCode, [
      ...new Set([...(draftRefByRule.get(parentCode) ?? []), ...refs]),
    ]);
    const proposedComponent = draft.proposed_component;
    if (
      proposedComponent !== null &&
      typeof proposedComponent === "object" &&
      !Array.isArray(proposedComponent)
    ) {
      const componentId = String(
        (proposedComponent as Record<string, unknown>).rule_component_id ?? "",
      );
      if (componentId.length > 0) {
        draftByComponentId.set(componentId, draft);
      }
    }
  }

  return rules.map((rawRule) => {
    const rule = asRuleWire(rawRule);
    return {
      ruleId: toId<RuleId>(rule.rule_id),
      officialCode: displayRuleCode(rule.official_code),
      kind: rule.kind as RuleKind,
      kindLabel: ruleKindLabel[rule.kind as RuleKind],
      sourceText: rule.source_text,
      sourceRefs: draftRefByRule.get(rule.official_code) ?? [],
      components: rule.components.map((component, componentIndex) => {
        const wire = asComponentWire(component as unknown as Record<string, unknown>);
        const ruleDrafts = draftsByRule.get(rule.official_code) ?? [];
        const draftEntry =
          draftByComponentId.get(wire.rule_component_id) ??
          ruleDrafts[componentIndex];
        const sourceRefs = stringList(draftEntry?.source_refs);
        const sourceExcerpts = stringList(draftEntry?.source_excerpts);
        return {
          componentId: toId<RuleComponentId>(wire.rule_component_id),
          parentRuleId: toId<RuleId>(wire.parent_rule_id),
          displayCode: displayRuleCode(wire.display_code),
          title: wire.title,
          expression: mapExpression(wire.expression),
          exceptionExpression:
            wire.exception_expression === null
              ? null
              : mapExpression(wire.exception_expression),
          sourceRefs,
          sourceExcerpts,
        };
      }),
    };
  });
}

export function mapProtocolSourceLocators(
  sourceSpans: Record<string, unknown>,
  selectedRefs: ReadonlyArray<string>,
): ProtocolSourceLocatorView[] {
  return selectedRefs.flatMap((ref) => {
    const raw = sourceSpans[ref] as Record<string, unknown> | undefined;
    if (raw === undefined) return [];
    const rawPrecision = String(raw.precision ?? "page_only");
    const precision: ProtocolSourcePrecision =
      rawPrecision === "bbox" ||
      rawPrecision === "text_range" ||
      rawPrecision === "page_excerpt" ||
      rawPrecision === "page_only" ||
      rawPrecision === "block"
        ? rawPrecision
        : "page_only";
    const pageNumber =
      typeof raw.render_page === "number" &&
      Number.isInteger(raw.render_page) &&
      raw.render_page > 0
        ? raw.render_page
        : typeof raw.page_number === "number" &&
            Number.isInteger(raw.page_number) &&
            raw.page_number > 0
          ? raw.page_number
          : undefined;
    return [
      {
        sourceSpanId: ref,
        sourceRef: protocolSourceLabel(raw),
        pageLabel: pageNumber !== undefined ? `第 ${pageNumber} 页` : null,
        excerpt: String(raw.excerpt ?? ""),
        precision,
        precisionLabel: protocolSourcePrecisionLabel[precision],
        degradationReason:
          raw.degradation_reason === null || raw.degradation_reason === undefined
            ? null
            : String(raw.degradation_reason),
      },
    ];
  });
}
