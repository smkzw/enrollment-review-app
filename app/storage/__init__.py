"""V2 persistence adapters and write-boundary enforcement."""
from app.storage import (
    evidence_locator_models,  # noqa: F401  # 导入即把 0010 ORM 注册到 Base.metadata
    facts_models,  # noqa: F401  # 导入即把 0013 ORM 注册到 Base.metadata
    models,  # noqa: F401  # 导入即把领域 ORM 注册到 Base.metadata
)
