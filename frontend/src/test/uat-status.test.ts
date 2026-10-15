/**
 * 试用品版本标记测试：frontend/public/uat-status.json。
 * - 该文件是 V2 一键启动器识别「V2 试用服务」的版本标记：
 *   只有返回 service=enrollment-review-v2 的服务才被当作本试用系统，
 *   不能用「端口能访问」代替（旧版 FastAPI 服务也在本机监听端口）。
 * - 页面版本必须与中央状态清单的稳定中文页面版本一致。
 * - dist 中的标记必须存在并与源标记一致，桌面入口只提供预构建页面。
 */

import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { UAT_PAGE_VERSION } from "../app/uatTrialState";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const sourceMarkerFile = path.join(frontendRoot, "public/uat-status.json");
const distMarkerFile = path.join(frontendRoot, "dist/uat-status.json");

interface UatStatusMarker {
  service: string;
  name: string;
  pageVersion: string;
}

function readMarker(file: string): UatStatusMarker {
  return JSON.parse(readFileSync(file, "utf8")) as UatStatusMarker;
}

describe("试用品版本标记 uat-status.json", () => {
  it("源标记存在且字段完整（service/name/pageVersion 均为非空字符串）", () => {
    expect(existsSync(sourceMarkerFile)).toBe(true);
    const marker = readMarker(sourceMarkerFile);
    expect(marker.service.length).toBeGreaterThan(0);
    expect(marker.name.length).toBeGreaterThan(0);
    expect(marker.pageVersion.length).toBeGreaterThan(0);
  });

  it("服务身份必须是 enrollment-review-v2（与旧版服务区分）", () => {
    const marker = readMarker(sourceMarkerFile);
    expect(marker.service).toBe("enrollment-review-v2");
  });

  it("页面版本必须与中央状态清单 UAT_PAGE_VERSION 一致", () => {
    const marker = readMarker(sourceMarkerFile);
    expect(marker.pageVersion).toBe(UAT_PAGE_VERSION);
  });

  it("构建产物中的标记必须存在并与源标记一致", () => {
    expect(existsSync(distMarkerFile)).toBe(true);
    expect(readMarker(distMarkerFile)).toEqual(readMarker(sourceMarkerFile));
  });
});
