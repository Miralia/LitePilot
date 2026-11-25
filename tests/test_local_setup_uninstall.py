from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "local_setup.py"


def load_local_setup_module():
    module_name = f"moviepilot_local_setup_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def prepare_install_tree(tmp_path, monkeypatch, *, legacy_config: bool = False):
    module = load_local_setup_module()

    root_dir = tmp_path / "LitePilot"
    helper_dir = root_dir / "app" / "helper"
    runtime_dir = root_dir / ".runtime"
    public_dir = root_dir / "public"
    venv_dir = root_dir / "venv"
    install_env_file = root_dir / ".moviepilot.env"
    config_dir = root_dir / "config" if legacy_config else tmp_path / "moviepilot-config"
    temp_config_dir = config_dir / "temp"

    helper_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)
    venv_dir.mkdir(parents=True)
    temp_config_dir.mkdir(parents=True)
    install_env_file.write_text("CONFIG_DIR=/tmp/moviepilot-config\n", encoding="utf-8")
    (root_dir / "moviepilot").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (helper_dir / "sites.py").write_text("generated\n", encoding="utf-8")
    (helper_dir / "user.sites.v2.bin").write_bytes(b"binary")
    (temp_config_dir / "moviepilot.runtime.json").write_text("{}", encoding="utf-8")
    (temp_config_dir / "moviepilot.frontend.runtime.json").write_text(
        "{}", encoding="utf-8"
    )

    monkeypatch.setattr(module, "ROOT", root_dir)
    monkeypatch.setattr(module, "HELPER_DIR", helper_dir)
    monkeypatch.setattr(module, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(module, "INSTALL_ENV_FILE", install_env_file)
    monkeypatch.setattr(module, "LEGACY_CONFIG_DIR", root_dir / "config")
    monkeypatch.setattr(module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(module, "TEMP_DIR", temp_config_dir)

    return module, root_dir, config_dir, venv_dir, install_env_file


def mock_uninstall_prompts(module, monkeypatch, yes_no_answers):
    answers = iter(yes_no_answers)
    monkeypatch.setattr(module, "_is_interactive", lambda: True)
    monkeypatch.setattr(
        module,
        "_prompt_yes_no",
        lambda label, default=False: next(answers),
    )
    monkeypatch.setattr(
        module,
        "_prompt_text",
        lambda label, default=None, allow_empty=False, secret=False: module.UNINSTALL_CONFIRM_TEXT,
    )
    monkeypatch.setattr(module, "_stop_managed_services", lambda venv_dir: None)


def test_remove_config_data_deletes_legacy_config_directory(tmp_path, monkeypatch):
    module, _, config_dir, _, _ = prepare_install_tree(
        tmp_path, monkeypatch, legacy_config=True
    )
    category_file = config_dir / "category.yaml"
    category_file.write_text("seed\n", encoding="utf-8")
    (config_dir / "logs").mkdir(exist_ok=True)
    (config_dir / "user.db").write_text("db\n", encoding="utf-8")

    removed = module._remove_config_data(config_dir)

    assert not config_dir.exists()
    assert not category_file.exists()
    assert str(config_dir.resolve()) in {str(path.resolve()) for path in removed}


def test_uninstall_keeps_config_by_default(tmp_path, monkeypatch):
    module, root_dir, config_dir, venv_dir, install_env_file = prepare_install_tree(
        tmp_path, monkeypatch
    )
    cli_dir = root_dir.parent / "bin"
    cli_dir.mkdir()
    cli_link = cli_dir / "moviepilot"
    cli_link.symlink_to(root_dir / "moviepilot")
    mock_uninstall_prompts(module, monkeypatch, [False, True])

    result = module.uninstall_local(
        venv_dir=venv_dir,
        config_dir=config_dir,
        launch_path=str(cli_link),
    )

    assert not result["cancelled"]
    assert config_dir.exists()
    assert install_env_file.exists()
    assert not venv_dir.exists()
    assert not (root_dir / ".runtime").exists()
    assert not (root_dir / "public").exists()
    assert not (root_dir / "app" / "helper" / "sites.py").exists()
    assert not (root_dir / "app" / "helper" / "user.sites.v2.bin").exists()
    assert not cli_link.exists()


def test_uninstall_deletes_external_config_when_requested(tmp_path, monkeypatch):
    module, _, config_dir, venv_dir, install_env_file = prepare_install_tree(
        tmp_path, monkeypatch
    )
    mock_uninstall_prompts(module, monkeypatch, [True, True])

    result = module.uninstall_local(
        venv_dir=venv_dir,
        config_dir=config_dir,
    )

    assert not result["cancelled"]
    assert result["config_deleted"]
    assert not config_dir.exists()
    assert not install_env_file.exists()


def test_uninstall_deletes_legacy_config_when_requested(tmp_path, monkeypatch):
    module, _, config_dir, venv_dir, install_env_file = prepare_install_tree(
        tmp_path, monkeypatch, legacy_config=True
    )
    (config_dir / "category.yaml").write_text("seed\n", encoding="utf-8")
    mock_uninstall_prompts(module, monkeypatch, [True, True])

    result = module.uninstall_local(
        venv_dir=venv_dir,
        config_dir=config_dir,
    )

    assert not result["cancelled"]
    assert result["config_deleted"]
    assert not config_dir.exists()
    assert not install_env_file.exists()
