# 原生部署与迁移

本分支不提供 Docker 镜像：代码与配置分离，由 systemd 托管后端进程，前端静态文件由宿主
nginx 直接托管。这样升级只需替换代码目录，迁移只需搬运配置目录。

## 目录约定

| 用途 | 路径 | 说明 |
|---|---|---|
| 代码 | `/opt/moviepilot` | 仓库检出目录，升级时整体替换 |
| 虚拟环境 | `/opt/moviepilot/venv` | `moviepilot install deps` 创建 |
| 前端产物 | `/opt/moviepilot/public` | `./scripts/build-frontend.sh` 构建 |
| 配置与数据库 | `/var/lib/moviepilot` | `CONFIG_DIR`，备份/迁移的唯一对象 |
| 日志 | `/var/lib/moviepilot/logs` | 备份时自动排除 |

> 生产环境若沿用 swizzin 的目录布局，也可把 `CONFIG_DIR` 指向 `~/moviepilot` 等位置；
> 所有命令都接受 `--config-dir`，不依赖固定路径。

## 首次安装

```bash
git clone <repo> /opt/moviepilot && cd /opt/moviepilot

# 1. 后端依赖（创建 venv 并安装 requirements）
./moviepilot install deps --config-dir /var/lib/moviepilot

# 2. 前端：从源码构建（本分支前端源码在 web/）
./scripts/build-frontend.sh

# 3. 初始化配置与超级管理员
./moviepilot init --config-dir /var/lib/moviepilot

# 4. 开机自启
./moviepilot startup enable --config-dir /var/lib/moviepilot
./moviepilot start --config-dir /var/lib/moviepilot
```

## nginx 反代

前端由 nginx 托管 `public/`，`/api` 反代到后端端口（默认 3001）。放在 swizzin 的
`/etc/nginx/apps/` 下即可被主配置 include：

```nginx
location /mp/ {
    alias /opt/moviepilot/public/;
    try_files $uri $uri/ /mp/index.html;
}
location /mp/api/ {
    proxy_pass http://127.0.0.1:3001/api/;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

改完执行 `nginx -t && systemctl reload nginx`。

## 备份与恢复

备份对象是配置目录（含 SQLite 数据库），日志与缓存等可重建内容自动排除。

```bash
# 备份（默认写到配置目录同级）
./moviepilot backup --config-dir /var/lib/moviepilot --output /root/mp-backup.tar.gz

# 恢复前必须先停止服务，避免数据库写入冲突
./moviepilot stop
./moviepilot restore /root/mp-backup.tar.gz --config-dir /var/lib/moviepilot --overwrite
./moviepilot start
```

备份包内含 `moviepilot-backup.json` 清单（格式版本、创建时间、文件数、来源目录）；
恢复时会校验清单与包内路径，出现越界路径直接拒绝，避免半包状态破坏现有数据。

## 从 Docker 迁移

旧容器把配置放在挂载卷里（例如 `/moviepilot-v2/config`）。迁移过程会先把当前配置
备份成可回滚的包，再把旧配置搬过来：

```bash
./moviepilot stop
./moviepilot migrate --config-dir /moviepilot-v2/config
./moviepilot start
```

要点：

- SQLite 数据库（`user.db`）随配置目录一并迁移；如用 PostgreSQL 需自行导出导入。
- 迁移前会打印回滚用的备份包路径，回滚即用 `moviepilot restore` 恢复该包。
- 旧的 `app.env` 会被一并带入；迁移后请核对 `CONFIG_DIR`、下载器路径映射与媒体库路径。
- 确认无误后再删除旧容器，避免不可逆丢失。

## 升级

```bash
./moviepilot backup                       # 升级前留一份可回滚备份
git -C /opt/moviepilot pull --ff-only
./moviepilot install deps                 # 依赖有变化时
./scripts/build-frontend.sh --skip-install
./moviepilot restart
```

数据库结构变更由启动时的 Alembic 迁移自动完成；若迁移失败，用升级前的备份回滚。
