// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { decodeReviewScope } from "../../api/protocolReviewScope";
import { ProtocolReviewScope } from "./ProtocolReviewScope";
import { ProtocolScopeSourcePicker } from "./ProtocolScopeSourcePicker";

function view(job = "job", revision = "rev") {
  return { job_id: job, draft_revision_id: revision, scope_content_hash: "c".repeat(64),
    clinical_adoption_applied: false, diagnostics: [],
    editable: false, selection: null, additional_source_records: [],
    candidates: [{ candidate_key: "d".repeat(64), scope_kind: "medication_section", label: "合并用药",
      source_span_ids: ["span"], official_codes: [], visit_instance: null, clinically_confirmed: false }],
    source_records: [{ source_span_id: "span", raw_text: "检查期间有源用药记录。", render_page: 7, identity_status: "ok" }] };
}
afterEach(() => vi.unstubAllGlobals());

describe("方案范围原文", () => {
  it("按需读取、分类下钻，不冒称新增内容已采用", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(view())));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    expect(fetcher).not.toHaveBeenCalled();
    await user.click(screen.getByText("查看审核范围"));
    expect(await screen.findByText(/不代表这些内容已经审定/)).toBeVisible();
    await user.click(screen.getByText("用药与伴随治疗章节"));
    await user.click(screen.getByText("合并用药"));
    expect(screen.getByText("第7页")).toBeVisible();
    expect(screen.getByText("检查期间有源用药记录。")).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("span")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /批准|发布/ })).not.toBeInTheDocument();
  });
  it("读取失败不显示空范围成功", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("保存的来源不可读")));
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    expect(await screen.findByRole("alert")).toHaveTextContent("保存的来源不可读");
    expect(screen.queryByText("0项")).not.toBeInTheDocument();
  });
  it("同一页不反复标注页码，重复标题不再占一段，正文仍完整保留", async () => {
    const data = view();
    data.candidates[0].source_span_ids = ["heading", "span", "other"];
    data.source_records.unshift({ ...data.source_records[0], source_span_id: "heading", raw_text: "合并用药" });
    data.source_records.push({ ...data.source_records[1], source_span_id: "other", raw_text: "另一项来源内容。" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    await userEvent.click(await screen.findByText("用药与伴随治疗章节"));
    await userEvent.click(screen.getByText("合并用药"));
    expect(screen.getAllByText("合并用药")).toHaveLength(1);
    expect(screen.getAllByText("第7页")).toHaveLength(1);
    expect(screen.getByText("另一项来源内容。")).toBeVisible();
    expect(screen.getByText("检查期间有源用药记录。")).toBeVisible();
  });
  it("切换项目后旧响应不能出现在新项目", async () => {
    let resolveOld!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => new Promise<Response>(resolve => { resolveOld = resolve; }))
      .mockResolvedValue(new Response(JSON.stringify({ ...view("new-job", "new-rev"), candidates: [] }))));
    const mounted = render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    mounted.rerender(<ProtocolReviewScope jobId="new-job" revisionId="new-rev" />);
    await screen.findByText(/不代表这些内容已经审定/);
    await act(async () => resolveOld(new Response(JSON.stringify(view()))));
    expect(screen.queryByText("合并用药")).not.toBeInTheDocument();
  });
  it("拒绝错误任务、修订及伪造采用身份", () => {
    expect(() => decodeReviewScope(view(), "other", "rev")).toThrow(/不一致/);
    expect(() => decodeReviewScope(view(), "job", "other")).toThrow(/不一致/);
    expect(() => decodeReviewScope({ ...view(), clinical_adoption_applied: true }, "job", "rev")).toThrow();
    expect(() => decodeReviewScope({ ...view(), candidates: [{ ...view().candidates[0], clinically_confirmed: true }] }, "job", "rev")).toThrow();
  });
  it("可勾选移除并保存理由，只追加草稿选择，不审批或发布", async () => {
    const user = userEvent.setup();
    const data = { ...view(), editable: true };
    const fetcher = vi.fn().mockImplementation(async (_url, init?: RequestInit) => {
      if (init?.method !== "PUT") return new Response(JSON.stringify(data));
      const body = JSON.parse(String(init.body));
      expect(body.expected_revision_id).toBe("rev");
      expect(body.proposal.included_candidate_keys).toEqual([]);
      expect(body.proposal.exclusions).toEqual([{ candidate_key: "d".repeat(64), reason: "后续范围另行核对" }]);
      return new Response(JSON.stringify({ ...data, draft_revision_id: "rev-next",
        selection: { ...body.proposal, snapshot_id: "snapshot", saved_by: "构建者（验证）", saved_at: "2026-10-15T00:00:00Z" } }));
    });
    vi.stubGlobal("fetch", fetcher);
    function Editor() { const [revision, setRevision] = useState("rev");
      return <ProtocolReviewScope jobId="job" revisionId={revision} onSaved={() => setRevision("rev-next")} />; }
    render(<Editor />);
    await user.click(screen.getByText("查看审核范围"));
    await user.click(await screen.findByText("用药与伴随治疗章节"));
    await user.click(screen.getByRole("checkbox", { name: "保留 合并用药" }));
    expect(screen.getByRole("button", { name: "保存范围选择" })).toBeDisabled();
    await user.type(screen.getByLabelText("移除理由"), "后续范围另行核对");
    await user.click(screen.getByRole("button", { name: "保存范围选择" }));
    expect(await screen.findByText(/范围选择已保存/)).toBeVisible();
    expect(screen.getByRole("button", { name: "保存范围选择" })).toBeDisabled();
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "审定通过" })).not.toBeInTheDocument();
  });
  it("可将已经定位的章节关联到具体条款，保存真实来源而非手写编号", async () => {
    const user = userEvent.setup();
    const data = { ...view(), editable: true, candidates: [...view().candidates,
      { ...view().candidates[0], candidate_key: "e".repeat(64), scope_kind: "official_rule_text", official_codes: ["IN-01"], label: "合成标准" }] };
    let submitted: Record<string, unknown> | null = null;
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (_url, init?: RequestInit) => {
      if (init?.method !== "PUT") return new Response(JSON.stringify(data));
      submitted = JSON.parse(String(init.body));
      const proposal = (submitted as { proposal: object }).proposal;
      return new Response(JSON.stringify({ ...data, draft_revision_id: "rev-next",
        selection: { ...proposal, snapshot_id: "snapshot", saved_by: "构建者（验证）", saved_at: "2026-10-15T00:00:00Z" } }));
    }));
    function Editor() { const [revision, setRevision] = useState("rev");
      return <ProtocolReviewScope jobId="job" revisionId={revision} onSaved={() => setRevision("rev-next")} />; }
    render(<Editor />);
    await user.click(screen.getByText("查看审核范围"));
    await user.click(await screen.findByText("手工指定原文"));
    await user.selectOptions(screen.getByLabelText("关联条款"), "IN-01");
    await user.selectOptions(screen.getByLabelText("从已定位章节选择"), "d".repeat(64));
    await user.type(screen.getByLabelText("选择理由"), "本条明确引用这一章节");
    await user.click(screen.getByRole("button", { name: "添加到范围" }));
    expect(screen.getByText(/手工指定的条款引用的说明/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "保存范围选择" }));
    await screen.findByText(/范围选择已保存/);
    expect(submitted).toMatchObject({ proposal: { additions: [{ scope_kind: "referenced_source",
      official_codes: ["IN-01"], source_span_ids: ["span"], reason: "本条明确引用这一章节" }] } });
  });
  it("手工指定具体待定位引用，不将其他引用或临床规则改为已采用", async () => {
    const user = userEvent.setup();
    const data = { ...view(), editable: true, diagnostics: [{ kind: "reference_unresolved", identifiers: ["参见8.12"],
      related_official_codes: ["IN-01"], diagnostic_key: "f".repeat(64), resolved_by_manual_selection: false }],
      candidates: [...view().candidates, { ...view().candidates[0], candidate_key: "e".repeat(64),
        scope_kind: "official_rule_text", label: "合成标准", official_codes: ["IN-01"] }] };
    let addition: unknown;
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (_url, init?: RequestInit) => {
      if (init?.method !== "PUT") return new Response(JSON.stringify(data));
      const body = JSON.parse(String(init.body)); addition = body.proposal.additions[0];
      return new Response(JSON.stringify({ ...data, draft_revision_id: "rev-next",
        diagnostics: data.diagnostics.map(item => ({ ...item, resolved_by_manual_selection: true })),
        selection: { ...body.proposal, snapshot_id: "snapshot", saved_by: "构建者（验证）", saved_at: "2026-10-15T00:00:00Z" } }));
    }));
    function Editor() { const [revision, setRevision] = useState("rev");
      return <ProtocolReviewScope jobId="job" revisionId={revision} onSaved={() => setRevision("rev-next")} />; }
    render(<Editor />);
    await user.click(screen.getByText("查看审核范围"));
    await user.click(await screen.findByText("手工指定原文"));
    await user.selectOptions(screen.getByLabelText("对应的待定位引用"), "f".repeat(64));
    await user.selectOptions(screen.getByLabelText("从已定位章节选择"), "d".repeat(64));
    await user.type(screen.getByLabelText("选择理由"), "指定本处引用的原文");
    await user.click(screen.getByRole("button", { name: "添加到范围" }));
    await user.click(screen.getByRole("button", { name: "保存范围选择" }));
    expect(await screen.findByText("引用原文已指定")).toBeVisible();
    expect(addition).toMatchObject({ official_codes: ["IN-01"], resolves_references: ["f".repeat(64)], source_span_ids: ["span"] });
    expect(screen.getByText(/补充要求尚未纳入规则/)).toBeVisible();
  });
  it("原文查找保留完整数量并可翻页，不要求用户输入内部位置编号", async () => {
    const user = userEvent.setup();
    const data = { ...view(), editable: true, candidates: [...view().candidates,
      { ...view().candidates[0], candidate_key: "e".repeat(64), scope_kind: "official_rule_text", label: "合成标准", official_codes: ["IN-01"] }] };
    const fetcher = vi.fn().mockImplementation(async (url: string) => {
      const offset = Number(new URL(url, "http://localhost").searchParams.get("offset") ?? 0);
      return new Response(JSON.stringify({ job_id: "job", draft_revision_id: "rev", total: 25,
        next_offset: offset === 0 ? 20 : null, items: Array.from({ length: offset === 0 ? 20 : 5 }, (_, index) => ({
          label: `额外原文${offset + index + 1}`, text: `合成原文${offset + index + 1}`, page: index + 1,
          source_span_ids: [`extra-${offset + index + 1}`], missing_positions: 0 })) }));
    });
    vi.stubGlobal("fetch", fetcher);
    const onAdd = vi.fn();
    render(<ProtocolScopeSourcePicker view={decodeReviewScope(data, "job", "rev")} onAdd={onAdd} />);
    await user.click(screen.getByText("手工指定原文"));
    await user.selectOptions(screen.getByLabelText("关联条款"), "IN-01");
    await user.type(screen.getByLabelText("选择理由"), "补充本条原文");
    await user.click(screen.getByText("查找其他原文"));
    await user.type(screen.getByLabelText("章节标题或原文"), "额外原文");
    await user.click(screen.getByRole("button", { name: "查找" }));
    expect(await screen.findByText("找到25处，本页20处")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("找到25处，本页5处")).toBeVisible();
    await user.click(screen.getAllByRole("radio")[0]);
    await user.click(screen.getByRole("button", { name: "添加到范围" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ source_span_ids: ["extra-21"], official_codes: ["IN-01"] }));
    expect(fetcher.mock.calls[1][0]).toContain("offset=20");
  });
});
