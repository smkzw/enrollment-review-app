/**
 * 运行时解码契约测试（任务 worker_03：运行时解码）。
 * - 合法载荷完整投影为领域模型，中文标签优先使用服务端值；
 * - 服务端标签缺失时使用兜底中文，绝不输出机器枚举；
 * - 未知分类、缺失必填字段、确认标志矛盾时立即抛 EvidenceDecodeError，
 *   不把 undefined/机器值渲染进界面。
 */

import { describe, expect, it } from "vitest";
import {
  EvidenceDecodeError,
  decodeCommitResponse,
  decodeMetadataRevisionResponse,
  decodeSnapshot,
  decodeSnapshotList,
  decodeUploadPreview,
  decodeUploadPreviewError,
  EvidenceApiError,
  commitResultMessage,
  formatByteSize,
} from "./evidenceViewModels";
import type { EvidenceUploadPreviewWire } from "./evidenceTypes";

function makeMetadataWire(overrides: Record<string, unknown> = {}) {
  return {
    metadata_revision_id: "metadata-1",
    source_document_version_id: "version-1",
    document_type: "检查报告",
    source_party: "研究中心",
    reason: "根据文件名生成待核对建议。",
    is_auto_suggestion: true,
    supersedes_metadata_revision_id: null,
    revision: 1,
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
    ...overrides,
  };
}

function makeItemWire(overrides: Record<string, unknown> = {}) {
  return {
    item_id: "item-1",
    file_name: "检查报告.pdf",
    byte_size: 2048,
    media_type: "application/pdf",
    status: "added",
    status_label: "新增资料",
    processing_hint: "process_new",
    processing_hint_label: "需要处理",
    reason: "该文件内容与文件名均未出现在上一有效快照中，为本次新增资料。",
    next_action: "将首次处理该文件，请确认后提交。",
    logical_document_id: "logical-1",
    existing_version_id: null,
    error_detail: null,
    ...overrides,
  };
}

function makePreviewWire(
  overrides: Record<string, unknown> = {},
): EvidenceUploadPreviewWire {
  return {
    preview_id: "preview-abc",
    project_id: "prj-1",
    subject_id: "subject-uat-01-clear",
    review_episode_id: "episode-uat-01-screening-clear",
    upload_mode: "incremental",
    upload_mode_label: "补充资料",
    base_revision: 1,
    base_snapshot_id: "snap-0",
    status: "staged",
    status_label: "等待确认",
    items: [makeItemWire()],
    matching_snapshot_id: null,
    matching_snapshot_status: null,
    matching_snapshot_status_label: null,
    preview_sha256: "a".repeat(64),
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
    ...overrides,
  };
}

describe("decodeUploadPreview", () => {
  it("合法预览完整投影，服务端中文标签优先", () => {
    const view = decodeUploadPreview(makePreviewWire());
    expect(view.previewId).toBe("preview-abc");
    expect(view.uploadMode).toBe("incremental");
    expect(view.uploadModeLabel).toBe("补充资料");
    expect(view.statusLabel).toBe("等待确认");
    expect(view.matchingSnapshotStatus).toBeNull();
    expect(view.items).toHaveLength(1);
    expect(view.items[0]).toMatchObject({
      itemId: "item-1",
      fileName: "检查报告.pdf",
      status: "added",
      statusLabel: "新增资料",
      nextAction: "将首次处理该文件，请确认后提交。",
    });
    expect(view.items[0].logicalDocumentId).toBe("logical-1");
  });

  it("服务端中文标签缺失时使用兜底中文，不暴露机器枚举", () => {
    const view = decodeUploadPreview(
      makePreviewWire({
        upload_mode_label: "",
        status_label: "",
        items: [
          makeItemWire({
            status: "conflict",
            status_label: "",
            processing_hint_label: "",
            next_action: "",
            reason: "",
          }),
        ],
      }),
    );
    expect(view.uploadModeLabel).toBe("补充资料");
    expect(view.statusLabel).toBe("等待确认");
    expect(view.items[0].statusLabel).toBe("名称相同但内容不同");
    expect(view.items[0].nextAction).toContain("作为原资料的新版本");
  });

  it("未知上传方式抛出 EvidenceDecodeError", () => {
    expect(() =>
      decodeUploadPreview(makePreviewWire({ upload_mode: "batch" })),
    ).toThrow(EvidenceDecodeError);
  });

  it("未知逐文件分类抛出 EvidenceDecodeError", () => {
    expect(() =>
      decodeUploadPreview(
        makePreviewWire({ items: [makeItemWire({ status: "mystery" })] }),
      ),
    ).toThrow(EvidenceDecodeError);
  });

  it("缺失必填字段抛出 EvidenceDecodeError", () => {
    const wire = makePreviewWire() as unknown as Record<string, unknown>;
    delete wire.preview_id;
    expect(() => decodeUploadPreview(wire)).toThrow(EvidenceDecodeError);
  });

  it("整组重复版本的标识、状态和中文说明必须成组且状态合法", () => {
    const view = decodeUploadPreview(
      makePreviewWire({
        matching_snapshot_id: "snap-pending",
        matching_snapshot_status: "processing",
        matching_snapshot_status_label: "正在整理",
      }),
    );
    expect(view.matchingSnapshotStatus).toBe("processing");
    expect(view.matchingSnapshotStatusLabel).toBe("正在整理");

    expect(() =>
      decodeUploadPreview(
        makePreviewWire({
          matching_snapshot_id: "snap-pending",
          matching_snapshot_status: null,
          matching_snapshot_status_label: null,
        }),
      ),
    ).toThrow(EvidenceDecodeError);
    expect(() =>
      decodeUploadPreview(
        makePreviewWire({
          matching_snapshot_id: "snap-pending",
          matching_snapshot_status: "unknown",
          matching_snapshot_status_label: "未知状态",
        }),
      ),
    ).toThrow(EvidenceDecodeError);
  });

  it("预览创建时间必须为 UTC 时间", () => {
    expect(() =>
      decodeUploadPreview(
        makePreviewWire({ created_at: "2026-08-19T08:00:00" }),
      ),
    ).toThrow(EvidenceDecodeError);
  });
});

describe("decodeSnapshot / decodeSnapshotList", () => {
  function makeSnapshotWire(overrides: Record<string, unknown> = {}) {
    return {
      evidence_snapshot_id: "snap-1",
      project_id: "prj-1",
      subject_id: "subject-uat-01-clear",
      review_episode_id: "episode-uat-01-screening-clear",
      upload_mode: "full",
      upload_mode_label: "建立完整资料快照",
      prior_snapshot_id: null,
      comparison_snapshot_id: null,
      status: "active",
      status_label: "当前有效",
      is_current: true,
      base_processing_revision_id: "base-revision-1",
      upload_job_id: "upload-job-1",
      members: [
        {
          member_id: "member-1",
          snapshot_id: "snap-1",
          logical_document_id: "logical-1",
          source_document_version_id: "version-1",
          file_name: "检查报告.pdf",
          media_type: "application/pdf",
          version_number: 1,
          origin: "added",
          origin_label: "本次新增",
          metadata_head: makeMetadataWire(),
        },
      ],
      collection_sha256: "b".repeat(64),
      created_at: "2026-08-19T08:00:00Z",
      created_by: "本地用户",
      ...overrides,
    };
  }

  it("快照与成员完整投影", () => {
    const snapshot = decodeSnapshot(makeSnapshotWire());
    expect(snapshot.statusLabel).toBe("当前有效");
    expect(snapshot.uploadJobId).toBe("upload-job-1");
    expect(snapshot.members[0].originLabel).toBe("本次新增");
    expect(snapshot.members[0].fileName).toBe("检查报告.pdf");
    expect(snapshot.members[0].metadataHead).toMatchObject({
      metadataRevisionId: "metadata-1",
      documentType: "检查报告",
      sourceParty: "研究中心",
      isAutoSuggestion: true,
      revision: 1,
    });
  });

  it("快照携带服务端最近一次资料版本生成状态", () => {
    const snapshot = decodeSnapshot(
      makeSnapshotWire({
        latest_processing_candidate: {
          candidate_id: "candidate-1",
          job_id: "job-1",
          candidate_status: "needs_attention",
          candidate_status_label: "需要核对",
          candidate_event_seq: 3,
          complete_revision_id: null,
        },
      }),
    );

    expect(snapshot.latestProcessingCandidate).toEqual({
      candidateId: "candidate-1",
      jobId: "job-1",
      candidateStatus: "needs_attention",
      candidateStatusLabel: "需要核对",
      candidateEventSeq: 3,
      completeRevisionId: null,
    });
  });

  it("快照不因任务编号暂缺而丢失候选状态", () => {
    const snapshot = decodeSnapshot(
      makeSnapshotWire({
        latest_processing_candidate: {
          candidate_id: "candidate-without-job",
          job_id: null,
          candidate_status: "ready",
          candidate_status_label: "待启用",
          candidate_event_seq: 2,
          complete_revision_id: "revision-1",
        },
      }),
    );

    expect(snapshot.latestProcessingCandidate).toMatchObject({
      candidateId: "candidate-without-job",
      jobId: null,
      candidateStatus: "ready",
    });
  });

  it("未知快照状态抛出 EvidenceDecodeError", () => {
    expect(() => decodeSnapshot(makeSnapshotWire({ status: "bogus" }))).toThrow(
      EvidenceDecodeError,
    );
  });

  it("快照列表投影", () => {
    const list = decodeSnapshotList({
      subject_id: "subject-uat-01-clear",
      review_episode_id: "episode-uat-01-screening-clear",
      active_evidence_snapshot_id: "snap-1",
      active_evidence_processing_revision_id: null,
      items: [makeSnapshotWire()],
    });
    expect(list.items).toHaveLength(1);
    expect(list.subjectId).toBe("subject-uat-01-clear");
  });

  it("资料分类信息必须与快照成员属于同一资料版本", () => {
    const wire = makeSnapshotWire();
    const member = (wire.members as Array<Record<string, unknown>>)[0];
    member.metadata_head = makeMetadataWire({
      source_document_version_id: "version-other",
    });
    expect(() => decodeSnapshot(wire)).toThrow(
      "资料分类信息与快照成员不属于同一份资料",
    );
  });
});

describe("decodeMetadataRevisionResponse", () => {
  it.each([
    [true, "追加新修订"],
    [false, "同一请求安全回放"],
  ])("完整解码资料信息（%s：%s）", (created) => {
    const view = decodeMetadataRevisionResponse({
      metadata: makeMetadataWire({
        metadata_revision_id: "metadata-2",
        document_type: "影像学检查",
        source_party: "中心影像科",
        reason: "已与原始资料核对。",
        is_auto_suggestion: false,
        supersedes_metadata_revision_id: "metadata-1",
        revision: 2,
      }),
      created,
    });
    expect(view.created).toBe(created);
    expect(view.metadata).toMatchObject({
      metadataRevisionId: "metadata-2",
      sourceDocumentVersionId: "version-1",
      documentType: "影像学检查",
      sourceParty: "中心影像科",
      reason: "已与原始资料核对。",
      isAutoSuggestion: false,
      supersedesMetadataRevisionId: "metadata-1",
      revision: 2,
      createdBy: "本地用户",
    });
  });

  it.each([
    ["修订号不是正整数", { revision: 0 }],
    ["资料类型为空", { document_type: "  " }],
    ["创建时间不是 UTC 时间", { created_at: "2026-08-19T08:00:00" }],
    ["后续修订缺少前序引用", { revision: 2 }],
    [
      "初始修订错误引用前序",
      { revision: 1, supersedes_metadata_revision_id: "metadata-0" },
    ],
  ])("拒绝不完整或矛盾的响应：%s", (_label, overrides) => {
    expect(() =>
      decodeMetadataRevisionResponse({
        metadata: makeMetadataWire(overrides),
        created: true,
      }),
    ).toThrow(EvidenceDecodeError);
  });

  it("created 缺失时拒绝猜测写入结果", () => {
    expect(() =>
      decodeMetadataRevisionResponse({ metadata: makeMetadataWire() }),
    ).toThrow(EvidenceDecodeError);
  });
});

describe("decodeCommitResponse", () => {
  function makeCommitWire(overrides: Record<string, unknown> = {}) {
    return {
      commit_id: "commit-1",
      preview_id: "preview-abc",
      evidence_snapshot_id: "snap-1",
      project_id: "prj-1",
      subject_id: "subject-uat-01-clear",
      review_episode_id: "episode-uat-01-screening-clear",
      upload_mode: "incremental",
      upload_mode_label: "补充资料",
      idempotency_key: "idem-1",
      job_id: "job-1",
      created: true,
      replayed: false,
      duplicate: false,
      resolutions: [],
      snapshot: {
        evidence_snapshot_id: "snap-1",
        project_id: "prj-1",
        subject_id: "subject-uat-01-clear",
        review_episode_id: "episode-uat-01-screening-clear",
        upload_mode: "incremental",
        upload_mode_label: "补充资料",
        prior_snapshot_id: "snap-0",
        comparison_snapshot_id: null,
        status: "staged",
        status_label: "待处理",
        is_current: false,
        base_processing_revision_id: null,
        upload_job_id: "job-1",
        members: [],
        collection_sha256: "c".repeat(64),
        created_at: "2026-08-19T08:00:00Z",
        created_by: "本地用户",
      },
      created_at: "2026-08-19T08:00:00Z",
      created_by: "本地用户",
      ...overrides,
    };
  }

  it("新建候选投影（created 单标志）", () => {
    const view = decodeCommitResponse(makeCommitWire());
    expect(view.created).toBe(true);
    expect(view.replayed).toBe(false);
    expect(view.duplicate).toBe(false);
    expect(view.jobId).toBe("job-1");
    expect(view.snapshot.statusLabel).toBe("待处理");
    expect(commitResultMessage(view)).toContain("已建立资料快照");
  });

  it.each([
    ["新建", { created: true, replayed: false, duplicate: false }],
    [
      "同键回放（原新建）",
      { created: false, replayed: true, duplicate: false },
    ],
    [
      "同键回放（原命中重复集合）",
      { created: false, replayed: true, duplicate: true },
    ],
    [
      "跨预览同集合 no-op",
      { created: false, replayed: false, duplicate: true },
    ],
  ])("合法标志组合 %s 被接受", (_label, flags) => {
    const view = decodeCommitResponse(makeCommitWire(flags));
    expect(view.created).toBe(flags.created);
    expect(view.replayed).toBe(flags.replayed);
    expect(view.duplicate).toBe(flags.duplicate);
  });

  it.each([
    ["新建且标记回放", { created: true, replayed: true, duplicate: false }],
    ["新建且标记重复", { created: true, replayed: false, duplicate: true }],
    [
      "新建且同时标记回放+重复",
      { created: true, replayed: true, duplicate: true },
    ],
    [
      "全假（无任何事实）",
      { created: false, replayed: false, duplicate: false },
    ],
  ])("非法标志组合 %s 抛出 EvidenceDecodeError", (_label, flags) => {
    expect(() => decodeCommitResponse(makeCommitWire(flags))).toThrow(
      EvidenceDecodeError,
    );
  });

  it("回放且命中重复集合时中文提示同时表达两种事实", () => {
    const view = decodeCommitResponse(
      makeCommitWire({ created: false, replayed: true, duplicate: true }),
    );
    const message = commitResultMessage(view);
    expect(message).toContain("已处理过");
    expect(message).toContain("未重复建立快照");
    expect(message).toContain("与已有快照相同");
  });
});

describe("decodeUploadPreviewError", () => {
  it("服务端中文错误信封投影为 EvidenceApiError", () => {
    const error = decodeUploadPreviewError({
      error: {
        code: "MISSING_RESOLUTION",
        title: "缺少同名文件的处置选择",
        detail: "必须明确选择处置方式后才能确认。",
        recovery_action: "请为每个冲突文件选择处置方式。",
        correlation_id: "abc",
      },
    });
    expect(error).toBeInstanceOf(EvidenceApiError);
    expect(error.code).toBe("MISSING_RESOLUTION");
    expect(error.message).toBe("必须明确选择处置方式后才能确认。");
    expect(error.recoveryAction).toContain("冲突文件");
  });

  it("409 保留提交值、服务端当前值与字段差异", () => {
    const error = decodeUploadPreviewError(
      {
        error: {
          code: "STALE_REVISION",
          title: "资料已发生变化",
          detail: "服务端已有更新，请核对差异。",
          recovery_action: "请确认当前值后再决定是否提交。",
          context: {
            submitted: { description: "本次说明" },
            current_record: { description: "服务端说明" },
            field_diff: {
              description: { submitted: "本次说明", current: "服务端说明" },
            },
          },
        },
      },
      409,
    );
    expect(error.statusCode).toBe(409);
    expect(error.conflictContext?.submitted.description).toBe("本次说明");
    expect(error.conflictContext?.currentRecord.description).toBe("服务端说明");
  });

  it("无法识别的错误载荷回退到统一错误", () => {
    const error = decodeUploadPreviewError("not-an-object");
    expect(error.code).toBe("INVALID_RESPONSE");
  });
});

describe("展示派生", () => {
  it("formatByteSize 输出中文友好单位", () => {
    expect(formatByteSize(512)).toBe("512 B");
    expect(formatByteSize(2048)).toBe("2 KB");
    expect(formatByteSize(3.5 * 1024 * 1024)).toBe("3.5 MB");
  });
});
