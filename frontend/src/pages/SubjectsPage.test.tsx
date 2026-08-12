// @vitest-environment jsdom
/**
 * Patient Profile（受试者与资料）组件测试：首屏风险过滤、完整明细、
 * 应备证据覆盖与“尚未见到 ≠ 明确否认”的显示语义（UAT-P1-06）。
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { SubjectsPage } from "./SubjectsPage";

async function openUat03(user: ReturnType<typeof userEvent.setup>) {
  render(<SubjectsPage />);
  // 默认进入第一位受试者（UAT-01）
  await screen.findByRole("heading", { name: "UAT-01" });
  await user.click(screen.getByRole("button", { name: /UAT-03/ }));
  await screen.findByRole("heading", { name: "UAT-03" });
}

describe("受试者与资料页", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("默认显示首位受试者并列出全部受试者", async () => {
    render(<SubjectsPage />);
    expect(await screen.findByRole("heading", { name: "UAT-01" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /UAT-02/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /UAT-08/ })).toBeInTheDocument();
  });

  it("切换受试者后风险视图突出关键事件并给出证据直达", async () => {
    const user = userEvent.setup();
    await openUat03(user);
    const riskSection = screen
      .getByRole("heading", { name: /关键事件与风险/ })
      .closest("section");
    expect(riskSection).not.toBeNull();
    // 7 个事件全部带风险分类 → 风险视图应全部可见
    expect(
      within(riskSection as HTMLElement).getAllByRole("article"),
    ).toHaveLength(7);
    expect(riskSection).toHaveTextContent("资料缺口与冲突待处理");
    // 证据直达：打开证据进入工作台
    const link = within(riskSection as HTMLElement).getAllByRole("link", {
      name: /打开证据/,
    })[0];
    expect(link.getAttribute("href")).toMatch(
      /^#\/workbench\?episode=episode-uat-03-screening-gap_conflict/,
    );
  });

  it("资料页元信息使用中文项目展示名，不暴露原始项目代号", async () => {
    render(<SubjectsPage />);
    expect(await screen.findByText(/界面试用项目 · III期/)).toBeInTheDocument();
    expect(screen.queryByText(/SYNTHETIC-001-III/)).not.toBeInTheDocument();
  });

  it("窄屏受试者选择器（下拉）存在且可切换受试者", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: "UAT-01" });
    const picker = screen.getByLabelText("受试者");
    expect(picker.tagName).toBe("SELECT");
    expect(screen.getAllByRole("option")).toHaveLength(8);
    await user.selectOptions(picker, "subject-uat-03-gap_conflict");
    await screen.findByRole("heading", { name: "UAT-03" });
    expect(window.location.hash).toContain("subject=subject-uat-03-gap_conflict");
  });

  it("风险过滤可按“存在冲突”缩小事件范围", async () => {
    const user = userEvent.setup();
    await openUat03(user);
    const filterButton = screen.getByRole("button", { name: "存在冲突" });
    await user.click(filterButton);
    const riskSection = screen
      .getByRole("heading", { name: /关键事件与风险/ })
      .closest("section");
    await waitFor(() => {
      expect(
        within(riskSection as HTMLElement).getAllByRole("article"),
      ).toHaveLength(1);
    });
    expect(riskSection).toHaveTextContent("同一判断存在冲突来源");
  });

  it("完整明细按主题展开并标记未记录≠否认", async () => {
    const user = userEvent.setup();
    await openUat03(user);
    await user.click(screen.getByRole("button", { name: "完整明细" }));
    expect(
      await screen.findByRole("heading", { name: /完整明细/ }),
    ).toBeInTheDocument();
    // 主题分组标题
    expect(screen.getByRole("heading", { name: "既往史" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "用药" })).toBeInTheDocument();
    // 空主题显示未记录说明
    expect(screen.getAllByText(/未记录按资料缺口处理/).length).toBeGreaterThan(0);
  });

  it("应备证据覆盖区分五类状态，引用未提供显示固定文案", async () => {
    const user = userEvent.setup();
    await openUat03(user);
    const coverage = screen
      .getByRole("heading", { name: /应备证据覆盖/ })
      .closest("section");
    expect(coverage).not.toBeNull();
    expect(coverage).toHaveTextContent("尚未见到");
    expect(coverage).toHaveTextContent("后续节点尚未到期");
    expect(coverage).toHaveTextContent("已引用但资料未提供");
    expect(coverage).toHaveTextContent("资料中提到这份文件，但当前尚未提供");
  });
});
