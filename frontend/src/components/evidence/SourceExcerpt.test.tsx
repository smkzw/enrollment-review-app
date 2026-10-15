// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sharedExcerptTerms, SourceExcerpt } from "./SourceExcerpt";

describe("当前条目的原文重点", () => {
  it("合并重叠重点，保留每一个原文字元与否定", () => {
    const text = "未使用药物甲；药物甲与治疗效果无关。";
    const { container } = render(<SourceExcerpt text={text} focusTexts={["使用药物甲", "药物甲"]} />);
    expect(container.textContent).toBe(text);
    expect([...container.querySelectorAll("mark")].map(node => node.textContent)).toEqual(["使用药物甲", "药物甲"]);
    expect(container.textContent).toMatch(/^未使用/);
  });

  it("按当前条件的共有文字突出，不把相同数字或泛称当作重点", () => {
    const text = "受试者筛选期：血小板计数 100，另处报告 100。";
    const { container } = render(<SourceExcerpt text={text} context="筛选期血小板计数不低于100" />);
    expect([...container.querySelectorAll("mark")].map(node => node.textContent)).toEqual(["血小板计数"]);
    expect(sharedExcerptTerms("100 受试者 筛选期", "100 受试者 筛选期")).toEqual([]);
    expect(container.textContent).toBe(text);
  });

  it("切换条目时重点跟随，不修改带HTML样文字的源内容", () => {
    const text = "ALT 40；AST 20；<script>不执行</script>";
    const { container, rerender } = render(<SourceExcerpt text={text} focusTexts={["ALT"]} />);
    expect(container.querySelector("mark")).toHaveTextContent("ALT");
    rerender(<SourceExcerpt text={text} focusTexts={["AST"]} />);
    expect(container.querySelector("mark")).toHaveTextContent("AST");
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toBe(text);
  });

  it("不匹配时不造重点，英文项目不能命中另一项目内部", () => {
    const text = "SALT 20";
    const { container } = render(<SourceExcerpt text={text} focusTexts={["ALT", "其他内容"]} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe(text);
  });
});
