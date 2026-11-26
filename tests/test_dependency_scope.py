"""运行依赖边界测试。"""

from pathlib import Path

from app import schemas


def test_async_timeout_is_not_required_for_supported_python_versions() -> None:
    """项目不使用 async_timeout，且支持基线已是现代 Python，不保留历史兼容依赖。"""
    assert "async_timeout" not in Path("requirements.in").read_text()


def test_missing_media_probe_schema_is_not_retained() -> None:
    """订阅缺失探测能力移除后，不保留对应的季集缺失响应 schema。"""
    assert not hasattr(schemas, "NotExistMediaInfo")
