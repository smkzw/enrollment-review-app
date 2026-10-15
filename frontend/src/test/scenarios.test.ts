/**
 * 场景数据测试：UAT 合同至少 10 个命名场景（本实现提供全部 14 项），
 * 每个场景的 id/文案/成功证据完整，且引用的 fixture 实体真实存在。
 */

import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../api/fixtureAssets";
import { UAT_SCENARIOS } from "../domain/scenarios";
import { precisionLabel } from "../domain/labels";
import { toId, type EvidenceSpanId } from "../domain/ids";

describe("UAT 场景数据", () => {
  it("提供至少 10 个命名场景（当前 14 项全量）", () => {
    expect(UAT_SCENARIOS.length).toBeGreaterThanOrEqual(10);
    expect(UAT_SCENARIOS.length).toBe(14);
  });

  it("场景 id 唯一且按 UAT-P1 编号对齐", () => {
    const ids = UAT_SCENARIOS.map((scenario) => scenario.id);
    expect(new Set(ids).size).toBe(ids.length);
    const uatIds = UAT_SCENARIOS.map((scenario) => scenario.uatId);
    expect(new Set(uatIds).size).toBe(uatIds.length);
    for (const scenario of UAT_SCENARIOS) {
      expect(scenario.uatId).toMatch(/^UAT-P1-\d{2}$/);
      expect(scenario.id).toBe(scenario.uatId.toLowerCase());
    }
  });

  it("每个场景文案完整：标题、任务、入口、成功证据", () => {
    for (const scenario of UAT_SCENARIOS) {
      expect(scenario.title.trim().length, scenario.id).toBeGreaterThan(0);
      expect(scenario.task.trim().length, scenario.id).toBeGreaterThan(0);
      expect(scenario.entrySurface.trim().length, scenario.id).toBeGreaterThan(
        0,
      );
      expect(scenario.acceptance.length, scenario.id).toBeGreaterThan(0);
      for (const item of scenario.acceptance) {
        expect(item.trim().length, scenario.id).toBeGreaterThan(0);
      }
    }
  });

  it("模拟行为明确标记为原型场景，不虚构后台完成", () => {
    for (const scenario of UAT_SCENARIOS) {
      expect(
        typeof scenario.prototypeOnly,
        scenario.id,
      ).toBe("boolean");
    }
    // 人工确认、任务恢复、批量与创建向导为本地演示
    for (const id of ["uat-p1-02", "uat-p1-10", "uat-p1-11", "uat-p1-12"]) {
      const scenario = UAT_SCENARIOS.find((item) => item.id === id);
      expect(scenario?.prototypeOnly, id).toBe(true);
    }
    // 纯查看类场景不依赖本地演示
    for (const id of ["uat-p1-01", "uat-p1-04", "uat-p1-07", "uat-p1-08"]) {
      const scenario = UAT_SCENARIOS.find((item) => item.id === id);
      expect(scenario?.prototypeOnly, id).toBe(false);
    }
  });

  it("关键证据目标精度合法且 ≤3 次操作可达", () => {
    for (const scenario of UAT_SCENARIOS) {
      const target = scenario.keyEvidence;
      if (target === null) continue;
      expect(target.maxClicksFromEntry, scenario.id).toBeLessThanOrEqual(3);
      expect(
        Object.prototype.hasOwnProperty.call(precisionLabel, target.precision),
        scenario.id,
      ).toBe(true);
      expect(target.pageNumber).toBeGreaterThan(0);
    }
  });

  it("引用的 episode/action/span/document 均存在于 workspace fixture", () => {
    const episodeIds = new Set(
      workspaceFixture.episodes.map(
        (episode) => episode.review_episode.review_episode_id,
      ),
    );
    const actionIds = new Set(
      workspaceFixture.episodes.flatMap((episode) =>
        episode.actions.map((action) => action.action_id),
      ),
    );
    const spanIds = new Set(
      workspaceFixture.episodes.flatMap((episode) =>
        episode.evidence_spans.map((span) => span.evidence_span_id),
      ),
    );
    const documentIds = new Set(
      workspaceFixture.episodes.flatMap((episode) =>
        episode.source_documents.map(
          (document) => document.source_document_version_id,
        ),
      ),
    );
    for (const scenario of UAT_SCENARIOS) {
      const refs = scenario.fixtureRefs;
      for (const id of refs.episodeIds) {
        expect(episodeIds.has(id), `${scenario.id}: episode ${id}`).toBe(true);
      }
      for (const id of refs.actionIds) {
        expect(actionIds.has(id), `${scenario.id}: action ${id}`).toBe(true);
      }
      for (const id of refs.spanIds) {
        expect(spanIds.has(id), `${scenario.id}: span ${id}`).toBe(true);
      }
      for (const id of refs.documentIds) {
        expect(documentIds.has(id), `${scenario.id}: document ${id}`).toBe(true);
      }
      if (scenario.keyEvidence !== null) {
        expect(
          spanIds.has(scenario.keyEvidence.spanId),
          `${scenario.id}: keyEvidence span`,
        ).toBe(true);
      }
    }
  });

  it("方案工作台场景引用真实 protocol_diff 变化（新增/删除/变化）", () => {
    const diff = workspaceFixture.protocol_diff;
    const scenario = UAT_SCENARIOS.find((item) => item.id === "uat-p1-03");
    expect(scenario?.fixtureRefs.usesProtocolDiff).toBe(true);
    expect(diff.added_rule_codes).toContain("EX-05");
    expect(diff.deleted_rule_codes).toContain("REQ-02");
    expect(diff.changed_logic_or_window_codes).toContain("EX-01");
  });

  it("四级定位场景覆盖 bbox/text_range/page_excerpt/page_only", () => {
    const scenario = UAT_SCENARIOS.find((item) => item.id === "uat-p1-08");
    const refs = scenario?.fixtureRefs.spanIds ?? [];
    expect(refs.length).toBeGreaterThanOrEqual(4);
    const precisions = new Set(
      workspaceFixture.episodes
        .flatMap((episode) => episode.evidence_spans)
        .filter((span) => refs.includes(toId<EvidenceSpanId>(span.evidence_span_id)))
        .map((span) => span.precision),
    );
    expect(precisions).toEqual(
      new Set(["bbox", "text_range", "page_excerpt", "page_only"]),
    );
  });
});
