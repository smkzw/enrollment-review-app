/**
 * 重新解构确认弹层：基于反馈修订（原文理解纠错 / 补充解释）、取消确认、发布确认。
 * 所有说明使用中文临床工作语言；发布确认明确新的不可变规则版本将追加到目标项目。
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { FeedbackKind } from "../../api/protocolWorkbenchTypes";
import { mapProtocolDraftRules } from "../../domain/protocolMappers";

export interface FeedbackDraftValues {
  kind: FeedbackKind;
  note: string;
}

interface ProtocolFeedbackDialogProps {
  open: boolean;
  busy: boolean;
  errorMessage?: string;
  onClose: () => void;
  onSubmit: (values: FeedbackDraftValues) => void;
}

const FEEDBACK_KINDS: ReadonlyArray<{ kind: FeedbackKind; label: string; hint: string }> = [
  {
    kind: "source_error",
    label: "原文理解纠错",
    hint: "系统对方案原文的理解有误，需要纠正为与当前方案原文一致。",
  },
  {
    kind: "clarification",
    label: "补充解释",
    hint: "在方案原文之外补充本次审阅的解释说明，不改变入选/排除阈值与逻辑。",
  },
];

export function ProtocolFeedbackDialog({
  open,
  busy,
  errorMessage,
  onClose,
  onSubmit,
}: ProtocolFeedbackDialogProps) {
  const [kind, setKind] = useState<FeedbackKind>("clarification");
  const [note, setNote] = useState("");
  const titleId = useId();
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    setKind("clarification");
    setNote("");
    requestAnimationFrame(() => noteRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  const canSubmit = kind === "source_error" || note.trim().length > 0;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({ kind, note: note.trim() });
  };

  if (!open) return null;

  return (
    <div className="confirmation-scrim" onClick={busy ? undefined : onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="confirmation-dialog protocol-feedback-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>基于反馈修订草稿</h2>
        <p className="confirmation-dialog__note">
          选择反馈类型并填写说明。提交后将基于当前草稿生成修订稿；正式版本不受影响。
        </p>
        <fieldset className="protocol-feedback-kind">
          <legend>反馈类型</legend>
          {FEEDBACK_KINDS.map((item) => (
            <label key={item.kind} className={`protocol-feedback-kind__option${kind === item.kind ? " protocol-feedback-kind__option--active" : ""}`}>
              <input
                type="radio"
                name="protocol-feedback-kind"
                value={item.kind}
                checked={kind === item.kind}
                onChange={() => setKind(item.kind)}
              />
              <span>
                <strong>{item.label}</strong>
                <small>{item.hint}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <label className="protocol-feedback-note">
          <span>说明（补充解释必填）</span>
          <textarea
            ref={noteRef}
            value={note}
            rows={4}
            placeholder="例如：EX-04 的阈值应改为…，依据见方案第 N 页…"
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        {errorMessage !== undefined && errorMessage.length > 0 && (
          <p className="protocol-draft-actions__error" role="alert">
            {errorMessage}
          </p>
        )}
        <div className="confirmation-dialog__actions">
          <button
            ref={closeRef}
            type="button"
            className="button"
            disabled={busy}
            onClick={onClose}
          >
            先不要
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={busy || !canSubmit}
            onClick={submit}
          >
            {busy ? "正在提交…" : "提交反馈修订"}
          </button>
        </div>
      </section>
    </div>
  );
}

interface ProtocolConfirmPublishDialogProps {
  open: boolean;
  busy: boolean;
  sessionLabel: string;
  onClose: () => void;
  onConfirm: () => void;
}

export function ProtocolConfirmPublishDialog({
  open,
  busy,
  sessionLabel,
  onClose,
  onConfirm,
}: ProtocolConfirmPublishDialogProps) {
  const titleId = useId();

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!busy) onClose();
      }
    },
    [busy, onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown, open]);

  if (!open) return null;

  return (
    <div className="confirmation-scrim" onClick={busy ? undefined : onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="confirmation-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>确认发布新规则版本</h2>
        <p className="confirmation-dialog__note">{sessionLabel}</p>
        <p className="confirmation-dialog__note">
          发布将在目标项目下生成一个新的不可变规则版本，并把当前正式版本切换到新草稿。已发布的历史版本保留用于追溯，不能被覆盖或删除。
        </p>
        <p className="confirmation-dialog__note confirmation-dialog__note--warning">
          请先与目标项目的方案编号、研究期别逐一核对；跨方案或跨期别的新版方案将被阻止发布。
        </p>
        <div className="confirmation-dialog__actions">
          <button type="button" className="button" disabled={busy} onClick={onClose}>
            先不要
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "正在发布…" : "确认发布"}
          </button>
        </div>
      </section>
    </div>
  );
}

interface ProtocolConfirmCancelDialogProps {
  open: boolean;
  busy: boolean;
  errorMessage?: string;
  onClose: () => void;
  onConfirm: () => void;
}

export function ProtocolConfirmCancelDialog({
  open,
  busy,
  errorMessage,
  onClose,
  onConfirm,
}: ProtocolConfirmCancelDialogProps) {
  const titleId = useId();

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!busy) onClose();
      }
    },
    [busy, onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown, open]);

  if (!open) return null;

  return (
    <div className="confirmation-scrim" onClick={busy ? undefined : onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="confirmation-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>确认取消本次草稿</h2>
        <p className="confirmation-dialog__note">
          取消本次重新解构草稿后，目标项目的正式版本不会改变；已保存的草稿可稍后从恢复入口继续。
        </p>
        {errorMessage !== undefined && errorMessage.length > 0 && (
          <p className="protocol-draft-actions__error" role="alert">
            {errorMessage}
          </p>
        )}
        <div className="confirmation-dialog__actions">
          <button type="button" className="button" disabled={busy} onClick={onClose}>
            先不要
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "正在取消…" : "确认取消"}
          </button>
        </div>
      </section>
    </div>
  );
}

export interface ManualEditValues {
  componentId: string;
  title: string;
  sourceExcerpts: string;
}

interface ProtocolManualEditDialogProps {
  open: boolean;
  busy: boolean;
  errorMessage?: string;
  candidateContent: Record<string, unknown>;
  onClose: () => void;
  onSubmit: (values: ManualEditValues) => void;
}

/** 手工修订草稿：改写所选子项标题与方案原文摘录；提交后生成修订稿，正式版本不受影响。 */
export function ProtocolManualEditDialog({
  open,
  busy,
  errorMessage,
  candidateContent,
  onClose,
  onSubmit,
}: ProtocolManualEditDialogProps) {
  const rules = useMemo(
    () => mapProtocolDraftRules(candidateContent),
    [candidateContent],
  );
  const allComponents = useMemo(
    () => rules.flatMap((rule) => rule.components),
    [rules],
  );
  const [componentId, setComponentId] = useState<string>(
    allComponents[0]?.componentId ?? "",
  );
  const [title, setTitle] = useState("");
  const [excerpts, setExcerpts] = useState("");
  const titleId = useId();
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const component = allComponents.find((item) => item.componentId === componentId);
    setTitle(component?.title ?? "");
    setExcerpts(component?.sourceExcerpts.join("\n") ?? "");
    requestAnimationFrame(() => titleRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!busy) onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, busy, componentId, onClose, allComponents]);

  if (!open) return null;

  const selected = allComponents.find((item) => item.componentId === componentId);
  const canSubmit = selected !== undefined && title.trim().length > 0;

  const chooseComponent = (id: string) => {
    setComponentId(id);
    const component = allComponents.find((item) => item.componentId === id);
    setTitle(component?.title ?? "");
    setExcerpts(component?.sourceExcerpts.join("\n") ?? "");
  };

  return (
    <div className="confirmation-scrim" onClick={busy ? undefined : onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="confirmation-dialog protocol-edit-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>手工修订草稿</h2>
        <p className="confirmation-dialog__note">
          选择要修订的子项，改写其标题与方案原文摘录。提交后生成修订稿；正式版本不受影响。
        </p>
        <label className="protocol-edit-dialog__field">
          <span>修订子项</span>
          <select
            value={componentId}
            onChange={(event) => chooseComponent(event.target.value)}
          >
            {allComponents.map((component) => (
              <option key={component.componentId} value={component.componentId}>
                {component.displayCode} · {component.title}
              </option>
            ))}
          </select>
        </label>
        {selected !== undefined && (
          <>
            <label className="protocol-edit-dialog__field">
              <span>子项标题</span>
              <input
                ref={titleRef}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="protocol-edit-dialog__field">
              <span>方案原文摘录（每行一条）</span>
              <textarea
                value={excerpts}
                rows={4}
                onChange={(event) => setExcerpts(event.target.value)}
              />
            </label>
          </>
        )}
        {errorMessage !== undefined && errorMessage.length > 0 && (
          <p className="protocol-draft-actions__error" role="alert">
            {errorMessage}
          </p>
        )}
        <div className="confirmation-dialog__actions">
          <button type="button" className="button" disabled={busy} onClick={onClose}>
            先不要
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={busy || !canSubmit}
            onClick={() =>
              onSubmit({
                componentId,
                title: title.trim(),
                sourceExcerpts: excerpts,
              })
            }
          >
            {busy ? "正在提交…" : "提交手工修订"}
          </button>
        </div>
      </section>
    </div>
  );
}
