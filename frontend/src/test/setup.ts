/**
 * 组件测试环境：jest-dom 匹配器 + Testing Library 自动清理 + 方案工作台 stub 注入。
 * 只作用于 jsdom 组件测试；node 环境的纯映射/HTTP 契约测试不受影响。
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";
import {
  createProtocolWorkbenchStub,
  setProtocolWorkbenchRepository,
} from "../api/protocolWorkbenchRepository";
import { createCatalogTrial, setCatalogRepository } from "../api/catalog";

beforeEach(() => {
  setProtocolWorkbenchRepository(createProtocolWorkbenchStub());
  setCatalogRepository(createCatalogTrial());
});

afterEach(() => {
  setProtocolWorkbenchRepository(null);
  setCatalogRepository(null);
  cleanup();
});
