"""人工事实修订服务的公共导出合同。"""

from app.services import fact_correction_service


def test_fact_correction_service_public_exports_resolve() -> None:
    assert all(
        hasattr(fact_correction_service, name)
        for name in fact_correction_service.__all__
    )
