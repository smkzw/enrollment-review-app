#!/usr/bin/env python3
"""Slice61cf model-free source-closure regressions.

Locks the D001 II package 94 SAE record / form / death materials / reporting
route boundary (frozen plan package 94: 应提供的安全信息资料及要求,
body.p1113-p1123) to its authoritative sources before any semantic replay
decision:

- config contract and role partition: 11 owned refs body.p1113-p1123
  (p1113/p1114/p1116/p1119/p1121 structural only; p1115 dual medical-record
  and event-form recording; p1117 all SAE treatment/record/form/signature/
  24h written report; p1118 new SAE form written follow-up; p1120 death
  materials to sponsor and regulator with open examples; p1122 appendix 7
  pointer; p1123 appendix 7 standalone change requires all parties' written
  confirmation); attached refs stay body.p1103-p1112 (package 93 read-only)
- heading obligation prevention: structural titles never invent record,
  report, recipient, timeline, contact, or change rules
- dual recording: medical record and corresponding event report form are
  parallel requirements, never either-or
- SAE object boundary: study-period all SAE regardless of drug relationship;
  never narrowed to drug-related SAE and never expanded to all AE/TEAE/lab/
  arbitrary safety data
- as-applicable scope: only treatment measures; never spills to record/form/
  signature/written report
- multi-action preservation and independent SAE awareness clock (never
  replaced by package 93 new-info clock)
- first written report vs follow-up separation; new SAE form + follow-up mark
- death materials remain open examples with both recipients; never closed or
  forced autopsy
- appendix 7 pointer-only; no fabricated contacts; written confirmation by
  all relevant parties (including but not limited to investigator/sponsor/CRO)
- package 95 prevention of absorption; zero candidates for owned+attached
- official matrix keeps zero rows anchored in body.p1113-p1123 or attached
  body.p1103-p1112 and zero 不良事件 / TEAE / SAE rows
- immutable source fingerprints and checklist freeze (claims_complete=false)

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
    / "representative_group_package94_sae_record_form_death_route_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61cf-package94-sae-record-form-death-route-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package94-sae-record-form-death-route-boundary"
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
    "96de5bbcb97cf33732f2091039123bf5fb53cef5dc96eb23424df94928f5fff1"
)

PLAN_ID = "papl-40b1237a22e538a278b4fd5e"
PACKAGE_94_ORDINAL = 94
PACKAGE_94_ID = "pap-205e346371315fa509f03126"
PACKAGE_93_ORDINAL = 93
PACKAGE_93_ID = "pap-2815c9e5b343ac6d7663ae21"
PACKAGE_95_ORDINAL = 95
PACKAGE_95_ID = "pap-d6a9d76caa3d4d5bd85c672e"
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_80_ORDINAL = 80
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_90_ORDINAL = 90
PACKAGE_91_ORDINAL = 91
PACKAGE_92_ORDINAL = 92

OWNED_REFS = [f"body.p{ordinal}" for ordinal in range(1113, 1124)]
ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1103, 1113)]
STRUCTURAL_REFS = [
    "body.p1113",
    "body.p1114",
    "body.p1116",
    "body.p1119",
    "body.p1121",
]
SEMANTIC_OWNED_REFS = [
    "body.p1115",
    "body.p1117",
    "body.p1118",
    "body.p1120",
    "body.p1122",
    "body.p1123",
]

PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG80_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1015, 1027)]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_TITLE_ONLY = ["body.p1102"]
PKG95_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1124, 1136)]

EXPECTED_UNIT_KIND_BY_REF = {
    "body.p1113": "paragraph",
    "body.p1114": "list_item",
    "body.p1115": "paragraph",
    "body.p1116": "list_item",
    "body.p1117": "paragraph",
    "body.p1118": "paragraph",
    "body.p1119": "list_item",
    "body.p1120": "paragraph",
    "body.p1121": "paragraph",
    "body.p1122": "paragraph",
    "body.p1123": "paragraph",
}

OWNED_EXCERPT_BY_REF = {
    "body.p1113": "应提供的安全信息资料及要求",
    "body.p1114": "原则",
    "body.p1115": (
        "研究者将负责确保所有关于事件和相关随访的正确信息均被记录在可溯源的参与者病历及对应的事件报告表上。"
    ),
    "body.p1116": "报告表的填写及随访要求",
    "body.p1117": (
        "研究期间发生的所有SAE，无论其与试验药物是否相关，研究者应立即（获知后24小时内）对参与者采取及时适当的治疗措施（如适用），完整并及时地记录所有相关信息，记录应尽可能详细，填写《SAE报告表》的所有使用部分，签名并签署日期，于获知后24小时内书面报告至申办者和其指定联系人。"
    ),
    "body.p1118": (
        "随后研究者应当及时提供详尽、书面的随访报告，随访信息或对质疑表中内容的回复将使用一份新的《SAE报告表》，并标明为之前报告的随访信息。"
    ),
    "body.p1119": "死亡报告的处理",
    "body.p1120": (
        "涉及死亡的报告，研究者应当向申办者和监管机构提供所有相关的资料，如尸检报告和最终医学报告。"
    ),
    "body.p1121": "报告途径",
    "body.p1122": "本研究的报告联系方式见附录7。",
    "body.p1123": (
        "附录7将根据实际情况进行单独变更（例如人员联系电话变动），变更内容应被所有相关方（包括但不限于研究者、申办者、参与本研究的CRO等）书面确认后生效。"
    ),
}

ATTACHED_EXCERPT_BY_REF = {
    "body.p1103": (
        "以下是研究者必须在获知后24小时（含）内向申办者报告的事件类型，无论事件与试验用药品的关系如何："
    ),
    "body.p1104": "死亡事件",
    "body.p1105": "严重不良事件",
    "body.p1106": "妊娠事件",
    "body.p1107": (
        "研究者必须立即向申办者报告这些事件的新的重要信息（在获知信息后24小时内），包括："
    ),
    "body.p1108": "新的体征或症状，或诊断改变",
    "body.p1109": "重要的新诊断检查结果",
    "body.p1110": "基于新信息的因果关系变化",
    "body.p1111": "事件结果的变化，包括恢复",
    "body.p1112": "关于事件临床过程的其他描述信息",
}

STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1113": ["应提供的安全信息资料及要求"],
    "body.p1114": ["原则"],
    "body.p1115": [
        "研究者",
        "事件和相关随访",
        "正确信息",
        "可溯源",
        "参与者病历",
        "对应的事件报告表",
    ],
    "body.p1116": ["报告表的填写及随访要求"],
    "body.p1117": [
        "研究期间发生的所有SAE",
        "无论其与试验药物是否相关",
        "立即（获知后24小时内）",
        "及时适当的治疗措施（如适用）",
        "完整并及时地记录",
        "尽可能详细",
        "《SAE报告表》的所有使用部分",
        "签名并签署日期",
        "于获知后24小时内",
        "书面报告",
        "申办者和其指定联系人",
    ],
    "body.p1118": [
        "随后",
        "及时",
        "详尽",
        "书面的随访报告",
        "新的《SAE报告表》",
        "标明为之前报告的随访信息",
    ],
    "body.p1119": ["死亡报告的处理"],
    "body.p1120": [
        "涉及死亡的报告",
        "申办者",
        "监管机构",
        "所有相关的资料",
        "如尸检报告和最终医学报告",
    ],
    "body.p1121": ["报告途径"],
    "body.p1122": ["报告联系方式", "附录7"],
    "body.p1123": [
        "附录7",
        "单独变更",
        "所有相关方",
        "包括但不限于",
        "书面确认后生效",
    ],
}

# 以下短语用于父级规格反例探针，不是运行时文本分类器。

HEADING_OBLIGATION_PHRASES = [
    "应提供的安全信息资料及要求标题本身构成24小时报告义务",
    "原则标题独立形成病历与报告表记录义务",
    "报告表的填写及随访要求标题直接设定签名与书面时限",
    "死亡报告的处理标题独立列出接收方与资料清单",
    "报告途径标题本身提供具体电话邮箱地址",
    "结构标题升格为独立控制点或入排门槛",
]

DUAL_RECORDING_EITHER_OR_PHRASES = [
    "事件信息记录在病历或对应事件报告表二者之一即可",
    "只需填写事件报告表，不必同步写入可溯源参与者病历",
    "可溯源病历已记录则无需对应事件报告表",
    "病历与报告表改成二选一记录要求",
    "删除可溯源性后仍可视为满足记录原则",
    "相关随访信息无需进入对应事件报告表",
]

SAE_OBJECT_NARROW_OR_EXPAND_PHRASES = [
    "仅药物相关SAE才需填写《SAE报告表》并书面报送",
    "无关SAE不适用获知后24小时书面报告",
    "所有不良事件均须按p1117完成治疗记录表单与书面报告",
    "全部TEAE均适用《SAE报告表》填写与24小时书面报送",
    "任何实验室异常均须按研究期间所有SAE规则报告",
    "任意安全性资料均适用获知后24小时书面报送申办者",
]

AS_APPLICABLE_SPILL_PHRASES = [
    "如适用时才完整记录相关信息",
    "如适用才填写《SAE报告表》所有使用部分",
    "如适用才签名并签署日期",
    "如适用才于获知后24小时内书面报告",
    "记录、表单、签名与书面报告均仅在适用时执行",
]

MULTI_ACTION_OMISSION_PHRASES = [
    "只需书面报告，无需填写《SAE报告表》所有使用部分",
    "只需治疗与记录，无需签名签署日期",
    "漏掉申办者指定联系人，仅报送申办者本部",
    "漏掉完整及时详细记录要求",
    "只保留治疗措施，省略表单签名与书面报告并列动作",
]

CLOCK_ERROR_PHRASES = [
    "获知后24小时后才书面报告即可",
    "按工作日口径计算24小时书面报送时限",
    "改为固定日历日次日17:00前书面报送",
    "必须0秒瞬时完成书面报告，否定24小时缓冲",
    "用新重要信息获知时钟替换本段SAE获知时钟",
    "随访新信息获知后24小时内规则覆盖首次SAE书面报送时钟",
]

FIRST_FOLLOWUP_COMPRESSION_PHRASES = [
    "首次书面报告与随访报告压成同一表单动作",
    "随访信息可直接改写首次《SAE报告表》无需新表",
    "质疑表回复无需标明为之前报告的随访信息",
    "删除新的《SAE报告表》要求",
    "书面随访弱化为口头或无序更新即可",
]

DEATH_MATERIALS_AND_RECIPIENT_PHRASES = [
    "死亡相关资料仅需提供尸检报告和最终医学报告两项",
    "所有死亡必须完成尸检后方可结案",
    "死亡报告仅向申办者提供资料，无需监管机构",
    "死亡报告仅向监管机构提供资料，无需申办者",
    "遗漏监管机构接收方",
]

APPENDIX7_FABRICATION_OR_WEAKENING_PHRASES = [
    "附录7联系电话为010-00000000，邮箱为sae@example.com",
    "在本包直接列出具体姓名电话邮箱地址替代附录7指针",
    "附录7变更经研究者或申办者任一方口头确认即可生效",
    "附录7变更仅需研究者、申办者、CRO三方确认，不包括其他相关方",
    "附录7单独变更等同于方案修订案自动生效",
]

PACKAGE95_ABSORPTION_PHRASES = [
    "申办者收到任何来源的安全性相关信息后均应当科学全面地分析评估",
    "申办者应当将SUSAR快速报告给所有参加临床试验的研究者",
    "对于致死或危及生命的SUSAR，应在首次获知后7天内尽快报告",
    "对于非致死或危及生命的SUSAR，应在首次获知后15天内尽快报告",
    "以下情况一般不作为快速报告内容",
    "非严重不良事件不作为快速报告内容",
]

CANDIDATE_UPGRADE_PHRASES = [
    "未在24小时内书面报送SAE的受试者筛选失败",
    "未完成《SAE报告表》签名视为基线不通过",
    "入组前必须完成附录7联系方式培训否则不得入组",
    "发布SAE报告表与死亡资料控制点",
    "筛选期必做：病历与事件报告表双记录核对",
    "基线期必做：书面确认附录7变更作为入组条件",
    "死亡资料示例缺失构成证据缺口，入排不通过",
]

ALL_DETERMINISTIC_PHRASES = (
    HEADING_OBLIGATION_PHRASES
    + DUAL_RECORDING_EITHER_OR_PHRASES
    + SAE_OBJECT_NARROW_OR_EXPAND_PHRASES
    + AS_APPLICABLE_SPILL_PHRASES
    + MULTI_ACTION_OMISSION_PHRASES
    + CLOCK_ERROR_PHRASES
    + FIRST_FOLLOWUP_COMPRESSION_PHRASES
    + DEATH_MATERIALS_AND_RECIPIENT_PHRASES
    + APPENDIX7_FABRICATION_OR_WEAKENING_PHRASES
    + PACKAGE95_ABSORPTION_PHRASES
    + CANDIDATE_UPGRADE_PHRASES
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _deterministic_hits(text: str) -> list[str]:
    return [phrase for phrase in ALL_DETERMINISTIC_PHRASES if phrase in text]


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


def _package94_contract_issues(config: dict) -> set[str]:
    """Validate the local Package 94 specification, not runtime model semantics."""
    issues: set[str] = set()
    semantics = config["exception_semantics_by_source_ref"]

    for ref in SEMANTIC_OWNED_REFS:
        if semantics[ref]["base_rule"] != OWNED_EXCERPT_BY_REF[ref]:
            issues.add(f"{ref}:SOURCE_TEXT")

    p1115 = " ".join(
        [
            semantics["body.p1115"]["exception_rule"],
            semantics["body.p1115"]["forbidden_inversion"],
            *semantics["body.p1115"]["preserve_keywords"],
        ]
    )
    if not all(
        fragment in p1115
        for fragment in ("参与者病历", "对应的事件报告表", "不得二选一")
    ):
        issues.add("body.p1115:DUAL_RECORDING")

    p1117 = " ".join(
        [
            semantics["body.p1117"]["exception_rule"],
            semantics["body.p1117"]["forbidden_inversion"],
            *semantics["body.p1117"]["preserve_keywords"],
        ]
    )
    required_actions = (
        "研究期间发生的所有SAE",
        "无论其与试验药物是否相关",
        "治疗措施（如适用）",
        "完整并及时地记录",
        "《SAE报告表》的所有使用部分",
        "签名并签署日期",
        "书面报告",
        "申办者和其指定联系人",
        "不得把'如适用'外溢",
    )
    if not all(fragment in p1117 for fragment in required_actions):
        issues.add("body.p1117:ACTION_SCOPE")
    if not all(
        fragment in p1117
        for fragment in (
            "立即（获知后24小时内）",
            "于获知后24小时内",
            "不得用第93包新信息时钟替换",
        )
    ):
        issues.add("body.p1117:CLOCK")

    p1118 = " ".join(
        [
            semantics["body.p1118"]["exception_rule"],
            semantics["body.p1118"]["forbidden_inversion"],
            *semantics["body.p1118"]["preserve_keywords"],
        ]
    )
    if not all(
        fragment in p1118
        for fragment in (
            "及时",
            "详尽",
            "书面",
            "新的《SAE报告表》",
            "之前报告的随访信息",
            "不得把首次与随访压缩为同一表单动作",
        )
    ):
        issues.add("body.p1118:FOLLOWUP_FORM")

    p1120 = " ".join(
        [
            semantics["body.p1120"]["exception_rule"],
            semantics["body.p1120"]["forbidden_inversion"],
            *semantics["body.p1120"]["preserve_keywords"],
        ]
    )
    if not all(
        fragment in p1120
        for fragment in (
            "申办者",
            "监管机构",
            "所有相关",
            "仅为示例",
            "不得强制尸检",
        )
    ):
        issues.add("body.p1120:DEATH_MATERIALS")

    p1122 = " ".join(
        [
            semantics["body.p1122"]["exception_rule"],
            semantics["body.p1122"]["forbidden_inversion"],
            *semantics["body.p1122"]["preserve_keywords"],
        ]
    )
    if not all(fragment in p1122 for fragment in ("附录7", "不得虚构")):
        issues.add("body.p1122:CONTACT_POINTER")

    p1123 = " ".join(
        [
            semantics["body.p1123"]["exception_rule"],
            semantics["body.p1123"]["forbidden_inversion"],
            *semantics["body.p1123"]["preserve_keywords"],
        ]
    )
    if not all(
        fragment in p1123
        for fragment in (
            "所有相关方",
            "包括但不限于",
            "书面确认后生效",
            "口头确认",
            "方案修订案",
        )
    ):
        issues.add("body.p1123:WRITTEN_CONFIRMATION")

    if set(config["owned_source_refs"] + config["attached_source_refs"]) & set(
        PKG95_SPAN_REFS
    ):
        issues.add("PACKAGE95_OWNERSHIP")
    return issues


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _attached_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_93_ORDINAL
    )
    return {
        u["source_ref"]: u["excerpt"]
        for u in pkg["owned_units"]
        if u["source_ref"] in ATTACHED_REFS
    }


def _structure_blob_text(blob: list[dict], ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == ref:
            return str(block.get("text") or "")
    raise AssertionError(f"block {ref} missing from structure blob")


@pytest.fixture(scope="module")
def config() -> dict:
    from slice59n_representative_group_control_replay import _load_config

    return _load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def plan() -> dict:
    return _load_json(PLAN_PATH)


@pytest.fixture(scope="module")
def matrix() -> dict:
    return _load_json(MATRIX_PATH)


@pytest.fixture(scope="module")
def procedure_catalog() -> dict:
    return _load_json(CATALOG_DIR / "required_procedures.json")


@pytest.fixture(scope="module")
def structure_blob() -> list[dict]:
    return _load_json(STRUCTURE_BLOB_PATH)


def test_config_contract(config: dict) -> None:
    assert (
        config["schema_version"]
        == "phase5/representative-group-control-replay-config/v1"
    )
    assert (
        config["group_id"]
        == "d001-ii-package94-sae-record-form-death-route-boundary"
    )
    assert config["task_id"] == "phase5-slice61cf-20260830"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["owned_source_refs"] == OWNED_REFS
    assert config["attached_source_refs"] == ATTACHED_REFS
    assert len(config["owned_source_refs"]) == 11
    assert len(config["attached_source_refs"]) == 10
    assert config["required_candidate_source_refs"] == []
    assert set(config["forbidden_candidate_source_refs"]) == set(
        OWNED_REFS + ATTACHED_REFS
    )
    assert config["pre_enrollment_source_refs"] == []
    assert config["structural_only_source_refs"] == STRUCTURAL_REFS

    dispositions = config["expected_disposition_by_source_ref"]
    assert set(dispositions) == set(SEMANTIC_OWNED_REFS)
    for ref in SEMANTIC_OWNED_REFS:
        assert dispositions[ref] == "post_treatment_execution", ref
    for ref in STRUCTURAL_REFS:
        assert ref not in dispositions

    for ref in OWNED_REFS + ATTACHED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {
            "筛选必做",
            "基线必做",
            "证据缺口",
            "不得入组",
            "排除标准",
            "入排不通过",
        } <= set(markers), ref
        assert ref in config["clinical_qc_checks_by_source_ref"]
        assert len(config["clinical_qc_checks_by_source_ref"][ref]) >= 2

    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert entry["preserve_keywords"]
        assert entry["forbidden_inversion"]


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg94 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    owned_94 = {u["source_ref"] for u in pkg94["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached == ATTACHED_REFS
    assert not (set(attached) & owned_94)
    assert "body.p1102" not in attached


def test_attached_refs_ownership_documented(plan: dict) -> None:
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_93_ORDINAL], ref
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_94_ORDINAL], ref
    assert owners.get("body.p1102") == [PACKAGE_93_ORDINAL]


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    assert set(PKG78_SPAN_REFS) <= counts[PACKAGE_78_ORDINAL] and len(
        counts[PACKAGE_78_ORDINAL]
    ) == 12
    assert set(PKG79_SPAN_REFS) <= counts[PACKAGE_79_ORDINAL] and len(
        counts[PACKAGE_79_ORDINAL]
    ) == 8
    assert set(PKG80_SPAN_REFS) <= counts[PACKAGE_80_ORDINAL] and len(
        counts[PACKAGE_80_ORDINAL]
    ) == 12
    assert set(PKG82_SPAN_REFS) <= counts[PACKAGE_82_ORDINAL] and len(
        counts[PACKAGE_82_ORDINAL]
    ) == 5
    assert set(PKG87_SPAN_REFS) <= counts[PACKAGE_87_ORDINAL] and len(
        counts[PACKAGE_87_ORDINAL]
    ) == 10
    assert set(PKG88_SPAN_REFS) <= counts[PACKAGE_88_ORDINAL] and len(
        counts[PACKAGE_88_ORDINAL]
    ) == 3
    assert set(PKG89_SPAN_REFS) <= counts[PACKAGE_89_ORDINAL] and len(
        counts[PACKAGE_89_ORDINAL]
    ) == 6
    assert set(PKG90_SPAN_REFS) <= counts[PACKAGE_90_ORDINAL] and len(
        counts[PACKAGE_90_ORDINAL]
    ) == 11
    assert set(PKG91_SPAN_REFS) <= counts[PACKAGE_91_ORDINAL] and len(
        counts[PACKAGE_91_ORDINAL]
    ) == 8
    assert set(PKG92_SPAN_REFS) <= counts[PACKAGE_92_ORDINAL] and len(
        counts[PACKAGE_92_ORDINAL]
    ) == 4
    assert set(ATTACHED_REFS + PKG93_TITLE_ONLY) <= counts[
        PACKAGE_93_ORDINAL
    ] and len(counts[PACKAGE_93_ORDINAL]) == 11
    assert set(OWNED_REFS) <= counts[PACKAGE_94_ORDINAL] and len(
        counts[PACKAGE_94_ORDINAL]
    ) == 11
    assert set(PKG95_SPAN_REFS) <= counts[PACKAGE_95_ORDINAL] and len(
        counts[PACKAGE_95_ORDINAL]
    ) == 12


def test_owned_refs_match_frozen_package_94(config: dict, plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    assert pkg["package_id"] == PACKAGE_94_ID
    assert [u["source_ref"] for u in pkg["owned_units"]] == OWNED_REFS
    assert config["owned_source_refs"] == OWNED_REFS


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    assert excerpts == OWNED_EXCERPT_BY_REF


def test_attached_unit_excerpts_verbatim(plan: dict) -> None:
    excerpts = _attached_excerpt_by_ref(plan)
    assert excerpts == ATTACHED_EXCERPT_BY_REF


def test_owned_unit_kinds_and_heading_paths(plan: dict) -> None:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    for unit in pkg["owned_units"]:
        ref = unit["source_ref"]
        assert unit.get("unit_kind") == EXPECTED_UNIT_KIND_BY_REF[ref], ref


def test_owned_excerpts_match_structure_blob(
    plan: dict, structure_blob: list[dict]
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref, excerpt in excerpts.items():
        assert excerpt == _structure_blob_text(structure_blob, ref)


def test_structural_heading_never_converted_to_obligations(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]
    for ref in STRUCTURAL_REFS:
        text = (
            semantics[ref]["exception_rule"]
            + " "
            + semantics[ref]["forbidden_inversion"]
        )
        assert "仅作结构" in text or "仅作结构" in semantics[ref]["exception_rule"]
        assert "不得" in semantics[ref]["forbidden_inversion"]


def test_specification_probe_catalog_is_unique_and_source_clean() -> None:
    assert ALL_DETERMINISTIC_PHRASES
    assert len(ALL_DETERMINISTIC_PHRASES) == len(set(ALL_DETERMINISTIC_PHRASES))
    for excerpt in OWNED_EXCERPT_BY_REF.values():
        assert _deterministic_hits(excerpt) == []


def test_p1115_dual_recording_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1115"]
    for frag in STRUCTURAL_FRAGMENTS_BY_REF["body.p1115"]:
        assert frag in semantics["base_rule"] or frag in " ".join(
            semantics["preserve_keywords"]
        )
    assert "二选一" in semantics["forbidden_inversion"]
    assert "可溯源" in " ".join(semantics["preserve_keywords"])


def test_dual_recording_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1115"]
    semantic["exception_rule"] = "病历或事件报告表记录任一即可；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["研究者", "事件和相关随访"]
    assert "body.p1115:DUAL_RECORDING" in _package94_contract_issues(mutated)


def test_p1117_sae_object_and_actions_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1117"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1117")
    assert missing == []
    inversion = semantics["forbidden_inversion"]
    assert "不得缩窄为药物相关SAE" in inversion
    assert "不得扩大到全部AE/TEAE/实验室异常" in inversion
    assert "如适用" in inversion
    assert "不得用第93包新信息时钟替换" in inversion


def test_p1117_action_scope_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1117"]
    semantic["exception_rule"] = "仅药物相关SAE在适用时记录并报告；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["研究期间发生的所有SAE"]
    assert "body.p1117:ACTION_SCOPE" in _package94_contract_issues(mutated)


def test_p1117_clock_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1117"]
    semantic["exception_rule"] = semantic["exception_rule"].replace(
        "不得用第93包新信息获知时钟替换本段SAE获知时钟", "沿用第93包新信息获知时钟"
    )
    semantic["forbidden_inversion"] = semantic["forbidden_inversion"].replace(
        "不得用第93包新信息时钟替换", "允许替换时钟"
    )
    semantic["preserve_keywords"] = [
        keyword
        for keyword in semantic["preserve_keywords"]
        if "获知后24小时内" not in keyword
    ]
    assert "body.p1117:CLOCK" in _package94_contract_issues(mutated)


def test_p1118_first_followup_separation_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1118"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1118")
    assert missing == []
    assert "不得把首次与随访压缩为同一表单动作" in semantics["forbidden_inversion"]
    assert "新的《SAE报告表》" in " ".join(semantics["preserve_keywords"])


def test_followup_form_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1118"]
    semantic["exception_rule"] = "沿用首次报告表口头补充随访；零候选"
    semantic["forbidden_inversion"] = "不得升格为入排控制点"
    semantic["preserve_keywords"] = ["随后"]
    assert "body.p1118:FOLLOWUP_FORM" in _package94_contract_issues(mutated)


def test_p1120_death_materials_and_recipients_preserved(config: dict) -> None:
    semantics = config["exception_semantics_by_source_ref"]["body.p1120"]
    missing = _missing_structural_fragments(semantics["base_rule"], "body.p1120")
    assert missing == []
    inversion = semantics["forbidden_inversion"]
    assert "不得遗漏申办者或监管机构" in inversion
    assert "不得把示例封闭为穷尽清单" in inversion
    assert "不得强制尸检" in inversion


def test_death_materials_contract_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    semantic = mutated["exception_semantics_by_source_ref"]["body.p1120"]
    semantic["exception_rule"] = "死亡报告只向申办者提供尸检报告；零候选"
    semantic["forbidden_inversion"] = "所有死亡必须尸检"
    semantic["preserve_keywords"] = ["申办者", "尸检报告"]
    assert "body.p1120:DEATH_MATERIALS" in _package94_contract_issues(mutated)


def test_appendix7_pointer_and_written_confirmation_preserved(config: dict) -> None:
    p1122 = config["exception_semantics_by_source_ref"]["body.p1122"]
    p1123 = config["exception_semantics_by_source_ref"]["body.p1123"]
    assert "附录7" in " ".join(p1122["preserve_keywords"])
    assert "不得虚构" in p1122["forbidden_inversion"]
    assert "书面确认后生效" in " ".join(p1123["preserve_keywords"])
    assert "包括但不限于" in " ".join(p1123["preserve_keywords"])
    assert "口头确认" in p1123["forbidden_inversion"]
    assert "方案修订案" in p1123["forbidden_inversion"]


def test_appendix7_contract_mutations_are_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    p1122 = mutated["exception_semantics_by_source_ref"]["body.p1122"]
    p1122["exception_rule"] = "联系人张某，电话13800000000"
    p1122["forbidden_inversion"] = "不得升格为入排控制点"
    assert "body.p1122:CONTACT_POINTER" in _package94_contract_issues(mutated)

    mutated = copy.deepcopy(config)
    p1123 = mutated["exception_semantics_by_source_ref"]["body.p1123"]
    p1123["exception_rule"] = "任一方口头确认即可生效"
    p1123["forbidden_inversion"] = "不得升格为入排控制点"
    p1123["preserve_keywords"] = ["附录7", "单独变更"]
    assert "body.p1123:WRITTEN_CONFIRMATION" in _package94_contract_issues(mutated)


def test_package95_content_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for ref in PKG95_SPAN_REFS:
        assert ref not in owned
        assert ref not in attached
    boundary = config["later_package_boundary"]["expected_owners_by_span"]
    for ref in PKG95_SPAN_REFS:
        assert boundary[ref] == PACKAGE_95_ORDINAL


def test_package95_ownership_mutation_is_detected(config: dict) -> None:
    mutated = copy.deepcopy(config)
    mutated["owned_source_refs"].append(PKG95_SPAN_REFS[0])
    assert "PACKAGE95_OWNERSHIP" in _package94_contract_issues(mutated)


def test_package94_contract_is_currently_closed(config: dict) -> None:
    assert _package94_contract_issues(config) == set()


def test_package93_clocks_not_rewritten(config: dict) -> None:
    qc_1117 = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1117"])
    assert "不得用第93包新信息获知时钟替换" in qc_1117
    qc_1107 = " ".join(config["clinical_qc_checks_by_source_ref"]["body.p1107"])
    assert "不得用本条新信息获知时钟替换p1117的SAE获知时钟" in qc_1107
    note = config["later_package_boundary"]["note"]
    assert "不得改写其三类事件与两套获知时钟" in note


def test_neighbor_packages_not_absorbed(config: dict) -> None:
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_TITLE_ONLY
        + PKG95_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in owned
        assert ref not in attached


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    expected_owners = boundary["expected_owners_by_span"]
    for pkg in plan["packages"]:
        ordinal = pkg["package_ordinal"]
        if ordinal in (
            78,
            79,
            80,
            82,
            87,
            88,
            89,
            90,
            91,
            92,
            93,
            94,
            95,
        ):
            for unit in pkg["owned_units"]:
                ref = unit["source_ref"]
                assert expected_owners.get(ref) == ordinal, (
                    f"{ref} 期望归属包 {ordinal}，配置中为 {expected_owners.get(ref)}"
                )


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    assert "第94包拥有安全信息资料要求、SAE治疗/记录/报告表/书面首次与随访、死亡资料及附录7报告途径" in note
    assert "第95包" in note
    assert "不提前吸收" in note
    assert "零候选" in note


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(ATTACHED_REFS)
    for ref in OWNED_REFS + ATTACHED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"

    assert by_ref["body.p1113"].excerpt == OWNED_EXCERPT_BY_REF["body.p1113"]
    assert "可溯源的参与者病历" in by_ref["body.p1115"].excerpt
    assert "对应的事件报告表" in by_ref["body.p1115"].excerpt
    assert "研究期间发生的所有SAE" in by_ref["body.p1117"].excerpt
    assert "于获知后24小时内书面报告至申办者和其指定联系人" in by_ref["body.p1117"].excerpt
    assert "新的《SAE报告表》" in by_ref["body.p1118"].excerpt
    assert "申办者和监管机构" in by_ref["body.p1120"].excerpt
    assert by_ref["body.p1122"].excerpt == OWNED_EXCERPT_BY_REF["body.p1122"]
    assert "书面确认后生效" in by_ref["body.p1123"].excerpt
    assert "获知后24小时（含）内" in by_ref["body.p1103"].excerpt
    assert "在获知信息后24小时内" in by_ref["body.p1107"].excerpt


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip()
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip()

    neighbors = (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG80_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG90_SPAN_REFS
        + PKG91_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_TITLE_ONLY
        + PKG95_SPAN_REFS
    )
    for ref in neighbors:
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 11
    assert summary["attached_count"] == 10
    assert summary["unit_count"] == 21
    assert summary["claims_complete"] is False


def test_hydrated_gate_enforces_zero_candidate_partition(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units
    from slice59n_representative_group_reject_gates import (
        evaluate_hydrated_agent_output,
    )

    rows = [
        {
            "source_ref": row.source_ref,
            "role": row.role,
            "lookup": row.lookup,
            "structure_unit_id": row.structure_unit_id,
            "source_span_ids": list(row.source_span_ids),
            "excerpt": row.excerpt,
            "study_phase": row.study_phase,
        }
        for row in _resolve_units(config)
    ]
    unit_by_ref = {row["source_ref"]: row["structure_unit_id"] for row in rows}
    dispositions = [
        {
            "structure_unit_id": unit_by_ref[ref],
            "disposition": disposition,
        }
        for ref, disposition in config["expected_disposition_by_source_ref"].items()
    ]
    kwargs = {
        "group_id": config["group_id"],
        "study_phase": config["study_phase"],
        "rows": rows,
        "hydrated": {"candidates": [], "dispositions": dispositions},
        "allowed_structure_unit_ids": [row["structure_unit_id"] for row in rows],
        "required_candidate_source_refs": config["required_candidate_source_refs"],
        "forbidden_candidate_source_refs": config["forbidden_candidate_source_refs"],
        "expected_disposition_by_source_ref": config[
            "expected_disposition_by_source_ref"
        ],
        "expected_workflow_stage_ids_by_source_ref": config[
            "expected_workflow_stage_ids_by_source_ref"
        ],
        "candidate_forbidden_markers_by_source_ref": config[
            "candidate_forbidden_markers_by_source_ref"
        ],
        "candidate_required_markers_by_source_ref": config[
            "candidate_required_markers_by_source_ref"
        ],
    }
    assert not evaluate_hydrated_agent_output(**kwargs)

    for ref in OWNED_REFS + ATTACHED_REFS:
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对SAE报告表与24小时书面报送，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    paraphrased_candidates = {
        "body.p1113": "安全信息资料要求章节作为入组前安全性培训门槛",
        "body.p1115": "病历与事件报告表双记录作为机构启动考核指标",
        "body.p1117": "研究期间SAE书面报送流程作为受试者随访执行前置条件",
        "body.p1118": "新表随访标记规范作为医学监查准入准则",
        "body.p1120": "死亡相关资料报送作为伦理委员会资格条件",
        "body.p1122": "附录7联系方式核对作为中心启动检查项",
        "body.p1123": "附录7书面确认变更作为合同签署前置要求",
        "body.p1103": "首次事件24小时报告义务作为研究者资质审核条件",
        "body.p1107": "新重要信息随访时限作为中心质量评分项",
    }
    for ref, title in paraphrased_candidates.items():
        assert _deterministic_hits(title) == [], "分区测试不得依赖规格探针原句"
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": title,
                    "semantics": {},
                }
            ],
            "dispositions": dispositions,
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref
        assert not any(issue.code == "DISPOSITION_MISMATCH" for issue in issues), ref

    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": ["su-not-in-group"],
                "title": "越界候选",
                "semantics": {},
            }
        ],
        "dispositions": dispositions,
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        hits = _deterministic_hits(excerpts[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"
    attached = _attached_excerpt_by_ref(plan)
    for ref in ATTACHED_REFS:
        hits = _deterministic_hits(attached[ref])
        assert hits == [], f"{ref} 只读附加来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    counterexamples_by_ref = {
        "body.p1113": [
            "筛选必做：应提供的安全信息资料及要求核对",
            "基线必做：安全信息资料章节确认",
            "安全信息资料要求未明确作为证据缺口，不得入组",
            "发布控制点：安全信息资料及要求",
        ],
        "body.p1115": [
            "筛选期必做：病历与事件报告表双记录培训",
            "基线必做：可溯源病历记录承诺",
            "双记录缺失视为证据缺口，判定入排不通过",
            "转移所有权至第94包发布控制点",
        ],
        "body.p1117": [
            "筛选必做：获知后24小时书面报送流程签署",
            "基线期必做：《SAE报告表》填写核对",
            "未完成24小时书面报告视为入排不通过",
            "研究期间所有SAE流程发布控制点",
        ],
        "body.p1118": [
            "筛选必做：新表书面随访标记确认",
            "基线必做：随访报告新表使用培训",
            "未标明随访信息视为证据缺口，不得入组",
        ],
        "body.p1120": [
            "筛选必做：死亡资料报送接收方核实",
            "基线必做：尸检与最终医学报告清单确认",
            "死亡相关资料缺失视为入排不通过",
        ],
        "body.p1122": [
            "筛选必做：附录7联系方式核对",
            "基线必做：报告途径联系人签署",
            "附录7指针缺失视为证据缺口，不符合入选标准",
        ],
        "body.p1123": [
            "筛选期必做：附录7书面确认变更流程培训",
            "基线必做：所有相关方书面确认承诺",
            "口头确认附录7变更视为入排不通过",
        ],
        "body.p1103": [
            "筛选必做：首次事件24小时报告流程告知",
            "基线必做：三类事件报告承诺",
            "首次获知时钟未签署视为入排不通过",
        ],
        "body.p1107": [
            "筛选必做：新重要信息立即报告培训",
            "基线期必做：新信息24小时内报送确认",
            "新重要信息随访机制缺失视为证据缺口，不得入组",
        ],
    }
    for ref, counterexamples in counterexamples_by_ref.items():
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        for text in counterexamples:
            hits = _forbidden_marker_hits(text, markers)
            assert hits, f"{ref} 升格反例未被 forbidden_markers 拦截: {text}"


def test_prompt_excludes_neighbor_and_package95_content() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")

    package95_fragments = [
        "申办者的报告要求",
        "申办者收到任何来源的安全性相关信息后，均应当科学全面地分析评估",
        "申办者应当将SUSAR快速报告给所有参加临床试验的研究者",
        "对于致死或危及生命的SUSAR，应在首次获知后7天内",
        "对于非致死或危及生命的SUSAR，应在首次获知后15天内",
        "以下情况一般不作为快速报告内容",
    ]
    for fragment in package95_fragments:
        assert fragment not in prompt_text, f"提示不当吸入第95包内容: {fragment}"

    # 第93包标题 p1102 不得作为独立来源进入；heading_path 中的“应报告的事件类型”
    # 是只读附加单元父级路径元数据，不视为吞并标题所有权。
    assert '"source_ref":"body.p1102"' not in prompt_text
    assert '"source_ref": "body.p1102"' not in prompt_text
    for ref in PKG95_SPAN_REFS:
        assert f'"source_ref":"{ref}"' not in prompt_text
        assert f'"source_ref": "{ref}"' not in prompt_text
    for fragment in [
        "评估CMS-D001片不良事件预期性见CMS-D001片的《研究者手册》",
        "可疑且非预期严重不良反应（Suspected Unexpected Serious Adverse Reaction，SUSAR）",
    ]:
        assert fragment not in prompt_text, f"提示不当吸入相邻包内容: {fragment}"


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    for ref in OWNED_REFS:
        assert OWNED_EXCERPT_BY_REF[ref] in prompt_text, f"{ref} 摘录未逐字进入提示"


def test_prompt_contains_attached_sources() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    for ref in ATTACHED_REFS:
        assert ATTACHED_EXCERPT_BY_REF[ref] in prompt_text, (
            f"{ref} 只读附加摘录未进入提示"
        )


def test_prompt_deterministic_phrases_clean() -> None:
    prompt_path = PREPARE_DIR / "execution" / "prompt.txt"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    hits = _deterministic_hits(prompt_text)
    assert hits == [], f"提示含确定性反例措辞: {hits}"


def test_matrix_has_no_rows_anchored_in_package94_or_attached(
    matrix: dict, plan: dict
) -> None:
    pkg94 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    all_refs = {u["source_ref"] for u in pkg94["owned_units"]} | set(ATTACHED_REFS)
    for row in matrix["rows"]:
        anchor = row.get("protocol_source_span_id") or row.get("source_span_id")
        assert anchor not in all_refs, (
            f"matrix row {row.get('rule_id')} anchored in {anchor}"
        )


def test_matrix_has_no_ae_teae_sae_rows(matrix: dict) -> None:
    for row in matrix["rows"]:
        text = " ".join(
            str(row.get(k, ""))
            for k in ("rule_id", "canonical_name", "description", "category")
        )
        assert "不良事件" not in text
        assert "TEAE" not in text
        assert "严重不良事件" not in text
        assert "应提供的安全信息资料及要求" not in text
        assert "《SAE报告表》" not in text


def test_no_official_rule_anchors_package94_owned_or_attached_spans(
    matrix: dict, plan: dict
) -> None:
    pkg94 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_94_ORDINAL
    )
    owned_spans = {
        span for u in pkg94["owned_units"] for span in u.get("source_span_ids", [])
    }
    attached_spans = set(ATTACHED_REFS)
    for row in matrix["rows"]:
        for span_id in row.get("source_span_ids", []):
            assert span_id not in owned_spans
            assert span_id not in attached_spans


def test_procedure_catalog_has_no_ae_or_sae_form_node(
    procedure_catalog: dict,
) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = item.get("label", "")
        assert "不良事件" not in label
        assert "TEAE" not in label
        assert "严重不良事件" not in label
        assert "SAE报告表" not in label
        assert "附录7" not in label


def test_no_procedure_node_sourced_from_package94_or_attached(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span_id in item.get("source_span_ids", []):
            for ordinal in list(range(1103, 1124)):
                assert not span_id.startswith(f"body.p{ordinal}"), span_id


def test_known_targets_build_empty(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert official == []
    assert procedures == []


def test_workflow_stages_are_nonbinding_replay_scaffold(config: dict) -> None:
    from slice59n_representative_group_control_replay import _workflow

    stages = {s.workflow_stage_id: s for s in _workflow(config)}
    assert set(stages) == {"flow-screening", "flow-baseline", "flow-d1-pre-dose"}
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}
    assert config["required_candidate_source_refs"] == []
    assert set(config["expected_disposition_by_source_ref"]) == set(
        SEMANTIC_OWNED_REFS
    )
    assert set(config["expected_disposition_by_source_ref"].values()) == {
        "post_treatment_execution"
    }
    rationale = config["phase_applicability"]["rationale"]
    assert "治疗后安全性记录与报告执行职责" in rationale
    assert "不是筛选/基线受试者执行义务" in rationale
    assert "不构成入排门槛" in rationale
    assert "全部禁止发射候选" in rationale


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(COVERAGE_PATH)
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_94_ID in text
    assert PACKAGE_93_ID in text
    assert PACKAGE_95_ID in text
    assert "body.p1113" in text
    assert "body.p1123" in text
    assert "body.p1103" in text
    assert "body.p1112" in text
    assert "claims_complete=false" in text
    assert "标题义务化" in text
    assert "病历/报告表二选一" in text
    assert "第95包吞并" in text
