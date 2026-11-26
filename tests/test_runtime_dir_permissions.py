"""运行时配置目录权限测试。"""

import os

import pytest

from app.core.config import Settings


@pytest.mark.skipif(os.name == "nt", reason="Windows POSIX 权限语义不同")
def test_settings_enforces_private_runtime_directories(tmp_path, monkeypatch) -> None:
    """运行时目录可能包含认证状态、缓存索引与下载内容，不得由本机其它账户改写。"""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32-bytes")
    monkeypatch.setenv("RESOURCE_SECRET_KEY", "test-resource-key-32-bytes")
    config_dir = tmp_path / "config"
    for path in [
        config_dir,
        config_dir / "temp",
        config_dir / "logs",
        config_dir / "cookies",
        config_dir / "cache",
    ]:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o777)

    instance = Settings(CONFIG_DIR=str(config_dir))

    for path in [
        instance.CONFIG_PATH,
        instance.TEMP_PATH,
        instance.LOG_PATH,
        instance.COOKIE_PATH,
        instance.CACHE_PATH,
    ]:
        assert path.stat().st_mode & 0o777 == 0o700
