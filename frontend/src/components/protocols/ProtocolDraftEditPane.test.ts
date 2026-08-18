import { describe, expect, it } from "vitest";

import type { IntegrityIssueView } from "../../api/protocolWorkbenchTypes";
import { toId, type RuleComponentId, type RuleId } from "../../domain/ids";
import type { ProtocolDraftComponentView } from "../../domain/protocolViewModels";
import { isIntegrityIssueRelatedToComponent } from "./ProtocolDraftEditPane";

const component: ProtocolDraftComponentView = {
  componentId: toId<RuleComponentId>("component-ex-07w"),
  parentRuleId: toId<RuleId>("rule-ex-07"),
  displayCode: "EX-07w",
  title: "蠕虫感染",
  expression: {
    kind: "logic",
    operator: "all",
    operatorLabel: "同时满足",
    children: [
      {
        kind: "predicate",
        predicateId: "predicate-ex-07w-status",
        subject: "受试者",
        attribute: "蠕虫感染",
        comparator: "exists",
        comparatorLabel: "存在",
        value: true,
        unit: null,
        requiresProfessionalJudgment: true,
        timeConstraint: null,
      },
    ],
  },
  exceptionExpression: {
    kind: "predicate",
    predicateId: "predicate-ex-07w-exception",
    subject: "受试者",
    attribute: "已治愈",
    comparator: "eq",
    comparatorLabel: "等于",
    value: true,
    unit: null,
    requiresProfessionalJudgment: false,
    timeConstraint: null,
  },
  sourceRefs: ["body.p115"],
  sourceExcerpts: ["6个月内存在或疑似蠕虫感染"],
};

function issue(affectedRefs: string[]): IntegrityIssueView {
  return {
    issueCode: "TIME_ANCHOR_UNRESOLVED",
    checkName: "时间要求完整性",
    level: "blocker",
    problem: "尚未明确六个月期限的起算时间点",
    impact: "无法判断该病史是否落入方案规定时限",
    nextAction: "请核对方案原文并补充起算时间点",
    affectedRefs,
    repairScope: affectedRefs,
  };
}

describe("isIntegrityIssueRelatedToComponent", () => {
  it.each([
    ["表达式谓词", "predicate-ex-07w-status"],
    ["例外谓词", "predicate-ex-07w-exception"],
    ["子项标识", "component-ex-07w"],
    ["父项标识", "rule-ex-07"],
    ["展示编号", "EX-07w"],
    ["原文定位", "body.p115"],
  ])("可按%s关联问题", (_label, affectedRef) => {
    expect(isIntegrityIssueRelatedToComponent(issue([affectedRef]), component)).toBe(true);
  });

  it("不会把其他条款的问题误挂到当前子项", () => {
    expect(isIntegrityIssueRelatedToComponent(issue(["predicate-ex-09"]), component)).toBe(false);
  });
});
