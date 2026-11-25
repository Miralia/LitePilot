"""整理重命名渲染的回归测试。"""
from pathlib import Path

from app.modules.filemanager.transhandler import TransHandler


def test_get_rename_path_renders_template_with_builtin_context():
    """重命名模板只使用主程序提供的上下文渲染。"""
    rename_dict = {"title": "Foo", "effect": "SDR"}

    path = TransHandler.get_rename_path(
        template_string="{{title}}{% if effect %} {{effect}}{% endif %}",
        rename_dict=rename_dict,
        source_path="/downloads/foo.mkv",
    )

    assert path.as_posix() == "Foo SDR"
    assert rename_dict == {"title": "Foo", "effect": "SDR"}


def test_get_rename_path_appends_rendered_path_to_base_path():
    """提供基础路径时按原契约拼接渲染结果。"""
    path = TransHandler.get_rename_path(
        template_string="{{title}}/{{season_episode}}",
        rename_dict={"title": "Foo", "season_episode": "S01E01"},
        path=Path("/library"),
    )

    assert path.as_posix() == "/library/Foo/S01E01"
