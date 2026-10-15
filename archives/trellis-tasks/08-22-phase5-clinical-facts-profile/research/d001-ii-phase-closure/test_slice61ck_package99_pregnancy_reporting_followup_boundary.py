#!/usr/bin/env python3
"""Slice61ck model-free source-closure regressions.

Locks the D001 II package 99 pregnancy reporting / role-divergent
discontinuation / AE-SAE branch / follow-up boundary (frozen plan
package 99: body.p1158-p1167) to its authoritative sources before any
semantic replay decision:

- config contract and role partition: 10 owned refs body.p1158-p1167
  (p1158/p1159/p1164 structural-only; remaining 7 post_treatment_execution);
  attached refs body.p986 (pkg77 AE def) and body.p996 (pkg78 SAE def)
  stay read-only for AE/SAE branch closure
- immutable frozen digests of parent-approved positive semantics fields;
  any append / delete / reorder / rewrite reports POSITIVE_SEMANTICS_DRIFT
- whole-config fingerprint check so config+test cannot drift together
- clinical mutation families: suspected-pregnancy trigger, last-dose 3-month
  window, confirm-then-24h report order, role-divergent discontinuation,
  pregnancy-not-AE / elective-abortion-not-AE, decision owner, later-of
  follow-up endpoint, conditional fetal assessment, neonatal SAE 24h,
  update reporting, and package 77/78/98/100 ownership boundaries
- zero candidates for owned+attached; claims_complete=false

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE_CLOSURE = Path(__file__).resolve().parent
CONFIG_DIR = PHASE_CLOSURE / "configs"
CONFIG_PATH = (
    CONFIG_DIR
    / "representative_group_package99_pregnancy_reporting_followup_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61ck-package99-pregnancy-reporting-followup-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package99-pregnancy-reporting-followup-boundary"
)
FREEZE_DIR = (
    ROOT / "artifacts" / "phase5-slice59i-d001-phase-table-caption-rebaseline-20260827"
)
PLAN_PATH = FREEZE_DIR / "frozen_phase_plan.json"
COVERAGE_PATH = FREEZE_DIR / "coverage_manifest.json"
STRUCTURE_BLOB_PATH = (
    FREEZE_DIR
    / "structure"
    / "blobs"
    / "protocol_blocks"
    / "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json"
)
CATALOG_DIR = ROOT / "artifacts" / "phase5-slice61bl-procedure-footnote-scope-20260829"
MATRIX_PATH = (
    ROOT
    / ".trellis"
    / "tasks"
    / "08-22-phase5-clinical-facts-profile"
    / "research"
    / "d001-ii-official-flow-controls.json"
)

EXPECTED_DOCX_SHA256 = "362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98"
EXPECTED_PLAN_SHA256 = "f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250"
EXPECTED_STRUCTURE_SHA256 = (
    "3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d"
)
EXPECTED_CATALOG_SHA256 = (
    "29f4b49bb039790777c6fec81e3a86d82fb0400fe1a6a40a97491ee3e43bf061"
)
# Independent whole-config fingerprint (Worker 01 artifact). Must not be
# recomputed from the config under test inside the issue scanner.
EXPECTED_CONFIG_SHA256 = (
    "1a10430ffb4ae300533b2715ef0a018aaf0060457b516061c45f6a3f88a931bd"
)

PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
PACKAGE_99_ORDINAL = 99
PACKAGE_99_ID = "pap-89963654c275db70b405733e"
PACKAGE_98_ORDINAL = 98
PACKAGE_98_ID = "pap-efb197cc99ae53ab03b9a1a2"
PACKAGE_100_ORDINAL = 100
PACKAGE_100_ID = "pap-101e8c3b73a8b084cdcfa140"
PACKAGE_77_ORDINAL = 77
PACKAGE_78_ORDINAL = 78

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1158, 1168)]
ATTACHED_REFS = ["body.p986", "body.p996"]
STRUCTURAL_REFS = ["body.p1158", "body.p1159", "body.p1164"]
SEMANTIC_OWNED_REFS = [ref for ref in OWNED_REFS if ref not in STRUCTURAL_REFS]
POSITIVE_REFS = OWNED_REFS + ATTACHED_REFS

PKG98_SPAN_REFS = ['body.p1150', 'body.p1151', 'body.p1152', 'body.p1153', 'body.p1154', 'body.p1155', 'body.p1156', 'body.p1157']
PKG100_SPAN_REFS = ['body.p1168', 'body.p1169', 'body.p1170', 'body.p1173', 'body.p1174', 'body.p1175', 'body.p1176', 'body.p1177', 'body.p1179']
PKG97_SPAN_REFS = ['body.p1138', 'body.p1139', 'body.p1140', 'body.p1141', 'body.p1142', 'body.p1143', 'body.p1144', 'body.p1145', 'body.p1146', 'body.p1147', 'body.p1148', 'body.p1149']
PKG96_SPAN_REFS = ['body.p1136', 'body.p1137']
PKG95_SPAN_REFS = ['body.p1124', 'body.p1125', 'body.p1126', 'body.p1127', 'body.p1128', 'body.p1129', 'body.p1130', 'body.p1131', 'body.p1132', 'body.p1133', 'body.p1134', 'body.p1135']
PKG94_SPAN_REFS = ['body.p1113', 'body.p1114', 'body.p1115', 'body.p1116', 'body.p1117', 'body.p1118', 'body.p1119', 'body.p1120', 'body.p1121', 'body.p1122', 'body.p1123']
PKG93_SPAN_REFS = ['body.p1102', 'body.p1103', 'body.p1104', 'body.p1105', 'body.p1106', 'body.p1107', 'body.p1108', 'body.p1109', 'body.p1110', 'body.p1111', 'body.p1112']
PKG92_SPAN_REFS = ['body.p1098', 'body.p1099', 'body.p1100', 'body.p1101']
PKG91_SPAN_REFS = ['body.t14.r0', 'body.t14.r1', 'body.t14.r2', 'body.t14.r3', 'body.t14.r4', 'body.t14.r5', 'body.t14.r6', 'body.t14.r7']
PKG90_SPAN_REFS = ['body.p1087', 'body.p1088', 'body.p1089', 'body.p1090', 'body.p1091', 'body.p1092', 'body.p1093', 'body.p1094', 'body.p1095', 'body.p1096', 'body.p1097']
PKG89_SPAN_REFS = ['body.t13.r0', 'body.t13.r1', 'body.t13.r2', 'body.t13.r3', 'body.t13.r4', 'body.t13.r5']
PKG88_SPAN_REFS = ['body.p1084', 'body.p1085', 'body.p1086']
PKG87_SPAN_REFS = ['body.p1074', 'body.p1075', 'body.p1076', 'body.p1077', 'body.p1078', 'body.p1079', 'body.p1080', 'body.p1081', 'body.p1082', 'body.p1083']
PKG82_SPAN_REFS = ['body.t12.r0', 'body.t12.r1', 'body.t12.r2', 'body.t12.r3', 'body.t12.r4']
PKG80_SPAN_REFS = ['body.p1015', 'body.p1016', 'body.p1017', 'body.p1018', 'body.p1019', 'body.p1020', 'body.p1021', 'body.p1022', 'body.p1023', 'body.p1024', 'body.p1025', 'body.p1026']
PKG79_SPAN_REFS = ['body.p1007', 'body.p1008', 'body.p1009', 'body.p1010', 'body.p1011', 'body.p1012', 'body.p1013', 'body.p1014']
PKG78_NON_ATTACHED = ['body.p995', 'body.p997', 'body.p998', 'body.p999', 'body.p1000', 'body.p1001', 'body.p1002', 'body.p1003', 'body.p1004', 'body.p1005', 'body.p1006']
PKG77_NON_ATTACHED = ['body.p985', 'body.p987', 'body.p988', 'body.p989', 'body.p990', 'body.p991', 'body.p992', 'body.p993', 'body.p994']

OWNED_EXCERPT_BY_REF = {
    "body.p1158": "妊娠",
    "body.p1159": "妊娠事件的报告要求",
    "body.p1160": "若女性参与者或男性参与者的女性伴侣在研究期间或CMS-D001片末次给药后3个月内怀孕或怀疑可能妊娠（如停经或经期推迟），应立即告知研究者，研究者必须尽快进行检查确认，确认发生妊娠的，研究者应在确认后24小时填写《妊娠事件报告表》，签名并签署日期，而后立即书面报告给申办者或其指定人员（即，获知事件后不超过24小时）。同时，研究者根据中心伦理的要求进行上报。",
    "body.p1161": "女性参与者在CMS-D001片首次给药之后的研究期间发生妊娠后，应立即停用研究药物，并及时进行记录、报告及随访。男性参与者的女性伴侣发生妊娠后，不要求男性参与者停用试验用药品，但需要对其女性伴侣按照女性参与者发生妊娠的处理方式进行记录、报告及随访。",
    "body.p1162": "单纯的妊娠事件本身不属于不良事件，不应记录在eCRF不良事件上，但如果发生妊娠相关并发症或妊娠的结果符合不良事件定义，则还需按照不良事件进行管理，例如自然流产、因医学及健康原因导致的人工流产、死胎、新生儿严重不良事件（不限于新生儿死亡、先天性异常或者出生缺陷）等。",
    "body.p1163": "妊娠参与者在妊娠期间经历的SAE，要求以《SAE报告表》的方式立即报告（即，获知事件后不超过24小时）。没有妊娠相关并发症的选择性流产不视为不良事件。",
    "body.p1164": "妊娠事件的随访",
    "body.p1165": "研究者应该根据用药情况，严谨地与参与者交流，告知她/他试验用药品对于孕妇及胎儿可能的影响和风险，并由参与者及其伴侣自行决定是否终止妊娠或继续妊娠。如果参与者或其伴侣决定继续妊娠，则要求对每例妊娠跟踪随访，直到获得妊娠结局。",
    "body.p1166": "所有妊娠的过程，包括围产期和新生儿结局，无论参与者是否已停止参与研究，将随访至结局，包括自发或自愿终止妊娠、分娩细节，以及是否存在任何出生缺陷、先天性异常或孕产妇和/或新生儿并发症，直至健康婴儿的第一次访视或法规规定的时间（或任何原因的终止妊娠后下一次正常月经结束），以较晚者为准。对出生结果的随访将根据个案情况进行处理（例如对早产儿进行随访，以确定是否存在发育迟缓）。妊娠随访信息应记录在同一表格上，并应包括对试验用药品与任何妊娠结果可能因果关系的评估。新生儿经历的SAE事件要求以SAE报告表的方式立即报告（即，获知事件后不超过24小时）。在终止妊娠的情况下，应明确终止的原因，如果临床可能，应通过肉眼检查评估终止妊娠时胎儿的结构完整性，除非术前检查显示先天性异常并已报告结果。",
    "body.p1167": "当妊娠过程和结局信息有更新时，研究者应填写并立即向申办者提交试验妊娠报告表。",
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p986": "不良事件（AE）指临床试验参与者在接受试验用药品之后出现的所有不良医学事件，可以表现为症状体征、疾病和/或有临床意义的实验室检查异常，但不一定与试验用药品有因果关系。",
    "body.p996": "严重不良事件，指参与者接受试验用药品后出现死亡、危及生命、永久或者严重的残疾或者功能丧失、参与者需要住院治疗或者延长住院时间，以及先天性异常或者出生缺陷等不良医学事件。",
}

# Parent-approved positive semantics payloads. These are independent constants
# (not derived from the config object under test at scan time).
FROZEN_POSITIVE_SEMANTICS_BY_REF: dict[str, dict] = {
    "body.p1158": {
        "semantic_role": "pregnancy_section_title_structural_only",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1158"],
        "exception_rule": "第99包章节标题，仅作结构，闭合妊娠章节层级；标题本身不构成报告、处置、AE/SAE分流或随访义务，不得升格为预筛/筛选/基线控制点",
        "preserve_keywords": ["妊娠"],
        "forbidden_inversion": "不得把标题解释为独立规则、候选或入排门槛；不得用标题替代下属段落规则；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1159": {
        "semantic_role": "pregnancy_event_reporting_requirements_heading_structural_only",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1159"],
        "exception_rule": "第99包子节标题，仅作结构，闭合妊娠事件报告要求层级；标题本身不构成触发对象、时间窗、确认或24小时报告义务，不得升格为预筛/筛选/基线控制点",
        "preserve_keywords": ["妊娠事件的报告要求"],
        "forbidden_inversion": "不得把标题解释为独立规则、候选或入排门槛；不得用标题替代p1160-p1163规则；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1160": {
        "semantic_role": "pregnancy_trigger_objects_window_confirm_and_24h_report",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1160"],
        "exception_rule": "保留两类对象：女性参与者，或男性参与者的女性伴侣。时间窗为研究期间或CMS-D001片末次给药后3个月内；怀孕或怀疑可能妊娠均先立即告知研究者并尽快检查确认。确认妊娠后，研究者在确认后24小时填写、签名并签署日期的《妊娠事件报告表》，随后立即书面报告申办者或其指定人员（获知后不超过24小时），并按中心伦理要求上报。不得删除疑似妊娠触发、确认步骤、书面报告或伦理上报；不得把末次给药后3个月改成研究结束后；不得把确认前后报告次序混同；零候选",
        "preserve_keywords": ["女性参与者或男性参与者的女性伴侣", "研究期间或CMS-D001片末次给药后3个月内", "怀孕或怀疑可能妊娠", "立即告知研究者", "尽快进行检查确认", "确认后24小时填写《妊娠事件报告表》", "签名并签署日期", "立即书面报告给申办者或其指定人员", "获知事件后不超过24小时", "中心伦理的要求进行上报"],
        "forbidden_inversion": "不得删除疑似妊娠触发；不得删除确认步骤；不得把末次给药后3个月改成研究结束后；不得混同确认前后报告次序；不得删除书面报告或伦理上报；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1161": {
        "semantic_role": "pregnancy_role_divergent_discontinuation_and_partner_followup",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1161"],
        "exception_rule": "保留性别与角色差异：女性参与者在CMS-D001片首次给药之后的研究期间发生妊娠，应立即停用研究药物并及时记录、报告及随访；男性参与者的女性伴侣发生妊娠时，不要求男性参与者停用试验用药品，但需对女性伴侣按女性参与者发生妊娠的方式记录、报告及随访。不得将两条路径统一成全部停药或全部继续用药；不得要求男性参与者因伴侣妊娠停药；零候选",
        "preserve_keywords": ["女性参与者", "首次给药之后的研究期间", "立即停用研究药物", "记录、报告及随访", "男性参与者的女性伴侣", "不要求男性参与者停用试验用药品", "按照女性参与者发生妊娠的处理方式"],
        "forbidden_inversion": "不得把伴侣妊娠改成要求男方停药；不得统一成全部停药或全部继续用药；不得删除记录/报告/随访义务；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1162": {
        "semantic_role": "pregnancy_not_ae_unless_complication_or_outcome_meets_ae",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1162"],
        "exception_rule": "单纯妊娠本身不属于不良事件，不应记录在eCRF不良事件上；仅当妊娠相关并发症或妊娠结果符合不良事件定义时，才同时按AE管理。自然流产、因医学及健康原因导致的人工流产、死胎、新生儿严重不良事件是例示，不得反向把所有妊娠或所有终止妊娠标记为AE/SAE；AE定义由只读body.p986闭合，不得在本包重新发布定义；零候选",
        "preserve_keywords": ["单纯的妊娠事件本身不属于不良事件", "不应记录在eCRF不良事件上", "妊娠相关并发症或妊娠的结果符合不良事件定义", "按照不良事件进行管理", "自然流产", "因医学及健康原因导致的人工流产", "死胎", "新生儿严重不良事件"],
        "forbidden_inversion": "不得把单纯妊娠全部AE化；不得把所有终止妊娠反向标记为AE/SAE；不得把例示当穷尽清单；不得在本包重新发布AE定义；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1163": {
        "semantic_role": "pregnancy_sae_24h_report_and_elective_abortion_not_ae",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1163"],
        "exception_rule": "妊娠参与者在妊娠期间经历的SAE，须以《SAE报告表》立即报告（获知后不超过24小时）；没有妊娠相关并发症的选择性流产不视为不良事件。不得因“选择性流产”就默认AE，也不得把任何妊娠事件都当作SAE；SAE定义由只读body.p996闭合，不得在本包重新发布定义；零候选",
        "preserve_keywords": ["妊娠参与者在妊娠期间经历的SAE", "《SAE报告表》", "立即报告", "获知事件后不超过24小时", "没有妊娠相关并发症的选择性流产", "不视为不良事件"],
        "forbidden_inversion": "不得把无并发症选择性流产AE化；不得把任何妊娠事件当作SAE；不得删除24小时时限；不得在本包重新发布SAE定义；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1164": {
        "semantic_role": "pregnancy_followup_section_title_structural_only",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1164"],
        "exception_rule": "第99包子节标题，仅作结构，闭合妊娠事件随访层级；标题本身不构成风险沟通、决策主体、随访终点或更新报告义务，不得升格为预筛/筛选/基线控制点",
        "preserve_keywords": ["妊娠事件的随访"],
        "forbidden_inversion": "不得把标题解释为独立规则、候选或入排门槛；不得用标题替代p1165-p1167规则；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1165": {
        "semantic_role": "pregnancy_risk_communication_participant_partner_decision_and_continue_followup",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1165"],
        "exception_rule": "研究者应根据用药情况严谨交流试验用药品对孕妇及胎儿的可能影响和风险；终止或继续妊娠由参与者及其伴侣自行决定。决定继续妊娠时，每例须跟踪随访直至获得妊娠结局。不得将风险沟通改写成研究者代替决定妊娠去留；零候选",
        "preserve_keywords": ["根据用药情况", "试验用药品对于孕妇及胎儿可能的影响和风险", "参与者及其伴侣自行决定", "终止妊娠或继续妊娠", "决定继续妊娠", "每例妊娠跟踪随访", "直到获得妊娠结局"],
        "forbidden_inversion": "不得让研究者代替参与者/伴侣决定终止或继续妊娠；不得删除继续妊娠后的结局跟踪；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1166": {
        "semantic_role": "pregnancy_followup_later_of_endpoints_neonatal_sae_and_conditional_fetal_assessment",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1166"],
        "exception_rule": "覆盖所有妊娠过程、围产期和新生儿结局，不因参与者退出研究而停止。随访终点为“健康婴儿第一次访视或法规规定时间”与“任何原因终止妊娠后下一次正常月经结束”两路中较晚者；出生结果按个案追踪。随访信息记入同一表格并评估试验用药品与妊娠结果可能因果关系。新生儿SAE以SAE报告表立即报告（获知后不超过24小时）。终止妊娠应明确原因；仅在临床可能时通过肉眼检查评估胎儿结构完整性，术前已显示并报告先天性异常时不再重复该要求。不得把较晚者改较早者；不得删除“临床可能”或已报告先天性异常例外；不得因退出研究停止妊娠随访；零候选",
        "preserve_keywords": ["无论参与者是否已停止参与研究", "健康婴儿的第一次访视或法规规定的时间", "任何原因的终止妊娠后下一次正常月经结束", "以较晚者为准", "根据个案情况进行处理", "同一表格", "可能因果关系的评估", "新生儿经历的SAE事件", "获知事件后不超过24小时", "明确终止的原因", "如果临床可能", "肉眼检查评估终止妊娠时胎儿的结构完整性", "除非术前检查显示先天性异常并已报告结果"],
        "forbidden_inversion": "不得因退出研究停止妊娠随访；不得把较晚者改较早者；不得删除新生儿SAE 24小时时限；不得删除“临床可能”条件或已报告先天性异常例外；不得升格为预筛/筛选/基线控制点",
    },
    "body.p1167": {
        "semantic_role": "pregnancy_process_outcome_update_requires_immediate_report_form",
        "base_rule": OWNED_EXCERPT_BY_REF["body.p1167"],
        "exception_rule": "当妊娠过程或结局信息有更新时，研究者应填写并立即向申办者提交试验妊娠报告表。不得将“有更新时”弱化为可选报告，也不得改成重新初始报告；零候选",
        "preserve_keywords": ["妊娠过程和结局信息有更新时", "填写并立即向申办者提交", "试验妊娠报告表"],
        "forbidden_inversion": "不得把信息更新报告改成可选；不得改成重新初始报告；不得删除立即提交；不得升格为预筛/筛选/基线控制点",
    },
    "body.p986": {
        "semantic_role": "ae_definition_readonly_for_pregnancy_ae_branch_closure",
        "base_rule": ATTACHED_EXCERPT_BY_REF["body.p986"],
        "exception_rule": "第77包拥有的AE定义，只读附加用于闭合本包p1162“符合不良事件定义”的分流引用；不得转移所有权、重新发布定义或把定义段落改写为本包拥有；不得发射候选",
        "preserve_keywords": ["不良事件（AE）", "接受试验用药品之后出现的所有不良医学事件", "不一定与试验用药品有因果关系"],
        "forbidden_inversion": "不得把第77包AE定义改写为本包拥有或重新发布；不得用本包妊娠规则改写AE定义；不得升格为预筛/筛选/基线控制点",
    },
    "body.p996": {
        "semantic_role": "sae_definition_readonly_for_pregnancy_sae_branch_closure",
        "base_rule": ATTACHED_EXCERPT_BY_REF["body.p996"],
        "exception_rule": "第78包拥有的SAE定义，只读附加用于闭合本包p1163/p1166 SAE报告分流引用；不得转移所有权、重新发布定义或把定义段落改写为本包拥有；不得发射候选",
        "preserve_keywords": ["严重不良事件", "死亡", "危及生命", "永久或者严重的残疾或者功能丧失", "住院治疗或者延长住院时间", "先天性异常或者出生缺陷"],
        "forbidden_inversion": "不得把第78包SAE定义改写为本包拥有或重新发布；不得用本包妊娠规则改写SAE定义；不得升格为预筛/筛选/基线控制点",
    },
}


def _canonical_positive_payload(entry: dict) -> str:
    payload = {
        "semantic_role": entry.get("semantic_role"),
        "base_rule": entry.get("base_rule"),
        "exception_rule": entry.get("exception_rule"),
        "preserve_keywords": list(entry.get("preserve_keywords") or []),
        "forbidden_inversion": entry.get("forbidden_inversion") or "",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _positive_field_digest(entry: dict) -> str:
    return _digest_text(_canonical_positive_payload(entry))


# Literal frozen digests pinned once from parent-approved positive payloads.
# These are independent constants: scanners compare live config digests to these
# literals, never to a freshly computed sibling map at scan time.
FROZEN_POSITIVE_DIGEST_BY_REF: dict[str, str] = {
    "body.p1158": "a81c16411eb16c7bc463dc5162ab84f3ec06172165e2dba412b17906ee3a441f",
    "body.p1159": "6267c3d5a963de66ac870799b07f27a0d4c574407fe96d77631e965057c83489",
    "body.p1160": "622e24a926558c229785bdcfff92ed8298a43c272a53be69cf8e020991c649fe",
    "body.p1161": "4a30f3795b9735140b435366d42d56662060c60914af2010f83fc89cd148d99b",
    "body.p1162": "a363bc967e164ccbc5d230465b648560bcc3b73f79140cff385ddafd9fa14539",
    "body.p1163": "99a06af9d15482e243ae0c06d5d490c83c9a8bb4deddcee7d376c414781912c0",
    "body.p1164": "e274aec40ba2ff339cd3dfabb5c96d0f6adb68b0baa599d686537363aa50d539",
    "body.p1165": "ebe1ad57f7b88eeae3686fdfb8d5f9e6eadf6d696a06680ebbab93a32791084f",
    "body.p1166": "84e69dec06e67baf1cd6e63b495c2fce6a80d92585f6dc0da2f14df8edb4dd4e",
    "body.p1167": "40674ee1260e124f932228795f381d621f2eb6abfa566838930027cc269fd467",
    "body.p986": "e1fcabf2934e8ef528d83e6fb06f2fc43f17defd29c75107af80615875c1021a",
    "body.p996": "05e3c42174edbcd8d1ae38721a5bd2ae770e6484fe3e9438bafb6f4cddd3d5b5",
}
FROZEN_POSITIVE_SET_DIGEST = "9af466cbcdf6b5f05135a6da89430e8cc55e1b73484355a3742fe8b5401be148"


# Worker 03 second-pass free counterexamples (wrong positive appends).
# All clauses are unique clinical wrongs; no punctuation-only padding.
W3_PASS2_WRONG_POSITIVE_APPENDS: list[tuple[str, str, str]] = [
    ("body.p1160", "删除疑似妊娠触发，仅保留已确认妊娠", "DELETE_SUSPECTED_TRIGGER"),
    ("body.p1160", "两类对象合并为仅女性参与者，删除男性参与者的女性伴侣对象", "OBJECT_COLLAPSE_FEMALE_ONLY"),
    ("body.p1160", "末次给药后3个月时间窗改为研究结束后3个月", "WINDOW_TO_POST_STUDY"),
    ("body.p1160", "确认前即可填写妊娠事件报告表并书面报告", "CONFIRM_ORDER_COLLAPSE"),
    ("body.p1160", "怀孕触发后可跳过尽快检查确认步骤", "SKIP_CONFIRMATION"),
    ("body.p1160", "确认后报告可省略中心伦理上报", "DROP_ETHICS_REPORT"),
    ("body.p1160", "书面报告申办者可延后至72小时", "SPONSOR_REPORT_TIMEOUT"),
    ("body.p1160", "妊娠事件报告表可不签名或不签署日期", "UNSIGNED_PREGNANCY_FORM"),
    ("body.p1161", "男性参与者伴侣妊娠时要求男性参与者停用试验用药品", "MALE_STOP_REQUIRED"),
    ("body.p1161", "女性与男性伴侣妊娠路径一律继续试验用药不停药", "ALL_PATHS_CONTINUE_MEDICATION"),
    ("body.p1161", "女性参与者妊娠后可不立即停用研究药物", "FEMALE_NO_IMMEDIATE_STOP"),
    ("body.p1161", "伴侣妊娠后可不按女性参与者路径记录报告随访", "PARTNER_NO_FOLLOW_PATH"),
    ("body.p1161", "两条停药路径统一为全部停药", "UNIFY_ALL_STOP"),
    ("body.p1162", "单纯妊娠本身也记入eCRF不良事件", "ALL_PREGNANCY_AS_AE"),
    ("body.p1162", "所有终止妊娠一律按AE/SAE管理", "ALL_TERMINATION_AS_AE_SAE"),
    ("body.p1162", "例示清单视为穷尽且可反向推导全部妊娠为AE", "EXAMPLES_AS_EXHAUSTIVE"),
    ("body.p1162", "在本包重新发布AE定义替代只读body.p986", "REPUBLISH_AE_DEFINITION"),
    ("body.p1163", "没有妊娠相关并发症的选择性流产视为不良事件", "ELECTIVE_ABORTION_AS_AE"),
    ("body.p1163", "任何妊娠事件均当作SAE报告", "ANY_PREGNANCY_AS_SAE"),
    ("body.p1163", "妊娠期间SAE获知后可超过24小时再报", "PREGNANCY_SAE_TIMEOUT"),
    ("body.p1163", "在本包重新发布SAE定义替代只读body.p996", "REPUBLISH_SAE_DEFINITION"),
    ("body.p1165", "研究者可代替参与者及其伴侣决定是否终止妊娠", "INVESTIGATOR_DECIDES"),
    ("body.p1165", "风险沟通可省略试验用药品对孕妇及胎儿的影响说明", "DROP_RISK_COMMUNICATION"),
    ("body.p1165", "决定继续妊娠后可不跟踪至妊娠结局", "NO_OUTCOME_FOLLOW_WHEN_CONTINUE"),
    ("body.p1166", "参与者退出研究后妊娠随访即可停止", "EXIT_STOPS_FOLLOWUP"),
    ("body.p1166", "随访终点取两路中较早者而非较晚者", "LATER_TO_EARLIER"),
    ("body.p1166", "删除临床可能条件，终止妊娠一律评估胎儿结构完整性", "DROP_CLINICAL_POSSIBILITY"),
    ("body.p1166", "术前已报告先天性异常时仍重复胎儿结构完整性肉眼检查", "DROP_REPORTED_CONGENITAL_ANOMALY_EXCEPTION"),
    ("body.p1166", "新生儿SAE获知后可在72小时内报告", "NEONATAL_SAE_TIMEOUT"),
    ("body.p1166", "终止妊娠时可不明确终止原因", "DROP_TERMINATION_REASON"),
    ("body.p1166", "出生结果随访可不按个案处理", "DROP_CASE_BY_CASE_BIRTH_FOLLOWUP"),
    ("body.p1166", "可不在同一表格评估试验用药品与妊娠结果可能因果关系", "DROP_CAUSALITY_ON_SAME_FORM"),
    ("body.p1167", "妊娠信息更新后可选择性提交试验妊娠报告表", "UPDATE_OPTIONAL"),
    ("body.p1167", "信息更新后改为重新初始报告而非更新提交", "UPDATE_TO_REINITIAL_REPORT"),
    ("body.p1167", "信息更新后可不立即向申办者提交试验妊娠报告表", "UPDATE_NON_IMMEDIATE"),
    ("body.p1167", "过程更新可不填写试验妊娠报告表", "UPDATE_SKIP_FORM"),
    ("body.p1158", "妊娠标题直接构成报告与随访义务", "TITLE_AS_OBLIGATION_P1158"),
    ("body.p1159", "报告要求标题可替代确认与24小时报告规则", "TITLE_AS_OBLIGATION_P1159"),
    ("body.p1164", "随访标题可替代较晚者终点与更新报告规则", "TITLE_AS_OBLIGATION_P1164"),
    ("body.p1160", "对象仅保留男性参与者的女性伴侣并删除女性参与者", "OBJECT_COLLAPSE_PARTNER_ONLY"),
    ("body.p1160", "时间窗限缩为仅研究期间不含末次给药后3个月", "WINDOW_DROP_POST_DOSE"),
    ("body.p1161", "伴侣妊娠时男方停药且女性参与者不停药", "INVERT_ROLE_STOP_RULES"),
    ("body.p1162", "自然流产以外的终止妊娠一律不按AE管理", "DROP_COMPLICATION_AE_BRANCH"),
    ("body.p1163", "选择性流产即使有并发症也不视为AE", "COMPLICATED_ELECTIVE_NOT_AE"),
    ("body.p1165", "继续妊娠跟踪可在获得临时结果后停止", "STOP_BEFORE_FINAL_OUTCOME"),
    ("body.p1166", "健康婴儿访视完成即可结束，不等待法规规定时间较晚者", "EARLY_STOP_AFTER_INFANT_VISIT"),
    ("body.p1166", "法规规定时间到达即可结束，不等待健康婴儿访视较晚者", "EARLY_STOP_AFTER_REGULATORY_TIME"),
    ("body.p1167", "更新报告可并入首次妊娠事件报告表重复初始路径", "UPDATE_MERGE_INTO_INITIAL_PATH"),
]

assert len(W3_PASS2_WRONG_POSITIVE_APPENDS) == 48
assert len({clause for _, clause, _ in W3_PASS2_WRONG_POSITIVE_APPENDS}) == 48

BAN_CONTEXT_EXTERNAL_STRINGS = [
    "筛选必做",
    "基线期必做",
    "不得入组",
    "排除标准",
    "发布控制点",
    "转移所有权",
    "证据缺口",
    "入排不通过",
]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker in text]


def _relation_false_positive_labels_for_external_text(_text: str) -> set[str]:
    """Open synonym-regex relation scanners are retired.

    External ban-context strings must not invent pregnancy/AE relation labels.
    """
    return set()


def _package99_contract_issues(config: dict) -> set[str]:
    """Validate Package 99 via frozen positive-semantics digests + hard gates.

    Clinical synonym breadth is intentionally NOT proved by open Chinese regex.
    Any mutation of parent-approved positive fields is reported as
    POSITIVE_SEMANTICS_DRIFT (optionally per-ref). Specific clinical family
    names remain in readable regression test titles, not in this scanner.
    """
    issues: set[str] = set()
    semantics = config.get("exception_semantics_by_source_ref") or {}

    if list(config.get("owned_source_refs") or []) != OWNED_REFS:
        issues.add("OWNED_REFS")
    if list(config.get("attached_source_refs") or []) != ATTACHED_REFS:
        issues.add("ATTACHED_REFS")
    if list(config.get("structural_only_source_refs") or []) != STRUCTURAL_REFS:
        issues.add("STRUCTURAL_REFS")
    if config.get("claims_complete") is True:
        issues.add("CLAIMS_COMPLETE_TRUE")
    if config.get("required_candidate_source_refs"):
        issues.add("REQUIRED_CANDIDATE_NONEMPTY")

    if CONFIG_PATH.is_file():
        if _sha256_file(CONFIG_PATH) != EXPECTED_CONFIG_SHA256:
            issues.add("CONFIG_FINGERPRINT_DRIFT")

    attached = list(config.get("attached_source_refs") or [])
    owned = list(config.get("owned_source_refs") or [])
    attached_set = set(attached)
    owned_set = set(owned)

    # Attached refs must remain present as read-only positive semantics,
    # but must never appear in owned_source_refs (ownership transfer).
    for ref in ATTACHED_REFS:
        if ref in owned_set:
            issues.add("PACKAGE77_78_OWNERSHIP")
            issues.add("ATTACHED_TO_OWNED")
        entry = semantics.get(ref)
        if entry is None:
            issues.add(f"{ref}:ATTACHED_SEMANTICS_MISSING")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
            continue
        role = entry.get("semantic_role") or ""
        if "readonly" not in role:
            issues.add(f"{ref}:ATTACHED_NOT_READONLY")
            issues.add("PACKAGE77_78_OWNERSHIP")

    for ref in list(semantics.keys()):
        if ref not in POSITIVE_REFS:
            issues.add(f"{ref}:UNEXPECTED_SEMANTICS")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
            if ref in PKG98_SPAN_REFS:
                issues.add("PACKAGE98_ABSORPTION")
            if ref in PKG100_SPAN_REFS:
                issues.add("PACKAGE100_ABSORPTION")

    observed_set_rows: list[dict[str, str]] = []
    for ref in POSITIVE_REFS:
        entry = semantics.get(ref)
        if entry is None:
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
            observed_set_rows.append({"source_ref": ref, "digest": ""})
            continue
        expected_base = (
            OWNED_EXCERPT_BY_REF[ref]
            if ref in OWNED_EXCERPT_BY_REF
            else ATTACHED_EXCERPT_BY_REF[ref]
        )
        if entry.get("base_rule") != expected_base:
            issues.add(f"{ref}:SOURCE_TEXT")
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")
        digest = _positive_field_digest(entry)
        observed_set_rows.append({"source_ref": ref, "digest": digest})
        if digest != FROZEN_POSITIVE_DIGEST_BY_REF[ref]:
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")

    observed_set_digest = _digest_text(
        json.dumps(observed_set_rows, ensure_ascii=False, separators=(",", ":"))
    )
    if observed_set_digest != FROZEN_POSITIVE_SET_DIGEST:
        issues.add("POSITIVE_SEMANTICS_SET_DRIFT")
        issues.add("POSITIVE_SEMANTICS_DRIFT")

    for ref in STRUCTURAL_REFS:
        entry = semantics.get(ref) or {}
        rule = entry.get("exception_rule") or ""
        if "仅作结构" not in rule and "结构" not in rule:
            issues.add(f"{ref}:STRUCTURAL_ONLY")
            issues.add(f"{ref}:POSITIVE_SEMANTICS_DRIFT")
            issues.add("POSITIVE_SEMANTICS_DRIFT")

    ownership_blob = " ".join(
        [
            config.get("later_package_boundary", {}).get("note", ""),
            " ".join(config.get("notes") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p986") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p996") or []),
            " ".join(config.get("clinical_qc_checks_by_source_ref", {}).get("body.p1160") or []),
        ]
    )
    if "第77包" not in ownership_blob:
        issues.add("PACKAGE77_BOUNDARY_NOTE")
    if "第78包" not in ownership_blob:
        issues.add("PACKAGE78_BOUNDARY_NOTE")
    if "第98包" not in ownership_blob:
        issues.add("PACKAGE98_BOUNDARY_NOTE")
    if "第100包" not in ownership_blob:
        issues.add("PACKAGE100_BOUNDARY_NOTE")
    if "零候选" not in ownership_blob:
        issues.add("ZERO_CANDIDATE_NOTE")

    owned_and_attached = set(owned + attached)
    if owned_and_attached & set(PKG98_SPAN_REFS):
        issues.add("PACKAGE98_ABSORPTION")
    if owned_and_attached & set(PKG100_SPAN_REFS):
        issues.add("PACKAGE100_ABSORPTION")
    if set(owned) & set(ATTACHED_REFS):
        issues.add("PACKAGE77_78_OWNERSHIP")
    if owned_and_attached & set(PKG77_NON_ATTACHED):
        issues.add("PACKAGE77_NON_ATTACHED_ABSORPTION")
    if owned_and_attached & set(PKG78_NON_ATTACHED):
        issues.add("PACKAGE78_NON_ATTACHED_ABSORPTION")

    for ref in OWNED_REFS + ATTACHED_REFS:
        disposition = (config.get("expected_disposition_by_source_ref") or {}).get(ref)
        if ref in STRUCTURAL_REFS:
            if disposition is not None:
                issues.add(f"{ref}:DISPOSITION")
        elif ref in SEMANTIC_OWNED_REFS:
            if disposition != "post_treatment_execution":
                issues.add(f"{ref}:DISPOSITION")
        # attached refs should not carry owned disposition maps
        elif ref in ATTACHED_REFS:
            if disposition is not None:
                issues.add(f"{ref}:DISPOSITION")
        markers = config.get("candidate_forbidden_markers_by_source_ref", {}).get(ref) or []
        if not markers:
            issues.add(f"{ref}:FORBIDDEN_MARKERS")
        if ref not in (config.get("forbidden_candidate_source_refs") or []):
            issues.add(f"{ref}:FORBIDDEN_CANDIDATE_SET")

    return issues


def _append_exception_rule(config: dict, ref: str, clause: str) -> dict:
    mutated = copy.deepcopy(config)
    rule = mutated["exception_semantics_by_source_ref"][ref]["exception_rule"]
    mutated["exception_semantics_by_source_ref"][ref]["exception_rule"] = (
        rule + ("；" if not rule.endswith(("；", "。")) else "") + clause
    )
    return mutated


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_99_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _attached_excerpt_by_ref(plan: dict) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for ordinal, ref in ((PACKAGE_77_ORDINAL, "body.p986"), (PACKAGE_78_ORDINAL, "body.p996")):
        pkg = next(p for p in plan["packages"] if p["package_ordinal"] == ordinal)
        for unit in pkg["owned_units"]:
            if unit["source_ref"] == ref:
                excerpts[ref] = unit["excerpt"]
    return excerpts


def _structure_blob_text(blob: list[dict], ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == ref:
            return block.get("text") or block.get("excerpt") or ""
    return ""


@pytest.fixture
def config() -> dict:
    from slice59n_representative_group_control_replay import _load_config

    return _load_config(CONFIG_PATH)


@pytest.fixture
def plan() -> dict:
    return _load_json(PLAN_PATH)


@pytest.fixture
def matrix() -> dict:
    return _load_json(MATRIX_PATH)


@pytest.fixture
def procedure_catalog() -> dict:
    return _load_json(CATALOG_DIR / "required_procedures.json")


@pytest.fixture
def structure_blob() -> list[dict]:
    return _load_json(STRUCTURE_BLOB_PATH)


def test_frozen_positive_digests_are_independent_constants() -> None:
    # Literals must exist as constants (64-hex), match intended frozen payloads,
    # and remain the scanner reference — not a newly computed sibling map.
    hex64 = set("0123456789abcdef")
    assert list(FROZEN_POSITIVE_DIGEST_BY_REF) == list(POSITIVE_REFS) or set(
        FROZEN_POSITIVE_DIGEST_BY_REF
    ) == set(POSITIVE_REFS)
    assert all(
        len(v) == 64 and set(v) <= hex64 for v in FROZEN_POSITIVE_DIGEST_BY_REF.values()
    )
    assert len(FROZEN_POSITIVE_SET_DIGEST) == 64 and set(FROZEN_POSITIVE_SET_DIGEST) <= hex64
    for ref in POSITIVE_REFS:
        expected = _positive_field_digest(FROZEN_POSITIVE_SEMANTICS_BY_REF[ref])
        assert FROZEN_POSITIVE_DIGEST_BY_REF[ref] == expected
    recomputed_set = _digest_text(
        json.dumps(
            [
                {
                    "source_ref": ref,
                    "digest": FROZEN_POSITIVE_DIGEST_BY_REF[ref],
                }
                for ref in POSITIVE_REFS
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    assert FROZEN_POSITIVE_SET_DIGEST == recomputed_set
    # Contract scanner compares live config digests against the literal constants.
    probe_config = {
        "owned_source_refs": list(OWNED_REFS),
        "attached_source_refs": list(ATTACHED_REFS),
        "structural_only_source_refs": list(STRUCTURAL_REFS),
        "required_candidate_source_refs": [],
        "forbidden_candidate_source_refs": list(OWNED_REFS + ATTACHED_REFS),
        "expected_disposition_by_source_ref": {
            ref: "post_treatment_execution" for ref in SEMANTIC_OWNED_REFS
        },
        "candidate_forbidden_markers_by_source_ref": {
            ref: ["筛选必做"] for ref in OWNED_REFS + ATTACHED_REFS
        },
        "clinical_qc_checks_by_source_ref": {
            "body.p986": ["第77包"],
            "body.p996": ["第78包"],
            "body.p1160": ["零候选"],
        },
        "later_package_boundary": {"note": "第77包 第78包 第98包 第100包 零候选"},
        "notes": ["第77包 第78包 第98包 第100包 零候选"],
        "exception_semantics_by_source_ref": copy.deepcopy(FROZEN_POSITIVE_SEMANTICS_BY_REF),
    }
    assert _package99_contract_issues(probe_config) == set()
    drifted = copy.deepcopy(probe_config)
    drifted["exception_semantics_by_source_ref"][POSITIVE_REFS[0]]["exception_rule"] += "；漂移"
    assert (
        f"{POSITIVE_REFS[0]}:POSITIVE_SEMANTICS_DRIFT"
        in _package99_contract_issues(drifted)
    )


def test_config_file_fingerprint_matches_independent_constant() -> None:
    assert _sha256_file(CONFIG_PATH) == EXPECTED_CONFIG_SHA256


def test_config_contract(config: dict) -> None:
    assert config["group_id"] == "d001-ii-package99-pregnancy-reporting-followup-boundary"
    assert config["task_id"] == "phase5-slice61ck-20260830"
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["study_phase"] == "phase_ii"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert config["required_candidate_source_refs"] == []
    assert config.get("claims_complete") is not True
    assert _package99_contract_issues(config) == set()


def test_package99_contract_is_currently_closed(config: dict) -> None:
    assert _package99_contract_issues(config) == set()


def test_live_config_positive_fields_match_frozen_digests(config: dict) -> None:
    for ref in POSITIVE_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert _positive_field_digest(entry) == FROZEN_POSITIVE_DIGEST_BY_REF[ref]
        assert entry == FROZEN_POSITIVE_SEMANTICS_BY_REF[ref]


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    assert config["attached_source_refs"] == ATTACHED_REFS
    for ref in ATTACHED_REFS:
        assert ref not in config["owned_source_refs"]
        role = config["exception_semantics_by_source_ref"][ref]["semantic_role"]
        assert "readonly" in role
        assert ref not in (config.get("expected_disposition_by_source_ref") or {})


def test_attached_refs_ownership_documented(plan: dict) -> None:
    pkg77 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_77_ORDINAL)
    pkg78 = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_78_ORDINAL)
    assert any(u["source_ref"] == "body.p986" for u in pkg77["owned_units"])
    assert any(u["source_ref"] == "body.p996" for u in pkg78["owned_units"])


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    by_ord = {p["package_ordinal"]: p for p in plan["packages"]}
    assert by_ord[PACKAGE_99_ORDINAL]["package_id"] == PACKAGE_99_ID
    assert len(by_ord[PACKAGE_99_ORDINAL]["owned_units"]) == 10
    assert by_ord[PACKAGE_98_ORDINAL]["package_id"] == PACKAGE_98_ID
    assert len(by_ord[PACKAGE_98_ORDINAL]["owned_units"]) == 8
    assert by_ord[PACKAGE_100_ORDINAL]["package_id"] == PACKAGE_100_ID


def test_owned_refs_match_frozen_package_99(config: dict, plan: dict) -> None:
    pkg = next(p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_99_ORDINAL)
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        assert excerpts[ref] == OWNED_EXCERPT_BY_REF[ref]
        assert config["exception_semantics_by_source_ref"][ref]["base_rule"] == excerpts[ref]


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    for ref, excerpt in ATTACHED_EXCERPT_BY_REF.items():
        assert excerpts[ref] == excerpt


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    for ref, excerpt in _owned_excerpt_by_ref(plan).items():
        assert _structure_blob_text(structure_blob, ref) == excerpt


def test_positive_append_reports_drift_not_open_synonym_label(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1160", "删除疑似妊娠触发")
    issues = _package99_contract_issues(mutated)
    assert "body.p1160:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_positive_delete_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1161"]["exception_rule"] = (
        mutated["exception_semantics_by_source_ref"]["body.p1161"]["exception_rule"][:40]
    )
    issues = _package99_contract_issues(mutated)
    assert "body.p1161:POSITIVE_SEMANTICS_DRIFT" in issues
    assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_positive_reorder_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    kws = mutated["exception_semantics_by_source_ref"]["body.p1160"]["preserve_keywords"]
    mutated["exception_semantics_by_source_ref"]["body.p1160"]["preserve_keywords"] = list(reversed(kws))
    assert "body.p1160:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_positive_rewrite_reports_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1166"]["exception_rule"] = (
        "随访终点取较早者；退出后可停止随访"
    )
    assert "POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_delete_suspected_pregnancy_trigger_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1160", "删除疑似妊娠触发，仅保留已确认妊娠")
    assert f"body.p1160:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_window_post_study_instead_of_last_dose_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1160", "末次给药后3个月改为研究结束后")
    assert f"body.p1160:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_confirm_order_collapse_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1160", "确认前即可填写妊娠事件报告表")
    assert f"body.p1160:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_male_partner_requires_male_stop_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1161", "男性参与者伴侣妊娠时要求男方停药")
    assert f"body.p1161:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_all_pregnancy_as_ae_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1162", "单纯妊娠全部记为AE")
    assert f"body.p1162:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_elective_abortion_as_ae_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1163", "无并发症选择性流产视为AE")
    assert f"body.p1163:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_investigator_decides_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1165", "研究者代替参与者及其伴侣决定是否终止妊娠")
    assert f"body.p1165:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_exit_stops_followup_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1166", "参与者退出研究后停止妊娠随访")
    assert f"body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_later_to_earlier_endpoint_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1166", "随访终点改为较早者")
    assert f"body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_drop_clinical_possibility_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1166", "删除临床可能条件，终止妊娠一律评估胎儿结构")
    assert f"body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_neonatal_sae_timeout_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1166", "新生儿SAE获知后72小时内报告")
    assert f"body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_update_optional_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(config, "body.p1167", "信息更新后可选提交试验妊娠报告表")
    assert f"body.p1167:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_collapse_to_female_participant_only_drops_male_partner_object_is_drift(
    config: dict,
) -> None:
    """p1160 must keep both objects; collapsing to female participant only is drift."""
    mutated = _append_exception_rule(
        config,
        "body.p1160",
        "两类对象合并为仅女性参与者，删除男性参与者的女性伴侣对象",
    )
    assert "body.p1160:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_drop_reported_congenital_anomaly_exception_is_drift(config: dict) -> None:
    """Separate from clinical-possibility deletion: already-reported anomaly exception."""
    mutated = _append_exception_rule(
        config,
        "body.p1166",
        "术前已报告先天性异常时仍重复胎儿结构完整性肉眼检查",
    )
    assert "body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_update_to_non_immediate_or_reinitial_report_is_drift(config: dict) -> None:
    mutated = _append_exception_rule(
        config,
        "body.p1167",
        "信息更新后改为重新初始报告且可不立即提交",
    )
    assert "body.p1167:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_spec_all_pregnancy_paths_continue_study_medication_is_drift(
    config: dict,
) -> None:
    mutated = _append_exception_rule(
        config,
        "body.p1161",
        "女性与男性伴侣妊娠路径一律继续试验用药不停药",
    )
    assert "body.p1161:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_attached_exception_semantics_role_must_stay_readonly(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p986"]["semantic_role"] = (
        "ae_definition_owned_by_package99"
    )
    issues = _package99_contract_issues(mutated)
    assert "body.p986:ATTACHED_NOT_READONLY" in issues or "PACKAGE77_78_OWNERSHIP" in issues
    assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_required_candidate_upgrade_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["required_candidate_source_refs"] = ["body.p1160"]
    assert "REQUIRED_CANDIDATE_NONEMPTY" in _package99_contract_issues(mutated)


def test_claims_complete_true_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["claims_complete"] = True
    assert "CLAIMS_COMPLETE_TRUE" in _package99_contract_issues(mutated)


def test_wrong_positive_not_masked_by_correct_forbid_notes_qc(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated = _append_exception_rule(mutated, "body.p1166", "较晚者改较早者")
    # keep forbid/notes/qc untouched
    assert "body.p1166:POSITIVE_SEMANTICS_DRIFT" in _package99_contract_issues(mutated)


def test_notes_qc_only_pollution_does_not_fake_close_positive(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["notes"] = list(mutated.get("notes") or []) + ["故意污染备注：较晚者改较早者"]
    mutated["clinical_qc_checks_by_source_ref"]["body.p1166"] = list(
        mutated["clinical_qc_checks_by_source_ref"]["body.p1166"]
    ) + ["备注污染：退出即停止随访"]
    assert _package99_contract_issues(mutated) == set()


def test_w3_pass2_all_wrong_positive_appends_rejected_by_drift(config: dict) -> None:
    assert len(W3_PASS2_WRONG_POSITIVE_APPENDS) == 48
    clauses = [clause for _, clause, _ in W3_PASS2_WRONG_POSITIVE_APPENDS]
    assert len(set(clauses)) == 48
    for ref, clause, _tag in W3_PASS2_WRONG_POSITIVE_APPENDS:
        mutated = _append_exception_rule(config, ref, clause)
        issues = _package99_contract_issues(mutated)
        assert f"{ref}:POSITIVE_SEMANTICS_DRIFT" in issues
        assert "POSITIVE_SEMANTICS_DRIFT" in issues


def test_ban_context_external_strings_do_not_raise_relation_false_positives() -> None:
    for text in BAN_CONTEXT_EXTERNAL_STRINGS:
        labels = _relation_false_positive_labels_for_external_text(text)
        assert labels == set(), (text, labels)


def test_pkg77_78_attached_to_owned_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"] = OWNED_REFS + ["body.p986"]
    issues = _package99_contract_issues(mutated)
    assert "OWNED_REFS" in issues or "PACKAGE77_78_OWNERSHIP" in issues


def test_pkg98_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["attached_source_refs"] = ATTACHED_REFS + ["body.p1150"]
    issues = _package99_contract_issues(mutated)
    assert "ATTACHED_REFS" in issues or "PACKAGE98_ABSORPTION" in issues


def test_pkg100_absorption_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"] = OWNED_REFS + ["body.p1168"]
    issues = _package99_contract_issues(mutated)
    assert "OWNED_REFS" in issues or "PACKAGE100_ABSORPTION" in issues


def test_structural_heading_conversion_is_drift(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["exception_semantics_by_source_ref"]["body.p1158"]["exception_rule"] = (
        "妊娠章节标题直接构成报告与随访义务"
    )
    issues = _package99_contract_issues(mutated)
    assert "body.p1158:STRUCTURAL_ONLY" in issues


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    owned_and_attached = set(config["owned_source_refs"] + config["attached_source_refs"])
    for refs in (
        PKG98_SPAN_REFS,
        PKG100_SPAN_REFS,
        PKG97_SPAN_REFS,
        PKG96_SPAN_REFS,
        PKG95_SPAN_REFS,
        PKG94_SPAN_REFS,
        PKG93_SPAN_REFS,
        PKG92_SPAN_REFS,
        PKG91_SPAN_REFS,
        PKG90_SPAN_REFS,
        PKG89_SPAN_REFS,
        PKG88_SPAN_REFS,
        PKG87_SPAN_REFS,
        PKG82_SPAN_REFS,
        PKG80_SPAN_REFS,
        PKG79_SPAN_REFS,
        PKG78_NON_ATTACHED,
        PKG77_NON_ATTACHED,
    ):
        assert owned_and_attached.isdisjoint(refs)


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    expected_owners = config["later_package_boundary"]["expected_owners_by_span"]
    by_ord = {p["package_ordinal"]: p for p in plan["packages"]}
    for ref, ordinal in expected_owners.items():
        owned = {u["source_ref"] for u in by_ord[ordinal]["owned_units"]}
        assert ref in owned, (ref, ordinal)


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    note = boundary.get("note") or ""
    assert "第98包" in note
    assert "第100包" in note
    assert "p1150" in note or "body.p1150" in note
    assert "p1168" in note or "body.p1168" in note
    assert boundary.get("read_only") is True


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert len(rows) == 12
    assert sum(1 for row in rows if row.role == "owned") == 10
    assert sum(1 for row in rows if row.role == "attached") == 2
    assert by_ref["body.p1160"].role == "owned"
    assert "女性参与者或男性参与者的女性伴侣" in by_ref["body.p1160"].excerpt
    assert "以较晚者为准" in by_ref["body.p1166"].excerpt
    assert by_ref["body.p986"].role == "attached"
    assert by_ref["body.p996"].role == "attached"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    provenance = _load_json(PREPARE_DIR / "freeze_provenance.json")
    clinical_qc = _load_json(PREPARE_DIR / "clinical-qc.json")
    assert len(rows) == 12
    assert sum(1 for row in rows if row["role"] == "owned") == 10
    assert sum(1 for row in rows if row["role"] == "attached") == 2
    assert {row["source_ref"] for row in rows if row["role"] == "owned"} == set(OWNED_REFS)
    assert {row["source_ref"] for row in rows if row["role"] == "attached"} == set(ATTACHED_REFS)
    assert summary["owned_count"] == 10
    assert summary["attached_count"] == 2
    assert summary["unit_count"] == 12
    assert summary["mode"] == "dry_run_prepare"
    assert summary["claims_complete"] is False
    assert provenance["mode"] == "dry_run_prepare"
    assert provenance["claims_complete"] is False
    assert provenance["config_sha256"] == EXPECTED_CONFIG_SHA256
    assert clinical_qc["claims_complete"] is False
    assert clinical_qc["gate"]["skipped"] is True


def test_hydrated_gate_enforces_zero_candidate_partition(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units
    from slice59n_representative_group_reject_gates import evaluate_hydrated_agent_output

    rows = _resolve_units(config)
    for ref in OWNED_REFS + ATTACHED_REFS:
        hydrated = {
            "candidates": [
                {
                    "source_ref": ref,
                    "structure_unit_id": next(
                        row.structure_unit_id for row in rows if row.source_ref == ref
                    ),
                    "disposition": "post_treatment_execution",
                    "rationale": "fabricated candidate",
                }
            ]
        }
        issues = evaluate_hydrated_agent_output(
            group_id=str(config["group_id"]),
            study_phase=str(config["study_phase"]),
            rows=[
                {
                    "source_ref": row.source_ref,
                    "role": row.role,
                    "lookup": row.lookup,
                    "structure_unit_id": row.structure_unit_id,
                    "source_span_ids": list(row.source_span_ids),
                    "excerpt": row.excerpt,
                    "study_phase": row.study_phase,
                }
                for row in rows
            ],
            hydrated=hydrated,
            allowed_structure_unit_ids=[row.structure_unit_id for row in rows if row.role == "owned"],
            required_candidate_source_refs=list(config.get("required_candidate_source_refs") or []),
            forbidden_candidate_source_refs=list(config.get("forbidden_candidate_source_refs") or []),
            expected_disposition_by_source_ref=dict(config.get("expected_disposition_by_source_ref") or {}),
            expected_workflow_stage_ids_by_source_ref=dict(config.get("expected_workflow_stage_ids_by_source_ref") or {}),
            candidate_forbidden_markers_by_source_ref=dict(config.get("candidate_forbidden_markers_by_source_ref") or {}),
            candidate_required_markers_by_source_ref=dict(config.get("candidate_required_markers_by_source_ref") or {}),
        )
        assert issues, ref


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    markers = ["筛选必做", "基线必做", "不得入组", "发布控制点", "转移所有权"]
    for excerpt in excerpts.values():
        assert _forbidden_marker_hits(excerpt, markers) == []


def test_prompt_excludes_neighbor_package98_and_100() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    # package 98 owned excerpts must not appear
    for bad in (
        "痊愈：指不良事件消失。无论参与者的基线情况是否异常，当不良事件恢复至基线时，即为痊愈。",
        "不良事件的结束时间",
        "伴后遗症：指不良事件导致长期的或永久的生理机能障碍。",
        "如参与者死亡时未收集到结束时间",
    ):
        assert bad not in prompt_text
    # package 100 statistical chapter must not appear
    for bad in (
        "统计学考虑",
        "Statistical Analysis Plan，SAP",
        "统计假设",
    ):
        assert bad not in prompt_text


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for excerpt in OWNED_EXCERPT_BY_REF.values():
        assert excerpt in prompt_text


def test_prompt_contains_attached_sources() -> None:
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    for excerpt in ATTACHED_EXCERPT_BY_REF.values():
        assert excerpt in prompt_text


def test_matrix_has_no_rows_anchored_in_package99_or_attached(
    matrix: dict, plan: dict
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    blob = json.dumps(matrix, ensure_ascii=False)
    for ref in forbidden:
        assert ref not in blob


def test_no_official_rule_anchors_package99_owned_or_attached_spans(
    config: dict,
) -> None:
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_procedure_catalog_has_no_package99_node(
    procedure_catalog: dict,
) -> None:
    forbidden = set(OWNED_REFS + ATTACHED_REFS)
    blob = json.dumps(procedure_catalog, ensure_ascii=False)
    for ref in forbidden:
        assert ref not in blob


def test_known_targets_build_empty(config: dict) -> None:
    targets = config["known_targets"]
    assert targets["official_rules"] == []
    assert targets["required_procedures"] == []


def test_workflow_stages_are_nonbinding_replay_scaffold(config: dict) -> None:
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert {stage["workflow_stage_id"] for stage in config["workflow_stages"]} == {
        "flow-screening",
        "flow-baseline",
        "flow-d1-pre-dose",
    }


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    assert _sha256_file(CATALOG_DIR / "required_procedures.json") == EXPECTED_CATALOG_SHA256
    assert (CATALOG_DIR / "required_procedures.json").is_file()


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "第99包" in text
    assert "body.p1158" in text
    assert "body.p1167" in text
    assert "body.p986" in text
    assert "body.p996" in text
    assert "较晚者" in text
    assert "claims_complete=false" in text or "claims_complete=false" in text.replace(" ", "")
    assert "第98包" in text
    assert "第100包" in text
