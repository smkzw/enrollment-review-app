/**
 * 品牌 ID：跨实体复用字符串会导致筛选/勾选/跳转选择漂移。
 * 所有领域 ID 在 wire→domain 映射边界通过 {@link toId} 构造一次。
 */

declare const brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [brand]: B };

export type ProjectId = Brand<string, "ProjectId">;
export type SubjectId = Brand<string, "SubjectId">;
export type ReviewEpisodeId = Brand<string, "ReviewEpisodeId">;
export type RuleSetId = Brand<string, "RuleSetId">;
export type RuleId = Brand<string, "RuleId">;
export type RuleComponentId = Brand<string, "RuleComponentId">;
export type EvidenceSpanId = Brand<string, "EvidenceSpanId">;
export type SourceDocumentVersionId = Brand<string, "SourceDocumentVersionId">;
export type EvidenceSnapshotId = Brand<string, "EvidenceSnapshotId">;
export type ActionId = Brand<string, "ActionId">;
export type AssessmentId = Brand<string, "AssessmentId">;
export type ExpectationId = Brand<string, "ExpectationId">;
export type ConflictGroupId = Brand<string, "ConflictGroupId">;
export type FactId = Brand<string, "FactId">;
export type ProfileEventId = Brand<string, "ProfileEventId">;
export type ReviewRunId = Brand<string, "ReviewRunId">;
export type JobId = Brand<string, "JobId">;
export type RequirementId = Brand<string, "RequirementId">;
export type WorkflowStageId = Brand<string, "WorkflowStageId">;

/**
 * 构造品牌 ID。仅在 api 层映射 fixture 资产时调用；
 * fixture 为 schema 冻结资产，ID 结构由契约保证，映射测试会校验实际引用。
 */
export function toId<T extends string>(value: string): T {
  return value as T;
}
