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
