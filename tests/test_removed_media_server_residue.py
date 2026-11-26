"""已移除媒体服务器生态的残留边界测试。"""

from pathlib import Path


def test_removed_ugreen_module_has_no_manual_tooling_residue():
    """绿联模块移除后，不应保留必然无法运行的手工调试入口。"""
    assert not Path("app/modules/ugreen").exists()
    assert not Path("tests/manual/ugreen_media_cli.py").exists()


def test_system_config_has_no_ugreen_session_key_residue():
    """系统配置枚举不应保留已删除绿联集成的悬空会话缓存说明。"""
    source = Path("app/schemas/types.py").read_text(encoding="utf-8")

    assert "绿联影视登录会话缓存" not in source
    assert "Ugreen" not in source
    assert "ugreen" not in source
