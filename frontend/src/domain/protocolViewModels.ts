/**
 * 方案解构工作台 ViewModel。
 */

import type { RuleKind } from "./enums";
import type { RuleComponentId, RuleId } from "./ids";
import type { ExpressionNodeView } from "./viewModels";

export interface ProtocolDraftComponentView {
  componentId: RuleComponentId;
  parentRuleId: RuleId;
  displayCode: string;
  title: string;
  expression: ExpressionNodeView;
  exceptionExpression: ExpressionNodeView | null;
  sourceRefs: string[];
  sourceExcerpts: string[];
}

export interface ProtocolDraftRuleView {
  ruleId: RuleId;
  officialCode: string;
  kind: RuleKind;
  kindLabel: string;
  sourceText: string;
  sourceRefs: string[];
  components: ProtocolDraftComponentView[];
}

export interface ProtocolSourceLocatorView {
  sourceSpanId: string;
  sourceRef: string;
  pageLabel: string | null;
  excerpt: string;
  precision: string;
  precisionLabel: string;
  degradationReason: string | null;
}
