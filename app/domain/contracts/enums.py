from enum import Enum


class StableEnum(str, Enum):
    pass


class StudyPhase(StableEnum):
    PHASE_II = "phase_ii"
    PHASE_III = "phase_iii"
    SEAMLESS_II_III = "seamless_phase_ii_iii"
    OTHER = "other"


class ReviewStage(StableEnum):
    PRE_SCREENING = "pre_screening"
    SCREENING = "screening"
    RUN_IN = "run_in"
    BASELINE = "baseline"


class RuleKind(StableEnum):
    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"
    REQUIRED_PROCEDURE = "required_procedure"


class LogicalOperator(StableEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"


class Comparator(StableEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"


class AnchorType(StableEnum):
    ICF_DATE = "icf_date"
    SCREENING_DATE = "screening_date"
    BASELINE_DATE = "baseline_date"
    RANDOMIZATION_DATE = "randomization_date"
    FIRST_DOSE_DATE = "first_dose_date"
    STUDY_DRUG_ADMINISTRATION_DATE = "study_drug_administration_date"
    LAST_DOSE_DATE = "last_dose_date"
    STUDY_COMPLETION_DATE = "study_completion_date"
    EVENT_DATE = "event_date"
    # 项目无关锚点：当前 ReviewRun 所绑定审核节点的日期。它不是筛选/基线
    # 的默认值；只有在来源明确的解释材料把未命名回溯锚点解析到“当前审核
    # 节点日期”后才允许出现在正式条件中，且不得用作 on 同日约束（审核
    # 阶段本身由资料要求的 due_stage 表达）。求值时由调用方按 episode 向
    # ``EvaluationContext.anchor_dates`` 注入当前审核节点日期；筛选与基线
    # 各自注入各自节点日期并独立评判，结果互不覆盖。锚点未注入时求值器
    # 保持 ``date_or_anchor_missing`` 的失败关闭行为。
    REVIEW_NODE_DATE = "review_node_date"


class ProtocolPeriod(StableEnum):
    TREATMENT_PERIOD = "treatment_period"
    STUDY_PERIOD = "study_period"


class TimeDirection(StableEnum):
    BEFORE = "before"
    AFTER = "after"
    ON = "on"


class CombinedWindowSelection(StableEnum):
    """固定日历窗与半衰期窗并存时的择窗语义。

    ``longer_of_calendar_and_half_life`` 表示“固定窗口或 N 个半衰期，以时间较长者为准”。
    这是同一洗脱/禁限窗的两种度量取较长者，不是把独立分支改写成 ``LogicalOperator.ANY``，
    也不得从原文“或”字自行推断；合同字段必须显式给出。
    """

    LONGER_OF_CALENDAR_AND_HALF_LIFE = "longer_of_calendar_and_half_life"


class DatePrecision(StableEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


class LocatorPrecision(StableEnum):
    BBOX = "bbox"
    TEXT_RANGE = "text_range"
    PAGE_EXCERPT = "page_excerpt"
    PAGE_ONLY = "page_only"


class ExpectationStatus(StableEnum):
    OBSERVED = "observed"
    OBSERVED_WEAK = "observed_weak"
    REFERENCED_MISSING = "referenced_missing"
    ABSENT = "absent"
    NOT_DUE = "not_due"
    #: 补充控制专属：适用条件与来源有效期评估尚未接入，按待判断处置，
    #: 不作为无条件缺失，也不阻断其余资料期望。
    PENDING_CONTROL_APPLICABILITY = "pending_control_applicability"


class ComponentDecision(StableEnum):
    INCLUSION_MET = "inclusion_met"
    INCLUSION_NOT_MET = "inclusion_not_met"
    EXCLUSION_NOT_TRIGGERED = "exclusion_not_triggered"
    EXCLUSION_TRIGGERED = "exclusion_triggered"
    INDETERMINATE = "indeterminate"
    PROFESSIONAL_JUDGMENT = "professional_judgment"
    CONFLICT = "conflict"
    NOT_DUE = "not_due"
    NOT_APPLICABLE = "not_applicable"
    REQUIREMENT_MET = "requirement_met"
    REQUIREMENT_NOT_MET = "requirement_not_met"


class GapType(StableEnum):
    OBSERVATION_UNVERIFIED = "observation_unverified"
    RECORD_INCOMPLETE = "record_incomplete"
    DESCRIPTION_INSUFFICIENT = "description_insufficient"
    HISTORICAL_SOURCE_UNAVAILABLE = "historical_source_unavailable"
    REFERENCED_FILE_MISSING = "referenced_file_missing"
    REQUIRED_PROCEDURE_NOT_DONE = "required_procedure_not_done"
    RESULT_FIELDS_MISSING = "result_fields_missing"
    DATE_OR_ANCHOR_MISSING = "date_or_anchor_missing"
    PROFESSIONAL_JUDGMENT = "professional_judgment"
    SOURCE_CONFLICT = "source_conflict"
    OCR_OR_PARSE_RISK = "ocr_or_parse_risk"
    INTERPRETATION_CONFLICT = "interpretation_conflict"
    FUTURE_STAGE_NOT_DUE = "future_stage_not_due"
    PROVENANCE_FOLLOWUP = "provenance_followup"
    CONTROL_APPLICABILITY_PENDING = "control_applicability_pending"


class BlockingLevel(StableEnum):
    NONE = "none"
    ATTENTION = "attention"
    BLOCKING = "blocking"


class EpisodeMainStatus(StableEnum):
    CLEAR_BARRIER = "clear_barrier"
    CURRENT_GAP = "current_gap"
    CONFLICT = "conflict"
    PROFESSIONAL_JUDGMENT = "professional_judgment"
    FUTURE_ATTENTION = "future_attention"
    NO_CLEAR_BARRIER = "no_clear_barrier"


class ActionTarget(StableEnum):
    INVESTIGATOR = "investigator"
    CRC = "crc"
    CRA = "cra"
    SPONSOR_MEDICAL_OR_PROJECT = "sponsor_medical_or_project"


class ActionState(StableEnum):
    OPEN = "open"
    CLOSED_SYSTEM = "closed_system"
    CLOSED_MANUAL = "closed_manual"
    REOPENED = "reopened"
    SUPERSEDED = "superseded"


class UploadMode(StableEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class FactPolarity(StableEnum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"
    UNKNOWN = "unknown"


class ProfileLane(StableEnum):
    STUDY_MILESTONE = "study_milestone"
    DEMOGRAPHICS = "demographics"
    TARGET_DISEASE = "target_disease"
    SYMPTOMS_SIGNS = "symptoms_signs"
    MEDICAL_HISTORY = "medical_history"
    MEDICATION = "medication"
    NON_DRUG_TREATMENT = "non_drug_treatment"
    TEST_EXAM_SCORE = "test_exam_score"
    ALLERGY_INFECTION_IMMUNE = "allergy_infection_immune"
    REPRODUCTIVE = "reproductive"
    SOCIAL_ENVIRONMENTAL = "social_environmental"
    SPECIAL_HISTORY = "special_history"
    EVIDENCE_QUALITY = "evidence_quality"


class JobEventType(StableEnum):
    CREATED = "created"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    WAITING_USER = "waiting_user"
    USER_RESUMED = "user_resumed"
    USER_UPDATED = "user_updated"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    PAGE_PROGRESS = "page_progress"
    SEMANTIC_BATCH_PROGRESS = "semantic_batch_progress"


class AgentNode(StableEnum):
    PROTOCOL_DECONSTRUCTOR = "protocol_deconstructor"
    EVIDENCE_NORMALIZER = "evidence_normalizer"
    ELIGIBILITY_ASSESSOR = "eligibility_assessor"
    SAFETY_PROVENANCE_CRITIC = "safety_provenance_critic"


class AgentOutputKind(StableEnum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    CRITIC_RUN = "critic_run"


class AgentWriteScope(StableEnum):
    PROTOCOL_DRAFT = "protocol_draft"
    EVIDENCE_CANDIDATE = "evidence_candidate"
    ASSESSMENT_CANDIDATE = "assessment_candidate"
    CRITIC_RUN = "critic_run"


class CriticAction(StableEnum):
    VETO = "veto"
    DOWNRANK = "downrank"
    OPEN_ACTION = "open_action"
    NONE = "none"


class TruthValue(StableEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class RunOutcome(StableEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STOPPED = "stopped"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class RuntimeErrorCode(StableEnum):
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    SCOPE_MISMATCH = "scope_mismatch"
    UPSTREAM_GATE_NOT_ACCEPTED = "upstream_gate_not_accepted"
    PAYLOAD_HASH_MISMATCH = "payload_hash_mismatch"
    PROTOCOL_INTEGRITY_FAILED = "protocol_integrity_failed"
    CANDIDATE_NOT_BOUND = "candidate_not_bound"
    SYNTHETIC_REJECTION = "synthetic_rejection"


class GateOutcome(StableEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ErrorCode(StableEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    SCOPE_MISMATCH = "scope_mismatch"
    STALE_REVISION = "stale_revision"
    CONTRACT_VALIDATION_FAILED = "contract_validation_failed"
    PROTOCOL_INTEGRITY_FAILED = "protocol_integrity_failed"
    PUBLICATION_INTEGRITY_FAILED = "publication_integrity_failed"
    CONFLICT = "conflict"
    JOB_FAILED = "job_failed"


# ---------------------------------------------------------------------------
# 方案文档提取（Phase 3 切片 1）：渲染、提取、来源定位与冻结目录
# ---------------------------------------------------------------------------


class RenderStatus(StableEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class ExtractionStatus(StableEnum):
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class AlignmentStatus(StableEnum):
    """结构通道与渲染通道的对齐状态；未对齐时仍保留结构通道定位。"""

    ALIGNED = "aligned"
    DEGRADED = "degraded"
    UNALIGNED = "unaligned"


class DocumentPart(StableEnum):
    """方案文档部件（OOXML document part 语义）。"""

    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    TEXTBOX = "textbox"
    OTHER = "other"


class SourceLocatorPrecision(StableEnum):
    """方案来源定位精度；block 为结构通道兜底，其余依赖渲染通道。"""

    BLOCK = "block"
    TEXT_RANGE = "text_range"
    PAGE_EXCERPT = "page_excerpt"
    PAGE_ONLY = "page_only"
    BBOX = "bbox"


class CatalogKind(StableEnum):
    """Agent 调用前冻结的两份目录类型。"""

    OFFICIAL_PARENT_RULES = "official_parent_rules"
    REQUIRED_PROCEDURES = "required_procedures"


class CatalogItemKind(StableEnum):
    PARENT_RULE = "parent_rule"
    REQUIRED_PROCEDURE = "required_procedure"


# ---------------------------------------------------------------------------
# 方案元信息、期别适用范围与解释材料（Phase 3 切片 2）
# ---------------------------------------------------------------------------


class ProtocolMetadataField(StableEnum):
    """方案身份候选的字段类别。

    模板字段与正式方案字段必须在结构上分开；不能因为同一页同时出现两个
    ``版本号`` 就采信文档中排在前面的值。
    """

    PROJECT_NAME = "project_name"
    PROJECT_CODE = "project_code"
    DOCUMENT_TITLE = "document_title"
    PROTOCOL_CODE = "protocol_code"
    PROTOCOL_VERSION = "protocol_version"
    PROTOCOL_DATE = "protocol_date"
    STUDY_PHASE = "study_phase"
    TEMPLATE_CODE = "template_code"
    TEMPLATE_VERSION = "template_version"


class MetadataSourceKind(StableEnum):
    """元信息来源位置；顺序由确定性解析器映射到 priority_rank。"""

    HEADER_FOOTER = "header_footer"
    FIRST_PAGE = "first_page"
    SIGNATURE_PAGE = "signature_page"
    BODY = "body"
    FILENAME = "filename"
    USER_CONFIRMATION = "user_confirmation"


class IdentityAuthority(StableEnum):
    """身份字段权威级别，与规则正文页级定位精度独立。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MetadataResolutionStatus(StableEnum):
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class PhaseDesignType(StableEnum):
    INDEPENDENT = "independent"
    SHARED_CONTENT = "shared_content"
    SEAMLESS_CANDIDATE = "seamless_candidate"
    UNKNOWN = "unknown"


class ApplicabilityGranularity(StableEnum):
    PARAGRAPH = "paragraph"
    TABLE_ROW = "table_row"
    VISIT_COLUMN = "visit_column"


class PhaseScope(StableEnum):
    PHASE_II = "phase_ii"
    PHASE_III = "phase_iii"
    SHARED = "shared"
    SEAMLESS_CANDIDATE = "seamless_candidate"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class InterpretationSourceType(StableEnum):
    AMENDMENT = "amendment"
    QA = "qa"
    CLARIFICATION_LETTER = "clarification_letter"
    EMAIL = "email"
    MEDICAL_INTERPRETATION = "medical_interpretation"


class InterpretationAuthority(StableEnum):
    FORMAL_REQUIREMENT = "formal_requirement"
    CLARIFICATION_ONLY = "clarification_only"


class InterpretationConflictStatus(StableEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED_BY_CURRENT_AMENDMENT = "resolved_by_current_amendment"


class InterpretationChangeField(StableEnum):
    CLARIFICATION_NOTE = "clarification_note"
    OFFICIAL_CODE = "official_code"
    THRESHOLD = "threshold"
    BOOLEAN_LOGIC = "boolean_logic"
    WORKFLOW_NODE = "workflow_node"
    DUE_STAGE = "due_stage"
    FORMAL_REQUIREMENT = "formal_requirement"


class AnchorResolutionMode(StableEnum):
    """解释材料解析未命名回溯锚点的受限模式。

    初始只有一个项目无关成员：把未命名回溯锚点解析为“当前审核节点日期”。
    解析只能提供锚点身份；窗口量、方向、阈值、布尔逻辑和官方编号仍必须
    逐字来自方案原文，不得由解释载荷携带或改写。目标审核节点集合是逐条款
    数据（由解析声明并经确定性门禁核验），不是代码常量。
    """

    CURRENT_REVIEW_NODE_DATE = "current_review_node_date"


# ---------------------------------------------------------------------------
# Phase 4 证据页、OCR 与诚实定位（Slice 4.0 冻结）
# ---------------------------------------------------------------------------


class ExtractionRoute(StableEnum):
    """页面识别来源路线；决定原始文本从哪一层取得，不决定临床语义。"""
    SOURCE_TEXT = "source_text"
    NATIVE_PDF_TEXT = "native_pdf_text"
    RENDERED_PDF_TEXT = "rendered_pdf_text"
    VISION_OCR = "vision_ocr"


class CoordinateSpace(StableEnum):
    """证据定位坐标系。PDF points 原点在左下、y 向上；渲染页图像素原点在左上、y 向下。"""
    PDF_POINTS = "pdf_points"
    PAGE_IMAGE_PIXELS = "page_image_pixels"


class PageArtifactStatus(StableEnum):
    """页产物状态；失败页必须显式说明原因，不得伪装为成功。"""
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class OCRPageStatus(StableEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OcrRiskKind(StableEnum):
    """结构化 OCR 风险类别（Slice 4.0 冻结种子集）。"""
    NEGATION_POLARITY = "negation_polarity"
    NUMERIC_VALUE = "numeric_value"
    DECIMAL_POINT = "decimal_point"
    UNIT = "unit"
    DATE = "date"
    REPEATED_TEXT = "repeated_text"
    OUTPUT_REPETITION = "output_repetition"
    LOW_CONFIDENCE = "low_confidence"


class OcrRiskLevel(StableEnum):
    """OCR 风险阻断等级矩阵。BLOCKING 未核对会阻止证据处理修订激活；INFORMATIONAL 不阻断。"""
    BLOCKING = "blocking"
    INFORMATIONAL = "informational"


class DisambiguationOutcome(StableEnum):
    """重复文本消歧结果；只有 UNIQUE_MATCH 允许形成区域定位。"""
    UNIQUE_MATCH = "unique_match"
    REPEATED_TEXT_DEGRADED = "repeated_text_degraded"
    NOT_FOUND = "not_found"


# ---------------------------------------------------------------------------
# Phase 4 证据快照与资料版本（Slice 4.1 冻结）
# ---------------------------------------------------------------------------


class SnapshotStatus(StableEnum):
    """证据快照候选生命周期状态（设计书 §6 状态表）。

    候选状态：staged -> processing -> (needs_attention | retryable_failure |
    terminal_failure | ready)；ready 经发布门禁后通过 activation 事件进入 active。
    终态：active、revision_conflict、cancelled、terminal_failure，禁止再发生候选跳转。
    """

    STAGED = "staged"
    PROCESSING = "processing"
    NEEDS_ATTENTION = "needs_attention"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    READY = "ready"
    ACTIVE = "active"
    REVISION_CONFLICT = "revision_conflict"
    CANCELLED = "cancelled"


class SnapshotMemberOrigin(StableEnum):
    """快照成员来源：从有效前序快照继承、本次新增，或显式替代旧版本后的新版本。

    完整资料快照的成员只能来自本次选择（added），不得继承前序；补充资料快照的
    成员可以是继承前序仍有效（inherited）、本次新增（added）或作为原资料新版本
    显式替代（replaced）后的活动版本。
    """

    INHERITED = "inherited"
    ADDED = "added"
    REPLACED = "replaced"


class UploadPreviewStatus(StableEnum):
    """上传预览候选生命周期（Slice 4.2 冻结）。

    staged -> committed（用户确认）；取消走 staged -> cancel_pending -> cancelled：
    ``cancel_pending`` 表示用户已取消且取消意图已追加记录，但预览自有暂存清理尚未
    验证完成（清理失败时保持该状态以便重试），不允许确认使用残缺预览；清理核实
    完成后进入终态 cancelled。committed/cancelled 为终态，不得再回退或二次提交。
    """

    STAGED = "staged"
    COMMITTED = "committed"
    CANCELLED = "cancelled"
    CANCEL_PENDING = "cancel_pending"


class UploadItemStatus(StableEnum):
    """逐文件差异分类（Slice 4.2 冻结）。

    - added                  本次新增：内容与文件名均不在有效基准快照中，将首次处理；
    - duplicate              内容重复：SHA-256 与有效基准快照中某活动成员相同，
                             存储层去重复用，无需重复保存原始二进制或重复 OCR；
    - conflict               名称相同但内容不同：必须显式选择“作为新版本”或
                             “并列保留”，不允许默认覆盖；
    - unsupported            格式不受支持（如压缩包），明确提示，不静默展开；
    - unreadable             文件无法读取/格式无法识别/内容为空；
    - full_snapshot_omission 完整资料模式下，上一有效快照存在、本次未选择导致遗漏；
    - expected_reprocessing  预计需要重新识别：完整资料模式重新纳入与基准内容相同
                             的文件，或重复提交后仍需再次处理的成员。
    """

    ADDED = "added"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported"
    UNREADABLE = "unreadable"
    FULL_SNAPSHOT_OMISSION = "full_snapshot_omission"
    EXPECTED_REPROCESSING = "expected_reprocessing"


class UploadConflictResolution(StableEnum):
    """同名异内容文件的显式处置：不允许默认覆盖。

    new_version   作为原资料的新版本：同逻辑资料递增版本号并显式替代前序链头；
    keep_parallel 作为另一份资料并列保留：新逻辑资料，原资料保持现状。
    """

    NEW_VERSION = "new_version"
    KEEP_PARALLEL = "keep_parallel"


# ---------------------------------------------------------------------------
# Phase 4 OCR 持久化与基础证据处理修订（Slice 4.3）
# ---------------------------------------------------------------------------


class ProcessingRevisionStatus(StableEnum):
    """证据处理修订状态（Slice 4.3 只冻结基础修订）。

    基础修订在文件/页处理完成后一次性冻结，状态为 READY；它明确不可激活
    （``is_activatable=False``），不参与活动指针，也不推断或改写审核节点活动版本。
    Slice 4.4 引入定位/校对关联后才通过新命令创建更完整的处理修订，旧基础修订
    保持 READY 且永远不可激活、只可回放。
    """

    READY = "ready"


class OcrRunStatus(StableEnum):
    """文件级 OCR 运行状态；汇总计数与状态必须一致（合同校验）。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OcrAttemptStatus(StableEnum):
    """每次真实 OCR 请求的尝试结果（追加写，包含被拒绝的晚到尝试）。

    succeeded      结果已产生并被接受为缓存/页结果；
    failed         请求失败（含可重试与终止失败，按 failure_category 区分）；
    rejected_late  结果已产生但晚到/租约代次不匹配，只保留审计，不得进入缓存；
    cancelled      尝试在安全边界被取消。
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED_LATE = "rejected_late"
    CANCELLED = "cancelled"


class OcrFailureCategory(StableEnum):
    """OCR 尝试失败类别；决定重试范围与用户可见动作，不承载临床判断。"""

    NETWORK = "network"
    PROVIDER = "provider"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    STALE_LEASE = "stale_lease"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Slice 4.4 定位、风险、校对、完整处理修订、处理候选与活动版本（WP-44A 冻结）
# ---------------------------------------------------------------------------


class ProcessingRevisionKind(StableEnum):
    """证据处理修订类别（Slice 4.4 辨别）。

    ``base``     4.3 产物：只冻结页/PageArtifact/OCRPage，永远不可激活；
    ``complete`` 新建完整修订：在 base 页清单上冻结全部 4.4 关联，门禁闭合后可激活。
    """

    BASE = "base"
    COMPLETE = "complete"


class LocatorSourceLayer(StableEnum):
    """定位来源文本层；决定 source_text_sha256 锚定哪一层。

    native_text        页产物的原生文本层（PDF 字符/词）；
    raw_ocr            OCRPage.raw_text；
    effective_text     原 OCR + 所选校对的确定性投影（必须同时绑定处理修订与投影哈希）；
    page_review_visual 页级双主读判读的逐字视觉摘录层（OCR 不是其逐字权威）。必须携带
                       类型化视觉溯源绑定；摘录哈希锚定判读原文，页图哈希只存在于溯源
                       绑定中，原图哈希与摘录文本哈希严格分立。
    """

    NATIVE_TEXT = "native_text"
    RAW_OCR = "raw_ocr"
    EFFECTIVE_TEXT = "effective_text"
    PAGE_REVIEW_VISUAL = "page_review_visual"


class LocatorAuthenticity(StableEnum):
    """定位真实性门禁结果。

    ``authenticated``  bbox 由同源字符/词坐标逐字符映射、闭包校验通过；
    ``degraded``       无真实坐标，按 text_range/excerpt/page_only 诚实降级；
    ``rejected``       坐标来源无法证明，禁止输出 bbox 也不得伪装为定位。
    """

    AUTHENTICATED = "authenticated"
    DEGRADED = "degraded"
    REJECTED = "rejected"


class OcrRiskReviewDecision(StableEnum):
    """风险核对决议（追加写用户动作）。"""

    CONFIRMED_AS_READ = "confirmed_as_read"
    CORRECTED = "corrected"
    NOT_APPLICABLE = "not_applicable"


class CorrectionChangeKind(StableEnum):
    """校对变化类别；前五类沿用 PRD blocking 二次确认规则。

    semantic_connector 不是扫描器的自动“修正”，但用户确实把且/或/以及/任一/全部
    等连接词改为另一逻辑含义时，必须二次确认并保留前后文本。
    """

    POLARITY = "polarity"
    NUMERIC = "numeric"
    DECIMAL = "decimal"
    UNIT = "unit"
    DATE = "date"
    SEMANTIC_CONNECTOR = "semantic_connector"
    OTHER_TEXT = "other_text"


class ReferencedDocumentOrigin(StableEnum):
    """被提及资料登记来源：手工登记或确定性文本模式候选。"""

    MANUAL = "manual"
    DETERMINISTIC_CANDIDATE = "deterministic_candidate"


class ReferencedDocumentStatus(StableEnum):
    """被提及资料状态（经不可变修订演进，不保留可变布尔值）。

    proposed   确定性模式只能生成 proposed，绝不自动 confirmed/provided；
    confirmed  用户确认，必须保留可回放触发定位；
    dismissed  用户解除候选，不删除候选/触发原文/历史。
    """

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ReferencedDocumentResolutionStatus(StableEnum):
    """被提及资料满足状态：unresolved 或 provided（provided 必须绑定快照成员）。"""

    UNRESOLVED = "unresolved"
    PROVIDED = "provided"


class ActivationEventKind(StableEnum):
    """激活事件类别：回滚也是新激活事件，不静默改写指针。"""

    ACTIVATE = "activate"
    ROLLBACK = "rollback"


class EvidenceProcessingCandidateStatus(StableEnum):
    """证据处理候选状态（Slice 4.4 候选隔离）。

    staged -> processing -> (needs_attention | retryable_failure |
    terminal_failure | ready)；ready 经 activate 进入 active，或 revision_mismatch
    进入 revision_conflict。终态：active、revision_conflict、cancelled、
    terminal_failure，禁止再跳转。候选失败/取消/待核对/冲突不得改变活动指针。
    """

    STAGED = "staged"
    PROCESSING = "processing"
    NEEDS_ATTENTION = "needs_attention"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    READY = "ready"
    REVISION_CONFLICT = "revision_conflict"
    CANCELLED = "cancelled"
    ACTIVE = "active"


class ProcessingCandidateEventKind(StableEnum):
    """证据处理候选追加事件（设计书 §6 状态表；未列出的转换一律拒绝）。"""

    WORKER_START = "worker_start"
    CANCEL = "cancel"
    CHECKPOINT_SUCCESS = "checkpoint_success"
    BLOCKING_RISK_FOUND = "blocking_risk_found"
    RETRYABLE_ERROR = "retryable_error"
    TERMINAL_ERROR = "terminal_error"
    CANCEL_AT_SAFE_BOUNDARY = "cancel_at_safe_boundary"
    ALL_GATES_PASSED = "all_gates_passed"
    RETRY = "retry"
    CORRECTION_OR_RESOLUTION = "correction_or_resolution"
    ACTIVATE = "activate"
    REVISION_MISMATCH = "revision_mismatch"


# ---------------------------------------------------------------------------
# Phase 5 临床事实与 Patient Profile（Slice 5.1 冻结）
# ---------------------------------------------------------------------------


class SourceStrength(StableEnum):
    """来源强度（由文档类型、来源方与定位元数据确定性派生，不直接改变事实值）。

    - contemporaneous_objective_result  同期客观结果（检验/检查报告等）；
    - historical_primary_document       既往原始资料；
    - current_study_chart_direct_record 当前研究病历直接记录；
    - screening_record_transcription    筛选病历转述（阳性长期史可发布为较弱事实，
                                         必须生成加强溯源提醒）；
    - unverifiable_source               无法确认来源。
    """

    CONTEMPORANEOUS_OBJECTIVE = "contemporaneous_objective_result"
    HISTORICAL_PRIMARY = "historical_primary_document"
    CURRENT_STUDY_CHART = "current_study_chart_direct_record"
    SCREENING_RECORD_TRANSCRIPTION = "screening_record_transcription"
    UNVERIFIABLE = "unverifiable_source"


class DurationStatus(StableEnum):
    """持续状态；“既往”不等于“已结束”，不能从“既往”自动推断终止日期。

    ongoing     持续；
    ended       已结束（必须由资料明确给出终止信息，不得由“既往”推断）；
    intermittent 间歇；
    single      单次；
    unknown     未知。
    """

    ONGOING = "ongoing"
    ENDED = "ended"
    INTERMITTENT = "intermittent"
    SINGLE = "single"
    UNKNOWN = "unknown"


class FactGate(StableEnum):
    """确定性事实门禁步骤（设计书 §4.2 顺序，逐候选记录结果）。"""

    CONTRACT_AND_ENUM = "contract_and_enum"
    AUTHORITY_AND_ACTIVE_REVISION = "authority_and_active_revision"
    PAGE_COVERAGE_AND_REFERENCE_CLOSURE = "page_coverage_and_reference_closure"
    LOCATOR_AND_TEXT_HASH = "locator_and_text_hash"
    POLARITY_AND_ASSERTED_OBJECT = "polarity_and_asserted_object"
    VALUE_UNIT_DATE_SOURCE = "value_unit_date_source"
    IN_DOCUMENT_DEDUP_CONFLICT = "in_document_dedup_conflict"
    CROSS_DOCUMENT_MERGE_CONFLICT = "cross_document_merge_conflict"
    TRANSACTIONAL_PUBLISH = "transactional_publish"


class FactNormalizationRunStatus(StableEnum):
    """规范化运行状态（复用持久 Job 语义；失败/取消不污染上一活动 Profile）。"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FactCallStatus(StableEnum):
    """单个规范化调用的状态（默认每个逻辑文档一次调用）。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
