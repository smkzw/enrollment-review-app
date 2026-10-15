/**
 * 全局壳：响应式 Grid 布局（侧栏 + 顶栏 + 主工作区），无登录直达（合同 §3.1）。
 * 主工作区面向宽屏桌面；沿用页面级容器布局。
 * 路由解析：已实现页面懒加载渲染；正式模式的旧入口会先回到方案工作台。
 * 未知路径显示“未找到这个页面”。
 */

import { Suspense, useEffect } from "react";
import { RouteLink, navigate, useHashRoute } from "./router";
import { findRoute, isImplemented } from "./routes";
import { SideNav } from "../components/shell/SideNav";
import { TopBar } from "../components/shell/TopBar";
import { LoadingState } from "../components/shell/Feedback";
import { ApplicationModeNotice } from "../components/shell/ApplicationModeNotice";
import { ApplicationModeProvider, BROWSE_ROUTES, useApplicationMode } from "./applicationMode";


function NotFound() {
  return (
    <div className="feedback feedback--empty" role="status">
      <p className="feedback__title">未找到这个页面。</p>
      <p className="feedback__hint">
        地址可能有误，请返回方案工作台继续。
      </p>
      <RouteLink to="/protocols" className="button button--primary">
        返回方案工作台
      </RouteLink>
    </div>
  );
}

function RouteRedirect({ to }: { to: string }) {
  useEffect(() => {
    navigate(to);
  }, [to]);
  return <LoadingState />;
}

function CurrentPage() {
  const { path } = useHashRoute();
  const { canModify } = useApplicationMode();
  if (!canModify && !BROWSE_ROUTES.has(path)) return <RouteRedirect to="/reports" />;
  const route = findRoute(path);
  if (route === undefined) {
    return <NotFound />;
  }
  if (route.redirectTo !== undefined) {
    return <RouteRedirect to={route.redirectTo} />;
  }
  if (!isImplemented(route) || route.component === null) {
    return <NotFound />;
  }
  const Page = route.component;
  return (
    <Suspense fallback={<LoadingState />}>
      <Page />
    </Suspense>
  );
}

export function AppShell() {
  return <ApplicationModeProvider><ApplicationShellBody /></ApplicationModeProvider>;
}

function ApplicationShellBody() {
  const { path } = useHashRoute();
  const { canModify } = useApplicationMode();
  const route = findRoute(path);
  const positionLabel = route?.label ?? "未知页面";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <SideNav currentPath={path} />
      <div className="app-shell__main">
        <TopBar
          positionLabel={positionLabel}
          showProjectCreation={canModify && path === "/board"}
          showProjectContext={canModify && !new Set(["/projects/new", "/protocols"]).has(path)}
        />
        <main id="main-content" tabIndex={-1} className="app-shell__content">
          <ApplicationModeNotice />
          <CurrentPage />
        </main>
      </div>
    </div>
  );
}
