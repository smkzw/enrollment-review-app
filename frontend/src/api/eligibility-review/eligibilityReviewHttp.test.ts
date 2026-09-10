import { describe, expect, it } from "vitest";
import {
  createEligibilityReviewHttp,
  EligibilityReviewDecodeError,
} from "./eligibilityReviewRepository";
function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function reviewBody() {
  return {
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    rule_set_id: "rule-set-1",
    rule_set_revision: 3,
    evidence_snapshot_v2_id: "snapshot-1",
    complete_processing_revision_id: "processing-1",
    clauses: [
      {
        rule_code: "IN-01",
        rule_kind: "inclusion",
        text_summary: "目标人群",
        parent_rule_code: null,
        decision: "professional_judgment",
        decision_label: "无法判定",
        reason: "需要研究者确认。",
        fact_refs: [{ fact_id: "fact-1", locator_id: null, page_number: null }],
        gap_type: "professional_judgment",
        determination_mode: "investigator_judgment",
      },
    ],
  };
}

describe("eligibility review HTTP repository", () => {
  it("requests the scoped endpoint and decodes nullable fact locations", async () => {
    let requested = "";
    const repository = createEligibilityReviewHttp({
      fetchImpl: ((input) => {
        requested = String(input);
        return Promise.resolve(response(reviewBody()));
      }) as typeof fetch,
    });
    const result = await repository.getEligibilityReview("subject 1", "episode/1");
    expect(requested).toBe(
      "/api/v2/subjects/subject%201/review-episodes/episode%2F1/eligibility-review",
    );
    expect(result.clauses[0]?.factRefs[0]?.pageNumber).toBeNull();
  });

  it("rejects unknown decision values instead of guessing a display state", async () => {
    const body = reviewBody();
    body.clauses[0].decision = "unknown";
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    await expect(
      repository.getEligibilityReview("subject-1", "episode-1"),
    ).rejects.toBeInstanceOf(EligibilityReviewDecodeError);
  });

  it("decodes API error envelopes", async () => {
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() =>
        Promise.resolve(
          response(
            {
              error: {
                code: "NOT_FOUND",
                title: "未找到",
                detail: "未找到这个审核节点。",
                recovery_action: "请重新选择。",
              },
            },
            404,
          ),
        )) as typeof fetch,
    });
    await expect(
      repository.getEligibilityReview("subject-1", "episode-1"),
    ).rejects.toMatchObject({
      code: "NOT_FOUND",
      statusCode: 404,
    });
  });
});
