from unittest.mock import MagicMock, patch

from app.modules.emby import EmbyModule
from app.modules.emby.emby import Emby


def test_request_utils_reuses_instance_session():
    """同一 Emby 实例的请求必须复用底层 session，避免每次 API 调用重建连接池。"""
    client = Emby.__new__(Emby)

    with patch("app.modules.emby.emby.RequestUtils") as request_utils_cls:
        client._request_utils()
        client._request_utils(timeout=10)

    first_session = request_utils_cls.call_args_list[0].kwargs["session"]
    second_session = request_utils_cls.call_args_list[1].kwargs["session"]
    assert first_session is second_session


def test_close_releases_emby_session():
    """Emby 客户端关闭时必须释放底层 HTTP session。"""
    client = Emby.__new__(Emby)
    session = MagicMock()
    client._session = session

    client.close()

    session.close.assert_called_once_with()


def test_close_stops_remaining_metadata_discovery():
    """关闭旧实例后，首个进行中的请求之外的后续发现请求不得继续发起。"""
    import threading

    first_request_started = threading.Event()
    release_first_request = threading.Event()
    request_count = 0
    request_count_lock = threading.Lock()
    response = MagicMock()
    response.json.side_effect = [
        [{"Id": "user-id", "Name": "mp-user", "Policy": {}}],
        [],
        {"Id": "server-id"},
    ]

    class BlockingFirstRequestUtils:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_res(self, *_args, **_kwargs):
            nonlocal request_count
            with request_count_lock:
                request_count += 1
                is_first_request = request_count == 1
            if is_first_request:
                first_request_started.set()
                release_first_request.wait(1)
            return response

    with patch("app.modules.emby.emby.RequestUtils", BlockingFirstRequestUtils):
        client = Emby(host="http://emby.local/", apikey="api-key", username="mp-user")
        assert first_request_started.wait(1)
        client.close()
        release_first_request.set()

        assert client._metadata_ready.wait(1)
        with request_count_lock:
            assert request_count == 1


def test_module_stop_closes_emby_instances():
    """模块停止必须逐实例释放媒体服务器连接资源。"""
    server = MagicMock()
    module = EmbyModule.__new__(EmbyModule)
    module.get_instances = MagicMock(return_value={"emby": server})

    module.stop()

    server.close.assert_called_once_with()
