"""HTTP 编码探测能力边界回归测试。"""

from pathlib import Path

from app.core.config import ConfigModel
from app.utils.http import RequestUtils


def test_legacy_site_response_decoding_helpers_are_removed() -> None:
    """站点/RSS 页面解码链路已经移除，HTTP 工具不再保留无消费者编码探测方法。"""
    for method in (
        "detect_encoding_from_html_response",
        "detect_xml_declared_encoding",
        "is_low_confidence_http_encoding",
        "get_decoded_xml_content",
        "get_decoded_html_content",
    ):
        assert not hasattr(RequestUtils, method)


def test_legacy_encoding_detection_configuration_is_removed() -> None:
    """编码探测性能开关只服务已删除的站点页面解码链路。"""
    assert "ENCODING_DETECTION_PERFORMANCE_MODE" not in ConfigModel.model_fields


def test_chardet_is_not_a_runtime_dependency() -> None:
    """活跃结构化 API 集成都返回 JSON，不需要 chardet 运行时依赖。"""
    requirements = Path("requirements.in").read_text(encoding="utf-8")
    assert "chardet" not in requirements
