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

export type NavGroup = "work" | "tools" | "system";

export interface AppRoute {
  path: string;
  /** 一级入口中文名（可见文案，合同 §3.1） */
  label: string;
  /** 入口说明：导航 title 与 aria 用途 */
  description: string;
  group: NavGroup;
  /** null 表示该模块由后续工作项接入（本阶段不渲染假页面） */
  component: LazyExoticComponent<ComponentType> | null;
  /** 是否默认首屏 */
  defaultPath?: boolean;
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
    description: "今天需要优先处理的事项",
    group: "work",
    component: lazy(() => import("../pages/TodayPage")),
    defaultPath: true,
  },
  {
    path: "/board",
    label: "项目看板",
    description: "项目、受试者和各审核节点的全局状态",
    group: "work",
    component: lazy(() => import("../pages/ProjectBoardPage")),
  },
  {
    path: "/protocols",
    label: "方案工作台",
    description: "方案版本与规则解构",
    group: "work",
    component: lazy(() => import("../pages/ProtocolsPage")),
  },
  {
    path: "/subjects",
    label: "受试者与资料",
    description: "受试者资料与个例全景",
    group: "work",
    component: lazy(() => import("../pages/SubjectsPage")),
  },
  {
    path: "/workbench",
    label: "入排工作台",
    description: "分阶段入排审核、规则与原始证据",
    group: "work",
    component: lazy(() => import("../pages/WorkbenchPage")),
  },
  {
    path: "/actions",
    label: "行动中心",
    description: "补充资料、研究者判定与人工确认",
    group: "work",
    component: lazy(() => import("../pages/ActionsPage")),
  },
  {
    path: "/reports",
    label: "报告",
    description: "个例、中心与项目报告",
    group: "tools",
    component: lazy(() => import("../pages/ReportsPage")),
  },
  {
    path: "/tasks",
    label: "任务与系统",
    description: "资料整理任务与系统状态",
    group: "system",
    component: lazy(() => import("../pages/TasksPage")),
  },
  {
    path: "/help",
    label: "系统帮助",
    description: "流程化操作帮助",
    group: "system",
    component: lazy(() => import("../pages/HelpPage")),
  },
];

export function findRoute(path: string): AppRoute | undefined {
  return APP_ROUTES.find((route) => route.path === path);
}

export function isImplemented(route: AppRoute): boolean {
  return route.component !== null;
}

/** 已注册页面的入口：主导航只展示这些（未注册模块不出现假入口） */
export function implementedRoutes(): ReadonlyArray<AppRoute> {
  return APP_ROUTES.filter(isImplemented);
}

export function defaultRoute(): AppRoute {
  return (
    APP_ROUTES.find((route) => route.defaultPath === true) ?? APP_ROUTES[0]
  );
}
