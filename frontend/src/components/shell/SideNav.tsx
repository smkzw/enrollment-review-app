/**
 * 侧栏导航：由 app/routes.tsx 注册表派生（spec: state-management §URL 状态）。
 * 只显示已实现入口；worker 03 注册页面后自动出现，不产生假入口。
 * 窄屏为抽屉：菜单按钮打开、遮罩/Escape 关闭、焦点返回触发按钮（合同 §7.1）。
 */

import { useEffect, useId, useRef, useState } from "react";
import {
  NAV_GROUPS,
  implementedRoutes,
} from "../../app/routes";
import { RouteLink } from "../../app/router";
import { BROWSE_ROUTES, useApplicationMode } from "../../app/applicationMode";
import {
  ActionsIcon,
  BoardIcon,
  CloseIcon,
  HelpIcon,
  MenuIcon,
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
                      title={route.description}
                    >
                      <span className="side-nav__icon" aria-hidden="true">
                        {routeIcon(route.path)}
                      </span>
                      <span>{route.label}</span>
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
  const [open, setOpen] = useState(false);
  const closeButtonId = useId();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  const close = () => {
    setOpen(false);
    menuButtonRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    // 打开时把焦点移入抽屉
    document.getElementById(closeButtonId)?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, closeButtonId]);

  return (
    <>
      <button
        ref={menuButtonRef}
        type="button"
        className="icon-button side-nav__menu-button"
        aria-label="打开菜单"
        title="打开菜单"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <MenuIcon />
      </button>
      {open && (
        <div
          className="side-nav__scrim"
          aria-hidden="true"
          onClick={close}
        />
      )}
      <aside
        ref={drawerRef}
        className={`side-nav${open ? " side-nav--open" : ""}`}
        aria-label="主要功能"
      >
        <div className="side-nav__head">
          <span className="side-nav__brand">入排审核工作台</span>
          <button
            id={closeButtonId}
            type="button"
            className="icon-button side-nav__close-button"
            aria-label="关闭菜单"
            title="关闭菜单"
            onClick={close}
          >
            <CloseIcon />
          </button>
        </div>
        <nav aria-label="主要功能">
          <NavList currentPath={currentPath} />
        </nav>
      </aside>
    </>
  );
}
