"""媒体类型 API 转换命名边界测试。"""

from app.schemas.types import MediaType


def test_media_type_api_conversion_uses_neutral_name():
    """媒体类型转换服务管理接口输出，不再保留 Agent 时代命名。"""
    assert hasattr(MediaType, "to_api_value")
    assert not hasattr(MediaType, "to_agent")
    assert not hasattr(MediaType, "from_agent")
    assert MediaType.MOVIE.to_api_value() == "movie"
    assert MediaType.TV.to_api_value() == "tv"
    assert MediaType.COLLECTION.to_api_value() == MediaType.COLLECTION.value
