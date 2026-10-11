// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  });

  it("显示对应提示，明确验证身份，并用内容与修订核对保存", async () => {
    const onReady = vi.fn();
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(initial)));
    fetcher.mockImplementationOnce(async (_url, options) => {
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
    await screen.findByText("提醒：请核对年龄依据");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    expect(screen.getByText(/不能代替医学经理正式审定/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "审定通过" }));
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(true));
    expect(screen.getByRole("button", { name: "撤销审定" })).toBeEnabled();
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
    expect(fetcher.mock.calls.every(([url, options]) => String(url).endsWith("/draft/reviews") && options.method === "GET")).toBe(true);
    expect(screen.getByRole("button", { name: "发布" })).toBeDisabled();
  });
});
