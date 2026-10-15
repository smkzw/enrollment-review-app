/** 判断检索接口的网络载荷与页面可用视图类型。 */

export const JUDGMENT_SEARCH_JOB_STATES = [
  "queued",
  "running",
  "completed",
  "failed_retryable",
  "failed_final",
  "cancel_requested",
  "cancelled",
  "recovering",
  "waiting_user",
  "user_resumed",
] as const;
export type JudgmentSearchJobState = (typeof JUDGMENT_SEARCH_JOB_STATES)[number];

export const JUDGMENT_SEARCH_RESULT_STATUSES = [
  "candidates_present",
  "all_supplied_pages_searched_without_candidate",
  "coverage_incomplete",
] as const;
export type JudgmentSearchResultStatus = (typeof JUDGMENT_SEARCH_RESULT_STATUSES)[number];

/** 服务端的检索读道标识；页面显示时必须转换成中文。 */
export const JUDGMENT_SEARCH_LANES = ["main-A", "main-B"] as const;
export type JudgmentSearchLane = (typeof JUDGMENT_SEARCH_LANES)[number];

export const JUDGMENT_SEARCH_CHANNELS = ["handwritten", "printed_analysis"] as const;
export type JudgmentSearchChannel = (typeof JUDGMENT_SEARCH_CHANNELS)[number];

export interface JudgmentSearchStartView {
  jobId: string;
  state: JudgmentSearchJobState;
  stateLabel: string;
  created: boolean;
}

export interface JudgmentSearchRequirementStatusView {
  requirementId: string;
  status: JudgmentSearchResultStatus;
  statusLabel: string;
  foundCandidateCount: number;
}

export interface JudgmentSearchStatusView {
  jobId: string;
  state: JudgmentSearchJobState;
  stateLabel: string;
  totalPages: number;
  completedReads: number;
  totalReads: number;
  requirementResults: ReadonlyArray<JudgmentSearchRequirementStatusView>;
  canResume: boolean;
}

export interface JudgmentSearchBoundingBoxView {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface JudgmentSearchExcerptView {
  text: string;
  bbox: JudgmentSearchBoundingBoxView | null;
  coordinateConvention: "unverified";
  uncertaintyNote: string | null;
}

export interface JudgmentSearchCandidateView {
  lane: JudgmentSearchLane;
  laneLabel: string;
  channel: JudgmentSearchChannel;
  channelLabel: string;
  sourceDocumentVersionId: string;
  pageArtifactId: string;
  pageNumber: number;
  excerpts: ReadonlyArray<JudgmentSearchExcerptView>;
}

export interface JudgmentSearchIncompletePageView {
  sourceDocumentVersionId: string;
  pageArtifactId: string;
  pageNumber: number;
  reasons: ReadonlyArray<string>;
}

export interface JudgmentSearchRequirementResultView {
  requirementId: string;
  requirementLabel: string;
  status: JudgmentSearchResultStatus | null;
  statusLabel: string;
  foundCandidates: ReadonlyArray<JudgmentSearchCandidateView>;
  incompletePages: ReadonlyArray<JudgmentSearchIncompletePageView>;
}

export interface JudgmentSearchResultsView {
  jobId: string;
  state: JudgmentSearchJobState;
  searchedPageCount: number;
  results: ReadonlyArray<JudgmentSearchRequirementResultView>;
}

export interface JudgmentSearchResumeView {
  jobId: string;
  state: JudgmentSearchJobState;
  changed: boolean;
  stateLabel: string;
}

export interface JudgmentSearchStartInput {
  requirementIds?: ReadonlyArray<string>;
}
