"""V2 中文投影词汇表：稳定机器值 -> 用户可读中文（design.md §5）。"""
from __future__ import annotations

from app.workflow.states import TERMINAL_JOB_STATES

JOB_STATE_LABELS: dict[str, str] = {
    "queued": "等待处理",
    "running": "正在处理",
    "completed": "已完成",
    "failed_retryable": "未完成，稍后重试",
    "failed_final": "未完成，需要处理",
    "cancel_requested": "正在停止",
    "cancelled": "已停止",
    "recovering": "正在恢复",
    "waiting_user": "等待确认",
    "user_resumed": "已完成核对，继续处理",
}

STEP_STATE_LABELS: dict[str, str] = {
    "queued": "等待处理",
    "running": "正在处理",
    "completed": "已完成",
    "failed_retryable": "未完成，稍后重试",
    "failed_final": "未完成，需要处理",
    "cancelled": "已停止",
    "waiting_user": "等待确认",
}

EVENT_TYPE_LABELS: dict[str, str] = {
    "created": "已建立处理事项",
    "step_started": "开始处理",
    "step_completed": "本项处理完成",
    "step_failed": "本项处理未完成",
    "retry_scheduled": "已安排再次处理",
    "waiting_user": "等待确认",
    "user_resumed": "已完成核对，继续处理",
    "user_updated": "已补充确认资料",
    "cancel_requested": "停止请求已受理",
    "cancelled": "本次处理已停止",
    "completed": "本次处理已完成",
    "failed": "本次处理未完成",
    "page_progress": "页面处理进度",
}

_JOB_RECOVERY_ACTIONS: dict[str, str] = {
    "queued": "无需操作，正在等待开始。",
    "running": "正在处理；关闭页面不会中断已经确认的工作。",
    "failed_retryable": "系统将自动再次处理未完成部分；也可以手动重新处理失败范围。",
    "failed_final": "可以点击“重新处理失败部分”；已完成内容不会重复处理。",
    "cancel_requested": "停止请求已受理，将在当前内容保存完成后停止。",
    "cancelled": "本次处理已停止；已完成内容和恢复位置仍会保留。",
    "completed": "本次处理已完成。",
    "recovering": "服务重新启动后正在恢复，无需操作。",
    "waiting_user": "正在等待识别核对；提交后将继续生成资料版本。",
}


def job_recovery_action(state: str) -> str:
    return _JOB_RECOVERY_ACTIONS.get(state, "请刷新任务状态获取最新进展。")


def is_terminal_label(state: str) -> bool:
    return state in TERMINAL_JOB_STATES


def study_phase_label(phase: str) -> str:
    labels = {
        "phase_ii": "II 期",
        "phase_iii": "III 期",
        "seamless_phase_ii_iii": "II/III 期无缝设计",
        "other": "其他",
    }
    return labels.get(phase, phase)


REVIEW_STAGE_LABELS: dict[str, str] = {
    "pre_screening": "预筛选",
    "screening": "筛选",
    "run_in": "导入期",
    "baseline": "基线",
}


def review_stage_label(stage: str) -> str:
    return REVIEW_STAGE_LABELS.get(stage, stage)


METADATA_STATUS_LABELS: dict[str, str] = {
    "pending": "待确认",
    "needs_confirmation": "需要确认",
    "confirmed": "已确认",
    "conflict": "存在冲突",
    "rejected": "已排除",
}

METADATA_FIELD_LABELS: dict[str, str] = {
    "document_title": "文档标题",
    "project_name": "项目名称",
    "project_code": "项目代号",
    "protocol_code": "方案编号",
    "protocol_version": "方案版本",
    "protocol_date": "方案日期",
    "template_code": "模板编号",
    "template_version": "模板版本",
}

METADATA_SOURCE_LABELS: dict[str, str] = {
    "header_footer": "页眉或页脚",
    "first_page": "方案首页",
    "signature_page": "方案签署页",
    "body": "方案正文",
    "filename": "文件名（仅供辅助核对）",
}

DRAFT_STATUS_LABELS: dict[str, str] = {
    "draft": "草稿",
    "saved": "已保存",
    "cancelled": "已取消",
    "published": "已发布",
    "restored_from": "已恢复",
}

DRAFT_REASON_LABELS: dict[str, str] = {
    "initial_save": "首次保存",
    "manual_edit": "手工编辑",
    "source_error_feedback": "原文理解纠错",
    "clarification_feedback": "解释性澄清",
    "restore": "恢复历史版本",
}


# ---------------------------------------------------------------------------
# Phase 4 证据上传预览与快照（Slice 4.2）
# ---------------------------------------------------------------------------


UPLOAD_MODE_LABELS: dict[str, str] = {
    "incremental": "补充资料",
    "full": "建立完整资料快照",
}


def upload_mode_label(mode: str) -> str:
    return UPLOAD_MODE_LABELS.get(mode, mode)


PREVIEW_STATUS_LABELS: dict[str, str] = {
    "staged": "等待确认",
    "committed": "已确认",
    "cancelled": "已取消",
    "cancel_pending": "正在取消",
}


def preview_status_label(status: str) -> str:
    return PREVIEW_STATUS_LABELS.get(status, status)


ITEM_STATUS_LABELS: dict[str, str] = {
    "added": "新增资料",
    "duplicate": "内容重复",
    "conflict": "名称相同但内容不同",
    "unsupported": "格式不支持",
    "unreadable": "无法读取",
    "full_snapshot_omission": "完整资料中未选择",
    "expected_reprocessing": "需要重新识别",
}


def item_status_label(status: str) -> str:
    return ITEM_STATUS_LABELS.get(status, status)


_PROCESSING_HINT_LABELS: dict[str, str] = {
    "process_new": "需要处理",
    "reuse_existing": "复用已有处理结果",
    "require_resolution": "需要选择处置方式",
    "rejected": "不纳入处理",
    "omitted": "不纳入本次快照",
    "reprocess": "需要重新识别",
}


def processing_hint_label(hint: str) -> str:
    return _PROCESSING_HINT_LABELS.get(hint, hint)


_ITEM_STATUS_REASONS: dict[str, str] = {
    "added": "该文件内容与文件名均未出现在上一有效快照中，为本次新增资料。",
    "duplicate": "该文件内容与上一有效快照中已存在的资料完全相同。",
    "conflict": "存在同名文件但内容不同，系统不会自动覆盖。",
    "unsupported": "该文件格式当前不受支持。",
    "unreadable": "该文件无法读取，可能为空、损坏或格式无法识别。",
    "full_snapshot_omission": "该资料存在于上一有效快照，但本次未选择。",
    "expected_reprocessing": "完整资料快照重新纳入了与基准内容相同的文件。",
}


def item_status_reason(status: str, error_detail: str | None = None) -> str:
    """逐文件分类的中文原因；服务端给出的具体原因（不支持/无法读取）优先。"""
    if error_detail:
        return error_detail
    return _ITEM_STATUS_REASONS.get(status, "")


_ITEM_NEXT_ACTIONS: dict[str, str] = {
    "added": "将首次处理该文件，请确认后提交。",
    "duplicate": "系统将复用已有处理结果，不会重复保存或重复识别。",
    "conflict": "请选择“作为原资料的新版本”或“作为另一份资料并列保留”。",
    "unsupported": "请解压或转换为受支持的格式（PDF、Word、TXT、常用图片）后重新选择。",
    "unreadable": "请检查文件是否损坏或为空后重新选择。",
    "full_snapshot_omission": "如确认遗漏，请重新选择该文件；完整资料快照只包含本次选择。",
    "expected_reprocessing": "系统将按本次快照重新处理该文件。",
}


def item_next_action(status: str) -> str:
    return _ITEM_NEXT_ACTIONS.get(status, "请确认后提交。")


SNAPSHOT_STATUS_LABELS: dict[str, str] = {
    "staged": "待处理",
    "processing": "处理中",
    "needs_attention": "待完成识别核对",
    "retryable_failure": "失败（可重试）",
    "terminal_failure": "处理失败",
    "ready": "待发布",
    "active": "当前有效",
    "revision_conflict": "修订冲突",
    "cancelled": "已取消",
}


def snapshot_status_label(status: str) -> str:
    return SNAPSHOT_STATUS_LABELS.get(status, status)


SNAPSHOT_MEMBER_ORIGIN_LABELS: dict[str, str] = {
    "inherited": "继承自上一快照",
    "added": "本次新增",
    "replaced": "替代旧版本",
}


def snapshot_member_origin_label(origin: str) -> str:
    return SNAPSHOT_MEMBER_ORIGIN_LABELS.get(origin, origin)


CONFLICT_RESOLUTION_LABELS: dict[str, str] = {
    "new_version": "作为原资料的新版本",
    "keep_parallel": "作为另一份资料并列保留",
}


def conflict_resolution_label(resolution: str) -> str:
    return CONFLICT_RESOLUTION_LABELS.get(resolution, resolution)


# ---------------------------------------------------------------------------
# Phase 4 定位、风险核对、校对与完整处理修订（Slice 4.4）
# ---------------------------------------------------------------------------


REVISION_KIND_LABELS: dict[str, str] = {
    "base": "基础处理修订",
    "complete": "完整处理修订",
}


def revision_kind_label(kind: str) -> str:
    return REVISION_KIND_LABELS.get(kind, kind)


OCR_PAGE_STATUS_LABELS: dict[str, str] = {
    "pending": "等待识别",
    "processing": "识别中",
    "succeeded": "已识别",
    "failed": "识别失败",
    "degraded": "降级结果",
}


def ocr_page_status_label(status: str) -> str:
    return OCR_PAGE_STATUS_LABELS.get(status, status)


PAGE_ARTIFACT_STATUS_LABELS: dict[str, str] = {
    "succeeded": "页面已就绪",
    "degraded": "页面可查看，部分内容需核对",
    "failed": "页面处理失败",
}


def page_artifact_status_label(status: str) -> str:
    return PAGE_ARTIFACT_STATUS_LABELS.get(status, status)


OCR_RISK_KIND_LABELS: dict[str, str] = {
    "negation_polarity": "否定/肯定",
    "numeric_value": "关键数值",
    "decimal_point": "小数点",
    "unit": "单位",
    "date": "日期",
    "repeated_text": "重复文本",
    "output_repetition": "识别内容异常重复",
    "low_confidence": "低置信度",
}


def ocr_risk_kind_label(kind: str) -> str:
    return OCR_RISK_KIND_LABELS.get(kind, kind)


OCR_RISK_LEVEL_LABELS: dict[str, str] = {
    "blocking": "关键识别项",
    "informational": "识别提示",
}


def ocr_risk_level_label(level: str) -> str:
    return OCR_RISK_LEVEL_LABELS.get(level, level)


OCR_RISK_REVIEW_DECISION_LABELS: dict[str, str] = {
    "confirmed_as_read": "确认与原文一致",
    "corrected": "已通过校对修正",
    "not_applicable": "不适用",
}


def ocr_risk_review_decision_label(decision: str) -> str:
    return OCR_RISK_REVIEW_DECISION_LABELS.get(decision, decision)


CORRECTION_CHANGE_KIND_LABELS: dict[str, str] = {
    "polarity": "极性",
    "numeric": "关键数值",
    "decimal": "小数点",
    "unit": "单位",
    "date": "日期",
    "semantic_connector": "语义连接词",
    "other_text": "其他文本",
}


def correction_change_kind_label(kind: str) -> str:
    return CORRECTION_CHANGE_KIND_LABELS.get(kind, kind)


LOCATOR_PRECISION_LABELS: dict[str, str] = {
    "bbox": "原文区域",
    "text_range": "原文文字",
    "page_excerpt": "页内摘录",
    "page_only": "仅页码",
}


def locator_precision_label(precision: str) -> str:
    return LOCATOR_PRECISION_LABELS.get(precision, precision)


LOCATOR_SOURCE_LAYER_LABELS: dict[str, str] = {
    "native_text": "文档原文",
    "raw_ocr": "原始识别文字",
    "effective_text": "校对后文字",
    "page_review_visual": "原件核对摘录",
}


def locator_source_layer_label(layer: str) -> str:
    return LOCATOR_SOURCE_LAYER_LABELS.get(layer, layer)


REFERENCED_DOCUMENT_ORIGIN_LABELS: dict[str, str] = {
    "manual": "手工登记",
    "deterministic_candidate": "系统候选",
}


def referenced_document_origin_label(origin: str) -> str:
    return REFERENCED_DOCUMENT_ORIGIN_LABELS.get(origin, origin)


REFERENCED_DOCUMENT_STATUS_LABELS: dict[str, str] = {
    "proposed": "待确认",
    "confirmed": "已确认",
    "dismissed": "已解除",
}


def referenced_document_status_label(status: str) -> str:
    return REFERENCED_DOCUMENT_STATUS_LABELS.get(status, status)


REFERENCED_DOCUMENT_RESOLUTION_LABELS: dict[str, str] = {
    "unresolved": "未提供",
    "provided": "已提供",
}


def referenced_document_resolution_label(status: str) -> str:
    return REFERENCED_DOCUMENT_RESOLUTION_LABELS.get(status, status)


ACTIVATION_EVENT_KIND_LABELS: dict[str, str] = {
    "activate": "启用",
    "rollback": "回滚",
}


def activation_event_kind_label(kind: str) -> str:
    return ACTIVATION_EVENT_KIND_LABELS.get(kind, kind)


GATE_STATUS_LABELS: dict[str, str] = {
    "passed": "通过",
    "not_applicable": "不适用",
}


def gate_status_label(status: str) -> str:
    return GATE_STATUS_LABELS.get(status, status)


# ---------------------------------------------------------------------------
# Phase 5 页面视觉核验任务（冻结修订后的独立后处理）
# ---------------------------------------------------------------------------


SELECTIVE_VISION_TASK_LABEL = "页面视觉核验"

_SELECTIVE_VISION_RECOVERY_ACTIONS: dict[str, str] = {
    "queued": "页面视觉核验正在等待开始；关闭页面不会中断任务。",
    "running": "正在对需要视觉核验的页面进行核验；完成后此处会自动更新。",
    "completed": "页面视觉核验已完成。",
    "failed_retryable": "页面视觉核验尚未完成，系统将自动重试；也可以手动重新开始。",
    "failed_final": "页面视觉核验未完成；可以点击“重新开始核验”，识别原文与核对结果不受影响。",
    "cancel_requested": "停止请求已受理，将在安全节点停止页面视觉核验。",
    "cancelled": "页面视觉核验已停止；识别原文与核对结果不受影响。",
    "recovering": "服务重新启动后正在恢复页面视觉核验，无需操作。",
    "waiting_user": "页面视觉核验正在等待确认。",
}

_SELECTIVE_VISION_NOT_CREATED_RECOVERY = (
    "当前资料版本建立时没有生成页面视觉核验任务；重新处理资料后会自动建立。"
)

#: 关闭记录的失败类别 -> 中文说明；不出现模型名、提示词或内部日志词。
_SELECTIVE_VISION_CLOSED_REASON_LABELS: dict[str, str] = {
    "missing_page_inputs": "部分页面缺少图像或识别输入，无法进行视觉核验",
    "config_error": "视觉核验配置与当前系统不一致",
    "source_fidelity": "页面内容与识别来源不一致，核验已停止",
    "remote_error": "视觉核验服务暂时不可用",
}


def selective_vision_recovery_action(state: str | None) -> str:
    if state is None:
        return _SELECTIVE_VISION_NOT_CREATED_RECOVERY
    return _SELECTIVE_VISION_RECOVERY_ACTIONS.get(
        state, "请刷新任务状态获取最新进展。"
    )


def selective_vision_closed_reason_label(kind: str | None) -> str | None:
    if kind is None:
        return None
    return _SELECTIVE_VISION_CLOSED_REASON_LABELS.get(
        kind, "部分页面未能完成视觉核验"
    )


def selective_vision_failed_scope_label(failed_step_names: list[str]) -> str | None:
    """失败范围的用户可读描述：只使用任务步骤的中文名称。"""
    names = [name for name in failed_step_names if str(name).strip()]
    if not names:
        return None
    return "、".join(names)
