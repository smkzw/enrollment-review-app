/**
 * 手工修订草稿补丁测试：改写子项标题与原文摘录，不改变结构/编号/来源绑定。
 */

import { describe, expect, it } from "vitest";
import { patchComponentText } from "./protocolManualEdit";
import { draftComparisonFixture } from "../fixtures/protocol-deconstruction-workbench";

const candidateContent = draftComparisonFixture.candidate.content;

describe("patchComponentText", () => {
  it("改写所选子项标题与方案原文摘录", () => {
    const patched = patchComponentText(candidateContent, "component-in", {
      title: "年龄要求（修订）",
      sourceExcerpts: ["年龄≥18岁", "且≤65岁"],
    });
    expect(patched).not.toBe(candidateContent);
    const rules = patched.proposed_rules as ReadonlyArray<Record<string, unknown>>;
    const rule = rules.find((item) => item.official_code === "IN-01");
    const components = rule?.components as ReadonlyArray<Record<string, unknown>>;
    const target = components.find(
      (item) => item.rule_component_id === "component-in",
    );
    expect(target?.title).toBe("年龄要求（修订）");
    const drafts = patched.component_drafts as ReadonlyArray<Record<string, unknown>>;
    const draft = drafts.find((item) => {
      const proposed = item.proposed_component as Record<string, unknown>;
      return proposed?.rule_component_id === "component-in";
    });
    expect(draft?.source_excerpts).toEqual(["年龄≥18岁", "且≤65岁"]);
  });

  it("不改变未选子项与结构字段", () => {
    const patched = patchComponentText(candidateContent, "component-in", {
      title: "年龄要求（修订）",
      sourceExcerpts: ["年龄≥18岁"],
    });
    const originalRules = candidateContent.proposed_rules as ReadonlyArray<
      Record<string, unknown>
    >;
    const patchedRules = patched.proposed_rules as ReadonlyArray<
      Record<string, unknown>
    >;
    expect(patchedRules).toHaveLength(originalRules.length);
    const exRule = patchedRules.find((item) => item.official_code === "EX-01");
    const exComponents = exRule?.components as ReadonlyArray<Record<string, unknown>>;
    expect(exComponents[0]?.title).toBe("肝功能阈值");
  });

  it("找不到匹配子项时原样返回（不做静默改写）", () => {
    const missing = patchComponentText(candidateContent, "component-missing", {
      title: "不存在",
      sourceExcerpts: ["不存在的摘录"],
    });
    expect(missing).toBe(candidateContent);
  });
});
