// @vitest-environment jsdom
/**
 * 方案工作台组件测试：当前/草稿版本对比与新增/删除/变化规则（UAT-P1-03）。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { ProtocolsPage } from "./ProtocolsPage";

describe("方案工作台", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("显示当前使用版本与新版草稿，并说明草稿不覆盖当前结果", async () => {
    render(<ProtocolsPage />);
    expect(await screen.findByRole("heading", { name: "方案工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /当前使用版本/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /新版本草稿/ })).toBeInTheDocument();
    expect(screen.getByText("V1.0")).toBeInTheDocument();
    expect(screen.getByText("V2.0（草稿）")).toBeInTheDocument();
    expect(screen.getByText(/草稿中的变化仅作比较参考/)).toBeInTheDocument();
  });

  it("差异列表区分新增 EX-05、删除必做-02 与变化 EX-01", async () => {
    render(<ProtocolsPage />);
    await screen.findByRole("heading", { name: "方案工作台" });
    expect(screen.getByRole("heading", { name: "规则差异" })).toBeInTheDocument();
    const list = screen.getByRole("heading", { name: "规则差异" }).closest("section");
    expect(list).toHaveTextContent("EX-05");
    expect(list).toHaveTextContent("必做-02");
    expect(list).not.toHaveTextContent("REQ-");
    expect(list).toHaveTextContent("EX-01");
  });

  it("提供方案原文位置与“新内容仍为草稿”说明", async () => {
    render(<ProtocolsPage />);
    await screen.findByRole("heading", { name: "方案工作台" });
    expect(screen.getByRole("heading", { name: "方案原文位置" })).toBeInTheDocument();
    expect(screen.getByText("当前方案")).toBeInTheDocument();
    expect(screen.getAllByText("新版本草稿").length).toBeGreaterThan(0);
    expect(screen.getByText(/当前规则版本未被覆盖/)).toBeInTheDocument();
  });
});
