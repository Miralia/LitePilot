"""后台进度能力边界测试。"""

from app.schemas.types import ProgressKey


def test_progress_keys_are_limited_to_active_background_workflows() -> None:
    """站点搜索链路移除后，不再保留无生产者的搜索进度键。"""
    assert {item.name for item in ProgressKey} == {"FileTransfer", "BatchRename"}
