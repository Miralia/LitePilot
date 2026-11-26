"""无入口 API 能力边界测试。"""

from app.api.endpoints import history as history_endpoint
from app.api.endpoints import mediaserver as mediaserver_endpoint
from app.api.endpoints import message as message_endpoint
from app.db import Base
from app.db.message_oper import MessageOper
from app.db.models.message import Message


def test_duplicate_mediaserver_client_listing_is_removed():
    """媒体服务器配置已统一从系统设置读取，不保留重复的客户端列表接口。"""
    routes = {route.path for route in mediaserver_endpoint.router.routes}
    assert "/clients" not in routes


def test_unreferenced_destructive_history_empty_api_is_removed():
    """整理历史已支持按选择删除，不保留无入口的全量清空危险接口。"""
    routes = {route.path for route in history_endpoint.router.routes}
    assert "/empty/transfer" not in routes


def test_removed_web_chat_message_apis_are_not_retained():
    """当前 UI 没有 Web 命令会话，不保留对应的接收与查询接口。"""
    routes = {(route.path, tuple(sorted(route.methods or ()))) for route in message_endpoint.router.routes}
    assert ("/web", ("POST",)) not in routes
    assert ("/web", ("GET",)) not in routes


def test_removed_web_chat_inbox_query_chain_is_not_retained():
    """Web 消息入口移除后，不保留只服务该收件箱的异步分页查询链。"""
    assert not hasattr(MessageOper, "async_list_by_page")
    assert not hasattr(Message, "async_list_by_page")


def test_unreferenced_async_truncate_helper_is_removed():
    """全量清空接口移除后，不保留无调用方的异步清表基础能力。"""
    assert not hasattr(Base, "async_truncate")
