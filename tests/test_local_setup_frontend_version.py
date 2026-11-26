from __future__ import annotations

import importlib.util
import json
import os
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


def test_linux_node_archive_uses_gzip_when_python_lacks_lzma(
    local_setup_module,
    monkeypatch,
):
    """精简编译的 Python 缺少 lzma 时，Linux Node 包应回退到 gzip 格式。"""
    monkeypatch.setattr(local_setup_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(local_setup_module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(local_setup_module, "_lzma_available", lambda: False, raising=False)

    assert local_setup_module._node_platform() == ("linux-x64", "tar.gz")

    monkeypatch.setattr(local_setup_module, "_lzma_available", lambda: True)
    assert local_setup_module._node_platform() == ("linux-x64", "tar.xz")


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


def test_build_frontend_update_preserves_existing_runtime_files(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """前端更新不得在替换阶段删除独立 Node 服务文件或其它运行时文件。"""
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    public_dir = tmp_path / "public"
    assets_dir = public_dir / "assets"
    node_runtime = public_dir / "node_modules" / "express"
    node_runtime.mkdir(parents=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "chunk-old-hash.js").write_text("old", encoding="utf-8")
    (public_dir / "service.js").write_text("runtime service", encoding="utf-8")
    (node_runtime / "index.js").write_text("express runtime", encoding="utf-8")
    node_bin = tmp_path / "node" / "bin" / "node"
    corepack_bin = tmp_path / "node" / "bin" / "corepack"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("", encoding="utf-8")
    corepack_bin.write_text("", encoding="utf-8")

    def fake_run(command, cwd=None, env=None, safe_command=None):
        if "build" in command:
            dist_assets = web_dir / "dist" / "assets"
            dist_assets.mkdir(parents=True, exist_ok=True)
            (web_dir / "dist" / "index.html").write_text("new index", encoding="utf-8")
            (dist_assets / "chunk-new-hash.js").write_text("new", encoding="utf-8")

    monkeypatch.setattr(local_setup_module, "WEB_DIR", web_dir)
    monkeypatch.setattr(local_setup_module, "WEB_DIST_DIR", web_dir / "dist")
    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "get_node_bin", lambda: node_bin)
    monkeypatch.setattr(local_setup_module, "get_corepack_bin", lambda: corepack_bin)
    monkeypatch.setattr(local_setup_module, "run", fake_run)

    local_setup_module.build_frontend_from_source()

    assert (public_dir / "service.js").read_text(encoding="utf-8") == "runtime service"
    assert (node_runtime / "index.js").read_text(encoding="utf-8") == "express runtime"


def test_build_frontend_copies_assets_before_index(
    local_setup_module,
    monkeypatch,
    tmp_path,
):
    """入口 HTML 必须最后更新，避免新入口引用尚未复制完成的懒加载 chunk。"""
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    node_bin = tmp_path / "node" / "bin" / "node"
    corepack_bin = tmp_path / "node" / "bin" / "corepack"
    node_bin.parent.mkdir(parents=True)
    node_bin.write_text("", encoding="utf-8")
    corepack_bin.write_text("", encoding="utf-8")
    copied_files = []

    def fake_run(command, cwd=None, env=None, safe_command=None):
        if "build" in command:
            dist_assets = web_dir / "dist" / "assets"
            dist_assets.mkdir(parents=True, exist_ok=True)
            (web_dir / "dist" / "index.html").write_text("new index", encoding="utf-8")
            (web_dir / "dist" / "service-worker.js").write_text("sw", encoding="utf-8")
            (dist_assets / "chunk-new-hash.js").write_text("new", encoding="utf-8")

    def record_copy(source, target):
        copied_files.append(target.relative_to(public_dir).as_posix())

    replaced_targets = []
    real_replace = os.replace

    def record_replace(source, target):
        replaced_targets.append(Path(target).name)
        return real_replace(source, target)

    monkeypatch.setattr(local_setup_module.os, "replace", record_replace)
    monkeypatch.setattr(local_setup_module, "WEB_DIR", web_dir)
    monkeypatch.setattr(local_setup_module, "WEB_DIST_DIR", web_dir / "dist")
    monkeypatch.setattr(local_setup_module, "PUBLIC_DIR", public_dir)
    monkeypatch.setattr(local_setup_module, "get_node_bin", lambda: node_bin)
    monkeypatch.setattr(local_setup_module, "get_corepack_bin", lambda: corepack_bin)
    monkeypatch.setattr(local_setup_module, "run", fake_run)
    monkeypatch.setattr(local_setup_module, "_copy_frontend_file", record_copy, raising=False)

    local_setup_module.build_frontend_from_source()

    assert copied_files[-1] == "index.html"
    assert copied_files.index("assets/chunk-new-hash.js") < copied_files.index("index.html")
    assert ".asset-generation.json" in replaced_targets


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

    replaced_targets = []
    real_replace = os.replace

    def record_replace(source, target):
        replaced_targets.append(Path(target).name)
        return real_replace(source, target)

    monkeypatch.setattr(local_setup_module.os, "replace", record_replace)
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
    assert {"version.txt", "service.js", "package.json"}.issubset(set(replaced_targets))
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


def test_publish_frontend_dist_retains_previous_hashed_assets(local_setup_module, tmp_path):
    """独立构建脚本复用的发布函数不得清空 public，并应保留上一代 hash 资产。"""
    dist_dir = tmp_path / "dist"
    dist_assets = dist_dir / "assets"
    dist_assets.mkdir(parents=True)
    (dist_dir / "index.html").write_text("new entry", encoding="utf-8")
    (dist_assets / "chunk-new.js").write_text("new chunk", encoding="utf-8")

    public_dir = tmp_path / "public"
    public_assets = public_dir / "assets"
    public_assets.mkdir(parents=True)
    (public_dir / "index.html").write_text("old entry", encoding="utf-8")
    (public_assets / "chunk-previous.js").write_text("previous chunk", encoding="utf-8")
    (public_assets / "chunk-obsolete.js").write_text("obsolete chunk", encoding="utf-8")
    (public_dir / ".asset-generation.json").write_text(
        json.dumps({"current": ["assets/chunk-previous.js"]}),
        encoding="utf-8",
    )

    local_setup_module.publish_frontend_dist(dist_dir, public_dir)

    assert (public_dir / "index.html").read_text(encoding="utf-8") == "new entry"
    assert (public_assets / "chunk-new.js").read_text(encoding="utf-8") == "new chunk"
    assert (public_assets / "chunk-previous.js").read_text(encoding="utf-8") == "previous chunk"
    assert not (public_assets / "chunk-obsolete.js").exists()


def test_build_frontend_script_uses_atomic_dist_publisher() -> None:
    """手动构建脚本不得通过清空 public 制造静态资产空窗。"""
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "build-frontend.sh"
    ).read_text(encoding="utf-8")

    assert "publish_frontend_dist" in script
    assert 'find "$DIST_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf' not in script


def test_build_frontend_script_prefers_repository_node_runtime() -> None:
    """手动构建脚本不得回退到系统 Node；当前依赖要求 Node 22+。"""
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "build-frontend.sh"
    ).read_text(encoding="utf-8")

    assert 'LOCAL_NODE_BIN_DIR="$PROJECT_ROOT/.runtime/node/bin"' in script
    local_corepack_branch = 'if [[ -x "$LOCAL_NODE_BIN_DIR/node" && -x "$LOCAL_NODE_BIN_DIR/corepack" ]]; then'
    assert local_corepack_branch in script
    assert script.index(local_corepack_branch) < script.index('if command -v yarn')
