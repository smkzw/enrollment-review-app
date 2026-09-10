/**
 * Phase 5.7 Patient Profile 人工事实修订：真实浏览器走 v2 HTTP 路由契约，
 * 仅将网络响应替换为可解码的合成数据，不注入组件内部状态。
 *
 * 夹具语义：
 * - patient_profile_revision_id 指向本次修订生成的不可变档案；
 * - Phase 4 locator id 跨版本不可变；页码/摘录变更必须换新 locator id。
 */

import { expect, test } from "@playwright/test";
import {
  makeFactItem,
  makeLaneSection,
  makeLocator,
  makeRevision,
  PROFILE_LANE_ORDER,
} from "../src/api/patient-profile/patientProfileFixtures.ts";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";
import {
  EPISODE_ID,
  PROFILE_HASH,
  SUBJECT_ID,
  registerProfileRoutes,
} from "./profile-evidence-fixtures";

const GENERATED_TITLE = "血压 130/85 mmHg";
const GENERATED_EXCERPT = "基线血压 130/85 mmHg";
const PRE_CORRECTION_TITLE = "血压 120/80 mmHg";
const CITED_LOCATOR_ID = "loc-bp-1";
const REASON = "原始报告与当前记录不一致。";

function factSnapshot(value: string) {
  return {
    kind: "fact",
    fact_type: "vital_sign",
    profile_lane: "demographics",
    polarity: "affirmed",
    asserted_object: "血压",
    value,
    unit: "mmHg",
    date_range: {
      source_text: "2026-03",
      precision: "month",
      lower_bound: "2026-03-01",
      upper_bound: "2026-03-31",
    },
    source_strength: "current_study_chart_direct_record",
    assertion_object: "血压",
    assertion_text: `基线血压 ${value} mmHg`,
    supported_requirement_ids: ["req-1"],
  };
}

function lanesWithFact(
  title: string,
  value: string,
  locatorIds: string[],
  sourceId: string,
) {
  return PROFILE_LANE_ORDER.map((lane) => {
    if (lane === "demographics") {
      return makeLaneSection(lane, [
        makeFactItem({
          source_id: sourceId,
          title,
          value,
          locator_ids: locatorIds,
        }),
      ]);
    }
    return makeLaneSection(lane, []);
  });
}

/** 当前/修订生成后档案：引用的定位页码与摘录固定。 */
function generatedProfileWire() {
  return makeRevision({
    patient_profile_revision_id: "profile-revision-3",
    revision: 3,
    lanes: lanesWithFact(
      GENERATED_TITLE,
      "130/85",
      [CITED_LOCATOR_ID],
      "fact-source-2",
    ),
    evidence_locators: [
      makeLocator({
        locator_id: CITED_LOCATOR_ID,
        page_number: 1,
        excerpt: GENERATED_EXCERPT,
        precision_label: "原文区域",
      }),
    ],
  });
}

/**
 * 修订前档案保留旧实体和错误结构化值，但仍引用同一个不可变原文定位；
 * 本次人工修订正是根据该原文把 120/80 改为 130/85。
 */
function preCorrectionProfileWire() {
  return makeRevision({
    patient_profile_revision_id: "profile-revision-2",
    revision: 2,
    lanes: lanesWithFact(
      PRE_CORRECTION_TITLE,
      "120/80",
      [CITED_LOCATOR_ID],
      "fact-source-1",
    ),
    evidence_locators: [
      makeLocator({
        locator_id: CITED_LOCATOR_ID,
        page_number: 1,
        excerpt: GENERATED_EXCERPT,
        precision_label: "原文区域",
      }),
    ],
  });
}

function correctionImpact() {
  return {
    scope_kind: "node",
    scope_kind_label: "审核节点全部事实",
    fallback_reason: "将重新整理本审核节点全部事实",
    affected_locator_ids: [CITED_LOCATOR_ID],
    affected_document_ids: ["document-1"],
    affected_fact_ids: ["fact-source-1"],
    affected_event_ids: [],
    affected_exposure_ids: [],
    affected_conflict_group_ids: ["conflict-1"],
    affected_rule_link_ids: ["rule-1"],
    affected_expectation_ids: [],
    affected_profile_revision_ids: ["profile-revision-1"],
  };
}

test("宽屏 Profile 修订：草稿保留、只读预览、持久完成状态与追加历史", async ({ page }) => {
  const runtimeErrors = collectRuntimeErrors(page);
  let submitRequests = 0;
  let statusRequests = 0;
  let historyRequests = 0;
  let generatedRevisionRequests = 0;
  let preCorrectionRevisionRequests = 0;
  let correctionCompleted = false;

  await registerProfileRoutes(page);
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (
      method === "GET" &&
      url.includes(
        `/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/patient-profile`,
      ) &&
      !url.includes("/patient-profile/history")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          correctionCompleted ? generatedProfileWire() : preCorrectionProfileWire(),
        ),
      });
      return;
    }

    if (
      method === "GET" &&
      url.endsWith(`/subjects/${SUBJECT_ID}/patient-profile-revisions/profile-revision-3`)
    ) {
      generatedRevisionRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(generatedProfileWire()),
      });
      return;
    }

    if (
      method === "GET" &&
      url.endsWith(`/subjects/${SUBJECT_ID}/patient-profile-revisions/profile-revision-2`)
    ) {
      preCorrectionRevisionRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preCorrectionProfileWire()),
      });
      return;
    }

    if (method === "POST" && url.endsWith(`/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/fact-corrections/preview`)) {
      const body = request.postDataJSON() as Record<string, unknown>;
      expect(body.target_kind).toBe("fact");
      expect(body.target_id).toBe("fact-source-1");
      expect(body.locator_ids).toEqual([CITED_LOCATOR_ID]);
      expect(body.reason).toBe(REASON);
      expect(body.date_range).toEqual({
        source_text: "2026-03",
        precision: "month",
        lower_bound: "2026-03-01",
        upper_bound: "2026-03-31",
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          target_kind: "fact",
          target_kind_label: "事实",
          target_id: "fact-source-1",
          locator_ids: [CITED_LOCATOR_ID],
          old_snapshot: factSnapshot("120/80"),
          new_snapshot: factSnapshot("130/85"),
          impact: correctionImpact(),
        }),
      });
      return;
    }

    if (method === "POST" && url.endsWith(`/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/fact-corrections`)) {
      submitRequests += 1;
      await route.fulfill({
        status: submitRequests === 1 ? 201 : 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "job-correction-1",
          correction_id: "correction-1",
          created: submitRequests === 1,
          state: "queued",
          state_label: "等待处理",
          recovery_action: "请等待处理完成。",
        }),
      });
      return;
    }

    if (method === "GET" && url.endsWith("/api/v2/jobs/job-correction-1")) {
      statusRequests += 1;
      correctionCompleted = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "job-correction-1",
          state: "completed",
          state_label: "已完成",
          cancel_requested: false,
          progress_completed: 2,
          progress_total: 2,
          error_code: null,
          error_classification: null,
          retryable_scope: [],
          recovery_action: "档案已刷新。",
          created_at: "2026-08-23T08:00:00Z",
          updated_at: "2026-08-23T08:01:00Z",
          last_event_seq: 2,
        }),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/fact-corrections`)) {
      historyRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          items: historyRequests > 1
            ? [{
                correction_id: "correction-1",
                target_kind: "fact",
                target_kind_label: "事实",
                target_id: "fact-source-1",
                new_entity_id: "fact-source-2",
                patient_profile_revision_id: "profile-revision-3",
                patient_profile_revision: 3,
                reason: REASON,
                operator_id: "local-reviewer",
                locator_ids: [CITED_LOCATOR_ID],
                corrected_at: "2026-08-23T08:00:00Z",
                old_snapshot: factSnapshot("120/80"),
                new_snapshot: factSnapshot("130/85"),
                impact: correctionImpact(),
              }]
            : [],
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto(`/${PROFILE_HASH}`);
  await expect(page.getByRole("heading", { name: "受试者与资料", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: /首屏重点/ })).toBeVisible();
  await expect(page.getByText(PRE_CORRECTION_TITLE, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /核对并修订/ })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByRole("button", { name: /核对并修订/ }).click();
  const dialog = page.getByRole("dialog", { name: /核对并修订/ });
  await expect(dialog).toBeVisible();

  await dialog.getByRole("textbox", { name: "修订理由（必填）" }).fill(REASON);
  const valueInput = dialog.getByLabel("记录结果");
  await valueInput.fill("130/85");
  await dialog.getByRole("button", { name: "预览影响范围" }).click();
  await expect(dialog.getByRole("region", { name: "修改前" })).toBeVisible();
  await expect(dialog.getByRole("region", { name: "拟修改" })).toBeVisible();
  await expect(dialog.getByText("受影响历史档案", { exact: true })).toBeVisible();

  // 查看原文时修订工作区保持挂载：关闭证据后面板与预览仍在。
  await dialog.getByRole("button", { name: /查看第 1 页原文定位/ }).click();
  const evidence = page.getByLabel("该条目的原文证据与定位");
  await expect(evidence).toBeVisible();
  await expect(evidence.getByText("筛选病历.pdf")).toBeVisible();
  await expect(dialog).toBeHidden();
  await evidence.getByRole("button", { name: "关闭原文证据" }).click();
  await expect(evidence).toHaveCount(0);
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "修订理由（必填）" })).toHaveValue(REASON);
  await expect(dialog.getByRole("region", { name: "修改前" })).toBeVisible();
  await expect(dialog.getByRole("region", { name: "拟修改" })).toBeVisible();
  await expect(
    dialog.getByText("将重新整理本审核节点全部事实。既有档案版本保持不变，完成后只会生成新的当前档案版本。", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText("冲突组")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "提交修订" })).toBeDisabled();
  await page.screenshot({
    path: test.info().outputPath("correction-preview.png"),
    fullPage: false,
  });

  await dialog.getByRole("checkbox", { name: /我已核对/ }).check();
  await dialog.getByRole("button", { name: "提交修订" }).click();
  await expect.poll(() => submitRequests).toBe(1);
  await expect.poll(() => statusRequests).toBeGreaterThan(0);
  await expect(dialog.getByText("修订已完成，档案和修订记录正在刷新。")).toBeVisible();

  await dialog.getByRole("button", { name: "关闭并回到档案" }).click();
  await expect.poll(() => historyRequests).toBeGreaterThan(1);
  await expect(page.getByRole("button", { name: /修订记录/ })).toBeVisible();
  await page.getByRole("button", { name: /修订记录/ }).click();
  await expect.poll(() => generatedRevisionRequests).toBeGreaterThan(0);
  expect(preCorrectionRevisionRequests).toBe(0);
  await expect(page.getByText(REASON, { exact: true })).toBeVisible();
  await expect(page.getByText("本次修订形成档案第 3 版。", { exact: true })).toBeVisible();
  await expect(page.getByText(GENERATED_TITLE, { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText(`第 1 页 · 原文区域 · “${GENERATED_EXCERPT}”`, { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(PRE_CORRECTION_TITLE, { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "查看原文" }).click();
  const historyEvidence = page.getByLabel("该条目的原文证据与定位");
  await expect(historyEvidence).toBeVisible();
  await expect(historyEvidence.getByRole("heading", { name: GENERATED_TITLE })).toBeVisible();
  await expect(historyEvidence.getByText(PRE_CORRECTION_TITLE, { exact: true })).toHaveCount(0);

  await page.screenshot({
    path: test.info().outputPath("correction-history.png"),
    fullPage: false,
  });
  await expectNoPageOverflow(page);
  expect(runtimeErrors).toEqual([]);
});
