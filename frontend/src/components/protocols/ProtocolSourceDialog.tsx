/**
 * 方案原文定位摘要（UAT-P1-03）。
 * 本地演示只展示版本、页码和变化关联，不伪造原始文件预览。
 */

import { useEffect, useId, useRef } from "react";
import { CloseIcon } from "../shell/icons";

export interface ProtocolSourceLocation {
  id: string;
  versionLabel: string;
  pageLabel: string | null;
  changeCode: string;
  changeLabel: string;
}

interface ProtocolSourceDialogProps {
  source: ProtocolSourceLocation;
  onClose: () => void;
}

export function ProtocolSourceDialog({
  source,
  onClose,
}: ProtocolSourceDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="protocol-source-dialog-scrim"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="protocol-source-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="protocol-source-dialog__head">
          <div>
            <p className="protocol-source-dialog__eyebrow">方案原文定位</p>
            <h2 id={titleId} className="protocol-source-dialog__title">
              {source.changeCode} · {source.changeLabel}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="icon-button"
            aria-label="关闭方案原文定位"
            title="关闭方案原文定位"
            onClick={onClose}
          >
            <CloseIcon size={17} />
          </button>
        </header>
        <dl className="protocol-source-dialog__details">
          <div>
            <dt>方案版本</dt>
            <dd>{source.versionLabel}</dd>
          </div>
          <div>
            <dt>原文位置</dt>
            <dd>{source.pageLabel ?? "已保留版本定位"}</dd>
          </div>
          <div>
            <dt>核对内容</dt>
            <dd>{source.changeLabel}：{source.changeCode}</dd>
          </div>
        </dl>
        <p className="protocol-source-dialog__note">
          本次试用展示方案版本与页码定位摘要。当前使用版本仍为 V1.0，新版本内容不会覆盖当前审核结果。
        </p>
        <footer className="protocol-source-dialog__actions">
          <button type="button" className="button button--primary" onClick={onClose}>
            返回比较结果
          </button>
        </footer>
      </section>
    </div>
  );
}

