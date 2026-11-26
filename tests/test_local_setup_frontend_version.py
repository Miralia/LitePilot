from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "local_setup.py"


def load_local_setup_module():
    module_name = f"moviepilot_local_setup_frontend_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def local_setup_module():
    return load_local_setup_module()


def test_repo_frontend_version_reads_version_file(local_setup_module, monkeypatch, tmp_path):
    """前端产物版本继续跟随当前仓库的应用版本。"""
    (tmp_path / "version.py").write_text(
        "APP_VERSION = 'v0.0.1'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(local_setup_module, "ROOT", tmp_path)

    assert local_setup_module._repo_frontend_version() == "v0.0.1"


def test_upstream_release_and_site_resource_interfaces_are_removed(local_setup_module):
    """本地安装器不得再下载上游前端 release 或站点私有资源。"""
    for name in (
        "FRONTEND_LATEST_API",
        "FRONTEND_TAG_API",
        "RESOURCES_MAIN_ZIP",
        "_resolve_frontend_release",
        "_download_resources_dir",
        "_resolve_local_resource_dir",
        "install_resources",
    ):
        assert not hasattr(local_setup_module, name)


def test_local_node_runtime_satisfies_frontend_build_requirement(local_setup_module):
    """本地 Node 运行时必须满足仓内前端构建的最低版本要求。"""
    major, minor, _patch = (
        int(part) for part in local_setup_module.DEFAULT_NODE_VERSION.split(".")
    )
    assert (major, minor) >= (20, 19)


def test_installer_rejects_node_versions_below_frontend_requirement(
    local_setup_module,
):
    """覆盖安装 Node 版本时不得绕过仓内前端构建的最低版本约束。"""
    with pytest.raises(RuntimeError, match="20.19"):
        local_setup_module.install_node_runtime("20.12.1")

    with pytest.raises(RuntimeError, match="20.19"):
        local_setup_module.install_node_runtime("not-a-version")


def test_parser_removes_release_and_resource_options(local_setup_module):
    """安装命令只构建当前源码，不再暴露独立前端版本或站点资源入口。"""
    parser = local_setup_module.build_parser()

    install_args = parser.parse_args(["install-frontend"])
    setup_args = parser.parse_args(["setup"])
    update_args = parser.parse_args(["update", "frontend"])
    init_args = parser.parse_args(["init"])

    assert not hasattr(install_args, "version")
    assert not hasattr(setup_args, "frontend_version")
    assert not hasattr(update_args, "frontend_version")
    assert not hasattr(setup_args, "skip_resources")
    assert not hasattr(update_args, "skip_resources")
    assert not hasattr(init_args, "skip_resources")
    with pytest.raises(SystemExit):
        parser.parse_args(["install-resources"])


def test_build_frontend_from_source_uses_local_node_and_copies_dist(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """前端安装应从仓内 web/ 源码构建，而不是下载远程发布包。"""
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    public_dir = tmp_path / "public"
    node_bin = tmp_path / "node" / "bin" / "node"
    corepack_bin = tmp_path / "node" / "bin" / "corepack"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("", encoding="utf-8")
    corepack_bin.write_text("", encoding="utf-8")
    commands = []

    def fake_run(command, cwd=None, env=None, safe_command=None):
        commands.append({
            "command": command,
            "cwd": cwd,
            "env": env,
        })
        if "build" in command:
            dist_dir = web_dir / "dist"
            dist_dir.mkdir(exist_ok=True)
            (dist_dir / "index.html").write_text("built", encoding="utf-8")

    monkeypatch.setattr(local_setup_module, "WEB_DIR", web_dir)
    monkeypatch.setattr(local_setup_module, "WEB_DIST_DIR", web_dir / "dist")
    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "get_node_bin", lambda: node_bin)
    monkeypatch.setattr(local_setup_module, "get_corepack_bin", lambda: corepack_bin)
    monkeypatch.setattr(local_setup_module, "run", fake_run)

    local_setup_module.build_frontend_from_source()

    assert (public_dir / "index.html").read_text(encoding="utf-8") == "built"
    assert [item["command"] for item in commands] == [
        [str(corepack_bin), "yarn", "install", "--frozen-lockfile"],
        [str(corepack_bin), "yarn", "build"],
    ]
    assert all(item["cwd"] == web_dir for item in commands)
    assert all(
        item["env"]["PATH"].split(":")[0] == str(node_bin.parent)
        for item in commands
    )
    assert all(
        item["env"]["COREPACK_ENABLE_DOWNLOAD_PROMPT"] == "0"
        for item in commands
    )


def test_build_frontend_from_source_retains_only_previous_hashed_assets(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """更新前端时应保留上一代 hash 资产供已打开页面加载，并淘汰更早一代。"""
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    public_dir = tmp_path / "public"
    assets_dir = public_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "chunk-current-oldhash.js").write_text("current old", encoding="utf-8")
    (assets_dir / "chunk-obsolete-olderhash.js").write_text("obsolete", encoding="utf-8")
    (public_dir / ".asset-generation.json").write_text(
        json.dumps({"current": ["assets/chunk-current-oldhash.js"]}),
        encoding="utf-8",
    )
    node_bin = tmp_path / "node" / "bin" / "node"
    corepack_bin = tmp_path / "node" / "bin" / "corepack"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("", encoding="utf-8")
    corepack_bin.write_text("", encoding="utf-8")

    def fake_run(command, cwd=None, env=None, safe_command=None):
        if "build" in command:
            dist_assets = web_dir / "dist" / "assets"
            dist_assets.mkdir(parents=True, exist_ok=True)
            (web_dir / "dist" / "index.html").write_text("built", encoding="utf-8")
            (dist_assets / "chunk-new-newhash.js").write_text("new", encoding="utf-8")

    monkeypatch.setattr(local_setup_module, "WEB_DIR", web_dir)
    monkeypatch.setattr(local_setup_module, "WEB_DIST_DIR", web_dir / "dist")
    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "get_node_bin", lambda: node_bin)
    monkeypatch.setattr(local_setup_module, "get_corepack_bin", lambda: corepack_bin)
    monkeypatch.setattr(local_setup_module, "run", fake_run)

    local_setup_module.build_frontend_from_source()

    assert (assets_dir / "chunk-new-newhash.js").read_text(encoding="utf-8") == "new"
    assert (assets_dir / "chunk-current-oldhash.js").read_text(encoding="utf-8") == "current old"
    assert not (assets_dir / "chunk-obsolete-olderhash.js").exists()
    state = json.loads((public_dir / ".asset-generation.json").read_text(encoding="utf-8"))
    assert state == {"current": ["assets/chunk-new-newhash.js"]}


def test_build_frontend_from_source_migrates_assets_without_generation_state(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """无代际清单的历史安装首次升级时应把现有 assets 全部视为上一代保留。"""
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    public_dir = tmp_path / "public"
    assets_dir = public_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "chunk-legacy-oldhash.js").write_text("legacy", encoding="utf-8")
    node_bin = tmp_path / "node" / "bin" / "node"
    corepack_bin = tmp_path / "node" / "bin" / "corepack"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("", encoding="utf-8")
    corepack_bin.write_text("", encoding="utf-8")

    def fake_run(command, cwd=None, env=None, safe_command=None):
        if "build" in command:
            dist_assets = web_dir / "dist" / "assets"
            dist_assets.mkdir(parents=True, exist_ok=True)
            (web_dir / "dist" / "index.html").write_text("built", encoding="utf-8")
            (dist_assets / "chunk-new-newhash.js").write_text("new", encoding="utf-8")

    monkeypatch.setattr(local_setup_module, "WEB_DIR", web_dir)
    monkeypatch.setattr(local_setup_module, "WEB_DIST_DIR", web_dir / "dist")
    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "get_node_bin", lambda: node_bin)
    monkeypatch.setattr(local_setup_module, "get_corepack_bin", lambda: corepack_bin)
    monkeypatch.setattr(local_setup_module, "run", fake_run)

    local_setup_module.build_frontend_from_source()

    assert (assets_dir / "chunk-legacy-oldhash.js").read_text(encoding="utf-8") == "legacy"
    assert (assets_dir / "chunk-new-newhash.js").read_text(encoding="utf-8") == "new"
    state = json.loads((public_dir / ".asset-generation.json").read_text(encoding="utf-8"))
    assert state == {"current": ["assets/chunk-new-newhash.js"]}


def test_install_frontend_writes_local_runtime_without_remote_download(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """前端运行时应由本地构建产物、受控 service.js 与运行依赖组成。"""
    public_dir = tmp_path / "public"
    node_bin = tmp_path / "node" / "bin" / "node"
    npm_bin = tmp_path / "node" / "bin" / "npm"
    npm_bin.parent.mkdir(parents=True)
    npm_bin.write_text("", encoding="utf-8")
    commands = []

    def fake_build():
        public_dir.mkdir(parents=True, exist_ok=True)
        (public_dir / "index.html").write_text("built", encoding="utf-8")

    def fake_run(command, cwd=None, env=None, safe_command=None):
        commands.append({"command": command, "cwd": cwd})

    def fail_download(*args, **kwargs):
        raise AssertionError("不得下载远程前端或资源包")

    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "_repo_frontend_version", lambda: "v9.9.9")
    monkeypatch.setattr(local_setup_module, "install_node_runtime", lambda _version: node_bin)
    monkeypatch.setattr(local_setup_module, "get_npm_bin", lambda: npm_bin)
    monkeypatch.setattr(local_setup_module, "build_frontend_from_source", fake_build)
    monkeypatch.setattr(local_setup_module, "run", fake_run)
    monkeypatch.setattr(local_setup_module, "download_file", fail_download)

    result = local_setup_module.install_frontend(
        node_version=local_setup_module.DEFAULT_NODE_VERSION
    )

    assert result == {"version": "v9.9.9", "node": str(node_bin)}
    assert (public_dir / "version.txt").read_text(encoding="utf-8") == "v9.9.9"
    service_script = (public_dir / "service.js").read_text(encoding="utf-8")
    assert "startBackendWatchdog" in service_script
    assert "MOVIEPILOT_FRONTEND_HEALTH_INTERVAL_MS" in service_script
    runtime_package = json.loads(
        (public_dir / "package.json").read_text(encoding="utf-8")
    )
    assert runtime_package["dependencies"] == {
        "express": "4.22.3",
        "express-http-proxy": "2.1.1",
    }
    assert commands == [
        {
            "command": [
                str(npm_bin),
                "install",
                "--no-fund",
                "--no-audit",
                "--omit=dev",
            ],
            "cwd": public_dir,
        }
    ]
