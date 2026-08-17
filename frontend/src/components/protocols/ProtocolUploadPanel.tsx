/**
 * 方案文件上传面板（首次解构第一步）。
 */

import { useRef, useState } from "react";
import { RouteLink } from "../../app/router";
import { ProtocolFileIcon } from "../shell/icons";

interface ProtocolUploadPanelProps {
  busy: boolean;
  error: string | null;
  onUpload: (file: File) => void;
}

export function ProtocolUploadPanel({ busy, error, onUpload }: ProtocolUploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (file: File | undefined) => {
    if (file === undefined) return;
    if (!file.name.toLowerCase().endsWith(".docx")) {
      return;
    }
    onUpload(file);
  };

  return (
    <div className="protocol-upload">
      <header className="page-head">
        <h1 className="page-head__title">首次解构新方案</h1>
        <p className="page-head__note">
          上传 DOCX 方案原文。系统将登记文件并提取结构；<strong>不声称</strong> OCR/LLM 在本阶段已全部完成。
        </p>
      </header>

      <div
        className={`protocol-upload__dropzone${dragOver ? " protocol-upload__dropzone--active" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          handleFile(event.dataTransfer.files[0]);
        }}
      >
        <ProtocolFileIcon size={32} />
        <p className="protocol-upload__hint">将 DOCX 方案拖放到此处，或点击选择文件</p>
        <button
          type="button"
          className="button button--primary"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? "正在登记文件…" : "选择方案文件"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="protocol-upload__input"
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
      </div>

      {error !== null && (
        <div className="feedback feedback--error" role="alert">
          <p className="feedback__title">{error}</p>
        </div>
      )}

      <p className="protocol-upload__back">
        <RouteLink to="/protocols" className="button button--quiet">
          返回方案工作台首页
        </RouteLink>
      </p>
    </div>
  );
}
