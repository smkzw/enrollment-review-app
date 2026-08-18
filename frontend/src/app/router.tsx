/**
 * 极简 hash 路由：URL 保存可分享/恢复的工作上下文（spec: state-management §URL 状态）。
 * - Phase 0.5 未锁定路由库，本地单机产品用 hash 避免深链刷新 404，且不引入运行时依赖。
 * - 页面切换（navigate）产生历史记录；筛选/排序参数（updateParams）用 replaceState 静默更新，
 *   不污染后退历史，也不触发跳顶。
 * - 返回上一级页面时，URL 中携带的筛选/排序/阶段参数自动恢复（合同 §4.1/7.2）。
 */

import { useSyncExternalStore, type ReactNode } from "react";

export interface RouteLocation {
  /** 例如 "/today"、"/board"、"/workbench" */
  path: string;
  /** 查询参数（阶段、筛选、排序、受试者等） */
  params: URLSearchParams;
}

/** 默认首屏：今日工作（合同 §3.1，无登录直达） */
export const DEFAULT_PATH = "/today";

export type RouteParams = Record<string, string | null | undefined>;

export function parseHash(): RouteLocation {
  const raw = window.location.hash.replace(/^#/, "");
  if (raw === "" && window.location.pathname !== "/") {
    return {
      path: window.location.pathname,
      params: new URLSearchParams(window.location.search),
    };
  }
  const questionIndex = raw.indexOf("?");
  const pathPart = questionIndex === -1 ? raw : raw.slice(0, questionIndex);
  const queryPart = questionIndex === -1 ? "" : raw.slice(questionIndex + 1);
  const path = pathPart === "" ? DEFAULT_PATH : pathPart;
  return { path, params: new URLSearchParams(queryPart) };
}

let current: RouteLocation = parseHash();

const listeners = new Set<() => void>();

function emit(): void {
  current = parseHash();
  for (const listener of listeners) listener();
}

// 浏览器前进/后退（hash 条目）与外部 hash 变化驱动路由更新；
// replaceState 产生的静默参数更新由 updateParams 直接 emit。
if (typeof window !== "undefined") {
  window.addEventListener("hashchange", emit);
  window.addEventListener("popstate", emit);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getRoute(): RouteLocation {
  return current;
}

/** 订阅当前 hash 路由；path/params 变化时重渲染。 */
export function useHashRoute(): RouteLocation {
  return useSyncExternalStore(subscribe, getRoute, getRoute);
}

export function buildHash(
  path: string,
  params?: RouteParams | URLSearchParams,
): string {
  const search =
    params instanceof URLSearchParams
      ? params
      : new URLSearchParams(
          Object.entries(params ?? {}).filter(
            (entry): entry is [string, string] =>
              entry[1] !== null && entry[1] !== undefined,
          ),
        );
  const query = [...search.entries()].length > 0 ? `?${search.toString()}` : "";
  return `#${path}${query}`;
}

/** 页面切换：写入 hash，产生历史记录；hashchange 事件驱动订阅者更新。 */
export function navigate(path: string, params?: RouteParams): void {
  const target = buildHash(path, params);
  if (window.location.hash === target) return;
  window.location.hash = target;
}

/**
 * 静默更新查询参数（筛选/排序/阶段），不产生新历史记录、不触发 hashchange。
 * 值传 null/undefined 表示删除该参数。
 */
export function updateParams(
  patch: RouteParams,
  path: string = getRoute().path,
): void {
  const next = new URLSearchParams(getRoute().params);
  for (const [key, value] of Object.entries(patch)) {
    if (value === null || value === undefined) next.delete(key);
    else next.set(key, value);
  }
  const target = buildHash(path, next);
  if (window.location.hash === target) return;
  window.history.replaceState(null, "", target);
  emit();
}

export interface RouteLinkProps {
  to: string;
  params?: RouteParams;
  className?: string;
  ariaLabel?: string;
  ariaCurrent?: "page" | "step" | "location" | "date" | "time" | "true" | "false";
  title?: string;
  children: ReactNode;
}

/** 带 href 的路由链接：保留原生锚点语义（中键/右键/新标签），左键点击走 navigate() 更新路由。 */
export function RouteLink({
  to,
  params,
  className,
  ariaLabel,
  ariaCurrent,
  title,
  children,
}: RouteLinkProps) {
  return (
    <a
      href={buildHash(to, params)}
      className={className}
      aria-label={ariaLabel}
      aria-current={ariaCurrent}
      title={title}
      onClick={(event) => {
        // 仅拦截普通左键点击；中键/新标签/修饰键保留浏览器默认行为
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        navigate(to, params);
      }}
    >
      {children}
    </a>
  );
}
