// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EvidenceSnapshotMemberView } from "../../api/evidence";
import { SourceMetadataEditor } from "./SourceMetadataEditor";

function member(isAutoSuggestion = true): EvidenceSnapshotMemberView {
  return {
    memberId: "member-1",
    snapshotId: "snapshot-1",
    logicalDocumentId: "document-1",
    sourceDocumentVersionId: "version-1",
    fileName: "筛选病历.pdf",
    mediaType: "application/pdf",
    versionNumber: 1,
    uploadedBy: "上传者甲",
    origin: "added",
    originLabel: "本次新增",
    metadataHead: {
      metadataRevisionId: "metadata-1",
      sourceDocumentVersionId: "version-1",
      documentType: "筛选病历",
      sourceParty: "研究中心（待确认）",
      reason: "系统根据文件名提出建议。",
      isAutoSuggestion,
      supersedesMetadataRevisionId: null,
      revision: 1,
      createdAt: "2026-08-21T00:00:00Z",
      createdBy: "本地用户",
    },
  };
}

describe("SourceMetadataEditor", () => {
  it("系统建议必须填写核对说明后才能保存", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <SourceMetadataEditor
        member={member()}
        busy={false}
        error={null}
        notice={null}
        onSave={onSave}
      />,
    );

    expect(screen.getByText("系统建议，待核对")).toBeInTheDocument();
    expect(screen.getByText("上传者：上传者甲 · 资料归属由上传者核对")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "保存核对结果" });
    expect(save).toBeDisabled();
    await user.type(
      screen.getByRole("textbox", { name: "核对说明" }),
      "已核对文件标题与正文内容",
    );
    await user.click(save);

    expect(onSave).toHaveBeenCalledWith({
      documentType: "筛选病历",
      sourceParty: "研究中心（待确认）",
      documentCategory: "unknown",
      sourceCategory: "unknown",
      reason: "已核对文件标题与正文内容",
    });
  });

  it("类别独立核对，保留原件上的具体名称和出具方", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <SourceMetadataEditor
        member={member()}
        busy={false}
        error={null}
        notice={null}
        onSave={onSave}
      />,
    );

    const documentName = screen.getByRole("textbox", { name: "原件所写资料名称" });
    const issuer = screen.getByRole("textbox", { name: "原件所写出具方" });
    await user.clear(documentName);
    await user.type(documentName, "某项检验原始报告");
    await user.clear(issuer);
    await user.type(issuer, "某研究中心检验科");
    await user.selectOptions(screen.getByRole("combobox", { name: "资料类别" }), "objective_report");
    await user.selectOptions(screen.getByRole("combobox", { name: "出具方类别" }), "study_site");
    await user.type(screen.getByRole("textbox", { name: "核对说明" }), "已核对报告抬头与出具机构");
    await user.click(screen.getByRole("button", { name: "保存核对结果" }));

    expect(onSave).toHaveBeenCalledWith({
      documentType: "某项检验原始报告",
      sourceParty: "某研究中心检验科",
      documentCategory: "objective_report",
      sourceCategory: "study_site",
      reason: "已核对报告抬头与出具机构",
    });
  });

  it("来源无法确认时可以明确保留未决", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <SourceMetadataEditor
        member={member()}
        busy={false}
        error={null}
        notice={null}
        onSave={onSave}
      />,
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "出具方类别" }), "unknown");
    await user.type(screen.getByRole("textbox", { name: "核对说明" }), "原件未见出具机构");
    await user.click(screen.getByRole("button", { name: "保存核对结果" }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      sourceParty: "研究中心（待确认）",
      sourceCategory: "unknown",
    }));
  });

  it("人工核对状态与保存错误均使用面向用户的中文呈现", () => {
    render(
      <SourceMetadataEditor
        member={member(false)}
        busy={false}
        error="资料信息已被更新，请重新核对后保存。"
        notice={null}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("已人工核对")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "资料信息已被更新，请重新核对后保存。",
    );
  });

  it("保存成功反馈在资料信息区域内呈现", () => {
    render(
      <SourceMetadataEditor
        member={member(false)}
        busy={false}
        error={null}
        notice="资料类型与提供方已保存，将纳入下一次生成的资料版本。"
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "资料类型与提供方已保存，将纳入下一次生成的资料版本。",
    );
  });
});
