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
    assert "location ~ ^/api/v1/system/(message$|progress/|logging$) {" in text
    assert "rewrite ^/api/(.*)$ /api/$1 break;" in text
    assert "location = /manifest.webmanifest {" in text
    assert "location = /version.txt {" in text


def test_render_nginx_site_subpath_prefix_normalizes_slash():
    """子路径部署时前缀缺失结尾斜杠应自动补齐。"""
    text = render_nginx_site(
        public_dir=Path("/opt/moviepilot/public"), backend_port=3001, prefix="/mp"
    )

    assert "location /mp/ {" in text
    assert "try_files $uri $uri/ /mp/index.html;" in text
    assert "location /mp/api/ {" in text
    assert "proxy_pass http://127.0.0.1:3001/api/;" in text
    assert "location ~ ^/mp/api/v1/system/(message$|progress/|logging$) {" in text
    assert "rewrite ^/mp/api/(.*)$ /api/$1 break;" in text
    assert "proxy_buffering off;" in text
    assert "proxy_cache off;" in text
    assert 'add_header X-Accel-Buffering no;' in text
    assert "location = /mp/manifest.webmanifest {" in text
    assert "location = /mp/version.txt {" in text


def test_paths_follow_systemd_and_swizzin_layout():
    """落盘路径应遵循 systemd 与 swizzin 的约定位置。"""
    assert systemd_unit_path() == Path("/etc/systemd/system/litepilot.service")
    assert nginx_site_path() == Path("/etc/nginx/apps/litepilot.conf")
    assert nginx_site_path(site_name="demo", apps_dir=Path("/tmp/nginx")) == Path(
        "/tmp/nginx/demo.conf"
    )


def test_render_nginx_site_disables_access_log_for_tokenized_api_proxy():
    """API query 可能携带 token，外层 nginx 不得把请求行明文写入 access log。"""
    text = render_nginx_site(public_dir=Path("/opt/moviepilot/public"), backend_port=3001)

    sse_block = text.split("location ~ ^/api/v1/system/", 1)[1].split("location /api/", 1)[0]
    api_block = text.split("location /api/ {", 1)[1].split("# 入口页", 1)[0]
    assert "access_log off;" in sse_block
    assert "access_log off;" in api_block


def test_render_nginx_site_adds_baseline_security_headers_to_every_leaf_location():
    """静态入口、hash 资产与 API 反代都应始终携带基础浏览器安全头。"""
    text = render_nginx_site(public_dir=Path("/opt/moviepilot/public"), backend_port=3001)

    assert text.count("add_header X-Content-Type-Options nosniff always;") == 8
    assert text.count('add_header Referrer-Policy "strict-origin-when-cross-origin" always;') == 8
