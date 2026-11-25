# LitePilot Doctor 诊断与自救

`moviepilot doctor` 是离线诊断入口，适合 WebUI 或后端 API 不可用时使用。它不调用 LitePilot 后端 API，而是直接检查本地配置、运行时文件、进程、端口、日志、依赖、数据库和前端资源。

## 快速使用

```shell
moviepilot doctor
moviepilot doctor --json
moviepilot doctor --fix
moviepilot doctor --deep
```

安全模式启动：

```shell
moviepilot start --safe
```

生产环境由 systemd 管理时，也可以在代码目录中直接执行：

```shell
CONFIG_DIR=/var/lib/moviepilot /opt/moviepilot/venv/bin/python -m app.cli doctor
```

## 诊断内容

Doctor 默认执行只读检查：

- 运行路径：程序目录、配置目录、日志目录、Python 解释器
- 关键配置：`API_TOKEN`、`PORT`、`NGINX_PORT`、代理格式、安全模式
- 进程与端口：后端、前端端口监听状态，runtime 文件是否过期
- 日志线索：后端日志、启动日志和前端日志最近 24 小时内的错误
- 核心依赖：FastAPI、Pydantic、SQLAlchemy、Uvicorn 等是否可导入
- 数据库：SQLite 只读打开和完整性检查；PostgreSQL 默认做配置检查
- 前端资源：`version.txt`、`service.js` 或核心静态文件是否存在
- 安全模式：当前是否跳过后台任务

`--deep` 会启用可能较慢或更依赖环境的检查，例如 PostgreSQL TCP 连通性。

整体状态只聚合会影响 LitePilot 核心运行的诊断项。纯静态前端部署下缺少独立 Node 前端端口属于预期状态，会标记为跳过且不影响整体状态。JSON 汇总中的 `warn` 保留全部警告数量，`advisory` 单独统计不影响整体状态的建议项；日志发现的 `context.log_files`、`matches` 和 `unique_matches` 分别说明来源、原始命中数和去重后命中数。

## 自救能力

`moviepilot doctor --fix` 只做白名单安全修复：

- 清理指向已退出进程的 runtime 文件
- 在未被系统环境变量锁定时，为缺失或过短的 `API_TOKEN` 生成合规值

Doctor 不会自动删除数据库、回滚迁移、修改 systemd 单元或删除用户数据。

## 安全模式

`moviepilot start --safe` 或 `MOVIEPILOT_SAFE_MODE=true` 会在本次启动中跳过：

- 调度器
- 目录监控
- 命令注册

安全模式不修改用户配置，适合调度任务、目录监控或命令服务导致后端无法启动时先恢复后台入口。修复问题后移除环境变量或使用普通 `moviepilot start` 重启即可恢复完整能力。

## 生产环境排查

生产环境建议使用只读命令先确认服务与日志状态：

```shell
systemctl status litepilot.service --no-pager
journalctl -u litepilot.service -n 200 --no-pager
CONFIG_DIR=/var/lib/moviepilot /opt/moviepilot/venv/bin/python -m app.cli doctor --json
```

如果后端端口已被 systemd 管理的进程正常监听，Doctor 会把 runtime 文件缺失或 CLI 管理状态差异视为非致命信息；不要为了避免这类提示而手工杀掉生产进程。
