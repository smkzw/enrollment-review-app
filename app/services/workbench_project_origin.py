"""共享工作台来源（``workbench:<shared_project_id>``）的最小持久合同。

来源标识是**元数据**：它只说明"该任务来自共享医学经理工作台的哪个用户项目"，
既不是本产品的正式 project_id，也不是方案身份、期别或发布授权。共享工作台与
本产品的项目编号体系不同，因此必须显式命名空间，禁止把 ``proj_user_*`` 直接
当作本产品正式身份使用。

本模块只包含纯函数：规范化与从持久任务 payload 读取来源。任务/项目的持久解析
在 :class:`app.services.protocol_workbench_service.ProtocolWorkbenchService`，
落库沿用既有 Job JSON payload（``workbench_origin`` 键），不新建表或队列。
"""
from __future__ import annotations

import re
from typing import Any, Mapping

WORKBENCH_ORIGIN_NAMESPACE = "workbench"
WORKBENCH_ORIGIN_PAYLOAD_KEY = "workbench_origin"

#: 共享侧项目编号的保守字符集；不假设任何 ``proj_*`` 前缀（那不是本产品合同）。
_SHARED_PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_MAX_ORIGIN_LENGTH = 256


class WorkbenchOriginError(ValueError):
    """共享工作台来源标识不符合显式命名空间合同。"""


def normalize_workbench_origin(value: str) -> str:
    """校验并规范化共享工作台来源；不符合合同立即拒绝，不做宽容猜测。"""
    raw = value.strip() if isinstance(value, str) else ""
    if not raw:
        raise WorkbenchOriginError("共享工作台来源不能为空")
    if len(raw) > _MAX_ORIGIN_LENGTH:
        raise WorkbenchOriginError("共享工作台来源过长")
    namespace, separator, shared_project_id = raw.partition(":")
    if separator != ":" or namespace != WORKBENCH_ORIGIN_NAMESPACE:
        raise WorkbenchOriginError(
            f"共享工作台来源必须使用显式命名空间 {WORKBENCH_ORIGIN_NAMESPACE}:<共享项目编号>，"
            "不能使用裸项目编号或其他命名空间"
        )
    if _SHARED_PROJECT_ID_PATTERN.fullmatch(shared_project_id) is None:
        raise WorkbenchOriginError(
            "共享工作台项目编号只能包含字母、数字、点、下划线和连字符"
        )
    return f"{WORKBENCH_ORIGIN_NAMESPACE}:{shared_project_id}"


def job_workbench_origin(payload: Mapping[str, Any]) -> str | None:
    """读取创建任务时冻结的来源；损坏值不能降为未绑定。"""
    if WORKBENCH_ORIGIN_PAYLOAD_KEY not in payload:
        return None
    return normalize_workbench_origin(payload[WORKBENCH_ORIGIN_PAYLOAD_KEY])
