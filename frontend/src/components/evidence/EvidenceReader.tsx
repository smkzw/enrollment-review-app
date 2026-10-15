import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/** Native modal isolation keeps original-page scrolling out of the underlying work area. */
export function EvidenceReader({ title, open = true, onClose, children }: {
  title: string;
  open?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current;
    element?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
    };
  }, [open]);
  return createPortal(<dialog ref={dialog} className="evidence-reader" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="evidence-reader__head">
      <h2 id={titleId}>{title}</h2>
      <button type="button" className="icon-button" aria-label="关闭原件" title="关闭原件" onClick={onClose}>
        <X size={20} aria-hidden="true" />
      </button>
    </header>
    <div className="evidence-reader__body">{children}</div>
  </dialog>, document.body);
}
