/**
 * 全局一级入口注册表（合同 §3.1）。
 * - 主导航由本表派生：只有注册了页面组件的入口才出现在导航中，不产生假入口。
 * - URL 契约：
 *   - /today            今日工作
 *   - /board            项目看板（?stage=&status=&sort=&q=）
 *   - /workbench        入排工作台（?episode=<ReviewEpisodeId>）——受试者×审核节点直达入口
 *   - /subjects         受试者与 Patient Profile（?subject=&stage=）
 *   - /protocols        方案工作台
 *   - /actions          行动中心
 *   - /reports          报告
 *   - /tasks            任务与系统（?job=）
 *   - /help             系统帮助
 * - worker 03 接入方式：把对应入口的 component 从 null 改为 lazy(() => import("../pages/XxxPage"))，
 *   导航与路由自动生效；入口顺序、分组和中文名已按合同固定，不要改动。
 */

import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { isInterfaceTrialMode } from "./runtimeMode";

const interfaceTrial = isInterfaceTrialMode();

export type NavGroup = "work" | "tools" | "system";

export interface AppRoute {
  path: string;
  /** 一级入口中文名（可见文案，合同 §3.1） */
  label: string;
  /** 入口说明：导航 title 与 aria 用途 */
  description: string;
  group: NavGroup;
  /** null 表示该地址只作为正式模式跳转入口 */
  component: LazyExoticComponent<ComponentType> | null;
  /** 正式模式下将深链带回已接入的真实工作区 */
  redirectTo?: string;
  /** 是否默认首屏 */
  defaultPath?: boolean;
  /** 仅作为上下文页面访问，不在主导航重复占位 */
  showInNavigation?: boolean;
}

export const NAV_GROUPS: ReadonlyArray<{ id: NavGroup; label: string }> = [
  { id: "work", label: "工作区" },
  { id: "tools", label: "工具与报告" },
  { id: "system", label: "系统" },
];

export const APP_ROUTES: readonly AppRoute[] = [
  {
    path: "/today",
    label: "今日工作",
    description: "待办理事项与近期审核记录",
    group: "work",
    component: interfaceTrial ? lazy(() => import("../pages/TodayPage")) : lazy(() => import("../pages/ReviewTodayPage")),
    defaultPath: true,
    showInNavigation: true,
  },
  {
    path: "/board",
    label: "项目看板",
    description: "项目、受试者和各审核节点的全局状态",
    group: "work",
    component: interfaceTrial ? lazy(() => import("../pages/ProjectBoardPage")) : lazy(() => import("../pages/ReviewProjectPage")),
    showInNavigation: true,
  },
  {
    path: "/projects/new",
    label: "新建项目",
    description: "从方案确认研究期别并选择独立审核节点",
    group: "work",
    component: interfaceTrial ? lazy(() => import("../pages/ProjectCreationPage")) : null,
    redirectTo: interfaceTrial ? undefined : "/protocols",
    showInNavigation: false,
  },
  {
    path: "/projects-new",
    label: "新建项目",
    description: "从方案确认研究期别并选择独立审核节点",
    group: "work",
    component: null,
    redirectTo: interfaceTrial ? undefined : "/protocols",
    showInNavigation: false,
  },
  {
    path: "/protocols",
    label: "方案工作台",
    description: "方案版本与规则解构",
    group: "work",
    component: lazy(() => import("../pages/ProtocolsPage")),
    defaultPath: false,
  },
  {
    path: "/subjects",
    label: "受试者与资料",
    description: "受试者资料与个例全景",
    group: "work",
    component: interfaceTrial
      ? lazy(() => import("../pages/SubjectsPage"))
      : lazy(() => import("../pages/SubjectsCatalogPage")),
  },
  {
    path: "/profiles",
    label: "个例档案",
    description: "当前受试者审核节点的原文关联档案",
    group: "work",
    component: lazy(() => import("../pages/SubjectsPage")),
    showInNavigation: false,
  },
  {
    path: "/subjects/:subjectId/evidence",
    label: "证据工作台",
    description: "受试者审核节点的资料上传与证据工作台",
    group: "work",
    component: lazy(() => import("../pages/EvidencePage")),
    showInNavigation: false,
  },
  {
    path: "/workbench",
    label: "入排工作台",
    description: "分阶段入排审核、规则与原始证据",
    group: "work",
    component: interfaceTrial
      ? lazy(() => import("../pages/WorkbenchPage"))
      : lazy(() => import("../pages/EligibilityWorkbenchPage")),
    showInNavigation: true,
  },
  {
    path: "/actions",
    label: "行动中心",
    description: "补充资料、研究者判定与人工确认",
    group: "work",
    component: interfaceTrial ? lazy(() => import("../pages/ActionsPage")) : lazy(() => import("../pages/ReviewActionsPage")),
    showInNavigation: true,
  },
  {
    path: "/reports",
    label: "报告",
    description: "入排审核结果打印版",
    group: "tools",
    component: lazy(() => import("../pages/ReportsPage")),
    showInNavigation: true,
  },
  {
    path: "/tasks",
    label: "任务与系统",
    description: "资料整理任务与系统状态",
    group: "system",
    component: lazy(() => import("../pages/TasksPage")),
    showInNavigation: true,
  },
  {
    path: "/help",
    label: "系统帮助",
    description: "流程化帮助",
    group: "system",
    component: lazy(() => import("../pages/HelpPage")),
  },
];

/**
 * 参数化路由匹配：pattern 中的 ``:param`` 段匹配任意非空段。
 * 返回捕获的参数表；不匹配返回 null。
 */
export function matchRouteParams(
  path: string,
  pattern: string,
): Record<string, string> | null {
  if (!pattern.includes(":")) return null;
  const patternParts = pattern.split("/");
  const pathParts = path.split("/");
  if (patternParts.length !== pathParts.length) return null;
  const params: Record<string, string> = {};
  for (let index = 0; index < patternParts.length; index += 1) {
    const patternPart = patternParts[index];
    if (patternPart.startsWith(":")) {
      const value = pathParts[index];
      if (value.length === 0) return null;
      params[patternPart.slice(1)] = value;
    } else if (patternPart !== pathParts[index]) {
      return null;
    }
  }
  return params;
}

export function findRoute(path: string): AppRoute | undefined {
  const exact = APP_ROUTES.find((route) => route.path === path);
  if (exact !== undefined) return exact;
  // 参数化路由（/subjects/:subjectId/evidence）：无顶级导航项，按模式匹配。
  return APP_ROUTES.find(
    (route) => route.path.includes(":") && matchRouteParams(path, route.path) !== null,
  );
}

export function isImplemented(route: AppRoute): boolean {
  return route.component !== null;
}

/** 已注册页面的入口：主导航只展示这些（未注册模块不出现假入口） */
export function implementedRoutes(): ReadonlyArray<AppRoute> {
  return APP_ROUTES.filter(
    (route) => isImplemented(route) && route.showInNavigation !== false,
  );
}

export function defaultRoute(): AppRoute {
  return (
    APP_ROUTES.find((route) => route.defaultPath === true) ?? APP_ROUTES[0]
  );
}
