/**
 * Phase 5.8 真实隔离项目浏览器验收编排。
 *
 * 覆盖 D001-II 与 MG-K10-SAR-III：
 * 项目创建 → 方案期别选择 → 受试者资料上传 → 真实 OCR →
 * 元数据/风险核对 → 生成并启用完整处理修订 → 真实个例档案整理任务 →
 * 成功 Profile → 原文定位 → 不可变历史回看。
 *
 * 门控：
 * - 仅当 PHASE5_ISOLATED_DATASET_ROOT 显式存在时才可能运行；否则 skip。
 * - 角色必须为 independent_tester（执行者不得替代）。
 * - 禁止 fixture 路由与直接 API 状态伪造；启用资料不等于已有 Profile。
 * - 真实 OCR/模型必须通过 PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL=1 显式启用，否则配置失败。
 *
 * 本文件只产出 browser_tester 机器可读观察，不给出入排结论，不声称最终验收。
 */

import { expect, test } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";
import {
  PHASE5_ISOLATED_DATASET_ENV,
  assertFreshDatabaseIdentity,
  assertNoForbiddenUiMarkers,
  installFixtureRouteTrap,
  rejectFixtureRouteRegistration,
  resolveRealAcceptanceConfig,
  stepCreateProjectAndSelectPhase,
  stepPatientProfileAndLocator,
  stepRealNormalizer,
  stepUploadSubjectMaterials,
  writeRunSummary,
  BrowserObservationSink,
  type RealAcceptanceConfig,
} from "./phase5-real-acceptance-support";

const resolved = resolveRealAcceptanceConfig();

test.describe("Phase 5.8 真实隔离浏览器验收编排", () => {
  test.skip(
    resolved.status === "disabled",
    resolved.status === "disabled"
      ? resolved.reason
      : `仅在显式设置 ${PHASE5_ISOLATED_DATASET_ENV} 时运行真实隔离验收。`,
  );

  test.beforeAll(() => {
    // disabled 时由 test.skip 跳过；此处只对“半开配置”大声失败，禁止降级 fixture。
    if (resolved.status === "misconfigured") {
      throw new Error(resolved.reason);
    }
  });

  test("拒绝 fixture 路由注册（防冒充）", () => {
    expect(() => rejectFixtureRouteRegistration("registerProfileRoutes")).toThrow(
      /禁止注册 fixture 路由/,
    );
    expect(() => rejectFixtureRouteRegistration("registerEvidenceRoutes")).toThrow(
      /禁止注册 fixture 路由/,
    );
  });

  test("D001-II 与 MG-K10-SAR-III 真实验收编排", async ({ page }, testInfo) => {
    test.setTimeout(
      resolved.status === "ready" && resolved.config.allowLiveModel
        ? 6_000_000
        : 120_000,
    );

    if (resolved.status !== "ready") {
      throw new Error("配置未就绪");
    }
    const config: RealAcceptanceConfig = resolved.config;
    const runtimeErrors = collectRuntimeErrors(page);
    await installFixtureRouteTrap(page);

    // 独立测试者入口：直达真实前端，不走 build:e2e 试用 stub。
    await page.goto(config.baseUrl);
    await assertNoForbiddenUiMarkers(page);

    const verifier = `playwright:${testInfo.project.name}:independent_tester`;
    const sinks = config.cases.map(
      (caseRow) => new BrowserObservationSink(config, caseRow, verifier),
    );

    // 所有项目创建前共同证明空数据库；第二个病例不得把第一个新建项目误判成旧数据。
    for (const sink of sinks) {
      await assertFreshDatabaseIdentity(page, config, sink);
    }

    for (const [index, caseRow] of config.cases.entries()) {
      const sink = sinks[index]!;

      sink.record({
        step_id: "gate.fixture_routes",
        source_locator: "suite-policy",
        artifact: sink.path,
        observed_result: "fixture route registration rejected by suite policy; live API required",
        disposition: "pass",
        notes: "结构性门禁通过 ≠ 临床正确。",
      });

      const project = await stepCreateProjectAndSelectPhase(
        page,
        config,
        caseRow,
        sink,
      );
      const ids = await stepUploadSubjectMaterials(
        page,
        config,
        caseRow,
        sink,
        project,
      );
      await stepRealNormalizer(page, config, sink);
      await stepPatientProfileAndLocator(page, config, caseRow, sink, ids);

      expect(sink.all().length).toBeGreaterThan(0);
      expect(sink.all().every((row) => row.evidence_class === "browser_tester")).toBe(true);
      expect(sink.all().every((row) => row.role === "independent_tester")).toBe(true);
    }

    const summaryPath = writeRunSummary(config, testInfo, sinks);
    await testInfo.attach("phase5-browser-run-summary", {
      path: summaryPath,
      contentType: "application/json",
    });

    await expectNoPageOverflow(page);
    expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual([]);
  });
});
