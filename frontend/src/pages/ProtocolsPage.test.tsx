// @vitest-environment jsdom
/**
 * 方案工作台组件测试：当前/草稿版本对比与新增/删除/变化规则（UAT-P1-03）。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { ProtocolsPage } from "./ProtocolsPage";

describe("方案工作台", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.sessionStorage.clear();
  });

  it("保存草稿后离开页面再进入，仍保持未发布草稿状态", async () => {
    const user = userEvent.setup();
    const first = render(<ProtocolsPage />);
    await screen.findByRole("heading", { name: "方案工作台" });
    await user.click(screen.getByRole("button", { name: "保存为草稿" }));
    first.unmount();

    render(<ProtocolsPage />);
    expect(await screen.findByRole("button", { name: "已保存为草稿" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("当前规则版本没有被覆盖");
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

  it("可以打开每类变化的原文定位，保存草稿不覆盖当前版本并可复位", async () => {
    const user = userEvent.setup();
    render(<ProtocolsPage />);
    await screen.findByRole("heading", { name: "方案工作台" });

    expect(screen.getByRole("heading", { name: /新增/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /删除/ })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /逻辑或时间范围变化/ }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: /查看当前方案.*EX-05/ }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "查看新版本草稿第 12 页：EX-05" }),
    );
    const sourceDialog = screen.getByRole("dialog", { name: /EX-05/ });
    expect(sourceDialog).toHaveTextContent("新版本草稿");
    expect(sourceDialog).toHaveTextContent("第 12 页");
    await user.click(
      within(sourceDialog).getByRole("button", { name: "关闭方案原文定位" }),
    );

    expect(
      screen.getByRole("button", { name: "查看当前方案第 10 页：必做-02" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /查看新版本草稿.*必做-02/ }),
    ).not.toBeInTheDocument();
    const changedGroup = screen
      .getByRole("heading", { name: /逻辑或时间范围变化/ })
      .closest("section");
    expect(changedGroup).toHaveTextContent("查看当前方案第 10 页：EX-01");
    expect(changedGroup).toHaveTextContent("查看新版本草稿第 12 页：EX-01");

    await user.click(screen.getByRole("button", { name: "保存为草稿" }));
    expect(screen.getByRole("status")).toHaveTextContent(/已保存为草稿/);
    expect(screen.getByText("V1.0")).toBeInTheDocument();
    expect(screen.getByText(/当前规则版本没有被覆盖/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "恢复试用初始状态" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存为草稿" })).toBeInTheDocument();
  });
});
