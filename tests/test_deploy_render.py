# -*- coding: utf-8 -*-
"""原生部署配置渲染用例。

只验证渲染出的文本结构与关键指令，不触碰 /etc 下的真实文件。
"""
from pathlib import Path

from app.helper.deploy import (
    nginx_site_path,
    render_nginx_site,
    render_systemd_unit,
    systemd_unit_path,
)


def test_render_systemd_unit_contains_required_directives():
    """unit 应直接守护 app.main，并注入 CONFIG_DIR 与重启策略。"""
    text = render_systemd_unit(
        root=Path("/opt/moviepilot"),
        config_dir=Path("/var/lib/moviepilot"),
        python_bin=Path("/opt/moviepilot/venv/bin/python"),
        user="root",
    )

    assert "Type=simple" in text
    assert "WorkingDirectory=/opt/moviepilot" in text
    assert "Environment=CONFIG_DIR=/var/lib/moviepilot" in text
    assert "ExecStart=/opt/moviepilot/venv/bin/python -m app.main" in text
    assert "Restart=on-failure" in text
    assert "User=root" in text
    assert "WantedBy=multi-user.target" in text


def test_render_nginx_site_root_prefix():
    """根路径部署应把静态目录挂在 /，并把 /api 反代到后端端口。"""
    text = render_nginx_site(public_dir=Path("/opt/moviepilot/public"), backend_port=3001)

    assert "location / {" in text
    assert "alias /opt/moviepilot/public/;" in text
    assert "try_files $uri $uri/ /index.html;" in text
    assert "location /api/ {" in text
    assert "proxy_pass http://127.0.0.1:3001/api/;" in text


def test_render_nginx_site_subpath_prefix_normalizes_slash():
    """子路径部署时前缀缺失结尾斜杠应自动补齐。"""
    text = render_nginx_site(
        public_dir=Path("/opt/moviepilot/public"), backend_port=3001, prefix="/mp"
    )

    assert "location /mp/ {" in text
    assert "try_files $uri $uri/ /mp/index.html;" in text
    assert "location /mp/api/ {" in text
    assert "proxy_pass http://127.0.0.1:3001/api/;" in text


def test_paths_follow_systemd_and_swizzin_layout():
    """落盘路径应遵循 systemd 与 swizzin 的约定位置。"""
    assert systemd_unit_path() == Path("/etc/systemd/system/moviepilot.service")
    assert nginx_site_path() == Path("/etc/nginx/apps/moviepilot.conf")
    assert nginx_site_path(site_name="demo", apps_dir=Path("/tmp/nginx")) == Path(
        "/tmp/nginx/demo.conf"
    )