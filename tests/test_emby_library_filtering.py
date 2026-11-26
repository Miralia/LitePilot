"""Emby 媒体库路径过滤的离线边界测试。"""
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.modules.emby.emby import Emby


def _emby_client() -> Emby:
    """构造不触发网络初始化的 Emby 客户端对象。"""
    client = Emby.__new__(Emby)
    client._host = "http://emby.local/"
    client._playhost = "http://emby.local/"
    client._apikey = "api-key"
    client._sync_libraries = []
    client._metadata_ready = threading.Event()
    client._metadata_ready.set()
    client.user = "user-id"
    client.serverid = "server-id"
    return client


def test_resume_does_not_treat_sibling_path_as_library_child():
    """/media/movies-old 不应被误判为 /media/movies 媒体库内容。"""
    client = _emby_client()
    response = Mock()
    response.json.return_value = {
        "Items": [
            {
                "Type": "Movie",
                "Id": "outside",
                "Name": "Outside",
                "Path": "/media/movies-old/outside.mkv",
            },
            {
                "Type": "Movie",
                "Id": "inside",
                "Name": "Inside",
                "Path": "/media/movies/inside.mkv",
            },
        ]
    }

    with patch("app.modules.emby.emby.RequestUtils") as request_utils, patch.object(
        client,
        "get_user_library_folders",
        return_value=["/media/movies"],
    ), patch.object(
        client,
        "get_play_url",
        side_effect=lambda item_id, server_id=None: f"play:{item_id}",
    ):
        request_utils.return_value.get_res.return_value = response
        result = client.get_resume(num=10)

    assert [item.id for item in result] == ["inside"]


def test_virtual_folders_skip_library_without_path_infos():
    """单个媒体库缺少 PathInfos 不应导致其他媒体库解析全部失败。"""
    client = _emby_client()
    response = Mock()
    response.json.return_value = {
        "Items": [
            {"ItemId": "broken", "Name": "Broken", "LibraryOptions": {}},
            {
                "ItemId": "movies",
                "Name": "Movies",
                "LibraryOptions": {
                    "PathInfos": [{"Path": "/media/movies"}],
                },
            },
        ]
    }

    with patch("app.modules.emby.emby.RequestUtils") as request_utils:
        request_utils.return_value.get_res.return_value = response
        result = client.get_emby_virtual_folders()

    assert result == [
        {"Id": "movies", "Name": "Movies", "Path": ["/media/movies"]}
    ]


def test_user_library_folders_all_includes_every_library():
    """同步范围为 all 时应保留所有媒体库路径。"""
    client = _emby_client()
    client._sync_libraries = ["all"]
    libraries = [
        {"Id": "movies", "Name": "Movies", "Path": ["/media/movies"]},
        {"Id": "tv", "Name": "TV", "Path": ["/media/tv"]},
    ]

    with patch.object(client, "get_emby_virtual_folders", return_value=libraries):
        result = client.get_user_library_folders()

    assert result == ["/media/movies", "/media/tv"]
