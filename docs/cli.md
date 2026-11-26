# LitePilot CLI

`moviepilot` 是 LitePilot 本地源码模式的一体化入口，负责本地安装、初始化、更新，以及前后端服务管理。

## 一键安装

```shell
curl -fsSL https://raw.githubusercontent.com/Miralia/LitePilot/main/scripts/bootstrap-local.sh | bash
```

脚本会自动：

- 检测操作系统
- 自动检查并尽量安装 `git`、`curl`、`Python 3.11+`
- 克隆 `LitePilot`
- 安装后端依赖
- 使用仓内 `web/` 源码构建前端，不再下载上游前端 release
- 下载本地 Node 运行时并安装前端运行依赖
- 执行初始化向导
- 创建全局 `moviepilot` 命令
- 默认启动前后端服务

说明：

- 如果系统里已经有可用的 `Python 3.11+`，脚本会优先直接复用本地解释器
- 如果系统里没有可用的 `Python 3.11+`，脚本会再尝试自动补齐运行环境
- Linux 下安装系统依赖时通常需要 `sudo`
- 复用已有仓库时，脚本现在只会因为已跟踪源码改动而阻止自动更新，不会再被 `.DS_Store` 之类未跟踪文件卡住

如果安装完成后当前终端仍提示找不到 `moviepilot`：

- 重新打开终端
- 如果脚本提示使用了 `~/.local/bin`，执行 `source ~/.zshrc` 或 `source ~/.bashrc`

## 配置目录

本地 CLI 默认将配置目录放在程序目录外，避免直接删除程序目录时把配置一并删掉。

- macOS：`~/Library/Application Support/MoviePilot`
- Linux：`${XDG_CONFIG_HOME:-~/.config}/moviepilot`

如果在交互式终端中执行一键安装脚本，或直接执行 `moviepilot setup` / `moviepilot init` 且未传入 `--config-dir`，程序会先询问配置目录，并把上面的默认路径作为默认值展示出来。

可以在安装或初始化时手动指定：

```shell
moviepilot setup --config-dir /path/to/moviepilot-config
moviepilot init --config-dir /path/to/moviepilot-config
```

查看当前实际配置目录：

```shell
moviepilot config path
```

## 目录说明

- 后端代码：仓库根目录
- 外置配置目录：`moviepilot config path` 输出的 `Config Dir`
- 前端静态文件：`public/`
- 前端本地 Node 运行时：`.runtime/node/`
- 后端日志：`<Config Dir>/logs/moviepilot.log`
- 后端启动日志：`<Config Dir>/logs/moviepilot.stdout.log`
  该文件同样受 `LOG_MAX_FILE_SIZE` 与 `LOG_BACKUP_COUNT` 控制
- 前端启动日志：`<Config Dir>/logs/moviepilot.frontend.stdout.log`

## 帮助与发现

根帮助：

```shell
moviepilot --help
moviepilot help
moviepilot commands
```

分级帮助：

```shell
moviepilot help install
moviepilot help init
moviepilot help setup
moviepilot help uninstall
moviepilot help update
moviepilot help backup
moviepilot help config
moviepilot help config set
moviepilot help scheduler
```

配置项清单与说明：

```shell
moviepilot config keys
moviepilot config keys API
moviepilot config describe API_TOKEN
```

## 完整命令清单

```text
moviepilot install deps
moviepilot install frontend
moviepilot init
moviepilot setup
moviepilot uninstall
moviepilot update backend
moviepilot update frontend
moviepilot update all
moviepilot startup enable
moviepilot startup disable
moviepilot startup status
moviepilot start
moviepilot stop
moviepilot restart
moviepilot status
moviepilot logs
moviepilot deploy
moviepilot backup
moviepilot restore
moviepilot migrate
moviepilot doctor
moviepilot version
moviepilot config path
moviepilot config list
moviepilot config get
moviepilot config set
moviepilot config keys
moviepilot config describe
moviepilot scheduler list
moviepilot scheduler run
moviepilot help
moviepilot commands
```

## 安装命令

安装后端依赖：

```shell
moviepilot install deps
moviepilot install deps --python python3.11
moviepilot install deps --venv /path/to/venv
moviepilot install deps --recreate
moviepilot install deps --config-dir /path/to/moviepilot-config
```

说明：

- 默认会自动选择本地已安装的 `Python 3.11+` 解释器

构建并安装仓内前端：

```shell
moviepilot install frontend
moviepilot install frontend --node-version 24.22.3
moviepilot install frontend --config-dir /path/to/moviepilot-config
```

说明：

- 始终使用当前仓库 `web/` 源码构建前端，产物版本写入 `version.py` 中的 `APP_VERSION`
- 不提供独立前端 release 版本参数，避免运行时界面与后端源码不一致
- 会自动安装本地 Node 运行时
- 会自动安装 `service.js` 所需的运行依赖


## 初始化命令

初始化本地配置：

```shell
moviepilot init
moviepilot init --wizard
moviepilot init --force-token
moviepilot init --superuser admin --superuser-password 'ChangeMe123!'
moviepilot init --config-dir /path/to/moviepilot-config
```

一体化安装：

```shell
moviepilot setup
moviepilot setup --wizard
moviepilot setup --node-version 24.22.3
moviepilot setup --recreate
moviepilot setup --superuser admin --superuser-password 'ChangeMe123!'
moviepilot setup --config-dir /path/to/moviepilot-config
```

`moviepilot setup` 会串行执行：

1. 安装后端依赖
2. 构建并安装仓内前端
3. 初始化本地配置

`--wizard` 会进入交互式初始化向导，支持配置：

- `API_TOKEN`
- 超级管理员用户名与密码
- 数据库类型
  默认 `SQLite`
  可切换为 `PostgreSQL`，并填写主机、端口、数据库名、用户名、密码
- 默认下载目录与媒体库目录
- 开机自启
  可按需启用，LitePilot 会根据当前操作系统注册登录自启动
- 下载器
- 媒体服务器
- 消息通知渠道

如果希望在自动化安装时直接预设超级管理员，也可以在一键安装脚本中透传：

```shell
curl -fsSL https://raw.githubusercontent.com/Miralia/LitePilot/main/scripts/bootstrap-local.sh | \
  bash -s -- --superuser admin --superuser-password 'ChangeMe123!'
```

说明：

- `--superuser-password` 更适合自动化场景，命令可能会出现在 shell 历史中
- 交互式 `--wizard` 会在初始化过程中提示输入超级管理员用户名和密码

## 开机自启命令

管理当前本地安装的开机自启：

```shell
moviepilot startup status
moviepilot startup enable
moviepilot startup disable
moviepilot startup enable --venv /path/to/venv
moviepilot startup enable --config-dir /path/to/moviepilot-config
```

说明：

- macOS 使用 `LaunchAgent`
- Linux 优先使用 `systemd --user`，当前环境不可用时自动回退到 `XDG autostart`
- Windows 使用当前用户的 Startup 启动目录
- 注册的启动项会调用本地 CLI 的统一启动入口，因此会同时拉起后端与前端

## 卸载命令

卸载本地安装产物：

```shell
moviepilot uninstall
moviepilot uninstall --venv /path/to/venv
moviepilot uninstall --config-dir /path/to/moviepilot-config
```

说明：

- 卸载时会先停止当前 CLI 管理的前后端服务
- 会删除本地虚拟环境、前端运行时、本地 Node 运行时以及全局 `moviepilot` 软链接，并清理此前安装遗留的站点资源文件
- 如果之前注册过开机自启，卸载时也会一并取消
- 会询问是否同时删除配置目录，默认不删除
- 如果当前使用的是仓库内 legacy `config/` 目录，确认删除后其中的 `category.yaml` 等配置文件也会一起删除
- 整个卸载流程包含两次确认
- 源码目录会保留，如需彻底移除仓库请在确认后手动删除项目目录

## 更新命令

更新后端：

```shell
moviepilot update backend
moviepilot update backend --ref latest
moviepilot update backend --ref main
moviepilot update backend --ref v0.1.0
```

更新前端：

```shell
moviepilot update frontend
moviepilot update frontend --node-version 24.22.3
```

整体更新：

```shell
moviepilot update all
moviepilot update all --ref latest
```

说明：

- `update backend` 会更新 Git 仓库并重新安装后端依赖
- `update frontend` 会重新构建当前仓库 `web/` 源码并覆盖同步到 `public/`；文件逐个原子替换，入口 HTML 最后更新，内容寻址的上一代静态资源会保留一代，避免已打开页面在更新后立即请求到 404 chunk
- `update all` 会先更新后端，再按更新后代码重新构建前端
- 更新前请先执行 `moviepilot stop`

## 部署配置生成

生成系统级 systemd unit 与 nginx 站点片段（原生部署，不使用容器）：

```shell
moviepilot deploy --print-only          # 先看内容
moviepilot deploy --prefix /mp/         # 子路径部署
moviepilot deploy --user moviepilot     # 指定运行用户
```

写入后按提示执行：

```shell
systemctl daemon-reload
systemctl enable --now litepilot
nginx -t && systemctl reload nginx
```

说明：

- unit 直接守护 `python -m app.main`，`Restart=on-failure` 由 systemd 负责重启
- 实际写入部署配置时，会在仓库根目录写入 `.moviepilot.env`，让后续 `moviepilot` CLI 默认使用同一个 `CONFIG_DIR`；`--print-only` 不会修改该文件
- 当前生成的 systemd/nginx 文件名均为 `litepilot`；如果旧环境曾手工生成并启用上游命名的 `moviepilot.service`，迁移时不要同时启用两个后端实例
- 后端默认只监听 `127.0.0.1`；nginx 托管仓库内 `public/`，`/api` 反代到后端端口（默认 3001）；系统消息、进度与日志 SSE 会单独关闭代理缓冲
- `index.html`、`service-worker.js`、`manifest.webmanifest` 与 `version.txt` 不长期缓存，避免升级后版本判断或 PWA 元数据滞后；所有叶子 location 均显式输出 `nosniff` 与 Referrer-Policy 安全头
- swizzin 环境下片段写入 `/etc/nginx/apps/` 即被主配置 include

## 备份与迁移命令

配置目录（含 SQLite 数据库）是迁移与重装的唯一对象，日志与缓存等可重建内容自动排除。

备份：

```shell
moviepilot backup
moviepilot backup --output /root/mp-backup.tar.gz
```

恢复（需先停止服务，避免数据库写入冲突）：

```shell
moviepilot stop
moviepilot restore /root/mp-backup.tar.gz
moviepilot restore /root/mp-backup.tar.gz --config-dir /var/lib/moviepilot --overwrite
moviepilot start
```

从旧实例（含 Docker 挂载卷）迁移，迁移前会自动备份当前配置用于回滚：

```shell
moviepilot stop
moviepilot migrate --config-dir /moviepilot-v2/config
moviepilot start
```

说明：

- 备份包内写入 `moviepilot-backup.json` 清单（格式版本、时间、文件数、来源目录）
- 恢复时先解到临时目录再整体替换，包内出现越界路径会被拒绝
- SQLite 数据库随配置目录一并迁移；PostgreSQL 需自行导出导入
- 更多部署细节见 `docs/fork/deploy.md`

## 服务管理命令

`moviepilot start/stop/restart/status` 统一管理前后端。

启动、停止、重启与状态：

```shell
moviepilot start
moviepilot start --timeout 60
moviepilot start --safe
moviepilot stop
moviepilot stop --timeout 30 --force
moviepilot restart
moviepilot restart --start-timeout 60 --stop-timeout 30
moviepilot status
moviepilot version
```

说明：

- `start` 会先启动后端，再启动前端
- `start --safe` 会以安全模式启动后端，本次启动跳过调度器、监控和命令等后台任务，不修改用户配置
- 如果开启了 `MOVIEPILOT_AUTO_UPDATE=release|true|dev`，`start/restart` 会在启动前尽力执行一次本地自动更新；更新失败只告警，不阻断当前启动
- 通过系统内置的重启入口触发重启时，本地 CLI 安装模式也会复用同一套前后端进程管理完成重启
- 前端默认监听 `NGINX_PORT`，默认值 `3000`
- 后端默认监听 `PORT`，默认值 `3001`
- `TRANSFER_TASK_TIMEOUT` 控制外部异步接管的运行中整理任务失活超时，单位为分钟，默认 `120`，设为 `0` 可禁用；主程序整理线程仍在直接执行的任务不受此项清理
- 前端通过 `service.js` 代理 `/api` 到后端
- 本地前端代理在启动时会先确认后端可用；如果后端长时间不可用，前端也会自动退出，避免只剩半套服务

离线诊断：

```shell
moviepilot doctor
moviepilot doctor --json
moviepilot doctor --fix
moviepilot doctor --deep
```

说明：

- `doctor` 不依赖后端服务已经启动，会直接读取配置目录、运行时文件、日志、进程、端口、依赖、数据库和前端资源
- `--json` 输出稳定 JSON，可供脚本或 Issue 流程收集
- `--fix` 只执行白名单安全修复，例如清理过期 runtime 文件或补齐不合法的 `API_TOKEN`
- `--deep` 执行可能较慢的深度探测，例如 PostgreSQL TCP 连通性检查
- Doctor 只分析最近 24 小时日志，并跨主日志与控制台镜像聚合相同错误
- `summary.advisory` 单独统计不影响整体状态的建议项，核心错误仍正常参与状态聚合
- systemd 生产环境可使用 `CONFIG_DIR=/var/lib/moviepilot /opt/moviepilot/venv/bin/python -m app.cli doctor` 执行离线诊断

日志：

```shell
moviepilot logs
moviepilot logs --lines 100
moviepilot logs --stdio
moviepilot logs --frontend
moviepilot logs --follow
moviepilot logs --frontend --follow
moviepilot logs --stdio --follow
```

说明：

- 默认 `logs` 查看后端应用日志
- `--stdio` 查看后端启动标准输出
- `--frontend` 查看前端启动标准输出

## 配置命令

查看配置路径：

```shell
moviepilot config path
```

查看当前配置：

```shell
moviepilot config list
moviepilot config list --show-secrets
```

读取和写入单个配置：

```shell
moviepilot config get PORT
moviepilot config set PORT 3001
moviepilot config set NGINX_PORT 3000
moviepilot config set API_TOKEN your-token-here
```

查看所有可配置项：

```shell
moviepilot config keys
moviepilot config keys DB_
moviepilot config keys --show-current
moviepilot config keys --show-current --show-secrets
moviepilot config describe PORT
moviepilot config describe API_TOKEN --show-secrets
```

说明：

- `config list` 显示当前配置值
- `config keys` 显示配置项名称、类型和默认值
- `config describe` 显示单个配置项的类型、默认值和当前值

## Scheduler 命令

列出调度任务：

```shell
moviepilot scheduler list
```

立即执行调度任务：

```shell
moviepilot scheduler run transfer
```
