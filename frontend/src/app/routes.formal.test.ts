import { beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
});

describe("正式模式路由", () => {
  it("开放正式工作入口，仅将旧新建地址指向方案工作台", async () => {
    vi.doMock("./runtimeMode", () => ({
      isInterfaceTrialMode: () => false,
    }));
    const { APP_ROUTES, implementedRoutes } = await import("./routes");
    const navigation = implementedRoutes().map((route) => route.path);
    expect(navigation).toEqual([
      "/today",
      "/board",
      "/protocols",
      "/subjects",
      "/workbench",
      "/actions",
      "/reports",
      "/tasks",
      "/help",
    ]);
    for (const path of ["/today", "/board", "/actions"]) {
      expect(APP_ROUTES.find((route) => route.path === path)?.component).not.toBeNull();
    }
    for (const path of ["/projects/new", "/projects-new"]) {
      const route = APP_ROUTES.find((candidate) => candidate.path === path);
      expect(route?.component).toBeNull();
      expect(route?.redirectTo).toBe("/protocols");
    }
  });

  it("正式模式的工作台、报告和任务入口均已接入页面", async () => {
    vi.doMock("./runtimeMode", () => ({
      isInterfaceTrialMode: () => false,
    }));
    const { findRoute } = await import("./routes");
    expect(findRoute("/workbench")?.component).not.toBeNull();
    expect(findRoute("/reports")?.component).not.toBeNull();
    expect(findRoute("/tasks")?.component).not.toBeNull();
  });
});
