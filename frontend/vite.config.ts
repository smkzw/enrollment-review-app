import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Phase 1: 无登录本地原型；fixture 资产已复制到 src/fixtures，无需 fs.allow 或代理。
// 单元测试（.test.ts）运行于 node 环境；组件测试（.test.tsx）在文件头使用
// `// @vitest-environment jsdom` 声明 DOM 环境（vitest 4 不再支持 environmentMatchGlobs）。
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
});
