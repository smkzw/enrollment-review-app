import { describe, expect, it } from "vitest";
import { decodeTargetedReviewDetail } from "./targetedReviewHttp";

const status = { job_id: "job", state: "completed", status_label: "两轮复核后仍有分歧，请核对原件",
  round_budget: 2, rounds_with_receipts: 2, outcome: { candidate_auto_accept: false, clinical_findings_allowed: false } };
const evidence = { job_id: "job", file_name: "检验报告.pdf", page_number: 1,
  image_path: "/api/v2/evidence-processing-revisions/revision/pages/page/image", candidate_auto_accept: false,
  excerpts: [{ round_number: 2, read_number: 1, field_name: "白细胞计数", raw_value: "3.2", excerpt: "白细胞计数 3.2 ↓",
    target_text: null, time_text: "2026-08-01", location_text: null }] };

describe("原件复核详情合同", () => {
  it("保留原文和轮次，不生成正式事实", () => {
    const result = decodeTargetedReviewDetail(status, evidence, "job");
    expect(result.excerpts[0]).toMatchObject({ round: 2, reader: 1, value: "3.2", context: ["2026-08-01"] });
  });
  it.each([
    { candidate_auto_accept: true }, { job_id: "other" }, { image_path: "/unbound/image" },
    { excerpts: [{ ...evidence.excerpts[0], round_number: 3 }] },
  ])("拒绝越界或来源不一致的摘录 %j", (change) => {
    expect(() => decodeTargetedReviewDetail(status, { ...evidence, ...change }, "job")).toThrow();
  });
  it("拒绝带临床判断能力的辅助结果", () => {
    expect(() => decodeTargetedReviewDetail({ ...status, outcome: { candidate_auto_accept: false, clinical_findings_allowed: true } }, evidence, "job")).toThrow();
  });
});
