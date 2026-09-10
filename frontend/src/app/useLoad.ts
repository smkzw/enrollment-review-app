/**
 * 通用数据加载 Hook：统一加载/成功/失败状态（spec: type-safety §LoadState）。
 * 组件不直接解析错误信封；失败文案为自然中文，不展示堆栈或内部编号。
 */

import { useCallback, useEffect, useState } from "react";
import { StubApiError } from "../api";
import { ProtocolWorkbenchApiError } from "../api/protocolWorkbenchRepository";
import { EvidenceApiError } from "../api/evidence";
import { CatalogApiError } from "../api/catalog";
import { EligibilityReviewApiError } from "../api/eligibility-review";
import { UI_PHRASES } from "../domain/labels";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "success"; data: T; revision: number }
  | { status: "error"; message: string; retryable: boolean };

/** 面向用户的错误说明：已知业务错误用其中文消息，其余用统一恢复文案（合同 §8）。 */
function toUserMessage(error: unknown): string {
  if (error instanceof StubApiError) return error.message;
  if (error instanceof ProtocolWorkbenchApiError) return error.message;
  if (error instanceof EvidenceApiError) return error.message;
  if (error instanceof CatalogApiError) return error.message;
  if (error instanceof EligibilityReviewApiError) return error.message;
  return UI_PHRASES.temporarilyUnavailable;
}

export interface UseLoadResult<T> {
  state: LoadState<T>;
  retry: () => void;
}

export interface UseLoadOptions {
  enabled?: boolean;
}

/**
 * @param loader 数据加载函数（stub/真实 API 同一接口）
 * @param deps 重新加载的依赖；切换对象时旧请求会被丢弃，不会覆盖新页面
 */
export function useLoad<T>(
  loader: (signal?: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown>,
  options: UseLoadOptions = {},
): UseLoadResult<T> {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (options.enabled === false) {
      setState({ status: "loading" });
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setState({ status: "loading" });
    loader(controller.signal).then(
      (data) => {
        if (cancelled) return;
        setState({ status: "success", data, revision: 1 });
      },
      (error: unknown) => {
        if (cancelled) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({
          status: "error",
          message: toUserMessage(error),
          retryable: true,
        });
      },
    );
    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt, options.enabled]);

  const retry = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  return { state, retry };
}
