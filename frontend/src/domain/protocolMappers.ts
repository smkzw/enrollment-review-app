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
import { precisionLabel } from "./labels";
import type { LocatorPrecision } from "./enums";

function displayRuleCode(code: string): string {
  return code.replace(/^REQ-/, "必做-");
}

function asRuleWire(rule: Record<string, unknown>): RuleWire {
  return rule as unknown as RuleWire;
}

function asComponentWire(component: Record<string, unknown>): RuleComponentWire {
  return component as unknown as RuleComponentWire;
}

export function mapProtocolDraftRules(
  content: Record<string, unknown>,
): ProtocolDraftRuleView[] {
  const rules = (content.proposed_rules as ReadonlyArray<Record<string, unknown>>) ?? [];
  const componentDrafts =
    (content.component_drafts as ReadonlyArray<Record<string, unknown>>) ?? [];
  const draftRefByComponent = new Map<string, string[]>();
  for (const draft of componentDrafts) {
    const parentCode = String(draft.parent_official_code ?? "");
    const refs = (draft.source_refs as string[]) ?? [];
    draftRefByComponent.set(parentCode, refs);
  }

  return rules.map((rawRule) => {
    const rule = asRuleWire(rawRule);
    return {
      ruleId: toId<RuleId>(rule.rule_id),
      officialCode: displayRuleCode(rule.official_code),
      kind: rule.kind as RuleKind,
      kindLabel: ruleKindLabel[rule.kind as RuleKind],
      sourceText: rule.source_text,
      sourceRefs: draftRefByComponent.get(rule.official_code) ?? [],
      components: rule.components.map((component) => {
        const wire = asComponentWire(component as unknown as Record<string, unknown>);
        const draftEntry = componentDrafts.find(
          (entry) => entry.parent_official_code === rule.official_code,
        );
        const sourceRefs = (draftEntry?.source_refs as string[]) ?? [];
        const sourceExcerpts = (draftEntry?.source_excerpts as string[]) ?? [];
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
    const precision = String(raw.precision ?? "page_only");
    const pageNumber = raw.page_number as number | undefined;
    return [
      {
        sourceSpanId: ref,
        sourceRef: String(raw.source_ref ?? ref),
        pageLabel: pageNumber !== undefined ? `第 ${pageNumber} 页` : null,
        excerpt: String(raw.excerpt ?? ""),
        precision,
        precisionLabel:
          precisionLabel[precision as LocatorPrecision] ?? precision,
        degradationReason:
          raw.degradation_reason === null || raw.degradation_reason === undefined
            ? null
            : String(raw.degradation_reason),
      },
    ];
  });
}
