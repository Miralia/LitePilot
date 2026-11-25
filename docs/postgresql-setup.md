# PostgreSQL 数据库配置指南

LitePilot 默认使用 SQLite，也可以连接外部 PostgreSQL 服务。项目不提供内置 PostgreSQL 容器或嵌入式 PostgreSQL 数据目录；数据库服务的安装、高可用、备份和升级由部署环境自行管理。

## 配置选项

在 `app.env` 或进程环境变量中设置：

```bash
DB_TYPE=postgresql
DB_POSTGRESQL_HOST=localhost
DB_POSTGRESQL_PORT=5432
DB_POSTGRESQL_DATABASE=moviepilot
DB_POSTGRESQL_USERNAME=moviepilot
DB_POSTGRESQL_PASSWORD=请使用独立强密码
DB_POSTGRESQL_POOL_SIZE=10
DB_POSTGRESQL_MAX_OVERFLOW=50
```

恢复 SQLite 时设置：

```bash
DB_TYPE=sqlite
```

## Unix Socket 连接

如果 PostgreSQL 通过 Unix Socket 暴露，可以把 `DB_POSTGRESQL_HOST` 设置为套接字目录，并将 TCP 端口留空：

```bash
DB_TYPE=postgresql
DB_POSTGRESQL_HOST=/var/run/postgresql
DB_POSTGRESQL_PORT=
DB_POSTGRESQL_DATABASE=moviepilot
DB_POSTGRESQL_USERNAME=moviepilot
DB_POSTGRESQL_PASSWORD=请使用独立强密码
```

如需显式指定 socket 端口，也可以保留 `DB_POSTGRESQL_PORT`，程序会生成带 `host=/path/to/socket` 查询参数的 PostgreSQL URL。

## 数据迁移

### 从 SQLite 迁移到 PostgreSQL

1. 停止 LitePilot，避免迁移期间继续写入 SQLite。
2. 备份 `${CONFIG_DIR}/user.db` 和整个配置目录。
3. 在 PostgreSQL 中创建独立数据库和账号。
4. 修改配置为 PostgreSQL。
5. 启动应用，让 Alembic 自动创建表结构。
6. 使用可靠的离线迁移工具或手工 SQL 导入历史数据。

如果从既有数据库导入含自增主键的数据，导入后必须重建序列起点，否则后续插入可能违反主键唯一约束。可以对每张包含 `id` 自增主键的表执行以下模板（示例使用 `transferhistory`，实际表名请逐表替换）：

```sql
DO $$
DECLARE
    max_id INTEGER;
BEGIN
    SELECT COALESCE(MAX(id), 0) INTO max_id FROM transferhistory;
    EXECUTE format('ALTER SEQUENCE transferhistory_id_seq RESTART WITH %s', max_id + 1);
END $$;
```

`user` 是 PostgreSQL 关键字，如需处理用户表，应写成 `public.user` 并相应调整序列名。

### 从 PostgreSQL 迁移到 SQLite

1. 停止 LitePilot。
2. 使用 `pg_dump` 导出 PostgreSQL 数据。
3. 修改配置为 SQLite。
4. 启动应用，让 Alembic 初始化 SQLite 表结构。
5. 离线转换并导入数据，确认无误后再恢复服务。

## 备份与恢复

PostgreSQL 数据不存放在 `${CONFIG_DIR}` 中，不能使用配置目录备份代替数据库备份。建议使用 `pg_dump` 做逻辑备份：

```bash
pg_dump -h localhost -U moviepilot -d moviepilot > moviepilot_backup.sql
```

恢复单个数据库：

```bash
psql -h localhost -U moviepilot -d moviepilot < moviepilot_backup.sql
```

备份命令不应写入应用日志或提交到仓库；密码请通过 PostgreSQL 标准认证机制或受控环境变量提供。

## 性能与连接池

- 根据应用负载调整 `DB_POSTGRESQL_POOL_SIZE`。
- 设置合适的 `DB_POSTGRESQL_MAX_OVERFLOW`。
- PostgreSQL 服务端的 `shared_buffers`、`work_mem`、`maintenance_work_mem` 等参数由数据库管理员按宿主资源调整。
- 定期执行 `VACUUM` 和 `ANALYZE`，并关注慢查询日志。

## 故障排除

1. 连接失败：确认 PostgreSQL 服务启动、监听地址、端口、防火墙和账号密码正确。
2. 权限问题：确认应用账号对目标数据库拥有建表、读写和执行迁移所需权限，并检查 `pg_hba.conf`。
3. 深度检查：可执行 `moviepilot doctor --deep` 做 PostgreSQL TCP 连通性探测。
4. 日志查看：应用问题查看 LitePilot 日志；数据库服务问题查看 PostgreSQL 日志或 `journalctl -u postgresql`。

## 注意事项

- 建议使用 PostgreSQL 12 或更高版本。
- 数据库和客户端使用 UTF-8 字符集。
- 切换数据库类型前必须先停止应用并备份。
- 不要把数据库密码写入文档、Issue、截图或日志。
