#!/usr/bin/env python3
"""Slice61cc model-free source-closure regressions.

Locks the D001 II package 91 table 9 causality evaluation matrix boundary
(frozen plan package 91: 表9不良事件与试验用药品因果关系评价,
body.t14.r0-r7) to its authoritative sources before any semantic replay
decision:

- config contract and role partition: 8 owned refs body.t14.r0-r7
  (r0 table header 判定依据｜相关｜不相关 structural only; r1 five-level
  conclusion row; r2-r6 five symbol-matrix dimensions; r7 symbol notes);
  attached refs body.p1087-p1097 stay read-only with ownership preserved
  to package 90
- merged-cell structure kept: grid 10 cols x 8 rows, frozen structure only
  lists non-duplicate cell paths (r0 c0/c1/c7 with c1 相关 merging c1-c6
  and c7 不相关 merging c7-c9; r1 c1/c2/c3/c7/c9 with an empty c0
  outside membership; r2 c0/c1/c2/c3/c7/c9; r3
  c0/c1/c2/c3/c5/c7/c8/c9; r4 c0-c7/c9; r5 c0/c1/c2/c3/c7/c9; r6 c0-c9;
  r7 c0 p0-p5); no symbol-count-based missing-cell fabrication, no
  five-level compression, no column shift, no merge-range-as-one-conclusion
- five-level conclusion order kept verbatim: 肯定有关、很可能有关、可能有关、
  可能无关、无关; 表头'相关/不相关' neither replaces the package 90
  statistical related-group (first three classes only) nor changes the
  five-level conclusions
- symbol literals kept: - is 否定/阴性/暂未获得结果; -/? is dechallenge/
  rechallenge only (阴性/尚未进行/不适用); the two never swap; 未进行/不适用/
  暂未获得 never turned into definite negativity; ± only 时间关系不能排除;
  ++ only 可用其他'更加'合理的原因解释; never generalized to 强阳性/权重/分值/
  严重程度
- composite-judgment-matrix nature: the five dimensions are comprehensive
  judgment inputs; no scoring, no majority voting, no single-symbol
  sufficiency, no mechanical decision tree
- zero candidates: required_candidate_source_refs explicitly empty; every
  owned and attached ref is forbidden to emit a candidate
- package 90 read-only closure semantics: p1095 可参照表7 vs p1097/表9
  inconsistency preserved as 需要核对 (never silently corrected); statistical
  related-group keeps exactly three classes; no reverse inference from
  statistical grouping to individual-case reporting; p1096 joint judgment
  is OR (report scope), never upgraded to 最终确认相关
- no absorption: package 92 expectedness (p1098-p1101) / package 93
  report-flow (p1102-p1112) / table 7 secondary-event rules (t12.r0-r4) /
  packages 78/79/87/88/89 never enter this closure
- official matrix keeps zero rows anchored in body.t14 and zero 不良事件 /
  TEAE / SAE rows; procedure catalog has no AE node and no t14 spans
- immutable source fingerprints and checklist freeze

No model, transport, or publication is involved in this module.
"""

from __future__ import annotations

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
    / "representative_group_package91_table9_causality_matrix_boundary.v1.json"
)
CHECKLIST_PATH = (
    PHASE_CLOSURE
    / "slice61cc-package91-table9-causality-matrix-boundary-parent-checklist.md"
)
PREPARE_DIR = (
    PHASE_CLOSURE
    / "slice59n-prepare"
    / "d001-ii-package91-table9-causality-matrix-boundary"
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
PACKAGE_78_ORDINAL = 78
PACKAGE_79_ORDINAL = 79
PACKAGE_82_ORDINAL = 82
PACKAGE_87_ORDINAL = 87
PACKAGE_88_ORDINAL = 88
PACKAGE_89_ORDINAL = 89
PACKAGE_90_ORDINAL = 90
PACKAGE_90_ID = "pap-969cb2554a2487b656fbbb20"
PACKAGE_91_ORDINAL = 91
PACKAGE_91_ID = "pap-87e89271165354d285b2faa1"
PACKAGE_92_ORDINAL = 92
PACKAGE_92_ID = "pap-c6c57a2734d51175bf06d031"
PACKAGE_93_ORDINAL = 93

OWNED_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]

# 只读闭包（11）：第90包 p1087-p1097 按最小只读上下文进入本包，用于闭合
# 五级分类（p1088）、五要点综合评价（p1089）、五个评价要点（p1090-p1094）、
# 统计分组边界与原文表号矛盾（p1095）、SAE共同判断报告范围（p1096）与表9
# 入口标题（p1097）。全部只读，所有权与候选发射权仍归第90包。
PKG90_ATTACHED_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
ATTACHED_REFS = list(PKG90_ATTACHED_REFS)

# 相邻包所有权元数据（不进入本包拥有/不进入提示）：第78包（p995-p1006）、
# 第79包（p1007-p1014）、第82包表7继发事件规则（body.t12.r0-r4）、第87包
# （p1074-p1083）、第88包（p1084-p1086）、第89包表8（body.t13.r0-r5）、
# 第92包预期性评估（p1098-p1101）、第93包应报告事件类型与随访流程
# （p1102-p1112）。均归各自包，本包不提前吞并。
PKG78_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(995, 1007)]
PKG79_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1007, 1015)]
PKG82_SPAN_REFS = [f"body.t12.r{ordinal}" for ordinal in range(0, 5)]
PKG87_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1074, 1084)]
PKG88_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1084, 1087)]
PKG89_SPAN_REFS = [f"body.t13.r{ordinal}" for ordinal in range(0, 6)]
PKG90_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1087, 1098)]
PKG91_SPAN_REFS = [f"body.t14.r{ordinal}" for ordinal in range(0, 8)]
PKG92_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1098, 1102)]
PKG93_SPAN_REFS = [f"body.p{ordinal}" for ordinal in range(1102, 1113)]

# 表9单元元数据：unit_kind、成员格数、冻结结构非重复单元格路径
# （表网格10列8行，各行非重复单元格数不同：3/5/6/8/9/6/10/6）。
TABLE9_HEADER_REF = "body.t14.r0"
TABLE9_CONCLUSION_REF = "body.t14.r1"
TABLE9_DIMENSION_REFS = [f"body.t14.r{ordinal}" for ordinal in range(2, 7)]
TABLE9_SYMBOL_ROWS = [f"body.t14.r{ordinal}" for ordinal in range(2, 7)]
TABLE9_NOTE_REF = "body.t14.r7"
TABLE9_DISPOSITION_REFS = [f"body.t14.r{ordinal}" for ordinal in range(1, 8)]

EXPECTED_UNIT_KIND_BY_REF = {
    "body.t14.r0": "table_header",
    **{f"body.t14.r{ordinal}": "table_row" for ordinal in range(1, 7)},
    "body.t14.r7": "table_note",
}
EXPECTED_MEMBER_CELL_COUNT_BY_REF = {
    "body.t14.r0": 3,
    "body.t14.r1": 5,
    "body.t14.r2": 6,
    "body.t14.r3": 8,
    "body.t14.r4": 9,
    "body.t14.r5": 6,
    "body.t14.r6": 10,
    "body.t14.r7": 6,
}
# 冻结覆盖清单 table_context.member_cell_paths（非重复单元格路径，合并范围只
# 保留首个单元格）：r0 c1'相关'横向合并c1-c6、c7'不相关'横向合并c7-c9；
# r3行内含合并（无c4/c6）；r4无c8；r6含c1-c9全部。
MEMBER_CELL_PATHS_BY_REF = {
    "body.t14.r0": [[0, 0], [0, 1], [0, 7]],
    "body.t14.r1": [[1, 1], [1, 2], [1, 3], [1, 7], [1, 9]],
    "body.t14.r2": [[2, 0], [2, 1], [2, 2], [2, 3], [2, 7], [2, 9]],
    "body.t14.r3": [[3, 0], [3, 1], [3, 2], [3, 3], [3, 5], [3, 7], [3, 8], [3, 9]],
    "body.t14.r4": [
        [4, 0],
        [4, 1],
        [4, 2],
        [4, 3],
        [4, 4],
        [4, 5],
        [4, 6],
        [4, 7],
        [4, 9],
    ],
    "body.t14.r5": [[5, 0], [5, 1], [5, 2], [5, 3], [5, 7], [5, 9]],
    "body.t14.r6": [
        [6, 0],
        [6, 1],
        [6, 2],
        [6, 3],
        [6, 4],
        [6, 5],
        [6, 6],
        [6, 7],
        [6, 8],
        [6, 9],
    ],
    "body.t14.r7": [[7, 0]],
}

# 源结构块逐格文本（按非重复单元格路径顺序，与冻结计划摘录的' | '拼接一致）
CELL_TEXT_BY_REF = {
    "body.t14.r0": ("判定依据", "相关", "不相关"),
    "body.t14.r1": ("肯定有关", "很可能有关", "可能有关", "可能无关", "无关"),
    "body.t14.r2": ("是否有合理的时间关系", "+", "+", "+", "±", "-"),
    "body.t14.r3": (
        "是否符合已知的作用机制、特性或已知的不良反应",
        "+",
        "+",
        "+",
        "-",
        "+",
        "-",
        "-",
    ),
    "body.t14.r4": ("去激发结果", "+", "+", "+", "-/?", "+", "-/?", "-/?", "-/?"),
    "body.t14.r5": ("再激发结果", "+", "-/?", "-/?", "-/?", "-/?"),
    "body.t14.r6": (
        "是否可用其他合理的原因解释",
        "-",
        "-",
        "+",
        "-",
        "-",
        "-",
        "++",
        "+",
        "+",
    ),
    "body.t14.r7": (
        "注：",
        "“+”表示肯定，或阳性结果；",
        "“-”表示否定，或阴性结果，或暂未获得结果的情况；",
        "“±”表示时间关系不能排除；",
        "“++”表示可用其他“更加”合理的原因解释；",
        "“-/?”表示去激发/再激发结果为阴性，或尚未进行去激发/再激发，或不适用去激发/再激发。",
    ),
}

# 冻结计划拥有单元逐字摘录（权威文本，任何改写反例必须破坏至少一个片段）
EXPECTED_EXCERPT_BY_REF = {
    ref: " | ".join(CELL_TEXT_BY_REF[ref]) for ref in OWNED_REFS
}

# 关键逐字片段门禁：改写文本必须保留的编码术语边界。符号行除单个关键片段外
# 还保留整行逐格拼接序列——任一符号被增删、互换或移动都会破坏该序列。
STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.t14.r0": ["判定依据", "相关", "不相关"],
    "body.t14.r1": [
        "肯定有关",
        "很可能有关",
        "可能有关",
        "可能无关",
        # 整行逐格拼接序列：'无关'是'可能无关'的子串，只能靠整行序列区分
        "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关",
    ],
    "body.t14.r2": [
        "是否有合理的时间关系",
        "±",
        "是否有合理的时间关系 | + | + | + | ± | -",
    ],
    "body.t14.r3": [
        "是否符合已知的作用机制、特性或已知的不良反应",
        "是否符合已知的作用机制、特性或已知的不良反应 | + | + | + | - | + | - | -",
    ],
    "body.t14.r4": [
        "去激发结果",
        "-/?",
        "去激发结果 | + | + | + | -/? | + | -/? | -/? | -/?",
    ],
    "body.t14.r5": [
        "再激发结果",
        "-/?",
        "再激发结果 | + | -/? | -/? | -/? | -/?",
    ],
    "body.t14.r6": [
        "是否可用其他合理的原因解释",
        "++",
        "是否可用其他合理的原因解释 | - | - | + | - | - | - | ++ | + | +",
    ],
    "body.t14.r7": [
        "注：",
        "“+”表示肯定，或阳性结果；",
        "“-”表示否定，或阴性结果，或暂未获得结果的情况；",
        "“±”表示时间关系不能排除；",
        "“++”表示可用其他“更加”合理的原因解释；",
        "“-/?”表示去激发/再激发结果为阴性，或尚未进行去激发/再激发，或不适用去激发/再激发。",
    ],
}

# 五级结论顺序（权威顺序，任何重排/压缩/增删都必须破坏该顺序）
FIVE_LEVEL_SEQUENCE = ["肯定有关", "很可能有关", "可能有关", "可能无关", "无关"]

# 只读闭包单元逐字摘录（第90包，p1087-p1097）
ATTACHED_EXCERPT_BY_REF = {
    "body.p1087": "不良事件因果关系判断",
    "body.p1088": "根据药物与不良事件相关性判断标准，按照五分法将不良事件与试验用药品相关性判定结果分为：肯定有关、很可能有关、可能有关、可能无关、无关。",
    "body.p1089": "研究者需根据五个评价要点进行临床试验个例不良事件与试验用药品相关性综合评价，并提供相关性判定依据。五个评价要点概括如下：",
    "body.p1090": "时间相关性：试验用药品和不良事件出现的有无合理的时间关系；",
    "body.p1091": "是否已知：不良事件是否符合该药物已知的作用机制、特性或已知的不良反应；",
    "body.p1092": "去激发结果：参与者在停药或减量后，可疑的不良事件是否减轻、好转或消失；",
    "body.p1093": "再激发结果：参与者在再次给药后，已经消除的同样、同性质的不良事件再次出现；",
    "body.p1094": "其他合理解释：不良事件是否可用参与者疾病进展（包括伴随疾病）、合并用药的作用、其他治疗措施或干扰因素等的影响来解释。",
    "body.p1095": "不良事件与试验用药品相关性判定结果分类及判定依据可参照表7进行。统计分析时，将“肯定有关”、“很可能有关”、“可能有关”视为与试验用药品相关。",
    "body.p1096": "严重不良事件（SAE）与试验用药品的因果关系由研究者和申办者双方共同判断。当双方意见不一致时，对研究者或/和申办者任意一方判断与试验用药品相关的严重不良事件，均属报告范围。",
    "body.p1097": "表 9 不良事件与试验用药品因果关系评价",
}
ATTACHED_STRUCTURAL_FRAGMENTS_BY_REF = {
    "body.p1087": ["不良事件因果关系判断"],
    "body.p1088": ["五分法", "肯定有关", "很可能有关", "可能有关", "可能无关", "无关"],
    "body.p1089": ["五个评价要点", "综合评价", "相关性判定依据"],
    "body.p1090": ["时间相关性", "合理的时间关系"],
    "body.p1091": ["是否已知", "已知的作用机制", "已知的不良反应"],
    "body.p1092": ["去激发结果", "停药或减量", "减轻、好转或消失"],
    "body.p1093": ["再激发结果", "再次给药", "同样、同性质的不良事件再次出现"],
    "body.p1094": ["其他合理解释", "疾病进展", "合并用药", "干扰因素"],
    "body.p1095": ["可参照表7进行", "肯定有关", "很可能有关", "可能有关", "视为与试验用药品相关"],
    "body.p1096": ["共同判断", "意见不一致", "任意一方判断与试验用药品相关", "均属报告范围"],
    "body.p1097": ["表 9 不良事件与试验用药品因果关系评价"],
}

# 以下短语用于父级规格反例探针，不是运行时文本分类器。运行时的零候选边界由
# forbidden_candidate_source_refs 按来源身份确定性拒绝，不能依赖有限关键词覆盖
# 同义改写。
# 合并单元格错位/臆造缺失值/压缩列位/移动列位的确定性措辞门禁
MERGED_CELL_MISALIGNMENT_PHRASES = [
    "按符号数量补齐",
    "按摘出符号臆造",
    "臆造缺失符号",
    "按五列对齐压缩",
    "压缩为五列",
    "把合并范围解释为同一结论",
    "合并单元格即同一评价结论",
    "将合并表头拆成多列",
    "五列对齐",
    "按列位对齐五级结论",
]

# 符号互换（-与-/?、±与++）的确定性措辞门禁
SYMBOL_SWAP_PHRASES = [
    "-/?即-",
    "-即-/?" ,
    "把-/改为-",
    "把-改为-/?",
    "-/?等同-",
    "去激发-即阴性",
    "再激发-即阴性",
    "±与++互换",
    "++即±",
    "±即++",
    "把±改为++",
    "把++改为±",
]

# 未知状态阴性化（未进行/不适用/暂未获得 -> 确定阴性）的确定性措辞门禁
UNKNOWN_STATUS_NEGATION_PHRASES = [
    "尚未进行去激发即视为阴性",
    "未进行去激发即阴性",
    "尚未进行再激发即视为阴性",
    "未进行再激发即阴性",
    "不适用即阴性",
    "不适用按阴性",
    "暂未获得结果即阴性",
    "暂未获得按阴性处理",
    "视为确定阴性",
    "判定为确定阴性",
    "即确定阴性",
    "确定为阴性结果",
    "未进行即按阴性",
    "尚未进行即按阴性",
]

# 符号泛化（±/++ -> 强阳性/权重/分值/严重程度）的确定性措辞门禁
SYMBOL_GENERALIZATION_PHRASES = [
    "±为强阳性",
    "±视为强阳性",
    "++为强阳性",
    "++视为强阳性",
    "±权重",
    "++权重",
    "符号赋权",
    "±计分",
    "++计分",
    "±分值",
    "++分值",
    "±视为严重程度",
    "++视为严重程度",
    "符号即严重程度",
    "符号即强度等级",
    "视为强度等级",
    "±强度",
    "++强度",
]

# 计分化（符号/维度加权计分）的确定性措辞门禁
SCORING_PHRASES = [
    "按符号计分",
    "符号计分",
    "符号加权",
    "每格计1分",
    "计1分",
    "按总分判定",
    "加总判定",
    "按维度计分",
    "维度加权",
    "得分达到",
    "计分达到",
    "固定计分",
    "按评分",
    "加权评分",
    "计分规则",
    "要点打分",
    "按要点计分",
    "要点加权",
]

# 多数表决化的确定性措辞门禁
MAJORITY_VOTING_PHRASES = [
    "多数表决",
    "按符号多数",
    "符号多数",
    "票数过半",
    "多数决定",
    "投票决定",
    "过半符号",
    "多数符号",
    "4个以上为+",
    "多数为+即",
    "按多数+判定",
]

# 单项充分化的确定性措辞门禁
SINGLE_SUFFICIENT_PHRASES = [
    "任一符号即",
    "任一符号即可",
    "单个维度即",
    "一项符号即可",
    "任意一项符号",
    "单项充分",
    "单项即判定",
    "一个维度即可",
    "单独作为判定",
    "单独作为充分条件",
    "单独作为否定条件",
    "任一维度即",
]

# 机械决策树化的确定性措辞门禁
DECISION_TREE_PHRASES = [
    "决策树",
    "机械决策",
    "自动判定相关",
    "算法判定",
    "机械判定",
    "跨项目通用算法",
    "通用算法",
]

# 五级列压缩/增删级别/重排的确定性措辞门禁（顺序另由_assert_five_level_order检查）
FIVE_LEVEL_COMPRESSION_PHRASES = [
    "压缩为三级",
    "压缩为3级",
    "合并级别",
    "三级结论",
    "删去可能无关",
    "删去无关",
    "增删级别",
    "五级缩为三级",
    "减为四级",
    "五级简化",
    "只需三类",
    "只需三个级别",
    "把可能无关与无关合并",
]

# 表号静默纠正的确定性措辞门禁（p1095'可参照表7'不得改为表9）
TABLE_NUMBER_SILENT_CORRECTION_PHRASES = [
    "可参照表9进行",
    "参照表9进行",
    "将表7更正为表9",
    "表7即表9",
    "表7实为表9",
    "表7应为表9",
    "表7系笔误",
    "表7（即表9）",
    "表7就是表9",
]

# 统计分组扩大的确定性措辞门禁（相关分组只含前三类：肯定有关/很可能有关/可能有关）
STAT_GROUP_EXPANSION_PHRASES = [
    "统计分组包含可能无关",
    "可能无关也视为相关",
    "可能无关也视为与试验用药品相关",
    "无关也视为相关",
    "将可能无关纳入相关组",
    "将无关纳入相关组",
    "扩大为五类",
    "统计时纳入可能无关",
    "可能无关计入相关",
]

# 由统计分组反推个例报告规则的确定性措辞门禁
REVERSE_INFERENCE_PHRASES = [
    "统计相关即个例报告",
    "统计相关即需报告",
    "相关分组即报告范围",
    "统计相关即确认",
    "按统计分组反推个例",
    "统计相关即上报",
]

# '报告范围'升级为'最终确认相关'的确定性措辞门禁
REPORT_SCOPE_UPGRADE_PHRASES = [
    "即最终确认相关",
    "即确认相关",
    "确认为最终相关",
    "即因果结论成立",
    "等同于确认因果关系",
    "即确认因果关系",
    "作为最终因果结论",
    "确认因果关系成立",
]

# 跨维度混同（五级结论/严重程度/SAE严重性/预期性/报告时限/已知性互相替代）门禁
DIMENSION_CONFLATION_PHRASES = [
    "因果关系即严重程度",
    "严重程度即因果关系",
    "因果判断即SAE判定",
    "按SAE严重性判断因果",
    "因果关系即预期性",
    "预期性即因果关系",
    "因果判断即报告时限",
    "按报告时限判断因果",
    "因果相关即SAE",
    "以严重程度判定因果",
    "以预期性判定因果",
    "以SAE严重性替代因果",
    "因果判断即预期性判断",
    "因果关系即报告时限",
    "五级结论即严重程度",
    "五级即SAE",
    "五级即预期性",
    "五级结论即预期性",
    "肯定有关即5级",
    "肯定有关即SAE",
    "可能无关即1级",
    "无关即1级",
    "已知性即预期性",
    "预期性即已知性",
    "符合已知机制即预期性",
    "已知不良反应即预期性",
    "表头相关即统计相关",
    "相关/不相关即统计分组",
    "表头相关替代统计分组",
    "报告范围即最终确认",
]

ALL_DETERMINISTIC_PHRASES = (
    MERGED_CELL_MISALIGNMENT_PHRASES
    + SYMBOL_SWAP_PHRASES
    + UNKNOWN_STATUS_NEGATION_PHRASES
    + SYMBOL_GENERALIZATION_PHRASES
    + SCORING_PHRASES
    + MAJORITY_VOTING_PHRASES
    + SINGLE_SUFFICIENT_PHRASES
    + DECISION_TREE_PHRASES
    + FIVE_LEVEL_COMPRESSION_PHRASES
    + TABLE_NUMBER_SILENT_CORRECTION_PHRASES
    + STAT_GROUP_EXPANSION_PHRASES
    + REVERSE_INFERENCE_PHRASES
    + REPORT_SCOPE_UPGRADE_PHRASES
    + DIMENSION_CONFLATION_PHRASES
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _deterministic_hits(text: str) -> list[str]:
    return [phrase for phrase in ALL_DETERMINISTIC_PHRASES if phrase in text]


def _forbidden_marker_hits(text: str, markers: list[str]) -> list[str]:
    """确定性门禁：命中任一禁止升格措辞即返回该措辞列表。"""
    return [marker for marker in markers if marker in text]


def _missing_structural_fragments(text: str, ref: str) -> list[str]:
    """结构级片段门禁：改写文本必须保留编码术语边界/限定/顺序的逐字片段。"""
    return [frag for frag in STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text]


def _missing_attached_fragments(text: str, ref: str) -> list[str]:
    return [
        frag for frag in ATTACHED_STRUCTURAL_FRAGMENTS_BY_REF[ref] if frag not in text
    ]


def _five_level_order_violation(text: str) -> bool:
    """五级结论顺序门禁：权威顺序中的级别若在文本中全部出现，必须保持
    '肯定有关、很可能有关、可能有关、可能无关、无关'的严格顺序。"""
    positions: list[int] = []
    for level in FIVE_LEVEL_SEQUENCE:
        index = text.find(level)
        if index < 0:
            return False  # 缺失由片段门禁负责
        positions.append(index)
    return positions != sorted(positions)


def _owned_excerpt_by_ref(plan: dict) -> dict[str, str]:
    pkg = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_91_ORDINAL
    )
    return {u["source_ref"]: u["excerpt"] for u in pkg["owned_units"]}


def _frozen_unit_by_ref(plan: dict) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            units.setdefault(u["source_ref"], u)
    return units


def _structure_blob_cell_text(blob: list[dict], cell_ref: str) -> str:
    for block in blob:
        if block.get("source_ref") == cell_ref:
            return str(block.get("text") or "")
    raise AssertionError(f"cell {cell_ref} missing from structure blob")


def _structure_blob_block(blob: list[dict], ref: str) -> dict:
    for block in blob:
        if block.get("source_ref") == ref:
            return block
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


@pytest.fixture(scope="module")
def coverage() -> dict:
    return _load_json(COVERAGE_PATH)


# ---------------------------------------------------------------------------
# config contract
# ---------------------------------------------------------------------------


def test_config_contract(config: dict) -> None:
    assert config["schema_version"] == "phase5/representative-group-control-replay-config/v1"
    assert config["group_id"] == "d001-ii-package91-table9-causality-matrix-boundary"
    assert config["task_id"] == "phase5-slice61cc-20260830"
    assert config["study_phase"] == "phase_ii"
    assert config["batching"]["mode"] == "single_batch_with_known_targets"
    assert config["expected_protocol_sha256"] == EXPECTED_DOCX_SHA256

    owned = set(config["owned_source_refs"])
    assert owned == set(OWNED_REFS)
    assert len(config["owned_source_refs"]) == 8

    structural = set(config["structural_only_source_refs"])
    forbidden = set(config["forbidden_candidate_source_refs"])
    pre_enrollment = set(config["pre_enrollment_source_refs"])
    required = set(config["required_candidate_source_refs"])
    assert structural == {TABLE9_HEADER_REF}, "第91包表头仅作结构"
    assert structural <= owned
    assert forbidden == set(OWNED_REFS + ATTACHED_REFS), (
        "第91包拥有单元与只读附加单元均禁止发射候选"
    )
    assert pre_enrollment == set()
    assert required == set(), "第91包不发射任何候选"
    assert required.isdisjoint(forbidden)

    # 零候选不等于无语义处置：表头仅作结构，r1结论行与r2-r7保持治疗后执行语义
    assert config["expected_disposition_by_source_ref"] == {
        ref: "post_treatment_execution" for ref in TABLE9_DISPOSITION_REFS
    }
    assert config["expected_workflow_stage_ids_by_source_ref"] == {}

    # 全部拥有与只读附加单元的禁止升格措辞必须已写入配置
    for ref in OWNED_REFS + ATTACHED_REFS:
        markers = config["candidate_forbidden_markers_by_source_ref"][ref]
        assert len(markers) >= 10, ref
        assert {"筛选必做", "基线必做", "证据缺口", "不得入组", "排除标准", "入排不通过"} <= set(
            markers
        ), ref
    assert config["candidate_required_markers_by_source_ref"] == {}
    assert set(config["candidate_forbidden_markers_by_source_ref"]) == forbidden

    # 合并单元格/五级顺序/符号原义/矩阵性质语义结构必须在配置中显式保留
    semantics = config["exception_semantics_by_source_ref"]
    assert set(semantics) == set(OWNED_REFS)
    for ref, entry in semantics.items():
        assert entry["base_rule"] and entry["exception_rule"]
        assert len(entry["preserve_keywords"]) >= 1, ref
        assert entry["forbidden_inversion"], ref
    # 只读闭包逐条质检声明
    for ref in ATTACHED_REFS:
        assert config["clinical_qc_checks_by_source_ref"][ref], ref
    assert config["ids"]["manifest_id"].startswith("manifest:slice61cc-package91")
    assert config["ids"]["catalog_id"].startswith("catalog:slice61cc-package91")


def test_attached_refs_are_read_only(config: dict, plan: dict) -> None:
    pkg91 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_91_ORDINAL
    )
    owned_91 = {u["source_ref"] for u in pkg91["owned_units"]}
    attached = config["attached_source_refs"]
    assert attached, "attached closure must not be empty"
    assert not (set(attached) & owned_91), "attached refs must not be owned by package 91"
    assert set(attached) == set(ATTACHED_REFS)
    assert len(attached) == 11


def test_attached_refs_ownership_documented(plan: dict) -> None:
    """背景来源保持原所有权，锚点只读且不改变既有包职责。"""
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref in PKG90_ATTACHED_REFS:
        assert owners.get(ref) == [PACKAGE_90_ORDINAL], f"{ref} 必须保持归第90包"
    for ref in OWNED_REFS:
        assert owners.get(ref) == [PACKAGE_91_ORDINAL], f"{ref} 必须保持归第91包"


def test_neighbor_boundary_counts_match_real_plan(plan: dict) -> None:
    """冻结计划实际所有权：第78包拥有p995-p1006（12）、第79包拥有p1007-p1014（8）、
    第82包拥有body.t12.r0-r4（5）、第87包拥有p1074-p1083（10）、第88包拥有
    p1084-p1086（3）、第89包拥有body.t13.r0-r5（6）、第90包拥有p1087-p1097（11）、
    第91包拥有body.t14.r0-r7（8）、第92包拥有p1098-p1101（4）、第93包拥有
    p1102-p1112（11）。"""
    counts = {
        p["package_ordinal"]: {u["source_ref"] for u in p["owned_units"]}
        for p in plan["packages"]
    }
    owned_78 = counts[PACKAGE_78_ORDINAL]
    owned_79 = counts[PACKAGE_79_ORDINAL]
    owned_82 = counts[PACKAGE_82_ORDINAL]
    owned_87 = counts[PACKAGE_87_ORDINAL]
    owned_88 = counts[PACKAGE_88_ORDINAL]
    owned_89 = counts[PACKAGE_89_ORDINAL]
    owned_90 = counts[PACKAGE_90_ORDINAL]
    owned_91 = counts[PACKAGE_91_ORDINAL]
    owned_92 = counts[PACKAGE_92_ORDINAL]
    owned_93 = counts[PACKAGE_93_ORDINAL]
    assert set(PKG78_SPAN_REFS) <= owned_78 and len(owned_78) == 12
    assert set(PKG79_SPAN_REFS) <= owned_79 and len(owned_79) == 8
    assert set(PKG82_SPAN_REFS) <= owned_82 and len(owned_82) == 5
    assert set(PKG87_SPAN_REFS) <= owned_87 and len(owned_87) == 10
    assert set(PKG88_SPAN_REFS) <= owned_88 and len(owned_88) == 3
    assert set(PKG89_SPAN_REFS) <= owned_89 and len(owned_89) == 6
    assert set(PKG90_SPAN_REFS) <= owned_90 and len(owned_90) == 11
    assert set(PKG91_SPAN_REFS) <= owned_91 and len(owned_91) == 8
    assert set(PKG92_SPAN_REFS) <= owned_92 and len(owned_92) == 4
    assert set(PKG93_SPAN_REFS) <= owned_93 and len(owned_93) == 11


# ---------------------------------------------------------------------------
# frozen plan ownership and table identity
# ---------------------------------------------------------------------------


def test_owned_refs_match_frozen_package_91(config: dict, plan: dict) -> None:
    matches = [p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_91_ORDINAL]
    assert len(matches) == 1
    pkg = matches[0]
    assert pkg["package_id"] == PACKAGE_91_ID
    assert plan["plan_id"] == PLAN_ID
    owned = {u["source_ref"] for u in pkg["owned_units"]}
    assert owned == set(config["owned_source_refs"])


def test_owned_unit_excerpts_verbatim(config: dict, plan: dict) -> None:
    excerpts = _owned_excerpt_by_ref(plan)
    for ref in OWNED_REFS:
        assert excerpts[ref] == EXPECTED_EXCERPT_BY_REF[ref], (
            f"{ref} 摘录与冻结计划不一致"
        )


def test_table9_heading_hierarchy(config: dict, plan: dict) -> None:
    """表9全部拥有单元位于'表 9 不良事件与试验用药品因果关系评价'标题之下，
    且位于'不良事件因果关系判断'与'不良事件的评估'层级。"""
    package = next(
        item for item in plan["packages"] if item["package_id"] == PACKAGE_91_ID
    )
    units = {item["source_ref"]: item for item in package["owned_units"]}
    for ref in OWNED_REFS:
        assert units[ref]["heading_path"][-1] == "表 9 不良事件与试验用药品因果关系评价"
        assert "不良事件因果关系判断" in units[ref]["heading_path"]
        assert "不良事件的评估" in units[ref]["heading_path"]
        assert "安全性评估" in units[ref]["heading_path"]
        assert units[ref]["phase_scopes"] == ["unknown"], ref


def test_table9_unit_kinds_and_member_cells(plan: dict) -> None:
    """r0是table_header；r1-r6是table_row；r7是table_note。成员格数必须与
    冻结结构非重复单元格路径一致（3/5/6/8/9/6/10/6），不得按符号数量臆造。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        assert unit["unit_kind"] == EXPECTED_UNIT_KIND_BY_REF[ref], ref
        assert len(unit["member_source_refs"]) == EXPECTED_MEMBER_CELL_COUNT_BY_REF[ref], ref
        assert len(unit["source_span_ids"]) == EXPECTED_MEMBER_CELL_COUNT_BY_REF[ref], ref


def test_table9_cell_text_matches_structure_blob(plan: dict, structure_blob: list[dict]) -> None:
    """行摘录必须与源结构块逐格文本按非重复单元格路径顺序拼接一致，证明无
    列错位、无符号增删、无按符号数量臆造缺失值、无虚构内容。"""
    units = _frozen_unit_by_ref(plan)
    for ref in OWNED_REFS:
        unit = units[ref]
        expected_cells = CELL_TEXT_BY_REF[ref]
        assert len(expected_cells) == len(unit["member_source_refs"]), ref
        for index, cell_ref in enumerate(unit["member_source_refs"]):
            cell_text = _structure_blob_cell_text(structure_blob, cell_ref)
            assert cell_text == expected_cells[index], (
                f"{ref} 第{index + 1}格与源结构块不一致: {cell_text!r} != {expected_cells[index]!r}"
            )
        joined = " | ".join(expected_cells)
        assert unit["excerpt"] == joined, f"{ref} 摘录与逐格拼接不一致"


def test_table9_grid_and_merged_cell_paths_match_frozen(
    plan: dict, structure_blob: list[dict], coverage: dict
) -> None:
    """表9网格10列8行；冻结覆盖清单的member_cell_paths与非重复单元格路径一致；
    合并单元格结构（r0 c1'相关'合并c1-c6、c7'不相关'合并c7-c9；r3含c5无c4/c6；
    r4含c4-c7无c8；r6含c1-c9全部）必须保持。"""
    table_block = _structure_blob_block(structure_blob, "body.t14")
    assert table_block["table_cols"] == 10
    assert table_block["table_rows"] == 8

    units = _frozen_unit_by_ref(plan)
    manifest_units = {u["source_ref"]: u for u in coverage["units"]}
    for ref in OWNED_REFS:
        unit = units[ref]
        expected_paths = MEMBER_CELL_PATHS_BY_REF[ref]
        assert unit["table_context"]["member_cell_paths"] == expected_paths, ref
        assert manifest_units[ref]["table_context"]["member_cell_paths"] == expected_paths, ref
        # 非重复单元格路径必须映射到成员格 source_span_ids（r7为c0内六段注记p0-p5）
        if ref == TABLE9_NOTE_REF:
            assert len(unit["member_source_refs"]) == 6, ref
        else:
            assert len(unit["member_source_refs"]) == len(expected_paths), ref

    # r0：c1'相关'横向合并c1-c6、c7'不相关'横向合并c7-c9（10列中只列c0/c1/c7）
    assert units[TABLE9_HEADER_REF]["table_context"]["member_cell_paths"] == [
        [0, 0],
        [0, 1],
        [0, 7],
    ]
    assert units[TABLE9_HEADER_REF]["table_context"]["column_headers"] == ["判定依据"]
    # r1 五级结论列位于 c1/c2/c3/c7/c9
    assert units[TABLE9_CONCLUSION_REF]["table_context"]["member_cell_paths"] == [
        [1, 1],
        [1, 2],
        [1, 3],
        [1, 7],
        [1, 9],
    ]
    empty_r1_c0 = _structure_blob_block(structure_blob, "body.t14.r1.c0.p0")
    assert empty_r1_c0["text"] == ""
    assert "body.t14.r1.c0.p0" not in units[TABLE9_CONCLUSION_REF]["member_source_refs"]
    # r7 注记为 c0 六段（p0-p5）
    assert units[TABLE9_NOTE_REF]["table_context"]["member_cell_paths"] == [[7, 0]]
    assert [m.rsplit(".", 1)[-1] for m in units[TABLE9_NOTE_REF]["member_source_refs"]] == [
        "p0",
        "p1",
        "p2",
        "p3",
        "p4",
        "p5",
    ]


def test_table9_merged_rows_not_reinterpreted_as_plain_grid(
    plan: dict, structure_blob: list[dict]
) -> None:
    """行内含合并单元格的行（r3/r4/r6）不得被当作10列全值行或5列对齐行：缺失
    列位必须在源结构块中确实不存在，且摘录不得臆造缺失符号。"""
    units = _frozen_unit_by_ref(plan)
    blob_refs = {b.get("source_ref") for b in structure_blob}
    # r3 无 c4/c6；r4 无 c8；r5 无 c4/c5/c6/c8；r2 无 c4/c5/c6/c8
    for row, missing_columns in {
        "body.t14.r2": ["c4", "c5", "c6", "c8"],
        "body.t14.r3": ["c4", "c6"],
        "body.t14.r4": ["c8"],
        "body.t14.r5": ["c4", "c5", "c6", "c8"],
    }.items():
        for column in missing_columns:
            assert f"{row}.{column}.p0" not in blob_refs, (
                f"{row}.{column}.p0 不应出现在源结构块（合并单元格范围）"
            )
    # 摘录不得包含臆造的第五列/第六列符号
    for ref in TABLE9_SYMBOL_ROWS:
        assert "| ±" not in units[ref]["excerpt"] or ref == "body.t14.r2"
        assert "| ++" not in units[ref]["excerpt"] or ref == "body.t14.r6"


# ---------------------------------------------------------------------------
# merged-cell misalignment / five-level compression gates
# ---------------------------------------------------------------------------


def test_merged_cell_misalignment_counterexamples_fail_exact_cell_contract(
    config: dict,
) -> None:
    """列位错误由逐格来源契约识别，不依赖有限关键词列表。"""
    counterexamples = {
        "body.t14.r3": [
            # 把行内含合并的七格压缩为五列对齐
            "是否符合已知的作用机制、特性或已知的不良反应 | + | + | + | - | +",
            # 按符号数量臆造缺失符号
            "是否符合已知的作用机制、特性或已知的不良反应 | + | + | + | - | + | - | - | -",
            # 移动列位：把c5的-写到c4位置
            "是否符合已知的作用机制、特性或已知的不良反应 | + | + | + | - | - | + | - | -",
        ],
        "body.t14.r4": [
            # 把-/?全部替换为-（符号互换）
            "去激发结果 | + | + | + | - | + | - | - | -",
            # 臆造一个第五符号
            "去激发结果 | + | + | + | -/? | + | -/? | -/? | -/? | -/?",
        ],
        "body.t14.r5": [
            "再激发结果 | + | -/? | -/? | -/? | -/? | -/?",
            "再激发结果 | + | - | - | - | -",
        ],
        "body.t14.r6": [
            # 把含合并的九格压缩为五列
            "是否可用其他合理的原因解释 | - | - | + | - | -",
            "是否可用其他合理的原因解释 | - | - | + | - | - | - | ++ | + | + | +",
        ],
    }
    for ref, texts in counterexamples.items():
        for text in texts:
            assert text.split(" | ") != CELL_TEXT_BY_REF[ref], (
                f"{ref} 合并单元格错位反例意外满足冻结逐格契约: {text}"
            )

    # 合法来源必须逐格等于冻结结构；语义短语门禁只负责语义篡改。
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert tuple(excerpts[ref].split(" | ")) == CELL_TEXT_BY_REF[ref]
        hits = _deterministic_hits(excerpts[ref])
        assert hits == [], f"误拦截合法行 {ref}: {hits}"


def test_r1_five_level_conclusion_order_verbatim(config: dict, plan: dict) -> None:
    """r1五级结论顺序必须保持'肯定有关、很可能有关、可能有关、可能无关、无关'；
    表头'相关/不相关'不替代第90包统计分组，也不改变五级结论。"""
    excerpts = _owned_excerpt_by_ref(plan)
    assert excerpts[TABLE9_CONCLUSION_REF] == (
        "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关"
    )
    assert not _five_level_order_violation(excerpts[TABLE9_CONCLUSION_REF])

    semantics = config["exception_semantics_by_source_ref"][TABLE9_CONCLUSION_REF]
    assert semantics["base_rule"] == "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关"
    assert "顺序必须保持" in semantics["exception_rule"]
    for level in FIVE_LEVEL_SEQUENCE:
        assert level in semantics["preserve_keywords"], level
    forbidden = semantics["forbidden_inversion"]
    assert "不得把五级缩为三级" in forbidden or "压缩五级列" in forbidden
    # 表头语义不得替代统计分组或五级结论
    header = config["exception_semantics_by_source_ref"][TABLE9_HEADER_REF]
    assert "不替代第90包统计分析前三类相关分组" in header["exception_rule"]
    assert "也不改变五级结论" in header["exception_rule"]


def test_five_level_compression_counterexamples_detected(config: dict) -> None:
    """五级列压缩/增删级别/重排反例必须被确定性门禁拦截。"""
    counterexamples = [
        "肯定有关 | 很可能有关 | 可能有关 | 可能无关",
        "肯定有关 | 很可能有关 | 可能有关",
        "五级结论压缩为三级：肯定有关、很可能有关、可能有关",
        "肯定有关 | 很可能有关 | 可能有关 | 无关",
        "可能有关 | 很可能有关 | 肯定有关 | 可能无关 | 无关",
        "肯定有关 | 可能有关 | 很可能有关 | 可能无关 | 无关",
        "把可能无关与无关合并为一个级别",
    ]
    for text in counterexamples:
        missing = _missing_structural_fragments(text, TABLE9_CONCLUSION_REF)
        hits = _deterministic_hits(text)
        order_broken = _five_level_order_violation(text)
        assert missing or hits or order_broken, (
            f"五级列压缩反例未被门禁拦截: {text}"
        )

    # 合法来源文本不得被误拦截
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    legal = excerpts[TABLE9_CONCLUSION_REF]
    assert _missing_structural_fragments(legal, TABLE9_CONCLUSION_REF) == []
    assert _deterministic_hits(legal) == []
    assert not _five_level_order_violation(legal)


# ---------------------------------------------------------------------------
# symbol literal gates (- / -/? / ± / ++)
# ---------------------------------------------------------------------------


def test_symbol_notes_verbatim_preserved(config: dict, plan: dict) -> None:
    """r7注记六段逐字保留符号原义；配置语义结构必须显式声明不得互换/误判/
    泛化。"""
    excerpts = _owned_excerpt_by_ref(plan)
    note = excerpts[TABLE9_NOTE_REF]
    assert note == EXPECTED_EXCERPT_BY_REF[TABLE9_NOTE_REF]
    for fragment in (
        "“+”表示肯定，或阳性结果；",
        "“-”表示否定，或阴性结果，或暂未获得结果的情况；",
        "“±”表示时间关系不能排除；",
        "“++”表示可用其他“更加”合理的原因解释；",
        "“-/?”表示去激发/再激发结果为阴性，或尚未进行去激发/再激发，或不适用去激发/再激发。",
    ):
        assert fragment in note, fragment

    semantics = config["exception_semantics_by_source_ref"][TABLE9_NOTE_REF]
    assert "“-/?”" in semantics["base_rule"] or "-/?" in semantics["base_rule"]
    assert "解释为确定阴性" in semantics["forbidden_inversion"]
    assert "'-'与'-/?'互换" in semantics["forbidden_inversion"]
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"][TABLE9_NOTE_REF])
    assert "符号原义必须逐字保持" in checks


def test_symbol_placement_keeps_row_semantics(plan: dict) -> None:
    """符号只能出现在其定义维度行：±只在时间关系行（r2），++只在其他合理解释行
    （r6），-/?只用于去激发/再激发（r4/r5）与注记（r7），-只出现在r2/r3/r6。"""
    excerpts = _owned_excerpt_by_ref(plan)
    assert "±" in excerpts["body.t14.r2"]
    assert "++" in excerpts["body.t14.r6"]
    for ref in TABLE9_SYMBOL_ROWS:
        if ref == "body.t14.r2":
            assert "++" not in excerpts[ref]
        if ref == "body.t14.r6":
            assert "±" not in excerpts[ref]
        if ref in ("body.t14.r3", "body.t14.r6"):
            assert "-/?" not in excerpts[ref]
        if ref == "body.t14.r4":
            assert "±" not in excerpts[ref] and "++" not in excerpts[ref]
        if ref == "body.t14.r5":
            assert "±" not in excerpts[ref] and "++" not in excerpts[ref]


def test_symbol_swap_counterexamples_detected(config: dict) -> None:
    """'-'与'-/?'、'±'与'++'互换反例必须被确定性门禁拦截。"""
    counterexamples = [
        # -/?(去激发/再激发专用)被写成-
        "去激发结果 | + | + | + | - | + | - | - | -",
        "再激发结果 | + | - | - | - | -",
        # -被写成-/?
        "是否有合理的时间关系 | + | + | + | ± | -/?",
        "是否可用其他合理的原因解释 | -/? | - | + | - | - | - | ++ | + | +",
        # ±与++互换
        "是否有合理的时间关系 | + | + | + | ++ | -",
        "是否可用其他合理的原因解释 | - | - | + | - | - | - | ± | + | +",
        # 措辞级互换
        "去激发-即阴性，无需区分-/？",
        "-/?等同-，按确定阴性处理。",
        "±与++互换不影响评价。",
    ]
    for text in counterexamples:
        missing = any(
            _missing_structural_fragments(text, ref)
            for ref in ("body.t14.r2", "body.t14.r3", "body.t14.r4", "body.t14.r5", "body.t14.r6")
        )
        hits = _deterministic_hits(text)
        assert missing or hits, f"符号互换反例未被门禁拦截: {text}"

    # 合法来源文本不得被误拦截
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert _deterministic_hits(excerpts[ref]) == [], f"误拦截合法行 {ref}"


def test_unknown_status_negation_counterexamples_detected(config: dict) -> None:
    """'未进行/不适用/暂未获得'被误判为确定阴性的反例必须被确定性门禁拦截。"""
    counterexamples = [
        "尚未进行去激发即视为阴性。",
        "未进行去激发即阴性，按确定阴性处理。",
        "尚未进行再激发即视为阴性。",
        "未进行再激发即阴性。",
        "去激发不适用即阴性。",
        "再激发不适用按阴性处理。",
        "暂未获得结果即阴性。",
        "暂未获得结果按阴性处理，判定为确定阴性。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"未知状态阴性化反例未被门禁拦截: {text}"

    # 合法注记不得误拦截
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    note = excerpts[TABLE9_NOTE_REF]
    assert "尚未进行去激发/再激发" in note
    assert "不适用去激发/再激发" in note
    assert _deterministic_hits(note) == []


def test_symbol_generalization_counterexamples_detected(config: dict) -> None:
    """±/++泛化为强阳性、权重、分值或严重程度的反例必须被确定性门禁拦截。"""
    counterexamples = [
        "±视为强阳性。",
        "±为强阳性，计权重大。",
        "++为强阳性，权重更高。",
        "++视为强度等级，分值2分。",
        "±符号赋权后参与计分。",
        "±计1分，++计2分，按符号计分判定。",
        "++视为严重程度等级。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"符号泛化反例未被门禁拦截: {text}"
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert _deterministic_hits(excerpts[ref]) == [], f"误拦截合法行 {ref}"


# ---------------------------------------------------------------------------
# composite-judgment-matrix nature (no scoring / no majority / no single
# sufficiency / no decision tree)
# ---------------------------------------------------------------------------


def test_five_dimensions_are_comprehensive_judgment_inputs(config: dict) -> None:
    """r2-r6五个评价维度是综合判断矩阵输入；配置语义结构必须显式声明四种禁止
    变形；只读总纲p1089闭合'综合评价'性质。"""
    for ref in TABLE9_DIMENSION_REFS:
        entry = config["exception_semantics_by_source_ref"][ref]
        assert entry["semantic_role"].startswith("symbol_matrix_row_"), ref
        assert (
            "综合判断矩阵输入" in entry["exception_rule"]
            or "维度行" in entry["exception_rule"]
        ), ref
        combined = entry["exception_rule"] + entry["forbidden_inversion"]
        assert ("单项充分" in combined) or ("充分条件" in combined), ref
    checks_blob = "\n".join(
        "\n".join(value)
        for value in config["clinical_qc_checks_by_source_ref"].values()
    )
    assert "不得计分、多数表决或单项充分化" in checks_blob
    # batching 理由与 notes 必须显式声明矩阵性质的四种禁止变形
    batching_reason = config["batching"]["reason"]
    assert "不得自动计分" in batching_reason
    assert "多数表决" in batching_reason
    assert "单项充分条件" in batching_reason
    assert "跨项目通用算法" in batching_reason
    # 只读总纲闭合矩阵性质
    p1089_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1089"])
    assert "综合评价矩阵输入" in p1089_checks
    assert "不得计分、多数表决或单项充分化" in p1089_checks
    # 五级结论不是严重程度/SAE严重性/预期性分级
    r1_semantics = config["exception_semantics_by_source_ref"][TABLE9_CONCLUSION_REF]
    assert "不是严重程度、SAE严重性或预期性分级" in r1_semantics["exception_rule"]
    # 已知性不得与第92包预期性混同（质检声明）
    r3_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t14.r3"])
    assert "不得与第92包预期性评估（body.p1098-p1101）混同" in r3_checks


def test_scoring_counterexamples_detected(config: dict) -> None:
    counterexamples = [
        "时间关系为+计1分，按总分判定相关性。",
        "五个维度按符号计分，得分达到阈值即相关。",
        "按维度加权评分后判定相关性级别。",
        "每个符号计分，固定计分规则加总。",
        "要点打分后按计分规则判定。",
        "符号加权后按评分加总。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"计分化反例未被门禁拦截: {text}"
    for ref in OWNED_REFS:
        assert _deterministic_hits(EXPECTED_EXCERPT_BY_REF[ref]) == [], ref


def test_majority_voting_counterexamples_detected(config: dict) -> None:
    counterexamples = [
        "按符号多数表决，多数为+即判定相关。",
        "五个维度按符号多数决定结论。",
        "符号多数即相关，票数过半即判定。",
        "按多数+判定相关性，多数表决生效。",
        "4个以上为+即视为相关。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"多数表决化反例未被门禁拦截: {text}"
    for ref in OWNED_REFS:
        assert _deterministic_hits(EXPECTED_EXCERPT_BY_REF[ref]) == [], ref


def test_single_sufficient_counterexamples_detected(config: dict) -> None:
    counterexamples = [
        "任一符号即可判定相关，单项充分。",
        "单个维度即判定，任意一项符号即可。",
        "一个维度即可判定相关性。",
        "去激发为+即单项充分条件。",
        "时间关系为-即单独作为否定条件。",
        "任一维度即判定，单项即判定。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"单项充分化反例未被门禁拦截: {text}"
    for ref in OWNED_REFS:
        assert _deterministic_hits(EXPECTED_EXCERPT_BY_REF[ref]) == [], ref


def test_decision_tree_counterexamples_detected(config: dict) -> None:
    counterexamples = [
        "按决策树依次核对五个维度后自动判定相关。",
        "建立机械决策流程，机械判定相关性。",
        "由系统按算法判定相关，无需研究者综合评价。",
        "机械决策：时间相关且已知即自动判定相关。",
        "把每列的组合解释为跨项目通用算法。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"机械决策树化反例未被门禁拦截: {text}"
    for ref in OWNED_REFS:
        assert _deterministic_hits(EXPECTED_EXCERPT_BY_REF[ref]) == [], ref


# ---------------------------------------------------------------------------
# package 90 read-only closure semantics (table number / statistical grouping /
# joint judgment / dimension separation)
# ---------------------------------------------------------------------------


def test_p1095_table_number_inconsistency_preserved(config: dict, plan: dict) -> None:
    """p1095'可参照表7进行'与p1097'表 9'必须同时逐字保留，方案内部不一致标为
    需要核对，不得静默纠正。"""
    p1095 = next(
        u
        for p in plan["packages"]
        if p["package_ordinal"] == PACKAGE_90_ORDINAL
        for u in p["owned_units"]
        if u["source_ref"] == "body.p1095"
    )["excerpt"]
    p1097 = next(
        u
        for p in plan["packages"]
        if p["package_ordinal"] == PACKAGE_90_ORDINAL
        for u in p["owned_units"]
        if u["source_ref"] == "body.p1097"
    )["excerpt"]
    assert "可参照表7进行" in p1095
    assert p1097 == "表 9 不良事件与试验用药品因果关系评价"
    note = config["later_package_boundary"]["note"]
    assert "表7" in note and "表9" in note
    assert "不一致" in note
    assert "只读提示范围" in note
    assert "不静默修正" in note
    semantics = config["exception_semantics_by_source_ref"]
    assert "body.p1095" not in semantics, "只读附加来源不得进入异常语义结构"
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1095"])
    assert "可参照表7进行" in checks
    assert "必须保留并标为需要核对" in checks
    assert "不得静默修正" in checks
    assert "p1097及下表标题'表9'" in checks


def test_table_number_silent_correction_counterexamples_detected() -> None:
    counterexamples = [
        "相关性判定结果分类及判定依据可参照表9进行。",
        "判定依据参照表9进行，不再使用表7。",
        "将表7更正为表9后执行。",
        "方案中的表7即表9，表7实为表9。",
        "表7应为表9，表7系笔误。",
        "判定依据参照表7（即表9）进行。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"表号静默纠正反例未被门禁拦截: {text}"
    # 合法来源文本不得误拦截
    plan = _load_json(PLAN_PATH)
    for p in plan["packages"]:
        for u in p["owned_units"]:
            hits = _deterministic_hits(u["excerpt"])
            assert hits == [], f"误拦截合法来源 {u['source_ref']}: {hits}"


def test_table7_secondary_event_rules_not_absorbed(config: dict) -> None:
    """第82包表7继发事件规则（body.t12.r0-r4）不得进入本包拥有、附加或提示。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    assert set(PKG82_SPAN_REFS).isdisjoint(owned)
    assert set(PKG82_SPAN_REFS).isdisjoint(attached)
    p82_note = config["later_package_boundary"]["semantics_by_package"]["82"]
    assert "表7继发事件规则" in p82_note
    assert "不得吸入本包作为因果评价表" in p82_note


def test_statistical_grouping_keeps_three_classes(config: dict, plan: dict) -> None:
    """统计分析相关分组只含前三类：肯定有关/很可能有关/可能有关；不得扩大到
    可能无关/无关。"""
    p1095 = next(
        u
        for p in plan["packages"]
        if p["package_ordinal"] == PACKAGE_90_ORDINAL
        for u in p["owned_units"]
        if u["source_ref"] == "body.p1095"
    )["excerpt"]
    assert "将“肯定有关”、“很可能有关”、“可能有关”视为与试验用药品相关" in p1095
    assert "可能无关" not in p1095.split("统计")[1]
    semantics = config["exception_semantics_by_source_ref"]
    assert "body.p1095" not in semantics, "只读附加来源不得进入异常语义结构"
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1095"])
    assert "统计分析相关分组只含三类" in checks
    assert "不得扩大到'可能无关'或'无关'" in checks


def test_stat_group_expansion_counterexamples_detected() -> None:
    counterexamples = [
        "统计分析时统计分组包含可能无关。",
        "可能无关也视为与试验用药品相关。",
        "无关也视为相关，扩大为五类。",
        "将可能无关纳入相关组进行统计。",
        "统计时纳入可能无关。",
        "可能无关计入相关组。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"统计分组扩大反例未被门禁拦截: {text}"
    plan = _load_json(PLAN_PATH)
    for p in plan["packages"]:
        for u in p["owned_units"]:
            assert _deterministic_hits(u["excerpt"]) == [], (
                f"误拦截合法来源 {u['source_ref']}"
            )


def test_reverse_inference_counterexamples_detected() -> None:
    counterexamples = [
        "统计相关即个例报告，无需再判。",
        "统计相关即需报告。",
        "相关分组即报告范围。",
        "统计相关即确认因果关系。",
        "按统计分组反推个例判定规则。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"统计分组反推反例未被门禁拦截: {text}"


def test_p1096_joint_judgment_scope_not_upgraded(config: dict, plan: dict) -> None:
    """p1096'报告范围'不得升级为'最终确认相关'；OR语义归第90包，本包不改变。"""
    p1096 = next(
        u
        for p in plan["packages"]
        if p["package_ordinal"] == PACKAGE_90_ORDINAL
        for u in p["owned_units"]
        if u["source_ref"] == "body.p1096"
    )["excerpt"]
    assert "均属报告范围" in p1096
    checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.p1096"])
    assert "共同判断为OR" in checks
    assert "'报告范围'不得升级为'最终确认相关'" in checks
    counterexamples = [
        "任一方判断相关即最终确认相关。",
        "任一方判断相关即确认因果关系成立。",
        "进入报告范围即因果结论成立。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"报告范围升级反例未被门禁拦截: {text}"


def test_dimension_separation_never_conflated(config: dict) -> None:
    """五级结论、严重程度、SAE严重性、预期性、报告时限与因果关系是不同维度，
    不得互相替代；表头'相关/不相关'不得替代统计分组。"""
    r1_semantics = config["exception_semantics_by_source_ref"][TABLE9_CONCLUSION_REF]
    assert "不是严重程度、SAE严重性或预期性分级" in r1_semantics["exception_rule"]
    assert (
        "表8严重程度等级、SAE严重性、预期性或报告时限互相替代"
        in r1_semantics["forbidden_inversion"]
    )
    r3_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t14.r3"])
    assert "已知性判断基于药物已知的作用机制" in r3_checks
    assert "不得与第92包预期性评估（body.p1098-p1101）混同" in r3_checks
    header = config["exception_semantics_by_source_ref"][TABLE9_HEADER_REF]
    assert "不替代第90包统计分析前三类相关分组" in header["exception_rule"]
    note = config["later_package_boundary"]["note"]
    assert "严重程度、SAE严重性、预期性、报告时限与因果关系是不同维度，不得相互替代" in note


def test_dimension_conflation_counterexamples_detected() -> None:
    counterexamples = [
        "五级结论即严重程度等级。",
        "肯定有关即5级。",
        "肯定有关即SAE，按SAE流程上报。",
        "五级即预期性评估。",
        "已知性即预期性。",
        "符合已知机制即预期性。",
        "表头相关即统计相关。",
        "相关/不相关即统计分组。",
        "以严重程度判定因果。",
        "因果相关即SAE。",
    ]
    for text in counterexamples:
        hits = _deterministic_hits(text)
        assert hits, f"跨维度混同反例未被门禁拦截: {text}"
    plan = _load_json(PLAN_PATH)
    for p in plan["packages"]:
        for u in p["owned_units"]:
            assert _deterministic_hits(u["excerpt"]) == [], (
                f"误拦截合法来源 {u['source_ref']}"
            )


# ---------------------------------------------------------------------------
# resolution and zero-candidate hydrated gate
# ---------------------------------------------------------------------------


def test_resolve_units_roles_and_key_excerpts(config: dict) -> None:
    from slice59n_representative_group_control_replay import _resolve_units

    rows = _resolve_units(config)
    by_ref = {row.source_ref: row for row in rows}
    assert {r.source_ref for r in rows if r.role == "owned"} == set(OWNED_REFS)
    assert {r.source_ref for r in rows if r.role == "attached"} == set(
        config["attached_source_refs"]
    )
    for ref in OWNED_REFS:
        assert by_ref[ref].excerpt.strip(), f"{ref} resolved empty"

    # 拥有单元关键语义片段
    assert "判定依据 | 相关 | 不相关" in by_ref[TABLE9_HEADER_REF].excerpt
    assert "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关" in by_ref[
        TABLE9_CONCLUSION_REF
    ].excerpt
    assert "是否有合理的时间关系" in by_ref["body.t14.r2"].excerpt
    assert "±" in by_ref["body.t14.r2"].excerpt
    assert "是否符合已知的作用机制" in by_ref["body.t14.r3"].excerpt
    assert "去激发结果" in by_ref["body.t14.r4"].excerpt
    assert "-/?" in by_ref["body.t14.r4"].excerpt
    assert "再激发结果" in by_ref["body.t14.r5"].excerpt
    assert "是否可用其他合理的原因解释" in by_ref["body.t14.r6"].excerpt
    assert "++" in by_ref["body.t14.r6"].excerpt
    assert "尚未进行去激发/再激发" in by_ref[TABLE9_NOTE_REF].excerpt
    assert "不适用去激发/再激发" in by_ref[TABLE9_NOTE_REF].excerpt

    # 只读闭包关键片段
    for ref, expected in ATTACHED_EXCERPT_BY_REF.items():
        assert by_ref[ref].excerpt == expected, f"{ref} 摘录漂移"

    # 成员格数
    for ref, count in EXPECTED_MEMBER_CELL_COUNT_BY_REF.items():
        assert len(by_ref[ref].source_span_ids) == count, f"{ref} 成员格数漂移"


def test_prepare_evidence_contains_real_closure(config: dict) -> None:
    """生成后的准备证据必须实际包含表9闭包与防吞并边界，不能只在配置元数据里声明。"""
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    assert set(by_ref) == set(OWNED_REFS + ATTACHED_REFS)
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned"
        assert by_ref[ref]["excerpt"].strip(), f"{ref} 未进入准备证据"
    # 相邻包仅第90包p1087-p1097只读进入；其余不得进入
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入准备证据"

    summary = _load_json(PREPARE_DIR / "replay-summary.json")
    assert summary["mode"] == "dry_run_prepare"
    assert summary["owned_count"] == 8
    assert summary["attached_count"] == 11
    assert summary["unit_count"] == 19
    assert summary["claims_complete"] is False

    provenance = _load_json(PREPARE_DIR / "freeze_provenance.json")
    assert provenance["mode"] == "dry_run_prepare"
    assert provenance["frozen_plan_sha256"] == EXPECTED_PLAN_SHA256
    assert provenance["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    assert provenance["claims_complete"] is False


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

    # 越界候选（把表9判定依据矩阵升格为筛选/基线控制候选）必须被拒绝
    for ref in ("body.t14.r2", "body.t14.r4", "body.t14.r7"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "筛选时核对表9因果关系评价符号，未确认者按证据缺口判定入排不通过",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 只读附加来源也只是上下文，任何候选发射都必须拒绝
    for ref in ("body.p1087", "body.p1095", "body.p1097"):
        kwargs["hydrated"] = {
            "candidates": [
                {
                    "frozen_structure_unit_ids": [unit_by_ref[ref]],
                    "title": "只读背景来源不得转移所有权或发布控制点",
                    "semantics": {},
                }
            ],
            "dispositions": [],
        }
        issues = evaluate_hydrated_agent_output(**kwargs)
        assert any(issue.code == "CONTROL_DUPLICATE_RETAINED" for issue in issues), ref

    # 越界引用组外单元必须被拒绝
    kwargs["hydrated"] = {
        "candidates": [
            {
                "frozen_structure_unit_ids": ["su-not-in-group"],
                "title": "越界候选",
                "semantics": {},
            }
        ],
        "dispositions": [],
    }
    issues = evaluate_hydrated_agent_output(**kwargs)
    assert any(issue.code == "SCOPE_CREEP" for issue in issues)


def test_owned_source_excerpts_carry_no_forbidden_upgrade_phrases(
    config: dict, plan: dict
) -> None:
    """冻结来源本身不得包含升格措辞；来源干净是重放门禁的前提。"""
    excerpts = dict(_owned_excerpt_by_ref(plan))
    for ref, expected in ATTACHED_EXCERPT_BY_REF.items():
        excerpts[ref] = expected
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref in OWNED_REFS + ATTACHED_REFS:
        hits = _forbidden_marker_hits(excerpts[ref], markers_by_ref[ref])
        assert hits == [], f"{ref} 来源已含禁止升格措辞: {hits}"


def test_forbidden_markers_detect_upgrade_counterexamples(config: dict) -> None:
    """确定性门禁必须拒绝把表9矩阵改写为筛选/基线门槛的反例。"""
    counterexamples_by_ref = {
        "body.t14.r0": [
            "筛选时核对表9三列表头，未确认者不得入组",
        ],
        "body.t14.r1": [
            "筛选时核对五级结论掌握情况，未确认者证据缺口不得入组",
        ],
        "body.t14.r2": [
            "基线时核对时间关系符号，未确认者入排不通过",
        ],
        "body.t14.r3": [
            "筛选时核对已知性符号，未确认者排除标准",
        ],
        "body.t14.r4": [
            "基线时核对去激发结果，未确认者不得入组",
        ],
        "body.t14.r5": [
            "筛选时核对再激发结果，未确认者入组前必查",
        ],
        "body.t14.r6": [
            "基线时核对其他合理解释符号，未确认者不得入组",
        ],
        "body.t14.r7": [
            "筛选时核对符号注记掌握情况，未确认者证据不足不得入组",
        ],
        "body.p1095": [
            "按统计分组核对筛选资格，未确认者入排不通过",
        ],
        "body.p1097": [
            "表9入口标题作为筛选必做核对项",
        ],
    }
    markers_by_ref = config["candidate_forbidden_markers_by_source_ref"]
    for ref, counterexamples in counterexamples_by_ref.items():
        for text in counterexamples:
            assert _forbidden_marker_hits(text, markers_by_ref[ref]), (
                f"门禁未拦截 {ref} 升格反例: {text}"
            )


# ---------------------------------------------------------------------------
# anti-absorption: package 78/79/82/87/88/89/92/93
# ---------------------------------------------------------------------------


def test_package90_attached_refs_stay_read_only(config: dict) -> None:
    """第90包p1087-p1097全部以只读附加角色进入，所有权与候选发射权不转移。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    assert set(PKG90_ATTACHED_REFS) == attached
    assert set(PKG90_ATTACHED_REFS).isdisjoint(owned)
    note = config["later_package_boundary"]["note"]
    assert "所有权与候选发射权仍归第90包" in note
    assert "本包不重新拥有段落" in note
    assert "不转移所有权" in note


def test_package92_93_not_absorbed(config: dict) -> None:
    """第92包预期性评估与第93包应报告事件类型与随访流程不得进入本包。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    assert set(PKG92_SPAN_REFS).isdisjoint(owned)
    assert set(PKG92_SPAN_REFS).isdisjoint(attached)
    assert set(PKG93_SPAN_REFS).isdisjoint(owned)
    assert set(PKG93_SPAN_REFS).isdisjoint(attached)
    note = config["later_package_boundary"]["note"]
    assert "第92包预期性评估（body.p1098-p1101）与第93包应报告事件类型与随访流程（body.p1102-p1112）不提前吞并" in note
    r3_checks = "\n".join(config["clinical_qc_checks_by_source_ref"]["body.t14.r3"])
    assert "不得与第92包预期性评估（body.p1098-p1101）混同" in r3_checks


def test_other_neighbors_not_absorbed(config: dict) -> None:
    """第78/79/82/87/88/89包仅保留所有权元数据，不进入本包拥有或附加。"""
    owned = set(config["owned_source_refs"])
    attached = set(config["attached_source_refs"])
    for span in (
        PKG78_SPAN_REFS,
        PKG79_SPAN_REFS,
        PKG82_SPAN_REFS,
        PKG87_SPAN_REFS,
        PKG88_SPAN_REFS,
        PKG89_SPAN_REFS,
    ):
        assert set(span).isdisjoint(owned)
        assert set(span).isdisjoint(attached)
    note = config["later_package_boundary"]["note"]
    assert "仅保留所有权元数据" in note
    assert "不进入本包语义" in note
    assert "前接第89包表8严重程度分级定义（body.t13.r0-r5）" in note
    assert "第88包AE严重程度评估与CTCAE 6.0回退方法（body.p1084-p1086）" in note
    assert "第78包SAE定义与严重性标准（body.p995-p1006）" in note
    assert "第87包死亡、药物过量与给药错误记录规则（body.p1074-p1083）" in note
    assert "不得相互替代" in note


def test_later_package_boundary_ownership_against_frozen_plan(
    config: dict, plan: dict
) -> None:
    boundary = config["later_package_boundary"]
    owners: dict[str, list[int]] = {}
    for p in plan["packages"]:
        for u in p["owned_units"]:
            owners.setdefault(u["source_ref"], []).append(p["package_ordinal"])
    for ref, expected_ordinal in boundary["expected_owners_by_span"].items():
        assert owners.get(ref) == [expected_ordinal], (
            f"{ref} 所有权漂移：期望第{expected_ordinal}包，实际{owners.get(ref)}"
        )
    # 本包拥有单元只允许 t14 八行
    for ref in boundary["expected_owners_by_span"]:
        if ref in OWNED_REFS:
            assert boundary["expected_owners_by_span"][ref] == PACKAGE_91_ORDINAL
    # 附加来源所有权全部归第90包
    for ref in PKG90_ATTACHED_REFS:
        assert boundary["expected_owners_by_span"][ref] == PACKAGE_90_ORDINAL


def test_later_boundary_note_documents_no_absorption(config: dict) -> None:
    boundary = config["later_package_boundary"]
    assert boundary["read_only"] is True
    note = boundary["note"]
    for fragment in (
        "第78包",
        "第79包",
        "第87包",
        "第88包",
        "第89包",
        "第90包",
        "第91包",
        "第92包",
        "第93包",
        "吞并",
        "所有权",
        "body.t14.r0-r7",
        "body.p1087-p1097",
        "body.p1098-p1101",
        "body.p1102-p1112",
        "表7",
        "表9",
        "不提前吞并",
        "不得相互替代",
        "不同维度",
    ):
        assert fragment in note, f"边界注记缺少防吞并/防混同声明: {fragment}"


def test_prompt_excludes_neighbor_content() -> None:
    """第78/79/82/87/88/89/92/93包内容不得进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    # 第82包表7继发事件规则 / 第88包严重程度 / 第89包表8 / 第87包记录规则
    for leaked in (
        "继发事件",
        "严重程度分级",
        "CTCAE",
        "药物过量",
        "给药错误",
        "猝死",
    ):
        assert leaked not in prompt_text, f"相邻包内容泄漏进第91包提示: {leaked}"
    # 第92包预期性 / 第93包应报告事件流程
    for leaked in (
        "预期性评估",
        "预期性",
        "研究者手册",
        "应报告事件",
        "随访流程",
    ):
        assert leaked not in prompt_text, f"后续包内容泄漏进第91包提示: {leaked}"
    # 相邻包来源不得进入提示
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in (
        PKG78_SPAN_REFS
        + PKG79_SPAN_REFS
        + PKG82_SPAN_REFS
        + PKG87_SPAN_REFS
        + PKG88_SPAN_REFS
        + PKG89_SPAN_REFS
        + PKG92_SPAN_REFS
        + PKG93_SPAN_REFS
    ):
        assert ref not in by_ref, f"{ref} 不得进入第91包准备证据"


# ---------------------------------------------------------------------------
# prompt surface checks
# ---------------------------------------------------------------------------


def test_owned_sources_verbatim_in_prompt(config: dict) -> None:
    """第91包全部拥有来源必须逐字进入提示。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    excerpts = _owned_excerpt_by_ref(_load_json(PLAN_PATH))
    for ref in OWNED_REFS:
        assert excerpts[ref] in prompt_text, f"{ref} 全文未进入提示"


def test_prompt_contains_table9_closure_and_attached_sources() -> None:
    """提示必须包含表9表头/五级结论/五个符号维度/注记与全部只读附加来源，
    且保持只读附加角色。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    assert "判定依据 | 相关 | 不相关" in prompt_text
    assert "肯定有关 | 很可能有关 | 可能有关 | 可能无关 | 无关" in prompt_text
    assert "是否有合理的时间关系 | + | + | + | ± | -" in prompt_text
    assert "去激发结果 | + | + | + | -/? | + | -/? | -/? | -/?" in prompt_text
    assert "是否可用其他合理的原因解释 | - | - | + | - | - | - | ++ | + | +" in prompt_text
    assert "“-/?”表示去激发/再激发结果为阴性，或尚未进行去激发/再激发，或不适用去激发/再激发。" in prompt_text
    for ref, expected in ATTACHED_EXCERPT_BY_REF.items():
        assert expected in prompt_text, f"{ref} 未进入提示"
    rows = _load_json(PREPARE_DIR / "source_rows.json")
    by_ref = {row["source_ref"]: row for row in rows}
    for ref in OWNED_REFS:
        assert by_ref[ref]["role"] == "owned", ref
    for ref in ATTACHED_REFS:
        assert by_ref[ref]["role"] == "attached", ref


def test_prompt_keeps_symbol_literals_and_matrix_nature() -> None:
    """提示含符号原义与五级结论，且无计分/表决/单项充分/决策树/符号互换/未知
    状态阴性化/跨维度混同措辞。"""
    prompt_text = (PREPARE_DIR / "execution" / "prompt.txt").read_text(encoding="utf-8")
    hits = _deterministic_hits(prompt_text)
    assert hits == [], f"提示含被禁止的变形措辞: {hits}"


# ---------------------------------------------------------------------------
# official matrix and procedure catalog
# ---------------------------------------------------------------------------


def test_matrix_has_no_rows_anchored_in_package91(matrix: dict, plan: dict) -> None:
    pkg91 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_91_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg91["owned_units"]}
    for row in matrix["rows"]:
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第91包拥有来源为锚点"
            )


def test_matrix_has_no_ae_teae_sae_rows(matrix: dict) -> None:
    for row in matrix["rows"]:
        text = " ".join(
            str(row.get(key) or "")
            for key in (
                "title_zh",
                "required_action_zh",
                "attainment_criteria_zh",
                "minimum_evidence",
            )
        )
        assert "不良事件" not in text, row["matrix_row_id"]
        assert "TEAE" not in text and "SAE" not in text, row["matrix_row_id"]
        assert "发生率" not in text, row["matrix_row_id"]
        for anchor in row.get("source_anchors") or []:
            ref = str(anchor.get("source_ref") or "")
            if ref.startswith(("body.t12", "body.t13", "body.t14")):
                raise AssertionError(f"{row['matrix_row_id']} 锚点 {ref} 落在表7/表8/因果判定表内")
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"{row['matrix_row_id']} 锚点 {ref} 落在定义章节或后续包边界内"
                )


def test_no_official_rule_anchors_package91_owned_spans(
    matrix: dict, plan: dict
) -> None:
    pkg91 = next(
        p for p in plan["packages"] if p["package_ordinal"] == PACKAGE_91_ORDINAL
    )
    owned_refs = {u["source_ref"] for u in pkg91["owned_units"]}
    for row in matrix["rows"]:
        if not (row.get("official_parent_code") or row.get("official_child_code")):
            continue
        for anchor in row.get("source_anchors") or []:
            assert anchor.get("source_ref") not in owned_refs, (
                f"{row['matrix_row_id']} 不得以第91包拥有来源为锚点"
            )


def _catalog_nodes(catalog: dict, label: str) -> list[dict]:
    return [item for item in catalog["items"] if item["label"] == label]


def test_procedure_catalog_has_no_ae_or_teae_node(procedure_catalog: dict) -> None:
    assert procedure_catalog["study_phase"] == "phase_ii"
    for item in procedure_catalog["items"]:
        label = str(item["label"])
        assert "不良事件" not in label
        assert label not in {"AE", "TEAE", "SAE", "发生率"}
    assert _catalog_nodes(procedure_catalog, "不良事件") == []
    assert _catalog_nodes(procedure_catalog, "TEAE") == []
    assert _catalog_nodes(procedure_catalog, "SAE") == []


def test_no_procedure_node_sourced_from_package91_or_definition_spans(
    procedure_catalog: dict,
) -> None:
    for item in procedure_catalog["items"]:
        for span in item.get("source_span_ids") or []:
            ref = str(span).rsplit("::", 1)[-1]
            if ref.startswith(("body.t12", "body.t13", "body.t14")):
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以表7/表8/因果判定表来源 {ref} 为来源"
                )
            ordinal = ref.removeprefix("body.p")
            if ordinal.isdigit() and 985 <= int(ordinal) <= 1100:
                raise AssertionError(
                    f"流程节点 {item['item_id']} 不得以定义章节来源 {ref} 为来源"
                )


# ---------------------------------------------------------------------------
# known targets build empty / workflow stages
# ---------------------------------------------------------------------------


def test_known_targets_build_empty(config: dict) -> None:
    from slice59n_representative_group_control_replay import _known_targets

    official, procedures = _known_targets(config)
    assert official == []
    assert procedures == []
    assert config["known_targets"]["official_rules"] == []
    assert config["known_targets"]["required_procedures"] == []


def test_workflow_stages_keep_d1_pre_dose_distinct(config: dict) -> None:
    from slice59n_representative_group_control_replay import _workflow

    stages = {s.workflow_stage_id: s for s in _workflow(config)}
    assert set(stages) == {"flow-screening", "flow-baseline", "flow-d1-pre-dose"}
    assert stages["flow-screening"].review_stage.value == "screening"
    assert stages["flow-baseline"].review_stage.value == "baseline"
    assert stages["flow-d1-pre-dose"].review_stage.value == "baseline"
    assert (
        stages["flow-d1-pre-dose"].visit_instance == "D1给药前"
        and stages["flow-d1-pre-dose"].visit_instance
        != stages["flow-baseline"].visit_instance
    )


# ---------------------------------------------------------------------------
# fingerprints and checklist freeze
# ---------------------------------------------------------------------------


def test_source_fingerprints_unchanged() -> None:
    assert _sha256_file(PLAN_PATH) == EXPECTED_PLAN_SHA256
    assert _sha256_file(STRUCTURE_BLOB_PATH) == EXPECTED_STRUCTURE_SHA256
    coverage = _load_json(COVERAGE_PATH)
    assert coverage["protocol_document_sha256"] == EXPECTED_DOCX_SHA256
    catalog = _load_json(CATALOG_DIR / "required_procedures.json")
    assert catalog["catalog_sha256"] == EXPECTED_CATALOG_SHA256


def test_parent_checklist_freeze_present() -> None:
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert PLAN_ID in text
    assert PACKAGE_90_ID in text
    assert PACKAGE_91_ID in text
    assert PACKAGE_92_ID in text
    assert EXPECTED_DOCX_SHA256 in text
    assert EXPECTED_PLAN_SHA256 in text
    assert EXPECTED_STRUCTURE_SHA256 in text
    assert "判定依据" in text
    assert "肯定有关" in text and "很可能有关" in text and "可能有关" in text
    assert "可能无关" in text and "无关" in text
    assert "-/?" in text
    assert "±" in text and "++" in text
    assert "body.t14" in text
    assert "body.p1087" in text and "body.p1097" in text
    assert "可参照表7进行" in text
    assert "第78包" in text and "第79包" in text and "第82包" in text
    assert "第87包" in text and "第88包" in text and "第89包" in text
    assert "第90包" in text and "第91包" in text and "第92包" in text
    assert "第93包" in text
    assert "claims_complete=false" in text
