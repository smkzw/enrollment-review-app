/**
 * 证据工作台 V2 API 契约（与 app/api/v2/evidence_schemas.py 对齐，Slice 4.2）。
 * 只描述网络载荷的原始结构；组件经 evidenceViewModels.ts 解码消费领域模型，
 * 不直接使用 wire 结构（spec: type-safety）。
 *
 * 服务端为每个上传预览/资料版本投影自然中文标签（upload_mode_label、status_label、
 * reason、next_action），前端不自行翻译内部枚举；中文标签的兜底映射只在解码层。
 */

/** 上传方式机器值：仅用于请求/类型，界面文案一律使用中文标签。 */
export type EvidenceUploadModeWire = "incremental" | "full";

export interface EvidenceUploadItemWire {
  item_id: string;
  file_name: string;
  byte_size: number;
  media_type: string;
  status: string;
  status_label: string;
  processing_hint: string;
  processing_hint_label: string;
  reason: string;
  next_action: string;
  logical_document_id: string | null;
  existing_version_id: string | null;
  error_detail: string | null;
}

export interface EvidenceUploadPreviewWire {
  preview_id: string;
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  upload_mode: EvidenceUploadModeWire;
  upload_mode_label: string;
  base_revision: number;
  base_snapshot_id: string | null;
  status: string;
  status_label: string;
  items: EvidenceUploadItemWire[];
  matching_snapshot_id: string | null;
  matching_snapshot_status: string | null;
  matching_snapshot_status_label: string | null;
  preview_sha256: string;
  created_at: string;
  created_by: string;
}

/** 资料类型与来源方的不可变修订；资料版本成员固定投影当前链头。 */
export interface EvidenceMetadataRevisionWire {
  metadata_revision_id: string;
  source_document_version_id: string;
  document_type: string;
  source_party: string;
  reason: string;
  is_auto_suggestion: boolean;
  supersedes_metadata_revision_id: string | null;
  revision: number;
  created_at: string;
  created_by: string;
}

export interface EvidenceMetadataRevisionRequestWire {
  document_type: string;
  source_party: string;
  reason: string;
  expected_metadata_revision: number;
  idempotency_key: string;
  actor?: string | null;
}

export interface EvidenceMetadataRevisionResponseWire {
  metadata: EvidenceMetadataRevisionWire;
  created: boolean;
}

export interface EvidenceSnapshotMemberWire {
  member_id: string;
  snapshot_id: string;
  logical_document_id: string;
  source_document_version_id: string;
  file_name: string;
  media_type: string;
  version_number: number;
  origin: string;
  origin_label: string;
  metadata_head: EvidenceMetadataRevisionWire;
}

export interface EvidenceSnapshotWire {
  evidence_snapshot_id: string;
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  upload_mode: EvidenceUploadModeWire;
  upload_mode_label: string;
  prior_snapshot_id: string | null;
  comparison_snapshot_id: string | null;
  status: string;
  status_label: string;
  /** 是否为审核节点活动指针投影；不得由前端按状态或时间推导。 */
  is_current: boolean;
  base_processing_revision_id: string | null;
  upload_job_id: string | null;
  members: EvidenceSnapshotMemberWire[];
  collection_sha256: string;
  created_at: string;
  created_by: string;
}

export interface EvidenceSnapshotListWire {
  subject_id: string;
  review_episode_id: string;
  active_evidence_snapshot_id: string | null;
  active_evidence_processing_revision_id: string | null;
  items: EvidenceSnapshotWire[];
}

/** 确认请求：preview_id 由路径确定；preview_sha256 由服务端重算核验。 */
export interface EvidenceCommitRequestWire {
  preview_sha256: string;
  upload_mode: EvidenceUploadModeWire;
  base_revision: number;
  idempotency_key: string;
  actor?: string | null;
  /** item_id -> new_version | keep_parallel（同名异内容文件） */
  resolutions: Record<string, string>;
}

export interface EvidenceResolutionDecisionWire {
  item_id: string;
  logical_document_id: string;
  resolution: string;
  resolution_label: string;
  source_document_version_id: string;
  supersedes_version_id: string | null;
}

export interface EvidenceCommitResponseWire {
  commit_id: string;
  preview_id: string;
  evidence_snapshot_id: string;
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  upload_mode: EvidenceUploadModeWire;
  upload_mode_label: string;
  idempotency_key: string;
  job_id: string | null;
  created: boolean;
  replayed: boolean;
  duplicate: boolean;
  resolutions: EvidenceResolutionDecisionWire[];
  snapshot: EvidenceSnapshotWire;
  created_at: string;
  created_by: string;
}

export interface EvidenceUploadErrorBody {
  code: string;
  title: string;
  detail: string;
  recovery_action: string;
  correlation_id?: string;
}

/** 证据上传入口请求：创建上传预览的多部分表单字段。 */
export interface CreateUploadPreviewInput {
  subjectId: string;
  reviewEpisodeId: string;
  uploadMode: EvidenceUploadModeWire;
  baseRevision: number;
  actor?: string;
  files: File[];
}
