"""原生 deploy 命令的配置目录持久化契约测试。"""

from click.testing import CliRunner

from tests.test_cli_auto_update import load_cli_module


def _load_deploy_module(tmp_path):
    """加载使用临时仓库根目录的 CLI 模块。"""
    module = load_cli_module()
    root = tmp_path / "repo"
    root.mkdir()
    module.settings.ROOT_PATH = root
    return module, root


def test_deploy_persists_config_dir_for_future_cli_commands(tmp_path):
    """实际写入部署配置时，应让后续 CLI 使用同一个 CONFIG_DIR。"""
    module, root = _load_deploy_module(tmp_path)
    service_dir = tmp_path / "systemd"
    nginx_dir = tmp_path / "nginx"
    config_dir = tmp_path / "runtime config"

    result = CliRunner().invoke(
        module.deploy,
        [
            "--service-dir",
            str(service_dir),
            "--nginx-dir",
            str(nginx_dir),
            "--config-dir",
            str(config_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (service_dir / "litepilot.service").exists()
    assert (nginx_dir / "litepilot.conf").exists()
    assert (root / ".moviepilot.env").read_text(encoding="utf-8") == (
        f"CONFIG_DIR='{config_dir}'\n"
    )


def test_deploy_print_only_does_not_persist_config_dir(tmp_path):
    """只打印部署配置时不得改变本地 CLI 安装状态。"""
    module, root = _load_deploy_module(tmp_path)
    config_dir = tmp_path / "runtime config"

    result = CliRunner().invoke(
        module.deploy,
        [
            "--service-dir",
            str(tmp_path / "systemd"),
            "--nginx-dir",
            str(tmp_path / "nginx"),
            "--config-dir",
            str(config_dir),
            "--print-only",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (root / ".moviepilot.env").exists()


def test_deploy_uses_configured_backend_port_in_nginx(tmp_path, monkeypatch):
    """自定义后端 PORT 时，nginx 反代不得继续指向默认 3001。"""
    module, _root = _load_deploy_module(tmp_path)
    monkeypatch.setattr(module.settings, "PORT", 3009)

    result = CliRunner().invoke(
        module.deploy,
        [
            "--service-dir",
            str(tmp_path / "systemd"),
            "--nginx-dir",
            str(tmp_path / "nginx"),
            "--print-only",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "proxy_pass http://127.0.0.1:3009/api/;" in result.output
    assert "proxy_pass http://127.0.0.1:3001" not in result.output
