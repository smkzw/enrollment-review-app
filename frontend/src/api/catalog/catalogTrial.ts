/** 合成界面试用目录。只供组件测试和显式视觉试用构建使用。 */
import { createStubRepository } from "../stubRepository";
import type { CatalogRepository } from "./catalogRepository";
import { CatalogApiError } from "./catalogTypes";
import type { CatalogSubjectView } from "./catalogTypes";

export function createCatalogTrial(): CatalogRepository {
  const source = createStubRepository();
  const loadBoard = () => source.getBoard();
  // 试用人工程新增的受试者叠加层：让新增/删除在界面试用中可感知（不影响底稿）。
  const extraSubjects: CatalogSubjectView[] = [];
  let nextId = 1;

  return {
    kind: "trial",
    async listProjects() {
      const { project } = await loadBoard();
      return [{
        projectId: project.projectId,
        projectCode: project.projectCode,
        projectName: "界面试用项目",
        studyPhase: project.studyPhase as never,
        studyPhaseLabel: project.studyPhase === "phase_iii" ? "Ⅲ期" : project.studyPhase,
        protocolCode: project.projectCode,
        officialVersion: project.protocolVersion,
        officialDateValue: project.protocolOfficialDate,
        officialDatePrecision: "day",
        ruleSetId: project.ruleSetId,
        ruleSetRevision: 1,
      }];
    },
    async getProject(projectId) {
      const items = await this.listProjects();
      const project = items.find((item) => item.projectId === projectId);
      if (project === undefined) throw new CatalogApiError("未找到这个项目。", "请重新选择项目。");
      return project;
    },
    async listSubjects(projectId) {
      const board = await loadBoard();
      if (board.project.projectId !== projectId) return [];
      const seeded = board.subjects.map((item) => ({
        subjectId: item.subjectId,
        subjectCode: item.subjectCode,
        projectId,
        centerCode: item.centerCode,
        centerName: item.centerName,
        sex: item.sex,
        ageYears: item.ageYears,
        revision: 1,
      }));
      return [...seeded, ...extraSubjects];
    },
    async getSubject(subjectId) {
      const board = await loadBoard();
      const item =
        extraSubjects.find((candidate) => candidate.subjectId === subjectId) ??
        board.subjects.find((candidate) => candidate.subjectId === subjectId);
      if (item === undefined) throw new CatalogApiError("未找到这个受试者。", "请重新选择受试者。");
      const extra = extraSubjects.find((candidate) => candidate.subjectId === subjectId);
      if (extra !== undefined) return extra;
      return {
        subjectId: item.subjectId,
        subjectCode: item.subjectCode,
        projectId: board.project.projectId,
        centerCode: item.centerCode,
        centerName: item.centerName,
        sex: item.sex,
        ageYears: item.ageYears,
        revision: 1,
      };
    },
    async createSubject(projectId, input) {
      const project = await this.getProject(projectId);
      const existing = await this.listSubjects(projectId);
      if (existing.some((subject) => subject.subjectCode === input.subjectCode)) {
        throw new CatalogApiError(
          `该项目已存在受试者代号 ${input.subjectCode}。`,
          "请更换受试者代号后重试；本次新增没有生效。",
        );
      }
      const created: CatalogSubjectView = {
        subjectId: `trial-subject-${nextId++}`,
        subjectCode: input.subjectCode,
        projectId: project.projectId,
        centerCode: input.centerCode ?? null,
        centerName: input.centerName ?? null,
        sex: input.sex ?? null,
        ageYears: input.ageYears ?? null,
        revision: 1,
      };
      extraSubjects.push(created);
      return created;
    },
    async deleteSubject(_projectId, subjectId) {
      const index = extraSubjects.findIndex((subject) => subject.subjectId === subjectId);
      if (index >= 0) {
        const [removed] = extraSubjects.splice(index, 1);
        return removed;
      }
      const board = await loadBoard();
      const isSeeded = board.subjects.some((item) => item.subjectId === subjectId);
      if (isSeeded) {
        throw new CatalogApiError(
          "该受试者已纳入审核安排。",
          "已建立审核节点或资料的受试者不能删除。",
        );
      }
      throw new CatalogApiError("未找到这个受试者。", "请刷新列表后重试。");
    },
    async listEpisodes(subjectId) {
      const board = await loadBoard();
      return board.episodes
        .filter((item) => item.subjectId === subjectId)
        .map((item) => ({
          reviewEpisodeId: item.episodeId,
          subjectId: item.subjectId,
          projectId: board.project.projectId,
          ruleSetId: board.project.ruleSetId,
          studyPhase: board.project.studyPhase,
          studyPhaseLabel: board.project.studyPhase === "phase_iii" ? "Ⅲ期" : board.project.studyPhase,
          stage: item.stage,
          stageLabel: item.stageLabel,
          protocolVersionId: board.project.protocolVersion,
          ruleSetRevision: 1,
          evidenceSnapshotId: item.evidenceSnapshotId,
          workflowStageId: null,
          workflowStageLabel: item.stageLabel,
          visitWindow: null,
          latestEvidenceSnapshotId: item.evidenceSnapshotId,
          activeEvidenceSnapshotId: item.evidenceSnapshotId,
          activeEvidenceProcessingRevisionId: null,
          anchorDates: {},
          dueAt: null,
          revision: item.revision,
        }));
    },
    async getEvidenceContext(subjectId, reviewEpisodeId) {
      const subject = await this.getSubject(subjectId);
      const [project, episodes] = await Promise.all([
        this.getProject(subject.projectId),
        this.listEpisodes(subjectId),
      ]);
      const episode = episodes.find((item) => item.reviewEpisodeId === reviewEpisodeId);
      if (episode === undefined) throw new CatalogApiError("未找到这个审核节点。", "请重新选择审核节点。");
      return { project, subject, episode };
    },
  };
}
