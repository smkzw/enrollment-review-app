/**
 * 全局壳：响应式 Grid 布局（侧栏 + 顶栏 + 主工作区），无登录直达（合同 §3.1）。
 * 主工作区为容器查询上下文，页面级无横向滚动；窄屏侧栏收起为抽屉（SideNav 负责）。
 * 路由解析：已实现页面懒加载渲染；未注册模块显示明确的“尚未开放”说明；
 * 未知路径显示“未找到此页面”，两者都不伪装功能已完成。
 */

import { Suspense } from "react";
import { RouteLink, useHashRoute } from "./router";
import { findRoute, isImplemented } from "./routes";
import { SideNav } from "../components/shell/SideNav";
import { TopBar } from "../components/shell/TopBar";
import { LoadingState } from "../components/shell/Feedback";

/** 尚未开放模块：诚实说明，不渲染假页面 */
function ModulePending({ label }: { label: string }) {
  return (
    <div className="feedback feedback--empty" role="status">
      <p className="feedback__title">「{label}」模块将在后续版本中开放。</p>
      <p className="feedback__hint">
        本版本提供今日工作与项目看板两个工作区入口。
      </p>
      <RouteLink to="/today" className="button button--primary">
        返回今日工作
      </RouteLink>
    </div>
  );
}

function NotFound() {
  return (
    <div className="feedback feedback--empty" role="status">
      <p className="feedback__title">未找到这个页面。</p>
      <p className="feedback__hint">
        地址可能有误，或该入口尚未开放。可返回今日工作继续。
      </p>
      <RouteLink to="/today" className="button button--primary">
        返回今日工作
      </RouteLink>
    </div>
  );
}

function CurrentPage() {
  const { path } = useHashRoute();
  const route = findRoute(path);
  if (route === undefined) {
    return <NotFound />;
  }
  if (!isImplemented(route) || route.component === null) {
    return <ModulePending label={route.label} />;
  }
  const Page = route.component;
  return (
    <Suspense fallback={<LoadingState />}>
      <Page />
    </Suspense>
  );
}

export function AppShell() {
  const { path } = useHashRoute();
  const route = findRoute(path);
  const positionLabel = route?.label ?? "未知页面";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <SideNav currentPath={path} />
      <div className="app-shell__main">
        <TopBar positionLabel={positionLabel} />
        <main id="main-content" tabIndex={-1} className="app-shell__content">
          <CurrentPage />
        </main>
      </div>
    </div>
  );
}
