"""运行依赖边界测试。"""

from pathlib import Path

from app.schemas import NotExistMediaInfo


def test_async_timeout_is_not_required_for_supported_python_versions() -> None:
    """项目不使用 async_timeout，且支持基线已是现代 Python，不保留历史兼容依赖。"""
    assert "async_timeout" not in Path("requirements.in").read_text()


def test_missing_media_schema_does_not_keep_acquisition_coverage_field() -> None:
    """缺失媒体查询只返回季集缺失状态，不保留批量下载择优覆盖标记。"""
    assert "require_complete_coverage" not in NotExistMediaInfo.model_fields
