"""Webhook 事件 schema 与解析边界测试。"""

import json
from unittest.mock import Mock

from app import schemas
from app.modules.emby.emby import Emby


ACTIVE_WEBHOOK_EVENT_FIELDS = {
    "event",
    "server_name",
    "item_type",
    "item_name",
    "item_path",
    "season_id",
    "episode_id",
    "tmdb_id",
    "json_object",
}


def test_webhook_event_schema_only_keeps_active_delete_contract():
    """Webhook 事件只保留联动删除消费者实际使用的字段。"""
    assert set(schemas.WebhookEventInfo.model_fields) == ACTIVE_WEBHOOK_EVENT_FIELDS


def test_emby_webhook_does_not_hydrate_unused_playback_metadata():
    """播放进度、会话与通知图片没有消费者，解析时不能额外请求 Emby 图片接口。"""
    server = object.__new__(Emby)
    server.get_remote_image_by_id = Mock(return_value="https://image.example/backdrop.jpg")
    payload = {
        "Event": "playback.start",
        "User": {"Name": "admin"},
        "Session": {
            "RemoteEndPoint": "192.168.1.10",
            "DeviceName": "Browser",
            "Client": "Emby Web",
        },
        "PlaybackInfo": {"PositionTicks": 50},
        "Item": {
            "Type": "Movie",
            "Name": "测试电影",
            "ProductionYear": 2026,
            "Id": "item-1",
            "Path": "/media/movie.mkv",
            "RunTimeTicks": 100,
            "ProviderIds": {"Tmdb": "123"},
            "Overview": "简介",
        },
    }

    info = Emby.get_webhook_message(server, form={"data": json.dumps(payload)}, args={})

    assert info is not None
    assert info.event == "playback.start"
    assert info.item_name == "测试电影 (2026)"
    assert info.item_path == "/media/movie.mkv"
    assert info.tmdb_id == "123"
    server.get_remote_image_by_id.assert_not_called()
    for field in (
        "item_id",
        "overview",
        "percentage",
        "ip",
        "device_name",
        "client",
        "user_name",
        "image_url",
        "item_favorite",
        "save_reason",
        "item_isvirtual",
        "media_type",
        "channel",
    ):
        assert field not in schemas.WebhookEventInfo.model_fields


def test_emby_webhook_normalizes_numeric_episode_zero_ids_to_strings():
    """WebhookEventInfo 的季集契约是字符串，原生 int 0 也必须保留并规范化。"""
    server = object.__new__(Emby)
    payload = {
        "Event": "deep.delete",
        "Item": {
            "Type": "Episode",
            "SeriesName": "Show",
            "Name": "Special",
            "ParentIndexNumber": 0,
            "IndexNumber": 0,
            "Path": "/media/Show/S00/episode0.mkv",
            "ProviderIds": {"Tmdb": "123"},
        },
    }

    info = Emby.get_webhook_message(server, form={"data": json.dumps(payload)}, args={})

    assert info is not None
    assert info.season_id == "0"
    assert info.episode_id == "0"
    assert isinstance(info.season_id, str)
    assert isinstance(info.episode_id, str)
