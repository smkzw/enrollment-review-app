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
    EVENT_DATE = "event_date"


class TimeDirection(StableEnum):
    BEFORE = "before"
    AFTER = "after"
    ON = "on"


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
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


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
