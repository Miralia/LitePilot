# 10 — Data and Persistent Management

## Database Models

**Location:** `app/db/models/`

Models are SQLAlchemy declarative classes. Each model maps to one database table.

| Model | Table Domain |
|---|---|
| `TransferHistory` | 整理历史记录 |
| `DownloadHistory` / `DownloadFiles` | 下载任务历史与种子文件清单 |
| `DownloadFailure` | 整理失败记录 |
| `MediaServerItem` | 媒体服务器条目缓存 |
| `SystemConfig` | 运行时键值配置 |
| `UserConfig` | 用户级配置 |
| `User` | 用户账号（由 swizzin 同步） |
| `Message` | 消息记录 |

站点、订阅、插件、工作流、PassKey 等模型已随功能一并移除，不要重新引入。

---

## Alembic Migrations

**Location:** `database/versions/`

**Rule:** Any change to a SQLAlchemy model schema (adding a column, renaming a column, changing a column type, adding a table, removing a table) **requires a new Alembic migration script**. Never update models without a corresponding migration.

**Generating a migration:**

```bash
# Auto-generate from model diff
alembic revision --autogenerate -m "describe the change"

# Create a blank migration for manual SQL
alembic revision -m "describe the change"
```

**Review the auto-generated migration before committing** — auto-generation can miss nullable changes, index modifications, or SQLite-incompatible operations.

---

## Data Access Layer (Oper Pattern)

**Location:** `app/db/`

Each model has a corresponding `*_oper.py` file containing the data access class. Do not write SQLAlchemy queries directly in chain, module, or endpoint code.

| Oper Class | File |
|---|---|
| `SystemConfigOper` | `systemconfig_oper.py` |
| `TransferHistoryOper` | `transferhistory_oper.py` |
| `DownloadHistoryOper` | `downloadhistory_oper.py` |
| `DownloadFailureOper` | `downloadfailure_oper.py` |
| `MediaServerOper` | `mediaserver_oper.py` |
| `UserOper` | `user_oper.py` |
| `UserConfigOper` | `userconfig_oper.py` |
| `MessageOper` | `message_oper.py` |

**Standard Oper method conventions:**

```python
oper = TransferHistoryOper()
history = oper.get(hid=1)             # 按主键或条件查询
histories = oper.list()               # 查询全部
oper.add(TransferHistory(...))        # 新增
oper.update(hid=1, title="New Title") # 按主键更新
oper.delete(hid=1)                    # 按主键删除
```

---

## SystemConfig — Runtime Configuration

**Purpose:** Runtime business configuration that is user-editable, persisted in the database, and survives application restarts.

**Enum:** `SystemConfigKey` in `app/schemas/types.py`

**Oper:** `SystemConfigOper` in `app/db/systemconfig_oper.py`

```python
from app.schemas.types import SystemConfigKey
from app.db.systemconfig_oper import SystemConfigOper

oper = SystemConfigOper()

# Read
rss_urls = oper.get(SystemConfigKey.RssUrls)

# Write
oper.set(SystemConfigKey.RssUrls, ["https://example.com/rss"])
```

**Rule:** Never use raw string literals as `SystemConfig` keys. Always define a new `SystemConfigKey` enum entry first. Raw string key lookups are not searchable and cannot be refactored safely.

---

## UserConfig — Per-User Configuration

**Purpose:** Settings that differ per user account. Uses `UserConfigOper`.

```python
from app.db.userconfig_oper import UserConfigOper

oper = UserConfigOper()
value = oper.get(user_id=1, key="notification_enabled")
oper.set(user_id=1, key="notification_enabled", value=True)
```

---

## Settings / Environment Configuration

**Purpose:** Deployment-level, environment-level, and startup-time configuration such as ports, paths, proxies, switches, API keys, and third-party service addresses.

**Location:** `ConfigModel` and `Settings` in `app/core/config.py`

These values are read from environment variables (or `.moviepilot.env`) at startup and are immutable at runtime. They are not stored in the database.

**Access:**

```python
from app.core.config import settings

host = settings.QB_HOST
port = settings.QB_PORT
```

---

## Caching

### FileCache / AsyncFileCache

**Location:** `app/core/cache.py`

Used to cache expensive external API responses to disk. Cache entries have a configurable TTL.

```python
from app.core.cache import FileCache, fresh

cache = FileCache(cache_name="tmdb", ttl=3600)

@fresh(cache=cache, key_func=lambda tmdb_id: f"movie_{tmdb_id}")
def get_movie_detail(tmdb_id: int) -> dict:
    return self._tmdb_client.get_movie(tmdb_id)
```

### Redis (Optional)

When `REDIS_HOST` is configured, `app/modules/redis/` provides a distributed cache backend. Prefer `FileCache` for single-node deployments.

---

## Data Lifecycle Rules

- **TransferHistory:** Records are inserted after every successful file transfer. Do not delete records without user confirmation.
- **DownloadHistory:** Records are inserted when a download task is added. Linked `DownloadFiles` records track individual files within a torrent.
- **SystemConfig:** Values may be read and written freely at runtime. Changes to watched config keys trigger `on_config_changed()` on registered classes via `ConfigReloadMixin`.
- **MediaServerItem:** This is a cache of the remote media server library. It is refreshed on media server sync events and can be safely cleared and rebuilt.

---

## Sensitive Data Handling

- Never log database record contents that include personal data (user credentials, passkeys, API tokens).
- `settings.API_TOKEN` and other secret fields must not be included in log output or API responses.
- The `config list --show-secrets` flag exists specifically to gate secret visibility in the CLI.

*Last Updated: 2026-05-25*
