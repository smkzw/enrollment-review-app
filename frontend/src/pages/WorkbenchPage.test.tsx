// @vitest-environment jsdom
/**
 * 入排工作台组件测试：规则树父子层级、三区同步、四级定位精度、
 * 证据弹窗焦点管理（UAT-P1-07/08/13 语义）。
 */

import { render, screen, waitFor, within } from "@testing-library/react";
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
    window.sessionStorage.clear();
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
    // 证据区：仅页码 + 降级原因 + 识别文字（同一降级证据可能同时出现在冲突来源并列区与相关证据区）
    expect(screen.getAllByText("仅页码").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/扫描页无法稳定定位字符或坐标/).length,
    ).toBeGreaterThan(0);
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

  it("无效审核节点 URL 显示明确未找到，不打开其他受试者（B4）", async () => {
    window.location.hash = "#/workbench?episode=episode-does-not-exist";
    render(<WorkbenchPage />);
    await screen.findByRole("heading", { name: "入排工作台" });
    expect(
      screen.getByText("未找到这个审核节点。"),
    ).toBeInTheDocument();
    expect(screen.getByText(/没有打开其他受试者的资料/)).toBeInTheDocument();
    // 未静默回落到任何受试者
    expect(screen.queryByText("UAT-01", { selector: ".workbench-episode__subject" })).not.toBeInTheDocument();
    expect(screen.queryByText("UAT-03", { selector: ".workbench-episode__subject" })).not.toBeInTheDocument();
    // 提供返回看板入口
    expect(
      screen.getByRole("link", { name: "返回项目看板" }),
    ).toHaveAttribute("href", "#/board");
  });

  it("无效 URL 后修复为裸导航时回到最近有效审核节点", async () => {
    window.location.hash = "#/workbench?episode=episode-does-not-exist";
    render(<WorkbenchPage />);
    await screen.findByText("未找到这个审核节点。");
    // 修复地址为裸导航：无最近记录时回落首个节点（UAT-02 筛选期，与既有排序一致），
    // 有效 URL 记录存在时则回到最近一次审核节点
    window.location.hash = "#/workbench";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => {
      expect(
        screen.getByText("UAT-02", { selector: ".workbench-episode__subject" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("筛选期", { selector: ".workbench-episode__stage" })).toBeInTheDocument();
  });

  it("冲突来源并列：两个事实各带立场、来源文件、页码、精度与快照版本（B1）", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(
      screen.getByRole("heading", { name: "冲突来源并列" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/不自动选择其中一方/)).toBeInTheDocument();
    // 两个事实并列：明确记载 vs 明确否认
    expect(screen.getByText("明确记载")).toBeInTheDocument();
    expect(screen.getByText("明确否认")).toBeInTheDocument();
    expect(screen.getByText(/受影响子项：EX-01a/)).toBeInTheDocument();
    expect(screen.getByText(/资料版本：第 1 版（2026-08-12 整理）/)).toBeInTheDocument();
    // 每个事实都带来源定位：文件、页码、精度
    const conflictSection = screen.getByLabelText("冲突来源并列");
    expect(
      within(conflictSection).getAllByText("合成筛选资料.pdf").length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      within(conflictSection).getAllByText("仅页码").length,
    ).toBeGreaterThanOrEqual(2);
    // 打开其中一个来源，证据弹窗显示资料版本版本且不声称可打开整页
    await user.click(
      within(conflictSection)
        .getAllByRole("button", { name: /打开证据：合成筛选资料/ })[0],
    );
    const dialog = screen.getByRole("dialog", { name: "原始资料证据" });
    expect(dialog).toHaveTextContent("资料版本");
    expect(dialog).toHaveTextContent("第 1 版（2026-08-12 整理）");
    expect(dialog).not.toHaveTextContent("可打开整页");
    await user.keyboard("{Escape}");
  });

  it("例外条件说明对主判定的作用，谓词无“为 等于 是”机械拼接（B5/I2）", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(
      screen.getByText("且不满足以下例外情况"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/例外条件成立时，本条不因主条件成立直接判定/),
    ).toBeInTheDocument();
    // 例外树以整句中文呈现，不再出现“为 等于 是”叠加
    expect(
      screen.getByText("例外情况·方案例外已记录"),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("为 等于");
    expect(document.body).not.toHaveTextContent("等于 是");
  });

  it("应备证据覆盖区分节点全部子项，行带规则编号、具体要求与到期节点（I4）", async () => {
    const user = userEvent.setup();
    await openWorkbench(user);
    expect(
      screen.getByRole("heading", { name: "应备证据覆盖（节点全部子项）" }),
    ).toBeInTheDocument();
    // 节点全部应备证据：IN-01 年龄记录要求 + EX-01a 复合风险要求（编号同时在行动区出现）
    expect(screen.getAllByText("IN-01").length).toBeGreaterThan(0);
    expect(
      screen.getByText("筛选节点应有可定位的年龄记录。"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("EX-01a").length).toBeGreaterThan(0);
    // 同一要求同时在“当前子项”与“节点全部子项”两处列出（范围标签不同）
    expect(
      screen.getAllByText(/异常指标与研究者不可接受风险判断必须同时有证据/).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/到期节点：筛选期/).length).toBeGreaterThan(0);
    // 当前子项要求与节点全部要求明确分开
    expect(
      screen.getByRole("heading", { name: "应备证据（当前子项）" }),
    ).toBeInTheDocument();
    // 展开 IN-01 父级后选中子项：factType 须投影为中文属性名
    // （禁止把整串 factType 误当作 attributeDisplayName 的 attribute）
    await user.click(
      screen.getByRole("button", { name: /IN-01 入选条件/ }),
    );
    await user.click(
      screen.getByRole("button", { name: /IN-01 年龄要求/ }),
    );
    await waitFor(() => {
      expect(screen.getByText("人口学·年龄（岁）")).toBeInTheDocument();
    });
  });

  it("裸导航保留最近一次有效审核节点，不跳转其他受试者（B4）", async () => {
    const user = userEvent.setup();
    await openWorkbench(user, EPISODE_URL); // 打开 UAT-03 筛选期
    // 裸导航回工作台：仍停留在最近一次 UAT-03 筛选期
    window.location.hash = "#/workbench";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => {
      expect(
        screen.getByText("UAT-03", { selector: ".workbench-episode__subject" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("筛选期", { selector: ".workbench-episode__stage" })).toBeInTheDocument();
    expect(screen.queryByText("UAT-01", { selector: ".workbench-episode__subject" })).not.toBeInTheDocument();
  });
});
