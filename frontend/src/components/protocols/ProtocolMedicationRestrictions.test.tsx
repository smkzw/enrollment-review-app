// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { decodeScopeSupplement } from "../../api/protocolMedications";
import { ProtocolMedicationRestrictions } from "./ProtocolMedicationRestrictions";

function supplement() {
  return { selection_sha256: "a".repeat(64), input_sha256: "b".repeat(64), structure_sha256: "c".repeat(64),
    sources: [{ source_span_id: "source-hidden", excerpt: "筛选前4周内禁止使用药物甲。" }], source_dispositions: [],
    medications: [{ item_id: "med:" + "d".repeat(24), drug_text: "药物甲", drug_class_id: null, period: null,
      window: { anchor_type: "screening_date", direction: "before", lower_bound_days: null, upper_bound_days: null,
        lower_bound: null, upper_bound: { value: 4, unit: "week" }, lower_bound_inclusive: true, upper_bound_inclusive: true,
        half_life_multiplier: null, allow_partial_date: false }, applicable_stages: ["screening"],
      exception_excerpt: null, unresolved_reason: null, applies_to_rule: null,
      source_quotes: [{ source_span_id: "source-hidden", excerpt: "筛选前4周内禁止使用药物甲。" }] }] };
}
afterEach(() => vi.unstubAllGlobals());

it("只在操作后请求，用来源提案保存，不伪装批准或发布", async () => {
  const user = userEvent.setup();
  const saved = vi.fn();
  const calls = vi.fn(async (_url: string, options: RequestInit) => {
    const body = JSON.parse(String(options.body));
    expect(body.expected_revision_id).toBe("revision");
    if (options.method === "POST") return new Response(JSON.stringify({ job_id: "job", draft_revision_id: "revision", supplement: supplement(), proposal_ref: "receipt" }));
    expect(body.proposal.medications[0]).not.toHaveProperty("item_id");
    expect(body.proposal.medications[0].window.upper_bound).toEqual({ value: 4, unit: "week" });
    return new Response(JSON.stringify({ revision_id: "next-revision" }));
  });
  vi.stubGlobal("fetch", calls);
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{}} drugClasses={{}} onSaved={saved} />);
  expect(calls).not.toHaveBeenCalled();
  await user.click(screen.getByText("用药与伴随治疗限制"));
  await user.click(screen.getByRole("button", { name: "整理选定章节" }));
  expect(await screen.findByText(/本次建议尚未保存/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "保存补充要求" }));
  expect(saved).toHaveBeenCalledOnce();
  expect(screen.queryByRole("button", { name: /批准|发布/ })).not.toBeInTheDocument();
  expect(screen.queryByText("source-hidden")).not.toBeInTheDocument();
});

it("已存条目可下钻和调整时间阶段，来源始终只读，不暴露内部编号", async () => {
  const user = userEvent.setup();
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{ scope_supplement: supplement() }} drugClasses={{}} onSaved={vi.fn()} />);
  await user.click(screen.getByText(/用药与伴随治疗限制/));
  await user.click(await screen.findByText(/药物甲 ·/));
  expect(screen.getByLabelText("最长间隔")).toHaveValue(4);
  await user.clear(screen.getByLabelText("最长间隔"));
  await user.type(screen.getByLabelText("最长间隔"), "3");
  expect(screen.getByRole("button", { name: "保存补充要求" })).toBeEnabled();
  const stages = screen.getByRole("group", { name: "适用审核阶段" });
  await user.click(within(stages).getByLabelText("基线"));
  expect(within(stages).getByLabelText("基线")).toBeChecked();
  await user.click(screen.getByText("原文依据"));
  expect(screen.getByText("筛选前4周内禁止使用药物甲。")).toBeVisible();
  expect(screen.queryByDisplayValue("筛选前4周内禁止使用药物甲。")).not.toBeInTheDocument();
});

it("来源版本或阶段格式不合法时拒绝展示，不默认为已完成", () => {
  expect(() => decodeScopeSupplement({ ...supplement(), structure_sha256: "invalid" })).toThrow();
  const invalid = supplement(); invalid.medications[0].applicable_stages = ["not-a-stage"];
  expect(() => decodeScopeSupplement(invalid)).toThrow();
});

it("旧时间窗不猜含义，选择后随现有保存入口提交，切换期间清除旧含义", async () => {
  const user = userEvent.setup();
  const request = vi.fn(async (_url: string, options: RequestInit) => {
    const value = JSON.parse(String(options.body)).proposal.medications[0];
    expect(value.window_interpretation).toBe("prohibited_interval");
    expect(value.window.upper_bound).toEqual({ value: 4, unit: "week" });
    return new Response(JSON.stringify({ revision_id: "next" }));
  });
  vi.stubGlobal("fetch", request);
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{ scope_supplement: supplement() }} drugClasses={{}} onSaved={vi.fn()} />);
  await user.click(screen.getByText(/用药与伴随治疗限制/));
  await user.click(await screen.findByText(/药物甲 ·/));
  expect(screen.getByLabelText("时间要求")).toHaveValue("");
  await user.selectOptions(screen.getByLabelText("时间要求"), "prohibited_interval");
  await user.click(screen.getByRole("button", { name: "保存补充要求" }));
  expect(request).toHaveBeenCalledOnce();
  await user.selectOptions(screen.getByLabelText("适用期间"), "study_period");
  expect(screen.queryByLabelText("时间要求")).not.toBeInTheDocument();
});

it("读取失败仍能从已选原文手工整理，不把失败回执附给手工要求", async () => {
  const user = userEvent.setup();
  const manual = { ...supplement(), medications: [], source_dispositions: [{ source_span_id: "source-hidden", disposition: "unresolved", reason: "尚未整理" }] };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ job_id: "job", draft_revision_id: "revision",
    supplement: null, manual_supplement: manual, system_issue: "原答尚未通过核对", proposal_ref: "failed-receipt" }))));
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{}} drugClasses={{}} onSaved={vi.fn()} />);
  await user.click(screen.getByText("用药与伴随治疗限制"));
  await user.click(screen.getByRole("button", { name: "整理选定章节" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("原答尚未通过核对");
  await user.click(screen.getByText(/其余所选原文的处置/));
  expect(screen.getByRole("button", { name: "从此段新增限制" })).toBeVisible();
});

it("移除错误提案仍保留原文未决，能从该段补回限制，不要求手写JSON", async () => {
  const user = userEvent.setup();
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{ scope_supplement: supplement() }} drugClasses={{}} onSaved={vi.fn()} />);
  await user.click(screen.getByText(/用药与伴随治疗限制/));
  await user.click(await screen.findByText(/药物甲 ·/));
  await user.click(screen.getByRole("button", { name: "移除此项，保留原文" }));
  await user.click(screen.getByText(/其余所选原文的处置/));
  expect(screen.getByText("提案已移除，此段是否包含限制仍待核对。")).toBeVisible();
  await user.click(screen.getByText("调整这段的处理方式"));
  await user.selectOptions(screen.getByLabelText("原文性质"), "permission");
  await user.clear(screen.getByLabelText("处理说明"));
  await user.type(screen.getByLabelText("处理说明"), "需同时核对剂量限制。");
  expect(screen.getByLabelText("处理说明")).toHaveValue("需同时核对剂量限制。");
  await user.click(screen.getByRole("button", { name: "从此段新增限制" }));
  await user.click(screen.getByText(/新增用药限制 ·/));
  expect(screen.getByLabelText("药物或治疗原文")).toHaveValue("");
  await user.type(screen.getByLabelText("药物或治疗原文"), "药物甲");
  expect(screen.getByLabelText("尚未核清的内容")).toHaveValue("适用时间与例外尚待核清");
});

it("从已选方案原文补充共同例外，保存真实引用且不重读或自动批准", async () => {
  const user = userEvent.setup();
  const content = supplement();
  const exception = { source_span_id: "exception-source-hidden", excerpt: "研究者评估后可以使用原本禁用的药物进行补救治疗。" };
  content.sources.push(exception);
  const sibling = { ...content.medications[0], item_id: "med:" + "e".repeat(24), drug_text: "药物乙" };
  content.medications.push(sibling);
  const saved = vi.fn();
  const request = vi.fn(async (_url: string, options: RequestInit) => {
    expect(options.method).toBe("PUT");
    const body = JSON.parse(String(options.body));
    expect(body.expected_revision_id).toBe("revision");
    expect(body.proposal.medications[0].source_quotes).toEqual([content.sources[0], exception]);
    expect(body.proposal.medications[0].exception_excerpt).toBe(exception.excerpt);
    expect(body.proposal.medications[1].source_quotes).toEqual(sibling.source_quotes);
    return new Response(JSON.stringify({ revision_id: "next" }));
  });
  vi.stubGlobal("fetch", request);
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{ scope_supplement: content }} drugClasses={{}} onSaved={saved} />);
  await user.click(screen.getByText(/用药与伴随治疗限制/));
  await user.click(await screen.findByText(/药物甲 ·/));
  await user.click(screen.getAllByText("补充或调整方案依据")[0]);
  const picker = screen.getAllByRole("group", { name: "选择本条依据" })[0];
  expect(within(picker).getByRole("checkbox", { name: content.sources[0].excerpt })).toBeDisabled();
  await user.type(screen.getAllByLabelText("查找方案原文")[0], "补救");
  expect(within(picker).queryByRole("checkbox", { name: content.sources[0].excerpt })).not.toBeInTheDocument();
  await user.click(within(picker).getByRole("checkbox", { name: exception.excerpt }));
  await user.type(screen.getAllByLabelText("例外原文")[0], exception.excerpt);
  expect(request).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "保存补充要求" }));
  expect(request).toHaveBeenCalledOnce();
  expect(saved).toHaveBeenCalledOnce();
  expect(screen.queryByText("exception-source-hidden")).not.toBeInTheDocument();
});

it("取消补充引用不改原文，不允许移除最后一处依据，查无结果仍可调整查询", async () => {
  const user = userEvent.setup();
  const content = supplement();
  content.sources.push({ source_span_id: "context", excerpt: "此限制只在完成前置条件后适用。" });
  render(<ProtocolMedicationRestrictions jobId="job" revisionId="revision" content={{ scope_supplement: content }} drugClasses={{}} onSaved={vi.fn()} />);
  await user.click(screen.getByText(/用药与伴随治疗限制/));
  await user.click(await screen.findByText(/药物甲 ·/));
  await user.click(screen.getByText("补充或调整方案依据"));
  const picker = screen.getByRole("group", { name: "选择本条依据" });
  const extra = within(picker).getByRole("checkbox", { name: content.sources[1].excerpt });
  await user.click(extra);
  expect(extra).toBeChecked();
  await user.click(extra);
  expect(extra).not.toBeChecked();
  expect(within(picker).getByRole("checkbox", { name: content.sources[0].excerpt })).toBeDisabled();
  await user.type(screen.getByLabelText("查找方案原文"), "不存在的段落");
  expect(within(picker).getByText("没有找到相应原文。")).toBeVisible();
  await user.clear(screen.getByLabelText("查找方案原文"));
  expect(within(picker).getAllByRole("checkbox")).toHaveLength(2);
});
