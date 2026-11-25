"""本地一键安装脚本的项目来源边界测试。"""

from pathlib import Path


BOOTSTRAP_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-local.sh"
).read_text(encoding="utf-8")


def test_bootstrap_uses_litepilot_repository_and_main_branch() -> None:
    """一键安装脚本不得再克隆上游 MoviePilot 仓库。"""
    assert 'REPO_URL="https://github.com/Miralia/LitePilot.git"' in BOOTSTRAP_SCRIPT
    assert 'REPO_REF="main"' in BOOTSTRAP_SCRIPT
    assert 'APP_DIR_NAME="LitePilot"' in BOOTSTRAP_SCRIPT
    assert "jxxghp/MoviePilot" not in BOOTSTRAP_SCRIPT


def test_bootstrap_does_not_reference_removed_release_or_site_resources() -> None:
    """一键安装脚本只能描述仓内前端构建，不能承诺已移除的上游资源。"""
    assert "下载前端 release" not in BOOTSTRAP_SCRIPT
    assert "MoviePilot-Resources" not in BOOTSTRAP_SCRIPT
    assert "资源文件" not in BOOTSTRAP_SCRIPT
