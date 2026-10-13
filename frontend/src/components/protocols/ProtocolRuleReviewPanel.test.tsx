// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { decodeRuleReviews } from "../../api/protocolRuleReviews";
import { ProtocolRuleReviewPanel } from "./ProtocolRuleReviewPanel";
import { ProtocolJobFlow } from "./ProtocolJobFlow";
import { createProtocolWorkbenchStub, setProtocolWorkbenchRepository, PROTOCOL_DEMO_JOB_ID } from "../../api/protocolWorkbenchRepository";
import { protocolSessionFixtures } from "../../fixtures/protocol-deconstruction-workbench";

const hash = "a".repeat(64);
const entry = { official_code: "IN-01", kind: "rule", label: "年龄要求", rule_content_hash: hash,
  source_refs: ["source-1"], issue_refs: ["component-1"], review: null };
const initial = { job_id: "job", draft_revision_id: "revision", operator_name: "王医学经理",
  all_reviewed: false, entries: [entry], history: [] };
const integrity = { jobId: "job", publishable: true, blockingCount: 0, reviewCount: 0, reminderCount: 1,
  summary: "可审定", checks: [], issues: [{ issueCode: "hint", checkName: "numeric", level: "提醒",
    problem: "请核对年龄依据", impact: "年龄判断", nextAction: "查看原文", affectedRefs: ["component-1"], repairScope: [] }] };
const sources = { jobId: "job", snapshotId: "snapshot", selectedPhase: "phase_iii" as const,
  selectedPhaseLabel: "III期", sourceSpans: {}, sourceMaterials: {} };

afterEach(() => { vi.unstubAllGlobals(); setProtocolWorkbenchRepository(createProtocolWorkbenchStub()); });
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
describe("逐条审定", () => {
  it("拒绝错任务、过期内容、重复条目与虚假的全部已审定状态", () => {
    expect(decodeRuleReviews(initial, "job").all_reviewed).toBe(false);
    expect(() => decodeRuleReviews(initial, "other")).toThrow();
    expect(() => decodeRuleReviews({ ...initial, all_reviewed: true }, "job")).toThrow();
    expect(() => decodeRuleReviews({ ...initial, entries: [entry, entry] }, "job")).toThrow();
    const review = { record_id: "record", official_code: "IN-01", rule_content_hash: "b".repeat(64),
      reviewer_kind: "builder_verification", reviewed_by: "构建者（验证）", reviewed_at: "2026-10-12T00:00:00Z",
      action: "approved", note: null, result_variables: [] };
    expect(() => decodeRuleReviews({ ...initial, entries: [{ ...entry, review }] }, "job")).toThrow();
    const copied = { ...initial, all_reviewed: true, entries: [{ ...entry, review, reviewed_content_hash: hash }], history: [review] };
    expect(decodeRuleReviews(copied, "job").entries[0].review?.rule_content_hash).toBe("b".repeat(64));
    expect(() => decodeRuleReviews({ ...copied, entries: [{ ...entry, review, reviewed_content_hash: "c".repeat(64) }] }, "job")).toThrow();
    expect(() => decodeRuleReviews({ ...copied, entries: [{ ...entry, review: { ...review, action: "revoked" }, reviewed_content_hash: hash }] }, "job")).toThrow();
  });

  it("显示对应提示，明确验证身份，并用内容与修订核对保存", async () => {
    const onReady = vi.fn();
    const fetcher = vi.fn(async (url, options) => {
      if (options.method === "GET") return new Response(JSON.stringify(String(url).endsWith("/variables")
        ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial));
      const payload = JSON.parse(options.body);
      expect(payload.reviewer_kind).toBe("builder_verification");
      expect(payload.expected_revision_id).toBe("revision");
      expect(payload.rule_content_hash).toBe(hash);
      const review = { record_id: "record", official_code: "IN-01", rule_content_hash: hash,
        reviewer_kind: "builder_verification", reviewed_by: "构建者（验证）", reviewed_at: "2026-10-12T00:00:00Z",
        action: "approved", note: null, result_variables: [] };
      return new Response(JSON.stringify({ ...initial, all_reviewed: true,
        entries: [{ ...entry, review }], history: [review] }));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={onReady} />);
    const hint = await screen.findByText("请核对年龄依据", { exact: true });
    expect(hint.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(hint.closest("details")!.querySelector("summary")!);
    expect(hint.closest("details")).toHaveAttribute("open");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    expect(screen.getByText(/不能代替医学经理正式审定/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "审定通过" }));
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(true));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定范围" }), "approved");
    expect(screen.getByRole("button", { name: "撤销审定" })).toBeEnabled();
  });

  it("分类、筛选、多选确认不会自动批准，批量保存明确绑定内容和身份", async () => {
    const second = { ...entry, official_code: "EX-01", label: "已知过敏", rule_content_hash: "b".repeat(64) };
    const full = { ...initial, entries: [entry, second] };
    const fetcher = vi.fn(async (_url, options) => {
      if (options.method === "GET") return new Response(JSON.stringify(String(_url).endsWith("/variables")
        ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : full));
      const payload = JSON.parse(options.body);
      expect(payload.entries.map((item: { official_code: string }) => item.official_code)).toEqual(["IN-01", "EX-01"]);
      expect(payload.expected_revision_id).toBe("revision");
      expect(payload.reviewer_kind).toBe("builder_verification");
      return new Response(JSON.stringify(full));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()} />);
    await screen.findByRole("checkbox", { name: "选择IN-01" });
    await userEvent.click(screen.getByRole("checkbox", { name: "选择IN-01" }));
    await userEvent.click(screen.getByRole("button", { name: "排除标准 1" }));
    expect(screen.getByRole("button", { name: "批准所选 0 项" })).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: "选择IN-01" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "全部 2" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "选择当前列表" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    await userEvent.click(screen.getByRole("button", { name: "批准所选 2 项" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("构建者验证（仅供验证）");
    expect(fetcher.mock.calls.every(([, options]) => options.method === "GET")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "确认批准所选" }));
    await screen.findByText("已保存2项审定。没有发布规则包。");
  });

  it("真实主入口只读取审定记录，不自动新建跨章作业", async () => {
    const base = createProtocolWorkbenchStub();
    setProtocolWorkbenchRepository({ ...base, kind: "http", getSession: async () => ({
      ...protocolSessionFixtures[PROTOCOL_DEMO_JOB_ID]!, draftRevisionId: "revision",
    }) });
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...initial, job_id: PROTOCOL_DEMO_JOB_ID })));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolJobFlow jobId={PROTOCOL_DEMO_JOB_ID} componentParam={null} />);
    await screen.findByRole("heading", { name: "逐条审定" });
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(fetcher.mock.calls.every(([url, options]) => /\/draft\/(reviews|variables)$/.test(String(url)) && options.method === "GET")).toBe(true);
    expect(screen.getByRole("button", { name: "发布" })).toBeDisabled();
  });
  it("实际条件树与原文分开展示，保留组合方向和中文项目名", async () => {
    const atom = (id: string, value: number) => ({ kind: "predicate", predicate: { predicate_id: id,
      subject: "受试者", attribute: "年龄", comparator: "gte", value, unit: "岁" } });
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: [{ rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "年龄范围", expression: {
        kind: "logical", operator: "all", children: [atom("p1", 18), { kind: "logical", operator: "any", children: [atom("p2", 30), atom("p3", 40)] }],
      }, exception_expression: null }] }] };
    vi.stubGlobal("fetch", vi.fn(async url => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial))));
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} content={content} onReady={vi.fn()} />);
    await screen.findByRole("region", { name: "逻辑解析" });
    expect([...screen.getByLabelText("逻辑解析").querySelectorAll(".expr-node__operator")]
      .map(node => node.textContent)).toEqual(["全部满足", "任一满足"]);
    expect(screen.getByText("年龄 大于等于 18 岁")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "查找条目" }), "没有的条目");
    expect(screen.queryByRole("region", { name: "逻辑解析" })).not.toBeInTheDocument();
    expect(screen.getByText("当前范围没有条目。")).toBeInTheDocument();
  });
  it.each([
    ["本节点已有治疗及其相对应疗效", "本节点已有治疗及其相对应疗效"],
    ["对相对应治疗的疗效已明确否认", "对相对应治疗的疗效已明确否认"],
    ["treatment_response", "疗效记录"],
  ])("数据项目名不能覆盖完整条件或否定：%s", async (attribute, visible) => {
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: [{ rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "治疗及疗效核对",
        expression: { kind: "predicate", predicate: { predicate_id: "response", subject: "受试者", attribute,
          comparator: "exists", value: null, unit: null, requires_professional_judgment: true } }, exception_expression: null }] }] };
    vi.stubGlobal("fetch", vi.fn(async url => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [{ variable_id: "response", label_zh: "疗效记录",
            value_type: "boolean", domain: "history", canonical_unit: null, unit_conversions: {}, plausible_range: null, aliases_zh: [] }],
          predicates: [{ component_id: "c", predicate_id: "response", label: "疗效记录", official_code: "IN-01",
            variable_id: "response", requirements: [] }] } : initial))));
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources}
      content={content} onReady={vi.fn()} />);
    const region = await screen.findByRole("region", { name: "逻辑解析" });
    await waitFor(() => expect(region).toHaveTextContent(`${visible}：需有相应记录`));
    expect(region).toHaveTextContent("需要研究者判断");
    expect(region).not.toHaveTextContent("treatment_response");
  });
  it("多子项备选默认只展开第一组，其他组可独立打开且预览不保存审定", async () => {
    const atom = (id: string) => ({ kind: "predicate", predicate: { predicate_id: id,
      subject: "受试者", attribute: "年龄", comparator: "gte", value: 18, unit: "岁" } });
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: ["a", "b"].map(id => ({ rule_component_id: id, parent_rule_id: "r", display_code: `IN-01${id}`,
        title: `条件${id}`, expression: { kind: "logical", operator: "any", children: [atom(`${id}1`), atom(`${id}2`)] },
        exception_expression: null })) }] };
    const fetcher = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial)));
    const onEdit = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity}
      sources={sources} content={content} onReady={vi.fn()} onEdit={onEdit} />);
    await screen.findByLabelText("备选解释与处理");
    const advice = screen.getByLabelText("备选解释与处理");
    await userEvent.click(advice.querySelector("summary")!);
    const groups = [...container.querySelectorAll<HTMLDetailsElement>(".protocol-review-advice__group")];
    expect(groups).toHaveLength(2);
    expect(groups.map(group => group.open)).toEqual([true, false]);
    await userEvent.click(groups[1].querySelector("summary")!);
    expect(groups[1].open).toBe(true);
    await userEvent.click(groups[1].querySelector("button")!);
    expect(onEdit).toHaveBeenCalledWith("b", "all");
    expect(fetcher.mock.calls.every(([, options]) => !options || options.method === "GET")).toBe(true);
  });
});
