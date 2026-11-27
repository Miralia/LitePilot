from app.helper.service import ServiceConfigHelper
from app.schemas.system import MediaServerConf
from app.schemas.types import SystemConfigKey


def test_mediaserver_conf_tolerates_blank_sync_interval():
    """自动同步间隔为空字符串等非法值时应回退为 None 而不是抛出校验错误。"""
    assert MediaServerConf(name="blank", sync_interval="").sync_interval is None
    assert MediaServerConf(name="spaces", sync_interval="  ").sync_interval is None
    assert MediaServerConf(name="invalid", sync_interval="abc").sync_interval is None
    assert MediaServerConf(name="text", sync_interval="12").sync_interval == 12
    assert MediaServerConf(name="number", sync_interval=6).sync_interval == 6
    assert MediaServerConf(name="none", sync_interval=None).sync_interval is None


def test_get_configs_skips_invalid_entries(monkeypatch):
    """单条配置校验失败时应跳过该条，不影响其它服务配置的加载。"""
    monkeypatch.setattr(
        "app.helper.service.SystemConfigOper.get",
        lambda self, key: [
            {"name": "good", "type": "emby", "enabled": True},
            "bad-format",
            {"name": "bad-type", "type": "plex", "enabled": "maybe"},
        ],
    )

    configs = ServiceConfigHelper.get_configs(SystemConfigKey.MediaServers, MediaServerConf)

    assert [conf.name for conf in configs] == ["good"]


def test_get_configs_does_not_log_secret_values(monkeypatch):
    """非法服务配置的诊断日志不得写入密码、API key 或原始输入值。"""
    malformed_secret = "malformed-secret"
    validation_secret = "validation-secret"
    warnings = []
    errors = []
    monkeypatch.setattr("app.helper.service.logger.warning", warnings.append)
    monkeypatch.setattr("app.helper.service.logger.error", errors.append)
    monkeypatch.setattr(
        "app.helper.service.SystemConfigOper.get",
        lambda self, key: [
            {"name": "good", "type": "emby", "enabled": True},
            f"password={malformed_secret}",
            {
                "name": "bad-config",
                "type": "emby",
                "config": f"password={validation_secret}",
            },
        ],
    )

    configs = ServiceConfigHelper.get_configs(SystemConfigKey.MediaServers, MediaServerConf)

    assert [conf.name for conf in configs] == ["good"]
    logged = "\n".join(warnings + errors)
    assert malformed_secret not in logged
    assert validation_secret not in logged
    assert "input_value" not in logged
    assert "config" in logged
