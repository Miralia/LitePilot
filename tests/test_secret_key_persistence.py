"""认证与资源签名密钥的跨重启持久化测试。"""

from dotenv import dotenv_values

from app.core.config import Settings
from app.utils.system import SystemUtils

_SECRET_KEY_NAMES = ("SECRET_KEY", "RESOURCE_SECRET_KEY")


def _scrub_secret_keys(env_path) -> None:
    """从测试 env 文件中移除密钥行，模拟首次启动或旧安装。"""
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    retained = [
        line for line in lines
        if not any(line.startswith(f"{key}=") for key in _SECRET_KEY_NAMES)
    ]
    env_path.write_text("\n".join(retained) + ("\n" if retained else ""), encoding="utf-8")


def test_generated_secret_keys_are_persisted_for_future_processes(monkeypatch) -> None:
    """未显式配置密钥时，随机生成值必须落盘，避免重启使 JWT 与资源签名全部失效。"""
    env_path = SystemUtils.get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    original_content = env_path.read_bytes() if env_path.exists() else None
    for key in _SECRET_KEY_NAMES:
        monkeypatch.delenv(key, raising=False)

    try:
        _scrub_secret_keys(env_path)
        first = Settings()
        persisted = dotenv_values(env_path)

        for key in _SECRET_KEY_NAMES:
            assert persisted.get(key) == getattr(first, key)
            assert len(persisted.get(key) or "") >= 32

        second = Settings()
        assert second.SECRET_KEY == first.SECRET_KEY
        assert second.RESOURCE_SECRET_KEY == first.RESOURCE_SECRET_KEY
    finally:
        if original_content is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_bytes(original_content)


def test_environment_secret_keys_are_not_written_to_env_file(monkeypatch) -> None:
    """进程环境显式注入的密钥优先生效，不得被复制到 app.env 扩大持久化面。"""
    env_path = SystemUtils.get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    original_content = env_path.read_bytes() if env_path.exists() else None
    monkeypatch.setenv("SECRET_KEY", "environment-secret-key-32-bytes")
    monkeypatch.setenv("RESOURCE_SECRET_KEY", "environment-resource-key-32-bytes")

    try:
        _scrub_secret_keys(env_path)
        instance = Settings()
        persisted = dotenv_values(env_path)

        assert instance.SECRET_KEY == "environment-secret-key-32-bytes"
        assert instance.RESOURCE_SECRET_KEY == "environment-resource-key-32-bytes"
        assert "SECRET_KEY" not in persisted
        assert "RESOURCE_SECRET_KEY" not in persisted
    finally:
        if original_content is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_bytes(original_content)
