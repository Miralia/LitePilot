"""无入口 API 能力边界测试。"""

from app.api.endpoints import dashboard as dashboard_endpoint
from app.api.endpoints import history as history_endpoint
from app.api.endpoints import media as media_endpoint
from app.api.endpoints import mediaserver as mediaserver_endpoint
from app.api.endpoints import message as message_endpoint
from app.api.endpoints import system as system_endpoint
from app.api.endpoints import transfer as transfer_endpoint
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


def test_duplicate_api_token_route_suffixes_are_removed():
    """API_TOKEN 已由 verify_token 统一支持，不保留上游 *2 重复路由。"""
    dashboard_routes = {route.path for route in dashboard_endpoint.router.routes}
    for path in (
        "/statistic2",
        "/storage2",
        "/downloader2",
        "/schedule2",
        "/schedule2/{job_id}/progress",
        "/cpu2",
        "/memory2",
        "/network2",
    ):
        assert path not in dashboard_routes

    media_routes = {route.path for route in media_endpoint.router.routes}
    assert "/recognize2" not in media_routes
    assert "/recognize_file2" not in media_routes

    system_routes = {route.path for route in system_endpoint.router.routes}
    assert "/runscheduler2" not in system_routes


def test_modulelist_does_not_emit_unwired_localization_keys(monkeypatch):
    """模块列表只返回前端消费的稳定字段，不保留未接线翻译键。"""
    class Module:
        """提供模块列表测试所需的最小名称接口。"""

        @staticmethod
        def get_name():
            """返回测试模块名称。"""
            return "测试模块"

    monkeypatch.setattr(
        system_endpoint.ModuleManager,
        "get_modules",
        lambda self: {"test_module": Module()},
    )

    response = system_endpoint.modulelist(None)

    assert response.data == {"modules": [{"id": "test_module", "name": "测试模块"}]}


def test_synchronous_transfer_trigger_route_is_removed():
    """手动整理由调度器统一触发，不保留绕过调度边界的同步 API_TOKEN 路由。"""
    transfer_routes = {route.path for route in transfer_endpoint.router.routes}
    assert "/now" not in transfer_routes


def test_manual_transfer_target_path_preview_api_is_removed():
    """手动整理目标路径由正式整理请求自动匹配，不保留无入口的预填接口。"""
    routes = {route.path for route in transfer_endpoint.router.routes}
    assert "/manual/target-path" not in routes
    assert not hasattr(transfer_endpoint, "match_manual_transfer_target_path")
    assert not hasattr(transfer_endpoint, "_build_manual_transfer_target_path")
    assert not hasattr(transfer_endpoint, "_get_manual_transfer_target_key")
