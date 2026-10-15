import { createCatalogHttp } from "./catalogHttp";
import type {
  CatalogEpisodeView,
  CatalogProjectView,
  CatalogSubjectView,
  EvidenceContextView,
  SubjectCreateInput,
} from "./catalogTypes";

export interface CatalogRepository {
  readonly kind: "http" | "trial";
  listProjects(signal?: AbortSignal): Promise<ReadonlyArray<CatalogProjectView>>;
  getProject(projectId: string, signal?: AbortSignal): Promise<CatalogProjectView>;
  listSubjects(projectId: string, signal?: AbortSignal): Promise<ReadonlyArray<CatalogSubjectView>>;
  getSubject(subjectId: string, signal?: AbortSignal): Promise<CatalogSubjectView>;
  createSubject(projectId: string, input: SubjectCreateInput, signal?: AbortSignal): Promise<CatalogSubjectView>;
  deleteSubject(projectId: string, subjectId: string, signal?: AbortSignal): Promise<CatalogSubjectView>;
  listEpisodes(subjectId: string, signal?: AbortSignal): Promise<ReadonlyArray<CatalogEpisodeView>>;
  getEvidenceContext(subjectId: string, reviewEpisodeId: string, signal?: AbortSignal): Promise<EvidenceContextView>;
}

let defaultRepository: CatalogRepository | null = null;

export function getCatalogRepository(): CatalogRepository {
  if (defaultRepository === null) defaultRepository = createCatalogHttp();
  return defaultRepository;
}

export function setCatalogRepository(repository: CatalogRepository | null): void {
  defaultRepository = repository;
}

export { createCatalogHttp };
export { createCatalogTrial } from "./catalogTrial";
export type {
  CatalogEpisodeView,
  CatalogProjectView,
  CatalogSubjectView,
  EvidenceContextView,
  SubjectCreateInput,
} from "./catalogTypes";
export { CatalogApiError } from "./catalogTypes";
