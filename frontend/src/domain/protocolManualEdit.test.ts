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
});
