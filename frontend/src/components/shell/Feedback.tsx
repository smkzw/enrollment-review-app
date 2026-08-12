/**
 * 加载/空/失败反馈：显式区分状态（合同 §8），统一使用固定中文文案。
 */

import { UI_PHRASES } from "../../domain/labels";

export function LoadingState() {
  return (
    <div className="feedback" role="status" aria-live="polite">
      <span className="feedback__spinner" aria-hidden="true" />
      <span>{UI_PHRASES.loading}</span>
    </div>
  );
}

interface EmptyStateProps {
  message?: string;
  hint?: string;
}

export function EmptyState({ message, hint }: EmptyStateProps) {
  return (
    <div className="feedback feedback--empty">
      <p className="feedback__title">{message ?? UI_PHRASES.empty}</p>
      {hint !== undefined && <p className="feedback__hint">{hint}</p>}
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="feedback feedback--error" role="alert">
      <p className="feedback__title">{message}</p>
      <button type="button" className="button" onClick={onRetry}>
        重试
      </button>
    </div>
  );
}
