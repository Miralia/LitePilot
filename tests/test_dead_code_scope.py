"""无消费者上游通用代码边界回归测试。"""

import importlib.util

from app.schemas import TransferInfo, TransferTask
from app.utils.object import ObjectUtils


def test_dead_object_utils_helpers_are_removed():
    """ObjectUtils 只保留模块与命令分发仍使用的方法。"""
    assert not hasattr(ObjectUtils, "is_obj")
    assert not hasattr(ObjectUtils, "is_objstr")


def test_dead_tmdb_as_obj_adapter_is_removed():
    """TMDB 客户端已直接返回 JSON 字典，不应保留上游 AsObj 适配层。"""
    assert importlib.util.find_spec("app.modules.themoviedb.tmdbv3api.as_obj") is None


def test_dead_transfer_schema_to_dict_helpers_are_removed():
    """Pydantic 传输模型使用 model_dump/直接字段访问，不保留无人调用的 to_dict。"""
    assert not hasattr(TransferTask, "to_dict")
    assert not hasattr(TransferInfo, "to_dict")
