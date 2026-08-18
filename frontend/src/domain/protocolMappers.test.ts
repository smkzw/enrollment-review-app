import { describe, expect, it } from "vitest";
import { draftRevisionFixture } from "../fixtures/protocol-deconstruction-workbench";
import { mapProtocolDraftRules, mapProtocolSourceLocators } from "./protocolMappers";

describe("方案草稿来源映射", () => {
  it("按子组件 ID 保留同一父规则下各自的来源", () => {
    const content = structuredClone(draftRevisionFixture.content) as Record<string, unknown>;
    const rules = content.proposed_rules as Array<Record<string, unknown>>;
    const firstRule = rules[0]!;
    const components = firstRule.components as Array<Record<string, unknown>>;
    const secondComponent = structuredClone(components[0]!);
    secondComponent.rule_component_id = "component-in-b";
    secondComponent.display_code = "IN-01b";
    components.push(secondComponent);

    const componentDrafts = content.component_drafts as Array<Record<string, unknown>>;
    componentDrafts.push({
      draft_component_id: "draft-component-in-b",
      parent_official_code: "IN-01",
      proposed_component: secondComponent,
      source_refs: ["span-in-b"],
      source_excerpts: ["第二条入选条件"],
    });

    const mapped = mapProtocolDraftRules(content);
    expect(mapped[0]?.sourceRefs).toEqual(["span-in", "span-in-b"]);
    expect(mapped[0]?.components[0]?.sourceRefs).toEqual(["span-in"]);
    expect(mapped[0]?.components[1]?.sourceRefs).toEqual(["span-in-b"]);
    expect(mapped[0]?.components[1]?.sourceExcerpts).toEqual(["第二条入选条件"]);
  });

  it("保留后端渲染页与未对齐结构块精度，不把 null 页码拼进界面", () => {
    const mapped = mapProtocolSourceLocators(
      {
        aligned: {
          source_ref: "body.p7",
          document_part: "body",
          table_path: null,
          render_page: 7,
          precision: "text_range",
          excerpt: "方案原文",
          degradation_reason: null,
        },
        block: {
          source_ref: "table.p0",
          document_part: "body",
          table_path: "table.0",
          render_page: null,
          page_number: null,
          precision: "block",
          excerpt: null,
          degradation_reason: "表格文本未在渲染页中找到",
        },
      },
      ["aligned", "block"],
    );

    expect(mapped[0]).toMatchObject({
      sourceRef: "方案正文",
      pageLabel: "第 7 页",
      precision: "text_range",
    });
    expect(mapped[1]).toMatchObject({
      sourceRef: "方案表格",
      pageLabel: null,
      precision: "block",
      precisionLabel: "结构块",
    });
    expect(mapped[1]?.pageLabel).toBeNull();
  });
});
