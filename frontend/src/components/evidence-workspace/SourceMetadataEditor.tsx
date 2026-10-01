import { useEffect, useState } from "react";
import type { EvidenceSnapshotMemberView } from "../../api/evidence";
import type { DocumentCategory, SourceCategory } from "../../api/evidence/evidenceTypes";

interface SourceMetadataEditorProps {
  member: EvidenceSnapshotMemberView;
  busy: boolean;
  error: string | null;
  notice: string | null;
  onSave: (values: {
    documentType: string;
    sourceParty: string;
    documentCategory: DocumentCategory;
    sourceCategory: SourceCategory;
    reason: string;
  }) => Promise<void>;
}

export function SourceMetadataEditor({
  member,
  busy,
  error,
  notice,
  onSave,
}: SourceMetadataEditorProps) {
  const [documentType, setDocumentType] = useState(member.metadataHead.documentType);
  const [sourceParty, setSourceParty] = useState(member.metadataHead.sourceParty);
  const [documentCategory, setDocumentCategory] = useState<DocumentCategory | "">(member.metadataHead.documentCategory ?? "");
  const [sourceCategory, setSourceCategory] = useState<SourceCategory | "">(member.metadataHead.sourceCategory ?? "");
  const [reason, setReason] = useState("");

  useEffect(() => {
    setDocumentType(member.metadataHead.documentType);
    setSourceParty(member.metadataHead.sourceParty);
    setDocumentCategory(member.metadataHead.documentCategory ?? "");
    setSourceCategory(member.metadataHead.sourceCategory ?? "");
    setReason("");
  }, [member.metadataHead.metadataRevisionId]);

  const ready =
    documentType.trim().length > 0 &&
    sourceParty.trim().length > 0 &&
    reason.trim().length > 0 &&
    !busy;

  return (
    <section className="evidence-metadata" aria-label="核对资料信息">
      <header className="evidence-metadata__head">
        <div>
          <p className="evidence-kicker">所选文件</p>
          <h4>核对资料信息</h4>
        </div>
        <span className={`chip${member.metadataHead.isAutoSuggestion ? " chip--attention" : " chip--success"}`}>
          {member.metadataHead.isAutoSuggestion ? "系统建议，待核对" : "已人工核对"}
        </span>
      </header>
      <p className="evidence-metadata__file">{member.fileName}</p>
      <p className="evidence-metadata__file">上传者：{member.uploadedBy} · 资料归属由上传者核对</p>
      <label className="evidence-field">
        <span>原件所写资料名称</span>
        <input
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value)}
          disabled={busy}
        />
      </label>
      <label className="evidence-field">
        <span>原件所写出具方</span>
        <input
          value={sourceParty}
          onChange={(event) => setSourceParty(event.target.value)}
          disabled={busy}
        />
      </label>
      <label className="evidence-field">
        <span>资料类别</span>
        <select
          value={documentCategory}
          onChange={(event) => setDocumentCategory(event.target.value as DocumentCategory | "")}
          disabled={busy}
        >
          <option value="">尚未核实</option>
          <option value="objective_report">检验或检查原始报告</option>
          <option value="historical_record">既往原始病历</option>
          <option value="study_chart">本研究病历</option>
          <option value="screening_transcription">筛选病历转述</option>
          <option value="other">其他资料</option>
          <option value="unknown">无法确认</option>
        </select>
      </label>
      <label className="evidence-field">
        <span>出具方类别</span>
        <select
          value={sourceCategory}
          onChange={(event) => setSourceCategory(event.target.value as SourceCategory | "")}
          disabled={busy}
        >
          <option value="">尚未核实</option>
          <option value="study_site">研究中心出具</option>
          <option value="external_hospital">外院出具</option>
          <option value="participant">受试者提供，出具方未核</option>
          <option value="other">其他来源</option>
          <option value="unknown">无法确认</option>
        </select>
      </label>
      <label className="evidence-field">
        <span>核对说明</span>
        <textarea
          rows={2}
          value={reason}
          placeholder="例如：已与原文件标题和内容核对"
          onChange={(event) => setReason(event.target.value)}
          disabled={busy}
        />
      </label>
      {error !== null && <p className="evidence-metadata__error" role="alert">{error}</p>}
      {notice !== null && <p className="evidence-metadata__notice" role="status">{notice}</p>}
      <button
        type="button"
        className="button button--primary"
        disabled={!ready}
        onClick={() => void onSave({
          documentType,
          sourceParty,
          documentCategory: documentCategory || "unknown",
          sourceCategory: sourceCategory || "unknown",
          reason,
        })}
      >
        {busy ? "正在保存…" : "保存核对结果"}
      </button>
    </section>
  );
}
