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
    // 汇总事件只链接到判断依据，不冒充事件本身的原始依据。
    const link = within(riskSection as HTMLElement).getAllByRole("link", {
      name: /查看判断依据/,
    })[0];
    expect(link.getAttribute("href")).toMatch(
      /^#\/workbench\?episode=episode-uat-03-screening-gap_conflict/,
    );
  });

  it("Profile 事件按证据关系显示诚实入口，不用无关片段冒充原始依据", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: "UAT-01" });
    await user.click(screen.getByRole("button", { name: "完整明细" }));

    const surgeryEvent = screen
      .getByRole("heading", { name: "阑尾切除术" })
      .closest("article");
    expect(surgeryEvent).not.toBeNull();
    expect(
      within(surgeryEvent as HTMLElement).queryByRole("link"),
    ).not.toBeInTheDocument();
    expect(surgeryEvent).toHaveTextContent("尚无该事件的独立原始资料定位");

    await user.click(screen.getByRole("button", { name: "返回风险视图" }));
    await user.click(screen.getByRole("button", { name: /UAT-03/ }));
    await screen.findByRole("heading", { name: "UAT-03" });
    expect(
      screen.getByRole("link", {
        name: "查看关联规则资料：合并用药时间轴待核对",
      }),
    ).toBeInTheDocument();
  });

  it("资料页元信息使用中文项目展示名，不暴露原始项目代号", async () => {
    render(<SubjectsPage />);
    expect(await screen.findByText(/界面试用项目 · Ⅲ期/)).toBeInTheDocument();
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
    // 空主题只表示当前没有结构化事件，缺口与否由应备证据覆盖决定（B3），
    // 不再把所有空泳道一律写成资料缺口
    expect(screen.getAllByText(/没有已整理的结构化事件/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/按资料缺口处理/)).not.toBeInTheDocument();
  });

  it("冲突来源在 Profile 风险视图内并列：立场、来源文件/页码/精度与快照版本（UAT-P1-06）", async () => {
    const user = userEvent.setup();
    await openUat03(user);
    expect(
      screen.getByRole("heading", { name: "冲突来源并列" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/不自动选择其中一方/)).toBeInTheDocument();
    // 两个事实并列，各自带立场与属性名
    expect(screen.getByText("明确记载")).toBeInTheDocument();
    expect(screen.getByText("明确否认")).toBeInTheDocument();
    expect(
      screen.getAllByText("研究者·构成不可接受参与风险").length,
    ).toBeGreaterThanOrEqual(2);
    // 每条来源：文件、页码、定位精度、资料快照版本
    const conflictSection = screen.getByLabelText("冲突来源并列");
    expect(
      within(conflictSection).getAllByText("合成筛选资料.pdf").length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      within(conflictSection).getAllByText(/第 4 页/).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      within(conflictSection).getAllByText("仅页码").length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      within(conflictSection).getByText(/资料快照：第 1 版（2026-08-12 整理）/),
    ).toBeInTheDocument();
    // 原始后端 ID 不作为主标签出现
    expect(screen.queryByText(/component-ex-01/)).not.toBeInTheDocument();
    expect(screen.queryByText(/fact-uat-03/)).not.toBeInTheDocument();
  });

  it("无冲突受试者的风险视图不显示冲突并列区块，完整明细视图也不重复显示", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: "UAT-01" });
    expect(
      screen.queryByRole("heading", { name: "冲突来源并列" }),
    ).not.toBeInTheDocument();
    // UAT-03 完整明细视图不重复展示冲突并列（只在风险视图）
    await user.click(screen.getByRole("button", { name: /UAT-03/ }));
    await screen.findByRole("heading", { name: "UAT-03" });
    await user.click(screen.getByRole("button", { name: "完整明细" }));
    await screen.findByRole("heading", { name: /完整明细/ });
    expect(
      screen.queryByRole("heading", { name: "冲突来源并列" }),
    ).not.toBeInTheDocument();
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
    // I4：每行带规则编号与到期节点（如 IN-01 年龄要求 → 筛选期）
    expect(coverage).toHaveTextContent("IN-01");
    expect(coverage).toHaveTextContent("筛选节点应有可定位的年龄记录。");
    expect(coverage).toHaveTextContent("到期节点：筛选期");
    expect(coverage).toHaveTextContent("到期节点：基线/随机前");
  });
});
