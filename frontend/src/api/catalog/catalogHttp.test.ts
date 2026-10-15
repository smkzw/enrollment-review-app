import { describe, expect, it, vi } from "vitest";
import { createCatalogHttp } from "./catalogHttp";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const project = {
  project_id: "project-real",
  project_code: "SAR-III",
  project_name: "季节性过敏性鼻炎研究",
  study_phase: "phase_iii",
  study_phase_label: "Ⅲ期",
  protocol_code: "MG-K10-SAR-001",
  official_version: "V2.1",
  official_date_value: "2025-09-19",
  official_date_precision: "day",
  rule_set_id: "rules-real",
  rule_set_revision: 2,
};

const subject = {
  subject_id: "subject-real",
  subject_code: "31001",
  project_id: "project-real",
  center_code: "31",
  center_name: "河北省中医院",
  sex: "男",
  age_years: 36,
  revision: 1,
};

const episode = {
  review_episode_id: "episode-screening",
  subject_id: "subject-real",
  project_id: "project-real",
  rule_set_id: "rules-real",
  study_phase: "phase_iii",
  study_phase_label: "Ⅲ期",
  stage: "screening",
  stage_label: "筛选期",
  protocol_version_id: "protocol-v21",
  rule_set_revision: 2,
  evidence_snapshot_id: "snapshot-initial",
  workflow_stage_id: "rules-real:2:stage-screening",
  workflow_stage_label: "筛选期审核",
  visit_window: "第1天",
  latest_evidence_snapshot_id: "snapshot-uploaded",
  active_evidence_snapshot_id: null,
  active_evidence_processing_revision_id: null,
  anchor_dates: {},
  due_at: null,
  revision: 1,
};

describe("正式项目资料目录", () => {
  it("按真实受试者与审核节点读取证据上下文，不依赖演示看板", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/protocol/projects")) return json({ projects: [project] });
      if (url.endsWith("/api/v2/projects/project-real/subjects")) {
        return json({ project_id: "project-real", items: [subject] });
      }
      if (url.endsWith("/api/v2/protocol/projects/project-real")) {
        return json({ project, versions: [], publication_count: 1 });
      }
      if (url.endsWith("/api/v2/subjects/subject-real/review-episodes")) {
        return json({ subject_id: "subject-real", items: [episode] });
      }
      throw new Error(`unexpected ${url}`);
    });
    const context = await createCatalogHttp(fetchImpl as typeof fetch)
      .getEvidenceContext("subject-real", "episode-screening");

    expect(context.project.projectName).toBe("季节性过敏性鼻炎研究");
    expect(context.subject.subjectCode).toBe("31001");
    expect(context.episode.stageLabel).toBe("筛选期");
    expect(context.episode.latestEvidenceSnapshotId).toBe("snapshot-uploaded");
    expect(fetchImpl).toHaveBeenCalledTimes(4);
  });

  it("多个项目只返回目录，不擅自选择其中一个", async () => {
    const fetchImpl = vi.fn(async () => json({ projects: [project, { ...project, project_id: "project-two" }] }));
    const items = await createCatalogHttp(fetchImpl as typeof fetch).listProjects();
    expect(items.map((item) => item.projectId)).toEqual(["project-real", "project-two"]);
  });

  it("审核节点不属于受试者时明确拒绝，不串用其他节点", async () => {    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/protocol/projects")) return json({ projects: [project] });
      if (url.endsWith("/api/v2/projects/project-real/subjects")) {
        return json({ project_id: "project-real", items: [subject] });
      }
      if (url.endsWith("/api/v2/protocol/projects/project-real")) {
        return json({ project, versions: [], publication_count: 1 });
      }
      return json({ subject_id: "subject-real", items: [episode] });
    });
    await expect(
      createCatalogHttp(fetchImpl as typeof fetch).getEvidenceContext("subject-real", "episode-other"),
    ).rejects.toThrow("未找到这个审核节点");
  });

  it("新增受试者以中文内容 POST 并映射返回的受试者", async () => {
    const created = { ...subject, subject_id: "subject-new", subject_code: "S-2026-101" };
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({
        subject_code: "S-2026-101",
        center_code: "31",
        center_name: "河北省中医院",
        sex: "男",
        age_years: 36,
      });
      return json(created, 201);
    });
    const view = await createCatalogHttp(fetchImpl as typeof fetch).createSubject("project-real", {
      subjectCode: "S-2026-101",
      centerCode: "31",
      centerName: "河北省中医院",
      sex: "男",
      ageYears: 36,
    });
    expect(view.subjectId).toBe("subject-new");
    expect(view.subjectCode).toBe("S-2026-101");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("删除受试者发送 DELETE 并映射返回的受试者", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      expect(init?.method).toBe("DELETE");
      expect(url).toContain("/api/v2/projects/project-real/subjects/subject-real");
      return json(subject);
    });
    const view = await createCatalogHttp(fetchImpl as typeof fetch).deleteSubject("project-real", "subject-real");
    expect(view.subjectCode).toBe("31001");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("重复受试者代号返回 409 并给出中文恢复动作", async () => {
    const fetchImpl = vi.fn(async () =>
      json({
        error: {
          code: "DUPLICATE_RECORD",
          title: "记录已存在",
          detail: "项目 project-real 已存在受试者代号 S-2026-101",
          recovery_action: "请使用现有记录，或更换唯一标识后重试。",
          correlation_id: "a".repeat(32),
          context: null,
        },
      }, 409),
    );
    await expect(
      createCatalogHttp(fetchImpl as typeof fetch).createSubject("project-real", {
        subjectCode: "S-2026-101",
      }),
    ).rejects.toMatchObject({
      name: "CatalogApiError",
      message: "项目 project-real 已存在受试者代号 S-2026-101",
      recoveryAction: "请使用现有记录，或更换唯一标识后重试。",
    });
  });

  it("自动建立的空节点可空 evidence_snapshot_id 且投影流程节点身份", async () => {
    const autoEpisode = {
      ...episode,
      evidence_snapshot_id: null,
      workflow_stage_id: "rules-real:2:stage-screening-d1",
      workflow_stage_label: "筛选 D1 审核",
      visit_window: "第1天",
    };
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/subjects/subject-real/review-episodes")) {
        return json({ subject_id: "subject-real", items: [autoEpisode] });
      }
      throw new Error(`unexpected ${url}`);
    });
    const items = await createCatalogHttp(fetchImpl as typeof fetch).listEpisodes("subject-real");
    expect(items).toHaveLength(1);
    const view = items[0];
    expect(view.evidenceSnapshotId).toBeNull();
    expect(view.workflowStageId).toBe("rules-real:2:stage-screening-d1");
    expect(view.workflowStageLabel).toBe("筛选 D1 审核");
    expect(view.visitWindow).toBe("第1天");
  });
});
