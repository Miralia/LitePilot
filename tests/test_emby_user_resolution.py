import threading
import time
from unittest.mock import Mock, patch

from app.modules.emby.emby import Emby


def _resolve_user(users: list[dict], requested_username: str, configured_username: str):
    emby = Emby.__new__(Emby)
    emby._host = "http://emby.local/"
    emby._apikey = "test-api-key"
    emby._username = configured_username

    response = Mock()
    response.json.return_value = users
    with patch("app.modules.emby.emby.RequestUtils") as request_utils:
        request_utils.return_value.get_res.return_value = response
        return emby.get_user(requested_username)


def test_emby_init_does_not_block_on_metadata_network_requests():
    """Emby 元数据首次建连缓慢时，模块构造不得阻塞应用启动。"""
    lookup_started = threading.Event()
    release_lookup = threading.Event()
    response = Mock()
    response.json.side_effect = [
        [{"Id": "user-id", "Name": "mp-user", "Policy": {"IsAdministrator": True}}],
        [],
        {"Id": "server-id"},
    ]

    class SlowRequestUtils:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_res(self, *_args, **_kwargs):
            lookup_started.set()
            release_lookup.wait(1)
            return response

    with patch("app.modules.emby.emby.RequestUtils", SlowRequestUtils):
        started_at = time.monotonic()
        client = Emby(host="http://emby.local/", apikey="api-key", username="mp-user")
        elapsed = time.monotonic() - started_at

        assert elapsed < 0.5
        assert lookup_started.wait(0.5)
        release_lookup.set()
        assert client.user == "user-id"
        assert client.serverid == "server-id"


def test_reconnect_waits_for_initial_metadata_bootstrap():
    """启动中的首次初始化与定时重连必须串行完成，不能相互覆盖或死锁。"""
    lookup_started = threading.Event()
    release_lookup = threading.Event()
    request_count = 0
    request_count_lock = threading.Lock()
    response = Mock()
    response.json.side_effect = [
        [{"Id": "initial-user", "Name": "mp-user", "Policy": {}}],
        [],
        {"Id": "initial-server"},
        [{"Id": "reconnected-user", "Name": "mp-user", "Policy": {}}],
        [{"Id": "library-id"}],
        {"Id": "reconnected-server"},
    ]

    class SlowFirstRequestUtils:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_res(self, *_args, **_kwargs):
            nonlocal request_count
            with request_count_lock:
                request_count += 1
                is_first_request = request_count == 1
            if is_first_request:
                lookup_started.set()
                release_lookup.wait(1)
            return response

    with patch("app.modules.emby.emby.RequestUtils", SlowFirstRequestUtils):
        client = Emby(host="http://emby.local/", apikey="api-key", username="mp-user")
        assert lookup_started.wait(1)
        reconnect_thread = threading.Thread(target=client.reconnect, daemon=True)
        reconnect_thread.start()
        release_lookup.set()
        reconnect_thread.join(2)

        assert not reconnect_thread.is_alive()
        assert client.user == "reconnected-user"
        assert client.folders == [{"Id": "library-id"}]
        assert client.serverid == "reconnected-server"


def test_get_user_prefers_requested_username():
    """指定用户名存在时应优先使用该用户。"""
    result = _resolve_user(
        users=[
            {"Id": "requested-id", "Name": "mp-user", "Policy": {}},
            {"Id": "configured-id", "Name": "configured-user", "Policy": {}},
            {"Id": "admin-id", "Name": "admin", "Policy": {"IsAdministrator": True}},
        ],
        requested_username="mp-user",
        configured_username="configured-user",
    )

    assert result == "requested-id"


def test_get_user_falls_back_to_configured_username():
    """指定用户名不存在时应回退媒体服务器配置用户。"""
    result = _resolve_user(
        users=[
            {"Id": "configured-id", "Name": "configured-user", "Policy": {}},
            {"Id": "admin-id", "Name": "admin", "Policy": {"IsAdministrator": True}},
        ],
        requested_username="missing-mp-user",
        configured_username="configured-user",
    )

    assert result == "configured-id"


def test_get_user_falls_back_to_administrator():
    """指定用户和配置用户均不存在时应回退管理员。"""
    result = _resolve_user(
        users=[
            {"Id": "regular-id", "Name": "regular", "Policy": {}},
            {"Id": "admin-id", "Name": "admin", "Policy": {"IsAdministrator": True}},
        ],
        requested_username="missing-mp-user",
        configured_username="missing-configured-user",
    )

    assert result == "admin-id"
