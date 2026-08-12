/**
 * 组件测试环境：jest-dom 匹配器 + Testing Library 自动清理。
 * 只作用于 jsdom 组件测试；node 环境的纯映射测试不受影响。
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
