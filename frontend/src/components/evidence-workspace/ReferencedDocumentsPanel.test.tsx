// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  decodeOcrPage,
  decodeReferencedDocumentList,
  decodeSnapshot,
} from "../../api/evidence";
import { ReferencedDocumentsPanel } from "./ReferencedDocumentsPanel";

function referencedData() {
  return decodeReferencedDocumentList({
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    items: [{
      revision_id: "ref-revision-1",
      referenced_document_id: "ref-1",
      project_id: "project-1",
      subject_id: "subject-1",
      review_episode_id: "episode-1",
      description: "既往影像报告",
      document_type: null,
      source_party: null,
      origin: "manual",
      origin_label: "手工登记",
      pattern_version: null,
      status: "proposed",
      status_label: "待确认",
      user_reviewed: false,
      reason: null,
      revision: 1,
      supersedes_revision_id: null,
      trigger_locator_id: null,
      resolution: null,
      created_at: "2026-08-21T00:00:00Z",
      created_by: "本地用户",
    }],
  });
}

describe("ReferencedDocumentsPanel", () => {
  it("支持登记、确认、解除候选以及关联/解除当前有效资料成员", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn(async () => undefined);
    const onRevise = vi.fn(async () => undefined);
    const onConfirm = vi.fn(async () => undefined);
    const onDismiss = vi.fn(async () => undefined);
    const onResolve = vi.fn(async () => undefined);
    const onUnresolve = vi.fn(async () => undefined);
    const snapshot = decodeSnapshot({
      evidence_snapshot_id: "snapshot-1",
      project_id: "project-1",
      subject_id: "subject-1",
      review_episode_id: "episode-1",
      upload_mode: "incremental",
      upload_mode_label: "补充资料",
      prior_snapshot_id: null,
      comparison_snapshot_id: null,
      status: "active",
      status_label: "当前有效",
      is_current: true,
      base_processing_revision_id: "revision-1",
      upload_job_id: null,
      members: [{
        member_id: "member-1",
        snapshot_id: "snapshot-1",
        logical_document_id: "logical-1",
        source_document_version_id: "version-1",
        file_name: "影像报告.pdf",
        media_type: "application/pdf",
        version_number: 1,
        origin: "added",
        origin_label: "本次新增",
        metadata_head: {
          metadata_revision_id: "metadata-1",
          source_document_version_id: "version-1",
          document_type: "影像报告",
          source_party: "研究中心",
          reason: "系统根据文件名和内容提出建议，等待人工核对。",
          is_auto_suggestion: true,
          supersedes_metadata_revision_id: null,
          revision: 1,
          created_at: "2026-08-21T00:00:00Z",
          created_by: "本地用户",
        },
      }],
      collection_sha256: "a".repeat(64),
      created_at: "2026-08-21T00:00:00Z",
      created_by: "本地用户",
    });
    const ocrPage = decodeOcrPage({
      ocr_page_id: "ocr-page-1",
      page_artifact_id: "artifact-1",
      source_document_version_id: "version-1",
      page_number: 1,
      source_sha256: "b".repeat(64),
      raw_text: "既往影像报告",
      raw_text_sha256: "c".repeat(64),
      status: "succeeded",
      status_label: "已识别",
      processing_revision_id: "revision-1",
      is_current_revision: true,
      effective_text: null,
      effective_text_sha256: null,
      selected_corrections: [],
      risk_scans: [],
      risk_reviews: [],
      locators: [{
        locator_id: "locator-1",
        page_artifact_id: "artifact-1",
        ocr_page_id: "ocr-page-1",
        source_document_version_id: "version-1",
        page_number: 1,
        source_layer: "raw_ocr",
        source_layer_label: "原始识别文本",
        source_text_sha256: "c".repeat(64),
        target_id: "target-1",
        precision: "text_range",
        precision_label: "文本范围",
        degradation_reason: null,
        text_start: 0,
        text_end: 6,
        excerpt: "既往影像报告",
        disambiguation: "unique_match",
        locator_algorithm_version: "locator-1",
        authenticity: "authenticated",
        match_confidence: 1,
        bbox: null,
        coordinate_frame: null,
        coordinate_transform_version: null,
      }],
    });
    const locator = ocrPage.locators[0];
    if (locator === undefined) throw new Error("测试定位缺失");

    render(
      <ReferencedDocumentsPanel
        data={referencedData()}
        currentMembers={snapshot.members}
        locators={[locator]}
        conflict={null}
        onCreate={onCreate}
        onRevise={onRevise}
        onConfirm={onConfirm}
        onDismiss={onDismiss}
        onResolve={onResolve}
        onUnresolve={onUnresolve}
      />,
    );

    expect(
      screen.getAllByRole("option", {
        name: "第 1 页 · 识别文字 · 既往影像报告",
      }),
    ).toHaveLength(2);
    expect(screen.queryByText("文本范围")).not.toBeInTheDocument();

    const createSection = screen.getByText("登记一项被提及资料").closest("details");
    expect(createSection).not.toHaveAttribute("open");
    await user.click(screen.getByText("登记一项被提及资料"));
    expect(createSection).toHaveAttribute("open");

    const createDescription = screen.getByPlaceholderText("例如：既往影像报告");
    await user.type(createDescription, "新的被提及资料");
    await user.click(screen.getByRole("button", { name: "登记为待确认" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({ description: "新的被提及资料" }),
      null,
    ));

    await user.type(screen.getByRole("textbox", { name: "本次操作说明" }), "已与中心核对");
    await user.selectOptions(screen.getByRole("combobox", { name: "确认提及位置（当前页）" }), "locator-1");
    await user.click(screen.getByRole("button", { name: "确认提及" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ referencedDocumentId: "ref-1" }),
      "locator-1",
      "已与中心核对",
    ));

    await user.selectOptions(screen.getByRole("combobox", { name: "关联当前有效资料" }), "version-1");
    await waitFor(() => expect(onResolve).toHaveBeenCalledWith(
      expect.objectContaining({ referencedDocumentId: "ref-1" }),
      "version-1",
    ));
  });
});
