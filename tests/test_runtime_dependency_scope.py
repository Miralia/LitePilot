"""运行时依赖边界回归测试。"""

from pathlib import Path


def test_unreferenced_legacy_runtime_dependencies_are_removed() -> None:
    """运行时依赖只保留生产代码或框架运行机制真实需要的包。"""
    requirements = Path("requirements.in").read_text(encoding="utf-8")

    assert "pywin32" not in requirements
    assert "packaging" not in requirements
