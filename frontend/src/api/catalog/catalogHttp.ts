import { getProtocolApiBase } from "../protocolApiConfig";
import type { CatalogRepository } from "./catalogRepository";
import {
  CatalogApiError,
  type CatalogEpisodeView,
  type CatalogProjectView,
  type CatalogSubjectView,
  type EvidenceContextView,
} from "./catalogTypes";

type ObjectValue = Record<string, unknown>;

function objectValue(value: unknown): ObjectValue {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new CatalogApiError(
      "系统没有读到完整的项目资料。",
      "请稍后重试；若仍无法读取，请重新启动系统。",
    );
  }
  return value as ObjectValue;
}

function textValue(source: ObjectValue, key: string): string {
  const value = source[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new CatalogApiError(
      "项目资料中有必要信息缺失。",
      "请回到方案工作台确认项目是否已经保存完成。",
    );
  }
  return value;
}

function nullableText(source: ObjectValue, key: string): string | null {
  const value = source[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(source: ObjectValue, key: string): number {
  const value = source[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new CatalogApiError("项目资料中有必要信息缺失。", "请稍后重试。");
  }
  return value;
}

function phaseLabel(phase: string, supplied: string): string {
  const labels: Record<string, string> = {
    phase_i: "Ⅰ期",
    phase_ii: "Ⅱ期",
    phase_iii: "Ⅲ期",
    phase_iv: "Ⅳ期",
  };
  return labels[phase] ?? supplied;
}

function projectOf(value: unknown): CatalogProjectView {
  const item = objectValue(value);
  const studyPhase = textValue(item, "study_phase");
  return {
    projectId: textValue(item, "project_id"),
    projectCode: textValue(item, "project_code"),
    projectName: textValue(item, "project_name"),
    studyPhase: studyPhase as CatalogProjectView["studyPhase"],
    studyPhaseLabel: phaseLabel(studyPhase, textValue(item, "study_phase_label")),
    protocolCode: textValue(item, "protocol_code"),
    officialVersion: textValue(item, "official_version"),
    officialDateValue: nullableText(item, "official_date_value"),
    officialDatePrecision: nullableText(item, "official_date_precision") as CatalogProjectView["officialDatePrecision"],
    ruleSetId: textValue(item, "rule_set_id"),
    ruleSetRevision: numberValue(item, "rule_set_revision"),
  };
}

function subjectOf(value: unknown): CatalogSubjectView {
  const item = objectValue(value);
  const age = item.age_years;
  return {
    subjectId: textValue(item, "subject_id"),
    subjectCode: textValue(item, "subject_code"),
    projectId: textValue(item, "project_id"),
    centerCode: nullableText(item, "center_code"),
    centerName: nullableText(item, "center_name"),
    sex: nullableText(item, "sex"),
    ageYears: typeof age === "number" && Number.isFinite(age) ? age : null,
    revision: numberValue(item, "revision"),
  };
}

function episodeOf(value: unknown): CatalogEpisodeView {
  const item = objectValue(value);
  const anchors = item.anchor_dates;
  const studyPhase = textValue(item, "study_phase");
  return {
    reviewEpisodeId: textValue(item, "review_episode_id"),
    subjectId: textValue(item, "subject_id"),
    projectId: textValue(item, "project_id"),
    ruleSetId: textValue(item, "rule_set_id"),
    studyPhase,
    studyPhaseLabel: phaseLabel(studyPhase, textValue(item, "study_phase_label")),
    stage: textValue(item, "stage"),
    stageLabel: textValue(item, "stage_label"),
    protocolVersionId: textValue(item, "protocol_version_id"),
    ruleSetRevision: numberValue(item, "rule_set_revision"),
    evidenceSnapshotId: nullableText(item, "evidence_snapshot_id"),
    workflowStageId: nullableText(item, "workflow_stage_id"),
    workflowStageLabel: nullableText(item, "workflow_stage_label"),
    visitWindow: nullableText(item, "visit_window"),
    latestEvidenceSnapshotId: nullableText(item, "latest_evidence_snapshot_id"),
    activeEvidenceSnapshotId: nullableText(item, "active_evidence_snapshot_id"),
    activeEvidenceProcessingRevisionId: nullableText(item, "active_evidence_processing_revision_id"),
    anchorDates:
      typeof anchors === "object" && anchors !== null && !Array.isArray(anchors)
        ? (anchors as Record<string, unknown>)
        : {},
    dueAt: nullableText(item, "due_at"),
    revision: numberValue(item, "revision"),
  };
}

async function readResponse(response: Response): Promise<unknown> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // 统一在下方转换为面向使用者的说明。
  }
  if (!response.ok) {
    const envelope = typeof payload === "object" && payload !== null ? payload as ObjectValue : {};
    const error = typeof envelope.error === "object" && envelope.error !== null ? envelope.error as ObjectValue : {};
    throw new CatalogApiError(
      typeof error.detail === "string" ? error.detail : "暂时无法读取这部分资料。",
      typeof error.recovery_action === "string" ? error.recovery_action : "请稍后重试。",
    );
  }
  return payload;
}

export function createCatalogHttp(fetchImpl: typeof fetch = fetch.bind(globalThis)): CatalogRepository {
  const url = (path: string) => `${getProtocolApiBase()}${path}`;
  const get = async (path: string, signal?: AbortSignal) =>
    readResponse(await fetchImpl(url(path), { method: "GET", signal }));
  const post = async (path: string, body: unknown, signal?: AbortSignal) =>
    readResponse(
      await fetchImpl(url(path), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      }),
    );
  const del = async (path: string, signal?: AbortSignal) =>
    readResponse(await fetchImpl(url(path), { method: "DELETE", signal }));

  return {
    kind: "http",
    async listProjects(signal) {
      const payload = objectValue(await get("/api/v2/protocol/projects", signal));
      if (!Array.isArray(payload.projects)) return [];
      return payload.projects.map(projectOf);
    },
    async getProject(projectId, signal) {
      const payload = objectValue(await get(`/api/v2/protocol/projects/${encodeURIComponent(projectId)}`, signal));
      return projectOf(payload.project);
    },
    async listSubjects(projectId, signal) {
      const payload = objectValue(await get(`/api/v2/projects/${encodeURIComponent(projectId)}/subjects`, signal));
      if (!Array.isArray(payload.items)) return [];
      return payload.items.map(subjectOf);
    },
    async getSubject(subjectId, signal) {
      const projects = await this.listProjects(signal);
      const subjectLists = await Promise.all(
        projects.map((project) => this.listSubjects(project.projectId, signal)),
      );
      const matches = subjectLists.flat().filter((subject) => subject.subjectId === subjectId);
      if (matches.length === 0) {
        throw new CatalogApiError("未找到这个受试者。", "请从受试者资料页重新选择。");
      }
      if (matches.length > 1) {
        throw new CatalogApiError(
          "这个受试者在多个项目中出现，系统无法确认应打开哪一份资料。",
          "请回到受试者资料页，先选择项目后再进入审核节点。",
        );
      }
      return matches[0];
    },
    async createSubject(projectId, input, signal) {
      const payload = objectValue(
        await post(
          `/api/v2/projects/${encodeURIComponent(projectId)}/subjects`,
          {
            subject_code: input.subjectCode,
            center_code: input.centerCode ?? null,
            center_name: input.centerName ?? null,
            sex: input.sex ?? null,
            age_years: input.ageYears ?? null,
          },
          signal,
        ),
      );
      return subjectOf(payload);
    },
    async deleteSubject(projectId, subjectId, signal) {
      const payload = objectValue(
        await del(
          `/api/v2/projects/${encodeURIComponent(projectId)}/subjects/${encodeURIComponent(subjectId)}`,
          signal,
        ),
      );
      return subjectOf(payload);
    },
    async listEpisodes(subjectId, signal) {
      const payload = objectValue(await get(`/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes`, signal));
      if (!Array.isArray(payload.items)) return [];
      return payload.items.map(episodeOf);
    },
    async getEvidenceContext(subjectId, reviewEpisodeId, signal): Promise<EvidenceContextView> {
      const subject = await this.getSubject(subjectId, signal);
      const [project, episodes] = await Promise.all([
        this.getProject(subject.projectId, signal),
        this.listEpisodes(subjectId, signal),
      ]);
      const episode = episodes.find((item) => item.reviewEpisodeId === reviewEpisodeId);
      if (episode === undefined) {
        throw new CatalogApiError(
          "未找到这个审核节点。",
          "请从受试者资料页重新选择审核节点。",
        );
      }
      return { project, subject, episode };
    },
  };
}
