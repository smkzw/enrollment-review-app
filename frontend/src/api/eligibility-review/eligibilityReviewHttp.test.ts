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
        rule_component_id: "component-in-01",
        rule_kind: "inclusion",
        text_summary: "目标人群",
        parent_rule_code: null,
        decision: "professional_judgment",
        decision_label: "无法判定",
        reason: "需要研究者确认。",
        fact_refs: [{ fact_id: "fact-1", excerpt: null, locator_id: null, page_number: null, source_document_version_id: null, page_artifact_id: null }],
        gap_type: "professional_judgment",
        action_owner: "investigator",
        action_detail: "研究者针对本条要求作出并记录明确的临床判断。",
        action_evidence: "具名、具日期并直接关联本条要求的研究者判断。",
        determination_mode: "investigator_judgment",
      },
    ],
  };
}

describe("eligibility review HTTP repository", () => {
  it("preserves unresolved entity conflicts without assigning clause gaps", async () => {
    const body = { ...reviewBody(), unassigned_conflicts: [{ conflict_group_id: "group", member_kind: "event", member_ids: ["a", "b"] }] };
    const repository = createEligibilityReviewHttp({ fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch });
    const decoded = await repository.getEligibilityReview("subject", "episode");
    expect(decoded.unassignedConflicts).toEqual([{ conflictGroupId: "group", memberKind: "event", memberIds: ["a", "b"] }]);
    expect(decoded.clauses[0]?.gapType).toBe("professional_judgment");
    expect(decoded.clauses[0]?.actionOwner).toBe("investigator");
    expect(decoded.clauses[0]?.actionDetail).toContain("临床判断");
    expect(decoded.clauses[0]?.actionEvidence).toContain("具名");
    body.unassigned_conflicts.push({ ...body.unassigned_conflicts[0] });
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow("争议记录重复");
    body.unassigned_conflicts.pop();
    body.unassigned_conflicts[0].member_ids = ["a", "a"];
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
    body.unassigned_conflicts[0].member_ids = ["a", "b"];
    body.unassigned_conflicts[0].member_kind = "fact";
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
  });
  it("preserves source text separately and never substitutes a legacy summary", async () => {
    const body = reviewBody();
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    expect((await repository.getEligibilityReview("subject", "episode")).clauses[0]?.sourceText).toBeNull();
    Object.assign(body.clauses[0], { source_text: "完整原文\n包括例外条件。" });
    const clause = (await repository.getEligibilityReview("subject", "episode")).clauses[0];
    expect(clause?.sourceText).toBe("完整原文\n包括例外条件。");
    expect(clause?.textSummary).toBe("目标人群");
    Object.assign(body.clauses[0], { source_text: 42 });
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
  });
  it("allows repeated official codes only with distinct component identities", async () => {
    const body = reviewBody();
    body.clauses.push({ ...body.clauses[0], rule_component_id: "component-in-01-b" });
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    const result = await repository.getEligibilityReview("subject", "episode");
    expect(result.clauses.map((clause) => clause.ruleComponentId)).toEqual([
      "component-in-01", "component-in-01-b",
    ]);
    body.clauses[1].rule_component_id = body.clauses[0].rule_component_id;
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow("审核要点重复");
  });

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

  it("preserves insufficient evidence separately from investigator judgment", async () => {
    const body = reviewBody();
    body.clauses[0].decision = "indeterminate";
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    const result = await repository.getEligibilityReview("subject", "episode");
    expect(result.clauses[0]?.decision).toBe("indeterminate");
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
