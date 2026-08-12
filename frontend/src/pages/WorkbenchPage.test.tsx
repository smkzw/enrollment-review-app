// @vitest-environment jsdom
/**
 * 入排工作台组件测试：规则树父子层级、三区同步、四级定位精度、
 * 证据弹窗焦点管理（UAT-P1-07/08/13 语义）。
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { WorkbenchPage } from "./WorkbenchPage";

const EPISODE_URL = "#/workbench?episode=episode-uat-03-screening-gap_conflict";

async function openWorkbench(
  user: ReturnType<typeof userEvent.setup>,
  hash: string = EPISODE_URL,
) {
  window.location.hash = hash;
  render(<WorkbenchPage />);
  await screen.findByRole("heading", { name: "入排工作台" });
  await waitFor(() => {
    expect(screen.getByText("UAT-03", { selector: ".workbench-episode__subject" })).toBeInTheDocument();
  });
  return user;
}

describe("入排工作台", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("URL 直达显示受试者、审核节点与主状态", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(
      screen.getByText("UAT-03", { selector: ".workbench-episode__subject" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("筛选期", { selector: ".workbench-episode__stage" }),
    ).toBeInTheDocument();
    expect(screen.getByText("当前节点缺口")).toBeInTheDocument();
  });

  it("规则树显示父子层级：父级 EX-01 展开含子项 EX-01a", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    const ruleButton = screen.getByRole("button", {
      name: /EX-01 排除条件，共 1 个子项，子项有冲突，已展开/,
    });
    expect(ruleButton).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/合成规则：研究者判断构成不可接受风险/)).toBeInTheDocument();
  });

  it("选中子项后判断区显示逻辑词与缺口，证据区显示定位精度", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    // 风险优先导航已直接选中 EX-01a。
    expect(
      screen.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toHaveAttribute("aria-current", "true");
    // 判断区：逻辑词 + 缺口 + 例外条件
    expect(screen.getAllByText("全部满足").length).toBeGreaterThan(0);
    expect(screen.getByText("任一满足")).toBeInTheDocument();
    expect(screen.getByText("不满足以下条件")).toBeInTheDocument();
    expect(screen.getByText("例外条件")).toBeInTheDocument();
    expect(screen.getByText("时间窗：随机前 28 天内")).toBeInTheDocument();
    expect(
      screen.getAllByText("文字或数值需要核对").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("来源存在冲突").length,
    ).toBeGreaterThan(0);
    // 证据区：仅页码 + 降级原因 + 识别文字
    expect(screen.getAllByText("仅页码").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/扫描页无法稳定定位字符或坐标/),
    ).toBeInTheDocument();
  });

  it("四级定位精度图例可见且仅页码无坐标高亮", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    const legend = screen.getByLabelText("定位精度说明");
    expect(legend).toHaveTextContent("坐标区域");
    expect(legend).toHaveTextContent("文本范围");
    expect(legend).toHaveTextContent("页内摘录");
    expect(legend).toHaveTextContent("仅页码");
    expect(legend).toHaveTextContent("没有坐标数据时不会显示任何高亮或定位框");
  });

  it("打开证据弹窗并支持 Escape 关闭", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(
      screen.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toHaveAttribute("aria-current", "true");
    const openEvidence = screen.getAllByRole("button", {
      name: /打开证据：合成筛选资料/,
    })[0];
    await user.click(openEvidence);
    const dialog = screen.getByRole("dialog", { name: "原始资料证据" });
    expect(dialog).toHaveTextContent("第 4 页");
    expect(dialog).toHaveTextContent("来源方：研究者方");
    expect(dialog).not.toHaveTextContent("原型");
    expect(dialog).toHaveTextContent("当前界面不附带原始页图预览");
    // Escape 关闭
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("核心判断区不泄漏空字段或英文年龄单位", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(document.body).not.toHaveTextContent("undefined");
    expect(document.body).not.toHaveTextContent("null");

    window.location.hash =
      "#/workbench?episode=episode-uat-01-screening-clear&component=component-in-01";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => {
      expect(screen.getByText(/大于等于 18/)).toBeInTheDocument();
    });
    expect(document.body).not.toHaveTextContent("year");
  });

  it("证据直达参数自动定位并选择引用该证据的子项", async () => {
    const user = userEvent.setup();
    await openWorkbench(
      user,
      "#/workbench?episode=episode-uat-03-screening-gap_conflict&evidence=span-uat-03-screening-gap-page",
    );
    // 自动选中引用该证据的 EX-01a，判断区出现其判断
    expect(
      screen.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toHaveAttribute("aria-current", "true");
    expect(screen.getAllByText("存在冲突").length).toBeGreaterThan(0);
  });
});
