"""V2 persistence adapters and write-boundary enforcement."""
from app.storage import (
    control_catalog_models,  # noqa: F401  # 0024 跨章控制目录
    evidence_locator_models,  # noqa: F401  # 导入即把 0010 ORM 注册到 Base.metadata
    facts_models,  # noqa: F401  # 导入即把 0013 ORM 注册到 Base.metadata
    judgment_search_models,  # noqa: F401  # 导入即把 0022 ORM 注册到 Base.metadata
    models,  # noqa: F401  # 导入即把领域 ORM 注册到 Base.metadata
    review_control_models,  # noqa: F401
    page_review_models,  # noqa: F401  # 导入即把 0020 ORM 注册到 Base.metadata
    selective_vision_observation_models,  # noqa: F401  # 导入即把 0019 ORM 注册到 Base.metadata
)
