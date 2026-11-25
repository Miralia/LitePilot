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
