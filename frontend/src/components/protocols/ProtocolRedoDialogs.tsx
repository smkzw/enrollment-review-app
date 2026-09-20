/**
 * 重新解构确认弹层：基于反馈修订（原文理解纠错 / 补充解释）、取消确认、发布确认。
 * 所有说明使用中文临床工作语言；发布确认明确新的不可变规则版本将追加到目标项目。
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { FeedbackKind } from "../../api/protocolWorkbenchTypes";
import { mapProtocolDraftRules } from "../../domain/protocolMappers";
import {
  getEditableProtocolComponents,
  type ComponentSemanticPatch,
  type EditablePredicate,
  type EditableProtocolComponent,
} from "../../domain/protocolManualEdit";

export interface FeedbackDraftValues {
  kind: FeedbackKind;
  targetRuleCode: string;
  note: string;
}

interface ProtocolFeedbackDialogProps {
  open: boolean;
  busy: boolean;
  errorMessage?: string;
  candidateContent: Record<string, unknown>;
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
  candidateContent,
  onClose,
  onSubmit,
}: ProtocolFeedbackDialogProps) {
  const [kind, setKind] = useState<FeedbackKind>("clarification");
  const rules = useMemo(
    () => mapProtocolDraftRules(candidateContent),
    [candidateContent],
  );
  const [targetRuleCode, setTargetRuleCode] = useState("");
  const [note, setNote] = useState("");
  const titleId = useId();
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    setKind("clarification");
    setTargetRuleCode(rules[0]?.officialCode ?? "");
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
  }, [open, onClose, rules]);

  const canSubmit = targetRuleCode.length > 0 && note.trim().length > 0;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({ kind, targetRuleCode, note: note.trim() });
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
          <span>需要核对的入排标准</span>
          <select
            value={targetRuleCode}
            onChange={(event) => setTargetRuleCode(event.target.value)}
          >
            {rules.map((rule) => (
              <option key={rule.ruleId} value={rule.officialCode}>
                {rule.officialCode}｜{rule.components[0]?.title ?? rule.sourceText}
              </option>
            ))}
          </select>
        </label>
        <label className="protocol-feedback-note">
          <span>具体意见（必填）</span>
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
  blocked?: boolean;
  errorMessage?: string;
  sessionLabel: string;
  isRedo?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ProtocolConfirmPublishDialog({
  open,
  busy,
  blocked = false,
  errorMessage,
  sessionLabel,
  isRedo = true,
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
        {errorMessage && <p role="alert">{errorMessage}</p>}
        {blocked && <p role="status">补充审核要求尚未整理完成，暂不能发布。</p>}
        <p className="confirmation-dialog__note">{sessionLabel}</p>
        <p className="confirmation-dialog__note">
          {isRedo
            ? "发布将在目标项目下生成一个新的不可变规则版本，并把当前正式版本切换到新草稿。已发布的历史版本保留用于追溯，不能被覆盖或删除。"
            : "发布将建立正式项目并生成第一个不可变规则版本。草稿发布后仍会保留完整来源和修订记录，用于后续追溯。"}
        </p>
        <p className="confirmation-dialog__note confirmation-dialog__note--warning">
          {isRedo
            ? "请先与目标项目的方案编号、研究期别逐一核对；跨方案或跨期别的新版方案将被阻止发布。"
            : "请最后核对方案编号、版本、日期和研究期别；同一方案、同一期别已有正式项目时，系统会阻止重复建立。"}
        </p>
        <div className="confirmation-dialog__actions">
          <button type="button" className="button" disabled={busy} onClick={onClose}>
            先不要
          </button>
          <button
            type="button"
            className="button button--primary"
            disabled={busy || blocked}
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
  isRedo?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ProtocolConfirmCancelDialog({
  open,
  busy,
  errorMessage,
  isRedo = true,
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
          {isRedo
            ? "取消本次重新解构草稿后，目标项目的正式版本不会改变；已保存的草稿可稍后从恢复入口继续。"
            : "取消本次首次解构草稿不会建立正式项目；已保存的草稿可稍后从恢复入口继续。"}
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
  patch: ComponentSemanticPatch;
}

interface ProtocolManualEditDialogProps {
  open: boolean;
  busy: boolean;
  errorMessage?: string;
  candidateContent: Record<string, unknown>;
  onClose: () => void;
  onSubmit: (values: ManualEditValues) => void;
}

/** 手工修订草稿：来源只读，只修订已有子项的结构化临床语义。 */
export function ProtocolManualEditDialog({
  open,
  busy,
  errorMessage,
  candidateContent,
  onClose,
  onSubmit,
}: ProtocolManualEditDialogProps) {
  const allComponents = useMemo(
    () => getEditableProtocolComponents(candidateContent),
    [candidateContent],
  );
  const [componentId, setComponentId] = useState<string>(
    allComponents[0]?.componentId ?? "",
  );
  const [editor, setEditor] = useState<EditableProtocolComponent | null>(null);
  const [predicateId, setPredicateId] = useState("");
  const titleId = useId();
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const component = allComponents.find((item) => item.componentId === componentId);
    setEditor(component ?? null);
    setPredicateId(component?.predicates[0]?.predicateId ?? "");
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
  const selectedPredicate = editor?.predicates.find((item) => item.predicateId === predicateId) ?? null;
  const canSubmit = editor !== null && editor.title.trim().length > 0 &&
    (selectedPredicate === null || (
      selectedPredicate.subject.trim().length > 0 &&
      selectedPredicate.attribute.trim().length > 0 &&
      (selectedPredicate.comparator === "exists" || selectedPredicate.valueText.trim().length > 0)
    ));

  const chooseComponent = (id: string) => {
    setComponentId(id);
    const component = allComponents.find((item) => item.componentId === id);
    setEditor(component ?? null);
    setPredicateId(component?.predicates[0]?.predicateId ?? "");
  };

  const updateEditor = (patch: Partial<EditableProtocolComponent>) => {
    setEditor((current) => current === null ? null : { ...current, ...patch });
  };

  const updatePredicate = (patch: Partial<EditablePredicate>) => {
    setEditor((current) => current === null ? null : {
      ...current,
      predicates: current.predicates.map((item) =>
        item.predicateId === predicateId ? { ...item, ...patch } : item,
      ),
    });
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
          选择子项后修订已有逻辑、条件、时间窗和资料要求。方案原文及定位保持只读；需要新增或重组条件时，请使用“基于反馈修订”。
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
                value={editor?.title ?? ""}
                onChange={(event) => updateEditor({ title: event.target.value })}
              />
            </label>
            {editor?.mainOperator !== null && (
              <label className="protocol-edit-dialog__field">
                <span>主条件之间的关系</span>
                <select
                  value={editor?.mainOperator ?? "all"}
                  disabled={editor?.mainOperator === "not"}
                  onChange={(event) => updateEditor({ mainOperator: event.target.value as "all" | "any" })}
                >
                  {editor?.mainOperator === "not" && <option value="not">不满足下列条件</option>}
                  <option value="all">以下条件全部满足</option>
                  <option value="any">以下任一条件满足</option>
                </select>
              </label>
            )}
            {editor?.exceptionOperator !== null && (
              <label className="protocol-edit-dialog__field">
                <span>例外条件之间的关系</span>
                <select
                  value={editor?.exceptionOperator ?? "all"}
                  disabled={editor?.exceptionOperator === "not"}
                  onChange={(event) => updateEditor({ exceptionOperator: event.target.value as "all" | "any" })}
                >
                  {editor?.exceptionOperator === "not" && <option value="not">不满足下列条件</option>}
                  <option value="all">以下条件全部满足</option>
                  <option value="any">以下任一条件满足</option>
                </select>
              </label>
            )}
            {(editor?.predicates.length ?? 0) > 0 && (
              <fieldset className="protocol-edit-dialog__group">
                <legend>具体判断条件</legend>
                <label className="protocol-edit-dialog__field">
                  <span>选择条件</span>
                  <select value={predicateId} onChange={(event) => setPredicateId(event.target.value)}>
                    {editor?.predicates.map((predicate, index) => (
                      <option key={predicate.predicateId} value={predicate.predicateId}>
                        {predicate.scope === "exception" ? "例外条件" : "主条件"} {index + 1} · {predicate.subject} {predicate.attribute}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedPredicate !== null && (
                  <>
                    <div className="protocol-edit-dialog__grid">
                      <label className="protocol-edit-dialog__field">
                        <span>判断对象</span>
                        <input value={selectedPredicate.subject} onChange={(event) => updatePredicate({ subject: event.target.value })} />
                      </label>
                      <label className="protocol-edit-dialog__field">
                        <span>判断项目</span>
                        <input value={selectedPredicate.attribute} onChange={(event) => updatePredicate({ attribute: event.target.value })} />
                      </label>
                      <label className="protocol-edit-dialog__field">
                        <span>比较关系</span>
                        <select value={selectedPredicate.comparator} onChange={(event) => updatePredicate({ comparator: event.target.value as EditablePredicate["comparator"] })}>
                          <option value="eq">等于</option><option value="ne">不等于</option>
                          <option value="gt">大于</option><option value="gte">大于或等于</option>
                          <option value="lt">小于</option><option value="lte">小于或等于</option>
                          <option value="in">属于其中之一</option><option value="not_in">不属于其中任何一项</option>
                          <option value="exists">存在该情况</option>
                        </select>
                      </label>
                      <label className="protocol-edit-dialog__field">
                        <span>界值或内容</span>
                        <input disabled={selectedPredicate.comparator === "exists"} value={selectedPredicate.valueText} onChange={(event) => updatePredicate({ valueText: event.target.value })} />
                      </label>
                      <label className="protocol-edit-dialog__field">
                        <span>单位</span>
                        <input value={selectedPredicate.unit} onChange={(event) => updatePredicate({ unit: event.target.value })} />
                      </label>
                    </div>
                    <label className="protocol-edit-dialog__check">
                      <input type="checkbox" checked={selectedPredicate.requiresProfessionalJudgment} onChange={(event) => updatePredicate({ requiresProfessionalJudgment: event.target.checked })} />
                      <span>该条件需要研究者进行专业判断</span>
                    </label>
                    {selectedPredicate.timeWindow !== null && (
                      <div className="protocol-edit-dialog__time">
                        <strong>时间窗</strong>
                        <div className="protocol-edit-dialog__grid">
                          <label className="protocol-edit-dialog__field"><span>参照时间点</span><select value={selectedPredicate.timeWindow.anchorType} onChange={(event) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, anchorType: event.target.value } })}><option value="icf_date">知情同意日期</option><option value="screening_date">筛选日期</option><option value="baseline_date">基线日期</option><option value="randomization_date">随机日期</option><option value="first_dose_date">首次用药日期</option><option value="event_date">相关事件日期</option></select></label>
                          <label className="protocol-edit-dialog__field"><span>方向</span><select value={selectedPredicate.timeWindow.direction} onChange={(event) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, direction: event.target.value as "before" | "after" | "on" } })}><option value="before">参照时间点之前</option><option value="after">参照时间点之后</option><option value="on">参照时间点当日</option></select></label>
                          <label className="protocol-edit-dialog__field"><span>最短间隔</span><input type="number" min="0" value={selectedPredicate.timeWindow.lowerValue} onChange={(event) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, lowerValue: event.target.value } })} /></label>
                          <label className="protocol-edit-dialog__field"><span>最长间隔</span><input type="number" min="0" value={selectedPredicate.timeWindow.upperValue} onChange={(event) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, upperValue: event.target.value } })} /></label>
                          <label className="protocol-edit-dialog__field"><span>最短间隔单位</span><TimeUnitSelect value={selectedPredicate.timeWindow.lowerUnit} onChange={(value) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, lowerUnit: value } })} /></label>
                          <label className="protocol-edit-dialog__field"><span>最长间隔单位</span><TimeUnitSelect value={selectedPredicate.timeWindow.upperUnit} onChange={(value) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, upperUnit: value } })} /></label>
                          <label className="protocol-edit-dialog__field"><span>半衰期倍数</span><input type="number" min="0" step="0.1" value={selectedPredicate.timeWindow.halfLifeMultiplier} onChange={(event) => updatePredicate({ timeWindow: { ...selectedPredicate.timeWindow!, halfLifeMultiplier: event.target.value } })} /></label>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </fieldset>
            )}
            {(editor?.requirements.length ?? 0) > 0 && (
              <fieldset className="protocol-edit-dialog__group">
                <legend>所需资料与完成阶段</legend>
                {editor?.requirements.map((requirement, index) => (
                  <div key={requirement.requirementId} className="protocol-edit-dialog__requirement">
                    <label className="protocol-edit-dialog__field"><span>资料要求 {index + 1}</span><textarea rows={2} value={requirement.description} onChange={(event) => updateEditor({ requirements: editor.requirements.map((item) => item.requirementId === requirement.requirementId ? { ...item, description: event.target.value } : item) })} /></label>
                    <label className="protocol-edit-dialog__field"><span>最迟应在</span><select value={requirement.dueStage} onChange={(event) => updateEditor({ requirements: editor.requirements.map((item) => item.requirementId === requirement.requirementId ? { ...item, dueStage: event.target.value as typeof item.dueStage } : item) })}><option value="pre_screening">预筛期</option><option value="screening">筛选期</option><option value="run_in">导入期</option><option value="baseline">基线期</option></select></label>
                  </div>
                ))}
              </fieldset>
            )}
            <div className="protocol-edit-dialog__source">
              <strong>方案原文（只读）</strong>
              {(editor?.sourceExcerpts.length ?? 0) === 0 ? <p>当前子项没有可显示的原文摘录。</p> : editor?.sourceExcerpts.map((excerpt, index) => <q key={`${index}-${excerpt}`}>{excerpt}</q>)}
            </div>
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
                patch: {
                  title: editor?.title.trim() ?? "",
                  mainOperator: editor?.mainOperator ?? null,
                  exceptionOperator: editor?.exceptionOperator ?? null,
                  predicate: selectedPredicate,
                  requirements: editor?.requirements ?? [],
                },
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

function TimeUnitSelect({ value, onChange }: { value: "day" | "week" | "month" | "year"; onChange: (value: "day" | "week" | "month" | "year") => void }) {
  return <select value={value} onChange={(event) => onChange(event.target.value as "day" | "week" | "month" | "year")}><option value="day">天</option><option value="week">周</option><option value="month">月</option><option value="year">年</option></select>;
}
