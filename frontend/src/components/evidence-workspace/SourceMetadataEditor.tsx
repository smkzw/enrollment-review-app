import { useEffect, useState } from "react";
import type { EvidenceSnapshotMemberView } from "../../api/evidence";

interface SourceMetadataEditorProps {
  member: EvidenceSnapshotMemberView;
  busy: boolean;
  error: string | null;
  notice: string | null;
  onSave: (values: {
    documentType: string;
    sourceParty: string;
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
  const [reason, setReason] = useState("");

  useEffect(() => {
    setDocumentType(member.metadataHead.documentType);
    setSourceParty(member.metadataHead.sourceParty);
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
      <label className="evidence-field">
        <span>资料类型</span>
        <input
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value)}
          disabled={busy}
        />
      </label>
      <label className="evidence-field">
        <span>资料提供方</span>
        <input
          value={sourceParty}
          onChange={(event) => setSourceParty(event.target.value)}
          disabled={busy}
        />
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
        onClick={() => void onSave({ documentType, sourceParty, reason })}
      >
        {busy ? "正在保存…" : "保存核对结果"}
      </button>
    </section>
  );
}
