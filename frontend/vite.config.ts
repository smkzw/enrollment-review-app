import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { createHash } from "node:crypto";

// Phase 1: 无登录本地原型；fixture 资产已复制到 src/fixtures，无需 fs.allow。
// 开发环境将 /api 代理至本机 V2 服务（默认 8902），浏览器无需手动填写 API 地址。
// 单元测试（.test.ts）运行于 node 环境；组件测试（.test.tsx）在文件头使用
// `// @vitest-environment jsdom` 声明 DOM 环境（vitest 4 不再支持 environmentMatchGlobs）。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const v2ProxyTarget = env.VITE_V2_API_PROXY_TARGET ?? "http://127.0.0.1:8902";
  let assetBase = "/";

  return {
    plugins: [react(), {
      name: "enrollment-product-build-identity",
      apply: "build",
      configResolved(config) { assetBase = config.base; },
      generateBundle: { order: "post", handler(_options, bundle) {
        const effective = (key: string) => process.env[key] ?? env[key] ?? "";
        const files = Object.fromEntries(Object.entries(bundle).map(([name, output]) => [
          name, createHash("sha256").update(output.type === "chunk" ? output.code : output.source).digest("hex"),
        ]));
        this.emitFile({ type: "asset", fileName: "product-build.json", source: JSON.stringify({
          version: "enrollment-product-build/v1",
          interface_trial: mode === "test" || effective("VITE_ENROLLMENT_INTERFACE_TRIAL") === "true",
          protocol_stub: effective("VITE_PROTOCOL_WORKBENCH_STUB") === "true",
          api_base: effective("VITE_API_BASE"),
          asset_base: assetBase,
          files,
        }) });
      } },
    }],
    server: {
      proxy: {
        "/api": {
          target: v2ProxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      proxy: {
        "/api": {
          target: v2ProxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.{ts,tsx}"],
      setupFiles: ["src/test/setup.ts"],
    },
  };
});
