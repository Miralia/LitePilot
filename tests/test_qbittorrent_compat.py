import importlib.util
import sys
import threading
import time
import types
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_qbittorrent_modules():
    repo_root = Path(__file__).resolve().parents[1]

    app_module = types.ModuleType("app")
    app_module.__path__ = []
    core_module = types.ModuleType("app.core")
    core_module.__path__ = []
    utils_module = types.ModuleType("app.utils")
    utils_module.__path__ = []
    modules_module = types.ModuleType("app.modules")
    modules_module.__path__ = []
    qbittorrent_package_module = types.ModuleType("app.modules.qbittorrent")
    qbittorrent_package_module.__path__ = []
    log_module = types.ModuleType("app.log")
    cache_module = types.ModuleType("app.core.cache")
    config_module = types.ModuleType("app.core.config")
    metainfo_module = types.ModuleType("app.core.metainfo")
    schemas_module = types.ModuleType("app.schemas")
    schema_types_module = types.ModuleType("app.schemas.types")
    string_module = types.ModuleType("app.utils.string")
    qbittorrentapi_module = types.ModuleType("qbittorrentapi")
    qbittorrentapi_client_module = types.ModuleType("qbittorrentapi.client")
    qbittorrentapi_transfer_module = types.ModuleType("qbittorrentapi.transfer")

    class _Logger:
        def info(self, *_args, **_kwargs):
            pass

        def warn(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

    class _StringUtils:
        @staticmethod
        def get_domain_address(address, prefix=False):
            return address, 8080

        @staticmethod
        def is_magnet_link(value):
            if isinstance(value, bytes):
                return value.startswith(b"magnet:")
            return isinstance(value, str) and value.startswith("magnet:")

        @staticmethod
        def generate_random_str(_length):
            return "tmp-tag-01"

        @staticmethod
        def str_filesize(value):
            return str(value)

        @staticmethod
        def str_secends(value):
            return str(value)

    class _FileCache:
        def get(self, *_args, **_kwargs):
            return None

    class _MetaInfo:
        def __init__(self, name):
            self.name = name
            self.year = None
            self.season_episode = ""
            self.episode_list = []

    class _ModuleBase:
        pass

    class _DownloaderBase:
        def __class_getitem__(cls, _item):
            return cls

    class _DownloaderTorrent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class TorrentStatus(Enum):
        TRANSFER = "transfer"
        DOWNLOADING = "downloading"

    class TorrentQueryStatus(Enum):
        ALL = "all"
        TRANSFER = "transfer"
        DOWNLOADING = "downloading"
        COMPLETED = "completed"
        PAUSED = "paused"

    class DownloadTaskState(Enum):
        DOWNLOADING = "downloading"
        PAUSED = "paused"
        COMPLETED = "completed"

    class ModuleType(Enum):
        Downloader = "Downloader"

    class DownloaderType(Enum):
        Qbittorrent = "Qbittorrent"

    log_module.logger = _Logger()
    cache_module.FileCache = _FileCache
    config_module.settings = types.SimpleNamespace(TORRENT_TAG="moviepilot-tag")
    metainfo_module.MetaInfo = _MetaInfo
    schemas_module.DownloaderInfo = object
    schemas_module.DownloaderTorrent = _DownloaderTorrent
    schema_types_module.TorrentStatus = TorrentStatus
    schema_types_module.TorrentQueryStatus = TorrentQueryStatus
    schema_types_module.DownloadTaskState = DownloadTaskState
    schema_types_module.ModuleType = ModuleType
    schema_types_module.DownloaderType = DownloaderType
    string_module.StringUtils = _StringUtils
    modules_module._ModuleBase = _ModuleBase
    modules_module._DownloaderBase = _DownloaderBase
    qbittorrentapi_module.TorrentDictionary = dict
    qbittorrentapi_module.TorrentFilesList = list
    qbittorrentapi_module.LoginFailed = type("LoginFailed", (Exception,), {})
    qbittorrentapi_module.Forbidden403Error = type("Forbidden403Error", (Exception,), {})
    qbittorrentapi_module.Unauthorized401Error = type("Unauthorized401Error", (Exception,), {})
    qbittorrentapi_module.Client = object
    qbittorrentapi_client_module.Client = object
    qbittorrentapi_transfer_module.TransferInfoDictionary = dict

    app_module.core = core_module
    app_module.log = log_module
    app_module.modules = modules_module
    app_module.schemas = schemas_module
    app_module.utils = utils_module
    core_module.cache = cache_module
    core_module.config = config_module
    core_module.metainfo = metainfo_module
    utils_module.string = string_module
    schemas_module.types = schema_types_module
    modules_module.qbittorrent = qbittorrent_package_module

    stub_modules = {
        "app": app_module,
        "app.core": core_module,
        "app.core.cache": cache_module,
        "app.core.config": config_module,
        "app.core.metainfo": metainfo_module,
        "app.log": log_module,
        "app.modules": modules_module,
        "app.modules.qbittorrent": qbittorrent_package_module,
        "app.schemas": schemas_module,
        "app.schemas.types": schema_types_module,
        "app.utils": utils_module,
        "app.utils.string": string_module,
        "qbittorrentapi": qbittorrentapi_module,
        "qbittorrentapi.client": qbittorrentapi_client_module,
        "qbittorrentapi.transfer": qbittorrentapi_transfer_module,
    }

    for stub_module in stub_modules.values():
        stub_module._qbittorrent_test_stub = True

    qbittorrent_path = repo_root / "app" / "modules" / "qbittorrent" / "qbittorrent.py"
    qbittorrent_spec = importlib.util.spec_from_file_location(
        "app.modules.qbittorrent.qbittorrent",
        qbittorrent_path,
    )
    qbittorrent_module = importlib.util.module_from_spec(qbittorrent_spec)
    assert qbittorrent_spec and qbittorrent_spec.loader

    module_path = repo_root / "app" / "modules" / "qbittorrent" / "__init__.py"
    qbittorrent_module_spec = importlib.util.spec_from_file_location(
        "_test_qbittorrent_module",
        module_path,
    )
    module_package = importlib.util.module_from_spec(qbittorrent_module_spec)
    assert qbittorrent_module_spec and qbittorrent_module_spec.loader

    with patch.dict(sys.modules, stub_modules):
        sys.modules[qbittorrent_spec.name] = qbittorrent_module
        qbittorrent_spec.loader.exec_module(qbittorrent_module)
        qbittorrent_package_module.qbittorrent = qbittorrent_module
        qbittorrent_module_spec.loader.exec_module(module_package)

    return qbittorrent_module, module_package


qbittorrent_module, qbittorrent_package_module = _load_qbittorrent_modules()
Qbittorrent = qbittorrent_module.Qbittorrent
QbittorrentModule = qbittorrent_package_module.QbittorrentModule


def test_init_does_not_block_on_qbittorrent_login():
    """qBittorrent 首次连接缓慢时，模块构造不得阻塞应用启动。"""
    login_started = threading.Event()
    release_login = threading.Event()
    fake_client = MagicMock()

    def slow_login(*_args, **_kwargs):
        login_started.set()
        release_login.wait(1)
        return fake_client

    with patch.object(Qbittorrent, "_Qbittorrent__login_qbittorrent", side_effect=slow_login):
        started_at = time.monotonic()
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")
        elapsed = time.monotonic() - started_at

        assert elapsed < 0.5
        assert login_started.wait(0.5)
        release_login.set()
        assert downloader.qbc is fake_client


def test_reconnect_waits_for_initial_qbittorrent_login():
    """启动中的首次登录与定时重连必须串行完成，不能相互覆盖或死锁。"""
    login_started = threading.Event()
    release_login = threading.Event()
    first_client = MagicMock(name="first-client")
    reconnected_client = MagicMock(name="reconnected-client")
    login_count = 0
    login_count_lock = threading.Lock()

    def slow_first_login(*_args, **_kwargs):
        nonlocal login_count
        with login_count_lock:
            login_count += 1
            is_first_login = login_count == 1
        if is_first_login:
            login_started.set()
            release_login.wait(1)
            return first_client
        return reconnected_client

    with patch.object(Qbittorrent, "_Qbittorrent__login_qbittorrent", side_effect=slow_first_login):
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")
        assert login_started.wait(1)
        reconnect_thread = threading.Thread(target=downloader.reconnect, daemon=True)
        reconnect_thread.start()
        release_login.set()
        reconnect_thread.join(2)

        assert not reconnect_thread.is_alive()
        assert downloader.qbc is reconnected_client


def test_login_uses_api_key_header_without_auth_login():
    """API Key 登录时应使用 Bearer Header 并跳过用户名密码登录。"""
    fake_client = MagicMock()
    fake_client.app_version.return_value = "v5.2.0"

    with patch.object(qbittorrent_module.qbittorrentapi, "Client", return_value=fake_client) as client_cls:
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, apikey="secret-token")

    assert downloader.qbc is fake_client
    fake_client.auth_log_in.assert_not_called()
    fake_client.app_version.assert_called_once_with()
    assert client_cls.call_args.kwargs["EXTRA_HEADERS"] == {"Authorization": "Bearer secret-token"}


def test_login_enables_incomplete_file_suffix_by_default():
    """
    登录成功后默认开启未完成文件后缀，避免下载中的媒体文件被提前整理。
    """
    fake_client = MagicMock()
    fake_client.app_preferences.return_value = {"incomplete_files_ext": False}

    with patch.object(qbittorrent_module.qbittorrentapi, "Client", return_value=fake_client):
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")

    assert downloader.qbc is fake_client
    fake_client.app_set_preferences.assert_called_once_with({"incomplete_files_ext": True})


def test_login_disables_incomplete_file_suffix_when_configured():
    """
    用户关闭配置后应同步关闭 qBittorrent 未完成文件后缀偏好。
    """
    fake_client = MagicMock()
    fake_client.app_preferences.return_value = {"incomplete_files_ext": True}

    with patch.object(qbittorrent_module.qbittorrentapi, "Client", return_value=fake_client):
        downloader = Qbittorrent(
            host="http://127.0.0.1",
            port=8080,
            username="admin",
            password="adminadmin",
            incomplete_files_ext=False,
        )

    assert downloader.qbc is fake_client
    fake_client.app_set_preferences.assert_called_once_with({"incomplete_files_ext": False})


def test_login_skips_incomplete_file_suffix_when_already_matches():
    """
    远端未完成文件后缀状态已匹配配置时不重复写入全局偏好。
    """
    fake_client = MagicMock()
    fake_client.app_preferences.return_value = {"incomplete_files_ext": True}

    with patch.object(qbittorrent_module.qbittorrentapi, "Client", return_value=fake_client):
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")

    assert downloader.qbc is fake_client
    fake_client.app_set_preferences.assert_not_called()


def test_completed_status_includes_qbittorrent_finished_upload_states():
    """
    qBittorrent 按完成状态查询时应包含非下载中、非暂停的上传侧状态。
    """
    server = MagicMock()
    server.get_torrents.return_value = (
        [
            {
                "name": "QB Done",
                "content_path": "/downloads/QB Done",
                "hash": "hash-qb",
                "total_size": 1024,
                "completed": 1024,
                "progress": 1,
                "state": "stalledUP",
                "tags": "moviepilot-tag",
                "dlspeed": 0,
                "upspeed": 128,
            },
            {
                "name": "QB Downloading",
                "content_path": "/downloads/QB Downloading",
                "hash": "hash-downloading",
                "total_size": 2048,
                "completed": 1024,
                "progress": 0.5,
                "state": "queuedDL",
                "tags": "moviepilot-tag",
                "dlspeed": 64,
                "upspeed": 0,
            },
        ],
        False,
    )
    module = QbittorrentModule.__new__(QbittorrentModule)
    module.get_instances = MagicMock(return_value={"qb": server})
    module.normalize_return_path = MagicMock(side_effect=lambda path, _name: str(path))

    torrents = module.list_torrents(status="completed")

    assert [torrent.hash for torrent in torrents] == ["hash-qb"]
    assert torrents[0].state == "completed"
    server.get_torrents.assert_called_once_with(tags="moviepilot-tag")


def test_get_completed_torrents_includes_finished_stopped_tasks():
    """
    已完成但不再做种的 qBittorrent 任务仍应进入待整理列表。
    """
    fake_client = MagicMock()
    fake_client.torrents_info.return_value = [
        {
            "hash": "hash-stalled-up",
            "progress": 1,
            "amount_left": 0,
            "state": "stalledUP",
        },
        {
            "hash": "hash-stopped-up",
            "progress": 1,
            "amount_left": 0,
            "state": "stoppedUP",
        },
        {
            "hash": "hash-moving",
            "progress": 1,
            "amount_left": 0,
            "state": "moving",
        },
        {
            "hash": "hash-metadata",
            "progress": 0,
            "amount_left": 0,
            "state": "metaDL",
        },
        {
            "hash": "hash-download-left",
            "progress": 0.9,
            "amount_left": 1024,
            "state": "stalledDL",
        },
    ]

    with patch.object(Qbittorrent, "_Qbittorrent__login_qbittorrent", return_value=fake_client):
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")

    torrents = downloader.get_completed_torrents()

    assert [torrent["hash"] for torrent in torrents] == ["hash-stalled-up", "hash-stopped-up"]
    fake_client.torrents_info.assert_called_once_with(torrent_hashes=None, status_filter="completed")


def test_list_torrents_include_all_tags_removes_builtin_tag_filter():
    """
    需要查询外部手动添加的任务时，qBittorrent 查询应取消内置标签过滤。
    """
    server = MagicMock()
    server.get_torrents.return_value = (
        [
            {
                "name": "External Task",
                "content_path": "/downloads/External Task",
                "hash": "hash-external",
                "total_size": 1024,
                "completed": 1024,
                "progress": 1,
                "state": "stalledUP",
                "tags": "external",
                "dlspeed": 0,
                "upspeed": 0,
            }
        ],
        False,
    )
    module = QbittorrentModule.__new__(QbittorrentModule)
    module.get_instances = MagicMock(return_value={"qb": server})
    module.normalize_return_path = MagicMock(side_effect=lambda path, _name: str(path))

    torrents = module.list_torrents(include_all_tags=True)

    assert [torrent.hash for torrent in torrents] == ["hash-external"]
    server.get_torrents.assert_called_once_with(tags=None)

def test_get_files_retries_until_qbittorrent_files_available():
    """qBittorrent 任务文件列表短暂未就绪时应重试。"""
    torrent_files = [{"id": 12, "name": "Show.S01E12.mkv"}]
    fake_client = MagicMock()
    fake_client.torrents_files.side_effect = [
        Exception("Torrent hash(es): abc123"),
        torrent_files,
    ]

    with patch.object(Qbittorrent, "_Qbittorrent__login_qbittorrent", return_value=fake_client):
        downloader = Qbittorrent(host="http://127.0.0.1", port=8080, username="admin", password="adminadmin")

    with patch.object(qbittorrent_module.time, "sleep") as sleep:
        result = downloader.get_files("abc123", retry=2, interval=1)

    assert result == torrent_files
    assert fake_client.torrents_files.call_count == 2
    fake_client.torrents_files.assert_called_with(torrent_hash="abc123")
    sleep.assert_called_once_with(1)
