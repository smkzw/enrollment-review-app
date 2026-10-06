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
  it("将检索原文与采用事实分开，并拒绝无法回源的页码", async () => {
    const body = { ...reviewBody(), clauses: [{ ...reviewBody().clauses[0], source_read_refs: [{
      source_document_version_id: "document", page_artifact_id: "page", page_number: 2,
      excerpt: "明确否认示例事件史", disposition: "mentioned",
    }] }] };
    const repository = createEligibilityReviewHttp({ fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch });
    const decoded = await repository.getEligibilityReview("subject", "episode");
    expect(decoded.clauses[0]?.sourceReadRefs?.[0]).toEqual({ sourceDocumentVersionId: "document",
      pageArtifactId: "page", pageNumber: 2, excerpt: "明确否认示例事件史", disposition: "mentioned" });
    expect(decoded.clauses[0]?.factRefs).toHaveLength(1);
    body.clauses[0]!.source_read_refs[0]!.page_number = 0;
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
  });
  it.each(["source_changed", "method_changed"])("keeps a %s work draft distinct from an unstarted review", async (state) => {
    const body = { ...reviewBody(), work_draft_state: state };
    const repository = createEligibilityReviewHttp({ fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch });
    expect((await repository.getEligibilityReview("subject", "episode")).workDraftState).toBe(state);
    body.work_draft_state = "unknown";
    await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
  });
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

  it("keeps unresolved protocol meaning separate from missing investigator judgment", async () => {
    const body = reviewBody();
    Object.assign(body.clauses[0], {
      decision: "indeterminate", determination_mode: "restricted",
      reason: "方案原文中有这项要求，但适用对象尚未核清。",
      gap_type: null, fact_refs: [], action_owner: null,
      action_detail: null, action_evidence: null,
    });
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    const clause = (await repository.getEligibilityReview("subject", "episode")).clauses[0];
    expect(clause?.determinationMode).toBe("restricted");
    expect(clause?.actionOwner).toBeNull();
    expect(clause?.gapType).toBeNull();
    expect(clause?.limitationKind).toBeNull();
  });

  it.each(["interpretation_unresolved", "consumer_unavailable"])(
    "preserves the source-defined limitation kind %s without guessing from copy", async (kind) => {
      const body = reviewBody();
      Object.assign(body.clauses[0], {
        decision: "indeterminate", determination_mode: "restricted", limitation_kind: kind,
        gap_type: null, fact_refs: [], action_owner: null,
      });
      const repository = createEligibilityReviewHttp({
        fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
      });
      expect((await repository.getEligibilityReview("subject", "episode")).clauses[0]?.limitationKind).toBe(kind);
      Object.assign(body.clauses[0], { limitation_kind: "made_up" });
      await expect(repository.getEligibilityReview("subject", "episode")).rejects.toThrow(EligibilityReviewDecodeError);
    },
  );

  it("decodes a source-bound restricted control without treating it as missing case evidence", async () => {
    const body = {
      ...reviewBody(),
      controls: [{
        protocol_control_id: "restricted:unit-1", display_label: "方案补充要求",
        title: "基线前尚未核清的要求", source_span_ids: ["span:source-1"],
        obligations: [{
          obligation_id: "restricted:unit-1", obligation_group_id: "restricted",
          statement: "基线前尚未核清的要求", source_excerpts: ["基线前尚未核清的要求"],
          status: "restricted", status_label: "方案待澄清",
          limitation_kind: "interpretation_unresolved",
          reason: "适用范围尚未核清", fact_refs: [],
          action_owner: "sponsor_medical_or_project", action_detail: "请澄清适用范围",
          action_evidence: "方案书面澄清或正式修订",
        }],
      }],
    };
    const repository = createEligibilityReviewHttp({
      fetchImpl: (() => Promise.resolve(response(body))) as typeof fetch,
    });
    const item = (await repository.getEligibilityReview("subject", "episode")).controls[0]?.obligations[0];
    expect(item?.status).toBe("restricted");
    expect(item?.actionOwner).toBe("sponsor_medical_or_project");
    expect(item?.actionEvidence).toContain("方案书面澄清");
    expect(item?.limitationKind).toBe("interpretation_unresolved");
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
