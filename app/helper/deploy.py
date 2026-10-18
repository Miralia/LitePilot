# -*- coding: utf-8 -*-
"""
原生部署配置生成。

本分支不使用容器：后端由系统级 systemd 守护 ``python -m app.main``，前端静态产物
交给宿主 nginx 直接托管，``/api`` 反代到后端端口。这里只负责把两份配置渲染成文本，
写盘与 systemd/nginx 的启停由调用方（CLI deploy 命令）负责，便于先打印后落盘。
"""

from pathlib import Path
from typing import Optional

# 服务名，同时作为 unit 文件名与日志标识
SERVICE_NAME = "moviepilot"
# 默认后端监听端口（与 ConfigModel.PORT 保持一致）
DEFAULT_BACKEND_PORT = 3001

SYSTEMD_UNIT_TEMPLATE = """\
[Unit]
Description=MoviePilot 内容库维护服务
Documentation=https://github.com/Miralia/MoviePilot
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PYTHONUNBUFFERED=1
Environment=CONFIG_DIR={config_dir}
ExecStart={python_bin} -m app.main
Restart=on-failure
RestartSec=5
# 归档与整理会长时间运行，给足停止时间避免硬杀
TimeoutStopSec=60
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
"""

NGINX_SITE_TEMPLATE = """\
# MoviePilot 站点配置：静态产物由 nginx 托管，/api 反代到后端
location {prefix} {{
    alias {public_dir}/;
    try_files $uri $uri/ {prefix}index.html;
}}

location {prefix}api/ {{
    proxy_pass http://127.0.0.1:{backend_port}/api/;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    # 备份包与日志包体积较大
    client_max_body_size 100M;
}}
"""


def render_systemd_unit(
    root: Path,
    config_dir: Path,
    python_bin: Path,
    user: str = "root",
) -> str:
    """
    渲染系统级 systemd unit 内容。

    :param root: 代码目录
    :param config_dir: 配置目录，作为 CONFIG_DIR 注入
    :param python_bin: 虚拟环境中的 Python 解释器
    :param user: 运行服务的系统用户
    :return: unit 文件文本
    """
    return SYSTEMD_UNIT_TEMPLATE.format(
        user=user,
        root=root,
        config_dir=config_dir,
        python_bin=python_bin,
    )


def render_nginx_site(
    public_dir: Path,
    backend_port: int = DEFAULT_BACKEND_PORT,
    prefix: str = "/",
) -> str:
    """
    渲染 nginx 站点片段内容。

    :param public_dir: 前端构建产物目录
    :param backend_port: 后端监听端口
    :param prefix: 挂载路径前缀，例如 ``/mp/`` 用于子路径部署
    :return: nginx 配置片段文本
    """
    normalized = prefix if prefix.endswith("/") else f"{prefix}/"
    return NGINX_SITE_TEMPLATE.format(
        prefix=normalized,
        public_dir=str(public_dir).rstrip("/"),
        backend_port=backend_port,
    )


def systemd_unit_path(service_name: str = SERVICE_NAME) -> Path:
    """
    返回系统级 systemd unit 的目标路径。

    :param service_name: 服务名
    :return: unit 文件路径
    """
    return Path("/etc/systemd/system") / f"{service_name}.service"


def nginx_site_path(
    site_name: Optional[str] = None,
    apps_dir: Path = Path("/etc/nginx/apps"),
) -> Path:
    """
    返回 nginx 站点片段的落盘路径。

    默认写入 swizzin 约定的 ``/etc/nginx/apps/<name>.conf``，该目录已被主配置 include。

    :param site_name: 站点文件名（不含扩展名），默认与服务名一致
    :param apps_dir: nginx 片段目录
    :return: 配置文件路径
    """
    return apps_dir / f"{site_name or SERVICE_NAME}.conf"