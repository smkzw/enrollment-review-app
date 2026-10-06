import { describe, expect, it } from "vitest";
import { getEditableProtocolComponents, patchComponentSemantics } from "./protocolManualEdit";
import { draftComparisonFixture } from "../fixtures/protocol-deconstruction-workbench";

const candidateContent = draftComparisonFixture.candidate.content;

describe("方案草稿手工修订", () => {
  it("读取子项的条件、资料要求和只读来源", () => {
    const components = getEditableProtocolComponents(candidateContent);
    const age = components.find((item) => item.componentId === "component-in")!;
    expect(age.predicates[0]).toMatchObject({ predicateId: "predicate-age", attribute: "年龄", comparator: "gte", valueText: "18" });
    expect(age.requirements[0]).toMatchObject({ dueStage: "screening" });
    expect(age.sourceExcerpts).toEqual(["年龄≥18岁"]);
  });

  it("修订逻辑、原子条件和资料要求，但不改来源摘录", () => {
    const components = getEditableProtocolComponents(candidateContent);
    const liver = components.find((item) => item.componentId === "component-ex")!;
    const predicate = { ...liver.predicates[0]!, valueText: "2", requiresProfessionalJudgment: true };
    const patched = patchComponentSemantics(candidateContent, liver.componentId, {
      title: "肝功能联合条件",
      mainOperator: "all",
      exceptionOperator: null,
      predicate,
      requirements: liver.requirements,
    });
    const patchedComponent = getEditableProtocolComponents(patched).find((item) => item.componentId === "component-ex")!;
    expect(patchedComponent.title).toBe("肝功能联合条件");
    expect(patchedComponent.mainOperator).toBe("all");
    expect(patchedComponent.predicates[0]).toMatchObject({ valueText: "2", requiresProfessionalJudgment: true });
    expect(patchedComponent.sourceExcerpts).toEqual(liver.sourceExcerpts);
  });

  it("找不到匹配子项时原样返回", () => {
    const missing = patchComponentSemantics(candidateContent, "component-missing", {
      title: "不存在",
      mainOperator: null,
      exceptionOperator: null,
      predicate: null,
      requirements: [],
    });
    expect(missing).toBe(candidateContent);
  });

  it("修订正常子项时完整保留未决要求和来源，不改旧稿", () => {
    const content = structuredClone(candidateContent);
    const rules = content.proposed_rules as Record<string, unknown>[];
    const restricted = [{
      rule_component_id: "restricted-extra", display_code: "IN-01b",
      title: "另项要求", source_span_ids: ["span-in"],
      source_excerpts: ["另须完成专项评估"],
      limitation_kind: "interpretation_unresolved",
      unresolved_dimensions: ["适用范围尚待核清"],
    }];
    rules[0]!.restricted_components = restricted;
    const before = JSON.stringify(content);
    const age = getEditableProtocolComponents(content).find(
      (item) => item.componentId === "component-in",
    )!;
    const patched = patchComponentSemantics(content, age.componentId, {
      title: "核对后的标题", mainOperator: age.mainOperator,
      exceptionOperator: age.exceptionOperator, predicate: age.predicates[0]!,
      requirements: age.requirements,
    });
    expect((patched.proposed_rules as Record<string, unknown>[])[0]!
      .restricted_components).toEqual(restricted);
    expect(JSON.stringify(content)).toBe(before);
    expect(getEditableProtocolComponents(content).some(
      (item) => item.componentId === "restricted-extra",
    )).toBe(false);
  });
});
