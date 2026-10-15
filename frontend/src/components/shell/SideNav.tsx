/**
 * 侧栏导航：由 app/routes.tsx 注册表派生（spec: state-management §URL 状态）。
 * 只显示已实现入口；worker 03 注册页面后自动出现，不产生假入口。
 * 宽屏默认图标轨；悬停或键盘聚焦时叠加展开，也可固定展开。
 */

import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import {
  NAV_GROUPS,
  implementedRoutes,
} from "../../app/routes";
import { RouteLink } from "../../app/router";
import { BROWSE_ROUTES, useApplicationMode } from "../../app/applicationMode";
import {
  ActionsIcon,
  BoardIcon,
  HelpIcon,
  ProtocolIcon,
  ReportsIcon,
  SubjectsIcon,
  TasksIcon,
  TodayIcon,
  WorkbenchIcon,
} from "./icons";
import type { ReactNode } from "react";

function routeIcon(path: string): ReactNode {
  switch (path) {
    case "/today":
      return <TodayIcon size={16} />;
    case "/board":
      return <BoardIcon size={16} />;
    case "/protocols":
      return <ProtocolIcon size={16} />;
    case "/subjects":
      return <SubjectsIcon size={16} />;
    case "/workbench":
      return <WorkbenchIcon size={16} />;
    case "/actions":
      return <ActionsIcon size={16} />;
    case "/reports":
      return <ReportsIcon size={16} />;
    case "/tasks":
      return <TasksIcon size={16} />;
    case "/help":
      return <HelpIcon size={16} />;
    default:
      return null;
  }
}

interface NavListProps {
  currentPath: string;
}

function NavList({ currentPath }: NavListProps) {
  const { canModify } = useApplicationMode();
  const routes = implementedRoutes().filter((route) => canModify || BROWSE_ROUTES.has(route.path));
  return (
    <ul className="side-nav__list">
      {NAV_GROUPS.map((group) => {
        const items = routes.filter((route) => route.group === group.id);
        if (items.length === 0) return null;
        return (
          <li key={group.id} className="side-nav__group">
            <h2 className="side-nav__group-title">{group.label}</h2>
            <ul>
              {items.map((route) => {
                const active = currentPath === route.path;
                return (
                  <li key={route.path}>
                    <RouteLink
                      to={route.path}
                      className={`side-nav__item${active ? " side-nav__item--active" : ""}`}
                      ariaCurrent={active ? "page" : undefined}
                      title={route.label}
                      ariaLabel={route.label}
                    >
                      <span className="side-nav__icon" aria-hidden="true">
                        {routeIcon(route.path)}
                      </span>
                      <span className="side-nav__label">{route.label}</span>
                    </RouteLink>
                  </li>
                );
              })}
            </ul>
          </li>
        );
      })}
    </ul>
  );
}

interface SideNavProps {
  currentPath: string;
}

export function SideNav({ currentPath }: SideNavProps) {
  const [pinned, setPinned] = useState(false);

  return (
      <aside
        className={`side-nav${pinned ? " side-nav--pinned" : ""}`}
        aria-label="主要功能"
      >
        <div className="side-nav__head">
          <span className="side-nav__brand">入排审核工作台</span>
          <button
            type="button"
            className="icon-button side-nav__pin"
            aria-label={pinned ? "收起导航" : "固定展开导航"}
            title={pinned ? "收起导航" : "固定展开导航"}
            aria-expanded={pinned}
            onClick={() => setPinned(value => !value)}
          >
            {pinned ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}
          </button>
        </div>
        <nav aria-label="主要功能">
          <NavList currentPath={currentPath} />
        </nav>
      </aside>
  );
}
