"""V2 应用引导再导出（WP-44C 薄 API 边界）。

``app/api/v2/app.py`` 只允许导入 domain contracts、application services、API
schemas/vocabulary 与 FastAPI；数据库引导（``DataPaths``/``upgrade_or_fail``）
经本服务再导出，使 app 工厂不直接导入 ``app.storage``。
"""
from __future__ import annotations

from app.storage.config import DataPaths, resolve_data_paths
from app.storage.migrate import upgrade_or_fail

__all__ = ["DataPaths", "resolve_data_paths", "upgrade_or_fail"]
