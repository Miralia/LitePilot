from typing import Any

from app.core.config import settings


def test_update_float_setting_accepts_json_integer(monkeypatch) -> None:
    """浮点配置应接受 JSON 整数并按浮点值持久化。"""
    persisted: dict[str, Any] = {}

    def persist_setting(
        field_name: str,
        original_value: Any,
        converted_value: Any,
    ) -> tuple[bool, None]:
        """记录待持久化配置，避免测试写入真实配置文件。"""
        persisted.update(
            field_name=field_name,
            original_value=original_value,
            converted_value=converted_value,
        )
        return True, None

    monkeypatch.setattr(settings, "WRITE_TIMEOUT", 3.0)
    monkeypatch.setattr(
        type(settings),
        "update_env_config",
        staticmethod(persist_setting),
    )

    success, message = settings.update_setting("WRITE_TIMEOUT", 1)

    assert success is True
    assert message is None
    assert settings.WRITE_TIMEOUT == 1.0
    assert isinstance(settings.WRITE_TIMEOUT, float)
    assert persisted == {
        "field_name": "WRITE_TIMEOUT",
        "original_value": 1,
        "converted_value": 1.0,
    }


def test_validate_api_token_does_not_log_generated_secret(monkeypatch) -> None:
    """自动生成 API_TOKEN 时日志不得泄露 token 原文。"""
    messages: list[str] = []
    monkeypatch.setattr("app.core.config.logger.info", messages.append)
    monkeypatch.setattr("app.core.config.logger.warning", messages.append)

    generated_token, needs_update = settings.validate_api_token("", "")

    assert needs_update is True
    assert isinstance(generated_token, str)
    assert len(generated_token) >= 16
    assert messages
    assert generated_token not in "".join(messages)


def test_repo_specific_github_headers_are_removed() -> None:
    """仓库级 GitHub 令牌属于已移除的上游插件市场残留。"""
    assert not hasattr(settings, "REPO_GITHUB_HEADERS")
    assert "REPO_GITHUB_TOKEN" not in type(settings).model_fields


def test_update_setting_replaces_unsupported_recognize_source(monkeypatch) -> None:
    """已移除的识别源配置应自动回退到可执行的TMDB源。"""
    persisted: dict[str, Any] = {}

    def persist_setting(
        field_name: str,
        original_value: Any,
        converted_value: Any,
    ) -> tuple[bool, None]:
        """记录待持久化配置，避免测试写入真实配置文件。"""
        persisted.update(
            field_name=field_name,
            original_value=original_value,
            converted_value=converted_value,
        )
        return True, None

    monkeypatch.setattr(settings, "RECOGNIZE_SOURCE", "themoviedb")
    monkeypatch.setattr(
        type(settings),
        "update_env_config",
        staticmethod(persist_setting),
    )

    success, _ = settings.update_setting("RECOGNIZE_SOURCE", "douban")

    assert success is True
    assert settings.RECOGNIZE_SOURCE == "themoviedb"
    assert persisted["converted_value"] == "themoviedb"


def test_media_source_setting_filters_unsupported_search_sources() -> None:
    """搜索源列表应过滤无集成模块的来源，并保留有效来源顺序。"""
    converted, needs_update = settings.validate_media_source_setting(
        "SEARCH_SOURCE", "douban,bangumi,unknown,themoviedb"
    )

    assert converted == "bangumi,themoviedb"
    assert needs_update is True


def test_media_source_setting_accepts_supported_sources() -> None:
    """当前支持的TMDB与Bangumi配置不应被改写。"""
    converted, needs_update = settings.validate_media_source_setting(
        "SEARCH_SOURCE", "themoviedb,bangumi"
    )

    assert converted == "themoviedb,bangumi"
    assert needs_update is False


def test_security_image_domains_follow_active_media_sources() -> None:
    """图片代理默认白名单不应保留已移除上游数据源的域名。"""
    field = type(settings).model_fields["SECURITY_IMAGE_DOMAINS"]
    assert field.default == [
        "image.tmdb.org",
        "images.tmdb.org",
        "bing.com",
        "doubanio.com",
        "lain.bgm.tv",
    ]


def test_removed_feishu_notification_settings_are_not_retained() -> None:
    """飞书通知模块已删除，配置层不应继续暴露其密钥与事件回调字段。"""
    for field_name in (
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_OPEN_ID",
        "FEISHU_CHAT_ID",
        "FEISHU_ADMINS",
        "FEISHU_VERIFICATION_TOKEN",
        "FEISHU_ENCRYPT_KEY",
    ):
        assert field_name not in type(settings).model_fields
