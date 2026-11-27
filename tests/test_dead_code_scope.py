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


def test_dead_category_folder_parameters_are_removed():
    """二级分类能力取消后，目标路径计算不应保留恒为空的类别目录参数。"""
    import inspect

    from app.modules.filemanager.transhandler import TransHandler

    assert "need_category_folder" not in inspect.signature(TransHandler.get_dest_path).parameters
    assert "need_category_folder" not in inspect.signature(TransHandler.get_dest_dir).parameters


def test_dead_message_source_lookup_is_removed():
    """消息 source 字段是渠道名而非唯一消息标识，无调用方的存在性查询不应保留。"""
    from app.db.message_oper import MessageOper
    from app.db.models.message import Message

    assert not hasattr(Message, "exists_by_source")
    assert not hasattr(MessageOper, "exists_by_source")


def test_dead_sync_transfer_history_search_is_removed():
    """整理历史搜索 API 已异步化，不保留仅被测试自引用的同步查询链。"""
    from app.db.models.transferhistory import TransferHistory
    from app.db.transferhistory_oper import TransferHistoryOper

    assert not hasattr(TransferHistory, "list_by_title")
    assert not hasattr(TransferHistory, "count_by_title")
    assert not hasattr(TransferHistoryOper, "get_by_title")
